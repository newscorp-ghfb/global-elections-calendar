"""The adapter contract (spec §7, §9.4).

Every source adapter fetches a few pages (``fetch``), then parses them into
input units and claims (``parse``); the ledger and the runner build on the
types here. ``fetch_pages`` runs requests one at a time, in order (§8).
"""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Final, Literal, Protocol

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.model import (
    MAX_DETAIL,
    Claim,
    InputUnit,
    JurisdictionKind,
    Level,
    Reason,
    ReasonCode,
    RecordError,
    _check_fields,
)
from elections_calendar.offices import InstitutionRegistry, Office, claim_level, classify
from elections_calendar.places import Place, PlaceRegistry, SubdivisionIndex, named_subdivisions
from elections_calendar.window import Window

PageOutcome = Literal[
    "ok",
    "valid_empty",
    "not_published_yet",
    "required_year_missing",
    "layout_not_recognised",
    "unfinished",
    "http_error",
    "timeout",
    "tls_error",
    "dns_error",
    "challenge_page",
    "api_error",
    "deadline",
    "fetch_failed",
]
_PAGES_WITH_UNITS = ("ok", "valid_empty")
# The reason each page outcome without units gives. "unfinished" is "deadline" for now: the
# runner also leaves requests unfinished after a worker failure (Plan 4 may tell them apart).
PAGE_REASONS: Final[dict[PageOutcome, ReasonCode]] = {
    "not_published_yet": "not_published_yet",
    "required_year_missing": "required_year_missing",
    "layout_not_recognised": "layout_not_recognised",
    "unfinished": "deadline",
    "http_error": "http_error",
    "timeout": "timeout",
    "tls_error": "tls_error",
    "dns_error": "dns_error",
    "challenge_page": "challenge_page",
    "api_error": "api_error",
    "deadline": "deadline",
    "fetch_failed": "fetch_failed",
}


@dataclass(frozen=True, slots=True)
class PageRequest:
    """One page to fetch; ``key`` names it in unit ids and coverage."""

    key: str
    url: str
    year: int | None = None
    mediawiki: bool = False


@dataclass(frozen=True, slots=True)
class RawPage:
    """A fetched page. ``fetched_at`` is timezone-aware."""

    request: PageRequest
    result: FetchResult
    fetched_at: datetime

    def __post_init__(self) -> None:
        if self.fetched_at.utcoffset() is None:
            raise RecordError("RawPage.fetched_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class RawPages:
    """All pages of one source run; ``unfinished`` are the requests whose pages were not
    received: the worker was cut at a deadline, or it failed before fetching them.
    A received page that cannot be read also stays unfinished, and its source becomes
    ``worker_failed``.
    """

    source: str
    pages: tuple[RawPage, ...]
    unfinished: tuple[PageRequest, ...] = ()


@dataclass(frozen=True, slots=True)
class PageCoverage:
    """What one page gave. ``unit_prefix`` (e.g. ``"electionguide:upcoming/"``) is set
    exactly when the outcome is ``ok`` or ``valid_empty``; the ledger owns the discovery rules.
    ``detail`` says where a page failed (e.g. the section and element of a changed layout);
    only a page that gave no units may have one. ``year`` is the request's year, or for a
    single-page list the year its claims share (A-WEB, P31); it is never verified page scope.
    """

    key: str
    year: int | None
    outcome: PageOutcome
    unit_prefix: str | None
    units_seen: int
    revid: int | None = None
    detail: str = ""

    def __post_init__(self) -> None:
        _check_fields(self)
        if self.detail and self.outcome in _PAGES_WITH_UNITS:
            raise RecordError(f"page {self.key!r}: only a page without units has a detail")
        if (self.unit_prefix is not None) != (self.outcome in _PAGES_WITH_UNITS):
            raise RecordError(
                f"page {self.key!r}: unit_prefix is set exactly for ok and valid_empty pages"
            )


def coverage_reasons(coverage: Iterable[PageCoverage]) -> tuple[Reason, ...]:
    """One reason per page that did not give its units: the detail is the page key, followed
    by the page's own detail when it has one (cut to ``MAX_DETAIL``).
    """
    reasons: list[Reason] = []
    for page in coverage:
        if page.outcome in _PAGES_WITH_UNITS:
            continue
        detail = f"{page.key}: {page.detail}" if page.detail else page.key
        reasons.append(Reason(PAGE_REASONS[page.outcome], detail[:MAX_DETAIL]))
    return tuple(reasons)


@dataclass(frozen=True, slots=True)
class ParseResult:
    """An adapter's output: one ``PageCoverage`` per ``RawPage`` in page order, then one
    ``unfinished`` coverage per ``raw.unfinished`` request.
    """

    source: str
    units: tuple[InputUnit, ...]
    claims: tuple[Claim, ...]
    coverage: tuple[PageCoverage, ...]
    notes: tuple[Reason, ...] = ()

    @property
    def layout_ok(self) -> bool:
        return all(page.outcome != "layout_not_recognised" for page in self.coverage)

    @property
    def reasons(self) -> tuple[Reason, ...]:
        return coverage_reasons(self.coverage) + self.notes


@dataclass(frozen=True, slots=True)
class Registries:
    places: PlaceRegistry
    institutions: InstitutionRegistry
    subdivisions: SubdivisionIndex

    @classmethod
    def load(cls) -> Registries:
        return cls(PlaceRegistry.load(), InstitutionRegistry.load(), SubdivisionIndex.load())


@dataclass(frozen=True, slots=True)
class LabelScope:
    office: Office
    level: Level
    jurisdiction: str | None
    jurisdiction_kind: JurisdictionKind
    unresolved: bool


def label_scope(
    label: str, place: Place, registries: Registries, default: Level = "national"
) -> LabelScope:
    """What a calendar label says about its jurisdiction (P38).

    A label that names a registered subdivision of the place ("Republika Srpska Early
    Presidential election") makes that subdivision the jurisdiction and withholds the
    source's national ``default``; office evidence (offices.py rules) still wins. The scope
    is ``unresolved`` when the office is recognised but gives no level of its own.
    """
    subs = named_subdivisions(label, place, registries.places, registries.subdivisions)
    office = classify(
        label, place.place_id, "subdivision" if subs else "nationwide", registries.institutions
    )
    return LabelScope(
        office=office,
        level=claim_level("unknown" if subs else default, office),
        jurisdiction=", ".join(subs) or None,
        jurisdiction_kind="subdivision" if subs else "nationwide",
        unresolved=bool(subs) and office.recognised and office.level_hint is None,
    )


class Getter(Protocol):
    def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult: ...


class Adapter(Protocol):
    source: str

    def requests(self, window: Window) -> tuple[PageRequest, ...]: ...

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]: ...

    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult: ...


def fetch_pages(
    requests: Iterable[PageRequest],
    fetcher: Getter,
    deadline: Deadline,
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Iterator[RawPage]:
    """Fetch each request in turn (lazily), stamping the fetch time."""
    for request in requests:
        result = fetcher.get(request.url, deadline=deadline, mediawiki=request.mediawiki)
        yield RawPage(request, result, now())


def page_failure(page: RawPage) -> PageOutcome | None:
    """The shared download check; ``None`` leaves the layout check to the adapter."""
    result = page.result
    if result.outcome != "ok":
        return result.outcome
    if result.http_status is not None and 300 <= result.http_status < 400:
        return "http_error"  # a redirect without Location
    return None


@dataclass(slots=True)
class PageParse:
    """What one page gave, before ``parse_pages`` turns it into coverage.

    ``year`` is the request's year, or for a single-page list the year its claims share
    (A-WEB, P31); it is never verified page scope.
    """

    outcome: PageOutcome
    units: list[InputUnit] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    detail: str = ""
    year: int | None = None
    notes: list[Reason] = field(default_factory=list)


def parse_pages(
    source: str, raw: RawPages, parse_page: Callable[[RawPage], PageParse]
) -> ParseResult:
    """Run ``parse_page`` on each downloaded page, in order, and assemble the result.

    A failed download keeps its own outcome and is not parsed. A page that is not ``ok`` or
    ``valid_empty`` gives no units, claims or notes, only its detail (cut to ``MAX_DETAIL``).
    Unfinished requests come last.
    """
    units: list[InputUnit] = []
    claims: list[Claim] = []
    notes: list[Reason] = []
    coverage: list[PageCoverage] = []
    for page in raw.pages:
        key = page.request.key
        failure = page_failure(page)
        if failure is not None:
            coverage.append(PageCoverage(key, page.request.year, failure, None, 0))
            continue
        try:
            parsed = parse_page(page)
        except RecursionError:
            parsed = PageParse("layout_not_recognised", detail="nested too deep")
        if parsed.outcome in _PAGES_WITH_UNITS:
            units += parsed.units
            claims += parsed.claims
            notes += parsed.notes
            prefix = f"{source}:{key}/"
            coverage.append(
                PageCoverage(key, parsed.year, parsed.outcome, prefix, len(parsed.units))
            )
        else:
            coverage.append(
                PageCoverage(
                    key, parsed.year, parsed.outcome, None, 0, detail=parsed.detail[:MAX_DETAIL]
                )
            )
    for request in raw.unfinished:
        coverage.append(PageCoverage(request.key, request.year, "unfinished", None, 0))
    return ParseResult(source, tuple(units), tuple(claims), tuple(coverage), tuple(notes))
