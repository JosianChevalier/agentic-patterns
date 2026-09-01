---
description: "When agent-written claims must be both mechanically traceable to sources and cognitively checked against what those sources actually say."
tags: [anti-hallucination, validation]
family: pipeline-core
---

# Two gates of different natures: sourcing (deterministic) vs fidelity (cognitive)

Anti-hallucination split. **Sourceability** — every claim ends with a citation token that must resolve — is a lint (`check.py`), wired into `done`. **Fidelity** — does the claim say what the source says — is an agent reading the span, resolving citations **back to ground truth** (not the intermediate fragment): one end-of-chain check covers distortion at both hops. Default posture: refute if in doubt. The fidelity check shards by **citation buckets**: citations counted per source, greedy-packed deterministically under a cap calibrated to the validator's time budget; an over-cited source becomes an atomic bucket, never split. `done` refuses a reduce with zero buckets — zero shards would make validation free.

## Reference

`reference/consolidation-pipeline/check.py`, `reference/consolidation-pipeline/docs/philosophy/gate-fidelite.md`
