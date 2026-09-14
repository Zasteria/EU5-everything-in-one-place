#!/usr/bin/env python3
"""Rebuild `glorpui_hints` from Glorp UI, and refuse to write it broken.

Two things live in this mod, and they are rebuilt on different occasions:

* **Glorp UI's hint text** is its own English file with the opener replaced,
  once per language, so a Glorp UI update that adds hints is picked up in all
  eleven languages without anyone noticing it happened. Regenerated every run.
* **The extra hint lists** are compiled out of the *game's* `common/` tree —
  laws, static modifiers, religious aspects, employment systems and the rest —
  which is large, so they are committed as generated files and rebuilt only when
  asked:

      python3 mods/glorpui_hints/tools/generate.py --game-files reference/game

What runs unconditionally is the part that catches the update this mod is most
likely to be broken by. The mod **overrides Glorp UI's own override** of
`SocietalValueCountryLeft_tooltip` / `SocietalValueCountryRight_tooltip`, and it
re-emits Glorp UI's list inside it. If Glorp UI restructures those templates,
nothing errors at load: the player simply gets our older copy of Glorp UI's list
and never sees whatever Glorp UI added. So the checks below compare the two
files every run and fail naming the difference.

    python3 mods/glorpui_hints/tools/generate.py
    python3 mods/glorpui_hints/tools/generate.py --check    # write nothing

And when Glorp UI has moved and the question is what that costs:

    python3 mods/glorpui_hints/tools/generate.py --conflicts

which lists the three — only three — places this mod writes over Glorp UI's own
work, and says whether the copy here is still theirs. Run it before a rebuild
and after one: the first says what their update changed, the second says whether
the rebuild picked it up.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
MOD = TOOLS.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(MOD.parent.parent / "tools"))

import refs  # noqa: E402
import generate_extra  # noqa: E402  the hint lists and the fork
import fork_hints  # noqa: E402  their names to ours, in every generated file
import languages as svx_languages  # noqa: E402
import translate_hints  # noqa: E402

EXTRA_GUI = MOD / "in_game/gui/svx_extra_societal_value_hints.gui"
UNLOCK_GATE = MOD / "in_game/common/customizable_localization/svx_unlock_gate.txt"
EXTRA_CUSTOM = MOD / "in_game/common/customizable_localization/svx_extra_hint_loc.txt"
EXTRA_VALUES = MOD / "in_game/common/script_values/svx_extra_hint_script_values.txt"
# Glorp UI's, forked under this mod's names by `fork_hints.py`.
FORKED_CUSTOM = MOD / "in_game/common/customizable_localization/svx_svh_hint_loc.txt"
FORKED_VALUES = MOD / "in_game/common/script_values/svx_svh_hint_script_values.txt"

# Which languages get Glorp UI's whole hint text from here rather than from
# Glorp UI.
#
# Until 2026-08-28 the answer was all eleven, because Glorp UI shipped English
# and nothing else and the other ten rendered as raw keys — that was this mod's
# reason to exist. Their build of that day ships all eleven itself, in the
# opener-per-language shape this mod worked out; the Korean is 179 keys
# identical to ours. So re-emitting them is an override that changes nothing and
# pins their file against every update they make, in ten languages nobody here
# has reviewed.
#
# Russian stays, because it is the language the owner plays and reads, and he
# prefers this mod's wording to Glorp UI's copy of it. Everywhere else Glorp
# UI's own text is what the player gets, and this mod ships only the handful of
# hints it actually changes — the ones an advance has to unlock first, which
# Glorp UI still recommends to a country that cannot take them.
# **All eleven since the 2026-09-14 fork.** Until then Glorp UI shipped the text
# itself and this mod only re-emitted Russian, which the owner prefers. With
# Glorp UI off the playset nobody else ships any of it, so every language comes
# from here — the openers in `languages.py` are what makes that cost fifty
# strings rather than eleven thousand.
SHIP_GLORP_HINTS = list(svx_languages.LANGUAGES)


def hints_path(language: str) -> Path:
    return (MOD / "main_menu/localization" / language
            / translate_hints.output_name(language))


def extra_path(language: str) -> Path:
    return (MOD / "main_menu/localization" / language
            / ("svx_extra_hints_l_%s.yml" % language))


def fixes_path(language: str) -> Path:
    return (MOD / "main_menu/localization" / language
            / ("svx_glorpui_fixes_l_%s.yml" % language))


def render_fixes(language: str) -> str:
    """Glorp UI's own keys this mod repairs in one language, and only there."""
    out = [HEADER,
           "# Glorp UI's own interface keys, repaired. Only the languages whose",
           "# text is actually broken get a file: overriding a translation that",
           "# is fine would pin it against a Glorp UI update for no reason.",
           "l_%s:" % language]
    for key, text in svx_languages.GLORP_UI_FIXES[language].items():
        out.append(' %s: "%s"' % (key, text))
    return "\n".join(out) + "\n"


def menu_path(language: str) -> Path:
    return (MOD / "main_menu/localization" / language
            / ("svx_menu_l_%s.yml" % language))


GLORP_HINTS_GUI = "in_game/gui/glorpUI_generated_societal_value_hints.gui"
GLORP_HINTS_VALUES = (
    "in_game/common/script_values/glorpui_generated_societal_value_hint_script_values.txt")
GLORP_HINTS_EN = ("main_menu/localization/english/"
                  + translate_hints.SOURCE_NAME)

# One TooltipScrolledStringPairList, reduced to what it actually does: which
# script value gates it, what title it carries, which body key it prints.
ENTRY_RE = re.compile(
    r"ScriptValue\('(?P<value>\w+)'\).*?"
    r'text = "(?P<title>[A-Z_]+)".*?'
    r"Localize\('(?P<body>\w+)'\)",
    re.S)
TEMPLATE_RE = re.compile(r"^template (\w+) \{", re.M)
LOC_KEY_RE = re.compile(r"^ (\w+):", re.M)
CUSTOM_RE = re.compile(r"^(\w+) = \{$", re.M)
SCRIPT_VALUE_RE = re.compile(r"^(\w+) = \{$", re.M)
PLAYER_CUSTOM_RE = re.compile(r"\[Player\.Custom\('(\w+)'\)\]")

HEADER = ("# Auto-generated by mods/glorpui_hints/tools/generate.py from the EU5 "
          "game files. Do not edit by hand.")


def entries(text: str) -> list[tuple[str, str, str, str]]:
    """(template, gating script value, title key, body key), in file order."""
    found = []
    for match in ENTRY_RE.finditer(text):
        template = "?"
        for candidate in TEMPLATE_RE.finditer(text[:match.start()]):
            template = candidate.group(1)
        found.append((template, match.group("value"),
                      match.group("title"), match.group("body")))
    return found


def check_glorp_list_is_current(problems: list[str], glorp: Path) -> None:
    """This mod's copy of Glorp UI's block must be Glorp UI's block, byte for byte.

    The mod replaces that `blockoverride` wholesale, so whatever is not carried
    across is a piece of Glorp UI the player stops getting. Compared as **text**
    rather than as parsed entries, and that is the whole point: this check used
    to compare what a regex recognised, and Glorp UI's 2026-08-28 build added an
    entry with neither a `ScriptValue` nor a `Localize` in it — vanilla's own
    hint blob behind their `showUnavailableSocietalValueSuggestions` setting.
    The parse could not see it, the check passed, and their new setting silently
    did nothing for anyone running both mods. Bytes cannot be blind that way.
    """
    theirs_file = (glorp / GLORP_HINTS_GUI).read_text(encoding="utf-8-sig")
    ours_file = EXTRA_GUI.read_text(encoding="utf-8-sig")
    for template, block in (
            ("SocietalValueCountryLeft_tooltip", "societal_value_left_tooltip_extra"),
            ("SocietalValueCountryRight_tooltip", "societal_value_right_tooltip_extra")):
        theirs = generate_extra.blockoverride_body(theirs_file, template, block)
        ours = generate_extra.blockoverride_body(ours_file, template, block)
        if ours.startswith(theirs):
            continue
        # Name the first line that differs; a whole block in a message is
        # unreadable and the first difference is what has to be looked at.
        for line_a, line_b in zip(ours.split("\n"), theirs.split("\n")):
            if line_a != line_b:
                problems.append(
                    "%s: Glorp UI's block is no longer carried verbatim — rebuild"
                    " with --game-files\n       theirs: %s\n       ours:   %s"
                    % (template, line_b.strip()[:120], line_a.strip()[:120]))
                break
        else:
            problems.append(
                "%s: Glorp UI's block is longer than the copy here — rebuild with"
                " --game-files" % template)


def check_english_is_glorp_uis_own(problems: list[str], glorp: Path) -> None:
    """Rendering English must give Glorp UI's file back, character for character.

    This is the proof that splitting a hint into opener, reference and number
    loses nothing: English's openers are Glorp UI's own English, so a lossless
    parse round-trips. If Glorp UI writes a hint the parse mangles rather than
    rejects, this is what notices — the ten other languages have no original to
    be compared against.
    """
    source = glorp / GLORP_HINTS_EN
    # Ungated: a held-back hint is deliberately not what Glorp UI writes, and
    # what is being checked here is that the *parse* loses nothing.
    ours, _, _ = translate_hints.render(source, "english")
    # Two header lines are this tool's; everything after the `l_english:` line
    # must match Glorp UI's file exactly.
    mine = ours.split("\n")[2:]
    theirs = source.read_text(encoding="utf-8-sig").split("\n")[1:]
    if mine == theirs:
        return
    for line_a, line_b in zip(mine, theirs):
        if line_a != line_b:
            problems.append("English render differs from Glorp UI's own file, "
                            "so the opener parse is lossy:\n       ours:   %s\n"
                            "       theirs: %s" % (line_a[:160], line_b[:160]))
            return
    problems.append("English render differs from Glorp UI's own file in length")


ADVANCE_BLOCK_RE = re.compile(r'([A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{|[{}]')
UNLOCKS_RE = re.compile(r'unlock_estate_privilege\s*=\s*([a-z_0-9]+)')
# Which privilege a hint is about, in either shape Glorp UI has written the
# reference in -- see `translate_hints.REFERENCE`. This one matters more than it
# looks: a shape it misses matches nothing, `unlock_gates` comes back empty, and
# the five advance-locked privileges quietly stop being held back. Nothing errors
# and the mod ships recommending privileges the country cannot take, so
# `check_gates_found_something` refuses a run whose two readings disagree.
PRIVILEGE_HINT_RE = re.compile(
    r'^ (?P<key>GLORP_UI_SVH_\w+): "@hint! [^"]*?'
    r'(?:#TOOLTIP:ESTATE_PRIVILEGE,(?P<tooltip>\w+) '
    r"|\[ShowEstatePrivilegeName(?:WithNoTooltip)?\('(?P<function>\w+)'\)\])", re.M)


def privileges_locked_behind_an_advance() -> dict[str, str]:
    """privilege -> the advance whose `unlock_estate_privilege` opens it.

    Glorp UI's own filter, `glorpui_svh_privilege_takeable`, reads a privilege's
    `potential` and `allow` and nothing else. Ten vanilla privileges are locked
    from the other side instead — by an advance — and their own `potential` is
    empty, so they sail through the filter and get recommended to a country that
    cannot take them. Read out of the advances rather than listed, so a patch
    that locks an eleventh is picked up by a rebuild.
    """
    locked: dict[str, str] = {}
    root = refs.GAME_COMMON / "advances"
    if not root.is_dir():
        return locked
    for path in sorted(root.rglob("*.txt")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        depth, name, start = 0, None, None
        for match in ADVANCE_BLOCK_RE.finditer(text):
            token = match.group(0)
            if token.endswith("{"):
                if depth == 0 and match.group(1):
                    name, start = match.group(1), match.end()
                depth += 1
            elif token == "}":
                depth -= 1
                if depth == 0 and name:
                    for privilege in UNLOCKS_RE.findall(text[start:match.start()]):
                        locked[privilege] = name
                    name = None
    return locked


def unlock_gates(glorp: Path) -> dict[str, tuple[str, str]]:
    """Glorp UI hint key -> (privilege, advance), for hints that must wait."""
    locked = privileges_locked_behind_an_advance()
    source = (glorp / GLORP_HINTS_EN).read_text(encoding="utf-8-sig")
    found = {match.group("key"): match.group("tooltip") or match.group("function")
             for match in PRIVILEGE_HINT_RE.finditer(source)}
    return {key: (privilege, locked[privilege])
            for key, privilege in found.items() if privilege in locked}


def check_gates_found_something(problems: list[str], glorp: Path) -> None:
    """`PRIVILEGE_HINT_RE` must see every privilege hint the parse sees.

    The advance gates are the one thing here built by a regex of its own rather
    than by the hint parse, and a reference shape it misses is silent: the gates
    come back empty, `svx_unlock_gate.txt` is written with nothing in it, and
    the mod ships recommending privileges an advance has not unlocked yet. That
    is what Glorp UI moving from `#TOOLTIP:ESTATE_PRIVILEGE,x` to
    `[ShowEstatePrivilegeName('x')]` would have done. So the two readings are
    compared rather than trusted.
    """
    source = (glorp / GLORP_HINTS_EN).read_text(encoding="utf-8-sig")
    parsed = set()
    for line in source.split("\n"):
        entry = translate_hints.ENTRY_RE.match(line)
        if not entry or entry.group(1).startswith("GLORP_UI_SVH_BODY_"):
            continue
        hint = translate_hints.HINT_RE.match(entry.group(2))
        if hint and translate_hints.registry_of(hint) == "ESTATE_PRIVILEGE":
            parsed.add(entry.group(1))
    scanned = {match.group("key") for match in PRIVILEGE_HINT_RE.finditer(source)}
    if scanned == parsed:
        return
    missed = sorted(parsed - scanned)
    problems.append(
        "the advance gates read %d of Glorp UI's %d estate privilege hints — "
        "PRIVILEGE_HINT_RE does not cover the shape of %s"
        % (len(scanned), len(parsed), ", ".join(missed[:3]) or "the rest"))


def render_unlock_gate(gates: dict[str, tuple[str, str]]) -> str:
    """The customizable localization each gated hint key dispatches to."""
    out = [HEADER,
           "# Glorp UI recommends a privilege its own filter thinks is takeable.",
           "# These are the ones an advance locks from the other side: the",
           "# privilege's own `potential` is empty, so `glorpui_svh_privilege_takeable`",
           "# lets it through. The list is scanned out of common/advances rather",
           "# than written down, so a patch that locks another one is picked up.",
           "#",
           "# The hint's own localization key is rewritten to print",
           "# [Player.Custom('svx_unlock_<key>')] and the words moved to",
           "# SVX_UNLOCK_<key>, because a customizable_localization cannot be",
           "# overridden — the first definition read wins and a later duplicate is",
           "# dropped with `gamedatabase.h: Duplicated key ... will not be created",
           "# from file`. Localization keys, on the other hand, do override, and",
           "# this mod rewrites every one of Glorp UI's already.",
           ""]
    for key, (privilege, advance) in sorted(gates.items()):
        out += ["# %s, locked by %s" % (privilege, advance),
                "%s = {" % translate_hints.gate_key(key),
                "\ttype = country",
                "\ttext = {",
                "\t\ttrigger = { has_advance = %s }" % advance,
                "\t\tlocalization_key = %s" % translate_hints.line_key(key),
                "\t}",
                "\ttext = {",
                "\t\tlocalization_key = empty_text",
                "\t}",
                "}",
                ""]
    return "\n".join(out)


def game_concept_keys() -> set[str]:
    """Every `game_concept_*` key the game defines, from its own localization."""
    keys: set[str] = set()
    root = refs.GAME / "main_menu/localization"
    for path in root.rglob("*.yml"):
        keys |= set(re.findall(r"^ (game_concept_\w+):", path.read_text(
            encoding="utf-8-sig", errors="replace"), re.M))
    return keys


def check_catalog_concepts_exist(problems: list[str]) -> None:
    """`[religious_aspect|e]` only renders because the game defines the concept.

    The fourteen category nouns are not translated by this mod — they are game
    concepts, which is what makes ten extra languages cost nothing and what
    makes the mod use the game's own word. The price is that a concept the game
    renames turns into a raw token on screen in every language at once, and
    nothing would error. So every id is checked against the game's own
    localization on every run.
    """
    defined = game_concept_keys()
    if not defined:
        problems.append("no game_concept_* keys under reference/game — "
                        "cannot check the catalogue concepts")
        return
    for source_type, concept in sorted(svx_languages.CATALOG_CONCEPTS.items()):
        if "game_concept_%s" % concept not in defined:
            problems.append("languages.py: the game defines no concept %s, "
                            "used for %s" % (concept, source_type))


def check_references_resolve(problems: list[str], glorp: Path,
                             language: str, hints: str) -> None:
    """Every name the `.gui` reaches for is defined by us or by Glorp UI.

    A `.gui` asking for a script value or a loc key that nothing defines does not
    fail to load; it prints zero, or the raw key, which is exactly the fault this
    mod exists to repair. Run per language, because a body key missing in one
    language is exactly the bug this mod was written to fix.
    """
    gui = EXTRA_GUI.read_text(encoding="utf-8-sig")
    defined_values = set(SCRIPT_VALUE_RE.findall(
        EXTRA_VALUES.read_text(encoding="utf-8-sig")))
    defined_values |= set(SCRIPT_VALUE_RE.findall(
        FORKED_VALUES.read_text(encoding="utf-8-sig")))
    loc = extra_path(language).read_text(encoding="utf-8-sig")
    defined_keys = set(LOC_KEY_RE.findall(loc))
    defined_keys |= set(LOC_KEY_RE.findall(hints))
    defined_keys |= set(LOC_KEY_RE.findall(
        menu_path(language).read_text(encoding="utf-8-sig")))

    for _, value, _, body in entries(gui):
        if value not in defined_values:
            problems.append("%s: no script value %s" % (EXTRA_GUI.name, value))
        if body not in defined_keys:
            problems.append("%s: no localization key %s in %s"
                            % (EXTRA_GUI.name, body, language))
    for title in {entry[2] for entry in entries(gui)}:
        # The two titles this mod adds are its own; the vanilla ones are not.
        if title.startswith("SVX_") and title not in defined_keys:
            problems.append("%s: no localization key %s in %s"
                            % (EXTRA_GUI.name, title, language))

    # And every gated line the localization prints has a rule behind it —
    # the availability gates in one file, the advance locks in the other.
    declared = set(CUSTOM_RE.findall(EXTRA_CUSTOM.read_text(encoding="utf-8-sig")))
    declared |= set(CUSTOM_RE.findall(UNLOCK_GATE.read_text(encoding="utf-8-sig")))
    declared |= set(CUSTOM_RE.findall(FORKED_CUSTOM.read_text(encoding="utf-8-sig")))
    used = set(PLAYER_CUSTOM_RE.findall(loc)) | set(PLAYER_CUSTOM_RE.findall(hints))
    # Everything the localization prints is this mod's own now: the forked
    # takeability rules, the availability gates and the advance locks. A name
    # here that nothing declares is a line the player silently never sees.
    for name in sorted({n for n in used if n.startswith("svx_")} - declared):
        problems.append("%s: no customizable localization %s"
                        % (extra_path(language).name, name))
    for name in sorted(declared - used):
        problems.append("%s: %s is declared and never printed in %s"
                        % (EXTRA_CUSTOM.name, name, language))
    for key in sorted({m.group(1) for m in re.finditer(
            r"localization_key = (\w+)",
            EXTRA_CUSTOM.read_text(encoding="utf-8-sig")
            + UNLOCK_GATE.read_text(encoding="utf-8-sig"))}):
        if key != "empty_text" and key not in defined_keys:
            problems.append("%s: no localization key %s in %s"
                            % (EXTRA_CUSTOM.name, key, language))


def check_localization_conventions(problems: list[str], language: str,
                                   files: list[tuple[Path, str]]) -> None:
    """A BOM, one leading space per key, and brackets that close.

    All three are silent in game: a file with no BOM is read as some other
    encoding and its text arrives as mojibake, a key without its leading space
    is not a key at all, and an unbalanced bracket renders as `ERROR:`.
    """
    for path, text in files:
        if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
            problems.append("%s: no UTF-8 BOM" % path.name)
        header = [line for line in text.splitlines() if line.strip().startswith("l_")]
        if header != ["l_%s:" % language]:
            problems.append("%s: header is %r, want ['l_%s:']"
                            % (path.name, header, language))
        for number, line in enumerate(text.splitlines(), 1):
            if (not line.strip() or line.lstrip().startswith("#")
                    or line.strip() == "l_%s:" % language):
                continue
            if not re.match(r'^ \w+: ".*"$', line):
                problems.append("%s:%d: not ` KEY: \"value\"`" % (path.name, number))
                continue
            value = line.split(":", 1)[1]
            if value.count("[") != value.count("]"):
                problems.append("%s:%d: brackets do not balance"
                                % (path.name, number))


def check_languages_are_in_step(problems: list[str]) -> None:
    """Every language defines the same keys, and none of them is empty.

    A key defined in one language and missing in another is the bug this mod
    exists to fix, one folder further along.
    """
    per_language = {}
    for language in svx_languages.LANGUAGES:
        keys = set()
        for path in (extra_path(language), menu_path(language),
                     hints_path(language)):
            keys |= set(LOC_KEY_RE.findall(path.read_text(encoding="utf-8-sig")))
        per_language[language] = keys
    reference_language = "russian"
    # Since the fork every language is shipped from here, hint keys included,
    # so they must match exactly — there is no longer another mod defining any
    # of them in some of the folders and not others.
    expected = per_language[reference_language]
    for language, keys in per_language.items():
        missing, extra = expected - keys, keys - expected
        for key in sorted(missing)[:5]:
            problems.append("%s is missing %s, which %s defines"
                            % (language, key, reference_language))
        for key in sorted(extra)[:5]:
            problems.append("%s defines %s, which %s does not"
                            % (language, key, reference_language))


def known_triggers() -> set[str]:
    """Every name a trigger clause may legitimately start with.

    Three sources, and all three are needed:

    * the engine's own dump, which is the authority on named triggers;
    * the game's `scripted_triggers/`, for things like
      `game_has_missions_enabled` that the dump does not know about;
    * **every name the game itself writes in the same position** anywhere in
      its `common/` tree. Not everything valid is a named trigger:
      `religion = religion:catholic` and `culture = culture:low_frankish` are
      scope comparisons, appear in the dump nowhere, and are written 598 and
      1 418 times by the game. Without this third source the check reports them
      and gets ignored, which is worse than not checking.

    What survives all three is a name nothing in the game has ever written —
    which is what `country_religion` was, in 492 gates.
    """
    names = set(re.findall(
        r"^## (\w+)", (refs.GAME / "docs/triggers.log").read_text(
            encoding="utf-8", errors="replace"), re.M))
    scripted = refs.GAME_COMMON / "scripted_triggers"
    if scripted.is_dir():
        for path in scripted.glob("*.txt"):
            names |= set(re.findall(r"^(\w+)\s*=\s*\{", path.read_text(
                encoding="utf-8-sig", errors="replace"), re.M))
    for path in refs.GAME_COMMON.rglob("*.txt"):
        names |= set(TRIGGER_CALL.findall(path.read_text(
            encoding="utf-8-sig", errors="replace")))
    return names


# A `name = ` at the start of a trigger clause. Values, targets and the right
# hand side of a comparison are not names being called.
TRIGGER_CALL = re.compile(r"(?:^|[{\s])([a-z_][a-z_0-9]*)\s*(?:=|<|>|<=|>=)")
# Logic and control words, which are the engine's own and not in the dump.
TRIGGER_KEYWORDS = {
    "and", "or", "not", "nor", "nand", "if", "else", "else_if", "limit",
    "trigger_if", "trigger_else", "trigger_else_if", "custom_tooltip",
    "custom_description", "hidden_trigger", "value", "add", "subtract",
    "multiply", "divide", "min", "max", "desc", "type", "text",
    "localization_key", "trigger", "scale", "count", "percent", "amount",
}


def trigger_blocks(text: str) -> str:
    """Just the insides of every `trigger = { ... }`, joined.

    The rest of the file is definition names and `localization_key = X`, and
    reading those as trigger calls reports every gate in the mod as unknown.
    """
    out = []
    for match in re.finditer(r"\btrigger\s*=\s*\{", text):
        depth = 0
        for index in range(match.end() - 1, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    out.append(text[match.end():index])
                    break
    return "\n".join(out)


# Logic words keep the scope they are written in; everything else that opens a
# block changes it (`capital = { ... }`, `owner = { ... }`, `any_owned_location`).
SCOPE_PRESERVING = {"AND", "OR", "NOT", "NOR", "NAND", "trigger_if", "trigger_else",
                    "trigger_else_if", "limit", "custom_tooltip",
                    "custom_description", "hidden_trigger"}


def trigger_scopes() -> dict[str, set[str]]:
    """Which scopes each trigger says it supports, from the engine's own dump."""
    text = (refs.GAME / "docs/triggers.log").read_text(
        encoding="utf-8", errors="replace")
    scopes: dict[str, set[str]] = {}
    name = None
    for line in text.splitlines():
        heading = re.match(r"^## (\w+)", line)
        if heading:
            name = heading.group(1)
            continue
        supported = re.match(r"^\*\*Supported Scopes\*\*: (.+?)\s*$", line)
        if supported and name:
            scopes[name] = {part.strip() for part in supported.group(1).split(",")}
            name = None
    return scopes


def country_scope_calls(block: str):
    """Every `name =` written in country scope inside one trigger block.

    Only the calls that are still in the scope the block started in — a nested
    `capital = { ... }` or `owner = { ... }` is a different scope and this does
    not follow it. That is the whole point: the calls it *can* see are exactly
    the ones that have to be country triggers.
    """
    depth = 0
    for match in re.finditer(r"([A-Za-z_][A-Za-z_0-9]*)\s*=\s*\{|\}|"
                             r"([a-z_][a-z_0-9]*)\s*(?:=|<|>|<=|>=)", block):
        if match.group(0) == "}":
            depth = max(0, depth - 1)
        elif match.group(1):
            if depth == 0 and match.group(1) not in SCOPE_PRESERVING:
                depth += 1          # a scope change: stop looking inside it
            elif depth:
                depth += 1
            # a scope-preserving block at depth 0 stays at depth 0
        elif match.group(2) and depth == 0:
            yield match.group(2)


def check_gate_scopes(problems: list[str]) -> None:
    """A country gate may only call triggers the engine allows in a country.

    The gates copy blocks verbatim out of the game's own files, and a block the
    game evaluates somewhere else is written for somewhere else. A building's
    `allow` is asked of the *location* being built in, so it says
    `is_core_of = owner` — and pasted into a `type = country` customizable
    localization that produced one line in the player's error.log, a gate that
    never answered, and nothing on screen to say so:

        jomini_trigger.cpp:803: is_core_of: Inconsistent trigger scopes
        (country vs. location) at svx_extra_hint_loc.txt:3073

    The engine's own dump states **Supported Scopes** per trigger, so this is
    answerable here rather than in a round trip. Only the calls still in the
    outer scope are checked; a nested `capital = { ... }` is a different scope
    and is left alone, which is exactly what the repair for that bug is.
    """
    scopes = trigger_scopes()
    if not scopes:
        problems.append("no triggers.log in reference/ — cannot check gate scopes")
        return
    for path in (EXTRA_CUSTOM, UNLOCK_GATE):
        seen: dict[str, int] = {}
        for block in trigger_blocks(path.read_text(encoding="utf-8-sig")).split("\n"):
            for name in country_scope_calls(block):
                supported = scopes.get(name)
                # `none` is the dump's word for "no scope required" —
                # `always`, `exists`, `has_variable`, `has_dlc`. Unknown names
                # are `check_triggers_exist`'s business, not this one's.
                if supported is None or supported & {"country", "none"}:
                    continue
                seen[name] = seen.get(name, 0) + 1
        for name, count in sorted(seen.items()):
            problems.append(
                "%s: %s is a %s trigger, called in country scope (%d time%s) — "
                "the engine logs `Inconsistent trigger scopes` and the gate "
                "never answers" % (path.name, name,
                                   "/".join(sorted(scopes[name])), count,
                                   "" if count == 1 else "s"))


def check_triggers_exist(problems: list[str]) -> None:
    """Every trigger the gates call is one the engine or the game defines.

    A mistyped trigger name is a load error, not a quiet nothing — but it is a
    load error in the *player's* game, found by them, a round trip away. The
    names come out of the shipped files and the engine's own dump, so checking
    them costs nothing and closes the one way this file can be wrong by a
    keystroke.
    """
    known = known_triggers()
    if not known:
        problems.append("no triggers.log in reference/ — cannot check trigger names")
        return
    seen: dict[str, int] = {}
    for name in TRIGGER_CALL.findall(trigger_blocks(
            EXTRA_CUSTOM.read_text(encoding="utf-8-sig")
            + UNLOCK_GATE.read_text(encoding="utf-8-sig"))):
        if name in TRIGGER_KEYWORDS or name in known:
            continue
        seen[name] = seen.get(name, 0) + 1
    for name, count in sorted(seen.items()):
        problems.append("%s: no trigger named %s (%d call%s)"
                        % (EXTRA_CUSTOM.name, name, count, "" if count == 1 else "s"))


# One entry of a TooltipScrolledStringPairList: everything between `@hint!` and
# the colon that splits the pair. `(?:(?!@hint!).)` rather than `.` because a
# body key is one long line of many entries, and a plain non-greedy match starts
# at the *first* `@hint!` and swallows every entry up to the first colon — which
# made the first version of this check pass on a label it was written to catch.
HINT_LABEL = re.compile(r"@hint!((?:(?!@hint!).)*?):\s*#color_green")
# What is markup or a reference rather than something a player reads.
NOT_TEXT = re.compile(r"\$[^$]*\$|\[[^\]]*\]|#[A-Za-z_!]+|#!|\\n")
# A game concept link, which is the one reference that may stand as a label on
# its own — see check_hints_have_labels.
CONCEPT_TOKEN = re.compile(r"\[(\w+)\|[eE]\]")


def check_hints_have_labels(problems: list[str], language: str) -> None:
    """Every hint line says something before its number.

    A line whose whole label is `$SOME_KEY$` renders as a bare value with no
    text when that reference does not resolve, and nothing errors. It happened:
    `$STATIC_MODIFIER_NAME_parliament_outside_capital$` came out blank on screen
    while `$STATIC_MODIFIER_NAME_is_bankrupt$` two lines away came out fine.

    So the rule is not "references are banned" — the catalogue lines reference
    `$building_type$` and always have — but "a label must carry text that is
    certain to resolve". Literal text always is. A **game concept token** is the
    one reference that also is: `[religious_aspect|e]` reads
    `game_concept_religious_aspect`, the game defines it in every one of its
    localization folders, and `check_catalog_concepts_exist` verifies each id
    this mod uses against the game's own files on every run. That is what lets
    the fourteen category nouns go untranslated in eleven languages.
    """
    text = extra_path(language).read_text(encoding="utf-8-sig")
    defined = game_concept_keys()
    for label in HINT_LABEL.findall(text):
        if NOT_TEXT.sub("", label).strip():
            continue
        concepts = CONCEPT_TOKEN.findall(label)
        if concepts and all("game_concept_%s" % name in defined
                            for name in concepts):
            continue
        problems.append("%s: a hint label is nothing but markup and references"
                        " — %r would render blank"
                        % (extra_path(language).name, label.strip()))
        return


# Somebody else's localization line, which is not written the way ours are:
# Glorp UI ends several with a `# LOCK` marker *after* the closing quote, and a
# parser that insists the quote is last reads none of them — the same mistake
# `nation_destinies_rus` already cost this repository once.
LOC_ENTRY_RE = re.compile(
    r'^ (\w+):\s*(?:\d+\s+)?"(.*)"\s*(?:#.*)?$', re.M)


def glorp_localization(glorp: Path, language: str) -> dict[str, str]:
    """Every key Glorp UI itself defines in one language."""
    found: dict[str, str] = {}
    root = glorp / "main_menu/localization" / language
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*.yml")):
        found.update(dict(LOC_ENTRY_RE.findall(
            path.read_text(encoding="utf-8-sig", errors="replace"))))
    return found


def glorp_hints_text(glorp: Path, language: str) -> str:
    """Glorp UI's own hint file in one language, empty when they ship none."""
    path = (glorp / "main_menu/localization" / language
            / translate_hints.output_name(language))
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""


def conflict_report(glorp: Path) -> int:
    """Every point where this mod writes over Glorp UI's own work.

    Three surfaces, and nothing else — checked rather than remembered, because
    each is a place where a Glorp UI update is silently reverted for anyone
    running both mods. Print it whenever Glorp UI moves, and again after a
    rebuild: the two runs say what the update changed and whether the rebuild
    picked it up.
    """
    print("what this mod writes over, in %s" % glorp.name)
    print()

    # 1. The tooltip templates. The mod overrides Glorp UI's own override, so
    #    whatever they put in that block is replaced wholesale by our copy —
    #    compared as text, because a parse only sees the shapes it knows.
    theirs_gui = (glorp / GLORP_HINTS_GUI).read_text(encoding="utf-8-sig")
    ours_gui = EXTRA_GUI.read_text(encoding="utf-8-sig")
    print("1. %s" % Path(GLORP_HINTS_GUI).name)
    for template, block in (
            ("SocietalValueCountryLeft_tooltip", "societal_value_left_tooltip_extra"),
            ("SocietalValueCountryRight_tooltip", "societal_value_right_tooltip_extra")):
        theirs = generate_extra.blockoverride_body(theirs_gui, template, block)
        ours = generate_extra.blockoverride_body(ours_gui, template, block)
        lists = "TooltipScrolledStringPairList"
        print("   %s: theirs %d lists, added here %d"
              % (template, theirs.count(lists), ours.count(lists) - theirs.count(lists)))
        print("   → %s" % ("their block is carried verbatim"
                           if ours.startswith(theirs)
                           else "THEIR BLOCK IS NOT CARRIED — rebuild with --game-files"))

    # 2. The hint keys, per language. Glorp UI shipped them in English only
    #    until 2026-08-28 and now ships all eleven, so what used to be this
    #    mod's whole reason for existing is now an override of their own work.
    print()
    print("2. GLORP_UI_SVH_* localization keys, per language")
    print("   %-14s %8s %8s %8s %8s" % ("", "theirs", "ours", "same", "differ"))
    for language in svx_languages.LANGUAGES:
        source = {k: v for k, v in LOC_ENTRY_RE.findall(
            glorp_hints_text(glorp, language)) if k.startswith("GLORP_UI_SVH_")}
        rendered = {k: v for k, v in LOC_ENTRY_RE.findall(
            hints_path(language).read_text(encoding="utf-8-sig"))}
        shared = [k for k in source if k in rendered]
        # A key this mod deliberately turns into a dispatch is not an accident.
        same = [k for k in shared if source[k] == rendered[k]]
        differ = [k for k in shared
                  if source[k] != rendered[k]
                  and not rendered[k].startswith("[Player.Custom(")]
        print("   %-14s %8d %8d %8d %8d"
              % (language, len(source), len(rendered), len(same), len(differ)))
        missing = [k for k in source if k not in rendered]
        dead = [k for k in rendered if k not in source and not k.startswith("SVX_")]
        if missing and language in SHIP_GLORP_HINTS:
            print("      → %d Glorp UI has and this mod has not: %s"
                  % (len(missing), ", ".join(sorted(missing)[:3])))
        if dead:
            print("      → %d this mod has and Glorp UI dropped: %s"
                  % (len(dead), ", ".join(sorted(dead)[:3])))
    print("   `same` is an override that changes nothing and pins their file;")
    print("   `differ` is this mod's wording winning over Glorp UI's own.")
    print("   Only %s ships Glorp UI's text from here; elsewhere `ours` is the"
          % ", ".join(SHIP_GLORP_HINTS))
    print("   handful of hints this mod holds back until an advance unlocks them.")

    # 3. The handful of Glorp UI interface keys repaired by hand.
    print()
    print("3. Glorp UI's own interface keys, repaired here")
    for language, fixes in sorted(svx_languages.GLORP_UI_FIXES.items()):
        defined = glorp_localization(glorp, language)
        for key, text in sorted(fixes.items()):
            if key not in defined:
                print("   → %s/%s: Glorp UI no longer defines it — drop the repair"
                      % (language, key))
            elif defined[key] == text:
                print("   → %s/%s: Glorp UI now says the same thing — drop the repair"
                      % (language, key))
            else:
                print("   %s/%s: theirs %r" % (language, key, defined[key][:60]))
    return 0


def rebuild_extra(game_files: Path) -> int:
    """Re-scan the game and rewrite the generated files, in every language."""
    # Beside the tool, not in the repository root: a crashed run used to leave
    # it where the next `git add -A` would sweep it into a commit.
    findings = TOOLS / "sv_findings.json"
    for command in (
            [sys.executable, str(TOOLS / "scan_sources.py"), str(game_files),
             "--json", str(findings)],
            [sys.executable, str(TOOLS / "generate_extra.py"),
             "--findings", str(findings), "--game-files", str(game_files),
             "--out", str(MOD)]):
        done = subprocess.run(command, capture_output=True, text=True)
        for line in (done.stdout + done.stderr).strip().splitlines():
            print("     %s" % line)
        if done.returncode != 0:
            return done.returncode
    findings.unlink(missing_ok=True)
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-files", type=Path,
                        help="unpacked EU5 game files, to rebuild the extra "
                             "hint lists; without it they are only checked")
    parser.add_argument("--check", action="store_true",
                        help="report, write nothing")
    parser.add_argument("--conflicts", action="store_true",
                        help="what this mod writes over in Glorp UI, and whether "
                             "the copy here is still theirs")
    args = parser.parse_args(argv[1:])

    glorp = refs.known("glorp_ui")

    if args.conflicts:
        return conflict_report(glorp)

    if args.game_files:
        code = rebuild_extra(args.game_files)
        if code:
            return code

    gates = unlock_gates(glorp)
    if not args.check:
        UNLOCK_GATE.parent.mkdir(parents=True, exist_ok=True)
        UNLOCK_GATE.write_text(fork_hints.rename(render_unlock_gate(gates)),
                               encoding="utf-8-sig", newline="\n")

    if not args.check:
        for language in svx_languages.GLORP_UI_FIXES:
            fixes_path(language).parent.mkdir(parents=True, exist_ok=True)
            fixes_path(language).write_text(render_fixes(language),
                                            encoding="utf-8-sig", newline="\n")

    rendered: dict[str, str] = {}
    counts: dict[str, tuple[int, int]] = {}
    gated = {key: advance for key, (_, advance) in gates.items()}
    for language in svx_languages.LANGUAGES:
        try:
            text, translated, bodies = translate_hints.render(
                glorp / GLORP_HINTS_EN, language, gated,
                only_gated=language not in SHIP_GLORP_HINTS)
            counts[language] = (translated, bodies)
        except translate_hints.Unrecognised as exc:
            print("Glorp UI writes a hint this mod cannot translate. Add the "
                  "opener to languages.py:\n  %s" % exc, file=sys.stderr)
            return 1
        text = fork_hints.rename(text)
        rendered[language] = text
        if not args.check:
            hints_path(language).parent.mkdir(parents=True, exist_ok=True)
            hints_path(language).write_text(text, encoding="utf-8-sig",
                                            newline="\n")
    if not args.check:
        for language in svx_languages.LANGUAGES:
            stale = (MOD / "main_menu/localization" / language
                     / ("glorpui_generated_societal_value_hints_l_%s.yml" % language))
            if stale.is_file():
                stale.unlink()
                print("removed %s — its keys are shipped as svx_svh_* now"
                      % stale.relative_to(MOD))
        print("wrote %d localization folders under %s"
              % (len(svx_languages.LANGUAGES),
                 (MOD / "main_menu/localization").relative_to(refs.REPO)))
    for language in SHIP_GLORP_HINTS:
        print("%s: %d of Glorp UI's hints re-translated here, %d body keys copied"
              % (language, counts[language][0], counts[language][1]))
    print("%d hints held back until the advance that unlocks the privilege: %s"
          % (len(gates),
             ", ".join(sorted({privilege for privilege, _ in gates.values()}))))
    print("%d of Glorp UI's own keys repaired, in %s"
          % (sum(len(v) for v in svx_languages.GLORP_UI_FIXES.values()),
             ", ".join(sorted(svx_languages.GLORP_UI_FIXES))))

    problems: list[str] = []
    check_gates_found_something(problems, glorp)
    check_english_is_glorp_uis_own(problems, glorp)
    check_catalog_concepts_exist(problems)
    check_languages_are_in_step(problems)
    check_triggers_exist(problems)
    check_gate_scopes(problems)
    for language in svx_languages.LANGUAGES:
        check_references_resolve(problems, glorp, language, rendered[language])
        paths = [extra_path(language), menu_path(language), hints_path(language)]
        if language in svx_languages.GLORP_UI_FIXES:
            paths.append(fixes_path(language))
        check_localization_conventions(problems, language, [
            (path, path.read_text(encoding="utf-8-sig")) for path in paths])
        check_hints_have_labels(problems, language)
    if problems:
        print()
        for problem in problems:
            print("     %s" % problem, file=sys.stderr)
        return 1

    # Counted in the text rather than by the parse, for the reason
    # `check_glorp_list_is_current` is text now: a list of a shape nobody here
    # anticipated is still a list on the player's screen.
    lists = "TooltipScrolledStringPairList"
    ours_gui = EXTRA_GUI.read_text(encoding="utf-8-sig")
    gated = len(CUSTOM_RE.findall(EXTRA_CUSTOM.read_text(encoding="utf-8-sig")))
    forked = len(CUSTOM_RE.findall(FORKED_CUSTOM.read_text(encoding="utf-8-sig")))
    print("%d tooltip lists, every name in them this mod's own or the game's"
          % ours_gui.count(lists))
    print("%d hint lines gated by a country trigger, %d takeability rules forked"
          % (gated, forked))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
