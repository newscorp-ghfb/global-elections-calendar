from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from urllib.parse import urlsplit

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.ledger import COUNT_RULES, LinkTableCellsRule, check
from elections_calendar.model import DateSpan, Reason
from elections_calendar.sources import eeas
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.sources.eeas import MISSION, URL, Eeas
from elections_calendar.window import window_for
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages, result

_: Adapter = Eeas()

WINDOW = window_for(datetime(2026, 10, 18, tzinfo=UTC))
REGISTRIES = Registries.load()
REQUEST = Eeas().requests(WINDOW)[0]
BODY = fixture("eeas", "missions.html", "2026-10-18")
ALL = raw_pages("eeas", [(REQUEST, result(BODY, url=URL))])
RES = Eeas().parse(ALL, WINDOW, REGISTRIES)
CLAIMS = {c.claim_id: c for c in RES.claims}
PAGE = BODY.decode("utf-8")
BAD = "https://evil.example/x"


def parse(raw: RawPages = ALL) -> ParseResult:
    res = Eeas().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return res


def page_of(body: bytes | str) -> RawPages:
    data = body.encode() if isinstance(body, str) else body
    return raw_pages("eeas", [(REQUEST, result(data, url=URL))])


def mission(name: str, href: str | None = "/eom/") -> str:
    return name if href is None else f'<a href="{href}">{name}</a>'


def eeas_page(cells: Sequence[str], beside: str = "") -> str:
    row = "".join(f"<td>{c}</td>" for c in cells)
    return (
        f"<!doctype html><html><body><div>{beside}<table><tbody><tr>{row}</tr></tbody>"
        "</table></div></body></html>"
    )


def cells_of(*cells: str) -> ParseResult:
    return parse(page_of(eeas_page(cells)))


def shape(res: ParseResult) -> list[tuple[str, str | None]]:
    return [(u.outcome, u.reason) for u in res.units]


def table_count(n: int) -> str:
    return f"{n} tables with EOM links"


def test_fixture_ledger_balances() -> None:
    res = parse(ALL)
    report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 23, "partial": 0, "unparsed": 0, "ignored": 11}
    assert report.ignored_reasons == {"year_heading": 4, "empty_cell": 7}
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [("missions", "ok", 34)]
    assert res.notes == ()
    assert [u.unit_id for u in res.units][:2] == ["eeas:missions/r1c1", "eeas:missions/r1c2"]
    assert res.units[-1].unit_id == "eeas:missions/r17c2"


def test_fixture_claims() -> None:  # v1 root cause 8: missions are years, never dates
    assert {(c.span.precision, c.date_meaning) for c in RES.claims} == {("year", "unknown")}
    assert Counter(c.span.year for c in RES.claims) == {2026: 5, 2025: 7, 2024: 4, 2023: 7}
    # fmt: off
    assert [c.place_id for c in RES.claims] == [
        "iso:CO", "iso:PE", "iso:BD", "iso:ZM", "iso:ST", "iso:MW", "iso:BO", "iso:PH",
        "iso:GY", "x:kosovo", "iso:EC", "iso:HN", "iso:LK", "iso:MZ", "iso:JO", "iso:SN",
        "iso:GT", "iso:LR", "iso:MV", "iso:NG", "iso:PY", "iso:SL", "iso:ZW",
    ]
    assert {
        (
            c.office_class, c.aggregate, c.kind, c.level, c.institution, c.evidence_kind,
            c.date_status, c.jurisdiction, c.jurisdiction_kind, c.round, c.source_event_id,
            c.status_claim, c.previous_date_text, c.indirect, c.office_label, c.source,
        )
        for c in RES.claims
    } == {
        (
            "general", True, "aggregate", "unknown", None, "observation", "unknown", None,
            "nationwide", None, None, None, None, False, "EU election observation mission",
            "eeas",
        )
    }
    # fmt: on
    assert {urlsplit(c.link).hostname for c in RES.claims} == {"www.eeas.europa.eu"}


def test_one_claim_field_by_field() -> None:
    c = CLAIMS["eeas:missions/r2c1#0"]
    assert c.place_id == "iso:CO" and c.unit_id == "eeas:missions/r2c1"
    assert c.span == DateSpan.of_year(2026)
    assert c.link == "https://www.eeas.europa.eu/eom-colombia-2026_en"
    assert c.date_text == "2026" and c.date_meaning == "unknown"
    assert c.place_raw == "Colombia" and c.office_label == "EU election observation mission"
    assert c.office_class == "general" and c.evidence_kind == "observation"


def test_cell_kinds() -> None:
    a = mission("EOM Chile 2026", "/x/")
    res = cells_of(a, a)
    assert shape(res) == [("parsed", None), ("ignored", "duplicate")]
    assert res.units[1].duplicate_of == "eeas:missions/r1c1" and len(res.claims) == 1
    assert res.units[0].duplicate_of is None
    res = cells_of(a, mission("EOM Peru 2026", "/y/"), a)
    assert res.units[2].duplicate_of == "eeas:missions/r1c1"
    # same href, different country or year: two claims
    res = cells_of(mission("EOM Chile 2026", "/x/"), mission("EOM Peru 2026", "/x/"))
    assert shape(res) == [("parsed", None)] * 2 and len(res.claims) == 2
    res = cells_of(mission("EOM Chile 2026", "/x/"), mission("EOM Chile 2025", "/x/"))
    assert shape(res) == [("parsed", None)] * 2 and len(res.claims) == 2
    # same text, different link: two claims
    res = cells_of(mission("EOM Chile 2026", "/x/"), mission("EOM Chile 2026", "/y/"))
    assert shape(res) == [("parsed", None)] * 2 and len(res.claims) == 2
    # a cell that gave no claim reserves nothing
    res = cells_of(mission("EOM Chile 2040", "/x/"), mission("EOM Chile 2026", "/x/"))
    assert shape(res) == [("unparsed", "implausible_date"), ("parsed", None)]
    res = cells_of(mission("EOM Narnia 2040", "/x/"), mission("EOM Narnia 2040", "/x/"))
    assert shape(res) == [("unparsed", "implausible_date")] * 2
    # the claim link is compared: a rejected href falls back to URL
    res = cells_of(mission("EOM Chile 2026", None), mission("EOM Chile 2026", BAD))
    assert shape(res) == [("parsed", None), ("ignored", "duplicate")]
    # a duplicate of a partial claim is still a duplicate
    res = cells_of(mission("EOM Narnia 2026"), mission("EOM Narnia 2026"))
    assert shape(res) == [("partial", "place_unregistered"), ("ignored", "duplicate")]

    res = cells_of("Election Observation Missions archive", mission("EOM Chile 2026", "/x/"))
    assert shape(res) == [("unparsed", "unrecognised_cell"), ("parsed", None)]
    res = cells_of(mission("EOM Narnia 2026"))
    assert shape(res) == [("partial", "place_unregistered")]
    assert res.claims[0].place_id.startswith("unknown:")
    res = cells_of(mission("EOM Peru 2026"), mission("EOM Chile 2026", None))
    assert res.claims[1].link == URL and shape(res)[1] == ("parsed", None)
    res = cells_of("", "&nbsp;", "20266", mission("EOM  2026"), "2026", mission("EOM Peru 2026"))
    assert shape(res) == [
        ("ignored", "empty_cell"),
        ("ignored", "empty_cell"),
        ("unparsed", "unrecognised_cell"),
        ("unparsed", "unrecognised_cell"),
        ("ignored", "year_heading"),
        ("parsed", None),
    ]
    th = eeas_page([mission("EOM Chile 2026")]).replace("<tr>", "<tr><th>2026</th>")
    res = parse(page_of(th))
    assert shape(res) == [("ignored", "year_heading"), ("parsed", None)]
    assert res.units[0].unit_id == "eeas:missions/r1c1"
    assert res.units[1].unit_id == "eeas:missions/r1c2"


def test_cell_checks_are_ordered() -> None:
    res = cells_of(mission("EOM --- 2026", BAD))
    assert shape(res) == [("unparsed", "place_missing")]
    res = cells_of(mission("EOM --- 2040", BAD))
    assert shape(res) == [("unparsed", "place_missing")]
    res = cells_of(mission("EOM Narnia 2040", BAD))
    assert shape(res) == [("unparsed", "implausible_date")]
    res = cells_of(mission("EOM Narnia 2026", BAD))
    assert shape(res) == [("partial", "place_unregistered")]
    res = cells_of(mission("EOM Chile 2026", BAD))
    assert shape(res) == [("partial", "link_rejected")] and res.claims[0].link == URL
    res = cells_of(mission("EOM Chile 2040", BAD))
    assert shape(res) == [("unparsed", "implausible_date")]


def test_mission_years_outside_the_model_are_outcomes() -> None:  # B-T07
    for year in ("0000", "1899", "2200", "9999", "2020", "2032"):
        res = cells_of(mission(f"EOM Chile {year}"))
        assert shape(res) == [("unparsed", "implausible_date")], year
        assert res.claims == ()
    for near in (2021, 2026, 2031):
        res = cells_of(mission(f"EOM Chile {near}"))
        assert shape(res) == [("parsed", None)]
        assert res.claims[0].span == DateSpan.of_year(near)
        assert res.claims[0].date_text == str(near)


def test_off_host_links_fall_back() -> None:
    res = cells_of(mission("EOM Chile 2026", "//example.invalid/eom"))
    assert res.claims[0].link == URL and shape(res) == [("partial", "link_rejected")]
    res = cells_of(mission("EOM Chile 2026", "http://[bad"))
    assert res.claims[0].link == URL and shape(res) == [("partial", "link_rejected")]
    res = cells_of(mission("EOM Chile 2026", "/eom-chile/"))
    assert res.claims[0].link == "https://www.eeas.europa.eu/eom-chile/"
    assert shape(res) == [("parsed", None)]
    for missing in ("", "   "):
        res = cells_of(mission("EOM Chile 2026", missing))
        assert res.claims[0].link == URL and shape(res) == [("parsed", None)]
    res = cells_of(mission("EOM Peru 2026"), "<a>EOM Chile 2026</a>")
    assert res.claims[1].link == URL and shape(res)[1] == ("parsed", None)
    # the first anchor of the cell wins
    res = cells_of('<a href="/a/">EOM Chile</a> <a href="/b/">2026</a>', mission("EOM Peru 2026"))
    assert res.claims[0].link == "https://www.eeas.europa.eu/a/"
    res = cells_of('<a>EOM Chile</a> <a href="/b/">2026</a>', mission("EOM Peru 2026"))
    assert res.claims[0].link == URL and shape(res)[0] == ("parsed", None)
    # no claim, so no link_rejected
    res = cells_of(mission("EOM Chile 2040", BAD))
    assert shape(res) == [("unparsed", "implausible_date")]


def test_a_new_year_heading_is_ignored_and_its_missions_parsed() -> None:
    row = f"<tr><td><h3>2027</h3></td><td>{mission('EOM Chile 2027')}</td></tr>"
    page = PAGE.replace("<tbody>", "<tbody>" + row, 1)
    assert page != PAGE
    res = parse(page_of(page))
    assert shape(res)[:2] == [("ignored", "year_heading"), ("parsed", None)]
    assert res.claims[0].span == DateSpan.of_year(2027) and res.claims[0].place_id == "iso:CL"
    assert len(res.claims) == 24


def test_relevance_comes_from_the_cell_text() -> None:
    res = cells_of(mission("EOM Chile 2026"), mission("EOM Chile 2020"), "Notes 2032")
    assert [u.relevance for u in res.units] == [
        "in_or_after_window",
        "before_window",
        "in_or_after_window",
    ]


def test_dated_text_beside_the_table_is_a_coverage_gap() -> None:
    page = eeas_page([mission("EOM Chile 2026")], beside="<p>Updated 2026</p>")
    res = parse(page_of(page))
    assert res.coverage[0].outcome == "ok" and len(res.units) == 1
    assert res.notes == (Reason("coverage_gap", "dated text beside the table: Updated 2026"),)
    assert RES.notes == ()


def test_broken_pages_get_an_outcome_never_units() -> None:
    half = BODY[: len(BODY) // 2]
    for body in (half, b"", b"\x00\xff garbage", "<html><body><p>x</p>"):
        res = parse(page_of(body))
        (cov,) = res.coverage
        assert res.units == () and res.claims == () and res.notes == ()
        assert (cov.outcome, cov.detail) == (
            "layout_not_recognised",
            "page does not end with </html>",
        )
    res = parse(page_of("<html><body><p>x</p></body></html>"))
    assert (res.coverage[0].outcome, res.coverage[0].detail) == (
        "layout_not_recognised",
        table_count(0),
    )
    start = PAGE.index("<table")
    end = PAGE.index("</table>", start) + len("</table>")
    res = parse(page_of(PAGE[:end] + PAGE[start:end] + PAGE[end:]))
    assert res.coverage[0].detail == table_count(2)
    assert res.units == () and res.claims == () and res.notes == ()


def test_tables_are_counted_as_the_ledger_counts_them() -> None:
    link = mission("EOM Chile 2026")
    inner = f"<table><tr><td>{link}</td></tr></table>"
    # a link inside an inner table belongs to that table only
    page = f"<html><body><table><tr><td>{inner}</td><td>x</td></tr></table></body></html>"
    res = parse(page_of(page))
    assert res.coverage[0].outcome == "ok"
    assert [u.unit_id for u in res.units] == ["eeas:missions/r1c1"]
    assert len(res.claims) == 1
    # a second link in the outer table too: two tables
    outer = f"<table><tr><td>{inner}</td><td>{mission('EOM Peru 2026')}</td></tr></table>"
    res = parse(page_of(f"<html><body>{outer}</body></html>"))
    assert res.coverage[0].detail == table_count(2)
    # two links in one table count once
    assert len(cells_of(link, mission("EOM Peru 2026")).claims) == 2
    # a link whose whole text does not match is not an EOM link
    res = parse(page_of(eeas_page(['<a href="/x/">EOM Chile 2026 archive</a>'])))
    assert res.coverage[0].detail == table_count(0)
    # a link outside every table is not counted
    res = parse(page_of(f"<html><body>{link}</body></html>"))
    assert res.coverage[0].detail == table_count(0)


def test_header_rows_are_units_too() -> None:
    page = (
        "<html><body><table><thead><tr><th>2026</th></tr><tr><th>"
        f"{mission('EOM Chile 2026')}</th></tr></thead><tbody><tr><td>{mission('EOM Peru 2026')}"
        "</td></tr></tbody></table></body></html>"
    )
    res = parse(page_of(page))
    assert [u.unit_id for u in res.units] == [f"eeas:missions/r{i}c1" for i in (1, 2, 3)]
    assert shape(res) == [("ignored", "year_heading"), ("parsed", None), ("parsed", None)]


def test_hostile_page_content_never_raises() -> None:
    hostile = [
        mission("EOM Chile 0000"),
        mission("EOM Chile 9999"),
        mission("EOM Chile 2026", "http://[::1"),
        mission("EOM Chile 2026", "https://user:pw@www.eeas.europa.eu:99999/"),
        "\u0000�",
        "",
        mission("EOM � 2026"),
    ]
    res = cells_of(mission("EOM Chile 2026"), *hostile)
    assert len(res.units) == len(hostile) + 1


def test_requests_and_fetch() -> None:
    assert [(r.key, r.url) for r in Eeas().requests(WINDOW)] == [("missions", URL)]
    assert URL == "https://www.eeas.europa.eu/eeas/eu-election-observation-missions-1_en"
    assert eeas.HOSTS == ("eeas.europa.eu",) and Eeas.source == "eeas"
    urls: list[str] = []

    class Stub:
        def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
            urls.append(url)
            return result(b"x", url=url)

    pages = list(Eeas().fetch(WINDOW, Stub(), Deadline.after(60)))
    assert [p.request.key for p in pages] == ["missions"] and urls == [URL]


def test_ledger_count_rule_matches_adapter_pattern() -> None:
    rule = COUNT_RULES["eeas"]
    assert isinstance(rule, LinkTableCellsRule)
    assert rule.link_text == MISSION.pattern
