# Idea Autopsy implementation plan

## Goal and authority

Implement the user's approved 34-file scope for evidence-based idea evaluation and agent-written revisions. Approval received in this conversation on 2026-09-22. Worktree: `/home/alex/idea-autopsy/.worktrees/evidence-driven-idea-loop`; branch: `feat/evidence-driven-idea-loop`; base: `02ff68fbe02b0daaf37104e7f3e6a35ed89895d9`.

No publication, PR, merge, plugin installation, original pitch changes, threshold-value changes, or automatic user-data migration. The scope document is `/home/alex/.codex/visualizations/2026/09/22/01a0ca1a-95d1-7911-b331-a978aca1dfb8/implementation-scope.md`.

## Phases

1. Read all 26 original files, verify current checkout, confirm exact scope — complete.
2. Create dedicated worktree and durable plan; define shared contracts — complete.
3. Implement policy/state/counting helpers, skill workflows, examples and packaging — complete.
4. Run focused tests, review integration, fix failures within scope — complete: 69 tests pass; both manifests validate.
5. Verify final scope and preserved files; deliver evidence and limitations — complete: approved 21 modifications and 13 additions; five preserved files byte-identical.

## Decisions

- Four business verdicts plus a separate insufficient-evidence/incomplete assessment status.
- Agent writes revisions; material choices and new facts come from the user. No invented evidence.
- Local state by default; immutable snapshots and reports, explicit legacy migration, no pruning.
- Small Python standard-library policy/state helpers; semantic judgments are supplied explicitly.
- Standalone package version 2.0.0, matching the approved breaking changes.
- Main agent owns shared contract, four skills, router, agents, README, manifests, LICENSE and planning files. Delegated work uses disjoint approved paths.

## Verification

Use unittest for policy/state/counting and fixture checks, including real-process concurrent writers. Check Markdown links, frontmatter, references, version agreement, stale workflow language, exact approved paths and preserved inputs. Structural tests do not establish model judgment quality.

## Errors

- Branch existence check returned missing ref (expected before creation); feature worktree created successfully.
