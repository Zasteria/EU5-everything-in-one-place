#!/usr/bin/env python3
"""The game's `type alert_banner`, copied whole, with the children our mods hang on it.

Two mods need a child on every alert banner: `quiet_alerts` plays the yellow
sound on red and orange ones, `assimilate_primary` wakes its council when the
«devastated locations» one appears. A type has one definition, so both mods ship
this same file under the same path, built here: whichever loads last replaces
the other's copy with an identical one, and a mod installed alone still works
(the other's child asks for a setting or a variable that is then never set).

    import alert_banner
    text = alert_banner.build(refs.GAME)     # the file, for PATH in each mod

Rebuilt by `mods/quiet_alerts/tools/generate.py` and
`mods/assimilate_primary/tools/generate.py`.
"""

from __future__ import annotations

from pathlib import Path

PATH = "in_game/gui/bag_alert_banner.gui"
ALERTS = "in_game/gui/alertmanager.gui"

HEAD = """# The game's `type alert_banner` (alertmanager.gui), copied whole, with two
# children: quiet_alerts' red/orange sound and assimilate_primary's
# devastated-locations watch. Both mods ship this same file; built by
# tools/alert_banner.py, do not edit by hand.

types BagAlertBanner {
"""

# quiet_alerts: born hidden, so a banner that is red or orange when it appears
# still goes hidden -> shown and fires _show (the CM pattern, cm_hidden_window).
# The engine's own sound for these is "" in quiet_alerts' defines.
SOUND_CHILD = """
\t\t# quiet_alerts: born hidden, so a banner that is red or orange when it
\t\t# appears still goes hidden -> shown and fires _show (the CM pattern,
\t\t# cm_hidden_window.gui). The engine's own sound for these is "" in defines.
\t\twidget = {
\t\t\tname = "quiet_alerts_sound"
\t\t\tsize = { 0 0 }
\t\t\tvisible_at_creation = no
\t\t\tvisible = "[And(Or(AlertEntry.GetDescription.IsPriority('red'), AlertEntry.GetDescription.IsPriority('orange')), CMMIsSettingEnabled('bag_qal__red_orange_sound'))]"
\t\t\tstate = {
\t\t\t\tname = _show
\t\t\t\tstart_sound = { soundeffect = "UI_alert_appear_yellow" }
\t\t\t}
\t\t}
"""

# assimilate_primary: lives only on the «devastated locations» banner (its
# title key, common/alert_descriptions) and only while the council automation
# is on. Wakes the emergency as the banner appears, then every second while it
# stays — a province can fall while the alert already shows, and a month is
# 4–8 s of real time (his words 10-12: ten seconds is two months).
DEVASTATION_CHILD = """
\t\t# assimilate_primary: the «devastated locations» banner wakes the council's
\t\t# emergency recovery; nothing on any other banner, nothing with the
\t\t# automation off.
\t\twidget = {
\t\t\tname = "bag_asp_devastation_watch"
\t\t\tsize = { 0 0 }
\t\t\tvisible_at_creation = no
\t\t\tvisible = "[And(EqualTo_string(AlertEntry.GetDescription.GetTitleKey, 'ALERT_HAS_DEVASTATED_LOCATIONS'), GetPlayer.MakeScope.GetVariable('bag_asp_auto_on').IsSet)]"
\t\t\tstate = {
\t\t\t\tname = _show
\t\t\t\tduration = 0.1
\t\t\t\ton_finish = "[GetScriptedGui('bag_asp_devastated_seen').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
\t\t\t\ton_finish = "[GetScriptedGui('bag_asp_devastated').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
\t\t\t\tnext = bag_asp_devastation_again
\t\t\t}
\t\t\tstate = {
\t\t\t\tname = bag_asp_devastation_again
\t\t\t\tduration = 1
\t\t\t\ton_finish = "[GetScriptedGui('bag_asp_devastated').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
\t\t\t\tnext = bag_asp_devastation_again
\t\t\t}
\t\t}
"""


def build(game: Path) -> str:
    """The file text; the type's closing brace is found by counting."""
    text = (game / ALERTS).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    start = text.find("\ttype alert_banner = button {")
    if start < 0:
        raise SystemExit("type alert_banner: the game no longer declares it")
    depth, i = 0, text.index("{", start)
    while True:
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    body = text[start:i].rstrip("\t")
    return HEAD + body + SOUND_CHILD + DEVASTATION_CHILD + "\t}\n}\n"
