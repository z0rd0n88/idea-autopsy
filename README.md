# Idea Autopsy

Idea Autopsy judges an entry against a brief you supply. An entry is anything written: a plan, a pitch, a script, lyrics, a spec, or a description of something made elsewhere, such as a track or a painting. Independent reviewers check fit, feasibility and quality, a fresh verifier checks their evidence, and the result is an auditable judgment with an improvement record. When the entry is the deliverable itself, the agent can write the next version and judge it again.

The business-specific version, which judges whether a product proposal deserves investment, moved to [idea-autopsy-business](https://github.com/z0rd0n88/idea-autopsy-business).

## Install

```bash
claude plugin marketplace add z0rd0n88/idea-autopsy
```

```bash
claude plugin install idea-autopsy@idea-autopsy
```

## Use

```text
/idea-autopsy:autopsy plan.md --brief brief.md
/idea-autopsy:autopsy plan.md --brief brief.md --loop
/idea-autopsy:autopsy --slug plan --status
```

## The brief file

```markdown
## Goal
A two-minute hackathon demo that runs on a laptop.

## Requirements
- R1: Runs offline.
- R2: Uses the event's sample dataset.

## Constraints
One weekend, two people, no paid services.

## Standard
Judged against last year's winning demos.
```

`Goal` and `Requirements` are required. A missing `Constraints` or `Standard` is recorded as not stated, and the matching label is marked provisional. Once a brief is confirmed on an entry it never changes; a different brief needs a new slug.

## What you get

| Label | Values |
|---|---|
| Fit | meets, partly meets, does not meet, cannot judge |
| Feasibility | achievable, achievable with changes, not achievable, cannot judge |
| Quality | strong, adequate, weak, cannot judge |
| Decision | yes, not yet, no, cannot judge |

The decision comes from fit and feasibility only. Quality is reported beside it; a quality bar you care about belongs in the requirements.

Interview-built briefs, briefs derived from good and bad examples, and ranking several entries against one brief arrive in later 4.x releases.
