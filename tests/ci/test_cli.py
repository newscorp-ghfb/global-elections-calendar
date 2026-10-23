import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from elections_calendar.ci.__main__ import main
from elections_calendar.publish import write_manifest
from tests.support.ci import REASON, make_artifact, run_env

ROOT = Path(__file__).resolve().parents[2]
NAMES = tuple(run_env()) + ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY")
NO_HEALTH = "## No HEALTH.md\n\nThe scrape stopped before it wrote one. See the job log.\n"
PAUSED = "## Paused\n\n`PAUSE_PUBLISHING` is on this commit: nothing is scraped or published.\n"
ALERT = (
    "## Alert test\n\n"
    "`ALERT_TEST` is on this commit: this run fails on purpose after it publishes.\n"
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in NAMES:
        monkeypatch.delenv(name, raising=False)


def _env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)


def test_cli_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    assert main(["switches", "--repo", str(repo)]) == 2
    assert "GITHUB_OUTPUT is not set" in capsys.readouterr().err

    out = tmp_path / "out"
    out.mkdir()
    summary = tmp_path / "summary.md"
    assert main(["scrape-summary", "--out", str(out)]) == 2  # no GITHUB_STEP_SUMMARY
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["scrape-summary", "--out", str(out)]) == 0
    assert summary.read_text(encoding="utf-8") == NO_HEALTH

    artifact = make_artifact(tmp_path / "artifact")
    _env(monkeypatch, run_env())
    summary.unlink()
    assert main(["verdict", "--artifact", str(artifact)]) == 0
    assert capsys.readouterr().out == "Verdict: green, published\n"
    assert summary.read_text(encoding="utf-8").startswith("## Verdict: green, published\n")

    monkeypatch.setenv("SERVED", "served_mismatch")
    assert main(["verdict", "--artifact", str(artifact)]) == 1
    assert capsys.readouterr().out == "Verdict: red, served_mismatch\n"


def test_verdict_without_a_step_summary_still_decides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact = make_artifact(tmp_path / "artifact")
    _env(monkeypatch, run_env())
    assert main(["verdict", "--artifact", str(artifact)]) == 0
    assert capsys.readouterr().out == "Verdict: green, published\n"
    monkeypatch.setenv("PUBLISH_OUTCOME", "git_failed")
    assert main(["verdict", "--artifact", str(artifact)]) == 1


def test_scrape_summary_appends_health(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = make_artifact(tmp_path / "out")
    summary = tmp_path / "summary.md"
    summary.write_bytes(b"before\n")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["scrape-summary", "--out", str(out)]) == 0
    assert summary.read_bytes() == b"before\n" + (out / "HEALTH.md").read_bytes()


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        ((), ""),
        (("PAUSE_PUBLISHING",), PAUSED),
        (("ALERT_TEST",), ALERT),
        (("PAUSE_PUBLISHING", "ALERT_TEST"), PAUSED + ALERT),
    ],
)
def test_switches_write_outputs_and_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, files: tuple[str, ...], expected: str
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in files:
        (repo / name).write_text("", encoding="utf-8")
    output, summary = tmp_path / "output", tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert main(["switches", "--repo", str(repo)]) == 0  # no step summary: still fine
    assert not summary.exists()
    paused = "true" if "PAUSE_PUBLISHING" in files else "false"
    alert = "true" if "ALERT_TEST" in files else "false"
    assert output.read_text(encoding="utf-8") == f"paused={paused}\nalert_test={alert}\n"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["switches", "--repo", str(repo)]) == 0
    assert (summary.read_text(encoding="utf-8") if summary.exists() else "") == expected


def test_outputs_hold_fixed_words_only_in_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = make_artifact(tmp_path / "artifact", verdict="red", reason=REASON)
    assert REASON.splitlines()[1] == "served=ok"
    repo = tmp_path / "repo"
    repo.mkdir()
    output, summary = tmp_path / "output", tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    _env(monkeypatch, run_env())
    assert main(["switches", "--repo", str(repo)]) == 0
    assert main(["scrape-summary", "--out", str(artifact)]) == 0
    assert main(["verdict", "--artifact", str(artifact)]) == 1
    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines
    assert all(re.fullmatch(r"(paused|alert_test)=(true|false)", line) for line in lines)
    text = summary.read_text(encoding="utf-8")
    assert "x served\\=ok outcome\\=published" in text
    assert "\\$\\{\\{ secrets\\.GITHUB\\_TOKEN \\}\\}" in text
    assert not {"served=ok", "outcome=published"} & set(text.splitlines())
    assert not any(line.startswith("::") for line in text.splitlines())


def test_light_commands_need_only_the_standard_library(tmp_path: Path) -> None:
    artifact = make_artifact(tmp_path / "artifact")
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "import elections_calendar.ci.__main__ as cli\n"
        "import elections_calendar.ci.context, elections_calendar.ci.manifest\n"
        "import elections_calendar.ci.summary, elections_calendar.ci.switches\n"
        "import elections_calendar.ci.verdict\n"
        "heavy = ['yaml', 'jsonschema', 'requests', 'bs4', 'lxml', 'elections_calendar.feed']\n"
        "assert not [m for m in heavy if m in sys.modules], sorted(sys.modules)\n"
        f"sys.exit(cli.main(['verdict', '--artifact', {str(artifact)!r}]))\n"
    )
    env = {k: v for k, v in os.environ.items() if k not in NAMES}
    env.update(run_env())
    done = subprocess.run(
        [sys.executable, "-I", "-S", "-c", code],
        env=env,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert (done.returncode, done.stdout.strip()) == (0, "Verdict: green, published"), done.stderr


def test_verdict_command_survives_nested_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    _env(monkeypatch, run_env())
    nested = b"[" * 100_000 + b"]" * 100_000
    for name, headline in (
        ("verdict.json", "verdict.json is malformed"),
        ("manifest.json", "artifact incomplete"),
    ):
        artifact = make_artifact(tmp_path / name)
        (artifact / name).write_bytes(nested)
        if name == "verdict.json":
            write_manifest(artifact)
        assert main(["verdict", "--artifact", str(artifact)]) == 1
        assert capsys.readouterr().out == f"Verdict: red, {headline}\n"
    assert summary.read_text(encoding="utf-8").count("## Verdict: red, ") == 2


def test_scrape_summary_treats_a_linked_health_as_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    real = tmp_path / "real.md"
    real.write_text("secret outside the artifact\n", encoding="utf-8")
    try:
        os.symlink(real, out / "HEALTH.md")
    except OSError as problem:  # Windows without the privilege to make links
        pytest.skip(f"cannot make a symbolic link here: {problem}")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert main(["scrape-summary", "--out", str(out)]) == 0
    assert summary.read_text(encoding="utf-8") == NO_HEALTH
