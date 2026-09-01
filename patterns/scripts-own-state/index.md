---
description: "When agents hand-edit shared state and you need deterministic guarantees (atomic transitions, serialization, trustworthy history) separated from agent judgment."
tags: [state-management, concurrency, git, crash-recovery]
family: pipeline-core
---

# Scripts own state, agents own cognition

The foundational rule. Deterministic guarantees (who holds what, atomic transitions, serialization, commit formats) belong to a CLI under `flock`; judgment (distilling, cutting, validating meaning) belongs to agents. An agent never hand-edits state: it calls a verb (`claim_next`, `done`, `release`…), does its cognitive work, writes *its* artifact; the CLI verifies and commits. Single mutation authority: one script, one lock. Contract of the critical section: read/write state **and commit** before releasing the lock — the transition is visible to others the moment the lock drops, and commit order = real transition order (git log becomes trustworthy as a journal, which `git-log-as-lease-db` builds on). Two write-atomicity doctrines, both deliberate: the full pipeline does tmp+rename (`tabular-registry`); the minimal one does a direct `write_text` — **the flock is the atomicity and git the recovery** (crash mid-write → `git checkout` from the last transition commit). Locking + a committed baseline replace atomic writes for a small pipeline — document it as a choice so nobody "fixes" it. In the minimal pipeline the lock sidecar also lives outside the repo (`$TMPDIR/<project>/task.lock`, survives checkouts; machine-global but per-repo state → test-safe); the full one keeps an untracked lockfile at repo root.

## Reference

`reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `reference/consolidation-pipeline/docs/specs/modele-donnees.md`, `reference/templates/file-validation/task.py`
