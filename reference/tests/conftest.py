"""Fixtures partagées pour la suite de tests `tools/`.

Convention :
- `tmp_repo` : un repo git vierge dans `tmp_path` (init + user.email/name).
- `session_env` : injecte `CLAUDE_CODE_SESSION_ID` déterministe (`a1b2c3d4…` → short `a1b2c3d4`).
- `make_ressources_todo` / `make_reports_todo` : composent un TODO minimal valide
  à écrire dans le `tmp_repo` (l'appelant choisit le chemin).
- `run_script` : lance un script de `tools/` via subprocess en passant
  `--repo-root <tmp_repo>`. N'élève pas en cas de rc≠0 — les tests assertent.
- `git_log` : liste les sujets de commit dans l'ordre antichronologique.

Les scripts tournent via `sys.executable`, donc avec l'interpréteur qui exécute
pytest. Si pytest est lancé depuis `.venv/bin/pytest`, les handlers qui
importent `pptx`/`docx`/`yaml` fonctionnent sans re-exec.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

def _find_root(start: Path | None = None) -> Path:
    """Racine du dépôt = premier ancêtre contenant `.git` (insensible à la
    profondeur : ces tests ont migré `tests/` → `common/outils/tests/`)."""
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        if (parent / ".git").exists():
            return parent
    return Path(__file__).resolve().parent.parent


REPO_ROOT = _find_root()
FIXTURES = Path(__file__).resolve().parent / "fixtures"

SESSION_ID_FULL = "a1b2c3d4testsession"
SESSION_ID_SHORT = "a1b2c3d4"


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """tmp_path + `git init` + user.email/name (sinon commit échoue)."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmp_path, check=True)
    return tmp_path


@pytest.fixture
def session_env(monkeypatch: pytest.MonkeyPatch) -> str:
    """Injecte un CLAUDE_CODE_SESSION_ID déterministe. Renvoie le short (8 chars)."""
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SESSION_ID_FULL)
    return SESSION_ID_SHORT


# ─── Composeurs de TODO ───────────────────────────────────────────────────────

RESSOURCES_COLS = ("extract", "triage", "embed", "transcribe", "validate", "verrou")
RESSOURCES_HEADER = (
    "| Slug | Source | Type | Extract | Triage | Embed | Transcribe | Validate | Verrou |\n"
    "|---|---|---|---|---|---|---|---|---|\n"
)


def _ressources_row(row: dict) -> str:
    slug = row["slug"]
    source = row["source"]
    ftype = row["type"]
    cells = [slug, f"`{source}`", ftype]
    for col in RESSOURCES_COLS:
        cells.append(str(row.get(col, "—")))
    return "| " + " | ".join(cells) + " |\n"


@pytest.fixture
def make_ressources_todo():
    """Compose un `RESSOURCES_TODO.md` valide à partir d'une liste de dicts.

    Chaque dict : `slug`, `source`, `type` (requis) + `extract`, `triage`,
    `embed`, `transcribe`, `validate`, `verrou` (default `—`).

    Inclut les markers `<!-- INVENTORY:BEGIN/END -->` et
    `<!-- DUPLICATES:BEGIN/END -->` attendus par `inventory.py`.
    """
    def _make(rows: list[dict], duplicates: list[tuple[str, str]] | None = None) -> str:
        parts = ["# Ressources TODO (fixture)\n\n"]
        parts.append("<!-- INVENTORY:BEGIN -->\n")
        parts.append(RESSOURCES_HEADER)
        for row in rows:
            parts.append(_ressources_row(row))
        parts.append("<!-- INVENTORY:END -->\n\n")
        parts.append("<!-- DUPLICATES:BEGIN -->\n")
        if duplicates:
            for canonical, dup_path in duplicates:
                parts.append(f"- `{dup_path}` → doublon de `{canonical}`\n")
        else:
            parts.append("*(aucun doublon détecté)*\n")
        parts.append("<!-- DUPLICATES:END -->\n")
        return "".join(parts)
    return _make


REPORTS_HEADER = (
    "| État | Atelier | Date | Transcript | Notes | Report | Verrou | Validation |\n"
    "|---|---|---|---|---|---|---|---|\n"
)


def _reports_row(row: dict) -> str:
    cells = [
        row.get("etat", "todo"),
        row["atelier"],
        row.get("date", "2026-01-01"),
        row.get("transcript", "—"),
        row.get("notes", "—"),
        row["report"],
        row.get("verrou", "—"),
        row.get("validation", "—"),
    ]
    return "| " + " | ".join(cells) + " |\n"


@pytest.fixture
def make_reports_todo():
    """Compose un `REPORTS_TODO.md` valide à partir d'une liste de dicts.

    Colonnes : État, Atelier, Date, Transcript, Notes, Report, Verrou, Validation.
    Le champ `report` doit contenir le chemin (`REPORT_<slug>.md`) — c'est sur
    ce nom que `report-task.py` matche le slug via regex.
    """
    def _make(rows: list[dict]) -> str:
        parts = ["# Reports TODO (fixture)\n\n", REPORTS_HEADER]
        for row in rows:
            parts.append(_reports_row(row))
        return "".join(parts)
    return _make


# ─── Lanceurs ─────────────────────────────────────────────────────────────────

@pytest.fixture
def run_script():
    """Lance un script de `tools/` via subprocess, n'élève pas si rc≠0.

    Usage : `run_script("ressources/claim.py", "extract", "myslug", repo=tmp_repo)`.

    Le script tourne via `sys.executable` (donc le venv si pytest est lancé
    depuis là). `--repo-root <repo>` est injecté automatiquement avant les
    args positionnels. `cwd=repo` (cohérent avec les hooks git).
    """
    def _run(script_rel: str, *args: str, repo: Path, env: dict | None = None
             ) -> subprocess.CompletedProcess:
        script = REPO_ROOT / "tools" / script_rel
        cmd = [sys.executable, str(script), "--repo-root", str(repo), *args]
        return subprocess.run(
            cmd, cwd=repo, capture_output=True, text=True, check=False, env=env,
        )
    return _run


@pytest.fixture
def git_log():
    """Retourne les sujets de commit d'un repo, ordre antichronologique."""
    def _log(repo: Path) -> list[str]:
        out = subprocess.run(
            ["git", "log", "--pretty=format:%s"],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout
        return [line for line in out.splitlines() if line]
    return _log
