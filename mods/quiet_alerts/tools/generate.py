#!/usr/bin/env python3
"""Builds `quiet_alerts`: red and orange alert banners play the yellow sound,
behind a checkbox in the CMF menu.

An alert banner's appear sound is chosen by the alert's `priority` in the
game's `NAlertAudio` defines; nothing per alert. 0.1.0 wrote a block holding
only the two emptied keys, and **every** alert went silent (his run 10-02,
the green alliance offers included): the block is taken whole, so it is
copied here from the game's own defines. 0.1.1 emptied the two keys; his
choice 10-02: give red and orange the yellow banner's sound instead.

0.3.0, his ask 10-02: a checkbox to turn that sound off and on. Defines are
read once at load, so the switch cannot live there: red and orange go silent
in the defines (0.1.1 proved "" is silence), and the banner itself plays the
yellow sound. `type alert_banner` is the game's own, copied whole (shared with
assimilate_primary, tools/alert_banner.py), plus one hidden child: born hidden (`visible_at_creation = no`, the CM pattern), it
turns visible when the banner is red or orange and the CMF setting is on, and
its `_show` plays the sound.

    python3 mods/quiet_alerts/tools/generate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import alert_banner  # noqa: E402
import refs  # noqa: E402

MOD = refs.REPO / "mods/quiet_alerts"
DEFINES = "loading_screen/common/defines/00_defines.txt"
OUT = MOD / "loading_screen/common/defines/quiet_alerts_defines.txt"
ALERTS = "in_game/gui/alertmanager.gui"
OLD_BANNER = MOD / "in_game/gui/quiet_alerts_banner.gui"
SOFT = ("ALERT_APPEAR_RED", "ALERT_APPEAR_ORANGE")
SOUND = "UI_alert_appear_yellow"
SETTING = "bag_qal__red_orange_sound"

HEAD = """# quiet_alerts: the game's whole NAlertAudio block (a partial one silenced every
# alert, 10-02), with red and orange alerts silent here — disease and famine are
# red, a location losing population is orange. Their sound is played by the
# banner instead (bag_alert_banner.gui), behind the CMF checkbox.
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
        body, n = re.subn(r'^(\t%s = )"[^"]*"' % key, r'\1""', body, flags=re.M)
        if n != 1:
            raise SystemExit(f"{key}: {n} lines in NAlertAudio")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\ufeff" + HEAD + body + "\n", encoding="utf-8")
    # The banner type is shared with assimilate_primary: tools/alert_banner.py.
    banner = MOD / alert_banner.PATH
    banner.parent.mkdir(parents=True, exist_ok=True)
    banner.write_text("\ufeff" + alert_banner.build(refs.GAME), encoding="utf-8")
    if OLD_BANNER.exists():
        OLD_BANNER.unlink()
    print("quiet_alerts: %s silent in defines, %s from the banner behind %s"
          % (", ".join(SOFT), SOUND, SETTING))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
