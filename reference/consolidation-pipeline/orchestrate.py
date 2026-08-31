#!/usr/bin/env python3
"""orchestrate.py — boucle qui fait tourner la pipeline de consolidation.

Peek read-only de `2-consolide/outils/tasks.csv` → spawn d'un agent jetable (`claude -p`)
du bon rôle → relance jusqu'au drain. Ne mute jamais le CSV, aucun git : toute
transition passe par les verbes `task.py` appelés par les agents.

`run` est une boucle slottée (`ThreadPoolExecutor`) : refill par slot via
`peek_schedule` (production prioritaire, validation au drain ; anti-sur-spawn du gate 2/2),
`consecutive_empty` anti-spawn-blanc, drain propre. Défaut séquentiel
(`slots=1`) → zéro régression sur les tests historiques. Chaque préoccupation est
verrouillée par une suite `tests/test_orchestrate_*.py` (une par préoccupation) —
les tests sont la spec.

Spec : `2-consolide/outils/docs/specs/orchestrateur.md`, `cli.md`, `validate.md`, `watchdog.md` ;
*pourquoi* : `2-consolide/outils/docs/philosophy/orchestrateur.md`.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _store  # noqa: E402
import task    # noqa: E402

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# Rôle → fichier-prompt de rôle (concaténé après common.md). `scope` et `map`
# partagent le type `map` côté CLI : c'est `note=oversize` qui les distingue
# (cf. prompts/scope.md).
PRODUCTION_ROLES = ("map", "scope", "reduce")


# --- Fabrication du prompt (R4 — aucun inline) ----------------------------

def prompt_for(role: str) -> str:
    """Prompt autonome d'un agent : `common.md` + `<role>.md` concaténés.

    Source unique = les fichiers `prompts/` (R4) : aucun fragment de consigne
    inline dans ce script (cf. `outils/docs/philosophy/prompts.md`). `role` ∈
    {map, scope, reduce, validate}.
    """
    common = (PROMPTS_DIR / "common.md").read_text(encoding="utf-8")
    body = (PROMPTS_DIR / f"{role}.md").read_text(encoding="utf-8")
    return common + "\n" + body


# --- Peek read-only (R1/R3/R6) --------------------------------------------

def peek_production(root: Path) -> "tuple[str, str] | None":
    """Lit `tasks.csv` **en lecture seule** et rend `(rôle, id)` de la prochaine
    tâche de **production** à spawner, ou `None` si plus rien de prenable.

    Mirroir déterministe de `task.py claim_next` (ordre `(type, id)`, gating reduce
    identique via `task.present_reduce_themes`) : prédit la tâche que l'agent
    claimera, et en déduit le rôle —
      - `map` prenable `note=oversize` → `"scope"` ;
      - `map` prenable sinon            → `"map"` ;
      - `reduce` prenable               → `"reduce"`.
    Ne rend **jamais** un reduce en `to_validate` (R6 : c'est de la validation,
    cf. préoccupation 2 / S12c). **Ne mute pas le CSV** (R1).
    """
    rows = _store.read_tasks(root)
    # Même set/ordre/gating que `task.py claim_next` sans `--type` : un seul scan des
    # fragments pour le gating reduce, puis ordre déterministe `(type, id)`.
    present = task.present_reduce_themes(root)
    cands = [r for r in rows if task.is_takeable(r, root, present)]
    if not cands:
        return None                                   # E5/E6 : drain production
    cands.sort(key=lambda r: (r["type"], r["id"]))
    row = cands[0]
    if row["type"] == "map":
        role = "scope" if row["note"] == "oversize" else "map"  # R3
    else:                                              # reduce prenable
        role = "reduce"
    return role, row["id"]


# --- Spawn d'un agent jetable (R2) ----------------------------------------

# Allowlist headless passée à `claude -p` — miroir de `prompts/common.md`
# § Allowlist headless stricte (source de vérité = common.md, à garder aligné).
# Le bash lecture seule (grep/wc/ls/cat/head/tail) est autorisé parce que les
# prompts l'utilisent déjà : sans lui, un Bash refusé annule les tool calls frères
# du même tour et l'agent agit sur des données partielles. `echo` est autorisé pour
# lire `$CLAUDE_CODE_SESSION_ID[:8]` → le `map_session` que `check.py` exige dans le
# frontmatter ; sans voie allowlistée l'agent le forçait hors allowlist (friction +
# annulation muette du batch). `sed` reste exclu (`sed -i` écrit) ; l'écriture passe
# par Write/Edit/task.py.
_ALLOWED_TOOLS = (
    "Read Edit Write Glob Grep "
    "Bash(2-consolide/outils/task.py *) "
    "Bash(grep *) Bash(wc *) Bash(ls *) Bash(cat *) Bash(head *) Bash(tail *) "
    "Bash(echo *) "
    "Bash(git status) Bash(git diff) Bash(git log) Bash(git show)"
)


def default_spawn(root: Path, role: str, task_id: str) -> None:
    """Spawn réel : `claude -p` headless avec `prompt_for(role)`. **L'agent**
    claime via `claim_next` (R2) ; cette fonction ne touche pas le CSV.

    Bloquant (modèle séquentiel du squelette) : on attend
    la fin de l'agent avant le peek suivant — « aucun agent en vol » est donc
    trivial (Q4). Le multi-slots + l'observabilité fine (rc/durée/commits,
    watchdog/cap) arrivent en S12e/f.

    **Session distincte par agent** : on retire `CLAUDE_CODE_SESSION_ID` de l'env
    transmis pour que chaque `claude -p` se forge son propre id — sinon tous les
    agents hériteraient du short de l'orchestrateur et la garde distinct-agent du
    gate 2/2 ne pourrait plus séparer auteur ↔ validateurs (cf. validate.md).

    Injectable : `run_production` reçoit un `spawn` pour permettre aux tests de
    simuler l'agent sans forker `claude`.
    """
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    subprocess.run(
        ["claude", "-p", prompt_for(role), "--model", DEFAULT_WORKER_MODEL,
         "--allowedTools", _ALLOWED_TOOLS],
        cwd=root, env=env, check=False,
    )


# --- Boucle production (R5) -----------------------------------------------

# Peeks identiques consécutifs tolérés avant d'abandonner la production. À 3, on
# laisse passer **un** spawn « blanc » transitoire (hoquet réseau, rate-limit,
# agent qui ne claime pas une fois) avant de conclure au blocage — deux peeks
# identiques arrivent en pratique, trois signalent un vrai stall.
STALL_LIMIT = 3


def _stderr_log(msg: str) -> None:
    """Fallback de log quand aucun callback n'est fourni (appels directs hors
    `run_monitored` — tests, CLI ad hoc) : la décision reste visible sur stderr.
    Le run réel backgroundé passe un callback vers `log_event` → la ligne tombe
    dans `orchestrator.log` (stderr y est perdu). Signature `msg -> None`,
    interchangeable avec `lambda m: log_event(logfh, m)`."""
    print(msg, file=sys.stderr, flush=True)


def run_production(root: Path, spawn, log=None) -> None:
    """Boucle du flux production : peek → spawn du rôle → relance jusqu'au drain.

    `spawn(role, task_id)` est injecté (réel : `default_spawn` ; test : fake qui
    simule l'agent). Tant que `peek_production` rend une tâche, la spawner ;
    `None` → production drainée, retour. L'orchestrateur ne mute jamais le CSV :
    tout l'état avance via les agents (R1/R2).

    **Garde anti-boucle (revue S12b).** Si `STALL_LIMIT` (3) peeks consécutifs
    rendent le **même** `(rôle, id)`, c'est que les spawns n'ont rien fait
    avancer — agent qui `release` en préservant `oversize` ou
    qui crashe avant de claimer (Q3). Le seuil à 3 tolère un spawn « blanc »
    transitoire avant de conclure au blocage. On s'arrête plutôt que de boucler à
    l'infini en background. Le watchdog/cap sur le temps (kill d'un agent trop
    lent) reste S12e.
    """
    log = log or _stderr_log
    last = None
    streak = 0
    while True:
        peek = peek_production(root)
        if peek is None:
            return                                     # production drainée (R5)
        streak = streak + 1 if peek == last else 1
        if streak >= STALL_LIMIT:
            log(f"stall production {peek[1]} peeks={streak} "
                f"(role={peek[0]}, sans progrès)")
            return
        role, task_id = peek
        spawn(role, task_id)                           # l'agent claime via claim_next (R2)
        last = peek


# --- Driver : boucle slottée, production prioritaire (S12d) ---------------

def _state_fingerprint(root: Path) -> tuple:
    """Empreinte de l'état ordonnançable du CSV — change ssi une transition a eu
    lieu (status/owner/note). Sert de garde anti-boucle **globale** au driver :
    les flux internes ont chacun leur garde, mais un tour complet (validation +
    production) qui ne change **rien** alors qu'il reste du grain est un stall
    croisé (p.ex. validateurs qui crashent en boucle)."""
    return tuple((r["id"], r["status"], r["owner"], r["note"])
                 for r in _store.read_tasks(root))


TASK_PY = Path(__file__).resolve().parent / "task.py"


def detect_short_sha(log_path: "Path | None") -> "str | None":
    """Parse les premières lignes du JSONL stream-json d'un sous-agent pour en
    extraire son `session_id` (1er event `type=system, subtype=init`). Rend les 8
    premiers chars, ou None si introuvable (log absent/illisible/pas encore d'init).
    Porté de `1-sources/outils/ressources/orchestrate.py:detect_short_sha`.

    L'orchestrateur retire `CLAUDE_CODE_SESSION_ID` de l'env de chaque agent → il ne
    connaît PAS le short a priori. C'est l'unique source du short de l'agent tué, que
    `_recover_orphan` doit passer à la garde owner==short de `task.py` (R53)."""
    if log_path is None:
        return None
    try:
        with log_path.open() as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    return None
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = ev.get("session_id")
                if sid:
                    return sid[:8]
    except OSError:
        pass
    return None


def _recover_orphan(root: Path, task_id: str, log_path: "Path | None" = None,
                    log=None) -> None:
    """Après la moisson d'un agent : toute tâche restée `claimed`/`to_validate`
    avec `owner` == le short de cet agent est un **verrou orphelin** — l'agent est
    mort (tué par le cap/sliding/audit, crashé avec exception, ou sorti sans
    `release`) en le tenant. Sans récup, un reduce orphelin `to_validate` gèle le
    gate 2/2 pour tout le run.

    **Indexée sur l'`owner` réel, jamais sur `task_id`.** `task_id` n'est que le
    *label de spawn* (la tâche prédite au peek) : l'agent claime via `claim_next`
    et peut tenir une AUTRE tâche (course entre slots — checker le label laisse la
    tâche réellement tenue orpheline, cf. watchdog.md § 6). On détecte donc le
    short sur le JSONL de l'agent moissonné (`detect_short_sha`), on scanne
    `tasks.csv` sur `owner == short` (0, 1 ou plusieurs lignes), et on délègue
    chaque reset à `task.py release --force-orphan <short> <id>` (R1 : seul
    `task.py` mute, sous flock ; R53) — sa garde owner==short (R51) re-vérifie
    sous le flock. **Best-effort** : short introuvable → impossible de savoir ce
    que l'agent tenait, diagnostic sur le label de spawn (log + skip, pas d'appel
    `task.py`) ; force-release en échec → log + continue. L'orphelin sera repris
    au prochain tour ou à la main."""
    log = log or _stderr_log
    rows = _store.read_tasks(root)
    short = detect_short_sha(log_path)
    if short is None:                               # pas de short → on ne peut pas garder owner==short
        # Sans short on ne sait pas quelle tâche l'agent tenait : diagnostic
        # best-effort sur le label de spawn. Si le parent tient une lease
        # `correcting:`, l'absence de short la rend **non récupérable** par
        # `--force-orphan` (garde owner==short) : le sémaphore
        # (`peek_schedule`/`is_validatable`) va alors sauter tous les shards de ce
        # consolidé → il **gèle** jusqu'à un `clear-lease` manuel. On le dit clairement
        # plutôt que de laisser croire « repris au prochain tour ».
        row = task.find_row(rows, task_id)
        if row is None or row["status"] not in ("claimed", "to_validate") or not row["owner"]:
            return
        parent = task.find_row(rows, row["parent"]) if row["parent"] else None
        if parent is not None and task.parse_lease(parent["note"]):
            log(f"orphan-FROZEN {task_id} short-introuvable, lease correcting: tenue "
                f"sur {parent['id']} non récupérable → consolidé gelé "
                f"(clear-lease manuel requis)")
        else:
            log(f"orphan-skip {task_id} short-introuvable "
                f"(owner={row['owner']}, best-effort, repris au prochain tour)")
        return
    owned = [r for r in rows
             if r["owner"] == short and r["status"] in ("claimed", "to_validate")]
    for r in owned:
        res = subprocess.run(
            [str(TASK_PY), "release", "--force-orphan", short, r["id"],
             "--repo-root", str(root)],
            cwd=root, capture_output=True, text=True, check=False)
        # rc dédié (task.FORCE_ORPHAN_NOOP_RC) : un « ok » uniforme confondrait
        # récup réelle et no-op — un no-op peut cacher un orphelin encore tenu.
        if res.returncode == 0:
            tag = "recovered"
        elif res.returncode == task.FORCE_ORPHAN_NOOP_RC:
            tag = "no-op (owner/statut a bougé sous le flock — rien resetté)"
        else:
            tag = f"FAIL rc={res.returncode}"
        log(f"orphan-recovery {r['id']} (owner={short}, spawn-label={task_id}) → {tag}")


def run(root: Path, spawn, slots: int = 1, max_agents: "int | None" = None,
        stats: "dict | None" = None,
        recover_log: "Callable[[str, str], Path | None] | None" = None,
        log=None) -> None:
    """Driver **slotté** (boucle unique, `ThreadPoolExecutor(max_workers=slots)`) :
    re-peek par slot libre via `peek_schedule` (production prioritaire, validation au drain, cap-aware),
    refill continu, deux dimensions de cap, drain propre des agents en vol
    (`orchestrateur.md` § La boucle / § Deux dimensions de cap, R21–R28).

    Choix d'archi (tranché par Josian) : **ThreadPool** — N
    threads, chacun **bloque** sur son `spawn(role, task_id)` injecté — et **non** la
    boucle mono-thread `Popen`+poll de `1-sources/outils/ressources/orchestrate.py`. Le contrat
    `spawn(role, task_id)` bloquant est donc **inchangé**, réutilisé tel quel par tous
    les fakes S12 → zéro régression. Le cap-temps dur reste porté par `spawn_capped`
    (chaque thread l'appelle pour le spawn réel) ; sliding-inactivity / audit-agent de
    `ressources` ne sont pas portés.

    - **`slots`** (≥ 1) — concurrence : ≤ `slots` agents en vol à tout instant (R22).
    - **`max_agents`** (`None` = illimité) — budget total : on **cesse de lancer** à
      `launched == max_agents`, puis on **draine** les slots en cours (R26).
    - **`consecutive_empty`** : à chaque moisson, si l'empreinte CSV n'a pas bougé
      depuis la précédente, les agents moissonnés n'ont rien fait avancer (spawn
      « blanc ») → `+= len(done)` ; sinon `0`. À `≥ EMPTY_LIMIT` on cesse de lancer
      et on draine (R27). Le gate 2/2 et le re-cycle des corrections (`corrigé`
      reset-all des frères) font progresser l'empreinte → jamais tués par cette garde.

    **Défaut séquentiel** (`slots=1, max_agents=None`) : un seul agent en vol, refill
    après chaque moisson → production prioritaire + drain complet **équivalents** à
    l'ancien driver d'alternation → tests S12 (production/validation/driver/
    monitoring) inchangés et verts (R28). Ne mute jamais le CSV (R1) : tout l'état
    avance via les agents."""
    log = log or _stderr_log
    inflight_val: "dict[str, int]" = {}     # reduce id → nb passes spawnées-non-moissonnées (R24)
    inflight_prod_ids: "set[str]" = set()   # ids de production en vol (R25)
    launched = 0
    consecutive_empty = 0
    last_fp = _state_fingerprint(root)
    futures: "dict" = {}                     # Future → (role, task_id, is_validate)
    with ThreadPoolExecutor(max_workers=slots) as pool:
        while True:
            # Fill : remplit les slots libres tant qu'il reste du budget, du grain et
            # qu'on n'a pas stallé. Le rôle se re-décide à chaque slot (R22/R23).
            while (len(futures) < slots
                   and (max_agents is None or launched < max_agents)
                   and consecutive_empty < EMPTY_LIMIT):
                sched = peek_schedule(root, inflight_val, inflight_prod_ids)
                if sched is None:
                    break                              # plus rien à lancer
                role, task_id, is_validate = sched
                fut = pool.submit(spawn, role, task_id)   # l'agent claime via next (R2)
                futures[fut] = (role, task_id, is_validate)
                if is_validate:
                    inflight_val[task_id] = inflight_val.get(task_id, 0) + 1
                else:
                    inflight_prod_ids.add(task_id)
                launched += 1
            if not futures:
                # Drain complet (aucun agent en vol). Pour l'auditabilité (S15),
                # qualifie POURQUOI on s'arrête : budget atteint, stall « blanc »
                # (consecutive_empty), ou plus aucun grain prenable (drain franc).
                if stats is not None:
                    if max_agents is not None and launched >= max_agents:
                        reason = "budget"
                    elif consecutive_empty >= EMPTY_LIMIT:
                        reason = "empty"
                    else:
                        reason = "drain"
                    stats["launched"] = launched
                    stats["stop_reason"] = reason
                return                                 # drain complet : aucun agent en vol
            # Moisson : attend qu'au moins un agent finisse, libère son slot.
            done, _ = wait(futures, return_when=FIRST_COMPLETED)
            for fut in done:
                role, task_id, is_validate = futures.pop(fut)
                if is_validate:
                    n = inflight_val.get(task_id, 0) - 1
                    if n > 0:
                        inflight_val[task_id] = n
                    else:
                        inflight_val.pop(task_id, None)
                else:
                    inflight_prod_ids.discard(task_id)
                exc = fut.exception()
                if exc is not None:                    # surface, ne crashe pas la boucle
                    log(f"agent-error {role} {task_id} {exc!r}")
                # Récup de verrou orphelin : couvre kill cap/sliding/audit, crash
                # (exc≠None) ET exit propre sans release. Doit tourner avant le
                # fingerprint pour que la récup compte comme un progrès (empreinte qui
                # bouge). `recover_log` résout le JSONL de l'agent moissonné → short ;
                # la récup scanne owner==short (R53) — `task_id` n'est que le label de
                # spawn, la tâche réellement claimée peut différer (claim_next) ;
                # log None (fakes sans JSONL) → skip best-effort.
                log_path = recover_log(role, task_id) if recover_log else None
                _recover_orphan(root, task_id, log_path, log=log)
            # Progrès : empreinte inchangée depuis la moisson précédente → blanc (R27).
            fp = _state_fingerprint(root)
            if fp == last_fp:
                consecutive_empty += len(done)
            else:
                consecutive_empty = 0
            last_fp = fp


# --- Ordonnancement slotté : deux dimensions de cap -----------------------
#
# Modèle slotté porté de `1-sources/outils/ressources/orchestrate.py` : `--slots`
# (concurrence) + `--max-agents` (budget total), refill par slot, anti-sur-spawn
# des validateurs (gate 2/2), drain propre. Spécificité consolide : prompts
# role-specific → l'orchestrateur décide le rôle avant de spawner (re-peek par slot
# via `peek_schedule`), pas de worker générique. Spec : `orchestrateur.md`
# § Deux dimensions de cap ; exemples E26–E34.

EMPTY_LIMIT = 5      # consecutive_empty ≥ ce seuil → cesse de lancer, draine (R27, parité ressources)


def peek_schedule(root: Path, inflight_val: "dict[str, int]",
                  inflight_prod_ids: "set[str]") -> "tuple[str, str, bool] | None":
    """Ordonnance **un** slot libre, read-only (R23) : rend `(rôle, id, is_validate)`.

    **Production prioritaire ; validation au drain de la production** (V0 deadline :
    produire tous les consolidés d'abord, valider ensuite — choix permanent, sans flag).
    **Production d'abord** : la 1ʳᵉ tâche prenable (mirroir de `peek_production`, ordre
    `(type, id)`) dont l'`id` ∉ `inflight_prod_ids`, rendue `(rôle, id, False)` (R25,
    oversize→`scope`). La production n'est jamais « à sec » tant qu'il reste un map ou un
    reduce → les validations ne démarrent qu'au drain de la production. **Sinon
    validation, une passe en vol par shard** : un **enfant** `validate:<clé>#n`
    `to_validate` (`owner` vide), **parent non sous correction** (lease `correcting:` —
    même sémaphore que `task.is_validatable`, source unique `task.held_lease_parents`),
    n'est rendu `("validate", id, True)` que si **aucune passe n'est déjà en vol** sur lui
    (`inflight_val.get(id, 0) == 0`, R24, gate 2/2 **per-shard**, `id` = l'enfant). Les
    deux `ok:` du gate s'obtiennent par **2 passes séquentielles, pas concurrentes** : une
    passe tient l'`owner` du shard jusqu'à son `approve`, donc une 2ᵉ passe lancée en
    parallèle ne peut pas le prendre — elle divergerait vers un autre shard (cassant le
    suivi `inflight_val` indexé par `id`) ou ne ferait rien. On attend donc
    la moisson de la passe en vol avant d'en lancer une autre sur le même shard. Le reduce
    parent `split` n'est jamais planifié lui-même — le gate vit sur ses enfants. `None` si
    plus rien à lancer (drain). **Ne mute pas le CSV.**"""
    rows = _store.read_tasks(root)
    # 1) Production prioritaire : mirroir de `peek_production` (gating reduce + ordre
    #    (type, id)), en sautant les `id` déjà en vol (R25).
    present = task.present_reduce_themes(root)
    prod_cands = sorted(
        (r for r in rows if task.is_takeable(r, root, present)),
        key=lambda r: (r["type"], r["id"]))
    for r in prod_cands:
        if r["id"] in inflight_prod_ids:
            continue                                   # déjà pris en charge par un agent vivant
        if r["type"] == "map":
            role = "scope" if r["note"] == "oversize" else "map"   # R3/R25
        else:
            role = "reduce"
        return role, r["id"], False
    # 2) Sinon validation, **une passe en vol par shard** (gate 2/2 séquentiel, R24).
    #    Enfants `validate:<clé>#n` `to_validate` `owner` vide, **parent non sous
    #    correction**, triés par id ; on rend le 1ᵉʳ sans passe en vol. Les passes sont
    #    **sérialisées par `owner`** (une passe tient le shard jusqu'à son `approve`) :
    #    lancer 2 passes concurrentes sur le même shard est inutile — la 2ᵉ ne peut pas le
    #    claimer, elle divergerait (suivi `inflight_val` indexé par `id` → faux).
    #    D'où le cap à 1 passe en vol (`inflight_val == 0`), pas `2 − oks − inflight`.
    #    Le filtre `owner` vide exclut un shard déjà claimé ; `inflight_val == 0` couvre en
    #    plus la fenêtre spawn→claim (owner pas encore posé). Le skip des parents
    #    verrouillés (lease `correcting:`) est le même sémaphore que `task.is_validatable`
    #    côté agent (`task.held_lease_parents`) : ne jamais planifier un shard qui va être
    #    reset-all — sinon spawn blanc + collision avec le correcteur en place.
    locked = task.held_lease_parents(rows)
    val_cands = sorted(
        (r for r in rows
         if r["type"] == "validate" and r["status"] == "to_validate"
         and not r["owner"] and r["parent"] not in locked),
        key=lambda r: r["id"])
    for r in val_cands:
        if inflight_val.get(r["id"], 0) == 0:          # ≤1 passe en vol par shard (sérialisé par owner)
            return "validate", r["id"], True
    return None                                        # plus rien à lancer (drain)


# --- Monitoring + robustesse ----------------------------------------------
#
# Rendre un run backgroundé observable sans bloquer l'agent qui l'a lancé
# (`orchestrateur.md` § Bandeau de monitoring ; exemples E19+).

RUN_LOG = "orchestrator.log"      # nom du fichier-log dans le <run> dir
TERMINAL_MARKER = "flags :"       # token stable+unique ; dernière ligne = run fini (R17)
DEFAULT_CAP_S = 300               # cap dur par agent (5 min, couche 3). Une tâche finit en ~1-3 min ;
                                  # au-delà l'agent est planté ou en rabbit-hole. Le cap n'attrape
                                  # PAS un rabbit-hole qui produit du log — d'où les couches sliding
                                  # (1) et audit (2) ci-dessous (watchdog.md § 3, qui définit le mot
                                  # « watchdog » référencé par orchestrateur.md).
DEFAULT_SLIDING_S = 120           # sliding-inactivity (couche 1) : aucun append au JSONL par-agent
                                  # depuis 120 s ⇒ kill. Plus court que le cap, attrape les plantages
                                  # silencieux avant. 120 s (vs 180 ressources) : pas de read d'images.
POLL_INTERVAL_S = 1.0             # période de poll du spawn auto-pollant (réactif sans busy-loop).

DEFAULT_AUDIT_AFTER_S = 150       # audit sémantique (couche 2) : on n'audite qu'au-delà de la fenêtre
                                  # normale (1-3 min) → seuls les retardataires/rabbit-holes le sont (§ 8).
DEFAULT_AUDIT_INTERVAL_S = 60     # re-audit toutes les 60 s tant que l'agent tient.
DEFAULT_AUDIT_MODEL = "sonnet"    # l'audit tranche kill/continue sur un digest ; un faux kill détruit
                                  # du travail en vol → sonnet, le jugement prime sur le coût (§ 8).
DEFAULT_AUDIT_TIMEOUT_S = 90      # cap dur sur le `claude -p` d'audit : s'il traîne, kill + CONTINUE (§ 8).

DEFAULT_WORKER_MODEL = "claude-opus-4-8"   # modèle PINNÉ des agents workers (reduce/map). Sans ce pin,
                                           # `claude -p` hériterait du défaut UI du lanceur (Fable 5 p. ex.)
                                           # → coût non déterministe. On pin pour que le coût ne dépende
                                           # pas du modèle sélectionné dans la session interactive.

# Sérialise les écritures de log : sous slots>1, plusieurs threads loggent
# spawn/fin en parallèle ; sans verrou les lignes s'entrelacent (orchestrateur.md
# § Bandeau). Mono-thread (tests S12) : aucun effet observable.
_LOG_LOCK = threading.Lock()


def banner(log_path: Path) -> str:
    """Bandeau « À L'AGENT QUI A LANCÉ CE SCRIPT » imprimé avant le 1er spawn (R15).

    (a) **Interdit** `sleep`/`until`/`wait` foreground ; (b) donne la **commande
    exacte à coller dans `Monitor`** — `2-consolide/outils/watch.py <run-id>`, qui
    streame les nouvelles lignes du log et sort sur le marqueur terminal. Le run-id
    est le nom du `<run>` dir (`log_path.parent.name`). Snippet historique (boucle
    inline remplacée par watch.py) : `outils/docs/philosophy/orchestrateur.md`.

    NB : aucune ligne ne commence par « spawn » — `run_monitored` repère le 1er
    spawn comme la 1ʳᵉ ligne contenant « spawn », il doit tomber **après** le bandeau.
    """
    # La commande Monitor : `watch.py <run-id>` (allowlistée `2-consolide/outils/*.py *`,
    # zéro prompt — l'ancienne boucle inline portait le run-id dans le chemin, donc
    # non allowlistable). Elle émet les nouvelles lignes au fil de l'eau et sort dès
    # que la dernière ligne porte `TERMINAL_MARKER`.
    run_id = log_path.parent.name
    monitor_cmd = f"2-consolide/outils/watch.py {run_id}"
    return (
        "════════════════════════════════════════════════════════════════════\n"
        "À L'AGENT QUI A LANCÉ CE SCRIPT\n"
        "════════════════════════════════════════════════════════════════════\n"
        "Ce run tourne en background et NE te réveillera PAS à sa fin.\n"
        "→ N'utilise PAS de `sleep` / `until` / `wait` en foreground : tu resterais\n"
        "  bloqué et aveugle.\n"
        "→ Colle plutôt cette commande dans l'outil `Monitor` (son sleep tourne en\n"
        f"  background, légitime) — elle émet chaque ligne au fil de l'eau et sort dès\n"
        f"  que la dernière ligne porte le marqueur terminal « {TERMINAL_MARKER} » :\n"
        "\n"
        f"{monitor_cmd}\n"
        "\n"
        "Pour inspecter l'état AVANT/PENDANT ce run, utilise `task.py peek_next`\n"
        "(LECTURE SEULE) — JAMAIS `task.py claim_next`, qui CLAIME la tâche de tête\n"
        "et l'orpheline (réservé aux agents spawnés par cet orchestrateur).\n"
        "\n"
        f"Log : {log_path}\n"
        "════════════════════════════════════════════════════════════════════"
    )


# --- Horodatage des lignes de log (auditabilité a posteriori) ---------------
#
# Chaque event (`spawn`/`end`/`kill`/`config`) et le marqueur terminal portent un
# timestamp wall-clock `HH:MM:SS` en tête → durées et ordre concurrent (slots>1)
# reconstituables a posteriori depuis `orchestrator.log`. Le **bandeau** n'est PAS
# horodaté (`ts=False`) : il contient la commande Monitor copiable, qui doit rester
# collable telle quelle.
#
# Garde-fou : le préfixe laisse intactes les sous-chaînes que le monitoring repère
# — « spawn » (1ʳᵉ ligne *contenant*, détection du 1er spawn) et « flags : » (grep
# en queue, marqueur terminal). `strip_ts` redonne le contenu brut aux parsers/tests.

TS_FMT = "%H:%M:%S"
_TS_RE = re.compile(r"^\d\d:\d\d:\d\d ")


def _now_ts() -> str:
    return datetime.datetime.now().strftime(TS_FMT)


def strip_ts(line: str) -> str:
    """Retire le préfixe `HH:MM:SS ` d'une ligne de log s'il est présent
    (idempotent sinon). Pour les parsers/tests qui veulent l'event brut."""
    return _TS_RE.sub("", line, count=1)


def log_event(logfh, msg: str, ts: bool = True) -> None:
    """Écrit `msg` en **1 ligne flushée immédiatement** sur `stdout`
    (`print(..., flush=True)`) **et** dans `logfh` (`write` puis `flush()`) — R16.
    Sans flush, un run backgroundé n'affiche rien avant sa fin. Sous slots>1, le
    verrou `_LOG_LOCK` empêche l'entrelacement des lignes concurrentes.

    `ts=True` (défaut) préfixe la ligne d'un timestamp wall-clock `HH:MM:SS` →
    auditabilité a posteriori (durées, ordre concurrent). `ts=False` pour le
    bandeau : sa commande Monitor doit rester copiable telle quelle."""
    line = f"{_now_ts()} {msg}" if ts else msg
    with _LOG_LOCK:
        print(line, flush=True)
        logfh.write(line + "\n")
        logfh.flush()


def log_terminal(logfh, flags_path: Path) -> None:
    """Écrit la **dernière** ligne du log = marqueur terminal `<ts> flags : <chemin>`
    (R17) — seul signal « run fini » pour le moniteur, présent même au drain
    immédiat. Horodaté (comme les events) et flushé ; le préfixe laisse « flags : »
    grepable en queue. `<chemin>` pointe vers le `<run>` dir (où vivent log et
    artefacts du run)."""
    line = f"{_now_ts()} {TERMINAL_MARKER} {flags_path}"
    with _LOG_LOCK:
        print(line, flush=True)
        logfh.write(line + "\n")
        logfh.flush()


# --- Plomberie log par-agent + digest d'audit -----------------------------
#
# Prérequis commun du watchdog 3 couches (`2-consolide/outils/docs/specs/watchdog.md` § 4) :
# sliding-inactivity, audit sémantique et auditabilité a posteriori lisent tous un
# JSONL streamé par agent. Le spawn réel le produit ; le digest
# (`build_audit_digest`/`_summarize_event`) est porté de `ressources` — porter, pas
# redessiner. Le contrat `spawn(role, task_id)` reste inchangé (la plomberie vit
# dans le spawn réel ; les fakes in-process ne la voient pas). Exemples E35–E41.

DIGEST_N_EVENTS = 50    # nb de derniers events résumés dans le digest (parité ressources)
DIGEST_MAX_FIELD = 400  # troncature par champ — borne la taille du digest (R32/R33)


def _summarize_event(ev: dict, max_field: int) -> "str | None":
    """Rend **un** event stream-json en bloc texte compact, en **retirant** les
    payloads image/base64 et en tronquant chaque champ à `max_field` (R33). Rend
    `None` si l'event n'a rien à montrer. Porté de `ressources` (adapté FR)."""
    t = ev.get("type")
    if t == "system":
        return f"[system {ev.get('subtype', '')}]"
    if t == "result":
        return f"[result {ev.get('subtype', '')}] {str(ev.get('result', ''))[:max_field]}"
    content = (ev.get("message") or {}).get("content")
    if not isinstance(content, list):
        return None
    parts: "list[str]" = []
    for item in content:
        if not isinstance(item, dict):
            continue
        it = item.get("type")
        if it == "text":
            txt = (item.get("text") or "").strip()
            if txt:
                parts.append(f"[text] {txt[:max_field]}")
        elif it == "thinking":
            th = (item.get("thinking") or "").strip()
            if th:
                parts.append(f"[thinking] {th[:max_field]}")
        elif it == "tool_use":
            inp = json.dumps(item.get("input") or {}, ensure_ascii=False)
            if len(inp) > max_field:
                inp = inp[:max_field] + "…"
            parts.append(f"[tool_use {item.get('name')}] {inp}")
        elif it == "tool_result":
            err = " ERROR" if item.get("is_error") else ""
            c = item.get("content")
            if isinstance(c, list):
                segs = []
                for b in c:
                    if isinstance(b, dict):
                        # image/base64 → rendu `<image>` (jamais le blob, R33).
                        segs.append(b.get("text", "") if b.get("type") == "text"
                                    else f"<{b.get('type', '?')}>")
                    else:
                        segs.append(str(b))
                cs = " ".join(segs)
            else:
                cs = str(c)
            parts.append(f"[tool_result{err}] {cs[:max_field]}")
    return "\n".join(parts) if parts else None


def build_audit_digest(log_path: Path, n_events: int = DIGEST_N_EVENTS,
                       max_field: int = DIGEST_MAX_FIELD) -> str:
    """Digest compact de la **fin** du JSONL d'un agent, pour l'audit (R32). Deux
    blocs : (1) compteurs globaux (events total, `tool_use` par nom décroissant,
    `tool_result` en erreur) — signal progrès/blocage à coût constant ; (2) les
    `n_events` derniers events résumés (base64/images retirés, champs tronqués).

    **Découple la taille du digest du contenu** : un log truffé de gros blobs
    produit un digest borné — sinon l'audit (S17) timeouterait sur les agents les
    plus longs, ceux qu'il doit justement surveiller. **Jamais d'exception** (R34) :
    log illisible → `(log illisible)`, vide → `(log vide…)`. Porté de `ressources`."""
    try:
        lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "(log illisible)"
    events: "list[dict]" = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not events:
        return "(log vide — agent pas encore démarré ?)"

    tool_counts: "dict[str, int]" = {}
    err_count = 0
    for ev in events:
        content = (ev.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use":
                name = item.get("name", "?")
                tool_counts[name] = tool_counts.get(name, 0) + 1
            elif item.get("type") == "tool_result" and item.get("is_error"):
                err_count += 1
    tool_summary = ", ".join(
        f"{k}×{v}" for k, v in sorted(tool_counts.items(), key=lambda kv: -kv[1])
    ) or "(aucun)"

    tail = events[-n_events:]
    rendered = [s for ev in tail if (s := _summarize_event(ev, max_field))]
    return (
        f"events total: {len(events)}\n"
        f"tool_use: {tool_summary}\n"
        f"tool_result en erreur: {err_count}\n\n"
        f"--- {len(tail)} derniers events ---\n" + "\n".join(rendered)
    )


# --- Audit sémantique en vol (couche 2) -----------------------------------
#
# `2-consolide/outils/docs/specs/watchdog.md` § 3 (couche 2) + § 8. À `--audit-after` puis tous
# les `--audit-interval` s, le spawn auto-pollant forke un `claude -p` sonnet qui
# lit le digest de l'agent en vol et tranche kill/continue. Défaut CONTINUE
# (rc≠0 / unparseable / timeout) : tuer un agent qui progressait coûte plus cher que
# le laisser finir. Prompt en fichier (`prompts/audit.md`, aucun inline) ; pas de
# plafond « K livrables/claim » (`compute_ceiling_check` non transposé — une tâche
# consolide = 1 artefact). Coupé par `--no-audit` (couches 1+3 seules). E55–E60.

_AUDIT_PROMPT_PATH = PROMPTS_DIR / "audit.md"


def build_audit_prompt(role: str, task_id: str, elapsed: int, log_path: Path) -> str:
    """Prompt d'audit : `prompts/audit.md` (R45 — aucun inline) formaté avec le
    rôle, la tâche, l'`elapsed` et le **digest** (S14) de l'agent en vol. Le digest
    est borné par construction (`build_audit_digest`) → pas de timeout sur les gros
    logs, ceux qu'il faut justement surveiller (§ 8)."""
    template = _AUDIT_PROMPT_PATH.read_text(encoding="utf-8")
    return template.format(
        role=role, task_id=task_id, elapsed=elapsed,
        digest=build_audit_digest(log_path),
    )


def launch_audit_async(role: str, task_id: str, n: int, log_path: Path,
                       elapsed: int, model: str, run_dir: Path,
                       cwd: "Path | None" = None,
                       ) -> "tuple[subprocess.Popen, Path]":
    """Forke un `claude -p` d'audit **non-bloquant** (R46, porté de `ressources`).
    Rend `(proc, audit_log_path)` ; l'appelant poll `proc.poll()` et passe le tuple
    à `parse_audit_result()` quand terminé. stdout/stderr → directement dans le
    fichier de log (pas de PIPE → pas de blocage de buffer). Pas d'`--allowedTools` :
    tout le contexte est dans le prompt, l'audit n'a **aucun fichier à lire** (évite
    qu'il tente un Read du log brut et timeoute). Retire `CLAUDE_CODE_SESSION_ID`
    comme le spawn d'agent."""
    prompt = build_audit_prompt(role, task_id, elapsed, log_path)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", task_id)
    audit_log = run_dir / f"audit-{role}-{safe}-{n}.log"
    cmd = ["claude", "-p", prompt, "--model", model, "--output-format", "text"]
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    audit_log.write_text(
        f"# audit {role} {task_id} (n={n}) — elapsed={elapsed}s model={model}\n\n",
        encoding="utf-8")
    af = audit_log.open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(cmd, stdout=af, stderr=subprocess.STDOUT,
                                cwd=cwd, env=env, start_new_session=True)
    finally:
        af.close()                                     # le fd hérité par le child reste écrit
    return proc, audit_log


def parse_audit_result(audit_proc: subprocess.Popen, audit_log_path: Path) -> bool:
    """À appeler quand `audit_proc.poll() is not None`. Lit le verdict ; rend
    **True ⇒ kill**, False ⇒ continue (R47). **Défaut CONTINUE** sur rc≠0, log
    illisible, ou verdict unparseable : tuer un agent qui progressait coûte plus
    cher que le laisser finir (§ 8). Seul un `VERDICT: kill` explicite tue."""
    if audit_proc.returncode != 0:
        return False                                   # erreur d'audit → continue
    try:
        out = audit_log_path.read_text(encoding="utf-8")
    except OSError:
        return False
    last = None
    for line in out.splitlines():
        s = line.strip()
        if s.upper().startswith("VERDICT:"):
            last = s.split(":", 1)[1].strip().lower()
    return last == "kill"                              # tout le reste (continue/unparseable) → False


def agent_log_path(run_dir: Path, role: str, task_id: str, n: int) -> Path:
    """Chemin du JSONL streamé d'un agent : `<run>/agent-<role>-<id>-<n>.jsonl`
    (R29). L'`id` est **sanitizé** (tout ce qui n'est pas alphanum/`-` → `_`) car
    il porte un `:` (`reduce:foo`) — illisible/ambigu en nom de fichier. `<n>` =
    compteur de spawn par (rôle, tâche), distingue 2 agents sur la même tâche après
    un re-spawn (R30)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", task_id)
    return run_dir / f"agent-{role}-{safe}-{n}.jsonl"


class _SpawnCounter:
    """Compteur de spawn par (rôle, tâche), thread-safe (R30). Sous `--slots > 1`
    plusieurs threads spawnent en parallèle → l'incrément doit être sérialisé pour
    que deux agents sur la même tâche obtiennent des `<n>` distincts."""

    def __init__(self) -> None:
        self._n: "dict[tuple[str, str], int]" = {}
        self._lock = threading.Lock()

    def next(self, role: str, task_id: str) -> int:
        with self._lock:
            key = (role, task_id)
            self._n[key] = self._n.get(key, 0) + 1
            return self._n[key]


# --- Auditabilité a posteriori : RUN.md / FLAGS.md ------------------------
#
# `2-consolide/outils/docs/specs/watchdog.md` § 5 : en fin de run, avant le marqueur terminal
# (R36), l'orchestrateur écrit un résumé forensique dans le run dir (gitignored) —
# agents tués + `reason`, orphelins résiduels, budget. Aucun git sur le run dir
# (R38) : que de l'I/O fichier + lectures RO du CSV. La promotion versionnée est
# hors orchestrateur. Exemples E42–E48.


def scan_run(root: Path, run_dir: Path, kills: "list[dict]", launched: int,
             max_agents: "int | None", stop_reason: str) -> str:
    """Construit le contenu Markdown de `RUN.md` (R37) — lecture seule, jamais de
    git mutant (R38). 3 sections : agents tués (+`reason`+JSONL), orphelins
    résiduels (CSV), budget (`launched`/`max`)."""
    rows = _store.read_tasks(root)

    killed_items = [
        f"- `{k['role']}` `{k['id']}` — reason : **{k.get('reason', '?')}**"
        + (f" — log : `{k['jsonl']}`" if k.get("jsonl") else "")
        for k in kills
    ]

    orphans = [
        f"- `{r['id']}` — `{r['status']}`, owner : `{r['owner']}`"
        for r in rows
        if r["status"] in ("claimed", "to_validate") and r["owner"]
    ]

    cap = max_agents if max_agents is not None else "∞"
    budget = [f"- {launched}/{cap} agents lancés — arrêt : **{stop_reason}**"]

    out: "list[str]" = []
    out.append(f"# Run {run_dir.name}\n")
    out.append(f"Généré : {datetime.datetime.now().isoformat(timespec='seconds')}\n")

    def section(title: str, items: "list[str]", hint: str) -> None:
        out.append(f"\n## {title}\n")
        if not items:
            out.append("*(rien)*\n")
            return
        out.append(f"_{hint}_\n\n")
        out.extend(item + "\n" for item in items)

    section("Agents tués", killed_items,
            "Tués par le watchdog/cap — `reason` = sliding/audit/cap. "
            "JSONL conservé dans ce run dir pour forensique.")
    section("Orphelins résiduels", orphans,
            "Tâches restées `claimed`/`to_validate` avec owner en fin de run. "
            "Devrait être vide (récup post-moisson) ; sinon → bug de récup.")
    section("Budget", budget,
            "launched / max_agents et raison d'arrêt (drain / budget / empty).")

    return "".join(out)


def write_run_md(root: Path, run_dir: Path, kills: "list[dict]", launched: int,
                 max_agents: "int | None", stop_reason: str, log=None) -> None:
    """Écrit `RUN.md` **et** `FLAGS.md` (alias, parité `ressources`) dans le run
    dir (R36). I/O fichier seul, jamais de git (R38). Reprise du même run-id :
    **append** (séparateur `---`) — le résumé forensique du run précédent (ses
    kills, ses orphelins) ne s'écrase pas. Best-effort : un échec d'I/O
    ne doit pas empêcher le marqueur terminal de tomber (R39) — l'échec est loggé
    via `log` (`glog`→`orchestrator.log`, sinon stderr) au lieu d'être muet en bg."""
    log = log or _stderr_log
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        md = scan_run(root, run_dir, kills, launched, max_agents, stop_reason)
        for name in ("RUN.md", "FLAGS.md"):
            path = run_dir / name
            if path.exists() and path.stat().st_size > 0:
                with path.open("a", encoding="utf-8") as f:
                    f.write("\n---\n\n" + md)
            else:
                path.write_text(md, encoding="utf-8")
    except OSError as e:
        log(f"run-md-fail {e!r} (best-effort — continue vers le marqueur)")


def kill_tree(proc: subprocess.Popen) -> None:
    """SIGKILL au **process group** entier de `proc` (R40, watchdog.md § 3 Kill).
    Suppose `Popen(start_new_session=True)` : un `claude -p` forke task.py/git/bash ;
    un simple `proc.kill()` ne tue que claude et laisse fuiter ses enfants (multiplié
    par des milliers de spawns). Fallback `proc.kill()` si pas de pgid / déjà mort.
    Idempotent : re-killer un process déjà terminé ne lève pas."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except OSError:                                    # process déjà mort / pas de pgid → repli
        try:
            proc.kill()
        except OSError:
            pass


def _kill_audit(audit_proc: "subprocess.Popen | None") -> None:
    """Kill best-effort un `claude -p` d'audit encore en vol (S17) : l'agent a fini
    / été tué pendant qu'un audit tournait, ou l'audit a dépassé son timeout. Pas de
    fuite de sous-process. Idempotent ; jamais d'exception."""
    if audit_proc is not None and audit_proc.poll() is None:
        kill_tree(audit_proc)


def spawn_capped(cmd: "list[str]", cap_seconds: float, **kwargs) -> "tuple[int, float, bool]":
    """Lance `cmd` (`Popen`) avec un **cap de temps** ; **kill** s'il dépasse (R18).
    Rend `(rc, durée_s, killed)`. Ne s'applique qu'au spawn réel (subprocess) ;
    le fake in-process des tests `run_monitored` n'est pas killable (cf. Q3).

    Cap seul (couche 3). Le spawn réel utilise désormais `spawn_polled` (sliding,
    couche 1, S16) ; `spawn_capped` reste **inchangé** pour les tests S12e/S14 qui
    l'exercent isolément (E22/E23/E40)."""
    start = time.monotonic()
    proc = subprocess.Popen(cmd, start_new_session=True, **kwargs)
    killed = False
    try:
        rc = proc.wait(timeout=cap_seconds)
    except subprocess.TimeoutExpired:
        kill_tree(proc)                                # SIGKILL au groupe entier (R40)
        rc = proc.wait()                               # SIGKILL → rc négatif
        killed = True
    return rc, time.monotonic() - start, killed


def spawn_polled(cmd: "list[str]", cap_seconds: float, sliding_inactivity: float,
                 log_path: Path, poll_interval: float = POLL_INTERVAL_S,
                 audit_cfg: "dict | None" = None,
                 **kwargs) -> "tuple[int, float, bool, str | None]":
    """Spawn **auto-pollant** (watchdog.md § 9, R41). `Popen(start_new_session=True)`
    puis boucle de poll toutes les `poll_interval` s tant que l'agent vit :

    1. **cap absolu** (couche 3) — `elapsed > cap_seconds` → kill, `reason='cap'`.
       Testé **avant** le sliding : le cap prime (R42).
    2. **sliding-inactivity** (couche 1) — aucun append au JSONL par-agent
       (`mtime` de `log_path`) depuis `sliding_inactivity` s → kill, `reason='sliding'`.
       Log absent (agent pas encore démarré) → on retient `start` comme référence
       (pas de faux positif au boot).
    3. **audit sémantique** (couche 2, S17) — si `audit_cfg` est fourni : à
       `audit_after` puis tous les `audit_interval` s, forke un `claude -p` sonnet
       non-bloquant (R46) qui lit un digest de l'agent ; verdict `kill` → kill,
       `reason='audit'` ; **défaut continue** sinon (R47). `audit_cfg=None` →
       couche 2 coupée (`--no-audit`, R49). Le cap (couche 3) prime toujours.

    Rend `(rc, durée_s, killed, reason)` avec `reason ∈ {None,'cap','sliding','audit'}`.
    Reste **bloquant côté thread** → le contrat `spawn(role, task_id)` est inchangé,
    les fakes in-process ne le voient pas (zéro régression S12)."""
    start = time.monotonic()
    proc = subprocess.Popen(cmd, start_new_session=True, **kwargs)
    audit_proc = None                                  # `claude -p` d'audit en cours (S17)
    audit_log_path: "Path | None" = None
    audit_deadline = 0.0                               # cap dur sur l'audit lui-même
    last_audit = start                                 # 1er audit possible à start+audit_after
    while True:
        try:
            rc = proc.wait(timeout=poll_interval)
            _kill_audit(audit_proc)
            return rc, time.monotonic() - start, False, None   # fini seul
        except subprocess.TimeoutExpired:
            pass
        now = time.monotonic()
        # 1. Cap absolu — prime sur tout (R42).
        if now - start > cap_seconds:
            kill_tree(proc)
            _kill_audit(audit_proc)
            rc = proc.wait()
            return rc, time.monotonic() - start, True, "cap"
        # 2. Sliding-inactivity sur le mtime du JSONL par-agent (S14, R42).
        try:
            last = log_path.stat().st_mtime
        except OSError:                                # log pas encore créé → réf = start (wall)
            last = None
        inactivity = (time.time() - last) if last is not None else (now - start)
        if inactivity > sliding_inactivity:
            kill_tree(proc)
            _kill_audit(audit_proc)
            rc = proc.wait()
            return rc, time.monotonic() - start, True, "sliding"
        # 3. Audit sémantique (couche 2, S17) — uniquement si activé (R49).
        if audit_cfg is not None:
            if audit_proc is not None:                 # un audit tourne déjà
                if now > audit_deadline:               # l'audit traîne → kill, défaut continue (§ 8)
                    _kill_audit(audit_proc)
                    _alog = audit_cfg.get("log")       # trace la décision (T2) : sinon le proc
                    if _alog:                          # d'audit est tué en silence (perdu en bg)
                        _alog(f"audit-timeout {audit_cfg['role']} {audit_cfg['task_id']} "
                              f"(n={audit_cfg['n']}, défaut continue)")
                    audit_proc, audit_log_path = None, None
                elif audit_proc.poll() is not None:    # audit terminé → verdict
                    if parse_audit_result(audit_proc, audit_log_path):
                        kill_tree(proc)
                        rc = proc.wait()
                        return rc, time.monotonic() - start, True, "audit"
                    audit_proc, audit_log_path = None, None   # continue → on relâche
            elif (now - start > audit_cfg["after"]
                  and now - last_audit > audit_cfg["interval"]):
                audit_proc, audit_log_path = launch_audit_async(
                    audit_cfg["role"], audit_cfg["task_id"], audit_cfg["n"],
                    log_path, int(now - start), audit_cfg["model"], audit_cfg["run_dir"],
                    cwd=audit_cfg.get("cwd"))
                audit_deadline = now + audit_cfg["timeout"]
                last_audit = now


def _head_sha(root: Path) -> "str | None":
    """SHA de `HEAD` — lecture seule (R19), borne basse de la fenêtre par agent.
    None si pas encore de commit (dépôt vierge)."""
    res = subprocess.run(["git", "rev-parse", "HEAD"],
                         cwd=root, capture_output=True, text=True, check=False)
    sha = res.stdout.strip()
    return sha if res.returncode == 0 and sha else None


def _commit_count(root: Path) -> int:
    """Nb de commits sur `HEAD` — lecture seule (R19). Fallback delta global."""
    res = subprocess.run(["git", "rev-list", "--count", "HEAD"],
                         cwd=root, capture_output=True, text=True, check=False)
    try:
        return int(res.stdout.strip())
    except ValueError:
        return 0


def _own_commit_count(root: Path, before_sha: "str | None", short: "str | None") -> int:
    """Commits **de cet agent** depuis `before_sha` (R19), correct en parallèle.

    Le delta global `HEAD_après - HEAD_avant` est faux dès que `--slots > 1` : il
    inclut les commits des agents concurrents (même historique linéaire, pas de
    worktree isolé). Chaque commit de `task.py` est tagué `… (<short>)` (cf.
    `task.py._do_claim`/`cmd_*`) ; on compte donc, dans la fenêtre `before_sha..HEAD`,
    les seuls commits portant le short de **cet** agent — détecté sur son JSONL
    (`detect_short_sha`). `-F` : le short est un littéral, pas une regex.

    Best-effort : si le short est introuvable (log illisible / agent mort avant
    l'init) ou le dépôt vierge, on retombe sur le delta global (legacy)."""
    if short is None:
        return _commit_count(root) - (_commit_count_at(root, before_sha)
                                      if before_sha else 0)
    rng = f"{before_sha}..HEAD" if before_sha else "HEAD"
    res = subprocess.run(["git", "rev-list", "--count", "-F",
                          f"--grep={short}", rng],
                         cwd=root, capture_output=True, text=True, check=False)
    try:
        return int(res.stdout.strip())
    except ValueError:
        return 0


def _commit_count_at(root: Path, sha: str) -> int:
    """Nb de commits accessibles depuis `sha` — pour le fallback delta global."""
    res = subprocess.run(["git", "rev-list", "--count", sha],
                         cwd=root, capture_output=True, text=True, check=False)
    try:
        return int(res.stdout.strip())
    except ValueError:
        return 0


def _real_capped_spawn(root: Path, run_dir: Path, role: str, task_id: str,
                       cap_seconds: float, n: int,
                       sliding_inactivity: float = DEFAULT_SLIDING_S,
                       audit: "dict | None" = None,
                       log=None,
                       model: str = DEFAULT_WORKER_MODEL,
                       ) -> "tuple[int, float, bool, int, str | None]":
    """Spawn réel `claude -p` **auto-pollant** (R41), avec délta de commits (R19).
    Rend `(rc, durée, killed, nb_commits, reason)` pour l'event de fin (R16/R43) ;
    `reason ∈ {None, 'cap', 'sliding', 'audit'}`.

    **S14 — plomberie log par-agent (R29).** `--output-format stream-json --verbose`
    → chaque event (tool_use, tool_result, message) tombe en JSONL ; `stdout`+`stderr`
    redirigés vers `<run>/agent-<role>-<id>-<n>.jsonl`, flushés au fil de l'eau.
    **S16 — sliding (R42).** `spawn_polled` poll le `mtime` de ce JSONL ; aucun
    append depuis `sliding_inactivity` s → kill (couche 1), en plus du cap (couche 3).
    **S17 — audit (R46/R48).** Si `audit` (dict de réglages) est fourni, on construit
    le `audit_cfg` complet (rôle/tâche/n/run_dir/cwd + seuils) → couche 2 active ;
    `audit=None` (`--no-audit`, R49) → couches 1+3 seules.
    Retire `CLAUDE_CODE_SESSION_ID` pour que l'agent forge un short distinct (gate 2/2)."""
    before_sha = _head_sha(root)
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_SESSION_ID"}
    cmd = ["claude", "-p", prompt_for(role), "--model", model,
           "--allowedTools", _ALLOWED_TOOLS,
           "--output-format", "stream-json", "--verbose"]
    log_path = agent_log_path(run_dir, role, task_id, n)
    audit_cfg = None
    if audit is not None:                              # couche 2 active (R49)
        audit_cfg = {"role": role, "task_id": task_id, "n": n, "run_dir": run_dir,
                     "cwd": root, "log": log, **audit}
    with log_path.open("w", encoding="utf-8") as jf:
        rc, dur, killed, reason = spawn_polled(
            cmd, cap_seconds, sliding_inactivity, log_path, audit_cfg=audit_cfg,
            cwd=root, env=env, stdout=jf, stderr=subprocess.STDOUT)
    # Commits de CET agent (R19, correct en parallèle) : son short tague chaque
    # commit ; le delta global compterait aussi les agents concurrents.
    commits = _own_commit_count(root, before_sha, detect_short_sha(log_path))
    return rc, dur, killed, commits, reason


def run_monitored(root: Path, run_dir: Path, spawn=None,
                  cap_seconds: float = DEFAULT_CAP_S,
                  sliding_inactivity: float = DEFAULT_SLIDING_S,
                  audit: "dict | None" = None,
                  slots: int = 1, max_agents: "int | None" = None,
                  model: str = DEFAULT_WORKER_MODEL) -> int:
    """Enveloppe **observable** de `run` (R20) : **bandeau** (avant le 1er spawn) →
    driver `run` avec un `spawn` **loggé + cappé** (spawn/fin/kill en 1 ligne flushée
    des deux côtés, R16) → **marqueur terminal** en dernière ligne (R17).

    `slots`/`max_agents` sont passés au driver `run` (défaut **séquentiel**
    `slots=1, max_agents=None` → tests monitoring S12 inchangés, R28). Une ligne de
    **config** (`config slots=… max_agents=…`) est loggée **après** le bandeau et
    avant le 1er spawn (`orchestrateur.md` § Bandeau).

    `spawn` injectable (tests : fake in-process ; défaut : spawn réel cappé via
    `spawn_capped`). Ne mute jamais le CSV ; seul git toléré = lecture RO
    (`rev-parse` + `rev-list --count --grep=<short>`) pour le nb de commits par
    agent (R19, scopé au short → correct en parallèle)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / RUN_LOG
    # Reprise du même run-id (relance depuis la même session) : on APPEND — le log
    # est l'historique forensique du run, l'écraser perdrait kills/events du run
    # précédent. Un séparateur horodaté marque la frontière (sans « spawn » ni
    # « flags : », sous-chaînes réservées au monitoring).
    resumed = log_path.exists() and log_path.stat().st_size > 0
    with log_path.open("a", encoding="utf-8") as logfh:
        if resumed:
            log_event(logfh, "─── reprise du run (même run-id) — "
                             "log précédent conservé ci-dessus ───")
        # Callback de log des **décisions de garde** (STALL, orphan-skip,
        # audit-timeout) : sans lui ces décisions partent sur stderr, perdu pour un
        # run backgroundé (T2). On le fait descendre dans `run` (→ `_recover_orphan`)
        # et dans le spawn réel (→ `spawn_polled` audit-timeout).
        def glog(msg: str) -> None:
            log_event(logfh, msg)

        # Bandeau AVANT le 1er spawn (R15/R20) — sur stdout et dans le log.
        # `ts=False` : non horodaté, la commande Monitor doit rester copiable.
        for line in banner(log_path).splitlines():
            log_event(logfh, line, ts=False)
        log_event(logfh, f"config slots={slots} max_agents={max_agents}")

        # spawn(role, id) → None (fake in-process) ou métriques (réel cappé). Le
        # spawn réel produit en plus un JSONL par agent (S14, R29) ; `<n>` vient
        # d'un compteur par (rôle, tâche) thread-safe (R30).
        counter = _SpawnCounter()
        real_spawn = spawn or (lambda role, tid: _real_capped_spawn(
            root, run_dir, role, tid, cap_seconds, counter.next(role, tid),
            sliding_inactivity, audit, log=glog, model=model))

        kills: "list[dict]" = []                       # agents tués → § RUN.md (R35/R37-1)

        def logged(role: str, task_id: str) -> None:
            n = counter._n.get((role, task_id), 0)     # dernier <n> spawné (pour le JSONL)
            log_event(logfh, f"spawn {role} {task_id}")
            info = real_spawn(role, task_id)
            if info is None:                           # fake in-process : pas de métriques
                log_event(logfh, f"end {role} {task_id}")
            else:                                      # réel : rc + durée + commits (R16/R18)
                # 5-tuple (S16, reason explicite) ou 4-tuple legacy (S15, reason
                # dérivé : killed ⇒ cap). `reason ∈ {None, 'cap', 'sliding'}` (R43).
                rc, dur, killed, commits, *rest = info
                reason = rest[0] if rest else ("cap" if killed else None)
                if killed:                             # watchdog (cap/sliding) → reason= (R35/R43)
                    log_event(logfh, f"kill {role} {task_id} "
                                     f"rc={rc} dur={dur:.0f}s commits={commits} reason={reason}")
                    kills.append({"role": role, "id": task_id, "reason": reason,
                                  "jsonl": agent_log_path(run_dir, role, task_id, n).name})
                else:                                  # agent terminé seul → pas de reason (R35)
                    log_event(logfh, f"end {role} {task_id} "
                                     f"rc={rc} dur={dur:.0f}s commits={commits}")

        def recover_log(role: str, task_id: str) -> "Path | None":
            """Résout le JSONL du dernier agent (role, task_id) spawné → `_recover_orphan`
            y détecte le short pour la garde owner==short (R53). Le spawn réel produit
            ce JSONL (S14) ; un fake in-process n'en a pas (`n=0` → chemin absent →
            `detect_short_sha` rend None → skip best-effort)."""
            n = counter._n.get((role, task_id), 0)
            return agent_log_path(run_dir, role, task_id, n) if n else None

        stats: "dict" = {}                             # rempli par `run` : launched + stop_reason
        run(root, logged, slots=slots, max_agents=max_agents, stats=stats,
            recover_log=recover_log, log=glog)
        # Auditabilité a posteriori (S15) : RUN.md/FLAGS.md AVANT le marqueur (R36),
        # forensique gitignored, aucun git mutant (R38).
        write_run_md(root, run_dir, kills, launched=stats.get("launched", 0),
                     max_agents=max_agents, stop_reason=stats.get("stop_reason", "drain"),
                     log=glog)
        log_terminal(logfh, run_dir)                   # marqueur terminal, quoi qu'il arrive (R17)
    return 0


def main(argv: "list[str] | None" = None) -> int:
    # Squelette complet, observable + slotté : bandeau → driver `run` (peek_schedule
    # par slot, production prioritaire) via des spawns réels `claude -p` cappés →
    # marqueur terminal. Deux dimensions de cap (`--slots` / `--max-agents`, parité
    # `ressources`). Le `<run>` dir vit sous `2-consolide/outils/.orchestrator/<id>/`
    # (gitignored) ; `id` = short session de l'orchestrateur, ou PID en repli
    # (préoccupation 3 : observabilité d'un run backgroundé).
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slots", type=int, default=3,
                        help="concurrence : nombre d'agents qui tournent EN MÊME "
                             "TEMPS (default: 3). Slot libéré → agent relancé.")
    parser.add_argument("--max-agents", type=int, default=10,
                        help="budget TOTAL : nombre cumulé d'agents lancés avant "
                             "arrêt des lancements (default: 10), puis drain. "
                             "Garde-fou indépendant de --slots.")
    parser.add_argument("--cap", type=int, default=DEFAULT_CAP_S,
                        help=f"cap-temps dur par agent en secondes (default: "
                             f"{DEFAULT_CAP_S}). Au-delà, l'agent est tué (R18).")
    parser.add_argument("--sliding-inactivity", type=int, default=DEFAULT_SLIDING_S,
                        help=f"sliding-inactivity (couche 1) : un agent sans append "
                             f"à son JSONL depuis ce nb de secondes est tué (default: "
                             f"{DEFAULT_SLIDING_S}). Filet plus court que --cap (R42).")
    parser.add_argument("--audit-after", type=int, default=DEFAULT_AUDIT_AFTER_S,
                        help=f"audit sémantique (couche 2) : on audite un agent "
                             f"AU-DELÀ de ce nb de secondes (default: {DEFAULT_AUDIT_AFTER_S}). "
                             f"Sous ce seuil, aucun audit (fenêtre normale 1-3 min).")
    parser.add_argument("--audit-interval", type=int, default=DEFAULT_AUDIT_INTERVAL_S,
                        help=f"intervalle entre deux audits d'un même agent en "
                             f"secondes (default: {DEFAULT_AUDIT_INTERVAL_S}).")
    parser.add_argument("--audit-model", default=DEFAULT_AUDIT_MODEL,
                        help=f"modèle du `claude -p` d'audit (default: "
                             f"{DEFAULT_AUDIT_MODEL}) — juge un digest, tranche binaire.")
    parser.add_argument("--audit-timeout", type=int, default=DEFAULT_AUDIT_TIMEOUT_S,
                        help=f"cap dur sur le `claude -p` d'audit lui-même en "
                             f"secondes (default: {DEFAULT_AUDIT_TIMEOUT_S}) ; au-delà "
                             f"on le tue et on retient CONTINUE (défaut continue).")
    parser.add_argument("--model", default=DEFAULT_WORKER_MODEL,
                        help=f"modèle PINNÉ des agents workers reduce/map (default: "
                             f"{DEFAULT_WORKER_MODEL}). Sans ce pin l'agent hériterait "
                             f"du défaut UI du lanceur → coût non déterministe.")
    parser.add_argument("--no-audit", action="store_true",
                        help="coupe la couche 2 (audit sémantique) : couches 1+3 "
                             "seules, zéro token d'audit. Audit ACTIF par défaut.")
    parser.add_argument("--dry-run", action="store_true",
                        help="spawn no-op (log seul, ne forke pas, ne mute pas le "
                             "CSV) : montre bandeau + slotting + marqueur sans "
                             "lancer claude. Borné par consecutive_empty + max-agents.")
    args = parser.parse_args(argv)

    if args.slots < 1 or args.max_agents < 1:
        print("error: --slots et --max-agents doivent être ≥ 1", file=sys.stderr)
        return 2
    if os.environ.get("ANTHROPIC_API_KEY"):           # parité ressources : pas de facturation
        print("error: ANTHROPIC_API_KEY est set — refus de lancer pour éviter toute "
              "facturation API. Unset la variable et relance.", file=sys.stderr)
        return 2

    root = _store.resolve_root()
    run_id = (os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()[:8]
              or f"pid{os.getpid()}")
    run_dir = _store.orchestrator_dir(root) / run_id

    # --dry-run : spawn no-op (ne forke pas, ne mute pas le CSV). L'empreinte ne
    # bouge donc jamais → consecutive_empty ≥ EMPTY_LIMIT borne la boucle, en plus
    # de --max-agents (préoccupation 4 : caps concurrence + budget).
    spawn = (lambda role, task_id: None) if args.dry_run else None
    # Audit sémantique (couche 2) : actif par défaut, coupé par `--no-audit` (R49).
    # Le dict porte les seuils ; `_real_capped_spawn` y ajoute rôle/tâche/n/run_dir/cwd.
    audit = None if args.no_audit else {
        "after": args.audit_after, "interval": args.audit_interval,
        "model": args.audit_model, "timeout": args.audit_timeout}
    return run_monitored(root, run_dir, spawn=spawn, cap_seconds=args.cap,
                         sliding_inactivity=args.sliding_inactivity, audit=audit,
                         slots=args.slots, max_agents=args.max_agents,
                         model=args.model)


if __name__ == "__main__":
    raise SystemExit(main())
