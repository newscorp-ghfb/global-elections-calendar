"""Snapshot records and their loaders (spec §5.10, §9.3; P91, P93, P94).

A snapshot is what one source gave in one run: its pages, units, claims and notes, stored
unstamped. A baseline is the snapshot a run last accepted, with the history the drop checks
need. ``load_baseline`` treats a file it cannot trust as corrupt, never as empty (P94).
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Final

from elections_calendar.fetch import FetchResult, redact_text, redact_url
from elections_calendar.ledger import record_problems
from elections_calendar.model import (
    Claim,
    FetchOutcome,
    InputUnit,
    Reason,
    RecordError,
    _check_fields,
    _iso_date,
    _iso_moment,
    _utc_iso,
    canonical_json,
)
from elections_calendar.offices import DEFAULT_INSTITUTIONS
from elections_calendar.places import DEFAULT_PLACES, DEFAULT_SUBDIVISIONS
from elections_calendar.sources.base import PageCoverage, PageOutcome, ParseResult, RawPages

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
        coverage = tuple(
            PageCoverage(
                p.key, p.year, p.outcome, p.unit_prefix, p.units_seen, p.revid, p.detail
            )
            for p in pages
        )
    except (TypeError, ValueError) as exc:
        if isinstance(exc, RecordError):
            raise
        raise RecordError(str(exc)) from exc
    return baseline, ParseResult(snapshot.source, units, claims, coverage, notes)


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


def load_baseline(path: Path) -> Baseline | None:
    """The baseline in ``path``; None when there is no file.

    A file that cannot be trusted raises ``RecordError("baseline.json is corrupt: <problem>")``
    and is never read as empty (P94).
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
    return baseline
