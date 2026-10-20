#!/usr/bin/env python3
"""Rebuilds `cmf_dev_beta`: Community Mod Framework for game 1.4, **a whole copy,
loaded instead of CMF Dev** — like `cm_dev_perf`.

Since +beta5 (10-03) the source is the authors' own **CMF 2.5.0**, their port to
1.4. CMF Dev 2.4.1 and CMF 2.4.1 were byte-for-byte the same mod, so 2.5.0 is
what CMF Dev becomes when its authors move it; their changes stand where they put
them. Measured on 2.5.0 against the game's files of 10-01: of 208 vanilla
interface types CMF keeps copies of, 200 are the game's own and the other 8 are
CMF's hooks (the lobby tooltips, its pause-menu buttons, its alert bar). So the
three fixes +beta1..4 carried (75 types from the beta, the beta's lobby,
`use_global_input_instance`) are the authors' now, and are gone from here.

Two changes remain, because 2.5.0 still has the faults:

**`cmf_is_host`.** The game added a native trigger `is_host` («the host of a
multiplayer session»), the name of CMF's own scripted trigger, and in a
single-player game the game's reads false (his probe 10-02). CMF's body is copied
under `cmf_is_host` and CMF's own calls use it; `is_host` stays for other mods.
`cm_dev_perf` and `cm_maps` call `cmf_is_host`.

**The bottom action bar keeps a slot for a hidden button** (+beta6, 10-05). Its
row of buttons is a datamodel `hbox` without `ignoreinvisible`, so a button whose
scripted GUI is not shown (CM's «Пересчитать» while the finder map is closed)
stands as an empty 34 px square that cannot be clicked — his screenshot 10-05,
bottom-left. The top bar is tabs and does not have it.

**The up/down arrows of an ordered list step onto hidden rows** (+beta7, 10-12).
A hidden row (`cmm_hide_list_item`) stays in the list and only its widget is
not drawn, while the arrows move by raw position: «up» under a hidden row swaps
the two and nothing on screen changes. His «works 2 times in 5» on CM's town
rights and on the council priority, 10-12 — both lists hide rows. The arrows now
swap with the nearest row that is shown.

**A typed position for an ordered list** (+beta8, 10-12, his ask: «как порядок
в мод-листе игры»). A box beside the arrows takes a number; Enter moves the row
to that place among the shown rows (1 = the top, past the end = the bottom). The
number reaches script the way CMF's own text setting sends its text: the console
command `effect c:<tag> = { cmf_beta_list_move_to = { ... to = <typed> } }`,
so the typed digits become a literal macro argument. Single player only, like
CMF's text setting.

**CMF's copies of vanilla interface types follow the game** (+beta12, 1.4.1).
`in_game/gui/vanilla/` is 201 types and templates CMF copies from the game,
none of them changed (measured on 2.5.0: 190 equal to 1.4.1, the other 11 equal
to 1.4.0 — the town-rights revoke conditions, the DLC map-mode hover, the
widened production numbers). A stale copy shadows the game's, so the patch
never shows. Each one that differs from the game is replaced by the game's
own definition and named in the output; a copy that mentions CMF (`cmf`/`cmm`)
would be CMF's hook and is left alone.

    python3 mods/cmf_dev_beta/tools/port_from_cmf_dev.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/cmf_dev_beta"
SRC = refs.mod("community_mod_framework")

_spec = importlib.util.spec_from_file_location(
    "beta_windows", refs.REPO / "mods/cm_dev_perf/tools/beta_windows.py")
beta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(beta)

REVISION = 14


def metadata() -> str:
    base = json.loads((SRC / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    version = base.get("version", "unknown")
    base["name"] = "Community Mod Framework Dev (1.4)"
    base["id"] = "bag.cmf_dev_beta"
    base["version"] = f"{version}+beta{REVISION}"
    base["supported_game_version"] = "1.4.*"
    base["short_description"] = (
        f"Community Mod Framework {version} (the authors' 1.4 port) with two fixes: CMF's "
        "own is_host is called as cmf_is_host, since the game's native is_host is false "
        "in single player; the bottom action bar no longer keeps empty slots for hidden "
        "buttons; ordered-list arrows step over hidden rows, and a typed number moves a row. "
        "Load this INSTEAD of CMF and CMF Dev.")
    base["relationships"] = []
    return json.dumps(base, indent=4, ensure_ascii=False) + "\n"


HOST_TRIGGERS = "in_game/common/scripted_triggers/cmf_core_triggers.txt"
HOST_CALL = re.compile(r"^([ \t]*)is_host(\s*=\s*(?:yes|no)\b)", re.M)


def own_host_trigger() -> int:
    """CMF's `is_host` copied as `cmf_is_host`, and CMF's calls moved onto it."""
    path = MOD / HOST_TRIGGERS
    text = path.read_text(encoding="utf-8-sig")
    span = re.search(r"^is_host = \{", text, re.M)
    if not span:
        raise SystemExit(f"{HOST_TRIGGERS}: CMF no longer defines is_host")
    _, end = beta._block(text, span.end(), 0)
    body = text[span.start():end]
    calls = 0
    for each in (MOD / "in_game/common").rglob("*.txt"):
        old = each.read_text(encoding="utf-8-sig")
        new, n = HOST_CALL.subn(r"\1cmf_is_host\2", old)
        if n:
            each.write_text("\ufeff" + new, encoding="utf-8")
            calls += n
    text = path.read_text(encoding="utf-8-sig")
    text += ("\n\n# cmf_dev_beta: CMF's is_host under a name of its own -- the beta added a\n"
             "# native trigger is_host, and CMF's calls must reach this body.\n"
             + body.replace("is_host = {", "cmf_is_host = {", 1) + "\n")
    path.write_text("\ufeff" + text, encoding="utf-8")
    return calls


VANILLA_TYPES = "in_game/gui/vanilla"
TYPE_NAME = re.compile(r"^[ \t]*(?:type\s+(\w+)\s*=\s*\w+|template\s+(\w+))\s*\{", re.M)


def vanilla_types_current() -> list[str]:
    """CMF's plain copies of game types replaced by the game's current ones."""
    taken = []
    for path in sorted((MOD / VANILLA_TYPES).glob("*.gui")):
        raw = path.read_text(encoding="utf-8-sig")
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        for name in [m.group(1) or m.group(2) for m in TYPE_NAME.finditer(text)]:
            span = beta.type_block(text, name)
            if not span:
                continue
            mine = text[span[0]:span[1]]
            if re.search(r"cmf|cmm", mine, re.I):
                continue
            try:
                game = beta.beta_type(refs.GAME_GUI, name)
            except beta.EditFailed:
                continue
            if " ".join(mine.split()) == " ".join(game.split()):
                continue
            text = text[:span[0]] + game + text[span[1]:]
            taken.append(f"{path.stem}:{name}")
        out = text.replace("\n", "\r\n") if crlf else text
        path.write_text("\ufeff" + out, encoding="utf-8")
    return taken


ACTION_BAR = "in_game/gui/cmf/cmf_action_bar.gui"
BAR_ROW = ("        hbox = {\n"
           "            spacing = 4\n"
           "            datamodel = \"[GetPlayer.MakeScope.GetList('cmf_action_bar_active_elements')]\"\n")


def bar_ignores_hidden() -> None:
    """The bottom bar's button row skips hidden buttons instead of keeping their slot."""
    path = MOD / ACTION_BAR
    text = path.read_text(encoding="utf-8-sig")
    if text.count(BAR_ROW) != 1:
        raise SystemExit(f"{ACTION_BAR}: the bottom bar's button row moved")
    text = text.replace(BAR_ROW, BAR_ROW.replace(
        "spacing = 4\n", "spacing = 4\n            ignoreinvisible = yes\n", 1))
    path.write_text("\ufeff" + text, encoding="utf-8")


LIST_RUNTIME = "in_game/common/scripted_effects/cmm_core_list_setting_runtime_effects.txt"
STEPS = {
    "up": "\t\t\tset_local_variable = { name = cmm_list_target_index value = "
          "{ value = var:cmm_list_position_to_apply subtract = 1 } }\n",
    "down": "\t\t\tset_local_variable = { name = cmm_list_target_index value = "
            "{ value = var:cmm_list_position_to_apply add = 1 } }\n",
}
REORDER = "\t\t\t_cmm_reorder_list_setting = { setting = $setting$ vt = $vt$ lt = $lt$ }\n"
NEIGHBOUR = """
# cmf_dev_beta: the nearest row that is shown {where} the marked one, as
# local_var:cmm_list_target_index (-1 when there is none). A hidden row stays in
# the list, so a step of one position can land on it and change nothing seen.
_cmf_beta_shown_neighbour_{dir} = {{
\tset_local_variable = {{ name = cmm_list_target_index value = -1 }}
\tset_local_variable = {{ name = cmm_list_scan_index value = 0 }}
\tset_local_variable = {{ name = cmm_list_scan_marked value = var:cmm_list_position_to_apply }}
\tevery_$lt$_list = {{
\t\tvariable = cmm_list_items_$setting$
\t\tsave_scope_as = cmm_list_scan_item
\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tNOT = {{ root = {{ is_key_in_variable_map = {{ name = cmm_list_item_hidden target = scope:cmm_list_scan_item }} }} }}
{test}
\t\t\t}}
\t\t\tset_local_variable = {{ name = cmm_list_target_index value = local_var:cmm_list_scan_index }}
\t\t}}
\t\tchange_local_variable = {{ name = cmm_list_scan_index add = 1 }}
\t}}
}}
"""
TESTS = {
    # the last shown row above wins
    "up": ("above", "\t\t\t\tlocal_var:cmm_list_scan_index < local_var:cmm_list_scan_marked"),
    # the first shown row below wins
    "down": ("below", "\t\t\t\tlocal_var:cmm_list_scan_index > local_var:cmm_list_scan_marked\n"
                      "\t\t\t\tlocal_var:cmm_list_target_index < 0"),
}


def arrows_skip_hidden() -> None:
    """Ordered-list up/down swap with the nearest shown row, not the next position."""
    path = MOD / LIST_RUNTIME
    text = path.read_text(encoding="utf-8-sig")
    for direction, step in STEPS.items():
        if text.count(step + REORDER) != 1:
            raise SystemExit(f"{LIST_RUNTIME}: the {direction} arrow's step moved")
        text = text.replace(step + REORDER, (
            f"\t\t\t_cmf_beta_shown_neighbour_{direction} = {{ setting = $setting$ lt = $lt$ }}\n"
            "\t\t\tif = {\n"
            "\t\t\t\tlimit = { local_var:cmm_list_target_index >= 0 }\n"
            "\t" + REORDER + "\t\t\t}\n"))
    for direction, (where, test) in TESTS.items():
        text += NEIGHBOUR.format(dir=direction, where=where, test=test)
    path.write_text("\ufeff" + text, encoding="utf-8")


LIST_GUI = "in_game/gui/cmm/cmm_components/cmm_list_setting.gui"
HEADER_ARROWS = ("\t\t\t\twidget = {\n\t\t\t\t\tsize = { 56 0 }\n\t\t\t\t\tminimumsize = { 56 0 }\n"
                 "\t\t\t\t\tvisible = \"[CMMListSettingIsOrdered(Scope.GetFlagName)]\"\n\t\t\t\t}\n")
HEADER_BOX = ("\t\t\t\t# cmf_dev_beta: room for the typed position below.\n"
              "\t\t\t\twidget = {\n\t\t\t\t\tsize = { 44 0 }\n\t\t\t\t\tminimumsize = { 44 0 }\n"
              "\t\t\t\t\tvisible = \"[CMMListSettingIsOrdered(Scope.GetFlagName)]\"\n\t\t\t\t}\n")
ROW_ARROWS = ("\t\t\twidget = {\n\t\t\t\tsize = { 56 28 }\n\t\t\t\tminimumsize = { 56 28 }\n"
              "\t\t\t\tvisible = \"[CMMListItemSettingIsOrdered(Scope.GetFlagName)]\"\n")
ROW_BOX = """\t\t\t# cmf_dev_beta: the row's place among the shown rows, as the game's mod list
\t\t\t# draws a load order (mods_gui.gui, selected_mod_item): a number; a click
\t\t\t# opens a box over it, Enter moves the row there and closes the box.
\t\t\twidget = {
\t\t\t\tsize = { 44 28 }
\t\t\t\tminimumsize = { 44 28 }
\t\t\t\tvisible = "[CMMListItemSettingIsOrdered(Scope.GetFlagName)]"
\t\t\t\ttooltip = "CMF_BETA_LIST_TYPE_POSITION"

\t\t\t\t# The place: cmf_beta_list_place, kept by cmf_beta_list_renumber after
\t\t\t\t# every reorder, so every row's number follows the move (his ask 10-12:
\t\t\t\t# +beta10 left the typed number in the box of the row that moved in).
\t\t\t\tbutton_default = {
\t\t\t\t\tsize = { 44 28 }
\t\t\t\t\tparentanchor = center
\t\t\t\t\twidgetanchor = center
\t\t\t\t\tvisible = "[Not(GetVariableSystem.Exists(Concatenate('cmf_beta_edit_place_', Scope.GetFlagName)))]"
\t\t\t\t\tenabled = "[CMMListItemCanEdit(Scope.GetFlagName)]"
\t\t\t\t\tonclick = "[GetVariableSystem.Set(Concatenate('cmf_beta_edit_place_', Scope.GetFlagName), 'yes')]"

\t\t\t\t\ttext_single = {
\t\t\t\t\t\tparentanchor = center
\t\t\t\t\t\talign = center|nobaseline
\t\t\t\t\t\tvisible = "[GreaterThan_int32(CMMMapInt('cmf_beta_list_place', Scope.GetFlagName), '(int32)0')]"
\t\t\t\t\t\ttext = "[ToString_int32(CMMMapInt('cmf_beta_list_place', Scope.GetFlagName))]"
\t\t\t\t\t}
\t\t\t\t\t# A list nobody has reordered has no place map yet (the renumber runs
\t\t\t\t\t# after a move): Construction Manager's categories showed 0 on every
\t\t\t\t\t# row (10-13). Until then, the row's own index + 1, as the arrows read it.
\t\t\t\t\ttext_single = {
\t\t\t\t\t\tparentanchor = center
\t\t\t\t\t\talign = center|nobaseline
\t\t\t\t\t\tvisible = "[Not(GreaterThan_int32(CMMMapInt('cmf_beta_list_place', Scope.GetFlagName), '(int32)0'))]"
\t\t\t\t\t\ttext = "[ToString_int32(Add_int32(PdxGuiWidget.GetIndexInDataModel, '(int32)1'))]"
\t\t\t\t\t}
\t\t\t\t}

\t\t\t\t# The game's editbox_single (main_menu/gui/editbox.gui) stretches and keeps
\t\t\t\t# 12 px each side; here it has a size of its own and room for two digits.
\t\t\t\teditbox_single = {
\t\t\t\t\tsize = { 44 28 }
\t\t\t\t\tmargin = { 6 0 }
\t\t\t\t\talign = center|nobaseline
\t\t\t\t\tparentanchor = center
\t\t\t\t\twidgetanchor = center
\t\t\t\t\tfocuspolicy = all
\t\t\t\t\talwaystransparent = no
\t\t\t\t\tmultiline = no
\t\t\t\t\tvisible = "[GetVariableSystem.Exists(Concatenate('cmf_beta_edit_place_', Scope.GetFlagName))]"
\t\t\t\t\tfocus_on_visible = yes
\t\t\t\t\ttext = ""

\t\t\t\t\t# Enter has one handler; the state runs the arrows' own path: mark
\t\t\t\t\t# the row, mark the place (CMF_BETA_MarkListPlace_<N>, a scripted GUI
\t\t\t\t\t# per number, as CMM_MarkListPosition_<N>), report the change, close.
\t\t\t\t\t# +beta10: this moved the row (10-12); PdxClearEditBoxText did not
\t\t\t\t\t# clear, so the box now closes instead.
\t\t\t\t\tstate = {
\t\t\t\t\t\tname = cmf_beta_place_go
\t\t\t\t\t\ton_start = "[CMMExecuteGuiSuffix('CMM_MarkListPosition_', ToString_int32(PdxGuiWidget.GetIndexInDataModel))]"
\t\t\t\t\t\ton_start = "[CMMExecuteGuiSuffix('CMF_BETA_MarkListPlace_', GetTextFromSelfOrAnyChildEditbox(PdxGuiWidget.Self))]"
\t\t\t\t\t\ton_start = "[CMMExecuteListItemSettingChanged(Scope.GetFlagName)]"
\t\t\t\t\t\ton_start = "[PdxClearEditBoxText(PdxGuiWidget.Self)]"
\t\t\t\t\t\ton_start = "[GetVariableSystem.Clear(Concatenate('cmf_beta_edit_place_', Scope.GetFlagName))]"
\t\t\t\t\t\ton_start = "[PdxGuiTriggerAllAnimations('cmm_recache_delay')]"
\t\t\t\t\t}

\t\t\t\t\tblockoverride "editbox_properties" {
\t\t\t\t\t\tonreturnpressed = "[PdxGuiWidget.TriggerAnimation('cmf_beta_place_go')]"
\t\t\t\t\t\tonfocusout = "[GetVariableSystem.Clear(Concatenate('cmf_beta_edit_place_', Scope.GetFlagName))]"
\t\t\t\t\t\tmaxcharacters = 2
\t\t\t\t\t}

\t\t\t\t\tblockoverride "editbox_label" {
\t\t\t\t\t\ttext = ""
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}

"""
PLACE_ACTION = 51
ACTION_TOP = ("\t\telse_if = {\n\t\t\tlimit = { AND = { has_variable = cmm_list_action_to_apply "
              "var:cmm_setting_list_is_ordered_$setting$ = 1 var:cmm_list_action_to_apply = 3 ")
PLACE_DISPATCH = (
    "\t\t# cmf_dev_beta: the typed place (CMF_BETA_MarkListPlace_<N>).\n"
    "\t\telse_if = {\n"
    "\t\t\tlimit = { AND = { has_variable = cmm_list_action_to_apply "
    f"var:cmm_setting_list_is_ordered_$setting$ = 1 var:cmm_list_action_to_apply = {PLACE_ACTION} "
    "has_variable = cmf_beta_list_place_to_apply } }\n"
    "\t\t\t_cmf_beta_list_place_target = { setting = $setting$ lt = $lt$ }\n"
    "\t\t\t_cmm_reorder_list_setting = { setting = $setting$ vt = $vt$ lt = $lt$ }\n"
    "\t\t}\n")
MOVE_EFFECT = """
# cmf_dev_beta: the reinsert index (local_var:cmm_list_target_index, as the
# reorder wants it: among the rows other than the marked one) of place
# var:cmf_beta_list_place_to_apply among the shown rows; 1 and below is the top,
# past the last shown row the bottom.
# Scope: country
_cmf_beta_list_place_target = {
\tset_local_variable = { name = cmf_beta_to value = var:cmf_beta_list_place_to_apply }
\tremove_variable = cmf_beta_list_place_to_apply
\tif = {
\t\tlimit = { local_var:cmf_beta_to < 1 }
\t\tset_local_variable = { name = cmf_beta_to value = 1 }
\t}
\tset_local_variable = { name = cmm_list_target_index value = 9999 }
\tset_local_variable = { name = cmm_list_scan_index value = 0 }
\tset_local_variable = { name = cmm_list_scan_raw value = 0 }
\tset_local_variable = { name = cmm_list_scan_shown value = 0 }
\tset_local_variable = { name = cmm_list_scan_marked value = var:cmm_list_position_to_apply }
\tevery_$lt$_list = {
\t\tvariable = cmm_list_items_$setting$
\t\tsave_scope_as = cmm_list_scan_item
\t\tif = {
\t\t\tlimit = { NOT = { local_var:cmm_list_scan_raw = local_var:cmm_list_scan_marked } }
\t\t\tif = {
\t\t\t\tlimit = { NOT = { root = { is_key_in_variable_map = { name = cmm_list_item_hidden target = scope:cmm_list_scan_item } } } }
\t\t\t\tchange_local_variable = { name = cmm_list_scan_shown add = 1 }
\t\t\t\tif = {
\t\t\t\t\tlimit = {
\t\t\t\t\t\tlocal_var:cmm_list_scan_shown = local_var:cmf_beta_to
\t\t\t\t\t\tlocal_var:cmm_list_target_index = 9999
\t\t\t\t\t}
\t\t\t\t\tset_local_variable = { name = cmm_list_target_index value = local_var:cmm_list_scan_index }
\t\t\t\t}
\t\t\t}
\t\t\tchange_local_variable = { name = cmm_list_scan_index add = 1 }
\t\t}
\t\tchange_local_variable = { name = cmm_list_scan_raw add = 1 }
\t}
}
"""
PLACE_SGUI = ("# cmf_dev_beta: the typed place of an ordered list row, one scripted GUI per\n"
              "# number as CMF's CMM_MarkListPosition_<N>; text that is not a number names\n"
              "# none, and nothing moves. Scope: country\n"
              "\n"
              + "".join(f"CMF_BETA_MarkListPlace_{n} = {{ effect = {{ set_variable = {{ name = cmf_beta_list_place_to_apply value = {n} }} "
                        f"set_variable = {{ name = cmm_list_action_to_apply value = {PLACE_ACTION} }} }} }}\n"
                        for n in range(0, 100)))
RENUMBER = """
# cmf_dev_beta: number the shown rows of one list 1, 2, 3… into the country's
# variable map cmf_beta_list_place, keyed by the row's flag; the typed-place box
# shows it. Runs after every reorder; a mod that hides or shows rows calls
# cmf_beta_list_renumber = { setting = <mod_id>__<setting_id> } after them.
# Scope: country
cmf_beta_list_renumber = {
\tset_local_variable = { name = cmm_tmp_flag value = flag:$setting$ }
\tif = {
\t\tlimit = { "variable_map(cmm_is_global|local_var:cmm_tmp_flag)" >= 1 }
\t\t_cmf_beta_list_renumber = { setting = $setting$ lt = in_global }
\t}
\telse = {
\t\t_cmf_beta_list_renumber = { setting = $setting$ lt = in }
\t}
}

_cmf_beta_list_renumber = {
\tset_local_variable = { name = cmf_beta_place value = 0 }
\tevery_$lt$_list = {
\t\tvariable = cmm_list_items_$setting$
\t\tsave_scope_as = cmf_beta_place_item
\t\tif = {
\t\t\tlimit = { root = { is_key_in_variable_map = { name = cmm_list_item_hidden target = scope:cmf_beta_place_item } } }
\t\t\troot = { add_to_variable_map = { name = cmf_beta_list_place key = scope:cmf_beta_place_item value = 0 } }
\t\t}
\t\telse = {
\t\t\tchange_local_variable = { name = cmf_beta_place add = 1 }
\t\t\troot = { add_to_variable_map = { name = cmf_beta_list_place key = scope:cmf_beta_place_item value = local_var:cmf_beta_place } }
\t\t}
\t}
}
"""
REORDER_END = "\tclear_variable_list = cmm_list_rebuild_temp\n}\n"
MOVE_LOC = {
    "english": ('CMF_BETA_LIST_TYPE_POSITION: "Click, type a place and press Enter: the row moves there"\n'
                'CMF_BETA_LIST_POSITION_LABEL: "#"\n'),
    "russian": ('CMF_BETA_LIST_TYPE_POSITION: "Нажмите, впишите место и нажмите Enter: строка встанет туда"\n'
                'CMF_BETA_LIST_POSITION_LABEL: "№"\n'),
}


def typed_position() -> None:
    """A number box beside an ordered row's arrows moves the row to that place."""
    path = MOD / LIST_GUI
    text = path.read_text(encoding="utf-8-sig")
    if text.count(HEADER_ARROWS) != 1 or text.count(ROW_ARROWS) != 1:
        raise SystemExit(f"{LIST_GUI}: the arrows' column moved")
    text = text.replace(HEADER_ARROWS, HEADER_ARROWS + "\n" + HEADER_BOX, 1)
    start = text.index(ROW_ARROWS)
    _, end = beta._block(text, start + len("\t\t\twidget = {"), 0)
    end = text.index("\n", end) + 1
    text = text[:end] + "\n" + ROW_BOX + text[end:].lstrip("\n")
    path.write_text("\ufeff" + text, encoding="utf-8")
    runtime = MOD / LIST_RUNTIME
    body = runtime.read_text(encoding="utf-8-sig")
    if body.count(REORDER_END) != 1:
        raise SystemExit(f"{LIST_RUNTIME}: the reorder's end moved")
    body = body.replace(REORDER_END, "\tclear_variable_list = cmm_list_rebuild_temp\n"
                        "\t_cmf_beta_list_renumber = { setting = $setting$ lt = $lt$ }\n}\n", 1)
    if body.count(ACTION_TOP) != 1:
        raise SystemExit(f"{LIST_RUNTIME}: the move-to-top branch moved")
    body = body.replace(ACTION_TOP, PLACE_DISPATCH + ACTION_TOP, 1)
    runtime.write_text("\ufeff" + body + MOVE_EFFECT + RENUMBER, encoding="utf-8")
    sgui = MOD / "in_game/common/scripted_guis/cmf_beta_list_place_scripted_gui.txt"
    sgui.write_text("\ufeff" + PLACE_SGUI, encoding="utf-8")
    for language, rows in MOVE_LOC.items():
        out = MOD / f"main_menu/localization/{language}/cmf_beta_l_{language}.yml"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\ufeff" + f"l_{language}:\n" + "".join(" " + r + "\n" for r in rows.splitlines()),
                       encoding="utf-8")


def main() -> int:
    for name in ("in_game", "main_menu", "loading_screen", ".metadata"):
        if (MOD / name).exists():
            shutil.rmtree(MOD / name)
    for name in ("in_game", "main_menu", "loading_screen"):
        if (SRC / name).exists():
            shutil.copytree(SRC / name, MOD / name)
    host_calls = own_host_trigger()
    bar_ignores_hidden()
    arrows_skip_hidden()
    typed_position()
    taken = vanilla_types_current()
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("﻿" + metadata(), encoding="utf-8")
    thumb = SRC / ".metadata/thumbnail.png"
    if thumb.exists():
        shutil.copy2(thumb, MOD / ".metadata/thumbnail.png")
    print("cmf_dev_beta: whole copy of %s, %d is_host calls on cmf_is_host"
          % (SRC.name, host_calls))
    print("     %d vanilla types taken from the game over CMF's stale copies%s"
          % (len(taken), (": " + ", ".join(taken)) if taken else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
