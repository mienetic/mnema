"""High-level memory orchestration.

:class:`MemoryService` ties backends, embedding providers, decay scoring, and
summarization planning together. It is the single entry point used by the MCP
tools, the SDK, and the CLI — keeping tool definitions thin.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Callable, Sequence

from mnema.backends import BackendQuery, VectorBackend, make_backend
from mnema.config import MnemaConfig, load_config
from mnema.decay import DecayParams, combine, decay_score
from mnema.embeddings import EmbeddingProvider, make_embedding
from mnema.errors import MemoryNotFoundError, ScopeError
from mnema.models import (
    Importance,
    MemoryRecord,
    Scope,
    SearchResponse,
    SearchResult,
    Stats,
)
from mnema.summarize import SummarizationPlan, plan_summarization


class MemoryService:
    """Coordinates backend, embeddings, decay, and summarization.

    The service is async-first because the MCP server, the OpenAI embedding
    client, and (potentially) remote backends are all async.
    """

    def __init__(
        self,
        config: MnemaConfig | None = None,
        *,
        backend: VectorBackend | None = None,
        embedding: EmbeddingProvider | None = None,
    ) -> None:
        self.config = config or load_config()
        self.config.validate_runtime()
        self._backend = backend or make_backend(self.config)
        self._embedding = embedding or make_embedding(self.config)
        self._decay = DecayParams(
            half_life_days=self.config.decay_half_life_days,
            floor=self.config.decay_floor,
        )

    # --- properties -----------------------------------------------------
    @property
    def backend(self) -> VectorBackend:
        return self._backend

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        return self._embedding

    @property
    def embedding_dim(self) -> int:
        return self._embedding.dim

    def _scope(self, scope: str | None) -> str:
        """Resolve a (possibly-None) scope against the configured default."""
        s = (scope or self.config.default_scope).strip()
        try:
            return str(Scope(value=s))
        except Exception as exc:
            raise ScopeError(str(exc)) from exc

    # --- write ----------------------------------------------------------
    async def remember(
        self,
        text: str,
        *,
        scope: str | None = None,
        tags: Sequence[str] | None = None,
        importance: int | Importance = Importance.NORMAL,
        metadata: dict[str, object] | None = None,
    ) -> MemoryRecord:
        """Embed and persist a new memory, returning the stored record."""
        scope_val = self._scope(scope)
        if isinstance(importance, int) and not isinstance(importance, Importance):
            importance = Importance(int(importance))
        vec = await self._embedding.embed_one(text)
        record = MemoryRecord(
            text=text,
            scope=scope_val,
            tags=list(tags or []),
            importance=importance,
            metadata=dict(metadata or {}),
            embedding_dim=len(vec),
        )
        await self._backend.add(record, vec)
        return record

    # --- read -----------------------------------------------------------
    async def get(self, memory_id: str) -> MemoryRecord:
        """Fetch a single memory, bumping its access counters."""
        record = await self._backend.get(memory_id)
        if record is None:
            raise MemoryNotFoundError(memory_id)
        await self._touch(record)
        return record

    async def recall(
        self,
        query: str,
        *,
        scope: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> SearchResponse:
        """Pure semantic vector search (no keyword boost)."""
        scope_val = self._scope(scope) if scope else None
        qvec = await self._embedding.embed_one(query)
        hits = await self._backend.search(
            BackendQuery(
                query_embedding=qvec,
                scope=scope_val,
                limit=limit,
                offset=offset,
            )
        )
        return self._rank(hits, scope_val, limit=limit, offset=offset)

    async def search(
        self,
        query: str,
        *,
        scope: str | None = None,
        tags: Sequence[str] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> SearchResponse:
        """Hybrid search: vector similarity + tag overlap + decay boost."""
        scope_val = self._scope(scope) if scope else None
        qvec = await self._embedding.embed_one(query)
        hits = await self._backend.search(
            BackendQuery(
                query_embedding=qvec,
                scope=scope_val,
                tags=list(tags) if tags else None,
                limit=limit,
                offset=offset,
            )
        )
        return self._rank(hits, scope_val, limit=limit, offset=offset)

    # --- mutate ---------------------------------------------------------
    async def update(
        self,
        memory_id: str,
        *,
        text: str | None = None,
        tags: list[str] | None = None,
        importance: int | None = None,
        metadata: dict[str, object] | None = None,
    ) -> MemoryRecord:
        """Patch a memory and re-embed when its text changes."""
        embedding = None
        if text is not None:
            embedding = await self._embedding.embed_one(text)
        updated = await self._backend.update(
            memory_id,
            text=text,
            tags=tags,
            importance=int(importance) if importance is not None else None,
            metadata=metadata,
            embedding=embedding,
        )
        if updated is None:
            raise MemoryNotFoundError(memory_id)
        return updated

    async def forget(self, memory_id: str) -> bool:
        """Delete one memory. Returns ``True`` if it existed."""
        return await self._backend.delete(memory_id)

    async def forget_scope(self, scope: str) -> int:
        """Delete every memory in a scope. Returns the count removed."""
        scope_val = self._scope(scope)
        return await self._backend.delete_by_scope(scope_val)

    async def list_scopes(self) -> dict[str, int]:
        return await self._backend.list_scopes()

    async def stats(self) -> Stats:
        scopes = await self._backend.list_scopes()
        total = await self._backend.count()
        return Stats(
            total_memories=total,
            scopes=scopes,
            embedding_provider=getattr(self._embedding, "display_name", self._embedding.name),
            embedding_dim=self.embedding_dim,
            backend=self._backend.name,
        )

    # --- re-embed (migration) -------------------------------------------
    async def reembed(
        self,
        *,
        scope: str | None = None,
        batch_size: int = 50,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Re-embed every memory using the **currently configured** embedding provider.

        Use this after switching `MNEMA_EMBEDDING` / `MNEMA_EMBEDDING_MODEL`:
        existing vectors were produced by the old model and have the wrong
        geometry (and possibly a different dimension). This re-embeds every
        memory's ``text`` with the provider this service is currently bound
        to, and writes the new vectors back.

        Safe to interrupt and re-run — already-updated memories simply get
        re-embedded again (idempotent in outcome, not in work).

        Args:
            scope: Restrict to one scope, or None for all memories.
            batch_size: How many texts to embed per provider call. Larger
                batches are more efficient but use more memory.
            on_progress: Optional callback ``(done, total)`` for progress UI.

        Returns:
            The number of memories re-embedded.

        Raises:
            ValueError: if the store is empty.
        """
        scope_val = self._scope(scope) if scope else None

        # Materialize once so we know the total for progress reporting and so
        # we don't hold the iteration open across embed calls.
        records = [r async for r in self._backend.iter_all(scope=scope_val)]
        total = len(records)
        if total == 0:
            return 0

        done = 0
        for start in range(0, total, batch_size):
            chunk = records[start : start + batch_size]
            texts = [r.text for r in chunk]
            vectors = await self._embedding.embed(texts)
            for record, vector in zip(chunk, vectors, strict=True):
                await self._backend.update(
                    record.id,
                    embedding=list(vector),
                )
                done += 1
                if on_progress is not None:
                    on_progress(done, total)
        return done

    # --- decay & summarize ---------------------------------------------
    async def apply_decay(
        self,
        *,
        scope: str | None = None,
        threshold: float = 0.05,
        dry_run: bool = True,
    ) -> list[MemoryRecord]:
        """Compute decay scores and (optionally) forget below ``threshold``.

        Args:
            scope: Restrict the sweep to one scope, or None for all.
            threshold: Decay score below which a memory is a forget candidate.
            dry_run: When True (default) nothing is deleted — only the
                candidate list is returned. Set False to actually forget.

        Returns:
            The list of memories that were (or would be) forgotten.
        """
        scope_val = self._scope(scope) if scope else None
        candidates: list[MemoryRecord] = []
        async for record in self._backend.iter_all(scope=scope_val):
            score = decay_score(
                created_at=record.created_at,
                last_accessed_at=record.last_accessed_at,
                access_count=record.access_count,
                importance=int(record.importance),
                params=self._decay,
            )
            if score <= threshold:
                candidates.append(record.model_copy(update={"score": score}))

        if not dry_run:
            for c in candidates:
                await self._backend.delete(c.id)
        return candidates

    async def summarize(
        self,
        *,
        scope: str,
        similarity_threshold: float = 0.75,
    ) -> SummarizationPlan:
        """Plan how to summarize a scope. Does NOT call any LLM."""
        scope_val = self._scope(scope)
        memories = [m async for m in self._backend.iter_all(scope=scope_val)]
        return plan_summarization(
            memories,
            scope=scope_val,
            similarity_threshold=similarity_threshold,
        )

    # --- lifecycle ------------------------------------------------------
    async def aclose(self) -> None:
        await self._embedding.aclose()
        await self._backend.aclose()

    # --- private --------------------------------------------------------
    async def _touch(self, record: MemoryRecord) -> None:
        """Bump access counters on the backend if it supports touch."""
        touch = getattr(self._backend, "touch", None)
        if touch is None:
            return
        with contextlib.suppress(Exception):
            # Touch failures must never break a read.
            await touch(record.id)

    def _rank(
        self,
        hits: Sequence,
        scope: str | None,
        *,
        limit: int,
        offset: int,
    ) -> SearchResponse:
        now = time.time()
        results: list[SearchResult] = []
        for hit in hits:
            record: MemoryRecord = hit.record
            dec = decay_score(
                created_at=record.created_at,
                last_accessed_at=record.last_accessed_at,
                access_count=record.access_count,
                importance=int(record.importance),
                params=self._decay,
                now=now,
            )
            final = combine(
                vector_score=float(hit.score),
                keyword_score=float(getattr(hit, "keyword_score", 0.0)),
                decay=dec,
                vector_weight=self.config.vector_weight,
                keyword_weight=self.config.keyword_weight,
                decay_weight=self.config.decay_weight,
            )
            results.append(
                SearchResult(
                    memory=record.model_copy(update={"score": final}),
                    score=final,
                    vector_score=float(hit.score),
                    keyword_score=float(getattr(hit, "keyword_score", 0.0)),
                    decay_score=dec,
                )
            )
        # Hybrid score may differ from backend ordering; re-sort.
        results.sort(key=lambda r: r.score, reverse=True)
        return SearchResponse(
            results=results,
            count=len(results),
            offset=offset,
            has_more=False,
            scope=scope,
        )


__all__ = ["MemoryService"]
