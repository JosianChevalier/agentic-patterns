---
description: "When task state must stay bounded, greppable, and crash-safe instead of growing as an append-only ledger."
tags: [state-management, git, crash-recovery, concurrency]
family: pipeline-core
---

# Tabular registry, not a ledger

Task state = one CSV row per task, mutated in place. Bounded by construction (doesn't grow with activity); history is free via `git log -- tasks.csv` since every transition is a commit. Read/write only through the `csv` module. `note` column carries structured tokens (`author:`, `ok:`, `fix:`, `correcting:<short>`). Writes are atomic: temp file **beside** the CSV (same filesystem → `os.replace` rename guaranteed atomic — a tmp in `/tmp` wouldn't be), suffixed with the PID (concurrent writers never share a temp); a watchdog SIGKILL mid-write can never leave a truncated registry. Timestamps are second-precision ISO strings compared *lexicographically*; changing the format needs no data migration when the new format is chosen so coexistence is benign: an old date-only value is a shorter prefix, sorts earlier, looks older — staleness false positives fall on the safe side (re-validate too much, never too little). "Migration without migration".

## Reference

`reference/consolidation-pipeline/_store.py`, `reference/consolidation-pipeline/task.py`, `reference/consolidation-pipeline/docs/specs/modele-donnees.md`
