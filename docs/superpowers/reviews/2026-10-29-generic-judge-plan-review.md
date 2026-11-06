# Multi-Agent Review: spec docs/superpowers/plans/2026-10-29-generic-judge.md

## Executive Summary
Lenses: pre-mortem, inversion, red-team, first-principles, jobs-to-be-done

Ten reviewers (five roster agents and five reasoning lenses) reviewed the general-judge implementation plan against its spec and the current `policy.py`/`state.py`/router code. The headline problem is that `policy.judgment` and `state.py` trust whatever the caller supplies:
- The requirement list, the lens panel and the brief are never checked against the ledger. One reviewer rated this CRITICAL: a partial or empty fit report yields `meets`, and so `decision: yes`.
- Requirement records drive decisions without verification.
- Route rule 15 re-judges unchanged snapshots without bound.
- Rank step 3 breaks re-ranking and later solo revision.
- `--entries` follows symlinks into secrets.

After dedupe the run produced 1 CRITICAL and 19 HIGH findings. The severity budget kept 8 HIGH and demoted 11. Recommended action: **block**. Do not execute the plan as written until the CRITICAL and kept HIGH items are fixed and the open questions below are dispositioned.

## Critical Findings

**C1. `judgment` never receives the brief's requirement IDs, so empty or partial fit records yield `fit = meets` and `decision = yes`.**
- **Location:** plan:146 (request keys), plan:153 (Task 2 step 3, "Empty `requirement_records` → `meets` with `fit_vacuous: true`"), plan:227 (`validate_result`); state.py:449/1035 (`validate_result` gets no state).
- **Description:**
  - A fit reviewer that returns `[]` for a 3-requirement brief gives a vacuous `meets`.
  - A reviewer that returns only R1 gives `meets` with R2 and R3 never judged.
  - A supported Critical whose `requirement_id` has no record, or names an unknown ID such as `R9`, moves nothing.
  - Coverage still reads `complete`. The spec ties vacuity to the brief having no requirements (spec:145), not to the reviewer returning nothing. In rank mode an entry can induce this through injected text.
- **Suggested fix:**
  - Add `requirement_ids` from the stored brief to the request. Require the set of record IDs to equal it exactly, with no duplicates; raise `PolicyError` (or mark fit coverage incomplete) on a mismatch.
  - Set `fit_vacuous` only when `requirement_ids == []`. Reject a finding `requirement_id` that is not in that set.
  - Pass `state` into `validate_result` and recheck against `state.brief.requirements`.
  - Add tests for empty, partial, duplicate and unknown IDs.
- **Attribution:** lens:inversion (CRITICAL); architect-reviewer, silent-failure-hunter, penetration-tester, lens:pre-mortem, lens:red-team (HIGH); lens:red-team (MEDIUM, unknown `requirement_id`).

## High Findings

**H1. The brief is mutable and judgments don't record which brief they used.**
- **Location:** plan:25 ("immutable within a run"), plan:224 (`PATCH_FIELDS` includes `brief`, `lenses`), plan:225 (`confirmation.brief_sha256`), plan:255 (test asserts "patch with brief → ok"), plan:285 (rule 5), plan:422; state.py:1038-1046.
- **Description:**
  - `update` can replace the brief at any time, for example mid-`--loop` revise to drop a failing requirement.
  - No check compares the brief with `confirmation.brief_sha256`, and judgment results carry no brief hash.
  - On resume, a re-supplied `--brief` whose file changed is silently ignored (rule 5 is skipped once `has_brief` is true).
  - "Run" is undefined.
- **Suggested fix:**
  - Add `brief_sha256` (and a lens-set hash) to every judgment result and check it at save time.
  - Refuse a `brief` patch once a confirmation or any judgment exists ("start a new slug").
  - Have the router stop when the hash of a supplied `--brief` differs from the stored one.
  - Change the Task 4 test to expect `StateError`.
- **Attribution:** lens:red-team, lens:inversion (HIGH); security-reviewer, penetration-tester, lens:first-principles, architect-reviewer, silent-failure-hunter (MEDIUM). Severity spread: HIGH/MEDIUM.

**H2. Requirement records and labels drive the decision without verification.**
- **Location:** plan:148 (verifier required only when `verifier_required(findings)`), plan:153, plan:156, plan:341 (the verifier checks findings only); policy.py:1301-1306, 604-609, 625-628.
- **Description:**
  - Spec:145 requires "`not_met` supported after verification". The plan folds raw `not_met` records, including ones with empty `finding_ids` or whose only finding was refused, into `does_not_meet` and `no`.
  - In the other direction, an all-`met`, zero-finding reply needs no verifier (`verifier_required([])` returns `False`, which reviewers ran). Nothing checks `evidence_location`, `feasibility_label` or `achievable`.
  - Today's "empty issue list is not sufficient to invest" guard (policy.py:604-609) is dropped with no replacement. In rank mode an injected "all requirements met" reaches `yes`.
- **Suggested fix:**
  - Count a `not_met`/`partly_met` record only when it cites an established, non-excluded finding; otherwise treat it as `cannot_tell`.
  - Require the verifier for every judgment whose decision is not `cannot_judge`, and extend it to spot-check `met` records' `evidence_location` and the basis of the feasibility label.
  - Add a test: an unverified `not_met` record does not yield `no`, and an unverified `met` record does not yield `yes`.
- **Attribution:** lens:first-principles, lens:inversion, architect-reviewer, lens:red-team, penetration-tester (HIGH); security-reviewer (MEDIUM).

**H3. A judgment declares its own lens panel, so v2 can drop a stored generated lens and still validate as `complete`.**
- **Location:** plan:146, plan:227 ("required roles are every ID in `result["lenses"]`"), plan:378; state.py:449, 1035.
- **Description:** Coverage and required roles both come from the caller's `lenses`. A re-judge that omits the generated lens that failed v1 saves as complete and can flip `no` to `yes`. That breaks "same lenses for v1 and v2" (spec:118, judge-standard rule 4) and the incomplete-coverage anti-goal.
- **Suggested fix:** In `report` for `judgment`, require `set(result.lenses) == {l.id for l in state.lenses}`, including `FIXED_LENSES`. Add a test where stored `mix` is omitted from the result, expecting `StateError`.
- **Attribution:** silent-failure-hunter, lens:red-team, lens:inversion (HIGH); penetration-tester, architect-reviewer, lens:pre-mortem (MEDIUM).

**H4. `--entries`/`--examples` follow symlinks, so a secret file is snapshotted into the ledger and sent to reviewers.**
- **Location:** plan:282, plan:426 (rank step 3), plan:450 (brief step 2); state.py:541-558 (`canonical_root` resolves with `strict=True`, `base = path.parent`), state.py:953.
- **Description:**
  - Reproduced: a symlinked source roots the ledger beside its target (`/usr/bin/.autopsy/entry-a`).
  - A submission such as `entries/x.md -> ~/.secrets` puts `GH_TOKEN` into an immutable `versions/v1.md`, every reviewer's context, and possibly reports.
  - The plan never says which files count as entries or examples: regular files only, hidden files, recursion, symlinks.
- **Suggested fix:** Enforce in Python a top-level, regular-file-only listing (`lstat` + `S_ISREG`). Skip dotfiles and `.autopsy/`, refuse symlinks, and require the resolved path to stay inside the folder. Add tests for a symlinked entry and a symlinked example.
- **Attribution:** security-reviewer (HIGH); penetration-tester, lens:red-team, lens:pre-mortem (MEDIUM); silent-failure-hunter (LOW, enumeration).

**H5. Route rule 15 ("Otherwise → `judge`") re-judges a judged, unchanged snapshot without bound.**
- **Location:** plan:291-295 (Task 5 rules 11-15); compare policy.py:1043-1067 (today every stored verdict ends in `stop`).
- **Description:** These states all return `judge`, as several reviewers confirmed by simulating the rules:
  - a complete `cannot_judge` (Review Focus 1's own case);
  - `not_yet`/`no` without `--loop`;
  - `--loop` with `can_revise: false`.

  Judging never bumps the version, so the version cap never fires. `--loop` dispatches about 7 agents per pass, forever, and plain resumes re-judge unchanged text. There is also no "what to supply" stop for `cannot_judge`.
- **Suggested fix:** Before rule 15, add "`has_judgment` → `stop`", with a reason naming the decision, the `cannot_tell` requirement IDs or the limiting lens, and how to continue. Keep `judge` only for "no judgment for current version" or an explicit `judge` intent. Add `route_cases` for each state.
- **Attribution:** architect-reviewer, silent-failure-hunter, lens:pre-mortem, lens:inversion, lens:first-principles, lens:jobs-to-be-done (HIGH).

**H6. `normalize` takes `lens`/`requirement_id` from the first group member, so the decision depends on dispatch order.**
- **Location:** plan:96, plan:129; policy.py:351-386.
- **Description:** Reproduced: two findings on one `issue_id` merge to `lens: fit, requirement_id: None` in one order and `lens: feasibility, requirement_id: R2` in the other, with `conflicts: []`. Task 2 rules 3 and 4 key on these fields, so the same evidence can yield `no` or `yes`.
- **Suggested fix:** Add `lens` and `requirement_id` to the per-issue conflict keys, or union them and have the rules iterate the union. Add an order-independence test.
- **Attribution:** lens:inversion, lens:pre-mortem (HIGH).

**H7. `--critique-only`/`--rewrite` are ignored once `rewritable` is stored, so an entry can be rewritten against the user's flag.**
- **Location:** plan:279, plan:288 (rule 8, null only), plan:292-293 (rules 12-13), plan:376 (judge honours flags only when null).
- **Description:** Simulated:
  - `route("auto", ["--critique-only","--loop"])` on stored `rewritable: true` and `not_yet` returns `revise`.
  - `--rewrite --loop` on stored `false` returns `critique_complete`.

  That violates spec:106 ("flags override the default") and the anti-goal "rewriting an entry the user did not want rewritten" (spec:39). `decided_by` exists but no rule reads it.
- **Suggested fix:** Before rule 12, let an explicit flag override a stored value whose `decided_by` is `default` (or `rank`), persisted as `decided_by: "flag"`. Return `ask_user` on a conflict with a `user` decision. Add both directions to `route_cases`.
- **Attribution:** penetration-tester, lens:inversion (HIGH).

**H8. Rank step 3 breaks re-ranking and later solo revision of ranked entries.**
- **Location:** plan:424-429 (Task 11 rank steps 1, 3 and 6); plan:376, 378; state.py:933-937; iterate-to-v2 SKILL.md:59; spec:166, 177, 179.
- **Description:**
  - **`init` on existing ledgers:** every entry ledger is `init`ed unconditionally, and `init` raises "state already exists" on any re-rank.
  - **No brief or lenses on entry ledgers:** they get none, so per-entry lens generation breaks "same panel", and a later solo run hits rule 5 (no brief).
  - **Forced `rewritable`:** the preset `rewritable: {false, decided_by: "default"}` plus rules 8 and 12 make a later `--rewrite` solo run end in `critique_complete`, contradicting spec:177.
  - **Wrong reuse key:** reuse keys on "its snapshot hash" alone. It ignores brief and lens changes, and if computed from the disk file it misses ledger-only revisions (spec:179).
  - **Stale reuse:** a transient `incomplete_coverage` judgment is reused forever.
- **Suggested fix:**
  - Run `status` first and `init` only when absent.
  - Copy the confirmed brief and lenses (with hashes) onto each entry ledger.
  - Record `decided_by: "rank"` and let `--rewrite` override it.
  - Key reuse on (entry ledger current-version hash, brief hash, lens-set hash), and never reuse non-complete reports.
  - Add tests: rank then solo `--rewrite --loop` gives `revise`; re-rank after a revision uses v2.
- **Attribution:** lens:jobs-to-be-done, silent-failure-hunter, lens:inversion, lens:pre-mortem, lens:red-team (HIGH); lens:first-principles, architect-reviewer, security-reviewer, penetration-tester (MEDIUM). Severity spread: HIGH/MEDIUM.

## Medium and Low Findings

| Severity | Title | Location | Reviewer(s) | One-line description |
|---|---|---|---|---|
| MEDIUM | `brief_merge` drops derived requirements on ID collision _(demoted from HIGH by severity budget; correctness, 4 reviewers, data loss is confined to brief derivation in 4.2.0)_ | plan:447, plan:36, plan:449 | silent-failure-hunter, lens:inversion, lens:pre-mortem (HIGH); lens:first-principles (MEDIUM) | Both sources number `R1..Rn`, so a different derived requirement with a matching ID is silently dropped and `conflicts` is never populated; use a `D1..` namespace and dedupe on normalised text only. |
| MEDIUM | 4.0.0 routes to `revise`/`rank` skills that don't exist; `iterate-to-v2` ships business vocabulary _(demoted from HIGH by severity budget; release-sequencing correctness, 3 reviewers)_ | plan:278, 293, 371, 384, 417-418, 497; iterate-to-v2 SKILL.md:14-46 | lens:first-principles, architect-reviewer, lens:pre-mortem (HIGH) | PR 2 is the "half-converted" state plan:497 forbids; move `revise` into PR 2 or add interim stops, and delete `iterate-to-v2` in Task 9. |
| MEDIUM | Pairwise tie-break undefined for 3+ ties and cycles; departs from the spec's one-reviewer group order _(demoted from HIGH by severity budget; correctness, 1 HIGH rater)_ | plan:402-403, 428; spec:173 | lens:jobs-to-be-done (HIGH); penetration-tester, lens:red-team, lens:inversion, lens:pre-mortem, silent-failure-hunter (MEDIUM) | A>B, B>C, C>A has no defined dense rank (filename order decides, measured); 12 tied entries need 66 dispatches; follow the spec or define cycle → shared rank. |
| MEDIUM | Two or more pairwise dispatches fail `review_model_coverage` _(demoted from HIGH by severity budget; correctness, 1 reviewer)_ | plan:227, 428; policy.py:1323, 1340 | architect-reviewer (HIGH) | Reproduced "duplicate observed/expected model role"; name roles per pair (`pairwise:<a>:<b>`) or record one role per run. |
| MEDIUM | A ranking report cannot be saved on the brief-level ledger (no version) _(demoted from HIGH by severity budget; correctness, loud failure)_ | plan:226, 429; state.py:1010-1015 | architect-reviewer (HIGH); security-reviewer, silent-failure-hunter (MEDIUM) | `report` requires `version in state["versions"]` and the brief ledger has none; let `ranking` skip the version and record the brief hash, and add a test. |
| MEDIUM | Explicit intents `brief`/`judge`/`rank` have no rules; `insufficient_evidence` is a dead end _(demoted from HIGH by severity budget; correctness)_ | plan:274, 285-295; policy.py:998-1018 | architect-reviewer, lens:pre-mortem (HIGH); lens:inversion (MEDIUM) | Intent `brief` with no brief falls to `judge`; an explicit re-judge after coverage is restored stops; `ask_input_roles` is never produced; add explicit-intent rules. |
| MEDIUM | Input flags (`--brief`, `--entries`, `--examples`, `--slug`) trip the "flag is incompatible with the selected skill" guard _(demoted from HIGH by severity budget; correctness)_ | plan:275, 279; policy.py:299-320, 946-958 | lens:pre-mortem (HIGH); lens:inversion (MEDIUM) | Every rank run and every resumed `--brief` judge raises (reproduced on current `route`); declare these as input flags excluded from the check. |
| MEDIUM | Task 1 under-counts broken tests: markdown import, `evidence` fixture key, integration test _(demoted from HIGH by severity budget; plan-accuracy, loud failure)_ | plan:89-96, 129-131; policy.py:171-322, 318-319; tests/test_policy.py:28-55, 638-690, 884 | architect-reviewer (HIGH); lens:pre-mortem (MEDIUM) | Simulated: 4 markdown tests (6 subtests) and 2 GateTests fail, `KeyError: 'evidence'` breaks 2 more, and no task rewrites the only end-to-end integration test. |
| MEDIUM | "Supported Critical" undefined in fit/feasibility rules _(demoted from HIGH by severity budget; ambiguity)_ | plan:153-154, 172; policy.py:136-160, 444-462 | lens:inversion (HIGH); silent-failure-hunter, lens:pre-mortem (MEDIUM); architect-reviewer (LOW) | `doc_support == "supported"` differs from `established()` and `affects_decision`; a resolved Critical could force `not_met` in v2. Reuse the existing `criticals`/`highs` filter. |
| MEDIUM | Confirmed hypotheses are never promoted into `requirements` _(demoted from HIGH by severity budget; correctness, 1 reviewer)_ | plan:447, 452, 153 | lens:inversion (HIGH) | With 1 good + 1 bad example every derived item stays a hypothesis, so fit is vacuous `meets`; brief step 4 should move confirmed hypotheses into `requirements`. |
| MEDIUM | `yes` blocks revision even on explicit `revise` intent _(demoted from HIGH by severity budget; product-job gap, 1 reviewer)_ | plan:293-294; policy.py:1017-1018; spec:22, 139 | lens:jobs-to-be-done (HIGH) | Quality is outside the decision, so a `yes`/`weak` competition entry can never be improved; today's router allows it; let explicit `revise` pass on `yes`. |
| MEDIUM | Business-term `lens_check` matches substrings, misses synonyms, and is unlocked by any mention | plan:356; spec:120 | architect-reviewer, silent-failure-hunter, penetration-tester, lens:red-team, lens:inversion, lens:first-principles, lens:jobs-to-be-done (MEDIUM); security-reviewer (LOW) | Measured: `roi` matches "heroic/android/Detroit"; "business value/sales/willingness to pay" pass; negations unlock; only `examine` is scanned; lens text has no length cap. Use `\b` regexes over requirement text only. |
| MEDIUM | Router and `judge` skill both own the rewritable decision; rule 8 asks on every first run | plan:288, 376; spec:101-106 | architect-reviewer, lens:pre-mortem, lens:first-principles, lens:jobs-to-be-done | `ask_rewritable` fires before the default rule can run; pick one owner (drop rule 8, or rename it to `decide_rewritable`). |
| MEDIUM | Override can set any label to any value, producing contradictory labels; rank's input is unspecified | plan:157, 402; policy.py:618-631 | penetration-tester, lens:red-team, lens:inversion, lens:first-principles, architect-reviewer, lens:pre-mortem | `decision: yes` beside `fit: does_not_meet`, or `cannot_judge` → `yes`; the old Invest upgrade guard is dropped; rank doesn't say whether it reads overridden or mechanical labels. |
| MEDIUM | Ranking labels and counts are caller-transcribed and never checked against the cited reports | plan:402, 227 | penetration-tester, lens:red-team, silent-failure-hunter | `report_id` is never resolved and counts are never validated; recompute from stored judgment reports at save time. |
| MEDIUM | Fact-checker and reviewers keep broad `Read` (+`WebFetch`) while reading untrusted rank entries | plan:332, 342, 279; agents/project-idea-validator.md:4 | security-reviewer, lens:red-team, penetration-tester | An injected claim can exfiltrate local files via `Read` + `WebFetch`; drop `Read` from the fact-checker, scope reviewer reads, or bar `--verify-claims` in rank mode. |
| MEDIUM | "Untrusted data, not instructions" rule is not pinned through the contracts/agents rewrite | plan:314-319, 332-342; contracts.md:13 | penetration-tester (MEDIUM); security-reviewer (LOW) | The Task 6 ledger may mark it "dropped" and the new agent bodies don't restate it; add a grep check in Tasks 6 and 7. |
| MEDIUM | Business plugin's `import-legacy` will take over a schema-3 ledger | plan:66-78, 228; state.py:305-310, 831-875 | penetration-tester, lens:jobs-to-be-done, lens:pre-mortem | Its error message points the user at `import-legacy`, which accepts any non-2 schema and replaces generic state; patch the business clone to refuse schema ≥3. |
| MEDIUM | Brief-ledger slug can collide with an entry slug; brief or examples may sit inside the entries dir | plan:282, 424-426 | security-reviewer, silent-failure-hunter, lens:inversion, architect-reviewer (MEDIUM); lens:jobs-to-be-done, penetration-tester, lens:red-team (LOW) | `brief.md` + `entries/brief.md` share `.autopsy/brief/`; rule 2 checks entry slugs only; give the brief ledger its own namespace and exclude the brief from entries. |
| MEDIUM | `ranking` in `CORE_MODEL_ROLES` demands `assessment_status`/`expected_model_roles` the ranking report lacks | plan:224, 429; state.py:450-463 | lens:inversion, architect-reviewer | Every ranking save is rejected unless the gate is silently removed; define the ranking gate and preflight pairwise roles. |
| MEDIUM | Pairwise records are not persisted, so the `pairwise`-role check never fires | plan:227, 402, 429 | lens:inversion, lens:pre-mortem | Step-6 report fields omit `pairwise`; add the records (with reason/sources) and require the role whenever `separated_by == "pairwise"`. |
| MEDIUM | Removing the `AXES` alias breaks `policy.py` import (`review_model_coverage` default) | plan:129, 224; policy.py:1309 | architect-reviewer (MEDIUM); silent-failure-hunter (LOW) | `required_roles=AXES` is evaluated at import; change the default to `()` or make it required, and list the line in Task 4. |
| MEDIUM | Shared-assumption / user-report-dependency path omitted from the judgment interface | plan:146-157, 195-196; policy.py:465-494, 547-553 | architect-reviewer, lens:pre-mortem | The plan says to keep it, but no request/result keys or derivation step carry it; insert "unresolved shared assumption → `insufficient_evidence`". |
| MEDIUM | `axes` vs `lens` ambiguous for the feasibility forcing rule | plan:96, 154, 159; policy.py:569 | lens:first-principles, lens:inversion (MEDIUM); architect-reviewer (LOW) | A Critical with `axes: ["feasibility"]` and no `lens` may or may not force `not_achievable`; pick one field or require `lens ∈ axes`. |
| MEDIUM | `lens_check` rejects stored fixed lenses; the cap can be bypassed via `user_edited` | plan:225, 356, 378 | lens:first-principles, lens:red-team, architect-reviewer, lens:inversion | Pass only non-fixed lenses and count `generated` + `user_edited` toward the cap of 3. |
| MEDIUM | `lens_check` rejections vanish silently; stored lenses are never re-validated | plan:356, 378, 425, 224-225 | silent-failure-hunter | Show `rejected` to the user and validate stored lens IDs (`LENS_ID`, reserved roles, uniqueness) in `state.py`. |
| MEDIUM | Optional judgment inputs may default to passing values | plan:146, 191; policy.py:430 | silent-failure-hunter | If `feasibility_label` defaults to `achievable` as in the test helper, missing reviewer output becomes `yes`; make these keys required. |
| MEDIUM | A fit-lens Critical without `requirement_id` does not move fit | plan:96, 153 | silent-failure-hunter | Require `requirement_id` when `lens == "fit"` (at least for Critical/High). |
| MEDIUM | `brief_merge` checks example counts, not files | plan:447 | silent-failure-hunter, lens:inversion | Duplicate or bad-example citations pass `support`; pass example file lists and require `set(support) == set(good)`. |
| MEDIUM | Task 4 "keep durability/concurrency/recovery tests as they are" cannot hold | plan:230 | lens:pre-mortem | Simulated: 19 `test_state.py` cases fail on the `KINDS`/`PATCH_FIELDS` change; specify a mechanical port with assertions unchanged. |
| MEDIUM | Task 6/13 vocabulary greps fail on code the plan keeps or adds | plan:319, 475; policy.py:240-277 | lens:pre-mortem, architect-reviewer (MEDIUM); lens:jobs-to-be-done (LOW) | `markdown_candidates` labels, `BUSINESS_TERMS`, `investment_context` in tests, and `roi` fragments make "no hits" impossible; scope the greps and use word boundaries. |
| MEDIUM | No size guard for brief, examples, or pairwise inputs | plan:428, 450 | lens:pre-mortem | Apply the `wordcount` combined guard to derive (all examples) and pairwise (brief + two entries). |
| MEDIUM | `--entries` enumeration, empty dir, binary files and per-entry failure are undefined | plan:276, 283-286, 426; state.py:952 | lens:pre-mortem (MEDIUM); silent-failure-hunter (LOW) | Define sorted regular non-hidden files, slugification, reject empty dirs, and send per-entry failures to `unranked`. |
| MEDIUM | README describes the business plugin through three releases | plan:207, 471 | lens:pre-mortem | Ship a minimal README in PR 2 with a "moved to `idea-autopsy-business`" line. |
| MEDIUM | Tracer bullet lands after eight horizontal tasks | plan:366-392; spec:230 | architect-reviewer, lens:pre-mortem | Run a fixed-lens tracer right after Tasks 1, 2 and 4 inside PR 2. |
| MEDIUM | Neutral brief package may hand example paths to `Read`-capable reviewers | plan:225, 332, 377 | lens:inversion | Strip `support`/`contradicted_by`/`example_hashes`/`confirmation` from the package. |
| MEDIUM | An unconfirmed derived brief counts as `has_brief` | plan:276, 225, 285; spec:90 | lens:inversion | A session that dies before confirmation judges against an unconfirmed brief; tie `has_brief` to confirmation. |
| MEDIUM | Lens reuse "when present" regenerates lenses when zero were generated | plan:378 | lens:inversion | Always store the full list, including fixed lenses, and define "present" as non-empty. |
| MEDIUM | `--slug` in the route flag set breaks `--slug X --status` | plan:275; policy.py:833-836, 902-906 | architect-reviewer | The admin branch rejects `--status` with any other flag; keep value selectors out of `flag_set`. |
| MEDIUM | Findings with no requirement can still drive all labels to `cannot_judge` | plan:152; spec:148 | architect-reviewer | Step 2 treats any non-established `affects_decision` finding as a gap; restrict `affects_decision` to findings with a requirement or on feasibility. |
| MEDIUM | Feasibility judged with no stated constraints carries no provisional flag | plan:147, 154-156; spec:63, 147 | lens:jobs-to-be-done | Add `feasibility_provisional` (like `quality_provisional`) and surface it. |
| MEDIUM | Non-rewritable path is never run end to end | plan:383, 388, 434, 461 | lens:jobs-to-be-done | Add a manual run on a described track expecting `critique_complete`, no v2, and a blockers list. |
| MEDIUM | Pasted briefs (a spec input) are never handled | plan:384, 449; spec:56, 226 | lens:jobs-to-be-done | Parse pasted brief text like a file, with `provenance: user`. |
| MEDIUM | Image entries fail at the `init` UTF-8 decode | plan:376; state.py:953-954; spec:11, 118 | lens:jobs-to-be-done | List image entries as a non-goal, or snapshot image bytes and force `rewritable: false`. |
| MEDIUM | One `cannot_tell` requirement removes an entry from the ranking, with no remedy shown | plan:153, 403 | lens:jobs-to-be-done | Have `unranked[].reason` list the `cannot_tell` IDs and "supply X to rank". |
| LOW | Error messages still point to the removed `import-legacy`; the schema-2 refusal is unreachable from `init`/`recover` | plan:228, 259; state.py:305-311, 903-906, 921, 933-937 | security-reviewer, penetration-tester, silent-failure-hunter, lens:red-team, lens:inversion, lens:pre-mortem, lens:first-principles | Check the schema before validate/exists/journal in a shared helper; refuse any `schema_version != 3`; reword all three messages. |
| LOW | Expected failure text is "unknown operation judgment"; `execute` raises "unknown operation" | plan:193; policy.py:1386 | architect-reviewer | Fix the expected text. |
| LOW | Deleting `__pycache__`, which is untracked | plan:206, 209 | architect-reviewer | Remove it from the Delete list. |
| LOW | Duplicate-slug error hard-codes "a.md or a.txt" | plan:282 | architect-reviewer, lens:first-principles | Format the message with the real colliding slug or files. |
| LOW | Rejecting `--critique-only` in rank mode has no basis | plan:283 | lens:first-principles | Rank never revises anyway; accept or ignore the flag. |
| LOW | Weak-support threshold `good == 1 and bad == 1` is narrower than its reasoning | plan:447 | lens:first-principles | Use `good == 1` with any `bad`, or justify `bad`. |
| LOW | `RANK_MAX_ENTRIES = 12` has no source | plan:284, 399 | lens:first-principles | Document the cost reasoning. |
| LOW | `iterate-to-v2` rename released as a minor bump | plan:419, 493 | lens:first-principles | Breaking a skill name is major per AGENTS.md; fold it into 4.0.0. |
| LOW | Interim 4.0.0 brief parser doesn't handle missing headings or unnumbered requirements | plan:384 | lens:jobs-to-be-done | Record missing Constraints/Standard as `not_stated` and auto-assign `R1..Rn`. |
| LOW | Rule 11 stop reason has no gap data to name | plan:291, 276 | silent-failure-hunter | Add `evidence_gaps` to the route state summary. |
| LOW | `pairwise` and `derive` dispatch steps omit "with the prohibitions" | plan:428, 450, 379 | penetration-tester | Add the prohibitions clause to both. |
| LOW | `standard_stated` is caller-supplied, not derived from the brief | plan:146, 155 | lens:inversion (LOW); penetration-tester (within HIGH-1 text) | Derive it from `brief.provenance.standard`. |
| LOW | Business repo history will include the generic spec and plan | plan:62-70 | lens:inversion, lens:pre-mortem | Push before Task 0 step 3, or accept and note it. |
| LOW | Tracer runs bare `/autopsy` while both plugins are installed | plan:388, 82 | lens:pre-mortem | Use `/idea-autopsy:autopsy`. |
| LOW | `brief_sha256` canonicalisation undefined | plan:225, 452 | lens:pre-mortem | Specify sorted-keys JSON of the brief without `confirmation`. |

## Coverage Report
Reviewers: 10/10 returned
Reviewed at: f75278cdd3039d954ecd7547711d4a7ba040cef9
Any commit after this one is unreviewed.

**Confirmed:**
- **Baseline suite:** `python3 -m pytest -q` gives 107 passed, 166 subtests (all nine severity-using reviewers).
- **Plan line ranges match `main`:**
  - policy.py: `validate_finding` 102, `normalize` 325, `verdict` 402-632, `flag_set`/`route` 813-1070.
  - state.py: 41 `NAME`, 61 reads `policy.AXES`, 161, 239, 305-311, 449, 670, 831, 876.
  - Sources: architect-reviewer, lens:first-principles, lens:inversion.
- **Tests and fixture named for change exist:** test_policy.py:1040/1070/1097, test_state.py:558, and the fixture keys (architect-reviewer, lens:inversion).
- **`verifier_required([])` returns `False`** (ran it: lens:first-principles, penetration-tester, lens:red-team).
- **Today's router stops after every completed verdict** (policy.py:1043-1067; architect-reviewer, silent-failure-hunter, lens:inversion, lens:first-principles, lens:jobs-to-be-done, lens:pre-mortem). Rule-15 simulations return `judge` (several reviewers).
- **Explicit `revise` reaches `revise()` regardless of verdict today** (policy.py:1017-1018; lens:jobs-to-be-done).
- **The Invest guards the plan drops exist:** policy.py:604-609, 625-628 (lens:red-team, penetration-tester, lens:first-principles).
- **`validate_result` has no state access:** state.py:449, called at 1035 (silent-failure-hunter, lens:red-team).
- **`report` requires an existing version:** state.py:1010-1015 (security-reviewer, silent-failure-hunter, architect-reviewer).
- **`init` refuses an existing ledger:** state.py:933-937 (several reviewers).
- **`CORE_MODEL_ROLES` kinds require `assessment_status`:** state.py:450-463 (silent-failure-hunter, lens:inversion).
- **`canonical_root` follows symlinks:** reproduced `/usr/bin/.autopsy/entry-a` (security-reviewer; read by penetration-tester and lens:red-team).
- **Existing ledger hardening holds:** artifact symlink/hardlink checks state.py:285-302, lock `O_NOFOLLOW` 908-920, slug regex blocks traversal (security-reviewer, penetration-tester, lens:red-team).
- **`normalize` merge is order-dependent:** reproduced with `conflicts: []` (lens:pre-mortem; read by lens:inversion).
- **Duplicate `pairwise` roles raise `PolicyError`:** reproduced (architect-reviewer).
- **Flag-incompatibility guard fires:** reproduced on current `route` (lens:pre-mortem).
- **Task 1 side effects simulated:** 4 markdown tests (6 subtests) and 2 GateTests fail, and `KeyError: 'evidence'` breaks 2 more (architect-reviewer, lens:pre-mortem).
- **Task 4 side effects simulated:** 19 `test_state.py` failures (lens:pre-mortem).
- **Business-term substring false positives and negatives measured** (7 reviewers).
- **3-cycle sort order depends on input permutation; comb(12,2) = 66** (lens:red-team).
- **Business `_legacy` accepts any non-2 schema** (state.py:838-841), and its message suggests `import-legacy` (penetration-tester, lens:jobs-to-be-done, lens:pre-mortem).
- **`iterate-to-v2` business vocabulary and hand-offs** at SKILL.md:14-46; it never overwrites the source (:59) (lens:first-principles, lens:pre-mortem, lens:red-team, lens:inversion).
- **`project-idea-validator` tools are `Read, WebFetch, WebSearch`:** agents/project-idea-validator.md:4 (security-reviewer, lens:red-team).
- **The untrusted-data clause exists at contracts.md:13** (security-reviewer, penetration-tester).
- **`init` decodes the source as UTF-8:** state.py:953-954 (lens:jobs-to-be-done).
- **`AXES` default argument at policy.py:1309** (architect-reviewer, silent-failure-hunter, lens:pre-mortem).
- **`__pycache__` is untracked; gitlink 160000 exists; no `idea-autopsy:` namespace references** (architect-reviewer, silent-failure-hunter, lens:inversion).
- **No common secret patterns in git history** before the Task 0 push (security-reviewer).
- **`thresholds.json` lacks `rank_max_entries`; `load_thresholds` checks only `REQUIRED_KEYS`** (lens:first-principles, lens:inversion).

**Examined, inconclusive:**
- **Prompt injection into lens/pairwise/derive reviewers and fact-checker exfiltration** need runtime adversarial-entry tests (security-reviewer, lens:red-team).
- **Whether the router handles `ask_rewritable`, strips `--brief`, and re-enters `route`** after storing the brief: the router prose doesn't exist yet (lens:jobs-to-be-done, lens:first-principles, lens:inversion, architect-reviewer).
- **Whether the judge skill passes stored lens IDs, and where rank-preset ledgers find the brief:** needs the written SKILL.md (lens:inversion, lens:jobs-to-be-done).
- **Whether `tools: Read` frontmatter is enforced for plugin-dispatched agents:** needs a runtime dispatch (lens:first-principles, penetration-tester).
- **Business `import-legacy` against a schema-3 ledger and `_commit` recoverability:** static trace only; writes were prohibited (penetration-tester, lens:pre-mortem).
- **`normalize` with generated-lens findings, and `review_model_roles` with lens IDs:** need the implementation (silent-failure-hunter).
- **Symlinked `--brief` handling in the interim router and `--reset`:** router is prose (security-reviewer).
- **Bare `/autopsy` resolution with two plugins installed:** needs an installed environment (lens:pre-mortem).
- **Entry slug source (CLI listing vs ledger):** router unwritten (lens:red-team).

**Not examined** (no reviewer confirmed or examined these):
- `wordcount.py` internals beyond threshold loading.
- Task 0 steps 4-6: business repo creation, the `gh`/`claude plugin` commands and `claude plugin details` output.
- Task 13 `examples/` content and the README rewrite text.
- `model_preflight`/`model_observation` bodies (policy.py:1100-1300).
- Journal/recovery internals (state.py:725-830) beyond the schema-check ordering.
- Full prose of `contracts.md`/`judgment-rubric.md`, i.e. Task 6 instruction-ledger completeness.
- The `revise` remedy table text, and execution of the frontmatter-ceiling one-liners (plan:345, 387).
- `gate`/`acceptance`/`change_id` internals beyond the `CATEGORIES` rename.

**Engagement check:** every severity-using reviewer has a substantive Confirmed list with evidence. None is tagged `[DID NOT ENGAGE]`.

## Unstated Assumptions and Open Questions (from critical-thinking)
- **Markdown import:** `markdown_candidates` (policy.py:316-319) emits `thesis_breaking`/`plausibly_resolvable`, which Task 1 rejects. The markdown tests (test_policy.py:641-687) would fail. *Verify:* does the general judge keep markdown import, and why is it absent from Task 1's files?
- **Shared-assumption dependence:** today it yields `insufficient_evidence` (policy.py:547-553), but its keys are missing from the judgment interface. *Decide:* is it still a gate, and where in the 1-7 order?
- **Requirement IDs:** `judgment` never receives the brief's requirement IDs. *Decide:* what guarantees one record per requirement, and what happens with an unknown ID?
- **"Supported":** undefined, and `doc_support` disagrees with `established()`. *Decide:* which predicate, and is `affects_decision` required?
- **`axes` vs `lens`:** both name the lens. *Decide:* why keep both, which is authoritative for forcing, and how does `lens` merge?
- **Findings with no requirement:** a non-established `affects_decision` finding with no requirement still blocks the judgment, though spec:148 says such findings don't move answers. *Decide:* can it be decisive?
- **Rewritable owner:** rule 8 and judge step 1 both decide rewritability, and rule 8 fires first. *Decide:* which owns it; should rule 8 exist?
- **Ranked entries:** they get `rewritable: false, decided_by: "default"`. *Decide:* can `--rewrite` override that on a later solo run, and where is it tested?
- **Pairwise:** the plan dispatches per pair, where the spec has one reviewer order all tied entries. *Decide:* why the departure, and what happens with cycles?
- **Pairwise model roles:** `review_model_coverage` rejects duplicate role names. *Decide:* how are multiple pairwise observations named?
- **Re-rank keys:** re-rank reuse keys on the snapshot hash only; editing the brief and slug collisions are undefined. *Decide:* key on brief and lens hashes too? What if the brief slug equals an entry slug?
- **`stage` values:** `brief` and `ranking` have no derivation from report kinds. *Decide:* how is each derived, and does any rule read them?
- **`--examples` in 4.0.0:** it is silently ignored by the interim router. *Decide:* reject it until 4.2.0?
- **Tracer placement:** the tracer bullet is Task 9, after 8 horizontal tasks. *Decide:* why can't a thin slice go first?
- **Tracer plugin version:** the tracer may run against the installed 3.x plugin. *Decide:* how does the run prove the worktree version loaded?
- **Task 0 ordering:** Task 0 merges before pushing the business repo, without a `pull --ff-only`. *Decide:* which commit should the business repo start from?
- **Collision direction:** the frozen business plugin points schema-3 users to `import-legacy`. *Decide:* is the business-to-generic direction safe?
- **Caps:** the version cap of 3 is hardcoded while the entry cap moves to `thresholds.json`. *Decide:* is 3 right for every entry type?
- **Rule 3 flags:** rule 3 doesn't reject `--accept-all`/`--accept-none` in rank mode. *Decide:* should it?
- **Task 2 expected text:** Task 2 expects "unknown operation judgment"; `execute` raises "unknown operation". *Decide:* fix the text, or name the operation?
- **Slugs:** no slugify rule exists for names that fail `NAME`. *Decide:* what is it, and does rule 2 run after slugifying?
- **Brief hash:** the canonical serialisation for `brief_sha256` is undefined. *Decide:* the form, and does `judge` refuse an unconfirmed brief?
- **Quality-bar requirements:** "quality never moves the decision" depends on the fit reviewer converting quality-bar requirements into records. *Decide:* which reviewer judges them, and is that written into `reviewer.md`?

## Reviewer Disagreements
- **C1 severity:** lens:inversion rated it CRITICAL; architect-reviewer, silent-failure-hunter, penetration-tester, lens:pre-mortem and lens:red-team rated it HIGH. *Resolution:* keep CRITICAL (highest rating wins), since it lets an unchecked entry reach `yes`.
- **Severity of H1 (brief mutability), H3 (lens panel), H8 (rank step 3) and H4 (symlinks):** each was rated HIGH by some reviewers and MEDIUM by others:
  - H1: HIGH from lens:red-team and lens:inversion; MEDIUM from security-reviewer, penetration-tester, lens:first-principles, architect-reviewer and silent-failure-hunter.
  - H3: HIGH from silent-failure-hunter, lens:red-team and lens:inversion; MEDIUM from penetration-tester, architect-reviewer and lens:pre-mortem.
  - H8: HIGH from five reviewers; MEDIUM from four.
  - H4: HIGH from security-reviewer; MEDIUM from penetration-tester, lens:red-team and lens:pre-mortem.

  *Resolution:* HIGH stands for all four; each was kept within the budget.
- **H2 severity:** lens:red-team and penetration-tester rated HIGH; security-reviewer rated MEDIUM, citing model-behaviour dependence. *Resolution:* HIGH. The unverified-`not_met` half is deterministic and needs no injection.
- **Business-term filter severity:** security-reviewer rated LOW ("user-confirmation step reduces the risk"); seven others rated MEDIUM. *Resolution:* MEDIUM. The false rejections are measured and hit legitimate briefs.
- **Brief/entry slug collision severity:** MEDIUM from security-reviewer, silent-failure-hunter, lens:inversion and architect-reviewer; LOW from lens:jobs-to-be-done, penetration-tester and lens:red-team. *Resolution:* MEDIUM, because one entrant's filename can break a whole ranking.
- **Pairwise fix:** lens:jobs-to-be-done and lens:red-team prefer following the spec (one reviewer orders the whole tie group). penetration-tester, silent-failure-hunter, lens:inversion and lens:pre-mortem accept pairs with "cycle → shared rank". *Resolution:* follow the spec. That also removes architect-reviewer's duplicate-role failure and the 66-dispatch blow-up.
- **Rule 8 fix:** drop rule 8 (architect-reviewer, lens:first-principles, lens:pre-mortem), or rename it to `decide_rewritable` (lens:jobs-to-be-done, lens:first-principles). *Resolution:* drop rule 8 and let judge step 1 own the default; this matches spec:101.
- **Override fix:** four approaches were proposed:
  - penetration-tester and lens:red-team: require a user decision ID for upgrades;
  - lens:inversion: re-derive `decision` from overridden labels;
  - lens:pre-mortem: forbid overriding away from `cannot_judge`;
  - architect-reviewer and lens:first-principles: state whether rank reads overridden or mechanical labels.

  *Resolution:* these are compatible. Forbid overriding away from `cannot_judge`, require consistency with the step-6 table, require a user decision ID for upgrades, and show overrides in the ranking.
- **`axes`/`lens` fix:** lens:first-principles suggests dropping `lens` or requiring `lens ∈ axes`; lens:inversion says pick either field; architect-reviewer requires `lens ∈ axes`. *Resolution:* keep `lens` as the source reviewer, require `lens ∈ axes`, and have forcing rules read `axes` (or the union after merge, per H6).
- **Rank-mode flag strictness:** lens:first-principles says `--critique-only` should be accepted in rank mode. critical-thinking asks whether `--accept-all`/`--accept-none` should also be rejected. *Resolution:* reject the flags that change behaviour rank can't honour (`--loop`, `--rewrite`, `--accept-*`), and accept the no-op `--critique-only`.
- **Explicit `revise` on `yes`:** lens:jobs-to-be-done wants it allowed. The plan's rule 14 stops. *Resolution:* this is an author decision (see Open Questions).

## Recommended Changes (Prioritized)
1. Disposition the 28 open questions.
2. Add `requirement_ids` from the stored brief to `judgment`, require exact record coverage, and tie `fit_vacuous` to an empty brief (C1).
3. Require that negative records cite established findings, and require verification of the records and labels behind any non-`cannot_judge` decision (H2).
4. Pass ledger state into `validate_result`, and require judgment `lenses` to equal the stored panel (H3).
5. Record `brief_sha256` and a lens-set hash on every judgment, refuse brief patches once confirmed or judged, and stop on a changed `--brief` (H1).
6. Make `normalize` merge `lens` and `requirement_id` order-independently (H6).
7. Replace route rule 15's catch-all with "`has_judgment` → `stop`" and add the missing route cases (H5).
8. Let explicit flags override a stored `rewritable` whose `decided_by` is `default`/`rank` (H7).
9. Rewrite rank step 3: status-then-init, copy brief and lenses to entry ledgers, `decided_by: "rank"`, and a three-hash reuse key on the ledger snapshot (H8).
10. Add a regular-file, no-symlink, top-level-only enumeration for `--entries`/`--examples`, with tests (H4).
11. Fix the 4.0.0 release scope: ship `revise` in PR 2 or add interim stops, and delete `iterate-to-v2` in Task 9.
12. Fix Task 1's test accounting: decide `markdown_candidates`, move the `assessment()` rewrite into Task 1, and assign the integration test to a task.
13. Allow `ranking` reports on version-less ledgers, define their gate, and resolve pairwise ties per the spec with persisted evidence.
14. Add explicit-intent rules and exempt input flags from the incompatibility check.
15. Use a `D1..` namespace in `brief_merge`, define conflicts, and promote confirmed hypotheses into requirements.
16. Define "supported" as today's `criticals`/`highs` filter, and restore the shared-assumption gate in the derivation.
17. Rewrite `lens_check` with word-boundary matching over requirement text, a cap covering all non-fixed lenses, and visible rejections.
18. Constrain overrides, cross-check ranking inputs against stored reports, and show overrides in the ranking table.
19. Narrow fact-checker and reviewer tools for untrusted entries, and pin the untrusted-data clause with grep checks.
20. Make the business clone refuse schema ≥3, and fix the stale `import-legacy` messages and schema-check ordering.
21. Address the remaining MEDIUM and LOW items in the table, scoping the vocabulary greps and moving the tracer bullet earlier.

## Open Questions for the Author
- Does the general judge keep markdown import (`markdown_candidates`), and if so, which task changes it? — Disposition: DROPPED. Judgment reports are structured; Task 1 deletes `markdown_candidates` and its four tests (plan Decision 1).
- Is shared-assumption dependence still a gate in `judgment`, and where in the derivation order? — Disposition: KEPT as step 3 of the judgment derivation (plan Decision 2).
- What guarantees exactly one requirement record per brief requirement, and what happens to an unknown `requirement_id`? — Disposition: `judgment` takes `requirement_ids` from the ledger and requires exact record coverage; an unknown ID is a `PolicyError` (plan Decision 3, Task 2).
- Which predicate does "supported" mean (`doc_support`, `established()`, `affects_decision`)? — Disposition: today's `criticals`/`highs` filter; the plan now says "established" (plan Decision 4).
- Why keep both `axes` and `lens`; which is authoritative for the forcing rules, and how does `lens` merge? — Disposition: `lens` is the originating reviewer and must be in `axes`; forcing rules read `axes`; merge unions `axes` and lists `lens` (plan Decision 5, Task 1).
- Can a finding with no requirement, from a non-feasibility lens, be `affects_decision`, and why should it block the judgment? — Disposition: it cannot; `normalize` rejects `affects_decision` without a `requirement_id` or `feasibility` in `axes` (plan Decision 6).
- Which component owns the rewritable decision, and should rule 8 exist? — Disposition: the `judge` skill owns it; rule 8 and `ask_rewritable` are gone (plan Decision 7).
- Does `--rewrite` override a stored `rewritable: false` set by ranking, and where is that tested? — Disposition: yes; route rule 10 overrides `decided_by` `default`/`rank`, tested in Task 4 `route_cases` and the Task 12 manual run (plan Decision 8).
- Why depart from the spec's single reviewer ordering all tied entries, and how are cycles resolved? — Disposition: the plan now follows the spec; one `tiebreak` reviewer orders each group, so no cycles (plan Decision 9).
- How are multiple pairwise model observations named so `review_model_coverage` accepts them? — Disposition: `tiebreak-1`, `tiebreak-2`, … one per group (plan Decision 10).
- Should re-rank reuse also key on the brief and lens hashes, and what happens when the brief slug equals an entry slug? — Disposition: reuse keys on (version hash, brief hash, lens-set hash) and only `complete` judgments; brief ledgers are `brief-<name>`; the brief file is excluded from entries (plan Decision 11).
- How is each `stage` value (including `brief` and `ranking`) derived, and does any rule read them? — Disposition: `stage` is the latest report kind; `brief` stage removed; only `has_brief`/`has_judgment` are read (plan Decision 12).
- Should 4.0.0 reject `--examples` until 4.2.0 instead of ignoring it? — Disposition: rejected with "arrives in 4.2.0" (plan Decision 13, route rule 5).
- Why can't a thin fixed-lens tracer slice go before Tasks 3 and 5-8? — Disposition: reordered; the tracer is Task 7 and every earlier task is something it calls; lens_check, protocol removal and revise now follow it (plan Decision 14).
- How does the tracer run prove the worktree plugin version, not the installed 3.x, was loaded? — Disposition: `claude --plugin-dir <worktree>`, plus `schema_version: 3` and `plugin_version` in the saved report (plan Decision 15).
- Which commit should `idea-autopsy-business` start from: before or after Task 0 step 3, and after a `pull --ff-only`? — Disposition: after step 3 and a `pull --ff-only`; the generic docs in business history are accepted (plan Decision 16).
- Is the business-to-generic collision direction safe, given the business `import-legacy` accepts schema 3? — Disposition: Task 0 step 5 patches the business clone to refuse schema ≥ 3 (plan Decision 17).
- Is a version cap of 3 right for every entry type, and why does the entry cap move to `thresholds.json` while the version cap stays hardcoded? — Disposition: cap stays 3 (user decision) and moves to `thresholds.json` as `max_versions` (plan Decision 18).
- Should rule 3 also reject `--accept-all`/`--accept-none` (and accept `--critique-only`) in rank mode? — Disposition: yes to both (plan Decision 19, route rule 3).
- Should Task 2's expected failure text be corrected to "unknown operation", or should `execute` name the operation? — Disposition: text corrected to "unknown operation" (plan Decision 20).
- What is the slugify function for entry filenames, and does rule 2 run on slugified names? — Disposition: `state.slugify` defined in Task 3; rule 2 runs on slugified names (plan Decision 21).
- What canonical serialisation is hashed for `brief_sha256`, and does `judge` refuse an unconfirmed brief? — Disposition: sorted-keys compact JSON without `confirmation`; `has_brief` means confirmed, so `judge` refuses otherwise (plan Decision 22).
- Which reviewer judges requirements that are really quality bars, and is that written into `reviewer.md`? — Disposition: the `fit` reviewer; written into the role table (plan Decision 23, Task 5).
- Should an explicit `revise` intent be allowed on a `yes` decision (for example `yes` with quality `weak`)? — Disposition: allowed; spec updated (user decision, plan Decision 24).
- Should `cannot_tell` on a non-rewritable entry give a provisional ranking placement rather than exclusion? — Disposition: stays unranked; the reason names the IDs and what to supply (plan Decision 25).
- Are image entries a non-goal (judged from a description), or should `init` snapshot image bytes? — Disposition: non-goal; spec updated (user decision, plan Decision 26).
- Does `rank` order on overridden or mechanical labels? — Disposition: reported labels, with an override marker in the table (plan Decision 27).
- Should feasibility judged without stated constraints be flagged provisional? — Disposition: yes, `feasibility_provisional` (plan Decision 28).

**Merge gate:** block. There is an unresolved CRITICAL and 28 PENDING questions.

**Author's response (2026-11-06):** all 28 questions dispositioned above; C1 and H1 to H8 answered in the plan revision committed after this review (`docs/superpowers/plans/2026-10-29-generic-judge.md`, "Decisions from the reasoned review"). The demoted-High items marked must-fix (release scope, ranking save on a version-less ledger, the input-flag guard, explicit-intent rules, Task 1 test accounting, `--slug --status`) are also in that revision.

## Notes
- Roster: context-aware selection (refs/multi-agent/context-aware-selection.md) was not run; the caller directed the static safety-net roster (architect-reviewer, critical-thinking, silent-failure-hunter, security-reviewer, penetration-tester), all parked agents dispatched as `general-purpose` with their agent-file bodies pasted.
- Brief delivery: each worker's fully expanded §7 brief was assembled byte-exactly by script into a scratchpad file and the dispatch prompt pointed at it (with the read-only prohibition restated inline), rather than inlining the brief text in the `prompt` field.
- Dispatch mode: the harness's Agent tool exposed no `run_in_background` parameter, so all 10 workers ran in the background; all 10 completion notifications reached the orchestrator and the count reconciled 10/10.
- Report path: `--write-to` points outside the git root (scratchpad), which §5A.1 step 10 would reject; accepted on the caller's explicit instruction. Per-reviewer JSON checkpoints under `.claude/reviews/` were skipped to keep the repo untouched.

## Report Audit

1. **High Findings / Medium and Low table: kept-versus-demoted HIGHs do not follow the stated tie-break (class 3).**
   - **What the report says:**
     - H6 ("`normalize` takes `lens`/`requirement_id` from the first group member") is kept as HIGH, attributed to "lens:inversion, lens:pre-mortem (HIGH)". That is 2 reviewers, impact class correctness.
     - These are demoted, also as correctness: "`brief_merge` drops derived requirements on ID collision _(demoted from HIGH by severity budget; correctness, 4 reviewers, …)_", "4.0.0 routes to `revise`/`rank` skills that don't exist _(… release-sequencing correctness, 3 reviewers)_", "Explicit intents … _(demoted from HIGH by severity budget; correctness)_" (3 reviewers), and "Pairwise tie-break undefined … _(… correctness, 1 HIGH rater)_" (6 reviewers listed).
   - **The rule the report was given:** rank by impact, and break ties by "the number of distinct reviewers that raised the finding".
   - **The discrepancy:** at equal impact class, the 2-reviewer H6 survives while 3-, 4- and 6-reviewer correctness findings are demoted. The pairwise row's reason, "1 HIGH rater", ranks by how many reviewers rated it HIGH, not by how many raised it. The brief_merge reason, "data loss is confined to brief derivation in 4.2.0", is a judgment on merit carried inside a budget tag.

2. **H4 credits lens:pre-mortem with the symlink finding, and the same enumeration findings are counted twice (classes 6 and 2).**
   - **What the report says:** H4 ("`--entries`/`--examples` follow symlinks, so a secret file is snapshotted…") lists "penetration-tester, lens:red-team, lens:pre-mortem (MEDIUM); silent-failure-hunter (LOW, enumeration)". Reviewer Disagreements repeats "H4: … MEDIUM from penetration-tester, lens:red-team and lens:pre-mortem".
   - **What the source says:** lens:pre-mortem's only related item is "`--entries DIR` enumeration and per-entry failure paths are undefined". Its description reads "Unspecified: an empty directory (`entry_count` 0), subdirectories, hidden files, non-UTF-8 or binary files … names that slug-normalise to invalid slugs … one entry's `init` or judge failing". It never mentions symlinks or secrets. silent-failure-hunter's item ("`--entries DIR` with zero files, hidden files or non-text files is unspecified") does not mention symlinks either.
   - **The double count:** both items also appear as their own table row, "`--entries` enumeration, empty dir, binary files and per-entry failure are undefined … lens:pre-mortem (MEDIUM); silent-failure-hunter (LOW)". The same two reviewer findings are counted in H4 and in the table, which inflates H4's support from 1 HIGH plus 2 MEDIUM to 1 HIGH plus 3 MEDIUM plus 1 LOW.
