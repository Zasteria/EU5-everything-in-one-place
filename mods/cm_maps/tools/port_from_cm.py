#!/usr/bin/env python3
"""Rebuilds `cm_maps` out of Construction Manager dev.

Three of CM's map modes, lifted whole: location food potential, recommended
urban rights (with its nine per-right children) and recommended governor
placement. **Copied as files, not reproduced as formulas** — the rule from
`docs/archive/wtp2_failed.md`, which one failed attempt paid for. Nothing here
edits a number, a colour or a threshold; it renames `cm_` to `bcm_`, drops the
blocks that belong to parts of CM this mod does not carry, and makes the five
wiring changes listed in `EDITS` below, each of which is there because CM's own
wiring runs through CMF and the rest of CM.

    python3 mods/cm_maps/tools/port_from_cm.py

Run from `tools/refresh.py` with the other generators. It reads
`reference/mods/<construction manager dev>/` and writes `mods/cm_maps/`, then
checks that nothing it emitted refers to a `bcm_` name it did not also emit —
a dangling reference is how a silent effect happens, and CM is big enough that
one is easy to leave behind.
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/cm_maps"
SRC = refs.mod("romaimperator.construction_manager.dev", "construction_manager_dev")

LANGUAGES = ("russian", "english")

BOM = "﻿"


# ---------------------------------------------------------------- block parsing

class Block:
    """One top-level `name = { ... }`, with the comment lines written above it."""

    def __init__(self, name: str, lead: list[str], body: list[str]) -> None:
        self.name = name
        self.lead = lead
        self.body = body

    @property
    def text(self) -> str:
        return "\n".join(self.lead + self.body)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse(path: Path) -> tuple[list[str], list[Block]]:
    """The file's preamble (comments and `@constants`) and its top-level blocks.

    Depth is counted on comment-stripped lines, because CM's own comments quote
    braces often enough that counting them would end a block early.
    """
    lines = read(path).split("\n")
    preamble: list[str] = []
    blocks: list[Block] = []
    lead: list[str] = []
    name: str | None = None
    body: list[str] = []
    depth = 0

    for line in lines:
        if name is None:
            opened = re.match(r"^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{", line)
            if opened:
                name = opened.group(1)
                body = [line]
                depth = _delta(line)
                if depth <= 0:
                    blocks.append(Block(name, lead, body))
                    lead, name, body = [], None, []
                continue
            if line.strip() == "" and lead and lead[-1].strip() == "":
                preamble.extend(lead)
                lead = []
                preamble.append(line)
                continue
            lead.append(line)
            continue

        body.append(line)
        depth += _delta(line)
        if depth <= 0:
            blocks.append(Block(name, lead, body))
            lead, name, body = [], None, []

    # Trailing comment lines that opened no block belong to the file, not a block.
    preamble.extend(lead)
    return preamble, blocks


def _delta(line: str) -> int:
    bare = re.sub(r"#.*", "", line)
    return bare.count("{") - bare.count("}")


# ------------------------------------------------------------------- the rename

IDENT = re.compile(r"\b(cm_[A-Za-z0-9_]*)\b")
IDENT_UPPER = re.compile(r"\b(CM_[A-Za-z0-9_]*)\b")


def rename(text: str) -> str:
    """`cm_x` -> `bcm_x`, in both cases, everywhere.

    Every name this mod carries is renamed, not only the definitions: a variable
    CM parks on a location, a saved scope, a map mode, a scripted gui and a
    localization key are all `cm_`-prefixed, and leaving any of them alone would
    make this mod and Construction Manager write over each other whenever both
    are loaded. `cmm_` (CMF's macros) and `cmf_` do not match: the pattern wants
    an underscore third.
    """
    text = IDENT.sub(lambda m: "b" + m.group(1), text)
    text = IDENT_UPPER.sub(lambda m: "B" + m.group(1), text)
    # The engine builds a map mode's name and tooltip keys itself, as
    # `mapmode_<mode>_name` and `MAPMODE_<MODE>`. There is no word boundary in
    # front of the `cm_` in those, so the two passes above walk straight past
    # them — and a mode whose name key is missing shows its raw key in the
    # flyout.
    text = text.replace("mapmode_cm_", "mapmode_bcm_")
    return text.replace("MAPMODE_CM_", "MAPMODE_BCM_")


def unrenamed(text: str) -> set[str]:
    """CM names left behind by `rename`, outside comments.

    A miss here does not fail: it silently keeps CM's own name, which either
    reads CM's data when CM is loaded or reads nothing when it is not. Both are
    invisible, so the port refuses to finish with one.
    """
    code = re.sub(r"#[^\n]*", "", text)
    return set(re.findall(r"(?<![A-Za-z0-9_b])(?:cm|CM)_[A-Za-z0-9_]*", code)) | {
        m for m in re.findall(r"[A-Za-z0-9]_((?:cm|CM)_[A-Za-z0-9_]*)", code)
    }


# ---------------------------------------------------------------- what is taken
#
# WHOLE: every block of the file, minus DROP.
# PARTIAL: only the blocks named, in the file's own order.
#
# The dropped families, and why each is not here:
#   cm_trmm_grant_*, cm_trmm_enable_expands_*  CM's grant panel and its
#       auto-build follow-through. Granting a charter from the map is CM's
#       feature, not a map, and it reaches into auto-build, foreign building
#       and the charter-cost settings — five files this mod would otherwise
#       have to carry.
#   cm_capital_finder(+_hidden)  the placement finder's other map. The engine
#       that scores it stays (it is the same code the governor map runs), but
#       the mode is not published and nothing ever views it, so the capital
#       half never runs.
#   cm_breadbasket, cm_location_food_potential_hidden  the auto-food map, and
#       a duplicate CM swaps through to force a repaint. Neither has anything
#       to read without CM's auto-food.

WHOLE: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # (source, destination, blocks to drop)
    ("in_game/common/script_values/cm_town_right_map_mode_script_values.txt",
     "in_game/common/script_values/bcm_trmm_values.txt", ()),
    ("in_game/common/script_values/cm_proximity_finder_script_values.txt",
     "in_game/common/script_values/bcm_pf_values.txt", ()),
    ("in_game/common/script_values/cm_proximity_finder_generated_values.txt",
     "in_game/common/script_values/bcm_pf_generated_values.txt", ()),
    ("in_game/common/scripted_effects/cm_town_right_map_mode_effects.txt",
     "in_game/common/scripted_effects/bcm_trmm_effects.txt",
     ("cm_trmm_enable_expands_",)),
    ("in_game/common/scripted_effects/cm_proximity_finder_effects.txt",
     "in_game/common/scripted_effects/bcm_pf_effects.txt", ()),
    ("in_game/common/scripted_triggers/cm_town_right_map_mode_triggers.txt",
     "in_game/common/scripted_triggers/bcm_trmm_triggers.txt", ()),
    ("in_game/common/scripted_guis/cm_town_right_map_mode_scripted_guis.txt",
     "in_game/common/scripted_guis/bcm_trmm_scripted_guis.txt",
     ("cm_trmm_grant_",)),
    ("in_game/common/scripted_guis/cm_proximity_finder_scripted_gui.txt",
     "in_game/common/scripted_guis/bcm_pf_scripted_guis.txt",
     ("cm_pf_prep_cap",)),
    ("in_game/common/customizable_localization/cm_town_right_map_mode_custom_loc.txt",
     "in_game/common/customizable_localization/bcm_trmm_custom_loc.txt", ()),
    ("in_game/common/customizable_localization/cm_proximity_finder_custom_loc.txt",
     "in_game/common/customizable_localization/bcm_pf_custom_loc.txt", ()),
)

PARTIAL: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    # (source, destination, blocks to take)
    ("in_game/common/script_values/cm_filter_script_values.txt",
     "in_game/common/script_values/bcm_shared_values.txt",
     ("cm_location_raw_wealth",
      "cm_location_food_potential_food_multiplier",
      "cm_location_food_potential_raw_output_multiplier",
      "cm_location_food_potential_live",
      "cm_location_food_potential",
      "cm_location_topography_proximity_modifier",
      "cm_location_vegetation_proximity_modifier",
      "cm_location_proximity_modifier")),
    ("in_game/common/script_values/cm_gov_script_values.txt",
     "in_game/common/script_values/bcm_gov_values.txt",
     ("cm_gov_replan_source_value",)),
    ("in_game/common/scripted_triggers/cm_map_mode_triggers.txt",
     "in_game/common/scripted_triggers/bcm_map_mode_triggers.txt",
     ("cm_pf_method_is_tax_base",
      "cm_pf_method_is_population",
      "cm_pf_roads_is_current",
      "cm_pf_roads_is_best_possible",
      "cm_pf_naval_is_current_presence",
      "cm_pf_naval_is_optimal_harbor",
      "cm_pf_river_data_is_current",
      "cm_pf_location_is_lake",
      "cm_location_has_road_or_river")),
    ("in_game/common/scripted_triggers/cm_gov_triggers.txt",
     "in_game/common/scripted_triggers/bcm_gov_triggers.txt",
     ("cm_gov_site_is_naval",
      "cm_gov_site_blocks_land_governor",
      "cm_gov_site_can_take_governor",
      "cm_gov_site_eligible")),
    ("in_game/common/scripted_triggers/cm_atr_ur_triggers.txt",
     "in_game/common/scripted_triggers/bcm_atr_ur_triggers.txt",
     ("cm_atr_ur_has_no_specialization",)),
    ("in_game/common/scripted_triggers/cm_mass_upgrade_triggers.txt",
     "in_game/common/scripted_triggers/bcm_mass_upgrade_triggers.txt",
     ("cm_location_rgo_blocks_urbanize", "cm_location_deurbanize_would_undo")),
    ("in_game/common/scripted_triggers/cm_setup_triggers.txt",
     "in_game/common/scripted_triggers/bcm_setup_triggers.txt",
     ("cm_trmm_data_is_current", "cm_fpot_data_is_current")),
    ("in_game/common/scripted_effects/cm_game_load_setup_effects.txt",
     "in_game/common/scripted_effects/bcm_lobby_effects.txt",
     ("cm_pf_populate_river_locations", "cm_fpot_recompute_all")),
    ("in_game/common/scripted_guis/cm_hidden_window_scripted_gui.txt",
     "in_game/common/scripted_guis/bcm_river_scripted_guis.txt",
     ("cm_pf_river_should_process", "cm_pf_river_record", "cm_pf_river_fill_batch")),
    ("in_game/common/scripted_guis/cm_trmm_grant_scripted_guis.txt",
     "in_game/common/scripted_guis/bcm_trmm_refresh_scripted_guis.txt",
     ("cm_trmm_refresh_pending", "cm_trmm_ack_refresh")),
)

# Bare `name = <number>` values, which are not blocks and so are lifted by line.
# Both are the stamps the two lobby passes compare against; bumping one in CM is
# how a CM update tells every save to redo that pass, and this port must carry
# the bump or it would keep serving data CM has decided is stale.
SCALARS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("in_game/common/script_values/cm_misc_script_values.txt",
     "in_game/common/script_values/bcm_version_values.txt",
     ("cm_trmm_version_value", "cm_fpot_version_value")),
)

MAP_MODES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("in_game/gfx/map/map_modes/cm_food_map_modes.txt",
     "in_game/gfx/map/map_modes/bcm_food_map_mode.txt",
     ("cm_location_food_potential",)),
    ("in_game/gfx/map/map_modes/cm_town_right_map_mode.txt",
     "in_game/gfx/map/map_modes/bcm_town_right_map_modes.txt",
     ()),  # empty = every block
    ("in_game/gfx/map/map_modes/cm_proximity_finder_map_modes.txt",
     "in_game/gfx/map/map_modes/bcm_governor_finder_map_mode.txt",
     ("cm_governor_finder", "cm_governor_finder_hidden")),
)

GUI: tuple[tuple[str, str], ...] = (
    ("in_game/gui/cm_town_rights_search_panel.gui",
     "in_game/gui/bcm_town_rights_search_panel.gui"),
)

ICONS = (
    "cm_best_town_right",
    "cm_location_food_potential",
    "cm_governor_finder",
    "cm_trmm_search_tooling",
    "cm_trmm_search_jewelry",
    "cm_trmm_search_naval",
    "cm_trmm_search_textile",
    "cm_trmm_search_weaponry",
    "cm_trmm_search_book",
    "cm_trmm_search_artisan",
    "cm_trmm_search_brewing",
    "cm_trmm_search_masonry",
)

LOCALIZATION = (
    ("cm_town_right_map_mode", "bcm_trmm"),
    ("cm_town_right_map_mode_static", "bcm_trmm_static"),
    ("cm_food_map_modes", "bcm_food_map_mode"),
    ("cm_proximity_finder", "bcm_pf"),
)


# ------------------------------------------------------------------ the rewires
#
# Everything else in this port is a rename. These are changes of behaviour, and
# each is here because CM's own wiring runs through CMF, through a part of CM
# this mod does not carry, or -- in the last one -- through a CM fault the port
# is not obliged to inherit. Applied to the renamed text, and each one asserts
# it matched, so a CM update that moves the line fails the build instead of
# quietly dropping the rewire.

EDITS: tuple[tuple[str, str, str, str], ...] = (
    # (destination file, what it was, what it becomes, why)
    # **Search Accuracy is left at CM's fallback of 1 (Exhaustive), and that is a
    # correction, not an oversight.** An earlier build rewired it to 3, reasoning
    # that 3 is the CMF dropdown's default and therefore what a CM player gets.
    # It is — because a CM player can move the dropdown. Here nothing can: there
    # is no settings page, so the fallback is not a fallback, it is the only
    # value the mod will ever use. Tiers 2-5 route through the phased runner,
    # which leaves locations unevaluated and paints them black under
    # `bcm_pf_tt_skipped` — a tooltip that tells the player to set Accuracy to
    # Exhaustive and refresh. With no settings page that is a dead end, and it is
    # what the first run of this mod reported: black patches over the empire and
    # a tooltip pointing at a setting that does not exist (docs/TESTLOG.md,
    # 2026-09-19). Tier 1 is the one path that skips nothing. It is also the
    # slowest, which is the price; the map fills in batches on open, so it costs
    # fill time, not a loading screen.

    # CM fires this from cm_on_init_human_country so the governor map is already
    # filled in the first time it is opened. That on_action is CMF's, and the
    # engine has no load hook of its own that reaches a country, so nothing here
    # calls it. Opening the map runs the same search through bcm_pf_prep_gated
    # instead, in batches rather than in one synchronous block — a map that fills
    # in over a few seconds instead of a loading screen that sits a few seconds
    # longer. The effect is kept rather than cut: it is CM's, it is correct, and
    # a CMF-aware version of this mod would want it back.
    ("in_game/common/scripted_effects/bcm_pf_effects.txt",
     "bcm_pf_recompute_now = {\n",
     "# NOT WIRED UP in this mod. CM calls it from cm_on_init_human_country, which\n"
     "# is one of CMF's on_actions; there is no CMF here and no engine load hook\n"
     "# that reaches a country, so the governor map computes on open instead.\n"
     "bcm_pf_recompute_now = {\n",
     "CM's load-time precompute is marked unwired"),

    # The magenta stripe marks a location CM's auto-food is farming. There is no
    # auto-food here, so the branch could only ever be false — and a branch that
    # is always false is worse than none: it reads like a feature.
    ("in_game/gfx/map/map_modes/bcm_food_map_mode.txt",
     "\tsecondary_map_color = {\n"
     "\t\tif = {\n"
     "\t\t\tlimit = {\n"
     "\t\t\t\towner ?= scope:actor\n"
     "\t\t\t\tbcm_location_is_auto_food_active = yes\n"
     "\t\t\t}\n"
     "\t\t\tvalue = rgb { 255 0 255 }\n"
     "\t\t}\n"
     "\t\telse_if = {\n",
     "\t# CM's first branch here striped the locations its auto-food was farming\n"
     "\t# magenta. That is CM's feature, not this map's, so only the grey for\n"
     "\t# foreign land is left.\n"
     "\tsecondary_map_color = {\n"
     "\t\tif = {\n",
     "the auto-food stripe is dropped"),
    ("in_game/gfx/map/map_modes/bcm_food_map_mode.txt",
     "\tlegend_key = {\n"
     "\t\tdesc = \"bcm_location_food_potential_auto_food_legend_key\"\n"
     "\t\tcolor = rgb { 255 0 255 }\n"
     "\t}\n",
     "",
     "and so is its legend row"),

    # A location whose best right scores zero is left unmarked. CM marks every
    # location in a province definition that cleared the entry gate, and the gate
    # takes a definition where *any* location has an input raw material **or** an
    # output bonus. Coverage is definition-wide, so the input half marks nobody
    # falsely; the output-bonus half does. A definition that qualified only on one
    # location's bonus leaves every other location with nine scores of zero, and
    # the encoding (round(score * 1000) * 10 + index, chained through `min`)
    # resolves an all-zero tie to the highest index -- 9, tooling. The location is
    # then painted royal_tooling_rights under a tooltip that prints its three
    # headings with nothing under any of them: the first run's "colour and a
    # window, empty description" (docs/TESTLOG.md, 2026-09-19). Unmarking sends it
    # to MAPMODE_BCM_BEST_TOWN_RIGHT_TT_NONE, whose text -- the province has no
    # raw materials specialized production uses -- is exactly true of it, because
    # a location scores zero only when its whole definition covers nothing.
    ("in_game/common/scripted_effects/bcm_trmm_effects.txt",
     "\t\t\t}\n\t\t}\n\t}\n\telse = {\n\t\tevery_province_in_province_definition = {",
     "\t\t\t\t# Only a location with a right worth naming is marked; see the note in\n\t\t\t\t# port_from_cm.py's EDITS. An all-zero encoding resolves to index 9 and\n\t\t\t\t# would paint the location as tooling under an empty tooltip, so it is\n\t\t\t\t# unmarked instead and falls to the map's no-data branch.\n\t\t\t\tif = {\n\t\t\t\t\t# enc below 10 = best score rounds to 0.\n\t\t\t\t\tlimit = { local_var:bcm_trmm_enc < 10 }\n\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { has_variable = bcm_trmm_best_idx }\n\t\t\t\t\t\tremove_variable = bcm_trmm_best_idx\n\t\t\t\t\t}\n\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { has_variable = bcm_trmm_best_mil }\n\t\t\t\t\t\tremove_variable = bcm_trmm_best_mil\n\t\t\t\t\t}\n\t\t\t\t\tif = {\n\t\t\t\t\t\tlimit = { has_variable = bcm_trmm_tie_idx }\n\t\t\t\t\t\tremove_variable = bcm_trmm_tie_idx\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n\telse = {\n\t\tevery_province_in_province_definition = {",
     "a location with no right worth naming is left unmarked"),

    # CM's setup log tells its own log pane that every load-time pass has
    # finished. There is no log pane here.
    ("in_game/common/scripted_guis/bcm_river_scripted_guis.txt",
     "\t\t\tbcm_log_setup_complete_if_ready = yes\n",
     "",
     "CM's setup-log line is dropped with the log pane"),
)


# ------------------------------------------------------------------- the writing

# Variables this port reads and never writes, and why each is sound. The reason
# goes on the line, which is `tools/check_script.py`'s own convention for a read
# it should stop asking about — and the rule it enforces is a real one: a
# variable with a reader, a remover and nobody to set it is what broke both of
# `where_to_produce`'s plan buttons in silence.
NEVER_SET: tuple[tuple[str, str], ...] = (
    ("bcm_pf_", "a macro-built name, bcm_pf_$RAW$ — there is no such variable"),
    ("bcm_gf_top", "written through a macro, as bcm_$M$_top in bcm_pf_rank_top"),
    ("bcm_cf_top", "written through a macro, as bcm_$M$_top in bcm_pf_rank_top"),
    ("bcm_pf_view_c",
     "the capital finder's view flag. Its one setter is bcm_pf_prep_cap, the "
     "scripted gui this port drops with the capital map; every read of it is an "
     "exists check, so the capital half simply never runs"),
    ("bcm_gov_replan",
     "CM's governor reorganization. Guarded by exists, and nothing here starts one"),
    ("bcm_gov_valid_only",
     "CM's Lucky Nations governor run. Guarded by exists, and nothing here starts one"),
    ("bcm_gov_plan_ord",
     "CM's governor planner's ordering. Guarded by has_variable"),
    ("bcm_gov_land_left",
     "CM's governor planner's budget, read from bcm_gov_site_eligible — which "
     "this mod reaches only through the bcm_gov_valid_only branch above, so it "
     "is never evaluated here"),
    ("bcm_gov_naval_left",
     "CM's governor planner's budget, read from bcm_gov_site_eligible — which "
     "this mod reaches only through the bcm_gov_valid_only branch above, so it "
     "is never evaluated here"),
    ("bcm_trmm_refresh_armed",
     "set by CM's grant effect, which goes with the grant panel. Nothing arms "
     "the repaint here, so its drivers sit idle"),
    ("bcm_placement_finder_accuracy",
     "a CMF setting. There is no settings page here; the exists check falls "
     "through to the default"),
    ("bcm_placement_finder_method",
     "a CMF setting. There is no settings page here; the exists check falls "
     "through to the default"),
    ("bcm_placement_finder_roads",
     "a CMF setting. There is no settings page here; the exists check falls "
     "through to the default"),
    ("bcm_placement_finder_naval",
     "a CMF setting. There is no settings page here; the exists check falls "
     "through to the default"),
    ("bcm_placement_finder_debug_path",
     "a CMF setting. There is no settings page here; the exists check falls "
     "through to the default"),
)

# Longest first: `bcm_pf_` is a prefix of `bcm_pf_view_c`, and an alternation
# takes the first arm that matches, not the longest.
READS = "|".join(re.escape(name)
                 for name, _ in sorted(NEVER_SET, key=lambda p: -len(p[0])))
READ_LINE = re.compile(
    rf"(?:(?:global_)?var:({READS})\b"
    rf"|has(?:_global)?_variable\s*=\s*({READS})\b)")


def mark_never_set(text: str) -> str:
    """Put `check-script: never set` on every read of one of those, with its reason."""
    reasons = dict(NEVER_SET)
    out = []
    for line in text.split("\n"):
        found = READ_LINE.search(re.sub(r"#.*", "", line))
        if found and "check-script:" not in line:
            name = found.group(1) or found.group(2)
            line = f"{line}  # check-script: never set — {reasons[name]}"
        out.append(line)
    return "\n".join(out)


def emit(path: Path, text: str) -> None:
    """Write with the BOM every script file in this game carries."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(BOM + text.lstrip(BOM), encoding="utf-8", newline="\n")


def header(source: str, note: str = "") -> str:
    lines = [
        "# Generated by mods/cm_maps/tools/port_from_cm.py - do not edit by hand.",
        f"# Lifted from Construction Manager dev, {source}.",
        "# Renamed cm_ -> bcm_ and nothing else; rebuild after a CM update.",
    ]
    if note:
        lines += ["#", *(f"# {line}" for line in note.split("\n"))]
    return "\n".join(lines) + "\n\n"


def take(source: str, keep: tuple[str, ...] = (), drop: tuple[str, ...] = ()) -> str:
    """The file's preamble plus the blocks asked for, renamed.

    `keep` names blocks exactly and orders the output by the file's own order;
    `drop` matches by prefix, because CM's droppable families are named that way
    (`cm_trmm_grant_*`), and a family that gains a member in a CM update must
    drop with the rest of it rather than arrive here unnoticed.
    """
    preamble, blocks = parse(SRC / source)
    wanted = []
    for block in blocks:
        if keep and block.name not in keep:
            continue
        if any(block.name.startswith(prefix) for prefix in drop):
            continue
        wanted.append(block)

    missing = set(keep) - {b.name for b in wanted}
    if missing:
        raise SystemExit(
            f"{source}: no block named {', '.join(sorted(missing))} — "
            "a CM update renamed or removed it, so this port is out of date."
        )

    body = "\n".join(block.text.rstrip("\n") for block in wanted)

    # Every `@name = value` the file declares, whether or not the blocks kept
    # happen to sit under it. The map mode files put their whole colour and
    # gradient palette in these, and a mode that reaches for one the output did
    # not carry is a parse error at load, not a missing colour. An unused one
    # costs nothing, so they all come.
    missing = [line for line in constants(SRC / source) if line not in body]

    lead = "\n".join(preamble).strip("\n")
    parts = [lead if not keep else "", "\n".join(missing), body]
    return rename("\n\n".join(p for p in parts if p.strip()))


def constants(path: Path) -> list[str]:
    """The file's top-level `@name = value` lines, in order."""
    out, depth = [], 0
    for line in read(path).split("\n"):
        if depth == 0 and re.match(r"^@[A-Za-z_][A-Za-z_0-9]*\s*=", line):
            out.append(line.rstrip("\r"))
        depth += _delta(line)
    return out


def take_scalars(source: str, names: tuple[str, ...]) -> str:
    """`name = <number>` lines, with the comment block written above each."""
    lines = read(SRC / source).split("\n")
    out: list[str] = []
    for name in names:
        at = next((i for i, line in enumerate(lines)
                   if re.match(rf"^{name}\s*=\s*[^{{]", line)), None)
        if at is None:
            raise SystemExit(
                f"{source}: no value named {name} — a CM update moved it, so this "
                "port is out of date."
            )
        top = at
        while top > 0 and lines[top - 1].lstrip().startswith("#"):
            top -= 1
        out.append("\n".join(lines[top:at + 1]))
    return rename("\n\n".join(out))


def apply_edits(written: dict[str, str]) -> None:
    for target, was, becomes, why in EDITS:
        if target not in written:
            raise SystemExit(f"rewire targets {target}, which this port does not write")
        if written[target].count(was) != 1:
            raise SystemExit(
                f"{target}: the rewire for «{why}» matched "
                f"{written[target].count(was)} times, not once. CM moved the line "
                "it patches; re-read it before trusting anything this port writes."
            )
        written[target] = written[target].replace(was, becomes)


# --------------------------------------------------------------------- checking

def defined_names(text: str) -> set[str]:
    return set(re.findall(r"^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{", text, re.M))


def check_dangling(written: dict[str, str], hand_written: dict[str, str]) -> list[str]:
    """`bcm_` names this mod refers to that CM defines but this mod does not.

    A name CM never defined is a variable, a saved scope or a localization key,
    and those are fine to carry. A name CM *did* define as a script block and
    this mod left behind is a call into nothing — which in this engine logs
    nothing and takes the rest of its effect with it.
    """
    cm_defs: set[str] = set()
    for folder in (SRC / "in_game/common").iterdir() if (SRC / "in_game/common").is_dir() else []:
        if not folder.is_dir():
            continue
        for path in folder.glob("*.txt"):
            cm_defs |= defined_names(read(path))

    ours: set[str] = set()
    for text in list(written.values()) + list(hand_written.values()):
        ours |= defined_names(text)

    # Comments are read past: CM's own comments cross-reference the rest of CM,
    # and a pointer to a file this mod does not carry is a note, not a call.
    used: set[str] = set()
    for text in list(written.values()) + list(hand_written.values()):
        code = re.sub(r"#.*", "", text)
        used |= set(re.findall(r"\b(bcm_[A-Za-z0-9_]*)\b", code))

    return sorted(n for n in used - ours if n[1:] in cm_defs)


# ------------------------------------------------------------------------ main

def main() -> int:
    written: dict[str, str] = {}

    for source, dest, drop in WHOLE:
        written[dest] = header(Path(source).name) + take(source, drop=drop)

    for source, dest, keep in PARTIAL:
        written[dest] = header(
            Path(source).name,
            "Only the blocks this mod's maps reach: " + ", ".join(
                "b" + k for k in keep),
        ) + take(source, keep=keep)

    for source, dest, names in SCALARS:
        written[dest] = header(Path(source).name) + take_scalars(source, names)

    for source, dest, keep in MAP_MODES:
        written[dest] = header(Path(source).name) + take(source, keep=keep)

    for source, dest in GUI:
        written[dest] = header(Path(source).name) + rename(read(SRC / source)).lstrip(BOM)

    apply_edits(written)

    hand = hand_written()
    written = {dest: mark_never_set(text) for dest, text in written.items()}
    for dest, text in {**written, **hand}.items():
        emit(MOD / dest, text)

    for name in ICONS:
        src = SRC / f"main_menu/gfx/interface/icons/map_modes/{name}.dds"
        dst = MOD / f"main_menu/gfx/interface/icons/map_modes/b{name}.dds"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)

    locale_files = port_localization()

    left = {name for text in {**written, **hand}.values() for name in unrenamed(text)}
    if left:
        print("NOT RENAMED - these still carry CM's own name:", file=sys.stderr)
        for name in sorted(left):
            print(f"  {name}", file=sys.stderr)
        return 1

    dangling = check_dangling(written, hand)
    if dangling:
        print("DANGLING - these are called and never defined:", file=sys.stderr)
        for name in dangling:
            print(f"  {name}", file=sys.stderr)
        return 1

    print(f"cm_maps: {len(written)} ported files, {len(hand)} hand-written, "
          f"{len(ICONS)} icons, {locale_files} localization files")
    return 0


def port_localization() -> int:
    """CM's own strings for the modes taken, in the two languages this mod ships.

    CM translates into eleven languages; the owner plays Russian and this
    repository ships English beside it. A key for a mode that is not published
    here is left in rather than hunted down: an unread key costs nothing, and
    pruning risks cutting one that a `$reference$` in a kept key still needs.
    """
    count = 0
    for language in LANGUAGES:
        have: set[str] = set()
        for stem, target in LOCALIZATION:
            src = SRC / f"main_menu/localization/{language}/{stem}_l_{language}.yml"
            if not src.is_file():
                continue
            text = prune(rename(read(src)).lstrip(BOM))
            have |= loc_keys(text)
            emit(MOD / f"main_menu/localization/{language}/{target}_l_{language}.yml", text)
            count += 1
        borrowed = borrow_keys(language, have)
        if borrowed:
            emit(MOD / f"main_menu/localization/{language}/bcm_borrowed_l_{language}.yml",
                 borrowed)
            count += 1
    return count


# The grant panel's own four labels. Nothing this mod ships quotes them, and
# BCM_TRMM_GRANT_LABEL prints a script value that belongs to CM's charter costs —
# a data function reading a value that is not there, sitting in a key nothing
# draws. The lowercase `bcm_trmm_grant_*` words stay: the map's own tooltip
# quotes several of them to say a charter is already granted.
PRUNE = ("BCM_TRMM_GRANT_LABEL", "BCM_TRMM_GRANT_LABEL_FREE",
         "BCM_TRMM_GRANT_CANT_AFFORD", "BCM_TRMM_GRANT_REQUIREMENTS")


def prune(text: str) -> str:
    kept = [line for line in text.split("\n")
            if not any(line.startswith(f" {key}:") for key in PRUNE)]
    return "\n".join(kept)


KEY = re.compile(r'^\s([A-Za-z_][A-Za-z_0-9.]*):\s*\d*\s*"', re.M)
VALUE = re.compile(r'^\s[A-Za-z_][A-Za-z_0-9.]*:\s*\d*\s*"((?:[^"\\]|\\.)*)"', re.M)


def loc_keys(text: str) -> set[str]:
    return set(KEY.findall(text))


def borrow_keys(language: str, have: set[str]) -> str:
    """The keys the ported strings quote that the ported files do not define.

    CM keeps a handful of shared phrases — «X is a sea zone», the estimate
    caveat — in `cm_localization_l_*.yml`, a file that is otherwise all of CM.
    Rather than carry it, the references are followed: whatever a kept string
    quotes with `$...$` is fetched from wherever in CM's localization it lives,
    and then whatever *those* quote, until nothing is left owing. A missing one
    would show as its own raw key in the middle of a tooltip.
    """
    pool: dict[str, str] = {}
    folder = SRC / f"main_menu/localization/{language}"
    for path in sorted(folder.glob("*.yml")) if folder.is_dir() else []:
        text = rename(read(path))
        for line in text.split("\n"):
            key = KEY.match(line)
            if key and key.group(1) not in pool:
                pool[key.group(1)] = line.rstrip("\r")

    def quoted(text: str) -> set[str]:
        return {ref for value in VALUE.findall(text)
                for ref in re.findall(r"\$(bcm_[A-Za-z0-9_.]*)\$", value)}

    owing = set()
    frontier = quoted("\n".join(
        line for key, line in pool.items() if key in have))
    while frontier:
        nxt: set[str] = set()
        for key in frontier - have - owing:
            if key not in pool:
                raise SystemExit(
                    f"{language}: «{key}» is quoted by a string this mod ships and "
                    "is nowhere in CM's localization. Read the string before "
                    "trusting this port."
                )
            owing.add(key)
            nxt |= quoted(pool[key])
        frontier = nxt

    if not owing:
        return ""
    lines = [
        "# Generated by mods/cm_maps/tools/port_from_cm.py - do not edit by hand.",
        "# Phrases the ported strings quote, which CM keeps in localization files",
        "# belonging to the rest of the mod. Fetched by reference, not by file.",
        "",
        f"l_{language}:",
    ]
    lines += [pool[key] for key in sorted(owing)]
    return "\n".join(lines)


# ---------------------------------------------------- the parts CM cannot supply

def hand_written() -> dict[str, str]:
    """What has no CM original: the load hooks, and the widget registration.

    CM runs all of this out of `cm_run_lobby_setup` and `cm_on_init_human_country`,
    which also seed auto-build, the market rotation and a dozen other things this
    mod has no use for. The three passes below are the ones its maps read.
    """
    return {
        "in_game/common/scripted_effects/bcm_setup_effects.txt": SETUP_EFFECTS,
        "in_game/common/scripted_guis/bcm_setup_scripted_guis.txt": SETUP_SCRIPTED_GUIS,
        "in_game/gui/scripted_widgets/bcm_scripted_widgets.txt": SCRIPTED_WIDGETS,
        "in_game/gui/bcm_pf_map_mode_window.gui": pf_window(),
    }


SETUP_SCRIPTED_GUIS = """# What the setup driver in bcm_pf_map_mode_window.gui fires, and the gate it
# fires behind.
#
# **There is no on_action here, and that is not an oversight.** CM runs its setup
# from on_game_start_after_lobby and on_game_load_after_lobby, and those two are
# not the engine's: the dump marks them `From Code: No`
# (reference/game/docs/on_actions.log), because the Community Mod Framework
# declares and fires them. The engine's own on_game_start fires before the
# country selection screen and has no load-time counterpart at all. Wiring to
# CMF's hooks would make this mod need CMF, so the work is driven from the
# window instead — the same way the river harvest below it already is.

# Root is the player. True while any of the three setup passes still owes work.
# The driver's _show fires once on the hidden->shown edge, so this staying true
# through the river harvest does not re-fire it.
bcm_setup_pending = {
	is_shown = {
		OR = {
			NOT = { bcm_trmm_data_is_current = yes }
			NOT = { bcm_fpot_data_is_current = yes }
			NOT = { bcm_pf_river_data_is_current = yes }
			# The migration below, which a save that predates it still owes. It is
			# a global stamp and not a check on what it retires, because what it
			# retires is written again in normal use: a governor run that finishes
			# sets bcm_pf_fresh_g, and gating on that flag would make this driver
			# throw away every cache the moment it was built.
			NOT = {
				AND = {
					has_global_variable = bcm_pf_epoch
					global_var:bcm_pf_epoch = 1
				}
			}
		}
	}
}

bcm_run_setup = {
	effect = {
		bcm_run_lobby_setup = yes
	}
}
"""

SETUP_EFFECTS = """# The once-per-save setup, cut down to what these three maps read. CM's own
# cm_run_lobby_setup does the same three calls in the same order, behind the same
# stamps, among a dozen others.
#
# **Every pass is behind its stamp, and that is not an optimisation.** Two of the
# three walk every location on the map; the stamp is what keeps a reload from
# paying for a pass whose result is already in the save.

bcm_run_lobby_setup = {
	# **Retiring what the 2026-09-19 fixes invalidated, once per save.** Both
	# fixes change stored data, and both stores outlive a reload on their own:
	# the urban-rights pass is held by a global stamp until its version changes,
	# and a finished governor run is held by bcm_pf_fresh_g for 1460 days. So a
	# campaign already under way would keep the wrong marks -- locations painted
	# tooling under an empty tooltip, and locations the old Search Accuracy of 3
	# skipped and left black -- and neither would ever be recomputed. Dropping
	# the trmm stamp costs one pass on the next load; dropping the governor
	# cache costs one recompute the next time the map is opened.
	#
	# The version constants live in a file this port generates from CM, so the
	# stamp is here instead, where a CM update cannot carry it away.
	if = {
		limit = {
			NOT = {
				AND = {
					has_global_variable = bcm_pf_epoch
					global_var:bcm_pf_epoch = 1
				}
			}
		}
		if = {
			limit = { has_global_variable = bcm_trmm_stamp }
			remove_global_variable = bcm_trmm_stamp
		}
		# Root is the player; the finder only ever runs for them.
		if = {
			limit = { exists = var:bcm_pf_fresh_g }
			remove_variable = bcm_pf_fresh_g
		}
		set_global_variable = { name = bcm_pf_epoch value = 1 }
	}

	# Recommended urban rights coverage: one pass over every province definition,
	# writing what the map and its tooltip then only read. Synchronous, so there
	# is no partial state for the stamp to certify.
	if = {
		limit = { NOT = { bcm_trmm_data_is_current = yes } }
		bcm_trmm_recompute_all = yes
		set_global_variable = { name = bcm_trmm_stamp value = bcm_trmm_version_value }
	}

	# Food potential per location, so the map reads a variable instead of
	# evaluating the whole formula per location per repaint.
	if = {
		limit = { NOT = { bcm_fpot_data_is_current = yes } }
		bcm_fpot_recompute_all = yes
		set_global_variable = { name = bcm_fpot_stamp value = bcm_fpot_version_value }
	}

	# River adjacency for the placement finder. This one is *not* synchronous: it
	# only queues the work, and the driver in bcm_pf_map_mode_window.gui records a
	# batch per tick, because the neighbour lists can only be read from GUI.
	bcm_pf_populate_river_locations = yes
}
"""

SCRIPTED_WIDGETS = """# What makes these two windows exist at all. A .gui file that is not named here
# is never instantiated, and nothing says so — see docs/pitfalls/windows.md.
gui/bcm_pf_map_mode_window.gui = bcm_pf_map_mode_window
gui/bcm_town_rights_search_panel.gui = bcm_town_rights_search_panel
"""


def pf_window() -> str:
    """CM's placement-finder driver, with the capital half cut and the river
    harvest folded in.

    Both drivers are CM's, verbatim but for the rename. They are here in one
    window rather than two because CM keeps the river harvest in
    `cm_hidden_window.gui`, which is its own large window full of parts of CM
    this mod does not carry.
    """
    text = rename(read(SRC / "in_game/gui/cm_pf_map_mode_window.gui")).lstrip(BOM)

    # Cut the three capital-finder widgets. Each is one `widget = {` block at one
    # indent, introduced by its own comment line; they are matched by that comment
    # so a CM edit inside one cannot make the cut miss.
    for comment in ("# Capital finder prep driver.",
                    "# Capital finder tick driver.",
                    "# Capital finder repaint driver."):
        text = _cut_widget(text, comment)

    # And the capital half of the mode-closed gate, which is the one place the two
    # finders share a line.
    closed_was = ("Not(Or(Or(GetMapMode('bcm_governor_finder').IsActive, "
                  "GetMapMode('bcm_governor_finder_hidden').IsActive), "
                  "Or(GetMapMode('bcm_capital_finder').IsActive, "
                  "GetMapMode('bcm_capital_finder_hidden').IsActive)))")
    closed_now = ("Not(Or(GetMapMode('bcm_governor_finder').IsActive, "
                  "GetMapMode('bcm_governor_finder_hidden').IsActive))")
    if text.count(closed_was) != 1:
        raise SystemExit(
            "cm_pf_map_mode_window.gui: the mode-closed gate is not the shape this "
            "port expects. CM changed it; read it before trusting the cut."
        )
    text = text.replace(closed_was, closed_now)

    closing = text.rstrip().rfind("\n}")
    if closing < 0:
        raise SystemExit("cm_pf_map_mode_window.gui: no closing brace found")
    return text[:closing] + "\n" + SETUP_DRIVER + _river_driver() + text[closing:]


# The setup driver. CM runs these passes from an on_action; those on_actions are
# CMF's, so this mod runs them from here instead. The shape is the one the river
# driver below uses and CM relies on all over: visible_at_creation = no pins the
# widget hidden at creation, so a load whose gate is already true still gets a
# hidden->shown edge, and _show fires exactly once on that edge.
SETUP_DRIVER = """	# Setup driver. Runs the urban-rights pass, the food-potential pass and the
	# river harvest's enumeration the first time any of the three is out of date,
	# which is a new game, a save made before this mod, or a version bump. Each
	# pass is stamped, so this costs nothing on a load that owes none of them.
	#
	# The gate stays true through the river harvest that follows, and that is
	# fine: _show fires on the hidden->shown edge, not every frame it is shown.
	widget = {
		size = { 0 0 }
		visible_at_creation = no
		visible = "[And(GetPlayer.Exists, GetScriptedGui('bcm_setup_pending').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End))]"
		state = {
			name = _show
			duration = 0.1
			on_finish = "[GetScriptedGui('bcm_run_setup').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
		}
	}

"""


def _cut_widget(text: str, comment: str) -> str:
    """Remove the `widget = { ... }` block the given comment line introduces."""
    at = text.find(comment)
    if at < 0:
        raise SystemExit(f"cm_pf_map_mode_window.gui: no widget introduced by «{comment}»")
    start = text.rfind("\n", 0, at) + 1
    lines = text[start:].split("\n")
    depth = 0
    taken = 0
    for i, line in enumerate(lines):
        depth += _delta(line)
        if depth > 0:
            continue
        if "{" in re.sub(r"#.*", "", "\n".join(lines[: i + 1])):
            taken = i + 1
            break
    end = start + len("\n".join(lines[:taken])) + 1
    # Swallow one blank line behind it so the file does not gap.
    while end < len(text) and text[end] == "\n":
        end += 1
    return text[:start] + text[end:]


def _river_driver() -> str:
    """The river-adjacency harvest, lifted out of CM's hidden window."""
    text = read(SRC / "in_game/gui/cm_hidden_window.gui")
    opening = text.find("\t\t# River-adjacency precompute for the placement finder.")
    if opening < 0:
        raise SystemExit("cm_hidden_window.gui: the river-adjacency driver has moved")
    start = text.rfind("\n\twidget = {", 0, opening) + 1
    lines = text[start:].split("\n")
    depth = 0
    taken = 0
    for i, line in enumerate(lines):
        depth += _delta(line)
        if depth <= 0 and i > 0:
            taken = i + 1
            break
    block = "\n".join(lines[:taken])
    return ("\t# River-adjacency harvest, lifted out of CM's own hidden window. The\n"
            "\t# placement finder reads the neighbour lists it writes, and\n"
            "\t# Location.GetRiverProximityLocations is readable only from GUI, which is\n"
            "\t# why this is a window and not a scripted effect.\n"
            + rename(block) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
