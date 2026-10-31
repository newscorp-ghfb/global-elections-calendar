"""Snapshot records, their loaders and the acceptance decision (spec §5.10, §9.3; P90-P95, P105).

A snapshot is what one source gave in one run: its pages, units, claims and notes, stored
unstamped. A baseline is the snapshot a run last accepted, with the history the drop checks
need. ``load_baseline`` treats a file it cannot trust as corrupt, never as empty (P94).
``decide`` chooses what a run serves: an invalid or shrunken candidate never replaces a
baseline, and served claims keep the time their page was fetched (R19).
"""

import dataclasses
import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from elections_calendar.fetch import FetchResult, redact_text, redact_url
from elections_calendar.ledger import LedgerReport, record_problems
from elections_calendar.model import (
    MAX_ATTENTION_TEXT,
    MAX_DETAIL,
    REASON_LEVEL,
    SOURCE_NAMES,
    Acceptance,
    AttentionItem,
    AttentionKind,
    Claim,
    DropAcceptance,
    FetchOutcome,
    InputUnit,
    Reason,
    ReasonCode,
    RecordError,
    SnapshotHealth,
    _check_fields,
    _iso_date,
    _iso_moment,
    _utc_iso,
    canonical_json,
    short_id,
)
from elections_calendar.offices import DEFAULT_INSTITUTIONS
from elections_calendar.places import DEFAULT_PLACES, DEFAULT_SUBDIVISIONS
from elections_calendar.runner import SourceOutcome
from elections_calendar.sources.base import (
    PageCoverage,
    PageOutcome,
    ParseResult,
    RawPages,
    coverage_reasons,
)
from elections_calendar.text import collapse_ws, norm_name
from elections_calendar.window import Window

REGISTRY_FILES: Final = (DEFAULT_PLACES, DEFAULT_INSTITUTIONS, DEFAULT_SUBDIVISIONS)
STAMPED: Final = ("fetched_at", "fallback", "snapshot_id", "provisional")
MAX_DIAGNOSTIC = 300


def registry_version(paths: Sequence[Path] = REGISTRY_FILES) -> str:
    """SHA-256 of the registry files' names and content hashes, in the given order (P93)."""
    parts = [[path.name, hashlib.sha256(path.read_bytes()).hexdigest()] for path in paths]
    return hashlib.sha256(canonical_json(parts)).hexdigest()


def snapshot_id(units: Sequence[InputUnit], claims: Sequence[Claim]) -> str:
    """SHA-256 of the units and of the claims without their provenance (spec §5.10)."""
    body = {
        "units": [u.to_dict() for u in units],
        "claims": [
            {k: v for k, v in c.to_dict().items() if k not in STAMPED} for c in claims
        ],
    }
    return hashlib.sha256(canonical_json(body)).hexdigest()


def _unstamped(claim: Claim) -> bool:
    return (
        claim.fetched_at is None
        and not claim.fallback
        and claim.snapshot_id is None
        and not claim.provisional
    )


def _check_aware(record: object, *names: str) -> None:
    for name in names:
        if getattr(record, name).utcoffset() is None:
            raise RecordError(f"{type(record).__name__}: {name} must be timezone-aware")


def _cut(text: str) -> str:
    return text[:MAX_DIAGNOSTIC]


@dataclass(frozen=True, slots=True)
class PageDownload:
    """``FetchResult.diagnostics()``, with ``final_url`` and ``error`` redacted again and cut."""

    outcome: FetchOutcome
    stage: str
    http_status: int | None
    final_url: str
    content_type: str | None
    bytes: int
    elapsed_ms: int
    attempts: int
    error_type: str | None
    error: str | None
    api_code: str | None

    def __post_init__(self) -> None:
        _check_fields(self)

    @classmethod
    def of(cls, result: FetchResult) -> PageDownload:
        """The download record of a ``FetchResult``; nothing unredacted reaches a file (P96)."""
        return cls(
            outcome=result.outcome,
            stage=result.stage,
            http_status=result.http_status,
            final_url=_cut(redact_url(result.final_url)),
            content_type=result.content_type,
            bytes=len(result.body),
            elapsed_ms=result.elapsed_ms,
            attempts=result.attempts,
            error_type=result.error_type,
            error=None if result.error is None else _cut(redact_text(result.error)),
            api_code=result.api_code,
        )


@dataclass(frozen=True, slots=True)
class PageRecord:
    """One requested page of a snapshot; an unfinished request has no fetch time or download."""

    key: str
    scope: str
    year: int | None
    url: str
    link: str
    outcome: PageOutcome
    unit_prefix: str | None
    units_seen: int
    revid: int | None
    detail: str
    fetched_at: datetime | None
    download: PageDownload | None

    def __post_init__(self) -> None:
        _check_fields(self)
        if self.fetched_at is not None and self.fetched_at.utcoffset() is None:
            raise RecordError("PageRecord.fetched_at must be timezone-aware")
        if (self.fetched_at is None) != (self.download is None):
            raise RecordError("PageRecord: fetched_at and download go together")


@dataclass(frozen=True, slots=True)
class Snapshot:
    source: str
    snapshot_id: str
    fetched_at: datetime | None
    parser_version: str
    registry_version: str
    years: tuple[int, ...]
    pages: tuple[PageRecord, ...]
    units: tuple[InputUnit, ...]
    claims: tuple[Claim, ...]
    notes: tuple[Reason, ...]

    def __post_init__(self) -> None:
        _check_fields(self)
        if self.fetched_at is not None:
            _check_aware(self, "fetched_at")
        if any(u.source != self.source for u in self.units) or any(
            c.source != self.source for c in self.claims
        ):
            raise RecordError("Snapshot: a unit or claim of another source")
        if not all(_unstamped(c) for c in self.claims):
            raise RecordError("Snapshot: claims are stored unstamped")
        if self.snapshot_id != snapshot_id(self.units, self.claims):
            raise RecordError("Snapshot: snapshot_id does not match its units and claims")


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One promotion of one scope (§5.10 ``units_seen_history``)."""

    scope: str
    fetched_at: datetime
    units_seen: int
    claims: int

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_aware(self, "fetched_at")


@dataclass(frozen=True, slots=True)
class Disappeared:
    """A unit the last promotion no longer listed (§9.3)."""

    source_event_id: str
    unit_id: str
    text: str
    date_text: str
    start: date
    end: date
    link: str
    since: datetime

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_aware(self, "since")


@dataclass(frozen=True, slots=True)
class CoverageGap:
    """In-window claims that a year change stopped listing (P91); diagnostic, never served."""

    scope: str
    old_year: int
    new_year: int
    since: datetime
    claims: tuple[Claim, ...]

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_aware(self, "since")
        if not self.claims or not all(map(_unstamped, self.claims)) or (
            self.old_year == self.new_year
        ):
            raise RecordError("CoverageGap: a gap holds unstamped claims of a year change")


@dataclass(frozen=True, slots=True)
class Baseline:
    snapshot: Snapshot
    history: tuple[HistoryEntry, ...]
    disappeared: tuple[Disappeared, ...]
    coverage_gaps: tuple[CoverageGap, ...]
    ledger_ok: bool
    discovery_ok: bool

    def __post_init__(self) -> None:
        _check_fields(self)
        if any(c.source != self.snapshot.source for g in self.coverage_gaps for c in g.claims):
            raise RecordError("Baseline: a coverage gap of another source")
        if not (self.ledger_ok and self.discovery_ok):
            raise RecordError("Baseline: a baseline passed its ledger and discovery checks")


def build_snapshot(
    raw: RawPages,
    result: ParseResult,
    *,
    parser_version: str,
    registry_version: str,
    years: Sequence[int],
) -> Snapshot:
    """The snapshot of one run: a record per coverage entry, joined to its page by key."""
    fetched = {page.request.key: page for page in raw.pages}
    unfinished = {request.key: request for request in raw.unfinished}
    pages: list[PageRecord] = []
    for entry in result.coverage:
        page = fetched.get(entry.key)
        if page is not None:
            request, when, download = page.request, page.fetched_at, PageDownload.of(page.result)
        elif entry.key in unfinished:
            request, when, download = unfinished[entry.key], None, None
        else:
            raise RecordError(f"build_snapshot: coverage for {entry.key!r}, which is no page")
        pages.append(
            PageRecord(
                key=entry.key,
                scope=request.scope_name,
                year=entry.year,
                url=request.url,
                link=request.page_link,
                outcome=entry.outcome,
                unit_prefix=entry.unit_prefix,
                units_seen=entry.units_seen,
                revid=entry.revid,
                detail=entry.detail,
                fetched_at=when,
                download=download,
            )
        )
    moments = [p.fetched_at for p in pages if p.fetched_at is not None]
    return Snapshot(
        source=result.source,
        snapshot_id=snapshot_id(result.units, result.claims),
        fetched_at=min(moments) if moments else None,
        parser_version=parser_version,
        registry_version=registry_version,
        years=tuple(years),
        pages=tuple(pages),
        units=result.units,
        claims=result.claims,
        notes=result.notes,
    )


# --- JSON ----------------------------------------------------------------------------------


def _download_dict(d: PageDownload) -> dict[str, Any]:
    return {
        "outcome": d.outcome,
        "stage": d.stage,
        "http_status": d.http_status,
        "final_url": d.final_url,
        "content_type": d.content_type,
        "bytes": d.bytes,
        "elapsed_ms": d.elapsed_ms,
        "attempts": d.attempts,
        "error_type": d.error_type,
        "error": d.error,
        "api_code": d.api_code,
    }


def _page_dict(p: PageRecord) -> dict[str, Any]:
    return {
        "key": p.key,
        "scope": p.scope,
        "year": p.year,
        "url": p.url,
        "link": p.link,
        "outcome": p.outcome,
        "unit_prefix": p.unit_prefix,
        "units_seen": p.units_seen,
        "revid": p.revid,
        "detail": p.detail,
        "fetched_at": _utc_iso(p.fetched_at),
        "download": None if p.download is None else _download_dict(p.download),
    }


def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]:
    return {
        "source": snapshot.source,
        "snapshot_id": snapshot.snapshot_id,
        "fetched_at": _utc_iso(snapshot.fetched_at),
        "parser_version": snapshot.parser_version,
        "registry_version": snapshot.registry_version,
        "scope": {
            "years": list(snapshot.years),
            "pages": [_page_dict(p) for p in snapshot.pages],
        },
        "units": [u.to_dict() for u in snapshot.units],
        "claims": [c.to_dict() for c in snapshot.claims],
        "notes": [n.to_dict() for n in snapshot.notes],
    }


def baseline_to_dict(baseline: Baseline) -> dict[str, Any]:
    return {
        **snapshot_to_dict(baseline.snapshot),
        "units_seen_history": [
            {
                "scope": h.scope,
                "fetched_at": _utc_iso(h.fetched_at),
                "units_seen": h.units_seen,
                "claims": h.claims,
            }
            for h in baseline.history
        ],
        "disappeared": [
            {
                "source_event_id": d.source_event_id,
                "unit_id": d.unit_id,
                "text": d.text,
                "date_text": d.date_text,
                "start": d.start.isoformat(),
                "end": d.end.isoformat(),
                "link": d.link,
                "since": _utc_iso(d.since),
            }
            for d in baseline.disappeared
        ],
        "coverage_gaps": [
            {
                "scope": g.scope,
                "old_year": g.old_year,
                "new_year": g.new_year,
                "since": _utc_iso(g.since),
                "claims": [c.to_dict() for c in g.claims],
            }
            for g in baseline.coverage_gaps
        ],
        "checks": {"ledger": baseline.ledger_ok, "discovery": baseline.discovery_ok},
    }


class _Shape(Exception):
    """A saved file whose structure is not a baseline's."""


_TOP = (
    "source",
    "snapshot_id",
    "fetched_at",
    "parser_version",
    "registry_version",
    "scope",
    "units",
    "claims",
    "notes",
    "units_seen_history",
    "disappeared",
    "coverage_gaps",
    "checks",
)
_PAGE_KEYS = (
    "key",
    "scope",
    "year",
    "url",
    "link",
    "outcome",
    "unit_prefix",
    "units_seen",
    "revid",
    "detail",
    "fetched_at",
    "download",
)
_DOWNLOAD_KEYS = (
    "outcome",
    "stage",
    "http_status",
    "final_url",
    "content_type",
    "bytes",
    "elapsed_ms",
    "attempts",
    "error_type",
    "error",
    "api_code",
)
_HISTORY_KEYS = ("scope", "fetched_at", "units_seen", "claims")
_DISAPPEARED_KEYS = (
    "source_event_id",
    "unit_id",
    "text",
    "date_text",
    "start",
    "end",
    "link",
    "since",
)
_GAP_KEYS = ("scope", "old_year", "new_year", "since", "claims")


def _obj(value: Any, keys: Sequence[str], what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _Shape(f"{what} is not an object")
    if set(value) != set(keys):
        raise _Shape(f"{what} has the keys {sorted(value)}, not {sorted(keys)}")
    return value


def _list(value: Any, what: str) -> list[Any]:
    if not isinstance(value, list):
        raise _Shape(f"{what} is not a list")
    return value


def _records(value: Any, what: str, keys: Sequence[str] | None = None) -> list[dict[str, Any]]:
    items = _list(value, what)
    return [_obj(x, keys, what) if keys is not None else _plain(x, what) for x in items]


def _plain(value: Any, what: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _Shape(f"{what} holds a non-object")
    return value


def _page(data: dict[str, Any]) -> PageRecord:
    values = dict(data)
    download = values.pop("download")
    when = _iso_moment(values.pop("fetched_at"))
    if download is not None:
        download = PageDownload(**_obj(download, _DOWNLOAD_KEYS, "a page download"))
    return PageRecord(**values, fetched_at=when, download=download)


def _parse_baseline(data: Any) -> tuple[Baseline, ParseResult]:
    top = _obj(data, _TOP, "baseline.json")
    scope = _obj(top["scope"], ("years", "pages"), "scope")
    years = _list(scope["years"], "scope.years")
    page_data = _records(scope["pages"], "scope.pages", _PAGE_KEYS)
    unit_data = _records(top["units"], "units")
    claim_data = _records(top["claims"], "claims")
    note_data = _records(top["notes"], "notes")
    history_data = _records(top["units_seen_history"], "units_seen_history", _HISTORY_KEYS)
    gone_data = _records(top["disappeared"], "disappeared", _DISAPPEARED_KEYS)
    gap_data = _records(top["coverage_gaps"], "coverage_gaps", _GAP_KEYS)
    gap_claims = [_records(g["claims"], "a coverage gap's claims") for g in gap_data]
    checks = _obj(top["checks"], ("ledger", "discovery"), "checks")

    try:
        pages = tuple(_page(p) for p in page_data)
        units = tuple(InputUnit.from_dict(u) for u in unit_data)
        claims = tuple(Claim.from_dict(c) for c in claim_data)
        notes = tuple(Reason.from_dict(n) for n in note_data)
        snapshot = Snapshot(
            source=top["source"],
            snapshot_id=top["snapshot_id"],
            fetched_at=_iso_moment(top["fetched_at"]),
            parser_version=top["parser_version"],
            registry_version=top["registry_version"],
            years=tuple(years),
            pages=pages,
            units=units,
            claims=claims,
            notes=notes,
        )
        history = tuple(
            HistoryEntry(h["scope"], _need_moment(h["fetched_at"]), h["units_seen"], h["claims"])
            for h in history_data
        )
        gone = tuple(
            Disappeared(
                d["source_event_id"],
                d["unit_id"],
                d["text"],
                d["date_text"],
                _need_date(d["start"]),
                _need_date(d["end"]),
                d["link"],
                _need_moment(d["since"]),
            )
            for d in gone_data
        )
        gaps = tuple(
            CoverageGap(
                g["scope"],
                g["old_year"],
                g["new_year"],
                _need_moment(g["since"]),
                tuple(Claim.from_dict(c) for c in claims_of),
            )
            for g, claims_of in zip(gap_data, gap_claims, strict=True)
        )
        baseline = Baseline(snapshot, history, gone, gaps, checks["ledger"], checks["discovery"])
        coverage = _coverage(pages)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, RecordError):
            raise
        raise RecordError(str(exc)) from exc
    return baseline, ParseResult(snapshot.source, units, claims, coverage, notes)


def _coverage(pages: Iterable[PageRecord]) -> tuple[PageCoverage, ...]:
    """The pages as the adapter's coverage entries (what ``coverage_reasons`` reads)."""
    return tuple(
        PageCoverage(p.key, p.year, p.outcome, p.unit_prefix, p.units_seen, p.revid, p.detail)
        for p in pages
    )


def _need_moment(value: Any) -> datetime:
    moment = _iso_moment(value)
    if moment is None:
        raise RecordError("a timestamp is missing")
    return moment


def _need_date(value: Any) -> date:
    day = _iso_date(value)
    if day is None:
        raise RecordError("a date is missing")
    return day


def load_baseline(path: Path, *, source: str | None = None) -> Baseline | None:
    """The baseline in ``path``; None when there is no file.

    A file that cannot be trusted raises ``RecordError("baseline.json is corrupt: <problem>")``
    and is never read as empty (P94). With ``source``, a baseline of another source is corrupt
    too: it is never served as this one's (R2-01).
    """
    if not path.exists():
        return None

    def corrupt(problem: str) -> RecordError:
        return RecordError(f"baseline.json is corrupt: {problem}")

    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise corrupt(f"not JSON ({type(exc).__name__})") from exc
    try:
        baseline, result = _parse_baseline(data)
    except _Shape as exc:
        raise corrupt(f"shape: {exc}") from exc
    except RecordError as exc:
        raise corrupt(f"record: {exc}") from exc
    problems = record_problems(result)
    if problems:
        raise corrupt(f"ledger: {'; '.join(problems[:3])}")
    snapshot = baseline.snapshot
    prefixes = [p.unit_prefix for p in snapshot.pages if p.unit_prefix is not None]
    for unit in snapshot.units:
        if sum(unit.unit_id.startswith(prefix) for prefix in prefixes) != 1:
            raise corrupt(f"ledger: unit {unit.unit_id} is not on exactly one page")
    # What build_snapshot and the ledger guarantee, checked again: none of it is in snapshot_id,
    # so a hand edit would otherwise pass (fetched_at drives fallback_stale and data_as_of;
    # units_seen is the base of the sudden-drop check).
    moments = [p.fetched_at for p in snapshot.pages if p.fetched_at is not None]
    if snapshot.fetched_at != (min(moments) if moments else None):
        raise corrupt("record: Snapshot: fetched_at is not the earliest page fetched_at")
    for page in snapshot.pages:
        if page.outcome in _WITH_UNITS:
            if page.unit_prefix is None:
                continue
            have = sum(unit.unit_id.startswith(page.unit_prefix) for unit in snapshot.units)
        else:
            have = 0
        if page.units_seen != have:
            raise corrupt(
                f"ledger: page {page.key!r} reports units_seen {page.units_seen}, has {have}"
            )
    if source is not None and snapshot.source != source:
        raise corrupt(f"it is of {snapshot.source!r}, not {source!r}")
    return baseline


# --- the acceptance decision (spec §9.3) ---------------------------------------------------

FALLBACK_FRESH: Final = timedelta(days=7)
HISTORY_DAYS: Final = timedelta(days=30)
DISAPPEARED_DAYS: Final = timedelta(days=7)
_WITH_UNITS: Final = ("ok", "valid_empty")
_SERVES_THE_BASELINE: Final = ("quarantined", "fallback")
_REGISTRY_INFO: Final = "baseline.json is from another registry version; it is never served"
# What claim_content leaves out (P105): position, formatting and stamped provenance.
_NOT_CONTENT: Final = frozenset(
    ("unit_id", "claim_id", "link", "place_raw", "date_text", *STAMPED)
)


@dataclass(frozen=True, slots=True)
class ScopeCount:
    """One scope of a snapshot: units seen, usable claims, pages and the year they share."""

    units: int
    claims: int
    pages: int
    year: int | None
    all_valid_empty: bool


def _scopes(snapshot: Snapshot) -> dict[str, list[PageRecord]]:
    scopes: dict[str, list[PageRecord]] = {}
    for page in snapshot.pages:
        scopes.setdefault(page.scope, []).append(page)
    return scopes


def _prefixes(pages: Iterable[PageRecord]) -> tuple[str, ...]:
    return tuple(p.unit_prefix for p in pages if p.unit_prefix is not None)


def scope_counts(snapshot: Snapshot) -> dict[str, ScopeCount]:
    """Per scope, in first-page order (P90).

    A scope's claims are those whose ``unit_id`` starts with one of its pages' ``unit_prefix``.
    Its year is the year all its pages share; when they differ (a mix of None and a year
    included) it is None, and a None year never explains a drop or restarts a history.
    """
    counts: dict[str, ScopeCount] = {}
    for scope, pages in _scopes(snapshot).items():
        prefixes = _prefixes(pages)
        years = {p.year for p in pages}
        counts[scope] = ScopeCount(
            units=sum(p.units_seen for p in pages),
            claims=sum(c.unit_id.startswith(prefixes) for c in snapshot.claims),
            pages=len(pages),
            year=years.pop() if len(years) == 1 else None,
            all_valid_empty=all(p.outcome == "valid_empty" for p in pages),
        )
    return counts


def _year_change(old: ScopeCount | None, new: ScopeCount) -> tuple[int, int] | None:
    """``(old year, new year)`` when the scope is in both, both years are set and they differ."""
    if old is None or old.year is None or new.year is None or old.year == new.year:
        return None
    return old.year, new.year


def claim_content(claim: Claim) -> tuple[object, ...]:
    """What makes two claims equal (P105): every field in its declared order except the
    claim's position (``unit_id``, ``claim_id``), its formatting (``link``, ``place_raw``,
    ``date_text``) and its stamped provenance. ``jurisdiction`` and ``office_label`` are
    compared through ``norm_name``, ``previous_date_text`` through ``collapse_ws``.
    """
    content: list[object] = []
    for f in dataclasses.fields(claim):
        if f.name in _NOT_CONTENT:
            continue
        value = getattr(claim, f.name)
        if f.name in ("jurisdiction", "office_label"):
            value = norm_name(value or "")
        elif f.name == "previous_date_text" and value is not None:
            value = collapse_ws(value)
        content.append(value)
    return tuple(content)


def unchanged(claim: Claim, others: Sequence[Claim]) -> bool:
    """Some claim of ``others`` has the same ``claim_content``. A ``source_event_id`` or a key
    only finds a related claim; it never makes two claims equal (P105)."""
    return claim_content(claim) in {claim_content(o) for o in others}


def _listing_key(claim: Claim) -> tuple[object, ...]:
    return (
        claim.place_id,
        claim.institution or claim.office_class,
        norm_name(claim.jurisdiction or ""),
        claim.kind,
        claim.round,
    )


def same_listing(claim: Claim, others: Sequence[Claim]) -> bool:
    """Still listed (P91): a claim of ``others`` with this claim's ``source_event_id`` when it
    has one, else with its key (place, institution or office class, jurisdiction, kind, round).
    """
    if claim.source_event_id is not None:
        return any(o.source_event_id == claim.source_event_id for o in others)
    key = _listing_key(claim)
    return any(_listing_key(o) == key for o in others)


@dataclass(frozen=True, slots=True)
class Decision:
    """What one run of one source serves, and what ``baseline.json`` holds after it."""

    source: str
    candidate: Snapshot
    served: Snapshot | None
    acceptance: Acceptance
    claims: tuple[Claim, ...]  # the served claims stamped, then the provisional ones
    provisional: tuple[Claim, ...]  # the provisional ones alone (also in claims)
    provisional_units: tuple[InputUnit, ...]
    baseline: Baseline | None  # the input baseline unless the candidate was promoted
    disappeared: tuple[Disappeared, ...]  # in effect at now, by source_event_id
    coverage_gaps: tuple[CoverageGap, ...]  # in effect at now, by (scope, since)
    reasons: tuple[Reason, ...]
    health: SnapshotHealth


def _reason(code: ReasonCode, detail: str, **where: Any) -> Reason:
    return Reason(code, detail[:MAX_DETAIL], **where)


def _own_reasons(
    candidate: Snapshot,
    run_outcome: SourceOutcome,
    run_detail: str,
    ledger: LedgerReport | None,
    base: Snapshot | None,
) -> list[Reason]:
    """Rule 1: the run, the pages, the notes and the ledger, with P92 applied in place."""
    reasons: list[Reason] = []
    if run_outcome in ("deadline", "scrape_deadline"):
        reasons.append(_reason("deadline", run_detail or run_outcome))
    elif run_outcome == "worker_failed":
        reasons.append(_reason("worker_failed", run_detail))
    published = (
        set()
        if base is None
        else {p.year for p in base.pages if p.outcome in _WITH_UNITS and p.year is not None}
    )
    pages = _coverage(candidate.pages)
    if run_outcome == "worker_failed":  # P108: worker_failed covers the unfinished pages
        pages = tuple(p for p in pages if p.outcome != "unfinished")
    for reason in coverage_reasons(pages) + candidate.notes:
        if reason.code == "not_published_yet" and reason.year in published:
            reason = Reason(
                "required_year_missing",
                f"{reason.year} was published before and is now missing",
                page=reason.page,
                year=reason.year,
            )
        reasons.append(reason)
    if ledger is not None:
        reasons += ledger.reasons
    return reasons


def _major(version: str) -> str:
    return version.partition(".")[0]


def _fall(cand: ScopeCount, units: int, claims: int) -> tuple[str, int, int] | None:
    """``(what, reference, the candidate's number)`` when either number is under half."""
    if cand.units * 2 < units:
        return "units", units, cand.units
    if cand.claims * 2 < claims:
        return "claims", claims, cand.claims
    return None


@dataclass(slots=True)
class _Checks:
    reasons: list[Reason]
    unexplained: bool
    accepted: set[str]  # the scopes whose drop an accept_drop explained


def _drop_checks(
    source: str,
    cand_counts: dict[str, ScopeCount],
    base_counts: dict[str, ScopeCount],
    history: Sequence[HistoryEntry],
    acceptances: Sequence[DropAcceptance],
    now: datetime,
) -> _Checks:
    """Rule 5 (P90, P95): per scope in both, the drop or its explanation, then the page count."""
    checks = _Checks([], False, set())
    for scope, cand in cand_counts.items():
        base = base_counts.get(scope)
        if base is None:
            continue
        recent = [
            h for h in history if h.scope == scope and now - h.fetched_at <= HISTORY_DAYS
        ]
        code: ReasonCode = "sudden_drop"
        fall = _fall(cand, base.units, base.claims)
        if fall is None:
            code = "cumulative_drop"
            fall = _fall(
                cand,
                max((h.units_seen for h in recent), default=0),
                max((h.claims for h in recent), default=0),
            )
        if fall is not None:
            what, ref, n = fall
            fell = f"{scope}: {what} fell from {ref} to {n}"
            changed = _year_change(base, cand)
            accepted = next(
                (
                    a
                    for a in acceptances
                    if a.source == source
                    and a.reason == code
                    and a.page == scope
                    and a.year == cand.year
                    and cand.units >= a.units_seen_min
                    and cand.claims >= a.claims_min
                ),
                None,
            )
            explained: str | None = None
            if cand.all_valid_empty:
                explained = f"{fell}; the source lists none"
            elif changed is not None:
                explained = f"{fell}; the year changed from {changed[0]} to {changed[1]}"
            elif accepted is not None:
                explained = f"{fell}; accepted until {_utc_iso(accepted.until)}"
                checks.accepted.add(scope)
            if explained is not None:
                checks.reasons.append(
                    _reason("count_change", explained, page=scope, year=cand.year)
                )
            else:
                checks.unexplained = True
                counts = f"(candidate: units {cand.units}, claims {cand.claims})"
                high = f"{scope}: {what} fell to {n}, under half the 30-day high of {ref}"
                detail = f"{fell} {counts}" if code == "sudden_drop" else f"{high} {counts}"
                checks.reasons.append(_reason(code, detail, page=scope, year=cand.year))
        if base.pages != cand.pages:
            checks.reasons.append(
                _reason(
                    "count_change",
                    f"{scope}: {base.pages} pages, now {cand.pages}",
                    page=scope,
                    year=cand.year,
                )
            )
    return checks


def _gaps(
    promoting: bool,
    baseline: Baseline | None,
    candidate: Snapshot,
    cand_counts: dict[str, ScopeCount],
    base_counts: dict[str, ScopeCount],
    served_claims: Sequence[Claim],
    window: Window,
    now: datetime,
) -> tuple[CoverageGap, ...]:
    """Rule 6 (P91): the baseline's gaps cut to the claims still missing, then on a
    promotion the new gaps of each scope whose year changed; by (scope, since)."""
    if baseline is None:
        return ()
    kept: list[CoverageGap] = []
    for gap in baseline.coverage_gaps:
        rest = tuple(
            c
            for c in gap.claims
            if window.overlaps(c.span) and not same_listing(c, served_claims)
        )
        if rest:
            kept.append(dataclasses.replace(gap, claims=rest))
    new: list[CoverageGap] = []
    if promoting:
        scopes = _scopes(baseline.snapshot)
        for scope, cand in cand_counts.items():
            changed = _year_change(base_counts.get(scope), cand)
            if changed is None:
                continue
            prefixes = _prefixes(scopes[scope])
            lost = tuple(
                c
                for c in baseline.snapshot.claims
                if c.unit_id.startswith(prefixes)
                and window.overlaps(c.span)
                and not same_listing(c, candidate.claims)
            )
            if lost:
                new.append(CoverageGap(scope, changed[0], changed[1], now, lost))
    return tuple(sorted(kept + new, key=lambda g: (g.scope, g.since)))


def _disappeared(
    promoting: bool, baseline: Baseline | None, candidate: Snapshot, now: datetime
) -> tuple[Disappeared, ...]:
    """Rule 7: events no longer listed, found through ``source_event_id``; by that id.

    One record per id: the first claim in the baseline's order (two claims may share an id).
    """
    if baseline is None:
        return ()
    today = now.astimezone(UTC).date()

    def in_effect(d: Disappeared) -> bool:
        return now - d.since < DISAPPEARED_DAYS and d.end >= today

    if not promoting:
        shown: dict[str, Disappeared] = {}
        for d in baseline.disappeared:
            if in_effect(d):
                shown.setdefault(d.source_event_id, d)
        return tuple(sorted(shown.values(), key=lambda d: d.source_event_id))
    listed = {c.source_event_id for c in candidate.claims if c.source_event_id is not None}
    carried: dict[str, Disappeared] = {}
    for d in baseline.disappeared:
        if in_effect(d) and d.source_event_id not in listed:
            carried.setdefault(d.source_event_id, d)
    texts = {u.unit_id: u.text for u in baseline.snapshot.units}
    for c in baseline.snapshot.claims:
        start, end = c.span.start, c.span.end
        sei = c.source_event_id
        if sei is None or start is None or end is None:
            continue
        if end >= today and sei not in listed and sei not in carried:
            text = collapse_ws(texts.get(c.unit_id, ""))[:MAX_ATTENTION_TEXT]
            carried[sei] = Disappeared(sei, c.unit_id, text, c.date_text, start, end, c.link, now)
    return tuple(sorted(carried.values(), key=lambda d: d.source_event_id))


def _history(
    candidate: Snapshot,
    cand_counts: dict[str, ScopeCount],
    baseline: Baseline | None,
    comparable: bool,
    restarted: set[str],
    now: datetime,
) -> tuple[HistoryEntry, ...]:
    """Rule 8: the recent entries of scopes not restarted, then one per candidate scope."""
    kept = (
        [
            h
            for h in baseline.history
            if now - h.fetched_at <= HISTORY_DAYS and h.scope not in restarted
        ]
        if baseline is not None and comparable
        else []
    )
    when = candidate.fetched_at  # None when no page has a fetch time: scopes may exist, no entry
    new = (
        []
        if when is None
        else [HistoryEntry(scope, when, c.units, c.claims) for scope, c in cand_counts.items()]
    )
    return tuple(sorted(kept + new, key=lambda h: (h.scope, h.fetched_at)))


def _stamp(
    claims: Iterable[Claim], snapshot: Snapshot, *, fallback: bool, provisional: bool
) -> tuple[Claim, ...]:
    """R19: each claim gets the fetch time of its page and the snapshot's id.

    A claim on no page of the snapshot (only a hand-edited file has one) gets the snapshot's
    oldest fetch time, so it never looks fresher than it is.
    """
    pages = [(p.unit_prefix, p.fetched_at) for p in snapshot.pages if p.unit_prefix is not None]
    stamped: list[Claim] = []
    for c in claims:
        when = next((t for prefix, t in pages if c.unit_id.startswith(prefix)), None)
        stamped.append(
            dataclasses.replace(
                c,
                fetched_at=when or snapshot.fetched_at,
                fallback=fallback,
                snapshot_id=snapshot.snapshot_id,
                provisional=provisional,
            )
        )
    return tuple(stamped)


def _provisional(
    candidate: Snapshot, served: Snapshot, ledger: LedgerReport | None
) -> tuple[list[Claim], tuple[InputUnit, ...]]:
    """Rule 10 (P88, P105): what the fully parsed pages changed; none without a clean ledger."""
    if ledger is None or not ledger.ok:
        return [], ()
    prefixes = _prefixes(p for p in candidate.pages if p.outcome in _WITH_UNITS)
    seen = {claim_content(c) for c in served.claims}  # unchanged(c, served.claims), once
    claims = [
        c
        for c in candidate.claims
        if c.unit_id.startswith(prefixes) and claim_content(c) not in seen
    ]
    texts = {collapse_ws(u.text) for u in served.units}
    units = tuple(
        u
        for u in candidate.units
        if u.unit_id.startswith(prefixes)
        and u.outcome in ("partial", "unparsed")
        and u.relevance != "before_window"
        and collapse_ws(u.text) not in texts
    )
    return claims, units


def _unavailable(base: Snapshot | None, baseline_problem: str | None) -> str:
    if base is not None:
        return "baseline.json is from another registry version"
    return "no baseline" if baseline_problem is None else "baseline.json is corrupt"


def decide(
    candidate: Snapshot,
    *,
    run_outcome: SourceOutcome,
    run_detail: str,
    ledger: LedgerReport | None,
    baseline: Baseline | None,
    baseline_problem: str | None,
    acceptances: Sequence[DropAcceptance],
    window: Window,
    now: datetime,
) -> Decision:
    """Spec §9.3: promote, quarantine or fall back, and stamp what is served.

    ``ledger`` is None when parsing failed, and then ``run_outcome`` is ``worker_failed``
    (anything else is a ValueError); ``baseline_problem`` is ``load_baseline``'s
    message when the file was corrupt (``baseline`` is then None); ``acceptances`` are the
    ``accept_drop`` entries in effect, of any source. ``now`` is timezone-aware: nothing
    here reads the clock. Only a promotion gives a new baseline; otherwise
    ``Decision.baseline`` is the input baseline itself.
    """
    if now.utcoffset() is None:
        raise ValueError("decide: now must be timezone-aware")
    if ledger is None and run_outcome != "worker_failed":
        raise ValueError(f"decide: no ledger report for a run that is {run_outcome}")
    if baseline is not None and baseline.snapshot.source != candidate.source:
        raise ValueError(
            f"decide: the baseline is of {baseline.snapshot.source!r}, "
            f"the candidate of {candidate.source!r}"
        )
    base = None if baseline is None else baseline.snapshot
    own = _own_reasons(candidate, run_outcome, run_detail, ledger, base)
    valid = all(REASON_LEVEL[r.code] != "error" for r in own)
    head = list(own)
    if baseline_problem is not None:
        head.append(_reason("ledger_mismatch", baseline_problem))
    same_registry = base is not None and base.registry_version == candidate.registry_version
    comparable = base is not None and _major(base.parser_version) == _major(
        candidate.parser_version
    )
    servable = same_registry
    if base is not None and not same_registry:
        head.append(Reason("count_change", _REGISTRY_INFO))

    cand_counts = scope_counts(candidate)
    base_counts = {} if base is None else scope_counts(base)
    checks = _Checks([], False, set())
    if valid and comparable and baseline is not None:
        checks = _drop_checks(
            candidate.source, cand_counts, base_counts, baseline.history, acceptances, now
        )

    acceptance: Acceptance
    if not valid:
        acceptance = "fallback" if servable else "unavailable"
    elif not comparable:
        acceptance = "promoted"
    elif checks.unexplained:
        acceptance = "quarantined" if servable else "unavailable"
    else:
        acceptance = "promoted"
    promoting = acceptance == "promoted"
    served = candidate if promoting else base if acceptance in _SERVES_THE_BASELINE else None

    served_claims = () if served is None else served.claims
    gaps = _gaps(
        promoting, baseline, candidate, cand_counts, base_counts, served_claims, window, now
    )
    gone = _disappeared(promoting, baseline, candidate, now)
    stamped: tuple[Claim, ...] = ()
    provisional: tuple[Claim, ...] = ()
    provisional_units: tuple[InputUnit, ...] = ()
    if served is not None:
        stamped = _stamp(
            served.claims,
            served,
            fallback=acceptance in ("quarantined", "fallback"),
            provisional=False,
        )
        if acceptance in _SERVES_THE_BASELINE:
            changed, provisional_units = _provisional(candidate, served, ledger)
            provisional = _stamp(changed, candidate, fallback=False, provisional=True)

    tail = [
        _reason(
            "coverage_gap",
            f"{g.scope}: the {g.old_year} list was replaced by {g.new_year}; "
            f"in-window claims no longer listed: {len(g.claims)}",
            page=g.scope,
            year=g.new_year,
            since=g.since,
        )
        for g in gaps
    ]
    if acceptance == "unavailable":
        tail.append(Reason("unavailable", _unavailable(base, baseline_problem)))
    if (
        acceptance in _SERVES_THE_BASELINE
        and served is not None
        and served.fetched_at is not None
        and now - served.fetched_at > FALLBACK_FRESH
    ):
        tail.append(Reason("fallback_stale", f"serving data fetched {_utc_iso(served.fetched_at)}"))
    if len(provisional) > 0:
        tail.append(
            Reason(
                "provisional_changes",
                f"new or changed claims from an incomplete fetch: {len(provisional)}",
            )
        )
    if gone:
        tail.append(Reason("units_disappeared", f"listed events no longer listed: {len(gone)}"))

    restarted = (
        set(checks.accepted)
        | {s for s, c in cand_counts.items() if c.all_valid_empty}
        | {s for s, c in cand_counts.items() if _year_change(base_counts.get(s), c)}
    )
    kept_or_new = (
        Baseline(
            candidate,
            _history(candidate, cand_counts, baseline, comparable, restarted, now),
            gone,
            gaps,
            True,
            True,
        )
        if acceptance == "promoted"
        else baseline
    )
    return Decision(
        source=candidate.source,
        candidate=candidate,
        served=served,
        acceptance=acceptance,
        claims=stamped + provisional,
        provisional=provisional,
        provisional_units=provisional_units,
        baseline=kept_or_new,
        disappeared=gone,
        coverage_gaps=gaps,
        reasons=(*head, *checks.reasons, *tail),
        health=SnapshotHealth(
            acceptance=acceptance,
            using_fallback=acceptance in _SERVES_THE_BASELINE,
            served_snapshot_id=None if served is None else served.snapshot_id,
            served_fetched_at=None if served is None else served.fetched_at,
            baseline_units_seen=None if base is None else sum(p.units_seen for p in base.pages),
            comparable=comparable,
        ),
    )


# ------------------------------------------------------------ unit attention items (P87, P88)


def _page_of(snapshot: Snapshot, unit_id: str) -> PageRecord | None:
    """The page whose ``unit_prefix`` starts the unit id (the longest, when several do)."""
    owners = [p for p in snapshot.pages if p.unit_prefix and unit_id.startswith(p.unit_prefix)]
    return max(owners, key=lambda p: len(p.unit_prefix or ""), default=None)


def _unit_item(
    kind: AttentionKind,
    snapshot: Snapshot,
    unit: InputUnit,
    source: str,
    prefix: str,
) -> AttentionItem:
    page = _page_of(snapshot, unit.unit_id)
    claims = [c for c in snapshot.claims if c.unit_id == unit.unit_id]
    starts = [c.span.start for c in claims if c.span.start is not None]  # a year claim has none
    # An orphan unit (only a hand-edited baseline.json has one) keeps its item and a fallback link.
    if claims:
        link = claims[0].link
    elif page is not None:
        link = page.link
    else:
        link = snapshot.pages[0].link if snapshot.pages else ""
    full = collapse_ws(unit.text)
    return AttentionItem(
        item_id=short_id([kind, unit.unit_id]),
        kind=kind,
        source=source,
        link=link,
        snapshot_id=snapshot.snapshot_id,
        relevance=unit.relevance,
        text=(prefix + full)[:MAX_ATTENTION_TEXT],
        reason=unit.reason or unit.outcome,
        possible_matches=(),
        merge_ids=(),
        undated_id=None,
        date=min(starts, default=None),
        unit_id=unit.unit_id,
        unit_text=full if kind in ("partial_unit", "unparsed_unit") else None,
    )


def _relevant_units(snapshot: Snapshot) -> tuple[InputUnit, ...]:
    """The partial and unparsed units that count: the ones not before the window."""
    return tuple(
        u
        for u in snapshot.units
        if u.outcome in ("partial", "unparsed") and u.relevance != "before_window"
    )


_UNIT_OUTCOME: Final = {"unparsed_relevant": "unparsed", "partial_relevant": "partial"}


def _unit_keys(snapshot: Snapshot, outcome: str) -> Counter[tuple[str | None, str, str]]:
    """How often each unit key (page scope, outcome, text) occurs among the relevant units."""
    keys: Counter[tuple[str | None, str, str]] = Counter()
    for unit in _relevant_units(snapshot):
        if unit.outcome == outcome:
            page = _page_of(snapshot, unit.unit_id)
            keys[(None if page is None else page.scope, unit.outcome, collapse_ws(unit.text))] += 1
    return keys


def known_unit_reasons(
    reasons: Sequence[Reason], served: Snapshot | None, baseline: Snapshot | None
) -> tuple[Reason, ...]:
    """The unit reasons whose every unit the baseline already had (P149), in the given order.

    One source's two snapshots. A unit's key is its page's scope, its outcome and its text with
    whitespace collapsed; the page's year and the row's position are not in it. A reason is
    known when each key of the served snapshot occurs in the baseline at least as often. Any
    other reason is never known.
    """
    if served is None or baseline is None or baseline.source != served.source:
        return ()
    known: list[Reason] = []
    for reason in reasons:
        outcome = _UNIT_OUTCOME.get(reason.code)
        if outcome is None:
            continue
        now = _unit_keys(served, outcome)
        before = _unit_keys(baseline, outcome)
        if now and all(before[k] >= n for k, n in now.items()):
            known.append(reason)
    return tuple(known)


def unit_items(decision: Decision) -> tuple[AttentionItem, ...]:
    """The attention items about single units (P88); sorted by ``item_id``.

    Partial and unparsed relevant units of the served snapshot, the same of a non-promoted
    candidate's fully parsed pages (``provisional_change``), and each disappeared event.
    ``()`` when nothing is served.
    """
    served = decision.served
    if served is None:
        return ()
    items: list[AttentionItem] = []
    for unit in _relevant_units(served):
        kind: AttentionKind = "partial_unit" if unit.outcome == "partial" else "unparsed_unit"
        items.append(_unit_item(kind, served, unit, decision.source, ""))
    cand = decision.candidate
    for unit in decision.provisional_units:
        items.append(
            _unit_item(
                "provisional_change", cand, unit, decision.source, "From an incomplete fetch: "
            )
        )
    name = SOURCE_NAMES[decision.source]
    for gone in decision.disappeared:
        text = f"No longer listed by {name}: {gone.text}, was {gone.date_text}"
        items.append(
            AttentionItem(
                item_id=short_id(["disappeared_unit", gone.source_event_id]),
                kind="disappeared_unit",
                source=decision.source,
                link=gone.link,
                snapshot_id=served.snapshot_id,
                relevance="in_or_after_window",
                text=text[:MAX_ATTENTION_TEXT],
                reason="disappeared",
                possible_matches=(),
                merge_ids=(),
                undated_id=None,
                date=gone.start,
                unit_id=gone.unit_id,
            )
        )
    return tuple(sorted(items, key=lambda i: i.item_id))
