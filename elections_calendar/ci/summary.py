"""``GITHUB_OUTPUT`` and ``GITHUB_STEP_SUMMARY``: fixed words in one, capped text in the other."""

from collections.abc import Mapping
from pathlib import Path
from typing import Final

from elections_calendar.ci.context import PUBLISH_OUTCOMES, SERVED_RESULTS, SWITCH_VALUES

SUMMARY_CAP_BYTES: Final = 900_000  # GitHub refuses a step summary over 1 MiB
OUTPUT_VALUES: Final[Mapping[str, tuple[str, ...]]] = {
    "paused": SWITCH_VALUES,
    "alert_test": SWITCH_VALUES,
    "outcome": PUBLISH_OUTCOMES,
    "served": SERVED_RESULTS,
}


def write_outputs(path: Path, values: Mapping[str, str]) -> None:
    """Append ``name=value`` lines; every name and value is checked before anything is written."""
    for name, value in values.items():
        if name not in OUTPUT_VALUES or value not in OUTPUT_VALUES[name]:
            raise ValueError(f"not an allowed output: {name!r}")
    data = "".join(f"{name}={value}\n" for name, value in values.items()).encode("ascii")
    with path.open("ab") as handle:
        handle.write(data)


def append_summary(path: Path, text: str, *, cap: int = SUMMARY_CAP_BYTES) -> None:
    """Append ``text`` so that the file never grows past ``cap`` bytes.

    Text that does not fit is cut after its last newline that leaves room for a note saying
    so; the note is appended. When even the note does not fit, nothing is appended.
    """
    data = text.encode("utf-8", errors="replace")
    room = cap - (path.stat().st_size if path.exists() else 0)
    if len(data) > room:
        note = (
            f"\n_The summary was cut at {cap} bytes. The full text is in the run's artifact._\n"
        ).encode()
        keep = data[: max(room - len(note), 0)]
        data = keep[: keep.rfind(b"\n") + 1] + note if len(note) <= room else b""
    with path.open("ab") as handle:
        handle.write(data)
