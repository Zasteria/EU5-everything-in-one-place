# Where the ten mods stand

One line each, and a link to the brief. **Read the brief for the mod the task is
about and no others** — `mods/<mod>/CLAUDE.md` holds the state, the commands and
what fails silently there.

| mod | state | never been in game |
| --- | --- | --- |
| [`glorpui_hints`](../mods/glorpui_hints/CLAUDE.md) | **автономен с 09-14**: машинерия подсказок Glorp UI форкнута под `svx_svh_*`, окно ценностей своё и подтверждено | весь форк; религиозный аспект |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | working; repairs the base game's own Russian markup, 207 keys | rounds two and three |
| [`auto_build_ru`](../mods/auto_build_ru/CLAUDE.md) | done and confirmed; 1269 keys. **Пересобрать нельзя**: Advanced Auto Build убран из дерева 2026-09-12, а генератор читает его английские ключи | the 0.9.3 work, 28 keys |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 174 keys, 10.2% | everything except Westphalia and the override itself |
| [`rgo_bonus_filter`](../mods/rgo_bonus_filter/CLAUDE.md) | working, in use, nothing outstanding | the location-panel chip |
| [`goods_target`](../mods/goods_target/CLAUDE.md) | paused, half working, four faults known | anything on the monthly pulse |
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, и работа идёт в ней.** Его список и все заходы — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), открыт пункт 9. Карта городских прав перенесена из CM dev целиком — [`investigations/wtp_town_right_map.md`](investigations/wtp_town_right_map.md) | окно замены, порядок «Пригодности» и `ERROR` прогонами 09-14 приняты; **не прогонялось ничего из 09-14:** `_cov_pass` со спросом о локации и сторона в `_stands_`, «на конец» без устаревших зданий, поделённое среднее провинции в лесенке, приоритет отставшей грамоты, правка грамот руками и провинцией; и **его слово 09-12: 90% из того, что документы звали непрогнанным, уже прогонялось или неактуально** — сверять с ним, не с документами |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; две дыры в данных закрыты. Три карты CM dev без CM и CMF: еда, права (+9 детских), губернатор | обе правки, карта еды |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **первая правка подтверждена 09-18, вторая ждёт прогона.** Копия Construction Manager: ворота на дереве типов зданий сняли потолок скорости, развёртки очереди строек переведены на одну за цикл из dev 2.3.0. Ставится **вместо** CM | месячная просадка и стройка после правки очереди |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **работает, проверено войной 09-17.** Содержание армии, флота и крепостей падает на мирное значение в месяц выхода из **всех** войн, чеканка гасит накопленную инфляцию и уходит обратно к ванильной автоматике. Настройки — страница в меню CMF | точный последний месяц правки инфляции (09-17, после его прогона) |

`where_to_produce` is the **second** attempt; the first failed untested, and why
is [`archive/where_to_produce.md`](archive/where_to_produce.md).

**Вылетов больше нет — его слово 2026-09-17, причину искать не нужно.**

## Two things being hunted that are not any mod's fault

- **[The widget leak](investigations/widget_leak.md)** — established as the base
  game's across five runs; the open question is whether a mod or a setting is a
  lever. A run is prepared and agreed.
- **[The panel hitch](investigations/panel_hitch.md)** — panels open slower with
  the playset from the first minute. **A different thing, not to be filed with
  the leak.** Next step is a bisect he can do in five minutes.

## The tooling around all of it

`mods.bat` → `tools/mods.ps1` is his whole mod loop, `tools/workshop.py` answers
whether a refresh is owed, and **neither is to be rebuilt** ([`SETTLED.md`](SETTLED.md)).
How it fits together: [`CONVENTIONS.md`](CONVENTIONS.md).
