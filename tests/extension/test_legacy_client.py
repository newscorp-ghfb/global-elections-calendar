"""A v1.0.2 client still renders the v2 feed (S1-T7)."""

import json

from tests.support.extension import Ext, artifact_pair, v1_feed


def _october(legacy_ext: Ext, feed: bytes) -> tuple[list[str], str, str]:
    legacy_ext.served.set("elections.json", feed)
    page = legacy_ext.open("popup.html")
    page.wait_for_selector("#electionList:not(.hidden) .election-item")
    # the page is v1.0.2's: "Results" is its tab, and "Past" does not exist yet
    assert page.locator("#tabResults").count() == 1
    assert page.locator("#tabPast").count() == 0
    names = page.locator("#electionList .election-country").all_text_contents()
    month = page.locator("#currentMonthLabel").text_content() or ""
    return names, month, page.locator("#footer").text_content() or ""


def test_v1_0_2_renders_the_v2_feed(legacy_ext: Ext) -> None:
    feed, _ = artifact_pair()
    names, month, footer = _october(legacy_ext, feed)
    doc = json.loads(feed)
    assert names == [c["country"] for c in doc["months"]["2026-10"]]  # 30 cards
    assert month == "OCTOBER 2026" and "Stale" not in footer
    assert legacy_ext.page_errors == []


def test_v1_0_2_renders_the_v1_feed(legacy_ext: Ext) -> None:
    names, month, _ = _october(legacy_ext, v1_feed())
    assert len(names) == 27 and month == "OCTOBER 2026"
    assert legacy_ext.page_errors == []
