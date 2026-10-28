"""The extension's place table, extension/places.json (Plan 5b-2 Task 2; D3, P140)."""

import json
from typing import Any

from elections_calendar.places import PlaceRegistry
from scripts.build_extension_places import OUT, ROOT, build


def _history() -> list[str]:
    lines = (ROOT / "data" / "feed_country_history.tsv").read_text(encoding="utf-8").splitlines()
    return [
        line.split("\t")[0]
        for line in lines
        if line and not line.startswith("#") and not line.startswith("country\t")
    ]


def test_places_table_matches_the_registry() -> None:
    built = build()
    assert built == OUT.read_bytes(), "extension/places.json is stale: run scripts.build_extension_places"
    table: dict[str, Any] = json.loads(built)
    registry = PlaceRegistry.load()
    names: dict[str, str] = table["names"]
    places: dict[str, dict[str, Any]] = table["places"]

    assert len(places) == 264
    assert len(names) == 487
    for name, place_id in names.items():
        found = registry.resolve(name)
        assert found is not None and found.place_id == place_id, name
    for place_id, entry in places.items():
        place = registry.get(place_id)
        assert entry == {"display": place.display, "parent": place.parent}, place_id
    assert all(place_id in places for place_id in names.values())
    history = _history()
    assert len(history) == 90
    assert [s for s in history if s not in names] == []
    assert b"\\u" not in built and built.endswith(b"}\n")
