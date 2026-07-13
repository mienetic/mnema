"""Mnema — Long-term memory for AI via MCP × Vector DB.

Mnema (μνῆμα, Greek for "memory") gives language-model agents persistent,
searchable memory so they can recall facts, decisions, and context across
sessions without overflowing their context window.

Public API:
    from mnema import Mnema, MnemaConfig
    from mnema.sdk import MemoryClient
"""

from mnema._version import __version__
from mnema.config import MnemaConfig, load_config
from mnema.models import Importance, Memory, MemoryRecord, Scope, SearchResult
from mnema.service import MemoryService

__all__ = [
    "__version__",
    "MnemaConfig",
    "load_config",
    "Importance",
    "Memory",
    "MemoryRecord",
    "Scope",
    "SearchResult",
    "MemoryService",
    "Mnema",
]


def Mnema(config: MnemaConfig | None = None) -> MemoryService:
    """Create a Mnema memory service (alias for :class:`MemoryService`).

    Args:
        config: Optional configuration. Defaults to environment-driven config.

    Returns:
        A ready-to-use :class:`MemoryService` instance.
    """
    return MemoryService(config or load_config())
