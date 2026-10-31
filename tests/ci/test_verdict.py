from pathlib import Path

import pytest

from elections_calendar.ci.verdict import FinalVerdict, final_verdict, state_from, summary_text
from elections_calendar.publish import write_manifest
from tests.support.ci import make_artifact, run_env, write_json

FEAT = "refs/heads/feat/x"
HINT = (
    "main moved during the run: start a new workflow_dispatch on main with publish: true "
    "(a re-run keeps the old commit)"
)
SKIPPED = {"SCRAPE_RESULT": "skipped", "PUBLISH_RESULT": "skipped"}
NOT_PUBLISHED = {"PUBLISH_RESULT": "skipped", "PUBLISH_OUTCOME": "", "SERVED": ""}


def _artifact(root: Path, kind: str) -> Path:
    """The artifact a matrix row runs against."""
    if kind == "none":
        root.mkdir()
    elif kind == "green":
        make_artifact(root)
    elif kind == "red":
        make_artifact(root, verdict="red")
    elif kind == "failed":
        make_artifact(root, verdict="red", outcome="validation_failed")
    elif kind == "dry":
        make_artifact(root, dry_run=True)
    elif kind == "stale":
        make_artifact(root)
        (root / "HEALTH.md").write_text("changed after the manifest", encoding="utf-8")
    elif kind == "no-verdict":
        make_artifact(root)
        (root / "verdict.json").unlink()
        (root / "manifest.json").unlink()
        write_manifest(root)
    else:
        raise AssertionError(kind)
    return root


# (id, env overrides, artifact kind, green, headline)
ROWS = [
    (
        "r01-push-branch",
        {
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": FEAT,
            **SKIPPED,
            "PAUSED": "",
            "ALERT_TEST": "",
            "PUBLISH_OUTCOME": "",
            "SERVED": "",
        },
        "none",
        True,
        "gates only",
    ),
    (
        "r02-push-main",
        {
            "GITHUB_EVENT_NAME": "push",
            **SKIPPED,
            "PAUSED": "",
            "ALERT_TEST": "",
            "PUBLISH_OUTCOME": "",
            "SERVED": "",
        },
        "none",
        True,
        "gates only",
    ),
    (
        "r03-push-gates-failed",
        {"GITHUB_EVENT_NAME": "push", "GATES_RESULT": "failure", **SKIPPED},
        "none",
        False,
        "gates failed",
    ),
    (
        "r04-schedule-gates-failed",
        {"GATES_RESULT": "failure", **SKIPPED},
        "none",
        False,
        "gates failed",
    ),
    ("r05-paused", {"PAUSED": "true", **NOT_PUBLISHED}, "none", True, "paused"),
    (
        "r06-scrape-failed",
        {"SCRAPE_RESULT": "failure", "PUBLISH_RESULT": "skipped"},
        "none",
        False,
        "scrape failed",
    ),
    (
        "r07-scrape-cancelled",
        {"SCRAPE_RESULT": "cancelled", "PUBLISH_RESULT": "skipped"},
        "none",
        False,
        "scrape failed",
    ),
    ("r08-no-verdict-json", {}, "no-verdict", False, "artifact incomplete"),
    ("r09-file-changed", {}, "stale", False, "artifact incomplete"),
    ("r10-published-green", {}, "green", True, "published"),
    ("r11-published-red", {}, "red", False, "published with open warnings or errors"),
    (
        "r12-validation-failed",
        {"PUBLISH_OUTCOME": "validation_failed", "SERVED": "not_checked"},
        "failed",
        False,
        "validation failed",
    ),
    (
        "r13-superseded",
        {"PUBLISH_OUTCOME": "superseded", "SERVED": "not_checked"},
        "green",
        False,
        "superseded",
    ),
    ("r14-served-mismatch", {"SERVED": "served_mismatch"}, "green", False, "served_mismatch"),
    (
        "r15-git-failed",
        {"PUBLISH_OUTCOME": "git_failed", "SERVED": "not_checked"},
        "green",
        False,
        "git failed",
    ),
    (
        "r16-refused",
        {"PUBLISH_OUTCOME": "refused", "SERVED": "not_checked"},
        "green",
        False,
        "artifact refused",
    ),
    (
        "r17-publish-cancelled",
        {"PUBLISH_RESULT": "cancelled", "PUBLISH_OUTCOME": "", "SERVED": ""},
        "green",
        False,
        "publish failed",
    ),
    ("r18-alert-test", {"ALERT_TEST": "true"}, "green", False, "alert test"),
    (
        "r19-alert-test-paused",
        {"ALERT_TEST": "true", "PAUSED": "true", **NOT_PUBLISHED},
        "none",
        False,
        "alert test",
    ),
    (
        "r20-branch-dispatch-healthy",
        {
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": FEAT,
            "INPUT_PUBLISH": "true",
            **NOT_PUBLISHED,
        },
        "green",
        True,
        "not published: no new unacknowledged issues",
    ),
    (
        "r21-branch-dispatch-red",
        {
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_REF": FEAT,
            "INPUT_PUBLISH": "true",
            **NOT_PUBLISHED,
        },
        "red",
        False,
        "not published: open warnings or errors",
    ),
    (
        "r22-main-dispatch-false",
        {"GITHUB_EVENT_NAME": "workflow_dispatch", "INPUT_PUBLISH": "false", **NOT_PUBLISHED},
        "green",
        True,
        "not published: no new unacknowledged issues",
    ),
    (
        "r23-main-dispatch-published",
        {"GITHUB_EVENT_NAME": "workflow_dispatch", "INPUT_PUBLISH": "true"},
        "green",
        True,
        "published",
    ),
    (
        "r24-main-dispatch-yes",
        {"GITHUB_EVENT_NAME": "workflow_dispatch", "INPUT_PUBLISH": "yes", **NOT_PUBLISHED},
        "green",
        True,
        "not published: no new unacknowledged issues",
    ),
    (
        "r25-publish-outside-context",
        {
            "GITHUB_EVENT_NAME": "workflow_dispatch",
            "INPUT_PUBLISH": "no",
            "PUBLISH_OUTCOME": "",
            "SERVED": "",
        },
        "green",
        False,
        "publish ran outside its context",
    ),
    ("r26-dry-run", {}, "dry", False, "dry-run artifact"),
    (
        "r27-not-published-validation-failed",
        {"GITHUB_REF": FEAT, **NOT_PUBLISHED},
        "failed",
        False,
        "validation failed (not published)",
    ),
    ("r28-publish-disagrees", {}, "failed", False, "publish disagrees with verdict.json"),
    ("r29-paused-but-published", {"PAUSED": "true"}, "green", False, "publish ran while paused"),
    (
        "r30-publish-refused-its-context",
        {"PUBLISH_OUTCOME": "not_allowed", "SERVED": "not_checked"},
        "green",
        False,
        "publish refused its context",
    ),
    (
        "r31-push-with-a-scrape",
        {"GITHUB_EVENT_NAME": "push", "PUBLISH_RESULT": "skipped"},
        "none",
        False,
        "unexpected jobs on a push",
    ),
    (
        "r32-push-alert-test-stays-green",
        {"GITHUB_EVENT_NAME": "push", **SKIPPED, "ALERT_TEST": "true"},
        "none",
        True,
        "gates only",
    ),
]


@pytest.mark.parametrize(
    ("overrides", "kind", "green", "headline"),
    [pytest.param(*row[1:], id=row[0]) for row in ROWS],
)
def test_outcome_matrix(
    tmp_path: Path, overrides: dict[str, str], kind: str, green: bool, headline: str
) -> None:
    artifact = _artifact(tmp_path / "artifact", kind)
    final = final_verdict(state_from(run_env(**overrides), artifact))
    assert (final.green, final.headline) == (green, headline)


def test_superseded_names_the_new_dispatch(tmp_path: Path) -> None:
    env = run_env(PUBLISH_OUTCOME="superseded", SERVED="not_checked")
    final = final_verdict(state_from(env, _artifact(tmp_path / "a", "green")))
    assert final.details == (HINT,)


def test_alert_test_keeps_the_replaced_headline_first(tmp_path: Path) -> None:
    env = run_env(ALERT_TEST="true", PAUSED="true", **NOT_PUBLISHED)
    final = final_verdict(state_from(env, _artifact(tmp_path / "a", "none")))
    assert final.details == ("paused",)


def test_alert_test_does_not_hide_early_failures(tmp_path: Path) -> None:
    env = run_env(ALERT_TEST="true", SCRAPE_RESULT="failure")
    final = final_verdict(state_from(env, _artifact(tmp_path / "a", "none")))
    assert (final.green, final.headline) == (False, "scrape failed")


@pytest.mark.parametrize(
    ("overrides", "headline"),
    [
        pytest.param({"GATES_RESULT": ""}, "unknown state: GATES_RESULT", id="gates-empty"),
        pytest.param({"GATES_RESULT": "ok"}, "unknown state: GATES_RESULT", id="gates-ok"),
        pytest.param({"SCRAPE_RESULT": "banana"}, "unknown state: SCRAPE_RESULT", id="scrape"),
        pytest.param({"PUBLISH_RESULT": "banana"}, "unknown state: PUBLISH_RESULT", id="publish"),
        pytest.param(
            {"GITHUB_EVENT_NAME": "pull_request"}, "unknown state: GITHUB_EVENT_NAME", id="event"
        ),
        pytest.param({"PAUSED": ""}, "unknown state: PAUSED", id="paused-empty"),
        pytest.param({"PAUSED": "yes"}, "unknown state: PAUSED", id="paused-yes"),
        pytest.param({"ALERT_TEST": ""}, "unknown state: ALERT_TEST", id="alert-empty"),
        pytest.param({"ALERT_TEST": "maybe"}, "unknown state: ALERT_TEST", id="alert-maybe"),
        pytest.param({"PUBLISH_OUTCOME": "banana"}, "unknown state: PUBLISH_OUTCOME", id="outcome"),
        pytest.param({"PUBLISH_OUTCOME": ""}, "unknown state: PUBLISH_OUTCOME", id="outcome-empty"),
        pytest.param({"SERVED": ""}, "unknown state: SERVED", id="served-empty"),
        pytest.param({"SERVED": "OK"}, "unknown state: SERVED", id="served-upper"),
    ],
)
def test_unknown_states_are_red(tmp_path: Path, overrides: dict[str, str], headline: str) -> None:
    artifact = _artifact(tmp_path / "a", "green")
    final = final_verdict(state_from(run_env(**overrides), artifact))
    assert (final.green, final.headline) == (False, headline)


@pytest.mark.parametrize(
    ("overrides", "headline"),
    [
        pytest.param(
            {"GITHUB_EVENT_NAME": "pull_request", "GATES_RESULT": "banana"},
            "unknown state: GITHUB_EVENT_NAME",
            id="event-before-gates",
        ),
        pytest.param(
            {"GATES_RESULT": "banana", "SCRAPE_RESULT": "banana"},
            "unknown state: GATES_RESULT",
            id="gates-before-scrape",
        ),
        pytest.param(
            {"PAUSED": "banana", "PUBLISH_OUTCOME": "banana"},
            "unknown state: PAUSED",
            id="paused-before-outcome",
        ),
    ],
)
def test_the_first_unknown_state_wins(
    tmp_path: Path, overrides: dict[str, str], headline: str
) -> None:
    final = final_verdict(state_from(run_env(**overrides), tmp_path))
    assert (final.green, final.headline) == (False, headline)


def test_unknown_state_shows_its_value_cut(tmp_path: Path) -> None:
    env = run_env(GATES_RESULT="y" * 300)
    final = final_verdict(state_from(env, tmp_path))
    assert final.details == ("y" * 100,)


def test_unknown_job_result_is_not_success(tmp_path: Path) -> None:
    final = final_verdict(state_from(run_env(GATES_RESULT="succes"), tmp_path))
    assert (final.green, final.headline) == (False, "unknown state: GATES_RESULT")


def test_state_from_reads_the_environment(tmp_path: Path) -> None:
    state = state_from({"GITHUB_EVENT_NAME": "push", "SERVED": "ok"}, tmp_path)
    assert (state.event, state.served, state.gates, state.artifact) == ("push", "ok", "", tmp_path)


@pytest.mark.parametrize(
    "kind",
    ["not-json", "list", "no-outcome", "case", "dry-string", "dry-zero", "dry-one", "bad-outcome"],
)
def test_malformed_verdict_json_is_red(tmp_path: Path, kind: str) -> None:
    root = make_artifact(tmp_path / "a")
    good = {"verdict": "green", "outcome": "published", "dry_run": False}
    bodies: dict[str, object] = {
        "list": [],
        "no-outcome": {"verdict": "green", "dry_run": False},
        "case": {**good, "verdict": "GREEN"},
        "dry-string": {**good, "dry_run": "false"},
        "dry-zero": {**good, "dry_run": 0},
        "dry-one": {**good, "dry_run": 1},
        "bad-outcome": {**good, "outcome": "superseded"},
    }
    if kind == "not-json":
        (root / "verdict.json").write_text("{", encoding="utf-8")
    else:
        write_json(root / "verdict.json", bodies[kind])
    write_manifest(root)
    final = final_verdict(state_from(run_env(), root))
    assert (final.green, final.headline) == (False, "verdict.json is malformed")


def test_artifact_incomplete_names_the_problem(tmp_path: Path) -> None:
    root = make_artifact(tmp_path / "a")
    (root / "HEALTH.md").write_text("changed", encoding="utf-8")
    final = final_verdict(state_from(run_env(), root))
    assert final.details == ("a file does not match the manifest: 'HEALTH.md'",)


def test_summary_text(tmp_path: Path) -> None:
    final = FinalVerdict(False, "alert test", ("main moved: [x]\n# h",))
    state = state_from(run_env(), tmp_path)
    lines = summary_text(final, state).splitlines()
    assert lines[0] == "## Verdict: red, alert test"
    assert "- main moved\\: \\[x\\] \\# h" in lines
    assert "| publish outcome | published |" in lines
    assert (
        summary_text(FinalVerdict(True, "paused", ()), state_from({}, tmp_path)).count("| none |")
        == 5
    )


NESTED = b"[" * 100_000 + b"]" * 100_000


def test_deeply_nested_verdict_json_is_malformed(tmp_path: Path) -> None:
    root = make_artifact(tmp_path / "a")
    (root / "verdict.json").write_bytes(NESTED)
    write_manifest(root)
    final = final_verdict(state_from(run_env(), root))
    assert (final.green, final.headline) == (False, "verdict.json is malformed")


def test_deeply_nested_manifest_is_malformed(tmp_path: Path) -> None:
    root = make_artifact(tmp_path / "a")
    (root / "manifest.json").write_bytes(NESTED)
    final = final_verdict(state_from(run_env(), root))
    assert (final.green, final.headline) == (False, "artifact incomplete")
    assert final.details == ("manifest.json is malformed",)
