# Where the mods stand

One line each. **Read only the brief of the mod the task is about** —
`mods/<mod>/CLAUDE.md`.

| mod | state | never been in game |
| --- | --- | --- |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | разметка русского и перевод беты 10-01, окна на бете (0.4.2); **09-26: круг 4 подтверждён** | круги 5–8 |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 385 keys (0.2.1, 10-03: 45 ключей под ND 1.4.0) | everything except Westphalia and the override itself |
| [`nmt_ru`](../mods/nmt_ru/CLAUDE.md) | Русский для National Mission Trees: 17 стран (0.4.0: + Литва, Польша), 3 555 ключей. База без русского и без отката, дерево пишется целиком | всё |
| [`nmt_fix`](../mods/nmt_fix/CLAUDE.md) | 0.2.0 (10-03): земли подданных (121 условие) + NMT под 1.4: Арагон, модификатор, подданные, 7 старых ошибок NMT | всё |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; губернатор починен и подтверждён, права починены. Три карты CM dev без CM и CMF | починка прав, карта еды |
| [`cm_perf`](../mods/cm_perf/CLAUDE.md) | **09-19 он снял мод: тормозит тем сильнее, чем больше точек авторасширения.** Копия CM, ставится **вместо** CM; месячный пульс не трогать | правки 3 и 5 |
| [`cm_dev_perf`](../mods/cm_dev_perf/CLAUDE.md) | CM Dev + правка 1 `cm_perf`, окна беты; журнал CM в `debug.log` (+perf8) пишет; +perf14 — окна на Río (ниже Río); галочки дорог при нехватке и основных товаров на чужом рынке | обе галочки |
| [`cmf_dev_beta`](../mods/cmf_dev_beta/CLAUDE.md) | +beta5 (10-03): копия авторского CMF под 1.4 + `cmf_is_host`; ставится вместо CMF и CMF Dev | всё |
| [`glorpui_hints`](../mods/glorpui_hints/CLAUDE.md) | 1.2.5: подсказка ценностей из файлов 1.4; «(IV)» у «пока недоступно», условия — тестовая галочка | тест условий |
| [`quiet_alerts`](../mods/quiet_alerts/CLAUDE.md) | 10-02: 0.3.0 не в игре. Красные и оранжевые с жёлтым звуком, галочка в CMF | всё |
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
`mods.bat` перестроен 10-03 по его списку и **ничего не пересобирает**: генераторы — работа сессии.
