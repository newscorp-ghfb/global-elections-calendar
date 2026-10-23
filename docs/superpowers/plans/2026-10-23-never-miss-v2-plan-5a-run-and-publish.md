# Never-miss v2, Plan 5a: Run and publish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 3 (2026-10-23).** Written against `2927bb0` (Plan 4 complete: 2214 tests, mypy 112
files, ruff clean, `Contracts: 2 kept, 0 broken`).
- **Revision 2 folds in the red-team review** of revision 1
  (`Downloads/never-miss-v2-plan-5a-red-team-review-2026-10-23.md`, sha256 of rev 1
  `ebaa95cb…`). All five findings were checked against the source, and P5A-01, P5A-04 and
  P5A-05 were reproduced (`.scratch/plan5a/served_rel.py`, `served_loop.py`,
  `expected_witness.py`). They change P112, P114, P119, P122, P123, P125 and the new P127, and
  Tasks 5–9. See "Review record", rows P5A-01 to P5A-10.
- **Revision 3 folds in the red-team review of revision 2**
  (`Downloads/never-miss-v2-plan-5a-r2-red-team-review-2026-10-23.md`, sha256 of rev 2
  `163d3d9a…`). Both findings were checked against the source and reproduced on the fixture
  run (`.scratch/plan5a/baseline_rows.py`, `witness_rows.py`, `served_guard.py`). They
  change P119, P122, P123, P125 and P127, and Tasks 6, 8 and 9. See "Review record", rows
  R2-01 to R2-07.
- **Plan 5 is split** (the user, 2026-10-23): **5a** (this plan: run and publish), **5b**
  (extension v2.0.0, its ZIP and the Playwright suite), **5c** (the rollout runbook, spec
  §15–§16). Each is written when the one before has landed, against the code as it then is.
- **R36 is Task 1** (the user, 2026-10-23). Its fixture facts were measured before any rule was
  written, as R36 requires (`r36_markers.py`, below).
- **The semantic items under "Spec corrections" need the user's approval before Task 1 starts.**
  Each gives the alternative and what it costs.

**Goal:** Every generation reaches `main` only through a checked path, and every attempt ends in
a stated verdict.
- `scraper.py` is the thin entry point; v1's scraper retires.
- The workflow's jobs only install, call tested Python and move one artifact.
- The publish job verifies that artifact, commits exactly the feed files, pushes without force
  and checks the bytes GitHub serves.
- A `verdict` job sets the run's result on every path (§11.6).
- A dry run is bounded, a rollback restores a verified recovery pair, and Plan 4's leftovers and
  R36 are closed first.

Nothing is pushed: the workflow runs on GitHub for the first time in Plan 5c, with the user's
go-ahead.

**Architecture:**
- **`elections_calendar/ci/`** (new package, top layer beside `__main__`): the job logic, called
  by the workflow as `python -m elections_calendar.ci <command>`.
  - **Light modules** (the standard library, `model` and `text` only, so they run without the
    venv; P117):
    - `context` decides who triggered the run and whether it may publish, and holds the output
      vocabularies;
    - `manifest` checks `manifest.json` against the files;
    - `summary` writes job outputs and the step summary;
    - `switches` reads `PAUSE_PUBLISHING` and `ALERT_TEST`;
    - `verdict` implements §11.6.
  - **Heavy modules:**
    - `artifact` decides what may be committed;
    - `git` is a thin subprocess wrapper;
    - `publishing` does the race check, the commit, the push and the served check;
    - `recovery` handles recovery pairs and republication.
  - `__main__` holds the commands. It imports the heavy modules only inside their commands.
- **`.github/workflows/update-elections.yml`** is rewritten: four jobs (`gates`, `scrape`,
  `publish`, `verdict`). Structural tests pin every trigger, permission, condition, timeout, pin
  and output.
- **`fetch.RequestBudget`** bounds a dry run's requests across worker processes.
- **`scripts/republish.py`** and **`scripts/live_check.py`** are thin command-line tools.

**Tech Stack:**
- Python 3.14.1 and the standard library (`subprocess`, `hashlib`, `json`, `argparse`,
  `os.open` with `O_CREAT | O_EXCL`);
- PyYAML 6.0.3 (already a runtime dependency) for the workflow tests;
- git: the tests use local bare repositories, never a remote;
- GitHub Actions on `ubuntu-24.04`.

No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`.
- Read these sections first:
  - §4 (the layers);
  - §5.7 and §5.8;
  - §9.6;
  - all of §11;
  - §13.3 (the S4, NM, V2 and RT rows), §13.5 and §14;
  - §15, §16 and §17.
- Where this plan and the spec differ, the plan wins *only* for the items under "Spec corrections".
- Plan 4 (`docs/superpowers/plans/2026-10-20-never-miss-v2-plan-4-health-snapshots-feed.md`) is
  built at `2927bb0`. Its Interfaces blocks describe the code, except where its own ledger's
  fix-wave rulings say otherwise.

## "As built" errata (read first)

**Plan 4** (built at `2927bb0`; record: `handovers/elections-v2-plan4-sdd-ledger.md`):
- **The run** is `python -m elections_calendar (--live | --offline DIR) --out DIR [--now ISO]
  [--repo DIR]`, exit 0/1/2 (README "Running v2 locally").
  - On the fixtures (`--offline tests/fixtures --now 2026-10-19T12:00:00Z`) it takes 3.4 s and
    prints `published, verdict red, 377390 feed bytes`.
  - It writes a 4.6 MB `out/`: `elections.json` 377,390 bytes, `HEALTH.md` 27,266,
    `status.json` 3,019, `verdict.json` 1,242, `attention_full.json` 126,100,
    `dispositions.json` 184,065, `manifest.json` 3,488, and `data/sources/<source>/` for all
    nine sources.
  - Parse time per source on the fixtures (`parse_ms`): 16 to 241 ms.
- **The `out/` layout** is Plan 4 Task 8's table. `manifest.json` (`{"schema_version": 1,
  "files": {posix path: sha256}}`) is written last and lists every other file under `out/`,
  except `*.tmp` files.
- **`verdict.json`** is `{verdict, outcome, severity, reasons, feed_bytes, feed_budget_bytes,
  trust_sources}`. `verdict` is `green` or `red`; `outcome` is `published` or
  `validation_failed`.
- **`status.json` `sources[]`** carry `name` (the display name), `severity`, `using_fallback`
  and `served_fetched_at`, with no source key (Task 2 adds it). Its `outcome` enum already
  includes `superseded`, `paused` and `republished`.
- **`schemas/feed-v2.schema.json`** has `additionalProperties: false` at the top level and no
  `republished_from_sha256` (Task 8 adds it).
- **`attempt_of(environ, now)`** reads `GITHUB_RUN_ID`, `GITHUB_EVENT_NAME` and `GITHUB_SHA`. A
  value of the wrong shape becomes `"local"`.
- **`tests/support/repo.commit(out, repo)`** copies the repository files of `out` into `repo`
  "as Plan 5's publish job will". Task 6 makes it call the real copy (`ci.artifact`).
- **Parse failures lose their traceback.** `pipeline._parse_source` and `_fetch_offline` keep
  only `type(exc).__name__`. The live runner's worker already prints its traceback to stderr
  (`runner._work`). Task 3 closes this (R33).
- **Plan 4's leftovers, recorded for this plan** (ledger, final review and fix wave):
  - **M3:** after a worker failure, every unfinished page gives a `deadline` reason.
  - **M12:**
    - each attention item's `snapshot_id` costs 12,560 bytes;
    - the legacy trio (`sources`, `source_names`, `links`) costs 28,360 bytes;
    - `status.json` sources lack the source key.
  - **The spec erratum:** §9.6's example `page: null` never matches a page reason.
  - **Two parked hand-edit items:**
    - a unit page with no `unit_prefix` skips `load_baseline`'s `units_seen` check;
    - a future-dated `last_absent_at` pair is carried for 14 days past its time.
  - **M2's child half:** "every child that needs an attention item has one" was not checkable
    from the feed.
- **The live run** needs 16 requests on a clean day: ElectionGuide 3, Wikipedia 4, NDI 2 (the
  chain), EISA 2 (calendar and one year table), and one each for OSCE, IPU, A-WEB, Carter and EEAS
  (`tests/fixtures/pages.json`).

**R36's fixture facts** (`.scratch/plan5a/r36_markers.py` → `r36_markers.txt`, measured
2026-10-23 on `tests/fixtures/ndi/2026-10-19/p0.html`–`p4.html`):
- **Every one of the 68 cards holds exactly one `button` whose class list is exactly
  `add-to-cal`.**

  | Page | upcoming cards = markers | past cards = markers |
  |---|---|---|
  | p0 | 10 | 10 |
  | p1 | 8 | 10 |
  | p2, p3, p4 | 0 | 10 |

- **No marker lies outside the two card blocks.**
- **The string `add-to-cal` occurs elsewhere.** It appears 48 times in p0's text: in CSS, in
  scripts, and in each card's `div class="add-to-cal-button"` wrapper. A substring count would
  double every card, so the rule matches the exact class token.

**v1** (on `main` at `ff30417`):
- `scraper.py` (890 lines) and `.github/workflows/update-elections.yml` (one job, `contents:
  write`, `pip install -r requirements.txt`, `git pull --rebase` then push) are v1's.
- `extension/background.js` reads
  `https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/elections.json`.
- `elections.json` at the root is v1's feed of 2026-10-16. It is the served file, so leave it.

## Plan series

1. **Foundations** (done, `8632297`).
2. **Sources:** 2a (done, `f5f3a1c`), 2b (done, `94ac45a`), 2c (done, `fa4d0a2`).
3. **Merge** (done, `6ba511b`).
4. **Health, snapshots, feed and publishing** (done, `2927bb0`).
5. **Workflow, extension and rollout**, in three plans:
   - **5a: run and publish (this plan);**
   - **5b:** extension v2.0.0, its ZIP and the Playwright suite;
   - **5c:** rollout and housekeeping.

**Not in this plan:**
- **Nothing leaves this machine.** No push, no workflow dispatch, no `ALERT_TEST` or
  `PAUSE_PUBLISHING` on `main`, no `MERGE_APPROVED`, no `pre-v2` tag, no Store upload (D10).
  Tests push only to bare repositories under `tmp_path`.
- **Not the first baselines:** `data/sources/` stays absent from the repository. Task 6 builds
  the tool (`ci adopt`); 5c runs it on a reviewed artifact.
- **No extension change:**
  - 5b changes `extension/`, `help.html` and `manifest.json`;
  - 5b writes `scripts/build_extension_zip.py` and the ZIP rows of `RELEASES.md`;
  - 5b adds the Playwright suite and any `xvfb-run` it needs.
- **The client half of recovery is 5b's:**
  - 5b orders feeds by `published_at` (V2-T03, NM-T03).
  - 5a proves the producer half: the republished bytes, their digest and their timestamps.
- **The live check runs once, read-only** (Task 9). Running it for the first baselines is 5c's.
- Nothing is merged.

## Global Constraints

Plans 1–4's Global Constraints still hold:
- **Code:**
  - the layering (the import-linter layers contract);
  - civil dates;
  - no network in tests;
  - `[0-9]`, never `\d`, in new regexes;
  - time is passed in, and a naive datetime raises;
  - timestamps on disk are UTC with a `Z` suffix (`model._utc_iso`);
  - a corrupt committed file is never read as empty.
- **Process:**
  - the four gates, each in its own shell call;
  - mutation checks;
  - `.scratch/` for scratch files.
- **Git:**
  - work on `feat/never-miss-v2` only;
  - check `git rev-parse --abbrev-ref HEAD` in its own call before every commit;
  - end each commit with the `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`
    trailer (or the implementer's own model name).

This plan adds:

- **The layers** (P106):

  ```
  __main__ | ci
  pipeline
  feed | publish | validate
  merge
  health | snapshots
  ledger | runner
  sources
  fetch | dates | places | offices | window
  model | text
  ```

  `ci` never imports `__main__` or `pipeline`. It reads artifacts, never builds them.
- **The workflow holds no logic.** Every decision a job makes is a function in
  `elections_calendar.ci` with a test. Its YAML only checks out, installs, moves the artifact and
  calls `python -m elections_calendar.ci <command>` or `scraper.py`.
- **No expression reaches a shell.** A `${{ … }}` value reaches a `run:` step only through `env:`,
  never inside the script text.
- **Job outputs carry fixed words only.** `GITHUB_OUTPUT` gets `name=value` lines whose values are
  from this plan's vocabularies (`true`, `false`, the publish outcomes, the served results). Free
  text, such as a reason or an error, goes to the step summary, escaped, never to an output.
- **Unknown fails closed.** An unknown job result, a missing output, a malformed `verdict.json` or
  an unreadable manifest makes the verdict red, or the artifact refused, and never green.
- **Exact bytes.** Every file the publish job, `ci adopt` or `republish.py` writes keeps its exact
  bytes through git: LF, no BOM, no re-encoding. On this machine `core.autocrlf` is `true`, and
  `.gitattributes` marks the served files `-text` (§16). `ci.git` also passes
  `-c core.autocrlf=false` to every git command, and recovery reads blobs with
  `git cat-file blob`, never from the working tree.
- **Tests never touch a real remote or this checkout's git state.** Git tests run in bare and
  cloned repositories under `tmp_path`, always as `git -C <tmp path>`.
- **Literals and messages** are copied verbatim from this plan.

## Review Focus

These are the five inputs most likely to hurt the people who rely on this pipeline that the spec
implies but no step spells out. Each one is pinned by the named tests, in the task that owns the
code.

1. **An artifact that tries to write beyond the feed.** The scrape job parses untrusted web pages,
   so its artifact can be wrong in any way.
   - The cases: a manifest key with `..`, a leading `/`, a backslash or a drive letter; a file
     named `.github/workflows/x.yml` or `known_issues.yml`; a source folder that is not one of the
     nine; a file not in the manifest; a `status.json` from another commit; a dry-run artifact.
   - **A self-consistent artifact with bad content:** an invalid feed whose digest was written into
     `status.json` and the manifest; a malformed `baseline.json` or `health_state.json`; a feed
     whose served snapshot is not the baseline being committed, or is a committed baseline
     that is corrupt or another source's; a failed validation whose `status.json` names a
     feed other than the one the repository keeps.
   - The publish job refuses every one and commits nothing. It writes only the allowlisted
     repository paths.

   Pinned by `test_publish_refuses_an_incomplete_artifact`,
   `test_an_artifact_with_an_unexpected_file_is_refused`,
   `test_a_self_consistent_invalid_artifact_is_refused`,
   `test_a_failed_validation_must_name_the_retained_feed` and
   `test_served_links_to_the_committed_baseline` (Task 6).
2. **Text that reaches the workflow machinery.** A reason text with a newline and
   `served=ok`, a `HEALTH.md` of 2 MB, a `${{ github.event... }}` string, or a `::add-mask::`
   line in a page that a traceback or a log line echoes.
   - None of them changes a job output.
   - The summary stays under GitHub's 1 MiB limit.
   - The workflow never interpolates an expression into a shell script.
   - Nothing the scrape prints can run a workflow command.

   Pinned by `test_outputs_hold_fixed_words_only` (Task 5), `test_summary_is_capped` (Task 5),
   `test_no_expression_in_run_scripts` and `test_scrape_logs_stop_workflow_commands` (Task 7).
3. **A CI state nobody planned for.** A job `cancelled` by its timeout, an empty `PAUSED`, a
   `PUBLISH_OUTCOME` of `banana`, a missing `verdict.json`, a `verdict.json` that says
   `"verdict": "GREEN"`.
   - Each one is red, with a headline that names it, and never green.

   Pinned by `test_unknown_states_are_red` (Task 5).
4. **Bytes that git or the CDN change.** On this Windows checkout `core.autocrlf` is `true`; GitHub's
   raw CDN serves an old copy for up to 5 minutes.
   - The committed blobs of `elections.json`, `status.json`, `HEALTH.md` and `data/sources/**` equal
     the artifact's bytes, and `git show <commit>:elections.json` hashes to the recorded digest.
   - The served check polls at most 10 times and never starts a fetch at or after its 600 s
     deadline: the deadline is checked before every fetch, and a fetch gets only the time left.
     A fetch that overruns the deadline anyway (the Fetcher does not bound name resolution,
     connecting or dripped headers) is not counted, whatever its body.

   Pinned by `test_committed_bytes_equal_the_artifact` (Task 6), `test_served_check` (Task 6),
   `test_served_fetcher_is_bounded` (Task 6) and `test_recovery_pair_round_trip` (Task 8).
5. **Two processes at once.** Two workers take a dry-run request token at the same instant;
   another writer pushes to `main` between the race check and the push; the live check's child is
   killed while its own workers run.
   - No token is given twice, and the budget is never exceeded.
   - The late push is `superseded` and commits nothing.
   - No worker outlives the live check.

   Pinned by `test_request_budget_is_shared` (Task 4),
   `test_another_writer_before_the_push_is_superseded` (Task 6) and
   `test_an_overrunning_run_is_killed_with_its_children` (Task 9).

**Known limits, by design.** Each is visible:
- **The workflow is proven offline.** The tests check the YAML's structure and the Python it
  calls. GitHub's own evaluation of `if:` expressions, outputs and artifacts runs first in 5c's
  branch run (§15 step 1), which is where O7 (the run summary) and R5 (certifi on GitHub's
  runners) close too.
- **A passed served check is not a guarantee for every reader.** It shows that the raw URL served
  the new digest within 10 minutes. A reader behind another CDN node may get the old bytes for up
  to 5 more minutes; 5b's feed/status link shows that case.
- **`superseded` is a red day.** A push to `main` during a scheduled run leaves that day's
  generation unpublished. The user starts a **new** `workflow_dispatch` on `main` with
  `publish: true` (§5.8). GitHub's "Re-run jobs" keeps the run's original `GITHUB_SHA`, so a
  re-run is superseded again; the verdict's detail says so (Task 5).
- **The data verdict is the producer's claim.** The publish job re-checks everything it commits
  (P119), but whether the day's data is healthy (`verdict.json`'s green or red) comes from the
  scrape job. A compromised scrape could call a valid feed green; it cannot commit an invalid one.
- **The artifact is kept for 14 days** (P117). After that, a day's raw invalid pages are gone.

## Spec corrections

These were found while measuring the fixtures and git's behaviour, and while reconciling the spec
with the code at `2927bb0`.
- **Semantic decisions** change what a run reports, what is committed, or how a run is judged:
  P107–P112, P114–P119, P121–P123, P125 and P127. They need the user's approval before Task 1
  starts.
- **The other corrections** (P106, P113, P120, P124, P126) refine names, layout and vocabulary.

| ID | Spec says | This plan does | Why / alternative |
|---|---|---|---|
| P106 (interfaces) | §4 layers; Plan 4's P83 | **`ci` joins the top layer** (`__main__ \| ci`). **A new forbidden contract** keeps `elections_calendar.ci` from importing `pipeline` and `__main__`, so the gate prints `Contracts: 3 kept, 0 broken`. **`md_text` moves from `feed` to `text`**, and `feed` re-exports it, so the light CI modules can escape text without `feed`'s dependencies | The publish job must check an artifact, never rebuild one, and the verdict job must run without the venv. Alternative: CI logic in `__main__` |
| P107 (semantic; R36) | Plan 2c: NDI's units are the wrapper's children, counted by the ledger's own parser | **The ledger also counts NDI's `add-to-cal` markers:** an element whose class list holds that exact token, of any tag. Each card must hold exactly one, each block as many as it has cards, and no marker may lie outside the blocks. Every failure is a `discovery_mismatch` problem: the candidate is invalid, and the problem can never be acknowledged. The layout, pager and P65 checks stay | Measured (`r36_markers.py`): 68 cards, one marker each, none outside; the substring occurs 48 times in p0. R36's conditions all hold: the count covers the whole block; the fixtures were measured first; a missing and a duplicated marker are each a problem; a page with no markers is never valid empty, because its cards still count, and an empty p0 is `layout_not_recognised`. Cost: if NDI changes its button, the source breaks until the rule is updated, which is P6's intent. Alternative: withdraw R36 and keep the wrapper count alone |
| P108 (semantic; M3) | Plan 2a: an unfinished page gives `deadline` | **After a worker failure, unfinished pages give no reason of their own**; the source's `worker_failed` covers them. After a deadline they keep their `deadline` reasons | After a crash, HEALTH.md showed deadlines that never happened, and each one needed its own acknowledgement. Cost: on a worker-failure day an acknowledged `deadline` of such a page is absent, so its next recurrence needs a new entry (§9.6 recurrence). That is a false red, never a false clean. Alternative: keep the reasons (Plan 4) |
| P109 (semantic; Plan 4 parked item) | Plan 4's ruling: mirror the ledger's `prefix or ""` in `load_baseline` | **A baseline page that is `ok` or `valid_empty` but has no `unit_prefix` is corrupt:** `ledger: page '<key>' is <outcome> without a unit_prefix` | Every adapter gives every such page its prefix (`parse_pages`, ElectionGuide and Wikipedia; measured on the nine fixture baselines by `prefixes.py`), so only a hand edit removes one. `prefix or ""` would count every unit of the snapshot on that page. Alternative: the ruling's mirror |
| P110 (semantic; Plan 4 parked item, P94) | P94: a `health_state.json` that cannot be read voids the source's acknowledgements | **A `last_absent_at` or `reset_at` later than the run's `now` makes the file corrupt** (`timestamp of <key> is after the run`). That gives `ack_invalid`, and the next state records `reset_at` | A future absence time is carried for 14 days past it, and it can void acknowledgements made before it. No run writes one. Cost: a hand edit with a skewed clock voids the source's acknowledgements. Alternative: clamp the time to `now` |
| P111 (semantic; M12) | M12 (Plan 4 final review): the feed's weight | **`status.json` sources gain `source`**: the key, required, one of `SOURCE_ORDER`. **The feed is unchanged.** Each attention item keeps its `snapshot_id`, because a `provisional_change` item's snapshot is the candidate's and `source_health` does not carry it. The legacy trio stays, because v1.0.2 reads it and §11.3's legacy contract checks it | The feed is 377,390 bytes of the 524,288-byte budget, so the 40,920 bytes these would save are not needed yet. Task 9 measures the live size (R34). Alternative: drop the per-item `snapshot_id` (saves 12,560 bytes; 5b then joins items to `source_health`, and a provisional item loses its candidate's id) |
| P112 (semantic; M2) | M2: every child that needs an attention item has one | **Narrowed (rev 2, P5A-07): 5a closes the transport half only.** The end-to-end test shows that `attention_full.json` holds every item of the run, that the feed's items are the first relevant ones in cap order, and that `attention_truncated` counts the rest. **Which units and claims need an item** is pinned by Plans 3–4's producer-rule tests: `test_attention_items_*` (`tests/merge/test_cards.py`), `test_provisional_changes`, `test_disappeared_units` (`tests/snapshots/test_decide.py`), `test_disappeared_items` (`tests/snapshots/test_unit_items.py`) and `test_attention_item_unit_rules` (`tests/unit/test_model.py`). **"This child needed one and has it" stays unprovable from the feed**, because a feed child carries no item id (P85). That part of M2 stays open by design | Plan 4 fixed the listing half. Alternative: a `child_ids` field on feed items, which costs bytes and is a second link to keep consistent |
| P113 (erratum) | §9.6's example: `scope: {stage: fetch, year: null, page: null}` | **`page: elections`**, IPU's page key. `known_issues.yml` already uses it | `page: null` never matches a page reason, so the example could not mute anything |
| P114 (semantic; R34) | R34: decide whether an over-budget feed becomes a reason code | **An over-budget feed makes the run red, without a reason code.** `verdict.json` gets `over_budget`, the verdict is red whenever it is true, and `HEALTH.md` keeps its "over budget" line. Nothing reaches `status.json` or the feed. **It is a soft budget:** the over-budget feed is still published. Only §11.3's hard size check (`validate.FEED_MAX_BYTES`, 2,000,000 bytes) blocks publication | The budget protects the extension's weight. The person to tell is the maintainer, through the red run's email, not the reader: a status reason would show in the popup. The fixture feed uses 72% of the budget, and Task 9 records the live size. Alternatives: keep the `HEALTH.md` line only (today an over-budget feed can go unnoticed on a green run); a reason code `over_budget`, which readers would see |
| P115 (semantic; R33) | R33: worker tracebacks go to stderr, never into a committed file; invalid pages' raw bodies stay in the artifact | **Tracebacks:** an offline fetch failure or any parse failure prints `<source>: fetch failed` or `<source>: parse failed`, then the traceback, to stderr. The recorded detail stays `fetch: <Type>` or `parse: <Type>`. **Bodies:** a page with a non-empty body is kept as `rejected/pages/<source>/<index>.body` when its source's parser failed, its ledger has a problem, or its own outcome is not `ok`/`valid_empty`. `rejected/pages/index.json` describes each kept page (Task 3). A run keeps at most 50 MiB of bodies; a page past the cap is listed with `kept: false` | A page's bytes are what a parser fix needs, and the artifact is never committed. The file name is the page's position, never its key. URLs are the fetcher's redacted ones. Alternative: keep every page (up to 20 MiB × 16 per run) |
| P116 (semantic; R30, §13.5) | §13.5: at most 40 requests counting retries and redirects, 4 at a time, 3 attempts of 60 s each, 10 min in total | **`--dry-run`** (with `--live` only) shares a 40-token request budget across the worker processes: one token file per request, created with `O_EXCL`. A token is taken before every attempt and every redirect hop. Once the budget is spent, a request is refused as `fetch_failed` "request budget reached" and is never retried. The scrape deadline is 480 s instead of 720 s. `verdict.json` records `dry_run` and `requests`, and `HEALTH.md` opens with `**Dry run:** <n> of 40 requests. Nothing here is published.` The publish job and `ci adopt` refuse a dry-run artifact. **The 10 minutes** are the live check's hard limit (Task 9), which kills the run's whole process tree | A clean run makes 16 requests (errata), which leaves 24 for retries and redirects. 480 s, plus the 7 s return bound and about 1 s of parsing on the fixtures, fits in 600 s. Alternative: count requests in the parent only, which cannot see the workers' retries |
| P117 (semantic; §11.2) | §11.2's jobs | **The workflow's shape** (Task 7): <ul><li>the triggers of §11.1, with `push` on every branch;</li><li>one artifact, `generation` (`out/`), kept 14 days, uploaded even after a crash for diagnosis, and downloaded to `$RUNNER_TEMP/artifact`;</li><li>`switches`, `scrape-summary` and `verdict` run with setup-python's interpreter and only the light modules, so the verdict job installs nothing;</li><li>the scrape step runs the scraper inside `::stop-commands::<random token>`;</li><li>the gates job sets `CI=true` for pytest.</li></ul> | The minimal summary must survive a failed install. Page text that a traceback echoes must not run a workflow command such as `::add-mask::`. 14 days covers a fortnight of diagnosis; GitHub's default is 90. Alternatives: install the venv in the verdict job; keep the artifact 90 days |
| P118 (semantic; §11.2) | §11.2: workflow-level `concurrency: {group: publish-elections, cancel-in-progress: false}` | **The concurrency group is on the `publish` job**, not the workflow | When a newer run of a group queues, GitHub cancels the older *pending* one. With a workflow-level group, two branch pushes during a scheduled run cancel that day's scheduled run, and a cancelled run sends no failure email. On the publish job, only publishers wait for each other, and a cancelled publish job makes the verdict red (`publish failed`). The push-race check (§11.2 step 2) still serialises commits. Alternative: the spec's workflow-level group |
| P119 (semantic; §11.2 steps 1 and 3, R28) | §11.2: check every file against `manifest.json`; commit one generation | **What an artifact must be** (Task 6's `load_artifact`): <ul><li>a manifest that lists exactly the files present, each path safe and each digest matching;</li><li>every path either a repository path (`elections.json`, `status.json`, `HEALTH.md`, or `data/sources/<one of the nine>/{baseline,candidate,health_state}.json`) or an artifact-only path (`verdict.json`, `attention_full.json`, `dispositions.json`, `rejected/**`);</li><li>`status.json` valid, from this run's commit, and `published` or `validation_failed`;</li><li>`verdict.json` agreeing with it, and not a dry run;</li><li>a published artifact has an `elections.json` whose digest is `serving_feed_sha256`, plus every source's `candidate.json` and `health_state.json`; a failed validation has none of them.</li></ul> **The content is re-checked by the publisher (rev 2, P5A-01)**, with the existing validators and without rebuilding anything: <ul><li>the feed passes §11.3's schema, legacy, invariant, size and timestamp checks (`validate.feed_content_problems`);</li><li>`status.json`'s four serving fields equal `feed.serving_fields` of the bytes that will be served: the artifact's feed when published, the repository's `elections.json` at the run's commit when validation failed;</li><li>for a published artifact (a failed validation carries no source files), every `baseline.json` loads with `load_baseline(path, source=s)`, which now also refuses a baseline of another source (rev 3, R2-01), and every `health_state.json` with `load_health_state` at the run's `attempt_at`, without a problem;</li><li>every `candidate.json` is a JSON object of its own source with a 64-hex `snapshot_id` (no code reads it back);</li><li>each source's served snapshot id in the feed is null, or the `snapshot_id` of the baseline the repository will hold after the commit (the artifact's, else the one committed at the run's commit). **That baseline is loaded through the same `load_baseline(…, source=s)` wherever its bytes come from** (rev 3, R2-01), so a committed baseline whose content no longer matches its stored id, or that belongs to another source, is refused. A baseline the feed does not serve is not loaded: a corrupt one stays and is reported (P94);</li><li>every repository file is at most 10 MiB (the largest fixture file is 755,024 bytes).</li></ul> **The publish job adds and changes files, and never deletes one** | The scrape job parses untrusted pages, so its artifact is untrusted input to a job that can write to `main`. Matching digests only show that the files agree with the producer's own manifest. On the fixture artifact all nine served ids equal their new baseline's (`served_rel.py`). The loader recomputes `snapshot_id` from the units and claims (`Snapshot.__post_init__`): a committed OSCE baseline with one claim's office or dates edited and its id kept gives `record: Snapshot: snapshot_id does not match its units and claims`, and IPU's baseline at OSCE's path loads cleanly; only `pipeline._read_baseline`, which `ci` may not import (P106), refused it (`baseline_rows.py`). Because nothing is deleted, a corrupt committed baseline that a run did not replace stays, and is reported every day (P94), instead of being silently reset. Alternative: mirror `data/sources/`, which deletes |
| P120 (vocabulary; §11.2 steps 2–6) | §11.2 | <ul><li>**Publish outcomes:** `published`, `validation_failed`, `superseded`, `refused`, `git_failed`, `not_allowed`.</li><li>**Served results:** `ok`, `served_mismatch`, `not_checked`.</li><li>**The race check** is `git fetch origin main`, then `FETCH_HEAD`.</li><li>**The commit** is by `github-actions[bot]` (`41898282+github-actions[bot]@users.noreply.github.com`), with the message `chore: update elections.json [<attempt_id>]` or `chore: record a failed validation [<attempt_id>]`.</li><li>**The push** is `git push --porcelain origin HEAD:refs/heads/main`; a `[rejected]` line means `superseded`.</li></ul> The command exits 0 for every outcome. **`superseded` and `paused` are recorded in the job summary and outputs**, not in a `status.json` inside the artifact (V4 and §5.8 say "the run artifact and summary"): the artifact is uploaded before the publish job runs, and a paused run makes none. `feed.AttemptOutcome` gains only `republished` (Task 8) | The verdict job reads the outcome, so the publish job never sets the result (§11.2 step 6). `FETCH_HEAD` does not depend on how the checkout configured its remote-tracking branches. v1's messages start `chore: update elections.json` |
| P121 (semantic; §11.6, NM-T05) | §11.6's matrix | **Task 5's rule table, in order**, with three additions: <ul><li>an unknown value of any input is red (`unknown state: <NAME>`);</li><li>`ALERT_TEST` makes a paused run red too;</li><li>on a branch run or a `publish:false` dispatch, the data verdict decides: `not published: healthy` (green), `not published: open warnings or errors` (red), `validation failed (not published)` (red).</li></ul> The verdict job also checks the manifest itself, so a damaged artifact is red on branch runs too | §11.6 lists outcomes, not the inputs the job receives. Every input it can receive needs a result, and anything else must fail closed. Alternative: a paused alert test is green, so the alert would not fire while paused |
| P122 (semantic; §11.5, §15 step 7, R31) | §11.5 recovery pairs; §15 step 7.2 | <ul><li>**The commit** is given as a full 40-character SHA, and it must be in `main`'s history: the checkout must be on branch `main`, and the commit an ancestor of `HEAD` (rev 2, P5A-03). Ancestry shows that the commit is reachable from `main`, not that it was ever `main`'s tip or served: a recovery pair is a validated, recorded candidate, and the user picks which one to restore (§15 step 7.2; rev 3, R2-05).</li><li>**Its pair** is that commit's row in `RELEASES.md`'s "Recovery pairs", or else that commit's own `status.json` `serving_feed_sha256`, whatever its outcome: the serving fields describe the `elections.json` beside them (P5A-01 checks that link at publication).</li><li>**Only two formats are recovered (rev 2, P5A-03).** A v2 feed has `schema_version` exactly the integer 2 and must pass `validate.feed_content_problems`. A v1 feed has no `schema_version` key and must pass `validate.legacy_feed_problems`, v1's contract as v1.0.2 reads it: `generated_at` a real UTC timestamp, `current_month` `YYYY-MM`, `errors` a list, `months` an object of `YYYY-MM` keys to lists of cards, every card passing §11.3's legacy checks. Any other `schema_version` (999, `"2"`, `true`, null) is refused with `format: schema_version <value> is not supported`.</li><li>**The republished bytes** are the original document with `published_at` set to now and `republished_from_sha256` (the original's digest) added, written compactly as `feed_bytes` writes, and checked again in their format. The served check is skipped, because the digest stands in for it.</li><li>**The status** is `status_doc` with outcome `republished`, trigger `republish`, no sources and no reasons. `HEALTH.md` is not touched.</li><li>**`republish.py`** writes the two files and commits nothing.</li></ul> | An abbreviated SHA can become ambiguous. A digest proves which bytes were chosen, not that they make a usable feed, and a commit that was never on `main` was never served. The v1 fixture (`tests/fixtures/feed/2026-10-16-ff30417.json`) has exactly `current_month`, `errors`, `generated_at` and `months`. Alternative: keep the original's formatting (v1's indentation), which needs v1's serialiser |
| P123 (semantic; §15 step 7.3) | §15 step 7.3: "Revert `pre-v2..v2.0.0` as one commit … the revert doesn't touch `elections.json` or `status.json`" | **The rollback restores the pre-v2 tree in one commit**, except the served files, `data/sources/`, `RELEASES.md` and `.gitattributes`: `git restore --source=pre-v2 --staged --worktree -- . <excludes>`, then `git commit`. The excludes are `recovery.ROLLBACK_EXCLUDES`, and Task 8 rehearses it with v1's real workflow. **Rev 2 (P5A-02): that commit hands publishing back to v1, and it removes `PAUSE_PUBLISHING`** (`pre-v2` has none, so the restore deletes it). v1's workflow (`ff30417`, sha256 `a89ac408…`) runs daily at 00:00 UTC and on dispatch, has no `push` trigger, never reads `PAUSE_PUBLISHING`, and commits only `elections.json`. Leaving the marker would only pretend to hold v1 back. **The writer after the rollback is v1**, as §15 intends ("the v1 scraper's daily feed … accepted as newer"). `status.json` stays the republication's, so after v1's first run v2 clients show "current health can't be confirmed for this data" (§12.1), which is true: v1 checks nothing. **To hold v1 back as well**, disable the workflow on GitHub (`gh workflow disable update-elections.yml`) before the restore, and enable it again to resume. That state lives outside the repository, so no commit changes it. Disabling stops new runs only: a run already in progress goes on, and its publish job is `superseded`, because step 1's commit moved `main` (`test_an_interleaved_publisher_is_superseded`). It is a 5c drill (R44), with such a run (rev 3, R2-05) | Rehearsed on 2026-10-23 in a scratch repository (`revert_rehearsal.py`, git 2.53). The range revert stops at a modify/delete conflict on `data/sources/<source>/candidate.json`, because the first baselines are in the range and every publication rewrites them. It also deletes the `baseline.json` files that no publication touched. The restore needs no conflict resolution and keeps the latest baselines for a re-release. It also undoes any v2 hotfix made after `v2.0.0`, which assumes v2 code anyway. 5c's runbook uses it. Alternative: the range revert, with a loop of conflict resolutions |
| P124 (interfaces; §15 step 2, RT-03) | §15 step 2: the user approves the first baselines from the dry-run artifact | **`python -m elections_calendar.ci adopt --artifact DIR --manifest-sha256 HEX`** copies only `data/sources/**` into the repository. The artifact must be published, not a dry run, and its `manifest.json` must have the approved digest. The repository must not have a `data/sources/` yet. Nothing is committed | The approval is tied to the exact candidate's bytes (RT-03). Alternative: copy the files by hand |
| P125 (semantic; §13.5) | §13.5: "the output is compared with the fixture expectations" | **`scripts/live_check.py`** compares the live dry run with a fresh offline run on the fixtures. **Material differences:** <ul><li>a page's `units_seen` under half or over double the fixture's (when the fixture's is above 0);</li><li>a fixture page that is not `ok`/`valid_empty` live;</li><li>a source at severity `error`;</li><li>**a national contest of `tests/expected/2026-10-16.yaml` whose date span overlaps the live window, with no witness child** (rev 2, P5A-05). A witness has the entry's place and level, the entry's office folded inside its folded `office_label`, the same `round`, the same `jurisdiction` when the entry names one, and a card date span that overlaps the entry's. **A moved contest needs a reviewed link** (rev 3, R2-02): a row of `tests/expected/reviewed_reschedules.yaml` that names the entry (place, office, round, jurisdiction, `from` its date) and the new date (`to`). `rescheduled_from` lists old dates as the sources wrote them (D2). It is shown, never parsed, and alone it proves nothing: a child that matches all but the date, has a non-empty `rescheduled_from` and has no reviewed row is the material line `possible reschedule, review required`. A same-place, same-date card for another office is not a witness;</li><li>a feed over the budget;</li><li>more than 40 requests;</li><li>a run killed at 10 minutes.</li></ul> Everything else is listed for information | The check is not a gate. It decides whether 5c's first rollout pauses for the user. The witness is SC1's rule (`entry_children` in `tests/pipeline/test_end_to_end.py`) without `status` and `source`, which change from day to day. On the fixture feed it finds all 74 in-window national entries, as the country/date rule does, but losing Brazil's Presidency child from its 2026-10-04 card (Presidency, Chamber, Senate) is visible only to the witness (`expected_witness.py`). The reviewed file starts empty: a reschedule seen live is a material line until the user reviews it and adds its row. `witness_rows.py` runs every row of Task 9's test on the fixture feed. Alternative: compare whole snapshots, which always differ days apart |
| P126 (interfaces; §11.2, §14, RT-01) | §11.2: the extension suite must not skip when `CI=true`, and the counts go to the job summary. §14: each gate is proven with a deliberate failure | **`tests/conftest.py`** fails a session that skipped any test when `CI=true`, and appends the counts to `GITHUB_STEP_SUMMARY` when that is set. **`scripts/prove_gates.py`** is a gates-job step, not a pytest test. It extracts `git archive HEAD` into a temporary directory and shows that mypy, ruff and import-linter, run as the README's Linux commands, each fail on one deliberate violation | Running the gates inside pytest would double the suite's time. pytest's own failure needs no proof beyond the conftest test. Alternative: prove all four inside pytest |
| P127 (semantic; §11.2 step 5, S4-T12; rev 2, P5A-04) | §11.2: poll the served file for up to 10 minutes. Rev 1: `publish` 15 minutes | **The served check has one absolute deadline, 600 s from its start.** It checks the deadline before every fetch, gives each fetch only `min(60, time left)`, and returns `served_mismatch` at the deadline, so a fetch never starts at or after it. **A fetch that returns after the deadline is not counted, whatever its body** (rev 3, R2-06). A real fetch can overrun its bound, because the Fetcher does not bound name resolution, connecting or dripped headers (`fetch.py`'s docstring). A fetch that ends exactly at the deadline counts. **The publishing steps before the served check share a `PUBLISH_STAGE_S` = 240 s deadline**, started before `load_artifact`. Only git calls check it: each is refused once it has passed, and each gets `min(60, time left)`. It does not interrupt `load_artifact` or a copy in progress (rev 3, R2-06): a slow check is caught at the next git call, before anything is written, as `git_failed`, `the publish stage's time limit was reached`. **The publish job's `timeout-minutes` becomes 25:** setup 300 + download 60 + stage 240 + served 600 + report 30 = 1230 s of 1500. **The hard bound is the job's timeout:** a fetch or a git call that overruns by more than the 270 s margin gets the job cancelled, which the verdict reads as `publish failed` (red) | Rev 1's loop checked the time only after a fetch. With 45 s fetches it started a 7th fetch at 600 s and returned at 645 s, and even 1 s fetches returned at 601 s (`served_loop.py`). Rev 1's 600 + 300 = 900 s left no room for git or the artifact. Alternative: keep 15 minutes and cut the served limit to 6 minutes, which leaves less than one CDN expiry (5 minutes) of margin |

**Also settled (no spec change):**
- **`scraper.py` keeps its name.** `python scraper.py` and `python -m elections_calendar` are the
  same command (R32).
- **The served check fetches exactly the extension's URL**, without a cache-busting query, because
  the point is what readers get (S4-T09).
- **A first run over v1's `elections.json`:** `status.json`'s serving fields describe the feed that
  is served, so a first run that fails validation records v1's digest.
- **The committer is unchanged from v1:** the publish job's `GITHUB_TOKEN`. A push made with it
  does not start another run.
- **Two preview artifacts, two uses (P5A-08):**
  - a branch run or a `publish: false` dispatch makes a full artifact, which `ci adopt` takes for
    the first baselines (5c);
  - `--dry-run` makes a request-bounded diagnostic artifact, which `ci adopt` and the publish job
    refuse by design.

  Never edit `dry_run` to get past that check.

## Review record

**Status:** "planned" becomes "verified" only when the SDD ledger records the task's commit, with
the named test passing and its mutation killed.

| ID | Kind | Ruling | Task · test | Status |
|---|---|---|---|---|
| R10 (Plan 2b) | Requirement | The scrape job's 20 minutes hold the 720 s deadline, the return bound, parsing and setup | T7 `test_scrape_job_fits_its_timeout` | planned |
| R27 (Plan 4) | Requirement | P117–P121 | T5 `test_outcome_matrix`; T6 `test_publish_reaches_the_writer_only_when_allowed`, `test_another_writer_before_the_push_is_superseded`, `test_a_failed_validation_commits_status_and_health_only`; T7 the workflow tests | planned |
| R28 (Plan 4) | Requirement | P119 | T6 `test_publish_refuses_an_incomplete_artifact` | planned |
| R29 (Plan 4) | Requirement | P120 | T6 `test_served_check`, `test_served_mismatch_is_red` | planned |
| R30 (Plan 4) | Requirement | P116, P125 | T4 `test_dry_run_writes_nothing`, `test_request_budget_is_shared`; T9 the live check's report | planned |
| R31 (Plan 4) | Requirement | P122, P123 | T8 `test_recovery_pair_round_trip`, `test_rollback_hands_publishing_to_v1`, `test_a_missing_or_altered_pair_blocks_restoration` | planned; V2-T03 (the client) is 5b's |
| R32 (Plan 4) | Requirement | `scraper.py` is the thin entry point | T3 `test_scraper_entry_point_runs_the_pipeline` | planned |
| R33 (Plan 4) | Requirement | P115 | T3 `test_worker_traceback_is_logged_not_committed`, `test_invalid_page_bodies_are_in_the_artifact` | planned |
| R34 (Plan 4) | Requirement | P114 | T3 `test_an_over_budget_feed_is_a_red_run`; T9 the live size | planned |
| R36 (Plan 4) | Requirement, approved by the user in principle | P107 | T1 `test_ndi_marker_count_matches_the_fixture_cards`, `test_ndi_missing_marker_is_a_ledger_problem`, `test_ndi_duplicate_marker_is_a_ledger_problem`, `test_ndi_without_markers_is_not_valid_empty` | planned |
| M2 (Plan 4 final review) | Finding | P112 | T2 `test_every_relevant_item_is_served_or_counted` | planned |
| M3 (Plan 4 final review) | Finding | P108 | T2 `test_a_worker_failure_gives_no_deadline_per_page` | planned |
| M12 (Plan 4 final review) | Finding | P111 | T2 `test_status_sources_carry_the_source_key` | planned |
| Parked: a unit page without a prefix | Finding | P109 | T2 `test_a_unit_page_without_a_prefix_is_corrupt` | planned |
| Parked: a future-dated state pair | Finding | P110 | T2 `test_a_future_health_state_is_corrupt` | planned |
| §9.6 example | Erratum | P113 | T2 (the spec's text) | planned |
| S4-T05 (commit part) | Spec acceptance | Only `status.json` and `HEALTH.md` are committed | T6 `test_a_failed_validation_commits_status_and_health_only` | planned |
| S4-T08 | Spec acceptance | Superseded before the race check, and between it and the push | T6 `test_another_writer_before_the_push_is_superseded` | planned |
| S4-T09 | Spec acceptance | The served check reads the extension's URL | T7 `test_served_check_reads_the_extension_url` | planned |
| S4-T10 (setup, test and push parts) | Spec acceptance | A failed install or test is `gates failed`, a failed push is `git failed`, a timed-out job is `cancelled` | T5 `test_outcome_matrix`; T6 `test_push_failures_are_git_failed` | planned |
| S4-T12 | Spec acceptance | The time budgets | T7 `test_scrape_job_fits_its_timeout`, `test_publish_job_fits_its_timeout`; T9 `test_dry_run_fits_the_live_check_limit` | planned |
| S4-T18, V2-T07 | Spec acceptance | `publish:false` and branch dispatches never reach the writer | T5 `test_publishing_allowed`; T6 `test_publish_reaches_the_writer_only_when_allowed`; T7 `test_job_conditions` | planned |
| S4-T19 (CI part) | Spec acceptance | Text never reaches an output; the summary is escaped and capped; the log takes no commands | T5 `test_outputs_hold_fixed_words_only`, `test_summary_is_capped`; T7 `test_scrape_logs_stop_workflow_commands` | planned |
| NM-T04 (served part) | Spec acceptance | The served check compares byte digests | T6 `test_served_check` (a copy with the same `content_id` and other bytes is a mismatch) | planned |
| NM-T05 | Spec acceptance | P121 | T5 `test_outcome_matrix` | planned |
| NM-T08 | Spec acceptance | Permissions, conditions, and an artifact whose digest changed | T6 `test_publish_refuses_an_incomplete_artifact`; T7 `test_permissions_are_least`, `test_job_conditions` | planned |
| V2-T05 (producer part) | Spec acceptance | P122, P123 | T8 `test_recovery_pair_round_trip`, `test_rollback_hands_publishing_to_v1`, `test_a_missing_or_altered_pair_blocks_restoration` | planned; the client check is 5b's |
| RT-01 | Spec acceptance | P126 | T7 `test_prove_gates_applies_and_restores_each_violation`; the controller's run of `scripts/prove_gates.py` | planned; on GitHub in 5c |
| RT-02 | Spec acceptance | The dry run and publishing are separate privileges, and page text is inert | T5 `test_outputs_hold_fixed_words_only`; T6 `test_an_artifact_with_an_unexpected_file_is_refused`; T7 `test_permissions_are_least` | planned |
| RT-03 (tool part) | Spec acceptance | P124 | T6 `test_adopt_takes_only_the_approved_artifact` | planned; the review itself is 5c's |
| RT-05 (rehearsal in temporary repositories) | Spec acceptance | P123 and the race check | T8 `test_an_interleaved_publisher_is_superseded`, `test_rollback_hands_publishing_to_v1` | planned; the drill is 5c's |
| §13.5 | Spec | P116, P125 | T9 | planned |
| §14 (configuration) | Spec | `scraper.py` is in mypy's `files` and no longer excluded from ruff | T3 (the gates) | planned |
| I2 (Plan 3 final review) | A ruling for the user's veto | Unchanged | — | open (the user's) |
| R37 | Parked by the user | Unchanged | — | open (parked) |
| P5A-01 (red-team, High) | Finding: a self-consistent artifact could publish an invalid feed or saved state, and a failed validation could name a wrong retained feed. Confirmed against rev 1's rules | P119's content re-check | T6 `test_a_self_consistent_invalid_artifact_is_refused`, `test_a_failed_validation_must_name_the_retained_feed`, `test_served_links_to_the_committed_baseline` | planned |
| P5A-02 (red-team, High) | Finding: the restore brings back v1's workflow, which never reads `PAUSE_PUBLISHING`. Confirmed on v1's file (`ff30417`): schedule and dispatch only, no pause step, commits `elections.json` only. Spec §15 means v1 to resume, so the defect was rev 1's step 4 implying the marker still held v1 | P123: the restore commit hands publishing to v1 and removes the marker; holding v1 too is `gh workflow disable` (5c drill) | T8 `test_rollback_hands_publishing_to_v1` (with v1's real workflow as a fixture) | planned; the GitHub drill is 5c's (R44) |
| P5A-03 (red-team, Medium) | Finding: the non-v2 branch accepted any JSON object; a pair's commit only had to exist locally. Confirmed | P122: v1 and v2 formats only; the commit must be in `main`'s history | T8 `test_only_supported_formats_are_republished`, `test_a_pair_must_be_on_main` | planned |
| P5A-04 (red-team, Medium) | Finding: the served loop started a fetch at the deadline (645 s with 45 s fetches, 601 s with 1 s fetches), and the publish budget had no room for git. Reproduced (`served_loop.py`) | P127 | T6 `test_served_check`, `test_the_publish_stage_has_a_deadline`; T7 `test_publish_job_fits_its_timeout` | planned |
| P5A-05 (red-team, Medium) | Finding: a same-country, same-date card hid a lost contest. Confirmed: on the fixtures, removing Brazil's Presidency child leaves the country/date rule satisfied | P125's witness child | T9 `test_compare_needs_a_witness_child` | planned |
| P5A-06 (red-team, smaller) | GitHub's "Re-run jobs" keeps the run's `GITHUB_SHA`, so a re-run after `superseded` is superseded again | Recovery is a new dispatch; the verdict's detail says so | T5 `test_outcome_matrix` (row 13's detail); full and partial re-runs measured in 5c (R46) | planned |
| P5A-07 (red-team, smaller) | P112 proved transport, not the whole child obligation | P112 narrowed, citing Plans 3–4's producer-rule tests | T2 `test_every_relevant_item_is_served_or_counted` | planned; the child-to-item witness stays open by design |
| P5A-08 (red-team, smaller) | The two preview artifacts must not be confused | "Also settled"; Task 6's README `ci adopt` section | T6 `test_adopt_takes_only_the_approved_artifact` (dry-run row) | planned |
| P5A-09 (red-team, smaller) | Job-level concurrency accepted; its cancel → verdict → email chain needs a drill | P118 unchanged | 5c (R46) | open (5c) |
| P5A-10 (red-team, smaller) | Over budget is a soft budget, not a block | P114 wording | — | done in rev 2 |
| R2-01 (rev 2 red-team, Medium) | Finding: a reused committed baseline was read for its `snapshot_id` only. Confirmed: the loader would catch an edited claim (`snapshot_id does not match its units and claims`) but was not called, and no loader `ci` may use checks the source (`baseline_rows.py`) | P119: `load_baseline(…, source=s)` for the served baseline wherever it comes from | T6 `test_served_links_to_the_committed_baseline` (5 rows), `test_a_self_consistent_invalid_artifact_is_refused` (the IPU row) | planned |
| R2-02 (rev 2 red-team, Medium) | Finding: any non-empty `rescheduled_from` excused the date. Confirmed: under rev 2's rule an unrelated or unreadable old date made a witness | P125: reviewed reschedule rows; otherwise a material `possible reschedule` line | T9 `test_compare_needs_a_witness_child` (`witness_rows.py`) | planned |
| R2-03 (rev 2 red-team, small) | Check 11 read as applying to failed validations, which carry no source files | Check 11 is for published artifacts only | T6 `test_a_failed_validation_commits_status_and_health_only` | planned |
| R2-04 (rev 2 red-team, small) | The JSON-list recovery row expected a message that `republished_feed` never reaches; `2.0` was untested | The row expects `the feed is not a JSON object`; a `2.0` row; `republished_problems(b"[]")` tested directly | T8 `test_only_supported_formats_are_republished`, `test_republished_feed_passes_the_schema` | planned |
| R2-05 (rev 2 red-team, small) | Ancestry is not proof of service; disabling a workflow does not stop a run in progress | P122 and P123 wording; R44's drill includes a run in flight | T8 `test_an_interleaved_publisher_is_superseded`; 5c (R44) | planned |
| R2-06 (rev 2 red-team, timing) | A match after the deadline counted; the real fetch's bound was assumed, not tested; the stage deadline was described as if it interrupted validation | P127: the post-fetch guard, the Fetcher's real limits, the stage deadline as built | T6 `test_served_check` (overrun rows), `test_served_fetcher_is_bounded`, `test_the_publish_stage_has_a_deadline` (slow-check row) | planned |
| R2-07 (found while fixing R2-06) | Task 6 called `trust_bundle(environ)`; the function is `trust_bundle(dest, environ)` and returns a `TrustBundle` | `served_fetcher(environ, *, workdir, url=RAW_URL)` | T6 `test_served_fetcher_is_bounded` | planned |
| P106–P127 | Decisions (the semantic ones need approval) | As in "Spec corrections" | Each task's tests, as named there | planned |

## How to execute this plan

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Do not create worktrees, do not switch branches, do not commit to `main`.
  - Keep the shell in the worktree. Use `( cd … && … )` subshells for anything elsewhere.
- **Style:** this plan pins names, signatures, rules, messages and test values; you write the
  bodies. Private helpers are yours. If a rule is ambiguous, stop and ask the controller. Never
  guess a value.
- **Measured values:** the probes in `.scratch/plan5a/` run from the worktree root as
  `PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe .scratch/plan5a/<script>`.
  - `r36_markers.py` → `r36_markers.txt`: NDI's markers per card, block and page (Task 1).
  - `prefixes.py`: the fixture baselines' page prefixes (P109). It reads `.scratch/plan5a/out/`,
    an offline run on the fixtures.
  - `revert_rehearsal.py` → `revert_rehearsal.txt`: the range revert and the restore (P123).
  - **The probes confirm the values; the rules define them.** If a value cannot be explained by
    its input and the rule next to it, stop and report it. Never change an expected value to
    match.
- **Per task:** follow the Implement-Review loop in the user's CLAUDE.md (at most 3 rounds):
  1. Pre-flight against the current source.
  2. Write the failing test.
  3. Implement.
  4. Run the four gates, each in its own shell call:
     - `.venv/Scripts/python.exe -m pytest -q`
     - `.venv/Scripts/mypy.exe`
     - `.venv/Scripts/ruff.exe check`
     - `.venv/Scripts/lint-imports.exe --config importlinter.ini`
  5. Run the mutation table.
  6. Commit.
- **Cost (an estimate by analogy with Plan 4, not a measurement):** nine tasks at one implementer
  and one reviewer each, about one fix round per task with its scoped re-review, then a final
  whole-branch review with one fix wave. That is about 28–36 agent runs, roughly USD 250–400, or
  two to three days of the USD 150 daily budget. Every task ends at a green commit, so a day can
  stop after any task.
- **Bounds:**
  - One task at a time, never two in parallel.
  - One reviewer per round, fresh each round; at most 3 fix rounds per task.
  - If round 3 ends with a gate red, a Critical or Important finding open, or a mutation alive,
    stop: commit nothing that is not green, and report what is open. A 4th round needs the user's
    say-so.
  - An AWS, Bedrock or budget error stops all work at the last green commit, with uncommitted work
    in a named stash.
  - No merge and no push.
- **Mutations:** one per new test, in `.scratch/mutations/plan5a-task-<N>.json`, in the format of
  `.scratch/mutate.py`.
  - Stage the task's files with `git add` first, and run with `PYTHONDONTWRITEBYTECODE=1`.
  - Choose mutations that fail fast. A loop that runs into `MUTATE_TIMEOUT_S` is a timeout, not a
    kill.
  - After every task, re-run the earlier tables' uniqueness check (a later task can make an old
    row's search string appear twice).
- **Handover:** after every task, record the commit, the Review record rows it verified and the
  next task in two files:
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-plan5a-sdd-ledger.md` (new);
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-RESUME.md`.
- **Hook:** the Desktop PostToolUse hook runs `ruff check --fix` on each edited `.py`. Check
  `git diff --stat` for unrelated rewrites.
- **Git in tests:**
  - Tests run `git` from `PATH` (2.53 here) in repositories under `tmp_path`.
  - Helper commits pass `-c user.name=… -c user.email=… -c commit.gpgsign=false`, so the machine's
    git configuration does not matter.
  - The Desktop commit hook watches Bash tool calls, not subprocesses, so it never sees these.
  - Never run a test's git command without `-C <tmp path>`.
- **Runtime:**
  - The offline run on all nine fixtures takes about 3.4 s. Build it once per session
    (`tests/support/artifact.py`) and copy it.
  - An OSCE-only run takes well under a second.
  - Each git command costs about 50–150 ms on Windows.
- **Test helpers:**
  - Plan 4's `tests/support/repo.py` (`config`, `offline_dir`, `osce_offline`, `commit`, `NOW`,
    `OSCE`) and `tests/support/fixtures.py`.
  - Task 3 adds `tests/support/broken.py` (adapters that fail).
  - Task 5 adds `tests/support/ci.py` (small artifacts with a manifest).
  - Task 6 adds `tests/support/artifact.py` (real artifacts) and `tests/support/git_repos.py`
    (bare repositories and clones).

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `elections_calendar/ledger.py`, `tests/adapters/test_ndi.py`, `tests/unit/test_ledger.py` | NDI's marker rule | 1 |
| `elections_calendar/snapshots.py`, `elections_calendar/sources/base.py` | M3 (P108); a baseline page without a prefix (P109) | 2 |
| `elections_calendar/health.py`, `elections_calendar/pipeline.py` | a future `health_state.json` time (P110) | 2 |
| `elections_calendar/feed.py`, `schemas/status-v1.schema.json` | `status.json` sources' `source` (P111) | 2 |
| `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md` | the §9.6 example (P113) | 2 |
| `scraper.py`, `pyproject.toml` | the thin entry point (R32) | 3 |
| `elections_calendar/pipeline.py`, `tests/support/broken.py`, `tests/pipeline/` | tracebacks, `rejected/pages/`, `over_budget` (P114, P115) | 3 |
| `elections_calendar/fetch.py`, `elections_calendar/runner.py`, `elections_calendar/__main__.py` | the request budget, `--dry-run` (P116) | 4 |
| `elections_calendar/text.py` | `md_text`, moved from `feed` (P106) | 5 |
| `elections_calendar/ci/__init__.py`, `context.py`, `manifest.py`, `summary.py`, `switches.py`, `verdict.py`, `__main__.py`; `tests/ci/`; `tests/support/ci.py` | the light CI modules and their commands (P117, P121) | 5 |
| `importlinter.ini` | `ci` in the top layer; the forbidden contract (P106) | 5 |
| `elections_calendar/ci/artifact.py`, `git.py`, `publishing.py`; `tests/support/artifact.py`, `tests/support/git_repos.py`; `tests/support/repo.py` | the artifact check, the publish job, `adopt` (P119, P120, P124, P127) | 6 |
| `elections_calendar/validate.py`, `elections_calendar/feed.py` | `feed_content_problems` and the public `serving_fields`, so the publisher re-checks content (P119, P5A-01) | 6 |
| `elections_calendar/snapshots.py`, `elections_calendar/pipeline.py` | `load_baseline(path, *, source=None)`: one loader binds a baseline to its source, for the pipeline and the publisher (R2-01) | 6 |
| `tests/unit/test_served_fetcher.py` | the real served fetcher against the local HTTPS server (R2-06, R2-07) | 6 |
| `.github/workflows/update-elections.yml`, `tests/workflow/` | the workflow (P117, P118) | 7 |
| `tests/conftest.py`, `scripts/prove_gates.py`, `tests/scripts/` | no skips under CI; RT-01 (P126) | 7 |
| `elections_calendar/ci/recovery.py`, `scripts/republish.py`, `RELEASES.md`, `schemas/feed-v2.schema.json`, `elections_calendar/validate.py` (`legacy_feed_problems`, `republished_problems`) | recovery pairs and their two formats, republication, the rollback (P122, P123) | 8 |
| `tests/fixtures/v1/update-elections.yml`, `tests/fixtures/v1/PROVENANCE.md` | v1's real workflow, for the rollback test (P5A-02) | 8 |
| `scripts/live_check.py`, `tests/scripts/test_live_check.py`, `tests/expected/reviewed_reschedules.yaml` | the bounded live check, its witness rule and the reviewed reschedules (P125, P5A-05, R2-02) | 9 |
| `README.md` | the entry point and `rejected/pages/` (3); `--dry-run` (4); `ci adopt` (6); CI (7); rollback (8); the live check (9) | 3, 4, 6, 7, 8, 9 |

## Tasks

### Task 1: NDI's independent marker count (`ledger.py`; P107; R36)

**Files:**
- Modify: `elections_calendar/ledger.py` (`CardBlocksRule`, `COUNT_RULES["ndi"]`, `_CardBlocks`,
  `_discovery_problems`; new `marker_problems`)
- Test: `tests/adapters/test_ndi.py`, `tests/unit/test_ledger.py`

**Interfaces:**
- Consumes: Plan 2c's `CardBlocksRule`, `discover`, `check`, `_CardBlocks`; the fixtures
  `tests/fixtures/ndi/2026-10-19/p0.html`–`p4.html` (`BODIES`, `RAW`, `RES` in `test_ndi.py`).
- Produces:
  - `CardBlocksRule.marker: str | None = None` (a new last field). The docstring gains one
    sentence on the marker rule.
  - `COUNT_RULES["ndi"] = CardBlocksRule((("upcoming-elections", "upcoming"), ("past-elections", "past")), "election-wrapper", marker="add-to-cal")`.
  - `marker_problems(rule: CardBlocksRule, body: bytes, key: str) -> list[str]`.

**The rule (P107).** With `marker` set, `_CardBlocks` also counts **markers**: elements of any
tag, start or self-closing, whose `class` attribute split on whitespace holds `marker` exactly.
`add-to-cal-button` is another token. Text, CSS and scripts never count. The counts are:
- **per card:** the markers in a direct element child of the block's wrapper, or in its
  descendants;
- **per block:** the markers anywhere inside the element with the block's id;
- **outside:** the markers not inside any block element.

`marker_problems` returns `[]` when `rule.marker` is None, or when the body cannot be read
(`_discovery_problems` already reports that). Otherwise it returns, for each block in rule order,
first one problem per card whose count is not 1, then the block's problem, and finally the
outside problem:
- (a) `f"page {key!r}: {slug} card {i} holds {n} {marker} markers"` (cards numbered from 1);
- (b) `f"page {key!r}: {slug} block holds {m} {marker} markers for {c} cards"` when `m != c`;
- (c) `f"page {key!r}: {n} {marker} markers outside the blocks"` when `n > 0`.

`_discovery_problems` appends them after its existing problems when the rule is a
`CardBlocksRule`. They are `discovery_mismatch` problems: never acknowledgeable (§9.6), and they
make the candidate invalid (§9.3). The adapter, the layout check, the pager checks and P65 stay
as they are.

- [ ] **Step 1: Write the failing tests.**
  - In `tests/adapters/test_ndi.py`:
    - **`test_ndi_marker_count_matches_the_fixture_cards`:**
      - for p0–p4, `marker_problems(COUNT_RULES["ndi"], BODIES[n], f"p{n}") == []`;
      - an independent BeautifulSoup count (`.select(".add-to-cal")` in each wrapper child) is 1
        for every card, the per-page totals are the errata's table (68 cards), and there are 0
        markers outside the blocks;
      - p0's text holds the substring `add-to-cal` 48 times, so a substring count would be wrong;
      - `check(RAW, RES).ok`: the fixture ledger stays clean with the marker rule.
    - **`test_ndi_missing_marker_is_a_ledger_problem`:**
      - In p0, the 3rd occurrence of the bytes `class="add-to-cal"` (with the closing quote)
        becomes `class="add-to-calx"`. Then `check` gives exactly one `discovery_mismatch` reason
        and `ok` is false. The problems include
        `page 'p0': upcoming card 3 holds 0 add-to-cal markers` and
        `page 'p0': upcoming block holds 9 add-to-cal markers for 10 cards`.
      - Second case: the 2nd marker is renamed, and `<span class="add-to-cal"></span>` is added
        inside upcoming card 5. The marker problems are exactly
        `page 'p0': upcoming card 2 holds 0 add-to-cal markers` and
        `page 'p0': upcoming card 5 holds 2 add-to-cal markers`. The block still holds 10 for 10,
        so only rule (a) sees it.
    - **`test_ndi_duplicate_marker_is_a_ledger_problem`:** `<span class="add-to-cal"></span>` added
      in three places:
      - inside upcoming card 1 → `… upcoming card 1 holds 2 …` and
        `… upcoming block holds 11 add-to-cal markers for 10 cards`;
      - inside `#past-elections` but outside its wrapper (before its pager) → only
        `page 'p0': past block holds 11 add-to-cal markers for 10 cards`;
      - before `</body>` → only `page 'p0': 1 add-to-cal markers outside the blocks`.

      Each gives `discovery_mismatch`, and `ok` is false.
    - **`test_ndi_without_markers_is_not_valid_empty`:**
      - Every `class="add-to-cal"` in p0 is renamed. p0's coverage stays `ok`, because the adapter
        reads no structure from the marker. The ledger has `discovery_mismatch` with 20 card
        problems and 2 block problems.
      - Both wrappers of p0 are emptied, so cards and markers are gone. p0 is then
        `layout_not_recognised` `upcoming block is page 0 with 0 cards`, never `valid_empty`.
  - In `tests/unit/test_ledger.py`:
    - `test_card_blocks_on_synthetic_pages` passes unchanged, because its rule has no marker.
    - Add **`test_marker_rule_on_synthetic_pages`**, on `block_page` cards with
      `marker="add-to-cal"`, with these rows:
      - a card with no marker;
      - a self-closing `<i class="add-to-cal"/>`;
      - `class="x add-to-cal"`;
      - `class="add-to-cal-button"` alone (not a marker);
      - a marker three levels down in a card (it counts for that card);
      - a `<br>` child of the wrapper (a card with no marker).

      Each row has its exact problem list.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_ndi.py tests/unit/test_ledger.py -q`.
  Expected: the new tests fail (`marker_problems` and `marker` do not exist).
- [ ] **Step 3: Implement** the rule in `elections_calendar/ledger.py`. `_CardBlocks` already
  knows the block and the wrapper depth. A marker inside the wrapper at a depth below its child
  belongs to the wrapper's last child.
- [ ] **Step 4: Run** the two modules, then the whole suite. Expected: PASS. Any other NDI test
  that changes is a finding: report it.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(ledger): count NDI's add-to-cal markers independently (R36)`.

  Mutations, one each:
  - rule (a) is skipped (`test_ndi_missing_marker_is_a_ledger_problem`, its second case);
  - rule (b) is skipped (`test_ndi_duplicate_marker_is_a_ledger_problem`, the pager row);
  - rule (c) is skipped (`test_ndi_duplicate_marker_is_a_ledger_problem`, the `</body>` row);
  - the class is matched as a substring of the attribute (`test_ndi_marker_count_matches_the_fixture_cards`);
  - markers are counted only on the wrapper's direct children (`test_ndi_marker_count_matches_the_fixture_cards`);
  - NDI's rule loses `marker` (`test_ndi_without_markers_is_not_valid_empty`);
  - self-closing tags are not counted (`test_marker_rule_on_synthetic_pages`).

### Task 2: Plan 4's leftovers (`snapshots.py`, `health.py`, `feed.py`, the status schema, §9.6; P108–P113)

**Files:**
- Modify:
  - `elections_calendar/snapshots.py` (`_own_reasons`, `load_baseline`);
  - `elections_calendar/sources/base.py` (the comment above `PAGE_REASONS`);
  - `elections_calendar/health.py` (`load_health_state`);
  - `elections_calendar/pipeline.py` (`_read_state`);
  - `elections_calendar/feed.py` (`status_doc`'s sources);
  - `schemas/status-v1.schema.json`;
  - `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md` (§9.6's example only).
- Test: the modules that hold `test_invalid_candidates`, `test_corrupt_baselines_are_never_served`,
  `test_recovery_after_a_corrupt_state` and `test_status_lists_reasons_and_sources` (find them
  with grep); `tests/pipeline/test_end_to_end.py`.

**Interfaces:**
- Consumes: Plan 4's `decide`, `load_baseline`, `HealthState`, `status_doc`, `SOURCE_ORDER`.
- Produces:
  - `load_health_state(path: Path, *, now: datetime) -> HealthState` (a naive `now` raises
    `ValueError`);
  - `pipeline._read_state(folder: Path, now: datetime) -> HealthState`;
  - `status.json` `sources[]` entries `{source, name, severity, using_fallback, served_fetched_at}`,
    with `source` first.

**Rules:**
- **P108 (M3):** in `_own_reasons`, when `run_outcome == "worker_failed"`, leave out the coverage
  reasons of pages whose outcome is `unfinished`. Runs that ended at `deadline` or
  `scrape_deadline` keep them, and every other page reason stays. The comment above
  `PAGE_REASONS` becomes: "unfinished" is "deadline"; after a worker failure `snapshots` leaves
  those reasons out, and the source's `worker_failed` covers them (P108).
- **P109:** in `load_baseline`'s `units_seen` loop, a page whose outcome is in `_WITH_UNITS` and
  whose `unit_prefix` is None raises through the existing `corrupt` helper with
  `f"ledger: page {page.key!r} is {page.outcome} without a unit_prefix"`.
  - **Pre-flight:** first check that such an edit is not already caught. If `snapshot_id` covers
    `unit_prefix`, the edited file fails its id check first. Then stop and report: P109 is moot.
- **P110:** after `load_health_state`'s existing checks:
  - a `last_absent_at` value later than `now` gives
    `HealthState((), f"timestamp of {_escaped(key)} is after the run")`;
  - a `reset_at` later than `now` gives `HealthState((), "timestamp of reset_at is after the run")`;
  - a time equal to `now` is valid.

  `pipeline._read_state` passes `config.now`. A test of Plan 4's that runs a second run with an
  earlier `now` than the first is a finding: list it, and give it a later `now`.
- **P111:** `status_doc` writes `"source": s.source` first in each sources entry. In the schema,
  `source` is required and is `{"enum": [the nine keys in SOURCE_ORDER]}`.
- **P112:** no code.
- **P113:** in the spec, `scope: {stage: fetch, year: null, page: null}` becomes
  `scope: {stage: fetch, year: null, page: elections}`. Nothing else in the spec changes.

- [ ] **Step 1: Write the failing tests.**
  - **`test_a_worker_failure_gives_no_deadline_per_page`** (M3; build its rows the way
    `test_invalid_candidates` does):
    - a candidate with two `unfinished` pages and the run outcome `worker_failed`
      (`fetch: RuntimeError`) has exactly one `worker_failed` reason and no `deadline`;
    - the same pages with the run outcome `deadline` give one run `deadline` plus one `deadline`
      per unfinished page, as before;
    - a `worker_failed` source whose fetched page is `layout_not_recognised` keeps that page's
      reason;
    - in the pipeline, an OSCE run whose parser fails (`tests/support/broken.py` is Task 3's; use
      a local stand-in here, or a `_parse_failure` raw with an unfinished request) shows one
      `worker_failed` and no `deadline` for OSCE in `status.json`.
  - **`test_a_unit_page_without_a_prefix_is_corrupt`** (P109): a fixture EISA baseline whose
    `calendar` page has `unit_prefix` null and `units_seen` 5 makes `load_baseline` raise with
    `ledger: page 'calendar' is ok without a unit_prefix`. The unchanged file loads.
  - **`test_a_future_health_state_is_corrupt`** (P110):
    - a pair at `now + 1 s` gives the problem `timestamp of <key> is after the run`;
    - `reset_at` at `now + 1 s` gives `timestamp of reset_at is after the run`;
    - both equal to `now` give no problem;
    - a naive `now` raises `ValueError`;
    - in the pipeline, an OSCE repository whose `health_state.json` holds a future pair gives
      OSCE `ack_invalid` `health_state.json is corrupt: timestamp of … is after the run`.
  - **`test_status_sources_carry_the_source_key`** (P111):
    - in the fixture run's `status.json`, `[s["source"] for s in sources] == list(SOURCE_ORDER)`;
    - `validate_status` of a copy that lacks `source` in one entry, or has `"source": "evil"`,
      gives a problem.
  - **`test_every_relevant_item_is_served_or_counted`** (P112, in `tests/pipeline/test_end_to_end.py`):
    - the feed's items are the first `len(items)` of `attention_full.json`'s relevant items
      (`in_or_after_window` and `unknown`), sorted in P87's cap order;
    - `len(items) + attention_truncated == 157`;
    - `attention_full.json` holds exactly the item ids of `tests/support/feed.py`'s first run;
    - the cap is `feed.MAX_FEED_ITEMS` (500), so the fixture feed holds all 157 and
      `attention_truncated == 0`; with `feed.MAX_FEED_ITEMS` patched to 100, there are 100 items
      and `attention_truncated == 57`.
- [ ] **Step 2: Run** them. Expected: they fail, except the M2 test, which passes on today's code
  (it pins P112's guarantee; its mutation below proves it can fail).
- [ ] **Step 3: Implement** P108–P111 and edit the spec for P113.
- [ ] **Step 4: Run** the whole suite. Expected: PASS. Every changed expectation in an older test
  is a finding: list it with the rule that changed it.
- [ ] **Step 5: Gates, mutation table, commit:**
  `fix: Plan 4 leftovers (M3, the parked hand edits, status source keys, §9.6 example)`.

  Mutations, one each:
  - M3's filter removed (`test_a_worker_failure_gives_no_deadline_per_page`, the first row);
  - M3's filter applied to every run outcome (the same test, the `deadline` row);
  - P109's check skipped (`test_a_unit_page_without_a_prefix_is_corrupt`);
  - P110's `>` becomes `>=` (`test_a_future_health_state_is_corrupt`, the equal row);
  - P110's `reset_at` check removed (the same test);
  - `status_doc` writes the display name as `source` (`test_status_sources_carry_the_source_key`);
  - the feed caps by `item_id` alone (`test_every_relevant_item_is_served_or_counted`).

### Task 3: The run as the scrape job sees it (`scraper.py`, `pipeline.py`; P114, P115; R32, R33, R34)

**Files:**
- Rewrite: `scraper.py`
- Modify: `pyproject.toml`, `elections_calendar/pipeline.py`, `README.md`
- Create: `tests/support/broken.py`, `tests/pipeline/test_scraper_entry.py`,
  `tests/pipeline/test_rejected_pages.py`
- Test: `tests/pipeline/test_run.py` (the over-budget test)

**Interfaces:**
- Consumes: Plan 4's `run`, `RunConfig`, `_parse_source`, `_fetch_offline`, `verdict_of`,
  `FEED_BUDGET_BYTES`; `ledger.LedgerReport.ok`.
- Produces:
  - `scraper.py`: the docstring `v2's entry point (spec §4): python scraper.py (--live | --offline DIR) --out DIR …; see elections_calendar.__main__.`,
    `import sys`, `from elections_calendar.__main__ import main`, and
    `if __name__ == "__main__": sys.exit(main())`. Nothing else.
  - `pipeline.REJECTED_PAGES_MAX_BYTES: Final = 50 * 1024 * 1024`.
  - `pipeline.rejected_pages(raw: RawPages, coverage: Sequence[PageCoverage], *, ledger_ok: bool, parse_failed: bool) -> list[tuple[int, str]]`:
    the index of each page to keep and why (`"parse_failed"`, `"ledger"` or `"page_outcome"`).
  - `verdict.json` gains `over_budget: bool`.
  - `tests/support/broken.py`: `BrokenParse(Osce)`, whose `parse` raises
    `RuntimeError("boom-7f3a C:/Users/someone/secret")`, and `BrokenFetch(Osce)`, whose `fetch`
    raises the same.

**Rules:**
- **R32:**
  - in `pyproject.toml`, remove `"scraper.py"` and its comment from ruff's `extend-exclude`, and
    add `"scraper.py"` to mypy's `files`;
  - grep the repository outside `docs/` and `.scratch/` for anything that imports or runs v1's
    scraper, and report what you find.
- **R33, tracebacks (P115):**
  - on a failure, `_fetch_offline` prints `f"{spec.source}: fetch failed"` and `_parse_source`
    prints `f"{spec.source}: parse failed"`;
  - then each prints `traceback.print_exception(exc)` to `sys.stderr`;
  - the recorded details are unchanged.
- **R33, pages (P115):** `rejected_pages` keeps page `i` of `raw.pages` when its body is not empty
  and:
  - the parser failed → `parse_failed` (every page);
  - otherwise the source's ledger is not `ok` → `ledger` (every page);
  - otherwise `coverage[i].outcome` is not `ok` or `valid_empty` → `page_outcome`.

  `coverage[i]` belongs to `raw.pages[i]` (`ParseResult`'s order). A shorter coverage list is
  already a ledger problem, so every page is then kept as `ledger`.
  - **The files:** `rejected/pages/<source>/<i>.body`, the exact bytes, with `i` in decimal and
    no padding.
  - **The index:** `rejected/pages/index.json` (`stored_json`) is a list of rows in
    (`SOURCE_ORDER`, `i`) order:
    `{source, index, key, year, url, final_url, fetch_outcome, page_outcome, http_status, content_type, bytes, sha256, why, kept}`.
    - `page_outcome` is the coverage outcome, or null when the parser failed.
    - `url` and `final_url` are `FetchResult`'s, already redacted.
    - `kept` is false, and no body is written, when the body would bring the run's total over
      `REJECTED_PAGES_MAX_BYTES`.
  - **When:** written after `dispositions.json`, before `manifest.json`. Nothing goes under
    `rejected/pages/` when no page is kept.
- **R34 (P114):**
  - `over_budget = feed is not None and len(feed) > FEED_BUDGET_BYTES`;
  - `verdict.json` records it;
  - the verdict, and `RunResult.verdict`, is `red` when it is true;
  - `status.json`, the feed and `HEALTH.md` are unchanged (its "over budget" line was already
    there).

- [ ] **Step 1: Write the failing tests.**
  - **`test_scraper_entry_point_runs_the_pipeline`:**
    - Run, as a subprocess with the repository root as the working directory,
      `[sys.executable, "scraper.py", "--offline", "tests/fixtures", "--now", "2026-10-19T12:00:00Z", "--out", out, "--repo", empty]`.
    - It exits 0, its stdout fullmatches `published, verdict red, [0-9]+ feed bytes\n` (text
      mode), and `out/manifest.json` exists.
    - `scraper.py` is at most 15 lines and imports neither `requests` nor `bs4`.
  - **`test_worker_traceback_is_logged_not_committed`:** OSCE runs with
    `AdapterSpec("osce", "tests.support.broken:BrokenParse")`, then with `BrokenFetch`.
    - stderr (capsys) holds `osce: parse failed` (or `osce: fetch failed`),
      `Traceback (most recent call last)` and `RuntimeError: boom-7f3a`;
    - `status.json` has the detail `parse: RuntimeError` (or `fetch: RuntimeError`);
    - no file under `out/`, read as bytes recursively, holds `boom-7f3a`.
  - **`test_invalid_page_bodies_are_in_the_artifact`:**
    - OSCE's page is `b"<html><body>Maintenance</body></html>"` (`offline_dir` with that file).
      The page is `layout_not_recognised`, and `rejected/pages/osce/0.body` holds exactly those
      bytes. The index row is `{source: "osce", index: 0, key: "elections", year: null, fetch_outcome: "ok", page_outcome: "layout_not_recognised", http_status: 200, why: "page_outcome", kept: true}`,
      plus the URLs, content type, length and SHA-256. Both files are in the manifest.
    - With `BrokenParse`, the row has `why` `parse_failed` and `page_outcome` null.
    - A clean OSCE run has no `rejected/pages/`.
    - With `REJECTED_PAGES_MAX_BYTES` patched to 10, the row has `kept: false` and there is no
      body file.
    - `rejected_pages` table rows:
      - a ledger that is not `ok` keeps every page that has a body;
      - an `http_error` page with an empty body is not kept;
      - a `challenge_page` body is kept as `page_outcome`.
  - **`test_an_over_budget_feed_is_a_red_run`:**
    - the OSCE run is green, with `over_budget` false;
    - with `pipeline.FEED_BUDGET_BYTES` patched to 100, `verdict.json` has verdict `red`,
      `over_budget` true and outcome `published`;
    - `status.json`'s `reasons` equal those of the green run;
    - `main` prints `published, verdict red, <n> feed bytes`.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.** In `README.md`:
  - "Running v2 locally" says that `python scraper.py …` is the same command;
  - the `out/` table gains `rejected/pages/` (when, what, the 50 MiB cap) and the `verdict.json`
    field `over_budget`.
- [ ] **Step 4: Run** the whole suite. Expected: PASS.
- [ ] **Step 5: Gates** (mypy now checks `scraper.py`, and ruff includes it), **mutation table,
  commit:** `feat: scraper.py runs v2; tracebacks to stderr; invalid pages and over-budget runs (R32-R34)`.

  Mutations, one each:
  - `scraper.py` calls `sys.exit(0)` (`test_scraper_entry_point_runs_the_pipeline`);
  - the traceback print is removed (`test_worker_traceback_is_logged_not_committed`);
  - the exception's message is recorded instead of its type (the same test);
  - parse-failed pages are not kept (`test_invalid_page_bodies_are_in_the_artifact`);
  - `page_outcome` pages are not kept (the same test);
  - the cap is ignored (the same test);
  - `over_budget` does not make the verdict red (`test_an_over_budget_feed_is_a_red_run`).

### Task 4: `--dry-run` and the request budget (`fetch.py`, `runner.py`, `pipeline.py`, `__main__.py`; P116; R30)

**Files:**
- Modify: `elections_calendar/fetch.py`, `elections_calendar/runner.py`,
  `elections_calendar/pipeline.py`, `elections_calendar/feed.py` (`health_md`'s dry-run line),
  `elections_calendar/__main__.py`, `README.md`
- Create: `tests/unit/test_request_budget.py`, `tests/pipeline/test_dry_run.py`
- Test: `tests/unit/test_fetch.py` (the budget in `Fetcher`), the runner's test module (the budget
  reaches the worker)

**Interfaces:**
- Consumes: Task 3's pipeline; `Fetcher._attempt`; `runner._work`; `run_sources`.
- Produces:
  - `fetch.RequestBudget(directory: Path, limit: int)`:
    - `take() -> bool` and `used() -> int`, with plain attributes `directory` and `limit`, so it
      pickles;
    - `limit < 0` raises `ValueError`;
    - the constructor creates `directory` (`exist_ok`).
  - `Fetcher(..., budget: RequestBudget | None = None)`.
  - `runner.run_sources(..., budget: RequestBudget | None = None)`. `_work` gains a final
    `budget` argument.
  - `pipeline.DRY_RUN_REQUESTS: Final = 40` and `pipeline.DRY_RUN_SCRAPE_DEADLINE_S: Final = 480`.
  - `RunConfig.dry_run: bool = False`.
  - `verdict.json` gains `dry_run: bool` and `requests: int | None`.
  - The CLI gains `--dry-run`.

**Rules (P116):**
- **`take()`:** try `os.open(directory / f"{n}.token", os.O_CREAT | os.O_EXCL | os.O_WRONLY)` for
  `n = 0 … limit - 1` in order. The first that succeeds is the token: close its descriptor and
  return True. If every token exists, return False. Any `OSError` other than `FileExistsError`
  propagates. `used()` counts the files `n.token` for `n < limit`.
- **`Fetcher`:** in `_attempt`, take a token just before each `_send` (each attempt and each
  redirect hop). If `take()` is False, return
  `_Attempt("fetch_failed", "redirect" if hop else "request", redact_url(current), error="request budget reached")`,
  not retryable. The refused request is never sent, and `get` stops there.
- **`run_sources`:** passes the budget to every worker, which builds
  `Fetcher(verify=bundle, budget=budget)`. Without a budget, behaviour is unchanged.
- **The pipeline:**
  - `dry_run` with `offline` set raises `UsageError("--dry-run needs --live")`.
  - On a dry run, `_fetch_live` builds `RequestBudget(workdir / "budget", DRY_RUN_REQUESTS)`,
    passes it and `scrape_deadline_s=DRY_RUN_SCRAPE_DEADLINE_S` to `run_sources`, and reads
    `budget.used()` before the work directory is removed.
  - `verdict.json` gets `dry_run`, and `requests` (an int on a dry run, else null).
  - `HEALTH.md` gets the line `**Dry run:** {requests} of 40 requests. Nothing here is published.`
    straight after its title.
  - Nothing else changes: the artifact is complete and can be compared, and Task 6's checks
    refuse it.
- **No new reason code.** A page refused by the budget is `fetch_failed` "request budget reached",
  and HEALTH.md shows it as such.

- [ ] **Step 1: Write the failing tests.**
  - **`test_request_budget_is_shared`** (in `tests/unit/test_request_budget.py`):
    - 4 spawned processes (`multiprocessing.get_context("spawn")`) each call `take()` 25 times on
      one directory with limit 40. In total exactly 40 calls return True, `used() == 40`, and
      there are exactly 40 token files. One more `take()` is False.
    - Limit 0 is False at once. A negative limit raises `ValueError`. A pickled copy shares the
      count.
  - **`test_a_refused_request_is_not_sent`** (with `test_fetch.py`'s local HTTPS server):
    - With a budget of 2, a URL that redirects once to a 200 is `ok`, uses 2 tokens, and the
      server sees 2 requests. The next `get` is `fetch_failed` with the error
      `request budget reached` and `attempts == 1`, and the server still saw 2.
    - With a budget of 1, a 503-then-200 URL sends its first attempt, and the retry is refused:
      `fetch_failed` `request budget reached`, and the server saw 1.
  - **`test_workers_get_the_budget`:** call `runner._work(...)` in this process (not spawned),
    with `runner.Fetcher` replaced by a recorder. It is built with `budget=` the budget that was
    passed.
  - **`test_dry_run_writes_nothing`** (in `tests/pipeline/test_dry_run.py`):
    - Call `main(["--live", "--dry-run", "--now", "2026-10-19T12:00:00Z", "--out", out, "--repo", repo])`, with
      `pipeline.run_sources` replaced by a fake. The fake asserts `budget.limit == 40` and
      `scrape_deadline_s == 480`, takes 16 tokens, and returns the fixture pages of
      `tests/fixtures/pages.json` as a `ScrapeRun` (through the offline getter).
    - It exits 0. `verdict.json` has `dry_run` true and `requests` 16, and `HEALTH.md` has the
      line.
    - `repo`'s tree (paths and bytes) is unchanged, and nothing new appears under `tmp_path`
      except `out`.
    - `main(["--offline", "tests/fixtures", "--dry-run", "--out", other])` exits 2, with stderr
      `--dry-run needs --live`.
    - An offline run has `dry_run` false and `requests` null.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement.** In `README.md`:
  - "Running v2 locally" documents `--dry-run`;
  - the `out/` table lists `verdict.json`'s `dry_run` and `requests`;
  - "How a scrape is bounded" gains one paragraph on the budget.
- [ ] **Step 4: Run** the whole suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat: --dry-run with a shared request budget (R30)`.

  Mutations, one each:
  - `take()` without `O_EXCL` (`test_request_budget_is_shared`);
  - no token for redirect hops (`test_a_refused_request_is_not_sent`);
  - a refused request is retryable (the same test, the 503 row);
  - the worker builds its `Fetcher` without the budget (`test_workers_get_the_budget`);
  - the dry run keeps the 720 s deadline (`test_dry_run_writes_nothing`);
  - `verdict.json`'s `dry_run` is always false (the same test);
  - `--dry-run` is accepted with `--offline` (the same test).

### Task 5: The CI's verdict, switches and summaries (the light `ci` modules; P106, P117, P121; NM-T05)

**Files:**
- Create:
  - the package: `elections_calendar/ci/__init__.py` (a docstring only), `ci/context.py`,
    `ci/manifest.py`, `ci/summary.py`, `ci/switches.py`, `ci/verdict.py`, `ci/__main__.py`;
  - the tests: `tests/ci/__init__.py`, `tests/ci/test_context.py`, `tests/ci/test_manifest.py`,
    `tests/ci/test_summary.py`, `tests/ci/test_switches.py`, `tests/ci/test_verdict.py`,
    `tests/ci/test_cli.py`;
  - `tests/support/ci.py`: a small artifact (`verdict.json`, `HEALTH.md`, a manifest written by
    `publish.write_manifest`).
- Modify: `elections_calendar/text.py` and `elections_calendar/feed.py` (`md_text` moves; `feed`
  re-exports it), `importlinter.ini`

**Interfaces:**
- Consumes: Task 4's `verdict.json` (`dry_run`); `text.md_text` (moved here); `model`.
- Produces:

  ```python
  # ci/context.py
  MAIN_REF: Final = "refs/heads/main"
  EVENTS: Final = ("push", "schedule", "workflow_dispatch")
  JOB_RESULTS: Final = ("success", "failure", "cancelled", "skipped")
  SWITCH_VALUES: Final = ("true", "false")
  PUBLISH_OUTCOMES: Final = ("published", "validation_failed", "superseded", "refused", "git_failed", "not_allowed")
  SERVED_RESULTS: Final = ("ok", "served_mismatch", "not_checked")
  def publishing_allowed(event: str, ref: str, publish_input: str) -> bool

  # ci/manifest.py
  class ManifestError(ValueError): ...
  def safe_path(path: str) -> bool
  def read_manifest(root: Path) -> dict[str, str]   # posix path -> sha256; raises ManifestError

  # ci/summary.py
  SUMMARY_CAP_BYTES: Final = 900_000
  OUTPUT_VALUES: Final[Mapping[str, tuple[str, ...]]]   # paused, alert_test, outcome, served
  def write_outputs(path: Path, values: Mapping[str, str]) -> None
  def append_summary(path: Path, text: str, *, cap: int = SUMMARY_CAP_BYTES) -> None

  # ci/switches.py
  def switches(repo: Path) -> dict[str, str]   # {"paused": "true"|"false", "alert_test": ...}

  # ci/verdict.py
  @dataclass(frozen=True, slots=True)
  class RunState:
      event: str
      ref: str
      publish_input: str
      gates: str
      scrape: str
      publish: str
      paused: str
      alert_test: str
      publish_outcome: str
      served: str
      artifact: Path

  @dataclass(frozen=True, slots=True)
  class FinalVerdict:
      green: bool
      headline: str
      details: tuple[str, ...]

  def state_from(environ: Mapping[str, str], artifact: Path) -> RunState
  def final_verdict(state: RunState) -> FinalVerdict
  def summary_text(final: FinalVerdict, state: RunState) -> str

  # ci/__main__.py
  def main(argv: Sequence[str] | None = None) -> int   # switches | scrape-summary | verdict
  ```

**Rules:**
- **Light modules (P117):** `context`, `manifest`, `summary`, `switches`, `verdict` and
  `__main__` import only the standard library, `elections_calendar.model`,
  `elections_calendar.text` and each other at module level. Task 6's commands import their
  modules inside their functions.
- **`publishing_allowed`:** True exactly when `ref == MAIN_REF` and either
  `event == "schedule"`, or `event == "workflow_dispatch"` and `publish_input == "true"`.
- **`safe_path`:** true when the path:
  - is non-empty and at most 255 characters;
  - splits on `/` into parts that are each non-empty and neither `.` nor `..`;
  - holds no `\`, `:`, NUL, C0 control or DEL character;
  - does not start with `/`.
- **`read_manifest` (P119):** these checks run in order, over paths in sorted order, and the first
  problem raises `ManifestError` with its message:
  1. the file exists, else `manifest.json is missing`;
  2. it is UTF-8 JSON of exactly `{"schema_version": 1, "files": {str: 64 lowercase hex}}`, else
     `manifest.json is malformed`;
  3. every key is a safe path, else `manifest lists an unsafe path: <shown>`;
  4. no file or directory under `root` is a symbolic link, else `a link is not a file: <shown>`;
  5. every regular file under `root` other than `manifest.json` is listed, else
     `a file is not in the manifest: <shown>`;
  6. every listed file exists, else `a file in the manifest is missing: <shown>`;
  7. every digest matches, else `a file does not match the manifest: <shown>`.

  `<shown>` is the path's `repr`, cut to 120 characters.
- **`write_outputs`:** every name must be a key of `OUTPUT_VALUES` and its value one of that key's
  values, else `ValueError` before anything is written. It appends `name=value\n` lines as UTF-8
  with LF. `OUTPUT_VALUES` is `{"paused": SWITCH_VALUES, "alert_test": SWITCH_VALUES, "outcome": PUBLISH_OUTCOMES, "served": SERVED_RESULTS}`.
- **`append_summary`:**
  - It appends UTF-8 text so that the file never grows past `cap` bytes.
  - When the text does not fit, it is cut after its last `\n` that leaves room for the note
    `\n_The summary was cut at {cap} bytes. The full text is in the run's artifact._\n`, and the
    note is appended. A cut never splits a character.
  - A missing file is created.
- **`switches`:** a switch is present when `os.path.lexists(repo / name)`: a file, a directory or
  a dangling link all count. The names are `PAUSE_PUBLISHING` and `ALERT_TEST`.
- **`state_from`:** it reads `GITHUB_EVENT_NAME`, `GITHUB_REF`, `INPUT_PUBLISH`, `GATES_RESULT`,
  `SCRAPE_RESULT`, `PUBLISH_RESULT`, `PAUSED`, `ALERT_TEST`, `PUBLISH_OUTCOME` and `SERVED`. A
  missing variable is `""`.
- **`final_verdict` (P121):** the first row that applies decides. "Data verdict" is
  `verdict.json`'s `verdict`, and "data outcome" is its `outcome`.

  | Step | Condition | Result |
  |---|---|---|
  | 0 | the event is not in `EVENTS`; a job result is not in `JOB_RESULTS`; `PAUSED` or `ALERT_TEST` is not in `SWITCH_VALUES` or `""`; `PUBLISH_OUTCOME` is not in `PUBLISH_OUTCOMES` or `""`; `SERVED` is not in `SERVED_RESULTS` or `""` (checked in this order) | red `unknown state: <NAME>`, with the value as a detail (cut to 100) |
  | 1 | event `push` | gates `success` with scrape and publish `skipped` → green `gates only`; gates not `success` → red `gates failed`; otherwise red `unexpected jobs on a push` |
  | 2 | gates not `success` | red `gates failed` |
  | 3 | scrape not `success` | red `scrape failed` (detail: the result) |
  | 4 | `PAUSED` or `ALERT_TEST` is `""` | red `unknown state: PAUSED` (or `ALERT_TEST`) |
  | 5 | `PAUSED` is `true` | publish `skipped` → green `paused`; otherwise red `publish ran while paused` |
  | 6 | `read_manifest(artifact)` raises, or there is no `verdict.json` | red `artifact incomplete` (detail: the problem) |
  | 7 | `verdict.json` is not an object whose `verdict` is green or red, whose `outcome` is published or validation_failed, and whose `dry_run` is the boolean false | `dry_run` true → red `dry-run artifact`; otherwise red `verdict.json is malformed` |
  | 8 | publishing allowed (`publishing_allowed`), publish not `success` | red `publish failed` (detail: the result) |
  | 9 | allowed; `PUBLISH_OUTCOME` is `published` or `validation_failed` and differs from the data outcome | red `publish disagrees with verdict.json` |
  | 10 | allowed, `published` | served `ok`: data green → green `published`, data red → red `published with open warnings or errors`; served `served_mismatch` → red `served_mismatch`; otherwise red `unknown state: SERVED` |
  | 11 | allowed, any other outcome | `validation_failed` → red `validation failed`; `superseded` → red `superseded`, with the detail `main moved during the run: start a new workflow_dispatch on main with publish: true (a re-run keeps the old commit)` (P5A-06); `refused` → red `artifact refused`; `git_failed` → red `git failed`; `not_allowed` → red `publish refused its context`; `""` → red `unknown state: PUBLISH_OUTCOME` |
  | 12 | not allowed, publish not `skipped` | red `publish ran outside its context` |
  | 13 | not allowed | data outcome `validation_failed` → red `validation failed (not published)`; data red → red `not published: open warnings or errors`; data green → green `not published: healthy` |
  | 14 | `ALERT_TEST` is `true`, after any result of steps 5–13 | red `alert test`, with the replaced headline as its first detail |
- **`summary_text`:**
  - first line `## Verdict: {green|red}, {headline}`;
  - then each detail as a list item, through `md_text`;
  - then a table of the three job results, the publish outcome and the served result, each
    through `md_text`.
- **Commands:**
  - **`switches --repo DIR`:**
    - it needs `GITHUB_OUTPUT`; without it, it exits 2 with `GITHUB_OUTPUT is not set`;
    - it writes `paused` and `alert_test`;
    - when `GITHUB_STEP_SUMMARY` is set, it appends
      `## Paused\n\n`PAUSE_PUBLISHING` is on this commit: nothing is scraped or published.\n`
      when paused, and
      `## Alert test\n\n`ALERT_TEST` is on this commit: this run fails on purpose after it publishes.\n`
      for the alert test;
    - it exits 0.
  - **`scrape-summary --out DIR`:**
    - it appends `DIR/HEALTH.md` through `append_summary`;
    - without the file it appends
      `## No HEALTH.md\n\nThe scrape stopped before it wrote one. See the job log.\n`;
    - it exits 0, and exits 2 when `GITHUB_STEP_SUMMARY` is not set.
  - **`verdict --artifact DIR`:** it appends `summary_text`, prints its first line without `## `,
    and exits 0 for green and 1 for red.
- **`importlinter.ini` (P106):**
  - the top layer becomes `__main__ | ci`;
  - a new contract:

    ```ini
    [importlinter:contract:ci]
    name = The CI reads artifacts, never builds them (Plan 5a P106)
    type = forbidden
    source_modules =
        elections_calendar.ci
    forbidden_modules =
        elections_calendar.pipeline
        elections_calendar.__main__
    ```

- [ ] **Step 1: Write the failing tests.**
  - **`test_publishing_allowed`** (S4-T18, V2-T07), as `(event, ref, input) → expected`:
    - `(schedule, refs/heads/main, "")` T;
    - `(schedule, refs/heads/feat/x, "")` F;
    - `(workflow_dispatch, refs/heads/main, "true")` T;
    - the same with `"false"`, `"True"`, `""` and `" true"` F;
    - `(workflow_dispatch, refs/heads/feat/x, "true")` F;
    - `(push, refs/heads/main, "true")` F;
    - `(schedule, refs/heads/main2, "")` F;
    - `(schedule, refs/tags/main, "")` F.
  - **`test_manifest_checks`:** one row per message above. Also: an empty directory
    (`manifest.json is missing`); unsafe keys `../x`, `/x`, `a\\b`, `C:x`, `a/./b`, `a//b`, `""`
    and a key holding `\n`; a `.tmp` file left over (`a file is not in the manifest`). The link
    row is skipped only where links cannot be made (Windows without the privilege). On CI it runs.
  - **`test_outputs_hold_fixed_words_only`** (S4-T19, RT-02):
    - `write_outputs` raises for `{"outcome": "published\nserved=ok"}`, for `{"evil": "true"}` and
      for `{"served": "OK"}`, and the file stays unchanged;
    - `{"outcome": "published"}` appends exactly `outcome=published\n`;
    - an artifact from `tests/support/ci.py` whose `HEALTH.md` and `verdict.json` reason texts hold
      `"x\nserved=ok\noutcome=published\n::set-output name=served::ok ${{ secrets.GITHUB_TOKEN }}"`:
      after the `switches` and `verdict` commands, every line of `GITHUB_OUTPUT` fullmatches
      `(paused|alert_test)=(true|false)` (the verdict writes no output);
    - the summary holds that text escaped, with no line that is `served=ok`.
  - **`test_summary_is_capped`:**
    - a `HEALTH.md` of 2 MB (`"Bangsamoro — São Tomé ✓ | <b>\n"` repeated) leaves a summary of at
      most 900,000 bytes that decodes as UTF-8 and ends with the note;
    - an existing summary of 899,000 bytes plus 10 KB of text stays at most 900,000 bytes;
    - text that fits is appended unchanged, with no note.
  - **`test_md_text_moved`:** `feed.md_text is text.md_text`, and Plan 4's `md_text` tests pass
    unchanged.
  - **`test_switches`:** none present; a `PAUSE_PUBLISHING` file; a directory of that name; a
    dangling link (skipped where links cannot be made); `ALERT_TEST`; both.
  - **`test_outcome_matrix`** (NM-T05), as `(event, ref, input, gates, scrape, publish, paused, alert_test, outcome, served, artifact) → (green, headline)`:
    1. push to `refs/heads/feat/x`: success, skipped, skipped, no artifact → green `gates only`;
    2. the same on `main` → green `gates only`;
    3. push, gates `failure` → red `gates failed`;
    4. schedule, gates `failure`, scrape and publish skipped → red `gates failed`;
    5. schedule, paused `true`, publish skipped → green `paused`;
    6. schedule, scrape `failure` → red `scrape failed`;
    7. schedule, scrape `cancelled` (its timeout) → red `scrape failed`;
    8. schedule, no `verdict.json` → red `artifact incomplete`;
    9. schedule, a file changed after the manifest → red `artifact incomplete`;
    10. schedule, published, served `ok`, data green → green `published`;
    11. the same with data red → red `published with open warnings or errors`;
    12. schedule, `validation_failed` (data outcome `validation_failed`) → red `validation failed`;
    13. `superseded` → red `superseded`, whose details start with the new-dispatch line;
    14. published, served `served_mismatch` → red `served_mismatch`;
    15. `git_failed` → red `git failed`;
    16. `refused` → red `artifact refused`;
    17. publish `cancelled` while allowed → red `publish failed`;
    18. alert `true`, published, served ok, data green → red `alert test`;
    19. alert `true` and paused `true` → red `alert test`;
    20. dispatch on a branch, input `true`, publish skipped, data green → green `not published: healthy`;
    21. the same with data red → red `not published: open warnings or errors`;
    22. dispatch on `main`, input `false`, publish skipped, data green → green `not published: healthy`;
    23. dispatch on `main`, input `true`, published, served ok, green → green `published`;
    24. dispatch on `main`, input `yes`, publish skipped → green `not published: healthy`;
    25. not allowed, but publish `success` → red `publish ran outside its context`;
    26. `verdict.json` with `dry_run` true → red `dry-run artifact`;
    27. not allowed, data outcome `validation_failed` → red `validation failed (not published)`;
    28. published while `verdict.json` says `validation_failed` → red `publish disagrees with verdict.json`.
  - **`test_unknown_states_are_red`:** each of the following is red, with the headline shown:
    - `GATES_RESULT` `""` → `unknown state: GATES_RESULT`;
    - `PUBLISH_RESULT` `banana` → `unknown state: PUBLISH_RESULT`;
    - `GITHUB_EVENT_NAME` `pull_request` → `unknown state: GITHUB_EVENT_NAME`;
    - `PAUSED` `""` with scrape success → `unknown state: PAUSED`;
    - `PUBLISH_OUTCOME` `banana` → `unknown state: PUBLISH_OUTCOME`;
    - `SERVED` `""` after `published` → `unknown state: SERVED`;
    - `verdict.json` `{"verdict": "GREEN", …}`, not JSON, a JSON list, without `outcome`, or with
      `dry_run` `"false"` (a string) → `verdict.json is malformed`.
  - **`test_light_commands_need_only_the_standard_library`:** a subprocess
    `[sys.executable, "-I", "-S", "-c", code]`, where `code` puts the repository root first on
    `sys.path`:
    - it imports `elections_calendar.ci.__main__` and the five light modules;
    - it asserts that none of `yaml`, `jsonschema`, `requests`, `bs4`, `lxml` is in `sys.modules`;
    - it runs `main(["verdict", "--artifact", <a tests/support/ci.py artifact>])` with the
      environment of matrix row 10, which exits 0.
  - **`test_cli_commands`:**
    - `switches` without `GITHUB_OUTPUT` exits 2;
    - `scrape-summary` with no `HEALTH.md` appends the minimal text;
    - `verdict` exits 0 for green and 1 for red, and prints `Verdict: green, published` or the
      red line.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/ci -q`. Expected: FAIL (no
  `elections_calendar.ci`).
- [ ] **Step 3: Implement** the modules, move `md_text`, and update `importlinter.ini`.
- [ ] **Step 4: Run** the whole suite, then
  `.venv/Scripts/lint-imports.exe --config importlinter.ini`. Expected: PASS and
  `Contracts: 3 kept, 0 broken`.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(ci): the verdict, switches and summaries of the workflow (NM-T05)`.

  Mutations, one each:
  - `publishing_allowed` compares the input case-insensitively (`test_publishing_allowed`);
  - a dispatch may publish from any ref (the same test);
  - `safe_path` accepts `..` (`test_manifest_checks`);
  - `read_manifest` skips the digest check (the same test);
  - `write_outputs` checks names only (`test_outputs_hold_fixed_words_only`);
  - `append_summary` leaves no room for the note (`test_summary_is_capped`);
  - step 14 is skipped (`test_outcome_matrix`, row 18);
  - step 5 is green whatever publish did (the matrix, a paused row with publish `success`; add it
    if no row has it);
  - step 6 is skipped (the matrix, row 9);
  - `served_mismatch` is green (the matrix, row 14);
  - step 13's data-red row is green (the matrix, row 21);
  - an unknown job result counts as `success` (`test_unknown_states_are_red`);
  - `verdict.py` imports `elections_calendar.feed` at module level
    (`test_light_commands_need_only_the_standard_library`).

### Task 6: The publish job and the first baselines (`ci/artifact.py`, `ci/git.py`, `ci/publishing.py`; P119, P120, P124; R28, R29, S4-T05, S4-T08, NM-T04, NM-T08, RT-02, RT-03, V2-T07)

**Files:**
- Create:
  - the modules: `elections_calendar/ci/artifact.py`, `ci/git.py`, `ci/publishing.py`;
  - the helpers: `tests/support/artifact.py`, `tests/support/git_repos.py`;
  - the tests: `tests/ci/test_artifact.py`, `tests/ci/test_publishing.py`, `tests/ci/test_adopt.py`,
    and `tests/unit/test_served_fetcher.py` (beside `tests/unit/conftest.py`'s `pki` and `server`).
- Modify:
  - `elections_calendar/ci/__main__.py` (`publish` and `adopt`);
  - `tests/support/repo.py` (`commit` uses the real copy);
  - `elections_calendar/validate.py` (`feed_content_problems`, which `validate_feed` now calls);
  - `elections_calendar/feed.py` (`_serving_fields` becomes the public `serving_fields`);
  - `elections_calendar/snapshots.py` (`load_baseline` takes `source`, R2-01) and
    `elections_calendar/pipeline.py` (`_read_baseline` passes it and drops its own check);
  - `README.md` (a `ci adopt` section: which artifacts it takes, P5A-08).

**Interfaces:**
- Consumes:
  - Task 5's `read_manifest`, `ManifestError`, `publishing_allowed`, the vocabularies,
    `write_outputs`, `append_summary`, `final_verdict`;
  - `validate.validate_status`, `publish.write_atomic`, `publish.write_manifest` (tests), `model.SOURCE_ORDER`;
  - `snapshots.load_baseline` (as changed here) and Task 2's `health.load_health_state(path, *, now)`;
  - `fetch.Fetcher`, `fetch.Deadline` (its `clock` is injectable), `fetch.trust_bundle`.
- Produces:

  ```python
  # validate.py: validate_feed(data, served=..., wall_clock=...) == feed_content_problems(...) + the served check
  def feed_content_problems(data: bytes, *, wall_clock: datetime) -> tuple[str, ...]

  # feed.py: renamed from _serving_fields, unchanged
  def serving_fields(serving: bytes | None) -> dict[str, str | None]

  # snapshots.py: `source` given -> a baseline of another source raises
  # RecordError("baseline.json is corrupt: it is of 'ipu', not 'osce'"), pipeline._read_baseline's text
  def load_baseline(path: Path, *, source: str | None = None) -> Baseline | None

  # ci/artifact.py
  REPOSITORY_NAMES: Final = ("elections.json", "status.json", "HEALTH.md")
  SOURCE_FILES: Final = ("baseline.json", "candidate.json", "health_state.json")
  ARTIFACT_ONLY: Final = ("verdict.json", "attention_full.json", "dispositions.json")
  REPOSITORY_FILE_MAX_BYTES: Final = 10 * 1024 * 1024
  class ArtifactError(ValueError): ...

  @dataclass(frozen=True, slots=True)
  class Artifact:
      root: Path
      outcome: Literal["published", "validation_failed"]
      repository_files: tuple[str, ...]   # sorted posix paths, the files to commit
      status: Mapping[str, Any]
      verdict: Mapping[str, Any]
      manifest_sha256: str

  def load_artifact(root: Path, *, code_sha: str | None, wall_clock: datetime, sources: Sequence[str] = SOURCE_ORDER) -> Artifact
  def served_link_problems(artifact: Artifact, committed_baseline: Callable[[str], bytes | None]) -> list[str]
  def copy_repository_files(artifact: Artifact, repo: Path, *, only: Callable[[str], bool] = lambda path: True) -> tuple[str, ...]

  # ci/git.py
  class GitError(RuntimeError): ...
  PushResult = Literal["pushed", "rejected", "failed"]

  @dataclass(frozen=True, slots=True)
  class Git:
      repo: Path
      timeout_s: float = 60.0
      deadline: Deadline | None = None            # the publish stage's (P127)
      def run(self, *args: str) -> str            # stdout, UTF-8, stripped
      def blob(self, commit: str, path: str) -> bytes | None
      def push(self, refspec: str) -> PushResult

  # ci/publishing.py
  RAW_URL: Final = "https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/elections.json"
  SERVED_POLL_S: Final = 60
  SERVED_LIMIT_S: Final = 600
  SERVED_FETCH_S: Final = 60
  PUBLISH_STAGE_S: Final = 240
  BOT_NAME: Final = "github-actions[bot]"
  BOT_EMAIL: Final = "41898282+github-actions[bot]@users.noreply.github.com"

  @dataclass(frozen=True, slots=True)
  class PublishResult:
      outcome: str     # one of PUBLISH_OUTCOMES
      served: str      # one of SERVED_RESULTS
      commit: str | None
      detail: str

  # fetch(timeout_s) returns the body, or None. It aims to end within timeout_s, but can overrun
  # it (the Fetcher does not bound name resolution, connecting or dripped headers), so
  # served_check does not count a fetch that ends after its deadline (P127)
  def served_check(expected_sha256: str, *, fetch: Callable[[float], bytes | None], sleep: Callable[[float], None], clock: Callable[[], float], poll_s: float = SERVED_POLL_S, limit_s: float = SERVED_LIMIT_S, fetch_s: float = SERVED_FETCH_S) -> str
  def commit_message(artifact: Artifact) -> str
  def publish(artifact_dir: Path, git: Git, *, code_sha: str, allowed: bool, wall_clock: datetime, fetch: Callable[[float], bytes | None], sleep: Callable[[float], None], clock: Callable[[], float], sources: Sequence[str] = SOURCE_ORDER) -> PublishResult
  def served_fetcher(environ: Mapping[str, str], *, workdir: Path, url: str = RAW_URL) -> Callable[[float], bytes | None]
  ```

**Rules:**
- **`load_artifact` (P119):** these checks run in order, and the first problem raises
  `ArtifactError`:
  1. `read_manifest`: a `ManifestError` becomes an `ArtifactError` with the same message.
  2. Every path is a repository path, an `ARTIFACT_ONLY` name, or under `rejected/`, else
     `an unexpected file: <shown>`. A repository path is a `REPOSITORY_NAMES` name, or
     `data/sources/<s>/<f>` with `s` in `sources` and `f` in `SOURCE_FILES`.
  3. `status.json`, `HEALTH.md` and `verdict.json` are present, else `the artifact has no <name>`.
  4. `validate_status(status bytes)` gives no problem, else `status.json is invalid: <first>`.
  5. Its `outcome` is `published` or `validation_failed`, else `status.json's outcome is <repr>`.
  6. `verdict.json` is an object whose `verdict` is green or red, else `verdict.json is malformed`.
     Its `outcome` equals the status outcome, else `verdict.json and status.json disagree`. Its
     `dry_run` is the boolean false, else `a dry-run artifact is never published`.
  7. When `code_sha` is given, `status["code_sha"] == code_sha`, else
     `status.json is from <code_sha of status>, not <code_sha>`.
  8. `[s["source"] for s in status["sources"]] == list(sources)`, else
     `status.json lists other sources`.
  9. Every repository file is at most `REPOSITORY_FILE_MAX_BYTES`, else
     `<path> is over 10485760 bytes`, and `HEALTH.md` is UTF-8, else `HEALTH.md is not UTF-8`.
  10. A published artifact:
      - has an `elections.json`, and `status.json`'s four `serving_*` fields equal
        `serving_fields(<its bytes>)`, else `elections.json does not match status.json`;
      - its feed has no `feed_content_problems(feed, wall_clock=wall_clock)`, else
        `elections.json is invalid: <first>` (P5A-01);
      - has, for every source, `candidate.json` and `health_state.json`, else
        `data/sources/<s> is incomplete`.

      A `validation_failed` artifact has no `elections.json` and nothing under `data/sources/`,
      else `a failed validation carries a feed`.
  11. **Saved state (P5A-01), for a published artifact only** (check 10 has made sure a failed
      validation carries no source files, so it goes straight on; R2-03), for each source in
      `sources` order:
      - a `baseline.json` loads with `load_baseline(path, source=s)`, else
        `data/sources/<s>/baseline.json: <the RecordError's message>`;
      - `load_health_state(<path>, now=<status attempt_at>)` has no `problem`, else
        `data/sources/<s>/health_state.json is corrupt: <problem>`;
      - `candidate.json` is a UTF-8 JSON object whose `source` is `s` and whose `snapshot_id` is
        64 lowercase hex, else `data/sources/<s>/candidate.json is malformed`.

  `manifest_sha256` is the SHA-256 of `manifest.json`'s bytes.
- **`served_link_problems`** (P5A-01): for a failed validation, `[]`. For a published artifact,
  it looks at each feed `source_health` entry in feed order:
  - `snapshot.served_snapshot_id` null → no problem;
  - else the baseline the repository will hold after the commit is the artifact's
    `data/sources/<s>/baseline.json` if present, else `committed_baseline(s)`;
  - none → `<s>: the feed serves snapshot <id>, but no baseline is committed`;
  - **its bytes are loaded with `load_baseline(<file>, source=s)` wherever they come from**
    (R2-01; the committed bytes are written to a `tempfile.TemporaryDirectory` first, because
    the loader reads a path). A `RecordError` →
    `<s>: the feed serves snapshot <id>, but its baseline is corrupt: <the RecordError's message>`;
  - the loaded `snapshot.snapshot_id` differs →
    `<s>: the feed serves snapshot <id>, the committed baseline is <other>`.

  A baseline whose source the feed does not serve (null) is never loaded here: a corrupt one
  stays on disk and in every day's reasons (P94), and the healthy sources still publish.

  **Pre-flight:** on the fixture artifact all nine served ids equal the artifact's baselines
  (`.scratch/plan5a/served_rel.py`). Check every published artifact of Plan 4's multi-run
  pipeline tests (quarantine, fallback, unavailable, other registry) against the rule. If one
  fails, stop and report it: the rule would then be wrong, not the run.
- **`copy_repository_files`:** it writes each repository path that `only` accepts, with the
  artifact's exact bytes, into `repo` through `write_atomic` (which creates the folders). It
  returns those paths, sorted, and never deletes anything.
- **`Git`:**
  - every call runs
    `["git", "-C", str(repo), "-c", "core.autocrlf=false", "-c", "core.safecrlf=false", "-c", "commit.gpgsign=false", *args]`
    with `GIT_TERMINAL_PROMPT=0` and `LC_ALL=C` added to the environment, captures the output,
    and is bounded by `min(timeout_s, deadline.remaining())` when there is a deadline (P127);
  - when the deadline has no time left, the call is not started and raises
    `GitError(f"git {args[0]} failed: the publish stage's time limit was reached")`;
  - a non-zero exit or a timeout raises `GitError(f"git {args[0]} failed: <the last stderr line, cut to 300>")`;
  - `blob` runs `cat-file -e <commit>:<path>` and then `cat-file blob <commit>:<path>`, returning
    the raw bytes, or None when the path is absent;
  - `push(refspec)` runs `push --porcelain origin <refspec>`: exit 0 is `pushed`; a non-zero exit
    with a porcelain line that starts with `!` and holds `[rejected]` is `rejected` (`[remote rejected]`
    is not); anything else is `failed`.
- **`served_check`** (P120, NM-T04, P127): it compares byte digests only, against one absolute
  deadline that is checked before every fetch.

  ```
  deadline = clock() + limit_s
  loop:
      left = deadline - clock()
      if left <= 0: return "served_mismatch"
      body = fetch(min(fetch_s, left))
      if clock() > deadline: return "served_mismatch"    # an overrun fetch is not counted (R2-06)
      if body is not None and sha256(body) == expected: return "ok"
      left = deadline - clock()
      if left <= 0: return "served_mismatch"
      sleep(min(poll_s, left))
  ```

- **`commit_message`:** `chore: update elections.json [<attempt_id>]` for a published artifact,
  and `chore: record a failed validation [<attempt_id>]` for a failed validation.
- **`publish`** (P120): the steps run in order, and the first step that decides an outcome ends
  the run:
  1. If not `allowed`: `not_allowed`, with the detail `publishing is not allowed in this context`.
     Nothing is read.
  2. Run `load_artifact(artifact_dir, code_sha=code_sha, wall_clock=wall_clock, sources=sources)`.
     An `ArtifactError` gives `refused` with its message. `sources` is a test seam for OSCE-only
     artifacts: the command never passes it, so a real run must carry all nine sources.
  3. If `git status --porcelain` is not empty: `refused`, `the checkout has changes`. If
     `git rev-parse HEAD` is not `code_sha`: `refused`, `the checkout is not at the run's commit`.
     Then the checks against the repository at `code_sha` (P5A-01):
     - a published artifact: the first of
       `served_link_problems(artifact, lambda s: git.blob(code_sha, f"data/sources/{s}/baseline.json"))`
       gives `refused` with it;
     - a failed validation: `status.json`'s four `serving_*` fields must equal
       `serving_fields(git.blob(code_sha, "elections.json"))`, else `refused`,
       `status.json does not describe the feed the repository keeps`.
  4. Run `git fetch origin main`, then `git rev-parse FETCH_HEAD`. If it is not `code_sha`:
     `superseded`, `main moved during the run`.
  5. Copy the files, then `git add -- <exactly the copied paths>`, then
     `git -c user.name=<BOT_NAME> -c user.email=<BOT_EMAIL> commit -m <commit_message>`.
  6. Push with `push("HEAD:refs/heads/main")`. `rejected` gives `superseded`,
     `main moved before the push`; `failed` gives `git_failed`.
  7. A published artifact runs `served_check(status["serving_feed_sha256"], ...)`. A failed
     validation gets `not_checked`.

  Any `GitError` gives `git_failed`, with its message as the detail. The detail of `published` or
  `validation_failed` is the new commit's SHA.
- **`served_fetcher`** (R2-07): it writes the CA file once,
  `trust_bundle(workdir / "ca-bundle.pem", environ)`, and returns a function `fetch(timeout_s)`
  that fetches `url` through `Fetcher(verify=str(bundle.path))` with
  `deadline=Deadline.after(timeout_s)`, and closes the Fetcher. It returns the body when the
  outcome is `ok`, else None. A `TrustBundleError` propagates (a crash: `publish failed`).
- **The commands:**
  - **`publish --artifact DIR --repo DIR`:**
    - it builds `Git(repo, deadline=Deadline.after(PUBLISH_STAGE_S))` first. The 240 s run from
      before `load_artifact`, but only git calls check them (P127): a slow `load_artifact` or
      copy is caught at the next git call, before anything is written;
    - it passes `served_fetcher(os.environ, workdir=<a tempfile.TemporaryDirectory>)`;
    - it reads `GITHUB_EVENT_NAME`, `GITHUB_REF`, `INPUT_PUBLISH`, `GITHUB_SHA`, `GITHUB_OUTPUT`
      and `GITHUB_STEP_SUMMARY`;
    - a `GITHUB_SHA` that is not 40 lowercase hex gives `refused`,
      `GITHUB_SHA is not a commit SHA`;
    - it writes the outputs `outcome` and `served`;
    - it appends `## Publish: <outcome>, served <served>`, the detail (through `md_text`) and the
      commit;
    - it exits 0 for every outcome. A crash propagates, which the verdict reads as
      `publish failed`.
  - **`adopt --artifact DIR --manifest-sha256 HEX [--repo DIR]`** (P124): each failure exits 1
    with its message on stderr:
    - `HEX` is not 64 lowercase hex → exit 2;
    - `manifest.json`'s SHA-256 is not `HEX` →
      `the artifact is not the approved one: its manifest is <sha>`;
    - `load_artifact(code_sha=None, wall_clock=<now>)` raises → its message;
    - the outcome is not `published` → `only a published artifact has baselines`;
    - `served_link_problems(artifact, lambda s: None)` is not empty → its first problem;
    - `os.path.lexists(repo / "data" / "sources")` →
      `data/sources already exists: the first baselines are adopted once`.

    Then it copies only the paths under `data/sources/`, prints each one, and prints
    `adopted <n> files from the run of <code_sha> (manifest <HEX>)`. It exits 0 and commits
    nothing.
- **`tests/support/repo.commit(out, repo)`** becomes `copy_repository_files(load_artifact(out, code_sha=None, wall_clock=datetime.now(UTC), sources=<status.json's source keys>), repo)`.
  A Plan 4 test that edits `out/` before `commit` must edit the repository copy after `commit`
  instead. List each one you change.

**Test helpers:**
- **`tests/support/git_repos.py`:**
  - `origin_and_clone(tmp_path: Path, *, files: Mapping[str, bytes] | None = None, gitattributes: bool = True) -> Repos`
    returns `(origin, clone, head)`. `origin` is a bare repository on `main` with one commit:
    the project's `.gitattributes` (unless `gitattributes` is False), `elections.json` holding
    the bytes of `tests/fixtures/feed/2026-10-16-ff30417.json`, and `files`. `clone` is a clone
    of it.
  - `push_competitor(origin: Path, tmp_path: Path) -> str` commits `NOTES.txt` from a second
    clone, pushes it to `main`, and returns its SHA.
- **`tests/support/artifact.py`:**
  - `osce_artifact(dest, *, repo, code_sha, outcome="published", offline=None)` runs the OSCE-only
    pipeline with `environ={"GITHUB_SHA": code_sha, "GITHUB_RUN_ID": "7", "GITHUB_EVENT_NAME": "schedule"}`,
    on OSCE's fixtures, or on the folder `offline` (an empty one makes OSCE unavailable).
    `outcome="validation_failed"` forces a validation failure the way Plan 4's
    `test_validation_failure_writes_no_feed` does.
  - `fixture_artifact(dest, *, code_sha, outcome="published")` copies a nine-source run that is
    built once per session for each outcome (`validation_failed` forced as for `osce_artifact`),
    and rewrites its `code_sha` with `rewrite`.
  - **Which to use:** tests that call `publish` directly use `osce_artifact` with
    `sources=("osce",)`. Tests that go through the command (`main(["publish", …])`,
    `main(["adopt", …])`) use `fixture_artifact`, because the command checks all nine sources.
  - `rewrite(root, path, data)` writes a file and rewrites the manifest with `write_manifest`.
  - `add_file(root, path, data)` adds a file and rewrites the manifest.
  - `rewrite_feed(root, data)` writes `elections.json`, sets `status.json`'s four `serving_*`
    fields to `serving_fields(data)`, and rewrites the manifest. The artifact is then
    self-consistent whatever `data` holds (P5A-01).

- [ ] **Step 1: Write the failing tests.** In every `refused` case, the origin's `main` and the
  clone's `HEAD` are unchanged, and `git status --porcelain` is empty.
  - **`test_publish_refuses_an_incomplete_artifact`** (R28, NM-T08): one row per
    `load_artifact` message, plus a file changed after the manifest (the digest changed), a
    `status.json` from another commit, and a dry-run artifact (with `dry_run` set through
    `rewrite`). Each is `refused`, with its message.
  - **`test_an_artifact_with_an_unexpected_file_is_refused`** (Review Focus 1, RT-02): each of
    `.github/workflows/x.yml`, `known_issues.yml`, `PAUSE_PUBLISHING`,
    `data/sources/evil/baseline.json`, `data/sources/osce/notes.txt` and `extension/background.js`,
    added with `add_file`, is `refused` `an unexpected file: …`.
  - **`test_a_self_consistent_invalid_artifact_is_refused`** (Review Focus 1, P5A-01): each row
    keeps the manifest and the status digests consistent (`rewrite_feed`, `rewrite`) and is
    `refused` with the message shown:
    - the feed `b"{"` → `elections.json is invalid: json: not UTF-8 JSON`;
    - the feed without `months` → `elections.json is invalid: schema: …`;
    - the feed with `published_at` an hour ahead of `wall_clock` → `elections.json is invalid: timestamp: …`;
    - OSCE's `baseline.json` with `scope.pages[0].units_seen` changed →
      `data/sources/osce/baseline.json: baseline.json is corrupt: ledger: …`;
    - OSCE's `health_state.json` with a `last_absent_at` after the run →
      `data/sources/osce/health_state.json is corrupt: timestamp of … is after the run`;
    - OSCE's `candidate.json` as `{"source": "ipu"}` → `data/sources/osce/candidate.json is malformed`;
    - OSCE's `baseline.json` replaced by IPU's from `fixture_artifact` (valid, of another source)
      → `data/sources/osce/baseline.json: baseline.json is corrupt: it is of 'ipu', not 'osce'`;
    - a `HEALTH.md` of 10 MiB + 1 byte → `HEALTH.md is over 10485760 bytes`;
    - the feed's OSCE `served_snapshot_id` changed to `"0" * 64` →
      `osce: the feed serves snapshot 0000…, the committed baseline is <id>`.

    **The positive control:** the feed re-serialised with two-space indentation (other bytes,
    same content), through `rewrite_feed`, publishes, and the origin holds those exact bytes.
  - **`test_a_failed_validation_must_name_the_retained_feed`** (P5A-01): a `validation_failed`
    artifact whose `serving_feed_sha256` is rewritten to another 64-hex value is `refused`
    `status.json does not describe the feed the repository keeps`, and the origin is unchanged.
    The unchanged artifact publishes (as in `test_a_failed_validation_commits_status_and_health_only`).
  - **`test_served_links_to_the_committed_baseline`** (P5A-01, R2-01): the OSCE artifact without
    its `baseline.json` (removed through `rewrite`), published to an origin that commits:
    - the same `baseline.json` bytes → publishes;
    - that baseline with one claim's `office_label` changed and its `snapshot_id` kept →
      `refused` `osce: the feed serves snapshot <id>, but its baseline is corrupt: baseline.json
      is corrupt: record: Snapshot: snapshot_id does not match its units and claims`;
    - that baseline without its `checks` key → `refused` `…, but its baseline is corrupt:
      baseline.json is corrupt: shape: …`;
    - IPU's valid baseline (from `fixture_artifact`) at OSCE's path → `refused`
      `…, but its baseline is corrupt: baseline.json is corrupt: it is of 'ipu', not 'osce'`;
    - no baseline → `refused` `osce: the feed serves snapshot <id>, but no baseline is committed`;
    - **the corrupt baseline left alone:** the origin commits the `office_label` row's baseline,
      and the OSCE run is made against it with OSCE unavailable (an empty offline folder, as
      Plan 4's `test_an_unknown_offline_url_is_a_404` does). Its feed serves null for OSCE and
      it carries no `baseline.json`. It publishes; the origin's `baseline.json` is still the
      corrupt bytes, and the run's `status.json` lists OSCE's `baseline.json is corrupt` reason.

    Every refusal leaves the origin, the clone's `HEAD` and its working tree unchanged.
  - **`test_the_publish_stage_has_a_deadline`** (P127): a `Git` subclass advances a fake clock
    by 50 s before every call, with `deadline=Deadline(240.0, clock)`.
    - `publish` ends `git_failed`, `git <cmd> failed: the publish stage's time limit was reached`,
      before any push, and the origin is unchanged;
    - with `subprocess.run` recorded, no call got a `timeout` above the time left or above 60;
    - **a slow check** (R2-06): `artifact.feed_content_problems` wrapped to advance the clock
      by 241 s → `git_failed`, `git status failed: the publish stage's time limit was
      reached`; no git command ran, and the origin and the clone are unchanged.
  - **`test_committed_bytes_equal_the_artifact`** (Review Focus 4):
    - The clone has `core.autocrlf=true` in its config and no `.gitattributes`
      (`gitattributes=False`). The artifact's `HEALTH.md` is rewritten to hold a raw `\r\n`.
    - After `publish`, for every repository file, `git -C <origin> cat-file blob main:<path>`
      (read from the bare origin, not the clone's tracking ref) equals the artifact's bytes.
    - The commit changes exactly `repository_files` (`git diff-tree --no-commit-id --name-only -r`).
    - Its author is `github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>`,
      and its message is `chore: update elections.json [<attempt_id>]`.
  - **`test_a_failed_validation_commits_status_and_health_only`** (S4-T05): the commit changes
    exactly `HEALTH.md` and `status.json`; the blob of `elections.json` is unchanged; the message
    is `chore: record a failed validation […]`; served is `not_checked`. The artifact has no
    `data/sources/` file and reaches the commit without reading one (check 11, R2-03).
  - **`test_another_writer_before_the_push_is_superseded`** (S4-T08):
    - `push_competitor` runs before `publish`: the result is `superseded`
      `main moved during the run`, and no commit is made.
    - A `Git` subclass whose `push` first runs `push_competitor`: the result is `superseded`
      `main moved before the push`. The origin's `main` is the competitor's commit, and its
      `elections.json` is v1's bytes.
  - **`test_push_failures_are_git_failed`:**
    - an origin whose `pre-receive` hook exits 1 (`[remote rejected]`) gives `git_failed`;
    - an origin directory removed before the fetch gives `git_failed`.
  - **`test_served_check`** (Review Focus 4, NM-T04, P127). The fakes: `clock` advances through
    `sleep`, and through `fetch` by `min(cost, timeout_s)`, where a row gives the fetch a cost.
    A fetch whose cost is over its `timeout_s` returns None. `fetch` returns a script of bodies.
    These values match `.scratch/plan5a/served_loop.py`'s `fixed`.
    - served at the 3rd fetch → `ok` after two sleeps of 60;
    - never served, free fetches → `served_mismatch` at exactly 600, after 10 fetches (at 0, 60, …,
      540);
    - never served, 45 s fetches → `served_mismatch` at exactly 600, after 6 fetches starting at
      0, 105, 210, 315, 420 and 525 (rev 1 returned at 645);
    - never served, 59 s fetches → `served_mismatch` at exactly 600. The 6th fetch starts at 595
      with `timeout_s` 5 and is cut (None);
    - the same, but the 6th fetch costs 3 s and returns the matching body → `ok` at 598;
    - **overruns** (R2-06): in these rows the fake advances the clock by the whole cost, past
      `timeout_s`, as a real fetch can. 59 s fetches, and the 6th (started at 595 with
      `timeout_s` 5) takes 6 s and returns the matching body → `served_mismatch` at 601. The
      same with a 5 s 6th fetch → `ok` at exactly 600 (`served_guard.py`);
    - never served, 1 s fetches → `served_mismatch` at exactly 600 after 10 fetches, none started
      at or after 600 (rev 1 returned at 601);
    - every recorded `timeout_s` is at most 60 and at most the time left;
    - a fetch that returns None is not served;
    - a copy of the feed with the same `content_id` and other bytes (an added space) is not served.
  - **`test_served_fetcher_is_bounded`** (R2-06, R2-07; `tests/unit/test_served_fetcher.py`,
    with the `pki` and `server` fixtures and `environ={"REQUESTS_CA_BUNDLE": str(pki.bundle)}`):
    - a route that serves `b"feed"` → `served_fetcher(environ, workdir=tmp_path, url=…)(5.0)`
      is `b"feed"`, and `tmp_path / "ca-bundle.pem"` exists;
    - a 404 → None;
    - a body dripped over 4 s (`Reply(body=b"x" * 400, drip=0.1)`) with `timeout_s` 1.0 →
      None, within 1.0 + 1.0 s of real time;
    - a `REQUESTS_CA_BUNDLE` naming a missing file raises `TrustBundleError`.
  - **`test_served_mismatch_is_red`** (R29): `publish` whose `fetch` always returns v1's bytes
    gives `("published", "served_mismatch")`. `final_verdict` for that run is red
    `served_mismatch`.
  - **`test_publish_reaches_the_writer_only_when_allowed`** (V2-T07, S4-T18): through
    `ci.__main__.main(["publish", …])`, with the environment of each row and
    `publishing.served_fetcher` replaced by a fake. Only `(schedule, main)` and
    `(workflow_dispatch, main, "true")` commit. `(workflow_dispatch, feat/x, "true")`,
    `(workflow_dispatch, main, "false")`, `(…, "True")`, `(…, "")` and `(push, main, "true")`
    each write `outcome=not_allowed` and `served=not_checked`, and leave the origin unchanged.
  - **`test_full_artifact_publishes`:** `fixture_artifact` publishes, and its commit changes
    exactly the repository paths of the artifact (3 files, plus every `data/sources/` file the
    run wrote).
  - **`test_adopt_takes_only_the_approved_artifact`** (RT-03, P124):
    - a wrong digest exits 1 and writes nothing;
    - the right digest exits 0 and writes only `data/sources/**`, with the artifact's exact
      bytes;
    - a second adopt exits 1 `data/sources already exists: …`;
    - a dry-run artifact exits 1 (P5A-08);
    - a `validation_failed` artifact exits 1 `only a published artifact has baselines`;
    - an artifact whose feed serves a snapshot that is not its own baseline exits 1 with the
      served-link problem.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/ci -q`. Expected: the new tests
  FAIL.
- [ ] **Step 3: Implement**, and change `tests/support/repo.commit`.
- [ ] **Step 4: Run** the whole suite. Expected: PASS, including every Plan 4 pipeline test that
  uses `commit`.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(ci): verify, commit, push and check the served feed; adopt first baselines (R28, R29)`.

  Mutations, one each:
  - `load_artifact` skips `read_manifest` (`test_publish_refuses_an_incomplete_artifact`, the
    digest row);
  - the path rule accepts any path under `data/` (`test_an_artifact_with_an_unexpected_file_is_refused`);
  - the `code_sha` check is skipped (`test_publish_refuses_an_incomplete_artifact`);
  - the race check is skipped (`test_another_writer_before_the_push_is_superseded`, the first
    case);
  - `rejected` maps to `git_failed` (the same test, the second case);
  - `copy_repository_files` also copies `verdict.json` (`test_committed_bytes_equal_the_artifact`);
  - `Git` drops `-c core.autocrlf=false` (the same test);
  - `served_check` always sleeps `poll_s` (`test_served_check`);
  - `served_check` loses the deadline check before the fetch (the same test, the 1 s row: an
    11th fetch starts at 600);
  - `served_check` passes `fetch_s` instead of the time left (the same test, the 59 s row ends
    at 654);
  - `served_check` compares `content_id` (the same test, the same-`content_id` row);
  - `served_check` loses the post-fetch deadline check (the same test, the 601 overrun row
    becomes `ok`);
  - `served_fetcher` passes `Deadline.after(60)` instead of `timeout_s`
    (`test_served_fetcher_is_bounded`, the drip row);
  - `load_artifact` skips `feed_content_problems` (`test_a_self_consistent_invalid_artifact_is_refused`,
    the `b"{"` row);
  - `load_artifact` skips the baseline load (the same test, the baseline row);
  - `served_link_problems` returns `[]` (the same test, the served-id row);
  - `served_link_problems` reads only the committed baseline's `snapshot_id` field, as rev 2
    did (`test_served_links_to_the_committed_baseline`, the `office_label` row);
  - `load_baseline` ignores `source` (the same test, the IPU row);
  - `served_link_problems` loads every committed baseline, served or not (the same test, the
    corrupt-baseline-left-alone row);
  - check 11 also runs for a failed validation, reading the missing `candidate.json`
    (`test_a_failed_validation_commits_status_and_health_only`);
  - the failed-validation serving check is skipped (`test_a_failed_validation_must_name_the_retained_feed`);
  - `Git` ignores its deadline (`test_the_publish_stage_has_a_deadline`, both rows);
  - `publish` ignores `allowed` (`test_publish_reaches_the_writer_only_when_allowed`);
  - `adopt` skips the digest check (`test_adopt_takes_only_the_approved_artifact`);
  - `adopt` also copies `elections.json` (the same test).

### Task 7: The workflow (`.github/workflows/update-elections.yml`; P117, P118, P126; R10, R27, S4-T09, S4-T12, NM-T08, RT-01)

**Files:**
- Rewrite: `.github/workflows/update-elections.yml`
- Create:
  - `tests/workflow/__init__.py`, `tests/workflow/test_workflow.py`;
  - `tests/conftest.py`, `tests/ci/test_conftest.py`;
  - `scripts/prove_gates.py`, `tests/scripts/__init__.py`, `tests/scripts/test_prove_gates.py`.
- Modify: `README.md` (a new "CI" section, and RT-01 under "Gates")

**Interfaces:**
- Consumes:
  - Task 5's and Task 6's commands and `publishing.RAW_URL`;
  - `fetch.SCRAPE_DEADLINE_S`, and `runner.run_sources`' `grace_s` default;
  - `publishing.SERVED_LIMIT_S`, `SERVED_POLL_S`, `SERVED_FETCH_S` and `PUBLISH_STAGE_S`, and the
    `git.Git.timeout_s` default.
- Produces:
  - the workflow;
  - `tests/conftest.py`, with `pytest_plugins = ("pytester",)`;
  - `scripts/prove_gates.py`: `VIOLATIONS`, `prove(root: Path, *, run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> list[str]`
    (the failures; empty when every gate failed as it should), and `main(argv) -> int`.

**The workflow** (exact; the pins were resolved from GitHub's API on 2026-10-23):

```yaml
name: Update Elections Calendar

on:
  push:
    branches: ["**"]
  schedule:
    - cron: "0 0 * * *"  # daily, 00:00 UTC
  workflow_dispatch:
    inputs:
      publish:
        description: "Publish the generation (main only)"
        type: boolean
        default: false

permissions: {}

jobs:
  gates:
    runs-on: ubuntu-24.04
    timeout-minutes: 15
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0
        with:
          python-version: "3.14.1"
      - name: Install
        run: |
          python -m venv .venv
          .venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
      - name: Install Chromium
        run: .venv/bin/python -m playwright install chromium
      - name: pytest
        env:
          CI: "true"
        run: .venv/bin/python -m pytest -q
      - name: mypy
        run: .venv/bin/mypy
      - name: ruff
        run: .venv/bin/ruff check
      - name: import-linter
        run: .venv/bin/lint-imports --config importlinter.ini
      - name: Prove the gates fail on purpose (RT-01)
        run: .venv/bin/python -m scripts.prove_gates

  scrape:
    needs: gates
    if: github.event_name != 'push'
    runs-on: ubuntu-24.04
    timeout-minutes: 20
    permissions:
      contents: read
    outputs:
      paused: ${{ steps.switches.outputs.paused }}
      alert_test: ${{ steps.switches.outputs.alert_test }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0
        with:
          python-version: "3.14.1"
      - name: Switches
        id: switches
        run: python -m elections_calendar.ci switches --repo .
      - name: Install
        if: steps.switches.outputs.paused != 'true'
        run: |
          python -m venv .venv
          .venv/bin/python -m pip install --require-hashes -r requirements.txt
      - name: Scrape
        if: steps.switches.outputs.paused != 'true'
        run: |
          token="$(python -c 'import secrets; print(secrets.token_hex(16))')"
          echo "::stop-commands::${token}"
          set +e
          .venv/bin/python scraper.py --live --out out
          code=$?
          echo "::${token}::"
          exit "${code}"
      - name: Summary
        if: always() && steps.switches.outputs.paused != 'true'
        run: python -m elections_calendar.ci scrape-summary --out out
      - name: Upload the generation
        if: always() && steps.switches.outputs.paused != 'true'
        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9  # v7.0.2
        with:
          name: generation
          path: out/
          retention-days: 14
          if-no-files-found: error

  publish:
    needs: scrape
    if: >-
      needs.scrape.result == 'success' && needs.scrape.outputs.paused != 'true' &&
      github.ref == 'refs/heads/main' &&
      (github.event_name == 'schedule' ||
      (github.event_name == 'workflow_dispatch' && inputs.publish == true))
    runs-on: ubuntu-24.04
    timeout-minutes: 25
    permissions:
      contents: write
    concurrency:
      group: publish-elections
      cancel-in-progress: false
    outputs:
      outcome: ${{ steps.publish.outputs.outcome }}
      served: ${{ steps.publish.outputs.served }}
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0
        with:
          python-version: "3.14.1"
      - name: Install
        run: |
          python -m venv .venv
          .venv/bin/python -m pip install --require-hashes -r requirements.txt
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333  # v8.0.2
        with:
          name: generation
          path: ${{ runner.temp }}/artifact
      - name: Publish
        id: publish
        env:
          INPUT_PUBLISH: ${{ inputs.publish }}
        run: .venv/bin/python -m elections_calendar.ci publish --artifact "${RUNNER_TEMP}/artifact" --repo .

  verdict:
    needs: [gates, scrape, publish]
    if: always()
    runs-on: ubuntu-24.04
    timeout-minutes: 5
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1  # v7.0.1
        with:
          persist-credentials: false
      - uses: actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97  # v7.0.0
        with:
          python-version: "3.14.1"
      - uses: actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333  # v8.0.2
        continue-on-error: true
        with:
          name: generation
          path: ${{ runner.temp }}/artifact
      - name: Verdict
        env:
          INPUT_PUBLISH: ${{ inputs.publish }}
          GATES_RESULT: ${{ needs.gates.result }}
          SCRAPE_RESULT: ${{ needs.scrape.result }}
          PUBLISH_RESULT: ${{ needs.publish.result }}
          PAUSED: ${{ needs.scrape.outputs.paused }}
          ALERT_TEST: ${{ needs.scrape.outputs.alert_test }}
          PUBLISH_OUTCOME: ${{ needs.publish.outputs.outcome }}
          SERVED: ${{ needs.publish.outputs.served }}
        run: python -m elections_calendar.ci verdict --artifact "${RUNNER_TEMP}/artifact"
```

**`tests/conftest.py` (P126):**
- when `os.environ.get("CI") == "true"` and any test was skipped, the session's exit status
  becomes `pytest.ExitCode.TESTS_FAILED`, and the terminal shows
  `<n> tests were skipped; under CI=true a skip is a failure (spec §11.2)`;
- when `GITHUB_STEP_SUMMARY` is set, it appends
  `pytest: <collected> collected, <passed> passed, <failed> failed, <skipped> skipped, <xfailed> xfailed\n`.

**`scripts/prove_gates.py` (P126, RT-01):**
- **The copy:** `main` extracts `git archive --format=tar HEAD` into a temporary directory with
  `tarfile` (`filter="data"`; never the `tar` command, which fails on Windows paths).
- **The violations:** for each row of `VIOLATIONS`, it appends the row's text to the row's file,
  runs the gate in that directory with the venv's executable next to `sys.executable`, checks
  that the exit code is non-zero and the output holds the row's marker, and puts the file back
  byte for byte.

  | Gate | File | Appended text | Marker |
  |---|---|---|---|
  | `mypy` | `elections_calendar/text.py` | `\n_RT01: int = "x"\n` | `Incompatible types in assignment` |
  | `ruff check` | `elections_calendar/text.py` | `\nimport os\n` | `F401` |
  | `lint-imports --config importlinter.ini` | `elections_calendar/model.py` | `\nimport elections_calendar.pipeline  # RT-01\n` | `broken` |

- **The result:** it prints one line per gate and exits 0 when every gate failed as it should,
  else 1.

**Rules:**
- **No logic in YAML** beyond the `if:` conditions above. **No `${{` inside any `run:` text.**
- The time budgets, as constants in `test_workflow.py`:
  - `SETUP_ALLOWANCE_S = 300` (checkout, Python, `pip install`; measured on the first branch run
    in 5c);
  - `PARSE_ALLOWANCE_S = 60` (about 1 s on the fixtures);
  - `UPLOAD_ALLOWANCE_S = 60` and `DOWNLOAD_ALLOWANCE_S = 60` (the artifact: 4.6 MB, plus at most
    50 MiB of `rejected/pages/`);
  - `REPORT_ALLOWANCE_S = 30` (outputs and the summary).

- [ ] **Step 1: Write the failing tests** in `tests/workflow/test_workflow.py`. The workflow is
  loaded with `yaml.safe_load`, which reads the key `on` as `True`.
  - **`test_triggers`:** push on `["**"]`; schedule `0 0 * * *`; `workflow_dispatch` with one
    input, `publish`, which is boolean and defaults to false.
  - **`test_permissions_are_least`** (NM-T08, RT-02): workflow-level `permissions` is `{}`.
    gates, scrape and verdict have exactly `{contents: read}`, and publish exactly
    `{contents: write}`. No job has another key. The text `secrets.` appears nowhere.
  - **`test_actions_are_pinned`:** every `uses:` is `<owner>/<repo>@<40 hex>`, followed by a
    `# v…` comment, and is one of the four pins above.
  - **`test_python_and_runner_are_pinned`:** every setup-python step uses `python-version`
    `"3.14.1"`, and every job runs on `ubuntu-24.04`.
  - **`test_job_conditions`** (S4-T18):
    - scrape: `needs: gates`, `if: github.event_name != 'push'`;
    - publish: `needs: scrape`, its `if` equal (whitespace collapsed) to the text above;
    - verdict: `needs: [gates, scrape, publish]`, `if: always()`;
    - no `if:` anywhere uses `cancelled()` or `failure()`;
    - the publish condition reaches publishing only through `refs/heads/main` and the two events
      that `publishing_allowed` names.
  - **`test_concurrency`** (P118): no workflow-level `concurrency`. Publish has
    `{group: publish-elections, cancel-in-progress: false}`, and no other job has one.
  - **`test_read_only_jobs_do_not_persist_credentials`:** every checkout in gates, scrape and
    verdict has `persist-credentials: false`. Publish's checkout has no `with` (it needs the token
    to push).
  - **`test_no_expression_in_run_scripts`** (Review Focus 2): no `run:` text holds `${{`. Every
    `${{` in the file is in an `env:`, `with:`, `outputs:` or `if:` value.
  - **`test_scrape_logs_stop_workflow_commands`** (Review Focus 2): the Scrape step's script
    holds, in order: a token from `secrets.token_hex`, `echo "::stop-commands::${token}"`,
    `scraper.py --live --out out`, `echo "::${token}::"` and `exit "${code}"`.
  - **`test_light_steps_use_setup_python`:** the Switches, Summary and Verdict steps run
    `python -m elections_calendar.ci …` (no `.venv`). Publish runs `.venv/bin/python -m elections_calendar.ci publish`.
    The verdict job has no Install step.
  - **`test_artifact_wiring`** (P117):
    - one upload: name `generation`, path `out/`, `retention-days` 14, `if-no-files-found`
      `error`, its `if` `always() && steps.switches.outputs.paused != 'true'`;
    - two downloads of `generation`, to `${{ runner.temp }}/artifact`, the verdict's with
      `continue-on-error: true`;
    - publish and verdict pass `"${RUNNER_TEMP}/artifact"`.
  - **`test_outputs_wiring`:**
    - scrape's outputs are exactly `paused` and `alert_test`, from the step `switches`;
    - publish's are exactly `outcome` and `served`, from the step `publish`;
    - the verdict step's `env` is exactly the eight names above, plus `INPUT_PUBLISH`, each
      reading its `needs.*` value;
    - every output name is a key of `summary.OUTPUT_VALUES`.
  - **`test_gates_job_runs_the_canonical_gates`:**
    - the run steps after Install are, in order: `playwright install chromium`, then
      `.venv/bin/python -m pytest -q` with `CI: "true"`, `.venv/bin/mypy`, `.venv/bin/ruff check`,
      `.venv/bin/lint-imports --config importlinter.ini` and `.venv/bin/python -m scripts.prove_gates`;
    - the four gate commands equal the README's Linux block line for line.
  - **`test_scrape_job_fits_its_timeout`** (R10, S4-T12):
    `SCRAPE_DEADLINE_S + grace_s + 2 + PARSE_ALLOWANCE_S + SETUP_ALLOWANCE_S + UPLOAD_ALLOWANCE_S <= 20 * 60`
    (720 + 5 + 2 + 60 + 300 + 60 = 1147), with the scrape job's `timeout-minutes` equal to 20.
  - **`test_publish_job_fits_its_timeout`** (S4-T12, P127):
    `SETUP_ALLOWANCE_S + DOWNLOAD_ALLOWANCE_S + PUBLISH_STAGE_S + SERVED_LIMIT_S + REPORT_ALLOWANCE_S <= 25 * 60`
    (300 + 60 + 240 + 600 + 30 = 1230), with publish's `timeout-minutes` 25, gates' 15 and
    verdict's 5. `Git`'s per-call `timeout_s` (60) is at most `PUBLISH_STAGE_S`, and
    `SERVED_FETCH_S` is at most `SERVED_POLL_S`.
  - **`test_served_check_reads_the_extension_url`** (S4-T09): `publishing.RAW_URL` equals the
    `DATA_URL` string in `extension/background.js`.
  - In `tests/ci/test_conftest.py`, with `pytester` (each inner run sets or removes `CI` and
    `GITHUB_STEP_SUMMARY` itself):
    - **`test_a_skip_fails_under_ci`:** an inner suite with one passing and one skipped test exits
      1 with `CI=true` and shows the message; without `CI` it exits 0.
    - **`test_counts_go_to_the_step_summary`:** the summary file gets
      `pytest: 2 collected, 1 passed, 0 failed, 1 skipped, 0 xfailed`.
  - **`test_prove_gates_applies_and_restores_each_violation`** (in `tests/scripts/`): `prove`
    runs with a fake `run`.
    - Each violation's text is in its file when its gate runs, and the file's bytes are back
      afterwards.
    - A fake gate that exits 0 is reported as a failure of `prove`. A gate that exits 1 without
      the marker is reported too.
    - `prove` returns `[]` when every fake gate fails with its marker.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/workflow tests/ci/test_conftest.py tests/scripts -q`.
  Expected: FAIL (v1's workflow; no conftest; no `prove_gates`).
- [ ] **Step 3: Implement.** Write the workflow exactly as above, then `tests/conftest.py` and
  `scripts/prove_gates.py`. In `README.md`:
  - **CI:** the trigger table (§11.1); the four jobs; which files the publish job commits; the
    outcomes and their headlines (Task 5's table); that a `superseded` day is recovered by a new
    `workflow_dispatch` on `main` with `publish: true`, never by "Re-run jobs", which keeps the
    old commit (P5A-06); `PAUSE_PUBLISHING` and `ALERT_TEST`; the artifact `generation` (14 days;
    `rejected/pages/`); that the workflow first runs on GitHub in Plan 5c;
  - **Gates:** `.venv/Scripts/python.exe -m scripts.prove_gates` proves that mypy, ruff and
    import-linter fail on purpose (RT-01).
- [ ] **Step 4: Run** the whole suite, then (controller, about 2 minutes)
  `.venv/Scripts/python.exe -m scripts.prove_gates`. Expected: PASS, and three lines that each
  say the gate failed as it should. Record the output in the ledger.
- [ ] **Step 5: Gates, mutation table, commit:**
  `ci: the v2 workflow (gates, scrape, publish, verdict) and RT-01`.

  Mutations, one each:
  - publish's permission becomes `contents: read` (`test_permissions_are_least`);
  - publish's `if` loses `github.ref == 'refs/heads/main' &&` (`test_job_conditions`);
  - the verdict's `if: always()` is removed (the same test);
  - `${{ inputs.publish }}` goes inside the Publish step's script (`test_no_expression_in_run_scripts`);
  - the Scrape step loses its `::stop-commands::` line (`test_scrape_logs_stop_workflow_commands`);
  - scrape's `timeout-minutes` becomes 10 (`test_scrape_job_fits_its_timeout`);
  - publish's `timeout-minutes` becomes 15 (`test_publish_job_fits_its_timeout`);
  - checkout is pinned to `@v7.0.1` (`test_actions_are_pinned`);
  - scrape's checkout loses `persist-credentials: false` (`test_read_only_jobs_do_not_persist_credentials`);
  - `retention-days` becomes 90 (`test_artifact_wiring`);
  - the concurrency group moves to the workflow (`test_concurrency`);
  - the conftest checks `CI == "1"` (`test_a_skip_fails_under_ci`);
  - `prove` treats exit 0 as a pass (`test_prove_gates_applies_and_restores_each_violation`).

### Task 8: Rollback and republication (`ci/recovery.py`, `scripts/republish.py`, `RELEASES.md`; P122, P123; R31, V2-T05, RT-05)

**Files:**
- Create: `elections_calendar/ci/recovery.py`, `scripts/republish.py`, `RELEASES.md`,
  `tests/ci/test_recovery.py`, `tests/fixtures/v1/update-elections.yml` (v1's workflow, copied
  byte for byte from `ff30417`, sha256 `a89ac40882d76a9414f67d7f6469b975639835396cc8413cddb7bd43a0667906`)
  and `tests/fixtures/v1/PROVENANCE.md` (its commit and digest, in the style of
  `tests/fixtures/feed/PROVENANCE.md`)
- Modify:
  - `schemas/feed-v2.schema.json`: the optional top-level `republished_from_sha256`, a 64-hex hash;
  - `elections_calendar/validate.py`: `legacy_feed_problems` and `republished_problems`;
  - `elections_calendar/feed.py`: `AttemptOutcome` gains `"republished"`, and its comment says
    that `superseded` and `paused` are never written (P120);
  - `README.md`: a "Rollback" section;
  - `tests/feed/test_validate.py`: the schema accepts the field.

**Interfaces:**
- Consumes:
  - Task 6's `Git`, `load_artifact`, `publish`, `validate.feed_content_problems`, and the test
    helpers;
  - Task 5's `switches.switches`;
  - `feed.status_doc`, `feed.Attempt`, `validate.validate_status`, `model.stored_json`,
    `model._utc_iso`, `publish.write_atomic`.
- Produces:

  ```python
  # ci/recovery.py
  # PAUSE_PUBLISHING is not excluded: pre-v2 has none, so the restore removes it (P5A-02)
  ROLLBACK_EXCLUDES: Final = (
      ":(exclude)elections.json", ":(exclude)status.json", ":(exclude)HEALTH.md",
      ":(exclude)data/sources", ":(exclude)RELEASES.md", ":(exclude).gitattributes",
  )
  class RecoveryError(ValueError): ...

  @dataclass(frozen=True, slots=True)
  class RecoveryPair:
      commit: str
      sha256: str
      recorded_in: Literal["RELEASES.md", "status.json"]

  def releases_pairs(text: str) -> dict[str, str]          # commit -> sha256
  def recorded_pair(git: Git, commit: str, releases_text: str) -> RecoveryPair
  def republished_feed(original: bytes, *, now: datetime) -> bytes
  def republish(git: Git, commit: str, *, now: datetime, releases_text: str, code_sha: str) -> tuple[bytes, bytes]   # (feed, status); writes nothing

  # validate.py
  def legacy_feed_problems(data: bytes, *, wall_clock: datetime) -> tuple[str, ...]   # v1's contract
  def republished_problems(data: bytes, *, wall_clock: datetime) -> tuple[str, ...]

  # scripts/republish.py
  def main(argv: Sequence[str] | None = None) -> int
  ```

**Rules (P122, P123):**
- **`RELEASES.md`** is created with exactly this text:

  ```markdown
  # Releases

  Spec §11.5. Each release and each recovery pair is recorded here by hand, with the user's approval.

  ## Releases

  | Version | Code SHA | `requirements.txt` SHA-256 | `requirements-dev.txt` SHA-256 | Extension ZIP SHA-256 | ZIP files | Destination | Date | Approved by |
  |---|---|---|---|---|---|---|---|---|

  ## Recovery pairs

  A recovery pair is a `main` commit and the SHA-256 of the `elections.json` blob at that commit
  (`git show <commit>:elections.json`). `scripts/republish.py --from-commit <commit>` restores only
  a pair recorded here or in that commit's `status.json`.

  | Name | Commit | `elections.json` SHA-256 | Checked |
  |---|---|---|---|
  ```

- **`releases_pairs`:** it reads the table rows under `## Recovery pairs`, stopping at the next
  `## ` heading.
  - In a row, the Commit cell must be 40 lowercase hex and the digest cell 64 lowercase hex, each
    optionally in backticks.
  - Any other row raises `RecoveryError("RELEASES.md has a malformed recovery pair row: <n>")`,
    where `n` counts the rows from 1.
- **`recorded_pair`:** these checks run in order, and the first problem raises `RecoveryError`:
  1. `commit` is 40 lowercase hex, else `give the full 40-character commit SHA`;
  2. `git cat-file -e <commit>^{commit}` succeeds, else
     `commit <commit> is not in this repository`;
  3. **`main`'s history (P5A-03):** `git symbolic-ref --short HEAD` is `main`, else
     `republish runs on branch main, not <branch>`. `git merge-base --is-ancestor <commit> HEAD`
     succeeds, else `commit <commit> is not in main's history`;
  4. `git.blob(commit, "elections.json")` exists, else `commit <commit> has no elections.json`;
  5. the expected digest is the `RELEASES.md` pair when there is one. Otherwise it is that
     commit's `status.json` `serving_feed_sha256`. With neither (no status, not JSON, or no
     64-hex digest): `no recovery pair is recorded for <commit>`;
  6. the blob's SHA-256 equals the expected digest, else
     `the elections.json of <commit> does not match its recorded digest <expected>`.
- **`republished_feed`:**
  - the original must load as a JSON object, else `the feed is not a JSON object`;
  - set `published_at` to `_utc_iso(now)` (in place if present, else appended);
  - set `republished_from_sha256` to the original's SHA-256 (in place if present, else appended);
  - write `json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n"` as UTF-8;
  - if `republished_problems(new, wall_clock=now)` returns anything, raise
    `RecoveryError(f"the republished feed is invalid: {first}")`.
- **`republished_problems`** (P5A-03): the bytes must be UTF-8 JSON, else
  `json: not UTF-8 JSON`. Then the document's format decides:
  - an object whose `schema_version` is the integer 2 (not `True`, not `2.0`) →
    `feed_content_problems(data, wall_clock=wall_clock)`;
  - an object with no `schema_version` key → `legacy_feed_problems(data, wall_clock=wall_clock)`;
  - anything else → `(f"format: schema_version {value!r} is not supported",)`, or
    `("format: the feed is not a JSON object",)`.
- **`legacy_feed_problems`** (v1's contract, as v1.0.2 reads it): its problems start `legacy: `.
  - the top-level keys include `current_month`, `errors`, `generated_at` and `months`, and are
    among those four plus `published_at` and `republished_from_sha256`;
  - `generated_at`, and `published_at` when present, are real UTC timestamps no more than
    `MAX_AHEAD` ahead of `wall_clock`;
  - `republished_from_sha256`, when present, is 64 lowercase hex;
  - `current_month` is `YYYY-MM`, and `errors` is a list;
  - `months` is an object whose keys are `YYYY-MM` and whose values are lists of objects, each
    passing §11.3's existing per-card legacy checks (`_legacy`);
  - the bytes are within `FEED_MAX_BYTES`.

  **Pre-flight:** `tests/fixtures/feed/2026-10-16-ff30417.json` must have no legacy feed
  problems. If it has any, stop and report it: v1's real feed defines the contract.
- **`republish`:**
  - it calls `recorded_pair`, then `republished_feed`;
  - the status is `stored_json(status_doc(attempt=Attempt(now, "local", "republish", code_sha), outcome="republished", severity="ok", sources=(), run_reasons=(), serving=feed))`;
  - `validate_status` must pass, else `RecoveryError`;
  - it returns `(feed, status)`.
- **`scripts/republish.py`:**
  - its arguments are `--from-commit SHA` (required), `--repo DIR` (default `.`) and `--now ISO`
    (default the clock; for tests);
  - it reads `<repo>/RELEASES.md` (missing means no rows) and `code_sha` from
    `git rev-parse HEAD`;
  - it writes `elections.json` and `status.json` into the repository with `write_atomic`;
  - it prints `republished <commit> (<original sha256>) as <new sha256>`, then
    `next: review, then commit elections.json and status.json and push (spec §15 step 7.2)`;
  - it exits 0; a `RecoveryError` exits 1 with its message and nothing written; a usage error
    exits 2.
- **The rollback (P123, P5A-02), as `README.md` "Rollback" states it and the test runs it:**
  1. **Commit `PAUSE_PUBLISHING`.** v2's workflow reads it, so v2's scheduled and dispatched
     runs stop scraping and publishing. A v2 run already in flight is superseded at the next
     push.
  2. **Run `republish.py --from-commit <sha>`**, then commit and push.
  3. **Restore and commit:** `git restore --source=pre-v2 --staged --worktree -- . <ROLLBACK_EXCLUDES>`,
     then `git commit -m "Roll back to the pre-v2 code"`. This commit removes `PAUSE_PUBLISHING`
     and brings back v1's workflow. **From this commit on, v1 is the writer:**
     - v1's workflow has no `push` trigger, so the push itself starts nothing;
     - its next 00:00 UTC run, or a dispatch, publishes v1's feed (§15: "accepted as newer");
     - it never reads `PAUSE_PUBLISHING` and commits only `elections.json`;
     - `status.json` stays the republication's, so v2 clients then show "current health can't be
       confirmed for this data" (§12.1).

     Check that the served digest still equals the republished one before 00:00 UTC.
  4. **Only if v1 must be held back too:** before step 3, disable the workflow on GitHub
     (`gh workflow disable update-elections.yml`), and enable it again to resume. That state is
     outside the repository, so no commit changes it. Disabling stops new runs only: a run
     already in progress goes on, and its publish job is `superseded` because step 1's commit
     moved `main` (`test_an_interleaved_publisher_is_superseded`); `gh run cancel <id>` stops
     it sooner. The drill is 5c's (R44).

  Every write to `main` needs the user's go-ahead at the time (§15). 5c's runbook holds the
  `MERGE_APPROVED` steps.

- [ ] **Step 1: Write the failing tests** (`tests/ci/test_recovery.py`, in temporary repositories).
  - **`test_releases_table`:**
    - the template has no pairs;
    - a row with backticked values parses;
    - a 39-hex commit, a 63-hex digest or a missing cell raises with its row number;
    - a table under another heading is ignored.
  - **`test_recovery_pair_round_trip`** (V2-T05, Review Focus 4):
    - The OSCE artifact published through Task 6's `publish` (commit `P`) has a pair read from
      its own `status.json`.
    - `republish` returns a feed for which:
      - `json.loads(new)` without `published_at` and `republished_from_sha256` equals
        `json.loads(old)` without `published_at`;
      - `generated_at` and `content_id` are unchanged;
      - `republished_from_sha256` is the old bytes' SHA-256;
      - `published_at` is `now`, in `Z` form.
    - The status has outcome `republished`, trigger `republish`, `serving_feed_sha256` equal to
      the new bytes' digest, and passes `validate_status`. Both files end in `\n` and hold no
      `\r`.
    - Committed in a clone with `core.autocrlf=true`, both blobs equal the bytes.
    - The `pre-v2` pair: the v1 feed at the first commit, with a `RELEASES.md` row, republishes,
      and keeps v1's fields plus the two new ones.
  - **`test_a_missing_or_altered_pair_blocks_restoration`:** each of these raises its message,
    and `republish.py` exits 1 with `elections.json` and `status.json` unchanged:
    - no row and no `status.json`;
    - a `RELEASES.md` digest changed by one character;
    - a commit whose `status.json` digest does not match its `elections.json`;
    - a 12-character SHA;
    - an unknown SHA;
    - a malformed row.
  - **`test_republished_feed_passes_the_schema`:** for a v2 feed, `republished_problems` is `()`.
    The same feed with `republished_from_sha256` `"x"` has a schema problem.
    `republished_problems(b"[]", wall_clock=…)` is `("format: the feed is not a JSON object",)`:
    the format check's own non-object case, which `republished_feed` never reaches (R2-04).
  - **`test_only_supported_formats_are_republished`** (P5A-03): each document below is committed
    as `elections.json` at a `main` commit with a matching `RELEASES.md` row, so its digest is
    right. `republish` raises `the republished feed is invalid: <first>`, and `republish.py`
    exits 1 with nothing written:
    - `{}` → `legacy: …`;
    - the v1 fixture without `months` → `legacy: …`;
    - the v1 fixture with one card's `country` removed → `legacy: …`;
    - the v1 fixture with an extra top-level key `evil` → `legacy: …`;
    - `schema_version` 999, `"2"`, `2.0`, `true` and null →
      `format: schema_version … is not supported` (R2-04: `2.0` is a float, not the integer);
    - **except** a JSON list, which `republished_feed` refuses before any format check: it
      raises `the feed is not a JSON object` (R2-04).

    **Positive controls:** the real v1 fixture and the OSCE v2 feed republish.
  - **`test_a_pair_must_be_on_main`** (P5A-03):
    - a commit on a side branch, with a self-consistent `status.json` pair, raises
      `commit <sha> is not in main's history`;
    - the checkout on branch `feat/x` raises `republish runs on branch main, not feat/x`;
    - after the side branch is merged into `main`, the same commit republishes.
  - **`test_rollback_hands_publishing_to_v1`** (V2-T05, P123, P5A-02), in a temporary repository
    built as `.scratch/plan5a/revert_rehearsal.py` builds its own, with the real workflows:
    - **History:** v1, with `tests/fixtures/v1/update-elections.yml` as its workflow, is tagged
      `pre-v2`. Then the v2 code is committed, with this repository's
      `.github/workflows/update-elections.yml` (Task 7's) and the first baselines; then more v2
      code, tagged `v2.0.0`; then a publication, `PAUSE_PUBLISHING`, and a republication from
      `pre-v2` (with its `RELEASES.md` row).
    - **Before the restore,** `switches(repo)["paused"] == "true"`: v2's reader honours the
      marker.
    - **After the restore of P123 and its commit:**
      - `elections.json` and `status.json` equal the republication's bytes;
      - `generated_at` is v1's;
      - `data/sources/**` equals the publication's;
      - `scraper.py` is v1's;
      - the v2-only files are gone;
      - `PAUSE_PUBLISHING` is gone;
      - the workflow equals the v1 fixture's bytes. Loaded with `yaml.safe_load`, its triggers
        are exactly `schedule` and `workflow_dispatch` (no `push`), no step's text mentions
        `PAUSE_PUBLISHING`, and its one `git add` adds only `elections.json`. These are the facts
        P123's "v1 is the writer" rests on.
    - `git revert --no-commit pre-v2..v2.0.0` on the same history exits non-zero, which records
      why P123 replaces it.
  - **`test_an_interleaved_publisher_is_superseded`** (RT-05): a scheduled run's artifact, built
    at the commit before `PAUSE_PUBLISHING`, is published after the pause and the republication
    reached the origin. The result is `superseded`, and the origin's `elections.json` stays the
    republished bytes.
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement**, and write `RELEASES.md`, the schema field, the v1 workflow fixture
  and the README "Rollback" section. Task 7 has already rewritten the working-tree workflow, so
  write the fixture from
  `git -c core.autocrlf=false cat-file blob ff30417:.github/workflows/update-elections.yml` and
  check its sha256. The README section covers: the steps above, that v1 is
  the writer after step 3, the recovery pairs and their two formats, and that `republish.py`
  writes but never commits.
- [ ] **Step 4: Run** the whole suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(ci): recovery pairs, republish.py and the rollback (R31)`.

  Mutations, one each:
  - an abbreviated SHA is accepted (`test_a_missing_or_altered_pair_blocks_restoration`);
  - the digest comparison is skipped (the same test);
  - `RELEASES.md` is not consulted (`test_recovery_pair_round_trip`, the `pre-v2` part);
  - `generated_at` is also set to now (the same test);
  - `republished_from_sha256` is the new bytes' digest (the same test);
  - a malformed row is skipped (`test_releases_table`);
  - `ROLLBACK_EXCLUDES` loses `data/sources` (`test_rollback_hands_publishing_to_v1`);
  - `ROLLBACK_EXCLUDES` keeps `:(exclude)PAUSE_PUBLISHING` (the same test);
  - `republished_problems` treats `schema_version` `True` as 2 (`test_only_supported_formats_are_republished`);
  - `republished_problems` accepts `2.0` as 2 (the same test, the `2.0` row);
  - `legacy_feed_problems` checks only that the document is an object (the same test, the `{}` row);
  - the `main`-history check is skipped (`test_a_pair_must_be_on_main`);
  - the race check is skipped (`test_an_interleaved_publisher_is_superseded`).

### Task 9: The bounded live check (`scripts/live_check.py`; P116, P125; R30, R34, §13.5)

**Files:**
- Create: `scripts/live_check.py`, `tests/scripts/test_live_check.py`, and
  `tests/expected/reviewed_reschedules.yaml` (R2-02): `[]`, under a comment that gives the row
  keys and says that a row is added only after the user has reviewed the reschedule
- Modify: `README.md` (a "Live check" section)

**Interfaces:**
- Consumes:
  - Task 4's `--dry-run`, `verdict.json` `requests`, and `pipeline.DRY_RUN_SCRAPE_DEADLINE_S`;
  - the CLI's offline run; `tests/expected/2026-10-16.yaml`; `FEED_BUDGET_BYTES`; `text.fold`.
- Produces:

  ```python
  LIMIT_S: Final = 600
  def run_bounded(cmd: Sequence[str], *, limit_s: float, cwd: Path, log: Path) -> int | None   # None: killed at the limit
  def kill_tree(process: subprocess.Popen[bytes]) -> None
  def alive(pid: int) -> bool
  def load_reviewed(path: Path) -> list[dict[str, Any]]   # raises ValueError on a bad row
  def compare(live: Path, offline: Path, expected: Path, reviewed: Sequence[Mapping[str, Any]]) -> tuple[list[str], list[str]]   # (material lines, information lines)
  def main(argv: Sequence[str] | None = None) -> int
  ```

**Rules:**
- **`run_bounded`:**
  - It starts the command in its own process group: `start_new_session=True` on POSIX, or
    `CREATE_NEW_PROCESS_GROUP` on Windows. stdout and stderr go to `log`.
  - It waits up to `limit_s`. At the limit it calls `kill_tree` and returns None.
  - **`kill_tree`:** on POSIX, `os.killpg(pgid, SIGKILL)`; on Windows, `taskkill /T /F /PID <pid>`.
- **`alive(pid)`:** on POSIX, `os.kill(pid, 0)` (`ProcessLookupError` means gone), and on Linux a
  zombie (state `Z` in `/proc/<pid>/stat`) is gone too, because a killed grandchild may wait
  to be reaped. On Windows,
  `OpenProcess` and `GetExitCodeProcess` through `ctypes`, with `STILL_ACTIVE` 259. Never call
  `os.kill` on Windows: it terminates the process.
- **`main --out DIR [--reviewed FILE]`:**
  1. Read `load_reviewed(FILE)` (default `tests/expected/reviewed_reschedules.yaml`). A
     `ValueError` exits 2 with its message, before anything runs. Make `DIR/<UTC stamp>/`.
  2. Run the offline fixture run into `offline/`:
     `[sys.executable, "-m", "elections_calendar", "--offline", "tests/fixtures", "--now", "2026-10-19T12:00:00Z", "--out", …, "--repo", <an empty dir>]`.
  3. Run `[sys.executable, "scraper.py", "--live", "--dry-run", "--out", <stamp>/live, "--repo", <an empty dir>]`
     through `run_bounded(limit_s=LIMIT_S)`, logging to `live.log`.
  4. Compare, and write `live_check.md`.
  5. Exit 0 when the report is written and the live run exited 0. Exit 1 when the run was killed
     or failed: the report is still written, with what is known.
- **`compare` (P125).**
  - **Material:**
    - for each fixture page in the offline `candidate.json` scopes, the live page with the same
      key is missing, is not `ok`/`valid_empty`, or (when the fixture's `units_seen` is above 0)
      has `units_seen` under half or over double the fixture's;
    - a source at severity `error` in the live `status.json`;
    - each `level: national` entry of the expected file whose date span overlaps the live feed's
      window (P5A-05: overlap, not "starts inside") and has no **witness child**. Below,
      `<contest>` is `<place> <office> round <round> <date>`, without ` round <round>` when the
      entry's round is null. A child **of the same contest**:
      - is on a card whose `place_id` and `level` are the entry's `place` and `level`;
      - has `fold(entry office)` inside `fold(office_label)` (`text.fold`);
      - has `round` equal to the entry's, and `jurisdiction` equal when the entry names one.

      It is a **witness** when its card's date span overlaps the entry's, or (R2-02) when a
      **reviewed row** links the entry to it: a row of `reviewed` whose `place`, `office`,
      `round` and `jurisdiction` (absent on both, or equal) are the entry's, whose `from` is the
      entry's `date`, and whose `to` span overlaps the child's card. A reviewed witness gives the
      information line
      `rescheduled from <from> to <card date> (reviewed): <place> <office>; the sources wrote <old dates>`,
      where `<old dates>` is `rescheduled_from` joined by `"; "`, or `no old date`.

      With no witness, the material line is
      `possible reschedule, review required: <contest> -> <card date> (rescheduled_from: <old dates>)`
      for the first child of the same contest with a non-empty `rescheduled_from`, and
      `expected and not found: <contest>` when there is none. `rescheduled_from` is a list of
      old dates as the sources wrote them (D2, `model.Child`): it is shown, never parsed, and
      never a witness by itself. One reviewed row links one entry, so a second expected entry of
      the same contest stays unresolved.

      A child of another office on the same card, or on another card of the same place and date,
      is not a witness. Date spans: `YYYY-MM-DD` is one day, `YYYY-MM` is the month, and
      `A to B` runs from A through B. A card's span is its month when `date_precision` is
      `month`, else `date` through `end_date`. The prototypes are
      `.scratch/plan5a/expected_witness.py` (on the fixture feed, window 2026-09 to 2027-01, all
      74 overlapping national entries have a witness) and `witness_rows.py` (every row of
      `test_compare_needs_a_witness_child`);
    - **`load_reviewed`** reads a YAML list. Each row has exactly `place`, `office`, `round`, `from`,
      `to` and `note`, plus an optional `jurisdiction`; `from` and `to` are in the expected
      file's date forms and `note` is non-empty text. Anything else raises
      `ValueError(f"reviewed_reschedules.yaml row {n}: {problem}")` (rows counted from 1);
    - live `feed_bytes` over `feed_budget_bytes`;
    - `requests` over 40;
    - a killed run.
  - **Information:**
    - pages present live only (for example a longer NDI chain);
    - every source's severity, live and on the fixtures;
    - the feed's bytes and `gzip` bytes against the budget;
    - the requests used;
    - the elapsed time.
- **`live_check.md`:**
  - the title `# Live check <stamp>`;
  - the limits;
  - `Material differences: <n>` with the list;
  - `Information` with the list;
  - the last 40 lines of `live.log`.

- [ ] **Step 1: Write the failing tests** in `tests/scripts/test_live_check.py`.
  - **`test_an_overrunning_run_is_killed_with_its_children`** (Review Focus 5):
    - a script written to `tmp_path` starts a `multiprocessing` spawn child that sleeps 120 s,
      writes both PIDs to a file, and sleeps 120 s itself;
    - `run_bounded(limit_s=3)` returns None within 3 + 10 s;
    - `alive` is false for both PIDs within 5 s.
  - **`test_a_run_within_the_limit_returns_its_code`:** a script that exits 3 returns 3, and its
    output is in the log.
  - **`test_compare_marks_material_differences`:** "live" is a copy of the offline fixture
    artifact, edited in place: one page's `units_seen` below half; one source at `error`;
    `feed_bytes` over the budget; `requests` 41.
    - Each edit gives one material line.
    - An unedited copy gives none.
    - A page added live gives an information line only.
  - **`test_compare_needs_a_witness_child`** (P5A-05), on copies of the fixture artifact:
    - Brazil's 2026-10-04 card loses its `Brazilian Presidency` child, keeping the Chamber and
      Senate children → exactly one material line,
      `expected and not found: iso:BR Presidency round 1 2026-10-04`;
    - the whole card removed → three material lines (Presidency, Chamber of Deputies, Federal
      Senate);
    - **moves** (R2-02): the Presidency child moved to a new national `iso:BR` card dated
      2026-10-11. `REVIEWED` is the one row
      `{place: iso:BR, office: Presidency, round: 1, from: 2026-10-04, to: 2026-10-11, note: test}`:
      - `rescheduled_from` `["4 October 2026"]` with `REVIEWED` → no material line, and the
        information line
        `rescheduled from 2026-10-04 to 2026-10-11 (reviewed): iso:BR Presidency; the sources wrote 4 October 2026`;
      - the same without a reviewed row → one material line,
        `possible reschedule, review required: iso:BR Presidency round 1 2026-10-04 -> 2026-10-11 (rescheduled_from: 4 October 2026)`;
      - `["1 September 2026"]` (an unrelated date) and `["???"]` (unreadable), each without a
        row → that same material line, with their own text;
      - `[]` without a row → `expected and not found: iso:BR Presidency round 1 2026-10-04`;
      - `[]` with `REVIEWED` → no material line (`the sources wrote no old date`);
    - **two expectations, one link:** a test-written expected file with the Presidency round 1
      entry and a copy of it dated 2026-11-08; the child moved to 2026-11-29 with
      `["4 October 2026"]`; one reviewed row from 2026-10-04 to 2026-11-29 → the 2026-10-04
      entry is witnessed (information line), and the 2026-11-08 entry gives
      `possible reschedule, review required: iso:BR Presidency round 1 2026-11-08 -> 2026-11-29 (…)`;
    - a reviewed file whose row has no `note` → `load_reviewed` raises
      `reviewed_reschedules.yaml row 1: …`, and `main` exits 2 with it before `run_bounded` is
      called; the committed `tests/expected/reviewed_reschedules.yaml` loads as `[]`;
    - the 2026-10-04 Presidency child's `round` changed to 2 → one material line (round 1 has no
      witness);
    - the unedited copy → no material line, so a card of several offices witnesses each of them;
    - a test-written expected file with one national entry dated `2026-08-25 to 2026-09-05`
      (overlapping the window's first month), for a place with no card then → one material line.
      A "starts inside the window" rule would skip it.
  - **`test_live_check_main_with_a_fake_run`:** with `run_bounded` replaced by a function that
    copies the offline artifact into the live folder, `main` writes `live_check.md` with
    `Material differences: 0` and exits 0. With a fake that returns None, it exits 1 and the
    report says the run was killed.
  - **`test_dry_run_fits_the_live_check_limit`** (S4-T12):
    `DRY_RUN_SCRAPE_DEADLINE_S + 5 + 2 + 60 <= LIMIT_S` (480 + 67 = 547).
- [ ] **Step 2: Run** them. Expected: FAIL.
- [ ] **Step 3: Implement**, and add the README "Live check" section: the command, the limits,
  the material rules, and that it is not a gate.
- [ ] **Step 4: Run** the whole suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(scripts): the bounded live check (§13.5)`.

  Mutations, one each:
  - `kill_tree` kills only the direct child (`test_an_overrunning_run_is_killed_with_its_children`);
  - `run_bounded` waits without a limit (the same test, run with a timeout);
  - the half rule becomes a quarter (`test_compare_marks_material_differences`);
  - expected contests are not checked (`test_compare_needs_a_witness_child`, the whole-card row);
  - the witness ignores the office (country and date only, as rev 1) (the same test, the
    Presidency row);
  - the witness ignores the round (the same test, the round row);
  - the reviewed rows are not consulted (the same test, the `REVIEWED` row);
  - any non-empty `rescheduled_from` is a witness, as in rev 2 (the same test, the
    `1 September 2026` row);
  - a reviewed row's `from` is not compared (the same test, the two-expectations row);
  - the window test is "starts inside" (the same test, the range row);
  - a killed run exits 0 (`test_live_check_main_with_a_fake_run`).
- [ ] **Step 6 (controller): run the live check once.**
  - **What it does:** read-only GETs of the nine public sources, at most 40 requests, with a hard
    limit of 10 minutes (D10: routine). State the expected runtime (at most 11 minutes) before
    starting.
  - **The command, in the background:**
    `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m scripts.live_check --out .scratch/live`,
    with this machine's TLS bundle variable set as for any live run (README "TLS").
  - **Record in the ledger:**
    - the report's material and information lines;
    - the requests used and the elapsed time;
    - the live feed's bytes and gzip bytes against 524,288 (R34; P114's decision is confirmed or
      reopened with the live number);
    - that no worker process was left behind.
  - **A material difference** is reported to the user. It changes no code in 5a; 5c's first
    rollout pauses on it (§13.5).

---

## Requirements for later plans

Plans 5b and 5c pull these rows into their own tasks, each with the named acceptance test. Rows
R4 (extension part), R22, R25, R26 (popup part) and R35 stand as written in Plans 2b, 3 and 4.

| ID | Requirement | Owner | Acceptance test (name and result) | Completion stage |
|---|---|---|---|---|
| R38 | The v2 extension's feed URL stays `publishing.RAW_URL`. `test_served_check_reads_the_extension_url` reads `extension/background.js`; if 5b moves the constant, it moves the test's reader with it | Plan 5b | `test_served_check_reads_the_extension_url` | 5b's extension |
| R39 | The gates job runs the extension suite under `xvfb-run` (§13.4), still with `CI=true` and no skips (P126). The workflow tests pin the new step | Plan 5b | the workflow tests; the suite's counts in the job summary | 5b's workflow change |
| R40 | V2-T03 and NM-T03: the client orders feeds by `published_at` (then `generated_at` for v1) and accepts the republication of Task 8's bytes. After a rollback (P123, P5A-02), v1 writes `elections.json` and `status.json` stays the republication's: the v2 client shows the §12.1 mismatch banner ("current health can't be confirmed for this data") over v1's feed | Plan 5b | V2-T03, NM-T03 as in §13.3, on Task 8's republished fixture; a v1 feed newer than the republication, beside the republication's `status.json`, shows the mismatch banner | 5b's extension |
| R41 | §15 step 1: the first branch run, with the user's go-ahead. O7 (the summary visible), O1 (IPU in CI), R5 (certifi on GitHub's runners), and the setup time against Task 7's `SETUP_ALLOWANCE_S` (300 s) | Plan 5c | the run's summary, read by the user; the ledger records the times | 5c |
| R42 | §15 step 2: the first baselines from the branch run's artifact through `ci adopt`, compared with Task 9's live check and the expected file; the user approves the manifest digest | Plan 5c | RT-03, RT-04 | 5c |
| R43 | §11.5: the `pre-v2` recovery pair row in `RELEASES.md` (checked by re-reading the blob), and the release rows | Plan 5c | `recorded_pair` on the real `pre-v2` commit | 5c |
| R44 | §15 step 7: the rollback is P123's restore, not the range revert. The runbook copies `recovery.ROLLBACK_EXCLUDES` and says v1 is the writer from the restore commit on. Holding v1 back is `gh workflow disable update-elections.yml` before the restore, and `gh workflow enable` to resume (P5A-02). The RT-05 and RT-07 drills, and the disable/enable drill, run with the user's go-ahead. The drill disables the workflow while a run is in progress: GitHub stops new runs only (rev 3, R2-05) | Plan 5c | RT-05, RT-07; while the workflow is disabled, neither a dispatch nor the schedule starts a run; the run already in progress finishes or is cancelled, and its publish job is `superseded` or never runs; once enabled, a dispatch runs | 5c |
| R45 | §16 housekeeping. The `dowjones` remote points at `github.dowjones.net/SenescalK/global-elections-calendar-1`, which the user's memory records as a private mirror pushed on 2026-08-04, not a dead remote: ask before removing it | Plan 5c | the user's answer, recorded | 5c |
| R46 | GitHub-side behaviour the local tests cannot show (P5A-06, P5A-09). **Re-runs:** a full re-run and a re-run of the failed jobs only, after a red `publish`; record which artifact attempt the fixed name `generation` resolves to and the `GITHUB_SHA` each attempt sees (a re-run keeps the original). **Concurrency:** two dispatches while a publish job runs; record that the older pending publish job is cancelled, that the verdict job turns red with `publish failed`, and that the failure email arrives | Plan 5c | the runs' summaries and the email, read by the user; the ledger records the attempts, the artifact ids and the SHAs | 5c |

## After Plan 5a

- **The branch** has the Plan 5a commits on top of the commit that holds this plan, with all
  gates green. Nothing is pushed or merged, and no workflow has run on GitHub.
- **The Review record** shows every Plan 5a row as "verified", with its commit in the SDD ledger.
- **`python scraper.py --offline tests/fixtures --now 2026-10-19T12:00:00Z --out out`** writes a
  complete artifact that `ci publish` would accept in its context. **`scripts/live_check.py`** has
  run once, and its report is in the ledger.
- **Next:** Plan 5b (extension v2.0.0, its ZIP and the Playwright suite), written against this
  code.
