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


# CM turns the game's own building automation off only on load and on a change
# of country, so one switched on mid-game (the Production tab's right click,
# say) builds beside CM until the next load: his castles of 10-05, and his words
# 10-04, «Ванильная автостройка при включёном cm вообще должна быть
# заблокирована и не работать». Each month puts it back off. «Добыча
# ресурсов» (`rgo`) stays his: +perf25 switched it off too and he had it taken
# out (10-04 23:16, «не нужно, чтобы мне принудительно выключали что-то, что
# можно использовать не мешая остальному»).
AUTOMATION_PULSE = """\ufeff# Generated by mods/cm_dev_perf/tools/port_from_cm_dev.py; not to be edited by hand.
# A bare on_action key merges with the existing definition rather than replacing it.
cmf_monthly_human_country_pulse = {
	on_actions = {
		cm_perf_automation_monthly_pulse
	}
}

# Root is the country.
cm_perf_automation_monthly_pulse = {
	effect = {
		cm_perf_council_probe = { WHEN = before }
		cm_suppress_engine_automation = yes
		cm_perf_council_probe = { WHEN = after }
		cm_perf_council_actions_back = yes
	}
}
"""

# Temporary probe (+perf28, 10-05): every council seat stopped getting new
# actions, with and without assimilate_primary, and nothing in the logs. Each
# month, before and after CM switches its five building automations off, this
# writes to debug.log which council automations the game reads as on and which
# seats hold an action. Remove once one run has answered.
COUNCIL_PROBE = "in_game/common/scripted_effects/cm_perf_council_probe_effects.txt"


def _council_probe() -> str:
    flags = "".join(
        f"\tif = {{ limit = {{ is_system_automated = {sys} }} debug_log = \"CM council probe $WHEN$: {sys} on\" }}\n"
        f"\telse = {{ debug_log = \"CM council probe $WHEN$: {sys} off\" }}\n"
        for sys in ("cabinet", "cabinetactions", "cabinetmembers"))
    return ("\ufeff# Generated by mods/cm_dev_perf/tools/port_from_cm_dev.py; not to be edited by hand.\n"
            "# Temporary probe (+perf28): council automation flags and idle seats in debug.log.\n"
            "# Root is the country.\n"
            "cm_perf_council_probe = {\n"
            + flags +
            "\tevery_cabinet = {\n"
            "\t\tif = { limit = { has_cabinet_action = yes } debug_log = \"CM council probe $WHEN$: seat busy\" }\n"
            "\t\telse = { debug_log = \"CM council probe $WHEN$: seat idle\" }\n"
            "\t}\n"
            "}\n\n"
            "# His run 10-05 08:09: «Совет» on, «Члены совета» on, the hidden «Действия совета»\n"
            "# (cabinetactions) off, so seats are filled and never given an action. The panel has\n"
            "# no switch for it. Put back once, where the panel's «Совет» is on; the probe then\n"
            "# shows whether something turns it off again.\n"
            "cm_perf_council_actions_back = {\n"
            "\tif = {\n"
            "\t\tlimit = {\n"
            "\t\t\tis_ai = no\n"
            "\t\t\tNOT = { has_variable = cm_perf_council_actions_back }\n"
            "\t\t\tis_system_automated = cabinet\n"
            "\t\t\tNOT = { is_system_automated = cabinetactions }\n"
            "\t\t}\n"
            "\t\tset_variable = cm_perf_council_actions_back\n"
            "\t\tset_automated_system = { system = cabinetactions activate = yes }\n"
            "\t\tdebug_log = \"CM council probe: cabinetactions switched back on\"\n"
            "\t}\n"
            "}\n")


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
    (CUSTOM, "the beta's capital buildings, and the National Destinies list's set", buildings.edit_custom_sets),
    ("in_game/common/scripted_triggers/cm_ab_triggers.txt", "subject candidates for the National Destinies list",
     buildings.edit_subjects_wanted),
    ("in_game/common/scripted_effects/cm_ab_production_effects.txt", "the Production tab skips National Destinies'",
     buildings.edit_production_skip),
    (SEED, "the National Destinies set listed at load", buildings.edit_populate),
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
RIO_PATCH_REVISION = 1


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
PERF_REVISION = 29


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
    _split_glorp_shared()
    # The beta's buildings and National Destinies' in Custom auto-build (buildings.py).
    buildings.vanilla_checks(refs.GAME / "in_game/common/building_types")
    try:
        nd_root = refs.mod("trin.national_destinies")
    except SystemExit:
        nd_root = None
    nd = buildings.ND(nd_root)
    if nd.most_rows() > buildings.ND_ROWS:
        raise SystemExit(f"National Destinies: a country can claim {nd.most_rows()} rows, the list has {buildings.ND_ROWS}")
    if nd.most_rows() > buildings.INFO_ROWS:
        raise SystemExit(f"National Destinies: a country has {nd.most_rows()} buildings, the info list {buildings.INFO_ROWS} rows")
    (MOD / "in_game/common/scripted_triggers/cm_perf_buildings_triggers.txt").write_text(
        buildings.scripted_triggers(), encoding="utf-8")
    (MOD / "in_game/common/customizable_localization").mkdir(parents=True, exist_ok=True)
    (MOD / "in_game/common/customizable_localization/cm_perf_buildings_custom_loc.txt").write_text(
        buildings.custom_localization(), encoding="utf-8")
    (MOD / "in_game/common/scripted_effects/cm_perf_buildings_effects.txt").write_text(
        buildings.effects(nd, (MOD / CUSTOM).read_text(encoding="utf-8-sig")), encoding="utf-8")
    (MOD / "in_game/common/scripted_guis/cm_perf_buildings_scripted_gui.txt").write_text(
        buildings.scripted_guis(), encoding="utf-8")
    (MOD / "in_game/common/on_action/cm_perf_automation_on_actions.txt").write_text(AUTOMATION_PULSE, encoding="utf-8")
    (MOD / COUNCIL_PROBE).write_text(_council_probe(), encoding="utf-8")
    (MOD / PF_VIEW).write_text(_pf_view_effects(), encoding="utf-8")
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
    print(f"cm_dev_perf: {gated} vanilla auto-expand toggles gated on CM; cm_rio_patch: {patch}")
    print("cm_dev_perf: National Destinies %s: %d buildings for its list (at most %d rows a country)"
          % ("read" if nd_root else "absent", nd.count(), nd.most_rows()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
