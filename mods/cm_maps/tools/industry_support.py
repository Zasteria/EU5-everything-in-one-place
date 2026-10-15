"""Recommended industry support per area, read off the recommended urban rights.

Game 1.4 added industry support («Поддержка отрасли», `common/industry_types`):
a promotion granted to a whole area for one industry, which raises the output
of that industry's goods in the area and their demand across the country. The
urban-rights map already says which royal right each location should take; a
right is a set of goods (its `local_<good>_output_modifier` lines), an industry
is a set of goods (its `goods = { }`), and the two sets do not line up: the
artisan right is furniture, pottery *and* leather, so two thirds of it is
furnishings and one third crafts; masonry is masonry and glass, half crafts and
half luxury; dyes, in the textile and book rights, belong to no industry.

So an industry is scored by which of its goods each province will produce —
yes or no, not how well (his rule, 10-15: «отрасль просто хочет бафать домики,
которые там будут стоять; она не решает, будет ли там что-то стоять»):

- a good some royal right raises is produced in a province when the province's
  recommended right (the colour of the rights map) raises it, and only then;
- a good no right raises is produced where the province has its key raw
  material, KEY_RAW, his pick 10-15: steel where there is iron, porcelain where
  there is clay («там дофига глины надо»), lacquerware where there are dyes —
  not lumber, which is nearly everywhere.

A province adds, to each industry, the number of the industry's goods it will
produce divided by the number of goods in the industry, so an industry of two
goods and one of four are measured alike: three provinces under the textile
right are 3 for textiles, one each under tools and masonry plus one with iron
are 3/4 for crafts. The area's recommendation is the largest sum, a tie going
to the industry earlier in the game's file. By provinces, not towns: his rule
13.10 18:43. Everything is derived from the game's files and from the rights
map's own index order, so a patch that moves a good between rights, industries
or production methods is picked up by a rebuild.

The pass runs once per save after the rights map, behind its own stamp, and
stores the result on every location of the area: area variables are not used,
because nothing here has shown that they read back.
"""

from __future__ import annotations

import re
from pathlib import Path

RIGHTS_FILE = "in_game/common/town_rights/01_discovery.txt"  # the royal rights
INDUSTRIES_FILE = "in_game/common/industry_types/01_industries.txt"
TRMM_EFFECTS = "in_game/common/scripted_effects/bcm_trmm_effects.txt"

STAMP = "bcm_ind_stamp"
VERSION = 3
# A good no right raises is produced where the province has this raw material.
# A patch that adds such a good stops the build until it is given one here.
KEY_RAW = {"steel": "iron", "porcelain": "clay", "lacquerware": "dyes"}
BUILDINGS_DIR = "in_game/common/building_types"
WATER = "hsv { 0.58 0.50 0.52 }"   # the rights map's own water colour
EMPTY = "rgb { 40 40 40 }"


class Stop(Exception):
    pass


def _blocks(text: str) -> dict[str, str]:
    out, lines, i = {}, text.lstrip("﻿").splitlines(), 0
    while i < len(lines):
        m = re.match(r"^(\w+)\s*=\s*\{", lines[i])
        if not m:
            i += 1
            continue
        depth, j = 0, i
        while j < len(lines):
            code = lines[j].split("#")[0]
            depth += code.count("{") - code.count("}")
            if depth <= 0:
                break
            j += 1
        out[m.group(1)] = "\n".join(lines[i:j + 1])
        i = j + 1
    return out


def industries(game: Path) -> list[tuple[str, str, list[str]]]:
    """(key, colour, goods) in file order."""
    res = []
    for key, body in _blocks((game / INDUSTRIES_FILE).read_text(encoding="utf-8-sig")).items():
        goods = re.search(r"^\s*goods\s*=\s*\{([^}]*)\}", body, re.M)
        colour = re.search(r"^\s*color\s*=\s*((?:hsv360|hsv|rgb)\s*\{[^}]*\})", body, re.M)
        if not goods or not colour:
            raise Stop(f"{INDUSTRIES_FILE}: `{key}` has no goods list or no literal colour")
        res.append((key, colour.group(1), goods.group(1).split()))
    if not res:
        raise Stop(f"{INDUSTRIES_FILE}: no industries")
    return res


def right_order(trmm_effects: str) -> dict[int, str]:
    """The rights map's index -> right short name, from its own encoding."""
    pairs = re.findall(
        r"value = local_var:bcm_trmm_l_r_(\w+)\s*\n\s*multiply = 1000\s*\n\s*round = yes"
        r"\s*\n\s*multiply = 10\s*\n\s*add = (\d+)", trmm_effects)
    order = {int(i): name for name, i in pairs}
    if len(order) != 9:
        raise Stop(f"{TRMM_EFFECTS}: found {len(order)} rights in the encoding, expected 9")
    return order


def right_goods(game: Path, short: str) -> list[str]:
    key = f"royal_{short}_rights"
    body = _blocks((game / RIGHTS_FILE).read_text(encoding="utf-8-sig")).get(key)
    if body is None:
        raise Stop(f"{RIGHTS_FILE}: no `{key}`")
    goods = re.findall(r"local_(\w+?)_output_modifier", body)
    if not goods:
        raise Stop(f"{RIGHTS_FILE}: `{key}` raises no good's output")
    return goods


def makes_from(game: Path, good: str) -> list[str]:
    """`file:line` of every production method of `good` that takes its KEY_RAW."""
    found = []
    raw = KEY_RAW[good]
    for path in sorted((game / BUILDINGS_DIR).glob("*.txt")):
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        for n, line in enumerate(lines):
            if not re.match(rf"^\s*produced\s*=\s*{good}\b", line.split("#")[0]):
                continue
            top = n
            while top > 0 and not re.match(r"^\s*\w+\s*=\s*\{\s*(#.*)?$", lines[top]):
                top -= 1
            if any(re.match(rf"^\s*{raw}\s*=", l.split("#")[0]) for l in lines[top:n]):
                found.append(f"{BUILDINGS_DIR}/{path.name}:{top + 1}")
    return found


def weights(game: Path, trmm_effects: str):
    """industries; per right index (short, goods, {industry: goods of it the right raises});
    per industry the goods no right raises, each with its methods' raw shares."""
    inds = industries(game)
    order = right_order(trmm_effects)
    raised = {g for short in order.values() for g in right_goods(game, short)}
    table = {}
    for idx, short in sorted(order.items()):
        goods = right_goods(game, short)
        row = {key: sum(g in igoods for g in goods) for key, _, igoods in inds}
        table[idx] = (short, goods, {k: v for k, v in row.items() if v})
    land = {}
    for key, _, igoods in inds:
        for good in igoods:
            if good in raised:
                continue
            if good not in KEY_RAW:
                raise Stop(f"no right raises {good} ({key}) and KEY_RAW has no raw material for it")
            where = makes_from(game, good)
            if not where:
                raise Stop(f"{BUILDINGS_DIR}: no production method makes {good} from {KEY_RAW[good]}")
            land.setdefault(key, []).append((good, KEY_RAW[good], where))
    return inds, table, land


def _num(f: float) -> str:
    return f"{f:.3f}".rstrip("0").rstrip(".")


def effects(inds, table, land) -> str:
    keys = [k for k, _, _ in inds]
    sizes = {k: len(g) for k, _, g in inds}
    out = [
        "# Written by mods/cm_maps/tools/industry_support.py - do not edit by hand.",
        "# Recommended industry support per area: every province adds to each industry",
        "# the share of the industry's goods it will produce. A good a royal right",
        "# raises is produced where the province's recommended right raises it; a good",
        "# no right raises, where the province has its key raw material.",
        "# Goods each right gives each industry, from the game's files:",
    ]
    for idx, (short, goods, row) in table.items():
        split = ", ".join(f"{k} {v} of {sizes[k]}" for k, v in row.items()) or "none"
        out.append(f"#   {idx} royal_{short}_rights ({' '.join(goods)}): {split}")
    for key, goods in land.items():
        for good, raw, where in goods:
            out.append(f"#   {key}, from the land: {good} where there is {raw} (of {sizes[key]}; {', '.join(where)})")
    out += ["", "# Area scope.", "bcm_ind_recompute_area = {"]
    for k in keys + ["towns"]:
        out.append(f"\tset_local_variable = {{ name = bcm_ind_l_{k} value = 0 }}")
    # Goods counted whole here and divided by the industry's size at the end.
    # The rights map colours all of a province alike, so one location speaks for
    # it. bcm_ind_l_towns counts the provinces with a recommended right.
    out += [
        "\tevery_province_definition_in_area = {",
        "\t\trandom_location_in_province_definition = {",
        "\t\t\tlimit = {",
        "\t\t\t\thas_variable = bcm_trmm_best_idx",
        "\t\t\t\thas_variable = bcm_trmm_best_mil",
        "\t\t\t\tvar:bcm_trmm_best_mil > 0",
        "\t\t\t}",
        "\t\t\tchange_local_variable = { name = bcm_ind_l_towns add = 1 }",
    ]
    first = True
    for idx, (short, _, row) in table.items():
        if not row:
            continue  # a right none of whose goods is in an industry gives nothing
        kw = "if" if first else "else_if"
        first = False
        out.append(f"\t\t\t{kw} = {{")
        out.append(f"\t\t\t\tlimit = {{ var:bcm_trmm_best_idx = {idx} }}  # royal_{short}_rights")
        for k, v in row.items():
            out.append(f"\t\t\t\tchange_local_variable = {{ name = bcm_ind_l_{k} add = {v} }}")
        out.append("\t\t\t}")
    out.append("\t\t}")
    for key, goods in land.items():
        for good, raw, _ in goods:
            out += ["\t\tif = {  # " + good,
                    f"\t\t\tlimit = {{ any_location_in_province_definition = {{ raw_material ?= goods:{raw} }} }}",
                    f"\t\t\tchange_local_variable = {{ name = bcm_ind_l_{key} add = 1 }}",
                    "\t\t}"]
    out.append("\t}")
    for k in keys:
        out.append(f"\tset_local_variable = {{ name = bcm_ind_l_{k} value = {{ value = local_var:bcm_ind_l_{k} divide = {sizes[k]} }} }}")
    out += [
        "\t# The winner: strictly greater, so a tie keeps the earlier industry.",
        "\tset_local_variable = { name = bcm_ind_l_best value = 0 }",
        "\tset_local_variable = { name = bcm_ind_l_best_s value = 0 }",
    ]
    for n, k in enumerate(keys, 1):
        out += [
            "\tif = {",
            f"\t\tlimit = {{ local_var:bcm_ind_l_{k} > local_var:bcm_ind_l_best_s }}",
            f"\t\tset_local_variable = {{ name = bcm_ind_l_best value = {n} }}",
            f"\t\tset_local_variable = {{ name = bcm_ind_l_best_s value = local_var:bcm_ind_l_{k} }}",
            "\t}",
        ]
    out += ["\tevery_location_in_area = {",
            "\t\tset_variable = { name = bcm_ind_best value = local_var:bcm_ind_l_best }",
            "\t\tset_variable = { name = bcm_ind_towns value = local_var:bcm_ind_l_towns }"]
    for k in keys:
        out.append(f"\t\tset_variable = {{ name = bcm_ind_s_{k} value = local_var:bcm_ind_l_{k} }}")
    out += ["\t}", "}", "",
            "# No scope. Runs after the rights map, which it reads; bcm_run_lobby_setup stamps it.",
            "bcm_ind_recompute_all = {",
            "\tevery_area = { bcm_ind_recompute_area = yes }",
            "}", ""]
    return "\n".join(out)


def values(inds) -> str:
    out = ["# Written by mods/cm_maps/tools/industry_support.py - do not edit by hand.",
           "# Bump to make every save redo the industry-support pass.",
           f"bcm_ind_version_value = {VERSION}", "",
           "# Location scope: the area's votes, read by the map's tooltip.",
           "bcm_ind_sv_towns = {", "\tvalue = 0",
           "\tif = { limit = { has_variable = bcm_ind_towns } add = var:bcm_ind_towns }", "}"]
    for k, _, _ in inds:
        out += [f"bcm_ind_sv_{k} = {{", "\tvalue = 0",
                f"\tif = {{ limit = {{ has_variable = bcm_ind_s_{k} }} add = var:bcm_ind_s_{k} }}", "}"]
    return "\n".join(out) + "\n"


def triggers() -> str:
    return ("# Written by mods/cm_maps/tools/industry_support.py - do not edit by hand.\n"
            "# No scope. The industry-support pass ran on this save at this version.\n"
            "bcm_ind_data_is_current = {\n"
            f"\thas_global_variable = {STAMP}\n"
            f"\tglobal_var:{STAMP} = bcm_ind_version_value\n"
            "}\n")


def map_mode(inds) -> str:
    out = ["# Written by mods/cm_maps/tools/industry_support.py - do not edit by hand.",
           "# Colours are the industries' own, common/industry_types/01_industries.txt.",
           "bcm_industry_support = {", "\tmap_color = {",
           "\t\tif = {", "\t\t\tlimit = { is_land = no }", f"\t\t\tvalue = {WATER}", "\t\t}",
           "\t\telse_if = {",
           "\t\t\tlimit = { OR = { NOT = { has_variable = bcm_ind_best } var:bcm_ind_best = 0 } }",
           f"\t\t\tvalue = {EMPTY}", "\t\t}"]
    for n, (k, colour, _) in enumerate(inds, 1):
        out += ["\t\telse_if = {", f"\t\t\tlimit = {{ var:bcm_ind_best = {n} }}  # {k}",
                f"\t\t\tvalue = {colour}", "\t\t}"]
    out.append("\t}")
    out.append("")
    for k, colour, _ in inds:
        out += ["\tlegend_key = {", f'\t\tdesc = "{k}"', f"\t\tcolor = {colour}", "\t}"]
    out += ["\tlegend_key = {", '\t\tdesc = "bcm_ind_legend_none"', f"\t\tcolor = {EMPTY}", "\t}", "",
            "\ttooltip_key = {",
            "\t\tif = {", "\t\t\tlimit = { is_land = no }",
            "\t\t\tvalue = MAPMODE_BCM_INDUSTRY_SUPPORT_TT_WATER", "\t\t}",
            "\t\telse_if = {",
            "\t\t\tlimit = { OR = { NOT = { has_variable = bcm_ind_best } var:bcm_ind_best = 0 } }",
            "\t\t\tvalue = MAPMODE_BCM_INDUSTRY_SUPPORT_TT_NONE", "\t\t}"]
    for n, (k, _, _) in enumerate(inds, 1):
        out += ["\t\telse_if = {", f"\t\t\tlimit = {{ var:bcm_ind_best = {n} }}",
                f"\t\t\tvalue = MAPMODE_BCM_INDUSTRY_SUPPORT_TT_{k.upper()}", "\t\t}"]
    out += ["\t}", "",
            # The rest is the rights map's own (bcm_best_town_right), so the two
            # read alike.
            "\tsmall_map_names = raw_material", "\tmedium_map_names = raw_material",
            "\tlarge_map_names = raw_material", "",
            "\tsmall_tooltip_context = location", "\tmedium_tooltip_context = location",
            "\tlarge_tooltip_context = location", "",
            "\tfill_in_impassable = yes", "\tenable_snow = no", "",
            "\tflatmap_behaviour = always", "\tuse_fow = no", "",
            "\tcategory = economy", "\tindex = 1", "",
            "\tmap_markers = {", "\t\tfort_marker = no", "\t\tport_marker = no", "\t\tunit_marker = no",
            "\t\tcombat_marker = no", "\t\tcombat_imminent_marker = no", "\t\tsupply_depot_marker = no",
            "\t\tmarket_marker = no", "\t\ttoll_marker = no", "\t\tdynasty_marker = no",
            "\t\traw_goods_marker = no", "\t}", "",
            "\tgradient_parameters = {", "\t\tzoom_step = 2", "",
            "\t\tgradient_alpha_inside = 1", "\t\tgradient_alpha_outside = 1",
            "\t\tgradient_width = 0.0375", "\t\tgradient_color_mult = 0.9", "\t\tedge_width = 0",
            "\t\tedge_sharpness = 0.01", "\t\tedge_alpha = 0", "\t\tedge_color_mult = 0",
            "\t\tbefore_lighting_blend = 0.5", "\t\tafter_lighting_blend = 0.5", "\t}", "",
            "\trefresh_colors_on_selection_change = no", "\tcolor_refresh_counters = { }", "}", ""]
    return "\n".join(out)


TEXT = {
    "russian": {
        "name": "Рекомендуемая поддержка отрасли",
        "desc": ("#T $mapmode_bcm_industry_support_name$#!\\nОкрашивает каждую [area|e] по [industry_promotion|e], "
                 "которая поднимет больше всего того, что там будут производить. Каждая провинция области "
                 "даёт отрасли долю её товаров, которые там будут: товары своего рекомендуемого городского права, "
                 "сталь — где есть железо, фарфор — где есть глина, лак — где есть краски. Так отрасль из двух "
                 "товаров и отрасль из четырёх меряются одинаково."),
        "best": "Область [ROOT.GetLocation.GetArea.GetName]: поддержка «#Y ${key}$#!»",
        "votes": "Доли товаров отраслей, сумма по провинциям",
        "none": ("В области [ROOT.GetLocation.GetArea.GetName] не будут производить ни одного товара отраслей — "
                 "рекомендовать нечего."),
        "water": "[ROOT.GetLocation.GetName] — не суша.",
        "legend_none": "Нечего рекомендовать",
    },
    "english": {
        "name": "Recommended industry support",
        "desc": ("#T $mapmode_bcm_industry_support_name$#!\\nColours every [area|e] by the [industry_promotion|e] "
                 "that would raise the most of what will be produced there. Every province of the area gives an "
                 "industry the share of its goods that will be made there: the goods of the province's recommended "
                 "urban right, steel where there is iron, porcelain where there is clay, lacquerware where there are "
                 "dyes. An industry of two goods and one of four are measured alike."),
        "best": "Area [ROOT.GetLocation.GetArea.GetName]: support «#Y ${key}$#!»",
        "votes": "Share of each industry's goods, summed over provinces",
        "none": ("Area [ROOT.GetLocation.GetArea.GetName] will produce none of the industries' goods — nothing "
                 "to recommend."),
        "water": "[ROOT.GetLocation.GetName] is not land.",
        "legend_none": "Nothing to recommend",
    },
}


def localization(language: str, inds) -> str:
    t = TEXT.get(language, TEXT["english"])  # a language without its own text reads English
    votes = "".join(
        f"\\n  ${k}$: [ROOT.GetLocation.MakeScope.ScriptValue('bcm_ind_sv_{k}')|2]" for k, _, _ in inds)
    towns = (" [ROOT.GetLocation.MakeScope.ScriptValue('bcm_ind_sv_towns')|0]")
    lines = [f"l_{language}:",
             f' mapmode_bcm_industry_support_name: "{t["name"]}"',
             f' MAPMODE_BCM_INDUSTRY_SUPPORT: "{t["desc"]}"',
             f' MAPMODE_BCM_INDUSTRY_SUPPORT_TT_WATER: "{t["water"]}"',
             f' MAPMODE_BCM_INDUSTRY_SUPPORT_TT_NONE: "{t["none"]}"',
             f' bcm_ind_legend_none: "{t["legend_none"]}"']
    for k, _, _ in inds:
        best = t["best"].replace("{key}", k)
        lines.append(f' MAPMODE_BCM_INDUSTRY_SUPPORT_TT_{k.upper()}: "{best}\\n{t["votes"]} ({towns.strip()}):{votes}"')
    return "\n".join(lines) + "\n"


def files(written: dict[str, str], game: Path) -> dict[str, str]:
    inds, table, land = weights(game, written[TRMM_EFFECTS])
    out = {
        "in_game/common/scripted_effects/bcm_ind_effects.txt": effects(inds, table, land),
        "in_game/common/script_values/bcm_ind_values.txt": values(inds),
        "in_game/common/scripted_triggers/bcm_ind_triggers.txt": triggers(),
        "in_game/gfx/map/map_modes/bcm_industry_support_map_mode.txt": map_mode(inds),
    }
    for language in TEXT:
        out[f"main_menu/localization/{language}/bcm_ind_l_{language}.yml"] = localization(language, inds)
    return out
