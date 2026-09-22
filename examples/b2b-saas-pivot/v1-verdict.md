# Evaluation: Stellate's sole differentiation thesis

**Synthetic illustrative output, not runtime evaluation or external research.** Report ID: `stellate-v1-evaluation-fixture-01`. Input: [`v1.md`](v1.md). Statements about actual competitors, employment, market populations, and acquisitions in that input remain externally `not_checked`.

Source version: `v1`; SHA-256: `90abff0a94f90fb31e7f0646747b840a971da59f9b398b281897878e17a590fc`.

## Fixture-supplied context and evidence

These entries are explicitly fictional user inputs. They are not research conducted by the agent.

| Ref | Fictional supplied content | Provenance |
|---|---|---|
| ST-D001 | “Decide whether to keep our sole-differentiation thesis or spend two days reframing it around the existing prototype. Do not decide the $4M raise yet. Budget for reframing: $240 and 12 team-hours.” | origin=user; doc_support=supported; external_status=not_checked; confidence=high about the chosen decision |
| ST-E001 | User-provided comparison trace: the team's existing alternative-tool installation reads a Sheet as source of truth, writes changes back, and requires no migration for the same sample workflow. Treat this as a fixture observation, not a verified statement about all Retool versions or configurations. | origin=user; doc_support=supported; external_status=not_checked; confidence=high within the fixture |
| ST-E002 | User-provided prototype trace: three sample Sheets produce forms/lists, round-trip edits succeed, and permission-denied requests fail visibly. No enterprise security, load, latency, or arbitrary-schema claim is included. | origin=user; doc_support=supported; external_status=not_checked; confidence=high within the fixture |
| ST-D002 | “Our no-migration exclusivity claim is the only demonstrated differentiation today. We have not measured a different customer advantage. Preserve our working schema parser and connector; do not select a new vertical without asking.” | origin=user; doc_support=supported; external_status=not_checked; confidence=high about the stated constraints |

## Review coverage

All four axes completed. Critical Thinking compared the exclusivity claim with ST-E001. Feasibility inspected ST-E002 and the 12-hour/$240 reframing plan; no blocking High or Critical was found for that limited task. Risk checked the proposed scope and platform dependency. ROI checked arithmetic and distinguished a small reframing decision from a seed investment.

This is not a “missing Feasibility report means pass” case. Production feasibility and the $4M raise still need evidence beyond these traces.

## Normalized findings

| Finding / causal issue / assumption | Severity and type | Evidence and consequence |
|---|---|---|
| ST-F001 / ST-I001 / ST-A001 | Critical; demonstrated thesis contradiction | `v1.md#differentiation` says “only product” and “entire wedge”; ST-E001 supplies a counterexample to exclusivity and ST-D002 confirms no other demonstrated wedge. The document's own Sheets-connector biography is a reason to investigate, not sufficient proof alone. origin=user; doc_support=supported; external_status=not_checked; confidence=high within the fixture. |
| ST-F002 / ST-I002 / ST-A002 | Medium for reframing; unresolved question | The 12/60 weekly users in `v1.md#traction` are a user-input claim, not payment evidence. $30/user/month is proposed; no conclusion that small teams cannot afford it follows. origin=document; doc_support=supported for absent payment evidence; external_status=not_checked; confidence=high about that absence. |
| ST-F003 / ST-I003 / ST-A003 | Medium; unsupported assertion | `v1.md#why-now` relies on acquisition interest and alleged incumbent deprioritization without supplied sources or buyer conversations. Neither the positive story nor the opposite story is verified. origin=document; doc_support=supported; external_status=not_checked; confidence=high about unsupported assertions. |

ST-F001 appears under Critical Thinking and ROI because both depend on ST-A001. It is **one causal Critical**, not two corroborating facts. ST-F002 and ST-F003 are independent questions, not more versions of the same Critical. No invented $80M SAM or categorical customer-price mismatch is used.

ST-F001 has `kind=contradiction`, `evidence_basis=user_report`, `affects_decision=true`, `thesis_breaking=true`, `plausibly_resolvable=false` for preserving this disproven exclusivity claim, `status=active`, and `resolution=unresolved`. Changing the thesis can reuse assets, but cannot make the current claim true. ST-F002/ST-F003 have `affects_decision=false` for the chosen reframing task; they remain evidence gaps for the raise. Feasibility coverage is complete and has no blocking High/Critical.

## Arithmetic and verification

V1's `50M × 20% × $30 × 12 = $3.6B` arithmetic is correct for its hypothetical full-population revenue ceiling; the population and eligibility assumptions remain unverified. No SAM is established. Adoption assumptions generate obtainable annual revenue, not a new SAM.

**Eight seats at $30/month generate `$2,880` annual recurring revenue per team.** Twelve such teams generate `$34,560` total ARR, not twelve $20,000 contracts. An annual $20,000 contract requires a different seat count, price, or package; the agent must ask before changing the commercial model.

External verification: none. Internally checked: source contradiction against explicitly supplied fixture evidence, causal deduplication, stated prototype coverage, and arithmetic. This report does not validate real competitor features or acquisition intentions.

## Verdict: Pivot

**Assessment status: complete. Rule result: Pivot. Final verdict: Pivot. Override: none.** One supported Critical defeats the current sole-differentiation thesis; reusable assets ST-E002 are documented; Feasibility completed with no blocking High/Critical for reframing; no separate fatal issue is established. Those conditions, not axis vote counts, support Pivot.

Contract result: `assessment_status=complete`, `mechanical_verdict=Pivot`, `verdict=Pivot`, `override=null`.

Here Pivot means replacing the unsupported exclusivity thesis while preserving the prototype. It does not mean changing pricing or selecting a vertical without the user. The original $4M raise is **insufficient_evidence; business verdict: null** pending demand, economics, and production-feasibility evidence.

## Next step and reassessment conditions

Run the strategy stage on this input and verdict. Ask which accessible customer workflow the user wants to investigate; after the answer, the agent drafts v2. [The strategy fixture](v1-strategy.md) shows this handoff.

To reconsider the **original exclusivity thesis**, obtain a comparable, reproducible test that actually refutes ST-E001's counterexample. New sales alone cannot make “only product” true. To assess a **new workflow thesis**, propose a separate buyer/task/payment experiment after the user chooses it. Neither path automatically upgrades the seed raise to Invest.
