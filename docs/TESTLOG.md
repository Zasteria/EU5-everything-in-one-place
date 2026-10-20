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

**2026-10-20 вечер (17:19–19:40 UTC, его сессия 22:16–00:39 по ПК), 1.4.2, его слова и логи (скопированы до перезапуска).** Шаблон мира 0.9.11: листает категории, ни одного пункта и золота — в логе 108 768 раз `FetchData failed` на проверке «хватает очков» (`IntToFixedPoint` отдаёт float) → 0.9.12 в целых. `debug.log` 588 МБ / 3,7 млн строк: 2,9 млн — 87 `AddTextIf` склонения товара в `RGO_BUILD_GOODS_PRICE_IMPACT_ON_COST`, 0,44 млн — `FILTER_BY_GOODS` (ru_loc_fix; на 1.4.2 падает каждая проверка, хотя `GOODS.GetDefaultMarketPrice` в той же строке живёт) → ru_loc_fix 0.5.3 без склонения. Ещё в логе: `*_action_progress` кабинета (SCOPE пуст у действий, поставленных скриптом: develop_province 36 тыс., increase_control 18 тыс., strengthen_government 11 тыс.) — не чинено. CM: камень расширялся при нехватке ~1000 рабочих при ползунке найма 1 год — общий проход RGO брал 72 месяца (`cm_location_rgo_promotion_buffer_slack`) → +perf48. Пивоварня закрыта годами, открыта им — сразу в прибыли: открытие ждало открытого прибыльного здания того же типа на рынке → +perf48. Рыбацкие деревни на реках житница не брала → +perf48. Напоминания западного раскола после конца ситуации, «владение ордену» без ордена → rulers_toolkit: напоминание ждёт ворот и `allow`. Значки авторасширения/субсидий/закрытия налезают; в одном меню нет значка авторасширения CM; текст привилегии вылезает за рамку — скринов в сессии нет, не разобрано. **Краш при открытии панели «Гуситские войны»** (00:39:12, ACCESS_VIOLATION, eu5.exe +0x5bae8bf, 1.4.2): ни наши моды, ни мастерская `hussite_wars.gui`, `country_header.gui`, `situation_view.gui` не трогают; перед этим `hussite_wars.txt:210 create_relation — the 2 countries are the same (UBV)`. Не разобрано.

**2026-10-20 (сообщения 13:08–14:44 UTC), бета 1.4.2: `rulers_toolkit` 0.9.3, его слова и логи.** Дипрепутация: «работает ок»; советник не вернулся на прежнее действие (толкание ценности), возврат шёл только от ручного отжатия — → возврат после отправки договора. Шаблон мира: «ничего не делает, пунктов не добавляется»; в `debug.log` `peace template started` и `done` через ~4 с — шагомер шёл, помощники не нажали ничего. Там же: `diplomatic_endeavors_action_progress` «Promote SCOPE returned nullptr» ~140 строк в секунду всю сессию (720 тыс., `debug.log` 280 МБ) с момента, как мод поставил действие. → 0.9.4–0.9.5.

**2026-10-20 10:15–11:00 UTC, 1.4.1: `rulers_toolkit` 0.8.0→0.8.1, запускал сам (его ПК, `eu5.exe -debug_mode -skip_flatmap_generation -loadsavehandsoff=autosave_9579bc3a-… -timed_handsoff=N`), сейв за Румынию, временный зонд на `monthly_country_pulse` для RMN.** CMF-пульс игрока в этом режиме у Румынии всё равно идёт. 0.8.0: `royal_marriage` обоими видами аргументов не женил, женил запасной `marry_character` — на Валерии ди Вуктыл, во втором прогоне на Маргарете фон Целль-ам-Циллер из Фуггеров; `royal marriage between countries no`. Зонд: Вук фон Кнёринген (16) — единственный годный; у Румынии дипломаты есть, лимит отношений не превышен, Блуа в дистанции, но `has_potential_royal_marriage` ложно со всеми. Жанет Шатийон из Блуа (годна по всем проверкам): `royal_marriage`, `mode = accept`, без `hidden` — не женит ни сразу, ни через месяц, `error.log` чист; `marry_character` — женит, династического брака нет и через три месяца, `create_relation` тоже нет. → 0.8.1: только `marry_character`, невеста — родня монарха в дипдистанции. Контрольный прогон 0.8.1 (4 месяца): `bag_rtk: wedding done, to:` Салдуси Эрика, ошибок по `bag_rtk_wed` нет. **Все десять запусков `-timed_handsoff` кончились краш-репортом** в одном месте exe (`…63CC`, ACCESS_VIOLATION в рабочем потоке) — в самом конце, когда игра закрывает прогон сама (месячных пульсов в логе столько, сколько заказано, иногда на один-два меньше: хвост `debug.log` не успевает записаться, полный лог лежит в папке краша). Его обычные краши 10-09…10-15 — по другим адресам. Каждый краш — около 70 МБ в `crashes`.

**2026-10-19 (сообщение 13:55 UTC): `auto_marry`, его слова.** «Почему в auto merry у тебя всё работало, а тут нет? Всё что нужно было сделать — приоритет по возрасту». Династические браки `auto_marry` (`perform_diplomatic_action … mode = accept`, затем `marry_character`) у него женили; какой путь — не сказал. → `rulers_toolkit` 0.8.0 делает так же, младшие первыми.

**2026-10-19 (сообщение 13:41 UTC, журнал 18:38–18:40 по его часам), 1.4.1: `rulers_toolkit` 0.7.4, скрин и логи, старое сохранение за Румынскую империю.** Женитьба включена, «никого не женят», висит алерт игры. В `debug.log` шесть месяцев подряд `wedding search` для Вука фон Кнёрингена (16) и `wedding proposed … married no`: Рафик Манан (наш итог +77), Ава фон Веттерау (+66), Элеанор из Гвинед (+38), Марта ав Тупирвиалуит (+22), Маргарете и Юлиана фон Целль-ам-Циллер (+131); пул таял 6→1. Окно игры с фильтрами «Дипломатическая дистанция», «Согласятся», «Возрастной диапазон» показывает только Блуа (кандидатки 71 и 20) и Речь Посполитую (63, 68, 40), ни одной из наших. Значит, формула мода расходится с игрой в обе стороны, и мод слал предложения вне дипломатической дистанции (Гренландия, Уэльс). Дипломаты до и после не мерились; `error.log` в архиве начинается с 18:40:08, загрузку скриптов не видно. Попутно: `bag_rtk: work of art sold, price=0.0 quality=0 …` с «Value of wrong type» по пять раз за месяц. → 0.7.5.

**2026-10-19 (сообщение 12:58 UTC), 1.4.1: `rulers_toolkit` 0.6.4, его слова и скрин.** «Религия»: четвёртая строка теперь «Привлечь чужеземного священнослужителя» — подпись вернулась после того, как мод сам записал `<строка>_name`, — но галочки нет. По `cmm_list_setting_fields.gui` поля строки считаются от владельца `cmm_list_item_owner_setting_<строка>`, а его 0.6.4 не писал. Остальное «на первый взгляд в порядке» (парламентские убраны, СРИ в организациях, лиги нет). Зонд `list rebuilt` не прислал. → 0.6.5.

**2026-10-19 (сообщение 12:42 UTC), 1.4.1: `rulers_toolkit` 0.6.3, его слова и четыре скрина.** «Религия» у католика: три верные строки и `ERROR_FLAG_INDEX` без галочки вместо «Привлечь чужеземного священнослужителя» (строка `cd_rel1` i29, список вырос с 27 до 31). «Сословные действия» — по строке на сословие, «Экстренный созыв парламента» отдельно; парламентские действия («Протолкнуть парламентский вопрос», налоги, ополчения) отслеживать не нужно — «завязаны на парламенте». В «Действиях с другими державами» видны действия округов СРИ, хотя округа не созданы; всё про СРИ и императора хочет во вкладке организаций. «Организации» — одна строка «Перехват лидерства в лиге», хотя он ни в какой лиге: ворота брали любую свою организацию, `visible` с `root` отбрасывался. Зонд сословий в логе не прислал. → 0.6.4.

**2026-10-19 (сообщение 11:35 UTC), 1.4.1: `rulers_toolkit` 0.6.1, его слова и три скрина.** Подвкладки «Перезарядок» работают (Религия, Держава, Организации; ситуаций не видно — пусто). «Религия» у католика — ровно «Просьба о кафедре кардинала», «Паломничество», «Предоставить владение религиозному ордену», `ERROR_FLAG_INDEX` нет, зонд не понадобился. «Привлечь чужеземного священнослужителя» ему не хватает — у действия в игре нет `cooldown` (`invite_foreign_cleric.txt`). Сословные действия у него «считаются отдельно для каждого сословия, за исключением созыва парламента» — хочет отдельным заголовком, по строке на сословие. «Международные организации» — шесть чужих действий (верховное королевство, казна, лига, ирландские фермеры): ворота смотрели любую организацию мира. → 0.6.2.

**2026-10-19 (сообщение ~11:00 UTC, журнал 15:53 по его часам), 1.4.1: `rulers_toolkit` 0.6.0, два скрина и логи.** Вкладка «Религия» у католика: группы «Показ», «Религиозные ордена» (строка «Предоставить владение религиозному ордену» и строка **`ERROR_FLAG_INDEX` без галочки**), «Христианство» («Просьба о кафедре кардинала»), «Ислам» — заголовок без строк, ниже ещё группы. Ворота строк, значит, работают (видно ровно доступное), но пустая группа не прячется, а семь групп на одну веру — не то: «мне просто нужен список того что доступно на вкладке "Религия"»; семь вкладок откатов в основе мода — тоже, хочет одну «Перезарядки» с подвкладками. Остальные вкладки не смотрел. `debug.log`: «Unknown trigger type: allow» в `bag_rtk_cd_gates_generated.txt` (три ворот захватили соседний `allow`), «No data specified for an event target link» по разу на `bag_rtk_cd.txt:23` и `:43` (один раз на строку, не на вызов — разбор шаблона). → 0.6.1.

**2026-10-19 (сообщение 10:20 UTC), 1.4.1: `rulers_toolkit` 0.5.0, его слова.** Религиозная напоминалка «вроде работает»: алерт CMF выскакивает по отмеченному действию. Просьба: клик открывает действие или вкладку религии. → 0.5.1: `cmf_set_alert_open_view` на `country_religion`.

Runs of 10-18 evening (`rulers_toolkit` 0.3.1–0.4.12: пленные в тыл, история продаж творений, ванильное действие продажи): [`archive/testlog_1018_rtk_prisoners_art.md`](archive/testlog_1018_rtk_prisoners_art.md), [`archive/testlog_1018_art_action.md`](archive/testlog_1018_art_action.md).

Runs of 10-14 by day (`nd_unnerf` 0.1.0–0.1.1, `cmf_saved_settings` 0.1.0–0.1.1): [`archive/testlog_1014_day.md`](archive/testlog_1014_day.md).

Runs of 10-15 (`assimilate_primary` 0.10.2–0.10.5): [`archive/testlog_1015.md`](archive/testlog_1015.md).

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

**Загрузка 1.4.2 (10-20, прогон без игрока):** ошибок от «Автоматики совета», CM, `cm_rio_patch` (GlorpUI) и rulers_toolkit нет, кроме исправленных в той же сессии: пометки совета на сословиях (тоже без переменных) и ворота перезарядок (`?=` берёт только `this`, остальным — `exists`).
