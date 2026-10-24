"""``ci adopt``: the first baselines come from one approved artifact and nothing else (P124)."""

import hashlib
import json
from pathlib import Path

import pytest

from elections_calendar.ci.__main__ import main
from elections_calendar.model import stored_json
from tests.support.artifact import fixture_artifact, rewrite, rewrite_feed

SHA = "4" * 40


def digest(root: Path) -> str:
    return hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()


def adopt(root: Path, repo: Path, approved: str | None = None) -> int:
    return main(
        ["adopt", "--artifact", str(root), "--manifest-sha256", approved or digest(root)]
        + ["--repo", str(repo)]
    )


def files_under(repo: Path) -> list[str]:
    return sorted(p.relative_to(repo).as_posix() for p in repo.rglob("*") if p.is_file())


def test_adopt_takes_only_the_approved_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = fixture_artifact(tmp_path / "artifact", code_sha=SHA)
    repo = tmp_path / "repo"
    repo.mkdir()
    assert adopt(root, repo, "0" * 64) == 1
    assert capsys.readouterr().err == (
        f"the artifact is not the approved one: its manifest is {digest(root)}\n"
    )
    assert adopt(root, repo, "XYZ") == 2
    assert files_under(repo) == []

    capsys.readouterr()
    assert adopt(root, repo) == 0
    expected = sorted(
        p.relative_to(root).as_posix()
        for p in (root / "data" / "sources").rglob("*")
        if p.is_file()
    )
    assert len(expected) == 27
    assert files_under(repo) == expected  # elections.json, status.json and HEALTH.md stay out
    for path in expected:
        assert (repo / path).read_bytes() == (root / path).read_bytes()
    lines = capsys.readouterr().out.splitlines()
    assert lines[:-1] == expected
    assert lines[-1] == f"adopted 27 files from the run of {SHA} (manifest {digest(root)})"

    assert adopt(root, repo) == 1
    assert capsys.readouterr().err == (
        "data/sources already exists: the first baselines are adopted once\n"
    )


def test_adopt_refuses_a_dry_run_and_a_failed_validation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dry = fixture_artifact(tmp_path / "dry", code_sha=SHA)
    verdict = json.loads((dry / "verdict.json").read_text(encoding="utf-8"))
    verdict["dry_run"] = True
    rewrite(dry, "verdict.json", stored_json(verdict))
    repo = tmp_path / "repo"
    repo.mkdir()
    assert adopt(dry, repo) == 1
    assert capsys.readouterr().err == "a dry-run artifact is never published\n"

    failed = fixture_artifact(tmp_path / "failed", code_sha=SHA, outcome="validation_failed")
    assert adopt(failed, repo) == 1
    assert capsys.readouterr().err == "only a published artifact has baselines\n"
    assert files_under(repo) == []


def test_adopt_refuses_a_feed_that_serves_another_snapshot(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = fixture_artifact(tmp_path / "artifact", code_sha=SHA)
    doc = json.loads((root / "elections.json").read_text(encoding="utf-8"))
    (osce,) = [e for e in doc["source_health"] if e["source"] == "osce"]
    held = osce["snapshot"]["served_snapshot_id"]
    osce["snapshot"]["served_snapshot_id"] = "0" * 64
    rewrite_feed(root, (json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode())
    repo = tmp_path / "repo"
    repo.mkdir()
    assert adopt(root, repo) == 1
    assert capsys.readouterr().err == (
        f"osce: the feed serves snapshot {'0' * 64}, the committed baseline is {held}\n"
    )
    assert files_under(repo) == []


def test_adopt_refuses_an_impossible_attempt_at(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = fixture_artifact(tmp_path / "artifact", code_sha=SHA)
    status = json.loads((root / "status.json").read_text(encoding="utf-8"))
    status["attempt_at"] = "2026-13-45T25:61:61Z"  # matches the schema's pattern, is no moment
    rewrite(root, "status.json", stored_json(status))
    repo = tmp_path / "repo"
    repo.mkdir()
    assert adopt(root, repo) == 1
    assert capsys.readouterr().err == "status.json is invalid: attempt_at\n"
    assert files_under(repo) == []
