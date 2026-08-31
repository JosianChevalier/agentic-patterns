---
description: "When many raw sources must feed synthesized outputs without any agent ever loading the full corpus."
tags: [context-budget, idempotency, state-management]
family: pipeline-core
---

# Map-reduce with an intermediate distillation layer

Map reads exactly one source, emits a distilled fragment; reduce greps fragments by key and never touches raw sources. The fragment layer is the buffer that absorbs volume. Reduce rebuilds from scratch (no incremental patching).

## Reference

`reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `reference/consolidation-pipeline/prompts/map.md`, `reference/consolidation-pipeline/prompts/reduce.md`
