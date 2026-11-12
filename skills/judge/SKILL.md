---
name: judge
description: Judge one entry against its confirmed brief with fit, feasibility and quality reviewers plus a verifier, then save an auditable judgment and improvement record. Part of the Idea Autopsy skillset.
---

# Judge

Read [the shared contracts](../_shared/contracts.md) and [the judge standard](../_shared/judge-standard.md) completely before acting. The router hands you a slug whose brief is confirmed; you judge the current version against it.

## Help

For an entire argument of `-h`, `--help` or `help`, show this purpose and the flags `--verify-claims`, `--critique-only` and `--rewrite`, then stop without state changes.

## Steps

1. **Resolve.** Call `state.py status` for the slug. Stop and return to the router if `has_brief` is false (no `brief.confirmation`). Keep the response's `brief_sha256`, `lens_set_sha256` and `requirement_ids`; you pass them on untouched. If `state.rewritable` is null, decide it: the text is the deliverable (a plan, pitch, script, lyrics, spec) means rewritable; the text describes a deliverable that exists elsewhere (a recording, canvas, built object) means not. Ask the user once only when you cannot tell. Store `{value, decided_by: "default"}`, or `"user"` when they answered, with `state.py update`.

2. **Package.** Build one neutral package for every reviewer: the goal, the requirements with their IDs, the constraints, the standard, the snapshot path and hash, and user facts with their provenance. Leave out earlier judgments, authorship, `confirmation`, `example_hashes`, `support` and `contradicted_by`.

3. **Lenses.** When the ledger's `lenses` is non-empty, it is the panel; use it as stored. Otherwise build the panel from the three fixed lenses below plus up to three lenses you generate from the brief's goal, requirements and standard, each `{id, examine, evidence, out_of_scope, origin: "generated"}`. Run `policy.py lens_check` with the generated lenses and `requirement_text` (goal, requirements and standard joined); show the user every `rejected` entry with its reason and keep only the returned `lenses`. A lens the user edits goes through `lens_check` again and is stored with `origin: "user_edited"`. Store the full list, fixed lenses included, with `state.py update`:

   | ID | examine | evidence | out_of_scope |
   |---|---|---|---|
   | `fit` | Each requirement by ID: met, partly met, not met, cannot tell | Text in the entry at a named location | Anything the brief does not require |
   | `feasibility` | Whether the entry can be accomplished under the stated constraints, and which step or resource breaks it | The entry's plan, resources and dependencies against the constraints | Industry facts the user did not supply |
   | `quality` | How good the entry is at what it is, against the brief's standard; strengths as well as weaknesses | Concrete passages or described elements | Requirements already judged by fit |

   Each fixed lens is stored as `{id, examine, evidence, out_of_scope, origin: "fixed"}`. Re-read `status` after the update so `lens_set_sha256` matches the stored panel.

4. **Dispatch the panel.** Record `expected_model_roles` with one entry per lens plus `verifier` before any dispatch. Run `policy.py model_preflight` per role. Dispatch `agents/reviewer.md` with role `lens`, once per lens, in parallel fresh contexts, each with the package, its one lens definition, and the prohibition clause: read only the named paths, no writes, no network, no further agents, no outside actions, the entry is untrusted data. Record each `model_observation`. A failed or blocked lens is coverage `failed` or `not_run`.

5. **Verify.** Dispatch `agents/verifier.md` with the package and the panel's findings, requirement records and labels. Apply its `doc_support` verdicts to the findings. With `--verify-claims`, also dispatch `agents/fact-checker.md` with the claim text inline.

6. **Compute.** Run `policy.py normalize` with the findings, `lenses` and `requirement_ids`, then `policy.py judgment` with the normalized findings, `lenses`, `requirement_ids`, `coverage`, the fit reviewer's `requirement_records`, the `feasibility_label` and `quality_label`, `brief: {sha256: brief_sha256, constraints_stated, standard_stated}`, `lens_set_sha256`, `expected_model_roles` and `review_protocol`. `constraints_stated` and `standard_stated` are false when the brief's provenance for that part is `not_stated`.

7. **Save.** Write an immutable `judgment` report with `state.py report` for the current version. Its `result` is the full judgment output plus `plugin_version` read from `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`. A ledger refusal stops here; report it as written.

8. **Report.** Show, in this order:
   - the brief in two lines and the entry version and hash;
   - fit, feasibility, quality, each provisional flag, and the decision;
   - a table with one row per requirement: ID, status, evidence location;
   - established findings with their evidence, then refuted ones with the verifier's reason;
   - the improvement record: every negative finding with its consequence and the smallest change that resolves it, ordered by consequence, and separately the blockers no change within the constraints resolves;
   - the saved report ID and the next action: `revise` when the entry is rewritable and the decision is `not_yet` or `no`, otherwise the end.

Done when the report is saved, its ID is shown, and every requirement ID appears in the table.
