"""lib/pins.js: pins as places, the one-time migration, the parent rule, the edit queue (Plan 5b-2 Task 2; P140)."""

import json
import time
from typing import Any, Final

from playwright.sync_api import Page

from elections_calendar.places import PlaceRegistry
from tests.support.extension import (
    ROOT,
    Ext,
    artifact_pair,
    feed_record,
    js,
    run_pin_edits,
    run_pins,
    status_record,
    v1_feed,
)

LEGACY: Final = "pinned_countries"
PLACES: Final = "pinned_places_v2"
UNRESOLVED: Final = "unresolved_pins_v2"
MIGRATED: Final = "pins_migrated_v2"
FEED: Final = "elections_cache_v2"
STATUS: Final = "status_cache"
CHECK: Final = "check_state_v2"
TABLE: Final[dict[str, Any]] = json.loads(
    (ROOT / "extension" / "places.json").read_text(encoding="utf-8")
)
SEED: Final = [
    "Cabo Verde",
    "Scotland (part of the United Kingdom)",
    "Atlantis",
    "Cape Verde",
    7,
    "constructor",
]


def _history() -> list[str]:
    lines = (ROOT / "data" / "feed_country_history.tsv").read_text(encoding="utf-8").splitlines()
    return [
        line.split("\t")[0]
        for line in lines
        if line and not line.startswith("#") and not line.startswith("country\t")
    ]


def _matches(lab: Page, pins: list[str], ids: list[str | None]) -> list[bool]:
    got: list[bool] = lab.evaluate(
        """async ([pins, ids, table]) => {
          const { pinMatcher } = await import('/lib/pins.js');
          const matches = pinMatcher(pins, table);
          return ids.map((id) => matches(id));
        }""",
        [pins, ids, TABLE],
    )
    return got


def test_every_v1_pin_string_migrates(lab: Page) -> None:
    strings = _history()
    assert len(strings) == 90
    got = js(lab, "lib/pins.js", "migration", {LEGACY: strings}, TABLE)
    registry = PlaceRegistry.load()
    want: list[str] = []
    for name in strings:
        place = registry.resolve(name)
        assert place is not None, name
        if place.place_id not in want:
            want.append(place.place_id)
    assert len(want) == 84
    assert got == {"places": want, "unresolved": []}


def test_pin_migration(lab: Page) -> None:
    first = run_pins(lab, stored={LEGACY: SEED})
    assert first["result"] == {"ok": True, "migrated": True}
    assert first["stored"][PLACES] == ["iso:CV", "iso:GB-SCT"]
    assert first["stored"][UNRESOLVED] == ["Atlantis", "constructor"]
    assert first["stored"][MIGRATED] is True
    assert first["stored"][LEGACY] == SEED
    assert first["sets"] == [[PLACES, UNRESOLVED], [MIGRATED]]

    again = run_pins(lab, stored=first["stored"])
    assert again["result"] == {"ok": True, "migrated": False}
    assert again["sets"] == []

    bad = run_pins(lab, stored={LEGACY: SEED}, verify_mismatch=True)
    assert bad["result"] == {"ok": False, "error": "the migrated pins could not be verified"}
    assert MIGRATED not in bad["stored"]

    cannot_read = run_pins(lab, stored={LEGACY: SEED}, get_fails="boom")
    assert cannot_read["result"] == {"ok": False, "error": "the pins could not be migrated: boom"}
    cannot_save = run_pins(lab, stored={LEGACY: SEED}, set_fails="quota")
    assert cannot_save["result"] == {"ok": False, "error": "the pins could not be migrated: quota"}
    assert MIGRATED not in cannot_save["stored"]

    deleted = {**first["stored"], PLACES: ["iso:GB-SCT"]}
    kept = run_pins(lab, stored=deleted)
    assert kept["stored"][PLACES] == ["iso:GB-SCT"] and kept["sets"] == []

    rolled_back = {**first["stored"], LEGACY: [*SEED, "Brazil"]}
    ignored = run_pins(lab, stored=rolled_back)
    assert ignored["stored"][PLACES] == ["iso:CV", "iso:GB-SCT"] and ignored["sets"] == []

    not_a_list = run_pins(lab, stored={LEGACY: "Brazil"})
    assert not_a_list["stored"][PLACES] == [] and not_a_list["stored"][UNRESOLVED] == []
    assert not_a_list["stored"][MIGRATED] is True


def test_a_parent_pin_includes_its_places(lab: Page) -> None:
    geo = _matches(lab, ["iso:GE"], ["x:south-ossetia", "x:abkhazia", "iso:GE", "iso:RU", None])
    assert geo == [True, True, True, False, False]
    sub = _matches(lab, ["x:south-ossetia"], ["iso:GE", "x:abkhazia", "x:south-ossetia"])
    assert sub == [False, False, True]
    assert _matches(lab, ["iso:ZZ"], ["iso:ZZ", "iso:GE", "x:abkhazia"]) == [True, False, False]
    assert _matches(lab, [], ["iso:GE", None]) == [True, True]

    feed, _ = artifact_pair()
    doc = json.loads(feed)
    view_js = """async ([doc, month, pinned, table]) => {
      const { view } = await import('/lib/count.js');
      const { pinMatcher } = await import('/lib/pins.js');
      const v = view(doc, { month, tab: 'all', level: 'all', query: '', today: '2026-10-19',
        now: 0, pins: pinMatcher(pinned, table) });
      return v.cards.map((c) => c.card.place_id);
    }"""

    def shown(month: str, pinned: list[str]) -> list[str]:
        got: list[str] = lab.evaluate(view_js, [doc, month, pinned, TABLE])
        return got

    assert shown("2026-09", ["iso:GE"]) == ["x:south-ossetia"]
    assert shown("2026-11", ["iso:MD"]) == ["iso:MD"]
    assert shown("2026-12", ["iso:MD"]) == ["x:transnistria"]
    assert len(shown("2026-11", [])) == 28


def _popup_cards(page: Page) -> list[str]:
    return [t or "" for t in page.locator(".election-item .election-country").all_text_contents()]


def test_pins_survive_and_filter_the_popup(ext: Ext) -> None:
    feed, status = artifact_pair()
    now_ms = int(time.time() * 1000)
    ext.seed(
        {
            LEGACY: ["Cabo Verde", "Moldova"],
            FEED: feed_record(feed),
            STATUS: status_record(status),
            CHECK: {"ok_at": now_ms, "failed_at": None, "error": None},
        }
    )
    page = ext.popup()
    page.click("#nextMonthBtn")
    assert page.locator("#currentMonthLabel").text_content() == "NOVEMBER 2026"
    assert sorted(_popup_cards(page)) == ["Cape Verde", "Moldova"]
    assert page.locator("#pinBarText").text_content() == "Pinned view · 2 countries"
    stored = ext.storage()
    assert PLACES not in stored and MIGRATED not in stored and UNRESOLVED not in stored

    options = ext.open("options.html")
    options.wait_for_function("() => document.body.dataset.pinSync === 'idle'")
    stored = ext.storage()
    assert stored[PLACES] == ["iso:CV", "iso:MD"]
    assert stored[MIGRATED] is True
    assert stored[LEGACY] == ["Cabo Verde", "Moldova"]

    # the legacy renderer, with the v1 feed and the same pins: November's Moldova cards only
    ext.seed({FEED: feed_record(v1_feed(), fmt="legacy")})
    legacy = ext.popup()
    legacy.click("#nextMonthBtn")
    assert legacy.locator("#currentMonthLabel").text_content() == "NOVEMBER 2026"
    assert _popup_cards(legacy) == ["Moldova"]
    assert legacy.locator("#pinBarText").text_content() == "Pinned view · 2 countries"
    assert ext.page_errors == []


_EDIT_STORED: Final = {
    MIGRATED: True,
    PLACES: ["iso:CV", "iso:MD"],
    UNRESOLVED: [],
    LEGACY: ["Brazil"],
}


def _pin(value: str) -> dict[str, str]:
    return {"op": "pin", "value": value}


def _unpin(value: str) -> dict[str, str]:
    return {"op": "unpin", "value": value}


def test_pin_edits_are_applied_in_order(lab: Page) -> None:
    def run(edits: list[dict[str, str]], **kw: Any) -> dict[str, Any]:
        ran = run_pin_edits(lab, stored=_EDIT_STORED, edits=edits, **kw)
        assert all(LEGACY not in keys for keys in ran["sets"])
        assert ran["stored"][LEGACY] == ["Brazil"]
        return ran

    overlapping = run([_unpin("iso:CV"), _pin("iso:LS")])
    assert overlapping["stored"][PLACES] == ["iso:MD", "iso:LS"]
    assert [r["pins"]["places"] for r in overlapping["replies"]] == [
        ["iso:MD"],
        ["iso:MD", "iso:LS"],
    ]

    rapid = run([_pin("iso:LS"), _unpin("iso:LS"), _pin("iso:LS")])
    assert rapid["stored"][PLACES] == ["iso:CV", "iso:MD", "iso:LS"]

    same = run([_unpin("iso:CV"), _pin("iso:CV")])
    assert same["stored"][PLACES] == ["iso:MD", "iso:CV"]

    idempotent = run([_pin("iso:CV")])
    assert idempotent["sets"] == [] and idempotent["replies"][0]["ok"] is True
    assert idempotent["stored"][PLACES] == ["iso:CV", "iso:MD"]

    retried = run([_pin("iso:LS"), _pin("iso:LS")], set_fails=(0,))
    assert retried["replies"][0] == {"ok": False, "error": "could not save the pins: quota"}
    assert retried["replies"][1]["ok"] is True
    assert retried["stored"][PLACES] == ["iso:CV", "iso:MD", "iso:LS"]

    forgotten = run_pin_edits(
        lab,
        stored={**_EDIT_STORED, UNRESOLVED: ["Atlantis"]},
        edits=[{"op": "forget", "value": "Atlantis"}],
    )
    assert forgotten["stored"][UNRESOLVED] == []
    assert forgotten["replies"][0]["pins"] == {"places": ["iso:CV", "iso:MD"], "unresolved": []}

    bad = run_pin_edits(lab, stored=_EDIT_STORED, edits=[{"op": "pin", "value": 7}])
    assert bad["replies"] == [{"ok": False, "error": "not a pin"}]
    assert bad["sets"] == []
