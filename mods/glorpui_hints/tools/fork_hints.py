#!/usr/bin/env python3
"""Glorp UI's societal value hint machinery, taken into this mod under our names.

The owner's decision, 2026-09-14: «просто спизди нужные вещи из glorp. Ничего
потом сверяться не нужно, любые косяки мы самостоятельно изменим и любые
обновления уже свои сделаем.» Glorp UI is off the playset and the hints have to
keep working, so the four generated files their tooltip stands on are copied
here and become this mod's to maintain.

**Renamed, not copied verbatim, and that is the whole point of the file.** A
`customizable_localization` cannot be overridden — the first definition read
wins and every later one is dropped with `gamedatabase.h: Duplicated key` — so
keeping their names would mean that, in a playset holding both mods, which
definition the game uses depends on load order and nothing here could say which.
Under `svx_svh_*` there is no collision at all: with Glorp UI installed both sets
exist side by side, and the `.gui` this mod writes reaches only for ours.

What is taken, and what each of them does:

| their file | here | what it holds |
| --- | --- | --- |
| `glorpui_generated_societal_value_hint_loc.txt` | `svx_svh_hint_loc.txt` | one `customizable_localization` per hint line: the takeability trigger, and the localization key to print when it passes |
| `glorpui_generated_societal_value_hint_script_values.txt` | `svx_svh_hint_script_values.txt` | one script value per axis end: nonzero while that end has at least one takeable line, which is what the `.gui` asks before drawing the list |
| `glorpui_societal_value_hint_scripted_triggers.txt` | `svx_svh_triggers.txt` | the three takeability gates the other two call — reform, policy, privilege |
| `glorpui_societal_value_hint_warning_suppression.txt` | `svx_svh_suppression.txt` | declares the two GUI-set scopes so the parser does not warn about them |

**One thing is removed rather than renamed.** Their script values carry
`NOT = { has_variable = showUnavailableSocietalValueSuggestions }` — their own
«show unavailable» switch, set by their settings window, which does not exist
here. The clause is stripped and the same switching is done in the `.gui` off
this mod's own `svx__show_all`, where every other list of this mod is already
switched. The count of clauses removed is reported, so a build where their file
stops carrying it says so instead of silently changing behaviour.

**Taken once, and then it is ours.** A rebuild does not re-take a file that is
already here: the owner's whole point was that fixes and updates to these lists
are made in this mod from now on, and a generator that copied their version back
over an edit would be the one thing he asked not to happen. To take their
current file again, delete ours and rebuild — the build says which files it kept
and which it took.

Usage: not run by hand — `generate.py --game-files` calls `fork()`.
"""

from __future__ import annotations

import re
from pathlib import Path

# Their identifiers, and ours. Applied to every generated file, the localization
# included, so a key and the thing that prints it always move together.
#
# `glorpui_sv` and `glorpui_country` are the two scope names the `.gui` sets
# before it asks for a script value; nothing could collide over them, but they
# move as well, because every file that sets one and every file that reads one
# is written by this mod's generators and renamed in the same pass. The order
# matters: `glorpui_svh` goes first, or the shorter rule would eat its prefix.
RENAMES = (
    # The advance gate composes its own name out of the hint key it takes over,
    # so `svx_unlock_` + their key would come out as `svx_unlock_glorp_ui_svh_…`.
    # These two run first and leave `svx_unlock_<axis>_<object>`.
    (re.compile(r"\bsvx_unlock_glorp_ui_svh_"), "svx_unlock_"),
    (re.compile(r"\bSVX_UNLOCK_GLORP_UI_SVH_"), "SVX_UNLOCK_"),
    (re.compile(r"\bglorpui_svh"), "svx_svh"),
    (re.compile(r"\bGLORP_UI_SVH"), "SVX_SVH"),
    (re.compile(r"\bglorpui_sv\b"), "svx_sv"),
    (re.compile(r"\bglorpui_country\b"), "svx_country"),
)

# Their switch, which has nothing to set it here.
THEIR_SWITCH = re.compile(
    r"^[ \t]*NOT = \{ has_variable = showUnavailableSocietalValueSuggestions \}[ \t]*\n",
    re.M)

HEADER = """\
# Taken from Glorp UI by mods/glorpui_hints/tools/fork_hints.py and renamed into
# this mod's own namespace. Do not edit by hand — edit the fork, not the copy.
#
# Source: %s
# Their generator's own header follows.
"""

# their path under the Glorp UI tree -> ours under this mod
FORKED = (
    ("in_game/common/customizable_localization/"
     "glorpui_generated_societal_value_hint_loc.txt",
     "in_game/common/customizable_localization/svx_svh_hint_loc.txt"),
    ("in_game/common/script_values/"
     "glorpui_generated_societal_value_hint_script_values.txt",
     "in_game/common/script_values/svx_svh_hint_script_values.txt"),
    ("in_game/common/scripted_triggers/"
     "glorpui_societal_value_hint_scripted_triggers.txt",
     "in_game/common/scripted_triggers/svx_svh_triggers.txt"),
    ("in_game/common/scripted_effects/"
     "glorpui_societal_value_hint_warning_suppression.txt",
     "in_game/common/scripted_effects/svx_svh_suppression.txt"),
)


def rename(text: str) -> str:
    """Their names to ours, everywhere, in one pass per rule."""
    for pattern, replacement in RENAMES:
        text = pattern.sub(replacement, text)
    return text


def fork(glorp, mod) -> tuple[list[tuple[str, str]], int, list[str]]:
    """[(path, text)] to write, their switch clauses dropped, and what was kept.

    A file this mod already has is left alone and named in the third return
    value; only the missing ones are taken. Raises if a file has to be taken and
    is not in the reference tree — a hint list that silently stopped being
    copied is the fault this whole mod exists to avoid.
    """
    out: list[tuple[str, str]] = []
    kept: list[str] = []
    stripped = 0
    for theirs, ours in FORKED:
        if (Path(mod) / ours).is_file():
            kept.append(ours)
            continue
        source = glorp / theirs
        if not source.is_file():
            raise SystemExit(
                "fork_hints: %s is not in the reference tree — the hint lists "
                "cannot be rebuilt without it" % theirs)
        text = source.read_text(encoding="utf-8-sig")
        text, count = THEIR_SWITCH.subn("", text)
        stripped += count
        out.append((ours, HEADER % theirs + rename(text)))
    return out, stripped, kept
