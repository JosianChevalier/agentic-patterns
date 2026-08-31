---
description: "When several agent sessions share one working tree and must commit without clobbering each other."
tags: [git, concurrency, permissions]
family: harness-permissions
---

# Shared-worktree git concurrency rules

Several sessions, one working tree, no isolated worktrees: never stage globally; commit path-scoped (`git commit -m msg -- <paths>` uses a temp index, ignores others' staging); never touch files another agent modified; scripts commit their own transitions so locks are visible in history. Commit convention (compact layer-scope prefix) doubles as a greppable machine contract. Plumbing for scripts that commit: retry **only** when stderr contains `index.lock` (short backoff — collision with out-of-flock commits from another pipeline in the same repo; any other error propagates, never delete the lock yourself); no-op-safe scoped commit = `git add -- <paths>` (untracked files need it), `git diff --cached --quiet -- <paths>` as predicate, then `commit -- <paths>` — caller commits without pre-checking; guard any pathspec on a possibly-empty dir with `git ls-files` first (else "pathspec did not match").

## Reference
`reference/harness/permissions-playbook.md`, `reference/harness/rules/commit-messages.md`
