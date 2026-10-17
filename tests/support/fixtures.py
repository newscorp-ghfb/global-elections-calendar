"""Read byte-exact source fixtures from tests/fixtures/<source>/<day>/."""

from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def fixture(source: str, name: str, day: str = "2026-10-16") -> bytes:
    """Return the raw bytes of one captured source file, unmodified."""
    return (FIXTURES / source / day / name).read_bytes()
