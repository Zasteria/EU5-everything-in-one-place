#!/usr/bin/env python3
"""Собирает `marker_throttle`: тормоз на пересчёт значков отрядов.

**Почему он существует.** `max_update_rate` — свойство виджета, которым движок
ограничивает, как часто виджет пересчитывает свои выражения. Игра пользуется им
сама, один раз: `map_markers.gui`, окно `inactive_widgets_storage`,
`max_update_rate = -2 # Don't update data properties`. Faster Universalis
пользуется им двадцать раз — и **ни разу на значке отряда**: throttled у него
парламент, святое место, рынок, пошлина, порт, династия, ввоз-вывоз и прочие
редкие дипломатические значки, а `unit_marker`, `combat_marker`, `fort_marker` и
`supply_depot_marker` остались без ограничения. То есть ровно то, чего на карте
сотни во время большой войны, пересчитывается каждый кадр.

Мод закрывает эту дыру и **ничего больше не делает**.

    python3 mods/marker_throttle/tools/port_from_fum.py

**Почему копией типов, а не своим `map_markers.gui`.** Корневой `unit_marker` —
это именованный виджет внутри `map_markers.gui`, и тронуть его можно только
заменив весь файл. Этот файл везут трое: игра, Glorp UI и FUM, и кто из них
побеждает, зависит от порядка загрузки. Заменять его — значит молча выкинуть
чужие правки. А типы `unit_marker_types` переопределяются по имени из отдельного
файла — так их переопределяет сам FUM, — и это складывается с кем угодно.

**Тела типов берутся у FUM дословно**, потому что переопределение типа заменяет
тело целиком: скопировать надо ту версию, которая в игре сейчас, иначе мод
откатит правки FUM. Добавляется ровно одна строка на тип.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

import refs  # noqa: E402

MOD = refs.REPO / "mods/marker_throttle"
OUT = MOD / "in_game/gui/bag_mth_unit_marker_types.gui"

# Миллисекунды между пересчётами. FUM ставит 9999 на редкие значки; у отряда
# числа меняются в бою, поэтому здесь секунда: в шестьдесят раз реже, чем
# каждый кадр, и отставание, которого на глаз не видно.
RATE = 1000

BLOCK = "types unit_marker_types {"

# Типы, на которые вешается тормоз. Список проверяется: пропал тип — генератор
# падает, а не тихо throttl-ит половину.
#
# **Только те, в которых нет ни кнопки, ни раскладки.** Первая сборка вешала
# тормоз на все семь, и его прогон 2026-09-20 показал, во что это обходится:
# значки отрядов рисовались, но **щелчком не выбирались** — только рамкой. То
# есть тормоз на типе портит попадание мышью, а не только числа. Поэтому здесь
# остались три, которые ничего не ловят и ничего не раскладывают, и в них же
# лежат оба тяжёлых шаблона: `unit_marker_item_modifiers` (24 покадровых
# выражения) и `unit_marker_item_unit_info` (полоса силы, ещё 44).
#
# Убраны и почему: `unit_maker_siege_banner` (кнопка, `onclick`,
# `alwaystransparent = no`), `unit_marker_compass` (кнопка),
# `unit_marker_item_units` (`overlappingitembox`, `alwaystransparent = no`),
# `unit_marker_item_layout` (`vbox`, то есть раскладка: устаревшая раскладка и
# есть самый вероятный виновник промаха).
TARGETS = (
    "unit_marker_item_modifiers",
    "unit_marker_item_unit_info",
    "unit_marker_battle_side_flank",
)


def source() -> Path:
    """Файл FUM, где лежат переопределённые типы значка отряда."""
    for candidate in refs.playset():
        if candidate.id == "faster.universalis":
            path = candidate.path / "in_game/gui/fum_map_markers_vanilla_types.gui"
            if not path.is_file():
                raise SystemExit(
                    f"{candidate.folder}: нет fum_map_markers_vanilla_types.gui. "
                    "FUM пересобрали -- перечитай его дерево."
                )
            return path
    raise SystemExit(
        "в reference/playset/ нет мода с id 'faster.universalis'. "
        "Без него копировать нечего: тела типов должны быть те, что в игре."
    )


def block(text: str) -> str:
    """Блок `types unit_marker_types { ... }` целиком, по счёту скобок."""
    start = text.find(BLOCK)
    if start < 0:
        raise SystemExit(f"в {BLOCK!r} не найден -- FUM пересобрали.")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise SystemExit(f"{BLOCK!r} не закрыт -- файл обрезан.")


def throttle(body: str) -> str:
    """Одна строка на тип, первой в теле."""
    for name in TARGETS:
        anchor = re.compile(r"(\n\ttype %s = [a-z]+ \{\n)" % re.escape(name))
        found = anchor.findall(body)
        if len(found) != 1:
            raise SystemExit(
                f"тип {name}: вхождений {len(found)}, ждали одно -- FUM "
                "пересобрали, перечитай файл прежде чем верить генератору."
            )
        body = anchor.sub(
            r"\1\t\tmax_update_rate = %d # marker_throttle\n" % RATE, body, count=1
        )
    return body


def metadata() -> str:
    """Форма ровно та же, что у остальных модов этого репозитория.

    **`game_custom_data` и `relationships` обязательны**: 2026-09-20 мод без них
    не появился в лаунчере вообще, а все одиннадцать работающих модов здесь их
    везут. Файл пишется с BOM, как и они.

    Зависимость от Faster Universalis объявлена не для красоты: тела типов —
    копия его тел, и лаунчер по этой строке сам ставит мод **после** FUM.
    Без неё порядок надо помнить руками, а забытый порядок FUM затирает молча.
    """
    return json.dumps({
        "name": "Map Marker Throttle",
        "id": "bag.marker_throttle",
        "version": "0.2.0",
        "game_id": "eu5",
        "supported_game_version": "1.3.*",
        "short_description": (
            "Throttles how often unit-marker widgets re-evaluate their "
            "expressions, the way the base game and Faster Universalis already "
            "do for other map markers."
        ),
        "tags": ["User Interface", "Utilities", "1.3"],
        "relationships": [
            {
                "rel_type": "dependency",
                "id": "faster.universalis",
                "display_name": "Faster Universalis",
                "resource_type": "mod",
                "version": "1.*",
            }
        ],
        "game_custom_data": {},
    }, indent=4, ensure_ascii=False) + "\n"


def main() -> int:
    src = source()
    body = throttle(block(src.read_text(encoding="utf-8-sig")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "﻿# Собрано mods/marker_throttle/tools/port_from_fum.py -- руками не писать.\n"
        "# Тела типов -- дословная копия из %s;\n"
        "# добавлена одна строка max_update_rate на тип.\n\n" % src.name
        + body + "\n",
        encoding="utf-8")
    (MOD / ".metadata").mkdir(parents=True, exist_ok=True)
    (MOD / ".metadata/metadata.json").write_text("\ufeff" + metadata(), encoding="utf-8")
    print("marker_throttle: %d типов с max_update_rate = %d, из %s"
          % (len(TARGETS), RATE, src.parent.parent.parent.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
