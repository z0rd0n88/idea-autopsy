# CLAUDE.md

## Versioning: bump on every content change

Every change to a skill, script, command, or agent in this repo bumps the plugin version before the PR opens. Two files move together, same bump, same commit:

| File | Field |
|---|---|
| `.claude-plugin/plugin.json` | `version` |
| `.claude-plugin/marketplace.json` | `plugins[0].version` |

Patch for fixes and wording, minor for a new skill or script, major for a breaking change to a skill's inputs or outputs. A PR that changes content without a bump is not mergeable: the installed plugin keeps serving the old text and the change is invisible to every session.

After the merge, the cache does not refresh itself. Run both, then restart:

```bash
claude plugin marketplace update idea-autopsy && claude plugin update idea-autopsy@idea-autopsy
```

## Workflow

Feature branch in a worktree, never a direct commit to main. Stage explicit paths. Merge from the primary checkout, then remove the worktree, the local branch, and the remote branch; `--delete-branch` on `gh pr merge` has left remote branches behind here, so check `git ls-remote --heads origin` afterwards.
