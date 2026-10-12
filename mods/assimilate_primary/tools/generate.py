#!/usr/bin/env python3
"""Builds `assimilate_primary`: cabinet automation assimilates a province into
the primary culture unless an accepted culture already leads it there.

The beta of 01.10 opened accepted cultures to `promote_culture` and dropped the
1.3 penalty `-1000 "Wrong culture"` from its `ai_will_do`. What is left scores
`1 - share of the target culture in the province`, so of two allowed cultures
the one with the *smaller* share wins: Torda, 05.10, Moldovan 3 % chosen over
the primary Wallachian 15 % (`docs/research/vanilla.md`).

His rule, 05.10: an accepted culture is a fair target where it already leads
the primary one by about 30 points; anywhere else, assimilate into the primary.

0.1.0 put the 1.3 penalty back into `ai_will_do`, and in his run
(05.10) no advisor assimilated anything at all; the logs hold no error for
the file. Why is not measured. 0.2.0 scores nothing negative: the rule moves
into the province's `enabled`, the same place the game itself narrows the
choice for the AI, and only while cabinet actions are automated, so a choice
made by hand stays free. 0.2.1, his ask 05.10: computer countries must not be
touched at all, so the rule also requires `is_ai = no`; 0.1.0's penalty had
applied to every country.

0.3.0, his run 05.10 08:09: every seat stopped getting new actions, with or
without this mod. A probe (in CM, now removed at his word) read «Совет»
(`cabinet`) and «Члены совета» (`cabinetmembers`) on and «Действия совета»
(`cabinetactions`) off, every month; the 1.4 panel has no switch for the last.
What turned it off is not known. 0.3.0 switched `cabinetactions` back on every
month. 0.4.0, his word 12.10: no monthly switch; he doubts the switch is a real
player setting at all («возможно только у ботов») and wants to see what it does.
So a checkbox on the mod's CMF page sets it when clicked and writes the state it
found and the state it left in debug.log. Technical switches belong in CMF, not
in game windows such as decisions (his word 12.10).

    python3 mods/assimilate_primary/tools/generate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/assimilate_primary"
SOURCE = "in_game/common/cabinet_actions/promote_culture.txt"
OUT = MOD / SOURCE
LEAD = 0.3

HEAD = """# assimilate_primary: the game's promote_culture.txt, copied whole, with one
# more condition in the province's `enabled`. Rebuilt from the game by
# tools/generate.py.
"""

RULE = """\t\t\t# assimilate_primary: for a player whose cabinet is automated, an accepted
\t\t\t# culture only where it already leads the primary culture in this province
\t\t\t# by %d points (the 1.3 rule was -1000 for any culture but the primary).
\t\t\t# Computer countries are not touched.
\t\t\ttrigger_if = {
\t\t\t\tlimit = {
\t\t\t\t\tscope:actor = {
\t\t\t\t\t\tis_ai = no
\t\t\t\t\t\tOR = {
\t\t\t\t\t\t\tis_system_automated = cabinetactions
\t\t\t\t\t\t\tis_system_automated = cabinet
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t\tNOT = { scope:target = scope:actor.culture }
\t\t\t\t}
\t\t\t\t"culture_percentage(scope:target)" >= {
\t\t\t\t\tvalue = "culture_percentage(scope:actor.culture)"
\t\t\t\t\tadd = %s
\t\t\t\t}
\t\t\t}
""" % (round(LEAD * 100), LEAD)


COUNCIL = MOD / "in_game/common/on_action/assimilate_primary_council_on_actions.txt"
DECISIONS = MOD / "in_game/common/decisions/assimilate_primary_decisions.txt"
CMF_EFFECTS = MOD / "in_game/common/scripted_effects/bag_asp_cmm_effects.txt"
CMF_EFFECTS_TEXT = """# assimilate_primary: the mod's CMF page. One checkbox sets the council's
# «Действия совета» automation (cabinetactions) when clicked, to see what it
# does. After any change here:
# python3 tools/check_cmm.py mods/assimilate_primary/in_game/common
# Rebuilt by tools/generate.py.

# Scope: country
bag_asp_register = {
\tcmm_register_bool_setting = {
\t\tmod_id = bag_asp
\t\tsetting_id = cabinetactions
\t\ttab_id = main
\t\tgroup_id = council
\t\tdefault_value = 0
\t}
}

# Scope: country. var:cmf_callback names what was clicked; switch as in
# war_sliders.
bag_asp_handle_callback = {
\tswitch = {
\t\ttrigger = var:cmf_callback
\t\tflag:bag_asp__cabinetactions = {
\t\t\tif = {
\t\t\t\tlimit = { is_system_automated = cabinetactions }
\t\t\t\tdebug_log = "assimilate_primary: cabinetactions was on before the click"
\t\t\t}
\t\t\telse = {
\t\t\t\tdebug_log = "assimilate_primary: cabinetactions was off before the click"
\t\t\t}
\t\t\tcmm_sync_bool_alias = {
\t\t\t\tsetting = bag_asp__cabinetactions
\t\t\t\talias = bag_asp_cabinetactions_on
\t\t\t}
\t\t\tif = {
\t\t\t\tlimit = { has_variable = bag_asp_cabinetactions_on }
\t\t\t\tset_automated_system = { system = cabinetactions activate = yes }
\t\t\t}
\t\t\telse = {
\t\t\t\tset_automated_system = { system = cabinetactions activate = no }
\t\t\t}
\t\t\tif = {
\t\t\t\tlimit = { is_system_automated = cabinetactions }
\t\t\t\tdebug_log = "assimilate_primary: cabinetactions is on after the click"
\t\t\t}
\t\t\telse = {
\t\t\t\tdebug_log = "assimilate_primary: cabinetactions is off after the click"
\t\t\t}
\t\t}
\t}
}
"""

CMF_ON_ACTIONS = MOD / "in_game/common/on_action/bag_asp_cmf_on_actions.txt"
CMF_ON_ACTIONS_TEXT = """# assimilate_primary: the CMF page and its checkbox. The engine merges
# on_actions lists, so these add to CMF's own. Rebuilt by tools/generate.py.
cmf_on_mod_registration = {
\ton_actions = {
\t\tbag_asp_on_register
\t}
}

cmf_on_callback = {
\ton_actions = {
\t\tbag_asp_on_callback
\t}
}

# Scope: country
bag_asp_on_register = {
\teffect = {
\t\tbag_asp_register = yes
\t}
}

# Scope: country
bag_asp_on_callback = {
\teffect = {
\t\tbag_asp_handle_callback = yes
\t}
}
"""

LOC = {
    "english": {
        "bag_asp_name": "Assimilate Into Primary Culture",
        "bag_asp_desc": "Cabinet automation assimilates into the primary culture.",
        "bag_asp__main_name": "Council",
        "bag_asp__main__council_name": "Automation",
        "bag_asp__cabinetactions_name": "Automate cabinet actions (cabinetactions)",
        "bag_asp__cabinetactions_desc": "Sets the game's cabinetactions automation switch when clicked. What it was before and after goes to debug.log.",
    },
    "russian": {
        "bag_asp_name": "Ассимиляция в основную культуру",
        "bag_asp_desc": "Автоматика совета ассимилирует в основную культуру.",
        "bag_asp__main_name": "Совет",
        "bag_asp__main__council_name": "Автоматика",
        "bag_asp__cabinetactions_name": "Автоматика действий совета (cabinetactions)",
        "bag_asp__cabinetactions_desc": "При нажатии ставит игровой переключатель автоматики cabinetactions. Каким он был до и стал после, пишется в debug.log.",
    },
}


def loc_text(language: str) -> str:
    rows = "".join(f' {k}: "{v}"\n' for k, v in LOC[language].items())
    return f"l_{language}:\n{rows}"


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8-sig") if path.exists() else None
    if old != text:
        path.write_text(text, encoding="utf-8-sig")
        print(f"{path.relative_to(refs.REPO)}: rebuilt")
    else:
        print(f"{path.relative_to(refs.REPO)}: unchanged")


def block_end(text: str, start: int) -> int:
    """Index of the brace closing the block whose `{` is the first after start."""
    depth, i = 0, text.index("{", start)
    while True:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1


def main() -> None:
    text = (refs.GAME / SOURCE).read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if "Wrong culture" in text:
        raise SystemExit("promote_culture: the game has its own culture penalty again — "
                         "this mod may no longer be needed; read the file before rebuilding")
    province = text.find("looking_for_a = province")
    if province < 0:
        raise SystemExit("promote_culture: no province selection in the game's file")
    trigger_end = block_end(text, text.rindex("select_trigger = {", 0, province))
    enabled = text.find("\t\tenabled = {", province, trigger_end)
    if enabled < 0:
        raise SystemExit("promote_culture: the province selection has no `enabled`")
    end = block_end(text, enabled)
    write(OUT, HEAD + text[:end].rstrip("\t") + RULE + "\t\t" + text[end:])
    if COUNCIL.exists():
        COUNCIL.unlink()
        print(f"{COUNCIL.relative_to(refs.REPO)}: removed (0.4.0)")
    if DECISIONS.exists():
        DECISIONS.unlink()
        print(f"{DECISIONS.relative_to(refs.REPO)}: removed (0.4.0)")
    write(CMF_EFFECTS, CMF_EFFECTS_TEXT)
    write(CMF_ON_ACTIONS, CMF_ON_ACTIONS_TEXT)
    for language in LOC:
        write(MOD / f"main_menu/localization/{language}/assimilate_primary_l_{language}.yml",
              loc_text(language))


if __name__ == "__main__":
    main()
