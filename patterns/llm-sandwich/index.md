---
description: "When a deterministic algorithm drifts on fuzzy input and an LLM must patch a precious artifact without being able to damage it."
tags: [anti-hallucination, validation]
family: pipeline-core
---

# LLM sandwich — deterministic dump / LLM judgment / deterministic apply

A deterministic labeler (lexical similarity matching) drifted on noisy input; measurement showed the full artifact fits in one context window, so an agent judges better. But the agent must not rewrite the artifact freely — its blast radius is bounded by two deterministic ends:

- **dump** — deterministic: emits the items to judge, each numbered by `idx`, plus the auxiliary evidence the LLM needs. The `idx` is the only address the LLM can use.
- **LLM** — returns nothing but a JSON mapping `{idx: verdict}`. No file access, no rewrite.
- **apply** — deterministic: re-parses the original artifact and rewrites **only the header lines addressed by idx**. The body text is intact by construction, whatever the LLM returned — the *what* cannot change, only the *which label*.

Guards in `apply`:
- **Cardinality check** — the dump covers every item, so the mapping must too; a count mismatch means wrong input file (e.g. already-processed) → refuse outright.
- **Undecidable verdicts** (empty, low-confidence placeholder) leave the original label — the LLM can decline, never degrade.

Generalizes to any spot where an LLM patches an artifact that deterministic code produced: deterministic code decides *what is allowed to change* (the mutation surface), the LLM only supplies *values* within it.

## Reference

`reference/relabel_llm.py` (its deterministic companion — the drifting algorithm and the shared parsers — stayed in the origin repo)
