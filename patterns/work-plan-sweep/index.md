---
description: "When work plans are distributed across layers but \"what remains to do, repo-wide?\" must be answerable with one grep."
tags: [discovery, work-tracking, doc-hygiene]
family: kb-conventions
---

# Work-plan sweep via anchored frontmatter (`plan_de_travail`)

Work plans stay distributed (each in the layer it concerns) but discoverable by one grep: any file that *is* a plan carries frontmatter `plan_de_travail: "<what must empty>"`. `^`-anchored grep keeps out prose that merely discusses plans. Pair with visible step checkboxes + a current-step marker so a zero-context session resumes without reading the whole file.

## Reference
`reference/work-index/CLAUDE.md` (frontmatter convention + checkbox/current-step rule), live frontmatter instance: `reference/work-index/INDEX.md`; convention as stated to every session: `reference/harness/CLAUDE.racine.md` (§3)
