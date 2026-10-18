"""The OSCE/ODIHR adapter (spec section 7): the one elections table on odihr.osce.org.

Every body row is an input unit. A parsed or partial row gives one claim; an unparsed row
gives none. Columns are found by header text, never by position.
"""

from collections.abc import Iterator

from bs4 import BeautifulSoup, Tag

from elections_calendar.dates import parse_date_text, plausible, relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import Claim, InputUnit, Outcome, Reason, StatusClaim
from elections_calendar.offices import is_executive_title
from elections_calendar.sources.base import (
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
    complete_html,
    dated_text_beside,
    header_columns,
    header_tables,
    own_rows,
    row_cells,
    source_link,
)
from elections_calendar.window import Window

URL = "https://odihr.osce.org/odihr/elections"
HOSTS = ("odihr.osce.org", "osce.org")
HEADERS = ("date", "country", "election", "activity")
_STATUS: dict[str, StatusClaim] = {
    "postponed": "postponed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
}
_PLAIN_BADGES = ("upcoming", "past")


class Osce:
    source = "osce"

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return (PageRequest("elections", URL),)

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        return fetch_pages(self.requests(window), fetcher, deadline)

    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult:
        return parse_pages(
            self.source, raw, lambda page: self._parse_page(page, window, registries)
        )

    def _parse_page(self, page: RawPage, window: Window, registries: Registries) -> PageParse:
        text = page.result.text()
        if not complete_html(text):
            return PageParse("layout_not_recognised", detail="page does not end with </html>")
        soup = BeautifulSoup(text, "lxml")
        tables = header_tables(soup, HEADERS)
        if len(tables) != 1:
            return PageParse(
                "layout_not_recognised",
                detail=f"{len(tables)} tables with headers {', '.join(HEADERS)}",
            )
        table = tables[0]
        cols, repeated = header_columns(table, HEADERS)
        if repeated:
            return PageParse(
                "layout_not_recognised", detail="repeated header: " + ", ".join(repeated)
            )
        rows = own_rows(table)
        if not rows:
            return PageParse("layout_not_recognised", detail="the table has no rows")
        parsed = PageParse("ok")
        beside = dated_text_beside(table)
        if beside is not None:
            parsed.notes.append(Reason("coverage_gap", f"dated text beside the table: {beside}"))
        for i, tr in enumerate(rows, 1):
            self._parse_row(parsed, f"osce:{page.request.key}/r{i}", tr, cols, window, registries)
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
        div = cells[cols["date"]].find("div") if len(cells) > cols["date"] else None
        date_text = cell_text(div) if isinstance(div, Tag) else ""
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
        if not isinstance(div, Tag):
            unit("unparsed", "date_unparsed", texts[cols["date"]])
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
        if is_executive_title(label):
            unit("unparsed", "office_not_modelled", label)
            return

        badges = [cell_text(b) for b in cells[cols["date"]].find_all("span")]
        mapped = {_STATUS[b.casefold()] for b in badges if b.casefold() in _STATUS}
        unrecognised = any(
            b.casefold() not in _STATUS and b.casefold() not in _PLAIN_BADGES for b in badges
        )
        if parse.status_claim is not None:
            mapped.add(parse.status_claim)
        conflict = len(mapped) > 1
        status_claim: StatusClaim | None = next(iter(mapped)) if len(mapped) == 1 else None
        leftover = (
            " ".join(b for b in badges if b.casefold() not in _PLAIN_BADGES)
            if conflict or unrecognised
            else ""
        )

        scope = label_scope(label, place, registries)
        office = scope.office
        hrefs: list[object] = []
        for key in ("activity", "country"):
            anchor = cells[cols[key]].find("a")
            if isinstance(anchor, Tag):
                hrefs.append(anchor.get("href"))
        link = next((u for u in (source_link(URL, h, HOSTS) for h in hrefs) if u), None)

        reason: str | None = None
        if span.precision == "day" and (
            span.start is None or tr.get("data-filter-date") != span.start.isoformat()
        ):
            reason = "filter_date_mismatch"
        elif conflict:
            reason = "status_conflict"
        elif unrecognised:
            reason = "status_unrecognised"
        elif not place.registered:
            reason = "place_unregistered"
        elif not office.recognised:
            reason = "office_unrecognised"
        elif scope.unresolved:
            reason = "level_unresolved"
        elif hrefs and link is None:
            reason = "link_rejected"
        unit("parsed" if reason is None else "partial", reason, leftover)
        out.claims.append(
            Claim(
                unit_id=unit_id,
                claim_id=f"{unit_id}#0",
                source=self.source,
                link=link or URL,
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
                date_meaning="voting_period",
                date_status=parse.date_status,
                date_text=date_text,
                status_claim=status_claim,
                previous_date_text=parse.previous_text,
                evidence_kind="calendar",
                indirect="(indirect)" in label.casefold(),
            )
        )
