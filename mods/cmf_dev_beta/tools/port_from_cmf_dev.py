#!/usr/bin/env python3
"""Rebuilds `cmf_dev_beta`: the files of Community Mod Framework Dev that carry
vanilla interface types the 2026-10-01 beta changed, with those types taken
from the beta.

CMF keeps copies of vanilla `types` in its own files (`gui/vanilla/cmf_*`,
`multiplayer_lobby.gui`, `cmm/cmm_ingame_menu.gui`); a later definition wins,
so its 1.3 copies pinned 75 types of the beta's windows to 1.3 — the
investigation of 2026-10-01 counted them. 69 are verbatim 1.3 copies; five in
the lobby only swap a tooltip key («avoids a tooltip error»), and those swaps are
dropped; one, the pause menu, carries CMF's own button to its menu, which is
put back after the beta's buttons.

This mod is **an overlay**: it holds only those 16 files, at CMF's own paths,
and loads after CMF Dev (its dependency), so its files replace CMF's. Remove it
once CMF Dev is updated for the beta.

    python3 mods/cmf_dev_beta/tools/port_from_cmf_dev.py

`beta_types.json` is the measured list: a CMF type whose body differs from the
beta's only because CMF hooked it is **not** on it, and must not be, or the hook
is lost.
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

MOD = refs.REPO / "mods/cmf_dev_beta"
SRC = refs.mod("community_mod_framework.dev")
TYPES = Path(__file__).resolve().parent / "beta_types.json"

_spec = importlib.util.spec_from_file_location(
    "beta_windows", refs.REPO / "mods/cm_dev_perf/tools/beta_windows.py")
beta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(beta)

REVISION = 1
PAUSE_MENU = "in_game/gui/cmm/cmm_ingame_menu.gui"
LOBBY = "in_game/gui/multiplayer_lobby.gui"
# CMF replaces the lobby whole, and the beta rewrote it (1 653 lines, five new
# types its window needs). CMF's own part is one row of mod banners; the rest
# of its copy is vanilla 1.3 and three tooltip swaps. So the lobby is the
# beta's file with that row put back after the DLC banners.
BANNERS = """
				# CMF: Mod Banners
				expand = {}
				hbox = {
					spacing = 5
					datamodel = "[GetGlobalList('cmf_lobby_banner_mod_ids')]"
					item = {
						cmf_lobby_banner = { }
					}
				}"""


def cmf_buttons(cmf_text: str) -> str:
    """CMF's two pause-menu buttons, as CMF wrote them."""
    span = beta.type_block(cmf_text, "frontend_menu_middle_template")
    body = cmf_text[span[0]:span[1]]
    start = body.index("\t# CMF: CMM open menu button")
    end = body.rstrip().rindex("}")
    return body[start:end].rstrip()


def metadata() -> str:
    base = json.loads((SRC / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    version = base.get("version", "unknown")
    meta = {
        "name": "Community Mod Framework Dev — beta types",
        "id": "bag.cmf_dev_beta",
        "version": f"{version}+beta{REVISION}",
        "game_id": "eu5",
        "supported_game_version": "1.*",
        "short_description": (
            f"For Community Mod Framework Dev {version} on the 2026-10-01 beta: the "
            "75 vanilla interface types CMF keeps 1.3 copies of, taken from the beta. "
            "Load after CMF Dev; remove once CMF Dev is updated."),
        "tags": ["Fixes", "User Interface"],
        "relationships": [{
            "rel_type": "dependency",
            "id": base["id"],
            "display_name": base.get("name", "Community Mod Framework Dev"),
            "resource_type": "mod",
            "version": "2.*",
        }],
        "game_custom_data": {},
    }
    return json.dumps(meta, indent=4, ensure_ascii=False) + "\n"


def main() -> int:
    for name in ("in_game", "main_menu", ".metadata"):
        if (MOD / name).exists():
            shutil.rmtree(MOD / name)
    plan = json.loads(TYPES.read_text(encoding="utf-8"))
    count = 0
    for path, names in plan.items():
        text = (SRC / path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        buttons = cmf_buttons(text) if path == PAUSE_MENU else None
        if path == LOBBY:
            if "cmf_lobby_banner_mod_ids" not in text:
                raise SystemExit("CMF's lobby no longer carries the banner row — re-read it")
            text = (refs.GAME / path).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
            text = beta.apply(text, [{
                "op": "insert_after_block", "up": 1,
                "anchor": 'dlc_banner = { visible = "[And(Not(GameDLC.IsActivated), Not(GameDLC.IsOwned))]" }',
                "text": BANNERS}], path)
        else:
            edits = [{"op": "beta_type", "name": name} for name in names]
            text = beta.apply(text, edits, path, refs.GAME_GUI)
        if buttons:
            text = beta.apply(text, [{
                "op": "insert_after_block", "anchor": 'text = "AI_SETTINGS"', "up": 0,
                "text": "\n" + buttons}], path)
        if re.search(r"\bHasActiveMod\(", text):
            raise SystemExit(f"{path}: still calls HasActiveMod, which the beta removed")
        target = MOD / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("﻿" + text, encoding="utf-8")
        count += len(names)
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("﻿" + metadata(), encoding="utf-8")
    thumb = SRC / ".metadata/thumbnail.png"
    if thumb.exists():
        shutil.copy2(thumb, MOD / ".metadata/thumbnail.png")
    print("cmf_dev_beta: %d types in %d files of %s taken from the beta"
          % (count, len(plan), SRC.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
