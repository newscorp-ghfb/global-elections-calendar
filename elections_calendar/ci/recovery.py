"""Recovery pairs and the republication of a recorded feed (spec §11.5, §15 step 7; P122, P123).

A recovery pair is a ``main`` commit and the SHA-256 of its ``elections.json`` blob. It is
recorded in ``RELEASES.md`` or in that commit's own ``status.json``. Nothing here writes a file or
commits: ``republish`` returns the bytes and ``scripts/republish.py`` writes them. Blobs are read
with ``git cat-file blob``, never from the working tree.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal

from elections_calendar.ci.git import Git
from elections_calendar.feed import Attempt, status_doc
from elections_calendar.model import _utc_iso, stored_json
from elections_calendar.validate import republished_problems, validate_status

# PAUSE_PUBLISHING is not excluded: pre-v2 has none, so the restore removes it (P5A-02)
ROLLBACK_EXCLUDES: Final = (
    ":(exclude)elections.json",
    ":(exclude)status.json",
    ":(exclude)HEALTH.md",
    ":(exclude)data/sources",
    ":(exclude)RELEASES.md",
    ":(exclude).gitattributes",
)

_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_DIGEST: Final = re.compile(r"[0-9a-f]{64}")
_PAIRS_HEADING: Final = "## Recovery pairs"
_SEPARATOR: Final = re.compile(r":?-+:?")


class RecoveryError(ValueError):
    """A recovery pair cannot be used, or the feed it names cannot be republished."""


@dataclass(frozen=True, slots=True)
class RecoveryPair:
    commit: str
    sha256: str
    recorded_in: Literal["RELEASES.md", "status.json"]


def _cell(cell: str, pattern: re.Pattern[str]) -> str | None:
    """The value of a table cell that is ``pattern``, optionally in backticks, else None."""
    if len(cell) >= 2 and cell.startswith("`") and cell.endswith("`"):
        cell = cell[1:-1]
    return cell if pattern.fullmatch(cell) else None


def releases_pairs(text: str) -> dict[str, str]:
    """The recovery pairs of ``RELEASES.md`` (commit to digest); a malformed row raises."""
    pairs: dict[str, str] = {}
    in_section = False
    seen_header = False
    number = 0
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("## "):
            in_section = line == _PAIRS_HEADING
            seen_header = False
            continue
        if not in_section or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.removeprefix("|").removesuffix("|").split("|")]
        if not seen_header:  # the table's header row
            seen_header = True
            continue
        if all(_SEPARATOR.fullmatch(c) for c in cells):
            continue
        number += 1
        commit = _cell(cells[1], _COMMIT) if len(cells) == 4 else None
        digest = _cell(cells[2], _DIGEST) if len(cells) == 4 else None
        if commit is None or digest is None or pairs.get(commit, digest) != digest:
            raise RecoveryError(f"RELEASES.md has a malformed recovery pair row: {number}")
        pairs[commit] = digest
    return pairs


def _status_digest(raw: bytes | None) -> str | None:
    """``serving_feed_sha256`` of a ``status.json``, or None when it has no usable one."""
    if raw is None:
        return None
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        return None
    digest = doc.get("serving_feed_sha256") if isinstance(doc, dict) else None
    return digest if isinstance(digest, str) and _DIGEST.fullmatch(digest) else None


def _checked(git: Git, commit: str, releases_text: str) -> tuple[RecoveryPair, bytes]:
    """The pair of ``commit`` and its ``elections.json``, after the six checks in order."""
    if not _COMMIT.fullmatch(commit):
        raise RecoveryError("give the full 40-character commit SHA")
    if not git.succeeds("cat-file", "-e", f"{commit}^{{commit}}"):
        raise RecoveryError(f"commit {commit} is not in this repository")
    if git.succeeds("symbolic-ref", "-q", "HEAD"):
        branch = git.run("symbolic-ref", "--short", "HEAD")
    else:
        branch = "a detached HEAD"
    if branch != "main":
        raise RecoveryError(f"republish runs on branch main, not {branch}")
    if not git.succeeds("merge-base", "--is-ancestor", commit, "HEAD"):
        raise RecoveryError(f"commit {commit} is not in main's history")
    blob = git.blob(commit, "elections.json")
    if blob is None:
        raise RecoveryError(f"commit {commit} has no elections.json")
    listed = releases_pairs(releases_text).get(commit)
    if listed is not None:
        pair = RecoveryPair(commit, listed, "RELEASES.md")
    else:
        digest = _status_digest(git.blob(commit, "status.json"))
        if digest is None:
            raise RecoveryError(f"no recovery pair is recorded for {commit}")
        pair = RecoveryPair(commit, digest, "status.json")
    if hashlib.sha256(blob).hexdigest() != pair.sha256:
        raise RecoveryError(
            f"the elections.json of {commit} does not match its recorded digest {pair.sha256}"
        )
    return pair, blob


def recorded_pair(git: Git, commit: str, releases_text: str) -> RecoveryPair:
    """The recovery pair of ``commit``; the first of six problems raises ``RecoveryError``."""
    return _checked(git, commit, releases_text)[0]


def republished_feed(original: bytes, *, now: datetime) -> bytes:
    """``original`` with ``published_at`` set to ``now`` and ``republished_from_sha256`` added."""
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    try:
        doc = json.loads(original.decode("utf-8"))
    except (ValueError, RecursionError):
        doc = None
    if not isinstance(doc, dict):
        raise RecoveryError("the feed is not a JSON object")
    doc["published_at"] = _utc_iso(now)
    doc["republished_from_sha256"] = hashlib.sha256(original).hexdigest()
    new = (json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    problems = republished_problems(new, wall_clock=now)
    if problems:
        raise RecoveryError(f"the republished feed is invalid: {problems[0]}")
    return new


def republish(
    git: Git, commit: str, *, now: datetime, releases_text: str, code_sha: str
) -> tuple[bytes, bytes]:
    """``(elections.json, status.json)`` that republish the feed of ``commit``; writes nothing."""
    _, original = _checked(git, commit, releases_text)
    feed = republished_feed(original, now=now)
    status = stored_json(
        status_doc(
            attempt=Attempt(now, "local", "republish", code_sha),
            outcome="republished",
            severity="ok",
            sources=(),
            run_reasons=(),
            serving=feed,
        )
    )
    problems = validate_status(status)
    if problems:
        raise RecoveryError(f"the republication's status is invalid: {problems[0]}")
    return feed, status
