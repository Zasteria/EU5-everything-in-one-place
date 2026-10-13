#!/usr/bin/env python3
"""Shifting societal values through the game's own window, his choice 12.10.

Script can put an advisor on `change_societal_values` but cannot name the pair
or the side: the pair stays empty (his runs 12.10). Only the game's window
`select_societal_value` picks them. So:

- `bag_asp_hidden.gui`, always present, opens that window for the seat in
  `bag_asp_sv_cab` when script sets `bag_asp_sv_open`
  (`ChangeCabinetActionTarget`, the right click on a seat);
- the window, the game's file copied whole, carries in each pair's row two
  children that press its left or right side when script asked for that pair
  (`bag_asp_sv_pair`) and that side (`bag_asp_sv_left` / `bag_asp_sv_right`).

Opened by hand, the window is the game's: nothing presses unless a side flag
is set, and the flags live only between the mod's request and the press.

Closing (his ask 13.10, «хотя бы просто закрыть»). A press shuts the pick view
by itself and leaves the panel under it open (his run 13.10 12:17: the closer
gated on `IsLateralViewOpened('select_societal_value')` never saw it open after
the mod's press, and fired only when he opened it by hand). So the press calls
`PdxGuiTriggerAllAnimations('bag_asp_sv_shut')`, and a widget of the hidden
window plays that state and closes both side panels (`LeftView.Close`,
`RightView.Close`, the game's own close button is `LateralView.Close`). Nothing
waits on a gate: the call comes from the press itself, the CM pattern
(`docs/pitfalls/windows.md`). When no row presses (the window leaves out the
pair the seat already pushes), the opener's `bag_asp_sv_wait` clears the flags
and closes the same way two seconds later.

    import value_window
    value_window.build(refs.GAME)     # {path under the mod: text}
"""

from __future__ import annotations

from pathlib import Path

WINDOW = "in_game/gui/select_societal_value.gui"
HIDDEN = "in_game/gui/bag_asp_hidden.gui"
WIDGETS = "in_game/gui/scripted_widgets/bag_asp_scripted_widgets.txt"

ROOT = "GuiScope.SetRoot(GetPlayer.MakeScope).End"
# The sides the mod presses.
SIDES = ("left", "right")


def var(name: str) -> str:
    return f"GetPlayer.MakeScope.GetVariable('{name}')"


def presser(side: str) -> str:
    """A child of a pair's row: presses `side` once, as it turns visible."""
    select = "SelectLeftCandidate" if side == "left" else "SelectRightCandidate"
    same = (f"ObjectsEqual(SocietalValueCandidate.GetSocietalValue.Self, "
            f"{var('bag_asp_sv_pair')}.GetSocietalValue.Self)")
    return f"""
\t\t\t\t\t\t\t\t# assimilate_primary: presses the {side} side of this pair when the
\t\t\t\t\t\t\t\t# council automation asked for it (value_window.py).
\t\t\t\t\t\t\t\twidget = {{
\t\t\t\t\t\t\t\t\tname = "bag_asp_sv_press_{side}"
\t\t\t\t\t\t\t\t\tsize = {{ 0 0 }}
\t\t\t\t\t\t\t\t\tvisible_at_creation = no
\t\t\t\t\t\t\t\t\tvisible = "[And({var('bag_asp_sv_' + side)}.IsSet, {same})]"
\t\t\t\t\t\t\t\t\tstate = {{
\t\t\t\t\t\t\t\t\t\tname = _show
\t\t\t\t\t\t\t\t\t\tduration = 0.1
\t\t\t\t\t\t\t\t\t\ton_start = "[SocietalValueCandidate.{select}]"
\t\t\t\t\t\t\t\t\t\ton_start = "[GetScriptedGui('bag_asp_sv_pressed').Execute({ROOT})]"
\t\t\t\t\t\t\t\t\t\ton_start = "[PdxGuiTriggerAllAnimations('bag_asp_sv_shut')]"
\t\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t}}
"""


def row_log() -> str:
    """A child of a pair's row: names the pair in debug.log once, while the mod
    waits for a press. The probe's way of seeing which rows the window built
    when no press comes."""
    wants = " ".join(f"{var('bag_asp_sv_' + s)}.IsSet" for s in SIDES)
    if len(SIDES) > 1:
        wants = f"Or({', '.join(wants.split(' '))})"
    scope = f"GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('sv', SocietalValueCandidate.GetSocietalValue.MakeScope).End"
    return f"""
\t\t\t\t\t\t\t\t# assimilate_primary: names this pair in debug.log while the council
\t\t\t\t\t\t\t\t# automation waits for a press (value_window.py).
\t\t\t\t\t\t\t\twidget = {{
\t\t\t\t\t\t\t\t\tname = "bag_asp_sv_row_log"
\t\t\t\t\t\t\t\t\tsize = {{ 0 0 }}
\t\t\t\t\t\t\t\t\tvisible_at_creation = no
\t\t\t\t\t\t\t\t\tvisible = "[{wants}]"
\t\t\t\t\t\t\t\t\tstate = {{
\t\t\t\t\t\t\t\t\t\tname = _show
\t\t\t\t\t\t\t\t\t\tduration = 0.1
\t\t\t\t\t\t\t\t\t\ton_start = "[GetScriptedGui('bag_asp_sv_row').Execute({scope})]"
\t\t\t\t\t\t\t\t\t}}
\t\t\t\t\t\t\t\t}}
"""


def live(children: str, tabs: int) -> str:
    """The children under a parent whose visible is an always-true expression.
    His run 13.10 11:40: inside the game's window a child's gate was read when
    the row was built and never again — the closers never fired, and a second
    request into the open window drew no row. cm_hidden_window.gui keeps its
    gates live this way, and ours there fire (the opener, every run)."""
    pad = "\t" * tabs
    # The children carry their own indent; one level more puts them inside.
    body = "".join("\t" + line if line.strip() else line
                   for line in children.lstrip("\n").splitlines(keepends=True))
    return (f"\n{pad}# assimilate_primary: keeps the gates below re-read every frame\n"
            f"{pad}# (value_window.py, as cm_hidden_window.gui).\n"
            f"{pad}widget = {{\n{pad}\tname = \"bag_asp_sv_live\"\n{pad}\tsize = {{ 0 0 }}\n"
            f"{pad}\tvisible = \"[EqualTo_CFixedPoint('(CFixedPoint)0', '(CFixedPoint)0')]\"\n"
            f"{body}{pad}}}\n")


HIDDEN_TEXT = f"""# assimilate_primary: always present, never seen. Opens the game's window of
# societal values for the seat the council automation chose. Built by
# tools/value_window.py, do not edit by hand.
widget = {{
\tname = "bag_asp_hidden"
\t# Keeps the children's visibility re-evaluated (cm_hidden_window.gui).
\tvisible = "[EqualTo_CFixedPoint('(CFixedPoint)0', '(CFixedPoint)0')]"
\tposition = {{ -10000 1 }}
\twidget = {{
\t\tname = "bag_asp_sv_opener"
\t\tsize = {{ 0 0 }}
\t\t# Hidden at creation, so a save loaded with the flag already set still
\t\t# turns it visible and fires _show.
\t\tvisible_at_creation = no
\t\tvisible = "[And(GetPlayer.Exists, {var('bag_asp_sv_open')}.IsSet)]"
\t\tstate = {{
\t\t\tname = _show
\t\t\tduration = 0.1
\t\t\ton_start = "[ChangeCabinetActionTarget({var('bag_asp_sv_cab')}.GetCabinet.Self)]"
\t\t\ton_start = "[GetScriptedGui('bag_asp_sv_opening').Execute({ROOT})]"
\t\t\ton_start = "[PdxGuiTriggerAllAnimations('bag_asp_sv_wait')]"
\t\t}}
\t}}
\t# His ask 13.10, «хотя бы просто закрыть». Plays a state only when called
\t# by name: `bag_asp_sv_shut` by the press, `bag_asp_sv_wait` by the opener.
\t# No gate: 0.9.12's gated closer misfired on his own clicks.
\twidget = {{
\t\tname = "bag_asp_sv_shutter"
\t\tsize = {{ 0 0 }}
\t\tstate = {{
\t\t\tname = bag_asp_sv_shut
\t\t\tduration = 0.2
\t\t\ton_finish = "[GetScriptedGui('bag_asp_sv_closed').Execute({ROOT})]"
\t\t\ton_finish = "[LeftView.Close]"
\t\t\ton_finish = "[RightView.Close]"
\t\t}}
\t\tstate = {{
\t\t\tname = bag_asp_sv_wait
\t\t\tduration = 2
\t\t\ton_finish = "[GetScriptedGui('bag_asp_sv_timeout').Execute({ROOT})]"
\t\t\ton_finish = "[LeftView.Close]"
\t\t\ton_finish = "[RightView.Close]"
\t\t}}
\t}}
}}
"""


def build(game: Path) -> dict[str, str]:
    text = (game / WINDOW).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    model = text.find('datamodel = "[SelectSocietalValue.GetCandidates]"')
    if model < 0:
        raise SystemExit("select_societal_value: the game's window no longer lists candidates")
    row = text.find("size = { 100% 50 }", model)
    if row < 0 or "SelectLeftCandidate" not in text or "SelectRightCandidate" not in text:
        raise SystemExit("select_societal_value: the pair's row changed; read the game's window first")
    at = text.index("\n", row) + 1
    head = ("# assimilate_primary: the game's select_societal_value.gui, copied whole,\n"
            "# with the council automation's children. Built by tools/value_window.py.\n")
    window = (head + text[:at]
              + live(row_log() + "".join(presser(s) for s in SIDES), 8) + text[at:])
    return {
        WINDOW: window,
        HIDDEN: HIDDEN_TEXT,
        WIDGETS: "gui/bag_asp_hidden.gui = bag_asp_hidden\n",
    }
