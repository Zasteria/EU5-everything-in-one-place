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

**2026-09-30, логи 22:42–22:47 (`eu5-logs-0930-2247`), Литва.** error.log
1 626 строк — все от одного: условие события `flavor_lit.43`
(`"culture_percentage_in_country(culture:crimean)" >= 0.05`) выводится ключом, которому
игра не даёт `TARGET_CULTURE` (в debug.log 2 659 раз, по кадру, пока открыто
окно; «Процент групп населения ой культуры»); так же `religion_percentage_…` 12
раз. В debug.log сверх того `ROOT.GetCountry.GetCulture.GetAdjective` — у культуры
нет прилагательного; по нему `locscan` научен правилу `wrong_type`, и
`ru_loc_fix` 0.3.5 чинит ещё 98 ключей. Текст миграции на его скриншоте
(«(Источник — Вильна)») в нашем `reference/` не встречается: локализация там от
08-31, игра новее; добавлена в манифест выгрузки.

**2026-09-29, NMT, Болгария — вассал не засчитывается.** «Завоевать Валахию»:
вся область (44 района) у вассала, «Отвечающих: 0». Чинит `nmt_fix` 0.1.0.

**2026-09-28, логи 12:23–12:40 (`eu5-logs-0928-1242`).** error.log 4 483 записи;
4 400 из них — события `flavor_mos.16` и `flavor_mos.23`, вызванные им из консоли
на державе, где триггер не проходит (`dynasty ?= root.ruler.dynasty`, 4 240 раз
за 12 с, пока окно события открыто). Это не поломка игры, чинить нечего. Прочее:
~30 `Widget cannot have a position in a layout` и 4 `untyped` — Glorp,
`glorpUI_country_header.gui:34/50`, `glorpUI_left_panel.gui:802`; одно
перекрытие сроков правления AMP 1425 — история игры. Единственное из русской
локализации — `[латинян]` в совете загрузки; по нему `locscan` научен правилу
`cyrillic_code`, и `ru_loc_fix` 0.3.4 чинит 47 ключей.

**2026-09-27, `ru_loc_fix` 0.3.2 и `cm_dev_perf` +perf3.** Его слова: «фикс
торга сработал» — у «Крепких спиртных напитков» «+» в торговом приказе снова
нажимается. Зонд perf показывал «классификация закрыта» (потом он окно убрал).
Версия «perf медленный, потому что классификация не закрылась» этим прогоном
не опровергнута и не подтверждена: игра шла «достаточно шустро», закрытое
дерево с быстрой игрой сходится. Решит медленный прогон: красное — версия верна. Попутно: CM «баговал»,
а после снятия и повторной постановки галочки строительства «начал что-то делать».

**2026-09-29, `war_sliders` 0.5.1 — после войны все три содержания на 100%.**
Два скриншота диагностики: через пару месяцев после долгой войны «помнит войну
0», содержания 1.00 / 1.00, приводов 16 (вчера после кнопки было 5), правка
чеканки сменила состояние. «Сработать сейчас» опустил всё правильно (22). Вывод,
не замер: мир мод заметил и ползунки опустил, поднял их потом кто-то другой —
вероятно ванильная автоматика «в начале конфликта». 0.5.2: в мирный месяц мод
возвращает содержания на цель; в диагностике счётчики замеченных войн и миров.
Тот же день, 0.5.2: войн 3, миров 3, всё на 50%, но каждый месяц содержания на
долю секунды встают на максимум, иногда до следующего месяца. Это взвод привода
верхом шкалы и слепой месячный возврат («нахуя это?»); 0.5.4 двигает только
поднятый ползунок и взводит на сотую выше цели.
Остаток инфляции 0.01% не гасился; 0.5.5 гасит любой, каждый мирный месяц.

**2026-09-28, `war_sliders` 0.5 — не сработал ни разу.** Подозреваемый: ворота
привода (`trigger_when` + `duration` + `on_finish` в одном состоянии, формы нет
ни в ванили, ни в CMF). В 0.5.1 выдержка вынесена в своё состояние; в тот же
вечер «Сработать сейчас» опустил все три содержания (приводов 5), ворота живы.

**2026-09-27, `war_sliders` 0.4 — правка чеканки иногда зависает.** Его
скриншот: инфляция 0.00%, месячный прирост 0.00% (база −0.10, контроль над
денежной политикой −0.05, чеканка +0.15), ползунок чеканки на нуле, авто-чеканка
выключена и не возвращается.

**Причина по коду:** правка кончалась только когда `inflation` не выше цели.
Остаток меньше 0.005% панель рисует как 0.00%, а месяц на полу не снимал
ничего — и формула держала пол вечно. **Починено в 0.4.1:** порог цели +0.005%,
и месяц, не снявший ничего, отдаёт чеканку автоматике. Прогона нет.

**2026-09-22, `nmt_ru` не появился в лаунчере** — не было `relationships` в `metadata.json`; `check_script.py` теперь требует полный набор ключей. Подробно: [`archive/testlog_nmt_ru_0922.md`](archive/testlog_nmt_ru_0922.md).

**2026-09-20, `marker_throttle` — два прогона, подход закрыт**, `max_update_rate`
на значках отрядов ломает клик
([`archive/testlog_marker_throttle_0920.md`](archive/testlog_marker_throttle_0920.md)).

**2026-09-20, debug mode и `gui.clearwidgets`** — UI Editor нет, UI Bounds и
Inspect есть; clearwidgets — не метла:
[`archive/testlog_debug_mode_0920.md`](archive/testlog_debug_mode_0920.md).

**2026-09-20, `cm_perf` с правкой 5 — «субъективно стало лучше»**; 21 443
строки `debug.log` про `EconomyView` — от `war_sliders`. Вынесено:
[`archive/testlog_cm_perf_0920.md`](archive/testlog_cm_perf_0920.md).

**2026-09-20, CM и карта — три его наблюдения об одном** (счёт на объект на такте). Вынесено:
[`archive/testlog_cm_map_0920.md`](archive/testlog_cm_map_0920.md).

**2026-09-20, зонд и логи** (секундомер месяца жив; 5 310 строк `error.log` за 87 с) —
вынесено: [`archive/testlog_0920_probe_logs.md`](archive/testlog_0920_probe_logs.md).

**2026-09-19, `widget_probe` — перепись корня закрыта, кнопка уничтожения
работает, профайлер мёртв.** Вынесено:
[`archive/testlog_widget_probe_0919.md`](archive/testlog_widget_probe_0919.md).

**2026-09-19, CM и скорость — он описал форму** (медленные первые дни после
тика, растут со временем, лечится перезагрузкой). Вынесено:
[`archive/testlog_cm_speed_0919.md`](archive/testlog_cm_speed_0919.md).

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

**2026-09-26, логи партии.** Днём 6 440 строк за 3 мин, круг 4 `ru_loc_fix`.
После него лог пуст до наведения; остаток — круг 5.
17:48: горы и море чисты; ошибки — NMT на ходу, `#l`, `LR_PREP` района 0.
18:02: `nmt_ru` снял NMT на ходу. 1 754 строки при запуске — почти всё база NMT.
Вечер: `CONSTRUCTION_AUDIO_MODE = 0` — звук достройки на слух остался.

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
