"""Structured logging + friendly error reporting for Mnema.

When something goes wrong, users get a clear message telling them:

1. What happened (the error)
2. What to try (a hint, when we can guess)
3. How to report it (a pre-filled issue link with diagnostics attached)

Set ``MNEMA_LOG_LEVEL=DEBUG`` to see verbose logs (backend queries, embed
latency, search scores, …).
"""

from __future__ import annotations

import logging
import platform
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mnema.config import MnemaConfig

GITHUB_ISSUES_URL = "https://github.com/mienetic/mnema/issues/new"
GITHUB_BUG_TEMPLATE = (
    GITHUB_ISSUES_URL
    + "?template=bug_report.md&title=Bug%3A%20"
)

# A logger that every module can import. Named "mnema" so users can
# configure it with ``logging.getLogger("mnema")``.
logger = logging.getLogger("mnema")


def configure_logging(level: str = "WARNING") -> None:
    """Set up the ``mnema`` logger.

    Args:
        level: One of ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``.
            Defaults to ``WARNING`` (quiet). Set ``MNEMA_LOG_LEVEL=DEBUG``
            for verbose output.
    """
    numeric_level = getattr(logging, level.upper(), logging.WARNING)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    # Replace any existing handlers so re-configuring (e.g. in tests) is safe.
    logger.handlers = [handler]
    logger.setLevel(numeric_level)
    logger.propagate = False  # avoid duplicate output via root logger


def _gather_diagnostics(config: MnemaConfig | None = None) -> dict[str, str]:
    """Collect environment info for bug reports."""
    from mnema._version import __version__

    info: dict[str, str] = {
        "mnema_version": __version__,
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.machine()}",
    }
    if config is not None:
        info["backend"] = config.backend
        info["embedding"] = config.embedding
        info["embedding_model"] = config.embedding_model
        info["transport"] = config.transport
    return info


def format_diagnostics(config: MnemaConfig | None = None) -> str:
    """Return a human-readable diagnostics block for pasting into an issue."""
    diag = _gather_diagnostics(config)
    lines = ["<details><summary>Environment</summary>", ""]
    for key, val in sorted(diag.items()):
        lines.append(f"- **{key}**: {val}")
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def format_error_report(
    error: BaseException,
    *,
    config: MnemaConfig | None = None,
    context: str = "",
) -> str:
    """Build a user-friendly error message with a pre-filled issue link.

    Args:
        error: The exception that occurred.
        config: Optional config (adds backend/embedding info to the report).
        context: Optional one-line context (e.g. "during mnema search").

    Returns:
        A multi-line string to print to stderr.
    """
    import traceback
    from urllib.parse import quote

    error_type = type(error).__name__
    error_msg = str(error)[:200]
    diag = _gather_diagnostics(config)

    # Build a compact title for the issue link.
    title_parts = [error_type]
    if context:
        title_parts.append(context)
    title = quote(" ".join(title_parts))

    # Build the body — the user copies this into the issue body field.
    body_lines = [
        "## Error",
        "",
        f"**Type**: `{error_type}`",
        f"**Message**: `{error_msg}`",
    ]
    if context:
        body_lines.append(f"**Context**: {context}")
    body_lines += ["", "## Environment", ""]
    for key, val in sorted(diag.items()):
        body_lines.append(f"- **{key}**: `{val}`")
    body_lines += ["", "## Traceback", "", "```"]
    body_lines.extend(traceback.format_exception(type(error), error, error.__traceback__))
    body_lines += ["```"]
    body = quote("\n".join(body_lines))

    issue_url = f"{GITHUB_ISSUES_URL}?title={title}&body={body}"

    # The message shown to the user on stderr.
    msg = [
        f"\n{'='*60}",
        f"  ✗ {error_type}: {error_msg}",
    ]
    if context:
        msg.append(f"    ({context})")
    msg += [
        f"{'='*60}",
        "",
        "  This looks like a bug. You can help fix it by opening an issue:",
        "",
        f"  {issue_url}",
        "",
        "  The link pre-fills the error details + environment info for you.",
        "  Just click it, review, and submit.",
        "",
        "  Or run again with MNEMA_LOG_LEVEL=DEBUG for verbose logs:",
        "    MNEMA_LOG_LEVEL=DEBUG mnema <command>",
        f"{'='*60}\n",
    ]
    return "\n".join(msg)


def install_excepthook(config: MnemaConfig | None = None) -> None:
    """Install a global exception hook that prints a friendly error report.

    When an unhandled exception crashes the CLI/server, instead of a raw
    traceback, the user sees a clear message with a pre-filled issue link.

    Args:
        config: Optional config — included in the diagnostic info.
    """
    original = sys.excepthook

    def _hook(exc_type, exc_value, exc_tb):
        # Don't intercept KeyboardInterrupt — let it exit quietly.
        if issubclass(exc_type, KeyboardInterrupt):
            original(exc_type, exc_value, exc_tb)
            return
        # MnemaError subclasses are "expected" errors (bad config, missing
        # memory, etc.) — print them cleanly without the bug-report noise.
        from mnema.errors import MnemaError

        if isinstance(exc_value, MnemaError):
            print(f"Error: {exc_value}", file=sys.stderr)
            return
        # Everything else is unexpected → show the friendly report.
        print(format_error_report(exc_value, config=config), file=sys.stderr)

    sys.excepthook = _hook


__all__ = [
    "configure_logging",
    "format_diagnostics",
    "format_error_report",
    "install_excepthook",
    "logger",
]
