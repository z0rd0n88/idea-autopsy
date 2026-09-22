---
description: Route an idea through evidence-based review, user decisions, agent-written revisions and assessment, resuming from preserved state.
argument-hint: "[doc or --slug NAME] [--loop|--status|--reset] [--verify-claims|--validate] [--accept-all|--accept-none]"
---

# Autopsy router

Read [the shared contract](../skills/_shared/contracts.md) before acting. Route to exactly one skill per step; in loop mode repeat completed steps until a documented stop. Never produce a substitute review yourself.

## Inputs and flags

Accept a source path, pasted idea, typed source+critique or source+assessment inputs, or slug-only state lookup. Determine each input's role from its content and the user's instruction. Two paths alone do not establish that one is a critique. Ask one focused clarification if roles or intent remain ambiguous.

| Flag | Meaning |
|---|---|
| `--slug NAME` | Resolve an explicit safe ledger slug. |
| `--status` | Read-only status; no skill, source copy, initialization or migration. |
| `--reset` | Archive the exact resolved ledger after user confirmation, then exit. Never recursively delete it. |
| `--loop` | Authorize stress test → questions if needed → agent revision → evaluation, with a three-version cap across resumes. |
| `--verify-claims` | Scoped external claim checks in review skills only. |
| `--validate` | Scoped external strategy checks only. |
| `--accept-all`, `--accept-none` | Revision finding defaults; mutually exclusive, and neither approves consequential remedies. |

Validate combinations through `policy.py route`. Do not silently drop incompatible flags or infer permission for an inapplicable research mode. `quit` or an explicit stop ends the loop.

## Resolve, inspect and route

1. Resolve source/slug and call `state.py status` if state exists. For pasted/no-state material, classify intent before creating state. If a source is already in `.autopsy/<slug>`, use that ledger. Never create nested state or resolve a pasted idea against an arbitrary earlier slug.
2. Normalize intent: `auto`, `stress_test`, `revise`, `evaluate`, `strategy`, `status`, `reset`, `stop`. Explicit user intent beats state defaults; identify the named source version rather than substituting a later file.
3. Build `policy.py route` request with typed `inputs`, literal `flags`, and a summary of stored state. Convert `vN` to integer N, using 1 for a new source. Derive stage and inputs from ledger records/report results. Do not infer completion from an orphan file.
4. State summary includes `current_version`, `stage`, `has_document`, `has_critique`, `has_verdict`, pending questions/experiments, assessment status, verdict and `can_revise`. Derive stage, inputs and assessment fields for the selected current version only; a v1 verdict cannot substitute for evaluating v2. Derive `has_verdict` from an evaluation assessment report even when the honest business verdict is null, so strategy can address evidence gaps. Carry applicable pending questions and experiments across versions. `can_revise` requires an identified substantive remedy, not a wish for a better verdict.
5. Execute the returned action and propagate `pass_flags`; preserve `loop_flags` for later steps. For `ask_document`, `ask_intent` or `ask_input_roles`, ask only the missing question. For `ask_user`, surface the recorded consequential choices with recommendations. For `await_evidence`, name the artifact needed. Do not ask the user to rewrite.
6. Invoke the chosen skill by its registered/namespaced name; if needed read its bundled SKILL.md and follow it through the host's skill mechanism. Pass source/report IDs, original request, approved context, slug and permitted flags. One brief routing line is sufficient.

## State-derived defaults

| Completed state | Next meaningful action |
|---|---|
| New source/snapshot | Stress test, unless explicit intent selects evaluation. |
| Stress test with final findings | Agent revision; ask only if dependent choices/facts are missing. |
| New agent-written revision | Evaluate it. |
| Pending consequential question | Resume after an applicable answer; routine independent work can continue within the revision skill. |
| Pending external experiment | Await results; do not substitute prose. |
| Complete Invest | Stop the review loop; explicit strategy can sequence the supported proposal. |
| Complete Caution, Pivot or Skip | Revise only if the user/loop authorizes an identified substantive remedy; otherwise stop or follow explicit strategy intent. |
| Insufficient evidence/incomplete coverage | Name the missing evidence/reviewer and do useful authorized work; no invented business verdict. |
| Strategy with selected remedy | Agent revision if within the cap; pending choice otherwise. |
| Version cap reached | Stop automatic new versions; explicit evaluation/status of existing versions remains available. |

Use the executable result if a combination requires more detail than this table. A default must never override an explicit request to reassess, revise or strategize.

## Loop and resume

`--loop` does not request a founder-written v2. The router invokes stress test, then iteration. The iteration skill calculates remedy IDs, asks consequential questions, saves answers, drafts the next version and writes its change record. Evaluate that generated version.

At each return, reload state and select the next action from actual completed reports. Carry pending experiments and questions across sessions. A response to a saved question must be applied to its exact remedy before continuing. A new message that changes the remedy needs a new gate; silence is not approval.

Never restart at v1 because the user says continue. Never create an identical version because all findings were rejected, all changes are blocked, or only cosmetic work remains. Record lack of substantive progress and stop. Three total versions is the default loop cap; do not evade it with new slugs. A user may explicitly start a separately scoped cycle.

## State writes and reset

The selected skill's parent owns state writes through `state.py`; subagents return results. Reports have unique IDs and snapshots are immutable. Record source hashes, coverage, user decisions and inputs. Keep historical contradictions visible, rather than choosing whichever verdict is newer.

For `archive_state`, first show the exact resolved source and timestamped archive destination and get confirmation. Ensure neither is a symlink escape or broad directory, no writer transaction is active, and no concurrent run owns the ledger. If exclusive access cannot be established, stop. Move that one ledger directory recoverably, confirm its new path, and exit. Do not initialize another ledger in the same invocation.

Do not auto-commit private state, migrate legacy data, overwrite the user's source, prune artifacts, publish, install plugins, or disguise a refused action.
