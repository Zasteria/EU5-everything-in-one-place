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

0.1.0 put the 1.3 penalty back into `ai_will_do`, and in his 40-minute run
(05.10) no advisor assimilated anything at all; the logs hold no error for
the file. Why is not measured. 0.2.0 scores nothing negative: the rule moves
into the province's `enabled`, the same place the game itself narrows the
choice for the AI, and only while cabinet actions are automated, so a choice
made by hand stays free.

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
# more condition in the province's `enabled`. Rebuilt from the game by
# tools/generate.py.
"""

RULE = """\t\t\t# assimilate_primary: while the cabinet is automated, an accepted culture
\t\t\t# only where it already leads the primary culture in this province by %d
\t\t\t# points (the 1.3 rule was -1000 for any culture but the primary).
\t\t\ttrigger_if = {
\t\t\t\tlimit = {
\t\t\t\t\tscope:actor = {
\t\t\t\t\t\tOR = {
\t\t\t\t\t\t\tis_system_automated = cabinetactions
\t\t\t\t\t\t\tis_system_automated = cabinet
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t\tNOT = { scope:target = scope:actor.culture }
\t\t\t\t}
\t\t\t\t"culture_percentage(scope:target)" >= {
\t\t\t\t\tvalue = "culture_percentage(scope:actor.culture)"
\t\t\t\t\tadd = %s
\t\t\t\t}
\t\t\t}
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
    province = text.find("looking_for_a = province")
    if province < 0:
        raise SystemExit("promote_culture: no province selection in the game's file")
    trigger_end = block_end(text, text.rindex("select_trigger = {", 0, province))
    enabled = text.find("\t\tenabled = {", province, trigger_end)
    if enabled < 0:
        raise SystemExit("promote_culture: the province selection has no `enabled`")
    end = block_end(text, enabled)
    out = HEAD + text[:end].rstrip("\t") + RULE + "\t\t" + text[end:]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    old = OUT.read_text(encoding="utf-8-sig") if OUT.exists() else None
    if old != out:
        OUT.write_text(out, encoding="utf-8-sig")
        print(f"{OUT.relative_to(refs.REPO)}: rebuilt")
    else:
        print(f"{OUT.relative_to(refs.REPO)}: unchanged")


if __name__ == "__main__":
    main()
