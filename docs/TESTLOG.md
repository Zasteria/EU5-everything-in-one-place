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

**2026-09-14, семнадцатый заход — счёт показал себя и оказался бредом.**

| что он проверил | что вышло |
| --- | --- |
| проценты в лесенке | **90650 %**: среднее провинции клалось в лесенку без деления на `RANK_SCALE` |
| разбор по способам | **городу предлагался «Сельский стекольщик», Вестфалии — японский «Сёэн»**: покрытие спрашивало только державу, ни разу локацию |
| режим «на конец» | **предлагал скрипторий** — здание, которое лестница давно заменила |
| режим «на сейчас» | **в город предлагал деревню с пивом** — то же отсутствие вопроса о локации |
| нули в лесенке | «фламандское суконное 0.0 %» — порог был `> 0`, а печатается это как ноль |
| три права в подробностях | по сути ок, **но читаются одним списком** без отступов |
| `ERROR` в разборе | **пропал** |
| план сам | **фильтры в плане правильные** — «отрадно хоть что это всё в сам план не пролезло» |

**Это первый прогон, где счёт наконец было видно.** Ошибка была не в формуле, а
в том, что её никогда не спрашивали о локации: ворота были страновые, и всё, что
страна умеет где-нибудь, считалось умением этой земли.

**2026-09-14, тринадцатый—пятнадцатый заходы разом, плюс его логи.** Первый
прогон, к которому приложены `error.log`, `debug.log` и `gui.log`, и они дали
три ошибки, которых на экране не видно ни одной.

| что он проверил | что вышло |
| --- | --- |
| «Пригодность»: Эйфель против Эмсланда | **сошлось**: 79.4 % против 76.1 %, «в целом теперь всё в нужном порядке и сходится» — вычитание выданной грамоты было той самой причиной |
| лесенка прав в подсказке | **показывала константинопольскую монополию**, которой у Вестфалии быть не может, и права с нулём |
| галочка «на конец» против «на сейчас» | **числа лесенки не менялись вовсе** («права в расчёте всегда показываются одни и те же»), хотя раздача от неё менялась: на сейчас фламандское сукно, на конец судматериалы |
| режим специализации | подсказка называет лучшим текстиль, раздача ставит судматериалы |
| разбор по способу | `ERROR 1/2` вместо имени способа |
| слагаемое модификатора | «какое-то левое… он нам не нужен» — выброшено целиком |

**Три ошибки из логов, и ни одна не была видна в игре:**

- `error.log`, **3 077 строк**: `unknown db name definition from loc/ux
  'wool_weavers_maintenance+base_fine_cloth_guild_maintenance'` — это и есть
  `ERROR 1/2` на экране. `Method.key` склеен из частей через `+`, а
  `ShowProductionMethodName` ждёт одно определение;
- `debug.log`, **1 448 строк**: `Value of wrong type in
  bag_wtp_generated_cov.txt` — проход покрытия звался из плана **без**
  `scope:bag_wtp_country`;
- `debug.log`, **240 строк**: то же у `bag_wtp_r_fit_pct` — значение читало
  переменную там, где прохода не было;
- `debug.log`, **16 строк**: `Unknown trigger type: ai_weight` в
  `bag_wtp_generated_triggers.txt` — разбор `potential` у чужого продвижения
  съедал соседний блок целиком.

**Логи стоит просить всегда.** Ни одна из этих четырёх не проявлялась ничем,
кроме одного `ERROR` в подсказке; три чинились по строке из лога за минуты.

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

**2026-09-14, шестой—одиннадцатый заходы — одно окно, пять сборок, четыре
догадки.** Разбор ошибок и порядок действий, который из них вырос, —
[`pitfalls/how_to_fix.md`](pitfalls/how_to_fix.md).

| что он проверил | что вышло |
| --- | --- |
| список модов на «Технической» | **встал**: у настройки-списка не было `_on_changed`, без него CMM рисует группу и прячет список |
| карты городских прав | **встали все**, вместе с полосой значков над баннером — после того, как перенос сделали целиком, а не кусками |
| окно замены, ряды | **встали** на пятой сборке: у рисующегося ряда `hbox` с политикой **и** `size = { -1 h }`, дети со своими размерами |
| имена и кнопка «−» | обе пропадали **шириной**: сумма ячеек шире колонки, лишнее срезается справа |
| «Можно поставить (0)» | счётчик читал список, который код перестал наполнять |
| «+» | ставил **ничего**: ворота требовали, чтобы нажатое здание уже было победителем товара |
| счёт грамоты против карты | **сошлось**: 841 в плане против 84 % на карте |
| «Пригодность» в поиске | число карты слепо к эпохе — заменено своим покрытием по нашим воротам |

**Пять правил ушли в `check_script.py`**, каждое проверено на подделке: триггер
вне `scripted_triggers`, значение вне `script_values`, список без `_on_changed`,
твёрдый размер над `datamodel`, локализация читает никем не наполняемый список.

**Автострой закрыт его решением.** Почему заглушку подсунуть нечем — в
[`RESEARCH.md`](RESEARCH.md); предлагать снова не надо.

**2026-09-14, пятый заход — счёт грамот сошёлся с картой, две дыры измерены.**

| что | что вышло |
| --- | --- |
| **счёт грамоты против карты** | **сошлось**: одна локация, ремесленные права, в плане «Лучшая» 841 — на карте городских прав 84 %. Перенос формулы CM подтверждён на числе |
| сводка прав за Вюртемберг | **порядок**, чужих грамот нет |
| строка грамоты в плане | подсказка работает, **но не влезает в экран** — «в самой карте это работает иначе, там окно ограничено и можно покрутить» |
| полоса значков карт | **сделана была не так**: он ждал полосу над баннером режима карты, как в CM dev, а не значок в сводке |
| окно замены | **третий заход пустое**, числа в заголовках верные (4 и 24) |
| список модов | **пуст**, `CMMLIST source=1 continent=5` |

**Две причины, обе из одного класса — «данные есть, рисование молчит».**

1. **Список модов.** CMF рисует строку списка только пока показан
   `<setting>_on_changed`, а его у списка модов не было: `list_settings()` в
   генераторе его не называл. Группа при этом рисуется — она зовётся по имени
   настройки, — поэтому на экране это выглядело как пустой список, а не как
   отсутствующий. **Ловит `check_script.py`** (правило проверено на подделке).
2. **Окно замены.** Числа в заголовке стоят в той же коробке, что и
   `datacontext`, а `datamodel` — внутри `blockoverride` у `scrollbox`. Что
   `datacontext` доходит туда, в этом дереве ничем не доказано: единственная
   работающая датамодель в `scrollbox` — строки плана — читает **глобальный**
   список. Оба списка окна зеркалятся теперь в глобальные.

**И мера, которую он попросил: мод весит 20 МБ.** Измерено: `gfx` — 232 КБ,
локализация — 636 КБ, остальное генерируемый скрипт. Никаких данных игры и
никаких её иконок мод не хранит. Но 2.82 МБ из 17.6 оказались **комментариями**,
и один блок в десять строк был выписан 1174 раза: у игры нет цикла по типам
зданий, поэтому каждая ветка пишется отдельно — вместе с прозой над ней.
Генератор теперь выбрасывает повтор блока. 20 МБ → 17 МБ, файл плана 6.7 → 4.6.

**2026-09-09 — 2026-09-13, прогоны до его списка** — второй заход, сборка
`242ff0`, первая «Перетасовать» и разбор «Расширить»:
[`archive/testlog_wtp_2026-09-09_13.md`](archive/testlog_wtp_2026-09-09_13.md).

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
- **`where_to_produce`'s vanilla auto-build crutch, all of it** (built
  2026-09-14, [`investigations/wtp_vanilla_autoexpand.md`](investigations/wtp_vanilla_autoexpand.md)).
  Nothing in it has been in the game: neither the hidden widget driver, nor
  `BuildOrExpandBuildingDefault` fired from it, nor
  `ToggleAutoExpandBuilding`, nor the engine price in the tooltip. The row to
  read is `VANILLA` on «Техническая», and `costed` must equal `pairs`.
