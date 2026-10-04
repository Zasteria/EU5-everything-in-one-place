#!/usr/bin/env python3
"""Rebuilds `cm_dev_perf`: Construction Manager **dev** with the cm_perf edit
that still applies to it.

A byte-for-byte copy of `reference/mods/<CM dev>/` plus the edits in `EDITS`.
Names are left alone (`cm_*`, CMF `mod_id = cm`, file paths): load it
**instead of** CM dev, never alongside it.

    python3 mods/cm_dev_perf/tools/port_from_cm_dev.py

What dev already carries and cm_perf had to add: the one-sweep-per-cycle drain
and the stall rescan (cm_perf edit 3 was taken off dev). What dev still lacks:

1. **The building-type tree has no gate of its own.** Dev's hidden window keeps
   a datamodel over every building type, with demand and production-method
   datamodels under each, standing under an always-true root for the whole
   session. Every one of those widgets is walked by every
   `PdxGuiTriggerAllAnimations` the queue drain fires, and their `visible`
   gates re-evaluate each frame. cm_perf gated the same tree; its run on
   2026-09-18 confirmed the classification still works. Dev differs in one
   way: the mid-session upgrade-map refresh (`cm_upgrade_type_refresh_state`)
   also lives in this tree, so the gate is either pass, not only the
   classification.

2. **A probe window** (`tools/probe/`, 2026-09-27): says whether the
   classification has closed. Open past the first seconds means the tree
   stands all session and the classification is incomplete, the suspected
   cause of perf's slow loads and wrong builds. Closed with its cross.

cm_perf's edit 5 (auto-expand verdict cached monthly) is left out on purpose:
the slot circles live only in the district and production windows, which she
opens on pause, so they cost nothing while the game runs (her call 2026-09-26).
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

MOD = refs.REPO / "mods/cm_dev_perf"
PROBE = MOD / "tools/probe"
SRC = refs.mod("romaimperator.construction_manager.dev", "construction_manager_dev")

# cm_perf's generator holds the first-pass widening; reuse it rather than keep
# two copies that drift apart.
_spec = importlib.util.spec_from_file_location(
    "cm_perf_port", refs.REPO / "mods/cm_perf/tools/port_from_cm.py"
)
perf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perf)

WINDOW = perf.WINDOW

_spec = importlib.util.spec_from_file_location(
    "beta_windows", Path(__file__).resolve().parent / "beta_windows.py")
beta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(beta)
BETA_SPECS = Path(__file__).resolve().parent / "beta"
BETA_RIO = Path(__file__).resolve().parent / "beta_rio"

_CLASSIFY = (
    "GetScriptedGui('cm_should_building_type_section_show')"
    ".IsShown(GuiScope.SetRoot(GetPlayer.MakeScope)"
    ".AddScope('cm_country', GetPlayer.MakeScope).End)"
)
_REFRESH = (
    "GetScriptedGui('cm_should_refresh_upgrade_types')"
    ".IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End)"
)
# Both drivers' own gates, copied off them: the tree stands while either pass runs.
GATE = f"\"[And(GetPlayer.Exists, Or({_CLASSIFY}, {_REFRESH}))]\""


def _gate_the_tree(text: str) -> str:
    """Give the building-type tree the gates of the two passes that use it."""
    anchor = (
        "\t\twidget = {\n"
        "\t\t\tdatamodel = \"[GetGlobalList('cm_building_types_to_process')]\"\n"
    )
    for part in (_CLASSIFY, _REFRESH):
        if part not in text:
            raise SystemExit(f"{WINDOW}: a driver gate has changed: {part}")
    if text.count(anchor) != 1:
        raise SystemExit(
            f"{WINDOW}: the building-type tree is not where this edit expects it; "
            "CM dev was rebuilt -- re-read the file before trusting this generator."
        )
    return text.replace(
        anchor,
        "\t\twidget = {\n"
        "\t\t\t# cm_dev_perf: stands only while the classification or the upgrade-map\n"
        "\t\t\t# refresh is armed. CM leaves it ungated under an always-true root, so every\n"
        "\t\t\t# type's widgets live, re-evaluate and get walked by each tree-wide trigger\n"
        "\t\t\t# for the whole session.\n"
        f"\t\t\tvisible = {GATE}\n"
        "\t\t\tdatamodel = \"[GetGlobalList('cm_building_types_to_process')]\"\n",
    )


def _widen_refresh(text: str) -> str:
    """Same reason as the first pass: the tree is now built when the gate opens."""
    anchor = (
        "\t\t\tstate = {\n"
        "\t\t\t\tname = _show\n"
        "\t\t\t\tduration = 0.5\n"
        "\t\t\t\tnext = cm_upgrade_type_refresh_done\n"
    )
    if text.count(anchor) != 1:
        raise SystemExit(f"{WINDOW}: the upgrade refresh driver's _show has moved")
    return text.replace(
        anchor,
        "\t\t\tstate = {\n"
        "\t\t\t\tname = _show\n"
        "\t\t\t\t# cm_dev_perf: 1.0 rather than 0.5 -- the gated tree is built when this opens.\n"
        "\t\t\t\tduration = 1\n"
        "\t\t\t\tnext = cm_upgrade_type_refresh_done\n",
    )


LOG = "in_game/common/scripted_effects/cm_log_effects.txt"
ROADS = "in_game/common/scripted_effects/cm_ab_roads_effects.txt"
CMM = "in_game/common/scripted_effects/cm_cmm_effects.txt"
CORE = "in_game/common/scripted_effects/cm_ab_core_effects.txt"
# wrapper: (number of values, logs a location, logs a building type)
_LOGGED = {
    "cm_dbg_log": (0, False, False),
    "cm_dbg_log_value": (1, False, False),
    "cm_dbg_log_at_loc": (0, True, False),
    "cm_dbg_log_loc": (1, True, False),
    "cm_dbg_log_loc_values": (3, True, False),
    "cm_dbg_log_bld": (2, True, True),
}


def _mirror_log(text: str) -> str:
    """Every line CM's Debug tab logs goes to `debug.log` as well (+perf8).

    CM's own log is CMF's action pane: 200 lines, on screen only, gone with the
    session. The same line in `debug.log` comes back with `mods.bat` → 4, so a
    run says what each cycle did without a screenshot. Still gated on the Debug
    tab's category toggles, so with them off nothing is written. The key is
    printed as the key (a `debug_log` does not resolve localization), the values
    through a scratch global, the location and building as named scopes
    (docs/research/engine.md, «What a `debug_log` string reaches»). The three
    script values that read the globals back ship with the probe, in tools/probe/.
    """
    for name, (values, loc, bt) in _LOGGED.items():
        head = f"\n{name} = {{\n"
        at = text.index(head)
        call = text.index("\t\tcmf_log", at)
        shown = []
        mirror = ["\t\t# cm_dev_perf: the same line into debug.log"]
        for n in range(1, values + 1):
            arg = "$value$" if n == 1 else f"$value{n}$"
            mirror.append(f"\t\tset_global_variable = {{ name = cm_perf_log_v{n} value = {arg} }}")
            shown.append(f"[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v{n}')|2]")
        words = ["CM", "$cat$", "$action$"]
        if values and name != "cm_dbg_log_value":
            words.append("$arg1$")
        if bt:
            words.append("$arg2$")
        mirror.append('\t\tdebug_log = "%s"' % " ".join(words + shown))
        if bt:
            mirror.append("\t\tscope:cmf_log_bt ?= { debug_log_scopes = no }")
        if loc:
            mirror.append("\t\tscope:cmf_log_loc ?= { debug_log_scopes = no }")
        text = text[:call] + "\n".join(mirror) + "\n" + text[call:]
    return text


_LOOKUP = re.compile(r"is_key_in_variable_map\s*=\s*\{\s*name\s*=\s*(\S+)\s+target\s*=\s*(\S+)\s*\}")


def _guard_maps(text: str) -> tuple[str, int]:
    """`AND = { has_variable_map = M <lookup> }` for every lookup not already
    guarded within the two lines above it, as CM itself writes the guard.

    The AND keeps the meaning under a `NOT`, which reads its children as NOR.
    """
    lines = text.split("\n")
    n = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        out, pos = [], 0
        for match in _LOOKUP.finditer(line):
            above = "\n".join(lines[max(0, i - 2):i]) + line[:match.start()]
            if re.search(r"has_variable_map\s*=\s*%s(?!\S)" % re.escape(match.group(1)), above):
                continue
            out.append(line[pos:match.start()])
            out.append("AND = { has_variable_map = %s %s }" % (match.group(1), match.group(0)))
            pos = match.end()
            n += 1
        if out:
            lines[i] = "".join(out) + line[pos:]
    return "\n".join(lines), n


_DIRECT = re.compile(r"^([ \t]*)cmf_log(_value|_decimal_value)? = \{ action = (\S+)(?: value = (\S+))? \}[ \t]*$")
_SHOWN = "[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v1')|2]"


def _mirror_direct(text: str) -> tuple[str, int]:
    """The lines CM writes with CMF's own `cmf_log*` rather than its Debug-tab
    wrappers go to `debug.log` too (+perf10): the probes' summaries (roads,
    governors, military, the gold balance) and the setup stamps. His run of
    10-04 pressed the roads probe and `debug.log` had nothing to show for it.
    """
    lines = text.split("\n")
    out, n = [], 0
    for line in lines:
        out.append(line)
        match = _DIRECT.match(line)
        if not match:
            continue
        indent, kind, action, value = match.groups()
        if value:
            out.append("%sset_global_variable = { name = cm_perf_log_v1 value = %s }" % (indent, value))
            out.append('%sdebug_log = "CM %s %s"' % (indent, action, _SHOWN))
        else:
            out.append('%sdebug_log = "CM %s"' % (indent, action))
        n += 1
    return "\n".join(out), n


def _probe_road_gates(text: str) -> str:
    """The roads probe also says which of the plan's three gates holds (+perf10):
    a plan that fails one of them returns without a word, so «no roads» and
    «not allowed to plan roads» read the same."""
    head = "cm_ab_rd_probe = {\n\tsave_scope_as = cm_country\n"
    gates = (("cm_ab_master_active = yes", "master_active"),
             ("exists = var:cm_ab_roads_enabled", "roads_enabled"),
             ("has_advance = road_building", "advance_road_building"),
             ("exists = var:cm_ab_roads_proximity", "proximity_on"),
             ("exists = var:cm_ab_roads_market_access", "market_access_on"),
             ("exists = var:cm_ab_roads_capital", "capital_on"),
             ("modifier:overlord_blocked_from_building_roads = no", "not_blocked_by_overlord"))
    lines = ["\t# cm_dev_perf: the plan's gates, into debug.log"]
    for trigger, name in gates:
        lines.append('\tif = { limit = { %s } debug_log = "CM roads gate %s yes" }' % (trigger, name))
        lines.append('\telse = { debug_log = "CM roads gate %s NO" }' % name)
    return text.replace(head, head + "\n".join(lines) + "\n", 1)


def _roads_ignore_shortage(text: str) -> str:
    """A road may go ahead through the market's lumber, masonry and sand
    shortage when the player ticks «Строить при нехватке товаров» (+perf12,
    his ask 10-04: the choice, but his to control). The 05:53 probe: every gate
    yes, 26 corridors planned, all 26 «short», and the walk stops on the first
    without a word. Released CM has no such gate; a shortage only slows the
    work, the gold is paid at once either way."""
    old = "\t\t\tcm_market_has_construction_goods_for_road = yes\n"
    if text.count(old) != 1:
        raise SystemExit("roads: the try_build gate has changed shape")
    return text.replace(old, "\t\t\t# cm_dev_perf: the shortage gate unless the player lifted it\n"
                             "\t\t\tOR = {\n\t\t\t\texists = var:cm_ab_roads_ignore_shortage\n"
                             "\t\t\t\tcm_market_has_construction_goods_for_road = yes\n\t\t\t}\n")


def _register_ignore_shortage(text: str) -> str:
    """The checkbox behind `_roads_ignore_shortage`, after «Связь со столицей»
    and registered and synced the way CM registers that one."""
    sync = ("\tcmm_sync_bool_alias = {\n\t\tsetting = cm__ab_roads_capital\n"
            "\t\talias = cm_ab_roads_capital\n\t}\n")
    if text.count(sync) != 1:
        raise SystemExit("cmm: the capital checkbox has changed shape")
    text = text.replace(sync, sync + (
        "\n\t# cm_dev_perf: roads through a market shortage (+perf12)\n"
        "\tcmm_register_bool_setting = {\n\t\tmod_id = cm\n\t\tsetting_id = ab_roads_ignore_shortage\n"
        "\t\ttab_id = ab_roads\n\t\tgroup_id = ab_roads\n\t\tdefault_value = 0\n\t}\n"
        "\tcmm_sync_bool_alias = {\n\t\tsetting = cm__ab_roads_ignore_shortage\n"
        "\t\talias = cm_ab_roads_ignore_shortage\n\t}\n"))
    changed = "\t\tflag:cm__ab_roads_min_discount = {\n"
    if text.count(changed) != 1:
        raise SystemExit("cmm: the roads discount branch has changed shape")
    return text.replace(changed, (
        "\t\t# cm_dev_perf: tested afresh at every issue, so no replan\n"
        "\t\tflag:cm__ab_roads_ignore_shortage = {\n\t\t\tcmm_sync_bool_alias = {\n"
        "\t\t\t\tsetting = cm__ab_roads_ignore_shortage\n\t\t\t\talias = cm_ab_roads_ignore_shortage\n"
        "\t\t\t}\n\t\t}\n") + changed)


def _core_foreign_markets(text: str) -> str:
    """Core goods also work markets whose centre is someone else's when the
    player ticks «И на чужом рынке» (+perf14, 10-04). His run 06:23: masonry
    20 % dear, target not met, every probe gate yes but «we own the market
    centre» — the walk only visits `every_market_center_in_country`, so his
    Württemberg, in a market centred outside it, never got a quarry."""
    old = ("\t\tevery_market_center_in_country = {\n\t\t\tlimit = { cm_market_in_slice = yes }\n"
           "\t\t\tsave_scope_as = cm_ab_market\n\t\t\tscope:cm_country = { cm_ab_stage_core_good = yes }\n\t\t}\n")
    if text.count(old) != 1:
        raise SystemExit("core: the market walk has changed shape")
    present = old.replace("every_market_center_in_country", "every_market_present_in_country")
    indent = lambda s: "".join("\t" + l + "\n" for l in s.rstrip("\n").split("\n"))
    return text.replace(old, (
        "\t\t# cm_dev_perf: every market the country is in, when the player asked for it\n"
        "\t\tif = {\n\t\t\tlimit = { exists = var:cm_ab_core_foreign_markets }\n"
        + indent(present) + "\t\t}\n\t\telse = {\n" + indent(old) + "\t\t}\n"))


def _register_core_foreign(text: str) -> str:
    """The checkbox behind `_core_foreign_markets`, after the core goods target."""
    sync = ("\tcmm_sync_setting_alias = {\n\t\tsetting = cm__ab_core_target\n"
            "\t\talias = cm_ab_core_target\n\t}\n")
    if text.count(sync) != 1:
        raise SystemExit("cmm: the core target setting has changed shape")
    text = text.replace(sync, sync + (
        "\n\t# cm_dev_perf: core goods in markets centred elsewhere (+perf14)\n"
        "\tcmm_register_bool_setting = {\n\t\tmod_id = cm\n\t\tsetting_id = ab_core_foreign_markets\n"
        "\t\ttab_id = ab_core\n\t\tgroup_id = ab_core\n\t\tdefault_value = 0\n\t}\n"
        "\tcmm_sync_bool_alias = {\n\t\tsetting = cm__ab_core_foreign_markets\n"
        "\t\talias = cm_ab_core_foreign_markets\n\t}\n"))
    changed = "\t\tflag:cm__ab_core_target = {\n"
    if text.count(changed) != 1:
        raise SystemExit("cmm: the core target branch has changed shape")
    return text.replace(changed, (
        "\t\tflag:cm__ab_core_foreign_markets = {\n\t\t\tcmm_sync_bool_alias = {\n"
        "\t\t\t\tsetting = cm__ab_core_foreign_markets\n\t\t\t\talias = cm_ab_core_foreign_markets\n"
        "\t\t\t}\n\t\t}\n") + changed)


TRMM = "in_game/common/scripted_effects/cm_town_right_map_mode_effects.txt"
TRMM_GUIS = "in_game/common/scripted_guis/cm_town_right_map_mode_scripted_guis.txt"
PF_WINDOW = "in_game/gui/cm_pf_map_mode_window.gui"

_MARK = "\t\t\tset_variable = {\n\t\t\t\tname = cm_trmm_cov_v\n\t\t\t\tvalue = cm_trmm_version_value\n\t\t\t}\n"


def _mark_trmm_slices(text: str) -> str:
    """**The rights tooltip of conquered land is empty** (his run 10-04: new
    Moldavian locations under the rights map, «Подробности» and «Лучшие
    производства» with nothing under them, the colour right). The coverage the
    tooltip reads is stored on the province, and a province is the owner's
    slice of a province definition: land changing hands makes new slices that
    carry none of it, while the colour is read from the location and lives on
    (docs/PITFALLS.md, found in cm_maps 2026-09-19). CM recomputes once per
    save, behind `cm_trmm_stamp`. So every slice the pass writes is marked,
    and `cm_trmm_repair` recomputes the definitions with an unmarked slice —
    cm_maps' repair, the same names without the `b`."""
    written = ("\t\tevery_province_in_province_definition = {\n"
               "\t\t\tset_variable = {\n\t\t\t\tname = cm_trmm_cov_tools")
    empty = ("\telse = {\n\t\tevery_province_in_province_definition = {\n"
             "\t\t\tevery_location_in_province = {")
    if text.count(written) != 1 or text.count(empty) != 1:
        raise SystemExit("trmm: the coverage write has changed shape")
    text = text.replace(written, written.replace(
        "{\n\t\t\tset_variable", "{\n\t\t\t# cm_dev_perf: this slice holds the coverage\n" + _MARK + "\t\t\tset_variable", 1))
    text = text.replace(empty, empty.replace(
        "{\n\t\t\tevery_location_in_province", "{\n\t\t\t# cm_dev_perf: marked too, or every open recomputes it\n" + _MARK + "\t\t\tevery_location_in_province", 1))
    return text + (
        "\n# cm_dev_perf: recomputes exactly the definitions holding a slice without the\n"
        "# mark -- a change of owner made it, or the save predates the mark. One cheap\n"
        "# check per definition; run each time the rights map family is entered.\n"
        "cm_trmm_repair = {\n\tevery_province_definition = {\n\t\tlimit = {\n"
        "\t\t\tany_province_in_province_definition = {\n"
        "\t\t\t\tNOT = { has_variable = cm_trmm_cov_v }\n\t\t\t}\n\t\t}\n"
        "\t\tcm_trmm_recompute_province_definition = yes\n\t}\n}\n")


def _trmm_repair_gui(text: str) -> str:
    return text.rstrip("\n") + (
        "\n\n# cm_dev_perf: fired on entering the rights map family (cm_pf_map_mode_window).\n"
        "# No is_shown: the effect's per-definition check is the gate.\n"
        "cm_trmm_run_repair = {\n\teffect = {\n\t\tcm_trmm_repair = yes\n\t}\n}\n")


_TRMM_MODES = ["cm_best_town_right"] + ["cm_trmm_search_" + r for r in (
    "tooling", "jewelry", "naval", "textile", "weaponry", "book", "artisan", "brewing", "masonry")]


def _trmm_repair_driver(text: str) -> str:
    """The repair runs when the player enters the rights map family: `_show`
    fires on the hidden->shown edge, so switching between its modes costs one
    scan, and the refresh modes are in the gate so a repaint is not a re-entry.
    The window's root is always shown; this child adds ten-odd map-mode reads a
    frame."""
    modes = [m for m in _TRMM_MODES] + [m + "_refresh" for m in _TRMM_MODES]
    ors = [f"GetMapMode('{m}').IsActive" for m in modes]
    groups = ["Or5(" + ", ".join(ors[i:i + 5]) + ")" for i in range(0, 20, 5)]
    gate = f"And(GetPlayer.Exists, Or(Or({groups[0]}, {groups[1]}), Or({groups[2]}, {groups[3]})))"
    closing = text.rstrip().rfind("\n}")
    if closing < 0:
        raise SystemExit("cm_pf_map_mode_window.gui: no closing brace")
    driver = ("\n\t# cm_dev_perf: urban-rights repair driver (+perf16); see _mark_trmm_slices.\n"
              "\twidget = {\n\t\tsize = { 0 0 }\n\t\tvisible_at_creation = no\n"
              f"\t\tvisible = \"[{gate}]\"\n"
              "\t\tstate = {\n\t\t\tname = _show\n\t\t\tduration = 0.1\n"
              "\t\t\ton_finish = \"[GetScriptedGui('cm_trmm_run_repair').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]\"\n"
              "\t\t}\n\t}\n")
    return text[:closing] + "\n" + driver + text[closing:]


# The checkbox's words: CMM shows a missing key raw, so every language gets
# them, English where there is no translation.
SETTING_WORDS = {
    "cm__ab_roads_ignore_shortage": {
        "russian": ("Строить при нехватке товаров",
                    "Прокладывать дороги, даже когда на рынке не хватает пиломатериалов, камня или песка. "
                    "Золото списывается сразу, нехватка только замедляет стройку."),
        "english": ("Build Through Shortages",
                    "Lay roads even when the market is short of lumber, masonry or sand. "
                    "The gold is paid at once; a shortage only slows the work."),
    },
    "cm__ab_core_foreign_markets": {
        "russian": ("И на чужом рынке",
                    "Строить основные товары и на рынках, центр которых принадлежит другой державе, "
                    "если там есть ваши районы. Без этого Construction Manager работает только на рынках "
                    "со своим центром."),
        "english": ("Markets Centred Elsewhere Too",
                    "Build core goods in markets whose centre belongs to another country too, where you "
                    "own locations. Without it Construction Manager only works markets you hold the centre of."),
    },
}


def _write_setting_words() -> None:
    for folder in sorted((MOD / "main_menu/localization").iterdir()):
        lang = folder.name
        lines = [f"\ufeffl_{lang}:"]
        for key, words in SETTING_WORDS.items():
            name, desc = words.get(lang, words["english"])
            lines += [f' {key}_name: "{name}"', f' {key}_desc: "{desc}"', f' {key}: "{key}"']
        (folder / f"cm_perf_settings_l_{lang}.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


EDITS = (
    (WINDOW, "gate the building-type tree", _gate_the_tree),
    (WINDOW, "widen the first pass's instantiation window", perf._widen_first_pass),
    (WINDOW, "widen the upgrade refresh's instantiation window", _widen_refresh),
    (LOG, "mirror the Debug tab's log into debug.log", _mirror_log),
    (ROADS, "say the roads plan's gates in its probe", _probe_road_gates),
    (ROADS, "let roads go ahead through a market shortage", _roads_ignore_shortage),
    (CMM, "the checkbox for it", _register_ignore_shortage),
    (CORE, "work core goods in markets centred elsewhere", _core_foreign_markets),
    (CMM, "the checkbox for it", _register_core_foreign),
    (TRMM, "mark the province slices the rights pass writes, and the repair", _mark_trmm_slices),
    (TRMM_GUIS, "the repair's scripted gui", _trmm_repair_gui),
    (PF_WINDOW, "run the repair on entering the rights map", _trmm_repair_driver),
)


# **Raise with every change to what this mod ships** (his rule, 2026-09-27):
# `mods.bat` compares this number with the one installed in the game, and a
# refresh rewrites `.metadata` from here — a bump made by hand there is lost.
PERF_REVISION = 17


UNBUILT_HOOK = """\t\t\t\t\tcm_auto_expand_new_building_button_pl = {
\t\t\t\t\t\tignore_layout = yes
\t\t\t\t\t\tparentanchor = right|vcenter
\t\t\t\t\t\tposition = { -133 0 }
\t\t\t\t\t\tdatacontext = "[BuildingItem.GetBuildingType]"
\t\t\t\t\t}
"""

UNBUILT_PROBE = """\t\t\t\t\t# PROBE +perf17: A drawn, B has owner, C owner = Player.Self, D owner = GetPlayer, then the location's name
\t\t\t\t\thbox = {
\t\t\t\t\t\tignore_layout = yes
\t\t\t\t\t\tparentanchor = left|top
\t\t\t\t\t\tposition = { 230 3 }
\t\t\t\t\t\tspacing = 6
\t\t\t\t\t\ttext_single = { fontsize = 13 raw_text = "A" }
\t\t\t\t\t\ttext_single = { fontsize = 13 visible = "[Location.HasOwner]" raw_text = "B" }
\t\t\t\t\t\ttext_single = { fontsize = 13 visible = "[ObjectsEqual(Location.GetOwner, Player.Self)]" raw_text = "C" }
\t\t\t\t\t\ttext_single = { fontsize = 13 visible = "[ObjectsEqual(Location.GetOwner, GetPlayer)]" raw_text = "D" }
\t\t\t\t\t\ttext_single = { fontsize = 13 raw_text = "[Location.GetName]" }
\t\t\t\t\t}
\t\t\t\t\t# PROBE +perf17: the same button with no owner gate
\t\t\t\t\tcm_auto_expand_new_building_button = {
\t\t\t\t\t\tignore_layout = yes
\t\t\t\t\t\tparentanchor = right|vcenter
\t\t\t\t\t\tposition = { -160 0 }
\t\t\t\t\t\tdatacontext = "[BuildingItem.GetBuildingType]"
\t\t\t\t\t}
"""


def _probe_unbuilt_toggle(path: Path) -> None:
    text = path.read_text(encoding="utf-8-sig")
    if text.count(UNBUILT_HOOK) != 1:
        raise SystemExit(f"{path.name}: the unbuilt-row auto-expand hook is not there once")
    path.write_text("﻿" + text.replace(UNBUILT_HOOK, UNBUILT_HOOK + UNBUILT_PROBE), encoding="utf-8")


def metadata() -> str:
    """CM dev's own metadata, whole, with this mod's identity."""
    base = json.loads((SRC / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    version = base.get("version", "unknown")
    base["name"] = "Construction Manager Dev (perf)"
    base["id"] = "bag.cm_dev_perf"
    base["version"] = f"{version}+perf{PERF_REVISION}"
    base["short_description"] = (
        f"Construction Manager Dev {version} with its hidden building-type tree "
        "gated on the passes that need it, and its vanilla windows rebuilt on the 2026-10-01 beta. "
        "Load this INSTEAD of Construction Manager Dev, never alongside it."
    )
    base["supported_game_version"] = "1.*"
    return json.dumps(base, indent=4, ensure_ascii=False) + "\n"


def main() -> int:
    for name in ("in_game", "main_menu", ".metadata"):
        if (MOD / name).exists():
            shutil.rmtree(MOD / name)
    copied = 0
    for name in ("in_game", "main_menu"):
        if (SRC / name).exists():
            shutil.copytree(SRC / name, MOD / name)
            copied += sum(1 for p in (MOD / name).rglob("*") if p.is_file())
    for path, label, edit in EDITS:
        target = MOD / path
        text = target.read_text(encoding="utf-8-sig")
        patched = edit(text)
        if patched == text:
            raise SystemExit(f"{path}: {label} changed nothing")
        target.write_text("﻿" + patched.lstrip("﻿"), encoding="utf-8")
    _write_setting_words()
    # 10-01: CM Dev's copies of vanilla windows are Glorp UI's 1.3 layout and
    # break on the beta; each with a spec in tools/beta/ is rebuilt as the
    # beta's window plus CM's hooks (beta_windows.py).
    rebuilt = beta.rebuild(refs.GAME_GUI, BETA_SPECS, MOD / "in_game/gui")
    # 10-04: Glorp UI Río replaces three of the same windows and loads after
    # this mod, so his location window was Río's, which carries every CM hook
    # but the RGO button's auto-expand and auto-food toggles (his screenshot:
    # «Запас пищи в провинции» is Río's header; the toggles were gone). Those
    # three are Río's file plus the hooks it lacks (`beta_rio/`); this mod then
    # has to load after Río. Río's windows name nothing that only Glorp UI
    # defines but its ROI labels.
    try:
        rio = refs.mod("glorp.ui.rio") / "in_game/gui"
    except SystemExit:
        rio = None
    if rio is not None and rio.is_dir():
        for spec in sorted(BETA_RIO.glob("*.json")):
            window = spec.stem + ".gui"
            text = (rio / window).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
            text = beta.apply(text, json.loads(spec.read_text(encoding="utf-8")), window, refs.GAME_GUI)
            (MOD / "in_game/gui" / window).write_text("\ufeff" + text, encoding="utf-8")
            rebuilt = [w if w != window else window + " (on Glorp UI Río)" for w in rebuilt]
    # The beta's engine dropped `use_global_input_instance` (his log 10-02:
    # «not a valid widget/type/property»); commented out as the beta does.
    for path in (MOD / "in_game/gui").rglob("*.gui"):
        text = path.read_text(encoding="utf-8-sig")
        text, n = re.subn(r"^([ \t]*)(use_global_input_instance\s*=\s*yes)",
                          r"\1# \2  (removed from the engine, beta 10-01)", text, flags=re.M)
        if n:
            path.write_text("\ufeff" + text, encoding="utf-8")
    # The beta's `Country.GetTag` no longer returns a CString («[unregistered]» in
    # the 10-02 dumps, CString in 1.3), and the one CM gate that compares tags as
    # strings is the unbuilt-building button: his run 10-04, no auto-expand
    # toggle on unbuilt rows of a location's building list, while the
    # existing-building and build-location buttons, which compare objects, drew.
    # Compared as objects here too (+perf15).
    owner_gate = "EqualTo_string(Location.GetOwner.GetTag, GetPlayer.GetTag)"
    owner_gates = 0
    for path in (MOD / "in_game/gui").rglob("*.gui"):
        text = path.read_text(encoding="utf-8-sig")
        if owner_gate in text:
            owner_gates += text.count(owner_gate)
            path.write_text("\ufeff" + text.replace(owner_gate, "ObjectsEqual(Location.GetOwner, Player.Self)"),
                            encoding="utf-8")
    if not owner_gates:
        raise SystemExit("the tag-compare owner gate is gone from CM's windows; drop this pass")
    # PROBE (+perf17), one run then out: +perf15's object compare did not bring
    # the toggle back (his run 10-04 17:14, Тырговиште). Letters by the name say
    # which part of the gate holds, an ungated copy of the button 27 px left of
    # the gated one says whether the button draws at all there.
    _probe_unbuilt_toggle(MOD / "in_game/gui/production_lateralview.gui")
    # The beta added a native trigger `is_host`, CMF's own trigger's name; CM's
    # host gates (the classification among them, his run 10-02: never ran) go
    # to cmf_is_host, which cmf_dev_beta defines with CMF's body.
    for path in (MOD / "in_game/common").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig")
        text, n = re.subn(r"^([ \t]*(?:limit = \{ )?)is_host(\s*=\s*(?:yes|no)\b)",
                          r"\1cmf_is_host\2", text, flags=re.M)
        if n:
            path.write_text("\ufeff" + text, encoding="utf-8")
    # A lookup into a map the scope does not have yet is an error, not false
    # (his log 10-04: 1 243 of them, cm_rgob_cov and cm_rgob_sum the bulk). CM
    # guards most of its lookups with `has_variable_map`; the rest get the
    # same guard (+perf9).
    for path in (MOD / "in_game/common").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig")
        guarded, n = _guard_maps(text)
        mirrored, m = _mirror_direct(guarded)
        if n or m:
            path.write_text("\ufeff" + mirrored, encoding="utf-8")
    # The probe window (09-27) ships beside CM's files; its sources live in
    # tools/probe/ so this rebuild does not wipe them.
    for src in PROBE.rglob("*"):
        if src.is_file():
            dst = MOD / src.relative_to(PROBE)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("﻿" + metadata(), encoding="utf-8")
    thumb = SRC / ".metadata/thumbnail.png"
    if thumb.exists():
        shutil.copy2(thumb, MOD / ".metadata/thumbnail.png")
    print("cm_dev_perf: %d files copied from %s, %d edits applied, rebuilt on the beta: %s"
          % (copied, SRC.name, len(EDITS), ", ".join(rebuilt)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
