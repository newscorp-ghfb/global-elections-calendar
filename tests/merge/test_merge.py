"""Task 6: ``merge`` (spec 10.8, 10.9; S3-T5, T8, T16; NM-T06; G03, G08)."""

from dataclasses import replace
from datetime import datetime
from itertools import permutations
from random import Random
from typing import Any

import pytest
from hypothesis import HealthCheck, example, given, seed, settings
from hypothesis import strategies as st

import elections_calendar.merge as merge_package
from elections_calendar.merge import MergeError, merge
from elections_calendar.merge.cards import build
from elections_calendar.merge.conservation import check
from elections_calendar.merge.match import match
from elections_calendar.model import Claim, MergeResult
from elections_calendar.places import PlaceRegistry
from elections_calendar.window import window_for
from tests.support.claims import (
    BR,
    BRP,
    EGP,
    EGU,
    MB,
    NOW,
    OBS,
    PRES_BR,
    RENEW,
    RU,
    UMB,
    WPn,
    cl,
    day,
    days,
    list_order,
    mk,
    month,
    year,
)

PLACES = PlaceRegistry.load()
BR_FIELDS: dict[str, Any] = BR

# Task 4's claims, rebuilt from their definitions
PHASE_A = [
    cl(f"{EGP}/r12", RU, span=day(2026, 9, 18)),
    cl("osce:elections/r33", RU, span=day(2026, 9, 19)),
    cl(f"{WPn}/September/li[3]", RU, span=day(2026, 9, 20)),
    cl("ndi:p0/past-c3", RU, span=day(2026, 9, 21)),
    cl("aweb:calendar/r23", RU, span=days(2026, 9, 18, 2026, 9, 21)),
]
ROUNDS = [
    cl(f"{EGP}/r4", PRES_BR, round=1, span=day(2026, 10, 4)),
    cl(f"{EGU}/r3", PRES_BR, round=2, span=day(2026, 10, 25)),
    cl(f"{WPn}/October/li[2]", PRES_BR, span=day(2026, 10, 4)),
]
ATTACH = [
    cl(f"{EGU}/r17", PRES_BR),
    cl("eisa:y2026/r7", PRES_BR, MB, round=1),
    cl("ndi:p0/upcoming-c4", PRES_BR, MB, round=2, date_status="tentative"),
]
_u = cl("aweb:calendar/r27", BR, UMB, office_label="2026 Brazilian General Elections (2nd round)",
        round=2, span=day(2026, 10, 25))
BRAZIL = [
    cl(f"{EGU}/r3", BRP, round=2, span=day(2026, 10, 25)),
    cl(f"{EGP}/r4", BRP, round=1, span=day(2026, 10, 4)),
    cl(f"{WPn}/October/li[9]/li[1]", BR, institution=None, office_class="governor",
       office_label="Governor", level="subnational", jurisdiction="Bahia",
       jurisdiction_kind="subdivision", round=2, span=day(2026, 10, 25)),
    cl(f"{WPn}/October/li[6]/li[4]", BR, institution=None, office_class="referendum",
       kind="referendum_day", office_label="Referendum", span=day(2026, 10, 25)),
    _u,
]


def test_merge_runs_the_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = build(match(BRAZIL, NOW), window=window_for(NOW), places=PLACES)
    assert merge(BRAZIL, now=NOW, places=PLACES) == expected

    def lossy(*args: Any, **kwargs: Any) -> MergeResult:
        res = build(*args, **kwargs)
        return replace(res, dispositions=res.dispositions[:-1])

    monkeypatch.setattr(merge_package, "build", lossy)
    with pytest.raises(MergeError) as err:
        merge(BRAZIL, now=NOW, places=PLACES)
    assert str(err.value).startswith("conservation: no disposition: ")


def test_duplicate_merge_id_stops_the_merge() -> None:
    with pytest.raises(MergeError) as err:
        merge([mk("osce:elections/r1"), mk("osce:elections/r1")], now=NOW, places=PLACES)
    assert str(err.value) == "duplicate merge_id: served/osce:elections/r1#0"


def test_merge_reads_a_one_shot_iterable_once() -> None:
    expected = merge(BRAZIL, now=NOW, places=PLACES)
    assert expected.cards
    assert merge(iter(BRAZIL), now=NOW, places=PLACES) == expected
    assert merge((c for c in BRAZIL), now=NOW, places=PLACES) == expected


def test_match_reads_a_one_shot_iterable_once() -> None:
    expected = list_order(match(BRAZIL, NOW))
    assert expected[0]
    assert list_order(match(iter(BRAZIL), NOW)) == expected


def test_check_reads_a_one_shot_iterable_once() -> None:
    res = merge(BRAZIL, now=NOW, places=PLACES)
    assert check(iter(BRAZIL), res) == ()
    damaged = replace(res, dispositions=res.dispositions[:-1])
    assert check(iter(BRAZIL), damaged) != ()


def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError) as err:
        merge([mk("osce:elections/r1")], now=datetime(2026, 10, 19), places=PLACES)
    assert str(err.value) == "now must be timezone-aware"


def test_replay_is_idempotent() -> None:
    first = merge(BRAZIL, now=NOW, places=PLACES)
    second = merge(BRAZIL, now=NOW, places=PLACES)
    assert first == second
    assert [k.child_id for c in first.cards for k in c.children] == [
        k.child_id for c in second.cards for k in c.children
    ]
    assert [c.group_id for c in first.cards] == [c.group_id for c in second.cards]
    copies = [cl(f"{EGU}/r1", source_event_id="electionguide:5259"),
              cl(f"{EGP}/r1", source_event_id="electionguide:5259")]
    assert merge(copies, now=NOW, places=PLACES) == merge(copies, now=NOW, places=PLACES)


ORDER_SETS = {
    "a-b-c-d-e": PHASE_A,
    "r1-r2-un": ROUNDS,
    "a-w1-w2": ATTACH,
    "brazil-and-observation": [
        *BRAZIL,
        mk("carter:observed/r1", **OBS, **BR_FIELDS, span=month(2026, 10)),
    ],
}


@pytest.mark.parametrize("name", ORDER_SETS)
def test_inputs_in_any_order_give_the_same_result(name: str) -> None:
    claims = ORDER_SETS[name]
    first = merge(claims, now=NOW, places=PLACES)
    first_order = list_order(match(claims, NOW))
    count = 0
    for p in permutations(claims):
        count += 1
        assert merge(list(p), now=NOW, places=PLACES) == first
        assert list_order(match(list(p), NOW)) == first_order
    assert count == {"a-b-c-d-e": 120, "r1-r2-un": 6, "a-w1-w2": 6}.get(name, 720)


# ---------------------------------------------------------------- the property test

SOURCES = ("electionguide:upcoming/r", "osce:elections/r",
           "wikipedia:national-2026@rev1/November/li[", "ndi:p0/upcoming-c",
           "ipu:elections/r", "carter:observed/r", "eeas:missions/r")
OFFICES = (
    dict(institution="iso:SE/riksdag", office_class="legislature", office_label="Riksdag",
         aggregate=False, kind="candidate_election"),
    dict(institution=None, office_class="legislature", office_label="Parliament",
         aggregate=True, kind="candidate_election"),
    dict(institution=None, office_class="general", office_label="General elections",
         aggregate=True, kind="aggregate"),
    dict(institution=None, office_class="mayor", office_label="Mayor", aggregate=False,
         kind="candidate_election"),
    dict(institution=None, office_class="referendum", office_label="Referendum",
         aggregate=False, kind="referendum_day"),
)
SPANS = (day(2026, 11, 1), day(2026, 11, 2), day(2026, 11, 9), month(2026, 11), year(2026),
         day(2027, 1, 10))
claim_st = st.tuples(st.integers(0, len(SOURCES) - 1), st.integers(1, 4),
                     st.integers(0, len(OFFICES) - 1), st.integers(0, len(SPANS) - 1),
                     st.sampled_from([None, 1, 2]), st.sampled_from(["iso:SE", "iso:NO"]),
                     st.sampled_from(["nationwide", "named", "unknown"]), st.booleans(),
                     st.sampled_from([None, "cancelled", "held"]))


def build_claim(t: tuple[Any, ...]) -> Claim:
    s, n, o, sp, rnd, place, jur, prov, status = t
    prefix = SOURCES[s]
    unit = f"{prefix}{n}]" if prefix.endswith("[") else f"{prefix}{n}"
    fields: dict[str, Any] = dict(OFFICES[o])
    if prefix.startswith("ipu"):
        fields.update(RENEW)
    if prefix.startswith(("carter", "eeas")):
        fields.update(OBS)
    fields.update(
        span=SPANS[sp],
        round=rnd,
        place_id=place,
        jurisdiction_kind=jur,
        jurisdiction="Lima" if jur == "named" else None,
        provisional=prov,
        status_claim=status,
    )
    return mk(unit, **fields)


def with_first_source_changed(res: MergeResult, claims: list[Claim]) -> list[str]:
    """``check`` on ``res`` after the first child's first source changes its place text."""
    card = res.cards[0]
    claim = card.children[0].sources[0].claim
    changed = replace(claim, place_raw=claim.place_raw + "x")
    cards = (
        replace(
            card,
            children=(
                replace(
                    card.children[0],
                    sources=(
                        replace(card.children[0].sources[0], claim=changed),
                        *card.children[0].sources[1:],
                    ),
                ),
                *card.children[1:],
            ),
        ),
        *res.cards[1:],
    )
    problems = check(claims, replace(res, cards=cards))
    return [p for p in problems if p == f"changed claim: {claim.merge_id}"]


# At seed 20261019 random lists attach a claim only rarely (7 attached claims over the run) and
# never leave a weak claim with several candidates, so two explicit examples hold those cases.
ATTACHING = [  # an anchor, two attached claims (a month and a year) and a provisional claim
    (0, 1, 0, 0, None, "iso:SE", "nationwide", False, None),
    (1, 1, 0, 3, None, "iso:SE", "nationwide", False, None),
    (3, 2, 0, 4, None, "iso:SE", "nationwide", False, None),
    (1, 2, 0, 0, None, "iso:SE", "nationwide", True, None),
]
SEVERAL = [  # a month claim that fits the round-1 and the round-2 contest
    (0, 1, 0, 0, 1, "iso:SE", "nationwide", False, None),
    (0, 2, 0, 0, 2, "iso:SE", "nationwide", False, None),
    (3, 1, 0, 3, None, "iso:SE", "nationwide", False, None),
]


@seed(20261019)
@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@example(ATTACHING, Random(7))
@example(SEVERAL, Random(7))
@given(st.lists(claim_st, min_size=1, max_size=9), st.randoms(use_true_random=False))
def test_property_any_order_and_conservation(tuples: list[Any], rnd: Random) -> None:
    unique: dict[str, Claim] = {}
    for t in tuples:
        c = build_claim(t)
        unique.setdefault(c.merge_id, c)
    claims = list(unique.values())
    res = merge(claims, now=NOW, places=PLACES)  # raises when the audit finds a problem
    assert {d.merge_id for d in res.dispositions} == set(unique)
    assert check(claims, res) == ()
    if res.cards:
        assert with_first_source_changed(res, claims), "the audit stopped looking"
    shuffled = list(claims)
    rnd.shuffle(shuffled)
    assert merge(shuffled, now=NOW, places=PLACES) == res
