---
description: "When the same agent error recurs and its recovery procedure should become a reusable, error-anchored skill."
tags: [prompts, cognitive-bias, doc-hygiene, derived-views]
family: agent-authoring
---

# Skills as codified mistakes

A skill = the recovery procedure for an error an agent already made, not a how-to: the error is what makes the trigger recognizable next time, and it turns a one-off correction into a reusable fix. The best exemplars open with a "why — the error this corrects" section; the others encode the error as a gate or a hard prohibition. Domain-free exemplars: **store vs view** (a fact has one home; indexes/checklists are derived views, not duplicates — a template repeating a fact is a structural smell, not N edits) and **snapshot, don't watch** (draining a human's inbox file: one snapshot, empty it first — before asking anything, since a full inbox blocks the human —, work the frozen batch, ignore mid-run arrivals — mentioning them is the watcher impulse in disguise). Also: fact-change propagation (gate first: is the canonical fact really wrong, or is a downstream copy merely stale? then "you transcribe, you don't rewrite"; upstream is read, downstream is written; sweep by the fact's terms, never by its id) and open-question resolution (dig raw sources first — many open questions are false ones).

## Reference
`reference/harness/skills/domicile-unique/SKILL.md` (store vs view), `reference/harness/skills/flush-notes/SKILL.md` (snapshot, don't watch), `reference/harness/skills/changement-fact/SKILL.md` (fact-change propagation), `reference/harness/skills/resolution-flou/SKILL.md` (open-question resolution)
