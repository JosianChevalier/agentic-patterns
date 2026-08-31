"""Tests de concurrence — `fcntl.flock` garantit l'atomicité du claim.

Deux subprocess lancés en parallèle pour réclamer la même ligne :
exactement un succès (rc=0), l'autre exit non-zero proprement.

Note : `report-task.py` utilise un verrou global `$TMPDIR/formation-cats/reports.lock`.
Un agent réel qui tournerait `report-task.py` en parallèle sur la même
machine ajouterait de la latence mais ne peut pas provoquer de faux
positif — chaque test contend la table de son propre `tmp_repo`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from conftest import REPO_ROOT  # racine via .git (post-mv vers common/outils/tests/)
SLUG = "monslug"


def _ressources_setup(repo: Path, make_ressources_todo) -> None:
    todo = repo / "1-sources" / "outils" / "ressources" / "RESSOURCES_TODO.md"
    todo.parent.mkdir(parents=True)
    todo.write_text(make_ressources_todo([
        {"slug": SLUG, "source": "1-sources/1.1-raw/postfiles/foo.pptx", "type": "pptx"}
    ]))
    subprocess.run(["git", "add", str(todo)], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)


def _reports_setup(repo: Path, make_reports_todo) -> None:
    todo = repo / "1-sources" / "outils" / "REPORTS_TODO.md"
    todo.parent.mkdir(parents=True)
    todo.write_text(make_reports_todo([{
        "etat": "todo", "atelier": "atelier",
        "date": "2026-01-01", "report": f"REPORT_{SLUG}.md",
    }]))
    subprocess.run(["git", "add", str(todo)], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)


def _launch_pair(script_rel: str, *args: str, repo: Path
                 ) -> tuple[subprocess.CompletedProcess, subprocess.CompletedProcess]:
    """Lance deux subprocess identiques en parallèle, attend leur fin."""
    script = REPO_ROOT / "tools" / script_rel
    cmd = [sys.executable, str(script), "--repo-root", str(repo), *args]
    p1 = subprocess.Popen(cmd, cwd=repo, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)
    p2 = subprocess.Popen(cmd, cwd=repo, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)
    o1, e1 = p1.communicate()
    o2, e2 = p2.communicate()
    return (subprocess.CompletedProcess(cmd, p1.returncode, o1, e1),
            subprocess.CompletedProcess(cmd, p2.returncode, o2, e2))


def test_ressources_claim_concurrent_un_seul_succes(
        tmp_repo, make_ressources_todo, session_env):
    """Deux `claim.py extract <slug>` simultanés → exactement un succès."""
    _ressources_setup(tmp_repo, make_ressources_todo)
    r1, r2 = _launch_pair("ressources/claim.py", "extract", SLUG, repo=tmp_repo)
    rcs = sorted([r1.returncode, r2.returncode])
    assert rcs[0] == 0 and rcs[1] != 0, (
        f"un seul succès attendu, got {rcs}\n"
        f"  P1 stderr={r1.stderr!r}\n  P2 stderr={r2.stderr!r}"
    )


def test_report_task_claim_concurrent_un_seul_succes(
        tmp_repo, make_reports_todo):
    """Deux `report-task.py claim <slug>` simultanés → exactement un succès."""
    _reports_setup(tmp_repo, make_reports_todo)
    r1, r2 = _launch_pair("report-task.py", "claim", SLUG, repo=tmp_repo)
    rcs = sorted([r1.returncode, r2.returncode])
    assert rcs[0] == 0 and rcs[1] != 0, (
        f"un seul succès attendu, got {rcs}\n"
        f"  P1 stderr={r1.stderr!r}\n  P2 stderr={r2.stderr!r}"
    )
