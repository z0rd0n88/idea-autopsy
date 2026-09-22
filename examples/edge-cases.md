# Decision contract edge cases

These are **synthetic, illustrative fixtures**, not completed model runs, vendor facts, or external verification. Each fixture supplies its own decision context and evidence. Machine tests of these cases check deterministic behavior, not quality of model judgment.

## EC-INVEST: bounded purchase with adequate evidence

User decision: buy a $40/month internal reporting tool with a cancellable one-month term; total permitted first-month expenditure $200. Supplied fixture contract confirms $40, and a task trace shows the same six monthly reporting tasks each fall from 120 to 60 minutes with required outputs unchanged. The user values saved time at $50/hour. Setup requires one hour; no data leaves the approved local environment in the supplied architecture/trace.

Arithmetic: monthly saved time `6 × (120 − 60) / 60 = 6 hours`; user-valued benefit `$300/month`; first-month tool plus setup time cost `$40 + $50 = $90`. These are the user's decision values, not a guaranteed cash return.

Evidence EC-E001 (contract/task trace): origin=user; doc_support=supported; external_status=not_checked; confidence=high within fixture. All four axes complete, adequate evidence for this limited purchase, no unresolved blocking High/Critical. Expected: `assessment_status=complete`, `mechanical_verdict=Invest`, `verdict=Invest`, override absent. It does not approve a company investment or infer future productivity beyond supplied tasks.

## EC-SKIP: proven constraint mismatch

User decision EC-D002: spend at most $1,000 on a specified one-day event installation, require the named venue and hardware configuration, and do not consider fundraising, borrowing, another date, or a reduced configuration. Supplied fixture contract EC-E002 establishes a **mandatory, non-negotiable $10,000 upfront fee** for exactly that event/configuration, with no alternative contractual path. The user confirms those constraints remain fixed after the mismatch is explained.

Finding EC-F002 / issue EC-I002 / assumption EC-A002: Critical; demonstrated contradiction. The $10,000 minimum exceeds the explicit $1,000 cap by $9,000, so this action cannot satisfy the chosen constraints. origin=user; doc_support=supported; external_status=not_checked; confidence=high within fixture. This is one supported fatal issue, unresolvable under the expressly fixed scope—not an estimate about market prices or a missing-data inference. All four axes complete; no unsupported second Critical is manufactured.

Expected: `assessment_status=complete`, `mechanical_verdict=Skip`, `verdict=Skip`, override absent. No plausible flip exists **within those fixed constraints**. A new budget/venue/configuration would require a user decision and new evaluation, not a claim the person or general idea has no future.

## EC-INSUFFICIENT: thin evidence is not negative evidence

Decision: commit $100,000 to launch a subscription product. Input provides a paragraph describing a feature and a proposed $20 price, but no buyer, cost, delivery, or payment evidence. EC-F003 / EC-I003 / EC-A003 is an unresolved question about viable paid demand; origin=document; doc_support=supported for absence of evidence; external_status=not_checked; confidence=high about the gap. No source demonstrates unwillingness to pay.

All axes returned but essential evidence is absent. Expected: `assessment_status=insufficient_evidence`, `mechanical_verdict=null`, `verdict=null`. Ask which initial customer is intended and what evidence/resources exist. The agent can draft a bounded next step after choices; it must not invent proof or mechanically assign Skip.

## EC-REFUTED: remove a Critical and recompute

Decision: use an offline planning tool for a local workshop with a $100 cap. Initial reviewer finding EC-F004 / EC-I004 / EC-A004 claims cloud upload is mandatory and violates the user's offline requirement (Critical; origin=reviewer; doc_support=not_established; external_status=not_checked; confidence=medium).

The supplied fixture's configuration and trace EC-E004 show the actual selected offline mode, disabled network, and successful required workflow. The source check **refutes the finding**; evidence origin=user, doc_support=refuted for EC-F004, external_status=not_checked. The fixture also supplies a $20 licence, completed feasibility, and adequate task evidence, with no other unresolved blocking High/Critical.

Expected: retain EC-F004 in audit history with status `refuted`, exclude it from retained counts, recompute to `assessment_status=complete`, `mechanical_verdict=Invest`, `verdict=Invest`, override absent. A softer result does not justify stopping verification. Internal evidence is not relabelled external verification. A further independent blocker, if present, would still count.

## EC-COVERAGE: missing Feasibility is not a pass

Decision: build the specified prototype. Critical Thinking, Risk, and ROI return; Feasibility times out without a usable report. The returned axes find no supported Critical. There is no evidence EC-E005 about whether the design can be built within the supplied resources: origin=reviewer; doc_support=not_established; external_status=not_checked; confidence=low.

Expected: `assessment_status=incomplete_coverage`, `mechanical_verdict=null`, `verdict=null`. Record missing Feasibility and retry or request review coverage. Do not produce Pivot or Invest based on an empty list of feasibility findings. Resume retains completed reports and targets the missing review instead of repeating all work.

## Revision and question boundary

Across fixtures, arithmetic and heading corrections proceed automatically. Changing the business model, customer, core thesis, spending cap, or product scope requires a focused question unless the user has already decided it. Persist the answer once, then the agent writes the revision. A pending answer is not approval, and successful drafting is not evidence that an experiment happened.
