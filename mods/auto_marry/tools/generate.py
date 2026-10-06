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
* the Russian file, which in the base is the English one under a Russian
  header.  It is written by hand in `main_menu/localization/russian/` and this
  tool never touches it.

Everything else under `in_game/` and `main_menu/` is derived: do not edit it.

Usage:  python3 mods/auto_marry/tools/generate.py
"""

from __future__ import annotations

import json
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

REVISION = "beta3"
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

# file -> [(anchor, replacement, times the anchor must occur)]
PATCHES = {
    "in_game/common/on_action/automarry_on_actions.txt": [
        (f"{name} = {{\n\ttrigger = {{\n",
         f"{name} = {{\n\ttrigger = {{\n\t\tis_ai = no\n", 1)
        for name in PLAYER_ON_ACTIONS
    ],
}


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
    edits = patch()
    version = metadata()
    print(f"auto_marry {version}: copied {BASE.name}, {edits} on_action guards")


if __name__ == "__main__":
    main()
