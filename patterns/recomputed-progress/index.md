---
description: "When an agent's declared progress cannot be trusted and must be recomputed from the artifact itself."
tags: [anti-hallucination, task-lifecycle, git]
family: pipeline-core
---

# Progress recomputed from the artifact, never declared

The agent releases its claimed task with a bare `ok` — never a count. The release script recomputes the progress counter `K/N` itself: K (units actually completed) by parsing the produced artifact, N (units expected) from the artifact or from disk. Guards: `K > N` → refuse (impossible state); `K <` previous K (work was deleted) → refuse to commit; terminal values like `skip` (nothing to do, downstream steps short-circuit) are computed outcomes, forbidden as agent input. Lying about one's progress is structurally impossible. The commit message carries the *computed* value — the log is reparsed by other regexes downstream, so it must tell the truth.

## Reference

`reference/extraction-pipeline/release.py`
