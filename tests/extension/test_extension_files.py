"""The extension folders as files (no browser)."""

import hashlib
from typing import Final

from tests.support.extension import V1_EXTENSION

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


def test_v1_extension_fixture_is_v1_0_2() -> None:
    found = {p.relative_to(V1_EXTENSION).as_posix(): p for p in V1_EXTENSION.rglob("*") if p.is_file()}
    assert sorted(found) == sorted(V1_SHA256)
    assert {name: hashlib.sha256(p.read_bytes()).hexdigest() for name, p in found.items()} == V1_SHA256
