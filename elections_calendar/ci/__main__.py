"""``python -m elections_calendar.ci <command>``: what the workflow's steps call (P117).

``switches`` and ``scrape-summary`` write side outputs; the verdict never depends on them.
Heavier commands (Task 6) import their modules inside their handlers, so these stay light.
"""

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from elections_calendar.ci.summary import append_summary, write_outputs
from elections_calendar.ci.switches import switches
from elections_calendar.ci.verdict import final_verdict, state_from, summary_text

_PAUSED_NOTE = (
    "## Paused\n\n`PAUSE_PUBLISHING` is on this commit: nothing is scraped or published.\n"
)
_ALERT_NOTE = (
    "## Alert test\n\n"
    "`ALERT_TEST` is on this commit: this run fails on purpose after it publishes.\n"
)
_NO_HEALTH = "## No HEALTH.md\n\nThe scrape stopped before it wrote one. See the job log.\n"

Handler = Callable[[argparse.Namespace], int]


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    return Path(value) if value else None


def _switches(args: argparse.Namespace) -> int:
    output = _env_path("GITHUB_OUTPUT")
    if output is None:
        print("GITHUB_OUTPUT is not set", file=sys.stderr)
        return 2
    found = switches(args.repo)
    write_outputs(output, found)
    summary = _env_path("GITHUB_STEP_SUMMARY")
    if summary is not None:
        if found["paused"] == "true":
            append_summary(summary, _PAUSED_NOTE)
        if found["alert_test"] == "true":
            append_summary(summary, _ALERT_NOTE)
    return 0


def _scrape_summary(args: argparse.Namespace) -> int:
    summary = _env_path("GITHUB_STEP_SUMMARY")
    if summary is None:
        print("GITHUB_STEP_SUMMARY is not set", file=sys.stderr)
        return 2
    health = args.out / "HEALTH.md"
    if health.is_file() and not health.is_symlink():
        append_summary(summary, health.read_bytes().decode("utf-8", errors="replace"))
    else:
        append_summary(summary, _NO_HEALTH)
    return 0


def _verdict(args: argparse.Namespace) -> int:
    state = state_from(os.environ, args.artifact)
    final = final_verdict(state)
    summary = _env_path("GITHUB_STEP_SUMMARY")
    if summary is not None:  # a side output: the verdict never depends on it
        append_summary(summary, summary_text(final, state))
    print(f"Verdict: {'green' if final.green else 'red'}, {final.headline}")
    return 0 if final.green else 1


def _parser() -> tuple[argparse.ArgumentParser, dict[str, Handler]]:
    """The parser and the handler of each command; a handler may import heavier modules itself."""
    parser = argparse.ArgumentParser(prog="elections_calendar.ci")
    commands = parser.add_subparsers(dest="command", required=True)
    handlers: dict[str, Handler] = {}

    def add(name: str, handler: Handler) -> argparse.ArgumentParser:
        handlers[name] = handler
        return commands.add_parser(name)

    add("switches", _switches).add_argument("--repo", type=Path, required=True, metavar="DIR")
    add("scrape-summary", _scrape_summary).add_argument(
        "--out", type=Path, required=True, metavar="DIR"
    )
    add("verdict", _verdict).add_argument("--artifact", type=Path, required=True, metavar="DIR")
    return parser, handlers


def main(argv: Sequence[str] | None = None) -> int:
    parser, handlers = _parser()
    args = parser.parse_args(argv)
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
