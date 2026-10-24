"""``scripts/prove_gates.py`` applies each deliberate violation and puts the file back (RT-01)."""

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import prove_gates
from scripts.prove_gates import VIOLATIONS, prove

Seen = list[tuple[str, str]]


def _tree(root: Path) -> dict[str, bytes]:
    originals: dict[str, bytes] = {}
    for violation in VIOLATIONS:
        path = root / violation.file
        path.parent.mkdir(parents=True, exist_ok=True)
        # CRLF and a missing final newline: the restore must be byte for byte
        path.write_bytes(f"# {violation.file}\r\nx = 1".encode())
        originals[violation.file] = path.read_bytes()
    return originals


def _fake(
    root: Path, seen: Seen, *, code: Callable[[str], int], output: Callable[[str], str]
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert Path(str(kwargs["cwd"])) == root
        gate = next(v for v in VIOLATIONS if Path(cmd[0]).stem == v.gate and list(v.args) == cmd[1:])
        assert Path(cmd[0]).parent == Path(sys.executable).parent
        text = (root / gate.file).read_bytes().decode("utf-8")
        seen.append((gate.gate, text))
        return subprocess.CompletedProcess(cmd, code(gate.marker), output(gate.marker), "")

    return run


def test_prove_gates_applies_and_restores_each_violation(tmp_path: Path) -> None:
    originals = _tree(tmp_path)
    seen: Seen = []
    run = _fake(tmp_path, seen, code=lambda _: 1, output=lambda marker: f"error: {marker}")
    assert prove(tmp_path, run=run) == []
    assert len(seen) == len(VIOLATIONS) == 3
    for violation, (_, text) in zip(VIOLATIONS, seen, strict=True):
        assert text.endswith(violation.text), violation.gate
    for name, original in originals.items():
        assert (tmp_path / name).read_bytes() == original
    # a gate that exits 0 is a failure of prove
    run = _fake(tmp_path, [], code=lambda _: 0, output=lambda marker: marker)
    problems = prove(tmp_path, run=run)
    assert len(problems) == 3
    assert all("passed" in problem for problem in problems)
    # a gate that exits 1 without its marker is one too
    run = _fake(tmp_path, [], code=lambda _: 1, output=lambda _: "something else broke")
    problems = prove(tmp_path, run=run)
    assert len(problems) == 3
    assert all("marker" in problem for problem in problems)
    for name, original in originals.items():
        assert (tmp_path / name).read_bytes() == original


def test_a_gate_that_raises_still_gets_its_file_back(tmp_path: Path) -> None:
    originals = _tree(tmp_path)

    def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise OSError("no such gate")

    with pytest.raises(OSError, match="no such gate"):
        prove(tmp_path, run=run)
    for name, original in originals.items():
        assert (tmp_path / name).read_bytes() == original


def test_the_violations_are_the_three_gates() -> None:
    assert [(v.gate, v.file, v.marker) for v in VIOLATIONS] == [
        ("mypy", "elections_calendar/text.py", "Incompatible types in assignment"),
        ("ruff", "elections_calendar/text.py", "F401"),
        (
            "lint-imports",
            "elections_calendar/model.py",
            "elections_calendar.model -> elections_calendar.pipeline",
        ),
    ]
    assert prove_gates.main.__name__ == "main"
