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

**2026-09-19, `cm_maps`, первый прогон — карты рисуются, две дыры в данных.**
Его слова: «Две карты — подбор городских прав и размещение губернатора глючат.
Некоторые области для гор. прав — просто ничего не показывают, хотя дают цвет и
окно, но описание пустое. Губернаторская карта тоже. Некоторые области чёрные,
мод говорит про какую-то настройку поиска, в общем он не может отсканировать всю
державу иногда.»

| что | что вышло |
| --- | --- |
| карты вообще загрузились и рисуют | **да** — первое подтверждение, что порт живой |
| «Рекомендуемые городские права» | часть локаций окрашена, а в подсказке три заголовка и ни строки под ними |
| «Рекомендуемый губернатор» | часть локаций чёрная, подсказка — `bcm_pf_tt_skipped` |
| `error.log`, `gui.log` | **от мода чисто**: ни одного `bcm_`. Всё, что там есть, — чужое (звуки строек, падежи товаров, виджеты CM после перезагрузки интерфейса) |

**Обе причины найдены в коде, ни одна не требовала второго прогона.**

*Чёрные области — наша правка, а не игра.* `bcm_pf_accuracy_value` порт сознательно
переписал с авторской единицы на тройку: «3 — это то, что видит игрок CM».
Игрок CM видит тройку потому, что **может подвинуть ползунок**; здесь страницы
настроек нет, и тройка — не запасное значение, а единственное. Уровни 2–5 идут
через фазовый обход, который часть локаций не оценивает и красит чёрным, а
подсказка над ними велит выставить «Исчерпывающую» точность — настройку, которой
в моде не существует. Вернули авторскую единицу: она одна ничего не пропускает.

*Пустые подсказки — ошибка самого CM, унаследованная портом.* Ворота прохода
берут определение провинции, если **хоть у одной** локации в нём есть сырьё
**или** бонус к выпуску. Покрытие считается на всё определение, поэтому сырьевая
половина ворот никого не метит зря, а бонусная — метит: в определении, прошедшем
только из-за чужого бонуса, у остальных локаций все девять прав получают ноль, и
кодировка `round(score*1000)*10 + index` разрешает ничью нулей в пользу старшего
индекса — 9, инструменты. Локация красится «Королевскими правами на инструменты»
и открывает подсказку с тремя пустыми списками. Теперь ноль не метится вовсе, и
локация уходит в `..._TT_NONE`, чей текст («в провинции нет сырья, используемого
специализированными производствами») для неё ровно верен.

**Обе правки — в `port_from_cm.py`, не в сгенерированных файлах**, и к ним
одноразовая миграция в `bcm_run_lobby_setup`: она снимает `bcm_trmm_stamp`
(иначе проход не переиграется) и `bcm_pf_fresh_g` (иначе кэш губернаторской
карты держится 1460 дней). **В игре не проверено.**

**2026-09-18, `cm_perf`, две просадки скорости** — накопительная за сессию и
месячная, обе разобраны и обе закрыты; вынесены в
[`archive/testlog_cm_perf_0918_slowdowns.md`](archive/testlog_cm_perf_0918_slowdowns.md).

**2026-09-18, CM и скорость игры, первые два захода** — замер FPS снял
объяснение через время кадра (на 6 скорости 90-110 кадров при симуляции уровня
4-й), а ворота на дереве типов зданий сняли потолок. Оба целиком в
[`archive/testlog_cm_perf_0918.md`](archive/testlog_cm_perf_0918.md); вывод — в
[`SETTLED.md`](SETTLED.md).

**2026-09-16 — 2026-09-17, `war_sliders`, три захода — мод работает, включая
войну.** Его слово по третьему: «работает отлично… всё работает так как мне и
нужно было». Привод (переменная страны → скрытый ползунок → движок), пределы
содержаний, измеряемый темп правки инфляции и находка про числа движка в
скрипте — целиком в
[`archive/testlog_war_sliders_first.md`](archive/testlog_war_sliders_first.md),
куда история уехала 2026-09-18.

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
- ~~**All of `cm_maps`**, built 2026-09-15~~ — **loaded 2026-09-19**, and both
  the urban-rights and the governor mode drew. What is still never run is the
  **food-potential map**, the icon strip, and the two 2026-09-19 fixes
  themselves.
