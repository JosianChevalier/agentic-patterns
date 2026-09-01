---
description: "When testing orchestration/concurrency code and mocks or dangling subprocesses would lie to you."
tags: [testing, concurrency, orchestration]
family: harness-permissions
---

# Test discipline for orchestration code

Black-box CLI tests: real subprocesses against a `git init`'d tmpdir, deterministic session id, no mocks, fail-loud on missing deps. Concurrency tests = two real parallel claimers on the same row. Two hard rules: **the verdict is the summary line alone** (progress dots ≠ success; no summary = hang), and **every spawned subprocess has an immanent time bound** (bounded loop, never `while True`) so a failed external kill can't orphan a process (the bound must sit well above the timeout under test, or it changes what is being tested). Caller-side sibling of that rule: the test's own wait on the child should be bounded too — the exemplar's `_launch_pair` in `test_concurrency.py` uses untimed `communicate()` (its claimers terminate on their own, but a hung claimer would hang the suite). Four fixture lines look anecdotal but each disarms a real trap — documented so a cleanup doesn't re-spring them:
- `commit.gpgsign false` in the repo fixture: on a machine with global commit signing, every test commit pops pinentry → the suite hangs.
- The fixture injecting the fake session id env var also *returns* the 8-char short the tests grep — injected value and asserted value have one source.
- State transitions are asserted through `git log` commit subjects (the public contract — every transition commits), never through internal state.
- The race test launches two real unsynchronized claimers and asserts `sorted([rc1, rc2]) == [0, non-zero]` — exactly one winner, whoever it is — and prints *both* stderrs on failure (a flaky race with one stderr is undebuggable).

## Reference
`patterns/blackbox-test-discipline/tests/README.md`, `patterns/blackbox-test-discipline/tests/conftest.py`, `patterns/blackbox-test-discipline/tests/test_concurrency.py`, `reference/harness/permissions-playbook.md` (pytest section: the two hard rules)

`tests/` is a verbatim copy of `common/outils/tests/` from the origin project (suites not runnable here — exemplars of the discipline).
