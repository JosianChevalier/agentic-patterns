---
description: "When oversize detection and cut decisions on large documents must not require reading their content."
tags: [context-budget, idempotency]
family: kb-conventions
---

# Cheap detection, cognitive cutting

A map step under a small-context budget must never read a large source in one block, so splitting it into thematic chunks is the normal mechanism, not an edge case. Two acts, two actors: **detecting** oversize is a script on cheap metadata (`wc -l` + image count, threshold e.g. `lines > 600 OR imgs > 6` — zero content read); **cutting** is an agent, because thematic boundaries are a judgment, not a computation (a script slicing every N lines cuts mid-reasoning). The objection "the agent burns its context reading the source to decide where to cut" fails: it reads only a generated **outline** — heading per structural unit (slide, page, section) + line count under each — which stays ~200 lines even for a 190-unit document; judgment is delegated without paying for the read. Cut doctrine: follow document order (no non-contiguous regrouping — clustering a theme's occurrences belongs to the downstream reduce, and doing it here would require reading content); the structural unit is the atom (boundaries fall on unit edges), except a single oversize unit may be subdivided by bare line ranges; the ~500-line target is indicative, the split step records the agent's ranges unchecked. Accepted tradeoff: the cut is non-deterministic (two runs could split differently), but it is confined to the *first* scoping — the parent task flips to `status=split`, children get ids (`map:<src>#k`), and an idempotent re-inventory that merges by id sees them and never re-cuts. The outline is regenerable scratch; losing it costs nothing. Deferred: a source that grows after re-extraction is not re-split (a `stale` marking, only if missed re-reduces are observed).

## Reference
`reference/consolidation-pipeline/docs/philosophy/scoping.md`
