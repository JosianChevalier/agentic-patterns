#!/usr/bin/env python3
"""Index `quand_piocher` des fiches thématiques couche 2 (axe CATS).

Point d'entrée de découverte avant tout travail couche 3+ ou réponse à Josian :
liste chaque fiche `2.2-content/*.md` avec sa phrase `quand_piocher`, pour repérer
la/les fiche(s) à charger.

Exclues de l'index : les fiches `formation-*` (axe formation) — elles ne se piochent
pas à la carte, elles se chargent en bloc, l'index ne couvre donc que l'axe CATS.

Usage :
  piocher.py        # toutes les fiches CATS : <nom>  <phrase>
  piocher.py archi  # filtre sur les fiches dont le nom contient "archi"
"""
import re
import sys
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent / "2.2-content"
FM = re.compile(r'^quand_piocher:\s*"?(.*?)"?\s*$')


def fiches(needle: str | None):
    for path in sorted(CONTENT.glob("*.md")):
        if path.stem.startswith("formation-"):
            continue
        if needle and needle.lower() not in path.stem.lower():
            continue
        phrase = ""
        for line in path.read_text(encoding="utf-8").splitlines()[:10]:
            m = FM.match(line)
            if m:
                phrase = m.group(1)
                break
        yield path.stem, phrase


def main() -> int:
    needle = sys.argv[1] if len(sys.argv) > 1 else None
    rows = list(fiches(needle))
    if not rows:
        print("Aucune fiche.", file=sys.stderr)
        return 1
    width = max(len(name) for name, _ in rows)
    missing = 0
    for name, phrase in rows:
        if not phrase:
            phrase = "⚠️  quand_piocher manquant"
            missing += 1
        print(f"{name.ljust(width)}  {phrase}")
    print(f"\n{len(rows)} fiche(s)" + (f", {missing} sans quand_piocher" if missing else ""),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
