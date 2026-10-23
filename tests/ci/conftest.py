"""Shared setup for the CI tests."""

import pytest


@pytest.fixture(autouse=True)
def only_local_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """The worktree's ``origin`` is the live repository, so no test may reach a remote."""
    monkeypatch.setenv("GIT_ALLOW_PROTOCOL", "file")
