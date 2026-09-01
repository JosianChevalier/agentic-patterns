---
description: "When output quality degrades on long sessions and you need to size work so no agent approaches context instability."
tags: [context-budget, orchestration]
family: orchestration
---

# Small-context doctrine

Quality degrades well before the window limit (~100k loaded = unstable; ~60k working ideal). Consequences: disposable sessions (1 task/session, then exit — the orchestrator relaunches a fresh one); volume is managed by the number of agents launched, "not your endurance"; the claim command re-prints the full start context (input path, notes, session id) so an agent never greps to bootstrap; per-claim **quotas** ("do your batch, release and exit even if the unit of work isn't finished — the rest is for the next agent").

## Reference

`reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `reference/consolidation-pipeline/prompts/common.md`, quotas: `reference/extraction-pipeline/RESSOURCES_PROTOCOL.md`
