"""The run: fetch, parse, decide, merge, build the feed, write ``out/`` (Plan 4 Task 8).

``run`` is the only place the pieces meet. It reads no clock: ``now`` (the instant the data is
judged at) and ``wall_clock`` (the machine clock, for the feed's timestamp check) come in with
the ``RunConfig``. Nothing is published here: the run writes ``out/`` and Plan 5's publish job
copies the repository files from it.

A defect in one source never costs the others: a fetch or parse exception becomes that source's
``worker_failed`` run, and a committed file that cannot be read becomes that file's corrupt form
(P94). A merge failure, a feed that fails validation and a status that fails validation each
block publishing (``validation_failed``) while the artifact still says why.

``manifest.json`` is written last, so an interrupted artifact has none.
"""

import dataclasses
import json
import shutil
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast, get_args

from elections_calendar import ledger
from elections_calendar.feed import (
    AttemptOutcome,
    FeedParts,
    RunInfo,
    SourceResult,
    attempt_of,
    build_feed,
    health_md,
    reason_dict,
    status_doc,
)
from elections_calendar.fetch import SOURCE_DEADLINE_S, Deadline, FetchResult
from elections_calendar.health import (
    HealthState,
    KnownIssues,
    Severity,
    Verdict,
    acknowledge,
    drop_acceptances,
    health_state_to_dict,
    load_health_state,
    load_known_issues,
    match_diagnostic,
    next_health_state,
    not_yet_active,
    present_keys,
    source_reasons,
    unacknowledged,
)
from elections_calendar.health import severity as severity_of
from elections_calendar.health import verdict as verdict_of
from elections_calendar.ledger import LedgerReport
from elections_calendar.merge import merge
from elections_calendar.model import (
    MAX_DETAIL,
    REASON_LEVEL,
    SOURCE_ORDER,
    FetchOutcome,
    MergeResult,
    Reason,
    RecordError,
    stored_json,
)
from elections_calendar.publish import (
    FEED_BUDGET_BYTES,
    feed_bytes,
    write_atomic,
    write_manifest,
)
from elections_calendar.runner import (
    DEFAULT_ADAPTERS,
    AdapterSpec,
    ScrapeRun,
    SourceRun,
    load_adapter,
    run_sources,
)
from elections_calendar.snapshots import (
    Baseline,
    Decision,
    Snapshot,
    baseline_to_dict,
    build_snapshot,
    decide,
    load_baseline,
    registry_version,
    snapshot_to_dict,
    unit_items,
)
from elections_calendar.sources.base import (
    PARSER_VERSION,
    PageCoverage,
    ParseResult,
    RawPages,
    Registries,
)
from elections_calendar.validate import ServedCheck, validate_feed, validate_status
from elections_calendar.window import Window, window_for

__all__ = [
    "OfflineGetter",
    "OfflinePage",
    "RunConfig",
    "RunResult",
    "UsageError",
    "load_offline",
    "run",
]

_SHAPE = "pages.json: shape"
_PAGE_KEYS = frozenset({"url", "file", "fetched_at", "content_type", "status"})
_OUTCOMES = frozenset(get_args(FetchOutcome))
_SEVERITY_RANK: Mapping[Severity, int] = {"ok": 0, "warning": 1, "error": 2}


class UsageError(Exception):
    """The run was asked for something it cannot do; ``__main__`` turns it into exit status 2."""


# --- offline input ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OfflinePage:
    """One entry of ``pages.json``: a URL answered from a file."""

    url: str
    file: Path  # resolved against the pages.json directory
    fetched_at: datetime
    content_type: str
    status: int | None
    outcome: FetchOutcome = "ok"


class OfflineGetter:
    """A ``fetch.Getter`` over ``pages.json``: a known URL gives its file, any other a 404."""

    def __init__(self, pages: Sequence[OfflinePage]) -> None:
        self._pages = {page.url: page for page in pages}

    def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
        page = self._pages.get(url)
        if page is None:
            return FetchResult(url, url, "http_error", "done", 404, None, b"", 0, 1)
        return FetchResult(
            url,
            url,
            page.outcome,
            "done",
            page.status,
            page.content_type,
            page.file.read_bytes(),
            0,
            1,
        )

    def fetched_at(self, url: str) -> datetime | None:
        page = self._pages.get(url)
        return None if page is None else page.fetched_at


def _offline_page(entry: object, directory: Path) -> OfflinePage:
    if not isinstance(entry, dict):
        raise UsageError(_SHAPE)
    keys = set(entry)
    if not (_PAGE_KEYS <= keys <= _PAGE_KEYS | {"outcome"}):
        raise UsageError(_SHAPE)
    url, file, stamp = entry["url"], entry["file"], entry["fetched_at"]
    content_type, status = entry["content_type"], entry["status"]
    outcome = entry.get("outcome", "ok")
    if not (
        isinstance(url, str)
        and isinstance(file, str)
        and isinstance(stamp, str)
        and isinstance(content_type, str)
        and (status is None or (isinstance(status, int) and not isinstance(status, bool)))
        and isinstance(outcome, str)
        and outcome in _OUTCOMES
    ):
        raise UsageError(_SHAPE)
    try:
        fetched_at = datetime.fromisoformat(stamp)
    except ValueError:
        raise UsageError(_SHAPE) from None
    if fetched_at.utcoffset() is None:
        raise UsageError(f"pages.json: {url}: fetched_at needs a time zone")
    path = directory / file
    if not path.is_file():
        raise UsageError(f"pages.json: no file {file}")
    return OfflinePage(url, path, fetched_at, content_type, status, cast(FetchOutcome, outcome))


def load_offline(directory: Path) -> OfflineGetter:
    """The getter over ``directory / "pages.json"``; ``UsageError("pages.json: <problem>")``."""
    try:
        raw = (directory / "pages.json").read_bytes()
    except FileNotFoundError:
        raise UsageError("pages.json: not found") from None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise UsageError(_SHAPE) from None
    if not isinstance(data, dict) or set(data) != {"pages"} or not isinstance(data["pages"], list):
        raise UsageError(_SHAPE)
    pages: list[OfflinePage] = []
    seen: set[str] = set()
    for entry in data["pages"]:
        page = _offline_page(entry, directory)
        if page.url in seen:
            raise UsageError(f"pages.json: repeated url {page.url}")
        seen.add(page.url)
        pages.append(page)
    return OfflineGetter(pages)


# --- the run ---------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RunConfig:
    out: Path
    repo: Path
    now: datetime
    wall_clock: datetime
    environ: Mapping[str, str]
    offline: Path | None = None  # None = live
    specs: tuple[AdapterSpec, ...] = DEFAULT_ADAPTERS
    timer: Callable[[], float] = time.perf_counter


@dataclass(frozen=True, slots=True)
class RunResult:
    outcome: AttemptOutcome
    verdict: Verdict
    feed_bytes: int | None


@dataclass(frozen=True, slots=True)
class _Parsed:
    """One source after parsing: everything ``decide`` and the writer need."""

    spec: AdapterSpec
    run: SourceRun
    parse_ms: int
    report: LedgerReport | None
    snapshot: Snapshot
    candidate_json: bytes
    baseline: Baseline | None
    baseline_problem: str | None
    state: HealthState


def _fetch_offline(
    config: RunConfig, window: Window, getter: OfflineGetter
) -> ScrapeRun:
    runs: list[SourceRun] = []
    for spec in config.specs:
        try:
            adapter = load_adapter(spec)
            pages = tuple(
                dataclasses.replace(
                    page,
                    fetched_at=getter.fetched_at(page.request.url) or config.now,
                )
                for page in adapter.fetch(window, getter, Deadline.after(SOURCE_DEADLINE_S))
            )
        except Exception as exc:
            raw = RawPages(spec.source, (), ())
            detail = f"fetch: {type(exc).__name__}"
            runs.append(SourceRun(spec.source, raw, "worker_failed", 0, detail))
        else:
            runs.append(SourceRun(spec.source, RawPages(spec.source, pages, ()), "complete", 0))
    return ScrapeRun((), tuple(runs))


def _fetch_live(config: RunConfig, window: Window) -> ScrapeRun:
    workdir = Path(tempfile.mkdtemp(prefix="elections-"))
    try:
        return run_sources(config.specs, window, workdir=workdir, environ=config.environ)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)  # F-10


def _parse_failure(raw: RawPages) -> ParseResult:
    """The result of a parser that failed: every page is unrecognised, every request unfinished."""
    coverage = [
        PageCoverage(
            page.request.key,
            page.request.year,
            "layout_not_recognised",
            None,
            0,
            detail="the parser failed",
        )
        for page in raw.pages
    ]
    coverage += [
        PageCoverage(request.key, request.year, "unfinished", None, 0) for request in raw.unfinished
    ]
    return ParseResult(raw.source, (), (), tuple(coverage))


def _read_baseline(path: Path) -> tuple[Baseline | None, str | None]:
    try:
        return load_baseline(path), None
    except RecordError as exc:
        return None, str(exc)
    except OSError as exc:
        return None, f"baseline.json is corrupt: cannot be read ({type(exc).__name__})"


def _read_state(path: Path) -> HealthState:
    try:
        return load_health_state(path)
    except OSError as exc:
        return HealthState((), f"cannot be read ({type(exc).__name__})")


def _read_issues(path: Path, now: datetime) -> KnownIssues:
    try:
        return load_known_issues(path, now=now)
    except OSError as exc:
        reason = Reason("ack_invalid", f"known_issues.yml cannot be read ({type(exc).__name__})")
        return KnownIssues((), (reason,))


def _parse_source(
    config: RunConfig,
    window: Window,
    registries: Registries,
    registry: str,
    spec: AdapterSpec,
    run: SourceRun,
) -> _Parsed:
    elapsed = 0.0
    report: LedgerReport | None = None
    failure: Exception | None = None
    try:
        adapter = load_adapter(spec)
        start = config.timer()
        try:
            result = adapter.parse(run.raw, window, registries)
        finally:
            elapsed = config.timer() - start
        report = ledger.check(run.raw, result)
        snapshot = build_snapshot(
            run.raw,
            result,
            parser_version=adapter.parser_version,
            registry_version=registry,
            years=window.years,
        )
        candidate_json = stored_json(snapshot_to_dict(snapshot))  # strict UTF-8, as it is written
    except Exception as exc:
        failure = exc
    if failure is not None:
        report = None
        run = dataclasses.replace(
            run, outcome="worker_failed", detail=f"parse: {type(failure).__name__}"
        )
        snapshot = build_snapshot(
            run.raw,
            _parse_failure(run.raw),
            parser_version=PARSER_VERSION,
            registry_version=registry,
            years=window.years,
        )
        candidate_json = stored_json(snapshot_to_dict(snapshot))
    folder = config.repo / "data" / "sources" / spec.source
    baseline, problem = _read_baseline(folder / "baseline.json")
    return _Parsed(
        spec=spec,
        run=run,
        parse_ms=round(elapsed * 1000),
        report=report,
        snapshot=snapshot,
        candidate_json=candidate_json,
        baseline=baseline,
        baseline_problem=problem,
        state=_read_state(folder / "health_state.json"),
    )


def _served_check(decision: Decision) -> ServedCheck:
    """The served snapshot's id and the two checks its baseline passed (§11.3 check 6)."""
    source = decision.source
    if decision.acceptance == "unavailable" or decision.served is None:
        return ServedCheck(source, None, True, True)
    if decision.acceptance == "promoted" or decision.baseline is None:
        return ServedCheck(source, decision.served.snapshot_id, True, True)
    base = decision.baseline
    return ServedCheck(source, decision.served.snapshot_id, base.ledger_ok, base.discovery_ok)


def _worst(*levels: Severity) -> Severity:
    return max(levels, key=_SEVERITY_RANK.__getitem__)


def _verdict_rows(
    sources: Sequence[SourceResult], run_reasons: Sequence[Reason]
) -> list[dict[str, Any]]:
    def row(source: str | None, reason: Reason, *, acknowledged: bool) -> dict[str, Any]:
        shown = reason_dict(reason)
        return {
            "source": source,
            "code": shown["code"],
            "level": shown["level"],
            "text": shown["text"],
            "acknowledged": acknowledged,
        }

    rows: list[dict[str, Any]] = []
    for s in sorted(sources, key=lambda s: SOURCE_ORDER.index(s.source)):
        open_reasons = unacknowledged(s.reasons, s.acknowledged)
        rows += [
            row(s.source, r, acknowledged=r not in open_reasons)
            for r in s.reasons
            if REASON_LEVEL[r.code] != "info"
        ]
    rows += [
        row(None, r, acknowledged=False) for r in run_reasons if REASON_LEVEL[r.code] != "info"
    ]
    return rows


def _check_usage(config: RunConfig) -> OfflineGetter | None:
    if config.now.utcoffset() is None or config.wall_clock.utcoffset() is None:
        raise UsageError("--now needs a time zone")
    if config.out.exists() and (not config.out.is_dir() or any(config.out.iterdir())):
        raise UsageError("--out must be empty")
    return None if config.offline is None else load_offline(config.offline)


def run(config: RunConfig) -> RunResult:
    """One run into ``config.out``; see the module docstring and Plan 4 Task 8 for the order."""
    now, out, repo = config.now, config.out, config.repo
    getter = _check_usage(config)
    window = window_for(now)
    registries = Registries.load()
    registry = registry_version()
    issues = _read_issues(repo / "known_issues.yml", now)

    # Fetch.
    scrape = (
        _fetch_live(config, window)
        if getter is None
        else _fetch_offline(config, window, getter)
    )

    # Parse, check, snapshot and load what is committed.
    parsed = [
        _parse_source(config, window, registries, registry, spec, source_run)
        for spec, source_run in zip(config.specs, scrape.runs, strict=True)
    ]

    # Decide.
    acceptances = drop_acceptances(issues, {p.spec.source: p.state for p in parsed}, now)
    decisions = [
        decide(
            p.snapshot,
            run_outcome=p.run.outcome,
            run_detail=p.run.detail,
            ledger=p.report,
            baseline=p.baseline,
            baseline_problem=p.baseline_problem,
            acceptances=acceptances,
            window=window,
            now=now,
        )
        for p in parsed
    ]
    all_items = [unit_items(d) for d in decisions]

    # Merge.
    claims = tuple(c for d in decisions for c in d.claims)
    run_reasons: list[Reason] = list(issues.problems)
    merge_error: str | None = None
    try:
        merged = merge(claims, now=now, places=registries.places)
    except ValueError as exc:
        merge_error = str(exc)
        merged = MergeResult((), (), (), ())
        run_reasons.append(Reason("merge_failed", merge_error[:MAX_DETAIL]))

    # Health per source.
    fresh = frozenset(d.source for d in decisions if d.acceptance == "promoted")
    results: list[SourceResult] = []
    for p, decision, items in zip(parsed, decisions, all_items, strict=True):
        match = match_diagnostic(merged, claims, p.spec.source, fresh=fresh, window=window)
        reasons = source_reasons(decision.reasons, items, match, p.state)
        results.append(
            SourceResult(
                source=p.spec.source,
                run=p.run,
                parse_ms=p.parse_ms,
                ledger=p.report,
                decision=decision,
                items=items,
                match=match,
                reasons=reasons,
                acknowledged=acknowledge(p.spec.source, reasons, items, issues, p.state, now),
                severity=severity_of(reasons),
            )
        )

    # The feed.
    attempt = attempt_of(config.environ, now)
    parts: FeedParts = build_feed(
        merged,
        results,
        window=window,
        now=now,
        run=RunInfo(attempt.code_sha, scrape.trust_sources),
        run_reasons=run_reasons,
    )
    feed: bytes | None = None
    problems: list[str] = []
    outcome: AttemptOutcome = "published"
    reasons_now = list(parts.run_reasons)
    if merge_error is None:
        feed = feed_bytes(parts.doc, published_at=now)
        problems = list(
            validate_feed(
                feed,
                served=[_served_check(d) for d in decisions],
                wall_clock=config.wall_clock,
            )
        )
        if problems:
            reasons_now.append(Reason("validation_failed", problems[0][:MAX_DETAIL]))
    feed_problems = len(problems)
    if merge_error is not None or problems:
        outcome = "validation_failed"

    def serving_for(state: AttemptOutcome) -> bytes | None:
        if state == "published":
            return feed
        try:
            return (repo / "elections.json").read_bytes()
        except FileNotFoundError:
            return None

    def status_for(state: AttemptOutcome) -> bytes:
        return stored_json(
            status_doc(
                attempt=attempt,
                outcome=state,
                severity=_worst(parts.severity, severity_of(reasons_now)),
                sources=results,
                run_reasons=reasons_now,
                serving=serving_for(state),
            )
        )

    # The status gate (review P4-06).
    status = status_for(outcome)
    rejected_status: bytes | None = None
    status_problems = validate_status(status)
    if status_problems:
        problems += status_problems
        rejected_status = status
        reasons_now.append(
            Reason("validation_failed", ("status: " + status_problems[0])[:MAX_DETAIL])
        )
        outcome = "validation_failed"
        status = status_for(outcome)
        again = validate_status(status)
        if again:
            raise RuntimeError(f"status.json failed validation: {again[0]}")
    run_severity = _worst(parts.severity, severity_of(reasons_now))

    # The verdict.
    open_reasons = [r for s in results for r in unacknowledged(s.reasons, s.acknowledged)]
    verdict = verdict_of([*open_reasons, *reasons_now])
    verdict_doc = {
        "verdict": verdict,
        "outcome": outcome,
        "severity": run_severity,
        "reasons": _verdict_rows(results, reasons_now),
        "feed_bytes": None if feed is None else len(feed),
        "feed_budget_bytes": FEED_BUDGET_BYTES,
        "trust_sources": list(scrape.trust_sources),
    }
    health = health_md(
        parts,
        sources=results,
        outcome=outcome,
        verdict=verdict,
        severity=run_severity,
        feed_size=None if feed is None else len(feed),
        budget=FEED_BUDGET_BYTES,
        problems=problems,
        not_yet_active=not_yet_active(issues, now),
    )

    # Write, `manifest.json` last.
    published = outcome == "published"
    if published:
        assert feed is not None
        write_atomic(out / "elections.json", feed)
    write_atomic(out / "status.json", status)
    write_atomic(out / "HEALTH.md", health.encode("utf-8"))
    if published:
        for p, decision, items, result in zip(parsed, decisions, all_items, results, strict=True):
            folder = out / "data" / "sources" / p.spec.source
            if decision.baseline is not None:
                baseline_json = stored_json(baseline_to_dict(decision.baseline))
                write_atomic(folder / "baseline.json", baseline_json)
            write_atomic(folder / "candidate.json", p.candidate_json)
            state = next_health_state(
                p.state, p.spec.source, issues, present_keys(result.reasons, items), now
            )
            write_atomic(folder / "health_state.json", stored_json(health_state_to_dict(state)))
    write_atomic(out / "verdict.json", stored_json(verdict_doc))
    write_atomic(out / "attention_full.json", stored_json(parts.attention_full))
    write_atomic(out / "dispositions.json", stored_json(parts.dispositions))
    if feed is not None and feed_problems:
        write_atomic(out / "rejected" / "elections.json", feed)
    if rejected_status is not None:
        write_atomic(out / "rejected" / "status.json", rejected_status)
    if problems:
        text = "\n".join(problems) + "\n"
        write_atomic(out / "rejected" / "validation.txt", text.encode("utf-8"))
    if merge_error is not None:
        write_atomic(out / "rejected" / "merge_error.txt", merge_error.encode("utf-8"))
    write_manifest(out)
    return RunResult(outcome, verdict, None if feed is None else len(feed))
