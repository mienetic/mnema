"""Exception hierarchy for Mnema.

All errors raised by Mnema derive from :class:`MnemaError` so callers can
catch the library's failures with a single ``except`` clause while still
distinguishing specific failure modes when needed.
"""

from __future__ import annotations


class MnemaError(Exception):
    """Base class for all Mnema errors."""


class ConfigError(MnemaError):
    """Raised when configuration is invalid or incomplete."""


class BackendError(MnemaError):
    """Base class for vector-backend errors."""


class BackendNotAvailableError(BackendError):
    """Raised when the requested backend's optional dependency is missing.

    The error message points the user at the one-line installer so they can
    recover without reading the docs.
    """

    def __init__(self, backend: str, extra: str) -> None:
        super().__init__(
            f"The {backend!r} backend requires the optional dependency "
            f"'{extra}'. Reinstall Mnema with that extra, e.g.:\n"
            f"    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh "
            f"| MNEMA_EXTRAS='{extra}' bash\n"
            f"(or MNEMA_EXTRAS='all' for every backend)."
        )
        self.backend = backend
        self.extra = extra


class EmbeddingNotAvailableError(MnemaError):
    """Raised when the requested embedding provider's dependency is missing."""

    def __init__(self, provider: str, extra: str) -> None:
        super().__init__(
            f"The {provider!r} embedding provider requires the optional "
            f"dependency '{extra}'. Reinstall Mnema with that extra, e.g.:\n"
            f"    curl -fsSL https://raw.githubusercontent.com/mienetic/mnema/main/scripts/install.sh "
            f"| MNEMA_EXTRAS='{extra}' bash\n"
            f"(or MNEMA_EXTRAS='all' for every backend)."
        )
        self.provider = provider
        self.extra = extra


class BackendInitError(BackendError):
    """Raised when a backend fails to initialize."""


class MemoryNotFoundError(MnemaError):
    """Raised when a memory id does not exist."""

    def __init__(self, memory_id: str) -> None:
        super().__init__(f"Memory not found: {memory_id!r}")
        self.memory_id = memory_id


class ScopeError(MnemaError):
    """Raised when a scope string is malformed."""


__all__ = [
    "BackendError",
    "BackendInitError",
    "BackendNotAvailableError",
    "ConfigError",
    "EmbeddingNotAvailableError",
    "MemoryNotFoundError",
    "MnemaError",
    "ScopeError",
]
