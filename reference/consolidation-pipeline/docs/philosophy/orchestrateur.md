# L'orchestrateur — pourquoi il est requis, et pourquoi un bandeau de monitoring

## Pourquoi l'orchestrateur n'est plus optionnel

Au départ, on hésitait : `orchestrate.py` dédié (comme `ressources`) ou picking manuel / `claim_next` en boucle ? Le **gate de fidélité 2/2 tranche** : il faut, par reduce, spawner 2 validateurs distincts et router leurs verdicts (`approve`/`corrige`). Un cycle à 3 agents par reduce (auteur + 2 validateurs), avec relances à la chaîne sous plafond 1-tâche/session, ne se pilote pas à la main. Une boucle qui fait tourner `claim_next` / `claim_next --type validate` + les agents est donc indispensable.

Le picking manuel est abandonné, sauf l'échappatoire `claim <id>` pour un cas ciblé.

## Boucles de corrections : surveillées, pas auto-coupées

Le `reject` nucléaire (reduce renvoyé en `todo`, consolidé refait de zéro) a été remplacé par la **correction en place** : un `corrige` édite le consolidé et **reset-all** les enfants `validate` à 0/2, sans compteur dédié. Volontaire : on ne veut pas qu'un seuil arbitraire abandonne un thème difficile. Une éventuelle boucle (`corrigé` → reset 0/2 → re-validé → `corrigé`…) se **surveille à l'œil dans les logs** de l'orchestrateur, et reste bornée par `--max-agents` ; Josian tranche s'il voit looper.

## Pourquoi un bandeau de monitoring (et pas juste « lancer le script »)

Problème concret du harness : l'agent qui lance un script multi-minutes en background **n'est pas réveillé à sa fin**. Sans dispositif, il se rabat sur un `sleep`/`until`/`wait` foreground — et se retrouve bloqué et aveugle : il ne voit rien avant la fin, et la fin ne le réveille pas. L'orchestrateur **doit** donc fournir un *bandeau de monitoring* qui rende le suivi observable sans bloquer l'agent.

Le pattern, autonome :

- **Une ligne par event, flushée immédiatement.** L'orchestrateur écrit une ligne par event significatif — lancement d'un agent, fin (rc + durée + nb de commits **de cet agent**, comptés via son short qui tague chaque commit — pas le delta global de `HEAD`, faux dès que plusieurs agents committent en parallèle sur le même historique), kill (watchdog/cap), début de drain — à la fois sur `stdout` (`print(..., flush=True)`) **et** dans `orchestrator.log` (`write` puis `flush()` à chaque ligne). Le flush est obligatoire : sans lui, un run backgroundé n'affiche rien avant sa fin.
- **Clore sur un marqueur terminal déterministe.** La toute dernière ligne du log porte un token stable et unique (p.ex. `flags : <chemin>`). C'est lui qui signale « run fini » au moniteur ; sans marqueur, un suivi de log ne se termine jamais.
- **Imprimer le bandeau au démarrage**, avant le premier agent : un bloc « À L'AGENT QUI A LANCÉ CE SCRIPT » qui (a) **interdit explicitement** `sleep`/`until`/`wait` foreground et (b) donne la **commande exacte à coller dans l'outil `Monitor`** : `2-consolide/outils/watch.py <run-id>`. Le `Monitor` poll en background (son `sleep` est légitime — il ne bloque pas l'agent), émet chaque ligne nouvelle au fil de l'eau, et **sort** dès le marqueur terminal.

  `watch.py` fait exactement ce que faisait l'ancienne boucle shell inline — compter les lignes, émettre les nouvelles, `break` dès que la dernière ligne matche le marqueur terminal :

  ```
  L=<run>/orchestrator.log; n=0; while :; do \
    t=$(wc -l <"$L" 2>/dev/null||echo 0); \
    [ "$t" -gt "$n" ] && { sed -n "$((n+1)),${t}p" "$L"; n=$t; }; \
    tail -n1 "$L" 2>/dev/null | grep -q "flags :" && break; \
    sleep 2; done
  ```

  Mais cette boucle inline **re-promptait à chaque run** : son chemin porte le run-id (qui change), et un one-liner ad-hoc n'est pas allowlistable. `watch.py <run-id>` est un appel `2-consolide/outils/*.py` couvert par l'allowlist → zéro prompt.

## Vues optionnelles (à l'usage)

- `render.py` (CSV → dashboard markdown lisible) : optionnel, si on veut un coup d'œil rapide hors `git log`.
- Marquage `stale` (un fragment re-mappé après un reduce → re-reduce) : à implémenter seulement si on constate des re-reduce manqués.
