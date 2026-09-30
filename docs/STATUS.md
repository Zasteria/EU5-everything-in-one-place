# Where the thirteen mods stand

One line each. **Read only the brief of the mod the task is about** —
`mods/<mod>/CLAUDE.md`.

| mod | state | never been in game |
| --- | --- | --- |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | разметка русского в игре, 266 ключей; **09-26: круг 4 подтверждён** | круги 5–7 |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 395 keys, 10.6% (0.2.0: + Речь Посполитая) | everything except Westphalia and the override itself |
| [`nmt_ru`](../mods/nmt_ru/CLAUDE.md) | **в игре не был; 09-22 лаунчер его прятал без `relationships` — дописан.** Русский для National Mission Trees: 17 стран (0.4.0: + Литва, Польша), 3 555 ключей. База без русского и без отката, дерево пишется целиком | всё |
| [`nmt_fix`](../mods/nmt_fix/CLAUDE.md) | 09-29. NMT засчитывает земли подданных, 111 условий | всё |
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, работа идёт в ней.** Заходы — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), открыт пункт 9 | [`archive/status_wtp_untested.md`](archive/status_wtp_untested.md) |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; губернатор починен и подтверждён, права починены. Три карты CM dev без CM и CMF | починка прав, карта еды |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **потолок скорости снят 09-18, но 09-19 он снял мод: тормозит тем сильнее, чем больше точек авторасширения.** Копия CM. Месячный пульс трогать нельзя — его слово 09-19. Ставится **вместо** CM | правки 3 и 5 |
| [`cm_dev_perf`](../mods/cm_dev_perf/CLAUDE.md) | 09-26, не в игре. CM Dev + правка 1 `cm_perf` | всё |
| [`widget_probe`](../mods/widget_probe/CLAUDE.md) | **отладочный. Прогоны 09-19: `PdxGuiDestroyWidget` работает, перечислить детей нечем.** Теперь меряет сам: сколько реальных секунд занял каждый из шести последних игровых месяцев | секундомер месяца, `gui.clearwidgets` |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **0.4 ждёт прогона** (0.3 проверена 09-17). После войны опускает содержание и гасит инфляцию чеканкой | мир в тот же день, короткие войны, первый месяц чеканки по прогнозу (09-27) |

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
