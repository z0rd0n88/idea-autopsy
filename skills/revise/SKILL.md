---
name: revise
description: Write the next version of a rewritable entry and its change record from the latest judgment, asking about scope and approach choices and handling routine ones. Part of the Idea Autopsy skillset.
---

# Revise

Read [the shared contracts](../_shared/contracts.md) completely. The router hands you a slug whose entry is rewritable and whose current version has a `judgment` report. Output is a new entry version plus its change record; the user never writes the revision.

## Help and inputs

For an entire argument of `-h`, `--help` or `help`, show this purpose and the flags `--accept-all` and `--accept-none`, then stop without state changes. The two flags conflict if combined; inline per-finding decisions and user facts are accepted. Neither flag approves a `scope` or `approach` remedy or fabricated evidence.

## Workflow

1. **Resolve.** Call `state.py status` for the slug. The critique is the latest `judgment` report for `current_version`; stop and return to the router when there is none. Read the brief, decisions, questions and facts from the ledger. Count the entry plus the judgment report with the shared combined guard.
2. **Findings.** Take the judgment's `result.findings` and `requirement_results`. Treat earlier labels and verifier verdicts as recorded facts, never as external truth.
3. **Accept.** Call `policy.py acceptance` with the findings and the explicit decisions. Show accepted, deferred, rejected and refuted IDs once, with the user's actual reason. Defer a conflicting remedy and continue the rest.
4. **Remedies.** Propose the smallest substantive change per accepted finding; cutting, replacing, adding or rephrasing are equal, none wins for deleting more words. The brief is never edited: a remedy that needs the brief to change is a blocker in the change record, not a change. For each change call `policy.py change_id` with `{category, description, required_facts}` (`routine`, `scope` or `approach`), then `policy.py gate` with the changes, decisions and facts.
5. **Ask.** For each blocked `scope` or `approach` change or missing fact, explain what changes, recommend an option and state the tradeoff. Record the question and answer. Continue the ready changes meanwhile; do not make dependent choices while waiting. A fallback revision keeps the original scope and marks unresolved claims explicitly.
6. **Write.** Draft v[N+1] yourself from the authorized changes, preserving the entry's intent and supported content. Correct arithmetic and contradictions; mark unavailable evidence honestly. Re-read the result and compare it with the accepted remedies and the word count.
7. **Save.** `state.py snapshot` with the next version, its parent and the freshly read generation, then a `revision` report whose `input_report_ids` lists the judgment report ID. Return to the router, which routes to `judge`.

## Remedy versus resolution

In `result.revision_changes`, classify each change as `evidence_added`, `reasoning_corrected`, `presentation_only` or `authorized_scope_change`, linking the finding ID, change ID, old and new locations and sources. Record model and prompt provenance in `result.review_protocol`. Better prose alone does not resolve a missing requirement.

| Situation | Valid change | Remaining assessment |
|---|---|---|
| Unsupported claim in the entry | Remove it, or restate it as a claim with the evidence the user supplied. | The claim stays unestablished until evidence arrives. |
| Requirement partly met | Add the missing element from supplied facts, or state plainly what is still missing. | A described element is not a delivered one until judged. |
| Constraint exceeded | Cut or rescope the part that breaks the constraint, after approval when scope changes. | The constraint is the brief's; it cannot be loosened here. |

Growth is justified by missing evidence or scope explanation, never by padding; the size guard is not a reward for deleting facts.

## Questions and overrides

Bind each user answer to the exact change ID. If the change's description, scope or required facts move, recompute its ID and ask again unless the existing instruction covers it. `--accept-none` rejects by default; explicit decisions still win. If nothing stays accepted, write the decision record and keep the current version. If every change is blocked and no ready edit exists, save the questions and stop. If ready work exists, save a clearly marked partial revision and carry the rest forward. Never spend a version on cosmetic polish.

## Output

Show the new file path, the source and new version IDs and hashes, readiness, the blockers and unresolved choices, and the saved report ID. The change record:

| Finding ID | Acceptance and reason | Change ID / user decision | Edit and new location | Resolution status | Remaining risk / evidence needed |
|---|---|---|---|---|---|

Keep user-supplied facts with their original provenance and exact wording. Preserve the source and every earlier report; never overwrite the user's live file, prune history, invent data or ask them to rewrite.
