# CLAUDE.md — agentic-patterns

## Ce que c'est

- Bibliothèque de **patterns réutilisables** pour (a) harness agentiques de code et (b) knowledge bases maintenues par agents.
- Extraits d'un projet clos : `/Users/josian/Projects/formation-cats`. Le domaine de ce projet (CATS, formation) est **hors sujet ici** — seul le méta compte. Ne jamais le remonter à Josian.
- Josian y a laissé beaucoup de temps et d'énergie ; ce repo est ce qu'on en capitalise.

## Structure

- `patterns/<slug>/index.md` — le catalogue : 5 familles (pipeline core, orchestration, harness/permissions, KB conventions, agent/skill authoring). Un dossier par pattern ; frontmatter = description concise + tags.
- `INDEX.md` — **point d'entrée** : vue générée par `piocher.py` (catalogue par famille), requêtable par tags.
- `patterns/TAGS.md` — vocabulaire de tags contrôlé (tag → définition) + règle d'extensibilité.
- `reference/` — copies **verbatim** de la machinerie d'origine (scripts Python, specs, philosophy, prompts, hooks, skills, agents, tests). En français, avec des mentions du domaine d'origine : c'est assumé, la généricisation est itérative. Provenance : `reference/README.md`.
- `sequential-flow-runner/` — **premier cas d'usage aval** : note de design (README) composant les patterns du catalogue pour transformer des flows de code agent-orchestrés (TDD, refactor atomique) en orchestrateur Python pilotant des workers `claude -p` ; avec copies verbatim des flows source (autre projet que l'origine du reste du repo).

## Règles de travail

- Tout ajout/retrait de pattern dans le catalogue = **arbitrage Josian** (liste de candidats avec verdict proposé, il tranche).
- Un pattern doit être **autoportant** : problème → mécanisme → insight, lisible sans ouvrir `reference/`. Les chemins `reference/` suivent en pointeurs.
- `reference/` est une **archive** : on n'y édite rien (fidélité à l'origine) ; un pattern généricisé vit dans son dossier `patterns/<slug>/`.
- `INDEX.md` est une **vue générée** : jamais éditée à la main — regénérer via `piocher.py --write`.
- Hook pre-commit versionné (`hooks/pre-commit`) — install par clone : `git config core.hooksPath hooks`. Lint le catalogue et vérifie que la vue correspond au **contenu du commit** (index git, commits path-scopés compris — le WIP non commité d'autres sessions n'entre jamais dans la vue). Dérive → il régénère `INDEX.md` dans le working tree et échoue : `git add INDEX.md` puis recommitter.

## État / en cours

- Les 3 audits (complétude, autoportance, or dans le code) et la validation pattern par pattern (autoportance, frontmatter, références, fond) sont passés : catalogue stable, prêt à consommer.
