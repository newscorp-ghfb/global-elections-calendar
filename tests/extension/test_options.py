"""The options page: places the feed lists, pins edited through the worker (Plan 5b-2 Task 2; P141, D4, R55)."""

import json
import time
from collections.abc import Sequence
from typing import Any, Final

import pytest
from playwright.sync_api import Page, expect

from tests.support.extension import (
    ROOT,
    Ext,
    artifact_pair,
    feed_record,
    release_pin_read,
    release_pin_reply,
    status_record,
    v1_feed,
    wrap_pin_messages,
    wrap_pin_reads,
)

PLACES: Final = "pinned_places_v2"
UNRESOLVED: Final = "unresolved_pins_v2"
MIGRATED: Final = "pins_migrated_v2"
FEED: Final = "elections_cache_v2"
STATUS: Final = "status_cache"
CHECK: Final = "check_state_v2"
TABLE: Final[dict[str, Any]] = json.loads(
    (ROOT / "extension" / "places.json").read_text(encoding="utf-8")
)
NO_DATA: Final = "No election data is available yet. Open the popup to load it, then come back here."
IDLE: Final = "() => document.body.dataset.pinSync === 'idle'"


@pytest.fixture(scope="module")
def pair() -> tuple[bytes, bytes]:
    return artifact_pair()


def _cached(pair: tuple[bytes, bytes]) -> dict[str, Any]:
    feed, status = pair
    return {
        FEED: feed_record(feed),
        STATUS: status_record(status),
        CHECK: {"ok_at": int(time.time() * 1000), "failed_at": None, "error": None},
    }


def _pins(places: Sequence[str] = (), unresolved: Sequence[str] = ()) -> dict[str, Any]:
    return {MIGRATED: True, PLACES: list(places), UNRESOLVED: list(unresolved)}


def _open(ext: Ext) -> Page:
    page = ext.open("options.html")
    page.wait_for_function(IDLE)
    return page


def _row(page: Page, place_id: str) -> Any:
    return page.locator(f'.country-item[data-place-id="{place_id}"]')


def _button(page: Page, place_id: str) -> Any:
    return _row(page, place_id).locator(".pin-btn")


def _ids(page: Page) -> list[str]:
    ids: list[str] = page.eval_on_selector_all(
        ".country-item", "els => els.map(e => e.dataset.placeId)"
    )
    return ids


def _status(page: Page) -> str:
    return page.locator("#pinStatus").text_content() or ""


def _stored_places(ext: Ext) -> list[str]:
    places: list[str] = ext.storage().get(PLACES, [])
    return places


def _wait_places(page: Page, places: list[str]) -> None:
    page.wait_for_function(
        """want => chrome.storage.local.get('pinned_places_v2').then(
          s => JSON.stringify(s.pinned_places_v2) === JSON.stringify(want))""",
        arg=places,
    )


def _shows(page: Page, pinned: list[str], unpinned: list[str], timeout: int = 5000) -> None:
    for place_id in pinned:
        expect(_button(page, place_id)).to_have_attribute("aria-pressed", "true", timeout=timeout)
    for place_id in unpinned:
        expect(_button(page, place_id)).to_have_attribute("aria-pressed", "false", timeout=timeout)


def test_options_lists_feed_places_and_pins(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair

    # (a) fresh: no cache, the pair routed; 58 card places and 15 listing-only places
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    page = _open(ext)
    assert len(_ids(page)) == 73
    assert page.locator('.country-item[data-place-id="iso:LS"] .country-name').text_content() == "Lesotho"
    assert page.locator("#unresolvedSection").is_hidden()
    assert page.locator("#noData").is_hidden()
    assert page.locator("#pinSummary").text_content() == "No countries pinned — popup shows all results."
    assert ext.page_errors == []
    ext.reset()

    # (b) after an upgrade: v1's cache is still there, the v2 record is what is listed
    v1 = json.loads(v1_feed())
    v1_ids = {
        TABLE["names"][e["country"]]
        for month in v1["months"].values()
        for e in month
        if e["country"] in TABLE["names"]
    }
    ext.seed({"elections_cache": {"ts": 1, "data": v1}, **_cached(pair)})
    page = _open(ext)
    ids = _ids(page)
    assert len(ids) == 73 and "iso:LS" in ids
    only_v1 = v1_ids - set(ids)
    assert only_v1 >= {"iso:BD", "iso:CO", "iso:ZM"}
    assert ext.page_errors == []
    ext.reset()

    # (c) an invalid v2 cache and no route: no data
    ext.seed({FEED: "garbage"})
    page = _open(ext)
    assert page.locator("#noData").text_content() == NO_DATA
    assert _ids(page) == []
    assert ext.page_errors == []
    ext.reset()

    # (c2) the same with saved pins: the text sits above a list of the saved pins
    ext.seed({FEED: "garbage", **_pins(["iso:CV"], ["Atlantis"])})
    page = _open(ext)
    assert page.locator("#noData").text_content() == NO_DATA
    assert _ids(page) == ["iso:CV"]
    expect(_button(page, "iso:CV")).to_have_attribute("aria-pressed", "true")
    assert ext.page_errors == []
    assert page.locator("#unresolvedList li").all_text_contents() == ["AtlantisRemove"]
    _button(page, "iso:CV").click()
    page.wait_for_function(IDLE)
    assert _stored_places(ext) == []
    assert ext.page_errors == []
    ext.reset()

    # (d) pins kept: pinned rows first, a pinned place the feed lacks from the table's display
    ext.seed({**_cached(pair), **_pins(["iso:CV", "iso:IS"], ["Atlantis"])})
    page = _open(ext)
    ids = _ids(page)
    assert ids[:2] == ["iso:CV", "iso:IS"] and len(ids) == 74
    assert page.locator(".country-item .country-name").nth(1).text_content() == "Iceland"
    assert page.locator("#unresolvedList .unresolved-name").all_text_contents() == ["Atlantis"]
    assert page.locator("#pinSummary").text_content() == "2 countries pinned — popup shows only these."
    assert ext.page_errors == []
    ext.reset()

    # (e) D4: no checkboxes, no Save, and the selection key is left alone
    ext.seed({**_cached(pair), "selected_countries": ["Brazil"]})
    page = _open(ext)
    assert page.locator("input[type=checkbox]").count() == 0
    assert page.locator("#save-btn").count() == 0
    assert ext.storage()["selected_countries"] == ["Brazil"]

    # (f) the worker unreachable: the pins cannot be prepared
    assert ext.page_errors == []
    ext.reset()
    ext.seed(_cached(pair))
    broken = ext.open(
        "options.html",
        init_script="chrome.runtime.sendMessage = () => Promise.reject(new Error('down'));",
    )
    broken.wait_for_function(IDLE)
    assert broken.locator("#pinsFailed").text_content() == (
        "Your pins could not be prepared: down. Reload this page to try again."
    )
    assert broken.locator(".pin-btn").count() == 0
    assert ext.page_errors == []


def test_options_pins_and_unpins(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    ext.seed({**_cached(pair), **_pins([], ["Atlantis"]), "pinned_countries": ["Brazil"]})
    page = _open(ext)
    _button(page, "iso:LS").click()
    page.wait_for_function(IDLE)
    assert _stored_places(ext) == ["iso:LS"]
    assert page.locator("#pinSummary").text_content() == "1 country pinned — popup shows only these."
    assert _ids(page)[0] == "iso:LS"
    _button(page, "iso:LS").click()
    page.wait_for_function(IDLE)
    assert _stored_places(ext) == []

    page.get_by_role("button", name="Remove Atlantis").click()
    page.wait_for_function(IDLE)
    assert ext.storage()[UNRESOLVED] == []
    assert page.locator("#unresolvedSection").is_hidden()

    transnistria = TABLE["places"]["x:transnistria"]["display"]
    somaliland = TABLE["places"]["x:somaliland"]["display"]
    assert _row(page, "iso:MD").locator(".also-shows").text_content() == f"Also shows: {transnistria}"
    assert _row(page, "iso:SO").locator(".also-shows").text_content() == f"Also shows: {somaliland}"
    assert ext.storage()["pinned_countries"] == ["Brazil"]
    assert ext.page_errors == []


def test_options_text_is_inserted_as_text(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    payload = "<img src=x onerror=alert(1)>"
    doc = json.loads(pair[0])
    doc["months"]["2026-10"][0]["place_id"] = "x:evil"
    doc["months"]["2026-10"][0]["country"] = payload
    raw = json.dumps(doc, separators=(",", ":")).encode()
    ext.seed({FEED: feed_record(raw), CHECK: {"ok_at": int(time.time() * 1000), "failed_at": None, "error": None}})
    page = _open(ext)
    assert _row(page, "x:evil").locator(".country-name").text_content() == payload
    assert page.locator("img").count() == 0
    assert ext.page_errors == []


def test_two_options_pages_edit_pins(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    ext.seed({**_cached(pair), **_pins(["iso:CV", "iso:MD"])})
    a = _open(ext)
    b = _open(ext)
    _button(a, "iso:CV").click()
    _button(b, "iso:LS").click()
    _wait_places(a, ["iso:MD", "iso:LS"])
    for page in (a, b):
        _shows(page, ["iso:MD", "iso:LS"], ["iso:CV"], timeout=2000)
    # B learns of an edit it did not make only through storage.onChanged
    _button(a, "iso:LS").click()
    _wait_places(a, ["iso:MD"])
    _shows(b, ["iso:MD"], ["iso:LS", "iso:CV"], timeout=2000)
    assert ext.page_errors == []


def test_a_rejected_pin_save_is_reported(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    ext.seed({**_cached(pair), **_pins(["iso:CV"])})
    page = _open(ext)
    worker = ext.worker()
    worker.evaluate(
        """() => {
          globalThis.__realSet = chrome.storage.local.set.bind(chrome.storage.local);
          let armed = true;
          chrome.storage.local.set = async (...args) => {
            if (armed) { armed = false; throw new Error('quota'); }
            return globalThis.__realSet(...args);
          };
        }"""
    )
    try:
        _button(page, "iso:LS").click()
        page.wait_for_function(IDLE)
        assert _status(page) == (
            "Your change could not be saved: could not save the pins: quota. Try again."
        )
        button = _button(page, "iso:LS")
        expect(button).to_have_attribute("aria-pressed", "false")
        expect(button).to_be_enabled()
        assert _stored_places(ext) == ["iso:CV"]
        button.click()
        page.wait_for_function(IDLE)
        expect(button).to_have_attribute("aria-pressed", "true")
        assert _stored_places(ext) == ["iso:CV", "iso:LS"]
        assert _status(page) == ""
        assert ext.page_errors == []
    finally:
        worker.evaluate("() => { chrome.storage.local.set = globalThis.__realSet; }")


def test_a_late_pin_reply_never_repaints_an_older_state(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    ext.seed({**_cached(pair), **_pins(["iso:CV", "iso:MD"])})
    a = _open(ext)
    b = _open(ext)

    # a late reply: A's reply is held until B's edit is stored and shown
    wrap_pin_messages(a, "hold")
    _button(a, "iso:CV").click()
    _wait_places(a, ["iso:MD"])
    # A has redrawn from storage (CV is unpinned), and the redraw kept CV's pending state
    expect(_button(a, "iso:CV")).to_have_attribute("aria-pressed", "false")
    expect(_button(a, "iso:CV")).to_have_attribute("aria-busy", "true")
    _button(b, "iso:LS").click()
    _wait_places(b, ["iso:MD", "iso:LS"])
    expect(_button(a, "iso:LS")).to_have_attribute("aria-pressed", "true")
    expect(_button(a, "iso:CV")).to_have_attribute("aria-busy", "true")
    release_pin_reply(a)
    a.wait_for_function(IDLE)
    for page in (a, b):
        _shows(page, ["iso:MD", "iso:LS"], ["iso:CV"])
    expect(_button(a, "iso:CV")).to_be_enabled()
    assert _button(a, "iso:CV").get_attribute("aria-busy") is None
    assert _status(a) == ""

    # an older read: held while A's other reconcile and then B's edit are drawn
    b.wait_for_function(IDLE)
    wrap_pin_reads(a, "hold-next")
    _button(a, "iso:MD").click()
    a.wait_for_function(
        "() => window.__pinReadHeld && JSON.stringify(window.__pinReadHeld.pinned_places_v2)"
        " === JSON.stringify(['iso:LS'])"
    )
    expect(_button(a, "iso:MD")).to_have_attribute("aria-pressed", "false")
    _button(b, "iso:CV").click()
    _wait_places(b, ["iso:LS", "iso:CV"])
    expect(_button(a, "iso:CV")).to_have_attribute("aria-pressed", "true")
    release_pin_read(a)
    a.wait_for_function(IDLE)
    _shows(a, ["iso:LS", "iso:CV"], ["iso:MD"])
    assert ext.page_errors == []


def test_a_lost_pin_reply_is_reconciled(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    ext.seed({**_cached(pair), **_pins(["iso:CV", "iso:MD"])})
    page = _open(ext)

    # lost before the save
    wrap_pin_messages(page, "reject-before")
    _button(page, "iso:CV").click()
    page.wait_for_function(IDLE)
    assert _status(page) == (
        "Your change could not be confirmed: Could not establish connection. Receiving end"
        " does not exist. The list shows your saved pins."
    )
    expect(_button(page, "iso:CV")).to_have_attribute("aria-pressed", "true")
    assert ext.page_errors == []
    expect(_button(page, "iso:CV")).to_be_enabled()
    assert _button(page, "iso:CV").get_attribute("aria-busy") is None
    assert _stored_places(ext) == ["iso:CV", "iso:MD"]
    _button(page, "iso:CV").click()
    page.wait_for_function(IDLE)
    assert _stored_places(ext) == ["iso:MD"]
    assert _status(page) == ""

    # lost after the save
    wrap_pin_messages(page, "reject-after")
    _button(page, "iso:LS").click()
    page.wait_for_function(IDLE)
    assert _status(page) == (
        "Your change could not be confirmed: The message port closed before a response was"
        " received. The list shows your saved pins."
    )
    expect(_button(page, "iso:LS")).to_have_attribute("aria-pressed", "true")
    expect(_button(page, "iso:LS")).to_be_enabled()
    assert _stored_places(ext) == ["iso:MD", "iso:LS"]
    _button(page, "iso:MD").click()
    page.wait_for_function(IDLE)
    assert _stored_places(ext) == ["iso:LS"]
    assert _status(page) == ""

    # no usable reply
    wrap_pin_messages(page, "no-reply")
    _button(page, "iso:MD").click()
    page.wait_for_function(IDLE)
    assert _status(page) == (
        "Your change could not be confirmed: no usable reply. The list shows your saved pins."
    )
    expect(_button(page, "iso:MD")).to_have_attribute("aria-pressed", "false")
    expect(_button(page, "iso:MD")).to_be_enabled()
    assert _stored_places(ext) == ["iso:LS"]

    # a failed read
    wrap_pin_reads(page, "fail")
    _button(page, "iso:CV").click()
    page.wait_for_function(IDLE)
    assert _stored_places(ext) == ["iso:LS", "iso:CV"]
    assert _status(page) == "Your saved pins could not be read: boom. Reload this page to try again."
    expect(_button(page, "iso:CV")).to_be_enabled()
    # a later good read clears the read-failure text and shows the pins from outside the page
    wrap_pin_reads(page, "ok")
    ext.seed(_pins(["iso:LS", "iso:CV", "iso:MD"]))
    # the draw and the clearing run in one synchronous step: once MD is pressed the status is final
    expect(_button(page, "iso:MD")).to_have_attribute("aria-pressed", "true")
    page.wait_for_function(IDLE)
    assert _status(page) == ""
    page.reload()
    page.wait_for_function(IDLE)
    expect(_button(page, "iso:CV")).to_have_attribute("aria-pressed", "true")
    assert ext.page_errors == []


def test_messages_in_sentences_lose_one_trailing_full_stop(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    # Chrome's own messages end in a full stop; the sentence supplies its own (no "..")
    ext.seed(_cached(pair))
    broken = ext.open(
        "options.html",
        init_script=(
            "chrome.runtime.sendMessage = () => Promise.reject("
            "new Error('Could not establish connection. Receiving end does not exist.'));"
        ),
    )
    broken.wait_for_function(IDLE)
    assert broken.locator("#pinsFailed").text_content() == (
        "Your pins could not be prepared: Could not establish connection. Receiving end does"
        " not exist. Reload this page to try again."
    )
    ext.seed(_pins())
    page = _open(ext)
    page.evaluate(
        """() => {
          const real = chrome.storage.local.get.bind(chrome.storage.local);
          chrome.storage.local.get = (keys, ...rest) => Array.isArray(keys) && keys.includes('pinned_places_v2')
            ? Promise.reject(new Error('Storage is broken.')) : real(keys, ...rest);
        }"""
    )
    _button(page, "iso:LS").click()
    page.wait_for_function(IDLE)
    assert _status(page) == "Your saved pins could not be read: Storage is broken. Reload this page to try again."
    assert ext.page_errors == []


def test_the_options_page_respects_the_check_throttle(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    # a recent successful check, but no valid record: the page asks without `force`, so the
    # worker's due() throttle still applies and nothing is fetched
    feed, status = pair
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    ext.seed({FEED: "garbage", CHECK: {"ok_at": int(time.time() * 1000), "failed_at": None, "error": None}})
    page = _open(ext)
    assert page.locator("#noData").text_content() == NO_DATA
    assert ext.served.log == []
    assert ext.page_errors == []


def test_the_pins_are_listed_before_a_slow_check(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    # R64, P152: no cached feed, and the check's request is held; the pins do not wait for it
    feed, status = pair
    ext.seed(_pins(["iso:LS", "iso:BR"]))
    ext.served.set("elections.json", "hold")
    ext.served.set("status.json", status)
    page = ext.open("options.html")  # not waited for: the page stays busy while the request is held
    expect(_button(page, "iso:LS")).to_be_enabled(timeout=3000)
    expect(_button(page, "iso:BR")).to_be_enabled(timeout=3000)
    _shows(page, ["iso:LS", "iso:BR"], [], timeout=3000)
    assert set(_ids(page)) == {"iso:LS", "iso:BR"}
    for _ in range(100):  # the worker's fetch may trail the pins: wait for it, bounded
        if "elections.json" in ext.served.log:
            break
        page.wait_for_timeout(50)
    else:
        raise AssertionError("the check never asked for elections.json")
    _button(page, "iso:BR").wait_for()  # the request is still held: the pins are listed and editable
    expect(_button(page, "iso:LS")).to_be_enabled()
    _button(page, "iso:LS").click()
    _wait_places(page, ["iso:BR"])
    assert _stored_places(ext) == ["iso:BR"]
    ext.served.release("elections.json", feed)
    page.wait_for_function(IDLE)
    assert len(_ids(page)) == 73
    assert page.locator("#noData").is_hidden()
    _shows(page, ["iso:BR"], ["iso:LS"])
    assert ext.page_errors == []


def test_a_failed_check_leaves_the_pins_editable(ext: Ext) -> None:
    # Review Focus 3: the check fails; the pins stay listed and editable, "no data" is shown
    ext.seed(_pins(["iso:LS", "iso:BR"]))
    ext.served.set("elections.json", 500)
    ext.served.set("status.json", 500)
    page = _open(ext)
    assert set(_ids(page)) == {"iso:LS", "iso:BR"}
    expect(_button(page, "iso:LS")).to_be_enabled()
    assert page.locator("#noData").text_content() == NO_DATA
    assert page.locator("#noData").is_visible()
    _button(page, "iso:LS").click()
    page.wait_for_function(IDLE)
    assert _stored_places(ext) == ["iso:BR"]
    assert ext.page_errors == []
