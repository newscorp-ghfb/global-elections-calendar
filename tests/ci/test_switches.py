import os
from pathlib import Path

import pytest

from elections_calendar import feed, text
from elections_calendar.ci.switches import switches


def test_md_text_moved() -> None:
    assert feed.md_text is text.md_text
    assert text.md_text("a_b‮ [x]\n") == "a\\_b \\[x\\]"
    assert text.md_text("می‌خواهم") == "می‌خواهم"


def test_switches(tmp_path: Path) -> None:
    assert switches(tmp_path) == {"paused": "false", "alert_test": "false"}
    (tmp_path / "PAUSE_PUBLISHING").write_text("", encoding="utf-8")
    assert switches(tmp_path) == {"paused": "true", "alert_test": "false"}
    (tmp_path / "PAUSE_PUBLISHING").unlink()
    (tmp_path / "PAUSE_PUBLISHING").mkdir()
    assert switches(tmp_path) == {"paused": "true", "alert_test": "false"}
    (tmp_path / "PAUSE_PUBLISHING").rmdir()
    (tmp_path / "ALERT_TEST").write_text("anything", encoding="utf-8")
    assert switches(tmp_path) == {"paused": "false", "alert_test": "true"}
    (tmp_path / "PAUSE_PUBLISHING").write_text("", encoding="utf-8")
    assert switches(tmp_path) == {"paused": "true", "alert_test": "true"}


def test_switches_count_a_dangling_link(tmp_path: Path) -> None:
    try:
        os.symlink(tmp_path / "nowhere", tmp_path / "PAUSE_PUBLISHING")
    except OSError as problem:  # Windows without the privilege to make links
        pytest.skip(f"cannot make a symbolic link here: {problem}")
    assert switches(tmp_path) == {"paused": "true", "alert_test": "false"}
