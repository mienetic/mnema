"""Config + error class tests."""

from __future__ import annotations

import pytest

from mnema.config import MnemaConfig
from mnema.errors import ConfigError


class TestConfig:
    def test_defaults(self):
        cfg = MnemaConfig()
        assert cfg.backend == "chroma"
        assert cfg.embedding == "local"
        assert cfg.transport == "stdio"
        assert cfg.decay_half_life_days == 30.0
        # Default weights sum to 1.
        assert (
            abs(cfg.vector_weight + cfg.keyword_weight + cfg.decay_weight - 1.0) < 1e-9
        )

    def test_validate_runtime_rejects_bad_weights(self):
        cfg = MnemaConfig(vector_weight=0.5, keyword_weight=0.5, decay_weight=0.5)
        with pytest.raises(ConfigError):
            cfg.validate_runtime()

    def test_validate_runtime_rejects_openai_without_key(self):
        cfg = MnemaConfig(embedding="openai", openai_api_key=None)
        with pytest.raises(ConfigError):
            cfg.validate_runtime()

    def test_validate_runtime_accepts_openai_with_key(self):
        cfg = MnemaConfig(embedding="openai", openai_api_key="sk-test")
        cfg.validate_runtime()  # should not raise

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("MNEMA_BACKEND", "qdrant")
        monkeypatch.setenv("MNEMA_DECAY_HALF_LIFE_DAYS", "7")
        cfg = MnemaConfig()
        assert cfg.backend == "qdrant"
        assert cfg.decay_half_life_days == 7.0


class TestErrors:
    def test_backend_not_available_message_includes_extra(self):
        from mnema.errors import BackendNotAvailableError

        err = BackendNotAvailableError("chroma", "chroma")
        msg = str(err)
        assert "chroma" in msg
        # Points at the installer (not pip), with the right extra.
        assert "install.sh" in msg
        assert "MNEMA_EXTRAS='chroma'" in msg

    def test_memory_not_found(self):
        from mnema.errors import MemoryNotFoundError

        err = MemoryNotFoundError("abc")
        assert "abc" in str(err)
        assert err.memory_id == "abc"
