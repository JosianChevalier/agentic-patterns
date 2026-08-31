---
description: "When an agent launches a long background script and goes blind or blocked waiting for it."
tags: [orchestration, background-monitoring, headless, permissions, agent-identity]
family: orchestration
---

# Banner-as-monitor — long background scripts under an agent

The problem: an agent that backgrounds a long script isn't woken when it ends, so it falls back to foreground waits and goes blind/blocked. The package:
1. **Flushed line-per-event log** (stdout + logfile — unflushed = invisible until exit);
2. **Deterministic terminal marker** as the log's last line, so any poller knows "over";
3. **Startup banner addressed to the launching agent** ("TO THE AGENT WHO LAUNCHED THIS") forbidding foreground waits and giving the exact monitor command;
4. **`watch.py <run-id>`** replacing inline tail loops (an inline loop carries the run-id in its command string → un-allowlistable → prompts every run);
5. **PostToolUse hook** that re-injects the banner into the launching agent's context when the launch command matches and `run_in_background == true` (the real banner goes to a stdout file nobody reads).
Per-agent progress counting = grep the agent's short in commit subjects, never a global `HEAD` delta (wrong under parallel commits); exact command: `git rev-list --count -F --grep=<short> <sha_at_spawn>..HEAD` — `-F` (the short is a literal, not a regex), window from the SHA captured at spawn, global-delta fallback when no short was detected. Hook implementation: the whole PostToolUse hook is one `jq -c` filter — predicate (command matches `orchestrate.py` AND `run_in_background == true`) → emit the context-injection object, else emit nothing (empty output = no-op, zero exit-code handling). The injected monitor command is pasteable as-is because hook and script **re-derive the same run-id from the same seed** (`session_id[0:8]`), with no channel between them.

## Reference

`reference/consolidation-pipeline/watch.py`, `reference/consolidation-pipeline/hooks/orchestrate_launch_banner.sh`, `reference/consolidation-pipeline/docs/philosophy/orchestrateur.md`, hook wiring in `reference/harness/settings.json`
