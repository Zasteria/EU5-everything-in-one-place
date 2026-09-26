#!/usr/bin/env python3
"""Rebuilds `cm_dev_perf`: Construction Manager **dev** with the cm_perf edits
that still apply to it.

A byte-for-byte copy of `reference/mods/<CM dev>/` plus the edits in `EDITS`.
Names are left alone (`cm_*`, CMF `mod_id = cm`, file paths): load it
**instead of** CM dev, never alongside it.

    python3 mods/cm_dev_perf/tools/port_from_cm_dev.py

What dev already carries and cm_perf had to add: the one-sweep-per-cycle drain
and the stall rescan (cm_perf edit 3 was taken off dev). What dev still lacks:

1. **The building-type tree has no gate of its own.** Dev's hidden window keeps
   a datamodel over every building type, with demand and production-method
   datamodels under each, standing under an always-true root for the whole
   session. Every one of those widgets is walked by every
   `PdxGuiTriggerAllAnimations` the queue drain fires, and their `visible`
   gates re-evaluate each frame. cm_perf gated the same tree; its run on
   2026-09-18 confirmed the classification still works. Dev differs in one
   way: the mid-session upgrade-map refresh (`cm_upgrade_type_refresh_state`)
   also lives in this tree, so the gate is either pass, not only the
   classification.
2. **The auto-expand verdict is recomputed per frame, twice per slot icon.**
   Same edit as cm_perf's 5, reused from its generator: the monthly pass
   stamps `cm_ae_ok` on the building, the GUI reads the variable.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/cm_dev_perf"
SRC = refs.mod("romaimperator.construction_manager.dev", "construction_manager_dev")

# cm_perf's generator holds the verdict edit and the first-pass widening; reuse
# them rather than keep two copies that drift apart.
_spec = importlib.util.spec_from_file_location(
    "cm_perf_port", refs.REPO / "mods/cm_perf/tools/port_from_cm.py"
)
perf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perf)

WINDOW = perf.WINDOW

_CLASSIFY = (
    "GetScriptedGui('cm_should_building_type_section_show')"
    ".IsShown(GuiScope.SetRoot(GetPlayer.MakeScope)"
    ".AddScope('cm_country', GetPlayer.MakeScope).End)"
)
_REFRESH = (
    "GetScriptedGui('cm_should_refresh_upgrade_types')"
    ".IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End)"
)
# Both drivers' own gates, copied off them: the tree stands while either pass runs.
GATE = f"\"[And(GetPlayer.Exists, Or({_CLASSIFY}, {_REFRESH}))]\""


def _gate_the_tree(text: str) -> str:
    """Give the building-type tree the gates of the two passes that use it."""
    anchor = (
        "\t\twidget = {\n"
        "\t\t\tdatamodel = \"[GetGlobalList('cm_building_types_to_process')]\"\n"
    )
    for part in (_CLASSIFY, _REFRESH):
        if part not in text:
            raise SystemExit(f"{WINDOW}: a driver gate has changed: {part}")
    if text.count(anchor) != 1:
        raise SystemExit(
            f"{WINDOW}: the building-type tree is not where this edit expects it; "
            "CM dev was rebuilt -- re-read the file before trusting this generator."
        )
    return text.replace(
        anchor,
        "\t\twidget = {\n"
        "\t\t\t# cm_dev_perf: stands only while the classification or the upgrade-map\n"
        "\t\t\t# refresh is armed. CM leaves it ungated under an always-true root, so every\n"
        "\t\t\t# type's widgets live, re-evaluate and get walked by each tree-wide trigger\n"
        "\t\t\t# for the whole session.\n"
        f"\t\t\tvisible = {GATE}\n"
        "\t\t\tdatamodel = \"[GetGlobalList('cm_building_types_to_process')]\"\n",
    )


def _widen_refresh(text: str) -> str:
    """Same reason as the first pass: the tree is now built when the gate opens."""
    anchor = (
        "\t\t\tstate = {\n"
        "\t\t\t\tname = _show\n"
        "\t\t\t\tduration = 0.5\n"
        "\t\t\t\tnext = cm_upgrade_type_refresh_done\n"
    )
    if text.count(anchor) != 1:
        raise SystemExit(f"{WINDOW}: the upgrade refresh driver's _show has moved")
    return text.replace(
        anchor,
        "\t\t\tstate = {\n"
        "\t\t\t\tname = _show\n"
        "\t\t\t\t# cm_dev_perf: 1.0 rather than 0.5 -- the gated tree is built when this opens.\n"
        "\t\t\t\tduration = 1\n"
        "\t\t\t\tnext = cm_upgrade_type_refresh_done\n",
    )


EDITS = (
    (WINDOW, "gate the building-type tree", _gate_the_tree),
    (WINDOW, "widen the first pass's instantiation window", perf._widen_first_pass),
    (WINDOW, "widen the upgrade refresh's instantiation window", _widen_refresh),
    (perf.FEATURE, "cache the auto-expand verdict on the building", perf._cache_the_verdict),
    (perf.AE_BUTTON, "read the cached verdict", perf._read_the_verdict(perf.AE_BUTTON)),
    (perf.AE_ICONS, "read the cached verdict", perf._read_the_verdict(perf.AE_ICONS)),
)


def metadata() -> str:
    """CM dev's own metadata, whole, with this mod's identity."""
    base = json.loads((SRC / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    version = base.get("version", "unknown")
    base["name"] = "Construction Manager Dev (perf)"
    base["id"] = "bag.cm_dev_perf"
    base["version"] = f"{version}+perf1"
    base["short_description"] = (
        f"Construction Manager Dev {version} with its hidden building-type tree "
        "gated on the passes that need it and the auto-expand verdict cached "
        "monthly. Load this INSTEAD of Construction Manager Dev, never alongside it."
    )
    return json.dumps(base, indent=4, ensure_ascii=False) + "\n"


def main() -> int:
    for name in ("in_game", "main_menu", ".metadata"):
        if (MOD / name).exists():
            shutil.rmtree(MOD / name)
    copied = 0
    for name in ("in_game", "main_menu"):
        if (SRC / name).exists():
            shutil.copytree(SRC / name, MOD / name)
            copied += sum(1 for p in (MOD / name).rglob("*") if p.is_file())
    for path, label, edit in EDITS:
        target = MOD / path
        text = target.read_text(encoding="utf-8-sig")
        patched = edit(text)
        if patched == text:
            raise SystemExit(f"{path}: {label} changed nothing")
        target.write_text("﻿" + patched.lstrip("﻿"), encoding="utf-8")
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("﻿" + metadata(), encoding="utf-8")
    thumb = SRC / ".metadata/thumbnail.png"
    if thumb.exists():
        shutil.copy2(thumb, MOD / ".metadata/thumbnail.png")
    print("cm_dev_perf: %d files copied from %s, %d edits applied" % (copied, SRC.name, len(EDITS)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
