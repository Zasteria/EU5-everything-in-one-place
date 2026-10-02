# Where the thirteen mods stand

One line each. **Read only the brief of the mod the task is about** —
`mods/<mod>/CLAUDE.md`.

| mod | state | never been in game |
| --- | --- | --- |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | разметка русского и перевод беты 10-01, окна на бете (0.4.2); **09-26: круг 4 подтверждён** | круги 5–8 |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 395 keys, 10.6% (0.2.0: + Речь Посполитая) | everything except Westphalia and the override itself |
| [`nmt_ru`](../mods/nmt_ru/CLAUDE.md) | Русский для National Mission Trees: 17 стран (0.4.0: + Литва, Польша), 3 555 ключей. База без русского и без отката, дерево пишется целиком | всё |
| [`nmt_fix`](../mods/nmt_fix/CLAUDE.md) | 09-29. NMT засчитывает земли подданных, 111 условий | всё |
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, работа идёт в ней.** Заходы — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), открыт пункт 9 | [`archive/status_wtp_untested.md`](archive/status_wtp_untested.md) |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; губернатор починен и подтверждён, права починены. Три карты CM dev без CM и CMF | починка прав, карта еды |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **09-19 он снял мод: тормозит тем сильнее, чем больше точек авторасширения.** Копия CM, ставится **вместо** CM; месячный пульс не трогать | правки 3 и 5 |
| [`cm_dev_perf`](../mods/cm_dev_perf/CLAUDE.md) | 09-26, не в игре. CM Dev + правка 1 `cm_perf`; 10-01 окна на бете | всё |
| [`qol_beta`](../mods/qol_beta/CLAUDE.md) | 10-01, не в игре. QoL by Buddy под бету, без границ | всё |
| [`cmf_dev_beta`](../mods/cmf_dev_beta/CLAUDE.md) | 10-02: без CMF Dev в плейсете не работал; +beta3 — полная копия CMF Dev, ставится вместо | всё |
| [`quiet_alerts`](../mods/quiet_alerts/CLAUDE.md) | 10-02: 0.1.0 глушил всё; 0.1.1 не в игре. Тихие красные и оранжевые уведомления | всё |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **0.6.2 ждёт прогона** (0.5.2 работала 09-29). Кнопка на панели CMF: содержание и инфляция, без нажатия спит | кнопка: содержание, правка чеканки (09-30) |

Закрытые моды (и `widget_probe`) вынесены:
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
