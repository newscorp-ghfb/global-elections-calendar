"""Offline inputs and the commit step for the pipeline tests (Plan 4 Task 8)."""

import json
import shutil
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from elections_calendar.model import FetchOutcome
from elections_calendar.pipeline import RunConfig
from elections_calendar.runner import AdapterSpec
from elections_calendar.sources.osce import Osce
from elections_calendar.window import window_for
from tests.support.fixtures import FIXTURES

NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)
OSCE = AdapterSpec("osce", "elections_calendar.sources.osce:Osce")
OSCE_FETCHED = datetime(2026, 10, 18, 11, 18, 37, tzinfo=UTC)
OSCE_FILE = FIXTURES / "osce" / "2026-10-18" / "elections.html"

Page = tuple[str, Path, datetime, FetchOutcome]


def osce_url() -> str:
    return Osce().requests(window_for(NOW))[0].url


def commit(out: Path, repo: Path) -> None:
    """Copy the repository files of ``out`` into ``repo``, as Plan 5's publish job will."""
    for name in ("elections.json", "status.json", "HEALTH.md"):
        if (out / name).exists():
            shutil.copyfile(out / name, repo / name)
    sources = out / "data" / "sources"
    for path in sorted(sources.rglob("*")) if sources.exists() else []:
        if path.is_file():
            target = repo / path.relative_to(out)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


def offline_dir(tmp_path: Path, pages: Sequence[Page], name: str = "offline") -> Path:
    """Write ``pages.json`` and one body file per page: the fixture for ``ok``, empty otherwise."""
    directory = tmp_path / name
    directory.mkdir(parents=True)
    entries = []
    for number, (url, fixture, fetched_at, outcome) in enumerate(pages):
        body = fixture.read_bytes() if outcome == "ok" else b""
        (directory / f"{number}.body").write_bytes(body)
        entries.append(
            {
                "url": url,
                "file": f"{number}.body",
                "fetched_at": fetched_at.isoformat(),
                "content_type": "text/html; charset=utf-8",
                "status": 200 if outcome == "ok" else None,
                "outcome": outcome,
            }
        )
    (directory / "pages.json").write_text(json.dumps({"pages": entries}), encoding="utf-8")
    return directory


def osce_offline(
    tmp_path: Path,
    outcome: FetchOutcome = "ok",
    fetched_at: datetime = OSCE_FETCHED,
    name: str = "offline",
) -> Path:
    return offline_dir(tmp_path, [(osce_url(), OSCE_FILE, fetched_at, outcome)], name)


def config(
    tmp_path: Path,
    offline: Path | None,
    *,
    out: str = "out",
    now: datetime = NOW,
    environ: Mapping[str, str] | None = None,
    specs: tuple[AdapterSpec, ...] = (OSCE,),
    timer: Callable[[], float] = lambda: 0.0,
) -> RunConfig:
    """A run of ``specs`` into ``tmp_path / out`` against ``tmp_path / "repo"`` (made if absent)."""
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    return RunConfig(
        out=tmp_path / out,
        repo=repo,
        now=now,
        wall_clock=now,
        environ={} if environ is None else environ,
        offline=offline,
        specs=specs,
        timer=timer,
    )
