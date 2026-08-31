---
name: resolution-flou
description: Quand on a une incertitude sur un fait, la source d'une déclaration ou un fonctionnement de CATS (typiquement les flous d'un FACTCHECK / la section `## Points flous` d'une fiche consolidée).
---

# resolution-flou

Trancher les flous d'un fact-check : pour chaque flou, **chercher la source couche 1 d'abord**, présenter à Josian, router selon SA décision.

## Pourquoi (l'erreur corrigée)

Un flou est **souvent un faux flou** : un fait **bien sourcé en couche 1** (transcript/notes/ressource) mais **jamais distillé en couche 2**. L'agent qui route sans chercher le traite à tort comme « hors-sources » (arbitrage) ou le jette. **Toujours fouiller la couche 1 avant de router.**

## Substrat (référencer, pas dupliquer)
- `1-sources/1.3-arbitrages/CLAUDE.md` — tri des flous, format mini-ADR, projecteur, file `QUESTIONS-CATS.md`.
- `2-consolide/2.2-content/cvp-*.md` — consolidés couche 2 (cible d'injection d'un faux flou).
- la fiche concernée `3-conception/3.x` (+ son `.validation.md`) — d'où vient le flou.

## Procédure

### 1. Cadrer le plan de travail
- Identifier le FACTCHECK (c'est un **plan de travail → se vide**) et la liste des flous en attente.
- **Relire le fichier + `git status` AVANT d'éditer** (d'autres agents peuvent être sur le même dossier).

### 2. Chaque flou — chercher la source D'ABORD
- Lancer un sous-agent **Explore** (lecture seule) qui cherche **exhaustivement** en couche 1 :
  `1.1-raw/` (transcripts = vérité, notes) + `1.2-nettoyes/` (reports, ressources).
- Objectif unique : trancher **sourcé / non-sourcé** avant de présenter quoi que ce soit.

### 3. Josian tranche — un flou à la fois, en échange vivant
Exposer le flou + le résultat de la recherche. **Pas de QCM** (`AskUserQuestion`) : on propose, on discute. **Citer le verbatim** du flou (jamais le paraphraser) — Josian n'a pas la tête dans les fichiers. **L'agent ne décide jamais.** 4 issues :
- **Tej** — sans valeur (graphie, attribution, pur chiffre/nom interne sans concept) → **retirer du FACTCHECK**.
- **Question CATS** — ni la KB ni Josian ne tranchent → `1-sources/1.3-arbitrages/QUESTIONS-CATS.md`, format `- [ ] #N <question> — <briefing>`.
- **Arbitrage candidat** — fait **hors-sources**, Josian tranche de mémoire → **mini-ADR 1.3 `candidat`** + projecteur.
- **Faux flou sourcé** — fait **trouvé en couche 1** mais absent de la 2.2 → **injecter en 2.2** avec `[src: <report> §X]` (**pas** de 1.3) puis réaligner la fiche.

### 4. Résoudre & propager
- Item tranché → **retirer du FACTCHECK**. Il **disparaît** : ni ligne « Résolus », ni entrée barrée, ni traîne de compteurs — le pourquoi vit dans le message de commit. *(« Pas d'éléphant rose », CLAUDE.md racine §3.)*
- **Réaligner la fiche 3.x** si le verdict la change.
- **Commits scopés par fichier** (`git commit -m "…" -- <chemin>`) ; ne pas toucher aux fichiers d'autres agents.

## Mini-ADR / projecteur / injection 2.2
Tout est dans `1-sources/1.3-arbitrages/CLAUDE.md` (format mini-ADR, `provenance: candidat`, projecteur `2-consolide/outils/project_arbitrages.py`). **Lancer le projecteur après toute vague d'arbitrages.** Injection 2.2 = touche manuelle assumée (précédent : faux flou *cadrage-360*).
