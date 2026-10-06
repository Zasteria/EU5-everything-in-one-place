#!/usr/bin/env python3
"""Nobles Auto Marry - Continued, carried to game 1.4, with Russian text.

A whole copy of the Workshop mod (`eu5.noblesautomarry.fix`, 3681629733),
loaded INSTEAD of it.  The base declares 1.3.*; checked 2026-10-06 against the
1.4 beta files and API dumps, every trigger, effect, modifier, data function and
GUI block it names still exists, and `character_can_marry_trigger` became a
wrapper over the engine's `is_eligible_for_marriage`.  So the copy changes only:

* `metadata.json` -- 1.4.*, our id, so the launcher stops warning;
* `PATCHES` -- every on_action that can only fire player events now says
  `is_ai = no` first, so AI countries stop counting their courtiers every month
  for events that refuse them anyway (each of those events already opens with
  `is_ai = no`).  AI marriage, when switched on, runs through its own
  on_actions, which are not touched;
* a byte order mark on the seven script and interface files the base ships
  without one;
* automatic royal marriages abroad (his ask, 2026-10-06): our own files under
  `own/`, copied in whole -- an on_action in the author's monthly list, a
  hidden event that marries one unmarried member of the crown estate eligible
  for a royal marriage to one of another country's royal family each month,
  without diplomats or opinion; a toggle in the settings menu
  (`auto_marry_royal_off`, on by default); the author's royal reminders fire
  only while it is off;
* marriage ages by class (his ask, 2026-10-06): every "age_in_years > 18"
  that picks whom to marry in the player's events, triggers and effects
  becomes `auto_marry_age_ok_<class> = yes` (`AGE_BLOCKS`), and a settings
  event (`auto_marry_age.1`, from the settings menu) sets the age per class.
  Unset, the age stays 19, the author's own;
* the Russian file, which in the base is the English one under a Russian
  header.  It is written by hand in `main_menu/localization/russian/` and this
  tool never touches it.

Everything else under `in_game/` and `main_menu/` is derived: do not edit it.

Usage:  python3 mods/auto_marry/tools/generate.py
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
REPO = MOD.parent.parent
sys.path.insert(0, str(REPO / "tools"))

import refs  # noqa: E402

BASE = refs.mod("eu5.noblesautomarry.fix")
PARTS = ("in_game", "main_menu")
OWN = Path("main_menu/localization/russian")  # hand written, kept
OWN_TREE = MOD / "own"  # our own files, copied over the base's

REVISION = "beta5"
TEXT = (".txt", ".gui", ".yml")
BOM = b"\xef\xbb\xbf"

PLAYER_ON_ACTIONS = (
    "noble_auto_marry_on_action",
    "noble_auto_marry_on_action_crown_estate",
    "noble_auto_marry_on_action_burghers_estate",
    "noble_auto_marry_on_action_clergy_estate",
    "noble_auto_marry_on_action_peasants_estate",
    "noble_auto_marry_on_action_dhimmi_estate",
    "noble_auto_marry_on_action_tribes_estate",
    "noble_auto_marry_on_action_cossacks_estate",
)

ROYAL_OPTION = """\toption = { # toggle royal family auto marriages (auto_marry)
\t\tname = noble_auto_marry.63.k
\t\tif = {
\t\t\tlimit = { has_variable = auto_marry_royal_off }
\t\t\tremove_variable = auto_marry_royal_off
\t\t}
\t\telse = {
\t\t\tset_variable = auto_marry_royal_off
\t\t}
\t\ttrigger_event_silently = {
\t\t\tid = noble_auto_marry.63
\t\t}
\t}
"""

AGE_OPTION = """\toption = { # marriage ages by class (auto_marry)
\t\tname = noble_auto_marry.63.l
\t\ttrigger_event_silently = {
\t\t\tid = auto_marry_age.1
\t\t}
\t}
"""

MENU_CLOSE = "\toption = { # close menu\n\t\tname = noble_auto_marry.63.h\n"

# file -> [(anchor, replacement, times the anchor must occur)]
PATCHES = {
    "in_game/common/on_action/automarry_on_actions.txt": [
        (f"{name} = {{\n\ttrigger = {{\n",
         f"{name} = {{\n\ttrigger = {{\n\t\tis_ai = no\n", 1)
        for name in PLAYER_ON_ACTIONS
    ] + [
                ("\t\tnoble_auto_marry_init_pop_limit\n",
         "\t\tnoble_auto_marry_init_pop_limit\n\t\tauto_marry_royal_on_action\n", 1),
        # reminders only while the royal family does not marry by itself
        ("\t\tNOT = { has_variable = hide_royal_marriage_events }\n",
         "\t\tNOT = { has_variable = hide_royal_marriage_events }\n"
         "\t\thas_variable = auto_marry_royal_off\n", 1),
    ],
    "in_game/events/nobles_auto_marry.txt": [
        (MENU_CLOSE, ROYAL_OPTION + AGE_OPTION + MENU_CLOSE, 1),
    ],
}


# Who is old enough to marry: the author writes "age_in_years > 18" wherever a
# character is picked for a marriage, and "> 16" only when counting relatives.
# Each top-level block that picks belongs to one class; the AI's blocks stay.
AGE_FILES = (
    "in_game/events/nobles_auto_marry.txt",
    "in_game/common/scripted_triggers/noble_auto_marry_triggers.txt",
    "in_game/common/scripted_effects/noble_auto_marry_effects.txt",
)
AGE_BLOCKS = {
    "noble_valid_for_auto_marry_unrestricted": "nobles",
    "noble_valid_for_auto_marry_selective": "nobles",
    "noble_valid_for_auto_marry_dynastic_preservation": "nobles",
    "noble_marriage_immediate_effect": "nobles",
    "noble_auto_marry.57": "royal",  # the author's royal reminder
    "burgher_valid_for_auto_marry": "burghers",
    "burgher_marriage_immediate_effect": "burghers",
    "clergy_valid_for_auto_marry": "clergy",
    "clergy_marriage_immediate_effect": "clergy",
    "peasants_valid_for_auto_marry": "peasants",
    "peasant_marriage_immediate_effect": "peasants",
    "dhimmi_valid_for_auto_marry": "dhimmi",
    "dhimmi_marriage_immediate_effect": "dhimmi",
    "tribes_valid_for_auto_marry": "tribes",
    "tribes_marriage_immediate_effect": "tribes",
    "cossacks_valid_for_auto_marry": "cossacks",
    "cossack_marriage_immediate_effect": "cossacks",
}
AGE_AI = {
    "noble_valid_for_auto_marry_dynastic_preservation_for_ai",
    "non_noble_valid_for_auto_marry_for_ai",
    "noble_marriage_immediate_effect_for_ai",
    "non_noble_marriage_immediate_effect_for_ai",
}
AGE_FROM = "age_in_years > 18"
AGE_COUNT = 42  # replaced; a different number means the base changed


def ages() -> int:
    done = 0
    for rel in AGE_FILES:
        path = MOD / rel
        text = path.read_text(encoding="utf-8-sig")
        out, pos = [], 0
        for m in re.finditer(r"(?ms)^([\w.]+) = \{.*?^\}", text):
            name, body = m.group(1), m.group(0)
            if AGE_FROM not in body:
                continue
            if name in AGE_AI:
                continue
            if name not in AGE_BLOCKS:
                sys.exit(f"{rel}: {name} picks by age but is in neither AGE_BLOCKS nor AGE_AI")
            out.append(text[pos:m.start()])
            out.append(body.replace(AGE_FROM, f"auto_marry_age_ok_{AGE_BLOCKS[name]} = yes"))
            done += body.count(AGE_FROM)
            pos = m.end()
        out.append(text[pos:])
        path.write_text("".join(out), encoding="utf-8-sig")
    if done != AGE_COUNT:
        sys.exit(f"ages: replaced {done}, expected {AGE_COUNT}")
    return done


def copy() -> None:
    for part in PARTS:
        target = MOD / part
        for path in sorted(target.rglob("*")) if target.exists() else []:
            if path.is_file() and OWN not in path.relative_to(MOD).parents:
                path.unlink()
        for path in sorted((BASE / part).rglob("*")):
            rel = path.relative_to(BASE)
            if not path.is_file() or OWN in rel.parents:
                continue
            (MOD / rel).parent.mkdir(parents=True, exist_ok=True)
            raw = path.read_bytes()
            if path.suffix in TEXT and not raw.startswith(BOM):
                raw = BOM + raw  # the base ships seven without one
            (MOD / rel).write_bytes(raw)
    for path in sorted(OWN_TREE.rglob("*")):
        if path.is_file():
            rel = path.relative_to(OWN_TREE)
            (MOD / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, MOD / rel)


def patch() -> int:
    done = 0
    for rel, edits in PATCHES.items():
        path = MOD / rel
        raw = path.read_bytes()
        bom = raw.startswith(BOM)
        text = raw.decode("utf-8-sig")
        for anchor, new, times in edits:
            found = text.count(anchor)
            if found != times:
                sys.exit(f"{rel}: anchor found {found} times, expected {times}:\n{anchor}")
            text = text.replace(anchor, new)
            done += found
        path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")
    return done


def metadata() -> str:
    base = json.loads((BASE / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    version = f"{base['version']}+{REVISION}"
    meta = {
        "name": "Nobles Auto Marry - Continued (1.4, RU)",
        "id": "bag.auto_marry",
        "version": version,
        "game_id": "eu5",
        "supported_game_version": "1.4.*",
        "short_description": (
            "Nobles Auto Marry - Continued %s for game 1.4: Russian text, and AI "
            "countries no longer count their courts every month for player-only "
            "events. Load this INSTEAD of the original." % base["version"]),
        "tags": base.get("tags", []),
        "relationships": [],
        "game_custom_data": base.get("game_custom_data", {}),
    }
    out = MOD / ".metadata"
    out.mkdir(exist_ok=True)
    (out / "metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=4) + "\n", encoding="utf-8-sig")
    shutil.copyfile(BASE / ".metadata/thumbnail.png", out / "thumbnail.png")
    return version


def main() -> None:
    copy()
    edits = patch() + ages()
    version = metadata()
    print(f"auto_marry {version}: copied {BASE.name}, {edits} patched anchors")


if __name__ == "__main__":
    main()
