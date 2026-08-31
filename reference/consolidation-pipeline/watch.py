#!/usr/bin/env python3
"""watch.py — suit le log d'un run d'orchestrateur au fil de l'eau.

Streame les nouvelles lignes de `2-consolide/outils/.orchestrator/<run-id>/orchestrator.log`
sur stdout (une ligne = un event, line-buffered) et **sort dès que la dernière
ligne porte le marqueur terminal** « flags : » écrit par `orchestrate.py` en fin
de run. Conçu pour tourner dans l'outil `Monitor` (son `sleep` est en background,
légitime) — il remplace la boucle shell inline que le bandeau imprimait avant
(non allowlistable : le chemin porte le run-id qui change à chaque run).

Usage (depuis la racine du repo, chemin relatif — cf. `common/outils/CLAUDE.md`) :

    2-consolide/outils/watch.py <run-id>      # suit ce run
    2-consolide/outils/watch.py               # auto-détecte le run le plus récent

Allowlist : couvert par `Bash(2-consolide/outils/*.py *)` et `Bash(2-consolide/outils/*.py)`
→ zéro prompt avec ou sans argument. Spec : `2-consolide/outils/docs/specs/orchestrateur.md`
§ Bandeau de monitoring / § Contrat avec `Monitor`.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _store       # noqa: E402
import orchestrate  # noqa: E402  (constantes RUN_LOG / TERMINAL_MARKER)

POLL_INTERVAL_S = 2.0     # période de poll (parité avec l'ancienne boucle inline).


def orchestrator_dir(root: Path) -> Path:
    """Dossier qui contient un sous-dossier par run : `2-consolide/outils/.orchestrator/`."""
    return _store.orchestrator_dir(root)


def latest_run(root: Path) -> "str | None":
    """Run le plus récent : le sous-dossier de `2-consolide/outils/.orchestrator/` dont le
    `orchestrator.log` a le `mtime` le plus récent. `None` si aucun run loggé."""
    base = orchestrator_dir(root)
    if not base.is_dir():
        return None
    runs = [d for d in base.iterdir() if d.is_dir() and (d / orchestrate.RUN_LOG).exists()]
    if not runs:
        return None
    return max(runs, key=lambda d: (d / orchestrate.RUN_LOG).stat().st_mtime).name


def stream(log_path: Path, poll_interval: float = POLL_INTERVAL_S) -> int:
    """Émet les nouvelles lignes de `log_path` au fil de l'eau (chaque ligne flushée),
    et **retourne dès que la dernière ligne porte le marqueur terminal** (R17 de
    `orchestrateur.md`). Si le log n'existe pas encore (orchestrateur qui démarre),
    on poll jusqu'à ce qu'il apparaisse — pas de faux exit. Boucle non bornée comme
    l'ancienne inline : c'est le marqueur terminal qui clôt, pas un timeout."""
    emitted = 0
    while True:
        if log_path.exists():
            lines = log_path.read_text(encoding="utf-8").splitlines()
            if len(lines) > emitted:
                for line in lines[emitted:]:
                    print(line, flush=True)         # 1 event/ligne, flushé (parité log_event)
                emitted = len(lines)
            # `break` sur la DERNIÈRE ligne uniquement (parité `tail -n1 | grep`) :
            # « flags : » n'apparaît qu'en queue, après RUN.md/FLAGS.md (R36/R17).
            if lines and orchestrate.TERMINAL_MARKER in lines[-1]:
                return 0
        time.sleep(poll_interval)


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_id", nargs="?",
                        help="run à suivre (sous-dossier de 2-consolide/outils/.orchestrator/). "
                             "Omis → run le plus récent (mtime du log).")
    parser.add_argument("--poll", type=float, default=POLL_INTERVAL_S,
                        help=f"période de poll en secondes (default: {POLL_INTERVAL_S}).")
    args = parser.parse_args(argv)

    root = _store.resolve_root()
    run_id = args.run_id or latest_run(root)
    if run_id is None:
        print(f"error: aucun run sous {orchestrator_dir(root)} "
              f"(orchestrateur jamais lancé ?)", file=sys.stderr)
        return 2

    log_path = orchestrator_dir(root) / run_id / orchestrate.RUN_LOG
    # Note sur stderr pour ne pas polluer le flux d'events (stdout) du Monitor.
    print(f"# watch {run_id} → {log_path}", file=sys.stderr, flush=True)
    return stream(log_path, poll_interval=args.poll)


if __name__ == "__main__":
    raise SystemExit(main())
