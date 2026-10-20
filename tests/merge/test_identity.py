"""Identity, roles and the same-source rule of the merge (spec 10.1, 10.2; P66, P67, P70, P78, P80)."""

from typing import Any

import pytest

from elections_calendar.merge.identity import (
    PRIORITY,
    SOURCE_ORDER,
    MergeError,
    claim_order,
    dates_compatible,
    family,
    gap_days,
    identity_compatible,
    qualified_numbers,
    role,
    same_source_compatible,
    short_id,
    years_of,
)
from tests.support.claims import OBS, RENEW, UMB, day, days, mk, month, months, year
from tests.support.fixture_claims import fixture_claim

EG = "electionguide:upcoming/r1"
OSCE = "osce:elections/r1"
QUESTION: dict[str, Any] = dict(
    institution=None,
    office_class="referendum",
    kind="referendum_question",
    office_label="Question A",
)


def test_family_and_claim_order() -> None:
    assert family(mk("wikipedia:national-2026@rev1/November/li[1]")) == "wikipedia:national"
    assert family(mk("wikipedia:local-2026@rev2/November/li[1]")) == "wikipedia:local"
    assert family(mk("ndi:p0/upcoming-c1")) == "ndi"
    claims = [
        mk("eeas:missions/r1c1"),
        mk("ipu:elections/r5"),
        mk("ndi:p0/upcoming-c1"),
        mk("wikipedia:local-2026@rev2/November/li[1]"),
        mk("wikipedia:national-2026@rev1/November/li[1]"),
        mk("electionguide:upcoming/r1"),
    ]
    assert [family(c) for c in sorted(claims, key=claim_order)] == [
        "electionguide",
        "wikipedia:national",
        "wikipedia:local",
        "ndi",
        "ipu",
        "eeas",
    ]
    ids = [
        mk("electionguide:upcoming/r3", source_event_id="electionguide:9"),
        mk("electionguide:upcoming/r2", source_event_id="electionguide:10"),
        mk("electionguide:upcoming/r1"),
    ]
    assert [c.unit_id[-2:] for c in sorted(ids, key=claim_order)] == ["r2", "r3", "r1"]
    assert PRIORITY == (
        "electionguide",
        "osce",
        "wikipedia:national",
        "wikipedia:local",
        "ndi",
        "aweb",
        "eisa",
        "ipu",
        "carter",
        "eeas",
    )
    assert SOURCE_ORDER == (
        "electionguide",
        "osce",
        "wikipedia",
        "ndi",
        "aweb",
        "eisa",
        "ipu",
        "carter",
        "eeas",
    )


def test_unknown_source_is_a_merge_error() -> None:
    with pytest.raises(MergeError, match="unknown source: xyz"):
        family(mk("xyz:p/r1"))


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        pytest.param({}, "anchor", id="plain"),
        pytest.param(dict(provisional=True, **UMB), "provisional", id="provisional"),
        pytest.param(OBS, "weak", id="observation"),
        pytest.param(UMB, "umbrella", id="umbrella"),
        pytest.param(dict(institution=None, aggregate=True), "umbrella", id="aggregate"),
        pytest.param(
            dict(jurisdiction="Bahia", jurisdiction_kind="subdivision"), "anchor", id="subdivision"
        ),
        pytest.param(dict(jurisdiction="Lima", jurisdiction_kind="named"), "anchor", id="named"),
        pytest.param(dict(jurisdiction_kind="unknown"), "weak", id="unknown-jurisdiction"),
        pytest.param(dict(span=month(2026, 11)), "weak", id="month"),
        pytest.param(dict(span=year(2026)), "weak", id="year"),
        pytest.param(dict(date_meaning="unknown"), "weak", id="meaning-unknown"),
        pytest.param(RENEW, "weak", id="renewal"),
        pytest.param(dict(institution=None, office_class="mayor"), "weak", id="no-institution"),
        pytest.param(
            dict(institution=None, office_class="referendum", kind="referendum_day"),
            "anchor",
            id="referendum-day",
        ),
        pytest.param(dict(round=2), "anchor", id="round-2"),
    ],
)
def test_roles(changes: dict[str, Any], expected: str) -> None:
    assert role(mk(EG, **changes)) == expected


Q_B = {**QUESTION, "office_label": "question  a"}
Q_DAY: dict[str, Any] = dict(kind="referendum_day", office_label="Referendum")
DISTRICT_12 = "State House District 12 special election"


@pytest.mark.parametrize(
    ("a", "b", "kw", "expected"),
    [
        pytest.param({}, {}, {}, True, id="same"),
        pytest.param({}, dict(place_id="iso:NO"), {}, False, id="place"),
        pytest.param({}, dict(level="subnational"), {}, False, id="level"),
        pytest.param({}, dict(level="unknown"), {}, True, id="level-unknown"),
        pytest.param({}, dict(institution="iso:SE/other"), {}, False, id="institution"),
        pytest.param({}, dict(institution=None), {}, True, id="no-institution-same-class"),
        pytest.param(
            {}, dict(institution=None, office_class="head_of_state"), {}, False, id="class"
        ),
        pytest.param(
            {},
            dict(jurisdiction="Lima", jurisdiction_kind="named"),
            {},
            False,
            id="nationwide-vs-named",
        ),
        pytest.param(
            dict(jurisdiction="Lima", jurisdiction_kind="named"),
            dict(jurisdiction="lima ", jurisdiction_kind="subdivision"),
            {},
            True,
            id="named-vs-subdivision",
        ),
        pytest.param(
            dict(jurisdiction="Lima", jurisdiction_kind="named"),
            dict(jurisdiction="Cusco", jurisdiction_kind="named"),
            {},
            False,
            id="two-names",
        ),
        pytest.param({}, dict(jurisdiction_kind="unknown"), {}, False, id="unknown-never-agrees"),
        pytest.param(
            {},
            dict(jurisdiction_kind="unknown"),
            dict(relax_jurisdiction=True),
            True,
            id="unknown-relaxed",
        ),
        pytest.param(
            dict(jurisdiction="Bahia", jurisdiction_kind="subdivision", level="unknown"),
            {},
            dict(relax_jurisdiction=True),
            False,
            id="subdivision-vs-nationwide-R7",
        ),
        pytest.param(dict(round=1), dict(round=2), {}, False, id="rounds-differ"),
        pytest.param(dict(round=1), {}, {}, True, id="round-one-sided"),
        pytest.param({}, dict(kind="by_election"), {}, False, id="kind"),
        pytest.param({}, dict(kind="by_election"), dict(ignore_kind=True), True, id="ignore-kind"),
        pytest.param(
            {},
            dict(institution="iso:SE/other"),
            dict(ignore_institution=True),
            True,
            id="ignore-institution",
        ),
        pytest.param(QUESTION, Q_B, {}, True, id="question-same-label"),
        pytest.param(
            QUESTION, {**QUESTION, "office_label": "Question B"}, {}, False, id="question-label"
        ),
        pytest.param(
            QUESTION, {**QUESTION, **Q_DAY}, dict(ignore_kind=True), True, id="question-vs-day"
        ),
        pytest.param(
            dict(office_label=DISTRICT_12),
            dict(office_label="12th State House District"),
            {},
            True,
            id="district-ordinal",
        ),
        pytest.param(
            dict(office_label=DISTRICT_12),
            dict(office_label="Louisiana State House District 40 Special Election"),
            {},
            False,
            id="district-12-vs-40",
        ),
        pytest.param(
            dict(office_label="District 12, Phase 2"),
            dict(office_label="District 2, Phase 12"),
            {},
            False,
            id="district-phase-swapped",
        ),
        pytest.param(
            dict(office_label="Riksdag (150 seats)"),
            dict(office_label="Riksdag (349 seats)"),
            {},
            True,
            id="seat-total",
        ),
        pytest.param(dict(office_label="District 12"), {}, {}, True, id="number-one-side"),
        pytest.param(
            dict(office_label="District 12"),
            dict(office_label="District 40"),
            dict(ignore_kind=True, ignore_institution=True),
            False,
            id="numbers-never-skipped",
        ),
        pytest.param(
            dict(jurisdiction="Bahia", jurisdiction_kind="subdivision"),
            dict(jurisdiction="Lima", jurisdiction_kind="nationwide"),
            {},
            False,
            id="subdivision-meets-nationwide",
        ),
    ],
)
def test_identity_compatible(
    a: dict[str, Any], b: dict[str, Any], kw: dict[str, Any], expected: bool
) -> None:
    assert identity_compatible(mk(EG, **a), mk(OSCE, **b), **kw) is expected


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("State House District 12 special election", {"district": {12}}),
        ("12th State House District", {"district": {12}}),
        ("District No. 12", {"district": {12}}),
        ("District 12, Phase 2", {"district": {12}, "phase": {2}}),
        ("District 2, Phase 12", {"district": {2}, "phase": {12}}),
        ("12th District, Phase 2", {"district": {12}, "phase": {2}}),
        ("Parliament (2nd phase)", {"phase": {2}}),
        ("Senate (series 2)", {"series": {2}}),
        ("5th Ward", {"ward": {5}}),
        ("Ward 5 by-election", {"ward": {5}}),
        (
            "18th congressional district, special election (2nd round)",
            {"district": {18}},
        ),
        ("150 seats", {}),
        ("National Assembly, 14 by-elections", {}),
        ("2026 General Election", {}),
        ("House of Representatives Carroll 7 district, special election", {}),
    ],
)
def test_qualified_numbers(label: str, expected: dict[str, set[int]]) -> None:
    assert qualified_numbers(label) == {k: frozenset(v) for k, v in expected.items()}


def test_same_source_compatible() -> None:
    a = mk("wikipedia:local-2026@rev2/November/li[9]/li[1]", office_label=DISTRICT_12)
    other = mk(
        "wikipedia:local-2026@rev2/November/li[9]/li[2]",
        office_label="State House District 40 special election",
    )
    same = mk(
        "wikipedia:local-2026@rev2/November/li[9]/li[2]",
        office_label="state house district 12 special  election",
    )
    assert same_source_compatible(a, other) is False
    assert same_source_compatible(a, same) is True
    national = mk("wikipedia:national-2026@rev1/November/li[1]")
    local = mk("wikipedia:local-2026@rev2/November/li[1]", office_label="Swedish general election")
    assert same_source_compatible(national, local) is True
    assert same_source_compatible(
        mk("electionguide:upcoming/r1"), mk("osce:elections/r1", office_label="Parliamentary Elections")
    )
    assert not same_source_compatible(
        mk("ndi:p0/upcoming-c1", office_label="2026 Côte d'Ivoire Presidential Election"),
        mk("ndi:p0/upcoming-c2", office_label="2026 Ivory Coast Presidential Election"),
    )


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        pytest.param(day(2026, 11, 15), day(2026, 11, 15), True, id="same-day"),
        pytest.param(day(2026, 11, 15), day(2026, 11, 16), False, id="no-tolerance"),
        pytest.param(days(2026, 11, 14, 2026, 11, 15), day(2026, 11, 15), True, id="range"),
        pytest.param(month(2026, 11), day(2026, 11, 15), True, id="month-in"),
        pytest.param(month(2026, 10), day(2026, 11, 15), False, id="month-out"),
        pytest.param(year(2026), day(2026, 11, 15), True, id="year-in"),
        pytest.param(year(2026), year(2027), False, id="year-year"),
        pytest.param(year(2027), months(2026, 12, 2027, 1), True, id="year-months"),
    ],
)
def test_dates_compatible(a: Any, b: Any, expected: bool) -> None:
    assert dates_compatible(mk(EG, span=a), mk(OSCE, span=b)) is expected


def test_gap_days_years_and_short_id() -> None:
    assert gap_days(day(2026, 11, 15), day(2026, 11, 18)) == 3
    assert gap_days(day(2026, 11, 18), day(2026, 11, 15)) == 3
    assert gap_days(day(2026, 11, 15), days(2026, 11, 14, 2026, 11, 16)) == 0
    assert gap_days(month(2026, 12), month(2027, 1)) == 1
    with pytest.raises(ValueError, match="gap_days needs dated spans"):
        gap_days(year(2026), day(2026, 11, 15))
    assert years_of(year(2026)) == {2026}
    assert years_of(months(2026, 12, 2027, 1)) == {2026, 2027}
    assert short_id(["b", "a"]) == short_id(["a", "b"]) == "fcd127ffa101"
    assert short_id(["served/electionguide:past/r4#0"]) == "6d12862ffe3c"


@pytest.mark.parametrize(
    ("claim_id", "institution"),
    [
        ("osce:elections/r52#0", "iso:BA/presidency"),
        ("aweb:calendar/r5#0", "iso:PK/national-assembly"),
        ("ndi:p0/past-c6#0", "iso:PH/house-of-representatives"),
    ],
)
def test_subdivision_claim_never_joins_a_nationwide_contest(
    claim_id: str, institution: str
) -> None:
    c = fixture_claim(claim_id)
    assert c.jurisdiction_kind == "subdivision"
    assert c.level == "unknown"
    assert role(c) == "weak"
    nat = mk(
        "electionguide:past/r90",
        place_id=c.place_id,
        place_raw=c.place_raw,
        institution=institution,
        office_class=c.office_class,
        office_label="national",
        span=c.span,
    )
    assert identity_compatible(c, nat) is False
    assert identity_compatible(c, nat, relax_jurisdiction=True) is False
