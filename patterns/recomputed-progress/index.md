---
description: "When an agent's declared progress cannot be trusted and must be recomputed from the artifact itself."
tags: [anti-hallucination, task-lifecycle, git]
family: pipeline-core
---

# Progress recomputed from the artifact, never declared

The agent releases with a bare `ok`; the script recounts K by parsing the real file and N from disk. Guards: `K > N` → refuse; `K <` previous K (work was deleted) → refuse to commit; `skip` is a computed value, forbidden as input. Lying about one's progress is structurally impossible. The commit message carries the *computed* value — the log is reparsed by other regexes downstream, so it must tell the truth.

## Reference

`reference/extraction-pipeline/release.py`
