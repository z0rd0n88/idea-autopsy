# Apply the scholarly findings to Idea Autopsy

Status: approved by the user's `go`; implemented and verified on the feature worktree. Changes are uncommitted and have not been installed or published.

Base: `448d47c85897b7c1f55f6d31c6cce3bd266974c7`.
Worktree: `/home/alex/idea-autopsy/.worktrees/research-informed-evaluation`.
Branch: `feat/research-informed-evaluation`.

## Intended behavior

1. Define abstract judgments through observable criteria: the scoped commitment, cited premise, causal consequence, counterevidence, and evidence that would change the judgment. Distinguish unsupported, contradicted, and novel-but-unresolved claims. Confidence labels describe an assessment and are not calibrated probabilities.
2. Require an inside-view forecast and a documented reference-class check for material cost, time, adoption, and benefit claims. Use supplied evidence by default; existing research flags govern external lookup. Record unavailable or unsuitable comparison data without inventing base rates. Make team capability explicit when material to the commitment.
3. Preserve independent first passes and record a credible success mechanism alongside critical analysis. The verifier checks premises and causal claims; fluent explanations and repeated model agreement do not establish truth.
4. Evaluate revisions in fresh contexts with author identity and previous verdicts withheld from initial judgment. Track which changes add evidence, correct reasoning, or merely improve presentation. Missing external evidence continues to block resolution after wording improves.
5. Record model/version when exposed by the host, prompt/protocol identity, input identity, limitations, and actual review conditions. Record unknown metadata honestly. Assess order, paraphrase, irrelevant framing, verbosity, and self-preference using controlled benchmark variants; do not add mandatory repeated model calls to every ordinary review.
6. Provide an offline audit helper for recorded evaluation runs. Measure equivalent-variant verdict changes, coverage/abstention rates, agreement with independently supplied labels, and correction versus regression in revisions. Validate comparison identities and denominators. Do not combine different commitments or evidence sets as if equivalent. No fabricated model runs, accuracy figures, or universal pass thresholds.
7. Publish a validation protocol and an initially unvalidated validation card. Separate human agreement, evidence fidelity, consistency, and later business outcomes. Compare the full workflow with a single reviewer and a checklist baseline, with cost and false-positive/false-negative consequences reported.

## Exact implementation file set

Paths below are relative to this worktree. Total scope: 17 files, including this planning document.

| Path | Change |
|---|---|
| `docs/research-implementation-plan.md` | Record scope, execution progress, and validation evidence. |
| `skills/_shared/contracts.md` | Shared semantic criteria, forecasting, metadata, verification, and revision safeguards. |
| `skills/_shared/judgment-rubric.md` | New concrete criteria and contrasting examples for abstract judgments; cite the relevant papers. |
| `skills/evaluate-proposal-harsh/SKILL.md` | Apply the rubric, reference classes, constructive alternatives, and transparent uncertainty to commitment evaluations. |
| `skills/stress-test-idea/SKILL.md` | Apply the rubric and retain a testable success case alongside criticism. |
| `skills/iterate-to-v2/SKILL.md` | Distinguish evidence improvement from presentation and enforce a fresh evaluation handoff. |
| `agents/project-idea-validator.md` | Check reference-class relevance, source limits, and evidential support for semantic judgments. |
| `agents/product-strategist.md` | Assess capability, credible success mechanisms, and bounded discriminating tests. |
| `skills/_shared/evaluation_audit.py` | New standard-library helper to validate recorded runs and calculate audit metrics. |
| `tests/test_evaluation_audit.py` | Meaningful tests of metric denominators, comparison validity, missing data, and revision regressions. |
| `tests/fixtures/evaluation_audit_cases.json` | Explicitly synthetic recorded-run fixtures covering stable and unstable judgments and invalid comparisons. |
| `docs/evaluation-validation.md` | Prospective benchmark protocol, baseline conditions, outcome definitions, run format, and validation card. |
| `docs/research/2026-09-22-scholarly-review-of-proposal-evaluation.md` | Carry the existing research into this branch with source limitations and implementation mapping. |
| `docs/scholar-refs.md` | Carry the existing academic bibliography into this branch. |
| `README.md` | Explain the new review behavior and how to run the audit, with the current validation limits. |
| `.claude-plugin/plugin.json` | Bump to 2.1.0 for the new helper. |
| `.claude-plugin/marketplace.json` | Match plugin and marketplace metadata versions to 2.1.0. |

## Compatibility and verification

Keep the existing verdict categories, deterministic thresholds, and state schema. Store additional review metadata within report results, supported by the current state API. The audit is a separate analysis tool and does not silently overrule historical or current business verdicts. Existing research drafts and other worktrees remain preserved.

Verify the full existing unit suite plus the audit tests, report metadata persistence through the existing state API, helper CLI behavior, Markdown links, frontmatter length, paired package versions, and plugin validation when available. Actual live-model quality and prospective business outcomes remain unmeasured until real runs and outcome data are collected.

## Research basis

The source review covers 17 academic publications. The implementation draws chiefly on Camuffo et al. for falsifiable entrepreneurial experiments; Grove et al. for explicit decision combination; Lampinen et al. for content effects; Wang et al. and Zheng et al. for judge presentation biases; Xu et al. for self-refinement bias; Turpin et al. for explanation faithfulness; Buehler et al. for forecasting; and Mueller et al. and Berg for evaluating novel ideas. Their transfer to proposal evaluation is a design hypothesis to test, not proof of this workflow's effectiveness.

## Completed work and verification

- All 17 approved files are present in the change set; no additional source files were modified.
- The shared rubric is loaded through the common contract, covering all four workflows and both bundled agents. It makes abstract judgments auditable, adds reference-class and capability checks, protects unresolved novel ideas, and specifies fresh revision evaluation and actual review provenance.
- The offline audit validates run/label identities, rejects invalid comparisons, reports numerator/denominator/null rates, and distinguishes verdict changes, abstentions and revision corrections/regressions. References and semantic equivalence are supplied assertions; the tool does not certify them.
- The existing state schema and verdict code are unchanged. An integration test confirms additive report metadata survives persistence and reload.
- Full unit suite: **81 tests passed**, including 12 new audit test methods with malformed-input subcases, CLI error behavior and persistence coverage.
- Ruff check and format check passed for both new Python files. Markdown links, frontmatter lengths, the exact 17-file scope and package version agreement passed. All version fields are **2.1.0**.
- Marketplace and plugin validation passed. Plugin validation retains the existing warning that root `CLAUDE.md` is not loaded as runtime context; shared runtime instructions are explicitly loaded by skills.
- No live model evaluation or prospective outcome study was run. The validation card reports zero real benchmark cases and no measured judgment accuracy.

The research worktree and company-feature-proposals worktree were preserved. The implementation is ready for review at the branch above.
