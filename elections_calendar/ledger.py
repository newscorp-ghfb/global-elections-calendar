"""The ledger: unit accounting and the independent discovery check (spec §9.1, §7).

Every input unit of a source gets exactly one outcome. ``check`` verifies an
adapter's accounting (``ledger_mismatch``) and re-discovers each page's units
with a parser that shares no code with any adapter (``discovery_mismatch``),
so an adapter that silently drops rows is caught. The counting rules live
here, not in the adapters, so an adapter cannot pick its own container (P6).
"""

import json
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import get_args

from elections_calendar.model import (
    IGNORED_REASONS,
    MAX_DETAIL,
    FetchOutcome,
    InputUnit,
    Outcome,
    Reason,
    ReasonCode,
    Relevance,
)
from elections_calendar.sources.base import (
    PageCoverage,
    ParseResult,
    RawPage,
    RawPages,
    page_failure,
)

_USABLE = ("parsed", "partial")
_PAGE_OUTCOMES = ("ok", "valid_empty")
_DOWNLOAD_OUTCOMES = frozenset(get_args(FetchOutcome)) - {"ok"}  # what page_failure can return
_NEEDS_A_FAILED_DOWNLOAD = ("not_published_yet", "required_year_missing")


@dataclass(frozen=True, slots=True)
class TableRowsRule:
    """Units are the body rows of the ``<table>`` with this id: ``r1``, ``r2``, ..."""

    table_id: str


@dataclass(frozen=True, slots=True)
class SectionItemsRule:
    """Units are the ``<li>`` items under each ``<h2>`` section of the HTML found at
    ``json_text_path`` in a JSON body; sections in ``stop_ids`` are skipped.
    ``revid_path`` locates the page revision, which then belongs in the unit prefix.
    """

    stop_ids: frozenset[str]
    json_text_path: tuple[str, ...] = ()
    revid_path: tuple[str, ...] | None = None
    box_classes: frozenset[str] = frozenset()  # items in a table or div with one are no units


@dataclass(frozen=True, slots=True)
class HeaderTableRowsRule:
    """Units are the body rows (``r1``, ...) of the one table whose ``thead`` has every one of
    ``headers`` (casefolded header texts); each must occur exactly once in it.
    """

    headers: frozenset[str]


@dataclass(frozen=True, slots=True)
class HeadingTablesRule:
    """Units are the rows of the one table under each ``<h2>`` named in ``sections``, a pair of
    (casefolded heading text, unit slug): ``<slug>-r1``, ``<slug>-r2``, ... Every ``tr`` counts.
    """

    sections: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class LinkTableCellsRule:
    """Units are the cells (``r<i>c<j>``, ``td`` and ``th``) of the one table that holds a link
    whose whole text matches the pattern ``link_text``.
    """

    link_text: str


CountRule = (
    TableRowsRule | SectionItemsRule | HeaderTableRowsRule | HeadingTablesRule | LinkTableCellsRule
)

COUNT_RULES: Mapping[str, CountRule] = {
    "electionguide": TableRowsRule("electionsTable"),
    "osce": HeaderTableRowsRule(frozenset({"date", "country", "election", "activity"})),
    "ipu": HeaderTableRowsRule(
        frozenset(
            {
                "country",
                "chamber",
                "principal mode of designation of members",
                "expected date of next elections",
            }
        )
    ),
    "wikipedia": SectionItemsRule(
        frozenset(
            {
                "See_also",
                "References",
                "Notes",
                "External_links",
                "Footnotes",
                "Further_reading",
                "Sources",
                "Citations",
                "Bibliography",
            }
        ),
        ("parse", "text"),
        ("parse", "revid"),
        frozenset({"ambox", "metadata", "navbox"}),
    ),
}


class _TableRows(HTMLParser):
    """``tr`` tags whose innermost open table is the target, outside its ``thead``."""

    def __init__(self, table_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.table_id = table_id
        self.tables: list[list[bool]] = []  # per open table: [is the target, inside its thead]
        self.rows = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.tables.append([dict(attrs).get("id") == self.table_id, False])
        elif self.tables:
            if tag == "thead":
                self.tables[-1][1] = True
            elif tag == "tr" and self.tables[-1][0] and not self.tables[-1][1]:
                self.rows += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "table" and self.tables:
            self.tables.pop()
        elif tag == "thead" and self.tables:
            self.tables[-1][1] = False


def _words(pieces: list[str]) -> str:
    return " ".join(" ".join(pieces).split())


@dataclass(slots=True)
class _HeadTable:
    in_head: bool = False
    th: list[str] | None = None  # data of the open th in the thead
    heads: list[str] = field(default_factory=list)
    rows: int = 0


class _HeaderTables(HTMLParser):
    """Every table's own ``thead`` header texts and body row count."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.open: list[_HeadTable] = []
        self.done: list[_HeadTable] = []

    def _end_th(self, table: _HeadTable) -> None:
        if table.th is not None:
            table.heads.append(_words(table.th).casefold())
            table.th = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.open.append(_HeadTable())
            return
        if not self.open:
            return
        table = self.open[-1]
        if tag in ("th", "td", "tr", "thead", "tbody", "tfoot"):
            self._end_th(table)
        if tag == "thead":
            table.in_head = True
        elif tag in ("tbody", "tfoot"):
            table.in_head = False
        elif tag == "tr" and not table.in_head:
            table.rows += 1
        elif tag == "th" and table.in_head:
            table.th = []

    def handle_endtag(self, tag: str) -> None:
        if not self.open:
            return
        table = self.open[-1]
        if tag == "table":
            self._end_th(table)
            self.done.append(self.open.pop())
        elif tag in ("th", "tr"):
            self._end_th(table)
        elif tag == "thead":
            self._end_th(table)
            table.in_head = False

    def handle_data(self, data: str) -> None:
        if self.open and self.open[-1].th is not None:
            self.open[-1].th.append(data)


class _Regions(HTMLParser):
    """Per table: the cells in each row and its links; per ``h2``: its text and the top-level
    tables before the next ``h2``. A row, cell or link belongs to the innermost open table.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[int]] = []  # per table: cells in each tr
        self.open: list[int] = []
        self.h2: list[str] | None = None
        self.region: int | None = None
        self.headings: list[tuple[str, list[int]]] = []
        self.links: list[tuple[int, str]] = []
        self.a: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self.h2, self.region = [], None
        elif tag == "table":
            self.tables.append([])
            if not self.open and self.region is not None:
                self.headings[self.region][1].append(len(self.tables) - 1)
            self.open.append(len(self.tables) - 1)
        elif not self.open:
            return
        elif tag == "tr":
            self.tables[self.open[-1]].append(0)
        elif tag in ("td", "th") and self.tables[self.open[-1]]:
            self.tables[self.open[-1]][-1] += 1
        elif tag == "a":
            self.a = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2" and self.h2 is not None:
            self.headings.append((_words(self.h2).casefold(), []))
            self.region, self.h2 = len(self.headings) - 1, None
        elif tag == "table" and self.open:
            self.open.pop()
        elif tag == "a" and self.a is not None:
            if self.open:
                self.links.append((self.open[-1], _words(self.a)))
            self.a = None

    def handle_data(self, data: str) -> None:
        for buf in (self.h2, self.a):
            if buf is not None:
                buf.append(data)


def _regions(body: bytes) -> _Regions | None:
    parser = _Regions()
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
        parser.close()
    except (ValueError, RecursionError):
        return None
    return parser


def _header_rows(rule: HeaderTableRowsRule, body: bytes) -> tuple[str, ...] | None:
    parser = _HeaderTables()
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
        parser.close()
    except (ValueError, RecursionError):
        return None
    hits = [t for t in parser.done if rule.headers <= set(t.heads)]
    if len(hits) != 1 or any(hits[0].heads.count(h) != 1 for h in rule.headers):
        return None
    return tuple(f"r{i}" for i in range(1, hits[0].rows + 1))


def _heading_rows(rule: HeadingTablesRule, body: bytes) -> tuple[str, ...] | None:
    parser = _regions(body)
    if parser is None:
        return None
    found: list[str] = []
    usable = 0
    for heading, slug in rule.sections:
        hits = [tables for text, tables in parser.headings if text == heading]
        if len(hits) > 1:
            return None
        if not hits or not hits[0]:
            continue
        if len(hits[0]) > 1:
            return None
        usable += 1
        found += [f"{slug}-r{i}" for i in range(1, len(parser.tables[hits[0][0]]) + 1)]
    return tuple(found) if usable else None


def _link_cells(rule: LinkTableCellsRule, body: bytes) -> tuple[str, ...] | None:
    parser = _regions(body)
    if parser is None:
        return None
    pattern = re.compile(rule.link_text)
    hits = sorted({table for table, text in parser.links if pattern.fullmatch(text)})
    if len(hits) != 1:
        return None
    return tuple(
        f"r{i}c{j}"
        for i, cells in enumerate(parser.tables[hits[0]], 1)
        for j in range(1, cells + 1)
    )


@dataclass(slots=True)
class _OpenItem:
    path: str | None  # None inside a stop section
    children: int = 0


class _SectionItems(HTMLParser):
    """Paths of the ``li`` items under each non-stop ``h2`` section."""

    def __init__(self, stop_ids: frozenset[str], box_classes: frozenset[str]) -> None:
        super().__init__(convert_charrefs=True)
        self.stop_ids = stop_ids
        self.box_classes = box_classes
        self.boxes: list[tuple[str, bool]] = []  # open table/div tags: (tag, in or is a box)
        self.section: str | None = None
        self.top = 0  # top-level items counted in the current section
        self.open: list[_OpenItem] = []
        self.paths: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "h2":
            self.section = dict(attrs).get("id") or ""
            self.top = 0
            self.open = []
            self.boxes = []
        elif tag in ("table", "div"):
            classes = (dict(attrs).get("class") or "").split()
            in_box = (bool(self.boxes) and self.boxes[-1][1]) or any(
                c in self.box_classes for c in classes
            )
            self.boxes.append((tag, in_box))
        elif tag == "li" and self.section is not None:
            path = None if self.boxes and self.boxes[-1][1] else self._next_path()
            self.open.append(_OpenItem(path))
            if path is not None:
                self.paths.append(path)

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self.open:
            self.open.pop()
        elif tag in ("table", "div"):
            for i in range(len(self.boxes) - 1, -1, -1):
                if self.boxes[i][0] == tag:
                    del self.boxes[i:]
                    break

    def _next_path(self) -> str | None:
        if self.section in self.stop_ids:
            return None
        if not self.open:
            self.top += 1
            return f"{self.section}/li[{self.top}]"
        parent = self.open[-1]
        if parent.path is None:
            return None
        parent.children += 1
        return f"{parent.path}/li[{parent.children}]"


def _follow(body: bytes, path: tuple[str, ...]) -> object | None:
    """The JSON value at ``path`` through dicts, else ``None``."""
    try:
        node: object = json.loads(body)
    except (ValueError, RecursionError):
        return None
    for step in path:
        if not isinstance(node, dict) or step not in node:
            return None
        node = node[step]
    return node


def discover(rule: CountRule, body: bytes) -> tuple[str, ...] | None:
    """Locators of the page's units in document order; ``None`` if the body is unreadable."""
    if isinstance(rule, TableRowsRule):
        table = _TableRows(rule.table_id)
        try:
            table.feed(body.decode("utf-8", errors="replace"))
            table.close()
        except (ValueError, RecursionError):
            return None
        return tuple(f"r{i}" for i in range(1, table.rows + 1))
    if isinstance(rule, HeaderTableRowsRule):
        return _header_rows(rule, body)
    if isinstance(rule, HeadingTablesRule):
        return _heading_rows(rule, body)
    if isinstance(rule, LinkTableCellsRule):
        return _link_cells(rule, body)
    text = _follow(body, rule.json_text_path)
    if not isinstance(text, str):
        return None
    items = _SectionItems(rule.stop_ids, rule.box_classes)
    try:
        items.feed(text)
        items.close()
    except (ValueError, RecursionError):
        return None
    return tuple(items.paths)


def page_revid(rule: CountRule, body: bytes) -> int | None:
    """The page revision at ``revid_path``: a positive ``int``, else ``None``."""
    if not isinstance(rule, SectionItemsRule) or rule.revid_path is None:
        return None
    value = _follow(body, rule.revid_path)
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return None


@dataclass(frozen=True, slots=True)
class LedgerReport:
    """What ``check`` found. Page failures (a timeout, nothing published yet) are not
    problems: ``ok`` means only that the accounting and the discovery agree.
    """

    source: str
    units_seen: int
    outcomes: dict[Outcome, int]
    ignored_reasons: dict[str, int]
    relevance: dict[Relevance, int]
    problems: tuple[str, ...]
    reasons: tuple[Reason, ...]

    @property
    def ok(self) -> bool:
        return self.problems == ()


def _unit_problems(result: ParseResult) -> list[str]:
    """Invariants 1 (sources), 2, 3, 4, 5 and 6: they need no raw pages."""
    problems: list[str] = []
    units: dict[str, InputUnit] = {}
    for u in result.units:
        if u.source != result.source:
            problems.append(f"unit {u.unit_id} has source {u.source!r}, not {result.source!r}")
        if u.unit_id in units:
            problems.append(f"duplicate unit id {u.unit_id}")
        units.setdefault(u.unit_id, u)
        if u.outcome == "ignored" and u.reason not in IGNORED_REASONS:
            problems.append(f"ignored unit {u.unit_id} has reason {u.reason!r}, not allowlisted")
    indexes: dict[str, set[str]] = {}
    seen_claims: set[str] = set()
    for c in result.claims:
        if c.source != result.source:
            problems.append(f"claim {c.claim_id} has source {c.source!r}, not {result.source!r}")
        if c.claim_id in seen_claims:
            problems.append(f"duplicate claim id {c.claim_id}")
        seen_claims.add(c.claim_id)
        owner = units.get(c.unit_id)
        if owner is None or owner.outcome not in _USABLE:
            problems.append(f"claim {c.claim_id} is on no parsed or partial unit")
        else:
            indexes.setdefault(c.unit_id, set()).add(c.claim_id.removeprefix(f"{c.unit_id}#"))
    for u in units.values():
        numbers = indexes.get(u.unit_id, set())
        if u.outcome in _USABLE and not numbers:
            problems.append(f"{u.outcome} unit {u.unit_id} has no claim")
        if numbers != {str(i) for i in range(len(numbers))}:
            problems.append(f"claims of {u.unit_id} are not numbered #0 to #{len(numbers) - 1}")
        if u.duplicate_of is not None:
            target = units.get(u.duplicate_of)
            if target is None or target is u or target.outcome not in _USABLE:
                problems.append(
                    f"unit {u.unit_id} duplicates {u.duplicate_of}, "
                    "which is no other parsed or partial unit"
                )
    return problems


def record_problems(result: ParseResult) -> tuple[str, ...]:
    """The accounting problems found without raw pages (invariants 1 to 6)."""
    return tuple(_unit_problems(result))


def _page_problems(raw: RawPages, result: ParseResult, rules: Mapping[str, CountRule]) -> list[str]:
    """Invariant 7: rules, page keys, coverage and prefixes."""
    problems: list[str] = []
    if result.source not in rules:
        problems.append(f"source {result.source!r} has no counting rule")
    keys = [p.request.key for p in raw.pages] + [r.key for r in raw.unfinished]
    for key, n in Counter(keys).items():
        if n > 1:
            problems.append(f"page key {key!r} is requested {n} times")
    covered = Counter(c.key for c in result.coverage)
    for key in sorted(set(keys) | set(covered)):
        if covered[key] != 1 and key in keys:
            problems.append(f"page {key!r} has {covered[key]} coverage entries, not 1")
        elif key not in keys:
            problems.append(f"coverage for {key!r}, which is no page or unfinished request")
    pages = {p.request.key: p for p in raw.pages}
    unfinished = {r.key for r in raw.unfinished}
    for entry in result.coverage:
        if entry.key in unfinished and entry.outcome != "unfinished":
            problems.append(
                f"page {entry.key!r} is an unfinished request, coverage says {entry.outcome}"
            )
        if entry.outcome == "unfinished" and entry.key not in unfinished and entry.key in pages:
            problems.append(f"page {entry.key!r} is unfinished but its page was fetched")
        if entry.outcome not in _PAGE_OUTCOMES:
            problems += _non_unit_problems(entry, pages.get(entry.key))
            continue
        page = pages.get(entry.key)
        if page is None:
            problems.append(f"page {entry.key!r} is {entry.outcome} but no page was fetched")
        elif (failure := page_failure(page)) is not None:
            problems.append(
                f"page {entry.key!r} is {entry.outcome} but its download failed: {failure}"
            )
    prefixes = [c.unit_prefix for c in result.coverage if c.unit_prefix is not None]
    for u in result.units:
        n = sum(u.unit_id.startswith(prefix) for prefix in prefixes)
        if n != 1:
            problems.append(f"unit {u.unit_id} is under {n} ok or valid_empty page prefixes, not 1")
    return problems


def _non_unit_problems(entry: PageCoverage, page: RawPage | None) -> list[str]:
    """What a page that gave no units may claim (F-04): the download decides, not the adapter.

    A download outcome must be what ``page_failure`` says; a page that is not published
    yet needs a failed download; a changed layout needs a clean one; no units are seen.
    """
    problems: list[str] = []
    if entry.units_seen != 0:
        problems.append(
            f"page {entry.key!r} is {entry.outcome} but reports units_seen {entry.units_seen}"
        )
    if page is None:
        return problems
    failure = page_failure(page)
    how = "succeeded" if failure is None else f"failed: {failure}"
    if entry.outcome in _DOWNLOAD_OUTCOMES and entry.outcome != failure:
        problems.append(f"page {entry.key!r} is {entry.outcome} but its download {how}")
    elif entry.outcome in _NEEDS_A_FAILED_DOWNLOAD and failure is None:
        problems.append(f"page {entry.key!r} is {entry.outcome} but its download succeeded")
    elif entry.outcome == "layout_not_recognised" and failure is not None:
        problems.append(f"page {entry.key!r} is {entry.outcome} but its download {how}")
    return problems


def _expected_prefix(source: str, entry: PageCoverage, rule: CountRule) -> str | None:
    if isinstance(rule, SectionItemsRule) and rule.revid_path is not None:
        if entry.revid is None:
            return None
        return f"{source}:{entry.key}@rev{entry.revid}/"
    return f"{source}:{entry.key}/"


def _discovery_problems(
    page: RawPage, entry: PageCoverage, result: ParseResult, rule: CountRule
) -> list[str]:
    """Invariants 8 to 11 for one ok or valid_empty page."""
    body = page.result.body
    found = discover(rule, body)
    if found is None:
        return [f"page {entry.key!r}: the body cannot be read for the counting rule"]
    problems: list[str] = []
    if isinstance(rule, SectionItemsRule) and rule.revid_path is not None:
        revid = page_revid(rule, body)
        if revid is None or revid != entry.revid:
            problems.append(f"page {entry.key!r}: page revid {revid} differs from {entry.revid}")
    expected = _expected_prefix(result.source, entry, rule)
    if expected is not None and entry.unit_prefix != expected:
        problems.append(f"page {entry.key!r}: unit prefix {entry.unit_prefix!r}, not {expected!r}")
    prefix = entry.unit_prefix or ""
    have = {u.unit_id for u in result.units if u.unit_id.startswith(prefix)}
    want = {prefix + loc for loc in found}
    if have != want:
        problems.append(
            f"page {entry.key!r}: the page has {len(want)} units, the result has {len(have)}; "
            f"missing {sorted(want - have)[:3]}, unexpected {sorted(have - want)[:3]}"
        )
    if entry.units_seen != len(want):
        problems.append(f"page {entry.key!r}: units_seen {entry.units_seen}, page has {len(want)}")
    return problems


def _reason(code: ReasonCode, problems: list[str]) -> list[Reason]:
    if not problems:
        return []
    return [Reason(code, problems[0][:MAX_DETAIL])]


def check(
    raw: RawPages, result: ParseResult, *, rules: Mapping[str, CountRule] = COUNT_RULES
) -> LedgerReport:
    """Check the adapter's accounting against the raw pages (spec §9.1)."""
    ledger: list[str] = []
    if raw.source != result.source:
        ledger.append(f"raw pages are of {raw.source!r}, the result of {result.source!r}")
    ledger += _unit_problems(result)
    ledger += _page_problems(raw, result, rules)
    discovery: list[str] = []
    rule = rules.get(result.source)
    pages = {p.request.key: p for p in raw.pages}
    if rule is not None:
        for entry in result.coverage:
            page = pages.get(entry.key)
            if entry.outcome in _PAGE_OUTCOMES and page is not None and page_failure(page) is None:
                discovery += _discovery_problems(page, entry, result, rule)
    outcomes: dict[Outcome, int] = dict.fromkeys(get_args(Outcome), 0)
    relevance: dict[Relevance, int] = dict.fromkeys(get_args(Relevance), 0)
    ignored: Counter[str] = Counter()
    for u in result.units:
        outcomes[u.outcome] += 1
        if u.outcome in ("partial", "unparsed"):
            relevance[u.relevance] += 1
        if u.outcome == "ignored" and u.reason is not None:
            ignored[u.reason] += 1
    return LedgerReport(
        source=result.source,
        units_seen=len(result.units),
        outcomes=outcomes,
        ignored_reasons=dict(ignored),
        relevance=relevance,
        problems=tuple(ledger + discovery),
        reasons=tuple(
            _reason("ledger_mismatch", ledger) + _reason("discovery_mismatch", discovery)
        ),
    )
