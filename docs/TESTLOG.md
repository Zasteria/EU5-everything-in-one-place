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

**2026-10-14 (сообщение 06:48 UTC), 1.4.1: его скриншот подсказки «Мрамор — потребность населения».** Аристократы потребляют мрамор, когда развитие района превысит 40. В файлах игры это `development_threshold` товара: 20 (стекло, бумага, тонкое сукно, фарфор, лаковые изделия, поделочная кость, жемчуг), 30 (книги), 40 (мрамор). Его правило: развивать от столицы наружу. → 0.10.1.

**2026-10-14 (сообщение 06:35 UTC), 1.4.1: `assimilate_primary` 0.9.22, его слова.** «Ну, вроде пошёл ассимилировать» — «до 50 %» снова берёт провинции после замены `NOT` на `NAND`. Его просьбы там же: развитие на нескольких советниках, цель развития в настройках, число мест на развитии числом. → 0.10.0.

**2026-10-14 (лог 11:17), 1.4.1: `assimilate_primary` 0.9.21, его лог.** Зонд показал одну провинцию, Средний Везер: район Дипхольц, чужие жители есть, `bag_asp_assimilable_any` ложен, и ни одно правило по отдельности (племена, иудаизм, самаритянство, блок сословия в районе или стране) их не ловит. Причина: `NOT = { pop_type = X  OR = {…} }` — это NOR, все сословия исключались. → 0.9.22, `NAND`.

**2026-10-14 (сообщение 05:59 UTC, лог 10:54), 1.4.1: `assimilate_primary` 0.9.20, его рассказ и логи.** Зонд видит четыре провинции, все «not taken, its foreign pops are all locked»: Мюнстерланд, Падерборнское плато (ранг 50300/60300), Средний Везер, Восточная Вестфалия. По его словам: в Мюнстерланде иудеи только в районе Мюнстер, а рядом его интегрированный район без ашкеназов; на плато в его трёх районах (контроль > 40 %) ашкеназов нет, они в Падерборне, который не его. Проверка мода уже идёт по районам, так что чужой район её не валит; какое правило блокирует — не названо. → зонд 0.9.21.

**2026-10-14 (сообщения 05:38–05:40 UTC), 1.4.1: `assimilate_primary` 0.9.18, его рассказ и те же логи.** «До 50 %» стоит в «Приоритете» выше развития, интегрированная земля есть, но ассимиляцию никто не берёт, а развитие и «Укрепление правительства» ниже по списку идут. В логе 10:02 зонд видит только Мюнстерланд и Восточную Вестфалию (порог зонда 40 % контроля), обе «not taken, no location integrated or conquered short of half»: Мюнстер — иудеи (0.9.17), Восточная Вестфалия — причина не названа. → зонд 0.9.20.

**2026-10-14 (сообщение 05:05 UTC, логи до 10:02 его времени), 1.4.1: `assimilate_primary` 0.9.18, два скриншота.** «Крепостничество» стоит на 63.30, игра пишет +0.62 в месяц (советник +0.17, «Независимые деревни» −0.10), то есть предел ≈ 62. Советник каждый месяц уходит на пустую задачу, потом на централизацию и снова на крепостничество, а пара не двигается. По логу перед проходом место уже пустое: игра сама снимает действие, когда пара не может сдвинуться. Модификатор в этот месяц ещё несёт толчок советника: прочитано 0.6285, и мод прибавил толчок второй раз (+0.1591), получив предел 78.76. Окно пару не показало (таймаут), перескок нажал её через централизацию. → 0.9.19.

**2026-10-14 (логи 00:47–00:57 его времени), 1.4.1: те же сборки, что в 19:45, его логи.** **Темп:** 49 игровых месяцев, ровно 4–6 с реального времени на месяц (≈0.15–0.2 с на день — его «как 0.15»); три провала 44–77 с — по виду пауза. **`error.log` непрерывно не пишет ничего:** все всплески совпадают с его действиями — окно отряда 00:52:56–00:53:05 (~75 строк/с «const context … Unit», `cmfg_single_unit_window_vanilla_types.gui` Glorp/CMF), подсказка рекрутов 00:52:08 (ванильная русская `ARMY_LEVY_ALL_ENTRY` зовёт `PROVINCE.GetArmyLevyPercentage`, которого в 1.4.1 нет — есть только `…ForCountry`), экономика 00:55:08–15, подсказка отношений 00:55:55–57. **Наши моды в логе:** месячный проход совета и цикл CM укладываются в ту же секунду, что смена месяца (CM 0–3 с после); в днях между ними ни один не пишет. Проход отраслей +perf41 — один раз при загрузке (00:48:30). **Причина логами не названа:** в них нет ни кадра, ни дня. Попрошено сравнение на одном сохранении: без совета и без `cm_dev_perf` — месячные строки другого мода служат секундомером.

Runs of 10-13 from 12:19 to 19:45 (`assimilate_primary` 0.9.14–0.9.18, Integration Hotfix 0.7): [`archive/testlog_1013_day.md`](archive/testlog_1013_day.md).

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

**`cmf_saved_settings` 0.1.0** (10-14): CMF → «Мои настройки» →
«Сохранить», затем до перезапуска `mods.bat` → 5, приложить `last.txt`. Верно:
у каждой строки `CMFSAVE c/g` имя `мод__настройка` и число.

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
