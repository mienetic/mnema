"""Command-line entry point for ``mnema`` / ``mnema-server``.

The binary serves two roles:

1. **MCP server** (default, no subcommand) — for AI clients (Claude Desktop,
   Cursor, Zed, …). Runs over stdio by default or HTTP with ``--transport``.
2. **CLI tool** (with a subcommand) — for humans in a terminal. Lets you
   add, search, and manage memories without an MCP client.

Examples::

    mnema                       # run the MCP server (stdio)
    mnema --transport http      # run the MCP server (HTTP)
    mnema --doctor              # probe backend + embedding, then exit

    mnema add "Alice likes tea" --tags pref,tea
    mnema recall "what does alice drink?"
    mnema search "preferences" --tag pref --scope user:alice
    mnema list-scopes
    mnema stats
    mnema get <id>
    mnema forget <id>
    mnema decay --threshold 0.1 --apply
"""

from __future__ import annotations

import argparse
import json
import sys

from mnema._version import __version__

# Subcommands that take over and run as a CLI tool rather than an MCP server.
# Keep this in sync with the subparsers registered below.
_CLI_COMMANDS = {
    "add",
    "recall",
    "search",
    "get",
    "update",
    "forget",
    "forget-scope",
    "list-scopes",
    "scopes",
    "stats",
    "decay",
    "summarize",
    "doctor",
    "export",
    "import",
    "backup",
    "restore",
    "eval",
    "dream",
    "re-embed",
    "reembed",
}


def _is_cli_invocation(argv: list[str]) -> bool:
    """True when the first positional (non-flag) arg is a known CLI subcommand.

    We skip leading flags (e.g. ``--version``) and inspect the first
    positional argument, which determines whether the user wants the CLI
    (``mnema add …``) or the MCP server (``mnema [--transport http]``).
    """
    for arg in argv:
        if arg.startswith("-"):
            continue
        return arg in _CLI_COMMANDS
    return False


def main(argv: list[str] | None = None) -> int:
    """Entry point used by the ``mnema`` console script."""
    if argv is None:
        argv = sys.argv[1:]

    # Route to the CLI when a known subcommand is given. Otherwise run the
    # MCP server (preserving the existing `mnema` / `mnema --transport http`
    # / `mnema --doctor` ergonomics).
    if _is_cli_invocation(argv):
        from mnema.cli import run_cli

        return run_cli(argv)

    return _run_server(argv)


def _run_server(argv: list[str]) -> int:
    """Parse server flags and start the MCP server."""
    p = argparse.ArgumentParser(
        prog="mnema",
        description=(
            "Mnema — long-term memory for AI via MCP × Vector DB. "
            "Run as an MCP server (stdio by default; HTTP with --transport http)."
        ),
    )
    p.add_argument("--version", action="version", version=f"mnema {__version__}")
    p.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=None,
        help="MCP transport (overrides MNEMA_TRANSPORT). Default: stdio.",
    )
    p.add_argument("--host", default=None, help="HTTP bind host.")
    p.add_argument("--port", type=int, default=None, help="HTTP bind port.")
    p.add_argument(
        "--doctor",
        action="store_true",
        help="Check configuration and backend/embedding availability, then exit.",
    )
    p.add_argument(
        "--fix",
        action="store_true",
        help="With --doctor: attempt to fix problems automatically (e.g. create the "
        "data directory, point at the installer for a missing backend/embedding).",
    )
    args = p.parse_args(argv)

    from mnema.config import load_config

    overrides: dict[str, object] = {}
    if args.transport:
        overrides["transport"] = args.transport
    if args.host:
        overrides["http_host"] = args.host
    if args.port:
        overrides["http_port"] = args.port

    try:
        config = load_config(**overrides)
    except Exception as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.doctor:
        return _doctor(config, fix=args.fix)

    from mnema.server import run

    run(config)
    return 0


def _doctor(config, *, fix: bool = False) -> int:
    """Print resolved config + probe the backend/embedding availability.

    When ``fix=True``, attempt to remediate the most common failures in
    place (create a missing data dir, print the exact install command for a
    missing optional dependency, etc.). Always exits non-zero if any check
    failed — fixes or no fixes.
    """
    import os

    print(f"mnema {__version__}")
    print(f"backend        = {config.backend}  ({config.backend_path})")
    print(f"embedding      = {config.embedding}  ({config.embedding_model})")
    print(f"transport      = {config.transport}")
    print(f"default_scope  = {config.default_scope}")
    print(f"decay_half_life= {config.decay_half_life_days} days")
    if fix:
        print("mode           = doctor --fix (will attempt remediation)")
    print()

    rc = 0

    # --- Pre-check: is the data directory usable? ------------------------
    # Only for local-path backends (not remote URLs).
    path = config.backend_path
    if path not in (":memory:",) and not path.startswith(("http://", "https://")):
        parent = os.path.dirname(path) or "."
        if not os.path.isdir(parent):
            print(f"✗ data path parent does not exist: {parent}")
            if fix:
                try:
                    os.makedirs(parent, exist_ok=True)
                    print(f"  ↳ created {parent}")
                except OSError as exc:
                    print(f"  ↳ could not create: {exc}")
                    rc = 3
            else:
                print(f"  hint: run `mnema --doctor --fix` to create it, or "
                      f"`mkdir -p {parent}`")
                rc = 3
        elif not os.access(parent, os.W_OK):
            print(f"✗ data path parent is not writable: {parent}")
            print(f"  hint: check permissions on {parent}")
            rc = 3

    # --- Backend ----------------------------------------------------------
    try:
        from mnema.backends import make_backend

        backend = make_backend(config)
        print(f"✓ backend '{backend.name}' loaded")
    except Exception as exc:
        rc = 3
        print(f"✗ backend failed: {exc}")
        # The error message from BackendNotAvailableError already points at
        # the installer; just remind the user when not fixing.
        if not fix:
            print("  hint: re-run `mnema --doctor --fix` for a suggested command.")

    # --- Embedding --------------------------------------------------------
    try:
        from mnema.embeddings import make_embedding

        emb = make_embedding(config)
        print(f"✓ embedding '{emb.name}' loaded (dim={emb.dim})")
    except Exception as exc:
        rc = 4
        print(f"✗ embedding failed: {exc}")
        # Common cause: embedding='openai' without a key.
        if config.embedding == "openai" and not config.openai_api_key:
            print("  cause: MNEMA_OPENAI_API_KEY is not set.")
            print("  fix:   export MNEMA_OPENAI_API_KEY=sk-...  (or switch to "
                  "MNEMA_EMBEDDING=local / ollama)")
        elif not fix:
            print("  hint: re-run `mnema --doctor --fix` for a suggested command.")

    # --- Summary ----------------------------------------------------------
    if rc == 0:
        print("\nAll checks passed — Mnema is ready to serve.")
    else:
        print(f"\nDoctor finished with errors (exit {rc}).", file=sys.stderr)
        if not fix:
            print("Re-run with `--fix` to attempt automatic remediation.",
                  file=sys.stderr)
    return rc


# Silence unused import in some static analyzers; json is used in cli.py.
_ = json

if __name__ == "__main__":
    raise SystemExit(main())
