"""The source health entries of the feed (spec §5.6; P96; R11, R15)."""

import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, get_args

import pytest

from elections_calendar.feed import (
    MAX_SAMPLE_TEXT,
    MAX_SAMPLES,
    DownloadOutcome,
    SourceResult,
    source_health_entry,
)
from elections_calendar.health import (
    Acknowledgement,
    HealthState,
    MatchDiagnostic,
    severity,
    source_reasons,
)
from elections_calendar.model import REASON_STAGE, SOURCE_NAMES, SOURCE_ORDER, InputUnit, Reason
from elections_calendar.runner import SourceOutcome, SourceRun
from elections_calendar.snapshots import PageRecord, Snapshot, decide, registry_version, unit_items
from elections_calendar.sources.base import PAGE_REASONS, PARSER_VERSION, PageOutcome, RawPages
from elections_calendar.window import window_for
from tests.support.feed import RUN_NOW, first_run, fixture_snapshot
from tests.support.snapshots import SynthPage, promoted, report, synth

ENTRY_KEYS = [
    "source",
    "name",
    "download",
    "parse",
    "coverage",
    "snapshot",
    "match",
    "severity",
    "reasons",
    "acknowledged",
]
DOWNLOAD_KEYS = [
    "outcome",
    "stage",
    "http_status",
    "final_url",
    "content_type",
    "bytes",
    "elapsed_ms",
    "attempts",
    "error",
    "pages",
]
PARSE_KEYS = [
    "parser_version",
    "parse_ms",
    "units",
    "claims",
    "ignored_reasons",
    "relevance",
    "unparsed_samples",
]
UNIT_KEYS = ["seen", "parsed", "partial", "unparsed", "ignored"]
SNAPSHOT_KEYS = [
    "acceptance",
    "using_fallback",
    "served_snapshot_id",
    "served_fetched_at",
    "baseline_units_seen",
    "comparable",
]


def entries() -> dict[str, dict[str, Any]]:
    return {s: source_health_entry(r) for s, r in first_run().sources.items()}


def test_source_health_entry_keys() -> None:
    got = entries()
    assert list(got) == list(SOURCE_ORDER)
    for source, e in got.items():
        assert list(e) == ENTRY_KEYS
        assert e["source"] == source
        assert e["name"] == SOURCE_NAMES[source]
        assert list(e["download"]) == DOWNLOAD_KEYS
        assert list(e["download"]["pages"]) == ["requested", "ok", "failed", "stop_reason"]
        assert list(e["parse"]) == PARSE_KEYS
        assert list(e["parse"]["units"]) == UNIT_KEYS
        assert list(e["parse"]["relevance"]) == ["in_or_after_window", "unknown", "before_window"]
        assert list(e["coverage"]) == ["per_year"]
        assert list(e["snapshot"]) == SNAPSHOT_KEYS
        assert list(e["match"]) == ["eligible", "peers_fresh", "matched", "unmatched", "informative"]
        assert e["acknowledged"] == []
        assert e["parse"]["parser_version"] == PARSER_VERSION
        assert e["snapshot"]["acceptance"] == "promoted"

    ndi = got["ndi"]["download"]
    assert ndi["pages"] == {"requested": 2, "ok": 2, "failed": 0, "stop_reason": "complete"}
    assert ndi["outcome"] == "ok"
    eg = got["electionguide"]["coverage"]["per_year"]
    assert eg == {"all": {"requested": 3, "units_seen": 351, "outcome": "ok"}}
    eisa = got["eisa"]
    assert eisa["download"]["outcome"] == "not_published_yet"
    assert eisa["coverage"]["per_year"] == {
        "2026": {"requested": 1, "units_seen": 22, "outcome": "ok"},
        "all": {"requested": 1, "units_seen": 0, "outcome": "ok"},
    }
    assert list(eisa["coverage"]["per_year"]) == ["2026", "all"]
    assert got["wikipedia"]["coverage"]["per_year"] == {
        "2026": {"requested": 2, "units_seen": 565, "outcome": "ok"},
        "2027": {"requested": 2, "units_seen": 99, "outcome": "ok"},
    }
    osce = got["osce"]
    assert osce["parse"]["units"]["seen"] == 634
    assert osce["parse"]["claims"] == 180
    assert osce["download"]["bytes"] > 0
    assert osce["download"]["final_url"] == "https://odihr.osce.org/odihr/elections"
    assert osce["download"]["content_type"] == "text/html; charset=utf-8"
    assert osce["download"]["http_status"] == 200
    assert osce["download"]["stage"] == "done"
    assert osce["parse"]["units"] == {
        "seen": 634,
        "parsed": 173,
        "partial": 7,
        "unparsed": 454,
        "ignored": 0,
    }
    assert osce["parse"]["relevance"] == {
        "in_or_after_window": 0,
        "unknown": 0,
        "before_window": 461,
    }
    assert osce["parse"]["unparsed_samples"] == []
    assert osce["snapshot"] == {
        "acceptance": "promoted",
        "using_fallback": False,
        "served_snapshot_id": first_run().sources["osce"].decision.candidate.snapshot_id,
        "served_fetched_at": "2026-10-18T11:18:37Z",
        "baseline_units_seen": None,
        "comparable": False,
    }
    for source, result in first_run().sources.items():
        assert got[source]["match"] == dataclasses.asdict(result.match)
    assert got["ndi"]["match"] == {
        "eligible": 7,
        "peers_fresh": 7,
        "matched": 5,
        "unmatched": 2,
        "informative": True,
    }
    assert osce["match"] == {
        "eligible": 7,
        "peers_fresh": 5,
        "matched": 7,
        "unmatched": 0,
        "informative": True,
    }
    assert osce["severity"] == first_run().sources["osce"].severity


def test_health_lists_coverage_gaps_and_ignored_reasons() -> None:
    got = entries()
    for source, result in first_run().sources.items():
        assert result.ledger is not None
        ignored = got[source]["parse"]["ignored_reasons"]
        assert ignored == result.ledger.ignored_reasons
        assert list(ignored) == sorted(ignored)
    assert list(got["ipu"]["parse"]["ignored_reasons"].items()) == [
        ("appointed_chamber", 28),
        ("inactive_chamber", 10),
        ("no_expected_date", 5),
    ]
    assert list(got["eeas"]["parse"]["ignored_reasons"].items()) == [
        ("empty_cell", 7),
        ("year_heading", 4),
    ]

    note = Reason("coverage_gap", "dated text beside the table: 5 December 2026")
    candidate = synth(
        source="aweb",
        pages=(SynthPage("calendar", 20, year=2026),),
        fetched_at=RUN_NOW,
        notes=(note,),
    )
    result = result_of(candidate)
    e = source_health_entry(result)
    assert e["reasons"] == [
        {
            "code": "coverage_gap",
            "level": "warning",
            "stage": "parse",
            "year": None,
            "page": None,
            "text": "dated text beside the table: 5 December 2026",
        }
    ]
    assert e["severity"] == "warning"
    assert e["snapshot"]["acceptance"] == "promoted"


NO_MATCH = MatchDiagnostic(0, 0, 0, 0, False)


def result_of(
    candidate: Snapshot,
    *,
    baseline: Snapshot | None = None,
    outcome: SourceOutcome = "complete",
    detail: str = "",
) -> SourceResult:
    """A source's result as the pipeline assembles it, with no match, state or acknowledgement."""
    window = window_for(RUN_NOW)
    report_ = report(candidate)
    decision = decide(
        candidate,
        run_outcome=outcome,
        run_detail=detail,
        ledger=report_,
        baseline=None if baseline is None else promoted(baseline),
        baseline_problem=None,
        acceptances=(),
        window=window,
        now=RUN_NOW,
    )
    items = unit_items(decision)
    reasons = source_reasons(decision.reasons, items, NO_MATCH, HealthState(()))
    run = SourceRun(candidate.source, RawPages(candidate.source, ()), outcome, 0, detail)
    return SourceResult(
        source=candidate.source,
        run=run,
        parse_ms=0,
        ledger=report_,
        decision=decision,
        items=items,
        match=NO_MATCH,
        reasons=reasons,
        acknowledged=(),
        severity=severity(reasons),
    )


def test_health_reports_chain_length_and_missing_pages() -> None:
    _, _, fixture, _ = fixture_snapshot("ndi")
    assert [p.scope for p in fixture.pages] == ["pages", "pages"]
    three = synth(
        source="ndi",
        pages=tuple(SynthPage(f"p{i}", 13, scope="pages") for i in range(3)),
        fetched_at=RUN_NOW,
        parser_version=PARSER_VERSION,
        registry=registry_version(),
    )
    e = source_health_entry(result_of(fixture, baseline=three))
    assert e["snapshot"]["acceptance"] == "promoted"
    assert {
        "code": "count_change",
        "level": "info",
        "stage": "snapshot",
        "year": None,
        "page": "pages",
        "text": "pages: 3 pages, now 2",
    } in e["reasons"]
    assert e["download"]["pages"] == {
        "requested": 2,
        "ok": 2,
        "failed": 0,
        "stop_reason": "complete",
    }

    note = Reason("pagination_incomplete", "p2 was expected, not received", page="pages")
    cut = dataclasses.replace(fixture, notes=(note,))
    e = source_health_entry(result_of(cut))
    assert e["download"]["pages"]["stop_reason"] == "pagination_incomplete"
    listed = [r for r in e["reasons"] if r["code"] == "pagination_incomplete"]
    assert [(r["level"], r["stage"], r["page"]) for r in listed] == [("error", "parse", "pages")]


def pages_of(
    *pages: SynthPage,
    sizes: Sequence[tuple[int, int, int]] = (),
) -> Snapshot:
    """A snapshot of the pages; ``sizes`` gives each page download's bytes, elapsed_ms, attempts."""
    snapshot = synth(pages=pages, fetched_at=RUN_NOW)
    if sizes:
        records: list[PageRecord] = []
        for page, (size, elapsed, attempts) in zip(snapshot.pages, sizes, strict=True):
            assert page.download is not None
            download = dataclasses.replace(
                page.download, bytes=size, elapsed_ms=elapsed, attempts=attempts
            )
            records.append(dataclasses.replace(page, download=download))
        snapshot = dataclasses.replace(snapshot, pages=tuple(records))
    return snapshot


def page(key: str, outcome: PageOutcome = "ok", units: int = 3) -> SynthPage:
    return SynthPage(key, units if outcome in ("ok", "valid_empty") else 0, outcome=outcome)


DOWNLOADS: list[Any] = [
    pytest.param(
        pages_of(page("p1"), page("p2")), "deadline", "", "deadline", None, id="run deadline"
    ),
    pytest.param(
        pages_of(page("p1"), page("p2")),
        "scrape_deadline",
        "",
        "deadline",
        None,
        id="scrape deadline",
    ),
    pytest.param(
        pages_of(page("p1"), page("p2", "timeout")),
        "deadline",
        "",
        "deadline",
        None,
        id="the run outcome wins",
    ),
    pytest.param(
        pages_of(page("p1")),
        "worker_failed",
        "parse: ValueError",
        "worker_failed",
        "parse: ValueError",
        id="worker failed",
    ),
    pytest.param(
        pages_of(page("p1"), page("p2", "timeout"), page("p3", "http_error")),
        "complete",
        "",
        "timeout",
        None,
        id="first failing page",
    ),
    pytest.param(
        pages_of(page("p1"), page("p2", "unfinished")),
        "deadline",
        "worker cut",
        "deadline",
        "worker cut",
        id="unfinished page",
    ),
    pytest.param(
        pages_of(page("p1"), page("p2", "unfinished")),
        "complete",
        "",
        "deadline",
        None,
        id="unfinished maps to deadline",
    ),
    pytest.param(
        pages_of(page("p1"), page("p2", "layout_not_recognised")),
        "complete",
        "",
        "layout_not_recognised",
        None,
        id="layout",
    ),
    pytest.param(
        pages_of(page("p1", "layout_not_recognised"), page("p2", "not_published_yet")),
        "complete",
        "",
        "layout_not_recognised",
        None,
        id="layout before not published",
    ),
    pytest.param(
        pages_of(page("p1"), page("p2", "not_published_yet")),
        "complete",
        "",
        "not_published_yet",
        None,
        id="not published yet",
    ),
    pytest.param(
        pages_of(page("p1"), page("p2", "required_year_missing")),
        "complete",
        "",
        "ok",
        None,
        id="a missing year is no download failure",
    ),
    pytest.param(pages_of(page("p1"), page("p2")), "complete", "", "ok", None, id="ok"),
]


@pytest.mark.parametrize(("snapshot", "run", "detail", "outcome", "error"), DOWNLOADS)
def test_download_outcomes(
    snapshot: Snapshot, run: SourceOutcome, detail: str, outcome: str, error: str | None
) -> None:
    e = source_health_entry(result_of(snapshot, outcome=run, detail=detail))
    assert e["download"]["outcome"] == outcome
    assert e["download"]["error"] == error


def test_the_representative_page_and_the_sums() -> None:
    snapshot = pages_of(
        page("p1"),
        page("p2", "timeout"),
        page("p3"),
        sizes=[(100, 10, 1), (20, 5, 3), (7, 1, 1)],
    )
    d = source_health_entry(result_of(snapshot))["download"]
    assert d["outcome"] == "timeout"
    assert d["final_url"] == "https://osce.test/p2"
    assert d["http_status"] == 200
    assert d["stage"] == "done"
    assert (d["bytes"], d["elapsed_ms"], d["attempts"]) == (127, 16, 5)
    assert d["pages"] == {"requested": 3, "ok": 2, "failed": 1, "stop_reason": "complete"}

    # All pages fine: the first page speaks for the source, the sums are over every page.
    snapshot = pages_of(page("p1"), page("p2"), sizes=[(100, 10, 1), (20, 5, 3)])
    d = source_health_entry(result_of(snapshot))["download"]
    assert d["outcome"] == "ok"
    assert d["final_url"] == "https://osce.test/p1"
    assert (d["bytes"], d["elapsed_ms"], d["attempts"]) == (120, 15, 4)

    # An unfinished page has no download.
    d = source_health_entry(result_of(pages_of(page("p1"), page("p2", "unfinished"))))["download"]
    assert d["outcome"] == "deadline"
    assert (d["stage"], d["http_status"], d["final_url"], d["content_type"]) == (None,) * 4
    assert d["pages"] == {"requested": 2, "ok": 1, "failed": 1, "stop_reason": "complete"}

    # A page not published yet is neither ok nor failed.
    d = source_health_entry(result_of(pages_of(page("p1"), page("p2", "not_published_yet"))))
    assert d["download"]["final_url"] == "https://osce.test/p2"
    assert d["download"]["pages"] == {
        "requested": 2,
        "ok": 1,
        "failed": 0,
        "stop_reason": "complete",
    }
    d = source_health_entry(result_of(pages_of(page("p1"), page("p2", "valid_empty", 0))))
    assert d["download"]["pages"]["ok"] == 2


def test_a_fallback_entry_names_what_is_served() -> None:
    old = synth(pages=(page("p1"), page("p2")), fetched_at=RUN_NOW - timedelta(days=2))
    new = synth(pages=(page("p1"), page("p2", "timeout")), fetched_at=RUN_NOW)
    e = source_health_entry(result_of(new, baseline=old))
    assert e["snapshot"] == {
        "acceptance": "fallback",
        "using_fallback": True,
        "served_snapshot_id": old.snapshot_id,
        "served_fetched_at": "2026-10-17T12:00:00Z",
        "baseline_units_seen": 6,
        "comparable": True,
    }
    assert e["download"]["outcome"] == "timeout"
    assert [r["code"] for r in e["reasons"]] == ["timeout"]
    assert e["severity"] == "error"


def test_the_run_detail_is_redacted() -> None:
    snapshot = pages_of(page("p1"))
    detail = "fetch https://x.test/a?token=secret failed"
    e = source_health_entry(result_of(snapshot, outcome="worker_failed", detail=detail))
    assert e["download"]["error"] == "fetch https://x.test/a?REDACTED failed"


def test_the_run_detail_is_the_error_of_a_failed_worker_only() -> None:
    snapshot = pages_of(page("p1"))
    complete = source_health_entry(result_of(snapshot, detail="a note"))
    assert complete["download"]["error"] is None
    cut = source_health_entry(result_of(snapshot, outcome="worker_failed", detail="x" * 500))
    assert cut["download"]["error"] == "x" * 300


def test_per_year_coverage() -> None:
    snapshot = synth(
        pages=(
            SynthPage("a", 5, year=2027),
            SynthPage("b", 7, year=2026),
            SynthPage("c", 2),
            SynthPage("d", 4, year=2026),
            SynthPage("e", outcome="timeout", year=2027),
            SynthPage("f", outcome="http_error", year=2027),
        ),
        fetched_at=RUN_NOW,
    )
    per_year = source_health_entry(result_of(snapshot))["coverage"]["per_year"]
    assert per_year == {
        "2026": {"requested": 2, "units_seen": 11, "outcome": "ok"},
        "2027": {"requested": 3, "units_seen": 5, "outcome": "timeout"},
        "all": {"requested": 1, "units_seen": 2, "outcome": "ok"},
    }
    assert list(per_year) == ["2026", "2027", "all"]


def test_unparsed_samples_are_capped() -> None:
    def unit(n: int, relevance: str) -> InputUnit:
        text = f"{n}:" + "x" * 498
        return InputUnit(f"osce:p/u{n}", "osce", text, "unparsed", "no_date", relevance)  # type: ignore[arg-type]

    units = (unit(0, "before_window"), *(unit(n, "in_or_after_window") for n in range(1, 8)))
    snapshot = synth(pages=(SynthPage("p", extra=units),), fetched_at=RUN_NOW)
    e = source_health_entry(result_of(snapshot))
    samples = e["parse"]["unparsed_samples"]
    assert MAX_SAMPLES == 5 and MAX_SAMPLE_TEXT == 200
    assert samples == [(f"{n}:" + "x" * 498)[:200] for n in range(1, 6)]
    assert all(len(s) == 200 for s in samples)
    assert e["parse"]["units"]["unparsed"] == 8
    assert e["parse"]["relevance"] == {"in_or_after_window": 7, "unknown": 0, "before_window": 1}


def test_a_failed_parse_has_empty_counts() -> None:
    snapshot = pages_of(page("p1", "layout_not_recognised"))
    result = dataclasses.replace(result_of(snapshot), ledger=None)
    e = source_health_entry(result)
    assert e["parse"]["units"] == dict.fromkeys(UNIT_KEYS, 0)
    assert e["parse"]["ignored_reasons"] == {}
    assert e["parse"]["relevance"] == {"in_or_after_window": 0, "unknown": 0, "before_window": 0}
    assert e["parse"]["claims"] == 0
    assert e["snapshot"]["acceptance"] == "unavailable"
    assert e["snapshot"]["served_snapshot_id"] is None
    assert e["snapshot"]["served_fetched_at"] is None


def test_timestamps_and_acknowledgements() -> None:
    base = result_of(pages_of(page("p1")))
    until = datetime(2026, 10, 25, 12, tzinfo=UTC)
    reason = Reason("http_error", "HTTP 500", page="p1", year=2026)
    acks = (Acknowledgement("http_error", until, "fetch", 2026, "p1"),)
    gap = Reason("coverage_gap", "gone", page="calendar", year=2027)
    e = source_health_entry(dataclasses.replace(base, acknowledged=acks, reasons=(reason, gap)))
    assert e["acknowledged"] == [
        {"code": "http_error", "until": "2026-10-25T12:00:00Z", "stage": "fetch", "year": 2026, "page": "p1"}
    ]
    assert e["reasons"] == [
        {
            "code": "http_error",
            "level": "error",
            "stage": "fetch",
            "year": 2026,
            "page": "p1",
            "text": "HTTP 500",
        },
        {
            "code": "coverage_gap",
            "level": "warning",
            "stage": "parse",
            "year": 2027,
            "page": "calendar",
            "text": "gone",
        },
    ]
    assert e["snapshot"]["served_fetched_at"] == "2026-10-19T12:00:00Z"
    shown = dataclasses.replace(base, parse_ms=123, severity="warning")
    assert source_health_entry(shown)["parse"]["parse_ms"] == 123
    assert source_health_entry(shown)["severity"] == "warning"
    # A reason without a detail shows its code.
    bare = dataclasses.replace(base, reasons=(Reason("timeout"),))
    assert source_health_entry(bare)["reasons"][0]["text"] == "timeout"


def with_download_error(snapshot: Snapshot, key: str, error: str) -> Snapshot:
    """The snapshot with the page's own download carrying ``error``."""
    records: list[PageRecord] = []
    for p in snapshot.pages:
        if p.key == key:
            assert p.download is not None
            p = dataclasses.replace(p, download=dataclasses.replace(p.download, error=error))
        records.append(p)
    return dataclasses.replace(snapshot, pages=tuple(records))


def test_a_download_shows_its_own_error() -> None:
    snapshot = with_download_error(pages_of(page("p1"), page("p2", "timeout")), "p2", "boom")
    d = source_health_entry(result_of(snapshot, detail="a note"))["download"]
    assert d["outcome"] == "timeout"
    assert d["error"] == "boom"

    # The page's own error wins over the run detail.
    snapshot = with_download_error(pages_of(page("p1"), page("p2")), "p1", "boom")
    d = source_health_entry(result_of(snapshot, outcome="deadline", detail="the run detail"))
    assert d["download"]["outcome"] == "deadline"
    assert d["download"]["error"] == "boom"


def test_download_outcomes_cover_every_fetch_failure_code() -> None:
    fetch = {code for code, stage in REASON_STAGE.items() if stage == "fetch"}
    page_codes = set(PAGE_REASONS.values())
    assert fetch & page_codes
    assert fetch & page_codes <= set(get_args(DownloadOutcome))


def test_a_failed_worker_with_no_pages() -> None:
    candidate = synth(pages=(), fetched_at=RUN_NOW)
    assert candidate.pages == ()
    e = source_health_entry(result_of(candidate, outcome="worker_failed", detail="parse: boom"))
    d = e["download"]
    assert d["outcome"] == "worker_failed"
    assert d["error"] == "parse: boom"
    assert (d["stage"], d["http_status"], d["final_url"]) == (None, None, None)
    assert (d["bytes"], d["elapsed_ms"], d["attempts"]) == (0, 0, 0)
    assert d["pages"]["requested"] == 0
    assert e["coverage"]["per_year"] == {}
