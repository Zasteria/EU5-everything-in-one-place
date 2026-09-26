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

**2026-09-22, `nmt_ru` — мод не появился в лаунчере, второй раз за неделю та же
болезнь.** Его слова: «я закинул мод в игру, игра не видит мод». До этого он
зашёл за Валахию и увидел сырые ключи — это был не тот мод, включена была одна
база.

**Ожидалось:** мод в списке лаунчера. **Увидено:** мода в списке нет, причины
лаунчер не называет.

**Найдено диффом, не правилом:** в `metadata.json` у `nmt_ru` не было ключа
`relationships`. Он есть у **всех двадцати трёх остальных** `metadata.json` в
дереве — у одиннадцати чужих модов и у двенадцати наших, включая те, что у него
в списке видны; у части он пустой (`[]`). Больше отличий нет: набор остальных
ключей, порядок, отступы, BOM — те же, что у работающего `nd_ru`.

**Это ровно тот же класс, что 09-20 с `marker_throttle`** (там не было
`game_custom_data`). Поэтому `tools/check_script.py` теперь требует **весь**
набор ключей, который везут работающие моды, а не тот, без которого «точно не
работает»: лаунчер про причину молчит, и дешевле повторить чужой файл целиком.

**Починено:** `relationships` дописан — зависимость от `national_mission_trees`,
как у `nd_ru` от `trin.national_destinies`. **Прогона починка не видела.**

**Сырые ключи за Валахию отдельной поломкой не являются:** база везёт только
английский и японский, отката у игры нет, поэтому база на русском без `nmt_ru`
даёт ровно эту картину.

**2026-09-20, `marker_throttle` — два прогона, подход закрыт**, `max_update_rate`
на значках отрядов ломает клик
([`archive/testlog_marker_throttle_0920.md`](archive/testlog_marker_throttle_0920.md)).

**2026-09-20, debug mode и `gui.clearwidgets`** — UI Editor нет, UI Bounds и
Inspect есть; clearwidgets — не метла:
[`archive/testlog_debug_mode_0920.md`](archive/testlog_debug_mode_0920.md).

**2026-09-20, `cm_perf` с правкой 5 — «субъективно стало лучше».**

Три часа, куча войн, нагруженная СРИ, все моды. Его слова: **«просадки в тиках
сократились, возможно сама деградация приблизилась к ванильной»** — иногда в
начале месяца и в конце, в середине хорошо. Первый час супер, второй терпимо,
третий «задушил сильно».

**Новое наблюдение:** галочка «максимизировать количество тиков» снова начала
давать разницу — небольшой прирост ценой нестабильного FPS. Раньше разницы не
было (это и был признак потолка, снятого правками 1–2).

Зонд `widget_probe` в сборке **не стоял**, поэтому секунд на месяц за этот заход
нет, и «лучше» — на глаз.

**Логи, 41 секунда `error.log` и 8 минут `debug.log`:**

- `cm_ae_ok` не упоминается **ни разу**. Правка 5 не ругается; живёт ли
  переменная, это не доказывает.
- **21 443 строки `debug.log` — одна и та же:** «Trying to access non-const
  context pointer from a const context for type `EconomyView`», ~45 раз в
  секунду, весь заход. Это **наш** `war_sliders`: драйвер `bag_wsl_driver.gui`
  нарочно всегда живой и держит два `datacontext = "[GetEconomyView]"`, один с
  живой датамоделью. Мод работает (война 09-17), но промот резолвится каждый
  кадр всю сессию.
- `gui.log` — только переопределения типов на загрузке, ничего покадрового.



**2026-09-20, CM и карта — его три наблюдения, и они об одном.** Не замер, а
то, что видно само: карта рекомендованных городских прав открыта и игра снята с
паузы — тики «супер медленно и подгружаются», закрыл карту — ускорились. То же
при множестве значков отрядов и при множестве значков строительства. Играет на
плоской карте, без 3D.

**Форма одна: счёт на объект, повторяемый на такте** — не пиксели. Разбор и
связь с панелями CM —
[`investigations/cm_performance.md`](investigations/cm_performance.md).

**И его претензия по делу**: предыдущий заход ушёл в ошибки локализации, которые
его сейчас не волнуют.


**2026-09-20, зонд и логи — секундомер работает, и в логах нашлась поломка
игры, которую чинит наш же мод.**

**Секундомер жив**: «по началу было 4-5 сек на месяц, потом… дошло до 7-9 сек…
минут 10-15 посидел» — **деградация вдвое, в числах**. Счётчики детей он
подтвердил бесполезными: это структура, а не утечка.

**Логи: 5310 строк `error.log` за 87 секунд**, самый частый источник — один
тултип игры:

| ключ | строк | что не так |
| --- | --- | --- |
| `BUILDING_TYPE_PROFIT_TT` | **362** | `LOCATION.GetRank.Custom('LR_PREP')`. `LR_PREP` объявлен `type = location` (`ru_EU5_custom_loc.txt:46422`), а ключ зовёт его с ранга. Чинится переписыванием на `LOCATION.Custom('LR_PREP')` — **сделано в `ru_loc_fix`**, 209 ключей вместо 207 |
| `longname_ru_GEN` на стране | **668** | суффикс с `parent = country_ru_flavor` (`ru_EU5_custom_suffix.txt:3926`), а зовут его прямо со страны — и сама игра тоже. Правильной формы не знаем |
| `MARKET_SURPLYS_INFO`, `GOODS_PRODUCED_IN_LOCATION_MARKET_TRIGGER` | по 15 | **наша починка второго круга не сработала**: `GOODS` там не резолвится и развёрнутым |

**Что это стоит в скорости, не измерено**, и утечку не объясняет.


**2026-09-19, `widget_probe` — перепись корня закрыта, кнопка уничтожения
работает, профайлер мёртв.** Вынесено:
[`archive/testlog_widget_probe_0919.md`](archive/testlog_widget_probe_0919.md).

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

**2026-09-19, `cm_maps`, два прогона — карты рисуются, губернатор и права
починены**, но починка прав в игре не проверена. Вынесено:
[`archive/testlog_cm_maps_0919.md`](archive/testlog_cm_maps_0919.md).

**Прогоны `cm_perf` 2026-09-18** (деградация за 20 минут; месячный ритм и
первые два захода) — вынесены:
[`archive/testlog_0918_cm_perf.md`](archive/testlog_0918_cm_perf.md); две
просадки скорости, накопительная и месячная, обе закрыты —
[`archive/testlog_cm_perf_0918_slowdowns.md`](archive/testlog_cm_perf_0918_slowdowns.md).

**Прогоны 2026-09-09 — 2026-09-14** (`where_to_produce`, `glorpui_hints`,
ванильный костыль автостроя) — вынесены:
[`archive/testlog_0909_0914.md`](archive/testlog_0909_0914.md).

**2026-09-26, логи партии, два захода.** Днём — 6 440 строк за три минуты, круг
четвёртый `ru_loc_fix`. Вечером, после него, лог пуст до первого наведения в
отладочном режиме; всё остальное — одна подсказка, круг пятый.

## Waiting on a run

The next session should start here rather than designing anything new. All of
these are prepared, all are cheap, and the owner has agreed to the hover one.

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
