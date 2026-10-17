"""Office classes, institutions and level evidence (spec §6.3, §6.4).

Labels are real strings from the 2026-10-16 sources.
"""

import pytest
import yaml

from elections_calendar.model import JurisdictionKind, Level
from elections_calendar.offices import (
    Chamber,
    InstitutionRegistry,
    extract_round,
    labels_similar,
    resolve_level,
    split_offices,
)
from elections_calendar.offices import classify as classify_office
from elections_calendar.places import PlaceRegistry
from scripts.build_institutions import IPU_TABLE, MANUAL, OUT, BuildError, build, render

REGISTRY = InstitutionRegistry.load()


def classify(label: str, place_id: str, kind: JurisdictionKind = "nationwide") -> tuple[object, ...]:
    o = classify_office(label, place_id, kind, REGISTRY)
    return (o.office_class, o.institution, o.aggregate, o.kind, o.round, o.level_hint)


@pytest.mark.parametrize(
    ("label", "place_id", "expected"),
    [
        # specific chambers, by IPU name or alias
        ("Serbian National Assembly", "iso:RS", ("legislature", "iso:RS/national-assembly", False, "candidate_election", None, "national")),
        ("Israeli Knesset", "iso:IL", ("legislature", "iso:IL/parliament", False, "candidate_election", None, "national")),
        ("Riksdag", "iso:SE", ("legislature", "iso:SE/parliament", False, "candidate_election", None, "national")),
        ("State Duma", "iso:RU", ("lower_house", "iso:RU/state-duma", False, "candidate_election", None, "national")),
        ("Chamber of Deputies", "iso:BR", ("lower_house", "iso:BR/chamber-of-deputies", False, "candidate_election", None, "national")),
        ("House of Keys", "iso:IM", ("lower_house", "iso:IM/house-of-keys", False, "candidate_election", None, "national")),
        ("House of Representatives", "iso:NZ", ("legislature", "iso:NZ/house-of-representatives", False, "candidate_election", None, "national")),
        # generic chamber words resolve to the place's one chamber of that class
        ("Senate", "iso:BR", ("upper_house", "iso:BR/federal-senate", False, "candidate_election", None, "national")),
        ("Czech Senate", "iso:CZ", ("upper_house", "iso:CZ/senate", False, "candidate_election", None, "national")),
        ("Senate (1st round)", "iso:CZ", ("upper_house", "iso:CZ/senate", False, "candidate_election", 1, "national")),
        # generic legislature words: identity only for a unicameral place
        ("Parliament", "iso:SE", ("legislature", "iso:SE/parliament", False, "candidate_election", None, "national")),
        ("Parliamentary Elections", "iso:RS", ("legislature", "iso:RS/national-assembly", False, "candidate_election", None, "national")),
        ("Parliament", "iso:DK", ("legislature", "iso:DK/danish-parliament", False, "candidate_election", None, "national")),
        ("Early Parliamentary Elections", "iso:ES", ("legislature", None, True, "aggregate", None, None)),
        ("Mid-term Congressional Elections", "iso:US", ("legislature", None, True, "aggregate", None, None)),
        ("Bangsamoro Parliament", "iso:PH", ("legislature", None, True, "aggregate", None, None)),
        # heads of state, rounds
        ("President (1st round)", "iso:BR", ("head_of_state", "iso:BR/president", False, "candidate_election", 1, "national")),
        ("Brazilian Presidency", "iso:BR", ("head_of_state", "iso:BR/president", False, "candidate_election", None, "national")),
        ("Presidential Election, Second Round", "iso:BG", ("head_of_state", "iso:BG/president", False, "candidate_election", 2, "national")),
        # subnational offices
        ("Guamanian Governor", "iso:GU", ("governor", None, False, "candidate_election", None, "subnational")),
        ("Governors", "iso:BR", ("governor", None, True, "aggregate", None, "subnational")),
        ("Governorial", "iso:NG", ("governor", None, False, "candidate_election", None, "subnational")),  # NDI's spelling
        ("municipal elections", "iso:CZ", ("local_council", None, True, "aggregate", None, "subnational")),
        ("regional and municipal elections", "iso:SE", ("local_council", None, True, "aggregate", None, "subnational")),
        ("regional and local elections", "iso:SK", ("local_council", None, True, "aggregate", None, "subnational")),
        ("Local Elections", "iso:SI", ("local_council", None, True, "aggregate", None, "subnational")),
        # referendums
        ("Constitutional referendum", "iso:FJ", ("referendum", None, False, "referendum_day", None, "national")),
        ("Referendums", "iso:CH", ("referendum", None, False, "referendum_day", None, "national")),
        # aggregates and unrecognised text
        ("General", "iso:FJ", ("general", None, True, "aggregate", None, None)),
        ("Ontario", "iso:CA", ("general", None, True, "aggregate", None, None)),
    ],
)
def test_classify_nationwide(label: str, place_id: str, expected: tuple[object, ...]) -> None:
    assert classify(label, place_id) == expected


@pytest.mark.parametrize(
    ("label", "place_id", "expected"),
    [
        # a generic chamber name under a named jurisdiction is not the national chamber...
        ("Senate", "iso:US", ("upper_house", None, False, "candidate_election", None, None)),
        ("Legislative Assembly", "iso:CA", ("legislature", None, True, "aggregate", None, None)),
        # ...unless it is a by-election to it
        ("House of Commons by-election", "iso:GB", ("lower_house", "iso:GB/house-of-commons", False, "by_election", None, "national")),
        ("Legislative Assembly by-election", "iso:WS", ("legislature", "iso:WS/legislative-assembly", False, "by_election", None, "national")),
        ("mayoral by-election (1st round)", "iso:PL", ("mayor", None, False, "by_election", 1, "subnational")),
        ("Governor", "iso:BR", ("governor", None, False, "candidate_election", None, "subnational")),
        ("city council", "iso:PL", ("local_council", None, False, "candidate_election", None, "subnational")),
        ("municipal elections", "iso:CA", ("local_council", None, True, "aggregate", None, "subnational")),
        ("President", "iso:BA", ("head_of_state", None, False, "candidate_election", None, None)),
        ("referendum", "iso:IT", ("referendum", None, False, "referendum_day", None, "subnational")),
    ],
)
def test_classify_named_jurisdiction(label: str, place_id: str, expected: tuple[object, ...]) -> None:
    assert classify(label, place_id, "named") == expected


def test_unrecognised_labels_are_flagged() -> None:
    assert not classify_office("Ontario", "iso:CA", "named", REGISTRY).recognised
    assert classify_office("General", "iso:FJ", "nationwide", REGISTRY).recognised
    assert classify_office("State Duma", "iso:RU", "nationwide", REGISTRY).label == "State Duma"


@pytest.mark.parametrize(
    ("text", "place_id", "parts"),
    [
        ("President (1st round), Chamber of Deputies and Senate", "iso:BR", ["President (1st round)", "Chamber of Deputies", "Senate"]),
        ("House of Representatives and Senate", "iso:US", ["House of Representatives", "Senate"]),
        ("President, Senate and House of Representatives", "iso:NG", ["President", "Senate", "House of Representatives"]),
        ("President, Assembly and Council of States", "iso:SS", ["President", "Assembly", "Council of States"]),
        ("President and Parliamentary", "iso:BJ", ["President", "Parliamentary"]),  # EISA
        ("National Assembly and local", "iso:CV", ["National Assembly", "local"]),  # EISA
        ("Mayor and city council", "iso:PL", ["Mayor", "city council"]),
        ("Local and District Councils", "iso:ZM", ["Local and District Councils"]),  # EISA
        ("regional and municipal elections", "iso:SE", ["regional and municipal elections"]),
        ("Regional, municipal and local elections", "iso:PE", ["Regional, municipal and local elections"]),
        ("President and Vice President", "iso:US", ["President and Vice President"]),
        ("Holborn and St Pancras", "iso:GB", ["Holborn and St Pancras"]),
        ("State Duma", "iso:RU", ["State Duma"]),
        ("", "iso:RU", []),
    ],
)
def test_split_offices(text: str, place_id: str, parts: list[str]) -> None:
    assert split_offices(text, place_id, REGISTRY) == parts


@pytest.mark.parametrize(
    ("text", "number", "rest"),
    [
        ("President (1st round)", 1, "President"),
        ("Senate (2nd round)", 2, "Senate"),
        ("Presidential Election, First Round", 1, "Presidential Election"),
        ("Presidential run-off", 2, "Presidential"),
        ("Governor runoff", 2, "Governor"),
        ("President, round 2", 2, "President"),
        ("Brazilian Presidency", None, "Brazilian Presidency"),
        ("Haiti General Election (Phase 1)", None, "Haiti General Election (Phase 1)"),  # a phase is not a round
    ],
)
def test_extract_round(text: str, number: int | None, rest: str) -> None:
    assert extract_round(text) == (number, rest)


def test_labels_similar_is_the_v1_stem_rule() -> None:
    assert labels_similar("Brazilian Presidency", "President (1st round)")
    assert not labels_similar("President (1st round)", "President (2nd round)")
    assert not labels_similar("Chamber of Deputies", "Senate")
    assert labels_similar("", "Senate")  # empty labels are compatible, as in v1


@pytest.mark.parametrize(
    ("default", "hints", "level"),
    [
        ("subnational", ["national"], "national"),  # Holborn: office evidence wins
        ("national", [None], "national"),  # no evidence: source default
        ("subnational", [None, None], "subnational"),
        ("national", ["national", "subnational"], "unknown"),  # conflicting evidence
        (None, [], "unknown"),  # no default, no evidence
        (None, ["subnational"], "subnational"),
    ],
)
def test_resolve_level(default: Level | None, hints: list[Level | None], level: Level) -> None:
    assert resolve_level(default, hints) == level


def test_committed_institutions_yaml_is_up_to_date() -> None:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    html = IPU_TABLE.read_text(encoding="utf-8")
    expected = render(build(html, manual, PlaceRegistry.load()))
    assert OUT.read_text(encoding="utf-8") == expected, "run python -m scripts.build_institutions and commit data/institutions.yaml"


def test_build_rejects_an_alias_for_a_missing_chamber() -> None:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    manual["aliases"]["iso:SE"] = {"Riksdag of the Estates": ["Riksdag"]}
    with pytest.raises(BuildError, match="no IPU chamber"):
        build(IPU_TABLE.read_text(encoding="utf-8"), manual, PlaceRegistry.load())


def test_suspended_chambers_keep_their_identity_but_are_not_active() -> None:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    built = build(IPU_TABLE.read_text(encoding="utf-8"), manual, PlaceRegistry.load())
    kz = {c["name"]: c["status"] for c in built["iso:KZ"]}
    assert kz == {"Kurultai": "active", "Senate": "suspended"}  # IPU: "Senate (Suspended)"
    assert {c["status"] for c in built["iso:AF"]} == {"suspended"}  # both chambers
    only = REGISTRY.unicameral("iso:KZ")
    assert only is not None and only.name == "Kurultai"
    assert REGISTRY.unicameral("iso:KW") is None  # its only chamber is suspended
    # the name still identifies the chamber (older or renewal evidence)...
    assert classify("National Assembly", "iso:KW") == ("legislature", "iso:KW/national-assembly", False, "candidate_election", None, "national")
    # ...but generic words never resolve to a chamber that is not active
    assert classify("Parliament", "iso:KW") == ("legislature", None, True, "aggregate", None, None)


def test_build_rejects_a_bicameral_place_left_with_one_active_chamber() -> None:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    html = IPU_TABLE.read_text(encoding="utf-8")
    assert html.count(">Federal Senate</a>") == 1
    html = html.replace(">Federal Senate</a>", ">Federal Senate (Suspended)</a>")
    with pytest.raises(BuildError, match="iso:BR"):
        build(html, manual, PlaceRegistry.load())


@pytest.mark.parametrize(
    ("label", "place_id", "kind", "expected"),
    [
        # a subnational qualifier outranks the chamber's name...
        ("State Senate by-election", "iso:US", "named", ("upper_house", None, False, "by_election", None, "subnational")),
        ("State Houses of Assembly", "iso:NG", "nationwide", ("legislature", None, False, "candidate_election", None, "subnational")),
        # ...and a by-election alone does not make a generic chamber word national
        ("House of Assembly by-election", "iso:AU", "named", ("lower_house", None, False, "by_election", None, None)),
        # a by-election to the chamber the text names, in a named constituency, is national
        ("House of Representatives by-election", "iso:MY", "named", ("lower_house", "iso:MY/house-of-representatives", False, "by_election", None, "national")),
        # a referendum that names a chamber is a referendum
        ("Referendum on reform of the Senate", "iso:US", "nationwide", ("referendum", None, False, "referendum_day", None, "national")),
        ("Senate referendum", "iso:IT", "subdivision", ("referendum", None, False, "referendum_day", None, "subnational")),
    ],
)
def test_scope_comes_before_chamber_identity(
    label: str, place_id: str, kind: JurisdictionKind, expected: tuple[object, ...]
) -> None:
    assert classify(label, place_id, kind) == expected  # constructed labels


def test_a_qualifier_in_the_chambers_own_name_is_not_scope() -> None:
    registry = InstitutionRegistry(
        {"iso:WF": (Chamber("Territorial Assembly", "legislature", "direct", (), "active"),)}
    )
    office = classify_office("Territorial Assembly", "iso:WF", "nationwide", registry)
    assert (office.institution, office.level_hint) == ("iso:WF/territorial-assembly", "national")


@pytest.mark.parametrize(
    ("label", "place_id", "kind", "expected"),
    [
        # national evidence in the text survives a state's voting area (US senators are elected by state)
        ("United States Senate special election", "iso:US", "subdivision", ("upper_house", "iso:US/senate", False, "by_election", None, "national")),
        ("U.S. Senate", "iso:US", "subdivision", ("upper_house", "iso:US/senate", False, "candidate_election", None, "national")),
        # an explicit state office is subnational
        ("State Senate special election", "iso:US", "subdivision", ("upper_house", None, False, "by_election", None, "subnational")),
        # bare chamber words in a state say neither: no institution, no level hint
        ("Senate special election", "iso:US", "subdivision", ("upper_house", None, False, "by_election", None, None)),
        ("Legislative Assembly by-election", "iso:MY", "subdivision", ("legislature", None, False, "by_election", None, None)),
        # a by-election in a national constituency names its chamber
        ("House of Commons by-election", "iso:GB", "named", ("lower_house", "iso:GB/house-of-commons", False, "by_election", None, "national")),
    ],
)
def test_the_voting_area_is_not_the_offices_level(
    label: str, place_id: str, kind: JurisdictionKind, expected: tuple[object, ...]
) -> None:
    assert classify(label, place_id, kind) == expected  # constructed labels


@pytest.mark.parametrize(
    ("label", "place_id", "expected"),
    [
        ("European Parliament election", "iso:SE", ("legislature", None, True, "aggregate", None, None)),
        ("Sami Parliament election", "iso:NO", ("legislature", None, True, "aggregate", None, None)),
        ("Moscow City Duma elections", "iso:RU", ("local_council", None, True, "aggregate", None, "subnational")),
        ("Regional presidents", "iso:PE", ("local_council", None, True, "aggregate", None, "subnational")),
        ("Municipal president", "iso:MX", ("local_council", None, True, "aggregate", None, "subnational")),
        ("Russian State Duma elections", "iso:RU", ("lower_house", "iso:RU/state-duma", False, "candidate_election", None, "national")),
        ("Presidential election", "iso:PE", ("head_of_state", "iso:PE/president", False, "candidate_election", None, "national")),
    ],
)
def test_a_body_named_inside_another_bodys_name_is_not_the_places_own(
    label: str, place_id: str, expected: tuple[object, ...]
) -> None:
    assert classify(label, place_id) == expected  # constructed labels
