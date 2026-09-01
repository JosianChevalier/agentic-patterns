---
description: "When several agent sessions share one working tree and must commit without clobbering each other."
tags: [git, concurrency, permissions]
family: harness-permissions
---

# Shared-worktree git concurrency rules

Several sessions, one working tree, no isolated worktrees: never stage globally; commit path-scoped (`git commit -m msg -- <paths>` uses a temp index, ignores others' staging); never touch files another agent modified; scripts commit their own transitions so locks are visible in history. Commit convention doubles as a greppable machine contract: a compact `(scope)` prefix in the title listing the areas touched (`(3)`, `(2-5)`, `(0,2,4-5)`). Plumbing for scripts that commit: retry **only** when stderr contains `index.lock` (short backoff — collision with out-of-flock commits from another pipeline in the same repo; any other error propagates, never delete the lock yourself); no-op-safe scoped commit = `git add -- <paths>` (untracked files need it), `git diff --cached --quiet -- <paths>` as predicate, then `commit -- <paths>` — caller commits without pre-checking; guard any pathspec on a possibly-empty dir with `git ls-files` first (else "pathspec did not match"). Repo-root resolution must be worktree-compatible: walk ancestors testing `.git` with `.exists()`, never `.is_dir()` — in a git worktree `.git` is a *file*; the ancestor walk also makes the tool insensitive to its own depth (a `git mv` across layers breaks nothing).

## Reference
`reference/harness/permissions-playbook.md` (concurrency rules, locks committed immediately), `reference/harness/rules/commit-messages.md` (scope-prefix convention), `reference/consolidation-pipeline/_store.py` (`_run_git` index.lock retry, no-op-safe `commit`, `find_root`), `reference/extraction-pipeline/release.py` (`git ls-files` guard before `commit -- <dir>`), `reference/extraction-pipeline/_paths.py` (`find_root` with `.exists()`)
