---
description: "When downstream agents must enrich an extracted artifact but must be structurally unable to erode its source text."
tags: [anti-hallucination, validation]
family: pipeline-core
---

# Append-only gate — pristine snapshot + insertion state machine

Same family as `sourcing-fidelity-gates` (deterministic gate), for enrichment chains: downstream steps annotating an extracted artifact must only **add**, never touch the source text. At extraction, write a hidden pristine snapshot (`.extract.md`) beside the living file; the gate diffs snapshot vs current via `SequenceMatcher` opcodes — any `delete`/`replace` fails outright, and each `insert` block runs through a small state machine that accepts only the declared insertion shapes (blank lines, single embed lines, open/close-tagged free-form blocks; an unclosed tag is a violation). Agents get full freedom *inside* the allowed shapes, structurally zero ability to erode the source. Missing snapshot → dedicated error carrying the bootstrap command.

## Reference

`reference/extraction-pipeline/check_text_preservation.py`, black-box suite `patterns/blackbox-test-discipline/tests/test_check_text_preservation.py`
