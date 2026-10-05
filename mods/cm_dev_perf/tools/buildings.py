"""Buildings Construction Manager Dev's Custom auto-build never names: the
2026-10-01 beta's own, and National Destinies'.

CM Dev's Custom tab works four fixed sets, each written out by hand for game
1.3: the capital buildings, the control buildings, the market-centre
buildings, and the player's roster (`auto_build_list`, 24 rows). A building
the author did not name is never built by it (his screenshot 2026-10-04).

The beta's new buildings join the author's sets where they strictly meet his
criterion, checked at build time (`NEW_CAPITAL`: `counts_as_capital`/
`is_capital = yes` in `location_potential`; `NEW_ROSTER`).

National Destinies' buildings are in none of CM's categories, his call 10-04
22:38: «все домики ND или какого-то другого мода — должны быть отдельным
списком… туда должны входить все домики мода, рыночные, производственные».
They get a list of their own, `auto_build_nd`, a category of its own: staged
and drained by copies of the roster's own effects over lists of its own, run
whenever a row is ticked, whatever the roster's checkbox says (the 22:38 run:
roster off, ND rows ticked, nothing built, since the rows rode the roster).
The Production tab skips them (`cm_perf_nd_all`). A row goes to a building of
the player's own country (the potential of the advance that unlocks it) the
first time it qualifies and keeps it: a row's settings stay with its building.
"""

from __future__ import annotations

import re
from pathlib import Path

NEW_CAPITAL = ("sacred_council", "khan_ordu", "chieftain_hall", "patrician_hall", "temple_militia")
NEW_ROSTER = ("village_granary",)
ROSTER_ROWS = 24  # CM Dev's own auto_build_list
ND_ROWS = 40
INFO_ROWS = 40  # auto_build_nd_info: every National Destinies building of the country
FREE = "flag:cm_perf_nd_free"


def _strip_comments(text: str) -> str:
    return re.sub(r"#[^\n]*", "", text)


def _close(text: str, open_at: int) -> int:
    depth = 0
    for j in range(open_at, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return j
    raise SystemExit("unbalanced braces")


def blocks(folder: Path) -> dict[str, str]:
    """Every top-level `key = { … }` in the folder's .txt files, comments dropped."""
    out: dict[str, str] = {}
    for path in sorted(folder.glob("*.txt")):
        text = _strip_comments(path.read_text(encoding="utf-8-sig"))
        pos = 0
        head = re.compile(r"(?m)^([A-Za-z_0-9]+)\s*=\s*\{")
        while (m := head.search(text, pos)):
            end = _close(text, m.end() - 1)
            out[m.group(1)] = text[m.end():end]
            pos = end + 1
    return out


def sub(body: str, key: str) -> str:
    """The inside of `key = { … }` in a block, on one line; empty when absent."""
    m = re.search(r"\b" + key + r"\s*=\s*\{", body)
    if not m:
        return ""
    return re.sub(r"\s+", " ", body[m.end():_close(body, m.end() - 1)]).strip()


def kind(body: str) -> str:
    if "always = no" in sub(body, "country_potential"):
        return "unbuildable"
    if re.search(r"\bis_foreign = yes", body) or re.search(r"\bestate = ", body):
        return "unbuildable"
    if re.search(r"\bproduced = ", body):
        return "production"
    place = sub(body, "location_potential")
    if "counts_as_capital = yes" in place or re.search(r"\bis_capital = yes", place):
        return "capital"
    if "is_market_center = yes" in place + " " + sub(body, "allow"):
        return "market"
    control = re.search(r"\blocal_max_control = ([0-9.]+)", sub(body, "modifier"))
    if control and float(control.group(1)) > 0 and re.search(r"\bis_special = yes", body):
        return "control"
    return "roster"


def vanilla_checks(game_types: Path) -> None:
    """The beta's new buildings still exist and still meet the criterion they were put under."""
    types = blocks(game_types)
    for key in NEW_CAPITAL:
        if key not in types or kind(types[key]) != "capital":
            raise SystemExit(f"{key}: no longer a capital building in the game's files")
    for key in NEW_ROSTER:
        if key not in types or kind(types[key]) != "roster":
            raise SystemExit(f"{key}: no longer a roster building in the game's files")


class ND:
    """National Destinies' buildings, sorted into CM's sets."""

    def __init__(self, root: Path | None):
        self.groups: dict[str, list[str]] = {}  # potential -> its buildings, file order
        if root is None:
            return
        types = blocks(root / "in_game/common/building_types")
        advances = blocks(root / "in_game/common/advances")
        for key, body in types.items():
            if kind(body) == "unbuildable":
                continue
            self.groups.setdefault(self._potential(body, advances), []).append(key)
        if not types:
            raise SystemExit(f"{root}: no building types read")

    @staticmethod
    def _potential(body: str, advances: dict[str, str]) -> str:
        """Whose building it is: the potential of the advance that unlocks it, else its own
        country_potential, else everyone's."""
        own = sub(body, "country_potential")
        unlocks = sorted(set(re.findall(r"\bhas_advance = (\w+)", own)))
        parts = []
        for adv in unlocks:
            if adv not in advances:
                raise SystemExit(f"advance {adv} not found in National Destinies")
            pot = sub(advances[adv], "potential")
            parts.append(pot or "always = yes")
        if not parts:
            return own or "always = yes"
        if len(parts) == 1:
            return parts[0]
        return "OR = { " + " ".join(f"AND = {{ {p} }}" for p in parts) + " }"

    @staticmethod
    def _most(groups: dict[str, list]) -> int:
        """The most rows one tag can claim: its own and its formed variants, plus every group no
        tag owns (a game rule, a formed-country variable, everyone's), as if it held all of them."""
        per_tag: dict[str, int] = {}
        anyone = 0
        for pot, keys in groups.items():
            tags = set(re.findall(r"has_or_had_tag = (\w+)", pot))
            if not tags:
                anyone += len(keys)
            for tag in tags:
                per_tag[tag] = per_tag.get(tag, 0) + len(keys)
        return max(per_tag.values(), default=0) + anyone

    def most_rows(self) -> int:
        return self._most(self.groups)

    def keys(self) -> list[str]:
        return [k for v in self.groups.values() for k in v]

    def count(self) -> int:
        return sum(len(v) for v in self.groups.values())


# --- edits to CM Dev's own files ------------------------------------------

def _once(text: str, anchor: str, where: str) -> None:
    if text.count(anchor) != 1:
        raise SystemExit(f"{where}: anchor occurs {text.count(anchor)} times: {anchor[:70]!r}")


def edit_custom_sets(text: str) -> str:
    """cm_ab_custom_effects.txt: the beta's capital buildings beside CM's, staged and drained; the
    National Destinies list as a set of its own beside the roster."""
    cap = "\t\t\t\tcm_ab_stage_capital_type_here = { bt = city_guard }\n"
    _once(text, cap, "capital set")
    text = text.replace(cap, cap + "\t\t\t\t# cm_dev_perf: the beta's new capital buildings.\n" + "".join(
        f"\t\t\t\tcm_ab_stage_capital_type_here = {{ bt = {k} }}\n" for k in NEW_CAPITAL))
    # +perf20 staged them and never drained them: the drain names its types too.
    drain = "\t\tcm_ab_drain_capital_type = { bt = city_guard }\n"
    _once(text, drain, "capital drain")
    text = text.replace(drain, drain + "\t\t# cm_dev_perf: the beta's new capital buildings.\n" + "".join(
        f"\t\tcm_ab_drain_capital_type = {{ bt = {k} }}\n" for k in NEW_CAPITAL))
    gate = "\t\t\t\texists = var:cm_ab_custom_market_centers\n\t\t\t\texists = var:cm_ab_custom_roster\n"
    _once(text, gate, "candidates gate")
    text = text.replace(gate, gate + "\t\t\t\tcm_perf_nd_wanted = yes\n")
    stage = "\t\tlimit = { exists = var:cm_ab_custom_roster }\n\t\tcm_ab_stage_custom_roster = yes\n\t}\n"
    _once(text, stage, "roster stage")
    text = text.replace(stage, stage + "\t# cm_dev_perf: the National Destinies list, a set of its own.\n"
                        "\tif = {\n\t\tlimit = { cm_perf_nd_wanted = yes }\n\t\tcm_perf_nd_stage_list = yes\n\t}\n")
    drained = "\t\tlimit = { exists = var:cm_ab_custom_roster }\n\t\tcm_ab_drain_custom_roster = yes\n\t}\n"
    _once(text, drained, "roster drain")
    return text.replace(drained, drained + "\t# cm_dev_perf: the National Destinies list, after the roster.\n"
                        "\tif = {\n\t\tlimit = { cm_perf_nd_wanted = yes }\n\t\tcm_perf_nd_drain_list = yes\n\t}\n")


def edit_subjects_wanted(text: str) -> str:
    """cm_ab_triggers.txt: subject candidates are gathered for the National Destinies list too."""
    old = ("cm_ab_custom_subjects_wanted = {\n\texists = var:cm_ab_custom_roster\n"
           "\thas_variable_list = cm_ab_building_types_in_subjects_enabled\n"
           "\tvariable_list_size = { name = cm_ab_building_types_in_subjects_enabled value >= 1 }\n}\n")
    _once(text, old, "cm_ab_custom_subjects_wanted")
    return text.replace(old, """cm_ab_custom_subjects_wanted = {
\tOR = {
\t\tAND = {
\t\t\texists = var:cm_ab_custom_roster
\t\t\thas_variable_list = cm_ab_building_types_in_subjects_enabled
\t\t\tvariable_list_size = { name = cm_ab_building_types_in_subjects_enabled value >= 1 }
\t\t}
\t\t# cm_dev_perf: the National Destinies list.
\t\tAND = {
\t\t\tcm_perf_nd_wanted = yes
\t\t\thas_variable_list = cm_perf_nd_types_in_subjects_enabled
\t\t\tvariable_list_size = { name = cm_perf_nd_types_in_subjects_enabled value >= 1 }
\t\t}
\t}
}
""")


def edit_production_skip(text: str) -> str:
    """cm_ab_production_effects.txt: the Production tab leaves National Destinies' to their list."""
    old = "\t\t\tcm_is_building_type_production_building = yes\n\t\t\tis_foreign = no\n"
    _once(text, old, "production type walk")
    return text.replace(old, old + "\t\t\t# cm_dev_perf: National Destinies' buildings are their list's alone.\n"
                        "\t\t\tNOT = { is_target_in_global_variable_list = { name = cm_perf_nd_all target = this } }\n")


def edit_populate(text: str) -> str:
    """cm_game_load_setup_effects.txt: the National Destinies set is listed with the building types."""
    old = "cm_populate_building_types_to_process = {\n  clear_global_variable_list = cm_building_types_to_process\n"
    _once(text, old, "cm_populate_building_types_to_process")
    return text.replace(old, old + "  cm_perf_nd_populate_all = yes\n")


def roster_copies(custom: str) -> str:
    """CM's own roster stage and drain, over the National Destinies list's lists."""
    out = []
    for src, dst in (("cm_ab_stage_custom_roster", "cm_perf_nd_stage_list"),
                     ("cm_ab_drain_custom_roster", "cm_perf_nd_drain_list")):
        m = re.search(rf"(?m)^{src} = \{{", custom)
        if not m:
            raise SystemExit(f"cm_ab_custom_effects.txt: {src} not found")
        body = custom[m.start():_close(custom, m.end() - 1) + 1]
        for a, b in (("cm_ab_building_types_in_subjects_enabled", "cm_perf_nd_types_in_subjects_enabled"),
                     ("cm_ab_building_types_enabled", "cm_perf_nd_types_enabled"),
                     ("cm_ab_building_types_list", "cm_perf_nd_types_list")):
            body = body.replace(a, b)
        out += [f"# Copied from CM's {src} by buildings.py, over the National Destinies list's lists.",
                body.replace(src, dst, 1), ""]
    return "\n".join(out)


def edit_registration(text: str) -> str:
    """cm_cmm_effects.txt: the roster's new rows, then the National Destinies list."""
    count = "\t\tsetting_id = auto_build_list\n\t\ttab_id = ab_custom\n\t\titem_count = 24\n"
    _once(text, count, "auto_build_list registration")
    text = text.replace(count, count.replace("24", str(ROSTER_ROWS + len(NEW_ROSTER))))
    last = "item = 24 value = building_type:granary }\n"
    _once(text, last, "auto_build_list last row")
    rows = "".join(
        f"\tcmm_set_list_item_value = {{ mod_id = cm setting_id = auto_build_list item = {ROSTER_ROWS + i} "
        f"value = building_type:{k} }}\n" for i, k in enumerate(NEW_ROSTER, 1))
    text = text.replace(last, last + rows)
    rgos = "\tcmm_disable_list_field_for_item = { mod_id = cm setting_id = auto_build_list field_id = min_rgos item = 24 }\n"
    _once(text, rgos, "auto_build_list min_rgos")
    off = "".join(
        f"\tcmm_disable_list_field_for_item = {{ mod_id = cm setting_id = auto_build_list field_id = min_rgos "
        f"item = {ROSTER_ROWS + i} }}\n" for i in range(1, len(NEW_ROSTER) + 1))
    return text.replace(rgos, rgos + off + "\n\t# cm_dev_perf: National Destinies' buildings, a list of their own.\n"
                        "\tcm_perf_nd_register = yes\n")


def edit_seed(text: str) -> str:
    """cm_game_load_setup_effects.txt: the seeded roster carries the new rows too."""
    last = "\tadd_to_variable_list = { name = cm_ab_building_types_list target = building_type:granary }\n"
    _once(text, last, "seeded roster")
    return text.replace(last, last + "".join(
        f"\tadd_to_variable_list = {{ name = cm_ab_building_types_list target = building_type:{k} }}\n"
        for k in NEW_ROSTER))


def edit_lookups(text: str) -> str:
    """cm_cmm_custom_effects.txt: the National Destinies rows join the roster's lookups, and get
    their buildings and visibility with the roster's."""
    end = ("\tcmm_build_list_field_map = { setting = cm__auto_build_list field_slot = 5 "
           "map_name = cm_min_rgos_by_building_type multiply = 1 }\n\n\t} # end guard\n")
    _once(text, end, "roster lookups")
    text = text.replace(end, end.replace("\n\n\t} # end guard",
                                         "\n\n\t# cm_dev_perf: National Destinies' rows, after the roster's.\n"
                                         "\tcm_perf_nd_merge = yes\n\n\t} # end guard"))
    vis = ("\t\tcmm_for_each_list_item = {\n\t\t\tsetting = cm__auto_build_list\n"
           "\t\t\teffect = cm_ab_list_update_visibility_item\n\t\t}\n\t}\n")
    _once(text, vis, "roster visibility")
    return text.replace(vis, vis + "\t# cm_dev_perf: National Destinies' rows.\n\tcm_perf_nd_refresh_rows = yes\n")


def edit_row_names(text: str) -> str:
    """cm_cmm_l_<lang>.yml: the new roster rows' labels, as CM writes its own."""
    m = re.search(r"(?m)^ cm__auto_build_list_i24_name: .*\n", text)
    if not m:
        raise SystemExit("cm__auto_build_list_i24_name: not found")
    rows = "".join(
        f" cm__auto_build_list_i{ROSTER_ROWS + i}_name: \"@{k}! [ShowBuildingTypeName('{k}')]\" # NO-TRANSLATE\n"
        for i, k in enumerate(NEW_ROSTER, 1))
    return text[:m.end()] + rows + text[m.end():]


# --- generated files ----------------------------------------------------------

def _rows(n: int, line: str) -> str:
    return "".join(line.format(i=i) for i in range(1, n + 1))


def effects(nd: ND, custom: str) -> str:
    lines = [
        "# Generated by mods/cm_dev_perf/tools/buildings.py; not to be edited by hand.",
        "# National Destinies' buildings in Construction Manager's Custom auto-build: a list and a",
        "# set of their own (auto_build_nd), whose rows go to the player's own country's buildings.",
        f"# {nd.count()} buildings.",
        "",
        "# Every National Destinies building, which the Production tab leaves to the list. Global,",
        "# called with cm_populate_building_types_to_process.",
        "cm_perf_nd_populate_all = {",
        "\tclear_global_variable_list = cm_perf_nd_all",
        *[f"\tadd_to_global_variable_list = {{ name = cm_perf_nd_all target = building_type:{k} }}" for k in nd.keys()],
        "}",
        "",
        roster_copies(custom),
        "# The list. Rows stand for nothing until cm_perf_nd_assign_rows gives them a building; the",
        "# placeholder keeps CMF's per-row walk from carrying the previous row's building into one that",
        "# has none. Registration runs on every load, so a row's building is set only once. Root is the",
        "# country.",
        "cm_perf_nd_register = {",
        "\tcmm_register_settings_list = {",
        "\t\tmod_id = cm",
        "\t\tsetting_id = auto_build_nd",
        "\t\ttab_id = ab_custom",
        f"\t\titem_count = {ND_ROWS}",
        "\t\tis_ordered = 1",
        "\t}",
        _rows(ND_ROWS, "\tif = {{ limit = {{ NOT = {{ has_variable_list = cm__auto_build_nd_i{i}_value }} }} "
                       "cmm_set_list_item_value = {{ mod_id = cm setting_id = auto_build_nd item = {i} value = "
                       + FREE + " }} }}\n").rstrip("\n"),
        "\t# Off until he ticks them: these are the dear buildings of a national tree.",
        "\tcmm_register_list_bool_field = { mod_id = cm setting_id = auto_build_nd field_id = enabled default_value = 0 }",
        "\tcmm_register_list_bool_field = { mod_id = cm setting_id = auto_build_nd field_id = in_subjects default_value = 0 }",
        "\tcmm_register_list_numeric_field = {",
        "\t\tmod_id = cm",
        "\t\tsetting_id = auto_build_nd",
        "\t\tfield_id = min_control",
        "\t\tdefault_value = 50",
        "\t\tmin_value = 0",
        "\t\tmax_value = 100",
        "\t\tstep_value = 5",
        "\t}",
        "\tcmm_set_list_field_format = { mod_id = cm setting_id = auto_build_nd field_id = min_control }",
        "\tcmm_register_list_numeric_field = {",
        "\t\tmod_id = cm",
        "\t\tsetting_id = auto_build_nd",
        "\t\tfield_id = min_discount",
        "\t\tdefault_value = 0",
        "\t\tmin_value = -33",
        "\t\tmax_value = 33",
        "\t\tstep_value = 1",
        "\t}",
        "\tcmm_set_list_field_conditional_format = { mod_id = cm setting_id = auto_build_nd field_id = min_discount }",
        "\tcm_perf_ndi_register = yes",
        "}",
        "",
        "# Gives each of this country's buildings a row the first time the country qualifies for it (the",
        "# potential of the advance that unlocks it), in National Destinies' own order, and never takes",
        "# it back: a tag change only adds rows. Root is the country.",
        "cm_perf_nd_assign_rows = {",
        "\tif = { limit = { NOT = { has_variable = cm_perf_nd_rows_used } } set_variable = { name = cm_perf_nd_rows_used value = 0 } }",
    ]
    for pot, keys in nd.groups.items():
        lines.append(f"\tif = {{ limit = {{ {pot} }}")
        lines += [f"\t\tcm_perf_nd_assign = {{ bt = {k} }}" for k in keys]
        lines.append("\t}")
    lines += [
        "}",
        "",
        "# Root is the country. $bt$ = the building type. Kept small: it is pasted once per building.",
        "cm_perf_nd_assign = {",
        "\tbuilding_type:$bt$ = { save_scope_as = cm_perf_nd_t }",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\tNOT = { is_target_in_variable_list = { name = cm_perf_nd_rows target = scope:cm_perf_nd_t } }",
        f"\t\t\tvar:cm_perf_nd_rows_used < {ND_ROWS}",
        "\t\t}",
        "\t\tcm_perf_nd_place_row = yes",
        "\t}",
        "}",
        "",
        "# The next free row gets scope:cm_perf_nd_t. Root is the country.",
        "cm_perf_nd_place_row = {",
        "\tchange_variable = { name = cm_perf_nd_rows_used add = 1 }",
        "\tadd_to_variable_list = { name = cm_perf_nd_rows target = scope:cm_perf_nd_t }",
        "\tset_local_variable = { name = cm_perf_nd_new value = 1 }",
        "\tswitch = {",
        "\t\ttrigger = var:cm_perf_nd_rows_used",
        _rows(ND_ROWS, "\t\t{i} = {{ cmm_set_list_item_value = {{ mod_id = cm setting_id = auto_build_nd item = {i} "
                       "value = scope:cm_perf_nd_t }} }}\n").rstrip("\n"),
        "\t}",
        "}",
        "",
        "# New rows first, then each row shown while its building can be built (or a later tier of it",
        "# can), as CM shows its own roster. Root is the country.",
        "cm_perf_nd_refresh_rows = {",
        "\tcm_perf_nd_assign_rows = yes",
        "\tif = {",
        "\t\tlimit = { has_variable_list = cmm_list_items_cm__auto_build_nd }",
        "\t\tcmm_for_each_list_item = { setting = cm__auto_build_nd effect = cm_perf_nd_row_visibility }",
        "\t}",
        "\tif = {",
        "\t\tlimit = { has_local_variable = cm_perf_nd_new }",
        "\t\tcm_rebuild_auto_build_lookups = yes",
        "\t}",
        "\tcm_perf_ndi_refresh_rows = yes",
        "}",
        "",
        "# Callback for cmm_for_each_list_item. A row's label reads its building from",
        "# var:cm_perf_nd_bt_<row> (localization cm__auto_build_nd_i<row>_name): set here rather",
        "# than once, so a save whose rows predate it gets its names too. Root is the country.",
        "cm_perf_nd_row_visibility = {",
        "\tif = {",
        "\t\tlimit = { is_target_in_variable_list = { name = cm_perf_nd_rows target = scope:cmm_list_current_item_value } }",
        "\t\tset_variable = { name = cm_perf_nd_bt_$i$ value = scope:cmm_list_current_item_value }",
        "\t\t# +perf20 tried to relabel the row by copying a flag between variables; put the row's",
        "\t\t# label back on its own key, as CMF's _cmm_initialize_list_item_metadata sets it.",
        "\t\tset_variable = { name = $setting$_i$i$_name value = flag:$setting$_i$i$_name }",
        "\t\tif = {",
        "\t\t\tlimit = {",
        "\t\t\t\tOR = {",
        "\t\t\t\t\tcan_build_building = scope:cmm_list_current_item_value",
        "\t\t\t\t\tbuilding_type_is_obsolete = scope:cmm_list_current_item_value",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t\tcmm_show_list_item = { mod_id = cm setting_id = auto_build_nd item = $i$ }",
        "\t\t}",
        "\t\telse = {",
        "\t\t\tcmm_hide_list_item = { mod_id = cm setting_id = auto_build_nd item = $i$ }",
        "\t\t}",
        "\t}",
        "\telse = {",
        "\t\tcmm_hide_list_item = { mod_id = cm setting_id = auto_build_nd item = $i$ }",
        "\t}",
        "\tif = {",
        "\t\tlimit = { always = no }",
        "\t\tcmf_suppress = { v = $setting$_$i$ }",
        "\t}",
        # Only the localization reads the row's type, and the engine counts no use there:
        # without a read in script error.log says it is set but never used, once a row.
        # cmf_suppress would also name it as a flag and a global, which nothing sets.
        "\tif = {",
        "\t\tlimit = { always = no exists = var:cm_perf_nd_bt_$i$ }",
        "\t}",
        "}",
        "",
        "# The list's own lists, rebuilt with the roster's lookups (cm_rebuild_auto_build_lookups), and",
        "# its rows' thresholds into the roster's maps, which are keyed by building type. Root is the",
        "# country.",
        "cm_perf_nd_merge = {",
        "\tclear_variable_list = cm_perf_nd_types_list",
        "\tclear_variable_list = cm_perf_nd_types_enabled",
        "\tclear_variable_list = cm_perf_nd_types_in_subjects_enabled",
        "\tif = {",
        "\t\tlimit = { has_variable_list = cmm_list_items_cm__auto_build_nd }",
        "\t\tcmm_for_each_list_item = { setting = cm__auto_build_nd effect = cm_perf_nd_merge_row }",
        "\t}",
        "}",
        "",
        "# Callback for cmm_for_each_list_item. Fields in registration order: 1 enabled, 2 in_subjects,",
        "# 3 min_control, 4 min_discount. Root is the country.",
        "cm_perf_nd_merge_row = {",
        "\tif = {",
        "\t\tlimit = { is_target_in_variable_list = { name = cm_perf_nd_rows target = scope:cmm_list_current_item_value } }",
        "\t\tadd_to_variable_list = { name = cm_perf_nd_types_list target = scope:cmm_list_current_item_value }",
        "\t\t# Read as CMF's own _cmm_build_list_*_item read them: every field has its default from",
        "\t\t# registration on, so the cmm map holds each key.",
        "\t\tset_local_variable = { name = cm_perf_nd_fk value = flag:$setting$_i$i$_f1 }",
        "\t\tif = {",
        "\t\t\tlimit = { \"variable_map(cmm|local_var:cm_perf_nd_fk)\" >= 1 }",
        "\t\t\tadd_to_variable_list = { name = cm_perf_nd_types_enabled target = scope:cmm_list_current_item_value }",
        "\t\t}",
        "\t\tset_local_variable = { name = cm_perf_nd_fk value = flag:$setting$_i$i$_f2 }",
        "\t\tif = {",
        "\t\t\tlimit = { \"variable_map(cmm|local_var:cm_perf_nd_fk)\" >= 1 }",
        "\t\t\tadd_to_variable_list = { name = cm_perf_nd_types_in_subjects_enabled target = scope:cmm_list_current_item_value }",
        "\t\t}",
        "\t\tset_local_variable = { name = cm_perf_nd_fk value = flag:$setting$_i$i$_f3 }",
        "\t\tset_local_variable = { name = cm_perf_nd_fv value = \"variable_map(cmm|local_var:cm_perf_nd_fk)\" }",
        "\t\tchange_local_variable = { name = cm_perf_nd_fv multiply = 0.01 }",
        "\t\tadd_to_variable_map = { name = cm_min_control_by_building_type key = scope:cmm_list_current_item_value value = local_var:cm_perf_nd_fv }",
        "\t\tset_local_variable = { name = cm_perf_nd_fk value = flag:$setting$_i$i$_f4 }",
        "\t\tset_local_variable = { name = cm_perf_nd_fv value = \"variable_map(cmm|local_var:cm_perf_nd_fk)\" }",
        "\t\tchange_local_variable = { name = cm_perf_nd_fv multiply = 0.01 }",
        "\t\tadd_to_variable_map = { name = cm_min_discount_by_building_type key = scope:cmm_list_current_item_value value = local_var:cm_perf_nd_fv }",
        "\t}",
        "\tif = {",
        "\t\tlimit = { always = no }",
        "\t\tcmf_suppress = { v = $setting$_$i$ }",
        "\t}",
        "}",
        "",
    ]
    lines += info_effects(nd)
    return "\ufeff" + "\n".join(lines)


def info_effects(nd: ND) -> list[str]:
    """auto_build_nd_info: every National Destinies building of the player's country, whatever it
    is, open or not — his ask 10-04, «открыть список этих зданий, без настроек… просто ради
    информации». No fields."""
    lines = [
        "",
        "# --- auto_build_nd_info: the country's National Destinies buildings, for reading only ---",
        "",
        "# Root is the country.",
        "cm_perf_ndi_register = {",
        "\tcmm_register_settings_list = {",
        "\t\tmod_id = cm",
        "\t\tsetting_id = auto_build_nd_info",
        "\t\ttab_id = ab_custom",
        f"\t\titem_count = {INFO_ROWS}",
        "\t\tis_ordered = 0",
        "\t}",
        _rows(INFO_ROWS, "\tif = {{ limit = {{ NOT = {{ has_variable_list = cm__auto_build_nd_info_i{i}_value }} }} "
                         "cmm_set_list_item_value = {{ mod_id = cm setting_id = auto_build_nd_info item = {i} value = "
                         + FREE + " }} }}\n").rstrip("\n"),
        "}",
        "",
        "# Root is the country. Same owners as the list's (the unlocking advance's potential).",
        "cm_perf_ndi_assign_rows = {",
        "\tif = { limit = { NOT = { has_variable = cm_perf_ndi_rows_used } } set_variable = { name = cm_perf_ndi_rows_used value = 0 } }",
    ]
    for pot, keys in nd.groups.items():
        lines.append(f"\tif = {{ limit = {{ {pot} }}")
        lines += [f"\t\tcm_perf_ndi_assign = {{ bt = {k} }}" for k in keys]
        lines.append("\t}")
    lines += [
        "}",
        "",
        "# Root is the country. $bt$ = the building type.",
        "cm_perf_ndi_assign = {",
        "\tbuilding_type:$bt$ = { save_scope_as = cm_perf_ndi_t }",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\tNOT = { is_target_in_variable_list = { name = cm_perf_ndi_rows target = scope:cm_perf_ndi_t } }",
        f"\t\t\tvar:cm_perf_ndi_rows_used < {INFO_ROWS}",
        "\t\t}",
        "\t\tcm_perf_ndi_place_row = yes",
        "\t}",
        "}",
        "",
        "# The next free row gets scope:cm_perf_ndi_t. Root is the country.",
        "cm_perf_ndi_place_row = {",
        "\tchange_variable = { name = cm_perf_ndi_rows_used add = 1 }",
        "\tadd_to_variable_list = { name = cm_perf_ndi_rows target = scope:cm_perf_ndi_t }",
        "\tswitch = {",
        "\t\ttrigger = var:cm_perf_ndi_rows_used",
        _rows(INFO_ROWS, "\t\t{i} = {{ cmm_set_list_item_value = {{ mod_id = cm setting_id = auto_build_nd_info item = {i} "
                         "value = scope:cm_perf_ndi_t }} }}\n").rstrip("\n"),
        "\t}",
        "}",
        "",
        "# Rows with a building are shown, open or not; the rest hidden. Root is the country.",
        "cm_perf_ndi_refresh_rows = {",
        "\tcm_perf_ndi_assign_rows = yes",
        "\tif = {",
        "\t\tlimit = { has_variable_list = cmm_list_items_cm__auto_build_nd_info }",
        "\t\tcmm_for_each_list_item = { setting = cm__auto_build_nd_info effect = cm_perf_ndi_row_visibility }",
        "\t}",
        "}",
        "",
        "# Callback for cmm_for_each_list_item; labels as cm_perf_nd_row_visibility. Root is the country.",
        "cm_perf_ndi_row_visibility = {",
        "\tif = {",
        "\t\tlimit = { is_target_in_variable_list = { name = cm_perf_ndi_rows target = scope:cmm_list_current_item_value } }",
        "\t\tset_variable = { name = cm_perf_ndi_bt_$i$ value = scope:cmm_list_current_item_value }",
        "\t\tif = {",
        "\t\t\tlimit = {",
        "\t\t\t\tOR = {",
        "\t\t\t\t\tcan_build_building = scope:cmm_list_current_item_value",
        "\t\t\t\t\tbuilding_type_is_obsolete = scope:cmm_list_current_item_value",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t\tset_variable = { name = cm_perf_ndi_open_$i$ value = 1 }",
        "\t\t}",
        "\t\telse = {",
        "\t\t\tset_variable = { name = cm_perf_ndi_open_$i$ value = 0 }",
        "\t\t}",
        "\t\tcmm_show_list_item = { mod_id = cm setting_id = auto_build_nd_info item = $i$ }",
        "\t}",
        "\telse = {",
        "\t\tcmm_hide_list_item = { mod_id = cm setting_id = auto_build_nd_info item = $i$ }",
        "\t}",
        "\tif = {",
        "\t\tlimit = { always = no }",
        "\t\tcmf_suppress = { v = $setting$_$i$ }",
        "\t}",
        # As in cm_perf_nd_row_visibility; and CMF sets five field flags on every row, which
        # a list with no fields never reads.
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\talways = no",
        "\t\t\texists = var:cm_perf_ndi_bt_$i$",
        *(f"\t\t\texists = flag:$setting$_i$i$_f{n}" for n in range(1, 6)),
        "\t\t}",
        "\t}",
        "}",
        "",
    ]
    return lines


KIND_KEYS = ("open", "closed")


def custom_localization() -> str:
    """Whether an info row's building can be built yet, by var:cm_perf_ndi_open_<row>."""
    lines = ["# Generated by mods/cm_dev_perf/tools/buildings.py; not to be edited by hand.", ""]
    for i in range(1, INFO_ROWS + 1):
        lines += [f"cm_perf_ndi_kind_{i} = {{", "\ttype = country"]
        for n, key in ((1, "open"), (0, "closed")):
            lines += ["\ttext = {", f"\t\tlocalization_key = cm_perf_ndi_kind_{key}",
                      f"\t\ttrigger = {{ has_variable = cm_perf_ndi_open_{i} var:cm_perf_ndi_open_{i} = {n} }}"
                      # set as cm_perf_ndi_open_$i$ by cm_perf_ndi_row_visibility, which no checker expands
                      " # check-script: never set", "\t}"]
        lines += ["\ttext = {", "\t\tlocalization_key = cm_perf_ndi_kind_none", "\t\tfallback = yes", "\t}", "}", ""]
    return "\ufeff" + "\n".join(lines)


def scripted_triggers() -> str:
    return "\ufeff" + "\n".join([
        "# Generated by mods/cm_dev_perf/tools/buildings.py; not to be edited by hand.",
        "# The National Destinies list runs as a set of its own while any row is ticked. Root is the country.",
        "cm_perf_nd_wanted = {",
        "\thas_variable_list = cm_perf_nd_types_enabled",
        "\tvariable_list_size = { name = cm_perf_nd_types_enabled value >= 1 }",
        "}",
        "",
    ])


def scripted_guis() -> str:
    return "\ufeff" + "\n".join([
        "# Generated by mods/cm_dev_perf/tools/buildings.py; not to be edited by hand.",
        "# A CMF list is invisible without its _on_changed (docs/research/cmf.md), and this one also",
        "# commits the change: lists have no auto-apply.",
        "cm__auto_build_nd_on_changed = {",
        "\tscope = country",
        "",
        "\tis_shown = {",
        "\t\talways = yes",
        "\t}",
        "",
        "\tis_valid = {",
        "\t\texists = var:cm_ab_custom_roster",
        "\t}",
        "",
        "\teffect = {",
        "\t\tcmm_apply_list_change = {",
        "\t\t\tsetting = cm__auto_build_nd",
        "\t\t}",
        "\t\tcm_rebuild_auto_build_lookups = yes",
        "\t}",
        "}",
        "",
        "cm__auto_build_nd_info_on_changed = {",
        "\tscope = country",
        "",
        "\tis_shown = {",
        "\t\talways = yes",
        "\t}",
        "",
        "\teffect = {",
        "\t\tcmm_apply_list_change = {",
        "\t\t\tsetting = cm__auto_build_nd_info",
        "\t\t}",
        "\t}",
        "}",
        "",
    ])


WORDS = {
    "russian": {
        "title": "Здания National Destinies",
        "desc": "Все национальные здания вашей страны из National Destinies, отдельной категорией: другие "
                "категории их не строят. Строка появляется, когда здание можно строить. По умолчанию выключены; "
                "отмеченные строятся по правилам списка «Выбрать здания», даже если сам он выключен.",
        "column": "Здание",
        "info_title": "Здания National Destinies: все здания державы",
        "info_desc": "Только для справки: все национальные здания вашей страны из National Destinies, открытые "
                     "и нет. Ничего не настраивает.",
        "kind_open": " — открыто",
        "kind_closed": " — ещё не открыто",
    },
    "english": {
        "title": "National Destinies Buildings",
        "desc": "All of your country's National Destinies buildings, a category of their own: no other "
                "category builds them. A row shows once the building can be built. Off by default; a ticked one "
                "is built by the rules of the list above, even with that list switched off.",
        "column": "Building",
        "info_title": "National Destinies Buildings: all of the country's",
        "info_desc": "For reading only: every National Destinies building of your country, open or not. "
                     "Sets nothing.",
        "kind_open": " — open",
        "kind_closed": " — not open yet",
    },
}


def localization(lang: str) -> str:
    w = WORDS.get(lang, WORDS["english"])
    src = "cm__auto_build_list"
    dst = "cm__auto_build_nd"
    lines = [
        f"\ufeffl_{lang}:",
        "# Generated by mods/cm_dev_perf/tools/buildings.py; not to be edited by hand.",
        f' cm__ab_custom__auto_build_nd_name: "{w["title"]}"',
        f' cm__ab_custom__auto_build_nd_desc: "{w["desc"]}"',
        f' cm__ab_custom__auto_build_nd: "cm__ab_custom__auto_build_nd"',
        f' {dst}_name: "{w["title"]}"',
        f' {dst}_desc: "{w["desc"]}"',
        f' {dst}: "{dst}"',
        f' {dst}_item_column_name: "{w["column"]}"',
    ]
    for field in ("enabled", "in_subjects", "min_control", "min_discount"):
        lines += [f' {dst}__{field}_name: "${src}__{field}_name$"',
                  f' {dst}__{field}_desc: "${src}__{field}_desc$"',
                  f' {dst}__{field}: "{dst}__{field}"']
    lines += [
        f' {dst}__min_control_prefix: ""',
        f' {dst}__min_discount_prefix: ""',
        f' {dst}__min_control_postfix: "%"',
        f' {dst}__min_discount_postfix: "%"',
        f' {dst}__min_discount_prefix_high: "#R "',
        f' {dst}__min_discount_postfix_high: "%#!"',
        f' {dst}__min_discount_prefix_low: "#G "',
        f' {dst}__min_discount_postfix_low: "%#!"',
    ]
    # A row's label is its building's own name, read from the variable the row's visibility pass
    # sets (CMF prints the localization of the row's _name flag; the 10-04 run showed «-» for every
    # row when the label was a flag copied out of another variable).
    # GetName, not GetNameWithNoTooltip: the name hovers as the building's own tooltip, as CM's
    # rows do with ShowBuildingTypeName (his ask 10-04 22:31).
    name = "[GetPlayer.MakeScope.GetVariable('{var}').GetBuildingType.GetName]"
    lines += [f' {dst}_i{i}_name: "{name.format(var=f"cm_perf_nd_bt_{i}")}" # NO-TRANSLATE'
              for i in range(1, ND_ROWS + 1)]
    info = f"{dst}_info"
    lines += [
        f' cm__ab_custom__auto_build_nd_info_name: "{w["info_title"]}"',
        f' cm__ab_custom__auto_build_nd_info_desc: "{w["info_desc"]}"',
        f' cm__ab_custom__auto_build_nd_info: "cm__ab_custom__auto_build_nd_info"',
        f' {info}_name: "{w["info_title"]}"',
        f' {info}_desc: "{w["info_desc"]}"',
        f' {info}: "{info}"',
        f' {info}_item_column_name: "{w["column"]}"',
    ]
    lines += [f' {info}_i{i}_name: "{name.format(var=f"cm_perf_ndi_bt_{i}")}'
              f'[GetPlayer.Custom(\'cm_perf_ndi_kind_{i}\')]" # NO-TRANSLATE' for i in range(1, INFO_ROWS + 1)]
    lines += [f' cm_perf_ndi_kind_{k}: "{w["kind_" + k]}"' for k in KIND_KEYS]
    lines.append(' cm_perf_ndi_kind_none: ""')
    return "\n".join(lines) + "\n"
