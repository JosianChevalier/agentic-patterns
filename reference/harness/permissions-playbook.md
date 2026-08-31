# Tools

Scripts d'orchestration et d'automatisation. Un sous-dossier par domaine.

## Invocation (agents Claude Code)

Les `.py` sous `tools/` ont tous un shebang `#!/usr/bin/env python3` et le bit exec — **appeler directement en chemin relatif depuis la racine du repo** (le cwd de l'agent), pas via `python3`, et **pas en chemin absolu** :

```bash
1-sources/outils/ressources/claim.py compose <slug>                                  # OK, autorisé sans prompt
python3 1-sources/outils/ressources/claim.py compose <slug>                          # KO, déclenche un prompt
/Users/.../formation-cats/1-sources/outils/ressources/claim.py compose <slug>        # KO, déclenche un prompt
```

Permissions définies dans `.claude/settings.json` (commité) : `Bash(tools/*.py *)`, `Bash(1-sources/outils/ressources/*.py *)`, `Bash(2-consolide/outils/*.py *)`, `Bash(common/outils/templates/file-validation/*.py *)`, plus `Bash(caffeinate -i 2-consolide/outils/*.py *)` (orchestrateur lancé sous `caffeinate`, cf. ci-dessous). Ces patterns matchent la **forme littérale** de la commande — un chemin absolu, même équivalent, n'est pas couvert, et le `*` du glob **ne traverse pas** `/` (d'où une entrée par sous-dossier).

**`tools/` = façade à plat, et c'est sa raison d'être.** Les scripts vivent dans la couche qu'ils servent ; `tools/` en expose des **symlinks de fichier, à plat**, pour que `Bash(tools/*.py *)` les couvre **sans prompt**. Invariant :
- Un script appelé par un agent → il lui faut un **symlink plat** `tools/<script>.py`. Sans lui, `tools/<sous-dossier>/<script>.py` **existe mais reprompte** (le glob ne traverse pas `/`) — piège vécu avec `piocher.py`.
- **Pas de symlink de dossier** dans `tools/` : il ne sert aucune permission et fabrique ce piège.
- Nouveau script exécutable → poser le symlink plat **et** le documenter ici.

**Inventaire de la façade** (`tools/<script>.py`, tous sans prompt) :

| Script | Rôle | Vit dans |
|---|---|---|
| `piocher.py [filtre]` | Index de découverte des fiches couche 2 (`quand_piocher`) — **point d'entrée** avant tout travail couche 3+ | `2-consolide/outils/` |
| `build.py <slug>` / `build-all.py` | Rendu reveal → HTML + PDF (une section / le deck complet) | `5-presentation/5.1-reveal/` |
| `slides.py annotate` / `slides.py <locator…>` | Renumérote les locators `NN#MM` des slides ; résout un locator en titre | `4-contenu/outils/` |
| `visuels.py` | Vue générée des visuels à produire, groupée par routage web (read-only) | `4-contenu/outils/` |
| `report-task.py` | Orchestration multi-agents des rapports couche 1 (claim/finish/release) | `1-sources/outils/` |
| `relabel_speakers.py` / `relabel_llm.py` | Ré-attribution des locuteurs dans les transcripts | `1-sources/outils/` |
| `whoami.py` | Short id d'agent (8 chars de `$CLAUDE_CODE_SESSION_ID`) | `common/outils/` |

Les scripts de la pipeline de consolidation (`task.py`, `inventory.py`, `check.py`, `orchestrate.py`, `watch.py`, `project_arbitrages.py`) s'appellent par leur **chemin de couche** `2-consolide/outils/<script>.py` — couvert par sa propre entrée d'allowlist, pas besoin de façade.

## Tests (pytest)

pytest n'est **ni dans le `PATH`, ni dans le python système** — il vit dans le **venv unique à la racine du repo** (`.venv/`), qui porte toutes les deps (consolide + ressources). **Ne pas créer ni utiliser de venv par sous-dossier** (ex. `2-consolide/outils/.venv`) : doublon résiduel de migration, à supprimer s'il réapparaît. Toujours invoquer pytest par le chemin explicite du venv racine (pas `pytest` nu, pas `python3 -m pytest`) :

```bash
.venv/bin/pytest 2-consolide/outils/tests/        # OK
pytest 2-consolide/outils/tests/                  # KO, "not found" (venv non activé)
```

Autorisé sans prompt via `.claude/settings.json` : une entrée `Bash(.venv/bin/pytest <arbo>/*)` par arbo d'outils (`tools/`, `1-sources/outils/`, `2-consolide/outils/`, `common/outils/`), et **uniquement** le binaire pytest du venv (pas `python … .py`, pas `pytest` nu). Tout autre binaire, ou un chemin hors de ces arbos, reprompt.

**Verdict = la ligne de résumé seule** (`===== N passed/failed/error in X s =====`). Jamais conclure d'un `%` de progression ni des points verts : un run figé sur un test affiche un `%` sans jamais produire de résumé. Pas de ligne de résumé = run non terminé (hang), pas un succès.

**Sous-process spawné par un test = borne d'arrêt immanente obligatoire.** Tout subprocess injecté (snippet `sys.executable -c …`) doit mourir seul en temps borné : `for _ in range(N)` ou `time.sleep(T)` borné, **jamais `while True`**. Le kill externe (cap, sliding…) reste ce qu'on teste ; la borne est le filet si ce kill échoue ou si pytest est interrompu — sinon l'orphelin survit reparenté à launchd (cas vécu : PID resté 2 jours). La borne doit être nettement > au timeout attendu pour ne pas changer la sémantique.

## `2-consolide/` — pipeline de consolidation (couche 2)

Pipeline map-reduce qui alimente `2-consolide/2.2-content/<theme>.md` à partir des rapports + ressources extraites. État dans `2-consolide/outils/tasks.csv`, spec normative dans `2-consolide/outils/docs/specs/`.

| Script | Rôle |
|---|---|
| `task.py <verbe>` | Dispatcher unique de l'état (`claim_next` / `peek_next` / `claim` / `done` / `split` / `release` / `claim_next --type validate` / `approve` / `reject`). Tout sous `flock`, un seul claim par session. **`claim_next` claime — réservé aux agents spawnés par l'orchestrateur ; pour inspecter l'état avant/pendant un run, utiliser `peek_next` (read-only)**. Verbes + gating : `2-consolide/outils/docs/specs/cli.md`. |
| `inventory.py` | Peuple `outils/tasks.csv` idempotent (merge par `id`) : lignes `reduce` (1/clé `THEMES.md`) + `map` (rapports + slugs ressources), détection de seuil oversize. `2-consolide/outils/docs/specs/inventory.md`. |
| `check.py` | Linter de sourçage déterministe (fragment + consolidé), exit≠0 sur violation. Câblé par `task.py done`. `2-consolide/outils/docs/specs/check.md`. |
| `orchestrate.py` | Boucle autonome (« lance un orchestrateur ») : peek read-only de `outils/tasks.csv` → spawn d'agents jetables `claude -p` du bon rôle → drain. **Slotté** : `--slots N` (concurrence, défaut 3) / `--max-agents N` (budget total, défaut 10), `--cap` (cap-temps/agent), `--dry-run` (no-op, montre bandeau+slotting sans forker). Ne mute jamais le CSV, aucun git mutant. **Lancer sous `caffeinate -i`** (boucle longue → veille laptop tuerait le run) ; cf. `2-consolide/outils/docs/specs/orchestrateur.md` § Lancement. |
| `watch.py [run-id]` | Suit le log d'un run au fil de l'eau pour l'outil `Monitor` : streame les nouvelles lignes de `2-consolide/outils/.orchestrator/<run-id>/orchestrator.log` (une ligne = un event) et sort sur le marqueur terminal « flags : ». Sans argument, auto-détecte le run le plus récent. La commande imprimée par le bandeau d'`orchestrate.py`. |

Invocation directe en chemin relatif (cf. ci-dessus) — `2-consolide/outils/task.py peek_next`, **pas** `python3 …`. Allowlist : `Bash(2-consolide/outils/*.py *)`.

**Commit concurrence-safe** : ces scripts committent eux-mêmes en scopant aux paths (`git commit -- <paths>`), jamais `git add .`. Plusieurs sessions jetables tournent sur le même dossier sans worktree isolé → ne stage **jamais** par-dessus avant un run de `task.py`, et ne touche pas les fichiers claimés par d'autres agents (cf. `CLAUDE.md` § Concurrence).

## `templates/` — patterns réutilisables

| Template | Rôle |
|---|---|
| `file-validation/` | Approche multi-agents pour produire **et** valider en parallèle un ensemble de livrables critiques (cf. `report-task.py`, qui en est une instance). Voir le `README.md` du dossier. |

## `ressources/` — extraction des binaires CATS vers `1-sources/1.2-nettoyes/ressources/`

Voir `1-sources/outils/ressources/RESSOURCES_TODO.md` (tableau de tâches) et `1-sources/outils/ressources/RESSOURCES_PROTOCOL.md` (workflow agent).

| Script | Rôle |
|---|---|
| `claim.py <step> <slug>` | Réserve atomiquement une tâche (`extract` / `compose` / `validate`) sur une ligne du tableau. Pose le verrou (`$CLAUDE_CODE_SESSION_ID`), vérifie les prérequis (étape précédente faite, agent ≠ composeur pour validate), commit. Échoue proprement si la cellule est prise. |
| `release.py <step> <slug> <result>` | Libère le verrou, inscrit le résultat dans la cellule (`ok` / `corrigé` / `signalé` / `done <sha>` / `abandon`), commit. |
| `inventory.py` | Walk `1-sources/1.1-raw/postfiles/`, calcule sha256, détecte doublons, peuple le tableau (`<!-- INVENTORY:BEGIN/END -->`) et la section doublons (`<!-- DUPLICATES:BEGIN/END -->`) de `RESSOURCES_TODO.md`. Lancé une fois en setup. |
| `extract.py <slug>` | Extraction déterministe d'un fichier source (pptx/docx/pdf/image) vers `1-sources/1.2-nettoyes/ressources/<slug>/`. Idempotent via sha256 dans le frontmatter. |
| `handlers/` | Un handler par type : `pptx.py`, `docx.py`, `pdf.py`, `image.py`. |

### Usage type (agent)

```bash
# Récupère ton short id (8 chars de $CLAUDE_CODE_SESSION_ID)
common/outils/whoami.py

# Picke une tâche, fais, release
1-sources/outils/ressources/claim.py compose cvp_process1_generer_les_idees
# ... travail ...
1-sources/outils/ressources/release.py compose cvp_process1_generer_les_idees ok
```

`common/outils/whoami.py` est whitelisté (`Bash(tools/*.py *)`) — aucun prompt. **Ne fais pas** `echo $CLAUDE_CODE_SESSION_ID` : `echo` n'est pas dans l'allowlist et déclenche une validation manuelle. Les scripts `claim.py` / `release.py` lisent l'env var directement, donc `whoami.py` n'est utile que pour les gardes "≠ composeur" / "≠ premier validateur" où l'agent doit comparer.

Cf. `RESSOURCES_PROTOCOL.md` pour l'ordre de priorité (Validate > Compose > Extract) et les critères par étape.

### Sémaphore

`claim.py` et `release.py` utilisent `fcntl.flock` sur `.ressources.lock` (gitignored) pour la sérialisation locale, et committent immédiatement pour rendre le verrou visible des autres agents. Ce fonctionnement suppose **une seule machine** (pas de concurrence distribuée).
