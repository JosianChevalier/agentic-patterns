---
description: "When a sliding watchdog kills healthy agents whose long silent subprocesses freeze the liveness signal."
tags: [watchdog, background-monitoring, orchestration]
family: orchestration
---

# Heartbeat env var — long silent subprocesses under a sliding watchdog

The sliding watchdog reads liveness from the agent's JSONL log mtime — but a domain script doing one long burst (heavy binary extraction, media conversion) behind the Bash tool has its stdout buffered until completion: the log freezes and the watchdog kills a healthy agent mid-task. Contract: the orchestrator exports `ORCHESTRATE_HEARTBEAT=<per-agent tmp path>` into the subagent's env and its inactivity check watches log mtime **or** heartbeat mtime; the domain script touches that path every ~30s (well under the inactivity window) from a daemon thread started just before the long work. Hard rules on the script side: no-op when the var is absent (stays usable standalone/in tests), touch wrapped in try/except so a heartbeat bug never fails the real task, thread dies with the process.

## Reference

`reference/templates/subagent-orchestrator/README.md` (copyable Python + shell snippets), `reference/templates/subagent-orchestrator/orchestrate.py`
