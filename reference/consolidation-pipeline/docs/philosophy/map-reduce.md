# Map-reduce & context-rot — pourquoi cette forme

## L'objectif premier : garder chaque session à petit contexte

Tout le design découle d'un seul constat : **les agents se dégradent bien avant la limite de fenêtre**. Le « context-rot » mord nettement avant 1M tokens — empiriquement, la qualité chute déjà autour de ~100k tokens chargés, et l'idéal de travail tourne plutôt autour de ~60k tokens par session. On ne cherche donc pas à *tenir* dans la fenêtre : on cherche à charger **le moins possible** à chaque session.

Map-reduce, avec une couche intermédiaire **1.5 (fragments)** entre sources (couche 1) et consolidé (couche 2), sert exactement ça :

- **Map** ne charge qu'une seule source ; sa sortie est distillée (≪ la source).
- **Reduce** ne charge que des fragments déjà distillés, jamais le corpus brut.
- L'agent ne charge **jamais** `tasks.csv` : le CLI ne lui rend que sa ligne.

Sans la couche 1.5, le reduce devrait relire les sources brutes de tous les fragments d'un thème → explosion de contexte. Les fragments sont le tampon qui absorbe le volume.

## Sessions jetables + plafond 1 tâche

Conséquence directe : **une session = une tâche, puis exit**. Un agent prend une seule tâche, la termine, sort ; l'orchestrateur en relance un frais pour la suivante. On ne laisse jamais un agent accumuler le contexte de plusieurs tâches — c'est ce qui le ferait pourrir. Le plafond 1 (cf. `specs/cli.md`) n'est pas une bride de débit, c'est l'application directe de la doctrine petit-contexte.

## Scripts ⊃ état, agents ⊃ cognition

**Les scripts possèdent l'état, les agents possèdent la cognition.** Un agent n'édite jamais l'état à la main : il appelle le CLI (`next/claim/done/split/release`, + `validate/approve/reject`), fait son travail cognitif, écrit son artefact, et le CLI vérifie + commit.

Pourquoi cette frontière nette : l'état (qui détient quoi, dans quel statut) demande des garanties déterministes — sérialisation par `flock`, transitions atomiques, pas de race. C'est le métier d'un script, pas d'un agent (qui hallucine, oublie, part en boucle). La cognition (distiller un fait, décider d'une coupe, juger une fidélité) demande l'inverse : du jugement, pas du déterminisme. On range chaque chose du bon côté.

## Pourquoi un registre tabulaire, pas un ledger

L'état vit dans **`2-consolide/outils/tasks.csv`** : lignes **mutées sur place**, une par tâche. Pas un ledger append-only, pas des tables markdown-as-DB.

- **Borné par construction** : 1 ligne/tâche, mutée. Le CSV ne grandit pas avec l'activité — contrairement à un ledger qui accumulerait un événement par transition et finirait par peser lourd à parser, à l'encontre de l'objectif petit-contexte.
- **La trace existe déjà ailleurs** : chaque claim/done/split étant un commit, `git log -- 2-consolide/outils/tasks.csv` *est* la trace. Dupliquer l'historique dans un ledger serait redondant.
- **Lu/écrit via le module `csv`** (quoting correct) — un split manuel sur `,` casserait dès qu'un champ `note` contient une virgule.
