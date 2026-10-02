#!/usr/bin/env python3
"""Rebuilds `cmf_dev_beta`: Community Mod Framework Dev, fitted to the
2026-10-01 beta. **A whole copy, loaded instead of CMF Dev** — like `qol_beta`
and `cm_dev_perf`.

It was an overlay of 16 files until his run of 10-02: the playset held the
overlay and not CMF Dev, so none of CMF's effects, macros or keys existed, and
CM's icons, CMF's pause button and its action bar all went missing. A copy
that is the whole framework cannot be loaded without it.

The changes, and nothing else:

1. **75 vanilla types from the beta.** CMF keeps copies of vanilla `types` in
   its own files (`gui/vanilla/cmf_*`, `multiplayer_lobby.gui`,
   `cmm/cmm_ingame_menu.gui`); a later definition wins, so its 1.3 copies
   pinned 75 types of the beta's windows to 1.3. 69 are verbatim copies; five
   in the lobby only swap a tooltip key, and those swaps are dropped; the
   pause menu carries CMF's own button, put back after the beta's buttons.
2. **The lobby is the beta's file** plus CMF's row of mod banners; the types
   CMF moved out of it into `cmf_multiplayer_lobby_vanilla_types.gui` are
   taken out of that file, or both register them (his log 10-02: 20 errors).
3. **`use_global_input_instance` commented out**, as the beta itself does:
   the engine dropped the property («input actions reimplementation»).
4. **`cmf_is_host`.** The beta added a native trigger `is_host` («the host of
   a multiplayer session»), the name of CMF's own scripted trigger; which one a
   call reaches is not documented. CMF's body is copied under `cmf_is_host` and
   CMF's own calls use it; `is_host` stays for other mods. His run 10-02: CM's
   classification, gated on `is_host`, never ran.

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

REVISION = 4
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
    # The two CMF buttons and nothing after them: CMF's 1.3 template went on with
    # vanilla's message, report and AI buttons, and taking the rest of the body
    # put those in twice (his run 10-02: two «Настройки уведомлений»).
    start = body.index("\t# CMF: CMM open menu button")
    end = start
    for _ in range(2):
        at = body.index("button_wax = {", end)
        _, end = beta._block(body, at + len("button_wax = {"), 0)
    return body[start:end].rstrip()


def metadata() -> str:
    base = json.loads((SRC / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    version = base.get("version", "unknown")
    base["name"] = "Community Mod Framework Dev (beta)"
    base["id"] = "bag.cmf_dev_beta"
    base["version"] = f"{version}+beta{REVISION}"
    base["supported_game_version"] = "1.*"
    base["short_description"] = (
        f"Community Mod Framework Dev {version} fitted to the 2026-10-01 beta: the 75 "
        "vanilla interface types it keeps 1.3 copies of are taken from the beta. "
        "Load this INSTEAD of CMF Dev; remove once CMF Dev is updated.")
    base["relationships"] = []
    return json.dumps(base, indent=4, ensure_ascii=False) + "\n"


def without_types(text: str, names: set[str]) -> str:
    """`text` with every type or template named in `names` (any case) cut out."""
    for name in re.findall(r"^[ \t]*(?:type\s+(\w+)\s*=|template\s+(\w+))", text, re.M):
        name = name[0] or name[1]
        if name.lower() in names:
            span = beta.type_block(text, name)
            if not span:
                raise SystemExit(f"type {name}: not a single block")
            text = text[:span[0]] + text[span[1]:].lstrip("\n")
    return text


HOST_TRIGGERS = "in_game/common/scripted_triggers/cmf_core_triggers.txt"
HOST_CALL = re.compile(r"^([ \t]*)is_host(\s*=\s*(?:yes|no)\b)", re.M)


def own_host_trigger() -> int:
    """CMF's `is_host` copied as `cmf_is_host`, and CMF's calls moved onto it."""
    path = MOD / HOST_TRIGGERS
    text = path.read_text(encoding="utf-8-sig")
    span = re.search(r"^is_host = \{", text, re.M)
    if not span:
        raise SystemExit(f"{HOST_TRIGGERS}: CMF no longer defines is_host")
    _, end = beta._block(text, span.end(), 0)
    body = text[span.start():end]
    calls = 0
    for each in (MOD / "in_game/common").rglob("*.txt"):
        old = each.read_text(encoding="utf-8-sig")
        new, n = HOST_CALL.subn(r"\1cmf_is_host\2", old)
        if n:
            each.write_text("\ufeff" + new, encoding="utf-8")
            calls += n
    text = path.read_text(encoding="utf-8-sig")
    text += ("\n\n# cmf_dev_beta: CMF's is_host under a name of its own -- the beta added a\n"
             "# native trigger is_host, and CMF's calls must reach this body.\n"
             + body.replace("is_host = {", "cmf_is_host = {", 1) + "\n")
    path.write_text("\ufeff" + text, encoding="utf-8")
    return calls


NO_GLOBAL_INPUT = re.compile(r"^([ \t]*)(use_global_input_instance\s*=\s*yes)", re.M)


def main() -> int:
    for name in ("in_game", "main_menu", "loading_screen", ".metadata"):
        if (MOD / name).exists():
            shutil.rmtree(MOD / name)
    for name in ("in_game", "main_menu", "loading_screen"):
        if (SRC / name).exists():
            shutil.copytree(SRC / name, MOD / name)
    plan = json.loads(TYPES.read_text(encoding="utf-8"))
    lobby_types = {(a or b).lower() for a, b in re.findall(
        r"^[ \t]*(?:type\s+(\w+)\s*=|template\s+(\w+))",
        (refs.GAME / LOBBY).read_text(encoding="utf-8-sig"), re.M)}
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
            if path.endswith("cmf_multiplayer_lobby_vanilla_types.gui"):
                text = without_types(text, lobby_types)
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
    silenced = 0
    for path in MOD.rglob("*.gui"):
        text = path.read_text(encoding="utf-8-sig")
        text, n = NO_GLOBAL_INPUT.subn(
            r"\1# use_global_input_instance removed from engine (beta 10-01)\n\1# \2", text)
        if n:
            path.write_text("\ufeff" + text, encoding="utf-8")
            silenced += n
    host_calls = own_host_trigger()
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("﻿" + metadata(), encoding="utf-8")
    thumb = SRC / ".metadata/thumbnail.png"
    if thumb.exists():
        shutil.copy2(thumb, MOD / ".metadata/thumbnail.png")
    print("cmf_dev_beta: whole copy of %s; %d types in %d files taken from the beta,"
          " %d use_global_input_instance silenced, %d is_host calls on cmf_is_host"
          % (SRC.name, count, len(plan), silenced, host_calls))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
