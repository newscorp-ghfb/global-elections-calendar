"""The publish job: verify, commit, push, check what is served (Plan 5a Task 6).

Every repository here is built by ``origin_and_clone`` under ``tmp_path``; ``tests/ci/conftest.py``
makes git refuse any other transport.
"""

import dataclasses
import hashlib
import json
import os
import shutil
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from elections_calendar.ci import artifact as artifact_module
from elections_calendar.ci import git as git_module
from elections_calendar.ci import publishing
from elections_calendar.ci.__main__ import main
from elections_calendar.ci.artifact import load_artifact
from elections_calendar.ci.git import Git
from elections_calendar.ci.publishing import PublishResult, publish, served_check
from elections_calendar.ci.verdict import final_verdict, state_from
from elections_calendar.fetch import Deadline, TrustBundleError
from elections_calendar.model import stored_json
from elections_calendar.text import md_text
from elections_calendar.validate import feed_content_problems
from tests.support.artifact import (
    add_file,
    fixture_artifact,
    osce_artifact,
    rewrite,
    rewrite_feed,
)
from tests.support.ci import MAIN, make_artifact, run_env
from tests.support.git_repos import (
    V1_FEED,
    Repos,
    git,
    git_bytes,
    origin_and_clone,
    push_competitor,
)
from tests.support.repo import NOW, offline_dir

SOURCES = ("osce",)
BASELINE = "data/sources/osce/baseline.json"
BOT = "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>"


class Clock:
    """A fake monotonic clock that ``sleep`` advances."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def served(root: Path) -> Callable[[float], bytes | None]:
    return lambda timeout_s: (root / "elections.json").read_bytes()


def run_publish(
    root: Path,
    repos: Repos,
    *,
    git_: Git | None = None,
    fetch: Callable[[float], bytes | None] | None = None,
    allowed: bool = True,
    clock: Clock | None = None,
    sources: tuple[str, ...] = SOURCES,
) -> PublishResult:
    clock = clock or Clock()
    return publish(
        root,
        git_ or Git(repos.clone),
        code_sha=repos.head,
        allowed=allowed,
        wall_clock=NOW,
        fetch=fetch or served(root),
        sleep=clock.sleep,
        clock=clock,
        sources=sources,
    )


def snapshot(repos: Repos) -> tuple[str, str, str]:
    """Origin's main, the clone's HEAD and the clone's ``git status --porcelain``."""
    return (
        git(repos.origin, "rev-parse", "main"),
        git(repos.clone, "rev-parse", "HEAD"),
        git(repos.clone, "status", "--porcelain"),
    )


def unchanged(repos: Repos) -> tuple[str, str, str]:
    return (repos.head, repos.head, "")


def names_changed(repos: Repos) -> list[str]:
    out = git(repos.origin, "diff-tree", "--no-commit-id", "--name-only", "-r", "main")
    return sorted(out.splitlines())


def make_writable(function: Callable[[str], object], path: str, error: BaseException) -> None:
    """Git writes its objects read-only, which Windows will not delete."""
    os.chmod(path, stat.S_IWRITE)
    function(path)


def make(tmp_path: Path, **kw: Any) -> tuple[Repos, Path]:
    repos = origin_and_clone(tmp_path)
    return repos, osce_artifact(tmp_path / "artifact", repo=repos.clone, code_sha=repos.head, **kw)


def load(root: Path, name: str) -> Any:
    return json.loads((root / name).read_text(encoding="utf-8"))


def edit_json(root: Path, name: str, edit: Callable[[Any], None]) -> None:
    data = load(root, name)
    edit(data)
    rewrite(root, name, stored_json(data))


def feed_edit(root: Path, edit: Callable[[dict[str, Any]], None]) -> None:
    doc = load(root, "elections.json")
    edit(doc)
    rewrite_feed(root, (json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode())


def osce_health(doc: dict[str, Any]) -> dict[str, Any]:
    (entry,) = [e for e in doc["source_health"] if e["source"] == "osce"]
    assert isinstance(entry, dict)
    return entry


# --- load_artifact through publish ----------------------------------------------------------

INCOMPLETE: list[tuple[str, str, Callable[[Path], object], str]] = [
    ("no-manifest", "published", lambda r: (r / "manifest.json").unlink(), "manifest.json is missing"),
    (
        "digest-changed",
        "published",
        lambda r: (r / "HEALTH.md").write_bytes(b"changed"),
        "a file does not match the manifest: 'HEALTH.md'",
    ),
    (
        "no-status",
        "published",
        lambda r: rewrite(r, "status.json", None),
        "the artifact has no status.json",
    ),
    (
        "no-health",
        "published",
        lambda r: rewrite(r, "HEALTH.md", None),
        "the artifact has no HEALTH.md",
    ),
    (
        "no-verdict",
        "published",
        lambda r: rewrite(r, "verdict.json", None),
        "the artifact has no verdict.json",
    ),
    (
        "status-invalid",
        "published",
        lambda r: rewrite(r, "status.json", b"{}\n"),
        "status.json is invalid: ",
    ),
    (
        "status-outcome",
        "published",
        lambda r: edit_json(r, "status.json", lambda s: s.update(outcome="superseded")),
        "status.json's outcome is 'superseded'",
    ),
    (
        "verdict-malformed",
        "published",
        lambda r: edit_json(r, "verdict.json", lambda v: v.update(verdict="GREEN")),
        "verdict.json is malformed",
    ),
    (
        "verdict-disagrees",
        "published",
        lambda r: edit_json(r, "verdict.json", lambda v: v.update(outcome="validation_failed")),
        "verdict.json and status.json disagree",
    ),
    (
        "dry-run",
        "published",
        lambda r: edit_json(r, "verdict.json", lambda v: v.update(dry_run=True)),
        "a dry-run artifact is never published",
    ),
    (
        "other-commit",
        "published",
        lambda r: edit_json(r, "status.json", lambda s: s.update(code_sha="1" * 40)),
        "status.json is from " + "1" * 40 + ", not ",
    ),
    (
        "other-sources",
        "published",
        lambda r: edit_json(r, "status.json", lambda s: s["sources"][0].update(source="ipu")),
        "status.json lists other sources",
    ),
    (
        "health-not-utf8",
        "published",
        lambda r: rewrite(r, "HEALTH.md", b"\xff\xfe"),
        "HEALTH.md is not UTF-8",
    ),
    (
        "no-feed",
        "published",
        lambda r: rewrite(r, "elections.json", None),
        "elections.json does not match status.json",
    ),
    (
        "feed-not-status",
        "published",
        lambda r: rewrite(r, "elections.json", (r / "elections.json").read_bytes() + b" "),
        "elections.json does not match status.json",
    ),
    (
        "no-candidate",
        "published",
        lambda r: rewrite(r, "data/sources/osce/candidate.json", None),
        "data/sources/osce is incomplete",
    ),
    (
        "no-health-state",
        "published",
        lambda r: rewrite(r, "data/sources/osce/health_state.json", None),
        "data/sources/osce is incomplete",
    ),
    (
        "failed-with-feed",
        "validation_failed",
        lambda r: add_file(r, "elections.json", b"{}"),
        "a failed validation carries a feed",
    ),
    (
        "failed-with-source",
        "validation_failed",
        lambda r: add_file(r, "data/sources/osce/candidate.json", b"{}"),
        "a failed validation carries a feed",
    ),
]


@pytest.mark.parametrize(
    ("outcome", "edit", "message"),
    [pytest.param(o, e, m, id=i) for i, o, e, m in INCOMPLETE],
)
def test_publish_refuses_an_incomplete_artifact(
    outcome: str, edit: Callable[[Path], None], message: str, tmp_path: Path
) -> None:
    repos, root = make(tmp_path, outcome=outcome)
    edit(root)
    result = run_publish(root, repos)
    assert (result.outcome, result.served, result.commit) == ("refused", "not_checked", None)
    assert result.detail.startswith(message), result.detail
    assert snapshot(repos) == unchanged(repos)


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/x.yml",
        "known_issues.yml",
        "PAUSE_PUBLISHING",
        "data/sources/evil/baseline.json",
        "data/sources/osce/notes.txt",
        "extension/background.js",
        "rejectedX/a",
        "rejected",
        "Rejected/a",
        "dataX/a",
    ],
)
def test_an_artifact_with_an_unexpected_file_is_refused(path: str, tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    add_file(root, path, b"x")
    result = run_publish(root, repos)
    assert (result.outcome, result.detail) == ("refused", f"an unexpected file: {path!r}")
    assert snapshot(repos) == unchanged(repos)


def test_rejected_files_are_artifact_only(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    add_file(root, "rejected/x", b"x")
    artifact = load_artifact(root, code_sha=repos.head, wall_clock=NOW, sources=SOURCES)
    assert "rejected/x" not in artifact.repository_files
    result = run_publish(root, repos)
    assert result.outcome == "published"
    assert names_changed(repos) == list(artifact.repository_files)


def test_an_impossible_attempt_at_is_an_artifact_error(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    edit_json(root, "status.json", lambda s: s.update(attempt_at="2026-02-30T00:00:00Z"))
    result = run_publish(root, repos)
    assert (result.outcome, result.served, result.commit) == ("refused", "not_checked", None)
    assert result.detail == "status.json is invalid: attempt_at"
    assert snapshot(repos) == unchanged(repos)


def test_the_checkout_must_be_clean_and_at_the_runs_commit(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    (repos.clone / "stray.txt").write_bytes(b"x")
    result = run_publish(root, repos)
    assert (result.outcome, result.served, result.commit) == ("refused", "not_checked", None)
    assert result.detail == "the checkout has changes"
    assert snapshot(repos) == (repos.head, repos.head, "?? stray.txt")
    assert (repos.clone / "stray.txt").read_bytes() == b"x"
    (repos.clone / "stray.txt").unlink()

    git(repos.clone, "commit", "--allow-empty", "-m", "local")
    local = git(repos.clone, "rev-parse", "HEAD")
    assert local != repos.head
    result = run_publish(root, repos)
    assert (result.outcome, result.commit) == ("refused", None)
    assert result.detail == "the checkout is not at the run's commit"
    assert snapshot(repos) == (repos.head, local, "")


def pretty(root: Path) -> None:
    doc = load(root, "elections.json")
    rewrite_feed(root, (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode())


def corrupt_units_seen(doc: dict[str, Any]) -> None:
    doc["scope"]["pages"][0]["units_seen"] += 1


def future_absence(doc: dict[str, Any]) -> None:
    doc["last_absent_at"] = {"timeout": "2026-10-20T00:00:00Z"}


def ipu_baseline(tmp_path: Path) -> bytes:
    other = fixture_artifact(tmp_path / "ipu-source", code_sha="2" * 40)
    return (other / "data/sources/ipu/baseline.json").read_bytes()


SELF_CONSISTENT: list[tuple[str, Callable[[Path, Path], None], str]] = [
    ("feed-not-json", lambda r, t: rewrite_feed(r, b"{"), "elections.json is invalid: json: not UTF-8 JSON"),
    (
        "feed-no-months",
        lambda r, t: feed_edit(r, lambda d: d.pop("months")),
        "elections.json is invalid: schema: ",
    ),
    (
        "feed-from-the-future",
        lambda r, t: feed_edit(r, lambda d: d.update(published_at="2026-10-19T13:00:00Z")),
        "elections.json is invalid: timestamp: ",
    ),
    (
        "baseline-ledger",
        lambda r, t: edit_json(r, BASELINE, corrupt_units_seen),
        "data/sources/osce/baseline.json: baseline.json is corrupt: ledger: ",
    ),
    (
        "health-state-future",
        lambda r, t: edit_json(r, "data/sources/osce/health_state.json", future_absence),
        "data/sources/osce/health_state.json is corrupt: timestamp of ",
    ),
    (
        "candidate-other-source",
        lambda r, t: rewrite(r, "data/sources/osce/candidate.json", b'{"source": "ipu"}'),
        "data/sources/osce/candidate.json is malformed",
    ),
    (
        "candidate-other-source-with-an-id",
        lambda r, t: rewrite(
            r, "data/sources/osce/candidate.json", b'{"source": "ipu", "snapshot_id": "' + b"a" * 64 + b'"}'
        ),
        "data/sources/osce/candidate.json is malformed",
    ),
    (
        "candidate-bad-id",
        lambda r, t: rewrite(
            r, "data/sources/osce/candidate.json", b'{"source": "osce", "snapshot_id": "ABC"}'
        ),
        "data/sources/osce/candidate.json is malformed",
    ),
    (
        "candidate-not-an-object",
        lambda r, t: rewrite(r, "data/sources/osce/candidate.json", b"[]"),
        "data/sources/osce/candidate.json is malformed",
    ),
    (
        "baseline-of-ipu",
        lambda r, t: rewrite(r, BASELINE, ipu_baseline(t)),
        "data/sources/osce/baseline.json: baseline.json is corrupt: it is of 'ipu', not 'osce'",
    ),
    (
        "health-too-big",
        lambda r, t: rewrite(r, "HEALTH.md", b"x" * (10 * 1024 * 1024 + 1)),
        "HEALTH.md is over 10485760 bytes",
    ),
    (
        "served-id-not-the-baseline",
        lambda r, t: feed_edit(
            r, lambda d: osce_health(d)["snapshot"].update(served_snapshot_id="0" * 64)
        ),
        f"osce: the feed serves snapshot {'0' * 64}, the committed baseline is ",
    ),
]


@pytest.mark.parametrize(
    ("edit", "message"), [pytest.param(e, m, id=i) for i, e, m in SELF_CONSISTENT]
)
def test_a_self_consistent_invalid_artifact_is_refused(
    edit: Callable[[Path, Path], None], message: str, tmp_path: Path
) -> None:
    repos, root = make(tmp_path)
    edit(root, tmp_path)
    result = run_publish(root, repos)
    assert (result.outcome, result.commit) == ("refused", None)
    assert result.detail.startswith(message), result.detail
    assert snapshot(repos) == unchanged(repos)


def test_a_reindented_feed_is_published_byte_for_byte(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    pretty(root)  # other bytes, same content: the positive control of the rows above
    data = (root / "elections.json").read_bytes()
    result = run_publish(root, repos)
    assert (result.outcome, result.served) == ("published", "ok")
    assert git_bytes(repos.origin, "cat-file", "blob", "main:elections.json") == data


def test_a_failed_validation_must_name_the_retained_feed(tmp_path: Path) -> None:
    repos, root = make(tmp_path, outcome="validation_failed")
    edit_json(root, "status.json", lambda s: s.update(serving_feed_sha256="a" * 64))
    result = run_publish(root, repos)
    assert (result.outcome, result.served, result.detail) == (
        "refused",
        "not_checked",
        "status.json does not describe the feed the repository keeps",
    )
    assert snapshot(repos) == unchanged(repos)
    honest = osce_artifact(
        tmp_path / "honest", repo=repos.clone, code_sha=repos.head, outcome="validation_failed"
    )
    assert run_publish(honest, repos).outcome == "validation_failed"


# --- the served link --------------------------------------------------------------------------


def own_baseline(tmp_path: Path) -> bytes:
    """OSCE's baseline.json as a first run on an empty repository writes it."""
    empty = tmp_path / "own-source"
    empty.mkdir()
    return (osce_artifact(tmp_path / "own", repo=empty, code_sha="3" * 40) / BASELINE).read_bytes()


def with_claim_edited(own: bytes) -> bytes:
    """One claim's office_label changed and the snapshot_id kept."""
    data = json.loads(own)
    data["claims"][0]["office_label"] = "A different office"
    return stored_json(data)


def without_checks(own: bytes) -> bytes:
    data = json.loads(own)
    del data["checks"]
    return stored_json(data)


def served_id(root: Path) -> str:
    snapshot_id = osce_health(load(root, "elections.json"))["snapshot"]["served_snapshot_id"]
    assert isinstance(snapshot_id, str)
    return snapshot_id


CORRUPT = ", but its baseline is corrupt: baseline.json is corrupt: "
LINK_REFUSALS = {
    "office-label": CORRUPT + "record: Snapshot: snapshot_id does not match its units and claims",
    "no-checks": CORRUPT + "shape: ",
    "ipu": CORRUPT + "it is of 'ipu', not 'osce'",
    "missing": ", but no baseline is committed",
}


@pytest.mark.parametrize(
    "variant", ["same", "office-label", "no-checks", "ipu", "missing", "left-alone"]
)
def test_served_links_to_the_committed_baseline(variant: str, tmp_path: Path) -> None:
    own = own_baseline(tmp_path)
    committed: dict[str, bytes | None] = {
        "same": own,
        "office-label": with_claim_edited(own),
        "no-checks": without_checks(own),
        "ipu": ipu_baseline(tmp_path),
        "missing": None,
        "left-alone": with_claim_edited(own),
    }
    held = committed[variant]
    (tmp_path / "w").mkdir()
    repos = origin_and_clone(tmp_path / "w", files={} if held is None else {BASELINE: held})
    if variant == "left-alone":
        # OSCE is unavailable, so the feed serves nothing of it and the artifact has no baseline.
        unavailable = offline_dir(tmp_path, [], name="empty-pages")
        root = osce_artifact(
            tmp_path / "artifact", repo=repos.clone, code_sha=repos.head, offline=unavailable
        )
        assert osce_health(load(root, "elections.json"))["snapshot"]["served_snapshot_id"] is None
        assert not (root / BASELINE).exists()
        assert "baseline.json is corrupt" in json.dumps(load(root, "status.json")["reasons"])
    else:
        empty = tmp_path / "empty"
        empty.mkdir()
        root = osce_artifact(tmp_path / "artifact", repo=empty, code_sha=repos.head)
        rewrite(root, BASELINE, None)  # the committed baseline is the one to serve
    result = run_publish(root, repos)
    if variant in LINK_REFUSALS:
        assert (result.outcome, result.commit) == ("refused", None)
        expected = f"osce: the feed serves snapshot {served_id(root)}{LINK_REFUSALS[variant]}"
        assert result.detail.startswith(expected), result.detail
        if variant == "missing":
            assert result.detail == expected
        assert snapshot(repos) == unchanged(repos)
    else:
        assert (result.outcome, result.served) == ("published", "ok")
        blob = git_bytes(repos.origin, "cat-file", "blob", f"main:{BASELINE}")
        assert blob == held  # a committed baseline is never rewritten or deleted


# --- the publish stage's deadline (P127) -----------------------------------------------------


@dataclass(frozen=True, slots=True)
class Ticking(Git):
    """A Git that lets 50 s pass on its clock before every command."""

    clock: Clock = dataclasses.field(default_factory=Clock)

    def _exec(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        self.clock.now += 50
        return Git._exec(self, *args)


def test_the_publish_stage_has_a_deadline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repos, root = make(tmp_path)
    clock = Clock()
    timeouts: list[tuple[float, float]] = []
    real_run = subprocess.run

    def recording(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("timeout") is not None:
            timeouts.append((kwargs["timeout"], clock.now))
        return real_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", recording)
    ticking = Ticking(repos.clone, deadline=Deadline(240.0, clock), clock=clock)
    result = run_publish(root, repos, git_=ticking)
    assert (result.outcome, result.served, result.commit) == ("git_failed", "not_checked", None)
    assert result.detail == "git add failed: the publish stage's time limit was reached"
    assert timeouts
    assert all(t <= min(60, 240 - now) for t, now in timeouts), timeouts
    assert git(repos.origin, "rev-parse", "main") == repos.head


def test_a_slow_check_is_caught_at_the_next_git_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repos, root = make(tmp_path)
    clock = Clock()
    real = feed_content_problems
    real_run = subprocess.run
    ran: list[tuple[Any, ...]] = []

    def slow(data: bytes, *, wall_clock: Any) -> tuple[str, ...]:
        clock.now += 241
        return real(data, wall_clock=wall_clock)

    def recording(*args: Any, **kwargs: Any) -> Any:
        if kwargs.get("timeout") is not None:  # a Git call; the helpers pass none
            ran.append(args)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(artifact_module, "feed_content_problems", slow)
    monkeypatch.setattr(subprocess, "run", recording)
    result = run_publish(root, repos, git_=Git(repos.clone, deadline=Deadline(240.0, clock)))
    assert (result.outcome, result.detail) == (
        "git_failed",
        "git status failed: the publish stage's time limit was reached",
    )
    assert ran == []
    assert snapshot(repos) == unchanged(repos)


# --- exact bytes (Review Focus 4) -----------------------------------------------------------


def test_committed_bytes_equal_the_artifact(tmp_path: Path) -> None:
    repos = origin_and_clone(tmp_path, gitattributes=False)
    git(repos.clone, "config", "core.autocrlf", "true")
    root = osce_artifact(tmp_path / "artifact", repo=repos.clone, code_sha=repos.head)
    rewrite(root, "HEALTH.md", b"# Health\r\nline two\r\n")
    wanted = load_artifact(root, code_sha=repos.head, wall_clock=NOW, sources=SOURCES)
    result = run_publish(root, repos)
    assert (result.outcome, result.served) == ("published", "ok")
    assert "data/sources/osce/baseline.json" in wanted.repository_files
    for path in wanted.repository_files:
        blob = git_bytes(repos.origin, "cat-file", "blob", f"main:{path}")
        assert blob == (root / path).read_bytes(), path
    assert names_changed(repos) == list(wanted.repository_files)
    attempt_id = wanted.status["attempt_id"]
    assert git(repos.origin, "log", "-1", "--format=%an <%ae>", "main") == BOT
    assert git(repos.origin, "log", "-1", "--format=%cn <%ce>", "main") == BOT
    assert git(repos.origin, "log", "-1", "--format=%B", "main") == (
        f"chore: update elections.json [{attempt_id}]"
    )
    assert result.commit == git(repos.origin, "rev-parse", "main") == result.detail


def test_a_failed_validation_commits_status_and_health_only(tmp_path: Path) -> None:
    repos, root = make(tmp_path, outcome="validation_failed")
    assert not (root / "data").exists()  # no source file: check 11 does not run (R2-03)
    result = run_publish(root, repos)
    assert (result.outcome, result.served) == ("validation_failed", "not_checked")
    assert names_changed(repos) == ["HEALTH.md", "status.json"]
    assert git_bytes(repos.origin, "cat-file", "blob", "main:elections.json") == V1_FEED.read_bytes()
    attempt_id = load(root, "status.json")["attempt_id"]
    assert git(repos.origin, "log", "-1", "--format=%s", "main") == (
        f"chore: record a failed validation [{attempt_id}]"
    )


def test_full_artifact_publishes(tmp_path: Path) -> None:
    repos = origin_and_clone(tmp_path)
    root = fixture_artifact(tmp_path / "artifact", code_sha=repos.head)
    clock = Clock()
    result = publish(
        root,
        Git(repos.clone),
        code_sha=repos.head,
        allowed=True,
        wall_clock=NOW,
        fetch=served(root),
        sleep=clock.sleep,
        clock=clock,
    )
    assert (result.outcome, result.served) == ("published", "ok")
    on_disk = sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file()
        and not p.relative_to(root).as_posix().startswith("rejected/")
        and p.name not in ("manifest.json", "verdict.json", "attention_full.json", "dispositions.json")
    )
    assert len(on_disk) == 3 + 9 * 3
    assert names_changed(repos) == on_disk


# --- the race (Review Focus 5) ----------------------------------------------------------------


def test_another_writer_before_the_run_is_superseded(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    competitor = push_competitor(repos.origin, tmp_path)
    result = run_publish(root, repos)
    assert (result.outcome, result.served, result.commit, result.detail) == (
        "superseded",
        "not_checked",
        None,
        "main moved during the run",
    )
    assert git(repos.origin, "rev-parse", "main") == competitor
    assert git(repos.clone, "rev-parse", "HEAD") == repos.head
    assert git(repos.clone, "status", "--porcelain") == ""


@dataclass(frozen=True, slots=True)
class Racing(Git):
    """A Git whose push is preceded by another writer's push."""

    origin: Path = Path()
    work: Path = Path()

    def push(self, refspec: str) -> git_module.PushResult:
        push_competitor(self.origin, self.work)
        return Git.push(self, refspec)


def test_another_writer_before_the_push_is_superseded(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    racing = Racing(repos.clone, origin=repos.origin, work=tmp_path)
    result = run_publish(root, repos, git_=racing)
    assert (result.outcome, result.served, result.commit, result.detail) == (
        "superseded",
        "not_checked",
        None,
        "main moved before the push",
    )
    main_sha = git(repos.origin, "rev-parse", "main")
    assert main_sha != repos.head
    assert git(repos.origin, "log", "-1", "--format=%s", "main") == "competitor"
    assert git_bytes(repos.origin, "cat-file", "blob", "main:elections.json") == V1_FEED.read_bytes()


def test_push_failures_are_git_failed(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    hook = repos.origin / "hooks" / "pre-receive"
    hook.write_bytes(b"#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    result = run_publish(root, repos)
    assert (result.outcome, result.served, result.commit) == ("git_failed", "not_checked", None)
    assert git(repos.origin, "rev-parse", "main") == repos.head


def test_a_missing_origin_is_git_failed(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    shutil.rmtree(repos.origin, onexc=make_writable)
    result = run_publish(root, repos)
    assert (result.outcome, result.commit) == ("git_failed", None)
    assert result.detail.startswith("git fetch failed: ")
    assert git(repos.clone, "rev-parse", "HEAD") == repos.head


# --- the served check (P120, P127) ------------------------------------------------------------

GOOD = b"the served feed\n"
DIGEST = hashlib.sha256(GOOD).hexdigest()
FEED = json.dumps({"content_id": "a" * 64, "months": {}}).encode()
SAME_CONTENT = FEED + b" "  # the same content_id, other bytes
assert json.loads(SAME_CONTENT)["content_id"] == json.loads(FEED)["content_id"]
TICKS = [float(60 * n) for n in range(10)]
LATE = [0.0, 119.0, 238.0, 357.0, 476.0, 595.0]  # 59 s fetches


def simulate(
    *,
    costs: Callable[[int], float] = lambda n: 0.0,
    bodies: Callable[[int], bytes | None] = lambda n: None,
    overrun: bool = False,
    expected: str = DIGEST,
) -> tuple[str, float, list[float], list[float]]:
    """``served_check`` on a fake clock: (result, end, fetch starts, fetch timeouts).

    A fetch costs ``costs(n)`` seconds. It is cut at its timeout and returns None, unless
    ``overrun``: then the clock advances by the whole cost, as a real fetch can (R2-06).
    """
    clock = Clock()
    starts: list[float] = []
    timeouts: list[float] = []

    def fetch(timeout_s: float) -> bytes | None:
        n = len(starts)
        starts.append(clock.now)
        timeouts.append(timeout_s)
        cost = costs(n)
        if cost > timeout_s and not overrun:
            clock.now += timeout_s
            return None
        clock.now += cost
        return bodies(n)

    result = served_check(expected, fetch=fetch, sleep=clock.sleep, clock=clock)
    return result, clock.now, starts, timeouts


def sixth(cost: float) -> dict[str, Any]:
    """59 s fetches whose sixth, started at 595, costs ``cost`` and holds the served feed."""
    return {
        "costs": lambda n: cost if n == 5 else 59.0,
        "bodies": lambda n: GOOD if n == 5 else None,
    }


SERVED_ROWS = [
    pytest.param({"bodies": lambda n: GOOD if n == 2 else None}, "ok", 120.0, TICKS[:3], id="third"),
    pytest.param({}, "served_mismatch", 600.0, TICKS, id="free"),
    pytest.param(
        {"costs": lambda n: 45.0},
        "served_mismatch",
        600.0,
        [0.0, 105.0, 210.0, 315.0, 420.0, 525.0],
        id="45s",
    ),
    pytest.param({"costs": lambda n: 59.0}, "served_mismatch", 600.0, LATE, id="59s"),
    pytest.param(sixth(3.0), "ok", 598.0, LATE, id="59s-then-3s"),
    pytest.param({**sixth(6.0), "overrun": True}, "served_mismatch", 601.0, LATE, id="overrun-6s"),
    pytest.param({**sixth(5.0), "overrun": True}, "ok", 600.0, LATE, id="overrun-5s"),
    pytest.param(
        {"costs": lambda n: 1.0},
        "served_mismatch",
        600.0,
        [61.0 * n for n in range(10)],
        id="1s",
    ),
    pytest.param(
        {"expected": hashlib.sha256(b"").hexdigest()},  # nothing fetched is not an empty body
        "served_mismatch",
        600.0,
        TICKS,
        id="none",
    ),
    pytest.param(
        {"bodies": lambda n: SAME_CONTENT, "expected": hashlib.sha256(FEED).hexdigest()},
        "served_mismatch",  # the same content_id, other bytes
        600.0,
        TICKS,
        id="same-content-id",
    ),
]


@pytest.mark.parametrize(("setup", "result", "end", "starts"), SERVED_ROWS)
def test_served_check(setup: dict[str, Any], result: str, end: float, starts: list[float]) -> None:
    found, ended, began, timeouts = simulate(**setup)
    assert (found, ended, began) == (result, end, starts)
    assert all(t <= min(60, 600 - s) for t, s in zip(timeouts, began, strict=True)), timeouts


def test_served_mismatch_is_red(tmp_path: Path) -> None:
    repos, root = make(tmp_path)
    result = run_publish(root, repos, fetch=lambda timeout_s: V1_FEED.read_bytes())
    assert (result.outcome, result.served) == ("published", "served_mismatch")
    state = state_from(
        run_env(PUBLISH_OUTCOME=result.outcome, SERVED=result.served),
        make_artifact(tmp_path / "verdict-artifact"),
    )
    final = final_verdict(state)
    assert (final.green, final.headline) == (False, "served_mismatch")


# --- the command (V2-T07, S4-T18) -----------------------------------------------------------

ROWS = [
    ("schedule", MAIN, "", True),
    ("workflow_dispatch", MAIN, "true", True),
    ("workflow_dispatch", "refs/heads/feat/x", "true", False),
    ("workflow_dispatch", MAIN, "false", False),
    ("workflow_dispatch", MAIN, "True", False),
    ("workflow_dispatch", MAIN, "", False),
    ("push", MAIN, "true", False),
]


class Command:
    """The ``publish`` command with a fake served fetcher."""

    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root: Path, *, fake: bool = True
    ) -> None:
        self.output = tmp_path / "output.txt"
        self.summary = tmp_path / "summary.md"
        self.root = root
        self.monkeypatch = monkeypatch
        if fake:
            monkeypatch.setattr(
                publishing,
                "served_fetcher",
                lambda environ, *, workdir, url=publishing.RAW_URL: served(root),
            )

    def env(self, event: str, ref: str, publish_input: str, sha: str) -> None:
        for name, value in {
            "GITHUB_EVENT_NAME": event,
            "GITHUB_REF": ref,
            "INPUT_PUBLISH": publish_input,
            "GITHUB_SHA": sha,
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_STEP_SUMMARY": str(self.summary),
        }.items():
            self.monkeypatch.setenv(name, value)

    def run(self, repo: Path) -> int:
        return main(["publish", "--artifact", str(self.root), "--repo", str(repo)])


@pytest.mark.parametrize(
    ("event", "ref", "publish_input", "commits"),
    [pytest.param(*row, id=f"{row[0]}-{row[1].rsplit('/', 1)[-1]}-{row[2] or 'none'}") for row in ROWS],
)
def test_publish_reaches_the_writer_only_when_allowed(
    event: str,
    ref: str,
    publish_input: str,
    commits: bool,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repos = origin_and_clone(tmp_path)
    root = fixture_artifact(tmp_path / "artifact", code_sha=repos.head)
    command = Command(tmp_path, monkeypatch, root)
    command.env(event, ref, publish_input, repos.head)
    assert command.run(repos.clone) == 0
    if commits:
        assert command.output.read_text(encoding="utf-8") == "outcome=published\nserved=ok\n"
        assert git(repos.origin, "rev-parse", "main") != repos.head
        text = command.summary.read_text(encoding="utf-8")
        assert text.startswith("## Publish: published, served ok\n")
        assert f"Commit: `{git(repos.origin, 'rev-parse', 'main')}`" in text
    else:
        assert command.output.read_text(encoding="utf-8") == "outcome=not_allowed\nserved=not_checked\n"
        assert snapshot(repos) == unchanged(repos)


def test_the_command_needs_an_output_and_a_commit_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repos = origin_and_clone(tmp_path)
    root = fixture_artifact(tmp_path / "artifact", code_sha=repos.head)
    command = Command(tmp_path, monkeypatch, root)
    command.env("schedule", MAIN, "", repos.head)
    monkeypatch.delenv("GITHUB_OUTPUT")
    assert command.run(repos.clone) == 2
    assert "GITHUB_OUTPUT is not set" in capsys.readouterr().err
    command.env("schedule", MAIN, "", "abc123")
    assert command.run(repos.clone) == 0
    assert command.output.read_text(encoding="utf-8") == "outcome=refused\nserved=not_checked\n"
    assert md_text("GITHUB_SHA is not a commit SHA") in command.summary.read_text(encoding="utf-8")
    assert snapshot(repos) == unchanged(repos)


def test_a_bad_ca_bundle_crashes_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repos = origin_and_clone(tmp_path)
    root = fixture_artifact(tmp_path / "artifact", code_sha=repos.head)
    command = Command(tmp_path, monkeypatch, root, fake=False)  # the real served_fetcher
    command.env("schedule", MAIN, "", repos.head)
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "missing.pem"))
    with pytest.raises(TrustBundleError):
        command.run(repos.clone)
    assert snapshot(repos) == unchanged(repos)


def test_a_status_stamp_with_a_trailing_newline_is_refused_and_commits_nothing(
    tmp_path: Path,
) -> None:
    """Python's ``$`` matches before a final newline; the schema's (ECMA-262) does not (final review F1)."""
    repos, root = make(tmp_path, outcome="validation_failed")
    edit_json(root, "status.json", lambda s: s.update(attempt_at=s["attempt_at"] + "\n"))
    result = run_publish(root, repos)
    assert result.outcome == "refused"
    assert git(repos.origin, "rev-parse", "main") == repos.head
