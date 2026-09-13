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

**2026-09-13, второй заход — три из шести правок приняты, три нашли по причине.**

| что | что вышло |
| --- | --- |
| дичь и рыба | **работает**: деревня больше не встаёт по «+1» на товар |
| строка деревень | **работает как функция**, но ему не годится: «я не хочу, чтобы они забирали себе отдельную строку… нужна только иконка, аналогично как с простыми товарами» |
| вторая страница сводки | **столбцы «Подходит» и «Лучшая» -- сплошные нули**, «хотя очевидно там есть те, что подходят по кормлению земли» |
| житницы в плане | **встают деревни и ирригации**; на локацию с мехом не встаёт ничего |
| житница в редакторе | **работает сразу как надо** |
| кнопка житницы | **всё так же на всех локациях** |

**Три причины, и все три измерены.**

1. **Кнопка житницы: `bag_wtp_is_food_loc` -- триггер, лежавший в файле
   эффектов.** Игра заводит триггеры только из `common/scripted_triggers`;
   условие переписывали дважды, а виновата была папка. Проверка добавлена в
   `check_script.py` (`misplaced_triggers`), и на всём моде такой блок был ровно
   один.
2. **Нули в сводке грамот: `_plan_right_fits_<k>` -- ворота постановки.** Внутри
   них `_plan_can_town_<i>`, а в нём «в городе ещё есть комната»; сводка
   считается **после** плана, когда города полны, поэтому ворота отвечали «нет»
   везде. **Та же ошибка, что 2026-09-03 дала `WTP RQ` тринадцатью нулями**, и
   она же записана в коде рядом с `_rq<k>`. Теперь считается по факту
   (`_plan_right_won_<k>`: городской метод товара связки выиграл здесь).
3. **Меховая житница: ставить туда нечего, и это честно.** `farming_village`
   требует своё сырьё списком, меха в нём нет; `irrigation_systems` хочет реку.
   Круг положил ноль домиков и соврать ему было нечем -- но комнаты такой
   локации из плана всё равно выпали, и это вопрос к нему, а не ошибка.

**2026-09-12, сборка `242ff0` — четыре из пяти правок подтверждены в игре, пятая
нашла свою же дыру.**

| что | что ждали | что вышло |
| --- | --- | --- |
| лесопилка | «древесина» находит локации | **встала** |
| галочка «Режим специализации» | «Пересчитать» считает выбранным режимом | **работает**, проверено на небольшой земле |
| одна грамота на провинцию | внутри провинции одна грамота, по земле — разные | **работает**, проверено на малой и на большой земле |
| «Мериносовая шерсть» | не предлагается никому, кроме Кастилии | **не предлагается**; и **скоуп угадан верно** — он прошёл событие за Испанию, взял нужный выбор, и метод появился. Ворота стоят на державе |
| две карты | видны и красят | **видны и красят** |

**И одна ошибка, которую этот же прогон нашёл.** Сняв фильтр в `methods()`, я
вернул в игру `forest_village`/`hunting_lodges` — и «+1» на дичь в редакторе
стал втыкать лесную деревню. **Так быть не должно**: деревня у этого мода —
сущность, а не товар. Ворота плана деревню из товара уже выбрасывали
(`_plan_can_rural_23` знает только `eng_royal_forest`), **а ворота редактора —
нет** (`_edit_fits_rural_23` знает и `forest_village`), и это было написано
нарочно: «Ворота редактора строятся отдельно и деревни сохраняют». Его слово:
«по такому случаю в списке товаров на +1 −1 нужно убрать те, которые
производятся ТОЛЬКО деревнями (кроме земледельческой) и добавить в список +1 −1
все три вида универсальных деревень».

**И режим карты «Житницы» ему не нужен** — нужна была только «Потенциал
продовольствия».

**2026-09-09, первая «Перетасовать» в игре — три ошибки, все названы числами**
(домики грамот уходили в обмен, ни одна деревня не менялась, «город 578 из
528», и `EDIT shuffle rounds=0` после перетасовки, переставившей 36 локаций).
Все четыре починены в тот же день, запись целиком —
[`archive/testlog_wtp_shares2.md`](archive/testlog_wtp_shares2.md).

**2026-09-09, вечер — «Расширить» разобрана по коду, прогона не просили.** Он
спросил, насколько доливка стремится к исходной формуле. Ответ из кода: доля
считается по всей земле Z = X + Y (полный список кандидатов, `_ext_recount`
пересчитывает комнаты и города), квота — плановая, уже стоящее засчитывается
(`_pn<i>` не обнуляются), лестница уровней переигрывается с нуля, так что новую
землю занимают отставшие товары. Отдать назад, догнать там, где новой земли нет,
и переставить старое она не может — для последнего есть «Перетасовать». Проба
`EXT ... moved=` обязана быть нулём и это единственное, что это опровергло бы.

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
