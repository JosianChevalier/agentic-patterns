#!/usr/bin/env python3
"""Chemins data centralisés du pipeline ressources (`1-sources/1.2-nettoyes/ressources/`).

Module importé par les scripts du pipeline — **pas invoqué en direct**. Miroir
de `2-consolide/outils/_store.py` pour la couche ressources : source unique de
vérité des chemins data, pour qu'aucun littéral `root / "…" / "…"` ne traîne
éparpillé dans les scripts (un futur déplacement de dossier ne touche qu'ici).

- `find_root()` : racine du dépôt par remontée vers `.git` (insensible à la
  profondeur du script — immunise les `git mv` d'outils entre couches).
- `postfiles_dir` / `ressources_dir` : les deux familles de chemins data
  (binaires sources + extractions).
- `ressources_todo` : l'inventaire `RESSOURCES_TODO.md` (état du pipeline), rangé
  avec ses scripts dans `1-sources/outils/ressources/`.
"""
from pathlib import Path


def find_root(start: "Path | None" = None) -> Path:
    """Racine du dépôt = premier ancêtre contenant `.git` (fichier ou dossier).

    **Insensible à la profondeur du script** : immunise les déplacements d'outils
    entre couches (un `git mv` de `1-sources/outils/ressources/` ne casse plus la résolution).
    Fallback historique (`parent.parent.parent`) si aucun `.git` trouvé.
    """
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        if (parent / ".git").exists():
            return parent
    return Path(__file__).resolve().parent.parent.parent


DEFAULT_REPO_ROOT = find_root()


def resolve_root(override: "str | None" = None) -> Path:
    """Racine du dépôt (override explicite — typiquement `--repo-root` en test —
    ou dérivée du chemin du script)."""
    return Path(override).resolve() if override else DEFAULT_REPO_ROOT


# --- Chemins data ----------------------------------------------------------
# Dérivés de `root`. Toute construction de chemin data passe par un de ces
# helpers (pas de littéral éparpillé dans les scripts).

def postfiles_dir(root: Path) -> Path:
    """Binaires sources CATS (gitignored). ← ancien `raw-downloaded/`."""
    return root / "1-sources" / "1.1-raw" / "postfiles"


def ressources_dir(root: Path) -> Path:
    """Extractions grepables `<slug>/index.md` + visuels. ← ancien `ressources/extracted/`."""
    return root / "1-sources" / "1.2-nettoyes" / "ressources"


def ressources_todo(root: Path) -> Path:
    """Inventaire `RESSOURCES_TODO.md` (état du pipeline). Rangé avec ses scripts
    dans la couche outils. ← ancien `ressources/RESSOURCES_TODO.md`."""
    return root / "1-sources" / "outils" / "ressources" / "RESSOURCES_TODO.md"
