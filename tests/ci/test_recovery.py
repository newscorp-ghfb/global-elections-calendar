"""Recovery pairs, ``scripts/republish.py`` and the rollback (Plan 5a Task 8; P122, P123; R31).

Every repository here is built under ``tmp_path``; every git command is ``git -C <tmp path>``
(``tests/ci/conftest.py`` also makes git refuse any other transport). ``pre-v2`` and ``v2.0.0``
exist only in the temporary repository of ``test_rollback_hands_publishing_to_v1``.
"""

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from elections_calendar.ci.git import Git, GitError
from elections_calendar.ci.publishing import publish
from elections_calendar.ci.recovery import (
    ROLLBACK_EXCLUDES,
    RecoveryError,
    RecoveryPair,
    recorded_pair,
    releases_pairs,
    republish,
    republished_feed,
)
from elections_calendar.ci.switches import switches
from elections_calendar.fetch import Deadline
from elections_calendar.publish import write_atomic
from elections_calendar.validate import (
    legacy_feed_problems,
    republished_problems,
    validate_status,
)
from scripts import republish as republish_script
from tests.support.artifact import osce_artifact
from tests.support.git_repos import ROOT, V1_FEED, Repos, git, git_bytes, origin_and_clone
from tests.support.repo import NOW, commit, osce_offline

LATER = datetime(2026, 10, 20, 8, 30, 15, tzinfo=UTC)
LATER_ISO = "2026-10-20T08:30:15Z"
CODE = "a" * 40
TEMPLATE = (ROOT / "RELEASES.md").read_text(encoding="utf-8")
V1_WORKFLOW = ROOT / "tests" / "fixtures" / "v1" / "update-elections.yml"
V1_WORKFLOW_SHA = "a89ac40882d76a9414f67d7f6469b975639835396cc8413cddb7bd43a0667906"
V1_DOC: dict[str, Any] = json.loads(V1_FEED.read_bytes())
WRONG_BRANCH_SHA = "0" * 40


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(doc: Any) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def commit_all(path: Path, message: str) -> str:
    git(path, "add", "--all")
    git(path, "commit", "-m", message)
    return git(path, "rev-parse", "HEAD")


def pair_row(commit_sha: str, digest: str, *, ticks: bool = False) -> str:
    wrap = "`" if ticks else ""
    return f"| a pair | {wrap}{commit_sha}{wrap} | {wrap}{digest}{wrap} | 2026-10-23 |\n"


def releases(*rows: str) -> str:
    return TEMPLATE + "".join(rows)


def flipped(digest: str) -> str:
    return digest[:-1] + ("0" if digest[-1] != "0" else "1")


class Clock:
    """A fake monotonic clock that ``sleep`` advances."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def run_publish(artifact: Path, repo: Path, code_sha: str) -> Any:
    clock = Clock()
    return publish(
        artifact,
        Git(repo),
        code_sha=code_sha,
        allowed=True,
        wall_clock=NOW,
        fetch=lambda timeout_s: (artifact / "elections.json").read_bytes(),
        sleep=clock.sleep,
        clock=clock,
        sources=("osce",),
    )


@dataclass(frozen=True, slots=True)
class Published:
    repos: Repos
    artifact: Path
    commit: str  # the publication, on origin and in the clone
    feed: bytes


def published(tmp_path: Path) -> Published:
    """The OSCE artifact published through Task 6's ``publish`` into a clone of a v1 repository."""
    repos = origin_and_clone(tmp_path)
    artifact = osce_artifact(tmp_path / "artifact", repo=repos.clone, code_sha=repos.head)
    result = run_publish(artifact, repos.clone, repos.head)
    assert (result.outcome, result.served) == ("published", "ok")
    return Published(repos, artifact, result.commit, (artifact / "elections.json").read_bytes())


def state(clone: Path) -> dict[str, bytes | None]:
    """The two files the script may write; ``None`` when absent."""
    return {
        name: (clone / name).read_bytes() if (clone / name).exists() else None
        for name in ("elections.json", "status.json")
    }


def run_script(
    clone: Path, commit_sha: str, capsys: pytest.CaptureFixture[str], *extra: str
) -> tuple[int, str, str]:
    code = republish_script.main(
        ["--from-commit", commit_sha, "--repo", str(clone), "--now", LATER_ISO, *extra]
    )
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- RELEASES.md ------------------------------------------------------------------------------


def test_releases_table() -> None:
    c1, c2 = "1" * 40, "2" * 40
    d1, d2 = "a" * 64, "b" * 64
    assert releases_pairs(TEMPLATE) == {}  # the template holds no pair
    # the row is found under the template's own heading
    assert releases_pairs(releases(pair_row(c1, d1))) == {c1: d1}
    assert releases_pairs(releases(pair_row(c1, d1, ticks=True), pair_row(c2, d2))) == {
        c1: d1,
        c2: d2,
    }
    # a line that is not a table row is skipped; an identical repeat is fine
    assert releases_pairs(releases(pair_row(c1, d1), "a note\n", pair_row(c1, d1))) == {c1: d1}
    # a table under another heading is ignored, whatever it holds
    other = TEMPLATE.replace("## Recovery pairs", "## Elsewhere") + pair_row("bad", "bad")
    assert releases_pairs(other) == {}
    after = TEMPLATE + pair_row(c1, d1) + "\n## Notes\n\n| a | b | c | d |\n|---|---|---|---|\n| x | y | z | w |\n"
    assert releases_pairs(after) == {c1: d1}
    # the first heading's rows (the Releases table) are not pairs
    releases_row = "| 1.0 | `" + c1 + "` | x | x | x | x | x | x | x |\n"
    assert releases_pairs(TEMPLATE.replace("|---|---|---|---|---|---|---|---|---|\n", "|---|---|---|---|---|---|---|---|---|\n" + releases_row)) == {}
    crlf = releases(pair_row(c1, d1)).replace("\n", "\r\n")
    assert releases_pairs(crlf) == {c1: d1}
    for label, row in MALFORMED:
        check_malformed(label, row)
    check_repeated_commit()


MALFORMED = [
        ("39-hex commit", "| p | " + "1" * 39 + " | " + "a" * 64 + " | c |\n"),
        ("41-hex commit", "| p | " + "1" * 41 + " | " + "a" * 64 + " | c |\n"),
        ("63-hex digest", "| p | " + "1" * 40 + " | " + "a" * 63 + " | c |\n"),
        ("uppercase commit", "| p | " + "A" * 40 + " | " + "a" * 64 + " | c |\n"),
        ("uppercase digest", "| p | " + "1" * 40 + " | " + "A" * 64 + " | c |\n"),
        ("a missing cell", "| p | " + "1" * 40 + " | " + "a" * 64 + " |\n"),
        ("an extra cell", "| p | " + "1" * 40 + " | " + "a" * 64 + " | c | d |\n"),
        ("a half backtick", "| p | `" + "1" * 40 + " | " + "a" * 64 + " | c |\n"),
        ("an empty row", "| | | | |\n"),
]


def check_malformed(label: str, row: str) -> None:
    good = pair_row("2" * 40, "b" * 64)
    with pytest.raises(RecoveryError) as raised:
        releases_pairs(releases(good, row))
    assert str(raised.value) == "RELEASES.md has a malformed recovery pair row: 2", label


def check_repeated_commit() -> None:
    first, second = "a" * 64, "b" * 64
    with pytest.raises(RecoveryError) as raised:
        releases_pairs(releases(pair_row("1" * 40, first), pair_row("1" * 40, second)))
    assert str(raised.value) == "RELEASES.md has a malformed recovery pair row: 2"


# --- Git.succeeds (R1) -------------------------------------------------------------------------


def test_git_succeeds_is_an_exit_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repos = origin_and_clone(tmp_path)
    runner = Git(repos.clone)
    assert runner.succeeds("cat-file", "-e", f"{repos.head}^{{commit}}") is True
    assert runner.succeeds("cat-file", "-e", "0" * 40 + "^{commit}") is False
    spent = Git(repos.clone, deadline=Deadline(0.0, lambda: 1.0))
    with pytest.raises(GitError, match="time limit"):
        spent.succeeds("cat-file", "-e", f"{repos.head}^{{commit}}")

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise OSError("no git")

    monkeypatch.setattr(subprocess, "run", broken)
    with pytest.raises(GitError, match="OSError"):
        runner.succeeds("cat-file", "-e", f"{repos.head}^{{commit}}")


# --- the pair round trip (V2-T05, Review Focus 4) ----------------------------------------------


def test_recovery_pair_round_trip(tmp_path: Path) -> None:
    p = published(tmp_path)
    clone, old = p.repos.clone, p.feed
    pair = recorded_pair(Git(clone), p.commit, "")
    assert pair == RecoveryPair(p.commit, sha(old), "status.json")
    new, status = republish(Git(clone), p.commit, now=LATER, releases_text="", code_sha=CODE)

    old_doc, new_doc = json.loads(old), json.loads(new)
    assert new_doc.pop("republished_from_sha256") == sha(old)
    assert new_doc.pop("published_at") == LATER_ISO
    assert old_doc.pop("published_at") != LATER_ISO
    assert new_doc == old_doc  # content_id and generated_at stay the original's
    assert list(json.loads(new)) == list(json.loads(old)) + ["republished_from_sha256"]
    assert new != old

    status_doc = json.loads(status)
    assert (status_doc["outcome"], status_doc["trigger"], status_doc["code_sha"]) == (
        "republished",
        "republish",
        CODE,
    )
    assert status_doc["serving_feed_sha256"] == sha(new)
    assert status_doc["serving_published_at"] == LATER_ISO
    assert status_doc["sources"] == []
    assert validate_status(status) == ()
    for data in (new, status):
        assert data.endswith(b"\n")
        assert b"\r" not in data

    assert new == dump(json.loads(new))  # compact, UTF-8 as written, one final newline

    # the pre-v2 pair: v1's feed at the first commit, recorded in RELEASES.md only
    original = V1_FEED.read_bytes()
    text = releases(pair_row(p.repos.head, sha(original), ticks=True))
    pair = recorded_pair(Git(clone), p.repos.head, text)
    assert pair == RecoveryPair(p.repos.head, sha(original), "RELEASES.md")
    v1_new, v1_status = republish(
        Git(clone), p.repos.head, now=LATER, releases_text=text, code_sha=CODE
    )
    v1_old_doc, v1_new_doc = json.loads(original), json.loads(v1_new)
    assert list(v1_new_doc) == list(v1_old_doc) + ["published_at", "republished_from_sha256"]
    assert v1_new_doc["published_at"] == LATER_ISO
    assert v1_new_doc["republished_from_sha256"] == sha(original)
    for key in v1_old_doc:
        assert v1_new_doc[key] == v1_old_doc[key], key  # v1's fields, generated_at among them
    assert v1_new_doc["generated_at"] == "2026-10-16T00:02:31Z"
    assert v1_new == dump(v1_new_doc)
    assert json.loads(v1_status)["serving_feed_sha256"] == sha(v1_new)
    assert validate_status(v1_status) == ()

    # committed in a clone with core.autocrlf=true, both blobs equal the bytes
    subprocess.run(
        ["git", "-C", str(clone), "config", "core.autocrlf", "true"], check=True, capture_output=True
    )
    (clone / "elections.json").write_bytes(new)
    (clone / "status.json").write_bytes(status)
    subprocess.run(
        ["git", "-C", str(clone), "add", "elections.json", "status.json"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(clone), "-c", "user.name=T", "-c", "user.email=t@example.org",
         "-c", "commit.gpgsign=false", "commit", "-m", "republish"],
        check=True,
        capture_output=True,
    )
    assert git_bytes(clone, "cat-file", "blob", "HEAD:elections.json") == new
    assert git_bytes(clone, "cat-file", "blob", "HEAD:status.json") == status


def test_the_releases_row_wins_over_the_status_digest(tmp_path: Path) -> None:
    p = published(tmp_path)
    other = "c" * 64  # the status.json is right, the row is not: the row decides
    with pytest.raises(RecoveryError) as raised:
        recorded_pair(Git(p.repos.clone), p.commit, releases(pair_row(p.commit, other)))
    assert str(raised.value).endswith(f"does not match its recorded digest {other}")
    agreeing = recorded_pair(Git(p.repos.clone), p.commit, releases(pair_row(p.commit, sha(p.feed))))
    assert agreeing == RecoveryPair(p.commit, sha(p.feed), "RELEASES.md")


# --- a missing or altered pair blocks restoration ------------------------------------------------


def case_no_pair(p: Published) -> tuple[str, str, str]:
    c = p.repos.head
    return c, "", f"no recovery pair is recorded for {c}"


def case_altered_row(p: Published) -> tuple[str, str, str]:
    c, bad = p.repos.head, flipped(sha(V1_FEED.read_bytes()))
    return (
        c,
        releases(pair_row(c, bad)),
        f"the elections.json of {c} does not match its recorded digest {bad}",
    )


def case_status_mismatch(p: Published) -> tuple[str, str, str]:
    clone = p.repos.clone
    doc = json.loads((clone / "status.json").read_bytes())
    doc["serving_feed_sha256"] = bad = flipped(doc["serving_feed_sha256"])
    (clone / "status.json").write_bytes(json.dumps(doc, indent=1).encode() + b"\n")
    c = commit_all(clone, "a status that names other bytes")
    return c, "", f"the elections.json of {c} does not match its recorded digest {bad}"


def case_status_without_digest(p: Published) -> tuple[str, str, str]:
    clone = p.repos.clone
    for body in (b"[1]\n", b"not json\n", b'{"serving_feed_sha256": "xyz"}\n', b'{"a": 1}\n'):
        (clone / "status.json").write_bytes(body)
        c = commit_all(clone, "a status without a digest")
        with pytest.raises(RecoveryError, match="no recovery pair is recorded"):
            recorded_pair(Git(clone), c, "")
    return c, "", f"no recovery pair is recorded for {c}"


def case_short(p: Published) -> tuple[str, str, str]:
    return p.commit[:12], "", "give the full 40-character commit SHA"


def case_upper(p: Published) -> tuple[str, str, str]:
    return p.commit.upper(), "", "give the full 40-character commit SHA"


def case_unknown(p: Published) -> tuple[str, str, str]:
    return WRONG_BRANCH_SHA, "", f"commit {WRONG_BRANCH_SHA} is not in this repository"


def case_malformed_row(p: Published) -> tuple[str, str, str]:
    text = releases("| x | `abc` | `def` | y |\n")
    return p.commit, text, "RELEASES.md has a malformed recovery pair row: 1"


def case_no_elections(p: Published) -> tuple[str, str, str]:
    clone = p.repos.clone
    git(clone, "rm", "-q", "elections.json")
    c = commit_all(clone, "no feed")
    return c, "", f"commit {c} has no elections.json"


CASES: dict[str, Callable[[Published], tuple[str, str, str]]] = {
    "no row and no status": case_no_pair,
    "an altered row": case_altered_row,
    "a status that names other bytes": case_status_mismatch,
    "a status without a digest": case_status_without_digest,
    "a 12-character SHA": case_short,
    "an uppercase SHA": case_upper,
    "an unknown SHA": case_unknown,
    "a malformed row": case_malformed_row,
    "no elections.json": case_no_elections,
}


@pytest.mark.parametrize("case", list(CASES))
def test_a_missing_or_altered_pair_blocks_restoration(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = published(tmp_path)
    clone = p.repos.clone
    commit_sha, text, message = CASES[case](p)
    with pytest.raises(RecoveryError) as raised:
        recorded_pair(Git(clone), commit_sha, text)
    assert str(raised.value) == message
    with pytest.raises(RecoveryError) as raised:
        republish(Git(clone), commit_sha, now=LATER, releases_text=text, code_sha=CODE)
    assert str(raised.value) == message

    if text:
        (clone / "RELEASES.md").write_text(text, encoding="utf-8", newline="")
    before = state(clone)
    code, out, err = run_script(clone, commit_sha, capsys)
    assert (code, out) == (1, "")
    assert message in err
    assert "Traceback" not in err
    assert state(clone) == before


# --- the schema and the format rules -----------------------------------------------------------


def test_republished_feed_passes_the_schema(tmp_path: Path) -> None:
    p = published(tmp_path)
    new = republished_feed(p.feed, now=LATER)
    assert republished_problems(new, wall_clock=LATER) == ()
    doc = json.loads(new)
    doc["republished_from_sha256"] = "x"
    problems = republished_problems(dump(doc), wall_clock=LATER)
    assert problems
    assert problems[0].startswith("schema: /republished_from_sha256")
    assert republished_problems(b"[]", wall_clock=LATER) == ("format: the feed is not a JSON object",)
    assert republished_problems(b"\xff\xfe", wall_clock=LATER) == ("json: not UTF-8 JSON",)
    assert republished_problems(b"not json", wall_clock=LATER) == ("json: not UTF-8 JSON",)
    naive = datetime(2026, 10, 20, 8, 30)
    for data in (new, b"[]", b"not json", V1_FEED.read_bytes()):
        with pytest.raises(ValueError, match="timezone-aware"):
            republished_problems(data, wall_clock=naive)


def test_a_republication_with_an_invalid_status_is_refused(tmp_path: Path) -> None:
    repos = origin_and_clone(tmp_path)
    text = releases(pair_row(repos.head, sha(V1_FEED.read_bytes())))
    with pytest.raises(RecoveryError, match="the republication's status is invalid: schema"):
        republish(Git(repos.clone), repos.head, now=LATER, releases_text=text, code_sha="nope")


def test_republished_feed_refuses_a_naive_time_and_a_non_object() -> None:
    with pytest.raises(ValueError, match="now must be timezone-aware"):
        republished_feed(V1_FEED.read_bytes(), now=datetime(2026, 10, 20, 8, 30))
    for data in (b"[]", b"3", b"not json", b"\xff"):
        with pytest.raises(RecoveryError) as raised:
            republished_feed(data, now=LATER)
        assert str(raised.value) == "the feed is not a JSON object"


def test_the_v1_fixture_has_no_legacy_problems() -> None:
    assert legacy_feed_problems(V1_FEED.read_bytes(), wall_clock=LATER) == ()
    assert sorted(V1_DOC) == ["current_month", "errors", "generated_at", "months"]


def legacy(doc: Any) -> tuple[str, ...]:
    return legacy_feed_problems(dump(doc), wall_clock=LATER)


def v1_with(edit: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(V1_FEED.read_bytes())
    edit(doc)
    return doc


def first_card(doc: dict[str, Any]) -> dict[str, Any]:
    card: dict[str, Any] = next(iter(next(iter(doc["months"].values()))))
    return card


@pytest.mark.parametrize(
    ("label", "edit"),
    [
        ("a missing key", lambda d: d.pop("errors")),
        ("an extra key", lambda d: d.update(evil=1)),
        ("a bad generated_at", lambda d: d.update(generated_at="2026-10-16")),
        ("an impossible generated_at", lambda d: d.update(generated_at="2026-02-30T00:00:00Z")),
        ("a generated_at ahead of the clock", lambda d: d.update(generated_at="2026-10-20T08:41:00Z")),
        ("a bad published_at", lambda d: d.update(published_at="yesterday")),
        ("a published_at ahead of the clock", lambda d: d.update(published_at="2026-10-20T08:41:00Z")),
        ("a bad republished_from_sha256", lambda d: d.update(republished_from_sha256="A" * 64)),
        ("a non-string republished_from_sha256", lambda d: d.update(republished_from_sha256=5)),
        ("a bad current_month", lambda d: d.update(current_month="2026-1")),
        ("a non-list errors", lambda d: d.update(errors={})),
        ("a non-object months", lambda d: d.update(months=[])),
        ("a bad month key", lambda d: d["months"].update({"2026-1": []})),
        ("a non-list month", lambda d: d["months"].update({"2026-12": {}})),
        ("a non-object card", lambda d: d["months"].update({"2026-12": ["card"]})),
        ("a card without a country", lambda d: first_card(d).pop("country")),
        ("a card with a bad date", lambda d: first_card(d).update(date="soon")),
    ],
)
def test_legacy_feed_problems(label: str, edit: Callable[[dict[str, Any]], None]) -> None:
    problems = legacy(v1_with(edit))
    assert problems, label
    assert all(p.startswith("legacy: ") for p in problems), problems


def test_legacy_feed_problems_accept_the_republication_keys_and_refuse_odd_input() -> None:
    doc = v1_with(
        lambda d: d.update(published_at=LATER_ISO, republished_from_sha256="a" * 64)
    )
    assert legacy(doc) == ()
    assert legacy({}) != ()
    assert legacy([]) == ("legacy: the feed is not a JSON object",)
    assert legacy_feed_problems(b"nope", wall_clock=LATER) == ("legacy: not UTF-8 JSON",)
    big = dump(v1_with(lambda d: d.update(errors=["x" * 2_000_000])))
    assert any(p.startswith("legacy: size") for p in legacy_feed_problems(big, wall_clock=LATER))
    with pytest.raises(ValueError, match="timezone-aware"):
        legacy_feed_problems(V1_FEED.read_bytes(), wall_clock=datetime(2026, 10, 20))


def only_supported_documents() -> list[tuple[str, bytes, str]]:
    """``(label, elections.json bytes, the message republish must give)``."""
    bad = "the republished feed is invalid: "
    rows: list[tuple[str, bytes, str]] = [
        ("an empty object", dump({}), bad + "legacy: "),
        ("v1 without months", dump(v1_with(lambda d: d.pop("months"))), bad + "legacy: "),
        (
            "v1 without a country",
            dump(v1_with(lambda d: first_card(d).pop("country"))),
            bad + "legacy: ",
        ),
        ("v1 with an extra key", dump(v1_with(lambda d: d.update(evil=1))), bad + "legacy: "),
        ("a JSON list", dump([]), "the feed is not a JSON object"),
    ]
    for value in (999, "2", 2.0, True, None):
        rows.append(
            (
                f"schema_version {value!r}",
                dump({"schema_version": value, "months": {}}),
                bad + f"format: schema_version {value!r} is not supported",
            )
        )
    return rows


def test_only_supported_formats_are_republished(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repos = origin_and_clone(tmp_path)
    clone = repos.clone
    v2 = osce_artifact(tmp_path / "artifact", repo=clone, code_sha=repos.head)
    cases: list[tuple[str, str, str]] = []
    rows = ""
    for label, data, message in only_supported_documents():
        (clone / "elections.json").write_bytes(data)
        c = commit_all(clone, label)
        rows += pair_row(c, sha(data))
        cases.append((label, c, message))
    # positive controls: the real v1 feed and the OSCE v2 feed
    controls = {"v1": V1_FEED.read_bytes(), "v2": (v2 / "elections.json").read_bytes()}
    good: dict[str, str] = {}
    for label, data in controls.items():
        (clone / "elections.json").write_bytes(data)
        good[label] = commit_all(clone, label)
        rows += pair_row(good[label], sha(data))
    text = releases(rows)
    (clone / "RELEASES.md").write_text(text, encoding="utf-8", newline="")

    for label, c, message in cases:
        with pytest.raises(RecoveryError) as raised:
            republish(Git(clone), c, now=LATER, releases_text=text, code_sha=CODE)
        assert str(raised.value).startswith(message), label
        before = state(clone)
        code, out, err = run_script(clone, c, capsys)
        assert (code, out) == (1, ""), label
        assert str(raised.value) in err, label
        assert state(clone) == before, label

    for label, c in good.items():
        new, _ = republish(Git(clone), c, now=LATER, releases_text=text, code_sha=CODE)
        assert republished_problems(new, wall_clock=LATER) == (), label
        assert json.loads(new)["republished_from_sha256"] == sha(controls[label])


# --- the pair must be on main (P5A-03) ---------------------------------------------------------


def test_a_pair_must_be_on_main(tmp_path: Path) -> None:
    repos = origin_and_clone(tmp_path)
    clone, runner = repos.clone, Git(repos.clone)
    doc = dict(V1_DOC)
    doc["errors"] = ["a side commit"]
    feed = dump(doc)
    git(clone, "checkout", "-b", "side")
    (clone / "elections.json").write_bytes(feed)
    (clone / "status.json").write_bytes(json.dumps({"serving_feed_sha256": sha(feed)}).encode())
    side = commit_all(clone, "a self-consistent pair off main")
    git(clone, "checkout", "main")

    with pytest.raises(RecoveryError) as raised:
        recorded_pair(runner, side, "")
    assert str(raised.value) == f"commit {side} is not in main's history"

    git(clone, "checkout", "-b", "feat/x")
    with pytest.raises(RecoveryError) as raised:
        recorded_pair(runner, side, "")
    assert str(raised.value) == "republish runs on branch main, not feat/x"

    git(clone, "checkout", "--detach")
    with pytest.raises(RecoveryError) as raised:
        recorded_pair(runner, side, "")
    assert str(raised.value) == "republish runs on branch main, not a detached HEAD"

    git(clone, "checkout", "main")
    git(clone, "merge", "--no-ff", "side", "-m", "merge side")
    new, _ = republish(runner, side, now=LATER, releases_text="", code_sha=CODE)
    assert json.loads(new)["republished_from_sha256"] == sha(feed)


# --- scripts/republish.py ----------------------------------------------------------------------


def test_the_script_writes_two_files_and_commits_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = published(tmp_path)
    clone = p.repos.clone
    head = git(clone, "rev-parse", "HEAD")
    code, out, err = run_script(clone, p.commit, capsys)
    assert (code, err) == (0, "")
    feed, status = (clone / "elections.json").read_bytes(), (clone / "status.json").read_bytes()
    expected_feed, expected_status = republish(
        Git(clone), p.commit, now=LATER, releases_text="", code_sha=head
    )
    assert (feed, status) == (expected_feed, expected_status)
    assert out.splitlines() == [
        f"republished {p.commit} ({sha(p.feed)}) as {sha(feed)}",
        "next: review, then commit elections.json and status.json and push (spec §15 step 7.2)",
    ]
    assert json.loads(status)["code_sha"] == head
    assert git(clone, "rev-parse", "HEAD") == head  # nothing committed
    changed = [line.strip() for line in git(clone, "status", "--porcelain").splitlines()]
    assert sorted(changed) == ["M elections.json", "M status.json"]
    assert not list(clone.glob("*.tmp"))


def test_the_script_reads_releases_md_and_defaults_to_the_current_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repos = origin_and_clone(tmp_path)
    clone = repos.clone
    (clone / "RELEASES.md").write_text(
        releases(pair_row(repos.head, sha(V1_FEED.read_bytes()), ticks=True)),
        encoding="utf-8",
        newline="",
    )
    monkeypatch.chdir(clone)
    code = republish_script.main(["--from-commit", repos.head])
    captured = capsys.readouterr()
    assert (code, captured.err) == (0, "")
    doc = json.loads((clone / "elections.json").read_bytes())
    published_at = datetime.fromisoformat(doc["published_at"].replace("Z", "+00:00"))
    assert abs(datetime.now(UTC) - published_at).total_seconds() < 300  # --now defaults to the clock
    assert doc["republished_from_sha256"] == sha(V1_FEED.read_bytes())


def test_the_script_usage_errors_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repos = origin_and_clone(tmp_path)
    before = state(repos.clone)
    assert republish_script.main([]) == 2
    assert "--from-commit" in capsys.readouterr().err
    for now in ("yesterday", "2026-10-20T08:30:15"):
        argv = ["--from-commit", repos.head, "--repo", str(repos.clone), "--now", now]
        assert republish_script.main(argv) == 2, now
        capsys.readouterr()
    assert state(repos.clone) == before


def test_a_git_failure_is_an_exit_1_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repos = origin_and_clone(tmp_path)
    before = state(repos.clone)

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise OSError("no git")

    monkeypatch.setattr(subprocess, "run", broken)
    code, out, err = run_script(repos.clone, repos.head, capsys)
    assert (code, out) == (1, "")
    assert "git" in err
    assert "Traceback" not in err
    assert state(repos.clone) == before


def test_the_script_runs_as_a_module(tmp_path: Path) -> None:
    repos = origin_and_clone(tmp_path)
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.republish",
            "--from-commit",
            repos.head,
            "--repo",
            str(repos.clone),
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    assert done.returncode == 1
    assert b"no recovery pair is recorded" in done.stderr


# --- the rollback (V2-T05, P123, P5A-02) ---------------------------------------------------------


def tree(root: Path, prefix: str) -> dict[str, bytes]:
    base = root.joinpath(*prefix.split("/"))
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(base.rglob("*")) if p.is_file()}


def workflow_facts(text: str) -> tuple[set[str], list[str], str]:
    """The workflow's triggers, its ``git add`` lines and the text of every step."""
    loaded = yaml.safe_load(text)
    triggers = loaded.get("on", loaded.get(True))
    steps = [step for job in loaded["jobs"].values() for step in job["steps"]]
    adds = [
        line.strip()
        for step in steps
        for line in str(step.get("run", "")).splitlines()
        if "git add" in line
    ]
    return set(triggers), adds, json.dumps(steps)


def rollback_history(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    """v1 (``pre-v2``), v2 code and first baselines, more v2 (``v2.0.0``), a publication,
    ``PAUSE_PUBLISHING`` and a republication from ``pre-v2``."""
    repo = tmp_path / "rollback"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")

    def write(path: str, data: bytes) -> None:
        target = repo.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def run_into(name: str, fetched: datetime) -> Path:
        scratch = tmp_path / f"{name}-scratch"
        scratch.mkdir()
        pages = osce_offline(tmp_path, fetched_at=fetched, name=f"{name}-pages")
        return osce_artifact(tmp_path / name, repo=scratch, code_sha="1" * 40, offline=pages)

    write("elections.json", V1_FEED.read_bytes())
    write("scraper.py", b"v1 code\n")
    write(".github/workflows/update-elections.yml", V1_WORKFLOW.read_bytes())
    pre_v2 = commit_all(repo, "v1")
    git(repo, "tag", "pre-v2")

    first = run_into("first", datetime(2026, 10, 18, 11, 18, 37, tzinfo=UTC))
    commit(first, repo)
    (repo / "elections.json").write_bytes(V1_FEED.read_bytes())  # the first baselines only
    for name in ("status.json", "HEALTH.md"):
        (repo / name).unlink(missing_ok=True)
    write(".gitattributes", (ROOT / ".gitattributes").read_bytes())  # pre-v2 has none
    write("scraper.py", b"v2 code\n")
    write("elections_calendar/model.py", b"v2 model\n")
    write(".github/workflows/update-elections.yml", (ROOT / ".github/workflows/update-elections.yml").read_bytes())
    write("RELEASES.md", releases(pair_row(pre_v2, sha(V1_FEED.read_bytes()))).encode())
    commit_all(repo, "v2 code and the first baselines")
    write("lib.py", b"more v2\n")
    write("schemas/x.json", b"{}\n")
    commit_all(repo, "more v2")
    git(repo, "tag", "v2.0.0")

    second = run_into("second", datetime(2026, 10, 19, 6, 0, 0, tzinfo=UTC))
    commit(second, repo)
    publication = commit_all(repo, "publication")
    write("PAUSE_PUBLISHING", b"pause\n")
    commit_all(repo, "pause")
    assert switches(repo)["paused"] == "true"  # v2's reader honours the marker

    feed, status = republish(
        Git(repo),
        pre_v2,
        now=LATER,
        releases_text=(repo / "RELEASES.md").read_text(encoding="utf-8"),
        code_sha=git(repo, "rev-parse", "HEAD"),
    )
    write("elections.json", feed)
    write("status.json", status)
    republication = commit_all(repo, "republish")
    return repo, {
        "pre_v2": pre_v2,
        "publication": publication,
        "republication": republication,
        "feed": feed,
        "status": status,
        "sources": tree(repo, "data/sources"),
        "kept": {
            name: (repo / name).read_bytes() for name in ("HEALTH.md", "RELEASES.md", ".gitattributes")
        },
    }


def test_rollback_hands_publishing_to_v1(tmp_path: Path) -> None:
    repo, facts = rollback_history(tmp_path)
    assert facts["sources"], "the publication holds baselines"
    first_baselines = git_bytes(repo, "show", "v2.0.0~1:data/sources/osce/candidate.json")
    assert first_baselines != facts["sources"]["data/sources/osce/candidate.json"], (
        "a publication rewrites the baselines: that is what makes the range revert conflict"
    )

    # the range revert, recorded as the reason P123 replaces it
    reverted = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=T", "-c", "user.email=t@example.org",
         "revert", "--no-commit", "pre-v2..v2.0.0"],
        capture_output=True,
        check=False,
    )
    assert reverted.returncode != 0
    git(repo, "revert", "--quit")  # --abort cannot reset the half-reverted tree here
    git(repo, "reset", "--hard", "HEAD")
    assert git(repo, "status", "--porcelain") == ""

    git(repo, "restore", "--source=pre-v2", "--staged", "--worktree", "--", ".", *ROLLBACK_EXCLUDES)
    git(repo, "commit", "-m", "Roll back to the pre-v2 code")

    assert (repo / "elections.json").read_bytes() == facts["feed"]
    assert (repo / "status.json").read_bytes() == facts["status"]
    assert json.loads(facts["feed"])["generated_at"] == "2026-10-16T00:02:31Z"
    assert tree(repo, "data/sources") == facts["sources"]
    assert (repo / "scraper.py").read_bytes() == b"v1 code\n"
    for gone in ("elections_calendar/model.py", "lib.py", "schemas/x.json", "PAUSE_PUBLISHING"):
        assert not (repo / gone).exists(), gone
    assert switches(repo)["paused"] == "false"
    for name, data in facts["kept"].items():  # the files the restore leaves alone
        assert (repo / name).read_bytes() == data, name
    assert git(repo, "status", "--porcelain") == ""

    workflow = (repo / ".github" / "workflows" / "update-elections.yml").read_bytes()
    triggers, adds, steps = workflow_facts(workflow.decode("utf-8"))
    assert triggers == {"schedule", "workflow_dispatch"}  # no push: the restore starts nothing
    assert "PAUSE_PUBLISHING" not in steps
    assert adds == ["git add elections.json"]
    assert workflow == V1_WORKFLOW.read_bytes()
    assert sha(workflow) == V1_WORKFLOW_SHA


def test_workflow_facts_see_what_v2_changes() -> None:
    triggers, adds, steps = workflow_facts((ROOT / ".github/workflows/update-elections.yml").read_text(encoding="utf-8"))
    assert "push" in triggers  # so the v1 assertions above can fail
    assert "paused" in steps


# --- the race (RT-05) --------------------------------------------------------------------------


def test_an_interleaved_publisher_is_superseded(tmp_path: Path) -> None:
    repos = origin_and_clone(tmp_path)
    operator = repos.clone
    runner = tmp_path / "runner"  # the scheduled run's own checkout, taken before the pause
    subprocess.run(
        ["git", "clone", "-c", "core.autocrlf=false", str(repos.origin), str(runner)],
        check=True,
        capture_output=True,
    )
    artifact = osce_artifact(tmp_path / "artifact", repo=runner, code_sha=repos.head)

    (operator / "PAUSE_PUBLISHING").write_bytes(b"pause\n")
    commit_all(operator, "pause")
    git(operator, "push", "origin", "HEAD:refs/heads/main")
    text = releases(pair_row(repos.head, sha(V1_FEED.read_bytes())))
    feed, status = republish(
        Git(operator),
        repos.head,
        now=LATER,
        releases_text=text,
        code_sha=git(operator, "rev-parse", "HEAD"),
    )
    (operator / "RELEASES.md").write_text(text, encoding="utf-8", newline="")
    (operator / "elections.json").write_bytes(feed)
    (operator / "status.json").write_bytes(status)
    republication = commit_all(operator, "republish")
    git(operator, "push", "origin", "HEAD:refs/heads/main")

    result = run_publish(artifact, runner, repos.head)
    assert (result.outcome, result.served, result.commit, result.detail) == (
        "superseded",
        "not_checked",
        None,
        "main moved during the run",
    )
    assert git(repos.origin, "rev-parse", "main") == republication
    assert git_bytes(repos.origin, "cat-file", "blob", "main:elections.json") == feed
    assert git(runner, "rev-parse", "HEAD") == repos.head
    assert git(runner, "status", "--porcelain") == ""


# --- the final fix wave (final review T6-M3, T8-M1 to T8-M4) ------------------------------------


def test_blob_is_none_only_for_a_path_that_is_not_there(tmp_path: Path) -> None:
    repos = origin_and_clone(tmp_path)
    runner = Git(repos.clone)
    assert runner.blob(repos.head, "elections.json") == V1_FEED.read_bytes()
    assert runner.blob(repos.head, "no/such/file.json") is None
    with pytest.raises(GitError, match="git ls-tree failed"):
        runner.blob("0" * 40, "elections.json")  # an unknown commit is not "absent"
    with pytest.raises(GitError, match="git ls-tree failed"):
        Git(tmp_path / "not-a-repository").blob(repos.head, "elections.json")


def test_blob_raises_when_the_blob_cannot_be_read(tmp_path: Path) -> None:
    repos = origin_and_clone(tmp_path, files={"data/x.json": b"{}"})
    runner = Git(repos.clone)
    # A tree is listed, but is not a blob: cat-file fails, which is an error, not "absent".
    with pytest.raises(GitError, match="git cat-file failed"):
        runner.blob(repos.head, "data")


def test_a_deleted_or_changed_pairs_header_is_refused() -> None:
    good = pair_row("1" * 40, "a" * 64)
    no_header = TEMPLATE.replace("| Name | Commit | `elections.json` SHA-256 | Checked |\n", "")
    assert no_header != TEMPLATE
    with pytest.raises(RecoveryError, match="has no header row"):
        releases_pairs(no_header + good)
    renamed = TEMPLATE.replace("| Name |", "| Label |")
    with pytest.raises(RecoveryError, match="has no header row"):
        releases_pairs(renamed + good)
    assert releases_pairs(TEMPLATE + good) == {"1" * 40: "a" * 64}


def test_an_unknown_sha_on_a_side_branch_is_unknown_before_it_is_off_main(tmp_path: Path) -> None:
    """Check 2 (the commit exists) runs before check 3 (the branch is main)."""
    repos = origin_and_clone(tmp_path)
    git(repos.clone, "checkout", "-q", "-b", "feat/x")
    runner = Git(repos.clone)
    with pytest.raises(RecoveryError, match="is not in this repository"):
        recorded_pair(runner, "9" * 40, "")
    with pytest.raises(RecoveryError, match="republish runs on branch main, not feat/x"):
        recorded_pair(runner, repos.head, "")


FOREIGN = ['"\\ud800"', "NaN", "Infinity", "-Infinity"]


@pytest.mark.parametrize("tail", FOREIGN, ids=["lone surrogate", "NaN", "Infinity", "-Infinity"])
def test_a_recorded_feed_json_cannot_hold_is_refused_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], tail: str
) -> None:
    repos = origin_and_clone(tmp_path)
    clone = repos.clone
    doc = dict(V1_DOC)
    doc["errors"] = ["@@"]
    raw = (json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").replace('"@@"', tail)
    (clone / "elections.json").write_bytes(raw.encode("utf-8"))
    recorded = commit_all(clone, "a feed json cannot hold")
    (clone / "RELEASES.md").write_text(
        releases(pair_row(recorded, sha(raw.encode("utf-8")))), encoding="utf-8", newline=""
    )
    before = state(clone)
    with pytest.raises(RecoveryError):
        republish(Git(clone), recorded, now=LATER, releases_text=releases(
            pair_row(recorded, sha(raw.encode("utf-8")))
        ), code_sha=CODE)
    code, out, err = run_script(clone, recorded, capsys)
    assert (code, out) == (1, "")
    assert err.strip() and "Traceback" not in err
    assert state(clone) == before


def test_the_script_names_what_it_replaced_when_a_write_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    p = published(tmp_path)
    clone = p.repos.clone
    real = write_atomic
    calls: list[str] = []

    def second_fails(path: Path, data: bytes) -> None:
        calls.append(path.name)
        if len(calls) == 2:
            raise PermissionError("status.json is locked")
        real(path, data)

    monkeypatch.setattr(republish_script, "write_atomic", second_fails)
    code, out, err = run_script(clone, p.commit, capsys)
    assert (code, out) == (1, "")
    assert err == (
        "cannot write status.json: status.json is locked (elections.json already replaced); "
        "run again\n"
    )
    assert calls == ["elections.json", "status.json"]

    calls.clear()

    def first_fails(path: Path, data: bytes) -> None:
        raise PermissionError("elections.json is locked")

    monkeypatch.setattr(republish_script, "write_atomic", first_fails)
    code, out, err = run_script(clone, p.commit, capsys)
    assert code == 1
    assert err == "cannot write elections.json: elections.json is locked (nothing replaced); run again\n"


def test_an_unreadable_releases_md_is_an_exit_1_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repos = origin_and_clone(tmp_path)
    (repos.clone / "RELEASES.md").mkdir()  # exists, but cannot be read as a file
    code, out, err = run_script(repos.clone, repos.head, capsys)
    assert (code, out) == (1, "")
    assert err.strip() and "Traceback" not in err
