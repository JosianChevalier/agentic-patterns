# Protocole — Extraction ressources (pour agents)

Référence pour les agents qui prennent une tâche dans `RESSOURCES_TODO.md`. Lis ce fichier en entier avant de claim. Pour le comportement détaillé des scripts (`claim.py`, `release.py`…), la spec exécutable est `tests/`.

## Le cadre — 1 claim, 1 lot borné, puis tu SORS

**1 agent = 1 claim = 1 cellule = 1 fichier.** Contexte minimal : tu n'as pas besoin des autres lignes ni de l'ensemble du projet. Tu pickes une cellule libre, tu fais **un lot borné**, tu releases, tu **sors**.

**Plafond par claim** — c'est la règle qui dérape le plus, lis-la bien :

| Étape | Plafond par claim |
|---|---|
| **Triage** | **3 slides candidates** |
| **Transcribe** | **1 PNG** |
| **Embed** / **Validate** | cellule entière (pas de plafond par-item) |
| **Extract** | hors périmètre sous-agent (manuel Josian) |

Tu fais **ton lot, pas la cellule**. Une fois tes 3 slides (ou ton 1 PNG) faits : tu release et tu **sors immédiatement — même si la cellule reste en `K/N`**. Tu ne cherches pas à « finir la cellule ». Les slides/PNG suivants sont pour l'agent **suivant**. Le volume est géré par le **nombre d'agents lancés** (orchestrateur), **pas par ton endurance**. Beaucoup de petits agents jetables, jamais un agent qui enchaîne. **Jamais de 2ᵉ claim**, même libre, même la même ligne.

> ⚠ **Dépasser ton plafond = travail perdu.** L'orchestrateur audite les agents en cours et **kill** (verdict déterministe : il compare la valeur figée dans la cellule au nombre de livrables présents) ceux qui produisent plus que leur plafond dans un seul claim. Un agent qui rabote la cellule entière finit par se dégrader (sauts de slide en slide, abandon, `signalé` fabriqué). Reste dans ton lot.

## Pipeline

```
Extract  →  Triage  →  Embed  →  Transcribe  →  Validate
(Josian)    (LLM)      (LLM)     (LLM)          (LLM, ≠ composeur)
```

- **Extract** : déterministe, produit `index.md` brut + rasterisation. **Lancé à la main par Josian, hors orchestrateur et hors sous-agents** (cf. § Extract). Une cellule Extract `—` n'est pas pickable, ni les étapes suivantes du slug : saute-la.
- **Triage** : décide quels visuels rasterisés apportent de l'info absente du texte. Sortie : `triage.md`. Aucune écriture dans `index.md`.
- **Embed** : insère les PNG retenus dans `index.md` (copie à la racine + `![]()`).
- **Transcribe** : retranscrit chaque PNG embeddé en texte fidèle (`<retranscription>…</retranscription>`).
- **Validate** : agent ≠ composeur vérifie la fidélité. `1/2` → `2/2` (deux passes, deux agents distincts).

## Choix de la cellule

Repère **toutes** les cellules prenables, puis **tires-en une au hasard**. Ne prends **pas** systématiquement la première : plusieurs sous-agents démarrent en parallèle et lisent le même tableau avant qu'aucun claim ne soit posé ; viser tous la première cellule = collisions de démarrage. Le tirage aléatoire vous disperse.

Une cellule est prenable si **Verrou est vide** (`—`) **et** :

- **Validate** : Transcribe ∈ {`ok`, `corrigé`} (ou Triage = `skip`) et Validate ∈ {`—`, `0/2`, `1/2`}, **et tu n'es ni composeur ni premier validateur**.
- **Transcribe** : Embed est `ok` et Transcribe ∈ {`—`, `K/N` avec K<N}.
- **Embed** : Triage est `ok` (≥1 PNG retenu) et Embed est vide.
- **Triage** : Extract est `done <sha>` et Triage ∈ {`—`, `K/N` avec K<N}.

Les gardes "≠ composeur" / "≠ premier validateur" sont vérifiées par `claim.py`.

## Identité & commits

`claim.py` / `release.py` lisent `$CLAUDE_CODE_SESSION_ID`, en prennent les 8 premiers caractères (`<short>`) comme identité, puis **stagent et committent eux-mêmes** — **ne touche pas au format** :

- Claim : `Claim <step> <slug> (<short>)`
- Release : `<Step> <slug>: <result> (<short>)`

Le `<short>` apparaît dans la colonne Verrou pendant le claim et sert aux gardes "≠ composeur" / "≠ premier validateur" à Validate. Pour lire ton `<short>` : `common/outils/whoami.py` (whitelisté). **N'utilise pas** `echo $CLAUDE_CODE_SESSION_ID` (`echo` hors allowlist).

Abandon en cours : `python3 1-sources/outils/ressources/release.py <step> <slug> abandon`.

## Étape Extract (manuel — Josian uniquement)

Hors périmètre sous-agent (cf. § cadre). Documenté ici pour référence.

**But** : produire le squelette `1-sources/1.2-nettoyes/ressources/<slug>/` (texte intégral + rasterisation complète dans `_all_pages/`). Raison du retrait du périmètre auto : `claude -p` peut auto-backgrounder une commande longue sans `run_in_background` explicite, laissant `extract.py` orphelin et la cellule verrouillée jusqu'au cap absolu (run 20260527-223339). `extract.py` est retiré de l'allowlist sous-agent **et** du pré-flight orchestrateur.

```bash
1-sources/outils/ressources/claim.py extract <slug>
1-sources/outils/ressources/extract.py <slug>                          # déterministe, idempotent
1-sources/outils/ressources/release.py extract <slug> "done <sha8>"    # ou "signalé <raison>" si crash
```

`extract.py` dépose aussi `<slug>/.extract.md` (snapshot pristine, gitignored) utilisé par `check_text_preservation.py`. Si le snapshot manque (slug pré-snapshot, fresh clone) : `1-sources/outils/ressources/extract.py --snapshot-only <slug>` le régénère sans toucher à l'`index.md` courant.

## Étape Triage

**But** : décider quels visuels apportent de l'info absente du texte. **Aucune écriture dans `index.md`.**

**Prérequis** : Extract `done <sha>`. **Plafond : 3 slides candidates** (cf. § cadre). `triage.md` est **append-only** : tu ajoutes aux sections existantes, tu ne retouches jamais celles d'un autre agent.

1. Lis `1-sources/1.2-nettoyes/ressources/<slug>/index.md` (texte brut).
2. Parcours `_all_pages/*.png` (pptx/pdf) **ou** `media/*` (docx). Si `triage.md` existe déjà, **ignore les slides déjà citées** (dans `## Retenus` ∪ `## Skip`) et prends les **3 suivantes** (ordre croissant).
3. Pour chaque image, **règle dure** : *l'info de l'image (labels, chiffres, relations, structure) est-elle déjà dans le texte adjacent de l'`index.md` ?* **Oui** → skip. **Non** → retenir + note l'ancre d'insertion (un titre/paragraphe identifiable après lequel insérer).
4. **Append** tes décisions dans `triage.md` (crée le fichier au premier claim) :

   ```markdown
   ---
   slug: <slug>
   ---

   ## Retenus

   - `_all_pages/slide-4.png` — insert after: `## Slide 4 — Synthèse février 2025` — raison: think-cell (4 quadrants chiffrés non transcrits)

   ## Skip

   - `_all_pages/slide-1.png` — raison: page de garde, titre identique au H1
   ```

   Pas de compteur dans le front-matter : la **liste des décisions est le compteur** (`release.py` compte les réfs `slide-N.png` / `imageN.png` distinctes dans Retenus ∪ Skip).

5. **Pas d'écriture dans `index.md`**.

**Cas par type de fichier** (set de candidats + défaut) :

- **PPTX/PDF** (`_all_pages/slide-N.png`) : rendu texte **+** visuels. **Default = skip** sur slides texte-only. Retain uniquement think-cell, SmartArt, diagrammes, schémas, graphiques. Beaucoup de `skip` sur un PPT long = normal.
- **DOCX** (`media/imageN.png`) : illustrations isolées. **Default = retain** (presque toujours porteuse d'info). Skip si décorative (logo, séparateur).
- **Image standalone** (le PNG est la ressource, `index.md` minimal) : 1 candidat, **toujours `ok`** en un claim. Ancre triviale (après le H1).

L'ancre (`insert after: …`) positionne le visuel dans le flux narratif : PPTX/PDF → ordre des slides ; DOCX → paragraphe qui introduit l'image.

```bash
python3 1-sources/outils/ressources/claim.py triage <slug>
# ... travail (≤3 slides) ...
python3 1-sources/outils/ressources/check_text_preservation.py <slug>   # vérif index.md intact
python3 1-sources/outils/ressources/release.py triage <slug> ok
```

Tu releases **toujours `ok`** (= « batch fait, rien à signaler ») — jamais `K/N` ni `skip` en arg. `release.py` compte K (slides tranchées) et N (PNG candidats sur disque), écrit `K/N` tant que K<N, puis à K==N `ok` (≥1 retenu) ou `skip` (zéro retenu — court-circuite Embed+Transcribe). Une cellule déjà à `K/N` se reclaim normalement (la suite est pour toi). **Exception** : si tu n'ajoutes aucune décision (plantage avant écriture, désistement) → release `abandon`, sinon le claim est consommé pour rien.

Résultats : `ok` | `signalé <raison>`.

## Étape Embed

**But** : insérer les PNG retenus par Triage dans `index.md`, sans toucher au texte existant.

**Prérequis** : Triage `ok`. **Plafond : cellule entière.**

1. Lis `triage.md`.
2. Pour chaque PNG retenu : copie-le depuis `_all_pages/` (ou `media/`) vers la racine `1-sources/1.2-nettoyes/ressources/<slug>/`, puis insère `![](nom-du-png.png)` dans `index.md` juste après l'ancre.
   - **Collision de nom** (rare, deux sources → même basename) : suffixer `slide-1-2.png`, etc.
3. **Ne modifie aucun texte existant** ; ajout de lignes d'embed uniquement.
4. **Aucune retranscription** — c'est Transcribe.
5. **Cas image standalone** : Extract a déjà posé le PNG à la racine **et** la ligne `![]()`. Embed est un **no-op** — release `ok` directement après le check.

```bash
python3 1-sources/outils/ressources/claim.py embed <slug>
# ... travail ...
python3 1-sources/outils/ressources/check_text_preservation.py <slug>
python3 1-sources/outils/ressources/release.py embed <slug> ok
```

Résultats : `ok` | `signalé <raison>`.

## Étape Transcribe

**But** : pour chaque PNG embeddé dans `index.md`, ajouter en adjacent une retranscription texte fidèle.

**Prérequis** : Embed `ok`. **Plafond : 1 PNG** (cf. § cadre). La cellule progresse en `K/N` (K retranscrits / N embeddés au root) → `ok` à K==N.

> Plafond à 1 (abaissé de 3) : sur les slides denses (MCD, think-cell), enchaîner plusieurs PNG faisait déraper budget/qualité. 1 PNG/agent = chaque passe reste courte et fiable.

1. Repère les `![](xxx.png)` **au root** du slug (pas de `/` dans le path — les `![](./_all_pages/…)` sont des réfs brutes, pas des embeds) **non encore suivis** d'un bloc `<retranscription>…</retranscription>`. Prends-en **un seul** (le premier non transcrit).
2. Lis le PNG (`Read` sur le fichier original suffit en général).
3. Ajoute immédiatement après l'embed un bloc encadré par `<retranscription>` … `</retranscription>` (tag XML, contenu libre — listes, tables, code fences, lignes vides OK) :

   ```markdown
   ![](slide-4.png)

   <retranscription>
   - Quadrant haut-gauche — « Idéation » : 12 idées/mois (KPI vert)

   | Étape | Owner | KPI |
   |-------|-------|-----|
   | …     | …     | …   |
   </retranscription>
   ```

4. **OCR fidèle** : mot-pour-mot pour labels et chiffres, structure pour les relations. Pas de paraphrase, pas d'analyse.
5. **Chrome à ignorer** (aucune info pédagogique) : logos (CATS, Crédit Agricole, CAGIP, Shodo…), copyright / confidentialité / « hypothèses de travail », numéros de slide, dates de version, watermarks, gabarits répétés.
6. **Ne modifie pas le texte existant** (hors ajouts post-embed).
7. **PNG dense / labels illisibles** : `Read` resize à ~1568 px → flou. Crop ciblé : `1-sources/outils/ressources/crop.py <src> <x> <y> <w> <h>` (écrit `$TMPDIR/formation-cats/zoom.png`, imprime le path) puis `Read`. 1-2 crops max, pas de mosaïque exhaustive.
   - **Raster source trop basse résolution** : si même les crops restent flous, c'est souvent que le PNG de `_all_pages/` a été rasterisé en basse déf — pas que le visuel est illisible. **Avant de conclure à l'impossibilité**, re-rendre la page en haute résolution depuis le binaire source : `pdftoppm -png -r 300 -f <page> -l <page> <source.pdf> $TMPDIR/p` (monter à `-r 600` si besoin), puis `Read`. Une mosaïque par zones est autorisée **ici** (on lit pour transcrire un haute-déf, pas pour brute-forcer un raster dégradé). Chemin du source : frontmatter `source:` de l'`index.md`.

```bash
python3 1-sources/outils/ressources/claim.py transcribe <slug>
# ... travail (1 PNG) ...
python3 1-sources/outils/ressources/check_text_preservation.py <slug>
python3 1-sources/outils/ressources/release.py transcribe <slug> ok
```

Tu releases toujours `ok` — pas de `K/N` en arg. `release.py` calcule K et N, écrit `K/N` (ou `ok` si K==N). Une cellule déjà à `K/N` se reclaim normalement. **Exception** : aucune retranscription ajoutée (plantage avant Edit, désistement) → release `abandon`, sinon le claim est consommé sans bouger la cellule.

Résultats : `ok` | `signalé <raison>`.

## Étape Validate

**But** : confirmer la fidélité de `index.md` vs source. Deux passes `ok` consécutives par deux agents distincts (≠ composeur, ≠ premier validateur) closent la ligne.

**Prérequis** : Transcribe ∈ {`ok`, `corrigé`} ou Triage `skip` ; Validate ∈ {`—`, `0/2`, `1/2`}. **Plafond : cellule entière.** Gardes ≠ composeur / ≠ premier validateur appliquées par `claim.py`.

Cellule (gérée par les scripts) :

| État | Sens | Transition sur release |
|---|---|---|
| `—` | aucune passe | `ok` → `1/2` |
| `1/2` | une passe `ok` | `ok` → `2/2` (terminé) |
| `0/2` | dernière passe a `corrigé` | `ok` → `1/2` |
| `2/2` | ligne terminée | — |
| `signalé <raison>` | bloqué, arbitrage Josian | écrit la cellule telle quelle |

`corrigé` (à n'importe quel état) → `0/2` : le correcteur ne peut pas s'auto-valider, il faut 2 passes propres après.

**Travail à faire** — préalable commun : `python3 1-sources/outils/ressources/check_text_preservation.py <slug>` (texte d'origine intact vs `.extract.md`).

- **Cas A — `triage = ok`** :
  1. Tous les PNG « Retenus » de `triage.md` sont bien embeddés dans `index.md`.
  2. **Audit inverse** : parcourir `_all_pages/*.png` (PPTX/PDF — regénérer via `extract.py` si absent) ou `media/*` (DOCX) et confirmer qu'aucun PNG critique n'a été indûment skip. Tolérance forte sur le texte-only ; intolérance sur les visuels (schémas, think-cell, diagrammes).
  3. Chaque retranscription est **fidèle** : chaque label, chiffre, relation présent dans le bloc `<retranscription>`. Pas de paraphrase, pas d'omission.
- **Cas B — `triage = skip`** : audit du skip — parcourir tous les candidats, confirmer qu'aucun n'aurait dû être retenu.
- **Cas C — image standalone** : PNG embeddé après le H1 + retranscription fidèle (cf. cas A.3).

Résultats :

- `ok` : rien à corriger → +1.
- `corrigé` : tu as modifié le fichier → `0/2`. Modifs stagées/committées par `release.py`.
- `signalé <raison>` : défaut non tranchable (ambiguïté source, erreur handler…) → note en *Points flous* si pertinent.

```bash
python3 1-sources/outils/ressources/claim.py validate <slug>
# ... travail ...
python3 1-sources/outils/ressources/release.py validate <slug> <ok|corrigé|signalé ...>
```

## Si ça coince

- `claim.py` échoue : verrou pris ou prérequis pas remplis. Normal en parallèle — prends une autre tâche.
- `check_text_preservation.py` échoue : tu as modifié le texte d'origine sans le vouloir. Diff `index.md` vs `<slug>/.extract.md`, corrige avant release. Sinon `release.py <step> <slug> abandon`.
- Étape impossible (fichier corrompu, ancres introuvables, ambiguïté source) : `release.py <step> <slug> "signalé <raison>"`, passe à autre chose.

## Ce que tu ne fais pas

- **Pas d'analyse pédagogique.** Tu structures et tu vérifies la fidélité ; l'orientation pédagogique vient plus tard, séparément.
- **Pas de réécriture du contenu source.** Triage et Embed n'altèrent **jamais** le texte d'origine ; Transcribe ajoute en adjacent.
- **Pas de modification du tableau à la main.** Toujours via `claim.py` / `release.py`.
- **Pas de 2ᵉ claim, pas de dépassement de plafond** (cf. § cadre).
