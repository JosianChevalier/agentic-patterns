#!/usr/bin/env python3
"""Walk 1-sources/1.1-raw/postfiles/, sha256, dedup, reconcile RESSOURCES_TODO.md.

**Idempotent : merge par slug** (≠ l'ancien comportement qui écrasait la table et
perdait le statut des lignes). Comme `2-consolide/outils/inventory.py`, ce script
réconcilie au lieu de régénérer :
  - slug déjà présent  → rafraîchit Source/Type (chemin courant) mais **garde**
    Extract…Verrou de l'existant ;
  - slug nouveau        → append en fin de table avec statut `—` ;
  - ligne existante absente du discovery (fichiers disparus + lignes manuelles
    type symlink contrats/meetings) → **reconduite telle quelle**, jamais droppée.

Le bloc DUPLICATES est dérivé du discovery → régénéré à chaque run.

Usage (cf. common/outils/CLAUDE.md — invocation directe, pas `python3`) :
  inventory.py                 # merge réconciliant (défaut)
  inventory.py --dry-run       # affiche les lignes qui seraient ajoutées, n'écrit rien
  inventory.py --reset         # ancien comportement destructif (regen total, setup pur)
  inventory.py [--repo-root <path>]
"""
import argparse
import hashlib
import re
import sys
import unicodedata
from pathlib import Path

import _paths

DEFAULT_REPO_ROOT = _paths.find_root()

EXT_TO_TYPE = {
    ".pptx": "pptx",
    ".docx": "docx",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
}
SKIP_EXTS = {".zip", ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v",
             ".wmv", ".flv", ".mpeg", ".mpg", ".ds_store"}

INVENTORY_BEGIN = "<!-- INVENTORY:BEGIN -->"
INVENTORY_END = "<!-- INVENTORY:END -->"
DUPLICATES_BEGIN = "<!-- DUPLICATES:BEGIN -->"
DUPLICATES_END = "<!-- DUPLICATES:END -->"


def slugify(name: str) -> str:
    name = name.rsplit(".", 1)[0]
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    return name.strip("_")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


NCOLS = 9  # Slug | Source | Type | Extract | Triage | Embed | Transcribe | Validate | Verrou


def parse_existing_rows(content: str) -> list[list[str]]:
    """Lignes de données du bloc INVENTORY existant, dans l'ordre (header/séparateur exclus).

    Chaque ligne → liste de cellules. Permet le merge : on préserve les colonnes
    de statut (Extract…Verrou) et l'ordre, on ne touche que Source/Type.
    """
    start = content.index(INVENTORY_BEGIN)
    end = content.index(INVENTORY_END)
    rows: list[list[str]] = []
    for line in content[start:end].splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if not cells or cells[0] == "Slug":
            continue
        if set("".join(cells)) <= {"-"}:  # ligne séparatrice |---|---|…
            continue
        rows.append((cells + ["—"] * NCOLS)[:NCOLS])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=None,
                        help="repo root (default: derived from this script's path)")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche les lignes qui seraient ajoutées, n'écrit rien")
    parser.add_argument("--reset", action="store_true",
                        help="regen total destructif (ancien comportement, setup pur)")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else DEFAULT_REPO_ROOT
    raw = _paths.postfiles_dir(repo_root)
    todo = _paths.ressources_todo(repo_root)

    if not raw.is_dir():
        sys.exit(f"1-sources/1.1-raw/postfiles/ not found at {raw}")

    by_sha: dict[str, list[tuple[Path, str]]] = {}
    skipped: list[str] = []
    for path in sorted(raw.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        ext = path.suffix.lower()
        if ext in SKIP_EXTS:
            continue
        if ext not in EXT_TO_TYPE:
            skipped.append(str(path.relative_to(repo_root)))
            continue
        sha = sha256_file(path)
        by_sha.setdefault(sha, []).append((path.relative_to(repo_root), EXT_TO_TYPE[ext]))

    if skipped:
        print("WARN: skipping unknown extensions:", file=sys.stderr)
        for s in skipped:
            print(f"  {s}", file=sys.stderr)

    used_slugs: set[str] = set()
    disc_rows: list[tuple[str, str, str, str]] = []
    dups: list[tuple[str, str]] = []
    for sha in sorted(by_sha.keys(), key=lambda s: str(by_sha[s][0][0]).lower()):
        entries = by_sha[sha]
        canonical_path, ftype = entries[0]
        base_slug = slugify(canonical_path.name)
        slug = base_slug
        n = 2
        while slug in used_slugs:
            slug = f"{base_slug}_{n}"
            n += 1
        used_slugs.add(slug)
        disc_rows.append((slug, str(canonical_path), ftype, sha[:8]))
        for dup_path, _ in entries[1:]:
            dups.append((slug, str(dup_path)))

    content = todo.read_text()

    # Defensive: each marker must appear exactly once. Otherwise we risk
    # replacing content inside surrounding prose that happens to mention them.
    for marker in (INVENTORY_BEGIN, INVENTORY_END, DUPLICATES_BEGIN, DUPLICATES_END):
        n = content.count(marker)
        if n != 1:
            sys.exit(f"marker {marker!r} must appear exactly once in {todo} (found {n})")

    # --- Merge réconciliant (≠ regen) ------------------------------------
    # Discovery indexé par slug pour rafraîchir Source/Type des lignes connues.
    disc_by_slug = {slug: (src, ftype) for slug, src, ftype, _ in disc_rows}
    existing = [] if args.reset else parse_existing_rows(content)
    existing_slugs = {r[0] for r in existing}

    merged: list[list[str]] = []
    for cells in existing:
        slug = cells[0]
        if slug in disc_by_slug:
            # Ligne connue : rafraîchir le chemin courant, garder le statut.
            src, ftype = disc_by_slug[slug]
            cells = [slug, f"`{src}`", ftype, *cells[3:]]
        # Sinon (fichier disparu / ligne manuelle symlink) : reconduite telle quelle.
        merged.append(cells)

    new_rows = [r for r in disc_rows if r[0] not in existing_slugs]
    for slug, src, ftype, _sha in new_rows:
        merged.append([slug, f"`{src}`", ftype, "—", "—", "—", "—", "—", "—"])

    table = [
        "| Slug | Source | Type | Extract | Triage | Embed | Transcribe | Validate | Verrou |\n",
        "|---|---|---|---|---|---|---|---|---|\n",
    ]
    for cells in merged:
        table.append("| " + " | ".join(cells) + " |\n")

    if dups:
        dup_lines = [f"- `{p}` → doublon de `{c}`\n" for c, p in dups]
    else:
        dup_lines = ["*(aucun doublon détecté)*\n"]

    if args.dry_run:
        for slug, src, ftype, _ in new_rows:
            print(f"  + {slug}  ({ftype})  `{src}`")
        print(f"inventory (dry-run): {len(disc_rows)} unique files, {len(dups)} duplicates, "
              f"+{len(new_rows)} new rows, {len(existing)} preserved")
        return

    new_inv = INVENTORY_BEGIN + "\n" + "".join(table) + INVENTORY_END
    new_dup = DUPLICATES_BEGIN + "\n" + "".join(dup_lines) + DUPLICATES_END

    content = re.sub(
        re.escape(INVENTORY_BEGIN) + r".*?" + re.escape(INVENTORY_END),
        lambda _m: new_inv,
        content, count=1, flags=re.DOTALL,
    )
    content = re.sub(
        re.escape(DUPLICATES_BEGIN) + r".*?" + re.escape(DUPLICATES_END),
        lambda _m: new_dup,
        content, count=1, flags=re.DOTALL,
    )

    todo.write_text(content)
    print(f"inventory: {len(disc_rows)} unique files, {len(dups)} duplicates, "
          f"+{len(new_rows)} new rows, {len(existing)} preserved")


if __name__ == "__main__":
    main()
