"""Vector-backend implementations and factory.

Use :func:`make_backend` to construct the right backend from a
:class:`~mnema.config.MnemaConfig`. Each concrete backend is imported lazily
so the optional dependency (chromadb / qdrant-client / sqlite-vec) is only
required when its backend is actually selected.
"""

from __future__ import annotations

from mnema.backends.base import BackendHit, BackendQuery, VectorBackend
from mnema.config import MnemaConfig
from mnema.errors import BackendNotAvailableError, ConfigError


def make_backend(config: MnemaConfig) -> VectorBackend:
    """Construct a :class:`VectorBackend` based on ``config.backend``.

    Raises:
        BackendNotAvailableError: if the selected backend's optional
            dependency isn't installed.
        ConfigError: if ``config.backend`` is unknown.
    """
    backend = config.backend
    if backend == "chroma":
        try:
            from mnema.backends.chroma import ChromaBackend
        except ImportError as exc:  # pragma: no cover - exercised via import guard
            raise BackendNotAvailableError("chroma", "chroma") from exc
        return ChromaBackend(config)

    if backend == "qdrant":
        try:
            from mnema.backends.qdrant import QdrantBackend
        except ImportError as exc:  # pragma: no cover
            raise BackendNotAvailableError("qdrant", "qdrant") from exc
        return QdrantBackend(config)

    if backend == "sqlite_vec":
        try:
            from mnema.backends.sqlite_vec import SqliteVecBackend
        except ImportError as exc:  # pragma: no cover
            raise BackendNotAvailableError("sqlite_vec", "sqlite_vec") from exc
        return SqliteVecBackend(config)

    if backend == "lancedb":
        try:
            from mnema.backends.lancedb import LanceDBBackend
        except ImportError as exc:  # pragma: no cover
            raise BackendNotAvailableError("lancedb", "lancedb") from exc
        return LanceDBBackend(config)

    raise ConfigError(f"Unknown backend: {backend!r}")


__all__ = ["BackendHit", "BackendQuery", "VectorBackend", "make_backend"]
