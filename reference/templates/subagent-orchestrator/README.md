# Template — orchestrateur de sous-agents `claude -p`

Patron pour faire **drainer une queue de tâches** (gérée par un `claim.py` /
`release.py` de type [`file-validation/`](../file-validation/README.md)) en
lançant N sous-agents `claude -p` en parallèle. Chaque sous-agent fait UNE
itération du pipeline puis sort. L'orchestrateur relance dès qu'un slot se
libère, supervise les agents bloqués via un **watchdog 3 couches**, et produit
un `FLAGS.md` en fin de run.

**Instance vivante** (référence concrète) : `1-sources/outils/ressources/orchestrate.py`.
Quand tu hésites sur un point qui n'est pas couvert ici, va lire le source.

## Quand utiliser ce template

Tu en as besoin si :

- Tu as déjà un `TODO.md` + `claim.py` / `release.py` qui marchent en mode
  un-agent-à-la-fois (cf. skill [`file-validation/`](../file-validation/README.md)).
- Tu veux **multiplier le débit** en lançant plusieurs sous-agents `claude -p`
  en parallèle, sans les surveiller à la main.
- Tu acceptes que les sous-agents soient **headless** (pas de retour interactif
  — tout doute doit passer par un `signalé <raison>`).

Tu n'en as **pas** besoin si :

- Une seule session Claude Code suffit (queue petite, tâches longues mais peu
  nombreuses).
- Les tâches ne sont pas indépendantes (un agent doit attendre la sortie d'un
  autre → tu cherches un pipeline DAG, pas un pool).

## Interdépendance avec `file-validation/`

Ce template **ne fonctionne pas seul**. Il suppose qu'un `claim.py` /
`release.py` côté domaine :

1. **Sérialise** les transitions via `flock` (sinon deux sous-agents se
   marchent dessus sur la même ligne du TODO).
2. **Choisit la tâche côté script** (`claim.py next`), qui imprime
   `TASK: <step> <slug>`. C'est le contrat que lit le `SUBAGENT_PROMPT` : le
   sous-agent appelle `next`, exécute ce qu'on lui donne, ne choisit jamais.
3. **Inclut le `<short>` du session id** dans le sujet de chaque commit, sous
   la forme `Claim <step> <slug> (<short>)` et un release estampillé `(<short>)`.
   L'orchestrateur grepe ces sujets pour attribuer les commits à un agent et
   détecter les claims orphelins après crash.
4. Expose **`release.py --force-abandon-orphan <short>`** pour libérer un
   verrou sans posséder la session — appelé par l'orchestrateur quand il kill
   un agent.

Les exigences 1-3 sont **dans le template de base** [`file-validation/`](../file-validation/README.md)
(le `next`, le stamp `<short>` et les gardes par session sont désormais core) :
il est branchable tel quel. Seul **`--force-abandon-orphan`** (exigence 4)
reste une variante à ajouter — voir la "Variantes connues" de `file-validation/`
et l'implémentation de référence `1-sources/outils/ressources/release.py`.

## Le pattern

Un **orchestrateur** (Python, processus parent) :

1. Lit le `TODO.md` pour vérifier qu'il reste du travail.
2. Lance jusqu'à `--slots` sous-agents `claude -p` en parallèle.
3. Chaque sous-agent demande UNE tâche au script (`claim.py next`), qui la
   choisit et la réserve sous flock, puis l'exécute (lire `TASK:` → travail →
   release → sortie). **Le sous-agent ne choisit pas sa cellule** — c'est ce
   qui élimine les courses de sélection (deux agents ne peuvent pas recevoir la
   même ligne) et les claims qui échouent. Le prompt précise aussi "tu ne fais
   qu'UNE tâche, l'orchestrateur s'occupe du volume" pour neutraliser les
   plafonds par-session du protocole de domaine.
4. Quand un sous-agent sort : l'orchestrateur compte ses commits, détecte les
   éventuels claims orphelins (Claim sans Release matchant), force le release
   en `abandon` si besoin, et relance un nouveau slot.
5. S'arrête au cap absolu `--max-agents` (budget total cumulé), ou si 2
   sous-agents consécutifs sortent sans commit (= queue vide).

### `--slots` vs `--max-agents` — deux dimensions orthogonales

Ne pas les confondre :

- `--slots` = **concurrence** (largeur du pipeline à un instant t). Combien
  d'agents tournent *en même temps*. Limité par CPU, conflits git, rate-limit
  Claude. À chaque slot libéré → relance (si budget restant).
- `--max-agents` = **budget total** sur tout le run. Nombre cumulé de
  lancements avant arrêt, peu importe la concurrence. Garde-fou contre une
  queue qui ne se viderait jamais.

Exemple : `--slots 3 --max-agents 30` → 3 agents en parallèle, run stoppe à
30 lancements cumulés (ou avant si queue vide). Penser `--max-agents` ≈
« combien de tâches *au maximum* je veux que ce run traite ».

## Lifecycle d'un run

```
<couche>/outils/<DOMAINE>/orchestrate.py
   │
   ├── crée <couche>/outils/<DOMAINE>/runs/<ts>/
   ├── garde anti-facturation : refuse si ANTHROPIC_API_KEY set
   ├── vérifie queue_has_work() → exit si rien à faire
   │
   ├── boucle scheduler
   │     ├── remplit les slots (jusqu'à --slots agents en parallèle)
   │     ├── pour chaque agent : claude -p --output-format stream-json --verbose
   │     │     → log JSONL en temps réel dans agent-NN.log
   │     │     → start_new_session=True (pour kill du process group entier)
   │     ├── poll(2s) → check_agent_deadline() applique le watchdog 3 couches
   │     ├── harvest() un agent sorti :
   │     │     - extrait son short_sha depuis l'init event du log
   │     │     - filtre les commits par short_sha
   │     │     - détecte orphan claims → force_release_abandon()
   │     │     - met à jour consecutive_empty
   │     └── stop si consecutive_empty ≥ 2 OU launched ≥ --max-agents
   │
   ├── drain : attend la sortie des agents restants (même watchdog actif)
   │
   └── scan_flags() → écrit FLAGS.md du run
```

## Watchdog 3 couches

Trois mécanismes indépendants pour décider qu'un agent doit être tué. Le **kill
fait toujours un SIGKILL du process group entier** (`os.killpg(SIGKILL)`) — pas
de SIGTERM, parce que `claude -p` peut spawn des subprocess (claim.py, release.py,
extractions lourdes…) qu'il faut tous arrêter.

### 1. Sliding watchdog — détection silencieuse

Default : `--sliding-inactivity 180s`.

Regarde le `mtime` du log JSONL **et** du heartbeat (sous `$TMPDIR/<projet>/orchestrate/<run_ts>/agent-NN.heartbeat`).
Si **aucun des deux** n'a bougé depuis `N` secondes → kill.

- Le log JSONL est appendé à chaque event Claude (tool_use, tool_result, text).
  Tant qu'un agent vit, ça bouge.
- Le heartbeat sert pour les scripts du domaine qui font des bursts longs
  (extraction d'un gros PPTX, conversion vidéo…) où la stdout est bufferisée
  par le Bash tool et le log JSONL ne bouge pas pendant 30s+. Le script du
  domaine peut `touch $ORCHESTRATE_HEARTBEAT` régulièrement pour dire "je
  travaille". L'orchestrateur pose `ORCHESTRATE_HEARTBEAT` dans l'env du
  sous-agent — c'est au script du domaine de l'utiliser (optionnel).

#### Snippet côté script du domaine — heartbeat 30s

Cas d'usage : tu écris un script Python (ou autre) appelé par le sous-agent
via `Bash`, qui peut tourner > `--sliding-inactivity` (default 180s) sans
imprimer une seule ligne — extraction binaire lourde, conversion média,
téléchargement, calcul long. Sans heartbeat, le sliding watchdog va tuer le
sous-agent en plein milieu de la tâche.

**Contrat** (à respecter quel que soit le langage) :

- Lire l'env var `ORCHESTRATE_HEARTBEAT`. **No-op si absente** — le script doit
  rester utilisable hors orchestrateur, en CLI ou en test.
- Toucher le path indiqué (mtime suffit, pas besoin d'écrire) toutes les ~30s
  depuis un **thread/processus daemon** qui meurt avec le script principal.
- Wrapper le `touch` dans un `try/except` qui avale toute erreur I/O — un bug
  dans le heartbeat ne doit jamais faire échouer la tâche métier.
- Démarrer le heartbeat **dans `main()`, avant la tâche longue**, après le
  parsing des args mais avant le travail réel.

**Implémentation Python de référence** (copiable depuis `1-sources/outils/ressources/extract.py`) :

```python
import os
import threading
import time
from pathlib import Path


def _start_heartbeat() -> None:
    """If ORCHESTRATE_HEARTBEAT is set, touch that file every 30s in a daemon thread.

    Lets orchestrate.py's sliding watchdog see that a long-running task is
    still alive even when the parent claude -p agent is blocked waiting on the
    Bash tool result (which buffers stdout until completion, freezing the JSONL
    log mtime). No-op when the env var is empty/absent — script stays
    standalone-usable. Daemon thread, dies with the process; touch wrapped in
    try/except so a heartbeat bug never fails the task.
    """
    path = os.environ.get("ORCHESTRATE_HEARTBEAT")
    if not path:
        return
    hb = Path(path)

    def beat() -> None:
        while True:
            try:
                hb.touch(exist_ok=True)
            except OSError:
                pass
            time.sleep(30)

    threading.Thread(target=beat, daemon=True).start()


def main() -> int:
    args = parse_args()
    _start_heartbeat()   # ← juste avant le travail long
    return do_work(args)
```

**Pourquoi 30s** : largement < `--sliding-inactivity` (180s par défaut), donc
6× de marge avant qu'une latence I/O ne déclenche un faux kill. Ne pas
descendre sous 5s sauf raison précise — ça pollue le filesystem pour rien.

**Variante shell** (script bash long lancé par le sous-agent) :

```bash
if [ -n "$ORCHESTRATE_HEARTBEAT" ]; then
  ( while :; do touch "$ORCHESTRATE_HEARTBEAT" 2>/dev/null; sleep 30; done ) &
  trap "kill $! 2>/dev/null" EXIT
fi
```

Même contrat : no-op si env var absente, background process tué en sortie.

### 2. Audit-agent intermédiaire — détection sémantique

Defaults : `--audit-after 300s`, `--audit-interval 60s`, `--audit-model sonnet`,
`--audit-timeout 90s`.

À partir de `--audit-after` secondes, l'orchestrateur lance un **second
`claude -p` non-bloquant** dont la seule tâche est de lire le log JSONL de
l'agent surveillé et de répondre `VERDICT: kill` ou `VERDICT: continue`.

Le prompt d'audit (cf. `AUDIT_PROMPT_TEMPLATE` dans `orchestrate.py`) liste
des signaux concrets de patinage (`tool_result is_error: true` répétés,
mêmes `tool_use` en boucle, monologue sans tool_use, etc.).

- L'audit tourne en parallèle de l'agent surveillé — il ne bloque pas le
  scheduler. Si l'audit lui-même dépasse `--audit-timeout`, on le kill et on
  garde le verdict par défaut `continue`.
- L'audit consomme du temps de modèle (souvent `sonnet`). Choisir un modèle
  léger.
- En cas d'erreur d'audit (rc != 0, verdict unparseable) → `continue` (safe
  default). Il vaut mieux laisser un agent borderline finir que kill faux-positif.

### 3. Cap absolu — détection ultime

Default : `--timeout 600s` (10 min par agent).

Kill systématique au-delà, peu importe les verdicts d'audit ou l'activité du
log. Garde-fou contre un agent qui produit un log très bavard mais ne
progresse pas dans le pipeline.

### Filet commun : auto-abandon des claims orphelins

Quel que soit le motif du kill (sliding / audit / cap / sortie propre), au
moment du `harvest()` :

1. On filtre les commits depuis le HEAD initial par `<short>` de l'agent
   (champ extrait du premier event `system/init` du log JSONL).
2. On parse les `Claim` et `Release` parmi ces commits.
3. Un `Claim <step> <slug> (<short>)` sans `<Step> <slug>: <result> (<short>)`
   matchant = orphelin. On appelle `force_release_abandon(step, slug, short)`,
   qui délègue à `release.py --force-abandon-orphan <short> <step> <slug> abandon`
   du domaine.

Sans ça, un verrou laissé sur une ligne du TODO la bloque pour tous les runs
futurs.

## Points d'adaptation (`# ADAPT:` dans `orchestrate.py`)

Six zones marquées. Faire le tour dans l'ordre :

| # | Zone | Ce que tu changes |
|---|---|---|
| 1 | `SUBAGENT_PROMPT` | Le prompt complet du sous-agent : procédure (`claim.py next` → lire `TASK:` → travail → release) avec le "tu ne choisis pas ta tâche", lien vers `PROTOCOL.md`, allowlist synchronisée avec `--allowedTools`, posture face au doute (`signalé`), restrictions git. Voir `1-sources/outils/ressources/orchestrate.py` pour un patron complet et travaillé. |
| 2 | `CLAIM_RE` / `RELEASE_RE` | Regex qui matchent les sujets de commit produits par `claim.py` / `release.py` du domaine. Doivent capturer `(step, slug, short)`. |
| 3 | `RELEASE_SCRIPT` + `force_release_abandon()` | Chemin du `release.py` du domaine. La signature `--force-abandon-orphan <short> <step> <slug> abandon` est la convention attendue (cf. `1-sources/outils/ressources/release.py`). |
| 4 | `queue_has_work()` + constantes (`NUM_COLS`, `STEP_COL_RANGE`, `VERROU_COL`, `RECLAIMABLE_COUNTER`, `COUNTER_STEP_COL`) | Lecture grossière du TODO. Heuristique, pas besoin de répliquer la logique exacte de `claim.py`. |
| 5 | `launch_subagent()` — `--allowedTools` | Liste stricte des outils et scripts autorisés. **Synchronisée à la main** avec ce que dit `SUBAGENT_PROMPT`. Pas de wildcard global. |
| 6 | `scan_flags()` | Format du `FLAGS.md` final. Quelles sections (signalé / verrous / compteur incomplet / mentions prose), quels noms d'étapes. |

Les **constantes de chemin** en haut du fichier (`TODO`, `RUNS_DIR`,
`TMP_PROJECT`) doivent aussi être adaptées — elles ne sont pas marquées `# ADAPT:`
parce qu'évidentes.

## Dupliquer pas à pas

1. **Copier** `common/outils/templates/subagent-orchestrator/` vers `<couche>/outils/<ton-domaine>/`.
   Renommer le fichier en `orchestrate.py` (déjà ce nom dans le template) ;
   supprimer le `README.md` et le `EXAMPLE_TODO.md` du template (ils sont
   méta — ton `PROTOCOL.md` et ton `TODO.md` du domaine vivent ailleurs).

2. **Adapter les constantes de chemin** en haut du fichier :
   ```python
   TODO = REPO_ROOT / "<ton-domaine>" / "TODO.md"
   RUNS_DIR = REPO_ROOT / "<couche>" / "outils" / "<ton-domaine>" / "runs"
   TMP_PROJECT = "<ton-projet>"
   ```

3. **Adapter les 6 zones `# ADAPT:`** dans l'ordre. La plus longue est le
   `SUBAGENT_PROMPT` — prends le temps, c'est ce que tes sous-agents lisent
   en premier. Inspire-toi de `1-sources/outils/ressources/orchestrate.py`.

4. **Vérifier la synchro `SUBAGENT_PROMPT` ↔ `--allowedTools`**. Tout
   `Bash(<couche>/outils/<domaine>/foo.py *)` mentionné dans `--allowedTools` doit être
   listé dans le prompt comme "tu peux exécuter X" — et inversement. Un
   décalage = un agent qui essaie une commande refusée silencieusement et
   tourne en rond.

5. **Ajouter les permissions dans `.claude/settings.json`** pour que tu
   puisses lancer `<couche>/outils/<ton-domaine>/orchestrate.py` sans prompt manuel à
   chaque run. Pattern habituel : `Bash(<couche>/outils/<ton-domaine>/orchestrate.py *)`.

6. **Smoke-test en `--dry-run`** d'abord : `<couche>/outils/<ton-domaine>/orchestrate.py --dry-run`.
   Ça vérifie que le `TODO.md` est lisible et que `queue_has_work()` rend la
   bonne réponse, sans lancer de `claude -p`.

7. **Premier vrai run en `--slots 1 --max-agents 1`** pour voir un cycle
   complet (claim → travail → release → harvest → FLAGS) avant de monter en
   parallèle.

## Refus de lancer si `ANTHROPIC_API_KEY` est set

Garde anti-facturation accidentelle. `claude -p` peut utiliser une session
Claude Code (gratuite, plafonnée par ton plan) **ou** facturer sur la clé API
si elle est posée dans l'env. Pour un run d'orchestrateur qui peut lancer 10
sous-agents × 10 minutes chacun, l'addition monte vite. Le script refuse
explicitement de partir si `ANTHROPIC_API_KEY` est set.

Si tu veux **vraiment** facturer sur l'API (cas légitime : tu n'as plus de
quota session) : `unset ANTHROPIC_API_KEY` n'est pas la bonne réponse —
retire la garde explicitement en éditant le script, comme ça tu sais ce que
tu fais.

## Pourquoi `--output-format stream-json --verbose`

Sans `stream-json`, `claude -p` n'imprime que la réponse finale, après
terminaison. Tu es aveugle pendant l'exécution → le sliding watchdog n'a rien
à observer (le fichier de log reste vide jusqu'à la fin).

Avec `stream-json --verbose`, chaque event (tool_use, tool_result, message,
init, …) est flushé en JSONL au fil de l'eau. C'est ce qui rend possible :

- Le sliding watchdog (mtime du log = preuve d'activité).
- L'audit-agent (lit les derniers events pour juger).
- La détection du `session_id` (event `system/init` en premier).

Ne retire pas ces flags.

## Hors scope du template

- **Tests** : pas de suite de tests fournie. L'instance vivante n'en a pas
  non plus — c'est testé par smoke-runs (`--dry-run` puis `--slots 1`).
- **CLI auto-générée** : les arguments sont écrits à la main avec `argparse`.
  Tu peux en ajouter, ne complexifie pas le pattern.
- **Audit-agent paramétrable** : le prompt d'audit est hardcodé pour le
  domaine. Tu peux le réécrire mais pas le rendre configurable depuis
  l'extérieur — ça mélange les niveaux d'abstraction.
- **Coordination multi-machine** : `flock` est local. Si tu veux orchestrer
  depuis plusieurs machines, il faut un état partagé via remote — sort
  complètement du périmètre.

## Voir aussi

- [`common/outils/templates/file-validation/`](../file-validation/README.md) — le
  skill compagnon. Si tu n'as pas encore le `claim.py` / `release.py` du
  domaine, commence par celui-là.
- [`1-sources/outils/ressources/orchestrate.py`](../../ressources/orchestrate.py) —
  instance vivante complète, en production sur le pipeline d'extraction des
  ressources CATS. ~830 lignes, exemple concret de tout ce qui est décrit
  ici.
- [`1-sources/outils/ressources/RESSOURCES_PROTOCOL.md`](../../ressources/RESSOURCES_PROTOCOL.md) —
  ce que fait un sous-agent en pratique (côté contenu du prompt).
