"""Tests outer-loop pour `common/outils/templates/file-validation/task.py`.

Delta vs `test_report_task.py` : on valide la paramétrabilité (threshold,
filename-re, lock-file, todo-rel, col-*) via flags CLI. Les defaults sont
testés indirectement par `test_report_task.py` (même logique métier).

Chaque test passe `--lock-file <tmp_repo>/...` pour rester isolé du lockfile
défaut (`$TMPDIR/your-project/task.lock`) et d'éventuelles instances voisines
(`report-task.py`, autres tests parallèles).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT = "templates/file-validation/task.py"
SLUG = "monslug"
TODO_REL = "out/MY_TODO.md"

HEADER_8COL = (
    "| État | A | B | C | D | Fichier | Verrou | Validation |\n"
    "|---|---|---|---|---|---|---|---|\n"
)

# Indices du layout 8-colonnes par défaut.
COL_ETAT, COL_VERROU, COL_VALIDATION = 0, 6, 7


def _row(*, etat: str, fichier: str, verrou: str = "—", validation: str = "—") -> str:
    return f"| {etat} | x | x | x | x | {fichier} | {verrou} | {validation} |\n"


def _write_todo(repo: Path, body: str) -> Path:
    todo = repo / TODO_REL
    todo.parent.mkdir(parents=True)
    todo.write_text(body)
    rel = str(todo.relative_to(repo))
    subprocess.run(["git", "add", rel], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return todo


def _cells_for(todo: Path, fichier: str) -> list[str]:
    for line in todo.read_text().splitlines():
        if fichier in line and line.startswith("| "):
            return [c.strip() for c in line.strip().strip("|").split("|")]
    raise AssertionError(f"ligne contenant {fichier!r} introuvable dans {todo}")


def _base_flags(repo: Path, *, threshold: int | None = None,
                filename_re: str | None = None, lock_file: Path | None = None) -> list[str]:
    flags = [
        "--todo-rel", TODO_REL,
        "--lock-file", str(lock_file or repo / "task.lock"),
    ]
    if threshold is not None:
        flags += ["--threshold", str(threshold)]
    if filename_re is not None:
        flags += ["--filename-re", filename_re]
    return flags


# ─── THRESHOLD=3 ──────────────────────────────────────────────────────────────

def test_threshold_3_converge_apres_3_passes_ok(run_script, tmp_repo, git_log, session_env):
    fichier = f"OUTPUT_{SLUG}.md"
    todo = _write_todo(
        tmp_repo,
        HEADER_8COL + _row(etat="fait", fichier=fichier, verrou="🔒", validation="0/3"),
    )
    flags = _base_flags(tmp_repo, threshold=3)

    # 1re passe → 1/3
    r1 = run_script(SCRIPT, *flags, "finish", SLUG, "ok", repo=tmp_repo)
    assert r1.returncode == 0, r1.stderr
    assert _cells_for(todo, fichier)[COL_VALIDATION] == "1/3"

    # 2e passe → 2/3 (re-claim requis car finish libère le verrou)
    run_script(SCRIPT, *flags, "claim", SLUG, repo=tmp_repo)
    r2 = run_script(SCRIPT, *flags, "finish", SLUG, "ok", repo=tmp_repo)
    assert r2.returncode == 0, r2.stderr
    assert _cells_for(todo, fichier)[COL_VALIDATION] == "2/3"

    # 3e passe → 3/3 ✓
    run_script(SCRIPT, *flags, "claim", SLUG, repo=tmp_repo)
    r3 = run_script(SCRIPT, *flags, "finish", SLUG, "ok", repo=tmp_repo)
    assert r3.returncode == 0, r3.stderr
    assert _cells_for(todo, fichier)[COL_VALIDATION] == "3/3 ✓"
    assert git_log(tmp_repo)[0] == f"Finish validation {SLUG} ok ({session_env})"


def test_threshold_3_claim_apres_converge_echoue(run_script, tmp_repo):
    fichier = f"OUTPUT_{SLUG}.md"
    todo = _write_todo(
        tmp_repo,
        HEADER_8COL + _row(etat="fait", fichier=fichier, validation="3/3 ✓"),
    )
    before = todo.read_text()
    r = run_script(SCRIPT, *_base_flags(tmp_repo, threshold=3),
                   "claim", SLUG, repo=tmp_repo)
    assert r.returncode != 0
    assert todo.read_text() == before


# ─── corrigé reset ────────────────────────────────────────────────────────────

def test_corrige_reset_a_zero_sur_threshold_3(run_script, tmp_repo):
    fichier = f"OUTPUT_{SLUG}.md"
    todo = _write_todo(
        tmp_repo,
        HEADER_8COL + _row(etat="fait", fichier=fichier, verrou="🔒", validation="2/3"),
    )
    r = run_script(SCRIPT, *_base_flags(tmp_repo, threshold=3),
                   "finish", SLUG, "corrigé", repo=tmp_repo)
    assert r.returncode == 0, r.stderr
    assert _cells_for(todo, fichier)[COL_VALIDATION] == "0/3"


# ─── FILENAME_RE custom ───────────────────────────────────────────────────────

def test_filename_re_custom_match_la_bonne_ligne(run_script, tmp_repo):
    custom = r"DOC_(?P<slug>[^.]+)\.md"
    body = (
        HEADER_8COL
        + _row(etat="todo", fichier=f"OUTPUT_{SLUG}.md")
        + _row(etat="todo", fichier=f"DOC_{SLUG}.md")
    )
    todo = _write_todo(tmp_repo, body)
    r = run_script(SCRIPT, *_base_flags(tmp_repo, filename_re=custom),
                   "claim", SLUG, repo=tmp_repo)
    assert r.returncode == 0, r.stderr
    # La ligne DOC_ doit avoir bougé ; la ligne OUTPUT_ doit être intacte.
    doc_cells = _cells_for(todo, f"DOC_{SLUG}.md")
    output_cells = _cells_for(todo, f"OUTPUT_{SLUG}.md")
    assert doc_cells[COL_ETAT] == "en cours"
    assert doc_cells[COL_VERROU] == "🔒"
    assert output_cells[COL_ETAT] == "todo"
    assert output_cells[COL_VERROU] == "—"


# ─── lock-file isolé ──────────────────────────────────────────────────────────

def test_lock_file_custom_cree_le_fichier_dans_repo(run_script, tmp_repo):
    """Le lockfile custom doit être créé/touché, pas le défaut `$TMPDIR/...`."""
    fichier = f"OUTPUT_{SLUG}.md"
    _write_todo(tmp_repo, HEADER_8COL + _row(etat="todo", fichier=fichier))
    lock = tmp_repo / "my-template.lock"
    r = run_script(SCRIPT, *_base_flags(tmp_repo, lock_file=lock),
                   "claim", SLUG, repo=tmp_repo)
    assert r.returncode == 0, r.stderr
    assert lock.exists()


# ─── col-* custom ─────────────────────────────────────────────────────────────

def test_col_indices_custom_matchent_un_tableau_court(run_script, tmp_repo):
    """Tableau à 4 colonnes : État | Fichier | Verrou | Validation."""
    short_header = (
        "| État | Fichier | Verrou | Validation |\n"
        "|---|---|---|---|\n"
    )
    fichier = f"OUTPUT_{SLUG}.md"
    body = short_header + f"| todo | {fichier} | — | — |\n"
    todo = _write_todo(tmp_repo, body)
    r = run_script(
        SCRIPT,
        "--todo-rel", TODO_REL,
        "--lock-file", str(tmp_repo / "task.lock"),
        "--col-fichier", "1",
        "--col-verrou", "2",
        "--col-validation", "3",
        "claim", SLUG, repo=tmp_repo,
    )
    assert r.returncode == 0, r.stderr
    cells = _cells_for(todo, fichier)
    assert cells[0] == "en cours"   # col-etat default = 0
    assert cells[2] == "🔒"          # col-verrou custom = 2
