# Agentic patterns — index

Patterns extracted from a real multi-agent project: a knowledge base built and validated entirely by disposable Claude Code sessions, orchestrated by scripts, feeding a human-arbitrated deliverable. Domain content stripped; machinery kept.

Two families: **harness** (running agents on code/tasks) and **KB** (agent-maintained knowledge). Each entry: the problem, the mechanism, where the reference lives. `reference/` holds verbatim copies of the original files (French; genericization is iterative — the reasoning is the asset).

---

## 1. Pipeline core (state & lifecycle)

### 1.1 Scripts own state, agents own cognition
The foundational rule. Deterministic guarantees (who holds what, atomic transitions, serialization, commit formats) belong to a CLI under `flock`; judgment (distilling, cutting, validating meaning) belongs to agents. An agent never hand-edits state: it calls a verb (`claim_next`, `done`, `release`…), does its cognitive work, writes *its* artifact; the CLI verifies and commits. Single mutation authority: one script, one lock.
→ `reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `docs/specs/modele-donnees.md`

### 1.2 Tabular registry, not a ledger
Task state = one CSV row per task, mutated in place. Bounded by construction (doesn't grow with activity); history is free via `git log -- tasks.csv` since every transition is a commit. Read/write only through the `csv` module. `note` column carries structured tokens (`author:`, `ok:`, `fix:`, `correcting:<short>`).
→ `reference/consolidation-pipeline/_store.py`, `task.py`, `docs/specs/modele-donnees.md`

### 1.3 The script picks the task, not the agent
`claim_next` selects the next eligible task under the lock and prints exactly the start context the agent needs (`input:`, `note:`, `session:`). Structurally eliminates selection races and failed claims, and keeps the agent from ever loading the full registry.
→ `reference/consolidation-pipeline/task.py`; simple markdown-board instance: `reference/report-task.py`

### 1.4 Validation by N/N convergence of distinct agents
An artifact converges when N *consecutive* passes by N *distinct* agents say `ok`. Guards enforced by script, not by instruction: validator ≠ author, no two passes by the same agent, validation only after production. Agent identity = 8-char session short, stamped in every commit subject in a fixed format — the format is a machine contract (scripts grep history to enforce guards and attribute work).
→ `reference/consolidation-pipeline/task.py`, `docs/specs/validate.md`

### 1.5 Correction lease — fix in place, never nuclear reject
A rejected artifact isn't thrown back to `todo`. A validator edits it in place (`corrige`); all sibling validation passes reset to 0/N (the content is no longer what they read). The edit spans multiple CLI calls, outside the lock → concurrent correctors serialized by a **durable lease** in the row's note (`correcting:<short>`). Orphaned corrector: clear lease + `git checkout` the artifact back.
→ `reference/consolidation-pipeline/docs/specs/modele-donnees.md` (§ lease), `task.py`

### 1.6 Map-reduce with an intermediate distillation layer
Map reads exactly one source, emits a distilled fragment; reduce greps fragments by key and never touches raw sources. The fragment layer is the buffer that absorbs volume. Reduce rebuilds from scratch (no incremental patching).
→ `reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `prompts/map.md`, `prompts/reduce.md`

### 1.7 Two gates of different natures: sourcing (deterministic) vs fidelity (cognitive)
Anti-hallucination split. **Sourceability** — every claim ends with a citation token that must resolve — is a lint (`check.py`), wired into `done`. **Fidelity** — does the claim say what the source says — is an agent reading the span, resolving citations **back to ground truth** (not the intermediate fragment): one end-of-chain check covers distortion at both hops. Default posture: refute if in doubt.
→ `reference/consolidation-pipeline/check.py`, `docs/philosophy/gate-fidelite.md`

### 1.8 Manual facts flow through the same machinery
Hand-arbitrated facts live as mini-ADRs (one fact per file, monotonic id = immutable citation key, body *is* the fact) and are **projected** into the pipeline as a synthetic fragment — so human input and extracted input converge through identical validation. Includes the `candidat` (human judged) vs `settled` (authority confirmed) distinction and an outgoing-questions queue that empties when the *outside world* answers.
→ `reference/consolidation-pipeline/project_arbitrages.py`

---

## 2. Orchestration

### 2.1 Slots vs budget — two orthogonal caps
`--slots` = concurrency width (CPU, commit serialization, rate limits); `--max-agents` = cumulative budget (guard against a queue that never empties). On each freed slot, **re-peek state** rather than planning the queue once — state moved. Pin `--model` on every `claude -p` (otherwise cost inherits the launcher's UI default). Stall detection = state-fingerprint diff at harvest (N consecutive no-change harvests → drain), not per-stream counters (false-positive on legitimately repeating gates).
→ `reference/consolidation-pipeline/orchestrate.py`, `docs/specs/orchestrateur.md`, `docs/philosophy/orchestrateur.md`

### 2.2 Banner-as-monitor — long background scripts under an agent
The problem: an agent that backgrounds a long script isn't woken when it ends, so it falls back to foreground waits and goes blind/blocked. The package:
1. **Flushed line-per-event log** (stdout + logfile — unflushed = invisible until exit);
2. **Deterministic terminal marker** as the log's last line, so any poller knows "over";
3. **Startup banner addressed to the launching agent** ("TO THE AGENT WHO LAUNCHED THIS") forbidding foreground waits and giving the exact monitor command;
4. **`watch.py <run-id>`** replacing inline tail loops (an inline loop carries the run-id in its command string → un-allowlistable → prompts every run);
5. **PostToolUse hook** that re-injects the banner into the launching agent's context when the launch command matches and `run_in_background == true` (the real banner goes to a stdout file nobody reads).
Per-agent progress counting = grep the agent's short in commit subjects, never a global `HEAD` delta (wrong under parallel commits).
→ `reference/consolidation-pipeline/watch.py`, `hooks/orchestrate_launch_banner.sh`, `docs/philosophy/orchestrateur.md`, hook wiring in `reference/harness/settings.json`

### 2.3 Three-layer watchdog + semantic audit
A time cap doesn't catch a rabbit-hole: an off-task agent produces output continuously. Layers: (1) sliding inactivity on JSONL mtime → kill; (2) **semantic audit** — a cheap model reads a *digest* of the agent's own event log and returns a verdict, continue-by-default on any error; (3) absolute cap as final net. Post-kill orphan recovery = admin force-release indexed on the real owner field.
→ `reference/consolidation-pipeline/docs/specs/watchdog.md`; reference impl `reference/extraction-pipeline/orchestrate.py`

### 2.4 Prompts as files, single source of truth
An instruction addressed to agents is written once, in a dedicated `.md`; the orchestrator `cat`s `common.md` + the role file. Dividing line: **prompt file = what you tell an agent; spec = what the system enforces.** Specs reference prompt files by path, never copy them. (Origin: a 130-line Python string literal drifting from the `.md` it told agents to read.)
→ `reference/consolidation-pipeline/prompts/`, `docs/philosophy/prompts.md`

### 2.5 Headless-worker preamble
Liftable boilerplate for any `claude -p` worker: one task then exit, never a second claim, no "while I'm here"; explicit `run_in_background: false` on every Bash (headless agents aren't woken); never `wait`/`sleep`-loops (refused silently outside allowlist); git only through the CLI verbs; read your session short from the claim output, not from `echo $VAR`.
→ `reference/consolidation-pipeline/prompts/common.md`

### 2.6 Small-context doctrine
Quality degrades well before the window limit (~100k loaded = unstable; ~60k working ideal). Consequences: disposable sessions (1 task/session), orchestrator manages volume — "not your endurance"; claim output carries the whole start context; per-claim **quotas** ("do your batch, release and exit even if the cell isn't done").
→ `reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `prompts/common.md`, quotas: `reference/extraction-pipeline/RESSOURCES_PROTOCOL.md`

---

## 3. Harness & permissions

### 3.1 `tools/` symlink facade for prompt-free allowlisting
Claude Code's Bash allowlist matches the literal command string and `*` doesn't cross `/`. Keep scripts in the layer they serve; expose **flat file symlinks** in `tools/`; one allowlist entry `Bash(tools/*.py *)` covers everything. Invariants: never a directory symlink (re-prompts), every new executable gets symlink + doc row. Deny-list only the git shapes that break concurrency (`git -C`, `git add .`/`-A`, `commit -a`), not git wholesale.
→ `reference/harness/permissions-playbook.md`, `reference/harness/settings.json`

### 3.2 Shared-worktree git concurrency rules
Several sessions, one working tree, no isolated worktrees: never stage globally; commit path-scoped (`git commit -m msg -- <paths>` uses a temp index, ignores others' staging); never touch files another agent modified; scripts commit their own transitions so locks are visible in history. Commit convention (compact layer-scope prefix) doubles as a greppable machine contract.
→ `reference/harness/permissions-playbook.md`, `reference/harness/rules/commit-messages.md`

### 3.3 Test discipline for orchestration code
Black-box CLI tests: real subprocesses against a `git init`'d tmpdir, deterministic session id, no mocks, fail-loud on missing deps. Concurrency tests = two real parallel claimers on the same row. Two hard rules: **the verdict is the summary line alone** (progress dots ≠ success; no summary = hang), and **every spawned subprocess has an immanent time bound** (bounded loop, never `while True`) so a failed external kill can't orphan a process.
→ `reference/tests/README.md`, `test_concurrency.py`

---

## 4. KB conventions (agent-maintained corpora)

### 4.1 Discovery index via frontmatter (`quand_piocher`)
Every note carries a frontmatter sentence — "load this note when…" — modeled on a skill's `description:`. A tiny script prints `<note> <sentence>` as the corpus's one-screen index; field presence is **linter-enforced** so the index can't rot; agent definitions make it the mandatory entry point (raw grep = complement, never entry). Kills the "grep the whole KB into context" blowup.
→ `reference/consolidation-pipeline/piocher.py`, `check.py`

### 4.2 Work-plan sweep via anchored frontmatter (`plan_de_travail`)
Work plans stay distributed (each in the layer it concerns) but discoverable by one grep: any file that *is* a plan carries frontmatter `plan_de_travail: "<what must empty>"`. `^`-anchored grep keeps out prose that merely discusses plans. Pair with visible step checkboxes + a current-step marker so a zero-context session resumes without reading the whole file.

### 4.3 Three natures of a location
Resolve before writing anywhere: **work plan** (empties — a remaining item = work not done), **archive** (never empties), **inventory** (a view mirroring an archive — *reconciled*, never emptied or frozen; a discrepancy = work on the archive, never an edit to the view).

### 4.4 No pink elephant — discarded things disappear, record included
Never keep a record-of-discarding in a living doc ("X removed because…", struck entries, out-of-scope notes re-describing X): it re-summons the closed topic — the next agent re-reads, re-debates, re-introduces. The thing disappears; the *why* lives in the commit message. Sole legitimate guard: against things that **come back from upstream** (an agent reloading source material will re-propose it → leave a barrier "covered in §N"). No upstream pressure → no guard → it goes.

### 4.5 Specs / philosophy split with a reading contract
Two doc trees: `specs/` (each rule once, no justification — read when *applying*) and `philosophy/` (tradeoffs, measured reality, named residual risks — read when *changing* the spec). Spec sections point at their justifying philosophy page; spec README carries "frozen decisions — don't re-litigate without going through philosophy". Fixes both failure modes: agents bloating on rationale, and agents changing rules they don't understand.
→ `reference/consolidation-pipeline/docs/specs/README.md`, `docs/philosophy/README.md`

### 4.6 Cheap detection, cognitive cutting
Detect oversize on cheap metadata (line counts, image counts — zero content read); when an agent must decide *where* to cut, feed it a generated **outline** (headings + line counts), not the document. Freeze the cut by immutable id so idempotent re-inventory never re-cuts.
→ `reference/consolidation-pipeline/docs/philosophy/scoping.md`

### 4.7 Generated regions inside human files
`inventory.py` repopulates a board between `<!-- INVENTORY:BEGIN/END -->` markers — machine-owned region, human-readable file, reconciled idempotently (merge by id).
→ `reference/extraction-pipeline/inventory.py`, `reference/consolidation-pipeline/inventory.py`

---

## 5. Agent & skill authoring

### 5.1 "Never escalate from ignorance" agent template
Before flagging a gap to the human: (1) read the relevant note *in full* including its open-questions section — if your problem is listed, it's known; (2) if you doubt the synthesized layer, descend to raw sources and settle it yourself (with a source-precedence rule); (3) escalate only what survives. Plus: declared preload set per role (the role→notes mapping lives in exactly one file) and tool scoping (read-only researcher by construction).
→ `reference/harness/agents/`

### 5.2 Skills as codified mistakes
A skill = the recovery procedure for an error already made; each opens with "the error this corrects". Domain-free exemplars: **store vs view** (a fact has one home; indexes/checklists are derived views, not duplicates — a template repeating a fact is a structural smell, not N edits) and **snapshot, don't watch** (draining a human's inbox file: one snapshot, empty immediately, work the frozen batch, ignore mid-run arrivals — mentioning them is the watcher impulse in disguise). Also: fact-change propagation ("you transcribe, you don't rewrite"; upstream is read, downstream is written) and open-question resolution (dig raw sources first — many open questions are false ones).
→ `reference/harness/skills/`

### 5.3 Human-attention protocol
The human's cognitive load is the project's scarce resource; **the methodology absorbs it, not the agent** (hand-compensation restarts at zero each session — load must live in the system, versioned). Mechanics: two decision natures (substance → human decides in detail, verbatim in front of them; means → one sentence problem + stake + recommendation); state lives in files, never in heads; any accidental load = a system defect → fix the system (rework > addition); **never a bare locator** (content leads, locator follows in parentheses — including when relaying subagents); decisions on text require the **quoted verbatim**, never a paraphrase; concise ≠ compressed (a message the human must decode is a failure); dialogue over multiple-choice.

---

## Reference map

| Path | Origin | What it is |
|---|---|---|
| `reference/consolidation-pipeline/` | `2-consolide/outils/` | CSV-registry pipeline: CLI + lint + orchestrator + watch + prompts + specs/philosophy docs |
| `reference/extraction-pipeline/` | `1-sources/outils/ressources/` | Multi-step board pipeline: per-cell claim/release, quotas, watchdog reference impl, protocol doc |
| `reference/report-task.py` | `1-sources/outils/` | Minimal claim/finish/release instance (markdown board) |
| `reference/harness/` | `.claude/`, `common/outils/` | settings.json, permissions playbook, commit rules, agent defs, skills, whoami |
| `reference/tests/` | `common/outils/tests/` | Test discipline README + concurrency exemplar |

Left behind on purpose: domain content (sources, notes, deliverables), extraction handlers (format-specific), domain state files (`tasks.csv`, boards).
