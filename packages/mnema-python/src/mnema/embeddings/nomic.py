"""Nomic embedding provider.

Uses the ``nomic-embed-text-v1`` model by default (768-d).

Configure with::

    export MNEMA_EMBEDDING=nomic
    export MNEMA_EMBEDDING_MODEL=nomic-embed-text-v1
    export MNEMA_NOMIC_API_KEY=...
"""
from __future__ import annotations

from collections.abc import Sequence

import httpx

from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider
from mnema.errors import BackendInitError

_NOMIC_DIMS: dict[str, int] = {
    "nomic-embed-text-v1": 768,
    "nomic-embed-text-v1.5": 768,
}


class NomicEmbeddingProvider(EmbeddingProvider):
    """Nomic API embedding provider."""

    name = "nomic"

    def __init__(self, config: MnemaConfig) -> None:
        if not config.nomic_api_key:
            raise BackendInitError(
                "embedding='nomic' requires MNEMA_NOMIC_API_KEY to be set."
            )

        self._model = config.embedding_model or "nomic-embed-text-v1"
        self.dim = int(
            config.embedding_dim or _NOMIC_DIMS.get(self._model, 768)
        )
        base_url = (config.nomic_base_url or "https://api-atlas.nomic.ai").rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {config.nomic_api_key}"},
        )
        self._name = f"nomic:{self._model}"

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
                f"Nomic embedding request failed: {exc}"
            ) from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise BackendInitError(
                "Nomic embedding response was not valid JSON."
            ) from exc

        items = data.get("data")
        if not isinstance(items, list):
            raise BackendInitError(
                "Nomic embedding response missing 'data'."
            )

        sorted_items = sorted(items, key=lambda x: x.get("index", 0))
        return [
            list(map(float, item["embedding"]))
            for item in sorted_items
        ]

    async def aclose(self) -> None:
        await self._client.aclose()


__all__ = ["NomicEmbeddingProvider", "_NOMIC_DIMS"]
