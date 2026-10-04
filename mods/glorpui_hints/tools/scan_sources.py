#!/usr/bin/env python3
"""Scan EU5 game files for everything that pushes a societal value.

Every push in the game is a `monthly_towards_<axis> = <value>` modifier - 34 of
them, one per direction, all declared with `is_societal_value_change = yes` in
common/modifier_type_definitions. This walks the game script with a brace
matcher and reports, for each occurrence, which top-level object grants it and
through which block.

Usage:
    python3 mods/glorpui_hints/tools/scan_sources.py <game-files-root> [--json out.json]
"""

import argparse
import collections
import json
import os
import re
import sys

MODIFIER_RE = re.compile(r'\bmonthly_towards_([a-z_]+)\s*=\s*(\S+)')
# Paradox script tokens: a key is followed by '=' and then a value or a block.
TOKEN_RE = re.compile(r'"[^"]*"|[^\s{}=]+|[{}=]')

# `societal_value_monthly_move` is the game's standard step, defined in
# common/script_values/default_values.txt.
NAMED_VALUES = {"societal_value_monthly_move": 0.1}


def strip_comments(text):
    out = []
    for line in text.split("\n"):
        quoted = False
        for i, ch in enumerate(line):
            if ch == '"':
                quoted = not quoted
            elif ch == "#" and not quoted:
                line = line[:i]
                break
        out.append(line)
    return "\n".join(out)


def walk(text):
    """Yield (path, key, value) for every `key = value` assignment.

    `path` is the tuple of enclosing block names, so a modifier inside
    `oprichnina = { country_modifier = { ... } }` comes back with
    path == ("oprichnina", "country_modifier").
    """
    tokens = TOKEN_RE.findall(strip_comments(text))
    path = []
    pending = None  # key awaiting its value
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "=":
            i += 1
            continue
        if token == "{":
            # Anonymous block, or the block belonging to `pending`.
            path.append(pending if pending else "")
            pending = None
            i += 1
            continue
        if token == "}":
            if path:
                path.pop()
            pending = None
            i += 1
            continue
        # A bare token: either a key (followed by '=') or a list element.
        if i + 1 < len(tokens) and tokens[i + 1] == "=":
            if i + 2 < len(tokens) and tokens[i + 2] != "{":
                yield tuple(path), token, tokens[i + 2]
                i += 3
                continue
            pending = token
            i += 2
            continue
        i += 1


def numeric(value):
    if value in NAMED_VALUES:
        return NAMED_VALUES[value]
    try:
        return float(value)
    except ValueError:
        return None


def scan(root):
    """Every `monthly_towards_*` under root, with the object and block it sits in."""
    findings = []
    for dirpath, _, filenames in os.walk(root):
        for filename in sorted(filenames):
            if not filename.endswith(".txt"):
                continue
            full = os.path.join(dirpath, filename)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, encoding="utf-8-sig", errors="replace") as handle:
                text = handle.read()
            if "monthly_towards_" not in text:
                continue
            for path, key, value in walk(text):
                match = MODIFIER_RE.match("%s = %s" % (key, value))
                if not match:
                    continue
                findings.append({
                    "file": rel,
                    "source_type": rel.split("/")[2] if rel.count("/") > 2 else rel,
                    "object": path[0] if path else "",
                    "path": list(path),
                    "axis": match.group(1),
                    "raw_value": value,
                    "value": numeric(value),
                })
    return findings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("--json")
    args = parser.parse_args()

    findings = scan(args.root)
    by_type = collections.Counter(f["source_type"] for f in findings)
    print("%d pushes across %d source types\n" % (len(findings), len(by_type)))
    for source_type, count in by_type.most_common():
        objects = len({f["object"] for f in findings
                       if f["source_type"] == source_type})
        print("  %-45s %4d pushes  %4d objects" % (source_type, count, objects))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(findings, handle, ensure_ascii=False, indent=1)
        print("\nwrote %s" % args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
