#!/usr/bin/env python3
"""project_arbitrages.py — projette les mini-ADR `1.3-arbitrages` en fragment couche 2.

**Déterministe, zéro LLM.** Plie tout `1-sources/1.3-arbitrages/NNNN-<slug>.md` en un
unique fragment `2-consolide/2.1-fragments/arbitrages.md`, groupé par thème, **une puce
par décision** avec citation `[arb: NNNN]`. Un arbitrage *est* déjà un fragment distillé
et taggé par thème → on ne le **mappe pas** (un agent LLM par fichier serait absurde à
~50 décisions/jour) : on le **projette**. Le reduce le consomme ensuite comme n'importe
quel fragment, **en tête de hiérarchie** (cf. `prompts/reduce.md`).

Règles de projection :
- **Provenance** : `candidat` / `settled` portée en tête de puce (`[candidat]` / `[settled]`)
  pour **survivre jusqu'à la fiche** (couche 3 distingue assumé vs confirmé).
- **Clés** : `theme:` ∈ `THEMES.md` **uniquement** (garde-fou à la source, fail-fast).

cf. `1-sources/1.3-arbitrages/CLAUDE.md`,
`2-consolide/outils/docs/specs/validate.md` (résolution `[arb:]` au gate 2/2).

Usage (cf. `common/outils/CLAUDE.md` — invocation directe, pas `python3`) :
  2-consolide/outils/project_arbitrages.py            # écrit + commit le fragment
  2-consolide/outils/project_arbitrages.py --dry-run  # imprime le fragment, n'écrit rien
  2-consolide/outils/project_arbitrages.py --no-commit
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _store  # noqa: E402

# Nom de fichier ADR : `NNNN-<slug>.md`, NNNN = séquence monotone à 4 chiffres.
_ADR_NAME = re.compile(r"^(?P<nnnn>\d{4})-(?P<slug>[a-z0-9][a-z0-9-]*)\.md$")

PROVENANCES = ("candidat", "settled")
SOURCE_TYPE = "arbitrage"   # cf. check.py SOURCE_TYPES — frontmatter du fragment projeté
MAP_SESSION = "projecteur"  # pas de session agent : projection déterministe


# --- Parsing d'un ADR -----------------------------------------------------

def parse_frontmatter(lines: "list[str]") -> "tuple[dict, int]":
    """(champs, index 1ʳᵉ ligne de corps). ({}, 0) si pas de bloc `---` … `---`.
    Miroir de `check.parse_frontmatter` (volontairement dupliqué : socle minimal)."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    fields: dict = {}
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return fields, i + 1
        if ":" in lines[i]:
            k, v = lines[i].split(":", 1)
            fields[k.strip()] = v.strip()
    return {}, 0


def parse_adr(text: str, filename: str) -> "dict":
    """Parse un mini-ADR en `{nnnn, slug, themes, provenance, fait}`.

    `themes` est une **liste** (un ADR peut être transverse) : `theme:` en frontmatter
    est une liste de clés séparées par des virgules. La projection émet la même puce
    sous chaque thème listé.

    Le **corps est le fait** : tout ce qui suit le titre `# NNNN · …`, aplati en une
    ligne (les puces du fragment sont mono-ligne). `die` sur tout ADR malformé (nom hors
    `NNNN-<slug>.md`, frontmatter incomplet, provenance hors {candidat, settled}, corps
    vide) : la projection est un garde-fou déterministe, un ADR cassé doit **bloquer**,
    pas produire un fragment muet.
    """
    name_m = _ADR_NAME.match(filename)
    if not name_m:
        _store.die(f"{filename}: nom hors convention `NNNN-<slug>.md`")
    nnnn, slug = name_m.group("nnnn"), name_m.group("slug")

    lines = text.splitlines()
    fm, body_start = parse_frontmatter(lines)
    if not fm:
        _store.die(f"{filename}: frontmatter absent ou non fermé (`---` … `---`)")
    themes = [t.strip() for t in fm.get("theme", "").split(",") if t.strip()]
    if not themes:
        _store.die(f"{filename}: frontmatter `theme:` manquant")
    provenance = fm.get("provenance", "").strip()
    if provenance not in PROVENANCES:
        _store.die(f"{filename}: `provenance` ∈ {list(PROVENANCES)} (vu: {provenance!r})")

    # Le corps = le fait : on saute le titre `# NNNN · …`, on aplatit le reste en
    # une ligne (join par espaces — un fait wrappé sur plusieurs lignes ne se tronque pas).
    fact_lines: "list[str]" = []
    seen_title = False
    for ln in lines[body_start:]:
        s = ln.strip()
        if not seen_title:
            if s.startswith("#"):
                seen_title = True
            continue
        if s:
            fact_lines.append(s)
    fait = " ".join(fact_lines)
    if not fait:
        _store.die(f"{filename}: corps (fait) absent sous le titre `# NNNN · …`")

    return {"nnnn": nnnn, "slug": slug, "themes": themes,
            "provenance": provenance, "fait": fait}


# --- Projection -----------------------------------------------------------

def project_fragment(adrs: "list[dict]", controlled: "set[str]") -> "str | None":
    """Assemble le fragment `arbitrages.md` (pur, testable hors I/O). `None` si
    aucun ADR (rien à projeter).

    - Groupe les ADR par thème (un ADR transverse apparaît sous **chacun** de
      ses thèmes), trie par `nnnn` intra-thème, thèmes triés.
    - `die` si un thème n'est pas une clé contrôlée de `THEMES.md` (par clé).
    """
    if not adrs:
        return None

    by_theme: "dict[str, list[dict]]" = {}
    for a in adrs:
        for theme in a["themes"]:
            if theme not in controlled:
                _store.die(f"{a['nnnn']}-{a['slug']}.md: clé de thème inconnue {theme!r} "
                           f"(absente de THEMES.md)")
            by_theme.setdefault(theme, []).append(a)

    out = [f"---\nsource: arbitrages\nsource_type: {SOURCE_TYPE}\n"
           f"map_session: {MAP_SESSION}\n---\n"]
    for theme in sorted(by_theme):
        out.append(f"\n## theme:{theme}\n")
        for a in sorted(by_theme[theme], key=lambda x: x["nnnn"]):
            out.append(f"- [{a['provenance']}] {a['fait']} [arb: {a['nnnn']}]")
    return "\n".join(out) + "\n"


def load_adrs(root: Path) -> "list[dict]":
    """Parse tous les `NNNN-*.md` du dossier d'arbitrages (triés par nom)."""
    adir = _store.arbitrages_dir(root)
    out = []
    for p in sorted(adir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        out.append(parse_adr(p.read_text(encoding="utf-8"), p.name))
    return out


def controlled_keys(root: Path) -> "set[str]":
    import inventory  # même dossier — réutilise le parseur de THEMES.md
    return set(inventory.parse_theme_keys(_store.themes_path(root)))


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(prog="project_arbitrages.py", description=__doc__)
    parser.add_argument("--repo-root", help="racine du dépôt (défaut : dérivée du script)")
    parser.add_argument("--dry-run", action="store_true", help="imprime le fragment, n'écrit rien")
    parser.add_argument("--no-commit", action="store_true", help="écrit le fragment mais ne committe pas")
    args = parser.parse_args(argv)

    root = _store.resolve_root(args.repo_root)
    fragment = project_fragment(load_adrs(root), controlled_keys(root))
    out_path = _store.arbitrages_fragment(root)

    if fragment is None:
        print("aucun arbitrage vivant — fragment non écrit")
        return 0

    if args.dry_run:
        sys.stdout.write(fragment)
        return 0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(fragment, encoding="utf-8")
    n = fragment.count("\n- ")
    print(f"projeté {n} arbitrage(s) → {out_path.relative_to(root)}")
    if not args.no_commit:
        _store.commit(root, [out_path], f"consolide arbitrages: projection ({n} décision(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
