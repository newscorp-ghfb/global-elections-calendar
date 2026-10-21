"""Office classes, institutions and level evidence (spec §6.3, §6.4).

Labels are real strings from the 2026-10-16 sources.
"""

import pytest
import yaml

from elections_calendar.model import JurisdictionKind, Level
from elections_calendar.offices import (
    Chamber,
    InstitutionRegistry,
    _split_top_level,
    claim_level,
    extract_round,
    is_by_election,
    is_executive_title,
    keyword_class,
    labels_similar,
    office_class_of,
    resolve_level,
    split_offices,
    unnamed_parts,
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
        ("President (round 0)", None, "President (round 0)"),  # no round 0: Claim refuses it
        ("President (0th round)", None, "President (0th round)"),
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


def test_office_titles_are_not_general_elections() -> None:
    for title in ("Attorney General", "Auditor General", "Solicitor General", "Secretary General"):
        assert keyword_class(title) is None
    assert keyword_class("General") == "general"


def test_a_seat_district_is_not_a_local_body() -> None:
    assert keyword_class("36th State Assembly district, special election") == "legislature"
    assert keyword_class("Assembly district 5") == "legislature"
    assert keyword_class("District council elections") == "local_council"
    assert keyword_class("school district") is None
    assert classify("36th State Assembly district, special election", "iso:US", "subdivision") == (
        "legislature", None, False, "by_election", None, "subnational")


def test_body_names_from_the_captured_pages() -> None:
    for name in ("Landtag", "Cortes", "Abgeordnetenhaus", "Kantonsrat", "Grosser Rat", "Bürgerschaft"):
        assert keyword_class(name) == "legislature"
    for name in ("Gemeinderat", "Bezirksverordnetenversammlungen", "Board of Supervisors"):
        assert keyword_class(name) == "local_council"
    assert keyword_class("Landrat") is None
    assert keyword_class("amendments") == keyword_class("constitutional amendment") == "referendum"


def test_a_federal_council_is_a_national_aggregate() -> None:
    assert classify("Federal Council", "iso:DE")[:2] == ("upper_house", "iso:DE/federal-council")
    # iso:CH is semantic-table row S14


def test_chamber_aliases_from_the_captured_pages() -> None:
    assert classify("Chamber of Representatives", "iso:MA")[:2] == (
        "lower_house", "iso:MA/house-of-representatives")
    assert classify("Dáil by-election", "iso:IE", "named")[:4] == (
        "lower_house", "iso:IE/house-of-representatives", False, "by_election")
    assert classify("Seanad", "iso:IE")[:2] == ("upper_house", "iso:IE/senate")
    assert classify("Seimas by-election", "iso:LT", "named")[:4] == (
        "legislature", "iso:LT/parliament", False, "by_election")
    assert classify("People's National Assembly", "iso:DZ")[:2] == (
        "lower_house", "iso:DZ/national-peoples-assembly")


@pytest.mark.parametrize(
    ("label", "place", "jkind", "expected"),
    [
        pytest.param("United States Senate special election", "iso:US", "subdivision",
                     ("upper_house", "iso:US/senate", False, "by_election", "national", True, False), id="S1"),
        pytest.param("State Senate", "iso:US", "subdivision",
                     ("upper_house", None, False, "candidate_election", "subnational", True, False), id="S2"),
        pytest.param("Senate", "iso:US", "subdivision",
                     ("upper_house", None, False, "candidate_election", None, True, False), id="S3"),
        pytest.param("Senate special election", "iso:US", "named",
                     ("upper_house", None, False, "by_election", None, True, False), id="S4"),
        pytest.param("House of Commons by-election", "iso:GB", "named",
                     ("lower_house", "iso:GB/house-of-commons", False, "by_election", "national", True, False),
                     id="S5"),
        pytest.param("by-election", "iso:CA", "named",
                     ("general", None, True, "aggregate", None, False, False), id="S6"),
        pytest.param("Vice President", "iso:MM", "nationwide",
                     ("general", None, True, "aggregate", None, False, True), id="S7"),
        pytest.param("President and Vice President", "iso:US", "nationwide",
                     ("head_of_state", "iso:US/president", False, "candidate_election", "national", True, False),
                     id="S8"),
        pytest.param("Lieutenant Governor", "iso:US", "subdivision",
                     ("general", None, True, "aggregate", None, False, True), id="S9"),
        pytest.param("Governor and Lieutenant Governor", "iso:US", "subdivision",
                     ("governor", None, False, "candidate_election", "subnational", True, False), id="S10"),
        pytest.param("City Attorney (1st round)", "iso:US", "subdivision",
                     ("general", None, True, "aggregate", None, False, True), id="S11"),
        pytest.param("Supreme Leader", "iso:IR", "nationwide",
                     ("general", None, True, "aggregate", None, False, False), id="S12"),
        pytest.param("Supreme Court", "iso:US", "subdivision",
                     ("general", None, True, "aggregate", None, False, False), id="S13"),
        pytest.param("Federal Council", "iso:CH", "nationwide",
                     ("general", None, True, "aggregate", "national", True, False), id="S14"),
        pytest.param("Board of Supervisors", "iso:US", "subdivision",
                     ("local_council", None, True, "aggregate", "subnational", True, False), id="S15"),
        pytest.param("Ethiopian House of People's Representatives", "iso:ET", "nationwide",
                     ("lower_house", "iso:ET/house-of-peoples-representatives", False, "candidate_election",
                      "national", True, False), id="S16"),
        pytest.param("Dutch Second Chamber", "iso:NL", "nationwide",
                     ("lower_house", "iso:NL/house-of-representatives", False, "candidate_election",
                      "national", True, False), id="S17"),
    ],
)
def test_semantic_table(label: str, place: str, jkind: JurisdictionKind, expected: tuple[object, ...]) -> None:
    o = classify_office(label, place, jkind, REGISTRY)
    assert (o.office_class, o.institution, o.aggregate, o.kind, o.level_hint, o.recognised,
            is_executive_title(label)) == expected


def test_claim_level_never_guesses_for_an_unrecognised_office() -> None:
    assert claim_level("subnational", classify_office("by-election", "iso:CA", "named", REGISTRY)) == "unknown"
    assert claim_level("subnational", classify_office("Senate", "iso:US", "subdivision", REGISTRY)) == "subnational"
    assert claim_level("national", classify_office("Senate", "iso:US", "subdivision", REGISTRY)) == "national"
    assert claim_level("subnational", classify_office("State Duma", "iso:RU", "nationwide", REGISTRY)) == "national"


def test_split_offices_drops_the_oxford_and() -> None:
    assert split_offices(
        "Mayor (1st round), City Attorney (1st round), City Controller, and City Council (1st round)",
        "iso:US", REGISTRY) == ["Mayor (1st round)", "City Attorney (1st round)", "City Controller",
                                "City Council (1st round)"]
    assert split_offices("Governor, Lieutenant Governor, and ballot measure", "iso:US", REGISTRY) == [
        "Governor", "Lieutenant Governor", "ballot measure"]


def test_executive_titles_split_lists_and_joint_tickets_stay_whole() -> None:
    assert split_offices("Governor, Lieutenant Governor, and Attorney General", "iso:US", REGISTRY) == [
        "Governor", "Lieutenant Governor", "Attorney General"]
    assert split_offices(
        "Governor, Lieutenant Governor, Secretary of State, Attorney General, ballot measures",
        "iso:US", REGISTRY) == ["Governor", "Lieutenant Governor", "Secretary of State",
                                "Attorney General", "ballot measures"]
    assert split_offices("Mayor and Attorney General", "iso:US", REGISTRY) == ["Mayor", "Attorney General"]
    for ticket in ("Governor and Lieutenant Governor", "President and Vice President"):
        assert split_offices(ticket, "iso:US", REGISTRY) == [ticket]
    assert [p for p in ("Governor", "Lieutenant Governor", "Secretary of State", "City Controller",
                        "Sheriff (1st round)", "Commissioner of Labor", "Governor and Lieutenant Governor",
                        "City Council") if is_executive_title(p)] == [
        "Lieutenant Governor", "Secretary of State", "City Controller", "Sheriff (1st round)",
        "Commissioner of Labor"]


def test_public_helpers() -> None:
    assert office_class_of("Senedd", "iso:GB-WLS", REGISTRY) == "legislature"
    assert office_class_of("by-election", "iso:GB", REGISTRY) is None
    assert office_class_of("Attorney General", "iso:US", REGISTRY) == "general"
    assert office_class_of("Georgia's 13th congressional district", "iso:US", REGISTRY) == "legislature"
    assert is_by_election("Georgia's 13th congressional district, special election (1st round)")
    assert not is_by_election("Governor")


def test_a_joint_ticket_followed_by_a_title_splits_after_the_ticket() -> None:
    assert split_offices(
        "Governor and Lieutenant Governor, Secretary of State", "iso:US", REGISTRY
    ) == ["Governor and Lieutenant Governor", "Secretary of State"]
    assert office_class_of("Governor and Lieutenant Governor", "iso:US", REGISTRY) == "governor"
    assert office_class_of("Attorney General", "iso:US", REGISTRY) == "general"


def test_a_hyphenated_lieutenant_title_is_not_its_principal() -> None:
    o = classify_office("Lieutenant-Governor", "iso:US", "subdivision", REGISTRY)
    assert (o.office_class, o.recognised) == ("general", False)
    assert is_executive_title("Lieutenant-Governor")


@pytest.mark.parametrize("letter", ["ı", "İ"])
def test_a_round_word_with_letters_only_ignorecase_folds_is_no_round(letter: str) -> None:
    # "f{letter}rst" matches the round pattern case-insensitively; casefold() does not map it to "first"
    number, rest = extract_round(f"President (f{letter}rst round)")
    assert number is None
    assert "President" in rest


def test_the_same_round_words_without_the_odd_letters_still_parse() -> None:
    assert extract_round("President (first round)") == (1, "President")
    assert extract_round("President (second round)") == (2, "President")


@pytest.mark.parametrize(
    "label",
    ["Vice gubernatorial election", "vice-gubernatorial", "Deputy gubernatorial", "Lieutenant gubernatorial"],
)
def test_a_vice_gubernatorial_title_is_not_a_governor(label: str) -> None:
    o = classify_office(label, "iso:PH", "subdivision", REGISTRY)
    assert (o.office_class, o.recognised) == ("general", False)
    assert is_executive_title(label)


@pytest.mark.parametrize("label", ["Gubernatorial election", "Governor", "Provincial gubernatorial"])
def test_a_gubernatorial_title_is_still_a_governor(label: str) -> None:
    assert classify_office(label, "iso:PH", "subdivision", REGISTRY).office_class == "governor"
    assert not is_executive_title(label)


def test_split_top_level_when_casefold_changes_length() -> None:
    assert _split_top_level("Großrat and Senate", (" and ",)) == ["Großrat", "Senate"]
    assert _split_top_level("İl Genel Meclisi and Senate", (" and ",)) == [
        "İl Genel Meclisi",
        "Senate",
    ]


@pytest.mark.parametrize(
    ("text", "place_id", "expected"),
    [
        ("President and Xyz", "iso:TD", ["Xyz"]),
        ("Presidential and Xyz Elections", "iso:CL", ["Xyz Elections"]),
        ("President, Senate and Xyz", "iso:TD", ["Xyz"]),
        ("President & Xyz", "iso:TD", ["Xyz"]),
        ("President and National Assembly", "iso:TD", []),
        ("Regional and local", "iso:TD", []),
        ("Xyz and Abc", "iso:TD", []),
        ("President (first and second round)", "iso:TD", []),
        ("General Elections", "iso:TD", []),
        ("", "iso:TD", []),
    ],
)
def test_unnamed_parts(text: str, place_id: str, expected: list[str]) -> None:  # P64
    assert unnamed_parts(text, place_id, REGISTRY) == expected


@pytest.mark.parametrize(
    ("text", "place_id", "expected"),
    [
        ("Presidential and Vice-Presidential", "iso:PH", []),
        ("Presidential and Vice Presidential", "iso:NG", []),
        ("Governor and Lieutenant Governor", "iso:US", []),
        ("Gubernatorial and Lieutenant Gubernatorial", "iso:US", []),
        ("Mayoral and Vice-Mayoral", "iso:PH", []),
        ("National and Provincial", "iso:ZA", ["National"]),
    ],
)
def test_joint_ticket_is_not_unnamed_parts(  # R21, P102
    text: str, place_id: str, expected: list[str]
) -> None:
    assert unnamed_parts(text, place_id, REGISTRY) == expected
    assert split_offices("Presidential and Vice-Presidential", "iso:PH", REGISTRY) == [
        "Presidential and Vice-Presidential"
    ]
