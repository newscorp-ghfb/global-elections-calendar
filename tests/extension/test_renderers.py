"""The renderer x feed matrix and a format change inside one popup (Plan 5b-2 Task 3; R61, S5-T17)."""

from datetime import UTC, datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from tests.support.extension import (
    Ext,
    artifact_pair,
    fresh_v1_feed,
    linking,
    published_at,
    republication,
)

FEED: Final = "elections_cache_v2"
STATUS: Final = "status_cache"
BRAZIL_CARD: Final = "c8c9844ab7a8"
UNCONFIRMED: Final = "Current health can't be confirmed for this data"
NO_HEALTH: Final = "Source health isn't available for this data"
NO_CONTENT_ID: Final = b'{"schema_version": 2, "months": {}}'
NOT_JSON: Final = b"{not json"
SPLIT_ERROR: Final = "Cannot read properties of undefined (reading 'split')"
V102_PARSE: Final = (
    "Could not load data: Expected property name or '}' in JSON at position 1 (line 1 column 2)"
)


def _feeds() -> dict[str, bytes]:
    return {
        "v1": fresh_v1_feed(),
        "v2": artifact_pair()[0],
        "no_content_id": NO_CONTENT_ID,
        "not_json": NOT_JSON,
    }


def _wait_v102(page: Page) -> None:
    """v1.0.2's popup has no state attributes: wait for cards or an error, else a fixed beat."""
    try:
        page.wait_for_function(
            "() => document.querySelector('.election-item')"
            " || !document.getElementById('stateError').classList.contains('hidden')",
            timeout=4000,
        )
    except Exception:  # noqa: BLE001 - the stuck-on-loading cell never gets there
        page.wait_for_timeout(1000)


def _cards(page: Page) -> int:
    return page.locator("#electionList .election-item").count()


@pytest.mark.parametrize("feed_name", ["v1", "v2", "no_content_id", "not_json"])
@pytest.mark.parametrize("files", ["v1.0.2", "v2"])
def test_renderer_matrix(request: pytest.FixtureRequest, files: str, feed_name: str) -> None:
    ext: Ext = request.getfixturevalue("legacy_ext" if files == "v1.0.2" else "ext")
    ext.served.set("elections.json", _feeds()[feed_name])
    if files == "v1.0.2":
        page = ext.open("popup.html")
        _wait_v102(page)
        error_shown = page.locator("#stateError").is_visible()
        message = page.locator("#errorMsg").text_content()
        if feed_name == "v1":
            assert _cards(page) == 27
            assert page.locator("#currentMonthLabel").text_content() == "OCTOBER 2026"
            assert ext.page_errors == []
        elif feed_name == "v2":
            assert _cards(page) == 30
            assert ext.page_errors == []
        elif feed_name == "no_content_id":
            assert page.locator("#stateLoading").is_visible() and _cards(page) == 0
            assert len(ext.page_errors) == 1 and SPLIT_ERROR in ext.page_errors[0]
        else:
            assert error_shown and message == V102_PARSE
            assert ext.page_errors == []
        return
    page = ext.popup()
    stored = ext.storage()
    assert ext.page_errors == []
    if feed_name in ("v1", "v2"):
        renderer = "legacy" if feed_name == "v1" else "v2"
        assert page.evaluate("document.body.dataset.renderer") == renderer
        assert _cards(page) == (27 if feed_name == "v1" else 30)
        assert page.locator("#bannerText").text_content() == UNCONFIRMED
        assert stored[FEED]["format"] == renderer
    else:
        assert page.locator("#stateError").is_visible()
        want = (
            "Could not load data: elections.json: unreadable feed: /: missing content_id"
            if feed_name == "no_content_id"
            else "Could not load data: elections.json: not UTF-8 JSON"
        )
        assert page.locator("#errorMsg").text_content() == want
        assert FEED not in stored and STATUS not in stored


def _search(page: Page, value: str) -> None:
    if not page.locator("#searchInput").is_visible():
        page.click("#filterToggle")
    page.fill("#searchInput", value)


def _refresh(page: Page) -> None:
    page.click("#refreshBtn")
    page.wait_for_function(
        "() => document.body.dataset.state === 'ready' && document.body.dataset.checking === 'false'"
    )


def _state(page: Page) -> dict[str, Any]:
    return {
        "renderer": page.evaluate("document.body.dataset.renderer"),
        "labels": [
            page.locator("#statTotalLabel").text_content(),
            page.locator("#statHeldLabel").text_content(),
        ],
        "record_count_visible": page.locator("#recordCount").is_visible(),
        "v2_cards": page.locator("#electionList > li.election-item-v2").count(),
        "legacy_cards": page.locator("#electionList > li.election-item:not(.election-item-v2)").count(),
        "active_tabs": page.locator(".nav-tab.active").evaluate_all("els => els.map(e => e.dataset.filter)"),
    }


def _shown(page: Page) -> list[str]:
    return page.locator("#electionList > li").all_text_contents()


def test_renderer_switches_inside_one_popup(ext: Ext) -> None:
    feed, status = artifact_pair()
    pair_at = datetime(2026, 10, 19, 13, 0, tzinfo=UTC)
    rollback_feed, rollback_status = republication(fresh_v1_feed(), now=pair_at)
    newer = published_at(feed, "2026-10-19T13:30:00Z")
    newer_status = linking(newer, status, "2026-10-19T13:30:00Z")

    # (renderer, feed, status, search typed before the step, banner text, tab left on)
    # The search is typed while the outgoing renderer is shown, so the incoming renderer last saw
    # the previous step's term; consecutive terms differ, so a stale query shows. The two renderers
    # are left on different tabs (legacy on Past, v2 on All).
    steps = [
        ("legacy", fresh_v1_feed(), None, "Brazil", UNCONFIRMED, "past"),
        ("v2", feed, status, "Canada", None, "all"),
        ("legacy", rollback_feed, rollback_status, "Brazil", NO_HEALTH, "past"),
        ("v2", newer, newer_status, "Canada", None, "all"),
    ]
    labels = {"legacy": ["Total Scheduled", "Held This Month"], "v2": ["Election records", "Confirmed held"]}

    ext.served.set("elections.json", steps[0][1])
    page = ext.popup()
    page.click("#tabPast")  # legacy's tab; v2 keeps its default (All) until it is clicked
    for index, (renderer, step_feed, step_status, term, banner, tab) in enumerate(steps):
        _search(page, term)  # typed while the previous renderer is shown
        if index > 0:
            ext.served.set("elections.json", step_feed)
            ext.served.set("status.json", step_status)
            _refresh(page)
        # right after the refresh, before any more typing: the new list is already filtered
        got = _state(page)
        assert got["renderer"] == renderer, index
        assert got["labels"] == labels[renderer], index
        assert got["record_count_visible"] is (renderer == "v2"), index
        other = "legacy_cards" if renderer == "v2" else "v2_cards"
        assert got[other] == 0, index
        assert got["v2_cards" if renderer == "v2" else "legacy_cards"] > 0, index
        assert got["active_tabs"] == [tab], index
        filtered = _shown(page)
        assert filtered and all(term.lower() in t.lower() for t in filtered), index
        if banner is not None:
            assert page.locator("#bannerText").text_content() == banner, index
        if index == 2:
            assert page.locator("#banner").get_attribute("data-level") == "amber"
        # the list is the highlighted tab's list
        if renderer == "legacy":
            chips = page.locator("#electionList > li .election-chips").evaluate_all(
                "els => els.map(e => e.lastElementChild.textContent)"
            )
            assert chips == ["Held"] * len(filtered), index
        else:
            page.click("#tabAll")
            assert len(_shown(page)) == len(filtered), index
        # one renderer answers the box
        _search(page, "")
        assert len(_shown(page)) > len(filtered), index
        brazil = page.locator(f'.election-item[data-group-id="{BRAZIL_CARD}"]')
        if index == 1:  # expand a card while v2 is shown; the open set outlives the renderer
            brazil.locator("button.card-toggle").click()
            assert brazil.locator(".child-entry").count() == 18
            page.click("#attentionToggle")  # the attention section is opened while v2 is shown
            assert page.locator("#attentionToggle").get_attribute("aria-expanded") == "true"
            assert page.locator("#attentionList > li.attention-row").count() > 0
        if index == 2:  # legacy: nothing of the v2 disclosure remains
            assert page.locator("#electionList .card-details, .card-toggle").count() == 0
            assert page.locator("#attention").is_hidden()
            assert page.locator("#attentionToggle").is_hidden()
        if index == 3:  # v2 again: the card is open again (remembered by group_id)
            assert brazil.locator("button.card-toggle").get_attribute("aria-expanded") == "true"
            assert brazil.locator(".child-entry").count() == 18
            # ... and so is the attention section, open again
            assert page.locator("#attentionToggle").is_visible()
            assert page.locator("#attentionToggle").get_attribute("aria-expanded") == "true"
            assert page.locator("#attentionList > li.attention-row").count() > 0
        after = _state(page)
        assert after["renderer"] == renderer and after[other] == 0, index
        assert after["active_tabs"] == [tab], index
        _search(page, term)
        assert len(_shown(page)) == len(filtered), index
    assert ext.page_errors == []
