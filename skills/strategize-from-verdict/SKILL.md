---
name: strategize-from-verdict
description: Develop evidence-grounded strategic options from an idea assessment, ask for consequential choices, and hand the selected path to the agent for an automatic revision.
---

# Strategize from assessment

Read [the shared contracts](../_shared/contracts.md) completely. Accept a prior assessment, including an honest insufficient-evidence result; do not invent a business verdict to unlock strategy.

## Help and inputs

For an entire argument of `-h`, `--help` or `help`, show the purpose and options, then stop.

Input: assessment plus findings, passed directly or resolved by `--slug NAME`. Optional: additional user-reported assets/constraints and `--validate` for scoped research. No assessment means first obtain an evaluation appropriate to the user's decision; a stress-test critique alone is not an investment assessment.

## Workflow

1. Read the exact source, assessment, finding IDs, coverage, context and prior decisions from state. Extract supported assets, unresolved blockers, the original thesis, current experiments and what would change the decision. Missing evidence is an anchor for investigation, not proof that the thesis is dead.
2. Resolve `product-strategist`: registered/namespaced agent first, otherwise the bundled `agents/product-strategist.md` via a general-purpose agent. Read the full body, inspect the effective definition's model pin and run the shared caller-model preflight before either dispatch path. Pass an available required `model_argument` explicitly to the host. Pass the shared contract plus explicit prohibitions on web, writes, extra agents and external actions; frontmatter restrictions do not survive a paste automatically. If the definition is missing, name the exact missing path and stop rather than silently substituting an unrelated persona. Record a blocked mandatory role as incomplete coverage.
3. Request up to three concrete options, each naming its customer, problem, offering, reused asset, finding IDs addressed, remaining/new risks, reachable first customer group, resource requirements and first test. Zero or one option is valid. Compare asset fit, blocker consequence, customer access and effort with explained tradeoffs; no undefined numeric ranking.
4. With `--validate`, apply the same model-policy preflight and observation to the validator in `strategy` mode and authorize only the selected query material. It returns claim-level sources and limits; it never writes shared state. Without the flag, external claims remain unchecked. Competitors can demonstrate demand or switching challenges; presence alone does not disqualify an option.
5. Check each option against the original findings and user constraints. If evidence refutes a prior blocker, request reassessment and record the reason. Do not suppress new evidence to preserve an earlier verdict. Do not claim avoiding an untested premise establishes the new thesis.
6. Recommend one path when supported. Ask the user before selecting a different customer, price, model, thesis, scope or experiment commitment. Compute/gate consequential changes using the shared policy; preserve the answers and unresolved facts. Do not assume a recommendation is permission.
7. Save an immutable `strategy` report with ranked options, evidence, finding mappings, pending decisions and each dispatched or blocked role in `result.review_protocol.roles`. If a mandatory strategist or decision-driving validator model requirement is unconfirmed, disclose incomplete coverage and withhold an unqualified recommendation. Once the user selects a path, provide that decision and findings to `iterate-to-v2`, which writes the next proposal automatically. In a loop, respect the same version cap and resume point.

## Special cases

- Invest: sequence the supported thesis; no forced pivot alternatives.
- Insufficient evidence: prioritize a feasible evidence request or discovery option; no definitive strategy claims from missing data.
- Skip: options must address the actual established blockers under a user-approved scope change. If none fits, say so.
- Thin asset inventory: ask if the missing facts determine viable options; otherwise proceed with explicit limitations.
- Platform expansion: optional and justified only by the specific opportunity.
- Alternative thesis: its test is distinct from reviving the original proposal.

## Output

Include source version/hash, assessment status and decision context; include the returned report ID in the handoff after persistence. Present anchors, ranked options, evidence and tradeoffs, recommendation (if any), user choices and the first proposed experiment.

For each experiment include hypothesis, original/alternative thesis, artifact, measurement method, threshold rationale, resources, time window and pass/fail decision. Mark it proposed until the user authorizes the commitment. No research flag authorizes conducting it.

End with the next concrete action: obtain an answer/evidence, reassess a contradicted blocker, or have the agent write the selected revision. Never ask the user to draft v2.
