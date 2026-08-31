---
name: domicile-unique
description: Quand un moule de document répète le même fait dans plusieurs sections (smell de duplication), ou qu'on hésite où ranger un bout de contenu (section du corps vs sidecar). Décide le domicile unique du fait et route le reste.
---

# domicile-unique

Un fait vit **une seule fois**. Quand un moule semble le répéter, ce n'est pas un défaut d'édition à corriger N fois — c'est un **smell structurel du moule** : décide le domicile unique, route le reste, ne duplique jamais.

## Pourquoi (l'erreur corrigée)
Face à un moule qui re-dit le même fait dans plusieurs sections, deux réflexes faux : (a) **éditer les N copies** (on entretient le doublon — toucher au fond = N éditions, lire = N relectures) ; (b) **fusionner/supprimer aveuglément** (on perd des vues légitimes). La répétition n'est **pas toujours** un doublon : une **vue dérivée** du fait (index, checklist, slogan) est saine. Le travail = distinguer *store* de *view*, puis router.

## Le principe
- **Le fait a UN domicile** : le porteur de substance (pour un conducteur 3.1 : le **Déroulé étoffé**).
- Toute autre section est soit **une vue dérivée** (on la garde, réduite à un pointeur/index — jamais re-rédigée), soit **du contenu qui appartient ailleurs** (route-le à son vrai domicile).

## Test 1 — store ou view ?
- **Store** (re-stocke la substance) → **doublon** → tuer, ou **démote en index** (`élément · dosage · « traité au beat X »`).
- **View** (vue dérivée : dosage, emphase, récolte) → légitime, mais **réduite à sa fonction** (1 ligne/élément), **zéro prose re-racontée**.

## Test 2 — handoff/récolte ou design-en-flux ? (pour ce qui survit)
- **Handoff vers une couche aval / récolte terminale** (glossaire → couche 4, liste de slides → couche 4, registre de validation jetable) → **sidecar** `<slug>.<type>.md`.
- **Matière de design lue dans le fil** (index de dosage, exercice, ponts, emphase formateur) → **section du corps**.

## Router, ne pas jeter en bloc
Une section « doublon » se dissout **rarement d'un coup** : décompose-la, chaque morceau a un domicile distinct.
> Ex. — ligne *Concepts* d'un conducteur : *le fait* → Déroulé · *le dosage/garde-fou* → reste en index Concepts · *le libellé d'acronyme* → glossaire-sidecar · *le « même outil qu'en étape X »* → Ponts.

## Avant de figer un moule — tester sur les extrêmes
Ne tranche pas dans l'abstrait. Applique le moule sur **deux cas opposés** : le **plus lourd** et le **cas miroir / dégénéré**. Si la substance migre proprement sur les deux → fige. Sinon, **le résidu qui résiste révèle ce que la section garde vraiment** (souvent : du dosage, pas du contenu).

## Convergence (pas d'éléphant rose)
Substance migrée → l'ancienne section **ne garde aucun record d'écartement** (« X retiré car… », entrée barrée, compteur « Précédents »). Le *pourquoi* vit dans le commit, jamais dans le doc. Instance de CLAUDE.md racine §3.

## Substrat (référencer, pas dupliquer)
- **CLAUDE.md racine §3** — store/archive/inventaire, « pas d'éléphant rose » : ce skill en est la **procédure de décision**.
- **`3-conception/CLAUDE.md`** — moule des conducteurs (corps + sidecars) : l'**instance de référence** de ce skill.
