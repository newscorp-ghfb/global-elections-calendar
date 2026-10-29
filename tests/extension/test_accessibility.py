"""Keyboard, ARIA and focus (Plan 5b-2 Task 6; P146, S5-T19). Automated role, state, keyboard and
focus checks; no screen reader is run."""

import json
import time
from datetime import UTC, datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from elections_calendar.model import SOURCE_NAMES
from tests.support.extension import (
    Ext,
    artifact_pair,
    feed_record,
    fresh_v1_feed,
    release_pin_reply,
    republication,
    status_record,
    wrap_pin_messages,
)

FEED: Final = "elections_cache_v2"
STATUS: Final = "status_cache"
CHECK: Final = "check_state_v2"
BRAZIL_CARD: Final = "c8c9844ab7a8"
BRAZIL_FIRST_CHILD: Final = "2b844b3ca773"
SWEDEN_CARD: Final = "fcd48da30f32"
SWEDEN_CHILD: Final = "451e4f4c0054"
IDLE: Final = "() => document.body.dataset.pinSync === 'idle'"


@pytest.fixture(scope="module")
def pair() -> tuple[bytes, bytes]:
    return artifact_pair()


def _fresh_check() -> dict[str, Any]:
    return {"ok_at": int(time.time() * 1000), "failed_at": None, "error": None}


def _seeded(ext: Ext, pair: tuple[bytes, bytes]) -> Page:
    feed, status = pair
    ext.seed({FEED: feed_record(feed), STATUS: status_record(status), CHECK: _fresh_check()})
    return ext.popup()


def _active(page: Page) -> str:
    out: str = page.evaluate("() => document.activeElement.id || document.activeElement.tagName")
    return out


def _tab_state(page: Page) -> dict[str, tuple[str | None, str | None]]:
    return {
        name: (
            page.locator(f"#tab{name}").get_attribute("aria-selected"),
            page.locator(f"#tab{name}").get_attribute("tabindex"),
        )
        for name in ("Upcoming", "Past", "All")
    }


def _expanded(page: Page, selector: str, value: bool) -> bool:
    found = page.locator(selector).and_(page.get_by_role("button", expanded=value))
    return found.count() == 1


def _by_keyboard(page: Page, selector: str) -> None:
    """Keyboard focus on `selector`: focus it, step away with Shift+Tab, and Tab back onto it."""
    page.locator(selector).first.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    assert page.evaluate("s => document.activeElement === document.querySelector(s)", selector), selector


def _ring(page: Page) -> tuple[str, str]:
    got: list[str] = page.evaluate(
        "() => { const c = getComputedStyle(document.activeElement); return [c.outlineStyle, c.outlineWidth]; }"
    )
    return got[0], got[1]


def _list_text(page: Page) -> list[str]:
    return page.locator("#electionList > li").all_text_contents()


def test_keyboard_and_aria_semantics(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed_doc: dict[str, Any] = json.loads(pair[0])
    page = _seeded(ext, pair)

    # the tablist, its tabs and their roving tabindex
    tablist = page.get_by_role("tablist", name="Show")
    assert [t.strip() for t in tablist.get_by_role("tab").all_text_contents()] == ["Upcoming", "Past", "All"]
    assert _tab_state(page) == {"Upcoming": ("false", "-1"), "Past": ("false", "-1"), "All": ("true", "0")}
    assert page.locator("#listPanel").get_attribute("aria-labelledby") == "tabAll"
    assert page.locator("#tabAll").get_attribute("aria-controls") == "listPanel"
    assert page.locator("#listPanel").get_attribute("role") == "tabpanel"

    # the keys select and focus a tab, change the list and the panel's name
    all_list = _list_text(page)
    page.locator("#tabAll").focus()
    page.keyboard.press("ArrowRight")  # wraps
    assert _active(page) == "tabUpcoming"
    assert _tab_state(page) == {"Upcoming": ("true", "0"), "Past": ("false", "-1"), "All": ("false", "-1")}
    assert page.locator("#listPanel").get_attribute("aria-labelledby") == "tabUpcoming"
    assert _list_text(page) != all_list
    page.keyboard.press("ArrowLeft")  # wraps back
    assert _active(page) == "tabAll" and _list_text(page) == all_list
    page.keyboard.press("Home")
    assert _active(page) == "tabUpcoming"
    assert page.locator("#tabUpcoming").get_attribute("aria-selected") == "true"
    page.keyboard.press("End")
    assert _active(page) == "tabAll"
    assert page.locator("#listPanel").get_attribute("aria-labelledby") == "tabAll"
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowRight")
    assert _active(page) == "tabPast" and page.locator("#listPanel").get_attribute("aria-labelledby") == "tabPast"
    page.keyboard.press("End")

    # the disclosures
    assert page.locator("#recordCount").get_attribute("aria-live") == "polite"
    toggle = page.get_by_role("button", name="Show details").first
    assert toggle.get_attribute("aria-expanded") == "false"
    assert _expanded(page, "#attentionToggle", False) and _expanded(page, "#banner", False)
    assert _expanded(page, "#filterToggle", False)
    page.click("#attentionToggle")
    page.click("#banner")
    page.click("#filterToggle")
    assert _expanded(page, "#attentionToggle", True) and _expanded(page, "#banner", True)
    assert _expanded(page, "#filterToggle", True)
    page.click("#filterToggle")
    assert _expanded(page, "#filterToggle", False)
    page.click("#attentionToggle")
    page.click("#banner")
    toggle.click()
    assert page.get_by_role("button", name="Hide details", expanded=True).count() == 1

    # a visible ring after keyboard focus
    for selector in ("#tabAll", "#refreshBtn", ".card-toggle", ".open-button", "#attentionToggle"):
        _by_keyboard(page, selector)
        style, width = _ring(page)
        assert style != "none" and width == "2px", (selector, style, width)

    # the Open controls carry the names Tasks 4 and 5 build
    page.click("#prevMonthBtn")
    sweden = page.locator(f'.election-item[data-group-id="{SWEDEN_CARD}"]')
    sweden.locator("button.card-toggle").click()
    heading = sweden.locator(f'.child-entry[data-child-id="{SWEDEN_CHILD}"] .child-heading').text_content()
    assert heading
    name = f"Open ElectionGuide for {heading} (new tab)"
    assert page.get_by_role("button", name=name, exact=True).count() == 1
    if page.locator("#attentionToggle").get_attribute("aria-expanded") != "true":
        page.click("#attentionToggle")
    for item in feed_doc["attention_items"][:4]:
        want = f"Open {SOURCE_NAMES[item['source']]}: {item['text'][:80]} (new tab)"
        button = page.locator(f'.attention-row[data-item-id="{item["item_id"]}"] button')
        assert button.get_attribute("aria-label") == want
        assert page.get_by_role("button", name=want, exact=True).count() >= 1
    _options_rows(ext, pair)
    assert ext.page_errors == []


def test_legacy_render_has_the_same_tab_semantics(ext: Ext) -> None:
    ext.seed({FEED: feed_record(fresh_v1_feed(), fmt="legacy"), CHECK: _fresh_check()})
    page = ext.popup()
    assert page.evaluate("document.body.dataset.renderer") == "legacy"
    tablist = page.get_by_role("tablist", name="Show")
    assert [t.strip() for t in tablist.get_by_role("tab").all_text_contents()] == ["Upcoming", "Past", "All"]
    assert _tab_state(page) == {"Upcoming": ("false", "-1"), "Past": ("false", "-1"), "All": ("true", "0")}
    assert page.locator("#listPanel").get_attribute("aria-labelledby") == "tabAll"
    all_list = _list_text(page)
    page.locator("#tabAll").focus()
    page.keyboard.press("ArrowLeft")
    assert _active(page) == "tabPast"
    assert _tab_state(page) == {"Upcoming": ("false", "-1"), "Past": ("true", "0"), "All": ("false", "-1")}
    assert page.locator("#listPanel").get_attribute("aria-labelledby") == "tabPast"
    assert page.locator("#tabPast").get_attribute("class") == "nav-tab active"
    assert _list_text(page) != all_list
    page.keyboard.press("Home")
    assert _active(page) == "tabUpcoming" and page.locator("#tabUpcoming").get_attribute("aria-selected") == "true"
    page.keyboard.press("End")
    assert _active(page) == "tabAll" and _list_text(page) == all_list
    page.click("#tabPast")
    assert _tab_state(page)["Past"] == ("true", "0")
    assert ext.page_errors == []


def _options_rows(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    """The options page: pin buttons expose aria-pressed, and a keyboard pin keeps its focus."""
    feed, status = pair
    ext.seed({
        FEED: feed_record(feed), STATUS: status_record(status), CHECK: _fresh_check(),
        "pins_migrated_v2": True, "pinned_places_v2": [], "unresolved_pins_v2": [],
    })
    page = ext.open("options.html")
    page.wait_for_function(IDLE)
    buttons = page.locator(".country-item .pin-btn")
    assert buttons.count() == 73
    assert set(buttons.evaluate_all("els => els.map(e => e.getAttribute('aria-pressed'))")) == {"false"}
    target = buttons.nth(3)
    key = target.get_attribute("data-pin-key")
    assert key is not None
    target.focus()
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    wrap_pin_messages(page, "hold")  # the reply waits, so a frame passes with the button disabled
    page.keyboard.press("Enter")
    page.wait_for_function("() => document.activeElement === document.body")
    release_pin_reply(page)
    page.wait_for_function(
        "k => document.querySelector(`button[data-pin-key='${k}']`).getAttribute('aria-pressed') === 'true'",
        arg=key,
    )
    page.wait_for_function(IDLE)
    assert page.evaluate("() => document.activeElement.dataset.pinKey || document.activeElement.tagName") == key
    assert ext.page_errors == []


def _hold_until_requested(ext: Ext, page: Page) -> None:
    for _ in range(100):
        if "elections.json" in ext.served.log:
            return
        page.wait_for_timeout(50)
    raise AssertionError("the popup never asked for elections.json")


def _focused_card(page: Page) -> str | None:
    card: str | None = page.evaluate(
        "() => { const li = document.activeElement.closest('.election-item'); return li ? li.dataset.groupId : null; }"
    )
    return card


def _focused_key(page: Page) -> str | None:
    key: str | None = page.evaluate("() => document.activeElement.dataset.focus ?? null")
    return key


def test_focus_survives_a_redraw(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    old = int(time.time() * 1000) - 3 * 3_600_000  # a check is due
    pair_at = datetime(2026, 10, 19, 13, 0, tzinfo=UTC)
    rollback_feed, rollback_status = republication(fresh_v1_feed(), now=pair_at)
    toggle_key = f"toggle:{BRAZIL_CARD}"

    def held_popup() -> Page:
        ext.reset()
        ext.seed({
            FEED: feed_record(feed), STATUS: status_record(status),
            CHECK: {"ok_at": old, "failed_at": None, "error": None},
        })
        ext.served.set("elections.json", "hold")
        ext.served.set("status.json", status)
        page = ext.open("popup.html")
        page.wait_for_function("() => document.body.dataset.state === 'ready'")
        _hold_until_requested(ext, page)
        assert page.evaluate("document.body.dataset.checking") == "true"
        return page

    def settle(page: Page, body: bytes) -> None:
        ext.served.release("elections.json", body)
        page.wait_for_function("() => document.body.dataset.checking === 'false'")

    # a card toggle, activated by the keyboard, keeps focus and stays expanded
    page = held_popup()
    brazil = page.locator(f'.election-item[data-group-id="{BRAZIL_CARD}"]')
    brazil.locator("button.card-toggle").focus()
    page.keyboard.press("Enter")
    assert brazil.locator("button.card-toggle").get_attribute("aria-expanded") == "true"
    assert _focused_key(page) == toggle_key
    settle(page, feed)
    assert _focused_key(page) == toggle_key
    assert _focused_card(page) == BRAZIL_CARD
    assert page.evaluate("document.activeElement.getAttribute('aria-expanded')") == "true"
    assert brazil.locator(".child-entry").count() == 18

    # an Open button inside the open card
    page = held_popup()
    brazil = page.locator(f'.election-item[data-group-id="{BRAZIL_CARD}"]')
    brazil.locator("button.card-toggle").click()
    first = brazil.locator(".child-entry .open-button").first
    key = f"open:{BRAZIL_FIRST_CHILD}:0"
    assert first.get_attribute("data-focus") == key
    first.focus()
    assert _focused_key(page) == key
    settle(page, feed)
    assert _focused_key(page) == key
    assert page.evaluate("document.activeElement.classList.contains('open-button')")
    assert _focused_card(page) == BRAZIL_CARD

    # the last source Open button and the last umbrella one of the card, not only the first
    for kind, prefix in (("source-open", "open:"), ("umbrella-open", "umbrella:")):
        page = held_popup()
        brazil = page.locator(f'.election-item[data-group-id="{BRAZIL_CARD}"]')
        brazil.locator("button.card-toggle").click()
        last = brazil.locator(f".child-entry .{kind}").last
        got_key = last.get_attribute("data-focus")
        assert got_key is not None and got_key.startswith(prefix) and got_key != f"open:{BRAZIL_FIRST_CHILD}:0"
        key = got_key
        last.focus()
        settle(page, feed)
        assert _focused_key(page) == key and _focused_card(page) == BRAZIL_CARD
        assert page.locator(f".child-entry .{kind}").last.evaluate("e => e === document.activeElement")

    # an attention row's Open button (the section sits above the list panel)
    page = held_popup()
    page.click("#attentionToggle")
    row = page.locator(".attention-row").nth(1)
    item_id = row.get_attribute("data-item-id")
    key = f"attention-open:{item_id}"
    row.locator("button.attention-open").focus()
    assert _focused_key(page) == key
    settle(page, feed)
    assert _focused_key(page) == key
    assert page.evaluate("document.activeElement.closest('.attention-row').dataset.itemId") == item_id

    # a focused control that is gone: the real rollback draws the legacy view
    page = held_popup()
    page.locator(f'.election-item[data-group-id="{BRAZIL_CARD}"] button.card-toggle').focus()
    assert _focused_key(page) == toggle_key
    ext.served.set("status.json", rollback_status)
    settle(page, rollback_feed)
    assert page.evaluate("document.body.dataset.renderer") == "legacy"
    assert page.locator(".card-toggle").count() == 0
    assert _active(page) == "listPanel"

    # the search box: no data-focus key, so a redraw leaves it alone
    page = held_popup()
    page.click("#filterToggle")
    page.locator("#searchInput").press_sequentially("Bra")
    settle(page, feed)
    got = page.evaluate(
        "() => [document.activeElement.id, document.activeElement.value, document.activeElement.selectionStart]"
    )
    assert got == ["searchInput", "Bra", 3]
    assert ext.page_errors == []
