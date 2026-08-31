---
description: "When output quality degrades on long sessions and you need to size work so no agent approaches context instability."
tags: [context-budget, orchestration]
family: orchestration
---

# Small-context doctrine

Quality degrades well before the window limit (~100k loaded = unstable; ~60k working ideal). Consequences: disposable sessions (1 task/session), orchestrator manages volume — "not your endurance"; claim output carries the whole start context; per-claim **quotas** ("do your batch, release and exit even if the cell isn't done").

## Reference

`reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `reference/consolidation-pipeline/prompts/common.md`, quotas: `reference/extraction-pipeline/RESSOURCES_PROTOCOL.md`
