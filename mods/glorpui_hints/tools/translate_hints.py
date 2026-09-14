#!/usr/bin/env python3
"""Glorp UI's societal value hints, in every language the game ships.

Glorp UI ships `glorpui_generated_societal_value_hints_l_english.yml` in
`main_menu/localization/english/` and nowhere else. Paradox games load the
localization folder of the selected language only, with no fallback to English,
so on a Russian client every `GLORP_UI_SVH_*` key is missing, the hint list
renders empty, and the tooltip says "Нет." — while `debug.log` collects one
`Missing loc key` line per key per load. The same is true of the other nine
non-English languages.

The hint strings are built from exactly three templates, and one line of one
looks like this:

    @hint! Grant #TOOLTIP:ESTATE_PRIVILEGE,kormlenije #L $kormlenije$#!#!: #color_green +0.10#!\\n
           ^^^^^ ^-------------------- the reference -------------------^  ^-- the number --^

Since 2026-08-28 Glorp UI writes the same reference as a data function instead,
and both shapes are in the file:

    @hint! Grant [ShowEstatePrivilegeName('petty_bureaucracy')]: #color_green +0.20#!\\n

Everything language specific is the opener. The reference in the middle is what
makes the privilege's name appear and hoverable, and the game resolves it in
whatever language the player runs, in either shape; the number is a number. So
a language costs **three phrases**, held in `languages.py`, each written with a `{ref}`
placeholder so a language may put the opener after the object rather than in
front of it — which German, Turkish, Japanese and Korean all want to.

    python3 mods/glorpui_hints/tools/translate_hints.py \\
        --source <glorp ui>/main_menu/localization/english/glorpui_generated_societal_value_hints_l_english.yml \\
        --output <mod>/main_menu/localization/russian/glorpui_generated_societal_value_hints_l_russian.yml \\
        --language russian

Normally it is run through `mods/glorpui_hints/tools/generate.py`, which does
every language in one pass.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import languages as svx_languages  # noqa: E402

# Glorp UI writes the reference in either of two shapes, and has written both:
# the `#TOOLTIP:` markup it started with, and, since 2026-08-28, the engine's
# own `[ShowEstatePrivilegeName('petty_bureaucracy')]` data function. Both put
# the object's name on screen in the player's language with the tooltip
# attached, and both are copied through a translation byte for byte -- which is
# the whole point of splitting a hint up. A shape neither covers raises
# `Unrecognised` rather than being guessed at.
REFERENCE = (
    r"(?P<ref>"
    r"#TOOLTIP:(?P<registry>[A-Z_]+),\S+ #L \$\S+\$#!#!"
    r"|\[(?P<function>Show\w+?Name(?:WithNoTooltip)?)\('[^']+'\)\]"
    r")"
)

# One hint, split into the four parts above. `tail` is the trailing game concept
# token English carries ("... the Altepetl [government_reform|e]:"); the opener
# in `languages.py` decides for itself whether its language wants one.
HINT_RE = re.compile(
    r'^@hint! (?P<opener>.*?)' + REFERENCE + r'(?P<tail>[^:]*): (?P<value>.*)$')

# `ShowEstatePrivilegeName` names the same registry the `#TOOLTIP:` form spells
# `ESTATE_PRIVILEGE`, so the opener a hint wants is derived from the function
# rather than tabulated: a form Glorp UI adopts for an object type this mod has
# never seen then fails with "no opener for registry X" -- the same error, and
# the same one-line fix in `languages.py` -- instead of silently going untranslated.
FUNCTION_RE = re.compile(r"Show(\w+?)Name(?:WithNoTooltip)?$")


def registry_of(match: "re.Match[str]") -> str:
    """Which of `languages.py`'s hint openers this reference asks for."""
    if match.group("registry"):
        return match.group("registry")
    body = FUNCTION_RE.match(match.group("function")).group(1)
    return re.sub(r"(?<!^)(?=[A-Z])", "_", body).upper()

ENTRY_RE = re.compile(r'^ (GLORP_UI_SVH_\w+): "(.*)"\s*$')

SOURCE_NAME = "glorpui_generated_societal_value_hints_l_english.yml"


def output_name(language: str) -> str:
    # Their keys live here under `svx_svh_*` since the 2026-09-14 fork, so the
    # file is this mod's own and named as one.
    return "svx_svh_hints_l_%s.yml" % language


class Unrecognised(Exception):
    """A hint Glorp UI now writes in a shape the openers do not cover."""


def translate(value: str, openers: dict[str, str]) -> str:
    match = HINT_RE.match(value)
    if not match:
        raise Unrecognised(value)
    registry = registry_of(match)
    opener = openers.get(registry)
    if opener is None:
        raise Unrecognised("no opener for registry %s: %s" % (registry, value))
    return "@hint! %s: %s" % (opener.format(ref=match.group("ref")),
                              match.group("value"))


def gate_key(hint_key: str) -> str:
    """The customizable localization that decides whether one hint prints."""
    return "svx_unlock_%s" % hint_key.lower()


def line_key(hint_key: str) -> str:
    """Where the hint's actual words go once the key itself is a dispatch."""
    return "SVX_UNLOCK_%s" % hint_key


def render(source: Path, language: str,
           gated: dict[str, str] | None = None,
           only_gated: bool = False) -> tuple[str, int, int]:
    """The file's text for one language, and how many hints and bodies it holds.

    `only_gated` keeps just the hints this mod actually changes and drops the
    rest. Since 2026-08-28 Glorp UI ships its own hints in all eleven languages,
    so re-emitting them is an override that changes nothing and pins their file
    against their next update -- see `SHIP_GLORP_HINTS` in `generate.py`.

    `gated` names the hints that must not be suggested until an advance unlocks
    the privilege they are about. Such a hint's own key becomes a dispatch to a
    customizable localization, and its words move to a second key the dispatch
    points at — because a `customizable_localization` **cannot be overridden**:
    the first definition read wins and a later duplicate is dropped with
    `gamedatabase.h: Duplicated key ... will not be created from file`. Glorp
    UI's entry is therefore untouchable, but the localization key that entry
    prints is not, and this mod is already rewriting every one of them.
    """
    openers = svx_languages.PHRASES[language]["hint"]
    gated = gated or {}
    lines = source.read_text(encoding="utf-8-sig").split("\n")

    out: list[str] = []
    translated = bodies = 0
    for line in lines:
        if line.strip() == "l_english:":
            out.append("l_%s:" % language)
            continue
        match = ENTRY_RE.match(line)
        if not match:
            # Glorp UI's own comments and blank lines belong to Glorp UI's file;
            # a file that keeps only what this mod changes keeps none of them.
            if not only_gated or not out:
                out.append(line)
            continue
        key, value = match.groups()
        if key.startswith("GLORP_UI_SVH_BODY_"):
            # Pure [Player.Custom('...')] concatenations — language independent.
            if not only_gated:
                bodies += 1
                out.append(line)
            continue
        try:
            text = translate(value, openers)
        except Unrecognised as exc:
            raise Unrecognised("%s: %s" % (key, exc)) from None
        if key in gated:
            out.append(' %s: "[Player.Custom(\'%s\')]"' % (key, gate_key(key)))
            out.append(' %s: "%s"' % (line_key(key), text))
        elif not only_gated:
            out.append(' %s: "%s"' % (key, text))
        else:
            continue
        translated += 1

    if only_gated:
        out[0] = ("# The few of Glorp UI's societal value hints this mod changes in"
                  " %s, written by" % language)
        out.insert(1, "# mods/glorpui_hints/tools/translate_hints.py. Do not edit"
                      " by hand. Glorp UI ships the")
        out.insert(2, "# rest in this language itself; only these wait for the"
                      " advance that unlocks them.")
    else:
        out[0] = ("# Glorp UI's societal value hints in %s, written by "
                  "mods/glorpui_hints/tools/translate_hints.py. Do not edit by hand."
                  % language)
        out.insert(1, "# Source: Glorp UI %s" % source.name)
    # A file the game reads has to end with a newline like any other.
    return "\n".join(out).rstrip("\n") + "\n", translated, bodies


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--language", default="russian",
                        choices=svx_languages.LANGUAGES)
    args = parser.parse_args(argv[1:])

    try:
        text, translated, bodies = render(args.source, args.language)
    except Unrecognised as exc:
        print("unrecognised hint shape — add an opener to languages.py: %s" % exc,
              file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8-sig", newline="\n")
    print("translated %d hints, copied %d body keys" % (translated, bodies))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
