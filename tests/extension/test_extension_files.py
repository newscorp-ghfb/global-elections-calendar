"""The extension folders as files (no browser)."""

import hashlib
import json
import re
from typing import Final

from tests.support.extension import ROOT, V1_EXTENSION

# Copied from tests/fixtures/v1/PROVENANCE.md (the blobs of ff30417:extension/).
V1_SHA256: Final[dict[str, str]] = {
    "background.js": "4f8d64798cd4d8aadbae57206c61994a11186ca2b085be1f07942c16fde63afa",
    "help.html": "0445967aef14851784278e9347c8e8a7c948d567538195e03080b516c984a7bf",
    "icons/icon128.png": "fd7a60e0de60c41bb2c643c9880b6bede360ee19294ee80f03f21dfd5df31b31",
    "icons/icon16.png": "2340f4bcc2c5abf10c5f800837624fcb8d8c038c83575f891dbc1eee8de04e15",
    "icons/icon48.png": "c4ff4e04ba1c491a249a7e5d8695b1afe0285558e253a3b220ab94ac30d70d1b",
    "manifest.json": "26668ccb37bbf76e4599a7d041a0fbebc97225b332b436ef179e3cdbe34a51c3",
    "options.css": "f2731d297c3f9f9661b90a87be216e821ead56a87bbb54307b69a2085a74e581",
    "options.html": "059f87b6b1d18e56d768f64bd5b707fc3910d93eaa8f0a5991a244b4fa046784",
    "options.js": "a9e5ed20fa947989847186d34069fec85e2540160ddd990516f4876a39b156d8",
    "popup.html": "47a52f247ce43112ba72e2c6cea0f9985ef6b396a3b14c20cf15f0e0938491d1",
    "popup.js": "9b0db4589d09320d9396d188a8018f500a5d605907188884ab968a19d9a923cf",
    "styles.css": "2ef2e9bd0fd737e7c4d02c5b6148ba34f426649760b246651d2fed56a69ae515",
}


PURE_MODULES: Final = ("dates.js", "labels.js", "schema.js", "validate.js", "order.js", "worker.js", "health.js", "count.js")
# A bare word must not touch an identifier character, so `expected_window` is not `window`.
BROWSER_TOKENS: Final = (
    "chrome.",
    "document",
    "window",
    "fetch(",
    "Date.now",
    "localStorage",
    "innerHTML",
)


def _uses(text: str, token: str) -> bool:
    if not token.isalpha():  # "chrome.", "fetch(", "Date.now" are matched as written
        return token in text
    return re.search(r"(?<![A-Za-z0-9_])" + token + r"(?![A-Za-z0-9_])", text) is not None


def test_pure_modules_use_no_browser_api() -> None:
    for name in PURE_MODULES:
        path = ROOT / "extension" / "lib" / name
        assert path.is_file(), f"{name} is missing"
        text = path.read_text(encoding="utf-8")
        for token in BROWSER_TOKENS:
            assert not _uses(text, token), f"{name} contains {token!r}"
        assert ("new Date(" in text) == (name == "dates.js"), f"{name}: new Date( placement"


def test_v1_extension_fixture_is_v1_0_2() -> None:
    found = {p.relative_to(V1_EXTENSION).as_posix(): p for p in V1_EXTENSION.rglob("*") if p.is_file()}
    assert sorted(found) == sorted(V1_SHA256)
    assert {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in found.items()} == V1_SHA256


def test_schema_copies_match() -> None:
    for name in ("feed-v2.schema.json", "status-v1.schema.json"):
        copy = ROOT / "extension" / "schemas" / name
        assert copy.read_bytes() == (ROOT / "schemas" / name).read_bytes(), name


def test_permissions_are_v1_0_2s() -> None:
    now = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
    was = json.loads((V1_EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    assert now["background"].pop("type") == "module"
    assert now == was
    assert "key" not in now and "content_security_policy" not in now


def test_the_worker_wires_its_handlers() -> None:
    text = (ROOT / "extension" / "background.js").read_text(encoding="utf-8")
    assert re.search(r"import \{[^}]*\bhandlers\b[^}]*\} from \"\./lib/worker\.js\"", text)
    for event in (
        "chrome.runtime.onInstalled",
        "chrome.runtime.onStartup",
        "chrome.alarms.onAlarm",
        "chrome.runtime.onMessage",
    ):
        assert text.count(event + ".addListener(") == 1, event
    assert text.count("const DATA_URL = ") == 1


def test_no_feed_text_through_inner_html_in_v2_code() -> None:
    # lib/legacy.js is exempt until R52
    for name in ("lib/health.js", "lib/render.js", "popup.js"):
        text = (ROOT / "extension" / name).read_text(encoding="utf-8")
        for token in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
            assert token not in text, f"{name} contains {token!r}"
