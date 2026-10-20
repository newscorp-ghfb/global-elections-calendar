"""Task 5: children, cards, undated listings, attention items and dispositions.

Spec 5.3-5.5 and 10.7 with the plan's P75-P77, P79, P81, P82, R2-01 and D4. Every id and text
below was measured by the plan's prototypes; the claims named after Task 4's cases have the
same definitions as there (the presets live in ``tests/support/claims.py``).
"""

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest

from elections_calendar.merge.cards import build, card_type, display_label, relevance_of
from elections_calendar.merge.identity import short_id
from elections_calendar.merge.match import match
from elections_calendar.model import (
    BibEntry,
    Card,
    Child,
    Claim,
    DateSpan,
    MergeResult,
    Relevance,
)
from elections_calendar.places import PlaceRegistry
from elections_calendar.window import window_for
from tests.support.claims import (
    BR,
    BRP,
    CO,
    EGP,
    EGU,
    GB,
    GD,
    GD_IPU,
    LEG,
    LOWER,
    MB,
    NOW,
    OBS,
    PE,
    PRES_BR,
    RENEW,
    SI,
    UMB,
    UPPER,
    XS,
    WPl,
    WPn,
    cl,
    day,
    mk,
    month,
    months,
    result,
    year,
)


def only_card(res: MergeResult) -> Card:
    (card,) = res.cards
    return card


def only_child(res: MergeResult) -> Child:
    (child,) = only_card(res).children
    return child


def sources(child: Child) -> list[tuple[Claim, bool, str | None]]:
    return [(s.claim, s.selected, s.rejected_reason) for s in child.sources]


def bib(*pairs: tuple[str, str]) -> tuple[BibEntry, ...]:
    return tuple(BibEntry(s, link) for s, link in pairs)


def disposition(res: MergeResult, claim: Claim) -> tuple[str, tuple[str, ...]]:
    (d,) = [d for d in res.dispositions if d.merge_id == claim.merge_id]
    return d.kind, d.targets


def at(now: datetime, *claims: Claim) -> MergeResult:
    return build(match(list(claims), now), window=window_for(now), places=PlaceRegistry.load())


# Task 4's claims (same definitions as in tests/merge/test_match.py).
E = cl(f"{EGU}/r1")
E_PROVISIONAL = cl(f"{EGU}/r1", provisional=True)  # test_match's "pe"
PO = cl(
    "osce:elections/r1",
    provisional=True,
    institution="iso:SE/x",
    office_class="head_of_state",
    office_label="President",
)
PS = cl("osce:elections/r1", provisional=True, span=day(2026, 12, 6))
AG = cl("ndi:p0/upcoming-c1", UMB, provisional=True)
AG_NO = replace(AG, place_id="iso:NO")
RES = cl("eisa:y2026/r3", status_claim="postponed", previous_date_text="1 November 2026")
Y = cl("osce:elections/r24", span=year(2027), office_label="Parliamentary Elections")
H = cl(f"{EGU}/r1", GB, jurisdiction="Holborn and St Pancras", jurisdiction_kind="named")
R = cl(f"{EGU}/r2", GB, jurisdiction="Runcorn and Helsby", jurisdiction_kind="named")
W = cl(f"{WPl}/November/li[3]", GB, jurisdiction_kind="unknown")
X1 = cl(
    f"{WPl}/November/li[2]",
    PE,
    jurisdiction_kind="unknown",
    office_class="mayor",
    office_label="Mayor",
)
X2 = cl(
    "ndi:p0/upcoming-c2",
    PE,
    jurisdiction_kind="unknown",
    office_class="mayor",
    office_label="Mayor",
)
S1 = cl(f"{WPn}/November/li[6]", XS)
S2 = cl("osce:elections/r4", XS, place_raw="S. Ossetia")
LO_SI = cl("osce:elections/r4", SI, UMB, office_label="Local Elections", level="subnational")
LL_SI = cl(f"{WPl}/November/li[4]", SI, UMB, office_label="local elections", level="subnational")
LN_SI = cl(
    "ndi:p0/upcoming-c8",
    SI,
    UMB,
    office_label="2026 Slovenia Local Elections",
    level="subnational",
    span=month(2026, 11),
    date_meaning="unknown",
    date_status="tentative",
)
GD_I = cl("ipu:elections/r105", GD, GD_IPU)
GD_W = cl(f"{WPn}/November/li[2]", GD, LEG)
_PRES = cl(f"{EGU}/r17", PRES_BR)
_MR_BASE = cl("eisa:y2026/r7", PRES_BR, span=month(2026, 10), date_meaning="unknown")
MR = replace(
    _MR_BASE,
    span=month(2026, 12),
    date_text="December 2026",
    status_claim="postponed",
    previous_date_text="15 November 2026",
)
AC = replace(_PRES, status_claim="cancelled")
HO = cl(
    "ndi:p0/past-c9",
    PRES_BR,
    span=month(2026, 10),
    date_meaning="unknown",
    status_claim="held",
    date_text="October 2026",
)
_W1 = cl("eisa:y2026/r7", PRES_BR, MB, round=1)
W1 = _W1
W2 = cl("ndi:p0/upcoming-c4", PRES_BR, MB, round=2, date_status="tentative")
MS = cl(
    f"{WPl}/November/li[1]",
    institution=None,
    office_class="mayor",
    office_label="Mayor",
    level="subnational",
    jurisdiction="Stockholm",
    jurisdiction_kind="named",
)
PZ = cl(
    f"{EGU}/r2",
    institution="iso:SE/president",
    office_class="head_of_state",
    office_label="President",
    date_status="confirmed",
)
N_N = cl("ndi:p0/upcoming-c1", UMB, level="national")
MA = cl(
    f"{WPl}/November/li[1]/li[1]",
    PE,
    jurisdiction="Lima",
    jurisdiction_kind="named",
    office_class="mayor",
    office_label="Mayor",
)
MC = cl(
    f"{WPl}/November/li[1]/li[2]",
    PE,
    jurisdiction="Lima",
    jurisdiction_kind="named",
    office_class="local_council",
    office_label="Municipal council",
)
U_PE = cl("ndi:p0/upcoming-c1", PE, UMB, office_label="2026 Peru Municipal Elections")
P1 = cl(f"{EGP}/r4", BRP, round=1, span=day(2026, 10, 4))
P2 = cl(f"{EGU}/r3", BRP, round=2, span=day(2026, 10, 25))
GB_GOV = cl(
    f"{WPl}/October/li[9]/li[1]",
    BR,
    institution=None,
    office_class="governor",
    office_label="Governor",
    level="subnational",
    jurisdiction="Bahia",
    jurisdiction_kind="subdivision",
    round=2,
    span=day(2026, 10, 25),
)
RF = cl(
    f"{WPn}/October/li[6]/li[4]",
    BR,
    institution=None,
    office_class="referendum",
    kind="referendum_day",
    office_label="Referendum",
    span=day(2026, 10, 25),
)
U_BR = cl(
    "aweb:calendar/r27",
    BR,
    UMB,
    office_label="2026 Brazilian General Elections (2nd round)",
    round=2,
    span=day(2026, 10, 25),
)
O_MONTH = mk("carter:observed/r1", **OBS, span=month(2026, 11))
O_NO = mk("carter:observed/r1", **OBS, span=month(2026, 11), place_id="iso:NO")
EYS = mk("eeas:missions/r1c1", **OBS, span=year(2026), date_text="2026")
EY_CO = cl("eeas:missions/r1c1", OBS, CO, span=year(2026), date_text="2026")
LO50 = cl(f"{EGP}/r50", LOWER, span=day(2026, 3, 8))
UP51 = cl(f"{EGP}/r51", UPPER, span=day(2026, 3, 8))
CANC = mk("osce:elections/r1", status_claim="cancelled", span=day(2026, 9, 13))
HFB = mk(
    f"{EGP}/r1",
    status_claim="held",
    span=day(2026, 9, 13),
    fallback=True,
    fetched_at=datetime(2026, 9, 1, tzinfo=UTC),
)
HLD = mk(f"{EGP}/r1", status_claim="held", span=day(2026, 9, 13))


# ---------------------------------------------------------------- display label and type


@pytest.mark.parametrize(
    ("label", "round_", "jurisdiction", "kind", "want"),
    [
        ("Brazilian Presidency", 2, None, "nationwide", "Brazilian Presidency (2nd round)"),
        ("President (2nd round)", 2, None, "nationwide", "President (2nd round)"),
        ("Senate", 1, None, "nationwide", "Senate (1st round)"),
        ("Senate", 3, None, "nationwide", "Senate (3rd round)"),
        ("Senate", 4, None, "nationwide", "Senate (4th round)"),
        (
            "House of Commons by-election",
            None,
            "Holborn and St Pancras",
            "named",
            "Holborn and St Pancras: House of Commons by-election",
        ),
        (
            "Holborn and St Pancras by-election",
            None,
            "Holborn and St Pancras",
            "named",
            "Holborn and St Pancras by-election",
        ),
        ("Governor", 2, "Bahia", "subdivision", "Bahia: Governor (2nd round)"),
        ("Mayor", None, "Hamilton", "unknown", "Mayor"),
    ],
    ids=[
        "round-2-added",
        "round-already-in-label",
        "1st",
        "3rd",
        "4th",
        "prefix-added",
        "label-names-jurisdiction",
        "prefix-and-round",
        "unknown-kind-no-prefix",
    ],
)
def test_display_label(
    label: str, round_: int | None, jurisdiction: str | None, kind: str, want: str
) -> None:
    child = only_child(result(mk("electionguide:upcoming/r1")))
    changed = replace(
        child,
        office_label=label,
        round=round_,
        jurisdiction=jurisdiction,
        jurisdiction_kind=kind,  # type: ignore[arg-type]
    )
    assert display_label(changed) == want


GOV = dict(
    **BR,
    institution=None,
    office_class="governor",
    office_label="Governor",
    level="subnational",
    jurisdiction_kind="subdivision",
    span=day(2026, 10, 4),
)
CA = dict(
    place_id="iso:CA",
    place_raw="Canada",
    institution=None,
    office_class="mayor",
    office_label="Mayor",
    level="subnational",
    jurisdiction_kind="named",
    span=day(2026, 10, 26),
)


def gov(i: int, name: str) -> Claim:
    return cl(f"{WPl}/October/li[1]/li[1]/li[{i}]", GOV, jurisdiction=name)


def ca(i: int, name: str | None, **fields: Any) -> Claim:
    return cl(f"{WPl}/October/li[7]/li[{i}]", CA, jurisdiction=name, **fields)


_STATES = [f"State number {i:02d} with a long name" for i in range(1, 31)]
_LONG = "Election of the " + "very " * 50 + "long council"
_COUNCILS = [
    ca(
        i,
        None,
        jurisdiction_kind="unknown",
        office_class="local_council",
        office_label=f"Council number {i:02d} of the region",
    )
    for i in range(1, 12)
]
_MAYOR_UNKNOWN = cl(f"{WPl}/October/li[8]", CA, jurisdiction_kind="unknown")

CARD_TYPES = {
    "plural-sorted": (
        [gov(1, "Bahia"), gov(2, "Alagoas"), gov(3, "Amazonas")],
        "Governors: Alagoas, Amazonas, Bahia (3)",
    ),
    "plural-cut": (
        [gov(i, name) for i, name in enumerate(_STATES, 1)],
        "Governors: " + ", ".join(_STATES[:5]) + " (+25 more) (30)",
    ),
    "comma-separator": (
        [ca(1, "Ontario, Hamilton"), ca(2, "Ontario, Ottawa")],
        "Mayors: Ontario, Hamilton; Ontario, Ottawa (2)",
    ),
    "two-classes": (
        [
            ca(1, "Hamilton"),
            ca(2, "Hamilton", office_class="local_council", office_label="City council"),
        ],
        "Hamilton: Mayor · Hamilton: City council",
    ),
    "unknown-jurisdiction": (
        [
            ca(1, "Hamilton"),
            cl("ndi:p0/upcoming-c3", CA, jurisdiction="Hamilton", jurisdiction_kind="unknown"),
        ],
        "Mayor · Hamilton: Mayor",
    ),
    "single-long": (
        [ca(1, None, jurisdiction_kind="unknown", office_label=_LONG)],
        _LONG[:199] + "…",
    ),
    "run-cut": (
        [*_COUNCILS, _MAYOR_UNKNOWN],
        "Mayor · Council number 05 of the region · Council number 01 of the region"
        " · Council number 07 of the region · Council number 03 of the region"
        " · Council number 06 of the region (+6 more)",
    ),
    "two-classes-two-places": (
        [
            ca(1, "Hamilton"),
            ca(2, "Ottawa", office_class="local_council", office_label="City council"),
        ],
        "Hamilton: Mayor · Ottawa: City council",
    ),
    "x1-x2": ([X1, X2], "Mayor · Mayor"),
    "h-r": ([H, R], "Lower houses: Holborn and St Pancras, Runcorn and Helsby (2)"),
}


@pytest.mark.parametrize(("claims", "want"), CARD_TYPES.values(), ids=list(CARD_TYPES))
def test_card_type(claims: list[Claim], want: str) -> None:
    card = only_card(result(*claims))
    assert card.type == want
    assert card_type(card.children) == want
    assert len(want) <= 200
    assert len(card.children) == len(claims)


def test_card_type_counts_the_suffix_inside_the_limit() -> None:
    labels = [f"Council {i} " + "n" * 54 for i in range(5)]
    assert {len(label) for label in labels} == {64}
    councils = [
        ca(i, None, jurisdiction_kind="unknown", office_class="local_council", office_label=label)
        for i, label in enumerate(labels, 1)
    ]
    card = only_card(result(*councils))
    shown = [c.office_label for c in card.children]
    assert sorted(shown) == sorted(labels)
    # three labels take 198 characters, but with " (+2 more)" they take 208: two are shown
    assert card.type == " · ".join(shown[:2]) + " (+3 more)"


# ---------------------------------------------------------------- children


def test_child_fields_brazil_round_two() -> None:
    a = cl(
        f"{EGU}/r3",
        BR,
        institution="iso:BR/president",
        office_class="head_of_state",
        office_label="Brazilian Presidency",
        round=2,
        span=day(2026, 10, 25),
        date_status="confirmed",
        link="https://eg.test/3",
    )
    b = cl(
        f"{WPn}/October/li[6]/li[3]",
        BR,
        institution="iso:BR/president",
        office_class="head_of_state",
        office_label="President (2nd round)",
        round=2,
        span=day(2026, 10, 25),
        indirect=True,
        link="https://wp.test/n",
    )
    u = cl(
        "aweb:calendar/r27", BR, UMB, round=2, span=day(2026, 10, 25), link="https://aweb.test/27"
    )
    o = mk(
        "carter:observed/r1",
        **OBS,
        place_id="iso:BR",
        span=month(2026, 10),
        link="https://carter.test/1",
    )
    card = only_card(result(a, b, u, o))
    assert card.group_id == "4b35f9d2401c"
    (child,) = card.children
    assert child.child_id == "8e4a9a33e280"
    assert (child.office_label, child.office_class, child.kind, child.level) == (
        "Brazilian Presidency",
        "head_of_state",
        "candidate_election",
        "national",
    )
    assert (child.round, child.institution) == (2, "iso:BR/president")
    assert (child.jurisdiction, child.jurisdiction_kind) == (None, "nationwide")
    assert child.indirect is True
    assert child.occurrence_confirmed is False
    assert (child.date_status, child.date_meaning) == ("confirmed", "voting_period")
    assert sources(child) == [
        (a, True, None),
        (b, False, "less_certain"),
        (o, False, "observation"),
    ]
    assert card.sources == bib(
        ("electionguide", "https://eg.test/3"),
        ("wikipedia", "https://wp.test/n"),
        ("aweb", "https://aweb.test/27"),
        ("carter", "https://carter.test/1"),
    )
    assert card.umbrella_sources == bib(("aweb", "https://aweb.test/27"))
    assert card.umbrellas == (u,)
    assert card.type == "Brazilian Presidency (2nd round)"
    assert (card.country, card.country_code) == ("Brazil", "BR")


def test_child_fields_holborn_two_sources() -> None:
    w = cl(
        f"{WPl}/October/li[3]/li[2]",
        GB,
        jurisdiction="Holborn and St Pancras",
        jurisdiction_kind="named",
        span=day(2026, 10, 8),
        link="https://wp.test/l",
    )
    e = cl(
        f"{EGP}/r9",
        GB,
        jurisdiction="Holborn and St Pancras",
        jurisdiction_kind="named",
        span=day(2026, 10, 8),
        office_label="Holborn and St Pancras by-election",
        status_claim="held",
        link="https://eg.test/9",
    )
    card = only_card(result(w, e))
    assert card.group_id == "cc453aae6835"
    (child,) = card.children
    assert child.child_id == "083a130d3044"
    assert child.office_label == "Holborn and St Pancras by-election"
    assert child.occurrence_confirmed is True
    assert child.status == "Held"
    assert card.type == "Holborn and St Pancras by-election"
    alone = only_card(result(w))
    assert alone.children[0].child_id == "1d3694a58ae8"
    assert alone.type == "Holborn and St Pancras: House of Commons by-election"


def test_child_fields_renewal_only_has_its_card_key() -> None:
    ipu = mk(
        "ipu:elections/r9",
        **RENEW,
        place_id="iso:LY",
        institution="iso:LY/house-of-representatives",
        office_class="lower_house",
        office_label="House of Representatives",
        span=month(2026, 12),
    )
    card = only_card(result(ipu))
    (child,) = card.children
    assert (child.date_status, child.date_meaning, child.status) == (
        "tentative",
        "expected_window",
        "Upcoming",
    )
    key = ("iso:LY", "national", "2026-12-01", "2026-12-31", "month", "expected_window")
    assert card.group_id == short_id(["|".join([*key, "tentative", "Upcoming"])])


def test_child_fields_aggregate() -> None:
    res = result(LL_SI, LN_SI, LO_SI)
    child = only_child(res)
    assert child.aggregate is True
    assert (child.office_label, child.office_class, child.kind, child.level) == (
        "Local Elections",
        "general",
        "aggregate",
        "subnational",
    )
    assert sources(child) == [
        (LO_SI, True, None),
        (LL_SI, False, "lower_priority"),
        (LN_SI, False, "not_covering"),
    ]


def test_child_fields_label_claim_skips_an_attached_aggregate() -> None:
    child = only_child(result(GD_I, GD_W))
    assert child.office_label == "House of Representatives"
    assert child.aggregate is False
    assert child.office_class == "lower_house"


def test_child_fields_provisional_source() -> None:
    ps = replace(PS, link="https://osce.test/p")
    card = only_card(result(E, ps))
    (child,) = card.children
    assert sources(child) == [(E, True, None), (ps, False, "provisional")]
    assert child.date_conflict is True
    assert child.provisional_date == "moved"
    assert card.sources == bib(("electionguide", "https://example.test/e"))


def test_child_fields_umbrella_walk_is_separate() -> None:
    r = cl(f"{WPn}/November/li[1]", link="https://wp.test/n")
    u = cl(f"{WPl}/November/li[2]", UMB, link="https://wp.test/l")
    card = only_card(result(r, u))
    assert card.sources == bib(("wikipedia", "https://wp.test/n"))
    assert card.umbrella_sources == bib(("wikipedia", "https://wp.test/l"))


def test_child_fields_rescheduling() -> None:
    card = only_card(result(RES))
    assert card.group_id == "5a94ef2ae3fe"
    (child,) = card.children
    assert child.child_id == "e3ee8e8e7dce"
    assert child.status == "Upcoming"
    assert child.rescheduled_from == ("1 November 2026",)
    assert child.status_conflict is False
    assert child.occurrence_confirmed is False
    ro = mk("osce:elections/r1", status_claim="postponed", previous_date_text="1  November 2026")
    child = only_child(result(RES, ro))
    assert child.child_id == "02bc80fb0ffd"
    assert child.rescheduled_from == ("1 November 2026",)
    ro8 = replace(ro, previous_date_text="8 November 2026")
    child = only_child(result(RES, ro8))
    assert child.rescheduled_from == ("1 November 2026", "8 November 2026")


def test_child_fields_cancellation_beside_a_cached_and_a_fresh_held_claim() -> None:
    card = only_card(result(CANC, HFB))
    assert card.group_id == "592ecabeb549"
    (child,) = card.children
    assert child.child_id == "4c9b2569520e"
    assert child.status == "Cancelled"
    assert child.status_conflict is False
    assert child.occurrence_confirmed is False
    card = only_card(result(CANC, HLD))
    assert card.group_id == "4d7199437e03"
    (child,) = card.children
    assert child.child_id == "4c9b2569520e"
    assert child.status == "Held"
    assert child.status_conflict is True
    assert child.occurrence_confirmed is True


def test_child_fields_cached_held_claim_still_confirms_the_vote() -> None:
    card = only_card(result(HFB))
    assert card.group_id == "4d7199437e03"
    (child,) = card.children
    assert child.child_id == "436692e1eac7"
    assert child.status == "Held"
    assert child.occurrence_confirmed is True
    assert child.unverified is True
    assert child.status_conflict is False
    (source,) = child.sources
    assert source.claim.fallback is True
    assert source.claim.fetched_at == datetime(2026, 9, 1, tzinfo=UTC)


def test_child_fields_held_for_another_month_beside_a_cancellation() -> None:
    card = only_card(result(AC, HO))
    assert card.group_id == "fca7f03c19fd"
    (child,) = card.children
    assert child.child_id == "12986edb4195"
    assert child.status == "Cancelled"
    assert child.occurrence_confirmed is False
    assert child.date_conflict is True
    assert child.status_conflict is True
    assert sources(child) == [(AC, True, None), (HO, False, "not_covering")]


def test_child_fields_held_for_another_month_without_a_cancellation() -> None:
    card = only_card(result(_PRES, HO))
    assert card.group_id == "2dc6c54b64ad"
    (child,) = card.children
    assert child.child_id == "12986edb4195"
    assert child.status == "Upcoming"
    assert child.span == day(2026, 11, 15)
    assert child.occurrence_confirmed is False
    assert child.date_conflict is True
    assert child.status_conflict is False


def test_child_occurrence_ignores_observations() -> None:
    held_obs = mk("carter:observed/r1", **OBS, span=day(2026, 9, 13), status_claim="held")
    pending = replace(E, span=day(2026, 9, 13))
    child = only_child(result(pending, held_obs))
    assert child.status == "Held"
    assert child.occurrence_confirmed is False
    assert sources(child)[1][2] == "observation"


@pytest.mark.parametrize(
    ("now", "group", "status"),
    [
        (datetime(2026, 11, 10, 12, tzinfo=UTC), "d8b9f8d1f6a1", "Upcoming"),
        (datetime(2026, 11, 20, 12, tzinfo=UTC), "d8b9f8d1f6a1", "Upcoming"),
        (datetime(2027, 1, 5, 12, tzinfo=UTC), "7c1e513c7a94", "Held"),
    ],
    ids=["before-old-date", "between-old-and-new", "after-new-date"],
)
def test_a_rescheduled_child_follows_its_new_date(now: datetime, group: str, status: str) -> None:
    card = only_card(at(now, _PRES, MR))
    assert card.group_id == group
    (child,) = card.children
    assert child.child_id == "12986edb4195"
    assert child.span == month(2026, 12)
    assert child.status == status
    assert child.rescheduled_from == ("15 November 2026",)
    assert child.date_conflict is True
    assert child.status_conflict is False
    assert child.occurrence_confirmed is False
    assert sources(child) == [(_PRES, False, "old_date"), (MR, True, None)]
    assert card.span == month(2026, 12)


def test_cards_split_by_certainty_and_meaning() -> None:
    eg = cl(f"{EGU}/r1", date_status="confirmed")
    president = cl(
        f"{WPn}/November/li[4]",
        institution="iso:SE/x",
        office_class="head_of_state",
        office_label="President",
    )
    res = result(eg, president)
    by_id = {c.group_id: c for c in res.cards}
    assert sorted(by_id) == ["5a94ef2ae3fe", "ad1a3d3732e2"]
    assert (by_id["ad1a3d3732e2"].type, by_id["ad1a3d3732e2"].date_status) == (
        "Riksdag",
        "confirmed",
    )
    assert (by_id["5a94ef2ae3fe"].type, by_id["5a94ef2ae3fe"].date_status) == (
        "President",
        "unknown",
    )
    aweb = cl(
        "aweb:calendar/r1",
        institution="iso:SE/x",
        office_class="head_of_state",
        office_label="President",
        date_meaning="unknown",
    )
    res = result(E, aweb)
    by_id = {c.group_id: c for c in res.cards}
    assert sorted(by_id) == ["47c3a41c029d", "5a94ef2ae3fe"]
    assert (by_id["47c3a41c029d"].type, by_id["47c3a41c029d"].date_meaning) == (
        "President",
        "unknown",
    )
    assert by_id["5a94ef2ae3fe"].type == "Riksdag"


def test_child_identity_through_split_and_rejoin() -> None:
    brd = dict(place_id="iso:BR", span=day(2026, 10, 4))
    a = cl(
        f"{EGP}/r4",
        brd,
        institution="iso:BR/president",
        office_class="head_of_state",
        office_label="Presidency",
    )
    b1 = cl(
        f"{EGP}/r7",
        brd,
        institution="iso:BR/chamber",
        office_class="lower_house",
        office_label="Chamber",
    )
    b2 = replace(b1, span=day(2026, 10, 11))

    def shape(res: MergeResult) -> list[tuple[str, list[str], str]]:
        return [(c.group_id, [k.child_id for k in c.children], c.type) for c in res.cards]

    first = shape(result(a, b1))
    assert first == [("5ddc43ed3758", ["6d12862ffe3c", "7455554d41e3"], "Presidency · Chamber")]
    assert shape(result(a, b2)) == [
        ("5ddc43ed3758", ["6d12862ffe3c"], "Presidency"),
        ("a6dd778a0f69", ["7455554d41e3"], "Chamber"),
    ]
    assert shape(result(a, b1)) == first


def test_children_are_sorted_by_class_then_jurisdiction_then_id() -> None:
    res = result(H, R)
    names = [c.jurisdiction for c in only_card(res).children]
    assert names == ["Holborn and St Pancras", "Runcorn and Helsby"]
    classes = ["local_council", "upper_house", "mayor", "legislature", "governor", "lower_house"]
    res = result(
        *(
            ca(i, None, jurisdiction_kind="unknown", office_class=c, office_label=f"Office {c}")
            for i, c in enumerate(classes, 1)
        )
    )
    assert [c.office_class for c in only_card(res).children] == [
        "lower_house",
        "upper_house",
        "legislature",
        "governor",
        "mayor",
        "local_council",
    ]
    # a tie on class and jurisdiction falls to the child id
    res = result(X1, X2)
    ids = [c.child_id for c in only_card(res).children]
    assert ids == sorted(ids)


# ---------------------------------------------------------------- relevance


@pytest.mark.parametrize(
    ("span", "want"),
    [
        (day(2026, 8, 31), "before_window"),
        (day(2026, 9, 1), "in_or_after_window"),
        (months(2026, 8, 2026, 9), "in_or_after_window"),
        (month(2026, 8), "before_window"),
        (day(2027, 5, 1), "in_or_after_window"),
        (year(2026), "in_or_after_window"),
        (year(2025), "before_window"),
    ],
    ids=[
        "day-before",
        "day-first",
        "months-straddling",
        "month-before",
        "far-future",
        "this-year",
        "last-year",
    ],
)
def test_relevance_of(span: DateSpan, want: Relevance) -> None:
    window = window_for(NOW)
    assert (window.start, window.end) == (date(2026, 9, 1), date(2027, 1, 31))
    assert relevance_of(mk("electionguide:upcoming/r1", span=span), window) == want


# ---------------------------------------------------------------- attention items


def test_attention_items_undated_listing() -> None:
    res = result(Y)
    (listing,) = res.undated
    assert listing.undated_id == "5e735b978230"
    assert (listing.place_id, listing.country, listing.office_label, listing.year) == (
        "iso:SE",
        "Sweden",
        "Parliamentary Elections",
        2027,
    )
    assert listing.claims == (Y,)
    assert listing.sources == bib(("osce", "https://example.test/e"))
    assert listing.possible_matches == ()
    (item,) = res.attention
    assert item.item_id == "fb4c9d1c4882"
    assert (item.kind, item.reason, item.relevance) == (
        "undated_listing",
        "undated",
        "in_or_after_window",
    )
    assert item.text == "Sweden: Parliamentary Elections (2027), date not given"
    assert item.merge_ids == ("served/osce:elections/r24#0",)
    assert item.undated_id == "5e735b978230"
    assert (item.source, item.link, item.snapshot_id) == (
        "osce",
        "https://example.test/e",
        None,
    )
    assert item.possible_matches == ()
    assert res.dispositions[0].kind == "undated"
    assert disposition(res, Y) == ("undated", ("5e735b978230",))


def test_attention_items_listing_with_possible_matches_and_two_claims() -> None:
    a = cl(f"{EGU}/r60", span=day(2027, 9, 12))
    b = cl(f"{EGU}/r61", span=day(2027, 3, 14))
    res = result(a, b, Y)
    (listing,) = res.undated
    both = sorted(k.child_id for card in res.cards for k in card.children)
    assert len(both) == 2
    assert listing.possible_matches == tuple(both)
    (item,) = res.attention
    assert item.possible_matches == listing.possible_matches
    y2 = cl(
        "wikipedia:national-2027@rev3/Unknown_date/li[1]",
        span=year(2027),
        office_label="Parliamentary Elections",
        link="https://wp.test/y",
    )
    res = result(Y, y2)
    (listing,) = res.undated
    assert listing.claims == (Y, y2)
    assert listing.sources == bib(
        ("osce", "https://example.test/e"), ("wikipedia", "https://wp.test/y")
    )
    (item,) = res.attention
    assert item.merge_ids == tuple(sorted(c.merge_id for c in (Y, y2)))
    assert listing.undated_id == short_id(["undated", Y.merge_id, y2.merge_id])
    assert item.item_id == short_id(["undated_listing", listing.undated_id])


def test_attention_items_several_candidates() -> None:
    res = result(H, R, W)
    (item,) = res.attention
    assert item.item_id == "c43265173fa1"
    assert (item.kind, item.reason, item.relevance) == (
        "unresolved_evidence",
        "several_candidates",
        "in_or_after_window",
    )
    assert item.text == "United Kingdom: House of Commons by-election (15 November 2026)"
    assert item.possible_matches == ("605682096ffe", "e70aa2e8fc49")
    assert item.merge_ids == (W.merge_id,)
    assert (item.source, item.link) == ("wikipedia", W.link)


def test_attention_items_provisional_change() -> None:
    res = result(E, PO)
    (item,) = res.attention
    assert item.item_id == "6d7737459737"
    assert (item.kind, item.reason) == ("provisional_change", "no_candidate")
    assert item.text == "Sweden: President (15 November 2026), from an incomplete fetch"


def test_attention_items_provisional_aggregate() -> None:
    res = result(AG, E)
    (item,) = res.attention
    assert item.item_id == "c0b91467ada1"
    assert (item.kind, item.reason) == ("provisional_change", "provisional_aggregate")
    assert item.possible_matches == ("605682096ffe",)
    assert item.text == "Sweden: General elections (15 November 2026), from an incomplete fetch"
    res = result(AG_NO)
    (item,) = res.attention
    assert item.item_id == "c0b91467ada1"
    assert item.possible_matches == ()
    assert item.text == "Norway: General elections (15 November 2026), from an incomplete fetch"


def test_attention_items_conflicting_claims_sorted_by_item_id() -> None:
    res = result(_PRES, W1, W2)
    assert [i.item_id for i in res.attention] == ["82d1189a7079", "fb5d5d211420"]
    by_id = {i.item_id: i for i in res.attention}
    assert by_id["fb5d5d211420"].merge_ids == (W1.merge_id,)
    assert by_id["82d1189a7079"].merge_ids == (W2.merge_id,)
    for item in res.attention:
        assert (item.kind, item.reason, item.relevance) == (
            "unresolved_evidence",
            "conflicting_claims",
            "in_or_after_window",
        )
        assert item.text == "Brazil: President (November 2026)"
        assert item.possible_matches == ("12986edb4195",)
    assert disposition(res, W1)[0] == "attention"
    assert disposition(res, W2)[0] == "attention"
    assert disposition(res, W1)[1] == ("fb5d5d211420",)
    assert disposition(res, W2)[1] == ("82d1189a7079",)


def test_attention_text_is_collapsed_and_cut() -> None:
    long = mk(
        "carter:observed/r1",
        **{**OBS, "office_label": "Mission   " + "x" * 400},
        span=month(2026, 12),
    )
    (item,) = result(long).attention
    assert len(item.text) == 300
    assert item.text.startswith("Sweden: Mission x")
    assert "  " not in item.text


def test_year_only_observation_stays_accounted_for() -> None:
    y25 = mk("eeas:missions/r2c1", **OBS, place_id="iso:NO", span=year(2025), date_text="2025")
    res = result(EYS, y25)
    by_id = {i.item_id: i for i in res.attention}
    assert sorted(by_id) == ["ed745bd6cbe3", "ff7c82d7217d"]
    sweden, norway = by_id["ff7c82d7217d"], by_id["ed745bd6cbe3"]
    assert (sweden.reason, sweden.relevance) == ("no_candidate", "in_or_after_window")
    assert sweden.text == "Sweden: Election observation mission (2026)"
    assert (norway.reason, norway.relevance) == ("no_candidate", "before_window")
    assert norway.text == "Norway: Election observation mission (2025)"
    assert sorted(d.merge_id for d in res.dispositions) == sorted([EYS.merge_id, y25.merge_id])

    res = result(EY_CO, LO50, UP51)
    (item,) = res.attention
    assert item.item_id == "ff7c82d7217d"
    assert (item.reason, item.relevance) == ("several_candidates", "in_or_after_window")
    assert item.possible_matches == ("a0ff75f39c29", "def863669d34")
    assert item.text == "Colombia: Election observation mission (2026)"
    assert len(res.dispositions) == 3

    up51_nov = cl(f"{EGU}/r51", UPPER, span=day(2026, 11, 22))
    res = result(EY_CO, LO50, up51_nov)
    (item,) = res.attention
    assert item.relevance == "in_or_after_window"
    assert item.possible_matches == ("a0ff75f39c29", "c908a5427792")
    assert len(res.dispositions) == 3

    hist = mk("carter:observed/r2", **OBS, span=month(2026, 3), date_text="March 2026")
    res = result(hist)
    (item,) = res.attention
    assert item.item_id == "3555993a0822"
    assert (item.reason, item.relevance) == ("no_candidate", "before_window")
    assert item.text == "Sweden: Election observation mission (March 2026)"
    assert len(res.dispositions) == 1


# ---------------------------------------------------------------- display names


def test_unknown_place_shows_its_raw_name() -> None:
    eg = mk("electionguide:upcoming/r1", place_id="x:atlantis", place_raw="Atlantis")
    carter = mk(
        "carter:observed/r1",
        **OBS,
        place_id="x:atlantis",
        place_raw="Atlantis",
        span=month(2026, 12),
    )
    res = result(eg, carter)
    card = only_card(res)
    assert card.group_id == "770bb0b91a94"
    assert (card.country, card.country_code) == ("Atlantis", None)
    assert (card.children[0].country, card.children[0].country_code) == ("Atlantis", None)
    (item,) = res.attention
    assert item.item_id == "39e8c2860ac1"
    assert item.text == "Atlantis: Election observation mission (15 November 2026)"
    card = only_card(result(S1, S2))
    assert (card.country, card.country_code) == ("South Ossetia", None)
    card = only_card(result(E))
    assert (card.country, card.country_code) == ("Sweden", "SE")


# ---------------------------------------------------------------- dispositions


def test_dispositions_umbrella_link_targets_are_child_ids() -> None:
    res = result(MS, N_N, PZ, E)
    assert disposition(res, N_N) == ("umbrella_link", ("605682096ffe", "e70aa2e8fc49"))
    assert sorted(c.group_id for c in res.cards if c.umbrellas) == ["5a94ef2ae3fe", "ad1a3d3732e2"]
    mayor = next(c for c in res.cards if c.children[0].office_class == "mayor")
    assert mayor.umbrellas == ()
    assert mayor.children[0].child_id not in disposition(res, N_N)[1]


def test_dispositions_two_children_of_one_card() -> None:
    res = result(MA, MC, U_PE)
    assert disposition(res, U_PE) == ("umbrella_link", ("35bd1312dc95", "e8c2e0c4e454"))
    assert len(res.cards) == 1


def test_dispositions_umbrella_covering_part_of_a_card() -> None:
    res = result(GB_GOV, P1, P2, RF, U_BR)
    assert disposition(res, U_BR) == ("umbrella_link", ("84c968bd489c",))
    card = next(c for c in res.cards if c.group_id == "862446e7b7ab")
    assert sorted(k.child_id for k in card.children) == ["84c968bd489c", "88e61e82732a"]
    assert card.umbrellas == (U_BR,)


def test_dispositions_kinds_and_targets() -> None:
    res = result(E, O_MONTH)
    child = only_child(res)
    assert disposition(res, E) == ("anchor_member", (child.child_id,))
    assert disposition(res, O_MONTH) == ("attached", (child.child_id,))

    res = result(X1, X2)
    for c in (X1, X2):
        kind, (target,) = disposition(res, c)
        assert kind == "standalone"
        assert target in {k.child_id for card in res.cards for k in card.children}
    assert disposition(res, X1)[1] != disposition(res, X2)[1]

    res = result(LL_SI, LN_SI, LO_SI)
    child = only_child(res)
    for c in (LL_SI, LN_SI, LO_SI):
        assert disposition(res, c) == ("standalone", (child.child_id,))

    res = result(E, E_PROVISIONAL)
    assert disposition(res, E_PROVISIONAL) == ("provisional", (only_child(res).child_id,))
    assert disposition(result(Y), Y)[0] == "undated"
    res = result(O_NO)
    (item,) = res.attention
    assert disposition(res, O_NO) == ("attention", (item.item_id,))


def test_dispositions_are_sorted_by_merge_id() -> None:
    res = result(MS, N_N, PZ, E, O_NO, Y)
    ids = [d.merge_id for d in res.dispositions]
    assert ids == sorted(ids)
    assert len(ids) == 6


# ---------------------------------------------------------------- the order of cards


def test_cards_are_sorted_by_date_then_place_then_group_id() -> None:
    claims = [cl(f"{EGU}/r{i}", span=day(2026, 11, 1 + i)) for i in range(1, 7)]
    claims.append(cl(f"{EGU}/r7", PRES_BR, span=day(2026, 11, 2)))
    claims.append(
        cl(
            f"{EGU}/r8",
            institution="iso:SE/x",
            office_class="lower_house",
            office_label="Chamber",
            span=day(2026, 11, 2),
            date_status="confirmed",
        )
    )
    res = result(*claims)
    assert len(res.cards) == 8
    order = [(c.span.start, c.place_id, c.group_id) for c in res.cards]
    assert order == sorted(order)
    assert [(c.span.start, c.place_id) for c in res.cards][:3] == [
        (date(2026, 11, 2), "iso:BR"),
        (date(2026, 11, 2), "iso:SE"),
        (date(2026, 11, 2), "iso:SE"),
    ]
