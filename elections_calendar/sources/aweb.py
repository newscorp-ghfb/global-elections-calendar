"""The A-WEB adapter (spec section 7): the World Election Calendar table on aweb.org.

Every body row is an input unit. A parsed or partial row gives one claim; an unparsed row
gives none. Columns are found by header text, never by position. The page's links point to
news and election-body sites, so every claim links to the calendar page itself.
"""

import re
from collections.abc import Iterator

from bs4 import Tag

from elections_calendar.dates import parse_date_text, plausible, relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import Claim, InputUnit, Outcome, Reason
from elections_calendar.offices import is_executive_title
from elections_calendar.sources.base import (
    PARSER_VERSION,
    Getter,
    PageParse,
    PageRequest,
    ParseResult,
    RawPage,
    RawPages,
    Registries,
    fetch_pages,
    label_scope,
    parse_pages,
)
from elections_calendar.sources.tables import (
    cell_text,
    dated_text_beside,
    one_header_table,
    row_cells,
)
from elections_calendar.window import Window

URL = "https://www.aweb.org/eng/bbs/B0000007/list.do?menuNo=300052&option=all"
HEADERS = ("country", "election", "date")
_PRIMARIES = re.compile(r"\bprimar(?:y|ies)\b", re.IGNORECASE)


class Aweb:
    source = "aweb"
    parser_version = PARSER_VERSION

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return (PageRequest("calendar", URL),)

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        return fetch_pages(self.requests(window), fetcher, deadline)

    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult:
        return parse_pages(
            self.source, raw, lambda page: self._parse_page(page, window, registries)
        )

    def _parse_page(self, page: RawPage, window: Window, registries: Registries) -> PageParse:
        layout = one_header_table(page.result.text(), HEADERS)
        if isinstance(layout, str):
            return PageParse("layout_not_recognised", detail=layout)
        table, cols, rows = layout
        parsed = PageParse("ok")
        beside = dated_text_beside(table)
        if beside is not None:
            parsed.notes.append(Reason("coverage_gap", f"dated text beside the table: {beside}"))
        for i, tr in enumerate(rows, 1):
            self._parse_row(parsed, f"aweb:{page.request.key}/r{i}", tr, cols, window, registries)
        years = {c.span.year for c in parsed.claims}
        parsed.year = years.pop() if len(years) == 1 else None
        return parsed

    def _parse_row(
        self,
        out: PageParse,
        unit_id: str,
        tr: Tag,
        cols: dict[str, int],
        window: Window,
        registries: Registries,
    ) -> None:
        cells = row_cells(tr)
        texts = [cell_text(c) for c in cells]
        unit_text = " | ".join(t for t in texts if t)
        enough = len(cells) > max(cols.values())
        date_text = texts[cols["date"]] if enough else ""
        rel = relevance(date_text, window.start)

        def unit(outcome: Outcome, reason: str | None, leftover: str = "") -> None:
            out.units.append(
                InputUnit(unit_id, self.source, unit_text, outcome, reason, rel, leftover)
            )

        if not enough:
            unit("unparsed", "too_few_cells")
            return
        country = texts[cols["country"]]
        place = registries.places.resolve(country)
        if place is None:
            unit("unparsed", "place_missing")
            return
        parse = parse_date_text(date_text)
        if parse.ok and not parse.spans:
            unit("unparsed", "date_missing")
            return
        if not parse.ok or len(parse.spans) != 1:
            unit("unparsed", "date_unparsed", parse.leftover)
            return
        span = parse.spans[0]
        if not plausible(span, window.today):
            unit("unparsed", "implausible_date")
            return
        label = texts[cols["election"]]
        if is_executive_title(label) or _PRIMARIES.search(label):
            unit("unparsed", "office_not_modelled", label)
            return

        one_day = span.start is not None and span.start == span.end
        scope = label_scope(label, place, registries)
        office = scope.office
        reason: str | None = None
        if not place.registered:
            reason = "place_unregistered"
        elif not office.recognised:
            reason = "office_unrecognised"
        elif scope.unresolved:
            reason = "level_unresolved"
        unit("parsed" if reason is None else "partial", reason)
        out.claims.append(
            Claim(
                unit_id=unit_id,
                claim_id=f"{unit_id}#0",
                source=self.source,
                link=URL,
                source_event_id=None,
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
                date_meaning="voting_period" if one_day else "unknown",
                date_status="unknown",
                date_text=date_text,
                status_claim=parse.status_claim,
                previous_date_text=parse.previous_text,
                evidence_kind="calendar",
                indirect=False,
            )
        )
