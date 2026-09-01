#!/usr/bin/env python3
"""Annote les titres de slides avec leur locator NN#MM, et le résout.

Usage :
  slides.py annotate     # (ré)écrit le locator dans chaque titre de *.slides.md
  slides.py              # liste toutes les slides : locator  titre
  slides.py 00           # une section entière
  slides.py 00#44 07#12  # un ou plusieurs locators précis

Annotation : dans la parenthèse ITALIQUE finale du titre, jamais rendue à
l'écran (build.py strippe la dernière parenthèse). `## Titre *(7.1)*` →
`## Titre *(7.1 · 07#03)*` ; sinon ajout → `## Titre *(07#03)*`.
Une parenthèse de sigle `(CVP)` fait partie du titre : on n'y touche pas,
le locator s'ajoute après → `## Titre (CVP) *(07#03)*`.
Idempotent : relancer `annotate` renumérote après ajout/retrait de slides.

Numérotation = celle des maps d'audit (4-contenu/audit-slides/*.map.md) :
une slide = un bloc séparé par `---`, titre = son premier `## `.
Un bloc SANS titre (carte encart pleine page) est une slide comme une autre :
il consomme un numéro (= ordre des pages rendues) et se résout en
`(sans titre) <première ligne>` ; seul un bloc vide ne compte pas.
Préfixe = numéro du fichier sans tirets (01-02-… → 0102).
"""
import re
import sys
from pathlib import Path

CONTENU = Path(__file__).resolve().parent.parent


def blocks_of(path: Path):
    """Rend [(idx ligne du titre | None, 1re ligne de contenu | None)] par bloc `---`."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks = []
    for i, line in enumerate(lines):
        if line.strip() == "---":
            blocks.append([None, None])
        elif blocks and line.strip():
            if line.startswith("## ") and blocks[-1][0] is None:
                blocks[-1][0] = i
            elif blocks[-1][1] is None and not line.startswith("<!--"):
                blocks[-1][1] = line.strip()
    return lines, blocks


def slides_of(path: Path):
    """Rend la liste ordonnée des slides (1 entrée par bloc non vide)."""
    lines, blocks = blocks_of(path)
    out = []
    for title_idx, first in blocks:
        if title_idx is not None:
            out.append(lines[title_idx][3:].strip())
        elif first is not None:
            out.append(f"(sans titre) {first[:70]}")
    return out


def sections():
    """{prefixe sans tirets: (path, [titres])} pour chaque *.slides.md."""
    out = {}
    for path in sorted(CONTENU.glob("*.slides.md")):
        m = re.match(r"([0-9][0-9-]*[0-9]|[0-9]+)", path.name)
        if m:
            out[m.group(1).replace("-", "")] = (path, slides_of(path))
    return out


# marqueur déjà posé : `· NN#MM` dans une parenthèse, ou `*(NN#MM)*` seul
MARK_IN_PAREN = re.compile(r"\s*·\s*\d{2,4}#\d+(?=\)\*?\s*$)")
MARK_ALONE = re.compile(r"\s*\*?\(\d{2,4}#\d+\)\*?\s*$")
# seule la parenthèse ITALIQUE `*(…)*` est réutilisable ; une parenthèse de
# sigle comme `(CVP)` fait partie du titre affiché, on n'y insère jamais.
TRAILING_PAREN = re.compile(r"(\*\()([^)]*)(\)\*)\s*$")


def annotate_title(line, locator):
    """Insère/rafraîchit le locator dans la parenthèse finale du titre."""
    line = MARK_IN_PAREN.sub("", line)
    line = MARK_ALONE.sub("", line).rstrip()
    m = TRAILING_PAREN.search(line)
    if m:
        return f"{line[:m.start()]}{m.group(1)}{m.group(2)} · {locator}{m.group(3)}"
    return f"{line} *({locator})*"


def annotate():
    for prefix, (path, _) in sections().items():
        lines, blocks = blocks_of(path)
        num = sans_titre = 0
        for title_idx, first in blocks:
            if title_idx is None and first is None:
                continue  # bloc vide : pas une slide
            num += 1
            if title_idx is not None:
                lines[title_idx] = annotate_title(lines[title_idx], f"{prefix}#{num:02d}")
            else:
                sans_titre += 1  # consomme le numéro, rien à écrire
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        extra = f" (dont {sans_titre} sans titre, non annotées)" if sans_titre else ""
        print(f"{path.name} : {num} slides{extra}")
    return 0


def main(args):
    if args and args[0] == "annotate":
        return annotate()
    secs = sections()
    if not args:
        args = sorted(secs)
    status = 0
    for arg in args:
        prefix, _, num = arg.partition("#")
        if prefix not in secs:
            print(f"?? section inconnue : {arg}", file=sys.stderr)
            status = 1
            continue
        path, titles = secs[prefix]
        if num:
            i = int(num)
            if 1 <= i <= len(titles):
                print(f"{prefix}#{i:02d}  {titles[i - 1]}")
            else:
                print(f"?? {arg} hors bornes ({path.name} : {len(titles)} slides)", file=sys.stderr)
                status = 1
        else:
            print(f"— {path.name} ({len(titles)} slides)")
            for i, title in enumerate(titles, 1):
                print(f"{prefix}#{i:02d}  {title}")
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
