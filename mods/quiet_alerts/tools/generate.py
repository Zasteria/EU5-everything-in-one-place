#!/usr/bin/env python3
"""Builds `quiet_alerts`: red and orange alert banners play the yellow sound.

An alert banner's appear sound is chosen by the alert's `priority` in the
game's `NAlertAudio` defines; nothing per alert. 0.1.0 wrote a block holding
only the two emptied keys, and **every** alert went silent (his run 10-02,
the green alliance offers included): the block is taken whole, so it is
copied here from the game's own defines. 0.1.1 emptied the two keys; his
choice 10-02: give red and orange the yellow banner's sound instead.

    python3 mods/quiet_alerts/tools/generate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/quiet_alerts"
DEFINES = "loading_screen/common/defines/00_defines.txt"
OUT = MOD / "loading_screen/common/defines/quiet_alerts_defines.txt"
SOFT = ("ALERT_APPEAR_RED", "ALERT_APPEAR_ORANGE")
SOUND = "UI_alert_appear_yellow"

HEAD = """# quiet_alerts: the game's whole NAlertAudio block (a partial one silenced every
# alert, 10-02), with red and orange alerts playing the yellow alert's sound —
# disease and famine are red, a location losing population is orange.
# Rebuilt from the game by tools/generate.py.
"""


def main() -> int:
    text = (refs.GAME / DEFINES).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    block = re.search(r"^NAlertAudio = \{\n.*?^\}", text, re.M | re.S)
    if not block:
        raise SystemExit("no NAlertAudio in the game's defines")
    body = block.group(0)
    if SOUND not in body:
        raise SystemExit(f"{SOUND}: the game no longer names it")
    for key in SOFT:
        body, n = re.subn(r'^(\t%s = )"[^"]*"' % key, r'\1"%s"' % SOUND, body, flags=re.M)
        if n != 1:
            raise SystemExit(f"{key}: {n} lines in NAlertAudio")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("﻿" + HEAD + body + "\n", encoding="utf-8")
    print("quiet_alerts: NAlertAudio copied whole, %s on %s" % (SOUND, ", ".join(SOFT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
