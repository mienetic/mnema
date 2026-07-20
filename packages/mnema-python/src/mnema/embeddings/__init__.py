"""Embedding providers and factory.

Use :func:`make_embedding` to construct the right provider from a
:class:`~mnema.config.MnemaConfig`. Providers are imported lazily so the
optional dependency (sentence-transformers / openai) is only required when
the corresponding provider is selected.
"""

from __future__ import annotations

from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider
from mnema.errors import ConfigError, EmbeddingNotAvailableError


def make_embedding(config: MnemaConfig) -> EmbeddingProvider:
    """Construct an :class:`EmbeddingProvider` based on ``config.embedding``.

    Raises:
        EmbeddingNotAvailableError: if the provider's optional dependency is
            missing.
        ConfigError: if ``config.embedding`` is unknown.
    """
    provider = config.embedding
    if provider == "local":
        try:
            from mnema.embeddings.sentence_transformers import (
                SentenceTransformersProvider,
            )
        except ImportError as exc:  # pragma: no cover - guarded by factory
            raise EmbeddingNotAvailableError("local", "local") from exc
        return SentenceTransformersProvider(config)

    if provider == "openai":
        try:
            from mnema.embeddings.openai import OpenAIEmbeddingProvider
        except ImportError as exc:  # pragma: no cover
            raise EmbeddingNotAvailableError("openai", "openai") from exc
        return OpenAIEmbeddingProvider(config)

    if provider == "ollama":
        from mnema.embeddings.ollama import OllamaEmbeddingProvider

        return OllamaEmbeddingProvider(config)

    if provider == "cohere":
        from mnema.embeddings.cohere import CohereEmbeddingProvider

        return CohereEmbeddingProvider(config)

    if provider == "voyage":
        from mnema.embeddings.voyage import VoyageEmbeddingProvider

        return VoyageEmbeddingProvider(config)

    if provider == "nomic":
        from mnema.embeddings.nomic import NomicEmbeddingProvider

        return NomicEmbeddingProvider(config)

    raise ConfigError(f"Unknown embedding provider: {provider!r}")


__all__ = ["EmbeddingProvider", "make_embedding"]
