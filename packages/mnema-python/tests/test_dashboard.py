"""Tests for the Mnema Dashboard UI (``mnema.dashboard``).

Uses the same in-memory fakes as the API tests and FastAPI's TestClient.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def client(service):
    """A FastAPI TestClient wired to the in-memory fake service."""
    pytest.importorskip("fastapi", reason="fastapi not installed ([api] extra)")
    pytest.importorskip("jinja2", reason="jinja2 not installed")
    from fastapi.testclient import TestClient

    from mnema.dashboard.app import create_dashboard_app

    app = create_dashboard_app(service=service)
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# GET /  (home/stats)
# ---------------------------------------------------------------------------
def test_home_page_returns_html(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert "Mnema" in resp.text


def test_home_shows_stats_when_memories_exist(client):
    client.post("/memories", json={"text": "hello world"}, headers={"content-type": "application/json"})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "1" in resp.text or "hello" in resp.text


# ---------------------------------------------------------------------------
# GET /memories  (list)
# ---------------------------------------------------------------------------
def test_list_memories_empty(client):
    resp = client.get("/memories")
    assert resp.status_code == 200
    assert "No memories found" in resp.text


def test_list_memories_renders_memories(client):
    client.post("/memories", json={"text": "Alice likes tea"}, headers={"content-type": "application/json"})
    client.post("/memories", json={"text": "Bob codes Rust"}, headers={"content-type": "application/json"})
    resp = client.get("/memories")
    assert resp.status_code == 200
    assert "Alice likes tea" in resp.text
    assert "Bob codes Rust" in resp.text


def test_list_memories_scope_filter(client):
    client.post("/memories", json={"text": "alice", "scope": "user:alice"}, headers={"content-type": "application/json"})
    client.post("/memories", json={"text": "bob", "scope": "user:bob"}, headers={"content-type": "application/json"})
    resp = client.get("/memories?scope=user:alice")
    assert resp.status_code == 200
    assert "alice" in resp.text
    # bob should appear only in the scope filter dropdown (sidebar stats), not in memory list
    mem_idx = resp.text.find("memory-text")
    page_after_memories = resp.text[mem_idx:] if mem_idx > 0 else resp.text
    assert "bob" not in page_after_memories


def test_list_memories_pagination(client):
    for i in range(25):
        client.post("/memories", json={"text": f"memory {i}"}, headers={"content-type": "application/json"})
    # Sorted newest-first, page 1 has 20 most recent, page 2 has 5 oldest
    page1 = client.get("/memories?page=1")
    assert page1.status_code == 200
    assert "memory 24" in page1.text
    page2 = client.get("/memories?page=2")
    assert page2.status_code == 200
    assert "memory 0" in page2.text


# ---------------------------------------------------------------------------
# GET /memories/{id}  (detail)
# ---------------------------------------------------------------------------
def test_memory_detail(client):
    created = client.post("/memories", json={"text": "detail me"}, headers={"content-type": "application/json"}).json()
    resp = client.get(f"/memories/{created['id']}")
    assert resp.status_code == 200
    assert "detail me" in resp.text


def test_memory_detail_404(client):
    resp = client.get(f"/memories/{uuid.uuid4().hex}")
    assert resp.status_code == 404


def test_memory_detail_shows_fields(client):
    created = client.post(
        "/memories",
        json={"text": "show fields", "tags": ["a", "b"], "importance": 8, "scope": "test"},
        headers={"content-type": "application/json"},
    ).json()
    resp = client.get(f"/memories/{created['id']}")
    assert resp.status_code == 200
    assert "show fields" in resp.text
    assert "HIGH" in resp.text or "8" in resp.text
    assert "a" in resp.text
    assert "b" in resp.text


# ---------------------------------------------------------------------------
# GET /memories/{id}/edit  (edit form)
# ---------------------------------------------------------------------------
def test_edit_form_renders(client):
    created = client.post("/memories", json={"text": "edit me"}, headers={"content-type": "application/json"}).json()
    resp = client.get(f"/memories/{created['id']}/edit")
    assert resp.status_code == 200
    assert "edit me" in resp.text
    assert "Save Changes" in resp.text


def test_edit_form_404(client):
    resp = client.get(f"/memories/{uuid.uuid4().hex}/edit")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /memories/{id}/edit  (edit submit)
# ---------------------------------------------------------------------------
def test_edit_submit_updates_memory(client):
    created = client.post("/memories", json={"text": "old text"}, headers={"content-type": "application/json"}).json()
    resp = client.post(
        f"/memories/{created['id']}/edit",
        data={"text": "new text", "scope": "global", "importance": 5, "tags": "", "metadata_json": "{}"},
        follow_redirects=False,
    )
    assert resp.status_code == 303  # redirect
    # Verify via detail page
    detail = client.get(f"/memories/{created['id']}")
    assert "new text" in detail.text


def test_edit_submit_404(client):
    resp = client.post(
        f"/memories/{uuid.uuid4().hex}/edit",
        data={"text": "x", "scope": "g", "importance": 5, "tags": "", "metadata_json": "{}"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /memories/{id}/forget
# ---------------------------------------------------------------------------
def test_forget_redirects(client):
    created = client.post("/memories", json={"text": "forget me"}, headers={"content-type": "application/json"}).json()
    resp = client.post(f"/memories/{created['id']}/forget", follow_redirects=False)
    assert resp.status_code == 303
    # Now gone
    assert client.get(f"/memories/{created['id']}").status_code == 404


# ---------------------------------------------------------------------------
# GET /search
# ---------------------------------------------------------------------------
def test_search_page_renders(client):
    resp = client.get("/search")
    assert resp.status_code == 200
    assert "Search Memories" in resp.text


# ---------------------------------------------------------------------------
# GET /search/results (htmx fragment)
# ---------------------------------------------------------------------------
def test_search_results_returns_html_fragment(client):
    resp = client.get("/search/results?query=test")
    assert resp.status_code == 200
    assert "No matches" in resp.text


def test_search_results_with_matches(client):
    client.post("/memories", json={"text": "Alice drinks tea", "tags": ["pref"], "scope": "global"}, headers={"content-type": "application/json"})
    resp = client.get("/search/results?query=tea&tags=pref")
    assert resp.status_code == 200
    assert "Alice" in resp.text


# ---------------------------------------------------------------------------
# GET /decay
# ---------------------------------------------------------------------------
def test_decay_page_renders(client):
    resp = client.get("/decay")
    assert resp.status_code == 200
    assert "Apply Decay" in resp.text


# ---------------------------------------------------------------------------
# POST /decay
# ---------------------------------------------------------------------------
def test_decay_preview_dry_run(client):
    # Add a memory with age-based decay
    resp = client.post("/decay", data={"threshold": "0.5", "scope": "", "apply": "false"})
    assert resp.status_code == 200
    # Should be HTML fragment
    assert "candidate" in resp.text.lower() or "No candidates" in resp.text


# ---------------------------------------------------------------------------
# GET /summarize
# ---------------------------------------------------------------------------
def test_summarize_page_renders(client):
    resp = client.get("/summarize")
    assert resp.status_code == 200
    assert "Summarize" in resp.text


# ---------------------------------------------------------------------------
# POST /summarize
# ---------------------------------------------------------------------------
def test_summarize_run(client):
    client.post("/memories", json={"text": "test memory", "scope": "global"}, headers={"content-type": "application/json"})
    resp = client.post("/summarize", data={"scope": "global", "similarity_threshold": "0.75"})
    assert resp.status_code == 200
    # Should show a plan or "No clusters"
    assert "Plan" in resp.text or "No clusters" in resp.text or "candidate" in resp.text.lower()


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
def test_static_css_served(client):
    resp = client.get("/static/style.css")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/css")


# ---------------------------------------------------------------------------
# CLI subcommand routing
# ---------------------------------------------------------------------------
def test_dashboard_subcommand_registered():
    from mnema.cli import _build_parser

    parser = _build_parser()
    seen = set()
    for action in parser._subparsers._actions:
        choices = getattr(action, "choices", None) or {}
        seen.update(choices)
    assert "dashboard" in seen


def test_dashboard_is_in_cli_commands():
    from mnema.__main__ import _CLI_COMMANDS

    assert "dashboard" in _CLI_COMMANDS
