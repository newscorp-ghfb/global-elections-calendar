"""The NDI adapter (spec section 7): the elections calendar on ndi.org.

The page has two card blocks, upcoming and past, each with its own pager; ``?page=N``
advances both. Only the first page is known up front: the later pages are implied by the
pagers of the pages received so far (``expected``, P46). Every card is an input unit; a
parsed or partial card gives one claim per office its title names, an unparsed or ignored
card gives none. Cards hold no links, so every claim links to the calendar page itself.
"""

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString

from elections_calendar.dates import parse_date_text, plausible, relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import (
    Claim,
    DateSpan,
    InputUnit,
    Level,
    Outcome,
    Reason,
    month_end,
)
from elections_calendar.offices import (
    extract_round,
    is_executive_title,
    split_offices,
    unnamed_parts,
)
from elections_calendar.places import Place, named_places
from elections_calendar.sources.base import (
    Getter,
    LabelScope,
    PageParse,
    PageRequest,
    ParseResult,
    RawPage,
    RawPages,
    Registries,
    fetch_chain,
    label_scope,
    missing_pages,
    page_failure,
    parse_pages,
    part_scopes,
)
from elections_calendar.sources.tables import cell_text, complete_html
from elections_calendar.text import collapse_ws
from elections_calendar.window import Window

URL = "https://www.ndi.org/elections-calendar"
CAP = 10
# NDI's cards per page. A source assumption, measured on p0-p4 (2026-10-19): a block with no
# pager and PAGE_SIZE or more cards is read as a pager that went missing. If NDI changes its
# page size, revise this against a new capture.
PAGE_SIZE = 10
BLOCKS = (("upcoming-elections", "upcoming"), ("past-elections", "past"))
WRAPPER = "election-wrapper"

SUBNATIONAL_TYPES = frozenset(
    {
        "commune council",
        "gubernatorial",
        "local",
        "local runoff",
        "local phase 1",
        "local phase 2",
        "local phase 3",
        "local phase 4",
        "municipal",
        "municipal runoff",
        "parochial",
        "provincial assembly",
        "regional",
        "state assembly",
    }
)
NATIONAL_TYPES = frozenset(
    {
        "by-election",
        "constitutional assembly",
        "executive",
        "general",
        "general runoff",
        "legislative",
        "legislative runoff",
        "national assembly",
        "national council",
        "parliamentary",
        "parliamentary by-election",
        "parliamentary phase 1",
        "parliamentary phase 2",
        "parliamentary phase 3",
        "parliamentary phase 4",
        "parliamentary re-run",
        "parliamentary runoff",
        "presidential",
        "presidential and parliamentary",
        "presidential and parliamentary by-election",
        "presidential and parliamentary phase 1",
        "presidential and parliamentary phase 2",
        "presidential and parliamentary phase 3",
        "presidential and parliamentary phase 4",
        "presidential and parliamentary re-run",
        "presidential and parliamentary runoff",
        "presidential by-election",
        "presidential phase 1",
        "presidential phase 2",
        "presidential phase 3",
        "presidential re-run",
        "presidential referendum",
        "presidential runoff",
        "re-run presidential runoff",
        "referendum",
        "referendum phase 1",
        "referendum phase 2",
        "senatorial",
        "senatorial by-election",
    }
)

_ACTIVE = re.compile(r"\?page=([0-9]{1,3})")
_TBD = re.compile(r"\bTBD\b", re.IGNORECASE)
_YEAR = re.compile(r"\b[0-9]{4}\b")
_EMPTY_PARENS = re.compile(r"\(\s*\)")
_LETTER = r"[^\W\d_]"


def request(n: int) -> PageRequest:
    return PageRequest(f"p{n}", f"{URL}?page={n}")


@dataclass(slots=True)
class Card:
    title: str
    date_text: str
    terms: list[str]
    location: str
    day: date | None  # the raw visible day, when the date text is one day


@dataclass(slots=True)
class Block:
    slug: str
    has_next: bool
    cards: list[Card] = field(default_factory=list)


def _raw_day(text: str) -> date | None:
    parsed = parse_date_text(text)
    if not parsed.ok or len(parsed.spans) != 1:
        return None
    span = parsed.spans[0]
    if span.precision != "day" or span.start is None or span.start != span.end:
        return None
    return span.start


def _read_card(tag: Tag) -> Card:
    heading = tag.select_one("h3.heading")
    date_type = tag.select_one(".date-type")
    date_el = tag.select_one(".date-type .date")
    button = tag.select_one("button.add-to-cal")
    terms: list[str] = []
    if date_type is not None:
        own = "".join(str(child) for child in date_type.children if type(child) is NavigableString)
        terms = [t for t in (collapse_ws(line) for line in own.splitlines()) if t]
    location = button.get("data-location") if button is not None else None
    date_text = cell_text(date_el) if date_el is not None else ""
    return Card(
        cell_text(heading) if heading is not None else "",
        date_text,
        terms,
        collapse_ws(location) if isinstance(location, str) else "",
        _raw_day(date_text),
    )


def _read_page(text: str, n: int) -> list[Block] | str:
    """The blocks of page ``p<n>``, or the first failing check's detail."""
    if not complete_html(text):
        return "page does not end with </html>"
    soup = BeautifulSoup(text, "lxml")
    blocks: list[Block] = []
    for block_id, slug in BLOCKS:
        found = soup.find_all(id=block_id)
        if len(found) != 1:
            return f"block #{block_id} appears {len(found)} times"
        panel = found[0]
        wrappers = panel.find_all("div", class_=WRAPPER)
        if len(wrappers) > 1:
            return f"{slug} block has {len(wrappers)} card lists"
        pagers = panel.find_all("nav", class_="pager")
        if len(pagers) > 1:
            return f"{slug} block has {len(pagers)} pagers"
        tags = [c for c in wrappers[0].children if isinstance(c, Tag)] if wrappers else []
        active, has_next = 0, False
        if pagers:
            current = pagers[0].select("li.is-active > a")
            href = current[0].get("href") if len(current) == 1 else None
            match = _ACTIVE.fullmatch(href) if isinstance(href, str) else None
            if match is None:
                return f"{slug} block has no current page"
            active = int(match.group(1))
            has_next = any("next" in (a.get("rel") or []) for a in pagers[0].find_all("a"))
            if not has_next and pagers[0].find_all("li")[-1] is not current[0].parent:
                return f"{slug} block has later pages but no next link"
        elif len(tags) >= PAGE_SIZE:
            return f"{slug} block has {len(tags)} cards and no pager"
        if not ((active == n and tags) or (active < n and not tags)):
            return f"{slug} block is page {active} with {len(tags)} cards"
        block = Block(slug, has_next, [_read_card(t) for t in tags])
        days = [c.day for c in block.cards if c.day is not None]
        if days != sorted(days, reverse=(slug == "past")):
            return f"{slug} block is not in date order"
        blocks.append(block)
    return blocks


def _titles_of(block: Block) -> tuple[str, frozenset[str]] | None:
    """The key of a block's card titles for the repeat check; ``None`` for an empty block (C06)."""
    if not block.cards:
        return None
    return block.slug, frozenset(c.title for c in block.cards)


def _wants_more(blocks: Sequence[Block], window: Window) -> bool:
    upcoming, past = blocks
    if upcoming.has_next:
        return True
    if not past.has_next or not past.cards:
        return False
    days = [c.day for c in past.cards if c.day is not None]
    return not days or min(days) >= window.start


def _readable(page: RawPage, n: int) -> list[Block] | None:
    """The blocks of a clean, readable page, else ``None``; never raises on content."""
    if page_failure(page) is not None:
        return None
    try:
        blocks = _read_page(page.result.text(), n)
    except RecursionError:
        return None
    return None if isinstance(blocks, str) else blocks


def expected(window: Window, pages: Sequence[RawPage]) -> tuple[PageRequest, ...]:
    """Every request that the pages received so far imply, first page first (P46, P50)."""
    by_key = {p.request.key: p for p in pages}
    requests = [request(0)]
    for n in range(CAP - 1):
        page = by_key.get(f"p{n}")
        blocks = _readable(page, n) if page is not None else None
        if blocks is None or not _wants_more(blocks, window):
            break
        requests.append(request(n + 1))
    return tuple(requests)


def _type_level(terms: Sequence[str]) -> tuple[Level, list[str]]:
    """The default level the type terms give, and the terms in neither vocabulary (P49)."""
    folded = [t.casefold() for t in terms]
    known = SUBNATIONAL_TYPES | NATIONAL_TYPES
    unknown = [t for t, f in zip(terms, folded, strict=True) if f not in known]
    kinds = {f in SUBNATIONAL_TYPES for f in folded if f in known}
    if kinds == {True}:
        return "subnational", unknown
    if kinds == {True, False}:
        return "unknown", unknown
    return "national", unknown


def _office_words(title: str, named: Sequence[tuple[str, Place]]) -> str:
    """The title without its named-place runs, four-digit years and empty brackets (P49)."""
    text = title
    for run, _ in named:
        sep = r"[^\w'’-]+"
        pattern = rf"(?<!{_LETTER})" + sep.join(re.escape(w) for w in run.split(" "))
        text = re.sub(pattern + rf"(?!{_LETTER})", " ", text)
    return collapse_ws(_EMPTY_PARENS.sub(" ", _YEAR.sub(" ", text)))


@dataclass(slots=True)
class _State:
    """What flows from page to page, in fetch order."""

    titles: dict[tuple[str, frozenset[str]], str] = field(default_factory=dict)
    last_day: dict[str, tuple[date, str]] = field(default_factory=dict)
    claimed: dict[tuple[str, str, tuple[str, ...], str], str] = field(default_factory=dict)


class Ndi:
    source = "ndi"

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return (request(0),)

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        return fetch_chain(lambda pages: expected(window, pages), fetcher, deadline)

    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult:
        state = _State()
        res = parse_pages(
            self.source, raw, lambda page: self._parse_page(page, window, registries, state)
        )
        notes = list(res.notes) + missing_pages(expected(window, raw.pages), raw)
        last = {p.request.key: p for p in raw.pages}.get(f"p{CAP - 1}")
        blocks = _readable(last, CAP - 1) if last is not None else None
        if blocks is not None and _wants_more(blocks, window):
            notes.append(Reason("pagination_incomplete", f"stopped at the {CAP}-page cap"))
        return ParseResult(res.source, res.units, res.claims, res.coverage, tuple(notes))

    def _parse_page(
        self, page: RawPage, window: Window, registries: Registries, state: _State
    ) -> PageParse:
        key = page.request.key
        blocks = _read_page(page.result.text(), int(key[1:]))
        if isinstance(blocks, str):
            return PageParse("layout_not_recognised", detail=blocks)
        for block in blocks:
            titles = _titles_of(block)
            if titles is not None and titles in state.titles:
                detail = f"{block.slug} block repeats {state.titles[titles]}"
                return PageParse("layout_not_recognised", detail=detail)
        for block in blocks:
            days = [c.day for c in block.cards if c.day is not None]
            if days and block.slug in state.last_day:
                before, at = state.last_day[block.slug]
                broken = days[0] < before if block.slug == "upcoming" else days[0] > before
                if broken:
                    detail = f"{block.slug} block is not in date order after {at}"
                    return PageParse("layout_not_recognised", detail=detail)
        for block in blocks:
            titles = _titles_of(block)
            if titles is not None:
                state.titles[titles] = key
            days = [c.day for c in block.cards if c.day is not None]
            if days:
                state.last_day[block.slug] = (days[-1], key)
        out = PageParse("ok")
        for block in blocks:
            for i, card in enumerate(block.cards, 1):
                self._card(out, f"ndi:{key}/{block.slug}-c{i}", card, window, registries, state)
        return out

    def _card(
        self,
        out: PageParse,
        uid: str,
        card: Card,
        window: Window,
        registries: Registries,
        state: _State,
    ) -> None:
        parts_text = (card.title, card.date_text, ", ".join(card.terms), card.location)
        text = " | ".join(t for t in parts_text if t)
        dup_key = (card.title, card.date_text, tuple(card.terms), card.location)
        rel = relevance(card.date_text, window.start)

        def unit(
            outcome: Outcome, reason: str | None, leftover: str = "", dup: str | None = None
        ) -> None:
            out.units.append(
                InputUnit(uid, self.source, text, outcome, reason, rel, leftover, duplicate_of=dup)
            )

        if dup_key in state.claimed:
            unit("ignored", "duplicate", dup=state.claimed[dup_key])
            return
        if not card.title:
            unit("unparsed", "title_missing")
            return
        if not card.date_text:
            unit("unparsed", "date_missing")
            return
        found = registries.places.resolve(card.location) if card.location else None
        named = named_places(card.title, registries.places)
        others: list[str] = []
        if found is not None and found.registered:
            place, place_raw = found, card.location
            children = [(w, p) for w, p in named if p.parent == found.place_id]
            others = [
                w for w, p in named if p.place_id != found.place_id and p.parent != found.place_id
            ]
            if len(children) == 1:
                place_raw, place = children[0]
        elif len(named) == 1:
            place_raw, place = named[0]
        elif len(named) > 1:
            unit("unparsed", "place_ambiguous", ", ".join(w for w, _ in named))
            return
        elif found is not None:
            place, place_raw = found, card.location
        else:
            unit("unparsed", "place_missing")
            return
        parsed = parse_date_text(card.date_text)
        if parsed.ok and not parsed.spans:
            unit("unparsed", "date_missing")
            return
        if card.day is None or parsed.status_claim is not None:
            unit("unparsed", "date_unparsed", parsed.leftover or card.date_text)
            return
        day = card.day
        if not plausible(DateSpan.day(day), window.today):
            unit("unparsed", "implausible_date")
            return
        if is_executive_title(card.title):
            unit("unparsed", "office_not_modelled", card.title)
            return
        tbd = bool(_TBD.search(card.title))
        if (day.month, day.day) == (12, 31):
            span = DateSpan.of_year(day.year)
        elif tbd or day == month_end(day.year, day.month):
            span = DateSpan.month(day.year, day.month)
        else:
            span = DateSpan.day(day)

        default, unknown_terms = _type_level(card.terms)
        words = _office_words(card.title, named)
        institutions = registries.institutions
        split = split_offices(words, place.place_id, institutions)
        unnamed = unnamed_parts(words, place.place_id, institutions)
        parts = split if len(split) > 1 else [card.title]
        fallback = False
        if (
            len(split) < 2
            and card.terms
            and not label_scope(card.title, place, registries, default).office.recognised
        ):
            joined = " and ".join(card.terms)
            if label_scope(
                card.title, place, registries, default, office_text=joined
            ).office.recognised:
                parts = split_offices(joined, place.place_id, institutions) or [joined]
                fallback = True
        scopes: list[LabelScope]
        if len(parts) > 1 and not fallback:
            scopes = part_scopes(parts, place, registries, default)
        else:
            scopes = [
                label_scope(card.title, place, registries, default, office_text=part)
                for part in parts
            ]
        title_round = extract_round(card.title)[0] if fallback else None
        round_clash = title_round is not None and any(
            sc.office.round not in (None, title_round) for sc in scopes
        )

        reason: str | None = None
        leftover = ""
        if others:
            reason, leftover = "place_conflict", ", ".join(others)
        elif not place.registered:
            reason = "place_unregistered"
        elif unknown_terms:
            reason, leftover = "type_unrecognised", ", ".join(unknown_terms)
        elif round_clash:
            reason, leftover = "round_conflict", ", ".join(card.terms)
        elif unnamed:
            reason, leftover = "office_unrecognised", ", ".join(unnamed)
        elif not all(sc.office.recognised for sc in scopes):
            reason = "office_unrecognised"
        elif any(sc.unresolved or sc.level == "unknown" for sc in scopes):
            reason = "level_unresolved"
        unit("parsed" if reason is None else "partial", reason, leftover)
        state.claimed[dup_key] = uid

        for n, (part, sc) in enumerate(zip(parts, scopes, strict=True)):
            office = sc.office
            if office.round is None:
                round_ = title_round
            else:
                round_ = office.round if title_round in (None, office.round) else None
            out.claims.append(
                Claim(
                    unit_id=uid,
                    claim_id=f"{uid}#{n}",
                    source=self.source,
                    link=URL,
                    source_event_id=None,
                    place_raw=place_raw,
                    place_id=place.place_id,
                    jurisdiction=sc.jurisdiction,
                    jurisdiction_kind=sc.jurisdiction_kind,
                    level=sc.level,
                    institution=office.institution,
                    office_class=office.office_class,
                    office_label=card.title if len(parts) == 1 else part,
                    aggregate=office.aggregate,
                    kind=office.kind,
                    round=round_,
                    span=span,
                    date_meaning="voting_period" if span.precision == "day" else "unknown",
                    date_status="tentative" if tbd else "unknown",
                    date_text=card.date_text,
                    status_claim=None,
                    previous_date_text=None,
                    evidence_kind="calendar",
                    indirect=False,
                )
            )
