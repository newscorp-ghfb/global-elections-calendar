"""The README describes version 2 as released (Plan 5c Task 4; spec section 16)."""

from pathlib import Path

from elections_calendar.model import SOURCE_NAMES, SOURCE_ORDER

README = Path(__file__).resolve().parents[2] / "README.md"


def test_readme_covers_the_release() -> None:
    text = README.read_text(encoding="utf-8")
    for source in SOURCE_ORDER:
        assert f"| {SOURCE_NAMES[source]} | " in text
    for phrase in (
        "](docs/extension/v2.0.0-release-notes.md)",  # a link, not only a mention
        "--release-sha",
        "--check",
        "Delete the folder's contents",
        "Developer mode",
        "Reload",
        "Do not remove the extension",
    ):
        assert phrase in text, phrase
    assert "is being built" not in text
