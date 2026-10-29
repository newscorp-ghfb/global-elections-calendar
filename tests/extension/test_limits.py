"""Layout in a narrow or short popup, the popup's time budget and bounded rendering of large
collections (Plan 5b-2 Task 6; P146, R59, R51, R26, S5-T21)."""

import json
import time
from datetime import datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from tests.support.extension import (
    ROOT,
    Ext,
    artifact_pair,
    feed_record,
    js,
    status_record,
    synthetic_feed,
)

FEED: Final = "elections_cache_v2"
STATUS: Final = "status_cache"
CHECK: Final = "check_state_v2"
US_CARD: Final = "54d4c47d9ded"
VIEWPORTS: Final = ((320, 600), (380, 300))
MAX_TABS: Final = 400


@pytest.fixture(scope="module")
def pair() -> tuple[bytes, bytes]:
    return artifact_pair()


def _dump(doc: Any) -> bytes:
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def _fresh_check() -> dict[str, Any]:
    return {"ok_at": int(time.time() * 1000), "failed_at": None, "error": None}


def _reason(code: str, level: str, text: str) -> dict[str, Any]:
    return {"code": code, "level": level, "stage": "parse", "year": None, "page": None, "text": text}


def _crowded(feed: bytes) -> tuple[bytes, int]:
    """The artifact with 10 source issues, four of its sources holding added ones, and the US
    2026-11-03 card cut to 27 children; with the count of issues."""
    doc = json.loads(feed)
    by_name = {entry["name"]: entry for entry in doc["source_health"]}
    by_name["IPU"]["reasons"] = []  # 7 warnings -> 6
    by_name["ElectionGuide"]["reasons"] = [_reason("unparsed_relevant", "warning", "relevant units unparsed: 3")]
    by_name["OSCE/ODIHR"]["reasons"] = [_reason("unavailable", "error", "OSCE/ODIHR did not answer")]
    by_name["Carter Center"]["reasons"] = [_reason("partial_relevant", "warning", "relevant units partly parsed: 5")]
    by_name["EEAS"]["reasons"] = [_reason("unparsed_relevant", "warning", "relevant units unparsed: 9")]
    issues = sum(
        1 for e in doc["source_health"] for r in e["reasons"] if r["level"] in ("warning", "error")
    )
    card = next(c for c in doc["months"]["2026-11"] if c["group_id"] == US_CARD)
    card["children"] = card["children"][:27]
    return _dump(doc), issues


def _inside(page: Page, selector: str) -> dict[str, Any]:
    """Scroll `selector` into view; where it lies and what is at its centre."""
    got: dict[str, Any] = page.evaluate(
        """s => {
          const el = document.querySelector(s);
          el.scrollIntoView();
          const r = el.getBoundingClientRect();
          const hit = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
          return {
            found: true, empty: r.width === 0 || r.height === 0,
            inside: r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight,
            hit: hit !== null && (el === hit || el.contains(hit)),
            rect: [r.left, r.top, r.right, r.bottom], at: hit === null ? null : hit.outerHTML.slice(0, 80),
          };
        }""",
        selector,
    )
    return got


def test_layout_in_a_narrow_or_short_popup(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, issues = _crowded(pair[0])
    assert issues == 10
    ext.seed({FEED: feed_record(feed), STATUS: status_record(pair[1]), CHECK: _fresh_check()})
    for width, height in VIEWPORTS:
        page = ext.open("popup.html")
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_function(
            "() => document.body.dataset.state === 'ready' && document.body.dataset.checking === 'false'"
        )
        page.click("#nextMonthBtn")  # November
        assert page.locator("#currentMonthLabel").text_content() == "NOVEMBER 2026"
        page.click("#banner")
        assert page.locator("#healthList > li").count() >= 4
        card = page.locator(f'.election-item[data-group-id="{US_CARD}"]')
        card.locator("button.card-toggle").click()
        assert card.locator(".child-entry").count() == 27
        page.click("#attentionToggle")
        assert page.locator(".attention-row").count() > 0

        where = f"{width}x{height}"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), where
        assert page.evaluate("document.body.scrollWidth <= innerWidth"), where
        mark = page.evaluate(
            """id => {
              const entries = document.querySelectorAll(`[data-group-id="${id}"] .child-entry`);
              const buttons = entries[26].querySelectorAll('.open-button');
              if (buttons.length === 0) return false;
              buttons[buttons.length - 1].setAttribute('data-last-open', 'true');
              return true;
            }""",
            US_CARD,
        )
        assert mark, "the 27th entry has no Open button"
        last_open = "[data-last-open]"
        checked = [
            "#tabUpcoming", "#tabPast", "#tabAll", "#refreshBtn", "#helpBtn", "#prevMonthBtn",
            "#nextMonthBtn", "#banner", "#filterToggle", f'.election-item[data-group-id="{US_CARD}"] .card-toggle',
            last_open, ".attention-row", "#electionList > li:last-child .card-toggle",
            "#footerData", "#footerChecked",
        ]
        for selector in checked:
            got = _inside(page, selector)
            assert not got["empty"], (where, selector)
            assert got["inside"], (where, selector, got["rect"])
            assert got["hit"], (where, selector, got["at"])
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), where
        if height <= 520:  # the document scrolls, not the list
            assert page.evaluate("document.scrollingElement.scrollHeight > innerHeight"), where
            assert page.evaluate("() => { const p = document.getElementById('listPanel'); return p.scrollHeight <= p.clientHeight + 1; }"), where

        # the keyboard reaches the 27th entry's last Open button
        page.locator("#helpBtn").focus()
        for _ in range(MAX_TABS):
            page.keyboard.press("Tab")
            if page.evaluate("s => document.activeElement === document.querySelector(s)", last_open):
                break
        else:
            raise AssertionError(f"{where}: Tab did not reach the 27th entry's Open button in {MAX_TABS}")
        page.close()
    assert ext.page_errors == []


def test_popup_renders_the_fixture_feed_within_the_budget(
    fresh_ext: Ext, pair: tuple[bytes, bytes], record_property: Any
) -> None:
    feed, status = pair
    fresh_ext.seed({FEED: feed_record(feed), STATUS: status_record(status), CHECK: _fresh_check()})
    page = fresh_ext.popup(now=None)
    measures: list[dict[str, Any]] = page.evaluate(
        "() => performance.getEntriesByName('popup:first-render').map(m => ({d: m.duration}))"
    )
    assert len(measures) == 1, "the popup made no first-render measure"
    ms = float(measures[0]["d"])
    record_property("popup_first_render_ms", round(ms, 1))
    print(f"\npopup:first-render {ms:.1f} ms")
    assert 0 < ms < 1000
    # the marks are made on the first render only (a check's reply renders again)
    assert page.evaluate("performance.getEntriesByName('popup:read').length") == 1
    assert page.evaluate("performance.getEntriesByName('popup:drawn').length") == 1
    assert fresh_ext.page_errors == []


def _show_october(page: Page) -> None:
    """The popup opens on the real month; step to October 2026 (the fixture's window is Sep-Jan)."""
    for _ in range(6):
        label = page.locator("#currentMonthLabel").text_content() or ""
        shown = datetime.strptime(label.title(), "%B %Y")
        if (shown.year, shown.month) == (2026, 10):
            return
        page.click("#prevMonthBtn" if (shown.year, shown.month) > (2026, 10) else "#nextMonthBtn")
    raise AssertionError("October 2026 is not in the window")


def test_large_collections_render_bounded(fresh_ext: Ext, pair: tuple[bytes, bytes]) -> None:
    # a launch of its own: a fixed context clock would stub the performance entries
    base: dict[str, Any] = json.loads(pair[0])
    october = len(base["months"]["2026-10"])
    big = synthetic_feed(pair[0], cards=1000, children=500, items=500, truncated=1200)
    schema = json.loads((ROOT / "schemas" / "feed-v2.schema.json").read_text(encoding="utf-8"))
    assert js(fresh_ext.lab(), "lib/validate.js", "feedFormat", json.loads(big), schema)["format"] == "v2"

    fresh_ext.seed({FEED: feed_record(big), CHECK: _fresh_check()})
    page = fresh_ext.popup(now=None)
    ms = page.evaluate("performance.getEntriesByName('popup:first-render')[0].duration")
    print(f"large feed popup:first-render {ms:.1f} ms")  # recorded, not asserted
    _show_october(page)
    assert page.locator("#electionList > li").count() == october + 1001
    assert page.locator(".child-entry").count() == 0
    synthetic = page.locator(".election-item", has_text="Synthetic Big")
    synthetic.locator("button.card-toggle").click()
    assert page.locator(".child-entry").count() == 500
    assert page.locator(".attention-row").count() == 0
    page.click("#attentionToggle")
    assert page.locator(".attention-row").count() == 200
    assert fresh_ext.page_errors == []
