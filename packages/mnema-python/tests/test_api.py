"""Tests for the REST API layer (``mnema.api``).

Route tests run against a real :class:`~mnema.service.MemoryService` built from
the in-memory fakes (``InMemoryBackend`` + ``HashingEmbedding``) via the shared
``service`` fixture — no live server, no embedding-model download. They use
FastAPI's ``TestClient``, which drives the ASGI app in-process. If FastAPI
isn't installed the ``client`` fixture skips those tests (the ``[api]`` extra is
optional), while ``test_core_imports_without_fastapi`` always runs to prove the
core package doesn't need FastAPI.
"""

from __future__ import annotations

import sys
import uuid

import pytest


@pytest.fixture
def client(service):
    """A FastAPI TestClient wired to the in-memory fake service.

    Skips (rather than errors) when FastAPI isn't installed so a minimal
    install still runs the rest of the suite.
    """
    pytest.importorskip("fastapi", reason="fastapi not installed ([api] extra)")
    from fastapi.testclient import TestClient

    from mnema.api.app import create_app

    app = create_app(service=service)
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# GET /memories  (list)
# ---------------------------------------------------------------------------
def test_list_memories_empty(client):
    resp = client.get("/memories")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_memories_returns_created(client):
    client.post("/memories", json={"text": "first fact"})
    client.post("/memories", json={"text": "second fact"})
    resp = client.get("/memories")
    assert resp.status_code == 200
    texts = {m["text"] for m in resp.json()}
    assert texts == {"first fact", "second fact"}


def test_list_memories_scope_filter(client):
    client.post("/memories", json={"text": "alice fact", "scope": "user:alice"})
    client.post("/memories", json={"text": "bob fact", "scope": "user:bob"})
    resp = client.get("/memories", params={"scope": "user:alice"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["scope"] == "user:alice"


# ---------------------------------------------------------------------------
# POST /memories  (create)
# ---------------------------------------------------------------------------
def test_create_memory(client):
    resp = client.post(
        "/memories",
        json={"text": "Alice likes tea", "scope": "user:alice", "tags": ["pref"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["text"] == "Alice likes tea"
    assert body["scope"] == "user:alice"
    assert body["tags"] == ["pref"]
    assert "id" in body


def test_create_validation_rejected(client):
    # `text` is required — omitting it is a 422 (pydantic body validation).
    resp = client.post("/memories", json={"scope": "user:alice"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /memories/{id}
# ---------------------------------------------------------------------------
def test_get_memory(client):
    created = client.post("/memories", json={"text": "recall me"}).json()
    resp = client.get(f"/memories/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["text"] == "recall me"


def test_get_missing_memory_404(client):
    resp = client.get(f"/memories/{uuid.uuid4().hex}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /memories/{id}
# ---------------------------------------------------------------------------
def test_update_memory(client):
    created = client.post("/memories", json={"text": "old text"}).json()
    resp = client.patch(f"/memories/{created['id']}", json={"text": "new text"})
    assert resp.status_code == 200
    assert resp.json()["text"] == "new text"


def test_update_missing_memory_404(client):
    resp = client.patch(f"/memories/{uuid.uuid4().hex}", json={"text": "x"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /memories/{id}
# ---------------------------------------------------------------------------
def test_delete_memory(client):
    created = client.post("/memories", json={"text": "delete me"}).json()
    resp = client.delete(f"/memories/{created['id']}")
    assert resp.status_code == 204
    # Now gone.
    assert client.get(f"/memories/{created['id']}").status_code == 404


def test_delete_missing_memory_404(client):
    resp = client.delete(f"/memories/{uuid.uuid4().hex}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------
def test_search_happy_path(client):
    client.post("/memories", json={"text": "Alice drinks Earl Grey tea", "tags": ["pref"]})
    resp = client.post("/search", json={"query": "tea", "tags": ["pref"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    # Hybrid search factors tag overlap in — the matching tag yields a nonzero
    # keyword component. (Pure recall, which ignores tags, would be 0 here.)
    assert body["results"][0]["keyword_score"] > 0


# ---------------------------------------------------------------------------
# POST /recall
# ---------------------------------------------------------------------------
def test_recall_happy_path(client):
    client.post("/memories", json={"text": "Bob codes in Rust", "scope": "user:bob"})
    resp = client.post("/recall", json={"query": "Rust", "scope": "user:bob"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 1
    assert "Bob" in body["results"][0]["memory"]["text"]


# ---------------------------------------------------------------------------
# GET /scopes
# ---------------------------------------------------------------------------
def test_scopes(client):
    client.post("/memories", json={"text": "a", "scope": "user:x"})
    client.post("/memories", json={"text": "b", "scope": "user:y"})
    resp = client.get("/scopes")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user:x"] == 1
    assert body["user:y"] == 1


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------
def test_stats(client):
    client.post("/memories", json={"text": "one"})
    resp = client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_memories"] == 1
    assert "embedding_provider" in body
    assert "backend" in body


# ---------------------------------------------------------------------------
# Optional-dependency isolation
# ---------------------------------------------------------------------------
def test_core_imports_without_fastapi(monkeypatch):
    """`import mnema` must work with FastAPI absent.

    Simulate the minimal install by making ``import fastapi`` fail, drop any
    cached ``mnema`` modules, and re-import the core package. It must succeed —
    proving the REST layer is never pulled in by the core import chain.
    """
    monkeypatch.setitem(sys.modules, "fastapi", None)  # None → ImportError on import
    for name in list(sys.modules):
        if name == "mnema" or name.startswith("mnema."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    import mnema  # noqa: F401 — the import itself is the assertion

    assert mnema.MemoryService is not None
    # Sanity: fastapi genuinely unimportable in this simulated environment.
    with pytest.raises(ImportError):
        import fastapi  # noqa: F401
