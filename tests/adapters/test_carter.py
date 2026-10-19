import re
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit

import pytest

from elections_calendar.dates import parse_date_text
from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.ledger import COUNT_RULES, HeadingTablesRule, check
from elections_calendar.model import DateSpan, Reason
from elections_calendar.sources import carter
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.sources.carter import FOOTNOTE, SECTIONS, URL, Carter
from elections_calendar.window import window_for
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages, result

_: Adapter = Carter()

WINDOW = window_for(datetime(2026, 10, 18, tzinfo=UTC))
REGISTRIES = Registries.load()
REQUEST = Carter().requests(WINDOW)[0]
BODY = fixture("carter", "observed.html", "2026-10-18")
ALL = raw_pages("carter", [(REQUEST, result(BODY, url=URL))])
RES = Carter().parse(ALL, WINDOW, REGISTRIES)
UNITS = {u.unit_id: u for u in RES.units}
CLAIMS = {c.claim_id: c for c in RES.claims}
H1 = "Elections Monitored by The Carter Center"
H2 = "Expert Missions"
CONGO = "https://www.cartercenter.org/country/democratic-republic-of-the-congo/"
PAGE = BODY.decode("utf-8")
NO_TABLE = "section has no table: elections monitored by the carter center"


def parse(raw: RawPages = ALL) -> ParseResult:
    res = Carter().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return res


def page_of(body: bytes | str) -> RawPages:
    data = body.encode() if isinstance(body, str) else body
    return raw_pages("carter", [(REQUEST, result(data, url=URL))])


def row(country: str, dates: str, href: str | None = "/c/") -> str:
    name = country if href is None else f'<a href="{href}">{country}</a>'
    return f"<tr><td>{name}</td><td>{dates}</td></tr>"


def carter_page(rows: Sequence[str], head: str = "", beside: str = "", h: str = H1) -> str:
    return (
        f"<!doctype html><html><body><h2>{h}</h2><figure>{beside}<table>{head}"
        f"<tbody>{''.join(rows)}</tbody></table></figure></body></html>"
    )


GAP = (Reason("coverage_gap", "section not found: expert missions"),)


def one(dates: str, country: str = "Chile", href: str | None = "/c/") -> ParseResult:
    res = parse(page_of(carter_page([row(country, dates, href)])))
    assert res.notes == GAP
    return res


def shape(res: ParseResult) -> tuple[str, str | None, str]:
    (u,) = res.units
    return u.outcome, u.reason, u.leftover


def spans(res: ParseResult) -> list[tuple[str, bool]]:
    return [(c.date_text, c.office_label.endswith("(targeted)")) for c in res.claims]


def test_fixture_ledger_balances() -> None:
    res = parse(ALL)
    report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 14, "partial": 0, "unparsed": 46, "ignored": 1}
    assert report.ignored_reasons == {"footnote": 1}
    assert Counter(u.reason for u in res.units if u.outcome == "unparsed") == {
        "implausible_date": 42,
        "date_unparsed": 4,
    }
    assert {u.relevance for u in res.units if u.outcome == "unparsed"} == {"before_window"}
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [("observed", "ok", 61)]
    assert res.notes == ()


def test_fixture_claims() -> None:
    got = [
        (
            c.claim_id.removeprefix("carter:observed/"),
            c.place_id,
            c.span.start.isoformat() if c.span.start else None,
            c.span.end.isoformat() if c.span.end else None,
        )
        for c in RES.claims
    ]
    assert got == [
        ("monitored-r6#0", "iso:CD", "2023-12-01", "2023-12-31"),
        ("monitored-r14#0", "iso:GY", "2025-09-01", "2025-09-30"),
        ("monitored-r39#0", "iso:TN", "2022-12-01", "2022-12-31"),
        ("monitored-r39#1", "iso:TN", "2023-01-01", "2023-01-31"),
        ("monitored-r41#0", "iso:VE", "2024-07-01", "2024-07-31"),
        ("monitored-r43#0", "iso:ZW", "2023-08-01", "2023-08-31"),
        ("expert-r2#0", "iso:BR", "2022-10-01", "2022-10-31"),
        ("expert-r3#0", "iso:CO", "2022-05-01", "2022-06-30"),
        ("expert-r3#1", "iso:CO", "2026-05-01", "2026-05-31"),
        ("expert-r3#2", "iso:CO", "2026-06-01", "2026-06-30"),
        ("expert-r7#0", "iso:KE", "2022-08-01", "2022-08-31"),
        ("expert-r9#0", "iso:LR", "2023-10-01", "2023-11-30"),
        ("expert-r11#0", "iso:PE", "2026-04-01", "2026-04-30"),
        ("expert-r11#1", "iso:PE", "2026-06-01", "2026-06-30"),
        ("expert-r12#0", "iso:PH", "2022-05-01", "2022-05-31"),
        ("expert-r14#0", "iso:TN", "2022-07-01", "2022-07-31"),
        ("expert-r15#0", "iso:VE", "2021-11-01", "2021-11-30"),
        ("expert-r16#0", "iso:ZM", "2021-08-01", "2021-08-31"),
    ]
    assert [c.claim_id for c in RES.claims if c.office_label.endswith("(targeted)")] == [
        "carter:observed/monitored-r6#0",
        "carter:observed/monitored-r39#1",
    ]
    assert {
        (
            c.office_class,
            c.aggregate,
            c.kind,
            c.level,
            c.institution,
            c.evidence_kind,
            c.date_meaning,
            c.date_status,
            c.jurisdiction,
            c.jurisdiction_kind,
            c.round,
            c.source_event_id,
            c.status_claim,
            c.previous_date_text,
            c.indirect,
        )
        for c in RES.claims
    } == {
        (
            "general",
            True,
            "aggregate",
            "unknown",
            None,
            "observation",
            "unknown",
            "unknown",
            None,
            "nationwide",
            None,
            None,
            None,
            None,
            False,
        )
    }
    assert {urlsplit(c.link).hostname for c in RES.claims} == {"www.cartercenter.org"}
    assert {c.office_label for c in RES.claims if c.claim_id.split("/")[1][0] == "e"} == {
        "Carter Center expert mission"
    }
    assert {c.source for c in RES.claims} == {"carter"}


def test_one_claim_field_by_field() -> None:
    c = CLAIMS["carter:observed/monitored-r6#0"]
    assert c.office_label == "Carter Center election observation (targeted)"
    assert c.date_text == "December 2023*"
    assert c.link == CONGO
    assert c.span == DateSpan.month(2023, 12)
    assert c.date_meaning == "unknown"
    assert c.unit_id == "carter:observed/monitored-r6"
    assert c.place_raw == "Democratic Republic of the Congo"


def test_token_grammar() -> None:
    res = one(
        "May 2026, June 2026*; and July 2026, Georgia (RLA) 2026, May 2026, "
        "October – November 2025"
    )
    assert shape(res) == ("partial", "date_unparsed", "Georgia (RLA) 2026")
    assert [(c.span.start.isoformat(), t) for c, t in zip(res.claims, [0, 1, 0, 0], strict=True)
            if c.span.start] == [
        ("2026-05-01", 0),
        ("2026-06-01", 1),
        ("2026-07-01", 0),
        ("2025-10-01", 0),
    ]
    assert spans(res) == [
        ("May 2026", False),
        ("June 2026*", True),
        ("July 2026", False),
        ("October – November 2025", False),
    ]
    assert [c.claim_id.rsplit("#", 1)[1] for c in res.claims] == ["0", "1", "2", "3"]
    assert res.claims[3].span.end is not None and res.claims[3].span.end.month == 11

    res = one("May 2026, May 2026*")
    assert shape(res) == ("parsed", None, "")
    assert spans(res) == [("May 2026", False), ("May 2026*", True)]
    res = one("May 2026, May 2026")
    assert shape(res) == ("parsed", None, "") and spans(res) == [("May 2026", False)]
    res = one("May 2026*, May 2026*")
    assert spans(res) == [("May 2026*", True)]
    res = one("May 2026 *")
    assert spans(res) == [("May 2026 *", True)]
    res = one("May 2026,June 2026;July 2026")
    assert [c.date_text for c in res.claims] == ["May 2026", "June 2026", "July 2026"]
    res = one("May 2026, and June 2026")
    assert [c.date_text for c in res.claims] == ["May 2026", "June 2026"]
    res = one("May 2026, , June 2026")
    assert shape(res) == ("parsed", None, "") and len(res.claims) == 2

    res = one("May 2026, May 2032")
    assert shape(res) == ("partial", "implausible_date", "May 2032")
    assert len(res.claims) == 1
    res = one("May 2032")
    assert shape(res) == ("unparsed", "implausible_date", "May 2032")
    assert res.units[0].relevance == "in_or_after_window" and res.claims == ()
    res = one("October 1991, December 2001")
    assert shape(res) == ("unparsed", "implausible_date", "")
    assert res.units[0].relevance == "before_window" and res.claims == ()
    res = one("May 2021, May 2020")
    assert shape(res) == ("parsed", None, "") and spans(res) == [("May 2021", False)]
    res = one("December 2031, January 2032")
    assert shape(res) == ("partial", "implausible_date", "January 2032")
    assert spans(res) == [("December 2031", False)]
    res = one("May 0000, May 2200")
    assert shape(res) == ("unparsed", "date_unparsed", "May 0000, May 2200")
    assert res.claims == ()


def test_a_range_ending_this_year_but_starting_long_ago_is_future() -> None:
    res = one("January 2015 – May 2026")
    assert shape(res) == ("unparsed", "implausible_date", "January 2015 – May 2026")


def test_the_star_is_stripped_before_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    real = parse_date_text

    def spy(text: str, **kw: int) -> object:
        seen.append(text)
        return real(text, **kw)

    monkeypatch.setattr(carter, "parse_date_text", spy)
    one("May 2026 *, June 2026*")
    assert seen == ["May 2026", "June 2026"]


def test_year_range_spanning_history_and_future() -> None:
    res = one("October 2020 – November 2032")
    assert shape(res) == ("unparsed", "implausible_date", "October 2020 – November 2032")
    res = one("October 2019 – November 2020")
    assert shape(res) == ("unparsed", "implausible_date", "")


def test_yearless_token_is_never_guessed() -> None:
    res = one("May, June 2026")
    assert shape(res) == ("partial", "date_unparsed", "May")
    assert spans(res) == [("June 2026", False)]
    res = one("May")
    assert shape(res) == ("unparsed", "date_unparsed", "May")


def test_leftover_order_is_unparsed_then_future() -> None:
    res = one("May 2032, Bogus A, June 2033, Bogus B, May 2026")
    assert shape(res) == ("partial", "date_unparsed", "Bogus A, Bogus B, May 2032, June 2033")
    res = one("May 2032, Bogus A")
    assert shape(res) == ("unparsed", "date_unparsed", "Bogus A, May 2032")
    res = one("Bogus A, May 2032*")
    assert res.units[0].leftover == "Bogus A, May 2032*"


def test_without_claims_the_reason_is_date_unparsed_before_implausible() -> None:
    assert shape(one("May 2032")) == ("unparsed", "implausible_date", "May 2032")
    assert shape(one("Bogus")) == ("unparsed", "date_unparsed", "Bogus")
    assert shape(one("Bogus, December 1999")) == ("unparsed", "date_unparsed", "Bogus")
    assert shape(one("December 1999, January 2001")) == ("unparsed", "implausible_date", "")


def test_partial_reason_order() -> None:
    both = "May 2026, Bogus, May 2032"
    res = one(both, country="Atlantis", href="https://evil.example/x")
    assert shape(res)[:2] == ("partial", "date_unparsed")
    res = one("May 2026, May 2032", country="Atlantis", href="https://evil.example/x")
    assert shape(res)[:2] == ("partial", "implausible_date")
    res = one("May 2026", country="Atlantis", href="https://evil.example/x")
    assert shape(res)[:2] == ("partial", "place_unregistered")
    res = one("May 2026", href="https://evil.example/x")
    assert shape(res)[:2] == ("partial", "link_rejected")
    res = one("May 2026", country="Atlantis")
    assert shape(res)[:2] == ("partial", "place_unregistered")
    assert res.claims[0].place_id.startswith("unknown:")


def test_row_kinds() -> None:
    thead = "<thead><tr><th>Country</th><th>Dates</th></tr></thead>"

    def unit_of(rows: list[str], head: str = "") -> tuple[str, str | None, str, str]:
        res = parse(page_of(carter_page(rows, head=head)))
        u = res.units[0]
        return u.outcome, u.reason, u.leftover, u.relevance

    assert unit_of([], thead) == ("ignored", "header_row", "", "unknown")
    body_th = "<tr><th>Country</th><th>Dates</th></tr>"
    assert unit_of([body_th]) == ("unparsed", "date_unparsed", "Dates", "unknown")
    chile = '<tr><th scope="row">Chile</th><td>May 2026</td></tr>'
    res = parse(page_of(carter_page([chile])))
    assert shape(ParseResult("carter", res.units, (), res.coverage)) == ("parsed", None, "")
    assert [(c.place_id, c.span) for c in res.claims] == [("iso:CL", DateSpan.month(2026, 5))]
    all_th = "<tr><th>Chile</th><th>May 2026</th></tr>"
    res = parse(page_of(carter_page([all_th])))
    assert res.units[0].outcome == "parsed" and res.claims[0].place_id == "iso:CL"
    tbc = '<tr><th scope="row">Chile</th><th>TBC</th></tr>'
    assert unit_of([tbc]) == ("unparsed", "date_unparsed", "TBC", "unknown")
    empty = '<tr><th scope="row">Chile</th><th></th></tr>'
    assert unit_of([empty]) == ("unparsed", "date_missing", "", "unknown")
    one_cell = "<tr><td>{}</td></tr>"
    for text in (
        "*Chile mission postponed; date TBD",
        "*Chile May 2026",
        "*These missions were targeted observations.",
        "See also",
    ):
        assert unit_of([one_cell.format(text)]) == ("unparsed", "too_few_cells", "", "unknown")
    padded = one_cell.format(FOOTNOTE + " More.")
    assert unit_of([padded]) == ("unparsed", "too_few_cells", "", "unknown")
    two = f"<tr><td>{FOOTNOTE}</td><td>May 2026</td></tr>"
    assert unit_of([two]) == ("partial", "place_unregistered", "", "unknown")
    res = parse(page_of(carter_page(["<tr><td>Chile</td><td>May 2026</td><td></td></tr>"])))
    assert res.units[0].text == "Chile | May 2026"
    assert unit_of([one_cell.format(FOOTNOTE)]) == ("ignored", "footnote", "", "unknown")
    assert unit_of([one_cell.format(FOOTNOTE.upper())]) == ("ignored", "footnote", "", "unknown")
    assert unit_of([row("", "May 2026", None)]) == ("unparsed", "place_missing", "", "unknown")
    assert unit_of([row("Chile", "", None)]) == ("unparsed", "date_missing", "", "unknown")
    assert unit_of([row("Chile", " , ; ", None)]) == ("unparsed", "date_missing", "", "unknown")


def test_thead_header_row_needs_every_cell_th() -> None:
    mixed = "<thead><tr><th>Country</th><td>Dates</td></tr></thead>"
    res = parse(page_of(carter_page([], head=mixed)))
    assert (res.units[0].outcome, res.units[0].reason) == ("unparsed", "date_unparsed")
    # the footnote in a thead is still the footnote, not a header
    foot = f"<thead><tr><th>{FOOTNOTE}</th></tr></thead>"
    res = parse(page_of(carter_page([], head=foot)))
    assert (res.units[0].outcome, res.units[0].reason) == ("ignored", "header_row")


def test_a_thead_outside_the_table_is_not_its_header() -> None:
    page = (
        f"<html><body><h2>{H1}</h2><thead><tr><td><table><tr><th>Country</th>"
        "<th>Dates</th></tr></table></td></tr></thead></body></html>"
    )
    res = parse(page_of(page))
    assert [(u.outcome, u.reason, u.leftover) for u in res.units] == [
        ("unparsed", "date_unparsed", "Dates")
    ]


def test_a_repeated_future_token_stays_in_leftover() -> None:
    res = one("May 2032, May 2032, May 2026")
    assert shape(res) == ("partial", "implausible_date", "May 2032, May 2032")
    assert spans(res) == [("May 2026", False)]


def test_nested_tables_are_not_sections_tables_or_units() -> None:
    nested = "<table><tr><td>Chile</td><td>May 2026</td></tr></table>"
    page = carter_page([f"<tr><td>{nested}</td><td>June 2026</td></tr>", row("Peru", "May 2026")])
    res = parse(page_of(page))
    assert res.coverage[0].outcome == "ok"
    assert [u.unit_id for u in res.units] == [
        "carter:observed/monitored-r1",
        "carter:observed/monitored-r2",
    ]
    assert res.units[1].text == "Peru | May 2026"
    assert res.claims[-1].place_id == "iso:PE"
    # a section whose only table is nested in another element still has one top-level table
    only_nested = f"<html><body><h2>{H1}</h2><div>{nested}</div></body></html>"
    assert len(parse(page_of(only_nested)).units) == 1
    # a table inside a top-level table is not a second table
    assert parse(page_of(page)).notes == GAP


def test_row_header_markup_gives_the_same_claims() -> None:
    rows = re.sub(
        r"<tr>\s*<td([^>]*)>(.*?)</td>", r'<tr><th scope="row"\1>\2</th>', PAGE, flags=re.S
    )
    assert rows != PAGE
    res = parse(page_of(rows))
    assert [(c.claim_id, c.place_id, c.span, c.date_text, c.link) for c in res.claims] == [
        (c.claim_id, c.place_id, c.span, c.date_text, c.link) for c in RES.claims
    ]
    assert len(res.claims) == 18 and len(res.units) == 61


def test_entity_and_curly_quote_names_resolve() -> None:
    u = UNITS["carter:observed/monitored-r5"]
    assert u.text == "Cote d’Ivoire | November 2010, December 2011, October 2020"
    assert (u.outcome, u.reason) == ("unparsed", "implausible_date")
    cherokee = next(x for x in RES.units if x.text.startswith("Cherokee Nation"))
    assert (cherokee.outcome, cherokee.reason) == ("unparsed", "implausible_date")
    for name, place in (
        ("Cote d&#8217;Ivoire", "iso:CI"),
        ("Cherokee Nation", "x:cherokee-nation"),
        ("S&atilde;o Tom&eacute; and Pr&iacute;ncipe", "iso:ST"),
    ):
        res = one("May 2026", country=name)
        assert shape(res) == ("parsed", None, "")
        assert res.claims[0].place_id == place


def test_sections_are_bound_to_their_heading() -> None:
    first = PAGE.index("<table")
    end = PAGE.index("</table>", first) + len("</table>")
    res = parse(page_of(PAGE[:first] + PAGE[end:]))
    assert res.coverage[0].outcome == "ok" and len(res.units) == 18
    assert {u.unit_id.split("/")[1][:7] for u in res.units} == {"expert-"}
    assert len(res.claims) == 12
    assert res.notes == (Reason("coverage_gap", NO_TABLE),)

    longer = PAGE.replace("</body>", f"<h2>{H2} Archive</h2></body>")
    assert longer != PAGE and len(parse(page_of(longer)).units) == 61
    heading = f"{H2}</h2>"
    assert heading in PAGE
    res = parse(page_of(PAGE.replace(heading, heading + f"<h2>{H2}</h2>", 1)))
    assert res.coverage[0].outcome == "layout_not_recognised"
    assert res.coverage[0].detail == "heading 'expert missions' appears 2 times"
    assert res.units == () and res.claims == () and res.notes == ()

    extra = "<table><tr><td>Note</td></tr></table>"
    res = parse(page_of(PAGE[:first] + extra + PAGE[first:]))
    assert res.coverage[0].outcome == "layout_not_recognised"
    assert res.coverage[0].detail == (
        "section 'elections monitored by the carter center' has 2 tables"
    )

    res = parse(page_of(PAGE.replace(f">{H2}<", ">Specialist Missions<")))
    assert res.coverage[0].outcome == "ok" and len(res.units) == 43
    assert res.notes == GAP

    renamed = PAGE.replace(f">{H2}<", ">Specialist<").replace(f">{H1}<", ">Other<")
    res = parse(page_of(renamed))
    assert res.coverage[0].outcome == "layout_not_recognised"
    assert res.coverage[0].detail == "no section found" and res.notes == ()

    start = PAGE.index("<table", PAGE.index(f">{H2}<"))
    stop = PAGE.index("</table>", start)
    inner = PAGE[start:stop]
    emptied = PAGE[:start] + re.sub(r"<tr>.*</tr>", "", inner, flags=re.S) + PAGE[stop:]
    res = parse(page_of(emptied))
    assert res.coverage[0].outcome == "layout_not_recognised"
    assert res.coverage[0].detail == "the table has no rows"
    assert res.units == ()


def test_a_table_outside_the_section_is_not_the_sections_table() -> None:
    # the table before the first heading and after the last h2 are in no section
    extra = "<table><tr><td>Note</td></tr></table>"
    res = parse(page_of(extra + PAGE))
    assert len(res.units) == 61
    tail = PAGE.replace("</body>", extra + "</body>")
    assert tail != PAGE
    # a later h2 ends the Expert section before the footer table
    assert len(parse(page_of(tail)).units) == 61


def test_off_host_links_fall_back() -> None:
    res = one("May 2026", href="https://cartercenter.org.evil.example/x")
    assert res.claims[0].link == URL
    assert shape(res) == ("partial", "link_rejected", "")
    res = one("May 2026", href="https://cartercenter.org/x")
    assert shape(res) == ("parsed", None, "")
    assert res.claims[0].link == "https://cartercenter.org/x"
    res = one("May 2026", href="/country/chile/")
    assert res.claims[0].link == "https://www.cartercenter.org/country/chile/"
    for missing in (None, "", "   "):
        res = one("May 2026", href=missing)
        assert shape(res) == ("parsed", None, "") and res.claims[0].link == URL
    res = one("May 2026", href="http://[bad")
    assert res.claims[0].link == URL and res.units[0].reason == "link_rejected"
    # no claims, so no link_rejected
    res = one("May 2032", href="https://evil.example/x")
    assert shape(res) == ("unparsed", "implausible_date", "May 2032")
    # the link comes from the country cell, not the date cell
    page = carter_page(['<tr><td>Chile</td><td><a href="/d/">May 2026</a></td></tr>'])
    assert parse(page_of(page)).claims[0].link == URL
    # the first anchor of the country cell wins
    page = carter_page(
        ['<tr><td><a href="/a/">Chile</a> <a href="/b/">x</a></td><td>May 2026</td></tr>']
    )
    assert parse(page_of(page)).claims[0].link == "https://www.cartercenter.org/a/"
    page = carter_page(['<tr><td><a>Chile</a> <a href="/b/">x</a></td><td>May 2026</td></tr>'])
    assert parse(page_of(page)).claims[0].link == URL


def test_relevance_comes_from_the_date_cell() -> None:
    page = carter_page(['<tr><td>Chile 2032</td><td>May 1999</td></tr>'])
    assert parse(page_of(page)).units[0].relevance == "before_window"
    page = carter_page(['<tr><td>Chile 1999</td><td>May 2032</td></tr>'])
    assert parse(page_of(page)).units[0].relevance == "in_or_after_window"
    page = carter_page(['<tr><td>Chile May 2032</td><td>TBC</td><td>May 1999</td></tr>'])
    assert parse(page_of(page)).units[0].relevance == "unknown"


def test_dated_text_beside_the_table_is_a_coverage_gap() -> None:
    page = carter_page([row("Chile", "May 2026")], beside="<p>Chile May 2026</p>")
    res = parse(page_of(page))
    assert res.coverage[0].outcome == "ok" and len(res.units) == 1
    assert res.notes == (
        Reason("coverage_gap", "dated text beside the table: Chile May 2026"),
        *GAP,
    )
    both = PAGE.replace("<figure", "<figure><p>Seen 2026</p><span></span", 1)
    notes = parse(page_of(both)).notes
    assert notes == (Reason("coverage_gap", "dated text beside the table: Seen 2026"),)
    assert RES.notes == ()


def test_broken_pages_get_an_outcome_never_units() -> None:
    half = BODY[: len(BODY) // 2]
    for body in (half, b"", b"\x00\xff garbage"):
        res = parse(page_of(body))
        (cov,) = res.coverage
        assert res.units == () and res.claims == () and res.notes == ()
        assert (cov.outcome, cov.detail) == (
            "layout_not_recognised",
            "page does not end with </html>",
        )
    res = parse(page_of("<html><body><p>x</p></body></html>"))
    assert res.coverage[0].detail == "no section found"


def test_hostile_page_content_never_raises() -> None:
    hostile = [
        row("Chile", "May 0000"),
        row("Chile", "May 9999, January 1800, 31 February 2026"),
        row("Chile", "May 2026", href="http://[::1"),
        row("Chile", "May 2026", href="https://user:pw@www.cartercenter.org:99999/"),
        row("Chile", "\u0000�*, *, **"),
        "<tr></tr>",
        "<tr><td></td></tr>",
        "<tr><td>Chile</td></tr>",
    ]
    res = parse(page_of(carter_page(hostile)))
    assert len(res.units) == len(hostile)


def test_requests_and_fetch() -> None:
    assert [(r.key, r.url) for r in Carter().requests(WINDOW)] == [("observed", URL)]
    assert URL == "https://www.cartercenter.org/programs/democracy/elections-observed/"
    assert carter.HOSTS == ("cartercenter.org",) and Carter.source == "carter"
    urls: list[str] = []

    class Stub:
        def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
            urls.append(url)
            return result(b"x", url=url)

    pages = list(Carter().fetch(WINDOW, Stub(), Deadline.after(60)))
    assert [p.request.key for p in pages] == ["observed"] and urls == [URL]


def test_sections_constants() -> None:
    assert SECTIONS == (
        (
            "elections monitored by the carter center",
            "monitored",
            "Carter Center election observation",
        ),
        ("expert missions", "expert", "Carter Center expert mission"),
    )
    assert FOOTNOTE == (
        "*these missions were targeted or focused observations and did not result in "
        "statements on the overall administration of the electoral process."
    )


def test_ledger_count_rule_matches_adapter_sections() -> None:
    rule = COUNT_RULES["carter"]
    assert isinstance(rule, HeadingTablesRule)
    assert rule.sections == tuple((h, slug) for h, slug, _ in SECTIONS)


def test_download_failures_keep_their_own_outcome() -> None:
    res = parse(raw_pages("carter", [(REQUEST, result(BODY, status=302, url=URL))]))
    assert res.coverage[0].outcome == "http_error" and res.units == ()


@pytest.mark.parametrize("bad", ["May 2026 May 2026", "4 and 11 October 2026"])
def test_a_token_with_two_spans_is_unparsed(bad: str) -> None:
    res = one(bad)
    assert shape(res) == ("unparsed", "date_unparsed", bad)


@pytest.mark.parametrize(
    "cell", ["Cancelled May 2026", "May 2026 Cancelled", "Postponed to June 2026", "Held May 2026"]
)
def test_a_token_with_a_status_word_is_unparsed(cell: str) -> None:
    res = one(cell)
    assert shape(res) == ("unparsed", "date_unparsed", cell)
    assert res.claims == ()


def test_a_status_token_beside_a_good_one_makes_the_row_partial() -> None:
    res = one("May 2026, Cancelled June 2026")
    assert shape(res) == ("partial", "date_unparsed", "Cancelled June 2026")
    assert len(res.claims) == 1
    assert res.claims[0].date_text == "May 2026"


@pytest.mark.parametrize(
    ("country", "dates", "extra", "outcome", "reason", "leftover", "claims"),
    [
        ("Chile", "May 2026", "with the OAS", "partial", "extra_cells", "with the OAS", 1),
        ("Chile", "May 2026, Bogus", "note", "partial", "date_unparsed", "Bogus, note", 1),
        ("Chile", "TBC", "note", "unparsed", "date_unparsed", "TBC, note", 0),
        ("Chile", "May 2026", " ", "parsed", None, "", 1),
        ("Atlantis", "May 2026", "note", "partial", "extra_cells", "note", 1),
    ],
)
def test_extra_cells_are_leftover(
    country: str,
    dates: str,
    extra: str,
    outcome: str,
    reason: str | None,
    leftover: str,
    claims: int,
) -> None:
    html = carter_page([row(country, dates).replace("</tr>", f"<td>{extra}</td></tr>")])
    res = parse(page_of(html))
    assert shape(res) == (outcome, reason, leftover)
    assert len(res.claims) == claims
    if country == "Atlantis":
        assert res.claims[0].place_id == "unknown:atlantis"
