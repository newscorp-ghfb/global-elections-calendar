"""The attention and undated section (Plan 5b-2 Task 5; P144, S5-T10, S5-T11, R50)."""

import copy
import json
import time
from datetime import date
from typing import Any, Final

import pytest
from playwright.sync_api import Locator, Page

from elections_calendar.model import SOURCE_NAMES
from tests.support.extension import (
    ROOT,
    Ext,
    artifact_pair,
    feed_record,
    fresh_v1_feed,
    js,
    status_record,
    synthetic_feed,
)

FEED: Final = "elections_cache_v2"
CHECK: Final = "check_state_v2"
STATUS: Final = "status_cache"
WINDOW: Final = "across the monitored window (Sep–Jan)"
EVIL: Final = "<img src=x onerror=alert(1)>"
WIKI: Final = "https://en.wikipedia.org/"
SAO_TOME: Final = "612356b9548b"
LESOTHO: Final = "c86ebcffe28b"
PERU_ITEM: Final = "36ad1dcad007"
CUT_NOTE: Final = (
    'This data includes 500 of the 1700 items. The other 1200 are in attention_full.json, in the '
    '"generation" artifact of the GitHub Actions run that published it (kept 14 days). '
    "Searches here do not cover them."
)
MONTHS: Final = ("January", "February", "March", "April", "May", "June", "July", "August",
                 "September", "October", "November", "December")


@pytest.fixture(scope="module")
def pair() -> tuple[bytes, bytes]:
    return artifact_pair()


@pytest.fixture
def doc(pair: tuple[bytes, bytes]) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(pair[0])
    return out


def _dump(doc: Any) -> bytes:
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def _fresh_check() -> dict[str, Any]:
    return {"ok_at": int(time.time() * 1000), "failed_at": None, "error": None}


def _seed(ext: Ext, feed: bytes, status: bytes | None = None, *, fmt: str = "v2") -> Page:
    values: dict[str, Any] = {FEED: feed_record(feed, fmt=fmt), CHECK: _fresh_check()}
    if status is not None:
        values[STATUS] = status_record(status)
    ext.seed(values)
    return ext.popup()


def _reads_as_v2(lab: Page, feed: bytes) -> None:
    schema = json.loads((ROOT / "schemas" / "feed-v2.schema.json").read_text(encoding="utf-8"))
    got = js(lab, "lib/validate.js", "feedFormat", json.loads(feed), schema)
    assert got["format"] == "v2", got["problems"][:3]


def _text(page: Page, selector: str) -> str:
    return page.locator(selector).text_content() or ""


def _search(page: Page, value: str) -> None:
    if page.locator("#filterBar").is_hidden():
        page.click("#filterToggle")
    page.fill("#searchInput", value)


def _open_section(page: Page) -> None:
    if page.locator("#attentionToggle").get_attribute("aria-expanded") != "true":
        page.click("#attentionToggle")


def _rows(page: Page) -> Locator:
    return page.locator("#attentionList > li.attention-row")


def _row_view(row: Locator) -> dict[str, Any]:
    return {
        "text": row.locator(".attention-text").text_content(),
        "source": row.locator(".attention-source").text_content(),
        "undated": row.locator(".attention-undated").all_text_contents(),
        "possible": row.locator(".possible-line").all_text_contents(),
        "open": row.locator("button.attention-open").count(),
    }


def _name(source: str) -> str:
    return SOURCE_NAMES.get(source, source)


def _matches(doc: dict[str, Any], needle: str) -> int:
    """How many included items P144's search finds: text, source name, listing country, office."""
    listings = {u["undated_id"]: u for u in doc["undated"]}
    count = 0
    for item in doc["attention_items"]:
        fields = [item["text"], _name(item["source"])]
        listing = listings.get(item["undated_id"])
        if listing is not None:
            fields += [listing["country"], listing["office_label"]]
        if any(needle.lower() in f.lower() for f in fields):
            count += 1
    return count


def _day_month_year(day: str) -> str:
    d = date.fromisoformat(day)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def _child(doc: dict[str, Any], child_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for cards in doc["months"].values():
        for card in cards:
            for child in card["children"]:
                if child["child_id"] == child_id:
                    return card, child
    raise AssertionError(child_id)


def _twenty(doc: dict[str, Any]) -> dict[str, Any]:
    """The artifact with 20 items: the three named ones, then others by item_id; feed order kept."""
    items = doc["attention_items"]
    must = {SAO_TOME, LESOTHO, PERU_ITEM}
    others = sorted((i for i in items if i["item_id"] not in must), key=lambda i: i["item_id"])
    keep = must | {i["item_id"] for i in others[:17]}
    out = copy.deepcopy(doc)
    out["attention_items"] = [i for i in items if i["item_id"] in keep]
    assert len(out["attention_items"]) == 20
    return out


def test_attention_items_are_listed(ext: Ext, lab: Page, doc: dict[str, Any]) -> None:
    edited = _twenty(doc)
    feed = _dump(edited)
    _reads_as_v2(lab, feed)
    page = _seed(ext, feed)
    items = {i["item_id"]: i for i in edited["attention_items"]}
    listing = next(u for u in doc["undated"] if u["undated_id"] == items[LESOTHO]["undated_id"])

    assert _text(page, "#attentionToggle") == f"20 items {WINDOW}"
    assert page.locator("#attentionToggle").get_attribute("aria-expanded") == "false"
    _open_section(page)
    rows = _rows(page)
    assert rows.count() == 20
    assert [_row_view(rows.nth(n))["text"] for n in range(20)] == [
        i["text"] for i in edited["attention_items"]
    ]
    assert [_row_view(rows.nth(n))["source"] for n in range(20)] == [
        _name(i["source"]) for i in edited["attention_items"]
    ]

    def row_of(item_id: str) -> Locator:
        position = [i["item_id"] for i in edited["attention_items"]].index(item_id)
        return rows.nth(position)

    card, child = _child(doc, "2b76c271e7be")
    sao = _row_view(row_of(SAO_TOME))
    assert sao["source"] == "EEAS"
    assert sao["possible"] == [
        "Provisional: may be the same contest as "
        f"{card['country']} {child['office_label']}, {_day_month_year(card['date'])}",
        "Provisional: 1 possible match outside the monitored window",
    ]
    assert sao["undated"] == []
    assert _row_view(row_of(LESOTHO))["undated"] == [
        f"Undated: {listing['country']}, {listing['office_label']}, {listing['year']}"
    ]
    assert _row_view(row_of(LESOTHO))["undated"] == ["Undated: Lesotho, Parliament, 2027"]
    assert _row_view(row_of(PERU_ITEM))["possible"] == [
        "Provisional: 4 possible matches outside the monitored window"
    ]
    wikipedia = [i for i in edited["attention_items"] if i["source"] == "wikipedia" and i["item_id"] != LESOTHO]
    for item in wikipedia[:2]:
        view = _row_view(row_of(item["item_id"]))
        assert view["text"] == item["text"] and view["source"] == "Wikipedia"
        assert view["possible"] == [] and view["undated"] == []
        button = row_of(item["item_id"]).locator("button.attention-open")
        assert ext.opened(button.click) == [item["link"]]
    assert ext.page_errors == []


def _first_month(page: Page) -> None:
    while page.locator("#prevMonthBtn").evaluate("e => e.style.visibility") != "hidden":
        page.click("#prevMonthBtn")


def test_attention_section_is_always_reachable(
    ext: Ext, pair: tuple[bytes, bytes], doc: dict[str, Any]
) -> None:
    feed, status = pair
    page = _seed(ext, feed, status)
    toggle = page.locator("#attentionToggle")
    page.click("#filterToggle")
    _first_month(page)
    seen = 0
    for _month in range(5):
        for tab in ("#tabUpcoming", "#tabPast", "#tabAll"):
            page.click(tab)
            for level in ("all", "national", "subnational"):
                page.select_option("#levelFilter", level)
                assert toggle.is_visible()
                assert _text(page, "#attentionToggle") == f"157 items {WINDOW}"
                seen += 1
        if page.locator("#nextMonthBtn").evaluate("e => e.style.visibility") != "hidden":
            page.click("#nextMonthBtn")
    assert seen == 45

    # the section's count sits beside the records counter and never changes it
    page.select_option("#levelFilter", "all")
    before = _text(page, "#recordCount")
    page.click("#attentionToggle")
    assert page.locator("#attentionList").is_visible()
    assert _text(page, "#recordCount") == before and "item" not in before
    page.click("#attentionToggle")

    # a search matching no card: the empty state sits below the section, which stays
    needle = "Lesotho"
    k = _matches(doc, needle)
    assert k > 0
    _search(page, needle)
    assert page.locator("#stateEmpty").is_visible()
    assert toggle.is_visible()
    assert _text(page, "#attentionToggle") == f"{k} of 157 items {WINDOW}"
    attention_box = page.locator("#attention").bounding_box()
    empty_box = page.locator("#stateEmpty").bounding_box()
    assert attention_box is not None and empty_box is not None
    assert attention_box["y"] + attention_box["height"] <= empty_box["y"]
    # nothing was cut: no note, and no "in this data" wording
    assert page.locator("#attentionNote").is_hidden() and _text(page, "#attentionNote") == ""
    assert "in this data" not in _text(page, "#attention")
    _search(page, "")

    # pins matching nothing
    ext.seed({"pins_migrated_v2": True, "pinned_places_v2": ["iso:ZZ"], "unresolved_pins_v2": []})
    pinned = ext.popup()
    assert pinned.locator("#stateEmpty").is_visible()
    assert _text(pinned, "#attentionToggle") == f"157 items {WINDOW}"
    ext.seed({"pinned_places_v2": []})

    assert ext.page_errors == []


def test_attention_section_is_hidden_without_data_or_for_legacy(ext: Ext) -> None:
    ext.served.set("elections.json", fresh_v1_feed())
    page = ext.popup()
    assert page.evaluate("document.body.dataset.renderer") == "legacy"
    assert page.locator("#attention").is_hidden()
    assert page.locator("#attentionToggle").is_hidden()
    assert page.locator("#attentionList > li").count() == 0
    ext.reset()
    ext.served.set("elections.json", b"{not json")
    empty = ext.popup()
    assert empty.locator("#stateError").is_visible()
    assert empty.locator("#attention").is_hidden()
    assert ext.page_errors == []


_VIEW_JS: Final = """async ([doc, query]) => {
  const d = await import('/lib/details.js');
  const a = await import('/lib/attention.js');
  const index = d.childIndex(doc);
  const full = a.attentionView(doc, { query, index, withRows: true });
  const bare = a.attentionView(doc, { query, index: null, withRows: false });
  return { full: { title: full.title, note: full.note, rows: full.rows.length },
           bare: { title: bare.title, note: bare.note, rows: bare.rows } };
}"""

_COUNT_URL_PARSES: Final = """(() => {
  const Real = window.URL;
  window.__itemParses = 0;
  window.URL = new Proxy(Real, {
    construct(target, args) {
      if (args[0] === 'https://en.wikipedia.org/wiki/Synthetic') window.__itemParses += 1;
      return Reflect.construct(target, args);
    },
  });
})();"""


def test_a_collapsed_view_counts_without_rows(lab: Page, doc: dict[str, Any]) -> None:
    edited = copy.deepcopy(doc)
    listing = copy.deepcopy(edited["undated"][0])
    listing.update(undated_id="cccccccccccc", country="Zorbland", office_label="Quuxoffice", year=2028)
    edited["undated"].append(listing)
    edited["attention_items"][0].update(undated_id="cccccccccccc", text="Alpha item")
    matched = edited["attention_items"][1]["text"].split()[0]
    for query in ("", matched, "no such text anywhere", "zorb", "QUUX"):
        got = lab.evaluate(_VIEW_JS, [edited, query])
        assert got["bare"]["rows"] is None, query
        assert got["bare"]["title"] == got["full"]["title"], query
        assert got["bare"]["note"] == got["full"]["note"], query
    some = lab.evaluate(_VIEW_JS, [edited, matched])["full"]["rows"]
    assert 0 < some < len(edited["attention_items"])  # the query matches some items, not all
    assert lab.evaluate(_VIEW_JS, [edited, "zorb"])["full"]["rows"] == 1
    assert lab.evaluate(_VIEW_JS, [edited, "no such text anywhere"])["full"]["rows"] == 0
    assert lab.evaluate(_VIEW_JS, [edited, ""])["full"]["rows"] == len(edited["attention_items"])


def test_a_collapsed_section_parses_no_item_links(
    ext: Ext, lab: Page, pair: tuple[bytes, bytes]
) -> None:
    feed = synthetic_feed(pair[0], items=500)
    _reads_as_v2(lab, feed)
    ext.seed({FEED: feed_record(feed), CHECK: _fresh_check()})
    page = ext.popup(init_script=_COUNT_URL_PARSES)
    assert page.locator("#attentionToggle").get_attribute("aria-expanded") == "false"
    assert page.evaluate("window.__itemParses") == 0  # the first paint
    _search(page, "Synthetic item 1")
    assert " of " in _text(page, "#attentionToggle")  # the title counts the matches
    assert page.evaluate("window.__itemParses") == 0
    page.click("#nextMonthBtn")
    assert page.evaluate("window.__itemParses") == 0
    page.click("#attentionToggle")
    assert page.evaluate("window.__itemParses") > 0  # control: the wrapper sees the parses
    assert ext.page_errors == []


def test_attention_rendering_is_bounded(ext: Ext, lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed = synthetic_feed(pair[0], items=500, truncated=1200)
    _reads_as_v2(lab, feed)
    page = _seed(ext, feed)
    toggle_text = "1700 items across the monitored window (Sep–Jan)"
    assert _text(page, "#attentionToggle") == toggle_text
    assert page.locator("#attentionNote").is_visible()
    assert _text(page, "#attentionNote") == CUT_NOTE
    assert page.locator("#attentionList > li").count() == 0  # nothing is built while collapsed

    page.click("#attentionToggle")
    assert page.locator("#attentionNote").is_visible()
    assert _rows(page).count() == 200
    assert _text(page, "#attentionShown") == "Showing 200 of 500"
    assert _text(page, "#attentionMore") == "Show 200 more"
    page.click("#attentionMore")
    assert _rows(page).count() == 400
    assert _text(page, "#attentionShown") == "Showing 400 of 500"
    assert _text(page, "#attentionMore") == "Show 100 more"
    page.click("#attentionMore")
    assert _rows(page).count() == 500
    assert page.locator("#attentionMore").is_hidden()
    assert page.locator("#attentionShown").is_hidden()
    assert _text(page, "#attentionToggle") == toggle_text
    assert ext.page_errors == []


def test_a_search_over_cut_items_says_what_it_searched(
    ext: Ext, lab: Page, pair: tuple[bytes, bytes], doc: dict[str, Any]
) -> None:
    edited = json.loads(synthetic_feed(pair[0], items=500, truncated=1200))
    edited["attention_items"][0]["text"] = "Lesotho: Parliament (2027), date not given"
    for n, item in enumerate(edited["attention_items"][1:251]):
        item["text"] = f"Peru {n}: Lima mission"
    feed = _dump(edited)
    _reads_as_v2(lab, feed)
    page = _seed(ext, feed)
    toggle = "#attentionToggle"

    # a word only the cut items could hold: the empty state, and the section stays
    _search(page, "Zanzibarland")
    assert _text(page, toggle) == "0 of the 500 items in this data match (1700 in total, Sep–Jan)"
    assert page.locator("#stateEmpty").is_visible()
    assert page.locator(toggle).is_visible()
    assert page.locator("#attentionNote").is_visible()
    assert _text(page, "#attentionNote") == CUT_NOTE
    assert page.locator("#attentionList > li").count() == 0

    _search(page, "Lesotho")
    assert _text(page, toggle) == "1 of the 500 items in this data match (1700 in total, Sep–Jan)"
    assert _text(page, "#attentionNote") == CUT_NOTE
    _open_section(page)
    assert _rows(page).count() == 1
    assert page.locator("#attentionShown").is_hidden()
    assert page.locator("#attentionMore").is_hidden()

    _search(page, "Peru")
    assert _text(page, toggle) == "250 of the 500 items in this data match (1700 in total, Sep–Jan)"
    assert _rows(page).count() == 200
    assert _text(page, "#attentionShown") == "Showing 200 of 250"
    assert _text(page, "#attentionMore") == "Show 50 more"
    page.click("#attentionMore")
    assert _rows(page).count() == 250
    assert page.locator("#attentionShown").is_hidden()
    assert page.locator("#attentionMore").is_hidden()

    # a changed search starts again at 200
    _search(page, "Lima")
    assert _rows(page).count() == 200
    assert _text(page, "#attentionShown") == "Showing 200 of 250"

    # nothing cut: "k of N", and no note
    plain = _seed(ext, _dump(doc))
    k = _matches(doc, "Lesotho")
    _search(plain, "Lesotho")
    assert _text(plain, toggle) == f"{k} of 157 items {WINDOW}"
    assert plain.locator("#attentionNote").is_hidden()
    assert ext.page_errors == []


def test_attention_links_are_safe(ext: Ext, lab: Page, doc: dict[str, Any]) -> None:
    edited = copy.deepcopy(doc)
    model = edited["attention_items"][0]
    long_text = "L" * 60 + "M" * 60
    hostile = {**model, "item_id": "aaaaaaaaaaaa", "source": "wikipedia", "link": "javascript:x",
               "text": long_text, "possible_matches": [], "possible_matches_outside": 0,
               "undated_id": None}
    unknown = {**model, "item_id": "bbbbbbbbbbbb", "source": "nope",
               "link": "https://en.wikipedia.org/wiki/X", "text": "Nobody's item",
               "possible_matches": [], "possible_matches_outside": 0, "undated_id": None}
    edited["attention_items"] = [hostile, unknown]
    feed = _dump(edited)
    _reads_as_v2(lab, feed)
    page = _seed(ext, feed)
    _open_section(page)
    rows = _rows(page)
    assert rows.count() == 2
    button = rows.nth(0).locator("button.attention-open")
    assert button.get_attribute("aria-label") == f"Open Wikipedia: {'L' * 60}{'M' * 20} (new tab)"
    assert ext.opened(button.click) == [WIKI]
    assert rows.nth(1).locator("button").count() == 0
    view = _row_view(rows.nth(1))
    assert view["text"] == "Nobody's item" and view["source"] == "nope"
    assert ext.page_errors == []


def test_attention_text_is_inserted_as_text(ext: Ext, lab: Page, doc: dict[str, Any]) -> None:
    edited = copy.deepcopy(doc)
    model = edited["attention_items"][0]
    listing = copy.deepcopy(edited["undated"][0])
    listing.update(undated_id="cccccccccccc", country="<b>C</b>", office_label="<i>O</i>", year=2027)
    edited["undated"].append(listing)
    first = {**model, "item_id": "aaaaaaaaaaaa", "source": "wikipedia", "text": EVIL,
             "possible_matches": [], "possible_matches_outside": 0, "undated_id": "cccccccccccc"}
    second = {**first, "item_id": "bbbbbbbbbbbb", "source": "<u>SRC</u>", "text": "<s>TEXT</s>",
              "undated_id": None}
    edited["attention_items"] = [first, second]
    feed = _dump(edited)
    _reads_as_v2(lab, feed)
    page = _seed(ext, feed)
    _open_section(page)
    rows = _rows(page)
    assert rows.count() == 2
    one, two = _row_view(rows.nth(0)), _row_view(rows.nth(1))
    assert one["text"] == EVIL
    assert one["undated"] == ["Undated: <b>C</b>, <i>O</i>, 2027"]
    assert two["text"] == "<s>TEXT</s>" and two["source"] == "<u>SRC</u>"
    for tag in ("img", "b", "i", "s", "u"):
        assert page.locator(f"#attention {tag}").count() == 0, tag
    assert ext.page_errors == []


def test_synthetic_feed_is_schema_valid(lab: Page, pair: tuple[bytes, bytes]) -> None:
    from jsonschema import Draft202012Validator

    schema = json.loads((ROOT / "schemas" / "feed-v2.schema.json").read_text(encoding="utf-8"))
    base = json.loads(pair[0])
    grown_bytes = synthetic_feed(pair[0], cards=3, children=40, items=500, truncated=7)
    grown = json.loads(grown_bytes)
    _reads_as_v2(lab, grown_bytes)  # the extension's own checks, with cards and children grown
    assert list(Draft202012Validator(schema).iter_errors(grown)) == []
    assert len(grown_bytes) < 4_000_000
    assert len(grown["months"]["2026-10"]) == len(base["months"]["2026-10"]) + 4
    assert len(grown["months"]["2026-10"][-1]["children"]) == 40
    assert len(grown["attention_items"]) == 500 and grown["attention_truncated"] == 7
    ids = [c["group_id"] for b in grown["months"].values() for c in b]
    ids += [k["child_id"] for b in grown["months"].values() for c in b for k in c["children"]]
    ids += [i["item_id"] for i in grown["attention_items"]]
    assert len(ids) == len(set(ids))
    assert json.loads(synthetic_feed(pair[0]))["attention_items"] == base["attention_items"]


def test_attention_search_reads_the_fields_a_reader_sees(
    ext: Ext, lab: Page, doc: dict[str, Any]
) -> None:
    edited = copy.deepcopy(doc)
    model = edited["attention_items"][0]
    listing = copy.deepcopy(edited["undated"][0])
    listing.update(undated_id="cccccccccccc", country="Zorbland", office_label="Quuxoffice", year=2028)
    edited["undated"].append(listing)
    first = {**model, "item_id": "aaaaaaaaaaaa", "source": "wikipedia", "text": "Alpha item",
             "possible_matches": [], "possible_matches_outside": 0, "undated_id": "cccccccccccc"}
    second = {**first, "item_id": "bbbbbbbbbbbb", "source": "eeas", "text": "Beta item",
              "undated_id": None}
    third = {**first, "item_id": "dddddddddddd", "source": "osce", "text": "Gamma item",
             "undated_id": None}
    edited["attention_items"] = [first, second, third]
    feed = _dump(edited)
    _reads_as_v2(lab, feed)
    page = _seed(ext, feed)
    _open_section(page)
    expect = {  # search -> the texts of the rows it keeps
        "zorb": ["Alpha item"],
        "QUUX": ["Alpha item"],
        "eeas": ["Beta item"],
        "wikipedia": ["Alpha item"],
        "beta": ["Beta item"],
        "ODIHR": ["Gamma item"],  # in the display name "OSCE/ODIHR", not in the key "osce"
        " item ": ["Alpha item", "Beta item", "Gamma item"],
        "": ["Alpha item", "Beta item", "Gamma item"],
        "nothing": [],
    }
    for term, texts in expect.items():
        _search(page, term)
        assert _rows(page).locator(".attention-text").all_text_contents() == texts, term
    # tabs and levels never filter the section
    _search(page, "beta")
    page.select_option("#levelFilter", "subnational")
    page.click("#tabPast")
    assert _rows(page).locator(".attention-text").all_text_contents() == ["Beta item"]
    page.click("#tabUpcoming")
    page.select_option("#levelFilter", "national")
    assert _rows(page).locator(".attention-text").all_text_contents() == ["Beta item"]
    assert ext.page_errors == []


def test_attention_title_forms(lab: Page) -> None:
    def title(k: int | None, included: int, total: int, months: list[str]) -> str:
        got: str = js(lab, "lib/attention.js", "attentionTitle",
                      {"k": k, "included": included, "total": total, "months": months})
        return got

    window = ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01"]
    assert title(None, 157, 157, window) == f"157 items {WINDOW}"
    assert title(None, 5, 5, ["2026-10"]) == "5 items across the monitored window (Oct)"
    assert title(None, 1, 1, ["2026-10"]) == "1 item across the monitored window (Oct)"
    assert title(None, 3, 3, []) == "3 items across the monitored window"
    assert title(None, 0, 0, ["2026-10"]) == "0 items across the monitored window (Oct)"
    assert title(1, 1, 1, ["2026-10"]) == "1 of 1 item across the monitored window (Oct)"
    assert title(2, 157, 157, window) == f"2 of 157 items {WINDOW}"
    assert title(1, 1, 3, []) == "1 of the 1 item in this data match (3 in total)"
    assert title(0, 500, 1700, ["2026-10"]) == (
        "0 of the 500 items in this data match (1700 in total, Oct)"
    )
    assert title(7, 500, 1700, window) == "7 of the 500 items in this data match (1700 in total, Sep–Jan)"
    assert js(lab, "lib/attention.js", "truncationNote", {"included": 5, "total": 5}) == ""
    assert js(lab, "lib/attention.js", "shownLine", 5, 5) == ""
    assert js(lab, "lib/attention.js", "shownLine", 0, 0) == ""
    assert js(lab, "lib/attention.js", "shownLine", 200, 500) == "Showing 200 of 500"


def test_an_update_needed_feed_hides_the_section(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    page = _seed(ext, feed, status)
    _open_section(page)
    assert _rows(page).count() > 0
    unknown = json.loads(feed)
    unknown["schema_version"] = 3
    ext.seed({FEED: feed_record(_dump(unknown), fmt="update_needed"), CHECK: _fresh_check()})
    page.click("#refreshBtn")
    page.wait_for_function(
        "() => document.body.dataset.state === 'ready' && document.body.dataset.checking === 'false'"
    )
    assert page.evaluate("document.body.dataset.renderer") == "legacy"
    assert page.locator("#bannerText").text_content() == "This data is newer than this extension — update the extension"
    assert page.locator("#attention").is_hidden()
    assert page.locator("#attentionList").evaluate("e => e.children.length") == 0
    assert ext.page_errors == []
