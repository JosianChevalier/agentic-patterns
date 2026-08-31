#!/usr/bin/env python3
"""Template — orchestre des sous-agents `claude -p` en parallèle pour drainer
une queue gérée par un script de type `file-validation/` (claim/release dans
un tableau markdown). Cf. `README.md` du dossier.

Chaque sous-agent tourne en headless, demande UNE tâche via `claim.py next`
(le script choisit, l'agent n'a pas à raisonner sur la priorité), la finit, et
sort. L'orchestrateur maintient N slots en parallèle, relance dès qu'un slot se
libère, s'arrête au cap dur ou si la queue est vide (2 sorties consécutives
sans commit).

## Deux dimensions de cap — `--slots` vs `--max-agents`

Ce sont des cadrans **orthogonaux** : ne pas les confondre.

- `--slots` (default 3) : **concurrence**. Combien de sous-agents tournent
  *en même temps*. C'est la largeur du pipeline à un instant t. Limité par
  ton CPU, ta tolérance aux conflits git, et le rate-limit Claude. À chaque
  fois qu'un slot se libère, l'orchestrateur en relance un (si budget restant).

- `--max-agents` (default 10) : **budget total** sur tout le run. Nombre
  cumulé de sous-agents que l'orchestrateur acceptera de lancer avant
  d'arrêter, peu importe combien tournent en parallèle. C'est un garde-fou
  contre une queue qui ne se viderait jamais (boucle, bug, mauvaise estimation).
  Une fois atteint, plus aucun lancement même si des slots sont libres ;
  l'orchestrateur draine les agents en cours puis sort.

Exemple : `--slots 3 --max-agents 30` → 3 agents en parallèle, le run s'arrête
après 30 lancements cumulés (ou avant si la queue se vide). Penser
`--max-agents` ≈ « combien de tâches *au maximum* je veux que ce run traite ».

## Timeout dynamique à 3 couches

1. **Sliding watchdog** : kill direct si aucun append au log JSONL depuis
   `--sliding-inactivity` secondes (default 180). Détecte les agents morts /
   bloqués / en attente silencieuse.
2. **Audit-agent intermédiaire** : à partir de `--audit-after` secondes (default
   300), puis toutes les `--audit-interval` (default 60), un `claude -p` lit le
   log de l'agent en cours et juge si le pattern ressemble à du progrès ou à un
   rabbit hole. Verdict binaire kill/continue. En cas d'erreur d'audit → continue
   (safe default).
3. **Cap absolu** : `--timeout` (default 600). Kill systématique au-delà, peu
   importe l'activité ou les verdicts précédents.

Dans les trois cas : kill + `force_release_abandon()` du verrou orphelin si
l'agent avait claim une cellule sans la release.

Six zones marquées `# ADAPT:` doivent être éditées pour brancher l'orchestrateur
sur un domaine concret. Reste fonctionnel (watchdog, scheduling, logs).
"""
import argparse
import datetime
import io
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

# =============================================================================
# Constantes de chemin — ajuster pour ton domaine.
# =============================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# ADAPT: chemin du TODO.md que ton domaine maintient (queue de travail).
TODO = REPO_ROOT / "<DOMAINE>" / "TODO.md"
# ADAPT: où mettre les logs de chaque run. Convention : <couche>/outils/<domaine>/runs/<ts>/.
RUNS_DIR = REPO_ROOT / "<couche>" / "outils" / "<DOMAINE>" / "runs"
# ADAPT: nom de projet pour le sous-dossier $TMPDIR (heartbeats hors repo).
TMP_PROJECT = "<projet>"

# =============================================================================
# ADAPT #1 — SUBAGENT_PROMPT
# Décris la tâche à un sous-agent qui ne fera QU'UNE itération du pipeline puis
# sortira. Doit pointer vers le PROTOCOL du domaine, donner la procédure
# (claim.py next → lire `TASK:` → travail → release), insister sur « tu ne
# choisis pas ta tâche », expliquer la posture face au doute (`signalé`), et
# lister les permissions (synchro avec --allowedTools dans launch_subagent).
#
# Voir `1-sources/outils/ressources/orchestrate.py` pour un exemple complet et travaillé.
# =============================================================================

SUBAGENT_PROMPT = """\
Tu es lancé par un orchestrateur (`<couche>/outils/<DOMAINE>/orchestrate.py`) pour faire
UNE tâche du pipeline `<DOMAINE>`, puis sortir.

## Tu ne choisis PAS ta tâche — le script te la donne

C'est `<couche>/outils/<DOMAINE>/claim.py next` qui choisit la tâche et la réserve, sous
flock, côté script. Toi tu exécutes ce qu'on te donne. **Ne lis pas le TODO
pour décider quoi prendre** : la sélection se fait dans le verrou → pas de
course, pas de claim qui échoue parce qu'un autre agent est passé avant toi.

## Procédure

1. Lis `<DOMAINE>/PROTOCOL.md` (protocole complet : étapes, critères, résultats).
2. `<couche>/outils/<DOMAINE>/claim.py next` (whitelisté). Le script imprime une ligne
   `TASK: <step> <slug>`.
   - S'il sort en erreur (« aucune tâche disponible ») : sors immédiatement
     sans toucher au repo. **Pas de retry** — le script a déjà parcouru toute
     la queue sous verrou ; réessayer ne changera rien.
3. Lis la ligne `TASK:` → tu connais <step> et <slug>. Fais le boulot selon la
   section <step> du protocole.
4. `<couche>/outils/<DOMAINE>/release.py <step> <slug> <result>`.
5. Sors.

Plafonds de session du protocole : ignore-les — tu ne fais qu'UNE tâche,
l'orchestrateur s'occupe du volume.

# ADAPT: ajouter la section "Permissions strictes" (allowlist synchronisée
# avec --allowedTools dans launch_subagent ci-dessous), la section "Posture
# face au doute" (canal signalé), et les "Restrictions git". Voir
# `1-sources/outils/ressources/orchestrate.py` SUBAGENT_PROMPT pour un patron complet.
"""


AUDIT_PROMPT_TEMPLATE = """\
Tu es un auditeur d'orchestrateur. Un sous-agent `claude -p` tourne depuis
{elapsed}s sur l'étape **{step}** du pipeline `<DOMAINE>`, slug **{slug}**.
Son log JSONL est à `{log_path}` (un event `claude -p` stream-json par ligne).

**Ta tâche** : lire ce log et décider si l'agent **progresse** ou s'il est
**dans un rabbit hole** (bloqué, en boucle, ou hors-piste).

Signaux de patinage :
- `tool_result` avec `is_error: true` répétés (commande refusée par l'allowlist).
- Même `tool_use` identique répété (boucle d'outil).
- `text` events qui contiennent "je vais essayer", "je n'arrive pas",
  "permission denied".
- Long monologue de raisonnement sans tool_use depuis 2+ min.

Signaux de progrès :
- Suite cohérente de tool_use qui correspond au protocole de l'étape `{step}`.
- Edits cohérents des fichiers du slug en cours.

**Sortie** : termine par une ligne EXACTEMENT au format :

    VERDICT: kill

ou

    VERDICT: continue

Avec une seule phrase de justification juste avant. Pas de markdown, pas de
gras, pas de longue analyse. Tu n'as que `Read` autorisé.
"""


# =============================================================================
# ADAPT #2 — Regex de parsing des sujets de commit.
# Doivent matcher le format des commits produits par claim.py / release.py du
# domaine (tous estampillés du `<short>` final, indispensable pour attribuer un
# commit à un agent quand plusieurs commitent en parallèle).
#
# Deux formats de référence :
#
# - file-validation de base (`task.py next`), <step> ∈ {rédaction, validation} :
#     Claim:   "Claim <step> <slug> (<short>)"
#     Release: "Finish <step> <slug> [verdict] (<short>)"  ou  "Release <step> <slug> (<short>)"
#   →  CLAIM_RE   = r"^Claim (rédaction|validation) (\S+) \(([0-9a-z]{8})\)$"
#      RELEASE_RE = r"^(?:Finish|Release) (rédaction|validation) (\S+)(?: \S+)? \(([0-9a-z]{8})\)$"
#
# - domaine multi-étapes enrichi (cf. 1-sources/outils/ressources) :
#     Claim:   "Claim <step> <slug> (<short>)"
#     Release: "<Step> <slug>: <result> (<short>)"
# =============================================================================

# ADAPT: liste tes étapes (en minuscules pour CLAIM, capitalisées pour RELEASE).
CLAIM_RE = re.compile(r"^Claim (step1|step2|step3) (\S+) \(([0-9a-f]{8})\)$")
RELEASE_RE = re.compile(r"^(Step1|Step2|Step3) (\S+): .+ \(([0-9a-f]{8})\)$")
# Générique — extrait `(short)` à la fin du sujet, n'importe quel format.
COMMIT_SHORT_RE = re.compile(r"\(([0-9a-f]{8})\)$")


# =============================================================================
# Helpers — pas de modification nécessaire.
# =============================================================================

def heartbeat_path(run_dir: Path, agent_id: int) -> Path:
    """Path du fichier heartbeat d'un agent, sous $TMPDIR (cleanup OS auto).

    Sert si tu veux qu'un long Bash tool (extract, conversion lourde…) écrive
    régulièrement sur ce path pour signaler qu'il est vivant — l'orchestrateur
    regarde `max(log_mtime, heartbeat_mtime)` pour le sliding watchdog. Si tu
    n'as pas ce besoin : laisse tel quel, le sliding regardera juste le log.
    """
    tmp_root = Path(os.environ.get("TMPDIR", "/tmp")) / TMP_PROJECT / "orchestrate" / run_dir.name
    tmp_root.mkdir(parents=True, exist_ok=True)
    return tmp_root / f"agent-{agent_id:02d}.heartbeat"


def now_iso() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def kill_tree(proc: subprocess.Popen) -> None:
    """SIGKILL le process group entier de `proc` (subagent + ses subprocess
    `claim.py`, `release.py`, etc.). Suppose que `proc` a été lancé avec
    `start_new_session=True`. Fallback sur `proc.kill()` si le PGID a déjà
    disparu (process déjà mort) ou OS non-posix."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError, AttributeError):
        try:
            proc.kill()
        except OSError:
            pass


def head_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    ).stdout.strip()


def commits_since(sha: str) -> list[str]:
    """Subjects of commits added since <sha> (most recent first)."""
    if not sha:
        return []
    out = subprocess.run(
        ["git", "log", f"{sha}..HEAD", "--pretty=format:%s"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    ).stdout.strip()
    return out.splitlines() if out else []


def detect_short_sha(log_path: Path) -> str | None:
    """Parse les premières lignes du log stream-json d'un sous-agent pour en
    extraire son `session_id` (premier event `type=system, subtype=init`).
    Retourne les 8 premiers chars, ou None si pas encore trouvable.

    Sert à attribuer correctement les commits à un agent dans un contexte où
    plusieurs sous-agents commitent en parallèle sur le même HEAD."""
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


def filter_commits(commits: list[str], short: str | None) -> list[str]:
    """Garde uniquement les commits dont le subject finit par `(short)`. Si
    `short is None`, retourne la liste telle quelle (fallback bug-compat)."""
    if short is None:
        return commits
    return [c for c in commits if (m := COMMIT_SHORT_RE.search(c)) and m.group(1) == short]


def detect_orphan_claims(commits: list[str]) -> list[tuple[str, str, str]]:
    """Parse subjects of an agent's commits ; return (step, slug, short) for
    each Claim without a matching release in the same commit list."""
    claims: set[tuple[str, str, str]] = set()
    releases: set[tuple[str, str, str]] = set()
    for subj in commits:
        if m := CLAIM_RE.match(subj):
            claims.add((m.group(1), m.group(2), m.group(3)))
        elif m := RELEASE_RE.match(subj):
            releases.add((m.group(1).lower(), m.group(2), m.group(3)))
    return [k for k in claims if k not in releases]


def current_step_slug(base_sha: str, short: str | None) -> tuple[str, str] | None:
    """Inspect commits since `base_sha` (filtered to commits authored by the
    agent identified by `short`); return (step, slug) of the most recent
    Claim that has no matching Release. None if no active claim yet — agent is
    either pre-claim or already done."""
    commits = filter_commits(commits_since(base_sha), short)
    # commits_since returns most-recent-first ; reverse for chronological order
    pending: list[tuple[str, str, str]] = []
    releases: set[tuple[str, str, str]] = set()
    for subj in reversed(commits):
        if m := CLAIM_RE.match(subj):
            pending.append((m.group(1), m.group(2), m.group(3)))
        elif m := RELEASE_RE.match(subj):
            releases.add((m.group(1).lower(), m.group(2), m.group(3)))
    for step, slug, short in reversed(pending):
        if (step, slug, short) not in releases:
            return step, slug
    return None


def launch_audit_async(agent_id: int, log_path: Path, step: str, slug: str,
                       elapsed: int, model: str, run_dir: Path,
                       ) -> tuple[subprocess.Popen, Path, io.TextIOBase]:
    """Lance un `claude -p` d'audit non-bloquant. Retourne (proc, audit_log_path,
    audit_file). L'appelant poll `proc.poll()` ; quand terminé, passe le tuple
    à `parse_audit_result()` qui ferme le fichier et lit le verdict."""
    prompt = AUDIT_PROMPT_TEMPLATE.format(
        elapsed=elapsed, step=step, slug=slug, log_path=log_path,
    )
    audit_log = run_dir / f"audit-{agent_id:02d}-{now_iso()}.log"
    cmd = [
        "claude", "-p", prompt,
        "--allowedTools", "Read",
        "--model", model,
        "--output-format", "text",
    ]
    audit_file = open(audit_log, "w")
    audit_file.write(
        f"# audit agent-{agent_id:02d} started at {now_iso()}\n"
        f"# step={step} slug={slug} elapsed={elapsed}s model={model}\n\n"
    )
    audit_file.flush()
    proc = subprocess.Popen(
        cmd, stdout=audit_file, stderr=subprocess.STDOUT, cwd=REPO_ROOT,
        start_new_session=True,
    )
    return proc, audit_log, audit_file


def parse_audit_result(audit_proc: subprocess.Popen, audit_log_path: Path,
                       audit_file: io.TextIOBase, agent_id: int, step: str,
                       slug: str, elapsed: int, log) -> bool:
    """À appeler quand `audit_proc.poll() is not None`. Ferme le fichier de log,
    lit le verdict, retourne True si kill / False sinon (default continue sur
    rc != 0 ou verdict unparseable)."""
    try:
        audit_file.close()
    except OSError:
        pass
    rc = audit_proc.returncode
    try:
        out = audit_log_path.read_text()
    except OSError:
        out = ""
    if rc != 0:
        log(f"  ! audit agent-{agent_id:02d} rc={rc} — default continue")
        return False
    last_verdict = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("VERDICT:"):
            last_verdict = s.split(":", 1)[1].strip().lower()
    if last_verdict == "kill":
        log(f"  ! audit agent-{agent_id:02d} verdict=KILL ({step}/{slug} @{elapsed}s)")
        return True
    if last_verdict == "continue":
        log(f"  ✓ audit agent-{agent_id:02d} verdict=continue ({step}/{slug} @{elapsed}s)")
        return False
    log(f"  ! audit agent-{agent_id:02d} verdict unparseable ({last_verdict!r}) — default continue")
    return False


# =============================================================================
# ADAPT #3 — force_release_abandon()
# Appelé quand l'orchestrateur kill un agent qui avait claim une cellule sans
# la release. Doit déléguer à `release.py --force-abandon-orphan <short>` du
# domaine, qui acquière le flock et écrit un commit
# "Auto-abandon <step> <slug> (orchestrator: agent <short> exited without release)".
# =============================================================================

# ADAPT: chemin du release.py du domaine.
RELEASE_SCRIPT = REPO_ROOT / "tools" / "<DOMAINE>" / "release.py"


def force_release_abandon(step: str, slug: str, short: str, log) -> None:
    """Clear a stale lock left by a sub-agent that exited without releasing.
    Délègue à `release.py --force-abandon-orphan` qui acquière le lock (flock)
    avant le read→modify→write — pas de TOCTOU avec un claim/release concurrent.

    Best-effort : on log et on continue si le commit échoue (pre-commit hook,
    lock git transient, etc.). Le verrou orphelin sera nettoyé au run suivant
    ou par `release.py <step> <slug> abandon` manuel."""
    cmd = [
        sys.executable, str(RELEASE_SCRIPT),
        "--repo-root", str(REPO_ROOT),
        "--force-abandon-orphan", short,
        step, slug, "abandon",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                cwd=REPO_ROOT, check=True)
        out = (result.stdout or "").strip()
        if out:
            log(f"  ! {out}")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        log(f"  ! force_release_abandon failed (rc={e.returncode}): {err}")
    except OSError as e:
        log(f"  ! force_release_abandon exec failed: {e}")


# =============================================================================
# ADAPT #4 — queue_has_work()
# Lit le TODO.md du domaine et retourne True si une cellule est encore pickable.
# Heuristique grossière : pas besoin de répliquer la logique exacte de claim.py
# (prereqs, gardes…). Si l'orchestrateur croit qu'il reste du boulot mais
# qu'aucun sous-agent ne picke rien, les 2 sorties vides consécutives feront
# stopper proprement.
#
# Le code ci-dessous suppose le format file-validation enrichi (cf. EXAMPLE_TODO.md) :
# - colonnes : Slug | ... | <Step1> | <Step2> | ... | Verrou
# - Verrou = "—" → libre ; sinon locked
# - cellule "—" ou vide → pickable
# - cellule de type compteur ("k/N") avec k<N → reclaimable
# Adapter au format réel de ton tableau.
# =============================================================================

# ADAPT: indices/nb de colonnes du TODO de ton domaine.
NUM_COLS = 9          # nb total de colonnes (incl. Slug et Verrou)
STEP_COL_RANGE = (3, 8)   # range(start, stop) — indices des cellules d'étape
VERROU_COL = 8        # index de la colonne Verrou
# ADAPT: cellules considérées "encore reclaimables" pour une étape à compteur
# (laisse vide si tu n'as pas d'étape à compteur).
RECLAIMABLE_COUNTER = {"0/2", "1/2"}
COUNTER_STEP_COL = 7  # index de l'étape à compteur (ou None)


def queue_has_work() -> bool:
    """True si au moins une ligne du TODO a une cellule pickable et pas de
    verrou. Heuristique grossière — cf. commentaire ci-dessus."""
    content = TODO.read_text().splitlines()
    for line in content:
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < NUM_COLS or cells[0] in ("Slug", "---"):
            continue
        verrou = cells[VERROU_COL]
        if verrou and verrou != "—":
            continue  # locked, skip
        for i in range(*STEP_COL_RANGE):
            v = cells[i]
            if not v or v == "—":
                return True
            if i == COUNTER_STEP_COL and v in RECLAIMABLE_COUNTER:
                return True
    return False


# =============================================================================
# ADAPT #5 — launch_subagent() / --allowedTools
# La liste d'outils autorisés doit être strictement synchronisée avec ce que
# SUBAGENT_PROMPT décrit. Tout `Bash(<commande>)` doit lister un pattern
# explicite — pas de wildcard global. C'est la sécurité du run : un agent
# qui essaie `rm -rf` ou `curl` sera refusé silencieusement.
# =============================================================================

def launch_subagent(agent_id: int, run_dir: Path, model: str | None,
                    dry_run: bool) -> tuple[subprocess.Popen | None, io.TextIOBase | None]:
    log_path = run_dir / f"agent-{agent_id:02d}.log"
    cmd = [
        "claude", "-p", SUBAGENT_PROMPT,
        # Strict allowlist : tout le reste est refusé silencieusement.
        # ADAPT: synchroniser avec SUBAGENT_PROMPT (section "Permissions").
        "--allowedTools",
        "Read", "Edit", "Write", "Glob", "Grep",
        # ADAPT: les scripts précis de ton pipeline, un par entrée.
        "Bash(<couche>/outils/<DOMAINE>/claim.py *)",
        "Bash(<couche>/outils/<DOMAINE>/release.py *)",
        # "Bash(<couche>/outils/<DOMAINE>/<autre-script>.py *)",
        # Git read-only — quasi toujours utile.
        "Bash(git status*)", "Bash(git diff*)",
        "Bash(git log*)", "Bash(git show*)",
        # stream-json + verbose : chaque event flushé en JSONL temps réel.
        # NE PAS retirer — le sliding watchdog et l'audit-agent lisent ce log.
        "--output-format", "stream-json", "--verbose",
    ]
    if model:
        cmd += ["--model", model]
    if dry_run:
        print(f"[dry-run] agent-{agent_id:02d}: would launch claude -p (log → {log_path})")
        return None, None
    log_file = open(log_path, "w")
    log_file.write(f"# orchestrator: launching agent-{agent_id:02d} at {now_iso()}\n")
    log_file.write(f"# cmd: {' '.join(repr(c) if ' ' in c else c for c in cmd[:4])} <prompt> ...\n\n")
    log_file.flush()
    hb_path = heartbeat_path(run_dir, agent_id)
    proc = subprocess.Popen(
        cmd, stdout=log_file, stderr=subprocess.STDOUT, cwd=REPO_ROOT,
        start_new_session=True,
        env={**os.environ, "ORCHESTRATE_HEARTBEAT": str(hb_path)},
    )
    return proc, log_file


# =============================================================================
# ADAPT #6 — scan_flags()
# Construit le FLAGS.md de fin de run : lignes à arbitrer humainement (cellules
# `signalé`, verrous orphelins, etc.). Le format dépend du tableau de ton
# domaine. Le squelette ci-dessous reprend le pattern de l'instance vivante —
# adapte les noms de colonnes / sections.
# =============================================================================

def scan_flags(run_dir: Path) -> str:
    """Build the final FLAGS.md content by scanning the TODO table + prose."""
    lines = TODO.read_text().splitlines()

    signaled: list[str] = []
    locked: list[str] = []
    # ADAPT: ajouter d'autres listes selon les sections que tu veux dans FLAGS.md
    # (ex. compteur Validate à 0/N après corrigé, lignes en abandon, etc.).

    # ADAPT: noms des étapes dans l'ordre des colonnes (matchent STEP_COL_RANGE).
    step_names = ("Step1", "Step2", "Step3")

    for line in lines:
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < NUM_COLS or cells[0] in ("Slug", "---"):
            continue
        slug = cells[0]
        for i, name in enumerate(step_names, start=STEP_COL_RANGE[0]):
            v = cells[i]
            if v.startswith("signalé"):
                signaled.append(f"- `{slug}` — {name} : {v}")
        verrou = cells[VERROU_COL]
        if verrou and verrou != "—":
            locked.append(f"- `{slug}` — Verrou : {verrou}")

    # ADAPT: si ton protocole a une convention "relecture humaine" en prose,
    # scanner ici. Sinon retirer ce bloc.
    prose_review: list[str] = []
    raw = TODO.read_text()
    for m in re.finditer(r"^.*relecture humaine.*$", raw, flags=re.MULTILINE | re.IGNORECASE):
        line = m.group(0)
        if line.startswith("| "):
            continue
        text = line.strip().lstrip("-").strip()
        prose_review.append(f"- {text}")

    out: list[str] = []
    out.append(f"# Flags — run {run_dir.name}\n")
    out.append(f"Généré : {datetime.datetime.now().isoformat(timespec='seconds')}\n")

    def section(title: str, items: list[str], hint: str) -> None:
        out.append(f"\n## {title}\n")
        if not items:
            out.append("*(rien)*\n")
            return
        out.append(f"_{hint}_\n\n")
        out.extend(item + "\n" for item in items)

    section("Cellules `signalé`", signaled,
            "Étapes bloquées — arbitrage humain nécessaire.")
    section("Verrous non libérés", locked,
            "Lock potentiellement orphelin (sous-agent crashé ?). "
            "Vérifier l'âge ; si vieux, `release.py <step> <slug> abandon`.")
    section("Mentions « relecture humaine » dans le TODO", prose_review,
            "Lignes en prose (hors tableau).")

    return "".join(out)


# =============================================================================
# Main — scheduler, watchdog 3 couches, harvest. Pas d'adaptation usuelle.
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--slots", type=int, default=3,
                        help="concurrence : nombre de sous-agents qui tournent "
                             "EN MÊME TEMPS (default: 3). Quand un slot se libère, "
                             "un nouvel agent est relancé pour le remplacer.")
    parser.add_argument("--max-agents", type=int, default=10,
                        help="budget TOTAL du run : nombre cumulé de sous-agents "
                             "que l'orchestrateur lancera avant d'arrêter (default: 10). "
                             "Garde-fou indépendant de --slots. Une fois atteint, "
                             "plus aucun lancement même si des slots sont libres ; "
                             "drain des agents en cours puis sortie.")
    parser.add_argument("--model", default=None,
                        help="forcer un modèle (ex: 'sonnet', 'opus'). Default: hérité.")
    parser.add_argument("--stagger", type=float, default=2.0,
                        help="délai (s) entre les lancements pour laisser les commits se sérialiser")
    parser.add_argument("--timeout", type=int, default=600,
                        help="cap absolu par sous-agent en secondes (default: 600 = 10 min). "
                             "Kill systématique au-delà, peu importe l'activité ou l'audit.")
    parser.add_argument("--sliding-inactivity", type=int, default=180,
                        help="kill si aucun append au log JSONL depuis N secondes "
                             "(default: 180). Détecte les agents morts/silencieux.")
    parser.add_argument("--audit-after", type=int, default=300,
                        help="à partir de quand l'audit-agent peut tourner (default: 300s). "
                             "En deçà, on fait confiance au sliding watchdog seul.")
    parser.add_argument("--audit-interval", type=int, default=60,
                        help="intervalle minimum entre deux audits d'un même sous-agent "
                             "(default: 60s).")
    parser.add_argument("--audit-model", default="sonnet",
                        help="modèle pour l'audit-agent (default: sonnet). Tâche courte : "
                             "lire un log JSONL et trancher kill/continue.")
    parser.add_argument("--audit-timeout", type=int, default=90,
                        help="timeout d'un audit-agent en secondes (default: 90). "
                             "Au-delà, l'audit est killé et le verdict par défaut est continue.")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche ce qui serait fait sans lancer claude -p")
    args = parser.parse_args()

    if args.slots < 1 or args.max_agents < 1:
        sys.exit("error: --slots et --max-agents doivent être ≥ 1")

    if not TODO.exists():
        sys.exit(f"error: {TODO} introuvable")

    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("error: ANTHROPIC_API_KEY est set — refus de lancer pour éviter "
                 "toute facturation API. Unset la variable et relance.")

    ts = now_iso()
    run_dir = RUNS_DIR / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    orch_log = open(run_dir / "orchestrator.log", "w")

    def log(msg: str) -> None:
        line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line)
        orch_log.write(line + "\n")
        orch_log.flush()

    log(f"run dir: {run_dir.relative_to(REPO_ROOT)}")
    log(f"slots={args.slots} max_agents={args.max_agents} "
        f"model={args.model or 'default'} dry_run={args.dry_run}")

    if not queue_has_work():
        log("queue vide à l'init — rien à faire.")
        orch_log.close()
        return

    launched = 0
    consecutive_empty = 0
    # (id, proc, base_sha, start, log_file)
    running: list[tuple[int, subprocess.Popen | None, str, float, io.TextIOBase | None]] = []
    last_audit_at: dict[int, float] = {}  # agent_id -> last audit timestamp (= terminé)
    pending_audits: dict[int, tuple[subprocess.Popen, Path, io.TextIOBase, float, str, str]] = {}
    # agent_id -> (audit_proc, audit_log_path, audit_file, audit_start, step, slug)
    agent_short: dict[int, str | None] = {}  # agent_id -> first 8 chars of session_id

    def ensure_short(aid: int) -> str | None:
        """Lazily detect and cache the agent's session_id short SHA from its
        log. Returns None until the init event is visible in the log."""
        cached = agent_short.get(aid)
        if cached is not None:
            return cached
        sh = detect_short_sha(run_dir / f"agent-{aid:02d}.log")
        if sh:
            agent_short[aid] = sh
            log(f"agent-{aid:02d} short_sha={sh}")
        return sh

    def cleanup_pending_audit(aid: int) -> None:
        """Kill et drop l'audit en cours pour `aid`, s'il y en a un. Idempotent."""
        if aid not in pending_audits:
            return
        audit_proc, _, audit_file, _, _, _ = pending_audits.pop(aid)
        if audit_proc.poll() is None:
            kill_tree(audit_proc)
        try:
            audit_file.close()
        except OSError:
            pass

    def check_agent_deadline(aid: int, proc: subprocess.Popen, base: str,
                             start: float) -> str | None:
        """Returns None if agent should keep running, else a short reason string
        ('finished' | 'cap' | 'sliding' | 'audit'). Side-effect : kills the
        process when returning a kill reason. Poll aussi l'audit non-bloquant
        de cet agent s'il y en a un, et en lance un nouveau quand la fenêtre
        est ouverte."""
        if proc is None:
            return None
        if proc.poll() is not None:
            cleanup_pending_audit(aid)
            return "finished"
        now = time.time()
        elapsed = now - start

        # 1. Poll l'audit en cours pour cet agent (non-bloquant).
        if aid in pending_audits:
            audit_proc, audit_log_path, audit_file, audit_start, step, slug = pending_audits[aid]
            if audit_proc.poll() is not None:
                verdict_kill = parse_audit_result(
                    audit_proc, audit_log_path, audit_file, aid, step, slug,
                    int(elapsed), log,
                )
                del pending_audits[aid]
                last_audit_at[aid] = time.time()
                if verdict_kill:
                    kill_tree(proc)
                    return "audit"
            elif now - audit_start > args.audit_timeout:
                log(f"  ! audit agent-{aid:02d} timeout ({args.audit_timeout}s) — kill audit, default continue")
                cleanup_pending_audit(aid)
                last_audit_at[aid] = time.time()

        # 2. Cap absolu — kill l'agent même si un audit tourne.
        if elapsed > args.timeout:
            log(f"agent-{aid:02d} cap absolu ({args.timeout}s) — kill")
            kill_tree(proc)
            cleanup_pending_audit(aid)
            return "cap"

        # 3. Sliding watchdog. Regarde mtime log JSONL ET heartbeat.
        log_path = run_dir / f"agent-{aid:02d}.log"
        try:
            mtime = log_path.stat().st_mtime
        except FileNotFoundError:
            mtime = start
        try:
            hb_mtime = heartbeat_path(run_dir, aid).stat().st_mtime
        except FileNotFoundError:
            hb_mtime = 0
        inactivity = now - max(mtime, hb_mtime)
        if inactivity > args.sliding_inactivity:
            log(f"agent-{aid:02d} sliding watchdog ({int(inactivity)}s sans append log+heartbeat) — kill")
            kill_tree(proc)
            cleanup_pending_audit(aid)
            return "sliding"

        # 4. Lancer un audit async si pas déjà en cours et fenêtre OK.
        if aid not in pending_audits:
            last_audit = last_audit_at.get(aid, start)
            if elapsed > args.audit_after and now - last_audit > args.audit_interval:
                short = ensure_short(aid)
                if short is None:
                    # Init event pas encore visible → retry au prochain poll.
                    return None
                step_slug = current_step_slug(base, short) or ("unknown", "unknown")
                step, slug = step_slug
                log(f"audit agent-{aid:02d} async start "
                    f"(elapsed={int(elapsed)}s, step={step}, slug={slug})")
                audit_proc, audit_log_path, audit_file = launch_audit_async(
                    aid, log_path, step, slug, int(elapsed),
                    args.audit_model, run_dir,
                )
                pending_audits[aid] = (
                    audit_proc, audit_log_path, audit_file, time.time(), step, slug,
                )

        return None

    def harvest(idx: int) -> None:
        """Pop running[idx], log summary, auto-abandon orphan claims, update
        consecutive_empty."""
        nonlocal consecutive_empty
        agent_id, proc, base, start, log_file = running.pop(idx)
        last_audit_at.pop(agent_id, None)
        cleanup_pending_audit(agent_id)
        short = ensure_short(agent_id)
        duration = int(time.time() - start)
        if proc is not None and proc.poll() is None:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        rc = proc.returncode if proc else -1
        all_commits = commits_since(base)
        new_commits = filter_commits(all_commits, short)
        did_work = len(new_commits) > 0
        consecutive_empty = 0 if did_work else consecutive_empty + 1
        log(
            f"agent-{agent_id:02d} exited rc={rc} duration={duration}s "
            f"commits={len(new_commits)} (short={short or '??'}) "
            f"consecutive_empty={consecutive_empty}"
        )
        if short is None and all_commits:
            log(f"  ! short_sha non détecté — filtrage commits désactivé, fallback bug-compat")
        for c in new_commits:
            log(f"  + {c}")
        for step, slug, ag_short in detect_orphan_claims(new_commits):
            force_release_abandon(step, slug, ag_short, log)
        if log_file is not None:
            try:
                log_file.close()
            except OSError:
                pass

    try:
        while launched < args.max_agents and consecutive_empty < 2:
            # Fill slots
            while len(running) < args.slots and launched < args.max_agents:
                agent_id = launched + 1
                base = head_sha() if not args.dry_run else ""
                proc, log_file = launch_subagent(agent_id, run_dir, args.model, args.dry_run)
                launched += 1
                running.append((agent_id, proc, base, time.time(), log_file))
                log(f"launched agent-{agent_id:02d} (running: {len(running)})")
                if args.dry_run:
                    running.clear()
                    break
                time.sleep(args.stagger)

            if args.dry_run:
                break

            # Wait for any agent to finish (poll)
            time.sleep(2)
            finished_idx = None
            for idx, (aid, proc, base, start, _lf) in enumerate(running):
                reason = check_agent_deadline(aid, proc, base, start)
                if reason is not None:
                    finished_idx = idx
                    break

            if finished_idx is None:
                continue

            harvest(finished_idx)

            if not queue_has_work():
                log("queue détectée vide — arrêt après les sous-agents en cours.")
                break

        # Drain remaining slots — keep applying the 3-layer check until each
        # agent exits (or hits a kill condition).
        log(f"drain : {len(running)} sous-agent(s) en cours")
        while running:
            time.sleep(2)
            finished_idx = None
            for idx, (aid, proc, base, start, _lf) in enumerate(running):
                reason = check_agent_deadline(aid, proc, base, start)
                if reason is not None:
                    finished_idx = idx
                    break
            if finished_idx is None:
                continue
            harvest(finished_idx)

    except KeyboardInterrupt:
        log("KeyboardInterrupt — kill des sous-agents et audits en cours")
        for aid in list(pending_audits):
            cleanup_pending_audit(aid)
        for aid, proc, _, _, log_file in running:
            if proc and proc.poll() is None:
                kill_tree(proc)
            if log_file is not None:
                try:
                    log_file.close()
                except OSError:
                    pass

    flags_md = scan_flags(run_dir)
    flags_path = run_dir / "FLAGS.md"
    flags_path.write_text(flags_md)
    log(f"flags : {flags_path.relative_to(REPO_ROOT)}")
    print("\n" + "=" * 60)
    print(flags_md)
    orch_log.close()


if __name__ == "__main__":
    main()
