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
in game windows such as decisions (his word 12.10). His run 12.10 answered it:
`cabinetactions` is not a value of the game's automated systems at all
(«Failed to read enum! Type: EAutomatedSystems»), so the checkbox and this rule's
use of it are gone; the rule reads «Совет» (`cabinet`) only.

    python3 mods/assimilate_primary/tools/generate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import council  # noqa: E402

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
\t\t\t\t\t\tis_system_automated = cabinet
\t\t\t\t\t}
\t\t\t\t\tNOT = { scope:target = scope:actor.culture }
\t\t\t\t}
\t\t\t\t"culture_percentage(scope:target)" >= {
\t\t\t\t\tvalue = "culture_percentage(scope:actor.culture)"
\t\t\t\t\tadd = %s
\t\t\t\t}
\t\t\t}
""" % (round(LEAD * 100), LEAD)


# Files the council automation used to have under other names.
STALE = [
    MOD / "in_game/common/on_action/assimilate_primary_council_on_actions.txt",
    MOD / "in_game/common/decisions/assimilate_primary_decisions.txt",
    # 10-20, his word: vanilla automation stays free; 1.4.2 also put the
    # game's own -1000 "Wrong culture" back, so the copy has no job left.
    OUT,
]

LOC = {
    "english": {
        "bag_asp_name": "Council Automation",
        "bag_asp_desc": "The mod's own council automation: seats get actions down a priority list you set here. Cabinet assimilation targets the primary culture.",
        "bag_asp__main_name": "Council",
        "bag_asp__main__council_name": "Own automation",
        "bag_asp__actions_name": "Actions",
        "bag_asp__auto_name": "Own council automation",
        "bag_asp__auto_desc": "On: switches the game's «Council» automation off and hands every seat out down the «Priority» list at once, then on the schedule below. Each assignment goes to debug.log.",
        "bag_asp__period_name": "Fill empty seats every, months",
        "bag_asp__period_desc": "How often a seat left without an action (a finished one, a new advisor) gets one. Seats that work are not touched.",
        "bag_asp__review_name": "Hand out all seats every, months",
        "bag_asp__log_name": "Detailed log",
        "bag_asp__log_desc": "On: debug.log gets every seat before and after each pass, the order read, why a province is not taken for assimilation, the settings after you change one, and who joins or leaves the cabinet. For finding what went wrong; off in normal play.",
        "bag_asp__review_desc": "How often every seat is handed out again down «Priority»: the top action takes the advisors best at it, even from a lower action, and moves there with its targets; then the next action, and so on. A change of the lists or a new advisor does the same at once. 0: never.",
        "bag_asp__actions__available_name": "Available",
        "bag_asp__actions__priority_name": "Priority",
        "bag_asp__available__use_name": "In use",
        "bag_asp__available_item_column_name": "Action",
        "bag_asp__priority__ability_name": "Skill",
        "bag_asp__fine_name": "Fine tuning",
        "bag_asp__priority_item_column_name": "Action",
        "bag_asp__available_name": "Available",
        "bag_asp__available_desc": "Every common action this country can see. Ticked ones are in use.",
        "bag_asp__priority_name": "Priority",
        "bag_asp__priority_desc": "The actions in use, tried from the top.",
    },
    "russian": {
        "bag_asp_name": "Автоматика совета",
        "bag_asp_desc": "Своя автоматика совета: места получают действия по списку приоритетов, который задаётся здесь. Ассимиляция советом идёт в основную культуру.",
        "bag_asp__main_name": "Совет",
        "bag_asp__main__council_name": "Своя автоматика",
        "bag_asp__actions_name": "Действия",
        "bag_asp__auto_name": "Своя автоматика совета",
        "bag_asp__auto_desc": "Включено: игровая автоматика «Совет» выключается, все места сразу распределяются по списку «Приоритет», дальше — по расписанию ниже. Каждое назначение пишется в debug.log.",
        "bag_asp__period_name": "Заполнять пустые места раз в, мес.",
        "bag_asp__period_desc": "Как часто место без действия (закончилось, новый советник) получает действие. Занятые места не трогаются.",
        "bag_asp__review_name": "Перераспределять все места раз в, мес.",
        "bag_asp__log_name": "Подробный журнал",
        "bag_asp__log_desc": "Включено: в debug.log пишутся все места до и после каждой раздачи, прочитанный порядок, почему провинцию не берёт ассимиляция, настройки после вашего изменения, кто вошёл в совет и кто вышел. Для поиска ошибок; в обычной игре выключите.",
        "bag_asp__review_desc": "Как часто все места заново раздаются по «Приоритету»: верхнее действие забирает лучших по его навыку советников, даже у действий ниже, и переезжает к ним со своими целями; потом следующее, и так далее. Смена списков или новый советник делают то же сразу. 0 — никогда.",
        "bag_asp__actions__available_name": "Доступные",
        "bag_asp__actions__priority_name": "Приоритет",
        "bag_asp__available__use_name": "Использовать",
        "bag_asp__available_item_column_name": "Действие",
        "bag_asp__priority__ability_name": "Навык",
        "bag_asp__fine_name": "Тонкие настройки",
        "bag_asp__priority_item_column_name": "Действие",
        "bag_asp__available_name": "Доступные",
        "bag_asp__available_desc": "Все общие действия, которые видит эта страна. Отмеченные используются.",
        "bag_asp__priority_name": "Приоритет",
        "bag_asp__priority_desc": "Используемые действия, пробуются сверху вниз.",
    },
}


def loc_text(language: str) -> str:
    items = {**LOC[language], **council.loc_rows(refs.GAME, language)}
    rows = "".join(f' {k}: "{v}"\n' for k, v in items.items())
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
    for path in STALE:
        if path.exists():
            path.unlink()
            print(f"{path.relative_to(refs.REPO)}: removed")
    for rel, text in council.build(refs.GAME).items():
        write(MOD / rel, text)
    for language in LOC:
        write(MOD / f"main_menu/localization/{language}/assimilate_primary_l_{language}.yml",
              loc_text(language))


if __name__ == "__main__":
    main()
