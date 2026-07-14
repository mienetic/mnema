"""Tests for embedding providers (currently Ollama; others covered via backends).

The Ollama provider talks to an HTTP server we don't have in CI, so these
tests mock httpx to verify the request shape, response parsing, and error
handling — without needing a running Ollama instance.
"""

from __future__ import annotations

import pytest

from mnema.config import MnemaConfig
from mnema.embeddings.base import EmbeddingProvider


@pytest.fixture
def ollama_config() -> MnemaConfig:
    return MnemaConfig(
        embedding="ollama",
        embedding_model="nomic-embed-text",
        ollama_url="http://localhost:11434",
        embedding_dim=768,
    )


class TestOllamaProviderInit:
    def test_instantiates_with_defaults(self, ollama_config):
        from mnema.embeddings.ollama import OllamaEmbeddingProvider

        prov = OllamaEmbeddingProvider(ollama_config)
        assert isinstance(prov, EmbeddingProvider)
        assert prov.name == "ollama"
        assert prov.dim == 768
        assert prov.display_name == "ollama:nomic-embed-text"

    def test_base_url_trailing_slash_stripped(self):
        from mnema.embeddings.ollama import OllamaEmbeddingProvider

        cfg = MnemaConfig(
            embedding="ollama",
            embedding_model="nomic-embed-text",
            ollama_url="http://localhost:11434/",
        )
        prov = OllamaEmbeddingProvider(cfg)
        assert prov._base_url == "http://localhost:11434"

    def test_dim_auto_detected_from_known_models(self):
        from mnema.embeddings.ollama import OllamaEmbeddingProvider

        cfg = MnemaConfig(
            embedding="ollama",
            embedding_model="nomic-embed-text",
            ollama_url="http://localhost:11434",
        )
        prov = OllamaEmbeddingProvider(cfg)
        # nomic-embed-text is in _OLLAMA_DIMS → 768.
        assert prov.dim == 768


pytestmark = pytest.mark.asyncio


class TestOllamaProviderEmbed:
    async def test_embed_parses_response(self, ollama_config, monkeypatch):
        """Mock httpx to return a canned embedding response."""
        from mnema.embeddings.ollama import OllamaEmbeddingProvider

        prov = OllamaEmbeddingProvider(ollama_config)

        # Build a fake response object.
        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}

        captured = {}

        async def _fake_post(url, json):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

        # Patch the instance method directly (no `self`).
        monkeypatch.setattr(prov._client, "post", _fake_post)

        result = await prov.embed(["hello", "world"])
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        # Verify the request shape.
        assert captured["json"]["model"] == "nomic-embed-text"
        assert captured["json"]["input"] == ["hello", "world"]
        assert captured["url"] == "/api/embed"

    async def test_embed_handles_empty_input(self, ollama_config):
        from mnema.embeddings.ollama import OllamaEmbeddingProvider

        prov = OllamaEmbeddingProvider(ollama_config)
        result = await prov.embed([])
        assert result == []

    async def test_embed_raises_on_missing_embeddings_key(
        self, ollama_config, monkeypatch
    ):
        from mnema.embeddings.ollama import OllamaEmbeddingProvider
        from mnema.errors import BackendInitError

        prov = OllamaEmbeddingProvider(ollama_config)

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"unexpected": "shape"}

        async def _fake_post(url, json):  # noqa: ARG001
            return _FakeResp()

        monkeypatch.setattr(prov._client, "post", _fake_post)

        with pytest.raises(BackendInitError, match="missing 'embeddings'"):
            await prov.embed(["hello"])

    async def test_embed_raises_on_http_error(self, ollama_config, monkeypatch):
        import httpx

        from mnema.embeddings.ollama import OllamaEmbeddingProvider
        from mnema.errors import BackendInitError

        prov = OllamaEmbeddingProvider(ollama_config)

        async def _fake_post(url, json):  # noqa: ARG001
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(prov._client, "post", _fake_post)

        with pytest.raises(BackendInitError, match="Ollama embedding request failed"):
            await prov.embed(["hello"])


class TestOllamaProviderFactory:
    def test_make_embedding_routes_ollama(self):
        """The factory must recognize embedding='ollama'."""
        from mnema.embeddings import make_embedding

        cfg = MnemaConfig(
            embedding="ollama",
            embedding_model="nomic-embed-text",
            ollama_url="http://localhost:11434",
        )
        prov = make_embedding(cfg)
        assert prov.name == "ollama"
