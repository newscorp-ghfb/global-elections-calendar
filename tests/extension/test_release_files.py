"""The v2.0.0 help page and release notes (Plan 5b-2 Task 7; S5-T20, R54)."""

import html
import json
import re

from tests.support.extension import ROOT

DESCRIPTION = (
    "Global elections month by month from 10 monitoring sources, with data health checks, "
    "honest date labels and items to review."
)


def _visible_text(page: str) -> str:
    page = re.sub(r"<(style|script)\b.*?</\1>", " ", page, flags=re.DOTALL)
    page = re.sub(r"<!--.*?-->", " ", page, flags=re.DOTALL)
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", page)).split())


def test_the_manifest_is_2_0_0() -> None:
    manifest = json.loads((ROOT / "extension" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "2.0.0"
    assert manifest["description"] == DESCRIPTION
    assert len(manifest["description"]) <= 132


def test_help_explains_v2() -> None:
    raw = (ROOT / "extension" / "help.html").read_text(encoding="utf-8")
    assert "<script" not in raw.lower()
    text = _visible_text(raw)
    phrases = [
        # banner
        "hours old — the daily update hasn't arrived",
        "The latest update failed its checks — showing the last good data",
        "source error",
        "This data is newer than this extension — update the extension",
        "Current health can't be confirmed for this data",
        "Source health isn't available for this data",
        "warning",
        "acknowledged",
        "All sources OK",
        # labels
        "Scheduled voting period: today (approx.)",
        "day unconfirmed",
        "Past expected period — not confirmed",
        "Expected between",
        "Possibly postponed — sources disagree",
        "Possibly cancelled — sources disagree",
        "Sources disagree on date",
        "Using source data from",
        "Unverified since",
        # chips
        "Tentative",
        "Subnational",
        "Rescheduled from",
        # tabs
        "Upcoming",
        "Past (formerly Results)",
        "All",
        # month rule
        "A month shows every election whose dates overlap it",
        # sources
        "ElectionGuide",
        "Wikipedia (national calendar)",
        "Wikipedia (local calendar)",
        "NDI",
        "OSCE/ODIHR",
        "IPU",
        "A-WEB",
        "EISA",
        "Carter Center",
        "EEAS",
        "five months",
        # attention
        "items across the monitored window",
        "and then the title says how many of them match.",
        "When items are omitted from the feed, the full attention list is in attention_full.json in the "
        "publishing run's generation artifact; retrieving it may require operator access, and the "
        "artifact is retained for 14 days after upload.",
        # Past tab, check timing, Wikipedia (fix round 1: M3, M8, M11)
        "cancelled ones are listed only under All",
        "if the last successful check is 30 minutes old or more",
        "The popup shows both Wikipedia calendars as \"Wikipedia\"",
        # pins
        "A pinned country also shows the places that belong to it",
        # update
        "Delete the folder's contents",
        "Click Reload",
        "Turn on Developer mode (top right) if it is off",
        "Don't remove the extension",
    ]
    for phrase in phrases:
        assert phrase in text, phrase
    assert "Results" not in text.replace("Past (formerly Results)", "")
    assert "7 international" not in text


def test_release_notes_cover_the_update() -> None:
    raw = (ROOT / "docs" / "extension" / "v2.0.0-release-notes.md").read_text(encoding="utf-8")
    notes = " ".join(raw.split())
    phrases = [
        "Load unpacked",
        "Chrome Web Store",
        "Cabo Verde",
        "Democratic People's Republic of Korea",
        "Lao People's Democratic Republic",
        "Viet Nam",
        "The Philippines",
        "São Tomé e Príncipe",
        "If you stay on v1.0.2, or go back to it, a pin on one of these six spellings no longer matches",
        "Re-pin the place under its display name on v1.0.2's options page",
        "1 OCT",
        "v1.0.1",
        "Select All",
        "Save",
        "Turn on Developer mode (top right) if it is off",
        "not migrated again",
        "Also shows",
        "Restarting Chrome instead of clicking Reload can leave the old version's background worker"
        " running until the next restart",
    ]
    for phrase in phrases:
        assert phrase in notes, phrase
