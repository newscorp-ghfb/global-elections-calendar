"""The per-source runner (spec §8, C15): hard deadlines over real spawned workers.

Workers are real child processes running the adapters in
``tests/support/slow_adapters.py``; the only server is the local HTTPS one.
"""

import multiprocessing
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
from elections_calendar.runner import AdapterSpec, run_sources
from elections_calendar.window import window_for
from tests.support.http_server import Reply, TestServer

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
        [spec("StallMidWrite")],
        WINDOW,
        workdir=tmp_path,
        environ=ca_env,
        source_deadline_s=3,
        grace_s=2,
    ).runs
    assert (r.outcome, r.raw.pages) == ("deadline", ())
    assert [q.key for q in r.raw.unfinished] == ["one"]
    assert time.monotonic() - start < 3 + 2 + 3


def test_deadlines_that_expire_together_are_cut_together(
    tmp_path: Path, ca_env: dict[str, str]
) -> None:  # review P2-03, A04
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
    assert time.monotonic() - start < 2 + 2 + 3  # one grace period, not three


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
