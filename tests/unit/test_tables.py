"""The shared table helpers of the single-page table sources (Plan 2b)."""

import pytest
from bs4 import BeautifulSoup, Tag

from elections_calendar.sources.tables import (
    anchor_href,
    cell_text,
    complete_html,
    dated_text_beside,
    header_cells,
    header_columns,
    header_tables,
    one_header_table,
    own_rows,
    row_cells,
    source_link,
)


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def first_table(html: str) -> Tag:
    table = soup(html).find("table")
    assert isinstance(table, Tag)
    return table


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("<html></html>", True),
        ("<html></html>\n  ", True),
        ("<html></HTML>", True),
        ("<html></html><!-- cache 3 -->\n", True),
        ("<html></html>\n<!-- a -->\n<!-- b -->  \n", True),
        ("<html></html><!-- unclosed", False),
        ("<html><body></body>", False),
        ("<html></html><p>x</p>", False),
        ("", False),
    ],
)
def test_complete_html(text: str, expected: bool) -> None:
    assert complete_html(text) is expected


def test_cell_text_collapses_whitespace() -> None:
    td = first_table("<table><tr><td> a<b>b</b>\n\xa0c </td></tr></table>").td
    assert td is not None and cell_text(td) == "a b c"


def test_own_rows() -> None:
    nested = first_table(
        "<table><tr><td>a<table><tr><td>x</td></tr><tr><td>y</td></tr></table></td></tr>"
        "<tr><td>b</td></tr></table>"
    )
    assert [cell_text(r) for r in own_rows(nested)] == ["a x y", "b"]
    bare = first_table("<table><tr><td>1</td></tr><tr><td>2</td></tr><tr><td>3</td></tr></table>")
    assert len(own_rows(bare)) == 3
    headed = first_table(
        "<table><thead><tr><th>H</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>"
    )
    assert [cell_text(r) for r in own_rows(headed)] == ["1"]
    assert [cell_text(r) for r in own_rows(headed, head=True)] == ["H", "1"]


def test_row_cells() -> None:
    table = first_table(
        '<table><tr><th scope="row">Chile</th><td>May 2026</td>'
        "<td><table><tr><td>x</td></tr></table></td></tr></table>"
    )
    cells = row_cells(own_rows(table)[0])
    assert [c.name for c in cells] == ["th", "td", "td"]
    assert cell_text(cells[0]) == "Chile"


def test_header_cells_are_the_tables_own() -> None:
    table = first_table(
        "<table><thead><tr><th>Date<br>of  Vote</th><th>"
        "<table><thead><tr><th>Inner</th></tr></thead></table></th></tr></thead></table>"
    )
    assert header_cells(table) == ["date of vote", "inner"]  # the nested th is no entry of its own


def test_header_tables_match_whole_header_texts() -> None:
    page = soup(
        "<table><thead><tr><th>Start date</th><th>Country</th></tr></thead></table>"
        "<table><thead><tr><th>Date</th><th>Country</th></tr></thead></table>"
        "<table><thead><tr><th>Date</th><th>Country</th><th>X</th></tr></thead></table>"
        "<table><tr><th>Date</th><th>Country</th></tr></table>"
    )
    assert len(header_tables(page, ["date", "country"])) == 2
    assert len(header_tables(page, ["start date"])) == 1
    long = soup(
        "<table><thead><tr><th>Expected date<br>of next elections</th></tr></thead></table>"
    )
    assert len(header_tables(long, ["expected date of next elections"])) == 1


def head_table(*heads: str) -> Tag:
    ths = "".join(f"<th>{h}</th>" for h in heads)
    return first_table(f"<table><thead><tr>{ths}</tr></thead></table>")


WANTED = ("date", "country", "election", "activity")


@pytest.mark.parametrize(
    ("heads", "columns", "repeated"),
    [
        (
            ("Date", "Country", "Election", "Activity"),
            {"date": 0, "country": 1, "election": 2, "activity": 3},
            (),
        ),
        (
            ("Country", "Activity", "Date", "Election"),
            {"country": 0, "activity": 1, "date": 2, "election": 3},
            (),
        ),
        (
            ("Date", "Country", "Type", "Election", "Activity"),
            {"date": 0, "country": 1, "election": 3, "activity": 4},
            (),
        ),
        (
            ("Type", "Date", "Country", "Election", "Activity"),
            {"date": 1, "country": 2, "election": 3, "activity": 4},
            (),
        ),
        (("Date", "Country", "Election", "Activity", "Date"), {"country": 1, "election": 2, "activity": 3}, ("date",)),
        (("Date", "Country", "Country", "Election", "Activity"), {"date": 0, "election": 3, "activity": 4}, ("country",)),
        (("Date", "Country", "Country", "Election", "Activity", "Date"), {"election": 3, "activity": 4}, ("date", "country")),
        (("", "Date", "", "Country", "Election", "Activity"), {"date": 1, "country": 3, "election": 4, "activity": 5}, ()),
    ],
)
def test_header_columns(
    heads: tuple[str, ...], columns: dict[str, int], repeated: tuple[str, ...]
) -> None:
    assert header_columns(head_table(*heads), WANTED) == (columns, repeated)


BASE = "https://www.eeas.europa.eu/eeas/x_en"
HOSTS = ("eeas.europa.eu",)


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        ("/eom-colombia-2026_en", "https://www.eeas.europa.eu/eom-colombia-2026_en"),
        ("  /eom-colombia-2026_en ", "https://www.eeas.europa.eu/eom-colombia-2026_en"),
        ("//www.eeas.europa.eu/eom-peru-2026_en", "https://www.eeas.europa.eu/eom-peru-2026_en"),
        ("https://eeas.europa.eu/a", "https://eeas.europa.eu/a"),
        ("https://WWW.EEAS.EUROPA.EU:443/a", "https://WWW.EEAS.EUROPA.EU:443/a"),
        ("//example.invalid/x", None),
        ("https://eeas.europa.eu.evil.example/a", None),
        ("https://evileeas.europa.eu/a", None),
        ("http://www.eeas.europa.eu/a", None),
        ("javascript:void(0)", None),
        ("mailto:x@eeas.europa.eu", None),
        ("https://user:pw@www.eeas.europa.eu/a", None),
        ("https://user@www.eeas.europa.eu/a", None),
        ("https://:pw@www.eeas.europa.eu/a", None),
        ("https://www.eeas.europa.eu:8443/a", None),
        ("//[", None),
        ("https://www.eeas.europa.eu:99999/a", None),
        ("https://www.eeas.europa.eu../a", None),
        ("https://" + "a" * 70 + ".eeas.europa.eu/a", None),
        (None, None),
        ("", None),
        ("  ", None),
        (["a"], None),
    ],
)
def test_source_link(href: object, expected: str | None) -> None:
    assert source_link(BASE, href, HOSTS) == expected


def test_source_link_compares_idna_hosts() -> None:
    muenchen = "https://münchen.example/a"
    assert source_link(BASE, muenchen, ("xn--mnchen-3ya.example",)) == muenchen
    assert source_link(BASE, "https://xn--mnchen-3ya.example/a", ("example",)) is not None
    assert source_link(BASE, muenchen, ("eeas.europa.eu",)) is None


def test_dated_text_beside() -> None:
    table = "<table><tr><td>x</td></tr></table>"
    one = first_table(f"<div><p>12  Dec 2026 Croatia,\n Local</p>{table}</div>")
    assert dated_text_beside(one) == "12 Dec 2026 Croatia, Local"
    after = first_table(f"<div>{table}<p>Updated 2027</p></div>")
    assert dated_text_beside(after) == "Updated 2027"
    long = first_table(f"<div><p>2026 {'x' * 200}</p>{table}</div>")
    assert dated_text_beside(long) == ("2026 " + "x" * 200)[:80]
    inside = first_table("<div><a>See All</a><table><tr><td>2026</td></tr></table></div>")
    assert dated_text_beside(inside) is None
    for hidden in (
        "<script>var y = 2026;</script>",
        "<style>/* 2026 */</style>",
        "<noscript>2026</noscript>",
        "<template>2026</template>",
        "<!-- 2026 -->",
    ):
        assert dated_text_beside(first_table(f"<div>{hidden}{table}</div>")) is None, hidden
    assert dated_text_beside(first_table(f"<div><p>Room 1850 and 21000</p>{table}</div>")) is None
    assert dated_text_beside(first_table(table)) is None


def _page(heads: str, rows: str = "<tr><td>x</td></tr>", tables: int = 1) -> str:
    table = f"<table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table>"
    return f"<html><body>{table * tables}</body></html>"


_HEADS = "".join(f"<th>{h}</th>" for h in ("A", "B"))


def test_one_header_table_returns_table_columns_and_rows() -> None:
    got = one_header_table(_page(_HEADS, "<tr><td>1</td></tr><tr><td>2</td></tr>"), ("a", "b"))
    assert not isinstance(got, str)
    table, columns, rows = got
    assert table.name == "table" and columns == {"a": 0, "b": 1} and len(rows) == 2


@pytest.mark.parametrize(
    ("text", "detail"),
    [
        ("<html><body></body>", "page does not end with </html>"),
        ("<html><body><p>x</p></body></html>", "0 tables with headers a, b"),
        (_page(_HEADS, tables=2), "2 tables with headers a, b"),
        (_page("<th>A</th><th>B</th><th>A</th>"), "repeated header: a"),
        (_page("<th>A</th><th>B</th><th>A</th><th>B</th>"), "repeated header: a, b"),
        (_page(_HEADS, ""), "the table has no rows"),
    ],
)
def test_one_header_table_failure_details(text: str, detail: str) -> None:
    assert one_header_table(text, ("a", "b")) == detail


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<a>x</a>", None),
        ('<a href="">x</a>', None),
        ('<a href="  ">x</a>', None),
        ('<a href="/x">x</a>', "/x"),
        ('<a href=" /x ">x</a>', " /x "),
    ],
)
def test_anchor_href(html: str, expected: str | None) -> None:
    assert anchor_href(soup(html).find("a")) == expected


def test_anchor_href_needs_a_tag() -> None:
    assert anchor_href(None) is None
    assert anchor_href("/x") is None
