# Test log

What has actually been in the game, and what it showed.

Only the player can run EU5, so a run is the scarcest thing this repository
consumes. Everything else here — the reference tree, the generators, the
checkers — exists to spend fewer of them. This file is where a run's result
stops being a remark in a chat and becomes something a later session can rely
on.

**A session writes the entry, not the player.** The player says what happened,
in as few words as they like; the session turns it into a row and commits it. If
a run is not written down, `STATUS.md` will keep calling something "untested"
long after it was tested, which is the same cost as not having run it.

## How to fill this in

One entry per run. What matters is the last two columns: what was expected, and
what actually appeared.

- **Date and mod** — and the base mod's version if the run was about a
  translation, from `python3 tools/refs.py`.
- **What was loaded** — the playset order matters for a localization mod, since
  the mod loaded later wins the key.
- **Expected / observed** — the whole point. "Nothing happened" is a result and
  belongs here.
- **`error.log`** — quote the line if there was one. It names the file and the
  line for GUI failures and script errors. An effect that never runs logs
  nothing at all, so "log clean" is itself worth recording: it says the failure
  is the silent kind and the next step is a `cmf_log`, not another guess.

**Do not ask for logs by default.** The owner said so on 2026-08-31 — a zip is
his time and the session's tokens both — and three loads running the answer was
"clean". Ask when something *did nothing* and the reason has to be either a GUI
error or a silent effect, when a crash or a load failure is in play, or when a
`cmf_log` was added for this run. A layout question, a number that looks wrong,
a filter that filters: the screenshot already says it.

## Runs

**2026-10-12 (сообщение 23:12 UTC), 1.4: зонд сдвига ценностей, второй.** Первый зонд ничего не тронул: пустого места не было, а снять действие руками игра не даёт. Второй (`stop_cabinet_action` у случайного места, затем `set_cabinet_action … change_societal_values target = societal_value_type:traditionalist_vs_innovative`) снял интеграцию провинции Ров и **поставил сдвиг ценностей с пустой парой** — подсказка «Изменение общественных ценностей «» на в пользу «NAME»». `target` пару не задаёт.

**2026-10-12 (сообщение 23:02 UTC), 1.4: зонд сдвига ценностей, его логи.** `effect every_country = { … set_cabinet_action = { type = cabinet_action:change_societal_values target = societal_value_type:traditionalist_vs_innovative } … }` дважды (03:58:39, 03:59:22, `debug_mode` включён): `console_success`, ошибок про `set_cabinet_action` в `error.log` нет. Что показало место совета — он не сказал. **Каждая команда `effect` шла 7–10 с** — между вызовом и успехом ~7 000 строк перепроверки скрипта.

**2026-10-12 (сообщение 22:45 UTC), 1.4: `assimilate_primary` 0.8.5 + `cmf_dev_beta` +beta10.** **Экстренное восстановление сработало прямо на паузе** — по плашке «разорённые районы» (`GetTitleKey`, ребёнок `type alert_banner`). **Номер места переносит строку** (+beta10, путь стрелок): вписал 4 — строка уехала на 4-ю; но вписанная «4» осталась в поле той строки, что встала на её место (`PdxClearEditBoxText` не очистил) — +beta11 рисует номер кнопкой и открывает поле по щелчку, как мод-лист игры. `quiet_alerts` велел удалить: уведомления игра глушит сама.

**2026-10-12 (сообщение 22:03 UTC), 1.4: `assimilate_primary` 0.8.x + `cmf_dev_beta` +beta8, затем +beta9, его логи.** (1) На паузе в начале месяца опустил процветание Киева; уведомление о разорённых районах **появилось уже на паузе** (уведомления на паузе обновляются). Места были: 2 интеграции, 1 ассимиляция. **Ни на паузе, ни после неё место на восстановление не перешло** — только раздачей в начале следующего месяца. `debug.log` того запуска не сохранился (переписан следующим запуском). Причина найдена по дереву: окно сравнивало `GetAlertOfTypeShowingCount('has_devastated_locations')` — функция берёт цвет, не имя — с `IntToUnsigned` (возвращает `float`). (2) +beta9: **номера мест в пустых полях видны**. Вписанное число и Enter — ничего, Enter лишь выделяет текст; строки зонда `cmf_beta: a typed place reached the script` в уцелевшем куске лога (02:54–03:00:07, обрезан на 4 МБ) нет. (3) Консольное `change_prosperity = -2` по четырём районам одной строкой сработало только на Киев, `= 2` (восстановить) — сработало. Ответ — 0.8.3 и +beta10.

**2026-10-12 (сообщение 21:39 UTC), 1.4: `assimilate_primary` ≥ 0.7.0 + `cmf_dev_beta` +beta8, окно CMF.** **Имена строк — ссылки игры, подсказки правильные** (`ShowCabinetActionName` в строке CMF рисует). Поле «№» есть, но **номеров мест в нём нет** — пустое поле показывало только «№»; он ждал номера, как в мод-листе игры. **Вписал 5 у «Восстановления» — строка не сдвинулась**, в поле осталось «5» (нажат ли Enter и дошло ли до скрипта — неизвестно; +beta9 пишет `cmf_beta: a typed place reached the script`). Ответ — +beta9: номер места в пустом поле, зонд.

**2026-10-12 (~23:50), 1.4: `assimilate_primary` 0.6.0 + `cmf_dev_beta` +beta7.** Советники **сменили задания на интеграцию** и «пошли пахать» — раздача по приоритету работает, `set_cabinet_action` с `target` берёт. **Стрелки работают** (+beta7). Подсказка строк (описание из игры текстом) — «мусор»: в строке CMF ссылки-понятия из описания открывают свои подсказки («Провинция»), а не подсказку действия. Хочет имя игры со ссылкой, как здания CM (`ShowBuildingTypeName`) — 0.7.0 `ShowCabinetActionName`.

**2026-10-12 21:13–21:29, 1.4: `assimilate_primary` 0.5.0 на `cmf_dev_beta` +beta6, с `cm_dev_perf`, его логи.** Всем советникам заранее дал другие задания, включил свою автоматику, оба срока по 1 мес., интеграция наверху «Приоритета». **Ничего не сменилось.** В `debug.log` одна строка мода — «own council automation on» (21:16:08); дальше ни одной строки прохода, хотя CM писал свой месячный цикл каждые 4–8 с. Проход при включении сделал что должен был — 0.5.0 трогал только пустые места, а пустых не было; ежемесячного шага не видно вовсе (0.5.0 висел на `monthly_country_pulse` и сам о себе не писал). `error.log`: `Failed to read enum! Type: "EAutomatedSystems", Val "cabinetactions"` — **такой системы нет**. Ещё два его замечания: строки списков голые рядом с подсказками игры; стрелки порядка срабатывают «2 из 5», и так же в CM у городских прав — оба списка скрывают строки, а стрелки CMF меняют местами со скрытой. Ответ — 0.6.0 и +beta7.

Runs of 10-06 and of 10-12 to 18:41 (`cm_dev_perf` +perf34–39, HRE Manager, `ru_loc_fix`, `war_sliders`, `speed_10`): [`archive/testlog_1006_1012_morning.md`](archive/testlog_1006_1012_morning.md).

Runs of 10-05 (`cm_dev_perf` +perf26–30, `assimilate_primary`): [`archive/testlog_1005.md`](archive/testlog_1005.md)

Runs of 10-04 from 22:15 to 23:09 (`cm_dev_perf` +perf21–24, Румыния, список ND): [`archive/testlog_1004_evening.md`](archive/testlog_1004_evening.md).

Runs of 10-04 from 12:55 to 17:42 (`centered_towns`, Better label placement, `cm_dev_perf` +perf14–18): [`archive/testlog_1004_day.md`](archive/testlog_1004_day.md).

Earlier runs of 10-04 (glorpui_hints 1.2.4–1.2.10, cm_dev_perf +perf11): [`archive/testlog_1004_morning.md`](archive/testlog_1004_morning.md).

## Waiting on a run

The next session should start here rather than designing anything new. All of
these are prepared, all are cheap, and the owner has agreed to the hover one.

**`nmt_fix` 0.1.0, та же болгарская партия**, мод после NMT. Верно:
«Завоевать Валахию» считает районы вассала, error.log молчит о `nmt_fix`.

**`cm_dev_perf` вместо CM Dev, та же партия.**
Ставится через `mods.bat`, CM Dev в плейсете выключить. Верный ответ: фильтры
и стройка работают как с CM Dev, тики на её глаз
быстрее. `widget_probe` она удалила 26.09, зонда нет. Подробно — `mods/cm_dev_perf/CLAUDE.md`.

**`cm_maps`, страница настроек CMF и починка прав — один заход, всё видно
сразу.** Мод ставится через `mods.bat` → 4, партия та же. Страница должна
появиться в меню CMF под именем «Карты Construction Manager».

1. **Страница вообще есть, и на ней всё.** Четыре списка под «Рекомендуемый
   губернатор», две кнопки, флаг диагностики. **Пустая группа или строка,
   печатающая собственное имя ключа, — это и есть отказ:** макрос CMM, позванный
   с чужим аргументом, молча уносит остаток эффекта, а кнопке нужен свой
   `_text`. Проверки прошли, но они сверяют имена, а не то, что нарисовалось.
2. **«Пересчитать» при открытой карте губернатора** — карта должна пересчитаться
   на глазах, а не через четыре игровых года.
3. **Смена «Точности поиска» на 3 или 5** — должны появиться чёрные области, и
   подсказка над ними теперь ведёт к настройке, которая есть. Вернуть на 1.
4. **«Пересобрать данные карт»** — несколько секунд, игра не встаёт, цвета прав
   и еды на месте.
5. **И то, что ждёт с 09-19: починка городских прав.** Провинции, которые были
   пустыми, должны показывать списки, и свежезанятые тоже.
6. **0.3.0:** районы одной провинции (Чернигов) одного цвета на карте прав,
   проценты в подсказке одинаковые.

**`where_to_produce`, twenty-eighth load.** Four small things and one question,
all of it one glance with the results window open. Not worth a run of its own.

1. **Any market can be taken now**, the neighbour's included — the list is every
   market in the world, framed by the ticked continents. Hover a market you hold
   nothing in and it should outline and click like the rest.
2. **The four picker buttons look like «Очистить выбор»** — solid, not
   transparent. Same in the rights window.
3. **The corner above the +/- buttons has a «+» in it** and «№» has not moved.
4. **«Восточная Мунтения» does not touch «Валахия»**, «Трансильвания» does not
   touch its percentage, and the row is four pixels narrower than it was.
5. **The one question: «Из чего».** The header and the row are identical column
   for column in the file, so if the icons still sit right of the heading, the
   cause is a constant inset the rows carry and the header does not. **What
   settles it in one look:** does «Сейчас» sit exactly over its percentages? If
   yes, the drift starts somewhere in the middle and I have the wrong model of
   it; if «Сейчас» is *also* slightly left of its numbers, every heading is, and
   `margin_left` is the one number to move.

**The panel-open bisect — five minutes, no log to read.** Reported 2026-08-25:
any tab opens instantly in vanilla and with a hitch, sometimes a freeze, under
the playset — *on a save loaded a minute ago*, so it is not the widget leak.
Counted from the files already; the candidates and the numbers are in
[`investigations/panel_hitch.md`](investigations/panel_hitch.md).
The playset is 22 workshop mods, 17 of them touching `in_game`
(`python3 tools/playset.py <logs>` reads it out of `debug.log`), so this is a
bisect: same save, same three panels (country, diplomacy, a location's build
panel), halving the `in_game` mods until the hitch is cornered — four or five
loads of a minute each. Worth trying **Construction Manager** and
`rgo_bonus_filter` first, in case they save the bisect. No log, no timing — the
owner's own sense of the hitch is the measurement, because the difference he
describes is one anybody can feel.

Advanced Auto Build was the first version's headline and it was wrong: the owner
does not run it. Its `3781437488` is mounted in the 2026-08-24 log, so if it
turns out to be enabled and merely unused, that still costs — a scripted widget
is instantiated whether it is opened or not.

**The hover test, and the tooltip settings with it.** One session, one save,
paused throughout. Two minutes sweeping the mouse over the map and top bar with
**no clicks**; then Settings → Tooltip Settings with `Map Tooltips` set to
Disabled and both delays at maximum; then the same two minutes again. Send
`performance_degradation.log`. What each outcome means is in
[`investigations/widget_leak.md`](investigations/widget_leak.md) — read it
before asking for anything else, because the losing branch has its own next test
already written and it is not this one repeated.

~~**`ru_loc_fix` round two — eleven keys and four expansions, never in game.**~~
**Confirmed 2026-08-27** from the logs drop above: none of the six keys appears
in `error.log` any more.

**And one thing only eyes can check.** Whether the repaired Russian *reads*
correctly. The log says those keys no longer fail; it does not say the sentences
are right. Quickest look: a religion tooltip (harmony, purity, honor), the goods
filter chips in a location's buildings panel, and the price line in the build
panel.

## Never run

Kept here so it is one list rather than scattered through prose:

- whether anything in `goods_target` runs on a monthly pulse. Its lists,
  readings and ticks are confirmed on screen; nothing periodic is.
- `rgo_bonus_filter`'s build-panel chip. Его же **панельная пара чинилась**
  2026-09-09 по чужой причине: она читала `root`, и это была та же
  ошибка, что у `where_to_produce`.
- ~~**`where_to_produce`'s «В конце» plan.**~~ **Run 2026-09-03**, three times.
  What is still never run is **the whole plan on a large ground since the
  ladders were rebuilt**: Westphalia is 48 locations and its answer came back
  identical to the old build's, so nothing there tests the change. The press
  that would is the one of the earlier report — northern Germany, 233 locations,
  where the open pass used to place 271 buildings of 770.
- Everything `nd_ru` has translated apart from Westphalia — 3 600 keys that have
  never been on screen.
- ~~**All of `cm_maps`**, built 2026-09-15~~ — **loaded 2026-09-19**, and both
  the urban-rights and the governor mode drew. What is still never run is the
  **food-potential map**, the icon strip, and the two 2026-09-19 fixes
  themselves.
