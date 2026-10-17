"""The Wikipedia adapter (spec §8): the "YYYY national/local electoral calendar" pages.

Each page is the MediaWiki-API JSON of one article. Its ``h2`` sections hold nested
``li`` items; every ``li`` is an input unit and gives one claim per (office, date span).
An item's text is "<date>: <place>, <jurisdiction>, <office>"; an item without a date
takes the nearest ancestor's, else its section's month (or the page year).

A nested item inherits the place, the place text and the jurisdiction tokens of its
nearest ancestor that has a place; it never resolves its own first token as a country.
With no inherited place, a first token that starts with a year ("2027 Lithuanian
municipal elections") is an article title and the unit is unparsed. A registered
subdivision named right after the place (Scotland under the United Kingdom) becomes the
place. The first token that is an office starts the office text; the tokens before it are
jurisdiction tokens. An item with children and no office token is a container; a leaf
without one takes its last token as the office. Two adapter overrides apply after
classification: the Canadian federal by-election and the US congressional district.
"""

import dataclasses
import json
import re
import urllib.parse
from collections.abc import Iterator
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString, PreformattedString

from elections_calendar.dates import parse_date_text, plausible, relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import (
    Claim,
    DateSpan,
    DateStatus,
    InputUnit,
    JurisdictionKind,
    Level,
    Outcome,
    StatusClaim,
)
from elections_calendar.offices import (
    Office,
    claim_level,
    classify,
    institution_id,
    is_by_election,
    is_executive_title,
    office_class_of,
    split_offices,
)
from elections_calendar.places import Place
from elections_calendar.sources.base import (
    Getter,
    PageCoverage,
    PageOutcome,
    PageRequest,
    ParseResult,
    RawPage,
    RawPages,
    Registries,
    fetch_pages,
    page_failure,
)
from elections_calendar.text import collapse_ws
from elections_calendar.window import Window

KINDS = ("national", "local")
STOP_IDS = frozenset(
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
)
MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip
_MONTH_BY_NAME = {name.casefold(): i for i, name in enumerate(MONTHS, 1)}
_MONTH_WORD = re.compile(r"\b(?:" + "|".join(MONTHS) + r")\b", re.IGNORECASE)
_EXTIW_BRACKETS = re.compile(r"\s*\[\s*\x00\s*\]")
_SKIPPED_IN_OWN_TEXT = ("ul", "ol", "sup", "style", "link")
_MAINTENANCE_TABLES = ("ambox", "metadata", "navbox")
_DATE_SEPARATORS = (":", ",")
_INDIRECT = "Indirect_elections"
_ARTICLE_TITLE = re.compile(r"^\d{4}\s")
PLACE_SUFFIX = re.compile(
    r"^(?:[A-Z][\w'’.-]*\s+)+(?:County|District|Region|Prefecture|Province|Parish|Borough)$"
)
ELECTION_WORD = re.compile(r"\b(?:by-?|special )?elections?\b", re.IGNORECASE)
_CONGRESSIONAL = re.compile(r"\bcongressional district\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _Date:
    """The date an item states or inherits. ``failure`` is the reason it has none."""

    text: str
    spans: tuple[DateSpan, ...]
    status: DateStatus
    status_claim: StatusClaim | None
    previous_text: str | None
    failure: str | None = None


@dataclass(frozen=True, slots=True)
class _Where:
    """The place, country text and jurisdiction tokens an item has or inherits."""

    place: Place | None = None
    place_text: str | None = None
    jurisdiction: tuple[str, ...] = ()


@dataclass(slots=True)
class _PageParse:
    outcome: PageOutcome
    revid: int | None = None
    units: list[InputUnit] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Walk:
    """What stays the same while one section's items are parsed."""

    out: _PageParse
    section: str
    members: set[int]
    request: PageRequest
    link_base: str
    window: Window
    registries: Registries


@dataclass(frozen=True, slots=True)
class _Section:
    key: str
    elements: tuple[Tag, ...]


def _is_heading(el: Tag) -> Tag | None:
    """The ``h2`` that makes ``el`` a section heading, if it is one."""
    if el.name == "h2":
        return el
    if el.name == "div" and "mw-heading" in (el.get("class") or []):
        found = el.find("h2")
        return found if isinstance(found, Tag) else None
    return None


def _sections(root: Tag) -> list[_Section]:
    """The page's sections in order; every ``h2`` has an id (checked by the caller)."""
    keys: list[str] = []
    bodies: list[list[Tag]] = []
    for el in root.children:
        if not isinstance(el, Tag):
            continue
        heading = _is_heading(el)
        if heading is not None:
            keys.append(str(heading.get("id")))
            bodies.append([])
        elif bodies:
            bodies[-1].append(el)
    return [_Section(k, tuple(b)) for k, b in zip(keys, bodies, strict=True)]


def _has_data_table(elements: tuple[Tag, ...]) -> bool:
    """Whether a section holds a ``dl`` or a table that is not a maintenance box."""
    for el in elements:
        for tag in (el, *el.find_all(["dl", "table"])):
            if tag.name in ("dl", "table") and not _is_maintenance(tag):
                return True
    return False


def _is_maintenance(table: Tag) -> bool:
    for tag in (table, *table.parents):
        classes = tag.get("class") if isinstance(tag, Tag) else None
        if classes and any(c in _MAINTENANCE_TABLES for c in classes):
            return True
    return False


def _own_text(li: Tag) -> tuple[str, str | None]:
    """The text an ``li`` holds itself, and the text of its first (non-interlanguage) link."""
    pieces: list[str] = []
    first_link: list[str] = []

    def walk(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, PreformattedString):
                continue  # comments, CDATA, doctype
            if isinstance(child, NavigableString):
                pieces.append(str(child))
            elif isinstance(child, Tag):
                if child.name in _SKIPPED_IN_OWN_TEXT:
                    continue
                if child.name == "a":
                    if "extiw" in (child.get("class") or []):
                        pieces.append("\x00")
                        continue
                    if not first_link:
                        first_link.append(collapse_ws(child.get_text()))
                walk(child)

    walk(li)
    text = _EXTIW_BRACKETS.sub("", "".join(pieces)).replace("\x00", "")
    text = collapse_ws(text).strip(" ").removesuffix(",").strip(" ")
    return text, first_link[0] if first_link else None


def _split_top(text: str) -> list[str]:
    """Split on ", " and ": " outside parentheses; tokens are stripped of " ,:"."""
    parts: list[str] = []
    depth = start = i = 0
    while i < len(text):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and text.startswith((", ", ": "), i):
            parts.append(text[start:i])
            i += 2
            start = i
            continue
        i += 1
    parts.append(text[start:])
    tokens = (p.strip(" ,:") for p in parts)
    return [t for t in tokens if t]


def _children(li: Tag, members: set[int]) -> list[Tag]:
    """The section's ``li`` items whose nearest ancestor ``li`` is ``li``."""
    return [
        k
        for k in li.find_all("li")
        if isinstance(k, Tag) and k.find_parent("li") is li and id(k) in members
    ]


def _date_prefix(text: str, year: int) -> tuple[str, str, _Date | None]:
    """(head, item text, date) for an item that starts with a date; (head, text, None) if not.

    The head of the first separator present is returned for the month-word check.
    """
    first_head = ""
    for sep in _DATE_SEPARATORS:
        if sep not in text:
            continue
        head = text.split(sep, 1)[0].strip()
        first_head = first_head or head
        if not (any(ch.isdigit() for ch in head) or head.casefold() in _MONTH_BY_NAME):
            continue
        parse = parse_date_text(head, default_year=year)
        if parse.ok and parse.spans:
            rest = text.split(sep, 1)[1].strip()
            date = _Date(
                head,
                tuple(dict.fromkeys(parse.spans)),
                parse.date_status,
                parse.status_claim,
                parse.previous_text,
            )
            return head, rest, date
    return first_head, text, None


def _section_date(section: str, year: int) -> _Date:
    month = _MONTH_BY_NAME.get(section.casefold())
    if month is not None:
        return _Date(section, (DateSpan.month(year, month),), "unknown", None, None)
    return _Date(section.replace("_", " "), (DateSpan.of_year(year),), "unknown", None, None)


def _country(
    rest: str, first_link: str | None, registries: Registries
) -> tuple[str | None, Place | None, list[str]]:
    """The item's own country text, its place and the tokens left after it.

    A first link that starts the text is the country ("Punjab, India" keeps its
    comma); otherwise the first token is. Only items with no inherited place use this.
    """
    if first_link and rest.startswith(first_link):
        after = _split_top(rest[len(first_link) :])
        return first_link, registries.places.resolve(first_link), after
    tokens = _split_top(rest)
    if not tokens:
        return None, None, []
    return tokens[0], registries.places.resolve(tokens[0]), tokens[1:]


def _is_office(token: str, place: Place, registries: Registries) -> bool:
    """Whether a token names an office (executive titles count) and not a place."""
    if registries.subdivisions.find(place.country_code, token) or PLACE_SUFFIX.match(token):
        return False
    return (
        office_class_of(token, place.place_id, registries.institutions) is not None
        or ELECTION_WORD.search(token) is not None
    )


def _jurisdiction_kind(
    tokens: tuple[str, ...], place: Place, registries: Registries
) -> JurisdictionKind:
    if not tokens:
        return "nationwide"
    if registries.subdivisions.find(place.country_code, tokens[0]):
        return "subdivision"
    return "named"


def _override(
    office: Office, part: str, place: Place, kind: JurisdictionKind, registries: Registries
) -> Office:
    """Apply the adapter overrides (P17) to a classified office: both are recognised, national."""
    if place.place_id == "iso:CA" and kind == "named" and part.casefold() == "federal by-election":
        return dataclasses.replace(
            office, office_class="lower_house", institution="iso:CA/house-of-commons",
            kind="by_election", aggregate=False, level_hint="national", recognised=True,
        )
    if _CONGRESSIONAL.search(part):
        lower = [
            c
            for c in registries.institutions.chambers(place.place_id)
            if c.office_class == "lower_house" and c.active
        ]
        if len(lower) == 1:
            return dataclasses.replace(
                office, office_class="lower_house",
                institution=institution_id(place.place_id, lower[0]),
                kind="by_election" if is_by_election(part) else "candidate_election",
                aggregate=False, level_hint="national", recognised=True,
            )
    return office


class Wikipedia:
    source = "wikipedia"
    KINDS = KINDS
    STOP_IDS = STOP_IDS

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return tuple(
            PageRequest(
                f"{kind}-{year}",
                f"https://en.wikipedia.org/w/api.php?action=parse&page={year}_{kind}_electoral_calendar"
                "&prop=text%7Crevid&format=json&formatversion=2&maxlag=5",
                year,
                mediawiki=True,
            )
            for kind in KINDS
            for year in window.years
        )

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        return fetch_pages(self.requests(window), fetcher, deadline)

    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult:
        units: list[InputUnit] = []
        claims: list[Claim] = []
        coverage: list[PageCoverage] = []
        for page in raw.pages:
            parsed = self._parse_page(page, window, registries)
            request = page.request
            if parsed.outcome in ("ok", "valid_empty"):
                units += parsed.units
                claims += parsed.claims
                prefix = f"wikipedia:{request.key}@rev{parsed.revid}/"
                coverage.append(
                    PageCoverage(
                        request.key, request.year, parsed.outcome, prefix,
                        len(parsed.units), parsed.revid,
                    )
                )
            else:
                coverage.append(PageCoverage(request.key, request.year, parsed.outcome, None, 0))
        for request in raw.unfinished:
            coverage.append(PageCoverage(request.key, request.year, "unfinished", None, 0))
        return ParseResult(self.source, tuple(units), tuple(claims), tuple(coverage))

    def _parse_page(self, page: RawPage, window: Window, registries: Registries) -> _PageParse:
        failure = page_failure(page)
        request = page.request
        if failure is not None:
            if (
                failure == "api_error"
                and page.result.api_code == "missingtitle"
                and request.year is not None
                and request.year > window.today.year
            ):
                return _PageParse("not_published_yet")
            if failure == "api_error" and page.result.api_code == "missingtitle":
                return _PageParse("required_year_missing")
            return _PageParse(failure)
        try:
            return self._parse_body(page, window, registries)
        except RecursionError:
            return _PageParse("layout_not_recognised")

    def _parse_body(self, page: RawPage, window: Window, registries: Registries) -> _PageParse:
        request = page.request
        kind = request.key.partition("-")[0]
        try:
            data = json.loads(page.result.text())
        except (ValueError, RecursionError):
            return _PageParse("layout_not_recognised")
        body = data.get("parse") if isinstance(data, dict) else None
        if not isinstance(body, dict) or request.year is None or kind not in KINDS:
            return _PageParse("layout_not_recognised")
        text, revid, title = body.get("text"), body.get("revid"), body.get("title")
        if (
            not isinstance(text, str)
            or not isinstance(revid, int)
            or isinstance(revid, bool)
            or revid < 1
            or title != f"{request.year} {kind} electoral calendar"
        ):
            return _PageParse("layout_not_recognised")
        root = BeautifulSoup(text, "lxml").select_one("div.mw-parser-output")
        if root is None:
            return _PageParse("layout_not_recognised")
        headings = {
            id(found)
            for el in root.children
            if isinstance(el, Tag) and (found := _is_heading(el)) is not None
        }
        # every h2 must be a section heading with an id; the ledger counts each h2 as one
        if any(id(h) not in headings or not h.get("id") for h in root.find_all("h2")):
            return _PageParse("layout_not_recognised")
        sections = _sections(root)
        if not any(s.key.casefold() in _MONTH_BY_NAME for s in sections):
            return _PageParse("layout_not_recognised")
        counted = [s for s in sections if s.key not in STOP_IDS]
        if any(_has_data_table(s.elements) for s in counted):
            return _PageParse("layout_not_recognised")
        page_key = f"{request.key}@rev{revid}"
        link_base = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
        out = _PageParse("valid_empty", revid)
        for section in counted:
            items = [
                li
                for el in section.elements
                for li in ([el] if el.name == "li" else []) + list(el.find_all("li"))
                if isinstance(li, Tag)
            ]
            members = {id(li) for li in items}
            top = [
                li
                for li in items
                if (up := li.find_parent("li")) is None or id(up) not in members
            ]
            walk = _Walk(out, section.key, members, request, link_base, window, registries)
            for i, li in enumerate(top, 1):
                self._parse_item(
                    walk, li, f"wikipedia:{page_key}/{section.key}/li[{i}]", None, [], _Where()
                )
        if out.units:
            out.outcome = "ok"
        return out

    def _parse_item(
        self,
        walk: _Walk,
        li: Tag,
        unit_id: str,
        inherited: _Date | None,
        chain: list[str],
        where: _Where,
    ) -> None:
        year = walk.request.year
        assert year is not None
        text, first_link = _own_text(li)
        kids = _children(li, walk.members)
        unit_text = " > ".join([*chain, text])
        head, rest, own_date = _date_prefix(text, year)
        if own_date is not None:
            date = own_date
        elif head and _MONTH_WORD.search(head):
            date = _Date(head, (), "unknown", None, None, "date_unparsed")
        elif inherited is not None:
            date = inherited
        else:
            date = _section_date(walk.section, year)
        outcome: Outcome
        outcome, reason, leftover = "parsed", None, ""
        new_claims: list[Claim] = []
        here = where
        if date.failure is not None:
            outcome, reason = "unparsed", date.failure
        elif not all(plausible(span, walk.window.today) for span in date.spans):
            outcome, reason = "unparsed", "implausible_date"
        else:
            outcome, reason, leftover, here, new_claims = self._item_body(
                walk, unit_id, rest, first_link, bool(kids), date, where
            )
        relevance_of = relevance(f"{date.text} {unit_text}", walk.window.start, default_year=year)
        walk.out.units.append(
            InputUnit(unit_id, self.source, unit_text, outcome, reason, relevance_of, leftover)
        )
        walk.out.claims += new_claims
        for j, kid in enumerate(kids, 1):
            self._parse_item(walk, kid, f"{unit_id}/li[{j}]", date, [*chain, text], here)

    def _item_body(
        self,
        walk: _Walk,
        unit_id: str,
        rest: str,
        first_link: str | None,
        has_kids: bool,
        date: _Date,
        where: _Where,
    ) -> tuple[Outcome, str | None, str, _Where, list[Claim]]:
        """Place, jurisdiction and offices of a dated item.

        Returns (outcome, reason, leftover, where, claims).

        ``where`` is what the item's children inherit.
        """
        registries = walk.registries
        place, place_text, jurisdiction = where.place, where.place_text, where.jurisdiction
        if place is None:
            tokens = _split_top(rest)
            if tokens and _ARTICLE_TITLE.match(tokens[0]):
                return "unparsed", "article_title", "", where, []
            place_text, place, tokens = _country(rest, first_link, registries)
        else:
            tokens = _split_top(rest)
        if place is None or place_text is None:
            if has_kids:
                return "ignored", "container_item", "", where, []
            return "unparsed", "place_missing", "", where, []
        if place.registered and tokens and not jurisdiction:
            sub = registries.places.resolve_subdivision(place.place_id, tokens[0])
            if sub is not None:
                place, tokens = sub, tokens[1:]
        k = next((i for i, t in enumerate(tokens) if _is_office(t, place, registries)), None)
        if k is not None:
            jurisdiction += tuple(tokens[:k])
            office_text = ", ".join(tokens[k:])
        elif has_kids:
            jurisdiction += tuple(tokens)
            here = _Where(place, place_text, jurisdiction)
            if all(registries.subdivisions.find(place.country_code, t) for t in tokens):
                return "ignored", "container_item", "", here, []
            return "unparsed", "container_text", ", ".join(tokens), here, []
        elif tokens and (jurisdiction or len(tokens) == 1):
            office_text = ", ".join(tokens)
        elif tokens:
            jurisdiction += tuple(tokens[:-1])
            office_text = tokens[-1]
        else:
            here = _Where(place, place_text, jurisdiction)
            return "unparsed", "office_missing", "", here, []
        here = _Where(place, place_text, jurisdiction)
        outcome, reason, leftover, claims = self._offices(walk, unit_id, office_text, here, date)
        return outcome, reason, leftover, here, claims

    def _offices(
        self,
        walk: _Walk,
        unit_id: str,
        office_text: str,
        where: _Where,
        date: _Date,
    ) -> tuple[Outcome, str | None, str, list[Claim]]:
        """Classify the offices of an item: (unit outcome, reason, leftover, claims)."""
        registries = walk.registries
        institutions = registries.institutions
        place = where.place
        assert place is not None
        names = tuple(dict.fromkeys(where.jurisdiction))
        jurisdiction = ", ".join(names) or None
        jkind = _jurisdiction_kind(names, place, registries)
        parts = split_offices(office_text, place.place_id, institutions)
        if not parts:
            return "unparsed", "office_missing", "", []
        titles = [p for p in parts if is_executive_title(p)]
        leftover = ", ".join(titles)
        offices: list[Office] = [
            _override(classify(p, place.place_id, jkind, institutions), p, place, jkind, registries)
            for p in parts
            if not is_executive_title(p)
        ]
        if not offices:
            return "unparsed", "office_not_modelled", leftover, []
        default: Level = "national" if walk.request.key.startswith("national-") else "subnational"
        claims: list[Claim] = []
        for office in offices:
            for span in date.spans:
                claims.append(
                    Claim(
                        unit_id=unit_id,
                        claim_id=f"{unit_id}#{len(claims)}",
                        source=self.source,
                        link=f"{walk.link_base}#{walk.section}",
                        source_event_id=None,
                        place_raw=where.place_text or "",
                        place_id=place.place_id,
                        jurisdiction=jurisdiction,
                        jurisdiction_kind=jkind,
                        level=claim_level(default, office),
                        institution=office.institution,
                        office_class=office.office_class,
                        office_label=office.label,
                        aggregate=office.aggregate,
                        kind=office.kind,
                        round=office.round,
                        span=span,
                        date_meaning="voting_period",
                        date_status=date.status,
                        date_text=date.text,
                        status_claim=date.status_claim,
                        previous_date_text=date.previous_text,
                        evidence_kind="calendar",
                        indirect=walk.section == _INDIRECT,
                    )
                )
        reason: str | None = None
        if not place.registered:
            reason = "place_unregistered"
        elif not all(o.recognised for o in offices):
            reason = "office_unrecognised"
        elif titles:
            reason = "office_not_modelled"
        return ("parsed" if reason is None else "partial"), reason, leftover, claims
