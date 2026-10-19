"""The EISA adapter (spec section 7): the African election calendar on eisa.org.

The calendar page names a table id per year; each year's rows come from an admin-ajax JSON
page. Only the calendar page is known up front: the year pages are implied by the calendar
page received (``expected``, P46). The calendar page gives no units. Every element of a
year's list is an input unit; a parsed or partial row gives one claim per office its election
names, an unparsed or ignored row gives none. Rows hold no links, so every claim links to the
calendar page itself.
"""

import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from bs4 import BeautifulSoup

from elections_calendar.dates import parse_date_text, plausible, relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import (
    MAX_DETAIL,
    Claim,
    DateMeaning,
    InputUnit,
    Outcome,
    Reason,
    ReasonCode,
)
from elections_calendar.offices import (
    is_executive_title,
    split_offices,
    unnamed_parts,
)
from elections_calendar.sources.base import (
    Getter,
    PageParse,
    PageRequest,
    ParseResult,
    RawPage,
    RawPages,
    Registries,
    fetch_chain,
    missing_pages,
    page_failure,
    parse_pages,
    part_scopes,
)
from elections_calendar.sources.tables import cell_text, complete_html
from elections_calendar.text import collapse_ws
from elections_calendar.window import Window

URL = "https://www.eisa.org/election-calendar/"
AJAX = (
    "https://www.eisa.org/wp-admin/admin-ajax.php"
    "?action=wp_ajax_ninja_tables_public_action&table_id={table_id}&target_action=get-all-data"
)
HEADING = "eisa african election calendar {year}"
FIELDS = ("country", "election", "date")
CALENDAR = "calendar"

_TABLE_ID = re.compile(r"[0-9]{1,9}")
_LEAD_ROUND = re.compile(r"\s*(?P<q>(?P<w>first|second)\s+round\s*:)\s*", re.IGNORECASE)
_TRAIL_ROUND = re.compile(
    r"\s*(?P<q>\((?:(?P<w>first|second)\s+round|run-?off)\))\s*$", re.IGNORECASE
)
_HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


def year_request(year: int, table_id: str) -> PageRequest:
    return PageRequest(f"y{year}", AJAX.format(table_id=table_id), year)


def _read_calendar(text: str, window: Window) -> tuple[dict[int, str], list[Reason]] | str:
    """The table id per window year and the year notes, or the first failing check's detail."""
    if not complete_html(text):
        return "page does not end with </html>"
    soup = BeautifulSoup(text, "lxml")
    headings = [(h, cell_text(h).casefold()) for h in soup.find_all(_HEADINGS)]
    ids: dict[int, str] = {}
    notes: list[Reason] = []
    for year in window.years:
        title = HEADING.format(year=year)
        matched = [h for h, folded in headings if folded == title]
        if not matched:
            late = year > window.today.year
            code: ReasonCode = "not_published_yet" if late else "required_year_missing"
            notes.append(Reason(code, f"no heading '{title}'"))
            continue
        per_heading: list[list[str]] = []
        for heading in matched:
            found = (
                [
                    str(t.get("data-footable_id", "")).strip()
                    for t in heading.parent.find_all("table", attrs={"data-footable_id": True})
                ]
                if heading.parent is not None
                else []
            )
            per_heading.append(found)
        distinct = {i for found in per_heading for i in found}
        if (
            len(distinct) != 1
            or any(len(found) != 1 for found in per_heading)
            or not _TABLE_ID.fullmatch(next(iter(distinct)))
        ):
            shown = ", ".join(sorted(distinct)) or "(none)"
            return f"heading '{title}' has table ids {shown}"
        ids[year] = next(iter(distinct))
    return ids, notes


def expected(window: Window, pages: Sequence[RawPage]) -> tuple[PageRequest, ...]:
    """Every request that the pages received so far imply, the calendar page first (P46)."""
    requests = [PageRequest(CALENDAR, URL)]
    page = next((p for p in pages if p.request.key == CALENDAR), None)
    if page is None or page_failure(page) is not None:
        return tuple(requests)
    try:
        read = _read_calendar(page.result.text(), window)
    except RecursionError:
        return tuple(requests)
    if isinstance(read, str):
        return tuple(requests)
    requests += [year_request(year, table_id) for year, table_id in read[0].items()]
    return tuple(requests)


def _cut_round(date_text: str) -> tuple[str, str | None, int | None]:
    """The date text without its round qualifier, the qualifier as written and its round (P57)."""
    rest = date_text
    qualifier: str | None = None
    number: int | None = None
    for pattern in (_LEAD_ROUND, _TRAIL_ROUND):
        match = pattern.match(rest) if pattern is _LEAD_ROUND else pattern.search(rest)
        if match is None or qualifier is not None:
            continue
        qualifier = match["q"].strip()
        word = match["w"]
        number = 1 if word is not None and word.casefold() == "first" else 2
        rest = collapse_ws(rest[: match.start()] + " " + rest[match.end() :])
    return rest, qualifier, number


def _fields(element: Any) -> tuple[str, str, str] | None:
    """The row's collapsed country, election and date, or ``None`` when it gives none."""
    if not isinstance(element, dict):
        return None
    value = element.get("value")
    if not isinstance(value, dict):
        return None
    texts = [value.get(name) for name in FIELDS]
    if not all(isinstance(t, str) for t in texts):
        return None
    country, election, date_text = (collapse_ws(t) for t in texts if isinstance(t, str))
    return country, election, date_text


def _years_of(date_text: str) -> set[int]:
    """The years a readable date touches (P62); empty when the text gives no readable date."""
    parse = parse_date_text(_cut_round(date_text)[0])
    if not parse.ok or not parse.spans:
        return set()
    years: set[int] = set()
    for span in parse.spans:
        if span.start is not None and span.end is not None:
            years.update(range(span.start.year, span.end.year + 1))
        else:
            years.add(span.year)
    return years


@dataclass(slots=True)
class _State:
    """What flows from table to table, in fetch order."""

    claimed: dict[tuple[str, str, str], str] = field(default_factory=dict)


class Eisa:
    source = "eisa"

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return (PageRequest(CALENDAR, URL),)

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        return fetch_chain(lambda pages: expected(window, pages), fetcher, deadline)

    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult:
        state = _State()
        res = parse_pages(
            self.source, raw, lambda page: self._parse_page(page, window, registries, state)
        )
        notes = list(res.notes) + missing_pages(expected(window, raw.pages), raw)
        return ParseResult(res.source, res.units, res.claims, res.coverage, tuple(notes))

    def _parse_page(
        self, page: RawPage, window: Window, registries: Registries, state: _State
    ) -> PageParse:
        key = page.request.key
        if key == CALENDAR:
            read = _read_calendar(page.result.text(), window)
            if isinstance(read, str):
                return PageParse("layout_not_recognised", detail=read)
            return PageParse("ok", notes=read[1])
        year = page.request.year
        try:
            data = json.loads(page.result.body)
        except (ValueError, RecursionError):
            return PageParse("layout_not_recognised", detail="the body is not JSON")
        if not isinstance(data, list):
            return PageParse("layout_not_recognised", detail="the body is not a JSON list")
        if not data:
            return PageParse("layout_not_recognised", detail="the table has no rows")
        if not any(_fields(e) is not None for e in data):
            return PageParse(
                "layout_not_recognised", detail="no row has country, election and date"
            )
        out = PageParse("ok", year=year)
        inherited: str | None = None
        dated_years: set[int] = set()
        for i, element in enumerate(data, 1):
            uid = f"{self.source}:{key}/r{i}"
            given = _fields(element)
            if given is None:
                text = json.dumps(element, ensure_ascii=False, sort_keys=True)[:MAX_DETAIL]
                out.units.append(
                    InputUnit(uid, self.source, text, "unparsed", "row_unrecognised", "unknown")
                )
                inherited = None
                continue
            country, election, date_text = given
            dated_years |= _years_of(date_text)
            shown = country
            if country:
                inherited = country
            elif inherited is not None:
                country, shown = inherited, f"{inherited} (from the row above)"
            else:
                shown = ""
            self._row(out, uid, (country, shown), election, date_text, window, registries, state)
        if year is not None and dated_years and year not in dated_years:
            out.notes.append(Reason("coverage_gap", f"{key} has no {year} date"))
        return out

    def _row(
        self,
        out: PageParse,
        uid: str,
        names: tuple[str, str],
        election: str,
        date_text: str,
        window: Window,
        registries: Registries,
        state: _State,
    ) -> None:
        country, shown = names
        text = " | ".join(t for t in (shown, election, date_text) if t)
        rel = relevance(date_text, window.start)

        def unit(
            outcome: Outcome, reason: str | None, leftover: str = "", dup: str | None = None
        ) -> None:
            out.units.append(
                InputUnit(uid, self.source, text, outcome, reason, rel, leftover, duplicate_of=dup)
            )

        place = registries.places.resolve(country) if country else None
        if place is None:
            unit("unparsed", "place_missing")
            return
        dup_key = (country, election, date_text)
        if dup_key in state.claimed:
            unit("ignored", "duplicate", dup=state.claimed[dup_key])
            return
        if not election:
            unit("unparsed", "office_missing")
            return
        rest, qualifier, q_round = _cut_round(date_text)
        parse = parse_date_text(rest)
        if parse.ok and not parse.spans:
            if parse.status_claim == "postponed":
                unit("unparsed", "no_new_date", date_text)
            else:
                unit("unparsed", "date_missing")
            return
        if not parse.ok or len(parse.spans) != 1:
            unit("unparsed", "date_unparsed", parse.leftover or date_text)
            return
        span = parse.spans[0]
        if not plausible(span, window.today):
            unit("unparsed", "implausible_date")
            return
        if is_executive_title(election):
            unit("unparsed", "office_not_modelled", election)
            return

        institutions = registries.institutions
        parts = split_offices(election, place.place_id, institutions) or [election]
        scopes = part_scopes(parts, place, registries)
        unnamed = unnamed_parts(election, place.place_id, institutions)
        round_clash = qualifier is not None and any(
            sc.office.round not in (None, q_round) for sc in scopes
        )
        reason: str | None = None
        leftover = ""
        if not place.registered:
            reason = "place_unregistered"
        elif round_clash and qualifier is not None:
            reason, leftover = "round_conflict", qualifier
        elif unnamed:
            reason, leftover = "office_unrecognised", ", ".join(unnamed)
        elif not all(sc.office.recognised for sc in scopes):
            reason = "office_unrecognised"
        elif any(sc.unresolved for sc in scopes):
            reason = "level_unresolved"
        unit("parsed" if reason is None else "partial", reason, leftover)
        state.claimed[dup_key] = uid

        one_day = span.precision == "day" and span.start == span.end
        months = span.precision == "month" and span.start != _month_start(span.end)
        meaning: DateMeaning = "voting_period" if one_day and not parse.phased else "unknown"
        if months and not parse.phased:
            meaning = "expected_window"
        for n, (part, sc) in enumerate(zip(parts, scopes, strict=True)):
            office = sc.office
            if office.round is None:
                round_ = q_round
            else:
                round_ = office.round if q_round in (None, office.round) else None
            out.claims.append(
                Claim(
                    unit_id=uid,
                    claim_id=f"{uid}#{n}",
                    source=self.source,
                    link=URL,
                    source_event_id=None,
                    place_raw=country,
                    place_id=place.place_id,
                    jurisdiction=sc.jurisdiction,
                    jurisdiction_kind=sc.jurisdiction_kind,
                    level=sc.level,
                    institution=office.institution,
                    office_class=office.office_class,
                    office_label=part,
                    aggregate=office.aggregate,
                    kind=office.kind,
                    round=round_,
                    span=span,
                    date_meaning=meaning,
                    date_status=parse.date_status,
                    date_text=date_text,
                    status_claim=parse.status_claim,
                    previous_date_text=parse.previous_text,
                    evidence_kind="calendar",
                    indirect=False,
                )
            )


def _month_start(end: date | None) -> date | None:
    return end.replace(day=1) if end is not None else None

