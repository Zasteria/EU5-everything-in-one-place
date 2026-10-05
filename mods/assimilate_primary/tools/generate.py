#!/usr/bin/env python3
"""Builds `assimilate_primary`: cabinet automation assimilates a province into
the primary culture unless an accepted culture already leads it there.

The beta of 01.10 opened accepted cultures to `promote_culture` and dropped the
1.3 penalty `-1000 "Wrong culture"` from its `ai_will_do`. What is left scores
`1 - share of the target culture in the province`, so of two allowed cultures
the one with the *smaller* share wins: Torda, 05.10, Moldovan 3 % chosen over
the primary Wallachian 15 % (`docs/research/vanilla.md`).

His rule, 05.10: an accepted culture is a fair target where it already leads
the primary one by about 30 points; anywhere else, assimilate into the primary.
The game's own file is copied whole and the penalty appended to `ai_will_do`,
after its `multiply`, so the factor does not shrink it.

    python3 mods/assimilate_primary/tools/generate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/assimilate_primary"
SOURCE = "in_game/common/cabinet_actions/promote_culture.txt"
OUT = MOD / SOURCE
LEAD = 0.3

HEAD = """# assimilate_primary: the game's promote_culture.txt, copied whole, with one
# penalty at the end of ai_will_do. Rebuilt from the game by tools/generate.py.
"""

PENALTY = """
\t\t# assimilate_primary: an accepted culture only where it already leads the
\t\t# primary culture in this province by %d points (the 1.3 rule was -1000 for
\t\t# any culture but the primary; the beta dropped it).
\t\tif = {
\t\t\tlimit = {
\t\t\t\tscope:target != scope:actor.culture
\t\t\t\t"scope:target_1.culture_percentage(scope:target)" < {
\t\t\t\t\tvalue = "scope:target_1.culture_percentage(scope:actor.culture)"
\t\t\t\t\tadd = %s
\t\t\t\t}
\t\t\t}
\t\t\tadd = -1000
\t\t}
""" % (round(LEAD * 100), LEAD)


def block_end(text: str, start: int) -> int:
    """Index of the brace closing the block whose `{` is the first after start."""
    depth, i = 0, text.index("{", start)
    while True:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1


def main() -> None:
    text = (refs.GAME / SOURCE).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if "Wrong culture" in text:
        raise SystemExit("promote_culture: the game has its own culture penalty again — "
                         "this mod may no longer be needed; read the file before rebuilding")
    start = text.find("\tai_will_do = {")
    if start < 0:
        raise SystemExit("promote_culture: no ai_will_do in the game's file")
    end = block_end(text, start)
    out = HEAD + text[:end].rstrip("\t") + PENALTY.lstrip("\n") + "\t" + text[end:]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    old = OUT.read_text(encoding="utf-8-sig") if OUT.exists() else None
    if old != out:
        OUT.write_text(out, encoding="utf-8-sig")
        print(f"{OUT.relative_to(refs.REPO)}: rebuilt")
    else:
        print(f"{OUT.relative_to(refs.REPO)}: unchanged")


if __name__ == "__main__":
    main()
