"""Bare repositories and clones under ``tmp_path`` for the publish tests (Plan 5a Task 6).

Every git command here is ``git -C <path>`` on a path under ``tmp_path``, with an identity given
on the command line, so neither this checkout nor the machine's git configuration matters.
"""

import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[2]
V1_FEED = ROOT / "tests" / "fixtures" / "feed" / "2026-10-16-ff30417.json"
IDENTITY = ("-c", "user.name=Test", "-c", "user.email=test@example.org", "-c", "commit.gpgsign=false")


class Repos(NamedTuple):
    origin: Path  # bare, on main
    clone: Path
    head: str  # main's commit when the clone was made


def git(path: Path, *args: str) -> str:
    """``git -C path args``, stripped stdout; a failure raises with git's own message."""
    done = subprocess.run(
        ["git", "-C", str(path), "-c", "core.autocrlf=false", *IDENTITY, *args],
        capture_output=True,
        check=False,
    )
    if done.returncode != 0:
        raise AssertionError(f"git {args}: {done.stderr.decode('utf-8', errors='replace')}")
    return done.stdout.decode("utf-8", errors="replace").strip()


def git_bytes(path: Path, *args: str) -> bytes:
    done = subprocess.run(["git", "-C", str(path), *args], capture_output=True, check=True)
    return done.stdout


def _commit_all(path: Path, message: str) -> str:
    git(path, "add", "--all")
    git(path, "commit", "-m", message)
    return git(path, "rev-parse", "HEAD")


def origin_and_clone(
    tmp_path: Path, *, files: Mapping[str, bytes] | None = None, gitattributes: bool = True
) -> Repos:
    """A bare ``origin`` with one commit on ``main`` and a ``clone`` of it.

    The commit holds the project's ``.gitattributes`` (unless ``gitattributes`` is False), an
    ``elections.json`` of v1's bytes and ``files``.
    """
    origin, seed, clone = tmp_path / "origin.git", tmp_path / "seed", tmp_path / "clone"
    seed.mkdir()
    contents: dict[str, bytes] = {"elections.json": V1_FEED.read_bytes()}
    if gitattributes:
        contents[".gitattributes"] = (ROOT / ".gitattributes").read_bytes()
    contents.update(files or {})
    for name, data in contents.items():
        target = seed.joinpath(*name.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(origin)],
        capture_output=True,
        check=True,
    )
    git(seed, "init", "--initial-branch=main")
    head = _commit_all(seed, "seed")
    git(seed, "push", str(origin), "main")
    subprocess.run(
        ["git", "clone", "-c", "core.autocrlf=false", str(origin), str(clone)],
        capture_output=True,
        check=True,
    )
    return Repos(origin, clone, head)


def push_competitor(origin: Path, tmp_path: Path) -> str:
    """Another writer's commit of ``NOTES.txt`` on ``main``; its SHA."""
    other = tmp_path / "competitor"
    subprocess.run(
        ["git", "clone", "-c", "core.autocrlf=false", str(origin), str(other)],
        capture_output=True,
        check=True,
    )
    (other / "NOTES.txt").write_bytes(b"another writer\n")
    sha = _commit_all(other, "competitor")
    git(other, "push", "origin", "HEAD:refs/heads/main")
    return sha
