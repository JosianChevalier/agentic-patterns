#!/usr/bin/env python3
"""inventory.py — peuple `2-consolide/outils/tasks.csv` depuis THEMES.md + sources prêtes.

**Idempotent : merge par `id`**, ne réécrit **jamais** une ligne existante
(≠ `ressources/inventory.py` qui écrase). Cf. `2-consolide/outils/docs/specs/inventory.md`,
`2-consolide/outils/docs/specs/scoping.md`, `2-consolide/outils/docs/specs/modele-donnees.md`.

Ce qu'il append :
  - **reduce** : une ligne par clé de `2-consolide/THEMES.md` (`reduce:<clé>`, `todo`).
  - **map**    : les 6 rapports `1-sources/1.2-nettoyes/reports/REPORT_*.md` + les slugs ressources en
    **Validate `2/2`** lus dans `1-sources/outils/ressources/RESSOURCES_TODO.md` (uniquement ceux-là).

Seuil oversize (`scoping.md`, sur métadonnées seules) : `lines > 600 OU imgs > 6`.
  - sous le seuil  → `map:<src>` `todo` (map normal) ;
  - au-dessus      → `map:<src>` `todo` `note=oversize` + **outline** régénérable
    dans `2-consolide/outils/outlines/<slug>.txt` (gitignored), **sans** enfants. Le découpage
    sera fait par un agent de scoping via `task.py split`.

Usage (cf. common/outils/CLAUDE.md — invocation directe, pas `python3`) :
  2-consolide/outils/inventory.py            # run réel : écrit le CSV sous flock + commit
  2-consolide/outils/inventory.py --dry-run  # affiche le plan, n'écrit rien
  2-consolide/outils/inventory.py --no-commit
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _store  # noqa: E402

THRESHOLD_LINES = 600
THRESHOLD_IMGS = 6

# Frontières de pagination régulières (pptx/pdf) — cf. scoping.md.
_BOUNDARY_RE = re.compile(r"^## (?:Slide|Page) \d+")
# Fallback (docx au fil de l'eau) : sous-titres / séparateurs.
_FALLBACK_RE = re.compile(r"^### |^---\s*$")


# --- THEMES.md ------------------------------------------------------------

def parse_theme_keys(themes_md: Path) -> "list[str]":
    """Clés contrôlées : première colonne (avant `#`) du bloc ```text de THEMES.md."""
    text = themes_md.read_text(encoding="utf-8")
    keys: list[str] = []
    in_block = False
    for line in text.splitlines():
        if line.startswith("```text"):
            in_block = True
            continue
        if in_block and line.startswith("```"):
            break
        if not in_block:
            continue
        head = line.split("#", 1)[0].strip()
        if re.fullmatch(r"[a-z0-9][a-z0-9-]*", head):
            keys.append(head)
    return keys


# --- Découverte des sources map ------------------------------------------

def discover_reports(root: Path) -> "list[tuple[str, str, Path]]":
    """(slug, input, chemin contenu) pour chaque 1-sources/1.2-nettoyes/reports/REPORT_*.md."""
    out = []
    for p in sorted(_store.reports_dir(root).glob("REPORT_*.md")):
        slug = p.stem[len("REPORT_"):]
        out.append((slug, f"1-sources/1.2-nettoyes/reports/{p.name}", p))
    return out


def discover_resources(root: Path) -> "list[tuple[str, str, Path]]":
    """(slug, input, chemin index.md) pour chaque slug ressource en Validate 2/2."""
    todo = _store.ressources_todo(root)
    out = []
    in_table = False
    for line in todo.read_text(encoding="utf-8").splitlines():
        if "INVENTORY:BEGIN" in line:
            in_table = True
            continue
        if "INVENTORY:END" in line:
            break
        if not in_table or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 8 or cells[0] in ("Slug", "---") or set(cells[0]) <= {"-"}:
            continue
        slug, validate = cells[0], cells[7]
        if validate != "2/2":
            continue
        index = _store.ressources_dir(root) / slug / "index.md"
        if not index.exists():
            print(f"WARNING: slug 2/2 sans index.md, ignoré: {slug}", file=sys.stderr)
            continue
        out.append((slug, f"1-sources/1.2-nettoyes/ressources/{slug}/", index))
    return out


# --- Seuil + outline ------------------------------------------------------

def measure(content: Path, count_imgs: bool = False) -> "tuple[int, int]":
    """(lines, imgs) cheap : `wc -l` du contenu + nb de *.png du dossier du slug.

    `imgs` n'a de sens que pour une **ressource**, dont `content` est
    `1-sources/1.2-nettoyes/ressources/<slug>/index.md` et `content.parent` le dossier du
    slug. Pour un **rapport** (`1-sources/1.2-nettoyes/reports/REPORT_*.md`, dossier plat partagé),
    `content.parent` vaut `reports/` : globber y compterait les PNG de TOUS les
    rapports. La spec (`scoping.md` § Seuil) fixe donc `imgs = 0` pour un
    rapport — d'où `count_imgs` passé par l'appelant qui sait quel cas c'est.
    """
    lines = len(content.read_text(encoding="utf-8").splitlines())
    imgs = len(list(content.parent.glob("*.png"))) if count_imgs else 0
    return lines, imgs


def is_oversize(lines: int, imgs: int) -> bool:
    return lines > THRESHOLD_LINES or imgs > THRESHOLD_IMGS


def generate_outline(content: Path) -> str:
    """Outline déterministe : `<titre> — L<début> (<n> lignes)` par frontière."""
    lines = content.read_text(encoding="utf-8").splitlines()
    bounds = [i for i, ln in enumerate(lines) if _BOUNDARY_RE.match(ln)]
    if not bounds:
        bounds = [i for i, ln in enumerate(lines) if _FALLBACK_RE.match(ln)]
    rows = []
    for k, start in enumerate(bounds):
        end = bounds[k + 1] if k + 1 < len(bounds) else len(lines)
        title = lines[start].lstrip("#").strip().lstrip("-").strip() or f"L{start + 1}"
        rows.append(f"{title} — L{start + 1} ({end - start} lignes)")
    return "\n".join(rows) + ("\n" if rows else "")


def outline_path(root: Path, slug: str) -> Path:
    return _store.outlines_dir(root) / f"{slug}.txt"


# --- Construction des lignes désirées ------------------------------------

def build_desired(root: Path, themes_md: Path) -> "list[dict]":
    """Lignes désirées dans l'ordre canonique : reduce, puis map (rapports, ressources).

    Chaque ligne porte une clé transitoire `_content` (chemin source pour
    l'outline) ignorée par `write_tasks` (qui ne sérialise que `FIELDS`).
    """
    rows: list[dict] = []
    for key in parse_theme_keys(themes_md):
        rows.append(_store.new_row(id=f"reduce:{key}", type="reduce", status="todo", input=key))
    # Seuls les slugs ressource portent des PNG comptables ; un rapport vit dans
    # le dossier plat `reports/` → imgs=0 (cf. measure / scoping.md § Seuil).
    for is_resource, sources in ((False, discover_reports(root)),
                                 (True, discover_resources(root))):
        for slug, inp, content in sources:
            lines, imgs = measure(content, count_imgs=is_resource)
            note = "oversize" if is_oversize(lines, imgs) else ""
            row = _store.new_row(id=f"map:{slug}", type="map", status="todo", input=inp, note=note)
            row["_content"] = content
            rows.append(row)
    return rows


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(prog="inventory.py", description=__doc__)
    parser.add_argument("--repo-root", help="racine du dépôt (défaut : dérivée du script)")
    parser.add_argument("--dry-run", action="store_true", help="affiche le plan, n'écrit rien")
    parser.add_argument("--no-commit", action="store_true", help="écrit le CSV mais ne committe pas")
    args = parser.parse_args(argv)

    root = _store.resolve_root(args.repo_root)
    themes_md = _store.themes_path(root)
    if not themes_md.exists():
        _store.die(f"introuvable: {themes_md}")

    desired = build_desired(root, themes_md)

    def report(new_rows: "list[dict]", total: int) -> None:
        n_red = sum(1 for r in new_rows if r["type"] == "reduce")
        n_over = sum(1 for r in new_rows if r.get("note") == "oversize")
        n_map = len(new_rows) - n_red
        print(f"nouvelles tâches: {len(new_rows)} ({n_red} reduce, {n_map} map dont {n_over} oversize)"
              f" — total {total}")
        for r in new_rows:
            flag = f"  [{r['note']}]" if r.get("note") else ""
            print(f"  + {r['type']:6} {r['id']}{flag}")

    if args.dry_run:
        existing_ids = {r["id"] for r in _store.read_tasks(root)}
        new_rows = [r for r in desired if r["id"] not in existing_ids]
        report(new_rows, len(existing_ids) + len(new_rows))
        return 0

    with _store.locked(root):
        existing = _store.read_tasks(root)
        existing_ids = {r["id"] for r in existing}
        new_rows = [r for r in desired if r["id"] not in existing_ids]
        if not new_rows:
            print(f"à jour — {len(existing)} tâches, rien à ajouter")
            return 0
        # Outlines des nouvelles sources oversize (scratch gitignored).
        for r in new_rows:
            if r.get("note") == "oversize":
                op = outline_path(root, r["id"].split(":", 1)[1])
                op.parent.mkdir(parents=True, exist_ok=True)
                op.write_text(generate_outline(r["_content"]), encoding="utf-8")
        _store.write_tasks(root, existing + new_rows)
        report(new_rows, len(existing) + len(new_rows))
        if not args.no_commit:
            _store.commit(root, [_store.tasks_path(root)],
                          f"consolide inventory: +{len(new_rows)} tâches (total {len(existing) + len(new_rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
