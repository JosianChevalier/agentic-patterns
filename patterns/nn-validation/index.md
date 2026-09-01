---
description: "When you need artifact review that cannot be gamed: distinct reviewers, script-enforced guards, machine-checkable identity."
tags: [validation, agent-identity]
family: pipeline-core
---

# Validation by N/N convergence of distinct agents

An artifact converges when N *consecutive* passes by N *distinct* agents say `ok`. Guards enforced by script, not by instruction: validator ≠ author, no two passes by the same agent, validation only after production. Agent identity = 8-char session short, stamped in every commit subject in a fixed format — the format is a machine contract (scripts grep history to enforce guards and attribute work). Load-bearing details:
- **`owner` as pass semaphore** — claiming a validation pass sets `owner=<short>` without touching `status`; after the first ok, owner is *cleared* to free the seat for the next validator; selection excludes rows with a non-empty owner. One field acting as a sub-state-machine.
- **TOCTOU-safe parent rollup** — on the final ok: child→done AND the "all siblings done → parent done" test run in the same critical section.
- **History guards fail closed** — the validator ≠ author guard greps git history for the author's commit; *none found* → the claim is refused: a broken history blocks instead of opening a hole in the N/N.

## Reference

`reference/consolidation-pipeline/task.py`, `reference/consolidation-pipeline/docs/specs/validate.md`; fail-closed history guard: `reference/extraction-pipeline/claim.py`; generic template (state machine, verdicts `ok`/`corrected`/`flagged`, script-enforced guards): `reference/templates/file-validation/`, black-box suite `patterns/blackbox-test-discipline/tests/test_template_file_validation.py`
