"""Severity, acknowledgements and the verdict (spec §9.4, §9.6; P91; S4-T14, V2-T06)."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from elections_calendar import ledger
from elections_calendar.health import (
    Acknowledgement,
    HealthState,
    MatchDiagnostic,
    acknowledge,
    drop_acceptances,
    severity,
    source_reasons,
    unacknowledged,
    verdict,
)
from elections_calendar.model import REASON_STAGE, AttentionItem, DropAcceptance, Reason
from elections_calendar.snapshots import (
    Decision,
    Snapshot,
    build_snapshot,
    decide,
    unit_items,
)
from elections_calendar.sources.base import PARSER_VERSION, Registries
from elections_calendar.sources.ipu import Ipu
from elections_calendar.window import window_for
from tests.support.claims import day, mk
from tests.support.feed import fixture_snapshot
from tests.support.known_issues import NOW, entry, issues, ts
from tests.support.pages import raw_pages
from tests.support.pages import result as fetched
from tests.support.snapshots import SynthPage, promoted, report, synth
from tests.support.unit_items import item

CLEAN = HealthState(())
NO_MATCH = MatchDiagnostic(0, 0, 0, 0, False)
HOUR = timedelta(hours=1)
HTTP = Reason("http_error", "elections", page="elections")
IPU_PAGE = "{stage: fetch, year: null, page: elections}"
OSCE_PAGE = "{stage: snapshot, year: null, page: elections}"
T0 = NOW - timedelta(days=1)


def test_severity() -> None:
    info = Reason("count_change", "x")
    warning = Reason("coverage_gap", "x")
    error = Reason("http_error", "x")
    assert severity(()) == "ok"
    assert severity((info, Reason("not_published_yet"))) == "ok"
    assert severity((info, warning)) == "warning"
    assert severity((warning, info)) == "warning"
    assert severity((warning, error)) == "error"
    assert severity((error, warning)) == "error"


def test_unacknowledged() -> None:
    since = NOW - HOUR
    reason = Reason("coverage_gap", "x", page="calendar", year=2027, since=since)

    def ack(**changes: object) -> Acknowledgement:
        values: dict[str, object] = dict(
            code="coverage_gap", until=NOW, stage="parse", year=2027, page="calendar", since=since
        )
        values.update(changes)
        return Acknowledgement(**values)  # type: ignore[arg-type]

    assert unacknowledged((reason,), (ack(),)) == ()
    for other in (
        ack(code="unparsed_relevant"),
        ack(stage="snapshot"),
        ack(year=2026),
        ack(year=None),
        ack(page="archive"),
        ack(page=None),
        ack(since=since + HOUR),
        ack(since=None),
    ):
        assert unacknowledged((reason,), (other,)) == (reason,)
    # Information is never open, and the order of the reasons is kept.
    info = Reason("count_change", "y")
    error = Reason("http_error", "z")
    assert unacknowledged((error, info, reason), ()) == (error, reason)
    assert unacknowledged((error, info, reason), (ack(),)) == (error,)


def test_verdict() -> None:
    assert verdict(()) == "green"
    assert verdict((Reason("count_change"),)) == "green"
    assert verdict((Reason("coverage_gap"),)) == "red"
    assert verdict((Reason("http_error"),)) == "red"


def codes(reasons: Sequence[Reason]) -> list[str]:
    return [r.code for r in reasons]


def judged(
    source: str, decision: Decision, known: object, now: datetime = NOW, units: bool = True
) -> tuple[tuple[Reason, ...], tuple[AttentionItem, ...], tuple[Acknowledgement, ...]]:
    """The source's reasons and acknowledgements; ``units=False`` leaves out the unit items."""
    items = unit_items(decision) if units else ()
    reasons = source_reasons(decision.reasons, items, NO_MATCH, CLEAN)
    acks = acknowledge(source, reasons, items, known, CLEAN, now)  # type: ignore[arg-type]
    return reasons, items, acks


def ipu_failed() -> Decision:
    """IPU with its page ``elections`` failing, the fixture snapshot as the baseline."""
    window = window_for(NOW)
    adapter = Ipu()
    request = adapter.requests(window)[0]
    raw = raw_pages("ipu", [(request, fetched(b"", url=request.url, outcome="http_error", status=500))])
    parsed = adapter.parse(raw, window, Registries.load())
    candidate = build_snapshot(
        raw,
        parsed,
        parser_version=PARSER_VERSION,
        registry_version=fixture_snapshot("ipu")[2].registry_version,
        years=window.years,
    )
    return decide(
        candidate,
        run_outcome="complete",
        run_detail="",
        ledger=ledger.check(raw, parsed),
        baseline=promoted(fixture_snapshot("ipu")[2]),
        baseline_problem=None,
        acceptances=(),
        window=window,
        now=NOW,
    )


def osce_drop(accept: Sequence[DropAcceptance] = ()) -> Decision:
    base = promoted(synth(pages=(SynthPage("elections", 100),), fetched_at=T0))
    candidate = synth(pages=(SynthPage("elections", 40),), fetched_at=NOW)
    return decide(
        candidate,
        run_outcome="complete",
        run_detail="",
        ledger=report(candidate),
        baseline=base,
        baseline_problem=None,
        acceptances=accept,
        window=window_for(NOW),
        now=NOW,
    )


def test_acknowledgements_change_only_the_verdict() -> None:
    decision = ipu_failed()
    assert decision.acceptance == "fallback"
    reasons, _, acks = judged("ipu", decision, issues(), units=False)
    assert HTTP in reasons
    assert severity(reasons) == "error"
    assert acks == ()
    assert unacknowledged(reasons, acks) == (HTTP,)
    assert verdict(unacknowledged(reasons, acks)) == "red"

    # An acknowledgement in effect: the same decision, severity and reasons; only the verdict moves.
    known = issues(entry(scope=IPU_PAGE))
    same, _, acks = judged("ipu", decision, known, units=False)
    assert same == reasons
    assert severity(same) == "error"
    assert [a.code for a in acks] == ["http_error"]
    assert unacknowledged(same, acks) == ()
    assert verdict(unacknowledged(same, acks)) == "green"
    # The fallback's own unparsed units are another reason, which this entry does not cover.
    with_units, _, acks = judged("ipu", decision, known)
    assert codes(unacknowledged(with_units, acks)) == ["unparsed_relevant"]

    # An acknowledgement of a drop does not promote the candidate; an accept_drop does.
    scope = OSCE_PAGE
    drop = osce_drop()
    assert drop.acceptance == "quarantined"
    sudden = Reason(
        "sudden_drop",
        "elections: units fell from 100 to 40 (candidate: units 40, claims 40)",
        page="elections",
    )
    assert sudden in drop.reasons
    known = issues(entry(source="osce", reason="sudden_drop", scope=scope))
    reasons, _, acks = judged("osce", drop, known)
    assert [a.code for a in acks] == ["sudden_drop"]
    assert unacknowledged(reasons, acks) == ()
    plain = drop_acceptances(known, {"osce": CLEAN}, NOW)
    assert plain == ()
    assert osce_drop(plain).acceptance == "quarantined"

    accept = issues(
        entry(
            source="osce",
            reason="sudden_drop",
            scope=scope,
            accept_units_seen_min="40",
            accept_claims_min="40",
        )
    )
    accepted = osce_drop(drop_acceptances(accept, {"osce": CLEAN}, NOW))
    assert accepted.acceptance == "promoted"
    assert "count_change" in codes(accepted.reasons)
    assert "sudden_drop" not in codes(accepted.reasons)


def aweb(claims: tuple[object, ...], year: int, at: datetime) -> Snapshot:
    page = SynthPage("calendar", claims=claims, year=year)  # type: ignore[arg-type]
    return synth(source="aweb", pages=(page,), fetched_at=at)


R1 = datetime(2027, 1, 2, 6, tzinfo=UTC)
GAMBIA = mk(
    "aweb:calendar/r1",
    place_id="iso:GM",
    place_raw="Gambia",
    institution="iso:GM/president",
    office_class="head_of_state",
    office_label="President",
    span=day(2026, 12, 5),
    date_text="5 December 2026",
)
MARCH = (
    mk("aweb:calendar/r2", place_id="iso:BJ", place_raw="Benin", institution=None,
       span=day(2026, 3, 8), date_text="8 March 2026"),
)
FEBRUARY = (
    mk("aweb:calendar/r1", place_id="iso:EC", place_raw="Ecuador", institution=None,
       span=day(2027, 2, 7), date_text="7 February 2027"),
)
GAP_SCOPE = "{stage: parse, year: 2027, page: calendar}"


def gap_decision() -> Decision:
    base = promoted(aweb((GAMBIA, *MARCH), 2026, datetime(2026, 12, 20, 6, tzinfo=UTC)))
    candidate = aweb(FEBRUARY, 2027, R1)
    return decide(
        candidate,
        run_outcome="complete",
        run_detail="",
        ledger=report(candidate),
        baseline=base,
        baseline_problem=None,
        acceptances=(),
        window=window_for(R1),
        now=R1,
    )


def test_a_coverage_gap_is_acknowledged_only_after_it_began() -> None:
    decision = gap_decision()
    assert decision.acceptance == "promoted"
    gaps = [r for r in decision.reasons if r.code == "coverage_gap"]
    assert len(gaps) == 1 and gaps[0].since == R1

    def entry_at(given: datetime, until: datetime) -> str:
        return entry(
            source="aweb",
            reason="coverage_gap",
            scope=GAP_SCOPE,
            acknowledged_at=ts(given),
            expires_at=ts(until),
        )

    def status(known_text: str, now: datetime) -> tuple[Decision, tuple[Reason, ...], tuple[Reason, ...], str]:
        known = issues(known_text, now=now)
        reasons, _, acks = judged("aweb", decision, known, now)
        open_reasons = unacknowledged(reasons, acks)
        return decision, reasons, open_reasons, verdict(open_reasons)

    given, until = R1 + HOUR, R1 + HOUR + timedelta(days=7)
    now = R1 + 2 * HOUR
    _, reasons, open_reasons, colour = status(entry_at(given, until), now)
    assert gaps[0] in reasons
    assert severity(reasons) == "warning"
    assert open_reasons == () and colour == "green"
    reasons, _, acks = judged("aweb", decision, issues(entry_at(given, until), now=now), now)
    assert acks == (
        Acknowledgement("coverage_gap", until, "parse", 2027, "calendar", R1),
    )

    # At the exact expiry the entry no longer counts.
    _, _, open_reasons, colour = status(entry_at(given, until), until)
    assert open_reasons == (gaps[0],) and colour == "red"

    # An entry made before the gap began never covers it.
    early = entry_at(R1 - HOUR, R1 - HOUR + timedelta(days=7))
    _, _, open_reasons, colour = status(early, now)
    assert open_reasons == (gaps[0],) and colour == "red"


def test_two_gaps_of_one_scope_are_told_apart() -> None:
    first = Reason("coverage_gap", "first", page="calendar", year=2027, since=R1 - 2 * HOUR)
    second = Reason("coverage_gap", "second", page="calendar", year=2027, since=R1 + 2 * HOUR)
    text = entry(
        source="aweb",
        reason="coverage_gap",
        scope=GAP_SCOPE,
        acknowledged_at=ts(R1),
        expires_at=ts(R1 + timedelta(days=7)),
    )
    now = R1 + 3 * HOUR
    acks = acknowledge("aweb", (first, second), [], issues(text, now=now), CLEAN, now)
    assert [(a.code, a.since) for a in acks] == [("coverage_gap", first.since)]
    assert unacknowledged((first, second), acks) == (second,)
    assert REASON_STAGE["coverage_gap"] == "parse"


def test_source_reasons_order() -> None:
    items = (
        item("partial_unit", "ipu", "a partial unit"),
        item("unparsed_unit", "ipu", "an unparsed unit"),
    )
    decision_reasons = (Reason("count_change", "x"), Reason("coverage_gap", "y"))
    match = MatchDiagnostic(5, 2, 0, 5, True)
    state = HealthState((), "not JSON")
    got = source_reasons(decision_reasons, items, match, state)
    assert codes(got) == [
        "count_change",
        "coverage_gap",
        "unparsed_relevant",
        "partial_relevant",
        "no_cross_source_match",
        "ack_invalid",
    ]
    assert got[2].detail == "relevant units unparsed: 1"
    assert got[4].detail == "no other source lists any of its 5 in-window national contests"
    assert got[5].detail == "health_state.json is corrupt: not JSON"
    # Nothing to add: the decision's reasons alone.
    assert source_reasons(decision_reasons, (), NO_MATCH, CLEAN) == decision_reasons


@pytest.mark.parametrize("matched", [0, 1])
def test_match_reason_only_when_nothing_matched(matched: int) -> None:
    match = MatchDiagnostic(5, 2, matched, 5 - matched, True)
    got = source_reasons((), (), match, CLEAN)
    assert codes(got) == (["no_cross_source_match"] if matched == 0 else [])
