# Modèle de données — `2-consolide/outils/tasks.csv`

Registre tabulaire unique. Lignes mutées sur place, sérialisées par `flock`, 1 commit par transition. Lu/écrit **uniquement via le module `csv`** (quoting correct) — jamais de split manuel sur `,`. *Pourquoi tabulaire et pas ledger* : `philosophy/map-reduce.md`.

## En-tête figé

```
id,type,status,parent,input,output,owner,claimed_at,done_at,note
```

Une ligne par tâche.

| Colonne | Sens |
|---|---|
| `id` | identifiant stable : `map:<src-slug>` / `reduce:<theme-clé>` ; enfant : `map:<src>#1` |
| `type` | `map` \| `reduce` \| `validate` (extensible sans changer le code). `validate` **est une ligne propre** : un enfant du reduce, un par bucket de sources (cf. § [Lignes-enfants `validate`](#lignes-enfants-validate)) |
| `status` | `todo` \| `claimed` \| `to_validate` \| `done` \| `blocked` \| `split` \| `abandon` |
| `parent` | `id` du parent si sous-tâche, sinon vide (enfant `validate` : `reduce:<clé>`) |
| `input` | source : chemin (`1-sources/1.2-nettoyes/reports/REPORT_x.md`, `1-sources/1.2-nettoyes/ressources/<slug>/`) pour map ; clé-thème pour reduce ; enfant `validate` : `2-consolide/<clé>.md#sources=slugA,slugB` |
| `output` | artefact produit (`2-consolide/2.1-fragments/<src>.md` ou `2-consolide/2.2-content/<theme>.md`) ; enfant `validate` : le consolidé du parent (les enfants ne produisent rien) |
| `owner` | short session (`$CLAUDE_CODE_SESSION_ID[:8]`) du détenteur courant (auteur en `claimed`, validateur courant pendant une passe) |
| `claimed_at` / `done_at` | dates ISO |
| `note` | libre : raison d'un `blocked`/`abandon`, clé `_à-créer` signalée, `oversize` (cf. [scoping.md](scoping.md)), **bookkeeping de validation** d'un enfant `validate` (`author:`/`ok:`/`fix:`, cf. ci-dessous), **ou lease de correction** `correcting:<short>` sur un reduce `split` (cf. [Lease de correction](#lease-de-correction)) |

## Règles d'état

- `status=split` : ligne-conteneur décomposée → `claim_next`/`peek_next` l'ignorent ; ses enfants portent l'état réel. **Jamais terminal** : vaut autant pour un map splité que pour un reduce shardé (« en attente de ses enfants `validate` », pas « fini » — cf. [Cycle de vie](#cycle-de-vie)).
- Source qui ne touche aucun thème : map = `done` quand même, fragment avec frontmatter + `<!-- aucun thème -->`.

## Cycle de vie

**MAP** : `todo → claimed → done`. Gate unique = `check.py` ([check.md](check.md)).

**REDUCE** : au `done` (check.py OK) il ne devient **pas** terminal — il se **shard** en enfants `validate`, un par bucket de sources, chacun portant son propre gate de fidélité 2/2 ([validate.md](validate.md)). Le reduce ne passe `done` que par **rollup**, quand tous ses enfants le sont.

```
todo → claimed → (check.py OK) → split ─┬─ validate:<clé>#1 : to_validate → 2/2 → done
                                        ├─ validate:<clé>#2 : to_validate → 2/2 → done
                                        └─ …
       split → done   (rollup : quand TOUS les enfants validate sont done)
       split → split  (un `corrigé` : consolidé édité en place, frères reset 0/2 — pas de retour todo)
```

- Au `done` d'un reduce, `check.py` passe **mais** la tâche ne devient pas `done` : elle passe `split`, `owner` lâché, et on **append un enfant `validate` par bucket** de [`cite_buckets`](validate.md) (cf. § ci-dessous). `check.py` exige ≥1 cite → au moins 1 bucket ; 0 bucket ⇒ le `done` est refusé (reste `claimed`).
- **Par enfant** : deux validateurs **distincts** (≠ auteur du consolidé, ≠ tout correcteur `fix:`, ≠ l'un de l'autre) relisent ses sources. Chaque `approve` distinct ajoute `ok:<short>` dans la `note` de l'enfant ; **2 distincts → enfant `done`**. Le 2/2 est **per-shard** (un même agent peut valider plusieurs shards distincts).
- **Rollup** : quand le dernier enfant passe `done`, le parent `split → done` (`done_at` posé) — dans le **même flock** que l'approve, pas de TOCTOU.
- **2 verdicts, aucun chemin nucléaire** (`reject` supprimé, cf. [validate.md](validate.md)) :
  - `corrigé` (`corrige`) — le validateur **édite le consolidé en place** (lease `correcting:` posée par `claim-correct`), `check.py` re-tourne, puis **reset-all** : **tous** les enfants `validate` du reduce repartent `to_validate` 0/2 (`ok:` tombent, `fix:<short>` ajouté, owner vidé), le parent **reste `split`** — *le contenu n'est plus celui qu'avaient relu les passes précédentes*. Même flock.
  - **Ambiguïté non tranchable** → même chemin `corrige` : le validateur **édite la section `## Points flous`** du consolidé pour y inscrire le flou ouvert (puce terse), pas de verdict séparé.
- **Orphelin après kill watchdog** : un `claimed` (production) ou un enfant `validate` en `to_validate` (passe abandonnée) garde son `owner` → `release --force-orphan <short>` ([cli.md](cli.md), [watchdog.md](watchdog.md) § 6). Un `claimed` revient `todo`. Un enfant `validate` **reste `to_validate`** avec son gate **reset à 0/2** (owner vidé, note ramenée à `author:`+`fix:` antérieurs) : le repasser `todo` le **gèlerait** (`is_validatable` exige `to_validate`). **Orphelin correcteur** : si le short libéré tient la lease `correcting:` du reduce parent, on **clear la lease** et on `git checkout -- 2-consolide/<clé>.md` (restaure la version committée = celle que les valideurs relisent), sinon un correcteur mort laisserait un working-tree dirty ≠ committé. Le reduce parent `split` n'a pas d'`owner` → jamais orphelin claimable. Seule mutation déclenchée par l'orchestrateur, toujours via `task.py` sous flock (R1).

### Lignes-enfants `validate`

Créées au `done` d'un reduce, une par bucket de sources. Naissent en `to_validate` (prêtes à valider — elles ne produisent aucun artefact, jamais de `done` via `cmd_done`, seulement `approve`/`corrige`).

| Colonne | Valeur de l'enfant |
|---|---|
| `id` | `validate:<clé>#<n>` (`<clé>` = clé de thème du reduce ; `<n>` = 1, 2, …) |
| `type` | `validate` |
| `status` | `to_validate` |
| `parent` | `reduce:<clé>` |
| `input` | `2-consolide/<clé>.md#sources=slugA,slugB` (consolidé + sources du bucket) |
| `output` | `2-consolide/<clé>.md` (le consolidé du parent ; pas d'artefact propre) |
| `owner` | vide à la naissance ; validateur courant pendant une passe |
| `note` | bookkeeping de validation (cf. ci-dessous), init `author:<short>` |

### Bookkeeping de validation dans `note`

Pour un enfant `validate`, `note` porte trois tokens cumulatifs : l'auteur du consolidé (`author:<short>`), les approbations distinctes déjà enregistrées (`ok:<short>`), et les correcteurs passés sur le shard (`fix:<short>`). C'est ce champ que lit la garde distinct-agent ([validate.md](validate.md)) : un appelant est exclu s'il est `author:`, un `fix:` ou un `ok:` déjà enregistré. Round-trip via `parse_validation_note(note) -> (author, oks, fixers)` / `format_validation_note(author, oks, fixers)`. Au reset-all d'un `corrigé`, chaque frère retombe à `author:<orig> fix:<correcteur> [+fix: antérieurs]` (les `ok:` tombent, les `fix:` **persistent**).

### Lease de correction

Un `corrigé` édite le consolidé partagé **hors flock CSV** (travail cognitif). Pour sérialiser les correcteurs concurrents d'un même reduce, `claim-correct <shard>` pose une **lease** `correcting:<short>` dans la `note` du **reduce parent** (`split`, note libre depuis le retrait du reject) ; un `claim-correct` concurrent est refusé tant qu'une autre lease est tenue. La lease est **durable** (champ CSV versionné) → survit entre les deux invocations CLI qui encadrent l'édit. `cmd_corrige` la clear au commit ; un orphelin correcteur la clear aussi (+ `git checkout` du consolidé). Elle n'exclut **que** les correcteurs : un `approve` concurrent reste sûr (le reset-all du `corrigé` vide son `ok:`, le flock CSV sérialise les bascules).
