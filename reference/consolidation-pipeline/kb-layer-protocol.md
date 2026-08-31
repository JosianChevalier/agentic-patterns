# 2-consolide/ — syntheses thématiques (couche 2)

Fichiers **transverses par thème** (CI/CD, squads, archi, tests, CAGIP, data, cyber…) qui agrègent ce qu'on sait depuis la couche 1 (rapports + ressources extraites + pré-contrats). Couche 2 du modèle médaillon décrit dans `CLAUDE.md`.

**Objectif** : avoir plein de petits documents focalisés dans lesquels on **pioche à la demande** sans charger toute la matière en contexte.

## Comment `2-consolide/` est peuplé

`2-consolide/` est peuplé **exclusivement par la pipeline autonome** — agents + scripts déterministes qui consolident les thèmes depuis la couche 1. Spec : `2-consolide/outils/docs/specs/` (prescriptif, à lire pour **appliquer**) + `2-consolide/outils/docs/philosophy/` (le *pourquoi*, à lire avant de **changer** la spec). Il n'y a **aucune voie manuelle** : c'est une knowledge base purement agentique, et Josian fait avancer la formation elle-même (couche 3) en parallèle sans éditer la KB à la main.

**Une seule entrée manuelle** : les arbitrages (faits CATS absents des sources mais tranchés à la main / par feedback CATS hors CR), en couche 1 sous `../1-sources/1.3-arbitrages/` (un mini-ADR par décision). Ils ne sont **pas mappés** : un **projecteur déterministe** (`outils/project_arbitrages.py`) les plie en `2.1-fragments/arbitrages.md`, consommé par le reduce **en tête de hiérarchie**. Servent aussi la validation des fiches couche 3. Cf. `../1-sources/1.3-arbitrages/CLAUDE.md`.

## Nature des emplacements (cf. `CLAUDE.md` §3)

Qui touche quoi, et comment chaque emplacement se traite selon les 3 cas (plan de travail / archive / inventaire) :

| Emplacement | Nature | Qui / comment |
|---|---|---|
| `outils/tasks.csv` | plan de travail | orchestrateur + agents (claim/finish/release) ; une tâche `todo` = à faire, **se vide** |
| `## theme:_à-créer:` dans `2.1-fragments/` | plan de travail | agents map posent un candidat clé ; **Josian arbitre** → promu (devient vraie clé) ou écarté → le **marqueur disparaît**, la distillation reste |
| *Points flous* (des fiches / rapports) | plan de travail | à trancher quand un thème consolide les touche |
| `2.2-content/<theme>.md` (consolidés) | archive | produits par reduce ; le rendu de la couche — **gardés**. Leur section `## Points flous` est un **plan de travail** (flou ouvert = puce ; résolu → retiré ; aucun → `-`) |
| `2.1-fragments/<src>.md` | archive | distillation sourcée par source (map) — « lu, compris, catégorisé » ; **jamais supprimée** |
| `../1-sources/1.3-arbitrages/NNNN-*.md` | archive | mini-ADR par décision, manuel / feedback CATS (hors couche 2) |
| `outils/outlines/` | archive | seeds |
| `outils/inventory.py` (sa sortie) | inventaire | vue de couverture clés ↔ ce qui existe ; un écart = travail sur l'**archive**, jamais maquillé |
| `THEMES.md` | référence (vocab contrôlé) | source de vérité des clés ; étendue **uniquement** via `_à-créer` + arbitrage |

## Format d'un fichier thématique

Cible ~100-300 lignes. Au-delà, signe qu'il faut découper. **Source de vérité du gabarit : `outils/prompts/reduce.md`** (le reduce produit ces fiches) ; ce qui suit en est le résumé. Le gabarit **dépend de l'axe** (cf. `THEMES.md`).

**Commun aux deux axes** :
- **Frontmatter « quand_piocher »** : **bloc `---` en tête de fiche, avant le titre**, champ `quand_piocher: "<phrase greppable>"` (façon `description:` d'un skill) — index de découverte entre thèmes, greppable et préchargeable côté agents couches 3/4. **Imposé par `check.py`** (présence du champ, les deux axes).
- Cible 100-300 lignes ; acronyme → au moins sa glose ; citations `[src:]`/`[res:]`/`[arb:]` reprises verbatim des fragments.

### Axe CATS (clés métier/technique — « comment CATS fait X »)

5 sections **imposées par `check.py`** ; « Matérialisation CATS » **doit** porter des citations.

```markdown
---
quand_piocher: "<phrase greppable : dans quel cas un agent/Josian lit cette fiche.>"
---
# <Thème>

<1-3 phrases de cadrage : ce que le fichier couvre / ne couvre pas.>

## Cœur d'industrie
<L'état de l'art, indépendant de CATS. Le *pourquoi* avant le *comment*.>

## Matérialisation CATS
<Comment ça se traduit chez CATS. Faits cités `[src: <slug> §N]` / `[res: <slug>/<fichier>]`.>

## Tension industrie ↔ CATS
<Écart **à l'altitude de l'audience** (BA/PO non-tech) seulement. Gap **trop technique** (stratégie de branches…) → `-` seul, on ne nomme pas la pratique d'industrie. Gate dans reduce.md.>

## Points flous
<**Plan de travail** : flou **ouvert** seulement (une puce terse), résolu → retiré, aucun → `-` (zéro prose). Gate dans reduce.md.>

## Sources
- Rapports : <liste> · Ressources : <liste> · Pré-contrats : <si pertinent>
```

### Axe formation (clés `formation-*` — « ce qui est attendu / comment on conçoit »)

**Forme libre, pas de gabarit.** `check.py` n'impose ici que le frontmatter (`quand_piocher`), le titre, les refs non cassées et la taille — **aucune section.** On n'instancie **pas** le gabarit axe CATS (pas de `## Cœur d'industrie`, `## Tension industrie ↔ CATS`, `## Points flous`) : c'est de l'overhead sur cet axe. Chaque fiche prend la structure que **son** contenu appelle. Règles de rédaction :

- **Que des faits actionnables**, cités `[src/res/arb:…]` (verbatim des fragments) ; tags `[candidat]`/`[settled]` reportés.
- Le ***pourquoi* de conception** (ex-« Cœur d'industrie ») se **replie inline** dans la décision qu'il justifie — pas de section dédiée, pas de théorie pédagogique générique.
- **Bullets, phrases courtes** (cf. `CLAUDE.md` §0bis) — pas de prose.
- Une **question de conception ouverte** ne reste pas dans la fiche : elle remonte en arbitrage (couche 1) ou en couche 3.
- Bloc minimal : `quand_piocher` + titre + 1-3 lignes de cadrage (ce que la fiche couvre / ne couvre pas) + le corps + `## Sources`.

**Critère de découpe** : un fichier = un thème qu'on pourrait charger seul en session sans avoir besoin des autres. Si on se retrouve à toujours charger A + B ensemble, fusionner.

**Pas de validation `N/N` systématique** — la convergence se fait à l'usage pédagogique (couche 3). Si un fichier sert effectivement à produire du livrable et que le résultat tient, c'est validé.

## Charger les fiches `formation-*` par consommateur (axe formation)

Les 13 fiches `formation-*` ne se **piochent pas à la carte** (absentes de l'index `quand_piocher`). Mais on ne les charge pas non plus **toutes en bloc** : chaque agent **consommateur** charge **le set de son rôle**. **Source canonique du mapping** (les autres couches pointent ici, ne recopient pas) :

| Consommateur | Set `formation-*` à charger |
|---|---|
| **A0 — pilotage** (`0-pilotage/reunions/`) | objectifs · audiences · scope-decisions · modalites · planning · methode-construction · livrables |
| **A3 — conception** (couche 3) | objectifs · audiences · scope-decisions · modalites · programme-axes · messages-cles · posture-editoriale · fil-rouge · suggestions-pedagogiques |
| **A4 — contenu** (couche 4) | programme-axes · messages-cles · posture-editoriale · livrables · **glossaire** (seulement quand on travaille le glossaire — se charge à part) |

- **But** : un agent ne charge que son sous-ensemble (≈ −24 % de contexte côté A3, ≈ −61 % côté A4 vs « charge tout », sur ~15 k tok).
- **Blocs partagés** (pour raisonner le mapping, pas pour fusionner) : *cadre* {A0,A3} = objectifs·audiences·scope-decisions·modalites ; *ossature partagée* {A3,A4} = programme-axes·messages-cles·posture-editoriale.
- **Pas de fusion physique** des fiches : re-cléer la couche 2 serait un chantier pipeline, écrasé au prochain reduce. Fusion **différée**, à n'envisager que si un co-chargement se stabilise à l'usage (couches 3/4 encore mouvantes).

## Articulation avec les chantiers couche 1

- **`common/archive/synthesis-done.md`** : pilotage historique de la synthèse (archivé) — y compris la suppression des deux ex-synthèses de 1re passe (`synthesis/`, dépréciées, contenu absorbé en couche 2).
- **`1-sources/1.2-nettoyes/ressources/`** : continue son pipeline propre. Plus il s'étoffe, plus les fichiers consolide deviennent solides.

## Différé

- **Audit fidélité résiduel** : **résorbé** (items absorbés en couche 2, reliquat en `QUESTIONS-CATS.md`, ex-synthèse d'audit supprimée). Restent les *Points flous* des rapports : à trancher au moment où un thème consolide les touche, avec `1-sources/1.2-nettoyes/ressources/` grepable à la main.