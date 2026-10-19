import re
from collections import Counter
from datetime import UTC, date, datetime
from typing import Any

import pytest
from bs4 import BeautifulSoup

from elections_calendar.fetch import Deadline
from elections_calendar.ledger import COUNT_RULES, CardBlocksRule, check, discover
from elections_calendar.model import Claim, DateSpan, Reason
from elections_calendar.sources import ndi
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.sources.ndi import URL, Ndi, expected, request
from elections_calendar.text import collapse_ws
from elections_calendar.window import Window, window_for
from tests.support.fixtures import fixture
from tests.support.pages import Served, raw_pages, result

_: Adapter = Ndi()

DAY = "2026-10-19"
WINDOW = window_for(datetime(2026, 10, 19, tzinfo=UTC))
REGISTRIES = Registries.load()
BODIES = {n: fixture("ndi", f"p{n}.html", DAY) for n in range(5)}
SERVED = {request(n).url: BODIES[n] for n in range(5)}
RAW = RawPages("ndi", tuple(Ndi().fetch(WINDOW, Served(SERVED), Deadline.after(60))), ())
RES = Ndi().parse(RAW, WINDOW, REGISTRIES)
D25 = "October 25, 2026 (ALL DAY)"


def card(title: str, date: str, types: str = "General", location: str | None = None) -> str:
    loc = f' data-location="{location}"' if location is not None else ""
    return (
        '<div class="partial -election -feed"><div class="text"><div class="left">'
        f'<h3 class="heading">\n<span>{title}</span>\n</h3>'
        f'<div class="date-type">\n<div class="date">{date}</div><span>|</span>'
        f"     {types}\n            </div>"
        '</div><div class="add-to-cal-button">'
        f'<button class="add-to-cal" data-contactname="NDI" data-end="x" data-name="{title}"'
        f' data-start="x"{loc} tabindex="0">Add</button>'
        '<div class="cal-dropdown"></div></div></div></div>'
    )


def pager(active: int, has_next: bool) -> str:
    items = (
        f'<li class="pager__item is-active"><a href="?page={active}" title="Current page">'
        f"{active + 1}</a></li>"
    )
    if has_next:
        items += (
            '<li class="pager__item pager__item--next">'
            f'<a href="?page={active + 1}" rel="next">Next</a></li>'
        )
    return f'<nav class="pager" role="navigation"><ul class="pager__items">{items}</ul></nav>'


def block(block_id: str, cards: list[str] | None, active: int | None, has_next: bool) -> str:
    inner = (
        f'<div class="election-wrapper">{"".join(cards)}</div>'
        if cards is not None
        else "<p>No Results Found</p>"
    )
    nav = pager(active, has_next) if active is not None else ""
    return (
        f'<div class="tab_panel" id="{block_id}"><div class="js-view-dom-id-1"><form></form>'
        f'<div class="bound boundwide">{inner}{nav}</div></div></div>'
    )


def ndi_page(
    up: list[str] | None,
    past: list[str] | None,
    *,
    up_page: int | None = 0,
    past_page: int | None = 0,
    up_next: bool = False,
    past_next: bool = False,
) -> bytes:
    return (
        "<!DOCTYPE html><html><body><main>"
        + block("upcoming-elections", up, up_page, up_next)
        + block("past-elections", past, past_page, past_next)
        + "</main></body></html>"
    ).encode()


PAST = [card("2026 Morocco Parliamentary Election", "September 23, 2026 (ALL DAY)", "Parliamentary")]
BULGARIA = card("2026 Bulgaria Parliamentary Elections", D25, "Parliamentary", "Bulgaria")
HUNGARY = card("2026 Hungary Parliamentary Elections", "April 12, 2026 (ALL DAY)", "Parliamentary")


def raw_of(bodies: dict[int, bytes], *, status: int = 200) -> RawPages:
    return raw_pages("ndi", [(request(n), result(b, status=status)) for n, b in sorted(bodies.items())])


def parse(raw: RawPages, window: Window = WINDOW, *, balanced: bool = True) -> ParseResult:
    res = Ndi().parse(raw, window, REGISTRIES)
    if balanced:
        assert check(raw, res).ok
    return res


def page0(body: bytes, *, balanced: bool = True) -> ParseResult:
    return parse(raw_of({0: body}), balanced=balanced)


def cards_of(res: ParseResult, which: str = "upcoming") -> list[Claim]:
    return [c for c in res.claims if f"/{which}-" in c.unit_id]


def units_of(res: ParseResult, which: str = "upcoming") -> list[Any]:
    return [u for u in res.units if f"/{which}-" in u.unit_id]


def one(*cards: str) -> ParseResult:
    return page0(ndi_page(list(cards), PAST))


def detail(res: ParseResult, key: str = "p0") -> tuple[str, str]:
    cov = next(c for c in res.coverage if c.key == key)
    return cov.outcome, cov.detail


def test_fixture_ledger_balances() -> None:
    report = check(RAW, RES)
    assert report.ok and RES.reasons == ()
    assert report.outcomes == {"parsed": 37, "partial": 1, "unparsed": 0, "ignored": 0}
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in RES.coverage] == [
        ("p0", "ok", 20, None),
        ("p1", "ok", 18, None),
    ]
    assert len(RES.claims) == 38


def test_fixture_values() -> None:
    C = RES.claims
    assert Counter(c.level for c in C) == {"national": 33, "subnational": 4, "unknown": 1}
    assert Counter(c.office_class for c in C) == {
        "legislature": 14,
        "general": 13,
        "head_of_state": 7,
        "local_council": 2,
        "governor": 2,
    }
    assert Counter(c.span.precision for c in C) == {"day": 26, "month": 11, "year": 1}
    assert Counter(c.date_status for c in C) == {"unknown": 28, "tentative": 10}
    assert Counter(c.date_meaning for c in C) == {"voting_period": 26, "unknown": 12}
    assert {c.link for c in C} == {URL} and {c.status_claim for c in C} == {None}
    assert Counter(u.relevance for u in RES.units) == {"in_or_after_window": 24, "unknown": 14}
    assert [(c.claim_id, c.jurisdiction) for c in C if c.jurisdiction] == [
        ("ndi:p0/past-c6#0", "BARMM"),
        ("ndi:p0/past-c8#0", "Osun"),
        ("ndi:p0/past-c10#0", "Ekiti"),
    ]
    assert [(c.claim_id, c.round) for c in C if c.round] == [("ndi:p1/past-c2#0", 2)]
    assert [(u.unit_id, u.reason) for u in RES.units if u.outcome != "parsed"] == [
        ("ndi:p0/past-c6", "level_unresolved")
    ]


def test_in_window_claims() -> None:
    assert sorted(
        (str(c.span.start), c.place_id, c.office_class, c.level, c.span.precision)
        for c in RES.claims
        if WINDOW.overlaps(c.span)
    ) == [
        ("2026-09-14", "iso:PH", "legislature", "unknown", "day"),
        ("2026-09-23", "iso:MA", "legislature", "national", "day"),
        ("2026-09-27", "iso:ST", "legislature", "national", "day"),
        ("2026-10-01", "iso:RS", "legislature", "national", "month"),
        ("2026-10-04", "iso:BA", "general", "national", "day"),
        ("2026-10-04", "iso:BR", "general", "national", "day"),
        ("2026-10-04", "iso:PE", "local_council", "subnational", "day"),
        ("2026-10-25", "iso:BG", "legislature", "national", "day"),
        ("2026-11-02", "iso:PH", "local_council", "subnational", "day"),
        ("2026-11-15", "iso:CV", "head_of_state", "national", "day"),
        ("2026-12-05", "iso:GM", "head_of_state", "national", "day"),
        ("2026-12-22", "iso:SS", "general", "national", "day"),
        ("2027-01-16", "iso:NG", "general", "national", "day"),
        ("2027-01-24", "iso:KG", "head_of_state", "national", "day"),
    ]


def test_claims_field_by_field() -> None:
    C = {c.claim_id: c for c in RES.claims}
    U = {u.unit_id: u for u in RES.units}
    bg = C["ndi:p0/upcoming-c1#0"]
    assert (bg.place_raw, bg.place_id) == ("Bulgaria", "iso:BG")
    assert (bg.institution, bg.office_class, bg.level) == (
        "iso:BG/national-assembly",
        "legislature",
        "national",
    )
    assert bg.span == DateSpan.day(date(2026, 10, 25))
    assert (bg.date_meaning, bg.date_status) == ("voting_period", "unknown")
    assert bg.date_text == "October 25, 2026 (ALL DAY)"
    assert bg.office_label == "2026 Bulgaria Parliamentary Elections"
    assert U["ndi:p0/upcoming-c1"].text == (
        "2026 Bulgaria Parliamentary Elections | October 25, 2026 (ALL DAY) | Parliamentary"
        " | Bulgaria"
    )
    serbia = C["ndi:p0/upcoming-c2#0"]
    assert serbia.span == DateSpan.month(2026, 10)
    assert (serbia.date_status, serbia.date_meaning) == ("tentative", "unknown")
    haiti = C["ndi:p0/upcoming-c7#0"]
    assert haiti.span == DateSpan.of_year(2026) and haiti.date_status == "tentative"
    assert haiti.office_class == "general" and haiti.aggregate
    salvador = C["ndi:p0/upcoming-c10#0"]
    assert salvador.span == DateSpan.month(2027, 2) and salvador.date_status == "unknown"
    assert C["ndi:p0/upcoming-c5#0"].place_raw == "The Gambia"
    bske = C["ndi:p0/upcoming-c3#0"]
    assert (bske.office_class, bske.level, bske.aggregate) == ("local_council", "subnational", True)
    bosnia = C["ndi:p0/past-c3#0"]
    assert (bosnia.place_raw, bosnia.place_id) == ("Bosnia and Herzegovina", "iso:BA")
    assert U["ndi:p0/past-c3"].outcome == "parsed"
    assert U["ndi:p0/past-c3"].text == (
        "2026 Bosnia and Herzegovina General Elections | October 04, 2026 (ALL DAY) | General"
        " | Bosnia-Herzegovina"
    )
    barmm = C["ndi:p0/past-c6#0"]
    assert (barmm.place_id, barmm.office_class, barmm.level) == ("iso:PH", "legislature", "unknown")
    assert (barmm.jurisdiction, barmm.jurisdiction_kind) == ("BARMM", "subdivision")
    osun = C["ndi:p0/past-c8#0"]
    assert (osun.office_class, osun.level, osun.jurisdiction, osun.place_raw) == (
        "governor",
        "subnational",
        "Osun",
        "Nigeria",
    )
    peru = C["ndi:p1/past-c2#0"]
    assert peru.round == 2 and peru.span == DateSpan.month(2026, 6)
    assert peru.date_status == "tentative"


def window_run(day: datetime, served: dict[str, bytes]) -> tuple[Window, RawPages, ParseResult, Served]:
    w = window_for(day)
    assert Ndi().requests(w) == (request(0),)
    getter = Served(served)
    raw = RawPages("ndi", tuple(Ndi().fetch(w, getter, Deadline.after(60))), ())
    return w, raw, parse(raw, w), getter


@pytest.mark.parametrize(
    ("day", "asked", "cov", "reasons", "units", "claims"),
    [
        (datetime(2026, 10, 19, tzinfo=UTC), 2, [20, 18], (), 38, 38),
        (datetime(2026, 5, 15, tzinfo=UTC), 3, [20, 18, 10], (), 48, 48),
        (datetime(2026, 1, 20, tzinfo=UTC), 4, [20, 18, 10, 10], (), 58, 58),
        (datetime(2025, 12, 20, tzinfo=UTC), 5, [20, 18, 10, 10, 10], (), 68, 67),
    ],
)
def test_chain_by_window(
    day: datetime, asked: int, cov: list[int], reasons: tuple[Reason, ...], units: int, claims: int
) -> None:
    _w, raw, res, getter = window_run(day, SERVED)
    assert getter.asked == [request(n).url for n in range(asked)]
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [
        (f"p{n}", "ok", seen) for n, seen in enumerate(cov)
    ]
    assert res.reasons == reasons and (len(res.units), len(res.claims)) == (units, claims)


def test_chain_ends_the_window_c06() -> None:
    _w, raw, res, _g = window_run(datetime(2025, 12, 20, tzinfo=UTC), SERVED)
    assert Counter(u.outcome for u in res.units) == {"parsed": 66, "partial": 1, "unparsed": 1}
    bad = next(u for u in res.units if u.outcome == "unparsed")
    assert (bad.unit_id, bad.reason, bad.relevance) == (
        "ndi:p4/past-c7",
        "date_unparsed",
        "in_or_after_window",
    )
    assert bad.leftover == "September 03, 2025 4:00 AM - December 03, 2025 5:00 AM EDT"
    partial = next(u for u in res.units if u.outcome == "partial")
    assert (partial.unit_id, partial.reason) == ("ndi:p0/past-c6", "level_unresolved")


def test_chain_with_a_missing_page() -> None:
    served = {k: v for k, v in SERVED.items() if k != request(3).url}
    _w, raw, res, _g = window_run(datetime(2026, 1, 20, tzinfo=UTC), served)
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [
        ("p0", "ok", 20),
        ("p1", "ok", 18),
        ("p2", "ok", 10),
        ("p3", "http_error", 0),
    ]
    assert res.reasons == (Reason("http_error", "p3"),)
    assert (len(res.units), len(res.claims)) == (48, 48)


def cut_pagers(body: bytes, keep: int | None = None) -> bytes:
    text = body.decode()
    navs = list(re.finditer(r'<nav class="pager".*?</nav>', text, re.S))
    assert len(navs) == 2
    for i, m in reversed(list(enumerate(navs))):
        if i != keep:
            text = text[: m.start()] + text[m.end() :]
    return text.encode()


def expect_layout(body: bytes, message: str, counted: int | None = None) -> None:
    res = page0(body)
    assert detail(res) == ("layout_not_recognised", message)
    assert res.units == () and res.claims == ()
    raw = raw_of({0: body})
    assert expected(WINDOW, raw.pages) == (request(0),)
    assert res.notes == ()
    if counted is not None:
        assert len(discover(COUNT_RULES['ndi'], body) or ()) == counted


def test_pagination_failures_are_loud() -> None:
    p0 = BODIES[0]
    expect_layout(cut_pagers(p0), "upcoming block has 10 cards and no pager", 20)
    expect_layout(cut_pagers(p0, keep=1), "upcoming block has 10 cards and no pager", 20)
    expect_layout(cut_pagers(p0, keep=0), "past block has 10 cards and no pager", 20)
    expect_layout(
        p0.replace(b'rel="next"', b'rel="x"', 1), "upcoming block has later pages but no next link"
    )
    eleven = [card(f"2026 Kenya General Elections {i}", f"November {10 + i:02d}, 2026 (ALL DAY)", "General", "Kenya") for i in range(11)]
    big = ndi_page(eleven, PAST, up_page=None)
    res = page0(big, balanced=False)
    assert detail(res) == ("layout_not_recognised", "upcoming block has 11 cards and no pager")
    assert len(discover(COUNT_RULES['ndi'], big) or ()) == 12
    nine = ndi_page(eleven[:9], PAST, up_page=None)
    raw = raw_of({0: nine})
    res = parse(raw)
    assert (res.coverage[0].outcome, res.coverage[0].units_seen, res.notes) == ("ok", 10, ())
    assert expected(WINDOW, raw.pages) == (request(0),)


def test_pagination_incomplete_and_unfinished() -> None:
    res = parse(raw_of({0: BODIES[0]}))
    assert res.notes == (Reason("pagination_incomplete", "p1 was not fetched"),)
    raw = raw_pages(
        "ndi",
        [
            (request(0), result(BODIES[0])),
            (request(1), result(b"", outcome="timeout", status=None)),
        ],
    )
    res = parse(raw)
    assert [(c.key, c.outcome) for c in res.coverage] == [("p0", "ok"), ("p1", "timeout")]
    assert res.notes == ()
    raw = RawPages("ndi", (), (request(0),))
    res = parse(raw)
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [("p0", "unfinished", 0)]
    assert res.notes == ()


def test_chain_page_checks() -> None:
    res = parse(raw_of({0: BODIES[0], 1: BODIES[0]}))
    assert detail(res, "p1") == ("layout_not_recognised", "upcoming block is page 0 with 10 cards")
    p0 = ndi_page([BULGARIA], PAST, up_next=True)
    repeat = ndi_page(None, PAST, up_page=0, past_page=1)
    res = parse(raw_of({0: p0, 1: repeat}))
    assert detail(res, "p1") == ("layout_not_recognised", "past block repeats p0")
    serbia = card("2026 Serbia Parliamentary Elections", "October 01, 2026 (ALL DAY)", "Parliamentary")
    p1 = ndi_page([serbia], [HUNGARY], up_page=1, past_page=1)
    res = parse(raw_of({0: p0, 1: p1}))
    assert detail(res, "p1") == (
        "layout_not_recognised",
        "upcoming block is not in date order after p0",
    )
    peru = card("2026 Peru General Election", "October 04, 2026 (ALL DAY)", "General")
    kenya = card("2027 Kenya General Elections", "November 01, 2026 (ALL DAY)", "General")
    p1 = ndi_page([kenya], [peru], up_page=1, past_page=1)
    res = parse(raw_of({0: p0, 1: p1}))
    assert detail(res, "p1") == (
        "layout_not_recognised",
        "past block is not in date order after p0",
    )
    assert res.units and all(not u.unit_id.startswith("ndi:p1") for u in res.units)


def test_a_card_shifted_between_pages_is_a_duplicate() -> None:
    p0 = ndi_page([BULGARIA], PAST, up_next=True)
    shifted = ndi_page([BULGARIA, card("2026 Serbia Parliamentary Elections", "November 01, 2026 (ALL DAY)", "Parliamentary")], [HUNGARY], up_page=1, past_page=1)
    res = parse(raw_of({0: p0, 1: shifted}))
    assert detail(res, "p1")[0] == "ok"
    first = units_of(res)[1]
    assert first.unit_id == "ndi:p1/upcoming-c1"
    assert (first.outcome, first.reason, first.duplicate_of) == (
        "ignored",
        "duplicate",
        "ndi:p0/upcoming-c1",
    )


def test_the_chain_stops_at_the_cap() -> None:
    pages = {
        n: ndi_page(
            [card(f"2027 Kenya General Elections {n}", f"August {10 + n:02d}, 2027 (ALL DAY)")],
            [card(f"2026 Peru General Election {n}", f"October {20 - n:02d}, 2026 (ALL DAY)")],
            up_page=n,
            past_page=n,
            up_next=True,
            past_next=True,
        )
        for n in range(10)
    }
    raw = raw_of(pages)
    assert [r.key for r in expected(WINDOW, raw.pages)] == [f"p{n}" for n in range(10)]
    res = parse(raw)
    assert res.notes == (Reason("pagination_incomplete", "stopped at the 10-page cap"),)
    raw9 = raw_of({n: pages[n] for n in range(9)})
    assert parse(raw9).notes == (Reason("pagination_incomplete", "p9 was not fetched"),)


def test_broken_pages_get_an_outcome_never_units() -> None:
    p0 = BODIES[0]
    expect_layout(p0[:200000], "page does not end with </html>")
    expect_layout(
        p0.replace(b'id="upcoming-elections"', b'id="x-elections"'),
        "block #upcoming-elections appears 0 times",
    )
    expect_layout(ndi_page(None, PAST), "upcoming block is page 0 with 0 cards")
    expect_layout(ndi_page([], PAST), "upcoming block is page 0 with 0 cards")
    two = ndi_page([BULGARIA], PAST).replace(
        b'<div class="election-wrapper">',
        b'<div class="election-wrapper"></div><div class="election-wrapper">',
        1,
    )
    expect_layout(two, "upcoming block has 2 card lists")
    extra = pager(0, False).encode()
    expect_layout(
        ndi_page([BULGARIA], PAST).replace(b'<nav class="pager"', extra + b'<nav class="pager"', 1),
        "upcoming block has 2 pagers",
    )
    serbia = card("2026 Serbia Parliamentary Elections", "October 01, 2026 (ALL DAY)", "Parliamentary")
    expect_layout(ndi_page([BULGARIA, serbia], PAST), "upcoming block is not in date order")
    peru = card("2026 Peru General Election", "October 04, 2026 (ALL DAY)", "General")
    expect_layout(ndi_page([BULGARIA], [PAST[0], peru]), "past block is not in date order")
    expect_layout(
        ndi_page([BULGARIA], PAST).replace(b"is-active", b"x", 1),
        "upcoming block has no current page",
    )
    expect_layout(
        ndi_page([BULGARIA], PAST).replace(b'href="?page=0"', 'href="?page=٠"'.encode(), 1),
        "upcoming block has no current page",
    )


def test_two_variants_are_ok() -> None:
    p0 = ndi_page([BULGARIA], PAST, up_next=True)
    clamped = ndi_page(None, [HUNGARY], up_page=0, past_page=1)
    res = parse(raw_of({0: p0, 1: clamped}))
    assert [(c.key, c.outcome) for c in res.coverage] == [("p0", "ok"), ("p1", "ok")]
    res = page0(ndi_page([BULGARIA], PAST, up_page=None, past_page=None))
    assert (res.coverage[0].outcome, len(res.units)) == ("ok", 2)


def test_download_failures_keep_their_own_outcome() -> None:
    raw = raw_pages("ndi", [(request(0), result(BODIES[0], status=302))])
    res = parse(raw)
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [("p0", "http_error", 0)]
    assert res.units == () and res.notes == ()
    assert expected(WINDOW, raw.pages) == (request(0),)


def title_date(title: str, date: str, types: str = "General", location: str | None = None) -> ParseResult:
    return one(card(title, date, types, location))


def test_card_duplicate_on_one_page() -> None:
    res = one(BULGARIA, BULGARIA)
    u = units_of(res)
    assert [(x.outcome, x.reason, x.duplicate_of) for x in u] == [
        ("parsed", None, None),
        ("ignored", "duplicate", "ndi:p0/upcoming-c1"),
    ]
    assert len(cards_of(res)) == 1
    other = card("2026 Bulgaria Parliamentary Elections", D25, "Presidential", "Bulgaria")
    res = one(BULGARIA, other)
    assert [x.outcome for x in units_of(res)] == ["parsed", "parsed"]
    assert [c.office_class for c in cards_of(res)] == ["legislature", "legislature"]


def kind(res: ParseResult) -> tuple[str, str | None, str]:
    (u,) = units_of(res)
    return u.outcome, u.reason, u.leftover


@pytest.mark.parametrize(
    ("title", "date", "types", "location", "want", "claim"),
    [
        ("", D25, "General", None, ("unparsed", "title_missing", ""), None),
        ("2026 Chile General Election", "", "General", None, ("unparsed", "date_missing", ""), None),
        ("2026 Chile General Election", D25, "General", "Peru", ("partial", "place_conflict", "Chile"), "iso:PE"),
        ("2026 Narnia General Election", D25, "General", None, ("unparsed", "place_missing", ""), None),
        ("2026 General Election", D25, "General", "Narnia", ("partial", "place_unregistered", ""), "unknown:narnia"),
        (
            "2026 Jamaica General Election",
            "September 03, 2026 4:00 AM - December 03, 2026 5:00 AM EDT",
            "General",
            None,
            ("unparsed", "date_unparsed", "September 03, 2026 4:00 AM - December 03, 2026 5:00 AM EDT"),
            None,
        ),
        (
            "2026 Chile General Election",
            "Postponed October 25, 2026",
            "General",
            None,
            ("unparsed", "date_unparsed", "Postponed October 25, 2026"),
            None,
        ),
        ("2026 Chile General Election", "TBD", "General", None, ("unparsed", "date_missing", ""), None),
        ("2036 Chile General Election", "October 25, 2036 (ALL DAY)", "General", None, ("unparsed", "implausible_date", ""), None),
        (
            "2026 Chile Attorney General Election",
            D25,
            "Local",
            None,
            ("unparsed", "office_not_modelled", "2026 Chile Attorney General Election"),
            None,
        ),
        ("2026 Chile Senatorial Recall", D25, "Recall", None, ("partial", "type_unrecognised", "Recall"), "upper_house/national"),
        ("2026 Chile Local Elections", D25, "Municipal\n Regional", None, ("parsed", None, ""), "local_council/subnational"),
        ("2026 Chile Elections", D25, "", None, ("partial", "office_unrecognised", ""), "general/unknown"),
        ("2026 Chile Mayor", D25, "Local", None, ("parsed", None, ""), "mayor/subnational"),
    ],
)
def test_card_kinds(
    title: str, date: str, types: str, location: str | None, want: tuple[str, str | None, str], claim: str | None
) -> None:
    res = title_date(title, date, types, location)
    assert kind(res) == want
    got = cards_of(res)
    if claim is None:
        assert got == []
    else:
        (c,) = got
        if "/" in claim:
            assert f"{c.office_class}/{c.level}" == claim
        else:
            assert c.place_id == claim


@pytest.mark.parametrize(
    ("title", "location", "types", "want", "claim"),
    [
        ("2026 Niger and Nigeria Elections", None, "General", ("unparsed", "place_ambiguous", "Niger, Nigeria"), None),
        ("2026 DRC Congo Elections", None, "General", ("unparsed", "place_ambiguous", "DRC, Congo"), None),
        ("2026 Republic of the Congo Presidential Election", None, "General", ("parsed", None, ""), ("iso:CG", "Republic of the Congo")),
        ("2026 United Kingdom Scotland Parliamentary Election", None, "General", ("parsed", None, ""), ("iso:GB-SCT", "Scotland")),
        ("2026 Scotland Parliamentary Election", "United Kingdom", "General", ("parsed", None, ""), ("iso:GB-SCT", "Scotland")),
        ("2026 Niger and Nigeria Elections", "Niger", "General", ("partial", "place_conflict", "Nigeria"), ("iso:NE", "Niger")),
        ("2026 Ivory Coast Presidential Election", "Côte d'Ivoire", "General", ("parsed", None, ""), ("iso:CI", "Côte d'Ivoire")),
        ("2026 Côte d'Ivoire (Ivory Coast) Presidential Election", None, "Presidential", ("parsed", None, ""), ("iso:CI", "Côte d'Ivoire")),
    ],
)
def test_card_places(
    title: str,
    location: str | None,
    types: str,
    want: tuple[str, str | None, str],
    claim: tuple[str, str] | None,
) -> None:
    res = title_date(title, D25, types, location)
    assert kind(res) == want
    got = [(c.place_id, c.place_raw) for c in cards_of(res)]
    assert got == ([] if claim is None else [claim])


def test_duplicates_compare_every_field() -> None:
    t = "2026 General Election"
    res = one(card(t, D25, "General", "Chile"), card(t, D25, "General", "Peru"))
    assert [u.outcome for u in units_of(res)] == ["parsed", "parsed"]
    assert [c.place_id for c in cards_of(res)] == ["iso:CL", "iso:PE"]
    t = "2026 Chile General Election"
    res = one(card(t, D25, "General", "Peru"), card(t, D25, "General", "Chile"))
    assert [(u.outcome, u.reason, u.leftover) for u in units_of(res)] == [
        ("partial", "place_conflict", "Chile"),
        ("parsed", None, ""),
    ]
    assert [c.place_id for c in cards_of(res)] == ["iso:PE", "iso:CL"]
    pres = card("2026 Chile Presidential Election", D25, "Presidential", "Chile")
    res = one(pres, pres)
    assert [(u.outcome, u.duplicate_of) for u in units_of(res)] == [
        ("parsed", None),
        ("ignored", "ndi:p0/upcoming-c1"),
    ]
    assert [c.place_id for c in cards_of(res)] == ["iso:CL"]
    narnia = card("2026 Narnia General Election", D25, "General")
    res = one(narnia, narnia)
    assert [(u.outcome, u.reason) for u in units_of(res)] == [("unparsed", "place_missing")] * 2
    t = "2026 Presidential Election"
    res = one(card(t, D25, "General", "Ivory Coast"), card(t, D25, "General", "Côte d'Ivoire"))
    assert [u.outcome for u in units_of(res)] == ["parsed", "parsed"]
    assert [c.place_id for c in cards_of(res)] == ["iso:CI", "iso:CI"]


@pytest.mark.parametrize(
    ("title", "types", "want", "claims"),
    [
        (
            "2026 Chile Presidential and Local Elections",
            "Presidential\n Local",
            ("parsed", None, ""),
            [("head_of_state", "national", "Presidential", False), ("local_council", "subnational", "Local Elections", True)],
        ),
        (
            "2026 Chile Presidential and Parliamentary Elections",
            "Presidential and Parliamentary",
            ("parsed", None, ""),
            [("head_of_state", "national", None, None), ("legislature", "national", None, None)],
        ),
        (
            "2026 Trinidad and Tobago Presidential and Local Elections",
            "Presidential\n Local",
            ("parsed", None, ""),
            [("head_of_state", None, None, None), ("local_council", None, None, None)],
        ),
        (
            "2026 Chile Presidential and Xyz Elections",
            "Presidential",
            ("partial", "office_unrecognised", "Xyz Elections"),
            [("head_of_state", "national", "2026 Chile Presidential and Xyz Elections", None)],
        ),
        (
            "2026 Brazil General Elections",
            "General",
            ("parsed", None, ""),
            [("general", "national", None, None)],
        ),
    ],
)
def test_compound_titles(
    title: str,
    types: str,
    want: tuple[str, str | None, str],
    claims: list[tuple[str, str | None, str | None, bool | None]],
) -> None:
    res = one(card(title, D25, types))
    assert kind(res) == want
    got = cards_of(res)
    for c, (office_class, level, label, aggregate) in zip(got, claims, strict=True):
        assert c.office_class == office_class
        if level is not None:
            assert c.level == level
        if label is not None:
            assert c.office_label == label
        if aggregate is not None:
            assert c.aggregate is aggregate
    if "Trinidad" in title:
        assert {c.place_id for c in got} == {"iso:TT"}


def test_compound_titles_keep_each_parts_scope() -> None:
    res = one(card("2026 Nigeria Presidential and Osun Gubernatorial Elections", D25, "Presidential\n Gubernatorial"))
    assert kind(res)[0] == "parsed"
    a, b = cards_of(res)
    assert (a.office_class, a.level, a.jurisdiction) == ("head_of_state", "national", None)
    assert (b.office_class, b.level, b.jurisdiction, b.office_label) == (
        "governor",
        "subnational",
        "Osun",
        "Osun Gubernatorial Elections",
    )
    res = one(card("2026 Nigeria Osun Gubernatorial and State Assembly Elections", D25, "Gubernatorial\n State Assembly"))
    assert kind(res)[0] == "parsed"
    a, b = cards_of(res)
    assert [(c.office_class, c.level, c.jurisdiction) for c in (a, b)] == [
        ("governor", "subnational", "Osun"),
        ("legislature", "subnational", "Osun"),
    ]


@pytest.mark.parametrize(
    ("title", "types", "want", "claim"),
    [
        ("2026 Philippines (BARMM) BSKE Elections", "Regional", ("parsed", None, ""), ("local_council", "subnational", "BARMM", None)),
        ("2026 Philippines BSKE Run-Off", "Regional", ("parsed", None, ""), ("local_council", "subnational", None, 2)),
        ("2026 Philippines BSKE Elections", "Presidential Runoff", ("parsed", None, ""), ("head_of_state", "national", None, 2)),
        (
            "2026 Philippines BSKE First Round",
            "Presidential Runoff",
            ("partial", "round_conflict", "Presidential Runoff"),
            ("head_of_state", "national", None, None),
        ),
    ],
)
def test_type_fallback_keeps_the_title_context(
    title: str,
    types: str,
    want: tuple[str, str | None, str],
    claim: tuple[str, str, str | None, int | None],
) -> None:
    res = one(card(title, D25, types))
    assert kind(res) == want
    (c,) = cards_of(res)
    assert (c.office_class, c.level, c.jurisdiction, c.round) == claim
    assert c.office_label == title
    assert c.place_id == "iso:PH"
    if claim[2] == "BARMM":
        assert c.jurisdiction_kind == "subdivision" and c.aggregate


@pytest.mark.parametrize(
    ("title", "date", "span", "status", "meaning"),
    [
        ("2026 Chile General Election", "October 25, 2026 (ALL DAY)", DateSpan.day(date(2026, 10, 25)), "unknown", "voting_period"),
        ("2026 Chile General Election (exact date TBD)", "October 25, 2026 (ALL DAY)", DateSpan.month(2026, 10), "tentative", "unknown"),
        ("2026 Chile General Election", "December 31, 2026 (ALL DAY)", DateSpan.of_year(2026), "unknown", "unknown"),
        ("2026 Chile General Election (date TBD)", "December 31, 2026 (ALL DAY)", DateSpan.of_year(2026), "tentative", "unknown"),
        ("2026 Chile General Election", "November 30, 2026 (ALL DAY)", DateSpan.month(2026, 11), "unknown", "unknown"),
        ("2027 Chile General Election", "February 28, 2027 (ALL DAY)", DateSpan.month(2027, 2), "unknown", "unknown"),
        ("2028 Chile General Election", "February 28, 2028 (ALL DAY)", DateSpan.day(date(2028, 2, 28)), "unknown", "voting_period"),
        ("2028 Chile General Election", "February 29, 2028 (ALL DAY)", DateSpan.month(2028, 2), "unknown", "unknown"),
        ("2027 Chile General Election (TBD)", "June 01, 2027 (ALL DAY)", DateSpan.month(2027, 6), "tentative", "unknown"),
        ("2027 Chile General Election", "June 01, 2027 (ALL DAY)", DateSpan.day(date(2027, 6, 1)), "unknown", "voting_period"),
        ("2026 Chile General Election (Tbd)", "October 25, 2026", DateSpan.month(2026, 10), "tentative", "unknown"),
    ],
)
def test_dates(title: str, date: str, span: DateSpan, status: str, meaning: str) -> None:
    res = title_date(title, date)
    (c,) = cards_of(res)
    assert (c.span, c.date_status, c.date_meaning, c.date_text) == (span, status, meaning, date)


def option_terms(body: bytes) -> set[str]:
    soup = BeautifulSoup(body, "lxml")
    terms: set[str] = set()
    for select in soup.select("select[name=type]"):
        for option in select.find_all("option"):
            if option.get("value") != "All":
                terms.add(collapse_ws(option.get_text()).casefold())
    return terms


def test_type_vocabulary_matches_the_page_filter() -> None:
    assert option_terms(BODIES[0]) == ndi.SUBNATIONAL_TYPES | ndi.NATIONAL_TYPES
    assert not ndi.SUBNATIONAL_TYPES & ndi.NATIONAL_TYPES
    assert (len(ndi.SUBNATIONAL_TYPES), len(ndi.NATIONAL_TYPES)) == (14, 39)


def test_count_rule_matches_the_adapter() -> None:
    assert COUNT_RULES["ndi"] == CardBlocksRule(ndi.BLOCKS, ndi.WRAPPER)
    assert COUNT_RULES["ndi"] == CardBlocksRule(
        (("upcoming-elections", "upcoming"), ("past-elections", "past")), "election-wrapper"
    )


def test_requests_are_the_first_page_only() -> None:
    assert Ndi().requests(WINDOW) == (request(0),)
    assert request(3).url == "https://www.ndi.org/elections-calendar?page=3"
    assert ndi.PAGE_SIZE == 10 and ndi.CAP == 10


def test_type_terms_skip_comments() -> None:
    plain = card("2026 Chile Presidential and Local Elections", D25, "Presidential\n Local")
    noisy = plain.replace("<span>|</span>", "<!-- x --><span>|</span>").replace(
        "Presidential\n Local", "Presidential\n <!-- y -->\n Local"
    )
    assert noisy != plain and noisy.count("<!--") == 2
    a, b = one(plain), one(noisy)
    assert [(u.outcome, u.reason, u.text) for u in units_of(b)] == [
        (u.outcome, u.reason, u.text) for u in units_of(a)
    ]
    assert units_of(b)[0].outcome == "parsed" and "Presidential, Local" in units_of(b)[0].text
    assert [(c.office_class, c.level) for c in cards_of(b)] == [
        (c.office_class, c.level) for c in cards_of(a)
    ]
    single = one(card("2026 Chile General Election", D25, "General").replace(
        "<span>|</span>", "<!-- x --><span>|</span>"))
    assert [(u.outcome, u.reason) for u in units_of(single)] == [("parsed", None)]
    assert units_of(single)[0].text == "2026 Chile General Election | " + D25 + " | General"


def test_recursion_while_reading_is_an_outcome(monkeypatch: pytest.MonkeyPatch) -> None:
    # No markup depth raises RecursionError here (lxml caps nesting; 50000 levels still read
    # fine), so the read itself is made to raise.
    def deep(text: str, n: int) -> list[Any]:
        raise RecursionError

    monkeypatch.setattr(ndi, "_read_page", deep)
    raw = raw_of({0: BODIES[0]})
    res = parse(raw)
    assert detail(res) == ("layout_not_recognised", "nested too deep")
    assert res.units == () and res.claims == () and res.notes == ()
    assert expected(WINDOW, raw.pages) == (request(0),)
    raw9 = raw_of({9: BODIES[0]})
    assert parse(raw9, balanced=False).notes == (
        Reason("pagination_incomplete", "p0 was not fetched"),
    )


def test_cards_outside_the_card_list_fail_the_page() -> None:
    # (a) a stray </div> before the second upcoming card of p0 closes the wrapper early: the card
    # list keeps 1 upcoming card + 10 past cards = 11, p0 holds 20 date-type elements, so the
    # other 20 - 11 = 9 cards sit outside the lists.
    text = BODIES[0].decode()
    opening = '<div  class="partial -election -feed">'
    starts = [m.start() for m in re.finditer(re.escape(opening), text)]
    assert len(starts) == 20
    broken = (text[: starts[1]] + "</div>" + text[starts[1] :]).encode()
    assert broken != BODIES[0]
    expect_layout(broken, "9 cards outside the card lists")
    # (b) three upcoming cards, the first followed by a stray </div>: the list keeps 1 + 1 past
    # card = 2 of the 3 + 1 = 4 on the page, so 4 - 2 = 2 sit outside.
    expect_layout(
        ndi_page([BULGARIA + "</div>", HUNGARY, BULGARIA], PAST), "2 cards outside the card lists"
    )
    # (c) one wrapper child holding three cards: card 1 of the upcoming block holds 3.
    expect_layout(
        ndi_page(['<div class="views-rows">' + BULGARIA + HUNGARY + BULGARIA + "</div>"], PAST),
        "upcoming block card 1 holds 3 cards",
    )
    # (c2) the same in the past block, second child: the index counts from 1 in that block.
    expect_layout(
        ndi_page([BULGARIA], PAST + ['<div class="views-rows">' + HUNGARY + HUNGARY + "</div>"]),
        "past block card 2 holds 2 cards",
    )
    # (d) control: the unchanged page is read in full.
    assert detail(page0(BODIES[0])) == ("ok", "") and len(page0(BODIES[0]).units) == 20
