import pytest

from elections_calendar.ci.context import publishing_allowed

MAIN = "refs/heads/main"
FEAT = "refs/heads/feat/x"


@pytest.mark.parametrize(
    ("event", "ref", "publish_input", "expected"),
    [
        ("schedule", MAIN, "", True),
        ("schedule", FEAT, "", False),
        ("workflow_dispatch", MAIN, "true", True),
        ("workflow_dispatch", MAIN, "false", False),
        ("workflow_dispatch", MAIN, "True", False),
        ("workflow_dispatch", MAIN, "", False),
        ("workflow_dispatch", MAIN, " true", False),
        ("workflow_dispatch", FEAT, "true", False),
        ("push", MAIN, "true", False),
        ("schedule", "refs/heads/main2", "", False),
        ("schedule", "refs/tags/main", "", False),
    ],
)
def test_publishing_allowed(event: str, ref: str, publish_input: str, expected: bool) -> None:
    assert publishing_allowed(event, ref, publish_input) is expected
