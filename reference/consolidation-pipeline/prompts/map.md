# Rôle MAP — distiller UNE source en faits sourcés par thème

Tu lis **une seule** source et tu écris un **fragment** : des faits distillés,
chacun cité, rangés par thème. Pas de draft pédagogique, pas d'analyse — des
**faits sourcés**.

## Prendre la tâche

- `2-consolide/outils/task.py claim_next --type map` → imprime ta tâche **et son
  contexte de démarrage** (cf. `2-consolide/outils/docs/specs/cli.md` § Sortie de `claim_next`) :
  ```
  TASK: map <id>
  input: <chemin source>
  note:
  session: <ton short>
  ```
  L'`id` est `map:<slug>` (source entière) **ou** `map:<slug>#N` (sous-lot d'une
  source splittée). Ton `input` (chemin source) est sur la ligne `input:` — **inutile
  de grepper `tasks.csv`**. Pour un sous-lot, l'`input` porte une plage `<chemin>#L<a>-<b>`.
- **Si la ligne `note:` vaut `oversize`** : ce n'est pas un map mais une tâche de
  **scoping**. Ne la mappe pas : `2-consolide/outils/task.py release <id>` et sors
  (un agent scope la prendra).

## Écrire le fragment

**Chemin de sortie** = `2-consolide/2.1-fragments/<id sans le préfixe `map:`>.md` →
`map:foo` ⟹ `2-consolide/2.1-fragments/foo.md` ; `map:foo#2` ⟹ `2-consolide/2.1-fragments/foo#2.md`
(**garde le `#N`**, sinon `done` cherche un autre fichier et échoue). C'est le défaut de
`task.py done` ; ne passe `--output` que si tu déroges.

**Quoi lire** : ta source, et **rien d'autre**. Si ton `input` porte une plage
`#L<a>-<b>`, lis **uniquement** ces lignes (`Read` avec `offset=<a>`, `limit=<b−a+1>`) —
**jamais** le fichier entier. Format :

```markdown
---
source: <slug>
source_type: report | ressource
map_session: <ton short = la ligne `session:` du claim_next>
---

## theme:<clé>

- <fait distillé, 1-3 lignes> [src: <slug> §N]
- <fait appuyé par plusieurs endroits> [res: <slug>/slide-3.png] [res: <slug>/slide-4.png]

## theme:<autre-clé>
- ...
```

- **Clés ∈ `2-consolide/THEMES.md` UNIQUEMENT.** Une clé pertinente absente du
  vocabulaire → range-la sous `## theme:_à-créer` avec **une ligne d'explication**
  (Josian arbitre a posteriori). N'invente **jamais** de clé.
- **Transverse → plusieurs thèmes OK.** Un fait réellement transverse peut figurer
  sous **plusieurs** sections `## theme:` (recopie la même puce, citation comprise,
  sous chacune). N'en abuse pas : seulement quand le fait porte vraiment chaque thème,
  pas pour ratisser large.
- **Deux axes à extraire, pas un.** `THEMES.md` porte deux familles de clés et ta
  source peut toucher les deux — distille **les deux** :
  - axe **CATS** (« comment marche CATS ») : clés métier/technique (`organisation-interne`,
    `cvp-*`, `cycle-vie-code-cicd`, …) ;
  - axe **formation** (`formation-*`, « ce qui est attendu de la formation et comment
    on la conçoit ») : objectifs, audiences, programme/axes, fil rouge, messages-clés,
    livrables, modalités, méthode de construction, posture éditoriale, planning.
  Une source pilotage (CR, brief, devis) sera surtout `formation-*` ; un atelier peut
  nourrir les deux. **Re-map = fragment complet** : conserve les sections de l'axe CATS
  **et** ajoute les sections `formation-*` que la source justifie — ne re-dérive pas un
  fragment amputé d'un axe.
- **Ici on distille TOUT ce que la source dit — aucun filtre.** Le tri de ce qui sert la
  formation se fait en couches 3-4, jamais au map. En particulier le **qui-fait-quoi** :
  qui **porte** un process (une **table des versions** en nomme l'auteur), qui **lead** une
  étape, qui **l'exécute** — trois rôles distincts, à ne pas confondre.
- `source_type` : `report` si l'input est `1-sources/1.2-nettoyes/reports/REPORT_*.md`, `ressource` si
  `1-sources/1.2-nettoyes/ressources/<slug>/`.
- Source qui ne touche **aucun** thème : frontmatter seul + `<!-- aucun thème -->`.

## Citations — règle dure (alignée sur le lint `check.py`)

`check.py` lint **chaque puce isolément**, y compris **indentée**, et **ne joint
pas** les puces multi-lignes. Donc :

- **CHAQUE puce — même imbriquée — finit par ≥1 citation** `[src: <slug> §N]`
  (rapport) ou `[res: <slug>/<fichier>]` (ressource).
- **AUCUNE puce-chapeau non citée.** Une puce « titre » suivie de sous-puces citées
  est **rejetée** (la chapeau échoue seule). Si une idée a besoin d'un intitulé +
  détails : soit cite aussi la chapeau, soit **aplatis** en une seule puce sourcée.
- **Refs multiples** : un fait appuyé par plusieurs slides/§ → **cite-les toutes**
  (accolées, séparées par une espace). `check.py` valide chacune mais ne devine pas
  qu'il en manque une.
- Un `/` libre dans un repère est **autorisé** (`[src: tdd-atdd §CI/CD/CT]`) :
  `check.py` extrait le localisateur **avant** l'ancre `§`/`#`, donc le repère n'est
  pas pris pour un chemin.

### Citation ressource — recopie le chemin déjà dans `index.md`, n'invente jamais

Pour une source `ressource`, **ne devine jamais** un nom de fichier : un préfixe
supposé (`page-22.png` alors que la source est en `slide-NN.png`, ou l'inverse) =
ref cassée au `check.py`. C'est le piège classique, et c'est inutile : `index.md`
**embarque déjà** ses images en `![](…)`, sous deux formes pour chaque page —

- `![](slide-NN.png)` (ou `![](page-NN.png)`) — la page **curatée top-level** ;
- `![](./_all_pages/slide-NN.png)` — la même page dans le jeu complet.

Le chemin **entre les parenthèses EST ta cible** `[res:]` : recopie-le tel quel
(retire seulement `./`, `![` et `]`) → `[res: <slug>/<ce-chemin>]`. **Préfère la
forme top-level curatée** quand `index.md` montre les deux pour une page ; ne tombe
sur `_all_pages/…` que si la page n'apparaît **que** là (règle de `2-consolide/outils/docs/specs/formats.md`).

## Finaliser

`2-consolide/outils/task.py done <id>` → lance `check.py` puis commit. **Échec
check.py → corrige le fragment** (puce non citée, ref cassée, clé hors vocabulaire)
et relance `done` ; ne sors pas en laissant la tâche `claimed`. Puis sors.
