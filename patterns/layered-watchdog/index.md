---
description: "When a time cap alone won't catch off-task agents that keep producing output, and kills must not leak child processes."
tags: [watchdog, orchestration, crash-recovery, background-monitoring]
family: orchestration
---

# Three-layer watchdog + semantic audit

A time cap doesn't catch a rabbit-hole: an off-task agent produces output continuously. Layers: (1) sliding inactivity on JSONL mtime → kill; (2) **semantic audit** — a cheap model reads a *digest* of the agent's own event log and returns a verdict, continue-by-default on any error; (3) absolute cap as final net. Post-kill orphan recovery = admin force-release indexed on the real owner field. Load-bearing implementation details:
- **One stream, four uses** — worker stdout as `--output-format stream-json --verbose`, redirected to a parent-opened *file* (never PIPE — buffer deadlock): its mtime feeds the sliding watchdog, its content feeds the audit digest, its first lines yield the session id, and the file is the post-mortem forensics.
- **Deterministic verdict pre-computed** — the orchestrator computes quota overrun itself and injects `PLAFOND: … → overrun|ok` into the audit prompt with "kill verdict, nothing to recount": code decides the quantifiable, the cheap model judges only the qualitative. Quota baseline = the unreleased board cell — claim/release hands the starting point for free, zero orchestrator state.
- **Audit disarmed, non-blocking, last-VERDICT-wins** — the audit subprocess gets no tools (everything inline in its prompt → it can't stall reading a 5 MB log), one audit in flight with its own deadline (a hung audit is killed, verdict = continue); parse the *last* `VERDICT:` line (the model deliberates before concluding); every error branch converges to continue. Anti-over-kill clause in the prompt: log tail shows the agent self-corrected → continue.
- **Digest bounded by construction** — constant-cost global counters (event total, `tool_use` by name, errors) + tail of the last 50 events, each field truncated, base64 blobs → `<image>`, unreadable log → dedicated string, never an exception. Digest size is invariant of log content — otherwise the audit would time out precisely on long-running agents, the ones it watches.
- **Kill the whole process group** — workers and audits spawned `start_new_session=True`; kill = `os.killpg(os.getpgid(pid), SIGKILL)` with idempotent `proc.kill()` fallback, then `wait()` to reap. A `claude -p` forks pipeline scripts/git that hold locks: killing only the claude process leaks children that block everyone behind a lock nobody will release.

## Reference

`reference/consolidation-pipeline/docs/specs/watchdog.md`; reference impl `reference/extraction-pipeline/orchestrate.py`; genericized (6 `# ADAPT:` zones, whole-process-group SIGKILL, orphan-claim auto-abandon): `reference/templates/subagent-orchestrator/`
