# Where the mods stand

One line each. **Read only the brief of the mod the task is about** —
`mods/<mod>/CLAUDE.md`.

| mod | state | never been in game |
| --- | --- | --- |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | разметка русского; перевод 1.4.1 (0.5.1, круг 12); 0.5.0 — круг 11: правки Russian Localization Fix и `unknown_custom`; **09-26: круг 4 подтверждён** | круги 5–8, 0.4.3, 0.5.0, 0.5.1 |
| [`nmt_fix`](../mods/nmt_fix/CLAUDE.md) | 0.2.0 (10-03): земли подданных (121 условие) + NMT под 1.4 | всё |
| [`integration_fix`](../mods/integration_fix/CLAUDE.md) | 0.2.0: Integration Hotfix на 1.4.1, вместо него | всё |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **загружен 09-19, рисует**; 0.6.0: три режима карты отраслей; еда, губернатор под 1.4 не сверены | 0.3.0–0.6.0, починка прав, еда |
| [`cm_dev_perf`](../mods/cm_dev_perf/CLAUDE.md) | +perf42–44: стройка по рабочим; +perf41/46: карта отраслей; перед Río, после Río — [`cm_rio_patch`](../mods/cm_rio_patch/CLAUDE.md); ND — своя категория | +perf19–39, патч |
| [`cmf_dev_beta`](../mods/cmf_dev_beta/CLAUDE.md) | +beta13: номер места с начала; +beta12: типы 1.4.1; `cmf_is_host`, панель, стрелки, номер места; вместо CMF и CMF Dev | +beta7, +beta12, +beta13 |
| [`glorpui_hints`](../mods/glorpui_hints/CLAUDE.md) | 1.2.14, в игре 10-18 | — |
| [`centered_towns`](../mods/centered_towns/CLAUDE.md) | 0.2.0 (10-04): позиции Better label placement под новыми именами файлов 1.4 | 0.2.0 |
| [`assimilate_primary`](../mods/assimilate_primary/CLAUDE.md) | 0.11.0: своя автоматика совета; ценности, «до 50 %» и развитие работают; порог контроля не проверен; ценности — свои задания мода без пары (0.11.0, не проверено) | 0.6.0 |
| [`speed_5`](../mods/speed_5/CLAUDE.md) | паузы, 5 скоростей | всё |
| [`cmf_saved_settings`](../mods/cmf_saved_settings/CLAUDE.md) | 0.3.0: применение | 0.3.0 |
| [`rulers_toolkit`](../mods/rulers_toolkit/CLAUDE.md) | 0.9.5: командиры, ползунки, пленные, творения, откаты, женитьба, мир (шаблон, дипрепутация), журнал | флоты, советники, выкуп, откаты |

Закрытые, но лежащие здесь: [`archive/status_closed.md`](archive/status_closed.md).
Убранные из дерева 10-03: [`archive/retired_mods.md`](archive/retired_mods.md).

## Two things being hunted that are not any mod's fault

- **[The widget leak](investigations/widget_leak.md)** — база игры, пять прогонов.
  09-19: **уничтожать виджеты мод умеет**, не умеет их перечислять. И цена CM,
  по-видимому, умножается на эту утечку —
  [`investigations/cm_performance.md`](investigations/cm_performance.md).
- **[The panel hitch](investigations/panel_hitch.md)** — панели открываются
  медленнее с плейсетом с первой минуты. **Не путать с утечкой.**

Инструменты — [`CONVENTIONS.md`](CONVENTIONS.md).
