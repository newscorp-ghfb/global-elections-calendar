"""The IPU Parline adapter (spec section 7): expected renewals of national chambers.

Every body row of the one elections table is an input unit. A parsed or partial row gives one
claim; an ignored or unparsed row gives none. Columns are found by header text, never by
position.
"""

import re
from collections.abc import Iterator

from bs4 import Tag

from elections_calendar.dates import parse_date_text, plausible, relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import Claim, DateSpan, InputUnit, Outcome, Reason, month_end
from elections_calendar.offices import claim_level, classify, is_executive_title
from elections_calendar.sources.base import (
    Getter,
    PageParse,
    PageRequest,
    ParseResult,
    RawPage,
    RawPages,
    Registries,
    fetch_pages,
    parse_pages,
)
from elections_calendar.sources.tables import (
    cell_text,
    dated_text_beside,
    one_header_table,
    row_cells,
    source_link,
)
from elections_calendar.window import Window

URL = "https://data.ipu.org/elections/"
HOSTS = ("data.ipu.org",)
HEADERS = (
    "country",
    "chamber",
    "principal mode of designation of members",
    "expected date of next elections",
)
_INACTIVE = re.compile(r"\((?:suspended|dissolved)\)$", re.IGNORECASE)
_EVENT = re.compile(r"/parliament/[A-Z]{2}/([A-Z]{2}-[A-Z]{2}\d{2})/")
_YEARS = 10


class Ipu:
    source = "ipu"

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return (PageRequest("elections", URL),)

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
            self._parse_row(parsed, f"ipu:{page.request.key}/r{i}", tr, cols, window, registries)
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
        date_text = texts[cols["expected date of next elections"]] if enough else ""
        rel = relevance(date_text, window.start)

        def unit(outcome: Outcome, reason: str | None, leftover: str = "") -> None:
            out.units.append(
                InputUnit(unit_id, self.source, unit_text, outcome, reason, rel, leftover)
            )

        if not enough:
            unit("unparsed", "too_few_cells")
            return
        country = texts[cols["country"]]
        chamber = texts[cols["chamber"]]
        designation = texts[cols["principal mode of designation of members"]]
        mode = designation.casefold()
        if _INACTIVE.search(chamber):
            unit("ignored", "inactive_chamber")
            return
        if mode == "appointed":
            unit("ignored", "appointed_chamber")
            return
        if mode not in ("directly elected", "indirectly elected"):
            unit("unparsed", "designation_unrecognised", designation)
            return
        place = registries.places.resolve(country)
        if place is None:
            unit("unparsed", "place_missing")
            return
        parse = parse_date_text(date_text)
        if parse.ok and not parse.spans:
            unit("ignored", "no_expected_date")
            return
        spans = parse.spans
        if (
            not parse.ok
            or len(spans) != 1
            or spans[0].start is None
            or spans[0].start != spans[0].end
        ):
            unit("unparsed", "date_unparsed", date_text)
            return
        span = spans[0]
        day = span.start
        if day is None or not plausible(span, window.today, years=_YEARS):
            unit("unparsed", "implausible_date")
            return
        if is_executive_title(chamber):
            unit("unparsed", "office_not_modelled", chamber)
            return
        if day == month_end(day.year, day.month):
            span = DateSpan.month(day.year, day.month)

        office = classify(chamber, place.place_id, "nationwide", registries.institutions)
        anchor = cells[cols["chamber"]].find("a")
        href = anchor.get("href") if isinstance(anchor, Tag) else None
        accepted = source_link(URL, href, HOSTS) if isinstance(href, str) else None
        found = _EVENT.search(accepted) if accepted else None

        reason: str | None = None
        if not place.registered:
            reason = "place_unregistered"
        elif not office.recognised:
            reason = "office_unrecognised"
        elif isinstance(href, str) and accepted is None:
            reason = "link_rejected"
        unit("parsed" if reason is None else "partial", reason)
        out.claims.append(
            Claim(
                unit_id=unit_id,
                claim_id=f"{unit_id}#0",
                source=self.source,
                link=accepted or URL,
                source_event_id=f"ipu:{found.group(1)}" if found else None,
                place_raw=country,
                place_id=place.place_id,
                jurisdiction=None,
                jurisdiction_kind="nationwide",
                level=claim_level("national", office),
                institution=office.institution,
                office_class=office.office_class,
                office_label=chamber,
                aggregate=office.aggregate,
                kind=office.kind,
                round=office.round,
                span=span,
                date_meaning="expected_window",
                date_status="tentative",
                date_text=date_text,
                status_claim=None,
                previous_date_text=None,
                evidence_kind="expected_renewal",
                indirect=mode == "indirectly elected",
            )
        )
