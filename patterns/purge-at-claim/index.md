---
description: "When an agent rebuilding an output would anchor on the previous version instead of re-deriving it from inputs."
tags: [cognitive-bias, task-lifecycle, crash-recovery]
family: pipeline-core
---

# Purge the output at claim — code guard against anchoring

When an agent claims a rebuild (reduce), the script `unlink()`s the previous version of the output file before handing over. This mechanically forces a fresh `Write`: an `Edit` would require a `Read`, anchoring the agent on the old text instead of re-deriving from the fragments. The purge happens under the lock but is **not committed** (crash → HEAD intact); `reopen` doesn't purge (the corpus stays greppable while the task waits). Purest instance of "a code guard against an agent's cognitive bias".

## Reference

`reference/consolidation-pipeline/task.py`
