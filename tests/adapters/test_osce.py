from collections import Counter
from collections.abc import Sequence
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

import pytest

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.ledger import COUNT_RULES, HeaderTableRowsRule, check
from elections_calendar.model import DateSpan, Reason
from elections_calendar.sources import osce
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.sources.osce import URL, Osce
from elections_calendar.window import window_for
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages, result

_: Adapter = Osce()

WINDOW = window_for(datetime(2026, 10, 18, tzinfo=UTC))
REGISTRIES = Registries.load()
REQUEST = Osce().requests(WINDOW)[0]
ALL = raw_pages(
    "osce", [(REQUEST, result(fixture("osce", "elections.html", "2026-10-18"), url=URL))]
)
RES = Osce().parse(ALL, WINDOW, REGISTRIES)
UNITS = {u.unit_id: u for u in RES.units}
CLAIMS = {c.claim_id: c for c in RES.claims}
DETAIL_NO_TABLE = "0 tables with headers date, country, election, activity"
HEAD = ("Date", "Country", "Election", "Activity")


def parse(raw: RawPages = ALL) -> ParseResult:
    res = Osce().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return res


def page_of(body: bytes) -> RawPages:
    return raw_pages("osce", [(REQUEST, result(body, url=URL))])


def osce_row(
    date: str = "25 Oct 2026",
    badges: Sequence[str] = ("Upcoming",),
    country: str = "Bulgaria",
    label: str = "Presidential Election",
    activity: str = "-",
    filter_date: str | None = "2026-10-25",
    country_href: str | None = "/odihr/elections/bulgaria",
    activity_href: str | None = None,
    date_cell: str | None = None,
) -> str:
    attr = f' data-filter-date="{filter_date}"' if filter_date is not None else ""
    spans = "".join(f'<span class="badge">{b}</span>' for b in badges)
    date_html = date_cell if date_cell is not None else f"<td><div>{date}</div>{spans}</td>"
    country_html = (
        f'<a href="{country_href}">{country}</a>' if country_href is not None else country
    )
    act = f'<div><a href="{activity_href}">{activity}</a></div>' if activity_href else activity
    return (
        f'<tr class="search-target"{attr}>{date_html}'
        f'<td><span class="elections-country">{country_html}</span></td>'
        f"<td>{label}</td><td>{act}</td></tr>"
    )


def osce_page(
    rows: Sequence[str], headers: Sequence[str] = HEAD, beside: str = ""
) -> bytes:
    head = "".join(f"<th>{h}</th>" for h in headers)
    return (
        f"<!doctype html><html><body><div class='table-wrapper'>{beside}<table>"
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
        "</body></html>"
    ).encode()


def one(**kw: object) -> ParseResult:
    return parse(page_of(osce_page([osce_row(**kw)])))  # type: ignore[arg-type]


def test_fixture_ledger_balances() -> None:
    res = parse(ALL)
    report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 173, "partial": 7, "unparsed": 454, "ignored": 0}
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in res.coverage] == [
        ("elections", "ok", 634, None)
    ]
    assert len(res.claims) == 180


def test_fixture_values() -> None:
    assert Counter(c.span.precision for c in RES.claims) == {"day": 165, "month": 7, "year": 8}
    assert Counter(c.level for c in RES.claims) == {
        "national": 144,
        "subnational": 29,
        "unknown": 7,
    }
    assert Counter(c.office_class for c in RES.claims) == {
        "legislature": 91,
        "head_of_state": 43,
        "local_council": 29,
        "general": 12,
        "referendum": 5,
    }
    assert Counter((u.outcome, u.reason) for u in RES.units if u.reason) == {
        ("unparsed", "implausible_date"): 454,
        ("partial", "office_unrecognised"): 6,
        ("partial", "level_unresolved"): 1,
    }
    assert {u.relevance for u in RES.units if u.outcome != "parsed"} == {"before_window"}
    assert {c.status_claim for c in RES.claims} == {None}
    assert not any(c.indirect for c in RES.claims)
    assert {urlsplit(c.link).hostname for c in RES.claims} == {"odihr.osce.org"}


def test_in_window_claims() -> None:
    assert sorted(
        (c.span.start.isoformat(), c.place_id, c.office_class, c.institution)
        for c in RES.claims
        if WINDOW.overlaps(c.span) and c.span.start is not None
    ) == [
        ("2026-09-13", "iso:SE", "legislature", "iso:SE/parliament"),
        ("2026-09-20", "iso:RU", "legislature", None),
        ("2026-10-03", "iso:LV", "legislature", "iso:LV/parliament"),
        ("2026-10-04", "iso:BA", "general", None),
        ("2026-10-25", "iso:BG", "head_of_state", "iso:BG/president"),
        ("2026-10-25", "iso:RS", "legislature", "iso:RS/national-assembly"),
        ("2026-11-03", "iso:US", "legislature", None),
        ("2026-11-15", "iso:SI", "local_council", None),
        ("2026-11-29", "iso:ES", "legislature", None),
        ("2027-01-27", "iso:KG", "head_of_state", "iso:KG/president"),
    ]


def test_one_claim_field_by_field() -> None:
    c = CLAIMS["osce:elections/r1#0"]
    assert (c.place_id, c.level, c.jurisdiction_kind) == ("iso:BG", "national", "nationwide")
    assert (c.office_class, c.institution, c.kind) == (
        "head_of_state",
        "iso:BG/president",
        "candidate_election",
    )
    assert c.span == DateSpan.day(date(2026, 10, 25))
    assert (c.date_meaning, c.date_status, c.date_text) == (
        "voting_period",
        "unknown",
        "25 Oct 2026",
    )
    assert c.link == "https://odihr.osce.org/odihr/elections/bulgaria"
    assert c.status_claim is None
    u = UNITS["osce:elections/r1"]
    assert u.text == "25 Oct 2026 Upcoming | Bulgaria | Presidential Election | -"
    assert u.relevance == "in_or_after_window"
    rs = CLAIMS["osce:elections/r52#0"]
    assert rs.office_class == "head_of_state" and rs.institution is None
    assert rs.level == "unknown"
    assert (rs.jurisdiction, rs.jurisdiction_kind) == ("Republika Srpska", "subdivision")
    assert (UNITS["osce:elections/r52"].outcome, UNITS["osce:elections/r52"].reason) == (
        "partial",
        "level_unresolved",
    )


@pytest.mark.parametrize(
    ("badges", "date_text", "filter_date", "outcome", "reason", "status", "leftover"),
    [
        (("Upcoming", "Past"), "25 Oct 2026", "2026-10-25", "parsed", None, None, ""),
        (("Postponed",), "25 Oct 2026", "2026-10-25", "parsed", None, "postponed", ""),
        (("Cancelled",), "25 Oct 2026", "2026-10-25", "parsed", None, "cancelled", ""),
        (("Canceled",), "25 Oct 2026", "2026-10-25", "parsed", None, "cancelled", ""),
        (("Cancelled", "Canceled"), "25 Oct 2026", "2026-10-25", "parsed", None, "cancelled", ""),
        (("Upcoming", "Postponed"), "25 Oct 2026", "2026-10-25", "parsed", None, "postponed", ""),
        (
            ("Postponed", "Cancelled"), "25 Oct 2026", "2026-10-25",
            "partial", "status_conflict", None, "Postponed Cancelled",
        ),
        (
            ("Cancelled", "Postponed"), "25 Oct 2026", "2026-10-25",
            "partial", "status_conflict", None, "Cancelled Postponed",
        ),
        (
            ("Postponed", "Cancelled"), "Held 25 Oct 2026", "2026-10-25",
            "partial", "status_conflict", None, "Postponed Cancelled",
        ),
        (
            ("Postponed",), "Held 25 Oct 2026", "2026-10-25",
            "partial", "status_conflict", None, "Postponed",
        ),
        (("Upcoming",), "Held 25 Oct 2026", "2026-10-25", "parsed", None, "held", ""),
        (
            ("Upcoming", "Postponed", "Cancelled"), "25 Oct 2026", "2026-10-25",
            "partial", "status_conflict", None, "Postponed Cancelled",
        ),
        (
            ("Postponed", "Cancelled"), "25 Oct 2026", "2026-10-24",
            "partial", "filter_date_mismatch", None, "Postponed Cancelled",
        ),
        (
            ("Rescheduled",), "25 Oct 2026", "2026-10-25",
            "partial", "status_unrecognised", None, "Rescheduled",
        ),
    ],
)
def test_badges(
    badges: tuple[str, ...],
    date_text: str,
    filter_date: str,
    outcome: str,
    reason: str | None,
    status: str | None,
    leftover: str,
) -> None:
    res = one(badges=badges, date=date_text, filter_date=filter_date)
    (u,), (c,) = res.units, res.claims
    assert (u.outcome, u.reason, u.leftover) == (outcome, reason, leftover)
    assert c.status_claim == status


def test_unrecognised_badge_keeps_a_mapped_status() -> None:
    res = one(badges=("Postponed", "Rescheduled"))
    (u,), (c,) = res.units, res.claims
    assert (u.reason, u.leftover, c.status_claim) == (
        "status_unrecognised",
        "Postponed Rescheduled",
        "postponed",
    )


def test_date_cell_rules() -> None:
    res = one(date_cell="<td>25 Oct 2026</td>")
    assert (res.units[0].reason, res.units[0].leftover) == ("date_unparsed", "25 Oct 2026")
    assert res.claims == ()
    assert one(date="-").units[0].reason == "date_missing"
    month = one(date="Apr 2027", filter_date="2030-01-01")
    assert (month.units[0].outcome, month.claims[0].span.precision) == ("parsed", "month")
    assert one(date="2027", filter_date=None).claims[0].span.precision == "year"
    far = one(date="25 Oct 2032")
    assert (far.units[0].reason, far.units[0].relevance) == (
        "implausible_date",
        "in_or_after_window",
    )
    assert one(date="25 Oct 9999").units[0].reason == "date_unparsed"
    assert one(date="").units[0].relevance == "unknown"
    assert one(date="", label="Presidential Election 2030").units[0].relevance == "unknown"
    assert one(date="25 Oct and 8 Nov 2026").units[0].reason == "date_unparsed"
    for fd in ("2026-10-24", None):
        u = one(filter_date=fd).units[0]
        assert (u.outcome, u.reason) == ("partial", "filter_date_mismatch")


def test_columns_are_found_by_header_not_position() -> None:
    base = one().claims[0]
    row = (
        '<tr data-filter-date="2026-10-25">'
        '<td><a href="/odihr/elections/bulgaria">Bulgaria</a></td><td>Type X</td>'
        "<td><div>25 Oct 2026</div><span>Upcoming</span></td><td>-</td>"
        "<td>Presidential Election</td></tr>"
    )
    page = osce_page([row], ("Country", "Type", "Date", "Activity", "Election"))
    got = parse(page_of(page)).claims[0]
    assert got == base
    th = osce_row(
        date_cell='<th scope="row"><div>25 Oct 2026</div><span>Upcoming</span></th>'
    )
    assert parse(page_of(osce_page([th]))).claims[0] == base
    res = parse(page_of(osce_page([osce_row()], ("Date", "Country", "Election"))))
    assert res.coverage[0].outcome == "layout_not_recognised"


@pytest.mark.parametrize(
    ("headers", "cells", "detail"),
    [
        (
            (*HEAD, "Date"), ("25 Oct 2026", "25 Oct 2026"), "repeated header: date",
        ),
        ((*HEAD, "Date"), ("25 Oct 2026", "8 Nov 2026"), "repeated header: date"),
        (("Date", "Country", "Country", "Election", "Activity"), ("Chile", "Peru"),
         "repeated header: country"),
        (("Date", "Country", "Country", "Election", "Activity"), ("Chile", "Chile"),
         "repeated header: country"),
    ],
)
def test_repeated_headers_fail_the_page(
    headers: tuple[str, ...], cells: tuple[str, str], detail: str
) -> None:
    if headers[-1] == "Date":
        row = (
            f"<tr><td><div>{cells[0]}</div></td><td>Chile</td><td>Presidential Election</td>"
            f"<td>-</td><td><div>{cells[1]}</div></td></tr>"
        )
    else:
        row = (
            f"<tr><td><div>25 Oct 2026</div></td><td>{cells[0]}</td><td>{cells[1]}</td>"
            "<td>Presidential Election</td><td>-</td></tr>"
        )
    res = parse(page_of(osce_page([row], headers, beside="<p>1 Jan 2027 note</p>")))
    (cov,) = res.coverage
    assert (cov.outcome, cov.detail) == ("layout_not_recognised", detail)
    assert res.units == () and res.claims == () and res.notes == ()


def test_off_host_links_fall_back() -> None:
    res = one(activity="Mission", activity_href="https://example.invalid/r")
    assert res.claims[0].link == "https://odihr.osce.org/odihr/elections/bulgaria"
    assert res.units[0].outcome == "parsed"
    res = one(activity="Mission", activity_href="/node/1")
    assert res.claims[0].link == "https://odihr.osce.org/node/1"
    res = one(
        country_href="javascript:void(0)", activity="Mission", activity_href="//["
    )
    assert res.claims[0].link == URL
    assert (res.units[0].outcome, res.units[0].reason) == ("partial", "link_rejected")


def test_rows_that_do_not_fit() -> None:
    short = parse(page_of(osce_page(["<tr><td>a</td><td>b</td><td>c</td></tr>"])))
    assert short.units[0].reason == "too_few_cells" and short.claims == ()
    assert one(country="").units[0].reason == "place_missing"
    res = one(country="Narnia", country_href=None)
    assert (res.units[0].outcome, res.units[0].reason) == ("partial", "place_unregistered")
    exec_ = one(label="Lieutenant Governor election")
    assert (exec_.units[0].reason, exec_.units[0].leftover) == (
        "office_not_modelled",
        "Lieutenant Governor election",
    )
    assert exec_.claims == ()
    assert (
        one(activity="").units[0].text == "25 Oct 2026 Upcoming | Bulgaria | Presidential Election"
    )
    assert one(label="Presidential (Indirect) Election").claims[0].indirect is True
    assert one().claims[0].indirect is False
    unknown = one(label="Zorp")
    assert unknown.units[0].reason == "office_unrecognised"


def test_dated_text_beside_the_table_is_a_coverage_gap() -> None:
    res = parse(
        page_of(osce_page([osce_row()], beside="<p>12 Dec 2026 Croatia, Local Elections</p>"))
    )
    assert res.coverage[0].outcome == "ok" and len(res.units) == 1
    assert res.notes == (
        Reason("coverage_gap", "dated text beside the table: 12 Dec 2026 Croatia, Local Elections"),
    )
    assert parse(page_of(osce_page([osce_row()]))).notes == ()


def _detail(body: bytes) -> tuple[str, str]:
    res = parse(page_of(body))
    (cov,) = res.coverage
    assert res.units == () and res.claims == ()
    return cov.outcome, cov.detail


def test_broken_pages_get_an_outcome_never_units() -> None:
    good = osce_page([osce_row()])
    text = good.decode()
    table = text[text.index("<table>") : text.index("</table>") + 8]
    cases = {
        "no table": (b"<html><body><p>x</p></body></html>", DETAIL_NO_TABLE),
        "renamed": (osce_page([osce_row()], ("Date", "Country", "Election", "Act")), DETAIL_NO_TABLE),
        "duplicated": (
            text.replace(table, table + table).encode(),
            "2 tables with headers date, country, election, activity",
        ),
        "cut": (good[: len(good) // 2], "page does not end with </html>"),
        "empty": (b"", "page does not end with </html>"),
        "garbage": (b"\x00\xff garbage", "page does not end with </html>"),
        "no rows": (osce_page([]), "the table has no rows"),
    }
    for body, detail in cases.values():
        assert _detail(body) == ("layout_not_recognised", detail)


def test_download_failures_keep_their_own_outcome() -> None:
    body = fixture("osce", "elections.html", "2026-10-18")
    res = parse(raw_pages("osce", [(REQUEST, result(body, status=302, url=URL))]))
    assert res.coverage[0].outcome == "http_error" and res.units == ()
    res = parse(raw_pages("osce", [(REQUEST, result(body, outcome="challenge_page", url=URL))]))
    assert res.coverage[0].outcome == "challenge_page" and res.units == ()


def test_requests_and_fetch() -> None:
    assert [(r.key, r.url) for r in Osce().requests(WINDOW)] == [("elections", URL)]
    urls: list[str] = []

    class Stub:
        def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
            urls.append(url)
            return result(b"x", url=url)

    pages = list(Osce().fetch(WINDOW, Stub(), Deadline.after(60)))
    assert [p.request.key for p in pages] == ["elections"] and urls == [URL]


def _bare(row: str, which: str) -> str:
    """The row with the href removed from the activity or country anchor."""
    head, sep, tail = row.partition("<td><span class=\"elections-country\">")
    if which == "country":
        tail = tail.replace(' href="/odihr/elections/bulgaria"', "", 1)
    else:
        head = head.replace(' href="/node/1"', "")
        tail = tail.replace(' href="/node/1"', "")
    return head + sep + tail


def test_anchor_without_href_is_not_link_rejected() -> None:
    row = osce_row(activity="Mission", activity_href="/node/1")
    row = _bare(_bare(row, "country"), "activity")
    assert "href" not in row and "<a>" in row
    res = parse(page_of(osce_page([row])))
    assert (res.units[0].outcome, res.units[0].reason) == ("parsed", None)
    assert res.claims[0].link == URL
    mixed = _bare(osce_row(activity="Mission", activity_href="/node/1"), "activity")
    assert "/node/1" not in mixed
    res = parse(page_of(osce_page([mixed])))
    assert res.units[0].outcome == "parsed"
    assert res.claims[0].link == "https://odihr.osce.org/odihr/elections/bulgaria"


def test_blank_hrefs_are_missing_not_rejected() -> None:
    for blank in ("", "   "):
        res = one(country_href=blank, activity="Mission", activity_href=blank)
        assert (res.units[0].outcome, res.units[0].reason) == ("parsed", None)
        assert res.claims[0].link == URL
    res = one(country_href="  ", activity="Mission", activity_href="/node/1")
    assert res.claims[0].link == "https://odihr.osce.org/node/1"
    assert res.units[0].outcome == "parsed"


def test_ledger_count_rule_matches_adapter_headers() -> None:
    rule = COUNT_RULES["osce"]
    assert isinstance(rule, HeaderTableRowsRule)
    assert rule.headers == frozenset(osce.HEADERS)


def test_subdomain_and_port_links() -> None:
    ok = one(activity="Mission", activity_href="https://www.osce.org/x")
    assert (ok.units[0].outcome, ok.claims[0].link) == ("parsed", "https://www.osce.org/x")
    bad = one(country_href="https://odihr.osce.org:8443/x")
    assert (bad.units[0].outcome, bad.units[0].reason) == ("partial", "link_rejected")
    assert bad.claims[0].link == URL


def test_empty_badge_span_is_ignored() -> None:
    res = one(badges=("",))
    assert (res.units[0].outcome, res.units[0].reason, res.units[0].leftover) == (
        "parsed",
        None,
        "",
    )


@pytest.mark.parametrize(
    ("old", "new", "detail"),
    [
        ("<th>Date</th>", '<th colspan="2">Date</th>', "spanned header: date"),
        ("</tr></thead>", "</tr><tr><th>Note</th></tr></thead>", "thead has 2 rows"),
    ],
)
def test_irregular_headers_fail_the_page(old: str, new: str, detail: str) -> None:
    body = osce_page([osce_row()])
    assert parse(page_of(body)).units
    edited = body.decode().replace(old, new, 1).encode()
    assert edited != body
    res = parse(page_of(edited))
    (cov,) = res.coverage
    assert (cov.outcome, cov.detail) == ("layout_not_recognised", detail)
    assert res.units == () and res.claims == ()


def test_badge_scope() -> None:
    def got(**kw: object) -> tuple[str, str | None, str, str | None, str]:
        res = one(**kw)
        (u,) = res.units
        claim = res.claims[0] if res.claims else None
        return (
            u.outcome,
            u.reason,
            u.leftover,
            claim.status_claim if claim else None,
            claim.office_label if claim else "",
        )

    out = got(
        date_cell='<td><div><span>25 Oct</span> 2026</div><span class="badge">Upcoming</span></td>'
    )
    assert out[:4] == ("parsed", None, "", None)
    out = got(label='Presidential Election <span class="badge">Postponed</span>')
    assert out[:2] == ("parsed", None)
    assert out[3] == "postponed"
    assert out[4] == "Presidential Election Postponed"
    out = got(activity="<span>Report</span>")
    assert out[:2] == ("parsed", None) and out[3] is None
    out = got(activity='<span class="badge">Rescheduled</span>')
    assert out[:3] == ("partial", "status_unrecognised", "Rescheduled")
