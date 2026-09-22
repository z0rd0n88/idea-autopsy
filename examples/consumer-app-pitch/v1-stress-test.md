# Stress test: GigPurse v1

**Synthetic illustrative output; no external research or runtime review was performed.** Source: [`v1.md`](v1.md). Report ID: `gigpurse-v1-stress-fixture-01`. Coverage: A, B, and C completed within this fixture. The document's initial decision is a $750,000 pre-seed raise.

Source version: `v1`; SHA-256: `3675f93851f6d24d3143057802f3968b7c9088af47c2b87bfe86c06ec57b9fd7`.

## Raw reviewer observations

These preserve attribution, not extra final findings. Repetition is not corroborating evidence.

| Observation | Reviewer / lens | Observation | Normalized finding |
|---|---|---|---|
| A1 | A / arithmetic | Stated 1% capture does not yield $1.7B. | GP-F001 |
| A2 | A / pre-mortem | A free waitlist does not establish payment at $8/month. | GP-F002 |
| A3 | A / jobs to be done | Drivers and freelance creatives are combined without a first test cohort. | GP-F005 |
| A4 | A / steel-manning | A spreadsheet and savings account may solve enough of the job; repeat use is unmeasured. | GP-F006 |
| A5 | A / switching | The work required to move existing records is unspecified. | GP-F007 |
| B1 | B / business model | Payment conversion is absent from the supplied evidence. | GP-F002 |
| B2 | B / distribution | No funnel connects 400 waitlist entries to 5,000 paying users. | GP-F003 |
| B3 | B / arithmetic | Full-population ceiling and captured annual revenue are conflated. | GP-F001 |
| B4 | B / initial legal observation | “Bank connection is read-only, so there is no transfer or custody exposure.” | Refuted; excluded |
| C1 | C / silent failure | Month-12 revenue has no costed recruitment/conversion path. | GP-F003 |
| C2 | C / operational risk | Automatic tax calculations and transfers lack controls, failure handling, and qualified review. | GP-F004 |
| B5 | B / source-check correction | The third solution feature explicitly transfers money; B4 is incorrect. | GP-F004 |

There are **12 raw observations, 11 surviving observations, and 7 unique findings**. B4 is kept only in the audit trail. A4 is Reviewer A's steel-manning observation, not Reviewer C's.

## Verification report

- Internal arithmetic: `70,000,000 × 25% = 17,500,000`; at `$8 × 12`, the full segment revenue ceiling is `$1,680,000,000`; 1% penetration gives `$16,800,000` annual revenue. Using rounded 18M instead gives $1.728B and $17.28M. Neither calculation validates population or adoption assumptions.
- Internal contradiction: B4 is refuted by `v1.md`, “The solution,” feature 3. Remove it from findings and recommendations. No legal conclusion follows from this source check.
- External verification: **not performed**. BLS attribution, competitor capabilities, API availability, biographies, and regulatory claims remain unverified.

## Synthesis

Evidence fields describe support for the finding, not independent truth of every quoted pitch claim. All external statuses are `not_checked`. Confidence concerns the stated finding within this document's coverage.

Contract mapping: “demonstrated contradiction” is `kind=contradiction`; “unsupported assertion” is `missing_evidence`; “plausible risk” is `risk`; “unresolved question” is `question`. GP-F001–GP-F004 use `evidence_basis=document_logic`; GP-F005–GP-F007 are reviewer hypotheses, not established outside facts. All are active/unresolved for v1. Tables summarize the normalized records; source refs identify the sections a live report must preserve in its structured `sources` field.

### Consensus findings

| ID / causal issue / assumption | Severity and type | Finding and source | Evidence |
|---|---|---|---|
| GP-F001 / GP-I001 / GP-A001 | High; demonstrated contradiction | `v1.md#market` labels revenue at 1% capture as $1.7B. Arithmetic contradicts that wording. A1, B3. | origin=document; doc_support=supported; external_status=not_checked; confidence=high |
| GP-F002 / GP-I002 / GP-A002 | High; unresolved question | `v1.md#traction` reports a waitlist/survey, not payments. Will users pay $8/month? A2 and B1 do not prove they will refuse. | origin=document; doc_support=supported; external_status=not_checked; confidence=high about missing evidence |
| GP-F003 / GP-I003 / GP-A003 | High; unsupported assertion | `v1.md#ask` targets 5,000 paying users without a funnel or acquisition budget. B2 and C1 identify the same gap. | origin=document; doc_support=supported; external_status=not_checked; confidence=high |
| GP-F004 / GP-I004 / GP-A004 | High; plausible risk | `v1.md#the-solution`, feature 3, proposes calculations/transfers without specifying authorization, incorrect estimates, support, or failure recovery. C2 and corrected B5 do not establish an actual violation or loss. | origin=document; doc_support=supported; external_status=not_checked; confidence=medium about consequence |

### Unique findings

| ID / causal issue / assumption | Severity and type | Finding and source | Evidence |
|---|---|---|---|
| GP-F005 / GP-I005 / GP-A005 | Medium; unresolved question | A3, `v1.md#the-problem`: which cohort/task comes first? Breadth alone does not prove cohorts differ. | origin=reviewer; doc_support=not_established for cohort differences; external_status=not_checked; confidence=medium |
| GP-F006 / GP-I006 / GP-A006 | Medium; plausible risk | A4, steel-manning, `v1.md#the-solution`: a buffer view may not improve on existing workarounds enough to sustain use. No industry churn benchmark or actual retention failure is asserted. | origin=reviewer; doc_support=not_established; external_status=not_checked; confidence=low |
| GP-F007 / GP-I007 / GP-A007 | Medium; unresolved question | A5, `v1.md#the-solution`: how much setup effort does the intended user accept? The input does not answer. | origin=reviewer; doc_support=not_established; external_status=not_checked; confidence=medium |

### Contradictions and exclusions

B4 was refuted and excluded. Feature differentiation and willingness to switch are different questions; differing opinions about them do not create a factual contradiction. No other contradiction blocks this handoff.

## Prioritized changes and questions

1. Ask whether the next decision is the original raise or bounded discovery. A discovery verdict must not approve the raise by implication.
2. Ask whether to remove transfers and tax calculations from the first test. That changes product scope; do not silently rewrite the core promise.
3. Ask which cohort to start with, available budget/time, and whether payment or retention evidence exists. Recommend rideshare-driver discovery if the user has access; accessibility is an assumption until confirmed.
4. Automatically correct GP-F001 and distinguish population, serviceability, penetration, and price assumptions. Do not replace unsourced TAM with invented SAM.
5. Write a revision using the answers, preserving unresolved GP-F002, GP-F003, GP-F006, and GP-F007. A test plan does not resolve them. Prioritize decision consequences, not repeated reviewer mentions.

## Next step

`iterate-to-v2` asks consequential questions, records answers, then **writes v2 itself** and a change record. The user supplies decisions/evidence, not rewritten sections. See [`v1-change-plan.md`](v1-change-plan.md) for this fixture's answers.
