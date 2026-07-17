"""Tests for the diagnostics module (logging + error reporting)."""

from __future__ import annotations

import logging

from mnema.config import MnemaConfig
from mnema.diagnostics import (
    GITHUB_ISSUES_URL,
    configure_logging,
    format_diagnostics,
    format_error_report,
    install_excepthook,
    logger,
)


class TestConfigureLogging:
    def test_sets_level(self):
        configure_logging("DEBUG")
        assert logger.level == logging.DEBUG

    def test_invalid_level_defaults_to_warning(self):
        configure_logging("INVALID")
        assert logger.level == logging.WARNING

    def test_has_handler(self):
        configure_logging("INFO")
        assert len(logger.handlers) >= 1


class TestFormatDiagnostics:
    def test_includes_version_and_platform(self):
        diag = format_diagnostics()
        assert "mnema_version" in diag
        assert "python" in diag
        assert "platform" in diag

    def test_includes_config_when_provided(self):
        cfg = MnemaConfig(backend="sqlite_vec", embedding="local")
        diag = format_diagnostics(cfg)
        assert "sqlite_vec" in diag
        assert "all-MiniLM-L6-v2" in diag

    def test_wraps_in_details_tag(self):
        diag = format_diagnostics()
        assert "<details>" in diag
        assert "</details>" in diag


class TestFormatErrorReport:
    def test_includes_error_type_and_message(self):
        try:
            raise RuntimeError("kaboom")
        except RuntimeError as e:
            report = format_error_report(e)
        assert "RuntimeError" in report
        assert "kaboom" in report

    def test_includes_github_issue_link(self):
        try:
            raise ValueError("test")
        except ValueError as e:
            report = format_error_report(e)
        assert GITHUB_ISSUES_URL in report
        # The link should be pre-filled with the error title.
        assert "title=" in report

    def test_includes_context(self):
        try:
            raise ValueError("oops")
        except ValueError as e:
            report = format_error_report(e, context="during mnema search")
        assert "during mnema search" in report

    def test_includes_diagnostics_when_config_given(self):
        cfg = MnemaConfig(backend="qdrant", embedding="openai")
        try:
            raise ValueError("test")
        except ValueError as e:
            report = format_error_report(e, config=cfg)
        assert "qdrant" in report

    def test_includes_log_level_hint(self):
        try:
            raise ValueError("test")
        except ValueError as e:
            report = format_error_report(e)
        assert "MNEMA_LOG_LEVEL=DEBUG" in report


class TestInstallExcepthook:
    def test_installs_without_error(self):
        # Just verify it doesn't crash — we can't easily test the hook itself
        # without triggering a real crash.
        original = __import__("sys").excepthook
        install_excepthook()
        # The hook should have been replaced.
        assert __import__("sys").excepthook is not original
        # Restore so other tests aren't affected.
        __import__("sys").excepthook = original

    def test_mnema_errors_are_clean(self):
        """MnemaError should print cleanly without the bug-report noise."""
        import io
        import sys
        from contextlib import redirect_stderr

        from mnema.errors import MemoryNotFoundError

        original_hook = sys.excepthook
        install_excepthook()
        try:
            err = io.StringIO()
            with redirect_stderr(err):
                sys.excepthook(MemoryNotFoundError, MemoryNotFoundError("missing"), None)
            output = err.getvalue()
            assert "Error: Memory not found" in output
            assert "github.com" not in output  # no bug-report link for expected errors
        finally:
            sys.excepthook = original_hook
