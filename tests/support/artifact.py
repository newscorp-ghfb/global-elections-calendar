"""Real artifacts for the publish tests: runs of the pipeline, copied and edited (Plan 5a Task 6).

``osce_artifact`` is an OSCE-only run (well under a second); tests that call ``publish`` directly
use it with ``sources=("osce",)``. ``fixture_artifact`` is the nine-source run on the fixtures
(about 3.4 s), built once per session and outcome and copied; tests that go through the command
use it, because the command checks all nine sources.
"""

import atexit
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

from elections_calendar import pipeline
from elections_calendar.feed import serving_fields
from elections_calendar.model import stored_json
from elections_calendar.pipeline import RunConfig, run
from elections_calendar.publish import write_manifest
from tests.support.fixtures import FIXTURES
from tests.support.git_repos import V1_FEED
from tests.support.repo import NOW, OSCE, osce_offline

FORCED_PROBLEMS = ("size: 1 bytes is over 2000000",)  # as Plan 4's test_validation_failure_writes_no_feed
_CACHE: dict[str, Path] = {}


def _environ(code_sha: str) -> dict[str, str]:
    return {"GITHUB_SHA": code_sha, "GITHUB_RUN_ID": "7", "GITHUB_EVENT_NAME": "schedule"}


def _run(config: RunConfig, outcome: str) -> None:
    if outcome == "validation_failed":
        with mock.patch.object(pipeline, "validate_feed", lambda *a, **k: FORCED_PROBLEMS):
            result = run(config)
    else:
        result = run(config)
    assert result.outcome == outcome


def osce_artifact(
    dest: Path, *, repo: Path, code_sha: str, outcome: str = "published", offline: Path | None = None
) -> Path:
    """The artifact of an OSCE-only run against ``repo``, into ``dest``."""
    pages = offline if offline is not None else osce_offline(dest.parent, name=f"{dest.name}-pages")
    config = RunConfig(
        out=dest,
        repo=repo,
        now=NOW,
        wall_clock=NOW,
        environ=_environ(code_sha),
        offline=pages,
        specs=(OSCE,),
        timer=lambda: 0.0,
    )
    _run(config, outcome)
    return dest


def rewrite(root: Path, path: str, data: bytes | None) -> None:
    """Write ``path`` under ``root`` (``None`` deletes it) and rewrite the manifest."""
    target = root.joinpath(*path.split("/"))
    if data is None:
        target.unlink()
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    write_manifest(root)


def add_file(root: Path, path: str, data: bytes) -> None:
    rewrite(root, path, data)


def rewrite_feed(root: Path, data: bytes) -> None:
    """Write ``elections.json`` and make ``status.json`` describe it, so the artifact agrees."""
    (root / "elections.json").write_bytes(data)
    status: dict[str, Any] = json.loads((root / "status.json").read_text(encoding="utf-8"))
    status.update(serving_fields(data))
    rewrite(root, "status.json", stored_json(status))


def _built(outcome: str) -> Path:
    if outcome not in _CACHE:
        base = Path(tempfile.mkdtemp(prefix="nm-fixture-artifact-"))
        atexit.register(shutil.rmtree, base, ignore_errors=True)
        repo = base / "repo"
        repo.mkdir()
        if outcome == "validation_failed":  # the retained feed the failed run names
            shutil.copyfile(V1_FEED, repo / "elections.json")
        config = RunConfig(
            out=base / "out",
            repo=repo,
            now=NOW,
            wall_clock=NOW,
            environ=_environ("0" * 40),
            offline=FIXTURES,
            timer=lambda: 0.0,
        )
        _run(config, outcome)
        _CACHE[outcome] = base / "out"
    return _CACHE[outcome]


def fixture_artifact(dest: Path, *, code_sha: str, outcome: str = "published") -> Path:
    """A copy of the nine-source run on the fixtures, from ``code_sha``."""
    shutil.copytree(_built(outcome), dest)
    status: dict[str, Any] = json.loads((dest / "status.json").read_text(encoding="utf-8"))
    status["code_sha"] = code_sha
    rewrite(dest, "status.json", stored_json(status))
    return dest
