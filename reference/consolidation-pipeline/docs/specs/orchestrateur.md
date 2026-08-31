# Orchestrateur `2-consolide/outils/orchestrate.py`

Boucle qui fait tourner la pipeline sans intervention humaine : sélectionne les tâches via `task.py`, spawn un agent jetable par tâche, fait converger la validation. **Requis** dès qu'on sort du pilotage manuel (le walking skeleton S9 se pilote à la main). → *pourquoi requis (gate 2/2), pourquoi un bandeau* : `philosophy/orchestrateur.md`.

## Lancement — sous `caffeinate`

Le run est une boucle longue en background : si le laptop se met en veille, les agents en vol meurent et la pipeline cale. Lancer **toujours** sous `caffeinate -i` pour inhiber la veille le temps du run :

```
caffeinate -i 2-consolide/outils/orchestrate.py --slots 3 --max-agents 30
```

`caffeinate` s'arrête de lui-même quand `orchestrate.py` sort (drain terminé) — pas de process à tuer.

> **`claim_next` claime — réservé aux agents spawnés par l'orchestrateur.** Pour inspecter l'état avant ou pendant un run, utiliser `2-consolide/outils/task.py peek_next` (lecture seule) — **jamais** `claim_next`, qui claime et orpheline silencieusement la tâche de tête. Le bandeau de démarrage rappelle cette règle ([cli.md](cli.md) § Verbes).

> La forme exacte `caffeinate -i 2-consolide/outils/*.py …` est allowlistée dans `.claude/settings.json` (pas de prompt). N'introduis pas une autre flag (`-s`, `-d`…) ou un autre ordre d'arguments : la commande ne matcherait plus le pattern → prompt.

> **Modèle des workers pinné (`--model`, défaut `claude-opus-4-8`).** Les agents reduce/map sont spawnés avec `--model` **explicite** : sans ce pin, `claude -p` hériterait du défaut UI du lanceur (Fable 5 observé) → coût non déterministe selon le modèle de la session interactive. L'audit a son propre `--audit-model` (défaut `sonnet`), indépendant.

## Modèle d'exécution

- **1 agent = 1 session jetable = 1 tâche.** L'orchestrateur peuple un slot en spawnant un `claude -p` avec le prompt du rôle ; **c'est l'agent qui claime sa tâche** via `task.py claim_next --type <type>`. Le claim est porté par l'agent parce que son short doit devenir l'`owner` de la ligne — sinon `done`/`split` échouent leur garde `require_owner` ([cli.md](cli.md)), et le gate de fidélité ne pourrait pas distinguer auteur ↔ validateurs. L'agent travaille, finalise, sort ; l'orchestrateur relance un agent frais. Le plafond 1 tâche/session est porté par le CLI (§ Plafond par session). → *pourquoi jetable* : `philosophy/map-reduce.md`.
- **Invariant R1 — autorité de mutation.** Le seul mutateur de `tasks.csv` est `task.py`, sous flock ; jamais d'édition à la main (agent, humain ou orchestrateur). `task.py` est appelable par **deux chemins** : le **cycle normal** (verbes `claim_next`/`claim`/`done`/`split`/`approve`/`claim-correct`/`corrige`/`release`, appelés par les agents ; `peek_next` est l'inspection read-only, hors cycle de mutation) et un **chemin admin** réservé à l'orchestrateur — le seul force-release post-kill ([watchdog.md](watchdog.md) § 6). Pour l'ordonnancement, l'orchestrateur lit `tasks.csv` en seule lecture (choisir le rôle à spawn, détecter le drain) ; sa seule écriture est ce force-release admin, après un kill qu'il a décidé. Il possède l'ordonnancement, pas l'état.
- **Concurrence par slots, pas séquentiel.** L'orchestrateur maintient N slots ouverts en parallèle (un `claude -p` bloquant par slot, dans un `ThreadPoolExecutor`). Dès qu'un slot se libère, il **re-peek** l'état pour décider le rôle du prochain agent et le relance — refill continu jusqu'au drain ou au cap. Re-peek **par slot**, pas une fois pour toute la file : entre deux spawns l'état a bougé (claims, dones, oks), donc le rôle se recalcule à chaque slot libre. Priorité validation > production conservée (cf. § La boucle). → *pourquoi des slots et un budget* : `philosophy/orchestrateur.md` ; modèle de référence porté depuis `1-sources/outils/ressources/orchestrate.py`.

## Deux dimensions de cap (`--slots` / `--max-agents`)

Deux cadrans orthogonaux bornent un run (parité avec `1-sources/outils/ressources/`) :

- **`--slots N`** (défaut **3**, ≥ 1) — **concurrence** : combien d'agents tournent en même temps. Largeur du pipeline à l'instant *t*, limitée par le CPU, les collisions git (commits sérialisés) et le rate-limit. Quand un slot se libère, un nouvel agent le remplace.
- **`--max-agents N`** (défaut **10**, ≥ 1) — **budget total** : nombre cumulé d'agents lancés avant que l'orchestrateur cesse de lancer, peu importe la concurrence. Garde-fou contre une file qui ne se vide pas (p. ex. un enfant `validate` repassé `to_validate` 0/2 par des `corrigé` à répétition, re-validé sans fin, n'a pas de compteur dédié : c'est `--max-agents` qui le borne). Une fois le budget atteint : plus aucun lancement, puis drain propre des slots en cours.

`--slots 3 --max-agents 30` = 3 en parallèle, arrêt des lancements après 30 agents cumulés (ou avant si la file est vide).

### Anti-sur-spawn des validateurs (gate 2/2 **per-shard**)

La validation porte sur des **enfants** `validate:<clé>#n` d'un reduce shardé par sources (cf. [modele-donnees.md](modele-donnees.md), [validate.md](validate.md)) : chaque enfant porte son propre gate 2/2. `peek_schedule` rend le même enfant tant qu'il est `to_validate` et `owner` vide.

**Les 2 passes du gate sont séquentielles, pas concurrentes.** Une passe est **sérialisée par l'`owner`** du shard : `claim_next --type validate` pose `owner=<short>` et le garde jusqu'à l'`approve` (1er `ok:` → owner relâché, le shard reste `to_validate`). Tant qu'une passe tient l'owner, une 2ᵉ passe lancée en parallèle **ne peut pas claimer ce shard** : `claim_next` la fait diverger vers un autre shard (ou ne rend rien). Or l'orchestrateur suit `inflight_val` **par `id` de shard prédit** ; une divergence désynchronise ce suivi (le shard réellement claimé n'est pas celui compté). Lancer 2 passes concurrentes sur le même shard est donc **inutile et nuisible**, pas seulement « du gaspillage de tokens ». (La récup d'orphelin, elle, est indexée sur l'`owner` réel — scan `owner == short`, cf. [watchdog.md](watchdog.md) § 6 — et survit à une divergence.)

L'orchestrateur plafonne donc les validateurs en vol à **une passe par enfant** :

```
peek planifie validate:<clé>#n  ⟺  to_validate ∧ owner vide ∧ parent non verrouillé ∧ inflight_val(id) == 0
```

`inflight_val` (indexé par l'id `validate:<clé>#n`) compte les passes spawnées et pas encore moissonnées. Le filtre `owner` vide du peek exclut un shard déjà claimé ; `inflight_val == 0` couvre **en plus** la fenêtre spawn→claim, où l'agent n'a pas encore posé l'owner (sans quoi un 2ᵉ slot, voyant l'owner encore vide, re-spawnerait le même shard). Une fois la passe en vol moissonnée (1er `ok:` posé, owner relâché), le tour suivant replanifie le shard pour sa 2ᵉ passe — **séquentiellement**. Deux enfants distincts d'un même reduce sont schedulés indépendamment, et un même agent peut valider plusieurs shards (la distinctness est per-shard). Pour la production, même idée sous forme d'ensemble des `id` en vol : on ne re-spawn pas un agent sur une tâche déjà prise en charge par un agent vivant.

### Garde anti-boucle — `consecutive_empty` (≠ STALL_LIMIT par-flux)

Le modèle séquentiel S12 stoppait sur un **peek identique** répété (`STALL_LIMIT`) ; ces gardes restent dans `run_production`/`run_validation` (toujours testées). Le modèle slotté retient plutôt le `consecutive_empty` de `1-sources/outils/ressources/` :

- À chaque agent moissonné, on compare l'empreinte du CSV (`_state_fingerprint`) à celle du moissonnage précédent. Inchangée → l'agent n'a rien fait avancer (spawn « blanc » : crash avant claim, agent qui ne claime rien) → `consecutive_empty += `. Changée → progrès → remise à 0.
- À `consecutive_empty ≥ EMPTY_LIMIT` (5), on cesse de lancer et on draine.
- **Le gate 2/2 n'est jamais tué par cette garde** : deux passes successives sur le même reduce font progresser le bookkeeping (0→1 `ok:`, puis 1→2) → l'empreinte change à chaque passe → progrès, pas stall. C'est le piège que `STALL_LIMIT` sur l'identité du peek tendait (faux positif en validation, cf. R14) et que l'empreinte évite.
- Une boucle de corrections `corrigé → reset-all 0/2 → re-validate → corrigé` fait elle aussi changer l'empreinte à chaque tour (donc `consecutive_empty` ne la voit pas) : elle est bornée par **`--max-agents`**, son garde-fou désigné.

## La boucle — deux flux

L'orchestrateur **peek en lecture seule** `tasks.csv` pour savoir quel flux a du grain à moudre et quel rôle spawner ; le claim réel (sélection + transition sous flock, cf. [cli.md](cli.md) § Gating) est fait par l'agent via `claim_next`.

1. **Production** — s'il existe un `map`/`reduce` prenable (au peek), spawn l'agent du rôle. map vs scope : un `map` prenable en `note=oversize` route vers le prompt `scope`, sinon `map` (cf. [scoping.md](scoping.md)). L'agent claime (`claim_next --type map|reduce`), travaille, appelle `done`/`split`, sort. **Garde-fou de course** : si un autre agent a pris la tâche peeked entre-temps et que le claim atterrit sur un autre genre, le prompt vérifie `note=oversize` et `release` si le rôle ne correspond pas (cf. `prompts/map.md`, `prompts/scope.md`).
2. **Validation** — s'il existe un **enfant** `validate:<clé>#n` en `to_validate` (au peek), spawn un validateur ; l'agent claime sa passe (`claim_next --type validate`). Le gate exige **2 passes distinctes par shard** (cf. [validate.md](validate.md)) : l'orchestrateur respawn un validateur tant qu'un enfant reste `to_validate` avec de la capacité. La garde distinct-agent sous flock — et non l'orchestrateur — interdit au même short de valider deux fois le même shard ou de valider son propre consolidé ; deux sessions distinctes fournissent naturellement les 2 `ok:`. Quand **tous** les enfants d'un reduce sont `done`, l'`approve` qui complète le dernier rollup le parent `split→done` (cf. [validate.md](validate.md)).

**Ordonnancement slotté — production prioritaire, validation au drain.** Pour chaque slot libre, `peek_schedule` (read-only) décide en un seul passage : **d'abord** la prochaine tâche de production prenable non déjà en vol (`map`/`scope`/`reduce`), **sinon** un validateur si un **enfant** `validate:<clé>#n` `to_validate` a encore de la capacité (gate 2/2 per-shard, cf. § Anti-sur-spawn). Choix permanent (deadline V0 : produire tous les consolidés d'abord, valider ensuite) : la production n'est jamais « à sec » tant qu'il reste un map ou un reduce, donc les validations ne démarrent qu'au **drain de la production** — automatiquement, en un seul run, sans flag. Le reduce parent `split` n'est **jamais** planifié lui-même — ni validable (`type≠validate`) ni prenable (`status≠todo`) : il n'est donc jamais compté terminé, et le driver ne boucle pas dessus en attendant ses shards (le gate vit sur les enfants). Le rôle (`map`/`scope`/`reduce`/`validate`) en découle. L'orchestrateur remplit tous les slots libres, attend qu'au moins un agent finisse, moissonne, et refill.

**Drain.** Quand l'orchestrateur cesse de lancer — file vide (`peek_schedule → None`), `--max-agents` atteint, ou `consecutive_empty ≥ EMPTY_LIMIT` — il attend la fin propre des agents en vol avant de sortir : *drain = aucun agent ne tourne*. Aucun reduce ne doit rester `claimed`/`to_validate` orphelin du fait de l'orchestrateur : chaque agent en vol mène sa transition (`done`/`approve`/`corrige`/`release`) à terme via `task.py`. La pipeline est drainée quand `peek_schedule → None` **et** plus aucun agent ne tourne.

## Routage de la validation

`approve`/`corrige` sont appelés par le **validateur lui-même** (il rend le verdict) — l'orchestrateur ne décide rien sur le fond et ne claime pas à sa place. Son seul rôle : respawner des validateurs tant qu'un enfant `validate` attend des passes ; la distinctness des 2 validateurs est garantie par la garde sous flock du CLI, pas par lui. Cognition du validateur : pointeur `prompts/validate.md` (cf. [README.md](README.md) § Prompts). Un `approve` qui complète le 2/2 d'un enfant le passe `done`, puis **rollup** le parent `split→done` dès que tous les frères sont `done`. Un `corrige` (le validateur a édité le consolidé en place sous lease `correcting:` — correction du fait, ou flou ouvert inscrit en section `## Points flous` si l'ambiguïté n'est pas tranchable, cf. [validate.md](validate.md)) déclenche un **reset-all** : tous les enfants `validate` du reduce repartent `to_validate` 0/2 (`fix:<correcteur>` ajouté à la note), le parent **reste `split`** ; les frères reset sont re-planifiés au tour suivant via le même prédicat `peek_schedule`. **Plus aucune cascade nucléaire** : `corrige` remplace l'ancien `reject` (qui renvoyait le reduce en `todo`, refait de zéro). Une éventuelle boucle de corrections se borne par `--max-agents` (§ Deux dimensions de cap).

## Fabrication du prompt d'un agent

Pour chaque spawn, l'orchestrateur `cat` `2-consolide/outils/prompts/common.md` + `prompts/<rôle>.md` et passe le résultat à `claude -p`. **Aucun prompt inline** dans le script : source unique = les fichiers-prompts. → `philosophy/prompts.md`, [README.md](README.md) § Prompts.

## Bandeau de monitoring (obligatoire)

Sans dispositif, l'agent qui lance l'orchestrateur en background **n'est pas réveillé à sa fin** et se rabat sur un `sleep`/`until`/`wait` foreground — bloqué et aveugle. → *pourquoi + snippets* : `philosophy/orchestrateur.md`. L'orchestrateur **doit** donc :

- **Imprimer un bandeau au démarrage**, avant le 1er spawn : bloc « À L'AGENT QUI A LANCÉ CE SCRIPT » qui (a) interdit `sleep`/`until`/`wait` foreground et (b) donne la **commande exacte à coller dans l'outil `Monitor`** : `2-consolide/outils/watch.py <run-id>` (le run-id = nom du `<run>` dir).
- **Une ligne par event, flushée immédiatement** sur `stdout` (`print(..., flush=True)`) **et** dans `<run>/orchestrator.log` (`write` puis `flush()`) : config du run (`slots=… max_agents=…`), spawn d'un agent, fin (rc + durée + nb commits), kill (raison `reason=sliding|audit|cap`, cf. [watchdog.md](watchdog.md)), atteinte du budget / début de drain. En mode slotté les écritures concurrentes sont sérialisées (un verrou de log) pour qu'aucune ligne ne s'entrelace. Le log est ouvert en **append** : relancer l'orchestrateur avec le même run-id (même session) n'écrase pas l'historique du run précédent — une ligne « reprise du run … » sépare les deux (sans les sous-chaînes réservées « spawn » / « flags : »).
- **Clore sur un marqueur terminal déterministe** : dernière ligne du log = token stable et unique (p.ex. `flags : <chemin>`), seul signal « run fini » pour le moniteur.

## Contrat avec `Monitor`

L'outil `Monitor` poll le log en background (son `sleep` est légitime — il ne bloque pas l'agent) : il émet chaque nouvelle ligne au fil de l'eau et **sort dès le marqueur terminal**. La commande imprimée par le bandeau est `2-consolide/outils/watch.py <run-id>` (`2-consolide/outils/watch.py`) : un petit script qui streame les nouvelles lignes du log d'un run et sort sur le marqueur. Sans argument, il auto-détecte le run le plus récent. Il **remplace l'ancienne boucle shell inline** (`wc -l` + `sed -n` + `break`) : celle-ci portait le run-id dans le chemin → non allowlistable, elle re-promptait à chaque run. `watch.py` est couvert par `Bash(2-consolide/outils/*.py *)` → zéro prompt.

## Vues optionnelles

`render.py` (CSV → dashboard markdown) et le marquage `stale` (re-reduce après re-map) sont **optionnels**, à implémenter seulement à l'usage. → `philosophy/orchestrateur.md` § vues optionnelles.
