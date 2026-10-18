"""Helpers shared by the table-page adapters (Plan 2b): rows, cells, headers, links.

Nothing here knows a source. ``own_rows`` and ``row_cells`` keep to the table and row
they are given, so a table nested in a cell never leaks rows or cells into its host.
"""

import re
from collections.abc import Collection, Sequence
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag
from bs4.element import Comment, NavigableString, PreformattedString

from elections_calendar.text import collapse_ws

_YEAR = re.compile(r"\b(?:19|20|21)\d{2}\b")
_HIDDEN = ("script", "style", "noscript", "template")
_BESIDE_MAX = 80


def complete_html(text: str) -> bool:
    """Whether ``text`` ends with ``</html>``, ignoring trailing whitespace and HTML comments."""
    text = text.rstrip()
    while text.endswith("-->"):
        start = text.rfind("<!--")
        if start < 0:
            break
        text = text[:start].rstrip()
    return text.casefold().endswith("</html>")


def cell_text(tag: Tag) -> str:
    return collapse_ws(tag.get_text(" "))


def row_cells(tr: Tag) -> list[Tag]:
    """The row's own ``td`` and ``th`` children, in order (P41)."""
    return [c for c in tr.find_all(["td", "th"], recursive=False) if isinstance(c, Tag)]


def own_rows(table: Tag, *, head: bool = False) -> list[Tag]:
    """Each ``tr`` whose nearest ``table`` is ``table``; ``thead`` rows only if ``head``."""
    rows: list[Tag] = []
    for tr in table.find_all("tr"):
        in_head = False
        nearest: Tag | None = None
        for parent in tr.parents:
            if parent.name == "table":
                nearest = parent
                break
            in_head = in_head or parent.name == "thead"
        if nearest is table and (head or not in_head):
            rows.append(tr)
    return rows


def header_cells(table: Tag) -> list[str]:
    """The casefolded text of each ``th`` in the table's own ``thead``."""
    return [
        cell_text(th).casefold()
        for th in table.select("thead th")
        if th.find_parent("table") is table
    ]


def header_tables(soup: BeautifulSoup, headers: Collection[str]) -> list[Tag]:
    """In document order, each table whose header cells include every header."""
    return [
        table
        for table in soup.find_all("table")
        if isinstance(table, Tag) and set(headers) <= set(header_cells(table))
    ]


def header_columns(
    table: Tag, headers: Collection[str]
) -> tuple[dict[str, int], tuple[str, ...]]:
    """The column of each header that appears once, and the headers that appear more than once."""
    cells = header_cells(table)
    columns: dict[str, int] = {}
    repeated: list[str] = []
    for header in headers:
        at = [i for i, cell in enumerate(cells) if cell == header]
        if len(at) == 1:
            columns[header] = at[0]
        elif len(at) > 1:
            repeated.append(header)
    return columns, tuple(repeated)


def source_link(base: str, href: object, hosts: Collection[str]) -> str | None:
    """``href`` resolved against ``base`` if it is an ``https`` link on one of ``hosts`` (P44).

    ``None`` for a missing or blank href, another scheme, credentials, a port other than 443
    and any host that is not a listed host or one of its subdomains.
    """
    if not isinstance(href, str) or not href.strip():
        return None
    try:
        url = urljoin(base, href.strip())
        parts = urlsplit(url)
        port = parts.port
        host = (parts.hostname or "").encode("idna").decode("ascii")
    except (ValueError, UnicodeError):
        return None
    if parts.scheme != "https" or parts.username is not None or parts.password is not None:
        return None
    if port not in (None, 443) or not host:
        return None
    if not any(host == h or host.endswith("." + h) for h in hosts):
        return None
    return url


def anchor_href(anchor: object) -> str | None:
    """The ``href`` of ``anchor`` as written, if it is a tag with a non-blank string href."""
    if not isinstance(anchor, Tag):
        return None
    href = anchor.get("href")
    return href if isinstance(href, str) and href.strip() else None


def dated_text_beside(table: Tag) -> str | None:
    """The first text next to ``table`` (in its parent) that holds a year, cut to 80 characters.

    Comments, and text inside the table, a script, a style, a noscript or a template, are
    left out (P40).
    """
    parent = table.parent
    if parent is None:
        return None
    for text in parent.find_all(string=True):
        if not isinstance(text, NavigableString) or isinstance(text, (Comment, PreformattedString)):
            continue
        if any(p is table for p in text.parents) or text.find_parent(_HIDDEN) is not None:
            continue
        clean = collapse_ws(text)
        if _YEAR.search(clean):
            return clean[:_BESIDE_MAX]
    return None


def one_header_table(
    text: str, headers: Sequence[str]
) -> tuple[Tag, dict[str, int], list[Tag]] | str:
    """The one table with ``headers``, its columns and its body rows; else why the layout fails.

    The failure is the ``layout_not_recognised`` detail: the page is cut, there is not exactly
    one such table, a header is repeated, or the table has no rows.
    """
    if not complete_html(text):
        return "page does not end with </html>"
    tables = header_tables(BeautifulSoup(text, "lxml"), headers)
    if len(tables) != 1:
        return f"{len(tables)} tables with headers {', '.join(headers)}"
    table = tables[0]
    columns, repeated = header_columns(table, headers)
    if repeated:
        return "repeated header: " + ", ".join(repeated)
    rows = own_rows(table)
    if not rows:
        return "the table has no rows"
    return table, columns, rows
