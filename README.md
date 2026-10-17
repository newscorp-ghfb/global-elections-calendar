# Global Elections Calendar

A daily GitHub Actions job scrapes election calendars and publishes
`elections.json`; a Chrome extension shows it. Version 2 is being built on
`feat/never-miss-v2`. Design:
[`docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`](docs/superpowers/specs/2026-10-16-never-miss-v2-design.md).

## Development setup

Python 3.14. Every dependency is pinned with hashes.

**Windows:**

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.txt
```

**Linux:**

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
```

## Gates

Run from the repository root. All four must pass before a commit.

**Windows (local):**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\mypy.exe
.venv\Scripts\ruff.exe check
.venv\Scripts\lint-imports.exe --config importlinter.ini
```

**Linux (CI):**

```bash
.venv/bin/python -m pytest -q
.venv/bin/mypy
.venv/bin/ruff check
.venv/bin/lint-imports --config importlinter.ini
```

mypy (strict) and ruff are configured in `pyproject.toml`; import layering
is in `importlinter.ini`. `ruff format` is not a gate.

## Updating dependencies

Edit `requirements.in` (runtime) or `requirements-dev.in` (development),
then regenerate both locks:

```powershell
.venv\Scripts\python.exe -m piptools compile --generate-hashes --allow-unsafe --strip-extras -o requirements.txt requirements.in
.venv\Scripts\python.exe -m piptools compile --generate-hashes --allow-unsafe --strip-extras -o requirements-dev.txt requirements-dev.in
```

Then check that Linux CI can install every pin:

```powershell
.venv\Scripts\python.exe -m pip download --require-hashes --only-binary=:all: --implementation cp --python-version 3.14 --platform manylinux_2_39_x86_64 --platform manylinux_2_34_x86_64 --platform manylinux_2_28_x86_64 --platform manylinux_2_27_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux2014_x86_64 --platform linux_x86_64 --platform any -r requirements-dev.txt -d .scratch/linux-wheels
```
