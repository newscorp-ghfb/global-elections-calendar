"""Task 4: matching (spec 10.1-10.4; P67, P68, P70-P75, P78, P80-P82; C7).

Each case names its claims and lists the whole expected matching in the notation of
``shape``; anything not listed is absent.
"""

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from functools import partial
from itertools import combinations
from typing import Any

import pytest

from elections_calendar.merge.identity import MergeError
from elections_calendar.merge.match import Contest, Matching, match
from elections_calendar.model import Claim, RejectedReason
from tests.support.claims import (
    NOW,
    OBS,
    RENEW,
    UMB,
    day,
    days,
    mk,
    month,
    months,
    year,
)
from tests.support.fixture_claims import FIXTURE_NOW, fixture_claim, fixture_claims

WPn = "wikipedia:national-2026@rev1"
WPl = "wikipedia:local-2026@rev2"
EGU = "electionguide:upcoming"
EGP = "electionguide:past"

# The presets (the brief's values, verbatim).
PE = dict(place_id="iso:PE", place_raw="Peru", institution=None, level="subnational",
          span=day(2026, 11, 22))
CH = dict(place_id="iso:CH", place_raw="Switzerland", institution=None, office_class="referendum",
          span=day(2026, 11, 29))
GB = dict(place_id="iso:GB", place_raw="United Kingdom", institution="iso:GB/house-of-commons",
          office_class="lower_house", kind="by_election",
          office_label="House of Commons by-election", span=day(2026, 11, 26))
XS = dict(place_id="x:south-ossetia", place_raw="South Ossetia",
          institution="x:south-ossetia/president", office_class="head_of_state",
          office_label="President")
IP = dict(**RENEW, source_event_id="ipu:SE-LC")
RU = dict(place_id="iso:RU", place_raw="Russia", institution="iso:RU/state-duma",
          office_class="lower_house", office_label="State Duma")
BR = dict(place_id="iso:BR", place_raw="Brazil")
PRES_BR = dict(**BR, institution="iso:BR/president", office_class="head_of_state",
               office_label="President")
LEG = dict(institution=None, office_class="legislature", aggregate=True, office_label="Parliament")
GD = dict(place_id="iso:GD", place_raw="Grenada", span=day(2026, 11, 5))
GD_IPU = dict(**RENEW, institution="iso:GD/house-of-representatives", office_class="lower_house",
              office_label="House of Representatives")
ES = dict(place_id="iso:ES", place_raw="Spain", span=day(2026, 11, 29))
SS = dict(place_id="iso:SS", place_raw="South Sudan", span=day(2026, 12, 22))
SI = dict(place_id="iso:SI", place_raw="Slovenia")
US = dict(place_id="iso:US", place_raw="United States",
          institution="iso:US/house-of-representatives", office_class="lower_house",
          kind="by_election", jurisdiction="Louisiana", jurisdiction_kind="subdivision",
          level="unknown", span=day(2026, 11, 3))
KG = dict(place_id="iso:KG", place_raw="Kyrgyzstan", institution="iso:KG/president",
          office_class="head_of_state", office_label="President")
CI = dict(place_id="iso:CI", place_raw="Côte d'Ivoire", institution="iso:CI/president",
          office_class="head_of_state", span=day(2026, 10, 25))
CO = dict(place_id="iso:CO", place_raw="Colombia")
LOWER = dict(**CO, institution="iso:CO/chamber", office_class="lower_house",
             office_label="Chamber of Representatives")
UPPER = dict(**CO, institution="iso:CO/senate", office_class="upper_house", office_label="Senate")
COUNCIL = dict(institution=None, office_class="local_council", office_label="Municipal councils",
               level="subnational")
GA = dict(place_id="iso:US", place_raw="United States", institution=None, level="subnational",
          jurisdiction="Georgia", jurisdiction_kind="subdivision", span=day(2026, 5, 19))
MB = dict(span=month(2026, 11), date_meaning="unknown", date_text="November 2026")
NOV = dict(span=month(2026, 11), date_meaning="unknown")
BRP = {**PRES_BR, "office_label": "Brazilian Presidency"}
EGE = dict(source_event_id="electionguide:5259")


def cl(unit_id: str, *presets: Mapping[str, Any], n: int = 0, **fields: Any) -> Claim:
    """``mk`` with presets applied left to right, then the fields (later values win)."""
    values: dict[str, Any] = {}
    for preset in presets:
        values.update(preset)
    return mk(unit_id, n, **{**values, **fields})


# ---------------------------------------------------------------- the notation

ORIGIN = {"anchor": "A", "standalone": "C", "aggregate": "G"}
PENDING = {
    ("unresolved_evidence", "no_candidate"): "none",
    ("unresolved_evidence", "several_candidates"): "several",
    ("unresolved_evidence", "conflicting_claims"): "conflicting",
    ("provisional_change", "no_candidate"): "prov none",
    ("provisional_change", "several_candidates"): "prov several",
    ("provisional_change", "provisional_aggregate"): "prov aggregate",
}


def _ordered(items: Sequence[Any], key: Callable[[Any], str], what: str) -> None:
    keys = [key(x) for x in items]
    assert keys == sorted(keys) and len(set(keys)) == len(keys), f"{what} out of order: {keys}"


def shape(m: Matching, names: Mapping[str, str]) -> set[str]:
    """The matching in the test notation; ``names`` maps merge ids to names.

    Also checks every stated order of the result (contests and candidates by child id,
    links and pending items by merge id, a contest's lists in step 0's order).
    """

    def ns(claims: Iterable[Claim]) -> list[str]:
        return sorted(names[c.merge_id] for c in claims)

    def ref(k: Contest) -> str:
        return "{" + " ".join(ns(k.members)) + "}"

    def refs(ks: Iterable[Contest]) -> list[str]:
        return [ref(k) for k in sorted(ks, key=lambda k: ns(k.members))]

    def by_id(k: Contest) -> str:
        return k.child_id

    def by_merge_id(c: Claim) -> str:
        return c.merge_id

    _ordered(m.contests, by_id, "contests")
    _ordered(m.links, lambda link: link.claim.merge_id, "links")
    _ordered(m.undated, lambda u: u.claims[0].merge_id, "undated")
    _ordered(m.pending, lambda p: p.claim.merge_id, "pending")
    out: set[str] = set()
    for k in m.contests:
        for part in (k.members, k.attached, k.provisional):
            _ordered(part, by_merge_id, "contest claims")
        inner = [*ns(k.members), *(f"+{n}" for n in ns(k.attached))]
        inner += [f"⟨{n}⟩" for n in ns(k.provisional)]
        flags = [ORIGIN[k.origin]]
        flags += [f for f, on in (("~", k.ambiguous), ("dc", k.date_conflict)) if on]
        flags += ["sc"] if k.status_conflict else []
        flags += [k.provisional_date] if k.provisional_date else []
        out.add("{" + " ".join(inner) + "} " + " ".join(flags))
        for q in k.possible:
            if k in q.possible:
                out.add(" ↔ ".join(refs([k, q])))
            else:
                out.add(f"{ref(k)} → {ref(q)} (one way)")
    for link in m.links:
        _ordered(link.contests, by_id, "link contests")
        out.add(" ".join([f"{names[link.claim.merge_id]} ⇒", *refs(link.contests)]))
    for p in m.pending:
        _ordered(p.candidates, by_id, "candidates")
        word = PENDING[p.kind, p.reason]
        out.add(" ".join([f"{names[p.claim.merge_id]} → {word}", *refs(p.candidates)]))
    for u in m.undated:
        _ordered(u.claims, by_merge_id, "undated claims")
        _ordered(u.possible, by_id, "undated possible")
        text = "U[" + " ".join(ns(u.claims)) + "]"
        out.add(" ".join([text, "poss", *refs(u.possible)]) if u.possible else text)
    return out


def linked(*names: str) -> set[str]:
    """Every pair of the named one-member contests, linked both ways."""
    return {f"{{{a}}} ↔ {{{b}}}" for a, b in combinations(sorted(names), 2)}


Table = Mapping[str, Claim | Callable[[], Claim]]
Reasons = Mapping[str, RejectedReason | None]
Statuses = Mapping[str, str | tuple[str, bool]]


def case(
    spec: str,
    *expected: str | set[str],
    reasons: Reasons | None = None,
    status: Statuses | None = None,
    id: str | None = None,
) -> Any:
    want: set[str] = set()
    for e in expected:
        want |= {e} if isinstance(e, str) else e
    return pytest.param(
        spec, frozenset(want), dict(reasons or {}), dict(status or {}), id=id or spec.replace(" ", "-")
    )


ROW = ("spec", "expected", "reasons", "status")


def holder(m: Matching, claim: Claim) -> Contest:
    (k,) = [k for k in m.contests if claim in k.direct()]
    return k


def run_case(
    table: Table,
    spec: str,
    expected: frozenset[str],
    reasons: Reasons,
    status: Statuses,
    now: datetime = NOW,
) -> Matching:
    picked = {n: v if isinstance(v, Claim) else v() for n, v in ((n, table[n]) for n in spec.split())}
    claims = list(picked.values())
    names = {c.merge_id: n for n, c in picked.items()}
    m = match(claims, now)
    assert shape(m, names) == set(expected)
    assert shape(match(claims[::-1], now), names) == set(expected), "input order changed the result"
    for n, reason in reasons.items():
        k = holder(m, picked[n])
        assert k.selection is not None
        assert k.selection.reasons[picked[n].merge_id] == reason, n
        if reason is None:
            assert k.selection.claim == picked[n]
    for n, want in status.items():
        k = holder(m, picked[n])
        assert k.status is not None
        word, rescheduled = (want, False) if isinstance(want, str) else want
        assert (k.status.status, k.status.rescheduled) == (word, rescheduled), n
    return m


# ---------------------------------------------------------------- Phase A


PHASE_A: Table = {
    "a": cl(f"{EGP}/r12", RU, span=day(2026, 9, 18)),
    "b": cl("osce:elections/r33", RU, span=day(2026, 9, 19)),
    "c": cl(f"{WPn}/September/li[3]", RU, span=day(2026, 9, 20)),
    "d": cl("ndi:p0/past-c3", RU, span=day(2026, 9, 21)),
    "e": cl("aweb:calendar/r23", RU, span=days(2026, 9, 18, 2026, 9, 21)),
    "b2": cl("osce:elections/r33", RU, span=day(2026, 9, 18)),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("a b c d", "{a} A", "{b} A", "{c} A", "{d} A", linked("a", "b", "c", "d")),
        case(
            "a b c d e",
            "{a} A ~",
            "{b} A ~",
            "{c} A ~",
            "{d} A ~",
            "{e} A ~",
            linked("a", "b", "c", "d", "e"),
        ),
        case("a b2", "{a b2} A"),
    ],
)
def test_phase_a_components(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(PHASE_A, spec, expected, reasons, status)


ROUNDS: Table = {
    "r1": cl(f"{EGP}/r4", PRES_BR, round=1, span=day(2026, 10, 4)),
    "r2": cl(f"{EGU}/r3", PRES_BR, round=2, span=day(2026, 10, 25)),
    "un": cl(f"{WPn}/October/li[2]", PRES_BR, span=day(2026, 10, 4)),
    "m": cl("eisa:y2026/r2", PRES_BR, span=month(2026, 10), date_meaning="unknown"),
    "n": cl("ndi:p0/past-c2", PRES_BR, span=day(2026, 10, 4)),
    "s": cl(f"{EGP}/r5", PRES_BR, round=2, span=day(2026, 10, 4)),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("r1 r2 un", "{r1 un} A", "{r2} A"),
        case("r1 r2 un m", "{r1 un} A", "{r2} A", "m → several {r1 un} {r2}"),
        case("n un", "{n un} A"),
        case("r1 s un", "{r1} A ~", "{s} A ~", "{un} A ~", "{r1} ↔ {un}", "{s} ↔ {un}"),
    ],
)
def test_rounds(spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses) -> None:
    run_case(ROUNDS, spec, expected, reasons, status)


# ---------------------------------------------------------------- Phase B


def r7_nat(claim_id: str, institution: str) -> Claim:
    """Task 2's nationwide claim beside a subdivision claim of the fixture (R7)."""
    c = fixture_claim(claim_id)
    return mk(
        "electionguide:past/r90",
        place_id=c.place_id,
        place_raw=c.place_raw,
        institution=institution,
        office_class=c.office_class,
        office_label="national",
        span=c.span,
    )


R7 = {
    "BA": ("osce:elections/r52#0", "iso:BA/presidency"),
    "PK": ("aweb:calendar/r5#0", "iso:PK/national-assembly"),
    "PH": ("ndi:p0/past-c6#0", "iso:PH/house-of-representatives"),
}

WEAK: Table = {
    "ma": cl(f"{WPl}/November/li[1]/li[1]", PE, jurisdiction="Lima", jurisdiction_kind="named",
             office_class="mayor", office_label="Mayor"),
    "mc": cl(f"{WPl}/November/li[1]/li[2]", PE, jurisdiction="Lima", jurisdiction_kind="named",
             office_class="local_council", office_label="Municipal council"),
    "u": cl("ndi:p0/upcoming-c1", PE, UMB, office_label="2026 Peru Municipal Elections"),
    "x1": cl(f"{WPl}/November/li[2]", PE, jurisdiction_kind="unknown", office_class="mayor",
             office_label="Mayor"),
    "x2": cl("ndi:p0/upcoming-c2", PE, jurisdiction_kind="unknown", office_class="mayor",
             office_label="Mayor"),
    "h": cl(f"{EGU}/r1", GB, jurisdiction="Holborn and St Pancras", jurisdiction_kind="named"),
    "r": cl(f"{EGU}/r2", GB, jurisdiction="Runcorn and Helsby", jurisdiction_kind="named"),
    "w": cl(f"{WPl}/November/li[3]", GB, jurisdiction_kind="unknown"),
    "s1": cl(f"{WPn}/November/li[6]", XS),
    "s2": cl("osce:elections/r4", XS, place_raw="S. Ossetia"),
    "j": cl(f"{EGU}/r40", span=day(2027, 1, 10)),
    "f": cl(f"{EGU}/r41", span=day(2027, 2, 20)),
    "t": cl("ndi:p0/upcoming-c9", span=months(2027, 1, 2027, 2), date_status="tentative",
            date_meaning="unknown"),
    # Added row (the "first member" mutation): a round-2 claim beside a round-1 member.
    "v0": cl(f"{EGU}/r1"),
    "v1": cl(f"{WPn}/November/li[1]", round=1),
    "v2": cl("ndi:p0/upcoming-c1", MB, round=2),
    **{f"c{p}": partial(fixture_claim, cid) for p, (cid, _) in R7.items()},
    **{f"nat{p}": partial(r7_nat, cid, i) for p, (cid, i) in R7.items()},
}


@pytest.mark.parametrize(
    ROW,
    [
        case("ma mc u", "{ma} C", "{mc} C", "u ⇒ {ma} {mc}"),
        case("x1 x2", "{x1} C", "{x2} C"),
        case("h w", "{h +w} A"),
        case("h r w", "{h} A", "{r} A", "w → several {h} {r}"),
        case("s1 s2", "{s1 s2} A"),
        case("f j t", "{f} A", "{j} A", "t → several {f} {j}"),
        case("v0 v1 v2", "{v0 v1} A", "{v2} C"),  # added: every member must fit
        *(case(f"c{p} nat{p}", f"{{c{p}}} C", f"{{nat{p}}} A", id=f"R7-{p}") for p in R7),
    ],
)
def test_weak_claims(spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses) -> None:
    run_case(WEAK, spec, expected, reasons, status)


def obs(**kw: Any) -> Claim:
    return mk("carter:observed/r1", **OBS, **kw)


REFERENDUM: Table = {
    "qa": cl(f"{WPn}/November/li[5]", CH, kind="referendum_question", office_label="Question A"),
    "qb": cl(f"{WPn}/November/li[5]", CH, n=1, kind="referendum_question",
             office_label="Question B"),
    "qa2": cl("osce:elections/r3", CH, kind="referendum_question", office_label="question a"),
    "s": cl(f"{EGU}/r20", CH, kind="referendum_day", office_label="Referendum"),
    "s2": cl(f"{WPn}/November/li[5]", CH, kind="referendum_day", office_label="Referendums"),
    "u": cl("ndi:p0/upcoming-c1", CH, UMB),
}

OBSERVED: Table = {
    "o": obs(span=month(2026, 11)),
    "oNO": obs(span=month(2026, 11), place_id="iso:NO"),
    "oOct": obs(span=month(2026, 10)),
    "oCO": obs(**CO, span=month(2026, 11)),
    "e1": cl(f"{EGU}/r1"),
    "lo": cl(f"{EGU}/r1", LOWER),
    "up": cl(f"{EGU}/r2", UPPER, span=day(2026, 11, 22)),
    "p50": cl(f"{EGP}/r50", span=day(2026, 2, 8)),
    "c51": cl(f"{EGP}/r51", COUNCIL, span=day(2026, 3, 8)),
    "ey": mk("eeas:missions/r1c1", **OBS, span=year(2026), date_text="2026"),
    "eyCO": cl("eeas:missions/r1c1", OBS, CO, span=year(2026), date_text="2026"),
    "lo50": cl(f"{EGP}/r50", LOWER, span=day(2026, 3, 8)),
    "up51": cl(f"{EGP}/r51", UPPER, span=day(2026, 3, 8)),
    "qa": REFERENDUM["qa"],
    "s": REFERENDUM["s"],
    "oCH": obs(place_id="iso:CH", place_raw="Switzerland", span=month(2026, 11)),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("oNO", "oNO → none"),
        case("e1 o", "{e1 +o} A"),
        case("lo oCO up", "{lo} A", "{up} A", "oCO → several {lo} {up}"),
        case("e1 oOct", "{e1} A", "oOct → none"),
        case("c51 ey p50", "{c51} C", "{p50 +ey} A"),
        case("eyCO lo50 up51", "{lo50} A", "{up51} A", "eyCO → several {lo50} {up51}"),
        case("oCH qa s", "{qa +oCH} A", "s ⇒ {qa}"),
    ],
)
def test_observation_with_zero_one_and_several_candidates(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(OBSERVED, spec, expected, reasons, status)


_m = cl("eisa:y2026/r7", PRES_BR, span=month(2026, 10), date_meaning="unknown")
_a = cl(f"{EGU}/r17", PRES_BR)
_i = cl("ipu:elections/r183", RENEW, span=day(2027, 2, 28))
MONTH: Table = {
    "a": _a,
    "b": cl(f"{EGU}/r18", PRES_BR, span=day(2026, 3, 1)),
    "m": _m,
    "mS": replace(_m, institution="iso:BR/senate", office_class="upper_house"),
    "m27": replace(_m, span=month(2027, 10)),
    "mU": replace(_m, jurisdiction_kind="unknown"),
    "g": cl(f"{EGU}/r34", span=day(2027, 1, 16)),
    "i": _i,
    "iM": replace(_i, span=month(2027, 2)),
    "mR": replace(_m, span=month(2026, 12), date_text="December 2026", status_claim="postponed",
                  previous_date_text="15 November 2026"),
    "ac": replace(_a, status_claim="cancelled"),
    "hO": cl("ndi:p0/past-c9", PRES_BR, span=month(2026, 10), date_meaning="unknown",
             status_claim="held", date_text="October 2026"),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("a m", "{a +m} A dc", reasons={"a": None, "m": "not_covering"}),
        case(
            "a mR",
            "{a +mR} A dc",
            reasons={"mR": None, "a": "old_date"},
            status={"mR": ("Upcoming", True)},
        ),
        case(
            "ac hO",
            "{ac +hO} A dc sc",
            reasons={"ac": None, "hO": "not_covering"},
            status={"ac": "Cancelled"},
        ),
        case("a b m", "{a} A", "{b} A", "m → several {a} {b}"),
        case("a mS", "{a} A", "{mS} C"),
        case("a m27", "{a} A", "{m27} C"),
        case("a mU", "{a} A", "{mU} C"),
        case("g i", "{g} A", "{i} C"),
        case("g iM", "{g +iM} A dc"),
    ],
)
def test_month_disagreement(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(MONTH, spec, expected, reasons, status)


def test_month_claim_attaches_with_date_conflict() -> None:
    claims = [c for c in fixture_claims() if c.place_id == "iso:CV"]
    assert len(claims) == 8
    m = match(claims, FIXTURE_NOW)
    names = {c.merge_id: c.claim_id for c in claims}
    assert shape(m, names) == {
        "{electionguide:upcoming/r17#0 ndi:p0/upcoming-c4#0"
        " wikipedia:national-2026@rev1380221397/November/li[4]#0 +eisa:y2026/r7#0} A dc",
        "{eisa:y2026/r6#0 electionguide:past/r36#0"
        " wikipedia:national-2026@rev1380221397/May/li[3]#0} A",
        "{ipu:elections/r47#0} C",
    }
    eg, eisa = fixture_claim("electionguide:upcoming/r17#0"), fixture_claim("eisa:y2026/r7#0")
    assert eisa.date_text == "October 2026"
    k = holder(m, eg)
    assert k.selection is not None
    assert k.selection.claim == eg
    assert k.selection.reasons[eisa.merge_id] == "not_covering"


IPU_CLAIMS: Table = {
    "i1": cl("ipu:elections/r1", IP, span=day(2026, 11, 5)),
    "i2": cl("ipu:elections/r2", IP, span=day(2030, 11, 5)),
    "i3": cl("ipu:elections/r2", IP, span=day(2026, 11, 9)),
    "p": cl("ipu:elections/r1", IP, span=day(2026, 12, 2), provisional=True),
    "i1b": cl("ipu:elections/r1", IP, span=day(2026, 12, 20)),
    "pb": cl("ipu:elections/r1", IP, span=day(2027, 1, 17), provisional=True),
    "e": cl("eisa:y2026/r3", span=day(2026, 11, 26), status_claim="postponed",
            previous_date_text="5 November 2026",
            date_text="Postponed from 5 November 2026 to 26 November 2026"),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("i1 i2", "{i1} C", "{i2} C"),
        case("i1 p", "{i1 ⟨p⟩} C dc moved"),
        case("i1b pb", "{i1b ⟨pb⟩} C dc moved"),
        case("e i1", "{e} A", "{i1} C", "{e} ↔ {i1}", status={"e": ("Upcoming", True)}),
        case("i1 i3", "{i1} C", "{i3} C", "{i1} ↔ {i3}"),
    ],
)
def test_ipu_chamber_id_is_not_an_election_cycle(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(IPU_CLAIMS, spec, expected, reasons, status)


_HOUSE = dict(institution="iso:GD/house-of-representatives", office_class="lower_house",
              office_label="House of Representatives")
GENERIC: Table = {
    "w": cl(f"{WPn}/November/li[2]", GD, LEG),
    "i": cl("ipu:elections/r105", GD, GD_IPU),
    "o": cl("osce:elections/r5", ES, LEG, office_label="Parliamentary Elections"),
    "c": cl(f"{EGU}/r18", ES, institution="iso:ES/congress", office_class="lower_house",
            office_label="Congress"),
    "s": cl(f"{EGU}/r19", ES, institution="iso:ES/senate", office_class="upper_house",
            office_label="Senate"),
    "asm": cl(f"{WPn}/December/li[4]", SS, LEG, n=1, office_label="Assembly"),
    "t": cl(f"{EGU}/r28", SS, institution="iso:SS/tnla", office_class="lower_house",
            office_label="TNLA"),
    "cs": cl(f"{EGU}/r29", SS, institution="iso:SS/council-of-states",
             office_class="upper_house", office_label="Council of States"),
    "wc": cl(f"{WPn}/December/li[4]", SS, n=2, institution="iso:SS/council-of-states",
             office_class="upper_house", office_label="Council of States"),
    "wy": cl("wikipedia:national-2027@rev3/Unknown_date/li[9]", GD, LEG, span=year(2027)),
    # Added row (the "C7 accepts ambiguous contests" mutation): three ambiguous chambers.
    "h0": cl(f"{WPn}/November/li[1]", GD, _HOUSE),
    "h1": cl(f"{EGU}/r50", GD, _HOUSE, round=1),
    "h2": cl(f"{WPn}/November/li[3]", GD, _HOUSE, round=2),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("i w", "{i +w} C", reasons={"w": None, "i": "lower_evidence"}),
        case("c o s", "{c} A", "{s} A", "o ⇒ {c} {s}"),
        case("asm cs t wc", "{cs wc} A", "{t +asm} A"),
        case("i wy", "{i} C", "U[wy]"),
        case(  # added: C7 never names an ambiguous contest
            "h0 h1 h2 w",
            "{h0} A ~",
            "{h1} A ~",
            "{h2} A ~",
            "{h0} ↔ {h1}",
            "{h0} ↔ {h2}",
            "w ⇒ {h0} {h1} {h2}",
        ),
    ],
)
def test_generic_legislature(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(GENERIC, spec, expected, reasons, status)


SAME: Table = {
    "d12": cl(f"{WPl}/November/li[9]/li[1]", US,
              office_label="State House District 12 special election"),
    "d40": cl(f"{WPl}/November/li[9]/li[2]", US,
              office_label="State House District 40 special election"),
    "d12b": cl(f"{WPl}/November/li[9]/li[2]", US,
               office_label="state house district 12 special  election"),
    "n40": cl("ndi:p0/upcoming-c6", US,
              office_label="Louisiana State House District 40 Special Election"),
    "n12": cl("ndi:p0/upcoming-c7", US, office_label="Louisiana House District 12 Special Election"),
    "e12": cl(f"{EGU}/r44", US, office_label="12th State House District"),
    "rn": cl(f"{WPn}/November/li[1]"),
    "rl": cl(f"{WPl}/November/li[1]", office_label="Swedish general election"),
    "c1": cl("ndi:p0/upcoming-c1", CI, office_label="2026 Côte d'Ivoire Presidential Election"),
    "c2": cl("ndi:p0/upcoming-c2", CI, office_label="2026 Ivory Coast Presidential Election"),
    "eg": cl(f"{EGU}/r9", CI, office_label="Ivorian Presidency"),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("d12 d40", "{d12} A", "{d40} A"),
        case("d12 d12b", "{d12 d12b} A"),
        case("d12 n40", "{d12} A", "{n40} A"),
        case("d12 n12", "{d12 n12} A"),
        case("d12 e12", "{d12 e12} A"),
        case("rl rn", "{rl rn} A"),
        case("c1 c2", "{c1} A", "{c2} A"),
        case("c1 c2 eg", "{c1} A ~", "{c2} A ~", "{eg} A ~", "{c1} ↔ {eg}", "{c2} ↔ {eg}"),
    ],
)
def test_same_source_rule(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(SAME, spec, expected, reasons, status)


@pytest.mark.parametrize(
    ROW,
    [
        case("qa qa2 qb s", "{qa qa2} A", "{qb} A", "s ⇒ {qa qa2} {qb}"),
        case("s s2", "{s s2} A"),
        case("s u", "{s} A", "{u} G"),
    ],
)
def test_referendum_questions_and_sessions(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(REFERENDUM, spec, expected, reasons, status)


# ---------------------------------------------------------------- umbrellas

_u = cl("aweb:calendar/r27", BR, UMB, office_label="2026 Brazilian General Elections (2nd round)",
        round=2, span=day(2026, 10, 25))
_n = cl("ndi:p0/upcoming-c1", UMB, level="unknown")
LINKS: Table = {
    "p2": cl(f"{EGU}/r3", BRP, round=2, span=day(2026, 10, 25)),
    "p1": cl(f"{EGP}/r4", BRP, round=1, span=day(2026, 10, 4)),
    "gb": cl(f"{WPl}/October/li[9]/li[1]", BR, institution=None, office_class="governor",
             office_label="Governor", level="subnational", jurisdiction="Bahia",
             jurisdiction_kind="subdivision", round=2, span=day(2026, 10, 25)),
    "rf": cl(f"{WPn}/October/li[6]/li[4]", BR, institution=None, office_class="referendum",
             kind="referendum_day", office_label="Referendum", span=day(2026, 10, 25)),
    "u": _u,
    "uU": replace(_u, level="unknown"),
    "pr": cl(f"{EGU}/r30", SS, institution="iso:SS/president", office_class="head_of_state",
             office_label="Presidency"),
    "tn": cl(f"{EGU}/r28", SS, institution="iso:SS/tnla", office_class="lower_house",
             office_label="TNLA"),
    "e0": cl("eisa:y2026/r19", SS, n=0, institution="iso:SS/president",
             office_class="head_of_state", office_label="Presidential"),
    "e1": cl("eisa:y2026/r19", SS, n=1, institution="iso:SS/tnla", office_class="lower_house",
             office_label="Legislative"),
    "e2": cl("eisa:y2026/r19", SS, n=2, institution=None, office_class="local_council",
             level="subnational", office_label="Local councils"),
    "r": cl(f"{EGU}/r1"),
    "pz": cl(f"{EGU}/r2", institution="iso:SE/president", office_class="head_of_state",
             office_label="President", date_status="confirmed"),
    "ms": cl(f"{WPl}/November/li[1]", institution=None, office_class="mayor", office_label="Mayor",
             level="subnational", jurisdiction="Stockholm", jurisdiction_kind="named"),
    "n": _n,
    "nN": replace(_n, level="national"),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("gb p1 p2 rf u", "{gb} C", "{p1} A", "{p2} A", "{rf} A", "u ⇒ {p2}"),
        case("gb p2 uU", "{gb} C", "{p2} A", "{uU} G"),
        case("e0 e1 e2 pr tn", "{e0 pr} A", "{e1 tn} A", "{e2} C"),
        case("ms n pz r", "{ms} C", "{n} G", "{pz} A", "{r} A"),
        case("ms nN pz r", "{ms} C", "{pz} A", "{r} A", "nN ⇒ {pz} {r}"),
    ],
)
def test_umbrella_links(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(LINKS, spec, expected, reasons, status)


SCOPE: Table = {
    "ma": WEAK["ma"],
    "u": WEAK["u"],
    "cz": cl(f"{WPl}/November/li[1]/li[3]", PE, jurisdiction="Cusco", jurisdiction_kind="named",
             office_class="mayor", office_label="Mayor"),
    "ul": cl("ndi:p0/upcoming-c3", PE, office_class="local_council", aggregate=True,
             kind="aggregate", office_label="Lima municipal elections", jurisdiction="Lima",
             jurisdiction_kind="named"),
    "p2": LINKS["p2"],
    "pl": cl("osce:elections/r9", BR, LEG, span=day(2026, 10, 25)),
    "gv": cl(f"{WPl}/May/li[11]/li[1]", GA, office_class="governor", office_label="Governor"),
    "lg": cl(f"{WPl}/May/li[11]/li[3]", GA, office_class="upper_house",
             office_label="7th Senate district, special election"),
    "sc": cl(f"{WPl}/May/li[11]/li[2]", GA, UMB, level="unknown", office_label="Supreme Court"),
    "gs": cl("ndi:p0/upcoming-c11", GA, UMB, office_label="Georgia state elections"),
    "c40": cl(f"{EGU}/r50", office_class="lower_house", office_label="District 40"),
    "c12": cl(f"{EGU}/r51", office_class="lower_house", office_label="District 12"),
    "lg12": cl("osce:elections/r32", LEG, office_label="District 12 legislature elections"),
    "ug12": cl("ndi:p0/upcoming-c12", UMB, level="national", office_label="District 12 elections"),
    "a0": cl(f"{EGU}/r52"),
    "w40": cl("ndi:p0/upcoming-c4", MB, office_label="District 40"),
    "ph1": cl(f"{EGU}/r53", office_label="Riksdag (1st phase)"),
    "ph2": cl(f"{EGU}/r54", office_label="Riksdag (2nd phase)"),
    "up2": cl("osce:elections/r31", UMB, level="national", office_label="Parliament (2nd phase)"),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("cz ul", "{cz} C", "{ul} G"),
        case("cz ma ul", "{cz} C", "{ma} C", "ul ⇒ {ma}"),
        case("cz ma u", "{cz} C", "{ma} C", "u ⇒ {cz} {ma}"),
        case("p2 pl", "{p2} A", "{pl} G"),
        case("gv lg sc", "{gv} C", "{lg} C", "{sc} G"),
        case("gs gv lg", "{gv} C", "{lg} C", "gs ⇒ {gv} {lg}"),
        case("c40 lg12", "{c40} A", "{lg12} G"),
        case("c12 lg12", "{c12 +lg12} A", reasons={"c12": None, "lg12": "lower_priority"}),
        case("c40 ug12", "{c40} A", "{ug12} G"),
        case("c12 c40 ug12", "{c12} A", "{c40} A", "ug12 ⇒ {c12}"),
        case("a0 w40 ug12", "{a0 +w40} A", "{ug12} G", reasons={"w40": "not_covering"}),
        case("ph1 ph2 up2", "{ph1} A", "{ph2} A", "up2 ⇒ {ph2}"),
        case("ph1 up2", "{ph1} A", "{up2} G"),
    ],
)
def test_umbrella_scope(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(SCOPE, spec, expected, reasons, status)


_w1 = cl("eisa:y2026/r7", PRES_BR, MB, round=1)
ATTACH: Table = {
    "a": cl(f"{EGU}/r17", PRES_BR),
    "w1": _w1,
    "w2": cl("ndi:p0/upcoming-c4", PRES_BR, MB, round=2, date_status="tentative"),
    "w0": cl(f"{WPn}/November/li[4]", PRES_BR, MB),
    "wy": cl("osce:elections/r24", PRES_BR, span=year(2026), date_text="2026", round=2),
    "m10": replace(_w1, span=month(2026, 10), date_text="October 2026"),
    "f1": cl("ndi:p0/upcoming-c4", PRES_BR, MB),
    "f2": cl("ndi:p0/upcoming-c5", PRES_BR, MB, office_label="Vice President"),
    "ua": cl(f"{EGU}/r44", US, office_label="Louisiana House special election"),
    "l1": cl("ndi:p0/upcoming-c6", US, NOV, level="national"),
    "l2": cl("eisa:y2026/r8", US, NOV, level="subnational"),
    "d1": cl("ndi:p0/upcoming-c6", US, NOV, office_label="House District 12 Special Election"),
    "d2": cl("eisa:y2026/r8", US, NOV, office_label="House District 40"),
    "d3": cl("eisa:y2026/r8", US, NOV, office_label="12th House District"),
    "i": GENERIC["i"],
    "w": GENERIC["w"],
    "g1": cl("osce:elections/r30", GD, LEG, round=1),
    "g2": cl(f"{WPn}/November/li[2]", GD, LEG, n=1, round=2),
    "h": cl(f"{EGU}/r50", GD, _HOUSE),
    "r2": cl("ndi:p0/upcoming-c4", GD, _HOUSE, span=month(2026, 11), date_meaning="unknown",
             date_status="tentative", round=2),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("a w1", "{a +w1} A"),
        case("a w0 w1", "{a +w0 +w1} A"),
        case("a w1 w2", "{a} A", "w1 → conflicting {a}", "w2 → conflicting {a}"),
        case("a w0 w1 w2", "{a +w0} A", "w1 → conflicting {a}", "w2 → conflicting {a}"),
        case("a w1 wy", "{a} A", "w1 → conflicting {a}", "U[wy] poss {a}"),
        case("a m10 w2", "{a} A", "m10 → conflicting {a}", "w2 → conflicting {a}"),
        case("a f1 f2", "{a} A", "f1 → conflicting {a}", "f2 → conflicting {a}"),
        case("ua l1 l2", "{ua} A", "l1 → conflicting {ua}", "l2 → conflicting {ua}"),
        case("ua d1 d2", "{ua} A", "d1 → conflicting {ua}", "d2 → conflicting {ua}"),
        case("ua d1 d3", "{ua +d1 +d3} A"),
        case("i w", "{i +w} C"),
        case("i g1 g2", "{i} C", "g1 ⇒ {i}", "g2 ⇒ {i}"),
        case("g1 h", "{h +g1} A"),
        case("g1 h r2", "{h +r2} A", "{g1} G"),
    ],
)
def test_attachments_are_checked_together(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(ATTACH, spec, expected, reasons, status)


_ln = cl("ndi:p0/upcoming-c8", SI, UMB, office_label="2026 Slovenia Local Elections",
         level="subnational", span=month(2026, 11), date_meaning="unknown",
         date_status="tentative")
UNMATCHED: Table = {
    "lo": cl("osce:elections/r4", SI, UMB, office_label="Local Elections", level="subnational"),
    "ll": cl(f"{WPl}/November/li[4]", SI, UMB, office_label="local elections", level="subnational"),
    "ln": _ln,
    "lnU": replace(_ln, level="unknown"),
    "pl": cl(f"{WPl}/November/li[5]", SI, LEG),
    "rg": cl(f"{WPl}/November/li[6]", SI, UMB, office_label="regional elections",
             level="subnational"),
    "sc": SCOPE["sc"],
    "ca": cl("ndi:p0/upcoming-c13", GA, UMB, level="unknown", office_label="Court of Appeals"),
    "sc2": cl("ndi:p0/upcoming-c14", GA, UMB, level="unknown", office_label="supreme  court"),
}


@pytest.mark.parametrize(
    ROW,
    [
        case(
            "ll ln lo",
            "{ll ln lo} G",
            reasons={"lo": None, "ll": "lower_priority", "ln": "not_covering"},
        ),
        case("ll lnU lo", "{ll lo} G", "{lnU} G"),
        case("ca sc", "{ca} G", "{sc} G"),
        case("sc sc2", "{sc sc2} G", reasons={"sc": None, "sc2": "lower_priority"}),
        case("lo pl", "{lo} G", "{pl} G"),
        case("ll rg", "{ll} G", "{rg} G"),
    ],
)
def test_unmatched_umbrellas_cluster(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(UNMATCHED, spec, expected, reasons, status)


# ---------------------------------------------------------------- Phase D

_pe = cl(f"{EGU}/r1", provisional=True)
_nmo = cl("ndi:p0/upcoming-c4", span=month(2026, 11), date_status="tentative",
          date_meaning="unknown")
_res = cl("eisa:y2026/r3", status_claim="postponed", previous_date_text="1 November 2026")
_ag = cl("ndi:p0/upcoming-c1", UMB, provisional=True)
_ps = cl("osce:elections/r1", provisional=True, span=day(2026, 12, 6))
PROVISIONAL: Table = {
    "e": cl(f"{EGU}/r1"),
    "e2": cl(f"{EGU}/r2", span=day(2026, 3, 1)),
    "ec": cl(f"{EGU}/r1", status_claim="cancelled"),
    "pe": _pe,
    "pe22": replace(_pe, span=day(2026, 11, 22)),
    "pe27": replace(_pe, span=year(2027), date_text="2027"),
    "pey": replace(_pe, span=year(2026), date_text="2026"),
    "pem": replace(_pe, span=month(2026, 11), date_text="November 2026"),
    "per": replace(_pe, span=days(2026, 11, 14, 2026, 11, 15)),
    "pes": replace(_pe, span=day(2026, 11, 15)),
    "pet": replace(_pe, date_text="Sunday 15 November 2026"),
    "pep": replace(_pe, status_claim="postponed"),
    "peh": replace(_pe, status_claim="held"),
    "er": cl(f"{EGU}/r1", span=days(2026, 11, 14, 2026, 11, 15)),
    "nmo": _nmo,
    "pnm": replace(_nmo, provisional=True, span=day(2026, 11, 22)),
    "res": _res,
    "presch": replace(_res, provisional=True),
    "ag": _ag,
    "agNO": replace(_ag, place_id="iso:NO"),
    "un": cl("ndi:p0/upcoming-c1", UMB),
    "po": cl("osce:elections/r1", provisional=True, institution="iso:SE/x",
             office_class="head_of_state", office_label="President"),
    "ps": _ps,
    "pn": replace(_ps, span=day(2027, 1, 10)),
    "psm": replace(_ps, span=month(2026, 11)),
    "psy": replace(_ps, span=year(2026)),
    "o": cl("osce:elections/r1"),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("e pe22", "{e ⟨pe22⟩} A dc moved"),
        case("e pe", "{e ⟨pe⟩} A"),
        case("e pet", "{e ⟨pet⟩} A"),
        case("e pey", "{e ⟨pey⟩} A less_precise"),
        case("e pem", "{e ⟨pem⟩} A less_precise"),
        case("er pem", "{er ⟨pem⟩} A less_precise"),
        case("e per", "{e ⟨per⟩} A dc moved"),
        case("er pes", "{er ⟨pes⟩} A dc moved"),
        case("e pe27", "{e ⟨pe27⟩} A dc moved"),
        case("e nmo pnm", "{e +nmo ⟨pnm⟩} A"),
        case("e pep", "{e ⟨pep⟩} A sc"),
        case("e peh", "{e ⟨peh⟩} A"),
        case("agNO", "agNO → prov aggregate"),
        case("ag e", "{e} A", "ag → prov aggregate {e}"),
        case("e un", "{e} A", "un ⇒ {e}"),
        case("e po", "{e} A", "po → prov none"),
        case("e ps", "{e ⟨ps⟩} A dc moved"),
        case("e psm", "{e ⟨psm⟩} A"),
        case("e psy", "{e ⟨psy⟩} A"),
        case("e o psy", "{e o ⟨psy⟩} A less_precise"),
        case("e o pe22 psy", "{e o ⟨pe22⟩ ⟨psy⟩} A dc moved"),
        case("e pn", "{e} A", "pn → prov none"),
        case("e e2 ps", "{e} A", "{e2} A", "ps → prov several {e} {e2}"),
        case("ec pe", "{ec ⟨pe⟩} A sc", status={"ec": "Cancelled"}),
        case("ec peh", "{ec ⟨peh⟩} A sc", status={"ec": "Cancelled"}),
        case("res", "{res} A", status={"res": ("Upcoming", True)}),
        case("res presch", "{res ⟨presch⟩} A"),
    ],
)
def test_provisional_claims(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(PROVISIONAL, spec, expected, reasons, status)


# ---------------------------------------------------------------- possible matches, undated

_k24 = cl("ndi:p0/upcoming-c5", KG, span=day(2027, 1, 24))
POSSIBLE: Table = {
    "k1": cl(f"{EGU}/r40", KG, span=day(2027, 1, 27)),
    "k24": _k24,
    "k19": cl("ndi:p0/upcoming-c5", KG, span=day(2027, 1, 19)),
    "k20": cl("ndi:p0/upcoming-c5", KG, span=day(2027, 1, 20)),
    "kx": replace(_k24, institution="iso:KG/other"),
    "c1": cl(f"{EGU}/r1", EGE),
    "c1r": cl(f"{EGU}/r1", EGE, span=days(2026, 11, 14, 2026, 11, 15)),
    "c2": cl(f"{EGP}/r1", EGE),
    "c2d": cl(f"{EGP}/r1", EGE, span=day(2026, 12, 20)),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("k1 k24", "{k1} A", "{k24} A", "{k1} ↔ {k24}"),
        case("k1 k19", "{k1} A", "{k19} A"),
        case("k1 k20", "{k1} A", "{k20} A", "{k1} ↔ {k20}"),
        case("k1 kx", "{k1} A", "{kx} A"),
        case("c1 c2d", "{c1} A", "{c2d} A", "{c1} ↔ {c2d}"),
        case("c1r c2", "{c1r c2} A dc", reasons={"c2": "not_covering"}),
        case("c1 c2", "{c1 c2} A"),
    ],
)
def test_possible_matches(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(POSSIBLE, spec, expected, reasons, status)


YEAR_ONLY: Table = {
    "y": cl("osce:elections/r24", span=year(2027), office_label="Parliamentary Elections"),
    "a": cl(f"{EGU}/r60", span=day(2027, 9, 12)),
    "b": cl(f"{EGU}/r61", span=day(2027, 3, 14)),
    "e": cl(f"{EGU}/r1"),
    "y1": cl("osce:elections/r26", institution=None, office_class="head_of_state",
             span=year(2027), office_label="Presidential Election"),
    "y2": cl("wikipedia:national-2027@rev3/Unknown_date/li[1]", institution=None,
             office_class="head_of_state", span=year(2027), office_label="President"),
    "g": cl("ndi:p0/upcoming-c7", UMB, span=year(2026)),
    "ya": cl("osce:elections/r24", span=year(2027), round=1),
    "yb": cl("wikipedia:national-2027@rev3/Unknown_date/li[1]", span=year(2027)),
    "yc": cl("ndi:p0/upcoming-c3", span=year(2027), round=2),
}


@pytest.mark.parametrize(
    ROW,
    [
        case("y", "U[y]"),
        case("a y", "{a +y} A"),
        case("a b y", "{a} A", "{b} A", "U[y] poss {a} {b}"),
        case("y1 y2", "U[y1 y2]"),
        case("g", "U[g]"),
        case("e g", "{e} A", "U[g]"),
        case("ya yb yc", "U[ya]", "U[yb]", "U[yc]"),
    ],
)
def test_year_only_claims(
    spec: str, expected: frozenset[str], reasons: Reasons, status: Statuses
) -> None:
    run_case(YEAR_ONLY, spec, expected, reasons, status)


def test_match_fails_closed() -> None:
    with pytest.raises(MergeError) as dup:
        match([mk("osce:elections/r1"), mk("osce:elections/r1")], NOW)
    assert str(dup.value) == "duplicate merge_id: served/osce:elections/r1#0"
    with pytest.raises(MergeError) as unknown:
        match([mk("xyz:p/r1")], NOW)
    assert str(unknown.value) == "unknown source: xyz"
    with pytest.raises(ValueError) as naive:
        match([mk("osce:elections/r1")], datetime(2026, 10, 19))
    assert str(naive.value) == "now must be timezone-aware"
