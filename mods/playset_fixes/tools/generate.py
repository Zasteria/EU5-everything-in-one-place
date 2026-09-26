#!/usr/bin/env python3
"""Build the overrides that repair other mods' faults.

    python3 mods/playset_fixes/tools/generate.py

Each repair is a search and replace over the mod's own shipped file, so an
update of that mod is picked up on the next refresh and the fault stays fixed.
A key defined twice wins by mount order: this mod depends on the one it fixes,
so it mounts after it (the same arrangement `nd_ru` runs on).

Cheat Menu Pro writes `#l` 373 times in its Russian text — and in English, so
the author's intent is a format, not a typo. The game has no `l` format and
says so, `pdx_text_formatter.cpp: Unknown formatting tag 'l'`, 2 692 lines in
two seconds of hovering its settings page (2026-09-26). The text around it is
key names — «Ctrl+ЛКМ», «Alt+ПКМ» — so it becomes `#H`, the game's highlight.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MOD.parent.parent / "tools"))
import refs  # noqa: E402

KEY = re.compile(r'^(\s*[A-Za-z0-9_.\-]+:\d*\s+")(.*)("\s*(?:#.*)?)$')
TAG = re.compile(r"#l(?=[ !])")
# Left to the mod as it ships: it also names `$colonize$`, a key nobody defines,
# and `check_script.py` rightly refuses to carry that. One tooltip's `#l`.
SKIP = {"CHEAT_MENU_COMMAND_STUDIES_TEXT_1"}


def main() -> int:
    sources = [m for m in refs.mods() if m.id == "sakuya"]
    if not sources:
        print("     Cheat Menu Pro is not in reference/mods — nothing to repair")
        return 1
    folder = sources[0].path / "main_menu/localization/russian"
    out_dir = MOD / "main_menu/localization/russian"
    total = 0
    for path in sorted(folder.glob("*_l_russian.yml")):
        lines = ["l_russian:"]
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = KEY.match(line)
            if not match or not TAG.search(match.group(2)) or match.group(1).split(":")[0].strip() in SKIP:
                continue
            value, count = TAG.subn("#H", match.group(2))
            total += count
            lines.append(match.group(1) + value + match.group(3))
        target = out_dir / ("zz_playset_fixes_" + path.name.lower())
        if len(lines) == 1:
            target.unlink(missing_ok=True)
            continue
        target.write_text("﻿" + "\n".join(lines) + "\n", encoding="utf-8")
        print("wrote %s: %d keys" % (target.relative_to(MOD.parent.parent), len(lines) - 1))
    if total == 0:
        print("     Cheat Menu Pro no longer writes #l — drop this repair")
        return 1
    print("     %d #l tags replaced" % total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
