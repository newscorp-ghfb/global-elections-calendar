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
An up-front page that cannot be read stays unfinished, and its source becomes `worker_failed`.
A source whose later pages depend on earlier ones (NDI's pager, EISA's year tables) names only
its first page up front; its adapter reports any later page it expected but did not receive,
or could not read, as `pagination_incomplete` (the source is `worker_failed` either way).
The cut worker is terminated, and killed if it is still alive after a 5 s grace
period. The **return bound** is longer: `run_sources` returns within the latest cutoff plus the
grace period plus 2 s, cleanup included, and no child outlives it. This bounds fetching only.
Parsing runs afterwards and has no time bound here (Plan 4).

## Running v2 locally

The v2 pipeline builds one artifact directory from the sources. `python scraper.py ...` is the
same command as `python -m elections_calendar ...`: `scraper.py` is only its entry point.

```powershell
.venv\Scripts\python.exe -m elections_calendar --offline tests/fixtures --now 2026-10-19T12:00:00Z --out out
.venv\Scripts\python.exe -m elections_calendar --live --out out
```

- `--offline DIR` reads `DIR/pages.json` instead of the network. `tests/fixtures/pages.json`
  lists the committed fixture pages; run it with `--now 2026-10-19T12:00:00Z`, the time the
  end-to-end test uses.
- `--live` fetches the nine sources.
- Give exactly one of the two.
- `--now ISO` is the time to judge the data at. It needs a time zone, and its UTC year must be
  1900 to 2199. The default is the machine clock. With `--live` it judges the real fetch times
  at the given moment. That is for tests: a `--now` before the fetch makes the fetch times lie
  in the future.
- `--out DIR` is required. It must be new or empty.
- `--repo DIR` is the checkout that holds the last published files (`elections.json`,
  `status.json`, `data/sources/`, `known_issues.yml`). The default is the current directory.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | A complete artifact was written, whatever the verdict. |
| 1 | The run failed before it could write one: an untrusted CA bundle, or an unexpected error. |
| 2 | Usage error: a bad option, a bad `--now`, a bad `pages.json`, or an `--out` that is not empty. |

A run prints one line, for example `published, verdict red, 377390 feed bytes`: the outcome
(`published` or `validation_failed`), the verdict (`green` or `red`) and the length of
`elections.json`. `red` means a source or the run has an open warning or error that nobody has
acknowledged. The feed is still published.

## `out/`

| File | When | What it is |
|---|---|---|
| `elections.json` | published | The feed. 524,288 bytes is the budget: a feed over it is published, and `HEALTH.md` says "over budget". Over 2,000,000 bytes it fails validation. |
| `status.json` | always | What the feed serves now, and why. |
| `HEALTH.md` | always | The run, each source and the attention items, for people. |
| `data/sources/<source>/baseline.json` | published, when there is one | The last accepted snapshot of the source. |
| `data/sources/<source>/candidate.json` | published | This run's snapshot of the source. |
| `data/sources/<source>/health_state.json` | published | `last_absent_at`: when each reason that a `known_issues.yml` entry names was last absent, each pair kept until it is 14 days old; and `reset_at`, the acknowledgements' reset time. |
| `verdict.json` | always | The verdict, its reasons, the feed's length and budget, and `over_budget`: true when the feed is longer than the budget, which makes the verdict `red` (the feed is still published). |
| `attention_full.json` | always | Every attention item, uncapped, with the text to acknowledge it by. |
| `dispositions.json` | always | What the merge did with every claim. |
| `rejected/` | on a failure | The bytes and the problems of whatever failed validation. |
| `rejected/pages/<source>/<i>.body` | when a page is kept | The exact bytes of page `i` (its position, in decimal) when its body is not empty and its parser failed, its source's ledger has a problem, or its own outcome is not `ok` or `valid_empty`. A run keeps at most 50 MiB of them; a page past that is listed with `kept: false` and has no file. |
| `rejected/pages/index.json` | when a page is kept | One row per such page, in source order: source, index, key, year, URLs, outcomes, status, content type, length, SHA-256, why and `kept`. |
| `manifest.json` | always, written last | Each other file with its SHA-256. |

A publish job (Plan 5) will commit only the repository files: `elections.json`, `status.json`,
`HEALTH.md` and `data/sources/`. The rest stays in the run's artifact. A run that stopped half
way has no `manifest.json`.

## `known_issues.yml`

`known_issues.yml` at the repository root lists what people have looked at and accepted. It is
a YAML list. The file explains its own rules at the top. There are three kinds of entry:

- **acknowledgement:** one reason of one source. Its `scope` (`stage`, `year`, `page`) says
  which reason it covers. For an open reason that a scope can acknowledge, `HEALTH.md` prints
  the scope to paste. For a unit reason (`unparsed_relevant`, `partial_relevant`) it says to
  acknowledge each unit by its `unit_text`. For a reason that can never be acknowledged it says
  so. For a reason that is already acknowledged it prints the entry's end time. An info reason
  has no hint.
- **unit acknowledgement:** one unparsed or partly parsed unit, named by its full text
  (`unit_text` in `attention_full.json`, whitespace collapsed). One entry per unit.
- **`accept_drop`:** accepts a drop in a source's counts (`sudden_drop` or `cumulative_drop`).
  It sets two minimums, `accept_units_seen_min` and `accept_claims_min`. The new snapshot must
  reach both. The drop reason in `HEALTH.md` gives the candidate's counts. It needs a
  `scope.page`.

Rules that hold for every entry:

- It lasts at most 14 days: `expires_at` is after `acknowledged_at`, and at most 14 days
  later.
- It ends when its reason goes away and comes back (recurrence). A new occurrence needs a new
  entry. Absence is recorded by published runs only, for the reasons that an unexpired entry
  names, in `health_state.json`.
- A `coverage_gap` stays listed in `HEALTH.md` while it is acknowledged. An entry made before
  the gap began never covers it.
- If `health_state.json` of a source is corrupt, or is missing while the source has a
  `baseline.json`, every acknowledgement of that source stops counting. The run that reads it
  records a reset time, if that run publishes. Only acknowledgements made after it count, so
  renew them.
- These can never be acknowledged: `ledger_mismatch`, `discovery_mismatch`, `fallback_stale`,
  `served_mismatch`, `attention_truncated`, `ack_invalid`, `merge_failed`,
  `validation_failed` and every info reason.
- A file that is not valid YAML, or an entry that breaks a rule, gives `ack_invalid` and has no
  effect.

## Registry changes

Before committing a change to `data/places.yaml`, `data/institutions.yaml` or
`data/subdivisions.yaml`, run the offline check above with `--repo` pointing at a checkout that holds `data/sources/`
(without baselines there is nothing to compare), and read `HEALTH.md`.

Each snapshot records the version of those three files. The first live run after a change finds
every source's baseline made under another version. That baseline is never served, but it still
counts for the drop checks. A source whose fetch fails that day, or whose counts drop, is
`unavailable` until a later run is clean. A drop that the change itself caused needs an
`accept_drop` entry.

## Legacy status

The `status` of a card is one of `Upcoming`, `Held`, `Postponed`, `Cancelled`, `Disputed` and
`Unknown`. A cancelled election that another source still lists shows
`Cancelled` with `status_conflict` set on the child. A rescheduled one shows `Upcoming` on its
new date, with the old date in `rescheduled_from`.

## Checking v2 against v1 (SC1 and SC2)

Two files in `tests/expected/` are written by hand, and `tests/pipeline/test_end_to_end.py`
checks the pipeline against them on the fixture pages.

- `2026-10-16.yaml` lists the 122 contests a person reading the pages would expect in the feed.
  Each has a quote from its source's page. The test needs each entry to fit exactly one child
  of the feed, and each child in scope to fit exactly one entry.
- `legacy-mapping-exceptions.yaml` lists the records of the v1 feed of 2026-10-16 that do not
  map to exactly one v2 card. A record maps to the card of its place whose span holds its date.
  If several cards fit, the record's link picks one, then its office. The card must also hold a
  child or an umbrella whose label matches the record's type (the witness).
  - `unmapped`: no card fits. These are the five EEAS observation missions that v1 dated
    1 October.
  - `ambiguous`: two cards still fit.
  - `merged`: several v1 records are one v2 card.
  - `unwitnessed`: the card holds no witness. A record goes here only with a comment that says
    why its contest is still represented. The list is empty today.

  The test requires every list to match what the mapping finds. When a change moves a record,
  decide whether the move is right, then update the file.
