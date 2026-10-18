"""Places (spec §6.2) against the committed data/places.yaml."""

from pathlib import Path

import pytest
import yaml

from elections_calendar.places import PlaceRegistry, SubdivisionIndex, named_subdivisions
from scripts.build_places import HISTORY, MANUAL, OUT, BuildError, build, load_history, render

REGISTRY = PlaceRegistry.load()
SUBDIVISIONS = SubdivisionIndex.load()


@pytest.mark.parametrize(
    ("raw", "place_id", "display"),
    [
        ("Russian Federation", "iso:RU", "Russia"),  # OSCE, IPU, ElectionGuide
        ("Russia", "iso:RU", "Russia"),  # A-WEB
        ("Czechia", "iso:CZ", "Czech Republic"),  # OSCE, IPU
        ("Türkiye", "iso:TR", "Turkey"),
        ("Cabo Verde", "iso:CV", "Cape Verde"),  # history minority spelling
        ("Gambia (The)", "iso:GM", "Gambia"),  # IPU
        ("Gambia, The", "iso:GM", "Gambia"),  # ElectionGuide
        ("Naoero", "iso:NR", "Nauru"),  # IPU uses the Nauruan name
        ("Republic of Korea", "iso:KR", "South Korea"),
        ("Democratic People's Republic of Korea", "iso:KP", "North Korea"),
        ("Lao People's Democratic Republic", "iso:LA", "Laos"),
        ("Viet Nam", "iso:VN", "Vietnam"),
        ("United States of America", "iso:US", "United States"),
        ("Congo (Brazzaville)", "iso:CG", "Republic of the Congo"),
        ("Republic of the Congo", "iso:CG", "Republic of the Congo"),
        ("Democratic Republic of the Congo", "iso:CD", "DR Congo"),
        ("Cote d’Ivoire", "iso:CI", "Côte d'Ivoire"),  # Carter Center
        ("Occupied Palestinian Territory", "iso:PS", "Palestine"),
        ("Western Sahara", "iso:EH", "Western Sahara"),  # EISA
        ("The Philippines", "iso:PH", "Philippines"),
        ("The Maldives", "iso:MV", "Maldives"),
        ("São Tomé e Príncipe", "iso:ST", "Sao Tome and Principe"),
        ("Micronesia (Federated States of)", "iso:FM", "Micronesia"),
        ("Virgin Islands, U.S.", "iso:VI", "U.S. Virgin Islands"),
        ("Macau", "iso:MO", "Macao"),
        ("Bolivia (Plurinational State of)", "iso:BO", "Bolivia"),
        ("Iran (Islamic Republic of)", "iso:IR", "Iran"),
        ("United Republic of Tanzania", "iso:TZ", "Tanzania"),
        ("Brunei Darussalam", "iso:BN", "Brunei"),
        ("Timor-Leste", "iso:TL", "East Timor"),
        ("Isle of Man", "iso:IM", "Isle of Man"),
        ("Kosovo", "x:kosovo", "Kosovo"),
        ("South Ossetia", "x:south-ossetia", "South Ossetia"),
        ("Northern Cyprus", "x:northern-cyprus", "Northern Cyprus"),
        ("European Union", "x:european-union", "European Union"),  # OSCE
        ("Zanzibar", "x:zanzibar", "Zanzibar"),
        ("Muscogee (Creek) Nation", "x:muscogee-creek-nation", "Muscogee (Creek) Nation"),
        ("Bougainville", "iso:PG-NSB", "Bougainville"),
        (
            "Scotland (part of the United Kingdom)",
            "iso:GB-SCT",
            "Scotland (part of the United Kingdom)",
        ),
        ("Punjab, India", "iso:IN-PB", "Punjab, India"),
    ],
)
def test_real_source_spellings_resolve(raw: str, place_id: str, display: str) -> None:
    place = REGISTRY.resolve(raw)
    assert place is not None and place.registered
    assert (place.place_id, place.display) == (place_id, display)


def test_display_names_are_frozen_from_feed_history() -> None:
    history = load_history(HISTORY)
    by_place: dict[str, dict[str, int]] = {}
    for raw, n in history.items():
        place = REGISTRY.resolve(raw)
        assert place is not None and place.registered, raw
        by_place.setdefault(place.place_id, {})[raw] = n
    for place_id, spellings in by_place.items():
        display = REGISTRY.get(place_id).display
        assert display in spellings, (place_id, display, spellings)
        assert spellings[display] == max(spellings.values()), (place_id, spellings)


@pytest.mark.parametrize(
    ("place_id", "display"),
    [
        ("iso:CV", "Cape Verde"),  # 43 vs Cabo Verde 2
        ("iso:KP", "North Korea"),  # 2/2 tie -> legacy canonical
        ("iso:LA", "Laos"),
        ("iso:VN", "Vietnam"),
        ("iso:PH", "Philippines"),  # 174 vs The Philippines 16
        ("iso:ST", "Sao Tome and Principe"),  # 154 vs São Tomé e Príncipe 99
    ],
)
def test_spec_display_table(place_id: str, display: str) -> None:
    assert REGISTRY.get(place_id).display == display


def test_subdivisions_have_parents() -> None:
    assert REGISTRY.get("iso:GB-SCT").parent == "iso:GB"
    assert REGISTRY.get("iso:GB-SCT").country_code == "GB"
    assert REGISTRY.get("x:somaliland").parent == "iso:SO"
    assert REGISTRY.get("x:kosovo").country_code is None


def test_uk_plus_scotland_resolves_to_the_subdivision() -> None:
    scotland = REGISTRY.resolve_subdivision("iso:GB", "Scotland")
    assert scotland is not None and scotland.place_id == "iso:GB-SCT"
    assert REGISTRY.resolve_subdivision("iso:GB", "Ontario") is None
    assert REGISTRY.resolve_subdivision("iso:CA", "Scotland") is None


def test_unregistered_part_of_names_get_a_subdivision_of_their_parent() -> None:
    place = REGISTRY.resolve("Northern Ireland (part of the United Kingdom)")
    assert place is not None and not place.registered
    assert place.place_id == "unknown:northern-ireland@iso:GB"
    assert place.parent == "iso:GB"
    assert place.display == "Northern Ireland (part of the United Kingdom)"


def test_unregistered_names_match_only_on_identical_normalised_names() -> None:
    a = REGISTRY.resolve("Republic of Artsakh")
    b = REGISTRY.resolve("  republic of  ARTSAKH ")
    c = REGISTRY.resolve("Artsakh")
    assert a is not None and b is not None and c is not None
    assert not a.registered
    assert a.place_id == b.place_id == "unknown:republic-of-artsakh"
    assert c.place_id != a.place_id


def test_unregistered_names_keep_their_distinctions() -> None:
    ids = {raw: REGISTRY.resolve(raw) for raw in (
        "O'Neill", "ONeill", "\u6771\u4eac",
        "Riverside (part of United States)", "Riverside (part of Canada)",
        "Riverside (part of Atlantis)",
    )}  # fmt: skip
    assert {raw: p.place_id for raw, p in ids.items() if p is not None} == {
        "O'Neill": "unknown:o'neill",
        "ONeill": "unknown:oneill",
        "\u6771\u4eac": "unknown:\u6771\u4eac",  # not empty, so not "missing"
        "Riverside (part of United States)": "unknown:riverside@iso:US",
        "Riverside (part of Canada)": "unknown:riverside@iso:CA",
        "Riverside (part of Atlantis)": "unknown:riverside@unknown:atlantis",
    }
    atlantis = ids["Riverside (part of Atlantis)"]
    assert atlantis is not None and atlantis.parent == "unknown:atlantis"


def test_unregistered_names_never_pose_as_registered_places(tmp_path: Path) -> None:
    posing = REGISTRY.resolve("x:somaliland")
    assert posing is not None and posing.place_id == "unknown:x-somaliland"
    registry = tmp_path / "places.yaml"
    registry.write_text(
        "unknown:atlantis: {display: Atlantis, country_code: null, parent: null, aliases: [Atlantis]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="reserved"):
        PlaceRegistry.load(registry)


@pytest.mark.parametrize("raw", ["", "   ", "\u00a0", "()", "-"])
def test_empty_country_text_resolves_to_nothing(raw: str) -> None:
    assert REGISTRY.resolve(raw) is None  # the adapter marks the unit partial: place_missing


def test_committed_places_yaml_is_up_to_date() -> None:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    expected = render(build(manual, load_history(HISTORY)))
    assert OUT.read_text(encoding="utf-8") == expected, "run python -m scripts.build_places and commit data/places.yaml"


def test_build_rejects_an_alias_shared_by_two_places() -> None:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    manual["extra_aliases"]["AT"] = ["Australia"]
    with pytest.raises(BuildError, match="names both"):
        build(manual, load_history(HISTORY))


def test_build_rejects_history_without_a_place() -> None:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    with pytest.raises(BuildError, match="matches no place"):
        build(manual, {"Atlantis": 3})


@pytest.mark.parametrize(
    ("raw", "place_id"),
    [
        ("Scotland (part of United Kingdom)", "iso:GB-SCT"),  # parent spelled without "the"
        ("Bougainville (part of Papua New Guinea)", "iso:PG-NSB"),
        ("Scotland (part of Canada)", "unknown:scotland@iso:CA"),  # not one of Canada's
    ],
)
def test_a_registered_subdivision_has_one_id_however_its_parent_is_spelled(
    raw: str, place_id: str
) -> None:
    place = REGISTRY.resolve(raw)
    assert place is not None
    assert place.place_id == place_id
    assert place.registered == (not place_id.startswith("unknown:"))


@pytest.mark.parametrize(
    ("country", "text", "expected"),
    [
        ("Pakistan", "2026 Gilgit Baltistan Assembly Election", ("Gilgit Baltistan",)),
        (
            "Bosnia and Herzegovina",
            "Republika Srpska Early Presidential election",
            ("Republika Srpska",),
        ),
        ("United Kingdom", "Scotland and Wales local elections", ("Scotland", "Wales")),
        ("United Kingdom", "Parliamentary Elections (Wales/United Kingdom)", ("Wales",)),
        ("Mexico", "Mexico General Election", ()),
        ("Trinidad and Tobago", "Trinidad and Tobago House of Representatives", ()),
        ("United Kingdom", "Scottish Parliament election", ()),
        ("Bulgaria", "Presidential Election", ()),
    ],
)
def test_named_subdivisions(country: str, text: str, expected: tuple[str, ...]) -> None:
    place = REGISTRY.resolve(country)
    assert place is not None
    assert named_subdivisions(text, place, REGISTRY, SUBDIVISIONS) == expected
