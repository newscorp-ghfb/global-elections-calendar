"""Session-wide pytest behaviour: skips fail under CI, and the counts reach the job summary (P126)."""

import os
from pathlib import Path

import pytest

pytest_plugins = ("pytester",)


def _count(session: pytest.Session, kind: str) -> int:
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    return len(reporter.stats.get(kind, [])) if reporter is not None else 0


def _skipped_under_ci(session: pytest.Session) -> int:
    return _count(session, "skipped") if os.environ.get("CI") == "true" else 0


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if _skipped_under_ci(session):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        failed = _count(session, "failed") + _count(session, "error")
        line = (
            f"pytest: {session.testscollected} collected, {_count(session, 'passed')} passed, "
            f"{failed} failed, {_count(session, 'skipped')} skipped, "
            f"{_count(session, 'xfailed')} xfailed\n"
        )
        with Path(path).open("a", encoding="utf-8", newline="") as handle:
            handle.write(line)


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    skipped = len(terminalreporter.stats.get("skipped", []))
    if skipped and os.environ.get("CI") == "true":
        terminalreporter.write_line(
            f"{skipped} tests were skipped; under CI=true a skip is a failure (spec §11.2)",
            red=True,
        )
