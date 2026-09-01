---
description: "When work plans are distributed across the repo but \"what remains to do, repo-wide?\" must be answerable with one grep."
tags: [discovery, work-tracking, doc-hygiene]
family: kb-conventions
---

# Work-plan sweep via anchored frontmatter (`plan_de_travail`)

Work plans stay distributed (each next to the work it concerns, no central list) but discoverable by one grep: any file that *is* a plan carries frontmatter, before the title, `plan_de_travail: "<what must empty — and when it counts as empty>"` (a plan is a file whose remaining content = undone work). Any repo-wide "what's left to do / clean / decide?" question starts with the sweep: `grep -rl '^plan_de_travail:'` lists the open plans, `grep -rh` prints their sentences. The `^` anchor keeps out prose that merely discusses plans — so the field goes **only** on files that are plans, never on the ones defining the notion. Pair with visible step checkboxes + a current-step marker so a zero-context session resumes without reading the whole file.

## Reference
`reference/work-index/CLAUDE.md` (frontmatter convention + checkbox/current-step rule), live frontmatter instance: `reference/work-index/INDEX.md`; convention as stated to every session: `reference/harness/CLAUDE.racine.md` (§3)
