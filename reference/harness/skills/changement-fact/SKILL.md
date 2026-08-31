---
name: changement-fact
description: Quand une déclaration est fausse / périmée, ou qu'on statue (ou re-statue) sur un fait déjà établi — par re-décision de Josian ou feedback CATS.
---

# changement-fact

Faire évoluer un fait **déjà posé** : corriger le canonique, puis **propager** partout où il vit.

## Posture : tu transcris, tu ne rédiges pas
- **Un feedback corrige ce qu'il corrige.** Le fait neuf porte ce que le correcteur a dit — sa portée, ses nuances (« plutôt X » **reste** « plutôt X »). Ce que tu en déduis, ce que tu affines, ce que tu retirerais en passant : ça **remonte à Josian**, ça ne s'écrit pas.
- **L'amont se lit, l'aval s'écrit.** La correction descend (1.3 → 2.2 → 3 → 4). Ce qui l'atteste ne se réécrit pas pour lui faire de la place : un rapport 1.2 restitue son atelier, et une citation `[src:]` / `[arb:]` ne porte que ce qu'elle porte — **relire le fichier cité** avant d'étendre une citation à du texte neuf.

## 0. D'abord : est-ce vraiment un changement de fait ? (gate anti-re-statuation)
**Avant de toucher au ledger 1.3, lire le fait canonique amont** (l'arbitrage 1.3 / la source). Ne re-statue rien tant que tu n'as pas confirmé que **le canonique lui-même est faux/périmé**.
- **Le canonique est déjà correct, et ce qui t'a alerté est une fiche aval (2.2 / 3.x) qui diverge** → c'est un **défaut de propagation**, pas un changement de fait. **Pas de nouvel arbitrage, pas de re-décision.** Saute direct à la **Propagation** : réaligne le texte aval sur le canonique.
- **Le canonique dit déjà ce que tu allais « décider »** → déjà tranché, rien à faire. Ne re-pose pas un arbitrage identique.
- **Le canonique est réellement faux/périmé/à affiner** → seul ce cas justifie la suite (ajout/supersession).

## vs resolution-flou
- **Flou** = ambiguïté non tranchée → router (skill `resolution-flou`).
- **changement-fact** = un fait **déjà acté** devient faux/périmé/affiné → le **remplacer + propager**. Pas de routage, une correction ciblée.

## Substrat (référencer, pas dupliquer)
- `1-sources/1.3-arbitrages/CLAUDE.md` — format mini-ADR, promotion `candidat → settled`, projecteur.
- `2-consolide/CLAUDE.md` — couche 2 peuplée par la pipeline (pas d'écriture manuelle hors propagation flaggée d'une ancre 1.3).
- fiches `3-conception/3.x` citant le fait (`[arb: NNNN]` / `[src:]`).

## Selon l'origine du fait

### Fait du ledger 1.3 (hors-sources)
- **Corriger le mini-ADR en place** : réécrire le corps avec le fait juste ; l'id `[arb: NNNN]` reste stable, aucune citation cassée.
- **Promotion `candidat → settled`** (feedback CATS confirme un candidat) : flip `provenance: settled` + `confirmed_by: <expert>/<date>` **dans le fichier existant**, pas de nouveau fichier.
- Puis **lancer le projecteur** `2-consolide/outils/project_arbitrages.py`.

### Fait distillé d'une source (couche 2)
- **Ancre d'abord en 1.3** : poser un **arbitrage qui l'écrase** (en tête de hiérarchie, gagne le reduce). C'est la **seule** voie durable — la 2.2 est pipeline-only, le re-reduce reproduira l'ancre.
- **Puis (optionnel) hand-édite la 2.2** pour propager tout de suite et bypasser le reduce (aller vite) : légitime **parce que** c'est aligné sur ce que le re-reduce régénérera depuis 1.3. **Flag pipeline** la touche manuelle.
- ⚠ **Toucher la 2.2 sans ancre 1.3** = divergence rogue, **perdue au prochain reduce** → interdit. La condition pour éditer la 2.2, c'est d'avoir changé la 1.3.

## Propagation (manuelle, toujours)
À la main, **pour bypasser les pipelines et aller vite** (ne pas relancer reduce/fact-check de bout en bout).

**Balayer par les TERMES du fait, jamais par son id.** Grepper `[arb: NNNN]` ne remonte que les fiches qui **citent** le fait ; celles qui le portent **en direct** (distillées d'une source, sans le citer) restent invisibles — et ce sont **exactement celles qui divergent**. Le sweep porte sur les **entités** du fait (équipe, outil, process, acronyme — toutes leurs graphies) :

```
grep -rni "<terme1>\|<terme2>" --include='*.md' 2-consolide/2.2-content/ 3-conception/ 4-contenu/
```

- **Trois couches, sidecars compris** : fiches `2.2-content/` · conducteurs `3.1` + `.glossaire`/`.validation` · slides couche 4 + `.visuels`. Un fait faux vit typiquement dans les trois.
- **Chaque hit se lit**, même hors du `theme:` de l'arbitrage : un rôle d'équipe fuit dans les fiches voisines.
- **Vues dérivées** (maps, `visuels-a-sourcer.md`) : régénérées, pas éditées.
- **Commits scopés par fichier** ; concurrence : relire + `git status` **avant** d'éditer, ne pas toucher aux fichiers d'autres agents.
