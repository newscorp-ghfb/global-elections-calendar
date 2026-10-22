"""Recurrence history and unreadable text through ``pipeline.run`` (Plan 4 final review I3-I5)."""

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from elections_calendar.model import FetchOutcome
from elections_calendar.pipeline import RunResult, run
from tests.support.known_issues import entry, ts
from tests.support.repo import NOW, commit, config, osce_offline

DAY = timedelta(days=1)
SCOPE = "{stage: fetch, year: null, page: elections}"
SURROGATE = r'"\ud83d\ude00"'  # how JSON-minded tools escape an emoji; PyYAML reads two lone surrogates
STATE = "data/sources/osce/health_state.json"


def acknowledgement() -> str:
    """A timeout acknowledgement given an hour before NOW, valid for ten days."""
    return entry(
        source="osce",
        reason="timeout",
        scope=SCOPE,
        acknowledged_at=ts(NOW - timedelta(hours=1)),
        expires_at=ts(NOW + 10 * DAY),
    )


class Repo:
    """One tmp repository that daily runs publish into, as Plan 5's job will."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.repo = tmp_path / "repo"
        self.repo.mkdir()

    def issues(self, text: str) -> None:
        (self.repo / "known_issues.yml").write_text(text + "\n", encoding="utf-8")

    def day(self, k: int, outcome: FetchOutcome = "ok") -> tuple[RunResult, Path]:
        at = NOW + k * DAY
        cfg = config(self.tmp, osce_offline(self.tmp, outcome, at, name=f"o{k}"), out=f"d{k}", now=at)
        result = run(cfg)
        commit(cfg.out, self.repo)
        return result, cfg.out


def rows(out: Path, code: str) -> list[dict[str, Any]]:
    doc = json.loads((out / "verdict.json").read_text(encoding="utf-8"))
    return [r for r in doc["reasons"] if r["code"] == code]


def test_a_broken_known_issues_file_does_not_erase_the_recurrence(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.issues(acknowledgement())
    repo.day(0)
    result, _ = repo.day(1)  # no timeout: the absence is recorded, the acknowledgement is void
    assert result.verdict == "green"
    result, out = repo.day(2, "timeout")  # the timeout recurs: it stays open
    assert result.verdict == "red"
    assert [r["acknowledged"] for r in rows(out, "timeout")] == [False]
    repo.issues("- source: osce\n\treason: timeout")  # a tab: the whole file is not valid YAML
    repo.day(3, "timeout")
    repo.issues(acknowledgement())  # fixed on day 4
    result, out = repo.day(4, "timeout")
    assert result.verdict == "red"
    assert [r["acknowledged"] for r in rows(out, "timeout")] == [False]


def test_a_deleted_health_state_does_not_bring_back_a_voided_acknowledgement(
    tmp_path: Path,
) -> None:
    repo = Repo(tmp_path)
    repo.issues(acknowledgement())
    repo.day(0)
    repo.day(1)  # the absence is recorded: the acknowledgement is void
    (repo.repo / STATE).unlink()  # the baseline stays; the history is lost
    result, out = repo.day(2, "timeout")
    assert result.verdict == "red"
    assert [r["acknowledged"] for r in rows(out, "timeout")] == [False]
    (invalid,) = rows(out, "ack_invalid")
    assert invalid["source"] == "osce"
    assert "health_state.json is corrupt: missing beside a baseline" in invalid["text"]
    state = json.loads((out / STATE).read_text(encoding="utf-8"))
    assert state["reset_at"] == "2026-10-21T12:00:00Z"


def test_a_first_run_without_a_state_has_no_complaint(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.issues(acknowledgement())
    _, out = repo.day(0, "timeout")
    assert rows(out, "ack_invalid") == []
    assert [r["acknowledged"] for r in rows(out, "timeout")] == [True]


def known_issues_with(field: str) -> str:
    if field == "page":
        return entry(
            source="osce",
            reason="http_error",
            scope="{stage: fetch, year: null, page: " + SURROGATE + "}",
        )
    if field == "unit":
        return entry(source="osce", reason="unparsed_relevant", scope=None, unit_text=SURROGATE)
    return entry(source=SURROGATE)


@pytest.mark.parametrize("field", ["page", "unit", "source"])
def test_unreadable_text_in_known_issues_is_an_invalid_entry(tmp_path: Path, field: str) -> None:
    repo = Repo(tmp_path)
    repo.issues(known_issues_with(field))
    result, out = repo.day(0)
    assert result.outcome == "published"
    assert (out / "manifest.json").exists()
    (invalid,) = rows(out, "ack_invalid")
    assert invalid["text"].startswith("known_issues.yml entry 1: ")
    (out / "HEALTH.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("key", "problem"),
    [
        (r"\ud800", "health_state.json is corrupt: shape"),
        (r"k\nl", 'health_state.json is corrupt: timestamp of "k\\nl"'),
    ],
    ids=["surrogate", "newline"],
)
def test_a_state_key_is_never_echoed_raw(tmp_path: Path, key: str, problem: str) -> None:
    repo = Repo(tmp_path)
    state = repo.repo / STATE
    state.parent.mkdir(parents=True)
    state.write_text(
        '{"last_absent_at": {"' + key + '": "x"}, "reset_at": null}', encoding="utf-8"
    )
    result, out = repo.day(0)
    assert result.outcome == "published"
    assert (out / "manifest.json").exists()
    (invalid,) = rows(out, "ack_invalid")
    assert problem in invalid["text"]
    (out / "HEALTH.md").read_text(encoding="utf-8")
