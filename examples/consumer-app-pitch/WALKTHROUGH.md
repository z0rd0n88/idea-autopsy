# Walkthrough: GigPurse's agent-written revision

All outputs and user answers are **synthetic illustrations**, not runtime traces. [`v1.md`](v1.md) preserves the flawed input. No new interviews, paid pilots, market research, or deployment are supplied.

| Stage | Artifact | Outcome |
|---|---|---|
| Input | `v1.md` | Broad fintech pitch, unverified waitlist, incorrect market arithmetic, and a $750k raise. |
| Stress test | `v1-stress-test.md` | Twelve raw observations become seven causal findings; one refuted observation remains only in the audit trail. Repeated uncertainty is not proof of failure. |
| Questions/revision | `v1-change-plan.md` | Seven findings accepted; five fictional user answers settle decision scope, customer, product scope, resources, and available evidence. |
| Generated proposal | `v2.md` | **The agent writes v2** with correct arithmetic, a manual prototype, capped discovery, and unresolved risks. No founder rewrite. |
| Evaluation | `v2-verdict.md` | Proceed with caution for $600/16-hour discovery; the original raise still has insufficient evidence and no business verdict. |

The user chooses the change from fundraising to bounded learning (GP-D001) and removes tax/transfers (GP-D002). The agent does not silently make those decisions. Arithmetic and structural corrections proceed automatically once answered; persisted answers prevent repeated questioning on resume.

Acceptance differs from resolution. GP-F002 is accepted but payment remains unknown. GP-F004 is a scope change, not proof of the original product's safety or legality. GP-F006 is Reviewer A's steel-manning hypothesis, not a verified retention fact. Seven IDs connect raw observations, synthesis, acceptance, changes, and evaluation without counting recommendations as new issues.

Market arithmetic separates population ceilings, serviceability, and obtainable annual revenue. The LTV illustration matches annual revenue/churn and includes a hypothetical margin. Neither establishes real LTV or CAC. Plausible-looking numbers cannot substitute for missing facts.

The zero-Critical rule still considers High findings. GP-F008 establishes that waitlist recruitment limits what success means; this warrants caution for discovery without asserting market failure. All four review axes completed within the fixture. Missing Feasibility coverage would instead produce incomplete_coverage.

After evaluation, another prose-only pass adds no evidence. Resume preserves the cap and pending observations. Once the user supplies facts, the agent interprets them, asks about consequential new choices, writes the next version, and evaluates it. The user is never told to create `v3.md`.

See [Stellate](../b2b-saas-pivot/WALKTHROUGH.md) for Pivot/strategy and [YieldVault](../unsupported-tam-skip/WALKTHROUGH.md) for essential missing evidence that cannot honestly become Skip.
