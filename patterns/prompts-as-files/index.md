---
description: "When instructions to agents drift because they live in code string literals instead of one dedicated file."
tags: [prompts, doc-hygiene]
family: orchestration
---

# Prompts as files, single source of truth

An instruction addressed to agents is written once, in a dedicated `.md`: one `common.md` for rules shared by every role, plus one file per role; the orchestrator `cat`s the two to build each agent's prompt. Dividing line: **prompt file = what you tell an agent; spec = what the system enforces.** Specs reference prompt files by path, never copy them. (Origin: a 130-line Python string literal drifting from the `.md` it told agents to read.)

## Reference

`reference/consolidation-pipeline/prompts/`, `reference/consolidation-pipeline/docs/philosophy/prompts.md`
