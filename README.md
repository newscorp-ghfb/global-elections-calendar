# Global Elections Calendar

A daily GitHub Actions job scrapes election calendars and publishes
`elections.json`; a Chrome extension shows it. Version 2 (`v2.0.0`) is released: nine sources are
merged, checked and published daily, and the extension shows what could not be checked as well as
what was. Release notes:
[`docs/extension/v2.0.0-release-notes.md`](docs/extension/v2.0.0-release-notes.md). Design:
[`docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`](docs/superpowers/specs/2026-10-16-never-miss-v2-design.md).

## How it works

1. **Sources.** The daily job fetches the pages of the nine sources listed under Sources and parses each into
   election records.
2. **Merge.** The records are merged into one feed, `elections.json`, with one card per election.
3. **Health.** Each source and the run get a severity (`ok`, `warning` or `error`) in `status.json`
   and `HEALTH.md`; the run's verdict, `green` or `red`, is in `HEALTH.md` and the artifact's
   `verdict.json`. A source that fails keeps its last good baseline, and the feed says so.
4. **Publish.** The publish job validates the artifact and commits the feed and the health files
   to `main`.
5. **Extension.** The Chrome extension reads the published feed and the status, and shows each
   election with a warning when its source could not be checked.

The design is in
[the spec](docs/superpowers/specs/2026-10-16-never-miss-v2-design.md).

## Sources

| Source | Page |
|---|---|
| ElectionGuide | `https://www.electionguide.org/elections/type/{view}/` |
| OSCE/ODIHR | `https://odihr.osce.org/odihr/elections` |
| Wikipedia | `https://en.wikipedia.org/wiki/{year}_{kind}_electoral_calendar` |
| NDI | `https://www.ndi.org/elections-calendar` |
| A-WEB | `https://www.aweb.org/eng/bbs/B0000007/list.do?menuNo=300052&option=all` |
| EISA | `https://www.eisa.org/election-calendar/` |
| IPU | `https://data.ipu.org/elections/` |
| Carter Center | `https://www.cartercenter.org/programs/democracy/elections-observed/` |
| EEAS | `https://www.eeas.europa.eu/eeas/eu-election-observation-missions-1_en` |

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

The extension suite (`tests/extension/`) runs headless Chromium build 1248; install it once
with `.venv\Scripts\python.exe -m playwright install chromium` (CI uses `--with-deps`).

The extension's worker is a module (`extension/background.js`). It wires Chrome's events to
`lib/worker.js`, runs one check at a time, fetches the two files and loads the schema files.
`lib/load.js` does one ordered, linked check of `elections.json` and `status.json` and writes
the result in a single `storage.set` (`elections_cache_v2`, `status_cache`, `check_state_v2`).
`lib/order.js` holds the publication order and the status selection, `lib/validate.js` and
`lib/schema.js` the validation. The popup reads `elections_cache_v2`, `status_cache`,
`check_state_v2` and `pinned_countries` from storage and asks the worker to check. `lib/render.js`
draws v2 documents; `lib/legacy.js` (v1.0.2's renderer) draws `legacy` and `update_needed`
documents only. `lib/health.js` gives the banner, panel and footer, and `lib/count.js` the tabs,
filters and counters.

mypy (strict) and ruff are configured in `pyproject.toml`; import layering
is in `importlinter.ini`. `ruff format` is not a gate.

**RT-01, the gates fail on purpose:** `.venv/Scripts/python.exe -m scripts.prove_gates` extracts
`git archive HEAD` into a temporary directory, adds one deliberate violation each for mypy, ruff
and import-linter, and checks that each gate fails with its expected message (a few seconds;
it proves the committed tree, and the CI gates job runs it as its last step).

## CI

`.github/workflows/update-elections.yml`. The workflow holds no logic: every decision is a
function in `elections_calendar.ci` with a test, and the YAML only checks out, installs, moves
the artifact and calls `python -m elections_calendar.ci <command>` or `scraper.py`. Its structure
is proven offline by `tests/workflow/`, and the workflow has run on GitHub since Plan 5c's B1.

**Triggers (spec 11.1):**

| Trigger | What runs | Can it publish? |
|---|---|---|
| `push` to any branch | `gates`, then `verdict` ("gates only") | no |
| `schedule` (00:00 UTC daily) | all four jobs | yes, on `main` |
| `workflow_dispatch` on `main`, `publish: true` | all four jobs | yes |
| `workflow_dispatch` otherwise (a branch, or `publish: false`) | `gates`, `scrape`, `verdict` | no |

**The four jobs:**

- `gates` (read-only): installs the dev lock and Chromium, then runs pytest (with `CI=true`, so a
  skipped test fails the session), mypy, ruff, import-linter and `scripts.prove_gates`.
  The job has a 30-minute limit, budgeted in `test_gates_job_fits_its_timeout`; a gates run over
  20 minutes is a review trigger.
- `scrape` (read-only): reads the switch files, then (unless paused) runs
  `scraper.py --live --out out` inside `::stop-commands::<random token>` so that page text in a log
  cannot run a workflow command, writes the step summary, and uploads `out/` as the artifact
  `generation` (kept 14 days, uploaded even after a crash; it holds `rejected/pages/`, the raw
  bytes of invalid pages, up to 50 MiB).
- `publish` (`contents: write`, its own concurrency group `publish-elections`): it runs only on
  `main` and only for the schedule or a dispatch with `publish: true`. A running publish
  job is not cancelled by a newer run, but a pending one is replaced by the newer one, and a
  timeout (25 minutes) or a user's cancel stops a running one. Each of these makes the verdict red
  with `publish failed`. It re-checks the
  artifact (nothing outside the allowlist is written) and commits only `elections.json`,
  `status.json`, `HEALTH.md` and `data/sources/**`, pushes, and polls the raw URL for up to 10
  minutes to see the new digest served. CI installs wheels only, so no source build runs while
  the publish job holds its token; the publish step's own dependency code still runs with it.
- `verdict` (read-only, always runs): installs nothing; reads the other jobs' results and outputs
  and the artifact's `verdict.json`, and fails the run unless the day is green.

**Verdict headlines** (green unless marked red): `gates only`, `paused`,
`published` (served `ok`, data green), `not published: no new unacknowledged issues`; red: `gates failed`,
`scrape failed`, `artifact incomplete`, `dry-run artifact`, `verdict.json is malformed`,
`validation failed`, `validation failed (not published)`, `superseded`, `served_mismatch`,
`git failed`, `artifact refused`, `publish refused its context`, `publish failed`, `publish ran while paused`,
`publish ran outside its context`, `publish disagrees with verdict.json`,
`published with open warnings or errors`, `not published: open warnings or errors`,
`alert test`, `unexpected jobs on a push`, and `unknown state: <NAME>` for any value outside the
vocabularies (a missing or unknown state is never green).

**A `superseded` day** (`main` moved during the run, so nothing was committed) is recovered by a
**new** `workflow_dispatch` on `main` with `publish: true`. Never use "Re-run jobs": it keeps the
run's original commit, so it is superseded again (P5A-06).

**Switch files** (at the repository root; present means on, whatever they hold, a dangling link
included): `PAUSE_PUBLISHING` skips the scrape and the publish, and the day's verdict is green
`paused`; `ALERT_TEST` turns the run red (`alert test`) after every other check, to prove that
the failure email reaches its readers.

**Known limits** (each is visible in the run, and the tests prove the rest):

- A passed served check is not a guarantee for every reader. It shows that the raw URL served the
  new digest within 10 minutes. A reader behind another CDN node may get the old bytes for up to 5
  more minutes; 5b's feed/status link shows that case.
- The data verdict is the producer's claim. The publish job re-checks everything it commits, but
  whether the day's data is healthy (`verdict.json`'s green or red) comes from the scrape job. A
  compromised scrape could call a valid feed green; it cannot commit an invalid one.

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

CI installs wheels only (`--only-binary :all:`), so this Linux wheel check must pass before a
lock change is pushed.

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

A **dry run** (`--dry-run`) also shares a request budget of 40 across the worker processes: one
token file per request, created with `O_EXCL`, taken before every attempt and every redirect hop.
Once the budget is spent a request is refused as `fetch_failed` "request budget reached"; it is
never sent and never retried. A clean run makes 16 requests, which leaves 24 for retries and
redirects. The scrape deadline of a dry run is 480 s instead of 720 s.

## Running v2 locally

The v2 pipeline builds one artifact directory from the sources. `python scraper.py ...` is the
same command as `python -m elections_calendar ...`: `scraper.py` is only its entry point.

```powershell
.venv\Scripts\python.exe -m elections_calendar --offline tests/fixtures --now 2026-10-19T12:00:00Z --out out
.venv\Scripts\python.exe -m elections_calendar --live --out out
.venv\Scripts\python.exe -m elections_calendar --live --dry-run --out out
```

- `--offline DIR` reads `DIR/pages.json` instead of the network. `tests/fixtures/pages.json`
  lists the committed fixture pages; run it with `--now 2026-10-19T12:00:00Z`, the time the
  end-to-end test uses.
- `--live` fetches the nine sources.
- `--dry-run` (with `--live` only; with `--offline` it is a usage error) is a live check that
  publishes nothing: at most 40 requests, retries and redirects included, and a 480 s scrape
  deadline. The artifact is complete and can be compared, `verdict.json` records `dry_run` and
  `requests`, and `HEALTH.md` opens with `**Dry run:** <n> of 40 requests. Nothing here is
  published.` The publish job and `ci adopt` refuse it.
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
`elections.json`. `red` means a source or the run has a new warning or error: one that nobody
has acknowledged and that is not already known from the last served data (P149; see
"`known_issues.yml`"), or that `elections.json` is over its byte budget (P114). The feed is
still published.

## Building the extension ZIP

```powershell
.venv\Scripts\python.exe -m scripts.build_extension_zip --release-sha <40-hex SHA> [--repo DIR]
```

Without `--release-sha` the build is a development build, and the row keeps `<code SHA>`.

- It builds `dist/Global_Elections_Calendar_v2.0.0.zip` (`dist/` is git-ignored) from the
  explicit file list `FILES` in `scripts/build_extension_zip.py`, and refuses to write anything
  if a check fails: the manifest is at the root, every referenced asset is present, the version
  is 2.0.0, the permission-related manifest keys equal v1.0.2's, and `FILES` equals the files
  under `extension/`. Add a new extension file to `FILES`.
- The bytes are reproducible for one Python minor version and one zlib version.
- It prints the ZIP's SHA-256 and the `RELEASES.md` row, naming both versions. It does not write
  the row: the release's destination, date and approval are recorded by hand; the code SHA comes only from
  a guarded build (`--release-sha`).
- `--release-sha` makes it a guarded release build. It refuses when the SHA is not the full 40
  lowercase hex, when `git status --porcelain --untracked-files=all` lists anything, or when `HEAD`
  is another commit (a detached `HEAD` at that commit is fine). Only then does it fill the row's
  code SHA. `--repo DIR` (default: this repository) names the repository whose `extension/` is
  built into `<DIR>/dist`.
- The release notes are `docs/extension/v2.0.0-release-notes.md`.

## Updating the extension

### Loaded unpacked ("Load unpacked")

1. In `chrome://extensions`, note the folder the extension was loaded from.
2. Delete the folder's contents (keep the folder).
3. Extract the v2.0.0 ZIP into it.
4. Turn on Developer mode (top right) if it is off, then click Reload on the extension's card.

Do not remove the extension: removing it deletes your pins and settings. The extension ID depends
on the folder path, and the manifest carries no `key`.

### Chrome Web Store

Upload the same ZIP. Users update automatically, with the same ID and the same storage.
**No permission prompt is expected**, because the permissions are v1.0.2's. That is an expectation:
it is confirmed only once a Store update lands (open item O4).

## `ci adopt`: the first baselines

The first baselines are not written by a publish job. The user approves one artifact, and
`ci adopt` copies its baselines into a checkout once:

```powershell
.venv\Scripts\python.exe -m elections_calendar.ci adopt --artifact DIR --manifest-sha256 HEX --repo DIR
```

- **Which artifact:** a **published** artifact of the scrape job, from a normal run. Do not use
  the artifact of a `--dry-run` (it carries `dry_run: true` and is refused) or of a validation
  failure (it has no baselines and is refused). The dry-run artifact is the one you *compare*; the
  published artifact is the one you *adopt*. They are two different artifacts.
- `HEX` is the SHA-256 of that artifact's `manifest.json`, which you read and approve first. Any
  other manifest is refused: `the artifact is not the approved one`.
- The artifact must pass every check the publish job makes (`load_artifact`), and its feed must
  serve each source's own `baseline.json`.
- It copies only `data/sources/**`, prints each path and `adopted <n> files from the run of
  <code_sha> (manifest <HEX>)`, and commits nothing. `elections.json`, `status.json` and
  `HEALTH.md` are not copied.
- It refuses when `--repo` (default: the current directory) already has a `data/sources`: the
  first baselines are adopted once.

## Rollback

To go back to the pre-v2 code (spec 15 step 7; P122, P123), run these steps from a checkout of
`main`. Every write to `main` needs the user's go-ahead at the time; 5c's runbook holds the
`MERGE_APPROVED` steps. `scripts/republish.py` writes files and never commits; with `--check` it writes nothing.

1. **Commit `PAUSE_PUBLISHING`.** v2's workflow reads it, so v2's scheduled and dispatched runs
   stop scraping and publishing. A v2 run already in flight is `superseded` at its next push.
2. **Check, then republish a recorded feed:**

   ```powershell
   .venv\Scripts\python.exe -m scripts.republish --from-commit <40-hex SHA> --check
   .venv\Scripts\python.exe -m scripts.republish --from-commit <40-hex SHA>
   ```

   `--check` runs every check and builds both files, writes nothing, and prints
   `recovery pair ok: <commit> (<digest>, recorded in <RELEASES.md|status.json>); its feed can be republished`.
   Run the second command only when it passes. The second command writes the files and prints
   `republished <commit> (<original sha256>) as <new sha256>`. Review
   `elections.json` and `status.json`, then commit and push them (spec 15 step 7.2).
3. **Restore the pre-v2 tree and commit it:**

   ```powershell
   git restore --source=pre-v2 --staged --worktree -- . ':(exclude)elections.json' ':(exclude)status.json' ':(exclude)HEALTH.md' ':(exclude)data/sources' ':(exclude)RELEASES.md' ':(exclude).gitattributes'
   git commit -m "Roll back to the pre-v2 code"
   ```

   The excludes are `elections_calendar.ci.recovery.ROLLBACK_EXCLUDES`. `PAUSE_PUBLISHING` is not
   excluded: `pre-v2` has none, so this commit removes it and brings back v1's workflow. **From
   this commit on, v1 is the writer:**
   - v1's workflow has no `push` trigger, so the push itself starts nothing;
   - its next 00:00 UTC run, or a dispatch, publishes v1's feed (spec 15: "accepted as newer");
   - it never reads `PAUSE_PUBLISHING` and commits only `elections.json`;
   - `status.json` stays the republication's, so v2 clients then show "current health can't be
     confirmed for this data" (spec 12.1).

   Check that the served digest still equals the republished one before 00:00 UTC.
4. **Only if v1 must be held back too:** before step 3, disable the workflow on GitHub
   (`gh workflow disable update-elections.yml -R newscorp-ghfb/global-elections-calendar`), and
   enable it again to resume
   (`gh workflow enable update-elections.yml -R newscorp-ghfb/global-elections-calendar`). That
   state is outside the repository, so no commit changes it. Disabling stops new runs only: a run
   already in progress goes on, and its publish job is `superseded` because step 1's commit moved
   `main`. `gh run cancel <id> -R newscorp-ghfb/global-elections-calendar` stops it sooner. The
   drill on GitHub is 5c's.

**Recovery pairs.** A pair is a `main` commit and the SHA-256 of its `elections.json` blob
(`git show <commit>:elections.json`). `republish.py` restores only a commit that is in `main`'s
history (the checkout must be on branch `main`) and has a pair, recorded in one of two formats:

- a row under "Recovery pairs" in `RELEASES.md`, written by hand with the user's approval:
  `| Name | <40-hex commit> | <64-hex digest> | Checked |`, each hash optionally in backticks.
  This is the only way to record the `pre-v2` feed, whose commit has no `status.json`;
- otherwise, the `serving_feed_sha256` in that commit's own `status.json`.

A row decides when there is one. The blob must hash to the digest, and its format must be a v2 feed
(`schema_version` exactly 2) or a v1 feed (no `schema_version`) that passes the format's checks.
The republished file is the original with `published_at` set to now and `republished_from_sha256`
(the original's digest) added; `status.json` records outcome `republished`. A missing or altered
pair, an abbreviated SHA or another format exits 1 with the reason and writes nothing.

## Live check

`scripts/live_check.py` runs the sources once for real, as a dry run, and compares the result
with a fresh offline run on the fixtures. It is a report for the person who decides whether the
first rollout goes ahead. It is **not a gate**: nothing in CI runs it.

```powershell
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python.exe -m scripts.live_check --out .scratch/live
```

Set this machine's TLS bundle variable first, as for any live run (see "TLS"). It makes read-only
GET requests, at most 40 including retries and redirects, and is killed with every process it
started after 600 s; the offline run is killed after 120 s, and a bad offline run stops the check
before the live run starts. `--out DIR` gets a folder named by the UTC time, holding `live_check.md`
(the report), the two artifacts, and the two logs. The exit code is 0 when the report is written
and the live run exited 0, 1 when the live run was killed or failed (the report is still
written), and 2 for a bad reviewed file.

**Material differences** (the report counts them; the first rollout pauses on any):

- a fixture page missing live, not `ok`/`valid_empty` live, or with `units_seen` under half or
  over double the fixture's (when the fixture's is above 0);
- a source at severity `error`;
- a national contest of `tests/expected/2026-10-16.yaml` whose dates overlap the live window and
  that has no witness child: a child on a card of the same place and level, with the entry's
  office inside its office label, the same round (and jurisdiction, when the entry names one),
  and a card that overlaps the entry's dates. A contest seen on another date is
  `possible reschedule, review required` until a row in `tests/expected/reviewed_reschedules.yaml`
  (keys in its header) links the old date to the new one after the user has reviewed it;
- a feed over its byte budget, more than 40 requests, a run killed at the limit, or a live file
  that cannot be read.

Everything else (live-only pages, every source's severity, feed and gzip bytes, requests used,
elapsed time) is listed for information.

## `out/`

| File | When | What it is |
|---|---|---|
| `elections.json` | published | The feed. 524,288 bytes is the budget: a feed over it is published, and `HEALTH.md` says "over budget". Over 2,000,000 bytes it fails validation. |
| `status.json` | always | What the feed serves now, and why. |
| `HEALTH.md` | always | The run, each source and the attention items, for people. |
| `data/sources/<source>/baseline.json` | published, when there is one | The last accepted snapshot of the source. |
| `data/sources/<source>/candidate.json` | published | This run's snapshot of the source. |
| `data/sources/<source>/health_state.json` | published | `last_absent_at`: when each reason that a `known_issues.yml` entry names was last absent, each pair kept until it is 14 days old; and `reset_at`, the acknowledgements' reset time. |
| `verdict.json` | always | The verdict, its reasons, the feed's length and budget, and `over_budget`: true when the feed is longer than the budget, which makes the verdict `red` (the feed is still published); `dry_run`: true on a `--dry-run`; and `requests`: the requests a dry run made (an integer), else null. |
| `attention_full.json` | always | Every attention item, uncapped, with the text to acknowledge it by. |
| `dispositions.json` | always | What the merge did with every claim. |
| `rejected/` | on a failure | The bytes and the problems of whatever failed validation. |
| `rejected/pages/<source>/<i>.body` | when a page is kept | The exact bytes of page `i` (its position, in decimal) when its body is not empty and its parser failed, its source's ledger has a problem, or its own outcome is not `ok` or `valid_empty`. A run keeps at most 50 MiB of them; a page past that is listed with `kept: false` and has no file. |
| `rejected/pages/index.json` | whenever any page is listed, including `kept: false` rows past the cap | One row per such page, in source order: source, index, key, year, URLs, outcomes, status, content type, length, SHA-256, why and `kept`. |
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

A unit reason whose every unit was already in the last served data is *known*: it is shown, but
it does not make the run red (P149). A unit is the same when its page's scope, its outcome and
its text match, and a second row with the same text is a new unit. A unit acknowledgement then
only turns it grey. Every other reason is red on each run while it lasts.

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
