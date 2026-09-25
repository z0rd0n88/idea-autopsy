# Judgment rubric — protocol 1

Use this rubric for stress tests, commitment evaluations, revisions and strategy. It defines review behavior; it is not an empirically calibrated scoring system. Keep the four existing axes and executable verdict policy.

## Make the judgment observable

For each decision-driving finding, record the scoped commitment, cited premise, causal consequence, strongest relevant counterevidence, and what evidence would change the assessment. Put this information in `severity_reason`, sources and report `result.judgment_audit`, keyed by finding ID. Do not invent additional canonical finding fields that downstream normalization may discard.

| Judgment | Required basis | Contrast |
|---|---|---|
| Critical | Supported mechanism that blocks the actual commitment; explain why a remedy can or cannot fit the constraints. | A documented mandatory cost exceeding an immutable budget can block. No cost estimate is an evidence gap. |
| High | Supported consequence requiring attention before the commitment; distinguish established danger from an unanswered question. | A documented unsupported production dependency can block launch; an unspecified dependency needs investigation. |
| Thesis-breaking | Cite the essential thesis and show why the supported contradiction defeats it; consider a credible success mechanism. | Refuted sole differentiation may break the thesis. A competitor's existence alone does not. |
| Plausibly resolvable | Identify a concrete remedy, its dependencies and resources, and its compatibility with fixed constraints. | A supplied compatible replacement can support a remedy; “the team will figure it out” cannot. |
| Sufficient evidence | Evidence supports benefits, feasibility and costs at the user's commitment scale, with residual uncertainty explained. | A successful local prototype may support a bounded trial, but cannot alone justify production adoption or fundraising. |
| Confidence | Explain source reliability, directness, contradictions and remaining uncertainty for the claim being judged. | High confidence that a document omits demand evidence does not mean high confidence demand is absent. |

Novelty, viability, desirability and strategic fit need explicit definitions for this decision. For example, desirability concerns an identified user's behavior and switching costs; viability concerns attributable economics and constraints. Model familiarity, polished language, and the number of reviewers agreeing are not evidence for these concepts. Confidence labels are not probabilities. Reasoning explanations are claims to check, not faithful access to model internals [Lampinen; Turpin; Zheng].

## Forecasts and capability

For material time, cost, adoption or benefit forecasts, retain the inside-view calculation and record a reference-class check: comparison population, inclusion/exclusion rules, source/date, outcome definition, observed distribution or range if supplied, and relevance limits. Include failures where available; explain survivorship bias and unsuitable comparators. Never invent a rate or treat a selected success anecdote as a base rate [Buehler].

Use supplied records by default. Only existing research permissions allow lookup. Mark a comparison `supplied`, `researched`, `unavailable`, or `not_applicable`, explaining the latter two. Missing comparisons do not automatically defeat a decision: explain whether the remaining evidence supports the commitment. If not, preserve the evidence gap under existing policy.

For full-build or funding commitments, explicitly assess relevant team skills, availability, dependencies and evidence of execution capacity. Other scopes may need only available time and skills; explain non-applicability. Do not infer competence from prestige or invent staffing [Song; Gompers].

## Constructive challenge and verification

Before synthesis, record a credible path to success using supported assets, its necessary assumptions, and a discriminating test if one fits the constraints. A hypothetical path is not positive evidence. Distinguish a demonstrated contradiction from an unresolved novel idea. Do not force optimism where a blocker is established [Mueller; Berg; Camuffo].

Reviewers receive the same source, evidence and decision constraints in fresh contexts. Withhold author/model attribution, previous verdicts and persuasive reviewer commentary from initial judgment; preserve substantive evidence and an audit record of redaction. Fresh contexts reduce information sharing but do not establish statistical independence. Do not claim diversity if the host only exposes one model [Wang; Xu].

The verifier checks source entailment, calculations, counterevidence, omitted context and the causal consequence. Agreement with a fluent explanation is insufficient. If evidence or semantic classification conflicts could alter the decision, resolve them from sources or record the gap before the existing verdict procedure. Preserve the exact mechanical result and any override.

## Revision and review record

Classify each revision change in its change record as `evidence_added`, `reasoning_corrected`, `presentation_only`, or `authorized_scope_change`. Multiple categories may apply. Cite the new evidence for any claimed resolution. A presentation-only revision can improve readability but cannot establish demand or eliminate a real blocker.

For a revision's evaluation, use a fresh initial review with the same applicable evidence and constraints. Hide previous verdict and author attribution until after this pass; then compare stable finding IDs. The parent checks whether improvement survives this comparison rather than rewarding its own wording [Xu; Zheng].

Store the pre-dispatch `result.expected_model_roles` separately from `result.review_protocol`; each planned role names its `caller_policy` or null. Store `result.review_protocol` with `protocol_id: judgment-rubric-v1`, actual source hash, decision/evidence references, prompt identifier or hash, actual blinding conditions, unavailable reviewers, limitations, and `roles` containing each dispatch's `model_observation` record. Each role records the caller's requested model (or null), the host-exposed actual model (or `unknown`), dispatch path, and compliance status. A missing planned role or mandatory model-policy gap is a coverage input to the existing verdict procedure; the remaining audit metadata does not create new verdict thresholds. Store `result.judgment_audit`, `result.forecast_checks`, and `result.success_case` for review/strategy reports; store `result.revision_changes` for revisions. Historical reports without these fields remain readable. Do not fill missing provenance by guessing.

Routine review does not require repeated model runs. The [validation protocol](../../docs/evaluation-validation.md) defines controlled tests for order, paraphrase, framing, verbosity and self-preference. Record tests as `not_run` until actual runs exist. Cross-model review is optional and must be reported accurately; it cannot replace source verification.

## Academic basis

These are design implications, not evidence that Idea Autopsy is accurate. See the [full bibliography](../../docs/scholar-refs.md).

- [Lampinen et al., PNAS Nexus (2024)](https://doi.org/10.1093/pnasnexus/pgae233): content-sensitive reasoning.
- [Turpin et al., NeurIPS (2023)](https://doi.org/10.52202/075280-3275): explanations can rationalize biased answers.
- [Zheng et al., NeurIPS (2023)](https://doi.org/10.52202/075280-2020), [Wang et al., ACL (2024)](https://doi.org/10.18653/v1/2024.acl-long.511), [Xu et al., ACL (2024)](https://doi.org/10.18653/v1/2024.acl-long.826): judge bias and limits of self-refinement.
- [Buehler et al., JPSP (1994)](https://doi.org/10.1037/0022-3514.67.3.366): planning fallacy.
- [Song et al., JPIM (2008)](https://doi.org/10.1111/j.1540-5885.2007.00280.x), [Gompers et al., JFE (2020)](https://doi.org/10.1016/j.jfineco.2019.06.011): venture context and team factors.
- [Mueller et al., Psychological Science (2012)](https://doi.org/10.1177/0956797611421018), [Berg, ASQ (2016)](https://doi.org/10.1177/0001839216642211): novelty and creative evaluation.
- [Camuffo et al., SMJ (2024)](https://doi.org/10.1002/smj.3580): entrepreneurial hypothesis testing.
