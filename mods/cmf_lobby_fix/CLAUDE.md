# `cmf_lobby_fix` — значки «Бонусов державы» в лобби под 1.4.4

**0.1.0 (10-27), в игре не был.** Один файл: `in_game/gui/vanilla/cmf_multiplayer_lobby_vanilla_types.gui`
из CMF 2.5.0 (мастерская) с тремя правками, теми же, что игра сделала в своём
`multiplayer_lobby.gui` в 1.4.4: `Or4` → `Or3`, `Or8` → `Or7` и снят виджет
`IsReligiousOrderSetup` — функцию убрали из движка.

Симптом без него: в лобби (выбор страны, «Наблюдать») под «Бонусы державы»
пустые рамки вместо значков, в `error.log` три ошибки
`Could not find data system function 'IsReligiousOrderSetup'` на строках 119, 551, 875
этого файла.

Ставится **после** CMF (зависимость в `metadata.json`), заменяет его файл тем же путём.
`cmf_dev_beta` эту правку уже несёт (+beta15) — с ним не нужен.

**Убрать, когда CMF обновится**: если в его файле больше нет `IsReligiousOrderSetup`,
мод лишний, а его копия затрёт новые правки CMF. Проверка:

    grep -c IsReligiousOrderSetup "<workshop>/3692202776/in_game/gui/vanilla/cmf_multiplayer_lobby_vanilla_types.gui"

Флаги в лобби (53×40 → 53×35, 82×62 → 82×55) лежат в `multiplayer_lobby.gui` CMF
целиком, их не трогал: флаг там чуть выше игрового, но рисуется.
