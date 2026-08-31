# Prompts des sous-agents — pourquoi des fichiers dédiés

## Le constat (apprentissage `1-sources/outils/ressources/`)

Dans `1-sources/outils/ressources/orchestrate.py`, le prompt passé aux sous-agents est un littéral Python (`SUBAGENT_PROMPT`, ~130 lignes). Il re-décrit le protocole — plafonds par claim, choix de cellule au hasard, posture face au doute, restrictions git, permissions headless — qui vit **déjà** dans `RESSOURCES_PROTOCOL.md`. Et il dit en plus à l'agent « Lis `RESSOURCES_PROTOCOL.md` ».

Deux sources pour une même règle ⟹ **drift** : on corrige un plafond dans le `.md`, on oublie le string Python (ou l'inverse), et l'agent reçoit une consigne périmée. Laquelle fait foi devient ambigu.

## La décision

**Un fragment de consigne destiné aux agents est écrit une seule fois**, dans un fichier-prompt dédié. Deux consommateurs, une source :

- le **script d'orchestration** `cat` les fichiers pour fabriquer le prompt de `claude -p` ;
- la **spec** (`2-consolide/outils/docs/specs/`) les référence par chemin au lieu de les recopier — un `.md` de spec joue le rôle de carte (« la cognition du validateur est dans `prompts/validate.md` »), pas de copie.

## Découpe : `common.md` + 1 fichier / rôle

- `common.md` : ce qui est identique pour tous (plafond 1 tâche/session, pas de 2ᵉ claim, git via CLI seulement, allowlist headless, posture face au doute). Cat'é en tête de chaque prompt.
- un fichier par rôle (`map`, `reduce`, `validate`, `scope`) : la cognition propre. C'est exactement ce que `specs/validate.md` (§ travail du validateur) et `specs/scoping.md` (§ l'agent de scoping) décrivent aujourd'hui — au build, ce contenu **migre** dans le fichier-prompt, et la spec n'en garde que le pointeur + les mécaniques que le *script* enforce (gating, transitions CSV, commits).

La ligne de partage : **le fichier-prompt = ce qu'on dit à un agent ; la spec = ce que le système contraint** (CLI, états, flock, formats). Ce qui relevait des deux était précisément ce qui dérivait.

## Tradeoff accepté

Lire la spec seule ne suffit plus à connaître le texte exact envoyé aux agents — il faut ouvrir les fichiers-prompts. On l'accepte : la spec reste la carte, les prompts restent le territoire, et il n'y a plus deux territoires contradictoires.
