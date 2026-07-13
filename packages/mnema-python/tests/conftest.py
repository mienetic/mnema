"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

# Make `import mnema` work when running from the source tree without install.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402
from tests.fakes import (  # noqa: E402
    HashingEmbedding,
    InMemoryBackend,
    make_service,
)

from mnema.backends.base import VectorBackend  # noqa: E402
from mnema.config import MnemaConfig  # noqa: E402
from mnema.embeddings.base import EmbeddingProvider  # noqa: E402


@pytest.fixture
def hashing_embedding() -> HashingEmbedding:
    return HashingEmbedding(dim=64)


@pytest.fixture
def memory_backend() -> InMemoryBackend:
    return InMemoryBackend(dim=64)


@pytest.fixture
def basic_config(tmp_path) -> MnemaConfig:
    return MnemaConfig(
        backend="sqlite_vec",
        backend_path=str(tmp_path / "mnema.db"),
        embedding="local",
        embedding_model="all-MiniLM-L6-v2",
        embedding_dim=64,
    )


@pytest.fixture
def service(
    basic_config: MnemaConfig,
    memory_backend: VectorBackend,
    hashing_embedding: EmbeddingProvider,
):
    """A MemoryService backed by in-memory fakes — fast and deterministic."""
    return make_service(basic_config, memory_backend, hashing_embedding)
