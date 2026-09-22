---
name: iterate-to-v2
description: Write a revised idea proposal and traceable change record from verified critique, asking the user for consequential choices and missing facts while handling routine corrections automatically.
---

# Iterate to the next version

Read [the shared contracts](../_shared/contracts.md) completely. Default output is a new proposal version plus its change record. The user never has to write or supply the revision.

## Help and inputs

For an entire argument of `-h`, `--help` or `help`, show the purpose, inputs and flags below, then stop.

Require the source proposal and critique, supplied directly or loaded with `--slug NAME`. Accept structured findings, a prior stress-test/evaluation report, or human notes. Optional flags: `--accept-all`, `--accept-none`; they conflict if combined. Inline finding decisions and user constraints are accepted. Neither acceptance flag approves consequential remedies or fabricated evidence.

If no critique exists, route to `stress-test-idea`. If the user expressly asks for a plan only, provide that artifact without generating a proposal; otherwise write the revision.

## Workflow

1. Resolve immutable source and selected critique through state. Read investment context, answers and exact report IDs. Reject an accidental pairing with another source/version; ask only if provenance cannot establish the intended inputs. Count source plus critique using the shared combined guard; do not omit critique findings from the count because they live in a fence or table.
2. Extract final canonical findings. Prefer the report's structured `result.findings`. For Markdown, use `policy.py normalize` with the supplied text: headings are matched independent of level, and raw reviews, summaries and recommendations are not separate evidence. Inspect legacy findings against the source; do not import old `[verified]` labels as external truth.
3. Call `policy.py acceptance` with normalized findings and explicit decisions. Show accepted, deferred, rejected and refuted IDs once. Unknown formats and unverified findings do not bypass evidence checks. Preserve the actual user rejection reason. Defer conflicting remedies locally and continue unaffected work.
4. Propose the smallest substantive remedy per accepted issue. Changes may cut, replace, add, refine or change scope; none is preferred merely because it deletes more words. Generate each immutable change ID with `policy.py change_id`, then call `policy.py gate` with changes, applicable decisions and supplied facts.
5. Ask focused questions for blocked consequential remedies or missing facts. Explain what changes, recommend an option, and state the tradeoff. Record questions and answers. Continue ready corrections. Do not make dependent choices while waiting; a fallback revision retains original scope and explicitly unresolved claims rather than silently choosing a pivot or price.
6. Write v[N+1] yourself from the authorized remedies. Preserve the original's intent and supported assets. Correct arithmetic and contradictions, restructure as needed, and mark unavailable evidence honestly. Read the actual result, check its word count and all quantitative changes, and compare against the accepted remedies.
7. Save the immutable snapshot via `state.py snapshot` with parent version and current generation, then an immutable `revision` report linking input critique report IDs. Record edits, decisions, facts, remaining risks and whether the draft is ready for evaluation. Refresh active findings/context. Return the new file and a concise change record; in a loop hand it to `evaluate-proposal-harsh`.

## Remedy versus resolution

| Situation | Valid change | Remaining assessment |
|---|---|---|
| Unsupported price assertion | Remove it or label a user-approved pricing hypothesis. | Willingness to pay remains unknown until evidence arrives. |
| Inflated market calculation | Correct units and arithmetic using attributable inputs. | Unknown population/conversion remains explicitly unknown. |
| Missing operational plan | Add concrete responsibilities and costs supported by user answers. | Proposed staffing is not a completed hire. |
| Regulatory uncertainty | Describe the unresolved question, or remove a dependent feature after approval. | Verbal feedback does not become counsel validation. |
| Unsupported growth projection | Replace with observed data if supplied, otherwise an explicit hypothesis/test. | Writing a pilot plan does not produce pilot results. |

Document growth can be justified by missing evidence or scope explanation. The shared size guard controls feasibility of review; it is not a reward for deleting facts. A claim removed from prose may remain a business risk. Keep that distinction in the change record and later evaluation.

## Questions and overrides

Consequential categories: target customer, pricing, business model, core thesis, scope, experiments/resources. The agent classifies them explicitly; the helper only enforces the supplied classification. Bind user answers to the exact proposed change. If its price, scope, description or required facts change, recompute its ID and ask again unless the existing user instruction explicitly covers that change.

`--accept-none` rejects findings by default; explicit per-finding decisions still take precedence. If no findings remain accepted, emit the rejection/decision record and retain the current version rather than manufacturing an identical v2. If all remedies are blocked and no meaningful ready edit exists, save pending questions and stop. If ready work exists, produce a clearly marked partial revision and carry unresolved issues forward. Do not spend another version solely on cosmetic polish.

## Output

Provide the generated proposal path, source/new version IDs and hashes, readiness and unresolved choices; include the returned report ID in the handoff after persistence. The change record contains:

| Finding ID | Acceptance and reason | Change ID / user decision | Edit and new location | Resolution status | Remaining risk / evidence needed |
|---|---|---|---|---|---|

Include any facts supplied by the user with their original provenance. If an input says “a regulator verbally suggested an exemption,” retain that exact limited claim; do not write “validated by counsel.” Cite exclusions and deferred issues instead of burying them.

Preserve original source and intermediate reports. Never overwrite the user's live document, prune history, invent data or require them to rewrite. A user's explicit later request can authorize a separate source update.
