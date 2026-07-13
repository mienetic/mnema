"""Tests for the ``mnema`` CLI subcommands.

Two layers:

1. **Parser + routing** — verify subcommands parse correctly and route to
   the right handler (fast, no I/O).
2. **Handlers** — call the async command handlers directly with the in-memory
   fakes (fast, no embedding model load). End-to-end subprocess coverage of
   the real backends lives in ``test_backends.py``.
"""

from __future__ import annotations

import argparse
import io
import json
from contextlib import redirect_stdout

import pytest

from mnema.cli import (
    _build_parser,
    cmd_add,
    cmd_forget,
    cmd_get,
    cmd_list_scopes,
    cmd_recall,
    cmd_search,
    cmd_stats,
)
from mnema.models import Importance


def _ns(**kw) -> argparse.Namespace:
    """Build a Namespace with sensible defaults for handler args."""
    base = {
        "json": False,
        "scope": None,
        "tags": None,
        "limit": 10,
        "offset": 0,
        "importance": int(Importance.NORMAL),
        "metadata": None,
    }
    base.update(kw)
    return argparse.Namespace(**base)


class TestParserRouting:
    """Verify the parser registers every subcommand and routes to handlers."""

    def test_no_subcommand_prints_help(self):
        parser = _build_parser()
        buf = io.StringIO()
        with redirect_stdout(buf):
            args = parser.parse_args([])
        assert args.command is None

    @pytest.mark.parametrize(
        "cmd",
        [
            "add",
            "recall",
            "search",
            "get",
            "update",
            "forget",
            "forget-scope",
            "list-scopes",
            "stats",
            "decay",
            "summarize",
            "export",
            "import",
        ],
    )
    def test_subcommand_registered(self, cmd):
        parser = _build_parser()
        # `add` needs a positional text; others need their own positionals.
        extras = {
            "add": ["text"],
            "recall": ["q"],
            "search": ["q"],
            "get": ["id"],
            "update": ["id"],
            "forget": ["id"],
            "forget-scope": ["scope"],
            "summarize": ["scope"],
        }.get(cmd, [])
        args = parser.parse_args([cmd, *extras])
        assert args.command == cmd
        assert hasattr(args, "func"), f"{cmd} has no handler"

    def test_aliases_work(self):
        parser = _build_parser()
        # Aliases map to the same handler; argparse keeps the alias used as command.
        assert parser.parse_args(["remember", "x"]).func == cmd_add
        assert parser.parse_args(["delete", "x"]).func == cmd_forget
        assert parser.parse_args(["scopes"]).func == cmd_list_scopes


pytestmark = pytest.mark.asyncio


class TestHandlersWithFakes:
    """Call command handlers directly with the in-memory fake service."""

    async def test_add_then_get(self, service):
        # add
        args = _ns(text="Alice likes tea", tags="pref,tea", scope="user:alice")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_add(args, service)
        assert code == 0
        out = buf.getvalue()
        assert "remembered" in out
        # The id line is "  id          <uuid>" (indented in the long format).
        mem_id = [
            line.split()[-1]
            for line in out.splitlines()
            if line.strip().startswith("id")
        ][0]

        # get
        args = _ns(id=mem_id)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_get(args, service)
        assert code == 0
        assert "Alice likes tea" in buf.getvalue()

    async def test_add_json_output(self, service):
        args = _ns(text="hello world", tags="greeting", json=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            await cmd_add(args, service)
        data = json.loads(buf.getvalue())
        assert data["text"] == "hello world"

    async def test_recall_returns_results(self, service):
        await service.remember("Alice likes Earl Grey tea", scope="user:alice")
        await service.remember("Bob codes in Rust", scope="user:bob")

        args = _ns(query="tea", scope="user:alice")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_recall(args, service)
        assert code == 0
        assert "Alice" in buf.getvalue()

    async def test_search_json(self, service):
        await service.remember("hello world", tags=["greeting"])
        args = _ns(query="hello", tags="greeting", json=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_search(args, service)
        assert code == 0
        data = json.loads(buf.getvalue())
        assert data["count"] >= 1

    async def test_forget(self, service):
        rec = await service.remember("bye")
        args = _ns(id=rec.id)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_forget(args, service)
        assert code == 0
        assert "forgot" in buf.getvalue()

    async def test_list_scopes(self, service):
        await service.remember("a", scope="user:x")
        await service.remember("b", scope="user:y")
        args = _ns()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_list_scopes(args, service)
        assert code == 0
        out = buf.getvalue()
        assert "user:x" in out
        assert "user:y" in out

    async def test_stats(self, service):
        await service.remember("one")
        args = _ns()
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_stats(args, service)
        assert code == 0
        assert "total memories" in buf.getvalue()

    async def test_stats_json(self, service):
        await service.remember("one")
        args = _ns(json=True)
        buf = io.StringIO()
        with redirect_stdout(buf):
            await cmd_stats(args, service)
        data = json.loads(buf.getvalue())
        assert data["total_memories"] == 1
