"""Prove that mypy, ruff and import-linter each fail on one deliberate violation (RT-01, P126).

Run from the repository root as ``python -m scripts.prove_gates``. It extracts
``git archive HEAD`` into a temporary directory, so the working tree is never touched, and it
proves the committed tree.
"""

import io
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Violation:
    gate: str  # the executable's name, found next to ``sys.executable``
    args: tuple[str, ...]
    file: str  # relative to the tree
    text: str  # appended to the file
    marker: str  # the gate's output must hold this


VIOLATIONS = (
    Violation(
        "mypy",
        (),
        "elections_calendar/text.py",
        '\n_RT01: int = "x"\n',
        "Incompatible types in assignment",
    ),
    Violation("ruff", ("check",), "elections_calendar/text.py", "\nimport os\n", "F401"),
    Violation(
        "lint-imports",
        ("--config", "importlinter.ini"),
        "elections_calendar/model.py",
        "\nimport elections_calendar.pipeline  # RT-01\n",
        "elections_calendar.model -> elections_calendar.pipeline",
    ),
)


def _executable(name: str) -> str:
    """The gate's executable in the interpreter's own scripts directory (Windows or Linux)."""
    folder = Path(sys.executable).parent
    for candidate in (folder / f"{name}.exe", folder / name):
        if candidate.exists():
            return str(candidate)
    return str(folder / name)


def _check(
    root: Path, violation: Violation, run: Callable[..., subprocess.CompletedProcess[str]]
) -> str | None:
    """Apply one violation, run its gate, put the file back; the problem, or None."""
    path = root / violation.file
    original = path.read_bytes()
    path.write_bytes(original + violation.text.encode("utf-8"))
    try:
        done = run(
            [_executable(violation.gate), *violation.args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        path.write_bytes(original)
    if done.returncode == 0:
        return f"{violation.gate} passed a deliberate violation in {violation.file}"
    if violation.marker not in f"{done.stdout}{done.stderr}":
        return (
            f"{violation.gate} failed (exit {done.returncode}) without the marker "
            f"{violation.marker!r}"
        )
    return None


def prove(
    root: Path, *, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> list[str]:
    """The failures: a gate that passed the violation, or failed without its marker.

    Each violation is appended to its file in ``root`` and the file's exact bytes are put back
    afterwards, also when the gate raises. An empty list means every gate failed as it should.
    """
    found = (_check(root, violation, run) for violation in VIOLATIONS)
    return [problem for problem in found if problem]


def main(argv: Sequence[str] = ()) -> int:
    repo = Path(__file__).resolve().parent.parent
    archive = subprocess.run(
        ["git", "-C", str(repo), "archive", "--format=tar", "HEAD"],
        capture_output=True,
        check=True,
    ).stdout
    failures = 0
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        root = Path(folder)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
            tar.extractall(root, filter="data")
        for violation in VIOLATIONS:
            problem = _check(root, violation, subprocess.run)
            failures += problem is not None
            print(f"{violation.gate}: {problem or 'failed as it should'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
