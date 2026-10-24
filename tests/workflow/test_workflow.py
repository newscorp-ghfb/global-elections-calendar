"""The workflow's structure (Plan 5a Task 7): permissions, pins, conditions, wiring, budgets.

The workflow is proven offline here: GitHub's own evaluation of ``if:`` expressions and
outputs first runs in Plan 5c's branch run.
"""

import inspect
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from elections_calendar.ci import publishing
from elections_calendar.ci.context import EVENTS, MAIN_REF, publishing_allowed
from elections_calendar.ci.git import Git
from elections_calendar.ci.summary import OUTPUT_VALUES
from elections_calendar.fetch import SCRAPE_DEADLINE_S
from elections_calendar.runner import run_sources

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "update-elections.yml"
TEXT = WORKFLOW.read_text(encoding="utf-8")

SETUP_ALLOWANCE_S = 300  # checkout, Python, pip install; measured on the first branch run in 5c
PARSE_ALLOWANCE_S = 60  # about 1 s on the fixtures
UPLOAD_ALLOWANCE_S = 60  # the artifact: 4.6 MB, plus at most 50 MiB of rejected/pages/
DOWNLOAD_ALLOWANCE_S = 60
REPORT_ALLOWANCE_S = 30  # outputs and the summary

PINS = {
    "actions/checkout": ("3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
    "actions/setup-python": ("5fda3b95a4ea91299a34e894583c3862153e4b97", "v7.0.0"),
    "actions/upload-artifact": ("cf430e030ddbb5b0abf93d22962f4752f3646cd9", "v7.0.2"),
    "actions/download-artifact": ("9000827ccba6bdab643e8b6fd33ac0654aef8333", "v8.0.2"),
}
PUBLISH_IF = (
    "needs.scrape.result == 'success' && needs.scrape.outputs.paused != 'true' && "
    "github.ref == 'refs/heads/main' && (github.event_name == 'schedule' || "
    "(github.event_name == 'workflow_dispatch' && inputs.publish == true))"
)
ARTIFACT_DIR = "${{ runner.temp }}/artifact"


def load() -> dict[Any, Any]:
    data = yaml.safe_load(TEXT)
    assert isinstance(data, dict)
    return data


def jobs() -> dict[str, dict[str, Any]]:
    found = load()["jobs"]
    assert isinstance(found, dict)
    return found


def steps(job: str) -> list[dict[str, Any]]:
    found = jobs()[job]["steps"]
    assert isinstance(found, list)
    return found


def step(job: str, name: str) -> dict[str, Any]:
    (found,) = [s for s in steps(job) if s.get("name") == name]
    return found


def all_steps() -> Iterator[tuple[str, dict[str, Any]]]:
    for job in jobs():
        for one in steps(job):
            yield job, one


def collapse(text: str) -> str:
    return " ".join(text.split())


def test_triggers() -> None:
    triggers = load()[True]  # YAML 1.1 reads the key `on` as True
    assert set(triggers) == {"push", "schedule", "workflow_dispatch"}
    assert triggers["push"] == {"branches": ["**"]}
    assert triggers["schedule"] == [{"cron": "0 0 * * *"}]
    inputs = triggers["workflow_dispatch"]["inputs"]
    assert set(inputs) == {"publish"}
    assert inputs["publish"]["type"] == "boolean"
    assert inputs["publish"]["default"] is False


def test_permissions_are_least() -> None:
    assert load()["permissions"] == {}
    assert jobs()["gates"]["permissions"] == {"contents": "read"}
    assert jobs()["scrape"]["permissions"] == {"contents": "read"}
    assert jobs()["verdict"]["permissions"] == {"contents": "read"}
    assert jobs()["publish"]["permissions"] == {"contents": "write"}
    assert set(jobs()) == {"gates", "scrape", "publish", "verdict"}
    # the Scrape step's own `secrets.token_hex` is Python's module, not the secrets context
    assert not re.search(r"\$\{\{[^}]*\bsecrets\b", TEXT)
    assert "secrets:" not in TEXT
    assert "GITHUB_TOKEN" not in TEXT


def test_actions_are_pinned() -> None:
    lines = [line for line in TEXT.splitlines() if "uses:" in line]
    assert len(lines) == 11
    for line in lines:
        found = re.fullmatch(
            r"\s*(?:- )?uses: ([a-z-]+/[a-z-]+)@([0-9a-f]{40})  # (v[0-9][0-9.]*)", line
        )
        assert found, line
        assert PINS[found[1]] == (found[2], found[3])


def test_python_and_runner_are_pinned() -> None:
    setups = [one for _, one in all_steps() if str(one.get("uses", "")).startswith("actions/setup")]
    assert len(setups) == 4
    assert all(one["with"]["python-version"] == "3.14.1" for one in setups)
    assert {job["runs-on"] for job in jobs().values()} == {"ubuntu-24.04"}


def test_job_conditions() -> None:
    found = jobs()
    assert "needs" not in found["gates"]
    assert "if" not in found["gates"]
    assert found["scrape"]["needs"] == "gates"
    assert found["scrape"]["if"] == "github.event_name != 'push'"
    assert found["publish"]["needs"] == "scrape"
    assert collapse(found["publish"]["if"]) == PUBLISH_IF
    assert found["verdict"]["needs"] == ["gates", "scrape", "publish"]
    assert found["verdict"]["if"] == "always()"
    conditions = [str(job["if"]) for job in found.values() if "if" in job]
    conditions += [str(one["if"]) for _, one in all_steps() if "if" in one]
    assert not [c for c in conditions if "cancelled()" in c or "failure()" in c]
    # publishing is reached only from main and the two events publishing_allowed names
    assert re.findall(r"github\.ref == '([^']*)'", found["publish"]["if"]) == [MAIN_REF]
    named = set(re.findall(r"github\.event_name == '([^']*)'", found["publish"]["if"]))
    allowed = {event for event in EVENTS if publishing_allowed(event, MAIN_REF, "true")}
    assert named == allowed == {"schedule", "workflow_dispatch"}


def test_concurrency() -> None:
    assert "concurrency" not in load()
    assert jobs()["publish"]["concurrency"] == {
        "group": "publish-elections",
        "cancel-in-progress": False,
    }
    assert [name for name, job in jobs().items() if "concurrency" in job] == ["publish"]


def test_read_only_jobs_do_not_persist_credentials() -> None:
    for job in ("gates", "scrape", "verdict"):
        (checkout,) = [
            s for s in steps(job) if str(s.get("uses", "")).startswith("actions/checkout")
        ]
        assert checkout["with"] == {"persist-credentials": False}, job
    (checkout,) = [
        s for s in steps("publish") if str(s.get("uses", "")).startswith("actions/checkout")
    ]
    assert "with" not in checkout  # it needs the token to push


def _expression_strings() -> Iterator[str]:
    """Every string in the places that may hold an expression."""
    for job in jobs().values():
        yield str(job.get("if", ""))
        yield from map(str, job.get("outputs", {}).values())
        for one in job["steps"]:
            yield str(one.get("if", ""))
            yield from map(str, one.get("env", {}).values())
            yield from map(str, one.get("with", {}).values())


def test_no_expression_in_run_scripts() -> None:
    for job, one in all_steps():
        assert "${{" not in str(one.get("run", "")), (job, one.get("name"))
    # every expression in the file is in an env:, with:, outputs: or if: value
    placed = sum(text.count("${{") for text in _expression_strings())
    assert placed == TEXT.count("${{") > 0


def test_scrape_logs_stop_workflow_commands() -> None:
    script = step("scrape", "Scrape")["run"]
    needles = [
        "secrets.token_hex",
        'echo "::stop-commands::${token}"',
        "scraper.py --live --out out",
        'echo "::${token}::"',
        'exit "${code}"',
    ]
    positions = [script.find(needle) for needle in needles]
    assert -1 not in positions
    assert positions == sorted(positions)


def test_light_steps_use_setup_python() -> None:
    for job, name, command in (
        ("scrape", "Switches", "switches"),
        ("scrape", "Summary", "scrape-summary"),
        ("verdict", "Verdict", "verdict"),
    ):
        run = step(job, name)["run"]
        assert run.startswith(f"python -m elections_calendar.ci {command} "), run
        assert ".venv" not in run
    assert step("publish", "Publish")["run"].startswith(
        ".venv/bin/python -m elections_calendar.ci publish "
    )
    assert not [s for s in steps("verdict") if "Install" in str(s.get("name"))]
    assert not [s for s in steps("verdict") if "pip" in str(s.get("run", ""))]


def test_artifact_wiring() -> None:
    uploads = [s for _, s in all_steps() if str(s.get("uses", "")).startswith("actions/upload")]
    assert len(uploads) == 1
    assert uploads[0]["with"] == {
        "name": "generation",
        "path": "out/",
        "retention-days": 14,
        "if-no-files-found": "error",
    }
    assert uploads[0]["if"] == "always() && steps.switches.outputs.paused != 'true'"
    downloads = [
        (j, s) for j, s in all_steps() if str(s.get("uses", "")).startswith("actions/down")
    ]
    assert [j for j, _ in downloads] == ["publish", "verdict"]
    for _, one in downloads:
        assert one["with"] == {"name": "generation", "path": ARTIFACT_DIR}
    assert "continue-on-error" not in downloads[0][1]
    assert downloads[1][1]["continue-on-error"] is True
    for job, name in (("publish", "Publish"), ("verdict", "Verdict")):
        assert '--artifact "${RUNNER_TEMP}/artifact"' in step(job, name)["run"]


def test_outputs_wiring() -> None:
    scrape = jobs()["scrape"]["outputs"]
    assert scrape == {
        "paused": "${{ steps.switches.outputs.paused }}",
        "alert_test": "${{ steps.switches.outputs.alert_test }}",
    }
    publish = jobs()["publish"]["outputs"]
    assert publish == {
        "outcome": "${{ steps.publish.outputs.outcome }}",
        "served": "${{ steps.publish.outputs.served }}",
    }
    assert step("scrape", "Switches")["id"] == "switches"
    assert step("publish", "Publish")["id"] == "publish"
    assert set(scrape) | set(publish) <= set(OUTPUT_VALUES)
    assert step("verdict", "Verdict")["env"] == {
        "INPUT_PUBLISH": "${{ inputs.publish }}",
        "GATES_RESULT": "${{ needs.gates.result }}",
        "SCRAPE_RESULT": "${{ needs.scrape.result }}",
        "PUBLISH_RESULT": "${{ needs.publish.result }}",
        "PAUSED": "${{ needs.scrape.outputs.paused }}",
        "ALERT_TEST": "${{ needs.scrape.outputs.alert_test }}",
        "PUBLISH_OUTCOME": "${{ needs.publish.outputs.outcome }}",
        "SERVED": "${{ needs.publish.outputs.served }}",
    }
    assert step("publish", "Publish")["env"] == {"INPUT_PUBLISH": "${{ inputs.publish }}"}


def _readme_linux_block() -> list[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    found = re.search(r"\*\*Linux \(CI\):\*\*\n\n```bash\n(.*?)```", readme, re.DOTALL)
    assert found
    return found[1].splitlines()


def test_gates_job_runs_the_canonical_gates() -> None:
    runs = [s for s in steps("gates") if "run" in s]
    assert runs[0]["name"] == "Install"
    after = runs[1:]
    assert [s["run"] for s in after] == [
        ".venv/bin/python -m playwright install chromium",
        ".venv/bin/python -m pytest -q",
        ".venv/bin/mypy",
        ".venv/bin/ruff check",
        ".venv/bin/lint-imports --config importlinter.ini",
        ".venv/bin/python -m scripts.prove_gates",
    ]
    assert after[1]["env"] == {"CI": "true"}
    assert all("env" not in s for s in after[2:])
    assert [s["run"] for s in after[1:5]] == _readme_linux_block()


def test_scrape_job_fits_its_timeout() -> None:
    grace = inspect.signature(run_sources).parameters["grace_s"].default
    total = SCRAPE_DEADLINE_S + grace + 2 + PARSE_ALLOWANCE_S + SETUP_ALLOWANCE_S
    total += UPLOAD_ALLOWANCE_S
    assert total <= 20 * 60
    assert jobs()["scrape"]["timeout-minutes"] == 20


def test_publish_job_fits_its_timeout() -> None:
    total = (
        SETUP_ALLOWANCE_S
        + DOWNLOAD_ALLOWANCE_S
        + publishing.PUBLISH_STAGE_S
        + publishing.SERVED_LIMIT_S
        + REPORT_ALLOWANCE_S
    )
    assert total <= 25 * 60
    assert jobs()["publish"]["timeout-minutes"] == 25
    assert jobs()["gates"]["timeout-minutes"] == 15
    assert jobs()["verdict"]["timeout-minutes"] == 5
    assert Git(Path(".")).timeout_s <= publishing.PUBLISH_STAGE_S
    assert publishing.SERVED_FETCH_S <= publishing.SERVED_POLL_S


def test_served_check_reads_the_extension_url() -> None:
    background = (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
    found = re.search(r'const DATA_URL\s*=\s*"([^"]*)"', background)
    assert found
    assert found[1] == publishing.RAW_URL
