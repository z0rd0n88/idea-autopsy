---
name: hackathon-judge
description: Assess whether an idea is worth a hackathon and could win it, scoring against the event's own rules through a simulated judge panel and an auditable verdict. Part of the Idea Autopsy skillset.
---

# Hackathon judge

Read [the shared contracts](../_shared/contracts.md) and [the judgment rubric](../_shared/judgment-rubric.md) completely before acting. Apply their evidence, authority, state, question and coverage rules unchanged. This skill answers a build-or-skip question for a time-boxed competition, not a business commitment; use `evaluate-proposal-harsh` for the latter and `stress-test-idea` when the user wants prioritized changes without a verdict.

This skill answers two separate questions and reports them separately:

1. **Is this idea worth spending the event on?** A project can be a good weekend and lose.
2. **Would it win the category being targeted?** A project can win and be miserable to build.

Collapsing them hides the useful answer. Neither question's result may be presented as the other's.

## Help and inputs

For an entire trimmed argument of `-h`, `--help` or `help`, show this purpose and the input/flag summary, then stop without creating state.

Accept a document, pasted substantive idea, or `--slug NAME`. Optional: `--verify-claims` for scoped external checking; default research is off and all review is closed-world. Reload stored context and prior user decisions before assessing.

**The rules and constraints block is required input, not optional context.** The rules decide every axis, so a missing block is missing coverage, not a default. Ask for it and stop rather than inferring a duration, a theme or a rubric. Record it in `investment_context` with the decision scope stated as the event commitment (for example "ship a demoable project in 36 hours, solo, targeting the sponsor API prize"). Collect:

| Field | Why it decides an axis |
|---|---|
| Duration and schedule | The entire Feasibility axis. Sleep, travel and the submission cutoff are part of it. |
| Theme | An off-theme project can score well and still place nowhere. |
| Mandated sponsor APIs or tech | Non-use is often disqualifying, and token use scores badly with the sponsor judge. |
| Team size cap and actual team | Feasibility is per-person-hour, not per-hour. |
| Pre-work rules | What may exist before the clock starts. Violation is disqualification, the highest-severity Risk finding available. |
| Submission requirements | Repo, video, deploy URL, devpost form. These consume build hours and are routinely underestimated. |
| The event's published judging rubric and weights | Supersedes any rubric this skill would otherwise construct. |
| Prize categories | Scoring is per category; "best overall" and a sponsor prize reward different projects. |

Unstated fields are recorded as unknown and named in coverage. Do not substitute a typical value for a stated one.

## Hackathon model

Reason from this baseline only where the rules are silent, and say when you are doing so. A typical event runs 24–48 hours against a theme, in teams of one to four, with pre-existing code restricted or banned. Work stops at a hard submission cutoff that precedes judging, and the submission artifacts are themselves deliverables. Judging is a science-fair expo round, a 3–5 minute stage demo, or both, scored by a panel against a published rubric; judges see dozens of projects in a few hours and remember few. "Done" means *demonstrated live on stage*, not merged, tested or deployable.

The recurring failure modes are over-scoping, integration hell between components that each worked alone, demo-day flakiness (network, rate limits, cold starts, a laptop on a projector), pre-work disqualification, and a project whose value is invisible in the format it is judged in.

## Rubric construction

Build the scoring rubric before dispatching reviewers, and persist it in `result.rubric` with its provenance.

- If the event publishes a rubric, use its criteria and weights **verbatim** and record `rubric.source: "event"`. Do not substitute, reweight or supplement your own criteria into a published one.
- Only where no rubric is published, construct one from the criteria below with `rubric.source: "constructed"`, stating each weight chosen and why the rules imply it.
- Score against the **specific prize category being targeted**, named in `rubric.category`. A sponsor-prize rubric weights non-trivial use of that sponsor's API far above general polish.

| Criterion | Scores |
|---|---|
| Demoability | Whether a 3-minute live demo has a visible moment that lands, or the value only shows up in a spreadsheet or a log. |
| Buildability | Whether a working slice ships inside the stated duration, on stacks the team already knows. Never recommend learning a new stack inside the event. |
| Differentiation | How many of the other teams build the same thing from the same theme and the same sponsor APIs. |
| Judge legibility | Whether a non-expert grasps the value in 30 seconds, without domain setup. |
| Scope escape hatch | What still demos at six hours to cutoff with the integration broken. An absent hatch is a finding, not a footnote. |
| Rule compliance | Sponsor tech, pre-work rules, team size, theme fit and submission requirements. |

## Axis mapping

`policy.py` requires exactly the four canonical axis IDs. Retarget what each examines; do not invent axis names, and record this mapping in `result.rubric.axis_mapping` so a reader can audit which criterion produced a finding.

| Axis | Examine |
|---|---|
| `critical_thinking` | Demo legibility and differentiation. Does the pitch hold up in 30 seconds to a non-expert, is the stated wow moment actually visible in the judged format, and is the idea distinguishable from the obvious reading of the theme? |
| `feasibility` | Buildability and the scope escape hatch. Scope against actual person-hours after sleep, travel, submission artifacts and integration time. Name the smallest slice that still demos. Stress assumptions transparently; do not invent productivity facts. |
| `risk` | Demo-day failure and rule compliance. Network dependence, rate limits, cold starts, unrehearsed demos, single points of failure, and anything disqualifying: pre-work violations, missing mandated tech, team size, missed submission requirements. A disqualifying rule violation is a thesis-breaking Critical. |
| `roi` | Win probability for the named category. Scored strength against the rubric's weights versus the hours it costs, and the opportunity cost of the alternative project. Absence of a published rubric limits confidence; it does not raise or lower win probability on its own. |

## Workflow

1. Resolve the source and slug through `state.py`. Read context, prior decisions and the rules block. Init a new source or select the exact immutable version requested; changed source text requires a new snapshot. Read the complete snapshot and run `wordcount.py check`.
2. Build the rubric per the section above. If the rules block is absent or missing a field that decides an axis, record that axis coverage as `partial` or `not_run` and say so; a guessed duration cannot produce a Feasibility verdict.
3. Prepare one neutral shared brief: snapshot path and hash, the decision scope as the event commitment, the rubric with its provenance and category, the rules block, the team's actual stacks, and the coverage map. Keep prior verdicts and reviewer conclusions out of it. Cross-check any stated hour budgets and arithmetic as auditable inputs, not assumed conformance.
4. Capture all four axis roles in `expected_model_roles` with their exact caller policies or null before dispatch, run the shared model preflight per role, inspect effective agent pins, and pass any available required `model_argument` explicitly. Dispatch allowed reviewers concurrently in fresh contexts that cannot see each other's output. Prohibit network access, file and state writes, further agents and outside actions explicitly. Record blocked or failed roles as incomplete coverage and continue the useful analysis without pretending the axis passed.
5. Dispatch the judge panel (below) as additional planned roles, added to `expected_model_roles` before their dispatch and observed afterwards like any other role. They score the rubric; they do not produce findings outside the canonical schema.
6. Add the fresh verifier under role ID `verifier` for every Critical/High finding and anything that could change either verdict. Remove refuted findings from the active set and recompute, including when the result becomes more favorable. Preserve the exclusion audit. With `--verify-claims` authorized, use `project-idea-validator` in `claims` mode for feasibility evidence only — prior art, API availability and rate limits, whether the hard part has a published library, whether the data exists. Market-size and demand evidence is out of scope for this skill and must not be requested or scored.
7. Normalize findings with `policy.py normalize`, supplying evidence-backed severity resolutions for conflicts. Build the verdict request with the four coverage states, the pre-dispatch `expected_model_roles`, `review_protocol.roles` from every attempted dispatch, and `decision_evidence` whose rationale addresses the event commitment, then run `policy.py verdict`. Render its mechanical result and assessment status faithfully.
8. Save an immutable `evaluation` report carrying the normalized findings, coverage, rubric, axis mapping, judge scorecards, panel disagreements, both verdicts and any override audit. Persist active context and findings through generation-checked updates.

## Judge panel

Simulate the panel the rules imply, as separate scorers with conflicting incentives, each in a fresh context that cannot see the others. Each scores every rubric criterion with one line of reasoning per criterion and states what would raise its lowest score. Persist the scorecards in `result.judge_panel`.

| Judge | Incentive |
|---|---|
| Sponsor engineer | Is the sponsor's API used non-trivially, or bolted on to qualify? Only dispatch when the rules name a sponsor prize or mandated tech. |
| Business judge | Is the problem real and the pitch legible to someone who does not code? |
| Technical judge | Is the hard part actually hard, or a thin wrapper over a hosted model or API? |
| Time-pressured generalist | Sees forty demos in three hours and remembers five. Is this one of the five? |

**Report the disagreements.** Where judges split on a criterion is where the project is fragile, and that split is a finding in its own right once it affects either verdict. Then aggregate to a panel score using the rubric's weights, stating that a simulated panel is a structured prediction, not measured judge behavior. Do not manufacture disagreement to satisfy the template, and do not average a split away into a middling score.

## Verdict presentation

`policy.py` is authoritative for the mechanical verdict and its branch ordering. Present its canonical value alongside the event-facing label, and persist the canonical value:

| Canonical | Event-facing | Requires |
|---|---|---|
| Invest | **BUILD IT** | — |
| Proceed with caution | **BUILD WITH SCOPE CUTS** | Name the cuts, each tied to the finding that forced it. |
| Pivot | **SAME DOMAIN, DIFFERENT DEMO** | Name the alternative demo and whether it reuses the supported assets. |
| Skip | **PICK SOMETHING ELSE** | — |

Every verdict cites the axis and the rubric criterion that decided it. Incomplete coverage or insufficient evidence yields a null verdict and no event-facing label; state what to obtain. The win assessment is reported separately from the build assessment and may disagree with it — a high `roi` score under a supported Feasibility Critical is still not a build recommendation.

For any non-Invest result, give the smallest useful next step if one exists: the thinnest prototype, API check or rules clarification that would flip the deciding finding, with its artifact, measurement, threshold rationale, time cost and pass/fail decision. Label proposed thresholds rather than manufacturing commitments.

## Output

Use concise headings for:

1. Decision context, source version and hash, the rules block as recorded, and coverage.
2. The two verdicts: build (canonical plus event-facing label, or null) and win probability for the named category, each citing what decided it.
3. The rubric, its weights, its provenance, and the axis mapping.
4. Each judge's scorecard, then the panel disagreements and the weighted aggregate.
5. Supported causal findings in full with their evidence and severity rationale; unresolved decision-critical questions separately.
6. Evidence gaps, verification summary, refuted IDs, shared assumptions and counterevidence.
7. The minimum demoable slice, and an hour-by-hour build plan fitted to the stated duration with the escape hatch marked at its decision point.
8. Rule explanation, any explicit override, and the persisted report ID.

Report every finding before any recommendation, in full; never pre-filter by severity or replace the list with a count. Do not soften a finding for approval or exaggerate it for decisiveness. Never recommend learning a new stack inside the event, present a simulated panel as measured judge behavior, or let a guessed rule stand in for a stated one.
