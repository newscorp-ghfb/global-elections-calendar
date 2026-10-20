"""Task 6: the conservation audit (spec 10.8, 10.9; P79, R2-04, R2-05; G08).

Each named claim is rebuilt here from its Task 4 definition (the tables below are copies).
"""

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import pytest

from elections_calendar.merge.conservation import check
from elections_calendar.model import Child, ChildSource, Claim, Disposition, MergeResult
from tests.support.claims import (
    BR,
    BRP,
    CH,
    CO,
    COUNCIL,
    EGP,
    EGU,
    GA,
    GB,
    GD,
    GD_IPU,
    LEG,
    LOWER,
    MB,
    NOV,
    OBS,
    PE,
    PRES_BR,
    RENEW,
    RU,
    SI,
    SS,
    UMB,
    UPPER,
    US,
    WPl,
    WPn,
    cl,
    day,
    days,
    mk,
    month,
    result,
    year,
)

LEG_FIELDS: dict[str, Any] = LEG

# ---------------------------------------------------------------- the helpers


def with_claim(res: MergeResult, merge_id: str, claim: Claim) -> MergeResult:
    """``res`` with the child source of that merge id holding ``claim`` instead."""

    def source(s: ChildSource) -> ChildSource:
        return replace(s, claim=claim) if s.claim.merge_id == merge_id else s

    cards = tuple(
        replace(
            card,
            children=tuple(
                replace(k, sources=tuple(source(s) for s in k.sources)) for k in card.children
            ),
        )
        for card in res.cards
    )
    return replace(res, cards=cards)


def with_child(res: MergeResult, child_id: str, **fields: Any) -> MergeResult:
    """``res`` with the fields of one child replaced."""
    cards = tuple(
        replace(
            card,
            children=tuple(
                replace(k, **fields) if k.child_id == child_id else k for k in card.children
            ),
        )
        for card in res.cards
    )
    return replace(res, cards=cards)


def children(res: MergeResult) -> list[Child]:
    return [k for card in res.cards for k in card.children]


def child_of(res: MergeResult, claim: Claim) -> str:
    (k,) = [k for k in children(res) if any(s.claim.merge_id == claim.merge_id for s in k.sources)]
    return k.child_id


def disposition(res: MergeResult, claim: Claim) -> Disposition:
    (d,) = [d for d in res.dispositions if d.merge_id == claim.merge_id]
    return d


def with_dispositions(
    res: MergeResult, old: Disposition, *new: Disposition
) -> MergeResult:
    kept = tuple(d for d in res.dispositions if d != old)
    return replace(res, dispositions=(*kept, *new))


# ---------------------------------------------------------------- Task 4's tables (copies)

WEAK = {
    "ma": cl(f"{WPl}/November/li[1]/li[1]", PE, jurisdiction="Lima", jurisdiction_kind="named",
             office_class="mayor", office_label="Mayor"),
    "mc": cl(f"{WPl}/November/li[1]/li[2]", PE, jurisdiction="Lima", jurisdiction_kind="named",
             office_class="local_council", office_label="Municipal council"),
    "u": cl("ndi:p0/upcoming-c1", PE, UMB, office_label="2026 Peru Municipal Elections"),
}
GENERIC = {
    "w": cl(f"{WPn}/November/li[2]", GD, LEG),
    "i": cl("ipu:elections/r105", GD, GD_IPU),
}
_HOUSE = dict(institution="iso:GD/house-of-representatives", office_class="lower_house",
              office_label="House of Representatives")


PHASE_A = {
    "a": cl(f"{EGP}/r12", RU, span=day(2026, 9, 18)),
    "b": cl("osce:elections/r33", RU, span=day(2026, 9, 19)),
    "c": cl(f"{WPn}/September/li[3]", RU, span=day(2026, 9, 20)),
    "d": cl("ndi:p0/past-c3", RU, span=day(2026, 9, 21)),
    "e": cl("aweb:calendar/r23", RU, span=days(2026, 9, 18, 2026, 9, 21)),
    "b2": cl("osce:elections/r33", RU, span=day(2026, 9, 18)),
}

ROUNDS = {
    "r1": cl(f"{EGP}/r4", PRES_BR, round=1, span=day(2026, 10, 4)),
    "r2": cl(f"{EGU}/r3", PRES_BR, round=2, span=day(2026, 10, 25)),
    "un": cl(f"{WPn}/October/li[2]", PRES_BR, span=day(2026, 10, 4)),
    "m": cl("eisa:y2026/r2", PRES_BR, span=month(2026, 10), date_meaning="unknown"),
    "n": cl("ndi:p0/past-c2", PRES_BR, span=day(2026, 10, 4)),
    "s": cl(f"{EGP}/r5", PRES_BR, round=2, span=day(2026, 10, 4)),
}

REFERENDUM = {
    "qa": cl(f"{WPn}/November/li[5]", CH, kind="referendum_question", office_label="Question A"),
    "qb": cl(f"{WPn}/November/li[5]", CH, n=1, kind="referendum_question",
             office_label="Question B"),
    "qa2": cl("osce:elections/r3", CH, kind="referendum_question", office_label="question a"),
    "s": cl(f"{EGU}/r20", CH, kind="referendum_day", office_label="Referendum"),
    "s2": cl(f"{WPn}/November/li[5]", CH, kind="referendum_day", office_label="Referendums"),
    "u": cl("ndi:p0/upcoming-c1", CH, UMB),
}

def obs(**kw: Any) -> Claim:
    return mk("carter:observed/r1", **OBS, **kw)

OBSERVED = {
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

_m = cl("eisa:y2026/r7", PRES_BR, span=month(2026, 10), date_meaning="unknown")

_a = cl(f"{EGU}/r17", PRES_BR)

_i = cl("ipu:elections/r183", RENEW, span=day(2027, 2, 28))

MONTH = {
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

_pe = cl(f"{EGU}/r1", provisional=True)

_nmo = cl("ndi:p0/upcoming-c4", span=month(2026, 11), date_status="tentative",
          date_meaning="unknown")

_res = cl("eisa:y2026/r3", status_claim="postponed", previous_date_text="1 November 2026")

_ag = cl("ndi:p0/upcoming-c1", UMB, provisional=True)

_ps = cl("osce:elections/r1", provisional=True, span=day(2026, 12, 6))

PROVISIONAL = {
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

YEAR_ONLY = {
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

_u = cl("aweb:calendar/r27", BR, UMB, office_label="2026 Brazilian General Elections (2nd round)",
        round=2, span=day(2026, 10, 25))

_n = cl("ndi:p0/upcoming-c1", UMB, level="unknown")

LINKS = {
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

SCOPE = {
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

_w1 = cl("eisa:y2026/r7", PRES_BR, MB, round=1)

_HOUSE = dict(institution="iso:GD/house-of-representatives", office_class="lower_house",
              office_label="House of Representatives")

ATTACH = {
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

_ln = cl("ndi:p0/upcoming-c8", SI, UMB, office_label="2026 Slovenia Local Elections",
         level="subnational", span=month(2026, 11), date_meaning="unknown",
         date_status="tentative")

UNMATCHED = {
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


# ---------------------------------------------------------------- the clean results

CLEAN = [
    (PHASE_A, "a b c d e"),
    (ROUNDS, "r1 r2 un m"),
    (LINKS, "gb p1 p2 rf u"),
    (LINKS, "gb p2 uU"),
    (LINKS, "ms nN pz r"),
    (SCOPE, "cz ma u"),
    (ATTACH, "a w1 w2"),
    (ATTACH, "i w"),
    (ATTACH, "i g1 g2"),
    (ATTACH, "g1 h r2"),
    (PROVISIONAL, "e pe22"),
    (PROVISIONAL, "e o pe22 psy"),
    (PROVISIONAL, "res"),
    (YEAR_ONLY, "a b y"),
    (UNMATCHED, "ll ln lo"),
    (REFERENDUM, "qa qa2 qb s"),
    (OBSERVED, "oCH qa s"),
    (OBSERVED, "oNO"),
    # revision 3: the new checks accept every correct result
    (MONTH, "a mR"),
    (MONTH, "ac hO"),
    (PROVISIONAL, "e per"),
    (PROVISIONAL, "er pes"),
    (SCOPE, "c12 c40 ug12"),
    (SCOPE, "a0 w40 ug12"),
    (SCOPE, "ph1 ph2 up2"),
    (UNMATCHED, "ll lnU lo"),
    (UNMATCHED, "ca sc"),
]


def built(table: Mapping[str, Claim], spec: str) -> tuple[list[Claim], MergeResult]:
    claims = [table[n] for n in spec.split()]
    return claims, result(*claims)


@pytest.mark.parametrize(
    ("table", "spec"), CLEAN, ids=[f"{spec.replace(' ', '-')}" for _, spec in CLEAN]
)
def test_clean_results_pass_the_audit(table: Mapping[str, Claim], spec: str) -> None:
    claims, res = built(table, spec)
    assert check(claims, res) == ()


# ---------------------------------------------------------------- dispositions


def test_lost_and_duplicated_inputs_are_caught() -> None:
    claims, res = built(ROUNDS, "r1 r2 un")
    r1, r2, un = claims
    un_disp = disposition(res, un)
    moved = replace(un_disp, merge_id=r1.merge_id)
    assert check(claims, with_dispositions(res, un_disp, moved)) == (
        "duplicate disposition: served/electionguide:past/r4#0",
        "no disposition: served/wikipedia:national-2026@rev1/October/li[2]#0",
    )
    extra = Disposition("served/osce:elections/r99#0", "standalone", (child_of(res, r2),))
    assert check(claims, replace(res, dispositions=(*res.dispositions, extra))) == (
        "unknown input: served/osce:elections/r99#0",
    )


def test_targets_and_placement() -> None:
    e1 = cl(f"{EGU}/r1")
    o = OBSERVED["o"]
    res = result(e1, o)
    od = disposition(res, o)
    assert check([e1, o], res) == ()
    dangling = replace(od, targets=("000000000000",))
    assert check([e1, o], with_dispositions(res, od, dangling)) == (
        "dangling target: served/carter:observed/r1#0 -> 000000000000",
        "misplaced: served/carter:observed/r1#0",
    )

    b = cl(f"{EGU}/r2", institution="iso:SE/president", office_class="head_of_state",
           office_label="President")
    w = mk("ndi:p0/upcoming-c1", span=month(2026, 11), date_status="tentative",
           date_meaning="unknown")
    res = result(e1, b, w)
    assert check([e1, b, w], res) == ()
    assert disposition(res, w).targets == (child_of(res, e1),)
    wd = disposition(res, w)
    elsewhere = replace(wd, targets=(child_of(res, b),))
    assert check([e1, b, w], with_dispositions(res, wd, elsewhere)) == (
        "misplaced: served/ndi:p0/upcoming-c1#0",
    )

    e, pe = PROVISIONAL["e"], PROVISIONAL["pe"]
    res = result(e, pe)
    pd = disposition(res, pe)
    assert pd.kind == "provisional"
    assert check([e, pe], with_dispositions(res, pd, replace(pd, kind="attached"))) == (
        "misplaced: provisional/electionguide:upcoming/r1#0",
    )


# ---------------------------------------------------------------- wrong merge

A1 = mk("electionguide:upcoming/r1", round=1)
X = mk("osce:elections/r1")
PAIR = (
    "wrong merge: 8c6da6604ce3: served/electionguide:upcoming/r1#0"
    " and served/osce:elections/r1#0",
)
WRONG_ROWS: list[Any] = [
    pytest.param(replace(X, office_class="head_of_state", institution=None), PAIR, id="class"),
    pytest.param(replace(X, round=2), PAIR, id="round"),
    pytest.param(replace(X, level="subnational"), PAIR, id="level"),
    pytest.param(replace(X, place_id="iso:NO", place_raw="Norway"), PAIR, id="place"),
    pytest.param(replace(X, institution="iso:SE/other"), PAIR, id="institution"),
    pytest.param(
        replace(X, jurisdiction="Lima", jurisdiction_kind="named"), PAIR, id="jurisdiction"
    ),
    pytest.param(replace(X, kind="by_election"), PAIR, id="kind"),
    pytest.param(
        replace(X, span=day(2026, 11, 16), date_text="16 November 2026"),
        (
            "wrong merge: 8c6da6604ce3: served/electionguide:upcoming/r1#0"
            " and served/osce:elections/r1#0 have other dates",
        ),
        id="joined-dates",
    ),
    pytest.param(replace(X, office_label="District 12"), (), id="one-side-no-district"),
    pytest.param(replace(X, **OBS), (), id="observation"),
    pytest.param(
        replace(X, **OBS, place_id="iso:NO"),
        ("wrong merge: 8c6da6604ce3 holds served/osce:elections/r1#0 from another place",),
        id="observation-other-place",
    ),
]


@pytest.mark.parametrize(("nx", "expected"), WRONG_ROWS)
def test_wrong_merge_is_caught(nx: Claim, expected: tuple[str, ...]) -> None:
    res = result(A1, X)
    (kid,) = [k.child_id for k in children(res)]
    assert kid == "8c6da6604ce3"
    assert check([A1, X], res) == ()
    assert check([A1, nx], with_claim(res, X.merge_id, nx)) == expected


def test_wrong_merge_rule_f() -> None:
    xe = cl(f"{EGU}/r2", round=1)
    res = result(A1, xe)
    (kid,) = [k.child_id for k in children(res)]
    assert kid == "382710a03c5b"
    nx = replace(xe, office_label="Other")
    assert check([A1, nx], with_claim(res, xe.merge_id, nx)) == (
        "wrong merge: 382710a03c5b: served/electionguide:upcoming/r1#0"
        " and served/electionguide:upcoming/r2#0",
    )


def test_wrong_merge_legislature_umbrella_outside_a_chamber() -> None:
    pres = dict(institution="iso:SE/president", office_class="head_of_state",
                office_label="President")
    h1 = cl("electionguide:upcoming/r1", pres)
    hx = cl("osce:elections/r1", pres)
    res = result(h1, hx)
    (kid,) = [k.child_id for k in children(res)]
    assert kid == "8c6da6604ce3"
    nx = replace(hx, **LEG_FIELDS)
    assert check([h1, nx], with_claim(res, hx.merge_id, nx)) == (
        "wrong merge: 8c6da6604ce3 has a legislature umbrella outside a chamber",
    )


def test_wrong_merge_aggregate_with_two_office_classes() -> None:
    ll, ln, lo = UNMATCHED["ll"], UNMATCHED["ln"], UNMATCHED["lo"]
    res = result(ll, ln, lo)
    nx = replace(ln, **LEG_FIELDS)
    assert check([ll, nx, lo], with_claim(res, ln.merge_id, nx)) == (
        "wrong merge: fd8b5b88f149 has two office classes",
    )


def test_wrong_merge_attached_date() -> None:
    e1 = cl(f"{EGU}/r1")
    w = mk("ndi:p0/upcoming-c1", span=month(2026, 11), date_status="tentative",
           date_meaning="unknown")
    res = result(e1, w)
    (kid,) = [k.child_id for k in children(res)]
    assert kid == "605682096ffe"
    assert disposition(res, w).kind == "attached"
    nw = replace(w, span=month(2026, 12))
    moved = with_claim(res, w.merge_id, nw)
    assert check([e1, nw], moved) == (
        "wrong merge: 605682096ffe: served/ndi:p0/upcoming-c1#0 has another date"
        " and no date_conflict",
    )
    assert check([e1, nw], with_child(moved, kid, date_conflict=True)) == ()


# ---------------------------------------------------------------- holders


def test_changed_and_unknown_holders_are_caught() -> None:
    res = result(A1, X)
    changed = "changed claim: served/osce:elections/r1#0"
    nx = replace(X, place_raw="Sverige")
    assert check([A1, X], with_claim(res, X.merge_id, nx)) == (changed,)
    nx = replace(X, span=day(2026, 11, 16))
    assert check([A1, X], with_claim(res, X.merge_id, nx)) == (
        changed,
        "wrong merge: 8c6da6604ce3: served/electionguide:upcoming/r1#0"
        " and served/osce:elections/r1#0 have other dates",
    )

    (kid,) = [k.child_id for k in children(res)]
    (k,) = children(res)
    ghost = ChildSource(mk("osce:elections/r99"), False, "lower_priority")
    grown = with_child(res, kid, sources=(*k.sources, ghost))
    assert check([A1, X], grown) == ("unknown holder: served/osce:elections/r99#0",)

    o = OBSERVED["oNO"]
    res = result(o)
    (item,) = res.attention
    item = replace(item, merge_ids=(*item.merge_ids, "served/osce:elections/r99#0"))
    assert check([o], replace(res, attention=(item,))) == (
        "unknown holder: served/osce:elections/r99#0",
    )


# ---------------------------------------------------------------- coverage


def test_umbrella_coverage_is_checked() -> None:
    brazil = "served/aweb:calendar/r27#0"
    claims, res = built(LINKS, "gb p1 p2 rf u")
    u = LINKS["u"]
    ud = disposition(res, u)
    assert ud.targets == ("84c968bd489c",)
    (card,) = [c for c in res.cards if any(k.child_id == "84c968bd489c" for k in c.children)]
    assert card.group_id == "862446e7b7ab"
    assert {k.child_id for k in card.children} >= {"84c968bd489c", "88e61e82732a"}
    for targets in (("88e61e82732a",), ("84c968bd489c", "88e61e82732a")):
        redirected = with_dispositions(res, ud, replace(ud, targets=targets))
        assert check(claims, redirected) == (f"wrong coverage: {brazil}",)

    claims, res = built({**WEAK}, "ma mc u")
    u = WEAK["u"]
    ud = disposition(res, u)
    assert ud.targets == ("35bd1312dc95", "e8c2e0c4e454")
    dropped = replace(ud, targets=("35bd1312dc95",))
    assert check(claims, with_dispositions(res, ud, dropped)) == (
        "wrong coverage: served/ndi:p0/upcoming-c1#0",
    )

    claims, res = built(SCOPE, "c12 c40 ug12")
    ug = SCOPE["ug12"]
    ud = disposition(res, ug)
    assert ud.targets == ("c908a5427792",)
    (card,) = res.cards
    assert card.group_id == "5a94ef2ae3fe"
    swapped = replace(ud, targets=("ed407c6c0cee",))
    assert check(claims, with_dispositions(res, ud, swapped)) == (
        "wrong coverage: served/ndi:p0/upcoming-c12#0",
    )

    cz, ul = SCOPE["cz"], SCOPE["ul"]
    res = result(cz, ul)
    nul = replace(ul, jurisdiction="Cusco")
    assert check([cz, nul], with_claim(res, ul.merge_id, nul)) == (
        "wrong coverage: served/ndi:p0/upcoming-c3#0",
    )


# ---------------------------------------------------------------- missed merge, ids


def test_missed_merge_is_caught() -> None:
    e1 = cl(f"{EGU}/r1")
    x16 = mk("osce:elections/r1", span=day(2026, 11, 16))
    res = result(e1, x16)
    assert check([e1, x16], res) == ()
    ids = sorted(k.child_id for k in children(res))
    assert len(ids) == 2
    nx = replace(x16, span=day(2026, 11, 15))
    assert check([e1, nx], with_claim(res, x16.merge_id, nx)) == (
        f"missed merge: {ids[0]} and {ids[1]}",
    )


def test_ids_and_possible_matches() -> None:
    o = OBSERVED["oNO"]
    res = result(o)
    (item,) = res.attention
    doubled = replace(res, attention=(item, item))
    assert check([o], doubled) == (
        f"duplicate id: {item.item_id}",
        "misplaced: served/carter:observed/r1#0",
    )

    e1 = cl(f"{EGU}/r1")
    res = result(e1)
    (kid,) = [k.child_id for k in children(res)]
    bad = with_child(res, kid, possible_matches=("ffffffffffff",))
    assert check([e1], bad) == (f"dangling possible match: {kid} -> ffffffffffff",)


# ---------------------------------------------------------------- the joining rules (final fix F2)


def fold(res: MergeResult, keep: Claim, other: Claim) -> tuple[MergeResult, str]:
    """``res`` with ``other``'s child folded into ``keep``'s: both joined there (damaged).

    Returns the damaged result and the surviving child id. The other child, and its card
    when it holds no other child, are removed, so the merge is the only problem.
    """
    kid, gone = child_of(res, keep), child_of(res, other)
    assert kid != gone
    moved = ChildSource(other, False, "lower_priority")
    cards = []
    for card in res.cards:
        kids = []
        for k in card.children:
            if k.child_id == kid:
                k = replace(k, sources=(*k.sources, moved))
            if k.child_id != gone:
                kids.append(k)
        if kids:
            cards.append(replace(card, children=tuple(kids)))
    old = disposition(res, other)
    dispositions = tuple(d for d in res.dispositions if d != old)
    dispositions += (replace(old, kind="anchor_member", targets=(kid,)),)
    return replace(res, cards=tuple(cards), dispositions=dispositions), kid


def test_wrong_merge_two_unknown_jurisdictions() -> None:
    mayor = dict(office_class="mayor", office_label="Mayor", aggregate=False,
                 kind="candidate_election", jurisdiction_kind="unknown", jurisdiction=None,
                 institution=None, level="subnational")
    a = cl(f"{WPl}/November/li[1]/li[1]", PE, mayor)
    b = cl("ndi:p0/upcoming-c1", PE, mayor)
    res = result(a, b)
    assert len(children(res)) == 2  # an unknown jurisdiction never agrees with another
    assert check([a, b], res) == ()
    folded, kid = fold(res, a, b)
    assert kid == "e8c2e0c4e454"
    assert check([a, b], folded) == (
        f"wrong merge: {kid}: {b.merge_id} and {a.merge_id}",
    )
    # clean: an attached unknown-jurisdiction claim beside a named joined one keeps the relaxation
    h = cl(f"{EGU}/r1", GB, jurisdiction="Holborn and St Pancras", jurisdiction_kind="named")
    w = cl(f"{WPl}/November/li[3]", GB, jurisdiction_kind="unknown")
    res = result(h, w)
    assert disposition(res, w).kind == "attached"
    assert check([h, w], res) == ()


def test_wrong_merge_aggregate_labels() -> None:
    court = dict(office_class="general", level="unknown", aggregate=True, kind="aggregate",
                 institution=None)
    sc = cl(f"{WPl}/May/li[11]/li[2]", GA, court, office_label="Supreme Court")
    ca = cl("ndi:p0/upcoming-c13", GA, court, office_label="Court of Appeals")
    res = result(sc, ca)
    assert len(children(res)) == 2 and all(k.aggregate for k in children(res))
    assert check([sc, ca], res) == ()
    folded, kid = fold(res, sc, ca)
    assert kid == "fbf26945d0d5"
    assert check([sc, ca], folded) == (
        f"wrong merge: {kid}: {ca.merge_id} and {sc.merge_id} have other labels",
    )
    same = cl("ndi:p0/upcoming-c14", GA, court, office_label="supreme  court")
    res = result(sc, same)
    assert len(children(res)) == 1 and children(res)[0].aggregate
    assert check([sc, same], res) == ()


def test_wrong_merge_attached_date_needs_a_month_disagreement() -> None:
    e1 = cl(f"{EGU}/r1")
    w = mk("ndi:p0/upcoming-c1", span=month(2026, 11), date_status="tentative",
           date_meaning="unknown")
    res = result(e1, w)
    (kid,) = [k.child_id for k in children(res)]
    assert kid == "605682096ffe"
    other = "wrong merge: 605682096ffe: served/ndi:p0/upcoming-c1#0 has another date"
    for span, expected in (
        (day(2026, 11, 20), (other + " that is not a month disagreement",)),
        (month(2026, 12), ()),
        (month(2027, 1), (other + " that is not a month disagreement",)),
    ):
        nw = replace(w, span=span)
        damaged = with_child(with_claim(res, w.merge_id, nw), kid, date_conflict=True)
        assert check([e1, nw], damaged) == expected, span
