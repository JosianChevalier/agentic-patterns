# 2-consolide/outils/docs/specs/ — spec prescriptive du pipeline de consolidation (couche 2)

Spec **normative** du pipeline map-reduce qui alimente `2-consolide/`. Tourne **100 % agents + scripts déterministes, sans intervention humaine** (Josian n'intervient qu'en couche 3).

> Statut : pipeline **pas encore construit**. On outille pendant que l'extraction `1-sources/outils/ressources/` tourne. Aucune consolidation à produire tant que le walking skeleton n'est pas vert.

## Contrat de lecture

- **Tu APPLIQUES la spec** (tu construis un script, tu codes un agent, tu exécutes une tâche) → lis **uniquement ce dossier**. Chaque règle y est énoncée une seule fois, sans justification longue.
- **Tu CHANGES la spec** (tu remets en cause une décision, tu ajoutes un mécanisme, tu arbitres un tradeoff) → lis **`2-consolide/outils/docs/philosophy/` d'abord** : le *pourquoi*, les tradeoffs, les risques résiduels et la réalité mesurée y vivent. Ne touche pas une règle d'ici sans avoir lu la page philosophie pointée en regard.

## Le modèle en une phrase

**Les scripts possèdent l'état, les agents possèdent la cognition.** Un agent n'édite jamais l'état à la main : il appelle le CLI, fait son travail cognitif, écrit **son** artefact (ou rend un verdict de validation), le CLI vérifie + commit. → *pourquoi* : `philosophy/map-reduce.md`.

## Composants

| Fichier | Couvre |
|---|---|
| [modele-donnees.md](modele-donnees.md) | `tasks.csv` : schéma, colonnes, états, cycle de vie d'un reduce |
| [cli.md](cli.md) | `task.py` : verbes, gating, flock, commits, plafond par session |
| [check.md](check.md) | `check.py` : linter de sourçage déterministe (ce qu'il vérifie) |
| [validate.md](validate.md) | gate de fidélité reduce-only : 2/2, garde distinct-agent, rôle des validateurs |
| [scoping.md](scoping.md) | découpe des grosses sources : seuil, outline, 4 règles de coupe, `split` |
| [formats.md](formats.md) | format du fragment + du fichier consolidé |
| [inventory.md](inventory.md) | `inventory.py` : peuplement idempotent du CSV |
| [orchestrateur.md](orchestrateur.md) | `orchestrate.py` : boucle de spawn (peek read-only ; **l'agent** claime via `claim_next`), routage validation, bandeau de monitoring + contrat `Monitor` |
| [watchdog.md](watchdog.md) | watchdog 3 couches (sliding/audit/cap) + auditabilité a posteriori + force-release admin post-kill ; porté de `1-sources/outils/ressources/orchestrate.py` |

## Architecture cible

```
couche 1 (sources)                  couche 1.5 (fragments)             couche 2 (consolidé)
1-sources/1.2-nettoyes/reports/REPORT_*.md         ──map──▶  2-consolide/2.1-fragments/<src>.md  ──reduce──▶ 2-consolide/2.2-content/<theme>.md
1-sources/1.2-nettoyes/ressources/<slug>/          (1 fichier / source,                      (1 fichier / thème,
  (slugs en Validate 2/2 only)         sections par clé-thème)                   format 2-consolide/README)

                            coordination : 2-consolide/outils/tasks.csv (CLI task.py) — trace : git log
```

- **MAP** : 1 tâche = 1 source. L'agent lit une seule source, écrit `2-consolide/2.1-fragments/<src>.md` (faits distillés + citations, par thème touché). Il possède son fichier → zéro concurrence en écriture.
- **REDUCE** : 1 tâche = 1 thème. L'agent fait `grep -l "## theme:<clé>" 2-consolide/2.1-fragments/*.md`, lit **seulement** ces sections, écrit `2-consolide/2.2-content/<theme>.md`. Contexte = fragments distillés, jamais les sources brutes.
- **Liant** : `2-consolide/THEMES.md` = vocabulaire de clés contrôlé (~30 clés, H2 + quelques H3 du sommaire du seed CATS — ex-synthèse de 1re passe, supprimée). Sans clés stables, le `grep` du reduce ne matche pas.

## Décisions figées (ne pas re-débattre sans passer par philosophy/)

1. Architecture **map-reduce** + couche **1.5 (fragments)** intermédiaire. → `philosophy/map-reduce.md`
2. État = registre tabulaire **`2-consolide/outils/tasks.csv`** (lignes mutées sur place, `flock`, 1 commit/transition). Pas de tables markdown-DB, pas de ledger append-only. Trace = `git log -- 2-consolide/outils/tasks.csv`. → `modele-donnees.md`
3. **CLI unique `2-consolide/outils/task.py <verbe>`** (dispatcher), une seule entrée d'allowlist. → `cli.md`
4. Deux gates distincts : MAP = `check.py` déterministe seul ; REDUCE = `check.py` **puis** gate de fidélité **2/2** agent-based. → `check.md`, `validate.md`, `philosophy/gate-fidelite.md`
5. **Décomposition (`split`)** = levier de petit contexte (pas un cas rare) : seuil cheap par `inventory`, outline déterministe, coupe par un agent de scoping. → `scoping.md`, `philosophy/scoping.md`
6. Granularité des thèmes = **H2 + quelques H3 (~30 clés)** dérivée du seed CATS (ex-synthèse de 1re passe). → `inventory.md`
7. **Prompts des sous-agents externalisés** dans des fichiers dédiés (`2-consolide/outils/prompts/` : 1 `common.md` + 1 fichier/rôle), source unique cat'ée par l'orchestrateur et référencée par la spec — jamais de prompt inline qui re-décrit le protocole. → `philosophy/prompts.md`

## Invocation des scripts

Les scripts (`task.py`, `inventory.py`, `check.py`) s'appellent en **chemin relatif direct** depuis la racine du repo (`2-consolide/outils/task.py peek_next`), pas via `python3` ni en chemin absolu — sinon prompt de permission. Allowlist + règle de commit concurrence-safe documentées dans [`common/outils/CLAUDE.md`](../../../harness/permissions-playbook.md) § `2-consolide/`.

## Orchestration

L'orchestrateur (boucle qui spawn les agents + route validation) est **requis**, avec bandeau de monitoring. Spec opérationnelle : [orchestrateur.md](orchestrateur.md) ; *pourquoi* + pattern : `philosophy/orchestrateur.md`.

## Prompts des sous-agents — fichiers dédiés (source unique)

Au build de l'orchestrateur, le prompt de chaque rôle d'agent (map, reduce, validate, scope) **ne s'écrit pas inline dans le script**. Chaque prompt vit dans son fichier sous `2-consolide/outils/prompts/` :

- `common.md` — règles répétées à tout agent (plafond 1 tâche/session, pas de 2ᵉ claim, git via CLI seulement, allowlist headless, posture face au doute).
- un fichier par rôle (`map.md`, `reduce.md`, `validate.md`, `scope.md`) — la cognition propre au rôle.

**Règle anti-duplication** : un fragment de consigne destiné aux agents est écrit une seule fois, dans son fichier-prompt. L'orchestrateur `cat` `common.md` + le fichier du rôle pour fabriquer le prompt de `claude -p`. Les `.md` de spec référencent ces fichiers (« cognition : `prompts/validate.md` ») au lieu de re-décrire. La spec ne garde que ce que le script enforce (gating, transitions CSV, commits). → *pourquoi* : `philosophy/prompts.md`.
