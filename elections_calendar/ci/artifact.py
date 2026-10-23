"""What the publish job accepts from the scrape job's artifact, and how it copies it (P119).

The scrape job parses untrusted pages, so its artifact is untrusted input to a job that can
write to ``main``. ``load_artifact`` re-checks the content with the existing validators, builds
nothing, and raises ``ArtifactError`` at the first problem.
"""

import hashlib
import json
import re
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal

from elections_calendar.ci.manifest import ManifestError, read_manifest
from elections_calendar.feed import serving_fields
from elections_calendar.health import load_health_state
from elections_calendar.model import SOURCE_ORDER, RecordError
from elections_calendar.publish import write_atomic
from elections_calendar.snapshots import load_baseline
from elections_calendar.validate import feed_content_problems, validate_status

REPOSITORY_NAMES: Final = ("elections.json", "status.json", "HEALTH.md")
SOURCE_FILES: Final = ("baseline.json", "candidate.json", "health_state.json")
ARTIFACT_ONLY: Final = ("verdict.json", "attention_full.json", "dispositions.json")
REPOSITORY_FILE_MAX_BYTES: Final = 10 * 1024 * 1024
_REQUIRED: Final = ("status.json", "HEALTH.md", "verdict.json")
_SOURCES_DIR: Final = "data/sources/"
_DIGEST: Final = re.compile(r"[0-9a-f]{64}")
_SHOWN: Final = 120


class ArtifactError(ValueError):
    """The artifact is not one the publish job may commit."""


@dataclass(frozen=True, slots=True)
class Artifact:
    root: Path
    outcome: Literal["published", "validation_failed"]
    repository_files: tuple[str, ...]  # sorted posix paths, the files to commit
    status: Mapping[str, Any]
    verdict: Mapping[str, Any]
    manifest_sha256: str


def _repository_path(path: str, sources: Sequence[str]) -> bool:
    if path in REPOSITORY_NAMES:
        return True
    parts = path.split("/")
    return (
        len(parts) == 4
        and parts[0] == "data"
        and parts[1] == "sources"
        and parts[2] in sources
        and parts[3] in SOURCE_FILES
    )


def _file(root: Path, path: str) -> Path:
    return root.joinpath(*path.split("/"))


def _json_object(data: bytes) -> dict[str, Any] | None:
    """The JSON object in ``data``, or None for anything else."""
    try:
        loaded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _check_verdict(raw: bytes, outcome: str) -> dict[str, Any]:
    verdict = _json_object(raw)
    if verdict is None or verdict.get("verdict") not in ("green", "red"):
        raise ArtifactError("verdict.json is malformed")
    if verdict.get("outcome") != outcome:
        raise ArtifactError("verdict.json and status.json disagree")
    if verdict.get("dry_run") is not False:
        raise ArtifactError("a dry-run artifact is never published")
    return verdict


def _check_sizes(root: Path, repository: Sequence[str]) -> None:
    for path in repository:
        if _file(root, path).stat().st_size > REPOSITORY_FILE_MAX_BYTES:
            raise ArtifactError(f"{path} is over {REPOSITORY_FILE_MAX_BYTES} bytes")
    if "HEALTH.md" in repository:
        try:
            _file(root, "HEALTH.md").read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            raise ArtifactError("HEALTH.md is not UTF-8") from None


def _check_published(
    root: Path,
    status: Mapping[str, Any],
    present: set[str],
    sources: Sequence[str],
    wall_clock: datetime,
) -> None:
    if "elections.json" not in present:
        raise ArtifactError("elections.json does not match status.json")
    feed = _file(root, "elections.json").read_bytes()
    if any(status.get(key) != value for key, value in serving_fields(feed).items()):
        raise ArtifactError("elections.json does not match status.json")
    problems = feed_content_problems(feed, wall_clock=wall_clock)
    if problems:
        raise ArtifactError(f"elections.json is invalid: {problems[0]}")
    for source in sources:
        folder = f"{_SOURCES_DIR}{source}/"
        if folder + "candidate.json" not in present or folder + "health_state.json" not in present:
            raise ArtifactError(f"data/sources/{source} is incomplete")


def _check_saved_state(
    root: Path, status: Mapping[str, Any], present: set[str], sources: Sequence[str]
) -> None:
    """P5A-01: what the repository will hold must load with the loaders that read it back."""
    try:
        attempt_at = datetime.fromisoformat(status["attempt_at"])
    except ValueError:  # the schema's pattern admits dates such as 2026-02-30
        raise ArtifactError("status.json is invalid: attempt_at") from None
    for source in sources:
        folder = f"{_SOURCES_DIR}{source}/"
        if folder + "baseline.json" in present:
            try:
                load_baseline(_file(root, folder + "baseline.json"), source=source)
            except RecordError as exc:
                raise ArtifactError(f"{folder}baseline.json: {exc}") from None
        state = load_health_state(_file(root, folder + "health_state.json"), now=attempt_at)
        if state.problem is not None:
            raise ArtifactError(f"{folder}health_state.json is corrupt: {state.problem}")
        candidate = _json_object(_file(root, folder + "candidate.json").read_bytes())
        snapshot_id = None if candidate is None else candidate.get("snapshot_id")
        if (
            candidate is None
            or candidate.get("source") != source
            or not isinstance(snapshot_id, str)
            or not _DIGEST.fullmatch(snapshot_id)
        ):
            raise ArtifactError(f"{folder}candidate.json is malformed")


def load_artifact(
    root: Path,
    *,
    code_sha: str | None,
    wall_clock: datetime,
    sources: Sequence[str] = SOURCE_ORDER,
) -> Artifact:
    """The artifact in ``root`` after the eleven checks of P119, or ``ArtifactError``."""
    try:  # 1
        manifest = read_manifest(root)
    except ManifestError as exc:
        raise ArtifactError(str(exc)) from None
    present = set(manifest)
    for path in manifest:  # 2
        if not (
            _repository_path(path, sources) or path in ARTIFACT_ONLY or path.startswith("rejected/")
        ):
            raise ArtifactError(f"an unexpected file: {repr(path)[:_SHOWN]}")
    for name in _REQUIRED:  # 3
        if name not in present:
            raise ArtifactError(f"the artifact has no {name}")
    status_bytes = _file(root, "status.json").read_bytes()
    problems = validate_status(status_bytes)  # 4
    if problems:
        raise ArtifactError(f"status.json is invalid: {problems[0]}")
    status: dict[str, Any] = json.loads(status_bytes.decode("utf-8"))
    outcome = status["outcome"]  # 5
    if outcome not in ("published", "validation_failed"):
        raise ArtifactError(f"status.json's outcome is {outcome!r}")
    verdict = _check_verdict(_file(root, "verdict.json").read_bytes(), outcome)  # 6
    if code_sha is not None and status["code_sha"] != code_sha:  # 7
        raise ArtifactError(f"status.json is from {status['code_sha']}, not {code_sha}")
    if [s["source"] for s in status["sources"]] != list(sources):  # 8
        raise ArtifactError("status.json lists other sources")
    repository = sorted(p for p in present if _repository_path(p, sources))
    _check_sizes(root, repository)  # 9
    if outcome == "published":  # 10 and 11
        _check_published(root, status, present, sources, wall_clock)
        _check_saved_state(root, status, present, sources)
    elif "elections.json" in present or any(p.startswith(_SOURCES_DIR) for p in present):
        raise ArtifactError("a failed validation carries a feed")
    return Artifact(
        root=root,
        outcome=outcome,
        repository_files=tuple(repository),
        status=status,
        verdict=verdict,
        manifest_sha256=hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
    )


def _served_id(entry: Any) -> str | None:
    snapshot = entry.get("snapshot") if isinstance(entry, dict) else None
    served = snapshot.get("served_snapshot_id") if isinstance(snapshot, dict) else None
    return served if isinstance(served, str) else None


def served_link_problems(
    artifact: Artifact, committed_baseline: Callable[[str], bytes | None]
) -> list[str]:
    """Where a source's served snapshot is not the baseline the repository will hold (P5A-01).

    Each baseline is the artifact's, else the committed one, and is loaded through
    ``load_baseline(..., source=)`` wherever its bytes come from (R2-01). A source the feed
    does not serve is never loaded: a corrupt baseline of it stays and is reported (P94).
    """
    if artifact.outcome != "published":
        return []
    feed = json.loads((artifact.root / "elections.json").read_bytes().decode("utf-8"))
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as scratch:
        for entry in feed["source_health"]:
            served = _served_id(entry)
            if served is None:
                continue
            source = entry["source"]
            relative = f"{_SOURCES_DIR}{source}/baseline.json"
            if relative in artifact.repository_files:
                path = _file(artifact.root, relative)
            else:
                data = committed_baseline(source)
                if data is None:
                    problems.append(
                        f"{source}: the feed serves snapshot {served}, "
                        "but no baseline is committed"
                    )
                    continue
                path = Path(scratch) / f"{source}.json"
                path.write_bytes(data)
            try:
                baseline = load_baseline(path, source=source)
            except RecordError as exc:
                problems.append(
                    f"{source}: the feed serves snapshot {served}, "
                    f"but its baseline is corrupt: {exc}"
                )
                continue
            if baseline is None or baseline.snapshot.snapshot_id != served:
                other = None if baseline is None else baseline.snapshot.snapshot_id
                problems.append(
                    f"{source}: the feed serves snapshot {served}, "
                    f"the committed baseline is {other}"
                )
    return problems


def copy_repository_files(
    artifact: Artifact, repo: Path, *, only: Callable[[str], bool] = lambda path: True
) -> tuple[str, ...]:
    """Write each repository file that ``only`` accepts into ``repo`` with the artifact's bytes.

    Returns the paths written, sorted. It adds and replaces; it never deletes.
    """
    copied = [path for path in artifact.repository_files if only(path)]
    for path in copied:
        write_atomic(_file(repo, path), _file(artifact.root, path).read_bytes())
    return tuple(copied)
