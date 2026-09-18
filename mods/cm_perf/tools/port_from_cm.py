#!/usr/bin/env python3
"""Rebuilds `cm_perf`: Construction Manager with its always-live building-type
tree put behind a gate.

**A copy of CM, not a rewrite of it.** Every file comes from
`reference/mods/<construction manager>/` byte for byte; the only differences are
the edits listed in `EDITS`, and each one is there for a reason written next to
it. Names inside the mod are left alone — `cm_*` script names, the CMF `mod_id =
cm`, every file path — because this is meant to be loaded **instead of** CM, not
alongside it, and identical names keep saves and CMF settings working.

    python3 mods/cm_perf/tools/port_from_cm.py

Run from `tools/refresh.py` with the other generators. Each edit fails loudly if
its anchor has moved, because a silently skipped edit is a mod that looks
patched and is not.

## What the edits are for

CM's hidden window holds a datamodel over **every building type the game
declares** (1 953 in this build) with nested datamodels for construction demand
and production methods under it, and that widget carries **no `visible` of its
own**. Its window's root is deliberately always-true
(`EqualTo_CFixedPoint('0','0')`, and CM's own comment says why: it keeps
descendant gates re-evaluating), so the tree stands for the whole session and
its gates re-evaluate for the whole session. The classification it exists for
runs **once per lobby**: `cm_should_building_type_section_show` goes false the
moment every type is processed, and the driver widget right above the tree is
already gated on exactly that.

So the tree is given the driver's own gate. When a pass is armed, both come up
together and the tree instantiates; when the pass completes, both go away.
Nothing else reads it — in this build of CM the classification driver is its
only consumer.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/cm_perf"
SRC = refs.mod("romaimperator.construction_manager", "construction_manager")

WINDOW = "in_game/gui/cm_hidden_window.gui"

# The gate the classification driver already carries, copied verbatim off it.
# Same expression on both widgets is the point: they live and die together, and
# it is an expression this very file is already known to evaluate correctly.
GATE = (
    "\"[And(GetPlayer.Exists, GetScriptedGui('cm_should_building_type_section_show')"
    ".IsShown(GuiScope.SetRoot(GetPlayer.MakeScope)"
    ".AddScope('cm_country', GetPlayer.MakeScope).End))]\""
)


def _gate_the_tree(text: str) -> str:
    """Give the building-type tree the gate its driver already has.

    This is the whole point of the mod. Without a `visible` of its own the tree
    stands under an always-true root for the session; with one it exists only
    while a classification pass is armed.
    """
    anchor = (
        "\t\twidget = {\n"
        "\t\t\tdatamodel = \"[GetGlobalList('cm_building_types_to_process')]\"\n"
    )
    if text.count(anchor) != 1:
        raise SystemExit(
            f"{WINDOW}: the building-type tree is not where this edit expects it "
            "(one `widget` whose first line is the cm_building_types_to_process "
            "datamodel). CM has been rebuilt here -- re-read the file before "
            "trusting this generator."
        )
    replacement = (
        "\t\twidget = {\n"
        "\t\t\t# cm_perf: the driver's own gate, so the tree stands only while a pass is\n"
        "\t\t\t# armed instead of for the whole session. CM leaves this widget ungated and\n"
        "\t\t\t# the window's root always true, which is what keeps every type's gates\n"
        "\t\t\t# re-evaluating long after the one classification they are for has finished.\n"
        f"\t\t\tvisible = {GATE}\n"
        "\t\t\tdatamodel = \"[GetGlobalList('cm_building_types_to_process')]\"\n"
    )
    return text.replace(anchor, replacement)


def _widen_first_pass(text: str) -> str:
    """Give the gated tree longer to build its rows before the first pass fires.

    Datamodel rows do not exist in the frame the gate opens -- the rule that
    cost a run in `docs/pitfalls/windows.md`. CM's `_show` waits 0.5s for
    exactly this, sized for a tree that was already standing; a tree that is
    being built from nothing in that window gets twice as long here. The cost
    is half a second once per lobby, and the failure it guards against is the
    silent kind: passes firing over rows that are not there yet leave the
    classification maps empty and every CM filter reading them wrong.
    """
    anchor = (
        "\t\t\tstate = {\n"
        "\t\t\t\tname = _show\n"
        "\t\t\t\tduration = 0.5\n"
        "\t\t\t\tnext = cm_building_type_pass_produced\n"
    )
    if anchor not in text:
        raise SystemExit(
            f"{WINDOW}: the classification driver's _show state has moved; "
            "the instantiation window cannot be widened blind."
        )
    return text.replace(
        anchor,
        "\t\t\tstate = {\n"
        "\t\t\t\tname = _show\n"
        "\t\t\t\t# cm_perf: 1.0 rather than CM's 0.5 -- the tree above is now built when\n"
        "\t\t\t\t# this gate opens, not already standing, and its rows appear later than\n"
        "\t\t\t\t# the frame that opened it.\n"
        "\t\t\t\tduration = 1\n"
        "\t\t\t\tnext = cm_building_type_pass_produced\n",
    )


EDITS = (
    (WINDOW, "gate the building-type tree", _gate_the_tree),
    (WINDOW, "widen the first pass's instantiation window", _widen_first_pass),
)


def metadata() -> str:
    """CM's own metadata with this mod's identity, and its version recorded.

    The CMF dependency is kept: nothing here removes CM's need for it.
    """
    base = json.loads((SRC / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    base_version = base.get("version", "unknown")
    base["name"] = "Construction Manager (perf)"
    base["id"] = "bag.cm_perf"
    base["version"] = f"{base_version}+perf1"
    base["short_description"] = (
        f"Construction Manager {base_version}, unchanged except that its hidden "
        "building-type classification tree is gated on the pass that needs it "
        "instead of standing for the whole session. Load this INSTEAD of "
        "Construction Manager, never alongside it."
    )
    return json.dumps(base, indent=4, ensure_ascii=False) + "\n"


def main() -> int:
    for name in ("in_game", "main_menu", ".metadata"):
        target = MOD / name
        if target.exists():
            shutil.rmtree(target)
    copied = 0
    for name in ("in_game", "main_menu"):
        source = SRC / name
        if not source.exists():
            continue
        shutil.copytree(source, MOD / name)
        copied += sum(1 for p in (MOD / name).rglob("*") if p.is_file())

    for path, label, edit in EDITS:
        target = MOD / path
        text = target.read_text(encoding="utf-8-sig")
        patched = edit(text)
        if patched == text:
            raise SystemExit(f"{path}: {label} changed nothing")
        target.write_text("﻿" + patched.lstrip("﻿"), encoding="utf-8")

    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text(metadata(), encoding="utf-8")
    thumbnail = SRC / ".metadata/thumbnail.png"
    if thumbnail.exists():
        shutil.copy2(thumbnail, MOD / ".metadata/thumbnail.png")

    print(
        "cm_perf: %d files copied from %s, %d edits applied"
        % (copied, SRC.name, len(EDITS))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
