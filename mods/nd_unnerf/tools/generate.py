#!/usr/bin/env python3
"""National Destinies with its 1.4.0 cuts softened to 30 %.

    python3 mods/nd_unnerf/tools/generate.py

ND 1.4.0 cut almost every country bonus by one multiplier per modifier —
production ×0.5 in 286 places of 288, food ×0.5 in all 177, population growth
×0.12 — while fixing bugs and porting to game 1.4 in the same release. The
owner's ruling (2026-10-14): keep the fixes, the buffs and the cheaper upkeep;
of each cut keep 30 %. So a value that went from `before` to `after` is written
as `before + 0.3 × (after − before)`: 0.05 → 0.025 becomes 0.0325.

`baseline.tsv` (from `baseline.py`) names every cut. This tool takes each
object holding one from the *current* ND text and writes it whole as
`REPLACE:`, with only those numbers changed — so whatever else the author
changes later arrives with a rebuild. A value the author has moved again since
the baseline is left as he wrote it and named on stderr; so is an object he
removed.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
REPO = MOD.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

import refs  # noqa: E402
import script  # noqa: E402

KEEP = 0.3  # share of each cut that stays
NAME = "zz_bag_nd_unnerf.txt"
WHOLE = {"global_max_bureaucracy_slots", "diplomatic_capacity"}


def softened(key: str, before: float, after: float) -> float:
    value = before + KEEP * (after - before)
    if key in WHOLE and before.is_integer() and after.is_integer():
        value = float(round(value))
    return value


def baseline() -> dict:
    """{(category, object): [(path, before, after)]}."""
    cuts = defaultdict(list)
    for line in (MOD / "baseline.tsv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        cat, name, path, before, after = line.split("\t")
        cuts[(cat, name)].append((script.path_parse(path), float(before), float(after)))
    return cuts


def current(nd: Path) -> dict:
    """{(category, object): (part, text, key_start, open, close)}, last one wins."""
    found = {}
    for part in ("in_game", "main_menu"):
        for path in sorted((nd / part / "common").rglob("*.txt")):
            cat = path.relative_to(nd / part / "common").parts[0]
            text = path.read_text(encoding="utf-8-sig")
            for key, key_start, start, end in script.objects(text):
                found[(cat, key.split(":")[-1])] = (part, text, key_start, start, end)
    return found


def build() -> tuple[dict, list[str], int]:
    nd = refs.known("national_destinies")
    cuts, have = baseline(), current(nd)
    files: dict = defaultdict(list)
    remarks, written = [], 0
    for (cat, name), rows in sorted(cuts.items()):
        if (cat, name) not in have:
            remarks.append(f"{cat}/{name}: no longer in ND, skipped")
            continue
        part, text, _, start, end = have[(cat, name)]
        values = script.leaves(text, start, end)
        edits = []
        for path, before, after in rows:
            got = values.get(path)
            if got is None or abs(got[0] - after) > 1e-9:
                now = "gone" if got is None else script.number(got[0])
                remarks.append(f"{cat}/{name} {script.path_text(path)}: "
                               f"ND now {now}, baseline {script.number(after)}; left as ND has it")
                continue
            edits.append((got[2], got[3], script.number(softened(path[-1][0], before, after))))
        if not edits:
            continue
        body = text[start:end]
        for vs, ve, new in sorted(edits, reverse=True):
            body = body[:vs - start] + new + body[ve - start:]
        files[(part, cat)].append(f"REPLACE:{name} = {body}\n")
        written += len(edits)
    out = {}
    for (part, cat), blocks in files.items():
        head = (f"# Written by mods/nd_unnerf/tools/generate.py from National Destinies'\n"
                f"# own {cat}: each 1.4.0 cut kept at {int(KEEP * 100)} %. Do not edit.\n\n")
        out[MOD / part / "common" / cat / NAME] = head + "\n".join(blocks)
    return out, remarks, written


def main() -> int:
    files, remarks, written = build()
    for part in ("in_game", "main_menu"):
        root = MOD / part
        for old in root.rglob("*.txt") if root.exists() else []:
            if old not in files:
                old.unlink()
    changed = 0
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = "﻿" + text
        if not path.exists() or path.read_text(encoding="utf-8") != data:
            path.write_text(data, encoding="utf-8", newline="\n")
            changed += 1
    for remark in remarks:
        print(f"nd_unnerf: {remark}", file=sys.stderr)
    objects = sum(t.count("\nREPLACE:") + t.startswith("REPLACE:") for t in files.values())
    print(f"nd_unnerf: {written} values in {objects} objects, {len(files)} files, {changed} rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
