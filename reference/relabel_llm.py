#!/usr/bin/env python3
"""Aligneur LLM des locuteurs (compagnon de relabel_speakers.py).

L'algo Jaccard de relabel_speakers.py dérive sur le cross-talk. Mesure faite : les
deux transcripts d'un fichier tiennent en contexte (27-43 k tokens) → un agent aligne
mieux. Ce module fournit les deux bouts non-LLM du montage :

  dump  : sort les tours MacWhisper numérotés (idx, timestamp, Speaker N, texte) +
          le transcript Teams (noms vrais, texte brouillon). L'agent lit ces deux
          fichiers et rend un mapping JSON {idx: {name, confidence, multi}}.
  apply : relit le .txt via parse_macwhisper(), réécrit LES EN-TÊTES SEULEMENT par
          idx selon le mapping → corps garanti intact (0 ligne de texte touchée).

Le *quoi* (texte) est identique quoi qu'on fasse ; seul le *qui* (en-tête) change.

Usage:
  1-sources/outils/relabel_llm.py dump  "<chemin.txt>" <outdir>     # -> outdir/{mw.txt,teams.txt}
  1-sources/outils/relabel_llm.py apply "<chemin.txt>" <mapping.json>   # réécrit le .txt en place
"""
import sys, os, json, re
from relabel_speakers import parse_macwhisper, parse_teams

def sec_to_hms(s):
    h, s = divmod(int(s), 3600)
    m, s = divmod(s, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

def cmd_dump(txt, outdir):
    os.makedirs(outdir, exist_ok=True)
    _, mw = parse_macwhisper(txt)
    docx = txt.replace('.txt', '.teams-auto.docx')
    tx = parse_teams(docx)
    if not mw:
        sys.exit(f"!! aucun tour MacWhisper parsé dans {txt}")

    # MW : un bloc numéroté par tour. idx = clé du mapping attendu en retour.
    mw_lines = [
        "# Tours MacWhisper (texte source-of-truth, locuteurs anonymes à ré-attribuer)",
        f"# {len(mw)} tours. Rends un mapping JSON {{idx: {{name, confidence, multi}}}} couvrant CHAQUE idx.",
        "",
    ]
    for i, (spk, sec, text, _) in enumerate(mw):
        mw_lines.append(f"[{i}] {sec_to_hms(sec)}  (orig: Speaker {spk})")
        mw_lines.append(text)
        mw_lines.append("")
    mw_path = os.path.join(outdir, 'mw.txt')
    open(mw_path, 'w', encoding='utf-8').write('\n'.join(mw_lines))

    # Teams : noms vrais mais texte lexicalement pourri. Source des NOMS uniquement.
    tm_lines = [
        "# Transcript Teams (noms vrais, texte brouillon — source des NOMS de locuteurs UNIQUEMENT)",
        f"# {len(tx)} tours.",
        "",
    ]
    for name, sec, text in tx:
        tm_lines.append(f"{sec_to_hms(sec)}  {name}")
        tm_lines.append(text)
        tm_lines.append("")
    tm_path = os.path.join(outdir, 'teams.txt')
    open(tm_path, 'w', encoding='utf-8').write('\n'.join(tm_lines))

    print(f"  ✓ {mw_path}  ({len(mw)} tours MW)")
    print(f"  ✓ {tm_path}  ({len(tx)} tours Teams)")

def cmd_apply(txt, mapping_path):
    lines, mw = parse_macwhisper(txt)
    mapping = json.load(open(mapping_path, encoding='utf-8'))
    # clés JSON = str ; on indexe par int
    mapping = {int(k): v for k, v in mapping.items()}

    # GARDE anti-footgun : parse_macwhisper ne reconnaît que les en-têtes 'Speaker N'.
    # Appliqué par erreur à un .txt DÉJÀ relabellisé (en-têtes = noms), il n'isole plus
    # qu'une poignée de tours et écraserait tout avec un mapping décalé. Le dump couvre
    # CHAQUE tour → un mismatch de cardinalité = mauvais fichier d'entrée. On refuse.
    if len(mw) != len(mapping):
        sys.exit(f"!! mismatch tours ({len(mw)}) vs mapping ({len(mapping)}). "
                 f"Applique sur le BRUT (Speaker N), pas sur un .txt déjà nommé.")

    out = list(lines)
    sub = re.compile(r'^Speaker (\d+)')
    named = multi = kept = 0
    for i, (spk, sec, text, hdr_idx) in enumerate(mw):
        m = mapping.get(i)
        if not m:
            kept += 1; continue
        # multi : bloc où MacWhisper a fusionné 2+ voix. Champ = "A/B" (noms séparés /).
        mu = m.get('multi')
        if mu:
            out[hdr_idx] = sub.sub('[multi: ' + str(mu) + ']', lines[hdr_idx], count=1); multi += 1
            continue
        name = str(m.get('name', '')).strip()
        if not name or name.startswith('Speaker'):
            kept += 1; continue  # indécidable → on laisse l'en-tête Speaker N d'origine
        out[hdr_idx] = sub.sub(name, lines[hdr_idx], count=1); named += 1

    open(txt, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print(f"  ✓ réécrit {txt}")
    print(f"    {named} nommés, {multi} [multi], {kept} laissés en 'Speaker N'  (sur {len(mw)} tours)")

def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cmd = sys.argv[1]
    if cmd == 'dump':
        cmd_dump(sys.argv[2], sys.argv[3])
    elif cmd == 'apply':
        cmd_apply(sys.argv[2], sys.argv[3])
    else:
        sys.exit(f"commande inconnue: {cmd}")

if __name__ == '__main__':
    main()
