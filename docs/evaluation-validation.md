# Evaluating the evaluator

The judgment rubric improves how reviews are conducted; its effectiveness remains unmeasured. This protocol separates evidence fidelity, repeatability, human agreement, revision quality and prospective business outcomes. The offline helper calculates descriptive metrics from supplied records and cannot establish their truth.

## Current validation card

| Item | Status |
|---|---|
| Review protocol | `judgment-rubric-v1`, plugin 2.1.0 |
| Model/version evaluated | None; no live model benchmark has been run |
| Real proposal sample | 0 |
| Blinded human agreement | Not measured |
| Presentation / self-preference bias | Not measured |
| Business outcome prediction / decision benefit | Not measured |
| Existing validation | Deterministic policy/state tests and synthetic audit fixtures only |
| Supported scientific claim | Research-informed decision support; no calibrated probabilities or validated verdict thresholds |

Update the card only with actual dated results, model and prompt identities, domain, case count, sampling method, cost and limitations. Keep synthetic fixture output separate from measured results.

## Collect a useful benchmark

1. Define the target decisions and error costs before collecting results. Keep prototype, discovery, full-build and funding commitments separate. Include viable, contradicted, missing-evidence, novel and out-of-domain cases. Use consented/redacted material and reserve a held-out set by proposal, not paraphrase.
2. Freeze each proposal, evidence packet, decision constraints, source hash, model/version, prompts and decoding settings. Record unknown values instead of guessing. Predeclare repetitions, transformations, comparison rules and acceptable error costs; choose sample size for the required precision. No universal sample size or pass rate is prescribed here.
3. Obtain independent, blinded expert assessments before exposing model results. Label the specific claim support, severity, coverage, status and decision; retain disagreements, provenance and adjudication. Do not use the same model's answer as its own reference. Human agreement is a separate target from later success.
4. Run the full workflow, a single reviewer, and a plain checklist on the same cases and supplied evidence. Record actual availability and costs. Ensure any external research condition is matched and authorized. A comparison of unequal evidence access does not isolate review method quality.
5. Make controlled equivalent variants: reorder material, paraphrase without changing facts, change irrelevant enthusiasm or attribution, or vary verbosity while preserving qualifiers and evidence. A human checks semantic equivalence and records its reason/source. Hold substantive context, model and protocol fixed. Record randomization and blinding; remove the previous verdict from initial evaluation. Attribution variants change only the displayed author/model label and do not establish a cause from one pair.
6. Compare original and revised proposals with blinded raters and fresh reviewers. Separate newly obtained evidence, corrected reasoning, changed scope and presentation. References must match each exact version and evidence set. A more favorable verdict alone is not improvement; record corrections, regressions, unresolved gaps and domain-specific expert assessments of proposal quality.
7. Prospectively record chosen action, later evidence/outcome, horizon, costs and context changes. Predefine success for the actual decision. Missing follow-up is missing data. Historical hindsight and selectively followed successes cannot establish prediction quality; decisions themselves affect outcomes. Estimate causal decision benefit only with a suitable controlled study.

Inspect sourced findings directly: unsupported assertion rate, lost qualifiers, missed counterevidence, and incorrectly resolved issues. Human review is required for these semantic measures. Audit error correlations across reviewers; fresh contexts or different personas alone do not prove independence. Report results by commitment, domain, model, protocol and transformation, including uncertainty and failures. Repeated observations from one proposal are dependent; use proposal-level uncertainty analysis in any subsequent statistical study.

## Offline audit

```bash
python3 skills/_shared/evaluation_audit.py --request tests/fixtures/evaluation_audit_cases.json
python3 skills/_shared/evaluation_audit.py --request /absolute/path/recorded-runs.json
```

The first command uses synthetic data and is a functionality demonstration. The helper also accepts JSON on stdin, writes JSON to stdout, makes no network/model calls, and never updates a ledger or verdict. Invalid records fail with nonzero exit and no success output. Run one model/protocol/condition group per request; use separate outputs for baseline comparisons.

Request shape: `schema_version: 1`, `data_kind: synthetic|recorded`, `runs: [...]`, `comparisons: [...]`. Empty arrays are allowed and produce null rates. Unknown fields are rejected.

| Run field | Meaning |
|---|---|
| `id` | Unique run identity within the request |
| `case_id` | Stable proposal family identity |
| `decision_id` | Identity for the exact commitment and constraints; change it if scope changes |
| `evidence_id` | Identity for the substantive evidence packet, including dates/qualifiers; freeze it separately from wording |
| `source_hash` | Actual lowercase SHA-256 of the evaluated proposal; fixtures use synthetic hashes |
| `model` | Actual model/version and relevant decoding setup identifier, or `unknown` |
| `protocol_id` | Exact prompt/protocol/configuration identity, or `unknown`; include a hash for recorded prompts |
| `condition` | `full-workflow`, `single-reviewer`, `checklist`, or another predeclared condition |
| `assessment_status`, `verdict` | Existing policy status and verdict; only `complete` has a non-null verdict |
| `coverage` | All four axes mapped to `complete`, `partial`, `failed`, or `not_run` |
| `reference` (optional) | Independently supplied status/verdict plus `source`, `independent: true`, and matching `source_hash`, `decision_id`, `evidence_id` |

Any incomplete coverage requires `incomplete_coverage` and a null verdict. `insufficient_evidence` has complete review coverage and a null verdict. A `complete` status requires one of the four business verdicts. Missing reference labels are excluded from agreement denominators and counted explicitly. References are expert decision labels, not observed business outcomes relabeled as verdicts.

Each comparison contains `kind`, `before`, `after` (run IDs), `reason` and `source` for the equivalence or revision assessment. Comparison pairs require the same case, commitment, model, protocol and condition. Unknown model/protocol identities can be recorded but cannot support controlled comparisons. Duplicate pairs, including reversed duplicates, are rejected.

- `kind: equivalent` additionally requires the same evidence identity and a `transform`: `order`, `paraphrase`, `framing`, `verbosity`, `attribution`, or `repeat`. Repeat requires the same source hash. Other transforms may change bytes while preserving meaning. The helper trusts the supplied equivalence assessment; it cannot inspect meaning.
- `kind: revision` requires a changed source hash and no `transform`. Evidence may change, but reference labels must match each version. A changed commitment needs a separate case analysis; it cannot be credited as a correction for the original decision.

| Metric | Denominator and interpretation |
|---|---|
| `coverage_complete` | All runs; fraction with every required axis complete |
| `abstention` | All runs; fraction with null verdict, whether evidence or coverage is missing |
| `reference_agreement` | Labeled runs only; exact status/verdict match, not business accuracy |
| `equivalent_outcome_changes` | All equivalent pairs; status or verdict changed |
| `equivalent_verdict_changes` | Equivalent pairs with both assessments complete; business verdict changed |
| `revision_corrections` | Revision pairs labeled at both ends; mismatch became match |
| `revision_regressions` | Revision pairs labeled at both ends; match became mismatch |

Each metric returns numerator, denominator and rate (`null` for denominator zero). Per-pair results expose abstention transitions and unlabeled revisions. Do not treat a high abstention rate as automatically good or bad; examine cases and error costs. Stratify transformations with separate requests when useful. No scalar quality score, automatic approval, confidence calibration, or significance claim is generated.

## Runtime provenance and research mapping

The [judgment rubric](../skills/_shared/judgment-rubric.md) defines additive report metadata. Existing state schema 2 persists it in `result`; older reports remain valid historical records. The audit request is an explicit export of selected recorded reports plus independent references and comparisons, not a new ledger schema. Never infer missing protocol identities or labels while exporting.

The [scholarly review](research/2026-09-22-scholarly-review-of-proposal-evaluation.md) explains supporting evidence and transfer limits. Content and presentation checks respond to Lampinen, Wang and Zheng; fresh revision assessment responds to Xu; evidence-based verification responds to Turpin; reference classes respond to Buehler; constructive alternatives respond to Mueller and Berg; falsifiable experiments respond to Camuffo. These papers motivate tests and safeguards, not invented weights or changes to current verdict thresholds.
