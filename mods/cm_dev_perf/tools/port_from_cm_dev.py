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

2. **The probe window is gone** (+perf45, 10-14, his ask). It said whether
   the classification had closed and which `is_host` the player passes; both
   were answered in game (TESTLOG 10-02 and 10-04: it closes, `cmf_is_host`
   holds). `tools/probe/` now carries only the script values the debug.log
   mirror reads (`cm_perf_log_values.txt`).

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

# cm_perf (retired 10-20) held the first-pass widening; its generator lives on as cm_perf_base.py
# two copies that drift apart.
_spec = importlib.util.spec_from_file_location(
    "cm_perf_port", Path(__file__).resolve().parent / "cm_perf_base.py"
)
perf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perf)

WINDOW = perf.WINDOW

_spec = importlib.util.spec_from_file_location(
    "beta_windows", Path(__file__).resolve().parent / "beta_windows.py")
beta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(beta)
BETA_SPECS = Path(__file__).resolve().parent / "beta"
RIO_SPECS = Path(__file__).resolve().parent / "rio_patch"
RIO_PATCH = refs.REPO / "mods/cm_rio_patch"

_spec = importlib.util.spec_from_file_location(
    "cm_perf_buildings", Path(__file__).resolve().parent / "buildings.py")
buildings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(buildings)

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


FOOD_13 = ("rice", "wheat", "maize", "potato", "livestock", "millet", "legumes", "fish", "olives",
           "fruit", "wild_game", "beeswax", "fur")


def _food_goods() -> list[str]:
    """Every raw good the game gives food to (`food = ` in goods/*.txt), in file order."""
    out = []
    for f in sorted((refs.GAME / "in_game/common/goods").glob("*.txt")):
        text = re.sub(r"#[^\n]*", "", f.read_text(encoding="utf-8-sig"))
        for m in re.finditer(r"(?m)^(\w+)\s*=\s*\{", text):
            depth, i = 1, m.end()
            while depth:
                depth += (text[i] == "{") - (text[i] == "}")
                i += 1
            body = text[m.end():i]
            food = re.search(r"\bfood\s*=\s*([\d.]+)", body)
            if food and float(food.group(1)) > 0 and "category = raw_material" in body:
                out.append(m.group(1))
    if not set(FOOD_13) <= set(out):
        raise SystemExit("food goods: one of CM's 13 lost its food in the game's files")
    return out


def _food_rgo_trigger(text: str) -> str:
    """CM names its 13 food goods by hand; 1.4.2 gives food to wool and horses
    too (pastoral locations feed themselves). The list is the game's own now:
    every raw good with `food` (+perf46, his word 10-20: «мод сам определяет, что
    даёт еду»)."""
    goods = _food_goods()
    for tabs in ("\t\t\t", "\t\t"):
        old = "".join(f"{tabs}raw_material = goods:{g}\n" for g in FOOD_13)
        if old in text:
            new = "".join(f"{tabs}raw_material = goods:{g}\n" for g in goods)
            return text.replace(old, new, 1)
    raise SystemExit("food goods: CM's 13-good list has changed shape")


def _food_rgo_list(text: str) -> str:
    goods = _food_goods()
    line = "\tadd_to_variable_list = {{ name = cm_auto_food_rgo_types_list target = goods:{} }}\n"
    old = "".join(line.format(g) for g in FOOD_13)
    if text.count(old) != 1:
        raise SystemExit("food goods: cm_auto_food_rgo_types_list has changed shape")
    return text.replace(old, "".join(line.format(g) for g in goods), 1)


def _gov_other_sources(text: str) -> str:
    """The governor plan leaves alone a location that already holds another
    proximity source (+perf46, his word 10-20): he put the Italian
    administration centre on a good spot and CM put a local governor on the
    same location right after, and the second source's proximity burned for
    nothing. Game 1.4.2 says the same in both governors' `allow`
    (`has_proximity_source_building = no`, capital_buildings.txt): the sources
    are mutually exclusive now. A location whose own source is a governor keeps
    its seat, which the plan may still re-score."""
    old = "cm_gov_site_blocks_land_governor = {\n\thas_building = building_type:seljuk_mint\n}\n"
    if text.count(old) != 1:
        raise SystemExit("governor triggers: cm_gov_site_blocks_land_governor has changed shape")
    new = ("cm_gov_site_blocks_land_governor = {\n\tOR = {\n\t\thas_building = building_type:seljuk_mint\n"
           "\t\tcm_gov_site_has_other_source = yes\n\t}\n}\n\n"
           "# cm_dev_perf +perf46: another proximity source already stands here (the Italian\n"
           "# administration centre, a lieutenancy, a mod's): 1.4.2 lets no governor join it.\n"
           "# Root is the location.\n"
           "cm_gov_site_has_other_source = {\n\thas_proximity_source_building = yes\n"
           "\tNOT = { has_building = building_type:local_governor }\n"
           "\tNOT = { has_building = building_type:naval_governor }\n}\n")
    text = text.replace(old, new, 1)
    naval = "cm_gov_site_is_naval = {\n\tNOT = { is_connected_to_through_realm = owner.capital }\n"
    if text.count(naval) != 1:
        raise SystemExit("governor triggers: cm_gov_site_is_naval has changed shape")
    return text.replace(naval, naval + "\tcm_gov_site_has_other_source = no # cm_dev_perf +perf46\n", 1)


# CM turns the game's own building automation off on load and on a change of
# country. +perf24..+perf31 also turned it off every month; he had that taken
# out 10-06 («Убери выключение каждый месяц, зачем это?» — the ask of 10-04 was
# a worry, not a want): what he switches on mid-game stays on.

def _food_pass_location(text: str) -> str:
    """The auto-food drain prices against scope:cm_location and never saves it.

    `cm_food_gold_threshold` reaches Glorp's RGO cost, which reads
    scope:cm_location; the drain saves the location only as cm_q_pass_loc, so
    every staged food building wrote four errors to error.log (608 lines in the
    10-05 03:43 run). Released CM has the same drain, so the error is CM's own.
    """
    pairs = (("\t\t\tvariable = cm_q_food_locations\n\t\t\tsave_temporary_scope_as = cm_q_pass_loc\n",
              "\t\t\tsave_temporary_scope_as = cm_location\n"),
             ("\t\t\tvariable = cm_q_food_rgo_locations\n",
              "\t\t\tsave_temporary_scope_as = cm_location\n"))
    for old, add in pairs:
        if text.count(old) != 1:
            raise SystemExit("food drain: the location loop has changed shape")
        text = text.replace(old, old + "\t\t\t# cm_dev_perf: the cost values read it\n" + add)
    return text


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
    "cm__ab_food_horizon": {
        "russian": ("Срок найма для RGO, лет",
                    "Сколько лет автостройка готова ждать, пока прирост населения заполнит новый уровень RGO еды "
                    "рабочими или рабами. Уровень строится, только если нехватку закроет прирост за этот срок. "
                    "Меньше — строит реже, но уровни не стоят пустыми."),
        "english": ("Hiring Horizon for RGOs, Years",
                    "How many years Auto-Build will wait for population growth to staff a new food RGO level "
                    "with laborers or slaves. A level is built only if growth covers the shortfall within this "
                    "time. Lower builds less often, but levels do not stand empty."),
    },
    "cm__ab_production_horizon": {
        "russian": ("Срок найма, лет",
                    "За сколько лет повышение должно закрыть уже начатую нехватку людей нужного типа, прежде чем "
                    "автостройка начнёт ещё один уровень производственного здания или RGO. Первый уровень "
                    "строится всегда, если свободных крестьян хватает на нехватку всех сословий плюс 500. "
                    "Меньше — нехватки не копятся."),
        "english": ("Hiring Horizon, Years",
                    "How many years promotion may take to fill a shortfall already started before Auto-Build "
                    "starts another level of a production building or RGO. A first level is built whenever the "
                    "free peasants cover every class's shortfall plus 500. Lower keeps shortfalls from piling up."),
    },
    "cm__ae_horizon": {
        "russian": ("Срок найма для авторасширения, лет",
                    "То же, что «Срок найма» автостройки, для авторасширения зданий и RGO: за сколько лет повышение "
                    "должно закрыть уже начатую нехватку людей, прежде чем строить следующий уровень."),
        "english": ("Hiring Horizon for Auto-Expand, Years",
                    "As Auto-Build's hiring horizon, for auto-expanding buildings and RGOs: how many years "
                    "promotion may take to fill a shortfall already started before the next level."),
    },
    "cm__af_horizon": {
        "russian": ("Срок найма для житниц, лет",
                    "То же, что «Срок найма» автостройки, для авторасширения еды (житниц): за сколько лет повышение "
                    "должно закрыть уже начатую нехватку людей, прежде чем строить следующий уровень."),
        "english": ("Hiring Horizon for Auto-Food, Years",
                    "As Auto-Build's hiring horizon, for auto-food: how many years promotion may take to fill a "
                    "shortfall already started before the next level."),
    },
    "cm__ab_food_take_manual": {
        "russian": ("Брать житницы, включённые вручную",
                    "Когда авторасширение еды выключено, автостройка строит и в районах, где житница включена "
                    "вручную, — из бюджета продовольствия, по правилам этой вкладки."),
        "english": ("Take Hand-Enabled Breadbaskets",
                    "While auto-food is off, Auto-Build also builds in locations whose breadbasket you enabled "
                    "by hand, from the food budget and by this tab's rules."),
    },
}


CUSTOM = "in_game/common/scripted_effects/cm_ab_custom_effects.txt"
SEED = "in_game/common/scripted_effects/cm_game_load_setup_effects.txt"
LOOKUPS = "in_game/common/scripted_effects/cm_cmm_custom_effects.txt"
AUTO_EXPAND = "in_game/gui/cm_auto_expand_button.gui"


def _unbuilt_toggle_slot(text: str) -> str:
    """Glorp UI Río places the unbuilt-row toggle itself (production_lateralview.gui:
    `parentanchor = right|vcenter`, `position = { -133 0 }`), which on the beta's row is the
    income column (his screenshot 10-04 17:42, the toggle over «+0.44 / +0.15»). From the
    right the row is margin 8, build button 110, spacing 6, margin 3, income 60, 5, efficiency
    70, 5, then an empty 24 px slot. Río's file is his and stays his (10-04: «не хотелось бы,
    чтобы наш мод перезаписывал окна интерфейса glorp»), so the type does the moving: it is
    156 wide and anchored by its right edge, which puts its left edge, and the toggle drawn
    there, 289 px from the row's right. Transparent, so the income and efficiency columns
    under it keep their tooltips. The beta window's own instance sets its size and anchor
    back (beta/production_lateralview.json)."""
    old = ("\ttype cm_auto_expand_new_building_button_pl = widget {\n\t\tsize = { 20 20 }\n"
           "\t\tvisible = \"[And(Location.HasOwner, EqualTo_string(Location.GetOwner.GetTag, GetPlayer.GetTag))]\"\n"
           "\t\tcm_auto_expand_new_building_button = { parentanchor = center widgetanchor = center }\n")
    new = ("\ttype cm_auto_expand_new_building_button_pl = widget {\n"
           "\t\t# cm_dev_perf: 156 wide, right-anchored, so Río's -133 lands the toggle at -289.\n"
           "\t\tsize = { 156 20 }\n\t\twidgetanchor = right|vcenter\n\t\talwaystransparent = yes\n"
           "\t\tvisible = \"[And(Location.HasOwner, EqualTo_string(Location.GetOwner.GetTag, GetPlayer.GetTag))]\"\n"
           "\t\tcm_auto_expand_new_building_button = { parentanchor = left|vcenter widgetanchor = left|vcenter }\n")
    if text.count(old) != 1:
        raise SystemExit("cm_auto_expand_button.gui: the unbuilt-row type is not as expected")
    return text.replace(old, new)


def _split_glorp_shared() -> int:
    """CM ships files under Glorp UI's own names (`glorpui_construction_manager_scripted_gui.txt`,
    `glorpui_shared_l_<lang>.yml`), and with this mod above Río it is Río's copy of each that
    loads, so what only CM's copy has would be gone while CM's ROI templates still name it. Those
    parts move to files of this mod's own name: present whichever copy wins, defined once."""
    sgui = MOD / "in_game/common/scripted_guis/glorpui_construction_manager_scripted_gui.txt"
    text = sgui.read_text(encoding="utf-8-sig")
    m = re.search(r"(?ms)^# True when the ROI figures should carry[^\n]*\n^glorpui_roi_indirect_active = \{.*?^\}\n?", text)
    if not m:
        raise SystemExit("glorpui_roi_indirect_active: not where CM keeps it")
    sgui.write_text("\ufeff" + text[:m.start()].rstrip("\n") + "\n" + text[m.end():], encoding="utf-8")
    (sgui.parent / "cm_perf_glorp_shared_scripted_gui.txt").write_text("\ufeff" + m.group(0), encoding="utf-8")
    try:
        rio = refs.mod("glorp.ui.rio") / "main_menu/localization"
    except SystemExit:
        return 0
    moved = 0
    for folder in sorted((MOD / "main_menu/localization").iterdir()):
        lang = folder.name
        ours = folder / f"glorpui_shared_l_{lang}.yml"
        theirs = rio / lang / f"glorpui_shared_l_{lang}.yml"
        if not ours.exists() or not theirs.exists():
            continue
        has = set(re.findall(r"(?m)^ ([A-Za-z0-9_.]+):", theirs.read_text(encoding="utf-8-sig")))
        keep, move = [], []
        for line in ours.read_text(encoding="utf-8-sig").splitlines():
            key = re.match(r" ([A-Za-z0-9_.]+):", line)
            (move if key and key.group(1) not in has else keep).append(line)
        ours.write_text("\ufeff" + "\n".join(keep) + "\n", encoding="utf-8")
        (folder / f"cm_perf_glorp_shared_l_{lang}.yml").write_text(
            "\ufeff" + f"l_{lang}:\n" + "\n".join(move) + "\n", encoding="utf-8")
        moved += len(move)
    return moved


def _write_setting_words() -> None:
    for folder in sorted((MOD / "main_menu/localization").iterdir()):
        lang = folder.name
        lines = [f"\ufeffl_{lang}:"]
        for key, words in SETTING_WORDS.items():
            name, desc = words.get(lang, words["english"])
            lines += [f' {key}_name: "{name}"', f' {key}_desc: "{desc}"', f' {key}: "{key}"']
        (folder / f"cm_perf_settings_l_{lang}.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


# The governor placement map and CM's own governor planner share one set of
# location variables (cm_gf_*). While the planner searches (phase 3 of
# cm_gov_reorg_tick, every month), its run writes them at Quick/Fastest accuracy
# with the committed sites as sources, so most of the map reads «skipped» and
# draws black, and the run's finalize marks it fresh for four years: his run
# 10-05, «нажимаю — показывает отлично, проходит месяц — всё чернеет». The road
# planner already stands aside while the map is open (cm_ab_rd_plan_proximity);
# the governor planner does not. +perf27: the player's view is saved before the
# planner's first search of a tick and put back at the end of the tick. The
# month the planner moves on to classify (phase 4) keeps its own scores, which
# classify reads for the seats; the view comes back after classify. A run of the
# player's own drops the saved view, being newer.
PF_VIEW_VARS = ("score", "avg", "taxgain", "popgain", "top", "localmax", "skip", "inelig", "nogain")
PF_VIEW = "in_game/common/scripted_effects/cm_perf_pf_view_effects.txt"


def _pf_view_effects() -> str:
    save = "".join(
        f"\t\t\tremove_variable = cm_perf_pfv_{v}\n"
        f"\t\t\tif = {{ limit = {{ has_variable = cm_gf_{v} }} set_variable = {{ name = cm_perf_pfv_{v} value = var:cm_gf_{v} }} }}\n"
        for v in PF_VIEW_VARS)
    restore = "".join(
        f"\t\t\t\tremove_variable = cm_gf_{v}\n"
        f"\t\t\t\tif = {{ limit = {{ has_variable = cm_perf_pfv_{v} }} set_variable = {{ name = cm_gf_{v} value = var:cm_perf_pfv_{v} }} }}\n"
        f"\t\t\t\tremove_variable = cm_perf_pfv_{v}\n"
        for v in PF_VIEW_VARS)
    drop = "".join(f"\t\tremove_variable = cm_perf_pfv_{v}\n" for v in PF_VIEW_VARS)
    return f"""﻿# Generated by mods/cm_dev_perf/tools/port_from_cm_dev.py; not to be edited by hand.
# The player's governor placement map, kept from CM's own governor planner (+perf27): the
# planner's monthly search writes the same cm_gf_* the map draws. See _pf_view_effects.

# Root is the country. Before the planner's first search of a tick.
cm_perf_pf_view_save = {{
	if = {{
		limit = {{
			is_ai = no
			NOT = {{ has_variable = cm_perf_pfv_saved }}
		}}
		set_variable = {{ name = cm_perf_pfv_saved value = 1 }}
		remove_variable = cm_perf_pfv_view_g
		remove_variable = cm_perf_pfv_view_c
		remove_variable = cm_perf_pfv_fresh_g
		if = {{ limit = {{ exists = var:cm_pf_view_g }} set_variable = {{ name = cm_perf_pfv_view_g value = 1 }} }}
		if = {{ limit = {{ exists = var:cm_pf_view_c }} set_variable = {{ name = cm_perf_pfv_view_c value = 1 }} }}
		if = {{ limit = {{ exists = var:cm_pf_fresh_g }} set_variable = {{ name = cm_perf_pfv_fresh_g value = 1 }} }}
		every_owned_location = {{
{save}		}}
	}}
}}

# Root is the country. At the end of every planner tick. The viewed-mode flags always come
# back; the scores wait while the planner is on classify (phase 4), which reads its own.
cm_perf_pf_view_restore = {{
	if = {{
		limit = {{ has_variable = cm_perf_pfv_saved }}
		if = {{
			limit = {{ exists = var:cm_perf_pfv_view_g }}
			set_variable = {{ name = cm_pf_view_g value = 1 }}
		}}
		if = {{
			limit = {{ exists = var:cm_perf_pfv_view_c }}
			set_variable = {{ name = cm_pf_view_c value = 1 }}
		}}
		# The planner's scores stand until classify, which strips them with the fresh flag; the
		# view comes back at the end of that tick.
		if = {{
			limit = {{ NOT = {{ var:cm_gov_phase = 4 }} }}
			every_owned_location = {{
{restore}			}}
			if = {{
				limit = {{ exists = var:cm_perf_pfv_fresh_g }}
				set_variable = {{ name = cm_pf_fresh_g value = 1 days = 1460 }}
			}}
			else = {{
				remove_variable = cm_pf_fresh_g
			}}
			if = {{
				limit = {{ exists = var:cm_pf_mode_open }}
				set_variable = {{ name = cm_pf_repaint value = 1 }}
			}}
			cm_perf_pf_view_drop = yes
		}}
	}}
}}

# Root is the country. A run of the player's own is newer than anything saved.
cm_perf_pf_view_drop = {{
	remove_variable = cm_perf_pfv_saved
	remove_variable = cm_perf_pfv_view_g
	remove_variable = cm_perf_pfv_view_c
	remove_variable = cm_perf_pfv_fresh_g
	every_owned_location = {{
{drop}	}}
}}
"""


def _pf_view_save_hook(text: str) -> str:
    head = "cm_gov_reorg_search_run = {\n"
    if text.count(head) != 1:
        raise SystemExit("governor plan: cm_gov_reorg_search_run has changed shape")
    return text.replace(head, head + "\t# cm_dev_perf: the player's map, before this run writes over it (+perf27)\n"
                                     "\tcm_perf_pf_view_save = yes\n", 1)


def _pf_view_restore_hook(text: str) -> str:
    tail = ("\t\tset_variable = { name = cm_gov_hold value = 1 }\n\t}\n}\n\n"
            "# Root is the country, scope:cm_country set.\ncm_gov_reorg_try_start = {\n")
    if text.count(tail) != 1:
        raise SystemExit("governor plan: the end of cm_gov_reorg_tick has changed shape")
    return text.replace(tail, tail.replace(
        "\t}\n}\n\n", "\t}\n\t# cm_dev_perf: the player's map back (+perf27)\n\tcm_perf_pf_view_restore = yes\n}\n\n", 1), 1)


def _pf_view_drop_hook(text: str) -> str:
    head = "cm_pf_prep_core = {\n\tsave_scope_as = cm_pf_c\n"
    if text.count(head) != 1:
        raise SystemExit("finder: cm_pf_prep_core has changed shape")
    return text.replace(head, head + (
        "\t# cm_dev_perf: a run of the player's own supersedes a view saved from the planner (+perf27)\n"
        "\tif = {\n\t\tlimit = {\n\t\t\thas_variable = cm_perf_pfv_saved\n"
        "\t\t\tNOT = { exists = var:cm_gov_valid_only }\n"
        "\t\t\tNOT = { exists = var:cm_ab_rd_plan_active }\n\t\t}\n"
        "\t\tcm_perf_pf_view_drop = yes\n\t}\n"), 1)


# The refresh button on CMF's bar shows while cm_pf_mode_open is set, and only
# the map window's close driver clears it — when neither finder mode nor its
# hidden twin is active. His run 10-05: the button can vanish after a use. Not
# measured why; the repaint swaps the map through the hidden twin, which is the
# one moment the close driver could see neither. +perf27: the swap re-asserts
# the open flag once it has settled, and the close and the click say so in
# debug.log, so the next run tells whether the close fired.
def _pf_reassert(text: str) -> str:
    for mode, state, prep in (("cm_governor_finder", "cm_pf_gf_restore", "cm_pf_prep_gov"),
                              ("cm_capital_finder", "cm_pf_cf_restore", "cm_pf_prep_cap")):
        old = (f"\t\t\tname = {state}\n\t\t\tduration = 0.1\n"
               f"\t\t\ton_finish = \"[GetMapMode('{mode}').SetMapMode]\"\n\t\t}}\n")
        if text.count(old) != 1:
            raise SystemExit(f"finder window: {state} has changed shape")
        new = (f"\t\t\tname = {state}\n\t\t\tduration = 0.1\n\t\t\tnext = {state}_reassert\n"
               f"\t\t\ton_finish = \"[GetMapMode('{mode}').SetMapMode]\"\n\t\t}}\n"
               f"\t\t# cm_dev_perf: the open flag back once the swap has settled (+perf27)\n"
               f"\t\tstate = {{\n\t\t\tname = {state}_reassert\n\t\t\tduration = 0.5\n"
               f"\t\t\ton_finish = \"[GetScriptedGui('{prep}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]\"\n\t\t}}\n")
        text = text.replace(old, new, 1)
    return text


def _pf_log_close(text: str) -> str:
    old = "cm_pf_clear_mode_open = {\n\teffect = {\n"
    if text.count(old) != 1:
        raise SystemExit("finder guis: cm_pf_clear_mode_open has changed shape")
    return text.replace(old, old + "\t\tdebug_log = \"CM pf: finder map closed, refresh button hidden\"\n", 1)


def _pf_log_click(text: str) -> str:
    old = "\t\tflag:cm_pf_refresh = {\n\t\t\tcm_pf_force_refresh = yes\n"
    if text.count(old) != 1:
        raise SystemExit("cmm callbacks: the refresh button's branch has changed shape")
    return text.replace(old, "\t\tflag:cm_pf_refresh = {\n\t\t\tdebug_log = \"CM pf: refresh button clicked\"\n"
                             "\t\t\tcm_pf_force_refresh = yes\n", 1)


# CM Dev links the automation card's «Gold to Save» slider to its own gold
# reserve both ways. The pull (slider into the reserve, every 0.25 s while the
# card is open) is the only way anything but CM's own setting writes the
# player's `cm_minimum_gold`, and his run 10-05: reserve 2000, the slider shot to
# its maximum (1 000 000+), CM took that number and built nothing. CM switches the
# game's own building automation off on load, so that slider steers nothing
# unless he switches it back on; the pull is cut, the push (CM's setting shown on the
# slider) stays. CM 2.2.12, the release, has no link at all.
RESERVE_GUIS = "in_game/common/scripted_guis/cm_cmm_custom_scripted_gui.txt"


def _cut_reserve_pull(text: str) -> str:
    old = ("\t\tif = {\n\t\t\tlimit = {\n"
           "\t\t\t\tNOT = { has_variable = cm_gold_reserve_from_cmm }\n")
    if text.count(old) != 1:
        raise SystemExit("reserve guis: cm_gold_reserve_changed has changed shape")
    return text.replace(old, "\t\tif = {\n\t\t\tlimit = {\n"
                             "\t\t\t\talways = no # cm_dev_perf: the slider no longer writes CM's reserve (+perf31)\n"
                             "\t\t\t\tNOT = { has_variable = cm_gold_reserve_from_cmm }\n", 1)


# The food subsidy checkbox subsidizes only what auto-food itself approved, the
# cycle after it stands. His run 10-06: a farming village in an auto-food
# location stood without workers, the country's building list showing the red
# «!» on farms, and the box ticked. Most of them CM never built, and a farm
# built later is never subsidized by the game either. +perf33: with the box
# ticked, every CM cycle (monthly) subsidizes each of the player's farming
# villages that is unprofitable or has no one employed — his words: «ежемесячной
# проверкой (есть ли фермы с убытком?)… включает в этом месте субсидии на все
# фермы». A location holds one building of a type per owner, so «every farm
# there» is that one. Only farms: «вся эта тема болит только на фермах».
FOOD = "in_game/common/scripted_effects/cm_food_auto_build_effects.txt"


def _subsidize_idle_farms(text: str) -> str:
    old = "cm_food_apply_subsidies = {\n"
    if text.count(old) != 1:
        raise SystemExit("food subsidies: cm_food_apply_subsidies has changed shape")
    add = ("\t# cm_dev_perf +perf33: every farm standing idle or at a loss, not only auto-food's own\n"
           "\tif = {\n"
           "\t\tlimit = { has_variable = cm_ab_food_subsidize }\n"
           "\t\tevery_owned_building = {\n"
           "\t\t\tlimit = {\n"
           "\t\t\t\tbuilding_type = building_type:farming_village\n"
           "\t\t\t\tis_subsidized = no\n"
           "\t\t\t\tOR = {\n"
           "\t\t\t\t\tis_not_profitable = yes\n"
           "\t\t\t\t\tbuilding_employed_amount <= 0\n"
           "\t\t\t\t}\n"
           "\t\t\t}\n"
           "\t\t\tset_subsidized = yes\n"
           "\t\t}\n"
           "\t}\n")
    return text.replace(old, old + add, 1)


# Auto-food counted every unemployed pop at the location, whatever its type,
# against a building that hires one type. His run 13.10 (1.4.1): a farming
# village location 3 500 workers short got one more farming village and stood
# 4 300 short — unemployed nobles, burghers or laborers let CM build peasant
# jobs. The unemployed count also misses a level that stands unstaffed. +perf42:
# each option asks its own pool, the pop count minus every job of that type
# already built or building (CM's own `cm_location_<type>_available`, which
# the rest of CM uses for the same question). The pool comes from the game's
# `pop_type` of the building; the RGO's is laborers or slaves, as CM's
# `cm_location_laborers_or_slaves_available` already counts it.
FOOD_TRIGGERS = "in_game/common/scripted_triggers/cm_food_auto_build_triggers.txt"
_FOOD_POOLS = {
    "peasants": "cm_location_peasants_available",
    "laborers": "cm_location_laborers_or_slaves_available",
    "slaves": "cm_location_laborers_or_slaves_available",
}


def _food_building_pools() -> dict[str, str]:
    pools = {}
    for path in sorted((refs.GAME_COMMON / "building_types").glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        for m in re.finditer(r"(?m)^(\w+) = \{\n(.*?)^\}", text, re.S):
            pt = re.search(r"(?m)^\tpop_type = (\w+)", m.group(2))
            if pt:
                pools[m.group(1)] = pt.group(1)
    return pools


def _food_pops_by_type(text: str) -> str:
    old_macro = ("\t$target$ = { save_temporary_scope_as = cm_food_pops_type }\n"
                 "\tcm_location_total_unemployed_pops >= scope:cm_food_pops_type.employment_size\n")
    old_fill = "\tNOT = { cm_location_total_unemployed_pops > 0 }\n"
    old_rgo = "\tcm_location_total_unemployed_pops >= 1\n"
    old_why = ("# Auto-food gates on the pops a location has left over of any type, never on the type a building\n"
               "# draws. Open jobs are what speed promotion, and a location reaches its population cap long before\n"
               "# it reaches its building caps, so holding a level back until the right type has promoted costs\n"
               "# more food than it saves.\n"
               "# Root is the location. Expects $target$ = a building_type.\n")
    for old in (old_macro, old_fill, old_rgo, old_why):
        if text.count(old) != 1:
            raise SystemExit("food pops: cm_food_auto_build_triggers has changed shape")
    text = text.replace(old_why,
                        "# CM gated auto-food on the pops left over of any type, on purpose: open jobs speed promotion.\n"
                        "# cm_dev_perf +perf42 gates on the type the building draws instead, by the owner's call 13.10:\n"
                        "# levels built on other types' unemployment stood short of workers (3 500 laborers short, then\n"
                        "# 4 300). Root is the location. Expects $target$ = a building_type and $pool$ = the script\n"
                        "# value counting free places of its pop type.\n", 1)
    text = text.replace(old_macro,
                        "\t$target$ = { save_temporary_scope_as = cm_food_pops_type }\n"
                        "\t# cm_dev_perf +perf42: a free place of the building's own pop type, jobs already built counted\n"
                        "\t$pool$ > 0\n", 1)
    text = text.replace(old_fill,
                        "\t# cm_dev_perf +perf42: no food pool has room, unemployed of other types aside\n"
                        "\tNOT = {\n\t\tOR = {\n"
                        "\t\t\tcm_location_peasants_available > 0\n"
                        "\t\t\tcm_location_laborers_or_slaves_available > 0\n"
                        "\t\t}\n\t}\n", 1)
    text = text.replace(old_rgo,
                        "\t# cm_dev_perf +perf42: the RGO's own pool, its levels and the laborer jobs counted\n"
                        "\tcm_location_laborers_or_slaves_available > 0\n", 1)
    game = _food_building_pools()
    calls = list(re.finditer(r"cm_food_location_has_pops_for = \{ target = building_type:(\w+) \}", text))
    if len(calls) != 4:
        raise SystemExit(f"food pops: expected four options, found {len(calls)}")
    for m in reversed(calls):
        pop = game.get(m.group(1))
        if pop not in _FOOD_POOLS:
            raise SystemExit(f"food pops: {m.group(1)} hires {pop}, which no pool here counts")
        text = (text[:m.start()]
                + f"cm_food_location_has_pops_for = {{ target = building_type:{m.group(1)} pool = {_FOOD_POOLS[pop]} }}"
                + text[m.end():])
    return text


# The same run, his correction 13.10 20:43: what grew was the livestock RGO,
# and the shortage was of laborers. Staging lets a food RGO in on one free
# worker; the drain then builds level after level up to the RGO's size cap,
# as many as the queue slots and the gold allow, with no pop read at all.
# +perf42: the drain stops when the laborer-or-slave pool has no free level
# left. The pool counts the RGO's levels under construction, so each level
# this loop builds takes one off it. Auto-Build's own food RGO loop is not
# touched: it gates on the six-year promotion projection by design.
APPROVAL = "in_game/common/scripted_effects/cm_queue_approval_effects.txt"


def _food_rgo_drain_pops(text: str) -> str:
    old = ("\t\t\t\t\t\tcm_get_max_rgo_workers_floor > { value = cm_modifier_rgo_level add = cm_get_rgos_under_construction }\n"
           "\t\t\t\t\t\tcm_check_country_gold_above = { threshold = cm_food_gold_threshold_plus_planned_spend }\n")
    if text.count(old) != 1:
        raise SystemExit("food rgo drain: the level loop has changed shape")
    return text.replace(old, old + "\t\t\t\t\t\t# cm_dev_perf +perf42: a level only for laborers or slaves who are there\n"
                                   "\t\t\t\t\t\tcm_location_laborers_or_slaves_available > 0\n", 1)


# His words 13.10 20:52, on Auto-Build's food tab (the system paying from its own
# budget): the six years it lets population growth take to staff a food RGO level
# become a slider, 1-10 years, 6 by default; and a checkbox lets it take the
# locations whose breadbasket he enabled by hand, while auto-food itself is off.
# +perf43. The six years stay everywhere else in CM: only this tab's RGO room and
# the level loop under it read the slider, and the loop now stops when the next
# level would not be covered (it built up to the size cap before).
AB_FOOD = "in_game/common/scripted_effects/cm_ab_food_effects.txt"
AB_FOOD_VALUES = "in_game/common/script_values/cm_perf_ab_food_values.txt"
AB_FOOD_VALUES_TEXT = """\ufeff# Generated by mods/cm_dev_perf/tools/port_from_cm_dev.py; not to be edited by hand.
# Auto-Build food's hiring horizon (+perf43): cm_location_rgo_promotion_buffer_slack with the
# slider's years in place of CM's fixed six. Root is the location.
cm_perf_ab_food_horizon_months = {
	value = 72
	if = {
		limit = { owner = { exists = var:cm_ab_food_horizon } }
		value = owner.var:cm_ab_food_horizon
		multiply = 12
	}
}

cm_perf_ab_food_rgo_slack = {
	value = cm_location_laborers_or_slaves_available
	add = {
		value = cm_location_fill_rate_for_laborers_or_slaves
		multiply = cm_perf_ab_food_horizon_months
	}
}
"""


def _ab_food_horizon(text: str) -> str:
    room = "\t\t\t\t\t\tcm_location_rgo_promotion_buffer_slack >= 0\n"
    loop = ("\t\t\t\t\t\t\tcm_get_max_rgo_workers_floor > { value = cm_modifier_rgo_level add = cm_get_rgos_under_construction }\n"
            "\t\t\t\t\t\t\tcm_ab_can_afford_rgo = { POOL = cm_ab_pool_food }\n")
    for old in (room, loop):
        if text.count(old) != 1:
            raise SystemExit("ab food: the RGO room or its level loop has changed shape")
    text = text.replace(room, "\t\t\t\t\t\t# cm_dev_perf +perf43: the tab's own horizon\n"
                              "\t\t\t\t\t\tcm_perf_ab_food_rgo_slack > 0\n", 1)
    return text.replace(loop, loop + "\t\t\t\t\t\t\t# cm_dev_perf +perf43: each level covered within the horizon\n"
                                     "\t\t\t\t\t\t\tcm_perf_ab_food_rgo_slack > 0\n", 1)


def _ab_food_take_manual(text: str) -> str:
    old = ("\t\t\tscope:cm_location = { cm_ab_food_stage_in_location = yes }\n"
           "\t\t}\n\t}\n}\n")
    if text.count(old) != 1:
        raise SystemExit("ab food: cm_ab_run_food has changed shape")
    return text.replace(old, old[:-2] + (
        "\t# cm_dev_perf +perf43: the breadbaskets he enabled by hand, while auto-food is off\n"
        "\tif = {\n\t\tlimit = {\n"
        "\t\t\texists = var:cm_ab_food_take_manual\n"
        "\t\t\tNOT = { is_target_in_variable_list = { name = cm_priority_features_enabled target = flag:cm_feature_auto_food } }\n"
        "\t\t}\n"
        "\t\tevery_owned_location = {\n\t\t\tlimit = {\n"
        "\t\t\t\texists = var:cm_auto_food_location_enabled\n"
        "\t\t\t\tlocation_rank = location_rank:rural_settlement\n"
        "\t\t\t\tNOT = { integration_level = conquered }\n"
        "\t\t\t\tcm_ab_location_is_system_food_picked = no\n"
        "\t\t\t\tcm_food_location_rgo_is_on_roster = yes\n"
        "\t\t\t}\n"
        "\t\t\tsave_scope_as = cm_location\n"
        "\t\t\traw_material = { save_scope_as = cm_food_good }\n"
        "\t\t\tcm_ab_food_stage_in_location = yes\n"
        "\t\t}\n\t}\n}\n"), 1)


def _register_ab_food(text: str) -> str:
    """The slider and the checkbox, after «Субсидировать» on the food tab."""
    sync = ("\tcmm_sync_bool_alias = {\n\t\tsetting = cm__ab_food_subsidize\n"
            "\t\talias = cm_ab_food_subsidize\n\t}\n")
    if text.count(sync) != 1:
        raise SystemExit("cmm: the food subsidy checkbox has changed shape")
    text = text.replace(sync, sync + (
        "\n\t# cm_dev_perf +perf43: the hiring horizon and the hand-enabled breadbaskets\n"
        "\tcmm_register_slider_setting = {\n\t\tmod_id = cm\n\t\tsetting_id = ab_food_horizon\n"
        "\t\ttab_id = ab_food\n\t\tgroup_id = ab_food\n\t\tdefault_value = 6\n"
        "\t\tmin_value = 1\n\t\tmax_value = 10\n\t\tstep_value = 1\n\t}\n"
        "\tcmm_sync_setting_alias = {\n\t\tsetting = cm__ab_food_horizon\n"
        "\t\talias = cm_ab_food_horizon\n\t}\n"
        "\tcmm_register_bool_setting = {\n\t\tmod_id = cm\n\t\tsetting_id = ab_food_take_manual\n"
        "\t\ttab_id = ab_food\n\t\tgroup_id = ab_food\n\t\tdefault_value = 0\n\t}\n"
        "\tcmm_sync_bool_alias = {\n\t\tsetting = cm__ab_food_take_manual\n"
        "\t\talias = cm_ab_food_take_manual\n\t}\n"))
    changed = "\t\tflag:cm__ab_food_run_now = {\n"
    if text.count(changed) != 1:
        raise SystemExit("cmm: the food run-now branch has changed shape")
    return text.replace(changed, (
        "\t\t# cm_dev_perf +perf43\n"
        "\t\tflag:cm__ab_food_horizon = {\n\t\t\tcmm_sync_setting_alias = {\n"
        "\t\t\t\tsetting = cm__ab_food_horizon\n\t\t\t\talias = cm_ab_food_horizon\n"
        "\t\t\t}\n\t\t}\n"
        "\t\tflag:cm__ab_food_take_manual = {\n\t\t\tcmm_sync_bool_alias = {\n"
        "\t\t\t\tsetting = cm__ab_food_take_manual\n\t\t\t\talias = cm_ab_food_take_manual\n"
        "\t\t\t}\n\t\t}\n") + changed, 1)


# His words 13.10 21:02: the same slider for Auto-Build's production tab — «пока ты
# спамишь зданиями там, где они ничего не приносят, ты можешь заспамить в других
# локациях». +perf44, by his rule of 21:07: one idle pop of the type is reason to
# build («пусть он заполняется»); the next level waits until the levels already
# there would be staffed within the horizon. CM let a level in on any unemployed pop
# of the type, which a level still hiring also has, or on a deficit filling within
# six years. Here: free places of the type (pops less every job built or building)
# plus the horizon's fill, strictly positive. Types without a fill rate (slaves,
# tribesmen) keep to their unemployed. The production RGO loop reads the slack with
# the slider's years, and builds while room is left after the levels it built. The
# rest of CM reads the same slider since 10-21 (`_every_horizon`).
AB_PROD = "in_game/common/scripted_effects/cm_ab_production_effects.txt"
AB_PROD_FILE = "in_game/common/script_values/cm_perf_ab_production_values.txt"
AB_PROD_TRIGGERS = "in_game/common/scripted_triggers/cm_perf_ab_production_triggers.txt"
_FILL_TYPES = ("nobles", "clergy", "burghers", "laborers", "soldiers", "peasants")


def _ab_prod_values() -> str:
    branches = "".join(
        f"\tif = {{\n\t\tlimit = {{ \"global_variable_map(cm_building_type_to_pop_type|scope:cm_building_type)\" = pop_type:{t} }}\n"
        f"\t\tvalue = cm_location_{t}_available\n"
        f"\t\tadd = {{ value = cm_location_fill_rate_for_{t} multiply = cm_perf_ab_prod_horizon_months }}\n\t}}\n"
        for t in _FILL_TYPES)
    return ("\ufeff# Generated by mods/cm_dev_perf/tools/port_from_cm_dev.py; not to be edited by hand.\n"
            "# Auto-Build production's hiring horizon (+perf44). Root is the location.\n"
            "cm_perf_ab_prod_horizon_months = {\n\tvalue = 72\n\tif = {\n"
            "\t\tlimit = { owner = { exists = var:cm_ab_production_horizon } }\n"
            "\t\tvalue = owner.var:cm_ab_production_horizon\n\t\tmultiply = 12\n\t}\n}\n\n"
            "# Free places of scope:cm_building_type's pop type (pops less every job built or building),\n"
            "# plus the horizon's fill. Positive: someone of the type is idle, or the levels already\n"
            "# there will be staffed within the horizon with room to start the next.\n"
            "cm_perf_ab_prod_slack = {\n\tvalue = cm_location_unemployed_for_building_type\n"
            + branches +
            "}\n\n"
            "# cm_location_rgo_promotion_buffer_slack with the slider's years.\n"
            "cm_perf_ab_prod_rgo_slack = {\n\tvalue = cm_location_laborers_or_slaves_available\n"
            "\tadd = { value = cm_location_fill_rate_for_laborers_or_slaves multiply = cm_perf_ab_prod_horizon_months }\n}\n")


AB_PROD_TRIGGERS_TEXT = """\ufeff# Generated by mods/cm_dev_perf/tools/port_from_cm_dev.py; not to be edited by hand.
# cm_location_has_enough_pops_available for Auto-Build production (+perf44): the level's own
# jobs covered within the production tab's horizon. Root is the location, expects
# scope:cm_building_type.
cm_perf_ab_prod_has_pops = {
	has_global_variable_map = cm_building_type_to_pop_type
	is_key_in_global_variable_map = { name = cm_building_type_to_pop_type target = scope:cm_building_type }
	cm_perf_ab_prod_slack > 0
}
"""


def _ab_prod_horizon(text: str) -> str:
    gate, n = re.subn(r"cm_location_has_enough_pops_available = yes", "cm_perf_ab_prod_has_pops = yes # cm_dev_perf +perf44", text)
    if n != 3:
        raise SystemExit(f"ab production: expected three pop gates, found {n}")
    old = "set_local_variable = { name = cm_ab_rgo_slack value = cm_location_rgo_promotion_buffer_slack }\n"
    if gate.count(old) != 1:
        raise SystemExit("ab production: the RGO slack read has changed shape")
    gate = gate.replace(old, "set_local_variable = { name = cm_ab_rgo_slack value = cm_perf_ab_prod_rgo_slack } # cm_dev_perf +perf44\n", 1)
    each = "local_var:cm_ab_rgo_slack >= local_var:cm_ab_rgo_done\n"
    if gate.count(each) != 2:
        raise SystemExit("ab production: the RGO loop's slack test has changed shape")
    return gate.replace(each, "local_var:cm_ab_rgo_slack > local_var:cm_ab_rgo_done # cm_dev_perf +perf44: room left after the levels built\n")


# Building Cleanup reopened a closed type only on proof from an open building of the same
# type in the market that still earns. Close the last brewery of a market and no proof can
# ever come: his brewery sat closed for years and earned the moment he opened it by hand
# (10-20). With none of its type open in the market, a closed building is judged on its own
# potential profit per level (`building_potential_profit`: full staff, full inputs) against
# the same floor its close was judged on.
CLEANUP = "in_game/common/scripted_effects/cm_cleanup_effects.txt"
CLEANUP_TRIGGERS = "in_game/common/scripted_triggers/cm_perf_cleanup_triggers.txt"
CLEANUP_TRIGGERS_TEXT = """﻿# Generated by mods/cm_dev_perf/tools/port_from_cm_dev.py; not to be edited by hand.
# A closed building whose type has nothing open in the market to vouch for it (cm_dev_perf).
# Root is the building, expects scope:cm_country and scope:cm_building_type.
cm_perf_cu_lone_reopen = {
	scope:cm_country = {
		NOT = {
			AND = {
				has_variable_map = cm_cu_open
				is_key_in_variable_map = { name = cm_cu_open target = scope:cm_building_type }
			}
		}
		trigger_if = {
			limit = {
				has_variable_map = cm_cu_reop
				is_key_in_variable_map = { name = cm_cu_reop target = scope:cm_building_type }
			}
			"variable_map(cm_cu_reop|scope:cm_building_type)" < cm_cu_reopen_cap
		}
		trigger_else = { cm_cu_reopen_cap >= 1 }
	}
	cm_perf_cu_potential_per_level > cm_cu_effective_floor
}
"""
CLEANUP_VALUES = "in_game/common/script_values/cm_perf_cleanup_values.txt"
CLEANUP_VALUES_TEXT = """﻿# Generated by mods/cm_dev_perf/tools/port_from_cm_dev.py; not to be edited by hand.
# What one level of a closed building would earn opened (cm_dev_perf). Root is the building.
cm_perf_cu_potential_per_level = {
	value = building_potential_profit
	if = {
		limit = { building_level >= 1 }
		divide = building_level
	}
}
"""


def _cleanup_lone_reopen(text: str) -> str:
    old = "\t\t\t\t\t\t\tscope:cm_country = { cm_cu_group_reopen_room = yes }\n"
    if text.count(old) != 1:
        raise SystemExit("cleanup: the reopen test has changed shape")
    return text.replace(old, old + "\t\t\t\t\t\t\tcm_perf_cu_lone_reopen = yes # cm_dev_perf: none of its type open to vouch for it\n", 1)


# 1.4.2 lets a fishing village stand on a river (`location_potential`: coastal or
# `has_river`); auto-food still asked for the coast alone (his question 10-20).
def _fishing_on_rivers(text: str) -> str:
    old = ("\t\tis_coastal = yes\n\t\tlocation_rank = location_rank:rural_settlement\n"
           "\t\tcm_food_location_buildable_for_building_type = { target = building_type:fishing_village }\n")
    if text.count(old) != 1:
        raise SystemExit("food: the fishing village option has changed shape")
    return text.replace(old, old.replace("\t\tis_coastal = yes\n",
                        "\t\tOR = { is_coastal = yes has_river = yes } # cm_dev_perf: rivers since 1.4.2\n"), 1)


def _every_horizon(text: str) -> str:
    """The rest of CM read six years flat (`multiply = 72`): the RGO auto-expand pass
    (`cm_queue_approval_effects.txt`) built stone with a thousand laborers short, his
    slider at one year (10-20, «там всё ещё действует правило 6 лет»). Both buffers
    now read the production tab's «Срок найма»."""
    for name in ("cm_location_rgo_promotion_buffer_slack", "cm_location_promotion_buffer_slack"):
        start = text.find(name + " = {")
        if start < 0:
            raise SystemExit(f"misc values: {name} is gone")
        end = text.find("\n}", start)
        body = text[start:end]
        if "multiply = 72" not in body:
            raise SystemExit(f"misc values: {name} no longer reads six years")
        text = text[:start] + body.replace("multiply = 72", "multiply = cm_perf_ab_prod_horizon_months") + text[end:]
    return text.replace("# Projected six-year pop slack", "# Projected pop slack over the hiring horizon (cm_dev_perf: the production tab's slider)")


def _register_ae_horizons(text: str) -> str:
    """+perf59, his ask 10-26: auto-expand and auto-food get hiring-horizon sliders of
    their own on the auto-expand tab, after the metric dropdown, instead of borrowing
    Auto-Build production's. Read by cm_perf_ae/af_horizon_months."""
    sync = ("\tcmm_sync_setting_alias = {\n\t\tsetting = cm__expand_metric\n"
            "\t\talias = cm_expand_metric\n\t}\n")
    if text.count(sync) != 1:
        raise SystemExit("cmm: the auto-expand metric setting has changed shape")
    sliders = ""
    branches = ""
    for key in ("ae_horizon", "af_horizon"):
        sliders += (
            f"\n\t# cm_dev_perf +perf59: the hiring horizon\n"
            f"\tcmm_register_slider_setting = {{\n\t\tmod_id = cm\n\t\tsetting_id = {key}\n"
            "\t\ttab_id = auto_expand\n\t\tgroup_id = priority_list\n\t\tdefault_value = 6\n"
            "\t\tmin_value = 1\n\t\tmax_value = 10\n\t\tstep_value = 1\n\t}\n"
            f"\tcmm_sync_setting_alias = {{\n\t\tsetting = cm__{key}\n\t\talias = cm_{key}\n\t}}\n")
        branches += (
            f"\t\t# cm_dev_perf +perf59\n\t\tflag:cm__{key} = {{\n\t\t\tcmm_sync_setting_alias = {{\n"
            f"\t\t\t\tsetting = cm__{key}\n\t\t\t\talias = cm_{key}\n\t\t\t}}\n\t\t}}\n")
    text = text.replace(sync, sync + sliders, 1)
    changed = "\t\tflag:cm__expand_metric = {\n"
    if text.count(changed) != 1:
        raise SystemExit("cmm: the auto-expand metric branch has changed shape")
    return text.replace(changed, branches + changed, 1)


def _register_ab_prod(text: str) -> str:
    """The slider, after the algorithm dropdown on the production tab."""
    sync = ("\tcmm_sync_setting_alias = {\n\t\tsetting = cm__ab_production_algorithm\n"
            "\t\talias = cm_ab_production_algorithm\n\t}\n")
    if text.count(sync) != 1:
        raise SystemExit("cmm: the production algorithm setting has changed shape")
    text = text.replace(sync, sync + (
        "\n\t# cm_dev_perf +perf44: the hiring horizon\n"
        "\tcmm_register_slider_setting = {\n\t\tmod_id = cm\n\t\tsetting_id = ab_production_horizon\n"
        "\t\ttab_id = ab_production\n\t\tgroup_id = ab_production\n\t\tdefault_value = 6\n"
        "\t\tmin_value = 1\n\t\tmax_value = 10\n\t\tstep_value = 1\n\t}\n"
        "\tcmm_sync_setting_alias = {\n\t\tsetting = cm__ab_production_horizon\n"
        "\t\talias = cm_ab_production_horizon\n\t}\n"))
    changed = "\t\tflag:cm__ab_production_algorithm = {\n"
    if text.count(changed) != 1:
        raise SystemExit("cmm: the production algorithm branch has changed shape")
    return text.replace(changed, (
        "\t\t# cm_dev_perf +perf44\n"
        "\t\tflag:cm__ab_production_horizon = {\n\t\t\tcmm_sync_setting_alias = {\n"
        "\t\t\t\tsetting = cm__ab_production_horizon\n\t\t\t\talias = cm_ab_production_horizon\n"
        "\t\t\t}\n\t\t}\n") + changed, 1)


# The box's own words, to say it now covers every farm.
SUBSIDY_DESC = {
    "english": "Subsidize the food-producing buildings auto-food constructs, and every month any farming village "
               "of yours that runs at a loss or has no workers, wherever it stands and whoever built it. A building "
               "that is not turning a profit hires nobody and grows no food; subsidizing it keeps it staffed and its "
               "harvest coming in. Subsidies are never turned back off.",
    "russian": "Субсидировать здания, производящие пищу и возводимые автоматикой, а также каждый месяц любую вашу "
               "земледельческую деревню без прибыли или без работников, где бы она ни стояла и кто бы её ни построил. "
               "Здание, не приносящее прибыли, никого не нанимает и не производит еду; субсидирование позволяет "
               "сохранять штат работников и обеспечивать сбор урожая. Субсидии никогда не отключаются.",
}


# +perf34, his call 10-12: fewer whole-tree walks in the queue drain. Every
# `PdxGuiTriggerAllAnimations` visits every widget in the game, and the count
# grows over a session (docs/investigations/cm_performance.md). Neither edit
# changes what CM scores, approves or builds.
QUEUE = "in_game/gui/cm_construct_queue_window.gui"

# Each scan shout and the list its rows hang from (the outer datamodel).
_SCAN_SHOUTS = (
    ("cm_q_construct", "cm_q_locations"),
    ("cm_q_construct_upgrade", "cm_gui_upgrade_locations"),
    ("cm_q_construct_urbanize", "cm_q_urbanize_locations"),
    ("cm_q_construct_food", "cm_q_food_locations"),
    ("cm_q_construct_food_rgo", "cm_q_food_rgo_locations"),
    ("cm_q_construct_rgo", "cm_q_rgo_locations"),
    ("cm_q_construct_foreign", "cm_q_fb_locations"),
    ("cm_q_construct_rank", "cm_q_rank_locations"),
    ("cm_ab_construct_build", "cm_ab_b_locations"),
    ("cm_ab_construct_upgrade", "cm_ab_u_locations"),
    ("cm_ab_construct_rgo", "cm_ab_r_locations"),
)


def _slow_the_poll(text: str) -> str:
    """The «ready?» loop between scoring and firing, every 1 s instead of 0.3 s:
    a third of the walks while CM waits. Completion is still decided by
    cm_q_sync_check; the step lengths only pace it."""
    old = ("\t\t\tstate = {\n\t\t\t\tname = cm_q_round_probe\n\t\t\t\tduration = 0.15\n"
           "\t\t\t\ton_finish = \"[PdxGuiTriggerAllAnimations('cm_q_probe')]\"\n"
           "\t\t\t\tnext = cm_q_round_check\n\t\t\t}\n"
           "\t\t\tstate = {\n\t\t\t\tname = cm_q_round_check\n\t\t\t\tduration = 0.15\n")
    if text.count(old) != 1:
        raise SystemExit("queue window: the poll loop has changed shape")
    return text.replace(old, old.replace("duration = 0.15", "duration = 0.5"), 1)


def _gate_scan_shouts(text: str) -> str:
    """One shout per queue that has something in it, instead of eleven every
    sweep. Each shout moves to its own zero-size widget that turns visible when
    the sweep arms and its list is non-empty, so its `_show` fires on the same
    edge and after the same 0.3 s the driver's did. The gate reads the
    variable cm_q_scan_gate tests, not the trigger, so the eleven cost three
    cheap reads a frame each, against the driver's one trigger."""
    shouts = "".join(
        f"\t\t\t\ton_finish = \"[PdxGuiTriggerAllAnimations('{name}')]\"\n" for name, _ in _SCAN_SHOUTS)
    old = "\t\t\t\tname = _show\n\t\t\t\tduration = 0.3\n" + shouts + "\t\t\t\tnext = cm_q_scan_done\n"
    if text.count(old) != 1:
        raise SystemExit("queue window: the scan driver's shouts have changed")
    text = text.replace(old, "\t\t\t\tname = _show\n\t\t\t\tduration = 0.3\n"
                             "\t\t\t\t# cm_dev_perf +perf34: the shouts are in the widgets below\n"
                             "\t\t\t\tnext = cm_q_scan_done\n", 1)
    anchor = "\t\t# Per-cycle poll driver:"
    if text.count(anchor) != 1:
        raise SystemExit("queue window: the poll driver's comment has moved")
    armed = "GetPlayer.MakeScope.GetVariable('cm_q_scan_armed').IsSet"
    gated = ("\t\t# cm_dev_perf +perf34: each scan shout only when its queue has entries. Every shout\n"
             "\t\t# walks every widget in the game, and most months most queues are empty.\n")
    for name, list_name in _SCAN_SHOUTS:
        gated += (
            "\t\twidget = {\n"
            "\t\t\tsize = { 0 0 }\n"
            "\t\t\tvisible_at_creation = no\n"
            f"\t\t\tvisible = \"[And3(GetPlayer.Exists, {armed}, DataModelHasItems(GetPlayer.MakeScope.GetList('{list_name}')))]\"\n"
            "\t\t\tstate = {\n"
            "\t\t\t\tname = _show\n"
            "\t\t\t\tduration = 0.3\n"
            f"\t\t\t\ton_finish = \"[PdxGuiTriggerAllAnimations('{name}')]\"\n"
            "\t\t\t}\n"
            "\t\t}\n")
    return text.replace(anchor, gated + anchor, 1)


# +perf35, his call 10-12 («стоит использовать какие-то инструменты отладки, а не
# забеги»): one line a cycle in debug.log, always on, that says whether the
# drain did its job. Every staged entry scores exactly once, so `scored` short of
# `staged` is a queue whose rows were never called — a broken gate of +perf34's
# — and `rounds` is the ready-polls the cycle took, each one a whole-tree walk.
FEATURE = "in_game/common/scripted_effects/cm_feature_effects.txt"
HIDDEN_GUIS = "in_game/common/scripted_guis/cm_hidden_window_scripted_gui.txt"


def _count_rounds_init(text: str) -> str:
    old = "\t\tset_variable = { name = cm_q_rescans value = 0 }\n"
    if text.count(old) != 1:
        raise SystemExit("feature effects: the cycle's counters have moved")
    text = text.replace(old, old + "\t\tset_variable = { name = cm_perf_rounds value = 0 } # cm_dev_perf +perf35\n", 1)
    old = "cm_q_reset_cycle_state = {\n"
    if text.count(old) != 1:
        raise SystemExit("feature effects: cm_q_reset_cycle_state has moved")
    log = (
        "\t# cm_dev_perf +perf35: one line a cycle in debug.log, always on\n"
        "\tif = {\n"
        "\t\tlimit = {\n"
        "\t\t\tis_human = yes\n"
        "\t\t\thas_variable = cm_q_staged\n"
        "\t\t\thas_variable = cm_q_processed\n"
        "\t\t\thas_variable = cm_q_rescans\n"
        "\t\t\thas_variable = cm_perf_rounds\n"
        "\t\t}\n"
        "\t\tset_global_variable = { name = cm_perf_log_v1 value = var:cm_q_staged }\n"
        "\t\tset_global_variable = { name = cm_perf_log_v2 value = var:cm_q_processed }\n"
        "\t\tset_global_variable = { name = cm_perf_log_v3 value = var:cm_perf_rounds }\n"
        "\t\tset_global_variable = { name = cm_perf_log_v4 value = var:cm_q_rescans }\n"
        # +perf36: how the cycle ended. skipped 2 = the dispatcher's force reset, which
        # drops the month unbuilt; approved 0 = it never reached the approval pass.
        "\t\tset_global_variable = { name = cm_perf_log_v5 value = 0 }\n"
        "\t\tif = { limit = { has_variable = cm_q_skipped_pulses } "
        "set_global_variable = { name = cm_perf_log_v5 value = var:cm_q_skipped_pulses } }\n"
        "\t\tset_global_variable = { name = cm_perf_log_v6 value = 0 }\n"
        "\t\tif = { limit = { has_variable = cm_q_pass_done } "
        "set_global_variable = { name = cm_perf_log_v6 value = 1 } }\n"
        "\t\tdebug_log = \"CM perf cycle: staged "
        + " scored ".join(f"[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v{n}')|0]" for n in (1, 2))
        + " rounds [GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v3')|0]"
        + " rescans [GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v4')|0]"
        + " skipped [GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v5')|0]"
        + " approved [GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v6')|0]\"\n"
        "\t}\n")
    return text.replace(old, old + log, 1)


def _count_rounds(text: str) -> str:
    old = "cm_q_sync_check = {\n\tis_valid = {\n\t\talways = yes\n\t}\n\teffect = {\n"
    if text.count(old) != 1:
        raise SystemExit("hidden window guis: cm_q_sync_check has changed shape")
    return text.replace(old, old + "\t\tif = { limit = { has_variable = cm_perf_rounds } "
                                   "change_variable = { name = cm_perf_rounds add = 1 } } # cm_dev_perf +perf35\n", 1)


# +perf38 (10-12, his «сделать в cm_dev_perf аналогичные изменения»): cm_maps
# 0.3.0's rights scoring, taken from cm_maps' own generator so the two stay one
# rule. The rights are scored for the province, not the location, and a
# granted 1.4 charter is not the location's own bonus (cm_maps/tools/port_from_cm.py,
# province_scored_edits, and its README «1.4»).
_spec = importlib.util.spec_from_file_location(
    "cm_maps_port", refs.REPO / "mods/cm_maps/tools/port_from_cm.py")
maps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(maps)

TRMM_VALUES = "in_game/common/script_values/cm_town_right_map_mode_script_values.txt"
MISC_VALUES = "in_game/common/script_values/cm_misc_script_values.txt"


def _province_scored(text: str) -> str:
    for path, old, new, label in maps.province_scored_edits():
        if path != maps.TRMM_VALUES:
            raise SystemExit(f"cm_maps edits a file this port does not map: {path}")
        old, new = old.replace("bcm_", "cm_"), new.replace("bcm_", "cm_").replace(
            "# cm_maps scores the province", "# cm_dev_perf (as cm_maps) scores the province")
        if text.count(old) != 1:
            raise SystemExit(f"rights values: {label} — matched {text.count(old)} times")
        text = text.replace(old, new, 1)
    return text


def _retire_trmm(text: str) -> str:
    """The stored best rights were scored the old way; a new version makes every
    started save recompute on load (`cm_trmm_stamp`, cm_setup_triggers.txt).
    Far above CM's own count, so a CM bump does not land on it."""
    old = "cm_trmm_version_value = 1\n"
    if text.count(old) != 1:
        raise SystemExit("misc values: cm_trmm_version_value has moved")
    return text.replace(old, "cm_trmm_version_value = 101 # cm_dev_perf +perf38: rights per province\n", 1)


def _chip_words() -> None:
    """The tooltip chips mark what is no longer in the score (cm_maps LOC_EDITS)."""
    for lang in ("russian", "english"):
        path = MOD / f"main_menu/localization/{lang}/cm_town_right_map_mode_l_{lang}.yml"
        text = path.read_text(encoding="utf-8-sig")
        for key, value in maps.LOC_EDITS[("bcm_trmm", lang)].items():
            key = key.replace("bcm_", "cm_")
            text, n = re.subn(rf'(?m)^( {re.escape(key)}:\s*\d*\s*)"(?:[^"\\]|\\.)*"',
                              lambda m: f'{m.group(1)}"{value}"', text)
            if n != 1:
                raise SystemExit(f"{path.name}: {key} matched {n} times")
        path.write_text("﻿" + text, encoding="utf-8")


# +perf38 (10-12, his words): «в 1.4 добавились младшие аналоги всех
# специализированных прав… мод должен уметь выдавать их, пока недоступны их
# старшие аналоги». The nine charters (town_rights/01_discovery_charter.txt) open
# with city_building_advance in age 1, each `upgrades_to` its royal right, which
# opens with town_rights_enable in age 3; same goods, half the bonus. So the
# specialization draw scores as before and grants the charter until the royal
# rights open; a location holding either counts as specialized.
ATR = "in_game/common/scripted_effects/cm_atr_ur_effects.txt"
ATR_TRIGGERS = "in_game/common/scripted_triggers/cm_atr_ur_triggers.txt"
ATR_ALLOW = "in_game/common/scripted_triggers/cm_auto_town_rights_allow_triggers.txt"
CHARTER_ADVANCE = "city_building_advance"


def _charters() -> dict[str, str]:
    """royal right -> its charter, read from the game's files."""
    text = (refs.GAME_COMMON / "town_rights/01_discovery_charter.txt").read_text(encoding="utf-8-sig")
    pairs = dict((royal, charter) for charter, royal in
                 re.findall(r"(?m)^([a-z_]+) = \{.*?^\tupgrades_to = ([a-z_]+)", text, re.S))
    advances = (refs.GAME_COMMON / "advances/0_age_of_traditions.txt").read_text(encoding="utf-8-sig")
    block = re.search(rf"(?ms)^{CHARTER_ADVANCE} = \{{.*?^\}}", advances)
    if not block or any(f"unlock_town_rights = {c}" not in block.group(0) for c in pairs.values()):
        raise SystemExit(f"charters: {CHARTER_ADVANCE} no longer unlocks all of them")
    return pairs


def _grant_charters(text: str) -> str:
    pairs = _charters()
    start = text.index("cm_atr_ur_pick_specialization = {\n")
    end = text.index("\n}\n", start) + 3
    pick = text[start:end]
    missing = [r for r in pairs if f"RIGHT = {r} " not in pick]
    if missing or len(pairs) != 9:
        raise SystemExit(f"charters: the draw and the game disagree ({missing}, {len(pairs)})")
    charter = pick.replace("cm_atr_ur_pick_specialization = {", "cm_atr_ur_pick_charter = {", 1)
    for royal, ch in pairs.items():
        charter = charter.replace(f"RIGHT = {royal} ", f"RIGHT = {ch} ")
    note = ("# cm_dev_perf +perf38: the same draw granting the 1.4 charter of each right, for a\n"
            "# country that has the charters and not yet the royal rights. Charters carry half the\n"
            "# royal bonus on the same goods, so fit and value rank them as the royal ones.\n")
    text = text[:end] + "\n" + note + charter + text[end:]
    # His ask 10-12: «перевыдачу городских прав по достижению открытия более сильных
    # вариантов». The game's own upgrade (town_rights.gui, TownRights.Upgrade) is a GUI
    # action with no script effect; script swaps the charter for its royal right and
    # pays the upgrade's price (prices/00_hardcoded.txt, upgrade_town_rights).
    swaps = "".join(
        f"\t\tif = {{\n"
        f"\t\t\tlimit = {{\n"
        f"\t\t\t\thas_town_rights = town_rights_type:{ch}\n"
        f"\t\t\t\tcm_trmm_right_fits_location = {{ RIGHT = {royal} ALLOW = cm_can_grant_specialization_right_at_location }}\n"
        f"\t\t\t\tscope:cm_country = {{ cm_town_rights_grant_affordable = yes }}\n"
        f"\t\t\t}}\n"
        f"\t\t\trevoke_town_rights_of_type = town_rights_type:{ch}\n"
        f"\t\t\tgrant_town_rights = town_rights_type:{royal}\n"
        f"\t\t\tcm_atr_ur_upgrade_paid = yes\n"
        f"\t\t}}\n"
        for royal, ch in pairs.items())
    upgrade = ("\n# cm_dev_perf +perf39: once the royal rights open, each 1.4 charter in the slice becomes\n"
               "# its royal right, the engine's upgrade path (`upgrades_to`). Root is the country,\n"
               "# scope:cm_country set.\n"
               "cm_atr_ur_upgrade_charters = {\n"
               "\tevery_in_list = {\n"
               "\t\tvariable = cm_slice_locations\n"
               + swaps +
               "\t}\n}\n\n"
               "# The upgrade's price, unless grants are free. Root is the location.\n"
               "cm_atr_ur_upgrade_paid = {\n"
               "\tif = {\n"
               "\t\tlimit = { NOT = { cm_town_rights_grants_are_free = yes } }\n"
               "\t\tscope:cm_country = { pay_price = price:upgrade_town_rights }\n"
               "\t}\n"
               "\tscope:cm_country = { set_variable = { name = cm_trmm_refresh_armed value = yes } }\n"
               "}\n")
    text = text + upgrade
    head = ("cm_atr_ur_specialization_pass = {\n\tif = {\n"
            "\t\tlimit = { cm_town_rights_grant_affordable = yes }\n")
    if text.count(head) != 1:
        raise SystemExit("charters: the specialization pass's head has moved")
    text = text.replace(head, head +
        "\t\t# cm_dev_perf +perf39: charters become royal rights first, then new grants\n"
        "\t\tif = {\n"
        "\t\t\tlimit = { has_advance = town_rights_enable }\n"
        "\t\t\tcm_atr_ur_upgrade_charters = yes\n"
        "\t\t}\n", 1)
    old = "\t\t\t\tcm_atr_ur_pick_specialization = yes\n"
    if text.count(old) != 1:
        raise SystemExit("charters: the pass's call to the draw has moved")
    return text.replace(old,
        "\t\t\t\tif = {\n"
        "\t\t\t\t\tlimit = { scope:cm_country = { has_advance = town_rights_enable } }\n"
        "\t\t\t\t\tcm_atr_ur_pick_specialization = yes\n"
        "\t\t\t\t}\n"
        "\t\t\t\telse = {\n"
        "\t\t\t\t\tcm_atr_ur_pick_charter = yes # cm_dev_perf +perf38\n"
        "\t\t\t\t}\n", 1)


def _charter_counts(text: str) -> str:
    """A charter is a specialization: one per location, as the royal right."""
    old = "\t\thas_town_rights = town_rights_type:royal_masonry_rights\n\t}\n"
    if text.count(old) != 1:
        raise SystemExit("charters: cm_atr_ur_has_no_specialization has changed")
    lines = "".join(f"\t\thas_town_rights = town_rights_type:{c} # cm_dev_perf +perf38\n"
                    for c in _charters().values())
    return text.replace(old, old[:-3] + lines + "\t}\n", 1)


def _charter_allow(text: str) -> str:
    """textile_charter carries the royal textile right's own allow (the Flemish right)."""
    start = text.index("cm_can_grant_specialization_right_at_location = {\n")
    head, text = text[:start], text[start:]
    old = ("\ttrigger_else_if = {\n"
           "\t\tlimit = { scope:cm_town_right = town_rights_type:royal_textile_rights }\n")
    if text.count(old) != 1:
        raise SystemExit("charters: the textile allow has moved")
    return head + text.replace(old, old.replace(
        "limit = { scope:cm_town_right = town_rights_type:royal_textile_rights }",
        "limit = {\n\t\t\tOR = {\n"
        "\t\t\t\tscope:cm_town_right = town_rights_type:royal_textile_rights\n"
        "\t\t\t\tscope:cm_town_right = town_rights_type:textile_charter # cm_dev_perf +perf38\n"
        "\t\t\t}\n\t\t}"), 1)


def _charter_gate(text: str) -> str:
    """The draw runs once the charters are open, not only the royal rights."""
    old = ("\t\t\t\texists = var:cm_auto_grant_specialization\n"
           "\t\t\t\thas_advance = town_rights_enable\n")
    if text.count(old) != 1:
        raise SystemExit("charters: the specialization gate has moved")
    return text.replace(old,
        "\t\t\t\texists = var:cm_auto_grant_specialization\n"
        "\t\t\t\t# cm_dev_perf +perf38: the 1.4 charters open in age 1\n"
        f"\t\t\t\tOR = {{ has_advance = town_rights_enable has_advance = {CHARTER_ADVANCE} }}\n", 1)


def _write_subsidy_desc() -> None:
    for lang, words in SUBSIDY_DESC.items():
        path = MOD / f"main_menu/localization/{lang}/cm_cmm_l_{lang}.yml"
        text = path.read_text(encoding="utf-8-sig")
        text, n = re.subn(r'(?m)^ cm__ab_food_subsidize_desc: ".*"$',
                          lambda _m: f' cm__ab_food_subsidize_desc: "{words}"', text)
        if n != 1:
            raise SystemExit(f"{path.name}: the subsidy checkbox's description has moved")
        path.write_text("\ufeff" + text, encoding="utf-8")


# +perf41 (10-13, his «Конечно, делаем… Я играю с автостройкой CM»): the
# recommended industry-support map, built by cm_maps' own tool so the two stay
# one rule (mods/cm_maps/tools/industry_support.py), renamed bcm_ -> cm_ and run
# by CM's own load-time setup right after the rights pass it reads.
_ind_spec = importlib.util.spec_from_file_location(
    "cm_maps_industry", refs.REPO / "mods/cm_maps/tools/industry_support.py")
industry = importlib.util.module_from_spec(_ind_spec)
_ind_spec.loader.exec_module(industry)

def _industry_files() -> dict[str, str]:
    trmm = (MOD / TRMM).read_text(encoding="utf-8-sig").replace("cm_trmm_", "bcm_trmm_")
    made = industry.files({industry.TRMM_EFFECTS: trmm}, refs.GAME, tab="map_modes")
    # CM ships more languages than cm_maps; each gets the rows (check_cmm wants them all).
    inds = industry.industries(refs.GAME)
    for folder in sorted((MOD / "main_menu/localization").iterdir()):
        made.setdefault(f"main_menu/localization/{folder.name}/bcm_ind_l_{folder.name}.yml",
                        industry.localization(folder.name, inds, "map_modes"))
    out = {}
    for path, text in made.items():
        path = path.replace("/bcm_ind_", "/cm_ind_").replace("/bcm_industry_", "/cm_industry_")
        text = text.replace("MAPMODE_BCM_", "MAPMODE_CM_").replace("bcm_", "cm_")
        out[path] = text
    return out


def _industry_pass(text: str) -> str:
    old = ("    cm_trmm_recompute_all = yes\n"
           "    # Synchronous, so there is no partial state for the stamp to certify.\n"
           "    set_global_variable = { name = cm_trmm_stamp value = cm_trmm_version_value }\n"
           "  }\n")
    if text.count(old) != 1:
        raise SystemExit("setup: the rights pass in cm_run_lobby_setup has changed shape")
    new = ("    cm_trmm_recompute_all = yes\n"
           "    # Synchronous, so there is no partial state for the stamp to certify.\n"
           "    set_global_variable = { name = cm_trmm_stamp value = cm_trmm_version_value }\n"
           "    # cm_dev_perf +perf41: the industry-support pass reads these rights.\n"
           "    if = { limit = { has_global_variable = cm_ind_stamp } remove_global_variable = cm_ind_stamp }\n"
           "  }\n"
           "  # cm_dev_perf +perf41: recommended industry support per area, from the rights above.\n"
           "  if = {\n"
           "    limit = { NOT = { cm_ind_data_is_current = yes } }\n"
           "    cm_ind_recompute_all = yes\n"
           "    set_global_variable = { name = cm_ind_stamp value = cm_ind_version_value }\n"
           "  }\n")
    text = text.replace(old, new, 1)
    drop = "  remove_global_variable = cm_fpot_stamp\n}\n"
    if text.count(drop) != 1:
        raise SystemExit("setup: cm_setup_drop_stamps has changed shape")
    return text.replace(drop, "  remove_global_variable = cm_fpot_stamp\n"
                              "  remove_global_variable = cm_ind_stamp # cm_dev_perf +perf41\n}\n", 1)


def _register_industry_mode(text: str) -> str:
    """+perf47 (10-15): the industry map's three modes, a dropdown on the map
    modes tab after the governor's, the same one cm_maps has (its words and
    `cm_ind_mode_changed` come with industry_support.py)."""
    sync = ("\tcmm_sync_setting_alias = {\n\t\tsetting = cm__placement_finder_accuracy\n"
            "\t\talias = cm_placement_finder_accuracy\n\t}\n")
    if text.count(sync) != 1:
        raise SystemExit("cmm: the governor accuracy dropdown has changed shape")
    text = text.replace(sync, sync + (
        "\n\t# cm_dev_perf +perf47: how the industry-support map counts, 2 = 0.4.1's rule\n"
        "\tcmm_register_dropdown_setting = {\n\t\tmod_id = cm\n\t\tsetting_id = industry_mode\n"
        "\t\ttab_id = map_modes\n\t\tgroup_id = industry\n\t\tdefault_index = 2\n\t\toption_count = 3\n\t}\n"
        "\tcmm_sync_setting_alias = {\n\t\tsetting = cm__industry_mode\n\t\talias = cm_ind_mode\n\t}\n"
        "\tif = {\n\t\tlimit = { has_variable = cm_ind_mode }\n"
        "\t\tset_global_variable = { name = cm_ind_mode_g value = var:cm_ind_mode }\n\t}\n"), 1)
    changed = "\t\tflag:cm__placement_finder_accuracy = {\n"
    if text.count(changed) != 1:
        raise SystemExit("cmm: the governor accuracy branch has changed shape")
    return text.replace(changed, (
        "\t\t# cm_dev_perf +perf47\n"
        "\t\tflag:cm__industry_mode = {\n\t\t\tcmm_sync_setting_alias = {\n"
        "\t\t\t\tsetting = cm__industry_mode\n\t\t\t\talias = cm_ind_mode\n"
        "\t\t\t}\n\t\t\tcm_ind_mode_changed = yes\n\t\t}\n") + changed, 1)


# The hiring horizon each gate reads (+perf59, his ask 10-26): Auto-Build production and
# food their tabs' sliders, auto-expand and auto-food the two on the auto-expand tab, and a
# gate several passes share the pass running now (cm_perf_horizon_months).
_PROD = "MONTHS = cm_perf_ab_prod_horizon_months"
_FOOD = "MONTHS = cm_perf_ab_food_horizon_months"
_AE = "MONTHS = cm_perf_ae_horizon_months"
_AF = "MONTHS = cm_perf_af_horizon_months"
_NOW = "MONTHS = cm_perf_horizon_months"
_POP_MARK = " # cm_dev_perf +perf53: his pop rule"


def _rule(scope: str, months: str) -> str:
    return f"cm_perf_pops_ok = {{ T = {scope} {months} }}"


def _rgo(months: str) -> str:
    return f"cm_perf_rgo_level_ok = {{ {months} }}"


# Every place CM decides whether a location has the pops for a new level, and what
# takes its place (+perf53, his rule 10-26, tools/probe/.../cm_perf_pop_rule_triggers.txt).
# (file, old, new, how many times old occurs).
_POP_RULE = (
    ("scripted_triggers/cm_location_has_enough_pops_available_triggers.txt",
     "\tOR = {\n\t\tcm_location_unemployed_for_building_type > 0\n"
     "\t\tcm_location_promotion_buffer_covers_deficit = yes\n\t}\n",
     f"\t{_rule('scope:cm_building_type', _NOW)}{_POP_MARK}\n", 1),
    ("scripted_triggers/cm_perf_ab_production_triggers.txt",
     "\tcm_perf_ab_prod_slack > 0\n", f"\t{_rule('scope:cm_building_type', _PROD)}{_POP_MARK}\n", 1),
    ("scripted_triggers/cm_ab_triggers.txt",
     "cm_ab_core_pops_ok = {\n\tcm_ab_core_pop_room > 0\n}",
     f"cm_ab_core_pops_ok = {{\n\tcm_ab_core_pop_room > 0\n\t{_rule('scope:cm_building_type', _PROD)}{_POP_MARK}\n}}", 1),
    ("scripted_triggers/cm_ab_triggers.txt",
     "\tOR = {\n\t\tcm_location_laborers_or_slaves_available > 0\n"
     "\t\tcm_location_laborers_promotion_source_pool > 0\n\t}\n",
     f"\t{_rgo(_PROD)}{_POP_MARK}\n", 1),
    ("scripted_triggers/cm_food_auto_build_triggers.txt",
     "\t$pool$ > 0\n", f"\t{_rule('scope:cm_food_pops_type', _NOW)}{_POP_MARK}\n", 1),
    # The rule reads the building's own type, so the pool each caller named goes.
    ("scripted_triggers/cm_food_auto_build_triggers.txt",
     " pool = cm_location_peasants_available }", " }", 3),
    ("scripted_triggers/cm_food_auto_build_triggers.txt",
     " pool = cm_location_laborers_or_slaves_available }", " }", 1),
    ("scripted_triggers/cm_food_auto_build_triggers.txt",
     " and $pool$ = the script\n# value counting free places of its pop type.\n",
     ". cm_dev_perf +perf53: the pops by his rule,\n# cm_perf_pops_ok.\n", 1),
    ("scripted_triggers/cm_food_auto_build_triggers.txt",
     "\t# cm_dev_perf +perf42: the RGO's own pool, its levels and the laborer jobs counted\n"
     "\tcm_location_laborers_or_slaves_available > 0\n",
     f"\t{_rgo(_NOW)}{_POP_MARK}\n", 1),
    ("scripted_triggers/cm_rgo_triggers.txt",
     "\t\tcm_location_rgo_promotion_buffer_slack >= 0\n", f"\t\t{_rgo(_AE)}{_POP_MARK}\n", 1),
    ("scripted_guis/cm_rgos.txt",
     "\t\tcm_location_rgo_promotion_buffer_slack >= 0\n", f"\t\t{_rgo(_AE)}{_POP_MARK}\n", 1),
    # The drains counted levels against a slack in thousands of pops: `>=` let the first
    # level through on a slack of exactly 0, a thousand laborers short (his run 10-26).
    ("scripted_effects/cm_queue_approval_effects.txt",
     "local_var:cm_q_rgo_slack >= local_var:cm_q_rgo_done", _rgo(_AE), 2),
    ("scripted_effects/cm_queue_approval_effects.txt",
     "\t\t\t\t\t\t# cm_dev_perf +perf42: a level only for laborers or slaves who are there\n"
     "\t\t\t\t\t\tcm_location_laborers_or_slaves_available > 0\n",
     f"\t\t\t\t\t\t{_rgo(_AF)}{_POP_MARK}\n", 1),
    ("scripted_effects/cm_ab_production_effects.txt",
     "local_var:cm_ab_rgo_slack > local_var:cm_ab_rgo_done # cm_dev_perf +perf44: room left after the levels built",
     f"{_rgo(_PROD)}{_POP_MARK}", 2),
    ("scripted_effects/cm_ab_food_effects.txt",
     "cm_perf_ab_food_rgo_slack > 0", _rgo(_FOOD), 2),
    ("scripted_effects/cm_ab_core_effects.txt",
     "\t\t\t\t\t\tcm_ab_can_afford_rgo = { POOL = cm_ab_pool_core }\n\t\t\t\t\t}\n"
     "\t\t\t\t\tchange_local_variable = { name = cm_ab_core_rgo_guard add = 1 }\n",
     f"\t\t\t\t\t\tcm_ab_can_afford_rgo = {{ POOL = cm_ab_pool_core }}\n\t\t\t\t\t\t{_rgo(_PROD)}{_POP_MARK}\n\t\t\t\t\t}}\n"
     "\t\t\t\t\tchange_local_variable = { name = cm_ab_core_rgo_guard add = 1 }\n", 1),
    # +perf57: a location its peasants cannot cover is held until half the time the debt
    # takes to clear, set where the sampler visits each tracked location before staging.
    ("scripted_effects/cm_pop_sample_effects.txt",
     "\t\t\t\tcm_pop_sample = yes\n",
     "\t\t\t\tcm_pop_sample = yes\n\t\t\t\tcm_perf_pop_hold_update = yes # cm_dev_perf +perf57: his rule 10-26\n", 1),
    # +perf59, his word 10-26: capital and market-centre buildings, point buildings and
    # strong ones, build whatever the pops (control buildings never asked).
    ("scripted_effects/cm_ab_custom_effects.txt",
     "cm_location_allowed_to_build = { target = scope:cm_building_type }\n"
     "\t\t\tcm_location_has_enough_pops_available = yes\n"
     "\t\t\tcm_check_location_meets_min_market_access = yes\n",
     "cm_location_allowed_to_build = { target = scope:cm_building_type }\n"
     "\t\t\t# cm_dev_perf +perf59: no pop rule for point buildings (his word 10-26)\n"
     "\t\t\tcm_check_location_meets_min_market_access = yes\n", 2),
    # +perf59: the pass running now, for the gates several passes share; the approval
    # drain marks it too (_probe_feature_names).
    # +perf60, his word 10-26: the auto-food cleanup clears non-food production as soon as
    # the peasants stop covering every class's shortfall plus 500 - where food buildings
    # begin to go short - not only once some type is already below its jobs.
    ("scripted_effects/cm_cleanup_effects.txt",
     "\t\t\tcm_location_has_worker_deficit = yes\n",
     "\t\t\tOR = { # cm_dev_perf +perf60: his rule 10-26\n"
     "\t\t\t\tcm_location_has_worker_deficit = yes\n"
     "\t\t\t\tcm_perf_peasant_debt >= 0\n"
     "\t\t\t}\n", 1),
    ("scripted_effects/cm_feature_effects.txt",
     "\t\t\t\t\t\tswitch = {\n\t\t\t\t\t\t\ttrigger = scope:cm_feature\n",
     "\t\t\t\t\t\tset_global_variable = { name = cm_perf_bp_feat value = scope:cm_feature } # cm_dev_perf +perf59\n"
     "\t\t\t\t\t\tswitch = {\n\t\t\t\t\t\t\ttrigger = scope:cm_feature\n", 1),
    ("scripted_effects/cm_feature_effects.txt",
     "\t\t\t\t\tscope:cm_country = { cm_ab_stage_category = yes }\n",
     "\t\t\t\t\tset_global_variable = { name = cm_perf_bp_feat value = scope:cm_ab_cat } # cm_dev_perf +perf59\n"
     "\t\t\t\t\tscope:cm_country = { cm_ab_stage_category = yes }\n", 1),
)


def _his_pop_rule() -> None:
    """+perf53: his pop rule in every place CM asks whether a level has its pops."""
    for path, old, new, count in _POP_RULE:
        target = MOD / "in_game/common" / path
        text = target.read_text(encoding="utf-8-sig")
        if text.count(old) != count:
            raise SystemExit(f"{path}: the pop gate {old.strip()[:60]!r} has changed shape "
                             f"({text.count(old)} found, {count} expected)")
        target.write_text("﻿" + text.replace(old, new), encoding="utf-8")


def _probe_each_build(text: str) -> str:
    """+perf51 (10-26, his ask): every build CM approves writes a line into
    `debug.log` with the numbers its worker gates read (the probe in
    tools/probe/). Every feature and Auto-Build category approves through
    `cm_q_approve_build_copy`; upgrades and urbanize construct on their own and
    are not probed. His complaint: shortage limits that still build where a
    location has no peasants, and sliders that seem not to reach what they name.
    """
    head = ("cm_q_approve_build_copy = {\n"
            "\tadd_to_variable_list = { name = cm_q_approved_build_types target = scope:cm_building_type }\n")
    if text.count(head) != 1:
        raise SystemExit("feature effects: cm_q_approve_build_copy has changed shape")
    return text.replace(head, head.replace(
        "{\n", "{\n\tcm_perf_build_probe = yes # cm_dev_perf +perf51\n", 1), 1)


def _probe_feature_names(text: str) -> str:
    """The pass that is approving, for the build probe's `feature` (+perf51): a
    flag in a global, which `GetGlobalVariable(...).GetFlagName` prints."""
    marks = (
        (r"switch = \{\n\t+trigger = scope:cm_q_pass_feature\n", "scope:cm_q_pass_feature", 1),
        (r"scope:cm_country = \{ cm_ab_drain_category = \{ WRAP = cm_ab_drain_", "scope:cm_ab_cat", 2),
        (r"cm_q_pass_auto_urbanize = yes\n", "flag:cm_feature_auto_urbanize", 1),
    )
    for anchor, value, count in marks:
        line = re.compile(r"^(\t*)(" + anchor + ")", re.M)
        if len(line.findall(text)) != count:
            raise SystemExit(f"approval pass: {anchor!r} has changed shape")
        text = line.sub(lambda m: f"{m.group(1)}set_global_variable = {{ name = cm_perf_bp_feat value = {value} }}"
                        f" # cm_dev_perf +perf51\n{m.group(1)}{m.group(2)}", text)
    return text


EDITS = (
    (CMM, "the industry map's mode dropdown", _register_industry_mode),
    (RESERVE_GUIS, "the gold slider no longer writes CM's reserve", _cut_reserve_pull),
    (WINDOW, "gate the building-type tree", _gate_the_tree),
    (WINDOW, "widen the first pass's instantiation window", perf._widen_first_pass),
    (WINDOW, "widen the upgrade refresh's instantiation window", _widen_refresh),
    (LOG, "mirror the Debug tab's log into debug.log", _mirror_log),
    (ROADS, "say the roads plan's gates in its probe", _probe_road_gates),
    (ROADS, "let roads go ahead through a market shortage", _roads_ignore_shortage),
    ("in_game/common/scripted_triggers/cm_gov_triggers.txt", "no governor beside another proximity source",
     _gov_other_sources),
    ("in_game/common/scripted_guis/cm_food_auto_build_scripted_gui.txt", "every food good of the game", _food_rgo_trigger),
    ("in_game/common/scripted_triggers/cm_ab_triggers.txt", "every food good of the game", _food_rgo_trigger),
    ("in_game/common/scripted_effects/cm_game_load_setup_effects.txt", "every food good of the game", _food_rgo_list),
    (CMM, "the checkbox for it", _register_ignore_shortage),
    (CORE, "work core goods in markets centred elsewhere", _core_foreign_markets),
    (CMM, "the checkbox for it", _register_core_foreign),
    (TRMM, "mark the province slices the rights pass writes, and the repair", _mark_trmm_slices),
    (TRMM_GUIS, "the repair's scripted gui", _trmm_repair_gui),
    (PF_WINDOW, "run the repair on entering the rights map", _trmm_repair_driver),
    (CUSTOM, "the beta's capital buildings, and the National Destinies list's set", buildings.edit_custom_sets),
    ("in_game/common/scripted_triggers/cm_ab_triggers.txt", "subject candidates for the National Destinies list",
     buildings.edit_subjects_wanted),
    ("in_game/common/scripted_effects/cm_ab_production_effects.txt", "the Production tab skips National Destinies'",
     buildings.edit_production_skip),
    (SEED, "the National Destinies set listed at load", buildings.edit_populate),
    (SEED, "the industry-support pass after the rights", _industry_pass),
    (CMM, "the roster's new rows and the National Destinies list", buildings.edit_registration),
    (SEED, "the seeded roster's new rows", buildings.edit_seed),
    (LOOKUPS, "National Destinies rows in the roster's lookups and visibility", buildings.edit_lookups),
    (AUTO_EXPAND, "the unbuilt-row toggle in Río's slot", _unbuilt_toggle_slot),
    ("in_game/common/scripted_effects/cm_queue_approval_effects.txt", "the food drain's location scope",
     _food_pass_location),
    ("in_game/common/scripted_effects/cm_gov_plan_effects.txt", "save the player's map before the planner's search",
     _pf_view_save_hook),
    ("in_game/common/scripted_effects/cm_gov_plan_effects.txt", "put the player's map back after the tick",
     _pf_view_restore_hook),
    ("in_game/common/scripted_effects/cm_proximity_finder_effects.txt", "the player's own run drops the saved map",
     _pf_view_drop_hook),
    (PF_WINDOW, "re-assert the finder map's open flag after the repaint swap", _pf_reassert),
    ("in_game/common/scripted_guis/cm_proximity_finder_scripted_gui.txt", "say the finder map's close in debug.log",
     _pf_log_close),
    (CMM, "say the refresh button's click in debug.log", _pf_log_click),
    (FOOD, "subsidize every idle or loss-making farm", _subsidize_idle_farms),
    (FOOD_TRIGGERS, "auto-food asks the building's own pop pool", _food_pops_by_type),
    (APPROVAL, "the food RGO drain stops at the laborer pool", _food_rgo_drain_pops),
    (AB_FOOD, "the food tab's hiring horizon", _ab_food_horizon),
    (AB_FOOD, "take the hand-enabled breadbaskets", _ab_food_take_manual),
    (CMM, "the food tab's slider and checkbox", _register_ab_food),
    (AB_PROD, "the production tab's hiring horizon", _ab_prod_horizon),
    (CMM, "the production tab's slider", _register_ab_prod),
    (CMM, "auto-expand's and auto-food's sliders", _register_ae_horizons),
    (MISC_VALUES, "every pop buffer reads the hiring horizon", _every_horizon),
    (CLEANUP, "reopen a closed type with nothing open to vouch for it", _cleanup_lone_reopen),
    ("in_game/common/scripted_triggers/cm_food_auto_build_triggers.txt", "fishing villages on rivers", _fishing_on_rivers),
    (QUEUE, "poll the queue every second, not every 0.3 s", _slow_the_poll),
    (QUEUE, "shout only into queues with entries", _gate_scan_shouts),
    (FEATURE, "count the ready-polls and log each cycle", _count_rounds_init),
    (HIDDEN_GUIS, "count each ready-poll", _count_rounds),
    (TRMM_VALUES, "score the rights per province, as cm_maps 0.3.0", _province_scored),
    (MISC_VALUES, "retire the rights stored the old way", _retire_trmm),
    (ATR, "grant the 1.4 charters until the royal rights open", _grant_charters),
    (ATR_TRIGGERS, "a charter is a specialization", _charter_counts),
    (ATR_ALLOW, "the textile charter's Flemish gate", _charter_allow),
    (FEATURE, "run the draw once the charters are open", _charter_gate),
    (FEATURE, "a debug.log line for every approved build", _probe_each_build),
    (APPROVAL, "name the approving pass for the build probe", _probe_feature_names),
)


CM_ACTIVE = "GetScriptedGui('glorpui_is_cm_active').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End)"
VANILLA_TOGGLE = re.compile(r'on_action = "\[(?:ToggleAutoExpand\w*\(|\w+LateralView\.ToggleAutoExpandAll\w*\])')
RGO_FLAG_ICON = 'visible = "[IsAutoExpandRGO(Location.Self)]"\n'


def _gate_vanilla_toggles(text: str) -> tuple[str, int]:
    """Hide the game's own auto-expand toggles while CM runs (his words 10-04:
    «Ванильная автостройка при включёном cm вообще должна быть заблокирована»).

    CM hides vanilla's checkboxes behind `glorpui_is_cm_active` and puts its own
    beside them; the beta added Alt+click toggles to the RGO and building
    buttons, and Río's RGO button marks a vanilla-flagged RGO with an icon, and
    neither was gated. Every `action_tooltip` whose action is a vanilla toggle
    gets the gate, and so does that icon.
    """
    out, n, at = [], 0, 0
    for m in re.finditer(r"action_tooltip = \{", text):
        if m.start() < at:
            continue
        depth, end = 0, m.end() - 1
        for end in range(m.end() - 1, len(text)):
            depth += {"{": 1, "}": -1}.get(text[end], 0)
            if depth == 0:
                break
        block = text[m.start():end + 1]
        if VANILLA_TOGGLE.search(block) and "glorpui_is_cm_active" not in block:
            seen = re.search(r'^([ \t]*)visible = "\[(.*)\]"$', block, flags=re.M)
            if seen:
                block = (block[:seen.start()] + f'{seen.group(1)}visible = "[And({seen.group(2)}, Not({CM_ACTIVE}))]"'
                         + block[seen.end():])
            else:
                indent = re.search(r"\n([ \t]*)\S", block).group(1)
                block = block.replace("{\n", f'{{\n{indent}visible = "[Not({CM_ACTIVE})]"\n', 1)
            n += 1
        out.append(text[at:m.start()] + block)
        at = end + 1
    text = "".join(out) + text[at:]
    for m in reversed(list(re.finditer(re.escape(RGO_FLAG_ICON) + r'[ \t]*texture = "gfx/interface/icons/flat_icons/mass_upgrade.dds"', text))):
        gated = f'visible = "[And(IsAutoExpandRGO(Location.Self), Not({CM_ACTIVE}))]"\n'
        text = text[:m.start()] + gated + text[m.start() + len(RGO_FLAG_ICON):]
        n += 1
    return text, n


# Bump with every change to what cm_rio_patch ships; `mods.bat` compares it.
RIO_PATCH_REVISION = 4


def _rio_patch() -> str:
    """mods/cm_rio_patch: Glorp UI Río's own windows with the CM hooks Río lacks.

    In 1.3 Glorp UI's windows carried every CM hook and CM loaded before it (his
    words 10-04: «всё было на месте… CM должен был идти перед glorpui»). Río,
    Glorp UI for 1.4, carries most of them but not CM's auto-food and RGO
    auto-expand toggles on the location window's RGO button, nor CM's toggle on
    a built building in the production view, where it shows the game's own.
    This mod is Río's file plus exactly those hooks (`tools/rio_patch/`), built
    from the Río in `reference/` and loaded right after Río.
    """
    rio_root = refs.mod("glorp.ui.rio")
    rio = rio_root / "in_game/gui"
    for name in ("in_game", ".metadata"):
        if (RIO_PATCH / name).exists():
            shutil.rmtree(RIO_PATCH / name)
    out = RIO_PATCH / "in_game/gui"
    out.mkdir(parents=True)
    gated = 0
    for spec in sorted(RIO_SPECS.glob("*.json")):
        window = spec.stem + ".gui"
        text = (rio / window).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        text = beta.apply(text, json.loads(spec.read_text(encoding="utf-8")), window, refs.GAME_GUI)
        text, n = _gate_vanilla_toggles(text)
        gated += n
        (out / window).write_text("﻿" + text, encoding="utf-8")
    # 1.4.x took `use_global_input_instance` out of the engine (the game's own
    # diplomacydialogs.gui says so in a comment); Río still sets it, and every
    # one is «untyped is not a valid type» in error.log (10-20, 1.4.2: 34 a
    # load). His word: fix it here, leave Glorp's own mod alone until its author
    # catches up. Río's files that carry it, copied whole minus that line; a
    # file a spec above already rebuilt is cleaned in place.
    stripped = 0
    for src in sorted(rio_root.rglob("*.gui")):
        raw = src.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        if not re.search(r"(?m)^\s*use_global_input_instance = yes\s*$", raw):
            continue
        rel = src.relative_to(rio_root)
        dest = RIO_PATCH / rel
        base = dest.read_text(encoding="utf-8-sig") if dest.exists() else raw
        lines = base.split("\n")
        kept = [ln for ln in lines if ln.strip() != "use_global_input_instance = yes"]
        stripped += len(lines) - len(kept)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("﻿" + "\n".join(kept), encoding="utf-8")
    print(f"cm_rio_patch: {stripped} dead use_global_input_instance lines dropped from Río's windows")
    rio_meta = json.loads((rio_root / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    meta = {
        "name": "CM Perf x Glorp UI Rio",
        "id": "bag.cm_rio_patch",
        "version": f"0.1.{RIO_PATCH_REVISION}",
        "game_id": "eu5",
        "supported_game_version": "1.*",
        "short_description": (
            f"Glorp UI Rio's location and production windows (built on its {rio_meta.get('version')}) with "
            "Construction Manager's auto-food, RGO auto-expand and building auto-expand toggles, and the "
            "game's own auto-expand toggles hidden while CM runs. Load right after Glorp UI Rio; "
            "Construction Manager Dev (perf) goes before Rio."),
        "tags": ["User Interface", "Utilities"],
        "relationships": [],
        "game_custom_data": {},
    }
    (RIO_PATCH / ".metadata").mkdir()
    (RIO_PATCH / ".metadata/metadata.json").write_text(
        "﻿" + json.dumps(meta, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    return f"{', '.join(p.stem for p in sorted(RIO_SPECS.glob('*.json')))} on Río {rio_meta.get('version')}, {gated} vanilla toggles gated"


# **Raise with every change to what this mod ships** (his rule, 2026-09-27):
# `mods.bat` compares this number with the one installed in the game, and a
# refresh rewrites `.metadata` from here — a bump made by hand there is lost.
PERF_REVISION = 60

# CMF's own `is_host`, under a name neither the game nor any CMF build takes.
# It reads the host country CMF 2.5.0 records (`_cmm_mark_host_country`), so
# CMF from the Workshop is all it needs.
HOST_TRIGGER = """# cm_dev_perf: CMF's is_host under CM's own name. The game's 1.4 trigger
# is_host shadows CMF's, and cmf_is_host exists only in cmf_dev_beta.
# True when this country is controlled by the host player, or in singleplayer.
# Scope: country
cm_is_host = {
\ttrigger_if = {
\t\tlimit = { has_multiple_players = no }
\t\tis_human = yes
\t}
\ttrigger_else = {
\t\ttrigger_if = {
\t\t\tlimit = { has_global_variable = cmf_core_host_country }
\t\t\tthis ?= global_var:cmf_core_host_country
\t\t}
\t\ttrigger_else = {
\t\t\talways = no
\t\t}
\t}
}
"""


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
    _write_subsidy_desc()
    _chip_words()
    _split_glorp_shared()
    # The beta's buildings and National Destinies' in Custom auto-build (buildings.py).
    buildings.vanilla_checks(refs.GAME / "in_game/common/building_types")
    # Other mods' buildings are found by the game at load (buildings.Others, his word 10-20).
    nd = buildings.Others(refs.GAME / "in_game/common/building_types")
    (MOD / "in_game/common/scripted_triggers/cm_perf_buildings_triggers.txt").write_text(
        buildings.scripted_triggers(), encoding="utf-8")
    (MOD / "in_game/common/customizable_localization").mkdir(parents=True, exist_ok=True)
    (MOD / "in_game/common/customizable_localization/cm_perf_buildings_custom_loc.txt").write_text(
        buildings.custom_localization(), encoding="utf-8")
    (MOD / "in_game/common/scripted_effects/cm_perf_buildings_effects.txt").write_text(
        buildings.effects(nd, (MOD / CUSTOM).read_text(encoding="utf-8-sig")), encoding="utf-8")
    (MOD / "in_game/common/scripted_guis/cm_perf_buildings_scripted_gui.txt").write_text(
        buildings.scripted_guis(), encoding="utf-8")
    (MOD / PF_VIEW).write_text(_pf_view_effects(), encoding="utf-8")
    (MOD / AB_FOOD_VALUES).write_text(AB_FOOD_VALUES_TEXT, encoding="utf-8")
    (MOD / AB_PROD_FILE).write_text(_ab_prod_values(), encoding="utf-8")
    (MOD / AB_PROD_TRIGGERS).write_text(AB_PROD_TRIGGERS_TEXT, encoding="utf-8")
    (MOD / CLEANUP_TRIGGERS).write_text(CLEANUP_TRIGGERS_TEXT, encoding="utf-8")
    (MOD / CLEANUP_VALUES).write_text(CLEANUP_VALUES_TEXT, encoding="utf-8")
    for path, text in _industry_files().items():
        (MOD / path).parent.mkdir(parents=True, exist_ok=True)
        (MOD / path).write_text("\ufeff" + text, encoding="utf-8")
    shutil.copy2(MOD / "main_menu/gfx/interface/icons/map_modes/cm_best_town_right.dds",
                 MOD / "main_menu/gfx/interface/icons/map_modes/cm_industry_support.dds")
    for folder in sorted((MOD / "main_menu/localization").iterdir()):
        lang = folder.name
        rows = folder / f"cm_cmm_l_{lang}.yml"
        rows.write_text("\ufeff" + buildings.edit_row_names(rows.read_text(encoding="utf-8-sig")), encoding="utf-8")
        (folder / f"cm_perf_buildings_l_{lang}.yml").write_text(buildings.localization(lang), encoding="utf-8")
    # 10-01: CM Dev's copies of vanilla windows are Glorp UI's 1.3 layout and
    # break on the beta; each with a spec in tools/beta/ is rebuilt as the
    # beta's window plus CM's hooks (beta_windows.py).
    rebuilt = beta.rebuild(refs.GAME_GUI, BETA_SPECS, MOD / "in_game/gui")
    # 10-04 night, his call: «не хотелось бы, чтобы наш мод перезаписывал окна интерфейса
    # glorp… аккуратно встраивался в glorp, если он включён». Glorp UI Río replaces three of the
    # same windows and carries CM's hooks itself; this mod ships the beta's windows with CM's
    # hooks and loads ABOVE Río, so with Río on Río's own windows win whole and without it these
    # do. (+perf11..19 shipped Río's file plus the hooks it lacks and loaded below it.) What Río
    # lacks, Río's file plus those hooks, is mods/cm_rio_patch, loaded right after Río (_rio_patch).
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
    # Compared as objects here too (+perf15), and against `GetPlayer`: his
    # probe run 10-04 17:33 in that row, `ObjectsEqual(Location.GetOwner,
    # GetPlayer)` true and the same against `Player.Self` false (+perf18).
    owner_gate = "EqualTo_string(Location.GetOwner.GetTag, GetPlayer.GetTag)"
    owner_gates = 0
    for path in (MOD / "in_game/gui").rglob("*.gui"):
        text = path.read_text(encoding="utf-8-sig")
        if owner_gate in text:
            owner_gates += text.count(owner_gate)
            path.write_text("\ufeff" + text.replace(owner_gate, "ObjectsEqual(Location.GetOwner, GetPlayer)"),
                            encoding="utf-8")
    if not owner_gates:
        raise SystemExit("the tag-compare owner gate is gone from CM's windows; drop this pass")
    gated = 0
    for path in (MOD / "in_game/gui").rglob("*.gui"):
        text = path.read_text(encoding="utf-8-sig")
        text, n = _gate_vanilla_toggles(text)
        if n:
            gated += n
            path.write_text("\ufeff" + text.lstrip("\ufeff"), encoding="utf-8")
    patch = _rio_patch()
    # The beta added a native trigger `is_host`, CMF's own trigger's name; CM's
    # host gates (the classification among them, his run 10-02: never ran) go
    # to cm_is_host, our own copy of CMF's body (+perf50). It was cmf_is_host,
    # which only cmf_dev_beta defines: with CMF from the Workshop the
    # classification, the upgrade-map refresh and the host setting stood still.
    hosts = 0
    for path in (MOD / "in_game/common").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig")
        text, n = re.subn(r"^([ \t]*(?:limit = \{ )?)is_host(\s*=\s*(?:yes|no)\b)",
                          r"\1cm_is_host\2", text, flags=re.M)
        if n:
            hosts += n
            path.write_text("\ufeff" + text, encoding="utf-8")
    if not hosts:
        raise SystemExit("CM no longer calls is_host; drop the cm_is_host pass")
    # +perf52: every RGO level CM orders says so in debug.log (his run 10-26:
    # a wave of RGO builds the build probe did not see, RGOs being no building).
    rgo_sites = 0
    for path in sorted((MOD / "in_game/common/scripted_effects").glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        calls = iter(range(1, 100))
        text, n = re.subn(r"^([ \t]*)(construct_rgo_upgrade = \{ \})",
                          lambda m: f"{m.group(1)}cm_perf_rgo_probe = {{ SITE = {path.stem}_{next(calls)} }}"
                                    f" # cm_dev_perf +perf52\n{m.group(1)}{m.group(2)}", text, flags=re.M)
        if n:
            rgo_sites += n
            path.write_text("﻿" + text, encoding="utf-8")
    if not rgo_sites:
        raise SystemExit("CM no longer calls construct_rgo_upgrade; drop the RGO probe")
    _his_pop_rule()
    (MOD / "in_game/common/scripted_triggers/cm_perf_host_triggers.txt").write_text(
        "\ufeff" + HOST_TRIGGER, encoding="utf-8")
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
    # Files of ours that ship beside CM's (since +perf45 only the log mirror's
    # script values); their sources live in tools/probe/ so this rebuild does
    # not wipe them.
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
    print(f"cm_dev_perf: {gated} vanilla auto-expand toggles gated on CM; cm_rio_patch: {patch}")
    print("cm_dev_perf: other mods' buildings found at load; the game's own files name %d types"
          % len(nd.vanilla))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
