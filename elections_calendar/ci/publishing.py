"""The publish job's steps: verify, commit, push, and check what is served (P119, P120, P127)."""

import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from elections_calendar.ci.artifact import (
    Artifact,
    ArtifactError,
    copy_repository_files,
    load_artifact,
    served_link_problems,
)
from elections_calendar.ci.git import Git, GitError
from elections_calendar.feed import serving_fields
from elections_calendar.fetch import Deadline, Fetcher, trust_bundle
from elections_calendar.model import SOURCE_ORDER

RAW_URL: Final = (
    "https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/elections.json"
)
SERVED_POLL_S: Final = 60
SERVED_LIMIT_S: Final = 600
SERVED_FETCH_S: Final = 60
PUBLISH_STAGE_S: Final = 240
BOT_NAME: Final = "github-actions[bot]"
BOT_EMAIL: Final = "41898282+github-actions[bot]@users.noreply.github.com"
_PUSH_TO_MAIN: Final = "HEAD:refs/heads/main"


@dataclass(frozen=True, slots=True)
class PublishResult:
    outcome: str  # one of PUBLISH_OUTCOMES
    served: str  # one of SERVED_RESULTS
    commit: str | None
    detail: str


def _stopped(outcome: str, detail: str) -> PublishResult:
    return PublishResult(outcome, "not_checked", None, detail)


def served_check(
    expected_sha256: str,
    *,
    fetch: Callable[[float], bytes | None],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    poll_s: float = SERVED_POLL_S,
    limit_s: float = SERVED_LIMIT_S,
    fetch_s: float = SERVED_FETCH_S,
) -> str:
    """``ok`` when the served bytes have the expected digest within ``limit_s``, else a mismatch.

    One absolute deadline, checked before every fetch; a fetch gets only the time left. A fetch
    can overrun its bound (name resolution, connecting and dripped headers are not bounded), so
    one that ends after the deadline is not counted, whatever its body (P127, R2-06).
    """
    deadline = clock() + limit_s
    while True:
        left = deadline - clock()
        if left <= 0:
            return "served_mismatch"
        body = fetch(min(fetch_s, left))
        if clock() > deadline:
            return "served_mismatch"
        if body is not None and hashlib.sha256(body).hexdigest() == expected_sha256:
            return "ok"
        left = deadline - clock()
        if left <= 0:
            return "served_mismatch"
        sleep(min(poll_s, left))


def commit_message(artifact: Artifact) -> str:
    attempt_id = artifact.status["attempt_id"]
    if artifact.outcome == "published":
        return f"chore: update elections.json [{attempt_id}]"
    return f"chore: record a failed validation [{attempt_id}]"


def _repository_problem(artifact: Artifact, git: Git, code_sha: str) -> str | None:
    """Step 3: the checkout is clean, at the run's commit, and agrees with the artifact."""
    if git.run("status", "--porcelain"):
        return "the checkout has changes"
    if git.run("rev-parse", "HEAD") != code_sha:
        return "the checkout is not at the run's commit"
    if artifact.outcome == "published":
        problems = served_link_problems(
            artifact, lambda source: git.blob(code_sha, f"data/sources/{source}/baseline.json")
        )
        return problems[0] if problems else None
    kept = serving_fields(git.blob(code_sha, "elections.json"))
    if any(artifact.status.get(key) != value for key, value in kept.items()):
        return "status.json does not describe the feed the repository keeps"
    return None


def _commit(artifact: Artifact, git: Git) -> str:
    """Step 5: copy the files, add exactly them, commit as the bot; the new commit's SHA."""
    copied = copy_repository_files(artifact, git.repo)
    git.run("add", "--", *copied)
    git.run(
        "-c",
        f"user.name={BOT_NAME}",
        "-c",
        f"user.email={BOT_EMAIL}",
        "commit",
        "-m",
        commit_message(artifact),
    )
    return git.run("rev-parse", "HEAD")


def publish(
    artifact_dir: Path,
    git: Git,
    *,
    code_sha: str,
    allowed: bool,
    wall_clock: datetime,
    fetch: Callable[[float], bytes | None],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    sources: Sequence[str] = SOURCE_ORDER,
) -> PublishResult:
    """The seven steps of P120; the first that decides an outcome ends the run.

    ``sources`` is a test seam for OSCE-only artifacts: the command never passes it. A
    ``GitError`` ends the run as ``git_failed``; whatever was copied before it stays in the
    working tree (nothing is committed or pushed after it).
    """
    if not allowed:
        return _stopped("not_allowed", "publishing is not allowed in this context")
    try:
        artifact = load_artifact(
            artifact_dir, code_sha=code_sha, wall_clock=wall_clock, sources=sources
        )
    except ArtifactError as exc:
        return _stopped("refused", str(exc))
    try:
        problem = _repository_problem(artifact, git, code_sha)
        if problem is not None:
            return _stopped("refused", problem)
        git.run("fetch", "origin", "main")
        if git.run("rev-parse", "FETCH_HEAD") != code_sha:
            return _stopped("superseded", "main moved during the run")
        commit = _commit(artifact, git)
        pushed = git.push(_PUSH_TO_MAIN)
    except GitError as exc:
        return _stopped("git_failed", str(exc))
    if pushed == "rejected":
        return _stopped("superseded", "main moved before the push")
    if pushed == "failed":
        return _stopped("git_failed", "git push failed")
    served = "not_checked"
    if artifact.outcome == "published":
        served = served_check(
            artifact.status["serving_feed_sha256"], fetch=fetch, sleep=sleep, clock=clock
        )
    return PublishResult(artifact.outcome, served, commit, commit)


def served_fetcher(
    environ: Mapping[str, str], *, workdir: Path, url: str = RAW_URL
) -> Callable[[float], bytes | None]:
    """A ``fetch(timeout_s)`` of ``url`` through the machine's CA bundle (R2-07).

    The CA file is written once. Each call gets a ``Deadline`` of ``timeout_s`` and closes its
    Fetcher. A ``TrustBundleError`` propagates: it is a crash, not a mismatch.
    """
    bundle = trust_bundle(workdir / "ca-bundle.pem", environ)

    def fetch(timeout_s: float) -> bytes | None:
        with Fetcher(verify=str(bundle.path)) as fetcher:
            result = fetcher.get(url, deadline=Deadline.after(timeout_s))
        return result.body if result.outcome == "ok" else None

    return fetch
