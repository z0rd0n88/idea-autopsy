# Idea Autopsy as a general judge

Date: 2026-10-28. Status: draft for approval.

## Summary

Idea Autopsy today judges one thing: whether a product or business proposal deserves a stated investment. This design turns it into a general judge. The user supplies an entry and a brief (goal, requirements, constraints, standard of quality), and the plugin judges whether the entry meets the brief and whether it can be accomplished. The business version is preserved unchanged in a new repo, `idea-autopsy-business`. The generic version takes over the `idea-autopsy` name, repo and path.

## Intent and why

The existing plugin's reviewer lenses, verdict table, question categories and vocabulary assume a business: `roi`, pricing, target customer, Invest / Pivot / Skip. That makes it useless for a music competition entry, a painting, a hackathon project plan, a personal build, or any idea where the question is "does this do what it set out to do, and can it be done?" rather than "will it make money?"

The evidence discipline underneath is domain-free: independent reviewers, a verifier that refutes unsupported findings, blinding from author and prior verdicts, an immutable state ledger, and a bounded revision loop. That machinery is worth keeping. Only the rubric is business-specific, and the rubric should come from the user.

## Goals

1. Judge one entry against one user-supplied brief per run, or several entries against the same brief, ranked best to worst.
2. Return three separate answers with cited evidence: fit to the requirements, feasibility under the constraints, quality against the brief's own standard.
3. Never invent a requirement. Missing brief material is asked for, not assumed.
4. When the entry is rewritable text, write the next version and re-judge, bounded as today.
5. When the entry is not rewritable, end with what is wrong and what would make it better, ranked.
6. Generate reviewer lenses tailored to the brief, in addition to fixed general lenses, and record them so a re-judge uses the same panel.
7. Keep the business plugin available under its own name with no behaviour change.

## Non-goals

- More than one brief per run. Entries are always judged against the same brief.
- Image, audio or video entries. An entry is text: the thing itself or a description of it. A described painting or track is judged from the description, and the judgment says so.
- Business or market evaluation. That is `idea-autopsy-business`.
- Producing the entry from scratch.
- Conducting any proposed test or experiment.
- Migrating `.autopsy/` ledgers written by the business plugin. The new plugin starts a fresh state schema and does not read old ledgers.

## Anti-goals (a build that does these has failed even if it runs)

- Scoring on the judge's taste instead of the brief. If the brief says "any genre", genre is not a finding.
- Silently reintroducing business criteria ("but how would this make money?").
- A numeric score with no defined scale. Labels with evidence, never arithmetic over undefined numbers.
- A verdict issued with incomplete reviewer coverage or unverified decision-driving findings.
- Rewriting an entry the user did not want rewritten, or asking the user to do the rewrite.

## What makes a good judge (the standard reviewers follow)

This replaces the business judgment rubric. Every reviewer, the verifier and the synthesis follow it.

1. Score against the brief, not against taste. A requirement not in the brief is not a requirement.
2. Keep three questions apart: does it meet the requirements, can it be accomplished with the stated constraints, how good is it at what it is.
3. Point at evidence in the entry. A finding names where in the entry the problem is and what consequence it has. Outside-world claims are unverified unless the user supplied them or research was authorised.
4. Be consistent and blind. Same lenses and weights for v1 and v2. Reviewers do not see the author, prior verdicts, or each other.
5. Say what would change the answer. Every negative finding carries the smallest change that would resolve it, or says that no change within the constraints resolves it.
6. Admit limits. "Cannot judge X from a text description of a painting" is a valid and required answer. It is not a failure of the entry.

## Inputs

**Entry or entries.** One file path or pasted text, or several file paths (or `--entries DIR`, one entry per file). More than one entry puts the run in ranking mode (see "Ranking several entries"). An entry may be the thing itself (a plan, a pitch, lyrics, a script, a design doc) or a description of a thing made elsewhere (a recording, a canvas, a built object). Size guards carry over from today.

**Brief.** A file path, pasted text, or answers to the elicitation questions. The brief has four parts:

| Part | Meaning | Required |
|---|---|---|
| `goal` | One or two sentences: what the entry is trying to accomplish. | Yes |
| `requirements` | Must-haves. Competition rules, spec items, hard asks. Each gets a stable ID. | Yes, may be empty if the user says there are none |
| `constraints` | Time, skill, budget, materials, tools, rules of the venue. | Asked for; may be "none stated" |
| `standard` | What "good" means here. Reference works, a target audience, a level ("first-year student", "release-ready"). | Asked for; may be "none stated" |

A brief can come from three places, in this order of preference: written by the user (`--brief` or pasted), derived from labelled examples (see "Deriving the brief from examples"), or built by interviewing the user. With no brief file and no examples, the `brief` skill interviews. Whatever the source, the stored brief records where each part came from.

**The interview.** One question at a time, goal first. Then requirements: the judge keeps asking until each one is something a reviewer could check in the entry ("under four minutes", "uses only the provided sample pack"), and restates vague ones for confirmation. Then constraints, then the standard, offering "none" as an answer for those two. The interview ends with the full brief played back for confirmation. It does not guess a missing part; if the user declines to supply one, it records "not stated" and dependent findings are marked limited. A partial brief file plus an interview for the missing parts is allowed.

**Flags.**

| Flag | Meaning |
|---|---|
| `--brief PATH` | Read the brief from a file instead of asking. |
| `--entries DIR` | Judge every file in the directory as a separate entry and rank them. Conflicts with `--loop`. |
| `--examples DIR` | Derive the brief from labelled examples in `DIR/good/` and `DIR/bad/`. May be combined with `--brief`. |
| `--critique-only` | Force the non-rewritable path even for text. |
| `--rewrite` | Force the rewritable path (the agent will draft a next version of a description). |
| `--loop` | Judge, revise, re-judge, up to the version cap. |
| `--slug`, `--status`, `--reset`, `--verify-claims`, `--accept-all`, `--accept-none` | As today. |

## Deriving the brief from examples

Instead of writing requirements and a standard, the user can hand over examples labelled good and bad (`--examples DIR`, with `good/` and `bad/` subdirectories; at least one of each). A fresh agent, role `derive`, reads them and drafts the brief:

- `requirements`: things every good example does that at least one bad example fails. Each cites the supporting examples by file. A pattern seen in good examples but never contradicted by a bad one is recorded as a hypothesis, not a requirement.
- `standard`: what separates the good from the bad beyond the requirements, in plain words, with cited examples.
- `constraints`: only where visible in the examples; otherwise "not stated".
- `goal`: inferred and marked provisional if the user gave none.

The drafted brief is shown to the user with its citations before any entry is judged. The user confirms it, edits it, or adds to it. This confirmation is a consequential decision and is recorded with the example file hashes. Nothing is judged against an unconfirmed derived brief.

Rules:

- Examples are never entries. They are not judged or ranked, and reviewers do not receive the raw example files; they receive the confirmed brief. This keeps reviewers scoring against the brief, not imitating the examples' taste.
- When `--examples` is combined with a user brief, the derived material may add requirements or sharpen the standard; it never removes or weakens something the user wrote. Conflicts are shown to the user.
- With only one good and one bad example the brief is marked weakly supported and every derived requirement is a hypothesis until the user confirms it.
- The `derive` role is recorded in `review_protocol` like any reviewer, with its model.

## Deciding whether the entry is rewritable

Default rule, decided by the judge skill from the entry, recorded in state, asked once if ambiguous:

- Rewritable: the text is the deliverable. A plan, pitch, essay, lyrics, script, design, spec, code outline.
- Not rewritable: the text describes or transcribes a deliverable that exists elsewhere. A description of a track, painting, sculpture, performance, built device, or a link to one.

`--critique-only` and `--rewrite` override the default. The decision is stored on the ledger and reused on resume.

## Reviewer panel

**Fixed lenses, every run:**

| Lens ID | Examines |
|---|---|
| `fit` | Each requirement by ID: met, partly met, not met, cannot tell. Evidence location in the entry for each. |
| `feasibility` | Can this be accomplished with the stated constraints? Which step or resource breaks it? Stress stated assumptions; do not invent productivity facts. |
| `quality` | How good is it at what it is, against the brief's standard. Strengths as well as weaknesses. If no standard is stated, say what standard was assumed and keep findings provisional. |

**Generated lenses, up to three per run.** Before dispatch, the judge reads the brief and writes up to three additional lens definitions specific to this brief. Each is a short reviewer instruction: lens ID, what to examine, what counts as evidence, what is out of scope. Examples: a music brief might yield `arrangement` and `mix`; a painting brief `composition` and `colour`; a hackathon plan `demo-risk`. Generated lenses are saved in the report's `review_protocol` and in state, and the same definitions are reused for every later version of the same entry. The user may edit them between versions; an edit is recorded.

A generated lens may not examine business value, market, pricing or monetisation unless the brief names it as a requirement.

**Verifier.** Unchanged in role: a fresh context checks every Critical/High and decision-driving finding against the entry and the brief, refutes unsupported ones, and the exclusion audit is preserved.

**Fact-checker (optional, `--verify-claims`).** The existing `project-idea-validator` reduced to `claims` mode, renamed. Research stays off by default.

**Agents shipped.** Two general-purpose agent definitions: `reviewer.md` (takes a lens definition and the brief) and `verifier.md`. The strategist and the standalone validator mode are dropped. Reviewers are dispatched as fresh, parallel contexts with web, writes, extra agents and outside actions prohibited, as today.

## The judgment

Mechanical, computed by `policy.py`, with the same mechanical-versus-reported audit as today.

| Answer | Values |
|---|---|
| `fit` | `meets`, `partly_meets`, `does_not_meet`, `cannot_judge` |
| `feasibility` | `achievable`, `achievable_with_changes`, `not_achievable`, `cannot_judge` |
| `quality` | `strong`, `adequate`, `weak`, `cannot_judge` |
| `decision` | `yes`, `not_yet`, `no`, `cannot_judge` |

`decision` is derived: `cannot_judge` if any required lens is missing, blocked, or has an unverified decision-driving finding; `no` if fit is `does_not_meet` or feasibility is `not_achievable`; `not_yet` if either is the middle value; `yes` only when fit is `meets` and feasibility is `achievable`. Quality never changes the decision on its own; it is reported alongside, because a brief that asks "is this release-ready" has put quality into `requirements` or `standard` and it reaches the decision that way.

An override must show both the mechanical and the reported answer, the reason, and the evidence. It cannot fill missing coverage.

**How each answer is derived (builder-check decision).**

- `fit`: the `fit` reviewer returns one record per requirement ID: `met`, `partly_met`, `not_met` or `cannot_tell`, each with an evidence location. `policy.py` folds them: any `not_met` supported after verification gives `does_not_meet`; otherwise any `cannot_tell` gives `cannot_judge`; otherwise any `partly_met` gives `partly_meets`; all `met` gives `meets`. An empty requirements list gives `meets` flagged `vacuous`, so `decision` rests on feasibility alone and the report says so.
- `feasibility`: the reviewer returns a label plus findings. `policy.py` checks consistency: a supported Critical on the `feasibility` lens forces `not_achievable`; a supported High forces at least `achievable_with_changes`; an unverified decision-driving finding forces `cannot_judge`.
- `quality`: the reviewer returns a label plus findings. With no `standard` in the brief the label is kept and marked `provisional`, not downgraded to `cannot_judge`.
- Generated-lens findings carry an optional `requirement_id`. A supported Critical from any lens that names a requirement counts as `not_met` for that requirement. Findings with no requirement are reported and ranked in the improvement record but do not move the three answers.

Severity still decides what the verifier must check and how the improvement record is ranked.

**Finding schema (builder-check decision).** Keep `id`, `severity`, `axes` (now the active lens IDs), `kind`, `evidence`, `resolution`, `bucket`, `assumption_ids`, `independence_evidence`. Add optional `requirement_id` and `lens`. Drop `thesis_breaking`, `plausibly_resolvable`, `reusable_assets` and `decision_evidence.sufficient`; they only fed the Invest/Pivot/Caution branches. "Critical" means "defeats the goal as briefed".

**The brief is immutable within a run (builder-check decision).** A run is the lifetime of one ledger slug: once the brief is confirmed on a slug, every judgment and revision on that slug uses that brief, and each judgment records the brief's hash. Revisions change the entry, never the brief. If a finding says a requirement cannot be met under the constraints, that is a blocker in the improvement record; the user may start a new run, on a new slug, with a changed brief. Consequential change categories are therefore `scope` and `approach` only, plus `routine`. The `goal`, `requirement` and `constraint` categories named earlier are withdrawn.

## After the judgment

**Rewritable path.** The loop revises on `not_yet` and `no`. A `yes` decision ends the loop, but an explicit request to revise is honoured on `yes` too: a competition entry can meet every requirement and still be `weak`, and the findings say what would make it stronger. `revise` (today's `iterate-to-v2`) takes the judgment's findings, proposes the smallest substantive remedy per accepted finding, asks about consequential changes, drafts the next version, saves it with a change record, and hands back to the judge. Version cap, the no-cosmetic-version rule, and the stop conditions carry over.

Consequential change categories replace the business set: `scope` and `approach`. Changing either needs a user answer bound to the exact change ID, as today. `routine` stays. The brief itself is never changed by a revision (see above).

**Non-rewritable path.** The run ends after the judgment with an improvement record: every negative finding with its evidence, its consequence for the goal, and the smallest change that would resolve it, ranked by consequence. Blockers that no change within the constraints resolves are listed separately. No next version is created and `--loop` stops with a documented reason.

## Ranking several entries

When more than one entry is supplied, every entry gets its own full judgment first: same brief, same fixed and generated lenses, same verifier, each in fresh contexts that never see another entry. Generated lenses are produced once from the brief, before any entry is read, so no entry shapes the panel.

**Order.** Mechanical, computed by `policy.py` from the judgments, best first:

1. `decision`: `yes`, then `not_yet`, then `no`. Entries with `cannot_judge` are not ranked; they are listed separately with the reason.
2. Within the same decision, `fit`, then `feasibility`, then `quality`, each by its label order.
3. Within identical labels, fewer supported Critical findings, then fewer supported High findings.
4. Still tied: a pairwise comparison. A fresh reviewer receives the brief and only the tied entries and returns an order with the evidence for each adjacent pair. Its model is recorded like every other role. If it cannot separate them it says so and they share a rank.

No numeric scores. The ranking report shows, for each adjacent pair, the step at which they separated and the evidence.

**What ranking mode does not do.** It does not revise entries. `--loop` with several entries is rejected by `policy.py route` with a reason. Each entry still gets its improvement record, and the user can revise one entry afterwards by running it alone on its own slug, which reuses the stored brief and lenses.

**State.** Each entry is its own `.autopsy/<entry-slug>/` ledger, exactly as a single-entry run. The ranking run adds one `.autopsy/<brief-slug>/` ledger holding the brief, the lens definitions, the entry slugs with their judgment report IDs, and immutable `ranking` reports. Re-running the ranking after one entry is revised produces a new ranking report referencing the new judgment; old rankings stay readable.

**Output.** A table of rank, entry, decision, fit, feasibility, quality and the one-line reason it sits above the entry below it; then the unranked entries and why; then per-entry judgment report IDs. The report says which steps separated which pairs.

## Skills and command

| Component | Replaces | Role |
|---|---|---|
| `commands/autopsy.md` | same | Router. Route to `brief` when none is stored, decide rewritable, route to `judge`, `revise` or `rank`, loop. |
| `skills/brief` | new | Obtain the brief: read a file, derive from examples, or interview the user; get confirmation; store it with provenance. |
| `skills/judge` | `stress-test-idea` + `evaluate-proposal-harsh` | One skill: lens generation, dispatch, verify, normalise, judgment, improvement record. |
| `skills/rank` | new | Runs `judge` per entry, computes the order, runs pairwise tiebreaks, writes the ranking report. |
| `skills/revise` | `iterate-to-v2` | Agent-written next version from accepted findings. |
| `skills/_shared/` | same | Contracts, judge standard, `policy.py`, `state.py`, `wordcount.py`, thresholds. Business sections rewritten. |
| `agents/reviewer.md`, `agents/verifier.md`, `agents/fact-checker.md` | the two current agents | General-purpose roles. |

`strategize-from-verdict` and `product-strategist` are removed. "What else could you do instead" is a different job.

The stress-test and evaluate split exists today because the business flow wants a closed critique before a verdict. For a general judge the findings and the judgment come from the same panel, so one skill is simpler and keeps the panel consistent. If a user wants findings without a decision, `judge` reports `decision` anyway; it is cheap and auditable.

## State

New schema version. `investment_context` becomes `brief` (the four parts, each with provenance: `user`, `elicited` or `derived` with example hashes, and the confirmation record). Add `rewritable` (boolean, with how it was decided) and `lenses` (fixed plus generated definitions). Reports keep unique IDs and immutability. Report kinds: `judgment`, `revision`. No `import-legacy` path for business ledgers; the operation is removed rather than left half-working.

The ledger directory stays `.autopsy/<slug>/` (builder-check decision). Both plugins only collide when run on the same slug in the same project. The new `state.py` refuses a schema-2 ledger with a message that names `idea-autopsy-business` as its owner and suggests a different slug; it never migrates or overwrites it.

## Repo split

Done first, before any content change, so the business plugin never has an inconsistent state.

1. Merge or close the two open worktrees in the current repo (`feat/company-feature-proposals`, `feat/hackathon-judge`). The user decides which.
2. Create GitHub repo `z0rd0n88/idea-autopsy-business` (private, issues on, SSH remote). Push the current `main` with full history. Clone to `/home/alex/idea-autopsy-business`. Change `plugin.json` and `marketplace.json` name to `idea-autopsy-business`, bump to `4.0.0` (name change breaks the install string), update the README title and install line. Install it so the business version keeps working.
3. The current repo and path stay `idea-autopsy` and `/home/alex/idea-autopsy`. All content work below happens there, on feature branches as usual. Version becomes `4.0.0` on the first content PR (inputs and outputs change).

The user confirms step 2's GitHub repo creation before it runs.

## Examples and tests

Replace the three business examples with three: a text entry judged against a brief and revised once (rewritable path, for instance a hackathon project plan against the hackathon rules); a non-text entry judged and ended with an improvement record (for instance a described track against a competition brief); and three short entries ranked against one brief, with one tie broken pairwise and one entry unranked. Examples stay labelled as illustrative, not runtime traces.

`tests/` carry over with the business fixtures rewritten: policy tests for the new decision table, the ranking order including ties and unranked entries, change categories, lens validation, and brief merging (derived material cannot weaken a user requirement); state tests for the new schema fields and the brief-level ledger; wordcount unchanged.

Removed from the generic plugin (builder-check decision): `skills/_shared/evaluation_audit.py`, `tests/test_evaluation_audit.py`, `tests/fixtures/evaluation_audit_cases.json`, `docs/evaluation-validation.md`, `docs/research/`, `docs/research-implementation-plan.md`, `docs/scholar-refs.md`. They validate and cite the business verdict protocol. They remain in `idea-autopsy-business` through its history. Any README or rubric link to them is removed with them.

## Left to the builder

- Exact wording of the interview questions and the test for "checkable enough" on a requirement.
- Where `--brief` and pasted briefs are parsed (router or `judge` skill).
- How generated lens definitions are validated in `policy.py` (minimum: non-empty ID, examine text, no business terms unless the brief has them).
- Whether `quality` reviewers get a separate pass or share the `fit` reviewer's context when the brief has no standard. Either is acceptable if recorded.
- How `--entries DIR` orders and names entries (suggested: filename order, slug from filename).
- Order of work. Suggested: repo split, then a tracer bullet (judge one text entry against a written brief, fixed lenses only, no loop), then revise loop, then generated lenses, then the non-rewritable path, then ranking, then brief derivation from examples, then examples, tests and docs.
