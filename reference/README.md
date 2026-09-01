# Reference map

Verbatim archive of the original project files — never edited; the patterns in `patterns/` point into it.

| Path | Origin | What it is |
|---|---|---|
| `reference/consolidation-pipeline/` | `2-consolide/outils/` | CSV-registry pipeline: CLI + lint + orchestrator + watch + prompts + specs/philosophy docs |
| `reference/consolidation-pipeline/kb-layer-protocol.md` | `2-consolide/CLAUDE.md` | KB layer protocol: canonical note format, `quand_piocher` index, role→notes consumer mapping (renamed — a `CLAUDE.md` here would auto-load) |
| `reference/consolidation-pipeline/arbitrages-protocol.md` | `1-sources/1.3-arbitrages/CLAUDE.md` | Mini-ADR protocol: format, triage rule, candidat→settled promotion, outgoing-questions queue (renamed, idem) |
| `reference/extraction-pipeline/` | `1-sources/outils/ressources/` | Multi-step board pipeline: per-cell claim/release, quotas, watchdog reference impl, append-only gate, protocol doc |
| `reference/report-task.py` | `1-sources/outils/` | Minimal claim/finish/release instance (markdown board) |
| `reference/relabel_llm.py` | `1-sources/outils/` | LLM-sandwich instance: deterministic dump (idx-numbered items) + deterministic apply (headers only, by idx) around an LLM judgment (imports its deterministic companion, left behind) |
| `reference/harness/` | `.claude/`, `common/outils/` | settings.json, permissions playbook, commit rules, agent defs, skills, whoami |
| `reference/harness/CLAUDE.racine.md` | `CLAUDE.md` (repo root) | Root project instructions: `human-attention-protocol`, `no-pink-elephant`, `three-natures`, `work-plan-sweep`, layer map (renamed — a `CLAUDE.md` here would auto-load) |
| `reference/deliverable-layer/` | `4-contenu/` | Deliverable-layer protocol (renamed — a `CLAUDE.md` here would auto-load): zero-meta rule, verbatim review loop, `NN#MM` locators; + `slides.py` (idempotent annotate + resolver) |
| `reference/presentation-layer/presentation-layer-protocol.md` | `5-presentation/CLAUDE.md` | Rendering-layer protocol (renamed — a `CLAUDE.md` here would auto-load): one source / two renderers, layout congruence, markdown grammar as 4↔5 contract, non-blocking degraded build |
| `reference/templates/` | `common/outils/templates/` | Liftable generic templates: `file-validation/` (claim + N/N-validation CLI + example board) and `subagent-orchestrator/` (`claude -p` pool, 3-layer watchdog, heartbeat), with `# ADAPT:` zones and duplication guides |
| `reference/work-index/` | `0-pilotage/travaux-en-cours/` | Permanent index of open work streams (rows empty, file stays) + folder protocol; domain rows kept as format illustration |

Left behind on purpose: domain content (sources, notes, deliverables), extraction handlers (format-specific), domain state files (`tasks.csv`, boards).
