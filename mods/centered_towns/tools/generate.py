#!/usr/bin/env python3
"""Builds `centered_towns`: Better label placement's town positions under the
file names the game reads on 1.4.

Better label placement (made on 1.2) puts every town, castle and village in the
middle of its location by shipping the game's locator files with new
positions. On 1.4 the game renamed two of them —
`generated_map_object_locators_city.txt` is now `generated_locators_city.txt`,
and `_vfx` likewise (`reference/game/FILES.txt`, 10-04) — so the mod's copies
replace nothing and the towns stay where the game puts them, on the rivers.

This writes the mod's positions under the new names. Only `city` and `vfx`:
the unit-stack and battle files kept their names, and the game's 1.4 copies
are newer than the mod's (two header fields, five lakes gone). Ids the game
no longer has are dropped, so nothing points at a missing location.

0.1.0 changed the `NGameCityLocators` weights instead; his run 10-04 showed no
effect — those weights only serve generation in the map editor, it seems.

    python3 mods/centered_towns/tools/generate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))
import refs  # noqa: E402

MOD = Path(__file__).resolve().parents[1]
OUT = MOD / "in_game/gfx/map/map_objects"
# old name in Better label placement -> the name the game reads on 1.4
RENAMED = {
    "generated_map_object_locators_city.txt": "generated_locators_city.txt",
    "generated_map_object_locators_vfx.txt": "generated_locators_vfx.txt",
}
INSTANCE = re.compile(r"\t\t\{\n\t\t\tid=(\S+)\n.*?\n\t\t\}\n", re.S)


def locations() -> set[str]:
    text = (refs.GAME / "in_game/map_data/location_templates.txt").read_text(encoding="utf-8-sig")
    return set(re.findall(r"^(\w+) = \{", text, re.M))


def main() -> int:
    source = refs.mod("labelplace", "better_label_placement") / "in_game/gfx/map/map_objects"
    known = locations()
    OUT.mkdir(parents=True, exist_ok=True)
    for old, new in RENAMED.items():
        text = (source / old).read_text(encoding="utf-8-sig")
        dropped: list[str] = []

        def keep(match: re.Match) -> str:
            if match.group(1) in known:
                return match.group(0)
            dropped.append(match.group(1))
            return ""

        text, kept = INSTANCE.subn(keep, text)
        (OUT / new).write_text("﻿# Written by mods/centered_towns/tools/generate.py from "
                               "Better label placement's %s.\n" % old + text, encoding="utf-8")
        print("%s: %d positions, dropped %d gone from the game%s"
              % (new, kept - len(dropped), len(dropped),
                 (": " + ", ".join(dropped)) if dropped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
