# Where the eleven mods stand

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
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, и работа идёт в ней.** Его список и все заходы — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), открыт пункт 9. Карта городских прав перенесена из CM dev целиком — [`investigations/wtp_town_right_map.md`](investigations/wtp_town_right_map.md) | список непрогнанного вынесен: [`archive/status_wtp_untested.md`](archive/status_wtp_untested.md) |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **новый 09-15, в игре не был.** Три карты CM dev без CM и CMF: еда, права (+9 детских), губернатор | всё |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **потолок скорости снят 09-18, но 09-19 он снял мод: тормозит тем сильнее, чем больше точек авторасширения.** Копия CM; добавлено: цикл авторасширения раз в три месяца. Ставится **вместо** CM | правки 3 и 4 |
| [`widget_probe`](../mods/widget_probe/CLAUDE.md) | **отладочный, прогон 09-19: вверху дерева утечки нет.** Свёрнут в кнопку; теперь переписывает детей `_root_` через `AccessChild` | перепись корня и все три вызова |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **работает, проверено войной 09-17.** Содержание армии, флота и крепостей падает на мирное значение в месяц выхода из **всех** войн, чеканка гасит накопленную инфляцию и уходит обратно к ванильной автоматике. Настройки — страница в меню CMF | точный последний месяц правки инфляции (09-17, после его прогона) |

`where_to_produce` is the **second** attempt; the first failed untested, and why
is [`archive/where_to_produce.md`](archive/where_to_produce.md).

**Вылетов больше нет — его слово 2026-09-17, причину искать не нужно.**

## Two things being hunted that are not any mod's fault

- **[The widget leak](investigations/widget_leak.md)** — established as the base
  game's across five runs. Рычаг ищет [`widget_probe`](../mods/widget_probe/CLAUDE.md):
  прогон 09-19 показал, что вверху дерева утечки нет.
- **[The panel hitch](investigations/panel_hitch.md)** — panels open slower with
  the playset from the first minute. **A different thing, not to be filed with
  the leak.** Next step is a bisect he can do in five minutes.

## The tooling around all of it

`mods.bat` → `tools/mods.ps1` is his whole mod loop, `tools/workshop.py` answers
whether a refresh is owed, and **neither is to be rebuilt** ([`SETTLED.md`](SETTLED.md)).
How it fits together: [`CONVENTIONS.md`](CONVENTIONS.md).
