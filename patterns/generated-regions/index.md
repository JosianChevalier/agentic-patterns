---
description: "When a script must maintain part of a human-readable file without destroying hand edits or resetting progress on re-runs."
tags: [derived-views, idempotency, state-management, doc-hygiene]
family: kb-conventions
---

# Generated regions inside human files

`inventory.py` repopulates a board between `<!-- INVENTORY:BEGIN/END -->` markers — machine-owned region, human-readable file, reconciled idempotently (merge by id). The reconciliation that makes it safe: (a) a row whose file vanished from disk is **carried over, never dropped** (deletion is a human decision; hand-added rows survive); (b) asymmetric per-column merge — factual columns refreshed from discovery, state columns preserved (a re-scan must never reset progress); (c) two generated regions of different natures in the same file: the inventory (*reconciled*) vs the duplicates list (*regenerated* each run — a derived view); (d) each marker must appear exactly once, else abort (corrupted file); (e) `--reset` is the sole, explicit destructive escape hatch.

## Reference
`reference/extraction-pipeline/inventory.py`, `reference/consolidation-pipeline/inventory.py`
