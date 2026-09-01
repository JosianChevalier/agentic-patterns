---
description: "When running a pool of `claude -p` workers and you need to cap concurrency and total spend independently, without identity or billing surprises."
tags: [orchestration, headless, concurrency, agent-identity]
family: orchestration
---

# Slots vs budget — two orthogonal caps

`--slots` = concurrency width (CPU, commit serialization, rate limits); `--max-agents` = cumulative budget (guard against a queue that never empties). On each freed slot, **re-peek state** rather than planning the queue once — state moved. Pin `--model` on every `claude -p` (otherwise cost inherits the launcher's UI default). Stall detection = state-fingerprint diff at harvest (N consecutive no-change harvests → drain), not per-stream counters (false-positive on legitimately repeating gates). Spawn each worker with the parent env **minus `CLAUDE_CODE_SESSION_ID`**: inherited, every worker gets the orchestrator's session short → one apparent identity everywhere → the validator ≠ author guard silently dies. Corollary: the orchestrator learns a worker's short only by parsing the first lines of the worker's own stream-json (`system/init` event, `session_id` field, truncated to 8) — sole identity source for a dead agent, indexing force-release and per-agent commit counts; best-effort (unparseable → skip, logged, audit deferred). Refuse to start at all if `ANTHROPIC_API_KEY` is set: dozens of `claude -p` would silently switch from the subscription to billed API. The task peeked at spawn only selects the worker's *role prompt* — a label, never a truth: the worker claims for itself and may land on a different task (race between slots); all recovery and attribution index on the real `owner` field, never on spawn intent, and an in-memory `inflight` set prevents double-spawning without mutating the registry. Run orphan recovery *before* computing the stall fingerprint — otherwise a successful recovery counts as a no-change harvest and can trigger the drain; fingerprint fields: `(id, status, owner, note)`.

## Reference

`reference/consolidation-pipeline/orchestrate.py`, `reference/consolidation-pipeline/docs/specs/orchestrateur.md`, `reference/consolidation-pipeline/docs/philosophy/orchestrateur.md`; generic template plugging onto `templates/file-validation/`: `reference/templates/subagent-orchestrator/`
