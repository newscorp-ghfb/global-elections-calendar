"""A unit reason the last served data already had does not turn the run red (P149), end to end.

The source is A-WEB: its one page has one unparsed and two partial relevant units, so on a
second day with the same page both unit reasons are known. Each day is one ``pipeline.run``
published into the same tmp repository, as the daily job does.
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from elections_calendar.model import FetchOutcome
from elections_calendar.pipeline import run
from elections_calendar.runner import AdapterSpec
from tests.support.fixtures import FIXTURES
from tests.support.known_issues import entry, ts
from tests.support.repo import NOW, commit, config, offline_dir

AWEB = AdapterSpec("aweb", "elections_calendar.sources.aweb:Aweb")
URL = "https://www.aweb.org/eng/bbs/B0000007/list.do?menuNo=300052&option=all"
FETCHED = datetime(2026, 10, 18, 11, 18, 38, tzinfo=UTC)
PAGE = (FIXTURES / "aweb/2026-10-18/calendar.html").read_text(encoding="utf-8")
DAY = timedelta(days=1)
UNIT_CODES = ("unparsed_relevant", "partial_relevant")
KNOWN_TEXT = " — known: all of these units were in the last served data, so the run is not red for it"
ROW = "| A" + chr(92) + "-WEB"  # md_text escapes the hyphen
GHANA = "2026 The Presidential Primaries"  # the one unparsed unit: office_not_modelled


class Repo:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        (tmp_path / "repo").mkdir()

    def day(self, k: int, page: str = PAGE, outcome: FetchOutcome = "ok") -> Path:
        at = NOW + k * DAY
        body = self.tmp / f"page{k}.html"
        body.write_text(page, encoding="utf-8")
        offline = offline_dir(self.tmp, [(URL, body, FETCHED + k * DAY, outcome)], name=f"o{k}")
        cfg = config(self.tmp, offline, out=f"d{k}", now=at, specs=(AWEB,))
        run(cfg)
        commit(cfg.out, self.tmp / "repo")
        return cfg.out


def verdict(out: Path) -> dict[str, Any]:
    return json.loads((out / "verdict.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def unit_rows(out: Path) -> list[dict[str, Any]]:
    return [r for r in verdict(out)["reasons"] if r["code"] in UNIT_CODES]


def acceptance(out: Path) -> str:
    lines = (out / "HEALTH.md").read_text(encoding="utf-8").splitlines()
    return next(ln for ln in lines if ln.startswith(ROW)).split("|")[3].strip()


def test_an_unchanged_unit_reason_does_not_make_the_run_red(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    first = repo.day(0)
    assert verdict(first)["verdict"] == "red"
    assert [r["code"] for r in unit_rows(first)] == list(UNIT_CODES)
    assert [r["known"] for r in unit_rows(first)] == [False, False]

    out = repo.day(1)
    doc = verdict(out)
    assert doc["verdict"] == "green"
    rows = unit_rows(out)
    assert [r["code"] for r in rows] == list(UNIT_CODES)
    assert all(r["known"] is True and r["acknowledged"] is False for r in rows)
    status = json.loads((out / "status.json").read_text(encoding="utf-8"))
    listed = status["reasons"]
    assert [r["code"] for r in listed if r["code"] in UNIT_CODES] == list(UNIT_CODES)
    assert all(not r["acknowledged"] for r in listed if r["code"] in UNIT_CODES)
    feed = json.loads((out / "elections.json").read_text(encoding="utf-8"))
    assert [h["severity"] for h in feed["source_health"] if h["source"] == "aweb"] == ["warning"]
    health = (out / "HEALTH.md").read_text(encoding="utf-8")
    lines = [ln for ln in health.splitlines() if "unparsed\\_relevant" in ln or "partial\\_relevant" in ln]
    assert len(lines) == 2
    assert all(ln.endswith(KNOWN_TEXT) for ln in lines)
    cells = [ln for ln in health.splitlines() if ln.startswith(ROW)]
    assert len(cells) == 1
    assert cells[0].endswith("| 0 (+2 known) |")


def test_a_new_unit_makes_the_run_red_again(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.day(0)
    assert GHANA in PAGE
    out = repo.day(1, PAGE.replace(GHANA, "2026 The Senate Primaries"))
    assert verdict(out)["verdict"] == "red"
    rows = unit_rows(out)
    assert [r["code"] for r in rows if not r["known"]] == ["unparsed_relevant"]


def test_a_unit_that_returns_is_new(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.day(0)
    resolved = repo.day(1, PAGE.replace(GHANA, "2026 The Presidential Election"))
    assert acceptance(resolved) == "promoted"
    out = repo.day(2)
    assert verdict(out)["verdict"] == "red"
    rows = [r for r in unit_rows(out) if r["code"] == "unparsed_relevant"]
    assert rows
    assert all(r["known"] is False for r in rows)


def test_an_unreadable_baseline_knows_nothing(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.day(0)
    (tmp_path / "repo/data/sources/aweb/baseline.json").write_text("{", encoding="utf-8")
    out = repo.day(1)
    assert verdict(out)["verdict"] == "red"
    rows = unit_rows(out)
    assert rows
    assert all(r["known"] is False for r in rows)
    assert [r for r in verdict(out)["reasons"] if r["code"] == "ledger_mismatch"]


def test_a_fallback_day_keeps_its_own_reasons_red(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    repo.day(0)
    out = repo.day(1, outcome="timeout")
    doc = verdict(out)
    assert doc["verdict"] == "red"
    rows = unit_rows(out)
    assert [r["code"] for r in rows] == list(UNIT_CODES)
    assert all(r["known"] is True for r in rows)
    shown = [r for r in doc["reasons"] if r["level"] in ("error", "warning")]
    assert [r["code"] for r in shown if not r["known"]] == ["timeout"]
    assert {r["code"] for r in shown if r["known"]} == set(UNIT_CODES)


def test_an_acknowledged_known_reason_shows_its_acknowledgement(tmp_path: Path) -> None:
    repo = Repo(tmp_path)
    first = repo.day(0)
    full = json.loads((first / "attention_full.json").read_text(encoding="utf-8"))
    texts = [
        i["unit_text"] for i in full["items"] if i["kind"] == "unparsed_unit" and i["source"] == "aweb"
    ]
    assert len(texts) == 1
    acknowledgement = entry(
        source="aweb",
        reason="unparsed_relevant",
        scope=None,
        unit_text=json.dumps(texts[0]),
        acknowledged_at=ts(NOW + DAY - timedelta(hours=1)),
        expires_at=ts(NOW + 5 * DAY),
    )
    (tmp_path / "repo/known_issues.yml").write_text(acknowledgement + "\n", encoding="utf-8")
    out = repo.day(1)
    assert verdict(out)["verdict"] == "green"
    lines = (out / "HEALTH.md").read_text(encoding="utf-8").splitlines()
    unparsed = next(ln for ln in lines if "unparsed\\_relevant" in ln)
    partial = next(ln for ln in lines if "partial\\_relevant" in ln)
    assert " — acknowledged until " in unparsed
    assert "known:" not in unparsed
    assert partial.endswith(KNOWN_TEXT)
    assert next(ln for ln in lines if ln.startswith(ROW)).endswith("| 0 (+1 known) |")
