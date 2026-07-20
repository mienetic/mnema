"""Cohere embedding provider.

Uses the ``embed-english-v3.0`` model by default (1024-d). Supports
input_type for specifying how the embeddings will be used.

Configure with::

    export MNEMA_EMBEDDING=cohere
    export MNEMA_EMBEDDING_MODEL=embed-english-v3.0
    export MNEMA_COHERE_API_KEY=...
"""
from __future__ import annotations

from collections.abc import Sequence

import httpx

from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider
from mnema.errors import BackendInitError

_COHERE_DIMS: dict[str, int] = {
    "embed-english-v3.0": 1024,
    "embed-english-light-v3.0": 384,
    "embed-multilingual-v3.0": 1024,
}


class CohereEmbeddingProvider(EmbeddingProvider):
    """Cohere API embedding provider."""

    name = "cohere"

    def __init__(self, config: MnemaConfig) -> None:
        if not config.cohere_api_key:
            raise BackendInitError(
                "embedding='cohere' requires MNEMA_COHERE_API_KEY to be set."
            )

        self._model = config.embedding_model or "embed-english-v3.0"
        self.dim = int(
            config.embedding_dim or _COHERE_DIMS.get(self._model, 1024)
        )
        base_url = (config.cohere_base_url or "https://api.cohere.com").rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {config.cohere_api_key}"},
        )
        self._name = f"cohere:{self._model}"

    @property
    def display_name(self) -> str:
        return self._name

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        texts = list(texts)

        if not texts:
            return []

        try:
            response = await self._client.post(
                "/v1/embed",
                json={
                    "model": self._model,
                    "texts": texts,
                    "input_type": "search_document",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BackendInitError(
                f"Cohere embedding request failed: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise BackendInitError(
                "Cohere embedding response was not valid JSON."
            ) from exc

        embeddings = data.get("embeddings")

        if not isinstance(embeddings, list):
            raise BackendInitError(
                "Cohere embedding response missing 'embeddings'."
            )

        return [
            list(map(float, embedding))
            for embedding in embeddings
        ]

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = ["CohereEmbeddingProvider", "_COHERE_DIMS"]
