# Evaluation: YieldVault v1

**Synthetic illustrative output; no external legal, financial, market, or technical research was performed.** Report ID: `yieldvault-v1-evaluation-fixture-01`. Source: [`v1.md`](v1.md). The historical directory name is retained, but the supplied evidence does **not** support the old categorical Skip verdict.

Source version: `v1`; SHA-256: `3e4a2cfa85cb8e123592516790f4d3a1f0954252e35ac437effe957e5e9f1c3a`.

## Assessment

**Assessment status: insufficient_evidence. Business verdict: null.** The decision is whether the proposed $1.5M/18-month undertaking is justified. Reviewers completed all four axes, but essential custody access, legal structure, production capability, costs, and actual demand are not established. Complete reviewer coverage is not complete evidence.

The document warrants concrete questions and arithmetic corrections. It does not establish that the product is illegal, that every custodian forbids it, that the team cannot hire, or that no plausible version could exist.

## Normalized findings

All cited input claims have external_status `not_checked`. Severity describes consequence for the stated commitment, not certainty that harm will occur.

| Finding / causal issue / assumption | Severity and type | Source, support, and implication |
|---|---|---|
| YV-F001 / YV-I001 / YV-A001 | High; demonstrated numerical mismatch | `v1.md#market` supplies percentages that yield $208,000/year under the interpretation below, not nine figures. It gives no quantified larger-scale scenario. origin=document; doc_support=supported; confidence=high for arithmetic, not market truth. |
| YV-F002 / YV-I002 / YV-A002 | High; unresolved question | `v1.md#the-product` assumes funds can move from an existing retirement account into a smart contract and back. No written custodian authorization, integration contract, or transaction trace is supplied. origin=document; doc_support=supported for missing evidence; confidence=high about the gap. |
| YV-F003 / YV-I003 / YV-A003 | High; unresolved question | `v1.md#ask` says “file Form ADV if required” but supplies no qualified analysis of the proposed entity, funds flow, account types, or jurisdictions. origin=document; doc_support=supported for missing evidence; confidence=high about the gap. |
| YV-F004 / YV-I004 / YV-A004 | High; unresolved question | `v1.md#team` and `#ask` identify a future hire, but no production custody design, security review, implementation evidence, or costed delivery plan. This does not prove the founder can never build a capable team. origin=document; doc_support=supported for missing evidence; confidence=high about the gap. |
| YV-F005 / YV-I005 / YV-A005 | High; unresolved question | `v1.md#traction` reports sign-ups and “would consider” survey answers. Those are not commitments or payment evidence. origin=document; doc_support=supported; confidence=high about the evidence limit. |

Risk, Feasibility, and ROI all depend partly on YV-A002. Repeating that unresolved access assumption across axes cannot manufacture several independent Criticals. No retained finding proves a fatal issue under fixed constraints.

YV-F001 is `kind=contradiction`, `evidence_basis=document_logic`. YV-F002–YV-F005 are `kind=missing_evidence`, `evidence_basis=document_logic`: missing evidence is established, not the truth of a negative answer. All remain active/unresolved and affect the requested funding decision. Contract result: `assessment_status=insufficient_evidence`, `mechanical_verdict=null`, `verdict=null`, `override=null`.

## Arithmetic and evidence report

Under the charitable assumption that the stated 8% is the annual yield base on which the 1% performance fee is charged:

`$13,000,000,000,000 × 0.001 × 0.02 × 0.08 × 0.01 = $208,000/year`.

The intermediate quantities are $13B of adopting account assets, $260M allocated, $20.8M annual yield, and $208K fee revenue. This is conditional arithmetic over unverified inputs, not a forecast. The input calls 8% a “yield differential” but charges on “yield”; the user must clarify the actual fee base. Different definitions change the economics.

The $13T is an asset-stock claim, not the product's revenue TAM. SAM requires an eligible, accessible population under an actual custody/product arrangement. Obtainable annual revenue then requires adoption, allocation, yield, and fee assumptions. None of those populations or costs is established here.

Internal checks: arithmetic, ambiguous yield/fee definitions, source coverage, and causal deduplication. External checks: none. References to legislation, ETFs, custodians, yields, and safety in v1 remain unverified; this report supplies no legal conclusions or invented compliance cost/timeline.

## Questions needed before a consequential revision

1. Which next decision matters: investigate a non-custodial concept, seek a custody partner, or assess the original full product? Recommend a bounded evidence-gathering stage before the $1.5M commitment. Changing custody or customer scope requires the user's choice.
2. What written custodian access evidence and qualified analysis exist for the actual account types, jurisdictions, and funds flow? A verbal assurance or generic rule reference must retain its original provenance; it is not counsel approval.
3. Is the 1% fee charged on gross yield, excess yield, assets, or something else? Supply one account-level example and operating costs if known.
4. What budget/time can be used to investigate, and what relevant implementation/security evidence can be supplied?

The agent can correct arithmetic now and outline unresolved sections. Once the user chooses a direction, it writes the revised proposal. It never fills evidence gaps with invented partnerships, security audits, legal clearance, or paid customers.

## Reassessment gate

There is no honest automatic Invest/Skip flip-condition yet because the decision's essential facts are unresolved. First obtain a specified funds-flow/access artifact, qualified scope-specific analysis, and a costed model using an unambiguous fee base. Propose a time/cash limit after the user states available resources; do not invent a legal-review quote or deadline. Negative evidence may support Skip for a particular constrained thesis; positive evidence permits further evaluation, not automatic investment.
