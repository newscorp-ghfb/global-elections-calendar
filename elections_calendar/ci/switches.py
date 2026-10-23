"""The repository's two switch files (§11.1): present, whatever they hold."""

import os
from pathlib import Path


def switches(repo: Path) -> dict[str, str]:
    """``paused`` and ``alert_test`` as "true" or "false"; a dangling link counts."""

    def on(name: str) -> str:
        return "true" if os.path.lexists(repo / name) else "false"

    return {"paused": on("PAUSE_PUBLISHING"), "alert_test": on("ALERT_TEST")}
