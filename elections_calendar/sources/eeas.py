"""The EEAS adapter (spec section 7): EU election observation missions.

The page holds one table whose cells link to ``EOM <country> <year>`` pages, with year
headings between the rows. Every cell is an input unit. A mission names a year, never a
date, so a claim has year precision and ``date_meaning="unknown"`` (P39).
"""

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup, Tag

from elections_calendar.dates import relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import Claim, DateSpan, InputUnit, Outcome, Reason
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
    anchor_href,
    cell_text,
    complete_html,
    dated_text_beside,
    own_rows,
    row_cells,
    source_link,
)
from elections_calendar.window import Window

URL = "https://www.eeas.europa.eu/eeas/eu-election-observation-missions-1_en"
HOSTS = ("eeas.europa.eu",)
MISSION = re.compile(r"EOM (?P<country>.+) (?P<year>\d{4})")
_YEAR = re.compile(r"\d{4}")
_YEARS_AWAY = 5
LABEL = "EU election observation mission"


def _mission_tables(soup: BeautifulSoup) -> list[Tag]:
    """The tables holding a link of their own (not in a nested table) that matches ``MISSION``."""
    hits: list[Tag] = []
    for table in soup.find_all("table"):
        for a in table.find_all("a"):
            if (
                isinstance(a, Tag)
                and a.find_parent("table") is table
                and MISSION.fullmatch(cell_text(a))
            ):
                hits.append(table)
                break
    return hits


class Eeas:
    source = "eeas"

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return (PageRequest("missions", URL),)

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
        tables = _mission_tables(soup)
        if len(tables) != 1:
            return PageParse(
                "layout_not_recognised", detail=f"{len(tables)} tables with EOM links"
            )
        table = tables[0]
        parsed = PageParse("ok")
        beside = dated_text_beside(table)
        if beside is not None:
            parsed.notes.append(Reason("coverage_gap", f"dated text beside the table: {beside}"))
        given: dict[tuple[str, str], str] = {}  # (text, claim link) -> unit of the first claim
        for i, tr in enumerate(own_rows(table, head=True), 1):
            for j, cell in enumerate(row_cells(tr), 1):
                unit_id = f"{self.source}:{page.request.key}/r{i}c{j}"
                self._parse_cell(parsed, unit_id, cell, given, window, registries)
        return parsed

    def _parse_cell(
        self,
        out: PageParse,
        unit_id: str,
        cell: Tag,
        given: dict[tuple[str, str], str],
        window: Window,
        registries: Registries,
    ) -> None:
        text = cell_text(cell)
        rel = relevance(text, window.start)

        def unit(outcome: Outcome, reason: str | None, duplicate_of: str | None = None) -> None:
            out.units.append(
                InputUnit(unit_id, self.source, text, outcome, reason, rel, "", duplicate_of)
            )

        if not text:
            unit("ignored", "empty_cell")
            return
        if _YEAR.fullmatch(text):
            unit("ignored", "year_heading")
            return
        mission = MISSION.fullmatch(text)
        if mission is None:
            unit("unparsed", "unrecognised_cell")
            return
        href = anchor_href(cell.find("a"))
        accepted = source_link(URL, href, HOSTS) if href is not None else None
        link = accepted or URL
        earlier = given.get((text, link))
        if earlier is not None:
            unit("ignored", "duplicate", earlier)
            return
        country = mission["country"]
        place = registries.places.resolve(country)
        if place is None:
            unit("unparsed", "place_missing")
            return
        year = int(mission["year"])
        if abs(year - window.today.year) > _YEARS_AWAY:
            unit("unparsed", "implausible_date")
            return
        reason: str | None = None
        if not place.registered:
            reason = "place_unregistered"
        elif href is not None and accepted is None:
            reason = "link_rejected"
        unit("parsed" if reason is None else "partial", reason)
        given[(text, link)] = unit_id
        out.claims.append(
            Claim(
                unit_id=unit_id,
                claim_id=f"{unit_id}#0",
                source=self.source,
                link=link,
                source_event_id=None,
                place_raw=country,
                place_id=place.place_id,
                jurisdiction=None,
                jurisdiction_kind="nationwide",
                level="unknown",
                institution=None,
                office_class="general",
                office_label=LABEL,
                aggregate=True,
                kind="aggregate",
                round=None,
                span=DateSpan.of_year(year),
                date_meaning="unknown",
                date_status="unknown",
                date_text=mission["year"],
                status_claim=None,
                previous_date_text=None,
                evidence_kind="observation",
                indirect=False,
            )
        )
