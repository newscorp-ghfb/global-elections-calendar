# Never-miss v2, Plan 3: Merge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 3 (2026-10-20).** Written against `fa4d0a2`, still in seven tasks.
- **Sources:**
  - revision 2 (sha256 `6d4f326d8da4abe28370aa1f0ab43cdba215794e6903860fb19891366bd58c21`);
  - the review of 20 October, findings R2-01–R2-05 and two clarifications
    (`Downloads/never-miss-v2-plan-3-revision-2-review-2026-10-20.md`);
  - the user's decisions on the clarifications (2026-10-20): **D4** (a cached `held` claim still
    confirms that a vote took place; only overriding a word needs a fresh claim) and **D5**
    (`less_precise` only for a coarser date; any other change of the served date is `moved`).
- **What changed:**
  - P69, P72, P74, P75, P79 and P81 are revised; `RejectedReason` gains `"old_date"`;
  - Tasks 1 and 3–6 carry the new rules, tests and mutations. Task 2 is unchanged, and Task 7's
    values are unchanged;
  - two revision 2 inputs change, with their expected values kept: Task 4's `ln` gets level
    `subnational` (R2-02 would split it off), and `pnm` moves to 22 November, because on the
    contest's own day its row could not kill its mutation (`mut7b.py`);
  - "Review record" has a row for each finding and decision, and R25 and the new R26 hand work to
    Plans 4 and 5.
- **Fixture delta: none.** The revision 3 prototype gives revision 2's fixture result field by
  field, with all its new rules on and with each one off (`check28.py`). So every count, id and
  property-test number below is revision 2's. Synthetic tests pin each new rule.
- **Weight (the extension).** Revision 3 adds no record field. R26 asks Plans 4 and 5 to measure
  the feed and the popup before they ship.
- **The semantic items under "Spec corrections" (P67–P78 and P80–P82) still need the user's
  approval before Task 2 starts.** Revision 3's changes to P69, P72, P74, P75 and P81 are among
  them.

Revision 2's notes follow.

**Revision 2 (2026-10-19).** Written against `fa4d0a2`, still in seven tasks.
- **Sources:**
  - revision 1 (sha256 `bec49f2a3f81f2db5af01183a27d5f483fb083dbed7a9b3d6ce7c510f2ccd739`);
  - the red-team review of 19 October, findings G01–G08
    (`Downloads/never-miss-v2-plan-3-red-team-review-2026-10-19.md`);
  - its rulings (`Downloads/claude-code-plan-3-revision-rulings-2026-10-19.md`);
  - the user's decisions D1–D3 on those rulings.
- **What changed:**
  - P69, P71, P74, P75, P77 and P79 are revised, and P80–P82 are new; P67 and P72 restate
    their measurements;
  - Tasks 1–7 carry the new rules, tests, mutations and counts;
  - "Review record" maps each finding to its task and test.
- **The fixture delta comes from P81 (umbrella scope) and P77 (relevance) only:**
  - umbrella links drop from 66 to 47, aggregate children rise from 131 to 150 and cards from 732
    to 742;
  - in-window evidence items rise from 1 to 5.

  The fixtures have no cancellations, stamped freshness or provisional claims, so G01 and
  G03–G06 change no fixture value. Synthetic tests pin those rules.
- **Measurement:** every count was measured by prototypes that implement exactly these rules (see
  "How to execute this plan"). Revision 1's values are kept beside the changed ones in the
  prototype outputs.
- **The pre-flight** (revision 1) took:
  - every "Requirements for later plans" row that Plans 1, 2a, 2b and 2c gave to Plan 3: R3–R8,
    R12, R13, Plan 1's C7, and Plan 2a's three merge rows;
  - Plan 2c's known limits;
  - the S3 rows of the spec's acceptance catalogue, NM-T06, V2-T01 and V2-T02.

  Each one has a row in "Review record", and so does each review finding and decision.
- **The semantic items under "Spec corrections" (P67–P78 and P80–P82) need the user's approval
  before Task 2 starts.** Each one gives the alternative and what it would cost.

**Goal:** Turn the nine adapters' claims into contests, cards, undated listings and attention items
(spec §10).
- Every claim gets exactly one disposition.
- A conservation audit stops the merge on any failure.
- The output is identical for identical evidence, in any input order.
- Nothing is serialised yet (Plan 4). v1 keeps running unchanged.

**Architecture:**
- **`model.py`** gains the merge's output records: `ChildSource`, `Child`, `BibEntry`, `Card`,
  `UndatedListing`, `AttentionItem`, `Disposition` and `MergeResult`, plus five Literal
  vocabularies. `_conforms` learns `tuple[X, ...]`.
- **A new package, `elections_calendar/merge/`,** fills the `(merge)` layer of the import-linter
  contract (spec §4):
  - `identity.py`: source priority, roles, identity (with qualified numbers) and date
    compatibility, rule F, short ids;
  - `select.py`: resolved-value selection (§10.5) and the legacy status (§5.9, §10.6);
  - `match.py`: Phases A–D, umbrellas, aggregates and possible matches (§10.1–§10.4);
  - `cards.py`: children, cards, undated listings, attention items and dispositions (§5.3–§5.5,
    §10.7);
  - `conservation.py`: the identity-based audit (§10.8);
  - `__init__.py`: `merge(claims, *, now, places) -> MergeResult`.
- **Tests:** `tests/merge/`, plus two helpers: `tests/support/claims.py` (a claim builder) and
  `tests/support/fixture_claims.py` (the nine adapters' claims on their fixtures).

**Tech Stack:**
- Python 3.14.1;
- the standard library (`hashlib`, `dataclasses`, `itertools`);
- `hypothesis` 6.170.1, already pinned in `requirements-dev.txt`, for the property test.

No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`.
- Read these sections before you start:
  - §5.2–§5.5 and §5.9;
  - §10, all of it;
  - §13.3: the S3 row, NM-T06, V2-T01 and V2-T02;
  - §13.4 "Merge tests";
  - Appendix B.
- Where this plan and the spec differ, the plan wins *only* for the items under "Spec corrections".
- Plan 2c (`docs/superpowers/plans/2026-10-19-never-miss-v2-plan-2c-ndi-eisa.md`) is built at
  `fa4d0a2`. Its Interfaces blocks describe the code, except where the errata below say otherwise.

## "As built" errata (read first)

**Plan 2c** (built at `fa4d0a2`: 1164 tests, mypy 61 files, ruff clean, `Contracts: 2 kept, 0 broken`):
- **P65, a rule beyond the Plan 2c text:** an NDI page fails `layout_not_recognised` when a card
  holds more than one `.date-type`, or when `.date-type` elements sit outside the card lists.
- Plan 1's must-miss pin `find("PH", "Bangsamoro") is None` was deleted, because P51 reverses it.
- **What the merge receives** (measured on the fixtures; `tests/support/fixture_claims.py` builds
  the same claims):
  - **1335 claims:** ElectionGuide 243, Wikipedia 543, OSCE 180, IPU 234, A-WEB 31, Carter 18,
    EEAS 23, NDI 38, EISA 25.
  - **Provenance is unstamped.** Every claim has `fetched_at` None, `fallback` False,
    `snapshot_id` None and `provisional` False; Plan 4 stamps them. The freshness and provisional
    rules are therefore pinned on synthetic claims only.
  - **`source_event_id`** comes only from ElectionGuide and IPU. No source repeats one.
  - **Evidence kinds:**
    - `calendar`: ElectionGuide, Wikipedia, OSCE, A-WEB, NDI, EISA;
    - `expected_renewal`: IPU;
    - `observation`: Carter, EEAS.

    No adapter emits `umbrella`. Umbrellas come from the role rule (§10.2).
  - **Status claims:**
    - ElectionGuide: `held` 198;
    - EISA: `held` 13, and `postponed` 2 (`eisa:y2026/r16#0` and `#1`, Somaliland, "Postponed
      from June 2026 to 2028", with `previous_date_text` "June 2026"). Both have year precision
      (2028), so both become undated listings (P68) and set no contest's status.

    No observation has a status claim.
  - **Year precision:** 61 claims (Wikipedia 26, EEAS 23, OSCE 8, EISA 3, NDI 1).
- **Known limits carried forward from Plan 2c:**
  - `unnamed_parts` gives false alarms on joint tickets ("Presidential and Vice-Presidential") and on
    "National and Provincial". They are loud. Deciding them is Plan 4's (R21), because the merge
    sees only claims.
  - EISA duplicate keys are committed row by row (practically unreachable, and loud).
  - NDI cards that differ only by an alias title: see P70. Plan 2c said "Plan 3's merge joins
    them"; under rule F it does not.

## Plan series

1. **Foundations** (done, `8632297`).
2. **Sources:** 2a (done, `f5f3a1c`), 2b (done, `94ac45a`), 2c (done, `fa4d0a2`).
3. **Merge (this plan).**
4. **Health, snapshots, feed and publishing.**
5. **Workflow, extension v2.0.0 and rollout.**

**Not in this plan:**
- **No serialisation.** `elections.json`, `content_id`, the 500-item attention cap and
  `attention_truncated` are Plan 4's (R17).
- **No unit-level attention items:** `unparsed_unit`, `partial_unit`, `disappeared_unit`, and
  `provisional_change` for units. They come from units and snapshots (Plan 4, R20). The merge
  builds items only for claims.
- **No provenance stamping, and no provisional claims from real runs** (Plan 4, R19).
- **Nothing outside the merge changes:** no change to `scraper.py`, the adapters,
  `.github/workflows/` or `extension/`.
- No network access. Nothing is pushed or merged.

## Global Constraints

Plan 1's, 2a's, 2b's and 2c's Global Constraints still hold:
- **Code:**
  - the layering (the import-linter layers contract);
  - civil dates;
  - no network in tests;
  - `[0-9]`, never `\d`, in new regexes.
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

- **The merge is pure.** `merge` takes the claims, a timezone-aware `now` and the place registry.
  It reads no file, clock or environment variable, and it never changes its input claims.
- **It fails closed** (§10.9). `MergeError` is raised for:
  - a duplicate `merge_id`;
  - a contest with no eligible date;
  - an unknown source;
  - any conservation problem.

  Nothing is dropped or overwritten silently.
- **Determinism.** The output depends only on the *set* of input claims.
  - Every order in this plan is total and stated.
  - A tie never falls back to input order, or to set or dict iteration order.
  - `merge` on a permutation of the claims returns an equal `MergeResult`.
- **Ids.** `short_id(parts)` is the first 12 hex characters of SHA-1 over `"\n".join(sorted(parts))`,
  UTF-8 encoded. Child, group, undated and attention ids all use it (Task 2).
- **The layer.** `merge` replaces `(merge)` in `importlinter.ini`. The package imports only from
  `model`, `text`, `dates`, `offices`, `places` and `window`, and from its own modules.
- **The window.** Relevance and the legacy status use `window_for(now)`. `today` is the UTC civil
  date. "In the window" is a visibility flag applied after resolution. The merge drops nothing
  that falls outside it (§10.8).
- **Literals and messages.** Literal values and error messages are copied verbatim from this plan.

## Review Focus

These are the five inputs most likely to hurt a user that the spec implies but no step spells out.
Each one is pinned by the named tests, in the task that owns the code.

1. **Evidence that disagrees by days or a month:**
   - a rescheduled election;
   - a source that is a few days off;
   - a month that misses the polling day;
   - two copies of one event with different dates.

   None of these is merged on proximity alone, and none is dropped. Each becomes separate contests
   linked by `possible_matches`, or one contest with `date_conflict`. A rescheduling in a contest
   sets aside the claims that still give the old date (`old_date`, R2-01), so the child shows the
   new date. Pinned by:
   - `test_old_dates` (Task 3);
   - `test_possible_matches`, `test_month_disagreement` and `test_ipu_chamber_id_is_not_an_election_cycle`
     (Task 4);
   - `test_month_claim_attaches_with_date_conflict` (Task 4, on the fixture);
   - `test_a_rescheduled_child_follows_its_new_date` (Task 5).
2. **Stale, fallback or refetched evidence next to an explicit status.** Plan 4 will stamp it.
   - Stale evidence can still win when it is more certain or more precise.
     - When fresh evidence of the same kind disagrees, the child says so (`date_conflict`).
     - When nothing fresh supports the same assertion, the child says that too (`unverified`).
     - A fresh renewal or a containing month is not that support (P69).
   - A cancellation stays `Cancelled`, flagged, against a refetched listing or confirmed date.
     Only a fresh `held` claim from another family, for the selected date, overrides it (P75,
     R2-01).
   - A fallback claim never overrides a word and never opposes one. A cached `held` claim still
     confirms that the vote took place (D4), and the child's source keeps its `fetched_at` and
     `fallback`, so its age stays visible.
   - A `held` claim confirms only the selected date: one for another date never sets
     `occurrence_confirmed` (R2-01).
   - A rescheduled election shows its new date, `Upcoming` before it (D2, R2-01).

   Pinned by `test_freshness`, `test_status_claims`, `test_rescheduling_lifecycle`, `test_old_dates`
   and `test_ndi_tbd_never_confirms_a_date` (Task 3), and by `test_child_fields` (rows 10–13) and
   `test_a_rescheduled_child_follows_its_new_date` (Task 5).
3. **The same evidence in another order, twice, or duplicated.**
   - The result is equal, and every id is equal.
   - A replayed copy adds no conflict.
   - A duplicate `merge_id` stops the merge.

   Pinned by `test_inputs_in_any_order_give_the_same_result`,
   `test_property_any_order_and_conservation`, `test_replay_is_idempotent` and
   `test_duplicate_merge_id_stops_the_merge` (Task 6), and `test_fixture_order` (Task 7).
4. **Vague claims:** an unknown jurisdiction, an unknown level, an unstated round, a generic or
   aggregate label, an observation, a district number in a label.
   - Each attaches only to a single justified contest. Two claims that contradict each other
     never attach together (P82).
   - An umbrella covers only the contests inside its scope (P81). An umbrella whose district,
     phase or series number differs from a contest's never covers it (R2-03).
   - Two offices the parsers do not recognise (class `general`, level `unknown`) share an
     aggregate child only when their labels are equal (R2-02).
   - Otherwise it stays visible: as its own contest, an umbrella link or an attention item.
   - It never joins a wrong contest. Districts with different numbers never join (P80).

   Pinned by:
   - `test_weak_claims`, `test_rounds`, `test_generic_legislature`, `test_umbrella_links`,
     `test_umbrella_scope`, `test_attachments_are_checked_together`, `test_same_source_rule` and
     `test_unmatched_umbrellas_cluster` (Task 4);
   - `test_subdivision_claim_never_joins_a_nationwide_contest` and `test_qualified_numbers`
     (Task 2);
   - `test_wrong_merge_is_caught` and `test_umbrella_coverage_is_checked` (Task 6).
5. **Very large or odd cards:**
   - US 3 Nov has 59 children;
   - labels over 200 characters;
   - jurisdictions that contain commas;
   - places not in the registry.

   The type is never longer than 200 characters and is deterministic, and every child stays on the
   card. Pinned by `test_card_type` and `test_unknown_place_shows_its_raw_name` (Task 5), and by
   `test_fixture_merge_counts` (Task 7: the longest type is 200 characters, the largest card has 59
   children).

**Known limits, by design.** The measured values include each of these, and each is visible:
- **Alias titles within one source (P70).** Two NDI cards for one election under two titles
  ("2026 Côte d'Ivoire Presidential Election", "2026 Ivory Coast Presidential Election") give two
  children on one card. With an ElectionGuide claim beside them, all three become `ambiguous` and
  linked. This is loud, not silent. None is in the fixtures.
- **Two `unknown` jurisdictions never join** (§10.1). Two sources' "Mayor" with no named city give
  "Mayor · Mayor" on one card (S3-T3).
- **Umbrella coverage is per child; the bibliography is per card.**
  - An `umbrella_link` disposition targets exactly the children the umbrella fits (P79, P81).
  - The card's `umbrellas` and `umbrella_sources` list every umbrella linked to any of its
    children, so they show beside the card's other children too (§10.4: "a scoped link in the
    card's `umbrella_sources`").
  - Example: Brazil's round-2 A-WEB umbrella targets only the 25 Oct presidency child, on the card
    that also holds a referendum child (S3-T13).
  - Plan 5 shows the coverage per child (R25).
- **Unrecognised offices stand alone** (P81, R2-02). The adapters give the shape `general` of
  unknown level to offices they do not model (a court, a retention vote).
  - Such a claim is never linked as an umbrella.
  - It shares an aggregate child only with a claim whose label is equal under `norm_name`, from
    any family. So "Supreme Court" and "Court of Appeals" stay two children. The cost: one such
    office under two labels gives two children.
  - Two genuine umbrellas also stand alone as aggregate children: the US "midterm elections"
    (3 Nov), and OSCE's Canada 2025 "Early Federal election".
- **District identity comes from the label** (P80).
  - Numbered districts, wards, phases and series are compared, in identity and in umbrella
    coverage (R2-03).
  - A named district without a number ("Holborn and St Pancras") relies on the jurisdiction and
    rule F.
  - Bare numbers (seat totals, counts, years) are ignored.
  - A label without a number is no evidence either way.
- **No reinstatement or supersession is represented** (P75, D1). A cancellation stays `Cancelled`,
  flagged, against any later listing or confirmed date. Only a fresh `held` claim from another
  family, whose date overlaps the selected date, overrides it (R2-01). The merge cannot tell when
  a source made its assertion: fetch time is not assertion time.
- **A cached `held` claim confirms that a vote took place** (D4), but never overrides or opposes a
  word. That a vote took place does not expire. The claim's age stays on the child's source
  (`fetched_at`, `fallback`), for Plan 5 to show (R22).
- **A past rescheduled election** shows the legacy `Held` on its new date, with
  `occurrence_confirmed` False unless a `held` claim gives that date. The passing of its new date
  is not proof that the vote took place. v2 shows it as past and unconfirmed (Plan 5, R25).
- **A postponement in another contest that names the old date** links the two contests (P74).
  The old-date contest keeps its own status: `Held` once its day has passed. A postponement in
  the same contest (joined, or attached by month disagreement) sets the old-date claims aside
  instead, and the contest follows the new date (R2-01).
- **A year-only claim that attaches can give the child's label,** when its source ranks highest.
  Serbia's 25 Dec 2026 child shows OSCE's "Early Presidential Election" (`osce:elections/r6#0`,
  attached as `year_only`).
- **The selection never counts corroboration.** Three sources that agree beat one that disagrees
  only through the order of §10.5, never by number.
- **Relevance comes from the claim's own date** (P77). An item dated January–August of the
  current year is `before_window`. A year-only item of the current year is `in_or_after_window`,
  even when its only candidates are in March. Plan 4 decides which items to serialise.

## Spec corrections

These were found while measuring the merge on the fixtures and on synthetic cases. They were
revised after the red-team review (G01–G08) and the user's decisions D1–D3, and again after the
review of 20 October (R2-01–R2-05) and decisions D4 and D5.
- **Semantic decisions:** P67–P78 and P80–P82 change what the calendar says, what it flags, or how
  a run is judged. They need the user's approval before Task 2 starts.
- **The other corrections** (P66, P79) refine vocabulary, names and checks.

Every "Measured" value below is the effect on the fixture run at `now` = 2026-10-19T00:00Z, with
the correction switched off one at a time: `alt4.py` for revision 1's rules, `alt6.py` for
revision 2's, and `check28.py` for revision 3's (no fixture effect).

| ID | Spec says | This plan does | Why / alternative |
|---|---|---|---|
| P66 (vocabulary) | §10.2 rule 3: an anchor's jurisdiction is "`nationwide` or `named`" | `subdivision` counts as named. An anchor's jurisdiction is `nationwide`, `named` or `subdivision`, and identity compares a named and a subdivision jurisdiction by name | Plan 2b's P38 split "named" into `named` and `subdivision` after the spec was written. Measured: 26 claims become `anchor_member` instead of `standalone`, and no in-window card changes. Alternative: subdivisions stay weak; they still cluster in Phase C |
| P67 (semantic; R5, R6, B06) | §10.2 puts class `general` first, so an observation (class `general`, P28) would be an umbrella. §10.5 step 1 ranks `observation` third for selection. §10.3: observations with 0 candidates become attention items | **An observation** (`evidence_kind="observation"`) gets the role `weak`, before the umbrella rule. **Its candidates** are the Phase A contests of the same place whose every member's date is compatible (`dates_compatible`). Office identity is not compared, because observations name no office (P28). 1 → attached; 0 → `unresolved_evidence` `no_candidate`; 2 or more → `several_candidates`. It never takes part in month disagreement. **It is never eligible for selection** (`rejected_reason="observation"`). It never gives a child's label or identity fields, never sets `occurrence_confirmed`, and never takes part in the status, as claimer or as contradiction. It does appear in the bibliography | This settles R5's open policy. A mission's year or observation month is never a polling date, so §10.5's observation tier is removed. Measured: the 41 observations give 5 attached claims and 36 attention items, of which 31 are before the window and 5 in it (P77; revision 1 had 35 and 1). Without the weak role, observations become umbrellas, and the unmatched ones cluster into aggregate contests that have no eligible date, so the merge fails closed. Alternative: keep the tier, which lets "EU election observation mission (2026)" become a contest's only date |
| P68 (semantic; R8) | §7 "Year-only → undated". §10.3: year = same year for candidates. §5.5: `undated[]` "holds year-only calendar claims that didn't attach to exactly one contest" | **A year-precision claim** is never eligible (`rejected_reason="year_only"`) and never creates a contest. **A weak year-only claim** with exactly one candidate attaches (§5.5's own rule). Otherwise it goes to an undated listing, whose `possible_matches` are its candidates. **A year-only umbrella** goes to an undated listing. Year-only claims that are pairwise `joinable` share one listing. **Year-only observations** (EEAS) follow P67, not this rule | R8 says "never a dated contest", while §5.5 allows attaching to exactly one. Measured: 35 year-only claims give 31 listings (Wikipedia 24, OSCE 7, EISA 3, NDI 1). 3 attach (Fiji, Slovakia 2027, Serbia `osce:elections/r6#0`), and none of the 3 is selected. EEAS's 23 year claims give 22 attention items and 1 attached claim (Guyana). Without the attach rule, the 3 become listings too. Alternative: R8's literal rule, which loses the link to the one contest each names |
| P69 (semantic) | §10.5 order: eligibility, coverage, date_status, precision, freshness, priority. "A fresh claim beats a fallback claim more than 7 days old". `unverified`: "every claim supporting the selected date is fallback data older than 7 days" | **Order:** (1) **eligibility**: observations and year-only claims are out; the best tier wins, with `calendar` (and `umbrella` evidence) above `expected_renewal`; a lower tier gets `lower_evidence`. (1b) **old dates (R2-01):** when the pool holds a rescheduling (P75), a claim that is not dates-compatible with it, or that lies inside its old date where the old date lies inside its new one, is set aside (`old_date`) and sets `date_conflict`. (2) **coverage**, among the day-precision claims (Task 3). (3) **precision before date_status.** (4) date_status. (5) freshness. (6) priority. **Stale** = `fallback` and (`fetched_at` is None, or `now − fetched_at` > 7 days); exactly 7 days is fresh. **The flags (G05)** look at the *support set*: the eligible claims with the winner's `evidence_kind`. **`date_conflict`:** the winner is stale, and a fresh claim of the support set has an interval that does not contain the winner's. **`unverified`:** every claim of the support set with the winner's (`start`, `end`), `date_meaning` and precision is stale. Umbrella-role claims are eligible inside their own aggregate contest and as C7 attachments | **Precision before status:** A-WEB's day range "14–15 Nov" (`unknown`) must beat NDI's "November 2026 (TBD)" (`tentative`). Otherwise a TBD month replaces two known polling days. Measured: no fixture effect (1 `less_precise`); the synthetic case flips. **`umbrella` evidence:** no adapter emits it, and ranking it with `calendar` keeps an aggregate contest selectable. **The flags (revision 2):** a fresh IPU renewal is not support for a stale polling date. A fresh "November (TBD)" that contains the stale day is missing support, not a disagreement. A calendar claim with another `date_meaning` is another assertion. Measured: no fixture effect (no stamped claims); 4 synthetic rows change (Task 3). **Old dates (revision 3):** beside "postponed from 15 November to December", a source that still lists 15 November must not date the child. Without the step, coverage selects the old day, and the status calls it `Held` once that day has passed (R2-01). Measured: no fixture effect (0 `old_date`). Alternative: the spec's order, revision 1's flags over every eligible claim, and no old-date step |
| P70 (semantic) | §10.1 identity key | **Rule F:** two claims from one source family join only when their `office_label`s are equal under `norm_name`. Wikipedia national and Wikipedia local are two families. The rule applies wherever claims join: Phases A–D, C7, aggregates and possible matches | One source lists distinct races separately. Wikipedia local's "State House District 12 special election" and "State House District 40 special election" share place, institution, subdivision and date. Measured: without the rule, 13 more children merge and 14 selections change. **Cost:** one source's alias titles for one election stay apart (see "Known limits"). This replaces Plan 2c's limit "Plan 3's merge joins them". Alternative: no rule F |
| P71 (semantic; Plan 1 C7) | §6.3: a generic legislature label is identity "when exactly one chamber contest exists for that place and date" | **A legislature umbrella** (class `legislature`, `aggregate=True`) attaches to the single contest from Phases A and C that meets all of these: it is not ambiguous; all its members are of a chamber class (`lower_house`, `upper_house`, `legislature`); none has a referendum kind; and every member is compatible with the umbrella, ignoring kind and institution, under rule F and dates. So is every non-observation claim already attached to it. **The proposals for one contest are checked as a set (P82):** two that are not compatible with each other (ignoring kind and institution), or fail rule F, both stay umbrellas. Otherwise it stays an umbrella. Once attached, it can be selected, but never gives the child's label | A bicameral place needs the other claims, and only the merge has them (Plan 1 moved this here). Measured: 14 attach. Grenada's Wikipedia "Parliament" joins IPU's House of Representatives, and Wikipedia is selected. Without the rule, the 14 become umbrella links and 3 selections change. Spain's OSCE "Parliamentary Elections" sees two chambers, so it stays an umbrella. South Sudan's Wikipedia "Assembly" sees one chamber after rule F |
| P72 (semantic) | §10.4 "Unmatched umbrella: a standalone `aggregate` contest" | **Unmatched umbrellas cluster** when they have the same office class, compatible identity ignoring institution, rule F and compatible dates. **An unrecognised claim** (class `general`, level `unknown`) clusters only with a claim whose `office_label` is equal under `norm_name`, from any family (R2-02). Each cluster is one aggregate contest (`Child.aggregate=True`) | Slovenia's OSCE "Local Elections", Wikipedia's "local elections" and NDI's November are one grouping, not three. Measured on revision 1's rules (`alt4.py`): 131 aggregate children instead of 138, and in-window cards +3/−1. With P81 the fixture has 150 aggregate children. **The label rule (revision 3):** a shared fallback shape is no evidence of one office, so Georgia's "Supreme Court" and "Court of Appeals" stay two children. Measured: no fixture effect. Cost: one unrecognised office under two labels gives two children. Alternative: one aggregate per umbrella claim; revision 2's clustering, which merges two courts |
| P73 (semantic; Plan 2a merge row) | §5.3 `possible_matches` (provisional). §10.2: ambiguity neighbours. Plan 2a: one source's copies of a `source_event_id` "link (§7) and never corroborate … the merge flags the conflict" | Besides §10.2's neighbours and the candidates of unresolved items, two contests are linked both ways when: (a) **rescheduling hint:** a claim's `previous_date_text` names a date that overlaps another compatible contest's span; (b) **near dates:** two compatible contests of one place are 1–7 days apart (`gap_days`); (c) **event copies:** one source's claims with one `source_event_id` sit in two contests. IPU is excluded from (c), because `ipu:<code>` names a chamber (R3). Copies inside one contest with different intervals set `date_conflict` | Measured: 4 children are linked (Kyrgyzstan: ElectionGuide 27 Jan vs NDI 24 Jan 2027; Cameroon: EISA December 2026 vs IPU January 2027). Without (b), there are 0. Alternative: §10.2's links only |
| P74 (semantic; R3, S3-T4; G06, D3, D5) | §10.1. R3 (b): the same chamber id with dates days apart, plus same-cycle evidence → "one rescheduled cycle" | **IPU chamber ids never join contests;** they are not identity. **A provisional twin** (the served claim with the same `claim_id`, in some contest) attaches to that contest whatever its date, across a year end too (Phase D). **The change is judged against the twin's served copy (G06, D3, D5):** the same span, or a finer span inside it (a day inside the served month), is no change. A coarser span that contains it (a day becoming its month or its year, a month its year) sets `Child.provisional_date="less_precise"`. Any other span, including a longer or a shorter range of days, sets `"moved"` and `date_conflict`. **With no twin:** a non-year span that neither contains nor lies inside the contest's span sets `"moved"` and `date_conflict`; a year-only claim says nothing. `date_text` alone never counts. **A postponement from another source that names the old date** links the two contests (P73 a). They are never merged. **Two IPU dates days apart with no such evidence** give two contests, linked when 7 days or less apart | R3 (b) is met for one unit: one contest, flagged. Across sources the merge links instead of merging, because identity plus a named previous date is not proof of one cycle. **Precision:** a day withdrawn to its month or year is a visible loss of precision, not a disagreement; 2026 → 2027 is a disagreement. **D5 (revision 3):** 15 November → 14–15 November keeps day precision and changes the polling days, so it is `moved`, never "less precise"; so is 14–15 → 15 November. Provisional claims stay unselected and keep one disposition. Measured: no fixture effect, because there are no provisional claims and no IPU repeats. Without the twin rule, a provisional date moved across New Year is `no_candidate`. Alternative: merge on a named previous date; revision 1's `date_conflict` for every non-year change and none for a year; revision 2's `less_precise` for any containing span |
| P75 (semantic; S1-T5, S3-T11; G04, D1, D2; R2-01, D4) | §5.9 rule 1: "A resolved postponed/cancelled claim (no fresh dated calendar claim contradicts it)". §10.6 | **Order:** `cancelled` before `postponed`. **An opposing claim** is a non-fallback `calendar` claim of day or month precision from a family other than every claimer's. **A word stands (D1):** beside an opposing claim with no status word, it is kept and `status_conflict` is set. **Only an opposing `held` claim whose interval overlaps the selected date overrides it (R2-01):** `status_conflict` is set and the next rule is tried. A `held` claim for another date sets `status_conflict`, and the word stands. **A rescheduling (D2):** a `postponed` whose every claimer has a `previous_date_text` and a non-year date follows the date rules on its own (new) date, with `rescheduled` True. Selection sets the old-date claims aside (P69 step 1b), so the selected date is the new one (R2-01). `Child.rescheduled_from` lists the old dates. **Opposed words:** two of `cancelled`, `postponed` and `disputed`, not fallback and from different families, set `status_conflict` whichever word wins. **A fresh `disputed`** is one that is not fallback. **Observations never take part.** **`occurrence_confirmed`** needs a `held` identity claim, fallback or not (D4), whose date is compatible with the selected claim's (R2-01), and a resolved word other than `cancelled` and `postponed`. **Phase D:** a provisional claim gives `status_conflict` when its word differs from the contest's (the resolved word, or `postponed` for a rescheduling), except a `held` claim where the contest has no word | **This reverses spec §5.9 rule 1 and §10.6:** a fresh listing no longer resolves a cancellation. A refetched page cannot prove that a cancellation was reversed. Fetch time is not the time of the assertion, and the model has no reinstatement evidence (rulings on G04). "Fresh" is read as "not fallback": a cached claim never overrides or opposes a word. It still confirms that a vote took place (D4): that does not expire, and the child's source keeps the claim's age. A `held` claim for another date (one attached by month disagreement) says nothing about the selected date, so it neither lifts a word nor confirms one (R2-01). A source never contradicts itself, and a year-only claim never does (P68). A rescheduled election belongs in the upcoming schedule. After its new date, the legacy `Held` is a compatibility mapping, and `occurrence_confirmed` stays False. Measured: 0 `status_conflict` on the fixture. EISA's two Somaliland postponements ("from June 2026 to 2028") have year precision, so they are undated listings (P68) and set no status. Revision 3 measured no fixture effect either (`check28.py`). Alternative: revision 1 (any fresh listing contradicts), which shows a cancelled election as `Upcoming`; revision 2 (a `held` claim of any date overrides, and confirms) |
| P76 (semantic) | §10.7: type "1 child: its `office_label`"; "`<Label>: <jurisdiction list> (<n>)`"; "Truncated to 200 characters + ' (+k more)'". §5.4: the bibliography | **The display label** (for the type) is the child's `office_label`, with " (Nth round)" added when the child's round is stated and the label states none (`extract_round`), and a "`<jurisdiction>: `" prefix when the jurisdiction is named or subdivision and its `norm_name` is not inside the label's. **The type** (Task 5): one child gives its display label; one office class over distinct named jurisdictions gives `"<Plural>: <jurisdictions> (+k more) (<n>)"`; anything else gives display labels joined with " · ", plus " (+k more)". It takes the longest run of items that fits in **200 characters including the suffix**. **The bibliography** leaves out provisional claims | Without the context, 30 in-window types change: "Mayor · Mayor", or a governor without "Bahia". The spec's "200 + suffix" can exceed 200, which v1.0.2's layout never had. Alternative: the spec's text |
| P77 (semantic; R6; G07) | §5.5: the item's relevance. R6: "year-aware relevance, never `Window.overlaps` alone" | **Relevance comes from the item's own claims (revision 2):** a year-precision claim is `in_or_after_window` when its year is the window start's year or later; any other claim when its span ends on or after the window start. **An item with several claims** is `in_or_after_window` when any claim is. Candidates never date an item | An EEAS "2026" mission whose candidates were all in March 2026 is still unresolved current-year evidence, and the candidate set may be incomplete (G07). A dated historical mission stays `before_window`. Measured: 5 in-window evidence items (Colombia, Peru, Bangladesh, Zambia, São Tomé) instead of 1. Alternative: revision 1's rule (an observation's item takes its relevance from its candidates), which gives 1 |
| P78 (semantic; S3-T2) | §10.1: "Referendum questions are children only when a source lists the questions; otherwise there is one `referendum_day` contest per place and date" | Two `referendum_question` claims are identity-compatible only when their `office_label`s are equal under `norm_name`. **A `referendum_day` contest beside an all-question contest** of compatible identity (kind ignored) and date is dissolved: its claims become umbrellas, and those link only to all-question contests. No other umbrella links to a contest with a referendum kind | A session is a grouping of its questions, not a third contest beside them. Fixture: Switzerland 29 Nov (ElectionGuide and Wikipedia `referendum_day`) is one contest, because no source lists the questions. Alternative: the session stays a contest next to its questions |
| P79 (interfaces; G02, G08; R2-04, R2-05) | §10.8 dispositions and checks; §5.3–§5.5 fields | **The API** is in Tasks 1–6, with `MergeError(ValueError)`. **Dispositions:** members of an aggregate contest are `standalone`, and `umbrella_link` targets are the sorted child ids the umbrella fits (G02). **Holders (G08):** every claim the result holds must be an input, equal to it field by field. **Wrong merge is role-aware (G08):** the identity claims of a child are pairwise identity-compatible and rule-F-compatible. The exceptions are explicit: observations and provisional claims are checked for place only; an attached claim's date is checked unless the child has `date_conflict` (month disagreement); C7 legislature claims skip kind and institution, in a child of chambers only; an aggregate child skips institution and holds one office class. **Joined dates (R2-04):** a child's joined claims (`anchor_member`, `standalone`) are pairwise `dates_compatible`, whatever its `date_conflict`. **Coverage (R2-05):** each `umbrella_link`'s targets are exactly the non-aggregate children its umbrella covers (`umbrella_covers`, Task 4), and no member of an aggregate child covers one. **Missed merge:** two children of one place, neither ambiguous nor aggregate, whose joined claims (`anchor_member` and `standalone`) are pairwise `joinable`, and each of which is the other's only such partner. **Display:** a place not in the registry shows its first claim's `place_raw`, with `country_code` None. **Attention text** is "`<country>: <office_label> (<date_text>)`" (Task 5). **Child ids** follow §5.3 after all attachments | §10.8 names the checks but does not define them. Revision 1's audit accepted a changed payload, an untracked holder and a legislature aggregate inside a presidency (G08). Revision 2's accepted two joined claims on disjoint days, and a link moved to another child of the same card (R2-04, R2-05). Measured on the fixture: 0 problems and 0 joinable pairs, in revision 3 too (`conserve7.py`) |
| P80 (semantic; G01) | §10.1 identity key: place, level, institution or class, jurisdiction, round, kind | **Qualified numbers are identity.** `qualified_numbers(office_label)` maps each qualifier (`district`, `ward`, `constituency`, `seat`, `phase`, `series`, `division`, `precinct`, `circuit`, `zone`, `position`, `place`) to the numbers it qualifies. It reads "District 12", "District No. 12" and "12th … District" (up to four words between). When two claims both state a qualifier, its numbers must be equal, whatever their families. Bare numbers (years, seat totals, counts) are ignored, and rounds stay in `round` | Rule F kept District 12 and District 40 apart only within one family; across families they joined (G01). "District 12, Phase 2" and "District 2, Phase 12" differ by qualifier, not by number. Measured: 74 of the fixture's 77 numbered labels yield qualifiers; no fixture pair is blocked, so no count changes. Cost: named districts without numbers rely on the jurisdiction and rule F (Known limits). Alternative: compare every bare number, which reads "150 seats" as identity |
| P81 (semantic; G02, R2-03) | §10.4: an umbrella "fits" a contest; "a scoped link". Plan 2a merge row 1 | **An umbrella covers only the contests inside its scope.** Besides place, referendums, dates, level and round: a `named` or `subdivision` umbrella covers only contests whose every member has that jurisdiction (`norm_name`); a `legislature` umbrella only chamber contests; a `local_council` umbrella only councils and mayors; any other class except `general` only its own class. **A `general` umbrella of unknown level never links**, because it may be an unrecognised office. **Qualified numbers (R2-03):** for each non-observation claim of the contest, attached ones included, every qualifier that it and the umbrella both state gives equal numbers (P80). Each link records the children it fits (P79) | Measured: 19 fewer links (66 → 47), and each one becomes an aggregate child (131 → 150); cards 732 → 742. In the window: +1 card and +5 children; the US 3 Nov card has 59 children instead of 56. 17 of the 19 links were wrong attributions, for example: Alabama "local elections" and Tennessee "county elections" over the 51 children of every state on 3 Nov; Georgia's "Supreme Court" and "Court of Appeals"; Mexico's "state elections" on the federal Chamber of Deputies. 2 were genuine umbrellas of unknown level, which now stand alone: the US "midterm elections" and OSCE's Canada 2025 "Early Federal election" (`check24.py`). **The numbers (revision 3):** a "District 12" umbrella that C7 rejects for "District 40" must not link to it either; the anchor's attached claims count, because an anchor may state no district. A nationwide umbrella with no number still covers every district. Measured: no fixture effect. Alternative: revision 1's fit (place, date, level and round only); revision 2's scope without the numbers |
| P82 (semantic; G03) | §10.3: a weak claim with exactly one candidate attaches | **Attachment proposals are checked as a set.** Phase B collects each contest's proposals: single candidates and month disagreements. Two proposals for one contest that are not identity-compatible with each other (relaxed when either jurisdiction is `unknown`), or fail rule F, are *conflicting*, and neither attaches. A conflicting dated claim becomes an `unresolved_evidence` item, with the new reason `conflicting_claims` and that contest as its candidate. A conflicting year-only claim goes to the undated pool, with that candidate. C7 proposals are checked the same way (P71) | One anchor with no stated round admits a round-1 and a round-2 claim one at a time. Together they make a contest with two rounds, and the audit would stop the whole feed (G03). Measured: no fixture effect (0 `conflicting_claims` items). The result does not depend on input order (Task 6). Alternative: attach the first in order, which does |

**Also settled (no spec change):**
- **§10.3's "exactly one candidate" for an `unknown` jurisdiction.** Phase B searches with the
  jurisdiction relaxed, and attaches only when that gives exactly one candidate. Two or more give
  `several_candidates`.
- **Month disagreement** compares every identity field strictly (no relaxing), under rule F. The
  claim's start year must be in every member's years.
- **Phase D's "within the same year"** means that every member shares a year with the provisional
  claim (`years_of`). The twin rule (P74) comes first.
- **Plan 2a's third merge row** (executive titles stay in `leftover`) needs no merge code. The
  adapters emit no claim for them (Plans 2a–2c, `office_not_modelled`).
- **D1–D3** are the user's decisions on the rulings (2026-10-19): D1 and D2 are in P75, and D3 in
  P74. D3 keeps `date_conflict`'s meaning ("sources disagree on the date"). A loss of precision is
  `provisional_date="less_precise"` instead, so Plan 5 can say that the source now gives a less
  precise date (R25).
- **D4 and D5** are the user's decisions on the review's two clarifications (2026-10-20):
  - **D4 (P75):** a cached `held` claim confirms occurrence; only overriding a word needs a fresh
    claim. The claim's `fetched_at` and `fallback` stay on the child's source.
  - **D5 (P74):** `less_precise` means a coarser precision (a day becoming its month or year, a
    month its year). Any other change of the served date, including a longer or a shorter range of
    days, is `moved`, with `date_conflict`.

## Review record

**Status:** "planned" becomes "verified" only when the SDD ledger records the task's commit, with
the named test passing and its mutation killed.

| ID | Kind | Ruling | Task · test | Status |
|---|---|---|---|---|
| R3 | Plan 2b requirement | P74. Its completion stage moves from the identity task to the matching task, where the twin rule and P73 live | T4 `test_ipu_chamber_id_is_not_an_election_cycle` | planned |
| R4 | Plan 2b requirement (Plan 3 part) | An unmatched renewal is a standalone contest, `tentative` and `expected_window` | T7 `test_unmatched_renewal_is_expected_not_announced` | planned; Plan 5 part open |
| R5 | Plan 2b open policy (B06) | P67 | T3 `test_unknown_meaning_observation_is_never_a_polling_date`, `test_unknown_meaning_observation_never_makes_held_or_ongoing` | planned; legacy-feed case open (Plan 4) |
| R6 | Plan 2b requirement (P28) | P67, P77 | T4 `test_observation_with_zero_one_and_several_candidates`; T5 `test_year_only_observation_stays_accounted_for` | planned |
| R7 (extended by 2c) | Plan 2b requirement (B07) | A subdivision is never compatible with a nationwide jurisdiction, even relaxed | T2 `test_subdivision_claim_never_joins_a_nationwide_contest` (OSCE r52, A-WEB r5, NDI past-c6) | planned |
| R8 | Plan 2b requirement | P68 | T4 `test_year_only_claims`; T7 `test_year_precision_claims_are_undated` | planned |
| R12 | Plan 2c requirement | Month disagreement (§10.3) | T4 `test_month_claim_attaches_with_date_conflict` | planned |
| R13 (extended) | Plan 2c requirement | P69's coverage and `unverified`; P68 | T3 `test_ndi_tbd_never_confirms_a_date`, `test_an_inferred_month_never_confirms_a_day`; T7 `test_a_year_only_claim_stays_visible` | planned |
| P28 / B06 | Plan 2b decision | The weak role comes before the umbrella rule | T2 `test_roles` | planned |
| C7 | Plan 1 deferral | P71 | T4 `test_generic_legislature` | planned |
| Plan 2a merge (1) | Requirement | Class `general` and aggregates are never specific contests. They link as umbrellas, or form aggregate groupings flagged `Child.aggregate` | T4 `test_umbrella_links`, `test_unmatched_umbrellas_cluster`; T5 `test_child_fields` | planned |
| Plan 2a merge (2) | Requirement | P73 (c): copies link, and copies that disagree are flagged | T4 `test_possible_matches` | planned |
| Plan 2a merge (3) | Requirement | Executive titles never reach the merge | — | satisfied by Plans 2a–2c |
| Plan 2c limit (NDI aliases) | Known limit | P70 replaces "the merge joins them" | T4 `test_same_source_rule` | planned |
| S3-T1, T3, T7 | Spec acceptance | Mayor vs council; aliases and empty jurisdictions; candidates outside the window | T4 `test_weak_claims` | planned |
| S3-T2 | Spec acceptance | P78 | T4 `test_referendum_questions_and_sessions` | planned |
| S3-T4 | Spec acceptance | P74 | T4 `test_ipu_chamber_id_is_not_an_election_cycle` | planned |
| S3-T5 | Spec acceptance | 18/19/20/21 and a bridge | T4 `test_phase_a_components`; T6 `test_inputs_in_any_order_give_the_same_result` (120 orders) | planned |
| S3-T6, NM-T06 | Spec acceptance | Rounds | T4 `test_rounds`; T6 `test_inputs_in_any_order_give_the_same_result` (6 orders) | planned |
| S3-T8 | Spec acceptance | Replay idempotence; a duplicate `merge_id` | T6 `test_replay_is_idempotent`, `test_duplicate_merge_id_stops_the_merge` | planned |
| S3-T9, T10, T12 | Spec acceptance | Coverage; renewal vs polling evidence; a past unverified date | T3 `test_selection`, `test_freshness` | planned |
| S3-T11, S1-T5 | Spec acceptance | An old cancellation refetched; fallback never resurrects a cancellation | T3 `test_status_claims` | planned |
| S3-T13, T14 | Spec acceptance | A scoped umbrella; partial umbrella parts | T4 `test_umbrella_links` | planned |
| S3-T15 | Spec acceptance | Lost-plus-duplicated input caught by the id audit | T6 `test_lost_and_duplicated_inputs_are_caught` | planned |
| S3-T16 | Spec acceptance | The merge raises `MergeError`; blocking publication is Plan 4's (R18) | T6 `test_merge_runs_the_audit` | planned (Plan 4 part open) |
| S3-T17 | Spec acceptance | Real v1.0.2 pins | — | Plan 5 |
| S3-T18, T19 | Spec acceptance | The card certainty split; child identity through a split and a rejoin | T5 `test_cards_split_by_certainty_and_meaning`, `test_child_identity_through_split_and_rejoin` | planned |
| V2-T01, V2-T02 | Spec acceptance (merge part) | Phase D. "An unchanged candidate gives no provisional change" is Plan 4's (R19) | T4 `test_provisional_claims`; T5 `test_attention_items` | planned |
| §10.9 property tests | Spec | Hypothesis, fixed seed | T6 `test_property_any_order_and_conservation` | planned |
| Appendix B | Spec regression cases | Field by field on the fixture | T7 `test_appendix_b` | planned |
| G01 | Red-team review (high) | P80 | T2 `test_qualified_numbers`, `test_identity_compatible` (district rows); T4 `test_same_source_rule` (`d12 n40`, `d12 n12`, `d12 e12`), `test_attachments_are_checked_together` (`ua d1 d2`) | planned |
| G02 | Red-team review (high) | P81; P79's child targets | T4 `test_umbrella_scope`, `test_umbrella_links`; T5 `test_dispositions`; T7 `test_fixture_merge_counts` | planned; Plan 4 and 5 parts are R24 and R25 |
| G03 | Red-team review (high) | P82; P71's set check | T4 `test_attachments_are_checked_together`; T6 `test_clean_results_pass_the_audit`, `test_inputs_in_any_order_give_the_same_result` (`a w1 w2`, 6 orders) | planned |
| G04 | Red-team review (high) | P75 (D1, D2); completed by R2-01 | T3 `test_status_claims`, `test_rescheduling_lifecycle`, `test_old_dates`; T4 `test_provisional_claims`, `test_ipu_chamber_id_is_not_an_election_cycle` (`e i1`), `test_month_disagreement` (`a mR`, `ac hO`); T5 `test_child_fields` (rows 9–13), `test_a_rescheduled_child_follows_its_new_date` | planned |
| G05 | Red-team review (medium) | P69's support set | T3 `test_freshness`, `test_ndi_tbd_never_confirms_a_date`, `test_an_inferred_month_never_confirms_a_day` | planned |
| G06 | Red-team review (medium) | P74 (D3, D5) | T4 `test_provisional_claims`; T5 `test_child_fields` (row 7) | planned |
| G07 | Red-team review (medium) | P77 | T5 `test_relevance_of`, `test_year_only_observation_stays_accounted_for`; T7 `test_fixture_merge_counts` (5 in-window evidence items) | planned |
| G08 | Red-team review (medium) | P79's holders and role-aware identity | T6 `test_wrong_merge_is_caught`, `test_changed_and_unknown_holders_are_caught`, `test_property_any_order_and_conservation` (its guard) | planned |
| D1 | User decision | A cancellation stays `Cancelled`, flagged; only a fresh `held` claim from another family overrides it; reinstatement is not represented | T3 `test_status_claims` | planned |
| D2 | User decision | A rescheduling follows its new date, with `Child.rescheduled_from`; after it, legacy `Held` with `occurrence_confirmed` False. Revision 3 makes the selected date the new one (R2-01) | T3 `test_rescheduling_lifecycle`, `test_old_dates`; T5 `test_child_fields` (row 9), `test_a_rescheduled_child_follows_its_new_date` | planned |
| D3 | User decision | `Child.provisional_date` (`moved`, `less_precise`); `date_conflict` keeps its meaning. D5 narrows `less_precise` | T4 `test_provisional_claims` | planned |
| R2-01 | Review of 2026-10-20 (high) | P69 step 1b (`old_date`), P75 (a `held` claim must overlap the selected date, to override and to confirm) | T3 `test_old_dates`, `test_status_claims` (`canc`, `hOct`); T4 `test_month_disagreement` (`a mR`, `ac hO`); T5 `test_child_fields` (rows 12 and 13), `test_a_rescheduled_child_follows_its_new_date` (before the old date, between the two, after the new one) | planned |
| R2-02 | Review of 2026-10-20 (high) | P72's label rule for unrecognised claims | T4 `test_unmatched_umbrellas_cluster` (`ca sc`, `sc sc2`, `ll lnU lo`; `ll ln lo` still one child) | planned |
| R2-03 | Review of 2026-10-20 (high) | P81's qualified numbers, over every non-observation claim of the contest | T4 `test_umbrella_scope` (`c40 lg12`, `c40 ug12`, `c12 c40 ug12`, `a0 w40 ug12`, `ph1 ph2 up2`, `ph1 up2`; `gs gv lg` still links); T6 `test_umbrella_coverage_is_checked` | planned |
| R2-04 | Review of 2026-10-20 (medium) | P79's joined dates | T6 `test_wrong_merge_is_caught` (the 16 November row), `test_changed_and_unknown_holders_are_caught` (its span row); `test_clean_results_pass_the_audit` (attachments and provisional changes still pass) | planned |
| R2-05 | Review of 2026-10-20 (medium) | P79's exact coverage | T6 `test_umbrella_coverage_is_checked` (the referendum redirect, the referendum added, a Peru target dropped, an aggregate member that covers a child); `test_clean_results_pass_the_audit` (`gb p1 p2 rf u` on one card, `ms nN pz r` on two) | planned |
| D4 | User decision (review clarification 1) | P75: a cached `held` claim confirms occurrence and never overrides; its age stays on the child's source | T5 `test_child_fields` (rows 10 and 11) | planned |
| D5 | User decision (review clarification 2) | P74: `less_precise` only for a coarser precision; a longer or shorter range of days is `moved` | T4 `test_provisional_claims` (`e per`, `er pes`, `e pem`, `er pem`) | planned; Plan 5 wording in R25 |
| Extension weight | User note (2026-10-20) | Revision 3 adds no record field; R26 makes Plans 4 and 5 measure the feed and the popup against a budget the user sets | — | Plans 4 and 5 (R26) |
| Somaliland wording | Red-team review (documentation) | The errata and P75 now say that EISA's two postponements are year-only (2028) and undated | T7 `test_year_precision_claims_are_undated` (EISA 3 `undated`) | planned |
| P66–P82 | Decisions (P67–P78 and P80–P82 need approval) | As in "Spec corrections" | Each task's tests, as named there | planned |

## How to execute this plan

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Do not create worktrees, do not switch branches, do not commit to `main`.
  - Keep the shell in the worktree. Use `( cd … && … )` subshells for anything elsewhere.
- **Style:** this plan pins names, signatures, rules and test values; you write the bodies.
  Private helpers are yours. If a rule is ambiguous, stop and ask the controller. Never guess a
  value.
- **Measured values:** every count in the tests was measured by prototypes that implement exactly
  these rules.
  - **Prototypes** (revision 3), in `.scratch/plan3/proto/`. They extend revision 2's, below.
    - `merge3r7.py`: the reference merge. `build_r7.py` builds it from `merge3r6.py` by exact-string
      edits. Its switches `r7_old_date`, `r7_held_date`, `r7_unknown_label`, `r7_umbrella_numbers`
      and `r7_range_moved` turn revision 3's rules off one at a time, and its
      `occurrence_confirmed(k)` is Task 5's rule.
    - `conserve7.py` (Task 6's audit) and `synthlib7.py` (`mk` on `merge3r7.py`), built by
      `build_c7.py`.
    - **The fixture:** `check28.py` → `check28.txt`. The fixture result of `merge3r7.py` equals
      `merge3r6.py`'s field by field, with all switches on and with each one off. `conserve7.py`
      finds no problem, `occurrence_confirmed` counts 197, and no claim is `old_date`. **So
      revision 2's fixture outputs (`r6_*.txt`) stay the reference.** `check26.py` and
      `check27.py` reproduce the review's cases and measure their fixture exposure (none).
    - **Synthetic cases:** `port7.py` writes `synth7a.py`–`synth7n.py` and `prop7.py` from
      revision 2's scripts. Their outputs equal `synth6*.txt` except for four explained rows:
      - `synth7c` and `synth7g`: `ll ln lo`, where `ln` has level `unknown`. R2-02 splits it off,
        so `synth7g`'s two-office-classes row finds a one-claim child. Task 4 gives `ln` level
        `subnational`, which keeps both rows (`synth7o.txt`), and `lnU` is the new row;
      - `synth7e`: `e per` is `moved` (D5);
      - `synth7g`: the holder row with another span also gives the joined-dates message (R2-04).

      `synth7f.py` gives each claim its row's span, as Task 3's tables say; it then equals
      `synth6f.txt`. `synth7j.py` holds Task 4's IPU twin rows, and its output equals
      `synth6j.txt` (revision 2's `synth6j.py` was never kept).
    - `synth7o.py` → `synth7o.txt`, and `synth7p.py` → `synth7p.txt`: every new row of revision 3.
    - `mut7.py` → `mut7.txt`: each new mutation below, applied to `merge3r7.py` or
      `conserve7.py`, changes its row; and the review's C7 example (`c40 lg12`). `mut7b.py` →
      `mut7b.txt`: revision 2's `e nmo pnm` did not kill its mutation; with `pnm` on 22 November it
      does, and the expected value is unchanged.
    - `prop7.py` → `prop7.txt`: the property run, with the same numbers as `prop6.txt`.
    - `weight7.py` → `weight7.txt`: a rough size of the claims a feed would carry (R26).
  - **Prototypes** (revision 2), in `.scratch/plan3/proto/`:
    - `merge3r6.py`: the reference merge, with Tasks 2–6 in one module. Its `OPTS` switch single
      corrections off.
      - It is built from `merge3r3.py` (revision 1) in three steps, each by exact-string edits:
        `build_r4.py`, `build_r5.py` and `build_r6.py`.
      - With revision 2's switches (`g01_…` to `g07_…`) off, it gives `merge3r3.py`'s fixture
        result (`check25.py`).
      - `merge3r3.py` and earlier are kept for comparison.
    - `claims3.py`: builds the fixture claims into `.scratch/plan3/all.pkl`. It is the same build
      as `tests/support/fixture_claims.py`.
    - `synthlib6.py`: `mk` and the span helpers, the same as `tests/support/claims.py`, on
      `merge3r6.py`. `synthlib.py` is revision 1's.
    - `conserve6.py`: the audit of Task 6 (`audit(claims, result)`).
  - **Synthetic cases** (each script prints its own cases into `.scratch/plan3/<name>.txt`):
    - `synth6a.py`–`synth6d.py`: revision 1's cases on `merge3r6.py`. Each output diffs against
      its `synth3*.txt`, and the diff is the list of changed rows;
    - `synth6e.py`: revision 2's matching cases (G01–G03, G06, D1 and D2 in Phase D, G07);
    - `synth6f.py`: every row of Task 3's revised tables;
    - `synth6g.py`: Task 5's occurrence rows and Task 6's audit messages;
    - `synth6h.py`: the district attachment set, and a year-only postponement;
    - `synth6i.py`: the qualified-number readings of Task 2;
    - `synth6j.txt`: Task 4's IPU twin rows (its script was not kept; `synth7j.py` rebuilds it);
      `synth6k.py`: `ua l1 l2` with the labelled `ua`;
    - `synth6l.py`: C7 with an attached claim (`g1 h r2`), and its mutant;
    - `synth6m.py`: two provisional claims on one contest (`e o pe22 psy`), and its mutant.
  - **The property run:** `prop6.py` (seed 20261019, 400 examples, with the payload guard) →
    `prop6.txt`.
  - **The fixture run:**
    - `report4_r6.py` → `.scratch/plan3/r6_report.txt`, every card;
    - `facts4_r6.py`, `window4_r6.py` and `facts6.py`: the end-to-end numbers (→ `r6_*.txt`);
    - `alt6.py` → `alt6.txt`: each review group's rules switched off;
    - `check6_r6.py` to `check13_r6.py`: revision 1's checks on `merge3r6.py` (→ `r6_check*.txt`;
      each diffs against its `r3_check*.txt`);
    - `check18.py`–`check24.py`: the review's measurements. `check20.py` covers the qualified
      numbers on the 77 numbered labels, `check23.py` observations in C7's attached check, and
      `check24.py` the 19 links P81 removes.
    - Revision 1's scripts (`report4.py`, `facts4.py`, `alt4.py`, `check5.py` to `check13.py`,
      `conserve3.py`, `prop3.py`) are kept.
  - **How to run them:** the fixture scripts run from the worktree root, as
    `PYTHONPATH=. PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 .venv/Scripts/python.exe .scratch/plan3/proto/<script>`.
    So do the `check*` scripts; `check7_r6.py` to `check10_r6.py` need `PYTHONPATH=.:.scratch/plan3/proto`.
    The `synth*` and `prop*` scripts run from `.scratch/plan3/proto`, with `PYTHONPATH=../../..`
    and `../../../.venv/Scripts/python.exe`.
  - **Where the prototype differs from this plan, the plan wins.** None of the differences changes
    a measured value:
    - The prototype keeps intermediate ids and remaps them at the end. The plan computes
      `child_id` from the final claims.
    - The prototype has no `umbrella` evidence rank (P69). No input has it.
    - `merge3r3.py` did not exclude observations from the status (P75); `merge3r6.py` does.
    - `merge3r6.py` does not compute `occurrence_confirmed`; `synth6g.py` computes revision 2's
      rule beside it. `merge3r7.py`'s helper `occurrence_confirmed(k)` is Task 5's rule (the merge
      itself does not use it). On the fixture it gives 197, as in revisions 1 and 2.
    - `merge3r7.py`'s `legacy_status_r6` tests a rescheduling on its own claimers, not through
      `rescheduling()`. The two sets are the same: the non-observation `postponed` claims.
    - `conserve7.py` takes a child's joined claims by their disposition kind alone. The plan also
      requires the disposition to target that child. They differ only for a misplaced claim, which
      the placement check reports anyway.
    - `conserve7.py`'s coverage check calls `umbrella_fits` on the prototype's contests. The plan's
      audit calls `umbrella_covers` on a child's joined claims, member claims and span, which are
      the same values.
    - `conserve6.py`'s attached-date check also covers attached observations. The plan leaves
      them out (P79: observations are checked for place only). An observation attaches only
      when its date is compatible with every member, so no output differs.
    - Its `rescheduled_from` lists every previous date of the identity claims. The plan lists
      them only when the status is a rescheduling. No case differs: the fixture has no previous
      date on a dated claim, and every synthetic one is a rescheduling.
    - Its C7 candidate check compares the umbrella with every attached claim, observations
      included. The plan leaves observations out. `check23.py` measured the difference: the
      fixture output is identical.
    - Its Phase B checks a contest's proposals twice: by the set of stated rounds and levels, then
      pairwise. The pairwise check (P82) marks the same claims.
    - The prototype's rescheduling hint and its old-date step pass `span.start.year` as
      `default_year`. The plan uses `span.year`, which is the same for dated claims, and also
      defined for year-only claims.
    - The prototype matches observations before the sessions, and keeps a dissolved session
      contest in candidate lists and possible matches. It sends a dissolved session's year-only
      claims to the umbrella list. The plan matches observations after the sessions, removes
      dissolved contests everywhere, and sends their year-only claims to the undated pool. The
      fixture has no `referendum_question` claim, so no session is ever dissolved there.
    - The prototype sorts cards by their key; the plan sorts them by `(span.start, place_id,
      group_id)`. The ids do not change.
    - The prototype picks the label claim from a pool that relies on the `aggregate` flag alone,
      and its identity fields include observations. The plan leaves observations out of both.
      `check10.py` measured the difference on the fixture: no child's label claim or jurisdiction
      changes, and no observation is in an aggregate child.
  - **Prototypes confirm the values; the rules define them.** Each expected value in a test table
    follows from its input and the rule named next to it. If a value cannot be explained that way,
    stop and report it, even when the prototype agrees.

  The prototypes are measurement tools, not code to copy. When a count differs, diff your
  contests against `r6_report.txt` (still the reference: revision 3 changes no fixture value) to
  find the rule that differs, then stop and report. Never change the expected value to match.
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
- **Mutations:** one per new test, in `.scratch/mutations/plan3-task-<N>.json`, in the format of
  `.scratch/mutate.py`.
  - Stage the task's files with `git add` first, and run with `PYTHONDONTWRITEBYTECODE=1`.
  - Choose mutations that fail fast. A loop that runs into `MUTATE_TIMEOUT_S` is a timeout, not a
    kill.
- **Handover:** after every task, record the commit, the Review record rows it verified and the
  next task in two files:
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-plan3-sdd-ledger.md` (new);
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-RESUME.md`.
- **Hook:** the Desktop PostToolUse hook runs `ruff check --fix` on each edited `.py`. Check
  `git diff --stat` for unrelated rewrites.
- **Runtime:** building the fixture claims takes about 2.4 s, and the fixture merge about 0.2 s.
  `fixture_claims()` is cached per test session.

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `elections_calendar/model.py`, `tests/unit/test_model.py` | the merge's output records; `tuple[X, ...]` in `_conforms` | 1 |
| `elections_calendar/merge/__init__.py` | the package; `merge()` (Task 6) | 2, 6 |
| `elections_calendar/merge/identity.py`, `tests/merge/test_identity.py` | priority, roles, qualified numbers, compatibility, rule F, ids | 2 |
| `importlinter.ini` | `(merge)` → `merge` | 2 |
| `tests/support/claims.py` | `mk`, span helpers, `NOW`, the `OBS`/`UMB`/`RENEW` presets; Task 4's presets and `list_order` (Task 6) | 2, 6 |
| `tests/support/fixture_claims.py`, `tests/merge/test_fixture_merge.py` | the nine adapters' claims; the end-to-end tests (Task 7) | 2, 7 |
| `elections_calendar/merge/select.py`, `tests/merge/test_select.py` | selection, staleness, legacy status | 3 |
| `elections_calendar/merge/match.py`, `tests/merge/test_match.py` | Phases A–D, umbrellas, aggregates, possible matches, undated groups | 4 |
| `elections_calendar/merge/cards.py`, `tests/merge/test_cards.py` | children, cards, listings, attention items, dispositions | 5 |
| `elections_calendar/merge/conservation.py`, `tests/merge/test_conservation.py`, `tests/merge/test_merge.py` | the audit; `merge()`; determinism | 6 |

## Tasks

### Task 1: The merge's output records (`model.py`)

**Files:**
- Modify: `elections_calendar/model.py`
- Test: `tests/unit/test_model.py`

**Interfaces:**
- Consumes: `_check_fields`, `_conforms`, `RecordError`, `Claim`, `DateSpan`, and the Literals
  `Level`, `JurisdictionKind`, `OfficeClass`, `Kind`, `DateMeaning`, `DateStatus`, `Relevance`.
- Produces, all in `model.py`:
  - **`_conforms(value, tuple[X, ...])`:** True when `value` is a `tuple` and every element
    conforms to `X`. Any other tuple hint (`tuple[int, str]`) still raises
    `TypeError("no runtime check for …")`, as today.
  - **Constants:** `MAX_TYPE = 200` and `MAX_ATTENTION_TEXT = 300`.
  - **Literals and records.** Each record is `@dataclass(frozen=True, slots=True)`, and its
    `__post_init__` calls `_check_fields(self)` and then its rules (below). There is no
    `to_dict` or `from_dict`, because Plan 4 serialises (R17).

```python
RejectedReason = Literal["observation", "year_only", "lower_evidence", "old_date", "not_covering",
                         "less_precise", "less_certain", "stale", "lower_priority", "provisional"]
                                                                       # old_date: R2-01
LegacyStatus = Literal["Upcoming", "Held", "Postponed", "Cancelled", "Disputed", "Unknown"]
DispositionKind = Literal["anchor_member", "attached", "provisional", "umbrella_link",
                          "standalone", "undated", "attention"]
AttentionKind = Literal["unparsed_unit", "partial_unit", "undated_listing",
                        "unresolved_evidence", "provisional_change", "disappeared_unit"]
ProvisionalDate = Literal["moved", "less_precise"]          # P74, D3

class ChildSource:      # one of a child's claims (spec §5.3 `sources`)
    claim: Claim
    selected: bool
    rejected_reason: RejectedReason | None

class BibEntry:         # one bibliography entry (spec §5.4)
    source: str
    link: str

class Child:            # one contest (spec §5.3)
    child_id: str
    place_id: str
    country: str
    country_code: str | None
    jurisdiction: str | None
    jurisdiction_kind: JurisdictionKind
    level: Level
    institution: str | None
    office_class: OfficeClass
    office_label: str
    kind: Kind
    round: int | None
    indirect: bool
    aggregate: bool     # an aggregate grouping (§10.4), never a specific contest
    span: DateSpan
    date_meaning: DateMeaning
    date_status: DateStatus
    status: LegacyStatus
    occurrence_confirmed: bool
    status_conflict: bool
    date_conflict: bool
    unverified: bool
    ambiguous: bool
    rescheduled_from: tuple[str, ...]     # D2: the old dates of a rescheduling, as the sources wrote them
    provisional_date: ProvisionalDate | None   # D3: how a provisional claim changes the date
    possible_matches: tuple[str, ...]
    sources: tuple[ChildSource, ...]

class Card:             # spec §5.4
    group_id: str
    place_id: str
    country: str
    country_code: str | None
    level: Level
    span: DateSpan
    date_meaning: DateMeaning
    date_status: DateStatus
    status: LegacyStatus
    type: str
    children: tuple[Child, ...]
    sources: tuple[BibEntry, ...]
    umbrella_sources: tuple[BibEntry, ...]
    umbrellas: tuple[Claim, ...]      # the umbrella claims linked to any of this card's children

class UndatedListing:   # spec §5.5
    undated_id: str
    place_id: str
    country: str
    office_label: str
    year: int
    claims: tuple[Claim, ...]
    sources: tuple[BibEntry, ...]
    possible_matches: tuple[str, ...]

class AttentionItem:    # spec §5.5
    item_id: str
    kind: AttentionKind
    source: str
    link: str
    snapshot_id: str | None
    relevance: Relevance
    text: str
    reason: str
    possible_matches: tuple[str, ...]
    merge_ids: tuple[str, ...]
    undated_id: str | None

class Disposition:      # spec §10.8
    merge_id: str
    kind: DispositionKind
    targets: tuple[str, ...]          # child ids (umbrella_link: every child it fits), a listing or an item

class MergeResult:
    cards: tuple[Card, ...]
    undated: tuple[UndatedListing, ...]
    attention: tuple[AttentionItem, ...]
    dispositions: tuple[Disposition, ...]
```

**Rules.** Each broken rule raises `RecordError` with the message shown. `<Name>` is the record's
class name.

| Record | Rule | Message |
|---|---|---|
| `ChildSource` | `selected` is True exactly when `rejected_reason` is None | `"selected and rejected_reason disagree"` |
| `Child`, `Card`, `UndatedListing`, `AttentionItem` | the id (`child_id`, `group_id`, `undated_id`, `item_id`) matches `[0-9a-f]{12}` | `"<Name>.<field> <value!r> is not 12 hex characters"` |
| `Child`, `Card` | `span.precision` is not `year` | `"<Name>: span is never year precision"` |
| `Child` | exactly one source has `selected` True | `"Child: exactly one source is selected"` |
| `Child`, `UndatedListing`, `AttentionItem` | `possible_matches` is sorted and has no repeats | `"<Name>.possible_matches must be sorted and unique"` |
| `Child` | `possible_matches` does not hold `child_id` | `"Child.possible_matches names the child itself"` |
| `Child` | `rescheduled_from` is sorted and has no repeats | `"Child.rescheduled_from must be sorted and unique"` |
| `Child` | `provisional_date` is None unless some source has `rejected_reason == "provisional"` | `"Child: provisional_date needs a provisional source"` |
| `Card` | `children` is not empty | `"Card: no children"` |
| `Card` | `1 <= len(type) <= MAX_TYPE` | `"Card.type is 1 to 200 characters"` |
| `UndatedListing` | `claims` is not empty, and each claim has year precision with `span.year == year` | `"UndatedListing: every claim is year-only, of its year"` |
| `AttentionItem` | `len(text) <= MAX_ATTENTION_TEXT` | `"AttentionItem.text is over 300 characters"` |
| `AttentionItem` | `undated_id` is set exactly when `kind == "undated_listing"` | `"AttentionItem: undated_id goes with kind undated_listing"` |
| `AttentionItem` | `merge_ids` is not empty, sorted and has no repeats | `"AttentionItem.merge_ids must be sorted, unique and non-empty"` |
| `Disposition` | `targets` is not empty, sorted and has no repeats | `"Disposition.targets must be sorted, unique and non-empty"` |
| `Disposition` | exactly one target unless `kind == "umbrella_link"` | `"Disposition: <kind> has exactly one target"` |

- [ ] **Step 1: Write the failing tests** in `tests/unit/test_model.py`. Build claims with the
  existing `tests.support.pages.claim` helper (Task 2's `mk` does not exist yet).
  - **`test_tuple_hints`** (parametrized, on `_conforms`):

    | value, hint | result |
    |---|---|
    | `()`, `tuple[str, ...]` | True |
    | `("a", "b")`, `tuple[str, ...]` | True |
    | `["a"]`, `tuple[str, ...]` | False |
    | `("a", 1)`, `tuple[str, ...]` | False |
    | `(True,)`, `tuple[int, ...]` | False (a bool is not an int) |
    | `(1, "a")`, `tuple[int, str]` | raises `TypeError` |
  - **`test_merge_records_accept_valid_values`:** one valid record of each of the eight classes
    builds. `MergeResult` holds one of each of the others. The valid `Child` has
    `rescheduled_from=("1 November 2026",)`, and a second one has `provisional_date="moved"` with a
    provisional source.
  - **`test_merge_record_rules`** (parametrized): one row per rule in the table above. Each row
    builds the valid record with one field changed, and asserts `RecordError` with the message.
    Also: a `Card` with a 200-character type builds, and one with 201 does not.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/unit/test_model.py -q`. Expected:
  FAIL (the names do not exist).
- [ ] **Step 3: Implement** the Literals, the constants, the eight records and the tuple arm of
  `_conforms`.
- [ ] **Step 4: Run** the full suite. Expected: PASS, with every existing test unchanged.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(model): merge output records (children, cards, listings, attention items, dispositions)`.

  Mutations, one each:
  - `_conforms` accepts a list for `tuple[X, ...]`;
  - `_conforms` skips the element check;
  - drop the `ChildSource` rule;
  - `Child` accepts two selected sources;
  - `Child` accepts its own id in `possible_matches`;
  - `Child` accepts an unsorted `rescheduled_from`;
  - `Child` accepts a `provisional_date` with no provisional source;
  - the `Card` type limit becomes 201;
  - `AttentionItem` accepts an `undated_id` with another kind;
  - `Disposition` accepts two targets for `attached`.

---

### Task 2: Identity, test claims and the merge layer (P66, P67 role, P70, P78 labels, P80, R7)

**Files:**
- Create:
  - `elections_calendar/merge/__init__.py` (the package docstring: spec §10, the module list;
    `merge` arrives in Task 6);
  - `elections_calendar/merge/identity.py`;
  - `tests/merge/__init__.py`, `tests/merge/test_identity.py`, `tests/merge/test_fixture_merge.py`;
  - `tests/support/claims.py`, `tests/support/fixture_claims.py`.
- Modify: `importlinter.ini`. In the layers contract, `(merge)` becomes `merge`.

**Interfaces:**
- Consumes: `Claim`, `DateSpan`, `text.norm_name`; for the fixtures, the nine adapters,
  `sources.base.Registries`, `RawPages`, `ParseResult`, `fetch.Deadline`, `window.window_for`,
  `ledger.check`, `ndi.request`, `eisa.URL`, `eisa.AJAX`, and `tests.support.fixtures.fixture`,
  `tests.support.pages.Served`, `raw_pages`, `result`.
- Produces, in `elections_calendar/merge/identity.py`:

```python
class MergeError(ValueError): ...   # the merge cannot give a trustworthy result; publication stops

PRIORITY: tuple[str, ...] = ("electionguide", "osce", "wikipedia:national", "wikipedia:local",
                             "ndi", "aweb", "eisa", "ipu", "carter", "eeas")      # §10.5 step 6
SOURCE_ORDER: tuple[str, ...] = ("electionguide", "osce", "wikipedia", "ndi", "aweb", "eisa",
                                 "ipu", "carter", "eeas")                          # bibliographies
REFERENDA: frozenset[str] = frozenset({"referendum_day", "referendum_question"})
CHAMBERS: frozenset[str] = frozenset({"lower_house", "upper_house", "legislature"})
Role = Literal["provisional", "anchor", "weak", "umbrella"]

QUALIFIERS: tuple[str, ...] = ("district", "ward", "constituency", "seat", "phase", "series",
                               "division", "precinct", "circuit", "zone", "position", "place")

def family(claim: Claim) -> str
def claim_order(claim: Claim) -> tuple[int, bool, str, str, str]
def role(claim: Claim) -> Role
def qualified_numbers(label: str) -> dict[str, frozenset[int]]          # P80
def identity_compatible(a: Claim, b: Claim, *, relax_jurisdiction: bool = False,
                        ignore_kind: bool = False, ignore_institution: bool = False) -> bool
def same_source_compatible(a: Claim, b: Claim) -> bool
def years_of(span: DateSpan) -> frozenset[int]
def dates_compatible(a: Claim, b: Claim) -> bool
def joinable(a: Claim, b: Claim) -> bool
def gap_days(s: DateSpan, t: DateSpan) -> int
def short_id(parts: Iterable[str]) -> str
```

  - In `tests/support/claims.py`:

```python
NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
def day(y: int, m: int, d: int) -> DateSpan                       # DateSpan.day
def days(y1: int, m1: int, d1: int, y2: int, m2: int, d2: int) -> DateSpan
def month(y: int, m: int) -> DateSpan
def months(y1: int, m1: int, y2: int, m2: int) -> DateSpan
def year(y: int) -> DateSpan                                      # DateSpan.of_year
def mk(unit_id: str, n: int = 0, **fields: Any) -> Claim
OBS: dict[str, Any]; UMB: dict[str, Any]; RENEW: dict[str, Any]
```

  - In `tests/support/fixture_claims.py`:

```python
FIXTURE_NOW = datetime(2026, 10, 19, tzinfo=UTC)
def fixture_results() -> dict[str, tuple[RawPages, ParseResult]]   # functools.cache
def fixture_claims() -> tuple[Claim, ...]                          # functools.cache
def fixture_claim(claim_id: str) -> Claim
```

**Rules:**
- **`family`:** for a Wikipedia claim, `"wikipedia:national"` when `unit_id` starts with
  `"wikipedia:national-"`, otherwise `"wikipedia:local"`. For any other source, `claim.source`. A
  family not in `PRIORITY` raises `MergeError(f"unknown source: {claim.source}")`.
- **`claim_order`:** `(PRIORITY.index(family), source_event_id is None, source_event_id or "",
  unit_id, merge_id)`. Event ids compare as strings.
- **`role`:** the first rule that applies wins (§10.2, with P66 and P67):
  1. `provisional` → `"provisional"`;
  2. `evidence_kind == "observation"` → `"weak"` (P67);
  3. `office_class == "general"` or `aggregate` → `"umbrella"`;
  4. `"anchor"` when all of these hold:
     - `evidence_kind == "calendar"`;
     - `span.precision == "day"`;
     - `date_meaning == "voting_period"`;
     - `institution is not None`, or `kind in REFERENDA`;
     - `jurisdiction_kind` is `nationwide`, `named` or `subdivision` (P66);
  5. otherwise `"weak"`.
- **`identity_compatible`** (§10.1, P78) requires all of these:
  - **place:** equal `place_id`;
  - **level:** equal, or either is `unknown`;
  - **institution** (skipped with `ignore_institution`): both set → equal; otherwise equal
    `office_class`;
  - **jurisdiction:** either is `unknown` → `relax_jurisdiction`. Otherwise, either is
    `nationwide` → both are. Otherwise `norm_name(a.jurisdiction or "") == norm_name(b.jurisdiction or "")`;
  - **round:** equal, or either is None;
  - **kind** (skipped with `ignore_kind`): equal, and for `referendum_question`, equal
    `norm_name(office_label)` (P78);
  - **qualified numbers** (P80, never skipped): for every qualifier in both
    `qualified_numbers(a.office_label)` and `qualified_numbers(b.office_label)`, the two sets are
    equal.
- **`qualified_numbers`** (P80): over `t = norm_name(label)`, with `Q` the alternation of
  `QUALIFIERS`, collect the matches of two patterns:
  - `\b(Q)\s+(?:no\s+|number\s+)?([0-9]+)(?![0-9a-z])`: "district 12", "district no 12";
  - `(?<![0-9a-z])([0-9]+)(?:st|nd|rd|th)\s+(?:[a-z]+\s+){0,4}?(Q)\b`: "12th state house
    district", lazily, so the ordinal binds to the nearest qualifier.

  Return each qualifier found mapped to the frozenset of its numbers. Qualifiers with no number are
  absent. A bare number ("150 seats", "2026", "14 by-elections") gives nothing.
- **`same_source_compatible`** (rule F, P70): `family(a) != family(b)`, or
  `norm_name(a.office_label) == norm_name(b.office_label)`.
- **`years_of`:** year precision → `{span.year}`; otherwise every year from `start.year` to
  `end.year`.
- **`dates_compatible`:** when either claim has year precision, `years_of` overlap; otherwise the
  intervals overlap (`a.start <= b.end and b.start <= a.end`). There is no tolerance (§10.2).
- **`joinable`** = `identity_compatible(a, b)` and `same_source_compatible(a, b)` and
  `dates_compatible(a, b)`.
- **`gap_days`:** 0 when the dated spans overlap; otherwise the days from the earlier one's end to
  the later one's start. A year span raises `ValueError("gap_days needs dated spans")`.
- **`short_id`:** `hashlib.sha1("\n".join(sorted(parts)).encode("utf-8")).hexdigest()[:12]`.
- **`mk`:** `source` is the `unit_id` before its first `":"`; `claim_id` is `f"{unit_id}#{n}"`;
  `span` defaults to `day(2026, 11, 15)`. Every other field comes from `fields`, then from `BASE`:

```python
BASE = dict(link="https://example.test/e", source_event_id=None, place_raw="Sweden",
            place_id="iso:SE", jurisdiction=None, jurisdiction_kind="nationwide", level="national",
            institution="iso:SE/riksdag", office_class="legislature", office_label="Riksdag",
            aggregate=False, kind="candidate_election", round=None, date_meaning="voting_period",
            date_status="unknown", date_text="15 November 2026", status_claim=None,
            previous_date_text=None, evidence_kind="calendar", indirect=False)
OBS = dict(evidence_kind="observation", office_class="general", aggregate=True, kind="aggregate",
           institution=None, level="unknown", date_meaning="unknown",
           office_label="Election observation mission")
UMB = dict(office_class="general", aggregate=True, kind="aggregate", institution=None,
           office_label="General elections")
RENEW = dict(evidence_kind="expected_renewal", date_status="tentative",
             date_meaning="expected_window")
```

- **`fixture_results`** parses each adapter on its own capture day, with `Registries.load()`. Each
  entry is `(raw pages, parse result)`:
  - **ElectionGuide and Wikipedia:** window `window_for(2026-10-16T00:00Z)`. Each request from the
    adapter's `requests(window)` is served from `fixture(source, f"{key}.html")` (ElectionGuide)
    or `fixture(source, f"{key}.json")` with content type `application/json; charset=utf-8`
    (Wikipedia), through `raw_pages` and `result`.
  - **OSCE, IPU, A-WEB, Carter, EEAS:** window 2026-10-18. The first request is served from
    `fixture(source, name, "2026-10-18")`. The names are `elections.html`, `elections.html`,
    `calendar.html`, `observed.html` and `missions.html`.
  - **NDI:** window 2026-10-19,
    `Ndi().fetch(window, Served({request(n).url: fixture("ndi", f"p{n}.html", "2026-10-19") for n in range(5)}), Deadline.after(60))`.
  - **EISA:** window 2026-10-19. `Eisa().fetch` serves `URL` → `calendar.html`,
    `AJAX.format(table_id="38978")` → `y2026.json` and `AJAX.format(table_id="34700")` →
    `y2025.json`, all of day `2026-10-19`.

  `fixture_claims()` concatenates the claims in the order electionguide, wikipedia, osce, ipu, aweb,
  carter, eeas, ndi, eisa. `fixture_claim(claim_id)` returns the one claim with that id (a
  `KeyError` names a missing id). The recipe is `.scratch/plan3/proto/claims3.py`.

- [ ] **Step 1: Write the failing tests.**
  - **`test_identity.py`:**
    - **`test_family_and_claim_order`:**
      - `family`: Wikipedia `wikipedia:national-2026@rev1/…` → `"wikipedia:national"`;
        `wikipedia:local-2026@rev2/…` → `"wikipedia:local"`; `ndi:p0/upcoming-c1` → `"ndi"`.
      - Sorted by `claim_order`, the claims `mk("eeas:missions/r1c1")`, `mk("ipu:elections/r5")`,
        `mk("ndi:p0/upcoming-c1")`, `mk("wikipedia:local-2026@rev2/November/li[1]")`,
        `mk("wikipedia:national-2026@rev1/November/li[1]")` and `mk("electionguide:upcoming/r1")`
        give the families electionguide, wikipedia:national, wikipedia:local, ndi, ipu, eeas.
      - `mk("electionguide:upcoming/r3", source_event_id="electionguide:9")`,
        `mk("electionguide:upcoming/r2", source_event_id="electionguide:10")` and
        `mk("electionguide:upcoming/r1")` sort r2, r3, r1. Event ids compare as strings, and a
        missing one comes last.
      - `PRIORITY` and `SOURCE_ORDER` equal the tuples above.
    - **`test_unknown_source_is_a_merge_error`:** `family(mk("xyz:p/r1"))` raises
      `MergeError("unknown source: xyz")`.
    - **`test_roles`** (parametrized; each row lists the changes to `mk("electionguide:upcoming/r1")`):

      | changes | role |
      |---|---|
      | none | anchor |
      | `provisional=True`, `**UMB` | provisional |
      | `**OBS` | weak (P67, before the umbrella rule) |
      | `**UMB` | umbrella |
      | `institution=None`, `aggregate=True` (a legislature aggregate) | umbrella |
      | `jurisdiction="Bahia"`, `jurisdiction_kind="subdivision"` | anchor (P66) |
      | `jurisdiction="Lima"`, `jurisdiction_kind="named"` | anchor |
      | `jurisdiction_kind="unknown"` | weak |
      | `span=month(2026, 11)` | weak |
      | `span=year(2026)` | weak |
      | `date_meaning="unknown"` | weak |
      | `**RENEW` | weak |
      | `institution=None`, `office_class="mayor"` | weak |
      | `institution=None`, `office_class="referendum"`, `kind="referendum_day"` | anchor |
      | `round=2` | anchor |
    - **`test_identity_compatible`** (parametrized). `a` is `mk("electionguide:upcoming/r1", …)`
      and `b` is `mk("osce:elections/r1", …)`, with the changes shown:

      | a changes | b changes | keyword | result |
      |---|---|---|---|
      | — | — | — | True |
      | — | `place_id="iso:NO"` | — | False |
      | — | `level="subnational"` | — | False |
      | — | `level="unknown"` | — | True |
      | — | `institution="iso:SE/other"` | — | False |
      | — | `institution=None` | — | True (same office class) |
      | — | `institution=None`, `office_class="head_of_state"` | — | False |
      | — | `jurisdiction="Lima"`, named | — | False (nationwide matches only nationwide) |
      | `jurisdiction="Lima"`, named | `jurisdiction="lima "`, subdivision | — | True |
      | `jurisdiction="Lima"`, named | `jurisdiction="Cusco"`, named | — | False |
      | — | `jurisdiction_kind="unknown"` | — | False (`unknown` never agrees) |
      | — | `jurisdiction_kind="unknown"` | `relax_jurisdiction=True` | True |
      | `jurisdiction="Bahia"`, subdivision, `level="unknown"` | — | `relax_jurisdiction=True` | False (R7) |
      | `round=1` | `round=2` | — | False |
      | `round=1` | — | — | True |
      | — | `kind="by_election"` | — | False |
      | — | `kind="by_election"` | `ignore_kind=True` | True |
      | — | `institution="iso:SE/other"` | `ignore_institution=True` | True |
      | Q: `institution=None`, `office_class="referendum"`, `kind="referendum_question"`, `office_label="Question A"` | Q with `office_label="question  a"` | — | True (P78) |
      | Q, "Question A" | Q, "Question B" | — | False |
      | Q, "Question A" | Q with `kind="referendum_day"`, `office_label="Referendum"` | `ignore_kind=True` | True |
      | `office_label="State House District 12 special election"` | `office_label="12th State House District"` | — | True (P80) |
      | `office_label="State House District 12 special election"` | `office_label="Louisiana State House District 40 Special Election"` | — | False (P80: across families too) |
      | `office_label="District 12, Phase 2"` | `office_label="District 2, Phase 12"` | — | False |
      | `office_label="Riksdag (150 seats)"` | `office_label="Riksdag (349 seats)"` | — | True (a seat total is not identity) |
      | `office_label="District 12"` | — ("Riksdag") | — | True (a number on one side only) |
      | `office_label="District 12"` | `office_label="District 40"` | `ignore_kind=True, ignore_institution=True` | False (never skipped) |
    - **`test_qualified_numbers`** (P80):

      | label | result |
      |---|---|
      | "State House District 12 special election" | `{"district": {12}}` |
      | "12th State House District" | `{"district": {12}}` |
      | "District No. 12" | `{"district": {12}}` |
      | "District 12, Phase 2" | `{"district": {12}, "phase": {2}}` |
      | "District 2, Phase 12" | `{"district": {2}, "phase": {12}}` |
      | "12th District, Phase 2" | `{"district": {12}, "phase": {2}}` (the ordinal binds to the nearest qualifier) |
      | "Parliament (2nd phase)" | `{"phase": {2}}` |
      | "Senate (series 2)" | `{"series": {2}}` |
      | "5th Ward", "Ward 5 by-election" | `{"ward": {5}}` |
      | "18th congressional district, special election (2nd round)" | `{"district": {18}}` (a round is not a qualifier) |
      | "150 seats", "National Assembly, 14 by-elections", "2026 General Election", "House of Representatives Carroll 7 district, special election" | `{}` |
    - **`test_same_source_compatible`** (P70):

      | a | b | result |
      |---|---|---|
      | `mk("wikipedia:local-2026@rev2/November/li[9]/li[1]", office_label="State House District 12 special election")` | `mk("wikipedia:local-2026@rev2/November/li[9]/li[2]", office_label="State House District 40 special election")` | False |
      | the same a | b with `office_label="state house district 12 special  election"` | True |
      | `mk("wikipedia:national-2026@rev1/November/li[1]")` ("Riksdag") | `mk("wikipedia:local-2026@rev2/November/li[1]", office_label="Swedish general election")` | True (two families) |
      | `mk("electionguide:upcoming/r1")` | `mk("osce:elections/r1", office_label="Parliamentary Elections")` | True |
      | `mk("ndi:p0/upcoming-c1", office_label="2026 Côte d'Ivoire Presidential Election")` | `mk("ndi:p0/upcoming-c2", office_label="2026 Ivory Coast Presidential Election")` | False |
    - **`test_dates_compatible`** (parametrized, the spans of two default claims):

      | a span | b span | result |
      |---|---|---|
      | `day(2026, 11, 15)` | `day(2026, 11, 15)` | True |
      | `day(2026, 11, 15)` | `day(2026, 11, 16)` | False (no tolerance) |
      | `days(2026, 11, 14, 2026, 11, 15)` | `day(2026, 11, 15)` | True |
      | `month(2026, 11)` | `day(2026, 11, 15)` | True |
      | `month(2026, 10)` | `day(2026, 11, 15)` | False |
      | `year(2026)` | `day(2026, 11, 15)` | True |
      | `year(2026)` | `year(2027)` | False |
      | `year(2027)` | `months(2026, 12, 2027, 1)` | True |
    - **`test_gap_days_years_and_short_id`:**
      - `gap_days(day(2026, 11, 15), day(2026, 11, 18)) == 3`, and 3 the other way round;
        overlapping spans give 0; `month(2026, 12)` and `month(2027, 1)` give 1; a year span
        raises `ValueError("gap_days needs dated spans")`.
      - `years_of(year(2026)) == {2026}`; `years_of(months(2026, 12, 2027, 1)) == {2026, 2027}`.
      - `short_id(["b", "a"]) == short_id(["a", "b"]) == "fcd127ffa101"`;
        `short_id(["served/electionguide:past/r4#0"]) == "6d12862ffe3c"`.
    - **`test_subdivision_claim_never_joins_a_nationwide_contest`** (R7, extended by Plan 2c).
      Take each of these fixture claims, paired with an institution:

      | claim | institution |
      |---|---|
      | `osce:elections/r52#0` | `iso:BA/presidency` |
      | `aweb:calendar/r5#0` | `iso:PK/national-assembly` |
      | `ndi:p0/past-c6#0` | `iso:PH/house-of-representatives` |

      For each claim `c`:
      - `c.jurisdiction_kind == "subdivision"` and `c.level == "unknown"`;
      - `role(c) == "weak"`;
      - build `nat = mk("electionguide:past/r90", place_id=c.place_id, place_raw=c.place_raw,
        institution=<institution>, office_class=c.office_class, office_label="national", span=c.span)`;
      - `identity_compatible(c, nat)` is False, and so is `identity_compatible(c, nat,
        relax_jurisdiction=True)`.

      The contest-level case is in Task 4 (`test_weak_claims`).
  - **`tests/merge/test_fixture_merge.py`, `test_fixture_claims`:**
    - the claims per source are ElectionGuide 243, Wikipedia 543, OSCE 180, IPU 234, A-WEB 31,
      Carter 18, EEAS 23, NDI 38 and EISA 25, for a total of 1335;
    - `ledger.check(raw, result).ok` holds for every source;
    - the claim ids are unique;
    - `fixture_claims() is fixture_claims()` (cached).
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/merge -q`. Expected: FAIL (no
  module `elections_calendar.merge`).
- [ ] **Step 3: Implement** the package, `identity.py` and the two support modules. Change
  `(merge)` to `merge` in `importlinter.ini`.
- [ ] **Step 4: Run** the full suite, then `.venv/Scripts/lint-imports.exe --config importlinter.ini`.
  Expected: PASS, and `Contracts: 2 kept, 0 broken`.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(merge): identity, roles and the same-source rule; test claims and fixture claims`.

  Mutations, one each:
  - `role` applies the umbrella rule before the observation rule;
  - `role` does not accept `subdivision` for an anchor;
  - an `unknown` jurisdiction always agrees;
  - `nationwide` agrees with any named jurisdiction;
  - two stated rounds may differ;
  - drop the referendum-question label check;
  - identity skips the qualified numbers;
  - `qualified_numbers` reads a bare number as a district (drop the qualifier from the first
    pattern);
  - the ordinal pattern is greedy (`{0,4}` instead of `{0,4}?`);
  - `same_source_compatible` always returns True;
  - `dates_compatible` returns True whenever either claim has year precision;
  - `gap_days` returns the difference minus one;
  - `short_id` does not sort its parts;
  - `family` swaps national and local;
  - `claim_order` drops `source_event_id`;
  - `family` lets `PRIORITY.index`'s `ValueError` escape instead of raising `MergeError`;
  - `fixture_results` drops EISA's `y2025` page.

---

### Task 3: Selection and the legacy status (`select.py`; P69, P75, R5, R13; G04, G05, D1, D2; R2-01)

**Files:**
- Create: `elections_calendar/merge/select.py`
- Test: `tests/merge/test_select.py`

**Interfaces:**
- Consumes: `identity.claim_order`, `family`, `dates_compatible`; `dates.parse_date_text`;
  `model.month_end`, `RejectedReason`, `LegacyStatus`, `StatusClaim`.
- Produces:

```python
STALE_AFTER = timedelta(days=7)
def is_stale(claim: Claim, now: datetime) -> bool
def rescheduling(direct: Sequence[Claim]) -> tuple[Claim, ...]      # D2, R2-01

@dataclass(frozen=True, slots=True)
class Selection:
    claim: Claim | None                               # None: no eligible claim
    reasons: Mapping[str, RejectedReason | None]      # every merge_id of `direct`; None = selected
    date_conflict: bool
    unverified: bool

def select(direct: Sequence[Claim], now: datetime) -> Selection

@dataclass(frozen=True, slots=True)
class StatusResult:
    status: LegacyStatus
    resolved: StatusClaim | None                      # the resolved postponed/cancelled/disputed
    conflict: bool
    rescheduled: bool                                 # D2: a postponement that follows its new date

def legacy_status(direct: Sequence[Claim], span: DateSpan, today: date) -> StatusResult
```

**Rules:**
- **`is_stale`** (P69): `claim.fallback` and (`fetched_at` is None, or `now - fetched_at >
  STALE_AFTER`). Exactly 7 days is fresh.
- **`rescheduling`** (D2): the claims of `direct` that are not observations and have
  `status_claim="postponed"`, sorted by `merge_id`, when there is at least one and every one has a
  `previous_date_text` and a span that is not year precision. Otherwise `()`.
- **`select`** (§10.5 with P67–P69). Each step keeps the claims with the best key, and gives the
  others that step's reason:
  1. **Eligibility.**
     - An observation → `"observation"` (P67).
     - A year-precision claim → `"year_only"` (P68).
     - The rest are the eligible claims E.
  2. **Tier.**
     - The tier ranks are `calendar` and `umbrella` 0, `expected_renewal` 1.
     - The pool is E's claims of the best tier present. The others → `"lower_evidence"`.
     - With an empty pool, the selection has `claim=None` and both flags False.
  3. **Old dates** (R2-01). R is the pool's claims that are in `rescheduling(direct)`. When R is
     not empty, every other pool claim `c` → `"old_date"` when either holds:
     - `c` is not `dates_compatible` with some claim of R;
     - for some `r` in R, and some span `o` of
       `parse_date_text(r.previous_date_text, default_year=r.span.year).spans` that is not year
       precision: `c.span` lies inside `o`, and `o` lies inside `r.span` ("x lies inside y" is
       `y.start <= x.start and x.end <= y.end`).

     The pool loses those claims. The second test catches the old day when the new date is the
     month that holds it ("postponed from 15 November to November 2026"). It needs the old date
     inside the new one, so a postponement from "November 2026" to 29 November keeps a claim for
     29 November: that is the new date, not the old one.
  4. **Coverage.**
     - The covering claims are the pool's claims of day precision and `date_meaning="voting_period"`
       whose interval contains the interval of every day-precision claim in the pool.
     - When there is at least one, every other pool claim (of any precision) → `"not_covering"`,
       and the pool is the covering claims.
  5. **Precision:** day before month → `"less_precise"`.
  6. **`date_status`:** confirmed, then tentative, then unknown → `"less_certain"`.
  7. **Freshness:** a fresh claim before a stale one → `"stale"`.
  8. **Priority:** the first in `claim_order` is selected (reason None). The rest →
     `"lower_priority"`.

  **The flags** (P69, G05) look at the *support set* S: the claims of E with the winner's
  `evidence_kind`.
  - `date_conflict`: some claim is `old_date` (sources disagree on the date: one still gives the
    old one), or the winner is stale and some fresh claim in S has an interval that does not
    contain the winner's (`start <= winner.start` and `winner.end <= end` fails);
  - `unverified`: every claim in S with the winner's (`start`, `end`), `date_meaning` and
    `span.precision` is stale. The winner is one of them, so the set is never empty.
- **`legacy_status`** (§5.9 with P75, D1, D2, R2-01). Observations are left out first. `conflict`
  and `rescheduled` start False. `span` is the selected claim's span.
  - **Opposed words.** Take the claims with a `status_claim` of `cancelled`, `postponed` or
    `disputed` and `fallback` False. When two of them have different words and different
    families, `conflict` becomes True.
  - Then the first rule that applies wins:
  1. **Postponement and cancellation.** For `cancelled`, then `postponed`:
     - the claimers are the claims with that `status_claim`; with no claimers, go to the next word;
     - **a rescheduling:** when the word is `postponed` and `rescheduling(direct)` is not empty
       (every claimer has a `previous_date_text` and a span that is not year precision),
       `rescheduled` becomes True and the next word is tried. The date rules then use its new
       date: `select` has set the old-date claims aside, so `span` is the new date (R2-01);
     - **the opposing claims** are those with `evidence_kind="calendar"`, day or month precision,
       `fallback` False, and a family that is none of the claimers' families;
     - an opposing claim with `status_claim="held"` whose interval overlaps `span`
       (`start <= span.end` and `span.start <= end`) → `conflict` becomes True, and the next word
       is tried (D1, R2-01: only evidence that the vote took place on the selected date overrides
       a word);
     - otherwise, an opposing claim with `status_claim` None, or a `held` one for another date →
       `conflict` becomes True, and the word stands;
     - the word stands → `StatusResult("Cancelled" | "Postponed", word, conflict, False)`.
  2. **Disputed.** A claim with `status_claim="disputed"` and `fallback` False →
     `("Disputed", "disputed", conflict, rescheduled)`.
  3. **Day precision:** `span.end < today` → `"Held"`, otherwise `"Upcoming"`.
  4. **Month precision:**
     - `span.end` is before the 1st of today's month → `"Held"`;
     - otherwise, `span.start <= month_end(today.year, today.month)` → `"Unknown"`;
     - otherwise `"Upcoming"`.

     Rules 3 and 4 give `resolved=None`, with `conflict` and `rescheduled` as they stand.

- [ ] **Step 1: Write the failing tests** in `tests/merge/test_select.py`. Claims come from
  `tests.support.claims` (`mk` defaults: Sweden, Riksdag, day 2026-11-15, `voting_period`,
  `unknown`). `NOW` is 2026-10-19 12:00 UTC, `STALE_AT` is 2026-09-01 00:00 UTC and `FRESH_AT` is
  2026-10-18 00:00 UTC. WPn is `wikipedia:national-2026@rev1`, WPl is `wikipedia:local-2026@rev2`.
  - **`test_is_stale`:**

    | claim | stale |
    |---|---|
    | `fallback=False`, `fetched_at=STALE_AT` | False |
    | `fallback=True`, `fetched_at=None` | True |
    | `fallback=True`, `fetched_at` 2026-10-12 12:00 UTC (exactly 7 days) | False |
    | `fallback=True`, `fetched_at` 2026-10-12 11:59 UTC | True |
  - **`test_selection`** (S3-T9). The test compares the winner's `merge_id` and every reason:

    | direct | selected | the others' reasons |
    |---|---|---|
    | `osce:elections/r1` day 09-20; `WPn/September/li[3]` days 09-18–09-20 | WPn (18–20) | OSCE `not_covering` |
    | the same, in reverse order | WPn | OSCE `not_covering` |
    | OSCE r1 day 09-20; `aweb:calendar/r1` days 09-18–09-20, `date_meaning="unknown"` | OSCE | A-WEB `lower_priority` (a range that is not `voting_period` never covers) |
    | `ipu:elections/r1` `**RENEW`; `carter:observed/r1` `**OBS` month Nov; `osce:elections/r9` year 2026; `WPn/November/li[4]` | WPn | IPU `lower_evidence`, Carter `observation`, OSCE `year_only` |
    | IPU, Carter, OSCE r9 as above | IPU | Carter `observation`, OSCE `year_only` |
    | Carter and OSCE r9 as above | none (`claim is None`) | Carter `observation`, OSCE `year_only` |
    | `ndi:p0/upcoming-c2` month Nov, `tentative`, `date_meaning="unknown"`; `aweb:calendar/r2` days 11-14–11-15, `date_meaning="unknown"` | A-WEB | NDI `less_precise` (P69: precision before status) |
    | WPn li[4]; `electionguide:upcoming/r2` `tentative`; `electionguide:upcoming/r1` `confirmed` | EG r1 | WPn `less_certain`, EG r2 `less_certain` |
    | `electionguide:upcoming/r3` (event `electionguide:9`), `…/r2` (event `electionguide:10`), `…/r1` (no event) | EG r2 | r1 and r3 `lower_priority` |
    | `eeas:missions/r1c1`, `ipu:elections/r5`, `ndi:p0/upcoming-c1`, `WPl/November/li[1]`, `WPn/November/li[1]` (all `mk` defaults, so all `calendar`) | WPn li[1] | the other four `lower_priority` |
    | `osce:elections/r1` with `evidence_kind="umbrella"`; IPU `**RENEW` | OSCE | IPU `lower_evidence` (P69: `umbrella` ranks with `calendar`) |

    In every row `date_conflict` and `unverified` are False.
  - **`test_freshness`** (S3-T10, S3-T12, P69, G05):

    | direct | selected | reasons | `date_conflict`, `unverified` |
    |---|---|---|---|
    | IPU `**RENEW`, `fetched_at=FRESH_AT`; WPn li[4] `fallback=True`, `fetched_at=STALE_AT` | WPn | IPU `lower_evidence` | False, True (a renewal is not support for a polling date) |
    | WPn stale (as above); `ndi:p0/upcoming-c4` month Nov, `tentative`, `date_meaning="unknown"`, `fetched_at=FRESH_AT` | WPn | NDI `not_covering` | False, True (a containing month is missing support, not a disagreement) |
    | WPn stale; NDI c4 as above with `span=month(2026, 12)` | WPn | NDI `not_covering` | True, True |
    | WPn stale; `aweb:calendar/r1`, `date_meaning="unknown"`, `fetched_at=FRESH_AT` (the same day) | WPn | A-WEB `not_covering` | False, True (another meaning is another assertion) |
    | WPn stale; OSCE r1 `fallback=True`, `fetched_at=STALE_AT`; IPU `**RENEW` fresh | OSCE | IPU `lower_evidence`, WPn `lower_priority` | False, True |
    | IPU `**RENEW`, `fetched_at=FRESH_AT`, alone | IPU | — | False, False (a fresh renewal-only child) |
    | IPU `**RENEW`, `fallback=True`, `fetched_at=STALE_AT`, alone | IPU | — | False, True |
    | WPn `fetched_at=FRESH_AT`; EG up/r1 `confirmed`, `fallback=True`, `fetched_at=STALE_AT` | EG | WPn `less_certain` | False, False |
    | WPn stale; OSCE r1 `fetched_at=FRESH_AT` | OSCE | WPn `stale` | False, False |
    | WPn `fallback=True`, `fetched_at=None`; OSCE r1 fresh | OSCE | WPn `stale` | False, False |
    | WPn `fallback=True`, `fetched_at` 2026-10-13 00:00 UTC; OSCE r1 fresh | OSCE | WPn `lower_priority` | False, False |
    | WPn `fallback=True`, `fetched_at` 2026-10-12 12:00 UTC; OSCE r1 fresh | OSCE | WPn `lower_priority` | False, False |
    | WPn `fallback=True`, `fetched_at` 2026-10-12 11:59 UTC; OSCE r1 fresh | OSCE | WPn `stale` | False, False |
  - **`test_legacy_status_by_date`** (today 2026-10-19; `direct` is one claim with that span):

    | span | status |
    |---|---|
    | `day(2026, 10, 4)` | Held |
    | `day(2026, 10, 19)` | Upcoming |
    | `days(2026, 10, 18, 2026, 10, 20)` | Upcoming |
    | `month(2026, 10)` | Unknown |
    | `month(2026, 9)` | Held |
    | `month(2026, 11)` | Upcoming |
    | `months(2026, 9, 2026, 10)` | Unknown |

    Every row has `resolved=None`, `conflict=False` and `rescheduled=False`.
  - **`test_status_claims`** (S1-T5, S3-T11, P75, D1, R2-01; span `day(2026, 11, 15)` unless
    stated, today 2026-10-19). `canc` is `mk("osce:elections/r1", status_claim="cancelled",
    fetched_at=FRESH_AT)`, `fresh` is `mk("WPn/November/li[4]", fetched_at=FRESH_AT)`, `held` is
    `mk("electionguide:past/r1", status_claim="held")`, `resch` is `mk("eisa:y2026/r3",
    status_claim="postponed", previous_date_text="1 November 2026")` and `hOct` is
    `mk("ndi:p0/past-c9", span=month(2026, 10), date_meaning="unknown", status_claim="held",
    date_text="October 2026")`. **Each claim takes the row's span**, unless the row gives the
    claim its own (revision 3: a `held` claim overrides only for an overlapping date, so "span
    9-13" puts `canc` and `held` on 13 September too). The rows give (status, resolved, conflict);
    `rescheduled` is False unless stated:

    | direct | (status, resolved, conflict) |
    |---|---|
    | `canc`, `fresh` | (Cancelled, cancelled, True) (D1: a listing never revives a cancellation) |
    | `canc`, `mk("electionguide:upcoming/r1", date_status="confirmed", fetched_at=FRESH_AT)` | (Cancelled, cancelled, True) (a refetched confirmed date is not reinstatement) |
    | `canc`, WPn `fallback=True`, `fetched_at=STALE_AT` | (Cancelled, cancelled, False) |
    | `canc` alone | (Cancelled, cancelled, False) |
    | `canc`, `mk("osce:elections/r2")` | (Cancelled, cancelled, False) (the same family never opposes) |
    | `canc`, IPU `**RENEW` fresh | (Cancelled, cancelled, False) |
    | `canc`, `ndi:p0/upcoming-c4` month Nov, `tentative`, `date_meaning="unknown"` | (Cancelled, cancelled, True) |
    | `canc`, `mk("electionguide:upcoming/r7", span=year(2026))` | (Cancelled, cancelled, False) (a year never opposes) |
    | `canc`, `held`; span `day(2026, 9, 13)` | (Held, None, True) (a fresh `held` claim from another family overrides) |
    | `canc`, `held` with `fallback=True`, `fetched_at=STALE_AT`; span 9-13 | (Cancelled, cancelled, False) |
    | `canc`, `held` with `fallback=True`, `fetched_at` 2026-10-13 00:00 UTC; span 9-13 | (Cancelled, cancelled, False) (fallback never overrides, fresh or not) |
    | `canc`, `mk("ipu:elections/r1", **RENEW, status_claim="held")`; span 9-13 | (Cancelled, cancelled, False) |
    | `canc`, `mk("carter:observed/r1", **OBS, span=day(2026, 9, 13), status_claim="held")`; span 9-13 | (Cancelled, cancelled, False) |
    | `canc`, `mk("osce:elections/r2", status_claim="held")`; span 9-13 | (Cancelled, cancelled, False) |
    | `canc`, `held` with `span=year(2026)`; span 9-13 | (Cancelled, cancelled, False) |
    | `canc`, `hOct` | (Cancelled, cancelled, True) (R2-01: a `held` claim for another month opposes, and never overrides) |
    | `mk("osce:elections/r1", status_claim="postponed")`, `fresh` | (Postponed, postponed, True) |
    | `resch`, `fresh` | (Upcoming, None, False), `rescheduled` True (D2) |
    | `mk("osce:elections/r2", status_claim="postponed")`, `canc` | (Cancelled, cancelled, False) (one family) |
    | `canc`, `mk("eisa:y2026/r3", status_claim="postponed")` | (Cancelled, cancelled, True) (opposed words) |
    | `canc`, that EISA claim with `fallback=True`, `fetched_at=STALE_AT` | (Cancelled, cancelled, False) |
    | `canc`, `resch`, `fresh` | (Cancelled, cancelled, True) |
    | `mk("osce:elections/r1", status_claim="disputed")`, `mk("eisa:y2026/r3", status_claim="postponed")` | (Postponed, postponed, True) |
    | `mk("osce:elections/r1", status_claim="disputed")`, `fresh`; span `day(2026, 9, 13)` | (Disputed, disputed, False) |
    | `mk("osce:elections/r1", status_claim="disputed", fallback=True, fetched_at=FRESH_AT)`; span `day(2026, 9, 13)` | (Held, None, False) |
  - **`test_rescheduling_lifecycle`** (D2; span `day(2026, 11, 15)`; `resch`, `held` and `canc` as
    above; `undated` is `mk("osce:elections/r1", status_claim="postponed")`):

    | direct | today | (status, resolved, conflict, rescheduled) |
    |---|---|---|
    | `resch` | 2026-10-19 | (Upcoming, None, False, True) |
    | `resch` | 2026-11-20 | (Held, None, False, True) (legacy Held; nothing confirms the vote) |
    | `resch`, `held` | 2026-11-20 | (Held, None, False, True) |
    | `undated` | 2026-11-20 | (Postponed, postponed, False, False) (no new date: it stays postponed) |
    | `undated`, `held` | 2026-11-20 | (Held, None, True, False) |
    | `resch`, `undated` | 2026-10-19 | (Postponed, postponed, False, False) (a further postponement) |
    | `resch`, `canc` | 2026-10-19 | (Cancelled, cancelled, True, False) |
    | `mk("eisa:y2026/r16", status_claim="postponed", previous_date_text="June 2026", span=year(2026))`, `fresh` | 2026-10-19 | (Postponed, postponed, True, False) (a year is not a usable new date) |
  - **`test_old_dates`** (R2-01, D2; `select` at `NOW`). The claims:
    - `eg` = EG up/r1 (15 November); `wp` = WPn `November/li[4]`;
    - `rs` = `mk("eisa:y2026/r3", span=month(2026, 12), date_meaning="unknown",
      date_status="tentative", status_claim="postponed", previous_date_text="15 November 2026",
      date_text="December 2026")`; `rsN` = `rs` with `span=month(2026, 11)`, "November 2026";
    - `eg29` = EG up/r1 with `day(2026, 11, 29)`; `rsF` = `mk("eisa:y2026/r3",
      span=day(2026, 11, 29), status_claim="postponed", previous_date_text="November 2026")`;
    - `resch` as in `test_status_claims`.

    | direct | selected | the others' reasons | `date_conflict` |
    |---|---|---|---|
    | `eg`, `rs` | `rs` | `eg` `old_date` (not dates-compatible with the new date) | True |
    | `eg`, `rsN` | `rsN` | `eg` `old_date` (inside the old day, which lies inside the new month) | True |
    | `eg`, `rs`, `wp` | `rs` | `eg` and `wp` `old_date` | True |
    | `eg29`, `rsF` | `eg29` | `rsF` `lower_priority` (the old month does not lie inside the new day) | False |
    | `eg`, `resch` | `eg` | `resch` `lower_priority` (both give the new date) | False |

    `unverified` is False in every row. Then `legacy_status([eg, rs], rs.span, date(2026, 11, 20))`
    is (Upcoming, None, False, True): five days after the abandoned date, the child is still
    upcoming, in December.
  - **`test_unknown_meaning_observation_is_never_a_polling_date`** (R5). Here `obs(span, **kw)`
    is `mk("carter:observed/r1", **OBS, span=span, **kw)`, and `eeas(span)` is
    `mk("eeas:missions/r1c1", **OBS, span=span)`:

    | `select` over | selected | the others' reasons |
    |---|---|---|
    | `obs(month(2026, 11))` | none (`claim is None`) | `observation` |
    | `obs(day(2026, 11, 15))`, WPn li[4] with `span=month(2026, 11)` | WPn (an observation is never eligible, even with day precision) | `observation` |
    | `obs(month(2026, 11))`, IPU `**RENEW` | IPU | `observation` |
    | `eeas(year(2026))`, `mk("osce:elections/r9", span=year(2026))` | none | `observation`, `year_only` |
  - **`test_unknown_meaning_observation_never_makes_held_or_ongoing`** (R5; the span is
    `day(2026, 11, 15)`; `rescheduled` is False in every row):

    | `legacy_status` over | today | result |
    |---|---|---|
    | WPn li[4], `obs(month(2026, 11), status_claim="cancelled")` | 2026-11-10 | (Upcoming, None, False): the observation's word is ignored, and its month, which holds today, does not decide the status |
    | `canc`, `obs(day(2026, 11, 15))` | 2026-10-19 | (Cancelled, cancelled, False): an observation never contradicts |
    | WPn li[4], `mk("eeas:missions/r1c1", **OBS, span=year(2026), status_claim="held")` | 2026-10-19 | (Upcoming, None, False) |
  - **`test_ndi_tbd_never_confirms_a_date`** (R13, Appendix B Serbia; `fixture_claim`,
    `FIXTURE_NOW`):
    - `select` over `electionguide:upcoming/r2#0`, `osce:elections/r2#0`,
      `wikipedia:national-2026@rev1380221397/October/li[6]/li[2]#0`, `ndi:p0/upcoming-c2#0` and
      `ipu:elections/r222#0`:
      - EG r2 is selected (`confirmed`, 2026-10-25);
      - OSCE and Wikipedia `less_certain`, NDI `not_covering`, IPU `lower_evidence`;
      - both flags False.
    - `select([ndi:p0/upcoming-c2#0])` → the NDI claim, with month precision (October 2026) and
      `date_status="tentative"`. It stays a TBD month, never a confirmed day.
    - `select` over EG r2 with `fallback=True` and `fetched_at=STALE_AT`, plus NDI c2 with
      `fetched_at=FRESH_AT` → EG r2, NDI `not_covering`, `date_conflict` False and `unverified`
      True. The TBD month does not confirm the day, and it contains the day, so it does not
      disagree (G05).
  - **`test_an_inferred_month_never_confirms_a_day`** (R13, the P47 ruling):
    - `ndi:p1/past-c5#0` (Colombia, `date_text` "May 31, 2026 (ALL DAY)") has month precision, May
      2026, with `date_status="unknown"`.
    - `select` over `electionguide:past/r32#0`,
      `wikipedia:national-2026@rev1380221397/May/li[6]/li[1]#0`, `ndi:p1/past-c5#0`,
      `aweb:calendar/r15#0` and `carter:observed/expert-r3#1`:
      - EG r32 is selected;
      - NDI `not_covering`, Carter `observation`, Wikipedia and A-WEB `less_certain`.
    - `select` over WPn li[4] with `span=day(2026, 11, 30)`, `fallback=True` and
      `fetched_at=STALE_AT`, plus `mk("ndi:p0/upcoming-c4", span=month(2026, 11),
      date_meaning="unknown", date_text="November 30, 2026 (ALL DAY)", fetched_at=FRESH_AT)` →
      WPn, NDI `not_covering`, `date_conflict` False and `unverified` True.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/merge/test_select.py -q`. Expected:
  FAIL (no module).
- [ ] **Step 3: Implement** `select.py`.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(merge): resolved-value selection and the legacy status`.

  Mutations, one each:
  - observations are eligible;
  - year-only claims are eligible;
  - `expected_renewal` ranks with `calendar`;
  - `umbrella` evidence ranks below `calendar`;
  - coverage accepts a claim that is not `voting_period`;
  - date_status before precision (the spec's order);
  - `is_stale` uses `>=` (exactly 7 days is stale);
  - `is_stale` treats a missing `fetched_at` as fresh;
  - the support set holds every eligible claim, of any evidence kind;
  - `date_conflict` counts a containing interval as a disagreement;
  - `date_conflict` looks only at the pool, not at the support set;
  - `unverified` ignores `date_meaning`;
  - `unverified` when *any* claim with the winner's interval is stale;
  - the final tie-break sorts by `unit_id` only;
  - `postponed` is tried before `cancelled`;
  - an opposing claim with no word overrides the word (revision 1's rule);
  - an opposing `held` claim does not override the word;
  - a fallback claim can oppose;
  - a claimer's own family can oppose;
  - a year-precision claim can oppose;
  - a rescheduling keeps `Postponed` (revision 1's rule);
  - a rescheduling accepts a year-only claimer;
  - `select` has no old-date step (`eg rs`);
  - the old-date step drops its inside-the-old-date test (`eg rsN`);
  - the inside-the-old-date test drops "the old date lies inside the new one" (`eg29 rsF`);
  - an `old_date` claim sets no `date_conflict` (`eg rsN`);
  - an opposing `held` claim overrides whatever its date (`canc hOct`);
  - an opposing `held` claim for another date sets no `conflict` (`canc hOct`);
  - opposed words from different families set no `conflict`;
  - opposed words count fallback claims;
  - a fallback `disputed` counts;
  - a month span over today's month gives `Upcoming`;
  - a day equal to today gives `Held`;
  - observations are not left out of `legacy_status`.

---

### Task 4: Matching (`match.py`; P67, P68, P70–P75, P78, P80–P82; R3, R6, R8, R12, C7; G01–G03, G06; R2-02, R2-03, D5)

**Files:**
- Create: `elections_calendar/merge/match.py`
- Test: `tests/merge/test_match.py`

**Interfaces:**
- Consumes: Task 2's `identity` module (all of it); Task 3's `select`, `legacy_status`,
  `Selection`, `StatusResult`; `model.ProvisionalDate`; `window.window_for`;
  `dates.parse_date_text`; `text.norm_name`.
- Produces:

```python
Origin = Literal["anchor", "standalone", "aggregate"]
PendingKind = Literal["unresolved_evidence", "provisional_change"]
PendingReason = Literal["no_candidate", "several_candidates", "provisional_aggregate",
                        "conflicting_claims"]                   # P82

@dataclass(eq=False)                        # identity semantics: contests go in sets
class Contest:
    origin: Origin
    members: list[Claim]                    # these three lists are in step 0's order (by
    attached: list[Claim] = field(default_factory=list)       # merge_id): each is filled by
    provisional: list[Claim] = field(default_factory=list)    # walking the sorted claims
    ambiguous: bool = False
    possible: set[Contest] = field(default_factory=set)
    date_conflict: bool = False
    status_conflict: bool = False
    provisional_date: ProvisionalDate | None = None           # Phase D (P74, D3)
    selection: Selection | None = None      # set when the contest is resolved
    status: StatusResult | None = None
    def direct(self) -> list[Claim]         # members + attached, sorted by merge_id
    @property
    def child_id(self) -> str
    @property
    def span(self) -> DateSpan              # the selected claim's span

@dataclass(frozen=True)
class Pending:                              # becomes an attention item (Task 5)
    kind: PendingKind
    reason: PendingReason
    claim: Claim
    candidates: tuple[Contest, ...]         # sorted by child_id

@dataclass(frozen=True)
class Undated:                              # becomes an undated listing (Task 5)
    claims: tuple[Claim, ...]               # sorted by merge_id
    possible: tuple[Contest, ...]           # sorted by child_id

@dataclass(frozen=True)
class Link:                                 # an umbrella and the contests it fits
    claim: Claim
    contests: tuple[Contest, ...]           # sorted by child_id

@dataclass(frozen=True)
class Matching:
    contests: tuple[Contest, ...]           # sorted by child_id
    links: tuple[Link, ...]                 # sorted by claim.merge_id
    undated: tuple[Undated, ...]            # sorted by claims[0].merge_id
    pending: tuple[Pending, ...]            # sorted by claim.merge_id

def match(claims: Sequence[Claim], now: datetime) -> Matching
def umbrella_covers(umbrella: Claim, members: Sequence[Claim], direct: Sequence[Claim],
                    span: DateSpan) -> bool                  # step 10; Task 6's audit calls it too
def umbrella_fits(umbrella: Claim, contest: Contest) -> bool  # umbrella_covers(u, k.members, k.direct(), k.span)
def contest_level(contest: Contest) -> Level
def contest_round(contest: Contest) -> int | None
```

**Rules** (§10.1–§10.4, with P66–P82). `match` runs these steps in order. Claims are paired only
within one place.

0. **Input.**
   - `window = window_for(now)`, so a naive `now` raises `ValueError("now must be timezone-aware")`.
     `today = window.today`.
   - A repeated `merge_id` raises `MergeError(f"duplicate merge_id: {merge_id}")`, naming the
     smallest repeated id.
   - Every claim's `role` is computed first, so an unknown source raises before anything else.
   - Sort the claims by `merge_id`, and keep every intermediate list in a stated order. The result
     never depends on the input order.
1. **Clustering**, used by steps 2, 4, 11 and 13:
   - two claims of one place are joined by an edge when the step's edge rule holds;
   - in each connected component, when every pair has an edge, the component is one group;
   - otherwise each claim of the component is its own group, flagged `ambiguous`. Its `possible`
     holds the groups of its edge neighbours;
   - a group lists its claims in step 0's order: take them from the sorted claims, never sort
     again. Task 6's order tests rely on this (their mutation drops step 0's sort).
2. **Phase A:** cluster the anchors with `joinable`. Each group is a contest of origin `anchor`.
3. **Phase B**, for the weak claims that are not observations.
   - A weak claim `w` **fits** a contest when every member is:
     - identity-compatible with `w`, with `relax_jurisdiction=True` when
       `w.jurisdiction_kind == "unknown"`;
     - `same_source_compatible` with `w`;
     - `dates_compatible` with `w`.
   - The candidates are the Phase A contests that `w` fits. Then, in order:
     1. **Month disagreement** (§10.3), only when there are no candidates and `w` has month
        precision. Its candidates are the Phase A contests whose every member is
        identity-compatible with `w` (strict), `same_source_compatible` with it, and has
        `w.span.start.year` in `years_of(member.span)`. One → a proposal for it, marked as a
        month disagreement. Two or more → pending `unresolved_evidence`, `several_candidates`.
        None → go on to 3.
     2. Exactly one candidate → a proposal for it (year precision too: P68).
     3. Year precision → the undated pool, with its candidates.
     4. No candidate → the standalone pool.
     5. Two or more → pending `unresolved_evidence`, `several_candidates`.
   - **The proposals of one contest are checked as a set** (P82). Two proposals `a`, `b` for one
     contest *conflict* when `identity_compatible(a, b, relax_jurisdiction=…)` fails (relaxed when
     either jurisdiction kind is `unknown`), or `same_source_compatible(a, b)` fails. Dates are not
     compared here.
     - A proposal that conflicts with any other proposal for its contest does not attach. A dated
       one → pending `unresolved_evidence`, `conflicting_claims`, with that contest as its only
       candidate. A year-only one → the undated pool, with that contest as its candidate.
     - Every other proposal attaches. A month-disagreement proposal sets the contest's
       `date_conflict`.
   - Members are fixed in this phase, and the conflicts are a symmetric relation over all of a
     contest's proposals, so the order of the weak claims does not matter.
4. **Phase C:** cluster the standalone pool with `joinable`. Each group is a contest of origin
   `standalone`.
5. **Umbrellas** (role `umbrella`), against the contests of Phases A and C:
   - **year precision** → the undated pool, with no candidates;
   - **class `legislature` with `aggregate`** (C7, P71). The candidates are the contests that are
     not `ambiguous`, whose members all have a class in `CHAMBERS` and none a kind in `REFERENDA`,
     whose every member is identity-compatible with the umbrella (`ignore_kind=True,
     ignore_institution=True`), `same_source_compatible` and `dates_compatible`, and whose every
     attached claim that is not an observation is identity-compatible with it (the same flags) and
     `same_source_compatible`. One → a C7 proposal for it. Otherwise → the umbrella list.
     **The C7 proposals of one contest are checked as a set** (P71, P82): two that are not
     identity-compatible with each other (`ignore_kind=True, ignore_institution=True`), or fail
     rule F, conflict. Conflicting ones join the umbrella list; the others attach;
   - **any other umbrella** → the umbrella list.
6. **Sessions** (P78).
   - A contest is dissolved when all its members have kind `referendum_day` and another contest's
     members all have kind `referendum_question`, with every (session member, question member)
     pair identity-compatible (`ignore_kind=True`) and `dates_compatible`.
   - Its direct claims join the umbrella list. Year-precision ones go to the undated pool instead,
     with no candidates.
   - A dissolved contest is removed from every pending item's candidates, every undated pool
     entry's candidates and every contest's `possible`. A pending item keeps its reason.
7. **Observations** (P67), after the sessions.
   - The candidates are the Phase A contests still present, of the observation's place, whose
     every member is `dates_compatible` with it. Office identity is not compared.
   - One → attach it. None → pending `unresolved_evidence`, `no_candidate`. Two or more →
     `several_candidates`.
8. **Resolve** each contest:
   - `selection = select(direct, now)`. When `selection.claim is None`, raise
     `MergeError(f"contest {child_id} has no eligible date")`. (Steps 2–7 make this unreachable.
     The check guards against a later rule change, and has no test.)
   - `date_conflict |= selection.date_conflict`.
   - `status = legacy_status(direct, span, today)`, and `status_conflict |= status.conflict`.
9. **Phase D** (provisional claims), against the resolved contests of steps 2–7:
   - **A `general` or `aggregate` claim** → pending `provisional_change`, `provisional_aggregate`.
     Its candidates are the contests it `umbrella_fits`.
   - **Otherwise, the twin** (P74). The candidates are the contests that hold a direct claim with
     `merge_id == "served/" + p.claim_id`, and whose every member is identity-compatible with `p`
     (strict; rule F and dates are not checked).
   - **No twin:** the candidates are the contests whose every member is identity-compatible and
     `same_source_compatible` with `p`, and shares a year with it (`years_of`).
   - **One candidate** → `provisional.append(p)`. Then the date (P74, D3). `covers(s, t)` holds
     when `s` has year precision and `years_of(t) == {s.year}`, or when neither has year
     precision and `s.start <= t.start` and `t.end <= s.end`.
     - **With a twin** (its served copy `d`; D5). The precision ranks are day 0, month 1, year 2.
       `p.span == d.span`, or `covers(d.span, p.span)` with `p` of a lower rank than `d` (a finer
       date inside the served one) → no change. `covers(p.span, d.span)` with `p` of a higher rank
       than `d` (a coarser date) → `less_precise`. Otherwise `moved`: a longer or a shorter range
       of days is a change of the polling days, not a loss of precision.
     - **Without a twin:** a year-precision `p`, `covers(p.span, k.span)` or
       `covers(k.span, p.span)` → no change; otherwise `moved`.
     - `moved` sets `date_conflict`, and `provisional_date = "moved"`. `less_precise` sets
       `provisional_date = "less_precise"` unless it is already `"moved"`.
   - Then the status (P75). The contest's word is `status.resolved`, or `"postponed"` when it is
     None and `status.rescheduled` is True. Set `status_conflict` when `p.status_claim` differs
     from that word, unless `p.status_claim == "held"` and the word is None.
   - **None** → pending `provisional_change`, `no_candidate`. **Two or more** →
     `several_candidates`.
10. **Links** (§10.4). Each claim of the umbrella list links to the contests of steps 2–7 that it
    `umbrella_fits`. A claim that fits none is *loose*. `umbrella_fits(u, k)` is
    `umbrella_covers(u, k.members, k.direct(), k.span)`, which holds when all of these do:
    - **place:** `u.place_id` is the members' place;
    - **referendums:** when `u.kind == "referendum_day"`, every member has kind
      `referendum_question`. Otherwise no member has a kind in `REFERENDA`;
    - **jurisdiction scope** (P81): when `u.jurisdiction_kind` is `named` or `subdivision`, every
      member has a `named` or `subdivision` jurisdiction with the same `norm_name`;
    - **office scope** (P81): a `legislature` umbrella needs every member's class in `CHAMBERS`; a
      `local_council` umbrella needs every member's class in {`local_council`, `mayor`}; a
      `general` umbrella has no office constraint; any other umbrella needs every member to have
      its class;
    - **a recognised umbrella** (P81): not (`u.office_class == "general"` and
      `u.level == "unknown"`);
    - **qualified numbers** (P81, R2-03): for every claim `d` of `direct` that is not an
      observation, every qualifier in both `qualified_numbers(u.office_label)` and
      `qualified_numbers(d.office_label)` gives equal sets. Attached claims count: an anchor may
      state no district while an attached claim names one. An umbrella that states no number is
      not constrained;
    - **dates:** for a year-precision `u`, `u.span.year in years_of(span)`. Otherwise `u.span`
      overlaps `span`;
    - **level:** `u.level` equals the level of `direct` (`contest_level`'s rule), or either is
      `unknown`;
    - **round:** `u.round` or the round of `direct` (`contest_round`'s rule) is None, or they are
      equal.
11. **Aggregates** (P72). Cluster the loose claims with this edge: the same `office_class`,
    identity-compatible with `ignore_institution=True`, `same_source_compatible` and
    `dates_compatible`; and, when either claim is *unrecognised* (`office_class == "general"` and
    `level == "unknown"`), `norm_name` of the two `office_label`s is equal, whatever their
    families (R2-02). Each group is a contest of origin `aggregate`, resolved as in step 8.
12. **Possible matches** (P73), over every contest. Each link goes both ways.
    - **(a) Rescheduling hint.** Take each direct claim `d` with a `previous_date_text`. Its
      contest is linked with every other contest whose every member is identity-compatible and
      `same_source_compatible` with `d`, when a non-year span of
      `parse_date_text(d.previous_date_text, default_year=d.span.year).spans` overlaps that
      contest's span.
    - **(b) Near dates.** Two contests of one place are linked when
      `1 <= gap_days(a.span, b.span) <= 7` and their members are pairwise identity-compatible and
      `same_source_compatible`.
    - **(c) Event copies.** Group the direct claims by (`source`, `source_event_id`), leaving out
      `ipu` and claims without an event id. When a group's claims sit in two or more contests, those
      contests are linked pairwise. When one contest holds two or more of its claims with
      different (`span.start`, `span.end`, `span.year`), that contest gets `date_conflict`.
13. **Undated groups.** Cluster the undated pool with `joinable`.
    - A complete group becomes one `Undated`, whose `possible` is the union of its claims'
      candidates.
    - An incomplete component gives one `Undated` per claim, each with its own candidates. The
      clustering's `ambiguous` flag and neighbours are not used here.

**The helpers:**
- `contest_level`: the one known level among the non-observation direct claims, else `"unknown"`.
- `contest_round`: the one stated round among the non-observation direct claims, else None.
- `umbrella_covers` applies these two rules to its `direct` argument, so Task 6's audit can call it
  on a child's claims, with no `Contest`.
- `Contest.child_id` (§5.3): `short_id` of the merge ids of the direct claims whose role is
  `anchor`; when there are none, of all the direct claims. It is computed when read, so it is
  final once matching ends.

- [ ] **Step 1: Write the failing tests** in `tests/merge/test_match.py`.
  - **The notation.** Each case names its claims, and lists the whole expected matching. Anything
    not listed is absent: no other contests, flags, links, pending items or undated groups. A test
    helper, `shape(matching, names)`, renders a matching as a set of strings in this notation, and
    each case compares sets:
    - **`{a b} A`:** a contest whose members are `a` and `b` (sorted).
      - `+c` inside the braces: `c` is attached. `⟨p⟩`: `p` is provisional.
      - The letter after the braces is the origin: `A` (anchor), `C` (standalone) or `G`
        (aggregate).
      - Then the flags, in this order: `~` (ambiguous), `dc` (`date_conflict`), `sc`
        (`status_conflict`), then `moved` or `less_precise` (`provisional_date`).
      - Elsewhere, a contest is named by its members alone: `{a b}`.
    - **`{a} ↔ {b}`:** the two contests name each other in `possible`.
    - **`u ⇒ {a} {b}`:** a link from umbrella `u` to those contests.
    - **Pending items:**
      - `w → several {a} {b}` is `unresolved_evidence`, `several_candidates`, with those candidates;
      - `w → none` is `unresolved_evidence`, `no_candidate`;
      - `w → conflicting {a}` is `unresolved_evidence`, `conflicting_claims` (P82);
      - `p → prov none`, `p → prov several {a} {b}` and `p → prov aggregate {a}` are
        `provisional_change` with `no_candidate`, `several_candidates` and `provisional_aggregate`.
    - **`U[y z] poss {a}`:** an undated group of `y` and `z`, with those possible contests.

    `EG up/rN` is `electionguide:upcoming/rN`, and `EG past/rN` is `electionguide:past/rN`. WPn and
    WPl are the synthetic revisions of Task 3 (`wikipedia:national-2026@rev1`,
    `wikipedia:local-2026@rev2`). `NOW` is the default `now`.
  - **The presets** (test-module constants; `RENEW`, `OBS` and `UMB` come from
    `tests.support.claims`):

```python
PE = dict(place_id="iso:PE", place_raw="Peru", institution=None, level="subnational",
          span=day(2026, 11, 22))
CH = dict(place_id="iso:CH", place_raw="Switzerland", institution=None, office_class="referendum",
          span=day(2026, 11, 29))
GB = dict(place_id="iso:GB", place_raw="United Kingdom", institution="iso:GB/house-of-commons",
          office_class="lower_house", kind="by_election",
          office_label="House of Commons by-election", span=day(2026, 11, 26))
XS = dict(place_id="x:south-ossetia", place_raw="South Ossetia",
          institution="x:south-ossetia/president", office_class="head_of_state",
          office_label="President")
IP = dict(**RENEW, source_event_id="ipu:SE-LC")
RU = dict(place_id="iso:RU", place_raw="Russia", institution="iso:RU/state-duma",
          office_class="lower_house", office_label="State Duma")
BR = dict(place_id="iso:BR", place_raw="Brazil")
PRES_BR = dict(**BR, institution="iso:BR/president", office_class="head_of_state",
               office_label="President")
LEG = dict(institution=None, office_class="legislature", aggregate=True, office_label="Parliament")
GD = dict(place_id="iso:GD", place_raw="Grenada", span=day(2026, 11, 5))
GD_IPU = dict(**RENEW, institution="iso:GD/house-of-representatives", office_class="lower_house",
              office_label="House of Representatives")
ES = dict(place_id="iso:ES", place_raw="Spain", span=day(2026, 11, 29))
SS = dict(place_id="iso:SS", place_raw="South Sudan", span=day(2026, 12, 22))
SI = dict(place_id="iso:SI", place_raw="Slovenia")
US = dict(place_id="iso:US", place_raw="United States",
          institution="iso:US/house-of-representatives", office_class="lower_house",
          kind="by_election", jurisdiction="Louisiana", jurisdiction_kind="subdivision",
          level="unknown", span=day(2026, 11, 3))
KG = dict(place_id="iso:KG", place_raw="Kyrgyzstan", institution="iso:KG/president",
          office_class="head_of_state", office_label="President")
CI = dict(place_id="iso:CI", place_raw="Côte d'Ivoire", institution="iso:CI/president",
          office_class="head_of_state", span=day(2026, 10, 25))
CO = dict(place_id="iso:CO", place_raw="Colombia")
LOWER = dict(**CO, institution="iso:CO/chamber", office_class="lower_house",
             office_label="Chamber of Representatives")
UPPER = dict(**CO, institution="iso:CO/senate", office_class="upper_house", office_label="Senate")
COUNCIL = dict(institution=None, office_class="local_council", office_label="Municipal councils",
               level="subnational")
GA = dict(place_id="iso:US", place_raw="United States", institution=None, level="subnational",
          jurisdiction="Georgia", jurisdiction_kind="subdivision", span=day(2026, 5, 19))
MB = dict(span=month(2026, 11), date_meaning="unknown", date_text="November 2026")
```

  - **`test_phase_a_components`** (S3-T5, §10.2). The claims, all `**RU`:
    - `a` = EG past/r12, `day(2026, 9, 18)`;
    - `b` = `osce:elections/r33`, 9-19;
    - `c` = WPn `September/li[3]`, 9-20;
    - `d` = `ndi:p0/past-c3`, 9-21;
    - `e` = `aweb:calendar/r23`, `days(2026, 9, 18, 2026, 9, 21)`;
    - `b2` = `osce:elections/r33`, 9-18.

    | claims | expected |
    |---|---|
    | a b c d | `{a} A`, `{b} A`, `{c} A`, `{d} A`; all 6 pairs linked (near dates, 1–3 days) |
    | a b c d e | `{a} A ~`, `{b} A ~`, `{c} A ~`, `{d} A ~`, `{e} A ~`; all 10 pairs linked (e's by ambiguity, the rest by near dates) |
    | a b2 | `{a b2} A` |
  - **`test_rounds`** (S3-T6, NM-T06). The claims, all `**PRES_BR`:
    - `r1` = EG past/r4, `round=1`, 10-04;
    - `r2` = EG up/r3, `round=2`, 10-25;
    - `un` = WPn `October/li[2]`, 10-04;
    - `m` = `eisa:y2026/r2`, `month(2026, 10)`, `date_meaning="unknown"`;
    - `n` = `ndi:p0/past-c2`, 10-04;
    - `s` = EG past/r5, `round=2`, 10-04.

    | claims | expected |
    |---|---|
    | r1 r2 un | `{r1 un} A`, `{r2} A` |
    | r1 r2 un m | the same, and `m → several {r1 un} {r2}` |
    | n un | `{n un} A` |
    | r1 s un | `{r1} A ~`, `{s} A ~`, `{un} A ~`; `{r1} ↔ {un}`, `{s} ↔ {un}` |
  - **`test_weak_claims`** (S3-T1, S3-T3, S3-T7, R7, §10.3). The claims:
    - **Peru:**
      - `ma` = WPl `November/li[1]/li[1]` `**PE`, jurisdiction "Lima" `named`, `mayor`, "Mayor";
      - `mc` = WPl `November/li[1]/li[2]` `**PE`, "Lima" `named`, `local_council`,
        "Municipal council";
      - `u` = `ndi:p0/upcoming-c1` `**{**PE, **UMB}`, "2026 Peru Municipal Elections";
      - `x1` = WPl `November/li[2]` `**PE`, `jurisdiction_kind="unknown"`, `mayor`, "Mayor";
      - `x2` = `ndi:p0/upcoming-c2`, the same fields as `x1`.
    - **United Kingdom:**
      - `h` = EG up/r1 `**GB`, "Holborn and St Pancras" `named`;
      - `r` = EG up/r2 `**GB`, "Runcorn and Helsby" `named`;
      - `w` = WPl `November/li[3]` `**GB`, `jurisdiction_kind="unknown"`.
    - **South Ossetia:** `s1` = WPn `November/li[6]` `**XS`; `s2` = `osce:elections/r4` `**XS`
      with `place_raw="S. Ossetia"`.
    - **Sweden:** `j` = EG up/r40, `day(2027, 1, 10)`; `f` = EG up/r41, `day(2027, 2, 20)`; `t` =
      `ndi:p0/upcoming-c9`, `months(2027, 1, 2027, 2)`, `tentative`, `date_meaning="unknown"`.

    | claims | expected |
    |---|---|
    | ma mc u | `{ma} C`, `{mc} C`; `u ⇒ {ma} {mc}` (S3-T1: a mayor and a council never join) |
    | x1 x2 | `{x1} C`, `{x2} C` (two `unknown` jurisdictions never join) |
    | h w | `{h +w} A` (relaxed, one candidate) |
    | h r w | `{h} A`, `{r} A`; `w → several {h} {r}` |
    | s1 s2 | `{s1 s2} A` (an `x:` place matches by `place_id`) |
    | f j t | `{f} A`, `{j} A`; `t → several {f} {j}` (S3-T7: a candidate outside the window still counts) |
    | each R7 claim `c` with its `nat` (Task 2) | `{c} C`, `{nat} A` |
  - **`test_observation_with_zero_one_and_several_candidates`** (R6, P67). `obs(**kw)` is
    `mk("carter:observed/r1", **OBS, **kw)`. The claims:
    - `o` = `obs(span=month(2026, 11))`; `oNO` = the same with `place_id="iso:NO"`; `oOct` =
      `obs(span=month(2026, 10))`; `oCO` = `obs(**CO, span=month(2026, 11))`;
    - `e1` = EG up/r1; `lo` = EG up/r1 `**LOWER`; `up` = EG up/r2 `**UPPER`, `day(2026, 11, 22)`;
    - `p50` = EG past/r50, `day(2026, 2, 8)`; `c51` = EG past/r51 `**COUNCIL`, `day(2026, 3, 8)`;
    - `ey` = `mk("eeas:missions/r1c1", **OBS, span=year(2026), date_text="2026")`; `eyCO` = `ey` with
      `**CO`;
    - `lo50` = EG past/r50 `**LOWER`, `day(2026, 3, 8)`; `up51` = EG past/r51 `**UPPER`,
      `day(2026, 3, 8)`;
    - `qa` and `s` from `test_referendum_questions_and_sessions`; `oCH` =
      `obs(place_id="iso:CH", place_raw="Switzerland", span=month(2026, 11))`.

    | claims | expected |
    |---|---|
    | oNO | `oNO → none` |
    | e1 o | `{e1 +o} A` |
    | lo oCO up | `{lo} A`, `{up} A`; `oCO → several {lo} {up}` |
    | e1 oOct | `{e1} A`; `oOct → none` (an observation never takes the month-disagreement path) |
    | c51 ey p50 | `{c51} C`, `{p50 +ey} A` (a Phase C contest is never an observation's candidate; a year-only observation attaches) |
    | eyCO lo50 up51 | `{lo50} A`, `{up51} A`; `eyCO → several {lo50} {up51}` |
    | oCH qa s | `{qa +oCH} A`; `s ⇒ {qa}` (observations are matched after the sessions) |
  - **`test_month_disagreement`** (§10.3). The claims:
    - `a` = EG up/r17 `**PRES_BR`, 11-15; `b` = EG up/r18 `**PRES_BR`, `day(2026, 3, 1)`;
    - `m` = `eisa:y2026/r7` `**PRES_BR`, `month(2026, 10)`, `date_meaning="unknown"`;
    - `mS` = `m` with `institution="iso:BR/senate"`, `office_class="upper_house"`; `m27` = `m` with
      `span=month(2027, 10)`; `mU` = `m` with `jurisdiction_kind="unknown"`;
    - `g` = EG up/r34, `day(2027, 1, 16)`; `i` = `ipu:elections/r183` `**RENEW`,
      `day(2027, 2, 28)`; `iM` = `i` with `span=month(2027, 2)`;
    - **R2-01:** `mR` = `m` with `span=month(2026, 12)`, "December 2026",
      `status_claim="postponed"`, `previous_date_text="15 November 2026"`; `ac` = `a` with
      `status_claim="cancelled"`; `hO` = `ndi:p0/past-c9` `**PRES_BR`, `month(2026, 10)`,
      `date_meaning="unknown"`, `status_claim="held"`, "October 2026".

    | claims | expected |
    |---|---|
    | a m | `{a +m} A dc`; `m` is `not_covering` |
    | a mR | `{a +mR} A dc`; `mR` selected, `a` `old_date`; status `Upcoming`, `rescheduled` True (R2-01: the contest follows the new date) |
    | ac hO | `{ac +hO} A dc sc`; `ac` selected, `hO` `not_covering`; status `Cancelled` (R2-01: a `held` claim for another month never lifts the word) |
    | a b m | `{a} A`, `{b} A`; `m → several {a} {b}` |
    | a mS | `{a} A`, `{mS} C` (strict identity: another office) |
    | a m27 | `{a} A`, `{m27} C` (the start year must be in every member's years) |
    | a mU | `{a} A`, `{mU} C` (no relaxing) |
    | g i | `{g} A`, `{i} C` (a day never disagrees) |
    | g iM | `{g +iM} A dc` |
  - **`test_month_claim_attaches_with_date_conflict`** (R12). Match the 8 fixture claims with
    `place_id == "iso:CV"` at `FIXTURE_NOW`. The result is exactly:
    - **the presidency:** members `electionguide:upcoming/r17#0`,
      `wikipedia:national-2026@rev1380221397/November/li[4]#0` and `ndi:p0/upcoming-c4#0`; attached
      `eisa:y2026/r7#0` ("October 2026"); `date_conflict` True; EG r17 selected and EISA r7
      `not_covering`;
    - **the National Assembly:** members `electionguide:past/r36#0`,
      `wikipedia:national-2026@rev1380221397/May/li[3]#0` and `eisa:y2026/r6#0`, with no flags;
    - **`ipu:elections/r47#0`** (May 2031), standalone.
  - **`test_ipu_chamber_id_is_not_an_election_cycle`** (R3, S3-T4, P74). The claims:
    - `i1` = `ipu:elections/r1` `**IP`, `day(2026, 11, 5)`; `i2` = `ipu:elections/r2` `**IP`,
      `day(2030, 11, 5)`; `i3` = `ipu:elections/r2` `**IP`, `day(2026, 11, 9)`;
    - `p` = `ipu:elections/r1` `**IP`, `day(2026, 12, 2)`, `provisional=True`;
    - `i1b` = `ipu:elections/r1` `**IP`, `day(2026, 12, 20)`; `pb` = the same unit,
      `day(2027, 1, 17)`, `provisional=True`;
    - `e` = `eisa:y2026/r3`, `day(2026, 11, 26)`, `status_claim="postponed"`,
      `previous_date_text="5 November 2026"`,
      `date_text="Postponed from 5 November 2026 to 26 November 2026"`.

    | claims | expected |
    |---|---|
    | i1 i2 | `{i1} C`, `{i2} C` (one chamber id, two cycles: never joined, never linked) |
    | i1 p | `{i1 ⟨p⟩} C dc moved` (the twin) |
    | i1b pb | `{i1b ⟨pb⟩} C dc moved` (the twin crosses the year end) |
    | e i1 | `{e} A`, `{i1} C`; `{e} ↔ {i1}`; `e`'s contest has status `Upcoming`, `rescheduled` True (D2) |
    | i1 i3 | `{i1} C`, `{i3} C`; `{i1} ↔ {i3}` (4 days apart) |
  - **`test_generic_legislature`** (C7, P71). The claims:
    - `w` = WPn `November/li[2]` `**GD, **LEG`; `i` = `ipu:elections/r105` `**GD, **GD_IPU`;
    - `o` = `osce:elections/r5` `**ES, **LEG` with "Parliamentary Elections"; `c` = EG up/r18 `**ES`,
      `institution="iso:ES/congress"`, `lower_house`, "Congress"; `s` = EG up/r19 `**ES`,
      `institution="iso:ES/senate"`, `upper_house`, "Senate";
    - `asm` = `mk("wikipedia:national-2026@rev1/December/li[4]", 1, **SS, **LEG)` with "Assembly";
      `t` = EG up/r28 `**SS`, `institution="iso:SS/tnla"`, `lower_house`, "TNLA"; `cs` = EG up/r29
      `**SS`, `institution="iso:SS/council-of-states"`, `upper_house`, "Council of States"; `wc` =
      `mk("wikipedia:national-2026@rev1/December/li[4]", 2, …)` with the same fields as `cs`;
    - `wy` = `mk("wikipedia:national-2027@rev3/Unknown_date/li[9]", **{**GD, "span": year(2027)}, **LEG)`.

    | claims | expected |
    |---|---|
    | i w | `{i +w} C`; `w` selected, `i` `lower_evidence` |
    | c o s | `{c} A`, `{s} A`; `o ⇒ {c} {s}` (two chambers: an umbrella) |
    | asm cs t wc | `{cs wc} A`, `{t +asm} A` (rule F leaves one chamber) |
    | i wy | `{i} C`; `U[wy]` |
  - **`test_same_source_rule`** (P70). The claims:
    - `d12` = WPl `November/li[9]/li[1]` `**US`, "State House District 12 special election";
      `d40` = WPl `November/li[9]/li[2]` `**US`, "State House District 40 special election";
      `d12b` = WPl `November/li[9]/li[2]` `**US`, "state house district 12 special  election";
    - `n40` = `ndi:p0/upcoming-c6` `**US`, "Louisiana State House District 40 Special Election";
      `n12` = `ndi:p0/upcoming-c7` `**US`, "Louisiana House District 12 Special Election"; `e12` =
      EG up/r44 `**US`, "12th State House District" (P80: qualified numbers across families);
    - `rn` = WPn `November/li[1]`; `rl` = WPl `November/li[1]`, "Swedish general election";
    - `c1` = `ndi:p0/upcoming-c1` `**CI`, "2026 Côte d'Ivoire Presidential Election"; `c2` =
      `ndi:p0/upcoming-c2` `**CI`, "2026 Ivory Coast Presidential Election"; `eg` = EG up/r9 `**CI`,
      "Ivorian Presidency".

    | claims | expected |
    |---|---|
    | d12 d40 | `{d12} A`, `{d40} A` |
    | d12 d12b | `{d12 d12b} A` |
    | d12 n40 | `{d12} A`, `{n40} A` (two families, districts 12 and 40) |
    | d12 n12 | `{d12 n12} A` |
    | d12 e12 | `{d12 e12} A` (an ordinal before its qualifier) |
    | rl rn | `{rl rn} A` (two families) |
    | c1 c2 | `{c1} A`, `{c2} A` (the known limit: one source's alias titles stay apart) |
    | c1 c2 eg | `{c1} A ~`, `{c2} A ~`, `{eg} A ~`; `{c1} ↔ {eg}`, `{c2} ↔ {eg}` |
  - **`test_referendum_questions_and_sessions`** (S3-T2, P78). The claims, all `**CH`:
    - `qa` = `mk("wikipedia:national-2026@rev1/November/li[5]", 0, **CH, kind="referendum_question", office_label="Question A")`;
    - `qb` = the same unit with `n=1`, "Question B";
    - `qa2` = `osce:elections/r3`, `referendum_question`, "question a";
    - `s` = EG up/r20, `referendum_day`, "Referendum"; `s2` = the WPn unit with `n=0`,
      `referendum_day`, "Referendums";
    - `u` = `ndi:p0/upcoming-c1` `**{**CH, **UMB}`.

    | claims | expected |
    |---|---|
    | qa qa2 qb s | `{qa qa2} A`, `{qb} A`; `s ⇒ {qa qa2} {qb}` |
    | s s2 | `{s s2} A` (a session alone is one contest) |
    | s u | `{s} A`, `{u} G` (no other umbrella links to a referendum contest) |
  - **`test_umbrella_links`** (S3-T13, S3-T14; Plan 2a merge row 1). The claims:
    - **Brazil** (`BRP` is `PRES_BR` with "Brazilian Presidency"):
      - `p2` = EG up/r3 `**BRP`, `round=2`, 10-25; `p1` = EG past/r4 `**BRP`, `round=1`, 10-04;
      - `gb` = WPl `October/li[9]/li[1]` `**BR`, `institution=None`, `governor`, "Governor",
        `subnational`, "Bahia" `subdivision`, `round=2`, 10-25;
      - `rf` = WPn `October/li[6]/li[4]` `**BR`, `institution=None`, `referendum`,
        `referendum_day`, "Referendum", 10-25;
      - `u` = `aweb:calendar/r27` `**BR, **UMB`, "2026 Brazilian General Elections (2nd round)",
        `round=2`, 10-25; `uU` = `u` with `level="unknown"`.
    - **South Sudan** (all `**SS`):
      - `pr` = EG up/r30, `institution="iso:SS/president"`, `head_of_state`, "Presidency";
      - `tn` = EG up/r28, `institution="iso:SS/tnla"`, `lower_house`, "TNLA";
      - `e0`, `e1`, `e2` = `eisa:y2026/r19` with `n` 0, 1, 2:
        - `e0`: `iso:SS/president`, `head_of_state`, "Presidential";
        - `e1`: `iso:SS/tnla`, `lower_house`, "Legislative";
        - `e2`: `institution=None`, `local_council`, `subnational`, "Local councils".
    - **Sweden:** `r` = EG up/r1; `pz` = EG up/r2, `institution="iso:SE/president"`,
      `head_of_state`, "President", `confirmed`; `ms` = WPl `November/li[1]`, `institution=None`,
      `mayor`, "Mayor", `subnational`, "Stockholm" `named`; `n` = `ndi:p0/upcoming-c1` `**UMB`,
      `level="unknown"`; `nN` = `n` with `level="national"`.

    | claims | expected |
    |---|---|
    | gb p1 p2 rf u | `{gb} C`, `{p1} A`, `{p2} A`, `{rf} A`; `u ⇒ {p2}` (S3-T13: only the second-round presidency, never the referendum or the subnational governor) |
    | gb p2 uU | `{gb} C`, `{p2} A`, `{uU} G` (P81: a `general` umbrella of `unknown` level links nowhere) |
    | e0 e1 e2 pr tn | `{e0 pr} A`, `{e1 tn} A`, `{e2} C` (S3-T14) |
    | ms n pz r | `{ms} C`, `{n} G`, `{pz} A`, `{r} A` (the same rule) |
    | ms nN pz r | `{ms} C`, `{pz} A`, `{r} A`; `nN ⇒ {pz} {r}` (a national umbrella never covers the mayor) |
  - **`test_umbrella_scope`** (P81, G02, R2-03). The claims:
    - **Peru:** `ma` and `u` from `test_weak_claims`; `cz` = WPl `November/li[1]/li[3]` `**PE`,
      "Cusco" `named`, `mayor`, "Mayor"; `ul` = `ndi:p0/upcoming-c3` `**PE`, `local_council`,
      `aggregate=True`, `kind="aggregate"`, "Lima municipal elections", "Lima" `named`.
    - **Brazil:** `p2` from `test_umbrella_links`; `pl` = `osce:elections/r9` `**BR, **LEG`, 10-25.
    - **Georgia (US):** `gv` = WPl `May/li[11]/li[1]` `**GA`, `governor`, "Governor"; `lg` = WPl
      `May/li[11]/li[3]` `**GA`, `upper_house`, "7th Senate district, special election"; `sc` = WPl
      `May/li[11]/li[2]` `**{**GA, **UMB}`, `level="unknown"`, "Supreme Court"; `gs` =
      `ndi:p0/upcoming-c11` `**{**GA, **UMB}`, "Georgia state elections".
    - **Sweden (R2-03, qualified numbers):** `c40` = EG up/r50, `lower_house`, "District 40"; `c12`
      = EG up/r51, `lower_house`, "District 12"; `lg12` = `osce:elections/r32` `**LEG`, "District 12
      legislature elections"; `ug12` = `ndi:p0/upcoming-c12` `**UMB`, `level="national"`,
      "District 12 elections"; `a0` = EG up/r52 ("Riksdag"); `w40` = `ndi:p0/upcoming-c4` `**MB`,
      "District 40"; `ph1` = EG up/r53, "Riksdag (1st phase)"; `ph2` = EG up/r54, "Riksdag (2nd
      phase)"; `up2` = `osce:elections/r31` `**UMB`, `level="national"`, "Parliament (2nd phase)".

    | claims | expected |
    |---|---|
    | cz ul | `{cz} C`, `{ul} G` (a named umbrella covers only its own jurisdiction) |
    | cz ma ul | `{cz} C`, `{ma} C`; `ul ⇒ {ma}` (a council umbrella covers the mayor) |
    | cz ma u | `{cz} C`, `{ma} C`; `u ⇒ {cz} {ma}` (an umbrella with no jurisdiction covers both) |
    | p2 pl | `{p2} A`, `{pl} G` (a legislature umbrella never covers a presidency) |
    | gv lg sc | `{gv} C`, `{lg} C`, `{sc} G` (an office the parsers do not recognise stands alone) |
    | gs gv lg | `{gv} C`, `{lg} C`; `gs ⇒ {gv} {lg}` (an umbrella with no number covers "7th Senate district") |
    | c40 lg12 | `{c40} A`, `{lg12} G` (the review's case: C7 rejects District 12 for District 40, and so does the link) |
    | c12 lg12 | `{c12 +lg12} A`; `c12` selected, `lg12` `lower_priority` (C7: the same district) |
    | c40 ug12 | `{c40} A`, `{ug12} G` |
    | c12 c40 ug12 | `{c12} A`, `{c40} A`; `ug12 ⇒ {c12}` |
    | a0 w40 ug12 | `{a0 +w40} A`, `{ug12} G`; `w40` `not_covering` (the attached claim states the district the anchor does not) |
    | ph1 ph2 up2 | `{ph1} A`, `{ph2} A`; `up2 ⇒ {ph2}` (phases) |
    | ph1 up2 | `{ph1} A`, `{up2} G` |
  - **`test_attachments_are_checked_together`** (P82, G03; C7). The claims:
    - **Brazil** (all `**PRES_BR`): `a` = EG up/r17; `w1` = `eisa:y2026/r7` `**MB`, `round=1`;
      `w2` = `ndi:p0/upcoming-c4` `**MB`, `round=2`, `tentative`; `w0` = WPn `November/li[4]`
      `**MB`; `wy` = `osce:elections/r24`, `year(2026)`, "2026", `round=2`; `m10` = `w1` with
      `month(2026, 10)`, "October 2026"; `f1` = `ndi:p0/upcoming-c4` `**MB`; `f2` =
      `ndi:p0/upcoming-c5` `**MB`, "Vice President".
    - **United States** (all `**US`; `NOV` is `span=month(2026, 11)`, `date_meaning="unknown"`):
      `ua` = EG up/r44, "Louisiana House special election"; `l1` = `ndi:p0/upcoming-c6` `**NOV`,
      `level="national"`; `l2` = `eisa:y2026/r8` `**NOV`, `level="subnational"`; `d1` =
      `ndi:p0/upcoming-c6` `**NOV`, "House District 12 Special Election"; `d2` = `eisa:y2026/r8`
      `**NOV`, "House District 40"; `d3` = `eisa:y2026/r8` `**NOV`, "12th House District".
    - **Grenada:** `i` and `w` from `test_generic_legislature`; `g1` = `osce:elections/r30`
      `**GD, **LEG`, `round=1`; `g2` = `mk("wikipedia:national-2026@rev1/November/li[2]", 1, **GD,
      **LEG, round=2)`; `h` = EG up/r50 `**GD`, `institution="iso:GD/house-of-representatives"`,
      `lower_house`, "House of Representatives"; `r2` = `ndi:p0/upcoming-c4` with the fields of `h`,
      `month(2026, 11)`, `date_meaning="unknown"`, `tentative`, `round=2`.

    | claims | expected |
    |---|---|
    | a w1 | `{a +w1} A` |
    | a w0 w1 | `{a +w0 +w1} A` |
    | a w1 w2 | `{a} A`; `w1 → conflicting {a}`, `w2 → conflicting {a}` (rounds 1 and 2) |
    | a w0 w1 w2 | `{a +w0} A`; `w1 → conflicting {a}`, `w2 → conflicting {a}` |
    | a w1 wy | `{a} A`; `w1 → conflicting {a}`; `U[wy] poss {a}` (a year-only proposal goes to the undated pool) |
    | a m10 w2 | `{a} A`; `m10 → conflicting {a}`, `w2 → conflicting {a}` (a month disagreement is checked too) |
    | a f1 f2 | `{a} A`; `f1 → conflicting {a}`, `f2 → conflicting {a}` (rule F) |
    | ua l1 l2 | `{ua} A`; `l1 → conflicting {ua}`, `l2 → conflicting {ua}` (two levels) |
    | ua d1 d2 | `{ua} A`; `d1 → conflicting {ua}`, `d2 → conflicting {ua}` (districts 12 and 40) |
    | ua d1 d3 | `{ua +d1 +d3} A` |
    | i w | `{i +w} C` |
    | i g1 g2 | `{i} C`; `g1 ⇒ {i}`, `g2 ⇒ {i}` (two C7 proposals that conflict become umbrellas) |
    | g1 h | `{h +g1} A` |
    | g1 h r2 | `{h +r2} A`, `{g1} G` (C7 checks the attached claims too) |
  - **`test_unmatched_umbrellas_cluster`** (P72, R2-02). The claims, all `**SI` unless stated:
    - `lo` = `osce:elections/r4` `**UMB`, "Local Elections", `subnational`;
    - `ll` = WPl `November/li[4]` `**UMB`, "local elections", `subnational`;
    - `ln` = `ndi:p0/upcoming-c8` `**UMB`, "2026 Slovenia Local Elections", `subnational`,
      `month(2026, 11)`, `date_meaning="unknown"`, `tentative` (revision 2 gave it `level="unknown"`);
      `lnU` = `ln` with `level="unknown"`;
    - `pl` = WPl `November/li[5]`, `**LEG`;
    - `rg` = WPl `November/li[6]` `**UMB`, "regional elections", `subnational`;
    - **Georgia (US):** `sc` from `test_umbrella_scope` ("Supreme Court", `level="unknown"`); `ca` =
      `ndi:p0/upcoming-c13` `**{**GA, **UMB}`, `level="unknown"`, "Court of Appeals"; `sc2` =
      `ndi:p0/upcoming-c14`, the same fields with "supreme  court".

    | claims | expected |
    |---|---|
    | ll ln lo | `{ll ln lo} G`; `lo` selected, `ll` `lower_priority`, `ln` `not_covering` |
    | ll lnU lo | `{ll lo} G`, `{lnU} G` (R2-02: an unrecognised claim joins only an equal label) |
    | ca sc | `{ca} G`, `{sc} G` (two courts, two families: never one child) |
    | sc sc2 | `{sc sc2} G`; `sc` selected, `sc2` `lower_priority` (equal labels across families) |
    | lo pl | `{lo} G`, `{pl} G` (two classes) |
    | ll rg | `{ll} G`, `{rg} G` (rule F) |
  - **`test_provisional_claims`** (V2-T01, V2-T02, P74, P75; G06, D1, D3, D5). The claims:
    - `e` = EG up/r1; `e2` = EG up/r2, `day(2026, 3, 1)`; `ec` = EG up/r1 with
      `status_claim="cancelled"`;
    - `pe` = EG up/r1 with `provisional=True`. Its variants:
      - `pe22` with `day(2026, 11, 22)`; `pe27` with `year(2027)`, "2027"; `pey` with `year(2026)`,
        "2026"; `pem` with `month(2026, 11)`, "November 2026"; `per` with
        `days(2026, 11, 14, 2026, 11, 15)`; `pes` with `day(2026, 11, 15)`; `pet` with
        `date_text="Sunday 15 November 2026"`;
      - `pep` with `status_claim="postponed"`; `peh` with `status_claim="held"`;
    - `er` = EG up/r1 with `days(2026, 11, 14, 2026, 11, 15)` (a served range of days, D5);
    - `nmo` = `ndi:p0/upcoming-c4`, `month(2026, 11)`, `tentative`, `date_meaning="unknown"`; `pnm`
      = the same unit with `provisional=True` and `day(2026, 11, 22)` (revision 3: revision 2's
      15 November is the contest's own day, so its row could not tell the twin's span from the
      contest's; `mut7b.py`);
    - `res` = `eisa:y2026/r3`, `status_claim="postponed"`, `previous_date_text="1 November 2026"`;
      `presch` = `res` with `provisional=True`;
    - `ag` = `ndi:p0/upcoming-c1` `**UMB` with `provisional=True`; `agNO` = `ag` with
      `place_id="iso:NO"`; `un` = `ndi:p0/upcoming-c1` `**UMB` (not provisional);
    - `po` = `osce:elections/r1`, `provisional=True`, `institution="iso:SE/x"`, `head_of_state`,
      "President";
    - `ps` = `osce:elections/r1`, `provisional=True`, `day(2026, 12, 6)`; `pn` = the same with
      `day(2027, 1, 10)`; `psm` = the same with `month(2026, 11)`; `psy` = the same with
      `year(2026)`.

    | claims | expected |
    |---|---|
    | e pe22 | `{e ⟨pe22⟩} A dc moved` |
    | e pe | `{e ⟨pe⟩} A` |
    | e pet | `{e ⟨pet⟩} A` (only the text changed) |
    | e pey | `{e ⟨pey⟩} A less_precise` |
    | e pem | `{e ⟨pem⟩} A less_precise` |
    | er pem | `{er ⟨pem⟩} A less_precise` (a range of days becoming its month) |
    | e per | `{e ⟨per⟩} A dc moved` (D5: 15 → 14–15 November is a change of the polling days, not a coarser date) |
    | er pes | `{er ⟨pes⟩} A dc moved` (D5: a shorter range of days) |
    | e pe27 | `{e ⟨pe27⟩} A dc moved` (a year that is not the day's) |
    | e nmo pnm | `{e +nmo ⟨pnm⟩} A` (the twin `nmo` is a month that holds the new day, 22 November; against the contest's 15 November it would be `moved`) |
    | e pep | `{e ⟨pep⟩} A sc` |
    | e peh | `{e ⟨peh⟩} A` (`held`, and the contest has no word) |
    | agNO | `agNO → prov aggregate` (no candidates) |
    | ag e | `{e} A`; `ag → prov aggregate {e}` |
    | e un | `{e} A`; `un ⇒ {e}` |
    | e po | `{e} A`; `po → prov none` |
    | e ps | `{e ⟨ps⟩} A dc moved` (no twin: identity, rule F and a shared year) |
    | e psm | `{e ⟨psm⟩} A` (no twin: a month that holds the day) |
    | e psy | `{e ⟨psy⟩} A` (no twin: a year is never a move) |
    | e o psy | `{e o ⟨psy⟩} A less_precise` (`o` = `osce:elections/r1`, so `psy` has a twin) |
    | e o pe22 psy | `{e o ⟨pe22⟩ ⟨psy⟩} A dc moved` (`moved` is never overwritten) |
    | e pn | `{e} A`; `pn → prov none` (no twin and no shared year) |
    | e e2 ps | `{e} A`, `{e2} A`; `ps → prov several {e} {e2}` |
    | ec pe | `{ec ⟨pe⟩} A sc`; status `Cancelled` |
    | ec peh | `{ec ⟨peh⟩} A sc`; status `Cancelled` (D1: a provisional `held` never lifts it) |
    | res | `{res} A`; status `Upcoming`, `rescheduled` True |
    | res presch | `{res ⟨presch⟩} A` (the word is `postponed`, through the rescheduling) |
  - **`test_possible_matches`** (P73; the rescheduling hint and the IPU exclusion are in
    `test_ipu_chamber_id_is_not_an_election_cycle`). The claims:
    - `k1` = EG up/r40 `**KG`, `day(2027, 1, 27)`;
    - `k24`, `k19`, `k20` = `ndi:p0/upcoming-c5` `**KG` on 24, 19 and 20 January 2027; `kx` =
      `k24` with `institution="iso:KG/other"`;
    - with `EGE = dict(source_event_id="electionguide:5259")`: `c1` = EG up/r1 `**EGE`; `c1r` = the
      same with `days(2026, 11, 14, 2026, 11, 15)`; `c2` = EG past/r1 `**EGE`; `c2d` = the same
      with `day(2026, 12, 20)`.

    | claims | expected |
    |---|---|
    | k1 k24 | `{k1} A`, `{k24} A`; `{k1} ↔ {k24}` (3 days) |
    | k1 k19 | `{k1} A`, `{k19} A` (8 days: no link) |
    | k1 k20 | `{k1} A`, `{k20} A`; `{k1} ↔ {k20}` (7 days) |
    | k1 kx | `{k1} A`, `{kx} A` (another institution) |
    | c1 c2d | `{c1} A`, `{c2d} A`; `{c1} ↔ {c2d}` (one event in two contests) |
    | c1r c2 | `{c1r c2} A dc`; `c2` is `not_covering` |
    | c1 c2 | `{c1 c2} A` (a replayed copy adds no conflict) |
  - **`test_year_only_claims`** (R8, P68). The claims:
    - `y` = `osce:elections/r24`, `year(2027)`, "Parliamentary Elections";
    - `a` = EG up/r60, `day(2027, 9, 12)`; `b` = EG up/r61, `day(2027, 3, 14)`; `e` = EG up/r1;
    - `y1` = `osce:elections/r26`, `institution=None`, `head_of_state`, `year(2027)`,
      "Presidential Election"; `y2` = `wikipedia:national-2027@rev3/Unknown_date/li[1]`, the same
      fields, "President";
    - `g` = `ndi:p0/upcoming-c7` `**UMB`, `year(2026)`;
    - `ya` = `osce:elections/r24`, `year(2027)`, `round=1`; `yb` =
      `wikipedia:national-2027@rev3/Unknown_date/li[1]`, `year(2027)`; `yc` =
      `ndi:p0/upcoming-c3`, `year(2027)`, `round=2`.

    | claims | expected |
    |---|---|
    | y | `U[y]` |
    | a y | `{a +y} A` |
    | a b y | `{a} A`, `{b} A`; `U[y] poss {a} {b}` |
    | y1 y2 | `U[y1 y2]` |
    | g | `U[g]` |
    | e g | `{e} A`; `U[g]` (a year-only umbrella never attaches, and has no candidates) |
    | ya yb yc | `U[ya]`, `U[yb]`, `U[yc]` (an incomplete group splits) |
  - **`test_match_fails_closed`:**
    - `match([mk("osce:elections/r1"), mk("osce:elections/r1")], NOW)` raises
      `MergeError("duplicate merge_id: served/osce:elections/r1#0")`;
    - `match([mk("xyz:p/r1")], NOW)` raises `MergeError("unknown source: xyz")`;
    - `match([mk("osce:elections/r1")], datetime(2026, 10, 19))` raises
      `ValueError("now must be timezone-aware")`.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/merge/test_match.py -q`. Expected:
  FAIL (no module).
- [ ] **Step 3: Implement** `match.py`.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(merge): matching (phases A-D, umbrellas, aggregates, possible matches)`.

  Mutations, one each:
  - an incomplete component becomes one contest;
  - an ambiguous contest gets no neighbours;
  - Phase B never relaxes an `unknown` jurisdiction;
  - Phase B relaxes every jurisdiction;
  - Phase B compares only the first member;
  - month disagreement relaxes the jurisdiction;
  - month disagreement skips the year check;
  - month disagreement leaves `date_conflict` False;
  - a year-only weak claim with one candidate goes to the undated pool;
  - Phase B attaches each proposal on its own (no set check: `a w1 w2`);
  - the set check skips rule F (`a f1 f2`);
  - the set check skips the qualified numbers (`ua d1 d2`);
  - a conflicting year-only proposal becomes a pending item (`a w1 wy`);
  - observations are matched before the sessions;
  - Phase C contests count as observation candidates;
  - C7 skips rule F;
  - C7 accepts ambiguous contests;
  - C7 ignores the attached claims (`g1 h r2`);
  - C7 proposals are not checked as a set (`i g1 g2`);
  - sessions are never dissolved;
  - Phase D has no twin rule;
  - Phase D skips the shared-year check;
  - Phase D compares with the contest's span when there is a twin (`e nmo pnm`);
  - a year-precision `p` with a twin is never a change (`e pey`, `e pe27`);
  - `less_precise` sets `date_conflict` (`e pey`);
  - a `less_precise` change overwrites `moved` (`e o pe22 psy`);
  - Phase D sets no `status_conflict` when `p` has no status word and the contest has one;
  - Phase D's word ignores `rescheduled` (`res presch`);
  - a `held` `p` sets `status_conflict` on a contest with no word (`e peh`);
  - `umbrella_fits` accepts a referendum contest for any umbrella;
  - `umbrella_fits` skips the jurisdiction scope (`cz ul`);
  - `umbrella_fits` skips the office scope (`p2 pl`, `cz ma ul`);
  - `umbrella_fits` links a `general` umbrella of `unknown` level (`gb p2 uU`, `gv lg sc`);
  - `umbrella_fits` skips the level;
  - `umbrella_fits` skips the round;
  - `umbrella_covers` skips the qualified numbers (`c40 lg12`, `c40 ug12`);
  - `umbrella_covers` compares the qualified numbers with the members only (`a0 w40 ug12`);
  - the aggregate edge drops the unrecognised-label rule (`ca sc`, `ll lnU lo`);
  - the twin rule gives `less_precise` for any span that contains the served one (revision 2's
    rule: `e per`);
  - the twin rule gives no change for any span inside the served one (`er pes`);
  - each loose umbrella becomes its own aggregate (no clustering);
  - near dates link at 8 days;
  - event copies include IPU;
  - event copies inside one contest set no `date_conflict`;
  - the rescheduling hint is off.

---

### Task 5: Children, cards, listings, attention items and dispositions (`cards.py`; P75–P77, P79, P81, P82; G02, G04, G07; R2-01, D4)

**Files:**
- Create: `elections_calendar/merge/cards.py`
- Test: `tests/merge/test_cards.py`

**Interfaces:**
- Consumes: Task 1's records; Task 2's `claim_order`, `short_id`, `SOURCE_ORDER`; Task 3's
  `StatusResult`; Task 4's `Matching`, `Contest`, `contest_level`, `contest_round`;
  `offices.extract_round`;
  `text.norm_name`, `collapse_ws`; `places.PlaceRegistry`; `window.Window`.
- Produces:

```python
CLASS_ORDER: tuple[str, ...] = ("head_of_state", "lower_house", "upper_house", "legislature",
                                "governor", "mayor", "local_council", "referendum", "general")
PLURAL: Mapping[str, str] = {"head_of_state": "Presidents", "lower_house": "Lower houses",
                             "upper_house": "Upper houses", "legislature": "Legislatures",
                             "governor": "Governors", "mayor": "Mayors",
                             "local_council": "Local councils", "referendum": "Referendums",
                             "general": "Elections"}
def display_label(child: Child) -> str
def card_type(children: Sequence[Child]) -> str
def relevance_of(claim: Claim, window: Window) -> Relevance
def build(matching: Matching, *, window: Window, places: PlaceRegistry) -> MergeResult
```

**Rules:**
- **Display names** (P79): a place in the registry shows `(place.display, place.country_code)`.
  Any other place shows the `place_raw` of the first claim in `claim_order` among the claims it
  is built from, with `country_code` None.
- **A child**, one per contest (§5.3):
  - **The label claim** is the first in `claim_order` among the direct claims that are not
    observations, and (unless the contest's origin is `aggregate`) not `aggregate`. When there is
    none, it is the first of all the direct claims. It gives `office_label`, `office_class` and
    `kind`.
  - **The identity claims** are the direct claims that are not observations:
    - `level` is `contest_level`, and `round` is `contest_round`;
    - `institution` is the one non-None institution among them, else None;
    - `jurisdiction` and `jurisdiction_kind` come from the first of them in `claim_order` whose
      kind is not `unknown`, else `(None, "unknown")`;
    - `indirect` is True when any of them is;
    - `occurrence_confirmed` is True when `status.resolved` is neither `cancelled` nor
      `postponed`, and one of them has `status_claim == "held"` and is `dates_compatible` with the
      selected claim (P75, R2-01). A fallback `held` claim counts (D4): that the vote took place
      does not expire, and its `ChildSource` keeps its `fetched_at` and `fallback`;
    - `rescheduled_from`: when `status.rescheduled`, the sorted, distinct
      `collapse_ws(previous_date_text)` of those that have one; otherwise `()` (D2).
  - **From the contest:**
    - `aggregate` is `origin == "aggregate"`;
    - `span`, `date_meaning` and `date_status` come from the selected claim, and `status` from
      `status.status`;
    - `date_conflict`, `status_conflict`, `ambiguous` and `provisional_date` are the contest's,
      and `unverified` is the selection's;
    - `possible_matches` are the sorted `child_id`s of `contest.possible`.
  - **`sources`:** the direct claims in `claim_order`, each as
    `ChildSource(claim, reason is None, reason)` with its selection reason. Then the provisional
    claims in `claim_order`, each as `ChildSource(claim, False, "provisional")`.
- **Cards** (§5.4):
  - **The key** is (`place_id`, `level`, `span.start.isoformat()`, `span.end.isoformat()`,
    `span.precision`, `date_meaning`, `date_status`, `status`) of a child. Children with one key
    share a card, and `group_id = short_id(["|".join(key)])`.
  - **The children** are sorted by (`CLASS_ORDER.index(office_class)`,
    `norm_name(jurisdiction or "")`, `child_id`).
  - The card's `country` and `country_code` come from the display names, over the children's
    direct claims. `type = card_type(children)`.
  - **`umbrellas`:** the claims of the links that name any of the card's contests, in
    `claim_order`. A link may cover only some of a card's children; the disposition records which
    (P79). Plan 5 shows the coverage per child (R25).
  - **The bibliography.** `sources` walks the children in order, through each child's
    non-provisional sources, then the umbrellas. `umbrella_sources` walks only the umbrellas. In
    each walk, a source's first link wins, and the entries are emitted in `SOURCE_ORDER`.
  - Cards are sorted by (`span.start`, `place_id`, `group_id`).
- **Undated listings** (§5.5), one per `Undated`:
  - `undated_id = short_id(["undated", *merge_ids])`;
  - `place_id`, `country`, `office_label` and `year` come from its first claim in `claim_order`;
  - `claims` are in `claim_order`, and `sources` is their bibliography;
  - `possible_matches` are the sorted `child_id`s;
  - listings are sorted by `undated_id`.
- **Attention items** (§5.5):
  - **One per pending item:**
    - `item_id = short_id([kind, claim.merge_id])`;
    - `kind` and `reason` are the pending item's;
    - `source`, `link` and `snapshot_id` are the claim's;
    - `merge_ids = (claim.merge_id,)`, and `possible_matches` are the candidates' sorted
      `child_id`s;
    - `text = "<country>: <office_label> (<date_text>)"`. A `provisional_change` item adds
      ", from an incomplete fetch".
  - **One per listing:**
    - `kind="undated_listing"`, `reason="undated"`;
    - `item_id = short_id(["undated_listing", undated_id])`, and `undated_id` is set;
    - `source`, `link` and `snapshot_id` are its first claim's;
    - `merge_ids` are the sorted merge ids, and `possible_matches` are the listing's;
    - `text = "<country>: <office_label> (<year>), date not given"`.
  - **Every text** goes through `collapse_ws`, then is cut to its first `MAX_ATTENTION_TEXT`
    characters.
  - **Relevance** (P77, G07): an item is `in_or_after_window` when `relevance_of` gives that for
    any of its claims, and `before_window` otherwise. Its candidates never count.
  - `relevance_of(claim, window)`: a year-precision claim is `in_or_after_window` when
    `span.year >= window.start.year`. Any other claim is when `span.end >= window.start`.
    Otherwise `before_window`.
  - Items are sorted by `item_id`.
- **Dispositions** (§10.8, P79), one per input claim, sorted by `merge_id`:

  | claim | kind | targets |
  |---|---|---|
  | a member of an `anchor` contest | `anchor_member` | its child |
  | a member of a `standalone` or `aggregate` contest | `standalone` | its child |
  | an attached claim | `attached` | its child |
  | a provisional claim of a contest | `provisional` | its child |
  | a linked umbrella | `umbrella_link` | the sorted `child_id`s of the contests it fits (G02) |
  | an undated claim | `undated` | its listing |
  | a pending claim | `attention` | its item |
- **`display_label`** (P76):
  - Start from `office_label`.
  - When `round` is stated and `extract_round(label)[0]` is None, add `" (1st round)"`,
    `" (2nd round)"`, `" (3rd round)"`, or `" (<n>th round)"` for any other `n`.
  - Then, when `jurisdiction_kind` is `named` or `subdivision`, the jurisdiction is not empty,
    and `norm_name(jurisdiction)` is not inside `norm_name(label)`, prefix `"<jurisdiction>: "`.
- **`card_type`** (P76):

```python
def card_type(children):
    if len(children) == 1:
        text = display_label(children[0])
        return text if len(text) <= MAX_TYPE else text[: MAX_TYPE - 1] + "…"
    classes = {c.office_class for c in children}
    named = all(c.jurisdiction_kind in ("named", "subdivision") and c.jurisdiction for c in children)
    if len(classes) == 1 and named and len({norm_name(c.jurisdiction) for c in children}) == len(children):
        items = [c.jurisdiction for c in children]
        sep = "; " if any("," in item for item in items) else ", "
        def render(n):
            more = len(items) - n
            return (f"{PLURAL[next(iter(classes))]}: {sep.join(items[:n])}"
                    f"{f' (+{more} more)' if more else ''} ({len(children)})")
    else:
        items = [display_label(c) for c in children]
        def render(n):
            more = len(items) - n
            return " · ".join(items[:n]) + (f" (+{more} more)" if more else "")
    for n in range(len(items), 0, -1):
        if len(render(n)) <= MAX_TYPE:
            return render(n)
    return render(1)[: MAX_TYPE - 1] + "…"
```

- [ ] **Step 1: Write the failing tests** in `tests/merge/test_cards.py`.
  - **Helpers:** `result(*claims) = build(match(list(claims), NOW), window=window_for(NOW), places=PlaceRegistry.load())`.
    The presets come from `test_match.py`; move them into `tests/support/claims.py` if both
    modules need them.
  - **`test_display_label`** (P76). Each row is the child of `result(mk("electionguide:upcoming/r1"))` with these fields changed (`dataclasses.replace`):

    | office_label | round | jurisdiction, kind | display label |
    |---|---|---|---|
    | "Brazilian Presidency" | 2 | None, nationwide | "Brazilian Presidency (2nd round)" |
    | "President (2nd round)" | 2 | None, nationwide | "President (2nd round)" |
    | "Senate" | 1 | None, nationwide | "Senate (1st round)" |
    | "Senate" | 3 | None, nationwide | "Senate (3rd round)" |
    | "Senate" | 4 | None, nationwide | "Senate (4th round)" |
    | "House of Commons by-election" | None | "Holborn and St Pancras", named | "Holborn and St Pancras: House of Commons by-election" |
    | "Holborn and St Pancras by-election" | None | "Holborn and St Pancras", named | "Holborn and St Pancras by-election" |
    | "Governor" | 2 | "Bahia", subdivision | "Bahia: Governor (2nd round)" |
    | "Mayor" | None | "Hamilton", unknown | "Mayor" |
  - **`test_child_fields`** (§5.3, P76, P79):
    1. **Brazil, round 2.** The claims:
       - `a` = EG up/r3 `**BR`, `institution="iso:BR/president"`, `head_of_state`,
         "Brazilian Presidency", `round=2`, 10-25, `confirmed`, link `https://eg.test/3`;
       - `b` = WPn `October/li[6]/li[3]`, the same institution and class, "President (2nd round)",
         `round=2`, 10-25, `indirect=True`, link `https://wp.test/n`;
       - `u` = `aweb:calendar/r27` `**BR, **UMB`, `round=2`, 10-25, link `https://aweb.test/27`;
       - `o` = `mk("carter:observed/r1", **OBS, place_id="iso:BR", span=month(2026, 10), link="https://carter.test/1")`.

       Expected: one card, `4b35f9d2401c`, with one child, `8e4a9a33e280`:
       - `office_label` "Brazilian Presidency", `head_of_state`, `candidate_election`, `national`,
         `round` 2, `institution` "iso:BR/president", jurisdiction None `nationwide`;
       - `indirect` True, `occurrence_confirmed` False, `confirmed`, `voting_period`;
       - `sources`: `a` selected, `b` `less_certain`, `o` `observation`;
       - the card's `sources`: (electionguide, `https://eg.test/3`), (wikipedia, `https://wp.test/n`),
         (aweb, `https://aweb.test/27`), (carter, `https://carter.test/1`);
       - `umbrella_sources`: (aweb, `https://aweb.test/27`). `umbrellas` is `(u,)`. The type is
         "Brazilian Presidency (2nd round)".
    2. **Holborn, two sources.** `w` = WPl `October/li[3]/li[2]` `**GB` with "Holborn and St Pancras"
       `named`, `day(2026, 10, 8)`, link `https://wp.test/l`; `e` = EG past/r9 with the same
       fields, "Holborn and St Pancras by-election", `status_claim="held"`, link
       `https://eg.test/9`. Expected: card `cc453aae6835`, child `083a130d3044`; `office_label`
       "Holborn and St Pancras by-election"; `occurrence_confirmed` True; status `Held`; the type
       is "Holborn and St Pancras by-election" (the label names the jurisdiction).
    3. **`w` alone:** child `1d3694a58ae8`, type
       "Holborn and St Pancras: House of Commons by-election".
    4. **R4, IPU only.** `mk("ipu:elections/r9", **RENEW, place_id="iso:LY", institution="iso:LY/house-of-representatives", office_class="lower_house", office_label="House of Representatives", span=month(2026, 12))`.
       Expected: `tentative`, `expected_window`, `Upcoming`. The card key is ("iso:LY",
       "national", "2026-12-01", "2026-12-31", "month", "expected_window", "tentative",
       "Upcoming").
    5. **An aggregate child:** Task 4's Slovenia claims `ll ln lo`. Expected: `aggregate` True;
       "Local Elections"; `general`; `aggregate` kind; `subnational`; sources `lo` selected, `ll`
       `lower_priority`, `ln` `not_covering`.
    6. **The C7 label:** Task 4's Grenada `i w`. The label is "House of Representatives", from `i`,
       although `w` is selected; `aggregate` False.
    7. **A provisional source:** `e` = EG up/r1 and `ps` = Task 4's provisional OSCE claim with
       link `https://osce.test/p`. Expected: `sources` are `e` selected and
       `ps` (`selected` False, `"provisional"`); `date_conflict` True; `provisional_date`
       "moved"; the card's `sources` is only (electionguide, `https://example.test/e`).
    8. **The umbrella walk:** `r` = WPn `November/li[1]` with link `https://wp.test/n`; `u` = WPl
       `November/li[2]` `**UMB` with link `https://wp.test/l`. Expected: the card's `sources` is
       (wikipedia, `https://wp.test/n`), and `umbrella_sources` is (wikipedia, `https://wp.test/l`).
    9. **A rescheduling (D2):** Task 4's `res` → card `5a94ef2ae3fe`, child `e3ee8e8e7dce`:
       `Upcoming`, `rescheduled_from` ("1 November 2026",), `status_conflict` False,
       `occurrence_confirmed` False. With `ro` = `osce:elections/r1`, `postponed`,
       `previous_date_text="1  November 2026"` (two spaces): child `02bc80fb0ffd`,
       `rescheduled_from` ("1 November 2026",). With `ro8` = `ro` with "8 November 2026":
       ("1 November 2026", "8 November 2026").
    10. **A cancellation and a cached `held` (D1, G04).** `canc` = `osce:elections/r1`,
        `status_claim="cancelled"`, `day(2026, 9, 13)`; `hfb` = EG past/r1, `held`, 9-13,
        `fallback=True`, fetched 2026-09-01:
        - `canc hfb` → card `592ecabeb549`, child `4c9b2569520e`: `Cancelled`, `status_conflict`
          False, `occurrence_confirmed` False (a `held` claim does not confirm a cancelled
          election);
        - `canc` with `hld` = EG past/r1, `held`, 9-13 (the defaults: not fallback) → card
          `4d7199437e03`, the same child: `Held`, `status_conflict` True, `occurrence_confirmed`
          True.
    11. **A cached `held` claim alone (D4):** `hfb` of row 10 → card `4d7199437e03`, child
        `436692e1eac7`: `Held`, `occurrence_confirmed` True (a cached claim still confirms the
        vote), `unverified` True (nothing fresh supports its date), `status_conflict` False; its
        source keeps `fallback` True and `fetched_at` 2026-09-01.
    12. **A `held` claim for another month beside a cancellation (R2-01):** Task 4's `ac hO` →
        card `fca7f03c19fd`, child `12986edb4195`: `Cancelled`, `occurrence_confirmed` False,
        `date_conflict` True, `status_conflict` True; sources `ac` selected, `hO` `not_covering`.
    13. **The same without the cancellation:** Task 4's `a` with `hO` → card `2dc6c54b64ad`, child
        `12986edb4195`: `Upcoming` (15 November), `occurrence_confirmed` False (the `held` claim
        gives October, not the selected day), `date_conflict` True, `status_conflict` False.
  - **`test_a_rescheduled_child_follows_its_new_date`** (R2-01, D2). Task 4's `a mR`, built at
    three times with `build(match(claims, now), window=window_for(now), places=PlaceRegistry.load())`:

    | `now` (12:00 UTC) | card | the child `12986edb4195` |
    |---|---|---|
    | 2026-11-10 (before the old date) | `d8b9f8d1f6a1` | span `month(2026, 12)`, `Upcoming`, `rescheduled_from` ("15 November 2026",), `date_conflict` True, `status_conflict` False, `occurrence_confirmed` False; sources `mR` selected, `a` `old_date` |
    | 2026-11-20 (between the old and the new date) | `d8b9f8d1f6a1` | the same: never `Held` on the abandoned day |
    | 2027-01-05 (after the new date) | `7c1e513c7a94` | the same, but `Held`: past, and unconfirmed (no `held` claim) |
  - **`test_card_type`** (P76; the type of the one card each case gives). Presets: `GOV` =
    `dict(**BR, institution=None, office_class="governor", office_label="Governor", level="subnational", jurisdiction_kind="subdivision", span=day(2026, 10, 4))`,
    and `CA` = `dict(place_id="iso:CA", place_raw="Canada", institution=None, office_class="mayor", office_label="Mayor", level="subnational", jurisdiction_kind="named", span=day(2026, 10, 26))`.
    The unit ids are WPl `October/li[1]/li[1]/li[<i>]` for `GOV` and WPl `October/li[7]/li[<i>]`
    for `CA`, numbered from 1.

    | claims | type |
    |---|---|
    | `GOV` with "Bahia", "Alagoas", "Amazonas" | "Governors: Alagoas, Amazonas, Bahia (3)" |
    | `GOV` with "State number 01 with a long name" … "State number 30 with a long name" | "Governors: State number 01 with a long name, State number 02 with a long name, State number 03 with a long name, State number 04 with a long name, State number 05 with a long name (+25 more) (30)" (195 characters) |
    | `CA` with "Ontario, Hamilton", "Ontario, Ottawa" | "Mayors: Ontario, Hamilton; Ontario, Ottawa (2)" |
    | `CA` "Hamilton"; `CA` "Hamilton" with `local_council`, "City council" | "Hamilton: Mayor · Hamilton: City council" |
    | `CA` "Hamilton"; `ndi:p0/upcoming-c3` `**CA` with "Hamilton" and `jurisdiction_kind="unknown"` | "Mayor · Hamilton: Mayor" |
    | `CA` with `jurisdiction_kind="unknown"` and `office_label="Election of the " + "very " * 50 + "long council"` | its first 199 characters + "…" (200 characters) |
    | 11 × `CA` with `jurisdiction_kind="unknown"`, `local_council`, "Council number 01 of the region" … "11"; then WPl `October/li[8]` `**CA` with `jurisdiction_kind="unknown"` | "Mayor · Council number 05 of the region · Council number 01 of the region · Council number 07 of the region · Council number 03 of the region · Council number 06 of the region (+6 more)" (185 characters) |
    | Task 4's `x1 x2` | "Mayor · Mayor" |
    | Task 4's `h r` | "Lower houses: Holborn and St Pancras, Runcorn and Helsby (2)" |
  - **`test_cards_split_by_certainty_and_meaning`** (S3-T18):
    - EG up/r1 `confirmed`, with WPn `November/li[4]` (`institution="iso:SE/x"`,
      `head_of_state`, "President") → two cards: `ad1a3d3732e2` ("Riksdag", `confirmed`) and
      `5a94ef2ae3fe` ("President", `unknown`);
    - EG up/r1, with `aweb:calendar/r1` (`institution="iso:SE/x"`, `head_of_state`, "President",
      `date_meaning="unknown"`) → two cards: `47c3a41c029d` ("President", meaning `unknown`) and
      `5a94ef2ae3fe` ("Riksdag").
  - **`test_child_identity_through_split_and_rejoin`** (S3-T19). With `BRD = dict(place_id="iso:BR", span=day(2026, 10, 4))`:
    - `A` = EG past/r4 `**BRD`, `institution="iso:BR/president"`, `head_of_state`, "Presidency";
    - `B1` = EG past/r7 `**BRD`, `institution="iso:BR/chamber"`, `lower_house`, "Chamber";
    - `B2` = `B1` with `span=day(2026, 10, 11)`.

    | run | cards: (group_id, child ids, type) |
    |---|---|
    | A, B1 | (`5ddc43ed3758`, [`6d12862ffe3c`, `7455554d41e3`], "Presidency · Chamber") |
    | A, B2 | (`5ddc43ed3758`, [`6d12862ffe3c`], "Presidency"), (`a6dd778a0f69`, [`7455554d41e3`], "Chamber") |
    | A, B1 again | equal to the first run |
  - **`test_relevance_of`** (P77; the window is `window_for(NOW)`, 2026-09-01 to 2027-01-31):

    | span | relevance |
    |---|---|
    | `day(2026, 8, 31)` | before_window |
    | `day(2026, 9, 1)` | in_or_after_window |
    | `months(2026, 8, 2026, 9)` | in_or_after_window |
    | `month(2026, 8)` | before_window |
    | `day(2027, 5, 1)` | in_or_after_window |
    | `year(2026)` | in_or_after_window |
    | `year(2025)` | before_window |
  - **`test_attention_items`** (V2-T01 and V2-T02, merge part; R8; P79):
    - **`y` of Task 4's `test_year_only_claims`, alone:**
      - one listing, `5e735b978230`: `iso:SE`, "Sweden", "Parliamentary Elections", 2027, `(y,)`,
        sources (osce, `https://example.test/e`), no possible matches;
      - one item, `fb4c9d1c4882`: `undated_listing`, `undated`, `in_or_after_window`,
        "Sweden: Parliamentary Elections (2027), date not given",
        `merge_ids` ("served/osce:elections/r24#0",), `undated_id` "5e735b978230";
      - the disposition is `undated` → ("5e735b978230",).
    - **Task 4's `h r w`:** item `c43265173fa1`, `unresolved_evidence`, `several_candidates`,
      `in_or_after_window`, "United Kingdom: House of Commons by-election (15 November 2026)",
      possible matches (`605682096ffe`, `e70aa2e8fc49`).
    - **Task 4's `e po`:** item `6d7737459737`, `provisional_change`, `no_candidate`,
      "Sweden: President (15 November 2026), from an incomplete fetch".
    - **Task 4's `ag e`:** item `c0b91467ada1`, `provisional_aggregate`, possible matches
      (`605682096ffe`,), "Sweden: General elections (15 November 2026), from an incomplete fetch".
      With `agNO` alone: the same `item_id`, no possible matches,
      "Norway: General elections (15 November 2026), from an incomplete fetch".
    - **Task 4's `a w1 w2`** (P82): items `fb5d5d211420` (`w1`) and `82d1189a7079` (`w2`), both
      `unresolved_evidence`, `conflicting_claims`, `in_or_after_window`,
      "Brazil: President (November 2026)", possible matches (`12986edb4195`,); both claims have
      the disposition `attention`.
    - **A long label:** `mk("carter:observed/r1", **{**OBS, "office_label": "Mission   " + "x" * 400}, span=month(2026, 12))`
      → `text` is 300 characters and starts "Sweden: Mission x".
    - **Two items** come out sorted by `item_id`.
  - **`test_year_only_observation_stays_accounted_for`** (R6, P77, G07). `y25` =
    `mk("eeas:missions/r2c1", **OBS, place_id="iso:NO", span=year(2025), date_text="2025")`:
    - Task 4's `ey` with `y25` → items `ff7c82d7217d` (`no_candidate`, `in_or_after_window`,
      "Sweden: Election observation mission (2026)") and `ed745bd6cbe3` (`no_candidate`,
      `before_window`, "Norway: Election observation mission (2025)");
    - Task 4's `eyCO lo50 up51` → item `ff7c82d7217d`, `several_candidates`, `in_or_after_window`
      (its own year is the window's, although both candidates are in March), possible matches
      (`a0ff75f39c29`, `def863669d34`), "Colombia: Election observation mission (2026)";
    - `lo50`, `mk("electionguide:upcoming/r51", **UPPER, span=day(2026, 11, 22))` and `eyCO` →
      `in_or_after_window`, possible matches (`a0ff75f39c29`, `c908a5427792`);
    - `hist` = `mk("carter:observed/r2", **OBS, span=month(2026, 3), date_text="March 2026")`
      alone → item `3555993a0822`, `no_candidate`, `before_window`,
      "Sweden: Election observation mission (March 2026)" (a dated past mission);
    - in each case every claim has exactly one disposition.
  - **`test_unknown_place_shows_its_raw_name`** (P79):
    - `mk("electionguide:upcoming/r1", place_id="x:atlantis", place_raw="Atlantis")` with
      `mk("carter:observed/r1", **OBS, place_id="x:atlantis", place_raw="Atlantis", span=month(2026, 12))`:
      - card `770bb0b91a94`: `country` "Atlantis", `country_code` None;
      - item `39e8c2860ac1`: "Atlantis: Election observation mission (15 November 2026)";
    - Task 4's `s1 s2` (a registered `x:` place) → `country` "South Ossetia", `country_code` None;
    - EG up/r1 → "Sweden", "SE".
  - **`test_dispositions`** (P79, G02):
    - Task 4's `ms nN pz r` → `nN` has one `umbrella_link` disposition, with targets
      (`605682096ffe`, `e70aa2e8fc49`): two children on two cards (`5a94ef2ae3fe` and
      `ad1a3d3732e2`), and never the mayor;
    - Task 4's `ma mc u` → `u` → `umbrella_link` (`35bd1312dc95`, `e8c2e0c4e454`): two children
      of one card give two targets;
    - Task 4's `gb p1 p2 rf u` → `u` → `umbrella_link` (`84c968bd489c`,). Its card `862446e7b7ab`
      also holds the referendum child `88e61e82732a`, which the umbrella does not cover; the card's
      `umbrellas` is still `(u,)`;
    - each kind of disposition comes from the source shown in its table row: `anchor_member`
      (Task 4's `e1 o`), `standalone` (`x1 x2`, and the aggregate `ll ln lo`), `attached` (`o`),
      `provisional` (`e pe`), `undated` (`y` of `test_year_only_claims`) and `attention` (`oNO`);
    - the dispositions are sorted by `merge_id`.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/merge/test_cards.py -q`. Expected:
  FAIL (no module).
- [ ] **Step 3: Implement** `cards.py`.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(merge): children, cards, undated listings, attention items and dispositions`.

  Mutations, one each:
  - the label claim may be an aggregate claim;
  - `child_id` hashes every direct claim;
  - every round gets "th";
  - the prefix is added even when the label names the jurisdiction;
  - the card key leaves out `date_status`;
  - the card key leaves out `date_meaning`;
  - children are sorted by `child_id` only;
  - the plural form is used for two classes;
  - the separator is ", " even with commas;
  - the type limit leaves out the suffix;
  - the bibliography includes provisional claims;
  - the bibliography walks the umbrellas first;
  - an observation item with candidates takes its relevance from them (revision 1's P77:
    `eyCO lo50 up51`);
  - `relevance_of` compares `span.start`;
  - the listing text drops ", date not given";
  - the provisional text drops ", from an incomplete fetch";
  - the text cap becomes 301;
  - `umbrella_link` targets are the cards' `group_id`s (`ma mc u`, `ms nN pz r`);
  - an unknown place shows its `place_id`;
  - `occurrence_confirmed` counts observations;
  - `occurrence_confirmed` ignores a resolved cancellation (row 10);
  - `occurrence_confirmed` counts only fresh `held` claims (row 11);
  - `occurrence_confirmed` ignores the `held` claim's date (row 13);
  - an opposing `held` claim overrides whatever its date, in `select.py` (row 12);
  - the child's span comes from the label claim, not the selected claim
    (`test_a_rescheduled_child_follows_its_new_date`);
  - `rescheduled_from` is not made distinct (row 9, `ro`);
  - `rescheduled_from` skips `collapse_ws` (row 9, `ro`);
  - `provisional_date` is not copied to the child (row 7).

---

### Task 6: The conservation audit and `merge()` (`conservation.py`, `merge/__init__.py`; §10.8, §10.9, P79; R2-04, R2-05)

**Files:**
- Create: `elections_calendar/merge/conservation.py`
- Modify: `elections_calendar/merge/__init__.py` (add `merge`)
- Test: `tests/merge/test_conservation.py`, `tests/merge/test_merge.py`

**Interfaces:**
- Consumes: Tasks 1–5 (`match.umbrella_covers` among them); `window.window_for`;
  `places.PlaceRegistry`.
- Produces:

```python
def check(claims: Sequence[Claim], result: MergeResult) -> tuple[str, ...]      # conservation.py
def merge(claims: Sequence[Claim], *, now: datetime,
          places: PlaceRegistry) -> MergeResult                                  # merge/__init__.py
```

  `elections_calendar/merge/__init__.py` exports `MergeError` and `merge` (`__all__`).

**Rules:**
- **`check`** runs the checks below in this order. It returns their messages, each check's
  messages sorted. An empty tuple means the result is sound. A child's *provisional sources* are
  those with `rejected_reason == "provisional"`; the rest are its *member sources*. Its *joined
  claims* are the claims of its sources whose disposition is `anchor_member` or `standalone` with
  that child as its target (attached claims are left out).
  1. **Ids.** A `child_id` (over every card's children), `group_id`, `undated_id` or `item_id`
     that appears twice in its own list → `"duplicate id: <id>"`.
  2. **Dispositions.**
     - An input merge id with no disposition → `"no disposition: <merge_id>"`.
     - One with two or more → `"duplicate disposition: <merge_id>"`.
     - A disposition for a merge id that is not an input → `"unknown input: <merge_id>"`.
  3. **Targets.** Each target must exist: a child for `anchor_member`, `standalone`, `attached`,
     `provisional` and `umbrella_link`; a listing for `undated`; an item for `attention`. Otherwise
     `"dangling target: <merge_id> -> <target>"`.
  4. **Holders** (P79, G08). The claims the result holds are those of every child source, every
     card's `umbrellas` and every listing's `claims`. One whose merge id is not an input →
     `"unknown holder: <merge_id>"`. One that is not equal to its input (`!=`, every field) →
     `"changed claim: <merge_id>"`. An item's `merge_ids` entry that is not an input → `"unknown
     holder: <merge_id>"`. Each message appears once.
  5. **Placement.** The holders of a claim, counted with repeats, are:
     - a child whose member sources hold it (as a member);
     - a child whose provisional sources hold it (as a provisional claim);
     - a card whose `umbrellas` hold it;
     - a listing whose `claims` hold it;
     - an item, other than an `undated_listing` item, whose `merge_ids` hold it.

     For each input with exactly one disposition, the holders must be exactly what the disposition
     names:
     - its child, as a member for `anchor_member`, `standalone` and `attached`, and as a
       provisional claim for `provisional`;
     - for `umbrella_link`, each distinct card that holds one of its target children;
     - its listing, or its item.

     Otherwise `"misplaced: <merge_id>"`.
  6. **Coverage** (P79, R2-05). Here `covers(u, c)` is `umbrella_covers(u, <c's joined claims>,
     <c's member sources' claims>, c.span)`, with `u` the input claim of that merge id. Only
     children that are not `aggregate` are covered.
     - An `umbrella_link` disposition of an input `u` whose targets are not exactly the sorted
       `child_id`s of the non-aggregate children that `u` covers → `"wrong coverage: <merge_id>"`.
       A correct card is not enough: a link moved to another child of the same card, or one that
       lost or gained a child there, is caught here, not by placement.
     - A joined claim of an `aggregate` child that covers some non-aggregate child →
       `"wrong coverage: <merge_id>"` (it should have been a link).
  7. **Wrong merge** (P79, G08: role-aware identity). For each child, the dispositions say which of
     its member sources are joined and which are attached. Its *identity claims* are the member
     sources' claims that are not observations. In a child that is not `aggregate`, its *C7
     claims* are the identity claims of class `legislature` with `aggregate` True.
     - An observation or a provisional source whose `place_id` is not the child's →
       `"wrong merge: <child_id> holds <merge_id> from another place"`.
     - C7 claims beside an identity claim whose class is not in `CHAMBERS`, or whose kind is in
       `REFERENDA` → `"wrong merge: <child_id> has a legislature umbrella outside a chamber"`.
     - Each pair of identity claims (`a < b` by merge id) that fails
       `identity_compatible(a, b, relax_jurisdiction=True, ignore_kind=c7, ignore_institution=c7 or aggregate)`,
       where `c7` is True when either is a C7 claim, or fails `same_source_compatible` →
       `"wrong merge: <child_id>: <a> and <b>"`.
     - An `aggregate` child whose identity claims have two or more office classes →
       `"wrong merge: <child_id> has two office classes"`.
     - **Joined dates** (R2-04): each pair of joined claims (`a < b` by merge id) that is not
       `dates_compatible` → `"wrong merge: <child_id>: <a> and <b> have other dates"`. The child's
       `date_conflict` never excuses it; attached and provisional claims are not joined claims.
     - In a child without `date_conflict`, an attached claim that is not an observation and is not
       `dates_compatible` with every joined claim →
       `"wrong merge: <child_id>: <merge_id> has another date and no date_conflict"`.
  8. **Missed merge** (P79).
     - Two children of one place, neither `ambiguous` nor `aggregate`, are *partners* when all
       their joined claims together are pairwise `joinable` (Task 2).
     - Two children that are each other's only partner → `"missed merge: <A> and <B>"`, with
       `A < B`.
  9. **Possible matches.** Each `possible_matches` entry of a child, listing or item must be a
     `child_id`. Otherwise `"dangling possible match: <owner id> -> <id>"`.
- **`merge`:**
  - `window = window_for(now)`, `matching = match(claims, now)`,
    `result = build(matching, window=window, places=places)`;
  - `problems = check(claims, result)`. Any problem → `MergeError("conservation: " + "; ".join(problems))`;
  - it calls `match`, `build` and `check` through the names imported into
    `elections_calendar/merge/__init__.py`, so a test can monkeypatch them there.

- [ ] **Step 1: Write the failing tests.** `test_conservation.py` builds results with Task 5's
  `result(...)` helper. It changes them with `dataclasses.replace`, and calls `check`.
  - The presets come from `tests/support/claims.py`: move Task 4's presets there now if Task 5
    has not. Each named claim is rebuilt in this module from its Task 4 definition.
  - A helper, `with_claim(result, merge_id, claim)`, replaces the claim of the child source with
    that merge id (the merge id stays the same).
  - **`test_clean_results_pass_the_audit`:** `check` returns `()` for the results of these
    Task 4 rows:
    - `a b c d e` (S3-T5) of `test_phase_a_components`; `r1 r2 un m` of `test_rounds`;
    - `gb p1 p2 rf u`, `gb p2 uU` and `ms nN pz r` of `test_umbrella_links`; `cz ma u` of
      `test_umbrella_scope`;
    - `a w1 w2`, `i w`, `i g1 g2` and `g1 h r2` of `test_attachments_are_checked_together`;
    - `e pe22`, `e o pe22 psy` and `res` of `test_provisional_claims`; `a b y` of
      `test_year_only_claims`; `ll ln lo` of `test_unmatched_umbrellas_cluster`; `qa qa2 qb s` of
      `test_referendum_questions_and_sessions`;
    - `oCH qa s` and `oNO` of `test_observation_with_zero_one_and_several_candidates`;
    - **revision 3** (the new checks accept every correct result): `a mR` and `ac hO` of
      `test_month_disagreement` (an attachment on another date); `e per` and `er pes` of
      `test_provisional_claims` (a moved provisional claim); `c12 c40 ug12`, `a0 w40 ug12` and
      `ph1 ph2 up2` of `test_umbrella_scope`; `ll lnU lo` and `ca sc` of
      `test_unmatched_umbrellas_cluster`. With `gb p1 p2 rf u` and `ms nN pz r` above, correct
      links on one card and on two cards pass.
  - **`test_lost_and_duplicated_inputs_are_caught`** (S3-T15). In the result of `r1 r2 un`,
    replace `un`'s disposition with a copy whose `merge_id` is `r1`'s →
    `("duplicate disposition: served/electionguide:past/r4#0", "no disposition: served/wikipedia:national-2026@rev1/October/li[2]#0")`.
    The placement check skips both claims. An extra
    `Disposition("served/osce:elections/r99#0", "standalone", (<r2's child_id>,))` gives
    `("unknown input: served/osce:elections/r99#0",)`.
  - **`test_targets_and_placement`:**
    - In `e1 o`, `o`'s targets become `("000000000000",)` →
      `("dangling target: served/carter:observed/r1#0 -> 000000000000", "misplaced: served/carter:observed/r1#0")`.
    - Take `e1`, `b` = EG up/r2 (`institution="iso:SE/president"`, `head_of_state`,
      "President") and `w` = `mk("ndi:p0/upcoming-c1", span=month(2026, 11), date_status="tentative", date_meaning="unknown")`.
      `w` attaches to `e1`'s child. Point its disposition at `b`'s child →
      `("misplaced: served/ndi:p0/upcoming-c1#0",)`.
    - In `e pe`, `pe`'s disposition kind becomes `attached` →
      `("misplaced: provisional/electionguide:upcoming/r1#0",)`.
  - **`test_wrong_merge_is_caught`** (G08). Start from the one-child result of
    `a1` = `mk("electionguide:upcoming/r1", round=1)` and `x` = `mk("osce:elections/r1")`: child
    `8c6da6604ce3`. Each row replaces `x` with `nx`, and calls `check([a1, nx], with_claim(result,
    x.merge_id, nx))`, so the holder check sees no change. `PAIR` is
    `("wrong merge: 8c6da6604ce3: served/electionguide:upcoming/r1#0 and served/osce:elections/r1#0",)`.

    | `nx` | problems |
    |---|---|
    | `replace(x, office_class="head_of_state", institution=None)` | `PAIR` |
    | `replace(x, round=2)` | `PAIR` |
    | `replace(x, level="subnational")` | `PAIR` |
    | `replace(x, place_id="iso:NO", place_raw="Norway")` | `PAIR` |
    | `replace(x, institution="iso:SE/other")` | `PAIR` |
    | `replace(x, jurisdiction="Lima", jurisdiction_kind="named")` | `PAIR` |
    | `replace(x, kind="by_election")` | `PAIR` |
    | `replace(x, span=day(2026, 11, 16), date_text="16 November 2026")` | `("wrong merge: 8c6da6604ce3: served/electionguide:upcoming/r1#0 and served/osce:elections/r1#0 have other dates",)` (R2-04: two joined claims on disjoint days) |
    | `replace(x, office_label="District 12")` | `()` (one side states no district) |
    | `replace(x, **OBS)` | `()` (observations are checked for place only) |
    | `replace(x, **OBS, place_id="iso:NO")` | `("wrong merge: 8c6da6604ce3 holds served/osce:elections/r1#0 from another place",)` |

    In the same way:
    - **rule F:** `a1` with `xe` = EG up/r2, `round=1`, gives one child, `382710a03c5b`;
      `replace(xe, office_label="Other")` gives
      `("wrong merge: 382710a03c5b: served/electionguide:upcoming/r1#0 and served/electionguide:upcoming/r2#0",)`;
    - **C7 outside a chamber:** `h1` = EG up/r1 and `hx` = `osce:elections/r1`, both with
      `institution="iso:SE/president"`, `head_of_state` and "President", give child
      `8c6da6604ce3`; `replace(hx, **LEG)` gives
      `("wrong merge: 8c6da6604ce3 has a legislature umbrella outside a chamber",)` (revision 1
      gave `()`);
    - **an aggregate:** in the child of `ll ln lo`, `replace(ln, **LEG)` gives
      `("wrong merge: fd8b5b88f149 has two office classes",)`;
    - **an attached date:** `e1` with `w` = `mk("ndi:p0/upcoming-c1", span=month(2026, 11), date_status="tentative", date_meaning="unknown")`
      gives child `605682096ffe` with `w` attached; `replace(w, span=month(2026, 12))` gives
      `("wrong merge: 605682096ffe: served/ndi:p0/upcoming-c1#0 has another date and no date_conflict",)`.
      With the child's `date_conflict` also set to True: `()`.
  - **`test_changed_and_unknown_holders_are_caught`** (G08). The result of `a1 x`, checked
    against the original inputs `[a1, x]`:
    - `with_claim(result, x.merge_id, replace(x, place_raw="Sverige"))` →
      `("changed claim: served/osce:elections/r1#0",)`;
    - `with_claim(result, x.merge_id, replace(x, span=day(2026, 11, 16)))` →
      `("changed claim: served/osce:elections/r1#0", "wrong merge: 8c6da6604ce3: served/electionguide:upcoming/r1#0 and served/osce:elections/r1#0 have other dates")`
      (revision 3: the joined-dates check sees the changed copy too);
    - the child gains a source `ChildSource(mk("osce:elections/r99"), False, "lower_priority")` →
      `("unknown holder: served/osce:elections/r99#0",)`;
    - in the result of `oNO`, its item's `merge_ids` gain `"served/osce:elections/r99#0"` → the
      same.
  - **`test_umbrella_coverage_is_checked`** (R2-05, R2-03). Each case changes a correct result,
    keeps every holder equal to its input unless stated, and calls `check`:
    - **Brazil** (`gb p1 p2 rf u`): `u`'s link targets the presidency child `84c968bd489c`, on card
      `862446e7b7ab`, which also holds the referendum child `88e61e82732a`.
      - The disposition's targets become (`88e61e82732a`,), on the same card →
        `("wrong coverage: served/aweb:calendar/r27#0",)`. Placement still passes: the card is
        right, the child is not.
      - The targets become (`84c968bd489c`, `88e61e82732a`) → the same.
    - **Peru** (`ma mc u`): the targets (`35bd1312dc95`, `e8c2e0c4e454`), both on one card, lose
      `e8c2e0c4e454` → `("wrong coverage: served/ndi:p0/upcoming-c1#0",)`.
    - **Districts** (`c12 c40 ug12` of Task 4; R2-03): both children are on card `5a94ef2ae3fe`.
      `ug12`'s targets move from `c908a5427792` (District 12) to `ed407c6c0cee` (District 40) →
      `("wrong coverage: served/ndi:p0/upcoming-c12#0",)`.
    - **An aggregate that should have been a link** (`cz ul`): `ul`'s jurisdiction becomes
      "Cusco" in the inputs and in its child's source, so it now covers the Cusco mayor →
      `("wrong coverage: served/ndi:p0/upcoming-c3#0",)`.
  - **`test_missed_merge_is_caught`.** In the result of `e1` and
    `x16` = `mk("osce:elections/r1", span=day(2026, 11, 16))` (two children),
    `with_claim(result, x16.merge_id, replace(x16, span=day(2026, 11, 15)))` gives
    `("missed merge: <A> and <B>",)`, with the two child ids sorted.
  - **`test_ids_and_possible_matches`:**
    - in `oNO`, add a second copy of its item →
      `("duplicate id: <item_id>", "misplaced: served/carter:observed/r1#0")`;
    - in `e1`, the child's `possible_matches` become `("ffffffffffff",)` →
      `("dangling possible match: <child_id> -> ffffffffffff",)`.
  - **`test_merge.py`:**
    - **`test_merge_runs_the_audit`** (S3-T16). Monkeypatch `elections_calendar.merge.build` with
      a wrapper that drops the last disposition. `merge` then raises a `MergeError` whose message
      starts with `"conservation: no disposition: "`. Unpatched, `merge` on `gb p1 p2 rf u`
      returns exactly `build(match(claims, NOW), window=window_for(NOW), places=PLACES)`.
    - **`test_duplicate_merge_id_stops_the_merge`** (S3-T8):
      `merge([mk("osce:elections/r1"), mk("osce:elections/r1")], now=NOW, places=PLACES)` raises
      `MergeError("duplicate merge_id: served/osce:elections/r1#0")`.
    - **`test_naive_now_is_rejected`:** `now=datetime(2026, 10, 19)` raises
      `ValueError("now must be timezone-aware")`.
    - **`test_replay_is_idempotent`** (S3-T8): merging `gb p1 p2 rf u` twice gives equal results,
      with equal ids. The replayed-copy case is Task 4's `c1 c2`.
    - **`test_inputs_in_any_order_give_the_same_result`** (S3-T5, NM-T06, G03). Every
      permutation gives a `MergeResult` equal to the first, and a `match` result with the same
      `list_order`.
      - `list_order(matching)`, a helper in `tests/support/claims.py`, lists each contest's
        `child_id` with the merge ids of its `members`, `attached` and `provisional`, in list
        order, and the merge ids of each link, undated group and pending entry. (Task 4's
        notation helper, `shape`, is a different function and stays in `test_match.py`.)
      - The sets:
        - `a b c d e` (120 orders);
        - `r1 r2 un` (6);
        - `a w1 w2` of `test_attachments_are_checked_together` (6);
        - `gb p1 p2 rf u` plus `mk("carter:observed/r1", **OBS, **BR, span=month(2026, 10))`
          (720).
    - **`test_property_any_order_and_conservation`** (§10.9). With `@seed(20261019)` and
      `@settings(max_examples=400, deadline=None, suppress_health_check=[HealthCheck.too_slow])`,
      over `st.lists(claim_st, min_size=1, max_size=9)` and `st.randoms(use_true_random=False)`:
      - keep the first claim per `merge_id`;
      - `merge` does not raise, so the audit passes;
      - the dispositions' merge ids are exactly the inputs';
      - **the guard** (G08): when the result has a child, `with_claim` on the claim of its first
        card's first child's first source, with `place_raw + "x"`, makes `check` report
        `"changed claim: <merge_id>"`. An audit that has stopped looking fails here;
      - `merge` on a shuffled copy is equal.

      The prototype's run (`prop7.txt`, revision 3's rules; `prop6.txt` gave the same numbers):
      the body ran 420 times, with 472 children, 7 attached claims and the guard in 290 runs.

      The strategy:

```python
SOURCES = ("electionguide:upcoming/r", "osce:elections/r",
           "wikipedia:national-2026@rev1/November/li[", "ndi:p0/upcoming-c",
           "ipu:elections/r", "carter:observed/r", "eeas:missions/r")
OFFICES = (
    dict(institution="iso:SE/riksdag", office_class="legislature", office_label="Riksdag",
         aggregate=False, kind="candidate_election"),
    dict(institution=None, office_class="legislature", office_label="Parliament",
         aggregate=True, kind="candidate_election"),
    dict(institution=None, office_class="general", office_label="General elections",
         aggregate=True, kind="aggregate"),
    dict(institution=None, office_class="mayor", office_label="Mayor", aggregate=False,
         kind="candidate_election"),
    dict(institution=None, office_class="referendum", office_label="Referendum",
         aggregate=False, kind="referendum_day"),
)
SPANS = (day(2026, 11, 1), day(2026, 11, 2), day(2026, 11, 9), month(2026, 11), year(2026),
         day(2027, 1, 10))
claim_st = st.tuples(st.integers(0, len(SOURCES) - 1), st.integers(1, 4),
                     st.integers(0, len(OFFICES) - 1), st.integers(0, len(SPANS) - 1),
                     st.sampled_from([None, 1, 2]), st.sampled_from(["iso:SE", "iso:NO"]),
                     st.sampled_from(["nationwide", "named", "unknown"]), st.booleans(),
                     st.sampled_from([None, "cancelled", "held"]))
# build(t): the unit id is f"{prefix}{n}]" for the Wikipedia prefix and f"{prefix}{n}" otherwise;
# fields from OFFICES[o]; IPU adds RENEW; Carter and EEAS take OBS; jurisdiction "Lima" when
# the kind is "named"; span, round, place_id, provisional and status_claim from the tuple.
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/merge/test_conservation.py tests/merge/test_merge.py -q`.
  Expected: FAIL (no `check`, no `merge`).
- [ ] **Step 3: Implement** `conservation.py`, and `merge` in `elections_calendar/merge/__init__.py`.
- [ ] **Step 4: Run** the full suite. Expected: PASS. The property test takes a few seconds.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(merge): the conservation audit and merge()`.

  Mutations, one each:
  - wrong merge counts observations (kills `test_clean_results_pass_the_audit`, through `oCH qa s`);
  - `check` drops the duplicate-disposition test;
  - `check` drops the unknown-input test;
  - `check` drops the dangling-target test;
  - the holder check compares merge ids only (`changed claim` rows);
  - the holder check skips items (`oNO` row);
  - placement ignores the member/provisional distinction;
  - placement counts holders as a set;
  - placement expects an `umbrella_link`'s targets themselves as cards;
  - wrong merge skips rule F;
  - wrong merge counts legislature aggregates in every child;
  - wrong merge allows a C7 claim beside a non-chamber (the C7 row);
  - wrong merge checks observations' identity (the `**OBS` row);
  - wrong merge skips the place of observations (the `iso:NO` observation row);
  - wrong merge skips the attached date check;
  - the attached date check ignores `date_conflict`;
  - wrong merge skips the joined-dates check (the 16 November row);
  - the coverage check is off (the Brazil redirect);
  - coverage checks only that each target is covered (the Peru target dropped);
  - coverage checks only that each covered child is a target (the referendum added);
  - coverage skips the members of aggregate children (`cz ul`, Cusco);
  - the missed-merge check is off;
  - the possible-match check is off;
  - the id check is off;
  - `merge` does not call `check`;
  - `match` skips the duplicate check;
  - `short_id` mixes in `__import__("time").monotonic_ns()`, so a second merge gives other ids (kills
    `test_replay_is_idempotent`);
  - `merge` coerces a naive `now` with `now.replace(tzinfo=UTC)` before it calls `window_for`;
  - `match` drops step 0's sort, so the claims keep the input order (the `list_order` comparison
    kills it);
  - Phase B's set check keeps the first conflicting proposal in input order (the `a w1 w2`
    orders);
  - the holder check is off (both `test_changed_and_unknown_holders_are_caught` and the property
    test's guard fail);
  - Phase B drops a weak claim that has two or more candidates, with no pending entry (the property
    test's audit kills it).

---

### Task 7: The fixture merge end to end (`test_fixture_merge.py`; Appendix B, R4, R8, R13)

**Files:**
- Modify: `tests/merge/test_fixture_merge.py`

No source file changes. When a value differs, stop and report it, with a diff of your contests
against `.scratch/plan3/r6_report.txt` and `.scratch/plan3/r6_check6.txt`. They stay the
reference: revision 3 changes no fixture value (`check28.py`). Never change the expected value.

**Interfaces:**
- Consumes: `merge`, `match`, `fixture_claims`, `FIXTURE_NOW`, `PlaceRegistry`, `window_for`, and
  `list_order` from `tests/support/claims.py` (Task 6).
- Produces: `fixture_result()`, a test-module helper cached with `functools.cache`:
  `merge(fixture_claims(), now=FIXTURE_NOW, places=PlaceRegistry.load())`.

In this task, WPn and WPl are the fixture revisions `wikipedia:national-2026@rev1380221397` and
`wikipedia:local-2026@rev1380378807`. Every merge id is `served/` + the claim id shown.

- [ ] **Step 1: Write the tests.**
  - **`test_fixture_merge_counts`** (measured by `facts4_r6.py`, `facts6.py`, `window4_r6.py`,
    `report4_r6.py` and `check6_r6.py`):

    | quantity | value |
    |---|---|
    | cards | 742 |
    | children | 988: 397 targeted by `anchor_member` dispositions and 591 by `standalone` ones (150 of them `aggregate`); 0 `ambiguous` |
    | dispositions | 1335: `standalone` 602, `anchor_member` 557, `attached` 58, `umbrella_link` 47, `attention` 36, `undated` 35 |
    | attention items | 67: (`undated_listing`, `undated`, `in_or_after_window`) 31; (`unresolved_evidence`, `no_candidate`, `before_window`) 24; (`unresolved_evidence`, `several_candidates`, `before_window`) 7; (`unresolved_evidence`, `several_candidates`, `in_or_after_window`) 5; no `conflicting_claims` item |
    | the in-window evidence items (G07) | five EEAS 2026 missions, each "<country>: EU election observation mission (2026)": `ed745bd6cbe3` Colombia (`eeas:missions/r2c1#0`; possible matches `10b7dbe42fb7`, `45a7ab6234dd`, `862d26542ee0`, `be76457bc81c`); `36ad1dcad007` Peru (`r2c2#0`; `10bce39f7c6a`, `40c90cc9183c`, `be9c226b2d9a`, `fd914fc6ede2`); `c8534f5327a6` Bangladesh (`r3c1#0`; `37f6037fd15b`, `a8031995b7b2`, `d97dacc76861`); `b98546e8d6db` Zambia (`r3c2#0`; `3b43a9575bcc`, `964b76e3a20e`, `d3effb731ef3`); `612356b9548b` "Sao Tome and Principe" (`r4c1#0`; `2b76c271e7be`, `eb7084dbf7f1`) |
    | undated listings | 31: 27 with one claim, and 4 with two (`osce:elections/r24#0` to `r27#0`, each with a `wikipedia:national-2027@rev1379360216/Unknown_date/…` claim); none has possible matches |
    | flags | `date_conflict` 3 (Nigerian House of Representatives and Nigerian Senate, 2027-01-16; Cabo Verdean Presidency, 2026-11-15); `status_conflict` 0; `unverified` 0; `occurrence_confirmed` 197; no child has `rescheduled_from` or `provisional_date` |
    | possible matches | on 4 children: the two Kyrgyz presidency children (ElectionGuide 27 Jan, NDI 24 Jan 2027) and the two Cameroon National Assembly children, each naming the other |
    | umbrella links | 47, with 120 child targets. By target children: 1 child 15 links, 2 children 18, 3 children 9, 6 children 4, 18 children 1. By cards: 45 links to one card, 2 to two (`aweb:calendar/r3#0` and El Salvador's `ndi:p0/upcoming-c10#0`). By source: NDI 13, A-WEB 12, Wikipedia 11, OSCE 9, EISA 2. 4 (card, umbrella) pairs cover only part of the card |
    | statuses | Held 613, Upcoming 375 |
    | source reasons (all children) | None 988, `less_certain` 161, `lower_evidence` 33, `not_covering` 17, `lower_priority` 9, `observation` 5, `year_only` 3, `less_precise` 1 |
    | in the window | 100 cards (`window_for(FIXTURE_NOW).overlaps(card.span)`) with 202 children; Upcoming 59, Held 41; day 95, month 5 |
    | the longest type | 200 characters |
    | the largest card | `iso:US`, `subnational`, 2026-11-03: 59 children |
    | observations | 41: 36 `attention`, 5 `attached` |
    | year-precision claims | 61 |
  - **`test_appendix_b`** (spec Appendix B, field by field). Every card below has `day` precision
    and `voting_period`. The children are listed in card order, each with its selected claim
    first and then its other claims with their reasons:

    | Appendix B row | card: group_id; place, level, dates, date_status, status | type | children | umbrellas |
    |---|---|---|---|---|
    | 13 Sep, Sweden, Riksdag | `fcd48da30f32`; iso:SE, national, 09-13, confirmed, Held | "Swedish Parliament" | `451e4f4c0054`: EG past/r13; OSCE r34 (`less_certain`), WPn September/li[1] (`less_certain`) | — |
    | 13 Sep, Sweden, regional and municipal | `4f4a086286ed`; iso:SE, subnational, 09-13, unknown, Held | "regional and municipal elections" | `16b1e5c54480` (aggregate): WPl September/li[4]/li[2] | — |
    | 18 Sep, South Ossetia | `c7558bb61e25`; x:south-ossetia, national, 09-18, unknown, Held | "President" | `5f80a5eff1aa`: WPn September/li[2] | — |
    | 18–20 Sep, Russia | `0854d007f42e`; iso:RU, national, 09-18 to 09-20, confirmed, Held | "Russian State Duma" | `4856e73735ea`: EG past/r12; OSCE r33 (`not_covering`), WPn September/li[3] (`less_certain`), A-WEB r23 (`not_covering`) | — |
    | 23 Sep, Morocco | `af23c8e10357`; iso:MA, national, 09-23, confirmed, Held | "Moroccan Chamber of Representatives" | `b5e3f77c0c1b`: EG past/r11; WPn September/li[4], NDI p0/past-c5, EISA y2026/r13 (all `less_certain`) | — |
    | 24 Sep, Isle of Man | `2064e8f68b8c`; iso:IM, national, 09-24, unknown, Held | "House of Keys" | `b74251137bc8`: WPn September/li[5] | — |
    | 27 Sep, São Tomé and Príncipe | `8818bc29cc27`; iso:ST, national, 09-27, confirmed, Held | "Sao Tomean National Assembly" | `2b76c271e7be`: EG past/r10; WPn September/li[6]/li[1], NDI p0/past-c4, EISA y2026/r15 (all `less_certain`) | — |
    | 4 Oct, Brazil, national | `54b356d5b5ea`; iso:BR, national, 10-04, confirmed, Held | "Brazilian Presidency (1st round) · Brazilian Chamber of Deputies · Brazilian Federal Senate" | `baa1bb5de7fe`: EG past/r4; WPn October/li[2]/li[2]#0. `219ff0785bdd`: EG past/r7; WPn …/li[2]/li[2]#1. `aefc0f383484`: EG past/r3; WPn …/li[2]/li[2]#2 (each `less_certain`) | A-WEB r25, NDI p0/past-c2 |
    | 4 Oct, Brazil, governors | `c8c9844ab7a8`; iso:BR, subnational, 10-04, unknown, Held | "Governors: Alagoas, Amazonas, Bahia, Ceará, Espírito Santo, Federal District, Goiás, Maranhão, Minas Gerais, Pará, Paraíba, Paraná, Pernambuco, Rio de Janeiro, Rio Grande do Norte (+3 more) (18)" | 18 children, one claim each: WPl October/li[1]/li[1]/li[1] to li[18] | WPl October/li[1]/li[1] |
    | 4 Oct, Paraguay | `d01ed25c943e`; iso:PY, subnational, 10-04, unknown, Held | "municipal elections" | `9ea96cd48d74` (aggregate): WPl October/li[1]/li[3] | — |
    | 4 Oct, Peru | `05f32126cb43`; iso:PE, subnational, 10-04, unknown, Held | "Lima: Mayor" | `1ba2f246cd98`: WPl October/li[1]/li[4]/li[1] | NDI p0/past-c1, WPl October/li[1]/li[4] |
    | 8 Oct, United Kingdom | `cc453aae6835`; iso:GB, national, 10-08, unknown, Held | "Holborn and St Pancras: House of Commons by-election" | `d5cc461fb60f`: WPl October/li[3]/li[2] | — |
    | 9–10 Oct, Czech Republic | `abf124b4c48f`; iso:CZ, subnational, 10-09 to 10-10, unknown, Held | "municipal elections" | `fd0fffe821dc` (aggregate): WPl October/li[4] | — |
    | 24 Oct, Slovakia | `d8b6179b8850`; iso:SK, subnational, 10-24, unknown, Upcoming | "regional and local elections" | `117d9dff3af3` (aggregate): WPl October/li[9]/li[2] | — |
    | 25 Oct, Brazil | `4b35f9d2401c`; iso:BR, national, 10-25, confirmed, Upcoming | "Brazilian Presidency (2nd round)" | `f90b0d7db440`: EG up/r3; WPn October/li[6]/li[3] (`less_certain`) | A-WEB r27 |
    | 25 Oct, Serbia | `c5842ef99109`; iso:RS, national, 10-25, confirmed, Upcoming | "Serbian National Assembly" | `bcb7e2ccdf47`: EG up/r2; OSCE r2 and WPn October/li[6]/li[2] (`less_certain`), NDI p0/upcoming-c2 (`not_covering`), IPU r222 (`lower_evidence`) | — |
    | 5 Nov, Grenada | `f65719631682`; iso:GD, national, 11-05, unknown, Upcoming | "House of Representatives" | `1e8c23148913`: WPn November/li[2]; IPU r105 (`lower_evidence`) | — |
    | 7 Nov, New Zealand | `32dd654de9aa`; iso:NZ, national, 11-07, confirmed, Upcoming | "New Zealand House of Representatives" | `1e8e1a5746c8`: EG up/r16; WPn November/li[3] (`less_certain`), IPU r180 (`lower_evidence`) | — |
    | 15 Nov, Cape Verde | `b65b9fe5b9b3`; iso:CV, national, 11-15, confirmed, Upcoming | "Cabo Verdean Presidency" | `eae5cc187a1a` (`date_conflict`): EG up/r17; WPn November/li[4] and NDI p0/upcoming-c4 (`less_certain`), EISA y2026/r7 (`not_covering`) | — |
    | 15 Nov, Slovenia | `4e451911e2f5`; iso:SI, subnational, 11-15, unknown, Upcoming | "Local Elections" | `ca2bd502e0e0` (aggregate): OSCE r4 | — |
    | 29 Nov, Spain | `64539229886f`; iso:ES, national, 11-29, confirmed, Upcoming | "Spanish Congress of Deputies · Spanish Senate" | `ad420bd35f9c`: EG up/r18; WPn November/li[5]/li[1]#1 (`less_certain`), IPU r236 (`lower_evidence`). `8199c9644471`: EG up/r19; WPn November/li[5]/li[1]#0 (`less_certain`), IPU r237 (`lower_evidence`) | OSCE r5 |
    | 29 Nov, Switzerland | `4a02993930ce`; iso:CH, national, 11-29, confirmed, Upcoming | "Referendum" | `22e9f7b733fe`: EG up/r20; WPn November/li[5]/li[2] (`less_certain`) | — |

    Where the merge reads an Appendix B row more precisely than its wording, the row above is
    the rule's result:
    - Peru's "regional and municipal" is an umbrella on the Lima Mayor card (§10.4), not a child;
    - Grenada's "Parliament" is a generic legislature attached by C7, so the child shows IPU's
      "House of Representatives";
    - the Czech 9–10 Oct national Senate card, `792ca8cad502` ("Czech Senate (1st round)", child
      `d3df127ddfa9`: EG past/r2; WPn October/li[3] `less_certain`), sits beside the municipal
      card;
    - Spain's OSCE "Parliamentary Elections" is an umbrella over both chambers (P71).
  - **`test_unmatched_renewal_is_expected_not_announced`** (R4, P25):
    - 201 children have only IPU sources. Every one is `tentative`, `expected_window` and
      `Upcoming`: 181 with month precision and 20 with day precision.
    - 4 of them are in the window: `iso:LY` "House of Representatives" (December 2026), `iso:MG`
      "Senate" (December 2026), `iso:SO` "Upper House" (December 2026) and `iso:CM`
      "National Assembly" (January 2027).
  - **`test_year_precision_claims_are_undated`** (R8, P68):
    - the 61 year-precision claims have the dispositions `undated` 35 (Wikipedia 24, OSCE 7, EISA
      3, NDI 1), `attention` 22 (EEAS) and `attached` 4 (Wikipedia 2, OSCE 1, EEAS 1);
    - `osce:elections/r24#0` to `r30#0` are `undated`. `osce:elections/r6#0` is `attached`, with
      the reason `year_only`, to the Serbian child `f4ad0477ca3a`, whose label is "Early
      Presidential Election";
    - no EEAS claim is `undated`.
  - **`test_a_year_only_claim_stays_visible`** (R13):
    - Haiti's `ndi:p0/upcoming-c7#0` → `undated` (`fd43d6447fdf`). Its item, `f6e0fc10981e`, is
      `in_or_after_window`, with the text
      "Haiti: 2026 Haiti General Election (Phase 1) (Date TBD) (2026), date not given";
    - El Salvador's `ndi:p0/upcoming-c10#0` (February 2027) → `umbrella_link` to the children
      `846a4e205782` (Salvadoran Legislative Assembly, card `fb957eb6f305`) and `c06f962c22e2`
      (President, card `51f6324c23ed`).
  - **`test_fixture_order`:**
    `merge(tuple(reversed(fixture_claims())), now=FIXTURE_NOW, places=PlaceRegistry.load()) == fixture_result()`,
    and `list_order(match(…, FIXTURE_NOW))` (Task 6's helper) is equal for the two orders.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/merge/test_fixture_merge.py -q`.
  Expected: PASS (the code exists). A failure is a rule that differs from this plan: find it, stop
  and report.
- [ ] **Step 3: Gates, mutation table, commit:**
  `test(merge): the fixture merge end to end (Appendix B, R4, R8, R13)`.

  Mutations, one each; each must fail its test:
  - `test_fixture_merge_counts`: each loose umbrella becomes its own aggregate (P72 off);
  - `test_fixture_merge_counts`: `umbrella_fits` drops P81's jurisdiction and office scope. Measured
    by `alt6.py`: 56 links, 141 aggregate children, 741 cards, the US card back to 56 children;
  - `test_fixture_merge_counts`: an observation item takes its relevance from its candidates
    (revision 1's P77). Measured by `alt6.py`: 1 in-window evidence item instead of 5;
  - `test_appendix_b`: the display label adds no round and no jurisdiction (P76 off). Measured by
    `check13_r6.py`: Brazil's 4 Oct type loses "(1st round)", and Peru's and the UK's lose "Lima: " and
    "Holborn and St Pancras: ";
  - `test_unmatched_renewal_is_expected_not_announced`: C7 is off. Measured by `check12_r6.py`: 204
    IPU-only children, and Grenada's joins the 4 in the window. No other single correction changes
    this test's values, and IPU claims are never anchors anyway (their `date_meaning` is
    `expected_window`);
  - `test_year_precision_claims_are_undated`: a weak year-only claim never attaches;
  - `test_a_year_only_claim_stays_visible`: listing items are `before_window`;
  - `test_fixture_order`: `match` drops step 0's sort.

---

## Requirements for later plans

Each later plan's pre-flight must pull its rows from this table into its own tasks, with the
named acceptance test. A row is closed only when that test is green in the owning plan. R1, R2,
R10, R11 and R14–R16 stand as written in Plans 2b and 2c.

| ID | Requirement | Owner | Acceptance test (name and result) | Completion stage |
|---|---|---|---|---|
| R4 (Plan 5 part) | A renewal-only contest is labelled as an expected renewal in the extension, never as an announced date | Plan 5 | `test_renewal_only_child_is_labelled_expected` | Plan 5's extension |
| R5 (Plan 4 part) | In the legacy feed, a `date_meaning="unknown"` observation never gives a date or a Held/Ongoing status (P67 keeps it out of selection and status) | Plan 4 | the legacy-feed case of `test_unknown_meaning_observation_never_makes_held_or_ongoing` | Plan 4's feed task |
| R17 | `elections.json` serialises `MergeResult`: cards, children, sources, umbrellas, listings, attention items and dispositions (§5.3–§5.5), with `content_id`, the 500-item attention cap and `attention_truncated` | Plan 4 | `test_feed_serialises_every_merge_record`; `test_attention_cap_sets_attention_truncated` | Plan 4's feed task |
| R18 | A `MergeError` blocks publishing: the previous feed stays, and the run reports the message (S3-T16) | Plan 4 | `test_merge_error_blocks_publishing` | Plan 4's publish task |
| R19 | Plan 4 stamps `fetched_at`, `fallback`, `snapshot_id` and `provisional`. A claim from an incomplete fetch that equals the served claim gives no provisional claim, so no `provisional_change` (V2-T01) | Plan 4 | `test_an_unchanged_partial_claim_is_not_provisional`; `test_stamped_fallback_claims_reach_the_merge` | Plan 4's snapshot task |
| R20 | Unit attention items (`unparsed_unit`, `partial_unit`, `disappeared_unit`, and `provisional_change` for units) join the merge's items in one list, sorted by `item_id`, before the cap | Plan 4 | `test_unit_and_claim_attention_items_share_one_list` | Plan 4's attention task |
| R21 | `unnamed_parts` gives false alarms on joint tickets ("Presidential and Vice-Presidential") and on "National and Provincial" (Plan 2c's known limit). The merge sees only claims, so the decision is Plan 4's | Plan 4 | `test_joint_ticket_is_not_unnamed_parts` | Plan 4's health task |
| R22 | The extension shows possible matches, umbrella sources, a stale fetch date (§12.3) and the S3-T17 v1.0.2 pins | Plan 5 | `test_possible_matches_and_umbrellas_are_labelled`; `test_stale_fetch_date_is_shown`; S3-T17's pins | Plan 5's extension |
| R23 | The serialised feed for the 2026-10-16 fixture shows every Appendix B row (this plan checks the merge; Plan 4 checks the feed) | Plan 4 | `test_appendix_b_in_the_feed` | Plan 4's feed task |
| R24 (revision 2: D1, D2, D3, G02) | The feed serialises `Child.rescheduled_from`, `Child.provisional_date`, and each `umbrella_link` disposition's child targets (not cards). The README notes two legacy-status changes for v1.0.2 users: a cancelled election that another source still lists now shows `Cancelled` (flagged), and a rescheduled election shows `Upcoming` on its new date | Plan 4 | `test_feed_serialises_rescheduling_and_provisional_date`; `test_umbrella_link_targets_children_in_the_feed`; the README note, checked in Plan 4's final review | Plan 4's feed task |
| R25 (revision 2: D1, D2, D3, G02; revision 3: D4, D5) | The extension shows an umbrella only on the children it covers, a "Rescheduled from <date>" chip, a `status_conflict` label that says a cancellation is disputed, and a past rescheduled election as past but unconfirmed (`occurrence_confirmed` False). For `less_precise`, a note that the source now gives a less precise date, with the served and the new date ("15 November 2026 → November 2026"); never "no longer specifies a day" for a range of days, which is `moved` (D5). A confirmation from a cached `held` claim shows its fetch date (D4) | Plan 5 | `test_umbrella_shown_per_child`; `test_rescheduled_chip`; `test_less_precise_note` (a day to its month, and a month to its year); `test_cancellation_conflict_label`; `test_past_rescheduled_is_unconfirmed`; `test_cached_confirmation_shows_its_date` | Plan 5's extension |
| R26 (revision 3: the user's note on extension weight) | The extension stays light. Plan 3's records carry every claim in full; serialised as they stand, the fixture's 1335 claims alone are about 1.09 MB (`weight7.py`), 40 times v1's 27,557-byte feed and over half of §11.3's 2 MB cap, and the in-window children's 274 claims about 229 KB. Plan 4 designs the feed to carry only what the extension shows or checks, measures the serialised bytes on the 2026-10-16 fixture, and asks the user for a byte budget before its feed task closes. Plan 5 measures the popup's parse and first render on that feed | Plan 4 (the feed), Plan 5 (the popup) | `test_feed_size_is_within_the_budget` (the bytes and the budget in the run summary); `test_popup_renders_the_fixture_feed_within_the_budget` | Plan 4's feed task; Plan 5's extension |

## After Plan 3

- **The branch** has the Plan 3 commits on top of the commit that holds this plan, with all gates
  green. Nothing is pushed or merged.
- **The Review record** shows every Plan 3 row as "verified", with its commit in the SDD ledger.
  R4 (Plan 5 part), R5 (Plan 4 part) and R17–R26 stay open until their own plans' acceptance tests
  pass.
- **Next:** Plan 4 (health, snapshots, feed and publishing), written against this code.
