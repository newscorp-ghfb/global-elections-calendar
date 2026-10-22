"""The acceptance decision (spec §9.3; P90-P95, P105; R1, R2, R14, R19).

Unless a test says otherwise the window is ``window_for(NOW)``, the baseline has one page
``elections`` of 100 units fetched at ``T0``, and the run is complete with a clean ledger report.
"""

import dataclasses
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import pytest

from elections_calendar.ledger import LedgerReport
from elections_calendar.merge import merge
from elections_calendar.model import (
    REASON_LEVEL,
    Claim,
    DropAcceptance,
    InputUnit,
    Reason,
    Relevance,
    SnapshotHealth,
)
from elections_calendar.places import PlaceRegistry
from elections_calendar.runner import SourceOutcome
from elections_calendar.snapshots import (
    Baseline,
    CoverageGap,
    Decision,
    Disappeared,
    HistoryEntry,
    ScopeCount,
    Snapshot,
    build_snapshot,
    decide,
    same_listing,
    scope_counts,
    unchanged,
)
from elections_calendar.sources.base import PageOutcome
from elections_calendar.window import window_for
from tests.support.claims import CH, PE, cl, day, mk, year
from tests.support.fixture_claims import FIXTURE_NOW, fixture_results
from tests.support.snapshots import NOW, REGISTRY, T0, SynthPage, promoted, report, synth

OTHER_REGISTRY = "s" * 64
UNTIL = NOW + timedelta(days=3)
UNTIL_TEXT = "2026-10-22T12:00:00Z"
DAY = timedelta(days=1)
DROP_CODES = ("sudden_drop", "cumulative_drop", "count_change", "coverage_gap")


def run(
    candidate: Snapshot,
    baseline: Baseline | None = None,
    *,
    outcome: SourceOutcome = "complete",
    detail: str = "",
    ledger: LedgerReport | None | Literal["clean"] = "clean",
    problem: str | None = None,
    accept: Sequence[DropAcceptance] = (),
    now: datetime = NOW,
) -> Decision:
    return decide(
        candidate,
        run_outcome=outcome,
        run_detail=detail,
        ledger=report(candidate) if ledger == "clean" else ledger,
        baseline=baseline,
        baseline_problem=problem,
        acceptances=accept,
        window=window_for(now),
        now=now,
    )


def one(
    units: int,
    claims: int | None = None,
    *,
    fetched_at: datetime = NOW,
    notes: Sequence[Reason] = (),
    **page: Any,
) -> Snapshot:
    """A snapshot of the one page ``elections``."""
    return synth(
        pages=(SynthPage("elections", units, claims, **page),), fetched_at=fetched_at, notes=notes
    )


def entry(scope: str, units: int, days: int) -> HistoryEntry:
    """A history entry of ``units`` units and as many claims, ``days`` days before NOW."""
    return HistoryEntry(scope, NOW - timedelta(days=days), units, units)


def drops(d: Decision) -> list[tuple[str, str]]:
    return [(r.code, r.detail) for r in d.reasons if r.code in DROP_CODES]


def history(d: Decision) -> list[tuple[str, int, datetime]]:
    assert d.baseline is not None
    return [(h.scope, h.units_seen, h.fetched_at) for h in d.baseline.history]


def codes(d: Decision) -> list[str]:
    return [r.code for r in d.reasons]


def accept_drop(
    reason: Literal["sudden_drop", "cumulative_drop"] = "cumulative_drop",
    *,
    page: str = "elections",
    year: int | None = None,
    units: int = 30,
    claims: int = 30,
    source: str = "osce",
) -> DropAcceptance:
    return DropAcceptance(source, reason, page, year, units, claims, UNTIL)


def served_as(snapshot: Snapshot, *, fallback: bool) -> tuple[Claim, ...]:
    """The snapshot's claims as ``decide`` stamps them when it serves the snapshot."""
    when = {p.unit_prefix: p.fetched_at for p in snapshot.pages if p.unit_prefix is not None}
    return tuple(
        dataclasses.replace(
            c,
            fetched_at=next(t for prefix, t in when.items() if c.unit_id.startswith(prefix)),
            fallback=fallback,
            snapshot_id=snapshot.snapshot_id,
        )
        for c in snapshot.claims
    )


def test_first_run() -> None:
    early = NOW - timedelta(minutes=5)
    candidate = synth(
        pages=(SynthPage("p1", 3), SynthPage("p2", 2, fetched_at=NOW)), fetched_at=early
    )
    d = run(candidate)
    assert d.source == "osce"
    assert d.candidate is candidate
    assert d.acceptance == "promoted"
    assert d.served is candidate
    assert d.reasons == ()
    assert d.baseline == Baseline(
        candidate, (HistoryEntry("p1", early, 3, 3), HistoryEntry("p2", early, 2, 2)), (), (), True, True
    )
    when = {"osce:p1/": early, "osce:p2/": NOW}
    assert len(d.claims) == 5
    for c in d.claims:
        assert (c.fallback, c.provisional, c.snapshot_id) == (False, False, candidate.snapshot_id)
        assert c.fetched_at == when[c.unit_id[: c.unit_id.index("/") + 1]]
    assert [dataclasses.replace(c, fetched_at=None, snapshot_id=None) for c in d.claims] == list(
        candidate.claims
    )
    assert (d.provisional, d.provisional_units, d.disappeared, d.coverage_gaps) == ((), (), (), ())
    assert d.health == SnapshotHealth("promoted", False, candidate.snapshot_id, early, None, False)

    broken = synth(pages=(SynthPage("p1", 3, outcome="timeout"),), fetched_at=NOW)
    d = run(broken)
    assert d.acceptance == "unavailable"
    assert (d.served, d.claims, d.baseline) == (None, (), None)
    assert d.reasons == (
        Reason("timeout", "p1", page="p1"),
        Reason("unavailable", "no baseline"),
    )
    assert d.health == SnapshotHealth("unavailable", False, None, None, None, False)


def three(*, notes: Sequence[Reason] = (), **outcomes: Any) -> Snapshot:
    return synth(
        pages=tuple(SynthPage(k, 10, outcome=outcomes.get(k, "ok")) for k in ("p1", "p2", "p3")),
        fetched_at=NOW,
        notes=notes,
    )


INVALID: list[Any] = [
    pytest.param(
        {"p3": "unfinished"},
        (),
        {"outcome": "deadline"},
        (),
        False,
        [("deadline", None, "deadline"), ("deadline", "p3", "p3")],
        id="deadline",
    ),
    pytest.param(
        {}, (), {"outcome": "scrape_deadline"}, (), False, [("deadline", None, "scrape_deadline")],
        id="scrape_deadline",
    ),
    pytest.param(
        {},
        (),
        {"outcome": "worker_failed", "detail": "ValueError"},
        (),
        False,
        [("worker_failed", None, "ValueError")],
        id="worker_failed",
    ),
    pytest.param({"p2": "timeout"}, (), {}, (), False, [("timeout", "p2", "p2")], id="p2_timeout"),
    pytest.param(
        {"p2": "challenge_page"}, (), {}, (), False, [("challenge_page", "p2", "p2")],
        id="p2_challenge",
    ),
    pytest.param(
        {},
        (Reason("pagination_incomplete", "p2 repeats p1", page="p2"),),
        {},
        (),
        False,
        [("pagination_incomplete", "p2", "p2 repeats p1")],
        id="p2_repeat",
    ),
    pytest.param(
        {"p1": "layout_not_recognised"},
        (),
        {},
        (),
        False,
        [("layout_not_recognised", "p1", "p1")],
        id="layout",
    ),
    pytest.param(
        {},
        (Reason("required_year_missing", "no heading for 2027", year=2027),),
        {},
        (),
        False,
        [("required_year_missing", None, "no heading for 2027")],
        id="year",
    ),
    pytest.param(
        {}, (), {}, ("30 units discovered, 29 outcomes",), False,
        [("ledger_mismatch", None, "30 units discovered, 29 outcomes")],
        id="ledger",
    ),
    pytest.param(
        {}, (), {}, ("page 'p2': the page has 10 units, the result has 9",), True,
        [("discovery_mismatch", None, "page 'p2': the page has 10 units, the result has 9")],
        id="discovery",
    ),
]


@pytest.mark.parametrize(
    ("outcomes", "notes", "how", "problems", "discovery", "expected"), INVALID
)
def test_invalid_candidates(
    outcomes: dict[str, str],
    notes: tuple[Reason, ...],
    how: dict[str, Any],
    problems: tuple[str, ...],
    discovery: bool,
    expected: list[tuple[str, str | None, str]],
) -> None:
    base = promoted(synth(pages=tuple(SynthPage(k, 10) for k in ("p1", "p2", "p3")), fetched_at=T0))
    candidate = three(notes=notes, **outcomes)
    d = run(candidate, base, ledger=report(candidate, problems, discovery), **how)
    assert d.acceptance == "fallback"
    assert d.served is base.snapshot
    assert d.baseline is base
    errors = [(r.code, r.page, r.detail) for r in d.reasons if REASON_LEVEL[r.code] == "error"]
    assert errors == expected
    assert len(d.claims) == 30
    assert d.claims == served_as(base.snapshot, fallback=True)
    assert all(c.fallback for c in d.claims)
    assert d.health == SnapshotHealth("fallback", True, base.snapshot.snapshot_id, T0, 30, True)


def test_quarantine_health() -> None:
    base = promoted(one(100, fetched_at=T0))
    d = run(one(40), base)
    assert d.acceptance == "quarantined"
    assert d.health == SnapshotHealth("quarantined", True, base.snapshot.snapshot_id, T0, 100, True)


def test_partial_baselines_are_impossible() -> None:
    def two(
        p1: int = 50, p2: int = 50, *, outcome: PageOutcome = "ok", at: datetime = NOW
    ) -> Snapshot:
        return synth(
            pages=(SynthPage("p1", p1), SynthPage("p2", p2, outcome=outcome)),
            fetched_at=at,
        )

    first = two(at=T0)
    b0 = run(first, now=T0).baseline
    assert b0 is not None and b0.snapshot is first

    d = run(two(20, 20), b0)
    assert (d.acceptance, d.served) == ("quarantined", first)
    assert d.baseline is b0

    d = run(two(outcome="timeout"), b0)
    assert d.acceptance == "fallback"
    assert d.baseline is b0

    broken = two()
    bad = report(broken, ("100 units discovered, 99 outcomes",))
    d = run(broken, b0, ledger=bad)
    assert d.acceptance == "fallback"
    assert d.baseline is b0
    d = run(broken, ledger=bad)
    assert d.acceptance == "unavailable"
    assert d.baseline is None

    good = two()
    d = run(good, b0)
    assert d.acceptance == "promoted"
    assert d.baseline is not None and d.baseline.snapshot is good


SUDDEN_40 = accept_drop("sudden_drop", units=40, claims=40)
DROPS: list[Any] = [
    pytest.param(
        (), {"units": 100}, {"units": 49}, (), "quarantined",
        [("sudden_drop", "elections: units fell from 100 to 49 (candidate: units 49, claims 49)")],
        None, id="a",
    ),
    pytest.param((), {"units": 100}, {"units": 50}, (), "promoted", [], None, id="b"),
    pytest.param(
        (), {"units": 100}, {"units": 100, "claims": 49}, (), "quarantined",
        [("sudden_drop", "elections: claims fell from 100 to 49 (candidate: units 100, claims 49)")],
        None, id="c",
    ),
    pytest.param(
        ((100, 2), (60, 1)), {"units": 60}, {"units": 36}, (), "quarantined",
        [(
            "cumulative_drop",
            "elections: units fell to 36, under half the 30-day high of 100 "
            "(candidate: units 36, claims 36)",
        )],
        None, id="d",
    ),
    pytest.param(((100, 31), (60, 1)), {"units": 60}, {"units": 36}, (), "promoted", [], None, id="e"),
    pytest.param(
        ((100, 30), (60, 1)), {"units": 60}, {"units": 36}, (), "quarantined",
        [(
            "cumulative_drop",
            "elections: units fell to 36, under half the 30-day high of 100 "
            "(candidate: units 36, claims 36)",
        )],
        None, id="f",
    ),
    pytest.param(
        (), {"units": 100}, {"units": 0, "outcome": "valid_empty"}, (), "promoted",
        [("count_change", "elections: units fell from 100 to 0; the source lists none")],
        None, id="g",
    ),
    pytest.param(
        (), {"units": 100, "year": 2026, "day": date(2026, 3, 15), "sei": "e"},
        {"units": 30, "year": 2027}, (), "promoted",
        [("count_change", "elections: units fell from 100 to 30; the year changed from 2026 to 2027")],
        None, id="h",
    ),
    pytest.param(
        ((100, 2), (60, 1)), {"units": 60}, {"units": 36}, (accept_drop(),), "promoted",
        [("count_change", f"elections: units fell from 100 to 36; accepted until {UNTIL_TEXT}")],
        [("elections", 36, NOW)], id="i",
    ),
    pytest.param(
        ((100, 2), (60, 1)), {"units": 60}, {"units": 36}, (accept_drop(units=40),), "quarantined",
        [(
            "cumulative_drop",
            "elections: units fell to 36, under half the 30-day high of 100 "
            "(candidate: units 36, claims 36)",
        )],
        None, id="j",
    ),
    pytest.param(
        ((100, 2), (60, 1)), {"units": 60}, {"units": 36}, (accept_drop("sudden_drop"),),
        "quarantined",
        [(
            "cumulative_drop",
            "elections: units fell to 36, under half the 30-day high of 100 "
            "(candidate: units 36, claims 36)",
        )],
        None, id="k",
    ),
    pytest.param(
        (), {"units": 100}, {"units": 49}, (accept_drop("sudden_drop", page="other"),), "quarantined",
        [("sudden_drop", "elections: units fell from 100 to 49 (candidate: units 49, claims 49)")],
        None, id="l",
    ),
    pytest.param(
        ((100, 40), (90, 2)), {"units": 90}, {"units": 90}, (), "promoted", [],
        [("elections", 90, NOW - 2 * DAY), ("elections", 90, NOW)], id="m",
    ),
    pytest.param(
        (), {"units": 100}, {"units": 40, "claims": 0}, (SUDDEN_40,), "quarantined",
        [("sudden_drop", "elections: units fell from 100 to 40 (candidate: units 40, claims 0)")],
        None, id="n",
    ),
    pytest.param(
        (), {"units": 100}, {"units": 40}, (SUDDEN_40,), "promoted",
        [("count_change", f"elections: units fell from 100 to 40; accepted until {UNTIL_TEXT}")],
        None, id="o",
    ),
    pytest.param(
        (), {"units": 100}, {"units": 100, "claims": 0}, (SUDDEN_40,), "quarantined",
        [("sudden_drop", "elections: claims fell from 100 to 0 (candidate: units 100, claims 0)")],
        None, id="p",
    ),
    pytest.param(
        (), {"units": 100}, {"units": 40, "claims": 0},
        (accept_drop("sudden_drop", units=40, claims=0),), "promoted",
        [("count_change", f"elections: units fell from 100 to 40; accepted until {UNTIL_TEXT}")],
        None, id="q",
    ),
    pytest.param(
        (), {"units": 100, "year": 2026}, {"units": 40, "year": 2026},
        (accept_drop("sudden_drop", units=40, claims=40, year=2027),), "quarantined",
        [("sudden_drop", "elections: units fell from 100 to 40 (candidate: units 40, claims 40)")],
        None, id="r",
    ),
    pytest.param(
        (), {"units": 100}, {"units": 40},
        (accept_drop("sudden_drop", units=40, claims=40, source="ipu"),), "quarantined",
        [("sudden_drop", "elections: units fell from 100 to 40 (candidate: units 40, claims 40)")],
        None, id="s",
    ),
]


@pytest.mark.parametrize(
    ("past", "base_page", "cand_page", "accept", "acceptance", "expected", "new_history"), DROPS
)
def test_drops(
    past: tuple[tuple[int, int], ...],
    base_page: dict[str, Any],
    cand_page: dict[str, Any],
    accept: tuple[DropAcceptance, ...],
    acceptance: str,
    expected: list[tuple[str, str]],
    new_history: list[tuple[str, int, datetime]] | None,
) -> None:
    base = promoted(
        synth(pages=(SynthPage("elections", **base_page),), fetched_at=T0),
        history=[entry("elections", units, days) for units, days in past],
    )
    candidate = synth(pages=(SynthPage("elections", **cand_page),), fetched_at=NOW)
    d = run(candidate, base, accept=accept)
    assert d.acceptance == acceptance
    assert drops(d) == expected
    for r in d.reasons:
        if r.code in DROP_CODES:
            assert (r.page, r.year) == ("elections", cand_page.get("year"))
    if acceptance == "quarantined":
        assert d.served is base.snapshot
        assert d.baseline is base
    if new_history is not None:
        assert history(d) == new_history


def test_a_shift_into_ignored_reasons_is_a_warning() -> None:
    base = promoted(one(10, fetched_at=T0))
    d = run(one(10, 4), base)
    assert d.acceptance == "quarantined"
    assert drops(d) == [
        ("sudden_drop", "elections: claims fell from 10 to 4 (candidate: units 10, claims 4)")
    ]
    assert d.served is base.snapshot


def test_claims_falling_while_units_hold_is_a_warning() -> None:
    base = promoted(one(10, fetched_at=T0))
    d = run(one(1, 0, ignored_reason="header_row"), base)
    assert d.acceptance == "quarantined"
    assert drops(d) == [
        ("sudden_drop", "elections: units fell from 10 to 1 (candidate: units 1, claims 0)")
    ]
    d = run(one(10, 0), base)
    assert d.acceptance == "quarantined"
    assert drops(d) == [
        ("sudden_drop", "elections: claims fell from 10 to 0 (candidate: units 10, claims 0)")
    ]


def test_a_new_list_restarts_the_history() -> None:
    def lists(calendar: int, archive: int, at: datetime, year: int = 2027) -> Snapshot:
        return synth(
            pages=(SynthPage("calendar", calendar, year=year), SynthPage("archive", archive)),
            fetched_at=at,
        )

    b0 = promoted(
        lists(100, 100, T0, year=2026), history=(entry("calendar", 100, 1), entry("archive", 100, 1))
    )
    r2 = run(lists(30, 60, NOW), b0)
    assert r2.acceptance == "promoted"
    assert drops(r2) == [
        ("count_change", "calendar: units fell from 100 to 30; the year changed from 2026 to 2027")
    ]
    assert history(r2) == [("archive", 100, NOW - DAY), ("archive", 60, NOW), ("calendar", 30, NOW)]
    assert r2.baseline is not None

    later = NOW + DAY
    r3 = run(lists(30, 60, later), r2.baseline, now=later)
    assert r3.acceptance == "promoted"
    assert drops(r3) == []
    q = run(lists(30, 36, later), r2.baseline, now=later)
    assert q.acceptance == "quarantined"
    assert drops(q) == [(
        "cumulative_drop",
        "archive: units fell to 36, under half the 30-day high of 100 (candidate: units 36, claims 36)",
    )]

    assert r3.baseline is not None
    r4 = run(lists(20, 60, NOW + 2 * DAY), r3.baseline, now=NOW + 2 * DAY)
    assert r4.acceptance == "promoted"
    assert drops(r4) == []
    assert r4.baseline is not None
    r5 = run(lists(14, 60, NOW + 3 * DAY), r4.baseline, now=NOW + 3 * DAY)
    assert r5.acceptance == "quarantined"
    assert drops(r5) == [(
        "cumulative_drop",
        "calendar: units fell to 14, under half the 30-day high of 30 (candidate: units 14, claims 14)",
    )]

    e0 = promoted(one(100, fetched_at=T0), history=(entry("elections", 100, 1),))
    e1 = run(one(0, outcome="valid_empty"), e0)
    assert e1.acceptance == "promoted"
    assert drops(e1) == [
        ("count_change", "elections: units fell from 100 to 0; the source lists none")
    ]
    assert history(e1) == [("elections", 0, NOW)]
    assert e1.baseline is not None
    e2 = run(one(10, fetched_at=later), e1.baseline, now=later)
    assert e2.acceptance == "promoted"
    assert drops(e2) == []


AW = "aweb:calendar"
GAMBIA = mk(
    f"{AW}/r1",
    place_id="iso:GM",
    place_raw="Gambia",
    institution="iso:GM/president",
    office_class="head_of_state",
    office_label="President",
    span=day(2026, 12, 5),
    date_text="5 December 2026",
)
MARCH = (
    mk(f"{AW}/r2", place_id="iso:BJ", place_raw="Benin", institution=None,
       span=day(2026, 3, 8), date_text="8 March 2026"),
    mk(f"{AW}/r3", place_id="iso:SN", place_raw="Senegal", institution=None,
       span=day(2026, 3, 22), date_text="22 March 2026"),
)
FEBRUARY = (
    mk(f"{AW}/r1", place_id="iso:EC", place_raw="Ecuador", institution=None,
       span=day(2027, 2, 7), date_text="7 February 2027"),
    mk(f"{AW}/r2", place_id="iso:CR", place_raw="Costa Rica", institution=None,
       span=day(2027, 2, 14), date_text="14 February 2027"),
)
R1 = datetime(2027, 1, 2, 6, tzinfo=UTC)


def aweb(
    claims: tuple[Claim, ...], year: int, at: datetime, outcome: PageOutcome = "ok"
) -> Snapshot:
    page = SynthPage("calendar", claims=claims, year=year, outcome=outcome)
    return synth(source="aweb", pages=(page,), fetched_at=at)


def gap_reasons(d: Decision) -> list[Reason]:
    return [r for r in d.reasons if r.code == "coverage_gap"]


def test_aweb_rollover_keeps_december_events() -> None:
    b0 = promoted(aweb((GAMBIA, *MARCH), 2026, datetime(2026, 12, 20, 6, tzinfo=UTC)))
    gap = CoverageGap("calendar", 2026, 2027, R1, (GAMBIA,))
    reason = Reason(
        "coverage_gap",
        "calendar: the 2026 list was replaced by 2027; in-window claims no longer listed: 1",
        page="calendar",
        year=2027,
        since=R1,
    )

    d1 = run(aweb(FEBRUARY, 2027, R1), b0, now=R1)
    assert d1.acceptance == "promoted"
    assert d1.coverage_gaps == (gap,)
    assert gap_reasons(d1) == [reason]
    assert d1.baseline is not None and d1.baseline.coverage_gaps == (gap,)
    assert len(d1.claims) == 2
    assert all(c.place_id != "iso:GM" for c in d1.claims)

    at = R1 + DAY
    d2 = run(aweb(FEBRUARY, 2027, at), d1.baseline, now=at)
    assert d2.acceptance == "promoted"
    assert [c for c in codes(d2) if c in ("sudden_drop", "cumulative_drop", "count_change")] == []
    assert gap_reasons(d2) == [reason]
    assert d2.baseline is not None and d2.baseline.coverage_gaps == (gap,)

    at = R1 + 2 * DAY
    d3 = run(aweb((), 2027, at, outcome="timeout"), d2.baseline, now=at)
    assert d3.acceptance == "fallback"
    assert gap_reasons(d3) == [reason]
    assert d3.coverage_gaps == (gap,)
    assert d3.baseline is d2.baseline

    again = dataclasses.replace(
        GAMBIA, unit_id=f"{AW}/r3", claim_id=f"{AW}/r3#0", date_status="confirmed"
    )
    assert same_listing(again, (GAMBIA,)) and not unchanged(again, (GAMBIA,))
    d = run(aweb((*FEBRUARY, again), 2027, at), d2.baseline, now=at)
    assert d.acceptance == "promoted"
    assert gap_reasons(d) == []
    assert d.coverage_gaps == ()
    assert d.baseline is not None and d.baseline.coverage_gaps == ()
    d = run(aweb((*FEBRUARY, again), 2027, R1), b0, now=R1)
    assert d.acceptance == "promoted"
    assert gap_reasons(d) == []
    assert d.baseline is not None and d.baseline.coverage_gaps == ()

    feb1 = datetime(2027, 2, 1, 6, tzinfo=UTC)
    d = run(aweb(FEBRUARY, 2027, feb1), d2.baseline, now=feb1)
    assert d.acceptance == "promoted"
    assert gap_reasons(d) == []
    assert d.baseline is not None and d.baseline.coverage_gaps == ()


def test_a_hand_edited_gap_scope_never_crashes() -> None:
    """R8: the coverage_gap detail is cut to 300 characters, whatever the stored scope."""
    long_scope = "x" * 400
    b0 = promoted(aweb((GAMBIA, *MARCH), 2026, datetime(2026, 12, 20, 6, tzinfo=UTC)))
    edited = dataclasses.replace(
        b0, coverage_gaps=(CoverageGap(long_scope, 2026, 2027, R1, (GAMBIA,)),)
    )
    d = run(aweb(FEBRUARY, 2027, R1), edited, now=R1)
    (reason,) = [r for r in gap_reasons(d) if r.page == long_scope]
    assert len(reason.detail) == 300
    assert reason.detail.startswith("x" * 100)


def test_eisa_january_without_a_new_table_keeps_december() -> None:
    december = datetime(2026, 12, 15, 6, tzinfo=UTC)
    january = datetime(2027, 1, 3, 6, tzinfo=UTC)

    def eisa(at: datetime, note: Reason) -> Snapshot:
        pages = (SynthPage("calendar"), SynthPage("y2026", 22, year=2026))
        return synth(source="eisa", pages=pages, fetched_at=at, notes=(note,))

    heading = "no heading 'eisa african election calendar 2027'"
    base = promoted(eisa(december, Reason("not_published_yet", heading, year=2027)))
    d = run(eisa(january, Reason("required_year_missing", heading, year=2027)), base, now=january)
    assert d.acceptance == "fallback"
    assert d.served is base.snapshot
    assert len(d.claims) == 22
    assert d.claims == tuple(
        dataclasses.replace(
            c, fetched_at=december, fallback=True, snapshot_id=base.snapshot.snapshot_id
        )
        for c in base.snapshot.claims
    )
    assert d.health.served_fetched_at == december


def test_a_disappeared_year_table_is_an_error() -> None:
    note = Reason("not_published_yet", "no heading 'eisa african election calendar 2027'", year=2027)
    missing = Reason(
        "required_year_missing", "2027 was published before and is now missing", year=2027
    )
    base = promoted(
        synth(
            source="eisa",
            pages=(SynthPage("y2026", 10, year=2026), SynthPage("y2027", 5, year=2027)),
            fetched_at=T0,
        )
    )
    candidate = synth(
        source="eisa", pages=(SynthPage("y2026", 10, year=2026),), notes=(note,), fetched_at=NOW
    )
    d = run(candidate, base)
    assert d.acceptance == "fallback"
    assert [r for r in d.reasons if r.year == 2027] == [missing]

    wiki_base = promoted(
        synth(source="wikipedia", pages=(SynthPage("national-2027", 5, year=2027),), fetched_at=T0)
    )
    wiki = synth(
        source="wikipedia",
        pages=(SynthPage("national-2027", outcome="not_published_yet", year=2027),),
        fetched_at=NOW,
    )
    d = run(wiki, wiki_base)
    assert d.acceptance == "fallback"
    assert d.reasons[0] == dataclasses.replace(missing, page="national-2027")

    without = promoted(
        synth(source="eisa", pages=(SynthPage("y2026", 10, year=2026),), fetched_at=T0)
    )
    d = run(candidate, without)
    assert d.acceptance == "promoted"
    assert [r for r in d.reasons if r.year == 2027] == [note]


A = mk("osce:p1/r1", source_event_id="osce:1")
B = mk("osce:p1/r2", span=day(2026, 11, 22), date_text="22 November 2026")
C = cl("osce:p2/r1", PE)
A2 = mk("osce:p1/r1", source_event_id="osce:1", span=day(2026, 11, 16), date_text="16 November 2026")
D = cl("osce:p1/r3", CH)
P1_AT = NOW + timedelta(minutes=1)


def unparsed(uid: str, text: str, relevance: Relevance = "unknown") -> InputUnit:
    return InputUnit(uid, "osce", text, "unparsed", "no date", relevance)


def provisional_as(candidate: Snapshot, *claims: Claim) -> tuple[Claim, ...]:
    return tuple(
        dataclasses.replace(
            c, fetched_at=P1_AT, snapshot_id=candidate.snapshot_id, provisional=True
        )
        for c in claims
    )


def test_provisional_changes() -> None:
    served_unit = unparsed("osce:p1/u1", "Gambia:  vote on 5 December")
    base = promoted(
        synth(
            pages=(SynthPage("p1", claims=(A, B), extra=(served_unit,)), SynthPage("p2", claims=(C,))),
            fetched_at=T0,
        )
    )

    def candidate(*p1: Claim, p2: SynthPage | None = None, extra: tuple[InputUnit, ...] = ()) -> Snapshot:
        return synth(
            pages=(
                SynthPage("p1", claims=p1, extra=extra, fetched_at=P1_AT),
                p2 or SynthPage("p2", outcome="timeout"),
            ),
            fetched_at=NOW,
        )

    cand = candidate(A2, B, D)
    d = run(cand, base)
    assert d.acceptance == "fallback"
    expected = provisional_as(cand, A2, D)
    assert d.provisional == expected
    assert d.claims == served_as(base.snapshot, fallback=True) + expected
    assert Reason("provisional_changes", "new or changed claims from an incomplete fetch: 2") in d.reasons
    assert same_listing(A2, base.snapshot.claims)
    assert not unchanged(A2, base.snapshot.claims)

    postponed = dataclasses.replace(A, status_claim="postponed")
    cand = candidate(postponed, B)
    assert run(cand, base).provisional == provisional_as(cand, postponed)

    with_id = dataclasses.replace(B, source_event_id="osce:9")
    cand = candidate(A, with_id)
    assert run(cand, base).provisional == provisional_as(cand, with_id)

    cand = candidate(A2, B, D)
    assert run(cand, base, ledger=report(cand, ("30 units discovered, 29 outcomes",))).provisional == ()
    assert run(cand, base, ledger=report(cand, ("p1 differs",), discovery=True)).provisional == ()

    changed_c = dataclasses.replace(C, date_status="confirmed")
    cand = candidate(A, B, p2=SynthPage("p2", claims=(changed_c,), outcome="timeout"))
    d = run(cand, base)
    assert d.acceptance == "fallback"
    assert d.provisional == ()

    ten = promoted(
        synth(pages=(SynthPage("p1", claims=(A, B)), SynthPage("p2", 10, claims=(C,))), fetched_at=T0)
    )
    cand = synth(
        pages=(
            SynthPage("p1", claims=(A2, B, D), fetched_at=P1_AT),
            SynthPage("p2", 4, claims=(changed_c,), fetched_at=P1_AT),
        ),
        fetched_at=NOW,
    )
    d = run(cand, ten)
    assert d.acceptance == "quarantined"
    assert d.provisional == provisional_as(cand, A2, D, changed_c)

    same = synth(pages=(SynthPage("p1", claims=(A, B)), SynthPage("p2", claims=(C,))), fetched_at=NOW)
    d = run(same, base)
    assert d.acceptance == "promoted"
    assert d.provisional == ()

    new_unit = unparsed("osce:p1/u2", "Benin: vote in 2027")
    respaced = unparsed("osce:p1/u3", "Gambia: vote on 5  December")
    early = unparsed("osce:p1/u4", "Togo: vote in 2025", "before_window")
    stray = unparsed("osce:p2/u1", "Mali: vote soon")
    cand = candidate(
        A, B, p2=SynthPage("p2", outcome="timeout", extra=(stray,)), extra=(new_unit, respaced, early)
    )
    d = run(cand, base)
    assert d.acceptance == "fallback"
    assert d.provisional_units == (new_unit,)
    assert run(cand, base, ledger=report(cand, ("units differ",))).provisional_units == ()


def test_an_unchanged_partial_claim_is_not_provisional() -> None:
    base = promoted(
        synth(pages=(SynthPage("p1", claims=(A, B)), SynthPage("p2", claims=(C,))), fetched_at=T0)
    )
    cand = synth(
        pages=(SynthPage("p1", claims=(A, B)), SynthPage("p2", outcome="timeout")), fetched_at=NOW
    )
    d = run(cand, base)
    assert d.acceptance == "fallback"
    assert d.provisional == ()
    assert "provisional_changes" not in codes(d)


A_DISTRICT = mk(
    "osce:p1/r1", source_event_id="osce:1", date_status="tentative", office_label="District 3"
)
CHANGES: list[Any] = [
    pytest.param({"date_status": "confirmed"}, True, id="certainty"),
    # The brief's "voting_period" is A's own value (mk's default); the ruling is "unknown".
    pytest.param({"date_meaning": "unknown"}, True, id="meaning"),
    pytest.param({"level": "subnational"}, True, id="level"),
    pytest.param({"office_label": "District 4"}, True, id="number"),
    pytest.param({"place_id": "iso:NO"}, True, id="place"),
    pytest.param({"institution": "iso:SE/sametinget"}, True, id="institution"),
    pytest.param({"previous_date_text": "1 November 2026"}, True, id="rescheduled"),
    pytest.param({"link": "https://example.test/other"}, False, id="link"),
    pytest.param({"date_text": "15 Nov 2026", "place_raw": "Kingdom of Sweden"}, False, id="wording"),
    pytest.param({"office_label": "district  3"}, False, id="spacing"),
    pytest.param({"unit_id": "osce:p1/r2", "claim_id": "osce:p1/r2#0"}, False, id="position"),
]


@pytest.mark.parametrize("p2", ["timeout", "drop"])
@pytest.mark.parametrize(("changes", "is_provisional"), CHANGES)
def test_unchanged_compares_the_whole_claim(
    changes: dict[str, Any], is_provisional: bool, p2: str
) -> None:
    changed = dataclasses.replace(A_DISTRICT, **changes)
    base = promoted(
        synth(pages=(SynthPage("p1", claims=(A_DISTRICT,)), SynthPage("p2", 10)), fetched_at=T0)
    )
    second = SynthPage("p2", outcome="timeout") if p2 == "timeout" else SynthPage("p2", 4)
    d = run(synth(pages=(SynthPage("p1", claims=(changed,)), second), fetched_at=NOW), base)
    assert d.acceptance == ("fallback" if p2 == "timeout" else "quarantined")
    assert [c.claim_id for c in d.provisional] == ([changed.claim_id] if is_provisional else [])
    assert unchanged(changed, base.snapshot.claims) is not is_provisional
    assert same_listing(changed, base.snapshot.claims)


def test_stamped_fallback_claims_reach_the_merge() -> None:
    raw, result = fixture_results()["osce"]
    snapshot = build_snapshot(
        raw,
        result,
        parser_version="2.0",
        registry_version=REGISTRY,
        years=window_for(FIXTURE_NOW).years,
    )
    page_time = snapshot.pages[0].fetched_at
    cut = synth(pages=(SynthPage("elections", outcome="timeout"),), fetched_at=FIXTURE_NOW)
    d = run(cut, promoted(snapshot), now=FIXTURE_NOW)
    assert d.acceptance == "fallback"
    out = merge(d.claims, now=FIXTURE_NOW, places=PlaceRegistry.load())
    sources = [
        s.claim
        for card in out.cards
        for child in card.children
        for s in child.sources
        if s.claim.source == "osce"
    ]
    assert sources
    assert all(c.fallback and c.fetched_at == page_time for c in sources)


def test_fallback_age_is_never_refreshed() -> None:
    base = promoted(one(100, fetched_at=T0))
    week = timedelta(days=7)
    for at, stale in ((T0 + week, False), (T0 + week + timedelta(seconds=1), True)):
        d = run(one(100, outcome="timeout", fetched_at=at), base, now=at)
        assert d.acceptance == "fallback"
        assert d.baseline is base
        assert d.health.served_fetched_at == T0
        assert all(c.fetched_at == T0 for c in d.claims)
        expected = [Reason("fallback_stale", "serving data fetched 2026-10-01T06:00:00Z")]
        assert [r for r in d.reasons if r.code == "fallback_stale"] == (expected if stale else [])


def test_parser_version_change() -> None:
    def version(parser: str, units: int, at: datetime) -> Snapshot:
        return synth(pages=(SynthPage("elections", units),), parser_version=parser, fetched_at=at)

    old = promoted(version("1.4", 100, T0), history=(entry("elections", 100, 1),))
    d = run(version("2.0", 40, NOW), old)
    assert d.acceptance == "promoted"
    assert d.health.comparable is False
    assert drops(d) == []
    assert history(d) == [("elections", 40, NOW)]

    minor = promoted(version("2.0", 100, T0), history=(entry("elections", 100, 1),))
    d = run(version("2.3", 40, NOW), minor)
    assert d.acceptance == "quarantined"
    assert d.health.comparable is True
    assert "sudden_drop" in codes(d)


REGISTRY_INFO = Reason("count_change", "baseline.json is from another registry version; it is never served")
UNAVAILABLE = Reason("unavailable", "baseline.json is from another registry version")


def other_registry() -> Baseline:
    snapshot = synth(pages=(SynthPage("elections", 100),), registry=OTHER_REGISTRY, fetched_at=T0)
    return promoted(snapshot, history=(entry("elections", 100, 1),))


REGISTRY_ROWS: list[Any] = [
    pytest.param({"units": 100}, (), "promoted", (REGISTRY_INFO,), id="success"),
    pytest.param(
        {"units": 40},
        (),
        "unavailable",
        (
            REGISTRY_INFO,
            Reason(
                "sudden_drop",
                "elections: units fell from 100 to 40 (candidate: units 40, claims 40)",
                page="elections",
            ),
            UNAVAILABLE,
        ),
        id="unit_drop",
    ),
    pytest.param(
        {"units": 100, "claims": 40},
        (),
        "unavailable",
        (
            REGISTRY_INFO,
            Reason(
                "sudden_drop",
                "elections: claims fell from 100 to 40 (candidate: units 100, claims 40)",
                page="elections",
            ),
            UNAVAILABLE,
        ),
        id="claim_only_drop",
    ),
    pytest.param(
        {"units": 100, "outcome": "timeout"},
        (),
        "unavailable",
        (Reason("timeout", "elections", page="elections"), REGISTRY_INFO, UNAVAILABLE),
        id="invalid",
    ),
    pytest.param(
        {"units": 40},
        (SUDDEN_40,),
        "promoted",
        (
            REGISTRY_INFO,
            Reason(
                "count_change",
                f"elections: units fell from 100 to 40; accepted until {UNTIL_TEXT}",
                page="elections",
            ),
        ),
        id="accepted_drop",
    ),
]


@pytest.mark.parametrize(("listed", "accept", "acceptance", "reasons"), REGISTRY_ROWS)
def test_registry_change(
    listed: dict[str, Any],
    accept: tuple[DropAcceptance, ...],
    acceptance: str,
    reasons: tuple[Reason, ...],
) -> None:
    b0 = other_registry()
    candidate = synth(pages=(SynthPage("elections", **listed),), fetched_at=NOW)
    d = run(candidate, b0, accept=accept)
    assert d.acceptance == acceptance
    assert d.health.comparable is True
    assert d.reasons == reasons
    if acceptance == "unavailable":
        assert (d.served, d.claims, d.provisional, d.provisional_units) == (None, (), (), ())
        assert d.baseline is b0
        assert d.health == SnapshotHealth("unavailable", False, None, None, 100, True)
        return
    assert d.served is candidate
    assert d.claims and all(c.snapshot_id == candidate.snapshot_id for c in d.claims)
    assert d.baseline is not None and d.baseline.snapshot is candidate
    assert d.baseline.snapshot.registry_version == REGISTRY
    if accept:
        assert history(d) == [("elections", 40, NOW)]
    else:
        assert history(d) == [("elections", 100, NOW - DAY), ("elections", 100, NOW)]


def test_registry_change_recovery_and_unaffected() -> None:
    b0 = other_registry()
    dropped = run(one(40), b0)
    assert dropped.acceptance == "unavailable"
    assert dropped.baseline is b0
    candidate = one(100)
    d = run(candidate, dropped.baseline)
    assert d.acceptance == "promoted"
    assert d.served is candidate
    assert "unavailable" not in codes(d)

    same = promoted(one(100, fetched_at=T0))
    d = run(one(40), same)
    assert d.acceptance == "quarantined"
    assert d.served is same.snapshot
    assert d.claims and all(c.fallback for c in d.claims)
    assert REGISTRY_INFO not in d.reasons
    assert "count_change" not in codes(d)


def test_a_corrupt_baseline_is_loud() -> None:
    problem = "baseline.json is corrupt: not JSON"
    d = run(one(100), problem=problem)
    assert d.acceptance == "promoted"
    assert d.health.comparable is False
    assert d.reasons == (Reason("ledger_mismatch", problem),)

    d = run(one(100, outcome="timeout"), problem=problem)
    assert d.acceptance == "unavailable"
    assert d.reasons == (
        Reason("timeout", "elections", page="elections"),
        Reason("ledger_mismatch", problem),
        Reason("unavailable", "baseline.json is corrupt"),
    )
    assert run(one(100), problem="x" * 400).reasons == (Reason("ledger_mismatch", "x" * 300),)


EG = "electionguide:upcoming"
G = mk(
    f"{EG}/r1",
    source_event_id="electionguide:5259",
    place_id="iso:GM",
    place_raw="Gambia",
    institution="iso:GM/president",
    office_class="head_of_state",
    office_label="President",
)
OLD = mk(f"{EG}/r2", source_event_id="electionguide:5000", span=day(2026, 9, 1), date_text="1 September 2026")
YEARLY = mk(f"{EG}/r3", source_event_id="electionguide:6000", span=year(2026), date_text="2026")
OTHERS = tuple(
    mk(f"{EG}/r{i}", source_event_id=f"electionguide:{7000 + i}", place_id="iso:FR")
    for i in (1, 2, 3)
)


def listing(*claims: Claim, at: datetime, outcome: PageOutcome = "ok") -> Snapshot:
    page = SynthPage("upcoming", claims=claims, outcome=outcome)
    return synth(source="electionguide", pages=(page,), fetched_at=at)


def test_disappeared_units() -> None:
    texts = ((G.unit_id, "Gambia: Presidential"),)
    page = SynthPage("upcoming", claims=(G, OLD, YEARLY), texts=texts)
    b0 = promoted(synth(source="electionguide", pages=(page,), fetched_at=T0))
    gone = Disappeared(
        "electionguide:5259",
        G.unit_id,
        "Gambia: Presidential",
        "15 November 2026",
        date(2026, 11, 15),
        date(2026, 11, 15),
        G.link,
        NOW,
    )
    shown = Reason("units_disappeared", "listed events no longer listed: 1")

    d = run(listing(*OTHERS, at=NOW), b0)
    assert d.acceptance == "promoted"
    assert d.disappeared == (gone,)
    assert shown in d.reasons
    assert d.baseline is not None and d.baseline.disappeared == (gone,)
    b1 = d.baseline

    at = NOW + 6 * DAY
    d = run(listing(*OTHERS, at=at), b1, now=at)
    assert d.acceptance == "promoted"
    assert d.disappeared == (gone,)
    assert d.baseline is not None and d.baseline.disappeared == (gone,)

    at = NOW + 7 * DAY
    d = run(listing(*OTHERS, at=at), b1, now=at)
    assert d.disappeared == ()
    assert "units_disappeared" not in codes(d)
    assert d.baseline is not None and d.baseline.disappeared == ()

    at = NOW + DAY
    back = dataclasses.replace(G, unit_id=f"{EG}/r9", claim_id=f"{EG}/r9#0")
    d = run(listing(*OTHERS, back, at=at), b1, now=at)
    assert d.acceptance == "promoted"
    assert d.disappeared == ()

    at = datetime(2026, 11, 16, 12, tzinfo=UTC)
    d = run(listing(*OTHERS, at=at), b1, now=at)
    assert d.disappeared == ()

    at = NOW + DAY
    d = run(listing(at=at, outcome="timeout"), b1, now=at)
    assert d.acceptance == "fallback"
    assert d.disappeared == (gone,)
    assert shown in d.reasons
    assert d.baseline is b1

    recent = promoted(
        b1.snapshot, disappeared=(dataclasses.replace(gone, since=datetime(2026, 11, 12, tzinfo=UTC)),)
    )
    on_the_day = datetime(2026, 11, 15, 12, tzinfo=UTC)
    d = run(listing(at=on_the_day, outcome="timeout"), recent, now=on_the_day)
    assert len(d.disappeared) == 1
    after = datetime(2026, 11, 16, 12, tzinfo=UTC)
    d = run(listing(at=after, outcome="timeout"), recent, now=after)
    assert d.acceptance == "fallback"
    assert d.disappeared == ()


def gone_event(number: int) -> Disappeared:
    return Disappeared(
        f"electionguide:{number}",
        f"{EG}/r{number}",
        "text",
        "15 November 2026",
        date(2026, 11, 15),
        date(2026, 11, 15),
        G.link,
        NOW - DAY,
    )


def test_one_event_id_with_two_baseline_claims_gives_one_disappeared() -> None:
    """Two claims of one ``source_event_id`` give one record: the first, in the baseline's order."""
    twin = dataclasses.replace(G, unit_id=f"{EG}/r8", claim_id=f"{EG}/r8#0")
    texts = ((G.unit_id, "first"), (twin.unit_id, "second"))
    page = SynthPage("upcoming", claims=(G, twin, OLD), texts=texts)
    b0 = promoted(synth(source="electionguide", pages=(page,), fetched_at=T0))
    d = run(listing(*OTHERS, at=NOW), b0)
    assert d.acceptance == "promoted"
    (gone,) = d.disappeared
    assert (gone.source_event_id, gone.unit_id, gone.text) == (
        "electionguide:5259",
        G.unit_id,
        "first",
    )
    assert d.baseline is not None and d.baseline.disappeared == (gone,)
    # carried records are folded the same way
    stored = promoted(b0.snapshot, disappeared=(gone, dataclasses.replace(gone, unit_id=twin.unit_id)))
    d = run(listing(*OTHERS, at=NOW), stored)
    assert d.disappeared == (gone,)
    d = run(listing(at=NOW, outcome="timeout"), stored)  # and when the baseline is served
    assert d.acceptance == "fallback"
    assert d.disappeared == (gone,)


def test_gaps_and_disappeared_are_sorted() -> None:
    later, earlier = gone_event(9), gone_event(1)
    base = listing(*OTHERS, at=T0)
    stored = promoted(base, disappeared=(later, earlier))
    wanted = (earlier, later)
    assert run(listing(*OTHERS, at=NOW), stored).disappeared == wanted  # promoted
    fallback = run(listing(at=NOW, outcome="timeout"), stored)
    assert fallback.acceptance == "fallback"
    assert fallback.disappeared == wanted

    b0 = promoted(aweb((GAMBIA, *MARCH), 2026, datetime(2026, 12, 20, 6, tzinfo=UTC)))
    unsorted_gaps = (
        CoverageGap("calendar", 2026, 2027, R1 + DAY, (GAMBIA,)),
        CoverageGap("calendar", 2026, 2027, R1, (GAMBIA,)),
    )
    edited = dataclasses.replace(b0, coverage_gaps=unsorted_gaps)
    d = run(aweb(FEBRUARY, 2027, R1), edited, now=R1)
    assert [g.since for g in d.coverage_gaps] == [R1, R1, R1 + DAY]  # the new gap joins the two
    served = promoted(
        aweb(MARCH, 2026, datetime(2026, 12, 20, 6, tzinfo=UTC)), coverage_gaps=unsorted_gaps
    )
    d = run(aweb((), 2027, R1, outcome="timeout"), served, now=R1)
    assert d.acceptance == "fallback"
    assert d.coverage_gaps == (unsorted_gaps[1], unsorted_gaps[0])


def test_a_coverage_gap_is_promoted() -> None:
    note = Reason("coverage_gap", "dated text beside the table: 5 December 2026")
    d = run(one(100, notes=(note,)), promoted(one(100, fetched_at=T0)))
    assert d.acceptance == "promoted"
    assert d.reasons == (note,)


def test_page_count_changes() -> None:
    def ndi(
        pages: int, each: int, other: int, at: datetime, outcome: PageOutcome = "ok"
    ) -> Snapshot:
        listed = tuple(SynthPage(f"p{i}", each, scope="pages") for i in range(pages))
        last = SynthPage("x", other, outcome=outcome)
        return synth(source="ndi", pages=(*listed, last), fetched_at=at)

    base = promoted(ndi(5, 10, 10, T0))
    d = run(ndi(4, 5, 4, NOW), base)
    assert d.acceptance == "quarantined"
    assert [r for r in d.reasons if r.code in DROP_CODES] == [
        Reason(
            "sudden_drop",
            "pages: units fell from 50 to 20 (candidate: units 20, claims 20)",
            page="pages",
        ),
        Reason("count_change", "pages: 5 pages, now 4", page="pages"),
        Reason("sudden_drop", "x: units fell from 10 to 4 (candidate: units 4, claims 4)", page="x"),
    ]

    d = run(ndi(4, 13, 10, NOW), base)
    assert d.acceptance == "promoted"
    assert d.reasons == (Reason("count_change", "pages: 5 pages, now 4", page="pages"),)

    d = run(ndi(4, 13, 10, NOW, outcome="timeout"), base)
    assert d.acceptance == "fallback"
    assert "count_change" not in codes(d)


def test_scope_counts() -> None:
    snapshot = synth(
        pages=(
            SynthPage("a1", 3, 2, scope="a", year=2026),
            SynthPage("a2", 2, scope="a", year=2026),
            SynthPage("b1", 1, scope="b", year=2026),
            SynthPage("b2", 0, scope="b", year=2027, outcome="valid_empty"),
            SynthPage("c1", 0, scope="c", year=2026, outcome="valid_empty"),
            SynthPage("c2", 0, scope="c", outcome="valid_empty"),
            SynthPage("d", 4, outcome="timeout"),
        ),
        fetched_at=NOW,
    )
    assert scope_counts(snapshot) == {
        "a": ScopeCount(units=5, claims=4, pages=2, year=2026, all_valid_empty=False),
        "b": ScopeCount(units=1, claims=1, pages=2, year=None, all_valid_empty=False),
        "c": ScopeCount(units=0, claims=0, pages=2, year=None, all_valid_empty=True),
        "d": ScopeCount(units=0, claims=0, pages=1, year=None, all_valid_empty=False),
    }
    assert list(scope_counts(snapshot)) == ["a", "b", "c", "d"]


@pytest.mark.parametrize("outcome", ["complete", "deadline", "scrape_deadline"])
def test_no_ledger_is_only_for_a_parse_failure(outcome: SourceOutcome) -> None:
    candidate = one(100)
    with pytest.raises(ValueError, match="no ledger report"):
        run(candidate, ledger=None, outcome=outcome)
    assert run(candidate, ledger=None, outcome="worker_failed", detail="parse: X").acceptance == (
        "unavailable"
    )


def test_a_baseline_of_another_source_is_a_programming_error() -> None:
    baseline = promoted(listing(*OTHERS, at=T0))  # electionguide
    with pytest.raises(ValueError, match="baseline is of 'electionguide', the candidate of 'osce'"):
        run(one(100), baseline)
