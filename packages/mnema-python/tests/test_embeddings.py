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


# ---------------------------------------------------------------------------
# Cohere
# ---------------------------------------------------------------------------

@pytest.fixture
def cohere_config() -> MnemaConfig:
    return MnemaConfig(
        embedding="cohere",
        embedding_model="embed-english-v3.0",
        cohere_api_key="test-key",
        embedding_dim=1024,
    )


class TestCohereProviderInit:
    def test_instantiates_with_defaults(self, cohere_config):
        from mnema.embeddings.cohere import CohereEmbeddingProvider

        prov = CohereEmbeddingProvider(cohere_config)
        assert isinstance(prov, EmbeddingProvider)
        assert prov.name == "cohere"
        assert prov.dim == 1024
        assert prov.display_name == "cohere:embed-english-v3.0"

    def test_raises_without_api_key(self):
        from mnema.embeddings.cohere import CohereEmbeddingProvider
        from mnema.errors import BackendInitError

        cfg = MnemaConfig(embedding="cohere", cohere_api_key=None)
        with pytest.raises(BackendInitError, match="MNEMA_COHERE_API_KEY"):
            CohereEmbeddingProvider(cfg)

    def test_dim_auto_detected_from_known_models(self):
        from mnema.embeddings.cohere import CohereEmbeddingProvider

        cfg = MnemaConfig(
            embedding="cohere",
            embedding_model="embed-english-light-v3.0",
            cohere_api_key="test-key",
        )
        prov = CohereEmbeddingProvider(cfg)
        assert prov.dim == 384


class TestCohereProviderEmbed:
    async def test_embed_parses_response(self, cohere_config, monkeypatch):
        from mnema.embeddings.cohere import CohereEmbeddingProvider

        prov = CohereEmbeddingProvider(cohere_config)

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

        captured = {}

        async def _fake_post(url, json):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

        monkeypatch.setattr(prov._client, "post", _fake_post)

        result = await prov.embed(["hello", "world"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]
        assert captured["json"]["model"] == "embed-english-v3.0"
        assert captured["json"]["texts"] == ["hello", "world"]
        assert captured["url"] == "/v1/embed"

    async def test_embed_handles_empty_input(self, cohere_config):
        from mnema.embeddings.cohere import CohereEmbeddingProvider

        prov = CohereEmbeddingProvider(cohere_config)
        result = await prov.embed([])
        assert result == []

    async def test_embed_raises_on_missing_embeddings_key(
        self, cohere_config, monkeypatch
    ):
        from mnema.embeddings.cohere import CohereEmbeddingProvider
        from mnema.errors import BackendInitError

        prov = CohereEmbeddingProvider(cohere_config)

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

    async def test_embed_raises_on_http_error(self, cohere_config, monkeypatch):
        import httpx

        from mnema.embeddings.cohere import CohereEmbeddingProvider
        from mnema.errors import BackendInitError

        prov = CohereEmbeddingProvider(cohere_config)

        async def _fake_post(url, json):  # noqa: ARG001
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(prov._client, "post", _fake_post)

        with pytest.raises(BackendInitError, match="Cohere embedding request failed"):
            await prov.embed(["hello"])


class TestCohereProviderFactory:
    def test_make_embedding_routes_cohere(self):
        from mnema.embeddings import make_embedding

        cfg = MnemaConfig(
            embedding="cohere",
            embedding_model="embed-english-v3.0",
            cohere_api_key="test-key",
        )
        prov = make_embedding(cfg)
        assert prov.name == "cohere"


# ---------------------------------------------------------------------------
# Voyage
# ---------------------------------------------------------------------------

@pytest.fixture
def voyage_config() -> MnemaConfig:
    return MnemaConfig(
        embedding="voyage",
        embedding_model="voyage-2",
        voyage_api_key="test-key",
        embedding_dim=1024,
    )


class TestVoyageProviderInit:
    def test_instantiates_with_defaults(self, voyage_config):
        from mnema.embeddings.voyage import VoyageEmbeddingProvider

        prov = VoyageEmbeddingProvider(voyage_config)
        assert isinstance(prov, EmbeddingProvider)
        assert prov.name == "voyage"
        assert prov.dim == 1024
        assert prov.display_name == "voyage:voyage-2"

    def test_raises_without_api_key(self):
        from mnema.embeddings.voyage import VoyageEmbeddingProvider
        from mnema.errors import BackendInitError

        cfg = MnemaConfig(embedding="voyage", voyage_api_key=None)
        with pytest.raises(BackendInitError, match="MNEMA_VOYAGE_API_KEY"):
            VoyageEmbeddingProvider(cfg)


class TestVoyageProviderEmbed:
    async def test_embed_parses_response(self, voyage_config, monkeypatch):
        from mnema.embeddings.voyage import VoyageEmbeddingProvider

        prov = VoyageEmbeddingProvider(voyage_config)

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "object": "list",
                    "data": [
                        {"object": "embedding", "embedding": [0.1, 0.2], "index": 0},
                        {"object": "embedding", "embedding": [0.3, 0.4], "index": 1},
                    ],
                }

        captured = {}

        async def _fake_post(url, json):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

        monkeypatch.setattr(prov._client, "post", _fake_post)

        result = await prov.embed(["hello", "world"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]
        assert captured["json"]["model"] == "voyage-2"
        assert captured["json"]["input"] == ["hello", "world"]
        assert captured["url"] == "/v1/embeddings"

    async def test_embed_handles_empty_input(self, voyage_config):
        from mnema.embeddings.voyage import VoyageEmbeddingProvider

        prov = VoyageEmbeddingProvider(voyage_config)
        result = await prov.embed([])
        assert result == []

    async def test_embed_raises_on_missing_data_key(
        self, voyage_config, monkeypatch
    ):
        from mnema.embeddings.voyage import VoyageEmbeddingProvider
        from mnema.errors import BackendInitError

        prov = VoyageEmbeddingProvider(voyage_config)

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"unexpected": "shape"}

        async def _fake_post(url, json):  # noqa: ARG001
            return _FakeResp()

        monkeypatch.setattr(prov._client, "post", _fake_post)

        with pytest.raises(BackendInitError, match="missing 'data'"):
            await prov.embed(["hello"])

    async def test_embed_raises_on_http_error(self, voyage_config, monkeypatch):
        import httpx

        from mnema.embeddings.voyage import VoyageEmbeddingProvider
        from mnema.errors import BackendInitError

        prov = VoyageEmbeddingProvider(voyage_config)

        async def _fake_post(url, json):  # noqa: ARG001
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(prov._client, "post", _fake_post)

        with pytest.raises(BackendInitError, match="Voyage embedding request failed"):
            await prov.embed(["hello"])


class TestVoyageProviderFactory:
    def test_make_embedding_routes_voyage(self):
        from mnema.embeddings import make_embedding

        cfg = MnemaConfig(
            embedding="voyage",
            embedding_model="voyage-2",
            voyage_api_key="test-key",
        )
        prov = make_embedding(cfg)
        assert prov.name == "voyage"


# ---------------------------------------------------------------------------
# Nomic
# ---------------------------------------------------------------------------

@pytest.fixture
def nomic_config() -> MnemaConfig:
    return MnemaConfig(
        embedding="nomic",
        embedding_model="nomic-embed-text-v1",
        nomic_api_key="test-key",
        embedding_dim=768,
    )


class TestNomicProviderInit:
    def test_instantiates_with_defaults(self, nomic_config):
        from mnema.embeddings.nomic import NomicEmbeddingProvider

        prov = NomicEmbeddingProvider(nomic_config)
        assert isinstance(prov, EmbeddingProvider)
        assert prov.name == "nomic"
        assert prov.dim == 768
        assert prov.display_name == "nomic:nomic-embed-text-v1"

    def test_raises_without_api_key(self):
        from mnema.embeddings.nomic import NomicEmbeddingProvider
        from mnema.errors import BackendInitError

        cfg = MnemaConfig(embedding="nomic", nomic_api_key=None)
        with pytest.raises(BackendInitError, match="MNEMA_NOMIC_API_KEY"):
            NomicEmbeddingProvider(cfg)


class TestNomicProviderEmbed:
    async def test_embed_parses_response(self, nomic_config, monkeypatch):
        from mnema.embeddings.nomic import NomicEmbeddingProvider

        prov = NomicEmbeddingProvider(nomic_config)

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {
                    "object": "list",
                    "data": [
                        {"object": "embedding", "embedding": [0.1, 0.2], "index": 0},
                        {"object": "embedding", "embedding": [0.3, 0.4], "index": 1},
                    ],
                }

        captured = {}

        async def _fake_post(url, json):
            captured["url"] = url
            captured["json"] = json
            return _FakeResp()

        monkeypatch.setattr(prov._client, "post", _fake_post)

        result = await prov.embed(["hello", "world"])
        assert result == [[0.1, 0.2], [0.3, 0.4]]
        assert captured["json"]["model"] == "nomic-embed-text-v1"
        assert captured["json"]["input"] == ["hello", "world"]
        assert captured["url"] == "/v1/embeddings"

    async def test_embed_handles_empty_input(self, nomic_config):
        from mnema.embeddings.nomic import NomicEmbeddingProvider

        prov = NomicEmbeddingProvider(nomic_config)
        result = await prov.embed([])
        assert result == []

    async def test_embed_raises_on_missing_data_key(
        self, nomic_config, monkeypatch
    ):
        from mnema.embeddings.nomic import NomicEmbeddingProvider
        from mnema.errors import BackendInitError

        prov = NomicEmbeddingProvider(nomic_config)

        class _FakeResp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"unexpected": "shape"}

        async def _fake_post(url, json):  # noqa: ARG001
            return _FakeResp()

        monkeypatch.setattr(prov._client, "post", _fake_post)

        with pytest.raises(BackendInitError, match="missing 'data'"):
            await prov.embed(["hello"])

    async def test_embed_raises_on_http_error(self, nomic_config, monkeypatch):
        import httpx

        from mnema.embeddings.nomic import NomicEmbeddingProvider
        from mnema.errors import BackendInitError

        prov = NomicEmbeddingProvider(nomic_config)

        async def _fake_post(url, json):  # noqa: ARG001
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(prov._client, "post", _fake_post)

        with pytest.raises(BackendInitError, match="Nomic embedding request failed"):
            await prov.embed(["hello"])


class TestNomicProviderFactory:
    def test_make_embedding_routes_nomic(self):
        from mnema.embeddings import make_embedding

        cfg = MnemaConfig(
            embedding="nomic",
            embedding_model="nomic-embed-text-v1",
            nomic_api_key="test-key",
        )
        prov = make_embedding(cfg)
        assert prov.name == "nomic"
