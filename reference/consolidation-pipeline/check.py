#!/usr/bin/env python3
"""check.py — linter de sourçage déterministe (fragment & consolidé).

Garde-fou mécanique : tout fait pointe vers une source réelle (anti-extrapolation).
**Ne vérifie pas la fidélité** (c'est le gate 2/2 cognitif, cf. `validate.md`).
Pur linter, lecture seule (ne touche ni le CSV ni git). Câblé dans `task.py done`
(S5) ; échec → `done` refuse, la tâche reste `claimed`.

Spec : `2-consolide/outils/docs/specs/check.md`, `2-consolide/outils/docs/specs/formats.md`, `2-consolide/CLAUDE.md`
(format thématique). → *pourquoi déterministe vs cognitif* : `outils/docs/philosophy/gate-fidelite.md`.

Usage :
  check.py fragment  <chemin>   # lint un 2-consolide/2.1-fragments/<src>.md
  check.py consolide <chemin>   # lint un 2-consolide/2.2-content/<theme>.md

Exit 0 = clean ; exit 1 = violations (listées sur stderr).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _store  # noqa: E402

THEME_LINE = re.compile(r"^## theme:(?P<key>.+?)\s*$")
ECARTE_LINE = re.compile(r"^## écarté(:\S+)?\s*$")
BULLET = re.compile(r"^\s*[-*] ")
# Suite de ≥1 réf accolée en fin de puce — regex de check.md.
REF_SUFFIX = re.compile(r"(?:\s*\[(?:src|res|arb):[^\]]+\])+\s*$")
ONE_REF = re.compile(r"\[(?P<kind>src|res|arb):(?P<body>[^\]]+)\]")
ANY_REF = ONE_REF  # même motif, recherché n'importe où dans une section
NO_THEME = re.compile(r"^<!--\s*aucun thème\s*-->\s*$")
# `arbitrage` = fragment projeté (déterministe) de `1-sources/1.3-arbitrages/`, cf.
# project_arbitrages.py — pas produit par un agent map, mais linté comme un fragment.
SOURCE_TYPES = {"report", "ressource", "arbitrage"}
CONSOLIDE_SECTIONS = [
    "Cœur d'industrie",
    "Matérialisation CATS",
    "Tension industrie ↔ CATS",
    "Points flous",
    "Sources",
]
CATS_SECTION = "Matérialisation CATS"
SIZE_MAX = 300


# --- Vocabulaire & sources connues ---------------------------------------

def load_theme_keys(root: Path) -> "set[str]":
    """Clés contrôlées de THEMES.md (réutilise le parseur d'inventory)."""
    import inventory  # même dossier
    return set(inventory.parse_theme_keys(_store.themes_path(root)))


def theme_key_ok(key: str, controlled: "set[str]") -> bool:
    return key in controlled or key.startswith("_à-créer")


def known_report_slugs(root: Path) -> "set[str]":
    return {p.stem[len("REPORT_"):] for p in _store.reports_dir(root).glob("REPORT_*.md")}


# --- Résolution des refs --------------------------------------------------

def ref_resolves(kind: str, body: str, root: Path, reports: "set[str]") -> bool:
    """`[src:…]` → rapport connu (slug ou chemin reports/) ; `[res:…]` → existe
    sous 1-sources/1.2-nettoyes/ressources/ ; `[arb:NNNN]` → mini-ADR
    `1-sources/1.3-arbitrages/NNNN-*.md` existe (le fait y est, trivialement présent).
    Ancres `§N` / `#L…` non vérifiées ligne à ligne."""
    body = body.strip()
    if kind == "arb":
        # `[arb:0042]` → le fichier ADR lui-même EST la source (cf. validate.md).
        nnnn = body.split("§", 1)[0].split("#", 1)[0].strip()
        if not re.fullmatch(r"\d{4}", nnnn):
            return False
        return any(_store.arbitrages_dir(root).glob(f"{nnnn}-*.md"))
    if kind == "src":
        # Localisateur = body sans son ancre `§<repère>` / `#L…`. On décide
        # chemin-vs-slug sur lui SEUL : un `/` dans le repère (§CI/CD/CT) n'est
        # pas un séparateur de chemin (sinon un slug valide bascule en faux chemin).
        loc = body.split("§", 1)[0].split("#", 1)[0].strip()
        if "/" in loc:  # forme chemin (1-sources/1.2-nettoyes/reports/REPORT_x §N)
            return (root / loc).exists()
        return bool(loc) and loc.split()[0] in reports  # `<slug> §N` → slug
    # kind == res : `<slug>` ou `<slug>/<fichier>`
    target = body.split("#", 1)[0].split("§", 1)[0].strip()
    parts = target.split("/", 1)
    base = _store.ressources_dir(root) / parts[0]
    return (base / parts[1]).exists() if len(parts) == 2 else base.is_dir()


def check_refs_in(text: str, root: Path, reports: "set[str]") -> bool:
    """Vrai si ≥1 réf de `text` résout."""
    return any(ref_resolves(m.group("kind"), m.group("body"), root, reports)
               for m in ANY_REF.finditer(text))


def lint_bullet_refs(line: str, lineno: int, root: Path, reports: "set[str]",
                     errors: "list[str]") -> None:
    """Une puce de fragment doit finir par ≥1 réf, chacune résolvable."""
    m = REF_SUFFIX.search(line)
    if not m:
        errors.append(f"L{lineno}: puce sans citation en fin de ligne")
        return
    for r in ONE_REF.finditer(m.group(0)):
        if not ref_resolves(r.group("kind"), r.group("body"), root, reports):
            errors.append(f"L{lineno}: réf non résolue [{r.group('kind')}:{r.group('body')}]")


# --- Frontmatter ----------------------------------------------------------

def parse_frontmatter(lines: "list[str]") -> "tuple[dict, int]":
    """Renvoie (champs, index 1ʳᵉ ligne de corps). ({}, 0) si pas de bloc fermé."""
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


# --- Lint fragment --------------------------------------------------------

def lint_fragment(path: Path, root: Path) -> "list[str]":
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    controlled = load_theme_keys(root)
    reports = known_report_slugs(root)

    fm, body_start = parse_frontmatter(lines)
    if not fm:
        errors.append("frontmatter absent ou non fermé (`---` … `---`)")
    if not fm.get("source"):
        errors.append("frontmatter: `source:` manquant")
    if fm.get("source_type") not in SOURCE_TYPES:
        errors.append(f"frontmatter: `source_type` ∈ {sorted(SOURCE_TYPES)} (vu: {fm.get('source_type')!r})")
    if not fm.get("map_session"):
        errors.append("frontmatter: `map_session:` manquant")

    in_theme = False
    saw_theme_or_none = False
    for i in range(body_start, len(lines)):
        line, lineno = lines[i], i + 1
        m = THEME_LINE.match(line)
        if m:
            in_theme = True
            saw_theme_or_none = True
            if not theme_key_ok(m.group("key"), controlled):
                errors.append(f"L{lineno}: clé de thème inconnue: {m.group('key')!r}")
            continue
        if NO_THEME.match(line):
            saw_theme_or_none = True
            in_theme = False
            continue
        if ECARTE_LINE.match(line):  # candidat arbitré-rejeté → archive figée
            saw_theme_or_none = True  # la section compte comme contenu
            in_theme = False          # puces en dessous = non lintées
            continue
        if line.startswith("## "):  # autre section → hors contexte thème
            in_theme = False
            continue
        if in_theme and BULLET.match(line):
            lint_bullet_refs(line, lineno, root, reports, errors)

    if not saw_theme_or_none:
        errors.append("aucune section `## theme:<clé>` ni `<!-- aucun thème -->`")
    return errors


# --- Lint consolidé -------------------------------------------------------

def split_sections(lines: "list[str]") -> "dict[str, list[str]]":
    """Map titre de `## ` → lignes de la section (jusqu'au prochain `## `)."""
    out: dict[str, list[str]] = {}
    current = None
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return out


def is_formation_fiche(path: Path) -> bool:
    """Fiche de l'axe formation (nom préfixé `formation-`, cf. CLAUDE.md §3).
    Son propos n'est pas « comment CATS fait X » → la structure consolidé
    (5 sections industrie↔CATS) ne s'applique pas."""
    return path.stem.startswith("formation-")


def lint_consolide(path: Path, root: Path) -> "list[str]":
    errors: list[str] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    reports = known_report_slugs(root)

    # Frontmatter « quand_piocher » — index de découverte greppable, exigé sur les
    # deux axes (cf. reduce.md § Règles communes + 2-consolide/CLAUDE.md § Format).
    # Présence seule : on ne contrôle pas le contenu de la phrase.
    fm, body_start = parse_frontmatter(lines)
    if not fm:
        errors.append("frontmatter absent ou non fermé (`---` … `---`)")
    if not fm.get("quand_piocher"):
        errors.append("frontmatter: `quand_piocher:` manquant (en-tête « Quand piocher ici »)")
    body = lines[body_start:]

    first = next((ln for ln in body if ln.strip()), "")
    if not re.match(r"^#\s+\S", first):
        errors.append("titre `# <clé>` manquant en tête")

    # Fiches `formation-*` : structure libre. On saute les sections imposées
    # et la citation CATS ; on garde titre, refs cassées, taille.
    if not is_formation_fiche(path):
        sections = split_sections(body)
        for want in CONSOLIDE_SECTIONS:
            if want not in sections:
                errors.append(f"section manquante: « {want} »")

        if CATS_SECTION in sections:
            if not check_refs_in("\n".join(sections[CATS_SECTION]), root, reports):
                errors.append(f"« {CATS_SECTION} » sans citation résolvable")
    # refs cassées explicites partout (une réf présente mais non résolue = erreur)
    for i, line in enumerate(lines):
        for r in ONE_REF.finditer(line):
            if not ref_resolves(r.group("kind"), r.group("body"), root, reports):
                errors.append(f"L{i + 1}: réf non résolue [{r.group('kind')}:{r.group('body')}]")

    if len(lines) > SIZE_MAX:
        errors.append(f"{len(lines)} lignes > {SIZE_MAX} (refus → éclater le thème)")
    return errors


# --- CLI ------------------------------------------------------------------

def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(prog="check.py", description=__doc__)
    parser.add_argument("mode", choices=["fragment", "consolide"])
    parser.add_argument("path")
    parser.add_argument("--repo-root", help="racine du dépôt (défaut : dérivée du script)")
    args = parser.parse_args(argv)

    root = _store.resolve_root(args.repo_root)
    path = Path(args.path)
    if not path.is_absolute():
        path = root / path
    if not path.exists():
        print(f"error: introuvable: {path}", file=sys.stderr)
        return 1

    errors = (lint_fragment if args.mode == "fragment" else lint_consolide)(path, root)
    if errors:
        print(f"{args.mode} {path.name}: {len(errors)} violation(s)", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"{args.mode} {path.name}: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
