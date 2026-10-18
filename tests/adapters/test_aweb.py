from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.ledger import COUNT_RULES, HeaderTableRowsRule, check
from elections_calendar.model import DateSpan, Reason
from elections_calendar.sources import aweb
from elections_calendar.sources.aweb import URL, Aweb
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.window import window_for
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages, result

_: Adapter = Aweb()

WINDOW = window_for(datetime(2026, 10, 18, tzinfo=UTC))
REGISTRIES = Registries.load()
REQUEST = Aweb().requests(WINDOW)[0]
ALL = raw_pages(
    "aweb", [(REQUEST, result(fixture("aweb", "calendar.html", "2026-10-18"), url=URL))]
)
RES = Aweb().parse(ALL, WINDOW, REGISTRIES)
UNITS = {u.unit_id: u for u in RES.units}
CLAIMS = {c.claim_id: c for c in RES.claims}
DETAIL_NO_TABLE = "0 tables with headers country, election, date"
HEAD = ("Flag", "Country", "Election", "Date")


def parse(raw: RawPages = ALL) -> ParseResult:
    res = Aweb().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return res


def page_of(body: bytes) -> RawPages:
    return raw_pages("aweb", [(REQUEST, result(body, url=URL))])


def aweb_row(
    date: str = "25 Oct 2026",
    country: str = "Bulgaria",
    label: str = "2026 Presidential Election",
    href: str | None = "https://www.example.invalid/news",
) -> str:
    inner = f"<a href='{href}' target='_blank'>{label}</a>" if href else label
    return (
        '<tr><td><img src="/f.png" alt="x"/></td>'
        f"<td>{country} </td><td class='tit'>{inner}</td>"
        f"<td>\n  {date}\n </td></tr>"
    )


def aweb_page(rows: Sequence[str], headers: Sequence[str] = HEAD, beside: str = "") -> bytes:
    head = "".join(f"<th>{h}</th>" for h in headers)
    return (
        f"<!doctype html><html><body><div>{beside}<table>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        "</body></html>"
    ).encode()


def one(**kw: str | None) -> ParseResult:
    return parse(page_of(aweb_page([aweb_row(**kw)])))  # type: ignore[arg-type]


def test_fixture_ledger_balances() -> None:
    res = parse(ALL)
    report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 29, "partial": 2, "unparsed": 1, "ignored": 0}
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in res.coverage] == [
        ("calendar", "ok", 32, 2026)
    ]
    assert len(res.claims) == 31


def test_fixture_values() -> None:
    assert Counter(c.level for c in RES.claims) == {"national": 24, "subnational": 5, "unknown": 2}
    assert Counter(c.office_class for c in RES.claims) == {
        "general": 13,
        "legislature": 7,
        "head_of_state": 6,
        "local_council": 5,
    }
    assert {c.link for c in RES.claims} == {URL}
    assert Counter(c.date_meaning for c in RES.claims) == {"voting_period": 30, "unknown": 1}
    ghana = UNITS["aweb:calendar/r6"]
    assert (ghana.outcome, ghana.reason, ghana.leftover, ghana.relevance) == (
        "unparsed",
        "office_not_modelled",
        "2026 The Presidential Primaries",
        "unknown",
    )
    assert [(u.unit_id, u.reason) for u in RES.units if u.outcome == "partial"] == [
        ("aweb:calendar/r5", "level_unresolved"),
        ("aweb:calendar/r29", "office_unrecognised"),
    ]


def test_in_window_claims() -> None:
    assert sorted(
        (c.span.start.isoformat(), c.place_id, c.office_class, c.level)
        for c in RES.claims
        if WINDOW.overlaps(c.span) and c.span.start is not None
    ) == [
        ("2026-09-20", "iso:RU", "legislature", "national"),
        ("2026-10-03", "iso:LV", "legislature", "national"),
        ("2026-10-04", "iso:BA", "general", "national"),
        ("2026-10-04", "iso:BR", "general", "national"),
        ("2026-10-25", "iso:BR", "general", "national"),
        ("2026-11-02", "iso:PH", "general", "unknown"),
        ("2026-11-02", "iso:ZA", "local_council", "subnational"),
        ("2026-11-28", "iso:TW", "local_council", "subnational"),
        ("2026-12-05", "iso:GM", "head_of_state", "national"),
        ("2026-12-22", "iso:SS", "general", "national"),
    ]


def test_claims_field_by_field() -> None:
    gm = CLAIMS["aweb:calendar/r31#0"]
    assert gm.institution == "iso:GM/president"
    assert gm.span == DateSpan.day(date(2026, 12, 5))
    assert (gm.date_meaning, gm.date_status, gm.date_text) == (
        "voting_period",
        "unknown",
        "05 Dec 2026",
    )
    assert (gm.evidence_kind, gm.indirect, gm.status_claim) == ("calendar", False, None)
    za = CLAIMS["aweb:calendar/r28#0"]
    assert za.span == DateSpan.days(date(2026, 11, 2), date(2027, 1, 31))
    assert (za.date_meaning, za.date_text) == ("unknown", "02 Nov 2026 -31 Jan 2027")
    pk = CLAIMS["aweb:calendar/r5#0"]
    assert (pk.office_class, pk.institution, pk.aggregate, pk.kind) == (
        "legislature",
        None,
        False,
        "candidate_election",
    )
    assert (pk.level, pk.jurisdiction, pk.jurisdiction_kind) == (
        "unknown",
        "Gilgit Baltistan",
        "subdivision",
    )
    assert pk.office_label == "2026 Gilgit Baltistan Assembly Election"
    assert pk.date_text == "24 Jan 2026"
    u = UNITS["aweb:calendar/r5"]
    assert (u.outcome, u.reason, u.relevance) == ("partial", "level_unresolved", "unknown")


def test_one_day_is_a_voting_period() -> None:
    assert one().claims[0].date_meaning == "voting_period"
    for text in ("Nov 2026", "2027", "2 Nov 2026 - 31 Jan 2027"):
        assert one(date=text).claims[0].date_meaning == "unknown"


def test_status_and_previous_date_come_from_the_date_text() -> None:
    c = one(date="Postponed from 25 Oct 2026 to 8 Nov 2026").claims[0]
    assert c.status_claim == "postponed"
    assert c.previous_date_text == "25 Oct 2026"
    assert c.span == DateSpan.day(date(2026, 11, 8))


def test_coverage_year_is_the_lists_year() -> None:
    def year(*dates: str) -> int | None:
        rows = [aweb_row(date=d) for d in dates]
        return parse(page_of(aweb_page(rows))).coverage[0].year

    assert year("5 Jan 2027", "8 Feb 2027") == 2027
    assert year("5 Jan 2026", "8 Feb 2027") is None
    assert year("-", "soon") is None
    assert year() is None


def test_external_links_are_never_claim_links() -> None:
    res = one(href="https://reuters.com/x")
    assert res.claims[0].link == URL
    assert (res.units[0].outcome, res.units[0].reason) == ("parsed", None)
    assert one(href=None).claims[0].link == URL


def test_rows_that_do_not_fit() -> None:
    short = parse(page_of(aweb_page(["<tr><td>a</td><td>b</td><td>c</td></tr>"])))
    assert short.units[0].reason == "too_few_cells" and short.claims == ()
    assert one(country="").units[0].reason == "place_missing"
    res = one(country="Narnia")
    assert (res.units[0].outcome, res.units[0].reason) == ("partial", "place_unregistered")
    exec_ = one(label="Lieutenant Governor election")
    assert (exec_.units[0].reason, exec_.units[0].leftover) == (
        "office_not_modelled",
        "Lieutenant Governor election",
    )
    assert exec_.claims == ()
    prim = one(label="2026 Democratic primary")
    assert (prim.units[0].reason, prim.units[0].leftover) == (
        "office_not_modelled",
        "2026 Democratic primary",
    )
    assert one(label="Primaries 2026").units[0].reason == "office_not_modelled"
    assert one(label="2026 Primarycolor Election").units[0].outcome != "unparsed"
    assert one(label="2026 Unprimary Election").units[0].outcome != "unparsed"
    assert one(label="Zorp").units[0].reason == "office_unrecognised"


def test_row_rule_order() -> None:
    assert one(country="", date="-").units[0].reason == "place_missing"
    assert one(date="-", label="Lieutenant Governor election").units[0].reason == "date_missing"
    assert one(date="25 Oct 2032", label="Lieutenant Governor election").units[0].reason == (
        "implausible_date"
    )
    assert one(date="25 Oct 2032").units[0].reason == "implausible_date"
    assert one(date="25 Oct 2026 and 8 Nov 2026").units[0].reason == "date_unparsed"
    assert one(date="25 Oct 9999").units[0].reason == "date_unparsed"
    assert one(date="soon").units[0].reason == "date_unparsed"
    assert one(date="soon", label="Lieutenant Governor election").units[0].reason == "date_unparsed"


def test_date_unparsed_leftover() -> None:
    u = one(date="soon").units[0]
    assert (u.outcome, u.leftover) == ("unparsed", "soon")


def test_partial_reasons_have_an_order() -> None:
    gb = "2026 Gilgit Baltistan Assembly Election"
    assert one(country="Narnia", label="Zorp").units[0].reason == "place_unregistered"
    assert one(country="Narnia", label=gb).units[0].reason == "place_unregistered"
    assert one(country="Pakistan", label="Zorp Gilgit Baltistan").units[0].reason == (
        "office_unrecognised"
    )
    assert one(country="Pakistan", label=gb).units[0].reason == "level_unresolved"


def test_relevance_comes_from_the_date_cell() -> None:
    assert one(date="").units[0].relevance == "unknown"
    assert one(date="", label="Presidential Election 2030").units[0].relevance == "unknown"
    assert one(date="25 Oct 2032").units[0].relevance == "in_or_after_window"
    assert one(date="3 Jan 2024", label="Election 2030").units[0].relevance == "before_window"


def test_columns_are_found_by_header_not_position() -> None:
    base = one().claims[0]
    row = (
        "<tr><td>25 Oct 2026</td><td>2026 Presidential Election</td><td>x</td>"
        "<td>Bulgaria</td></tr>"
    )
    page = aweb_page([row], ("Date", "Election", "Flag", "Country"))
    got = parse(page_of(page)).claims[0]
    assert got.date_text == base.date_text
    assert (got.place_id, got.office_label, got.span) == (
        base.place_id,
        base.office_label,
        base.span,
    )


def test_repeated_header_fails_the_page() -> None:
    row = "<tr><td>x</td><td>Chile</td><td>Presidential Election</td><td>1 Jan 2027</td>"
    row += "<td>2 Jan 2027</td></tr>"
    res = parse(page_of(aweb_page([row], (*HEAD, "Date"), beside="<p>1 Jan 2027 note</p>")))
    (cov,) = res.coverage
    assert (cov.outcome, cov.detail) == ("layout_not_recognised", "repeated header: date")
    assert res.units == () and res.claims == () and res.notes == ()


def test_dated_text_beside_the_table_is_a_coverage_gap() -> None:
    res = parse(
        page_of(aweb_page([aweb_row()], beside="<p>12 Dec 2026 Croatia, Local Elections</p>"))
    )
    assert res.coverage[0].outcome == "ok" and len(res.units) == 1
    assert res.notes == (
        Reason("coverage_gap", "dated text beside the table: 12 Dec 2026 Croatia, Local Elections"),
    )
    assert parse(page_of(aweb_page([aweb_row()]))).notes == ()
    assert RES.notes == ()


def _detail(body: bytes) -> tuple[str, str]:
    res = parse(page_of(body))
    (cov,) = res.coverage
    assert res.units == () and res.claims == ()
    return cov.outcome, cov.detail


def test_broken_pages_get_an_outcome_never_units() -> None:
    good = aweb_page([aweb_row()])
    text = good.decode()
    table = text[text.index("<table>") : text.index("</table>") + 8]
    cases = {
        "no table": (b"<html><body><p>x</p></body></html>", DETAIL_NO_TABLE),
        "renamed": (aweb_page([aweb_row()], ("Flag", "Country", "Election", "When")), DETAIL_NO_TABLE),
        "duplicated": (
            text.replace(table, table + table).encode(),
            "2 tables with headers country, election, date",
        ),
        "cut": (good[: len(good) // 2], "page does not end with </html>"),
        "empty": (b"", "page does not end with </html>"),
        "garbage": (b"\x00\xff garbage", "page does not end with </html>"),
        "no rows": (aweb_page([]), "the table has no rows"),
    }
    for body, detail in cases.values():
        assert _detail(body) == ("layout_not_recognised", detail)


def test_download_failures_keep_their_own_outcome() -> None:
    body = fixture("aweb", "calendar.html", "2026-10-18")
    res = parse(raw_pages("aweb", [(REQUEST, result(body, status=302, url=URL))]))
    assert res.coverage[0].outcome == "http_error" and res.units == ()
    res = parse(raw_pages("aweb", [(REQUEST, result(body, outcome="challenge_page", url=URL))]))
    assert res.coverage[0].outcome == "challenge_page" and res.units == ()


def test_requests_and_fetch() -> None:
    assert [(r.key, r.url) for r in Aweb().requests(WINDOW)] == [("calendar", URL)]
    urls: list[str] = []

    class Stub:
        def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
            urls.append(url)
            return result(b"x", url=url)

    pages = list(Aweb().fetch(WINDOW, Stub(), Deadline.after(60)))
    assert [p.request.key for p in pages] == ["calendar"] and urls == [URL]


def test_ledger_count_rule_matches_adapter_headers() -> None:
    rule = COUNT_RULES["aweb"]
    assert isinstance(rule, HeaderTableRowsRule)
    assert rule.headers == frozenset(aweb.HEADERS)


def test_ok_parse_with_two_spans_is_date_unparsed() -> None:
    for text in ("4 and 11 October 2026", "4 October, 11 October 2026", "4, 4 October 2026"):
        res = one(date=text)
        (u,) = res.units
        assert (u.outcome, u.reason, u.leftover) == ("unparsed", "date_unparsed", "")
        assert res.claims == ()
