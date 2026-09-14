#!/usr/bin/env python3
"""Generate the "extra societal value hints" add-on mod for Glorp UI.

Glorp UI's generated hints cover three source types - government reforms,
laws/policies and estate privileges. The game pushes societal values from far
more than that: employment systems, buildings, religious aspects, parliament
issues, cabinet actions, and modifiers that are either scaled by some country
state (fort maintenance, army size, average control) or switched on by a
condition (bankruptcy, being at war, exceeding the fort limit).

Entries whose availability can be checked with a trigger form that appears
verbatim in the shipped game files are wrapped in customizable localization, so
hints for other religions, estates or subject types drop out. The rest are
emitted as plain text - see mods/glorpui_hints/tools/gates.py for why nothing is guessed.

**A hint line is collected as data and only turned into words at the end**, once
per language. The `.gui`, the customizable localization and the script values
carry no words at all and are written once; the eleven `.yml` files differ only
in the openers held in `languages.py`. That is what makes eleven languages cost
about fifty strings rather than eleven thousand.

Inputs:
  - the scan produced by mods/glorpui_hints/tools/scan_sources.py
  - the extracted game files, for axis pairs and availability blocks

Usage:
    python3 mods/glorpui_hints/tools/generate_extra.py \
        --findings sv_findings.json --game-files <game-files> --out glorpui_svh_extra
"""

import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "tools"))

import gates as svx_gates
import languages as svx_languages
import refs  # noqa: E402  the reference tree, resolved by mod id

# Glorp UI's own version of the two templates this mod overrides.
GLORP_HINTS_GUI = "in_game/gui/glorpUI_generated_societal_value_hints.gui"


def blockoverride_body(text, template, block):
    """The raw text inside `template <name> { ... blockoverride "<block>" { ... } }`.

    Taken verbatim rather than parsed, because this mod replaces that block
    wholesale and anything it fails to carry across is a piece of Glorp UI the
    player stops getting. Glorp UI's 2026-08-28 build put one entry in there
    that no parse here recognised - vanilla's own C++ hint blob behind their
    `showUnavailableSocietalValueSuggestions` setting, which has neither a
    `ScriptValue` nor a `Localize` - and the whole setting silently did nothing
    for anyone running both mods. Copying the bytes cannot make that mistake.

    Braces are matched with quoted strings and comments skipped; the file has
    none inside a string today, and this does not depend on that staying true.
    """
    start = re.search(r"^template %s \{" % re.escape(template), text, re.M)
    if not start:
        raise SystemExit("%s: no template %s" % (GLORP_HINTS_GUI, template))
    opener = re.compile(r'blockoverride "%s"\s*\{' % re.escape(block))
    found = opener.search(text, start.end())
    if not found:
        raise SystemExit("%s: template %s has no blockoverride %r"
                         % (GLORP_HINTS_GUI, template, block))
    depth = 0
    index = found.end() - 1
    while index < len(text):
        char = text[index]
        if char == '"':
            index = text.find('"', index + 1)
            if index < 0:
                break
        elif char == "#":
            index = text.find("\n", index)
            if index < 0:
                break
            continue
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[found.end():index].strip("\n").rstrip()
        index += 1
    raise SystemExit("%s: blockoverride %r does not close" % (GLORP_HINTS_GUI, block))

# Only one of these can be in force at a time, so a weaker one is pointless
# while a stronger one is already active.
EXCLUSIVE_SOURCES = {"employment_systems"}

# Where the object definitions live, for the availability gates.
SOURCE_DIRS = {
    "building_types": "in_game/common/building_types",
    "missions": "in_game/common/missions",
    "parliament_types": "in_game/common/parliament_types",
    "cabinet_actions": "in_game/common/cabinet_actions",
    "religious_aspects": "in_game/common/religious_aspects",
    "religious_schools": "in_game/common/religious_schools",
    "estates": "in_game/common/estates",
    "subject_types": "in_game/common/subject_types",
    "chivalric_orders": "in_game/common/chivalric_orders",
    "parliament_issues": "in_game/common/parliament_issues",
}

# What each of the four kinds of line is called, and where its words come from,
# is in languages.py: `CATALOG_CONCEPTS` and `CATALOG_REGISTRIES` for the
# catalogue lines, `scaled` and `conditional` for the two modifier kinds. Which
# modifier is scaled and which is conditional is the same question in every
# language, so the two key lists live there too and are read here.
SCALED_KEYS = set(svx_languages.SCALED_KEYS)
CONDITIONAL_KEYS = set(svx_languages.CONDITIONAL_KEYS)

CABINET_SUFFIX = "_progress_cabinet_efficiency"

STEPS = {
    "societal_value_min_scaling_monthly_move": 0.01,
    "societal_value_tiny_monthly_move": 0.025,
    "societal_value_minor_monthly_move": 0.05,
    "societal_value_monthly_move": 0.1,
    "societal_value_large_monthly_move": 0.2,
    "societal_value_significant_monthly_move": 0.33,
    "societal_value_huge_monthly_move": 0.5,
}

HEADER = ("# Auto-generated by mods/glorpui_hints/tools/generate_extra.py from the EU5 game "
          "files. Do not edit by hand.")


def axis_pairs(path):
    pairs = []
    with open(path, encoding="utf-8-sig") as handle:
        for line in handle:
            match = re.match(r'^([a-z_]+)_vs_([a-z_]+)\s*=\s*\{', line.strip())
            if match:
                pairs.append((match.group(1), match.group(2),
                              "%s_vs_%s" % (match.group(1), match.group(2))))
    return pairs


def amount(raw):
    if raw in STEPS:
        return STEPS[raw]
    try:
        return float(raw)
    except ValueError:
        return None


def line_text(entry, phrases):
    """One hint line, in one language.

    The entry itself holds no words - only which kind of line it is, which
    object it is about and how hard it pushes. Everything a player reads comes
    out of `phrases`, which is one language's table from languages.py.
    """
    kind = entry["kind"]
    if kind == "catalog":
        source_type, obj = entry["source_type"], entry["object"]
        reference = "#TOOLTIP:%s,%s #L $%s$#!#!" % (
            svx_languages.CATALOG_REGISTRIES[source_type], obj, obj)
        concept = svx_languages.CATALOG_CONCEPTS.get(source_type)
        if concept is None:
            # building_types: the push is a `capital_country_modifier`, so the
            # line has to say build it *in the capital* and no game concept
            # says that.
            label = "%s %s" % (phrases["build_in_capital"], reference)
        else:
            label = phrases["catalog"].format(concept=concept, ref=reference)
        return "@hint! %s: #color_green +%.2f#!\\n" % (label, entry["value"])
    if kind == "scaled":
        return "@hint! %s #help (%s)#!: #color_green %s+%.2f#!\\n" % (
            phrases["scaled"][entry["object"]], phrases["scales"],
            phrases["up_to"], entry["value"])
    if kind == "conditional":
        return "@hint! %s: #color_green +%.2f#!\\n" % (
            phrases["conditional"][entry["object"]], entry["value"])
    if kind == "cabinet":
        return "@hint! %s #help (%s)#!\\n" % (
            phrases["cabinet"], phrases["cabinet_scales"])
    raise AssertionError("unknown line kind %r" % kind)


def collect(findings, game_files):
    """direction -> ordered list of entry dicts, with no words in any of them."""
    caches = {}
    for source_type, relative in SOURCE_DIRS.items():
        caches[source_type] = svx_gates.scan_objects(game_files, relative)
    # Which organization grants each special status, read from the
    # organizations rather than from the statuses. See gates.status_owners.
    extra = {"status_owners": svx_gates.status_owners(game_files)}

    entries = collections.defaultdict(list)
    for row in findings:
        axis, obj, raw = row["axis"], row["object"], row["raw_value"]
        source_type = row["source_type"]
        value = amount(raw)
        if value is None:
            continue

        if source_type in svx_languages.CATALOG_REGISTRIES:
            gate = svx_gates.gate_for(source_type, obj, caches.get(source_type, {}), extra)
            if source_type in EXCLUSIVE_SOURCES:
                # Suppress once the country holds this one, or any peer that
                # already pushes this axis at least as hard.
                peers = sorted(
                    other["object"] for other in findings
                    if other["source_type"] == source_type
                    and other["axis"] == axis
                    and (amount(other["raw_value"]) or 0) >= value)
                gate = {
                    "reach": list(gate["reach"]),
                    "now": list(gate["now"]) + [
                        "NOT = { has_employment_system = employment_system:%s }" % peer
                        for peer in dict.fromkeys(peers)],
                }
            entries[axis].append({"sort": (-value, obj), "kind": "catalog",
                                  "source_type": source_type, "object": obj,
                                  "value": value, "gate": gate})
        elif obj in SCALED_KEYS:
            entries[axis].append({"sort": (-value, obj), "kind": "scaled",
                                  "object": obj, "value": value,
                                  "gate": {"reach": [], "now": []}})
        elif obj in CONDITIONAL_KEYS:
            entries[axis].append({"sort": (-value, obj), "kind": "conditional",
                                  "object": obj, "value": value,
                                  "gate": {"reach": [], "now": []}})
        elif obj.endswith(CABINET_SUFFIX):
            entries[axis].append({"sort": (-99, obj), "kind": "cabinet",
                                  "object": obj, "value": value,
                                  "gate": {"reach": [], "now": []}})

    ordered = {}
    for axis, rows in entries.items():
        seen, out = set(), []
        for row in sorted(rows, key=lambda r: r["sort"]):
            # Two findings that would print the same line - the same object
            # pushing the same axis twice - collapse into one. Compared on what
            # the line is *about* rather than on its text, so the answer cannot
            # depend on which language is being written.
            identity = (row["kind"], row.get("source_type"), row["object"],
                        row["value"])
            if identity in seen:
                continue
            seen.add(identity)
            out.append(row)
        ordered[axis] = out
    return ordered


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="\n") as handle:
        handle.write(text)


def localization(language, pairs, entries, gate_keys):
    """One language's `svx_extra_hints_l_<language>.yml`.

    `gate_keys` is the (direction, index) -> localization key mapping worked out
    once by `main`, so every language prints the same key for the same gate and
    the single customizable localization file serves all eleven.
    """
    phrases = svx_languages.PHRASES[language]
    out = [HEADER, "l_%s:" % language]
    for key, text in phrases["titles"].items():
        out.append(' %s: "%s"' % (key, text))
    for left, right, _ in pairs:
        for direction in (left, right):
            now_body, soon_body = [], []
            for index, row in enumerate(entries.get(direction, [])):
                text = line_text(row, phrases)
                if not row["gate"]["now"]:
                    now_body.append(text)
                    continue
                now_key = gate_keys[("n", direction, index)]
                out.append(' %s: "%s"' % (now_key, text))
                now_body.append("[Player.Custom('%s')]" % now_key.lower())
                soon_key = gate_keys.get(("s", direction, index))
                if soon_key:
                    out.append(' %s: "%s"' % (soon_key, text))
                    soon_body.append("[Player.Custom('%s')]" % soon_key.lower())
            out.append(' SVX_BODY_%s: "%s"' % (direction.upper(), "".join(now_body)))
            out.append(' SVX_SOON_%s: "%s"' % (direction.upper(), "".join(soon_body)))
            # The unfiltered pool, for the mod menu switch: every line this
            # direction has, with no trigger in front of any of it. It is a
            # third body key rather than a mode the gates understand, because a
            # customizable localization cannot be told to ignore its own
            # trigger - and because a plain string cannot fail.
            out.append(' SVX_ALL_%s: "%s"' % (
                direction.upper(),
                "".join(line_text(row, phrases)
                        for row in entries.get(direction, []))))
    return "\n".join(out) + "\n"


def menu(language):
    """The CMF mod menu entry. CMM derives every key from the mod and setting id."""
    phrases = svx_languages.PHRASES[language]
    out = [HEADER,
           "# CMM derives every key below from the mod id and the setting id,",
           "# and a key it cannot find shows as the raw key on screen.",
           "l_%s:" % language]
    for key, text in phrases["menu"].items():
        out.append(' %s: "%s"' % (key, text))
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings", required=True)
    parser.add_argument("--game-files", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    with open(args.findings, encoding="utf-8") as handle:
        findings = json.load(handle)
    pairs = axis_pairs(os.path.join(
        args.game_files, "in_game/common/societal_values/00_default.txt"))
    entries = collect(findings, args.game_files)

    custom = [HEADER, ""]
    gate_keys = {}
    soon_gates = collections.defaultdict(list)
    counts = {"now": 0, "soon": 0}

    def emit(name, trigger_lines):
        custom.append("%s = {" % name)
        custom.append("\ttype = country")
        custom.append("\ttext = {")
        custom.append("\t\ttrigger = {")
        for line in trigger_lines:
            custom.append("\t\t\t%s" % line)
        custom.append("\t\t}")
        custom.append("\t\tlocalization_key = %s" % name.upper())
        custom.append("\t}")
        custom.append("\ttext = {")
        custom.append("\t\tlocalization_key = empty_text")
        custom.append("\t}")
        custom.append("}")
        custom.append("")

    # The gates first, because they are the same in every language: a trigger
    # has no words in it, and the localization key it points at is a name.
    for left, right, _ in pairs:
        for direction in (left, right):
            for index, row in enumerate(entries.get(direction, [])):
                gate = row["gate"]
                if not gate["now"]:
                    continue
                name = "svx_n_%s_%03d" % (direction, index)
                emit(name, gate["now"])
                gate_keys[("n", direction, index)] = name.upper()
                counts["now"] += 1

                # Attainable-but-not-yet needs a real "reach" condition to be
                # about. Without one, failing "now" does not mean "later" - a
                # mutually exclusive option displaced by a better one is simply
                # out, not pending.
                if not gate["reach"] or gate["now"] == gate["reach"]:
                    continue
                soon = list(gate["reach"]) + [
                    "NOT = { AND = { %s } }" % " ".join(gate["now"])]
                name = "svx_s_%s_%03d" % (direction, index)
                emit(name, soon)
                gate_keys[("s", direction, index)] = name.upper()
                soon_gates[direction].append(soon)
                counts["soon"] += 1

    for language in svx_languages.LANGUAGES:
        write(os.path.join(args.out, "main_menu/localization/%s/svx_extra_hints_l_%s.yml"
                           % (language, language)),
              localization(language, pairs, entries, gate_keys))
        write(os.path.join(args.out, "main_menu/localization/%s/svx_menu_l_%s.yml"
                           % (language, language)),
              menu(language))

    write(os.path.join(args.out,
                       "in_game/common/customizable_localization/svx_extra_hint_loc.txt"),
          "\n".join(custom))

    values = [HEADER, ""]
    for left, right, pair in pairs:
        values += ["svx_axis_%s = {" % pair,
                   "\tvalue = 0",
                   "\tif = {",
                   "\t\tlimit = { scope:glorpui_sv = societal_value_type:%s }" % pair,
                   "\t\tadd = 1",
                   "\t}",
                   "}",
                   ""]
        for direction in (left, right):
            gates = soon_gates.get(direction, [])
            values.append("svx_soon_visible_%s = {" % direction)
            values.append("\tvalue = 0")
            if gates:
                values.append("\tif = {")
                values.append("\t\tlimit = {")
                values.append("\t\t\tscope:glorpui_sv = societal_value_type:%s" % pair)
                values.append("\t\t\tscope:glorpui_country = {")
                values.append("\t\t\t\tOR = {")
                for gate in gates:
                    values.append("\t\t\t\t\tAND = { %s }" % " ".join(gate))
                values.append("\t\t\t\t}")
                values.append("\t\t\t}")
                values.append("\t\t}")
                values.append("\t\tadd = 1")
                values.append("\t}")
            values += ["}", ""]
    write(os.path.join(args.out,
                       "in_game/common/script_values/svx_extra_hint_script_values.txt"),
          "\n".join(values))


    def scroll_list(visible_value, title, body_key, switch=None):
        live = ("GreaterThan_CFixedPoint(GuiScope"
                ".AddScope('glorpui_sv', SocietalValue.MakeScope)"
                ".AddScope('glorpui_country', Player.MakeScope)"
                ".ScriptValue('%s'), '(CFixedPoint)0')" % visible_value)
        if switch == "on":
            live = "And(%s, %s)" % (live, show_all)
        elif switch == "off":
            live = "And(%s, Not(%s))" % (live, show_all)
        return "\n".join([
            "\t\tTooltipScrolledStringPairList = {",
            "\t\t\tvisible = \"[%s]\"" % live,
            "\t\t\tblockoverride \"block_scrollarea\" {",
            "\t\t\t\tmaximumsize = { -1 160 }",
            "\t\t\t}",
            "",
            "\t\t\tblockoverride \"block_title\" {",
            "\t\t\t\ttext = \"%s\"" % title,
            "\t\t\t\tdefault_format = \"#help\"",
            "\t\t\t}",
            "",
            "\t\t\ttextcontext = \"[Localize('%s')]\"" % body_key,
            "\t\t}",
            "",
        ])

    def vanilla_hint(side):
        """The game's own hint list, shown when Glorp UI is not in the playset.

        Vanilla prints `SocietalValue.GetLeftHint(Player.Self)` under
        `TO_MOVE_FURTHER_TO_LEFT` unconditionally. Glorp UI's block, which this
        mod splices in above, replaces that with the same list behind their
        `showUnavailableSocietalValueSuggestions` variable - and **nobody sets
        that variable when Glorp UI is gone**, so the whole block goes dark and
        the player is left with this mod's own two lists and no main list at
        all. Seen in game 2026-09-14.

        So the same list is emitted once more here, gated on Glorp UI *not*
        having registered with the mod menu. The two gates cannot both be true:
        theirs needs their window to set the variable, which needs their mod.
        Before CMF has run its registration the answer is "not registered" and
        this shows - which is vanilla's own behaviour, and the safe way round.

        `glorpui__showUnavailableSocietalValueSuggestions` is a bool setting
        Glorp UI registers with CMM (`glorpui_cmm_effects.txt`), and
        `CMMSettingIsRegistered` is CMF's own generic macro over a setting key -
        CMF asks it about `cmf_core__action_bar_position` the same way.
        """
        return "\n".join([
            "\t\tTooltipScrolledStringPairList = {",
            "\t\t\tvisible = \"[Not(CMMSettingIsRegistered("
            "'glorpui__showUnavailableSocietalValueSuggestions'))]\"",
            "\t\t\tblockoverride \"block_scrollarea\" {",
            "\t\t\t\tmaximumsize = { -1 160 }",
            "\t\t\t}",
            "",
            "\t\t\tblockoverride \"block_title\" {",
            "\t\t\t\ttext = \"TO_MOVE_FURTHER_TO_%s\"" % side.upper(),
            "\t\t\t\tdefault_format = \"#help\"",
            "\t\t\t}",
            "",
            "\t\t\ttextcontext = \"[SocietalValue.Get%sHint(Player.Self)]\"" % side,
            "\t\t}",
            "",
        ])

    glorp_gui = (refs.known("glorp_ui") / GLORP_HINTS_GUI).read_text(
        encoding="utf-8-sig")

    gui = [HEADER,
           "# Overrides Glorp UI's own override, so this mod must load AFTER Glorp UI.",
           "# Glorp UI's own block is copied in first, byte for byte, and this mod's",
           "# lists are added after it. Verbatim rather than re-emitted: whatever",
           "# Glorp UI puts in that block is theirs to decide, and anything a parse",
           "# here failed to recognise would be a piece of their mod the player",
           "# stops getting -- which is exactly what their 2026-08-28 build cost.",
           ""]
    # True while the mod menu switch is on. `CMMSettingIsRegistered` guards the
    # case CMF describes: the setting is read before registration has run, or
    # the mod menu is not there at all - in which case the answer is "off" and
    # the filtered lists show, which is the behaviour without a switch.
    show_all = ("And(CMMSettingIsRegistered('svx__show_all'),"
                "CMMValueEqualsOne(CMMSettingValue('svx__show_all')))")

    for side, index, block_name in (
            ("Left", 0, "societal_value_left_tooltip_extra"),
            ("Right", 1, "societal_value_right_tooltip_extra")):
        template = "SocietalValueCountry%s_tooltip" % side
        gui.append("template %s {" % template)
        gui.append("\tusing = SocietalValue%s_tooltip" % side)
        gui.append("\tblockoverride \"%s\" {" % block_name)
        gui.append(blockoverride_body(glorp_gui, template, block_name))
        gui.append("")
        gui.append("\t\t# --- everything below is this mod's ---")
        gui.append("")
        gui.append("\t\t# The game's own list, for a playset without Glorp UI.")
        gui.append(vanilla_hint(side))
        for parts in pairs:
            direction = parts[index]
            gui.append(scroll_list("svx_axis_%s" % parts[2], "SVX_ALSO_PUSHES",
                                   "SVX_BODY_%s" % direction.upper(), switch="off"))
            gui.append(scroll_list("svx_soon_visible_%s" % direction, "SVX_REACHABLE",
                                   "SVX_SOON_%s" % direction.upper(), switch="off"))
            gui.append(scroll_list("svx_axis_%s" % parts[2], "SVX_EVERYTHING",
                                   "SVX_ALL_%s" % direction.upper(), switch="on"))
        gui += ["\t}", "}", ""]
    write(os.path.join(args.out, "in_game/gui/svx_extra_societal_value_hints.gui"),
          "\n".join(gui))

    total = sum(len(v) for v in entries.values())
    print("%d hint lines: %d gated as available now, %d also listed as attainable"
          % (total, counts["now"], counts["soon"]))
    print("%d languages written" % len(svx_languages.LANGUAGES))


if __name__ == "__main__":
    main()
