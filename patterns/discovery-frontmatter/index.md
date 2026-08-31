---
description: "When agents grep a whole corpus into context because there is no one-screen index saying which note to load when."
tags: [discovery, context-budget, doc-hygiene, derived-views]
family: kb-conventions
---

# Discovery index via frontmatter (`quand_piocher`)

Every note carries a frontmatter sentence — "load this note when…" — modeled on a skill's `description:`. A tiny script prints `<note> <sentence>` as the corpus's one-screen index; field presence is **linter-enforced** so the index can't rot; agent definitions make it the mandatory entry point (raw grep = complement, never entry). Kills the "grep the whole KB into context" blowup.

## Reference
`reference/consolidation-pipeline/piocher.py`, `reference/consolidation-pipeline/check.py`
