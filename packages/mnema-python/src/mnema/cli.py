"""Mnema command-line interface.

Provides human-friendly subcommands for working with memories directly from a
terminal — no MCP client required. Reuses :class:`~mnema.service.MemoryService`
so the CLI behaves exactly like an MCP-connected client.

Design: every command handler is an ``async`` function that takes a
:class:`~mnema.service.MemoryService`. :func:`run_cli` owns the single event
loop, builds the service once, runs the selected handler, and cleans up.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import sys
from typing import Any

from mnema._version import __version__
from mnema.config import MnemaConfig, load_config
from mnema.errors import MemoryNotFoundError, MnemaError
from mnema.models import Importance
from mnema.service import MemoryService


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _print_err(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)


def _truncate(text: str, width: int = 80) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def _format_record(record: Any, *, long: bool = False) -> str:
    if long:
        lines = [
            f"id          {record.id}",
            f"text        {record.text}",
            f"scope       {record.scope}",
            f"tags        {', '.join(record.tags) or '—'}",
            f"importance  {int(record.importance)}",
            f"created     {record.created_at}",
            f"accessed    {record.last_accessed_at} (×{record.access_count})",
        ]
        if record.metadata:
            lines.append(f"metadata    {json.dumps(record.metadata)}")
        if record.score is not None:
            lines.append(f"score       {record.score:.3f}")
        return "\n  ".join(lines)
    score = f" [{record.score:.3f}]" if record.score is not None else ""
    return f"{record.id}  score={score}  {_truncate(record.text)}"


def _format_hit(hit: Any, index: int) -> str:
    m = hit.memory
    parts = [
        f"{index}. {m.id}",
        f"score={hit.score:.3f}",
        f"vec={hit.vector_score:.3f}",
    ]
    if getattr(hit, "keyword_score", 0.0):
        parts.append(f"kw={hit.keyword_score:.3f}")
    parts.append(f"decay={hit.decay_score:.3f}")
    header = "  ".join(parts)
    body = _truncate(m.text, 100)
    meta = f"scope={m.scope}  importance={int(m.importance)}"
    if m.tags:
        meta += f"  tags={','.join(m.tags)}"
    return f"{header}\n   {body}\n   {meta}"


def _parse_tags(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    return [t.strip() for t in raw.split(",") if t.strip()]


def _parse_importance(raw: str | int | None) -> int:
    if raw is None:
        return int(Importance.NORMAL)
    return int(raw)


# ---------------------------------------------------------------------------
# Command handlers — each is async, returns an exit code.
# ---------------------------------------------------------------------------
async def cmd_add(args: argparse.Namespace, svc: MemoryService) -> int:
    record = await svc.remember(
        args.text,
        scope=args.scope,
        tags=_parse_tags(args.tags) or [],
        importance=_parse_importance(args.importance),
        metadata=json.loads(args.metadata) if args.metadata else {},
    )
    if getattr(args, "json", False):
        print(record.model_dump_json(indent=2))
    else:
        print(f"✓ remembered\n  {_format_record(record, long=True)}")
    return 0


async def cmd_recall(args: argparse.Namespace, svc: MemoryService) -> int:
    res = await svc.recall(
        args.query, scope=args.scope, limit=args.limit, offset=args.offset
    )
    _emit_search_results(res, args)
    return 0


async def cmd_search(args: argparse.Namespace, svc: MemoryService) -> int:
    res = await svc.search(
        args.query,
        scope=args.scope,
        tags=_parse_tags(args.tags),
        limit=args.limit,
        offset=args.offset,
    )
    _emit_search_results(res, args)
    return 0


def _emit_search_results(res, args: argparse.Namespace) -> None:
    if args.json:
        print(res.model_dump_json(indent=2))
        return
    if not res.results:
        print("No matches.")
        return
    for i, hit in enumerate(res.results, 1):
        print(_format_hit(hit, i))
        print()


async def cmd_get(args: argparse.Namespace, svc: MemoryService) -> int:
    try:
        record = await svc.get(args.id)
    except MemoryNotFoundError as exc:
        _print_err(str(exc))
        return 1
    if args.json:
        print(record.model_dump_json(indent=2))
    else:
        print(_format_record(record, long=True))
    return 0


async def cmd_update(args: argparse.Namespace, svc: MemoryService) -> int:
    try:
        record = await svc.update(
            args.id,
            text=args.text,
            tags=_parse_tags(args.tags),
            importance=_parse_importance(args.importance) if args.importance else None,
            metadata=json.loads(args.metadata) if args.metadata else None,
        )
    except MemoryNotFoundError as exc:
        _print_err(str(exc))
        return 1
    print(f"✓ updated\n  {_format_record(record, long=True)}")
    return 0


async def cmd_forget(args: argparse.Namespace, svc: MemoryService) -> int:
    ok = await svc.forget(args.id)
    if ok:
        print(f"✓ forgot {args.id}")
        return 0
    _print_err(f"no such memory: {args.id}")
    return 1


async def cmd_forget_scope(args: argparse.Namespace, svc: MemoryService) -> int:
    n = await svc.forget_scope(args.scope)
    print(f"✓ forgot {n} memories in scope '{args.scope}'")
    return 0


async def cmd_list_scopes(args: argparse.Namespace, svc: MemoryService) -> int:
    scopes = await svc.list_scopes()
    if args.json:
        print(json.dumps({"scopes": scopes}, indent=2))
        return 0
    if not scopes:
        print("(no scopes yet)")
        return 0
    width = max(len(s) for s in scopes)
    for scope, count in sorted(scopes.items()):
        print(f"{scope:<{width}}  {count}")
    return 0


async def cmd_stats(args: argparse.Namespace, svc: MemoryService) -> int:
    stats = await svc.stats()
    if args.json:
        print(stats.model_dump_json(indent=2))
        return 0
    print(f"total memories : {stats.total_memories}")
    print(f"backend        : {stats.backend}")
    print(f"embedding      : {stats.embedding_provider} (dim={stats.embedding_dim})")
    if stats.scopes:
        print("scopes         :")
        for scope, count in sorted(stats.scopes.items()):
            print(f"  {scope:<30}  {count}")
    else:
        print("scopes         : (none)")
    return 0


async def cmd_decay(args: argparse.Namespace, svc: MemoryService) -> int:
    candidates = await svc.apply_decay(
        scope=args.scope,
        threshold=args.threshold,
        dry_run=not args.apply,
    )
    if args.json:
        payload = {
            "mode": "apply" if args.apply else "dry-run",
            "threshold": args.threshold,
            "candidate_count": len(candidates),
            "candidates": [c.model_dump(mode="json") for c in candidates],
        }
        print(json.dumps(payload, indent=2))
        return 0
    verb = "forgot" if args.apply else "would forget"
    print(f"{len(candidates)} memories {verb} (threshold={args.threshold})")
    for c in candidates:
        print(f"  {c.id}  score={c.score:.3f}  {_truncate(c.text)}")
    return 0


async def cmd_summarize(args: argparse.Namespace, svc: MemoryService) -> int:
    plan = await svc.summarize(scope=args.scope, similarity_threshold=args.threshold)
    if args.json:
        import dataclasses

        print(json.dumps(dataclasses.asdict(plan), indent=2, default=str))
        return 0
    from mnema.summarize import build_summary_prompt

    print(build_summary_prompt(plan))
    return 0


async def cmd_export(args: argparse.Namespace, svc: MemoryService) -> int:
    config = svc.config
    records = [r.model_dump(mode="json") async for r in svc.backend.iter_all()]
    payload = {
        "version": __version__,
        "backend": config.backend,
        "embedding": config.embedding,
        "embedding_model": config.embedding_model,
        "count": len(records),
        "memories": records,
    }
    out = json.dumps(payload, indent=2, default=str)
    if args.output and args.output != "-":
        with open(args.output, "w") as f:
            f.write(out)
        print(f"✓ exported {len(records)} memories → {args.output}")
    else:
        print(out)
    return 0


async def cmd_backup(args: argparse.Namespace, svc: MemoryService) -> int:
    """Create a portable backup (.tar.gz) of the memory store.

    The backup bundles:
      - memories.json  (the export payload)
      - manifest.json  (backend, embedding, version, timestamp)

    Restore with `mnema restore <file>`.
    """
    import io
    import tarfile
    import time

    config = svc.config
    records = [r.model_dump(mode="json") async for r in svc.backend.iter_all()]
    export_payload = {
        "version": __version__,
        "backend": config.backend,
        "embedding": config.embedding,
        "embedding_model": config.embedding_model,
        "count": len(records),
        "memories": records,
    }
    manifest = {
        "mnema_version": __version__,
        "backend": config.backend,
        "embedding": config.embedding,
        "embedding_model": config.embedding_model,
        "embedding_dim": svc.embedding_dim,
        "memory_count": len(records),
        "created_at": time.time(),
    }

    out_path = args.output
    if not out_path:
        ts = time.strftime("%Y%m%d-%H%M%S")
        out_path = f"mnema-backup-{ts}.tar.gz"
    elif not out_path.endswith((".tar.gz", ".tgz")):
        out_path = out_path + ".tar.gz"

    mem_json = json.dumps(export_payload, indent=2, default=str).encode()
    man_json = json.dumps(manifest, indent=2).encode()
    with tarfile.open(out_path, "w:gz") as tar:
        info = tarfile.TarInfo(name="memories.json")
        info.size = len(mem_json)
        tar.addfile(info, io.BytesIO(mem_json))
        info = tarfile.TarInfo(name="manifest.json")
        info.size = len(man_json)
        tar.addfile(info, io.BytesIO(man_json))

    print(f"✓ backed up {len(records)} memories → {out_path}")
    print(f"  backend={config.backend}  embedding={config.embedding}:{config.embedding_model}")
    print(f"  restore with: mnema restore {out_path}")
    return 0


async def cmd_restore(args: argparse.Namespace, svc: MemoryService) -> int:
    """Restore memories from a backup (.tar.gz) created by `mnema backup`."""
    import tarfile

    in_path = args.input
    try:
        tar = tarfile.open(in_path, "r:gz")  # noqa: SIM115
    except (OSError, tarfile.TarError) as exc:
        _print_err(f"could not open backup: {exc}")
        return 1

    try:
        # Read manifest first (informational).
        try:
            man_file = tar.extractfile("manifest.json")
            manifest = json.loads(man_file.read()) if man_file else {}
            if manifest:
                print(
                    f"Backup: mnema {manifest.get('mnema_version', '?')}, "
                    f"{manifest.get('memory_count', '?')} memories, "
                    f"backend={manifest.get('backend', '?')}, "
                    f"embedding={manifest.get('embedding', '?')}:{manifest.get('embedding_model', '?')}"
                )
                cur_backend = svc.config.backend
                bk_backend = manifest.get("backend")
                if bk_backend and bk_backend != cur_backend:
                    _print_err(
                        f"backup was made with backend '{bk_backend}' but the "
                        f"current backend is '{cur_backend}'. Memories will still "
                        f"restore, but vector geometry may differ if the embedding "
                        f"model changed — run `mnema re-embed` after."
                    )
        except KeyError:
            manifest = {}

        # Read memories.json.
        try:
            mem_file = tar.extractfile("memories.json")
            if mem_file is None:
                _print_err("backup is missing memories.json")
                return 1
            data = json.loads(mem_file.read())
        except KeyError:
            _print_err("backup is missing memories.json")
            return 1
    finally:
        tar.close()

    memories = data.get("memories", [])
    n = 0
    for m in memories:
        await svc.remember(
            m["text"],
            scope=m.get("scope", svc.config.default_scope),
            tags=m.get("tags", []),
            importance=m.get("importance", Importance.NORMAL),
            metadata=m.get("metadata", {}),
        )
        n += 1
    print(f"✓ restored {n} memories from {in_path}")
    return 0


async def cmd_import(args: argparse.Namespace, svc: MemoryService) -> int:
    if args.input == "-":
        text = sys.stdin.read()
    else:
        with open(args.input) as f:
            text = f.read()
    data = json.loads(text)
    memories = data.get("memories", [])
    for m in memories:
        await svc.remember(
            m["text"],
            scope=m.get("scope", svc.config.default_scope),
            tags=m.get("tags", []),
            importance=m.get("importance", Importance.NORMAL),
            metadata=m.get("metadata", {}),
        )
    print(f"✓ imported {len(memories)} memories")
    return 0


async def cmd_reembed(args: argparse.Namespace, svc: MemoryService) -> int:
    """Re-embed all memories with the currently configured embedding provider.

    Use after switching ``MNEMA_EMBEDDING`` / ``MNEMA_EMBEDDING_MODEL`` so
    existing vectors match the new model.
    """
    total_before = await svc.backend.count()
    if total_before == 0:
        print("No memories to re-embed.")
        return 0

    provider = getattr(svc.embedding_provider, "display_name", svc.embedding_provider.name)
    dim = svc.embedding_dim
    print(
        f"Re-embedding {total_before} memories with {provider} (dim={dim})…"
    )

    def _progress(done: int, total: int) -> None:
        pct = (done * 100 // total) if total else 0
        print(f"  {done}/{total} ({pct}%)", flush=True)

    n = await svc.reembed(
        scope=args.scope,
        batch_size=args.batch_size,
        on_progress=_progress,
    )
    print(f"✓ re-embedded {n} memories")
    return 0


async def cmd_eval(args: argparse.Namespace, svc: MemoryService) -> int:
    """Run the recall evaluation harness.

    Seeds the store with a curated dataset (unless --no-seed), asks
    natural-language queries, and reports recall@k + MRR.
    """
    from mnema.eval_harness import run_eval

    report = await run_eval(svc, k=args.k, seed=not args.no_seed)
    if args.json:
        import json as _json

        payload = {
            "summary": report.summary(),
            "recall_at_k": report.recall_at_k,
            "mrr": report.mrr,
            "avg_score": report.avg_score,
            "total_queries": report.total_queries,
            "memory_count": report.memory_count,
            "elapsed_seconds": report.elapsed_seconds,
            "k": report.k,
            "hits": [
                {
                    "query": h.query,
                    "expected": h.expected,
                    "found": h.found,
                    "rank": h.rank,
                    "score": h.score,
                }
                for h in report.hits
            ],
        }
        print(_json.dumps(payload, indent=2))
    else:
        print(report.detail())
    # Exit 0 even on misses — eval is informational, not a CI gate.
    return 0


def cmd_serve(args: argparse.Namespace, config: MnemaConfig) -> int:
    """Run the REST API server (requires the 'api' extra).

    Unlike the other command handlers this one is **synchronous**: it hands
    control to uvicorn, which owns the event loop for the lifetime of the
    server. The FastAPI app builds (and, on shutdown, tears down) its own
    :class:`MemoryService` from ``config``.
    """
    try:
        import uvicorn

        from mnema.api.app import create_app
    except ImportError:
        _print_err(
            "The REST API server requires the 'api' extra (fastapi + uvicorn). "
            "Install it with:\n    uv pip install 'mnema-mcp[api]'"
        )
        return 2

    host = args.host or config.http_host
    port = args.port or config.http_port
    app = create_app(config)
    print(f"Serving Mnema REST API on http://{host}:{port}  (Ctrl-C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


def cmd_dashboard(args: argparse.Namespace, config: MnemaConfig) -> int:
    """Run the Mnema Dashboard web UI (requires the 'api' extra).

    Like :func:`cmd_serve`, this is synchronous — uvicorn owns the loop.
    """
    try:
        import uvicorn

        from mnema.dashboard import create_dashboard_app
    except ImportError:
        _print_err(
            "The Dashboard requires the 'api' extra (fastapi + uvicorn + jinja2). "
            "Install it with:\n    uv pip install 'mnema-mcp[api]'"
        )
        return 2

    host = args.host or config.http_host
    port = args.port or 8080
    app = create_dashboard_app(config)
    print(f"🧠 Mnema Dashboard on http://{host}:{port}  (Ctrl-C to stop)")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


async def cmd_dream(args: argparse.Namespace, svc: MemoryService) -> int:
    """Run a single dream cycle (decay-forget + summarize-plan).

    This is the manual equivalent of what the Auto Dream background scheduler
    does automatically when ``MNEMA_DREAM_ENABLED=true``.
    """
    from mnema.dream import dream_once

    report = await dream_once(svc, svc.config)
    if args.json:
        import json as _json

        payload = {
            "summary": report.summary(),
            "memories_forgotten": report.memories_forgotten,
            "memory_count_before": report.memory_count_before,
            "memory_count_after": report.memory_count_after,
            "scopes_summarized": report.scopes_summarized,
            "elapsed_seconds": report.elapsed_seconds,
        }
        print(_json.dumps(payload, indent=2))
    else:
        print(f"✓ {report.summary()}")
        if report.memories_forgotten:
            print(f"  forgot {report.memories_forgotten} low-value memories")
        if report.scopes_summarized:
            print(f"  summarized scopes: {', '.join(report.scopes_summarized)}")
        if not report.memories_forgotten and not report.scopes_summarized:
            print("  nothing to dream about — store is already tidy.")
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mnema",
        description=(
            "Mnema — long-term memory for AI via MCP × Vector DB.\n\n"
            "Use a subcommand to work with memories from the terminal."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"mnema {__version__}")
    sub = p.add_subparsers(dest="command", metavar="<command>")

    # add ----------------------------------------------------------------
    sp = sub.add_parser("add", help="Store a new memory", aliases=["remember"])
    sp.add_argument("text", help="The memory text (natural language)")
    sp.add_argument("--scope", default=None, help="Namespace (e.g. user:alice)")
    sp.add_argument("--tags", default=None, help="Comma-separated tags")
    sp.add_argument(
        "--importance", type=int, default=int(Importance.NORMAL),
        help="1=low … 10=critical (default 5)",
    )
    sp.add_argument("--metadata", default=None, help="JSON object string")
    sp.add_argument("--json", action="store_true", help="Output as JSON")
    sp.set_defaults(func=cmd_add)

    # recall -------------------------------------------------------------
    sp = sub.add_parser("recall", help="Semantic vector search (meaning)")
    sp.add_argument("query", help="What to recall")
    sp.add_argument("--scope", default=None)
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--offset", type=int, default=0)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_recall)

    # search -------------------------------------------------------------
    sp = sub.add_parser("search", help="Hybrid search (vector + tags + decay)")
    sp.add_argument("query", help="What to search for")
    sp.add_argument("--scope", default=None)
    sp.add_argument("--tags", "--tag", dest="tags", default=None, help="Comma-separated tags")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--offset", type=int, default=0)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_search)

    # get ----------------------------------------------------------------
    sp = sub.add_parser("get", help="Fetch a single memory by id")
    sp.add_argument("id", help="Memory id")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_get)

    # update -------------------------------------------------------------
    sp = sub.add_parser("update", help="Patch a memory (re-embeds on text change)")
    sp.add_argument("id", help="Memory id")
    sp.add_argument("--text", default=None)
    sp.add_argument("--tags", default=None, help="Comma-separated tags")
    sp.add_argument("--importance", type=int, default=None)
    sp.add_argument("--metadata", default=None, help="JSON object string")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_update)

    # forget -------------------------------------------------------------
    sp = sub.add_parser("forget", help="Delete one memory by id", aliases=["delete"])
    sp.add_argument("id", help="Memory id")
    sp.set_defaults(func=cmd_forget)

    # forget-scope -------------------------------------------------------
    sp = sub.add_parser(
        "forget-scope", help="Delete every memory in a scope", aliases=["delete-scope"]
    )
    sp.add_argument("scope", help="Scope name")
    sp.set_defaults(func=cmd_forget_scope)

    # list-scopes --------------------------------------------------------
    sp = sub.add_parser("list-scopes", help="List all scopes + counts", aliases=["scopes"])
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_list_scopes)

    # stats --------------------------------------------------------------
    sp = sub.add_parser("stats", help="Show aggregate stats")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_stats)

    # decay --------------------------------------------------------------
    sp = sub.add_parser("decay", help="Find / forget low-value memories")
    sp.add_argument("--scope", default=None, help="Restrict to a scope")
    sp.add_argument("--threshold", type=float, default=0.05, help="Decay cutoff")
    sp.add_argument("--apply", action="store_true", help="Actually delete (default: dry run)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_decay)

    # summarize ----------------------------------------------------------
    sp = sub.add_parser("summarize", help="Plan how to condense a scope")
    sp.add_argument("scope", help="Scope to summarize")
    sp.add_argument("--threshold", type=float, default=0.75, help="Similarity cutoff")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_summarize)

    # export -------------------------------------------------------------
    sp = sub.add_parser("export", help="Export all memories to JSON")
    sp.add_argument("-o", "--output", default="-", help="Output file (default: stdout)")
    sp.set_defaults(func=cmd_export)

    # import -------------------------------------------------------------
    sp = sub.add_parser("import", help="Import memories from JSON")
    sp.add_argument("-i", "--input", default="-", help="Input file (default: stdin)")
    sp.set_defaults(func=cmd_import)

    # backup --------------------------------------------------------------
    sp = sub.add_parser(
        "backup",
        help="Create a portable .tar.gz backup of all memories (+ manifest)",
    )
    sp.add_argument(
        "-o", "--output", default=None,
        help="Output file (default: mnema-backup-YYYYMMDD-HHMMSS.tar.gz)",
    )
    sp.set_defaults(func=cmd_backup)

    # restore -------------------------------------------------------------
    sp = sub.add_parser(
        "restore",
        help="Restore memories from a backup created by `mnema backup`",
    )
    sp.add_argument("input", help="Backup file (.tar.gz)")
    sp.set_defaults(func=cmd_restore)

    # eval ----------------------------------------------------------------
    sp = sub.add_parser(
        "eval",
        help="Run the recall evaluation harness (recall@k + MRR)",
    )
    sp.add_argument("-k", type=int, default=5, help="cutoff for recall@k (default 5)")
    sp.add_argument(
        "--no-seed",
        action="store_true",
        help="Don't seed the dataset; eval the store as-is",
    )
    sp.add_argument("--json", action="store_true", help="Output as JSON")
    sp.set_defaults(func=cmd_eval)

    # dream ----------------------------------------------------------------
    sp = sub.add_parser(
        "dream",
        help="Run a single dream cycle: forget decayed memories + plan "
        "summarization (the manual version of Auto Dream)",
    )
    sp.add_argument("--json", action="store_true", help="Output as JSON")
    sp.set_defaults(func=cmd_dream)

    # serve ---------------------------------------------------------------
    sp = sub.add_parser(
        "serve",
        help="Run the REST API server (requires the 'api' extra)",
    )
    sp.add_argument(
        "--host", default=None,
        help="Bind host (default: MNEMA_HTTP_HOST or 127.0.0.1)",
    )
    sp.add_argument(
        "--port", type=int, default=None,
        help="Bind port (default: MNEMA_HTTP_PORT or 8000)",
    )
    sp.set_defaults(func=cmd_serve)

    # dashboard -----------------------------------------------------------
    sp = sub.add_parser(
        "dashboard",
        help="Run the Mnema Dashboard web UI (requires the 'api' extra)",
    )
    sp.add_argument(
        "--host", default=None,
        help="Bind host (default: MNEMA_HTTP_HOST or 127.0.0.1)",
    )
    sp.add_argument(
        "--port", type=int, default=None,
        help="Bind port (default: 8080)",
    )
    sp.set_defaults(func=cmd_dashboard)

    # re-embed ------------------------------------------------------------
    sp = sub.add_parser(
        "re-embed",
        help="Re-embed all memories with the current embedding model (after "
        "switching MNEMA_EMBEDDING / MNEMA_EMBEDDING_MODEL)",
        aliases=["reembed"],
    )
    sp.add_argument("--scope", default=None, help="Restrict to a scope")
    sp.add_argument(
        "--batch-size", type=int, default=50, help="Embed batch size (default 50)"
    )
    sp.set_defaults(func=cmd_reembed)

    return p


# ---------------------------------------------------------------------------
# Entry point — owns the single event loop.
# ---------------------------------------------------------------------------
def run_cli(argv: list[str] | None = None) -> int:
    """Dispatch a CLI subcommand. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "func", None):
        parser.print_help()
        return 0

    try:
        config = load_config()
    except MnemaError as exc:
        _print_err(str(exc))
        return 2

    # Set up logging + install a friendly crash handler so unexpected errors
    # produce a pre-filled GitHub issue link instead of a raw traceback.
    from mnema.diagnostics import configure_logging, install_excepthook

    configure_logging(config.log_level)
    install_excepthook(config)

    func = args.func
    # `serve` (and the `doctor` shim) are synchronous handlers that take the
    # config directly; every other handler is async and gets a built service.
    if asyncio.iscoroutinefunction(func):
        return _run_async_handler(func, config, args)
    return func(args, config)  # pragma: no cover - blocking server / doctor shim


def _run_async_handler(
    func: Any, config: MnemaConfig, args: argparse.Namespace
) -> int:
    """Build a service, run the async handler on a fresh loop, clean up."""

    async def _main() -> int:
        svc = MemoryService(config)
        try:
            return await func(args, svc)
        finally:
            with contextlib.suppress(Exception):
                await svc.aclose()

    return asyncio.run(_main())


__all__ = ["run_cli"]
