# Never-miss v2, Plan 4: Health, snapshots, feed and publishing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 3 (2026-10-20).** Records the user's decisions of the same day
(`claude-code-plan-4-decision-response-2026-10-20.md`). The plan still needs the user's
approval before Task 1 starts.
- **Feed budget (R26), decided:** `FEED_BUDGET_BYTES = 524_288` (512 KiB). The 2,000,000-byte
  validation ceiling and Plan 5's popup check stay; Task 9 measures the final stamped feed.
- **P84, decided:** each child source carries `status_claim`, `date_meaning` and `date_status`.
- **P85, decided:** `possible_matches_outside` counts the distinct ids left out. An item whose
  every candidate is outside keeps its kind and reason.
- **P91, changed:** a coverage gap is kept in `baseline.json` and reported on every run while its
  claims are in the window and not listed again. An acknowledgement mutes its effect on the
  verdict, never its visibility, and never covers a gap that began after it.
- **P93, changed:** beside a baseline of another registry version, a candidate with an
  unexplained drop is `unavailable`, not promoted.
- **Recorded, not done here:** M3 as R37 (parked by the user); NDI's independent card count as
  R36 (approved in principle, subject to fixture verification).
- **Not reopened:** I2 is built at `6ba511b` and stays as built until the user rules on it.

**Revision 2 (2026-10-20).** Revised after the red-team review of the same day
(`never-miss-v2-plan-4-red-team-review-2026-10-20.md`: findings P4-01 to P4-07 and two contract
corrections). Each finding has a row in "Review record":
- **P4-01:** a provisional change compares the whole claim, not only its date and status (P105).
- **P4-02:** a new year, or a list the source says is empty, restarts that scope's history (P90).
- **P4-03:** `accept_drop` sets a floor on usable claims as well as on units (P95).
- **P4-04:** a unit acknowledgement compares the unit's full text, never the 300-character
  display text (P88).
- **P4-05:** after a corrupt `health_state.json`, only acknowledgements made after the recovery
  count (P94).
- **P4-06:** the run validates `status.json` before it writes the artifact (Task 8).
- **P4-07:** every SC2 mapping needs a witness: a child or an umbrella of the record's office
  (P101).
- **Contracts:** `status.json` keeps each reason's scope and whether it is acknowledged (Task 7),
  and a new run id changes both `status.json` and `manifest.json` (Task 8).
- **Four decisions the review reopened went to the user:** P84 (per-source status, date meaning
  and date status), P85 (a count of possible matches outside the window), P91 (how long a
  rollover warning lasts) and P93 (what a registry change does). Revision 3 records the answers.

**Revision 1 (2026-10-20).** Written against `6ba511b` (Plan 3 complete), in nine tasks.
- **The pre-flight** took every "Requirements for later plans" row that Plans 1–3 gave to Plan 4:
  - Plan 1: C9 (stored IDs), C20 (loaders), C1 (trust);
  - Plan 2a's Plan 4 list;
  - Plan 2b's R1, R2 and R11; Plan 2c's R14, R15 and R16;
  - Plan 3's R5 (legacy part) and R17–R21, R23, R24 and R26;
  - the RESUME notes of 2026-10-20 (R18 catches `ValueError`, serialisers, item dates, before-window
    items, umbrella coverage per child, R26 weight) and the older open items (N-4, F-10, the
    `coverage_gap` promotion question);
  - the S4, NM and V2 acceptance rows that are not the workflow's or the extension's.

  Each one has a row in "Review record".
- **Measured values** come from prototypes in `.scratch/plan4/proto/` (see "How to execute this
  plan").
- **The feed byte budget (R26)** is `FEED_BUDGET_BYTES = 524_288` (512 KiB, the user's decision
  of 2026-10-20). Measured on the fixtures: 393,152 bytes compact with P84's and P85's fields
  (361,114 without them), 25.01% under the budget, about 24 KB gzipped either way (v1's feed:
  27,557 bytes). Task 9 measures the final stamped feed again.
- **The semantic items under "Spec corrections" need the user's approval before Task 1 starts.**
  Each one gives the alternative and what it would cost.

**Goal:** Turn each run's parsed sources into a complete, validated, publishable generation,
offline: snapshot acceptance, source health, acknowledgements, the v2 feed with its legacy
projection, `status.json`, `HEALTH.md` and the run artifact (spec §5.6–§5.10, §9.3–§9.6,
§11.3).
- An invalid or shrunken candidate never replaces a baseline, and its age stays visible.
- Every relevant unit that is not fully parsed is an attention item.
- The feed carries what the extension shows or checks, within the byte budget.
- Nothing is published: `python -m elections_calendar` writes `out/`. The workflow, the push,
  the served check and the extension are Plan 5's. v1 keeps running unchanged.

**Architecture:**
- **`model.py`** gains the shared vocabulary that more than one layer needs: `short_id`,
  `canonical_json`, `SOURCE_ORDER`, `SOURCE_NAMES`, each reason code's level and stage,
  `DropAcceptance` and `SnapshotHealth`. `Reason` gains `page`, `year` and `since`; `AttentionItem`
  gains `date`, `unit_id` and `unit_text`.
- **`snapshots.py`** (new): snapshot records, ids, the store's loaders, the acceptance decision
  (§9.3), provenance stamping and unit attention items.
- **`health.py`** (new): `known_issues.yml`, `health_state.json`, acknowledgements, the match
  diagnostic (§9.5), severity (§9.4) and the verdict after acknowledgements (§9.6).
- **`feed.py`** (new): each source's health entry (§5.6), the v2 feed and its legacy projection
  (§5.3–§5.7), `status.json` (§5.8) and `HEALTH.md`. It sits above `health` and `snapshots`, so
  it is where their results meet.
- **`publish.py`** (new): `content_id`, the canonical bytes, atomic writes and the manifest.
- **`validate.py`** (new): the two JSON Schemas and the checks of §11.3.
- **`pipeline.py`** (new) and **`__main__.py`** (new): the run, offline or live, and the CLI.
- **Tests:** `tests/snapshots/`, `tests/health/`, `tests/feed/`, `tests/pipeline/`, plus
  `tests/expected/` (the hand-written expected file) and `tests/fixtures/pages.json` (the
  offline page map).

**Tech Stack:**
- Python 3.14.1;
- the standard library (`hashlib`, `json`, `tempfile`, `argparse`, `os.replace`);
- `PyYAML` 6.0.3 and `jsonschema` 4.26.0, both already in `requirements.txt`;
- `hypothesis` 6.170.1 for one property test.

No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`.
- Read these sections before you start:
  - §4 (the layers), §5.3–§5.10;
  - §9.3–§9.6;
  - §11.2 (`scrape` only), §11.3 and §11.6;
  - §13.2, §13.3 (the S4, NM and V2 rows), §13.4 "Pipeline tests" and "End-to-end";
  - Appendix B.
- Where this plan and the spec differ, the plan wins *only* for the items under "Spec corrections".
- Plan 3 (`docs/superpowers/plans/2026-10-19-never-miss-v2-plan-3-merge.md`) is built at
  `6ba511b`. Its Interfaces blocks describe the code, except where the errata below say otherwise.

## "As built" errata (read first)

**Plan 3** (built at `6ba511b`: 1627 tests, mypy 77 files, ruff clean, `Contracts: 2 kept, 0 broken`):
- **The wrong-merge audit is stricter than Plan 3's Task 6 text** (final review I2). It mirrors
  the matcher exactly: strict jurisdictions for joined pairs, the R2-02 label rule for
  unrecognised offices, and `date_conflict` excuses an attached date only for a month claim.
  It is listed for the user's veto. No Plan 4 task depends on the choice: both audits pass the
  fixture merge, and the stricter one can only fail closed (`merge_failed`).
- `merge(claims)` reads its argument once, so a one-shot iterator works (final review I1).
- **What Plan 4 receives from the fixture merge** (`merge(fixture_claims(), now=FIXTURE_NOW)`,
  `FIXTURE_NOW` = 2026-10-19T00:00Z; `feed1.py`):
  - 742 cards, of which **100 are in the window**: September 22, October 30, November 28,
    December 15, January 5. They hold 202 children and 274 child sources.
  - 67 attention items: 31 `unresolved_evidence` before the window, 31 `undated_listing` and
    5 `unresolved_evidence` in or after it. Of the 36 relevant ones, 15 of their 16
    `possible_matches` name children outside the window.
  - 31 undated listings (2026: 4, 2027: 25, 2028: 2).
  - 1335 dispositions.
- **Every claim is unstamped** (`fetched_at` None, `fallback` False, `snapshot_id` None,
  `provisional` False). Plan 4 stamps them (R19).
- **`AttentionItem` has no date,** and its `merge_ids` must be non-empty. Task 3 changes both.
- **`short_id` and `SOURCE_ORDER` live in `merge/identity.py`.** Task 1 moves them to `model.py`;
  `identity` re-exports both, so no merge import changes.
- **Parked by the user, outside this plan:** M3 (a year-less "postponed from 15 November" with a
  January date loses its old-date link). It is a matching limitation, recorded as R37. Plan 4
  guesses no year and reports nothing about it as fixed.

**Plans 2a–2c, as measured for Plan 4** (`reasons1.py`, `units2.py`, `match1.py`):
- **Every source's ledger is clean on its fixtures.** Coverage:
  - ElectionGuide `upcoming` 45, `past` 200, `anticipated` 106 units;
  - Wikipedia `national-2026` 108, `national-2027` 46, `local-2026` 457, `local-2027` 53;
  - OSCE 634; IPU 281; A-WEB `calendar` 32 (year 2026); Carter 61; EEAS 34;
  - NDI `p0` 20 and `p1` 18 (the chain ends after two pages);
  - EISA `calendar` 0, `y2026` 22, and the note `not_published_yet` "no heading 'eisa african
    election calendar 2027'".
- **Relevant units that are not fully parsed** (outcome `partial` or `unparsed`, relevance not
  `before_window`): **121**.
  - Wikipedia 111: `local-2026` 61, `local-2027` 48, `national-2026` 2 (60 partial, 51
    unparsed);
  - IPU 4 (`designation_unrecognised`), A-WEB 3, NDI 1 (`level_unresolved`, BARMM), EISA 2
    (`no_new_date`, Libya).
  - 63 of them have a dated claim; 2 of those are dated after the window end.
  - Their texts start with the source's own date prefix ("23 February: Canada, …").
- **Where unit ids put the page key:** `<source>:<key>/…`, and Wikipedia's
  `wikipedia:<key>@rev<revid>/…`. `PageCoverage.unit_prefix` gives each page's exact prefix.
- **`unnamed_parts` false alarms (R21):** "Presidential and Vice-Presidential" (PH) and
  "Presidential and Vice Presidential" (NG) give `['Vice-Presidential']`, because `_DEPUTY_OF`
  knows only "vice president", "deputy governor" and the like. "National and Provincial" (ZA)
  gives `['National']`, and that alarm is true: the whole label classifies as a subnational
  council, so the national part is lost. Fixing the joint ticket changes no fixture unit
  (`r21c.py`).
- **Notes carry no page or year.** EISA's year notes (`not_published_yet`,
  `required_year_missing`) name the year only in their detail text. Task 1 adds the fields.
- **The runner's `_load(spec)` is private.** Task 8 makes it public as `load_adapter`.

## Plan series

1. **Foundations** (done, `8632297`).
2. **Sources:** 2a (done, `f5f3a1c`), 2b (done, `94ac45a`), 2c (done, `fa4d0a2`).
3. **Merge** (done, `6ba511b`).
4. **Health, snapshots, feed and publishing (this plan).**
5. **Workflow, extension v2.0.0 and rollout.**

**Not in this plan:**
- **No workflow and no publication:** `.github/workflows/`, the `publish` and `verdict` jobs, the
  push race (`superseded`), `PAUSE_PUBLISHING`, `ALERT_TEST`, the served check
  (`served_mismatch`), `republish.py` and `RELEASES.md` are Plan 5's.
- **`scraper.py` stays v1's.** Plan 5 turns it into the thin entry point.
- **No bounded live check and no `--dry-run`** (§13.5). Plan 5 adds both. Plan 4's tests make no
  network access; `--live` is wired but not run.
- **No extension change.**
- **No first baselines in the repository.** `data/sources/` is created by the first reviewed run
  (§15 step 2, Plan 5).
- **Not done here:** NDI's independent card count (`.add-to-cal`, Plan 2c). The user approved
  the approach in principle, subject to fixture verification; R36 carries the conditions.
- Nothing is pushed or merged.

## Global Constraints

Plans 1–3's Global Constraints still hold:
- **Code:**
  - the layering (the import-linter layers contract);
  - civil dates;
  - no network in tests;
  - `[0-9]`, never `\d`, in new regexes;
  - the merge is pure and fails closed.
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

- **Time is passed in.** Every function that depends on the time takes a timezone-aware `now`.
  Nothing below `pipeline` reads the clock. `pipeline.run` takes `now` and a separate
  `wall_clock` for the §11.3 timestamp check. A naive datetime anywhere raises.
- **Timestamps on disk** are UTC ISO 8601 with a `Z` suffix (`model._utc_iso`).
- **Nothing is lost silently.** A corrupt or hand-edited committed file never crashes the run
  and is never read as empty. It gives a loud, unacknowledgeable reason (P94).
- **The baseline only moves forward through a valid candidate.** No acknowledgement and no
  partial page ever changes a baseline. Only `accept_drop` changes acceptance, and only for
  drops (§9.6).
- **A coverage gap is diagnostic.** Its claims stay in `baseline.json`; they are never stamped,
  served or merged (P91).
- **Determinism.** Every list written to disk or into the feed has a stated total order. The
  same evidence and the same `now` give byte-identical files, except for the run identity
  (`attempt_id`, `trigger`, `code_sha`), which comes from the environment, and `parse_ms`, which
  is measured (`RunConfig.timer`; tests pass a fixed one).
- **Text that came from a source** is collapsed (`collapse_ws`) and cut before it is stored in
  a reason, an item or a sample. `HEALTH.md` escapes it (Task 7). The feed is JSON, so it needs
  no escaping, and the extension renders it as text (Plan 5).
- **The layers** (P83):

  ```
  __main__
  pipeline
  feed | publish | validate
  merge
  health | snapshots
  ledger | runner
  sources
  fetch | dates | places | offices | window
  model | text
  ```

  `health` and `snapshots` never import each other; what they share is in `model`.
- **Literals and messages.** Literal values, reason details and error messages are copied
  verbatim from this plan.

## Review Focus

These are the five inputs most likely to hurt a user that the spec implies but no step spells out.
Each one is pinned by the named tests, in the task that owns the code.

1. **A fallback that ages.** A source fails every day for ten days.
   - The feed keeps its original `served_fetched_at` and each claim's `fetched_at`, never the
     time of the run. `data_as_of` is the oldest served fetch.
   - From the eighth day the source has `fallback_stale` (exactly 7 days is still fresh), which
     no acknowledgement can mute.
   - The baseline file is not rewritten.

   Pinned by `test_fallback_age_is_never_refreshed` (Task 2), `test_data_as_of_is_the_oldest_served_fetch`
   (Task 6) and `test_a_ten_day_outage_ages_honestly` (Task 8).
2. **A committed file that is corrupt or hand-edited:** `baseline.json` with a changed claim, a
   wrong `snapshot_id`, a missing key or a non-list; `health_state.json` that is not JSON;
   `known_issues.yml` with a tab, a duplicate key or a list of strings.
   - The run never crashes and never treats the file as empty.
   - A corrupt baseline is never served, and the run is red (`ledger_mismatch`).
   - A corrupt `health_state.json` voids every acknowledgement (`ack_invalid`). Afterwards only
     an acknowledgement made after the recovery counts.
   - A corrupt `known_issues.yml` gives `ack_invalid` and no acknowledgement.

   Pinned by `test_corrupt_baselines_are_never_served` (Task 1), `test_a_corrupt_baseline_is_loud`
   (Task 2), `test_malformed_known_issues`, `test_a_corrupt_health_state_voids_every_acknowledgement`
   and `test_recovery_after_a_corrupt_state` (Task 4), and
   `test_a_corrupt_health_state_needs_a_new_acknowledgement` (Task 8).
3. **Hostile or huge text from a source:** a unit or a reason detail holding Markdown, HTML,
   backticks, `|`, newlines, control characters, a `javascript:` URL or 10,000 characters.
   - `HEALTH.md` escapes it, so it can never add a heading, a link, a table cell or an image.
   - Every stored text keeps its cap: reasons 300, items 300, samples 200, `final_url` and
     `error` 300.

   Pinned by `test_health_md_escapes_hostile_text` and `test_diagnostics_are_capped_and_redacted`
   (Task 7).
4. **A run that is cut off or repeated:** the process dies half way through writing `out/`; the
   same `out/` is given twice; `out/` already holds old files.
   - No final file is ever partly written: each is written to a temporary name and renamed.
   - `manifest.json` is written last, so an interrupted artifact has none, and Plan 5's publish
     job refuses it.
   - A `--out` that is not empty is refused (exit 2), so no stale file reaches the manifest.

   Pinned by `test_an_interrupted_write_leaves_no_manifest` and `test_out_must_be_empty` (Task 8).
5. **Clocks and timestamps:** a naive or date-only timestamp in `known_issues.yml`, an
   acknowledgement 5 minutes or 2 days in the future, the exact expiry instant, a `--now`
   without a time zone, a `--now` an hour ahead of the machine clock.
   - Naive and date-only timestamps are invalid. A future acknowledgement has no effect yet,
     and one more than a day ahead is invalid.
   - An acknowledgement ends at its exact `expires_at`.
   - `--now` must carry a time zone (exit 2).
   - `generated_at` more than 10 minutes ahead of the machine clock fails validation, so it is
     never published.

   Pinned by `test_acknowledgement_validity` (Task 4), `test_timestamps_ahead_of_the_clock_fail`
   (Task 7) and `test_now_needs_a_time_zone` (Task 8).

**Known limits, by design.** Each is visible:
- **Reports, not repairs (P91).** When A-WEB's 2026 list is replaced by its 2027 list on 2
  January, the December claims that are no longer listed become a coverage gap. The gap is kept
  in `baseline.json` and reported (`coverage_gap`) on every run until its claims are listed again
  or their dates leave the window (an old year's dates leave it on 1 February). It is never
  served as evidence. Whether other sources list those elections is not checked. A gap carried
  across a registry change is compared through its old IDs, so it may last until its dates
  leave the window.
- **One registry per baseline (P93).** A commit that changes `places.yaml`, `institutions.yaml`
  or `subdivisions.yaml` makes every baseline unservable until the next promotion. The drop
  checks still run against it, and every source says so (`count_change` "baseline.json is from
  another registry version; it is never served"). A source whose candidate fails, or drops
  without an explanation, that day is `unavailable` rather than served from a baseline whose
  stored IDs may be stale. A drop that the registry change itself caused needs an
  `accept_drop`; the README asks for an offline run before such a commit.
- **Units are compared by count, not content.** A shift of 10% of a source's rows into an ignored
  reason passes the drop checks (R1 catches shifts of more than half). The per-reason counts are
  in `HEALTH.md`.
- **A disappeared event is found only through `source_event_id`** (ElectionGuide, IPU), and only
  through the candidate's claims. An event whose unit becomes unparsed counts as disappeared,
  and the unparsed unit is also an attention item.
- **The feed leaves out what the extension cannot show** (P85, P86): cards outside the window,
  before-window items and listings, and possible matches to children not in the feed. The run
  artifact keeps the full lists (`attention_full.json`, `dispositions.json`).
- **Parsing is measured, not bounded.** Each source's `parse_ms` is recorded. The whole scrape
  has no end-to-end deadline until Plan 5 checks the measured times (R10).

## Spec corrections

These were found while measuring the fixtures and while reconciling the spec with the code of
Plans 1–3.
- **Semantic decisions** change what the feed says, what a run reports, or how a run is judged:
  P84–P88, P90–P95, P97, P100–P103 and P105. They need the user's approval before Task 1 starts.
- **The other corrections** (P83, P89, P96, P98, P99, P104) refine names, layout and vocabulary.

Every "Measured" value is on the fixtures at `FIXTURE_NOW`, by the prototype named.

| ID | Spec says | This plan does | Why / alternative |
|---|---|---|---|
| P83 (interfaces) | §4 layers: `__main__`; `feed \| publish \| validate`; `merge`; `health \| snapshots \| ledger`; … | **A new `pipeline` layer** sits between `__main__` and `feed \| publish \| validate`. **`health \| snapshots`** sit above `ledger \| runner` (Plan 2 put `runner` beside `ledger`). What `health` and `snapshots` share (`DropAcceptance`, `SnapshotHealth`, the reason levels and stages, `SOURCE_NAMES`) lives in `model`. `short_id`, `canonical_json` and `SOURCE_ORDER` move to `model`, and `merge.identity` re-exports the two it had | The run needs one place that calls every stage. In `__main__` it could not be imported by tests without the CLI. `snapshots` reads `ledger` reports, and `health` reads `snapshots`' output only through `model` records. Alternative: everything in `__main__` |
| P84 (semantic; R17, R26) | §5.3: a child holds `place_id`, `country`, `country_code`, every resolved field and its claims. §5.4: the card. R17: serialise every merge record | **The feed carries what the extension shows or checks.** A child leaves out the fields that are part of its card's key and so always equal the card's: `place_id`, `country`, `country_code`, `level`, `date`, `end_date`, `date_precision`, `date_meaning`, `date_status`, `status`. A child source is the 12 fields of §5.3 plus `date_precision`, `date_meaning`, `date_status` and `status_claim`, never the whole claim (review: so a reader can tell which source says postponed, tentative or a voting period, and what a provisional source changed; **decided by the user, 2026-10-20**). A card's `umbrellas` are `{name, link, office_label, date_text, children}`, where `children` are the card's child ids that umbrella covers (R24). Listings and bibliographies carry `{name, link}` | Measured (`feed1.py`, `feed2.py`, `feed3.py`, `bytes3.py`): with every field of §5.3 the fixture feed is about 406 KB; revision 1's shape is 361,114 bytes compact (months 259,295; attention items 73,871; source health 19,088; undated 8,070), 23,720 gzipped. The three per-source fields add 20,728 bytes (343 gzipped; `status_claim` alone 5,506), and with P85's counts the feed is **393,152 bytes**, 24,260 gzipped. Serialising Plan 3's records as they stand gives about 1.09 MB (R26). **Cost:** an unregistered place's child shows its card's raw country name, not its own claims' spelling. Alternatives: revision 1's child source, without the three fields (the popup cannot say which source disagrees on status); `status_claim` alone; §5.3 in full (+45 KB); a leaner shape that omits false, null and empty values (284,710 bytes, but every reader must supply the defaults) |
| P85 (semantic) | §5.5: items reference only `child_id`s and `undated_id`s "which are always serialised". §5.7: `months`, `undated`, `attention_items` | **Only in-window cards are serialised.** Items whose relevance is `before_window` are left out (§5.5 already says so). An undated listing is serialised exactly when its item is. **Possible matches** (on children, listings and items) keep only the ids of children in the feed, so no reference dangles, and **`possible_matches_outside`** counts the ones left out, so "no candidate" and "a candidate outside the window" differ. The count is of distinct ids, taken before the filter, and an item whose every candidate is outside keeps its kind and reason (review; **decided by the user, 2026-10-20**) | Measured: 100 of 742 cards; 36 of 67 merge items; 15 of the 16 possible matches of those 36 items, and the children's matches that leave the window, name children outside it. The count adds 11,310 bytes (179 gzipped; `bytes3.py`). Alternatives: no count; serialise every card (all 742; the extension shows only the window), which makes `months` 1,331,826 bytes instead of 259,294 (`bytes2.py`) |
| P86 (semantic; R17 vs R26) | R17: `elections.json` serialises "attention items and dispositions" | **Dispositions and `merge_ids` are audit data and go to the run artifact:** `dispositions.json` (every disposition) and `attention_full.json` (every item, uncapped, with `merge_ids`). The feed's items have no `merge_ids` | The 1335 dispositions are 143,626 bytes that no reader shows (`bytes2.py`). The conservation audit already ran on them inside `merge`. Alternative: R17's literal text |
| P87 (semantic; R17, R20) | §5.5 cap: "`in_or_after_window` first (by date), then `unknown`". R20: one list "sorted by `item_id`, before the cap" | **`AttentionItem` gains `date`** (the start of its claims' day or month spans, the earliest one; None for year-only claims and for units without a dated claim). **The full list** (`attention_full.json`) is sorted by `item_id`. **The feed's list** is the first 500 of the full list in cap order: relevance (`in_or_after_window` before `unknown`), then `date` (None last), then `item_id`. `attention_truncated` is the number left out | The cap needs a date, and Plan 3's items had none. Ties need a total order. Measured: 157 relevant items (126 `in_or_after_window`, 31 `unknown`), well under the cap. Alternative: no date, cap by `item_id` |
| P88 (semantic; R20, R16) | §5.5 unit kinds; §9.3 provisional changes and disappeared units | **Unit items** come from the *served* snapshot: each relevant `partial` or `unparsed` unit is a `partial_unit` or `unparsed_unit` item. **A non-promoted candidate's** relevant `partial`/`unparsed` units on fully parsed pages, whose text no served unit has, are `provisional_change` items. **Each disappeared event** is a `disappeared_unit` item. Texts, links, ids and dates are in Task 3. **A unit item is acknowledged by its source and exact text** (`unit_text`), never by its id (R16). The text compared is the unit's full `collapse_ws` text (`AttentionItem.unit_text`, never cut), not the 300-character display `text` (review P4-04); units whose full texts are equal share an acknowledgement. `unparsed_relevant` and `partial_relevant` are acknowledged only this way, when every relevant unit of that kind is covered | A unit has no claim, so the merge cannot see it. An acknowledgement keyed by text follows the content: reordering rows never moves it, and a changed inherited country reopens it. No fixture unit is longer than 187 characters (`units3.py`), so the cut changes nothing today. Alternative: acknowledge by `unit_id`, which reordering breaks |
| P89 (interfaces) | §9.3 "the same year/page scope"; §9.6 `scope {stage, year, page}` | **`PageRequest` gains `scope`** (None = the key) and **`link`** (the page a reader opens; None = the URL). NDI's chain pages share the scope `"pages"`; Wikipedia's link is the article, EISA's year tables link to its calendar page. **`Reason` gains `page` and `year`**, set by `coverage_reasons`, `missing_pages`, EISA's year notes and the drop checks. **A reason's stage** comes from its code (`REASON_STAGE`, Task 1). **Adapters** declare `parser_version = "2.0"` | NDI's items move between pages as time passes, so per-page drop checks there are noise. A Wikipedia API URL is not a page a reader can open. An acknowledgement needs an exact scope to match. Alternative: derive scopes from detail texts |
| P90 (semantic; R1) | §9.3: a drop compares `units_seen` per scope; `sudden_drop` > 50% below the baseline, `cumulative_drop` > 50% below the 30-day high-water mark | **Both checks compare two numbers per scope: units seen, and usable claims** (claims of that scope's units). A drop is `candidate × 2 < reference` for either number. One reason per scope: `sudden_drop` when the baseline rule fires, else `cumulative_drop`. **Explained, so no drop:** every candidate page of the scope is `valid_empty`, or the scope's year changed. Both give the info reason `count_change`, and both, like an accepted drop, **restart the scope's history** (review P4-02: an old year's or a full list's high-water mark would quarantine the next healthy run). A drop reason gives both of the candidate's counts | R1: IPU rows moving from dated to `no_expected_date` at equal totals, and a table of only ignored rows, lose claims while units hold. Exactly half is not a drop ("more than 50%"). Cost: a decline across a year change is measured from the new year's first count. Alternatives: units only, which misses R1's cases; history kept per year |
| P91 (semantic; R2) | R2: A-WEB's previous-year claims that still overlap the window "stay as fallback evidence, or the coverage limit is reported" | **Reported for as long as it lasts** (**decided by the user, 2026-10-20**). When a promotion changes a scope's year, the dated baseline claims of that scope that overlap the window and that the candidate no longer lists (`same_listing`, Task 2) become a **coverage gap**: a record in `baseline.json` (Task 1's `CoverageGap`) that holds those claims, unstamped and never served. Every run reports each gap that still has claims in the window not listed again, as `coverage_gap` "`<scope>: the <old> list was replaced by <new>; in-window claims no longer listed: <n>`". A gap only shrinks, and it ends when none of its claims is left: each is listed again or dated outside the window. The candidate is promoted. **Acknowledgement:** an ordinary one (scope `{stage: parse, year: <new>, page: <scope>}`) mutes the gap's effect on the verdict while it is in effect, and the gap stays listed, as acknowledged. The reason carries the gap's `since`, and an entry acknowledged before it never covers it, so a new gap never inherits an older acknowledgement (Task 4) | Keeping old claims as fallback evidence means serving a mixed snapshot, which §9.3 forbids ("the baseline is never partly replaced"). A new baseline does not show that the lost coverage came back, and an alert sent is no evidence that anyone reviewed the gap (the user's decision). Cost: the warning on every run until 1 February for an old year's dates, and an acknowledgement renewed every 14 days to keep the verdict green; Plan 5 may group repeated notifications. Whether other sources still list those claims is not checked. Alternatives: the warning on the promoting run only (revision 2); a mixed served snapshot for one scope |
| P92 (semantic; R14) | R14: a never-published future year (`not_published_yet`) is told apart from one that an earlier snapshot had and that has now disappeared, "which is an error" | **A `not_published_yet` reason for a year that the baseline has an `ok` or `valid_empty` page of** becomes `required_year_missing` "`<year> was published before and is now missing`", and the candidate is invalid | Plan 2c left the comparison to the snapshot, which alone has both runs. Alternative: keep the info reason, which hides a vanished table |
| P93 (semantic; Plan 1 C9) | C9: define how registries are versioned before the first save, and how stored IDs are re-resolved when a name is registered or a chamber renamed; "never a silent new identity" | **Each snapshot records `registry_version`**, the SHA-256 of the three runtime registry files (Task 1). **A baseline of another version is never served**, but it stays **comparable**: the drop checks compare its counts, and its history continues. Beside it, a valid candidate with no unexplained drop is promoted, and a candidate that is invalid or has an unexplained drop is **`unavailable`** "`baseline.json is from another registry version`": nothing is served or merged, the baseline is kept, the drop reason is listed and `candidate.json` keeps the candidate for diagnosis. Every run adds the info reason `count_change` "`baseline.json is from another registry version; it is never served`". A later candidate is promoted once it passes the drop checks or an `accept_drop` explains its drop (**decided by the user, 2026-10-20**). Stored IDs are never re-resolved | Re-resolving an institution needs the unit's text and the adapter's context, which a snapshot does not keep. A stale ID would be a silent new identity. Whether the old counts can be compared and whether the old claims can be served are separate questions: a registry change can change how many claims a parser makes, and that change must be reviewed, not passed. Cost: on the first run after a registry change, every source whose fetch fails or whose counts drop is `unavailable`, and a drop that the change caused needs an `accept_drop`; the README asks for an offline run before such a commit (Known limits). Alternatives: revision 1's rule (no drop checks after a registry change, and no sign of it); revision 2's (a dropped candidate promoted with its drop warning); re-parse from stored raw pages (Plan 5 keeps only invalid pages' bodies) |
| P94 (semantic; Plan 1 C20) | C20: loaders treat a `RecordError` "as a corrupt record, never as an empty one" | **`baseline.json`** that cannot be read (not JSON, a missing key, a non-list, a `RecordError`, a ledger problem, or a `snapshot_id` that its own units and claims do not give) is treated as absent for acceptance, so it is never served, and gives `ledger_mismatch` "`baseline.json is corrupt: <problem>`" (never acknowledgeable). A valid candidate is then promoted as on a first run. **`health_state.json`** that cannot be read voids every acknowledgement of that source and gives `ack_invalid`; the next state written records `reset_at`, and only acknowledgements made after it count again (review P4-05). **`known_issues.yml`** that cannot be read gives `ack_invalid`, and no entry has an effect. `candidate.json` is written but never read | Each committed file is either trusted fully or not at all, and the run says so. Alternatives: void acknowledgements for the corrupt run only, which lets an old acknowledgement silence a recurrence whose history was lost; fail the run, which stops every source for one file |
| P95 (semantic; §9.6, R16) | §9.6: entries with `source`, `reason`, `scope`, `explanation`, `owner`, `acknowledged_at`, `expires_at`; `accept_drop` adds `accept_units_seen_min` | **The entry kinds:** a reason acknowledgement (`scope`), a unit acknowledgement (`unit_text` instead of `scope`, reason `unparsed_relevant` or `partial_relevant`), and `accept_drop` (`scope`, reason `sudden_drop` or `cumulative_drop`, `accept_units_seen_min` and `accept_claims_min`; the candidate must reach both floors, review P4-03). **Validity** is Task 4's table. **Recurrence** is tracked per entry key in `health_state.json`: only the keys that valid entries name are kept | §9.6 needs an exact scope, and R16 an exact text. Keeping only named keys bounds the state file. A floor on units alone would let an approval for 40 units with 40 claims accept 40 units with none. Cost: muting Wikipedia's 111 units takes 111 entries, renewed at least every 14 days. Alternative: track every reason ever seen; acknowledge a whole page's units by scope, which would also mute new ones |
| P96 (vocabulary) | §5.6 download `outcome`: ok, http_error, timeout, tls_error, dns_error, challenge_page, api_error, layout_not_recognised, not_published_yet, deadline | **The outcome enum adds `fetch_failed` and `worker_failed`** (both exist since Plans 1–2). **`parse.parse_ms`** is the measured parse time (Plan 2a's parsing bound). **`final_url` and `error` are capped at 300 characters** (L127d) | The runner and `fetch` produce both outcomes. Alternative: fold them into `http_error` |
| P97 (semantic; SC4) | §5.4 "one entry per source name" | **The source names are v1's** where v1 had them: "ElectionGuide", "OSCE/ODIHR", "Wikipedia", "A-WEB", "IPU", "Carter Center", "EEAS"; the new sources are "NDI" and "EISA" (`model.SOURCE_NAMES`) | v1.0.2 shows the names, and users' pins and searches use them. Alternative: new names |
| P98 (interfaces) | §4: `--live \| --offline DIR, --now ISO, --out DIR, --dry-run` | **The CLI:** `--live \| --offline DIR`, `--now ISO` (with a time zone), `--out DIR` (empty or new), and the new **`--repo DIR`** (default `.`), where the baselines, `health_state.json`, `known_issues.yml` and the served `elections.json` are read. `--dry-run` is Plan 5's. **Exit codes:** 0 when a complete artifact was written, whatever the verdict; 1 when the run failed before it could write one; 2 for a usage error | Tests and the workflow need to point the run at a repository that is not the code checkout. Alternative: read from the working directory |
| P99 (interfaces) | §11.2: `out/` holds the candidate generation, `verdict.json` and `manifest.json` | **The `out/` layout** is Task 8's table: the repository files (`elections.json`, `status.json`, `HEALTH.md`, `data/sources/<source>/{baseline,candidate,health_state}.json`), then the artifact-only files (`verdict.json`, `attention_full.json`, `dispositions.json`, `rejected/`), and `manifest.json` last. On a failed validation, `elections.json` and `data/sources/` are not written | The publish job must be able to commit exactly the repository files (§11.6). Alternative: one flat directory |
| P100 (semantic) | §13.4: the end-to-end run is "at `--now 2026-10-16T00:00:00Z`" | **The end-to-end run is at `--now 2026-10-19T12:00:00Z`** | The NDI and EISA fixtures were captured on 2026-10-19 (the latest at 08:57:53Z). At 16 October their fetch times would be in the future, and §11.3 rejects timestamps more than 10 minutes ahead. The window (September–January) and the expected contests are the same. Alternative: re-capture NDI and EISA (impossible: the pages have changed) |
| P101 (semantic; SC2) | SC2: "every record in the 2026-10-16 production feed maps to exactly one v2 record" | **A v1 record maps to a v2 card** whose place is `PlaceRegistry.resolve(v1 country)` and whose span holds the v1 date. Several such cards narrow to one by the v1 link, then by label (Task 9). **The card must hold a witness** (review P4-07): a child or an umbrella whose folded `office_label` contains, or is contained in, the folded v1 `type`; a record without one is `unwitnessed`. **Exceptions** (`unmapped`, `ambiguous`, `unwitnessed`) and **merged groups** (several v1 records on one card) are listed in `legacy-mapping-exceptions.yaml`, and the test requires both lists to be exact | Measured (`sc2b.py`): 44 of 50 map to exactly one card; 5 EEAS "2026-10-01" fake dates map to none; the US 3 Nov midterm record maps to two (governors, and the "midterm elections" grouping). Merged groups: Brazil 4 Oct Chamber + Senate (`54b356d5b5ea`), Brazil 25 Oct Presidency + A-WEB 2nd round (`4b35f9d2401c`). All 44 have a witness (`sc2w4.py`): 42 a child (15 of them also a link only that card has), 2 an umbrella (Philippines 14 Sep "Bangsamoro Parliament", Wikipedia; Brazil 25 Oct "2026 General Elections (2nd round)", A-WEB). v1 has no structured office, round or jurisdiction, and its links are often a calendar page that many cards share, so the label is the witness. Alternative: child level, which v1's multi-office records cannot match |
| P102 (semantic; R21) | Plan 2c: `unnamed_parts` gives false alarms on joint tickets and "National and Provincial" | **A joint ticket is one office:** `_DEPUTY_OF` also reads the adjectives (presidential, gubernatorial, mayoral), and `unnamed_parts` returns `[]` for a two-part joint ticket, as `split_offices` does. **"National and Provincial" stays an alarm**, because it is true | Measured (`r21c.py`): no fixture unit changes. Alternative: silence both, which hides the lost national part of South Africa's label |
| P103 (semantic; NM-T04) | §5.7: `content_id` is SHA-256 over months, undated, items and served snapshot ids; "two generations with the same evidence share it" | **`content_id` leaves out every `fetched_at`.** It hashes the canonical JSON of `{months, undated, attention_items, snapshots}` after removing each `fetched_at` key, where `snapshots` is `[[source, served_snapshot_id], …]` in `SOURCE_ORDER` | A re-fetch of unchanged pages changes every child source's `fetched_at`, so the spec's hash would never repeat. The byte digest (`serving_feed_sha256`) still tells publications apart. Alternative: the spec's hash, which never matches across runs |
| P104 (vocabulary) | §9.4 codes; §11.6 "validation failed" | **`ReasonCode` gains the errors `merge_failed` and `validation_failed`**, both never acknowledgeable. **Run-level reasons** (`merge_failed`, `validation_failed`, `attention_truncated`, `ack_invalid` for `known_issues.yml`) belong to no source and are listed in `run.reasons` and `status.json` | §11.6 needs a reason for a blocked generation, and R18 a code for a merge failure. Alternative: report them as text only |
| P105 (semantic; §9.3) | §9.3: provisional changes come from fully parsed pages, "none on `ledger_mismatch`"; compared "by `source_event_id` … otherwise by identity key (§10.1) within the same year" | **No provisional change on `ledger_mismatch` or `discovery_mismatch`.** **A candidate claim is unchanged** when a served claim has the same content: every field except its position (`unit_id`, `claim_id`), its formatting (`link`, `place_raw`, `date_text`) and its stamped provenance, with names compared through `norm_name` (Task 2's `claim_content`). A `source_event_id` or a key only finds a related claim; it never makes two claims equal (review P4-01). Everything else is provisional. **Still listed** (P91's count) is correlation: the same `source_event_id`, or without one the same key (place, institution or office class, folded jurisdiction, kind, round) | §9.3 compares only date, end date and status claim, so a corrected office, level, place, date status or rescheduling on a fully parsed page would stay hidden while the source is on fallback or quarantined; the merge reads most of these fields (§10.1). `snapshots` sits below `merge` and cannot use §10.1's matcher. A page that fails its independent count cannot be trusted to have been read correctly. Cost: a change the merge does not read (`date_meaning`, `date_status`) still makes a provisional source entry, which P84's per-source fields explain. Alternatives: §9.3's three fields; §10.1's full identity, which needs the merge layer |

**Also settled (no spec change):**
- **A candidate with `coverage_gap` is promoted.** Its layout is recognised and its paging
  complete, so §9.3's first row applies; the warning shows on the source (the open question from
  Plan 2b's handover).
- **What "fully parsed pages" means:** pages whose outcome is `ok` or `valid_empty`.
- **Exactly 7 days of fallback is fresh,** as in Plan 3 (`fallback_stale` from more than 7 days).
- **A first run has `comparable` false** and `baseline_units_seen` null.
- **`status.json` keeps each reason's scope** (review): its `reasons` carry `page`, `year` and
  `acknowledged`, and its `acknowledged` entries carry `stage`, `year` and `page`, so a reader
  can tell an acknowledged failure on one page from the same code on another (Task 7).
- **`status.json` passes `validate_status` before the artifact is written** (review P4-06,
  Task 8).
- **`jsonschema` has no type information:** `pyproject.toml` gets a mypy override
  (`ignore_missing_imports` for `jsonschema` and `jsonschema.*`).
- **N-4 (Plan 2a):** section keys and other page text in reason details are escaped where
  `HEALTH.md` renders them (Task 7), and the feed carries them as JSON strings.
- **F-10 (Plan 2a):** each run's working directory is a fresh `tempfile.mkdtemp`, removed at the
  end (Task 8).
- **The over-budget feed** is a test failure on the fixtures (R26) and a line in `HEALTH.md` for
  live runs. It is not a reason code; Plan 5 decides whether it should be.

## Review record

**Status:** "planned" becomes "verified" only when the SDD ledger records the task's commit, with
the named test passing and its mutation killed.

| ID | Kind | Ruling | Task · test | Status |
|---|---|---|---|---|
| C9 (Plan 1) | Requirement (stored IDs) | P93 | T1 `test_registry_version`; T2 `test_registry_change`; T8 `test_a_registry_change_never_serves_the_old_baseline` | planned |
| C20 (Plan 1), Plan 2a "Loaders" | Requirement | P94; `ledger.record_problems` on load | T1 `test_corrupt_baselines_are_never_served`; T2 `test_a_corrupt_baseline_is_loud` | planned |
| C1 (Plan 1), Plan 2a "Trust error" | Requirement | Task 8 prints the message and records only `.variable` and the bundle's sources | T8 `test_trust_error_is_reported_without_its_message` | planned |
| Plan 2a "Caps" | Requirement (L127d) | P96 | T7 `test_diagnostics_are_capped_and_redacted` | planned |
| Plan 2a "Source outcomes as reasons" | Requirement | `deadline`/`scrape_deadline` → `deadline`; `worker_failed` → `worker_failed`; both make the candidate invalid | T2 `test_invalid_candidates` | planned |
| Plan 2a "Parsing bound" | Requirement | P96 `parse_ms`; no end-to-end deadline is claimed (Known limits) | T8 `test_parse_time_is_recorded` | planned |
| Plan 2a "Attention items" | Requirement | P87, P88 | T3 `test_unit_items_on_the_fixtures` (121; Wikipedia 111: local-2026 61, local-2027 48, national-2026 2) | planned |
| Plan 2a "Expected file" | Requirement | §13.2 | T9 `test_expected_file` | planned |
| R1 (Plan 2b) | Requirement | P90 | T2 `test_a_shift_into_ignored_reasons_is_a_warning`, `test_claims_falling_while_units_hold_is_a_warning` | planned |
| R2 (Plan 2b) | Requirement | P91 | T1 `test_coverage_gaps_round_trip`; T2 `test_aweb_rollover_keeps_december_events` (the limit is reported while it lasts); T4 `test_an_acknowledgement_never_covers_a_later_gap`; T5 `test_acknowledgements_change_only_the_verdict` (the gap rows) | planned |
| R11 (Plan 2b) | Requirement | Coverage gaps and ignored reasons in source health and `HEALTH.md` | T5 `test_health_lists_coverage_gaps_and_ignored_reasons`; T7 `test_health_md_sections` | planned |
| R14 (Plan 2c) | Requirement | P92; an invalid January candidate falls back to December's baseline | T2 `test_eisa_january_without_a_new_table_keeps_december`, `test_a_disappeared_year_table_is_an_error` | planned |
| R15 (Plan 2c) | Requirement | Pages per scope; `count_change` for a chain of another length; `pagination_incomplete` counted | T5 `test_health_reports_chain_length_and_missing_pages` | planned |
| R16 (Plan 2c) | Requirement | P88, P95 | T4 `test_a_no_new_date_unit_can_be_acknowledged_until_it_changes`, `test_an_inherited_country_change_reopens_an_acknowledgement` | planned |
| R5 (Plan 3, legacy part) | Requirement | The legacy fields come from the merge's child status and span, which P67 already keeps observations out of | T6 `test_unknown_meaning_observation_never_makes_held_or_ongoing` (legacy-feed case) | planned |
| R17 (Plan 3) | Requirement | P84–P87 | T6 `test_feed_serialises_every_merge_record`, `test_attention_cap_sets_attention_truncated` | planned |
| R18 (Plan 3), S3-T16 | Requirement | `ValueError` from the merge → `merge_failed` (detail cut to 300; full text in `rejected/merge_error.txt`); `status.json` `validation_failed`; the served feed stays | T8 `test_merge_error_blocks_publishing` | planned |
| R19 (Plan 3), V2-T01 | Requirement | Task 2's stamping and provisional rules (P105) | T2 `test_an_unchanged_partial_claim_is_not_provisional`, `test_stamped_fallback_claims_reach_the_merge` | planned |
| R20 (Plan 3) | Requirement | P87, P88 | T6 `test_unit_and_claim_attention_items_share_one_list` | planned |
| R21 (Plan 3) | Requirement | P102 | T3 `test_joint_ticket_is_not_unnamed_parts` | planned |
| R23 (Plan 3) | Requirement | Appendix B in the serialised feed | T9 `test_appendix_b_in_the_feed` | planned |
| R24 (Plan 3) | Requirement | P84's child fields and umbrella children; the README note on the two legacy-status changes | T6 `test_feed_serialises_rescheduling_and_provisional_date`, `test_umbrella_link_targets_children_in_the_feed`; T9 README (final review) | planned |
| R26 (Plan 3) | User note (extension weight) | P84–P86; a budget of 524,288 bytes (the user's decision) | T6 `test_feed_size_is_within_the_budget`; T9 `test_feed_size_on_the_fixtures` (bytes and budget in `HEALTH.md` and `verdict.json`) | planned; Plan 5 part (popup) open |
| S4-T01, V2-T04 | Spec acceptance | 100 → 40 → timeout never makes a partial baseline; 99 outcomes for 100 units is never promoted | T2 `test_invalid_candidates`, `test_partial_baselines_are_impossible` | planned |
| S4-T02 | Spec acceptance | Bootstrap and justified drops | T2 `test_first_run`, `test_drops` | planned |
| S4-T03 | Spec acceptance | A middle page that fails, repeats or is a challenge page | T2 `test_invalid_candidates` (rows `p2 timeout`, `p2 challenge`, `p2 repeat`) | planned |
| S4-T04, NM-T02 | Spec acceptance | A partial scrape with a correction | T2 `test_provisional_changes` | planned |
| S4-T05 | Spec acceptance | Validation failure does not publish | T8 `test_validation_failure_writes_no_feed` | planned (the commit part is Plan 5's) |
| S4-T06 | Spec acceptance | Fallback schema and parser-version honesty | T2 `test_parser_version_change`; T7 `test_feed_schema` | planned |
| S4-T07 | Spec acceptance | Interrupted writes | T8 `test_an_interrupted_write_leaves_no_manifest` | planned |
| S4-T10 (deadline part) | Spec acceptance | A source cut at its deadline | T8 `test_a_deadline_is_a_reason` | planned; setup/test/push parts are Plan 5's |
| S4-T14, NM-T07, V2-T06 | Spec acceptance | Acknowledgement expiry, scope and recurrence; only `accept_drop` changes acceptance | T4 `test_acknowledgement_validity`, `test_acknowledgement_scope`, `test_recurrence_voids_an_acknowledgement`; T5 `test_acknowledgements_change_only_the_verdict` | planned |
| S4-T15 | Spec acceptance | Malformed acknowledgements; global gates cannot be muted | T4 `test_malformed_known_issues`, `test_never_acknowledgeable` | planned |
| S4-T16 | Spec acceptance | Match-diagnostic limits; the frozen OSCE column shift is caught structurally | T5 `test_match_diagnostic`, `test_match_diagnostic_on_the_fixtures`, `test_osce_column_shift_is_an_error` | planned |
| S4-T17 | Spec acceptance | The ledger with multi-output units | — | satisfied by Plan 2a (`tests/unit/test_ledger.py`) |
| S4-T19 | Spec acceptance | Escaped and redacted diagnostics | T7 `test_health_md_escapes_hostile_text`, `test_diagnostics_are_capped_and_redacted` | planned |
| NM-T01 | Spec acceptance | 100 → 60 → 36 gives `cumulative_drop`; `accept_drop`; the 4-cell row and the cross-count are Plan 2's | T2 `test_drops` | planned |
| NM-T04 | Spec acceptance (Plan 4 part) | P103 | T6 `test_same_evidence_shares_a_content_id`; T7 `test_status_links_the_feed_by_its_bytes` | planned; the served check is Plan 5's |
| S1-T4, S1-T6 | Spec acceptance | A correction plus one bad row; honest ageing, including a first-run failure | T2 `test_provisional_changes`, `test_first_run`, `test_fallback_age_is_never_refreshed` | planned |
| SC1 | Success criterion | The expected file | T9 `test_expected_file` | planned |
| SC2 | Success criterion | P101 | T9 `test_v1_records_map_to_v2_cards` | planned |
| §11.3 | Spec | Every check | T7 `test_validate` | planned |
| P4-01 (review) | Finding | P105 | T2 `test_unchanged_compares_the_whole_claim`, `test_aweb_rollover_keeps_december_events` | planned |
| P4-02 (review) | Finding | P90 | T2 `test_a_new_list_restarts_the_history` | planned |
| P4-03 (review) | Finding | P95 | T2 `test_drops` (rows n–r); T4 `test_malformed_known_issues`, `test_drop_acceptances` | planned |
| P4-04 (review) | Finding | P88 | T3 `test_unit_items_carry_the_full_text`; T4 `test_unit_acknowledgement_uses_the_full_text` | planned |
| P4-05 (review) | Finding | P94 | T4 `test_recovery_after_a_corrupt_state`; T8 `test_a_corrupt_health_state_needs_a_new_acknowledgement` | planned |
| P4-06 (review) | Finding | Task 8 step 8 (the status gate) | T8 `test_an_invalid_status_blocks_publishing`, `test_an_invalid_failure_status_writes_nothing` | planned |
| P4-07 (review) | Finding | P101 | T9 `test_v1_records_map_to_v2_cards`, `test_sc2_needs_a_witness` | planned |
| Review: status scope | Finding | "Also settled" | T7 `test_status_lists_reasons_and_sources` | planned |
| Review: manifest determinism | Finding | A new run id changes `status.json` and `manifest.json` | T8 `test_the_same_input_gives_the_same_files` | planned |
| Review: P84, P85, P91, P93, budget | User decisions (2026-10-20) | P84: all three per-source fields; P85: the count; P91: a gap kept while it lasts; P93: `unavailable` on a drop; a budget of 524,288 bytes | T2 `test_aweb_rollover_keeps_december_events`, `test_registry_change`; T4 `test_an_acknowledgement_never_covers_a_later_gap`; T6 `test_possible_matches_never_dangle`, `test_feed_size_is_within_the_budget`; T8 `test_a_registry_change_never_serves_the_old_baseline`; T9 `test_feed_size_on_the_fixtures` | planned |
| I2 (Plan 3 final review) | A ruling for the user's veto | Built at `6ba511b`; no Plan 4 task depends on it | — | open (the user's) |
| M3 (Plan 3 final review) | Finding, parked by the user | R37 | — | open (R37) |
| NDI marker (Plan 2c) | User decision: approved in principle | R36 | — | open (R36) |
| P83–P105 | Decisions (the semantic ones need approval) | As in "Spec corrections" | Each task's tests, as named there | planned |

## How to execute this plan

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Do not create worktrees, do not switch branches, do not commit to `main`.
  - Keep the shell in the worktree. Use `( cd … && … )` subshells for anything elsewhere.
- **Style:** this plan pins names, signatures, rules, messages and test values; you write the
  bodies. Private helpers are yours. If a rule is ambiguous, stop and ask the controller. Never
  guess a value.
- **Measured values:** every fixture count in the tests was measured by the prototypes in
  `.scratch/plan4/proto/`. They run from the worktree root as
  `PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe .scratch/plan4/proto/<script>`.
  - `feed1.py` → `out1/A.json`–`D.json`: the fixture merge as the feed sees it (window, items,
    dangling matches) and four feed shapes with their bytes.
  - `feed2.py` → `out2/feed.json`: the planned shape (P84), unit items, and the snapshot sizes
    (1.62 MB compact for the nine sources, 1.93 MB at `indent=1`). `bytes2.py` → `bytes2.txt`:
    the dispositions (143,626 bytes) and every card serialised (1,331,826 bytes).
  - `units1.py`, `units2.py`: the 121 relevant unit items and Wikipedia's split.
  - `reasons1.py`: every source's coverage, notes, ledger report and expected severity.
  - `match1.py`: the match diagnostic (Task 4's table).
  - `sc2.py`, `sc2b.py` → `sc2b.txt`: SC2 (Task 9).
  - `r21.py`, `r21b.py`, `r21c.py` → `r21c.txt`: R21's probes and its fixture effect (none, over
    3452 units and claims).
  - `r21d.py` → `r21d.txt`: Task 3's R21 test rows under P102's rule.
  - `lean2.py`, `bytes1.py`: the leaner alternative of P84 and the per-field bytes.
  - `count1.py`: the children in the window by level (Task 9's expected file).
  - `health1.py` → `health1.txt`: page years, outcomes, notes and ignored reasons per source
    (Task 5).
  - `osce_shift.py` → `osce_shift.txt`: the OSCE column shift (Task 5).
  - `umb1.py` → `umb1.txt`: umbrella coverage of in-window cards (Task 6).
  - `e2e_window.py`, `e2e_ct.py` → `.txt`: every fixture parses identically at the end-to-end
    window, and the pages NDI and EISA ask for (Task 9).
  - Revision 2 (the review): `sc2w.py`, `sc2w2.py`, `sc2w3.py`, `sc2w4.py` → `.txt`: SC2's
    witnesses (Task 9); `units3.py` → `units3.txt`: unit text lengths (P88); `mk_feed3.py` →
    `feed3.py` → `out3/feed.json`, and `bytes3.py` → `bytes3.txt`: P84's per-source fields and
    P85's counts.
  - **Where a prototype differs from this plan, the plan wins.** The prototypes fill
    `source_health` with placeholder values of realistic size, use the source key in items, and
    stamp nothing. None of that changes a count. Expect the real fixture feed to be within a few
    kilobytes of 361,114 bytes, not equal to it.
  - **Prototypes confirm the values; the rules define them.** If a value cannot be explained by
    its input and the rule named next to it, stop and report it, even when a prototype agrees.
    Never change an expected value to match.
- **Per task:** follow the Implement-Review loop in the user's CLAUDE.md (at most 3 rounds):
  1. Pre-flight against the current source.
  2. Write the failing test.
  3. Implement.
  4. Run the four gates:
     - `.venv/Scripts/python.exe -m pytest -q`
     - `.venv/Scripts/mypy.exe`
     - `.venv/Scripts/ruff.exe check`
     - `.venv/Scripts/lint-imports.exe --config importlinter.ini`
  5. Run the mutation table.
  6. Commit.
- **Cost (an estimate by analogy with Plan 3, not a measurement):** nine tasks at one
  implementer and one reviewer each, about one fix round with its scoped re-review per task,
  and a final whole-branch review with one fix wave: about 30–40 agent runs, roughly
  USD 280–440, or two to three days of the USD 150 daily budget. Every task ends at a green
  commit, so a day can stop after any task.
- **Bounds:** one task at a time, never two in parallel; one reviewer per round, fresh each
  round; at most 3 fix rounds per task. If round 3 ends with a gate red, a Critical or Important
  finding open or a mutation alive, stop: commit nothing that is not green and report what is
  open. A 4th round needs the user's say-so. An AWS, Bedrock or budget error stops all work at
  the last green commit, with uncommitted work in a named stash. No merge and no push.
- **Mutations:** one per new test, in `.scratch/mutations/plan4-task-<N>.json`, in the format of
  `.scratch/mutate.py`.
  - Stage the task's files with `git add` first, and run with `PYTHONDONTWRITEBYTECODE=1`.
  - Choose mutations that fail fast. A loop that runs into `MUTATE_TIMEOUT_S` is a timeout, not a
    kill.
- **Handover:** after every task, record the commit, the Review record rows it verified and the
  next task in two files:
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-plan4-sdd-ledger.md` (new);
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-RESUME.md`.
- **Hook:** the Desktop PostToolUse hook runs `ruff check --fix` on each edited `.py`. Check
  `git diff --stat` for unrelated rewrites.
- **Runtime:** building the fixture results takes about 2.4 s, and the fixture merge about 0.2 s.
  `fixture_results()` and `fixture_claims()` are cached per test session. Task 9's end-to-end run
  is cached per test module (one run for all its tests).
- **Test helpers:** `tests/support/claims.py` (`mk`, `cl`, the presets, `NOW`),
  `tests/support/pages.py` (`result`, `raw_pages`, `unit`, `claim`, `Served`),
  `tests/support/fixture_claims.py` (`FIXTURE_NOW`, `fixture_results()`, `fixture_claims()`).
  Task 2 adds `tests/support/snapshots.py` (synthetic snapshots), Task 5 `tests/support/feed.py`
  (a first run over the fixtures), Task 8 `tests/support/repo.py` (offline inputs and the
  commit step), Task 9 `tests/support/appendix_b.py` (Plan 3's Appendix B rows, moved).

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `elections_calendar/model.py`, `tests/unit/test_model.py` | shared vocabulary (`short_id`, `canonical_json`, `stored_json`, `SOURCE_ORDER`, `SOURCE_NAMES`, levels, stages); `Reason.page`/`year`; `DropAcceptance`, `SnapshotHealth`; `AttentionItem.date`/`unit_id`/`unit_text` | 1, 2, 3 |
| `elections_calendar/merge/identity.py`, `merge/cards.py` | re-export `short_id` and `SOURCE_ORDER`; merge items get `date` | 1, 3 |
| `elections_calendar/sources/base.py`, the nine adapters | `PageRequest.scope`/`link`; reasons with page and year; `parser_version` | 1 |
| `elections_calendar/offices.py`, `tests/unit/test_offices.py` | R21 joint tickets | 3 |
| `elections_calendar/snapshots.py`, `tests/snapshots/` | snapshot records and loaders; `decide`; unit items | 1, 2, 3 |
| `tests/support/snapshots.py` | synthetic pages, snapshots and baselines | 2 |
| `tests/support/feed.py` | the first run over the fixtures, as the pipeline does it | 5 |
| `tests/support/repo.py` | `pages.json` builders and the commit step between runs | 8 |
| `elections_calendar/health.py`, `tests/health/` | `known_issues.yml`, `health_state.json`, acknowledgements, relevance reasons (4); match diagnostic, severity, verdict (5) | 4, 5 |
| `known_issues.yml` | the (empty) acknowledgement file, with its format in comments | 4 |
| `elections_calendar/feed.py`, `tests/feed/` | source health entries (5); the feed document, items and the cap (6); `status.json`, `HEALTH.md` (7) | 5, 6, 7 |
| `elections_calendar/publish.py`, `tests/feed/test_publish.py` | `content_id`, the feed bytes, atomic writes, the manifest | 6 |
| `schemas/feed-v2.schema.json`, `schemas/status-v1.schema.json`, `elections_calendar/validate.py`, `tests/feed/test_validate.py` | the schemas and §11.3 | 7 |
| `pyproject.toml` | the mypy override for `jsonschema` | 7 |
| `elections_calendar/runner.py` | `load_adapter` (public) | 8 |
| `elections_calendar/pipeline.py`, `elections_calendar/__main__.py`, `tests/pipeline/` | the run, offline and live; the CLI | 8 |
| `importlinter.ini` | the layers of P83 | 1, 8 |
| `tests/fixtures/feed/2026-10-16-ff30417.json`, `tests/fixtures/feed/PROVENANCE.md` | v1's production feed, byte for byte | 7 |
| `tests/fixtures/pages.json`, `tests/expected/2026-10-16.yaml`, `tests/expected/legacy-mapping-exceptions.yaml`, `tests/support/appendix_b.py`, `tests/pipeline/test_end_to_end.py` | the end-to-end run, SC1, SC2, Appendix B | 9 |
| `README.md` | the CLI, `out/`, `known_issues.yml`, the two legacy-status changes (R24) | 9 |

## Tasks

### Task 1: Shared vocabulary, page scopes and snapshot records (`model.py`, `sources/base.py`, `snapshots.py`; P83, P89, P91, P93, P94, P97, P104; C9, C20)

**Files:**
- Modify: `elections_calendar/model.py`, `elections_calendar/merge/identity.py`,
  `elections_calendar/sources/base.py`, the nine adapters in `elections_calendar/sources/`,
  `importlinter.ini`
- Create: `elections_calendar/snapshots.py`, `tests/snapshots/__init__.py`,
  `tests/snapshots/test_records.py`
- Test: `tests/unit/test_model.py`, `tests/unit/test_sources_base.py`; the adapter tests whose
  expected coverage reasons gain `page` and `year` (no other expected value changes)

**Interfaces:**
- Consumes: `InputUnit`, `Claim` and `Reason` with their `to_dict`/`from_dict`; `_utc_iso`,
  `_check_fields`, `RecordError`; `PageCoverage`, `ParseResult`, `RawPages`, `PageOutcome`;
  `FetchResult`, `FetchOutcome`, `redact_url`, `redact_text`; `ledger.record_problems`; `DEFAULT_PLACES`,
  `DEFAULT_INSTITUTIONS`, `DEFAULT_SUBDIVISIONS`.
- Produces in **`model.py`**:

```python
def short_id(parts: Iterable[str]) -> str            # moved unchanged from merge.identity
def canonical_json(value: object) -> bytes            # json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False), UTF-8
def stored_json(value: object) -> bytes               # json.dumps(value, ensure_ascii=False, indent=1) + "\n", UTF-8: committed files
SOURCE_ORDER: Final[tuple[str, ...]]                  # moved unchanged from merge.identity
SOURCE_NAMES: Final[dict[str, str]]                   # P97, in SOURCE_ORDER:
#   electionguide "ElectionGuide", osce "OSCE/ODIHR", wikipedia "Wikipedia", ndi "NDI",
#   aweb "A-WEB", eisa "EISA", ipu "IPU", carter "Carter Center", eeas "EEAS"
ReasonLevel = Literal["error", "warning", "info"]
Stage = Literal["fetch", "parse", "snapshot", "match", "run"]
REASON_LEVEL: Final[dict[ReasonCode, ReasonLevel]]    # spec §9.4, plus the codes below
REASON_STAGE: Final[dict[ReasonCode, Stage]]
NEVER_ACKNOWLEDGEABLE: Final[frozenset[ReasonCode]]
# ReasonCode gains, among the errors: "merge_failed", "validation_failed" (P104)

class Reason:            # gains three fields (P89, P91); to_dict gives all five keys
    code: ReasonCode
    detail: str = ""
    page: str | None = None   # the page key or scope the reason concerns
    year: int | None = None   # the year it concerns
    since: datetime | None = None   # P91: when the condition began (coverage gaps only)
```

  A naive `since` raises `RecordError("Reason.since must be timezone-aware")`.

  **The tables:**

  | Code | Level | Stage |
  |---|---|---|
  | `fetch_failed`, `tls_error`, `timeout`, `dns_error`, `http_error`, `challenge_page`, `api_error`, `deadline`, `worker_failed` | error | fetch |
  | `layout_not_recognised`, `required_year_missing`, `pagination_incomplete`, `ledger_mismatch`, `discovery_mismatch` | error | parse |
  | `unavailable` | error | snapshot |
  | `merge_failed`, `validation_failed` | error | run |
  | `unparsed_relevant`, `partial_relevant`, `coverage_gap` | warning | parse |
  | `sudden_drop`, `cumulative_drop`, `fallback_stale` | warning | snapshot |
  | `no_cross_source_match` | warning | match |
  | `served_mismatch`, `attention_truncated`, `ack_invalid` | warning | run |
  | `not_published_yet` | info | parse |
  | `count_change`, `provisional_changes`, `units_disappeared` | info | snapshot |

  `NEVER_ACKNOWLEDGEABLE` = `ledger_mismatch`, `discovery_mismatch`, `fallback_stale`,
  `served_mismatch`, `attention_truncated`, `ack_invalid`, `merge_failed`, `validation_failed`
  (§9.6), plus every info code.

- Produces in **`merge/identity.py`:** `short_id` and `SOURCE_ORDER` are imported from `model`
  and stay importable from `identity` (no merge import changes).
- Produces in **`sources/base.py`:**

```python
PARSER_VERSION: Final = "2.0"

class PageRequest:      # gains two fields (P89)
    key: str
    url: str
    year: int | None = None
    mediawiki: bool = False
    scope: str | None = None    # pages that share a scope are compared together (§9.3)
    link: str | None = None     # the page a reader opens
    @property
    def scope_name(self) -> str: ...   # scope, or key
    @property
    def page_link(self) -> str: ...    # link, or url

class Adapter(Protocol):
    source: str
    parser_version: str        # new; every adapter sets parser_version = PARSER_VERSION
    ...
```

  - `coverage_reasons` gives each reason `page=page.key` and `year=page.year`. `missing_pages`
    gives `page=request.key` and `year=request.year`. Their details are unchanged.
  - **NDI:** `request(n)` gives `scope="pages"`. **Wikipedia:** each request's `link` is
    `https://en.wikipedia.org/wiki/<year>_<kind>_electoral_calendar`. **EISA:** `year_request`
    gives `link=URL` (the calendar page), and its year notes (`not_published_yet`,
    `required_year_missing`) give `year=year`.
- Produces in **`snapshots.py`** (all records `@dataclass(frozen=True, slots=True)`, each
  `__post_init__` calling `_check_fields(self)` first):

```python
REGISTRY_FILES: Final = (DEFAULT_PLACES, DEFAULT_INSTITUTIONS, DEFAULT_SUBDIVISIONS)
STAMPED: Final = ("fetched_at", "fallback", "snapshot_id", "provisional")
MAX_DIAGNOSTIC = 300

def registry_version(paths: Sequence[Path] = REGISTRY_FILES) -> str
    # SHA-256 hex of canonical_json([[path.name, sha256 hex of its bytes], ...]) in the given order
def snapshot_id(units: Sequence[InputUnit], claims: Sequence[Claim]) -> str
    # SHA-256 hex of canonical_json({"units": [u.to_dict()], "claims": [c.to_dict() without STAMPED]})

class PageDownload:      # FetchResult.diagnostics(); final_url and error redacted again and cut (P96)
    outcome: FetchOutcome
    stage: str
    http_status: int | None
    final_url: str
    content_type: str | None
    bytes: int
    elapsed_ms: int
    attempts: int
    error_type: str | None
    error: str | None
    api_code: str | None
    @classmethod
    def of(cls, result: FetchResult) -> PageDownload: ...

class PageRecord:        # one requested page of a snapshot
    key: str
    scope: str           # PageRequest.scope_name
    year: int | None     # PageCoverage.year
    url: str             # the request URL
    link: str            # PageRequest.page_link
    outcome: PageOutcome
    unit_prefix: str | None
    units_seen: int
    revid: int | None
    detail: str
    fetched_at: datetime | None       # None for an unfinished request
    download: PageDownload | None     # None for an unfinished request

class Snapshot:
    source: str
    snapshot_id: str
    fetched_at: datetime | None       # the earliest page fetch; None when no page arrived
    parser_version: str
    registry_version: str
    years: tuple[int, ...]            # the window's years when it was taken
    pages: tuple[PageRecord, ...]     # coverage order
    units: tuple[InputUnit, ...]
    claims: tuple[Claim, ...]         # stored unstamped
    notes: tuple[Reason, ...]

class HistoryEntry:      # one promotion of one scope (§5.10 units_seen_history)
    scope: str
    fetched_at: datetime
    units_seen: int
    claims: int

class Disappeared:       # §9.3
    source_event_id: str
    unit_id: str
    text: str            # the unit's text, collapse_ws, cut to MAX_ATTENTION_TEXT
    date_text: str
    start: date
    end: date
    link: str
    since: datetime

class CoverageGap:       # P91: in-window claims that a year change stopped listing
    scope: str
    old_year: int
    new_year: int
    since: datetime      # the promotion that found it
    claims: tuple[Claim, ...]   # stored unstamped, in the old snapshot's order; never served

class Baseline:
    snapshot: Snapshot
    history: tuple[HistoryEntry, ...]   # sorted by (scope, fetched_at)
    disappeared: tuple[Disappeared, ...] # sorted by source_event_id
    coverage_gaps: tuple[CoverageGap, ...]   # sorted by (scope, since)
    ledger_ok: bool
    discovery_ok: bool

def build_snapshot(raw: RawPages, result: ParseResult, *, parser_version: str,
                   registry_version: str, years: Sequence[int]) -> Snapshot
def snapshot_to_dict(snapshot: Snapshot) -> dict[str, Any]
def baseline_to_dict(baseline: Baseline) -> dict[str, Any]
def load_baseline(path: Path) -> Baseline | None
    # None when the file does not exist; RecordError("baseline.json is corrupt: <problem>") otherwise
```

  - **`PageDownload.of`** applies `fetch.redact_url` to `final_url` and `fetch.redact_text` to
    `error` before cutting both to `MAX_DIAGNOSTIC`. `Fetcher` already redacts, but a
    `FetchResult` built elsewhere (Task 8's offline getter, tests) must never reach a file
    unredacted.
  - **`build_snapshot`:** one `PageRecord` per `result.coverage` entry, in that order, joined to
    its `RawPage` (or its `raw.unfinished` request) by key. Units, claims and notes are
    `result`'s; claims are stored with `STAMPED` at their defaults.
  - **The JSON shape** (§5.10). A snapshot is
    `{source, snapshot_id, fetched_at, parser_version, registry_version, scope: {years, pages},
    units, claims, notes}`. A baseline adds `units_seen_history`, `disappeared`,
    `coverage_gaps` (each `{scope, old_year, new_year, since, claims}`) and
    `checks: {ledger, discovery}`. Timestamps use `_utc_iso`; dates are ISO; records use their
    `to_dict`. Files are written with `stored_json` (Task 8).
  - **Record rules** (each a `RecordError` with this message):

    | Record | Rule | Message |
    |---|---|---|
    | `PageRecord` | `fetched_at` is aware when set | `"PageRecord.fetched_at must be timezone-aware"` |
    | `PageRecord` | `fetched_at` and `download` are both set or both None | `"PageRecord: fetched_at and download go together"` |
    | `Snapshot` | every unit and claim has `source == self.source` | `"Snapshot: a unit or claim of another source"` |
    | `Snapshot` | every claim has `STAMPED` at its default | `"Snapshot: claims are stored unstamped"` |
    | `Snapshot` | `snapshot_id == snapshot_id(units, claims)` | `"Snapshot: snapshot_id does not match its units and claims"` |
    | `HistoryEntry`, `Disappeared`, `CoverageGap` | the timestamp is aware | `"<Name>: <field> must be timezone-aware"` |
    | `CoverageGap` | `claims` is not empty, every claim has `STAMPED` at its default, and `old_year != new_year` | `"CoverageGap: a gap holds unstamped claims of a year change"` |
    | `Baseline` | every gap's claims have `source == snapshot.source` | `"Baseline: a coverage gap of another source"` |
    | `Baseline` | `ledger_ok` and `discovery_ok` are both True | `"Baseline: a baseline passed its ledger and discovery checks"` |
  - **`load_baseline`'s problems,** in the order they are checked; `<problem>` is the text after
    "corrupt: ":

    | Case | `<problem>` starts with |
    |---|---|
    | not UTF-8 or not JSON | `not JSON` |
    | not an object; a missing or unknown key; `units`, `claims`, `notes`, `scope.pages`, `units_seen_history`, `disappeared`, `coverage_gaps` or a gap's `claims` not a list | `shape: ` |
    | a record's `RecordError` (including the rules above) | `record: ` |
    | `ledger.record_problems` on its units and claims, with coverage rebuilt from its pages | `ledger: ` |

- [ ] **Step 1: Write the failing tests.**
  - `tests/unit/test_model.py`:
    - **`test_reason_tables_cover_every_code`:** `REASON_LEVEL` and `REASON_STAGE` have exactly
      the keys `get_args(ReasonCode)`; the levels and stages are the table's; every info code is
      in `NEVER_ACKNOWLEDGEABLE`; `http_error` is not.
    - **`test_reason_page_and_year`:** `Reason("http_error", "upcoming", page="upcoming", year=None)`
      round-trips through `to_dict`/`from_dict`; `to_dict` has the five keys; `from_dict` of the
      old two-key form gives `page=None`, `year=None`, `since=None`;
      `Reason("coverage_gap", "x", page="calendar", year=2027, since=<aware>)` round-trips, and a
      naive `since` raises.
    - **`test_canonical_and_stored_json`:** `canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()`;
      `stored_json([1])` ends with `b"\n"` and decodes to `[1]`.
    - **`test_source_names`:** `tuple(SOURCE_NAMES) == SOURCE_ORDER`, and the nine names are
      P97's.
    - **`test_identity_re_exports`:** `merge.identity.short_id is model.short_id`, and the same for
      `SOURCE_ORDER`.
  - `tests/unit/test_sources_base.py`:
    - **`test_coverage_reasons_have_page_and_year`:** a `timeout` page `national-2027` of year 2027
      gives `Reason("timeout", "national-2027", page="national-2027", year=2027)`.
    - **`test_missing_pages_have_page_and_year`.**
    - **`test_page_request_scope_and_link`:** defaults give `scope_name == key` and
      `page_link == url`; NDI's `request(3).scope_name == "pages"`; Wikipedia's
      `national-2026` request links to `https://en.wikipedia.org/wiki/2026_national_electoral_calendar`;
      EISA's `year_request(2026, "38978").page_link == URL`.
    - **`test_every_adapter_declares_its_parser_version`:** each `DEFAULT_ADAPTERS` class has
      `parser_version == "2.0"`.
    - **`test_eisa_year_notes_have_a_year`:** on the 2026-10-19 fixture, EISA's
      `not_published_yet` note has `year=2027`.
  - `tests/snapshots/test_records.py`:
    - **`test_snapshots_of_the_fixtures_round_trip`** (parametrized over the nine sources): build
      each fixture snapshot (`fixture_results()`, `registry_version()`, the window's years); its
      `snapshot_id` is 64 hex characters; `Baseline(snapshot, (), (), (), True, True)` written with
      `stored_json(baseline_to_dict(…))` and read back with `load_baseline` is equal.
    - **`test_snapshot_id_ignores_provenance`:** stamping every claim (`fetched_at`,
      `fallback=True`, `snapshot_id`, `provisional=True`) and hashing again gives the same id;
      changing one claim's `span` or one unit's `text` changes it.
    - **`test_registry_version`** (copies of the three files in `tmp_path`): the same bytes give
      the same version from another directory; one byte changed in any one file changes it; the
      default arguments give the version of `data/`.
    - **`test_corrupt_baselines_are_never_served`** (parametrized; each row edits a good baseline
      file of the OSCE fixture and expects `RecordError` whose message starts with
      `"baseline.json is corrupt: "` plus the given text):

      | Edit | Starts with |
      |---|---|
      | the bytes `b"{"` | `not JSON` |
      | the bytes `b"\xff"` | `not JSON` |
      | `[]` | `shape: ` |
      | the key `claims` removed | `shape: ` |
      | an extra top-level key `note` | `shape: ` |
      | `units` is `{}` | `shape: ` |
      | `coverage_gaps` is `{}` | `shape: ` |
      | one claim's `date` changed by a day | `record: Snapshot: snapshot_id does not match` |
      | one claim with `fallback: true` (and the id recomputed) | `record: Snapshot: claims are stored unstamped` |
      | `checks.ledger` false | `record: Baseline: a baseline passed` |
      | a gap's claim with `fallback: true` | `record: CoverageGap: a gap holds unstamped claims` |
      | one claim's `unit_id` changed to a unit that does not exist (and the id recomputed) | `ledger: ` |

      A missing file gives None.
    - **`test_page_record_rules`:** one row per rule of the table.
    - **`test_coverage_gaps_round_trip`** (P91): an A-WEB baseline with one gap
      (`calendar`, 2026 → 2027, `since` aware, one dated claim) round-trips through
      `baseline_to_dict`, `stored_json` and `load_baseline`. A gap with no claims, one with
      `old_year == new_year`, one with a naive `since` and a baseline whose gap claim is of
      another source each raise with the table's message.
    - **`test_page_download_redacts_and_cuts`:** a `FetchResult` with `final_url`
      `"https://e.test/a;jsessionid=XYZ?token=abc&page=2"` + 400 × `"x"` and an `error` holding
      `"https://e.test/?key=s3cret"` gives a `PageDownload` whose `final_url` and `error` contain
      neither `XYZ`, `abc` nor `s3cret`, and are at most 300 characters.
  - Adapter tests that compare coverage reasons get `page`/`year` added to their expected
    `Reason`s. Run the suite first and change only those assertions.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/unit/test_model.py tests/unit/test_sources_base.py tests/snapshots -q`.
  Expected: FAIL (the names do not exist).
- [ ] **Step 3: Implement** the model additions, the `PageRequest` fields and reason fields, the
  adapters' `parser_version`, scopes and links, and `snapshots.py`.
  - `importlinter.ini`: the layers become P83's list, with `pipeline` and `__main__` still in
    parentheses (Task 8 creates them):
    `(__main__)`, `(pipeline)`, `(feed) | (publish) | (validate)`, `merge`,
    `(health) | snapshots`, `ledger | runner`, `sources`, `fetch | dates | places | offices | window`,
    `model | text`.
- [ ] **Step 4: Run** the full suite. Expected: PASS. The fixture merge's counts are unchanged
  (`tests/merge/test_fixture_merge.py`).
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(snapshots): snapshot records, ids and loaders; page scopes; shared vocabulary`.

  Mutations, one each:
  - `REASON_LEVEL["coverage_gap"]` becomes `"info"`;
  - `NEVER_ACKNOWLEDGEABLE` loses `fallback_stale`;
  - `canonical_json` drops `sort_keys`;
  - `coverage_reasons` drops `year`;
  - NDI's `request` drops `scope`;
  - Wikipedia's link drops `_electoral_calendar`;
  - EISA's year note drops `year`;
  - `snapshot_id` keeps `fetched_at`;
  - `snapshot_id` leaves out units;
  - `registry_version` hashes only the first file;
  - `load_baseline` skips `record_problems`;
  - `load_baseline` accepts an unknown top-level key;
  - `load_baseline` reads `coverage_gaps` as empty;
  - the `CoverageGap` unstamped rule is skipped;
  - the `Snapshot` id rule is skipped;
  - the unstamped rule is skipped;
  - `PageRecord` accepts a naive `fetched_at`;
  - `PageDownload.of` skips `redact_url`.

---

### Task 2: The acceptance decision and provenance stamping (`snapshots.decide`; §9.3; P90–P94, P105; R1, R2, R14, R19)

**Files:**
- Modify: `elections_calendar/model.py`, `elections_calendar/snapshots.py`
- Create: `tests/support/snapshots.py`, `tests/snapshots/test_decide.py`
- Test: `tests/unit/test_model.py`

**Interfaces:**
- Consumes: Task 1's records, `REASON_LEVEL`, `coverage_reasons`, `PageCoverage`,
  `LedgerReport`, `SourceOutcome` (runner), `Window`, `norm_name` (text), `collapse_ws`,
  `MAX_DETAIL`, `MAX_ATTENTION_TEXT`.
- Produces in **`model.py`** (frozen, slotted, `_check_fields` first; datetimes must be aware,
  `"<Name>.<field> must be timezone-aware"`):

```python
Acceptance = Literal["promoted", "quarantined", "fallback", "unavailable"]

class DropAcceptance:    # an accept_drop entry in effect (§9.6); Task 4 builds them
    source: str
    reason: Literal["sudden_drop", "cumulative_drop"]
    page: str            # the scope
    year: int | None
    units_seen_min: int
    claims_min: int      # P95: the candidate must reach both floors
    until: datetime

class SnapshotHealth:    # spec §5.6 "Snapshot"
    acceptance: Acceptance
    using_fallback: bool
    served_snapshot_id: str | None
    served_fetched_at: datetime | None
    baseline_units_seen: int | None
    comparable: bool
```

- Produces in **`snapshots.py`:**

```python
FALLBACK_FRESH: Final = timedelta(days=7)
HISTORY_DAYS: Final = timedelta(days=30)
DISAPPEARED_DAYS: Final = timedelta(days=7)

class Decision:
    source: str
    candidate: Snapshot
    served: Snapshot | None
    acceptance: Acceptance
    claims: tuple[Claim, ...]        # the served claims stamped, then the provisional ones: the merge's input
    provisional: tuple[Claim, ...]   # the provisional ones alone (also in claims)
    provisional_units: tuple[InputUnit, ...]   # rule 10; Task 3 turns them into items
    baseline: Baseline | None        # what baseline.json holds after this run
    disappeared: tuple[Disappeared, ...]   # in effect at now, sorted by source_event_id
    coverage_gaps: tuple[CoverageGap, ...] # rule 6: in effect at now, sorted by (scope, since)
    reasons: tuple[Reason, ...]      # in the order of rule 9
    health: SnapshotHealth

def decide(
    candidate: Snapshot,
    *,
    run_outcome: SourceOutcome,
    run_detail: str,
    ledger: LedgerReport | None,       # None when parsing failed
    baseline: Baseline | None,
    baseline_problem: str | None,      # load_baseline's message when the file was corrupt
    acceptances: Sequence[DropAcceptance],   # only those in effect, for any source
    window: Window,
    now: datetime,
) -> Decision

def scope_counts(snapshot: Snapshot) -> dict[str, ScopeCount]
    # ScopeCount(units: int, claims: int, pages: int, year: int | None, all_valid_empty: bool),
    # per scope in first-page order; claims are those whose unit_id starts with a page's unit_prefix
def claim_content(claim: Claim) -> tuple[object, ...]           # P105: what rule 11 compares
def unchanged(claim: Claim, others: Sequence[Claim]) -> bool    # P105
def same_listing(claim: Claim, others: Sequence[Claim]) -> bool # rule 6: still listed
```

**The rules of `decide`,** in order. "Today" is `now`'s UTC civil date.

1. **The candidate's own reasons,** in this order:
   1. the run: `deadline` and `scrape_deadline` give `Reason("deadline", run_detail or run_outcome)`;
      `worker_failed` gives `Reason("worker_failed", run_detail)`; `complete` gives none;
   2. `coverage_reasons` of the candidate's pages (as `PageCoverage`);
   3. the candidate's notes;
   4. `ledger.reasons`, when `ledger` is given;
   5. **P92:** each `not_published_yet` reason of (2) or (3) whose `year` has an `ok` or
      `valid_empty` page in the baseline's snapshot is replaced, in place, by
      `Reason("required_year_missing", f"{year} was published before and is now missing", page=<its page>, year=year)`.

   **The candidate is invalid** when one of these has level `error`.
2. **A corrupt baseline:** when `baseline_problem` is set, `Reason("ledger_mismatch", baseline_problem[:MAX_DETAIL])`
   follows the candidate's reasons. It does not make the candidate invalid (P94).
3. **The baseline's standing:**
   - `same_registry`: the baseline's `registry_version` equals the candidate's;
   - `same_major`: the parser versions' text before the first `.` are equal;
   - `comparable` = a baseline exists and `same_major` (P93: the counts do not depend on the
     registry);
   - `servable` = a baseline exists and `same_registry` (P93);
   - a baseline that is not `same_registry` adds the info
     `Reason("count_change", "baseline.json is from another registry version; it is never served")`.
4. **Acceptance:**

   | Candidate | Baseline | Acceptance | Served |
   |---|---|---|---|
   | invalid | servable | `fallback` | the baseline's snapshot |
   | invalid | none, corrupt, or another registry | `unavailable` | None |
   | valid | none, corrupt, or not comparable | `promoted` | the candidate |
   | valid, with an unexplained drop (rule 5) | comparable and servable | `quarantined` | the baseline's snapshot |
   | valid, with an unexplained drop | comparable, not servable | `unavailable`; the drop reason stays | None |
   | valid, no unexplained drop | comparable | `promoted` | the candidate |

   `unavailable` adds `Reason("unavailable", d)` with `d` = `"no baseline"`,
   `"baseline.json is corrupt"` or `"baseline.json is from another registry version"`. On
   `unavailable`, nothing of the candidate is served, merged or provisional, and
   `Decision.baseline` is the input baseline (rule 8), so a later candidate is still compared
   with it (P93).
5. **Drop checks (P90)** run only for a valid candidate and a comparable baseline. For each scope
   in both `scope_counts`, in the candidate's order:
   - `hwm_units`, `hwm_claims`: the largest values among the baseline's history entries of that
     scope with `now - fetched_at <= HISTORY_DAYS` (0 when there are none);
   - **sudden:** `cand.units * 2 < base.units` (what = "units"), else
     `cand.claims * 2 < base.claims` (what = "claims"); the reference is the baseline's number;
   - **cumulative,** only when not sudden: the same two tests against `hwm_units` and
     `hwm_claims`; the reference is the high-water mark;
   - **explained,** in this order, giving `Reason("count_change", …, page=scope, year=cand.year)`:
     - every candidate page of the scope is `valid_empty`: `f"{scope}: {what} fell from {ref} to {n}; the source lists none"`;
     - the scope's year changed (both set, different):
       `f"{scope}: {what} fell from {ref} to {n}; the year changed from {old} to {new}"`;
     - an acceptance with this source, the drop's code, `page == scope`, `year == cand.year`,
       `cand.units >= units_seen_min` and `cand.claims >= claims_min` (P95):
       `f"{scope}: {what} fell from {ref} to {n}; accepted until {_utc_iso(until)}"`; the
       scope's history restarts (rule 8);
   - **unexplained:** `Reason("sudden_drop", f"{scope}: {what} fell from {base} to {n} (candidate: units {cand.units}, claims {cand.claims})", page=scope, year=cand.year)`
     or `Reason("cumulative_drop", f"{scope}: {what} fell to {n}, under half the 30-day high of {hwm} (candidate: units {cand.units}, claims {cand.claims})", page=scope, year=cand.year)`.
     The two counts are what an `accept_drop` needs (P95).

   Then, for each scope in both whose number of pages differs:
   `Reason("count_change", f"{scope}: {base.pages} pages, now {cand.pages}", page=scope, year=cand.year)`
   (R15).
6. **Coverage gaps (P91; the user's decision of 2026-10-20).** The "served claims" are the
   served snapshot's claims, or none when nothing is served.
   - **A gap's remaining claims** are its claims that overlap the window (`window.overlaps`)
     and that `same_listing` finds in none of the served claims. A gap with none remaining has
     ended: each claim was listed again or is dated outside the window.
   - **New gaps,** on a promotion with a baseline: for each scope in both whose year changed
     (both set, different), the baseline claims of that scope that are dated (not year
     precision), overlap the window and that `same_listing` finds in none of the candidate's
     claims. A non-empty set gives `CoverageGap(scope, old, new, since=now, claims)`, the
     claims unstamped and in the baseline's order.
   - **In effect:** on a promotion, the baseline's gaps cut to their remaining claims (each
     keeps its `since`; ended gaps are dropped), then the new ones, and the new baseline holds
     them. Otherwise the baseline's gaps cut to their remaining claims are shown, and nothing
     is written. Both are sorted by (`scope`, `since`) and are `Decision.coverage_gaps`.
   - **Each gap in effect** adds, on every run,
     `Reason("coverage_gap", f"{scope}: the {old} list was replaced by {new}; in-window claims no longer listed: {n}", page=scope, year=new, since=since)`,
     with `n` its remaining claims.
   - A gap's claims are never stamped, served or merged.
7. **Disappeared events** (claims with a `source_event_id`):
   - **On promotion with a baseline:** a baseline claim whose span is dated and ends on or after
     today, and whose `source_event_id` no candidate claim has, is a new `Disappeared` (its
     unit's text, the claim's `date_text`, `span.start`, `span.end`, `link`, `since=now`). The
     baseline's own `disappeared` entries are carried while in effect and while no candidate
     claim has their `source_event_id`. The new baseline holds both.
   - **Otherwise:** the baseline's entries in effect are shown, and nothing is written.
   - **In effect:** `now - since < DISAPPEARED_DAYS` and `end >= today`.
   - A non-zero number shown adds `Reason("units_disappeared", f"listed events no longer listed: {n}")`.
8. **The new baseline** (promotion only): `Baseline(candidate, history, disappeared, coverage_gaps, True, True)`.
   - **History:** when comparable, the baseline's entries with `now - fetched_at <= HISTORY_DAYS`,
     except those of restarted scopes; then one new entry per candidate scope
     (`candidate.fetched_at`, its units and claims). Not comparable or no baseline: the new
     entries only.
   - **Restarted scopes** (P90; review P4-02): a scope whose drop rule 5 accepted, whose year
     changed (both set, different), or whose candidate pages are all `valid_empty`. Each keeps
     only its new entry, so an old year's or a full list's high-water mark never judges the new
     list.
   - Otherwise `Decision.baseline` is the input baseline, unchanged (the same object), or None.
9. **The reasons,** in order: rule 1's, rule 2's, rule 3's, then per scope rule 5's drop or explanation and
   its page count, then rule 6's, then `unavailable`, then **`fallback_stale`** (served is the
   baseline's snapshot and `now - served.fetched_at > FALLBACK_FRESH`:
   `f"serving data fetched {_utc_iso(served.fetched_at)}"`), then
   **`provisional_changes`** (`f"new or changed claims from an incomplete fetch: {n}"`, when
   n > 0), then `units_disappeared`.
10. **Provisional claims** (acceptance `quarantined` or `fallback`; none when `ledger` is None or
    not `ok`, P105): each candidate claim whose unit lies on a page of outcome `ok` or
    `valid_empty`, and that is not `unchanged` against the served claims. **Provisional units**,
    on the same condition (P88): each candidate unit on such a page with outcome `partial` or
    `unparsed`, relevance not `before_window`, whose `collapse_ws(text)` no served unit has, in
    candidate order.
11. **`unchanged(claim, others)` (P105):** some claim in `others` has the same `claim_content`.
    - **`claim_content(c)`** is the tuple of `c`'s fields in their declared order, leaving out
      its position (`unit_id`, `claim_id`), its formatting (`link`, `place_raw`, `date_text`)
      and its stamped provenance (`fetched_at`, `fallback`, `snapshot_id`, `provisional`), with
      `jurisdiction` and `office_label` as `norm_name(x or "")` and `previous_date_text` as
      `collapse_ws(x)` (None stays None).
    - A `source_event_id` or a key only finds a related claim; it never makes two claims equal
      (review P4-01). A re-fetch that changes only position, formatting or provenance is
      unchanged.
    - **`same_listing(claim, others)`** (rule 6): some claim in `others` with the claim's
      `source_event_id` when it has one, else with its key: `place_id`,
      `institution or office_class`, `norm_name(jurisdiction or "")`, `kind` and `round`.
12. **Stamping (R19)** with `dataclasses.replace`:
    - served claims: `fetched_at` = the `fetched_at` of the served page whose `unit_prefix` starts
      the claim's `unit_id`; `fallback` = acceptance is `quarantined` or `fallback`;
      `snapshot_id` = the served snapshot's; `provisional` False;
    - provisional claims: the candidate page's `fetched_at`, `fallback` False, the candidate's
      `snapshot_id`, `provisional` True.

    `Decision.claims` is the served claims in snapshot order, then the provisional ones in
    candidate order.
13. **`SnapshotHealth`:** `using_fallback` is True for `quarantined` and `fallback`;
    `served_fetched_at` is the served snapshot's `fetched_at` (never the run's time);
    `baseline_units_seen` is the sum of the baseline snapshot's `units_seen` (None without one).

**`tests/support/snapshots.py`** builds synthetic snapshots, so the tests read as tables:
- `SynthPage(key, units=0, claims=None, outcome="ok", scope=None, year=None, ignored_reason="no_expected_date", day=date(2026, 11, 15), status=None, sei=None)`:
  `units` units seen; the first `claims` of them (default: all) are `parsed` with one claim
  each, dated `day` (`DateSpan.day`), with `status_claim=status` and `source_event_id`
  `f"{source}:{sei}{i}"` when `sei` is set; the rest are `ignored` with `ignored_reason`.
  Tests that need particular claims (A, B, C below) pass them as `claims=(Claim, …)` built
  with `tests/support/claims.py`'s `mk`.
- `synth(source="osce", pages=(…), fetched_at=T0, parser_version="2.0", registry="r"*64, notes=())`
  → `Snapshot`, built through `build_snapshot` from synthetic `RawPages` and `ParseResult`.
- `promoted(snapshot, history=(), disappeared=(), coverage_gaps=())` → `Baseline`.
- `report(snapshot, problems=(), discovery=False)` → `LedgerReport`.
- `T0 = datetime(2026, 10, 1, 6, tzinfo=UTC)`; `NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)`.

- [ ] **Step 1: Write the failing tests** in `tests/snapshots/test_decide.py`. Unless a row says
  otherwise, the window is `window_for(NOW)`, the baseline has one page `elections` with 100 units
  fetched at `T0`, and the run is `complete` with a clean ledger report.
  - **`test_first_run`** (S4-T02, S1-T6): no baseline and a valid candidate → `promoted`; served
    is the candidate; the new baseline has one history entry per scope and both checks True;
    every claim has `fallback` False, its page's `fetched_at` and the candidate's `snapshot_id`;
    `comparable` False, `baseline_units_seen` None. No baseline and an invalid candidate →
    `unavailable` "no baseline", served None, `claims == ()`, `baseline` None.
  - **`test_invalid_candidates`** (parametrized; S4-T01, S4-T03; a baseline of pages `p1`, `p2`,
    `p3` with 10 units each). Each row gives `fallback`, the baseline's snapshot served, the same
    baseline object kept, every claim stamped `fallback` True, and the listed reason:

    | Row | Candidate | Reason (code, page) |
    |---|---|---|
    | `deadline` | run `deadline`, `p3` unfinished | `deadline` (run) and `deadline` (`p3`) |
    | `scrape_deadline` | run `scrape_deadline` | `deadline` |
    | `worker_failed` | run `worker_failed`, detail `"ValueError"` | `worker_failed` "ValueError" |
    | `p2 timeout` | `p2` outcome `timeout` | `timeout` (`p2`) |
    | `p2 challenge` | `p2` outcome `challenge_page` | `challenge_page` (`p2`) |
    | `p2 repeat` | note `Reason("pagination_incomplete", "p2 repeats p1", page="p2")` | `pagination_incomplete` (`p2`) |
    | `layout` | `p1` outcome `layout_not_recognised` | `layout_not_recognised` (`p1`) |
    | `year` | note `required_year_missing`, year 2027 | `required_year_missing` |
    | `ledger` | report with a problem | `ledger_mismatch` |
    | `discovery` | report with a discovery problem | `discovery_mismatch` |
  - **`test_partial_baselines_are_impossible`** (S4-T01, V2-T04): one source through five runs:
    B0 (100 units) promoted; 40 units → `quarantined`, baseline B0; 100 units with `p2` timed
    out → `fallback`, B0; 100 units with a ledger problem ("100 units discovered, 99 outcomes")
    → `fallback`, B0, and the same candidate with no baseline → `unavailable`; 100 complete
    units → `promoted`, the new baseline holds this candidate.
  - **`test_drops`** (parametrized; NM-T01; one scope `elections`; history entries as
    (units, days before `NOW`)):

    | Row | History | Baseline | Candidate | Acceptance in effect | Result |
    |---|---|---|---|---|---|
    | a | — | 100 | 49 | — | `quarantined`; `sudden_drop` "elections: units fell from 100 to 49 (candidate: units 49, claims 49)" |
    | b | — | 100 | 50 | — | `promoted`; no reason |
    | c | — | 100 units, 100 claims | 100 units, 49 claims (51 ignored) | — | `sudden_drop` "elections: claims fell from 100 to 49 (candidate: units 100, claims 49)" |
    | d | (100, 2), (60, 1) | 60 | 36 | — | `cumulative_drop` "elections: units fell to 36, under half the 30-day high of 100 (candidate: units 36, claims 36)" |
    | e | (100, 31), (60, 1) | 60 | 36 | — | `promoted` |
    | f | (100, 30), (60, 1) | 60 | 36 | — | `cumulative_drop` (30 days is inside) |
    | g | — | 100 | 0, `valid_empty` | — | `promoted`; `count_change` "elections: units fell from 100 to 0; the source lists none" |
    | h | — | 100, year 2026, claims in March 2026 | 30, year 2027 | — | `promoted`; `count_change` "elections: units fell from 100 to 30; the year changed from 2026 to 2027"; no `coverage_gap` |
    | i | (100, 2), (60, 1) | 60 | 36 | `cumulative_drop`, `elections`, min 30 units and 30 claims, until `NOW + 3 days` | `promoted`; `count_change` "elections: units fell from 100 to 36; accepted until 2026-10-22T12:00:00Z"; the new history is the one new entry |
    | j | as i | 60 | 36 | as i, min 40 units | `cumulative_drop` |
    | k | as i | 60 | 36 | as i, reason `sudden_drop` | `cumulative_drop` |
    | l | — | 100 | 49 | `sudden_drop`, page `other` | `sudden_drop` |
    | m | (100, 40), (90, 2) | 90 | 90 | — | `promoted`; history (90, 2), (90, new): the 40-day entry is pruned |
    | n | — | 100 units, 100 claims | 40 units, 0 claims (40 ignored) | `sudden_drop`, `elections`, min 40 units and 40 claims, until `NOW + 3 days` | `sudden_drop` "elections: units fell from 100 to 40 (candidate: units 40, claims 0)" |
    | o | — | 100 units, 100 claims | 40 units, 40 claims | as n | `promoted`; `count_change` "elections: units fell from 100 to 40; accepted until 2026-10-22T12:00:00Z" |
    | p | — | 100 units, 100 claims | 100 units, 0 claims (100 ignored) | as n | `sudden_drop` "elections: claims fell from 100 to 0 (candidate: units 100, claims 0)" |
    | q | — | 100 units, 100 claims | 40 units, 0 claims (40 ignored) | as n, min 40 units and 0 claims | `promoted`; `count_change` "elections: units fell from 100 to 40; accepted until 2026-10-22T12:00:00Z" |
    | r | — | 100, year 2026 | 40, year 2026 | as o, year 2027 | `sudden_drop` |

    Rows n–r (P95; review P4-03): an approval made for 40 units and 40 claims never accepts 40
    units with none; only an explicit `claims_min` of 0 (YAML `accept_claims_min: 0`) does.
  - **`test_a_shift_into_ignored_reasons_is_a_warning`** (R1): baseline 10 units, 10 claims;
    candidate 10 units of which 6 are ignored `no_expected_date`, 4 claims → `quarantined`,
    `sudden_drop` "elections: claims fell from 10 to 4 (candidate: units 10, claims 4)", the baseline
    served.
  - **`test_claims_falling_while_units_hold_is_a_warning`** (R1): a header-only table (1 unit,
    ignored `header_row`) against 10 → `sudden_drop` "elections: units fell from 10 to 1 (candidate: units 1, claims 0)"; a table
    of 10 ignored units against 10 parsed → `sudden_drop` "elections: claims fell from 10 to 0 (candidate:
    units 10, claims 0)".
  - **`test_a_new_list_restarts_the_history`** (P90; review P4-02). Two scopes, `calendar` (a
    year) and `archive` (none). The baseline B0 has `calendar` 100 units (year 2026) and
    `archive` 100, each with one history entry of 100 from 1 day before `NOW`.
    - Run 2 at `NOW`: `calendar` 30 (year 2027), `archive` 60 → `promoted`; `count_change`
      "calendar: units fell from 100 to 30; the year changed from 2026 to 2027"; the new
      history holds only `calendar`'s new entry, and both of `archive`'s.
    - Run 3 from run 2's baseline at `NOW + 1 day`: `calendar` 30 (2027) and `archive` 60 →
      `promoted` with no drop reason. The same with `archive` 36 → `quarantined`, and the only
      drop reason is `archive`'s `cumulative_drop` "archive: units fell to 36, under half the
      30-day high of 100 (candidate: units 36, claims 36)".
    - From run 3's promoted baseline, with `archive` at 60: `calendar` 20 → `promoted`; then 14 →
      `cumulative_drop` "calendar: units fell to 14, under half the 30-day high of 30
      (candidate: units 14, claims 14)".
    - One scope `elections`: 100 → 0 `valid_empty` → `promoted` with `count_change` "elections:
      units fell from 100 to 0; the source lists none" and only the new history entry; then 10
      → `promoted`, no reason.
  - **`test_aweb_rollover_keeps_december_events`** (R2, P91; the user's decision). A-WEB, page
    `calendar`. The baseline B0 (year 2026) lists Gambia 5 December 2026 and two claims in
    March 2026; the candidate C (year 2027) lists two claims in February 2027.
    `R1 = datetime(2027, 1, 2, 6, tzinfo=UTC)`.
    - **Run 1** at `R1` → `promoted`; `coverage_gaps` is
      `(CoverageGap("calendar", 2026, 2027, R1, (Gambia,)),)`; the reason `coverage_gap`
      "calendar: the 2026 list was replaced by 2027; in-window claims no longer listed: 1"
      (page `calendar`, year 2027, `since` `R1`); the new baseline holds the gap; no claim in
      `Decision.claims` is Gambia's.
    - **Run 2:** C again, from run 1's baseline, at `R1 + 1 day` → `promoted` with no drop
      reason (P4-02) and the same `coverage_gap` reason, its `since` still `R1`; the new
      baseline still holds the gap.
    - **Run 3:** from run 2's baseline at `R1 + 2 days`, `calendar` timed out → `fallback`; the
      same `coverage_gap` reason; `Decision.baseline` is the input object.
    - **Listed again:** from run 2's baseline, C plus Gambia with another `date_status`
      (`same_listing`, not `unchanged`) → no `coverage_gap`, and the new baseline has no gap.
      The same candidate in run 1 makes no gap at all.
    - **Out of the window:** C from run 2's baseline at `2027-02-01T06:00Z` (the window starts
      in January) → no `coverage_gap`, and the new baseline has no gap.
  - **`test_eisa_january_without_a_new_table_keeps_december`** (R14): baseline taken
    2026-12-15 (`calendar` 0 units, `y2026` 22 units, note `not_published_yet` year 2027).
    `now` = 2027-01-03; the candidate has `calendar` and `y2026` and the note
    `required_year_missing` year 2027 → `fallback`; the December claims are the merge's input,
    stamped `fallback` True with their December `fetched_at`.
  - **`test_a_disappeared_year_table_is_an_error`** (R14, P92): baseline with an `ok` page `y2027`
    (year 2027); candidate note `not_published_yet` year 2027 → `required_year_missing` "2027 was
    published before and is now missing" (year 2027), `fallback`. With a baseline without a 2027
    page, the note stays `not_published_yet` and the candidate is `promoted`.
  - **`test_provisional_changes`** (S4-T04, NM-T02, S1-T4). Baseline pages `p1` (claims A: sei 1,
    15 November; B: no sei, 22 November) and `p2` (C). Candidate `p1`: A′ (sei 1, 16 November),
    B unchanged, D (new); `p2` timed out → `fallback`; `provisional` is (A′, D) stamped
    `provisional` True with the candidate's `p1` `fetched_at` and `snapshot_id`;
    `provisional_changes` "new or changed claims from an incomplete fetch: 2"; `claims` ends with
    A′, D. More rows:
    - A with `status_claim` `postponed` and the same date → provisional;
    - the same candidate with a ledger problem → `provisional == ()`; with a discovery problem → `()`;
    - a quarantined candidate (a drop) → provisional from every page;
    - a complete candidate with no change → `promoted` and `provisional == ()`;
    - **provisional units** (`p2` timed out): a new `unparsed` unit on `p1` with relevance
      `unknown` → in `provisional_units`; the same text with other spacing as a served unit → not;
      a `before_window` one → not; one on the timed-out `p2` → not; with a ledger problem →
      `provisional_units == ()`.
  - **`test_an_unchanged_partial_claim_is_not_provisional`** (R19, V2-T01): `p1` equal to the
    served `p1`, `p2` timed out → `provisional == ()`, no `provisional_changes` reason.
  - **`test_unchanged_compares_the_whole_claim`** (P105; review P4-01; parametrized). The
    baseline's `p1` holds A = `mk("osce:p1/r1", source_event_id="osce:1", date_status="tentative", office_label="District 3")`;
    the candidate's `p1` holds A′, which is A changed as the row says, and its `p2` timed out
    (`fallback`). Each row runs again with `p2` falling from 10 units to 4 (`quarantined`):

    | Row | A′ | Provisional |
    |---|---|---|
    | certainty | `date_status="confirmed"` | yes |
    | meaning | `date_meaning="voting_period"` | yes |
    | level | `level="subnational"` | yes |
    | number | `office_label="District 4"` | yes |
    | place | another `place_id`, the same `source_event_id` | yes |
    | institution | another `institution` | yes |
    | rescheduled | `previous_date_text="1 November 2026"` | yes |
    | link | another `link` | no |
    | wording | `date_text="15 Nov 2026"`, another `place_raw` | no |
    | spacing | `office_label="district  3"` | no |
    | position | `unit_id` `osce:p1/r2` (a row inserted above) | no |

    `same_listing` finds A for every row (the same `source_event_id`).
  - **`test_stamped_fallback_claims_reach_the_merge`** (R19): the OSCE fixture snapshot as the
    baseline, and the same pages timed out as the candidate → `fallback`. `merge(decision.claims, now=FIXTURE_NOW, places=…)`
    gives children whose OSCE sources all have `fallback` True and the baseline page's
    `fetched_at`.
  - **`test_fallback_age_is_never_refreshed`** (Review Focus 1): baseline fetched at `T0`, an
    invalid candidate. At `T0 + 7 days`: no `fallback_stale`, `served_fetched_at == T0`. At
    `T0 + 7 days + 1 s`: `fallback_stale` "serving data fetched 2026-10-01T06:00:00Z". Both
    times, `Decision.baseline` is the input object.
  - **`test_parser_version_change`** (S4-T06): baseline `1.4`, candidate `2.0`, 100 → 40 →
    `promoted`, `comparable` False, the history only the new entry. Baseline `2.0`, candidate
    `2.3` → `sudden_drop`.
  - **`test_registry_change`** (P93; the user's decision; parametrized). The baseline B0 is of
    another registry version: page `elections`, 100 units and 100 claims, one history entry of
    100 from 1 day before `NOW`. Every row has `comparable` True and the info `count_change`
    "baseline.json is from another registry version; it is never served":

    | Row | Candidate | Acceptance | Served, and `claims` | `Decision.baseline` | Other reasons, in order |
    |---|---|---|---|---|---|
    | success | 100 units, 100 claims | `promoted` | the candidate; its claims with its `snapshot_id` | new: the candidate (this registry), history B0's entry plus the new one | none |
    | unit drop | 40 units, 40 claims | `unavailable` | None; `()` | B0, the same object | `sudden_drop` "elections: units fell from 100 to 40 (candidate: units 40, claims 40)", `unavailable` "baseline.json is from another registry version" |
    | claim-only drop | 100 units, 40 claims (60 ignored) | `unavailable` | None; `()` | B0 | `sudden_drop` "elections: claims fell from 100 to 40 (candidate: units 100, claims 40)", `unavailable` |
    | invalid | `elections` timed out | `unavailable` | None; `()` | B0 | `timeout` (`elections`), `unavailable` |
    | accepted drop | the unit drop, with an `accept_drop` (`sudden_drop`, `elections`, min 40 units and 40 claims) | `promoted` | the candidate | new; `elections`' history restarted | `count_change` "elections: units fell from 100 to 40; accepted until 2026-10-22T12:00:00Z" |

    - `provisional == ()` in every `unavailable` row.
    - **Recovery:** after the unit-drop row (B0 kept), a candidate of 100 units and 100 claims
      → `promoted`, the candidate served, no `unavailable`.
    - **Unaffected:** the unit drop beside a baseline of this registry → `quarantined`, the
      baseline served with `fallback` True, and no registry `count_change`.
  - **`test_a_corrupt_baseline_is_loud`** (P94): no baseline, `baseline_problem` "baseline.json
    is corrupt: not JSON" → `ledger_mismatch` with that detail; a valid candidate is `promoted`
    with `comparable` False; an invalid one is `unavailable` "baseline.json is corrupt".
  - **`test_disappeared_units`** (ElectionGuide, `now` = `NOW`). Baseline claims: sei
    `electionguide:5259` (15 November 2026, unit text "Gambia: Presidential"), sei
    `electionguide:5000` (1 September 2026), and a year-only claim with sei
    `electionguide:6000`. A promoted candidate with none of them → `disappeared` holds only 5259
    (`since` = `NOW`, `start` = `end` = 15 November), `units_disappeared` "listed events no
    longer listed: 1", and the new baseline holds it. From that baseline:
    - at `NOW + 6 days`, promoted, still absent → shown, `since` unchanged;
    - at `NOW + 7 days` → gone;
    - a candidate that lists 5259 again → gone;
    - at 16 November → gone (its date passed);
    - a fallback run at `NOW + 1 day` → shown, and the baseline is not rewritten.
  - **`test_a_coverage_gap_is_promoted`:** a valid candidate with a `coverage_gap` note →
    `promoted`, and the reason is kept.
  - In `tests/unit/test_model.py`, **`test_drop_acceptance_and_snapshot_health`:** both records
    reject a naive datetime.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/snapshots/test_decide.py -q`.
  Expected: FAIL (`decide` does not exist).
- [ ] **Step 3: Implement** the two model records, `ScopeCount`, `scope_counts`, `claim_content`, `unchanged`,
  `same_listing`,
  `Decision` and `decide`.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(snapshots): the acceptance decision, drop checks, provisional changes and stamping`.

  Mutations, one each:
  - the sudden rule becomes `cand * 2 <= base`;
  - the claims comparison is dropped;
  - the high-water mark ignores `HISTORY_DAYS`;
  - `<=` becomes `<` in the history window;
  - `valid_empty` no longer explains;
  - the year change no longer explains;
  - an acceptance ignores `units_seen_min`;
  - an acceptance ignores `claims_min`;
  - an acceptance ignores its reason;
  - accepted scopes keep their history;
  - a year change keeps the scope's history;
  - `valid_empty` keeps the scope's history;
  - history entries are never pruned;
  - an invalid candidate with a servable baseline is promoted;
  - a `worker_failed` run is valid;
  - a registry mismatch is servable;
  - a registry mismatch skips the drop checks;
  - a dropped candidate beside an unservable baseline is promoted;
  - P92 is skipped;
  - P91 counts claims outside the window;
  - a gap is dropped on the next promotion;
  - a claim listed again stays in its gap;
  - a carried gap's `since` becomes `now`;
  - a gap's claims reach `Decision.claims`;
  - provisional claims also come from a timed-out page;
  - provisional claims ignore a ledger problem;
  - provisional units keep a text that a served unit has;
  - `unchanged` ignores `status_claim`;
  - `unchanged` ignores `source_event_id`;
  - `claim_content` leaves out `date_status`;
  - `claim_content` keeps `link`;
  - `same_listing` requires the same span;
  - served claims are stamped `fallback` False on fallback;
  - `served_fetched_at` is `now`;
  - `fallback_stale` uses `>=`;
  - disappeared entries are kept after `DISAPPEARED_DAYS`;
  - a reappeared event stays disappeared;
  - a corrupt baseline adds no reason;
  - `Decision.baseline` is the candidate on `quarantined`.

---

### Task 3: Unit attention items, item dates and joint tickets (`snapshots.unit_items`; P87, P88, P102; R20, R21)

**Files:**
- Modify: `elections_calendar/model.py`, `elections_calendar/merge/cards.py`,
  `elections_calendar/offices.py`, `elections_calendar/snapshots.py`
- Create: `tests/snapshots/test_unit_items.py`
- Test: `tests/unit/test_model.py`, `tests/unit/test_offices.py`, `tests/merge/test_cards.py`

**Interfaces:**
- Consumes: Task 2's `Decision` (`served`, `candidate`, `acceptance`, `provisional_units`,
  `disappeared`); `PageRecord.link`, `PageRecord.unit_prefix`; `SOURCE_NAMES`; `short_id`;
  `collapse_ws`; `MAX_ATTENTION_TEXT`.
- Produces in **`model.py`:** `AttentionItem` gains three fields, after `undated_id`:

```python
    date: date | None = None     # P87: the earliest start of its day or month claim spans
    unit_id: str | None = None   # set on items about one unit; such items have no merge_ids
    unit_text: str | None = None # P88: the full collapse_ws text of a partial or unparsed unit; never cut
```

  | Rule | Message |
  |---|---|
  | `unit_id` None: `merge_ids` sorted, unique and non-empty (as before) | `"AttentionItem.merge_ids must be sorted, unique and non-empty"` |
  | `unit_id` set: `merge_ids == ()` | `"AttentionItem: a unit item has no merge_ids"` |
  | kind `unparsed_unit`, `partial_unit` or `disappeared_unit`: `unit_id` set | `"AttentionItem: a <kind> item needs a unit_id"` |
  | kind `undated_listing` or `unresolved_evidence`: `unit_id` None | `"AttentionItem: a <kind> item has no unit_id"` |
  | `unit_text` set exactly when the kind is `partial_unit` or `unparsed_unit` | `"AttentionItem: unit_text is set exactly on partial_unit and unparsed_unit items"` |

  `provisional_change` items exist in both forms: the merge's (a claim, `merge_ids`) and Task 3's
  (a unit, `unit_id`).
- Produces in **`merge/cards.py`:** `_pending_item` sets `date=c.span.start` unless
  `c.span.precision == "year"` (then None). `_listing_item` sets no date.
- Produces in **`offices.py`** (P102):
  - `_DEPUTY_OF` = `^(?:lieutenant|deputy|vice)[\s-]+(governor|mayor|president|gubernatorial|mayoral|presidential)$`;
  - `unnamed_parts` returns `[]` when its split gives exactly two parts and `_joint_ticket(parts[0], parts[1])`;
  - docstrings of `split_offices` and `unnamed_parts` name the adjective forms.
- Produces in **`snapshots.py`:**

```python
def unit_items(decision: Decision) -> tuple[AttentionItem, ...]   # sorted by item_id; () when served is None
```

  | Items | From | `item_id` | `text` | `reason` | `relevance` | `link` | `date` | `snapshot_id` |
  |---|---|---|---|---|---|---|---|---|
  | `partial_unit`, `unparsed_unit` | each served unit with that outcome and relevance not `before_window` | `short_id([kind, unit_id])` | `collapse_ws(unit.text)` | `unit.reason or unit.outcome` | the unit's | the first of its served claims' `link`, else its page's `link` | the earliest `span.start` of its served day or month claims, else None | the served snapshot's |
  | `provisional_change` | each of `decision.provisional_units` | `short_id(["provisional_change", unit_id])` | `"From an incomplete fetch: " + collapse_ws(unit.text)` | `unit.reason or unit.outcome` | the unit's | as above, from the candidate | as above, from the candidate's claims | the candidate's |
  | `disappeared_unit` | each of `decision.disappeared` | `short_id(["disappeared_unit", source_event_id])` | `f"No longer listed by {SOURCE_NAMES[source]}: {text}, was {date_text}"` | `"disappeared"` | `in_or_after_window` | the entry's `link` | its `start` | the served snapshot's |

  - Every `text` is cut to `MAX_ATTENTION_TEXT` after it is built. `unit_text` is
    `collapse_ws(unit.text)` on `partial_unit` and `unparsed_unit` items, never cut (P88: what
    an acknowledgement compares), and None on the others.
  - `source` is the decision's source; `possible_matches`, `merge_ids` are `()`;
    `undated_id` is None; `unit_id` is the unit's (for `disappeared_unit`, the entry's).
  - "Its page" is the served (or candidate) `PageRecord` whose `unit_prefix` starts the
    `unit_id`.

- [ ] **Step 1: Write the failing tests.**
  - `tests/unit/test_offices.py`, **`test_joint_ticket_is_not_unnamed_parts`** (R21), with the
    loaded `InstitutionRegistry`:

    | Text | Place | `unnamed_parts` |
    |---|---|---|
    | `"Presidential and Vice-Presidential"` | `iso:PH` | `[]` |
    | `"Presidential and Vice Presidential"` | `iso:NG` | `[]` |
    | `"Governor and Lieutenant Governor"` | `iso:US` | `[]` |
    | `"Gubernatorial and Lieutenant Gubernatorial"` | `iso:US` | `[]` |
    | `"Mayoral and Vice-Mayoral"` | `iso:PH` | `[]` |
    | `"National and Provincial"` | `iso:ZA` | `["National"]` |

    and `split_offices("Presidential and Vice-Presidential", "iso:PH", reg) == ["Presidential and Vice-Presidential"]`.
  - `tests/unit/test_model.py`, **`test_attention_item_unit_rules`:** one row per rule of the
    table, plus a valid unit item (`unit_id` set, `merge_ids == ()`) and a valid merge
    `provisional_change` item (`merge_ids` set, `unit_id` None).
  - `tests/merge/test_cards.py`, **`test_merge_items_have_dates`:** on the fixture merge, each
    `unresolved_evidence` item's `date` is its claim's `span.start` (None for a year-precision
    claim), and each `undated_listing` item's `date` is None.
  - `tests/snapshots/test_unit_items.py`:
    - **`test_unit_items_on_the_fixtures`:** for each source, the fixture snapshot promoted on a
      first run (`decide` with no baseline, `now=FIXTURE_NOW`). Over the nine sources:
      - 121 items: Wikipedia 111 (60 `partial_unit`, 51 `unparsed_unit`; by page `local-2026`
        61, `local-2027` 48, `national-2026` 2), IPU 4, A-WEB 3, NDI 1, EISA 2;
      - the reasons: Wikipedia `article_title` 46, `office_not_modelled` 34,
        `office_unrecognised` 31; IPU `designation_unrecognised` 4; A-WEB `level_unresolved`,
        `office_not_modelled`, `office_unrecognised` 1 each; NDI `level_unresolved` 1; EISA
        `no_new_date` 2;
      - relevance: 90 `in_or_after_window`, 31 `unknown`;
      - 63 have a date, and 2 of those are after `window_for(FIXTURE_NOW).end`;
      - no link contains `api.php`; every Wikipedia link starts with
        `https://en.wikipedia.org/wiki/`;
      - EISA's two texts are `"Libya | Presidential | Postponed from April 2026"` and
        `"Libya (from the row above) | House of Representatives | Postponed from April 2026"`.
    - **`test_unit_items_follow_the_served_snapshot`:** a fallback decision (Task 2's helper:
      baseline with an `unparsed` unit U1, candidate with `p2` timed out and an `unparsed` unit
      U2 on `p1`) gives the `unparsed_unit` item of U1 (the baseline's `snapshot_id`) and the
      `provisional_change` item of U2 with text `"From an incomplete fetch: …"` and the
      candidate's `snapshot_id`; an `unavailable` decision gives `()`.
    - **`test_disappeared_items`:** Task 2's `test_disappeared_units` decision gives one
      `disappeared_unit` item: text `"No longer listed by ElectionGuide: Gambia: Presidential, was <date_text>"`,
      date 15 November 2026, `unit_id` the baseline unit's, reason `"disappeared"`.
    - **`test_unit_item_ids_are_stable`:** the same decision twice gives equal tuples; the
      items are sorted by `item_id`.
    - **`test_unit_items_carry_the_full_text`** (P88; review P4-04): a relevant `unparsed` unit of
      400 characters gives an item whose `text` is its first 300 and whose `unit_text` is all
      400 (`collapse_ws(unit.text)`); two units that differ only after character 300 give equal
      `text`s and different `unit_text`s; `provisional_change` and `disappeared_unit` items have
      `unit_text` None.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/snapshots/test_unit_items.py tests/unit/test_offices.py tests/unit/test_model.py tests/merge/test_cards.py -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the model fields and rules, the merge item dates, R21 and
  `unit_items`.
- [ ] **Step 4: Run** the full suite. Expected: PASS, and the fixture merge's counts unchanged.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(snapshots): unit attention items, item dates and joint tickets`.

  Mutations, one each:
  - `_DEPUTY_OF` loses `presidential`;
  - `unnamed_parts` skips the joint-ticket check;
  - the unit item rule accepts `merge_ids` on a unit item;
  - `_pending_item` sets no date;
  - year-precision claims get a date;
  - `unit_items` keeps `before_window` units;
  - `unit_items` takes units from the candidate on fallback;
  - the link ignores the page's `link` (uses `url`);
  - the date takes the latest start;
  - the text is not cut;
  - `unit_text` is cut to 300.

---

### Task 4: Acknowledgements and recurrence (`health.py`: `known_issues.yml`, `health_state.json`; §9.6; P94, P95; R16)

**Files:**
- Create: `elections_calendar/health.py`, `known_issues.yml`, `tests/health/__init__.py`,
  `tests/health/test_known_issues.py`, `tests/health/test_acknowledge.py`
- Modify: `importlinter.ini` (`(health)` loses its parentheses)

**Interfaces:**
- Consumes: `collapse_ws`; `Reason`, `ReasonCode`, `Stage`, `AttentionItem`, `REASON_LEVEL`, `REASON_STAGE`,
  `NEVER_ACKNOWLEDGEABLE`, `SOURCE_ORDER`, `DropAcceptance`, `stored_json`, `_utc_iso`,
  `MAX_DETAIL` (Tasks 1–3); `yaml` (PyYAML).
- Produces in **`health.py`** (records frozen and slotted; datetimes aware):

```python
MAX_ACK_LENGTH: Final = timedelta(days=14)
MAX_ACK_AHEAD: Final = timedelta(days=1)
UNIT_REASONS: Final = ("unparsed_relevant", "partial_relevant")
DROP_REASONS: Final = ("sudden_drop", "cumulative_drop")

class Scope:
    stage: Stage
    year: int | None
    page: str | None

EntryKind = Literal["acknowledgement", "unit_acknowledgement", "accept_drop"]

class Entry:
    index: int                    # 1-based position in the file
    kind: EntryKind
    source: str
    reason: ReasonCode
    scope: Scope | None           # None for unit_acknowledgement
    unit_text: str | None         # only for unit_acknowledgement; stored as collapse_ws gives it
    units_seen_min: int | None    # only for accept_drop (YAML: accept_units_seen_min)
    claims_min: int | None        # only for accept_drop (YAML: accept_claims_min)
    explanation: str
    owner: str
    acknowledged_at: datetime
    expires_at: datetime
    @property
    def key(self) -> str: ...     # the recurrence key, below

class KnownIssues:
    entries: tuple[Entry, ...]    # the valid ones, in file order
    problems: tuple[Reason, ...]  # one ack_invalid per invalid entry, or one for the whole file

class HealthState:                # one source's data/sources/<source>/health_state.json
    last_absent_at: tuple[tuple[str, datetime], ...]   # sorted by key
    problem: str | None = None    # set when the file was corrupt
    reset_at: datetime | None = None   # P94: acknowledgements made before it never count

class Acknowledgement:            # one reason acknowledged in this run (§5.6 acknowledged[])
    code: ReasonCode
    until: datetime
    stage: Stage
    year: int | None
    page: str | None
    since: datetime | None = None   # the acknowledged reason's (P91)

def parse_known_issues(text: str, *, now: datetime) -> KnownIssues
def load_known_issues(path: Path, *, now: datetime) -> KnownIssues   # a missing file: no entries
def load_health_state(path: Path) -> HealthState                     # a missing file: empty
def health_state_to_dict(state: HealthState) -> dict[str, Any]       # {"last_absent_at": {key: iso}, "reset_at": iso | None}
def reason_key(reason: Reason) -> str
def unit_key(reason: ReasonCode, text: str) -> str
def in_effect(entry: Entry, state: HealthState, now: datetime) -> bool
def not_yet_active(issues: KnownIssues, now: datetime) -> tuple[Entry, ...]
def relevance_reasons(items: Sequence[AttentionItem]) -> tuple[Reason, ...]
def acknowledge(source: str, reasons: Sequence[Reason], items: Sequence[AttentionItem],
                issues: KnownIssues, state: HealthState, now: datetime) -> tuple[Acknowledgement, ...]
def drop_acceptances(issues: KnownIssues, states: Mapping[str, HealthState],
                     now: datetime) -> tuple[DropAcceptance, ...]
def present_keys(reasons: Sequence[Reason], items: Sequence[AttentionItem]) -> frozenset[str]
def next_health_state(previous: HealthState, source: str, issues: KnownIssues,
                      present: frozenset[str], now: datetime) -> HealthState
def state_problem_reason(state: HealthState) -> Reason | None
    # Reason("ack_invalid", f"health_state.json is corrupt: {problem}"[:MAX_DETAIL])
```

**The file format** (§9.6). `known_issues.yml` is a YAML list of mappings:

| Kind | Fields (all required, no others) |
|---|---|
| `acknowledgement` | `source`, `reason`, `scope: {stage, year, page}`, `explanation`, `owner`, `acknowledged_at`, `expires_at` |
| `unit_acknowledgement` | the same with `unit_text` in place of `scope` |
| `accept_drop` | the `acknowledgement` fields plus `accept_units_seen_min` and `accept_claims_min` |

The kind is read from the fields: `unit_text` makes a unit acknowledgement,
`accept_units_seen_min` or `accept_claims_min` an `accept_drop`. The repository's `known_issues.yml` is `[]` with this
table and the §9.6 example as comments.

**Loading rules.** The YAML is read with a `yaml.SafeLoader` subclass whose mappings reject a
repeated key. Whole-file problems give one reason and no entries:

| Case | `ack_invalid` detail |
|---|---|
| not UTF-8, invalid YAML (a tab, a repeated key) | `"known_issues.yml is not valid YAML"` |
| an empty file | none: no entries |
| not a list | `"known_issues.yml is not a list"` |

Each invalid entry gives `Reason("ack_invalid", f"known_issues.yml entry {n}: {problem}")` (cut
to `MAX_DETAIL`) and has no effect. The checks, in order; the first that fails is the problem:

| Check | `problem` |
|---|---|
| the entry is a mapping | `"not a mapping"` |
| no field is missing (in the table's order) | `"missing field <f>"` |
| no field is unknown (sorted) | `"unknown field <f>"` |
| `scope` is a mapping of exactly `stage`, `year` (int or null) and `page` (string or null) | `"scope must have stage, year and page"` |
| `source` is in `SOURCE_ORDER` | `"unknown source <s>"` |
| `reason` is a `ReasonCode` | `"unknown reason <r>"` |
| `reason` is not in `NEVER_ACKNOWLEDGEABLE` | `"<r> can never be acknowledged"` |
| a unit acknowledgement's reason is in `UNIT_REASONS`; a scoped entry's is not | `"unit_text is only for unparsed_relevant and partial_relevant"` / `"<r> is acknowledged per unit (unit_text)"` |
| an `accept_drop`'s reason is in `DROP_REASONS` | `"accept_units_seen_min and accept_claims_min are only for sudden_drop and cumulative_drop"` |
| `accept_units_seen_min`, then `accept_claims_min`, is an `int` (not a `bool`) ≥ 0 | `"<f> must be a whole number of at least 0"` |
| `scope.stage == REASON_STAGE[reason]` | `"scope.stage must be <stage> for <r>"` |
| `explanation`, `owner` and `unit_text` are non-empty strings after `collapse_ws` | `"<f> must not be empty"` |
| each timestamp is a `datetime` with a time zone, or a string that `datetime.fromisoformat` reads as one | `"<f> must be a timestamp with a time zone"` |
| `expires_at > acknowledged_at` | `"expires_at must be after acknowledged_at"` |
| `expires_at - acknowledged_at <= MAX_ACK_LENGTH` | `"an acknowledgement lasts at most 14 days"` |
| `acknowledged_at <= now + MAX_ACK_AHEAD` | `"acknowledged_at is more than 1 day in the future"` |

Timestamps are stored in UTC. A `date` (YAML `2026-10-20`) and a naive datetime fail the
timestamp check.

**Keys and effect:**
- `reason_key(r)` = `f"{r.code}|{REASON_STAGE[r.code]}|{r.year if r.year is not None else ''}|{r.page or ''}"`;
  a scoped entry's key is the same text built from its reason and scope.
- `unit_key(reason, text)` = `f"unit|{reason}|{sha256(text.encode()).hexdigest()[:16]}"`.
- **`in_effect`:** `acknowledged_at <= now < expires_at`, the state has no problem, and the state
  has no `last_absent_at` for the entry's key later than `acknowledged_at` (recurrence), and
  the state's `reset_at` is None or not later than `acknowledged_at` (P94).
- **`not_yet_active`:** valid entries with `acknowledged_at > now`, in file order.
- **`acknowledge`:**
  - a reason of level `error` or `warning` and not in `UNIT_REASONS` is acknowledged when an
    entry in effect of this source (any kind but `unit_acknowledgement`) has its key;
    when the reason has a `since`, only entries with `acknowledged_at >= since` count (P91: a
    gap that began after an acknowledgement is a new incident); `until` = the latest
    `expires_at` of those entries;
  - `unparsed_relevant` (`partial_relevant`) is acknowledged when every `unparsed_unit`
    (`partial_unit`) item of this source is covered by a `unit_acknowledgement` in effect with
    that reason and `entry.unit_text == item.unit_text` (the full text, never the cut `text`;
    review P4-04); `until` = the earliest, over the items, of each
    item's latest covering expiry;
  - the result follows the order of `reasons`; info reasons are never in it. Each
    `Acknowledgement` carries its reason's `since`.
- **`drop_acceptances`:** each `accept_drop` entry in effect (with its source's state) as a
  `DropAcceptance` (`page` = `scope.page`, `year` = `scope.year`, the two minimums, `until` =
  `expires_at`), in
  file order.
- **`relevance_reasons`:** over items of kind `unparsed_unit` and `partial_unit`:
  `Reason("unparsed_relevant", f"relevant units unparsed: {n}")`, then
  `Reason("partial_relevant", f"relevant units partly parsed: {n}")`, each only when n > 0.
- **`present_keys`:** `reason_key` of every reason, plus `unit_key` of every `unparsed_unit`
  (`unparsed_relevant`) and `partial_unit` (`partial_relevant`) item, over its `unit_text`.
- **`next_health_state`** (written only on a published generation, Task 8): for each key named by
  a valid entry of this source that has not expired at `now`: `now` when the key is not in
  `present`, else the previous value when there is one. Keys of no such entry are dropped. The
  result has no problem. Its `reset_at` is `now` when `previous.problem` is set (review P4-05:
  the lost history could have voided an old acknowledgement), else `previous.reset_at`.

**`health_state.json`** is `{"last_absent_at": {key: "<Z timestamp>"}, "reset_at": "<Z timestamp>" | null}`
with sorted keys. Its problems, each giving `HealthState((), problem)`:

| Case | `problem` |
|---|---|
| not UTF-8 or not JSON | `"not JSON"` |
| not an object of exactly `last_absent_at` and `reset_at`, or `last_absent_at` is not an object | `"shape"` |
| a value that is not a timestamp with a time zone | `"timestamp of <key>"` |
| `reset_at` neither null nor a timestamp with a time zone | `"timestamp of reset_at"` |

- [ ] **Step 1: Write the failing tests.** `NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)`; a helper
  `entry(**changes)` gives the YAML text of one valid IPU `http_error` acknowledgement
  (`acknowledged_at` `NOW - 1 h`, `expires_at` `NOW + 6 days`) with the changes applied.
  - `tests/health/test_known_issues.py`:
    - **`test_acknowledgement_validity`** (parametrized; S4-T14, V2-T06; Review Focus 5). Each row:
      valid or the problem, and in effect at `NOW` or not:

      | Row | Change | Valid | In effect |
      |---|---|---|---|
      | Z | as built | yes | yes |
      | offset | `acknowledged_at: 2026-10-20T13:00:00+02:00` | yes | yes |
      | quoted | `acknowledged_at: "2026-10-20T11:00:00Z"` | yes | yes |
      | naive | `acknowledged_at: 2026-10-20T11:00:00` | `acknowledged_at must be a timestamp with a time zone` | — |
      | date only | `expires_at: 2026-10-25` | `expires_at must be a timestamp with a time zone` | — |
      | zero length | `expires_at` = `acknowledged_at` | `expires_at must be after acknowledged_at` | — |
      | reversed | `expires_at` an hour before | the same | — |
      | 14 days | `expires_at` = `acknowledged_at + 14 days` | yes | yes |
      | 14 days + 1 s | | `an acknowledgement lasts at most 14 days` | — |
      | now + 5 min | `acknowledged_at` = `NOW + 5 min`, `expires_at` + 1 day | yes | no (and in `not_yet_active`) |
      | now + 1 day | `acknowledged_at` = `NOW + 1 day` | yes | no |
      | now + 1 day + 1 s | | `acknowledged_at is more than 1 day in the future` | — |
      | at expiry | `expires_at` = `NOW` | yes | no |
      | 1 s before expiry | `expires_at` = `NOW + 1 s` | yes | yes |
    - **`test_malformed_known_issues`** (S4-T15; Review Focus 2): a tab in the indentation and a
      repeated `owner` key give `known_issues.yml is not valid YAML`; `{a: 1}` and a list of
      strings give `not a list` and `entry 1: not a mapping`; an empty file gives no entries and
      no problems; a missing file gives the same. Then one row per entry check of the table
      (missing `owner`, unknown `note`, a scope without `page`, source `cnn`, reason `oops`,
      `unit_text` with `http_error`, a scoped `unparsed_relevant`, `accept_units_seen_min` with
      `http_error`, an `accept_drop` without `accept_claims_min`, `accept_units_seen_min: -1`,
      `accept_claims_min: true`, stage `parse` for
      `http_error`, `explanation: "  "`). A file of one bad and one good entry gives one problem
      (`entry 1: …`) and one entry with `index == 2`.
    - **`test_never_acknowledgeable`** (S4-T15): one row per code of `NEVER_ACKNOWLEDGEABLE`
      gives `"<code> can never be acknowledged"`.
    - **`test_repository_file_is_empty_and_valid`:** `known_issues.yml` at the repository root
      loads with no entries and no problems.
  - `tests/health/test_acknowledge.py`:
    - **`test_acknowledgement_scope`** (S4-T14): an entry for (`ipu`, `http_error`,
      `{stage: fetch, year: null, page: null}`) acknowledges `Reason("http_error", "…")` of IPU;
      not the same reason of A-WEB; not one with `page="elections"`; not `timeout`; an entry with
      `page: elections` acknowledges only the `page="elections"` reason; `Reason("deadline", page="p3")`
      needs `page: p3`. Info reasons are never in the result. Two matching entries give the later
      `until`.
    - **`test_recurrence_voids_an_acknowledgement`** (NM-T07): the entry acknowledged at
      `NOW - 1 h`; a state with its key at `NOW - 2 h` → in effect; at `NOW - 30 min` → void.
      `next_health_state` with the key not present gives it `NOW`; present, it keeps the previous
      value; a key no entry names is dropped; an expired entry's key is dropped.
    - **`test_a_corrupt_health_state_voids_every_acknowledgement`** (Review Focus 2): the bytes
      `b"{"`, `[]`, `{"last_absent_at": {}}`,
      `{"last_absent_at": {"k": "2026-10-20T10:00:00"}, "reset_at": null}` and
      `{"last_absent_at": {}, "reset_at": "2026-10-20T10:00:00"}` give `not JSON`, `shape`,
      `shape`, `timestamp of k` and `timestamp of reset_at`; with such a state, `acknowledge` gives `()` and `drop_acceptances`
      leaves out that source; `state_problem_reason` gives `ack_invalid`
      `"health_state.json is corrupt: not JSON"`. A good state, with and without `reset_at`, round-trips through
      `health_state_to_dict` and `load_health_state`.
    - **`test_recovery_after_a_corrupt_state`** (P94; review P4-05): IPU's state is corrupt and
      OSCE's is good, and each source has an entry acknowledged at `NOW - 1 h`. IPU's entry is
      void and OSCE's in effect. `next_health_state` of IPU's state at `NOW` has no problem and
      `reset_at == NOW`. With that state, at `NOW + 1 day`, IPU's old entry is still void and an
      entry acknowledged at `NOW + 1 h` is in effect; the state written next keeps
      `reset_at == NOW`.
    - **`test_an_acknowledgement_never_covers_a_later_gap`** (P91): A-WEB's
      `Reason("coverage_gap", "calendar: …", page="calendar", year=2027, since=NOW - 2 h)` and an
      entry (`aweb`, `coverage_gap`, `{stage: parse, year: 2027, page: calendar}`) acknowledged at
      `NOW - 1 h` → acknowledged; the same reason with `since=NOW - 30 min` → not; with `since`
      None → acknowledged.
    - **`test_drop_acceptances`:** a valid `accept_drop` (`osce`, `cumulative_drop`,
      `{stage: snapshot, year: null, page: elections}`, minimums 30 units and 20 claims) gives
      `DropAcceptance("osce", "cumulative_drop", "elections", None, 30, 20, expires_at)`; expired,
      not yet active, or void by recurrence gives none; a plain acknowledgement of
      `cumulative_drop` gives none.
    - **`test_relevance_reasons`:** two `unparsed_unit` and one `partial_unit` item give
      `unparsed_relevant` "relevant units unparsed: 2" then `partial_relevant`
      "relevant units partly parsed: 1"; `provisional_change` and `disappeared_unit` items
      count for neither.
    - **`test_a_no_new_date_unit_can_be_acknowledged_until_it_changes`** (R16): EISA's two
      fixture unit items (Task 3) and two unit acknowledgements with their exact texts →
      `unparsed_relevant` acknowledged. The same texts with other `unit_id`s and `item_id`s (the
      rows reordered) → still acknowledged. The first text with `April` changed to `May` →
      not acknowledged.
    - **`test_an_inherited_country_change_reopens_an_acknowledgement`** (R16): the second text
      with `Libya (from the row above)` changed to `Chad (from the row above)` → not
      acknowledged; one entry missing → not acknowledged; a third entry for a text no item has
      changes nothing.
    - **`test_unit_acknowledgement_uses_the_full_text`** (P88; review P4-04): two `unparsed_unit`
      items whose `unit_text`s share their first 300 characters and end in `"District A"` and
      `"District B"`, so their `text`s are equal. An entry with the first full text leaves
      `unparsed_relevant` unacknowledged; one entry for each acknowledges it; an entry with the
      300-character `text` covers neither; the first full text with its spaces doubled still
      covers its item. The two items' `present_keys` differ.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/health -q`. Expected: FAIL
  (`elections_calendar.health` does not exist).
- [ ] **Step 3: Implement** `health.py`, `known_issues.yml` and the import-linter change.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(health): acknowledgements, accepted drops and recurrence state`.

  Mutations, one each:
  - the loader accepts repeated keys;
  - a naive timestamp is read as UTC;
  - a `date` is read as midnight UTC;
  - `MAX_ACK_LENGTH` is compared with `<`;
  - `MAX_ACK_AHEAD` is compared with `<`;
  - an entry stays in effect at its `expires_at`;
  - an entry is in effect before its `acknowledged_at`;
  - recurrence is ignored;
  - a corrupt state keeps acknowledgements;
  - the scope's `page` is ignored when matching;
  - the source is ignored when matching;
  - `NEVER_ACKNOWLEDGEABLE` is not checked;
  - a scoped `unparsed_relevant` entry is valid;
  - a unit acknowledgement matches when one item of the kind is covered;
  - `acknowledge` compares `item.text`;
  - `acknowledge` ignores a reason's `since`;
  - `in_effect` ignores `reset_at`;
  - `next_health_state` leaves `reset_at` unset after a corrupt state;
  - `accept_claims_min` is optional;
  - `accept_units_seen_min: true` is valid;
  - `next_health_state` keeps keys that no entry names;
  - `relevance_reasons` counts `provisional_change` items.

---

### Task 5: Match diagnostic, severity, verdict and source health (`health.py`, `feed.py`; §5.6, §9.4, §9.5; R11, R15)

**Files:**
- Modify: `elections_calendar/health.py`, `importlinter.ini` (`(feed)` loses its parentheses)
- Create: `elections_calendar/feed.py`, `tests/health/test_match.py`, `tests/health/test_verdict.py`,
  `tests/feed/__init__.py`, `tests/feed/test_source_health.py`, `tests/support/feed.py`

**Interfaces:**
- Consumes: `MergeResult`, `Child`, `Claim`, `Reason`, `REASON_LEVEL`, `REASON_STAGE`,
  `SOURCE_NAMES`, `_utc_iso` (model); `Window`; Task 2's `Decision`, `Snapshot`, `PageRecord`;
  Task 3's `unit_items`; Task 4's `Acknowledgement`, `HealthState`, `relevance_reasons`,
  `state_problem_reason`; `LedgerReport`; `SourceRun` (runner); `collapse_ws`.
- Produces in **`health.py`:**

```python
Severity = Literal["ok", "warning", "error"]
Verdict = Literal["green", "red"]

class MatchDiagnostic:
    eligible: int
    peers_fresh: int
    matched: int
    unmatched: int
    informative: bool

def match_diagnostic(result: MergeResult, claims: Sequence[Claim], source: str, *,
                     fresh: Collection[str], window: Window) -> MatchDiagnostic
def match_reason(diagnostic: MatchDiagnostic) -> Reason | None
def source_reasons(decision_reasons: Sequence[Reason], items: Sequence[AttentionItem],
                   match: MatchDiagnostic, state: HealthState) -> tuple[Reason, ...]
def severity(reasons: Sequence[Reason]) -> Severity
def unacknowledged(reasons: Sequence[Reason],
                   acknowledged: Sequence[Acknowledgement]) -> tuple[Reason, ...]
def verdict(open_reasons: Sequence[Reason]) -> Verdict
```

  - **`match_diagnostic`** (§9.5; the fixture values were measured by `match1.py`):
    - **eligible:** the children of cards with `window.bucket(card.span)` set, whose `level` is
      `national`, that are not `aggregate`, and that have a source whose claim is of `source`
      and not provisional;
    - **peers_fresh:** the number of other sources in `fresh` that have a claim in `claims` at
      the `place_id` of an eligible child;
    - **matched:** the eligible children with a source whose claim is of another source in
      `fresh` and not provisional; `unmatched = eligible - matched`;
    - **informative:** `peers_fresh >= 2 and eligible >= 5`.
  - **`match_reason`:** when informative and `matched == 0`,
    `Reason("no_cross_source_match", f"no other source lists any of its {eligible} in-window national contests")`;
    else None.
  - **`source_reasons`:** the decision's reasons, then `relevance_reasons(items)`, then the match
    reason, then `state_problem_reason(state)`; Nones dropped.
  - **`severity`:** the worst `REASON_LEVEL` among error and warning reasons, else `"ok"`.
  - **`unacknowledged`:** the error and warning reasons for which no acknowledgement has the same
    `code`, `stage` (`REASON_STAGE`), `year`, `page` and `since`, in order (P91: two gaps of one
    scope that began at different times are told apart).
  - **`verdict`:** `"red"` when any reason is of level error or warning, else `"green"`. The
    pipeline passes each source's `unacknowledged` reasons plus the run's reasons.
- Produces in **`feed.py`:**

```python
DownloadOutcome = Literal["ok", "http_error", "timeout", "tls_error", "dns_error", "challenge_page",
                          "api_error", "layout_not_recognised", "not_published_yet", "deadline",
                          "fetch_failed", "worker_failed"]          # §5.6 plus P96
MAX_SAMPLES: Final = 5
MAX_SAMPLE_TEXT: Final = 200

class SourceResult:                  # one source's run, as the pipeline assembled it (Task 8)
    source: str
    run: SourceRun
    parse_ms: int
    ledger: LedgerReport | None      # None when parsing failed
    decision: Decision
    items: tuple[AttentionItem, ...] # unit_items(decision)
    match: MatchDiagnostic
    reasons: tuple[Reason, ...]      # source_reasons(...)
    acknowledged: tuple[Acknowledgement, ...]
    severity: Severity

def reason_dict(reason: Reason) -> dict[str, Any]
    # {code, level, stage, year, page, text}; text = detail or code
def source_health_entry(result: SourceResult) -> dict[str, Any]
```

  **`source_health_entry`** keys, in this order. "Pages" are the candidate's `PageRecord`s.

  | Key | Value |
  |---|---|
  | `source`, `name` | the key; `SOURCE_NAMES[source]` |
  | `download` | `{outcome, stage, http_status, final_url, content_type, bytes, elapsed_ms, attempts, error, pages}` |
  | `parse` | `{parser_version, parse_ms, units {seen, parsed, partial, unparsed, ignored}, claims, ignored_reasons, relevance {in_or_after_window, unknown, before_window}, unparsed_samples}` |
  | `coverage` | `{per_year {key: {requested, units_seen, outcome}}}` |
  | `snapshot` | `{acceptance, using_fallback, served_snapshot_id, served_fetched_at, baseline_units_seen, comparable}` (`SnapshotHealth`) |
  | `match` | `{eligible, peers_fresh, matched, unmatched, informative}` |
  | `severity` | the result's |
  | `reasons` | `[reason_dict(r)]` in order |
  | `acknowledged` | `[{code, until, stage, year, page}]` in order |

  - **`download.outcome`:** `deadline` when the run outcome is `deadline` or `scrape_deadline`;
    `worker_failed` for `worker_failed`; else the first page whose outcome is a download failure
    (`PAGE_REASONS[outcome]`, so `unfinished` is `deadline`); else `layout_not_recognised` when a
    page has it; else `not_published_yet` when a page or reason has it; else `ok`.
  - **The representative page** is the page that gave the outcome, else the first page with a
    download. `stage`, `http_status`, `final_url`, `content_type` and `error` are its download's
    (None without one; `error` falls back to the run's `detail` for `worker_failed` and the
    deadlines, or None when that is empty). `bytes`, `elapsed_ms` and `attempts` are sums over
    every page's download.
  - **`download.pages`:** `requested` = the number of pages; `ok` = pages `ok` or `valid_empty`;
    `failed` = pages that are none of `ok`, `valid_empty`, `not_published_yet`;
    `stop_reason` = `"pagination_incomplete"` when a reason has that code, else the run outcome.
  - **`parse`:** `parser_version` is the candidate's; `units`, `ignored_reasons` (sorted by key)
    and `relevance` come from the ledger report (all zero and `{}` when it is None); `claims` is
    the number of candidate claims; `unparsed_samples` are the texts (`collapse_ws`, cut to
    `MAX_SAMPLE_TEXT`) of the first `MAX_SAMPLES` candidate units with outcome `unparsed` and
    relevance not `before_window`.
  - **`coverage.per_year`:** pages grouped by `year` (`str(year)`, or `"all"` for None), years
    ascending then `"all"`: `requested` pages, the sum of `units_seen`, and `outcome` =
    `"ok"` when every page is `ok` or `valid_empty`, else the first other page outcome.
  - Timestamps are `_utc_iso`. Every text is already capped (Tasks 1–4).

**`tests/support/feed.py`** gives Tasks 5–7 a first run over the fixtures, as Task 8's pipeline
will do it. Task 9 checks the pipeline against the same values, so the two cannot drift apart.
- `RUN_NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)` (P100).
- `FIXTURE_FETCHED`: each source's fetch time from its `PROVENANCE.md`, given to every page of the
  source: ElectionGuide `2026-10-16T14:39:00Z`, Wikipedia `2026-10-17T16:13:00Z`, OSCE and IPU
  `2026-10-18T11:18:37Z`, A-WEB `2026-10-18T11:18:38Z`, Carter and EEAS `2026-10-18T11:18:40Z`,
  NDI `2026-10-19T08:57:34Z`, EISA `2026-10-19T08:57:41Z`. The fixture `RawPages` of NDI and
  EISA carry the wall-clock time of the test run (their `fetch` stamps `datetime.now`), so the
  helper always re-stamps with `dataclasses.replace`.
- `fixture_snapshot(source) -> tuple[RawPages, ParseResult, Snapshot, LedgerReport]`: the
  re-stamped raw pages, the fixture result, `build_snapshot(…, parser_version=PARSER_VERSION,
  registry_version=registry_version(), years=window_for(RUN_NOW).years)` and `ledger.check`.
- `first_run() -> FirstRun(window, sources: dict[str, SourceResult], merge: MergeResult, claims)`,
  cached: per source in `SOURCE_ORDER`, `decide` with no baseline, a `complete` run and no
  acceptances, then `unit_items`; one `merge` of every decision's `claims` at `RUN_NOW`; then per
  source `match_diagnostic` (every promoted source fresh), `source_reasons` with an empty state,
  no acknowledgements, and `severity`. `run` is `SourceRun(source, raw, "complete", 0)` and
  `parse_ms` 0.

- [ ] **Step 1: Write the failing tests.**
  - `tests/health/test_match.py`:
    - **`test_match_diagnostic`** (S4-T16; synthetic merge results built with
      `tests/support/claims.py`):
      - a subnational child, an aggregate child, a child outside the window and a child whose
        only claim of the source is provisional are not eligible;
      - a peer that is not in `fresh` does not count, and neither does a peer's provisional
        claim;
      - 5 eligible and 2 peers → informative; 4 eligible or 1 peer → not;
      - informative with `matched == 0` → `no_cross_source_match` "no other source lists any of
        its 5 in-window national contests"; not informative → None.
    - **`test_match_diagnostic_on_the_fixtures`** (S4-T16): the fixture merge
      (`fixture_claims()`, `FIXTURE_NOW`), every source fresh:

      | Source | eligible | peers_fresh | matched | unmatched | informative |
      |---|---|---|---|---|---|
      | electionguide | 46 | 8 | 38 | 8 | yes |
      | osce | 7 | 5 | 7 | 0 | yes |
      | wikipedia | 54 | 8 | 37 | 17 | yes |
      | ndi | 7 | 7 | 5 | 2 | yes |
      | aweb | 3 | 6 | 3 | 0 | no |
      | eisa | 6 | 6 | 5 | 1 | yes |
      | ipu | 18 | 7 | 14 | 4 | yes |
      | carter | 0 | 0 | 0 | 0 | no |
      | eeas | 0 | 0 | 0 | 0 | no |

      No source gets `no_cross_source_match`.
    - **`test_osce_column_shift_is_an_error`** (S4-T16; measured by `osce_shift.py`), on the
      OSCE fixture page:
      - a `<th>Type</th>` column inserted after `Country`, with a `<td>-</td>` in each of the
        634 rows → the same 180 claims as the fixture (columns are found by header);
      - the `Activity` header removed → page outcome `layout_not_recognised`, detail
        `"0 tables with headers date, country, election, activity"`, no units; `decide` with the
        fixture snapshot as baseline → `fallback`, `severity` `error`;
      - the `Election` header renamed `Contest` → the same.

      The shift is caught by the layout check, before any match diagnostic.
  - `tests/health/test_verdict.py`:
    - **`test_severity`:** `()` → ok; info only → ok; a warning → warning; a warning and an
      error → error.
    - **`test_acknowledgements_change_only_the_verdict`** (S4-T14, V2-T06). IPU with its page
      `http_error`, the fixture snapshot as baseline:
      - without an entry: `fallback`, severity `error`, `unacknowledged` holds the `http_error`
        reason, verdict red;
      - with an acknowledgement in effect (scope `{stage: fetch, year: null, page: elections}`,
        since `coverage_reasons` names the page): the same acceptance, severity and reasons;
        `acknowledge` lists it; `unacknowledged` is `()`; verdict green;
      - with an acknowledgement of `sudden_drop` for a drop, the candidate is still
        `quarantined`; with an `accept_drop` for it (via `drop_acceptances`), it is `promoted`
        with `count_change`;
      - **a coverage gap** (P91): an A-WEB decision with one gap (baseline `calendar` of 2026
        listing Gambia 5 December 2026, a 2027 candidate without it, `now`
        2027-01-02T06:00Z). With an entry for `coverage_gap` (scope
        `{stage: parse, year: 2027, page: calendar}`) acknowledged after the gap's `since` and in
        effect: the reason is still in `reasons`, severity `warning`, `acknowledge` lists it,
        `unacknowledged` is `()`, verdict green. At the entry's `expires_at`: unacknowledged,
        verdict red. An entry acknowledged before the gap's `since`: unacknowledged, verdict red.
        Two `coverage_gap` reasons of `calendar`, year 2027, with their `since` before and after
        the entry's `acknowledged_at`: `acknowledge` lists only the first, and `unacknowledged`
        holds only the second.
    - **`test_source_reasons_order`:** decision reasons, then `unparsed_relevant`, then
      `partial_relevant`, then `no_cross_source_match`, then the state's `ack_invalid`.
  - `tests/feed/test_source_health.py` (entries of `first_run()`'s sources unless a row says
    otherwise):
    - **`test_source_health_entry_keys`:** the key order of the table for every source; `name`
      is `SOURCE_NAMES`'; NDI `download.pages == {requested: 2, ok: 2, failed: 0, stop_reason: "complete"}`;
      ElectionGuide `coverage.per_year` has the key `"all"` with `requested` 3 and `units_seen`
      351; EISA `download.outcome` is `not_published_yet` and its `per_year` is
      `{"2026": {requested: 1, units_seen: 22, outcome: "ok"}, "all": {requested: 1, units_seen: 0, outcome: "ok"}}`.
    - **`test_health_lists_coverage_gaps_and_ignored_reasons`** (R11): each source's
      `parse.ignored_reasons` equals its ledger report's, with sorted keys (IPU:
      `{"appointed_chamber": 28, "inactive_chamber": 10, "no_expected_date": 5}` in that order;
      EEAS: `{"empty_cell": 7, "year_heading": 4}`; measured by `health1.py`); a candidate with an
      A-WEB `coverage_gap` note lists `{code: coverage_gap, level: warning, stage: parse, …}`,
      and its severity is `warning` while its acceptance is `promoted`.
    - **`test_health_reports_chain_length_and_missing_pages`** (R15): an NDI baseline of three
      pages in scope `pages` against the two-page fixture candidate → `count_change`
      "pages: 3 pages, now 2"; a candidate with a `pagination_incomplete` note → `stop_reason`
      `"pagination_incomplete"` and the reason listed with level `error`.
    - **`test_download_outcomes`** (parametrized): run `deadline` → `deadline`; run
      `worker_failed` with detail `"parse: ValueError"` → `worker_failed`, `error`
      `"parse: ValueError"`; page `p2` `timeout` → `timeout` with `p2`'s `final_url`; a page
      `unfinished` → `deadline`; a page `layout_not_recognised` → `layout_not_recognised`; all
      `ok` → `ok`, `bytes` the sum.
    - **`test_unparsed_samples_are_capped`:** seven relevant unparsed units of 500 characters →
      five samples of 200 characters; a `before_window` unparsed unit is not sampled.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/health tests/feed -q`.
  Expected: FAIL.
- [ ] **Step 3: Implement** the `health.py` additions and `feed.py`'s `SourceResult`,
  `reason_dict` and `source_health_entry`.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(health): match diagnostic, severity, verdict and source health entries`.

  Mutations, one each:
  - eligible children include subnational ones;
  - a provisional claim of the source makes a child eligible;
  - a non-fresh peer counts;
  - informative needs 3 peers;
  - `match_reason` fires when not informative;
  - `severity` lets info raise it;
  - `unacknowledged` ignores `page`;
  - `unacknowledged` ignores `since`;
  - `verdict` is green with an open warning;
  - `source_reasons` drops the state problem;
  - `download.outcome` ignores the run outcome;
  - `unfinished` pages map to `timeout`;
  - `stop_reason` ignores `pagination_incomplete`;
  - `per_year` sums `units_seen` over every year;
  - `ignored_reasons` keys keep the ledger's order (IPU's are unsorted);
  - samples are not cut.

---

### Task 6: The feed document and its bytes (`feed.py`, `publish.py`; §5.3–§5.5, §5.7; P84–P87, P97, P103; R5, R17, R20, R24, R26; NM-T04)

**Files:**
- Modify: `elections_calendar/feed.py`, `importlinter.ini` (`(publish)` loses its parentheses)
- Create: `elections_calendar/publish.py`, `tests/feed/test_feed.py`, `tests/feed/test_publish.py`

**Interfaces:**
- Consumes: `MergeResult`, `Card`, `Child`, `ChildSource`, `BibEntry`, `UndatedListing`,
  `AttentionItem`, `Disposition`, `Reason`, `SOURCE_NAMES`, `SOURCE_ORDER`, `canonical_json`,
  `_utc_iso` (model); `Window`; `PARSER_VERSION`; Task 5's `SourceResult`, `reason_dict`,
  `source_health_entry`, `severity`; `tests/support/feed.py`'s `first_run()`.
- Produces in **`feed.py`:**

```python
MAX_FEED_ITEMS: Final = 500

class RunInfo:
    code_sha: str                    # 40 hex characters, or "local"
    trust_sources: tuple[str, ...]   # ScrapeRun.trust_sources

class FeedParts:
    doc: dict[str, Any]              # elections.json, with content_id and published_at None
    attention_full: dict[str, Any]   # {"items": [...]}: every item, uncapped
    dispositions: dict[str, Any]     # {"dispositions": [...]}: every disposition
    run_reasons: tuple[Reason, ...]  # the given ones, then attention_truncated
    severity: Severity               # the run's

def build_feed(result: MergeResult, sources: Sequence[SourceResult], *, window: Window,
               now: datetime, run: RunInfo, run_reasons: Sequence[Reason]) -> FeedParts
```

**What is serialised** (P85). "In the feed" means: the cards with `window.bucket(card.span)`
set, their children, and the undated listings whose item is in the capped list. Every
`possible_matches` list in the feed keeps only the child ids that are in it, and
`possible_matches_outside` beside it is the number of distinct ids left out, counted before the
filter (P85; `possible_matches` is sorted and unique). An item whose every candidate is outside
keeps its kind and reason: its `possible_matches` is `[]` and its `possible_matches_outside`
is not 0, which is never read as "no candidate".

**The items.** All items are `result.attention` plus each source's `items`, in no particular
order.
- **`attention_full`** holds all of them, sorted by `item_id`, each as the feed item dict plus
  `merge_ids` (a list), `unit_id` and `unit_text`, with `possible_matches` unfiltered
  (`possible_matches_outside` as in the feed).
- **The feed's list** holds the items whose relevance is not `before_window`, in cap order
  (P87): `in_or_after_window` before `unknown`, then `date` ascending with None last, then
  `item_id`. Only the first `MAX_FEED_ITEMS` are kept.
- **`attention_truncated`** is the number left out. When it is above 0,
  `Reason("attention_truncated", f"attention items left out of the feed: {n}")` follows the given
  run reasons.

**Dicts, with keys in this order:**

| Record | Keys |
|---|---|
| card | `date`, `country`, `type`, `status`, `sources`, `source_names`, `links`, `group_id`, `end_date`, `date_precision`, `date_meaning`, `date_status`, `level`, `place_id`, `country_code`, `children`, `umbrella_sources`, `umbrellas` |
| child (P84) | `child_id`, `jurisdiction`, `jurisdiction_kind`, `institution`, `office_class`, `office_label`, `kind`, `round`, `indirect`, `aggregate`, `occurrence_confirmed`, `status_conflict`, `date_conflict`, `unverified`, `ambiguous`, `rescheduled_from`, `provisional_date`, `possible_matches`, `possible_matches_outside`, `sources` |
| child source | `name`, `link`, `source_event_id`, `date`, `end_date`, `date_precision`, `date_text`, `date_meaning`, `date_status`, `status_claim`, `fetched_at`, `fallback`, `provisional`, `evidence_kind`, `selected`, `rejected_reason` |
| umbrella (R24) | `name`, `link`, `office_label`, `date_text`, `children` |
| bibliography entry | `name`, `link` |
| undated listing | `undated_id`, `place_id`, `country`, `office_label`, `year`, `sources`, `possible_matches`, `possible_matches_outside` |
| item | `item_id`, `kind`, `source`, `link`, `snapshot_id`, `relevance`, `date`, `text`, `reason`, `possible_matches`, `possible_matches_outside`, `undated_id` |

- `name` is `SOURCE_NAMES[source]` (P97). An item's `source` is the source key.
- A card's `date`, `end_date` and `date_precision` are its span's `start`, `end` and
  `precision`; a child source's are its claim's span's (`date` and `end_date` None for a year
  span). Dates are ISO strings; `fetched_at` is `_utc_iso`.
- `source_names` and `links` are the names and links of the card's `sources`, in order.
- An umbrella's `children` are the sorted ids of the card's children among the targets of that
  umbrella claim's `umbrella_link` disposition.
- Tuples become lists; every other value is the record's.

**The document's keys, in this order:**

| Key | Value |
|---|---|
| `schema_version` | `2` |
| `content_id` | None (set by `publish.feed_bytes`) |
| `generated_at` | `_utc_iso(now)` |
| `published_at` | None (set by `publish.feed_bytes`) |
| `data_as_of` | the oldest `served_fetched_at` among the sources with a served snapshot, or None |
| `current_month` | `window.current_month` |
| `window` | `{months: [window.month_keys], years: [window.years]}` |
| `months` | `{key: [cards in that bucket, in the merge's order]}` for every month key, in order |
| `undated` | the listings in the feed, sorted by `undated_id` |
| `attention_items` | the capped list |
| `attention_truncated` | the number left out |
| `source_health` | `source_health_entry` of each source, in `SOURCE_ORDER` |
| `run` | `{parser_version: PARSER_VERSION, code_sha, trust_sources, merge_checks: {conservation: "ok"}, severity, reasons: [reason_dict]}` |
| `errors` | one line per error or warning reason: `f"{name}: {code}: {detail}"` for each source's reasons in `SOURCE_ORDER`, then `f"Run: {code}: {detail}"`; `: {detail}` is left out when the detail is empty |

The run's `severity` is the worst of the sources' severities and `severity(run_reasons)`.

- Produces in **`publish.py`:**

```python
FEED_BUDGET_BYTES: Final = 524_288   # R26: 512 KiB, the user's decision of 2026-10-20

def content_id(doc: Mapping[str, Any]) -> str
def feed_bytes(doc: Mapping[str, Any], *, published_at: datetime) -> bytes
def write_atomic(path: Path, data: bytes) -> None
def write_manifest(out: Path) -> dict[str, Any]
```

  - **`content_id`** (P103): the SHA-256 hex of `canonical_json` of
    `{"months": …, "undated": …, "attention_items": …, "snapshots": [[source, served_snapshot_id], …]}`
    after every `fetched_at` key is removed at any depth. `snapshots` follows the document's
    `source_health` order.
  - **`feed_bytes`:** a copy of `doc` with `content_id` set and `published_at` =
    `_utc_iso(published_at)`, as `json.dumps(…, ensure_ascii=False, separators=(",", ":"))` plus
    `"\n"`, UTF-8. Key order is the document's; nothing is sorted.
  - **`write_atomic`:** creates the parent directories, writes `<name>.tmp` beside the target,
    flushes and `os.fsync`s it, then `os.replace`s it onto the target. When any step fails, the
    `.tmp` file is removed and the error propagates; the target is unchanged.
  - **`write_manifest`:** `{"schema_version": 1, "files": {path: sha256 hex}}` over every file
    under `out` except `manifest.json` and `*.tmp`, with paths relative to `out` in POSIX form,
    sorted; written with `write_atomic(out / "manifest.json", stored_json(…))` and returned.

- [ ] **Step 1: Write the failing tests.** `run = RunInfo("local", ())` unless a row says
  otherwise.
  - `tests/feed/test_feed.py`:
    - **`test_feed_serialises_every_merge_record`** (R17; measured by `feed1.py`, `feed2.py`):
      the `first_run()` feed has:
      - month keys `2026-09` … `2027-01` with 22, 30, 28, 15 and 5 cards (100), 202 children and
        274 child sources;
      - 31 undated listings and 157 items (36 from the merge, 121 units), `attention_truncated` 0;
      - `attention_full` with 188 items (67 from the merge with `merge_ids`, 121 with
        `unit_id` and `unit_text`), sorted by `item_id`, and `dispositions` with 1335 entries;
        no feed item has a `unit_text` key;
      - the key orders of the table for one card, child, child source, umbrella, listing and
        item;
      - for card `54b356d5b5ea` (Brazil, 4 October), each value equals its `Card` record's,
        mapped as above.
    - **`test_possible_matches_never_dangle`** (P85): every `possible_matches` id in the feed is a
      `child_id` in the feed, and every item's `undated_id` is a listing in the feed; the 36
      merge items kept 1 of their 16 possible matches and their `possible_matches_outside`
      sum to 15; at least one merge item has `possible_matches == []` and
      `possible_matches_outside > 0`, with the kind `unresolved_evidence` and the reason of its
      `attention_full.json` entry; for every child, listing and item, the kept ones plus
      `possible_matches_outside` are its record's number of possible matches.
    - **`test_attention_cap_sets_attention_truncated`** (R17): a synthetic source with 501 unit
      items (300 `in_or_after_window` with dates, 100 `in_or_after_window` without, 101
      `unknown`) → 500 items in cap order (dated ones by date, then undated ones by `item_id`,
      then `unknown`), `attention_truncated` 1, run reason `attention_truncated` "attention items
      left out of the feed: 1" (level warning), run severity at least `warning`; `attention_full`
      still has all 501. An undated listing whose item is cut is not in `undated`.
    - **`test_unit_and_claim_attention_items_share_one_list`** (R20): in the `first_run()` feed,
      unit and merge items are in one list, in cap order, with unique `item_id`s; the first item
      is `in_or_after_window` and the last 31 are `unknown`.
    - **`test_feed_serialises_rescheduling_and_provisional_date`** (R24): with
      `tests/support/claims.py`, `cl(f"{EGU}/r1")` and
      `cl("osce:elections/r1", provisional=True, span=day(2026, 12, 6))` (as in
      `tests/merge/test_cards.py`) give one child with `provisional_date` `"moved"`,
      `date_conflict` true, and an OSCE source with `provisional` true, `selected` false and
      `rejected_reason` `"provisional"`. `cl("eisa:y2026/r3", status_claim="postponed", previous_date_text="1 November 2026")`
      gives `rescheduled_from` `["1 November 2026"]` and the card `status` `"Upcoming"`.
    - **`test_umbrella_link_targets_children_in_the_feed`** (R24; measured by `umb1.py`): the
      `first_run()` feed has 16 umbrellas; each one's `children` are ids of its card's children;
      card `811a20289c2a` (South Sudan, December 2026) has the EISA umbrella with children
      `["31ce89602954", "6f60dcabc9d2"]`, two of its three.
    - **`test_unknown_meaning_observation_never_makes_held_or_ongoing`** (R5, the legacy-feed
      case of Plan 3's test): a Wikipedia calendar claim for Grenada on 5 November 2026 and an
      EEAS observation for Grenada (`test_select.py`'s `OBS` fields, span `year(2026)`,
      `status_claim="held"`) give a card with `date` `"2026-11-05"` and `status` `"Upcoming"`,
      whose child lists the observation with `selected` false and `rejected_reason`
      `"observation"`. The observation alone gives no card, and one `unresolved_evidence` item.
      In the `first_run()` feed, no selected child source has `evidence_kind` `"observation"`.
    - **`test_data_as_of_is_the_oldest_served_fetch`** (Review Focus 1): `first_run()` gives
      `"2026-10-16T14:39:00Z"`. Synthetic sources served at `T1 < T2`, one of them a fallback
      from `T0 < T1`, and one `unavailable` → `_utc_iso(T0)`; no served source → None.
    - **`test_errors_lines`:** an IPU `http_error` with detail `"elections"` gives
      `"IPU: http_error: elections"`; a run `ack_invalid` gives `"Run: ack_invalid: …"`; info
      reasons give no line; a reason without detail gives `"EISA: unparsed_relevant"` style
      lines without the trailing colon.
  - `tests/feed/test_publish.py`:
    - **`test_feed_size_is_within_the_budget`** (R26): `feed_bytes` of the `first_run()` feed is
      at most `FEED_BUDGET_BYTES`; the failure message gives the size and the budget.
    - **`test_feed_bytes`:** they end with `b"\n"`, decode to the document with `content_id` and
      `published_at` set, keep the document's key order, and are byte-identical for two builds.
    - **`test_same_evidence_shares_a_content_id`** (NM-T04): the `first_run()` document, and a
      copy with every `fetched_at` moved by a day and another `generated_at`, have the same
      `content_id` and different bytes; one child source's `date` changed, or one source's
      `served_snapshot_id` changed, gives another `content_id`.
    - **`test_write_atomic`:** writes new and existing files; with `os.replace` patched to raise,
      the old content stays, no `.tmp` file is left, and the error propagates.
    - **`test_manifest_lists_every_file`:** files `a.json`, `data/sources/osce/baseline.json` and
      a stray `x.tmp` give the two paths (POSIX, sorted) with their SHA-256; `manifest.json`
      itself is not listed.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/feed -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `build_feed` and `publish.py`.
- [ ] **Step 4: Run** the full suite. Expected: PASS. Record the fixture feed's size in the
  ledger (expected within a few kilobytes of 393,152 bytes, `feed3.py`; 361,114 without P84's
  per-source fields and P85's counts).
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(feed): the v2 feed document, the cap, content id and atomic writes`.

  Mutations, one each:
  - cards outside the window are serialised;
  - a child keeps `place_id`;
  - possible matches are not filtered;
  - `possible_matches_outside` counts the kept ones;
  - a child source leaves out `status_claim`;
  - `before_window` items stay in the feed;
  - the cap sorts `unknown` first;
  - undated items sort before dated ones;
  - `MAX_FEED_ITEMS` is 501;
  - a listing is serialised although its item was cut;
  - an umbrella's `children` are all its targets;
  - `name` is the source key;
  - `data_as_of` is the newest fetch;
  - `content_id` keeps `fetched_at`;
  - `content_id` leaves out the snapshot ids;
  - `feed_bytes` sorts keys;
  - `write_atomic` writes the target directly;
  - the manifest lists `manifest.json`;
  - `errors` lists info reasons.

---

### Task 7: `status.json`, `HEALTH.md`, the schemas and validation (`feed.py`, `validate.py`; §5.8, §11.3; P96, P104; S4-T06, S4-T19, NM-T04)

**Files:**
- Modify: `elections_calendar/feed.py`, `pyproject.toml`, `importlinter.ini` (`(validate)` loses
  its parentheses)
- Create: `elections_calendar/validate.py`, `schemas/feed-v2.schema.json`,
  `schemas/status-v1.schema.json`, `tests/feed/test_status.py`, `tests/feed/test_health_md.py`,
  `tests/feed/test_validate.py`, `tests/fixtures/feed/2026-10-16-ff30417.json` (the exact bytes of
  `git show ff30417:elections.json`, 27,557 bytes; `.gitattributes` keeps `tests/fixtures/**`
  byte-exact) and `tests/fixtures/feed/PROVENANCE.md` (the commit, the command and the SHA-256)

**Interfaces:**
- Consumes: Task 6's `FeedParts`, `build_feed`, `feed_bytes`, `FEED_BUDGET_BYTES`; Task 5's
  `SourceResult`, `reason_dict`, `DownloadOutcome`; Task 4's `Entry`, `UNIT_REASONS`,
  `REASON_STAGE`, `NEVER_ACKNOWLEDGEABLE`; Task 2's `Acceptance`; `collapse_ws`; `jsonschema`.
- Produces in **`feed.py`:**

```python
AttemptOutcome = Literal["published", "validation_failed"]   # Plan 5 adds superseded, paused, republished
                                                             # (not model.Outcome, a unit's outcome)

class Attempt:
    attempt_at: datetime
    run_id: str           # GITHUB_RUN_ID when it is all digits, else "local"
    trigger: str          # GITHUB_EVENT_NAME when it matches [a-z_]+, else "local"
    code_sha: str         # GITHUB_SHA when it is 40 lowercase hex characters, else "local"
    @property
    def attempt_id(self) -> str: ...   # f"{attempt_at:%Y%m%dT%H%M%SZ}-{run_id}" (UTC)

def attempt_of(environ: Mapping[str, str], now: datetime) -> Attempt
def status_doc(*, attempt: Attempt, outcome: AttemptOutcome, severity: Severity,
               sources: Sequence[SourceResult], run_reasons: Sequence[Reason],
               serving: bytes | None) -> dict[str, Any]
def md_text(value: object) -> str
def health_md(parts: FeedParts, *, sources: Sequence[SourceResult], outcome: AttemptOutcome,
              verdict: Verdict, severity: Severity, feed_size: int | None, budget: int,
              problems: Sequence[str], not_yet_active: Sequence[Entry]) -> str
```

  - **`status_doc`** keys, in order (§5.8): `schema_version` 1, `attempt_id`, `attempt_at`,
    `trigger`, `code_sha`, `outcome`, `severity`, `reasons`, `serving_feed_sha256`,
    `serving_published_at`, `serving_generated_at`, `serving_content_id`, `sources`,
    `acknowledged`.
    - `reasons`: `{source, code, level, text, page, year, acknowledged}` for each error and
      warning reason, sources in `SOURCE_ORDER` then the run's (`source` null, `acknowledged`
      false).
    - The `serving_*` fields describe `serving`: the new feed's bytes when `published`, the
      repository's current `elections.json` when `validation_failed` (None when it has none, which
      makes all four null). The digest is `sha256(serving).hexdigest()`; the other three are the
      string values of `published_at`, `generated_at` and `content_id` in it, or null when it is
      not JSON or has no such string (v1's feed).
    - `sources`: `{name, severity, using_fallback, served_fetched_at}` per source.
    - `acknowledged`: `{source, code, until, stage, year, page}` for each source's
      acknowledgements (review: the scope tells same-code reasons on two pages apart).
  - **`md_text`:** `str(value)`, `collapse_ws`, every remaining control character (Unicode
    category `Cc`) dropped, then a backslash before every character of `string.punctuation`.
    Every value from a source, a file or a reason goes through it.
  - **`health_md`** sections, in order:

    | Section | Content |
    |---|---|
    | `# Elections calendar health` | bullets: Generated, Outcome (`published` or `validation failed`), Verdict, Severity (the run's, as given), Data as of, Feed (`<n> bytes of a <budget> byte budget`, plus `, over budget` when n > budget; `no feed` when `feed_size` is None, after a merge failure) |
    | `## Run` | each run reason and each validation problem as a bullet, or `No run reasons.` |
    | `## Sources` | a table: Source, Severity, Acceptance, Served data fetched, Open reasons (the count of error and warning reasons not acknowledged) |
    | `## <Name>`, per source in `SOURCE_ORDER` | bullets: Download, Parse, Ignored (`code n, …` sorted, or `none`), Coverage (`year: pages, units, outcome; …`), Snapshot, Match |
    | `### Reasons` | per reason: `**level** code: text`, then ` — acknowledged until <iso>`, or ` — cannot be acknowledged` (`NEVER_ACKNOWLEDGEABLE`), or ` — acknowledge each unit by its full text (unit_text in attention_full.json)` (`UNIT_REASONS`), or ` — to acknowledge: scope {stage: <s>, year: <y or null>, page: <p or null>}`, followed for `DROP_REASONS` by `; to accept the drop: accept_drop with this scope and the candidate's counts`; info reasons get nothing |
    | `### Unparsed samples`, `### Provisional changes`, `### No longer listed` | the samples, then the texts of the source's `provisional_change` and `disappeared_unit` items; a section with nothing is left out |
    | `## Not yet active` | `entry <n>: <source> <reason>, from <acknowledged_at>`; left out when empty |
    | `## Attention items` | a table of the feed's items: Kind, Source, Date, Text; then `and <n> more in attention_full.json` when truncated |

    Each source section is its source health entry (the feed's) rendered; nothing is recomputed.
- Produces in **`validate.py`:**

```python
FEED_MAX_BYTES: Final = 2_000_000
MAX_AHEAD: Final = timedelta(minutes=10)
SCHEMAS: Final = Path(__file__).resolve().parents[1] / "schemas"   # the repository's schemas/
FEED_SCHEMA: Final = SCHEMAS / "feed-v2.schema.json"
STATUS_SCHEMA: Final = SCHEMAS / "status-v1.schema.json"

class ServedCheck:
    source: str
    snapshot_id: str | None
    ledger_ok: bool
    discovery_ok: bool

def validate_feed(data: bytes, *, served: Sequence[ServedCheck], wall_clock: datetime) -> tuple[str, ...]
def validate_status(data: bytes) -> tuple[str, ...]
```

  `validate_feed` returns the problems, `()` when valid, each prefixed by its check; checks run
  in this order and all of them run when the bytes are JSON:

  | Check (§11.3) | Problem text |
  |---|---|
  | 1. JSON and the schema (`jsonschema.Draft202012Validator`, every error, sorted by path) | `"json: not UTF-8 JSON"`, `"schema: <path>: <message>"` |
  | 2. the legacy contract: each card's `date` is `YYYY-MM-DD`, `country` non-empty, `type` a string, `status` a legacy value, `sources` a list of `{name, link}` strings, `source_names` and `links` equal to its `sources`' | `"legacy: <group_id>: <what>"` |
  | 3. the feed's invariants: unique `group_id`s, `child_id`s, `undated_id`s and `item_id`s; each card in the first month of `window.months` that its `date`–`end_date` overlaps; each `possible_matches` id is a child in the feed; each item's `undated_id` is in `undated`; each umbrella's `children` are its card's; at most 500 items; exactly one selected source per child | `"invariant: <what>"` |
  | 4. size | `"size: <n> bytes is over 2000000"` |
  | 5. `generated_at` and `published_at` are at most `MAX_AHEAD` after `wall_clock` | `"timestamp: <field> is <iso>, more than 10 minutes ahead of <iso>"` |
  | 6. each source health entry's `served_snapshot_id` equals its `ServedCheck`'s, and both checks are true | `"served: <source>: <what>"` |

  `<what>` is the implementer's wording; the tests check the prefix and the named record.
  An `unavailable` source has `ServedCheck(source, None, True, True)`: nothing is served, so
  check 6 compares its null `served_snapshot_id` with None and passes (P93).

  **The schemas** are Draft 2020-12 with `additionalProperties: false` on every object and every
  key required. Each enum equals its Literal: `Kind`, `OfficeClass`, `Level`,
  `JurisdictionKind`, `Precision`, `DateMeaning`, `DateStatus`, `StatusClaim`, `LegacyStatus`, `EvidenceKind`,
  `RejectedReason`, `ProvisionalDate`, `AttentionKind`, `Relevance`, `Acceptance`,
  `DownloadOutcome`, `Severity`, `ReasonCode`, `ReasonLevel`, `Stage`. Timestamps match
  `^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$`; dates
  `^[0-9]{4}-[0-9]{2}-[0-9]{2}$`; ids `^[0-9a-f]{12}$`; `content_id` and snapshot ids
  `^[0-9a-f]{64}$`. `status-v1`'s `outcome` enum is §5.8's five values.

  `pyproject.toml` gains a mypy override: `ignore_missing_imports = true` for `jsonschema` and
  `jsonschema.*`.

- [ ] **Step 1: Write the failing tests.**
  - `tests/feed/test_status.py`:
    - **`test_attempt_of`:** `GITHUB_RUN_ID=123`, `GITHUB_EVENT_NAME=schedule` and a 40-hex
      `GITHUB_SHA` at `2026-10-19T12:00:00Z` give `attempt_id` `"20261019T120000Z-123"`; an
      empty environment gives `local` for all three; `GITHUB_SHA=abc` and
      `GITHUB_EVENT_NAME="push; rm"` give `local`.
    - **`test_status_links_the_feed_by_its_bytes`** (NM-T04): `published` with the
      `first_run()` feed's bytes → `serving_feed_sha256` is their SHA-256 and the other three
      are the feed's; `validation_failed` with v1's feed
      (`tests/fixtures/feed/2026-10-16-ff30417.json`) → its digest, `serving_generated_at`
      `"2026-10-16T00:02:31Z"` and null `serving_published_at` and `serving_content_id`; with
      `serving=None` → four nulls; `b"not json"` → its digest and three nulls; every result
      passes `validate_status`.
    - **`test_status_lists_reasons_and_sources`:** the `first_run()` status lists only error and
      warning reasons, nine `sources` entries in `SOURCE_ORDER` with `served_fetched_at`, and
      run reasons last with `source` null. An IPU result with `http_error` on pages `a` and
      `b`, only `a`'s acknowledged, lists both with their `page` and `acknowledged` true and
      false, and one `acknowledged` entry, with `page` `a`.
  - `tests/feed/test_health_md.py`:
    - **`test_health_md_sections`** (R11): the `first_run()` `HEALTH.md` has the headings of the
      table in order; IPU's line `Ignored: appointed_chamber 28, inactive_chamber 10, no_expected_date 5`
      (escaped as `md_text` gives it); EISA's `not_published_yet` reason with nothing after it;
      Wikipedia's `unparsed_relevant` reason ending with
      `acknowledge each unit by its full text (unit_text in attention_full.json)`;
      `feed_size=600_000, budget=524_288` adds `, over budget`.
    - **`test_health_md_escapes_hostile_text`** (S4-T19; Review Focus 3): a unit text and a reason
      detail of `"# H1\n<script>x</script> [a](javascript:alert(1)) ![i](https://e.test/i.png) `c` a|b \x07"`
      plus 10,000 × `"y"`. In `HEALTH.md`: no line starts with `#` except the headings of the
      table; neither `<script`, `](`, `![`, an unescaped backtick nor `\x07` appears; every row
      of the attention table has the same number of unescaped `|`.
    - **`test_md_text`:** `md_text("a*b_[c]")` is `"a\*b\_\[c\]"`; `md_text("x\n\ty")` is `"x y"`;
      `md_text("\x1b[31m")` is `"\[31m"`; `md_text(None)` is `"None"`.
    - **`test_diagnostics_are_capped_and_redacted`** (P96, S4-T19; Plan 2a "Caps"): an OSCE page
      whose `FetchResult` has the `final_url` and `error` of Task 1's
      `test_page_download_redacts_and_cuts` and outcome `http_error`, through `build_snapshot`,
      `decide`, `source_health_entry`, `build_feed`, `feed_bytes` and `health_md`: none of `XYZ`,
      `abc`, `s3cret` appears in the feed bytes or `HEALTH.md`; `download.final_url` and
      `download.error` are at most 300 characters; every reason `text` at most 300; every sample
      at most 200; every item `text` at most 300.
  - `tests/feed/test_validate.py`:
    - **`test_feed_schema`** (S4-T06): the `first_run()` feed is valid; a fallback run (every
      source served from a baseline, claims stamped `fallback`) is valid and its entries say
      `using_fallback` true; `run.parser_version` is `PARSER_VERSION` and each source's
      `parse.parser_version` its candidate's; each schema enum equals its Literal's `get_args`;
      an extra key on a child source, a missing `round` on a child, and `status: "Ongoing"` on a
      card are each a `schema:` problem.
    - **`test_validate`** (§11.3): one row per check of the table (a card `date` of
      `"2026-10"`, `source_names` out of step with `sources`, a repeated `child_id`, a dangling
      possible match, an umbrella child of another card, a child with two selected sources, a
      card in the wrong month, 2,000,001 bytes, a `published_at` 11 minutes ahead, a
      `served_snapshot_id` that is not the `ServedCheck`'s, a `ServedCheck` with
      `ledger_ok=False`) gives a problem with that prefix; the unchanged feed gives `()`, and so
      does a feed with one `unavailable` source (`served_snapshot_id` null,
      `ServedCheck(source, None, True, True)`). A feed
      with `attention_truncated` 3 and 500 items is valid.
    - **`test_timestamps_ahead_of_the_clock_fail`** (Review Focus 5): `generated_at` 10 minutes
      ahead of `wall_clock` is valid, 10 minutes and 1 second is not; a `+02:00` timestamp is a
      schema problem.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/feed -q`. Expected: FAIL.
- [ ] **Step 3: Implement** the status document, `md_text`, `health_md`, both schemas,
  `validate.py` and the mypy override.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(validate): status.json, HEALTH.md, the feed and status schemas, and the checks of §11.3`.

  Mutations, one each:
  - `md_text` escapes only `*` and `_`;
  - `md_text` keeps control characters;
  - `health_md` writes a sample without `md_text`;
  - the over-budget suffix is never written;
  - status reasons leave out `page`;
  - `status_doc` hashes the new feed on `validation_failed`;
  - `attempt_of` accepts any `GITHUB_SHA`;
  - one schema enum drops a value;
  - `additionalProperties` is left out of the child source;
  - the legacy check skips `source_names`;
  - the invariant check allows two selected sources;
  - `FEED_MAX_BYTES` is compared with `<`;
  - `MAX_AHEAD` is compared with `<=` on the wrong side (10 minutes fails);
  - the served check ignores `ledger_ok`.

---

### Task 8: The run and the CLI (`pipeline.py`, `__main__.py`, `runner.load_adapter`; P98, P99; R18; C1; F-10; S4-T05, S4-T07, S4-T10)

**Files:**
- Modify: `elections_calendar/runner.py` (`_load` becomes the public `load_adapter`; its three
  callers and `tests/unit/test_runner.py` follow), `importlinter.ini` (`(__main__)` and
  `(pipeline)` lose their parentheses)
- Create: `elections_calendar/pipeline.py`, `elections_calendar/__main__.py`,
  `tests/pipeline/__init__.py`, `tests/pipeline/test_offline.py`, `tests/pipeline/test_run.py`,
  `tests/pipeline/test_cli.py`, `tests/support/repo.py`

**Interfaces:**
- Consumes: everything above. From the runner: `AdapterSpec`, `DEFAULT_ADAPTERS`,
  `SOURCE_DEADLINE_S`, `SourceRun`, `ScrapeRun`, `run_sources`; from fetch: `Deadline`,
  `FetchResult`, `TrustBundleError`; `merge.merge`; `PlaceRegistry`; `Registries`;
  `ledger.check`.
- Produces in **`runner.py`:** `def load_adapter(spec: AdapterSpec) -> Adapter` (the body of
  `_load`, unchanged).
- Produces in **`pipeline.py`:**

```python
class UsageError(Exception): ...          # __main__ turns it into exit status 2

class OfflinePage:
    url: str
    file: Path            # resolved against the pages.json directory
    fetched_at: datetime
    content_type: str
    status: int | None
    outcome: FetchOutcome = "ok"

class OfflineGetter:      # a fetch.Getter over pages.json
    def __init__(self, pages: Sequence[OfflinePage]) -> None: ...
    def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult: ...
    def fetched_at(self, url: str) -> datetime | None: ...

def load_offline(directory: Path) -> OfflineGetter      # UsageError("pages.json: <problem>")

class RunConfig:
    out: Path
    repo: Path
    now: datetime
    wall_clock: datetime
    environ: Mapping[str, str]
    offline: Path | None = None                  # None = live
    specs: tuple[AdapterSpec, ...] = DEFAULT_ADAPTERS
    timer: Callable[[], float] = time.perf_counter

class RunResult:
    outcome: AttemptOutcome
    verdict: Verdict
    feed_bytes: int | None

def run(config: RunConfig) -> RunResult
```

**`pages.json`** (offline input): `{"pages": [{"url", "file", "fetched_at", "content_type", "status", "outcome"?}]}`.
`load_offline` raises `UsageError` for: a missing `pages.json` (`"pages.json: not found"`),
not JSON or not this shape (`"pages.json: shape"`), a `file` that does not exist
(`"pages.json: no file <file>"`), a `fetched_at` without a time zone
(`"pages.json: <url>: fetched_at needs a time zone"`), or a repeated `url`. The getter serves a
known URL as `FetchResult(url, url, outcome, "done", status, content_type, body, 0, 1)` and any
other URL as `outcome="http_error"`, `http_status=404`, an empty body.

**`run`, in order** (no step reads the clock; `now` and `wall_clock` come in):
1. **Usage:** `now` and `wall_clock` aware (else `UsageError("--now needs a time zone")`); `out`
   absent or an empty directory (else `UsageError("--out must be empty")`); `offline` holds
   `pages.json`. Then `window = window_for(now)`, `Registries.load()`, `registry_version()`,
   `load_known_issues(repo / "known_issues.yml", now=now)`.
2. **Fetch.**
   - **Offline:** per spec, `load_adapter(spec).fetch(window, getter, Deadline.after(SOURCE_DEADLINE_S))`,
     each `RawPage` re-stamped with `getter.fetched_at(url)` (or `now` for an unknown URL);
     `SourceRun(source, RawPages(source, pages, ()), "complete", 0)`. An exception becomes a
     `worker_failed` run with detail `f"fetch: {type(exc).__name__}"` and no pages.
     `trust_sources` is `()`.
   - **Live:** `run_sources(specs, window, workdir=Path(tempfile.mkdtemp(prefix="elections-")), environ=environ)`;
     the directory is removed in a `finally` (F-10). A `TrustBundleError` propagates.
3. **Per source,** in spec order:
   - parse with `timer()` before and after (`parse_ms` = the difference × 1000, rounded). An
     exception gives a `ParseResult` with no units, claims or notes and one `PageCoverage` per
     page and unfinished request, outcome `layout_not_recognised`, detail `"the parser failed"`;
     the run becomes `worker_failed` with detail `f"parse: {type(exc).__name__}"`; the ledger
     report is None.
   - `ledger.check`; `build_snapshot`; `load_baseline` (a `RecordError` gives
     `baseline_problem = str(error)`); `load_health_state`.
4. **Decide:** `drop_acceptances(issues, states, now)`, then `decide` and `unit_items` per source.
5. **Merge** every decision's `claims` at `now`. A `ValueError` gives the run reason
   `Reason("merge_failed", str(error)[:MAX_DETAIL])`, keeps the full text for
   `rejected/merge_error.txt`, and continues with an empty `MergeResult` (so `HEALTH.md` still
   shows every source; nothing of it is published).
6. **Health per source:** `match_diagnostic` (fresh = the `promoted` sources),
   `source_reasons`, `acknowledge`, `severity` → `SourceResult`.
7. **Feed:** `build_feed` with the run reasons so far (`issues.problems`, then `merge_failed`);
   `RunInfo(attempt.code_sha, trust_sources)`. Unless the merge failed, `feed_bytes(doc,
   published_at=now)` and `validate_feed(…, served=…, wall_clock=wall_clock)`, where each
   `ServedCheck` is the served snapshot's id with the baseline's two checks (a promoted
   candidate's are both true; an `unavailable` source's is `ServedCheck(source, None, True, True)`). Any problem adds `Reason("validation_failed", problems[0][:MAX_DETAIL])`.
   The outcome is `validation_failed` after a merge failure or a validation problem, else
   `published`. From here on, **the run reasons** are `parts.run_reasons` plus each
   `validation_failed` (here or in step 8), and **the run severity** is the worst of `parts.severity` and
   `severity(run reasons)`; `status_doc`, `verdict` and `verdict.json` use both, and `health_md`
   gets the problems.
8. **Status gate** (review P4-06): `validate_status(stored_json(status_doc(…)))` for the outcome
   so far. A problem adds `Reason("validation_failed", ("status: " + problems[0])[:MAX_DETAIL])`
   to the run reasons and makes the outcome `validation_failed`: the failed bytes go to
   `rejected/status.json` and every problem to `rejected/validation.txt`, and `status_doc` is
   built again for `validation_failed`. When that one fails `validate_status` too, `run` raises
   `RuntimeError(f"status.json failed validation: {problems[0]}")` before step 10 writes
   anything.
9. **Verdict:** `verdict(each source's unacknowledged reasons + the run reasons)`.
10. **Write** (`publish.write_atomic` for every file, `stored_json` unless noted), in this order:

| Path in `out/` | When | Content |
|---|---|---|
| `elections.json` | published | the feed bytes |
| `status.json` | always | the `status_doc` that passed step 8; `serving` = the feed bytes, or the repository's `elections.json` bytes on `validation_failed` |
| `HEALTH.md` | always | `health_md` (UTF-8) |
| `data/sources/<source>/baseline.json` | published, when `decision.baseline` is set | `baseline_to_dict` |
| `data/sources/<source>/candidate.json` | published | `snapshot_to_dict(candidate)` |
| `data/sources/<source>/health_state.json` | published | `next_health_state(state, source, issues, present_keys(reasons, items), now)` |
| `verdict.json` | always | `{verdict, outcome, severity, reasons: [{source, code, level, text, acknowledged}], feed_bytes, feed_budget_bytes, trust_sources}`; the error and warning reasons, sources in order then the run's |
| `attention_full.json` | always | `parts.attention_full` |
| `dispositions.json` | always | `parts.dispositions` |
| `rejected/elections.json` | validation problems | the feed bytes that failed |
| `rejected/status.json` | a status problem | the status bytes that failed step 8 |
| `rejected/validation.txt` | validation problems | every problem (feed and status), one per line |
| `rejected/merge_error.txt` | merge failure | the full error text |
| `manifest.json` | always, last | `write_manifest(out)` |

- Produces in **`__main__.py`:** `def main(argv: Sequence[str] | None = None) -> int` and
  `sys.exit(main())` under `if __name__ == "__main__":`.
  - Arguments (P98): `--live` or `--offline DIR` (one is required; `argparse` exits 2);
    `--now ISO` (default: the machine clock); `--out DIR` (required); `--repo DIR` (default `.`).
  - `wall_clock = datetime.now(UTC)`; `now` = `datetime.fromisoformat(--now)`.
  - Exit 0 after `run` returns, whatever the verdict; prints one line:
    `f"{outcome}, verdict {verdict}, {feed_bytes} feed bytes"`.
  - `UsageError`: prints its message to stderr, exit 2.
  - `TrustBundleError`: prints `str(error)` to stderr, writes `out/rejected/trust_error.json` =
    `{"variable": error.variable}` (the message holds the bundle's path, so it is never written),
    exit 1.
  - Any other exception propagates (Python exits 1); `manifest.json` is then never written.

**`tests/support/repo.py`:** `commit(out, repo)` copies the repository files of `out`
(`elections.json`, `status.json`, `HEALTH.md`, `data/sources/**`) into `repo`, as Plan 5's
publish job will; `offline_dir(tmp_path, pages)` writes a `pages.json` for a list of
`(url, fixture path, fetched_at, outcome)`.

- [ ] **Step 1: Write the failing tests.** Most tests run one source (`OSCE = AdapterSpec("osce", …)`)
  with the OSCE fixture at `2026-10-18T11:18:37Z`, `now = wall_clock = 2026-10-19T12:00:00Z`,
  and an empty `repo`.
  - `tests/pipeline/test_offline.py`:
    - **`test_offline_getter`:** a known URL gives its bytes, outcome, status and content type;
      an unknown URL gives `http_error` 404 with an empty body; `fetched_at` of an unknown URL is
      None.
    - **`test_bad_pages_json`** (parametrized): each `UsageError` of the list, with its message.
  - `tests/pipeline/test_run.py`:
    - **`test_a_first_run_writes_a_complete_artifact`:** exit 0, `published`; `out` holds exactly
      the "published" rows of the table (OSCE's three snapshot files) plus `verdict.json`,
      `attention_full.json`, `dispositions.json` and `manifest.json`; the manifest lists every
      other file with its SHA-256; `elections.json` passes `validate_feed` and `status.json`
      `validate_status`; `status.serving_feed_sha256` is the digest of `elections.json`.
    - **`test_the_same_input_gives_the_same_files`:** two runs into two `out` directories with
      the same environment and a fixed `timer` give byte-identical files; with
      `GITHUB_RUN_ID=7`, only `status.json` and `manifest.json` differ (the manifest holds
      `status.json`'s digest).
    - **`test_an_interrupted_write_leaves_no_manifest`** (S4-T07; Review Focus 4): with
      `write_atomic` patched to raise `OSError` on its fourth call, `run` raises; `out` has no
      `manifest.json` and no `*.tmp` file.
    - **`test_merge_error_blocks_publishing`** (R18, S3-T16): `merge` patched to raise
      `ValueError("x" * 1000)` → `validation_failed`; run reason `merge_failed` with a 300-character
      detail; `rejected/merge_error.txt` holds all 1000; no `elections.json` and no
      `data/sources/`; `HEALTH.md` has the OSCE section; `status.json` describes the repository's
      `elections.json` (none here: four nulls).
    - **`test_validation_failure_writes_no_feed`** (S4-T05): `validate_feed` patched to return
      `("size: 1 bytes is over 2000000",)`, with a repository holding v1's feed → exit 0,
      `validation_failed`, verdict red; `status.json`'s `serving_feed_sha256` is the digest of the
      repository's file; `rejected/elections.json` and `rejected/validation.txt` exist; no
      `elections.json` and no `data/sources/`.
    - **`test_an_invalid_status_blocks_publishing`** (review P4-06): `status_doc` (as `pipeline`
      calls it) patched to add the key `"x": 1` when the outcome is `published` → exit 0,
      `validation_failed`, verdict red, a run reason `validation_failed` whose detail starts
      with `"status: "`; `rejected/status.json` holds the document with `"x"`; `status.json`
      passes `validate_status`; no `elections.json` and no `data/sources/`; `manifest.json`
      lists every other file.
    - **`test_an_invalid_failure_status_writes_nothing`:** `status_doc` patched to add `"x": 1`
      for every outcome → `run` raises `RuntimeError`, and there is no file under `out`.
    - **`test_a_corrupt_health_state_needs_a_new_acknowledgement`** (review P4-05; Review Focus
      2): the OSCE URL gives `http_error`; `known_issues.yml` acknowledges OSCE's `http_error`
      (scope `{stage: fetch, year: null, page: elections}`) from `now - 1 day` for 7 days; the
      repository's `data/sources/osce/health_state.json` is `b"{"`. Run 1 → `ack_invalid`,
      and the `http_error` reason in `verdict.json` has `acknowledged` false; `commit`. Run 2 a
      day later → no `ack_invalid`, `acknowledged` still false, and `health_state.json`'s
      `reset_at` is run 1's `now`. Run 3, with a second entry acknowledged after run 1's `now`
      → `acknowledged` true.
    - **`test_a_registry_change_never_serves_the_old_baseline`** (P93; the user's decision): the
      repository holds OSCE's `baseline.json` from a first run, with its `registry_version`
      changed to `"0" * 64` (written with `stored_json`). Run 1 with the OSCE URL giving
      `http_error` → `published`, and `elections.json` passes `validate_feed`; OSCE's acceptance
      is `unavailable` with `served_snapshot_id` null, no child source in the feed is OSCE's, its
      reasons hold `count_change` "baseline.json is from another registry version; it is never
      served" and `unavailable` "baseline.json is from another registry version", the verdict
      is red, and `data/sources/osce/baseline.json` is byte-identical to the repository's.
      `commit`, then run 2 with the OSCE fixture → `promoted`; the new `baseline.json` has
      `registry_version()`; no `unavailable` reason.
    - **`test_a_ten_day_outage_ages_honestly`** (Review Focus 1): day 0 at
      `T = 2026-10-18T11:18:37Z` is a good run; days 1–10 run at `T + k days` with the OSCE URL
      giving `timeout`, and `commit(out, repo)` after every run. Every day:
      - acceptance `fallback`, `served_fetched_at` `T`, every OSCE child source `fetched_at` `T`
        and `fallback` true, `data_as_of` `T`;
      - `data/sources/osce/baseline.json` byte-identical to day 0's.

      Days 1–7 have no `fallback_stale`; days 8–10 have it ("serving data fetched
      2026-10-18T11:18:37Z") and their children are `unverified`. Day 0's verdict is green and
      days 1–10 are red.
    - **`test_a_deadline_is_a_reason`** (S4-T10, deadline part): live, with `run_sources`
      patched to return OSCE `deadline` with its page unfinished → download outcome `deadline`,
      reason `deadline`, acceptance `unavailable`, verdict red, exit 0.
    - **`test_parse_time_is_recorded`** (Plan 2a "Parsing bound"): a `timer` giving 10.0 then
      10.25 → `parse.parse_ms` 250; a parser that raises `ValueError` gives `worker_failed`
      "parse: ValueError", page outcome `layout_not_recognised` "the parser failed", and no
      ledger counts.
    - **`test_live_records_trust_sources`:** `run_sources` patched to return a `ScrapeRun` with
      `trust_sources=("certifi", "REQUESTS_CA_BUNDLE")` → `verdict.json` and `run.trust_sources`
      list both; the work directory is gone afterwards (F-10).
  - `tests/pipeline/test_cli.py`:
    - **`test_now_needs_a_time_zone`** (Review Focus 5): `--now 2026-10-19T12:00:00` and
      `--now 2026-10-19` exit 2 with `--now needs a time zone`; nothing is written.
    - **`test_out_must_be_empty`** (Review Focus 4): an `out` holding `old.txt` exits 2 and
      `old.txt` is unchanged; `--live --offline DIR` and neither both exit 2.
    - **`test_trust_error_is_reported_without_its_message`** (C1): `run_sources` patched to raise
      `TrustBundleError("REQUESTS_CA_BUNDLE=C:/secret/ca.pem is not a usable CA bundle: x", "REQUESTS_CA_BUNDLE")`
      → exit 1; stderr holds the message; `out/rejected/trust_error.json` is
      `{"variable": "REQUESTS_CA_BUNDLE"}`; no file under `out` contains `secret`; no
      `manifest.json`.
    - **`test_main_prints_one_line`:** an offline OSCE run prints
      `published, verdict green, <n> feed bytes` (OSCE alone has no warning) and exits 0.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/pipeline -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `load_adapter`, `pipeline.py`, `__main__.py`, the test support and
  the import-linter change.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(pipeline): the offline and live run, the out/ artifact and the CLI`.

  Mutations, one each:
  - the offline getter serves unknown URLs as `ok`;
  - pages are not re-stamped;
  - a naive `--now` is accepted;
  - a non-empty `out` is accepted;
  - the work directory is kept;
  - a parse exception propagates;
  - `parse_ms` is in seconds;
  - a merge `ValueError` propagates;
  - `elections.json` is written on `validation_failed`;
  - `data/sources/` is written on `validation_failed`;
  - `manifest.json` is written first;
  - `status.json` describes the rejected feed;
  - the status gate is skipped;
  - `data/sources/` is written when only the status failed;
  - a second failing status is written;
  - the trust error's message goes into `trust_error.json`;
  - `baseline.json` is rewritten from the candidate on fallback;
  - an `unavailable` source's `ServedCheck` carries the baseline's snapshot id.

---

### Task 9: End to end on the fixtures, SC1, SC2 and the README (§13.2, §13.4; P100, P101; R23, R24, R26)

**Files:**
- Create: `tests/fixtures/pages.json`, `tests/expected/2026-10-16.yaml`,
  `tests/expected/legacy-mapping-exceptions.yaml`, `tests/support/appendix_b.py`,
  `tests/pipeline/test_end_to_end.py`
- Modify: `tests/merge/test_fixture_merge.py` (its Appendix B rows move to
  `tests/support/appendix_b.py` unchanged), `README.md`

**Interfaces:**
- Consumes: `pipeline.run`, `RunConfig`; `validate_feed`; `FEED_BUDGET_BYTES`; `PlaceRegistry`;
  `text.fold`; `fixture_claim`; Task 7's `tests/fixtures/feed/2026-10-16-ff30417.json`.
- Produces: no code. The end-to-end run is `run(RunConfig(out, repo=<empty>, now=RUN_NOW,
  wall_clock=RUN_NOW, environ={}, offline=Path("tests/fixtures"), timer=<fixed>))` with
  `RUN_NOW = 2026-10-19T12:00:00Z` (P100), run once per module (a module-scoped fixture on
  `tmp_path_factory`).

**`tests/fixtures/pages.json`** lists the 16 pages the adapters ask for at `RUN_NOW`
(measured by `e2e_ct.py`: NDI stops after `p1`, EISA asks for `calendar` and `y2026` only), with
`file` relative to `tests/fixtures/`, `status` 200, and the content type and fetch time of its
`PROVENANCE.md` (`text/html; charset=utf-8` where none was recorded):

| Pages | `file` | `fetched_at` |
|---|---|---|
| ElectionGuide `upcoming`, `past`, `anticipated` | `electionguide/2026-10-16/<key>.html` | `2026-10-16T14:39:00Z` |
| Wikipedia `national-2026`, `national-2027`, `local-2026`, `local-2027` | `wikipedia/2026-10-16/<key>.json` | `2026-10-17T16:13:00Z` |
| OSCE | `osce/2026-10-18/elections.html` | `2026-10-18T11:18:37Z` |
| IPU | `ipu/2026-10-18/elections.html` | `2026-10-18T11:18:37Z` |
| A-WEB | `aweb/2026-10-18/calendar.html` | `2026-10-18T11:18:38Z` |
| Carter | `carter/2026-10-18/observed.html` | `2026-10-18T11:18:40Z` |
| EEAS | `eeas/2026-10-18/missions.html` | `2026-10-18T11:18:40Z` |
| NDI `p0`, `p1` | `ndi/2026-10-19/p0.html`, `p1.html` | `2026-10-19T08:57:34Z`, `2026-10-19T08:57:36Z` |
| EISA calendar, `y2026` | `eisa/2026-10-19/calendar.html`, `y2026.json` | `2026-10-19T08:57:41Z`, `2026-10-19T08:57:53Z` |

Each `url` is the request URL of the adapter at `window_for(RUN_NOW)` (for Wikipedia, the API URL
with `page=`; for EISA's table, `AJAX.format(table_id="38978")`).

**`tests/expected/2026-10-16.yaml` (SC1)** is written by hand from the fixture pages, never from
the program's output. It has one entry per contest a person reading the pages would expect in
the feed: the 83 national and unknown-level children of the feed, and the 39 subnational
children of October 2026 (122 entries; measured by `count1.py`). Each entry:

| Field | Meaning |
|---|---|
| `place` | the `place_id` |
| `office` | a text whose `fold` is contained in the child's folded `office_label` |
| `jurisdiction` | optional; the child's `jurisdiction` |
| `round` | the round or null |
| `date` | `YYYY-MM-DD`, `YYYY-MM` (month precision) or `YYYY-MM-DD to YYYY-MM-DD` (the card's span) |
| `level`, `status` | the card's |
| `source` | one source key that lists the contest |
| `quote` | text from that source's fixture page that shows the contest and its date |

**`tests/expected/legacy-mapping-exceptions.yaml` (SC2, P101):**
- `unmapped`: the five EEAS records dated `2026-10-01` (Colombia, Peru, Bangladesh, Zambia,
  São Tomé e Príncipe), each as `{date, country}`;
- `ambiguous`: the United States record of `2026-11-03` with the cards `54d4c47d9ded` and
  `5a8da530909b`;
- `merged`: `54b356d5b5ea` (Brazil, 4 October: the Chamber of Deputies and Federal Senate
  records) and `4b35f9d2401c` (Brazil, 25 October: the Presidency and A-WEB's second-round
  records), each with its v1 `{date, country, type}` records;
- `unwitnessed`: none (P101: every mapped record's card holds a witness; measured by
  `sc2w4.py`). A record goes here only with a comment that says why its contest is still
  represented.

All measured by `sc2b.py` and `sc2w4.py`.

- [ ] **Step 1: Write the data files and the failing tests** in `tests/pipeline/test_end_to_end.py`.
  - **`test_pages_json_matches_provenance`:** `pages.json` equals the table; every file exists
    and its SHA-256 equals the one in its `PROVENANCE.md` where one is given; every URL the run
    asks for is in `pages.json`, and every entry is asked for.
  - **`test_end_to_end_counts`:**
    - `published`, verdict red, run severity `warning`, `run.reasons == []`;
    - the months `2026-09` … `2027-01` hold 22, 30, 28, 15 and 5 cards (100), with 202
      children;
    - 157 items (126 `in_or_after_window`, 31 `unknown`), `attention_truncated` 0;
    - every source `promoted`, `comparable` false, `using_fallback` false, and
      `served_fetched_at` its earliest page time in `pages.json`; `data_as_of`
      `"2026-10-16T14:39:00Z"`;
    - severities `warning` for Wikipedia, IPU, A-WEB, NDI and EISA, `ok` for the other four;
    - the relevance reasons: Wikipedia `relevant units unparsed: 51` and
      `relevant units partly parsed: 60`; IPU unparsed 4; A-WEB unparsed 1 and partly parsed 2;
      NDI partly parsed 1; EISA unparsed 2, then its `not_published_yet` (info);
    - `validate_feed` of `elections.json` gives `()`; `manifest.json` lists every other file.
  - **`test_appendix_b_in_the_feed`** (R23): for each of the 23 rows of
    `tests/support/appendix_b.py`, the feed card with that `group_id` has the row's place,
    level, dates, precision, meaning, date status, status and type; each child has the row's
    `child_id`, `aggregate` and `date_conflict`, and sources whose `(name, link, rejected_reason)`
    are those of the row's claims (`fixture_claim(merge_id.removeprefix("served/"))`), in order;
    the umbrellas' `(name, link)` are those of the row's umbrella claims.
  - **`test_expected_file`** (SC1): every entry's `quote` is in its page's text (HTML:
    `collapse_ws(BeautifulSoup(body, "lxml").get_text(" "))`; JSON: the same over every string
    value). Every entry matches exactly one feed child (by the table's fields; `source` among the
    child's source names), and every child in scope is matched by exactly one entry. The number
    of subnational children in other months (80) is printed, not checked.
  - **`test_v1_records_map_to_v2_cards`** (SC2, P101): for each of the 50 records of
    `tests/fixtures/feed/2026-10-16-ff30417.json`:
    1. the cards with `place_id == PlaceRegistry.resolve(record.country).place_id` and
       `date <= record.date <= end_date`;
    2. if exactly one of them has a child source whose `link` is in the record's `links`, that
       card;
    3. if still more than one, those with a child whose folded `office_label` contains the
       folded record `type` or is contained in it (unless none does);
    4. **the witness** (P101; review P4-07): the one card left must hold a child or an umbrella
       whose folded `office_label` contains, or is contained in, the folded record `type`; a
       record whose card has none is `unwitnessed`, even when that card was the only candidate;

    then 44 records map to one card, all witnessed (42 by a child, 2 by an umbrella), and the
    unmapped, ambiguous, merged and unwitnessed lists equal the exceptions file exactly. The
    four steps are a helper, `map_v1(v1, feed, places)`, in the test module.
  - **`test_sc2_needs_a_witness`** (P101; review P4-07): on a copy of the feed in which child
    `f90b0d7db440` (Brazil, 25 October, "Brazilian Presidency") becomes `office_class`
    `lower_house` and `office_label` `"Chamber of Deputies"`, and card `4b35f9d2401c` loses its
    umbrellas, `map_v1` lists ElectionGuide's "Brazilian Presidency" record and A-WEB's "2026
    General Elections (2nd round)" record as `unwitnessed`. On the real feed, the two Brazil
    4 October records (Chamber of Deputies, Federal Senate) both map to `54b356d5b5ea`, and no
    child witnesses both.
  - **`test_feed_size_on_the_fixtures`** (R26): `elections.json` is at most `FEED_BUDGET_BYTES`;
    `HEALTH.md` has the line `<n> bytes of a 524288 byte budget` with the file's length (as
    `md_text` gives it); `verdict.json` has `feed_bytes` equal to the file's length and
    `feed_budget_bytes` `FEED_BUDGET_BYTES`. Record in the ledger the file's length, its
    `gzip.compress` length and its headroom under 524,288 bytes, beside the prototype's 393,152.
  - **`test_main_on_the_fixtures`:** `main(["--offline", "tests/fixtures", "--now", "2026-10-19T12:00:00Z", "--out", <tmp>, "--repo", <empty tmp>])`
    exits 0 and prints `published, verdict red, <n> feed bytes`.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/pipeline/test_end_to_end.py -q`.
  Expected: the new tests pass except where a data file is still incomplete. A count that
  differs from this task is a finding: stop and report it with the rule it came from (see
  "Measured values"), never change the expected value.
- [ ] **Step 3: Update `README.md`:**
  - **Running v2 locally:** `python -m elections_calendar --offline tests/fixtures --now 2026-10-19T12:00:00Z --out out`,
    `--live`, `--repo`, the exit codes (0, 1, 2) and the one-line summary.
  - **`out/`:** Task 8's table; which files a publish job would commit (Plan 5).
  - **`known_issues.yml`:** the three entry kinds, the scope of a reason (`HEALTH.md` gives it
    ready to paste), unit acknowledgements by their full text (`unit_text` in
    `attention_full.json`), `accept_drop`'s two minimums (the drop reason gives the candidate's
    counts), the 14-day limit, recurrence, renewing a source's acknowledgements after a corrupt
    `health_state.json`, what can never be acknowledged. A `coverage_gap` stays listed while it
    is acknowledged, and an entry made before a gap began never covers it.
  - **Registry changes (P93):** before committing a change to `places.yaml`,
    `institutions.yaml` or `subdivisions.yaml`, run the offline check; on the next live run
    every source says its baseline is from another registry version, and a source whose fetch
    fails or whose counts drop that day is unavailable. A drop that the change itself caused
    needs an `accept_drop`.
  - **Legacy status (R24):** a cancelled election that another source still lists shows
    `Cancelled` with `status_conflict`; a rescheduled one shows `Upcoming` on its new date with
    `rescheduled_from`.
  - **SC2:** the exceptions file and what each exception means.
- [ ] **Step 4: Run** the full suite. Expected: PASS. Record the suite's runtime in the ledger.
- [ ] **Step 5: Gates, mutation table, commit:**
  `test(pipeline): end to end on the fixtures, the expected file and the v1 mapping`.

  Mutations, one each:
  - `pages.json`'s EG time moves by a minute (`test_pages_json_matches_provenance`);
  - the pipeline stamps `now` instead of the page time (`test_end_to_end_counts`);
  - one Appendix B child's selected source changes (`test_appendix_b_in_the_feed`);
  - one expected entry's date moves by a day (`test_expected_file`);
  - one `unmapped` record is removed from the exceptions file (`test_v1_records_map_to_v2_cards`);
  - the witness step is skipped (`test_sc2_needs_a_witness`);
  - `FEED_BUDGET_BYTES` is 300,000 (`test_feed_size_on_the_fixtures`);
  - `main` prints the severity instead of the verdict (`test_main_on_the_fixtures`).

---

## Requirements for later plans

Plan 5's pre-flight must pull these rows into its own tasks, with the named acceptance test. A
row is closed only when that test is green in Plan 5. R4 (Plan 5 part), R10, R22, R25 and
R26 (popup part) stand as written in Plans 2b and 3.

| ID | Requirement | Owner | Acceptance test (name and result) | Completion stage |
|---|---|---|---|---|
| R27 | The workflow (§11): the `scrape`, `publish` and `verdict` jobs; `PAUSE_PUBLISHING`; `ALERT_TEST`; the push race (`superseded`); `status.json` committed only with a generation (§5.8); the outcome matrix of §11.6 (S4-T08, S4-T09, S4-T10's setup, test and push parts, S4-T11, S4-T12, S4-T18, NM-T05, NM-T08, V2-T07) | Plan 5 | the workflow tests named in §13.3 for those rows | Plan 5's workflow |
| R28 | The publish job refuses an artifact whose `manifest.json` is missing or does not match the files (Task 8 writes it last) | Plan 5 | `test_publish_refuses_an_incomplete_artifact` | Plan 5's workflow |
| R29 | The served check (`served_mismatch`) after the push (NM-T04's served part, NM-T03) | Plan 5 | `test_served_mismatch_is_red` | Plan 5's workflow |
| R30 | `--dry-run` and the bounded live check (§13.5): a stated runtime, a timeout, run in the background, orphaned workers cleaned up | Plan 5 | `test_dry_run_writes_nothing`; the live check's report | Plan 5 |
| R31 | Rollback and republication (§15): `republish.py`, `RELEASES.md`, `published_at` versus `generated_at` (V2-T03, V2-T05) | Plan 5 | V2-T03 and V2-T05 as in §13.3 | Plan 5 |
| R32 | `scraper.py` becomes the thin entry point and v1's scraper retires (§4) | Plan 5 | `test_scraper_entry_point_runs_the_pipeline` | Plan 5 |
| R33 | Worker tracebacks reach the job log (stderr) but never a committed file; the raw bodies of invalid pages are kept in the artifact (`rejected/`) for diagnosis, never committed | Plan 5 | `test_worker_traceback_is_logged_not_committed`; `test_invalid_page_bodies_are_in_the_artifact` | Plan 5's workflow |
| R34 | An over-budget feed (R26) is a line in `HEALTH.md` today. Decide whether it becomes a reason code, once live sizes are known | Plan 5 | the decision in Plan 5's spec corrections | Plan 5 |
| R35 | The extension (§12) reads `schema_version` 2 and `status.json`, links them by `serving_feed_sha256`, renders the text fields as text, and supplies no defaults for the fields Plan 4 always writes (S5, RT) | Plan 5 | §13.3's S5 and RT rows | Plan 5's extension |
| R36 | NDI's card count comes from an independent marker (`.add-to-cal`, Plan 2c), not from the adapter's own wrapper children, so P6 ("an adapter cannot certify itself") holds for NDI. Approved by the user in principle (2026-10-20) on these conditions: the marker is counted over the whole block, never only inside the cards the parser found; the fixtures establish how many markers a real card has before any rule is written; a missing marker and a duplicated marker each give a ledger problem, never a clean ledger; a page whose markers all vanish is never read as a valid empty calendar; the layout, pagination and P65 (`.date-type`) checks stay | Plan 5's pre-flight, or a plan of its own | `test_ndi_marker_count_matches_the_fixture_cards`, `test_ndi_missing_marker_is_a_ledger_problem`, `test_ndi_duplicate_marker_is_a_ledger_problem`, `test_ndi_without_markers_is_not_valid_empty` | the owning plan, after fixture verification |
| R37 | M3 (Plan 3 final review): a previous date without a year ("postponed from 15 November") is read in the new date's year, so the old-date link (P73(a)) is lost when the rescheduling crosses a year. Parked by the user (2026-10-20) as a matching limitation: the old-date contest still shows, unlinked. No year is guessed, and nothing reports it as fixed | a later matching plan | `test_a_year_less_previous_date_across_a_year_keeps_its_link` | open (parked) |

## After Plan 4

- **The branch** has the Plan 4 commits on top of the commit that holds this plan, with all gates
  green. Nothing is pushed or merged.
- **The Review record** shows every Plan 4 row as "verified", with its commit in the SDD ledger.
- **`python -m elections_calendar --offline tests/fixtures --now 2026-10-19T12:00:00Z --out out`**
  writes a complete artifact. v1 keeps running unchanged.
- **Next:** Plan 5 (workflow, extension v2.0.0 and rollout), written against this code.
