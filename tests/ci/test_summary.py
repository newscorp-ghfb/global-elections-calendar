from pathlib import Path

import pytest

from elections_calendar.ci.summary import SUMMARY_CAP_BYTES, append_summary, write_outputs

NOTE_END = "The full text is in the run's artifact._\n"


def _note(cap: int) -> str:
    return f"\n_The summary was cut at {cap} bytes. The full text is in the run's artifact._\n"


def test_outputs_hold_fixed_words_only(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.write_bytes(b"paused=true\n")
    for bad in ({"outcome": "published\nserved=ok"}, {"evil": "true"}, {"served": "OK"}):
        with pytest.raises(ValueError):
            write_outputs(out, bad)
    with pytest.raises(ValueError):  # a bad value stops the good one before it
        write_outputs(out, {"paused": "false", "served": "OK"})
    assert out.read_bytes() == b"paused=true\n"
    write_outputs(out, {"outcome": "published"})
    assert out.read_bytes() == b"paused=true\noutcome=published\n"


def test_outputs_create_the_file(tmp_path: Path) -> None:
    out = tmp_path / "new"
    write_outputs(out, {"paused": "true", "alert_test": "false"})
    assert out.read_bytes() == b"paused=true\nalert_test=false\n"


def test_summary_is_capped(tmp_path: Path) -> None:
    line = "Bangsamoro — São Tomé ✓ | <b>\n"
    big = line * (2_000_000 // len(line.encode()) + 1)
    summary = tmp_path / "summary"
    append_summary(summary, big)
    data = summary.read_bytes()
    assert len(data) <= SUMMARY_CAP_BYTES
    text = data.decode("utf-8")
    assert text.endswith(_note(900_000))
    assert text.startswith(line)


def test_summary_cut_is_at_a_line_end_and_whole_characters(tmp_path: Path) -> None:
    summary = tmp_path / "summary"
    append_summary(summary, "aaaaa\n" + "é" * 120 + "\nz\n", cap=200)
    assert summary.read_bytes().decode("utf-8") == "aaaaa\n" + _note(200)


def test_summary_appends_to_a_nearly_full_file(tmp_path: Path) -> None:
    summary = tmp_path / "summary"
    summary.write_bytes(b"x" * 899_000)
    append_summary(summary, "ü line\n" * 2000)
    assert len(summary.read_bytes()) <= SUMMARY_CAP_BYTES
    assert summary.read_bytes().decode("utf-8").endswith(NOTE_END)


@pytest.mark.parametrize("size", [900_000, 950_000])
def test_summary_never_grows_a_full_file(tmp_path: Path, size: int) -> None:
    summary = tmp_path / "summary"
    summary.write_bytes(b"x" * size)
    append_summary(summary, "more\n")
    assert len(summary.read_bytes()) == size


def test_summary_that_fits_is_appended_unchanged(tmp_path: Path) -> None:
    summary = tmp_path / "summary"
    summary.write_bytes(b"first\n")
    append_summary(summary, "second é\n")
    assert summary.read_bytes() == "first\nsecond é\n".encode()
