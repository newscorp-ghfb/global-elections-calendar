"""lib/links.js and the links of both renderers (Plan 5b-2 Task 3; P142, R52)."""

import json
import time
from typing import Any, Final
from urllib.parse import urlsplit

from playwright.sync_api import Page

from elections_calendar.model import SOURCE_NAMES
from tests.support.extension import Ext, feed_record, fresh_v1_doc, js

LINKS: Final = "lib/links.js"
FEED: Final = "elections_cache_v2"
CHECK: Final = "check_state_v2"
WIKI: Final = "https://en.wikipedia.org/"
EVIL: Final = "<img src=x onerror=alert(1)>"

# §12.6's table, in the spec's order.
HOSTS: Final = {
    "electionguide": ["electionguide.org"],
    "wikipedia": ["en.wikipedia.org"],
    "ndi": ["ndi.org"],
    "osce": ["odihr.osce.org", "osce.org"],
    "ipu": ["data.ipu.org"],
    "aweb": ["aweb.org"],
    "eisa": ["eisa.org"],
    "carter": ["cartercenter.org"],
    "eeas": ["eeas.europa.eu"],
}
HOMES: Final = {
    "electionguide": "https://www.electionguide.org/",
    "wikipedia": "https://en.wikipedia.org/",
    "ndi": "https://www.ndi.org/",
    "osce": "https://odihr.osce.org/",
    "ipu": "https://data.ipu.org/",
    "aweb": "https://www.aweb.org/",
    "eisa": "https://www.eisa.org/",
    "carter": "https://www.cartercenter.org/",
    "eeas": "https://www.eeas.europa.eu/",
}


def _safe(lab: Page, source: Any, url: Any) -> Any:
    return js(lab, LINKS, "safeLink", source, url)


def test_safe_links(lab: Page) -> None:
    keep = "https://en.wikipedia.org/wiki/X"
    same = [
        ("Wikipedia", keep, keep),
        ("wikipedia", keep, keep),
        ("Wikipedia", "https://EN.WIKIPEDIA.ORG/wiki/X", keep),
        ("NDI", "https://ndi.org/a", "https://ndi.org/a"),
        ("NDI", "https://www.ndi.org/a", "https://www.ndi.org/a"),
        ("OSCE/ODIHR", "https://www.osce.org/x", "https://www.osce.org/x"),
        ("Wikipedia", "https://en.wikipedia.org:443/x", "https://en.wikipedia.org/x"),
    ]
    for source, url, want in same:
        assert _safe(lab, source, url) == want, (source, url)
    hostile: list[Any] = [
        "javascript:alert(1)",
        "data:text/html,x",
        "http://en.wikipedia.org/",
        "https://u:p@en.wikipedia.org/",
        "https://en.wikipedia.org:8443/",
        "https://en.wikipedia.org.evil.example/",
        "https://evilwikipedia.org/",
        "https://de.wikipedia.org/",
        "https://xen.wikipedia.org/",
        "https://xn--wkipedia-c6a.org/",
        "",
        "/wiki/X",
        None,
        42,
    ]
    for url in hostile:
        assert _safe(lab, "Wikipedia", url) == WIKI, url
    assert _safe(lab, "Wikipedia", ["https://en.wikipedia.org/x"]) == WIKI
    assert _safe(lab, "NDI", "https://evilndi.org/a") == "https://www.ndi.org/"
    assert _safe(lab, "Unknown", "https://example.org/") is None
    assert _safe(lab, "constructor", "https://example.org/") is None
    assert _safe(lab, None, "https://en.wikipedia.org/") is None
    for key, page in HOMES.items():
        assert _safe(lab, key, page) == page, key
        assert _safe(lab, SOURCE_NAMES[key], "javascript:1") == page, key


def test_links_match_the_producers_sources(lab: Page) -> None:
    rows = lab.evaluate('async () => (await import("/lib/links.js")).SOURCES')
    assert {r["key"]: r["name"] for r in rows} == SOURCE_NAMES
    assert {r["key"]: r["hosts"] for r in rows} == HOSTS
    assert {r["key"]: r["home"] for r in rows} == HOMES
    for key, name in SOURCE_NAMES.items():
        found = js(lab, LINKS, "sourceOf", name)
        assert found is not None and found["key"] == key
        assert js(lab, LINKS, "sourceOf", key) == found
        assert js(lab, LINKS, "sourceName", key) == name
    assert js(lab, LINKS, "sourceOf", "Unknown") is None
    assert js(lab, LINKS, "sourceName", "Unknown") == "Unknown"


def _seed_v1(ext: Ext, edit: Any = None) -> Page:
    doc = fresh_v1_doc()
    if edit is not None:
        edit(doc)
    feed = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    ext.seed({FEED: feed_record(feed, fmt="legacy"), CHECK: _fresh_check()})
    return ext.popup()


def _fresh_check() -> dict[str, Any]:
    return {"ok_at": int(time.time() * 1000), "failed_at": None, "error": None}


def _sources(card: dict[str, Any], *sources: tuple[str, str]) -> None:
    """The card's sources, with the two lists the v1 checks keep in step with them."""
    card["sources"] = [{"name": n, "link": u} for n, u in sources]
    card["source_names"] = [n for n, _ in sources]
    card["links"] = [u for _, u in sources]


def _october(doc: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = doc["months"]["2026-10"]
    return cards


def test_legacy_opens_only_safe_links(ext: Ext) -> None:
    def edit(doc: dict[str, Any]) -> None:
        first, second = _october(doc)[0], _october(doc)[1]
        first["country"], first["type"] = "Alpha", "Hostile"
        _sources(first, ("Wikipedia", "javascript:alert(1)"))
        second["country"], second["type"] = "Beta", "Strange"
        _sources(second, ("Unknown", "https://example.org/"))

    page = _seed_v1(ext, edit)
    # an off-allowlist A-WEB link (Taiwan, November) opens the A-WEB home page
    page.click("#nextMonthBtn")
    premise = [
        s["link"]
        for c in fresh_v1_doc()["months"]["2026-11"]
        if c["country"] == "Taiwan"
        for s in c["sources"]
    ]
    assert [urlsplit(u).hostname for u in premise] == ["focustaiwan.tw"]
    taiwan = page.locator(".election-item").filter(has=page.get_by_text("Taiwan", exact=True))
    assert taiwan.count() == 1
    assert ext.opened(lambda: taiwan.locator(".source-chip-link").click()) == ["https://www.aweb.org/"]
    page.click("#prevMonthBtn")

    hostile = page.locator(".election-item", has_text="Alpha")
    assert ext.opened(lambda: hostile.locator(".source-chip-link").click()) == [WIKI]
    assert ext.opened(lambda: hostile.locator(".election-link-icon").click()) == [WIKI]
    assert ext.opened(lambda: hostile.locator(".election-country").click()) == [WIKI]

    # an unknown source: plain chip, no Open control, nothing opens
    strange = page.locator(".election-item", has_text="Beta")
    chip = strange.locator(".chip-source")
    assert chip.count() == 1 and chip.evaluate("e => e.tagName") == "SPAN"
    assert chip.get_attribute("class") == "chip chip-source"
    assert chip.get_attribute("title") is None
    assert strange.locator(".election-link-icon").count() == 0
    assert ext.opened(lambda: chip.click()) == []
    assert ext.opened(lambda: strange.locator(".election-country").click()) == []
    assert ext.page_errors == []


def test_legacy_text_is_inserted_as_text(ext: Ext) -> None:
    def edit(doc: dict[str, Any]) -> None:
        card = _october(doc)[0]
        card["country"] = card["type"] = EVIL
        _sources(card, (EVIL, "https://example.org/"))

    page = _seed_v1(ext, edit)
    item = page.locator(".election-item").first
    assert item.locator(".election-country").text_content() == EVIL
    assert item.locator(".election-type").text_content() == EVIL
    assert item.locator(".chip-source").text_content() == EVIL
    assert page.locator("#electionList img").count() == 0
    assert ext.page_errors == []
