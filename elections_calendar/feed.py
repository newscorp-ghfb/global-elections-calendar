"""The feed's per-source health entries (spec §5.6; P96; R11, R15).

``SourceResult`` is one source's run as the pipeline assembles it; ``source_health_entry`` turns
it into the JSON object of ``source_health[]``. Every text in an entry was capped and redacted
upstream, except a run's detail, which is redacted and cut here. Nothing here reads the clock.
"""

from dataclasses import dataclass
from typing import Any, Final, Literal, cast

from elections_calendar.fetch import redact_text
from elections_calendar.health import Acknowledgement, MatchDiagnostic, Severity
from elections_calendar.ledger import LedgerReport
from elections_calendar.model import (
    REASON_LEVEL,
    REASON_STAGE,
    SOURCE_NAMES,
    AttentionItem,
    Reason,
    _utc_iso,
)
from elections_calendar.runner import SourceRun
from elections_calendar.snapshots import MAX_DIAGNOSTIC, Decision, PageRecord
from elections_calendar.sources.base import PAGE_REASONS
from elections_calendar.text import collapse_ws

DownloadOutcome = Literal[
    "ok",
    "http_error",
    "timeout",
    "tls_error",
    "dns_error",
    "challenge_page",
    "api_error",
    "layout_not_recognised",
    "not_published_yet",
    "deadline",
    "fetch_failed",
    "worker_failed",
]  # §5.6 plus P96
MAX_SAMPLES: Final = 5
MAX_SAMPLE_TEXT: Final = 200

_WITH_UNITS: Final = ("ok", "valid_empty")
_RELEVANCE: Final = ("in_or_after_window", "unknown", "before_window")
_RUN_DEADLINES: Final = ("deadline", "scrape_deadline")


@dataclass(frozen=True, slots=True)
class SourceResult:
    """One source's run, as the pipeline assembled it."""

    source: str
    run: SourceRun
    parse_ms: int
    ledger: LedgerReport | None  # None when parsing failed
    decision: Decision
    items: tuple[AttentionItem, ...]  # unit_items(decision)
    match: MatchDiagnostic
    reasons: tuple[Reason, ...]  # source_reasons(...)
    acknowledged: tuple[Acknowledgement, ...]
    severity: Severity


def reason_dict(reason: Reason) -> dict[str, Any]:
    return {
        "code": reason.code,
        "level": REASON_LEVEL[reason.code],
        "stage": REASON_STAGE[reason.code],
        "year": reason.year,
        "page": reason.page,
        "text": reason.detail or reason.code,
    }


def _fetch_failure(page: PageRecord) -> DownloadOutcome | None:
    """The download outcome of a page that failed to download, else None."""
    code = PAGE_REASONS.get(page.outcome)
    if code is not None and REASON_STAGE[code] == "fetch":
        return cast(DownloadOutcome, code)
    return None


def _download(result: SourceResult) -> dict[str, Any]:
    pages = result.decision.candidate.pages
    run = result.run
    outcome: DownloadOutcome = "ok"
    given: PageRecord | None = None
    if run.outcome in _RUN_DEADLINES:
        outcome = "deadline"
    elif run.outcome == "worker_failed":
        outcome = "worker_failed"
    else:
        failed = next((p for p in pages if _fetch_failure(p) is not None), None)
        layout = next((p for p in pages if p.outcome == "layout_not_recognised"), None)
        unpublished = next((p for p in pages if p.outcome == "not_published_yet"), None)
        if failed is not None:
            outcome, given = cast(DownloadOutcome, _fetch_failure(failed)), failed
        elif layout is not None:
            outcome, given = "layout_not_recognised", layout
        elif unpublished is not None:
            outcome, given = "not_published_yet", unpublished
        elif any(r.code == "not_published_yet" for r in result.reasons):
            outcome = "not_published_yet"
    downloads = [p.download for p in pages if p.download is not None]
    rep = given if given is not None else next((p for p in pages if p.download is not None), None)
    shown = None if rep is None else rep.download
    error = None if shown is None else shown.error
    if error is None and outcome in ("deadline", "worker_failed"):
        error = collapse_ws(redact_text(run.detail))[:MAX_DIAGNOSTIC] or None
    stop = (
        "pagination_incomplete"
        if any(r.code == "pagination_incomplete" for r in result.reasons)
        else run.outcome
    )
    return {
        "outcome": outcome,
        "stage": None if shown is None else shown.stage,
        "http_status": None if shown is None else shown.http_status,
        "final_url": None if shown is None else shown.final_url,
        "content_type": None if shown is None else shown.content_type,
        "bytes": sum(d.bytes for d in downloads),
        "elapsed_ms": sum(d.elapsed_ms for d in downloads),
        "attempts": sum(d.attempts for d in downloads),
        "error": error,
        "pages": {
            "requested": len(pages),
            "ok": sum(p.outcome in _WITH_UNITS for p in pages),
            "failed": sum(p.outcome not in (*_WITH_UNITS, "not_published_yet") for p in pages),
            "stop_reason": stop,
        },
    }


def _parse(result: SourceResult) -> dict[str, Any]:
    candidate = result.decision.candidate
    report = result.ledger
    outcomes = {} if report is None else report.outcomes
    samples = [
        collapse_ws(u.text)[:MAX_SAMPLE_TEXT]
        for u in candidate.units
        if u.outcome == "unparsed" and u.relevance != "before_window"
    ][:MAX_SAMPLES]
    return {
        "parser_version": candidate.parser_version,
        "parse_ms": result.parse_ms,
        "units": {
            "seen": 0 if report is None else report.units_seen,
            "parsed": outcomes.get("parsed", 0),
            "partial": outcomes.get("partial", 0),
            "unparsed": outcomes.get("unparsed", 0),
            "ignored": outcomes.get("ignored", 0),
        },
        "claims": len(candidate.claims),
        "ignored_reasons": {}
        if report is None
        else dict(sorted(report.ignored_reasons.items())),
        "relevance": {k: 0 if report is None else report.relevance.get(k, 0) for k in _RELEVANCE},
        "unparsed_samples": samples,
    }


def _per_year(pages: tuple[PageRecord, ...]) -> dict[str, Any]:
    years = sorted({p.year for p in pages if p.year is not None})
    out: dict[str, Any] = {}
    for year in (*years, None):
        group = [p for p in pages if p.year == year]
        if not group:
            continue
        other = next((p.outcome for p in group if p.outcome not in _WITH_UNITS), "ok")
        out["all" if year is None else str(year)] = {
            "requested": len(group),
            "units_seen": sum(p.units_seen for p in group),
            "outcome": other,
        }
    return out


def source_health_entry(result: SourceResult) -> dict[str, Any]:
    """The ``source_health[]`` entry of one source (§5.6)."""
    health = result.decision.health
    match = result.match
    return {
        "source": result.source,
        "name": SOURCE_NAMES[result.source],
        "download": _download(result),
        "parse": _parse(result),
        "coverage": {"per_year": _per_year(result.decision.candidate.pages)},
        "snapshot": {
            "acceptance": health.acceptance,
            "using_fallback": health.using_fallback,
            "served_snapshot_id": health.served_snapshot_id,
            "served_fetched_at": _utc_iso(health.served_fetched_at),
            "baseline_units_seen": health.baseline_units_seen,
            "comparable": health.comparable,
        },
        "match": {
            "eligible": match.eligible,
            "peers_fresh": match.peers_fresh,
            "matched": match.matched,
            "unmatched": match.unmatched,
            "informative": match.informative,
        },
        "severity": result.severity,
        "reasons": [reason_dict(r) for r in result.reasons],
        "acknowledged": [
            {
                "code": a.code,
                "until": _utc_iso(a.until),
                "stage": a.stage,
                "year": a.year,
                "page": a.page,
            }
            for a in result.acknowledged
        ],
    }
