# Idea Autopsy as a General Judge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the `idea-autopsy` plugin into a general judge that scores one or more entries against a user-supplied brief, after preserving the business version as `idea-autopsy-business`.

**Architecture:** The executable policy (`skills/_shared/policy.py`) and ledger (`skills/_shared/state.py`) keep their shape: pure operations called with JSON, validated, persisted immutably. The business vocabulary inside them is replaced by a brief-driven one (`fit` / `feasibility` / `quality` / `decision`, lens IDs instead of fixed axes). Prose skills, agents and the router are rewritten on top. Ranking and brief derivation are new operations and skills layered on the single-entry flow.

**Tech Stack:** Python 3.12 stdlib only (no new dependencies), `unittest` with subtests (existing style), Markdown skills/agents/commands for the Claude Code plugin format.

**Spec:** `docs/superpowers/specs/2026-10-28-generic-judge-design.md`

## Global Constraints

- Every PR that changes a skill, script, command or agent bumps `version` in both `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (`plugins[0].version`) in the same commit. First content PR goes to `4.0.0`; later PRs that add a skill bump minor, others bump patch.
- All work on feature branches in worktrees; merge from the primary checkout; remove worktree, local branch and remote branch after each merge.
- No new Python dependencies. No network access in `policy.py` or `state.py`.
- Decision labels, verbatim: `fit` ∈ `meets|partly_meets|does_not_meet|cannot_judge`; `feasibility` ∈ `achievable|achievable_with_changes|not_achievable|cannot_judge`; `quality` ∈ `strong|adequate|weak|cannot_judge`; `decision` ∈ `yes|not_yet|no|cannot_judge`.
- Fixed lens IDs, verbatim: `fit`, `feasibility`, `quality`. Generated lens IDs match `[a-z][a-z0-9-]{1,31}` and never collide with a fixed ID or `verifier`, `derive`, `pairwise`, `fact-checker`.
- Consequential change categories, verbatim: `routine`, `scope`, `approach`.
- Severity vocabulary unchanged: `Critical`, `High`, `Medium`.
- Ledger directory stays `.autopsy/<slug>/`. Schema version becomes `3`. A schema-2 ledger is refused, never migrated.
- Skill frontmatter `description` ≤ 1024 characters (hard ceiling), aim ≤ 200.
- The brief is immutable within a run. Reviewers never receive raw example files.
- No numeric scores anywhere in results or prose.

## Review Focus

Inputs the spec implies but no task's tests would otherwise exercise, most likely to bite first:

1. **A brief with zero requirements and a feasibility of `cannot_judge`.** Expected: `fit = meets` flagged `vacuous`, `decision = cannot_judge`, and the reasons name feasibility, not fit. Test added to Task 3.
2. **A generated lens whose ID collides with a fixed one or with `verifier`.** Expected: `lens_check` rejects it before dispatch. Test added to Task 8.
3. **`--entries DIR` with a single file.** Expected: single-entry route (`judge`), not `rank`; no brief-level ledger. Test added to Task 5.
4. **Ranking where every entry is `cannot_judge`.** Expected: `ranked` empty, all entries in `unranked` with reasons, no pairwise dispatch requested. Test added to Task 10.
5. **A derived brief that drops or softens a user-written requirement.** Expected: `brief_merge` keeps the user's text and lists the conflict. Test added to Task 12.

---

### Task 0: Repo split

Not a code task. Run from the primary checkout `/home/alex/idea-autopsy`, never from a worktree. The user confirms step 4 before it runs.

**Files:** none in this repo beyond the merge; `plugin.json`, `marketplace.json`, `README.md` in the new business clone.

- [ ] **Step 0: Drop the stale tracked gitlink**

`.worktrees/evidence-driven-idea-loop` is tracked as a gitlink (mode 160000) with no `.gitmodules`; a fresh clone gets an empty directory and a warning. On a branch `chore/untrack-stale-worktree`: `git rm --cached .worktrees/evidence-driven-idea-loop`, add a root `.gitignore` containing `.worktrees/` and `__pycache__/`, commit, PR, merge, clean up.

- [ ] **Step 1: Merge the existing hackathon-judge PR**

A PR for `feat/hackathon-judge` already exists: [z0rd0n88/idea-autopsy#16](https://github.com/z0rd0n88/idea-autopsy/pull/16). From the primary checkout: `gh pr merge 16 --squash`, `git pull --ff-only`, `git worktree remove .worktrees/hackathon-judge`, `git branch -D feat/hackathon-judge`, `git push origin --delete feat/hackathon-judge`.

- [ ] **Step 2: Remove the empty worktree**

```bash
cd /home/alex/idea-autopsy && git worktree remove .worktrees/company-feature-proposals && git branch -D feat/company-feature-proposals
```

Expected: `git worktree list` shows only the primary checkout and `.worktrees/generic-judge`.

- [ ] **Step 3: Merge this design/plan branch**

Push `feat/generic-judge-design`, open a PR titled "docs: design and plan for the general judge", merge, clean up as in Step 1.

- [ ] **Step 4: Create the business repo (user confirms first)**

```bash
gh repo create z0rd0n88/idea-autopsy-business --private --description "Evidence-based business proposal assessment (the business-specific Idea Autopsy)" && cd /home/alex/idea-autopsy && git push git@github.com:z0rd0n88/idea-autopsy-business.git main:main
```

- [ ] **Step 5: Clone and rename the business plugin**

```bash
git clone git@github.com:z0rd0n88/idea-autopsy-business.git /home/alex/idea-autopsy-business
```

In the clone, on branch `chore/rename-to-business`: set `name` to `idea-autopsy-business` in `plugin.json` and in `marketplace.json` (`name`, `plugins[0].name`), set both versions to `4.0.0`, change the README H1 to `# Idea Autopsy Business` and its install line to `claude plugin install idea-autopsy-business@idea-autopsy-business`. Commit, push, PR, merge.

- [ ] **Step 6: Verify both plugins resolve**

Run: `claude plugin marketplace add z0rd0n88/idea-autopsy-business && claude plugin install idea-autopsy-business@idea-autopsy-business && claude plugin details idea-autopsy-business`
Expected: install succeeds; the details inventory lists five skills (the four business ones plus `hackathon-judge`) and the `autopsy` command. Then in a scratch project, `/idea-autopsy-business:autopsy --slug nothing --status` returns a read-only "no state" answer without creating files.

---

### Task 1: Policy vocabulary and finding schema

**Files:**
- Modify: `skills/_shared/policy.py:19-55` (constants), `:102-133` (`validate_finding`), `:325-400` (`normalize`)
- Modify: `tests/fixtures/workflow_cases.json` (`base_finding`)
- Test: `tests/test_policy.py`

**Interfaces:**
- Produces: `FIXED_LENSES = ("fit", "feasibility", "quality")`; `RESERVED_ROLES = ("verifier", "derive", "pairwise", "fact-checker")`; `LENS_ID = re.compile(r"[a-z][a-z0-9-]{1,31}\Z")`; `CATEGORIES = ("routine", "scope", "approach")`; `LABELS = {"fit": (...), "feasibility": (...), "quality": (...), "decision": (...)}` with the Global Constraints values; `validate_finding(value, lenses=FIXED_LENSES) -> dict`; `normalize(request) -> dict` accepting optional `request["lenses"]` (list of lens IDs, default fixed three).
- Finding fields: keep `id, issue_id, statement, severity, severity_reason, kind, origin, doc_support, external_status, confidence, status, resolution, bucket, evidence_basis, affects_decision, axes, assumption_ids, sources, member_ids`. Add optional `requirement_id` (nonempty string or absent) and optional `lens` (must be in `lenses` when present). Remove `thesis_breaking` and `plausibly_resolvable` (a finding carrying either is rejected with "finding.thesis_breaking is no longer accepted").

- [ ] **Step 1: Update `base_finding` in the fixture**: remove `thesis_breaking` and `plausibly_resolvable`; set `axes` to `["fit"]`.

- [ ] **Step 2: Write failing tests** in `tests/test_policy.py`, class `FindingSchemaTests`:

```python
def test_generated_lens_in_axes_requires_lens_list(self):
    f = finding(axes=["arrangement"])
    with self.assertRaises(policy.PolicyError):
        policy.validate_finding(f)
    self.assertEqual(policy.validate_finding(f, lenses=("fit","feasibility","quality","arrangement"))["axes"], ["arrangement"])

def test_business_only_fields_are_rejected(self):
    for key in ("thesis_breaking", "plausibly_resolvable"):
        with self.subTest(key=key), self.assertRaises(policy.PolicyError):
            policy.validate_finding(finding(**{key: True}))

def test_requirement_id_and_lens_are_optional_but_validated(self):
    self.assertEqual(policy.validate_finding(finding(requirement_id="R2"))["requirement_id"], "R2")
    with self.assertRaises(policy.PolicyError):
        policy.validate_finding(finding(lens="mix"))
    with self.assertRaises(policy.PolicyError):
        policy.validate_finding(finding(requirement_id=""))

def test_categories_are_routine_scope_approach(self):
    self.assertEqual(policy.CATEGORIES, ("routine", "scope", "approach"))
    with self.assertRaises(policy.PolicyError):
        policy.change_id({"change": {"category": "pricing", "description": "x"}})
```

- [ ] **Step 3: Run** `python3 -m pytest tests/test_policy.py -k FindingSchema -q`. Expected: 4 failures.

- [ ] **Step 4: Implement** the constants, `validate_finding(value, lenses=FIXED_LENSES)`, and thread `request.get("lenses")` through `normalize` into every `validate_finding` call. Keep `VERDICTS` (route reads it until Task 5) and keep `AXES = FIXED_LENSES` as a one-line alias with the comment `# removed in Task 4 once state.py stops importing it`, because `state.py:61` reads `policy.AXES` at import time. Existing tests that reference `thesis_breaking`, `plausibly_resolvable`, `Invest` etc. will now fail; the verdict and route tests are rewritten in Tasks 2 and 5, so mark them `@unittest.skip("rewritten in Task 2/5")` for this commit only, listing each in the commit body. The edited `base_finding` is also read by `tests/test_state.py::test_new_complete_evaluation_and_stress_test_require_verifier`, which fails until `state.validate_findings` changes in Task 4; skip it with `"rewritten in Task 4"` and replace it there. Delete outright `test_worked_example_hashes_and_output_contracts`, `test_worked_example_economics_match_the_fixture_text` and `test_fixture_arithmetic` (they read the business examples) and remove `arithmetic_cases` and `evidence` from the fixture.

- [ ] **Step 5: Run** `python3 -m pytest -q`. Expected: new tests pass; skipped tests listed (policy verdict/route tests plus the one state test); nothing else fails.

- [ ] **Step 6: Commit** `git add skills/_shared/policy.py tests/test_policy.py tests/fixtures/workflow_cases.json` / `git commit -m "feat(policy): brief-driven lens and category vocabulary"`.

---

### Task 2: `judgment` operation (replaces `verdict`)

**Files:**
- Modify: `skills/_shared/policy.py:402-632` (replace `verdict` with `judgment`), operations table in `execute`
- Modify: `tests/fixtures/workflow_cases.json` (`verdict_cases` → `judgment_cases`)
- Test: `tests/test_policy.py`

**Interfaces:**
- Consumes: Task 1 constants and `normalize`.
- Produces: `judgment(request) -> dict`. Request keys: `findings`, `severity_resolutions`, `lenses` (list of active lens IDs, must include the three fixed), `coverage` ({lens_id: complete|partial|not_run|failed} with exactly the keys in `lenses`), `requirement_records` (list of `{requirement_id, status: met|partly_met|not_met|cannot_tell, evidence_location, finding_ids}`), `feasibility_label`, `quality_label`, `standard_stated` (bool), `expected_model_roles`, `review_protocol`, optional `override` (`{fit?, feasibility?, quality?, decision?, reason, sources}`).
  Result keys: `schema_version: 3`, `assessment_status` (`complete|incomplete_coverage|insufficient_evidence`), `fit`, `fit_vacuous` (bool), `feasibility`, `quality`, `quality_provisional` (bool), `decision`, `mechanical` (dict of the four labels before override), `reasons`, `requirement_results` (dict keyed by `requirement_id`: `{"status", "evidence_location", "forced_by": [finding IDs]}`), `critical_issue_ids`, `high_issue_ids`, `evidence_gaps`, `excluded_ids`, `conflicts`, `coverage`, `override`, `model_policy_gaps`, `review_role_gaps`, `findings`, `expected_model_roles`, `review_protocol`.
- Required roles for coverage: every ID in `lenses`, plus `verifier` when `verifier_required(findings)`.

Derivation (from the spec, in this order):
1. Model or role gaps, or any coverage value ≠ `complete` → `incomplete_coverage`, all four labels `cannot_judge`.
2. Conflicts or decisive evidence gaps (an `affects_decision` finding that is `missing_evidence`/`question` kind or not established) → `insufficient_evidence`, all four `cannot_judge`.
3. Fit: a supported Critical finding with `requirement_id` sets that requirement to `not_met`. Then: any `not_met` → `does_not_meet`; else any `cannot_tell` → `cannot_judge`; else any `partly_met` → `partly_meets`; else `meets`. Empty `requirement_records` → `meets` with `fit_vacuous: true`.
4. Feasibility: start from `feasibility_label`; a supported Critical on lens `feasibility` forces `not_achievable`; a supported High on lens `feasibility` forces at least `achievable_with_changes` (never lowers a `not_achievable`).
5. Quality: `quality_label`; `quality_provisional = not standard_stated`.
6. Decision: `cannot_judge` if fit or feasibility is `cannot_judge`; `no` if fit `does_not_meet` or feasibility `not_achievable`; `not_yet` if fit `partly_meets` or feasibility `achievable_with_changes`; else `yes`.
7. Override requires `assessment_status == complete`, a nonempty reason and sources; it may change any label to any valid value; `mechanical` keeps the pre-override labels.

- [ ] **Step 1: Rewrite the fixture**: set `coverage` to `{"fit": "complete", "feasibility": "complete", "quality": "complete"}`; replace `verdict_cases` with `judgment_cases`, each `{name, request, expected: {assessment_status, fit, feasibility, quality, decision}}`, covering: all met and achievable → `yes`; one `partly_met` → `not_yet`; Critical on `feasibility` with label `achievable` → `not_achievable`/`no`; `cannot_tell` requirement → `cannot_judge`; empty requirements + feasibility `cannot_judge` → `cannot_judge` with `fit_vacuous` (Review Focus 1); partial coverage on a generated lens → `incomplete_coverage`.

- [ ] **Step 2: Write failing tests** (replace the skipped verdict tests):

```python
def test_fixture_judgment_table(self):
    for case in FIXTURE["judgment_cases"]:
        with self.subTest(case=case["name"]):
            result = policy.execute("judgment", assessment(**case["request"]))
            for key, value in case["expected"].items():
                self.assertEqual(result[key], value, key)

def test_critical_with_requirement_id_forces_not_met(self):
    f = finding(severity="Critical", requirement_id="R1", affects_decision=True, doc_support="supported")
    result = policy.execute("judgment", assessment([f], requirement_records=[{"requirement_id": "R1", "status": "met", "evidence_location": "p1", "finding_ids": []}]))
    self.assertEqual(result["requirement_results"]["R1"]["status"], "not_met")
    self.assertEqual(result["fit"], "does_not_meet")
    self.assertEqual(result["decision"], "no")

def test_high_on_feasibility_lens_raises_floor_but_never_lowers(self):
    ...  # label achievable + High on feasibility → achievable_with_changes; label not_achievable + High → not_achievable

def test_quality_never_moves_decision(self):
    ...  # quality weak, fit meets, feasibility achievable → decision yes

def test_override_records_mechanical_and_requires_complete(self):
    ...  # override decision no with reason+sources → decision no, mechanical.decision yes; override on incomplete_coverage raises

def test_coverage_must_match_active_lenses(self):
    ...  # coverage missing a generated lens raises PolicyError
```

Update the `assessment()` helper to build `expected_model_roles`/`review_protocol` from `request["lenses"]` (default fixed three) plus verifier, and to default `requirement_records=[]`, `feasibility_label="achievable"`, `quality_label="adequate"`, `standard_stated=True`.

- [ ] **Step 3: Run** `python3 -m pytest tests/test_policy.py -q`. Expected: the new tests fail with "unknown operation judgment".

- [ ] **Step 4: Implement `judgment(request) -> dict`** in `policy.py`, register `"judgment"` in the operations table, delete `verdict`. Keep the existing model-coverage, shared-assumption and user-report-dependency code paths; they only change their required-roles input.

- [ ] **Step 5: Run** `python3 -m pytest tests/test_policy.py -q`. Expected: PASS, no skips left for verdict tests.

- [ ] **Step 6: Commit** `git commit -m "feat(policy): judgment operation with fit, feasibility, quality and decision"`.

---

### Task 3: Remove the business validation protocol

**Files:**
- Delete: `skills/_shared/evaluation_audit.py`, `tests/test_evaluation_audit.py`, `tests/fixtures/evaluation_audit_cases.json`, `docs/evaluation-validation.md`, `docs/research/`, `docs/research-implementation-plan.md`, `docs/scholar-refs.md`, `skills/_shared/__pycache__/`
- Modify: `README.md` and `skills/_shared/judgment-rubric.md` only to drop links to the deleted files (full rewrite comes in Task 6).

- [ ] **Step 1: Delete the files** with `git rm -r` for tracked paths (`.gitignore` already covers `__pycache__/` and `.worktrees/` from Task 0 step 0).
- [ ] **Step 2: Run** `git grep -n 'evaluation_audit\|evaluation-validation\|scholar-refs\|research-implementation' -- ':!docs/superpowers'`. Expected: no hits.
- [ ] **Step 3: Run** `python3 -m pytest -q`. Expected: PASS.
- [ ] **Step 4: Commit** `git commit -m "chore: remove business verdict validation protocol"`.

---

### Task 4: Ledger schema 3

**Files:**
- Modify: `skills/_shared/state.py:40-85` (constants), `:161-238` (`validate_findings`: axes ⊆ the ledger's active lens IDs, accept optional `requirement_id` and `lens`, drop `thesis_breaking` and `plausibly_resolvable`), `:239-270` (`validate_working_fields`), `:305-310` (schema check), `:449-528` (`validate_result`), `:670-688` (`_fresh`), `:831-875` (delete `_legacy`), `:876-1081` (`execute`: `init` fields, `update` patch fields, remove `import-legacy`)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `policy.FIXED_LENSES`, `policy.LABELS`, `policy.LENS_ID`.
- Produces: `SCHEMA_VERSION = 3`; `KINDS = {"judgment", "revision", "ranking", "review_copy"}`; `PATCH_FIELDS = {"brief", "rewritable", "lenses", "decisions", "questions", "findings", "entries"}`; `DECISIONS = set(policy.LABELS["decision"])`; `REQUEST_FIELDS["init"] = {"text", "brief", "rewritable", "lenses"}`; no `import-legacy`. Remove the `AXES` alias from `policy.py` in this task; `CORE_MODEL_ROLES` becomes `{"judgment": policy.FIXED_LENSES, "ranking": ()}` and the per-report required roles come from `result["lenses"]`.
- State shape: `brief` is `{}` or `{goal, goal_provisional: bool, requirements: [{id, text, provenance: "user"|"elicited"|"derived", support: [...], contradicted_by: [...]}], hypotheses: [same shape as a requirement], constraints, standard, provenance: {goal|constraints|standard: "user"|"elicited"|"derived"|"not_stated"}, weakly_supported: bool, example_hashes: [{file, sha256, label: "good"|"bad"}], confirmation: null | {decision_id, brief_sha256, review_protocol: {roles: [...]}}}`. The `derive` role's model observation lives in `confirmation.review_protocol`. `rewritable` is `null` or `{value: bool, decided_by: "default"|"flag"|"user"}`; `lenses` is a list of `{id, examine, evidence, out_of_scope, origin: "fixed"|"generated"|"user_edited"}`; `entries` is a list of `{slug, snapshot_sha256, judgment_report_id}` (brief-level ledgers only; `[]` otherwise).
- `init` with `project_dir` and neither `source` nor `text` must pass `validate_state` with `current_version: null` (needed for a brief-level ledger that holds no document); add `test_brief_level_ledger_has_no_document` to the tests below.
- `validate_result`: a new `judgment` report requires `assessment_status`, `expected_model_roles`, `review_protocol.roles`, `decision` and `lenses`; required roles are every ID in `result["lenses"]` plus `verifier` when `policy.verifier_required(findings)`; any `decision` other than `cannot_judge` requires `assessment_status == "complete"`. A new `ranking` report requires `ranked`, `unranked`, `entries`, and when `pairwise` is non-empty, role `pairwise` in `review_protocol.roles`.
- Schema-2 ledger: `status` and every other operation raise `StateError("this ledger was written by idea-autopsy-business (schema 2); it is not migrated. Use a different slug.")`.

- [ ] **Step 1: Write failing tests** in `tests/test_state.py` (replace the strategy/verdict/legacy tests; keep durability, concurrency, recovery tests as they are):

```python
def test_init_stores_brief_rewritable_and_lenses(self):
    ...  # init with brief + rewritable + lenses; status returns them unchanged; generation increments once

def test_schema_two_ledger_is_refused_not_migrated(self):
    ...  # write a state.json with schema_version 2; status raises StateError mentioning "idea-autopsy-business"; file bytes unchanged

def test_new_judgment_report_requires_all_active_lenses(self):
    ...  # result.lenses includes "mix"; review_protocol lacks "mix" → StateError; with assessment_status incomplete_coverage and decision cannot_judge → saved

def test_new_judgment_report_requires_verifier_for_decisive_findings(self):
    ...  # replaces the skipped test_new_complete_evaluation_and_stress_test_require_verifier: a decisive finding with no "verifier" role → StateError

def test_brief_level_ledger_has_no_document(self):
    ...  # init with project_dir, brief and no text → current_version null, status succeeds, snapshot later still allowed

def test_decision_other_than_cannot_judge_requires_complete(self):
    ...

def test_ranking_report_requires_pairwise_role_only_when_used(self):
    ...

def test_patch_fields_are_the_schema_three_set(self):
    ...  # patch with investment_context → StateError; patch with brief → ok
```

- [ ] **Step 2: Run** `python3 -m pytest tests/test_state.py -q`. Expected: new tests fail.
- [ ] **Step 3: Implement** the constants and validation changes; delete `_legacy` and the `import-legacy` branch; add the schema-2 refusal in `_load`.
- [ ] **Step 4: Run** `python3 -m pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(state): schema 3 with brief, rewritable, lenses and entries"`.

---

### Task 5: Router policy (`route`)

**Files:**
- Modify: `skills/_shared/policy.py:813-838` (`flag_set`), `:840-1070` (`route`)
- Modify: `tests/fixtures/workflow_cases.json` (`route_cases`)
- Test: `tests/test_policy.py`

**Interfaces:**
- Produces: `route(request) -> {"action", "reason", "pass_flags", "loop_flags", "current_version"}`.
  Intents: `auto, brief, judge, revise, rank, status, reset, stop`.
  Flags: `--brief, --entries, --examples, --critique-only, --rewrite, --loop, --verify-claims, --accept-all, --accept-none, --slug, --status, --reset`.
  State fields (a summary the router builds from the ledger, as today): `current_version` (int ≥ 1), `stage` ∈ `snapshot|brief|judgment|revision|ranking`, `has_document`, `has_brief`, `has_judgment`, `rewritable` (the ledger's `rewritable.value`, or null when undecided), `entry_slugs` (list of slugs; `entry_count` is its length), `pending_questions`, `decision` (null or decision label), `assessment_status`, `can_revise`. `pending_experiments` and `await_evidence` are gone: the spec has no experiment step, and a proposed test lives in the improvement record as prose.
  Input types: `document`, `brief`, `examples`, `judgment`.
  Actions: `ask_document, ask_input_roles, ask_rewritable, brief, judge, revise, rank, ask_user, version_limit, critique_complete, stop, status, archive_state`.
  Skill flag allowlist: `brief` → `--brief --examples`; `judge` → `--verify-claims --critique-only --rewrite`; `revise` → `--accept-all --accept-none`; `rank` → `--verify-claims`.
- Rules, in order after the administrative branch: `--critique-only` with `--rewrite` → `PolicyError`; duplicate values in `entry_slugs` → `PolicyError("entry slugs must be unique; rename a.md or a.txt")`; `entry_count > 1` with any of `--loop`, `--rewrite`, `--critique-only` → `PolicyError("rank mode judges only; it never revises")`; `entry_count > RANK_MAX_ENTRIES` → `PolicyError` naming the cap (`RANK_MAX_ENTRIES = 12` module constant; Task 10 replaces it with the value from `thresholds.json`, read once at import with `json.loads(Path(__file__).with_name("thresholds.json").read_text())`, a read the pure-policy rule allows); no brief and intent not `brief` → `brief` when `--brief` or `--examples` is present, otherwise `stop` with the interim text from Task 9 (this branch and its fixture case are removed in Task 12); `entry_count > 1` → `rank` (a ranking run routes on the brief-level ledger, which has no document, so this precedes the document check); no document → `ask_document`; `entry_count > 1` → `rank`; `rewritable is None` and intent in (`auto`, `revise`) and no overriding flag → `ask_rewritable`; `pending_questions` → `ask_user`; stage `revision` and not `has_judgment` → `judge`; `has_judgment`: `incomplete_coverage` → `stop`; `insufficient_evidence` → `stop` with reason naming the gap; `rewritable.value is False` → `critique_complete`; decision in (`not_yet`, `no`) and (`loop` or intent `revise`) and `can_revise` → revise path (version ≥ 3 → `version_limit`); decision `yes` → `stop`; otherwise `judge`.

- [ ] **Step 1: Rewrite `route_cases`** in the fixture to cover every action above at least once, including Review Focus 3 (`--entries` with one slug → `judge`) and `{entry_slugs: ["a","b","c"], has_document: false, has_brief: true} → rank`. Delete `VERDICTS` from `policy.py` in this task's step 4 (`route` is its last reader).
- [ ] **Step 2: Write failing tests** (replace skipped route tests): `test_fixture_routes` (loops the fixture), `test_revision_flags_with_several_entries_are_rejected` (each of `--loop`, `--rewrite`, `--critique-only`), `test_duplicate_entry_slugs_are_rejected`, `test_entry_cap_is_enforced`, `test_critique_only_and_rewrite_conflict`, `test_non_rewritable_judgment_ends_with_critique_complete`, `test_loop_flags_propagate_only_to_judge_and_revise`, `test_brief_action_without_brief_skill_is_a_stop_until_task_12` (see Task 9 interim rule).
- [ ] **Step 3: Run** `python3 -m pytest tests/test_policy.py -k route -q`. Expected: FAIL.
- [ ] **Step 4: Implement** the new `route` and `flag_set`.
- [ ] **Step 5: Run** `python3 -m pytest -q`. Expected: PASS, zero skips remaining in the suite (the three example-reading tests were deleted in Task 1, not skipped).
- [ ] **Step 6: Commit** `git commit -m "feat(policy): brief-driven routing with rank and critique-only paths"`.

---

### Task 6: Shared contracts and the judge standard

**Files:**
- Modify: `skills/_shared/contracts.md` (full rewrite, same section order)
- Create: `skills/_shared/judge-standard.md`
- Delete: `skills/_shared/judgment-rubric.md`

**Interfaces:**
- Produces: `contracts.md` sections: Purpose and authority; The brief; Evidence and findings (schema from Task 1, including `requirement_id` and `lens`); Lenses (fixed, generated, `lens_check`); Model policy (unchanged text, role IDs now lens IDs plus `verifier`, `derive`, `pairwise`, `fact-checker`); Judgment (derivation table from Task 2, override rules); Ranking (order from spec); Consequential changes (`scope`, `approach`); Size and coverage (unchanged); State (schema 3 shape, operations list without `import-legacy`, worked `init` example with a `brief`); Non-claims.
- `judge-standard.md`: the six "What makes a good judge" rules from the spec, each with one sentence on how a reviewer applies it and one on how the verifier checks it.

- [ ] **Step 1: Build the ledger** required by the editing-instruction-files rule: list every instruction in the old `contracts.md` and `judgment-rubric.md`, mark preserved / changed / dropped, save as `docs/superpowers/plans/ledgers/contracts-rewrite.md`.
- [ ] **Step 2: Write both files.**
- [ ] **Step 3: Verify** `command grep -nE 'Invest|Pivot|Skip|roi|pricing|business_model|target_customer|investment_context|import-legacy' skills/_shared/contracts.md skills/_shared/judge-standard.md`. Expected: no hits.
- [ ] **Step 4: Commit** `git commit -m "docs: brief-driven shared contracts and judge standard"`.

---

### Task 7: Agents

**Files:**
- Create: `agents/reviewer.md`, `agents/verifier.md`
- Rename: `agents/project-idea-validator.md` → `agents/fact-checker.md` (claims mode only; `strategy` and `standalone` modes removed)
- Delete: `agents/product-strategist.md`

**Interfaces:**
- `reviewer.md` frontmatter `tools: Read`. Body: reads `skills/_shared/contracts.md` and `judge-standard.md`; never sees the author or prior verdicts; returns results to the caller and writes nothing. It carries a role table, and the caller names the role in the dispatch:

| Role | Receives | Returns |
|---|---|---|
| `lens` (any lens ID) | the brief, one lens definition, one entry snapshot | canonical findings; for `fit`, one `requirement_record` per requirement ID; for `feasibility` and `quality`, the label |
| `derive` | the labelled example files, the user brief if any | a drafted brief in the Task 4 shape with `support` / `contradicted_by` per item |
| `pairwise` | the brief and exactly two entries | the winner or null, the reason, sources |

A `lens` reviewer never sees a second entry; only `pairwise` does.
- `verifier.md` frontmatter `tools: Read`. Body: checks every Critical/High and decision-driving finding against entry and brief; returns `doc_support` per finding and an exclusion audit.
- `fact-checker.md`: existing text with the mode table reduced to `claims`.

- [ ] **Step 1: Write the three files; delete the strategist.**
- [ ] **Step 2: Verify** each frontmatter parses and has `name`, `description`, `tools`: `python3 -c "import re,sys,pathlib;[print(p, re.match(r'---\n(.*?)\n---', p.read_text(), re.S).group(1).count('\n')+1) for p in pathlib.Path('agents').glob('*.md')]"`. Expected: three files, each ≥ 3 frontmatter lines.
- [ ] **Step 3: Commit** `git commit -m "feat(agents): general reviewer, verifier and fact-checker"`.

---

### Task 8: Lens generation check (`lens_check`)

**Files:**
- Modify: `skills/_shared/policy.py` (new operation), `tests/test_policy.py`

**Interfaces:**
- Produces: `lens_check(request) -> {"lenses": [...validated...], "rejected": [{"id", "reason"}]}`. Request: `lenses` (list of `{id, examine, evidence, out_of_scope, origin}`), `brief_text` (string). Rules: ID matches `LENS_ID`; not in `FIXED_LENSES` or `RESERVED_ROLES`; unique; `examine` and `evidence` nonempty; at most three with `origin: generated`; a lens whose `examine` contains any of `market`, `pricing`, `price`, `revenue`, `monetis`, `monetiz`, `profit`, `roi`, `customer acquisition` (case-insensitive) is rejected unless that word appears in `brief_text`. `BUSINESS_TERMS` is a module constant.

- [ ] **Step 1: Write failing tests**: `test_generated_lens_ids_cannot_collide_with_fixed_or_reserved` (Review Focus 2), `test_more_than_three_generated_lenses_rejected`, `test_business_terms_need_the_brief_to_mention_them`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_policy.py -k lens -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `lens_check` and register it.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat(policy): lens_check for generated reviewer lenses"`.

---

### Task 9: `judge` skill and router (tracer bullet)

**Files:**
- Create: `skills/judge/SKILL.md`
- Modify: `commands/autopsy.md` (full rewrite)
- Delete: `skills/stress-test-idea/`, `skills/evaluate-proposal-harsh/`, `skills/strategize-from-verdict/`, `skills/hackathon-judge/` (merged in Task 0 so it lives on in `idea-autopsy-business`; the generic judge supersedes it)
- Modify: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (version `4.0.0`, description "Judge an entry against a brief you supply: fit, feasibility, quality and an agent-written revision.")

**Interfaces:**
- `judge` skill workflow: 1 resolve entry snapshot and brief via `state.py`; if `rewritable` is null, apply the spec's default rule (the text is the deliverable → rewritable; the text describes a deliverable that exists elsewhere → not), honour `--critique-only` / `--rewrite`, ask once when unsure, and store `{value, decided_by}`; 2 build the neutral brief package; 3 generate up to three lenses from the brief, run `policy.py lens_check`, store lenses via `state.py update` (reuse stored lenses when present; if the user supplies an edited lens definition, run `lens_check` on it and store it with `origin: user_edited`, keeping the previous definition in ledger history); 4 capture `expected_model_roles` for every lens plus `verifier`, run model preflight per role, dispatch `agents/reviewer.md` per lens in parallel fresh contexts with prohibitions; 5 dispatch the verifier; optional `fact-checker` with `--verify-claims`; 6 `policy.py normalize` with `lenses`, then `policy.py judgment`; 7 save an immutable `judgment` report with `result.lenses`, `decision`, labels, findings, `requirement_results`, `review_protocol`; 8 output: brief summary, labels and decision, per-requirement table, supported findings with evidence, verification summary, the improvement record (every negative finding, consequence, smallest resolving change, blockers separately, ranked by consequence), and the next action (`revise` when rewritable, otherwise end).
- Router: inputs and flags from Task 5; resolves state, builds the `route` request, executes the returned action, routes to `brief`, `judge`, `revise`, `rank`. Interim rule, released in 4.0.0 and removed in Task 12: when the action is `brief`, the router reads `--brief PATH` itself (four headings, `R1..Rn` IDs) and stores it via `init`/`update` with every part `provenance: user`; with no `--brief` it stops with the exact text "Supply the brief with --brief PATH. The interview and example-derived briefs arrive in 4.2.0." This is tested in Task 5 as a `route_cases` entry (`brief` action with no `--brief` flag → `stop`); loop and resume rules carried over from the current router minus strategy and experiments; `archive_state` text unchanged.

- [ ] **Step 1: Write `skills/judge/SKILL.md`** (target ≤ 90 lines) and the router (target ≤ 70 lines). Delete the three old skill directories. Bump versions.
- [ ] **Step 2: Verify frontmatter ceilings**: `python3 -c "import re,pathlib;[print(p, len(re.search(r'^description: (.*)$', p.read_text(), re.M).group(1))) for p in pathlib.Path('.').glob('*/*/SKILL.md')]"`. Expected: every value ≤ 1024.
- [ ] **Step 3: Tracer bullet run.** In a scratch project under the scratchpad directory, write `plan.md` (a short hackathon project plan) and `brief.md` (goal, three requirements `R1..R3`, constraints, standard). Run `/autopsy plan.md --brief brief.md` from a Claude Code session with this worktree installed as a local plugin. Expected: `.autopsy/plan/` contains one `judgment` report whose `result.decision` is one of the four labels, `result.lenses` lists the three fixed lenses plus any generated ones, and the output includes the per-requirement table. Record the report ID in the commit body.
- [ ] **Step 4: Run** `python3 -m pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "feat: judge skill and brief-driven router"`.

**Stop here and present the tracer-bullet result before continuing.**

---

### Task 10: Ranking policy (`rank`)

**Files:**
- Modify: `skills/_shared/policy.py` (new operation), `skills/_shared/thresholds.json` (add `"rank_max_entries": 12`; `route` reads it in place of `RANK_MAX_ENTRIES`), `tests/test_policy.py`, `tests/fixtures/workflow_cases.json` (`rank_cases`)

**Interfaces:**
- Produces: `rank(request) -> {"ranked": [{"rank", "entry", "separated_by": step|null, "reason"}], "unranked": [{"entry", "reason"}], "ties": [[entries...]], "pairwise_needed": [[a, b], ...]}`. Request: `judgments` (list of `{entry, report_id, decision, fit, feasibility, quality, critical_count, high_count}`), optional `pairwise` (list of `{entries: [a, b], winner: a|b|null, reason, sources}`). More than `rank_max_entries` judgments → `PolicyError`.
  Order: decision `yes` < `not_yet` < `no` (best first); `cannot_judge` → `unranked`; then fit, feasibility, quality by label order; then `critical_count`, then `high_count`; still tied → look up `pairwise`; a null winner or no record keeps them tied (`pairwise_needed` lists pairs with no record). Ranks are dense: tied entries share a rank. `separated_by` names the first step that split an entry from the one below it: `decision|fit|feasibility|quality|critical_count|high_count|pairwise`.

- [ ] **Step 1: Add `rank_cases`** to the fixture: clear order; tie broken by pairwise; tie with null winner shares rank; all `cannot_judge` (Review Focus 4) → `ranked` empty and `pairwise_needed` empty.
- [ ] **Step 2: Write failing tests**: `test_fixture_rank_table`, `test_pairwise_needed_lists_only_unresolved_ties`, `test_pairwise_record_needs_reason_and_sources`.
- [ ] **Step 3: Run** `python3 -m pytest tests/test_policy.py -k rank -q`. Expected: FAIL.
- [ ] **Step 4: Implement** `rank` and register it.
- [ ] **Step 5: Run** the tests. Expected: PASS.
- [ ] **Step 6: Commit** `git commit -m "feat(policy): rank operation with mechanical order and pairwise ties"`.

---

### Task 11: `revise` and `rank` skills

**Files:**
- Create: `skills/revise/SKILL.md` (from `skills/iterate-to-v2/SKILL.md`), `skills/rank/SKILL.md`
- Delete: `skills/iterate-to-v2/`
- Modify: version bump (minor)

**Interfaces:**
- `revise`: today's iterate-to-v2 workflow with these substitutions: critique source is the latest `judgment` report; consequential categories `scope`, `approach`; the brief is never edited (a remedy that would need a brief change becomes a blocker in the change record); hand back to `judge`; the business remedy table replaced by three generic rows (unsupported claim in the entry, requirement partly met, constraint exceeded).
- `rank`: 1 resolve the brief-level ledger (`init` with `project_dir`, slug from the brief file name or `--slug`); 2 generate lenses once from the brief, `lens_check`, store on the brief ledger; 3 for each entry, `init` its own ledger with `rewritable: {value: false, decided_by: "default"}` (rank mode never revises, so `judge` asks no rewritable question), then compare its current snapshot hash with `entries[].snapshot_sha256` on the brief ledger; reuse the stored `judgment_report_id` when unchanged, otherwise run the `judge` skill on its own slug with the stored brief and lenses and record the new hash and report ID (so a re-rank after one revision re-judges only that entry); 4 build the `rank` request from the reports, run `policy.py rank`; 5 for each pair in `pairwise_needed`, dispatch one fresh `reviewer.md` with role `pairwise`, the brief and only those two entries, record its model, rerun `rank` with the records; 6 save an immutable `ranking` report on the brief ledger with `ranked`, `unranked`, `ties`, `entries`, `review_protocol`; 7 output the table from the spec.

- [ ] **Step 1: Write both skills** (`revise` ≤ 60 lines, `rank` ≤ 50 lines). Delete `iterate-to-v2`. Bump versions.
- [ ] **Step 2: Verify frontmatter ceilings** (command from Task 9 Step 2).
- [ ] **Step 3: Manual run**: in the scratch project, `/autopsy plan.md --brief brief.md --loop`. Expected: a `revision` report and a second `judgment` report exist; v2 snapshot differs from v1; the loop stops with a documented reason. Then `/autopsy --entries entries/ --brief brief.md` with three short entries. Expected: one `ranking` report, a table with ranks, at least one `unranked` or tie exercised.
- [ ] **Step 4: Commit** `git commit -m "feat: revise and rank skills"`.

---

### Task 12: Brief merge policy and `brief` skill

**Files:**
- Modify: `skills/_shared/policy.py` (new operation `brief_merge`), `tests/test_policy.py`
- Create: `skills/brief/SKILL.md`
- Modify: `commands/autopsy.md` (route the `brief` action to the skill), `skills/_shared/policy.py` (`route`: remove the interim `stop` branch so `brief` is returned whenever `has_brief` is false), `tests/fixtures/workflow_cases.json` (replace the interim `stop` route case with `brief`), version bump (minor)

**Interfaces:**
- `brief_merge(request) -> {"brief": {...}, "conflicts": [{"requirement_id", "user_text", "derived_text", "reason"}], "hypotheses": [...]}`. Request: `user_brief` (may be `{}`), `derived_brief` (same shape plus per-item `support: [example files]` and `contradicted_by: [example files]`), `example_count: {good: n, bad: n}`. Rules: `example_count.good < 1 or example_count.bad < 1` → `PolicyError("examples need at least one good and one bad")`; every user requirement survives verbatim with its ID; a derived requirement with the same ID or a normalised-equal text as a user one is dropped (no duplicate); a derived requirement whose `support` covers every good example and whose `contradicted_by` is non-empty becomes a requirement with `provenance: derived`; otherwise it goes to `hypotheses`; with `good == 1 and bad == 1` all derived requirements are hypotheses and `brief.weakly_supported` is `true`; derived `goal` is used only when the user's is empty and is marked `provisional`; a derived constraint or standard never replaces a user one.
- `brief` skill: 1 if `--brief` read the file, parse four headings (`Goal`, `Requirements`, `Constraints`, `Standard`), assign `R1..Rn` to requirements lacking IDs; a heading that is missing or empty is left for step 3 (partial file plus interview); 2 if `--examples`, hash every file under `good/` and `bad/` (refuse when either is empty, matching `brief_merge`), capture role `derive` in `expected_model_roles`, run the model preflight, dispatch `agents/reviewer.md` with role `derive` and the derivation instruction, record the observation under `brief.confirmation.review_protocol`, run `brief_merge`; 3 if neither, interview: goal first, then requirements one at a time until each is checkable (restate vague ones), then constraints and standard with "none" allowed; 4 play back the full brief with provenance and citations, get confirmation (recorded as a consequential decision bound to the brief hash); 5 store via `state.py` (`init` with `brief` or `update` patch); 6 return to the router.

- [ ] **Step 1: Write failing tests**: `test_derived_cannot_remove_or_weaken_user_requirement` (Review Focus 5), `test_single_pair_of_examples_marks_everything_hypothesis`, `test_missing_good_or_bad_examples_is_an_error`, `test_derived_requirement_needs_all_good_and_one_bad`, `test_derived_goal_only_fills_an_empty_one`.
- [ ] **Step 2: Run** `python3 -m pytest tests/test_policy.py -k brief -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `brief_merge`; register it.
- [ ] **Step 4: Run** the tests. Expected: PASS.
- [ ] **Step 5: Write `skills/brief/SKILL.md`** (≤ 70 lines); update the router; bump versions.
- [ ] **Step 6: Manual run**: `/autopsy plan.md` with no brief in the scratch project. Expected: the interview asks for the goal first, one question at a time, and ends with a playback before any reviewer dispatch. Then `/autopsy plan.md --examples examples-dir/` with two good and one bad file. Expected: a drafted brief with citations shown for confirmation before judging.
- [ ] **Step 7: Commit** `git commit -m "feat: brief skill with interview and example-derived rubric"`.

---

### Task 13: Examples, README, AGENTS.md, final cleanup

**Files:**
- Delete: `examples/b2b-saas-pivot/`, `examples/consumer-app-pitch/`, `examples/unsupported-tam-skip/`
- Create: `examples/hackathon-plan/` (`brief.md`, `v1.md`, `v1-judgment.md`, `v2.md`, `v2-judgment.md`, `WALKTHROUGH.md`), `examples/track-critique/` (`brief.md`, `entry.md`, `judgment.md`, `WALKTHROUGH.md`), `examples/ranked-entries/` (`brief.md`, `entries/a.md`, `entries/b.md`, `entries/c.md`, `ranking.md`, `WALKTHROUGH.md`)
- Modify: `examples/README.md`, `examples/edge-cases.md`, `README.md` (full rewrite: what it does, the three brief sources, the four labels, flags table, the two paths, ranking, install line), `AGENTS.md` (unchanged rules; update the skill list if it names skills), version bump (patch)

- [ ] **Step 1: Write the examples.** The hackathon example's brief is adapted from the rubric in the deleted `hackathon-judge` skill, read with `git show main:skills/hackathon-judge/SKILL.md` from a commit before Task 9 (or from `/home/alex/idea-autopsy-business/skills/hackathon-judge/SKILL.md`). Every example states "illustrative, not a runtime trace". The ranking example has one pairwise tie and one unranked entry.
- [ ] **Step 2: Rewrite README.** Install line: `claude plugin marketplace add z0rd0n88/idea-autopsy && claude plugin install idea-autopsy@idea-autopsy`.
- [ ] **Step 3: Verify** `git grep -nE 'Invest|Pivot|Proceed with caution|roi|investment_context|strategize|stress-test-idea|iterate-to-v2|evaluate-proposal-harsh|product-strategist|project-idea-validator|hackathon-judge' -- ':!docs/superpowers'`. Expected: no hits.
- [ ] **Step 4: Run** `python3 -m pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `git commit -m "docs: examples and README for the general judge"`.

---

### Task 14: Branch review and merge

- [ ] **Step 1:** `git diff main...HEAD --stat` from the worktree; confirm every changed path traces to a task above.
- [ ] **Step 2:** Run `zord-multi-agent-review` on the PR (per `code-review.md`), triage findings, fix with `finding-fixer`.
- [ ] **Step 3:** Merge from the primary checkout; remove worktree, local and remote branch; `claude plugin marketplace update idea-autopsy && claude plugin update idea-autopsy@idea-autopsy`; restart.

## PR grouping

| PR | Tasks | Version |
|---|---|---|
| 1 | 0 (steps 1 to 3 only; step 4 to 6 happen outside this repo) | none |
| 2 | 1, 2, 3, 4, 5, 6, 7, 8, 9 | 4.0.0 |
| 3 | 10, 11 | 4.1.0 |
| 4 | 12 | 4.2.0 |
| 5 | 13 | 4.2.1 |

PR 2 is large because `policy.py`, `state.py` and the skills cannot ship half-converted: a plugin whose policy speaks `decision` while its skills speak `Invest` is broken in both directions. Tasks inside it are still separate commits with their own tests.
