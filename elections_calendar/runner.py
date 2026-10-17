"""The per-source runner (spec §8, C15): every source in its own process, under hard deadlines.

``Fetcher`` limits inactivity, not wall-clock time: name resolution, connecting
to several addresses in turn and headers sent a byte at a time can all run long.
So each source is fetched by a spawned child process, and the parent cuts the
child at its deadline whatever it is doing.

The parent never reads from a running worker and never blocks on one: it waits
only on process sentinels (no pipes, no queues), so a worker that stalls half
way through a handover cannot hold it up. A worker hands its pages over as
files in its own directory: each page is pickled to ``<n>.tmp`` and published
with ``os.replace`` as ``<n>.page``; ``done`` or ``error`` ends the handover.
Only published files are read, and only after the worker is gone.

A scrape is bounded twice. The work cutoff of a source is the earlier of its
own start + ``source_deadline_s`` and the scrape deadline. The parent cuts the
worker within its wake latency of the cutoff, and no page published after the
cut counts. A worker cut at its cutoff is ``deadline`` even if it had just
finished. ``run_sources`` returns within the latest cutoff + ``grace_s``
+ 2 s, cleanup included. Parsing happens after ``run_sources`` and is not
bounded here (Plan 4).
"""

import importlib
import multiprocessing
import multiprocessing.connection
import os
import pickle
import shutil
import sys
import time
import traceback
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any, Literal

from elections_calendar.fetch import (
    SCRAPE_DEADLINE_S,
    SOURCE_DEADLINE_S,
    Deadline,
    Fetcher,
    trust_bundle,
)
from elections_calendar.sources.base import Adapter, PageRequest, RawPage, RawPages
from elections_calendar.window import Window

SourceOutcome = Literal["complete", "deadline", "scrape_deadline", "worker_failed"]

_wait = multiprocessing.connection.wait  # a module-level name so a test can replace it
_IDLE_WAKE_S = 1.0


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    """Which adapter to run: ``target`` is ``"module:Class"``, ``options`` its keyword arguments."""

    source: str
    target: str
    options: tuple[tuple[str, str], ...] = ()


DEFAULT_ADAPTERS = (
    AdapterSpec("electionguide", "elections_calendar.sources.electionguide:ElectionGuide"),
    AdapterSpec("wikipedia", "elections_calendar.sources.wikipedia:Wikipedia"),
)


@dataclass(frozen=True, slots=True)
class SourceRun:
    """What one source gave. ``raw.unfinished`` lists the requests whose pages were not received."""

    source: str
    raw: RawPages
    outcome: SourceOutcome
    elapsed_ms: int
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ScrapeRun:
    trust_sources: tuple[str, ...]
    runs: tuple[SourceRun, ...]  # in spec order


def _load(spec: AdapterSpec) -> Adapter:
    module, _, name = spec.target.partition(":")
    adapter_class: Any = getattr(importlib.import_module(module), name)
    adapter: Adapter = adapter_class(**dict(spec.options))
    return adapter


def _publish(directory: Path, temporary: str, final: str, data: bytes) -> None:
    """Write ``temporary``, then make it visible as ``final`` in one step."""
    path = directory / temporary
    path.write_bytes(data)
    os.replace(path, directory / final)


def _work(spec: AdapterSpec, directory: str, bundle: str, seconds: float, window: Window) -> None:
    """The worker's entry point (runs in the child). Writes only into ``directory``."""
    out = Path(directory)
    try:
        adapter = _load(spec)
        deadline = Deadline.after(seconds)
        with Fetcher(verify=bundle) as fetcher:
            for number, page in enumerate(adapter.fetch(window, fetcher, deadline), start=1):
                _publish(out, f"{number:04d}.tmp", f"{number:04d}.page", pickle.dumps(page))
        _publish(out, "done.tmp", "done", b"")
    except Exception as exc:
        traceback.print_exc()  # to this process's stderr, the operator's console
        # Only the type: the message may carry a URL or a path.
        _publish(out, "error.tmp", "error", type(exc).__name__.encode("utf-8"))
        sys.exit(1)


@dataclass(slots=True)
class _Slot:
    """One source on its way through the runner."""

    index: int
    spec: AdapterSpec
    requests: tuple[PageRequest, ...]
    directory: Path
    process: BaseProcess | None = None
    started_at: float = 0.0
    cutoff: float = 0.0
    scrape_cut: bool = False  # the scrape deadline, not the source's own, is the cutoff
    cut_at: float | None = None
    kill_at: float | None = None
    killed: bool = False
    snapshot: frozenset[str] = frozenset()  # the pages published when the worker was cut


class _Scrape:
    def __init__(
        self,
        specs: Sequence[AdapterSpec],
        window: Window,
        bundle: Path,
        began: float,
        source_deadline_s: float,
        scrape_deadline_s: float,
        parallel: int,
        grace_s: float,
        pages_root: Path,
    ) -> None:
        self._window = window
        self._bundle = bundle
        self._source_deadline_s = source_deadline_s
        self._scrape_end = began + scrape_deadline_s
        self._parallel = parallel
        self._grace_s = grace_s
        self._pages_root = pages_root
        self._context = multiprocessing.get_context("spawn")
        self.slots = [
            _Slot(
                index, spec, _load(spec).requests(window), pages_root / f"{index:02d}-{spec.source}"
            )
            for index, spec in enumerate(specs)
        ]
        self._pending = deque(self.slots)
        self.live: list[_Slot] = []
        self.runs: dict[int, SourceRun] = {}

    def run(self) -> tuple[SourceRun, ...]:
        while self._pending or self.live:
            self._start_pending(time.monotonic())
            if not self.live:
                break
            ready = _wait([_process(s).sentinel for s in self.live], timeout=self._timeout())
            now = time.monotonic()
            self._reap(set(ready), now)
            self._cut(now)
            self._kill(now)
        return tuple(self.runs[slot.index] for slot in self.slots)

    def stop_all(self) -> None:
        """Kill and join every worker that is still alive."""
        for slot in self.live:
            _process(slot).kill()
        for slot in self.live:
            _process(slot).join()
        self.live.clear()

    def _start_pending(self, now: float) -> None:
        while self._pending and len(self.live) < self._parallel:
            if now >= self._scrape_end:
                while self._pending:
                    slot = self._pending.popleft()
                    raw = RawPages(slot.spec.source, (), slot.requests)
                    self.runs[slot.index] = SourceRun(slot.spec.source, raw, "scrape_deadline", 0)
                return
            self._start(self._pending.popleft(), now)

    def _start(self, slot: _Slot, now: float) -> None:
        own_cutoff = now + self._source_deadline_s
        slot.scrape_cut = self._scrape_end <= own_cutoff
        slot.cutoff = self._scrape_end if slot.scrape_cut else own_cutoff
        slot.started_at = now
        slot.directory.mkdir(parents=True)
        slot.process = self._context.Process(
            target=_work,
            args=(
                slot.spec,
                str(slot.directory),
                str(self._bundle),
                slot.cutoff - now,
                self._window,
            ),
            name=f"source-{slot.spec.source}",
            daemon=True,
        )
        slot.process.start()
        self.live.append(slot)

    def _timeout(self) -> float:
        """Seconds to the nearest cutoff or kill time."""
        moments = [
            slot.cutoff if slot.kill_at is None else slot.kill_at
            for slot in self.live
            if not slot.killed
        ]
        if not moments:
            return _IDLE_WAKE_S  # every live worker is killed; its sentinel is about to fire
        return max(0.0, min(moments) - time.monotonic())

    def _reap(self, ready: set[Any], now: float) -> None:
        for slot in list(self.live):
            process = _process(slot)
            if process.sentinel in ready:
                process.join()  # it has exited: returns at once
                self.live.remove(slot)
                self.runs[slot.index] = self._collect(slot, now)

    def _cut(self, now: float) -> None:
        for slot in self.live:
            if slot.cut_at is None and now >= slot.cutoff:
                # The snapshot comes first: what is published later does not count.
                slot.snapshot = frozenset(p.name for p in slot.directory.glob("*.page"))
                _process(slot).terminate()
                slot.cut_at = now
                slot.kill_at = now + self._grace_s

    def _kill(self, now: float) -> None:
        for slot in self.live:
            if slot.kill_at is not None and not slot.killed and now >= slot.kill_at:
                _process(slot).kill()
                slot.killed = True

    def _collect(self, slot: _Slot, now: float) -> SourceRun:
        """The run of a worker that has exited; deletes its directory."""
        directory = slot.directory
        detail = ""
        if slot.cut_at is not None:
            outcome: SourceOutcome = "scrape_deadline" if slot.scrape_cut else "deadline"
            names = sorted(slot.snapshot)
            ended = slot.cut_at
        else:
            ended = now
            names = sorted(p.name for p in directory.glob("*.page"))
            if (directory / "done").exists():
                outcome = "complete"
            elif (directory / "error").exists():
                outcome = "worker_failed"
                detail = (directory / "error").read_text(encoding="utf-8")
            else:
                outcome = "worker_failed"
                detail = f"exit code {_process(slot).exitcode}"
        pages: list[RawPage] = [pickle.loads((directory / name).read_bytes()) for name in names]
        shutil.rmtree(directory, ignore_errors=True)
        got = {page.request.key for page in pages}
        raw = RawPages(
            slot.spec.source,
            tuple(pages),
            tuple(request for request in slot.requests if request.key not in got),
        )
        elapsed_ms = int((ended - slot.started_at) * 1000)
        return SourceRun(slot.spec.source, raw, outcome, elapsed_ms, detail)


def _process(slot: _Slot) -> BaseProcess:
    assert slot.process is not None
    return slot.process


def run_sources(
    specs: Sequence[AdapterSpec],
    window: Window,
    *,
    workdir: Path,
    environ: Mapping[str, str] = os.environ,
    source_deadline_s: float = SOURCE_DEADLINE_S,
    scrape_deadline_s: float = SCRAPE_DEADLINE_S,
    parallel: int = 4,
    grace_s: float = 5.0,
) -> ScrapeRun:
    """Fetch every source in its own worker process; returns within the latest cutoff + grace + 2 s.

    The CA bundle is written first, in the parent: a ``TrustBundleError`` propagates before
    any worker starts. No worker outlives this call, whatever happens in it. ``environ`` only
    selects the CA bundle: workers inherit ``os.environ``, proxy variables included.
    """
    began = time.monotonic()
    if parallel < 1:
        raise ValueError("parallel must be at least 1")
    bundle = trust_bundle(workdir / "ca-bundle.pem", environ)
    pages_root = workdir / "pages"
    shutil.rmtree(pages_root, ignore_errors=True)  # left by a killed run
    scrape = _Scrape(
        specs,
        window,
        bundle.path,
        began,
        source_deadline_s,
        scrape_deadline_s,
        parallel,
        grace_s,
        pages_root,
    )
    try:
        runs = scrape.run()
    finally:
        scrape.stop_all()
        shutil.rmtree(pages_root, ignore_errors=True)
    return ScrapeRun(bundle.sources, runs)
