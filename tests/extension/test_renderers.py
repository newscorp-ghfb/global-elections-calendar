"""The renderer x feed matrix and a format change inside one popup (Plan 5b-2 Task 3; R61, S5-T17)."""

import json
from datetime import UTC, datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from tests.support.extension import (
    Ext,
    artifact_pair,
    linking,
    published_at,
    republication,
    v1_feed,
)

FEED: Final = "elections_cache_v2"
STATUS: Final = "status_cache"
UNCONFIRMED: Final = "Current health can't be confirmed for this data"
NO_HEALTH: Final = "Source health isn't available for this data"
NO_CONTENT_ID: Final = b'{"schema_version": 2, "months": {}}'
NOT_JSON: Final = b"{not json"
SPLIT_ERROR: Final = "Cannot read properties of undefined (reading 'split')"
V102_PARSE: Final = (
    "Could not load data: Expected property name or '}' in JSON at position 1 (line 1 column 2)"
)


def _v1_fresh() -> bytes:
    """The v1 feed, generated 12 h before PAGE_NOW so it is not stale."""
    doc = json.loads(v1_feed())
    doc["generated_at"] = "2026-10-19T02:00:00Z"
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def _feeds() -> dict[str, bytes]:
    return {
        "v1": _v1_fresh(),
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


def _state(page: Page, renderer: str) -> dict[str, Any]:
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


def test_renderer_switches_inside_one_popup(ext: Ext) -> None:
    feed, status = artifact_pair()
    pair_at = datetime(2026, 10, 19, 13, 0, tzinfo=UTC)
    rollback_feed, rollback_status = republication(_v1_fresh(), now=pair_at)
    newer = published_at(feed, "2026-10-19T13:30:00Z")
    newer_status = linking(newer, status, "2026-10-19T13:30:00Z")

    steps = [
        ("legacy", (_v1_fresh(), None)),
        ("v2", (feed, status)),
        ("legacy", (rollback_feed, rollback_status)),
        ("v2", (newer, newer_status)),
    ]
    labels = {"legacy": ["Total Scheduled", "Held This Month"], "v2": ["Election records", "Confirmed held"]}

    ext.served.set("elections.json", steps[0][1][0])
    page = ext.popup()
    # per-renderer tab state: both show Past (each keeps its own)
    page.click("#tabPast")
    seen_tab = {"legacy": "past"}
    for index, (renderer, (step_feed, step_status)) in enumerate(steps):
        if index > 0:
            ext.served.set("elections.json", step_feed)
            ext.served.set("status.json", step_status)
            _search(page, "Brazil")
            _refresh(page)
        if renderer == "v2" and "v2" not in seen_tab:
            page.click("#tabPast")
            seen_tab["v2"] = "past"
        got = _state(page, renderer)
        assert got["renderer"] == renderer, index
        assert got["labels"] == labels[renderer], index
        assert got["record_count_visible"] is (renderer == "v2"), index
        other = "legacy_cards" if renderer == "v2" else "v2_cards"
        assert got[other] == 0, index
        assert got["v2_cards" if renderer == "v2" else "legacy_cards"] > 0, index
        assert got["active_tabs"] == [seen_tab[renderer]], index
        if index == 2:
            assert page.locator("#healthNote").text_content() == NO_HEALTH
        # a search typed before the step filters the new list; one renderer answers it
        _search(page, "Brazil")
        filtered = page.locator("#electionList > li").count()
        texts = page.locator("#electionList > li").all_text_contents()
        assert filtered > 0 and all("brazil" in t.lower() for t in texts), index
        _search(page, "")
        assert page.locator("#electionList > li").count() > filtered, index
        after = _state(page, renderer)
        assert after["renderer"] == renderer and after[other] == 0, index
        _search(page, "Brazil")
        assert page.locator("#electionList > li").count() == filtered, index
    assert ext.page_errors == []
