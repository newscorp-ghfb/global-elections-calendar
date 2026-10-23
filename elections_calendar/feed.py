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

import hashlib
import json
import re
import string
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal, cast

from elections_calendar.fetch import redact_text
from elections_calendar.health import (
    DROP_REASONS,
    UNIT_REASONS,
    Acknowledgement,
    Entry,
    MatchDiagnostic,
    Severity,
    Verdict,
    severity,
    unacknowledged,
)
from elections_calendar.ledger import LedgerReport
from elections_calendar.model import (
    NEVER_ACKNOWLEDGEABLE,
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
        "acknowledged": [_acknowledged_dict(a) for a in result.acknowledged],
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


def _acknowledged_dict(a: Acknowledgement) -> dict[str, Any]:
    """One acknowledgement as ``feed`` and ``status.json`` both list it (without its source)."""
    return {
        "code": a.code,
        "until": _utc_iso(a.until),
        "stage": a.stage,
        "year": a.year,
        "page": a.page,
    }


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
    ordered = _in_order(sources)
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


# --- status.json and HEALTH.md (spec §5.8, §11.6; P96, P104; S4-T19, NM-T04) -------------------

AttemptOutcome = Literal["published", "validation_failed"]  # Plan 5 adds the other three
_RUN_ID: Final = re.compile(r"[0-9]+")
_TRIGGER: Final = re.compile(r"[a-z_]+")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_STAMP: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z)?"
)
_TIMESTAMP: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")
_DIGEST: Final = re.compile(r"[0-9a-f]{64}")
_ESCAPES: Final = str.maketrans({c: "\\" + c for c in string.punctuation})
_UNIT_HINT: Final = "acknowledge each unit by its full text (unit_text in attention_full.json)"
_DROP_HINT: Final = "to accept the drop: accept_drop with this scope and the candidate's counts"


@dataclass(frozen=True, slots=True)
class Attempt:
    """Who ran, when and from which code: the run identity of ``status.json``."""

    attempt_at: datetime
    run_id: str  # GITHUB_RUN_ID when it is all digits, else "local"
    trigger: str  # GITHUB_EVENT_NAME when it matches [a-z_]+, else "local"
    code_sha: str  # GITHUB_SHA when it is 40 lowercase hex characters, else "local"

    def __post_init__(self) -> None:
        if self.attempt_at.utcoffset() is None:
            raise ValueError("attempt_at must be timezone-aware")

    @property
    def attempt_id(self) -> str:
        return f"{self.attempt_at.astimezone(UTC):%Y%m%dT%H%M%SZ}-{self.run_id}"


def _env(environ: Mapping[str, str], name: str, pattern: re.Pattern[str]) -> str:
    value = environ.get(name, "")
    return value if pattern.fullmatch(value) else "local"


def attempt_of(environ: Mapping[str, str], now: datetime) -> Attempt:
    """The attempt of this run; an environment value of the wrong shape counts as absent."""
    return Attempt(
        attempt_at=now,
        run_id=_env(environ, "GITHUB_RUN_ID", _RUN_ID),
        trigger=_env(environ, "GITHUB_EVENT_NAME", _TRIGGER),
        code_sha=_env(environ, "GITHUB_SHA", _CODE_SHA),
    )


def _real_timestamp(value: str) -> bool:
    """Whether ``value`` is a whole status-v1 timestamp that names a real moment."""
    if not _TIMESTAMP.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _serving_fields(serving: bytes | None) -> dict[str, str | None]:
    """The four ``serving_*`` fields of the bytes the repository serves (NM-T04)."""
    fields: dict[str, str | None] = {
        "serving_feed_sha256": None,
        "serving_published_at": None,
        "serving_generated_at": None,
        "serving_content_id": None,
    }
    if serving is None:
        return fields
    fields["serving_feed_sha256"] = hashlib.sha256(serving).hexdigest()
    try:
        loaded = json.loads(serving)
    except (ValueError, RecursionError):
        return fields
    if isinstance(loaded, dict):
        for field, key, valid in (
            ("serving_published_at", "published_at", _real_timestamp),
            ("serving_generated_at", "generated_at", _real_timestamp),
            ("serving_content_id", "content_id", _DIGEST.fullmatch),
        ):
            value = loaded.get(key)
            if isinstance(value, str) and valid(value):
                fields[field] = value
    return fields


def _in_order(sources: Sequence[SourceResult]) -> list[SourceResult]:
    """The sources in ``SOURCE_ORDER``; an unknown or repeated source raises."""
    by_source: dict[str, SourceResult] = {}
    for s in sources:
        if s.source not in SOURCE_ORDER:
            raise ValueError(f"unknown source: {s.source}")
        if s.source in by_source:
            raise ValueError(f"a source appears twice: {s.source}")
        by_source[s.source] = s
    return [by_source[k] for k in SOURCE_ORDER if k in by_source]


def _status_reason(source: str | None, reason: Reason, *, acknowledged: bool) -> dict[str, Any]:
    shown = reason_dict(reason)
    return {
        "source": source,
        "code": shown["code"],
        "level": shown["level"],
        "text": shown["text"],
        "page": shown["page"],
        "year": shown["year"],
        "acknowledged": acknowledged,
    }


def status_doc(
    *,
    attempt: Attempt,
    outcome: AttemptOutcome,
    severity: Severity,
    sources: Sequence[SourceResult],
    run_reasons: Sequence[Reason],
    serving: bytes | None,
) -> dict[str, Any]:
    """``status.json`` (§5.8): this attempt and the feed the repository serves after it."""
    ordered = _in_order(sources)
    reasons: list[dict[str, Any]] = []
    for s in ordered:
        open_reasons = unacknowledged(s.reasons, s.acknowledged)
        reasons += [
            _status_reason(s.source, r, acknowledged=r not in open_reasons)
            for r in s.reasons
            if REASON_LEVEL[r.code] != "info"
        ]
    reasons += [
        _status_reason(None, r, acknowledged=False)
        for r in run_reasons
        if REASON_LEVEL[r.code] != "info"
    ]
    return {
        "schema_version": 1,
        "attempt_id": attempt.attempt_id,
        "attempt_at": _utc_iso(attempt.attempt_at),
        "trigger": attempt.trigger,
        "code_sha": attempt.code_sha,
        "outcome": outcome,
        "severity": severity,
        "reasons": reasons,
        **_serving_fields(serving),
        "sources": [
            {
                "source": s.source,
                "name": SOURCE_NAMES[s.source],
                "severity": s.severity,
                "using_fallback": s.decision.health.using_fallback,
                "served_fetched_at": _utc_iso(s.decision.health.served_fetched_at),
            }
            for s in ordered
        ],
        "acknowledged": [
            {"source": s.source, **_acknowledged_dict(a)}
            for s in ordered
            for a in s.acknowledged
        ],
    }


_JOINERS: Final = "\u200c\u200d"  # ZWNJ and ZWJ: names in Persian and Indic scripts need them


def md_text(value: object) -> str:
    """``value`` as one line of plain Markdown text (S4-T19).

    Whitespace is collapsed, control, surrogate and format characters are dropped (a name
    keeps its ZWNJ and ZWJ), and every ASCII punctuation character gets a backslash, so the
    text cannot start a heading, link, image, table cell, code span or HTML tag, reorder
    its neighbours (U+202E, U+2066) or fail to write as UTF-8.
    """
    text = collapse_ws(str(value))
    text = "".join(c for c in text if not _dropped(c))
    return text.translate(_ESCAPES)


def _dropped(c: str) -> bool:
    category = unicodedata.category(c)
    return category in ("Cc", "Cs") or (category == "Cf" and c not in _JOINERS)


def _stamp_text(value: object) -> str:
    """A timestamp or date as it is (it holds no Markdown); anything else through ``md_text``."""
    if isinstance(value, str) and _STAMP.fullmatch(value):
        return value
    return "none" if value is None else md_text(value)


def _yes(flag: object) -> str:
    return "yes" if flag else "no"


def _reason_hint(reason: Reason, stage: str, ack: Acknowledgement | None) -> str:
    if REASON_LEVEL[reason.code] == "info":
        return ""
    if ack is not None:
        return f" — acknowledged until {_stamp_text(_utc_iso(ack.until))}"
    if reason.code in NEVER_ACKNOWLEDGEABLE:
        return " — cannot be acknowledged"
    if reason.code in UNIT_REASONS:
        return f" — {_UNIT_HINT}"
    year = "null" if reason.year is None else str(reason.year)
    page = "null" if reason.page is None else md_text(reason.page)
    hint = f" — to acknowledge: scope {{stage: {stage}, year: {year}, page: {page}}}"
    if reason.code in DROP_REASONS:
        hint += f"; {_DROP_HINT}"
    return hint


def _reason_line(reason: Reason, ack: Acknowledgement | None, *, hint: bool = True) -> str:
    shown = reason_dict(reason)
    line = f"- **{shown['level']}** {md_text(shown['code'])}: {md_text(shown['text'])}"
    return line + (_reason_hint(reason, shown["stage"], ack) if hint else "")


def _source_section(entry: dict[str, Any], result: SourceResult) -> list[str]:
    download, parse = entry["download"], entry["parse"]
    snapshot, match, pages = entry["snapshot"], entry["match"], download["pages"]
    units, relevance = parse["units"], parse["relevance"]
    http = "none" if download["http_status"] is None else download["http_status"]
    lines = [
        f"## {md_text(entry['name'])}",
        "",
        f"- Download: {md_text(download['outcome'])}; HTTP {http}; {download['bytes']} bytes, "
        f"{download['attempts']} attempts, {download['elapsed_ms']} ms; pages {pages['ok']} of "
        f"{pages['requested']} ok, {pages['failed']} failed, stop {md_text(pages['stop_reason'])}"
        + (f"; error {md_text(download['error'])}" if download["error"] else "")
        + (f"; url {md_text(download['final_url'])}" if download["final_url"] else ""),
        f"- Parse: parser {md_text(parse['parser_version'])}; {units['seen']} units "
        f"({units['parsed']} parsed, {units['partial']} partial, {units['unparsed']} unparsed, "
        f"{units['ignored']} ignored); {parse['claims']} claims; relevance "
        f"{relevance['in_or_after_window']} in or after the window, {relevance['unknown']} "
        f"unknown, {relevance['before_window']} before it; {parse['parse_ms']} ms",
    ]
    ignored = ", ".join(f"{md_text(k)} {n}" for k, n in sorted(parse["ignored_reasons"].items()))
    lines.append(f"- Ignored: {ignored or 'none'}")
    coverage = "; ".join(
        f"{md_text(year)}: {c['requested']} pages, {c['units_seen']} units, {md_text(c['outcome'])}"
        for year, c in entry["coverage"]["per_year"].items()
    )
    lines.append(f"- Coverage: {coverage or 'none'}")
    served_id = snapshot["served_snapshot_id"]
    baseline_units = snapshot["baseline_units_seen"]
    lines.append(
        f"- Snapshot: {md_text(snapshot['acceptance'])}; "
        f"fallback {_yes(snapshot['using_fallback'])}; "
        f"served {'none' if served_id is None else md_text(served_id)}, "
        f"fetched {_stamp_text(snapshot['served_fetched_at'])}; "
        f"baseline units {'none' if baseline_units is None else baseline_units}; "
        f"comparable {_yes(snapshot['comparable'])}"
    )
    lines.append(
        f"- Match: {match['matched']} of {match['eligible']} eligible matched, "
        f"{match['unmatched']} unmatched, {match['peers_fresh']} fresh peers, "
        f"informative {_yes(match['informative'])}"
    )
    lines += ["", "### Reasons", ""]
    if not result.reasons:
        lines.append("No reasons.")
    open_reasons = unacknowledged(result.reasons, result.acknowledged)
    for reason in result.reasons:
        ack = None
        if reason not in open_reasons:
            ack = next((a for a in result.acknowledged if not unacknowledged([reason], [a])), None)
        lines.append(_reason_line(reason, ack))
    lists = (
        ("### Unparsed samples", [md_text(t) for t in parse["unparsed_samples"]]),
        (
            "### Provisional changes",
            [md_text(i.text) for i in result.items if i.kind == "provisional_change"],
        ),
        (
            "### No longer listed",
            [md_text(i.text) for i in result.items if i.kind == "disappeared_unit"],
        ),
    )
    for heading, texts in lists:
        if texts:
            lines += ["", heading, "", *(f"- {t}" for t in texts)]
    return [*lines, ""]


def health_md(
    parts: FeedParts,
    *,
    sources: Sequence[SourceResult],
    outcome: AttemptOutcome,
    verdict: Verdict,
    severity: Severity,
    feed_size: int | None,
    budget: int,
    problems: Sequence[str],
    not_yet_active: Sequence[Entry],
    dry_run: tuple[int, int] | None = None,
) -> str:
    """``HEALTH.md``: the run, each source and the attention items, every value escaped (S4-T19).

    ``dry_run`` (a dry run's requests made and allowed, P116) adds the dry-run line after the title.

    The source sections render the feed's own source health entries; nothing is recomputed.
    """
    doc = parts.doc
    ordered = _in_order(sources)
    entries = {e["source"]: e for e in doc["source_health"]}
    if set(entries) != {s.source for s in ordered}:
        raise ValueError("the sources do not match the feed's source_health")
    if feed_size is None:
        size = "no feed"
    else:
        size = f"{feed_size} bytes of a {budget} byte budget" + (
            ", over budget" if feed_size > budget else ""
        )
    lines = ["# Elections calendar health", ""]
    if dry_run is not None:
        made, allowed = dry_run
        lines += [
            f"**Dry run:** {made} of {allowed} requests. "
            "Nothing here is published.",
            "",
        ]
    lines += [
        f"- Generated: {_stamp_text(doc['generated_at'])}",
        f"- Outcome: {'published' if outcome == 'published' else 'validation failed'}",
        f"- Verdict: {verdict}",
        f"- Severity: {severity}",
        f"- Data as of: {_stamp_text(doc['data_as_of'])}",
        f"- Feed: {size}",
        "",
        "## Run",
        "",
    ]
    run_lines = [_reason_line(r, None, hint=False) for r in parts.run_reasons]
    run_lines += [f"- {md_text(p)}" for p in problems]
    lines += run_lines or ["No run reasons."]
    lines += ["", "## Sources", ""]
    lines += [
        "| Source | Severity | Acceptance | Served data fetched | Open reasons |",
        "| --- | --- | --- | --- | --- |",
    ]
    for s in ordered:
        entry = entries[s.source]
        opened = len(unacknowledged(s.reasons, s.acknowledged))
        lines.append(
            f"| {md_text(entry['name'])} | {entry['severity']} "
            f"| {md_text(entry['snapshot']['acceptance'])} "
            f"| {_stamp_text(entry['snapshot']['served_fetched_at'])} | {opened} |"
        )
    lines.append("")
    for s in ordered:
        lines += _source_section(entries[s.source], s)
    if not_yet_active:
        lines += ["## Not yet active", ""]
        lines += [
            f"- entry {e.index}: {md_text(e.source)} {md_text(e.reason)}, "
            f"from {_stamp_text(_utc_iso(e.acknowledged_at))}"
            for e in not_yet_active
        ]
        lines.append("")
    lines += ["## Attention items", ""]
    items = doc["attention_items"]
    if items:
        lines += ["| Kind | Source | Date | Text |", "| --- | --- | --- | --- |"]
        lines += [
            f"| {md_text(i['kind'])} | {md_text(SOURCE_NAMES.get(i['source'], i['source']))} "
            f"| {_stamp_text(i['date']) if i['date'] else ''} | {md_text(i['text'])} |"
            for i in items
        ]
    else:
        lines.append("No attention items.")
    if doc["attention_truncated"]:
        lines += ["", f"and {doc['attention_truncated']} more in attention_full.json"]
    return "\n".join(lines) + "\n"
