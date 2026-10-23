"""``pipeline.run``: the offline and live run and the ``out/`` artifact (Plan 4 Task 8)."""

import dataclasses
import hashlib
import json
import shutil
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from elections_calendar import pipeline
from elections_calendar.feed import md_text, status_doc
from elections_calendar.health import match_diagnostic
from elections_calendar.health import severity as severity_of
from elections_calendar.health import verdict as verdict_of
from elections_calendar.model import SOURCE_NAMES, SOURCE_ORDER, DropAcceptance, Reason, stored_json
from elections_calendar.pipeline import RunResult, run
from elections_calendar.publish import write_atomic
from elections_calendar.runner import AdapterSpec, ScrapeRun, SourceRun
from elections_calendar.snapshots import decide, registry_version
from elections_calendar.sources.base import RawPages
from elections_calendar.sources.osce import Osce
from elections_calendar.validate import ServedCheck, validate_feed, validate_status
from tests.support.fixture_claims import fixture_results
from tests.support.known_issues import entry as ack_entry
from tests.support.known_issues import ts
from tests.support.repo import (
    NOW,
    OSCE,
    OSCE_FETCHED,
    commit,
    config,
    offline_dir,
    osce_offline,
)

IPU = AdapterSpec("ipu", "elections_calendar.sources.ipu:Ipu")
V1_FEED = Path(__file__).resolve().parents[1] / "fixtures" / "feed" / "2026-10-16-ff30417.json"
DAY = timedelta(days=1)
OSCE_NAME = SOURCE_NAMES["osce"]


def files(out: Path) -> set[str]:
    return {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}


def load(out: Path, name: str) -> Any:
    return json.loads((out / name).read_text(encoding="utf-8"))


def go(
    tmp_path: Path, offline: Path | None, **kw: Any
) -> tuple[RunResult, Path]:
    cfg = config(tmp_path, offline, **kw)
    return run(cfg), cfg.out


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def osce_entry(out: Path) -> dict[str, Any]:
    (entry,) = load(out, "elections.json")["source_health"]
    assert isinstance(entry, dict)
    return entry


def reason_codes(entry: dict[str, Any]) -> list[str]:
    return [r["code"] for r in entry["reasons"]]


def child_sources(doc: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for cards in doc["months"].values():
        for card in cards:
            for child in card["children"]:
                yield from child["sources"]


def children(doc: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for cards in doc["months"].values():
        for card in cards:
            yield from card["children"]


def write_known_issues(tmp_path: Path, *texts: str) -> None:
    (tmp_path / "repo").mkdir(exist_ok=True)
    (tmp_path / "repo" / "known_issues.yml").write_text("\n".join(texts) + "\n", encoding="utf-8")


PUBLISHED_FILES = {
    "elections.json",
    "status.json",
    "HEALTH.md",
    "data/sources/osce/baseline.json",
    "data/sources/osce/candidate.json",
    "data/sources/osce/health_state.json",
    "verdict.json",
    "attention_full.json",
    "dispositions.json",
    "manifest.json",
}


def test_a_first_run_writes_a_complete_artifact(tmp_path: Path) -> None:
    offline = osce_offline(tmp_path)
    result, out = go(tmp_path, offline)
    assert result.outcome == "published"
    assert result.verdict == "green"
    assert files(out) == PUBLISHED_FILES
    manifest = load(out, "manifest.json")
    assert manifest["files"] == {
        name: sha(out / name) for name in sorted(PUBLISHED_FILES - {"manifest.json"})
    }
    feed = (out / "elections.json").read_bytes()
    assert result.feed_bytes == len(feed)
    doc = json.loads(feed)
    served = doc["source_health"][0]["snapshot"]["served_snapshot_id"]
    assert validate_feed(feed, served=[ServedCheck("osce", served, True, True)], wall_clock=NOW) == ()
    assert validate_status((out / "status.json").read_bytes()) == ()
    status = load(out, "status.json")
    assert status["outcome"] == "published"
    assert status["serving_feed_sha256"] == sha(out / "elections.json")
    # Each severity is the one of the reasons verdict.json lists, and the verdict follows them.
    verdict = load(out, "verdict.json")
    for entry in doc["source_health"]:
        rows = [r for r in verdict["reasons"] if r["source"] == entry["source"]]
        assert entry["severity"] == severity_of([Reason(r["code"]) for r in rows])
    open_rows = [r for r in verdict["reasons"] if not r["acknowledged"]]
    assert verdict["verdict"] == verdict_of([Reason(r["code"]) for r in open_rows])
    assert verdict["outcome"] == "published"
    assert verdict["feed_bytes"] == len(feed)
    assert verdict["feed_budget_bytes"] == 524_288
    assert verdict["trust_sources"] == []


def test_the_same_input_gives_the_same_files(tmp_path: Path) -> None:
    offline = osce_offline(tmp_path)
    _, one = go(tmp_path, offline, out="one")
    _, two = go(tmp_path, offline, out="two")
    assert files(one) == files(two) == PUBLISHED_FILES
    assert all((one / n).read_bytes() == (two / n).read_bytes() for n in files(one))
    _, three = go(tmp_path, offline, out="three", environ={"GITHUB_RUN_ID": "7"})
    differing = {n for n in files(one) if (one / n).read_bytes() != (three / n).read_bytes()}
    assert differing == {"status.json", "manifest.json"}
    assert load(three, "manifest.json")["files"]["status.json"] == sha(three / "status.json")


def test_an_interrupted_write_leaves_no_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = write_atomic
    calls: list[Path] = []

    def dying(path: Path, data: bytes) -> None:
        calls.append(path)
        if len(calls) == 4:
            raise OSError("disk full")
        real(path, data)

    monkeypatch.setattr(pipeline, "write_atomic", dying)
    cfg = config(tmp_path, osce_offline(tmp_path))
    with pytest.raises(OSError, match="disk full"):
        run(cfg)
    assert len(calls) == 4
    assert not (cfg.out / "manifest.json").exists()
    assert not list(cfg.out.rglob("*.tmp"))


def test_merge_error_blocks_publishing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def failing(*args: object, **kwargs: object) -> None:
        raise ValueError("x" * 1000)

    monkeypatch.setattr(pipeline, "merge", failing)
    result, out = go(tmp_path, osce_offline(tmp_path))
    assert result.outcome == "validation_failed"
    assert result.verdict == "red"
    assert result.feed_bytes is None
    status = load(out, "status.json")
    (merge_failed,) = [r for r in status["reasons"] if r["code"] == "merge_failed"]
    assert merge_failed["source"] is None
    assert merge_failed["text"] == "x" * 300
    assert (out / "rejected" / "merge_error.txt").read_text(encoding="utf-8") == "x" * 1000
    assert not (out / "elections.json").exists()
    assert not (out / "data").exists()
    assert md_text(OSCE_NAME) in (out / "HEALTH.md").read_text(encoding="utf-8")
    assert status["outcome"] == "validation_failed"
    assert [status[k] for k in status if k.startswith("serving_")] == [None] * 4
    assert validate_status((out / "status.json").read_bytes()) == ()
    assert "manifest.json" in files(out)
    assert load(out, "verdict.json")["feed_bytes"] is None


def test_validation_failure_writes_no_feed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problems = ("size: 1 bytes is over 2000000",)
    monkeypatch.setattr(pipeline, "validate_feed", lambda *a, **k: problems)
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copyfile(V1_FEED, repo / "elections.json")
    result, out = go(tmp_path, osce_offline(tmp_path))
    assert (result.outcome, result.verdict) == ("validation_failed", "red")
    status = load(out, "status.json")
    assert status["outcome"] == "validation_failed"
    assert status["serving_feed_sha256"] == sha(V1_FEED)
    assert status["severity"] == load(out, "verdict.json")["severity"] == "error"
    rejected = json.loads((out / "rejected" / "elections.json").read_text(encoding="utf-8"))
    assert rejected["schema_version"] == 2
    assert (out / "rejected" / "validation.txt").read_text(encoding="utf-8") == problems[0] + "\n"
    assert not (out / "elections.json").exists()
    assert not (out / "data").exists()
    (reason,) = [r for r in status["reasons"] if r["code"] == "validation_failed"]
    assert reason["text"] == problems[0]


def test_an_invalid_status_blocks_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = status_doc

    def broken(**kwargs: Any) -> dict[str, Any]:
        doc = real(**kwargs)
        if kwargs["outcome"] == "published":
            doc["x"] = 1
        return doc

    monkeypatch.setattr(pipeline, "status_doc", broken)
    result, out = go(tmp_path, osce_offline(tmp_path))
    assert (result.outcome, result.verdict) == ("validation_failed", "red")
    status = load(out, "status.json")
    assert status["severity"] == load(out, "verdict.json")["severity"] == "error"
    assert validate_status((out / "status.json").read_bytes()) == ()
    (reason,) = [r for r in status["reasons"] if r["code"] == "validation_failed"]
    assert reason["text"].startswith("status: ")
    assert load(out, "verdict.json")["outcome"] == "validation_failed"
    assert load(out, "rejected/status.json")["x"] == 1
    assert (out / "rejected" / "validation.txt").read_text(encoding="utf-8").startswith("status: schema")
    assert not (out / "elections.json").exists()
    assert not (out / "data").exists()
    assert "rejected/elections.json" not in files(out)
    assert files(out) == {
        "status.json",
        "HEALTH.md",
        "verdict.json",
        "attention_full.json",
        "dispositions.json",
        "rejected/status.json",
        "rejected/validation.txt",
        "manifest.json",
    }
    manifest = load(out, "manifest.json")["files"]
    assert set(manifest) == files(out) - {"manifest.json"}
    problem = (out / "rejected" / "validation.txt").read_text(encoding="utf-8").splitlines()[0]
    assert reason["text"] == problem
    assert problem.startswith("status: ")
    assert md_text(problem) in (out / "HEALTH.md").read_text(encoding="utf-8")


def test_an_invalid_failure_status_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = status_doc

    def broken(**kwargs: Any) -> dict[str, Any]:
        doc = real(**kwargs)
        doc["x"] = 1
        return doc

    monkeypatch.setattr(pipeline, "status_doc", broken)
    cfg = config(tmp_path, osce_offline(tmp_path))
    with pytest.raises(RuntimeError, match="status.json failed validation: "):
        run(cfg)
    assert not cfg.out.exists() or files(cfg.out) == set()


def test_a_corrupt_health_state_needs_a_new_acknowledgement(tmp_path: Path) -> None:
    scope = "{stage: fetch, year: null, page: elections}"

    def acknowledgement(at: datetime) -> str:
        return ack_entry(
            source="osce",
            reason="http_error",
            scope=scope,
            acknowledged_at=ts(at),
            expires_at=ts(at + 7 * DAY),
        )

    state = tmp_path / "repo" / "data" / "sources" / "osce" / "health_state.json"
    state.parent.mkdir(parents=True)
    state.write_bytes(b"{")
    write_known_issues(tmp_path, acknowledgement(NOW - DAY))

    def http_error_row(out: Path) -> dict[str, Any]:
        (row,) = [r for r in load(out, "verdict.json")["reasons"] if r["code"] == "http_error"]
        assert isinstance(row, dict)
        return row

    def codes(out: Path) -> list[str]:
        return [r["code"] for r in load(out, "verdict.json")["reasons"]]

    repo = tmp_path / "repo"
    offline = osce_offline(tmp_path, "http_error", NOW - DAY)
    _, one = go(tmp_path, offline, out="one")
    assert codes(one).count("ack_invalid") == 1
    assert http_error_row(one)["acknowledged"] is False
    commit(one, repo)

    later = NOW + DAY
    offline = osce_offline(tmp_path, "http_error", later, name="offline2")
    _, two = go(tmp_path, offline, out="two", now=later)
    assert "ack_invalid" not in codes(two)
    assert http_error_row(two)["acknowledged"] is False
    assert load(two, "data/sources/osce/health_state.json")["reset_at"] == "2026-10-19T12:00:00Z"
    commit(two, repo)

    write_known_issues(tmp_path, acknowledgement(NOW - DAY), acknowledgement(NOW + timedelta(hours=1)))
    latest = NOW + 2 * DAY
    offline = osce_offline(tmp_path, "http_error", latest, name="offline3")
    _, three = go(tmp_path, offline, out="three", now=latest)
    assert "ack_invalid" not in codes(three)
    assert http_error_row(three)["acknowledged"] is True


def test_a_registry_change_never_serves_the_old_baseline(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _, first = go(tmp_path, osce_offline(tmp_path), out="first")
    commit(first, repo)
    baseline = repo / "data" / "sources" / "osce" / "baseline.json"
    data = json.loads(baseline.read_text(encoding="utf-8"))
    data["registry_version"] = "0" * 64
    baseline.write_bytes(stored_json(data))

    offline = osce_offline(tmp_path, "http_error", NOW, name="offline2")
    result, one = go(tmp_path, offline, out="one")
    assert result.outcome == "published"
    feed = (one / "elections.json").read_bytes()
    assert validate_feed(feed, served=[ServedCheck("osce", None, True, True)], wall_clock=NOW) == ()
    doc = json.loads(feed)
    entry = osce_entry(one)
    assert entry["snapshot"]["acceptance"] == "unavailable"
    assert entry["snapshot"]["served_snapshot_id"] is None
    assert all(s["name"] != OSCE_NAME for s in child_sources(doc))
    texts = {(r["code"], r["text"]) for r in entry["reasons"]}
    assert (
        "count_change",
        "baseline.json is from another registry version; it is never served",
    ) in texts
    assert ("unavailable", "baseline.json is from another registry version") in texts
    assert result.verdict == "red"
    assert (one / "data/sources/osce/baseline.json").read_bytes() == baseline.read_bytes()
    commit(one, repo)

    later = NOW + DAY
    result, two = go(tmp_path, osce_offline(tmp_path, "ok", name="offline3"), out="two", now=later)
    entry = osce_entry(two)
    assert entry["snapshot"]["acceptance"] == "promoted"
    assert "unavailable" not in reason_codes(entry)
    new = json.loads((two / "data/sources/osce/baseline.json").read_text(encoding="utf-8"))
    assert new["registry_version"] == registry_version()


def test_a_ten_day_outage_ages_honestly(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    start = OSCE_FETCHED
    stamp = "2026-10-18T11:18:37Z"
    _, day0 = go(tmp_path, osce_offline(tmp_path), out="day0", now=start)
    commit(day0, repo)
    assert load(day0, "verdict.json")["verdict"] == "green"
    baseline = (day0 / "data/sources/osce/baseline.json").read_bytes()
    for k in range(1, 11):
        at = start + k * DAY
        offline = osce_offline(tmp_path, "timeout", at, name=f"offline{k}")
        result, out = go(tmp_path, offline, out=f"day{k}", now=at)
        commit(out, repo)
        assert result.outcome == "published"
        assert load(out, "verdict.json")["verdict"] == "red"
        doc = load(out, "elections.json")
        entry = osce_entry(out)
        assert entry["snapshot"]["acceptance"] == "fallback"
        assert entry["snapshot"]["served_fetched_at"] == stamp
        assert doc["data_as_of"] == stamp
        sources = list(child_sources(doc))
        assert sources
        assert all(s["fetched_at"] == stamp and s["fallback"] for s in sources)
        assert (out / "data/sources/osce/baseline.json").read_bytes() == baseline
        stale = [r for r in entry["reasons"] if r["code"] == "fallback_stale"]
        if k <= 7:
            assert stale == []
        else:
            assert [r["text"] for r in stale] == [f"serving data fetched {stamp}"]
            assert all(c["unverified"] for c in children(doc))


def test_a_deadline_is_a_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake(specs: Any, window: Any, **kwargs: Any) -> ScrapeRun:
        raw = RawPages("osce", (), Osce().requests(window))
        return ScrapeRun((), (SourceRun("osce", raw, "deadline", 0, "cut"),))

    monkeypatch.setattr(pipeline, "run_sources", fake)
    result, out = go(tmp_path, None)
    entry = osce_entry(out)
    assert entry["download"]["outcome"] == "deadline"
    assert ("deadline", "cut") in [(r["code"], r["text"]) for r in entry["reasons"]]
    assert entry["snapshot"]["acceptance"] == "unavailable"
    assert (result.outcome, result.verdict) == ("published", "red")


def test_parse_time_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    times = iter([10.0, 10.25])
    _, out = go(tmp_path, osce_offline(tmp_path), timer=lambda: next(times))
    assert osce_entry(out)["parse"]["parse_ms"] == 250

    def boom(self: Osce, *args: object) -> None:
        raise ValueError("secret detail")

    monkeypatch.setattr(Osce, "parse", boom)
    _, out = go(tmp_path, osce_offline(tmp_path, name="again"), out="second")
    entry = osce_entry(out)
    reasons = {r["code"]: r["text"] for r in entry["reasons"]}
    assert reasons["worker_failed"] == "parse: ValueError"
    assert reasons["layout_not_recognised"].endswith("the parser failed")
    assert entry["download"]["outcome"] == "worker_failed"
    assert entry["parse"]["units"] == {"seen": 0, "parsed": 0, "partial": 0, "unparsed": 0, "ignored": 0}
    assert entry["snapshot"]["acceptance"] != "promoted"
    assert "secret" not in (out / "elections.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("where", ["unit", "note"])
def test_a_lone_surrogate_costs_only_its_source(
    where: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Osce.parse
    lone = chr(0xD800)

    def poisoned(self: Osce, raw: Any, window: Any, registries: Any) -> Any:
        result = real(self, raw, window, registries)
        first, *rest = result.units
        units = (dataclasses.replace(first, text=first.text + lone), *rest)
        notes = (*result.notes, Reason("count_change", lone))
        if where == "unit":
            return dataclasses.replace(result, units=units)
        return dataclasses.replace(result, notes=notes)

    monkeypatch.setattr(Osce, "parse", poisoned)
    _, out = go(tmp_path, osce_offline(tmp_path))
    assert "manifest.json" in files(out)
    entry = osce_entry(out)
    assert {r["code"]: r["text"] for r in entry["reasons"]}["worker_failed"] == (
        "parse: UnicodeEncodeError"
    )
    for name in files(out):
        (out / name).read_bytes().decode("utf-8")


def test_a_parse_failure_shows_one_worker_failed_and_no_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P108 (M3) end to end; the stand-in is a run whose requests are all unfinished."""

    def fake(specs: Any, window: Any, **kwargs: Any) -> ScrapeRun:
        raw = RawPages("osce", (), Osce().requests(window))
        return ScrapeRun((), (SourceRun("osce", raw, "complete", 0),))

    def boom(self: Osce, *args: object) -> None:
        raise ValueError("x")

    monkeypatch.setattr(pipeline, "run_sources", fake)
    monkeypatch.setattr(Osce, "parse", boom)
    _, out = go(tmp_path, None)
    status = load(out, "status.json")
    mine = [r["code"] for r in status["reasons"] if r["source"] == "osce"]
    assert mine.count("worker_failed") == 1
    assert "deadline" not in mine
    assert "deadline" not in reason_codes(osce_entry(out))


def test_a_future_health_state_is_ack_invalid(tmp_path: Path) -> None:
    """P110 end to end: a pair later than the run's now voids the source's acknowledgements."""
    state = tmp_path / "repo" / "data" / "sources" / "osce" / "health_state.json"
    state.parent.mkdir(parents=True)
    future = NOW + timedelta(hours=1)
    state.write_text(
        json.dumps({"last_absent_at": {"http_error|fetch||": ts(future)}, "reset_at": None}),
        encoding="utf-8",
    )
    _, out = go(tmp_path, osce_offline(tmp_path))
    details = [r["text"] for r in osce_entry(out)["reasons"] if r["code"] == "ack_invalid"]
    assert details == [
        'health_state.json is corrupt: timestamp of "http_error|fetch||" is after the run'
    ]


def test_a_failed_parse_keeps_the_unfinished_requests_unfinished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(specs: Any, window: Any, **kwargs: Any) -> ScrapeRun:
        raw = RawPages("osce", (), Osce().requests(window))
        return ScrapeRun((), (SourceRun("osce", raw, "complete", 0),))

    def boom(self: Osce, *args: object) -> None:
        raise ValueError("x")

    monkeypatch.setattr(pipeline, "run_sources", fake)
    monkeypatch.setattr(Osce, "parse", boom)
    _, out = go(tmp_path, None)
    codes = reason_codes(osce_entry(out))
    assert "worker_failed" in codes
    assert "deadline" not in codes  # P108: worker_failed covers the unfinished requests
    assert "layout_not_recognised" not in codes


def test_a_failed_fetch_is_that_sources_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(self: Osce, *args: object) -> None:
        raise RuntimeError("secret detail")

    monkeypatch.setattr(Osce, "fetch", boom)
    _, out = go(tmp_path, osce_offline(tmp_path))
    entry = osce_entry(out)
    assert {r["code"]: r["text"] for r in entry["reasons"]}["worker_failed"] == (
        "fetch: RuntimeError"
    )
    assert entry["snapshot"]["acceptance"] == "unavailable"


def test_offline_pages_are_restamped(tmp_path: Path) -> None:
    other = datetime(2026, 10, 17, 3, 4, 5, tzinfo=UTC)
    _, out = go(tmp_path, osce_offline(tmp_path, fetched_at=other))
    candidate = load(out, "data/sources/osce/candidate.json")
    assert candidate["fetched_at"] == "2026-10-17T03:04:05Z"


def test_an_unknown_offline_url_is_a_404(tmp_path: Path) -> None:
    _, out = go(tmp_path, offline_dir(tmp_path, []))
    entry = osce_entry(out)
    assert entry["download"]["outcome"] == "http_error"
    assert entry["download"]["http_status"] == 404
    assert entry["snapshot"]["acceptance"] == "unavailable"


def test_live_records_trust_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    raw, _ = fixture_results()["osce"]
    seen: list[Path] = []

    def fake(specs: Any, window: Any, *, workdir: Path, environ: Any) -> ScrapeRun:
        assert workdir.is_dir()
        seen.append(workdir)
        return ScrapeRun(("certifi", "REQUESTS_CA_BUNDLE"), (SourceRun("osce", raw, "complete", 0),))

    monkeypatch.setattr(pipeline, "run_sources", fake)
    _, out = go(tmp_path, None)
    assert load(out, "verdict.json")["trust_sources"] == ["certifi", "REQUESTS_CA_BUNDLE"]
    assert load(out, "elections.json")["run"]["trust_sources"] == ["certifi", "REQUESTS_CA_BUNDLE"]
    (workdir,) = seen
    assert not workdir.exists()


def test_the_workdir_goes_when_the_scrape_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[Path] = []

    def fake(specs: Any, window: Any, *, workdir: Path, environ: Any) -> ScrapeRun:
        seen.append(workdir)
        raise KeyboardInterrupt

    monkeypatch.setattr(pipeline, "run_sources", fake)
    with pytest.raises(KeyboardInterrupt):
        go(tmp_path, None)
    assert not seen[0].exists()


def test_match_diagnostic_is_given_the_promoted_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = match_diagnostic
    calls: list[tuple[str, frozenset[str]]] = []

    def spy(result: Any, claims: Any, source: str, *, fresh: Any, window: Any) -> Any:
        calls.append((source, frozenset(fresh)))
        return real(result, claims, source, fresh=fresh, window=window)

    monkeypatch.setattr(pipeline, "match_diagnostic", spy)
    go(tmp_path, osce_offline(tmp_path), specs=(OSCE, IPU))
    assert calls == [("osce", frozenset({"osce"})), ("ipu", frozenset({"osce"}))]


@pytest.mark.parametrize("which", ["baseline", "state", "known_issues"])
def test_an_unreadable_committed_file_is_that_files_corrupt_form(
    which: str, tmp_path: Path
) -> None:
    repo = tmp_path / "repo"
    folder = repo / "data" / "sources" / "osce"
    folder.mkdir(parents=True)
    path = {
        "baseline": folder / "baseline.json",
        "state": folder / "health_state.json",
        "known_issues": repo / "known_issues.yml",
    }[which]
    path.mkdir()
    result, out = go(tmp_path, osce_offline(tmp_path))
    assert result.outcome == "published"
    rows = load(out, "verdict.json")["reasons"]
    wanted = {
        "baseline": ("osce", "ledger_mismatch", "baseline.json is corrupt: cannot be read ("),
        "state": ("osce", "ack_invalid", "health_state.json is corrupt: cannot be read ("),
        "known_issues": (None, "ack_invalid", "known_issues.yml cannot be read ("),
    }[which]
    assert [r for r in rows if (r["source"], r["code"]) == wanted[:2]]
    (row,) = [r for r in rows if (r["source"], r["code"]) == wanted[:2]]
    assert row["text"].startswith(wanted[2]) and row["text"].endswith(")")
    assert row["acknowledged"] is False
    assert result.verdict == "red"


def test_verdict_rows_follow_the_source_order(tmp_path: Path) -> None:
    guide = AdapterSpec("electionguide", "elections_calendar.sources.electionguide:ElectionGuide")
    write_known_issues(tmp_path, "- just a string")  # a run reason, which comes last
    _, out = go(tmp_path, offline_dir(tmp_path, []), specs=(IPU, guide))
    sources = [r["source"] for r in load(out, "verdict.json")["reasons"]]
    assert set(sources) == {"electionguide", "ipu", None}
    assert sources == sorted(sources, key=lambda s: (s is None, SOURCE_ORDER.index(s) if s else 0))


def test_drop_acceptances_reach_decide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = (DropAcceptance("osce", "sudden_drop", "elections", None, 1, 1, NOW + DAY),)
    asked: list[tuple[Any, ...]] = []
    given: list[Any] = []
    real = decide

    def accept(issues: Any, states: Any, now: datetime) -> Any:
        asked.append((sorted(states), now))
        return sentinel

    def spy(*args: Any, **kwargs: Any) -> Any:
        given.append(kwargs["acceptances"])
        return real(*args, **kwargs)

    monkeypatch.setattr(pipeline, "drop_acceptances", accept)
    monkeypatch.setattr(pipeline, "decide", spy)
    go(tmp_path, osce_offline(tmp_path))
    assert asked == [(["osce"], NOW)]
    assert given == [sentinel]


@pytest.mark.parametrize("field", ["now", "wall_clock"])
def test_an_out_of_range_time_is_a_usage_error(field: str, tmp_path: Path) -> None:
    bad = datetime.fromisoformat("0001-01-01T00:00:00+05:00")
    base = config(tmp_path, osce_offline(tmp_path))
    cfg = (
        dataclasses.replace(base, now=bad)
        if field == "now"
        else dataclasses.replace(base, wall_clock=bad)
    )
    with pytest.raises(pipeline.UsageError, match="--now is out of range"):
        run(cfg)
    assert not cfg.out.exists()


def test_a_baseline_of_another_source_is_never_served(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _, first = go(tmp_path, osce_offline(tmp_path), out="first")
    commit(first, repo)
    folder = repo / "data" / "sources"
    (folder / "ipu").mkdir()
    for name in ("baseline.json", "health_state.json"):
        shutil.copyfile(folder / "osce" / name, folder / "ipu" / name)  # IPU's files hold OSCE's
    _, out = go(tmp_path, offline_dir(tmp_path, [], name="empty"), specs=(IPU,), out="second")
    (entry,) = load(out, "elections.json")["source_health"]
    assert entry["source"] == "ipu"
    assert entry["snapshot"]["acceptance"] == "unavailable"
    texts = [r["text"] for r in entry["reasons"]]
    assert any(t.startswith("baseline.json is corrupt: it is of 'osce', not 'ipu'") for t in texts)
    assert list(children(load(out, "elections.json"))) == []  # nothing of OSCE is served as IPU


def test_a_scrape_run_of_another_source_is_a_programming_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake(specs: Any, window: Any, **kwargs: Any) -> ScrapeRun:
        raw = RawPages("ipu", (), ())
        return ScrapeRun((), (SourceRun("ipu", raw, "complete", 0),))

    monkeypatch.setattr(pipeline, "run_sources", fake)
    cfg = config(tmp_path, None)
    with pytest.raises(ValueError, match="scrape run of 'ipu'.*for 'osce'"):
        run(cfg)
    assert not cfg.out.exists() or files(cfg.out) == set()


def test_an_over_budget_feed_is_a_red_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from elections_calendar.__main__ import main

    offline = osce_offline(tmp_path)
    green, out = go(tmp_path, offline)
    assert (green.verdict, load(out, "verdict.json")["over_budget"]) == ("green", False)
    reasons = load(out, "status.json")["reasons"]

    monkeypatch.setattr(pipeline, "FEED_BUDGET_BYTES", 100)
    red, out = go(tmp_path, offline, out="over")
    verdict = load(out, "verdict.json")
    assert (red.verdict, verdict["verdict"]) == ("red", "red")
    assert verdict["over_budget"] is True
    assert (red.outcome, verdict["outcome"]) == ("published", "published")
    assert load(out, "status.json")["reasons"] == reasons

    status = main(
        [
            "--offline", str(offline), "--now", "2026-10-19T12:00:00Z",
            "--out", str(tmp_path / "cli"), "--repo", str(tmp_path / "repo"),
        ]
    )
    assert status == 0
    cli = tmp_path / "cli"
    assert load(cli, "verdict.json")["over_budget"] is True
    size = (cli / "elections.json").stat().st_size
    assert capsys.readouterr().out == f"published, verdict red, {size} feed bytes\n"
