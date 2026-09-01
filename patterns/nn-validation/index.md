---
description: "When you need artifact review that cannot be gamed: distinct reviewers, script-enforced guards, machine-checkable identity."
tags: [validation, agent-identity]
family: pipeline-core
---

# Validation by N/N convergence of distinct agents

An artifact converges when N *consecutive* passes by N *distinct* agents say `ok`. Guards enforced by script, not by instruction: validator ≠ author, no two passes by the same agent, validation only after production. Agent identity = 8-char session short, stamped in every commit subject in a fixed format — the format is a machine contract (scripts grep history to enforce guards and attribute work).

## Reference

`reference/consolidation-pipeline/task.py`, `reference/consolidation-pipeline/docs/specs/validate.md`; generic template (state machine, verdicts `ok`/`corrected`/`flagged`, script-enforced guards): `reference/templates/file-validation/`, black-box suite `patterns/blackbox-test-discipline/tests/test_template_file_validation.py`
