# Agentic patterns — index

Patterns extracted from a real multi-agent project: a knowledge base built and validated entirely by disposable Claude Code sessions, orchestrated by scripts, feeding a human-arbitrated deliverable. Domain content stripped; machinery kept.

Two families: **harness** (running agents on code/tasks) and **KB** (agent-maintained knowledge). Each entry: the problem, the mechanism, where the reference lives. `reference/` holds verbatim copies of the original files (French; genericization is iterative — the reasoning is the asset).

---

## 1. Pipeline core (state & lifecycle)

### 1.1 Scripts own state, agents own cognition
The foundational rule. Deterministic guarantees (who holds what, atomic transitions, serialization, commit formats) belong to a CLI under `flock`; judgment (distilling, cutting, validating meaning) belongs to agents. An agent never hand-edits state: it calls a verb (`claim_next`, `done`, `release`…), does its cognitive work, writes *its* artifact; the CLI verifies and commits. Single mutation authority: one script, one lock. Contract of the critical section: read/write state **and commit** before releasing the lock — the transition is visible to others the moment the lock drops, and commit order = real transition order (git log becomes trustworthy as a journal, which 2.8 builds on).
→ `reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `docs/specs/modele-donnees.md`

### 1.2 Tabular registry, not a ledger
Task state = one CSV row per task, mutated in place. Bounded by construction (doesn't grow with activity); history is free via `git log -- tasks.csv` since every transition is a commit. Read/write only through the `csv` module. `note` column carries structured tokens (`author:`, `ok:`, `fix:`, `correcting:<short>`).
→ `reference/consolidation-pipeline/_store.py`, `task.py`, `docs/specs/modele-donnees.md`

### 1.3 The script picks the task, not the agent
`claim_next` selects the next eligible task under the lock and prints exactly the start context the agent needs (`input:`, `note:`, `session:`). Structurally eliminates selection races and failed claims, and keeps the agent from ever loading the full registry. Second selection pattern, for boards with per-cell claims and no `claim_next` verb: the prompt orders "list ALL takeable cells, **draw one at random**, max 3 attempts then exit" — N agents all aiming at the first free cell would collide systematically; randomness is the cheapest anti-collision.
→ `reference/consolidation-pipeline/task.py`; simple markdown-board instance: `reference/report-task.py`; liftable generic template (`# ADAPT:` zones, step-by-step duplication guide, known variants): `reference/templates/file-validation/`

### 1.4 Validation by N/N convergence of distinct agents
An artifact converges when N *consecutive* passes by N *distinct* agents say `ok`. Guards enforced by script, not by instruction: validator ≠ author, no two passes by the same agent, validation only after production. Agent identity = 8-char session short, stamped in every commit subject in a fixed format — the format is a machine contract (scripts grep history to enforce guards and attribute work).
→ `reference/consolidation-pipeline/task.py`, `docs/specs/validate.md`; generic template (state machine, verdicts `ok`/`corrected`/`flagged`, script-enforced guards): `reference/templates/file-validation/`, black-box suite `reference/tests/test_template_file_validation.py`

### 1.5 Correction lease — fix in place, never nuclear reject
A rejected artifact isn't thrown back to `todo`. A validator edits it in place (`corrige`); all sibling validation passes reset to 0/N (the content is no longer what they read). The edit spans multiple CLI calls, outside the lock → concurrent correctors serialized by a **durable lease** in the row's note (`correcting:<short>`). Orphaned corrector: clear lease + `git checkout` the artifact back.
→ `reference/consolidation-pipeline/docs/specs/modele-donnees.md` (§ lease), `task.py`

### 1.6 Map-reduce with an intermediate distillation layer
Map reads exactly one source, emits a distilled fragment; reduce greps fragments by key and never touches raw sources. The fragment layer is the buffer that absorbs volume. Reduce rebuilds from scratch (no incremental patching).
→ `reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `prompts/map.md`, `prompts/reduce.md`

### 1.7 Two gates of different natures: sourcing (deterministic) vs fidelity (cognitive)
Anti-hallucination split. **Sourceability** — every claim ends with a citation token that must resolve — is a lint (`check.py`), wired into `done`. **Fidelity** — does the claim say what the source says — is an agent reading the span, resolving citations **back to ground truth** (not the intermediate fragment): one end-of-chain check covers distortion at both hops. Default posture: refute if in doubt.
→ `reference/consolidation-pipeline/check.py`, `docs/philosophy/gate-fidelite.md`

### 1.7bis Append-only gate — pristine snapshot + insertion state machine
Same family as 1.7 (deterministic gate), for enrichment chains: downstream steps annotating an extracted artifact must only **add**, never touch the source text. At extraction, write a hidden pristine snapshot (`.extract.md`) beside the living file; the gate diffs snapshot vs current via `SequenceMatcher` opcodes — any `delete`/`replace` fails outright, and each `insert` block runs through a small state machine that accepts only the declared insertion shapes (blank lines, single embed lines, open/close-tagged free-form blocks; an unclosed tag is a violation). Agents get full freedom *inside* the allowed shapes, structurally zero ability to erode the source. Missing snapshot → dedicated error carrying the bootstrap command.
→ `reference/extraction-pipeline/check_text_preservation.py`, black-box suite `reference/tests/test_check_text_preservation.py`

### 1.8 Purge the output at claim — code guard against anchoring
When an agent claims a rebuild (reduce), the script `unlink()`s the previous version of the output file before handing over. This mechanically forces a fresh `Write`: an `Edit` would require a `Read`, anchoring the agent on the old text instead of re-deriving from the fragments. The purge happens under the lock but is **not committed** (crash → HEAD intact); `reopen` doesn't purge (the corpus stays greppable while the task waits). Purest instance of "a code guard against an agent's cognitive bias".
→ `reference/consolidation-pipeline/task.py`

### 1.9 Manual facts flow through the same machinery
Hand-arbitrated facts live as mini-ADRs (one fact per file, monotonic id = immutable citation key, body *is* the fact) and are **projected** into the pipeline as a synthetic fragment — so human input and extracted input converge through identical validation. Includes the `candidat` (human judged) vs `settled` (authority confirmed) distinction and an outgoing-questions queue that empties when the *outside world* answers.
→ `reference/consolidation-pipeline/project_arbitrages.py`, `arbitrages-protocol.md` (the mini-ADR protocol: format, triage rule, candidat→settled promotion, outgoing-questions queue)

### 1.10 Progress recomputed from the artifact, never declared
The agent releases with a bare `ok`; the script recounts K by parsing the real file and N from disk. Guards: `K > N` → refuse; `K <` previous K (work was deleted) → refuse to commit; `skip` is a computed value, forbidden as input. Lying about one's progress is structurally impossible. The commit message carries the *computed* value — the log is reparsed by other regexes downstream, so it must tell the truth.
→ `reference/extraction-pipeline/release.py`

---

## 2. Orchestration

### 2.1 Slots vs budget — two orthogonal caps
`--slots` = concurrency width (CPU, commit serialization, rate limits); `--max-agents` = cumulative budget (guard against a queue that never empties). On each freed slot, **re-peek state** rather than planning the queue once — state moved. Pin `--model` on every `claude -p` (otherwise cost inherits the launcher's UI default). Stall detection = state-fingerprint diff at harvest (N consecutive no-change harvests → drain), not per-stream counters (false-positive on legitimately repeating gates). Spawn each worker with the parent env **minus `CLAUDE_CODE_SESSION_ID`**: inherited, every worker gets the orchestrator's session short → one apparent identity everywhere → the validator ≠ author guard silently dies. Corollary: the orchestrator learns a worker's short only by parsing the first lines of the worker's own stream-json (`system/init` event, `session_id` field, truncated to 8) — sole identity source for a dead agent, indexing force-release and per-agent commit counts; best-effort (unparseable → skip, logged, audit deferred). Refuse to start at all if `ANTHROPIC_API_KEY` is set: dozens of `claude -p` would silently switch from the subscription to billed API.
→ `reference/consolidation-pipeline/orchestrate.py`, `docs/specs/orchestrateur.md`, `docs/philosophy/orchestrateur.md`; generic template plugging onto `templates/file-validation/`: `reference/templates/subagent-orchestrator/`

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
A time cap doesn't catch a rabbit-hole: an off-task agent produces output continuously. Layers: (1) sliding inactivity on JSONL mtime → kill; (2) **semantic audit** — a cheap model reads a *digest* of the agent's own event log and returns a verdict, continue-by-default on any error; (3) absolute cap as final net. Post-kill orphan recovery = admin force-release indexed on the real owner field. Load-bearing implementation details:
- **One stream, four uses** — worker stdout as `--output-format stream-json --verbose`, redirected to a parent-opened *file* (never PIPE — buffer deadlock): its mtime feeds the sliding watchdog, its content feeds the audit digest, its first lines yield the session id, and the file is the post-mortem forensics.
- **Deterministic verdict pre-computed** — the orchestrator computes quota overrun itself and injects `PLAFOND: … → overrun|ok` into the audit prompt with "kill verdict, nothing to recount": code decides the quantifiable, the cheap model judges only the qualitative. Quota baseline = the unreleased board cell — claim/release hands the starting point for free, zero orchestrator state.
- **Audit disarmed, non-blocking, last-VERDICT-wins** — the audit subprocess gets no tools (everything inline in its prompt → it can't stall reading a 5 MB log), one audit in flight with its own deadline (a hung audit is killed, verdict = continue); parse the *last* `VERDICT:` line (the model deliberates before concluding); every error branch converges to continue. Anti-over-kill clause in the prompt: log tail shows the agent self-corrected → continue.
- **Digest bounded by construction** — constant-cost global counters (event total, `tool_use` by name, errors) + tail of the last 50 events, each field truncated, base64 blobs → `<image>`, unreadable log → dedicated string, never an exception. Digest size is invariant of log content — otherwise the audit would time out precisely on long-running agents, the ones it watches.
- **Kill the whole process group** — workers and audits spawned `start_new_session=True`; kill = `os.killpg(os.getpgid(pid), SIGKILL)` with idempotent `proc.kill()` fallback, then `wait()` to reap. A `claude -p` forks pipeline scripts/git that hold locks: killing only the claude process leaks children that block everyone behind a lock nobody will release.
→ `reference/consolidation-pipeline/docs/specs/watchdog.md`; reference impl `reference/extraction-pipeline/orchestrate.py`; genericized (6 `# ADAPT:` zones, whole-process-group SIGKILL, orphan-claim auto-abandon): `reference/templates/subagent-orchestrator/`

### 2.4 Prompts as files, single source of truth
An instruction addressed to agents is written once, in a dedicated `.md`; the orchestrator `cat`s `common.md` + the role file. Dividing line: **prompt file = what you tell an agent; spec = what the system enforces.** Specs reference prompt files by path, never copy them. (Origin: a 130-line Python string literal drifting from the `.md` it told agents to read.)
→ `reference/consolidation-pipeline/prompts/`, `docs/philosophy/prompts.md`

### 2.5 Headless-worker preamble
Liftable boilerplate for any `claude -p` worker: one task then exit, never a second claim, no "while I'm here"; explicit `run_in_background: false` on every Bash (headless agents aren't woken); never `wait`/`sleep`-loops (refused silently outside allowlist); git only through the CLI verbs; read your session short from the claim output, not from `echo $VAR`. Two headless traps documented **in the prompt itself**: (a) an out-of-allowlist Bash in `-p` mode is refused without a prompt AND **cancels the sibling tool calls of the same turn** — the agent silently proceeds on partial data (hence `Bash(echo *)` allowlisted solely so reading one's session id never triggers it); (b) a tool result can surface one turn late → the prompt announces it and mandates a single `git log -1` confirmation, never a retry loop.
→ `reference/consolidation-pipeline/prompts/common.md`

### 2.6 Small-context doctrine
Quality degrades well before the window limit (~100k loaded = unstable; ~60k working ideal). Consequences: disposable sessions (1 task/session), orchestrator manages volume — "not your endurance"; claim output carries the whole start context; per-claim **quotas** ("do your batch, release and exit even if the cell isn't done").
→ `reference/consolidation-pipeline/docs/philosophy/map-reduce.md`, `prompts/common.md`, quotas: `reference/extraction-pipeline/RESSOURCES_PROTOCOL.md`

### 2.7 Heartbeat env var — long silent subprocesses under a sliding watchdog
The sliding watchdog reads liveness from the agent's JSONL log mtime — but a domain script doing one long burst (heavy binary extraction, media conversion) behind the Bash tool has its stdout buffered until completion: the log freezes and the watchdog kills a healthy agent mid-task. Contract: the orchestrator exports `ORCHESTRATE_HEARTBEAT=<per-agent tmp path>` into the subagent's env and its inactivity check watches log mtime **or** heartbeat mtime; the domain script touches that path every ~30s (well under the inactivity window) from a daemon thread started just before the long work. Hard rules on the script side: no-op when the var is absent (stays usable standalone/in tests), touch wrapped in try/except so a heartbeat bug never fails the real task, thread dies with the process.
→ `reference/templates/subagent-orchestrator/README.md` (copyable Python + shell snippets), `orchestrate.py`

### 2.8 `git log` as the lease database
Orphan recovery with zero persisted orchestrator state: diff the commit subjects — any `Claim <step> <slug> (<short>)` without a paired release commit → force-abandon (admin mode bypasses the ownership guard but **stays under flock**, idempotent no-op). History *is* the lease registry: nothing to persist, nothing to drift.
→ `reference/extraction-pipeline/orchestrate.py`, `release.py`

---

## 3. Harness & permissions

### 3.1 `tools/` symlink facade for prompt-free allowlisting
Claude Code's Bash allowlist matches the literal command string and `*` doesn't cross `/`. Keep scripts in the layer they serve; expose **flat file symlinks** in `tools/`; one allowlist entry `Bash(tools/*.py *)` covers everything. Invariants: never a directory symlink (re-prompts), every new executable gets symlink + doc row. Deny-list only the git shapes that break concurrency (`git -C`, `git add .`/`-A`, `commit -a`), not git wholesale. Corollary pattern: `CLAUDE_CODE_SESSION_ID` sits in the Bash env but `echo $VAR` isn't cleanly allowlistable → package the read as a 3-line `tools/whoami.py` (fail-loud) that falls under the single entry; one derivation of the session short, three uses (commits, leases, run-id).
→ `reference/harness/permissions-playbook.md`, `reference/harness/settings.json`

### 3.2 Shared-worktree git concurrency rules
Several sessions, one working tree, no isolated worktrees: never stage globally; commit path-scoped (`git commit -m msg -- <paths>` uses a temp index, ignores others' staging); never touch files another agent modified; scripts commit their own transitions so locks are visible in history. Commit convention (compact layer-scope prefix) doubles as a greppable machine contract. Plumbing for scripts that commit: retry **only** when stderr contains `index.lock` (short backoff — collision with out-of-flock commits from another pipeline in the same repo; any other error propagates, never delete the lock yourself); no-op-safe scoped commit = `git add -- <paths>` (untracked files need it), `git diff --cached --quiet -- <paths>` as predicate, then `commit -- <paths>` — caller commits without pre-checking; guard any pathspec on a possibly-empty dir with `git ls-files` first (else "pathspec did not match").
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
→ `reference/work-index/CLAUDE.md` (frontmatter convention + checkbox/current-step rule), live frontmatter instance: `reference/work-index/INDEX.md`; convention as stated to every session: `reference/harness/CLAUDE.racine.md` (§3)

### 4.3 Three natures of a location
Resolve before writing anywhere: **work plan** (empties — a remaining item = work not done), **archive** (never empties), **inventory** (a view mirroring an archive — *reconciled*, never emptied or frozen; a discrepancy = work on the archive, never an edit to the view).
→ worked instance: `reference/work-index/CLAUDE.md` (opens by distinguishing the work-in-progress folder from its two sibling folders — frozen archive, accumulating meeting log — then states its own nature: "this empties"); canonical statement: `reference/harness/CLAUDE.racine.md` (§3)

### 4.4 No pink elephant — discarded things disappear, record included
Never keep a record-of-discarding in a living doc ("X removed because…", struck entries, out-of-scope notes re-describing X): it re-summons the closed topic — the next agent re-reads, re-debates, re-introduces. The thing disappears; the *why* lives in the commit message. Sole legitimate guard: against things that **come back from upstream** (an agent reloading source material will re-propose it → leave a barrier "covered in §N"). No upstream pressure → no guard → it goes.
→ canonical statement: `reference/harness/CLAUDE.racine.md` (§3, « Pas d'éléphant rose »)

### 4.4bis Permanent work-stream index whose rows self-empty
One permanent entry point answers "what's running right now?": an index file that is **never deleted** — its *rows* empty. A finished stream's working file disappears and its row is removed (the why lives in the commit message, per 4.4); when nothing runs, the table is empty but the file remains, so the entry point never moves. Table columns force actionability: what it is, state, **next action**, **who decides**. Standing instruction to agents: serve the human *the next action, ready to decide* — never a global status report; if serving it requires the human to carry anything else, the index is missing something → propose the fix, don't hand-compensate (5.3). Stream files follow 4.2 (work-plan frontmatter, step checkboxes); the folder's nature is settled per 4.3.
→ `reference/work-index/CLAUDE.md` (folder protocol), `reference/work-index/INDEX.md` (live index — domain rows kept verbatim, they illustrate the format)

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
→ `reference/harness/agents/`; the one-file role→notes mapping lives in `reference/consolidation-pipeline/kb-layer-protocol.md` (§ consommateur)

### 5.2 Skills as codified mistakes
A skill = the recovery procedure for an error already made; each opens with "the error this corrects". Domain-free exemplars: **store vs view** (a fact has one home; indexes/checklists are derived views, not duplicates — a template repeating a fact is a structural smell, not N edits) and **snapshot, don't watch** (draining a human's inbox file: one snapshot, empty immediately, work the frozen batch, ignore mid-run arrivals — mentioning them is the watcher impulse in disguise). Also: fact-change propagation ("you transcribe, you don't rewrite"; upstream is read, downstream is written) and open-question resolution (dig raw sources first — many open questions are false ones).
→ `reference/harness/skills/`

### 5.3 Human-attention protocol
The human's cognitive load is the project's scarce resource; **the methodology absorbs it, not the agent** (hand-compensation restarts at zero each session — load must live in the system, versioned). Mechanics: two decision natures (substance → human decides in detail, verbatim in front of them; means → one sentence problem + stake + recommendation); state lives in files, never in heads; any accidental load = a system defect → fix the system (rework > addition); **never a bare locator** (content leads, locator follows in parentheses — including when relaying subagents); decisions on text require the **quoted verbatim**, never a paraphrase; concise ≠ compressed (a message the human must decode is a failure); dialogue over multiple-choice.
**Glossing boundary**: contextualize only what the human *offloaded* (org-internal names, repo conventions, agent-written file contents — never cite a file as if they know what's in it: say what it contains); never gloss standard industry vocabulary — the test is "is this a thing they delegated?".
**Pending human actions get a durable home**: while the topic is active, the item lives in the current working doc; once disengaged it must move to a permanent home (global scope → the work index; layer-scoped → that layer's protocol doc — never an audit archive), or it dies with the task.
→ `reference/harness/CLAUDE.racine.md` (§0 « Communication avec Josian » — the full protocol as stated to every session)

---

## Reference map

| Path | Origin | What it is |
|---|---|---|
| `reference/consolidation-pipeline/` | `2-consolide/outils/` | CSV-registry pipeline: CLI + lint + orchestrator + watch + prompts + specs/philosophy docs |
| `reference/consolidation-pipeline/kb-layer-protocol.md` | `2-consolide/CLAUDE.md` | KB layer protocol: canonical note format, `quand_piocher` index, role→notes consumer mapping (renamed — a `CLAUDE.md` here would auto-load) |
| `reference/consolidation-pipeline/arbitrages-protocol.md` | `1-sources/1.3-arbitrages/CLAUDE.md` | Mini-ADR protocol: format, triage rule, candidat→settled promotion, outgoing-questions queue (renamed, idem) |
| `reference/extraction-pipeline/` | `1-sources/outils/ressources/` | Multi-step board pipeline: per-cell claim/release, quotas, watchdog reference impl, protocol doc |
| `reference/report-task.py` | `1-sources/outils/` | Minimal claim/finish/release instance (markdown board) |
| `reference/harness/` | `.claude/`, `common/outils/` | settings.json, permissions playbook, commit rules, agent defs, skills, whoami |
| `reference/harness/CLAUDE.racine.md` | `CLAUDE.md` (repo root) | Root project instructions: human-attention protocol (5.3), pink elephant (4.4), three natures (4.3), work-plan sweep (4.2), layer map (renamed — a `CLAUDE.md` here would auto-load) |
| `reference/templates/` | `common/outils/templates/` | Liftable generic templates: `file-validation/` (claim + N/N-validation CLI + example board) and `subagent-orchestrator/` (`claude -p` pool, 3-layer watchdog, heartbeat), with `# ADAPT:` zones and duplication guides |
| `reference/tests/` | `common/outils/tests/` | Test discipline README + concurrency exemplar + template black-box suite |
| `reference/work-index/` | `0-pilotage/travaux-en-cours/` | Permanent index of open work streams (rows empty, file stays) + folder protocol; domain rows kept as format illustration |

Left behind on purpose: domain content (sources, notes, deliverables), extraction handlers (format-specific), domain state files (`tasks.csv`, boards).
