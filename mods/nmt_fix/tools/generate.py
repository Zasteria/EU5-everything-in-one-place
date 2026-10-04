#!/usr/bin/env python3
"""Make National Mission Trees count the subjects its missions promise to count.

The base mod writes "N locations in this area, owned by us or by our subject"
as

    any_owned_location = {
        area = area:wallachia_area
        OR = { owner = root owner = { is_subject_of = root } }
        count >= 40
    }

but ``any_owned_location`` walks only the locations *root* owns, so the
subject half of the ``OR`` never sees a location and a vassal's land never
counts (Bulgaria's «Завоевать Валахию», 2026-09-29: whole area vassalised,
«Отвечающих этому требованию: 0»).  The author's own Swedish tree already has
the working form -- walk the area, test the owner:

    area:wallachia_area = {
        any_location_in_area = {
            OR = { owner ?= root owner ?= { is_subject_of = root } }
            count >= 40
        }
    }

This tool writes that form for every such block with one ``area`` or
``region``.  The rest cannot be one trigger, because a ``count`` does not add up
across two iterators: a count over the whole map compares a script value that
adds the subjects' ``num_locations`` to root's, and a count over an ``OR`` of
two areas or regions compares a script value walking each of them.  Those are
wrapped in a ``custom_tooltip`` so the mission says what it counts.

A mission file is replaced whole by a file of the same name loading later, so
only files with a change are written, and the mod must load after the base.

``PATCHES`` (0.2.0, 2026-10-03) carries the rest: what game 1.4 removed under
the base mod (Aragon's event, a trade modifier, a subject-type field), and
references the base mod always had that name nothing in the game (a holy-war
casus belli, a colonial country type, Gothenburg, India, «reformed», a
Byzantine culture) or give a casus belli the wrong way round.  Every anchor
must match the stated number of times, or the build stops.

Usage:  python3 mods/nmt_fix/tools/generate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
REPO = MOD.parent.parent
sys.path.insert(0, str(REPO / "tools"))

import refs  # noqa: E402

BASE = refs.known("national_mission_trees")
MISSIONS = "in_game/common/missions"
OUT = MOD / MISSIONS
VALUE = "nmt_fix_locations_with_subjects"

OPEN = re.compile(r"any_owned_location\s*=\s*\{")
SCOPE_LINE = re.compile(r"^[ \t]*(area|region)\s*=\s*((?:area|region):\w+)[ \t]*\n", re.M)
COUNT = re.compile(r"^[ \t]*count\s*>=\s*(\d+)[ \t]*\n", re.M)
OWNER = re.compile(r"\bowner = ")
MISSION = re.compile(r"^\t(\w+)\s*=\s*\{", re.M)
SHAPE = "OR = { owner = root owner = { is_subject_of = root } }"
OWNED = "OR = { owner ?= root owner ?= { is_subject_of = root } }"
GAME_LOC = REPO / "reference/game/main_menu/localization"

# (file under the base mod, text, replacement, times it occurs, why)
PATCHES = [
    # -- game 1.4 --
    ("in_game/common/missions/ara_crown_mission_pack.txt",
     "\t\t\thas_fired_unique_event = flavor_ara.6\n",
     "\t\t\tOR = {\n"
     "\t\t\t\thas_variable = ara_sindicat_remenca_flag\n"
     "\t\t\t\thas_estate_privilege = estate_privilege:ara_sindicat_remenca\n"
     "\t\t\t}\n", 1,
     "1.4 turned event flavor_ara.6 into ara_sindicat_remenca_decision; its "
     "first option sets this flag and grants the privilege"),
    ("main_menu/common/static_modifiers/ayy_modifiers.txt",
     "global_trade_through_owned_territory_efficiency = 0.10",
     "trade_land_efficiency = tiny_trade_land_efficiency_bonus", 1,
     "1.4 removed the modifier; the game's own 0.10 became this (Emilian advance)"),
    ("main_menu/common/static_modifiers/brb_modifiers.txt",
     "global_trade_through_owned_territory_efficiency = 0.10",
     "trade_land_efficiency = tiny_trade_land_efficiency_bonus", 1,
     "1.4 removed the modifier; the game's own 0.10 became this (Emilian advance)"),
    *((f"{root}/common/subject_types/{name}.txt",
       "\toverlord_protects_other_subjects = yes\n", "", 1,
       "1.4 removed the field from subject types")
      for root in ("in_game", "main_menu")
      for name in ("eng_welsh_principality", "hab_integrated_crown")),
    # -- the base mod's own, never valid --
    ("in_game/common/missions/hun_crown_of_saint_stephen_mission_pack.txt",
     "\t\t\t\tadd_casus_belli = {\n"
     "\t\t\t\t\ttarget = this\n"
     "\t\t\t\t\ttype = casus_belli:cb_holy_war\n"
     "\t\t\t\t}\n",
     "\t\t\t\tsave_scope_as = nmt_fix_holy_war_target\n"
     "\t\t\t\troot = {\n"
     "\t\t\t\t\tadd_casus_belli = {\n"
     "\t\t\t\t\t\ttarget = scope:nmt_fix_holy_war_target\n"
     "\t\t\t\t\t\ttype = casus_belli:cb_crusade\n"
     "\t\t\t\t\t}\n"
     "\t\t\t\t}\n", 1,
     "no cb_holy_war exists, and in the neighbour's scope each neighbour got a "
     "casus belli on itself"),
    ("in_game/common/missions/cas_castile_mission_pack.txt",
     "\t\t\t\t\towner ?= {\n"
     "\t\t\t\t\t\tadd_casus_belli = {\n"
     "\t\t\t\t\t\t\ttarget = root\n"
     "\t\t\t\t\t\t\ttype = casus_belli:cb_conquer_province\n"
     "\t\t\t\t\t\t\tprovince = prev.province\n"
     "\t\t\t\t\t\t\tyears = 50\n"
     "\t\t\t\t\t\t}\n"
     "\t\t\t\t\t}\n",
     "\t\t\t\t\tsave_scope_as = nmt_fix_target_location\n"
     "\t\t\t\t\troot = {\n"
     "\t\t\t\t\t\tadd_casus_belli = {\n"
     "\t\t\t\t\t\t\ttarget = scope:nmt_fix_target_location.owner\n"
     "\t\t\t\t\t\t\ttype = casus_belli:cb_conquer_province\n"
     "\t\t\t\t\t\t\tprovince = scope:nmt_fix_target_location.province\n"
     "\t\t\t\t\t\t\tyears = 50\n"
     "\t\t\t\t\t\t}\n"
     "\t\t\t\t\t}\n", 2,
     "the owners of Castile and Leon got the casus belli on Castile; the "
     "author's Carolingian tree has the right way round"),
    ("in_game/common/missions/hab_habsburg_mission_pack.txt",
     "limit = { country_type = country_type:colonial }",
     "limit = { is_subject_type = colonial_nation }", 2,
     "country types are location/pop/building/army/navy; colonial is a subject type"),
    ("in_game/common/missions/por_portuguese_mission_pack.txt",
     "capital = { region = region:india }",
     "capital = { sub_continent = sub_continent:south_asia }", 1,
     "no region india; its six regions make up sub-continent south_asia"),
    ("in_game/common/missions/mon_montferrat_mission_pack.txt",
     "\t\t\t\t\t\tculture = { this = culture:byzantine_culture }\n", "", 1,
     "no such culture; greek_culture beside it is the game's"),
    ("in_game/common/missions/swe_stormaktstiden_mission_pack.txt",
     "location:goteborg = {", "location:varberg = {", 1,
     "no location goteborg; the mission checks Varberg and its text says Varberg"),
    ("in_game/common/missions/brb_brabant_mission_pack.txt",
     "religion:reformed", "religion:calvinist", 2,
     "no religion reformed; the game's Reformed faith is calvinist"),
]


def game_name(key: str, lang: str) -> str:
    """The game's own name for an area or region, in ``lang``."""
    for path in (GAME_LOC / lang).glob("*.yml"):
        found = re.search(rf'^ {key}:\d* "([^"]*)"',
                          path.read_text(encoding="utf-8-sig"), re.M)
        if found:
            return found.group(1)
    sys.exit(f"no {lang} name for {key} in {GAME_LOC}")


def block_end(text: str, start: int) -> int:
    """Index just past the brace that closes the one opened before ``start``."""
    depth = 1
    i = start
    while depth:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return i


def indent_of(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    return re.match(r"[ \t]*", text[line_start:]).group(0)


def reindent(body: str) -> str:
    return re.sub(r"^(?=[ \t]*\S)", "\t", body, flags=re.M)


def rewrite(text: str, where: str, values: dict, tooltips: dict) -> tuple[str, int]:
    out = []
    pos = 0
    fixed = 0
    for match in OPEN.finditer(text):
        if match.start() < pos:
            continue
        end = block_end(text, match.end())
        body = text[match.end():end - 1]
        if "is_subject_of = root" not in body:
            continue
        pad = indent_of(text, match.start())
        scopes = SCOPE_LINE.findall(body)
        line = text[:match.start()].count("\n") + 1
        counts = COUNT.findall(body)
        shape = re.sub(r"\s+", " ", COUNT.sub("", SCOPE_LINE.sub("", body))).strip()
        if len(scopes) == 1 and len(counts) == 1 and shape == SHAPE:
            kind, target = scopes[0]
            inner = OWNER.sub("owner ?= ", SCOPE_LINE.sub("", body))
            new = (f"{target} = {{\n{pad}\tany_location_in_{kind} = {{"
                   f"{reindent(inner)}\t}}\n{pad}}}")
        elif len(counts) == 1 and shape in (SHAPE, f"OR = {{ }} {SHAPE}"):
            n = int(counts[0])
            if scopes:
                mission = MISSION.findall(text[:match.start()])[-1]
                value = f"nmt_fix_{mission}_count"
                walks = "".join(
                    f"\t{target} = {{\n\t\tevery_location_in_{kind} = {{\n"
                    f"\t\t\tlimit = {{ {OWNED} }}\n\t\t\tadd = 1\n\t\t}}\n\t}}\n"
                    for kind, target in scopes)
                values[value] = f"\tvalue = 0\n{walks}"
                key = f"nmt_fix_{mission}_tt"
                tooltips[key] = [t.split(":", 1)[1] for _, t in scopes], n
            else:
                value = "nmt_fix_locations_with_subjects"
                values[value] = ("\tvalue = num_locations\n"
                                 "\tevery_subject = {\n\t\tadd = num_locations\n\t}\n")
                key = f"nmt_fix_locations_{n}_tt"
                tooltips[key] = [], n
            new = (f"custom_tooltip = {{\n{pad}\ttext = {key}\n"
                   f"{pad}\t{value} >= {n}\n{pad}}}")
        else:
            sys.exit(f"{where}:{line}: a block of an unknown shape: {shape}")
        out.append(text[pos:match.start()])
        out.append(new)
        pos = end
        fixed += 1
    out.append(text[pos:])
    return "".join(out), fixed


def localization(tooltips: dict) -> None:
    whole = {"english": "At least {n} locations owned by us or our subjects",
             "russian": "Не менее {n} районов у нас и наших подданных"}
    some = {"english": "At least {n} locations in {where} owned by us or our subjects",
            "russian": "Не менее {n} районов в землях «{where}» у нас и наших подданных"}
    joiner = {"english": "» or «", "russian": "» или «"}
    for lang in whole:
        folder = MOD / "main_menu/localization" / lang
        folder.mkdir(parents=True, exist_ok=True)
        lines = [f"l_{lang}:"]
        for key, (targets, n) in sorted(tooltips.items()):
            if targets:
                where = joiner[lang].join(game_name(t, lang) for t in targets)
                if lang == "english":
                    where = f"«{where}»"
                text = some[lang].format(n=n, where=where)
            else:
                text = whole[lang].format(n=n)
            lines.append(f' {key}: "{text}"')
        (folder / f"nmt_fix_l_{lang}.yml").write_text(
            "\n".join(lines) + "\n", encoding="utf-8-sig")


def script_values(values: dict) -> None:
    folder = MOD / "in_game/common/script_values"
    folder.mkdir(parents=True, exist_ok=True)
    parts = ["# Generated by mods/nmt_fix/tools/generate.py -- do not edit.\n"
             "# Counts the base mod meant as \"ours or our subjects'\" where one\n"
             "# `count` cannot hold them: the whole map, or two areas at once.\n"]
    for name, body in sorted(values.items()):
        parts.append(f"{name} = {{\n{body}}}\n")
    (folder / "nmt_fix_values.txt").write_text("\n".join(parts), encoding="utf-8-sig")


def patch(text: str, where: str, edits: list) -> tuple[str, int]:
    """``text`` with each edit applied; an anchor off its count stops the build."""
    for old, new, times in edits:
        found = text.count(old)
        if found != times:
            sys.exit(f"{where}: {old.strip()[:60]!r} occurs {found} times, not {times}"
                     " -- the base mod changed; re-read it")
        text = text.replace(old, new)
    return text, len(edits)


def main() -> int:
    if OUT.is_dir():
        for old in OUT.glob("*.txt"):
            old.unlink()
    OUT.mkdir(parents=True, exist_ok=True)
    tooltips: dict = {}
    values: dict = {}
    total = 0
    patches: dict[str, list] = {}
    for rel, old, new, times, _why in PATCHES:
        patches.setdefault(rel, []).append((old, new, times))
    for path in sorted((BASE / MISSIONS).glob("*.txt")):
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        new, fixed = rewrite(text, path.name, values, tooltips)
        rel = f"{MISSIONS}/{path.name}"
        new, patched = patch(new, rel, patches.pop(rel, []))
        if not fixed and not patched:
            continue
        total += fixed
        (OUT / path.name).write_bytes(
            new.encode("utf-8-sig"))
        print(f"{path.name}: {fixed}" + (f", {patched} for 1.4" if patched else ""))
    for rel, edits in sorted(patches.items()):
        new, patched = patch((BASE / rel).read_bytes().decode("utf-8-sig"), rel, edits)
        (MOD / rel).parent.mkdir(parents=True, exist_ok=True)
        (MOD / rel).write_bytes(new.encode("utf-8-sig"))
        print(f"{rel}: {patched} for 1.4")
    script_values(values)
    localization(tooltips)
    print(f"nmt_fix: {total} blocks now count subjects")
    return 0


if __name__ == "__main__":
    sys.exit(main())
