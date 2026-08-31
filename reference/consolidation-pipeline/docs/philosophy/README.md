# 2-consolide/outils/docs/philosophy/ — le *pourquoi* du pipeline de consolidation

Le raisonnement derrière la spec : tradeoffs, risques résiduels, réalité mesurée. **À lire avant de changer une règle du prescriptif** ([../specs/](../specs/)).

Inversement, si tu ne fais qu'appliquer la spec (coder un script, exécuter une tâche), tu n'as pas besoin de ce dossier — va directement à `specs/`.

## Pages

| Fichier | Sujet |
|---|---|
| [map-reduce.md](map-reduce.md) | map-reduce & context-rot ; pourquoi le petit contexte est l'objectif ; scripts ⊃ état / agents ⊃ cognition ; pourquoi un registre tabulaire et pas un ledger |
| [gate-fidelite.md](gate-fidelite.md) | pourquoi le gate de fidélité remonte aux **sources** et pas aux fragments ; risque résiduel map vs reduce |
| [scoping.md](scoping.md) | doctrine de scoping (où couper) ; réalité mesurée (le deck 10739 l.) ; tradeoff idempotence ↔ coupe non déterministe |
| [orchestrateur.md](orchestrateur.md) | pourquoi l'orchestrateur est requis ; pourquoi un bandeau de monitoring ; le pattern log + marqueur terminal |
| [prompts.md](prompts.md) | pourquoi les prompts des sous-agents vont dans des fichiers dédiés (source unique) plutôt qu'inline dans le script ; le drift `ressources` qui l'a motivé |
