"""lib/labels.js: the label rules of spec correction P134 (Plan 5b-1 Task 2)."""

import copy
import json
from collections import Counter
from datetime import datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from tests.support.extension import PAGE_NOW, artifact_pair, js

L: Final = "lib/labels.js"


def _ms(instant: str) -> float:
    return datetime.fromisoformat(instant).timestamp() * 1000


PAGE_NOW_MS: Final = _ms(PAGE_NOW)
TODAY: Final = "2026-10-19"
FETCHED: Final = "2026-10-16T14:39:00Z"
FETCHED_MS: Final = _ms(FETCHED)
WEEK_MS: Final = 7 * 86400 * 1000


def _template() -> dict[str, Any]:
    feed = json.loads(artifact_pair()[0])
    found = [
        c
        for c in feed["months"]["2026-10"]
        if c["country"] == "Canada" and c["date"] == TODAY and c["type"] == "Alberta: Referendum"
    ]
    assert len(found) == 1
    assert len(found[0]["children"]) == 1
    template: dict[str, Any] = copy.deepcopy(found[0])
    template["level"] = "national"
    template["date_status"] = "confirmed"
    return template


TEMPLATE: Final = _template()


def card(**fields: Any) -> dict[str, Any]:
    out = copy.deepcopy(TEMPLATE)
    out.update(fields)
    return out


def source(**fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = copy.deepcopy(TEMPLATE["children"][0]["sources"][0])
    out.update(fields)
    return out


def kid(**fields: Any) -> dict[str, Any]:
    out: dict[str, Any] = copy.deepcopy(TEMPLATE["children"][0])
    out.update(fields)
    return out


def dated(
    start: str, end: str, precision: str = "day", meaning: str = "voting_period", **more: Any
) -> dict[str, Any]:
    return card(date=start, end_date=end, date_precision=precision, date_meaning=meaning, **more)


def label(
    page: Page,
    c: dict[str, Any],
    child: dict[str, Any] | None = None,
    today: str = TODAY,
    now: float = PAGE_NOW_MS,
) -> dict[str, Any]:
    got: dict[str, Any] = js(
        page,
        L,
        "childLabel",
        c,
        child if child is not None else kid(),
        {"today": today, "now": now},
    )
    return got


def check(
    page: Page,
    c: dict[str, Any],
    child: dict[str, Any] | None,
    kind: str,
    text: str,
    chips: list[str] | None = None,
    notes: list[str] | None = None,
) -> None:
    got = label(page, c, child)
    assert (got["kind"], got["text"]) == (kind, text)
    if chips is not None:
        assert got["chips"] == chips
    if notes is not None:
        assert got["notes"] == notes


@pytest.mark.parametrize(
    ("fields", "chips"),
    [
        (dated("2026-10-26", "2026-10-26", status="Upcoming"), []),
        (
            dated(
                "2026-10-26",
                "2026-10-26",
                status="Upcoming",
                date_status="tentative",
                level="subnational",
            ),
            ["Tentative", "Subnational"],
        ),
    ],
)
def test_exact_dates(lab: Page, fields: dict[str, Any], chips: list[str]) -> None:
    check(lab, fields, None, "scheduled", "Scheduled", chips, [])


@pytest.mark.parametrize(
    ("c", "kind", "text", "chips"),
    [
        (
            dated("2026-10-01", "2026-10-31", "month", "unknown"),
            "day_unconfirmed",
            "October — day unconfirmed",
            None,
        ),
        (
            dated("2026-12-01", "2026-12-31", "month", "unknown"),
            "day_unconfirmed",
            "December — day unconfirmed",
            None,
        ),
        (
            dated("2026-11-01", "2027-01-31", "month", "unknown"),
            "day_unconfirmed",
            "November–January — day unconfirmed",
            None,
        ),
        (
            dated("2026-09-01", "2026-09-30", "month", "unknown"),
            "past_expected",
            "Past expected period — not confirmed",
            None,
        ),
        (
            dated("2026-11-02", "2027-01-31", "day", "expected_window", date_status="tentative"),
            "expected",
            "Expected between 2 Nov and 31 Jan",
            ["Tentative"],
        ),
        (
            dated("2026-12-01", "2026-12-31", "month", "expected_window"),
            "expected",
            "Expected in December",
            None,
        ),
        (
            dated("2026-11-01", "2027-01-31", "month", "expected_window"),
            "expected",
            "Expected between November and January",
            None,
        ),
        (
            dated("2027-01-01", "2027-12-31", "year", "unknown"),
            "day_unconfirmed",
            "2027 — date unconfirmed",
            None,
        ),
        (
            dated("2027-01-01", "2027-12-31", "year", "expected_window"),
            "expected",
            "Expected in 2027",
            None,
        ),
        (
            dated("2026-09-01", "2026-10-18", "day", "expected_window"),
            "past_expected",
            "Past expected period — not confirmed",
            None,
        ),
        (
            dated("2026-11-20", "2026-11-20", "day", "expected_window"),
            "expected",
            "Expected on 20 Nov",
            None,
        ),
        (
            dated("2026-10-19", "2026-10-19", "day", "expected_window"),
            "expected",
            "Expected on 19 Oct",
            None,
        ),
    ],
)
def test_month_year_and_expected_windows(
    lab: Page, c: dict[str, Any], kind: str, text: str, chips: list[str] | None
) -> None:
    check(lab, c, None, kind, text, chips)


HELD_DAY = dated("2026-10-04", "2026-10-04", status="Held")


def test_held_and_past(lab: Page) -> None:
    check(lab, HELD_DAY, kid(occurrence_confirmed=True), "held", "Held")
    check(lab, HELD_DAY, kid(occurrence_confirmed=False), "past", "Past")
    three = [label(lab, HELD_DAY, kid(occurrence_confirmed=ok)) for ok in (True, True, False)]
    got = js(lab, L, "cardLabel", HELD_DAY, three)
    assert got == {"kind": "past", "text": "Past · 2 of 3 confirmed held"}
    every = [label(lab, HELD_DAY, kid(occurrence_confirmed=True)) for _ in range(3)]
    assert js(lab, L, "cardLabel", HELD_DAY, every) == {"kind": "held", "text": "Held"}


def test_past_rescheduled_is_unconfirmed(lab: Page) -> None:
    child = kid(rescheduled_from=["15 September"], occurrence_confirmed=False)
    check(lab, HELD_DAY, child, "past", "Past")


NOW_RANGE = dated("2026-10-18", "2026-10-20")


def test_conflicts_suppress_today(lab: Page) -> None:
    check(lab, NOW_RANGE, None, "today", "Scheduled voting period: today (approx.)")
    check(
        lab,
        NOW_RANGE,
        kid(date_conflict=True),
        "scheduled",
        "Scheduled",
        notes=["Sources disagree on date"],
    )
    check(
        lab,
        NOW_RANGE,
        kid(status_conflict=True),
        "possibly_postponed",
        "Possibly postponed — sources disagree",
    )
    check(lab, {**NOW_RANGE, "status": "Postponed"}, None, "postponed", "Postponed")
    check(
        lab,
        {**NOW_RANGE, "status": "Cancelled"},
        kid(status_conflict=True),
        "cancelled",
        "Cancelled",
    )
    check(lab, {**NOW_RANGE, "status": "Disputed"}, None, "disputed", "Disputed")
    check(lab, dated("2026-10-18", "2026-10-20", "day", "unknown"), None, "scheduled", "Scheduled")
    two = [label(lab, NOW_RANGE, kid(status_conflict=True)), label(lab, NOW_RANGE)]
    assert js(lab, L, "cardLabel", NOW_RANGE, two) == {
        "kind": "possibly_postponed",
        "text": "Possibly postponed — sources disagree · 1 of 2",
    }


def test_cancellation_conflict_label(lab: Page) -> None:
    child = kid(status_conflict=True, sources=[source(status_claim="cancelled")])
    check(lab, NOW_RANGE, child, "possibly_cancelled", "Possibly cancelled — sources disagree")


def test_renewal_only_child_is_labelled_expected(lab: Page) -> None:
    c = dated("2026-12-01", "2026-12-31", "month", "expected_window", date_status="tentative")
    child = kid(sources=[source(name="IPU", evidence_kind="expected_renewal")])
    check(lab, c, child, "expected", "Expected in December", ["Tentative"])


def test_less_precise_note(lab: Page) -> None:
    served = dated("2026-11-15", "2026-11-15")
    provisional = source(
        provisional=True, date="2026-11-01", end_date="2026-11-30", date_precision="month"
    )
    check(
        lab,
        served,
        kid(provisional_date="less_precise", sources=[source(), provisional]),
        "scheduled",
        "Scheduled",
        notes=["The source now gives a less precise date: 15 November 2026 → November 2026"],
    )
    month = dated("2026-11-01", "2026-11-30", "month")
    year = source(provisional=True, date="2026-01-01", end_date="2026-12-31", date_precision="year")
    check(
        lab,
        month,
        kid(provisional_date="less_precise", sources=[source(), year]),
        "day_unconfirmed",
        "November — day unconfirmed",
        notes=["The source now gives a less precise date: November 2026 → 2026"],
    )
    moved = source(provisional=True, date="2026-11-22", end_date="2026-11-22")
    check(
        lab,
        served,
        kid(provisional_date="moved", sources=[source(), moved]),
        "scheduled",
        "Scheduled",
        notes=["Sources disagree on date"],
    )


def test_cached_confirmation_shows_its_date(lab: Page) -> None:
    held = source(selected=False, status_claim="held", fallback=True, fetched_at=FETCHED)
    child = kid(occurrence_confirmed=True, sources=[source(), held])
    check(lab, HELD_DAY, child, "held", "Held", notes=["Confirmed by source data from 16 Oct 2026"])
    # One held source is live, so the confirmation is not only from the cache.
    live = source(selected=False, status_claim="held", fallback=False)
    mixed = kid(occurrence_confirmed=True, sources=[source(), held, live])
    check(lab, HELD_DAY, mixed, "held", "Held", notes=[])


def test_stale_fetch_date_is_shown(lab: Page) -> None:
    c = dated("2026-10-26", "2026-10-26")
    child = kid(sources=[source(fallback=True, fetched_at=FETCHED)])
    using = ["Using source data from 16 Oct 2026"]

    def notes(now: float, child: dict[str, Any] = child) -> list[str]:
        got: list[str] = label(lab, c, child, now=now)["notes"]
        return got

    assert notes(PAGE_NOW_MS) == using
    assert notes(FETCHED_MS + WEEK_MS) == using
    assert notes(FETCHED_MS + WEEK_MS + 1000) == ["Unverified since 16 Oct 2026"]
    unknown = kid(sources=[source(fallback=True, fetched_at=None)])
    assert notes(PAGE_NOW_MS, unknown) == ["Unverified: the source data's date is unknown"]


def test_fallback_dates_report_the_oldest_and_the_latest(lab: Page) -> None:
    older, newer = "2026-10-14T09:00:00Z", "2026-10-16T14:39:00Z"
    sources = [
        source(selected=True, status_claim="held", fallback=True, fetched_at=older),
        source(selected=True, status_claim="held", fallback=True, fetched_at=newer),
    ]
    for ordered in (sources, sources[::-1]):
        child = kid(occurrence_confirmed=True, sources=ordered)
        notes = [
            "Using source data from 14 Oct 2026",  # the OLDEST of the selected fallbacks
            "Confirmed by source data from 16 Oct 2026",  # the LATEST of the held claims
        ]
        check(lab, HELD_DAY, child, "held", "Held", notes=notes)


@pytest.mark.parametrize(
    ("meaning", "kind", "text"),
    [
        ("voting_period", "past", "Past"),
        ("expected_window", "past_expected", "Past expected period — not confirmed"),
    ],
)
def test_no_tentative_chip_on_past_cards(lab: Page, meaning: str, kind: str, text: str) -> None:
    c = dated("2026-10-04", "2026-10-04", "day", meaning, status="Held", date_status="tentative")
    check(lab, c, kid(occurrence_confirmed=False), kind, text, [])


def test_a_tentative_held_card_has_no_tentative_chip(lab: Page) -> None:
    c = dated("2026-10-04", "2026-10-04", status="Held", date_status="tentative")
    check(lab, c, kid(occurrence_confirmed=True), "held", "Held", [])


def test_one_child_has_no_k_of_n_suffix(lab: Page) -> None:
    one = [label(lab, NOW_RANGE, kid(status_conflict=True))]
    assert js(lab, L, "cardLabel", NOW_RANGE, one) == {
        "kind": "possibly_postponed",
        "text": "Possibly postponed — sources disagree",
    }


def test_provisional_source_note(lab: Page) -> None:
    on = source(provisional=True, fetched_at="2026-10-19T08:57:34Z")
    assert js(lab, L, "sourceNote", on) == "Newer data from an incomplete fetch on 19 Oct 2026"
    assert js(lab, L, "sourceNote", source(provisional=False)) is None
    undated = source(provisional=True, fetched_at=None)
    assert js(lab, L, "sourceNote", undated) == "Newer data from an incomplete fetch"


EXPECTED_COUNTS: Final = {
    "2026-09": {"held": 5, "past": 22},
    "2026-10": {"held": 8, "past": 35, "scheduled": 14, "today": 1},
    "2026-11": {"scheduled": 89},
    "2026-12": {"day_unconfirmed": 1, "expected": 3, "scheduled": 17},
    "2027-01": {"expected": 1, "scheduled": 6},
}


def test_every_fixture_child_has_a_label(lab: Page) -> None:
    feed = json.loads(artifact_pair()[0])
    kinds = lab.evaluate("async () => (await import('/lib/labels.js')).KINDS")
    labelled = lab.evaluate(
        """async ([months, today, now]) => {
            const { childLabel } = await import("/lib/labels.js");
            const out = [];
            for (const [month, cards] of Object.entries(months)) {
                for (const card of cards) {
                    for (const child of card.children) {
                        const l = childLabel(card, child, { today, now });
                        out.push([month, l.kind, l.text]);
                    }
                }
            }
            return out;
        }""",
        [feed["months"], TODAY, PAGE_NOW_MS],
    )
    assert len(labelled) == 202
    assert all(kind in kinds and text for _, kind, text in labelled)
    counts: dict[str, Counter[str]] = {}
    for month, kind, _ in labelled:
        counts.setdefault(month, Counter())[kind] += 1
    assert {m: dict(c) for m, c in counts.items()} == EXPECTED_COUNTS
