"""Fixtures for the extension suite: one browser per extension for the session (about 2 s each)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page, Playwright

from tests.support.extension import Ext, extension_copy, launch


@pytest.fixture(scope="session")
def _working(playwright: Playwright, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Ext]:
    base = tmp_path_factory.mktemp("working-extension")
    running = launch(playwright, base / "profile", extension_copy(base / "ext", legacy=False))
    yield running
    running.close()


@pytest.fixture(scope="session")
def _legacy(playwright: Playwright, tmp_path_factory: pytest.TempPathFactory) -> Iterator[Ext]:
    base = tmp_path_factory.mktemp("legacy-extension")
    running = launch(playwright, base / "profile", extension_copy(base / "ext", legacy=True))
    yield running
    running.close()


@pytest.fixture
def ext(_working: Ext) -> Ext:
    _working.reset()
    return _working


@pytest.fixture
def legacy_ext(_legacy: Ext) -> Ext:
    _legacy.reset()
    return _legacy


@pytest.fixture
def fresh_ext(playwright: Playwright, tmp_path: Path) -> Iterator[Ext]:
    running = launch(playwright, tmp_path / "profile", extension_copy(tmp_path / "ext", legacy=False))
    yield running
    running.close()


@pytest.fixture(scope="session")
def lab(_working: Ext) -> Page:
    return _working.lab()
