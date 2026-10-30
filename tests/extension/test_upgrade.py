"""The real ZIP upgrades a v1.0.2 folder through Chrome's Reload (Plan 5b-2 Task 8; S5-T16, RT-06, R49).

With v1.0.2 running, Developer mode is switched on at chrome://extensions, the folder's contents are
replaced by the built ZIP while the browser stays open, and the extension card's Reload button is
clicked. That is the update path (Playwright's Chromium only). A browser relaunch is not used: it
reports ``install`` and runs v1.0.2's cached worker script (R49).
"""

import shutil
import time
import zipfile
from pathlib import Path
from typing import Any, Final

from playwright.sync_api import Playwright

from scripts.build_extension_zip import build
from tests.support.extension import PAGE_FILES, artifact_pair, extension_copy, launch, v1_feed

V1_KEYS: Final = ("elections_cache", "pinned_countries", "selected_countries")
V2_ABSENT: Final = (
    "pins_migrated_v2",
    "pinned_places_v2",
    "unresolved_pins_v2",
    "elections_cache_v2",
    "check_state_v2",
)
PINS_V1: Final = ["Cabo Verde", "Moldova", "Scotland (part of the United Kingdom)", "Atlantis"]
SELECTED_V1: Final = ["Brazil"]
PLACES_V2: Final = ["iso:CV", "iso:MD", "iso:GB-SCT"]
CACHED: Final = "() => chrome.storage.local.get('elections_cache').then(s => 'elections_cache' in s)"


def _empty(folder: Path) -> None:
    for entry in folder.iterdir():
        if entry.is_dir():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def test_real_zip_same_folder_upgrade(playwright: Playwright, tmp_path: Path) -> None:
    profile, folder = tmp_path / "profile", tmp_path / "X"
    extension_copy(folder, legacy=True)
    ext = launch(playwright, profile, folder)
    try:
        ext.served.set("elections.json", v1_feed())
        old_popup = ext.open("popup.html")
        old_popup.wait_for_selector("#electionList:not(.hidden) .election-item")
        old_popup.wait_for_function(CACHED)
        ext.seed({"pinned_countries": PINS_V1, "selected_countries": SELECTED_V1})
        before = ext.storage()
        first_id = ext.ext_id
        for key in V2_ABSENT:
            assert key not in before, key
        v1_before: dict[str, Any] = {key: before[key] for key in V1_KEYS}
        assert v1_before["pinned_countries"] == PINS_V1
        assert v1_before["selected_countries"] == SELECTED_V1

        # Developer mode on, so that the card has a Reload button
        lab = ext.lab()
        ext.close_other_pages()
        extensions = ext.context.new_page()
        extensions.goto("chrome://extensions")
        extensions.click("#devMode")
        reload_button = extensions.locator(f"extensions-item#{first_id} #dev-reload-button")
        reload_button.wait_for(state="visible")
        feed, status = artifact_pair()
        ext.served.set("elections.json", feed)
        ext.served.set("status.json", status)

        # the swap, with the browser open
        _empty(folder)
        zip_path, _ = build(out_dir=tmp_path / "dist")
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(folder)
            listed = sorted(archive.namelist())
        extracted = sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
        assert extracted == listed
        shutil.copytree(PAGE_FILES, folder / "test")  # the harness page, as extension_copy adds it

        started_ms = int(time.time() * 1000)
        with lab.expect_event("close"):
            reload_button.click()
        # Chrome reports the reloaded extension enabled at 2.0.0 before the settle opens a page of it
        extensions.wait_for_function(
            "() => chrome.developerPrivate.getExtensionsInfo()"
            ".then(xs => xs.some(x => x.state === 'ENABLED' && x.version === '2.0.0'))"
        )
        listed_now = extensions.evaluate(
            "() => chrome.developerPrivate.getExtensionsInfo({ includeDisabled: true, includeTerminated: true })"
            ".then(xs => xs.map(x => [x.id, x.version, x.state]))"
        )
        assert listed_now == [[first_id, "2.0.0", "ENABLED"]]
        ext.wait_for_install_check(started_ms)

        # storage first: the options page migrates by itself (PINS), which would hide a missing
        # update-time migration
        assert ext.lab().evaluate("() => chrome.runtime.getManifest().version") == "2.0.0"
        after = ext.storage()
        assert {key: after[key] for key in V1_KEYS} == v1_before
        assert after.get("pins_migrated_v2") is True
        assert after.get("pinned_places_v2") == PLACES_V2
        assert after.get("unresolved_pins_v2") == ["Atlantis"]
        assert after["check_state_v2"]["ok_at"] >= started_ms
        assert after["check_state_v2"]["error"] is None
        assert [p.url for p in ext.context.pages if p.url.endswith("/help.html")] == []  # D7

        popup = ext.popup()
        popup.click("#nextMonthBtn")
        assert popup.locator("#currentMonthLabel").text_content() == "NOVEMBER 2026"
        names = popup.locator(".election-item .election-country").all_text_contents()
        assert sorted(names) == ["Cape Verde", "Moldova"]
        assert popup.locator("#pinBarText").text_content() == "Pinned view · 3 countries"

        options = ext.open("options.html")
        options.wait_for_function("() => document.body.dataset.pinSync === 'idle'")
        first_three = options.eval_on_selector_all(
            ".country-item", "els => els.slice(0, 3).map(e => e.dataset.placeId)"
        )
        assert first_three == PLACES_V2
        assert options.locator("#unresolvedSection").is_visible()
        assert (
            options.locator(".unresolved-title").text_content()
            == "Pins from version 1 that match no known country"
        )
        assert options.locator("#unresolvedList .unresolved-name").all_text_contents() == ["Atlantis"]
        assert ext.page_errors == []
    finally:
        ext.close()
