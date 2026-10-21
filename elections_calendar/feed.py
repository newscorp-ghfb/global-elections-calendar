"""The feed document and its per-source health entries (spec §5.6, §5.7; P84-P87, P96; R11, R15).

``build_feed`` assembles the document from the merge result and the sources' runs: the months, the
undated listings and the attention items capped at ``MAX_FEED_ITEMS``. It also returns the full
attention list (``attention_full``) and the ``dispositions`` as audit parts beside the feed. A
source given twice or outside ``SOURCE_ORDER`` raises, so none is dropped silently.

``SourceResult`` is one source's run as the pipeline assembles it; ``source_health_entry`` turns
it into the JSON object of ``source_health[]``. Every text in an entry was capped and redacted
upstream, except a run's detail, which is redacted and cut here. Nothing here reads the clock:
``build_feed`` uses only the ``now`` it is given.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal, cast

from elections_calendar.fetch import redact_text
from elections_calendar.health import Acknowledgement, MatchDiagnostic, Severity, severity
from elections_calendar.ledger import LedgerReport
from elections_calendar.model import (
    REASON_LEVEL,
    REASON_STAGE,
    SOURCE_NAMES,
    SOURCE_ORDER,
    AttentionItem,
    BibEntry,
    Card,
    Child,
    ChildSource,
    MergeResult,
    Reason,
    UndatedListing,
    _utc_iso,
)
from elections_calendar.runner import SourceRun
from elections_calendar.snapshots import MAX_DIAGNOSTIC, Decision, PageRecord
from elections_calendar.sources.base import PAGE_REASONS, PARSER_VERSION
from elections_calendar.text import collapse_ws
from elections_calendar.window import Window

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
MAX_FEED_ITEMS: Final = 500

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


# --- the feed document (spec §5.3-§5.5, §5.7; P84-P87) --------------------------------------


@dataclass(frozen=True, slots=True)
class RunInfo:
    """What the environment says about the run."""

    code_sha: str  # 40 hex characters, or "local"
    trust_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FeedParts:
    """The feed document and the two audit files that go beside it."""

    doc: dict[str, Any]  # elections.json, with content_id and published_at None
    attention_full: dict[str, Any]  # {"items": [...]}: every item, uncapped
    dispositions: dict[str, Any]  # {"dispositions": [...]}: every disposition
    run_reasons: tuple[Reason, ...]  # the given ones, then attention_truncated
    severity: Severity  # the run's


_RELEVANCE_RANK: Final = {"in_or_after_window": 0, "unknown": 1}
_SEVERITY_RANK: Final = {"ok": 0, "warning": 1, "error": 2}


def _iso(value: Any) -> str | None:
    return None if value is None else cast(str, value.isoformat())


def _bib(entry: BibEntry) -> dict[str, Any]:
    return {"name": SOURCE_NAMES[entry.source], "link": entry.link}


def _kept(matches: Sequence[str], in_feed: frozenset[str]) -> tuple[list[str], int]:
    """The possible matches that are in the feed, and the number of distinct ones left out."""
    return [m for m in matches if m in in_feed], len(set(matches) - in_feed)


def _child_source(source: ChildSource) -> dict[str, Any]:
    claim = source.claim
    return {
        "name": SOURCE_NAMES[claim.source],
        "link": claim.link,
        "source_event_id": claim.source_event_id,
        "date": _iso(claim.span.start),
        "end_date": _iso(claim.span.end),
        "date_precision": claim.span.precision,
        "date_text": claim.date_text,
        "date_meaning": claim.date_meaning,
        "date_status": claim.date_status,
        "status_claim": claim.status_claim,
        "fetched_at": _utc_iso(claim.fetched_at),
        "fallback": claim.fallback,
        "provisional": claim.provisional,
        "evidence_kind": claim.evidence_kind,
        "selected": source.selected,
        "rejected_reason": source.rejected_reason,
    }


def _child(child: Child, in_feed: frozenset[str]) -> dict[str, Any]:
    kept, outside = _kept(child.possible_matches, in_feed)
    return {
        "child_id": child.child_id,
        "jurisdiction": child.jurisdiction,
        "jurisdiction_kind": child.jurisdiction_kind,
        "institution": child.institution,
        "office_class": child.office_class,
        "office_label": child.office_label,
        "kind": child.kind,
        "round": child.round,
        "indirect": child.indirect,
        "aggregate": child.aggregate,
        "occurrence_confirmed": child.occurrence_confirmed,
        "status_conflict": child.status_conflict,
        "date_conflict": child.date_conflict,
        "unverified": child.unverified,
        "ambiguous": child.ambiguous,
        "rescheduled_from": list(child.rescheduled_from),
        "provisional_date": child.provisional_date,
        "possible_matches": kept,
        "possible_matches_outside": outside,
        "sources": [_child_source(s) for s in child.sources],
    }


def _card(
    card: Card, in_feed: frozenset[str], umbrella_targets: dict[str, set[str]]
) -> dict[str, Any]:
    mine = {c.child_id for c in card.children}
    umbrellas = [
        {
            "name": SOURCE_NAMES[u.source],
            "link": u.link,
            "office_label": u.office_label,
            "date_text": u.date_text,
            "children": sorted(mine & umbrella_targets.get(u.merge_id, set())),
        }
        for u in card.umbrellas
    ]
    return {
        "date": _iso(card.span.start),
        "country": card.country,
        "type": card.type,
        "status": card.status,
        "sources": [_bib(b) for b in card.sources],
        "source_names": [SOURCE_NAMES[b.source] for b in card.sources],
        "links": [b.link for b in card.sources],
        "group_id": card.group_id,
        "end_date": _iso(card.span.end),
        "date_precision": card.span.precision,
        "date_meaning": card.date_meaning,
        "date_status": card.date_status,
        "level": card.level,
        "place_id": card.place_id,
        "country_code": card.country_code,
        "children": [_child(c, in_feed) for c in card.children],
        "umbrella_sources": [_bib(b) for b in card.umbrella_sources],
        "umbrellas": umbrellas,
    }


def _listing(listing: UndatedListing, in_feed: frozenset[str]) -> dict[str, Any]:
    kept, outside = _kept(listing.possible_matches, in_feed)
    return {
        "undated_id": listing.undated_id,
        "place_id": listing.place_id,
        "country": listing.country,
        "office_label": listing.office_label,
        "year": listing.year,
        "sources": [_bib(b) for b in listing.sources],
        "possible_matches": kept,
        "possible_matches_outside": outside,
    }


def _item(item: AttentionItem, in_feed: frozenset[str], *, full: bool) -> dict[str, Any]:
    kept, outside = _kept(item.possible_matches, in_feed)
    out: dict[str, Any] = {
        "item_id": item.item_id,
        "kind": item.kind,
        "source": item.source,
        "link": item.link,
        "snapshot_id": item.snapshot_id,
        "relevance": item.relevance,
        "date": _iso(item.date),
        "text": item.text,
        "reason": item.reason,
        "possible_matches": list(item.possible_matches) if full else kept,
        "possible_matches_outside": outside,
        "undated_id": item.undated_id,
    }
    if full:
        out["merge_ids"] = list(item.merge_ids)
        out["unit_id"] = item.unit_id
        out["unit_text"] = item.unit_text
    return out


def _cap_key(item: AttentionItem) -> tuple[int, bool, str, str]:
    """P87: relevance, then date (None last), then item id."""
    return (
        _RELEVANCE_RANK[item.relevance],
        item.date is None,
        "" if item.date is None else item.date.isoformat(),
        item.item_id,
    )


def _errors(sources: Sequence[SourceResult], run_reasons: Sequence[Reason]) -> list[str]:
    groups = [(SOURCE_NAMES[s.source], s.reasons) for s in sources]
    groups.append(("Run", tuple(run_reasons)))
    return [
        f"{name}: {r.code}: {r.detail}" if r.detail else f"{name}: {r.code}"
        for name, reasons in groups
        for r in reasons
        if REASON_LEVEL[r.code] != "info"
    ]


def build_feed(
    result: MergeResult,
    sources: Sequence[SourceResult],
    *,
    window: Window,
    now: datetime,
    run: RunInfo,
    run_reasons: Sequence[Reason],
) -> FeedParts:
    """The feed document, the full attention list and the dispositions (§5.7; P84-P87)."""
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    by_source: dict[str, SourceResult] = {}
    for s in sources:
        if s.source not in SOURCE_ORDER:
            raise ValueError(f"unknown source: {s.source}")
        if s.source in by_source:
            raise ValueError(f"a source appears twice: {s.source}")
        by_source[s.source] = s
    ordered = [by_source[k] for k in SOURCE_ORDER if k in by_source]
    in_window = [c for c in result.cards if window.bucket(c.span) is not None]
    in_feed = frozenset(ch.child_id for c in in_window for ch in c.children)
    umbrella_targets: dict[str, set[str]] = {}
    for d in result.dispositions:
        if d.kind == "umbrella_link":
            umbrella_targets.setdefault(d.merge_id, set()).update(d.targets)

    all_items = sorted([*result.attention, *(i for s in ordered for i in s.items)],
                       key=lambda i: i.item_id)
    relevant = sorted((i for i in all_items if i.relevance != "before_window"), key=_cap_key)
    capped = relevant[:MAX_FEED_ITEMS]
    truncated = len(relevant) - len(capped)
    reasons = tuple(run_reasons)
    if truncated:
        reasons += (
            Reason("attention_truncated", f"attention items left out of the feed: {truncated}"),
        )
    kept_undated = {i.undated_id for i in capped if i.undated_id is not None}
    listings = sorted(
        (u for u in result.undated if u.undated_id in kept_undated), key=lambda u: u.undated_id
    )

    months: dict[str, list[dict[str, Any]]] = {k: [] for k in window.month_keys}
    for card in in_window:
        bucket = window.bucket(card.span)
        if bucket is not None:
            months[bucket].append(_card(card, in_feed, umbrella_targets))

    served = [
        s.decision.health.served_fetched_at
        for s in ordered
        if s.decision.health.served_fetched_at is not None
    ]
    worst = max([severity(reasons), *(s.severity for s in ordered)], key=_SEVERITY_RANK.__getitem__)
    doc: dict[str, Any] = {
        "schema_version": 2,
        "content_id": None,
        "generated_at": _utc_iso(now),
        "published_at": None,
        "data_as_of": _utc_iso(min(served)) if served else None,
        "current_month": window.current_month,
        "window": {"months": list(window.month_keys), "years": list(window.years)},
        "months": months,
        "undated": [_listing(u, in_feed) for u in listings],
        "attention_items": [_item(i, in_feed, full=False) for i in capped],
        "attention_truncated": truncated,
        "source_health": [source_health_entry(s) for s in ordered],
        "run": {
            "parser_version": PARSER_VERSION,
            "code_sha": run.code_sha,
            "trust_sources": list(run.trust_sources),
            "merge_checks": {"conservation": "ok"},
            "severity": worst,
            "reasons": [reason_dict(r) for r in reasons],
        },
        "errors": _errors(ordered, reasons),
    }
    return FeedParts(
        doc=doc,
        attention_full={"items": [_item(i, in_feed, full=True) for i in all_items]},
        dispositions={
            "dispositions": [
                {"merge_id": d.merge_id, "kind": d.kind, "targets": list(d.targets)}
                for d in result.dispositions
            ]
        },
        run_reasons=reasons,
        severity=worst,
    )
