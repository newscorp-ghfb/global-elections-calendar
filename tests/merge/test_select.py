"""Task 3: resolved-value selection and the legacy status (spec 10.5, 5.9; P67-P69, P75, R2-01)."""

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from elections_calendar.merge.select import (
    Selection,
    StatusResult,
    is_stale,
    legacy_status,
    select,
)
from elections_calendar.model import Claim, DateSpan
from tests.support.claims import NOW, OBS, RENEW, day, days, mk, month, months, year
from tests.support.fixture_claims import FIXTURE_NOW, fixture_claim

STALE_AT = datetime(2026, 9, 1, tzinfo=UTC)
FRESH_AT = datetime(2026, 10, 18, tzinfo=UTC)
WPn = "wikipedia:national-2026@rev1"
WPl = "wikipedia:local-2026@rev2"
TODAY = date(2026, 10, 19)


def wp4(**kw: Any) -> Claim:
    return mk(f"{WPn}/November/li[4]", **kw)


def stale(claim: Claim) -> Claim:
    return replace(claim, fallback=True, fetched_at=STALE_AT)


def at(h: int, mi: int, d: int = 12) -> datetime:
    return datetime(2026, 10, d, h, mi, tzinfo=UTC)


Pairs = Sequence[tuple[Claim, str | None]]


def check(sel: Selection, pairs: Pairs) -> None:
    winners = [c for c, r in pairs if r is None]
    assert sel.claim == (winners[0] if winners else None)
    assert sel.reasons == {c.merge_id: r for c, r in pairs}


def run(pairs: Pairs, now: datetime = NOW) -> Selection:
    sel = select([c for c, _ in pairs], now)
    check(sel, pairs)
    return sel


@pytest.mark.parametrize(
    ("claim", "expected"),
    [
        (mk("osce:elections/r1", fallback=False, fetched_at=STALE_AT), False),
        (mk("osce:elections/r1", fallback=True, fetched_at=None), True),
        (mk("osce:elections/r1", fallback=True, fetched_at=at(12, 0)), False),
        (mk("osce:elections/r1", fallback=True, fetched_at=at(11, 59)), True),
    ],
    ids=["not-fallback", "no-fetch-time", "exactly-7-days", "7-days-1-minute"],
)
def test_is_stale(claim: Claim, expected: bool) -> None:
    assert is_stale(claim, NOW) is expected


D20 = day(2026, 9, 20)


def _osce(span: DateSpan = D20, **kw: Any) -> Claim:
    return mk("osce:elections/r1", span=span, **kw)


def _wp_range() -> Claim:
    return mk(f"{WPn}/September/li[3]", span=days(2026, 9, 18, 2026, 9, 20))


_ipu_renew = mk("ipu:elections/r1", **RENEW)
_carter_nov = mk("carter:observed/r1", **OBS, span=month(2026, 11))
_osce_year = mk("osce:elections/r9", span=year(2026))
_eg3 = mk("electionguide:upcoming/r3", source_event_id="electionguide:9")
_eg2 = mk("electionguide:upcoming/r2", source_event_id="electionguide:10")
_eg1 = mk("electionguide:upcoming/r1")
_ndi_c2 = mk(
    "ndi:p0/upcoming-c2", span=month(2026, 11), date_status="tentative", date_meaning="unknown"
)
_aweb_r2 = mk("aweb:calendar/r2", span=days(2026, 11, 14, 2026, 11, 15), date_meaning="unknown")

SELECTION_ROWS: list[tuple[str, Pairs]] = [
    ("range-covers-day", [(_osce(), "not_covering"), (_wp_range(), None)]),
    ("range-covers-day-reversed", [(_wp_range(), None), (_osce(), "not_covering")]),
    (
        "unknown-meaning-range-never-covers",
        [
            (_osce(), None),
            (
                mk(
                    "aweb:calendar/r1",
                    span=days(2026, 9, 18, 2026, 9, 20),
                    date_meaning="unknown",
                ),
                "lower_priority",
            ),
        ],
    ),
    (
        "calendar-beats-renewal-observation-year",
        [
            (_ipu_renew, "lower_evidence"),
            (_carter_nov, "observation"),
            (_osce_year, "year_only"),
            (wp4(), None),
        ],
    ),
    (
        "renewal-alone",
        [(_ipu_renew, None), (_carter_nov, "observation"), (_osce_year, "year_only")],
    ),
    ("nothing-eligible", [(_carter_nov, "observation"), (_osce_year, "year_only")]),
    (
        "precision-before-status",
        [(_ndi_c2, "less_precise"), (_aweb_r2, None)],
    ),
    (
        "confirmed-first",
        [
            (wp4(), "less_certain"),
            (mk("electionguide:upcoming/r2", date_status="tentative"), "less_certain"),
            (mk("electionguide:upcoming/r1", date_status="confirmed"), None),
        ],
    ),
    (
        "event-id-before-no-event",
        [(_eg3, "lower_priority"), (_eg2, None), (_eg1, "lower_priority")],
    ),
    (
        "family-priority",
        [
            (mk("eeas:missions/r1c1"), "lower_priority"),
            (mk("ipu:elections/r5"), "lower_priority"),
            (mk("ndi:p0/upcoming-c1"), "lower_priority"),
            (mk(f"{WPl}/November/li[1]"), "lower_priority"),
            (mk(f"{WPn}/November/li[1]"), None),
        ],
    ),
    (
        "umbrella-ranks-with-calendar",
        [(_osce(span=day(2026, 11, 15), evidence_kind="umbrella"), None),
         (_ipu_renew, "lower_evidence")],
    ),
]


@pytest.mark.parametrize(
    "pairs", [r for _, r in SELECTION_ROWS], ids=[n for n, _ in SELECTION_ROWS]
)
def test_selection(pairs: Pairs) -> None:
    sel = run(pairs)
    assert (sel.date_conflict, sel.unverified) == (False, False)


def _fresh(**kw: Any) -> dict[str, Any]:
    return dict(fetched_at=FRESH_AT, **kw)


FRESHNESS_ROWS: list[tuple[str, Pairs, bool, bool]] = [
    (
        "renewal-is-no-support",
        [(mk("ipu:elections/r1", **RENEW, **_fresh()), "lower_evidence"), (stale(wp4()), None)],
        False,
        True,
    ),
    (
        "renewal-elsewhere-is-no-disagreement",
        [
            (
                mk("ipu:elections/r1", **RENEW, span=month(2026, 12), **_fresh()),
                "lower_evidence",
            ),
            (stale(wp4()), None),
        ],
        False,
        True,
    ),
    (
        "containing-month-is-missing-support",
        [
            (stale(wp4()), None),
            (
                mk(
                    "ndi:p0/upcoming-c4",
                    span=month(2026, 11),
                    date_status="tentative",
                    date_meaning="unknown",
                    **_fresh(),
                ),
                "not_covering",
            ),
        ],
        False,
        True,
    ),
    (
        "other-month-disagrees",
        [
            (stale(wp4()), None),
            (
                mk(
                    "ndi:p0/upcoming-c4",
                    span=month(2026, 12),
                    date_status="tentative",
                    date_meaning="unknown",
                    **_fresh(),
                ),
                "not_covering",
            ),
        ],
        True,
        True,
    ),
    (
        "other-meaning-same-day",
        [
            (stale(wp4()), None),
            (mk("aweb:calendar/r1", date_meaning="unknown", **_fresh()), "not_covering"),
        ],
        False,
        True,
    ),
    (
        "stale-pair-beats-fresh-renewal",
        [
            (mk("ipu:elections/r1", **RENEW, **_fresh()), "lower_evidence"),
            (stale(wp4()), "lower_priority"),
            (stale(mk("osce:elections/r1")), None),
        ],
        False,
        True,
    ),
    (
        "fresh-renewal-alone",
        [(mk("ipu:elections/r1", **RENEW, **_fresh()), None)],
        False,
        False,
    ),
    (
        "stale-renewal-alone",
        [(stale(mk("ipu:elections/r1", **RENEW)), None)],
        False,
        True,
    ),
    (
        "stale-confirmed-loses-to-nothing",
        [
            (wp4(**_fresh()), "less_certain"),
            (stale(mk("electionguide:upcoming/r1", date_status="confirmed")), None),
        ],
        False,
        False,
    ),
    (
        "fresh-beats-stale",
        [(stale(wp4()), "stale"), (mk("osce:elections/r1", **_fresh()), None)],
        False,
        False,
    ),
    (
        "no-fetch-time-is-stale",
        [
            (wp4(fallback=True, fetched_at=None), "stale"),
            (mk("osce:elections/r1", **_fresh()), None),
        ],
        False,
        False,
    ),
    (
        "fetched-just-under-8-days",
        [
            (wp4(fallback=True, fetched_at=datetime(2026, 10, 13, tzinfo=UTC)), "lower_priority"),
            (mk("osce:elections/r1", **_fresh()), None),
        ],
        False,
        False,
    ),
    (
        "exactly-7-days-is-fresh",
        [
            (wp4(fallback=True, fetched_at=at(12, 0)), "lower_priority"),
            (mk("osce:elections/r1", **_fresh()), None),
        ],
        False,
        False,
    ),
    (
        "7-days-1-minute-is-stale",
        [
            (wp4(fallback=True, fetched_at=at(11, 59)), "stale"),
            (mk("osce:elections/r1", **_fresh()), None),
        ],
        False,
        False,
    ),
]


@pytest.mark.parametrize(
    ("pairs", "conflict", "unverified"),
    [(p, c, u) for _, p, c, u in FRESHNESS_ROWS],
    ids=[n for n, *_ in FRESHNESS_ROWS],
)
def test_freshness(pairs: Pairs, conflict: bool, unverified: bool) -> None:
    sel = run(pairs)
    assert (sel.date_conflict, sel.unverified) == (conflict, unverified)


LEGACY_ROWS = [
    (day(2026, 10, 4), "Held"),
    (day(2026, 10, 19), "Upcoming"),
    (days(2026, 10, 18, 2026, 10, 20), "Upcoming"),
    (month(2026, 10), "Unknown"),
    (month(2026, 9), "Held"),
    (month(2026, 11), "Upcoming"),
    (months(2026, 9, 2026, 10), "Unknown"),
]


@pytest.mark.parametrize(
    ("span", "status"),
    LEGACY_ROWS,
    ids=["day-past", "day-today", "range-over-today", "this-month", "last-month", "next-month",
         "months-over-today"],
)
def test_legacy_status_by_date(span: DateSpan, status: str) -> None:
    got = legacy_status([mk("osce:elections/r1", span=span)], span, TODAY)
    assert got == StatusResult(status, None, False, False)  # type: ignore[arg-type]


D15 = day(2026, 11, 15)
D13 = day(2026, 9, 13)


def canc(s: DateSpan) -> Claim:
    return mk("osce:elections/r1", span=s, status_claim="cancelled", fetched_at=FRESH_AT)


def fresh(s: DateSpan) -> Claim:
    return wp4(span=s, fetched_at=FRESH_AT)


def held(s: DateSpan, **kw: Any) -> Claim:
    return mk("electionguide:past/r1", span=s, status_claim="held", **kw)


def resch(s: DateSpan) -> Claim:
    return mk(
        "eisa:y2026/r3", span=s, status_claim="postponed", previous_date_text="1 November 2026"
    )


def eisa_post(s: DateSpan, **kw: Any) -> Claim:
    return mk("eisa:y2026/r3", span=s, status_claim="postponed", **kw)


H_OCT = mk(
    "ndi:p0/past-c9",
    span=month(2026, 10),
    date_meaning="unknown",
    status_claim="held",
    date_text="October 2026",
)
NDI_C4 = mk(
    "ndi:p0/upcoming-c4", span=month(2026, 11), date_status="tentative", date_meaning="unknown"
)

Maker = Callable[[DateSpan], list[Claim]]
STATUS_ROWS: list[tuple[str, DateSpan, Maker, tuple[str, str | None, bool], bool]] = [
    ("listing-never-revives", D15, lambda s: [canc(s), fresh(s)], ("Cancelled", "cancelled", True), False),
    (
        "refetched-confirmed-is-no-reinstatement",
        D15,
        lambda s: [
            canc(s),
            mk("electionguide:upcoming/r1", span=s, date_status="confirmed", fetched_at=FRESH_AT),
        ],
        ("Cancelled", "cancelled", True),
        False,
    ),
    (
        "stale-listing-does-not-oppose",
        D15,
        lambda s: [canc(s), stale(wp4(span=s))],
        ("Cancelled", "cancelled", False),
        False,
    ),
    ("alone", D15, lambda s: [canc(s)], ("Cancelled", "cancelled", False), False),
    (
        "same-family-never-opposes",
        D15,
        lambda s: [canc(s), mk("osce:elections/r2", span=s)],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "renewal-never-opposes",
        D15,
        lambda s: [canc(s), mk("ipu:elections/r1", span=s, **RENEW, fetched_at=FRESH_AT)],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "tentative-month-opposes",
        D15,
        lambda s: [canc(s), NDI_C4],
        ("Cancelled", "cancelled", True),
        False,
    ),
    (
        "year-never-opposes",
        D15,
        lambda s: [canc(s), mk("electionguide:upcoming/r7", span=year(2026))],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "held-overrides",
        D13,
        lambda s: [canc(s), held(s)],
        ("Held", None, True),
        False,
    ),
    (
        "stale-held-never-overrides",
        D13,
        lambda s: [canc(s), stale(held(s))],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "fresh-fallback-held-never-overrides",
        D13,
        lambda s: [canc(s), held(s, fallback=True, fetched_at=datetime(2026, 10, 13, tzinfo=UTC))],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "renewal-held-never-overrides",
        D13,
        lambda s: [canc(s), mk("ipu:elections/r1", span=s, **RENEW, status_claim="held")],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "observation-held-never-overrides",
        D13,
        lambda s: [canc(s), mk("carter:observed/r1", **OBS, span=D13, status_claim="held")],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "same-family-held-never-overrides",
        D13,
        lambda s: [canc(s), mk("osce:elections/r2", span=s, status_claim="held")],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "year-held-never-overrides",
        D13,
        lambda s: [canc(s), held(year(2026))],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "held-for-another-month-opposes-only",
        D15,
        lambda s: [canc(s), H_OCT],
        ("Cancelled", "cancelled", True),
        False,
    ),
    (
        "postponed-beside-listing",
        D15,
        lambda s: [mk("osce:elections/r1", span=s, status_claim="postponed"), fresh(s)],
        ("Postponed", "postponed", True),
        False,
    ),
    (
        "rescheduling-follows-new-date",
        D15,
        lambda s: [resch(s), fresh(s)],
        ("Upcoming", None, False),
        True,
    ),
    (
        "one-family-two-words",
        D15,
        lambda s: [mk("osce:elections/r2", span=s, status_claim="postponed"), canc(s)],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "opposed-words",
        D15,
        lambda s: [canc(s), eisa_post(s)],
        ("Cancelled", "cancelled", True),
        False,
    ),
    (
        "stale-opposed-word-is-ignored",
        D15,
        lambda s: [canc(s), stale(eisa_post(s))],
        ("Cancelled", "cancelled", False),
        False,
    ),
    (
        "cancelled-before-rescheduling",
        D15,
        lambda s: [canc(s), resch(s), fresh(s)],
        ("Cancelled", "cancelled", True),
        False,
    ),
    (
        "disputed-yields-to-postponed",
        D15,
        lambda s: [mk("osce:elections/r1", span=s, status_claim="disputed"), eisa_post(s)],
        ("Postponed", "postponed", True),
        False,
    ),
    (
        "disputed",
        D13,
        lambda s: [mk("osce:elections/r1", span=s, status_claim="disputed"), fresh(s)],
        ("Disputed", "disputed", False),
        False,
    ),
    (
        "fallback-disputed-is-no-word",
        D13,
        lambda s: [
            mk(
                "osce:elections/r1",
                span=s,
                status_claim="disputed",
                fallback=True,
                fetched_at=FRESH_AT,
            )
        ],
        ("Held", None, False),
        False,
    ),
]


@pytest.mark.parametrize(
    ("span", "make", "expected", "rescheduled"),
    [(s, m, e, r) for _, s, m, e, r in STATUS_ROWS],
    ids=[n for n, *_ in STATUS_ROWS],
)
def test_status_claims(
    span: DateSpan, make: Maker, expected: tuple[str, str | None, bool], rescheduled: bool
) -> None:
    got = legacy_status(make(span), span, TODAY)
    assert (got.status, got.resolved, got.conflict, got.rescheduled) == (*expected, rescheduled)


UNDATED = mk("osce:elections/r1", status_claim="postponed")
NOV20 = date(2026, 11, 20)
LIFECYCLE_ROWS: list[tuple[str, list[Claim], date, tuple[str, str | None, bool, bool]]] = [
    ("rescheduled-upcoming", [resch(D15)], TODAY, ("Upcoming", None, False, True)),
    ("rescheduled-then-past", [resch(D15)], NOV20, ("Held", None, False, True)),
    ("rescheduled-and-held", [resch(D15), held(D15)], NOV20, ("Held", None, False, True)),
    ("undated-stays-postponed", [UNDATED], NOV20, ("Postponed", "postponed", False, False)),
    ("undated-and-held", [UNDATED, held(D15)], NOV20, ("Held", None, True, False)),
    (
        "further-postponement",
        [resch(D15), UNDATED],
        TODAY,
        ("Postponed", "postponed", False, False),
    ),
    ("rescheduled-and-cancelled", [resch(D15), canc(D15)], TODAY, ("Cancelled", "cancelled", True, False)),
    (
        "year-is-no-new-date",
        [
            mk(
                "eisa:y2026/r16",
                status_claim="postponed",
                previous_date_text="June 2026",
                span=year(2026),
            ),
            fresh(D15),
        ],
        TODAY,
        ("Postponed", "postponed", True, False),
    ),
]


@pytest.mark.parametrize(
    ("direct", "today", "expected"),
    [(d, t, e) for _, d, t, e in LIFECYCLE_ROWS],
    ids=[n for n, *_ in LIFECYCLE_ROWS],
)
def test_rescheduling_lifecycle(
    direct: list[Claim], today: date, expected: tuple[str, str | None, bool, bool]
) -> None:
    got = legacy_status(direct, D15, today)
    assert (got.status, got.resolved, got.conflict, got.rescheduled) == expected


EG = mk("electionguide:upcoming/r1")
WP = wp4()
RS = mk(
    "eisa:y2026/r3",
    span=month(2026, 12),
    date_meaning="unknown",
    date_status="tentative",
    status_claim="postponed",
    previous_date_text="15 November 2026",
    date_text="December 2026",
)
RS_N = replace(RS, span=month(2026, 11), date_text="November 2026")
EG29 = mk("electionguide:upcoming/r1", span=day(2026, 11, 29))
RS_F = mk(
    "eisa:y2026/r3",
    span=day(2026, 11, 29),
    status_claim="postponed",
    previous_date_text="November 2026",
)
OLD_ROWS: list[tuple[str, Pairs, bool]] = [
    ("new-month-elsewhere", [(EG, "old_date"), (RS, None)], True),
    ("old-day-inside-new-month", [(EG, "old_date"), (RS_N, None)], True),
    ("both-old-dates", [(EG, "old_date"), (RS, None), (WP, "old_date")], True),
    ("old-month-is-not-inside-new-day", [(EG29, None), (RS_F, "lower_priority")], False),
    ("both-give-the-new-date", [(EG, None), (resch(D15), "lower_priority")], False),
]


@pytest.mark.parametrize(
    ("pairs", "conflict"), [(p, c) for _, p, c in OLD_ROWS], ids=[n for n, *_ in OLD_ROWS]
)
def test_old_dates(pairs: Pairs, conflict: bool) -> None:
    sel = run(pairs)
    assert (sel.date_conflict, sel.unverified) == (conflict, False)


def test_old_date_status_follows_the_new_date() -> None:
    got = legacy_status([EG, RS], RS.span, date(2026, 11, 20))
    assert got == StatusResult("Upcoming", None, False, True)


def obs(span: DateSpan, **kw: Any) -> Claim:
    return mk("carter:observed/r1", **OBS, span=span, **kw)


def eeas(span: DateSpan) -> Claim:
    return mk("eeas:missions/r1c1", **OBS, span=span)


_OBS_DAY = obs(day(2026, 11, 15))
_WP_MONTH = wp4(span=month(2026, 11))
OBS_ROWS: list[tuple[str, Pairs]] = [
    ("month-only", [(obs(month(2026, 11)), "observation")]),
    ("day-observation", [(_OBS_DAY, "observation"), (_WP_MONTH, None)]),
    ("beside-renewal", [(obs(month(2026, 11)), "observation"), (_ipu_renew, None)]),
    (
        "year-claims",
        [(eeas(year(2026)), "observation"), (mk("osce:elections/r9", span=year(2026)), "year_only")],
    ),
]


@pytest.mark.parametrize("pairs", [p for _, p in OBS_ROWS], ids=[n for n, _ in OBS_ROWS])
def test_unknown_meaning_observation_is_never_a_polling_date(pairs: Pairs) -> None:
    run(pairs)


@pytest.mark.parametrize(
    ("direct", "today", "expected"),
    [
        (
            [wp4(), obs(month(2026, 11), status_claim="cancelled")],
            date(2026, 11, 10),
            ("Upcoming", None, False),
        ),
        ([canc(D15), obs(day(2026, 11, 15))], TODAY, ("Cancelled", "cancelled", False)),
        (
            [wp4(), mk("eeas:missions/r1c1", **OBS, span=year(2026), status_claim="held")],
            TODAY,
            ("Upcoming", None, False),
        ),
    ],
    ids=["ignored-cancelled-word", "never-contradicts", "year-held-observation"],
)
def test_unknown_meaning_observation_never_makes_held_or_ongoing(
    direct: list[Claim], today: date, expected: tuple[str, str | None, bool]
) -> None:
    got = legacy_status(direct, D15, today)
    assert (got.status, got.resolved, got.conflict) == expected
    assert got.rescheduled is False


def test_ndi_tbd_never_confirms_a_date() -> None:
    eg = fixture_claim("electionguide:upcoming/r2#0")
    osce = fixture_claim("osce:elections/r2#0")
    wiki = fixture_claim("wikipedia:national-2026@rev1380221397/October/li[6]/li[2]#0")
    ndi = fixture_claim("ndi:p0/upcoming-c2#0")
    ipu = fixture_claim("ipu:elections/r222#0")
    sel = select([eg, osce, wiki, ndi, ipu], FIXTURE_NOW)
    check(
        sel,
        [
            (eg, None),
            (osce, "less_certain"),
            (wiki, "less_certain"),
            (ndi, "not_covering"),
            (ipu, "lower_evidence"),
        ],
    )
    assert eg.date_status == "confirmed"
    assert (sel.date_conflict, sel.unverified) == (False, False)

    only = select([ndi], FIXTURE_NOW)
    assert only.claim == ndi
    assert ndi.span.precision == "month" and ndi.span.start == date(2026, 10, 1)
    assert ndi.date_status == "tentative"

    stale_eg = stale(eg)
    fresh_ndi = replace(ndi, fetched_at=FRESH_AT)
    sel = select([stale_eg, fresh_ndi], FIXTURE_NOW)
    check(sel, [(stale_eg, None), (fresh_ndi, "not_covering")])
    assert (sel.date_conflict, sel.unverified) == (False, True)


def test_an_inferred_month_never_confirms_a_day() -> None:
    ndi = fixture_claim("ndi:p1/past-c5#0")
    assert ndi.span.precision == "month" and ndi.span.start == date(2026, 5, 1)
    assert ndi.date_status == "unknown"
    eg = fixture_claim("electionguide:past/r32#0")
    wiki = fixture_claim("wikipedia:national-2026@rev1380221397/May/li[6]/li[1]#0")
    aweb = fixture_claim("aweb:calendar/r15#0")
    carter = fixture_claim("carter:observed/expert-r3#1")
    sel = select([eg, wiki, ndi, aweb, carter], FIXTURE_NOW)
    check(
        sel,
        [
            (eg, None),
            (wiki, "less_certain"),
            (ndi, "not_covering"),
            (aweb, "less_certain"),
            (carter, "observation"),
        ],
    )

    wp = wp4(span=day(2026, 11, 30), fallback=True, fetched_at=STALE_AT)
    ndi4 = mk(
        "ndi:p0/upcoming-c4",
        span=month(2026, 11),
        date_meaning="unknown",
        date_text="November 30, 2026 (ALL DAY)",
        fetched_at=FRESH_AT,
    )
    sel = select([wp, ndi4], FIXTURE_NOW)
    check(sel, [(wp, None), (ndi4, "not_covering")])
    assert (sel.date_conflict, sel.unverified) == (False, True)
