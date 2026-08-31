#!/usr/bin/env python3
"""Release a claim, write the result into the table, commit.

Usage: release.py [--repo-root <path>] <extract|triage|embed|transcribe|validate> <slug> <result>

Result values (allow-list per step):
  extract     : done <sha8> | signalé <reason> | abandon
  triage      : ok | signalé <reason> | abandon
                (`ok` = batch fait — release.py calcule la cellule K/N puis
                 `ok`/`skip` à K==N. `skip` n'est plus une entrée agent : c'est
                 une valeur de cellule calculée quand zéro PNG retenu.)
  embed       : ok | signalé <reason> | abandon
  transcribe  : ok | signalé <reason> | abandon
  validate    : ok | corrigé | signalé <reason> | abandon

`abandon` releases the lock without writing a result (the cell stays `—`).

Validate has a 2/2 counter in its cell (not a raw result like other steps):
  ok      : — | 0/2 → 1/2 ; 1/2 → 2/2 (line done)
  corrigé : → 0/2 (forces 2 fresh passes after a correction)
  signalé : written as-is, blocks the line until arbitration

Transcribe has a K/N counter computed from the agent's `index.md` state
(K = embedded PNGs followed by a `<retranscription>` block, N = total embedded
PNGs at the slug root). The agent releases `ok` ; release.py reads the
markdown and writes `K/N` (or `ok` if K == N — N == 0 is treated the same).
This allows several claims on the same Transcribe cell, each handling up to
~3 PNGs, to drain big slugs without busting the orchestrator's per-agent
absolute cap (cf. run 20260528-005952 : 10-slide pptx, kill à 601s, 3/10
done).

Triage has the same K/N mechanism (cf. TRIAGE_BATCH_SPEC). The agent releases
`ok` (= « batch fait ») ; release.py reads `triage.md` and counts K = distinct
candidate-page refs decided in `## Retenus` ∪ `## Skip`, N = candidate PNGs on
disk (`_all_pages/*.png`, sinon `media/*`). Cell becomes `K/N` while K<N, and
at K==N becomes `ok` if `## Retenus` holds ≥1 bullet, else `skip` (zero PNG
retained → short-circuits embed + transcribe). The agent never releases `skip`
itself — it's the computed value.

The Verrou must be held by the current $CLAUDE_CODE_SESSION_ID, otherwise the
release is rejected (prevents stealing another agent's work).

On success: stages RESSOURCES_TODO.md + 1-sources/1.2-nettoyes/ressources/<slug>/ (if it
exists), commits with `<Step> <slug>: <result> (<short>)` — the short session
id in the commit message is what claim.py greps for the composer / prior-
validator checks. For Transcribe, `<result>` in the commit message is the
final cell value (`ok` or `K/N` or `signalé …` or `abandon`).
"""
import argparse
import fcntl
import os
import re
import subprocess
import sys
from pathlib import Path

import _paths

DEFAULT_REPO_ROOT = _paths.find_root()

STEPS = ("extract", "triage", "embed", "transcribe", "validate")
# Cols: Slug(0) Source(1) Type(2) Extract(3) Triage(4) Embed(5) Transcribe(6) Validate(7) Verrou(8)
STEP_COL = {"extract": 3, "triage": 4, "embed": 5, "transcribe": 6, "validate": 7}
VERROU_COL = 8
MIN_COLS = 9

# Per-step allow-list for the <result> arg. `signalé <reason>` forbids `|` to
# avoid breaking the markdown table when the result lands in a cell.
RESULT_RE = {
    "extract":    re.compile(r"^(done [0-9a-f]{8}|signalé [^|]+|abandon)$"),
    "triage":     re.compile(r"^(ok|signalé [^|]+|abandon)$"),
    "embed":      re.compile(r"^(ok|signalé [^|]+|abandon)$"),
    "transcribe": re.compile(r"^(ok|signalé [^|]+|abandon)$"),
    "validate":   re.compile(r"^(ok|corrigé|signalé [^|]+|abandon)$"),
}


def next_validate_cell(current: str, result: str) -> str:
    """Compute the next Validate cell value given current cell and a result."""
    current = current.strip()
    if result.startswith("signalé"):
        return result
    if result == "corrigé":
        return "0/2"
    # result == "ok"
    if current in ("", "—", "0/2"):
        return "1/2"
    if current == "1/2":
        return "2/2"
    if current == "2/2":
        sys.exit(f"error: validate already done (2/2) — cannot increment")
    sys.exit(f"error: unexpected validate cell {current!r} — cannot increment on ok")


# Real embeds are basenames at the slug root (e.g. `![](slide-04.png)`). Raw
# rasterized references kept by extract.py for context (e.g.
# `![](./_all_pages/slide-04.png)`) contain a path separator and must NOT
# count : ils ne sont pas retranscrits.
EMBED_LINE_RE = re.compile(r"^!\[\]\(([^/)\s]+\.png)\)\s*$")
RETRANSCRIPTION_OPEN_RE = re.compile(r"^<retranscription>\s*$")
# Cellule compteur `K/N` partagée par transcribe et triage.
KN_RE = re.compile(r"^(\d+)/(\d+)$")


def count_transcribe(index_md: str) -> tuple[int, int]:
    """Compute (K, N) for the Transcribe step from `index.md` content.

    N = real embedded PNGs (basename only, no path separator).
    K = embedded PNGs followed by a `<retranscription>` opening tag before the
        next embed (or EOF).
    """
    lines = index_md.splitlines()
    embed_positions = [i for i, line in enumerate(lines) if EMBED_LINE_RE.match(line)]
    n = len(embed_positions)
    k = 0
    for idx, pos in enumerate(embed_positions):
        next_pos = embed_positions[idx + 1] if idx + 1 < n else len(lines)
        for j in range(pos + 1, next_pos):
            if RETRANSCRIPTION_OPEN_RE.match(lines[j]):
                k += 1
                break
    return k, n


def parse_kn_cell(cell: str) -> tuple[int, int] | None:
    """Parse a `K/N` counter cell (transcribe or triage). Returns (K, N) if
    `K/N`, else None (covers `—`, empty, `ok`, `skip`, `signalé …`)."""
    m = KN_RE.match(cell.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


# ─── Triage K/N (cf. TRIAGE_BATCH_SPEC) ──────────────────────────────────────
# Réfs de page candidates citées dans triage.md : `_all_pages/slide-N.png`
# (pptx/pdf) ou `media/imageN.png` (docx). On ne retient que le motif de page,
# pas le préfixe de dossier — le compteur K est le nombre de basenames
# distincts tranchés.
TRIAGE_PAGE_RE = re.compile(r"(slide-\d+|page-\d+|image\d+)\.png")
H2_RE = re.compile(r"^##\s+(.*?)\s*$")
RETENUS_RE = re.compile(r"^Retenus$", re.IGNORECASE)
SKIP_RE = re.compile(r"^Skip$", re.IGNORECASE)
BULLET_RE = re.compile(r"^\s*[-*]\s+\S")


def _section_bodies(triage_md: str, want) -> list[str]:
    """Lignes de corps des sections H2 dont le titre matche un des prédicats
    `want` (liste de regex compilés testés sur le titre)."""
    out: list[str] = []
    keep = False
    for line in triage_md.splitlines():
        m = H2_RE.match(line)
        if m:
            keep = any(rx.match(m.group(1)) for rx in want)
            continue
        if keep:
            out.append(line)
    return out


def count_triaged(triage_md: str) -> int:
    """K = nb de basenames de page distincts tranchés (## Retenus ∪ ## Skip)."""
    body = "\n".join(_section_bodies(triage_md, (RETENUS_RE, SKIP_RE)))
    return len({m.group(0) for m in TRIAGE_PAGE_RE.finditer(body)})


def count_candidates(slug_dir: Path) -> int:
    """N = nb de PNG candidats : `_all_pages/*.png` ; si 0, `media/*`."""
    pages = list(slug_dir.glob("_all_pages/*.png"))
    if pages:
        return len(pages)
    return len(list(slug_dir.glob("media/*")))


def triage_has_retained(triage_md: str) -> bool:
    """True si la section `## Retenus` contient ≥1 puce."""
    return any(BULLET_RE.match(line) for line in _section_bodies(triage_md, (RETENUS_RE,)))


def find_row(lines: list[str], slug: str) -> int | None:
    for i, line in enumerate(lines):
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|\n").split("|")]
        if len(cells) < MIN_COLS or cells[0] in ("Slug", "---"):
            continue
        if cells[0] == slug:
            return i
    return None


SHORT_RE = re.compile(r"^[0-9a-f]{8}$")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=None,
                        help="repo root (default: derived from this script's path)")
    parser.add_argument("--force-abandon-orphan", metavar="SHORT", default=None,
                        help="Mode admin (orchestrateur) : clear un verrou orphelin "
                             "laissé par l'agent <SHORT> (8 hex). Result doit être "
                             "'abandon'. CLAUDE_CODE_SESSION_ID non requis. "
                             "Bypass la garde 'tu dois posséder le lock' mais reste "
                             "sous flock — pas de TOCTOU avec claim/release concurrents.")
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("slug")
    parser.add_argument("result")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else DEFAULT_REPO_ROOT
    todo = _paths.ressources_todo(repo_root)
    lock = repo_root / ".ressources.lock"
    extracted = _paths.ressources_dir(repo_root)
    step, slug, result = args.step, args.slug, args.result

    admin_short = args.force_abandon_orphan
    if admin_short is not None:
        if result != "abandon":
            sys.exit("error: --force-abandon-orphan requires result='abandon'")
        if not SHORT_RE.match(admin_short):
            sys.exit(f"error: --force-abandon-orphan SHORT must be 8 hex chars: {admin_short!r}")
        short = admin_short
    else:
        if not RESULT_RE[step].match(result):
            sys.exit(f"error: invalid result for {step}: {result!r} (expected pattern: {RESULT_RE[step].pattern})")
        session = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
        if not session:
            sys.exit("error: CLAUDE_CODE_SESSION_ID env var is required")
        short = session[:8]

    with open(lock, "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)

        lines = todo.read_text().splitlines(keepends=True)
        idx = find_row(lines, slug)
        if idx is None:
            if admin_short is not None:
                print(f"slug {slug!r} not found in table — nothing to abandon")
                return
            sys.exit(f"error: slug not found in table: {slug}")

        cells = [c.strip() for c in lines[idx].strip("|\n").split("|")]
        verrou = cells[VERROU_COL]

        # commit_result is what we put after `<Step> <slug>:` in the commit
        # message. Equals the input result for most steps, but for Transcribe
        # ok we substitute the computed cell value (`ok` or `K/N`) so the log
        # reflects the actual progression.
        commit_result = result

        if admin_short is not None:
            if not verrou or verrou == "—" or not verrou.startswith(admin_short):
                print(f"no orphan lock to clear for {slug} "
                      f"(verrou={verrou!r}, expected start={admin_short!r})")
                return
            cells[VERROU_COL] = "—"
        else:
            if verrou and verrou != "—" and not verrou.startswith(short):
                sys.exit(f"error: you ({short}) don't hold this lock (held by: {verrou})")
            if result == "abandon":
                cells[VERROU_COL] = "—"
            elif step == "validate":
                cells[STEP_COL[step]] = next_validate_cell(cells[STEP_COL[step]], result)
                cells[VERROU_COL] = "—"
            elif step == "transcribe" and result == "ok":
                index_path = extracted / slug / "index.md"
                if not index_path.exists():
                    sys.exit(f"error: {index_path} not found — cannot compute K/N for transcribe")
                k, n = count_transcribe(index_path.read_text())
                if k > n:
                    sys.exit(f"error: K={k} > N={n} in {index_path} — impossible state")
                prev = parse_kn_cell(cells[STEP_COL["transcribe"]])
                if prev is not None and k < prev[0]:
                    sys.exit(
                        f"error: K decreased ({prev[0]} → {k}) in {index_path} — "
                        f"retranscriptions removed? not committing"
                    )
                new_cell = "ok" if n == 0 or k == n else f"{k}/{n}"
                cells[STEP_COL["transcribe"]] = new_cell
                cells[VERROU_COL] = "—"
                commit_result = new_cell
            elif step == "triage" and result == "ok":
                triage_path = extracted / slug / "triage.md"
                if not triage_path.exists():
                    sys.exit(f"error: {triage_path} not found — cannot compute K/N for triage")
                triage_md = triage_path.read_text()
                k = count_triaged(triage_md)
                n = count_candidates(extracted / slug)
                if k > n:
                    sys.exit(
                        f"error: K={k} > N={n} for {slug} — impossible state "
                        f"(more decided page refs in triage.md than candidate PNGs)"
                    )
                prev = parse_kn_cell(cells[STEP_COL["triage"]])
                if prev is not None and k < prev[0]:
                    sys.exit(
                        f"error: K decreased ({prev[0]} → {k}) in {triage_path} — "
                        f"decisions removed? not committing"
                    )
                # K==N (N==0 inclus : standalone retenu → ok ; rien → skip).
                if k == n:
                    new_cell = "ok" if triage_has_retained(triage_md) else "skip"
                else:
                    new_cell = f"{k}/{n}"
                cells[STEP_COL["triage"]] = new_cell
                cells[VERROU_COL] = "—"
                commit_result = new_cell
            else:
                cells[STEP_COL[step]] = result
                cells[VERROU_COL] = "—"

        lines[idx] = "| " + " | ".join(cells) + " |\n"
        todo.write_text("".join(lines))

        paths = [str(todo)]
        slug_dir = extracted / slug
        # En mode force-abandon-orphan : ne JAMAIS inclure slug_dir. Le commit
        # ne doit toucher que le TODO. Un dossier laissé par un extract avorté
        # (vide ou avec des fichiers untracked tels que `_signaled.md` écrit
        # via Write) ferait planter `git commit -- <dir>` avec :
        #     pathspec '…/1-sources/1.2-nettoyes/ressources/<slug>' did not match any
        #     file(s) known to git
        # (git ne stage pas les untracked via pathspec). Le contenu du dossier
        # sera commité plus tard, soit manuellement, soit par un release.py
        # normal sur un futur claim réussi.
        if admin_short is None and slug_dir.is_dir():
            # Mode release normal : on stage nous-mêmes TOUT le slug_dir —
            # tracked modifiés + untracked neufs produits par le step
            # (triage.md, slide-*.png au root, index.md). `git commit --
            # <pathspec>` ne peut PAS committer un fichier untracked sans
            # `git add` préalable, et en headless l'agent n'a pas le droit de
            # `git add` (hors allowlist) → sans ça les embeds restaient
            # danglants au checkout. Le `git add` est scopé au slug que l'agent
            # possède (Verrou tenu) → concurrence-safe. `.gitignore` couvre
            # `_all_pages/` + `.extract.md` : ils ne seront pas stagés.
            subprocess.run(
                ["git", "add", "--", str(slug_dir)],
                check=True, cwd=repo_root,
            )
            # Garde-fou : si après le add le slug_dir n'a toujours aucun fichier
            # connu de git (cas limite : que des fichiers ignorés), ne pas le
            # passer à `git commit -- <pathspec>` qui planterait sur
            # "pathspec did not match any file(s) known to git".
            known = subprocess.run(
                ["git", "ls-files", "--", str(slug_dir)],
                capture_output=True, text=True, cwd=repo_root, check=False,
            )
            if known.stdout.strip():
                paths.append(str(slug_dir))

        if admin_short is not None:
            msg = f"Auto-abandon {step} {slug} (orchestrator: agent {short} exited without release)"
        else:
            msg = f"{step.capitalize()} {slug}: {commit_result} ({short})"
        subprocess.run(["git", "commit", "-m", msg, "--", *paths], check=True, cwd=repo_root)
        if admin_short is not None:
            print(f"auto-abandon {step} {slug} ({short})")
        else:
            print(f"released {step} on {slug}: {commit_result}")


if __name__ == "__main__":
    main()
