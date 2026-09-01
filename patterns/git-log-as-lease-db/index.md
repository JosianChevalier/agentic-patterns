---
description: "When you need orphan-lease recovery with zero persisted orchestrator state."
tags: [git, crash-recovery, state-management, task-lifecycle, orchestration]
family: orchestration
---

# `git log` as the lease database

Orphan recovery with zero persisted orchestrator state. The orchestrator keeps no database of who holds what: every claim and release is already a commit with a machine-parseable subject (`Claim <step> <slug> (<short>)` / `<Step> <slug>: <result> (<short>)`, where `<short>` is the agent's id). When a worker is dead (exited or killed — the precondition that makes its lease provably orphaned), the orchestrator lists commit subjects since the run's baseline SHA, filters to that agent's `<short>`, and pairs claims to releases on `(step, slug, short)`: any unpaired `Claim` → force-abandon through the normal release script in admin mode. Admin mode bypasses the ownership guard but **stays under the same flock** as live claims/releases (no TOCTOU with concurrent agents) and is an idempotent no-op when the lock no longer bears that `<short>`. History *is* the lease registry: nothing to persist, nothing to drift — it only holds because every transition is committed under the lock (`scripts-own-state`), so commit order is transition order.

## Reference

`reference/extraction-pipeline/orchestrate.py`, `reference/extraction-pipeline/release.py`
