"""The ElectionGuide adapter (spec §7): three table views of the IFES Election Guide.

Each view (upcoming, past, anticipated) is one ``table#electionsTable``; every body
row is an input unit. A parsed or partial row gives one claim; an unparsed or ignored row
gives none. ElectionGuide lists an election in more than one view, so a row that repeats
an earlier row of the same event is ignored as a duplicate.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date

from bs4 import BeautifulSoup, Tag

from elections_calendar.dates import make_range, parse_date_text, plausible, relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import (
    Claim,
    DateSpan,
    DateStatus,
    InputUnit,
    Outcome,
    Reason,
    RecordError,
    StatusClaim,
)
from elections_calendar.offices import is_executive_title
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
    label_scope,
    page_failure,
)
from elections_calendar.sources.tables import (
    cell_text,
    complete_html,
    header_columns,
    header_problem,
    own_rows,
    row_cells,
)
from elections_calendar.window import Window

VIEWS = ("upcoming", "past", "anticipated")
_EVENT = re.compile(r"/elections/id/(\d+)/")
_REQUIRED = {
    "country": "country",
    "election for": "election",
    "start date": "start",
    "end date": "end",
}
_READ = (*_REQUIRED, "status")
_PLAIN_STATUS = ("confirmed", "date not confirmed")


@dataclass(frozen=True, slots=True)
class _Kept:
    """A kept row, as later rows of the same event are compared with it."""

    unit_id: str
    place_id: str
    label: str
    span: DateSpan
    date_status: DateStatus
    status_claim: StatusClaim | None


@dataclass(slots=True)
class _PageParse:
    outcome: PageOutcome
    units: list[InputUnit] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    kept_starts: list[date] = field(default_factory=list)


def _columns(table: Tag) -> dict[str, int] | None:
    """Column index by role, or None when a required header is missing or repeated (U01),
    or the thead is not one plain row of th cells."""
    if header_problem(table) is not None:
        return None
    found, repeated = header_columns(table, _READ)
    if repeated or not all(head in found for head in _REQUIRED):
        return None
    cols = {role: found[head] for head, role in _REQUIRED.items()}
    if "status" in found:
        cols["status"] = found["status"]
    return cols


class ElectionGuide:
    source = "electionguide"

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return tuple(
            PageRequest(view, f"https://www.electionguide.org/elections/type/{view}/")
            for view in VIEWS
        )

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        return fetch_pages(self.requests(window), fetcher, deadline)

    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult:
        by_key = {page.request.key: page for page in raw.pages}
        units: list[InputUnit] = []
        claims: list[Claim] = []
        coverage: list[PageCoverage] = []
        kept: dict[str, list[_Kept]] = {}
        past: _PageParse | None = None
        ordered = [by_key[view] for view in VIEWS if view in by_key]
        ordered += [page for page in raw.pages if page.request.key not in VIEWS]
        for page in ordered:
            staged = {event: list(rows) for event, rows in kept.items()}
            parsed = self._parse_page(page, window, registries, staged)
            if parsed.outcome in ("ok", "valid_empty"):
                kept = staged
                units += parsed.units
                claims += parsed.claims
                key = page.request.key
                coverage.append(
                    PageCoverage(
                        key, None, parsed.outcome, f"electionguide:{key}/", len(parsed.units)
                    )
                )
            else:
                coverage.append(PageCoverage(page.request.key, None, parsed.outcome, None, 0))
            if page.request.key == "past":
                past = parsed
        for request in raw.unfinished:
            coverage.append(PageCoverage(request.key, None, "unfinished", None, 0))
        notes: list[Reason] = []
        if past is not None and past.outcome in ("ok", "valid_empty"):
            oldest = min(past.kept_starts) if past.kept_starts else None
            if oldest is None or oldest >= window.start:
                starts = oldest.isoformat() if oldest else "empty"
                notes.append(Reason("coverage_gap", f"past list starts {starts}"))
        return ParseResult(
            self.source, tuple(units), tuple(claims), tuple(coverage), tuple(notes)
        )

    def _parse_page(
        self,
        page: RawPage,
        window: Window,
        registries: Registries,
        kept: dict[str, list[_Kept]],
    ) -> _PageParse:
        failure = page_failure(page)
        if failure is not None:
            return _PageParse(failure)
        text = page.result.text()
        if not complete_html(text):
            return _PageParse("layout_not_recognised")
        try:
            table = BeautifulSoup(text, "lxml").select_one("table#electionsTable")
            if table is None:
                return _PageParse("layout_not_recognised")
            cols = _columns(table)
            if cols is None:
                return _PageParse("layout_not_recognised")
            rows = own_rows(table)
            if not rows and _EVENT.search(text):
                return _PageParse("layout_not_recognised")
            parsed = _PageParse("ok" if rows else "valid_empty")
            for i, tr in enumerate(rows, 1):
                self._parse_row(
                    parsed, f"electionguide:{page.request.key}/r{i}", tr, cols, page.request,
                    window, registries, kept,
                )
        except RecursionError:
            return _PageParse("layout_not_recognised")
        return parsed

    def _parse_row(
        self,
        out: _PageParse,
        unit_id: str,
        tr: Tag,
        cols: dict[str, int],
        request: PageRequest,
        window: Window,
        registries: Registries,
        kept: dict[str, list[_Kept]],
    ) -> None:
        cells = row_cells(tr)
        texts = [cell_text(td) for td in cells]
        unit_text = " | ".join(t for t in texts if t)
        rel = relevance(unit_text, window.start)

        def unit(outcome: Outcome, reason: str | None, **extra: str) -> None:
            out.units.append(
                InputUnit(unit_id, self.source, unit_text, outcome, reason, rel, **extra)
            )

        if len(cells) <= max(cols.values()):
            unit("unparsed", "too_few_cells")
            return
        country = texts[cols["country"]]
        place = registries.places.resolve(country)
        if place is None:
            unit("unparsed", "place_missing")
            return
        start_text, end_text = texts[cols["start"]], texts[cols["end"]]
        start, end = parse_date_text(start_text), parse_date_text(end_text)
        both = (start, end)
        if any(d.ok and not d.spans for d in both):
            unit("unparsed", "date_missing")
            return
        if any(
            not d.ok or len(d.spans) > 1 or d.spans[0].precision != "day" for d in both
        ):
            unit("unparsed", "date_unparsed")
            return
        try:
            span = make_range(start.spans[0], end.spans[0])
        except RecordError:
            unit("unparsed", "end_before_start")
            return
        if not plausible(span, window.today):
            unit("unparsed", "implausible_date")
            return
        election = cells[cols["election"]]
        link_tag = election.find("a", href=_EVENT)
        match = _EVENT.search(str(link_tag["href"])) if isinstance(link_tag, Tag) else None
        label = cell_text(link_tag) if isinstance(link_tag, Tag) else texts[cols["election"]]
        if is_executive_title(label):
            unit("unparsed", "office_not_modelled", leftover=label)
            return

        status = texts[cols["status"]].casefold() if "status" in cols else ""
        explicit: StatusClaim | None = None
        status_unrecognised = False
        if status == "postponed":
            explicit = "postponed"
        elif status in ("cancelled", "canceled"):
            explicit = "cancelled"
        elif status and status not in _PLAIN_STATUS:
            status_unrecognised = True
        if "tentative" in (start.date_status, end.date_status) or status == "date not confirmed":
            date_status: DateStatus = "tentative"
        elif (
            start.date_status == end.date_status == "confirmed"
            and status in ("", "confirmed")
        ):
            date_status = "confirmed"
        else:
            date_status = "unknown"
        status_claim: StatusClaim | None = explicit
        if status_claim is None and request.key == "past":
            status_claim = "held"

        event = match.group(1) if match else None
        if event is not None:
            for earlier in kept.get(event, ()):
                if (
                    earlier.place_id == place.place_id
                    and earlier.label == label
                    and earlier.span == span
                    and earlier.date_status == date_status
                    and status_claim in (None, earlier.status_claim)
                ):
                    unit("ignored", "duplicate", duplicate_of=earlier.unit_id)
                    return

        scope = label_scope(label, place, registries)
        office = scope.office
        reason: str | None = None
        if not place.registered:
            reason = "place_unregistered"
        elif not office.recognised:
            reason = "office_unrecognised"
        elif status_unrecognised:
            reason = "status_unrecognised"
        elif scope.unresolved:
            reason = "level_unresolved"
        leftover = texts[cols["status"]] if status_unrecognised else ""
        unit("parsed" if reason is None else "partial", reason, leftover=leftover)
        out.claims.append(
            Claim(
                unit_id=unit_id,
                claim_id=f"{unit_id}#0",
                source=self.source,
                link=(
                    f"https://www.electionguide.org/elections/id/{event}/"
                    if event
                    else request.url
                ),
                source_event_id=f"electionguide:{event}" if event else None,
                place_raw=country,
                place_id=place.place_id,
                jurisdiction=scope.jurisdiction,
                jurisdiction_kind=scope.jurisdiction_kind,
                level=scope.level,
                institution=office.institution,
                office_class=office.office_class,
                office_label=label,
                aggregate=office.aggregate,
                kind=office.kind,
                round=office.round,
                span=span,
                date_meaning="voting_period",
                date_status=date_status,
                date_text=f"{start_text} to {end_text}",
                status_claim=status_claim,
                previous_date_text=None,
                evidence_kind="calendar",
                indirect=False,
            )
        )
        if span.start is not None:
            out.kept_starts.append(span.start)
        if event is not None:
            kept.setdefault(event, []).append(
                _Kept(unit_id, place.place_id, label, span, date_status, status_claim)
            )
