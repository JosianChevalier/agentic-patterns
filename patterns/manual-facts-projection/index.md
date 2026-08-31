---
description: "When human-arbitrated facts must enter an agent pipeline through the same validation machinery as extracted facts."
tags: [validation, human-protocol, state-management]
family: pipeline-core
---

# Manual facts flow through the same machinery

Hand-arbitrated facts live as mini-ADRs (one fact per file, monotonic id = immutable citation key, body *is* the fact) and are **projected** into the pipeline as a synthetic fragment — so human input and extracted input converge through identical validation. Includes the `candidat` (human judged) vs `settled` (authority confirmed) distinction and an outgoing-questions queue that empties when the *outside world* answers.

## Reference

`reference/consolidation-pipeline/project_arbitrages.py`, `reference/consolidation-pipeline/arbitrages-protocol.md` (the mini-ADR protocol: format, triage rule, candidat→settled promotion, outgoing-questions queue)
