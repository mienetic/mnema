"""Command-line entry point for ``mnema`` / ``mnema-server``.

Supports both transports (``stdio`` by default, ``http`` via env/flag), and
exposes a few simple diagnostics (``--version``, ``--doctor``).
"""

from __future__ import annotations

import argparse
import sys

from mnema._version import __version__


def _build_parser() -> argparse.ArgumentParser:
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
    p.add_argument(
        "--host",
        default=None,
        help="HTTP bind host (overrides MNEMA_HTTP_HOST).",
    )
    p.add_argument(
        "--port",
        type=int,
        default=None,
        help="HTTP bind port (overrides MNEMA_HTTP_PORT).",
    )
    p.add_argument(
        "--doctor",
        action="store_true",
        help="Check configuration and backend/embedding availability, then exit.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    """Entry point used by the ``mnema`` console script."""
    args = _build_parser().parse_args(argv)

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
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.doctor:
        return _doctor(config)

    from mnema.server import run

    run(config)
    return 0


def _doctor(config) -> int:
    """Print resolved config + probe the backend/embedding availability."""
    print(f"mnema {__version__}")
    print(f"backend        = {config.backend}  ({config.backend_path})")
    print(f"embedding      = {config.embedding}  ({config.embedding_model})")
    print(f"transport      = {config.transport}")
    print(f"default_scope  = {config.default_scope}")
    print(f"decay_half_life= {config.decay_half_life_days} days")
    print()

    # Probe backend.
    try:
        from mnema.backends import make_backend

        backend = make_backend(config)
        print(f"✓ backend '{backend.name}' loaded")
    except Exception as exc:
        print(f"✗ backend failed: {exc}")
        return 3

    # Probe embedding.
    try:
        from mnema.embeddings import make_embedding

        emb = make_embedding(config)
        print(f"✓ embedding '{emb.name}' loaded (dim={emb.dim})")
    except Exception as exc:
        print(f"✗ embedding failed: {exc}")
        return 4

    print("\nAll checks passed — Mnema is ready to serve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
