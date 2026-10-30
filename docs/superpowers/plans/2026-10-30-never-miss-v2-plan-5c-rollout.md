# Never-miss v2, Plan 5c: Rollout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 3 (2026-10-30), APPROVED by the user on 2026-10-30 ("approved").** Committed plans-only.
Written against `c8e39f4` (Plan 5b-2 complete, code `cee7ca9`:
2939 tests, mypy 183 files on both platforms, ruff clean, `Contracts: 3 kept, 0 broken`).

- **Rev 3** records the user's decisions of 2026-10-30 (`plan-5c-r2-decision-advice-2026-10-30.md`,
  its reply text). It also fixes what checking that text against the code found. Rev 2 is kept
  as `.scratch/plan5c/plan-5c-rev2.md` (SHA-256 `aa2f5372…`). Every change is marked **(rev 3)**:
  - decided: choice 2 (F6's residual risk accepted for this release), choice 3 (P153 as in
    rev 2), choice 7 (open rulings one by one, with an index of the rest), and choice 11 (R63's
    full check before the merge);
  - P149's key drops the page year. For a one-page source it is the single year of all the
    page's claims (`aweb.py`), so one row of another year would make every unit of the page
    new. The per-year pages already carry their year in the scope name;
  - P149 keeps sources apart (row `other_source`);
  - P160 and the new step B3b: R63's full check on B3's reviewed v2 data, through the
    unchanged loader, before the merge. B11 keeps a short check of the final ZIP;
  - P159 gains recovery for a conflicting tag, and the push probe proves the remote moved
    first.
- **Rev 2** answers the red-team review of rev 1 (`plan-5c-red-team-review-2026-10-30.md`; rev 1 is
  55,848 B, SHA-256 `44d07c3f…5345ec`, kept as `.scratch/plan5c/plan-5c-rev1.md`). Every change is
  marked **(rev 2)**. In short:
  - P149 compares unit keys with counts, not texts (PC02);
  - P153 skips only a skipped reply (PC01);
  - P150, P151, P156 and P158 are reworded;
  - P159, the atomic push (PC04), and P160, R63 on v2 data (PC03), are new;
  - the runbook is reordered: the rehearsal comes before the first push, and the drills before
    distribution. Its steps are renumbered B0–B12: rev 1's B7, B8, B9, B10 and B11 are now B9,
    B11, B10, B7 and B12;
  - the concurrency drill reads observed job states (PC05).
- **Inputs:**
  - spec §11, §15, §16 and §17;
  - "Requirements for later plans" of Plan 5a (R41–R46), Plan 5b-1 (R53, R58's 5c half) and Plan
    5b-2 (R62–R67);
  - Plan 5a's final review, F5 (the gates job's 15 min was never argued) and F6 (the publish
    job's checkout keeps its credentials during `pip install`);
  - the 2026-10-24 live check (`.scratch/live/20261024T140811Z/`): two material differences,
    the Somali move and the South Sudan rename (5a ledger, Task 9);
  - (rev 2) the red-team review of rev 1, 2026-10-30: PC01–PC05, P151, six corrections, and
    advice on the ten open choices;
  - two decisions by the user on 2026-10-30, taken while this plan was being written:
    - **"Red only for new units"**: every live run so far is red because of 7 steady warnings
      (122 relevant units unparsed or partly parsed across Wikipedia, NDI, A-WEB, EISA and IPU),
      and each unit can only be acknowledged one entry at a time, for at most 14 days (P149);
    - **"Safe drills live"**: the alert test, the disable/enable drill and the re-run and
      concurrency drills run against the live repository. The rollback is rehearsed on a local
      clone of the real history and never pushed (P156).
- **Measured while writing it:**
  - `gh` is logged in to `github.dowjones.net` only. The user logs in to `github.com` before
    Part B (B1).
  - The main checkout `C:/Users/senescalk/Desktop/elections-calendar` is on `main` at `9ad92a8`,
    an ancestor of `origin/main` (`ff30417` as last fetched). It has three untracked items:
    - `build_elections_pptx.py`;
    - `extension/Global_Elections_Calendar_v1.0.2 .zip` (with a space before `.zip`);
    - `.scratch/`.
    There is no v2 `.venv` there.
  - The branch does not touch `elections.json`, `status.json` or `HEALTH.md`
    (`git diff --stat ff30417 HEAD` on them is empty), so the rebase over v1's daily feed
    commits is conflict-free if those commits touch only `elections.json` (checked again in B5).
  - The full suite takes 1,196 s on this machine (the six chunks at `c8e39f4`). That is longer
    than the gates job's 15 min before installs (F5).
  - (rev 2) **The 2026-10-24 live snapshots hold 122 relevant unparsed or partial units, and no
    two of them share a text,** neither within a scope nor across scopes and years
    (`.scratch/plan5c/pc02_collisions.py`). Wikipedia's scopes are per year (`national-2026`,
    `national-2027`, `local-2026`, `local-2027`). P149's key therefore changes no live outcome
    today.
  - (rev 2) **A plain multi-ref push publishes the tags even when `main` is rejected.** Checked
    on git 2.53 against a local bare repository whose `main` had moved: the push exited 1 and
    created both tags. `git push --atomic` left all three refs unchanged.

## Goal, architecture, stack

**Goal:** Release v2 safely. Close the last code requirements on the branch, then run the spec's
rollout: branch CI, reviewed first baselines, merge, first publication, alert test, extension
release and drills. Every outward step gets the user's go-ahead at the time.

**Architecture:** There are two parts.
- **Part A** has four small code tasks on `feat/never-miss-v2`, each with the Implement-Review
  loop:
  - the workflow's time limit and wheel-only installs;
  - known unit reasons in the verdict;
  - two extension follow-ups;
  - the release tools and the README.
- **Part B** is the rollout runbook, steps B0–B12 (rev 2). The controller runs it with the user,
  without implementer subagents. Each step lists its commands, the go-ahead it needs, what to record in
  the ledger, and when to stop.

**Tech stack:** Python 3.14.1, pytest, pytest-playwright (Chromium 1248), GitHub Actions, the
`gh` CLI, git.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md` (§11, §15, §16, §17), as
corrected by Plans 1–5b-2's P-rows. P122–P124 (Plan 5a) replace §15 step 7.3's range revert with
a tree restore, and add `ci adopt` for §15 step 2.

## Plan series

5c is the last plan. After it, `main` runs v2, v2.0.0 of the extension is released, and the
branch is merged and removed.

## Global Constraints

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Subagents never create worktrees, never switch branches and never commit to `main`.
  - Before every commit, `git rev-parse --abbrev-ref HEAD` must print `feat/never-miss-v2`, except
    for the `main` commits in Part B, which carry the `MERGE_APPROVED` marker.
- **Outward steps (spec §15):** "Every step that writes outside this machine needs the user's
  go-ahead at the time." That covers each push, each dispatch, each re-run, each workflow
  disable or enable, the Web Store upload and the ZIP share. An approval for one step never
  covers the next.
  - (rev 2) **One exception: a restoration is approved with the change it undoes, before that
    change.** That covers B10's enable after its disable, and B9's removal of `ALERT_TEST`. The
    approval covers only that restoration, at the time the step names, even when the drill's
    diagnosis is unfinished. Daily publication is never left disabled while waiting for the
    next conversation.
- (rev 2) **Release tags:** a tag that exists on `origin` is never moved or deleted. A local tag
  is moved only when `git ls-remote origin` shows that tag absent.
- **`main` writes:** "The marker is created for one approved action at a time and deleted
  straight after; it is never left in place."
  - Run them in the main checkout, because the Desktop hook reads the shell's own directory.
  - Then go back to the worktree before any other command.
- **Never** run `ci publish`. Never run `ci adopt` or `scripts.republish` against the worktree.
  There are three exceptions, each named in Part B:
  - B3's one `ci adopt`, with the manifest digest the user approved;
  - `republish --check`, which writes nothing;
  - B7's rehearsal, in a throwaway clone with no remote (rev 2: was B10).
- **Tests and mutations:** run them with `GIT_ALLOW_PROTOCOL=file`, because the worktree's
  `origin` is the live repository. Mutations also need `PYTHONDONTWRITEBYTECODE=1`.
- **Long runs:** run them in the FOREGROUND, in chunks under 600 s; a background run can be
  reaped on this loaded machine.
  - Check free memory before any browser run (`.scratch/plan5b2/topmem.ps1`), and stop under
    2,500 MB.
  - Every `chrome` process belongs to the user.
- **The extension stays light** (feed 524,288 B budget, P114); no new runtime dependency.
- **Files use LF.** JS is plain ES2022 modules, as in Plan 5b-2.
- **Copy:** the strings this plan quotes are exact; never change an expected value to match the
  output.
- **Times:** never push `main` or dispatch between 23:00 and 01:00 UTC. v1's daily run (until
  B8; rev 2: was B6) and v2's schedule both start at 00:00 UTC.

## Review Focus

These are the five inputs most likely to bite a person using this software that no test covered
until now. Each one now has a test in the task that owns the code:

1. **A fallback day (P149).** A source's candidate is not promoted, so its unit items come from
   the baseline. Those reasons are "known", and the day stays red for the fallback's own reason
   (Task 2, `test_a_fallback_day_keeps_its_own_reasons_red`).
2. (rev 3) **The same unit text again, but as a second row, on another page scope or from
   another source (P149).** It is a new unit, so the run is red. Rows that only moved, and a
   page whose own year changed, stay known (Task 2, `test_known_unit_reasons`, rows
   `extra_occurrence`, `other_scope`, `other_source`, `reordered` and `page_year_changed`).
3. **The CHECK fails while the options page shows the pins (R64).** The pins stay listed and
   editable, and "no data" is shown after the reply (Task 3,
   `test_a_failed_check_leaves_the_pins_editable`).
4. (rev 2) **A Refresh with the same bytes after a time boundary (P153).** Examples are local
   midnight after a card's last day, or a week since a fallback's fetch. The open popup then
   shows what a fresh popup would show (Task 3, `test_a_same_bytes_refresh_updates_the_time_labels`,
   with P139's expiry test in `test_banner.py` kept as it is).
5. **The R62 rebuild check from a detached HEAD.** It runs on `git checkout v2.0.0`, so a
   release build must work from a detached HEAD at the release commit (Task 4,
   `test_a_release_build_works_from_a_detached_head`).

## Spec corrections

| ID | Spec or earlier plan says | This plan says | Why; cost if wrong; alternative |
|---|---|---|---|
| P149 (semantic; user 2026-10-30; rev 2) | §11.6: "Valid, with an unacknowledged warning or error → red"; §9.6 unit acknowledgements, at most 14 days each | **A unit reason is "known"** when the source's input baseline exists and every unit of the reason is in it. (rev 2) Precisely: take the relevant units of the reason's outcome (`unparsed_relevant` ↔ `unparsed`, `partial_relevant` ↔ `partial`; relevant = not `before_window`, as `unit_items` selects them) in the served snapshot and in the input baseline. Give each one the **unit key** (page scope, outcome, `collapse_ws(text)`), with the page found by `unit_prefix` as `_page_of` does; a unit with no page has scope `None`. (rev 3) The page's own year is not in the key. For a one-page source it is the single year of all the page's claims (`aweb.py`), so it would change for every unit of the page when one row of another year appears. A meaningful year, that of a per-year page, is already in the scope name (`national-2026`, `y2026`). A baseline of another source knows nothing. The reason is known when every key occurs in the baseline **at least as often** as in the served snapshot. The key has no row position, so rows that only moved stay known. A second row with the same text, the same text on another page scope (such as the next year's page), and a unit that was resolved and then returns are all new. **A known reason does not make the verdict red.** It stays as it is in `status.json`, in the feed's `source_health` (still a warning, `acknowledged` false), and in `HEALTH.md`, whose line ends ` — known: all of these units were in the last served data, so the run is not red for it`. `verdict.json` rows gain `"known": true\|false`. No baseline (the first run, or an unreadable baseline) means nothing is known. An acknowledgement still works as before, and its hint wins over "known". **Only the two unit reasons can be known.** A timeout, a validation failure, an unreadable baseline or any other reason is red on every run while it lasts. (rev 2) **The green headline without a publication becomes `not published: no new unacknowledged issues`** (was `not published: healthy`). HEALTH.md's Sources table still shows the counts (`0 (+k known)`) | 122 steady units would make every day red, or need about 120 entries renewed every 14 days. Red for a unit now means "a unit appeared that the last served data did not have". (rev 3) It stays red until the comparison baseline has the unit. That is normally one run, because the next promoted run's baseline has it. A failed promotion, or a missing or unreadable baseline, keeps it red on later runs. A scope with no new problem unit does not go red. (rev 2) Rev 1 compared texts only, so a second row or another year's row with a known text was hidden (red team PC02). The live data has no such pair today (see "Measured"). Cost: a new unit alerts once only; it stays visible in HEALTH.md and in the extension's banner. Unit acknowledgements now change the display (grey instead of amber) more than the verdict. "Healthy" no longer fits a green run that still lists known warnings. Alternatives (not chosen): warnings never red; acknowledge each unit; text-only keys, recorded as the user's accepted limit |
| P150 (semantic; F5; rev 2) | §11.2: `gates` 15 min | **`gates` 30 min**, a hard limit. The workflow test's allowances (setup 300 s + Chromium 180 s + the suite 1,200 s + the checks 120 s = 1,800 s) are (rev 2) **a provisional budget, not proof of the runtime**. B1 measures each step on GitHub (R53). (rev 2) **20 min is a review trigger**: a job over 20 min, or one that leaves less than 5 min of the limit unused, stops for the user's ruling. The 30-min limit is where GitHub ends the job | The suite alone takes 1,196 s here. Cost: a scheduled run waits up to 15 min longer for its scrape. Alternative: split or parallelise the suite (a new dependency, pytest-xdist) |
| P151 (interfaces; F6; rev 2) | §11.2: `pip install --require-hashes`; the publish checkout keeps its credentials | **Every `pip install` in the workflow also gets `--only-binary :all:`**, and scrape's and publish's install scripts are the same string. The publish checkout itself is unchanged. (rev 2) **This mitigates F6; it does not close it.** Wheel-only installs run no source build (no `setup.py`, no build backend) while the token is in `.git/config`. They do not stop package code from running while the token is there. A wheel's `.pth` line runs at the next interpreter start. `ci publish` imports its dependencies (pyyaml, jsonschema, requests and others) in the job that holds the token. **The residual risk is the user's ruling** (open choice 2). (rev 3) **Decided 2026-10-30: "F6: mitigated; residual risk accepted for this release."** The consequence, as accepted: dependency code running with repository write credentials could alter the live election feed, or other repository content those credentials permit. Hashes show that the approved bytes were installed, not that they are benign. Owner: the user. B4 records the reviewed commit and the workflow file's blob SHA, and confirms the facts the acceptance rests on. Checked at `c8e39f4`: top-level `permissions: {}`; gates, scrape and verdict `contents: read`; publish alone `contents: write`; no `secrets.*` in the workflow; publish only on `main`, for the schedule or a dispatch with `publish: true`; no other workflow file. **Reopen** when the credential scope, the trust in the dependencies, the workflow's entry points or the publication design change materially. Changed facts come back as a new decision, never as a silent extension | The publish job runs only on `main`, so a reordered checkout would first run at the first v2 publication. (rev 2) The branch run proves that every pin has a Linux wheel and that the install works on the runner. Publish's privileges and behaviour get their own evidence: B8's first publication and B10's drills. Cost: a future pin without a Linux wheel fails the install (README's Linux wheel check catches it first). Alternatives: a second checkout with `clean: false`, unproven before production; or (rev 3) dependency execution and data preparation separated from a minimal authenticated publication stage. Today the push runs inside `ci publish`, so that is a redesign: a valid later improvement, not a release blocker |
| P152 (semantic; R64) | `options.js` `start()`: with no cached feed, the pins are drawn after the `CHECK` reply | **The pins are drawn and editable before the `CHECK`**, from storage and the place table. Once the reply arrives, the feed's places are added and `#noData` is set | The pins do not depend on the feed, and the check can take up to 25 s per request. Cost: none known |
| P153 (semantic; R67; rev 2) | R67: "the popup skips its second render when the check is skipped or replies `changed: false`" | (rev 2) **Only a skipped reply skips the second render.** `{ok: true, changed: false, skipped: true}` comes only from the opening check when the cache is fresh, with no request made. A forced CHECK is never skipped (`worker.js`). The popup then draws nothing again, and the first render stands. **Every other reply renders in full at one new `now`.** That includes `{ok: true, changed: false}` after a real request, and every Refresh. Each render that draws makes the mark `popup:render` | (rev 2) Rev 1's footer-only redraw for `changed: false` would leave the display stale after a same-bytes Refresh: an expired acknowledgement, a "Past" date label, an "Unverified since" note. It also breaks P139's own test (`test_banner.py`, "An open popup across `until` changes at its next render"; red team PC01). R67's acceptance was "a popup test counting renders for a fresh cache", and this keeps it. P139 already lets an open popup change at its next render, so the milliseconds before a skipped reply fall within it. Cost: an opening check that makes a real request and finds the same bytes still renders twice, at most once per check interval. Alternative (not chosen): compute the next boundary of every time rule. Each new time rule would then have to be added there |
| P154 (interfaces; R65, R62) | R65: the build refuses a dirty tree or a HEAD other than the recorded SHA | **`python -m scripts.build_extension_zip --release-sha HEX [--repo DIR]`** refuses when HEX is not 40 lowercase hex, when `git status --porcelain --untracked-files=all` lists anything, or when `HEAD` is another commit. Only then does it fill the row's code SHA cell. Without `--release-sha` it is a development build, and the row keeps `<code SHA>` | The row's code SHA can only come from a guarded build |
| P155 (interfaces; R43) | §11.5: the `pre-v2` pair "is checked once by re-reading the blob and comparing" | **`python -m scripts.republish --from-commit SHA --check`** runs every check and builds both files, writes nothing, and prints `recovery pair ok: <commit> (<digest>, recorded in <RELEASES.md\|status.json>); its feed can be republished` | It shows the pair is restorable, not only that it matches |
| P156 (semantic; user 2026-10-30; rev 2) | §15 steps 5 and 7; R44, R46: the drills | **Live:** the alert test (B9), the re-run drill (B9, using the `ALERT_TEST` push as the interleaved commit), and the disable/enable and concurrency drills (B10). **The rollback (RT-05)** is rehearsed on a local clone of the real history, with no remote (B7). (rev 2) **Order:** the rehearsal runs before `main` is first pushed, and the drills before the extension is distributed (B11). A drill is accepted, or its limit is ruled on by the user, before B11. **Evidence:** the concurrency drill is judged on observed job states and head SHAs, never on dispatch order. A drill that does not reach its state is *inconclusive*, not failed or passed. Each restoration is bounded (Global Constraints) | No drill rolls production back. Each live drill publishes at most one normal v2 feed. (rev 2) Every publish job must pass gates (about 20 min) and scrape first, so dispatch order does not set publish-queue order (red team PC05) |
| P157 (semantic; open choice) | §15 step 4: "The next scheduled run publishes the v2 feed" | **The first v2 publication is a dispatch on `main` with `publish: true`**, started with the user's go-ahead while both of us are watching. The schedule's own email path is proven in B9 | Midnight UTC is a bad time to watch a first publication. Alternative: wait for 00:00 UTC |
| P158 (semantic; open choice; rev 2) | §13.5: "any unexplained material difference pauses the release until the user accepts it on record" | **The two known differences may be accepted on record in B3**, with no expected-file change. (rev 2) Each needs its B3 evidence first: the exact source, event and artifact line; the captured page; and the user's acceptance in the ledger. 1. **Somalia:** IPU's *expected renewal* date for the Somali chambers moved to 15 Apr 2027, outside the window. This is expected-renewal evidence, not a confirmed polling date. 2. **South Sudan:** ElectionGuide renamed 5108. B3 checks that the rename lost no contest: the event's contests in the CI artifact equal those of the 2026-10-24 live check. Accepting these two does not waive any other change for Somalia or South Sudan. Any other material difference stops B3 | Both are explained source-side changes. Alternative: the South Sudan alias in `data/institutions_manual.yaml` (a registry task; the user said "for later" on 2026-10-24) |
| P159 (operational; new in rev 2) | §15 step 4: push `main` and the tags | **B8 pushes `main` and both tags in one `git push --atomic`.** A server without atomic support makes git refuse the whole push, so it fails closed: stop and ask. **After any failed or unclear push** (an error, a timeout, a lost reply), `git ls-remote origin refs/heads/main refs/tags/pre-v2 refs/tags/v2.0.0` decides the next step: 1. all three unchanged on `origin`: back to B5; local tags may be re-made; 2. all three equal the local values: the push succeeded, so record it and go on; 3. anything else, including a tag on `origin` with another value: stop and ask, and never move that tag. (rev 3) Recovery: a `v2.0.0` on `origin` at another commit stays. The release is re-cut as `v2.0.1` (the manifest version too) by a short fix plan, unless the user rules otherwise. A `pre-v2` on `origin` at another commit also stays. The user rules whether that commit becomes the pair (B6's row and `--check` redone), or a new tag name is used. B8 first runs `.scratch/plan5c/push_probe.sh`. It proves that the remote branch moved (rev 3), that a plain push leaks the tags, and that `--atomic` changes nothing | A plain multi-ref push created both tags while `main` was rejected (red team PC04, reproduced here on git 2.53). A published `v2.0.0` at the wrong commit would then need a new version. Cost: none known |
| P160 (operational; rev 2; rewritten in rev 3) | R63: the manual 200 % zoom check | (rev 3, decided 2026-10-30: before the merge) **R63's full check runs in B3b, before the merge, on B3's reviewed v2 data, through the unchanged loader.** `.scratch/plan5c/r63_session.py` opens Playwright's Chromium, headed, with a fresh profile and the candidate build. That build is a `--release-sha` build of the reviewed branch commit. As the extension tests do, the session routes the real raw URL to the B3 artifact's `elections.json` and `status.json`, and blocks every other host (`--host-resolver-rules=MAP * ~NOTFOUND`). So the worker downloads, validates and caches v2 data by its own code, and no refresh can bring v1 data. Checked: the attention section, a card expanded with many children, the health panel open, the month navigation and both footer lines, with no horizontal overflow and every control reachable. **Evidence:** the candidate ZIP's SHA-256 and code SHA; the served files' SHA-256s and the artifact's manifest SHA-256; the request log; the popup's `document.body.dataset.renderer` (`v2`) and `devicePixelRatio`, with the display's own scale; the user's result. **After the first publication, before distribution (B11):** a short check of the final ZIP on the live feed. If any extension file differs from the candidate's, B3b's whole checklist is repeated on the final ZIP. B0 keeps R66's real Reload on the v1 feed | Rev 1 checked R63 on main's v1 feed, whose legacy renderer hides the attention section (`popup.js`, `hideAttention()`; red team PC03). (rev 3) Before the merge, a layout fix is a branch fix, not a v2.0.1. A routed host is not GitHub's CDN: B8's served check and B11's short check cover the real path. Rev 2's console-seeding alternative is dropped, because it would have skipped the loader. Alternative (not chosen): the full check only after publication, accepting a possible v2.0.1 |

## Requirements traceability

| ID | Where | Acceptance |
|---|---|---|
| F5, R53, R41 (setup) | Task 1; B1, B2 | `test_gates_job_fits_its_timeout`; B1's and B2's step times in the ledger |
| F6 (mitigated; residual risk accepted, rev 3) | Task 1; B2; B4 | `test_installs_are_wheel_only_and_hashed`; B2's scrape install passes on GitHub; B4's record of the acceptance, the workflow SHA and the confirmed permission map |
| (user) red only for new units | Task 2; B3 | Task 2's tests; B3's second branch run is green unless a unit is new |
| R64 | Task 3 | `test_the_pins_are_listed_before_a_slow_check` |
| R67 (rev 2) | Task 3 | `test_a_fresh_cache_does_not_render_again`; `test_a_same_bytes_refresh_updates_the_time_labels`; P139's `test_banner.py` expiry test, unchanged |
| R65, R62 | Task 4; B11 | Task 4's ZIP tests; B11's row and its identical rebuild |
| R43 | Task 4; B6, B7 | `test_republish_check_writes_nothing`; B6's `--check` on the real `pre-v2`; B7's rehearsal |
| §16 README | Task 4 | `test_readme_covers_the_release` |
| R66 | B0 | the user's notes in the ledger |
| R63 (rev 3, P160) | B3b; B11 | B3b: the candidate ZIP's hash and code SHA, the served files' and the manifest's hashes, the request log, the renderer, `devicePixelRatio`, the user's result; B11: the final ZIP's file comparison and its short check |
| R41, O1, O7, R5 | B1, B2 | the run summaries, read by the user; the ledger |
| R42, P124, P158 | B3 | the approved manifest digest; the adopt output; the baselines commit; each accepted difference's evidence |
| §15 step 3 | B4, B5 | the review verdict; the gates on the rebased SHA; `pre-v2` and `v2.0.0` |
| RT-05 (rev 2: before the first push) | B7 | the rehearsal's checks and its time |
| §15 step 4, P157, P159 | B8 | the push rehearsal; the remote refs after the push; the served digest equals `serving_feed_sha256`; v1.0.2 renders the v2 feed |
| RT-07, S4-T13, R46 (re-runs) | B9 | the user confirms the email; the attempts, the artifact each one consumed, and the SHAs in the ledger |
| R44, R46 (concurrency) | B10 | the observed job states and SHAs in the ledger; each drill's verdict: passed, failed or inconclusive |
| §15 step 6, O4 | B11 | the RELEASES.md row; the user's Store note |
| §16, R45 | B12 | the housekeeping commits; the user's answers |

## Open choices for the user (confirm or veto in the review)

(rev 2) The red team's advice is in brackets. (rev 3) Choices 2, 3, 7 and 11 are decided. **The
user's approval of rev 3 (2026-10-30) confirms the rest as written here:** 1, 4 and 6 confirmed;
5 conditional on B3's evidence; 8 keep the remote; 9 leave the pptx untracked; 10 decided after
the rollout, from the exact list.

1. P150: the gates job's limit is 30 min, a provisional budget that B1 measures. [Confirm.]
2. (rev 3) **Decided 2026-10-30:** P151's wheel-only installs, and "F6: mitigated; residual risk
   accepted for this release". P151 holds the wording, the facts it rests on and when it is
   reopened. There is no credential-separation plan for this release.
3. (rev 2) P153: only a skipped reply skips the second render; every Refresh renders in full.
   (rev 3) **Decided 2026-10-30:** accepted, with the counts kept in HEALTH.md.
4. P157: the first publication by a dispatch, not the 00:00 UTC schedule. [Confirm.]
5. (rev 2) P158: Somalia and South Sudan may be accepted on record, each only with its B3
   evidence. [Conditional: the process now, the facts at B3.]
6. **The merge review (B4):**
   - one opus reviewer over Plan 5c's commits in full (Part A, the first baselines, any B fix);
   - plus a release-readiness pass over the seams between plans: the workflow, the `ci`
     modules, publish, the extension's URL, the README and RELEASES.md;
   - (rev 2) and the links between alert verdicts, publisher permissions, recovery, the
     popup's cache and render, release tags and packaging;
   - on the named final SHA, and again on any later material diff;
   - not a fresh review of the whole 166-commit branch.
   Every earlier plan had its own whole-branch review. [Confirm.]
7. (rev 2) **Before the merge (yours, open since Plan 3):** the I2 veto (the strict wrong-merge
   audit), R37 (parked), and the ledgers' open "Ruling:" lines. **B4 presents each one on its
   own,** with its exact current wording and what it changes. There are 179 "Ruling:" lines
   across the nine ledgers; the list is only the ones still open. Nothing is approved as a
   bundle. (rev 3) **Decided 2026-10-30:** as above, with an index of the rest (B4).
8. R45: keep or remove the `dowjones` remote, and whether the release goes to that mirror too.
   (rev 2) Default: keep the remote; the mirror is a separate decision. [Keep the remote.]
9. §16: whether to update and commit `build_elections_pptx.py` (untracked today) or leave it.
   (rev 2) Default: leave it untracked, outside the release. [Defer.]
10. At the end: which parts of the two `.scratch/` folders may be deleted. (rev 2) Only after
    the rollout. You get the exact deletion list; unique captures, mutation tooling and tables,
    and reproducibility records stay unless you name them. [Decide after rollout.]
11. (rev 3) **Decided 2026-10-30: R63's full check before the merge** (B3b), with a short check
    of the final ZIP before distribution (B11). B3b sends the data through the unchanged
    loader, instead of rev 2's console seeding.

## How to execute this plan

- **Part A** works as Plan 5b-2's "How to execute this plan", with these changes:
  - the ledger is `C:/Users/senescalk/Desktop/handovers/elections-v2-plan5c-sdd-ledger.md` (new);
  - the supplements come from `.scratch/supp5c.py`, a copy of `supp5b2.py` pointed at this plan;
  - the mutation tables are `.scratch/mutations/plan5c-task-<N>.json`, checked with `.scratch/plan5b2/mut_unique.py`;
  - after each task, the controller re-runs that task's table and every earlier table whose
    files the task touched, in the foreground (`run_parts.sh` when memory is low);
  - the controller copies each new or changed table to `handovers/elections-v2-tooling/`.
  - **Gates**, each in its own shell call:
    - `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m pytest -q`;
    - `.venv/Scripts/mypy.exe`;
    - `.venv/Scripts/mypy.exe --platform linux`;
    - `.venv/Scripts/ruff.exe check`;
    - `.venv/Scripts/lint-imports.exe --config importlinter.ini`.
    The controller may run the suite in chunks under 600 s. (rev 2) **The chunks must cover
    the collected test ids exactly once,** not only sum to the count:
    - `.scratch/plan5c/chunk_cover.py <chunk>...` runs `pytest --collect-only -q` on the
      whole suite and on each chunk's arguments;
    - it prints `chunks cover the <N> collected tests once`, or exits 1 and names each
      duplicate and each omission;
    - each chunk's run must then report as many passed and skipped as that chunk collected.
    The bounded mutation fixtures and the process-ownership rules from Plan 5b-2 stay.
  - **Bounds:**
    - one task at a time;
    - one fresh reviewer per round, and at most 3 rounds;
    - an AWS, Bedrock or budget error stops at the last green commit;
    - no merge and no push in Part A.
  - **Reviewers check**, besides CLAUDE.md's list:
    - a verdict input outside P149's rule;
    - a `status.json` or feed byte changed by P149;
    - a workflow `run:` with an expression;
    - copy that differs from this plan.
- **Part B:** the controller and the user, in order B0 to B12 (rev 2). Rules:
  - no subagent, except B4's reviewer and any fix it needs;
  - after each step, the ledger records the evidence named there and the RESUME doc records
    the next step;
  - a step whose stop condition fires is not "done", and the next step does not start.
- **Cost (an estimate by analogy, not a measurement):**
  - Part A: four tasks, one implementer and one reviewer each, about three fix rounds in all,
    about 12–15 agent runs, **USD 120–200** (rev 2: Task 2 grew). Task 2 is the largest.
  - B4: one opus review, a possible fix wave and its re-review, **USD 40–80**.
  - The rest of Part B is the controller's own work.
  - **In all, about USD 160–280.** (rev 3) This is an estimate, not approval of unlimited
    retries: the round limits above stand.
- **Calendar:** Part A takes one to two days. Part B takes at least five more (rev 2):
  - B1–B3b need a day (rev 3: B3b adds about an hour);
  - B5–B8 need a day inside 01:00–23:00 UTC;
  - B9 needs two 00:00 UTC runs;
  - B10 needs a day;
  - B11–B12 need a day.

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `.github/workflows/update-elections.yml`, `tests/workflow/test_workflow.py`, `README.md` (CI, Updating dependencies) | gates limit (P150); wheel-only installs (P151) | 1 |
| `elections_calendar/snapshots.py`, `elections_calendar/feed.py`, `elections_calendar/pipeline.py`, `elections_calendar/ci/verdict.py`; `tests/snapshots/test_known_units.py`, `tests/pipeline/test_known_units.py`, `tests/ci/test_verdict.py`; `README.md` (`known_issues.yml`, "CI") | known unit reasons; the green headline (P149, rev 2) | 2 |
| `extension/options.js`, `extension/popup.js`; `tests/extension/test_options.py`, `tests/extension/test_loading.py` | pins before the check (P152); only a skipped reply skips the second render (P153, rev 2) | 3 |
| `scripts/build_extension_zip.py`, `scripts/republish.py`; `tests/scripts/test_build_extension_zip.py`, `tests/ci/test_recovery.py`, `tests/unit/test_readme.py` (new); `README.md` | the release guard (P154); `--check` (P155); README for the release (§16) | 4 |
| `data/sources/**` | the first baselines (B3, the controller) | B3 |
| `RELEASES.md` | the `pre-v2` pair (B6), the v2.0.0 row (B11), the v1.0.2 ZIP (B12) | B6, B11, B12 |

## Part A: tasks

### Task 1: The gates job's time limit and wheel-only installs (F5, F6; P150, P151)

**Files:**
- Modify: `.github/workflows/update-elections.yml` (gates `timeout-minutes`, the three `Install` steps)
- Modify: `tests/workflow/test_workflow.py` (constants near `SETUP_ALLOWANCE_S`; `test_publish_job_fits_its_timeout`; two new tests)
- Modify: `README.md` ("CI": the gates line; "Updating dependencies": CI installs wheels only)

**Interfaces:**
- Consumes: `jobs()`, `steps(job)` and `SETUP_ALLOWANCE_S` in `tests/workflow/test_workflow.py`.
- Produces: none for later tasks. B1 records the measured times against these allowances.

- [ ] **Step 0: Pre-flight: check that every pin has a Linux wheel.** Run README's "Updating
  dependencies" command with this machine's TLS bundle set. (rev 2) It already names the
  target, not this Windows host: `pip download --require-hashes --only-binary=:all:
  --implementation cp --python-version 3.14 --platform manylinux_2_39_x86_64 … --platform any
  -r requirements-dev.txt -d .scratch/linux-wheels`. Run it once for `requirements.txt` too
  (`-d .scratch/linux-wheels-runtime`). Expected: exit 0 both times. If a pin has no wheel,
  stop and report: P151 then falls back to recording F6 as an accepted risk, which is the
  user's call.

- [ ] **Step 1: Write the failing tests** in `tests/workflow/test_workflow.py`:

```python
# A provisional budget (P150), not proof of the runtime: B1 measures each step on GitHub.
CHROMIUM_ALLOWANCE_S = 180  # playwright install --with-deps chromium
SUITE_ALLOWANCE_S = 1200  # the full suite: 1,196 s in six chunks on the dev machine at c8e39f4
CHECKS_ALLOWANCE_S = 120  # mypy, ruff, lint-imports, scripts.prove_gates


def test_gates_job_fits_its_timeout() -> None:
    total = SETUP_ALLOWANCE_S + CHROMIUM_ALLOWANCE_S + SUITE_ALLOWANCE_S + CHECKS_ALLOWANCE_S
    assert total <= 30 * 60
    assert jobs()["gates"]["timeout-minutes"] == 30


def test_installs_are_wheel_only_and_hashed() -> None:
    installs = {
        job: [s["run"] for s in steps(job) if "pip install" in s.get("run", "")]
        for job in ("gates", "scrape", "publish")
    }
    for job, runs in installs.items():
        assert len(runs) == 1, job
        assert "--require-hashes" in runs[0] and "--only-binary :all:" in runs[0], job
    assert installs["scrape"] == installs["publish"]
```

  In `test_publish_job_fits_its_timeout`, delete the line
  `assert jobs()["gates"]["timeout-minutes"] == 15`. The new test owns it.

- [ ] **Step 2: Run them; both must fail** (15 min; no `--only-binary`):
  `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m pytest tests/workflow -q`

- [ ] **Step 3: Edit the workflow.**
  - gates: `timeout-minutes: 30`.
  - gates' install line: `.venv/bin/python -m pip install --require-hashes --only-binary :all: -r requirements-dev.txt`.
  - scrape's and publish's install lines: `.venv/bin/python -m pip install --require-hashes --only-binary :all: -r requirements.txt`.
  - In README "CI": the gates job has a 30-minute limit, budgeted in
    `test_gates_job_fits_its_timeout`; a job over 20 min is a review trigger (P150).
  - (rev 2) In README "CI", F6's state, in one sentence: CI installs wheels only, so no
    source build runs while the publish job holds its token; the publish step's own
    dependency code still runs with it.
  - In README "Updating dependencies": CI installs wheels only, so the Linux wheel check must
    pass before a lock change is pushed.

- [ ] **Step 4: Run `tests/workflow` again (pass), then all five gates.**

- [ ] **Step 5: Mutations** (`plan5c-task-1.json`):
  - `timeout-minutes: 30` → `timeout-minutes: 15` in the gates job (`test_gates_job_fits_its_timeout`);
  - publish's install without ` --only-binary :all:` (`test_installs_are_wheel_only_and_hashed`).

- [ ] **Step 6: Commit** `ci(workflow): gates limit argued at 30 min; wheel-only installs (Plan 5c Task 1)`.

### Task 2: A unit reason the last served data already had does not turn the run red (P149)

(rev 2) Rewritten. The comparison moves to `snapshots.py` and uses unit keys with counts. The
green headline without a publication is renamed. Rev 1's `other_source` row is gone: the
function now takes one source's two snapshots.

**Files:**
- Modify: `elections_calendar/snapshots.py` (new `known_unit_reasons`; one relevance selection shared with `unit_items`)
- Modify: `elections_calendar/feed.py` (`SourceResult.known`; `health_md`'s reason hint and Sources table)
- Modify: `elections_calendar/pipeline.py` (the per-source loop; the verdict; `_verdict_rows`)
- Modify: `elections_calendar/ci/verdict.py` (the green headline without a publication)
- Modify: `tests/ci/test_verdict.py` (its three `not published: healthy` expectations)
- Modify: `README.md` (`known_issues.yml`: one paragraph; "CI": the headline list)
- Create: `tests/snapshots/test_known_units.py`, `tests/pipeline/test_known_units.py`

**Interfaces:**
- Consumes:
  - `UNIT_REASONS` (`health.py`), with the pairs `unparsed_relevant` ↔ `unparsed` and
    `partial_relevant` ↔ `partial`;
  - `_page_of(snapshot, unit_id)` (`snapshots.py`), and `unit_items`' selection: outcome
    `partial` or `unparsed`, relevance not `before_window`;
  - `collapse_ws` (`text.py`);
  - `Decision.served`;
  - the pipeline's per-source record `p.baseline: Baseline | None`, the **input** baseline that
    `decide` receives. `Decision.baseline` is the new one when the candidate is promoted.
- Produces:
  - `known_unit_reasons(reasons: Sequence[Reason], served: Snapshot | None, baseline: Snapshot | None) -> tuple[Reason, ...]`
    in `snapshots.py`: the reasons of `reasons` that P149 calls known, in the given order.
    - It lives in `snapshots.py`, not `health.py`: the unit key needs `_page_of`, and `health`
      and `snapshots` share a layer, so they may not import each other (`importlinter.ini`).
    - Its own map `_UNIT_OUTCOME = {"unparsed_relevant": "unparsed", "partial_relevant": "partial"}`
      stands in for `UNIT_REASONS`; a test keeps the two equal.
  - `SourceResult.known: tuple[Reason, ...] = ()`, the last field, so existing constructors keep
    working.
  - The headline `not published: no new unacknowledged issues`.

- [ ] **Step 1: Write the failing unit test** `tests/snapshots/test_known_units.py`.
  - `test_the_unit_reasons_match_health`: `set(_UNIT_OUTCOME) == set(UNIT_REASONS)`.
  - `test_known_unit_reasons`, parametrised over the rows below. Build both snapshots with
    `tests/support/snapshots.synth` and `SynthPage(..., scope=, year=, extra=(...))`.
  - The pages are `p26` (scope `s`, year 2026), `p27` (scope `s`, year 2027) and `q26` (scope
    `q`, year 2026).
  - U(T, page) is a relevant `unparsed` unit of `aweb` with text T on that page; P(T, page) is
    the same as `partial`. Positions are the order given.

| id | reasons | served units | baseline units | expected |
|---|---|---|---|---|
| `none` | unparsed_relevant | U(T1, p26) | no baseline (`None`) | `()` |
| `all` | unparsed_relevant | U(T1, p26), U(T2, p26) | U(T1, p26), U(T2, p26), a parsed T3 | `(unparsed_relevant,)` |
| `one_new` | unparsed_relevant | U(T1, p26), U(T2, p26) | U(T1, p26) | `()` |
| `outcome` | unparsed_relevant | U(T1, p26) | P(T1, p26) | `()` |
| `spaces` | unparsed_relevant | U("a b", p26) | U("a \n  b", p26) | `(unparsed_relevant,)` |
| `case` | unparsed_relevant | U("A b", p26) | U("a b", p26) | `()` |
| `partial` | partial_relevant | P(T1, p26) | P(T1, p26) | `(partial_relevant,)` |
| `other_reason` | timeout, unparsed_relevant | U(T1, p26) | U(T1, p26) | `(unparsed_relevant,)` |
| `reordered` | unparsed_relevant | U(T2, p26), U(T1, p26) | U(T1, p26), U(T2, p26) | `(unparsed_relevant,)` |
| `extra_occurrence` | unparsed_relevant | U(T1, p26), U(T1, p26) | U(T1, p26) | `()` |
| `other_scope` | unparsed_relevant | U(T1, q26) | U(T1, p26) | `()` |
| `page_year_changed` (rev 3) | unparsed_relevant | U(T1, p27) | U(T1, p26) | `(unparsed_relevant,)` |
| `other_source` (rev 3) | unparsed_relevant | U(T1, p26) | the same U(T1, p26), in an `ndi` snapshot | `()` |
| `baseline_before_window` | unparsed_relevant | U(T1, p26) | U(T1, p26) with relevance `before_window` | `()` |

- [ ] **Step 2: Run it; it must fail** (`known_unit_reasons` does not exist).

- [ ] **Step 3: Implement `known_unit_reasons` in `snapshots.py`.**
  - With `served` or `baseline` None, or (rev 3) with `baseline.source != served.source`, return
    `()`.
  - (rev 3) The unit key is `(page.scope, unit.outcome, collapse_ws(unit.text))`; the page's
    year is not in it (P149). The page is `_page_of(<the unit's own snapshot>, unit.unit_id)`;
    with no page, the scope is `None`. Only a hand-edited `baseline.json` has such a unit;
    `build_snapshot` makes none.
  - Both sides use one selection, shared with `unit_items` so the reason's count and the keyed
    units cannot drift: outcome `partial` or `unparsed`, relevance not `before_window`.
  - For each reason in `_UNIT_OUTCOME`, count the keys of that outcome's selected units with a
    `Counter`, on each side. The reason is known when the served count is not empty and every
    served key's count is at most the baseline's.
  - Any other reason is never known.

- [ ] **Step 4: Write the failing pipeline tests** `tests/pipeline/test_known_units.py`.
  - Use `tests/pipeline/test_recurrence.py`'s `Repo` pattern:
    - `config(..., specs=(<spec>,))`;
    - `offline_dir` for the day's pages;
    - `commit(out, repo)` after each day.
  - Pre-flight: pick the one-source run that has at least one relevant unparsed unit at
    `NOW` on its fixture. A-WEB is the likely one; measure it and record the choice in the
    report.
  - **`test_an_unchanged_unit_reason_does_not_make_the_run_red`:**
    - Day 0 has no baseline: the verdict is red, and the unit reason's `verdict.json` row has
      `"known": false`.
    - Day 1 has the same page:
      - `verdict.json` `verdict == "green"`, and the row has `"known": true` and
        `"acknowledged": false`;
      - `status.json` still lists the reason, with `acknowledged` false;
      - the feed's `source_health` severity for the source is `warning`;
      - the HEALTH.md reason line ends with
        ` — known: all of these units were in the last served data, so the run is not red for it`;
      - the Sources table cell is `0 (+1 known)`, or `(+2 known)` when both unit reasons are
        present; assert the exact cell for the chosen source.
  - **`test_a_new_unit_makes_the_run_red_again`:**
    - Day 1's page is a copy of the fixture with one more relevant unparsed unit, either an
      added row or one unparsed row's text changed.
    - The verdict is red, and the row has `"known": false`.
  - **`test_a_unit_that_returns_is_new`** (rev 2):
    - Day 1 resolves one unparsed unit: its row is edited so it parses, or removed if the
      candidate is still promoted. Assert day 1's acceptance is `promoted`; if neither edit is
      promoted, stop and report.
    - Day 2 serves day 0's page again. The verdict is red, and the row has `"known": false`.
  - **`test_an_unreadable_baseline_knows_nothing`** (rev 2):
    - Day 1 overwrites `data/sources/<source>/baseline.json` with `{`.
    - The verdict is red; every unit reason row has `"known": false`; the baseline problem's
      own `ledger_mismatch` row is present (`decide` adds it from `load_baseline`'s message).
  - **`test_a_fallback_day_keeps_its_own_reasons_red`** (Review Focus 1):
    - Day 1's page times out (`outcome="timeout"`), so the baseline is served.
    - The unit reasons are known.
    - The verdict is red for the timeout's reason, and only that row has `"known": false`
      among the error and warning rows.
  - **Existing tests:** any test that expected red from a unit reason on a day whose units the
    input baseline already had now expects green. List each one in the report with this reason,
    and change no other expectation.
  - **`tests/ci/test_verdict.py`:** its three `not published: healthy` expectations (rows
    `r20-branch-dispatch-healthy`, `r22-main-dispatch-false`, `r24-main-dispatch-yes`) become
    `not published: no new unacknowledged issues`. The row ids stay.

- [ ] **Step 5: Run them; they must fail.**

- [ ] **Step 6: Implement.**
  - `pipeline.py`, in the per-source loop: `known=known_unit_reasons(reasons, decision.served, None if p.baseline is None else p.baseline.snapshot)`.
  - The verdict's `open_reasons` keeps only the unacknowledged reasons that are not in `s.known`.
  - `_verdict_rows` adds `"known": r in s.known` to source rows, and `False` to run rows.
  - `feed.py`:
    - `_reason_hint` returns the known text for an unacknowledged known reason (an
      acknowledgement's hint wins);
    - the Sources table's open count leaves known reasons out and appends ` (+<k> known)` when
      k > 0.
  - `ci/verdict.py`: `_late`'s last line returns `_green("not published: no new unacknowledged issues")`.
  - Nothing else in `status.json` or the feed changes.
  - README:
    - in `known_issues.yml`, add: "A unit reason whose every unit was already in the last
      served data is *known*: it is shown, but it does not make the run red (P149). A unit is
      the same when its page's scope, its outcome and its text match, and a second
      row with the same text is a new unit. A unit acknowledgement then only turns it grey.
      Every other reason is red on each run while it lasts.";
    - in "CI", the headline list says `not published: no new unacknowledged issues`.

- [ ] **Step 7: Run the new tests (pass), then all five gates.**

- [ ] **Step 8: Mutations** (`plan5c-task-2.json`):
  - `u.outcome == outcome` → `True` (`test_known_unit_reasons[outcome]`);
  - `all(` → `any(` (`[one_new]`);
  - the `collapse_ws` call on the baseline side removed (`[spaces]`);
  - (rev 2) the count comparison replaced by membership (`before[k] >= n` → `k in before`)
    (`[extra_occurrence]`);
  - (rev 2) the scope dropped from the key (`[other_scope]`);
  - (rev 3) the page year added to the key (`[page_year_changed]`);
  - (rev 3) the source check removed (`[other_source]`);
  - (rev 2) the unit id added to the key (`[reordered]`);
  - (rev 2) the baseline side selected without the relevance filter (`[baseline_before_window]`);
  - the pipeline's `not in s.known` filter removed (`test_an_unchanged_unit_reason_does_not_make_the_run_red`);
  - the known hint text changed (the same test);
  - `known_unit_reasons` given the decision's baseline instead of the input baseline
    (`test_a_new_unit_makes_the_run_red_again`; when the candidate is promoted, the decision's
    baseline is the new one);
  - `known_unit_reasons` returns every reason once one unit reason is known
    (`test_a_fallback_day_keeps_its_own_reasons_red`);
  - (rev 2) the green headline back to `not published: healthy` (`tests/ci/test_verdict.py`,
    row `r20-branch-dispatch-healthy`).

- [ ] **Step 9: Commit** `feat(health): a unit reason the last served data had is known, not red (Plan 5c Task 2, P149)`.

### Task 3: Options pins before the check, and only a skipped reply skips the second render (R64, R67; P152, P153)

(rev 2) The popup half is rewritten for P153: there is no footer-only draw. The options half is
unchanged.

**Files:**
- Modify: `extension/options.js` (`start()`)
- Modify: `extension/popup.js` (`render()`'s mark; `check()`)
- Modify: `tests/extension/test_options.py`, `tests/extension/test_loading.py`
- Unchanged, and still required to pass: `tests/extension/test_banner.py::test_ended_acknowledgements_in_the_popup`,
  P139's "An open popup across `until` changes at its next render" (a same-bytes Refresh after an
  acknowledgement ends).

**Interfaces:**
- Consumes:
  - `Ext`, `Served` (`"hold"` and `release`) and `ext.open` from `tests/support/extension.py`;
  - `ext.popup(now=...)` and `context.clock.set_fixed_time(...)`, as `test_ended_acknowledgements_in_the_popup`
    uses them;
  - the worker's CHECK replies `{ok: true, changed}`, `{ok: true, changed: false, skipped: true}`
    (only for an unforced check that is not due) and `{ok: false, error}`.
- Produces: the mark `popup:render`, made once by every render that draws (P153).

- [ ] **Step 1: Write the failing options tests** in `test_options.py`.
  - **`test_the_pins_are_listed_before_a_slow_check`:**
    - Seed migrated v2 pins for two places and no feed, and set
      `ext.served.set("elections.json", "hold")`.
    - Open `options.html` without waiting for the page to be idle.
    - Within 3 s, both pinned rows are listed with enabled buttons, while `elections.json` is
      held (`"elections.json" in ext.served.log`).
    - Unpin one; storage changes while the request is still held.
    - Release the feed: the feed's places are listed, and `#noData` is hidden.
  - **`test_a_failed_check_leaves_the_pins_editable`** (Review Focus 3):
    - The same seeding, and `elections.json` answers 500.
    - The pinned rows are listed and editable, `#noData` is shown once the page is idle, and no
      page error is recorded.
- [ ] **Step 2: Write the popup tests** in `test_loading.py` (rev 2).
  - **`test_a_fresh_cache_does_not_render_again`** (R67's acceptance):
    - Seed the fixture pair with a recent `check_state_v2.ok_at`, so the opening check is
      skipped.
    - After the popup settles, `performance.getEntriesByName("popup:render").length == 1`, and
      no `elections.json` request was added to `ext.served.log` after the popup opened. The
      worker may have fetched at start-up, so compare the log before and after.
    - (rev 3) A skipped check claims no new download: `#footerChecked` keeps its text, and
      `check_state_v2.ok_at` in storage is unchanged.
  - **`test_a_same_bytes_refresh_renders_again`:**
    - The same seeding, with `ok_at` old enough that a new check shows a different "Checked"
      text; measure it.
    - Click Refresh with the same bytes served: the count is 2, and `#footerChecked` shows the
      new check's time.
    - Serve a newer feed and click Refresh: the count is 3.
  - **`test_a_same_bytes_refresh_updates_the_time_labels`**, parametrised (Review Focus 4):
    - `midnight`: a card whose child has `day` precision and ends on day D. Open the popup at
      23:58 local time on D: the child's label is not `Past`. Set the clock to 00:02 local
      time on D + 1, and click Refresh with the same bytes: the label is `Past`.
    - `week`: a child held only by a fallback source fetched at F. Open at F + 7 d − 2 min: its
      note is `Using source data from <F's date>`. Set the clock to F + 7 d + 2 min, and click
      Refresh with the same bytes: the note is `Unverified since <F's date>`.
    - Both rows: after the Refresh, these equal what a second popup opened fresh at the same
      clock shows: the banner's `data-level` and text, the health panel's lines, and the card's
      label and notes.
    - Pre-flight: pick the fixture cards and record them. If the fixture feed has no
      fallback-only child, derive one from it as `tests/extension/test_labels.py` builds its
      fallback cases.
  - **`test_a_failed_refresh_renders_again`:**
    - After a good first render, Refresh with both files answering 500.
    - The count is 2, and `#footerChecked` contains "couldn't check".
- [ ] **Step 3: Run them.** The two options tests and every test that counts `popup:render`
  must fail (the mark does not exist yet).
  - `test_a_same_bytes_refresh_updates_the_time_labels` may already pass: today's popup renders
    after every reply.
  - It guards P153's skip, and Step 6's mutation proves that.
- [ ] **Step 4: Implement.**
  - **`options.js` `start()`**, after the migration check:
    - read the stored feed;
    - set `feedPlaces = optionPlaces(record, table)`;
    - add the search and storage listeners;
    - `await reconcile()`.
    Then, only when `record === null`:
    - send `CHECK`;
    - re-read the feed;
    - set `feedPlaces` and `noDataEl.hidden = record !== null`;
    - `await reconcile()` again.
    The top comment's "pins are drawn one way only" stays true.
  - **`popup.js`:**
    - `render()` makes the mark `popup:render` when it draws;
    - in `check()`, when the popup has drawn and the reply is `{ok: true, changed: false, skipped: true}`,
      return without `render()`;
    - every other reply goes through `render()` as today, with one `now` read inside it (P139).
- [ ] **Step 5: Run `tests/extension/test_options.py tests/extension/test_loading.py
  tests/extension/test_banner.py` (pass), then all five gates.** Check memory first.
- [ ] **Step 6: Mutations** (`plan5c-task-3.json`):
  - the first `await reconcile()` moved after the `CHECK` block (`test_the_pins_are_listed_before_a_slow_check`);
  - `noDataEl.hidden = record !== null` → `= true` (`test_a_failed_check_leaves_the_pins_editable`);
  - the early return removed (`test_a_fresh_cache_does_not_render_again`);
  - (rev 2) the early return taken for every `changed: false` reply, `skipped` ignored, which
    is rev 1's rule. Its row names `test_a_same_bytes_refresh_updates_the_time_labels`. The
    controller also confirms by hand that `test_a_same_bytes_refresh_renders_again` and
    `test_ended_acknowledgements_in_the_popup` fail on it, and records that;
  - the early return taken for any `ok: true` reply (`test_a_same_bytes_refresh_renders_again`,
    its newer-feed part);
  - the early return taken for `ok: false` too (`test_a_failed_refresh_renders_again`).
- [ ] **Step 7: Commit** `fix(extension): pins before the check; only a skipped check skips the second render (Plan 5c Task 3, R64, R67)`.

### Task 4: Release tools and the README for the release (R65, R62, R43, §16; P154, P155)

**Files:**
- Modify: `scripts/build_extension_zip.py` (`release_problems`, `release_row`, `main`)
- Modify: `scripts/republish.py` (`--check`)
- Modify: `tests/scripts/test_build_extension_zip.py`, `tests/ci/test_recovery.py`
- Create: `tests/unit/test_readme.py`
- Modify: `README.md`

**Interfaces:**
- Consumes:
  - `elections_calendar.ci.git.Git(repo)`: `.run(*args) -> str`;
  - `recorded_pair(git, commit, releases_text) -> RecoveryPair`;
  - `republish(...)`;
  - `tests/support/git_repos.git(path, *args)`;
  - `SOURCE_ORDER` and `SOURCE_NAMES` (`elections_calendar.model` / `snapshots`).
- Produces:
  - `release_problems(repo: Path, release_sha: str) -> list[str]`;
  - `release_row(sha256: str, count: int, *, root: Path = ROOT, code_sha: str | None = None) -> str`;
  - `main(argv: Sequence[str] | None = None) -> int` with `--release-sha HEX` and `--repo DIR`
    (default `ROOT`; the extension folder is `<repo>/extension`, the output `<repo>/dist`);
  - `republish.main` gains `--check`.

- [ ] **Step 1: Write the failing ZIP tests.**
  - The temporary repository: `git init` a directory with a copy of `extension/`,
    `requirements.txt`, `requirements-dev.txt` and a `.gitignore` holding `dist/`, then commit
    them.
  - **`test_a_release_build_needs_a_clean_tree_at_the_release_commit`**, parametrised:

| id | change before the build | `--release-sha` | exit | stderr holds |
|---|---|---|---|---|
| `ok` | none | HEAD | 0 | — |
| `untracked` | a new file `x.txt` | HEAD | 1 | `the working tree is not clean (1 changed or untracked, first: x.txt)` |
| `untracked_dir` | a new file `new/x.txt` | HEAD | 1 | `(1 changed or untracked, first: new/x.txt)` |
| `modified` | `extension/popup.js` edited | HEAD | 1 | `the working tree is not clean` |
| `other_commit` | none | `"0" * 40` | 1 | `HEAD is <HEAD>, not the release commit 0000…` (the full SHA) |
| `short` | none | `"abc1234"` | 1 | `--release-sha must be the full 40-character commit SHA` |

    For a refused build, `dist/` holds no ZIP, and (rev 2) stdout holds no `| 2.0.0 |` row.
  - **`test_a_release_build_works_from_a_detached_head`** (Review Focus 5):
    `git checkout --detach HEAD`, then the build exits 0.
  - **`test_the_release_row_carries_the_code_sha`:**
    - the `ok` build prints a row starting `| 2.0.0 | <HEAD> |`;
    - a build without `--release-sha` prints `<code SHA>` and the line
      `Development build: the RELEASES.md row needs --release-sha`.
- [ ] **Step 2: Write the failing republish tests** in `tests/ci/test_recovery.py`, with that
  file's repository fixtures.
  - **`test_republish_check_writes_nothing`:**
    - with a recorded pair, `republish.main(["--from-commit", sha, "--repo", str(repo), "--check", "--now", NOW])`
      returns 0;
    - stdout holds `recovery pair ok: <sha> (<digest>, recorded in RELEASES.md); its feed can be republished`;
    - `elections.json` and `status.json` are byte-identical to before, and
      `git status --porcelain` is empty.
  - **`test_republish_check_refuses_a_bad_pair`:** an altered digest returns 1 with the existing
    message, and nothing is written.
- [ ] **Step 3: Write the failing README test** `tests/unit/test_readme.py`,
  `test_readme_covers_the_release`. The README must hold:
  - each `SOURCE_NAMES[s]` for `s` in `SOURCE_ORDER`;
  - `docs/extension/v2.0.0-release-notes.md`;
  - `--release-sha`;
  - `--check`;
  - the four Load-unpacked steps' key phrases from the release notes ("Delete the folder's
    contents", "Developer mode", "Reload", "Don't remove the extension");
  - no "is being built" sentence.
- [ ] **Step 4: Run them; they must fail.**
- [ ] **Step 5: Implement.**
  - **`release_problems`:**
    - the SHA format first: if it fails, return only that problem;
    - then `git status --porcelain --untracked-files=all`: `n` lines, and `first` is the
      first line's path, in the message
      `the working tree is not clean ({n} changed or untracked, first: {first})`;
    - then `git rev-parse HEAD` against the SHA.
  - **`main`:**
    - parses its arguments;
    - with `--release-sha`, prints every problem to stderr and returns 1 before `build`;
    - fills `code_sha` only after the checks pass;
    - passes `root=repo` to `release_row`.
  - **`republish.main --check`:**
    - calls `recorded_pair` and `republish` as the write path does;
    - prints the line, then `nothing was written (--check)`;
    - returns 0 without writing.
  - **README:**
    - The opening paragraph describes v2 as released (`v2.0.0`).
    - A short "How it works" section: the sources, merge, health, publish and the extension,
      with a link to the spec.
    - A "Sources" section listing the nine sources and their pages.
    - An "Updating the extension" section with both install routes, copied from the release
      notes.
    - "Building the extension ZIP" gets `--release-sha`.
    - "Rollback" step 2 runs `--check` before writing.
- [ ] **Step 6: Run the new tests (pass), then all five gates.**
- [ ] **Step 7: Mutations** (`plan5c-task-4.json`):
  - the porcelain check removed (`[untracked]`);
  - `--untracked-files=all` removed, so git names the folder `new/` instead of the file
    (`[untracked_dir]`);
  - the HEAD comparison removed (`[other_commit]`);
  - (rev 2) `release_row` ignores `code_sha` and always writes `<code SHA>`
    (`test_the_release_row_carries_the_code_sha`). Rev 1's "`code_sha` filled before the
    checks" was an equivalent mutation: `main` returns before the row is built, so it
    cannot be killed and is dropped;
  - (rev 2) the `return 1` after the problems removed, so a refused build still builds
    (`[other_commit]`: a ZIP and a row appear);
  - `--check` falls through to the writes (`test_republish_check_writes_nothing`);
  - the README's release-notes link removed (`test_readme_covers_the_release`).
- [ ] **Step 8: Commit** `feat(release): guarded release ZIP, republish --check, README for v2.0.0 (Plan 5c Task 4)`.

## Part B: the rollout runbook

Each step lists its go-ahead (GA) and stop conditions. "Record" means the ledger. Repository
`newscorp-ghfb/global-elections-calendar` is written R below.

(rev 2) **Order:**
- B0–B6 prepare everything, with `main` changed only locally;
- B7 rehearses the rollback before anything of v2 is pushed to `main`;
- B8 pushes and publishes;
- B9–B10 are the live drills;
- B11 distributes the extension, only after the drills;
- B12 cleans up.

Rev 1 → rev 2 numbering: B7 → B9, B8 → B11, B9 → B10, B10 → B7, B11 → B12. Rev 1's B6 push is
now B8. (rev 3) B3b, R63's full check before the merge, sits between B3 and B4.

### B0. The real Reload on the user's Chrome (R66)

- [ ] Build a development ZIP in the worktree: `.venv/Scripts/python.exe -m scripts.build_extension_zip`.
- [ ] **R66, the real Reload.** The user:
  1. copies `tests/fixtures/v1/extension/` to a new folder (for example
     `C:/Users/senescalk/Desktop/gec-r66/`);
  2. loads it unpacked, pins two countries in its options and notes the ID;
  3. deletes the folder's contents, extracts the ZIP into it, turns Developer mode on and clicks
     Reload on the card;
  4. checks that the ID is the same, the version is 2.0.0, the pins show as places in the
     options, and the popup draws main's current (v1) feed with the legacy renderer.
  Then the user removes the test extension. Their real install is untouched.
- [ ] (rev 2) **R63 is not checked here.** main's v1 feed uses the legacy renderer, which hides
  the attention section, so R63 is checked on v2 data: in full in B3b (rev 3), and briefly on the
  final ZIP in B11 (P160).
- [ ] **Record** the user's notes and the development ZIP's SHA-256. **Stop** on any failure: a
  fix task on the branch comes first.

### B1. Push the branch; gates on GitHub (§15 step 1; R53, F5)

- [ ] **Before it:**
  - the user runs `! gh auth login --hostname github.com`;
  - `gh repo view R` works;
  - the user confirms they can push to R.
- [ ] **GA:** `git push -u origin feat/never-miss-v2`. It starts a push run: gates, then verdict.
- [ ] **Record:**
  - the run id and the runner image version;
  - each gates step's time (Install, Install Chromium, pytest, mypy, ruff, import-linter, the
    gates proof) against its allowance, and the job's total against 30 min;
  - the summary's collected, passed and skipped counts.
- [ ] **Expected:** green, `gates only`.
- [ ] **Stop:**
  - **red gates:** diagnose. A Linux-only failure gets a fix task on the branch, then a new GA
    push;
  - (rev 2) **P150's review trigger:** a job over 20 min, or one that leaves less than 5 min of
    the 30-min limit unused. Ask the user.

### B2. Dispatch on the branch (§15 step 1; R41, O1, O7, R5)

- [ ] **GA:** `gh workflow run update-elections.yml -R R --ref feat/never-miss-v2 -f publish=false`.
  It runs the branch's file, because the file name also exists on `main`. If `gh` refuses,
  the user uses Actions → "Run workflow" with the branch selected. Record which one worked.
- [ ] **Record:**
  - the scrape job's setup time (checkout, Python, switches, install) against `SETUP_ALLOWANCE_S`
    (300 s), and the scrape step's time;
  - **O7:** the user confirms that the run summary shows HEALTH.md. If not, the spec's fallback
    is a `diag` branch commit, with a GA;
  - **O1:** IPU's row: download outcome, units and severity;
  - **R5:** `trust_sources` is `["certifi"]`, and OSCE downloads `ok`;
  - the verdict headline. Expected: red, `not published: open warnings or errors`. The branch
    has no baselines yet, so every unit reason is new (P149).
- [ ] **Download the artifact:** `gh run download <id> -R R -n generation -D .scratch/plan5c/run-<id>`
  into a new folder. If it gets a 403, the user downloads it from the run page.
- [ ] **Stop:**
  - **IPU fails in CI:** ask the user. Options: a bounded acknowledgement (at most 14 days),
    or a follow-up task;
  - **OSCE fails TLS:** ask. This is spec O6's pinned emSign root, as a new task;
  - **setup over 300 s:** ask whether to re-argue `test_scrape_job_fits_its_timeout`.

### B3. Reviewed first baselines (§15 step 2; R42, P124, P158)

- [ ] **The same day as B2,** run the live check (TLS bundle set):
  `$env:PYTHONIOENCODING = "utf-8"; .venv\Scripts\python.exe -m scripts.live_check --out .scratch/live`.
- [ ] **Compare:**
  - (rev 2) **The live check's material lines.** Somalia and South Sudan *may* be accepted on
    record (P158). Each needs its evidence in the ledger first:
    - **Somalia:** the IPU line (its source, event, artifact path and line), the captured IPU
      page, and the wording "IPU's expected renewal date moved to 15 Apr 2027; expected-renewal
      evidence, not a polling date; outside the window";
    - **South Sudan:** the ElectionGuide 5108 line, the captured page, and the check that the
      rename lost no contest: the event's contests (office and date) in the CI artifact equal
      those in `.scratch/live/20261024T140811Z/`;
    - the user's acceptance of each one, in their words.
    Any other change for Somalia or South Sudan is a separate material line. Any other line is
    explained to the user, or fixed by a task before the merge.
  - **The CI artifact against the live check's live artifact,** with
    `scripts.live_check.compare(<CI artifact>, <live artifact>, tests/expected/2026-10-16.yaml, reviewed rows)`
    in `.scratch/plan5c/compare.py`. Lines that only say the CI artifact is not a dry run are
    expected; record them as such.
- [ ] **The user reviews** the CI HEALTH.md, the two reports and the manifest digest
  (`sha256sum .scratch/plan5c/run-<id>/manifest.json`), then approves "adopt `<digest>`".
- [ ] **Adopt** (the one sanctioned run):
  `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m elections_calendar.ci adopt --artifact .scratch/plan5c/run-<id> --manifest-sha256 <digest> --repo .`
  - It prints `adopted <n> files from the run of <code_sha> (manifest <digest>)`.
  - `<code_sha>` must equal the SHA that B2 dispatched.
- [ ] **Run all five gates,** then commit on the branch:
  `data(sources): first baselines from run <id> (manifest <digest>)`. If a test fails only
  because `data/sources/` now exists, stop and report: that test reads the real repository
  instead of a temporary one.
- [ ] **GA:** push the branch (a gates run). **GA:** dispatch on the branch again, as B2.
  (rev 3) Download its artifact as in B2, to `.scratch/plan5c/run-<id>`; B3b uses it.
- [ ] **Expected** (rev 2): green, `not published: no new unacknowledged issues`.
  - The unit reasons are now known (P149, the live proof).
  - (rev 3) This run's own HEALTH.md, from its downloaded artifact, shows them as
    `0 (+k known)`; record each source's cell. Its `Generated:` time is this run's, and its
    SHA-256 is in this run's manifest. The HEALTH.md committed on `main` is v1's, and is never
    this run's evidence. A branch artifact's `Outcome: published` means the generation passed
    validation; the run's headline says that nothing was published.
  - If a unit is new since B2, the run is red, and HEALTH.md shows which reason is not known.
    Record it and ask the user.

### B3b. R63's full check, before the merge, on B3's reviewed v2 data (R63; P160; new in rev 3)

- [ ] **The candidate build.** In the worktree, at B3's pushed commit with a clean tree:
  `.venv/Scripts/python.exe -m scripts.build_extension_zip --release-sha <B3 SHA>`. Extract it to
  `.scratch/plan5c/r63-candidate/`. Record the ZIP's SHA-256, its file count and the code SHA.
- [ ] **The session tool** `.scratch/plan5c/r63_session.py` (controller tooling, not repository
  code; the user reads it before it runs):
  - `--build DIR --artifact DIR [--minutes 20] [--self-check]`;
  - it launches Playwright's Chromium (`channel="chromium"`) with a new profile in
    `.scratch/plan5c/r63-profile/` (deleted first), `--load-extension` and
    `--disable-extensions-except` for DIR, and `--host-resolver-rules=MAP * ~NOTFOUND`. No real
    host can be reached, so no refresh can bring v1 data;
  - it routes `https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/*`
    (the same as `tests/support/extension.RAW_BASE`), as the extension tests do. By file name
    it serves the artifact's `elections.json` and `status.json`, and 404 for anything else. It
    logs each request: the time, the name, and the SHA-256 of what was served;
  - the extension's code and the build are not changed. The worker downloads, validates and
    caches the data itself;
  - `--self-check`: headless. It opens the extension's `popup.html` in a tab, waits up to 60 s
    for `body[data-renderer="v2"]` and at least one card, prints `self-check ok: v2, <n>
    cards`, and exits 0; otherwise it exits 1;
  - otherwise headed. It prints the extension id and waits until the user closes the window,
    or `--minutes`, whichever comes first;
  - always, in a `finally` block: it closes the context, then prints the request log and the
    served files' SHA-256s. It closes only its own browser; the user's Chrome is never
    touched.
- [ ] **Self-check** by the controller, after the memory check (stop under 2,500 MB):
  `.venv/Scripts/python.exe .scratch/plan5c/r63_session.py --build .scratch/plan5c/r63-candidate --artifact .scratch/plan5c/run-<B3 second run> --self-check`.
  Expected: `self-check ok: v2, <n> cards`, exit 0.
- [ ] **The user's session.** The user runs the same command without `--self-check`, in their
  own PowerShell window. Then, in that test browser:
  1. pins the extension's icon (the puzzle menu);
  2. sets the page zoom to 200 % at `chrome://settings/appearance`;
  3. opens the real action popup, and in its DevTools console (right-click → Inspect) reads
     `document.body.dataset.renderer` (must be `v2`) and `devicePixelRatio`. They also note the
     display's own scale (Windows Settings → Display). At 200 %, `devicePixelRatio` is twice
     the display scale;
  4. checks, with no horizontal scroll and every control reachable:
     - the attention section open;
     - a card expanded with many children, and its controls;
     - the health panel open, with several sources' issues (B3's data has them);
     - the month navigation;
     - both footer lines;
  5. closes the window.
- [ ] **Record:**
  - the candidate ZIP's SHA-256 and code SHA;
  - the artifact's manifest SHA-256, and the served files' SHA-256s;
  - the request log, which must hold only the routed files;
  - the renderer, `devicePixelRatio` and the display scale;
  - the user's result.
  Then delete `.scratch/plan5c/r63-profile/`.
- [ ] **Limits, recorded as such:** a routed host is not GitHub or its CDN. B8's served check
  and B11's short check cover the real path.
- [ ] **Stop** on a failure: a fix task on the branch (still editable). B4's review covers it,
  and B3b is repeated on the new build.

### B4. The merge review (§15 step 3.1)

- [ ] (rev 2) **First, the controller writes `C:/Users/senescalk/Desktop/handovers/elections-v2-plan5c-rulings.md`.**
  - (rev 3) It holds I2 and R37 if still open, and each "Ruling:" line still open, one row
    each: the ledger and line; the exact current behaviour; whether it departs from an
    approved requirement, and which; the recommendation; the consequence if wrong.
  - (rev 3) An index follows for every other "Ruling:" line: previously approved (with the
    reference), superseded (with the reference), or an implementation detail inside approved
    scope. An agent's earlier decision that still needs the user's approval stays on the open
    list, even when its code is done.
  - The user rules on each open row on its own, and on open choice 6. Nothing is approved as a
    bundle, and approving the open list approves nothing that is not on it.
- [ ] **One opus reviewer** on the named SHA, the branch HEAD after B3, with the scope ruled.
  - (rev 2) The scope includes the links between alert verdicts, publisher permissions,
    recovery, the popup's cache and render, release tags and packaging.
  - Brief: the worktree path, the branch, "do not create worktrees, do not switch branches, do
    not commit to main"; this plan; the ledger.
  - Critical and Important findings get one fix wave and a scoped re-review.
  - Then all five gates. If the code changed, a GA push and a GA re-dispatch, as B3. (rev 3) If
    an extension file changed, B3b is repeated on the new build.
  - (rev 2) Any later material diff gets a scoped re-review of that diff: a fix, or a rebase
    that changes more than `elections.json`.
- [ ] **Record** the verdict and the reviewed SHA.
- [ ] (rev 3) **Record F6's acceptance:** "F6: mitigated; residual risk accepted for this
  release". Record the owner (the user), the reviewed commit, and
  `git rev-parse <SHA>:.github/workflows/update-elections.yml`. The reviewer confirms the
  publish job's permission map, the workflow's entry points, and that no other credential is
  used (P151). A changed fact goes back to the user.

### B5. Rebase, tag and fast-forward, locally (§15 step 3.2–3.6)

- [ ] **The user says "merge".** Start after 01:00 UTC, and finish B8's push before 23:00 UTC.
- [ ] **In the worktree:** `git fetch origin`. Then
  `git diff --stat ff30417 origin/main` must list only `elections.json`. Any other file means
  stop: it needs a fresh review.
- [ ] (rev 2) **No release tag exists on `origin` yet:**
  `git ls-remote origin refs/tags/pre-v2 refs/tags/v2.0.0` prints nothing. Otherwise stop and
  ask (Global Constraints: a published tag never moves).
- [ ] **In the worktree:** `git rebase origin/main`. Record the rebased HEAD.
  `git diff <reviewed SHA> HEAD -- . ':!elections.json'` must be empty; then the gates only,
  each in its own call:
  - the suite in chunks under 600 s, with `chunk_cover.py`'s proof;
  - mypy for both platforms;
  - ruff;
  - lint-imports;
  - `.venv/Scripts/python.exe -m scripts.prove_gates`.
- [ ] **In the main checkout** (cd there):
  1. write `MERGE_APPROVED` holding the rebased SHA;
  2. `git merge --ff-only origin/main`;
  3. `git tag pre-v2 origin/main`, and record its SHA;
  4. `git merge --ff-only feat/never-miss-v2`; `HEAD` must equal the marker's SHA;
  5. `git tag v2.0.0`;
  6. delete `MERGE_APPROVED`;
  7. cd back to the worktree.
  `main` and both tags are local until B8.
- [ ] **Stop:**
  - **a non-fast-forward:** stop, and never force;
  - **an untracked file in the way:** stop and ask. The checked items do not collide.

### B6. The `pre-v2` pair, locally (R43, P155)

- [ ] **Write the pair.**
  - Its digest: `git -C <main checkout> show pre-v2:elections.json | sha256sum`.
  - Add the row under RELEASES.md's "Recovery pairs" in the main checkout:
    `| pre-v2 | <SHA> | <digest> | <date>, republish --check |`.
- [ ] **Check it** (it writes nothing):
  `.venv/Scripts/python.exe -m scripts.republish --repo C:/Users/senescalk/Desktop/elections-calendar --from-commit <pre-v2 SHA> --check`.
  It is run from the worktree, whose code equals `main`'s. Expected: `recovery pair ok: … recorded in RELEASES.md; its feed can be republished`.
- [ ] **Commit on `main`** (in the main checkout, with the marker, then delete the marker):
  `docs(releases): the pre-v2 recovery pair`. Nothing is pushed yet.

### B7. The rollback rehearsal on a local clone (RT-05; P156; rev 2: was B10, now before the first push)

- [ ] **Make the clone:** `git clone C:/Users/senescalk/Desktop/elections-calendar .scratch/plan5c/rehearsal`,
  then `git -C .scratch/plan5c/rehearsal remote remove origin`. Nothing can be pushed from it.
  - The clone holds local `main` at B6's commit, with `pre-v2` and the pair's row.
  - v2 has not published yet, so its `elections.json` is still v1's.
  - The rehearsal proves the commands, the checks and the time, which is RT-05's point.
- [ ] **Follow README "Rollback" steps 1–3 verbatim in the clone, timed.** Run git in the clone,
  and run the Python modules from the worktree with `--repo <clone>`:
  1. commit `PAUSE_PUBLISHING`;
  2. `scripts.republish --repo <clone> --from-commit <pre-v2 SHA> --check`, then run it without
     `--check`, then commit;
  3. the restore and its commit.
- [ ] **Check:**
  - `git diff pre-v2 HEAD --stat` lists only the excluded paths (`ROLLBACK_EXCLUDES`);
  - `elections.json` carries `republished_from_sha256` equal to the pair's digest;
  - `status.json` has outcome `republished`;
  - `PAUSE_PUBLISHING` is gone;
  - the workflow file equals `pre-v2`'s;
  - the total time is under 2 h.
- [ ] **Record** the results, then delete the clone.
- [ ] **Stop** on a failed check. Nothing has been pushed, so after the fix, local `main` and the
  local tags are re-made with the user's go-ahead (B4's review covers the fix).

### B8. Push `main` atomically; the first publication (§15 step 4; P157, P159; rev 2)

- [ ] **Rehearse the push (P159):** `bash .scratch/plan5c/push_probe.sh` in the worktree.
  - It builds a local bare repository whose branch has moved, then pushes a branch and two
    tags plainly and with `--atomic`.
  - Expected: `atomic push: exit 1, every remote ref unchanged: yes`, and exit 0.
  - It uses neutral ref names and no remote, so no `main` is involved.
  - Record its output.
- [ ] **Before the push:** `git ls-remote origin refs/heads/main refs/tags/pre-v2 refs/tags/v2.0.0`.
  Record it; `main` must still equal `pre-v2`'s SHA, and neither tag may exist.
- [ ] **GA: push**, from the main checkout with the marker:
  `git push --atomic origin main refs/tags/pre-v2 refs/tags/v2.0.0`. Then delete the marker.
- [ ] **After it, whatever it printed:** run the same `git ls-remote` and compare with the local
  values. Record both, then follow P159:
  1. **all three unchanged on `origin`:** back to B5's fetch. The local tags may be re-made,
     and B6's row and `--check` are redone if `pre-v2` moved. B7 is not repeated unless more
     than `elections.json` changed;
  2. **all three equal the local values:** the push succeeded, even if git reported an error.
     Go on;
  3. **anything else** (one ref moved, or a tag on `origin` with another value): stop and ask,
     and never move a tag that is on `origin`.
  Never force.
- [ ] **Record** the push run (gates only on `main`): green, `gates only`.
- [ ] **GA: the first publication (P157):**
  `gh workflow run update-elections.yml -R R --ref main -f publish=true`.
- [ ] **Check:**
  - the publish outcome is `published`, served `ok`;
  - the SHA-256 of `curl -s https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/elections.json`
    equals `status.json`'s `serving_feed_sha256`;
  - HEALTH.md on `main`;
  - the verdict is green, or red for a new unit, which is explained;
  - **v1.0.2 renders the v2 feed:** the user's own install shows cards in the months. The known
    v1.0.2 limits are in the release notes. The S5-T17 tests are the automated evidence.
- [ ] **Stop:**
  - **`served_mismatch`:** wait one CDN period, then compare again (P127). If it persists, ask;
  - **`validation_failed`:** nothing was published. Diagnose; v1's last feed is still served.

### B9. The alert test and the re-run drill (§15 step 5; RT-07, S4-T13, R46 re-runs; P156; rev 2: was B7)

- [ ] (rev 2) **One GA, before anything else here, covers both `ALERT_TEST`'s push and its
  removal** (Global Constraints).
  - The removal is pushed after the first 00:00 UTC run that has the marker finishes, and
    before 23:00 UTC that day, whether or not the email has arrived.
  - Email diagnosis goes on after the removal. Another alert run needs a new GA.
- [ ] **GA:** dispatch run A on `main`, `publish=true`.
- [ ] **While A is in its gates job** (under the paired GA): commit `ALERT_TEST` on `main` (in the
  main checkout, with the marker) and push it. Expected: A's publish is `superseded`, and
  nothing is committed.
- [ ] **GA:** `gh run rerun <A> --failed`, then **GA:** `gh run rerun <A>`. For each attempt,
  record:
  - the attempt number and the jobs it ran. `ci publish` exits 0 when superseded, so the
    failed-only re-run probably runs `verdict` alone; record what GitHub does;
  - (rev 2) **the `generation` artifact that attempt's publish job actually downloaded:** its id
    and the attempt that uploaded it, from that job's `download-artifact` log
    (`gh run view <A> -R R --attempt <n> --log`, or the job's log page). The run's artifact
    list alone is not enough;
  - the head SHA (still the original);
  - the outcome: `superseded` or a red verdict, with nothing committed.
- [ ] (rev 2) **R46's re-run half is verified only** when every attempt is `superseded` or red
  with nothing committed, and each attempt's consumed artifact is identified. A full re-run may
  be refused at upload because the artifact name already exists in the run. Record that refusal
  as a finding, or as a limit the user accepts on record. It never counts as a pass.
- [ ] **The next 00:00 UTC run** publishes normally, then fails with `alert test`. The user
  confirms the email arrived.
  - GitHub documents that scheduled-run emails go to the user who last changed the workflow's
    cron line. If no email arrives, that is the first suspect.
- [ ] **Remove `ALERT_TEST`** (under the paired GA) on `main` (marker) and push it, within the
  bound above.
- [ ] **The next 00:00 UTC run** must not be `alert test`, and `ALERT_TEST` must be absent from
  `main`. It is green, unless HEALTH.md shows a data reason; record which.

### B10. The disable/enable and concurrency drills (R44, R46; P156; rev 2: was B9)

Never run these between 23:00 and 01:00 UTC.

- [ ] **R44: disable and enable.**
  1. (rev 2) **One GA covers the disable and its enable.** The enable runs as soon as step 4 has
     a result, and in any case within 60 min of the disable, even if the diagnosis is
     unfinished.
  2. **GA:** dispatch run B on `main` with `publish=false`.
  3. While B runs: `gh workflow disable update-elections.yml -R R`.
  4. `gh workflow run ... --ref main -f publish=false` must be refused. Record the message.
     B must finish on its own. Record its result.
  5. `gh workflow enable update-elections.yml -R R` (under the paired GA).
  6. A dispatch with `publish=false` runs again. Record its id.
  7. (rev 2) **Record R44 precisely:** "dispatch refused while disabled: observed". A disabled
     workflow also skips its schedule. That is GitHub's documented behaviour, not observed
     here, because the disable never spans 00:00 UTC. It is recorded as such, not as proof.
- [ ] **R46: concurrency** (rev 2: judged on observed states).
  1. **GA:** three dispatches with `publish=true` on `main`, within one minute. They are named
     by run id, never by order.
  2. **Watch** with a Monitor bounded to 60 min. Every 30 s while any of them is unfinished,
     record `gh run view <id> -R R --json headSha,jobs` for each: the head SHA, and the publish
     job's status, conclusion, `startedAt` and `completedAt`, with the time read.
  3. **Judge from the records only:**
     - **serialised:** no two publish jobs are `in_progress` at once; their run intervals do
       not overlap;
     - **the pending publisher replaced:** at some read, one publish job was running and one
       was pending, and then a newer one queued. The older pending one ends `cancelled`, and
       its run's verdict is `publish failed`;
     - **obsolete generations rejected:** every publish job that ran after another had moved
       `main` reports `superseded` and commits nothing;
     - the user confirms the failure emails of the red runs.
  4. Any order that keeps these rules is correct, whichever run was dispatched first.
  5. **Inconclusive:** if no read shows one running and one pending publisher when a newer
     run queues, the replacement rule is *inconclusive*, neither passed nor failed. Ask before
     one retry (a new GA), or the user rules on the limit on record. R46 is never marked
     verified from dispatch times.
  6. **Record:** the reads, the head SHAs, which pending publisher was cancelled, each verdict,
     the emails, and `main`'s commits (`git ls-remote origin refs/heads/main` before and after).
- [ ] **Before B11:** every drill of B9 and B10 is passed, or the user has ruled on its limit on
  record.

### B11. The final ZIP's short R63 check, then the extension release (§15 step 6; R62, R63, R65, O4; P160; rev 2: was B8)

- [ ] **Before it:** B7's rehearsal is recorded, and B9's and B10's drills are passed or ruled on.
- [ ] **In the worktree:** `git rev-parse HEAD` must equal `git rev-parse v2.0.0`, and the tree
  must be clean.
- [ ] **Build:** `.venv/Scripts/python.exe -m scripts.build_extension_zip --release-sha <v2.0.0 SHA>`.
  Then build again; the SHA-256 must be identical (R62, same toolchain). Record both, with the
  Python and zlib versions.
- [ ] (rev 3) **Compare the final ZIP with B3b's candidate (P160).**
  `.scratch/plan5c/zip_files.py <final ZIP> <candidate ZIP>` lists each file's SHA-256 and
  prints `same files`, or each difference. Record it.
- [ ] (rev 3) **The short R63 check on the real path.** The user:
  1. extracts the final ZIP to a new folder (for example `C:/Users/senescalk/Desktop/gec-r63/`)
     and loads it unpacked as a separate test extension in their Chrome. Its popup loads the
     live v2 feed from GitHub;
  2. sets Chrome's default page zoom to 200 % (Settings → Appearance → Page zoom) and opens
     the popup;
  3. reads `document.body.dataset.renderer` (`v2`) and `devicePixelRatio` in the popup's
     DevTools console, and notes the display's own scale;
  4. checks that the attention section, a card's children and both footer lines show with no
     horizontal scroll. **If any extension file differed,** they go through B3b's whole
     checklist instead;
  5. restores the zoom and removes the test extension.
  - **Record:** the ZIP's SHA-256; the served feed's SHA-256 at that time, and that it equals
    `status.json`'s `serving_feed_sha256`; the renderer, `devicePixelRatio` and the display
    scale; the user's result.
  - **Stop** on a failure: v2.0.0 is not distributed, and the fix ships as v2.0.1 by a short
    fix plan.
- [ ] **The user** fills in the row's destination, date and approval.
  - Commit the row on `main` (marker): `docs(releases): v2.0.0`.
  - **GA:** push it (`git push origin main`).
- [ ] **The user:**
  - shares the ZIP and `docs/extension/v2.0.0-release-notes.md` with the Load-unpacked users;
  - uploads the ZIP to the company Web Store listing;
  - **O4:** confirms the Store update, and whether a permission prompt appeared;
  - checks their own v2 install on the live feed: the banner, the cards, and the pins kept.
- [ ] **Record** the user's notes.

### B12. Housekeeping (§16; R45; rev 2: was B11)

- [ ] **The v1.0.2 ZIP** (rev 2: its code is matched, never assumed).
  - List the ZIP's files, with or without a leading `extension/`. Compare each file's SHA-256
    with `git show <commit>:extension/<path>`:
    - at `ff30417`;
    - and at each commit where `extension/manifest.json` says `1.0.2`
      (`git log --format=%H -- extension/manifest.json`, checked with `git show`).
  - If one commit's `extension/` matches every file, with nothing missing and nothing extra,
    the row's code is that commit, written "contents match `extension/` at `<sha>`".
  - Otherwise the code is "unknown: the contents match no commit". Never write an unmatched
    SHA.
  - Record the ZIP's SHA-256 in RELEASES.md: a `1.0.2` row with that code and destination
    "(historical)".
  - Move the file to the main checkout's `dist/`.
  - Commit on `main` (marker), then **GA:** push.
- [ ] **`build_elections_pptx.py`:** per open choice 9 (default: leave it untracked). If it is
  included, review it, update its text to the help page's wording (5 months, the sources), and
  commit it on its own (marker, GA push).
- [ ] **R45:** per open choice 8 (default: keep the `dowjones` remote). Record the answer.
- [ ] `.gitignore` and `.gitattributes` (§16) were done in Plan 1 Task 1; nothing to do.
- [ ] **The main checkout's emergency `.venv`:**
  - `py -3.14 -m venv .venv`;
  - `.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-dev.txt`;
  - then `republish --check --from-commit <pre-v2 SHA>` there must exit 0.
- [ ] (rev 2) **`.scratch/`** (in both checkouts), only after the rollout:
  - give the user the exact deletion list;
  - unique captures, the mutation tooling and tables (`.scratch/mutate.py`,
    `.scratch/mutations/`, `handovers/elections-v2-tooling/`) and the reproducibility records
    stay unless the user names them;
  - never delete `.scratch/plan2c/captures-2026-10-19/` without the user.
- [ ] **Cleanup, each step with the user's GA:**
  - close the processes that use the worktree;
  - `git worktree remove` it, and report any leftover folder rather than retrying;
  - delete the local branch;
  - delete `origin/feat/never-miss-v2`.
- [ ] **Update** the ledger, the RESUME doc and the memory file, then grep them for `\x07`.

## Review record

| Row | What | Verified by | Status |
|---|---|---|---|
| P149 (rev 3) | known unit reasons by unit key (scope, outcome, text) and count; the green headline | Task 2's tests; B3's second run | planned |
| P150, P151 (rev 2) | gates limit as a provisional budget; wheel-only installs as a mitigation | Task 1's tests; B1, B2; the user's F6 ruling | planned |
| P152, P153 (rev 2) | options pins before the check; only a skipped reply skips the second render | Task 3's tests; P139's test unchanged | planned |
| P154, P155 | release guard, `--check` | Task 4's tests; B6, B11 | planned |
| P156 (rev 2) | drills, in order, judged on observed states | B7, B9, B10 records | planned |
| P157, P158 (rev 2) | first publication; differences accepted only with evidence | B8, B3 records | planned |
| P159 (rev 2) | atomic push of `main` and the tags | B8's probe and `ls-remote` records | planned |
| P160 (rev 3) | R63's full check before the merge; a short check before distribution | B3b's and B11's records | planned |
| R66 | the real Reload | B0 notes | planned |

## After Plan 5c

- `main` holds v2 at `v2.0.0` and publishes daily. (rev 2) A run is red when a unit appears
  that the last served data did not have, or when any other warning or error is open and
  unacknowledged. A lasting failure such as a timeout is red on every run while it lasts.
- RELEASES.md holds the `pre-v2` pair, the v2.0.0 row and the v1.0.2 ZIP.
- The extension v2.0.0 is shared and in the Web Store.
- The drills and the rehearsal are recorded.
- The worktree and the branch are gone.
- Still open, outside this plan:
  - O2 (`Mogzauri14/Exp_KS2025` still publishes a v1.0.0 feed; ask the user);
  - the South Sudan alias (the user: "for later").
