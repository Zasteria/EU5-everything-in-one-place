"""Buildings Construction Manager Dev's Custom auto-build never names: the
2026-10-01 beta's own, and National Destinies'.

CM Dev's Custom tab works four fixed sets, each written out by hand for game
1.3: the capital buildings, the control buildings, the market-centre
buildings, and the player's roster (`auto_build_list`, 24 rows). A building
the author did not name is never built by it, so the beta's new capital
buildings and every National Destinies building were out (his screenshot
2026-10-04, the Custom tab).

Each building goes where it **strictly** meets the author's own criterion for
a set, read off the sets he wrote:

- capital: `counts_as_capital = yes` in its `location_potential` (every one of
  CM's thirteen, `capital_buildings.txt` and the two capital guards in
  `manpower_buildings.txt`), or the stricter `is_capital = yes` most National
  Destinies buildings use;
- market centre: `is_market_center = yes` in its `location_potential` or
  `allow` (CM's six from `market_buildings.txt`; `city_walls` is CM's one
  exception and stays his);
- control: a special building with a positive `local_max_control` in its
  `modifier` (CM's six uniques from `unique_buildings.txt`, all of them).

A building that produces goods is the Production tab's: that tab walks every
building type the game has (`cm_building_types_to_process`), modded ones
included, so it is left out here rather than built twice.

The beta's new buildings are few and named in `NEW_CAPITAL` and `NEW_ROSTER`;
each is checked against the criterion above and the build fails if the game
drops one. National Destinies' are read from its files at build time, about a
thousand of which belong in no set: each country can build a dozen of them,
and a CMF list holds fifty rows at most. They get a list of their own,
`auto_build_nd`, whose rows are given to the buildings of the player's own
country (the potential of the advance that unlocks each) the first time it
qualifies, and keep them: a row's settings stay with its building.
"""

from __future__ import annotations

import re
from pathlib import Path

NEW_CAPITAL = ("sacred_council", "khan_ordu", "chieftain_hall", "patrician_hall", "temple_militia")
NEW_ROSTER = ("village_granary",)
ROSTER_ROWS = 24  # CM Dev's own auto_build_list
ND_ROWS = 30
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
        self.capital: list[str] = []
        self.market: list[str] = []
        self.control: list[str] = []
        self.groups: dict[str, list[str]] = {}  # potential -> roster buildings, file order
        if root is None:
            return
        types = blocks(root / "in_game/common/building_types")
        advances = blocks(root / "in_game/common/advances")
        for key, body in types.items():
            k = kind(body)
            if k in ("capital", "market", "control"):
                getattr(self, k).append(key)
            elif k == "roster":
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

    def most_rows(self) -> int:
        """The most roster rows one tag can claim (its own and its formed variants)."""
        per_tag: dict[str, int] = {}
        for pot, keys in self.groups.items():
            for tag in set(re.findall(r"has_or_had_tag = (\w+)", pot)) or {pot}:
                per_tag[tag] = per_tag.get(tag, 0) + len(keys)
        return max(per_tag.values(), default=0)

    def count(self) -> int:
        return sum(len(v) for v in self.groups.values())


# --- edits to CM Dev's own files ------------------------------------------

def _once(text: str, anchor: str, where: str) -> None:
    if text.count(anchor) != 1:
        raise SystemExit(f"{where}: anchor occurs {text.count(anchor)} times: {anchor[:70]!r}")


def edit_custom_sets(text: str) -> str:
    """cm_ab_custom_effects.txt: the beta's capital buildings beside CM's, and a call into each
    National Destinies set."""
    cap = "\t\t\t\tcm_ab_stage_capital_type_here = { bt = city_guard }\n"
    _once(text, cap, "capital set")
    added = "".join(f"\t\t\t\tcm_ab_stage_capital_type_here = {{ bt = {k} }}\n" for k in NEW_CAPITAL)
    text = text.replace(cap, cap + "\t\t\t\t# cm_dev_perf: the beta's new capital buildings, and National Destinies'.\n"
                        + added + "\t\t\t\tcm_perf_nd_stage_capital = yes\n")
    market = "\t\t\t\tcm_ab_stage_custom_type_here = { bt = city_walls }\n"
    _once(text, market, "market-centre set")
    text = text.replace(market, market + "\t\t\t\t# cm_dev_perf: National Destinies' market-centre buildings.\n"
                        "\t\t\t\tcm_perf_nd_stage_market = yes\n")
    control = "\tcm_ab_add_control_type = { bt = tambo }\n"
    _once(text, control, "control set")
    return text.replace(control, control + "\t# cm_dev_perf: National Destinies' control buildings.\n"
                        "\tcm_perf_nd_add_control = yes\n")


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


def effects(nd: ND) -> str:
    lines = [
        "# Generated by mods/cm_dev_perf/tools/buildings.py; not to be edited by hand.",
        "# National Destinies' buildings in Construction Manager's Custom auto-build. Each one",
        "# strictly meeting the author's criterion for a set is called from that set",
        "# (cm_ab_custom_effects.txt); the rest of them, those that produce nothing, are the",
        "# auto_build_nd list's, whose rows go to the player's own country's buildings.",
        f"# {len(nd.capital)} capital, {len(nd.market)} market-centre, {len(nd.control)} control, "
        f"{nd.count()} for the list.",
        "",
        "# Root is the capital location. Expects scope:cm_country, scope:cm_location.",
        "cm_perf_nd_stage_capital = {",
        *[f"\tcm_ab_stage_capital_type_here = {{ bt = {k} }}" for k in nd.capital],
        "}",
        "",
        "# Root is a market-centre location. Expects scope:cm_country, scope:cm_location.",
        "cm_perf_nd_stage_market = {",
        *[f"\tcm_ab_stage_custom_type_here = {{ bt = {k} }}" for k in nd.market],
        "}",
        "",
        "# Root is the country.",
        "cm_perf_nd_add_control = {",
        *[f"\tcm_ab_add_control_type = {{ bt = {k} }}" for k in nd.control],
        "}",
        "",
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
        "\t\tset_variable = { name = cm_perf_nd_label value = flag:$bt$ }",
        "\t\tcm_perf_nd_place_row = yes",
        "\t}",
        "}",
        "",
        "# The next free row gets scope:cm_perf_nd_t, labelled with var:cm_perf_nd_label (the",
        "# building's own key, which is its name). Root is the country.",
        "cm_perf_nd_place_row = {",
        "\tchange_variable = { name = cm_perf_nd_rows_used add = 1 }",
        "\tadd_to_variable_list = { name = cm_perf_nd_rows target = scope:cm_perf_nd_t }",
        "\tset_local_variable = { name = cm_perf_nd_new value = 1 }",
        "\tswitch = {",
        "\t\ttrigger = var:cm_perf_nd_rows_used",
        _rows(ND_ROWS, "\t\t{i} = {{ cmm_set_list_item_value = {{ mod_id = cm setting_id = auto_build_nd item = {i} "
                       "value = scope:cm_perf_nd_t }} set_variable = {{ name = cm__auto_build_nd_i{i}_name "
                       "value = var:cm_perf_nd_label }} }}\n").rstrip("\n"),
        "\t}",
        "\tremove_variable = cm_perf_nd_label",
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
        "}",
        "",
        "# Callback for cmm_for_each_list_item. Root is the country.",
        "cm_perf_nd_row_visibility = {",
        "\tif = {",
        "\t\tlimit = { is_target_in_variable_list = { name = cm_perf_nd_rows target = scope:cmm_list_current_item_value } }",
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
        "}",
        "",
        "# Appends the rows that have a building to the roster's lookups, which",
        "# cm_rebuild_auto_build_lookups has just rebuilt from CM's own list, with the same fields and",
        "# the same scaling. Root is the country.",
        "cm_perf_nd_merge = {",
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
        "\t\tadd_to_variable_list = { name = cm_ab_building_types_list target = scope:cmm_list_current_item_value }",
        "\t\t# Read as CMF's own _cmm_build_list_*_item read them: every field has its default from",
        "\t\t# registration on, so the cmm map holds each key.",
        "\t\tset_local_variable = { name = cm_perf_nd_fk value = flag:$setting$_i$i$_f1 }",
        "\t\tif = {",
        "\t\t\tlimit = { \"variable_map(cmm|local_var:cm_perf_nd_fk)\" >= 1 }",
        "\t\t\tadd_to_variable_list = { name = cm_ab_building_types_enabled target = scope:cmm_list_current_item_value }",
        "\t\t}",
        "\t\tset_local_variable = { name = cm_perf_nd_fk value = flag:$setting$_i$i$_f2 }",
        "\t\tif = {",
        "\t\t\tlimit = { \"variable_map(cmm|local_var:cm_perf_nd_fk)\" >= 1 }",
        "\t\t\tadd_to_variable_list = { name = cm_ab_building_types_in_subjects_enabled target = scope:cmm_list_current_item_value }",
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
    return "﻿" + "\n".join(lines)


def scripted_guis() -> str:
    return "﻿" + "\n".join([
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
    ])


WORDS = {
    "russian": {
        "title": "Здания National Destinies",
        "desc": "Национальные здания вашей страны из National Destinies, которые ничего не производят: "
                "строка появляется, когда здание можно строить. По умолчанию выключены. Работают вместе со "
                "списком выше и по его правилам, после него. Производящие здания строит вкладка «Производство».",
        "column": "Здание",
    },
    "english": {
        "title": "National Destinies Buildings",
        "desc": "Your country's own National Destinies buildings that produce nothing: a row shows once the "
                "building can be built. Off by default. Worked with the list above and by its rules, after it. "
                "Buildings that produce goods are the Production tab's.",
        "column": "Building",
    },
}


def localization(lang: str) -> str:
    w = WORDS.get(lang, WORDS["english"])
    src = "cm__auto_build_list"
    dst = "cm__auto_build_nd"
    lines = [
        f"﻿l_{lang}:",
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
    # A row's label is the building's own name once it has one (flag:<building>); until then the
    # row is hidden, and its default label says what it is if it ever shows.
    lines += [f' {dst}_i{i}_name: "-"' for i in range(1, ND_ROWS + 1)]
    return "\n".join(lines) + "\n"
