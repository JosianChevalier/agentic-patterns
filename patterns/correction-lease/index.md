---
description: "When a rejected artifact should be fixed in place by a validator rather than thrown back to the queue, with concurrent correctors serialized."
tags: [validation, task-lifecycle, concurrency, crash-recovery]
family: pipeline-core
---

# Correction lease — fix in place, never nuclear reject

A rejected artifact isn't thrown back to `todo`. A validator edits it in place (`corrige`); all sibling validation passes reset to 0/N (the content is no longer what they read). The edit spans multiple CLI calls, outside the lock → concurrent correctors serialized by a **durable lease** in the row's note (`correcting:<short>`). Orphaned corrector: clear lease + `git checkout` the artifact back.

## Reference

`reference/consolidation-pipeline/docs/specs/modele-donnees.md` (§ lease), `reference/consolidation-pipeline/task.py`
