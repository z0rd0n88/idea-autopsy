# Idea Autopsy

Idea Autopsy turns a product or business proposal into a better-supported decision and an agent-written revision. The user supplies preferences, consequential choices and missing facts; the agent writes v2 and later versions.

```text
proposal → stress test → user choices when needed → agent revision → evaluation
                                                                      ↓
                                                        strategy / evidence / stop
```

## Four modes

| Skill | Input | Output |
|---|---|---|
| [stress-test-idea](skills/stress-test-idea/SKILL.md) | Idea and decision context | Verified reasoning, unresolved questions and prioritized substantive changes |
| [iterate-to-v2](skills/iterate-to-v2/SKILL.md) | Source and final critique | Agent-written proposal plus traceable change record |
| [evaluate-proposal-harsh](skills/evaluate-proposal-harsh/SKILL.md) | Proposal and scoped commitment | Assessment status and, when justified, Invest / Proceed with caution / Pivot / Skip |
| [strategize-from-verdict](skills/strategize-from-verdict/SKILL.md) | Assessment, findings and assets | Concrete options, user choices and revision handoff |

The historical names remain available. Missing numbers, a short pitch or an unavailable reviewer do not automatically mean Skip. Insufficient evidence and incomplete coverage are separate assessment statuses with no business verdict.

## Use

```text
/autopsy ./pitch.md --loop
/autopsy --slug pitch --status
/autopsy --slug pitch give me a verdict
/autopsy --slug pitch what should I pivot to?
```

The agent asks before changing your target customer, pricing, business model, core thesis, scope or resource commitments. It handles ordinary corrections automatically. Answers are bound to the exact proposed change and reused on resume. Accepting a criticism does not approve every possible remedy.

The default loop creates at most three proposal versions. It stops for an experiment, missing decisive evidence, a pending consequential choice, a terminal decision or lack of substantive progress. It does not keep rewriting to obtain Invest. You can explicitly request a separate cycle or reassessment.

| Option | Effect |
|---|---|
| `--slug NAME` | Select a saved idea |
| `--loop` | Run the bounded automatic revision cycle |
| `--status` | Read-only progress and next action |
| `--reset` | Confirm and archive the exact ledger; no deletion |
| `--verify-claims` | Permit scoped web checking during reviews |
| `--validate` | Permit scoped web checking during strategy |
| `--accept-all` / `--accept-none` | Revision acceptance defaults, not remedy approval; cannot be combined |

See [routing rules](commands/autopsy.md) for precedence and incompatible combinations. Explicit intent wins over inferred next steps.

## Evidence and storage

[Shared contracts](skills/_shared/contracts.md) define claim origin, document support, external verification, confidence, causal finding IDs, user decisions and state. Reviewer agreement is not independent corroboration. A source saying something is not proof it is true outside that source.

Default review/revision has no web calls. Reviewers receive the proposal or access to its immutable snapshot, so sensitive content is also present in delegated contexts. Research flags authorize only approved claim material; use redacted claims for confidential work. They never authorize customer contact, purchases or experiments.

State lives beside the source in `.autopsy/<slug>/`; pasted input uses an explicit project directory. Supplying a saved snapshot reuses its existing ledger. The helper returns exact file paths and report IDs: use those instead of assuming a fixed verdict filename.

Snapshots, reports, hashes, context, answers and history survive repeated reviews. Reports of the same version do not overwrite one another. The original source is never automatically replaced and history is not pruned. State remains local by default; decide whether to track it, and add `.autopsy/` to your own ignore rules for confidential proposals.

## Install and update

This repository is a standalone plugin; it does not require the ClaudesMods marketplace.

```bash
claude plugin marketplace add z0rd0n88/idea-autopsy
claude plugin install idea-autopsy@idea-autopsy
```

For a local checkout:

```bash
git clone git@github.com:z0rd0n88/idea-autopsy.git
claude --plugin-dir ./idea-autopsy
```

After an authorized release:

```bash
claude plugin marketplace update idea-autopsy
claude plugin update idea-autopsy@idea-autopsy
```

Reload/restart the host as needed to use updated instructions. Both agent definitions are bundled under `agents/`. Claude Code discovers plugin agents there; other hosts can use the explicit paste fallback with restrictions included in the dispatch. The directory is not a parked roster. See the [official plugin reference](https://code.claude.com/docs/en/plugins-reference#agents) for component discovery.

## Version 2 compatibility

Version 2.0.0 changes revision outputs and state contracts. Revisions now include generated proposals, not only change plans. Evidence fields replace ambiguous legacy verification tags. Reports use immutable identities.

Legacy state is historical input, not automatically migrated or reclassified. The state helper offers explicit `import-legacy` with a preserved backup and review requirements. Inspect legacy inputs before opting in; old reviews do not become verified evidence. If a write is interrupted, use explicit recovery of the recorded transaction. Never repair shared state by choosing longer notes or overwriting another report.

## Implementation and checks

Python 3.10+ on a POSIX host, with only the standard library, supports the deterministic helpers:

- [policy.py](skills/_shared/policy.py): normalized verdict, routing, acceptance, questions and priority rules.
- [state.py](skills/_shared/state.py): validation, immutable identity and concurrent-safe persistence.
- [wordcount.py](skills/_shared/wordcount.py): evidence-preserving counting and explicit excerpts.
- [thresholds.json](skills/_shared/thresholds.json): the sole size-threshold configuration.
- [examples](examples/README.md): synthetic illustrations, including automatic revisions and incomplete evidence.

Run from the checkout:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
claude plugin validate .
```

The first command tests deterministic behavior and fixtures. The second checks package structure when Claude Code is installed. Neither establishes whether a model reliably judges evidence, classifies consequential changes or produces better ideas; actual model-based evaluations must be reported separately.

See [CLAUDE.md](CLAUDE.md) for contributor workflow and paired version bumps. It is contributor documentation, not automatically loaded plugin context; the skills explicitly load their shared runtime contract. The plugin validator may warn about that preserved root file.

## Research-informed review and validation

Reviews now use [observable judgment criteria](skills/_shared/judgment-rubric.md), check material forecasts against relevant comparison evidence when available, and assess a credible success mechanism alongside criticism. Reviews record source and model limitations explicitly. Agent revisions distinguish new evidence, corrected reasoning, presentation changes and authorized scope changes; fresh initial evaluation withholds prior verdicts and author attribution.

These safeguards draw on [academic research](docs/scholar-refs.md). Their effectiveness on real proposals remains unmeasured. The [validation protocol and card](docs/evaluation-validation.md) describe controlled comparisons, human review and prospective outcomes. Run the offline audit on explicitly synthetic fixtures:

```bash
python3 skills/_shared/evaluation_audit.py --request tests/fixtures/evaluation_audit_cases.json
```

The audit measures recorded consistency, abstention, reference agreement and revision regressions. It makes no model calls and does not change verdicts. Existing reports remain readable; missing historical provenance stays unknown.

## License

[MIT](LICENSE).
