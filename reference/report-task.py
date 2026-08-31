#!/usr/bin/env python3
"""Gère verrou + état des tâches dans 1-sources/outils/REPORTS_TODO.md.

Sous-commandes :
  claim <slug>              Réserve une ligne (rédaction si état=todo, validation si fait <2/2).
  release <slug>            Libère le verrou sans transition (abandon).
  finish <slug> [verdict]   Termine la tâche. Verdict requis pour validation : ok | corrigé | signalé.

Options globales :
  --repo-root <path>        Racine du dépôt (default : dérivée du chemin du script).

Le script sérialise les opérations via flock($TMPDIR/formation-cats/reports.lock) et commit lui-même.
"""

import argparse
import fcntl
import os
import re
import subprocess
import sys
from pathlib import Path

def find_root(start: "Path | None" = None) -> Path:
    """Racine du dépôt = premier ancêtre contenant `.git` (fichier ou dossier).

    Insensible à la profondeur du script : immunise les déplacements d'outils
    entre couches (un `git mv` vers `1-sources/outils/` ne casse plus la
    résolution). Fallback historique (`parent.parent`) si aucun `.git` trouvé.
    """
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        if (parent / ".git").exists():
            return parent
    return Path(__file__).resolve().parent.parent


DEFAULT_REPO_ROOT = find_root()
LOCK_FILE = Path(os.environ.get("TMPDIR", "/tmp")) / "formation-cats" / "reports.lock"
LOCK_HELD = "🔒"
LOCK_FREE = "—"
VALID_VERDICTS = {"ok", "corrigé", "signalé"}

# Indices dans la table : | État | Atelier | Date | Transcript | Notes | Report | Verrou | Validation |
COL_ETAT = 0
COL_REPORT = 5
COL_VERROU = 6
COL_VALIDATION = 7


def die(msg: str) -> None:
    sys.exit(f"error: {msg}")


def parse_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.rstrip("\n").strip().strip("|").split("|")]


def format_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |\n"


def find_row(lines: list[str], slug: str) -> int:
    pattern = re.compile(rf"REPORT_{re.escape(slug)}\.md")
    for i, line in enumerate(lines):
        if line.startswith("| ") and pattern.search(line):
            return i
    die(f"aucune ligne ne correspond au slug '{slug}'")


def git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], check=True, cwd=repo_root)


def commit(repo_root: Path, todo_file: Path, message: str) -> None:
    rel = todo_file.relative_to(repo_root)
    git(repo_root, "commit", "-m", message, "--", str(rel))


def with_lock(fn):
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.touch(exist_ok=True)
    with open(LOCK_FILE, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_table(todo_file: Path) -> list[str]:
    return todo_file.read_text(encoding="utf-8").splitlines(keepends=True)


def write_table(todo_file: Path, lines: list[str]) -> None:
    todo_file.write_text("".join(lines), encoding="utf-8")


def cmd_claim(repo_root: Path, todo_file: Path, slug: str) -> None:
    def go():
        lines = read_table(todo_file)
        idx = find_row(lines, slug)
        cells = parse_row(lines[idx])
        if cells[COL_VERROU] == LOCK_HELD:
            die(f"ligne déjà verrouillée ({slug})")
        etat = cells[COL_ETAT]
        validation = cells[COL_VALIDATION]
        if etat == "todo":
            cells[COL_ETAT] = "en cours"
            kind = "rédaction"
        elif etat == "fait" and not validation.startswith("2/2"):
            kind = "validation"
        else:
            die(f"ligne non prenable (état={etat}, validation={validation})")
        cells[COL_VERROU] = LOCK_HELD
        lines[idx] = format_row(cells)
        write_table(todo_file, lines)
        commit(repo_root, todo_file, f"Claim {kind} {slug}")
        print(f"Claimed {kind} for {slug}")

    with_lock(go)


def cmd_release(repo_root: Path, todo_file: Path, slug: str) -> None:
    def go():
        lines = read_table(todo_file)
        idx = find_row(lines, slug)
        cells = parse_row(lines[idx])
        if cells[COL_VERROU] != LOCK_HELD:
            die("ligne non verrouillée")
        if cells[COL_ETAT] == "en cours":
            cells[COL_ETAT] = "todo"
        cells[COL_VERROU] = LOCK_FREE
        lines[idx] = format_row(cells)
        write_table(todo_file, lines)
        commit(repo_root, todo_file, f"Release {slug}")
        print(f"Released {slug}")

    with_lock(go)


def cmd_finish(repo_root: Path, todo_file: Path, slug: str, verdict: str | None) -> None:
    def go():
        lines = read_table(todo_file)
        idx = find_row(lines, slug)
        cells = parse_row(lines[idx])
        if cells[COL_VERROU] != LOCK_HELD:
            die("ligne non verrouillée — utilise `claim` d'abord")
        etat = cells[COL_ETAT]
        if etat == "en cours":
            if verdict:
                die("pas de verdict pour une fin de rédaction")
            cells[COL_ETAT] = "fait"
            cells[COL_VALIDATION] = "0/2"
            cells[COL_VERROU] = LOCK_FREE
            msg = f"Finish rédaction {slug}"
        elif etat == "fait":
            if verdict not in VALID_VERDICTS:
                die(f"verdict requis : {' | '.join(sorted(VALID_VERDICTS))}")
            current = cells[COL_VALIDATION]
            m = re.match(r"(\d+)/2", current)
            if not m:
                die(f"validation illisible : '{current}'")
            n = int(m.group(1))
            if verdict in {"ok", "signalé"}:
                n = min(n + 1, 2)
            else:  # corrigé
                n = 0
            cells[COL_VALIDATION] = f"{n}/2 ✓" if n == 2 else f"{n}/2"
            cells[COL_VERROU] = LOCK_FREE
            msg = f"Finish validation {slug} ({verdict})"
        else:
            die(f"état inattendu : {etat}")
        lines[idx] = format_row(cells)
        write_table(todo_file, lines)
        commit(repo_root, todo_file, msg)
        print(msg)

    with_lock(go)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", default=None,
                   help="racine du dépôt (default : dérivée du chemin du script)")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("claim", "release"):
        s = sub.add_parser(name)
        s.add_argument("slug")
    f = sub.add_parser("finish")
    f.add_argument("slug")
    f.add_argument("verdict", nargs="?")
    args = p.parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else DEFAULT_REPO_ROOT
    todo_file = repo_root / "1-sources" / "outils" / "REPORTS_TODO.md"
    if args.cmd == "claim":
        cmd_claim(repo_root, todo_file, args.slug)
    elif args.cmd == "release":
        cmd_release(repo_root, todo_file, args.slug)
    elif args.cmd == "finish":
        cmd_finish(repo_root, todo_file, args.slug, args.verdict)


if __name__ == "__main__":
    main()
