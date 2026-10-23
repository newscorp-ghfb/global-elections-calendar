"""The vocabularies of the workflow and the one rule on where it may publish (Plan 5a)."""

from typing import Final

MAIN_REF: Final = "refs/heads/main"
EVENTS: Final = ("push", "schedule", "workflow_dispatch")
JOB_RESULTS: Final = ("success", "failure", "cancelled", "skipped")
SWITCH_VALUES: Final = ("true", "false")
PUBLISH_OUTCOMES: Final = (
    "published",
    "validation_failed",
    "superseded",
    "refused",
    "git_failed",
    "not_allowed",
)
SERVED_RESULTS: Final = ("ok", "served_mismatch", "not_checked")


def publishing_allowed(event: str, ref: str, publish_input: str) -> bool:
    """True on ``main``, for the schedule or for a dispatch whose input is exactly ``true``."""
    if ref != MAIN_REF:
        return False
    return event == "schedule" or (event == "workflow_dispatch" and publish_input == "true")
