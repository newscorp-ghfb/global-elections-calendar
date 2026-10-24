"""``tests/conftest.py``: a skip is a failure under ``CI=true``, and the counts reach the summary."""

from pathlib import Path

import pytest

CONFTEST = Path(__file__).resolve().parents[1] / "conftest.py"
INNER = """
import pytest

def test_passes():
    pass

def test_skipped():
    pytest.skip("on purpose")
"""


def _inner(pytester: pytest.Pytester) -> None:
    pytester.makeconftest(CONFTEST.read_text(encoding="utf-8"))
    pytester.makepyfile(INNER)


def test_a_skip_fails_under_ci(pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch) -> None:
    _inner(pytester)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("PYTHONIOENCODING", "utf-8")  # the message holds a section sign
    failed = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    assert failed.ret == pytest.ExitCode.TESTS_FAILED
    failed.stdout.fnmatch_lines(
        ["*1 tests were skipped; under CI=true a skip is a failure (spec §11.2)*"]
    )
    monkeypatch.delenv("CI")
    quiet = pytester.runpytest_subprocess("-p", "no:cacheprovider")
    assert quiet.ret == pytest.ExitCode.OK
    assert "a skip is a failure" not in quiet.stdout.str()


def test_counts_go_to_the_step_summary(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _inner(pytester)
    summary = tmp_path / "summary.md"
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    pytester.runpytest_subprocess("-p", "no:cacheprovider")
    assert summary.read_text(encoding="utf-8") == (
        "pytest: 2 collected, 1 passed, 0 failed, 1 skipped, 0 xfailed\n"
    )
