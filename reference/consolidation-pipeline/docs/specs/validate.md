# Gate de fidélité `validate` — par shard de sources, agent-based

S'ajoute au reduce par-dessus `check.py`. Map n'a pas de double passe (sa précision vient du seul `check.py` déterministe). → *pourquoi remonter aux sources et pas aux fragments, risque résiduel map vs reduce* : `philosophy/gate-fidelite.md`.

Sur un thème à fort fan-in (40-50 citations sur 10-14 sources), une seule passe re-résolvant **toutes** les cites dépasse le cap dur de l'agent. Principe : on **rétrécit l'unité de travail**, pas le cap, et on **préserve le 2/2 par agents distincts** pour chaque citation. Le `validate` n'est donc plus un *verbe sur la ligne reduce* : c'est un jeu de **lignes-enfants** du reduce, **bucketées par source**.

## Mécanique (cf. [cli.md](cli.md) + [modele-donnees.md](modele-donnees.md))

- Au `done` d'un reduce, `check.py` passe → le reduce **ne devient pas terminal** : il passe **`split`** (`owner` lâché) et on **append un enfant `validate` par bucket** de [`cite_buckets`](#cite_buckets-bucketing-par-source). `check.py` exige ≥1 cite → au moins 1 bucket ; **0 bucket ⇒ `done` refusé** (reste `claimed`).
- Chaque enfant `validate:<clé>#n` naît `to_validate`, `note=author:<short>`, `input=2-consolide/<clé>.md#sources=slugA,slugB` (le consolidé + **les sources de son bucket**).
- `claim_next --type validate` sélectionne sous flock un **enfant** `to_validate` prenable, garde distinct-agent OK, **et dont le reduce parent ne tient pas de lease `correcting:`** (shard sous correction → reset-all imminent : le claim est un **sémaphore**, il ne rend jamais un shard verrouillé), puis enregistre le validateur comme `owner`. Même exclusion côté orchestrateur (`peek_schedule`) : on ne planifie pas un shard verrouillé — sinon spawn blanc + collision avec le correcteur en place. Source unique de la liste des parents verrouillés : `task.held_lease_parents(rows)`.
- **2 verdicts, aucun chemin nucléaire** :
  - `approve` (verdict `ok`) — append `ok:<short>` ; **2e `ok:` distinct → l'enfant passe `done`**. **Rollup** : quand tous les enfants du reduce sont `done`, le parent `split → done` (même flock).
  - `corrige` (verdict `corrigé`) — le validateur **édite le consolidé en place** au lieu de tout jeter. Pré-requis : `claim-correct` a posé la **lease** `correcting:<short>` sur le reduce parent (sérialise les correcteurs d'un même consolidé). `corrige` re-lance `check.py` (un fix ne peut pas casser le sourçage → **refus + garde la lease** si KO), puis **reset-all** : **tous** les enfants `validate` repartent `to_validate` 0/2 (les `ok:` tombent, `fix:<short>` ajouté). Le parent **reste `split`**, lease libérée. Committe `[consolidé, tasks.csv]`.
- **Ambiguïté non tranchable → `corrige`** (chemin normal) : le validateur pose la lease (`claim-correct`), **édite la section `## Points flous`** du consolidé pour y inscrire le flou ouvert (puce terse), puis `corrige`. Pas de verdict séparé pour « je ne tranche pas » : le flou ouvert **est** la correction.
- **`reject` est supprimé** — plus de cascade « tout refait de zéro ». Un doute se résout par `corrige` (le valideur répare le fait, ou inscrit le flou ouvert en `## Points flous`).
- **2/2 obligatoire par shard.** Le gate est **per-shard** : un même agent peut valider plusieurs shards distincts du même reduce (la distinctness se lit sur la `note` de chaque enfant).

## `cite_buckets` — bucketing par source

`cite_buckets(consolide_path) -> list[list[str]]` (pur, dans `task.py`). Parse les refs du consolidé (`[src:…]` / `[res:…]` / `[arb:…]`, motif `ONE_REF` de `check.py`), compte les citations **par slug de source**, puis empile glouton (slugs triés) tant que la somme des comptes `≤ MAX_CITES_PER_SHARD` (= 12, vise ~60 s sous le cap de 300 s). Cas notables :

- **Une source seule très citée** (> MAX) = son propre bucket (la source est l'atome, on ne la coupe pas).
- **Consolidé peu cité** (total ≤ MAX) → **1 seul bucket** = un unique enfant `validate` ≈ le comportement d'avant.
- **Aucune ref** → `[]` (cas dégénéré, écarté par le refus du `done` ci-dessus).
- **Arbitrages** : **toutes** les cites `[arb:NNNN]` partagent le slug constant `arbitrages` (`_ref_slug`) → un seul bucket, jamais un shard par décision. Le validateur du shard `sources=arbitrages` résout chaque `[arb:NNNN]` contre le mini-ADR `1-sources/1.3-arbitrages/NNNN-*.md` lui-même (le fait y est trivialement présent — fidélité de l'énoncé **et** de la provenance), pas contre une source brute.

## Garde distinct-agent

Vérifiée **sous le flock**, **per-shard**, via le bookkeeping `author:`/`ok:`/`fix:` de la `note` **de l'enfant**. Les deux validateurs d'un même shard doivent être distincts **entre eux**, **de l'auteur** du reduce, **et de tout correcteur** (`fix:`) passé sur le shard (modèle `1-sources/outils/ressources/`, anti-rubber-stamping : *« l'auteur ne valide/corrige jamais, et le correcteur n'approuve pas son propre fix »*). L'appelant est refusé s'il est `author:`, un `fix:` déjà enregistré, un `ok:` déjà enregistré sur ce shard, ou `owner` d'une passe en cours sur ce shard. **En amont de la garde distinct-agent**, la sélection exclut d'office tout shard dont le **reduce parent tient une lease `correcting:`** (le consolidé est en cours de correction, ses shards vont être reset-all) : un claim verrouillé n'est jamais rendu. Si malgré tout un validateur bute sur un verbe refusé (lease prise entre son claim et son `claim-correct` — course TOCTOU résiduelle), le prompt lui dit **STOP** : il rend la main et sort, l'orchestrateur récupère le verrou laissé (`release --force-orphan`, clear-lease).

## Travail du validateur (cognition)

Migrée dans [`2-consolide/outils/prompts/validate.md`](../../2-consolide/outils/prompts/validate.md) — source unique cat'ée par l'orchestrateur. En substance : pour le shard pris, remonter **chaque** fait cité **depuis les sources du bucket** (`#sources=…`) jusqu'à la **source d'origine** (`1-sources/1.2-nettoyes/reports/REPORT_x §N` / `1-sources/1.2-nettoyes/ressources/<slug>/index.md`, **pas** le fragment), lire **seulement les spans cités**, vérifier que la source supporte le fait. Verdict : `approve` si tout est fidèle ; `claim-correct` puis `corrige` si le validateur peut réparer la distorsion en place (ou, si l'ambiguïté n'est pas tranchable, inscrire le flou ouvert dans la section `## Points flous`). Le validateur n'écrit aucun artefact **hors** le consolidé qu'il corrige lui-même. → `README.md` § Prompts, `philosophy/prompts.md`.
