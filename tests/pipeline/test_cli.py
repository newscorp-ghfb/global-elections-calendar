"""The command line (Plan 4 Task 8; P98)."""

import functools
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from elections_calendar import __main__ as cli
from elections_calendar import pipeline
from elections_calendar.fetch import TrustBundleError
from elections_calendar.model import stored_json
from elections_calendar.pipeline import RunConfig
from tests.support.repo import OSCE, osce_offline

NOW = "2026-10-19T12:00:00Z"


def args(tmp_path: Path, *extra: str, out: str = "out") -> list[str]:
    (tmp_path / "repo").mkdir(exist_ok=True)
    return ["--out", str(tmp_path / out), "--repo", str(tmp_path / "repo"), *extra]


@pytest.mark.parametrize("now", ["2026-10-19T12:00:00", "2026-10-19"])
def test_now_needs_a_time_zone(
    now: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    offline = osce_offline(tmp_path)
    assert cli.main(["--offline", str(offline), "--now", now, *args(tmp_path)]) == 2
    assert "--now needs a time zone" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("now", ["0001-01-01T00:00:00+05:00", "9999-12-31T23:59:59-05:00"])
def test_now_must_be_in_range(
    now: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    offline = osce_offline(tmp_path)
    assert cli.main(["--offline", str(offline), "--now", now, *args(tmp_path)]) == 2
    assert "--now is out of range" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_now_must_be_a_time(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    offline = osce_offline(tmp_path)
    assert cli.main(["--offline", str(offline), "--now", "abc", *args(tmp_path)]) == 2
    assert "--now is not an ISO 8601 time" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


def test_out_must_be_empty(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    offline = osce_offline(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    (out / "old.txt").write_text("old")
    assert cli.main(["--offline", str(offline), "--now", NOW, *args(tmp_path)]) == 2
    assert "--out must be empty" in capsys.readouterr().err
    assert [p.name for p in out.iterdir()] == ["old.txt"]
    assert (out / "old.txt").read_text() == "old"
    both = ["--live", "--offline", str(offline), *args(tmp_path, out="other")]
    assert cli.main(both) == 2
    assert cli.main(args(tmp_path, out="other")) == 2
    assert cli.main(["--live"]) == 2


def test_a_missing_pages_json_is_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "empty").mkdir()
    assert cli.main(["--offline", str(tmp_path / "empty"), *args(tmp_path)]) == 2
    assert "pages.json: not found" in capsys.readouterr().err


def test_trust_error_is_reported_without_its_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    message = "REQUESTS_CA_BUNDLE=C:/secret/ca.pem is not a usable CA bundle: x"

    def fail(*a: object, **k: object) -> None:
        raise TrustBundleError(message, "REQUESTS_CA_BUNDLE")

    monkeypatch.setattr(pipeline, "run_sources", fail)
    assert cli.main(["--live", "--now", NOW, *args(tmp_path)]) == 1
    assert message in capsys.readouterr().err
    out = tmp_path / "out"
    assert (out / "rejected" / "trust_error.json").read_bytes() == stored_json(
        {"variable": "REQUESTS_CA_BUNDLE"}
    )
    found = [p for p in out.rglob("*") if p.is_file()]
    assert [p.name for p in found] == ["trust_error.json"]
    assert all(b"secret" not in p.read_bytes() for p in found)
    assert not (out / "manifest.json").exists()


def test_main_prints_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "RunConfig", functools.partial(RunConfig, specs=(OSCE,)))
    offline = osce_offline(tmp_path)
    assert cli.main(["--offline", str(offline), "--now", NOW, *args(tmp_path)]) == 0
    size = (tmp_path / "out" / "elections.json").stat().st_size
    assert capsys.readouterr().out == f"published, verdict green, {size} feed bytes\n"
    assert json.loads((tmp_path / "out" / "manifest.json").read_text())["files"]


def test_an_unexpected_error_propagates_without_a_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*a: object, **k: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "run_sources", fail)
    with pytest.raises(RuntimeError, match="boom"):
        cli.main(["--live", "--now", NOW, *args(tmp_path)])
    assert not (tmp_path / "out" / "manifest.json").exists()


def test_the_machine_clock_is_the_default_now(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = datetime(2026, 10, 20, 8, 30, tzinfo=UTC)

    class Fixed(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> Any:
            return clock.astimezone(tz)

    monkeypatch.setattr(cli, "datetime", Fixed)
    monkeypatch.setattr(cli, "RunConfig", functools.partial(RunConfig, specs=(OSCE,)))
    offline = osce_offline(tmp_path)
    assert cli.main(["--offline", str(offline), *args(tmp_path, out="machine")]) == 0
    assert cli.main(["--offline", str(offline), "--now", NOW, *args(tmp_path, out="given")]) == 0
    for name, at in (("machine", "2026-10-20T08:30:00Z"), ("given", NOW)):
        assert json.loads((tmp_path / name / "status.json").read_text())["attempt_at"] == at
        assert json.loads((tmp_path / name / "elections.json").read_text())["generated_at"] == at
