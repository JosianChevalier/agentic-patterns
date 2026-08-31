# CLI `2-consolide/outils/task.py <verbe>`

Dispatcher unique (mirror simplifié de `ressources`). Tout sous `flock` sur `.consolide.lock`. Commit scopé au(x) fichier(s) du livrable (concurrence-safe : `git commit -- <paths>`, pas `git add .`).

## Verbes

> **`claim_next` CLAIME — réservé aux agents spawnés par l'orchestrateur.** Pour
> inspecter l'état avant/pendant un run (réflexe « qu'est-ce qui vient »), utiliser
> **`peek_next`** (lecture seule, ci-dessous), **jamais** `claim_next` : ce dernier
> claime et orpheline silencieusement la tâche de tête.

| Verbe | Effet |
|---|---|
| `claim_next [--type map\|reduce\|validate]` | **flux normal — CLAIME** (agents orchestrés). Sélectionne **et** claim une seule tâche prenable **dans le même flock** (ordre déterministe : type puis `id` ; gating ci-dessous), mute (`status=claimed`, `owner`, `claimed_at`), commit `Claim <id> (<short>)`, imprime `TASK: <type> <id>` **suivi du contexte de démarrage** (§ Sortie ci-dessous). **reduce** : le claim **purge l'output** `2-consolide/2.2-content/<clé>.md` (`unlink`, `missing_ok`, working-tree seul, non committé) → l'agent repart d'un `Write` neuf des fragments, jamais d'`Edit` qui l'ancrerait sur l'ancienne version ; `reopen` ne purge **pas** (KB grepable jusqu'au re-claim). Rien de prenable → sort en erreur. L'agent traite cette tâche puis sort ; l'orchestrateur relance un agent pour la suivante. `--type validate` : sélectionne un **enfant** `validate:<clé>#n` en `to_validate` prenable (gating ci-dessous), **sans muter `status`** (reste `to_validate`) — enregistre seulement le validateur courant comme `owner`, commit `Take-validate <id> (<short>)`, imprime `TASK: validate <id>` + contexte. |
| `peek_next [--type map\|reduce\|validate]` | **LECTURE SEULE** — même sélection/gating que `claim_next` (filtre `is_takeable` ; `validate` → miroir de la garde distinct-agent ; ordre déterministe `(type, id)` ; 1er candidat), mais **aucune mutation, aucun commit, pas de flock**. Imprime le candidat (`TASK: <type> <id>`) ou `rien à prendre`. Verbe d'inspection « qu'est-ce qui vient » avant/pendant un run — n'orpheline rien. |
| `claim <id>` | **échappatoire manuelle ciblée** (préférer `claim_next`) : même gating + transition que `claim_next`, sur un `id` précis. |
| `done <id> [--output <path>]` | lance `check.py` sur l'artefact ; échec → refuse (tâche reste `claimed`). OK : **map** → `status=done`, `done_at`, commit `Done <id> (<short>)`. **reduce** → **ne devient pas terminal** : `status=split`, `owner` lâché, et **append un enfant `validate:<clé>#n` par bucket** de `cite_buckets` (chacun `to_validate`, `note=author:<short>`, `input=<output>#sources=slugA,slugB`). **0 bucket → refuse** (reste `claimed`). Commit unique `[<output>, tasks.csv]` `To-validate <id> → N shard(s) (<short>)`. Dans les deux cas l'artefact untracked est stagé avec le CSV. |
| `approve <id>` | **issue de validation `ok`** (enfant `validate:<clé>#n` en `to_validate`). Garde distinct-agent **per-shard** (sur la `note` de l'enfant) : appelant ≠ `author:` ≠ tout `fix:` ≠ tout `ok:` déjà présent. Append `ok:<short>`. **2e `ok:` distinct → enfant `status=done`, `done_at`**, bookkeeping nettoyé. **Rollup (même flock)** : si **tous** les frères `validate` du parent sont `done`, le reduce parent `split → done` (`done_at`). Commit `Validate <id>: 2/2 (<short>)`. Sinon (1er) : `owner` libéré, commit `Validate <id>: 1/2 (<short>)`. |
| `claim-correct <id>` | **pré-requis du `corrigé`** : pose la **lease** `correcting:<short>` sur la `note` du reduce parent `split` (sérialise les correcteurs concurrents d'un consolidé partagé) → **refus** si un autre correcteur la tient. Sous flock CSV ; l'édition cognitive du consolidé qui suit reste **hors flock**, sérialisée par cette lease durable. Commit `Claim-correct <id> (<short>)`. |
| `corrige <id> [--reason …]` | **issue de validation `corrigé`** (remplace `reject`). Pré-requis hors CLI : `claim-correct` a posé la lease, l'agent a **édité `2-consolide/<clé>.md`** (corrigé le fait, **ou** inscrit le flou ouvert en section `## Points flous` si l'ambiguïté n'est pas tranchable). Sous flock CSV unique : exige la lease (`correcting:<short>` sur le parent, sinon `die`) ; **re-lance `check.py`** sur le consolidé → **refus + garde la lease** si KO (un fix ne peut pas casser le sourçage, l'agent re-corrige et relance) ; **reset-all** : tous les frères `validate` repartent `to_validate` 0/2 (les `ok:` tombent, `fix:<short>` ajouté, `fix:` antérieurs + `author:` préservés). Le parent **reste `split`**, lease clearée. Commit scopé unique `[<consolidé>, tasks.csv]` `Corrige <id> (<short>)`. |
| `split <id> <child-input>...` | parent → `status=split` ; append des lignes enfant `todo` (`parent=<id>`) ; commit. Enregistre les plages telles quelles (aucune vérif de budget). Cf. [scoping.md](scoping.md). |
| `release <id> [--reason …]` | rend la tâche (`claimed`→`todo`) ou la marque `blocked`/`abandon` avec `note` ; commit. Garde owner (l'appelant doit posséder le lock). |
| `release --force-orphan <short> <id> [--reason …]` | **chemin admin (orchestrateur uniquement), force-release post-kill** — calqué sur `release.py --force-abandon-orphan`. Sous flock, bypasse la garde owner mais **ne reset que si** `owner == <short>` (l'agent tué ; sinon no-op loggé + **rc dédié `FORCE_ORPHAN_NOOP_RC`=3** — récup réelle rc 0, l'orchestrateur les distingue dans son log ; pas de TOCTOU). Orphelin de **production** (`claimed` → `todo`) ; orphelin de **validation** (enfant `to_validate` : reste `to_validate` re-prenable, gate ramené 0/2, note → `author:` seul — le repasser `todo` le gèlerait). Efface `owner`/`claimed_at`/bookkeeping de passe en cours, préserve `output`. **Orphelin correcteur** : si `<short>` tient la lease `correcting:` du reduce parent, la clear **et** `git checkout` du consolidé committé (la version que les valideurs relisent — sinon working-tree dirty validé 2/2 ≠ committé). Commit scopé **`-- 2-consolide/outils/tasks.csv` uniquement** (jamais l'artefact/un dir). Best-effort. → [watchdog.md](watchdog.md) § 6. |

## Sortie de `claim_next` (et `claim`) — contexte de démarrage

`claim_next` (et l'échappatoire `claim`) imprime **la ligne `TASK:` puis le contexte
de démarrage**, une paire `clé: valeur` par ligne, valeur vide → `clé:`. Format
**stable** : tout ce dont l'agent a besoin pour démarrer est là, **sans re-grepper
`tasks.csv`** (les infos viennent du `row` déjà claimé).

```
TASK: map map:cadre_normatif#2
input: 1-sources/1.2-nettoyes/ressources/cadre_normatif/index.md#L256-748
note:
session: dc588706
```

| Ligne | Source | Usage |
|---|---|---|
| `TASK: <type> <id>` | type+id de la ligne (`validate` → `TASK: validate <id>`) | **1re ligne, contrat inchangé** — l'agent y lit sa tâche unique. |
| `input:` | col `input` | chemin source d'un `map` (plage `#L<a>-<b>` si sous-lot splitté), clé de thème d'un `reduce` ; un `validate` (enfant) porte `2-consolide/<clé>.md#sources=slugA,slugB` — le consolidé + **les sources de son shard** (borne le travail du validateur). |
| `note:` | col `note` | bookkeeping ; `note: oversize` ⟹ c'est une tâche de **scoping**, pas un map. |
| `session:` | `<short>` (= l'`owner` que ce claim vient d'écrire) | le short de l'agent — va en `map_session` du fragment. |

> **`peek_next` n'imprime QUE la ligne `TASK:`** (inspection read-only) — pas le
> contexte, qui n'a de sens qu'après un claim réel.

## Gating (appliqué dans `claim_next`/`peek_next`/`claim` — sous flock sauf `peek_next`, read-only)

- `map <id>` : claimable si `status=todo` (inventory ne pose que des sources prêtes).
- `reduce <theme>` : claimable si `status=todo` **et** `grep -l "## theme:<clé>" 2-consolide/2.1-fragments/*.md` rend ≥1 fichier. Ce grep tourne **dans `claim_next`/`peek_next`** : une tâche reduce sans fragment n'est jamais sélectionnée.
- `validate <id>` : prenable si l'**enfant** `validate:<clé>#n` est en `to_validate`, **aucune passe en cours** (`owner` vide) **et** garde distinct-agent OK (per-shard, sur la `note` de l'enfant) — appelant ≠ `author:`, ≠ tout `fix:` (correcteur exclu), **et** ≠ tout `ok:` enregistré sur ce shard. Le reduce parent `split` n'est jamais prenable (non terminal, type ≠ validate).

## Plafond par session

**1 tâche** (map 1 / reduce 1 / validate 1), puis exit. Sessions jetables : un agent prend une seule tâche, la termine, sort ; l'orchestrateur relance à la chaîne. → *pourquoi sessions jetables* : `philosophy/map-reduce.md`.

## Staging des untracked

Contrainte headless (l'agent n'a pas `git add` hors allowlist) : c'est `done`/`split`/`approve`/`corrige` qui stagent l'artefact + le CSV. L'agent ne stage jamais à la main.
