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

So each province of the area votes for industries with the right the rights
map colours it with, split by the share of the right's goods each industry
covers, and the area's recommendation is the industry with the most votes.
His rule 13.10 18:43: by provinces, as the rights map colours them, not by
towns («4 провинции под винокурни и 2 под ремесло и камень — спиртные
напитки»). A province with nothing recommended does not vote. Everything is derived from the game's
files and from the rights map's own index order, so a patch that moves a good
between rights or industries is picked up by a rebuild.

The pass runs once per save after the rights map, behind its own stamp, and
stores the result on every location of the area: area variables are not used,
because nothing here has shown that they read back.
"""

from __future__ import annotations

import re
from fractions import Fraction
from pathlib import Path

RIGHTS_FILE = "in_game/common/town_rights/01_discovery.txt"  # the royal rights
INDUSTRIES_FILE = "in_game/common/industry_types/01_industries.txt"
TRMM_EFFECTS = "in_game/common/scripted_effects/bcm_trmm_effects.txt"

STAMP = "bcm_ind_stamp"
VERSION = 2
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


def weights(game: Path, trmm_effects: str):
    inds = industries(game)
    table = {}
    for idx, short in sorted(right_order(trmm_effects).items()):
        goods = right_goods(game, short)
        row = {}
        for key, _, igoods in inds:
            share = Fraction(sum(g in igoods for g in goods), len(goods))
            if share:
                row[key] = share
        table[idx] = (short, goods, row)
    return inds, table


def _num(f: Fraction) -> str:
    return f"{float(f):.3f}".rstrip("0").rstrip(".")


def effects(inds, table) -> str:
    keys = [k for k, _, _ in inds]
    out = [
        "# Written by mods/cm_maps/tools/industry_support.py - do not edit by hand.",
        "# Recommended industry support per area: each province votes with its",
        "# recommended royal right, split by the share of the right's goods each",
        "# industry covers. Shares, from the game's files:",
    ]
    for idx, (short, goods, row) in table.items():
        split = ", ".join(f"{k} {_num(v)}" for k, v in row.items()) or "none"
        out.append(f"#   {idx} royal_{short}_rights ({' '.join(goods)}): {split}")
    out += ["", "# Area scope.", "bcm_ind_recompute_area = {"]
    for k in keys + ["towns"]:
        out.append(f"\tset_local_variable = {{ name = bcm_ind_l_{k} value = 0 }}")
    # The rights map scores a province and colours all its locations alike,
    # so one location speaks for it. bcm_ind_l_towns counts the voting provinces.
    out += [
        "\tevery_province_definition_in_area = {",
        "\t\trandom_location_in_province_definition = {",
        "\t\tlimit = {",
        "\t\t\thas_variable = bcm_trmm_best_idx",
        "\t\t\thas_variable = bcm_trmm_best_mil",
        "\t\t\tvar:bcm_trmm_best_mil > 0",
        "\t\t}",
        "\t\tchange_local_variable = { name = bcm_ind_l_towns add = 1 }",
    ]
    first = True
    for idx, (short, _, row) in table.items():
        if not row:
            continue  # a right none of whose goods is in an industry votes for nothing
        kw = "if" if first else "else_if"
        first = False
        out.append(f"\t\t{kw} = {{")
        out.append(f"\t\t\tlimit = {{ var:bcm_trmm_best_idx = {idx} }}  # royal_{short}_rights")
        for k, v in row.items():
            out.append(f"\t\t\tchange_local_variable = {{ name = bcm_ind_l_{k} add = {_num(v)} }}")
        out.append("\t\t}")
    first_line = out.index("\t\trandom_location_in_province_definition = {") + 1
    out[first_line:] = ["\t" + line for line in out[first_line:]]
    out += [
        "\t\t}",
        "\t}",
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
                 "которую стоит выбрать для неё по карте рекомендуемых городских прав: каждая провинция "
                 "области голосует правом, в цвет которого её красит та карта, а право делится между отраслями по доле своих "
                 "товаров. Права ткачей и книжников частью приходятся на краски, которых нет ни в одной отрасли."),
        "best": "Область [ROOT.GetLocation.GetArea.GetName]: поддержка «#Y ${key}$#!»",
        "votes": "Голоса провинций по рекомендуемым правам",
        "none": ("В области [ROOT.GetLocation.GetArea.GetName] нет провинций с рекомендуемым правом — "
                 "рекомендовать нечего."),
        "water": "[ROOT.GetLocation.GetName] — не суша.",
        "legend_none": "Нет провинций с рекомендацией",
    },
    "english": {
        "name": "Recommended industry support",
        "desc": ("#T $mapmode_bcm_industry_support_name$#!\\nColours every [area|e] by the [industry_promotion|e] "
                 "to choose for it from the recommended urban rights map: every province of the area votes "
                 "with the right that map colours it with, split between industries by the share of the right's goods. The "
                 "textile and book rights partly go to dyes, which no industry covers."),
        "best": "Area [ROOT.GetLocation.GetArea.GetName]: support «#Y ${key}$#!»",
        "votes": "Province votes by recommended right",
        "none": ("Area [ROOT.GetLocation.GetArea.GetName] has no province with a recommended right — nothing "
                 "to recommend."),
        "water": "[ROOT.GetLocation.GetName] is not land.",
        "legend_none": "No province with a recommendation",
    },
}


def localization(language: str, inds) -> str:
    t = TEXT[language]
    votes = "".join(
        f"\\n  ${k}$: [ROOT.GetLocation.MakeScope.ScriptValue('bcm_ind_sv_{k}')|1]" for k, _, _ in inds)
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
    inds, table = weights(game, written[TRMM_EFFECTS])
    out = {
        "in_game/common/scripted_effects/bcm_ind_effects.txt": effects(inds, table),
        "in_game/common/script_values/bcm_ind_values.txt": values(inds),
        "in_game/common/scripted_triggers/bcm_ind_triggers.txt": triggers(),
        "in_game/gfx/map/map_modes/bcm_industry_support_map_mode.txt": map_mode(inds),
    }
    for language in TEXT:
        out[f"main_menu/localization/{language}/bcm_ind_l_{language}.yml"] = localization(language, inds)
    return out
