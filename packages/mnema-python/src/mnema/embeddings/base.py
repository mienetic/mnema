"""Abstract embedding provider interface.

An *embedding provider* turns text into vectors. It is independent from the
backend so you can mix-and-match (e.g. local embeddings + remote Qdrant).

Two providers ship out of the box:

* :class:`mnema.embeddings.sentence_transformers.SentenceTransformersProvider`
  — local, offline (default)
* :class:`mnema.embeddings.openai.OpenAIEmbeddingProvider`
  — uses OpenAI's ``text-embedding-3-*`` family
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingProvider(ABC):
    """Pluggable text→vector provider."""

    #: Short identifier surfaced in stats (e.g. ``"local"``).
    name: str = "base"
    #: Vector dimensionality (must be stable for a given model).
    dim: int = 0

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of texts and return one vector per input."""

    async def embed_one(self, text: str) -> list[float]:
        """Convenience wrapper for the single-text case."""
        return (await self.embed([text]))[0]

    async def aclose(self) -> None:
        """Release resources. Default no-op."""
        return None


__all__ = ["EmbeddingProvider"]
