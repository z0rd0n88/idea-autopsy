---
name: evaluate-proposal-harsh
description: Assess whether a product or business proposal supports a stated commitment, using verified reasoning, explicit evidence gaps and an auditable Invest, Caution, Pivot or Skip decision.
---

# Evaluate proposal

Read [the shared contracts](../_shared/contracts.md) completely. The historical skill name remains compatible; accuracy and usefulness govern the evaluation, not harshness.

## Help and inputs

For an entire argument of `-h`, `--help` or `help`, show this purpose and input/flag summary, then stop without state changes.

Accept a document, pasted substantive idea, or `--slug NAME`. Optional context: decision being made, budget, time, team, existing alternatives and `--verify-claims`. Default research is off. Reload stored context; ask a focused question if the decision cannot be evaluated without it. Do not silently replace a large commitment with a smaller one.

Non-business material needs an appropriate explicit decision scope; mark irrelevant lenses not applicable in the explanation. Do not claim full four-axis coverage if a required axis was not assessed. A document's length or lack of TAM is not a fatal flaw.

## Workflow

1. Resolve and read the immutable source, its hash, user constraints and answers through `state.py`. A changed file is a new version; a repeated review is a new report on the same version. Prior results are history, not a veto on reassessment: changed evidence, context or a discovered review error can justify a new evaluation even with identical prose.
2. Read all source evidence and run the shared count/coverage check. Ask for a scoped excerpt only when necessary; never discard appendices or fenced material by heading or formatting. Prepare one neutral shared brief with the source and user facts, separate from previous reviewer conclusions.
3. Dispatch four fresh, parallel reviewers using the lenses below. Explicitly prohibit web, writes, additional agents and outside actions. If a reviewer fails, record its real coverage status. Respect denied operations; do not disguise their intent to retry.
4. Dispatch a fresh verifier for Critical/High and all potentially decision-driving findings. It checks support and counterevidence against the source. Remove refuted findings from the active set and recompute, even when the result becomes more favorable. Preserve the exclusion audit.
5. Optionally use `project-idea-validator` in `claims` mode for authorized external checking. Claims contradicted by a source may produce a new finding, which must itself be normalized and checked. Distinguish original claim verification from evidence supporting the resulting criticism.
6. Normalize causal findings with `policy.py normalize`; supply explicit evidence-backed severity resolutions for conflicts. Build the verdict request and run `policy.py verdict`. Render its mechanical result and assessment status faithfully.
7. Save an immutable `evaluation` report with the request's normalized evidence, coverage, result, exclusions and any override audit. Include input report IDs for longitudinal comparison. Persist active context/findings through generation-checked state updates.

## Reviewer lenses

All reviewers use the canonical finding schema. They may return no issues; they also identify supported assets and counterevidence. Outside-world estimates remain unverified unless attributable evidence is provided. Reviewer count does not set severity.

| Axis | Examine |
|---|---|
| `critical_thinking` | Thesis logic, unsupported categorical assertions, alternative explanations, falsifiability, definitions, and contradictions in the source. |
| `feasibility` | Scope versus actual time/capital/team, explicit dependencies, delivery and ongoing operations. Stress assumptions transparently; do not invent industry productivity facts. |
| `risk` | What can defeat the scoped commitment, mitigations, recovery, concentration and acknowledged versus unexamined uncertainty. Legal uncertainty is not a legal ruling. |
| `roi` | Stated benefits versus costs and alternatives, units and periods, gross margin, adoption assumptions, plausible ranges and opportunity cost. Absence of numbers limits confidence, not automatically viability. |

## Decision table and evidence

Apply the shared judgment rubric before building the verdict request. Record each decision-driving classification and its counterevidence in `result.judgment_audit`, material forecasts and comparator limits in `result.forecast_checks`, and a credible success mechanism with unresolved assumptions in `result.success_case`. Assess team capability explicitly where material. An unavailable reference class is a stated limitation, not an automatic failure.

Record the actual review setup in `result.review_protocol`. For an agent-written revision, keep author attribution and prior verdicts out of first-pass reviewer and verifier inputs, then compare previous findings after the fresh assessment. Do not remove relevant facts to achieve blinding. If fresh review is unavailable, disclose that limitation and actual coverage; never claim independence. Measure presentation sensitivity through the separate validation protocol, not invented repeat-run results.

The shared contract and executable policy replace severity-vote pseudocode. Pass all four coverage states, canonical findings, decision evidence and documented reusable assets. `decision_evidence.sufficient` needs a rationale and source references supporting the requested commitment.

- Incomplete coverage yields `incomplete_coverage` with no business verdict.
- Missing decisive evidence yields `insufficient_evidence` with no business verdict. State what to obtain.
- Zero supported Criticals with unresolved blocking Highs yields Proceed with caution.
- Zero supported Criticals or blocking Highs plus sufficient positive decision evidence yields Invest.
- One supported broken thesis with documented reusable assets and clean, complete Feasibility can yield Pivot.
- One supported, plausibly resolvable non-thesis Critical can yield Proceed with caution.
- An unresolvable Critical or multiple distinct supported Criticals yields Skip.

Never treat an omitted axis as passing, an unsupported assertion as a supported Critical, or repeated views of one cause as several deal-breakers. A rule override must show both the mechanical and reported verdict, reason and source evidence. It cannot fill missing coverage or evidence. There is no arbitrary override quota.

## Experiment or flip-condition

For any non-Invest result, identify the smallest useful next evidence step if one exists. Give the thesis, hypothesis, artifact, measurement method, threshold rationale, time window, resource cost, pass/fail decision and required user choice. Label proposed dates and thresholds rather than manufacturing commitments.

A Pivot test must say whether it could revive the original thesis or supports an alternative. Do not promise that evidence for one validates the other. If no viable test fits the accepted scope and resources, explain that limitation without claiming universal impossibility.

## Output

Use concise headings for:

1. Decision context, source version/hash and coverage; include the returned report ID in the handoff after persistence.
2. Assessment status, mechanical verdict and reported verdict (or null).
3. Supported causal findings, their evidence and severity rationale; unresolved decision-critical questions separately.
4. Verification summary, refuted IDs, source limitations, shared assumptions and counterevidence.
5. Rule explanation and any explicit override.
6. Next experiment/choice and the resulting decision if it passes or fails.
7. Changes since the previous assessment, mapped by stable finding ID.

Do not soften a finding for approval or exaggerate it for decisiveness. If new evidence corrects the previous review, say what changed. In a loop, return the result to the router: the agent can revise further when a substantive authorized change exists, but cannot replace an experiment with additional prose.
