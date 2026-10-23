"""The command line: ``python -m elections_calendar (--live | --offline DIR) --out DIR`` (P98).

``--dry-run`` (with ``--live`` only) spends at most 40 requests and marks the artifact a dry run.

Exit 0: a complete artifact was written, whatever the verdict. Exit 1: the run failed before it
could write one (an untrusted CA bundle, or an unexpected error, which propagates). Exit 2: a
usage error. Only this module chooses the clock (``now`` and ``wall_clock`` come in with the
``RunConfig``); ``pipeline`` reads only ``RunConfig.timer``, for ``parse_ms``.
"""

import argparse
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from elections_calendar.fetch import TrustBundleError
from elections_calendar.model import stored_json
from elections_calendar.pipeline import RunConfig, UsageError, run
from elections_calendar.publish import write_atomic


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="elections_calendar", description="Build the elections calendar artifact."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="fetch the sources")
    mode.add_argument("--offline", type=Path, metavar="DIR", help="read DIR/pages.json instead")
    parser.add_argument(
        "--dry-run", action="store_true", help="with --live: at most 40 requests, nothing published"
    )
    parser.add_argument("--now", metavar="ISO", help="the time to judge the data at (needs a zone)")
    parser.add_argument("--out", type=Path, required=True, metavar="DIR", help="empty or new")
    parser.add_argument("--repo", type=Path, default=Path(), metavar="DIR", help="default: .")
    return parser


def _now(text: str | None, wall_clock: datetime) -> datetime:
    if text is None:
        return wall_clock
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise UsageError("--now is not an ISO 8601 time") from None


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:  # argparse exits 2 on a usage error, 0 for --help
        return exc.code if isinstance(exc.code, int) else 2
    wall_clock = datetime.now(UTC)
    try:
        config = RunConfig(
            out=args.out,
            repo=args.repo,
            now=_now(args.now, wall_clock),
            wall_clock=wall_clock,
            environ=os.environ,
            offline=args.offline,
            dry_run=args.dry_run,
        )
        result = run(config)
    except UsageError as error:
        print(error, file=sys.stderr)
        return 2
    except TrustBundleError as error:
        print(error, file=sys.stderr)
        # The message holds the bundle's path; only the variable's name is recorded.
        recorded = stored_json({"variable": error.variable})
        write_atomic(args.out / "rejected" / "trust_error.json", recorded)
        return 1
    print(f"{result.outcome}, verdict {result.verdict}, {result.feed_bytes} feed bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
