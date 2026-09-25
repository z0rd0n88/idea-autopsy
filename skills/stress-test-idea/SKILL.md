---
name: stress-test-idea
description: Find evidence-backed weaknesses in a product or business proposal with complementary reviewers, then prioritize substantive changes for an agent-written revision.
---

# Stress test idea

Read [the shared contracts](../_shared/contracts.md) completely before acting. Apply their evidence, authority, state, question and coverage rules. This skill produces iteration input; use `evaluate-proposal-harsh` when the user requests a commitment decision.

## Help and inputs

If the entire trimmed argument is `-h`, `--help` or `help`, show the purpose, accepted inputs and flags below and stop without creating state.

Input: a document path, pasted substantive idea, or `--slug NAME` referring to existing state. Optional: user constraints and `--verify-claims`. The flag enables scoped external checking; otherwise all review stays closed-world. A short proposal is acceptable. If there is no material at all, ask for the idea and intended decision, not an arbitrary word minimum.

## Workflow

1. Resolve the source and slug using `state.py`. Read context and prior user decisions. Init a new source or select the exact immutable version requested; changed source text requires a new snapshot. Do not reuse stale counts or overwrite a snapshot. Read the complete snapshot and run `wordcount.py check`. Follow the shared size/coverage policy.
2. Prepare a neutral common brief: snapshot path/hash, decision scope, resources, user facts with provenance, and coverage. Prior verdicts belong in the later comparison, not the reviewers' brief. Cross-check explicit arithmetic, units, constants and supplied worked examples; keep these results as auditable inputs, not assumed conformance.
3. Before dispatching A, B and C, capture each under its exact role ID (`A`, `B`, `C`) and its caller policy or null in `expected_model_roles`, then run the shared caller-model preflight separately for each. Inspect any effective agent pin; pass an available required `model_argument` explicitly to the host, including pasted-definition dispatch. Dispatch allowed roles concurrently with the brief and their lens below. Use fresh reviewer contexts; they must not see each other's outputs. Explicitly prohibit network access, file/state changes, further agents and outside actions. Record a blocked mandatory role as incomplete coverage and continue useful analysis without pretending it passed.
4. Add the fresh verifier and, when `--verify-claims` is authorized, the validator in `claims` mode to `expected_model_roles` before each dispatch; apply the same preflight and post-dispatch model observation. Give the validator only the approved query material. Integrate new findings through the same verification process. A mandatory model gap in a decision-driving verification leaves that finding unverified.
5. Normalize final findings with `policy.py normalize`. Preserve IDs and assumptions, resolve severity conflicts with evidence, and separate supported issues, unverified questions and refuted claims. Use `policy.py prioritize` for the ready findings. Causal consequence outranks repeated mentions.
6. Write an immutable `stress_test` report via `state.py report`, including structured final findings, coverage, the pre-dispatch `result.expected_model_roles`, and each role's observation in `result.review_protocol.roles`. A missing planned role or mandatory model gap must be named as incomplete coverage; do not offer an unqualified conclusion from that role. Refresh the active findings view with a generation-checked update. Return findings and the next action: `iterate-to-v2` writes the revision, asking only about consequential decisions and unavailable facts.

## Reviewer brief

Each reviewer returns the canonical finding fields from the shared contract plus counterevidence, useful assets, assumptions and coverage limitations. Zero findings is valid. Findings must identify a causal issue, source location, consequence and evidence basis; no fixed minimum. Missing evidence is a question or uncertainty, not proof of failure. Preserve provisional and simulated labels.

| Reviewer | Complementary lens |
|---|---|
| A — reasoning and customer job | Who has the problem, what they currently do, switching value, internal logic and dimensionally consistent market/unit math. Build the strongest case for and against the stated thesis; report what could falsify each. |
| B — product and execution | Differentiation, distribution, delivery resources, business model and dependencies. Mark dimensions supported, contradicted, unknown or not applicable. Avoid binary FAIL merely because a brief is silent. |
| C — operations and hidden assumptions | Support, reliability, trust, ongoing costs, adoption friction, monitoring and failure recovery. Check the entire reviewed source before asserting an omission. Identify load-bearing assumptions without inventing outside-world facts. |

Optional thinking skills can inform a lens if available, but must not expand authority or replace the brief. Inline reasoning is an acceptable fallback; do not claim a quality difference that has not been measured.

## Synthesis

Use the shared judgment rubric to record the strongest supported success mechanism, its unresolved assumptions and a discriminating test, alongside criticisms. Check material forecasts against relevant supplied comparison outcomes and explicitly assess execution capability. Unavailable comparison evidence remains a limitation. Persist `judgment_audit`, `forecast_checks`, `success_case`, and the actual `review_protocol` in the report result. This adds no default research permission or mandatory repeat model calls.

- Consensus describes several lenses noticing a causal issue, not several independent observations proving it.
- Unique findings require their own evidence. Mark supported ones `unique_real`, unresolved ones `unique_unrated`, and unsupported stretches `unique_reach`.
- Contradictions identify which statements actually conflict, their sources and the smallest question or check that resolves them. Different but compatible perspectives are not contradictions.
- Speculative synthesis additions remain questions until verified. They cannot sneak into recommendations as established facts.
- Explain shared assumptions and corroboration dependence. Do not manufacture disagreement to satisfy a template.
- Expand up to five highest-value changes, with IDs, expected consequence, dependencies and effort. List any remaining blockers separately. Preserve assets and counterevidence that constrain a good revision.

## Output

Include source version/hash; intended decision; review coverage; final findings with evidence dimensions; verification results and excluded IDs; causal/shared-assumption summary; prioritized changes; and pending user choices or evidence. Include the returned report ID in the handoff after persistence.

Raw reviewer text may be retained as labeled audit material, but downstream acceptance consumes only the final normalized findings. A critique with missing evidence should name the evidence needed. A thin but concrete idea can still receive useful, proportionate feedback.

Do not issue an Invest/Pivot/Skip verdict here, change the proposal itself, or require the user to draft a revision. In `--loop`, return control to the router for automatic iteration.
