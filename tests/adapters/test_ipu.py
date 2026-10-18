from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

import pytest

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.ledger import COUNT_RULES, HeaderTableRowsRule, check
from elections_calendar.model import DateSpan, Reason
from elections_calendar.sources import ipu
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.sources.ipu import URL, Ipu
from elections_calendar.window import window_for
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages, result

_: Adapter = Ipu()

WINDOW = window_for(datetime(2026, 10, 18, tzinfo=UTC))
REGISTRIES = Registries.load()
REQUEST = Ipu().requests(WINDOW)[0]
ALL = raw_pages(
    "ipu", [(REQUEST, result(fixture("ipu", "elections.html", "2026-10-18"), url=URL))]
)
RES = Ipu().parse(ALL, WINDOW, REGISTRIES)
UNITS = {u.unit_id: u for u in RES.units}
CLAIMS = {c.claim_id: c for c in RES.claims}
DETAIL_NO_TABLE = (
    "0 tables with headers country, chamber, principal mode of designation of members, "
    "expected date of next elections"
)
HEAD = (
    "Country",
    "Chamber",
    "Structure of parliament",
    "Chamber type",
    "Principal mode of designation of members",
    "Last election",
    "First session",
    "Expected date of next elections",
)
NZ = "https://data.ipu.org/parliament/NZ/NZ-LC01/elections/elections"


def parse(raw: RawPages = ALL) -> ParseResult:
    res = Ipu().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return res


def page_of(body: bytes) -> RawPages:
    return raw_pages("ipu", [(REQUEST, result(body, url=URL))])


def ipu_row(
    country: str = "New Zealand",
    chamber: str = "House of Representatives",
    designation: str = "Directly elected",
    expected: str | None = "07 Nov 2026",
    href: str | None = NZ,
    anchor: bool = True,
) -> str:
    if not anchor:
        name = chamber
    elif href is None:
        name = f"<a>{chamber}</a>"
    else:
        name = f'<a href="{href}">{chamber}</a>'
    exp = "" if expected is None else f"<td><span class='nowrap'>{expected}</span></td>"
    return (
        f"<tr><td>{country}</td><td>{name}</td><td>Unicameral</td><td>Lower chamber</td>"
        f"<td>{designation}</td><td>-</td><td>-</td>{exp}</tr>"
    )


def ipu_page(rows: Sequence[str], headers: Sequence[str] = HEAD, beside: str = "") -> bytes:
    head = "".join(f"<th>{h}</th>" for h in headers)
    return (
        f"<!doctype html><html><body><div>{beside}<table>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        "</body></html>"
    ).encode()


def one(**kw: object) -> ParseResult:
    return parse(page_of(ipu_page([ipu_row(**kw)])))  # type: ignore[arg-type]


def test_fixture_ledger_balances() -> None:
    res = parse(ALL)
    report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 234, "partial": 0, "unparsed": 4, "ignored": 43}
    assert report.ignored_reasons == {
        "inactive_chamber": 10,
        "appointed_chamber": 28,
        "no_expected_date": 5,
    }
    assert len(res.claims) == 234


def test_fixture_values() -> None:
    assert Counter(c.span.precision for c in RES.claims) == {"month": 197, "day": 37}
    assert Counter(c.office_class for c in RES.claims) == {
        "legislature": 96,
        "lower_house": 80,
        "upper_house": 58,
    }
    assert {c.level for c in RES.claims} == {"national"}
    assert sum(c.indirect for c in RES.claims) == 32
    assert all(c.institution and c.source_event_id for c in RES.claims)
    assert {urlsplit(c.link).hostname for c in RES.claims} == {"data.ipu.org"}
    assert {(c.date_meaning, c.date_status, c.evidence_kind) for c in RES.claims} == {
        ("expected_window", "tentative", "expected_renewal")
    }
    assert [
        (u.unit_id, u.leftover) for u in RES.units if u.reason == "designation_unrecognised"
    ] == [
        ("ipu:elections/r32", "Other"),
        ("ipu:elections/r44", "Other"),
        ("ipu:elections/r143", "Other"),
        ("ipu:elections/r264", "Other"),
    ]
    assert {u.relevance for u in RES.units if u.outcome == "unparsed"} == {"in_or_after_window"}


def test_in_window_claims() -> None:
    assert sorted(
        (c.place_id, c.office_class, c.span.precision, c.span.start.isoformat())
        for c in RES.claims
        if WINDOW.overlaps(c.span) and c.span.start is not None
    ) == [
        ("iso:CM", "lower_house", "month", "2027-01-01"),
        ("iso:ES", "lower_house", "day", "2026-11-29"),
        ("iso:ES", "upper_house", "day", "2026-11-29"),
        ("iso:FJ", "legislature", "month", "2026-12-01"),
        ("iso:GD", "lower_house", "day", "2026-11-05"),
        ("iso:HT", "lower_house", "month", "2026-12-01"),
        ("iso:HT", "upper_house", "month", "2026-12-01"),
        ("iso:IL", "legislature", "day", "2026-10-27"),
        ("iso:LY", "legislature", "month", "2026-12-01"),
        ("iso:MG", "upper_house", "month", "2026-12-01"),
        ("iso:NZ", "legislature", "day", "2026-11-07"),
        ("iso:RS", "legislature", "day", "2026-10-25"),
        ("iso:SO", "lower_house", "month", "2026-12-01"),
        ("iso:SO", "upper_house", "month", "2026-12-01"),
        ("iso:US", "lower_house", "day", "2026-11-03"),
        ("iso:US", "upper_house", "day", "2026-11-03"),
    ]


def test_claims_field_by_field() -> None:
    c = CLAIMS["ipu:elections/r180#0"]
    assert c.place_id == "iso:NZ" and c.institution == "iso:NZ/house-of-representatives"
    assert (c.level, c.jurisdiction, c.jurisdiction_kind) == ("national", None, "nationwide")
    assert c.office_class == "legislature" and c.office_label == "House of Representatives"
    assert c.span == DateSpan.day(date(2026, 11, 7)) and c.date_text == "07 Nov 2026"
    assert c.source_event_id == "ipu:NZ-LC01" and c.link == NZ
    assert (c.date_meaning, c.date_status, c.evidence_kind) == (
        "expected_window",
        "tentative",
        "expected_renewal",
    )
    assert c.status_claim is None and c.previous_date_text is None and c.indirect is False
    assert UNITS["ipu:elections/r180"].outcome == "parsed"
    cm = CLAIMS["ipu:elections/r50#0"]
    assert cm.span == DateSpan.month(2027, 1) and cm.date_text == "31 Jan 2027"
    assert cm.source_event_id == "ipu:CM-LC01"


@pytest.mark.parametrize(
    ("text", "span"),
    [
        ("31 Dec 2026", DateSpan.month(2026, 12)),
        ("30 Nov 2026", DateSpan.month(2026, 11)),
        ("28 Feb 2027", DateSpan.month(2027, 2)),
        ("29 Feb 2028", DateSpan.month(2028, 2)),
        ("28 Feb 2028", DateSpan.day(date(2028, 2, 28))),
        ("29 Nov 2026", DateSpan.day(date(2026, 11, 29))),
        ("01 Jan 2027", DateSpan.day(date(2027, 1, 1))),
    ],
)
def test_month_end_dates_are_months(text: str, span: DateSpan) -> None:
    res = one(expected=text)
    (c,) = res.claims
    assert c.span == span and c.date_text == text and c.date_status == "tentative"


def test_far_renewals() -> None:
    assert CLAIMS["ipu:elections/r31#0"].span == DateSpan.month(2033, 1)
    far = one(expected="31 Jan 2037")
    assert (far.units[0].outcome, far.units[0].reason) == ("unparsed", "implausible_date")
    assert far.claims == ()
    assert one(expected="31 Jan 2016").claims[0].span == DateSpan.month(2016, 1)
    assert one(expected="31 Jan 2015").units[0].reason == "implausible_date"


def test_designations() -> None:
    assert one(designation="Indirectly elected").claims[0].indirect is True
    assert one(designation="Directly elected").claims[0].indirect is False
    app = one(designation="Appointed")
    assert (app.units[0].outcome, app.units[0].reason) == ("ignored", "appointed_chamber")
    assert app.claims == ()
    for other in ("Other", "Mixed"):
        res = one(designation=other)
        u = res.units[0]
        assert (u.outcome, u.reason, u.leftover) == ("unparsed", "designation_unrecognised", other)
        assert res.claims == ()
    sus = one(chamber="Senate (Suspended)", designation="Appointed")
    assert (sus.units[0].outcome, sus.units[0].reason) == ("ignored", "inactive_chamber")
    dis = one(chamber="Senate (Dissolved)")
    assert (dis.units[0].outcome, dis.units[0].reason) == ("ignored", "inactive_chamber")
    assert one(chamber="Senate (suspended)").units[0].reason == "inactive_chamber"
    assert one(chamber="Senate (Suspended) of the realm").units[0].outcome in ("parsed", "partial")


def test_row_rule_order() -> None:
    short = parse(page_of(ipu_page(["<tr><td>a</td><td>b</td><td>c</td></tr>"])))
    assert short.units[0].reason == "too_few_cells" and short.claims == ()
    seven = parse(page_of(ipu_page([ipu_row(expected=None)])))
    assert seven.units[0].reason == "too_few_cells"
    # inactive beats appointed beats unrecognised beats place beats date
    res = one(country="", chamber="X (Dissolved)", designation="Other", expected="x")
    assert res.units[0].reason == "inactive_chamber"
    res = one(country="", designation="Appointed", expected="x")
    assert res.units[0].reason == "appointed_chamber"
    res = one(country="", designation="Other", expected="x")
    assert res.units[0].reason == "designation_unrecognised"
    res = one(country="", expected="-")
    assert res.units[0].reason == "place_missing"
    res = one(expected="-", chamber="Lieutenant Governor")
    assert res.units[0].reason == "no_expected_date"
    res = one(expected="31 Jan 2037", chamber="Lieutenant Governor")
    assert res.units[0].reason == "implausible_date"
    res = one(expected="Nov 2026", chamber="Lieutenant Governor")
    assert res.units[0].reason == "date_unparsed"
    exec_ = one(chamber="Lieutenant Governor")
    assert (exec_.units[0].reason, exec_.units[0].leftover) == (
        "office_not_modelled",
        "Lieutenant Governor",
    )
    assert exec_.claims == ()
    res = one(country="Narnia")
    assert (res.units[0].outcome, res.units[0].reason) == ("partial", "place_unregistered")
    assert res.claims[0].place_id


def test_partial_reason_order() -> None:
    res = one(country="Narnia", chamber="Zorp", href="https://evil.example/x")
    assert res.units[0].reason == "place_unregistered"
    res = one(chamber="Zorp", href="https://evil.example/x")
    assert res.units[0].reason == "office_unrecognised"
    res = one(href="https://evil.example/x")
    assert res.units[0].reason == "link_rejected"


def test_expected_date_cells() -> None:
    res = one(expected="-")
    assert (res.units[0].outcome, res.units[0].reason) == ("ignored", "no_expected_date")
    assert res.claims == ()
    for text in ("Nov 2026", "01 Nov 2026 - 02 Nov 2026", "2027", "Soon"):
        u = one(expected=text).units[0]
        assert (u.outcome, u.reason, u.leftover) == ("unparsed", "date_unparsed", text)
    res = one(href=None, anchor=False)
    assert res.claims[0].source_event_id is None and res.claims[0].link == URL
    assert res.units[0].outcome == "parsed"


def test_relevance_comes_from_the_expected_date_cell() -> None:
    res = one(expected="")
    assert res.units[0].reason == "no_expected_date" and res.units[0].relevance == "unknown"
    row = ipu_row(expected="2030").replace("<td>-</td><td>-</td>", "<td>2020</td><td>2019</td>")
    assert parse(page_of(ipu_page([row]))).units[0].relevance == "in_or_after_window"
    row = ipu_row(expected="-").replace("<td>-</td><td>-</td>", "<td>2030</td><td>2030</td>")
    assert parse(page_of(ipu_page([row]))).units[0].relevance == "unknown"
    assert one(expected="31 Jan 2016").units[0].relevance == "before_window"


def test_anchor_without_a_str_href_is_not_link_rejected() -> None:
    res = one(href=None)
    assert (res.units[0].outcome, res.units[0].reason) == ("parsed", None)
    assert res.claims[0].link == URL and res.claims[0].source_event_id is None


def test_off_host_links_fall_back() -> None:
    res = one(href="https://evil.example/parliament/NZ/NZ-LC01/x")
    assert res.claims[0].link == URL and res.claims[0].source_event_id is None
    assert (res.units[0].outcome, res.units[0].reason) == ("partial", "link_rejected")
    res = one(href="//[")
    assert res.claims[0].link == URL
    assert (res.units[0].outcome, res.units[0].reason) == ("partial", "link_rejected")
    for blank in ("", "   "):
        res = one(href=blank)
        assert (res.units[0].outcome, res.units[0].reason) == ("parsed", None)
        assert res.claims[0].link == URL and res.claims[0].source_event_id is None


def test_source_event_id_comes_from_the_accepted_link() -> None:
    res = one(href="/parliament/NZ/NZ-LC01/elections/elections")
    assert res.claims[0].source_event_id == "ipu:NZ-LC01"
    assert res.claims[0].link == NZ
    res = one(href="https://data.ipu.org/parliament/NZ/other/")
    assert res.claims[0].source_event_id is None
    assert res.units[0].outcome == "parsed"
    res = one(href="https://data.ipu.org/parliament/NZ/NZ-LC1/")
    assert res.claims[0].source_event_id is None
    res = one(href="https://sub.data.ipu.org/parliament/NZ/NZ-UC02/")
    assert res.claims[0].source_event_id == "ipu:NZ-UC02"


def test_columns_are_found_by_header_not_position() -> None:
    base = one().claims[0]
    cells = ipu_row().removeprefix("<tr>").removesuffix("</tr>").split("</td>")[:-1]
    cells = [c + "</td>" for c in cells]
    order = (7, 4, 1, 0, 2, 3, 5, 6)
    page = ipu_page(["<tr>" + "".join(cells[i] for i in order) + "</tr>"], [HEAD[i] for i in order])
    assert parse(page_of(page)).claims[0] == base
    res = parse(page_of(ipu_page([ipu_row()], HEAD[:4])))
    assert res.coverage[0].outcome == "layout_not_recognised"


def test_dated_text_beside_the_table_is_a_coverage_gap() -> None:
    res = parse(page_of(ipu_page([ipu_row()], beside="<p>Updated 12 Dec 2026</p>")))
    assert res.coverage[0].outcome == "ok" and len(res.units) == 1
    assert res.notes == (
        Reason("coverage_gap", "dated text beside the table: Updated 12 Dec 2026"),
    )
    assert parse(page_of(ipu_page([ipu_row()]))).notes == ()


def _detail(body: bytes) -> tuple[str, str]:
    res = parse(page_of(body))
    (cov,) = res.coverage
    assert res.units == () and res.claims == ()
    return cov.outcome, cov.detail


def test_broken_pages_get_an_outcome_never_units() -> None:
    good = ipu_page([ipu_row()])
    text = good.decode()
    table = text[text.index("<table>") : text.index("</table>") + 8]
    cases = {
        "no table": (b"<html><body><p>x</p></body></html>", DETAIL_NO_TABLE),
        "renamed": (ipu_page([ipu_row()], (*HEAD[:7], "Next")), DETAIL_NO_TABLE),
        "duplicated": (
            text.replace(table, table + table).encode(),
            DETAIL_NO_TABLE.replace("0 tables", "2 tables"),
        ),
        "cut": (good[: len(good) // 2], "page does not end with </html>"),
        "empty": (b"", "page does not end with </html>"),
        "garbage": (b"\x00\xff garbage", "page does not end with </html>"),
        "no rows": (ipu_page([]), "the table has no rows"),
        "repeated": (ipu_page([ipu_row()], (*HEAD, "Chamber")), "repeated header: chamber"),
    }
    for body, detail in cases.values():
        assert _detail(body) == ("layout_not_recognised", detail)


def test_download_failures_keep_their_own_outcome() -> None:
    body = fixture("ipu", "elections.html", "2026-10-18")
    res = parse(raw_pages("ipu", [(REQUEST, result(body, status=302, url=URL))]))
    assert res.coverage[0].outcome == "http_error" and res.units == ()
    res = parse(raw_pages("ipu", [(REQUEST, result(body, outcome="challenge_page", url=URL))]))
    assert res.coverage[0].outcome == "challenge_page" and res.units == ()


def test_requests_and_fetch() -> None:
    assert [(r.key, r.url) for r in Ipu().requests(WINDOW)] == [("elections", URL)]
    assert URL == "https://data.ipu.org/elections/" and ipu.HOSTS == ("data.ipu.org",)
    urls: list[str] = []

    class Stub:
        def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
            urls.append(url)
            return result(b"x", url=url)

    pages = list(Ipu().fetch(WINDOW, Stub(), Deadline.after(60)))
    assert [p.request.key for p in pages] == ["elections"] and urls == [URL]


def test_ledger_count_rule_matches_adapter_headers() -> None:
    rule = COUNT_RULES["ipu"]
    assert isinstance(rule, HeaderTableRowsRule)
    assert rule.headers == frozenset(ipu.HEADERS)
