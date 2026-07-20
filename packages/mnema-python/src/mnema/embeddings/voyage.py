"""Voyage AI embedding provider.

Uses the ``voyage-2`` model by default (1024-d).

Configure with::

    export MNEMA_EMBEDDING=voyage
    export MNEMA_EMBEDDING_MODEL=voyage-2
    export MNEMA_VOYAGE_API_KEY=...
"""
from __future__ import annotations

from collections.abc import Sequence

import httpx

from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider
from mnema.errors import BackendInitError

_VOYAGE_DIMS: dict[str, int] = {
    "voyage-2": 1024,
    "voyage-large-2": 1536,
    "voyage-code-2": 1536,
}


class VoyageEmbeddingProvider(EmbeddingProvider):
    """Voyage AI API embedding provider."""

    name = "voyage"

    def __init__(self, config: MnemaConfig) -> None:
        if not config.voyage_api_key:
            raise BackendInitError(
                "embedding='voyage' requires MNEMA_VOYAGE_API_KEY to be set."
            )

        self._model = config.embedding_model or "voyage-2"
        self.dim = int(
            config.embedding_dim or _VOYAGE_DIMS.get(self._model, 1024)
        )
        base_url = (config.voyage_base_url or "https://api.voyageai.com").rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {config.voyage_api_key}"},
        )
        self._name = f"voyage:{self._model}"

    @property
    def display_name(self) -> str:
        return self._name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        texts = list(texts)

        if not texts:
            return []

        try:
            response = await self._client.post(
                "/v1/embeddings",
                json={
                    "model": self._model,
                    "input": texts,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BackendInitError(
                f"Voyage embedding request failed: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise BackendInitError(
                "Voyage embedding response was not valid JSON."
            ) from exc

        items = data.get("data")
        if not isinstance(items, list):
            raise BackendInitError(
                "Voyage embedding response missing 'data'."
            )

        # OpenAI-compatible format: sort by index, extract embedding.
        sorted_items = sorted(items, key=lambda x: x.get("index", 0))
        return [
            list(map(float, item["embedding"]))
            for item in sorted_items
        ]

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = ["VoyageEmbeddingProvider", "_VOYAGE_DIMS"]
