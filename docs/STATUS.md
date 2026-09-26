# Where the thirteen mods stand

One line each, and a link to the brief. **Read the brief for the mod the task is
about and no others** — `mods/<mod>/CLAUDE.md` holds the state, the commands and
what fails silently there.

| mod | state | never been in game |
| --- | --- | --- |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | working; repairs the base game's own Russian markup, 224 keys and the Ottoman panel. **09-26: круг четвёртый подтверждён, пятый в игре не был** | круг пятый |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 174 keys, 10.2% | everything except Westphalia and the override itself |
| [`nmt_ru`](../mods/nmt_ru/CLAUDE.md) | **новый 09-22, в игре не был: лаунчер его не показал, не хватало `relationships` — дописан.** Русский для National Mission Trees: Валахия, Византия, Феодоро, Грузия — 716 ключей из 8 348. База без русского и без отката, дерево пишется целиком | всё |
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, работа идёт в ней.** Заходы — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), открыт пункт 9 | [`archive/status_wtp_untested.md`](archive/status_wtp_untested.md) |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; губернатор починен и подтверждён, права починены. Три карты CM dev без CM и CMF | починка прав, карта еды |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **потолок скорости снят 09-18, но 09-19 он снял мод: тормозит тем сильнее, чем больше точек авторасширения.** Копия CM. Месячный пульс трогать нельзя — его слово 09-19. Ставится **вместо** CM | правки 3 и 5 |
| [`widget_probe`](../mods/widget_probe/CLAUDE.md) | **отладочный. Прогоны 09-19: `PdxGuiDestroyWidget` работает, перечислить детей нечем.** Теперь меряет сам: сколько реальных секунд занял каждый из шести последних игровых месяцев | секундомер месяца, `gui.clearwidgets` |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **работает, проверено войной 09-17.** Содержание падает на мирное значение при выходе из всех войн, чеканка гасит инфляцию. Настройки — страница в меню CMF | точный последний месяц правки инфляции (09-17, после его прогона) |

Пять закрытых модов вынесены:
[`archive/status_closed.md`](archive/status_closed.md).

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
