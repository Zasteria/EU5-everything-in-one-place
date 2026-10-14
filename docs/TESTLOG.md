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

**2026-10-13 (сообщения 20:37–20:39 UTC), 1.4.1: `cm_dev_perf` +perf41, его рассказ.** **Тормоза:** он играет императором СРИ; до Золотой буллы малые страны массово объявляли войны без повода, после её принятия скорость, на его глаз, вернулась к норме. Вывод его, не замер. **Житница CM растит RGO «скот» при нехватке рабочих** (его поправка в 20:43: не деревня, и не хватает именно рабочих): нехватка 3 500, CM накопил золото и построил ещё уровень — стало 4 300. Причина в коде, тот же в CM Dev 2.3.0: авто-еда пускает RGO при одном безработном любого типа, а слив строит уровни до потолка размера RGO, сколько позволят слоты и золото, не глядя на рабочих. Наши правки (крики, опрос, оценка) этого пути не меняли — сверено диффом с CM Dev. → +perf42.

**2026-10-14 (логи 00:47–00:57 его времени), 1.4.1: те же сборки, что в 19:45, его логи.** **Темп:** 49 игровых месяцев, ровно 4–6 с реального времени на месяц (≈0.15–0.2 с на день — его «как 0.15»); три провала 44–77 с — по виду пауза. **`error.log` непрерывно не пишет ничего:** все всплески совпадают с его действиями — окно отряда 00:52:56–00:53:05 (~75 строк/с «const context … Unit», `cmfg_single_unit_window_vanilla_types.gui` Glorp/CMF), подсказка рекрутов 00:52:08 (ванильная русская `ARMY_LEVY_ALL_ENTRY` зовёт `PROVINCE.GetArmyLevyPercentage`, которого в 1.4.1 нет — есть только `…ForCountry`), экономика 00:55:08–15, подсказка отношений 00:55:55–57. **Наши моды в логе:** месячный проход совета и цикл CM укладываются в ту же секунду, что смена месяца (CM 0–3 с после); в днях между ними ни один не пишет. Проход отраслей +perf41 — один раз при загрузке (00:48:30). **Причина логами не названа:** в них нет ни кадра, ни дня. Попрошено сравнение на одном сохранении: без совета и без `cm_dev_perf` — месячные строки другого мода служат секундомером.

**2026-10-13 (сообщение 19:45 UTC), 1.4.1: `cm_dev_perf` +perf41, `assimilate_primary` 0.9.18, `integration_fix` 0.2.0, его рассказ.** «Вроде всё работает» — без подробностей, что именно смотрел. **Тики медленные даже на последней скорости** (без паузы между днями), на глаз как 0.15 с между днями. По сегодняшнему диффу ни одна правка не считается каждый день: проход отраслей — при загрузке, автоматика совета — раз в месяц, CMF-страница — только открытая. Причина не названа; попрошен прогон-сравнение.

**2026-10-13 (сообщения 18:25–18:30 UTC), 1.4.1: `assimilate_primary` 0.9.16, его рассказ и два скриншота.** **Закрытие:** после нажатия мода окно закрывается сразу, и через 2 с ещё раз — закрывая то, что он успел открыть (`bag_asp_sv_wait` закрывал без условия). **Ассимиляция навсегда:** Мюнстерланд, город Мюнстер 97.7 % вестфальцев, 100 % контроля, ашкеназы 0.9 % (иудаизм); подсказка игры: «ни одну из групп населения нельзя ассимилировать», советник держит провинцию. **Закон в принятии:** пока закон вводится, его толчок к паре растёт, предел растёт, и советник каждый месяц берёт пару на волосок — окно дёргается ежемесячно. **Подсказка «Ассимиляция провинции … в ую культуру»** на месте, ушедшем с ценностей, показывает старый сдвиг к «Общинности», а ценности уже толкает другой советник к инновациям. → 0.9.17.

**2026-10-13 (сообщение 17:39 UTC), 1.4.1: Integration Hotfix 0.7 из мастерской, новая партия, четыре скриншота.** Эмсланд, «Интеграция провинции», 3 района. **Подсказка действия: две строки, +1.00 и +0.50** — `INJECT` хотфикса добавил второй `province_modifier` к ванильному, а не заменил его. Навык +80.21 % → «Скорость интеграции +2.70» = 1.5 × 1.8021. В районе: база +0.16 (= 0.5 / 3 — **`province_base` хотфикса без префикса в `000_` победил ванильный `province.txt`**), +0.60 и +0.30 (= 1.0 и 0.5 × 1.8021 / 3), дипломатический вес +4.32 %, доминирующая культура +100 % → **+2.18 в месяц**; расчёт даёт 2.1816. Ваниль 1.4.1 дала бы ≈1.30, `integration_fix` 0.1.0 — ≈1.57; 0.2.0 ставит кабинет 1.5 (Занзибар 2.5) и возвращает 2.18.

**2026-10-13 (сообщение 12:19 UTC), 1.4: `assimilate_primary` 0.9.14, его скриншот.** Советник на «Качестве»: ценность −20.70, «(+0.00)» в месяц, толчок советника +0.20, эффективный навык 104.85 % (ДИП 64, правитель 9). Пара стоит: чистый сдвиг ≈ 0. Правило в 12:50:54 взяло её при чистом сдвиге −0.009 — проверялся только предел, не сам сдвиг. Значение идёт на чистый сдвиг в месяц (централизация 37.66 → 38.18 за месяц при +0.52), предел его лишь обрезает. **Его правило:** шаг не меньше 0.05, лучше 0.10, кроме дотягивания до 100.

Runs of the morning of 10-13 to 07:55 (`assimilate_primary` 0.9.6–0.9.13, the first value-window probes): [`archive/testlog_1013_morning.md`](archive/testlog_1013_morning.md).

Runs of the night of 10-13 (`assimilate_primary` 0.9.0–0.9.1): [`archive/testlog_1013_night.md`](archive/testlog_1013_night.md).

Runs of the evening of 10-12 (`assimilate_primary` 0.5.0–0.8.5 on `cmf_dev_beta`, and the two value probes of 23:02 and 23:12): [`archive/testlog_1012_evening.md`](archive/testlog_1012_evening.md).

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
