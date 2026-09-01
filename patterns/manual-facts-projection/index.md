---
description: "When human-arbitrated facts must enter an agent pipeline through the same validation machinery as extracted facts."
tags: [validation, human-protocol, state-management]
family: pipeline-core
---

# Manual facts flow through the same machinery

Hand-arbitrated facts live as mini-ADRs (one fact per file, monotonic id = immutable citation key — a wrong fact is corrected *in place*, never re-issued, so citations never break; body *is* the fact) and are **projected** into the pipeline as a synthetic fragment that ranks top of the source hierarchy (wins any conflict with extracted material) — so human input and extracted input converge through identical validation. The projection is deterministic, zero LLM: a hand-arbitrated fact is *already* distilled and themed, so it skips the map stage entirely and a malformed ADR fails the projection loudly. Includes the `candidat` (human judged) vs `settled` (authority confirmed) distinction, stamped on each projected fact so provenance survives into the final artifact, and an outgoing-questions queue that empties when the *outside world* answers.

## Reference

`reference/consolidation-pipeline/project_arbitrages.py`, `reference/consolidation-pipeline/arbitrages-protocol.md` (the mini-ADR protocol: format, triage rule, candidat→settled promotion, outgoing-questions queue)
