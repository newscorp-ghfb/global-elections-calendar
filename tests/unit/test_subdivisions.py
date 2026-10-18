"""First-level subdivision index (plan 2a task 2) against the committed data/subdivisions.yaml."""

import pytest
import yaml

from elections_calendar.places import SubdivisionIndex
from scripts.build_subdivisions import (
    MANUAL,
    OUT,
    BuildError,
    _keys,
    build,
    first_level_rows,
    render,
)

SUBDIVISIONS = SubdivisionIndex.load()


def test_subdivisions_resolve_names_sources_use() -> None:
    cases = {
        ("US", "Georgia"): "US-GA", ("US", "Texas"): "US-TX",
        ("BR", "Federal District"): "BR-DF", ("BR", "São Paulo"): "BR-SP",
        ("DE", "Lower Saxony"): "DE-NI", ("CH", "Bern"): "CH-BE",
        ("ES", "Madrid"): "ES-MD", ("CZ", "Praha"): "CZ-10",
        ("JP", "Okinawa Prefecture"): "JP-47", ("NG", "Oyo State"): "NG-OY",
        ("PE", "Lima"): "PE-LIM", ("CA", "Ontario"): "CA-ON",
        ("AU", "Northern Territory"): "AU-NT", ("US", "District of Columbia"): "US-DC",
    }  # fmt: skip
    assert {k: SUBDIVISIONS.find(*k) for k in cases} == cases


@pytest.mark.parametrize(
    ("country", "name", "code"),
    [("ZA", "Gauteng Province", "ZA-GP"), ("PE", "Cusco Region", "PE-CUS")],
)
def test_a_province_or_region_suffix_is_dropped(country: str, name: str, code: str) -> None:
    assert SUBDIVISIONS.find(country, name) == code
    assert SUBDIVISIONS.find(country, name.rsplit(" ", 1)[0]) == code  # the bare name is a key


def test_subdivision_lookups_that_must_miss() -> None:
    assert SUBDIVISIONS.find("GE", "Georgia") is None  # the country has no such subdivision
    assert SUBDIVISIONS.find(None, "Texas") is None
    assert SUBDIVISIONS.find("US", "") is None
    assert SUBDIVISIONS.find("US", "Scarborough Southwest") is None
    assert SUBDIVISIONS.find("BG", "Sofia") is None  # ambiguous: BG-22 and BG-23
    assert SUBDIVISIONS.find("PH", "Bangsamoro") is None


def test_build_leaves_out_names_two_subdivisions_share() -> None:
    index, ambiguous = build(
        [("XA-1", "XA", "Alpha"), ("XA-2", "XA", "Alpha (city)"), ("XA-3", "XA", "Beta, Region of")],
        {"XA": {"Gamma": "XA-3"}},
    )
    assert index == {"XA": {"beta": "XA-3", "beta region of": "XA-3", "gamma": "XA-3"}}
    assert ambiguous == ["XA alpha"]


def test_build_rejects_an_unknown_manual_code() -> None:
    rows = [("XA-1", "XA", "Alpha")]
    with pytest.raises(BuildError):
        build(rows, {"XA": {"Delta": "XA-9"}})
    with pytest.raises(BuildError):
        build(rows + [("XB-1", "XB", "Beta")], {"XA": {"Delta": "XB-1"}})


def test_build_rejects_two_manual_names_that_normalise_to_one_key() -> None:
    rows = [("XA-1", "XA", "Alpha"), ("XA-2", "XA", "Beta")]
    for names in ({"Gamma": "XA-1", "GAMMA": "XA-2"}, {"São": "XA-1", "Sao": "XA-1"}):
        with pytest.raises(BuildError, match="manual names"):
            build(rows, {"XA": names})
    index, _ = build(rows, {"XA": {"Gamma": "XA-1"}, "XB": {}})  # one name is fine
    assert index["XA"]["gamma"] == "XA-1"


def test_committed_subdivisions_yaml_is_up_to_date() -> None:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    expected = render(*build(first_level_rows(), manual))
    assert OUT.read_text(encoding="utf-8") == expected, "run python -m scripts.build_subdivisions and commit data/subdivisions.yaml"


def test_keys_strip_a_trailing_bracket() -> None:  # P45
    assert _keys("Wales [Cymru GB-CYM]") == {"wales"}
    assert _keys("Blekinge län [SE-10]") == {"blekinge lan"}
    assert _keys("Madrid, Comunidad de") == {"madrid comunidad de", "madrid"}
    assert SUBDIVISIONS.find("GB", "Wales") == "GB-WLS"
    assert SUBDIVISIONS.find("SE", "Skåne län") == "SE-M"
