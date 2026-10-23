"""The artifact's loader helpers, the copy, and the validators that Task 6 split or renamed."""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from elections_calendar.ci.artifact import (
    Artifact,
    ArtifactError,
    copy_repository_files,
    load_artifact,
    served_link_problems,
)
from elections_calendar.feed import serving_fields
from elections_calendar.model import RecordError
from elections_calendar.snapshots import load_baseline
from elections_calendar.validate import feed_content_problems, validate_feed
from tests.support.artifact import osce_artifact, rewrite_feed
from tests.support.git_repos import V1_FEED
from tests.support.repo import NOW

SOURCES = ("osce",)
SHA = "1" * 40


def loaded(tmp_path: Path, outcome: str = "published") -> Artifact:
    empty = tmp_path / "empty"
    empty.mkdir(exist_ok=True)
    root = osce_artifact(tmp_path / "artifact", repo=empty, code_sha=SHA, outcome=outcome)
    return load_artifact(root, code_sha=SHA, wall_clock=NOW, sources=SOURCES)


def test_the_artifact_is_described_by_its_manifest(tmp_path: Path) -> None:
    artifact = loaded(tmp_path)
    assert artifact.outcome == "published"
    assert artifact.repository_files == tuple(sorted(artifact.repository_files))
    assert set(artifact.repository_files) == {
        "HEALTH.md",
        "elections.json",
        "status.json",
        "data/sources/osce/baseline.json",
        "data/sources/osce/candidate.json",
        "data/sources/osce/health_state.json",
    }
    manifest = (artifact.root / "manifest.json").read_bytes()
    assert artifact.manifest_sha256 == hashlib.sha256(manifest).hexdigest()
    assert artifact.status["code_sha"] == SHA
    assert artifact.verdict["dry_run"] is False


def test_a_naive_wall_clock_raises(tmp_path: Path) -> None:
    artifact = loaded(tmp_path)
    with pytest.raises(ValueError, match="timezone-aware"):
        load_artifact(
            artifact.root, code_sha=SHA, wall_clock=datetime(2026, 10, 19, 12), sources=SOURCES
        )


def test_the_copy_adds_and_replaces_and_never_deletes(tmp_path: Path) -> None:
    artifact = loaded(tmp_path)
    repo = tmp_path / "repo"
    (repo / "data" / "sources" / "osce").mkdir(parents=True)
    (repo / "data" / "sources" / "osce" / "extra.txt").write_bytes(b"kept")
    (repo / "elections.json").write_bytes(b"old")
    only = copy_repository_files(artifact, repo, only=lambda path: path.startswith("data/"))
    assert only == tuple(p for p in artifact.repository_files if p.startswith("data/"))
    assert (repo / "elections.json").read_bytes() == b"old"  # not accepted by `only`
    everything = copy_repository_files(artifact, repo)
    assert everything == artifact.repository_files
    for path in everything:
        assert (repo / path).read_bytes() == (artifact.root / path).read_bytes()
    assert (repo / "data" / "sources" / "osce" / "extra.txt").read_bytes() == b"kept"
    assert not (repo / "verdict.json").exists()
    assert not list(repo.rglob("*.tmp"))


def test_a_failed_validation_has_no_served_link_to_check(tmp_path: Path) -> None:
    artifact = loaded(tmp_path, "validation_failed")

    def never(source: str) -> bytes | None:
        raise AssertionError("a failed validation reads no baseline")

    assert artifact.outcome == "validation_failed"
    assert served_link_problems(artifact, never) == []


def test_a_failed_artifact_with_a_source_file_cannot_load(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    root = osce_artifact(tmp_path / "a", repo=empty, code_sha=SHA, outcome="validation_failed")
    rewrite_feed(root, V1_FEED.read_bytes())
    with pytest.raises(ArtifactError, match="a failed validation carries a feed"):
        load_artifact(root, code_sha=SHA, wall_clock=NOW, sources=SOURCES)


def test_feed_content_problems_is_validate_feed_without_the_served_checks(tmp_path: Path) -> None:
    feed = (loaded(tmp_path).root / "elections.json").read_bytes()
    assert feed_content_problems(feed, wall_clock=NOW) == ()
    served_only = validate_feed(feed, served=[], wall_clock=NOW)
    assert served_only and all(p.startswith("served: ") for p in served_only)
    late = json.loads(feed)
    late["published_at"] = "2026-10-19T13:00:00Z"
    stale = (json.dumps(late) + "\n").encode()
    content = feed_content_problems(stale, wall_clock=NOW)
    assert content and content[0].startswith("timestamp: ")
    assert validate_feed(stale, served=[], wall_clock=NOW)[: len(content)] == content


def test_content_problems_of_bytes_that_are_not_json_are_the_json_problem_alone() -> None:
    assert feed_content_problems(b"{", wall_clock=NOW) == ("json: not UTF-8 JSON",)
    assert feed_content_problems(b"\xff", wall_clock=NOW) == ("json: not UTF-8 JSON",)
    assert validate_feed(b"{", served=[], wall_clock=NOW) == ("json: not UTF-8 JSON",)
    with pytest.raises(ValueError, match="timezone-aware"):
        feed_content_problems(b"{", wall_clock=datetime(2026, 10, 19, 12))


def test_load_baseline_refuses_a_baseline_of_another_source(tmp_path: Path) -> None:
    artifact = loaded(tmp_path)
    path = artifact.root / "data" / "sources" / "osce" / "baseline.json"
    assert load_baseline(path, source="osce") == load_baseline(path)
    with pytest.raises(RecordError) as caught:
        load_baseline(path, source="ipu")
    assert str(caught.value) == "baseline.json is corrupt: it is of 'osce', not 'ipu'"
    assert load_baseline(tmp_path / "missing.json", source="ipu") is None


def test_serving_fields_of_nothing_and_of_a_feed(tmp_path: Path) -> None:
    assert set(serving_fields(None).values()) == {None}
    artifact = loaded(tmp_path)
    feed = (artifact.root / "elections.json").read_bytes()
    found = serving_fields(feed)
    assert found["serving_feed_sha256"] == hashlib.sha256(feed).hexdigest()
    assert found["serving_content_id"] == json.loads(feed)["content_id"]
    assert found == {key: artifact.status[key] for key in found}
    legacy = serving_fields(V1_FEED.read_bytes())  # v1's file is not even JSON
    assert legacy["serving_feed_sha256"] == hashlib.sha256(V1_FEED.read_bytes()).hexdigest()
    assert legacy["serving_content_id"] is None
