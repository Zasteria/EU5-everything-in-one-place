#!/usr/bin/env python3
"""Rebuilds `cm_dev_perf`: Construction Manager **dev** with the cm_perf edit
that still applies to it.

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

2. **A probe window** (`tools/probe/`, 2026-09-27): says whether the
   classification has closed. Open past the first seconds means the tree
   stands all session and the classification is incomplete, the suspected
   cause of perf's slow loads and wrong builds. Closed with its cross.

cm_perf's edit 5 (auto-expand verdict cached monthly) is left out on purpose:
the slot circles live only in the district and production windows, which she
opens on pause, so they cost nothing while the game runs (her call 2026-09-26).
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

MOD = refs.REPO / "mods/cm_dev_perf"
PROBE = MOD / "tools/probe"
SRC = refs.mod("romaimperator.construction_manager.dev", "construction_manager_dev")

# cm_perf's generator holds the first-pass widening; reuse it rather than keep
# two copies that drift apart.
_spec = importlib.util.spec_from_file_location(
    "cm_perf_port", refs.REPO / "mods/cm_perf/tools/port_from_cm.py"
)
perf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perf)

WINDOW = perf.WINDOW

_spec = importlib.util.spec_from_file_location(
    "beta_windows", Path(__file__).resolve().parent / "beta_windows.py")
beta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(beta)
BETA_SPECS = Path(__file__).resolve().parent / "beta"

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


LOG = "in_game/common/scripted_effects/cm_log_effects.txt"
ROADS = "in_game/common/scripted_effects/cm_ab_roads_effects.txt"
# wrapper: (number of values, logs a location, logs a building type)
_LOGGED = {
    "cm_dbg_log": (0, False, False),
    "cm_dbg_log_value": (1, False, False),
    "cm_dbg_log_at_loc": (0, True, False),
    "cm_dbg_log_loc": (1, True, False),
    "cm_dbg_log_loc_values": (3, True, False),
    "cm_dbg_log_bld": (2, True, True),
}


def _mirror_log(text: str) -> str:
    """Every line CM's Debug tab logs goes to `debug.log` as well (+perf8).

    CM's own log is CMF's action pane: 200 lines, on screen only, gone with the
    session. The same line in `debug.log` comes back with `mods.bat` → 4, so a
    run says what each cycle did without a screenshot. Still gated on the Debug
    tab's category toggles, so with them off nothing is written. The key is
    printed as the key (a `debug_log` does not resolve localization), the values
    through a scratch global, the location and building as named scopes
    (docs/research/engine.md, «What a `debug_log` string reaches»). The three
    script values that read the globals back ship with the probe, in tools/probe/.
    """
    for name, (values, loc, bt) in _LOGGED.items():
        head = f"\n{name} = {{\n"
        at = text.index(head)
        call = text.index("\t\tcmf_log", at)
        shown = []
        mirror = ["\t\t# cm_dev_perf: the same line into debug.log"]
        for n in range(1, values + 1):
            arg = "$value$" if n == 1 else f"$value{n}$"
            mirror.append(f"\t\tset_global_variable = {{ name = cm_perf_log_v{n} value = {arg} }}")
            shown.append(f"[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v{n}')|2]")
        words = ["CM", "$cat$", "$action$"]
        if values and name != "cm_dbg_log_value":
            words.append("$arg1$")
        if bt:
            words.append("$arg2$")
        mirror.append('\t\tdebug_log = "%s"' % " ".join(words + shown))
        if bt:
            mirror.append("\t\tscope:cmf_log_bt ?= { debug_log_scopes = no }")
        if loc:
            mirror.append("\t\tscope:cmf_log_loc ?= { debug_log_scopes = no }")
        text = text[:call] + "\n".join(mirror) + "\n" + text[call:]
    return text


_LOOKUP = re.compile(r"is_key_in_variable_map\s*=\s*\{\s*name\s*=\s*(\S+)\s+target\s*=\s*(\S+)\s*\}")


def _guard_maps(text: str) -> tuple[str, int]:
    """`AND = { has_variable_map = M <lookup> }` for every lookup not already
    guarded within the two lines above it, as CM itself writes the guard.

    The AND keeps the meaning under a `NOT`, which reads its children as NOR.
    """
    lines = text.split("\n")
    n = 0
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#"):
            continue
        out, pos = [], 0
        for match in _LOOKUP.finditer(line):
            above = "\n".join(lines[max(0, i - 2):i]) + line[:match.start()]
            if re.search(r"has_variable_map\s*=\s*%s(?!\S)" % re.escape(match.group(1)), above):
                continue
            out.append(line[pos:match.start()])
            out.append("AND = { has_variable_map = %s %s }" % (match.group(1), match.group(0)))
            pos = match.end()
            n += 1
        if out:
            lines[i] = "".join(out) + line[pos:]
    return "\n".join(lines), n


_DIRECT = re.compile(r"^([ \t]*)cmf_log(_value|_decimal_value)? = \{ action = (\S+)(?: value = (\S+))? \}[ \t]*$")
_SHOWN = "[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('cm_perf_log_v1')|2]"


def _mirror_direct(text: str) -> tuple[str, int]:
    """The lines CM writes with CMF's own `cmf_log*` rather than its Debug-tab
    wrappers go to `debug.log` too (+perf10): the probes' summaries (roads,
    governors, military, the gold balance) and the setup stamps. His run of
    10-04 pressed the roads probe and `debug.log` had nothing to show for it.
    """
    lines = text.split("\n")
    out, n = [], 0
    for line in lines:
        out.append(line)
        match = _DIRECT.match(line)
        if not match:
            continue
        indent, kind, action, value = match.groups()
        if value:
            out.append("%sset_global_variable = { name = cm_perf_log_v1 value = %s }" % (indent, value))
            out.append('%sdebug_log = "CM %s %s"' % (indent, action, _SHOWN))
        else:
            out.append('%sdebug_log = "CM %s"' % (indent, action))
        n += 1
    return "\n".join(out), n


def _probe_road_gates(text: str) -> str:
    """The roads probe also says which of the plan's three gates holds (+perf10):
    a plan that fails one of them returns without a word, so «no roads» and
    «not allowed to plan roads» read the same."""
    head = "cm_ab_rd_probe = {\n\tsave_scope_as = cm_country\n"
    gates = (("cm_ab_master_active = yes", "master_active"),
             ("exists = var:cm_ab_roads_enabled", "roads_enabled"),
             ("has_advance = road_building", "advance_road_building"),
             ("exists = var:cm_ab_roads_proximity", "proximity_on"),
             ("exists = var:cm_ab_roads_market_access", "market_access_on"),
             ("exists = var:cm_ab_roads_capital", "capital_on"),
             ("modifier:overlord_blocked_from_building_roads = no", "not_blocked_by_overlord"))
    lines = ["\t# cm_dev_perf: the plan's gates, into debug.log"]
    for trigger, name in gates:
        lines.append('\tif = { limit = { %s } debug_log = "CM roads gate %s yes" }' % (trigger, name))
        lines.append('\telse = { debug_log = "CM roads gate %s NO" }' % name)
    return text.replace(head, head + "\n".join(lines) + "\n", 1)


EDITS = (
    (WINDOW, "gate the building-type tree", _gate_the_tree),
    (WINDOW, "widen the first pass's instantiation window", perf._widen_first_pass),
    (WINDOW, "widen the upgrade refresh's instantiation window", _widen_refresh),
    (LOG, "mirror the Debug tab's log into debug.log", _mirror_log),
    (ROADS, "say the roads plan's gates in its probe", _probe_road_gates),
)


# **Raise with every change to what this mod ships** (his rule, 2026-09-27):
# `mods.bat` compares this number with the one installed in the game, and a
# refresh rewrites `.metadata` from here — a bump made by hand there is lost.
PERF_REVISION = 10


def metadata() -> str:
    """CM dev's own metadata, whole, with this mod's identity."""
    base = json.loads((SRC / ".metadata/metadata.json").read_text(encoding="utf-8-sig"))
    version = base.get("version", "unknown")
    base["name"] = "Construction Manager Dev (perf)"
    base["id"] = "bag.cm_dev_perf"
    base["version"] = f"{version}+perf{PERF_REVISION}"
    base["short_description"] = (
        f"Construction Manager Dev {version} with its hidden building-type tree "
        "gated on the passes that need it, and its vanilla windows rebuilt on the 2026-10-01 beta. "
        "Load this INSTEAD of Construction Manager Dev, never alongside it."
    )
    base["supported_game_version"] = "1.*"
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
    # 10-01: CM Dev's copies of vanilla windows are Glorp UI's 1.3 layout and
    # break on the beta; each with a spec in tools/beta/ is rebuilt as the
    # beta's window plus CM's hooks (beta_windows.py).
    rebuilt = beta.rebuild(refs.GAME_GUI, BETA_SPECS, MOD / "in_game/gui")
    # The beta's engine dropped `use_global_input_instance` (his log 10-02:
    # «not a valid widget/type/property»); commented out as the beta does.
    for path in (MOD / "in_game/gui").rglob("*.gui"):
        text = path.read_text(encoding="utf-8-sig")
        text, n = re.subn(r"^([ \t]*)(use_global_input_instance\s*=\s*yes)",
                          r"\1# \2  (removed from the engine, beta 10-01)", text, flags=re.M)
        if n:
            path.write_text("\ufeff" + text, encoding="utf-8")
    # The beta added a native trigger `is_host`, CMF's own trigger's name; CM's
    # host gates (the classification among them, his run 10-02: never ran) go
    # to cmf_is_host, which cmf_dev_beta defines with CMF's body.
    for path in (MOD / "in_game/common").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig")
        text, n = re.subn(r"^([ \t]*(?:limit = \{ )?)is_host(\s*=\s*(?:yes|no)\b)",
                          r"\1cmf_is_host\2", text, flags=re.M)
        if n:
            path.write_text("\ufeff" + text, encoding="utf-8")
    # A lookup into a map the scope does not have yet is an error, not false
    # (his log 10-04: 1 243 of them, cm_rgob_cov and cm_rgob_sum the bulk). CM
    # guards most of its lookups with `has_variable_map`; the rest get the
    # same guard (+perf9).
    for path in (MOD / "in_game/common").rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig")
        guarded, n = _guard_maps(text)
        mirrored, m = _mirror_direct(guarded)
        if n or m:
            path.write_text("\ufeff" + mirrored, encoding="utf-8")
    # The probe window (09-27) ships beside CM's files; its sources live in
    # tools/probe/ so this rebuild does not wipe them.
    for src in PROBE.rglob("*"):
        if src.is_file():
            dst = MOD / src.relative_to(PROBE)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("﻿" + metadata(), encoding="utf-8")
    thumb = SRC / ".metadata/thumbnail.png"
    if thumb.exists():
        shutil.copy2(thumb, MOD / ".metadata/thumbnail.png")
    print("cm_dev_perf: %d files copied from %s, %d edits applied, rebuilt on the beta: %s"
          % (copied, SRC.name, len(EDITS), ", ".join(rebuilt)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
