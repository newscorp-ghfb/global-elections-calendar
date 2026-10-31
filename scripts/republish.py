"""Republish a recorded feed: write ``elections.json`` and ``status.json``, commit nothing.

Run from the repository root as ``python -m scripts.republish --from-commit <40-hex SHA>``
(spec §15 step 7.2; Plan 5a P122). The commit must be in ``main``'s history and have a recovery pair
in ``RELEASES.md`` or in its own ``status.json``. Review the two files, then commit and push them
by hand.
"""

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from elections_calendar.ci.git import Git, GitError
from elections_calendar.ci.recovery import RecoveryError, recorded_pair, republish
from elections_calendar.publish import write_atomic


def _moment(text: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not an ISO timestamp") from None
    if moment.utcoffset() is None:
        raise argparse.ArgumentTypeError(f"{text!r} has no UTC offset (use ...Z)")
    return moment


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.republish",
        description="Write a republished elections.json and status.json; commits nothing.",
    )
    parser.add_argument("--from-commit", required=True, metavar="SHA", help="full 40-character SHA")
    parser.add_argument("--repo", type=Path, default=Path("."), help="the repository (default .)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="run every check and build both files, but write nothing (P155)",
    )
    parser.add_argument("--now", type=_moment, default=None, help="ISO time with offset (tests)")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_:
        return exit_.code if isinstance(exit_.code, int) else 2
    repo: Path = args.repo
    now: datetime = args.now or datetime.now(UTC)
    try:
        releases = repo / "RELEASES.md"
        text = releases.read_text(encoding="utf-8") if releases.exists() else ""
        git = Git(repo)
        pair = recorded_pair(git, args.from_commit, text)
        feed, status = republish(
            git,
            args.from_commit,
            now=now,
            releases_text=text,
            code_sha=git.run("rev-parse", "HEAD"),
        )
    except (RecoveryError, GitError, UnicodeDecodeError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.check:
        print(
            f"recovery pair ok: {pair.commit} ({pair.sha256}, recorded in {pair.recorded_in}); "
            "its feed can be republished"
        )
        print("nothing was written (--check)")
        return 0
    replaced: list[str] = []
    for name, data in (("elections.json", feed), ("status.json", status)):
        try:
            write_atomic(repo / name, data)
        except OSError as exc:
            done = f"{' and '.join(replaced)} already replaced" if replaced else "nothing replaced"
            print(f"cannot write {name}: {exc} ({done}); run again", file=sys.stderr)
            return 1
        replaced.append(name)
    original = json.loads(feed)["republished_from_sha256"]
    print(f"republished {args.from_commit} ({original}) as {hashlib.sha256(feed).hexdigest()}")
    print("next: review, then commit elections.json and status.json and push (spec §15 step 7.2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
