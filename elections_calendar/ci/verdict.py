"""The verdict job's decision: one first-match table over the run's inputs (P121, NM-T05).

Unknown values fail closed: every input has a result, and anything else is red.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from elections_calendar.ci.context import (
    EVENTS,
    JOB_RESULTS,
    PUBLISH_OUTCOMES,
    SERVED_RESULTS,
    SWITCH_VALUES,
    publishing_allowed,
)
from elections_calendar.ci.manifest import ManifestError, read_manifest
from elections_calendar.text import md_text

_SUPERSEDED_HINT: Final = (
    "main moved during the run: start a new workflow_dispatch on main with publish: true "
    "(a re-run keeps the old commit)"
)
_OUTCOME_HEADLINES: Final = {
    "validation_failed": "validation failed",
    "refused": "artifact refused",
    "git_failed": "git failed",
    "not_allowed": "publish refused its context",
}
_SHOWN: Final = 100


@dataclass(frozen=True, slots=True)
class RunState:
    event: str
    ref: str
    publish_input: str
    gates: str
    scrape: str
    publish: str
    paused: str
    alert_test: str
    publish_outcome: str
    served: str
    artifact: Path


@dataclass(frozen=True, slots=True)
class FinalVerdict:
    green: bool
    headline: str
    details: tuple[str, ...]


def state_from(environ: Mapping[str, str], artifact: Path) -> RunState:
    """The run's state from the workflow's environment; a missing variable is ``""``."""

    def get(name: str) -> str:
        return environ.get(name, "")

    return RunState(
        event=get("GITHUB_EVENT_NAME"),
        ref=get("GITHUB_REF"),
        publish_input=get("INPUT_PUBLISH"),
        gates=get("GATES_RESULT"),
        scrape=get("SCRAPE_RESULT"),
        publish=get("PUBLISH_RESULT"),
        paused=get("PAUSED"),
        alert_test=get("ALERT_TEST"),
        publish_outcome=get("PUBLISH_OUTCOME"),
        served=get("SERVED"),
        artifact=artifact,
    )


def _red(headline: str, *details: str) -> FinalVerdict:
    return FinalVerdict(False, headline, details)


def _green(headline: str) -> FinalVerdict:
    return FinalVerdict(True, headline, ())


def _early(state: RunState) -> FinalVerdict | None:
    """Steps 0 to 4: the first that applies, or ``None`` when the run reached step 5."""
    checks = (  # step 0
        ("GITHUB_EVENT_NAME", state.event, EVENTS),
        ("GATES_RESULT", state.gates, JOB_RESULTS),
        ("SCRAPE_RESULT", state.scrape, JOB_RESULTS),
        ("PUBLISH_RESULT", state.publish, JOB_RESULTS),
        ("PAUSED", state.paused, (*SWITCH_VALUES, "")),
        ("ALERT_TEST", state.alert_test, (*SWITCH_VALUES, "")),
        ("PUBLISH_OUTCOME", state.publish_outcome, (*PUBLISH_OUTCOMES, "")),
        ("SERVED", state.served, (*SERVED_RESULTS, "")),
    )
    for name, value, allowed in checks:
        if value not in allowed:
            return _red(f"unknown state: {name}", value[:_SHOWN])
    if state.event == "push":  # step 1
        if state.gates != "success":
            return _red("gates failed")
        if state.scrape == "skipped" and state.publish == "skipped":
            return _green("gates only")
        return _red("unexpected jobs on a push")
    if state.gates != "success":  # step 2
        return _red("gates failed")
    if state.scrape != "success":  # step 3
        return _red("scrape failed", state.scrape)
    if state.paused == "":  # step 4
        return _red("unknown state: PAUSED")
    if state.alert_test == "":
        return _red("unknown state: ALERT_TEST")
    return None


def _data(artifact: Path) -> tuple[dict[str, Any] | None, FinalVerdict | None]:
    """Steps 6 and 7: the artifact's ``verdict.json``, or the red result that explains why not."""
    try:
        files = read_manifest(artifact)
    except ManifestError as problem:
        return None, _red("artifact incomplete", str(problem))
    if "verdict.json" not in files:
        return None, _red("artifact incomplete", "verdict.json is missing")
    try:
        data: Any = json.loads((artifact / "verdict.json").read_bytes().decode("utf-8"))
    except OSError, ValueError, RecursionError:
        data = None
    if isinstance(data, dict) and data.get("dry_run") is True:
        return None, _red("dry-run artifact")
    if not (
        isinstance(data, dict)
        and data.get("verdict") in ("green", "red")
        and data.get("outcome") in ("published", "validation_failed")
        and data.get("dry_run") is False
    ):
        return None, _red("verdict.json is malformed")
    return data, None


def _published(state: RunState, data: dict[str, Any]) -> FinalVerdict:
    """Step 10: the run published; the served check decides."""
    if state.served == "ok":
        if data["verdict"] == "green":
            return _green("published")
        return _red("published with open warnings or errors")
    if state.served == "served_mismatch":
        return _red("served_mismatch")
    return _red("unknown state: SERVED")


def _late(state: RunState) -> FinalVerdict:
    """Steps 5 to 13, for a run past the early checks."""
    if state.paused == "true":  # step 5
        if state.publish == "skipped":
            return _green("paused")
        return _red("publish ran while paused")
    data, problem = _data(state.artifact)  # steps 6 and 7
    if data is None:
        return problem or _red("artifact incomplete")
    if publishing_allowed(state.event, state.ref, state.publish_input):
        if state.publish != "success":  # step 8
            return _red("publish failed", state.publish)
        if (  # step 9
            state.publish_outcome in ("published", "validation_failed")
            and state.publish_outcome != data["outcome"]
        ):
            return _red("publish disagrees with verdict.json")
        if state.publish_outcome == "published":  # step 10
            return _published(state, data)
        if state.publish_outcome == "superseded":  # step 11
            return _red("superseded", _SUPERSEDED_HINT)
        if state.publish_outcome in _OUTCOME_HEADLINES:
            return _red(_OUTCOME_HEADLINES[state.publish_outcome])
        return _red("unknown state: PUBLISH_OUTCOME")
    if state.publish != "skipped":  # step 12
        return _red("publish ran outside its context")
    if data["outcome"] == "validation_failed":  # step 13
        return _red("validation failed (not published)")
    if data["verdict"] == "red":
        return _red("not published: open warnings or errors")
    return _green("not published: no new unacknowledged issues")


def final_verdict(state: RunState) -> FinalVerdict:
    """The run's verdict: the first table row that applies, then step 14 (``ALERT_TEST``)."""
    early = _early(state)
    if early is not None:
        return early
    result = _late(state)
    if state.alert_test == "true":  # step 14
        return _red("alert test", result.headline, *result.details)
    return result


def summary_text(final: FinalVerdict, state: RunState) -> str:
    """The step summary: the verdict line, its details and a table of the inputs."""
    lines = [f"## Verdict: {'green' if final.green else 'red'}, {final.headline}", ""]
    if final.details:
        lines += [f"- {md_text(detail)}" for detail in final.details]
        lines.append("")
    rows = (
        ("gates", state.gates),
        ("scrape", state.scrape),
        ("publish", state.publish),
        ("publish outcome", state.publish_outcome),
        ("served", state.served),
    )
    lines += ["| Input | Value |", "| --- | --- |"]
    lines += [f"| {name} | {md_text(value or 'none')} |" for name, value in rows]
    return "\n".join(lines) + "\n"
