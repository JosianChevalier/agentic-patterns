#!/usr/bin/env python3
"""Socle partagé de la pipeline de consolidation (`2-consolide/`).

Module importé par `inventory.py` et `task.py` — **pas invoqué en direct**.
Centralise les quatre primitives transverses, une seule fois :

- **I/O `tasks.csv`** via le module `csv` uniquement (en-tête figé, quoting
  correct) — jamais de split manuel sur `,`. Cf. `2-consolide/outils/docs/specs/modele-donnees.md`.
- **Verrou `flock`** sur `.consolide.lock` (sérialisation locale, une machine).
- **Short session** dérivé de `$CLAUDE_CODE_SESSION_ID[:8]`.
- **Commit scopé** (`git add -- <paths>` puis `git commit -- <paths>`, jamais
  `git add .`) — concurrence-safe, ne stage que les chemins passés.
"""
import contextlib
import csv
import datetime
import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

def find_root(start: "Path | None" = None) -> Path:
    """Racine du dépôt = premier ancêtre contenant `.git` (fichier ou dossier).

    **Insensible à la profondeur du script** : immunise les déplacements d'outils
    entre couches (un `git mv` de `2-consolide/outils/` ne casse plus la résolution).
    Fallback historique (`parent.parent.parent`) si aucun `.git` trouvé.
    """
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        if (parent / ".git").exists():
            return parent
    return Path(__file__).resolve().parent.parent.parent


DEFAULT_REPO_ROOT = find_root()

# En-tête figé de `2-consolide/outils/tasks.csv` — cf. modele-donnees.md. Ne pas réordonner.
FIELDS = [
    "id", "type", "status", "parent", "input",
    "output", "owner", "claimed_at", "done_at", "note",
]


def die(msg: str) -> "None":
    sys.exit(f"error: {msg}")


# --- Chemins --------------------------------------------------------------

def resolve_root(override: "str | None" = None) -> Path:
    """Racine du dépôt (override explicite ou dérivée du chemin du script)."""
    return Path(override).resolve() if override else DEFAULT_REPO_ROOT


def tasks_path(root: Path) -> Path:
    return root / "2-consolide" / "outils" / "tasks.csv"


def lock_path(root: Path) -> Path:
    return root / ".consolide.lock"


# Localisations de la couche 2 et des sources amont, dérivées de `root`.
# Source unique de vérité : tout chemin de données passe par un de ces helpers
# (pas de littéral `root / "…" / "…"` éparpillé dans les scripts).

def consolide_dir(root: Path) -> Path:
    """Dossier des fiches consolidées (sortie du reduce) : `2-consolide/2.2-content/`."""
    return root / "2-consolide" / "2.2-content"


def themes_path(root: Path) -> Path:
    return root / "2-consolide" / "THEMES.md"


def fragments_dir(root: Path) -> Path:
    return root / "2-consolide" / "2.1-fragments"


def arbitrages_dir(root: Path) -> Path:
    """Source couche 1 des mini-ADR tranchés à la main : `1-sources/1.3-arbitrages/`
    (`NNNN-<slug>.md`). Projetée en `arbitrages_fragment` par `project_arbitrages.py`."""
    return root / "1-sources" / "1.3-arbitrages"


def arbitrages_fragment(root: Path) -> Path:
    """Fragment projeté (déterministe) des arbitrages : `2-consolide/2.1-fragments/arbitrages.md`.
    Plié par `project_arbitrages.py`, consommé par le reduce comme tout fragment."""
    return fragments_dir(root) / "arbitrages.md"


def outlines_dir(root: Path) -> Path:
    return root / "2-consolide" / "outils" / "outlines"


def orchestrator_dir(root: Path) -> Path:
    return root / "2-consolide" / "outils" / ".orchestrator"


def reports_dir(root: Path) -> Path:
    return root / "1-sources" / "1.2-nettoyes" / "reports"


def ressources_dir(root: Path) -> Path:
    return root / "1-sources" / "1.2-nettoyes" / "ressources"


def ressources_todo(root: Path) -> Path:
    """Inventaire des ressources extraites. Rangé avec le pipeline ressources
    dans `1-sources/outils/ressources/` (miroir de `_paths.ressources_todo`)."""
    return root / "1-sources" / "outils" / "ressources" / "RESSOURCES_TODO.md"


# --- Verrou ---------------------------------------------------------------

@contextlib.contextmanager
def locked(root: Path):
    """Sérialise les sections critiques via `flock` exclusif sur `.consolide.lock`.

    Lit/écrit `tasks.csv` et committe **dans** ce bloc pour rendre la transition
    visible des autres agents avant de relâcher le verrou.
    """
    lock = lock_path(root)
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lockf, fcntl.LOCK_UN)


# --- Session --------------------------------------------------------------

def short_session() -> str:
    """8 premiers caractères de `$CLAUDE_CODE_SESSION_ID`. Exit si absent."""
    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if not session:
        die("CLAUDE_CODE_SESSION_ID env var is required")
    return session[:8]


def now() -> str:
    """Horodatage ISO 8601 à la **seconde** (`claimed_at` / `done_at`), p. ex.
    `2026-06-09T23:11:05`. Granularité seconde (pas date-seule) pour que le prédicat
    stale `max(map.done_at) > reduce.done_at` ordonne deux tâches du même jour
    (cf. `docs/specs/stale.md` § Prérequis de schéma). Comparaison lexicographique
    inchangée : une ancienne valeur date-seule (`2026-06-08`) reste comparable et
    trie **avant** tout horodatage du même jour (préfixe plus court) — direction sûre
    (les reduces antérieurs aux rapports ressortent stale)."""
    return datetime.datetime.now().isoformat(timespec="seconds")


# --- I/O CSV --------------------------------------------------------------

def read_tasks(root: Path) -> "list[dict]":
    """Lit `tasks.csv` en liste de dicts (clés = `FIELDS`). [] si le fichier
    n'existe pas. Valide que l'en-tête correspond à `FIELDS`."""
    path = tasks_path(root)
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != FIELDS:
            die(f"en-tête tasks.csv inattendu: {reader.fieldnames!r} != {FIELDS!r}")
        return [dict(row) for row in reader]


def write_tasks(root: Path, rows: "list[dict]") -> None:
    """Réécrit `tasks.csv` **atomiquement** (en-tête figé + lignes, quoting `csv`).

    Écrit un temp voisin puis `os.replace` (rename atomique, même FS) : une
    interruption mid-write (kill watchdog, Ctrl-C, crash) ne laisse JAMAIS un
    CSV tronqué dans le working tree — l'ancien fichier reste intact jusqu'au
    rename. Sans ça, le prochain agent lirait un CSV partiel et la pipeline
    callerait (probabilité qui croît avec le volume d'appels).
    """
    path = tasks_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})
    os.replace(tmp, path)


def new_row(**values: str) -> "dict":
    """Ligne pré-remplie (toutes les colonnes de `FIELDS`, défaut vide)."""
    row = {k: "" for k in FIELDS}
    row.update(values)
    unknown = set(values) - set(FIELDS)
    if unknown:
        die(f"colonnes inconnues: {sorted(unknown)}")
    return row


# --- Git ------------------------------------------------------------------

# Retry borné sur collision `.git/index.lock` : d'autres agents (pipeline
# rapports) committent **hors** du flock consolide → `git add`/`git commit`
# peut buter sur un lock transitoire. Backoff exponentiel 0.05→0.4s
# (4 sleeps, total < 0.8s) ; on ne re-essaie QUE sur index.lock, jamais on
# ne supprime le lock soi-même.
_INDEX_LOCK_RETRIES = 5
_INDEX_LOCK_BACKOFF = 0.05


def _run_git(args: "list[str]", root: Path) -> "subprocess.CompletedProcess":
    """Lance `git <args>` dans `root` avec retry borné sur `index.lock`.

    Retry UNIQUEMENT si stderr mentionne `index.lock` (collision transitoire
    avec un agent qui committe hors flock). Toute autre erreur git — ou
    l'épuisement des tentatives — remonte comme `CalledProcessError`
    (équivalent `check=True`). Ne touche jamais au lock.
    """
    delay = _INDEX_LOCK_BACKOFF
    for attempt in range(_INDEX_LOCK_RETRIES):
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        if proc.returncode == 0:
            return proc
        if "index.lock" in proc.stderr and attempt < _INDEX_LOCK_RETRIES - 1:
            time.sleep(delay)
            delay *= 2
            continue
        raise subprocess.CalledProcessError(
            proc.returncode, proc.args, output=proc.stdout, stderr=proc.stderr,
        )
    raise AssertionError("unreachable")  # la boucle sort toujours par return/raise


def commit(root: Path, paths: "list[str | Path]", message: str) -> None:
    """Stage **puis** committe exactement les chemins passés.

    `git add -- <paths>` (gère les untracked) puis `git commit -- <paths>` :
    concurrence-safe, ne touche que `paths`, ignore ce qui traîne stagé par
    d'autres agents. Jamais `git add .` / `-A`.

    No-op silencieux si les `paths` sont inchangés (aucun diff stagé) : pas de
    commit vide, pas de `CalledProcessError` — l'appelant peut committer sans
    pré-vérifier. Retry borné sur `.git/index.lock` (cf. `_run_git`).
    """
    rels = [str(Path(p).resolve().relative_to(root)) for p in paths]
    _run_git(["add", "--", *rels], root)
    # Rien de stagé sur ces chemins → no-op (sinon `git commit` planterait).
    staged = subprocess.run(["git", "diff", "--cached", "--quiet", "--", *rels], cwd=root)
    if staged.returncode == 0:
        return
    _run_git(["commit", "-m", message, "--", *rels], root)


def checkout(root: Path, paths: "list[str | Path]") -> None:
    """Restaure les chemins à leur version committée (`git checkout -- <paths>`),
    scopé. Sert à annuler l'édition working-tree d'un correcteur mort qui tenait
    la lease (cf. task.py `_force_orphan_release`). Retry borné sur `index.lock`
    (cf. `_run_git`) ; remonte `CalledProcessError` si git échoue (appelant
    best-effort)."""
    rels = [str(Path(p).resolve().relative_to(root)) for p in paths]
    _run_git(["checkout", "--", *rels], root)


if __name__ == "__main__":
    die("_store.py est un module importé, pas un script (cf. task.py / inventory.py)")
