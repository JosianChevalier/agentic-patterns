#!/usr/bin/env python3
"""Query the pattern catalogue via patterns/*/index.md frontmatters.

Usage:
  ./piocher.py               list all patterns, grouped by family
  ./piocher.py <term>...     filter: every term must match (substring,
                             case-insensitive) slug, tags, description or body
  ./piocher.py --tags        list the controlled tag vocabulary (patterns/TAGS.md)
  ./piocher.py --write       regenerate the CATALOGUE region of INDEX.md

Also the catalogue linter: any missing/unreadable frontmatter fails loudly.
Stdlib only.
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATTERNS_DIR = ROOT / "patterns"
TAGS_FILE = PATTERNS_DIR / "TAGS.md"
INDEX_FILE = ROOT / "INDEX.md"

FAMILY_ORDER = [
    "pipeline-core",
    "orchestration",
    "harness-permissions",
    "kb-conventions",
    "agent-authoring",
]

BEGIN_MARKER = "<!-- CATALOGUE:BEGIN -->"
END_MARKER = "<!-- CATALOGUE:END -->"


def die(msg):
    print(f"piocher.py: error: {msg}", file=sys.stderr)
    sys.exit(1)


def parse_frontmatter(path):
    """Parse the simple `key: value` frontmatter between the two `---` lines."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        die(f"{path}: unreadable ({e})")
    if not lines or lines[0].strip() != "---":
        die(f"{path}: missing frontmatter (file must open with `---`)")
    closing = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            closing = i
            break
    if closing is None:
        die(f"{path}: unterminated frontmatter (no closing `---`)")
    fm = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        if ":" not in line:
            die(f"{path}: unparseable frontmatter line: {line!r}")
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    body = "\n".join(lines[closing + 1:])
    return fm, body


def load_patterns():
    if not PATTERNS_DIR.is_dir():
        die(f"{PATTERNS_DIR}: not a directory")
    patterns = []
    for entry in sorted(PATTERNS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        index = entry / "index.md"
        if not index.is_file():
            die(f"{entry}: no index.md")
        fm, body = parse_frontmatter(index)
        for field in ("description", "tags", "family"):
            if not fm.get(field):
                die(f"{index}: missing frontmatter field `{field}`")
        description = fm["description"].strip('"').replace('\\"', '"')
        m = re.fullmatch(r"\[(.+)\]", fm["tags"])
        if not m:
            die(f"{index}: `tags` must be a [a, b] list, got {fm['tags']!r}")
        tags = [t.strip() for t in m.group(1).split(",") if t.strip()]
        if not tags:
            die(f"{index}: empty `tags` list")
        family = fm["family"]
        if family not in FAMILY_ORDER:
            die(f"{index}: unknown family {family!r} (expected one of {', '.join(FAMILY_ORDER)})")
        patterns.append({
            "slug": entry.name,
            "description": description,
            "tags": tags,
            "family": family,
            "body": body,
        })
    if not patterns:
        die(f"no patterns found under {PATTERNS_DIR}")
    return patterns


def matches(pattern, terms):
    haystack = "\n".join([
        pattern["slug"],
        " ".join(pattern["tags"]),
        pattern["description"],
        pattern["body"],
    ]).lower()
    return all(term.lower() in haystack for term in terms)


def cmd_list(patterns, terms):
    if terms:
        patterns = [p for p in patterns if matches(p, terms)]
        if not patterns:
            print(f"no pattern matches: {' '.join(terms)}", file=sys.stderr)
            sys.exit(1)
    width = max(len(p["slug"]) for p in patterns)
    for family in FAMILY_ORDER:
        members = [p for p in patterns if p["family"] == family]
        if not members:
            continue
        print(f"== {family} ==")
        for p in members:
            tags = ", ".join(p["tags"])
            print(f"{p['slug']:<{width}}  {p['description']}  [{tags}]")
        print()


def cmd_tags():
    if not TAGS_FILE.is_file():
        die(f"{TAGS_FILE}: not found")
    rows = []
    for line in TAGS_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|\s*$", line)
        if m:
            rows.append((m.group(1), m.group(2)))
    if not rows:
        die(f"{TAGS_FILE}: no tag rows found (expected `| `tag` | definition |` lines)")
    width = max(len(tag) for tag, _ in rows)
    for tag, definition in rows:
        print(f"{tag:<{width}}  {definition}")


def generated_block(patterns):
    n_families = len({p["family"] for p in patterns})
    lines = [f"{len(patterns)} patterns in {n_families} families.", ""]
    for family in FAMILY_ORDER:
        members = [p for p in patterns if p["family"] == family]
        if not members:
            continue
        lines.append(f"## {family}")
        lines.append("")
        for p in members:
            tags = ", ".join(f"`{t}`" for t in p["tags"])
            lines.append(
                f"- [{p['slug']}](patterns/{p['slug']}/index.md) — {p['description']} — {tags}"
            )
        lines.append("")
    return "\n".join(lines).rstrip("\n")


def cmd_write(patterns):
    if not INDEX_FILE.is_file():
        die(f"{INDEX_FILE}: not found")
    text = INDEX_FILE.read_text(encoding="utf-8")
    for marker in (BEGIN_MARKER, END_MARKER):
        count = text.count(marker)
        if count != 1:
            die(f"{INDEX_FILE}: marker {marker!r} found {count} time(s), expected exactly 1")
    head, _, rest = text.partition(BEGIN_MARKER)
    _, _, tail = rest.partition(END_MARKER)
    new_text = f"{head}{BEGIN_MARKER}\n\n{generated_block(patterns)}\n\n{END_MARKER}{tail}"
    if new_text != text:
        INDEX_FILE.write_text(new_text, encoding="utf-8")
    print(f"{INDEX_FILE.name}: catalogue region up to date ({len(patterns)} patterns)")


def main():
    parser = argparse.ArgumentParser(
        description="Query the agentic-patterns catalogue.", add_help=True
    )
    parser.add_argument("terms", nargs="*", help="filter terms (all must match)")
    parser.add_argument("--tags", action="store_true", help="list the controlled tag vocabulary")
    parser.add_argument("--write", action="store_true", help="regenerate INDEX.md's CATALOGUE region")
    args = parser.parse_args()

    if args.tags:
        cmd_tags()
        return
    patterns = load_patterns()
    if args.write:
        cmd_write(patterns)
        return
    cmd_list(patterns, args.terms)


if __name__ == "__main__":
    main()
