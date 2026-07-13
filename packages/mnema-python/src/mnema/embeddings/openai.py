"""OpenAI embedding provider.

Uses the ``text-embedding-3-*`` family. Supports the ``dimensions`` parameter
so you can shorten vectors (e.g. 256-d from ``text-embedding-3-large``) to
trade a little recall for big storage savings.

Install with::

    pip install 'mnema-mcp[openai]'

Configure with::

    export MNEMA_EMBEDDING=openai
    export MNEMA_EMBEDDING_MODEL=text-embedding-3-small
    export MNEMA_OPENAI_API_KEY=sk-...
"""

from __future__ import annotations

from collections.abc import Sequence

from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider
from mnema.errors import BackendInitError

_OPENAI_DIMS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI API embedding provider."""

    name = "openai"

    def __init__(self, config: MnemaConfig) -> None:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - guarded by factory
            raise BackendInitError(
                "openai is not installed. Install with: "
                "pip install 'mnema-mcp[openai]'"
            ) from exc

        if not config.openai_api_key:
            raise BackendInitError(
                "embedding='openai' requires MNEMA_OPENAI_API_KEY to be set."
            )

        self._model = config.embedding_model or "text-embedding-3-small"
        self._dimensions = config.embedding_dim
        self.dim = int(
            config.embedding_dim or _OPENAI_DIMS.get(self._model, 1536)
        )
        self._client = AsyncOpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )
        self._name = f"openai:{self._model}"

    @property
    def display_name(self) -> str:
        return self._name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        texts = list(texts)
        kwargs: dict[str, object] = {"input": texts, "model": self._model}
        if self._dimensions is not None:
            kwargs["dimensions"] = self._dimensions
        try:
            res = await self._client.embeddings.create(**kwargs)  # type: ignore[arg-type]
        except Exception as exc:
            raise BackendInitError(f"OpenAI embedding request failed: {exc}") from exc
        # OpenAI returns vectors already normalized for the 3-* family.
        return [list(map(float, d.embedding)) for d in res.data]

    async def aclose(self) -> None:
        await self._client.close()


__all__ = ["OpenAIEmbeddingProvider", "_OPENAI_DIMS"]
