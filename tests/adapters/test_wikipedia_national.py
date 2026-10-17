import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, Literal

import pytest

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.ledger import COUNT_RULES, SectionItemsRule, check
from elections_calendar.model import Claim, DateSpan, InputUnit, Reason
from elections_calendar.sources import wikipedia
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.sources.wikipedia import Wikipedia
from elections_calendar.window import window_for
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages, result

_: Adapter = Wikipedia()

WINDOW = window_for(datetime(2026, 10, 16, tzinfo=UTC))
REGISTRIES = Registries.load()
JSON_TYPE = "application/json; charset=utf-8"
NATIONAL = raw_pages(
    "wikipedia",
    [
        (r, result(fixture("wikipedia", f"{r.key}.json"), url=r.url, content_type=JSON_TYPE))
        for r in Wikipedia().requests(WINDOW)
        if r.key.startswith("national-")
    ],
)
RES = Wikipedia().parse(NATIONAL, WINDOW, REGISTRIES)
CLAIMS = {c.claim_id: c for c in RES.claims}
UNITS = {u.unit_id: u for u in RES.units}
P = "wikipedia:national-2026@rev1380221397/"
P27 = "wikipedia:national-2027@rev1379360216/"
S = "wikipedia:national-2026@rev7/"
TITLE = "2026 national electoral calendar"


def wiki_page(sections: dict[str, str], *, title: str = TITLE, revid: int = 7) -> bytes:
    """The MediaWiki parse JSON of a page with these sections (id -> inner HTML)."""
    html = "".join(
        f'<div class="mw-heading mw-heading2"><h2 id="{sid}">{sid.replace("_", " ")}</h2></div>{body}'
        for sid, body in sections.items()
    )
    text = f'<div class="mw-parser-output">{html}</div>'
    return json.dumps({"parse": {"title": title, "pageid": 1, "revid": revid, "text": text}}).encode()


def swap(**bodies: FetchResult) -> RawPages:
    """NATIONAL with some pages' results replaced; keys use "_" for "-" ("national_2026")."""
    replaced = {key.replace("_", "-"): res for key, res in bodies.items()}
    return raw_pages(
        "wikipedia",
        [(p.request, replaced.get(p.request.key, p.result)) for p in NATIONAL.pages],
    )


def body_of(body: bytes, key: str = "national-2026") -> FetchResult:
    request = next(p.request for p in NATIONAL.pages if p.request.key == key)
    return result(body, url=request.url, content_type=JSON_TYPE)


def synth(sections: dict[str, str], **kw: Any) -> tuple[RawPages, ParseResult]:
    raw = swap(national_2026=body_of(wiki_page(sections, **kw)))
    res = Wikipedia().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return raw, res


def of(res: ParseResult, key: str = "national-2026") -> tuple[InputUnit, ...]:
    return tuple(u for u in res.units if u.unit_id.startswith(f"wikipedia:{key}@"))


def one_page(body: bytes) -> ParseResult:
    raw = swap(national_2026=body_of(body))
    res = Wikipedia().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return res


def per_page_counter(key: str, fn: Callable[[Claim], object]) -> Counter[object]:
    return Counter(fn(c) for c in RES.claims if c.unit_id.startswith(f"wikipedia:{key}@"))


def mine(res: ParseResult) -> list[Claim]:
    return [c for c in res.claims if c.unit_id.startswith('wikipedia:national-2026@')]


def li(text: str) -> str:
    return f"<ul><li>{text}</li></ul>"


def test_requests_cover_both_kinds_for_every_window_year() -> None:
    reqs = Wikipedia().requests(WINDOW)
    assert [(r.key, r.year, r.mediawiki) for r in reqs] == [
        ("national-2026", 2026, True),
        ("national-2027", 2027, True),
        ("local-2026", 2026, True),
        ("local-2027", 2027, True),
    ]
    assert reqs[0].url == (
        "https://en.wikipedia.org/w/api.php?action=parse&page=2026_national_electoral_calendar"
        "&prop=text%7Crevid&format=json&formatversion=2&maxlag=5"
    )
    assert reqs[3].url.startswith("https://en.wikipedia.org/w/api.php?action=parse&page=2027_local_")
    rule = COUNT_RULES["wikipedia"]
    assert isinstance(rule, SectionItemsRule)
    assert Wikipedia.STOP_IDS == rule.stop_ids == wikipedia.STOP_IDS


def test_fetch_gets_each_request_in_order_with_the_mediawiki_flag() -> None:
    seen: list[tuple[str, bool]] = []

    class Stub:
        def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
            seen.append((url, mediawiki))
            return result(b"x", url=url)

    pages = list(Wikipedia().fetch(WINDOW, Stub(), Deadline.after(60)))
    assert [p.request.key for p in pages] == [
        "national-2026", "national-2027", "local-2026", "local-2027",
    ]
    assert seen == [(r.url, True) for r in Wikipedia().requests(WINDOW)]


def test_national_fixture_ledger_balances() -> None:
    res = Wikipedia().parse(NATIONAL, WINDOW, REGISTRIES)
    assert check(NATIONAL, res).ok and res.reasons == ()
    assert [(c.key, c.outcome, c.units_seen, c.revid, c.unit_prefix) for c in res.coverage] == [
        ("national-2026", "ok", 108, 1380221397, "wikipedia:national-2026@rev1380221397/"),
        ("national-2027", "ok", 46, 1379360216, "wikipedia:national-2027@rev1379360216/"),
    ]
    for key, counts, n_claims in (
        ("national-2026", {("parsed", None): 95, ("partial", "office_unrecognised"): 1,
                           ("unparsed", "office_not_modelled"): 1,
                           ("ignored", "container_item"): 11}, 113),
        ("national-2027", {("parsed", None): 44, ("ignored", "container_item"): 2}, 56),
    ):
        assert Counter((u.outcome, u.reason) for u in of(res, key)) == counts
        assert sum(1 for c in res.claims if c.unit_id.startswith(f"wikipedia:{key}@")) == n_claims


def test_national_claim_classes() -> None:
    assert per_page_counter("national-2026", lambda c: (c.office_class, c.level)) == {
        ("general", "national"): 1, ("general", "unknown"): 1, ("head_of_state", "national"): 32,
        ("legislature", "national"): 35, ("lower_house", "national"): 18,
        ("referendum", "national"): 14, ("upper_house", "national"): 12,
    }
    assert per_page_counter("national-2027", lambda c: (c.office_class, c.level)) == {
        ("head_of_state", "national"): 15, ("legislature", "national"): 27,
        ("lower_house", "national"): 7, ("upper_house", "national"): 7,
    }
    assert {c.jurisdiction_kind for c in RES.claims} == {"nationwide"}


@pytest.mark.parametrize(
    ("claim_id", "place", "label", "office_class", "institution", "rnd", "start", "end"),
    [
        (P + "September/li[1]#0", "iso:SE", "Parliament", "legislature", "iso:SE/parliament", None, "2026-09-13", "2026-09-13"),
        (P + "September/li[2]#0", "x:south-ossetia", "President", "head_of_state", "x:south-ossetia/president", None, "2026-09-18", "2026-09-18"),
        (P + "September/li[3]#0", "iso:RU", "State Duma", "lower_house", "iso:RU/state-duma", None, "2026-09-18", "2026-09-20"),
        (P + "September/li[4]#0", "iso:MA", "House of Representatives", "lower_house", "iso:MA/house-of-representatives", None, "2026-09-23", "2026-09-23"),
        (P + "September/li[5]#0", "iso:IM", "House of Keys", "lower_house", "iso:IM/house-of-keys", None, "2026-09-24", "2026-09-24"),
        (P + "September/li[6]/li[1]#0", "iso:ST", "Parliament", "legislature", "iso:ST/national-assembly", None, "2026-09-27", "2026-09-27"),
        (P + "October/li[2]/li[2]#0", "iso:BR", "President (1st round)", "head_of_state", "iso:BR/president", 1, "2026-10-04", "2026-10-04"),
        (P + "October/li[2]/li[2]#1", "iso:BR", "Chamber of Deputies", "lower_house", "iso:BR/chamber-of-deputies", None, "2026-10-04", "2026-10-04"),
        (P + "October/li[2]/li[2]#2", "iso:BR", "Senate", "upper_house", "iso:BR/federal-senate", None, "2026-10-04", "2026-10-04"),
        (P + "October/li[6]/li[3]#0", "iso:BR", "President (2nd round)", "head_of_state", "iso:BR/president", 2, "2026-10-25", "2026-10-25"),
        (P + "November/li[2]#0", "iso:GD", "Parliament", "legislature", None, None, "2026-11-05", "2026-11-05"),
        (P + "November/li[3]#0", "iso:NZ", "Parliament", "legislature", "iso:NZ/house-of-representatives", None, "2026-11-07", "2026-11-07"),
        (P + "November/li[4]#0", "iso:CV", "President", "head_of_state", "iso:CV/president", None, "2026-11-15", "2026-11-15"),
        (P + "November/li[5]/li[1]#0", "iso:ES", "Senate", "upper_house", "iso:ES/senate", None, "2026-11-29", "2026-11-29"),
        (P + "November/li[5]/li[1]#1", "iso:ES", "Congress of Deputies", "lower_house", "iso:ES/congress-of-deputies", None, "2026-11-29", "2026-11-29"),
        (P + "November/li[5]/li[2]#0", "iso:CH", "Referendums", "referendum", None, None, "2026-11-29", "2026-11-29"),
        (P + "Indirect_elections/li[2]#0", "iso:IN", "Council of States", "upper_house", "iso:IN/council-of-states", None, "2026-03-16", "2026-03-16"),
        (P + "Indirect_elections/li[2]#1", "iso:IN", "Council of States", "upper_house", "iso:IN/council-of-states", None, "2026-06-18", "2026-06-18"),
        (P + "Indirect_elections/li[2]#2", "iso:IN", "Council of States", "upper_house", "iso:IN/council-of-states", None, "2026-10-16", "2026-10-16"),
        (P + "Indirect_elections/li[14]#0", "iso:CH", "Federal Council", "general", None, None, "2026-12-09", "2026-12-09"),
    ],
)
def test_appendix_b_national_claims(
    claim_id: str,
    place: str,
    label: str,
    office_class: str,
    institution: str | None,
    rnd: int | None,
    start: str,
    end: str,
) -> None:
    c = CLAIMS[claim_id]
    assert (
        c.place_id, c.office_label, c.office_class, c.institution, c.round,
        c.span.start, c.span.end,
    ) == (
        place, label, office_class, institution, rnd,
        date.fromisoformat(start), date.fromisoformat(end),
    )
    assert c.indirect == claim_id.startswith(P + "Indirect_elections/")


def test_appendix_b_aggregates_kinds_and_levels() -> None:
    assert CLAIMS[P + "November/li[2]#0"].aggregate is True  # Grenada
    assert CLAIMS[P + "September/li[1]#0"].aggregate is False
    assert CLAIMS[P + "November/li[5]/li[2]#0"].kind == "referendum_day"
    assert CLAIMS[P + "Indirect_elections/li[14]#0"].level == "national"
    assert {c.indirect for c in RES.claims if "/Indirect_elections/" not in c.unit_id} == {False}


def test_one_national_claim_field_by_field() -> None:
    c = CLAIMS[P + "September/li[1]#0"]
    assert (
        c.link, c.place_raw, c.date_text, c.date_status, c.status_claim, c.source_event_id,
        c.level, c.kind, c.aggregate, c.evidence_kind, c.date_meaning,
        c.previous_date_text, c.jurisdiction, c.source,
    ) == (
        "https://en.wikipedia.org/wiki/2026_national_electoral_calendar#September", "Sweden",
        "13 September", "unknown", None, None, "national", "candidate_election", False,
        "calendar", "voting_period", None, None, "wikipedia",
    )


def test_offices_the_calendar_does_not_model_or_recognise() -> None:
    u = UNITS[P + "Indirect_elections/li[6]"]  # 3 April: Myanmar, Vice President
    assert (u.outcome, u.reason, u.leftover) == ("unparsed", "office_not_modelled", "Vice President")
    assert not [c for c in RES.claims if c.unit_id == u.unit_id]
    u = UNITS[P + "Indirect_elections/li[1]"]  # Iran, Supreme Leader
    c = CLAIMS[P + "Indirect_elections/li[1]#0"]
    assert (u.outcome, u.reason, c.office_class, c.aggregate, c.level) == (
        "partial", "office_unrecognised", "general", True, "unknown",
    )


def test_undated_items_get_the_page_year() -> None:
    c = CLAIMS[P27 + "Unknown_date/li[1]#0"]
    assert (c.place_id, c.office_class, c.aggregate, c.span, c.date_text, c.date_status) == (
        "iso:BH", "legislature", True, DateSpan.of_year(2027), "Unknown date", "unknown",
    )


def test_year_rollover() -> None:
    missing = result(b'{"error": {"code": "missingtitle"}}', outcome="api_error", api_code="missingtitle")
    cases: list[tuple[str, Literal["not_published_yet", "required_year_missing"]]] = [
        ("national_2027", "not_published_yet"),
        ("national_2026", "required_year_missing"),
    ]
    for key, outcome in cases:
        raw = swap(**{key: missing})
        res = Wikipedia().parse(raw, WINDOW, REGISTRIES)
        assert check(raw, res).ok
        page = key.replace("_", "-")
        by_key = {c.key: c for c in res.coverage}
        assert (by_key[page].outcome, by_key[page].unit_prefix, by_key[page].units_seen) == (outcome, None, 0)
        assert res.reasons == (Reason(outcome, page),)
        other = "national-2026" if page == "national-2027" else "national-2027"
        assert by_key[other].outcome == "ok"
        assert not of(res, page)
    other_code = result(b"{}", outcome="api_error", api_code="ratelimited")
    res = Wikipedia().parse(swap(national_2027=other_code), WINDOW, REGISTRIES)
    assert res.reasons == (Reason("api_error", "national-2027"),)
    res = Wikipedia().parse(swap(national_2027=result(b"", outcome="http_error", status=404)), WINDOW, REGISTRIES)
    assert res.reasons == (Reason("http_error", "national-2027"),)


@pytest.mark.parametrize(
    "body",
    [
        b"[]",
        b"null",
        b'{"parse": []}',
        b'{"parse": {"text": 5, "revid": 1}}',
        b'{"parse": {"text": "<div class=\\"mw-parser-output\\"><p>x</p></div>", "revid": 1, "title": "2026 national electoral calendar"}}',
        b"\xff{",
        pytest.param(b"[" * 100000, id="deeply-nested-array"),
    ],
)
def test_mediawiki_bodies_that_are_not_an_object_fail_the_layout_check(body: bytes) -> None:
    raw = swap(national_2026=body_of(body))
    res = Wikipedia().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    assert res.coverage[0].outcome == "layout_not_recognised"
    assert res.coverage[0].unit_prefix is None
    assert not of(res)
    assert res.coverage[1].outcome == "ok" and len(of(res, "national-2027")) == 46
    assert res.reasons == (Reason("layout_not_recognised", "national-2026"),)


def _edited(**changes: object) -> bytes:
    data = json.loads(fixture("wikipedia", "national-2026.json"))
    for field, value in changes.items():
        if value is KeyError:
            del data["parse"][field]
        else:
            data["parse"][field] = value
    return json.dumps(data).encode()


@pytest.mark.parametrize(
    "changes",
    [
        {"title": KeyError},
        {"title": None},
        {"title": ["x"]},
        {"title": "2025 national electoral calendar"},
        {"title": "2026 local electoral calendar"},
        {"revid": True},
        {"revid": 0},
        {"revid": "1380221397"},
        {"revid": KeyError},
        {"text": KeyError},
    ],
)
def test_layout_needs_every_field_the_adapter_uses(changes: dict[str, object]) -> None:
    raw = swap(national_2026=body_of(_edited(**changes)))
    res = Wikipedia().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    assert res.coverage[0].outcome == "layout_not_recognised"
    assert not of(res) and not [c for c in res.claims if "national-2026@" in c.unit_id]
    assert len(of(res, "national-2027")) == 46


def test_layout_needs_a_month_heading_a_parser_output_and_ids() -> None:
    def text_of(html: str) -> bytes:
        data = {"parse": {"title": TITLE, "revid": 7, "text": html}}
        return json.dumps(data).encode()

    ul = "<ul><li>5 January: Sweden, Parliament</li></ul>"
    cases = [
        # no month heading anywhere
        f'<div class="mw-parser-output"><h2 id="Overview">Overview</h2>{ul}</div>',
        # no div.mw-parser-output
        f'<div><h2 id="January">January</h2>{ul}</div>',
        # a heading without an id (MediaWiki always sets one)
        f'<div class="mw-parser-output"><h2 id="January">January</h2>{ul}<h2>Other</h2></div>',
    ]
    for html in cases:
        res = one_page(text_of(html))
        assert res.coverage[0].outcome == "layout_not_recognised", html
        assert not of(res)
    ok = one_page(text_of(f'<div class="mw-parser-output"><h2 id="January">January</h2>{ul}</div>'))
    assert ok.coverage[0].outcome == "ok" and len(of(ok)) == 1


def test_a_data_table_in_a_calendar_section_is_not_valid_empty() -> None:
    def outcome(html: str) -> str:
        return one_page(wiki_page({"January": html})).coverage[0].outcome

    assert outcome('<table class="wikitable"><tr><td>5 January</td><td>Sweden</td></tr></table>') == "layout_not_recognised"
    assert outcome("<table><tr><td>5 January</td></tr></table>") == "layout_not_recognised"
    assert outcome("<dl><dt>5 January</dt></dl>") == "layout_not_recognised"
    assert outcome('<div><table class="wikitable"><tr><td>x</td></tr></table></div>') == "layout_not_recognised"
    for cls in ("ambox", "metadata", "navbox", "mbox-small ambox ambox-content"):
        assert outcome(f'<table class="{cls}"><tr><td>This section is empty.</td></tr></table>') == "valid_empty"
    # a table in a stop section is not a calendar entry
    stop = wiki_page({"January": "<p>none</p>", "References": '<table class="wikitable"><tr><td>x</td></tr></table>'})
    assert one_page(stop).coverage[0].outcome == "valid_empty"


def test_a_page_with_month_headings_and_no_items_is_valid_empty() -> None:
    _, res = synth({"January": "<p>none</p>", "February": "<p>none</p>"})
    assert [(c.outcome, c.units_seen, c.revid) for c in res.coverage][0] == ("valid_empty", 0, 7)
    assert res.coverage[0].unit_prefix == S
    assert not of(res) and res.reasons == ()


def test_section_items_and_ids() -> None:
    _, res = synth(
        {
            "January": (
                "<ul><li>5 January: <a>Sweden</a>, <a>Parliament</a></li>"
                "<li>11 January:<ul><li><a>Chile</a>, President (2nd round)</li>"
                "<li><a>Fiji</a>, Parliament</li></ul></li></ul>"
            ),
            "Unknown_date": li("<a>Fiji</a>, Parliament"),
            "Indirect_elections": li("9 December: <a>Switzerland</a>, Federal Council"),
            "References": "<ol><li>a reference</li></ol>",
        }
    )
    units = {u.unit_id: u for u in of(res)}
    claims = {c.claim_id: c for c in mine(res)}
    assert list(units) == [
        S + "January/li[1]", S + "January/li[2]", S + "January/li[2]/li[1]",
        S + "January/li[2]/li[2]", S + "Unknown_date/li[1]", S + "Indirect_elections/li[1]",
    ]
    assert (units[S + "January/li[2]"].outcome, units[S + "January/li[2]"].reason) == ("ignored", "container_item")
    assert not [c for c in mine(res) if c.unit_id == S + "January/li[2]"]
    jan11 = DateSpan.day(date(2026, 1, 11))
    assert claims[S + "January/li[2]/li[1]#0"].span == jan11
    assert claims[S + "January/li[2]/li[2]#0"].span == jan11
    assert claims[S + "January/li[2]/li[1]#0"].round == 2
    assert claims[S + "January/li[2]/li[1]#0"].date_text == "11 January"
    assert claims[S + "Unknown_date/li[1]#0"].span == DateSpan.of_year(2026)
    assert claims[S + "Unknown_date/li[1]#0"].date_text == "Unknown date"
    assert claims[S + "Indirect_elections/li[1]#0"].indirect is True
    assert claims[S + "January/li[1]#0"].indirect is False
    assert claims[S + "January/li[1]#0"].link.endswith("2026_national_electoral_calendar#January")
    assert [c.claim_id for c in mine(res)] == sorted(claims, key=list(claims).index)
    # month items without a date of their own take the month
    _, res2 = synth({"March": li("<a>Fiji</a>, Parliament")})
    c = mine(res2)[0]
    assert (c.span, c.date_text, c.date_status) == (DateSpan.month(2026, 3), "March", "unknown")


def test_own_text_ignores_footnotes_and_interlanguage_links() -> None:
    _, res = synth(
        {
            "January": li(
                '5 January: <a>Sweden</a>, <a>Parliament</a><sup class="reference">[1]</sup> '
                '<span>[<a class="extiw">es</a>]</span>'
            )
        }
    )
    (unit,) = of(res)
    (claim,) = mine(res)[:1]
    assert unit.text == "5 January: Sweden, Parliament"
    assert (claim.office_label, claim.place_raw) == ("Parliament", "Sweden")
    assert len(mine(res)) == 1 and unit.outcome == "parsed"
    # a link whose text holds a comma is the country text
    _, res2 = synth({"January": li("5 January: <a>Punjab, India</a>, Parliament")})
    assert mine(res2)[0].place_raw == "Punjab, India"
    # an interlanguage link inside the first position is never the country link
    _, res3 = synth(
        {"January": li('5 January: <a class="extiw">xx</a><a>Sweden</a>, Parliament')}
    )
    assert mine(res3)[0].place_raw == "Sweden"


def test_date_prefix_separators_and_head_rules() -> None:
    _, res = synth(
        {
            "January": (
                "<ul><li>5 January, Sweden: Parliament</li>"
                "<li>Sweden, Parliament</li></ul>"
            )
        }
    )
    claims = {c.unit_id: c for c in mine(res)}
    # ":" is tried first but "5 January, Sweden" is no date, so "," gives the prefix
    first = claims[S + "January/li[1]"]
    assert (first.date_text, first.place_raw, first.office_label) == ("5 January", "Sweden", "Parliament")
    assert first.span == DateSpan.day(date(2026, 1, 5))
    # a head without a digit that is no month name is not a date
    second = claims[S + "January/li[2]"]
    assert (second.date_text, second.place_raw, second.span) == ("January", "Sweden", DateSpan.month(2026, 1))


def test_date_looking_text_that_does_not_parse_is_unparsed() -> None:
    _, res = synth({"January": li("31 September: <a>Sweden</a>, Parliament")})
    (unit,) = of(res)
    assert (unit.outcome, unit.reason) == ("unparsed", "date_unparsed")
    assert not mine(res)


def test_children_of_an_unparsed_date_are_not_dated_by_the_section() -> None:
    _, res = synth(
        {"January": "<ul><li>31 September:<ul><li>Sweden, Parliament</li></ul></li></ul>"}
    )
    assert [(u.outcome, u.reason) for u in of(res)] == [
        ("unparsed", "date_unparsed"), ("unparsed", "date_unparsed"),
    ]
    assert not mine(res)


def test_implausible_dates_are_unparsed() -> None:
    _, res = synth({"January": li("5 January 1990: Sweden, Parliament")})
    (unit,) = of(res)
    assert (unit.outcome, unit.reason) == ("unparsed", "implausible_date")
    assert not mine(res)


def test_identical_spans_give_one_claim() -> None:
    _, res = synth({"January": li("4, 4 October: <a>Sweden</a>, Parliament")})
    assert len(mine(res)) == 1
    assert mine(res)[0].span == DateSpan.day(date(2026, 10, 4))


def test_date_status_and_previous_date_come_from_the_parse() -> None:
    _, res = synth({"January": li("Postponed from 5 March to 7 April: Sweden, Parliament")})
    c = mine(res)[0]
    assert (c.status_claim, c.span, c.previous_date_text) == (
        "postponed", DateSpan.day(date(2026, 4, 7)), "5 March",
    )
    assert c.date_text == "Postponed from 5 March to 7 April"


def test_items_without_a_country_or_office() -> None:
    _, res = synth(
        {
            "January": (
                "<ul><li>5 January:</li>"
                "<li>6 January: Sweden</li>"
                "<li>7 January: Sweden<ul><li>Parliament</li></ul></li>"
                "<li>8 January: <ul><li>Fiji, Parliament</li></ul></li></ul>"
            )
        }
    )
    got = [(u.unit_id.removeprefix(S), u.outcome, u.reason) for u in of(res)]
    assert got == [
        ("January/li[1]", "unparsed", "place_missing"),
        ("January/li[2]", "unparsed", "office_missing"),
        ("January/li[3]", "ignored", "container_item"),
        ("January/li[3]/li[1]", "unparsed", "office_missing"),
        ("January/li[4]", "ignored", "container_item"),
        ("January/li[4]/li[1]", "parsed", None),
    ]


def test_unregistered_places_and_unrecognised_offices_are_partial() -> None:
    _, res = synth({"January": li("5 January: Atlantis, Parliament")})
    (unit,) = of(res)
    assert (unit.outcome, unit.reason) == ("partial", "place_unregistered")
    assert mine(res)[0].place_id.startswith("unknown:")
    _, res2 = synth({"January": li("5 January: Sweden, Parliament and Vice President")})
    (unit2,) = of(res2)
    assert (unit2.outcome, unit2.reason, unit2.leftover) == ("partial", "office_not_modelled", "Vice President")
    assert len(mine(res2)) == 1
