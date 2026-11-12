---
description: Judge an entry against a brief you supply, revise it when it is rewritable, and resume from saved state.
argument-hint: "[entry] [--brief PATH] [--slug NAME] [--loop] [--critique-only|--rewrite] [--verify-claims] [--accept-all|--accept-none] [--status|--reset]"
---

# Autopsy router

Read [the shared contracts](../skills/_shared/contracts.md) before acting. Route to exactly one skill per step; never write a substitute review yourself.

## Inputs and flags

| Flag | Meaning |
|---|---|
| `--brief PATH` | Read the brief from a file with `Goal`, `Requirements`, `Constraints` and `Standard` headings. |
| `--slug NAME` | Select a saved entry. |
| `--loop` | Judge, revise and re-judge until a stop, within `max_versions`. |
| `--critique-only`, `--rewrite` | Force the critique path or the revision path for this entry. |
| `--verify-claims` | Scoped claim checks by the fact-checker. |
| `--accept-all`, `--accept-none` | Revision finding defaults; neither approves a consequential remedy. |
| `--status` | Read-only progress and next action. |
| `--reset` | Archive the resolved ledger after confirmation, then exit. |

`--entries` and `--examples` are recognised and answered by the route policy with their release notes.

## Steps

1. **Resolve the slug.** With `--slug`, use it. With an entry path, run `state.py list-files` on its parent directory and take the matching row: its `slug`, and the guarantee that the entry is a regular file and not a symlink.
2. **Summarise state.** If the ledger exists, call `state.py status` and build the route summary exactly as the contracts' State section defines it, from the returned `state` and report results.
3. **Route.** Call `policy.py route` with the normalized `intent`, typed `inputs`, the literal `flags` and the summary. Explicit user intent beats stored defaults.
4. **Persist an override.** When the result's `rewritable` is not null, write it with `state.py update` and the freshly read generation before acting.
5. **Act on the result:**
   - `brief`: read the `--brief` file (regular file; check with `list-files` on its parent). Parse the four headings; requirements without IDs get `R1`, `R2` and so on; a missing or empty `Constraints` or `Standard` is recorded as `not_stated`. A missing `Goal` or `Requirements` stops with "the brief needs a Goal and a Requirements heading". Every part has `provenance: user`. Create the ledger with `state.py init` (entry as `source`, the brief with `confirmation: null`); if the ledger already exists with an unconfirmed brief, patch the brief instead. Then confirm it with `state.py update`, setting `confirmation` to `{decision_id: "brief-file", brief_sha256: <brief_sha256 from that response>, review_protocol: {roles: []}}`. Route again.
   - `judge` or `revise`: invoke that skill with the slug, `pass_flags` and any caller model requirement exactly as supplied.
   - `ask_document`, `ask_input_roles`, `ask_user`: ask only the missing question.
   - `critique_complete`: show the latest judgment's improvement record; this entry is not rewritten.
   - `stop`, `version_limit`: show the returned reason word for word.
   - `status`: show the summary; create nothing.
   - `archive_state`: show the exact ledger path and a timestamped archive destination, get confirmation, check that neither is a symlink and no transaction is pending, move that one directory, confirm its new path, and exit.
6. **Loop.** With `--loop`, after each skill returns, reload `status` and route again. Stop on any action other than `judge` or `revise`.

A resumed run whose `--brief` file parses to a brief different from the stored one (ignoring `confirmation`) stops with "the brief on this slug is fixed; start a new slug". Never restart a slug at v1, never create a version that changes nothing, and never commit `.autopsy/`.
