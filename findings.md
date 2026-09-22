# Findings and decisions

## Source inspection

All 26 original project files were read while preparing the prompt and scope. Checkout remains at the inspected 02ff68f base with no pre-existing edits. History confirms standalone conversion and locally bundled agent definitions.

## Request traceability

| Request | Implementation surface |
|---|---|
| 1–6: verdict logic, evidence vs absence, provenance, verification, shared bias, prioritization | contracts.md, policy.py, both review skills, policy tests |
| 7–9: automatic revisions, acceptance, questions, routing/resume | policy.py, iterate skill, router, workflow fixtures |
| 10–11: state identity, preservation, concurrency, source coverage and counting | state.py, wordcount.py, shared contract, state/counting tests |
| 12–13: strategy, tool boundaries, experiments | strategy skill, both agents, contract |
| 14: illustrative examples and arithmetic | 10 existing example outputs/indexes and two new example documents |
| 15: standalone packaging and documentation | README, paired manifests, LICENSE |

## Original defects addressed

- Invest branch preempts caution; unfinished condition; missing axis can look clean.
- Document support is mislabeled external verification; refuted Criticals can block softer results.
- Repeated lenses amplify shared assumptions and recommendation count outranks blocker consequence.
- Revision defaults require founder rewrite, prioritize deletion, and permit source/pruning side effects.
- Word-count helper strips fences/headings, accepts malformed thresholds, caches only vN, and uses a shared temporary file without writer locking.
- State roots and merge policies conflict; repeat reports can overwrite.
- Examples have wrong attribution, acceptance counts, churn/LTV periods and $20,000 vs $2,880 arithmetic, plus unsupported outside-world claims.
- README package/version/agent/license claims disagree with repository contents.

## Evidence limits

Examples are labeled synthetic or user-reported. No external legal or market claims are represented as researched. All 69 deterministic tests pass; no actual model-based evaluation was performed. Reviewers still supply semantic classifications, source truth assessments, scope judgments and consequential-change categories. Helpers validate those supplied contracts, not the truth of the underlying world.

## Deliberate behavior and format changes

- Version 2.0.0: iteration now writes proposals and change records, with exact-remedy user decisions and generation-checked resume.
- Missing decisive evidence and incomplete coverage return separate statuses with no business verdict. Supported Highs prevent the old premature Invest branch.
- Immutable schema-v2 snapshots/reports replace fixed report filenames. Original files are never automatically overwritten; legacy import and crash recovery are explicit.
- The old YieldVault Skip illustration now returns insufficient evidence: its categorical legal claims were unsupported. A separate fixed-resource edge case demonstrates a justified Skip.
- Consumer Caution applies only to fictional user-approved $600/16-hour discovery; it does not approve the original raise. B2B Pivot counts one causal Critical. Worked example hashes, result fields and economics are checked by tests.
- State locks coordinate cooperating processes on one POSIX host. They are not a distributed merge protocol. Pre-journal orphan staging files remain inspectable rather than being silently deleted.
- Both manifests validate. Plugin validation warns that root CLAUDE.md is not runtime context; that preserved file is contributor documentation, and skills explicitly load contracts.md.
