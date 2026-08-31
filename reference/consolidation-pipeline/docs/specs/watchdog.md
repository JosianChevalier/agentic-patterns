# Watchdog & auditabilité — spec

> **Implémentation de référence : `1-sources/outils/ressources/orchestrate.py`** (+ `release.py`).
> Le watchdog 3 couches, le digest d'audit et le force-release post-kill **tournent
> déjà en prod côté `ressources`**. Cette spec les **porte** dans la pipeline de
> consolidation (`2-consolide/outils/`) — **porter, ne pas redessiner**. Les seules
> adaptations sont les spécificités consolide (cibles, rôles, pas de gros base64
> image).

## 1. Le problème — rabbit-hole, et une référence pendante

L'orchestrateur (`2-consolide/outils/orchestrate.py`, S13 complet) n'a **qu'un**
garde-temps : un cap dur par agent (`spawn_capped`, `DEFAULT_CAP_S`).

Le cap dur **n'attrape pas un rabbit-hole**. Un agent qui part en vrille
(fabrique un script hors tâche, retente une commande refusée en boucle,
sur-vérifie un claim) produit du log en continu : ni le cap (il finit par
le tuer, mais après 5 min de gâchis) ni un simple watchdog d'inactivité ne le
voient. **Seul un audit sémantique** de ce qu'il fait le distingue d'un agent
qui progresse. `1-sources/outils/ressources/orchestrate.py` a ce modèle complet à 3
couches ; consolide ne l'a pas encore porté.

**Référence pendante.** `orchestrateur.md` parle de « kill (watchdog/cap) »,
mais « watchdog » n'était défini nulle part dans la spec. Ce document le
définit (§ 3) et la référence pointe désormais ici (§ 7).

## 2. Invariant R1 — autorité de mutation (reformulé)

Le seul mutateur de `tasks.csv` est `task.py`, sous flock. Personne n'édite
le fichier à la main (ni agent, ni humain, ni orchestrateur). `task.py` est
appelable par **deux chemins** :

- **cycle normal** — appelé par les agents jetables (`claim_next`/`claim`/`done`/
  `split`/`approve`/`claim-correct`/`corrige`/`release`) ; c'est par là
  que passent toutes les transitions métier ;
- **chemin admin** — un flag réservé à l'orchestrateur pour le seul
  force-release post-kill (§ 6), calqué sur `release.py --force-abandon-orphan`.

R1 ne dit donc **pas** « l'orchestrateur n'appelle jamais de verbe mutant » : il
dit **toute mutation passe par `task.py` sous flock, jamais d'édition à la
main**. L'orchestrateur reste read-only sur l'ordonnancement (peek du CSV
pour choisir le rôle, détecter le drain) ; sa seule écriture autorisée est
le force-release admin, et uniquement après un kill qu'il a lui-même décidé.

> Options écartées pour le force-release : reaper (spawn jetable dédié — coûte
> un spawn/kill), lease/TTL (horloge dans le gating `task.py`, blast radius
> S7), statu quo (gèle le gate 2/2 d'un reduce orphelin). Le chemin admin
> (parité `ressources`) est retenu — tranché.

## 3. Le watchdog 3 couches

Porté de `ressources`, recalibré pour des tâches consolide (prose bornée : un
`map`/`reduce`/`validate` = 1 claim borné, lecture de quelques rapports/fragments,
finalise, sort — ~1 à 3 min, pas de gros base64 image à lire).

| Couche | Détecte | Mécanisme (fonction de réf.) | Verdict |
|---|---|---|---|
| **1. Sliding-inactivity** | agent mort / silencieux / bloqué | aucun append au JSONL depuis `--sliding-inactivity` s (`mtime` du log, cf. poll loop `check_agent_deadline`) | kill direct |
| **2. Audit sémantique** | **rabbit-hole** (log mais hors tâche / boucle) | `claude -p` sonnet qui lit un **digest** du JSONL (`build_audit_digest` + `_summarize_event`) → verdict (`parse_audit_result`) | kill / **continue par défaut** (erreur/timeout/unparseable) |
| **3. Cap absolu** | filet de sécurité ultime | dépassement de `--cap` s | kill systématique |

**Le « watchdog » = ces 3 couches réunies.** Le cap dur existant (couche 3) en
fait déjà partie ; on ajoute les couches 1 et 2.

### Valeurs (défauts calibrables au 1er run réel)

Posées comme défauts, calibrés au 1er run (comme le placeholder de cap
côté `ressources`) :

| Réglage | `ressources` | **consolide** | Justification |
|---|---|---|---|
| `--sliding-inactivity` | 180 s | **120 s** | pas de read d'images longues (le 180 s de `ressources` tolérait des PNG) ; 2 min sans event = agent planté. |
| `--audit-after` | 300 s | **150 s** | une tâche normale finit en ~1-3 min ; auditer **au-delà** → seuls les retardataires le sont (coût quasi nul, cf. § 8). |
| `--audit-interval` | 60 s | **60 s** | inchangé. |
| `--cap` | 600 s | **300 s** *(déjà en place, commit a0e35a5)* | 5 min = large filet pour une tâche bornée. |
| `--audit-model` | sonnet | **sonnet** | l'audit tranche kill/continue sur un digest ; un faux kill détruit du travail en vol → on prend sonnet (parité `ressources`), le jugement prime sur le coût (§ 8). |
| `--no-audit` | — | flag, **audit actif par défaut** | désactive la couche 2 (couches 1+3 seules) pour un run zéro-token d'audit. |

### Digest et prompt d'audit

`build_audit_digest` / `_summarize_event` se portent **tels quels** (compteurs
globaux + N derniers events, base64/images retirés par sûreté même si consolide
n'en produit pas). Le prompt d'audit vit en **fichier** (`prompts/audit.md`, R4 —
aucun inline). Sa cognition est adaptée à consolide :

- **marqueurs de dérive** : `Write`/`Edit` hors `2-consolide/2.1-fragments/` ou hors le
  `<theme>.md` ciblé ; `Bash` hors allowlist retenté en boucle (`tool_result
  ERROR` répétés) ; `git log`/`grep` de sur-vérification après un claim réussi ;
  beaucoup de `tool_use` sans `task.py claim_next` réussi ;
- **pas de plafond « K livrables/claim »** : spécificité `ressources`
  (Triage/Transcribe). Une tâche consolide = un seul artefact → `compute_ceiling_check`
  n'est pas transposé (le critère tombe).

### Kill

Signal au **process group** entier (`kill_tree` : `os.killpg(SIGKILL)`, fallback
`proc.kill()`) — l'agent **et** ses sous-process (`task.py`, `git`). Suppose le
spawn lancé `Popen(start_new_session=True)`. Chaque kill est loggé avec une
**raison explicite** : `reason=sliding|audit|cap` (aujourd'hui un kill cap est
`tag=kill` sans cause distincte).

## 4. Plomberie log par-agent — prérequis commun

Aujourd'hui `spawn_capped` fait `Popen` sans transcript exploitable par couche.
Sliding (1), audit (2) et auditabilité (§ 5) lisent **tous** un JSONL streamé.
C'est le premier chantier (S14). À câbler dans le spawn réel :

- `--output-format stream-json --verbose` sur le `claude -p` de l'agent ;
- `stdout`/`stderr` redirigés vers `<run>/agent-<role>-<id>-<n>.jsonl`
  (`<n>` = compteur de spawn, distingue 2 agents sur la même tâche après un
  reset-all `corrigé` qui re-planifie un frère `validate`) ;
- chaque event flushé en JSONL temps réel → relisible par le poll loop **et**
  conservé après le run.

`orchestrator.log` reste **1 ligne/event** (config, spawn, end/kill avec
`reason=`, drain, marqueur terminal), flushée `stdout`+fichier, sérialisée par
`_LOG_LOCK` (déjà en place). Le contrat `spawn(role, task_id)` ne change pas :
seul le corps du spawn réel évolue.

## 5. Auditabilité a posteriori

Tout vit dans le **run dir** `2-consolide/outils/.orchestrator/<id>/` (gitignored,
tranché S12e Q4 ; même rôle que `1-sources/outils/ressources/runs/<ts>/`).
L'orchestrateur n'y fait que de l'I/O fichier — **aucun git** sur le run dir,
donc R1 intact.

| Artefact | Contenu | Rétention |
|---|---|---|
| `orchestrator.log` *(existe)* | 1 ligne/event : config, spawn, end/kill (rc+durée+commits+**`reason=`**), drain, marqueur terminal | gardé |
| `agent-<role>-<id>-<n>.jsonl` *(S14)* | transcript stream-json complet de chaque agent | gardé |
| `audit-<role>-<id>-<n>.log` *(S17)* | digest envoyé + verdict (kill/continue) + justification, par audit | gardé |
| `RUN.md` *(S15, équivalent `FLAGS.md`)* | résumé de fin de run (ci-dessous) | gardé |

`RUN.md` est écrit **en dernier** (avant le marqueur terminal), par `scan_*`
analogue à `scan_flags`, listant :

- **agents tués** : `<role> <id>` + `reason` (sliding/audit/cap) + lien JSONL + audit log ;
- **orphelins résiduels** : tâches restées `claimed`/`to_validate` avec `owner` set
  en fin de run (lecture seule du CSV) — devrait être vide si § 6 fait son travail ;
- **budget** : `launched`/`max_agents`, raison d'arrêt (drain/budget/empty).

**Rétention (D4).** Tout reste gitignored (forensique locale post-run, comme
`ressources`) et **purgeable une fois le run exploité** (`rm -rf` du run dir —
les vieux runs polluent les greps shell sur le disque). `RUN.md`/`FLAGS.md` sont générés en fin de run ; **reprise du même
run-id** → le nouveau résumé est **appendu** (séparateur `---`), comme
`orchestrator.log` (ouvert en append, séparateur de reprise) : l'historique d'un
run ne s'écrase jamais. Une **promotion
versionnée** (digest slim sous `2-consolide/runs/<id>.md`) est optionnelle, hors
orchestrateur (Josian, ou un `promote-run.py` dédié appelé à la main) — non
requise : l'orchestrateur ne commit jamais.

## 6. Orphan-release post-kill — chemin admin (D1)

**Le problème.** Quand le watchdog tue un agent, son verrou reste : `owner` set,
tâche orpheline. Deux cas :

- **orphelin `claimed`** (map/scope/reduce tué) : `status=claimed, owner=X`.
- **orphelin `to_validate`** (validateur tué après `claim_next --type validate`) :
  `status=to_validate, owner=X`. Aucun verbe actuel ne le nettoie, et il gèle
  le gate 2/2 de ce reduce pour le reste du run.

**La solution — chemin admin sur `task.py`, calqué sur `release.py
--force-abandon-orphan`.** `force_release_abandon()` côté `ressources` fait ça :
l'orchestrateur appelle `release.py --force-abandon-orphan <short>
<step> <slug> abandon`, qui prend le flock, bypasse la garde « tu dois posséder le
lock » mais vérifie que le verrou appartient bien à `<short>` (l'agent tué),
reset la cellule, commit scopé au seul fichier d'état. À porter dans `task.py` :

- **verbe/flag admin** : `task.py release --force-orphan <short> <id> [--reason kill:<reason>]`
  (ou un flag `--force-orphan <short>` sur `release`). Réservé à l'orchestrateur ;
- **garde** : ne reset que si la ligne `<id>` a `owner == <short>` (le short de
  l'agent tué) ; sinon no-op loggé, **rc dédié** (`FORCE_ORPHAN_NOOP_RC`, ≠ 0) —
  l'orchestrateur logge `recovered` / `no-op` / `FAIL rc=` distinctement, un « ok »
  uniforme masquerait un orphelin encore tenu (l'agent a pu release juste avant le
  kill — pas de TOCTOU car tout est **sous le flock `.consolide.lock`**) ;
- **transition** : orphelin de production `claimed`→`todo` ; orphelin de
  validation : l'enfant **reste `to_validate`** (re-prenable), gate ramené 0/2
  (note → `author:` seul) — le repasser `todo` le **gèlerait** (`is_validatable`
  exige `to_validate`). Dans les deux cas `owner`/`claimed_at`/bookkeeping de
  passe en cours effacés, `output` préservé ;
- **commit scopé** : `git commit -- 2-consolide/outils/tasks.csv` **uniquement** (ne stage
  jamais l'artefact ni un dossier — leçon `release.py` ll. 313-323 : un pathspec
  sur un dir untracked fait planter le commit) ;
- **best-effort** : log + continue si le commit échoue (lock git transient,
  pre-commit) ; l'orphelin sera nettoyé au run suivant ou à la main.

C'est l'orchestrateur qui appelle ce chemin, immédiatement après le kill, en
réutilisant le short de l'agent (détecté par `detect_short_sha` / `ensure_short`
sur le JSONL, comme `ressources`). Conforme à R1 : la mutation passe
par `task.py` sous flock, pas par une édition à la main.

**La récup s'indexe sur l'`owner`, jamais sur le label de spawn.** La tâche pour
laquelle un agent a été spawné n'est qu'une *prédiction* du peek : l'agent claime
via `claim_next` et peut tenir une **autre** tâche (course entre slots). Checker le
label laisserait la tâche réellement tenue orpheline (owner fantôme, gate gelé)
pendant que le label — owner vide — donne un faux no-op. L'orchestrateur scanne donc
`tasks.csv` sur `owner == short` (les deux statuts `claimed`/`to_validate`, 0, 1 ou
plusieurs lignes) et force-release chaque ligne trouvée. Short introuvable (JSONL
absent/illisible) → on ne sait pas ce que l'agent tenait : log + skip best-effort
sur le label, l'orphelin sera repris au run suivant ou à la main.

## 7. Réparation de la référence pendante « watchdog »

`orchestrateur.md` (« kill (watchdog/cap) ») **pointe désormais vers ce fichier**
(§ 3, les 3 couches). Le commentaire de `DEFAULT_CAP_S` dans `orchestrate.py` qui
signalait la lacune (« conception à venir ») sera mis à jour pour pointer cette
spec au moment de l'impl (S16/S17). Plus de terme défini nulle part.

## 8. Coût

L'audit = des `claude -p` supplémentaires, maîtrisés par construction :

- `--audit-after=150 s` **au-delà** de la fenêtre normale (1-3 min) → la plupart
  des agents ne sont jamais audités ; seuls les retardataires/rabbit-holes le
  déclenchent ;
- `--audit-model=sonnet` → coût unitaire maîtrisé car l'audit ne se déclenche que
  sur ces rares retardataires, pas à chaque agent ;
- `main()` **refuse déjà** de lancer si `ANTHROPIC_API_KEY` est set (parité
  `ressources`, anti-facturation) — inchangé ;
- `--no-audit` coupe la couche 2 (couches 1+3 seules) pour zéro token d'audit.

Borne de process : avec `--slots S`, au pire `S` agents + `S` audits = `2·S`
`claude -p` simultanés. Borné, acceptable.

## 9. Architecture — la « 3ᵉ voie » (ThreadPool intact)

Le `run()` slotté (S13) est un `ThreadPoolExecutor` où chaque worker **bloque**
sur `spawn(role, task_id)` ; ce contrat est porté par tous les tests S12/S13
(fakes in-process). L'audit doit inspecter l'agent en vol — incompatible avec
un thread qui bloque sur un `subprocess.run` opaque.

**On garde le ThreadPool intact.** Le seul changement est dans le spawn réel
(`spawn_capped` → un spawn auto-pollant), qui tourne déjà dans le worker : au lieu
d'un `Popen`+`wait(timeout)` opaque, il fait `Popen(start_new_session=True)` + une
**boucle de poll interne** qui, tant que l'agent vit :

1. relit le JSONL streamé (sliding-inactivity, couche 1) ;
2. à `audit-after` puis tous les `audit-interval`, forke un audit `claude -p`, lit
   son verdict (couche 2) ;
3. applique le cap (couche 3) ;
4. **kill** (`kill_tree`) + force-release admin (§ 6) si une couche le décide.

La fonction **reste bloquante côté thread** → le contrat `spawn(role, task_id)`
est inchangé, les fakes in-process ne le voient pas → zéro régression S12.
Chaque worker surveille son agent. Le kill reste exercé sur le vrai
subprocess (comme `spawn_capped` aujourd'hui), pas via les fakes — discipline
de test S12 préservée.
