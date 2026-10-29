"""lib/count.js, lib/render.js: one pipeline for tabs, filters and counters (Plan 5b-1 Task 6; P135, P138)."""

import copy
import json
import time
from typing import Any, Final

import pytest
from playwright.sync_api import Locator, Page

from tests.support.extension import PAGE_NOW_MS, Ext, artifact_pair, feed_record, js, v1_feed

FEED: Final = "elections_cache_v2"
CHECK: Final = "check_state_v2"
TODAY: Final = "2026-10-19"
OCT: Final = "2026-10"

_VIEW_JS: Final = """async ([doc, opts]) => {
  const { view } = await import('/lib/count.js');
  const { pinMatcher } = await import('/lib/pins.js');
  const { loadPlaces } = await import('/lib/load.js');
  const table = await loadPlaces((p) => chrome.runtime.getURL(p));
  const v = view(doc, { ...opts, pins: pinMatcher(opts.pinned, table) });
  return {
    records: v.records, groupings: v.groupings, held: v.held,
    cards: v.cards.map((c) => ({
      id: c.card.group_id, country: c.card.country, kept: c.children.length, total: c.total,
      match: c.match, label: c.label.text, kind: c.label.kind,
      kinds: c.children.map((x) => x.label.kind), texts: c.children.map((x) => x.label.text),
    })),
  };
}"""

_TABS_JS: Final = """async ([label, card, today]) => {
  const { tabsOf } = await import('/lib/count.js');
  return [...tabsOf(label, card, today)].sort();
}"""


@pytest.fixture(scope="module")
def pair() -> tuple[bytes, bytes]:
    return artifact_pair()


@pytest.fixture(scope="module")
def feed_doc(pair: tuple[bytes, bytes]) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(pair[0])
    return doc


def _view(
    lab: Page,
    doc: dict[str, Any],
    month: str = OCT,
    tab: str = "all",
    level: str = "all",
    query: str = "",
    pinned: tuple[str, ...] = (),
) -> dict[str, Any]:
    opts = {
        "month": month, "tab": tab, "level": level, "query": query,
        "pinned": list(pinned), "today": TODAY, "now": PAGE_NOW_MS,
    }
    got: dict[str, Any] = lab.evaluate(_VIEW_JS, [doc, opts])
    return got


def _shape(v: dict[str, Any]) -> tuple[int, int, int, int]:
    return (len(v["cards"]), v["records"], v["groupings"], v["held"])


def _card(doc: dict[str, Any], bucket: str, country: str, **fields: Any) -> dict[str, Any]:
    found: dict[str, Any] = next(
        c for c in doc["months"][bucket]
        if c["country"] == country and all(c[k] == val for k, val in fields.items())
    )
    return found


def _synthetic(doc: dict[str, Any], tag: str, **fields: Any) -> dict[str, Any]:
    """A one-child card copied from October's first card, with its own ids and `fields`."""
    card: dict[str, Any] = copy.deepcopy(doc["months"][OCT][0])
    card["children"] = card["children"][:1]
    card["children"][0]["child_id"] = "synthetic-" + tag
    card["group_id"] = "synthetic-" + tag
    card["status"] = "Upcoming"
    card["children"][0].update(occurrence_confirmed=False, status_conflict=False, date_conflict=False)
    card.update(fields)
    return card


def _ids(v: dict[str, Any]) -> list[str]:
    return [c["id"] for c in v["cards"]]


# ── the pure rules ────────────────────────────────────────────────────────────


def test_children_are_counted_once(lab: Page, feed_doc: dict[str, Any]) -> None:
    base = _view(lab, feed_doc)
    assert _shape(base) == (30, 58, 11, 8)
    texts = {
        (58, 11): "58 election records (incl. 11 groupings)",
        (1, 1): "1 election record (incl. 1 grouping)",
        (2, 0): "2 election records",
        (0, 0): "0 election records",
    }
    for (records, groupings), want in texts.items():
        assert js(lab, "lib/count.js", "recordText", records, groupings) == want

    doubled = copy.deepcopy(feed_doc)
    shared = copy.deepcopy(doubled["months"][OCT][0]["children"][0])
    doubled["months"][OCT][1]["children"].append(shared)
    assert _shape(_view(lab, doubled)) == (30, 58, 11, 8)

    # The held counter follows the label, not occurrence_confirmed.
    held_card = next(c for c in base["cards"] if "held" in c["kinds"])
    index = held_card["kinds"].index("held")
    conflicted = copy.deepcopy(feed_doc)
    cards = conflicted["months"][OCT]
    child = next(c for c in cards if c["group_id"] == held_card["id"])["children"][index]
    assert child["occurrence_confirmed"] is True
    child["status_conflict"] = True
    after = _view(lab, conflicted)
    assert after["held"] == 7 and after["records"] == 58
    entry = next(c for c in after["cards"] if c["id"] == held_card["id"])
    assert entry["texts"][index] == "Possibly postponed — sources disagree"


def test_month_rule(lab: Page, feed_doc: dict[str, Any]) -> None:
    # the fixture: only Fiji's 24 Dec - 6 Feb card reaches past its bucket
    months = ("2026-09", OCT, "2026-11", "2026-12", "2027-01")
    got = [_shape(_view(lab, feed_doc, m))[:2] for m in months]
    assert got == [(22, 27), (30, 58), (28, 89), (15, 21), (6, 8)]
    fiji = _card(feed_doc, "2026-12", "Fiji", date="2026-12-24")
    entry = next(c for c in _view(lab, feed_doc, "2027-01")["cards"] if c["id"] == fiji["group_id"])
    assert entry["label"] == "Scheduled"
    assert js(lab, "lib/dates.js", "badge", fiji) == {"day": "24–6", "mon": "DEC–FEB"}
    assert fiji["group_id"] not in _ids(_view(lab, feed_doc, "2026-11"))

    # a synthetic day-precision voting period, bucketed in December, shows in December and January
    doc = copy.deepcopy(feed_doc)
    long_vote = _synthetic(
        doc, "long", date="2026-12-24", end_date="2027-02-06", date_precision="day",
        date_meaning="voting_period",
    )
    doc["months"]["2026-12"].append(long_vote)
    for month, records in (("2026-12", 22), ("2027-01", 9)):
        v = _view(lab, doc, month)
        assert v["records"] == records
        assert _ids(v).count("synthetic-long") == 1
    assert "synthetic-long" not in _ids(_view(lab, doc, "2026-11"))

    # a synthetic month-precision expected window keeps its "Expected ..." label in each month
    doc = copy.deepcopy(feed_doc)
    window = _synthetic(
        doc, "window", date="2026-11-01", end_date="2027-01-31", date_precision="month",
        date_meaning="expected_window", date_status="tentative",
    )
    doc["months"]["2026-11"].append(window)
    for month in ("2026-11", "2026-12", "2027-01"):
        entry = next(c for c in _view(lab, doc, month)["cards"] if c["id"] == "synthetic-window")
        assert entry["label"] == "Expected between November and January"
    assert "synthetic-window" not in _ids(_view(lab, doc, OCT))


def test_partial_matches(lab: Page, feed_doc: dict[str, Any]) -> None:
    for query in ("county elections", "COUNTY ELECTIONS", "  county elections "):
        v = _view(lab, feed_doc, "2026-11", query=query)
        assert len(v["cards"]) == 1
        only = v["cards"][0]
        assert (only["country"], only["kept"], only["total"], only["match"]) == (
            "United States", 1, 59, "1 matching of 59",
        )
        assert (v["records"], v["groupings"]) == (1, 1)
    everything = _view(lab, feed_doc, "2026-11", query="United States")["cards"]
    full = next(c for c in everything if c["total"] == 59)
    assert (full["kept"], full["match"]) == (59, "")

    # the card's own type is cut, so search never reads it
    doc = copy.deepcopy(feed_doc)
    doc["months"][OCT][0]["type"] = "Zzyzx only in the card type"
    assert _view(lab, doc, query="zzyzx")["cards"] == []


def test_tab_membership(lab: Page) -> None:
    upcoming = {
        "scheduled", "today", "day_unconfirmed", "expected",
        "possibly_postponed", "possibly_cancelled", "postponed",
    }
    past = {"held", "past", "past_expected"}
    card = {"end_date": "2030-01-01"}
    kinds = lab.evaluate("async () => (await import('/lib/labels.js')).KINDS")
    assert len(kinds) == 12
    for kind in kinds:
        if kind == "disputed":
            continue
        want = {"all"} | ({"upcoming"} if kind in upcoming else set()) | ({"past"} if kind in past else set())
        assert set(lab.evaluate(_TABS_JS, [{"kind": kind}, card, TODAY])) == want, kind
    assert lab.evaluate(_TABS_JS, [{"kind": "cancelled"}, card, TODAY]) == ["all"]
    for end, tab in (("2026-10-18", "past"), ("2026-10-19", "upcoming")):
        got = lab.evaluate(_TABS_JS, [{"kind": "disputed"}, {"end_date": end}, TODAY])
        assert got == sorted(["all", tab]), end


def test_level_filter(lab: Page, feed_doc: dict[str, Any]) -> None:
    rows = [
        ("2026-10", "national", (15, 19)),
        ("2026-10", "subnational", (15, 39)),
        ("2026-09", "national", (15, 18)),
        ("2026-09", "subnational", (12, 16)),
    ]
    for month, level, want in rows:
        v = _view(lab, feed_doc, month, level=level)
        assert (len(v["cards"]), v["records"]) == want, (month, level)
    unknown = [c["group_id"] for c in feed_doc["months"]["2026-09"] if c["level"] == "unknown"]
    assert len(unknown) == 5
    for level in ("national", "subnational"):
        shown = set(_ids(_view(lab, feed_doc, "2026-09", level=level)))
        assert set(unknown) <= shown, level


def test_tab_counts_on_the_fixture(lab: Page, feed_doc: dict[str, Any]) -> None:
    assert _shape(_view(lab, feed_doc, OCT, "upcoming")) == (11, 15, 7, 0)
    assert _shape(_view(lab, feed_doc, OCT, "past")) == (19, 43, 4, 8)
    assert _view(lab, feed_doc, "2026-09", "upcoming")["cards"] == []
    assert _view(lab, feed_doc, "2026-11", "past")["cards"] == []


# ── the popup ─────────────────────────────────────────────────────────────────

RECORDS_ALL: Final = "58 election records (incl. 11 groupings)"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _fresh_check() -> dict[str, Any]:
    return {"ok_at": _now_ms(), "failed_at": None, "error": None}


def _open(ext: Ext, pair: tuple[bytes, bytes]) -> Page:
    feed, status = pair
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    return ext.popup()


def _text(page: Page, selector: str) -> str:
    return page.locator(selector).text_content() or ""


def _text_of(item: Locator, selector: str) -> str:
    return item.locator(selector).text_content() or ""


def _cards(page: Page) -> int:
    return page.locator(".election-item").count()


def _tabs(page: Page) -> dict[str, tuple[bool, str | None]]:
    out: dict[str, tuple[bool, str | None]] = {}
    for name in ("tabUpcoming", "tabPast", "tabAll"):
        tab = page.locator("#" + name)
        classes = (tab.get_attribute("class") or "").split()
        out[name] = ("active" in classes, tab.get_attribute("aria-selected"))
    return out


def _only_active(page: Page, name: str) -> bool:
    """`name` is `active` and `aria-selected="true"`; the other two are not and say "false"."""
    return all(
        state == ((t == name), "true" if t == name else "false")
        for t, state in _tabs(page).items()
    )


def _search(page: Page, value: str) -> None:
    if page.locator("#filterBar").is_hidden():
        page.click("#filterToggle")
    page.fill("#searchInput", value)


def _settled(page: Page) -> None:
    page.wait_for_function(
        "() => document.body.dataset.state === 'ready' && document.body.dataset.checking === 'false'"
    )


def test_tabs_and_counters_share_one_state(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    page = _open(ext, pair)
    # on open
    assert _only_active(page, "tabAll")
    assert _cards(page) == 30
    assert _text(page, "#recordCount") == RECORDS_ALL
    assert (_text(page, "#statTotal"), _text(page, "#statHeld")) == ("58", "8")
    assert (_text(page, "#statTotalLabel"), _text(page, "#statHeldLabel")) == (
        "Election records", "Confirmed held",
    )
    # Upcoming
    page.click("#tabUpcoming")
    assert _only_active(page, "tabUpcoming")
    assert _cards(page) == 11
    assert _text(page, "#recordCount") == "15 election records (incl. 7 groupings)"
    assert (_text(page, "#statTotal"), _text(page, "#statHeld")) == ("15", "0")
    # Past
    page.click("#tabPast")
    assert _only_active(page, "tabPast")
    assert _cards(page) == 19
    assert _text(page, "#recordCount") == "43 election records (incl. 4 groupings)"
    assert _text(page, "#statHeld") == "8"
    # All, then November, then a search
    page.click("#tabAll")
    assert _only_active(page, "tabAll")
    page.click("#nextMonthBtn")
    assert _text(page, "#currentMonthLabel") == "NOVEMBER 2026"
    _search(page, "county elections")
    assert _cards(page) == 1
    assert _text(page, ".election-item .card-match") == "1 matching of 59"
    assert _text(page, "#recordCount") == "1 election record (incl. 1 grouping)"
    # the level filter, in October with no search
    _search(page, "")
    page.click("#prevMonthBtn")
    page.select_option("#levelFilter", "national")
    assert _cards(page) == 15
    assert _text(page, "#recordCount") == "19 election records"
    assert ext.page_errors == []


def test_v2_cards_show_labels_and_badges(
    ext: Ext, pair: tuple[bytes, bytes], feed_doc: dict[str, Any]
) -> None:
    page = _open(ext, pair)

    def card(bucket: str, country: str, **fields: Any) -> Locator:
        group = _card(feed_doc, bucket, country, **fields)["group_id"]
        return page.locator(f'.election-item[data-group-id="{group}"]')

    def badge(item: Locator) -> tuple[str, str]:
        return (_text_of(item, ".date-badge .day"), _text_of(item, ".date-badge .mon"))

    canada = card(OCT, "Canada", date="2026-10-19")
    assert _text_of(canada, ".card-label") == "Scheduled voting period: today (approx.)"
    czech = card(OCT, "Czech Republic", date="2026-10-09")
    assert badge(czech) == ("9–10", "OCT")
    assert _text_of(czech, ".card-match") == ""
    assert czech.locator(".card-notes > li").count() == 0

    # R47: a v2 card opens no link
    pages_before = len(ext.context.pages)
    page.evaluate("() => { window.__opened = []; chrome.tabs.create = (o) => { window.__opened.push(o); }; }")
    canada.click()
    assert page.evaluate("() => window.__opened") == []
    assert len(ext.context.pages) == pages_before

    page.click("#prevMonthBtn")
    assert badge(card("2026-09", "Russia", date="2026-09-18")) == ("18–20", "SEP")

    page.click("#nextMonthBtn")
    page.click("#nextMonthBtn")
    assert _text(page, "#currentMonthLabel") == "NOVEMBER 2026"
    verde = card("2026-11", "Cape Verde")
    assert verde.locator(".card-notes > li").all_text_contents() == ["Sources disagree on date"]

    page.click("#nextMonthBtn")
    libya = card("2026-12", "Libya")
    assert badge(libya) == ("TBC", "DEC")
    assert _text_of(libya, ".card-label") == "Expected in December"
    assert _text_of(libya, ".chip-tentative") == "Tentative"
    assert ext.page_errors == []


def test_v2_card_text_is_inserted_as_text(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, _ = pair
    doc = json.loads(feed)
    doc["months"][OCT][0]["country"] = "<b>X</b>"
    doc["months"][OCT][0]["type"] = "<img src=x>"
    raw = json.dumps(doc, separators=(",", ":")).encode()
    ext.seed({FEED: feed_record(raw), CHECK: _fresh_check()})
    page = ext.popup()
    first = page.locator(".election-item").first
    assert _text_of(first, ".election-country") == "<b>X</b>"
    assert _text_of(first, ".election-type") == "<img src=x>"
    assert page.locator("#electionList b").count() == 0
    assert page.locator("#electionList img").count() == 0
    assert ext.page_errors == []


def test_legacy_feeds_keep_the_legacy_renderer(ext: Ext) -> None:
    ext.seed({FEED: feed_record(v1_feed(), fmt="legacy"), CHECK: _fresh_check()})
    page = ext.popup()
    assert ext.served.log == []
    assert _cards(page) == 27
    tabs = _tabs(page)
    assert tabs["tabAll"][0] and not tabs["tabPast"][0]
    assert _text(page, "#statTotalLabel") == "Total Scheduled"
    page.click("#filterToggle")
    assert page.locator("#filterBar").is_visible()
    assert page.locator("#levelFilter").is_hidden()
    assert page.locator("#recordCount").is_hidden()
    page.click("#tabPast")
    assert _cards(page) == 15
    assert ext.page_errors == []


def test_only_the_active_renderer_handles_controls(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    page = _open(ext, pair)
    page.click("#tabUpcoming")
    assert (_cards(page), _text(page, "#recordCount")) == (11, "15 election records (incl. 7 groupings)")
    page.click("#nextMonthBtn")
    assert _text(page, "#currentMonthLabel") == "NOVEMBER 2026"
    assert (_text(page, "#prevMonthLabel"), _text(page, "#nextMonthLabel")) == ("OCT", "DEC")
    assert _cards(page) == 28
    page.click("#prevMonthBtn")
    assert _text(page, "#listTitle") == "October 2026 Schedule"
    _search(page, "zzzz")
    assert _cards(page) == 0
    _search(page, "Canada")
    assert _cards(page) > 0 and _text(page, "#statTotalLabel") == "Election records"
    _search(page, "")
    assert (_cards(page), _text(page, "#statTotal")) == (11, "15")
    assert _text(page, "#currentMonthLabel") == "OCTOBER 2026"
    assert page.locator("#levelFilter").is_visible()
    assert ext.page_errors == []

    # a format switch inside one popup: the legacy renderer takes the controls over
    ext.seed({FEED: feed_record(v1_feed(), fmt="legacy")})
    ext.served.set("elections.json", 503)
    page.click("#refreshBtn")
    _settled(page)
    assert _cards(page) == 27 and page.locator("#levelFilter").is_hidden()
    assert _text(page, "#statTotalLabel") == "Total Scheduled"
    assert _text(page, "#statTotal") == "27"
    tabs = _tabs(page)
    # legacy now sets the tab attributes too (Plan 5b-2 Task 6, P146): it used to remove aria-selected
    assert _only_active(page, "tabAll"), tabs
    page.click("#tabPast")
    assert _cards(page) == 15
    # v2's listener would have drawn its controls back
    assert page.locator("#levelFilter").is_hidden() and page.locator("#recordCount").is_hidden()
    assert _text(page, "#statTotalLabel") == "Total Scheduled"
    assert ext.page_errors == []


def test_v2_shares_the_legacy_states(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    ext.seed({"pins_migrated_v2": True, "pinned_places_v2": ["iso:CZ"], "unresolved_pins_v2": []})
    page = _open(ext, pair)
    assert page.locator("#pinBar").is_visible()
    assert _text(page, "#pinBarText") == "Pinned view · 1 country"
    assert _cards(page) == 3
    assert _text(page, "#recordCount") == "3 election records (incl. 1 grouping)"

    page.click("#prevMonthBtn")
    assert _text(page, "#currentMonthLabel") == "SEPTEMBER 2026"
    assert page.locator("#prevMonthBtn").evaluate("e => e.style.visibility") == "hidden"
    assert _text(page, "#prevMonthLabel") == ""
    assert _text(page, "#nextMonthLabel") == "OCT"
    assert page.locator("#stateEmpty").is_visible() and page.locator("#electionList").is_hidden()
    page.click("#nextMonthBtn")
    assert page.locator("#stateEmpty").is_hidden() and _cards(page) == 3

    for _ in range(3):
        page.click("#nextMonthBtn")
    assert _text(page, "#currentMonthLabel") == "JANUARY 2027"
    assert page.locator("#nextMonthBtn").evaluate("e => e.style.visibility") == "hidden"
    assert _text(page, "#nextMonthLabel") == ""

    ext.seed({"pinned_places_v2": []})
    page.click("#refreshBtn")
    _settled(page)
    assert page.locator("#pinBar").is_hidden()
    assert ext.page_errors == []


def test_a_month_outside_the_window_falls_back(ext: Ext, feed_doc: dict[str, Any]) -> None:
    lab = ext.lab()

    def start(current: str, today: str, months: list[str] | None = None) -> str:
        doc = {
            "current_month": current,
            "window": {"months": feed_doc["window"]["months"] if months is None else months},
        }
        got: str = js(lab, "lib/count.js", "startMonth", doc, today)
        return got

    assert start(OCT, TODAY) == OCT
    assert start("2027-01", TODAY) == "2027-01"  # in the window: the producer's month wins
    assert start("2027-05", TODAY) == OCT  # today's month, when it is in the window
    assert start("2027-05", "2027-06-01") == "2026-09"  # else the window's first month
    assert start("2027-05", TODAY, []) == "2027-05"  # an empty window: current_month

    # in the popup: current_month outside the window opens on today's month
    doc = copy.deepcopy(feed_doc)
    doc["current_month"] = "2027-05"
    raw = json.dumps(doc, separators=(",", ":")).encode()
    ext.seed({FEED: feed_record(raw), CHECK: _fresh_check()})
    page = ext.popup()
    assert _text(page, "#currentMonthLabel") == "OCTOBER 2026"
    assert _cards(page) == 30
    assert ext.page_errors == []
