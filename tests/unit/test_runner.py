"""The per-source runner (spec §8, C15): hard deadlines over real spawned workers.

Workers are real child processes running the adapters in
``tests/support/slow_adapters.py``; the only server is the local HTTPS one.
"""

import configparser
import multiprocessing
import multiprocessing.context
import pickle
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from multiprocessing.connection import wait as real_wait
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Any

import pytest

from elections_calendar import runner
from elections_calendar.fetch import TrustBundleError
from elections_calendar.model import Reason
from elections_calendar.runner import AdapterSpec, run_sources
from elections_calendar.sources.base import missing_pages
from elections_calendar.window import window_for
from tests.support.http_server import Reply, TestServer
from tests.support.slow_adapters import Chain

WINDOW = window_for(datetime(2026, 10, 16, 12, 0, tzinfo=UTC))


@pytest.fixture(autouse=True)
def no_worker_outlives_the_test() -> Iterator[None]:
    yield
    assert multiprocessing.active_children() == []


def spec(adapter: str, **options: str) -> AdapterSpec:
    return AdapterSpec(
        adapter.lower(), f"tests.support.slow_adapters:{adapter}", tuple(options.items())
    )


def test_a_complete_source_returns_its_pages(
    server: TestServer, ca_env: dict[str, str], tmp_path: Path
) -> None:
    urls = f"{server.route('/a', Reply(body=b'a'))},{server.route('/b', Reply(body=b'b'))}"
    run = run_sources([spec("Pages", urls=urls)], WINDOW, workdir=tmp_path, environ=ca_env)
    (r,) = run.runs
    assert (r.outcome, [p.request.key for p in r.raw.pages], r.raw.unfinished) == (
        "complete",
        ["one", "two"],
        (),
    )
    assert [p.result.body for p in r.raw.pages] == [b"a", b"b"]
    assert run.trust_sources == ("certifi", "REQUESTS_CA_BUNDLE")
    assert not (tmp_path / "pages").exists()


@pytest.mark.parametrize("adapter", ["SlowDns", "FailingAddresses", "DripHeaders"])
def test_a_blocked_worker_is_cut_at_the_source_deadline(
    adapter: str, server: TestServer, ca_env: dict[str, str], tmp_path: Path
) -> None:
    options: dict[str, str] = {}
    if adapter == "DripHeaders":
        options["url"] = server.route("/slow", Reply(body=b"x", header_drip=0.5))
    start = time.monotonic()
    (r,) = run_sources(
        [spec(adapter, **options)],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        source_deadline_s=2,
        grace_s=2,
    ).runs
    assert r.outcome == "deadline" and r.raw.pages == () and len(r.raw.unfinished) == 1
    assert time.monotonic() - start < 2 + 2 + 3  # cutoff + grace + spawn slack


def test_a_worker_stalled_mid_handover_cannot_block_the_parent(
    tmp_path: Path, ca_env: dict[str, str]
) -> None:  # review P2-03, A03
    start = time.monotonic()
    (r,) = run_sources(
        [spec("StallMidWrite", record=str(tmp_path / "stalled"))],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        source_deadline_s=2,
        grace_s=2,
    ).runs
    assert (tmp_path / "stalled").exists()  # the worker did reach the stalled os.replace
    assert (r.outcome, r.raw.pages) == ("deadline", ())
    assert [q.key for q in r.raw.unfinished] == ["one"]
    assert time.monotonic() - start < 2 + 2 + 3


def test_deadlines_that_expire_together_are_cut_together(
    tmp_path: Path, ca_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:  # review P2-03, A04
    # terminate() does nothing, like a worker that ignores SIGTERM (on Windows it
    # is TerminateProcess), so only the kill after the grace period ends them.
    monkeypatch.setattr(BaseProcess, "terminate", lambda self: None)
    start = time.monotonic()
    runs = run_sources(
        [spec("IgnoreTerm", seconds="30")] * 3,
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        source_deadline_s=2,
        grace_s=2,
    ).runs
    assert [r.outcome for r in runs] == ["deadline"] * 3
    elapsed = time.monotonic() - start
    assert 2 + 2 <= elapsed < 2 + 2 + 3  # the kill ran, after one grace period, not three


def test_pages_published_before_a_crash_are_kept(
    tmp_path: Path, ca_env: dict[str, str], server: TestServer
) -> None:  # A04
    url = server.route("/a", Reply(body=b"a"))
    (r,) = run_sources(
        [spec("CrashAfterPage", url=url)], WINDOW, workdir=tmp_path, environ=ca_env
    ).runs
    assert (
        r.outcome,
        r.detail,
        [p.request.key for p in r.raw.pages],
        [q.key for q in r.raw.unfinished],
    ) == ("worker_failed", "exit code 3", ["one"], ["two"])


def test_the_scrape_budget_ending_mid_source_keeps_finished_pages(
    server: TestServer, ca_env: dict[str, str], tmp_path: Path
) -> None:
    urls = f"{server.route('/fast', Reply(body=b'f'))},{server.route('/slow', Reply(delay=30))}"
    (r,) = run_sources(
        [spec("Pages", urls=urls)],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        source_deadline_s=30,
        scrape_deadline_s=6,
        grace_s=2,
    ).runs
    assert (r.outcome, [p.request.key for p in r.raw.pages], [q.key for q in r.raw.unfinished]) == (
        "scrape_deadline",
        ["one"],
        ["two"],
    )


def test_sources_not_started_before_the_scrape_deadline_are_recorded(
    tmp_path: Path, ca_env: dict[str, str]
) -> None:
    second = tmp_path / "second-ran"
    runs = run_sources(
        [spec("Sleeper", seconds="5"), spec("Sleeper", seconds="0", record=str(second))],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        parallel=1,
        scrape_deadline_s=2,
        grace_s=2,
    ).runs
    assert [r.outcome for r in runs] == ["scrape_deadline", "scrape_deadline"]
    assert (runs[1].elapsed_ms, runs[1].raw.pages) == (0, ())
    assert not second.exists()


def test_a_stale_pages_directory_is_cleared_before_the_first_worker(
    server: TestServer, ca_env: dict[str, str], tmp_path: Path
) -> None:
    stale = tmp_path / "pages" / "00-pages"
    stale.mkdir(parents=True)
    (stale / "0001.page").write_bytes(b"junk left by a killed run")
    url = server.route("/a", Reply(body=b"a"))
    (r,) = run_sources([spec("Pages", urls=url)], WINDOW, workdir=tmp_path, environ=ca_env).runs
    assert (r.outcome, [p.result.body for p in r.raw.pages]) == ("complete", [b"a"])
    assert not (tmp_path / "pages").exists()


def test_nothing_arrives_after_the_deadline(
    tmp_path: Path, ca_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # terminate() does nothing, like a worker that ignores SIGTERM: the page is
    # published after the cutoff but before the kill, and must not count.
    monkeypatch.setattr(BaseProcess, "terminate", lambda self: None)
    (r,) = run_sources(
        [spec("LatePage", seconds="3")],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        source_deadline_s=1.5,
        grace_s=8,
    ).runs
    assert (r.outcome, r.raw.pages) == ("deadline", ())
    assert [q.key for q in r.raw.unfinished] == ["one"]


def test_a_worker_that_raises_or_crashes_is_worker_failed(
    tmp_path: Path, ca_env: dict[str, str]
) -> None:
    runs = run_sources([spec("Raise"), spec("Crash")], WINDOW, workdir=tmp_path, environ=ca_env).runs
    assert [(r.outcome, r.detail) for r in runs] == [
        ("worker_failed", "RuntimeError"),
        ("worker_failed", "exit code 3"),
    ]


def test_a_failure_in_the_parent_still_reaps_every_worker(
    tmp_path: Path, ca_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []

    def failing_wait(sentinels: Any, timeout: float | None = None) -> Any:
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("the parent failed")
        return real_wait(sentinels, 1.0)  # the workers are running: do not wait for them

    monkeypatch.setattr(runner, "_wait", failing_wait)
    with pytest.raises(RuntimeError, match="the parent failed"):
        run_sources([spec("Sleeper", seconds="30")] * 3, WINDOW, workdir=tmp_path, environ=ca_env)
    assert len(calls) == 2
    assert not (tmp_path / "pages").exists()
    left = multiprocessing.active_children()
    for child in left:  # so that a failure here does not also fail the autouse check
        child.kill()
        child.join()
    assert left == []


def test_at_most_parallel_sources_run_at_once(tmp_path: Path, ca_env: dict[str, str]) -> None:
    records = [tmp_path / f"r{n}" for n in range(6)]
    runs = run_sources(
        [spec("Sleeper", seconds="2", record=str(path)) for path in records],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        parallel=4,
    ).runs
    assert [r.outcome for r in runs] == ["complete"] * 6
    spans = [tuple(map(float, path.read_text(encoding="utf-8").split())) for path in records]
    overlaps = [sum(a <= start < b for a, b in spans) for start, _ in spans]
    assert 2 <= max(overlaps) <= 4


def test_a_bad_trust_bundle_stops_before_any_worker_starts(tmp_path: Path) -> None:
    with pytest.raises(TrustBundleError) as caught:
        run_sources(
            [spec("Sleeper", seconds="0", record=str(tmp_path / "ran"))],
            WINDOW,
            workdir=tmp_path,
            environ={"REQUESTS_CA_BUNDLE": str(tmp_path / "missing.pem")},
        )
    assert caught.value.variable == "REQUESTS_CA_BUNDLE" and not (tmp_path / "ran").exists()
    assert not (tmp_path / "pages").exists()


GOOD = "tests.support.slow_adapters:Sleeper"


def late(source: str) -> AdapterSpec:
    """A source with the one request ``one``."""
    return AdapterSpec(source, "tests.support.slow_adapters:LatePage", (("seconds", "0"),))


def sleeper(record: Path, source: str = "good") -> AdapterSpec:
    return AdapterSpec(source, GOOD, (("seconds", "0"), ("record", str(record))))


def test_a_spec_that_cannot_be_imported_costs_only_its_own_source(
    tmp_path: Path, ca_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    ran = tmp_path / "ran"
    started: list[str] = []
    real_start = multiprocessing.context.SpawnProcess.start

    def start(self: BaseProcess) -> None:
        started.append(self.name)
        real_start(self)

    monkeypatch.setattr(multiprocessing.context.SpawnProcess, "start", start)
    broken = AdapterSpec("typo", "elections_calendar.sources.electiongiude:ElectionGuide")
    runs = run_sources([broken, sleeper(ran)], WINDOW, workdir=tmp_path, environ=ca_env).runs
    assert started == ["source-good"]  # no worker is spawned for a spec that does not load
    assert [(r.source, r.outcome, r.detail) for r in runs] == [
        ("typo", "worker_failed", "ModuleNotFoundError"),
        ("good", "complete", ""),
    ]
    assert (runs[0].raw.pages, runs[0].raw.unfinished) == ((), ())
    assert ran.exists()


def test_a_spec_that_cannot_be_constructed_costs_only_its_own_source(
    tmp_path: Path, ca_env: dict[str, str]
) -> None:
    ran = tmp_path / "ran"
    wrong = AdapterSpec("wrong", GOOD, (("nonsense", "1"),))  # Sleeper takes no such option
    missing = AdapterSpec("missing", "tests.support.slow_adapters:NoSuchAdapter")
    runs = run_sources([wrong, missing, sleeper(ran)], WINDOW, workdir=tmp_path, environ=ca_env).runs
    assert [(r.source, r.outcome, r.detail) for r in runs] == [
        ("wrong", "worker_failed", "TypeError"),
        ("missing", "worker_failed", "AttributeError"),
        ("good", "complete", ""),
    ]
    assert ran.exists()


def test_a_spec_whose_requests_raise_costs_only_its_own_source(
    tmp_path: Path, ca_env: dict[str, str]
) -> None:
    ran = tmp_path / "ran"
    bad = AdapterSpec("bad", "tests.support.slow_adapters:BadRequests", (("level", "9"),))
    runs = run_sources([sleeper(ran), bad], WINDOW, workdir=tmp_path, environ=ca_env).runs
    assert [(r.source, r.outcome, r.detail) for r in runs] == [
        ("good", "complete", ""),
        ("bad", "worker_failed", "ValueError"),
    ]
    assert ran.exists()


def test_a_source_that_cannot_start_costs_only_its_own_source(
    tmp_path: Path, ca_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    real_mkdir = Path.mkdir
    real_start = multiprocessing.context.SpawnProcess.start

    def mkdir(self: Path, *args: Any, **kwargs: Any) -> None:
        if self.name.endswith("-nodir"):
            raise PermissionError("no directory for you")
        real_mkdir(self, *args, **kwargs)

    def start(self: BaseProcess) -> None:
        if self.name == "source-nostart":
            raise RuntimeError("cannot spawn")
        real_start(self)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    monkeypatch.setattr(multiprocessing.context.SpawnProcess, "start", start)
    ran = tmp_path / "ran"
    specs = [late("nodir"), late("nostart"), sleeper(ran)]
    runs = run_sources(specs, WINDOW, workdir=tmp_path, environ=ca_env).runs
    assert [(r.source, r.outcome, r.detail) for r in runs] == [
        ("nodir", "worker_failed", "PermissionError"),
        ("nostart", "worker_failed", "RuntimeError"),
        ("good", "complete", ""),
    ]
    assert [[q.key for q in r.raw.unfinished] for r in runs] == [["one"], ["one"], []]
    assert ran.exists() and not (tmp_path / "pages").exists()


def test_an_unreadable_page_stays_unfinished_and_fails_the_source(
    tmp_path: Path, ca_env: dict[str, str]
) -> None:
    ran = tmp_path / "ran"
    corrupt = AdapterSpec("corrupt", "tests.support.slow_adapters:PartlyCorrupt")
    runs = run_sources([corrupt, sleeper(ran)], WINDOW, workdir=tmp_path, environ=ca_env).runs
    first, second = runs
    assert (first.outcome, first.detail) == ("worker_failed", "UnpicklingError")
    assert ([p.request.key for p in first.raw.pages], [q.key for q in first.raw.unfinished]) == (
        ["two"],
        ["one"],
    )
    assert second.outcome == "complete" and ran.exists()


def test_a_source_whose_directory_cannot_be_read_costs_only_its_own_source(
    tmp_path: Path, ca_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    real_collect = runner._Scrape._collect

    def collect(self: Any, slot: Any, now: float) -> Any:
        if slot.spec.source == "unreadable":
            raise OSError("cannot read")
        return real_collect(self, slot, now)

    monkeypatch.setattr(runner._Scrape, "_collect", collect)
    runs = run_sources(
        [late("unreadable"), sleeper(tmp_path / "y")],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
    ).runs
    assert [(r.source, r.outcome, r.detail) for r in runs] == [
        ("unreadable", "worker_failed", "OSError"),
        ("good", "complete", ""),
    ]
    assert (runs[0].raw.pages, [q.key for q in runs[0].raw.unfinished]) == ((), ["one"])
    assert not (tmp_path / "pages").exists()


def test_the_default_adapters_import_construct_and_pickle_their_window() -> None:
    assert [s.source for s in runner.DEFAULT_ADAPTERS] == [
        "electionguide",
        "osce",
        "wikipedia",
        "ndi",
        "aweb",
        "eisa",
        "ipu",
        "carter",
        "eeas",
    ]
    shipped = pickle.loads(pickle.dumps(WINDOW))
    for spec_ in runner.DEFAULT_ADAPTERS:
        adapter = runner._load(spec_)  # no options
        assert adapter.source == spec_.source
        requests = adapter.requests(WINDOW)
        assert requests and adapter.requests(shipped) == requests
        assert len({r.key for r in requests}) == len(requests)


@pytest.mark.parametrize("source", ["", "Wikipedia", "a b", "a/b", "..", "a.b", "é", "x\n"])
def test_an_adapter_spec_source_must_be_a_plain_name(source: str) -> None:
    with pytest.raises(ValueError, match="AdapterSpec.source"):
        AdapterSpec(source, "m:C")


@pytest.mark.parametrize("source", ["a", "electionguide", "my_source-2"])
def test_a_plain_source_name_is_accepted(source: str) -> None:
    assert AdapterSpec(source, "m:C").source == source


class _Unpicklable(str):
    def __reduce__(self) -> Any:
        raise TypeError("this option cannot be pickled")


def test_a_worker_payload_that_cannot_be_pickled_creates_no_child(
    tmp_path: Path, ca_env: dict[str, str]
) -> None:
    # On Windows, spawn creates the child before it pickles the payload; a failed pickle then
    # orphans that child onto the next worker's pipe handle. The payload is pickled first.
    record = tmp_path / "good-ran"
    bad = AdapterSpec("bad", "tests.support.slow_adapters:LatePage", (("seconds", _Unpicklable("0")),))
    good = AdapterSpec("good", GOOD, (("seconds", "1"), ("record", str(record))))
    runs = run_sources([bad, good], WINDOW, workdir=tmp_path, environ=ca_env).runs
    assert [(r.source, r.outcome, r.detail) for r in runs] == [
        ("bad", "worker_failed", "TypeError"),
        ("good", "complete", ""),
    ]
    written = record.read_text(encoding="utf-8")
    time.sleep(3)  # a stray worker would write (or rewrite) its marker in this time
    assert record.read_text(encoding="utf-8") == written


def test_importlinter_adapters_contract_lists_every_default_adapter() -> None:
    ini = configparser.ConfigParser()
    ini.read(Path(__file__).parents[2] / "importlinter.ini", encoding="utf8")
    modules = ini["importlinter:contract:adapters"]["modules"].split()
    assert modules
    assert set(modules) == {s.target.split(":")[0] for s in runner.DEFAULT_ADAPTERS}


def test_every_adapter_module_is_registered() -> None:
    root = Path(__file__).parents[2]
    on_disk = {
        f"elections_calendar.sources.{p.stem}"
        for p in (root / "elections_calendar" / "sources").glob("*.py")
        if p.stem not in {"__init__", "base", "tables"}
    }
    ini = configparser.ConfigParser()
    ini.read(root / "importlinter.ini", encoding="utf8")
    linted = set(ini["importlinter:contract:adapters"]["modules"].split())
    assert on_disk == linted
    assert on_disk == {s.target.split(":")[0] for s in runner.DEFAULT_ADAPTERS}


def test_a_chained_source_cut_mid_chain(
    server: TestServer, ca_env: dict[str, str], tmp_path: Path
) -> None:
    """Only the first page is named up front, so the runner keeps a chained page it received
    and has nothing unfinished; the adapter's own ``missing_pages`` reports the one cut off."""
    a, b = server.route("/a", Reply(body=b"a")), server.route("/b", Reply(body=b"b"))
    c = server.route("/c", Reply(body=b"c", header_drip=0.5))
    urls = f"{a},{b},{c}"
    run = run_sources(
        [spec("Chain", urls=urls)],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        source_deadline_s=2,
        grace_s=2,
    )
    (r,) = run.runs
    assert r.outcome == "deadline"
    assert [p.request.key for p in r.raw.pages] == ["one", "two"]
    assert r.raw.unfinished == ()
    assert missing_pages(Chain(urls).expected(r.raw.pages), r.raw) == [
        Reason("pagination_incomplete", "three was not fetched")
    ]
