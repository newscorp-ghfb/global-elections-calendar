"""The adapter contract (spec §8, §9.4).

Every source adapter fetches a few pages (``fetch``), then parses them into
input units and claims (``parse``); the ledger and the runner build on the
types here. ``fetch_pages`` runs requests one at a time, in order (§8).
"""

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.model import Claim, InputUnit, Reason, RecordError, _check_fields
from elections_calendar.offices import InstitutionRegistry
from elections_calendar.places import PlaceRegistry, SubdivisionIndex
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
    """All pages of one source run; ``unfinished`` were not fetched before the deadline."""

    source: str
    pages: tuple[RawPage, ...]
    unfinished: tuple[PageRequest, ...] = ()


@dataclass(frozen=True, slots=True)
class PageCoverage:
    """What one page gave. ``unit_prefix`` (e.g. ``"electionguide:upcoming/"``) is set
    exactly when the outcome is ``ok`` or ``valid_empty``; the ledger owns the discovery rules.
    """

    key: str
    year: int | None
    outcome: PageOutcome
    unit_prefix: str | None
    units_seen: int
    revid: int | None = None

    def __post_init__(self) -> None:
        _check_fields(self)
        if (self.unit_prefix is not None) != (self.outcome in _PAGES_WITH_UNITS):
            raise RecordError(
                f"page {self.key!r}: unit_prefix is set exactly for ok and valid_empty pages"
            )


def coverage_reasons(coverage: Iterable[PageCoverage]) -> tuple[Reason, ...]:
    """One reason (detail = page key) per page that did not give its units."""
    reasons: list[Reason] = []
    for page in coverage:
        if page.outcome in _PAGES_WITH_UNITS:
            continue
        code = "deadline" if page.outcome == "unfinished" else page.outcome
        reasons.append(Reason(code, page.key))  # type: ignore[arg-type]
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

