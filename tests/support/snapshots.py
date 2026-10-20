"""Synthetic snapshots for the acceptance tests: pages given as counts, so tests read as tables.

``SynthPage("elections", 100)`` is a page of 100 parsed units with one claim each;
``SynthPage("elections", 100, 40)`` parses the first 40 and ignores the rest. Tests that need
particular claims pass them as ``claims=(Claim, ...)``; each claim's unit is then a parsed unit.
A page that gave no units (a timeout, a changed layout) has none, except the claims and the
``extra`` units given explicitly: those model an adapter that broke the rules, which ``decide``
must ignore.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import cast, get_args

from elections_calendar.ledger import LedgerReport
from elections_calendar.model import (
    MAX_DETAIL,
    Claim,
    DateSpan,
    FetchOutcome,
    IgnoredReason,
    InputUnit,
    Outcome,
    Reason,
    ReasonCode,
    Relevance,
    StatusClaim,
)
from elections_calendar.snapshots import (
    Baseline,
    CoverageGap,
    Disappeared,
    HistoryEntry,
    Snapshot,
    build_snapshot,
)
from elections_calendar.sources.base import (
    PageCoverage,
    PageOutcome,
    PageRequest,
    ParseResult,
    RawPage,
    RawPages,
)
from elections_calendar.window import window_for
from tests.support.claims import mk
from tests.support.pages import result

T0 = datetime(2026, 10, 1, 6, tzinfo=UTC)
NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)
REGISTRY = "r" * 64
_FETCH_OUTCOMES: frozenset[str] = frozenset(get_args(FetchOutcome))
_WITH_UNITS = ("ok", "valid_empty")


@dataclass(frozen=True)
class SynthPage:
    """One page; ``extra`` units come after the others, ``texts`` names claim units' texts."""

    key: str
    units: int = 0
    claims: int | tuple[Claim, ...] | None = None
    outcome: PageOutcome = "ok"
    scope: str | None = None
    year: int | None = None
    ignored_reason: IgnoredReason = "no_expected_date"
    day: date = date(2026, 11, 15)
    status: StatusClaim | None = None
    sei: str | None = None
    extra: tuple[InputUnit, ...] = ()
    texts: tuple[tuple[str, str], ...] = ()
    fetched_at: datetime | None = None  # None: the snapshot's time


def _unit(uid: str, source: str, text: str, outcome: Outcome, reason: str | None) -> InputUnit:
    return InputUnit(uid, source, text, outcome, reason, "in_or_after_window")


def _page(source: str, page: SynthPage) -> tuple[list[InputUnit], list[Claim]]:
    prefix = f"{source}:{page.key}/"
    texts = dict(page.texts)
    units: list[InputUnit] = []
    claims: list[Claim] = []
    if isinstance(page.claims, tuple):
        claims = list(page.claims)
        owners = list(dict.fromkeys(c.unit_id for c in claims))
        units = [_unit(u, source, texts.get(u, f"{u} text"), "parsed", None) for u in owners]
        if page.outcome in _WITH_UNITS:
            units += [
                _unit(f"{prefix}x{j}", source, f"{page.key} ignored {j}", "ignored", page.ignored_reason)
                for j in range(1, page.units - len(owners) + 1)
            ]
    elif page.outcome in _WITH_UNITS:
        parsed = page.units if page.claims is None else page.claims
        for i in range(1, page.units + 1):
            uid = f"{prefix}r{i}"
            if i <= parsed:
                units.append(_unit(uid, source, texts.get(uid, f"{page.key} row {i}"), "parsed", None))
                claims.append(
                    mk(
                        uid,
                        span=DateSpan.day(page.day),
                        status_claim=page.status,
                        source_event_id=None if page.sei is None else f"{source}:{page.sei}{i}",
                    )
                )
            else:
                units.append(_unit(uid, source, f"{page.key} row {i}", "ignored", page.ignored_reason))
    return units + list(page.extra), claims


def synth(
    source: str = "osce",
    pages: Sequence[SynthPage] = (),
    fetched_at: datetime = T0,
    parser_version: str = "2.0",
    registry: str = REGISTRY,
    notes: Sequence[Reason] = (),
) -> Snapshot:
    """A snapshot built through ``build_snapshot`` from synthetic raw pages and a parse result."""
    raw: list[RawPage] = []
    unfinished: list[PageRequest] = []
    units: list[InputUnit] = []
    claims: list[Claim] = []
    coverage: list[PageCoverage] = []
    for page in pages:
        request = PageRequest(
            page.key, f"https://{source}.test/{page.key}", year=page.year, scope=page.scope
        )
        if page.outcome == "unfinished":
            unfinished.append(request)
        else:
            outcome: FetchOutcome = (
                cast(FetchOutcome, page.outcome) if page.outcome in _FETCH_OUTCOMES else "ok"
            )
            fetched = result(b"", url=request.url, outcome=outcome)
            raw.append(RawPage(request, fetched, page.fetched_at or fetched_at))
        page_units, page_claims = _page(source, page)
        units += page_units
        claims += page_claims
        has_units = page.outcome in _WITH_UNITS
        coverage.append(
            PageCoverage(
                page.key,
                page.year,
                page.outcome,
                f"{source}:{page.key}/" if has_units else None,
                len(page_units) if has_units else 0,
            )
        )
    parsed = ParseResult(source, tuple(units), tuple(claims), tuple(coverage), tuple(notes))
    return build_snapshot(
        RawPages(source, tuple(raw), tuple(unfinished)),
        parsed,
        parser_version=parser_version,
        registry_version=registry,
        years=window_for(NOW).years,
    )


def promoted(
    snapshot: Snapshot,
    history: Sequence[HistoryEntry] = (),
    disappeared: Sequence[Disappeared] = (),
    coverage_gaps: Sequence[CoverageGap] = (),
) -> Baseline:
    return Baseline(snapshot, tuple(history), tuple(disappeared), tuple(coverage_gaps), True, True)


def report(
    snapshot: Snapshot, problems: Sequence[str] = (), discovery: bool = False
) -> LedgerReport:
    """A ledger report of the snapshot; a problem gives ``ledger_mismatch`` or, with
    ``discovery``, ``discovery_mismatch``."""
    outcomes: dict[Outcome, int] = dict.fromkeys(get_args(Outcome), 0)
    relevance: dict[Relevance, int] = dict.fromkeys(get_args(Relevance), 0)
    for u in snapshot.units:
        outcomes[u.outcome] += 1
        if u.outcome in ("partial", "unparsed"):
            relevance[u.relevance] += 1
    ignored = Counter(u.reason for u in snapshot.units if u.outcome == "ignored" and u.reason)
    code: ReasonCode = "discovery_mismatch" if discovery else "ledger_mismatch"
    return LedgerReport(
        source=snapshot.source,
        units_seen=len(snapshot.units),
        outcomes=outcomes,
        ignored_reasons=dict(ignored),
        relevance=relevance,
        problems=tuple(problems),
        reasons=(Reason(code, problems[0][:MAX_DETAIL]),) if problems else (),
    )
