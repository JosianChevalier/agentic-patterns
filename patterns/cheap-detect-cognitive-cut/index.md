---
description: "When oversize detection and cut decisions on large documents must not require reading their content."
tags: [context-budget, idempotency]
family: kb-conventions
---

# Cheap detection, cognitive cutting

Detect oversize on cheap metadata (line counts, image counts — zero content read); when an agent must decide *where* to cut, feed it a generated **outline** (headings + line counts), not the document. Freeze the cut by immutable id so idempotent re-inventory never re-cuts.

## Reference
`reference/consolidation-pipeline/docs/philosophy/scoping.md`
