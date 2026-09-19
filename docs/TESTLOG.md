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

**2026-09-20, зонд и логи — секундомер работает, и в логах нашлась поломка
игры, которую чинит наш же мод.**

**Секундомер жив.** Его слова: «по началу было 4-5 сек на месяц, потом по
чуть-чуть дошло до 7-9 сек на месяц… минут 10-15 посидел». То есть
**деградация вдвое за десять-пятнадцать минут, в числах**. Ни одной строки
`bag_wpr` в логах — мёртвых выражений в зонде не осталось.

**А счётчики детей он подтвердил бесполезными**: «количество виджетов не
менялось, что и где бы я ни тыкал». Это структура, а не утечка, и мерить ею
нечего.

**Логи той же сессии: 5310 строк `error.log` за 87 секунд.** Самый частый
источник — один тултип игры:

| ключ | строк | что не так |
| --- | --- | --- |
| `BUILDING_TYPE_PROFIT_TT` | **362** | `LOCATION.GetRank.Custom('LR_PREP')`. `LR_PREP` объявлен `type = location` (`ru_EU5_custom_loc.txt:46422`), а ключ зовёт его с ранга. Чинится переписыванием на `LOCATION.Custom('LR_PREP')` — **сделано в `ru_loc_fix`**, 209 ключей вместо 207 |
| `longname_ru_GEN` на стране | **668** | «Object of type 'country' is not valid». Объявлен суффиксом с `parent = country_ru_flavor` (`ru_EU5_custom_suffix.txt:3926`), а зовут его прямо со страны — и сама игра тоже (`country_history_l_russian.yml:7`). Правильной формы ещё не знаем, чинить пока нечем |
| `MARKET_SURPLYS_INFO`, `GOODS_PRODUCED_IN_LOCATION_MARKET_TRIGGER` | по 15 | **наша починка второго круга не сработала**: развёрнутый `AddTextIf(EqualTo_string(…, GOODS.…))` всё равно не резолвит `GOODS` в этих двух ключах |
| `glorpUI_country_header.gui:34` | немного | чужое, было и раньше |

**Что это стоит в скорости, не измерено**, и утечку оно не объясняет; но 362
провала за полторы минуты — это то, что видно и чинится.


**2026-09-19, `widget_probe` — перепись корня закрыта.** Скриншот плюс логи.

| что спросили | что ответил движок |
| --- | --- |
| `AccessChild('(int32)N')` на `_root_`, N от 0 до 23 | **`Promote 'AccessChild' returned nullptr`** на каждом. Перечислить детей нечем — дорога закрыта |
| `FindChild('cm_construct_queue_window')` от `windows_layer` | nullptr, но CM в этом прогоне и не стоял — строка ничего не доказала |
| `_root_`, `windows_layer` | 23 и 33 ребёнка. Стоят на месте: «по-моему там ни одно число не изменилось» — он прав, это структура, а не утечка |

**Пустая строка — это не ноль, а неразрешённое выражение.** Ни одного `ERROR`
на экране не было: нулевой виджет **гасит всю строку целиком**, вместе с
литеральным текстом вокруг. Отличить «ноль детей» от «виджета нет» на экране
нельзя — только по `error.log`.

**И зонд писал по три строки в лог на каждую такую строку каждый кадр** — 698 за
короткую сессию; мёртвые строки убраны. Вместо них секундомер месяца: «все эти
замеры я делать не собираюсь целенаправленно, для этого твои зонды есть».


**2026-09-19, `widget_probe` — `PdxGuiDestroyWidget` из мода работает.** Он
нажал кнопку, жертва пропала. **Вызов доказан в игре**, и это первый рычаг
против утечки, который у мода вообще есть. Профайлер мёртв: кнопку он жал тоже,
`PdxProfilerGetFrameTimeMs` так и вернул «−», строка убрана.

**2026-09-19, CM и скорость — он описал форму, и она не та, под которую я
правил.** Его слова: «Я тебе хоть раз жаловался, что ежемесячный пересчёт —
долгий? Нет… Основной паттерн: идёт пересчёт месячный, потом первые пару игровых
дней очень замедленны (будто бы игра что-то ещё досчитывает), потом идёт разгон
постепенный до нормальной скорости… к 8-10 дню скорость полностью
восстанавливается. И всё бы ничего, но с течением игры срок медленного
начального тика дней становится длиннее, разгон тоже», пока медленное не
занимает весь месяц. **Лечится перезагрузкой.** Без CM то же жирное сохранение
4 эпохи — «просто молния скорость».

| что это исключает | почему |
| --- | --- |
| месячный пересчёт как причина | он «не особо отличается от базовой игры» — его прямые слова |
| правка 4 (пульс раз в три месяца) | целилась в пересчёт, а не в то, что болит. **Выключена по его слову в тот же день: «верни ежемесячную».** Месячный пульс не трогать |
| что растёт в сохранении | перезагрузка лечит, а сохранение то же — значит растёт **в процессе** |

**Названный механизм** — слив очереди зовёт `PdxGuiTriggerAllAnimations`,
глобальную функцию, обходящую всё дерево виджетов, кругами; цена = длина очереди
× число виджетов в процессе. С файлами и строками:
[`investigations/cm_performance.md`](investigations/cm_performance.md). **В игре
не проверен**, и проверку через режимы карты он делать отказался — мерить должен
зонд, поэтому в нём теперь секундомер месяца.


**2026-09-19, `widget_probe` — первый прогон зонда** (дерево над окном мелкое,
профайлер мёртв). Вынесено:
[`archive/testlog_widget_probe_first.md`](archive/testlog_widget_probe_first.md).


**2026-09-18, `cm_perf` и фон — деградация за 20 минут, и это не CM.**
Его слова: правка очереди дала «слегка плавнее, но это субъективно», а скорость
всё равно «деградирует в течении минут 20… потом стабильно медленно».

| что | что вышло |
| --- | --- |
| правка очереди строек (одна развёртка за цикл) | «слегка плавнее», на глаз неотличимо от плацебо |
| общая картина | деградация за ~20 минут до стабильно медленной |
| загрузка сохранения **изнутри партии** | деградацию **не снимает** |

**Он прав, что это не CM.** Форма — накопление по времени сессии, а не месячный
ритм, и это [**утечка виджетов**](investigations/widget_leak.md), меренная пятью
прогонами и установленная как игровая: с выключенными модами та же деятельность
течёт **+1.99** виджета на кадр против **+1.86** с полным плейсетом.

**Два уточнения, оба уже перенесены в
[`investigations/widget_leak.md`](investigations/widget_leak.md)**: плато после
~20 минут бывает, и «перезагрузка снимает» значит выход в главное меню, а не
загрузку изнутри партии.

**2026-09-18, `cm_perf` — месячный ритм и первые два захода** (замер FPS,
ворота на дереве типов зданий). Вынесено:
[`archive/testlog_cm_perf_0918.md`](archive/testlog_cm_perf_0918.md).


**2026-09-14, заходы девятнадцатый—двадцать первый** — «Грамоты поровну»
принято; целиком —
[`archive/testlog_0914_passes_19_21.md`](archive/testlog_0914_passes_19_21.md).
**Общее из них: переключить фильтр панели из скрипта нечем, а разрез по живой
строке раскладки виден только глазом.**

**2026-09-14, восемнадцатый заход — лесенка грамот предложила невозможное**
(`_stands_<здание>` под галочкой ранга сам ранг не спрашивал) —
[`archive/testlog_0914_pass_18.md`](archive/testlog_0914_pass_18.md).

**2026-09-14, ванильный костыль автостроя — два прогона, и оба против него.**
CM выключен. Сборки `be45c5`, `fa76e2`, `970a21`. «Первый ярус» работает (но
иногда нужно нажать дважды), «авторасширение» не встало ни разу. **Попытка
снята целиком по его решению, дерево мода откачено**; таблица, что эти прогоны
установили и чего не установили —
[`archive/wtp_vanilla_autoexpand_attempt.md`](archive/wtp_vanilla_autoexpand_attempt.md).

**2026-09-14, `glorpui_hints` без Glorp UI** — полоски встали, главный список
подсказки погас целиком; выпущен свой под теми же ключами. **Прогона не видело**,
разбор — [`archive/testlog_0914_glorpui_hints.md`](archive/testlog_0914_glorpui_hints.md).

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
