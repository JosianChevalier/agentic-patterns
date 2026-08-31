---
description: "When agents either bloat on rationale while applying rules or change rules whose tradeoffs they never read."
tags: [doc-hygiene, context-budget]
family: kb-conventions
---

# Specs / philosophy split with a reading contract

Two doc trees: `specs/` (each rule once, no justification — read when *applying*) and `philosophy/` (tradeoffs, measured reality, named residual risks — read when *changing* the spec). Spec sections point at their justifying philosophy page; spec README carries "frozen decisions — don't re-litigate without going through philosophy". Fixes both failure modes: agents bloating on rationale, and agents changing rules they don't understand.

## Reference
`reference/consolidation-pipeline/docs/specs/README.md`, `reference/consolidation-pipeline/docs/philosophy/README.md`
