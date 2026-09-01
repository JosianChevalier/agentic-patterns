---
description: "When writing the standing instructions for any `claude -p` worker, including the traps headless mode springs silently."
tags: [headless, prompts, permissions, orchestration]
family: orchestration
---

# Headless-worker preamble

Liftable boilerplate for any `claude -p` worker: one task then exit, never a second claim, no "while I'm here"; explicit `run_in_background: false` on every Bash (headless agents aren't woken); never `wait`/`sleep`-loops (refused silently outside allowlist); git only through the CLI verbs; read your session short from the claim output, not from `echo $VAR`. Two headless traps documented **in the prompt itself**: (a) an out-of-allowlist Bash in `-p` mode is refused without a prompt AND **cancels the sibling tool calls of the same turn** — the agent silently proceeds on partial data (hence `Bash(echo *)` allowlisted solely so reading one's session id never triggers it); (b) a tool result can surface one turn late → the prompt announces it and mandates a single `git log -1` confirmation, never a retry loop. The worker's Bash allowlist is also duplicated in prose in the prompt (with a "keep both in sync" comment): the agent knows upfront what is forbidden instead of floundering on silent refusals.

## Reference

`reference/consolidation-pipeline/prompts/common.md`, `reference/consolidation-pipeline/orchestrate.py` (the machine-side allowlist mirroring the prose, with the keep-in-sync comment and the `echo` rationale), `reference/extraction-pipeline/orchestrate.py` (embedded preamble carrying the late-tool-result trap and the single-`git log -1` rule)
