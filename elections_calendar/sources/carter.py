"""The Carter Center adapter (spec section 7): elections the Center has observed.

The page holds heading-bound tables, not a header table: the rows under "Elections Monitored
by The Carter Center" and under "Expert Missions". Every row is an input unit. The date cell
lists ``Month YYYY`` tokens; each token that parses and is near today gives one claim.
"""

import re
from collections.abc import Iterator

from bs4 import BeautifulSoup, Tag

from elections_calendar.dates import parse_date_text, plausible, relevance
from elections_calendar.fetch import Deadline
from elections_calendar.model import Claim, DateSpan, InputUnit, Outcome, Reason
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

URL = "https://www.cartercenter.org/programs/democracy/elections-observed/"
HOSTS = ("cartercenter.org",)
SECTIONS = (
    (
        "elections monitored by the carter center",
        "monitored",
        "Carter Center election observation",
    ),
    ("expert missions", "expert", "Carter Center expert mission"),
)
FOOTNOTE = (
    "*these missions were targeted or focused observations and did not result in statements "
    "on the overall administration of the electoral process."
)
_SPLIT = re.compile(r"[,;]")
_AND = re.compile(r"^and\s+", re.IGNORECASE)


def _tokens(date_text: str) -> list[str]:
    found: list[str] = []
    for part in _SPLIT.split(date_text):
        token = _AND.sub("", part.strip()).strip()
        if token:
            found.append(token)
    return found


def _section_table(h2s: list[Tag], heading: str) -> str | Tag | None:
    """The section's one top-level table; ``None`` if the heading is missing; ``""`` if the
    section has no table; else the ``layout_not_recognised`` detail.
    """
    hits = [h for h in h2s if cell_text(h).casefold() == heading]
    if not hits:
        return None
    if len(hits) > 1:
        return f"heading '{heading}' appears {len(hits)} times"
    start = hits[0]
    at = next(i for i, h in enumerate(h2s) if h is start)
    stop = h2s[at + 1] if at + 1 < len(h2s) else None
    tables: list[Tag] = []
    for el in start.next_elements:
        if el is stop:
            break
        if isinstance(el, Tag) and el.name == "table" and el.find_parent("table") is None:
            tables.append(el)
    if len(tables) > 1:
        return f"section '{heading}' has {len(tables)} tables"
    return tables[0] if tables else ""


class Carter:
    source = "carter"
    parser_version = PARSER_VERSION

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return (PageRequest("observed", URL),)

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
        h2s = [h for h in soup.find_all("h2") if isinstance(h, Tag)]
        parsed = PageParse("ok")
        usable = 0
        for heading, slug, label in SECTIONS:
            found = _section_table(h2s, heading)
            if found is None:
                parsed.notes.append(Reason("coverage_gap", f"section not found: {heading}"))
                continue
            if not isinstance(found, Tag):
                if found:
                    return PageParse("layout_not_recognised", detail=found)
                parsed.notes.append(Reason("coverage_gap", f"section has no table: {heading}"))
                continue
            rows = own_rows(found, head=True)
            if not rows:
                return PageParse("layout_not_recognised", detail="the table has no rows")
            usable += 1
            beside = dated_text_beside(found)
            if beside is not None:
                parsed.notes.append(
                    Reason("coverage_gap", f"dated text beside the table: {beside}")
                )
            for i, tr in enumerate(rows, 1):
                unit_id = f"{self.source}:{page.request.key}/{slug}-r{i}"
                self._parse_row(parsed, unit_id, tr, found, label, window, registries)
        if not usable:
            return PageParse("layout_not_recognised", detail="no section found")
        return parsed

    def _parse_row(
        self,
        out: PageParse,
        unit_id: str,
        tr: Tag,
        table: Tag,
        label: str,
        window: Window,
        registries: Registries,
    ) -> None:
        cells = row_cells(tr)
        texts = [cell_text(c) for c in cells]
        unit_text = " | ".join(t for t in texts if t)
        date_text = texts[1] if len(cells) > 1 else ""
        rel = relevance(date_text, window.start)

        def unit(outcome: Outcome, reason: str | None, leftover: str = "") -> None:
            out.units.append(
                InputUnit(unit_id, self.source, unit_text, outcome, reason, rel, leftover)
            )

        thead = tr.find_parent("thead")
        if (
            thead is not None
            and thead.find_parent("table") is table
            and cells
            and all(c.name == "th" for c in cells)
        ):
            unit("ignored", "header_row")
            return
        if len(cells) == 1 and texts[0].casefold() == FOOTNOTE:
            unit("ignored", "footnote")
            return
        if len(cells) < 2:
            unit("unparsed", "too_few_cells")
            return
        country = texts[0]
        place = registries.places.resolve(country)
        if place is None:
            unit("unparsed", "place_missing")
            return
        tokens = _tokens(date_text)
        if not tokens:
            unit("unparsed", "date_missing")
            return

        made: list[tuple[str, DateSpan, bool]] = []
        bad: list[str] = []
        future: list[str] = []
        seen: set[tuple[DateSpan, bool]] = set()
        for token in tokens:
            targeted = token.endswith("*")
            parse = parse_date_text(token[:-1].rstrip() if targeted else token)
            if not parse.ok or parse.status_claim is not None or len(parse.spans) != 1:
                bad.append(token)
                continue
            span = parse.spans[0]
            if not plausible(span, window.today):
                last = span.end.year if span.end else span.year
                if last >= window.today.year:
                    future.append(token)
                continue
            if (span, targeted) in seen:
                continue
            seen.add((span, targeted))
            made.append((token, span, targeted))
        extra = [t for t in texts[2:] if t]
        leftover = ", ".join(bad + future + extra)

        href = anchor_href(cells[0].find("a"))
        accepted = source_link(URL, href, HOSTS) if href is not None else None
        if not made:
            unit("unparsed", "date_unparsed" if bad else "implausible_date", leftover)
            return
        reason: str | None = None
        if bad:
            reason = "date_unparsed"
        elif future:
            reason = "implausible_date"
        elif extra:
            reason = "extra_cells"
        elif not place.registered:
            reason = "place_unregistered"
        elif href is not None and accepted is None:
            reason = "link_rejected"
        unit("parsed" if reason is None else "partial", reason, leftover)
        for n, (token, span, targeted) in enumerate(made):
            out.claims.append(
                Claim(
                    unit_id=unit_id,
                    claim_id=f"{unit_id}#{n}",
                    source=self.source,
                    link=accepted or URL,
                    source_event_id=None,
                    place_raw=country,
                    place_id=place.place_id,
                    jurisdiction=None,
                    jurisdiction_kind="nationwide",
                    level="unknown",
                    institution=None,
                    office_class="general",
                    office_label=label + (" (targeted)" if targeted else ""),
                    aggregate=True,
                    kind="aggregate",
                    round=None,
                    span=span,
                    date_meaning="unknown",
                    date_status="unknown",
                    date_text=token,
                    status_claim=None,
                    previous_date_text=None,
                    evidence_kind="observation",
                    indirect=False,
                )
            )
