---
description: "When testing orchestration/concurrency code and mocks or dangling subprocesses would lie to you."
tags: [testing, concurrency, orchestration]
family: harness-permissions
---

# Test discipline for orchestration code

Black-box CLI tests: real subprocesses against a `git init`'d tmpdir, deterministic session id, no mocks, fail-loud on missing deps. Concurrency tests = two real parallel claimers on the same row. Two hard rules: **the verdict is the summary line alone** (progress dots ≠ success; no summary = hang), and **every spawned subprocess has an immanent time bound** (bounded loop, never `while True`) so a failed external kill can't orphan a process. (The copied exemplar suite predates this rule in one spot: two untimed `communicate()` calls in `test_concurrency.py` — the rule stands, the exemplar deviates.)

## Reference
`patterns/blackbox-test-discipline/tests/README.md`, `patterns/blackbox-test-discipline/tests/test_concurrency.py`

`tests/` is a verbatim copy of `common/outils/tests/` from the origin project (suites not runnable here — exemplars of the discipline).
