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



# ---------------------------------------------------------- the drain loop

QUEUE = "in_game/gui/cm_construct_queue_window.gui"
SGUI = "in_game/common/scripted_guis/cm_hidden_window_scripted_gui.txt"
DISPATCH = "in_game/common/on_action/cm_on_action.txt"

# Раз во сколько месяцев идёт весь цикл авторасширения. Должно делить 12.
# 1 — правка не применяется вовсе, цикл идёт каждый месяц, как у самого CM.
# Стоит 1 по его слову 2026-09-19: месячный пересчёт ему не мешает, и трогать
# его не надо.
PULSE_MONTHS = 1

# CM 2.2.12's drain driver, verbatim. Rebuilt rather than patched line by line,
# so a changed source stops the generator instead of being half-edited.
_LOOP_OLD = (
	"\t\t# Per-cycle driver: tears down when cm_should_construct clears and rebuilds next cycle, re-running _show.\n"
	"\t\twidget = {\n"
	"\t\t\tsize = { 0 0 }\n"
	"\t\t\tvisible = \"[And(GetPlayer.Exists, GetScriptedGui('cm_should_construct')"
	".IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End))]\"\n"
	"\t\t\t# Step lengths only pace the loop; completion is decided by cm_q_sync_check.\n"
	"\t\t\tstate = {\n"
	"\t\t\t\tname = _show\n"
	"\t\t\t\tduration = 0.1\n"
	"\t\t\t\tnext = cm_q_round_fire\n"
	"\t\t\t}\n"
	"\t\t\t# Rounds are safe to repeat: executors skip entries already processed this cycle.\n"
	"\t\t\tstate = {\n"
	"\t\t\t\tname = cm_q_round_fire\n"
	"\t\t\t\tduration = 0.15\n"
)

SWEEPS = (
	"cm_q_construct", "cm_q_construct_upgrade", "cm_q_construct_ungated",
	"cm_q_construct_urbanize", "cm_q_construct_food", "cm_q_construct_food_rgo",
	"cm_q_construct_rgo",
)


def _fire(name: str, indent: str) -> str:
	return f"{indent}on_finish = \"[PdxGuiTriggerAllAnimations('{name}')]\"\n"


def _split_the_drain_loop(text: str) -> str:
	"""One sweep per cycle instead of one per round.

	CM's loop re-fired every construct sweep every 0.15s round for as long as the
	cycle took. `PdxGuiTriggerAllAnimations` matches by state name across the
	whole tree, so each sweep costs one scripted_gui_command per staged item, and
	the round count multiplied that. On a large nation it is the monthly slow
	stretch: the cycle drains for the first stretch of the month at a few rounds a
	second, and the rest of the month runs at full speed once it is done.

	**This is the author's own fix, taken off CM dev 2.3.0**, whose comment on the
	same widget names the fault: "repeating it every poll round multiplied that by
	the round count and flooded the engine's message queue on very large nations."
	The sweeps move to a one-shot driver gated on `cm_q_scan_armed`; the loop keeps
	only `cm_q_probe`, which verifies approved entries, and the sync check.

	What repeating was for -- an item widget that had not instantiated when the
	sweep fired -- is covered by the rescan in `_rescan_when_stalled`, dev's answer
	to the same question.
	"""
	if text.count(_LOOP_OLD) != 1:
		raise SystemExit(
			f"{QUEUE}: the per-cycle drain driver is not the one this edit was "
			"written against. Re-read the file and the dev build's version of it "
			"before touching the loop again."
		)
	for name in SWEEPS + ("cm_q_probe",):
		if _fire(name, "\t\t\t\t") not in text:
			raise SystemExit(f"{QUEUE}: sweep {name} is gone; the split would drop it")
	start = text.index(_LOOP_OLD)
	# "\t\t}" also matches the last two tabs of a three-tab state close, which is how
	# the first build of this edit left an orphan brace behind. Anchor on the newline.
	loop_back = text.index("next = cm_q_round_fire\n", start + len(_LOOP_OLD))
	end = text.index("\n\t\t}\n", loop_back) + 1
	new = (
		"\t\t# cm_perf: one-shot scan driver. CM fired every sweep below on every round of\n"
		"\t\t# the poll loop; each sweep costs one scripted_gui_command per staged item, so\n"
		"\t\t# the round count multiplied the whole queue. Taken off dev 2.3.0, which splits\n"
		"\t\t# it the same way. Pinned hidden so the gate going true always gives a first show.\n"
		"\t\twidget = {\n"
		"\t\t\tsize = { 0 0 }\n"
		"\t\t\tvisible_at_creation = no\n"
		"\t\t\tvisible = \"[And(GetPlayer.Exists, GetScriptedGui('cm_q_scan_gate')"
		".IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End))]\"\n"
		"\t\t\t# 0.3 gives the staged datamodels time to instantiate before their one sweep.\n"
		"\t\t\tstate = {\n"
		"\t\t\t\tname = _show\n"
		"\t\t\t\tduration = 0.3\n"
		+ "".join(_fire(n, "\t\t\t\t") for n in SWEEPS)
		+ "\t\t\t\tnext = cm_q_scan_done\n"
		"\t\t\t}\n"
		"\t\t\tstate = {\n"
		"\t\t\t\tname = cm_q_scan_done\n"
		"\t\t\t\tduration = 0.15\n"
		"\t\t\t\ton_finish = \"[GetScriptedGui('cm_q_scan_disarm')"
		".Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]\"\n"
		"\t\t\t}\n"
		"\t\t}\n"
		"\t\t# Per-cycle poll driver: tears down when cm_should_construct clears and rebuilds\n"
		"\t\t# next cycle, re-running _show. cm_perf: the construct sweeps have moved to the\n"
		"\t\t# one-shot driver above; what is left is the probe, which verifies approved\n"
		"\t\t# entries and costs nothing until the approval pass fills them.\n"
		"\t\twidget = {\n"
		"\t\t\tsize = { 0 0 }\n"
		"\t\t\tvisible = \"[And(GetPlayer.Exists, GetScriptedGui('cm_should_construct')"
		".IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End))]\"\n"
		"\t\t\t# Step lengths only pace the loop; completion is decided by cm_q_sync_check.\n"
		"\t\t\tstate = {\n"
		"\t\t\t\tname = _show\n"
		"\t\t\t\tduration = 0.1\n"
		"\t\t\t\tnext = cm_q_round_probe\n"
		"\t\t\t}\n"
		"\t\t\tstate = {\n"
		"\t\t\t\tname = cm_q_round_probe\n"
		"\t\t\t\tduration = 0.15\n"
		+ _fire("cm_q_probe", "\t\t\t\t")
		+ "\t\t\t\tnext = cm_q_round_check\n"
		"\t\t\t}\n"
		"\t\t\tstate = {\n"
		"\t\t\t\tname = cm_q_round_check\n"
		"\t\t\t\tduration = 0.15\n"
		"\t\t\t\ton_finish = \"[GetScriptedGui('cm_q_sync_check')"
		".Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]\"\n"
		"\t\t\t\tnext = cm_q_round_probe\n"
		"\t\t\t}\n"
	)
	return text[:start] + new + text[end:]


def _add_scan_gate(text: str) -> str:
	"""The two scripted_guis the one-shot driver needs, verbatim from dev 2.3.0."""
	# Above cm_q_sync_check's own comment block, not between it and its definition:
	# a comment that ends up over the wrong block is worse than no comment.
	anchor = "# Per-round completion check for the construct window's loop."
	if anchor not in text:
		raise SystemExit(
			f"{SGUI}: cm_q_sync_check's comment block does not start where this edit "
			"expects; the scan gate has "
			"nowhere to sit without landing over the wrong definition"
		)
	block = (
		"# cm_perf, from dev 2.3.0. Gates the construction-queue window's one-shot scan\n"
		"# driver. Root is the player. Set by the dispatcher when a cycle arms, and again\n"
		"# by cm_q_sync_check when a stalled cycle still has unscored entries; cleared by\n"
		"# the scan driver's own terminal state.\n"
		"cm_q_scan_gate = {\n"
		"\tis_shown = {\n"
		"\t\texists = var:cm_q_scan_armed\n"
		"\t}\n"
		"}\n"
		"\n"
		"# cm_perf, from dev 2.3.0. Ends the scan driver's one sweep. Root is the player.\n"
		"cm_q_scan_disarm = {\n"
		"\teffect = {\n"
		"\t\tif = {\n"
		"\t\t\tlimit = { exists = var:cm_q_scan_armed }\n"
		"\t\t\tremove_variable = cm_q_scan_armed\n"
		"\t\t}\n"
		"\t}\n"
		"}\n"
		"\n"
	)
	i = text.index(anchor)
	return text[:i] + block + text[i:]


def _rescan_when_stalled(text: str) -> str:
	"""Dev 2.3.0's rescan, which is what makes one sweep per cycle safe.

	The repeated sweep CM had covered one case: an item widget that had not
	instantiated when a sweep fired had no other way back in. Dev answers it by
	re-arming the one-shot scan after six rounds with no progress, at most twice.
	Placed before the give-up branch and resetting the stall counter, so a round
	that rescans cannot also give up.
	"""
	anchor = (
		"\t\t\t\t\tif = {\n"
		"\t\t\t\t\t\t# 8 stalled rounds is about 2.4s with zero instantiation progress.\n"
		"\t\t\t\t\t\tlimit = { var:cm_q_stall_rounds >= 8 }\n"
	)
	if text.count(anchor) != 1:
		raise SystemExit(f"{SGUI}: the stall watchdog has moved; the rescan has nowhere to go")
	branch = (
		"\t\t\t\t\t# cm_perf, from dev 2.3.0. Scoring is the only side a re-sweep can help: an\n"
		"\t\t\t\t\t# item widget that had not instantiated when the one sweep fired has no other\n"
		"\t\t\t\t\t# way back in, while an unverified approved entry gets a probe every round.\n"
		"\t\t\t\t\t# Resets the stall count, so the give-up branch below cannot fire this round.\n"
		"\t\t\t\t\tif = {\n"
		"\t\t\t\t\t\tlimit = {\n"
		"\t\t\t\t\t\t\tvar:cm_q_stall_rounds >= 6\n"
		"\t\t\t\t\t\t\tvar:cm_q_processed < var:cm_q_staged\n"
		"\t\t\t\t\t\t\tvar:cm_q_rescans < 2\n"
		"\t\t\t\t\t\t\tNOT = { exists = var:cm_q_scan_armed }\n"
		"\t\t\t\t\t\t}\n"
		"\t\t\t\t\t\tchange_variable = { name = cm_q_rescans add = 1 }\n"
		"\t\t\t\t\t\tset_variable = { name = cm_q_stall_rounds value = 0 }\n"
		"\t\t\t\t\t\tset_variable = { name = cm_q_scan_armed value = yes }\n"
		"\t\t\t\t\t}\n"
	)
	return text.replace(anchor, branch + anchor)


def _arm_the_scan(text: str) -> str:
	"""Arm the one-shot scan with the cycle, and zero the rescan count with it."""
	reset = "\t\t\tset_variable = { name = cm_q_stall_rounds value = 0 }\n"
	arm = (
		"\t\t\tif = { limit = { var:cm_q_staged >= 1 }\n"
		"\t\t\t\tset_variable = { name = cm_should_construct value = yes }\n"
	)
	if text.count(reset) != 1 or text.count(arm) != 1:
		raise SystemExit(
			f"{DISPATCH}: the per-cycle reset or the arming branch has moved; "
			"the one-shot scan cannot be armed blind"
		)
	text = text.replace(
		reset,
		reset
		+ "\t\t\t# cm_perf: counts this cycle's rescans, read by cm_q_sync_check.\n"
		"\t\t\tset_variable = { name = cm_q_rescans value = 0 }\n",
	)
	return text.replace(
		arm,
		arm
		+ "\t\t\t\t# cm_perf: the one sweep this cycle gets, fired by the scan driver.\n"
		"\t\t\t\tset_variable = { name = cm_q_scan_armed value = yes }\n",
	)


def _thin_the_pulse(text: str) -> str:
	"""Run the whole auto-expand cycle once every PULSE_MONTHS, not every month.

	CM does all of its work on one monthly on_action, and the cost grows with the
	number of auto-expand points — his words 2026-09-19, after removing this mod
	because it still slowed a large country. Dividing the pulse divides that cost
	by the same number, and it is one insertion: an on_action takes a `trigger`
	block (the game does it in `appanage_monthly.txt`), and `current_month` is a
	trigger of its own (1..12, no scope). Nothing else in the file moves.

	The two lighter monthly hooks — the CMF list refresh and auto town rights —
	stay monthly on purpose: if the dip survives this, they are what is left.
	"""
	if 12 % PULSE_MONTHS:
		raise SystemExit(
			f"PULSE_MONTHS = {PULSE_MONTHS} does not divide 12; the pattern would "
			"drift from year to year"
		)
	anchor = (
		"cm_unified_auto_expand = {\n"
		"\teffect = {\n"
		"\t\tsave_scope_as = cm_country\n"
	)
	if text.count(anchor) != 1:
		raise SystemExit(
			f"{DISPATCH}: the unified dispatcher's head has moved; the pulse cannot "
			"be thinned blind"
		)
	months = "".join(
		"\t\t\tcurrent_month = %d\n" % m for m in range(1, 13, PULSE_MONTHS)
	)
	gate = (
		"cm_unified_auto_expand = {\n"
		"\t# cm_perf: the whole cycle runs once every %d months, not every month.\n"
		"\t# An on_action's own trigger gates its effect; the game does the same in\n"
		"\t# in_game/common/on_action/appanage_monthly.txt.\n"
		"\ttrigger = {\n"
		"\t\tOR = {\n"
		"%s"
		"\t\t}\n"
		"\t}\n"
		"\teffect = {\n"
		"\t\tsave_scope_as = cm_country\n"
	) % (PULSE_MONTHS, months)
	return text.replace(anchor, gate)


EDITS = (
    (WINDOW, "gate the building-type tree", _gate_the_tree),
    (WINDOW, "widen the first pass's instantiation window", _widen_first_pass),
    (QUEUE, "one construct sweep per cycle, not per round", _split_the_drain_loop),
    (SGUI, "the scan gate the one-shot driver needs", _add_scan_gate),
    (SGUI, "dev 2.3.0's rescan, which makes one sweep safe", _rescan_when_stalled),
    (DISPATCH, "arm the one-shot scan with the cycle", _arm_the_scan),
) + (
    ((DISPATCH, "run the cycle once every %d months" % PULSE_MONTHS, _thin_the_pulse),)
    if PULSE_MONTHS > 1
    else ()
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
