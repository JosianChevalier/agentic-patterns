# Sequential flow runner — design note

Turn agent-orchestrated code flows (a TDD loop, an atomic-refactor while-loop) into a **Python orchestrator driving disposable `claude -p` workers**. A composition of catalogued patterns (`scripts-own-state`, `script-picks-task`, `sourcing-fidelity-gates`, `layered-watchdog`, `prompts-as-files`, `headless-preamble`, `small-context-doctrine` in `../patterns/`) applied to a shape the original pipeline never instantiated: a **per-task sequential state machine** instead of a queue of independent tasks.

Case study: a real harness where an interactive Claude session orchestrates subagents through skill files — verbatim copies in `reference/` (dispatch rule, two flow skills, five role agents, commit wrapper + hook).

## Measured — the agent-orchestrated prototype

The case-study harness is a working prototype (interactive session as orchestrator, subagents as steps). Two results that reframe the note:
- **Economic.** Step granularity (one role, one bounded move) is cheap — the per-step cold-start cost is not a concern.
- **Faster — not because agents code faster.** The gain is that the **human's cognitive load flows**: bounded steps, structured verdicts, one decision at a time. Throughput of the sociotechnical system is bounded by the human in the loop (`human-attention-protocol`), and this shape unblocks them.

So the **primary value is human-in-the-loop throughput**; F.1 (unskippable steps) is the secondary gain. The Python runner earns its keep only for what the agent orchestrator cannot do: **unattended runs**, and closing the residual **slips** a cognitive orchestrator still makes despite the armor.

## The structural difference

The catalogued orchestrator drains a queue of independent tasks with N parallel workers. These flows are sequential state machines per task, with **cognitive exit conditions** ("anything left to refactor?"). The adaptation trio:
- the `while` loop lives in **Python** (script owns state and step transitions),
- each step = **one disposable `claude -p` session** (inter-step state in files, never in a long session),
- the exit condition = a **structured agent verdict**, parsed, never interpreted.

## Patterns

### F.0 Behavior selection is upstream
The runner never decides *what* to test next. An **upstream step** (a higher-level flow, or the human) produces the ordered list of behaviors; the TDD loop consumes it one behavior at a time. Input contract of the runner = that list (persisted in the flow state file, F.7); the tester role turns *one* behavior into *one* failing test, it doesn't pick behaviors. Keeps the cognitive "what next?" out of the loop and in the hands of whoever holds the goal.

### F.1 The anti-rationalization armor becomes code
Half of the TDD skill (Iron Law, rationalization tables, red flags, a mandatory task-checklist) exists to keep a *cognitive* orchestrator from skipping steps. A Python state machine cannot rationalize: steps are unskippable by construction, and all that prose disappears. What survives as prompts: the **role definitions only** (tester, green-implementor, tdd-refactorer, refactorer). Sharpens `prompts-as-files`'s dividing line: prompt = what you tell an agent; the loop itself = code.
→ `reference/skills/test-driven-development.md` (compare its bulk to `reference/agents/`)

### F.2 Structured footer as loop condition
The role agents already end with a machine contract (`CHANGED:` / `STATUS: MORE_TO_DO | NOTHING_TO_REFACTOR` / `NEXT:`). The runner reads the worker's final message (`claude -p --output-format json`), parses the footer, and `STATUS` drives the state machine. Hardening: an unparseable footer = fail-loud (retry or park), **never interpret prose**.
→ `reference/agents/refactorer.md`, `tdd-refactorer.md`

### F.3 Verify gates go deterministic
"Verify RED" / "verify GREEN" are cognitive today (an agent reads test output). The script runs the test runner and classifies: assertion failure vs error vs compilation failure. The green-implementor's "~20 lines max" guard = `git diff --stat`. Instance of `sourcing-fidelity-gates`'s split: everything mechanizable becomes a lint; cognition only where irreducible.
→ `reference/skills/test-driven-development.md` (§ Verify RED / Verify GREEN)

### F.4 The committer dissolves into the script
The committer agent is a cheap model doing deterministic work: path-scoped staging, wrapper invocation, pre-commit-reformat retry. Per `scripts-own-state`, that's runner code. The commit subject ≈ the `CHANGED` line + the goal the runner already knows; at most a micro cheap-model call for phrasing.
→ `reference/agents/committer.md`, `reference/scripts/commit.sh`, `block-direct-commit.sh`

### F.5 One step, one disposable session
The runner composes each worker's start context (failing-test content, file paths, goal) the way `claim_next` prints a claim — the worker never explores. Headless preamble (`headless-preamble`) concatenated to every role prompt; prompts stay files (`prompts-as-files`).

### F.6 Watchdog subset
Inactivity on JSONL mtime + absolute cap suffice — per-step verdicts already bound the work. The semantic audit (`layered-watchdog`) survives only for **directed refactoring**, whose "check direction via reports" is cognitive: a cheap model reading the accumulated `NEXT` lines — or the human.

### F.7 Flow state in a file, no locks
A JSON state file (current phase, current behavior, test list) makes the flow crash-resumable. Sequential and single-flow: no registry, no `flock`. Shared-worktree rules (`shared-worktree-git`) return only when several flows share one repo.

### F.8 `NEEDS_HUMAN` — the headless escalation channel
The role agents say "ask the user if risky or ambiguous"; a headless worker can't ask. Extend the footer contract with `STATUS: NEEDS_HUMAN`: the worker writes its question to a file and exits; the runner parks the flow. Sequential analogue of `manual-facts-projection`'s outgoing-questions queue.

## Reference map

| Path | Origin (`.ai/` of a Java project harness) | What it is |
|---|---|---|
| `reference/one-change-one-commit.md` | `rules/` | Dispatch rule: which flow for which request, refactor→TDD→cleanup sequence |
| `reference/skills/atomic-refactoring.md` | `skills/` | While-loop flow: directed & cleanup modes, one tiny move per cycle |
| `reference/skills/test-driven-development.md` | `skills/` | Red-green-refactor flow, new-code & existing-code variants |
| `reference/agents/` | `agents/` | The five roles: tester, green-implementor, tdd-refactorer, refactorer, committer |
| `reference/scripts/` | `scripts/`, `hooks/` | Commit wrapper + hook blocking direct `git commit` |
