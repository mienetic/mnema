"""Ollama embedding provider.

Uses Ollama's local embedding API so embeddings can run fully locally without
loading a model in-process.

Configure with::

    export MNEMA_EMBEDDING=ollama
    export MNEMA_EMBEDDING_MODEL=nomic-embed-text
    export MNEMA_OLLAMA_URL=http://localhost:11434
"""
from __future__ import annotations

from collections.abc import Sequence

import httpx

from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider
from mnema.errors import BackendInitError

_OLLAMA_DIMS: dict[str, int] = {
    "nomic-embed-text": 768,
}


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Ollama local embedding provider."""

    name = "ollama"

    def __init__(self, config: MnemaConfig) -> None:
        self._model = config.embedding_model or "nomic-embed-text"
        self._base_url = config.ollama_url.rstrip("/")
        self.dim = int(
            config.embedding_dim or _OLLAMA_DIMS.get(self._model, 768)
        )
        self._client = httpx.AsyncClient(base_url=self._base_url)
        self._name = f"ollama:{self._model}"

    @property
    def display_name(self) -> str:
        return self._name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        texts = list(texts)

        if not texts:
            return []

        try:
            response = await self._client.post(
                "/api/embed",
                json={
                    "model": self._model,
                    "input": texts,
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BackendInitError(
                f"Ollama embedding request failed: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise BackendInitError(
                "Ollama embedding response was not valid JSON."
            ) from exc

        embeddings = data.get("embeddings")

        if not isinstance(embeddings, list):
            raise BackendInitError(
                "Ollama embedding response missing 'embeddings'."
            )

        return [
            list(map(float, embedding))
            for embedding in embeddings
        ]

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = ["OllamaEmbeddingProvider", "_OLLAMA_DIMS"]