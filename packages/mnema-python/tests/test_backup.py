"""Tests for `mnema backup` / `mnema restore` (issue #12).

Verifies the backup → restore roundtrip preserves memories and that the
backup archive contains the expected manifest + memories.json. Uses the
in-memory fakes so no embedding model is loaded.
"""

from __future__ import annotations

import argparse
import io
import json
import tarfile
from contextlib import redirect_stderr, redirect_stdout

import pytest

from mnema.cli import cmd_backup, cmd_restore
from mnema.models import Importance


def _ns(**kw) -> argparse.Namespace:
    base = {"json": False, "scope": None, "tags": None, "importance": int(Importance.NORMAL)}
    base.update(kw)
    return argparse.Namespace(**base)


pytestmark = pytest.mark.asyncio


class TestBackup:
    async def test_backup_creates_tarball_with_manifest(self, service, tmp_path):
        await service.remember("Alice likes tea", scope="user:alice", tags=["pref"])
        await service.remember("Bob codes Rust", scope="user:bob")

        out = tmp_path / "backup.tar.gz"
        args = _ns(output=str(out))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_backup(args, service)
        assert code == 0
        assert out.exists()

        # Verify the tarball contains memories.json + manifest.json.
        with tarfile.open(out, "r:gz") as tar:
            names = tar.getnames()
            assert "memories.json" in names
            assert "manifest.json" in names

            man = json.loads(tar.extractfile("manifest.json").read())
            assert man["memory_count"] == 2
            assert man["backend"] == service.config.backend

            mems = json.loads(tar.extractfile("memories.json").read())
            assert mems["count"] == 2

    async def test_backup_default_filename(self, service, tmp_path, monkeypatch):
        """When -o is omitted, a timestamped filename is created in cwd."""
        await service.remember("one")
        monkeypatch.chdir(tmp_path)
        args = _ns(output=None)
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_backup(args, service)
        assert code == 0
        # A mnema-backup-*.tar.gz should exist in tmp_path.
        files = list(tmp_path.glob("mnema-backup-*.tar.gz"))
        assert len(files) == 1

    async def test_backup_empty_store(self, service, tmp_path):
        """Backing up an empty store should work (0 memories)."""
        out = tmp_path / "empty.tar.gz"
        args = _ns(output=str(out))
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_backup(args, service)
        assert code == 0
        assert out.exists()
        with tarfile.open(out, "r:gz") as tar:
            man = json.loads(tar.extractfile("manifest.json").read())
            assert man["memory_count"] == 0


class TestRestore:
    async def test_restore_roundtrip(self, service, tmp_path):
        """Backup from `service`, restore into a fresh service, verify."""
        await service.remember("Alice likes tea", scope="user:alice", tags=["pref"])
        await service.remember("Bob codes Rust", scope="user:bob", importance=8)

        # Backup.
        out = tmp_path / "bk.tar.gz"
        args = _ns(output=str(out))
        with redirect_stdout(io.StringIO()):
            await cmd_backup(args, service)

        # Restore into a fresh service (same config, fresh backend).
        from mnema.service import MemoryService
        from tests.fakes import InMemoryBackend

        fresh_backend = InMemoryBackend(dim=64)
        fresh_svc = MemoryService(service.config, backend=fresh_backend, embedding=service.embedding_provider)
        try:
            args = _ns(input=str(out))
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = await cmd_restore(args, fresh_svc)
            assert code == 0
            assert "restored 2 memories" in buf.getvalue()

            # Verify both memories are present.
            scopes = await fresh_svc.list_scopes()
            assert scopes == {"user:alice": 1, "user:bob": 1}
        finally:
            await fresh_svc.aclose()

    async def test_restore_missing_file(self, service):
        args = _ns(input="/nonexistent/path.tar.gz")
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = await cmd_restore(args, service)
        assert code == 1

    async def test_restore_warns_on_backend_mismatch(self, service, tmp_path):
        """Restore should warn (not crash) if backup backend != current backend."""
        await service.remember("one")
        out = tmp_path / "bk.tar.gz"
        args = _ns(output=str(out))
        with redirect_stdout(io.StringIO()):
            await cmd_backup(args, service)

        # Tamper with the manifest to simulate a different backend.
        import time

        with tarfile.open(out, "r:gz") as tar:
            mems = json.loads(tar.extractfile("memories.json").read())
        man = {
            "mnema_version": "0.2.0",
            "backend": "chroma",  # different from the fake's "memory"
            "embedding": "local",
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dim": 64,
            "memory_count": 1,
            "created_at": time.time(),
        }
        man_json = json.dumps(man, indent=2).encode()
        mem_json = json.dumps(mems, indent=2, default=str).encode()
        with tarfile.open(out, "w:gz") as tar:
            for name, data in [("manifest.json", man_json), ("memories.json", mem_json)]:
                info = tarfile.TarInfo(name=name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))

        # Restore into a fresh service — should warn but still succeed.
        from mnema.service import MemoryService
        from tests.fakes import InMemoryBackend

        fresh_svc = MemoryService(
            service.config,
            backend=InMemoryBackend(dim=64),
            embedding=service.embedding_provider,
        )
        try:
            args = _ns(input=str(out))
            buf = io.StringIO()
            err_buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(err_buf):
                code = await cmd_restore(args, fresh_svc)
            assert code == 0
            combined = buf.getvalue() + err_buf.getvalue()
            assert "backend 'chroma'" in combined or "current backend" in combined
            assert "restored 1 memories" in combined
        finally:
            await fresh_svc.aclose()
