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

**2026-09-14, девятнадцатый заход — три правки прогнаны, одна не сработала.**
Сборка `04998d`, сводка по грамотам (39 городов, 9 грамот, квота 1).

| что | что вышло |
| --- | --- |
| грамоты провинцией, галочка | **работает**, но строка нажатия называла **район**, а не провинцию: «я долго искал провинцию, в которой находится конкретная локация из этой строки» |
| замена грамоты точечно, окно замены | **работает**, «вроде как корректно» |
| приоритет отставшей грамоты | **не сработал**: оружейные 1, пивные 8. Остальные «попытались себе взять компенсацию и встали около 4» |

**Его числа по оружейным, и они же — потолок.** Там, где грамота встала, земля
платит ей ~6 %; ещё в одной провинции те же 6 %; в остальных ноль. То есть
честный предел оружейных на этой земле — **две** провинции, а не восемь.

**Причина названа диффом со сводкой, а не правилом.** 6 % — это 60 из
`RANK_SCALE`, а полосы раздачи 800/600/400/200/0: оружейные не проходили ворота
`_sprt >= _rband` ни в одной полосе, кроме нулевой, а к нулевой свободной земли
уже не оставалось. Добавка отставшему стояла в ключе сравнения и не успевала
ничего решить — её просто не с чем было сравнивать. **Полоса, а не ключ, и была
воротами.**

**Починено, прогона не видело.** Отставшая грамота рассматривается в любой
полосе — но только там, где земля ей платит `> 0`, и только если провинция у неё
уже есть (`_rn<k> > 0`): «ещё не получившая ничего» стоит в очереди, а не
отстаёт, и очередь держит лестница уровней. Строка нажатия называет провинцию
(`GetProvinceDefinition.GetName`). В сводке появилась шестая причина —
«отстала, но на остальной земле ей не платят ничего».

**2026-09-14, восемнадцатый заход — лесенка грамот предложила невозможное.**
Швабия, окно плана, «на конец». Подсказка строки городского права: «Права на
ювелирное производство: 100.0%», а разбор под ней — «Ювелирные изделия: 100.0%
— **Торговая деревня**, Сельский ювелир 1/1». Его слова: «а деревни в целом не
могут вставать в города. Соответственно мод предлагает вариант, которые
невозможен».

| что | что вышло |
| --- | --- |
| лесенка на строке города | **врёт стороной**: в разборе стоит сельское здание, которого в городе быть не может |
| подсказка шапки столбца «Городское право» | **не рисуется вовсе**: `error.log` × 13 — «No context supplied (Use SetDataContext), wanted context of type 'Location'» по каждому `_rq_slot_*` и `_rq_bd_slot_*`, следом «PdxDataFetchLocalizedData failed for 'bag_wtp_plan_right_tt'» |
| `error.log` в остальном | `bag_wtp_show_plan_quota` × 413 — старое, к этому заходу отношения не имеет |

**Причина и починка — [`pitfalls/script.md`](pitfalls/script.md), «Счёт "что тут
может стоять" обязан спрашивать локацию».** Коротко: `_stands_<здание>` под
галочкой «город»/«село» ранг не спрашивал вовсе, а у `market_village`
`location_potential` нет, так что под галочкой он стоял где угодно. Строки 2 и 3
его скриншота (Гогенберг, Эрбах-ан-дер-Донау) помечены «город» именно ей.
**Починено в генераторе, прогона не видело.**

**2026-09-14, ванильный костыль автостроя — два прогона, и оба против него.**
CM выключен. Сборки `be45c5`, `fa76e2`, `970a21`. «Первый ярус» работает (но
иногда нужно нажать дважды), «авторасширение» не встало ни разу. **Попытка
снята целиком по его решению, дерево мода откачено**; таблица, что эти прогоны
установили и чего не установили —
[`archive/wtp_vanilla_autoexpand_attempt.md`](archive/wtp_vanilla_autoexpand_attempt.md).

**2026-09-14, `glorpui_hints` без Glorp UI — полоски встали, подсказка осталась
без главного списка.** Первый заход мода на плейсете, с которого Glorp UI снят.

| что он проверил | что вышло |
| --- | --- |
| полоски равновесия в окне ценностей | **«визуально выглядит хорошо»** — вторая полоска под `GetDirection` на месте, ряды ровные. Окно закрыто как непрогнанное |
| подсказка ценности (Децентрализация, Вюртемберг) | **главного списка «чтобы сместить дальше» нет вовсе**: на скрине только ванильное «При своём максимальном значении…» и наш блок «Также влияет на смещение» с одной строкой |

**Причина найдена в файлах, не угадана.** Вклеенный дословно блок Glorp UI
держит ванильный блоб за их переменной `showUnavailableSocietalValueSuggestions`
(её ставит только их окно настроек), а их 34 списка по осям — за их
`glorpui_svh_visible_*`, которых без мода нет и которые читаются как ноль. Без
Glorp UI гаснет весь блок целиком, и от ванильной подсказки не остаётся ничего.

**Исправлено:** тот же ванильный список выпускается ещё раз, своим, под тем же
заголовком `TO_MOVE_FURTHER_TO_LEFT/RIGHT`, с воротами
`Not(CMMSettingIsRegistered('glorpui__showUnavailableSocietalValueSuggestions'))`
— то есть «Glorp UI не зарегистрировался в CMF». Оба условия одновременно
истинными быть не могут, поэтому список никогда не удваивается. Их блок при этом
остался дословным, и сверка `check_glorp_list_is_current` цела.

**Вердикт: непрогнано.** В игре правка не была. И даже с ней подсказка **не**
равна виду с Glorp UI: главный список будет ванильным, нефильтрованным — их 827
отфильтрованных строк вернутся только своей генерацией
([`../mods/glorpui_hints/README.md`](../mods/glorpui_hints/README.md#автономность-чего-не-хватает)).


**2026-09-14, семнадцатый заход — счёт показал себя и оказался бредом.**
Проценты в лесенке шли как 90650 %, городу предлагался «Сельский стекольщик», а
Вестфалии японский «Сёэн»: покрытие спрашивало только державу и ни разу локацию.
Всё восемь строк таблицы —
[`archive/testlog_0914_pass_17.md`](archive/testlog_0914_pass_17.md). **Ошибка
была не в формуле, а в том, что её никогда не спрашивали о локации.**

**2026-09-14, тринадцатый—пятнадцатый заходы разом, плюс его логи.** Первый
прогон с `error.log`, `debug.log` и `gui.log` — и они дали **четыре ошибки,
которых на экране не было видно ни одной**: склеенный через `+` ключ способа
(`ERROR 1/2`), проход покрытия без `scope:bag_wtp_country`, то же у
`_r_fit_pct`, и `ai_weight` в разборе чужого продвижения. Таблица и строки логов
— [`archive/testlog_0914_passes_13_15.md`](archive/testlog_0914_passes_13_15.md).
**Логи стоит просить всегда**: три из четырёх чинились по строке из лога за
минуты.

**2026-09-14, двенадцатый заход — окно замены принято, «Пригодность» нет.**

| что он проверил | что вышло |
| --- | --- |
| «−» на здании, которое игра пускает и в село, и в город (`mason`) | **снимает**. «Мы это уже сделали, зачем снова проверять? Всё работает» |
| правый список окна замены | **не предлагает непоставимого**: «локации сельские не предлагаются в городе и в селе городские — ок» |
| пустой правый список в полной локации | **так и задумано, принято**: «нажал на товар −1 список справа появился… ок» |
| процент в правом списке | **был в порядке и до правки**, править его не просили; возвращён как был |
| «Пригодность» в поиске по грамоте | **числа появились и оказались абсурдными**: Эмсланд 236.1 %, Эйфель 132.7 % при том, что у Эйфеля сырья больше (книги 2/2 против 1/2) и денег больше (47.76 против 47.58) |
| подсказка под «Пригодностью» | **считала не то, что столбец**: в ней стоял разбор карты CM (76.1 %), в столбце наш счёт (236.1 %) |

**Это тот прогон, который назвал цифру, а не «не работает».** Из «236.1 против
132.7 при большем сырье» вышла причина, которую по коду видно было не сразу:
перенесённая формула CM у нас была **переписана**, а не скопирована, и потеряла
вычитание уже выданной грамоты — город, держащий грамоту на книгопечатание,
выглядел лучшим местом для неё же.

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
