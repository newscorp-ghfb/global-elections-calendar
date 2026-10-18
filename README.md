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

## Reference data

These files are generated and committed; review their diffs. Never edit
them by hand: edit the inputs and rebuild.

| File | Built by | Inputs |
|---|---|---|
| `data/feed_country_history.tsv` | `python -m scripts.count_feed_countries ff30417` | every `elections.json` version in git up to `ff30417` |
| `data/places.yaml` | `python -m scripts.build_places` | `pycountry`, `data/places_manual.yaml`, the history TSV |
| `data/subdivisions.yaml` | `python -m scripts.build_subdivisions` | `pycountry`, `data/subdivisions_manual.yaml` |
| `data/institutions.yaml` | `python -m scripts.build_institutions` | the IPU chamber table fixture, `data/institutions_manual.yaml` |

```powershell
.venv\Scripts\python.exe -m scripts.build_places
.venv\Scripts\python.exe -m scripts.build_subdivisions
.venv\Scripts\python.exe -m scripts.build_institutions
```

Tests fail when a committed file is out of date with its inputs.

## TLS

Certificates are verified on every request. The trust store is certifi's
roots plus, when set, the CA bundle named by `REQUESTS_CA_BUNDLE`,
`SSL_CERT_FILE` or `CURL_CA_BUNDLE`. On a network whose HTTPS is
intercepted by a corporate proxy, that variable names the bundle holding
the proxy's root; CI sets none and uses certifi alone.

## How a scrape is bounded

`runner.run_sources` fetches each source in its own spawned child process, at most four at a
time, and never waits on a child except through its exit signal. Each source has a **work
cutoff**: the earlier of its own start plus 4 minutes and the 12-minute scrape deadline. The
parent cuts the worker within its wake latency of the cutoff, and no page published after the
cut counts; a worker cut at its cutoff is reported as a deadline even if it had just finished.
A received page that cannot be read stays unfinished, and its source becomes `worker_failed`.
The cut worker is terminated, and killed if it is still alive after a 5 s grace
period. The **return bound** is longer: `run_sources` returns within the latest cutoff plus the
grace period plus 2 s, cleanup included, and no child outlives it. This bounds fetching only.
Parsing runs afterwards and has no time bound here (Plan 4).
