#!/usr/bin/env python3
"""Atomically claim a task on a RESSOURCES_TODO.md row.

Usage: claim.py [--repo-root <path>] <extract|triage|embed|transcribe|validate> <slug>

Echoes success and exits 0 if the claim is granted. Otherwise prints the reason
and exits non-zero — the agent should try another task.

Pre-flight checks:
- $CLAUDE_CODE_SESSION_ID must be set.
- The slug must exist in the table.
- Verrou must be empty.
- The targeted step cell must be in a reclaimable state :
  - most steps   : empty / `—`.
  - triage       : `—` OR `K/N` with K<N (partial work, batch suivant).
                   `ok` / `skip` / `signalé …` are final, refused.
  - transcribe   : `—` OR `K/N` with K<N (partial work, batch suivant).
                   `ok` / `signalé …` are final, refused.
  - validate     : `—`, `0/2`, `1/2`. `2/2` final, `signalé …` blocked.
- Prerequisite step(s) must be satisfied:
  - triage      ← extract done
  - embed       ← triage == "ok" (skip is NOT enough — nothing to embed)
  - transcribe  ← embed done
  - validate    ← triage == "skip" OR transcribe ∈ {"ok", "corrigé"}
- For validate:
  - The current session must NOT match any of the composers' sessions (agents
    who ran Triage / Embed / Transcribe on this slug, detected from
    `<Step> <slug>: <result> (<short>)` git commit messages).
  - The current session must NOT match any prior Validate `ok` session on this
    slug (prevents the same agent from filling both 1/2 and 2/2). Same grep,
    on `^Validate <slug>: ok`.
  - The Validate cell is "in progress" while it holds `1/2` or `0/2` (after a
    `corrigé`) — those are reclaimable. `2/2` means done; `signalé …` means
    blocked.

On success: writes `<short> — <YYYY-MM-DD>` into Verrou, commits the change.
"""
import argparse
import datetime
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
# Standard "previous-step-done" prereqs. `embed` and `validate` have
# non-standard prereqs handled inline below.
PREREQ = {"triage": "extract", "transcribe": "embed"}
COMPOSER_STEPS = ("Triage", "Embed", "Transcribe")
VALIDATE_IN_PROGRESS = ("1/2", "0/2")
VALIDATE_DONE = "2/2"
# Cellule compteur `K/N` partagée par transcribe et triage : K<N = batch
# partiel (reclaimable), K>=N = terminé.
KN_RE = re.compile(r"^(\d+)/(\d+)$")


def is_done(value: str) -> bool:
    v = value.strip()
    return bool(v) and v != "—" and not v.startswith("signalé") and v != "abandon"


def _commit_shorts(pattern: str, repo_root: Path) -> set[str]:
    """Extract `(short)` session ids from commit subjects matching pattern."""
    shorts: set[str] = set()
    out = subprocess.run(
        ["git", "log", "--grep", pattern, "--pretty=format:%s"],
        capture_output=True, text=True, cwd=repo_root, check=False,
    ).stdout.strip()
    for line in out.splitlines():
        m = re.search(r"\(([0-9a-f]+)\)\s*$", line)
        if m:
            shorts.add(m.group(1))
    return shorts


def composer_shorts(slug: str, repo_root: Path) -> set[str]:
    """Short session ids of agents who ran Triage/Embed/Transcribe on this slug."""
    shorts: set[str] = set()
    for step_name in COMPOSER_STEPS:
        shorts |= _commit_shorts(f"^{step_name} {re.escape(slug)}:", repo_root)
    return shorts


def prior_validator_shorts(slug: str, repo_root: Path) -> set[str]:
    """Short session ids of agents who released a Validate `ok` on this slug."""
    return _commit_shorts(f"^Validate {re.escape(slug)}: ok ", repo_root)


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


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=None,
                        help="repo root (default: derived from this script's path)")
    parser.add_argument("step", choices=STEPS)
    parser.add_argument("slug")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else DEFAULT_REPO_ROOT
    todo = _paths.ressources_todo(repo_root)
    lock = repo_root / ".ressources.lock"
    step, slug = args.step, args.slug

    session = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if not session:
        sys.exit("error: CLAUDE_CODE_SESSION_ID env var is required")
    short = session[:8]
    today = datetime.date.today().isoformat()

    with open(lock, "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)

        lines = todo.read_text().splitlines(keepends=True)
        idx = find_row(lines, slug)
        if idx is None:
            sys.exit(f"error: slug not found in table: {slug}")

        cells = [c.strip() for c in lines[idx].strip("|\n").split("|")]

        verrou = cells[VERROU_COL]
        if verrou and verrou != "—":
            sys.exit(f"error: row locked by: {verrou}")

        current = cells[STEP_COL[step]]
        if step == "validate":
            if current == VALIDATE_DONE:
                sys.exit(f"error: step validate already done: {current}")
            if current and current != "—" and current.startswith("signalé"):
                sys.exit(f"error: step validate blocked: {current}")
            if current and current != "—" and current not in VALIDATE_IN_PROGRESS:
                sys.exit(f"error: unexpected validate cell value: {current!r}")
        elif step in ("transcribe", "triage") and current and current != "—":
            # K/N (K<N) = batch partiel → reclaimable. ok / skip / signalé =
            # final (skip ne concerne que triage).
            if current.startswith("signalé"):
                sys.exit(f"error: step {step} blocked: {current}")
            m = KN_RE.match(current)
            if m:
                k_prev, n_prev = int(m.group(1)), int(m.group(2))
                if k_prev >= n_prev:
                    sys.exit(f"error: step {step} already done: {current}")
                # K_prev < N_prev : fall through to prereq checks.
            else:
                sys.exit(f"error: step {step} already done: {current}")
        elif is_done(current):
            sys.exit(f"error: step {step} already done: {current}")

        prereq = PREREQ.get(step)
        if prereq and not is_done(cells[STEP_COL[prereq]]):
            sys.exit(f"error: prereq {prereq} not done (cell: {cells[STEP_COL[prereq]] or '—'})")

        if step == "embed":
            triage = cells[STEP_COL["triage"]]
            if triage != "ok":
                sys.exit(f"error: embed prereq not met — triage must be 'ok', got {triage!r}")

        if step == "validate":
            triage = cells[STEP_COL["triage"]]
            transcribe = cells[STEP_COL["transcribe"]]
            if not (triage == "skip" or transcribe in ("ok", "corrigé")):
                sys.exit(
                    f"error: validate prereq not met — need triage=='skip' or "
                    f"transcribe in {{ok,corrigé}} (triage={triage!r}, transcribe={transcribe!r})"
                )
            composers = composer_shorts(slug, repo_root)
            if not composers:
                sys.exit("error: cannot find any Triage/Embed/Transcribe commit — composer check failed")
            if short in composers:
                sys.exit(
                    f"error: you ({short}) composed this slug "
                    f"(one of triage/embed/transcribe) — cannot also validate"
                )
            prior = prior_validator_shorts(slug, repo_root)
            if short in prior:
                sys.exit(
                    f"error: you ({short}) already validated this slug once — "
                    f"the second pass must be done by a different agent"
                )

        cells[VERROU_COL] = f"{short} — {today}"
        lines[idx] = "| " + " | ".join(cells) + " |\n"
        todo.write_text("".join(lines))

        subprocess.run(
            ["git", "commit", "-m", f"Claim {step} {slug} ({short})", "--", str(todo)],
            check=True, cwd=repo_root,
        )
        print(f"claimed {step} on {slug}")


if __name__ == "__main__":
    main()
