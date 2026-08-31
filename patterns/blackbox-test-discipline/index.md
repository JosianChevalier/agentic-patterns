---
description: "When testing orchestration/concurrency code and mocks or dangling subprocesses would lie to you."
tags: [testing, concurrency, orchestration]
family: harness-permissions
---

# Test discipline for orchestration code

Black-box CLI tests: real subprocesses against a `git init`'d tmpdir, deterministic session id, no mocks, fail-loud on missing deps. Concurrency tests = two real parallel claimers on the same row. Two hard rules: **the verdict is the summary line alone** (progress dots ≠ success; no summary = hang), and **every spawned subprocess has an immanent time bound** (bounded loop, never `while True`) so a failed external kill can't orphan a process.

## Reference
`reference/tests/README.md`, `reference/tests/test_concurrency.py`
