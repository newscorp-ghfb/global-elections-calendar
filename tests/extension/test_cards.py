"""lib/details.js and the v2 card disclosure (Plan 5b-2 Task 4; P143, R22, R25, R47)."""

import copy
import json
import time
from datetime import UTC, datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Locator, Page

from tests.support.extension import Ext, artifact_pair, feed_record, js

DETAILS: Final = "lib/details.js"
LINKS: Final = "lib/links.js"
FEED: Final = "elections_cache_v2"
CHECK: Final = "check_state_v2"
EVIL: Final = "<img src=x onerror=alert(1)>"
WIKI: Final = "https://en.wikipedia.org/"

CAPE_VERDE: Final = "eae5cc187a1a"
SWEDEN: Final = "451e4f4c0054"
SWEDEN_CARD: Final = "fcd48da30f32"
NIGERIA_PRESIDENCY: Final = "d00397654a28"
NIGERIA_HOUSE: Final = "dd48097e3357"
NIGERIA_SENATE: Final = "fcd8572f383a"
SOUTH_SUDAN_PRESIDENCY: Final = "512ac66dc2b0"
SOUTH_SUDAN_ASSEMBLY: Final = "31ce89602954"
SOUTH_SUDAN_COUNCIL: Final = "6f60dcabc9d2"
CAMEROON_DECEMBER: Final = "00d51e66e43c"
CAMEROON_JANUARY: Final = "1e0beadfb091"
KYRGYZSTAN: Final = "7e0ee894e09f"
BRAZIL_BIG: Final = "c8c9844ab7a8"  # 18 governors, one Wikipedia umbrella
BRAZIL_SMALL: Final = "54b356d5b5ea"  # 3 children, NDI and A-WEB umbrellas

_DETAILS_JS: Final = """async ([doc, childId]) => {
  const d = await import('/lib/details.js');
  const index = d.childIndex(doc);
  const { card, child } = index.get(childId);
  return d.childDetails(card, child, { index });
}"""

_DETAILS_ALL_JS: Final = """async ([doc, cardId]) => {
  const d = await import('/lib/details.js');
  const index = d.childIndex(doc);
  const card = [...index.values()].find((e) => e.card.group_id === cardId).card;
  return card.children.map((child) => d.childDetails(card, child, { index }));
}"""


@pytest.fixture(scope="module")
def pair() -> tuple[bytes, bytes]:
    return artifact_pair()


@pytest.fixture
def doc(pair: tuple[bytes, bytes]) -> dict[str, Any]:
    out: dict[str, Any] = json.loads(pair[0])
    return out


def _cards(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for bucket in doc["months"].values() for c in bucket]


def _find(doc: dict[str, Any], child_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for card in _cards(doc):
        for child in card["children"]:
            if child["child_id"] == child_id:
                return card, child
    raise AssertionError(child_id)


def _card(doc: dict[str, Any], group_id: str) -> dict[str, Any]:
    return next(c for c in _cards(doc) if c["group_id"] == group_id)


def _details(lab: Page, doc: dict[str, Any], child_id: str) -> dict[str, Any]:
    got: dict[str, Any] = lab.evaluate(_DETAILS_JS, [doc, child_id])
    return got


def _lines(entry: dict[str, Any]) -> list[str]:
    out: list[str] = [s["text"] for s in entry["sources"]]
    return out


def _umbrella_names(entry: dict[str, Any]) -> list[str]:
    out: list[str] = [u["name"] for u in entry["umbrellas"]]
    return out


def _safe(lab: Page, name: str, url: str) -> Any:
    return js(lab, LINKS, "safeLink", name, url)


# ── the pure rules (details.js) ───────────────────────────────────────────────


def test_umbrella_shown_per_child(lab: Page, doc: dict[str, Any]) -> None:
    presidency = _details(lab, doc, SOUTH_SUDAN_PRESIDENCY)
    assert _umbrella_names(presidency) == ["NDI", "A-WEB"]
    for child_id in (SOUTH_SUDAN_ASSEMBLY, SOUTH_SUDAN_COUNCIL):
        assert _umbrella_names(_details(lab, doc, child_id)) == ["NDI", "A-WEB", "EISA"]
    eisa = _details(lab, doc, SOUTH_SUDAN_ASSEMBLY)["umbrellas"][2]
    assert eisa["text"] == "Also listed by EISA: National Legislative Assembly, 22 December 2026"
    assert eisa["link"] == _safe(lab, "EISA", "https://www.eisa.org/election-calendar/")
    # a card with no umbrellas has none to show
    assert _details(lab, doc, SWEDEN)["umbrellas"] == []


def test_possible_matches_and_umbrellas_are_labelled(lab: Page, doc: dict[str, Any]) -> None:
    assert _details(lab, doc, CAMEROON_DECEMBER)["possible"] == [
        "Provisional: may be the same contest as Cameroon National Assembly, January 2027"
    ]
    assert _details(lab, doc, KYRGYZSTAN)["possible"] == [
        "Provisional: may be the same contest as Kyrgyzstan Kyrgyz Presidency, 27 January 2027"
    ]
    assert _details(lab, doc, SWEDEN)["possible"] == []

    edited = copy.deepcopy(doc)
    _, sweden = _find(edited, SWEDEN)
    sweden["possible_matches_outside"] = 1
    assert _details(lab, edited, SWEDEN)["possible"] == [
        "Provisional: 1 possible match outside the monitored window"
    ]
    sweden["possible_matches_outside"] = 3
    assert _details(lab, edited, SWEDEN)["possible"] == [
        "Provisional: 3 possible matches outside the monitored window"
    ]
    sweden["possible_matches"] = ["ffffffffffff"]  # not in the feed: no line
    sweden["possible_matches_outside"] = 0
    assert _details(lab, edited, SWEDEN)["possible"] == []
    # a match, then the outside count
    _, december = _find(edited, CAMEROON_DECEMBER)
    december["possible_matches_outside"] = 2
    assert _details(lab, edited, CAMEROON_DECEMBER)["possible"] == [
        "Provisional: may be the same contest as Cameroon National Assembly, January 2027",
        "Provisional: 2 possible matches outside the monitored window",
    ]
    # a year-precision match names the year only
    _card(edited, "5e8a2c4b7ad7")["date_precision"] = "year"
    assert _details(lab, edited, CAMEROON_DECEMBER)["possible"][0] == (
        "Provisional: may be the same contest as Cameroon National Assembly, 2027"
    )

    # Brazil has two cards on 2026-10-04: each umbrella shows on its own card's children only
    small = lab.evaluate(_DETAILS_ALL_JS, [doc, BRAZIL_SMALL])
    assert len(small) == 3
    assert all(_umbrella_names(e) == ["NDI", "A-WEB"] for e in small)
    big = lab.evaluate(_DETAILS_ALL_JS, [doc, BRAZIL_BIG])
    assert len(big) == 18
    for entry in big:
        assert _umbrella_names(entry) == ["Wikipedia"]
        assert entry["umbrellas"][0]["text"] == "Also listed by Wikipedia: Governors, 4 October"


def test_per_source_dates_for_date_conflicts(lab: Page, doc: dict[str, Any]) -> None:
    cape = _details(lab, doc, CAPE_VERDE)
    assert _lines(cape) == [
        "ElectionGuide: 2026-11-15 (d) to 2026-11-15 (d) (used)",
        "Wikipedia: 15 November",
        "NDI: November 15, 2026 (ALL DAY)",
        "EISA: October 2026",
    ]
    ipu = "IPU: 28 Feb 2027 · expected renewal, not an announced date"
    for child_id in (NIGERIA_HOUSE, NIGERIA_SENATE):
        nigeria = _details(lab, doc, child_id)
        assert _lines(nigeria) == [
            "ElectionGuide: 2027-01-16 (d) to 2027-01-16 (d) (used)",
            "Wikipedia: 16 January",
            ipu,
        ]
    # the Presidency has no IPU source
    presidency = _details(lab, doc, NIGERIA_PRESIDENCY)
    assert _lines(presidency) == [
        "ElectionGuide: 2027-01-16 (d) to 2027-01-16 (d) (used)",
        "Wikipedia: 16 January",
    ]
    for entry, child_id in ((cape, CAPE_VERDE), (presidency, NIGERIA_PRESIDENCY)):
        _, child = _find(doc, child_id)
        assert [s["name"] for s in entry["sources"]] == [s["name"] for s in child["sources"]]
        for line, src in zip(entry["sources"], child["sources"], strict=True):
            assert line["link"] == _safe(lab, src["name"], src["link"])


def test_source_lines_say_who_claims_what(lab: Page, doc: dict[str, Any]) -> None:
    assert _lines(_details(lab, doc, SWEDEN)) == [
        "ElectionGuide: 2026-09-13 (d) to 2026-09-13 (d) (used) · reports it held",
        "OSCE/ODIHR: 13 Sep 2026",
        "Wikipedia: 13 September",
    ]

    # the same date, a different claim
    edited = copy.deepcopy(doc)
    _, cape = _find(edited, CAPE_VERDE)
    cape["status_conflict"] = True
    wiki, ndi = cape["sources"][1], cape["sources"][2]
    wiki["date_text"] = ndi["date_text"] = "15 November 2026"
    ndi["status_claim"] = "postponed"
    first = _lines(_details(lab, edited, CAPE_VERDE))
    assert first[1:3] == ["Wikipedia: 15 November 2026", "NDI: 15 November 2026 · reports it postponed"]
    ndi["status_claim"], wiki["status_claim"] = None, "postponed"
    second = _lines(_details(lab, edited, CAPE_VERDE))
    assert second[1:3] == [
        "Wikipedia: 15 November 2026 · reports it postponed",
        "NDI: 15 November 2026",
    ]
    assert first != second

    # saved data beside fresh
    wiki["status_claim"] = None
    wiki["date_text"] = "15 November"
    wiki["fallback"] = True
    wiki["fetched_at"] = "2026-10-01T12:00:00Z"
    assert _lines(_details(lab, edited, CAPE_VERDE))[1] == (
        "Wikipedia: 15 November · saved data from 1 Oct 2026"
    )
    wiki["fetched_at"] = None
    assert _lines(_details(lab, edited, CAPE_VERDE))[1] == (
        "Wikipedia: 15 November · saved data, date unknown"
    )

    # observation
    _, sweden = _find(edited, SWEDEN)
    sweden["sources"][1]["evidence_kind"] = "observation"
    assert _lines(_details(lab, edited, SWEDEN))[1] == (
        "OSCE/ODIHR: 13 Sep 2026 · observation mission dates"
    )

    # several tags, in order
    several = copy.deepcopy(sweden["sources"][1])
    several.update(
        name="Wikipedia",
        date_text="13 September",
        status_claim="cancelled",
        fallback=True,
        fetched_at="2026-10-19T12:00:00Z",
        provisional=True,
        evidence_kind="calendar",
    )
    assert js(lab, DETAILS, "sourceLine", several) == (
        "Wikipedia: 13 September · reports it cancelled · saved data from 19 Oct 2026"
        " · Newer data from an incomplete fetch on 19 Oct 2026"
    )

    # every claim and every kind of evidence has its own tag
    plain = copy.deepcopy(sweden["sources"][1])
    plain.update(name="NDI", date_text="D", evidence_kind="calendar", status_claim=None)
    assert js(lab, DETAILS, "sourceLine", plain) == "NDI: D"
    for claim in ("held", "postponed", "cancelled", "disputed"):
        line = js(lab, DETAILS, "sourceLine", {**plain, "status_claim": claim})
        assert line == f"NDI: D · reports it {claim}"
    for kind, tag in (
        ("expected_renewal", "expected renewal, not an announced date"),
        ("observation", "observation mission dates"),
        ("umbrella", "a listing covering several contests"),
    ):
        assert js(lab, DETAILS, "sourceLine", {**plain, "evidence_kind": kind}) == f"NDI: D · {tag}"
    selected = js(lab, DETAILS, "sourceLine", {**plain, "selected": True, "status_claim": "held"})
    assert selected == "NDI: D (used) · reports it held"

    # ordinary sources stay plain
    assert _lines(_details(lab, doc, CAPE_VERDE)) == [
        "ElectionGuide: 2026-11-15 (d) to 2026-11-15 (d) (used)",
        "Wikipedia: 15 November",
        "NDI: November 15, 2026 (ALL DAY)",
        "EISA: October 2026",
    ]


def test_headings_follow_the_rule(lab: Page, doc: dict[str, Any]) -> None:
    edited = copy.deepcopy(doc)
    _, sweden = _find(edited, SWEDEN)

    def heading(**fields: Any) -> str:
        sweden.update(office_label="Swedish Parliament", jurisdiction=None, round=None, indirect=False)
        sweden.update(fields)
        got: str = _details(lab, edited, SWEDEN)["heading"]
        return got

    assert heading() == "Swedish Parliament"
    assert heading(jurisdiction="Stockholm") == "Swedish Parliament · Stockholm"
    assert heading(jurisdiction="PARLIAMENT") == "Swedish Parliament"  # contained, any case
    assert heading(round=2) == "Swedish Parliament · Round 2"
    assert heading(indirect=True) == "Swedish Parliament · Indirect"
    assert heading(jurisdiction="Skane", round=1, indirect=True) == (
        "Swedish Parliament · Skane · Round 1 · Indirect"
    )


# ── the card disclosure in the popup ──────────────────────────────────────────


def _fresh_check() -> dict[str, Any]:
    return {"ok_at": int(time.time() * 1000), "failed_at": None, "error": None}


def _seed(ext: Ext, doc: dict[str, Any], *, now: str | None = None) -> Page:
    raw = json.dumps(doc, separators=(",", ":")).encode()
    ext.seed({FEED: feed_record(raw), CHECK: _fresh_check()})
    return ext.popup() if now is None else ext.popup(now=now)


def _search(page: Page, value: str) -> None:
    if page.locator("#filterBar").is_hidden():
        page.click("#filterToggle")
    page.fill("#searchInput", value)


def _item(page: Page, group_id: str) -> Locator:
    return page.locator(f'.election-item[data-group-id="{group_id}"]')


def _face(item: Locator) -> dict[str, Any]:
    return {
        "text": item.locator(".election-info > .card-label").text_content(),
        "chips": item.locator(".election-info .chip").all_text_contents(),
        "notes": item.locator(".election-info .card-notes > li").all_text_contents(),
    }


def _entry_view(entry: Locator) -> dict[str, Any]:
    return {
        "text": entry.locator(".child-label .child-label-text").text_content(),
        "chips": entry.locator(".child-label .chip").all_text_contents(),
        "notes": entry.locator(".child-label .child-notes > li").all_text_contents(),
    }


def test_cards_expand_on_demand(ext: Ext, pair: tuple[bytes, bytes], doc: dict[str, Any]) -> None:
    feed, status = pair
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    page = ext.popup()
    assert page.locator(".child-entry").count() == 0
    assert page.locator(".card-toggle").count() == 30
    brazil = _item(page, BRAZIL_BIG)
    toggle = brazil.locator("button.card-toggle")
    assert toggle.text_content() == "Show details"
    assert toggle.get_attribute("aria-expanded") == "false"
    assert toggle.get_attribute("aria-controls") == f"details-{BRAZIL_BIG}"

    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "true"
    assert toggle.text_content() == "Hide details"
    details = brazil.locator(f"div.card-details#details-{BRAZIL_BIG}")
    assert details.is_visible()
    assert brazil.locator(".child-entry").count() == 18
    assert page.locator(".child-entry").count() == 18  # no other card built its entries

    # a search keeping one child (the word is a jurisdiction: search reads it)
    _search(page, "Alagoas")
    assert brazil.locator(".card-match").text_content() == "1 matching of 18"
    assert brazil.locator(".child-entry").count() == 1
    assert brazil.locator(".child-heading").text_content() == "Governor · Alagoas"
    _search(page, "")
    assert brazil.locator(".child-entry").count() == 18
    assert toggle.get_attribute("aria-expanded") == "true"

    toggle.click()
    assert toggle.get_attribute("aria-expanded") == "false"
    assert toggle.text_content() == "Show details"
    assert brazil.locator(".child-entry").count() == 0
    assert details.is_hidden()

    toggle.focus()
    page.keyboard.press("Enter")
    assert toggle.get_attribute("aria-expanded") == "true"
    assert brazil.locator(".child-entry").count() == 18

    # the face shows each chip once, however many children carry it
    for item in page.locator(".election-item-v2").all():
        chips = item.locator(".election-info .chip").all_text_contents()
        assert len(chips) == len(set(chips))
    big = _card(doc, BRAZIL_BIG)
    assert big["level"] == "subnational" and len(big["children"]) == 18
    assert brazil.locator(".election-info .chip-subnational").count() == 1
    assert ext.page_errors == []


def _synthetic(doc: dict[str, Any], tag: str, country: str, **fields: Any) -> dict[str, Any]:
    """A one-child October card with its own ids and country, in doc's October bucket."""
    card: dict[str, Any] = copy.deepcopy(doc["months"]["2026-10"][0])
    card["children"] = card["children"][:1]
    card.update(
        group_id=tag + "0" * 6, country=country, status="Upcoming", level="national",
        date="2026-10-26", end_date="2026-10-26", date_precision="day",
        date_meaning="voting_period", date_status="confirmed", umbrellas=[], umbrella_sources=[],
    )
    child = card["children"][0]
    child.update(
        child_id=tag + "1" * 6, occurrence_confirmed=False, status_conflict=False,
        date_conflict=False, possible_matches=[], possible_matches_outside=0,
        rescheduled_from=[], provisional_date=None,
    )
    child["sources"] = child["sources"][:1]
    child["sources"][0].update(selected=True, fallback=False, provisional=False, status_claim=None)
    card.update(fields)
    doc["months"]["2026-10"].append(card)
    return card


def _lab_label(page: Page, doc: dict[str, Any], group_id: str, now: str) -> dict[str, Any]:
    card = _card(doc, group_id)
    got: dict[str, Any] = page.evaluate(
        """async ([card, now]) => {
          const { childLabel } = await import('/lib/labels.js');
          const { localToday } = await import('/lib/dates.js');
          const ms = new Date(now).getTime();
          return childLabel(card, card.children[0], { today: localToday(ms), now: ms });
        }""",
        [card, now],
    )
    return got


def _expected(label: dict[str, Any]) -> dict[str, Any]:
    return {
        "text": label["text"],
        "chips": [c["text"] for c in label["chips"]],
        "notes": label["notes"],
    }


def test_expanded_labels_match_the_card_face(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    clock = "2026-10-19T14:00:00Z"
    week_ms = 7 * 86400 * 1000
    p_ms = int(datetime(2026, 10, 19, 14, tzinfo=UTC).timestamp() * 1000)

    def stamp(ms: int) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms / 1000))

    # (a) the week boundary
    doc: dict[str, Any] = json.loads(pair[0])
    inside = _synthetic(doc, "a1a1a1", "Zzyzx Inside")
    outside = _synthetic(doc, "b2b2b2", "Zzyzx Outside")
    for card, fetched in ((inside, p_ms - week_ms + 60_000), (outside, p_ms - week_ms - 60_000)):
        card["children"][0]["sources"][0].update(fallback=True, fetched_at=stamp(fetched))
    page = _seed(ext, doc, now=clock)
    seen = []
    for card in (inside, outside):
        item = _item(page, card["group_id"])
        item.locator("button.card-toggle").click()
        face = _face(item)
        entry = _entry_view(item.locator(".child-entry"))
        assert entry == face
        assert entry == _expected(_lab_label(page, doc, card["group_id"], clock))
        seen.append(face["notes"][0].split(" ")[0])
    assert seen == ["Using", "Unverified"]

    # (c) a change of view that keeps the card: the open entry still matches its face
    _search(page, "Zzyzx Inside")
    page.click("#tabUpcoming")
    item = _item(page, inside["group_id"])
    assert item.locator(".child-entry").count() == 1
    assert _entry_view(item.locator(".child-entry")) == _face(item)
    assert _face(item) == _expected(_lab_label(page, doc, inside["group_id"], clock))
    assert ext.page_errors == []
    page.close()

    # (b) the local date: a day card dated today, with the clock at 23:59 local
    late = "2026-10-19T23:59:00"
    doc = json.loads(pair[0])
    today_card = _synthetic(
        doc, "c3c3c3", "Zzyzx Today", date="2026-10-19", end_date="2026-10-19"
    )
    page = _seed(ext, doc, now=late)
    item = _item(page, today_card["group_id"])
    item.locator("button.card-toggle").click()
    face = _face(item)
    assert face["text"] == "Scheduled voting period: today (approx.)"
    assert _entry_view(item.locator(".child-entry")) == face
    assert face == _expected(_lab_label(page, doc, today_card["group_id"], late))
    assert ext.page_errors == []


def test_source_entries_open_only_safe_links(
    ext: Ext, pair: tuple[bytes, bytes], doc: dict[str, Any]
) -> None:
    sweden_doc = copy.deepcopy(doc)
    _, sweden = _find(sweden_doc, SWEDEN)
    sweden["sources"][2]["link"] = "javascript:alert(1)"
    sweden["sources"][1]["name"] = "Evil"
    ndi = _card(sweden_doc, BRAZIL_SMALL)["umbrellas"][0]
    ndi["link"] = "javascript:alert(2)"
    headings = [c["office_label"] + " · " + c["jurisdiction"] for c in _card(doc, BRAZIL_BIG)["children"]]
    assert len(set(headings)) == 18  # the distinct-names row below depends on it

    page = _seed(ext, sweden_doc)
    page.click("#prevMonthBtn")  # September
    card = _item(page, SWEDEN_CARD)
    card.locator("button.card-toggle").click()
    entry = card.locator(f'.child-entry[data-child-id="{SWEDEN}"]')

    def open_named(name: str) -> Locator:
        found = entry.get_by_role("button", name=name, exact=True)
        assert found.count() == 1, name
        return found

    guide = open_named("Open ElectionGuide for Swedish Parliament (new tab)")
    assert ext.opened(lambda: guide.click()) == ["https://www.electionguide.org/elections/id/5079/"]
    wiki = open_named("Open Wikipedia for Swedish Parliament (new tab)")
    assert ext.opened(lambda: wiki.click()) == [WIKI]
    # a source we do not know: its line stays, with no Open control
    lines = entry.locator(".source-line")
    assert lines.count() == 3
    evil = lines.filter(has_text="Evil: 13 Sep 2026")
    assert evil.count() == 1 and evil.locator(".source-open").count() == 0
    assert entry.locator(".source-open").count() == 2

    # the card body opens nothing (ruling 30)
    assert ext.opened(lambda: card.locator(".election-country").click()) == []
    assert ext.opened(lambda: card.locator(".child-heading").click()) == []

    # an umbrella's Open goes through safeLink too
    page.click("#nextMonthBtn")
    small = _item(page, BRAZIL_SMALL)
    small.locator("button.card-toggle").click()
    presidency = small.locator('.child-entry[data-child-id="baa1bb5de7fe"]')
    button = presidency.get_by_role(
        "button",
        name="Open NDI (2026 Brazil General Elections) for Brazilian Presidency · Round 1 (new tab)",
        exact=True,
    )
    assert ext.opened(lambda: button.click()) == ["https://www.ndi.org/"]
    a_web = presidency.get_by_role(
        "button",
        name="Open A-WEB (2026 General Elections (first round)) for Brazilian Presidency · Round 1 (new tab)",
        exact=True,
    )
    assert ext.opened(lambda: a_web.click()) == [
        "https://www.aweb.org/eng/bbs/B0000007/list.do?menuNo=300052&option=all"
    ]

    # one umbrella over 18 children: 18 different button names
    big = _item(page, BRAZIL_BIG)
    big.locator("button.card-toggle").click()
    names = big.locator(".umbrella-open").evaluate_all("els => els.map(e => e.getAttribute('aria-label'))")
    assert len(names) == 18 and len(set(names)) == 18
    assert all(n.startswith("Open Wikipedia (Governors) for Governor") for n in names)
    assert ext.page_errors == []


def test_card_details_text_is_inserted_as_text(ext: Ext, doc: dict[str, Any]) -> None:
    edited = copy.deepcopy(doc)
    card = _card(edited, BRAZIL_SMALL)
    child = card["children"][0]
    child["office_label"] = "<b>OFFICE</b>"
    child["jurisdiction"] = "<i>JURISDICTION</i>"
    child["round"] = None
    child["sources"][0]["date_text"] = "<u>DATE</u>"
    child["sources"][0]["name"] = EVIL
    card["umbrellas"][0]["office_label"] = "<s>UMBRELLA</s>"
    page = _seed(ext, edited)
    item = _item(page, BRAZIL_SMALL)
    item.locator("button.card-toggle").click()
    entry = item.locator(f'.child-entry[data-child-id="{child["child_id"]}"]')
    assert entry.locator(".child-heading").text_content() == (
        "<b>OFFICE</b> · <i>JURISDICTION</i>"
    )
    assert (entry.locator(".source-line").first.text_content() or "").startswith(f"{EVIL}: <u>DATE</u>")
    assert "<s>UMBRELLA</s>" in (entry.locator(".umbrella-line").first.text_content() or "")
    for tag in ("b", "i", "u", "s", "img"):
        assert item.locator(f".card-details {tag}").count() == 0, tag
    assert page.locator("#electionList img").count() == 0
    assert ext.page_errors == []
