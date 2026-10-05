# Where the mods stand

One line each. **Read only the brief of the mod the task is about** —
`mods/<mod>/CLAUDE.md`.

| mod | state | never been in game |
| --- | --- | --- |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | разметка русского и перевод беты 10-01, окна на бете; 0.4.3 — скриншоты 10-04; **09-26: круг 4 подтверждён** | круги 5–8, 0.4.3 |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 385 keys (0.2.1, 10-03: 45 ключей под ND 1.4.0) | everything except Westphalia and the override itself |
| [`nmt_ru`](../mods/nmt_ru/CLAUDE.md) | Русский для National Mission Trees: 17 стран, 3 555 ключей; дерево пишется целиком | всё |
| [`nmt_fix`](../mods/nmt_fix/CLAUDE.md) | 0.2.0 (10-03): земли подданных (121 условие) + NMT под 1.4: Арагон, модификатор, подданные, 7 старых ошибок NMT | всё |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; губернатор починен и подтверждён, права починены. Три карты CM dev без CM и CMF | починка прав, карта еды |
| [`cm_dev_perf`](../mods/cm_dev_perf/CLAUDE.md) | CM Dev + правка 1, окна беты; +perf26 перед Río, после Río — [`cm_rio_patch`](../mods/cm_rio_patch/CLAUDE.md); ND — своя категория | +perf19–26, патч |
| [`cmf_dev_beta`](../mods/cmf_dev_beta/CLAUDE.md) | +beta5 (10-03): копия авторского CMF под 1.4 + `cmf_is_host`; ставится вместо CMF и CMF Dev | всё |
| [`glorpui_hints`](../mods/glorpui_hints/CLAUDE.md) | 1.2.12, игра 1.4, основной предмет; ворота по техам | 1.2.10–1.2.12 в игре не были |
| [`glorpui_hints_1_3`](../mods/glorpui_hints_1_3/CLAUDE.md) | 1.1.1 для 1.3, свой предмет | — |
| [`centered_towns`](../mods/centered_towns/CLAUDE.md) | 0.2.0 (10-04): позиции Better label placement под новыми именами файлов 1.4 | 0.2.0 |
| [`quiet_alerts`](../mods/quiet_alerts/CLAUDE.md) | 10-02: 0.3.0 не в игре. Красные и оранжевые с жёлтым звуком, галочка в CMF | всё |
| [`assimilate_primary`](../mods/assimilate_primary/CLAUDE.md) | 0.2.0: автоматика в основную; 0.1.0 глушил ассимиляцию | 0.2.0 |
| [`war_sliders`](../mods/war_sliders/CLAUDE.md) | **0.6.2 ждёт прогона** (0.5.2 работала 09-29). Кнопка на панели CMF: содержание и инфляция, без нажатия спит | кнопка: содержание, правка чеканки (09-30) |

Закрытые, но лежащие здесь: [`archive/status_closed.md`](archive/status_closed.md).
Убранные из дерева 10-03 (`where_to_produce`, `goods_target`, `marker_throttle`,
`widget_probe`, `qol_beta`, `auto_build_ru`): [`archive/retired_mods.md`](archive/retired_mods.md).

## Two things being hunted that are not any mod's fault

- **[The widget leak](investigations/widget_leak.md)** — база игры, пять прогонов.
  09-19: **уничтожать виджеты мод умеет**, не умеет их перечислять. И цена CM,
  по-видимому, умножается на эту утечку —
  [`investigations/cm_performance.md`](investigations/cm_performance.md).
- **[The panel hitch](investigations/panel_hitch.md)** — панели открываются
  медленнее с плейсетом с первой минуты. **Не путать с утечкой.**

Инструменты вокруг всего этого — [`CONVENTIONS.md`](CONVENTIONS.md);
`mods.bat` **ничего не пересобирает**: генераторы — работа сессии.
