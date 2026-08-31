---
description: "When N agents choosing their own next task collide or load the whole backlog into context."
tags: [task-lifecycle, concurrency, context-budget]
family: pipeline-core
---

# The script picks the task, not the agent

`claim_next` selects the next eligible task under the lock and prints exactly the start context the agent needs (`input:`, `note:`, `session:`). Structurally eliminates selection races and failed claims, and keeps the agent from ever loading the full registry. Second selection pattern, for boards with per-cell claims and no `claim_next` verb: the prompt orders "list ALL takeable cells, **draw one at random**, max 3 attempts then exit" — N agents all aiming at the first free cell would collide systematically; randomness is the cheapest anti-collision.

## Reference

`reference/consolidation-pipeline/task.py`; simple markdown-board instance: `reference/report-task.py`; liftable generic template (`# ADAPT:` zones, step-by-step duplication guide, known variants): `reference/templates/file-validation/`
