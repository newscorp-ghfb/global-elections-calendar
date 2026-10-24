"""``python -m elections_calendar.ci <command>``: what the workflow's steps call (P117).

``switches`` and ``scrape-summary`` write side outputs; the verdict never depends on them.
Heavier commands (Task 6) import their modules inside their handlers, so these stay light.
"""

import argparse
import hashlib
import os
import re
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
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


def _publish(args: argparse.Namespace) -> int:
    from elections_calendar.ci import publishing
    from elections_calendar.ci.context import publishing_allowed
    from elections_calendar.ci.git import Git
    from elections_calendar.fetch import Deadline
    from elections_calendar.text import md_text

    output = _env_path("GITHUB_OUTPUT")
    if output is None:
        print("GITHUB_OUTPUT is not set", file=sys.stderr)
        return 2
    env = os.environ
    git = Git(args.repo, deadline=Deadline.after(publishing.PUBLISH_STAGE_S))
    code_sha = env.get("GITHUB_SHA", "")
    allowed = publishing_allowed(
        env.get("GITHUB_EVENT_NAME", ""), env.get("GITHUB_REF", ""), env.get("INPUT_PUBLISH", "")
    )
    if allowed and not re.fullmatch(r"[0-9a-f]{40}", code_sha):
        result = publishing.PublishResult(
            "refused", "not_checked", None, "GITHUB_SHA is not a commit SHA"
        )
    else:
        with tempfile.TemporaryDirectory() as workdir:
            fetch = (
                publishing.served_fetcher(env, workdir=Path(workdir))
                if allowed
                else _no_fetch
            )
            result = publishing.publish(
                args.artifact,
                git,
                code_sha=code_sha,
                allowed=allowed,
                wall_clock=datetime.now(UTC),
                fetch=fetch,
                sleep=time.sleep,
                clock=time.monotonic,
            )
    write_outputs(output, {"outcome": result.outcome, "served": result.served})
    summary = _env_path("GITHUB_STEP_SUMMARY")
    if summary is not None:
        head = f"## Publish: {result.outcome}, served {result.served}"
        lines = [head]
        if result.detail != result.commit:  # a published run's detail is the commit: show it once
            lines += ["", md_text(result.detail)]
        if result.commit is not None:
            lines += ["", f"Commit: `{result.commit}`"]
        append_summary(summary, "\n".join(lines) + "\n")
    return 0


def _no_fetch(timeout_s: float) -> bytes | None:
    raise AssertionError("nothing is fetched when publishing is not allowed")


def _adopt(args: argparse.Namespace) -> int:
    from elections_calendar.ci.artifact import (
        ArtifactError,
        copy_repository_files,
        load_artifact,
        served_link_problems,
    )

    approved: str = args.manifest_sha256
    if not re.fullmatch(r"[0-9a-f]{64}", approved):
        print("--manifest-sha256 must be 64 lowercase hex characters", file=sys.stderr)
        return 2
    try:
        actual = hashlib.sha256((args.artifact / "manifest.json").read_bytes()).hexdigest()
    except OSError:
        print("manifest.json is missing", file=sys.stderr)
        return 1
    if actual != approved:
        print(f"the artifact is not the approved one: its manifest is {actual}", file=sys.stderr)
        return 1
    try:
        artifact = load_artifact(args.artifact, code_sha=None, wall_clock=datetime.now(UTC))
    except ArtifactError as exc:
        print(exc, file=sys.stderr)
        return 1
    if artifact.outcome != "published":
        print("only a published artifact has baselines", file=sys.stderr)
        return 1
    problems = served_link_problems(artifact, lambda source: None)
    if problems:
        print(problems[0], file=sys.stderr)
        return 1
    if os.path.lexists(args.repo / "data" / "sources"):
        print(
            "data/sources already exists: the first baselines are adopted once", file=sys.stderr
        )
        return 1
    copied = copy_repository_files(
        artifact, args.repo, only=lambda path: path.startswith("data/sources/")
    )
    for path in copied:
        print(path)
    run_sha = artifact.status["code_sha"]
    print(f"adopted {len(copied)} files from the run of {run_sha} (manifest {approved})")
    return 0


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
    publish = add("publish", _publish)
    publish.add_argument("--artifact", type=Path, required=True, metavar="DIR")
    publish.add_argument("--repo", type=Path, required=True, metavar="DIR")
    adopt = add("adopt", _adopt)
    adopt.add_argument("--artifact", type=Path, required=True, metavar="DIR")
    adopt.add_argument("--manifest-sha256", required=True, metavar="HEX")
    adopt.add_argument("--repo", type=Path, default=Path(), metavar="DIR")
    return parser, handlers


def main(argv: Sequence[str] | None = None) -> int:
    parser, handlers = _parser()
    args = parser.parse_args(argv)
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
