#!/usr/bin/env python3
"""The one generated file of `cmf_saved_settings`: his saved values, as script.

`mods/cmf_saved_settings` prints every CMF setting into `debug.log` as a block of
`CMFSAVE` lines; `mods.bat` → 5 lifts it into a file and calls this to write
`bag_cmfs_apply` into **the game's copy** of the same mod (`GENERATED`). **The
game can read nothing else**: a mod cannot write a file or read another save
(docs/research/engine_reach.md), so the way back in is script in a mod folder.
The repository holds the same file empty (what this writes for no settings);
`mods.bat` → 3 rewrites it from `last.txt` after each install, and the digest
that says «совпадает» leaves it out.

What the mod does with it, once per new game (the hooks are static, in the mod):

- **Only in a game started with it on.** `on_game_started_after_lobby` raises
  `bag_cmfs_new_game`; a loaded old save never has it, so his settings there
  are never touched.
- **Each key once.** A value is written only when CMF has registered the key
  (it is in the `cmm` map) and only the first time; the mark lives in the save,
  so what he changes later in the game stays. A key that a mod registers later
  — a newer mod version — is caught on the next registration pass.
- **Then the mod is told.** One `cmf_on_callback` per setting that changed, as
  CMF's own «Сбросить» does, so aliases and the mods' own reactions follow.
- **Ordered lists are put back in the saved order**, items the save does not
  know (a mod update) after them; `cmf_dev_beta`'s place numbers are dropped so
  it falls back to the row index.

    python3 tools/cmf_saved_apply.py <last.txt> <mod folder>   write by hand
    python3 tools/cmf_saved_apply.py --stub                    the empty file
"""

from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path

MOD = "cmf_saved_settings"
GENERATED = "in_game/common/scripted_effects/bag_cmfs_my_values.txt"
BOM = "﻿"

# A plain setting is `<mod>__<setting>`; a list field `<mod>__<setting>_i<N>_f<slot>`.
KEY = re.compile(r"^\w+__\w+$")
FIELD = re.compile(r"^(\w+__\w+?)_i\d+_f\d+$")
ROW = re.compile(r"^CMFSAVE ([cg]) (-?[\d.]+) (\w+)$")
ORDER = re.compile(r"^CMFSAVE order ((\w+__\w+?)_i\d+)$")


def parse(lines: list[str]) -> tuple[dict, dict, list[str]]:
    """values[(kind, key)] = number, order[setting] = [item flags], skipped keys."""
    values: dict[tuple[str, str], str] = OrderedDict()
    order: dict[str, list[str]] = OrderedDict()
    skipped: list[str] = []
    for raw in lines:
        line = raw.strip()
        row = ROW.match(line)
        if row:
            kind, number, key = row.groups()
            # `cmm_init` is CMF's own bookkeeping, and the saver's button is not
            # a setting anybody wants carried over.
            if not KEY.match(key) or key.startswith("bag_cmfs__"):
                skipped.append(key)
                continue
            values[(kind, key)] = number
            continue
        item = ORDER.match(line)
        if item:
            order.setdefault(item.group(2), []).append(item.group(1))
    return values, order, skipped


def number(text: str) -> str:
    value = float(text)
    return str(int(value)) if value == int(value) else ("%.3f" % value).rstrip("0")


def owner(key: str) -> str:
    field = FIELD.match(key)
    return field.group(1) if field else key


def apply_effect(values: dict, order: dict) -> str:
    out = ["# Scope: country (a human). Written by tools/cmf_saved_apply.py (mods.bat → 5\n# and → 3) from his saved settings; empty in the repository — do not edit.",
           "bag_cmfs_apply = {",
           "\tset_global_variable = { name = bag_cmfs_total value = %d }" % (len(values) + len(order)),
           "\tsave_scope_as = bag_cmfs_owner"]
    by_setting: dict[tuple[str, str], list[tuple[str, str]]] = OrderedDict()
    for (kind, key), value in values.items():
        by_setting.setdefault((kind, owner(key)), []).append((key, value))

    for (kind, setting), keys in by_setting.items():
        g = "global_" if kind == "g" else ""
        out.append("\t# %s" % setting)
        out.append("\tset_local_variable = { name = bag_cmfs_touched value = 0 }")
        for key, value in keys:
            out += [
                "\tif = {",
                "\t\tlimit = {",
                "\t\t\tis_key_in_%svariable_map = { name = cmm target = flag:%s }" % (g, key),
                # Guarded: the first lookup comes before the map exists (error.log, 1.4.5 run 10-30).
                "\t\t\tNOT = { AND = { has_%svariable_map = bag_cmfs_done"
                " is_key_in_%svariable_map = { name = bag_cmfs_done target = flag:%s } } }" % (g, g, key),
                "\t\t}",
                # CMF itself removes before it adds (cmm_core_auto_apply_scripted_gui).
                "\t\tremove_from_%svariable_map = { name = cmm key = flag:%s }" % (g, key),
                "\t\tadd_to_%svariable_map = { name = cmm key = flag:%s value = %s }" % (g, key, number(value)),
                "\t\tadd_to_%svariable_map = { name = bag_cmfs_done key = flag:%s value = 1 }" % (g, key),
                "\t\tset_local_variable = { name = bag_cmfs_touched value = 1 }",
                "\t\tchange_global_variable = { name = bag_cmfs_applied add = 1 }",
                "\t}",
            ]
        out += [
            "\tif = {",
            "\t\tlimit = { local_var:bag_cmfs_touched = 1 }",
            "\t\tbag_cmfs_tell = { setting = %s }" % setting,
            "\t}",
        ]

    for setting, items in order.items():
        out += [
            "\t# order of %s" % setting,
            "\tif = {",
            "\t\tlimit = {",
            "\t\t\thas_variable_list = cmm_list_items_%s" % setting,
            "\t\t\tNOT = { AND = { has_variable_map = bag_cmfs_done"
            " is_key_in_variable_map = { name = bag_cmfs_done target = flag:%s } } }" % setting,
            "\t\t}",
            "\t\tclear_variable_list = bag_cmfs_tmp",
            "\t\tevery_in_list = {",
            "\t\t\tvariable = cmm_list_items_%s" % setting,
            "\t\t\tsave_scope_as = bag_cmfs_item",
            "\t\t\tscope:bag_cmfs_owner = { add_to_variable_list = { name = bag_cmfs_tmp target = scope:bag_cmfs_item } }",
            "\t\t}",
            "\t\tclear_variable_list = cmm_list_items_%s" % setting,
        ]
        for item in items:
            out += [
                "\t\tif = {",
                "\t\t\tlimit = { is_target_in_variable_list = { name = bag_cmfs_tmp target = flag:%s } }" % item,
                "\t\t\tadd_to_variable_list = { name = cmm_list_items_%s target = flag:%s }" % (setting, item),
                "\t\t}",
            ]
        out += [
            "\t\tevery_in_list = {",
            "\t\t\tvariable = bag_cmfs_tmp",
            "\t\t\tsave_scope_as = bag_cmfs_item",
            "\t\t\tscope:bag_cmfs_owner = {",
            "\t\t\t\tif = {",
            "\t\t\t\t\tlimit = { NOT = { is_target_in_variable_list = { name = cmm_list_items_%s target = scope:bag_cmfs_item } } }" % setting,
            "\t\t\t\t\tadd_to_variable_list = { name = cmm_list_items_%s target = scope:bag_cmfs_item }" % setting,
            "\t\t\t\t}",
            "\t\t\t}",
            "\t\t}",
            "\t\tclear_variable_list = bag_cmfs_tmp",
            "\t\t# cmf_dev_beta numbers the rows in cmf_beta_list_place; without an",
            "\t\t# entry it shows the row index, which is right after a rebuild.",
            "\t\tif = {",
            "\t\t\tlimit = { has_variable_map = cmf_beta_list_place }",
        ]
        for item in items:
            out += [
                "\t\t\tif = {",
                "\t\t\t\tlimit = { is_key_in_variable_map = { name = cmf_beta_list_place target = flag:%s } }" % item,
                "\t\t\t\tremove_from_variable_map = { name = cmf_beta_list_place key = flag:%s }" % item,
                "\t\t\t}",
            ]
        out += [
            "\t\t}",
            "\t\tadd_to_variable_map = { name = bag_cmfs_done key = flag:%s value = 1 }" % setting,
            "\t\tchange_global_variable = { name = bag_cmfs_applied add = 1 }",
            "\t\tbag_cmfs_tell = { setting = %s }" % setting,
            "\t}",
        ]
    out.append("}")
    return "\n".join(out) + "\n"


def file_text(lines: list[str]) -> tuple[str, dict]:
    """The generated file for this block, and what went in."""
    values, order, skipped = parse(lines)
    report = {"values": len(values), "lists": len(order), "skipped": skipped,
              "mods": sorted({key.split("__")[0] for _, key in values})}
    return BOM + apply_effect(values, order), report


def write_into(mod_folder: Path, lines: list[str]) -> dict:
    """Write the generated file into a copy of the mod. Returns what went in."""
    text, report = file_text(lines)
    path = mod_folder / GENERATED
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return report


def main(argv: list[str]) -> int:
    if argv[1:] == ["--stub"]:
        sys.stdout.write(file_text([])[0])
        return 0
    if len(argv) != 3:
        print(__doc__)
        return 2
    source = Path(argv[1])
    print(write_into(Path(argv[2]), source.read_text(encoding="utf-8").splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
