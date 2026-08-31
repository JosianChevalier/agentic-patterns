#!/usr/bin/env python3
"""Verify that <slug>/index.md preserves the text of <slug>/.extract.md.

The Extract step writes .extract.md as a pristine copy of index.md. Triage,
Embed and Transcribe must not alter the source text — only ADD lines in two
permitted shapes:

  - Embed insertions    : a single line `![](filename.png)` (path with no `/`,
                          meaning a PNG promoted to the slug root). Blank lines
                          around it are allowed.
  - Transcribe blocks   : a block opened by a line containing
                          `<retranscription>` and closed by a line containing
                          `</retranscription>`. Body lines inside are
                          free-form (lists, tables, ASCII-art, code fences,
                          blank lines…). An unclosed `<retranscription>` is
                          a violation.

Any deletion or modification of an Extract line — or any insertion that does
not match the rules above — fails the check.

Usage:
    check_text_preservation.py [--repo-root <path>] <slug>
        Exit 0 if preserved, 1 otherwise.

If <slug>/.extract.md is missing (typical for slugs extracted before snapshots
existed), re-run `extract.py --snapshot-only <slug>` first to bootstrap it.
"""
import argparse
import difflib
import re
import sys
from pathlib import Path

import _paths

DEFAULT_REPO_ROOT = _paths.find_root()

EMBED_RE = re.compile(r"^!\[[^\]]*\]\(([^)]+)\)\s*$")
OPEN_TAG_RE = re.compile(r"<retranscription>")
CLOSE_TAG_RE = re.compile(r"</retranscription>")


def _is_root_embed(line: str) -> bool:
    """True if `line` is a Markdown image whose target has no path separator.

    Extract-time embeds live under `./_all_pages/...` or `media/...`; an Embed
    agent promotes a PNG to the slug root, so its path is just `filename.png`.
    """
    m = EMBED_RE.match(line)
    if not m:
        return False
    return "/" not in m.group(1)


def _classify_insertion(lines: list[str]) -> tuple[bool, str]:
    """Validate a block of inserted lines. Returns (ok, reason_if_not_ok).

    State machine:
      OUTSIDE      : blank lines and root-embed lines are OK; a line containing
                     `<retranscription>` switches to IN_TRANSCRIPTION.
      IN_TRANSCRIPTION : any line is OK; a line containing `</retranscription>`
                     returns to OUTSIDE. Reaching end-of-insertion while still
                     IN_TRANSCRIPTION is a violation (unclosed block).
    Anything else in OUTSIDE is a rule violation.
    """
    state = "OUTSIDE"
    for i, raw in enumerate(lines):
        line = raw.rstrip("\n")
        if state == "OUTSIDE":
            if line.strip() == "":
                continue
            if _is_root_embed(line):
                continue
            if OPEN_TAG_RE.search(line):
                state = "IN_TRANSCRIPTION"
                if CLOSE_TAG_RE.search(line):
                    state = "OUTSIDE"
                continue
            return False, f"line {i+1} of insertion is neither an embed nor a transcription opener: {line!r}"
        else:  # IN_TRANSCRIPTION
            if CLOSE_TAG_RE.search(line):
                state = "OUTSIDE"
            # else: still inside the transcription block, accept anything.
    if state == "IN_TRANSCRIPTION":
        return False, "unclosed <retranscription> block (no </retranscription>)"
    return True, ""


def check(slug: str, repo_root: Path) -> int:
    extracted = _paths.ressources_dir(repo_root)
    out_dir = extracted / slug
    index = out_dir / "index.md"
    snap = out_dir / ".extract.md"

    if not index.exists():
        print(f"ERROR {slug}: {index.relative_to(repo_root)} not found", file=sys.stderr)
        return 2
    if not snap.exists():
        print(
            f"ERROR {slug}: snapshot {snap.relative_to(repo_root)} missing.\n"
            f"  Run: python3 1-sources/outils/ressources/extract.py --snapshot-only {slug}",
            file=sys.stderr,
        )
        return 2

    extract_lines = snap.read_text().splitlines(keepends=True)
    current_lines = index.read_text().splitlines(keepends=True)

    matcher = difflib.SequenceMatcher(a=extract_lines, b=current_lines, autojunk=False)
    errors: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("delete", "replace"):
            removed = "".join(extract_lines[i1:i2]).rstrip("\n")
            errors.append(
                f"forbidden {tag} at Extract lines {i1+1}-{i2} (Extract content lost or modified):\n"
                f"    {removed!r}"
            )
            if tag == "replace":
                added = "".join(current_lines[j1:j2]).rstrip("\n")
                errors.append(f"  replaced by:\n    {added!r}")
            continue
        # tag == "insert"
        inserted = current_lines[j1:j2]
        ok, reason = _classify_insertion(inserted)
        if not ok:
            block = "".join(inserted).rstrip("\n")
            errors.append(
                f"forbidden insertion after Extract line {i1} (between Extract lines {i1} and {i1+1}):\n"
                f"  {reason}\n"
                f"  block:\n    " + block.replace("\n", "\n    ")
            )

    if errors:
        print(f"FAIL {slug}: text preservation violated", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1

    print(f"OK {slug}: text preserved")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo-root", default=None,
                        help="repo root (default: derived from this script's path)")
    parser.add_argument("slug")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else DEFAULT_REPO_ROOT
    return check(args.slug, repo_root)


if __name__ == "__main__":
    sys.exit(main())
