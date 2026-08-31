# CLAUDE.md — agentic-patterns

## Ce que c'est

- Bibliothèque de **patterns réutilisables** pour (a) harness agentiques de code et (b) knowledge bases maintenues par agents.
- Extraits d'un projet clos : `/Users/josian/Projects/formation-cats`. Le domaine de ce projet (CATS, formation) est **hors sujet ici** — seul le méta compte. Ne jamais le remonter à Josian.
- Josian y a laissé beaucoup de temps et d'énergie ; ce repo est ce qu'on en capitalise.

## Structure

- `INDEX.md` — le catalogue : 24 patterns, 5 familles (pipeline core, orchestration, harness/permissions, KB conventions, agent/skill authoring). **Point d'entrée unique** : toute session commence par le lire.
- `reference/` — copies **verbatim** de la machinerie d'origine (scripts Python, specs, philosophy, prompts, hooks, skills, agents, tests). En français, avec des mentions du domaine d'origine : c'est assumé, la généricisation est itérative.
- Provenance détaillée : table « Reference map » en fin d'`INDEX.md`.
- `sequential-flow-runner/` — **premier cas d'usage aval** : note de design (README) composant les patterns de l'INDEX pour transformer des flows de code agent-orchestrés (TDD, refactor atomique) en orchestrateur Python pilotant des workers `claude -p` ; avec copies verbatim des flows source (autre projet que l'origine du reste du repo).

## Règles de travail

- **La forme finale du repo n'est pas encore cadrée.** Josian doit expliquer ce qu'il vise (usage, format cible). D'ici là : pas de restructuration, pas de généricisation massive, pas de traduction — on **collecte et on audite**.
- Tout ajout/retrait de pattern dans `INDEX.md` = **arbitrage Josian** (liste de candidats avec verdict proposé, il tranche).
- Une entrée d'INDEX doit être **autoportante** : problème → mécanisme → insight, lisible sans ouvrir `reference/`. Les chemins `reference/` suivent en pointeurs.
- `reference/` est une **archive** : on n'y édite pas les copies (fidélité à l'origine) ; un pattern généricisé vivra ailleurs, quand la forme cible sera tranchée.

## État / en cours

- 3 audits (sessions dédiées, handovers émis) : **complétude** (qu'a-t-on oublié dans formation-cats ?), **autoportance** (le repo se comprend-il sans formation-cats ?), **or dans le code** (tricks d'implémentation non catalogués).
- Puis session de **cadrage** : Josian pose l'objectif, on décide la forme finale.
