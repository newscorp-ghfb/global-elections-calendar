"""Running git for the publish job: exact bytes, bounded time, no prompts (P120, P127)."""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from elections_calendar.fetch import Deadline

PushResult = Literal["pushed", "rejected", "failed"]
_STDERR_SHOWN: Final = 300


class GitError(RuntimeError):
    """A git command failed, timed out, or was refused for lack of time."""


def _name(args: tuple[str, ...]) -> str:
    """The git command in ``args``, after any leading ``-c key=value`` pairs."""
    rest = list(args)
    while len(rest) >= 2 and rest[0] == "-c":
        del rest[:2]
    return rest[0] if rest else ""


def _last_line(stderr: bytes) -> str:
    lines = [ln for ln in stderr.decode("utf-8", errors="replace").splitlines() if ln.strip()]
    return lines[-1].strip()[:_STDERR_SHOWN] if lines else "no error output"


def _reason(stderr: bytes) -> str:
    """The last three non-empty lines of ``stderr`` on one line, capped."""
    lines = [ln.strip() for ln in stderr.decode("utf-8", errors="replace").splitlines()]
    kept = [ln for ln in lines if ln][-3:]
    return " | ".join(kept)[:_STDERR_SHOWN] if kept else "no error output"


@dataclass(frozen=True, slots=True)
class Git:
    """The git of one repository. ``deadline`` is the publish stage's (P127)."""

    repo: Path
    timeout_s: float = 60.0
    deadline: Deadline | None = None

    def _exec(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        """Run one git command; a spent deadline or a timeout raises ``GitError``."""
        name = _name(args)
        timeout = self.timeout_s
        if self.deadline is not None:
            left = self.deadline.remaining()
            if left <= 0:
                raise GitError(f"git {name} failed: the publish stage's time limit was reached")
            timeout = min(timeout, left)
        command = [
            "git",
            "-C",
            str(self.repo),
            "-c",
            "core.autocrlf=false",
            "-c",
            "core.safecrlf=false",
            "-c",
            "commit.gpgsign=false",
            *args,
        ]
        environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
        try:
            return subprocess.run(
                command, capture_output=True, env=environment, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            raise GitError(f"git {name} failed: it ran over {timeout:.0f} s") from None
        except OSError as exc:
            raise GitError(f"git {name} failed: {type(exc).__name__}") from None

    def run(self, *args: str) -> str:
        """The stdout of a git command, UTF-8 and stripped; a non-zero exit raises."""
        done = self._exec(*args)
        if done.returncode != 0:
            raise GitError(f"git {_name(args)} failed: {_last_line(done.stderr)}")
        return done.stdout.decode("utf-8", errors="replace").strip()

    def succeeds(self, *args: str) -> bool:
        """Whether a git command exits 0; a timeout, an ``OSError`` or a spent deadline raises."""
        return self._exec(*args).returncode == 0

    def blob(self, commit: str, path: str) -> bytes | None:
        """The raw bytes of ``path`` at ``commit``, or None when it is not there.

        Absent means ``git ls-tree`` succeeded and listed nothing; any other failure raises.
        """
        listed = self._exec("ls-tree", "-z", commit, "--", path)
        if listed.returncode != 0:
            raise GitError(f"git ls-tree failed: {_last_line(listed.stderr)}")
        if not listed.stdout:
            return None
        done = self._exec("cat-file", "blob", f"{commit}:{path}")
        if done.returncode != 0:
            raise GitError(f"git cat-file failed: {_last_line(done.stderr)}")
        return done.stdout

    def push(self, refspec: str) -> tuple[PushResult, str]:
        """Push to ``origin``: ``[rejected]`` is ``rejected``; ``[remote rejected]`` is not.

        The second item is git's reason (the tail of its stderr, capped) when the push ``failed``,
        else ``""``. It is for the summary and the log, never for a job output.
        """
        done = self._exec("push", "--porcelain", "origin", refspec)
        if done.returncode == 0:
            return "pushed", ""
        lines = done.stdout.decode("utf-8", errors="replace").splitlines()
        if any(line.startswith("!") and "[rejected]" in line for line in lines):
            return "rejected", ""
        return "failed", _reason(done.stderr)
