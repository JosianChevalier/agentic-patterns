# Template — validation multi-agents de fichiers importants

Approche pour faire produire **et** valider en parallèle un ensemble de livrables critiques par plusieurs agents (sessions Claude Code, scripts, humains), sans collisions, avec un critère de convergence explicite.

Pensé pour : rapports d'atelier, rapports d'analyse, documents normatifs, dossiers de spec — tout livrable où la fidélité à des sources compte et où un seul agent ne suffit pas comme garant.

**Instances vivantes** dans ce repo (utiles comme références concrètes) :
- `1-sources/outils/report-task.py` — instance simple (un seul tableau, une étape rédaction + validation). Proche du template à la lettre.
- `1-sources/outils/ressources/{claim.py,release.py}` — instance enrichie (pipeline multi-étapes, gardes par session via grep des commits, résultats typés, auto-abandon orphelin). À regarder quand tu te demandes « est-ce que mon cas relève du template ou d'une réécriture ? ». Voir « Variantes connues » plus bas.

## Le problème

- Une liste de N fichiers à produire et à fiabiliser.
- Plusieurs agents disponibles, qu'on veut faire travailler en parallèle.
- Pas de garantie qu'un agent unique produise un fichier correct du premier coup → il faut **plusieurs relectures par des agents distincts**.
- Pas de dispatcher central qui pousse les tâches : chaque agent demande la suivante au script (`task.py next`), qui **choisit sous flock**. La sélection se fait à l'intérieur du verrou → deux agents ne peuvent jamais recevoir la même ligne, et l'agent n'a pas à raisonner sur la priorité (donc pas de course de sélection, pas de claim qui échoue parce qu'un autre est passé avant).

## Vue d'ensemble

Un **tableau markdown** (`TODO.md`) sert de tableau d'état partagé. Une ligne par fichier. Toutes les transitions passent par un **script Python** (`task.py`) qui sérialise les accès via `flock` et commit lui-même chaque transition pour la rendre visible aux autres agents.

**Flux par défaut : le script choisit la tâche.** L'agent appelle `task.py next` ; le script, sous flock, picke la première ligne prenable *par cet agent* (validation proche de la sortie d'abord, sinon rédaction), pose le verrou, commit, et imprime `TASK: <rédaction|validation> <slug>`. L'agent fait *ce* travail-là — il ne choisit pas, donc il ne peut pas entrer en collision avec un autre. `claim <slug>` reste disponible comme échappatoire manuelle ciblée.

Machine à états par ligne :

```
todo ──claim──▶ en cours ──finish──▶ fait (0/N) ──┐
                                                  │
        ┌───────────── claim ─────────────────────┘
        ▼
   en validation ──finish ok──────▶ fait (k+1/N)
                  ──finish corrigé─▶ fait (0/N)      ← reset
                  ──finish signalé─▶ bloqué          ← gel jusqu'à arbitrage

                  jusqu'à fait (N/N ✓)
```

Sous-commandes :

```bash
task.py next                    # ★ mode normal : le script choisit + réserve la tâche,
                                #   imprime `TASK: <rédaction|validation> <slug>`
task.py claim <slug>            # échappatoire : réserve une ligne précise (sans garde ≠rédacteur)
task.py finish <slug>           # fin de rédaction → fait, validation = 0/N
task.py finish <slug> <verdict> # fin de validation : ok | corrigé | signalé
task.py release <slug>          # abandon : libère sans transition
```

`next` sort en erreur (code ≠ 0) si aucune ligne n'est prenable par cet agent — l'agent interprète ça comme « rien pour moi » et sort.

## Format du tableau

Colonnes minimales :

| Colonne | Rôle |
|---|---|
| **État** | `todo` / `en cours` / `fait` / `bloqué` (signalé, gel jusqu'à arbitrage) |
| **Item** | Métadonnées du livrable (nom, sources, etc. — libre) |
| **Fichier** | Chemin du livrable (sert de clé via le slug) |
| **Verrou** | Booléen `🔒` (occupé) / `—` (libre) |
| **Validation** | Compteur `X/N` ; `N/N ✓` quand convergé |

Le **slug** est extrait du nom de fichier (ex. `OUTPUT_<slug>.md`). Voir `TODO.md` pour un exemple complet.

## Sémantique des verdicts

| Verdict | Effet sur le compteur | Quand |
|---|---|---|
| `ok` | +1 | Le valideur a relu, rien à corriger. |
| `corrigé` | reset à `0/N` | Le valideur a **modifié le fichier** sur un point de fond. Repart à zéro car le contenu n'est plus celui qu'avaient relu les passes précédentes. |
| `signalé` | gèle la ligne | Le valideur **ne peut pas avancer** : blocage/ambiguïté qu'il ne tranche pas lui-même. La ligne passe à **`bloqué`** et sort du compteur **jusqu'à arbitrage** (humain/escalade). Rien à voir avec une section *Points flous*. Capturer une raison libre = variante (cf. `release.py`, ligne ci-dessous). |

**Convergence** : `N` passes `ok` **consécutives** par **N agents distincts**. `corrigé` réinitialise le compteur ; `signalé` **gèle** la ligne (sortie du flux jusqu'à arbitrage).

`N=2` est un bon défaut. Augmenter si les enjeux sont critiques, baisser si le contenu est court ou peu risqué.

## Contraintes inter-agents — appliquées par `next`

Trois règles, **vérifiées par le script** (plus par consigne) au moment où `next` choisit :

1. **Le valideur doit être ≠ rédacteur** du fichier. Sinon biais auto-validation. `next` saute toute ligne que cet agent a rédigée (grep `Finish rédaction <slug> (<short>)`).
2. **Pas deux passes du même agent** sur la même ligne. Le `N/N` doit venir de N agents distincts. `next` saute toute ligne que cet agent a déjà validée (grep `Finish validation <slug> … (<short>)`).
3. **Validation d'abord, rédaction ensuite** : `next` prend la ligne de validation la plus proche de la sortie (compteur le plus haut) avant celles qui repartent de zéro, puis les `todo`.

L'identité d'agent est le `<short>` (8 chars de `$CLAUDE_CODE_SESSION_ID`, ou `manual` hors session Claude Code) estampillé dans chaque commit — c'est ce que `next` grepe. **Corollaire** : il faut au moins `threshold + 1` agents distincts pour qu'une ligne converge (le rédacteur + N valideurs différents). Avec moins, une ligne peut rester bloquée — c'est voulu, pas un bug.

> L'échappatoire `claim <slug>` **ne vérifie pas** ces gardes (claim ciblé, supposé piloté par un humain). En automatique, n'utilise que `next`.

## Concurrence

- **`fcntl.flock` sur un lockfile** (`$TMPDIR/<projet>/task.lock`, sous-dossier projet créé à la demande) sérialise les opérations CLI sur une même machine.
- **Commit git après chaque transition** pour rendre le verrou et l'état visibles aux autres agents (qui voient `git status` / `git log`). Sans commit, deux agents qui éditent en parallèle se marchent dessus.
- **Une seule machine** : ce template ne gère pas la concurrence distribuée (plusieurs machines, plusieurs clones). Pour ça il faudrait un état partagé via remote (issue tracker, Redis, etc.).
- Si un `🔒` reste orphelin (agent crashé), édition manuelle du tableau pour remettre `—`.

## Format des commits

Chaque transition produit un commit avec un sujet stable, **estampillé du `<short>` de l'agent** en fin de sujet. Le format est **partie intégrante du contrat** : `next` grepe l'historique pour ses gardes ≠rédacteur / ≠valideur, et l'orchestrateur compagnon l'utilise pour attribuer chaque commit à un agent et détecter les claims orphelins après crash.

| Transition | Sujet du commit |
|---|---|
| Claim sur `todo` | `Claim rédaction <slug> (<short>)` |
| Claim sur `fait <k/N>` | `Claim validation <slug> (<short>)` |
| Finish rédaction | `Finish rédaction <slug> (<short>)` |
| Finish validation | `Finish validation <slug> <verdict> (<short>)` |
| Release (abandon) | `Release <rédaction\|validation> <slug> (<short>)` |

`<short>` = 8 premiers chars de `$CLAUDE_CODE_SESSION_ID` (ou `manual` hors session Claude Code). Ce stamp est **core** — il rend le template directement branchable sur [`../subagent-orchestrator/`](../subagent-orchestrator/README.md) sans modification.

## Dupliquer pas à pas

La voie recommandée : **copier** le dossier, **ajuster** les constantes, **écrire ton propre `TODO.md`**. Pas de réutilisation du `task.py` du template via flags depuis plusieurs domaines — chaque cas a son propre copie.

1. **Copier** `common/outils/templates/file-validation/` vers la couche servie, ex. `<couche>/outils/<ton-domaine>/`.
2. **Ajuster les `DEFAULT_*` en tête de `task.py`** :

   ```python
   DEFAULT_TODO_REL    = "<ton-domaine>/TODO.md"
   DEFAULT_LOCK_FILE   = Path(os.environ.get("TMPDIR", "/tmp")) / "<ton-projet>" / "task.lock"
   DEFAULT_THRESHOLD   = 2                        # N passes consécutives requises
   DEFAULT_FILENAME_RE = r"OUTPUT_(?P<slug>[^.]+)\.md"
   DEFAULT_COL_ETAT       = 0
   DEFAULT_COL_FICHIER    = 5
   DEFAULT_COL_VERROU     = 6
   DEFAULT_COL_VALIDATION = 7
   ```
3. **Renommer/déplacer le `TODO.md`** au chemin choisi et adapter les colonnes (les indices doivent correspondre).
4. **Écrire à côté un `PROTOCOL.md` de domaine** : critères qualité, seuil `corrigé`, zones rouges (cf. « Hors scope » ci-dessous).
5. **Mettre à jour `.claude/settings.json`** pour autoriser le nouveau script sans prompt (pattern `Bash(<couche>/outils/<ton-domaine>/*.py *)`) et `common/outils/CLAUDE.md` pour le déclarer.

Le passage de flags CLI (`--todo-rel`, `--filename-re`…) existe pour les **tests** et le debug ponctuel ; n'en fais pas un mode d'usage permanent par-dessus le template original.

## Variantes connues / quand sortir du template

Le template couvre le cas **basique** : une liste de fichiers, une rédaction, une validation à `N/N`. Il existe des cas où ce périmètre ne suffit plus. Dans ces cas, **réécris ton propre `task.py`** (en t'inspirant de l'instance vivante `1-sources/outils/ressources/{claim.py,release.py}`) plutôt que de patcher le template — sinon le template grossit jusqu'à ne plus être lisible.

| Variante | Symptôme | Référence vivante |
|---|---|---|
| **Pipeline multi-étapes** (ex. `extract → triage → embed → transcribe → validate`) avec prérequis par étape et résultats spécifiques (`done <sha>`, `skip` qui court-circuite des étapes en aval…). | Tu veux plus que `rédaction → validation`. Le tableau a plusieurs colonnes d'étape, pas une seule. Le `next` du domaine encode l'ordre de priorité de *ses* étapes. | `1-sources/outils/ressources/claim.py` (table `STEP_COL`, `PREREQ`, gardes `composer_shorts` / `prior_validator_shorts`) |
| **Résultats typés par étape** (allow-list regex). | Tu veux que `signalé <reason>` capture une raison libre, ou interdire des transitions illégales (`signalé` sans message). | `1-sources/outils/ressources/release.py` (`RESULT_RE`) |
| **Auto-abandon de verrous orphelins** par un orchestrateur. | Tu veux qu'un superviseur (pas le détenteur du lock) puisse libérer une ligne après crash d'agent. | `1-sources/outils/ressources/release.py` (`--force-abandon-orphan`) |
| **Embed/staging d'artéfacts produits** dans le même commit que la transition. | Le `release` doit aussi stager `<domaine>/produit/<slug>/` (PNG embeddés, sous-fichiers…). | `1-sources/outils/ressources/release.py` (`slug_dir` + `git add`) |

Le **stamp `(<short>)` et les gardes par session** (≠rédacteur / ≠valideur via grep des commits) sont désormais **dans le template de base** — c'est ce qui rend `next` sûr en auto-pick et le rend directement branchable sur l'orchestrateur compagnon ([`common/outils/templates/subagent-orchestrator/`](../subagent-orchestrator/README.md)). Les variantes ci-dessus enrichissent encore le format (typiquement `<Step> <slug>: <result> (<short>)` pour un pipeline multi-étapes) ; quand tu les adoptes, garde le `next` qui choisit côté script — c'est l'invariant à ne pas perdre.

Règle du pouce : **si tu te retrouves à ajouter une 4ème option CLI au template ou un 2ème `if/elif` dans une fonction du `task.py` du template, tu es en train de l'étendre — duplique et adapte plutôt.**

## Hors scope de ce template

**Les critères qualité** appliqués pendant la validation sont **spécifiques au domaine** et n'ont pas leur place ici. Pour chaque cas d'usage, écrire à côté du `TODO.md` un guide qui définit :

- Ce qu'il faut vérifier à chaque passe (exhaustivité vs sources, exactitude factuelle, conformité à un format…).
- Le **seuil de correction** — quand `corrigé` vs quand laisser `ok` malgré une retouche mineure. Ce seuil est crucial : trop bas et le compteur ne sort jamais. Le formuler explicitement et lister les cas typiques tolérés.
- Les **zones rouges** spécifiques — patterns qui ont déjà laissé passer des erreurs (polarité, ratios, attributions, etc.). À enrichir au fil du temps.

Sans ces critères, le compteur tourne dans le vide. Avec des critères trop laxistes, on valide n'importe quoi ; trop stricts, on ne converge jamais.

## Limites connues

- Tableau markdown comme source de vérité : OK jusqu'à ~50 lignes. Au-delà, envisager une vraie base.
- `flock` local uniquement, pas de coordination distribuée.
- Identité d'agent = `<short>` du `$CLAUDE_CODE_SESSION_ID`, lue à chaque appel et estampillée dans les commits. Hors session Claude Code, elle vaut `manual` (tous les appels manuels partagent alors la même identité — les gardes ≠rédacteur/≠valideur de `next` ne les distinguent pas).
- Le verdict `corrigé` est binaire — si un valideur fait 3 corrections triviales + 1 grosse, c'est `corrigé`. Le seuil de correction du domaine doit gérer ça.
