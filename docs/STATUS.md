# Where the thirteen mods stand

One line each, and a link to the brief. **Read the brief for the mod the task is
about and no others** — `mods/<mod>/CLAUDE.md` holds the state, the commands and
what fails silently there.

| mod | state | never been in game |
| --- | --- | --- |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | working; repairs the base game's own Russian markup, 209 keys. **09-20: тултип выгоды здания сыпал 362 строки за 87 с, починен** | новый ключ и круги два-три |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 174 keys, 10.2% | everything except Westphalia and the override itself |
| [`nmt_ru`](../mods/nmt_ru/CLAUDE.md) | **новый 09-22, в игре не был: лаунчер его не показал, не хватало `relationships` — дописан.** Русский для National Mission Trees: Валахия, Византия, Феодоро, Грузия — 716 ключей из 8 348. База без русского и без отката, дерево пишется целиком | всё |
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, работа идёт в ней.** Заходы — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), открыт пункт 9 | [`archive/status_wtp_untested.md`](archive/status_wtp_untested.md) |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; губернатор починен и подтверждён, права починены. Три карты CM dev без CM и CMF | починка прав, карта еды |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **потолок скорости снят 09-18, но 09-19 он снял мод: тормозит тем сильнее, чем больше точек авторасширения.** Копия CM. Месячный пульс трогать нельзя — его слово 09-19. Ставится **вместо** CM | правки 3 и 5 |
| [`widget_probe`](../mods/widget_probe/CLAUDE.md) | **отладочный. Прогоны 09-19: `PdxGuiDestroyWidget` работает, перечислить детей нечем.** Теперь меряет сам: сколько реальных секунд занял каждый из шести последних игровых месяцев | секундомер месяца, `gui.clearwidgets` |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **работает, проверено войной 09-17.** Содержание падает на мирное значение при выходе из всех войн, чеканка гасит инфляцию. Настройки — страница в меню CMF | точный последний месяц правки инфляции (09-17, после его прогона) |

Пять закрытых модов вынесены:
[`archive/status_closed.md`](archive/status_closed.md).
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, и работа идёт в ней.** Его список и все заходы — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), открыт пункт 9. Карта городских прав перенесена из CM dev целиком — [`investigations/wtp_town_right_map.md`](investigations/wtp_town_right_map.md) | окно замены, порядок «Пригодности» и `ERROR` прогонами 09-14 приняты; **не прогонялось ничего из 09-14:** `_cov_pass` со спросом о локации и сторона в `_stands_`, «на конец» без устаревших зданий, поделённое среднее провинции в лесенке, приоритет отставшей грамоты, правка грамот руками и провинцией; и **его слово 09-12: 90% из того, что документы звали непрогнанным, уже прогонялось или неактуально** — сверять с ним, не с документами |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; губернатор починен и подтверждён, права починены. Три карты CM dev без CM и CMF | починка прав, карта еды |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **первая правка подтверждена 09-18, вторая ждёт прогона.** Копия Construction Manager: ворота на дереве типов зданий сняли потолок скорости, развёртки очереди строек переведены на одну за цикл из dev 2.3.0. Ставится **вместо** CM | месячная просадка и стройка после правки очереди |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **работает, проверено войной 09-17.** Содержание армии, флота и крепостей падает на мирное значение в месяц выхода из **всех** войн, чеканка гасит накопленную инфляцию и уходит обратно к ванильной автоматике. Настройки — страница в меню CMF | точный последний месяц правки инфляции (09-17, после его прогона) |
| [`glorpui_hints`](../mods/glorpui_hints/CLAUDE.md) | **автономен с 09-14**: подсказки Glorp UI форкнуты под `svx_svh_*`, окно ценностей своё и подтверждено | весь форк; религиозный аспект |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | working; repairs the base game's own Russian markup, 207 keys | rounds two and three |
| [`auto_build_ru`](../mods/auto_build_ru/CLAUDE.md) | done and confirmed; 1269 keys. **Пересобрать нельзя**: Advanced Auto Build убран из дерева 09-12, а генератор читает его ключи | the 0.9.3 work, 28 keys |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 174 keys, 10.2% | everything except Westphalia and the override itself |
| [`rgo_bonus_filter`](../mods/rgo_bonus_filter/CLAUDE.md) | working, in use, nothing outstanding | the location-panel chip |
| [`goods_target`](../mods/goods_target/CLAUDE.md) | paused, half working, four faults known | anything on the monthly pulse |
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, и работа идёт в ней.** Его список и все заходы — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), открыт пункт 9. Карта городских прав перенесена из CM dev целиком — [`investigations/wtp_town_right_map.md`](investigations/wtp_town_right_map.md) | шесть правок 09-14 и оговорка к самому списку — [`archive/status_wtp_untested_0914.md`](archive/status_wtp_untested_0914.md) |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; губернатор подтверждён, права починены, 09-23 добавлена страница настроек CMF. Три карты CM dev без CM | страница, починка прав, карта еды |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **первая правка подтверждена 09-18, вторая ждёт прогона.** Копия CM, ставится **вместо** него: ворота на дереве типов зданий и развёртки очереди из dev 2.3.0 | месячная просадка и стройка после правки очереди |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **работает, проверено войной 09-17.** Содержание и чеканка правятся в месяц выхода из **всех** войн; настройки — страница CMF | точный последний месяц правки инфляции (09-17, после его прогона) |

`where_to_produce` — **вторая** попытка; первая провалилась непроверенной:
[`archive/where_to_produce.md`](archive/where_to_produce.md).
**Вылетов больше нет — его слово 2026-09-17.**

## Two things being hunted that are not any mod's fault

- **[The widget leak](investigations/widget_leak.md)** — база игры, пять прогонов.
  09-19: **уничтожать виджеты мод умеет**, не умеет их перечислять. И цена CM,
  по-видимому, умножается на эту утечку —
  [`investigations/cm_performance.md`](investigations/cm_performance.md).
- **[The panel hitch](investigations/panel_hitch.md)** — панели открываются
  медленнее с плейсетом с первой минуты. **Не путать с утечкой.**

Инструменты вокруг всего этого — [`CONVENTIONS.md`](CONVENTIONS.md);
`mods.bat` и `tools/workshop.py` **перестраивать не надо** ([`SETTLED.md`](SETTLED.md)).
