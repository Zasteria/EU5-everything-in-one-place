#!/usr/bin/env python3
"""Integration Hotfix's own changes, written onto the current game's text.

Integration Hotfix (workshop 3721516330, 0.7, game 1.3.x) is no longer on the
workshop and will not be updated.  Under game 1.4 its files do three kinds of
thing at once: what its author meant (his workshop description, read
2026-10-13), the game's 1.3 text it copied around those changes, and two
objects redeclared without a prefix.  The copied text now reverts the patch:
twelve subject types lose 1.4's call-to-arms rules, accepting a culture stops
granting its bonus advances, the Roman casus belli loses its border limit, the
annexation cost goes *up* from 50 to 75, and the integration cabinet actions
are injected with 0.5 where 1.4 already gives 1.0.

This tool takes only the author's changes and writes each one as ``REPLACE:``
of the game's current block, so a patch is picked up by a rebuild instead of
being reverted.  Every edit names its anchor and how many times it must match
in the block; a patch that moves the anchor stops the build, it does not write
a quiet no-op.

Left to the game on purpose: the integration cabinet actions (1.4's 1.0 and 1.5
are above the hotfix's 0.5 and 1.0), the annexation base cost (1.4's 50 is
below the hotfix's 75), the Roman casus belli, and every subject-type field
other than cabinet efficiency.

Usage:  python3 mods/integration_fix/tools/generate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MOD = HERE.parent
REPO = MOD.parent.parent
sys.path.insert(0, str(REPO / "tools"))

import refs  # noqa: E402

GAME = refs.GAME
PREFIX = "zz_bag_integration_fix"
HEAD = "# Written by mods/integration_fix/tools/generate.py from the game's own file. Do not edit.\n"

# The hotfix author's list: every subject type loses its cabinet-efficiency
# penalty except the state bank.  The HRE's types (hre.txt) were not in his
# list and keep theirs.
CABINET_FREE = [
    "fiefdom", "dominion", "appanage", "uc_bey", "vassal", "samanta",
    "maha_samanta", "pradhana_maha_samanta", "hanseatic_member", "march", "tusi",
]
CABINET = re.compile(r"[ \t]*country_cabinet_efficiency\s*=\s*-?[\d.]+[ \t]*\n?")

# (game file, key, [(pattern, replacement, times)])
EDITS = [
    # «Integrated»: +15% max control, +0.05% monthly control, no assimilation penalty.
    ("main_menu/common/static_modifiers/integration.txt", "integration_integrated", [
        (r"\n\t*local_pop_assimilation_speed = -0\.01[ \t]*", "", 1),
        (r"local_max_control = 0\.05", "local_max_control = 0.15\n\tlocal_monthly_control = 0.0005", 1),
    ]),
    # Natural integration speed of a province.
    ("main_menu/common/static_modifiers/province.txt", "province_base", [
        (r"province_integration_speed = 0\.1\b", "province_integration_speed = 0.5", 1),
    ]),
    # Subjects: no -50% assimilation and conversion.
    ("main_menu/common/static_modifiers/country.txt", "is_subject", [
        (r"\n\t*global_pop_assimilation_speed_modifier = -0\.5[ \t]*", "", 1),
        (r"\n\t*global_pop_conversion_speed_modifier = -0\.5[ \t]*", "", 1),
    ]),
    # No crown-power penalty from the subjects' population.
    ("main_menu/common/static_modifiers/country.txt", "relative_subject_power", [
        (r"crown_power_from_population = -0\.5", "crown_power_from_population = 0", 1),
    ]),
    # Any culture present in the country can be accepted or tolerated.
    ("in_game/common/generic_actions/culture.txt", "add_accepted_culture", [
        (r"value >= 0\.025", "value >= 0", 1),
        (r"value >= 1000", "value >= 0", 1),
    ]),
    ("in_game/common/generic_actions/culture.txt", "add_tolerated_culture", [
        (r"value >= 0\.01\b", "value >= 0", 1),
        (r"value >= 1000", "value >= 0", 1),
    ]),
    # Forcing a subject's religion or culture: no shared ten-year cooldown and
    # no wait after it became a subject.
    ("in_game/common/country_interactions/enforce_religion.txt", "enforce_religion", [
        (r"\tcooldown = \{[^{}]*\}[ \t]*\n", "", 1),
        (r"[ \t]*dependency_length_days = \{[^{}]*\}[ \t]*\n", "", 1),
    ]),
    ("in_game/common/country_interactions/enforce_culture.txt", "enforce_culture", [
        (r"\tcooldown = \{[^{}]*\}[ \t]*\n", "", 1),
        (r"[ \t]*dependency_length_days = \{[^{}]*\}[ \t]*\n", "", 1),
    ]),
    # Byzantium's Latinitas / Rhomanismos value, as the hotfix has it; the
    # selling bonus stays the game's (1.4 renamed it and raised it to 5%).
    ("in_game/common/societal_values/00_default.txt", "latinization_vs_hellenization", [
        (r"[ \t]*monthly_towards_(humanist|innovative|spiritualist|traditionalist) = societal_value_monthly_move[ \t]*\n", "", 4),
        (r"allow_roman_movement = yes", "allow_roman_movement = yes\n\t\ttolerance_heretic = 2.0\n\t\ttolerance_heathen = 1.0", 1),
        (r"tolerance_own = 0\.5", "tolerance_own = 5.0\n\t\ttax_income_efficiency = 0.1\n\t\tcultures_capacity_modifier = 0.2", 1),
    ]),
]

DEFINES = """\
# Truces after a peace: 3 years plus up to 7 by the size of the peace (game: 5 and 10).
NDiplomacy = {
\tTRUCE_YEARS = 3
\tSCALED_TRUCE_YEARS = 7
}
"""

AUTO_KEY = "bag_integration_fix_annexation_from_influence"
AUTO = f"""\
# +100% annexation speed per 1 000 cultural influence of the primary culture, up to +1000%.
{AUTO_KEY} = {{
\tpotential_trigger = {{
\t\tculture.cultural_influence > 0
\t}}
\tscales_with = {{
\t\tvalue = culture.cultural_influence
\t\tmultiply = 0.001
\t\tmax = 10.0
\t}}
\tannexation_speed_modifier = 1
}}
"""
LOC = {
    "english": "Annexation speed from cultural influence",
    "russian": "Скорость аннексии от культурного влияния",
}


class Stop(Exception):
    pass


def block(text: str, key: str, where: str) -> str:
    """The top-level ``key = { ... }`` block, braces counted outside comments."""
    m = list(re.finditer(rf"^{re.escape(key)}\s*=\s*\{{", text, re.M))
    if len(m) != 1:
        raise Stop(f"{where}: `{key}` found {len(m)} times at top level, expected 1")
    i, depth, quoted = m[0].end() - 1, 0, False
    while i < len(text):
        ch = text[i]
        if ch == '"':
            quoted = not quoted
        elif ch == "#" and not quoted:
            i = text.index("\n", i) if "\n" in text[i:] else len(text)
            continue
        elif ch == "{" and not quoted:
            depth += 1
        elif ch == "}" and not quoted:
            depth -= 1
            if depth == 0:
                return text[m[0].start(): i + 1]
        i += 1
    raise Stop(f"{where}: `{key}` never closes")


def read(rel: str) -> str:
    return (GAME / rel).read_text(encoding="utf-8-sig")


def edit(body: str, edits, where: str) -> str:
    for pattern, repl, times in edits:
        body, n = re.subn(pattern, repl, body)
        if n != times:
            raise Stop(f"{where}: `{pattern}` matched {n} times, expected {times}")
    return body


def replaced(body: str) -> str:
    return "REPLACE:" + body


def build() -> dict[Path, str]:
    out: dict[Path, str] = {}
    files: dict[str, list[str]] = {}
    for rel, key, edits in EDITS:
        where = f"{rel}:{key}"
        body = edit(block(read(rel), key, rel), edits, where)
        target = str(Path(rel).parent / f"{PREFIX}_{Path(rel).stem}.txt")
        files.setdefault(target, []).append(f"# from {rel}\n" + replaced(body))

    folder = "in_game/common/subject_types"
    for path in sorted((GAME / folder).glob("*.txt")):
        text = path.read_text(encoding="utf-8-sig")
        for key in CABINET_FREE:
            if not re.search(rf"^{key}\s*=\s*\{{", text, re.M):
                continue
            body = block(text, key, path.name)
            body, n = CABINET.subn("", body)
            if n != 1:
                raise Stop(f"{folder}/{path.name}:{key}: cabinet efficiency {n} times, expected 1")
            body = body.replace("subject_modifier = { }", "subject_modifier = {}")
            files.setdefault(f"{folder}/{PREFIX}_subject_types.txt", []).append(
                f"# from {folder}/{path.name}\n" + replaced(body))
            CABINET_FREE_SEEN.add(key)
    missing = [k for k in CABINET_FREE if k not in CABINET_FREE_SEEN]
    if missing:
        raise Stop(f"{folder}: no subject type named {', '.join(missing)}")

    for target, blocks in files.items():
        out[MOD / target] = HEAD + "\n\n".join(blocks) + "\n"
    out[MOD / f"loading_screen/common/defines/{PREFIX}_defines.txt"] = HEAD + DEFINES
    out[MOD / f"in_game/common/auto_modifiers/{PREFIX}_annexation.txt"] = HEAD + AUTO
    for lang, text in LOC.items():
        out[MOD / f"main_menu/localization/{lang}/{PREFIX}_l_{lang}.yml"] = (
            f'l_{lang}:\n AUTO_MODIFIER_NAME_{AUTO_KEY}: "{text}"\n')
    return out


CABINET_FREE_SEEN: set[str] = set()


def main() -> int:
    try:
        files = build()
    except Stop as e:
        print(f"integration_fix: STOP — {e}", file=sys.stderr)
        return 1
    for part in ("in_game", "main_menu", "loading_screen"):
        for old in (MOD / part).rglob("*") if (MOD / part).exists() else []:
            if old.is_file() and old not in files:
                old.unlink()
    changed = 0
    for path, text in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = "\ufeff" + text  # every file: without it the game reads the first key as part of it
        if not path.exists() or path.read_text(encoding="utf-8") != data:
            path.write_text(data, encoding="utf-8", newline="\n")
            changed += 1
    print(f"integration_fix: {len(files)} files, {changed} rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())
