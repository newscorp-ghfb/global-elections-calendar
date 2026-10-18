"""No stray control bytes in tracked text files (a Git Bash heredoc once wrote literal \x01)."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROL = re.compile(rb"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
TOP = ("elections_calendar/", "scripts/", "tests/", "docs/", "data/")


def tracked_text_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise AssertionError(f"git ls-files failed: {exc!r}") from exc
    names = [n for n in out.decode("utf-8").split("\0") if n]
    picked = []
    for name in names:
        if name.startswith("tests/fixtures/"):
            continue
        root_file = "/" not in name and name.endswith((".ini", ".toml", ".md"))
        if name.startswith(TOP) or root_file:
            path = ROOT / name
            if path.is_file():
                picked.append(path)
    return picked


def test_tracked_text_files_hold_no_control_bytes() -> None:
    files = tracked_text_files()
    assert len(files) > 50, "git ls-files found suspiciously few files"
    found = []
    for path in files:
        m = CONTROL.search(path.read_bytes())
        if m:
            found.append(f"{path.relative_to(ROOT).as_posix()} at byte {m.start()}")
    assert found == []
