#!/usr/bin/env python3
"""Rebuilds `cmf_dev_beta`: Community Mod Framework for game 1.4, **a whole copy,
loaded instead of CMF Dev** — like `cm_dev_perf`.

Since +beta5 (10-03) the source is the authors' own **CMF 2.5.0**, their port to
1.4. CMF Dev 2.4.1 and CMF 2.4.1 were byte-for-byte the same mod, so 2.5.0 is
what CMF Dev becomes when its authors move it; their changes stand where they put
them. Measured on 2.5.0 against the game's files of 10-01: of 208 vanilla
interface types CMF keeps copies of, 200 are the game's own and the other 8 are
CMF's hooks (the lobby tooltips, its pause-menu buttons, its alert bar). So the
three fixes +beta1..4 carried (75 types from the beta, the beta's lobby,
`use_global_input_instance`) are the authors' now, and are gone from here.

Two changes remain, because 2.5.0 still has the faults:

**`cmf_is_host`.** The game added a native trigger `is_host` («the host of a
multiplayer session»), the name of CMF's own scripted trigger, and in a
single-player game the game's reads false (his probe 10-02). CMF's body is copied
under `cmf_is_host` and CMF's own calls use it; `is_host` stays for other mods.
`cm_dev_perf` and `cm_maps` call `cmf_is_host`.

**The bottom action bar keeps a slot for a hidden button** (+beta6, 10-05). Its
row of buttons is a datamodel `hbox` without `ignoreinvisible`, so a button whose
scripted GUI is not shown (CM's «Пересчитать» while the finder map is closed)
stands as an empty 34 px square that cannot be clicked — his screenshot 10-05,
bottom-left. The top bar is tabs and does not have it.

    python3 mods/cmf_dev_beta/tools/port_from_cmf_dev.py
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
SRC = refs.mod("community_mod_framework")

_spec = importlib.util.spec_from_file_location(
    "beta_windows", refs.REPO / "mods/cm_dev_perf/tools/beta_windows.py")
beta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(beta)

REVISION = 6


def metadata() -> str:
    base = json.loads((SRC / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    version = base.get("version", "unknown")
    base["name"] = "Community Mod Framework Dev (1.4)"
    base["id"] = "bag.cmf_dev_beta"
    base["version"] = f"{version}+beta{REVISION}"
    base["supported_game_version"] = "1.4.*"
    base["short_description"] = (
        f"Community Mod Framework {version} (the authors' 1.4 port) with two fixes: CMF's "
        "own is_host is called as cmf_is_host, since the game's native is_host is false "
        "in single player; the bottom action bar no longer keeps empty slots for hidden "
        "buttons. Load this INSTEAD of CMF and CMF Dev.")
    base["relationships"] = []
    return json.dumps(base, indent=4, ensure_ascii=False) + "\n"


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


ACTION_BAR = "in_game/gui/cmf/cmf_action_bar.gui"
BAR_ROW = ("        hbox = {\n"
           "            spacing = 4\n"
           "            datamodel = \"[GetPlayer.MakeScope.GetList('cmf_action_bar_active_elements')]\"\n")


def bar_ignores_hidden() -> None:
    """The bottom bar's button row skips hidden buttons instead of keeping their slot."""
    path = MOD / ACTION_BAR
    text = path.read_text(encoding="utf-8-sig")
    if text.count(BAR_ROW) != 1:
        raise SystemExit(f"{ACTION_BAR}: the bottom bar's button row moved")
    text = text.replace(BAR_ROW, BAR_ROW.replace(
        "spacing = 4\n", "spacing = 4\n            ignoreinvisible = yes\n", 1))
    path.write_text("\ufeff" + text, encoding="utf-8")


def main() -> int:
    for name in ("in_game", "main_menu", "loading_screen", ".metadata"):
        if (MOD / name).exists():
            shutil.rmtree(MOD / name)
    for name in ("in_game", "main_menu", "loading_screen"):
        if (SRC / name).exists():
            shutil.copytree(SRC / name, MOD / name)
    host_calls = own_host_trigger()
    bar_ignores_hidden()
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("﻿" + metadata(), encoding="utf-8")
    thumb = SRC / ".metadata/thumbnail.png"
    if thumb.exists():
        shutil.copy2(thumb, MOD / ".metadata/thumbnail.png")
    print("cmf_dev_beta: whole copy of %s, %d is_host calls on cmf_is_host"
          % (SRC.name, host_calls))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
