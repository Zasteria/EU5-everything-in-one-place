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

**2026-09-18, `cm_perf` — ворота на дереве типов зданий сняли потолок скорости.**
Его слова: «скорость стала явно выше… она высокая на 6 скорости без
максимизации тактов. Если её включить — ничего не меняется, но оно и не особо
надо… с твоими правками игра стала значительно отзывчивей и быстрее».

| что | что вышло |
| --- | --- |
| 6 скорость без максимизации тактов | **быстро**, прежнего потолка нет |
| галочка максимизации тактов поверх этого | ничего не меняет — и не нужна |
| сравнение с игрой без CM | не мерено: на больших скоростях на глаз не сравнить |
| функционал CM | не проверен, нужны часы игры |

**Что это закрывает.** Причина потолка названа и снята: **всегда живое дерево по
всем типам зданий** в скрытом окне CM
([`investigations/cm_performance.md`](investigations/cm_performance.md)). Правка —
те же ворота, что у его драйвера, `mods/cm_perf`.

**И это же подтверждает, что классификация прошла.** В 2.2.12
`cm_populate_building_types_to_process` вооружает её **каждую загрузку** и ничего
не переиспользует (`cm_game_load_setup_effects.txt:4-14`), а ворота закрываются
только когда обработаны все типы. Провались проход — дерево стояло бы дальше и
игра была бы ровно такой же медленной. Быстрая игра и есть тот счётчик.

**Чего прогон не сказал.** Два вложенных прохода — спрос на стройку по товарам и
производимый товар — срабатывают позже внешнего, а их ряды рождаются позже.
Недосчитай они, счётчик всё равно полон и ворота всё равно закроются. Видимая
проверка на это одна и она в брифе `cm_perf`: строка дефицита в подсказке
галочки авторасширения.

**2026-09-18, `construction_manager`, замер FPS — потолок скорости игры не в
кадрах.** Его слова: «на 6 скорости с галочкой макс тиков и без, с выключенной
автоматизацией и без — всегда примерно от 90 до 110 фпс»; «с включённым cm я
наблюдал на паузе примерно 160-180 фпс. А без cm на паузе 180-220»; «сильно
прыгает фпс из-за постоянных пересчётов ежемесячных». Какой из двух билдов CM
стоял, не уточнялось.

| что | что вышло |
| --- | --- |
| FPS на паузе, с CM против без CM | 160-180 против 180-220 — CM стоит около 15% кадра |
| FPS на 6 скорости, четыре комбинации: галочка максимизации тактов ×2, автоматизация CM ×2 | всегда 90-110, между комбинациями разницы не видно |
| ежемесячные пересчёты | видны как скачки FPS |

**Что прогон закрывает.** Объяснение «CM роняет FPS, а такты считаются в темпе
кадров, поэтому слайдер скорости выше четвёртой ничего не меняет» — **отпало**.
На 6 скорости кадров 90-110, этого с запасом, а симуляция всё равно идёт как на
4-й. Постоянно живое дерево по всем типам зданий в `cm_hidden_window.gui`
(корень на `EqualTo_CFixedPoint('0','0')`, датамодель без `visible`) стоит около
15% кадра — цена настоящая, но не та причина.

**Чего прогон не сказал.** Мерился FPS, а не скорость симуляции. Сколько игровых
дней проходит за секунду реального времени — с CM, без CM и с приостановленной
автоматизацией — не считал никто, поэтому потолок «максимум 4 из 7 при живом CM»
остаётся без названной причины. Это и есть следующий замер: три раза по тридцать
секунд с часами, разница дат.

**2026-09-17, `war_sliders` 0.3, третий заход — мод работает, включая войну.**
Сборка `7130d26e`. Его слово: «работает отлично. Проверил и на диагностике и на
войне, всё работает так как мне и нужно было».

| что | что вышло |
| --- | --- |
| страница настроек в меню CMF | есть, тумблеры и значения читаются |
| «Сработать сейчас» | содержания уезжают на своё значение |
| настоящая война | по выходу из войны всё падает само, как задумано |
| правка инфляции чеканкой | идёт и доводит до нуля |

**Единственный недостаток — темп правки был слепым.** Мод держал чеканку на полу
до тех пор, пока инфляция не сойдёт к цели, и последний месяц отрабатывал на
полную: «когда инфляция снижается до 0.05, мод всё равно продолжает снижать на
максимальные 0.10% … эти 0.04% — значительная сумма». И темп не константа: он
«может меняться от разных моментов вроде привилегии горожан».

**Ответ, и он не прогонялся:** темп теперь **измеряется** — сколько инфляции
ушло за прошлый месяц при том положении ползунка, которое держал мод, — а
последний месяц ставится на `m0 − R × (m0 − пол) / D`, где `m0` — точка нулевого
прироста, снятая с ползунка в момент, когда мод его перехватил. Промах
самоисправляется: следующий месяц просто делает ещё один маленький шаг.

**Заодно установлено, что скрипту доступны числа движка**, которые до сих пор
считались интерфейсными: триггер страны работает как значение
(`set_variable = { name = x value = slider_minting_value }`) — форма самой
ваниллы (`value = stability`).

**2026-09-16 — 2026-09-17, `war_sliders`, первый и второй заходы** — привод
найден: скрипт пишет число в переменную страны, скрытый виджет держит на нём
ползунок, привязанный к `GetEconomyView`, движок применяет. Там же пределы
содержаний (`MaintenanceSetting.GetMin`), и что `GetEconomyView` берётся
выражением данных, но не колбэком и не датамоделью. Полностью:
[`archive/testlog_war_sliders_first.md`](archive/testlog_war_sliders_first.md).

**2026-09-14, заходы девятнадцатый—двадцать первый** — «Грамоты поровну» принято
(разброс 3–6), разъехавшийся ряд галочек в окне плана, «Из плана — сюда» с
отставанием ровно на одну локацию, и прогон не в том режиме, который сессия
«починила» вслепую. Целиком —
[`archive/testlog_0914_passes_19_21.md`](archive/testlog_0914_passes_19_21.md).
**Общее из них: переключить фильтр панели из скрипта нечем, а разрез по живой
строке раскладки виден только глазом — `check_script` ловит ширину, не смысл.**

**2026-09-14, восемнадцатый заход — лесенка грамот предложила невозможное.**
Ювелирная грамота 100 % на городе, а в разборе «Торговая деревня, Сельский
ювелир 1/1»: `_stands_<здание>` под галочкой ранга сам ранг не спрашивал.
Подробности и вторая находка (подсказка шапки столбца без локации, 13 строк в
`error.log`) — [`archive/testlog_0914_pass_18.md`](archive/testlog_0914_pass_18.md).

**2026-09-14, ванильный костыль автостроя — два прогона, и оба против него.**
CM выключен. Сборки `be45c5`, `fa76e2`, `970a21`. «Первый ярус» работает (но
иногда нужно нажать дважды), «авторасширение» не встало ни разу. **Попытка
снята целиком по его решению, дерево мода откачено**; таблица, что эти прогоны
установили и чего не установили —
[`archive/wtp_vanilla_autoexpand_attempt.md`](archive/wtp_vanilla_autoexpand_attempt.md).

**2026-09-14, `glorpui_hints` без Glorp UI — полоски встали, подсказка осталась
без главного списка.** Вклеенный блок Glorp UI держит ванильный список за их
переменными, которых без мода нет, — и гаснет весь целиком. Выпущен свой, под
теми же ключами, с воротами «Glorp UI не зарегистрировался в CMF». **Прогона не
видело**, разбор —
[`archive/testlog_0914_glorpui_hints.md`](archive/testlog_0914_glorpui_hints.md).

**2026-09-14, заходы двенадцатый—семнадцатый** — окно замены, «Пригодность»,
первый прогон с логами и счёт грамот, который показал себя и оказался бредом
(90650 %, сельский стекольщик в городе, Сёэн в Вестфалии). Всё починено, разборы
в архиве: [`archive/testlog_0914_pass_12.md`](archive/testlog_0914_pass_12.md),
[`archive/testlog_0914_passes_13_15.md`](archive/testlog_0914_passes_13_15.md),
[`archive/testlog_0914_pass_17.md`](archive/testlog_0914_pass_17.md).
**Из них общее: ошибка была не в формуле, а в том, что её не спрашивали о
локации**, и логи стоит просить всегда — три ошибки из четырёх нашлись только
там.

**2026-09-14, пятый—одиннадцатый заходы** — окно замены, карты городских
прав, счёт грамоты против карты, и пять правил, ушедших в `check_script.py`:
[`archive/testlog_0914_passes_5_11.md`](archive/testlog_0914_passes_5_11.md).

**2026-09-09 — 2026-09-13, прогоны до его списка** — второй заход, сборка
`242ff0`, первая «Перетасовать» и разбор «Расширить»:
[`archive/testlog_wtp_2026-09-09_13.md`](archive/testlog_wtp_2026-09-09_13.md).
**2026-09-14, шестой—одиннадцатый заходы — одно окно, пять сборок, четыре
догадки.** Таблица целиком —
[`archive/testlog_0914_passes_5_11.md`](archive/testlog_0914_passes_5_11.md);
разбор ошибок и порядок действий, который из них вырос, —
[`pitfalls/how_to_fix.md`](pitfalls/how_to_fix.md). **Автострой закрыт его
решением**: почему заглушку подсунуть нечем — в [`RESEARCH.md`](RESEARCH.md),
предлагать снова не надо.

**2026-09-14, пятый заход — счёт грамот сошёлся с картой, две дыры измерены**,
и мод взвешен (20 → 17 МБ, 2.82 МБ оказались повторёнными комментариями):
[`archive/testlog_wtp_2026-09-14_fifth.md`](archive/testlog_wtp_2026-09-14_fifth.md).

## Waiting on a run

The next session should start here rather than designing anything new. All of
these are prepared, all are cheap, and the owner has agreed to the hover one.

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
- **All of `cm_maps`**, built 2026-09-15: three CM dev maps standing without CM.
  Nothing in it has been loaded — not the three modes, not the icon strip, not
  the placement search. What one load would settle is in its brief.
