---
description: "When many raw sources must feed synthesized outputs without any agent ever loading the full corpus."
tags: [context-budget, idempotency]
family: pipeline-core
---

# Map-reduce with an intermediate distillation layer

Map reads exactly one source and emits a distilled fragment, sectioned by keys from a shared controlled vocabulary (map never invents a key — that's what makes reduce's grep reliable); reduce greps fragments by key, loads only the matching sections, and never touches raw sources. The fragment layer is the buffer that absorbs volume: without it, reduce would have to reload the raw sources behind every fragment and blow its context. Reduce rebuilds its output from scratch on every run (file purged at claim, no incremental patching) — the consolidated output is a function of the fragments, never of its own previous version.

## Reference

`reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `reference/consolidation-pipeline/prompts/map.md`, `reference/consolidation-pipeline/prompts/reduce.md`
