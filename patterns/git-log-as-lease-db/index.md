---
description: "When you need orphan-lease recovery with zero persisted orchestrator state."
tags: [git, crash-recovery, state-management, task-lifecycle, orchestration]
family: orchestration
---

# `git log` as the lease database

Orphan recovery with zero persisted orchestrator state: diff the commit subjects — any `Claim <step> <slug> (<short>)` without a paired release commit → force-abandon (admin mode bypasses the ownership guard but **stays under flock**, idempotent no-op). History *is* the lease registry: nothing to persist, nothing to drift.

## Reference

`reference/extraction-pipeline/orchestrate.py`, `reference/extraction-pipeline/release.py`
