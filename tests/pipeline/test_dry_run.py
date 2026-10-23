"""``--dry-run``: a live run that publishes nothing and spends at most 40 requests (P116, R30)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from elections_calendar import __main__ as cli
from elections_calendar import pipeline
from elections_calendar.pipeline import RunConfig, _fetch_offline, load_offline
from elections_calendar.runner import ScrapeRun
from elections_calendar.window import Window
from tests.support.fixtures import FIXTURES

NOW = "2026-10-19T12:00:00Z"
TREE_NOTE = b"a committed file the run must not touch\n"


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def fixture_run(window: Window) -> ScrapeRun:
    config = RunConfig(
        out=Path("unused"),
        repo=Path("unused"),
        now=datetime(2026, 10, 19, 12, tzinfo=UTC),
        wall_clock=datetime(2026, 10, 19, 12, tzinfo=UTC),
        environ={},
    )
    return _fetch_offline(config, window, load_offline(FIXTURES))


def load(out: Path, name: str) -> Any:
    return json.loads((out / name).read_text(encoding="utf-8"))


def test_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[tuple[int, float]] = []
    workdirs: list[Path] = []

    def fake(specs: Any, window: Window, **kwargs: Any) -> ScrapeRun:
        budget = kwargs["budget"]
        seen.append((budget.limit, kwargs["scrape_deadline_s"]))
        workdirs.append(Path(kwargs["workdir"]))
        assert workdirs[0].is_dir()
        for _ in range(16):
            assert budget.take()
        return fixture_run(window)

    monkeypatch.setattr(pipeline, "run_sources", fake)
    workspace = tmp_path / "workspace"
    repo = workspace / "repo"
    repo.mkdir(parents=True)
    (repo / "elections.json").write_bytes(TREE_NOTE)
    before = tree(repo)
    out = workspace / "out"
    args = ["--live", "--dry-run", "--now", NOW, "--out", str(out), "--repo", str(repo)]
    assert cli.main(args) == 0
    assert seen == [(40, 480)]
    assert not workdirs[0].exists()
    verdict = load(out, "verdict.json")
    assert (verdict["dry_run"], verdict["requests"]) == (True, 16)
    health = (out / "HEALTH.md").read_text(encoding="utf-8").splitlines()
    assert health[0] == "# Elections calendar health"
    assert health[2] == "**Dry run:** 16 of 40 requests. Nothing here is published."
    assert (out / "manifest.json").is_file()
    assert tree(repo) == before
    assert sorted(p.name for p in workspace.iterdir()) == ["out", "repo"]
    assert capsys.readouterr().err == ""


def test_dry_run_removes_its_work_directory_even_when_the_scrape_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workdirs: list[Path] = []

    def boom(specs: Any, window: Window, **kwargs: Any) -> ScrapeRun:
        workdirs.append(Path(kwargs["workdir"]))
        kwargs["budget"].take()
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "run_sources", boom)
    (tmp_path / "repo").mkdir()
    args = ["--live", "--dry-run", "--now", NOW, "--out", str(tmp_path / "out")]
    args += ["--repo", str(tmp_path / "repo")]
    with pytest.raises(RuntimeError, match="boom"):
        cli.main(args)
    (workdir,) = workdirs
    assert not workdir.exists()


def test_dry_run_needs_live(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    other = tmp_path / "other"
    argv = ["--offline", str(FIXTURES), "--dry-run", "--out", str(other)]
    assert cli.main(argv) == 2
    assert capsys.readouterr().err == "--dry-run needs --live\n"
    assert not other.exists()


def test_a_run_that_is_not_a_dry_run_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    argv = ["--offline", str(FIXTURES), "--now", NOW, "--out", str(out), "--repo", str(repo)]
    assert cli.main(argv) == 0
    verdict = load(out, "verdict.json")
    assert (verdict["dry_run"], verdict["requests"]) == (False, None)
    assert "Dry run" not in (out / "HEALTH.md").read_text(encoding="utf-8")
