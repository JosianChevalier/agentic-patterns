#!/usr/bin/env python3
"""Template — gère verrou + état des tâches dans un tableau markdown.

Flux par défaut : **le script choisit la tâche** (`next`), l'agent ne choisit
pas. C'est ce qui élimine les courses de sélection quand plusieurs agents
drainent la même queue en parallèle — la sélection se fait DANS le flock, donc
deux agents ne peuvent jamais recevoir la même ligne.

Sous-commandes :
  next                     Choisit et réserve la première ligne prenable PAR CET AGENT
                           (validation proche de la sortie d'abord, sinon rédaction),
                           puis imprime `TASK: <rédaction|validation> <slug>`. Si rien
                           n'est prenable, sort en erreur. C'est le mode normal sous
                           orchestrateur.
  claim <slug>             Réserve une ligne précise (échappatoire manuelle / ciblée).
                           Pas de garde ≠rédacteur — réservé à un humain qui sait ce
                           qu'il fait. Préfère `next` en automatique.
  release <slug>           Libère le verrou sans transition (abandon).
  finish <slug> [verdict]  Termine la tâche. Verdict requis pour validation : ok | corrigé | signalé.

Identité de session : tout commit est estampillé `(<short>)` (8 chars de
`$CLAUDE_CODE_SESSION_ID`, ou `manual` hors session Claude Code). C'est ce qui
permet (a) à `next` d'appliquer les gardes ≠rédacteur / ≠validateur-précédent en
grepant l'historique, et (b) à l'orchestrateur compagnon d'attribuer chaque
commit à un agent. Voir `../subagent-orchestrator/`.

Options globales (tous avec defaults = comportement de référence) :
  --repo-root <path>        Racine du dépôt (default : dérivée du chemin du script).
  --todo-rel <path>         Chemin du TODO relatif au repo root.
  --lock-file <path>        Lockfile fcntl (local, hors git).
  --threshold <int>         N passes consécutives requises (default 2).
  --filename-re <regex>     Extrait le slug depuis le chemin (doit contenir (?P<slug>...)).
  --col-etat / --col-fichier / --col-verrou / --col-validation <int>
                            Indices 0-based des colonnes après split du `|`.

Le script sérialise les opérations via flock(lock-file) et commit lui-même chaque transition.

Adapter à un nouveau cas d'usage : **copier ce dossier sous `<couche>/outils/<ton-domaine>/`** et
ajuster les `DEFAULT_*` ci-dessous. Les flags CLI existent pour les tests et le debug
ponctuel — ne sont pas une stratégie de réutilisation. Si tes besoins dépassent
rédaction + validation (multi-étapes, résultats typés…), **réécris ton propre
script** en t'inspirant de `1-sources/outils/ressources/{claim,release}.py` plutôt que d'étendre
celui-ci. Voir README.md, section « Variantes connues ».
"""

import argparse
import fcntl
import os
import re
import subprocess
import sys
from pathlib import Path

# ─── Defaults (à ajuster, ou override en CLI) ─────────────────────────────────
DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_TODO_REL = "path/to/TODO.md"
# Lockfile scopé à un sous-dossier projet sous $TMPDIR (créé à la demande).
DEFAULT_LOCK_FILE = Path(os.environ.get("TMPDIR", "/tmp")) / "your-project" / "task.lock"
DEFAULT_THRESHOLD = 2
DEFAULT_FILENAME_RE = r"OUTPUT_(?P<slug>[^.]+)\.md"
DEFAULT_COL_ETAT = 0
DEFAULT_COL_FICHIER = 5
DEFAULT_COL_VERROU = 6
DEFAULT_COL_VALIDATION = 7

LOCK_HELD = "🔒"
LOCK_FREE = "—"
VALID_VERDICTS = {"ok", "corrigé", "signalé"}
# ───────────────────────────────────────────────────────────────────────────────


class Config:
    """Bundle des paramètres résolus (defaults + overrides CLI)."""
    def __init__(self, repo_root: Path, todo_file: Path, lock_file: Path,
                 threshold: int, filename_re: str,
                 col_etat: int, col_fichier: int, col_verrou: int, col_validation: int):
        self.repo_root = repo_root
        self.todo_file = todo_file
        self.lock_file = lock_file
        self.threshold = threshold
        self.filename_re = filename_re
        self.col_etat = col_etat
        self.col_fichier = col_fichier
        self.col_verrou = col_verrou
        self.col_validation = col_validation


def die(msg: str) -> None:
    sys.exit(f"error: {msg}")


def session_short() -> str:
    """8 premiers chars de $CLAUDE_CODE_SESSION_ID, ou 'manual' hors session.

    Estampillé dans chaque commit. Sert aux gardes ≠rédacteur / ≠validateur de
    `next` (grep de l'historique) et à l'orchestrateur pour attribuer les commits.
    """
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    return sid[:8] if sid else "manual"


def parse_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.rstrip("\n").strip().strip("|").split("|")]


def format_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |\n"


def row_slug(line: str, filename_re: str) -> str | None:
    """Slug de la ligne (via filename_re sur la ligne entière), ou None si la
    ligne ne contient pas de fichier (header, séparateur, prose)."""
    m = re.compile(filename_re).search(line)
    return m.group("slug") if m else None


def find_row(lines: list[str], slug: str, filename_re: str) -> int:
    pattern = re.compile(filename_re.replace("(?P<slug>[^.]+)", re.escape(slug)))
    for i, line in enumerate(lines):
        if line.startswith("| ") and pattern.search(line):
            return i
    die(f"aucune ligne ne correspond au slug '{slug}'")


def git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], check=True, cwd=repo_root)


def commit(repo_root: Path, todo_file: Path, message: str) -> None:
    rel = todo_file.relative_to(repo_root)
    git(repo_root, "add", str(rel))
    git(repo_root, "commit", "-m", message)


def commit_shorts(repo_root: Path, grep: str) -> set[str]:
    """Shorts `(xxxxxxxx)` extraits des sujets de commit matchant `grep`.

    Utilisé par les gardes de `next` : qui a déjà rédigé / validé ce slug."""
    out = subprocess.run(
        ["git", "log", "--grep", grep, "--pretty=format:%s"],
        capture_output=True, text=True, cwd=repo_root, check=False,
    ).stdout
    shorts: set[str] = set()
    for line in out.splitlines():
        m = re.search(r"\(([0-9a-z]+)\)\s*$", line)
        if m:
            shorts.add(m.group(1))
    return shorts


def writer_shorts(cfg: Config, slug: str) -> set[str]:
    """Agents qui ont terminé la rédaction de ce slug (ne peuvent pas valider)."""
    return commit_shorts(cfg.repo_root, rf"^Finish rédaction {re.escape(slug)} ")


def validator_shorts(cfg: Config, slug: str) -> set[str]:
    """Agents qui ont déjà fait une passe de validation sur ce slug (chaque passe
    du N/N doit venir d'un agent distinct)."""
    return commit_shorts(cfg.repo_root, rf"^Finish validation {re.escape(slug)} ")


def with_lock(lock_file: Path, fn):
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.touch(exist_ok=True)
    with open(lock_file, "w") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            return fn()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def read_table(todo_file: Path) -> list[str]:
    return todo_file.read_text(encoding="utf-8").splitlines(keepends=True)


def write_table(todo_file: Path, lines: list[str]) -> None:
    todo_file.write_text("".join(lines), encoding="utf-8")


def converged(validation: str, threshold: int) -> bool:
    return validation.startswith(f"{threshold}/{threshold}")


def validation_count(validation: str) -> int:
    m = re.match(r"(\d+)/", validation)
    return int(m.group(1)) if m else 0


def cmd_next(cfg: Config, short: str) -> None:
    """Choisit la première ligne prenable PAR CET AGENT et la claim.

    Priorité (cf. README « Contraintes inter-agents ») :
    1. Validation des lignes `fait` non convergées, la plus proche de la sortie
       d'abord (compteur le plus haut), en sautant celles que cet agent a
       rédigées ou déjà validées (gardes ≠rédacteur / ≠validateur-précédent).
    2. Rédaction des lignes `todo`, dans l'ordre du tableau.

    La sélection ET le claim se font sous le flock → pas de course possible.
    Imprime `TASK: <kind> <slug>` ; l'agent fait CE travail-là, sans choisir.
    """
    def go():
        lines = read_table(cfg.todo_file)
        max_col = max(cfg.col_etat, cfg.col_fichier, cfg.col_verrou, cfg.col_validation)
        validation_cands: list[tuple[int, int, str]] = []  # (count, idx, slug)
        redaction_cands: list[tuple[int, str]] = []        # (idx, slug)
        for i, line in enumerate(lines):
            if not line.startswith("| "):
                continue
            cells = parse_row(line)
            if len(cells) <= max_col:
                continue
            slug = row_slug(line, cfg.filename_re)
            if not slug:
                continue
            if cells[cfg.col_verrou] == LOCK_HELD:
                continue
            etat = cells[cfg.col_etat]
            validation = cells[cfg.col_validation]
            if etat == "todo":
                redaction_cands.append((i, slug))
            elif etat == "fait" and not converged(validation, cfg.threshold):
                if short in writer_shorts(cfg, slug):
                    continue
                if short in validator_shorts(cfg, slug):
                    continue
                validation_cands.append((validation_count(validation), i, slug))

        # Validation d'abord, la plus proche du N/N ; à compteur égal, ordre du tableau.
        validation_cands.sort(key=lambda t: (-t[0], t[1]))
        if validation_cands:
            _, idx, slug = validation_cands[0]
            kind = "validation"
        elif redaction_cands:
            idx, slug = redaction_cands[0]
            kind = "rédaction"
        else:
            die("aucune tâche disponible pour cet agent")

        cells = parse_row(lines[idx])
        if kind == "rédaction":
            cells[cfg.col_etat] = "en cours"
        cells[cfg.col_verrou] = LOCK_HELD
        lines[idx] = format_row(cells)
        write_table(cfg.todo_file, lines)
        commit(cfg.repo_root, cfg.todo_file, f"Claim {kind} {slug} ({short})")
        print(f"TASK: {kind} {slug}")

    with_lock(cfg.lock_file, go)


def cmd_claim(cfg: Config, slug: str, short: str) -> None:
    def go():
        lines = read_table(cfg.todo_file)
        idx = find_row(lines, slug, cfg.filename_re)
        cells = parse_row(lines[idx])
        if cells[cfg.col_verrou] == LOCK_HELD:
            die(f"ligne déjà verrouillée ({slug})")
        etat = cells[cfg.col_etat]
        validation = cells[cfg.col_validation]
        if etat == "todo":
            cells[cfg.col_etat] = "en cours"
            kind = "rédaction"
        elif etat == "fait" and not converged(validation, cfg.threshold):
            kind = "validation"
        else:
            die(f"ligne non prenable (état={etat}, validation={validation})")
        cells[cfg.col_verrou] = LOCK_HELD
        lines[idx] = format_row(cells)
        write_table(cfg.todo_file, lines)
        commit(cfg.repo_root, cfg.todo_file, f"Claim {kind} {slug} ({short})")
        print(f"Claimed {kind} for {slug}")

    with_lock(cfg.lock_file, go)


def cmd_release(cfg: Config, slug: str, short: str) -> None:
    def go():
        lines = read_table(cfg.todo_file)
        idx = find_row(lines, slug, cfg.filename_re)
        cells = parse_row(lines[idx])
        if cells[cfg.col_verrou] != LOCK_HELD:
            die("ligne non verrouillée")
        kind = "rédaction" if cells[cfg.col_etat] == "en cours" else "validation"
        if cells[cfg.col_etat] == "en cours":
            cells[cfg.col_etat] = "todo"
        cells[cfg.col_verrou] = LOCK_FREE
        lines[idx] = format_row(cells)
        write_table(cfg.todo_file, lines)
        commit(cfg.repo_root, cfg.todo_file, f"Release {kind} {slug} ({short})")
        print(f"Released {slug}")

    with_lock(cfg.lock_file, go)


def cmd_finish(cfg: Config, slug: str, verdict: str | None, short: str) -> None:
    def go():
        lines = read_table(cfg.todo_file)
        idx = find_row(lines, slug, cfg.filename_re)
        cells = parse_row(lines[idx])
        if cells[cfg.col_verrou] != LOCK_HELD:
            die("ligne non verrouillée — utilise `next` ou `claim` d'abord")
        etat = cells[cfg.col_etat]
        if etat == "en cours":
            if verdict:
                die("pas de verdict pour une fin de rédaction")
            cells[cfg.col_etat] = "fait"
            cells[cfg.col_validation] = f"0/{cfg.threshold}"
            cells[cfg.col_verrou] = LOCK_FREE
            msg = f"Finish rédaction {slug} ({short})"
        elif etat == "fait":
            if verdict not in VALID_VERDICTS:
                die(f"verdict requis : {' | '.join(sorted(VALID_VERDICTS))}")
            current = cells[cfg.col_validation]
            m = re.match(rf"(\d+)/{cfg.threshold}", current)
            if not m:
                die(f"validation illisible : '{current}'")
            n = int(m.group(1))
            if verdict == "signalé":
                # gèle la ligne : blocage non tranchable par le valideur, sort
                # du flux jusqu'à arbitrage. Compteur inchangé, état non-`fait`
                # → plus pickable par `next`.
                cells[cfg.col_etat] = "bloqué"
            else:
                if verdict == "ok":
                    n = min(n + 1, cfg.threshold)
                else:  # corrigé
                    n = 0
                cells[cfg.col_validation] = (
                    f"{n}/{cfg.threshold} ✓" if n == cfg.threshold else f"{n}/{cfg.threshold}"
                )
            cells[cfg.col_verrou] = LOCK_FREE
            msg = f"Finish validation {slug} {verdict} ({short})"
        else:
            die(f"état inattendu : {etat}")
        lines[idx] = format_row(cells)
        write_table(cfg.todo_file, lines)
        commit(cfg.repo_root, cfg.todo_file, msg)
        print(msg)

    with_lock(cfg.lock_file, go)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", default=None,
                   help="racine du dépôt (default : dérivée du chemin du script)")
    p.add_argument("--todo-rel", default=DEFAULT_TODO_REL,
                   help=f"chemin du TODO relatif au repo root (default : {DEFAULT_TODO_REL})")
    p.add_argument("--lock-file", default=str(DEFAULT_LOCK_FILE),
                   help=f"lockfile fcntl (default : {DEFAULT_LOCK_FILE})")
    p.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD,
                   help=f"N passes consécutives requises (default : {DEFAULT_THRESHOLD})")
    p.add_argument("--filename-re", default=DEFAULT_FILENAME_RE,
                   help=f"regex avec (?P<slug>...) pour matcher la ligne (default : {DEFAULT_FILENAME_RE})")
    p.add_argument("--col-etat", type=int, default=DEFAULT_COL_ETAT)
    p.add_argument("--col-fichier", type=int, default=DEFAULT_COL_FICHIER)
    p.add_argument("--col-verrou", type=int, default=DEFAULT_COL_VERROU)
    p.add_argument("--col-validation", type=int, default=DEFAULT_COL_VALIDATION)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("next")
    for name in ("claim", "release"):
        s = sub.add_parser(name)
        s.add_argument("slug")
    f = sub.add_parser("finish")
    f.add_argument("slug")
    f.add_argument("verdict", nargs="?")
    args = p.parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else DEFAULT_REPO_ROOT
    cfg = Config(
        repo_root=repo_root,
        todo_file=repo_root / args.todo_rel,
        lock_file=Path(args.lock_file),
        threshold=args.threshold,
        filename_re=args.filename_re,
        col_etat=args.col_etat,
        col_fichier=args.col_fichier,
        col_verrou=args.col_verrou,
        col_validation=args.col_validation,
    )
    short = session_short()
    if args.cmd == "next":
        cmd_next(cfg, short)
    elif args.cmd == "claim":
        cmd_claim(cfg, args.slug, short)
    elif args.cmd == "release":
        cmd_release(cfg, args.slug, short)
    elif args.cmd == "finish":
        cmd_finish(cfg, args.slug, args.verdict, short)


if __name__ == "__main__":
    main()
