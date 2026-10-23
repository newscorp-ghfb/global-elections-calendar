"""Small artifacts and run environments for the CI tests (Plan 5a Task 5)."""

import json
from pathlib import Path

from elections_calendar.model import stored_json
from elections_calendar.publish import write_manifest
from elections_calendar.text import md_text

REASON = "x\nserved=ok\noutcome=published\n::set-output name=served::ok ${{ secrets.GITHUB_TOKEN }}"
MAIN = "refs/heads/main"


def make_artifact(
    root: Path,
    *,
    verdict: str = "green",
    outcome: str = "published",
    dry_run: object = False,
    reason: str = "relevant units unparsed: 1",
) -> Path:
    """``verdict.json``, ``HEALTH.md`` and a manifest written by ``publish.write_manifest``."""
    root.mkdir(parents=True, exist_ok=True)
    data = {
        "verdict": verdict,
        "outcome": outcome,
        "reasons": [{"source": "osce", "code": "unparsed_relevant", "text": reason}],
        "dry_run": dry_run,
        "requests": None,
    }
    (root / "verdict.json").write_bytes(stored_json(data))
    health = f"# Elections calendar health\n\n- Outcome: {outcome}\n- Reason: {md_text(reason)}\n"
    (root / "HEALTH.md").write_bytes(health.encode("utf-8"))
    write_manifest(root)
    return root


def run_env(**overrides: str) -> dict[str, str]:
    """A scheduled run on main that published and was served, unless ``overrides`` say otherwise."""
    env = {
        "GITHUB_EVENT_NAME": "schedule",
        "GITHUB_REF": MAIN,
        "INPUT_PUBLISH": "",
        "GATES_RESULT": "success",
        "SCRAPE_RESULT": "success",
        "PUBLISH_RESULT": "success",
        "PAUSED": "false",
        "ALERT_TEST": "false",
        "PUBLISH_OUTCOME": "published",
        "SERVED": "ok",
    }
    env.update(overrides)
    return env


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
