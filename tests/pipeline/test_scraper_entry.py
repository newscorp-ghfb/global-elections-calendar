"""``scraper.py`` is v2's entry point (R32)."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_scraper_entry_point_runs_the_pipeline(tmp_path: Path) -> None:
    out, empty = tmp_path / "out", tmp_path / "empty"
    empty.mkdir()
    done = subprocess.run(
        [
            sys.executable,
            "scraper.py",
            "--offline",
            "tests/fixtures",
            "--now",
            "2026-10-19T12:00:00Z",
            "--out",
            str(out),
            "--repo",
            str(empty),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    assert re.fullmatch(r"published, verdict red, [0-9]+ feed bytes\n", done.stdout), done.stdout
    assert (out / "manifest.json").is_file()
    source = (ROOT / "scraper.py").read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 15
    assert "requests" not in source
    assert "bs4" not in source
