# Tags — controlled vocabulary

Controlled tag vocabulary for the `patterns/*/index.md` frontmatter; `piocher.py --tags` reads this table. Tags name **problems/capabilities** ("I want to do X"), not implementation details.

| Tag | Definition (one line) |
|---|---|
| `concurrency` | Multiple agents/processes acting on shared state (files, registry, repo) without races or collisions. |
| `state-management` | Where task/pipeline state lives, how it mutates, and who holds the single mutation authority. |
| `task-lifecycle` | Claim/release/progress transitions: selecting, handing over, correcting, and closing units of work. |
| `git` | Using git itself as infrastructure — journal, lease database, recovery baseline, concurrency rules, commit contracts. |
| `anti-hallucination` | Keeping agent claims faithful and traceable to ground truth; making lying about work structurally impossible. |
| `validation` | Converging artifacts through scripted review passes and gates (N/N convergence, correction, verdicts). |
| `cognitive-bias` | Code/protocol guards against known agent biases (anchoring on old output, watcher impulse, re-summoning closed topics). |
| `orchestration` | Launching, capping, and supervising pools of headless workers (`claude -p`). |
| `watchdog` | Detecting and killing stuck, silent, or off-task agents without killing healthy ones. |
| `background-monitoring` | Keeping visibility on long-running background scripts from an agent session (logs, markers, progress counts). |
| `context-budget` | Keeping agent context small: minimal start context, distilled inputs, preload sets, quotas, disposable sessions. |
| `headless` | `claude -p` specific traps and boilerplate (allowlist refusals, late tool results, no wake-ups, env inheritance). |
| `prompts` | Authoring and organizing instruction files addressed to agents (prompt files, preambles, skills). |
| `permissions` | Allowlist/deny-list ergonomics and tool scoping: invoking tools without permission prompts, denying dangerous shapes. |
| `testing` | Test discipline for concurrent/orchestration code (black-box CLI tests, real subprocesses, time bounds). |
| `crash-recovery` | Surviving kills, crashes, orphaned leases, and partial writes; restoring a coherent state afterwards. |
| `discovery` | Finding the right note/plan/pattern fast from a one-screen entry point instead of grepping everything into context. |
| `doc-hygiene` | Keeping agent-maintained docs from rotting, duplicating facts, or re-summoning discarded topics. |
| `work-tracking` | Plans and indexes that represent open work and empty as it completes (vs archives and inventories). |
| `human-protocol` | Protecting the human's attention: how decisions, escalations, and pending actions reach them. |
| `idempotency` | Safe re-runs and reconciliation: rebuild or re-scan without destroying state, progress, or human edits. |
| `agent-identity` | Deriving and stamping a per-agent identity (session short) for attribution, guards, and progress counting. |
| `derived-views` | Machine-generated views/regions inside or beside human-readable files — derived, never a second home for a fact. |

**Extensibilité** : un tag ne s'ajoute que si (a) aucun tag existant ne colle même en élargissant légèrement sa définition, et (b) sa définition d'une ligne est ajoutée à cette table dans le même commit. Un tag qui ne servirait qu'un seul pattern est suspect — ne l'ajouter que si le pattern est réellement isolé (précédent accepté : `testing`, porté par le seul pattern de discipline de test).
