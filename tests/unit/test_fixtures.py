"""Source fixtures match their provenance notes byte for byte (spec §16)."""

import hashlib
import json
import re

from tests.support.fixtures import FIXTURES, fixture

SHA_LINE = re.compile(r"\*\*SHA-256 of `([^`]+)`:\*\* ([0-9a-f]{64})")


def test_every_fixture_file_matches_its_provenance_note() -> None:
    notes = sorted(FIXTURES.glob("*/*/PROVENANCE.md"))
    assert [n.parent.relative_to(FIXTURES).as_posix() for n in notes] == [
        "aweb/2026-10-18", "carter/2026-10-18", "eeas/2026-10-18", "electionguide/2026-10-16",
        "ipu/2026-10-16", "ipu/2026-10-18", "osce/2026-10-18", "wikipedia/2026-10-16"]
    for note in notes:
        listed = dict(SHA_LINE.findall(note.read_text(encoding="utf-8")))
        files = {p.name for p in note.parent.iterdir() if p.name != "PROVENANCE.md"}
        assert set(listed) == files, note
        for name, digest in listed.items():
            assert hashlib.sha256((note.parent / name).read_bytes()).hexdigest() == digest, name


def test_fixture_reads_bytes() -> None:
    assert fixture("electionguide", "upcoming.html").rstrip().endswith(b"</html>")
    assert json.loads(fixture("wikipedia", "local-2026.json"))["parse"]["revid"] == 1380378807
