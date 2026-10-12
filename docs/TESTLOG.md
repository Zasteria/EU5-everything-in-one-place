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

**2026-10-12 18:24–18:41, 1.4: `cm_dev_perf` (свежий, не ниже +perf36 — в строке есть `skipped`), Киев, его логи.** 69 циклов в уцелевших 4 МБ `debug.log`: **во всех `staged` = `scored`, `rescans 0`, `skipped 0`, `approved 1`, опросов 1–3**. Ворота +perf34 зовут каждую очередь; опрос раз в 1 с месяц не теряет. Месяц — 4–8 с реального времени; размер очереди чередуется (≈1000 и ≈80, позже ≈450 и ≈220) — срезы по 300 локаций идут через месяц. Ошибок CM в `error.log` нет. Шум не наш: `ARMY_LEVY_ALL_ENTRY` (9 407 раз, ванильная строка зовёт несуществующий `PROVINCE.GetArmyLevyPercentage`) и `teu_event_6_trigger` (1 222, ванильный текст). Автосохранение раз в ~2 мин держит игру 2.1 с. Карту прав и грамоты +perf38/39 логи не показывают.

**2026-10-12 (~11:45), 1.4: `cm_dev_perf` +perf34, дальше по той же партии.** (1) CM годами копил ~500 золота и не строил ничего, чтобы поднять деревню до городка при выключенной урбанизации, причём в столичной провинции. Это подготовка места губернатору (`cm_gov_rank_step`, держит казну через `cm_gov_hold`); снял галочку подготовки мест — пошёл строить другое. Было и до +perf34. (2) Производственные здания в городах не строил, пользовательские и RGO строил. **Отозвано им в 12:15:** на старом сохранении под тем же +perf34 производство строится, «вероятно я на том сохранении что-то просто не учёл». +perf36 (опрос назад на 0.3 с) отменён в +perf37.

**2026-10-12 (~11:30), 1.4: `cm_dev_perf` +perf34.** «На первый взгляд работает как раньше»; сломались ли ворота криков, на глаз не сказать — отсюда +perf35, строка цикла в `debug.log`.

**2026-10-12, 1.4, поздняя игра с CM (по памяти).** Тик терпим до конца даже в худшей стадии. Душит теперь **разовый месячный пересчёт** (фриз на смене месяца), а не скорость тика. Со временем — **микрофризы примерно раз в секунду**, сильнее при движении карты, **на паузе их нет**; скорость тика при этом высокая.

**2026-10-12, 1.4, с CM (по памяти).** Медленное начало месяца после пульса CM **есть и на 1.4**, но появляется «значительно позже», с ростом державы. И второе его наблюдение: открытое крупное окно (стройка) при снятой паузе сразу роняет скорость тиков.

**2026-10-12 (по памяти, раньше), 1.4: HRE Manager 1.1.0 (Workshop 3705462070), кроме него ничего нового.** Игра «знатно» тормозила, **и при закрытом окне тоже**. По файлам мод при закрытой вкладке не делает ничего ([`investigations/hre_manager_cost.md`](investigations/hre_manager_cost.md)) — расхождение не объяснено; он списывает на старую версию (1.1). Заодно: на 1.4 игра без тормозов играется до 4-й эпохи даже с CM; сейчас он пробует без CM, на ванильном автострое, «кажется так лучше».

**2026-10-12, 1.4: `ru_loc_fix` 0.4.3 + Russian Localization Fix 1.0.2 (Workshop 3813229007) последним в плейсете.** «Как мне показалось, он починил достаточно много вещей, которые не чинил наш мод». Какие именно ключи он видел изменёнными — не сказано. Всё нужное из того мода перенесено в 0.5.0; там же правило `unknown_custom` (около 400 вызовов несуществующих падежных функций).

**2026-10-06 (~14:40), 1.4: `war_sliders` 0.7.x.** Восстание (гражданская война с мятежниками) подавлено — ползунки сам не выправил. Война с мятежниками кончается своими крючками (`on_civil_war_*`), не обязательно `on_ending_war`; 0.7.2 висит на всех. Обычную войну после 0.7 он не упоминал.

**2026-10-06 (до 13:26), 1.4: `speed_10` 0.1.1.** Сначала сказал «8 слишком медленная, 9 слишком быстрая», в 13:39 поправил: перепутал, медленна 7-я (0.2), быстровата 8-я (0.15), 9-я (0.1) «бешеная». Искать между 0.2 и 0.15. 0.1.4 — его числа: 2.0 / 1.0 / 0.5 / 0.25 / 0.2 / 0.175 / 0.15 / 0.125 / 0.1 / 0.

**2026-10-06 (~00:41), 1.4: `speed_10` 0.1.0.** Десять скоростей работают все, кнопки 6–10 на верхней панели рисуются «как положено». Значит, число скоростей — длина таблиц `GAME_SPEED_TICKS`/`GAME_SPEED_SCALES`, движок пятью не ограничен. Паузы 0.08 и 0.04 для него от 0 не отличимы, 0.1 «слегка быстровата»; 0.1.1 — лестница 2.0 → 0.1 на 1–9, 10-я без ограничения.

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
