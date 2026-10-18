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

**2026-10-18 (сообщение 17:09 UTC), 1.4.1: `glorpui_hints` 1.2.14, его слова.** «Мод я уже проверил и вроде как указанные мной вещи были поправлены хорошо»: эпоха у «Элитной подготовки» и строка доли солдат. Что именно смотрел на экране, не сказал.

**2026-10-18 (сообщение 15:47 UTC), 1.4.1: `glorpui_hints` 1.2.13, Пфальц, его скриншоты.** Ссылка условий работает: наведение на «(II)» у «Элитной подготовки» в «Ещё не доступно» открывает «Условия: Сейчас НЕ Эпоха Революций». **Цифра неверна**: «(II)» — эпоха теха, открывающего закон о вербовке, а `allow` политики хочет шестую. Подсказка игры: «Процент солдат −0.05» при 1.40 % солдат в населении (10 791 из ~771 тыс.) — сходится с `soldier_percentage_in_country`: доля дробью × 20, не больше 1, × 0.2 (0.014 × 20 × 0.2 = 0.056). → 1.2.14.

**2026-10-14 (сообщение 17:26 UTC), 1.4.1: `nd_unnerf` 0.1.1.** Его слова: «Вроде работает», после правки до пяти знаков. Какие подсказки он смотрел (бюрократия, «Льняная промышленность»), не сказано.

**2026-10-14 (сообщение 17:17 UTC), 1.4.1: `nd_unnerf` 0.1.0, бюрократия Вестфалии Markgenossenschaft.** В положительном модификаторе остались два эффекта из трёх, сепаратизм и довольство; роста населения нет вовсе. Значит, `REPLACE:` бюрократии сработал (иначе стояло бы 0.00025 автора), а пропало ровно то число, что записано с шестью знаками: 0.002175. В `common/` игры и ND шестого знака нет нигде (пятый — 67 раз). В его `error.log` строк о моде нет, но лог начинается с 22:11, через три минуты после старта, то есть загрузка в него не попала. → 0.1.1: не больше пяти знаков (0.00218).

**2026-10-14 (сообщение 08:50 UTC), 1.4.1: `cmf_saved_settings` 0.1.1, `last.txt` после закрытия игры.** Блок целый: 611 строк, 62 строки порядка, `end count=611`. **Хвост `debug.log` при открытой игре не дописан** — тот же блок без трёх последних строк в 08:43. Два «безымянных» — `cmm_init`, служебный ключ CMF. `GetValue` совпал с script value во всех 611; `TopScope.GetFlagName('<scope>')` печатает пусто. Настройки у семи модов: cm 435, qol 68, bag_asp 68, glorpui 20, bag_wsl 11, cmf_core 6, svx 1. → 0.2.0: применение.

**2026-10-14 (сообщение 08:43 UTC), 1.4.1: `cmf_saved_settings` 0.1.1, вывод `mods.bat` → 5.** Настроек 611, с читаемым именем 609, строк порядка 60 из ожидаемых 62 (38 прав CM + 24 «Приоритета»), `end` нет. **Причина 0.1.0 подтверждена:** параметр только в кавычках — правило в `pitfalls/cmm.md` и `check_script.py`. `GetFlagName` на глобальной в `debug_log` имя печатает. Хвост из трёх строк, по-видимому, не дописан в лог, пока игра открыта — не проверено; два безымянных ключа не разобраны, `last.txt` попрошен.

**2026-10-14 (сообщение 08:35 UTC), 1.4.1: `cmf_saved_settings` 0.1.0, вывод `mods.bat` → 5.** Загрузил сейв, нажал «Сохранить»: в блоке только `CMFSAVE begin 1`, ни одной настройки, ни `end`. Логи не смотрены. Подозреваемый: `bag_cmfs_print = { kind = c }`, где `$kind$` стоял только в кавычках — там макрос не подставляется (комментарий CMF), параметр не объявлен, и вызов уносит остаток эффекта. → 0.1.1: параметров в кавычках нет, строки `CMFSAVE stage`.

**2026-10-15 (сообщение 12:24 UTC, журнал 17:23), 1.4.1: `assimilate_primary` 0.10.5, зонд.** Урбанизация доступна, но провинций с `unfilled_jobs_in_province > 0` ноль. У самой населённой, Северной Мунтении, значение −1.82, а на его скриншоте в Слэнике −684 работника. Нехватка — отрицательное число. → 0.10.6, условие `< 0`. Мест контроля в этом журнале не было, поэтому про переключение контроля зонд ничего не сказал.

**2026-10-15 (сообщение 11:58 UTC, журнал 16:57), 1.4.1: `assimilate_primary` 0.10.4.** Его слова: урбанизацию не берёт ни один советник. В журнале `pop_promote_action` выше развития по приоритету, но место не получает ни разу. Ошибок от мода нет, хотя `error.log` начинается только с 16:52. Его настройки: `control_boost` 10, `control_take` 10, `develop_control` 40, `develop_seats` 1. Ещё одно: советник с adm 40 каждый месяц переходит с Noblesse Oblige на повышение контроля и обратно («stopped on a seat» / «seat set to»). Причины обоих не названы. → зонд 0.10.5.

**2026-10-15 (сообщение 11:11 UTC), 1.4.1: `assimilate_primary` 0.10.3, его слова.** 0.10.3 не запускал. Развитие, по его наблюдению, уходит с провинции, когда до цели дошло среднее развитие; нужно, чтобы цели достиг каждый район. Его цифры по контролю: задание даёт около +2.5 % контроля в месяц, без советника контроль спадает к обычному максимуму на 0.5 % в месяц. Значит, одно задание может держать по кругу 4–5 провинций выше их максимума. → 0.10.4.

**2026-10-15 (сообщение 10:56 UTC), 1.4.1: `assimilate_primary` 0.10.2, его слова.** «Стимулирование урбанизации» держится на провинции, где незанятых мест для повышения уже 0, и не уходит ни на другую провинцию, ни ниже по списку. У строки не было условия на цель: порядок по населению, место держалось всегда. → 0.10.3.

Runs of 10-14 from 06:35 to 13:30 (`assimilate_primary` 0.9.22–0.10.1, «Мрамор»): [`archive/testlog_1014_morning.md`](archive/testlog_1014_morning.md).

Runs of the early morning of 10-14 to 06:00 UTC (`assimilate_primary` 0.9.18–0.9.21): [`archive/testlog_1014_early.md`](archive/testlog_1014_early.md).

Runs of the evening of 10-13 and the night of 10-14 (`cm_dev_perf` +perf41, the tempo logs of 00:47–00:57): [`archive/testlog_1013_evening.md`](archive/testlog_1013_evening.md).

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

**`cmf_saved_settings` 0.3.0 + `mods.bat`** (10-14): пункт 3 (ставит 0.3.0 и
сразу кладёт в него `last.txt`), пункт 5 (удаляет старый «CMF: мои настройки» —
выключить в плейсете), **новая** партия. Верно: настройки его, в `debug.log`
строка `CMFMY pass applied=N of 611` с N около 600.

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
7. **0.6.0, отрасли, список на CMF:** Молдавия — текстиль во всех трёх; в
   подсказке режим 1: 3/2/1, ремёсла 0.67; 2: текстиль = напитки = 2; 3:
   ремёсла и роскошь 0.75 (по стартовым файлам).

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
