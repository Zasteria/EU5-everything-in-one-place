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

**2026-10-04 (~06:10), 1.4: `glorpui_hints` 1.2.3.** «Пока недоступно»: строка
обрывается сразу после названия политики — нет закрывающей «»», нет «(IV)»,
навестись не на что. Понятия `svx_req_*` лежали в `in_game/common/game_concepts`;
рабочее понятие Calidad de Vida — в `main_menu/`, туда и перенесено (1.2.4).
С переключателем «показывать всё» видел списки игры без эпох и условий — 1.2.4
показывает там свой список.

**2026-10-04 (05:53), 1.4: `cm_dev_perf` +perf11, `glorpui_hints` 1.2.2.**
Вюртемберг. **Значки авторасширения и житниц на кнопке RGO есть** — окна на
файлах Río сработали. **Дороги:** зонд — все ворота плана «yes», участков 8+9+9,
все 26 `cm_log_rd_p_short` (рынок не тянет пиломатериалы/камень/песок по
проверке CM Dev, спрос > 1.5 предложения), обход обрывается молча; +perf13 даёт
галочку, которая эту проверку для дорог снимает. Подсказка: значок `#TOOLTIP:CUSTOM` после числа
наведением **не открыл ничего**, в `error.log` о нём ни строки; ссылки-понятия в
той же строке открываются. С переключателем «без фильтра» видны списки игры —
так задумано.

**2026-10-04 (05:15), 1.4: `cm_dev_perf` +perf10, `glorpui_hints` 1.2.1.**
Вюртемберг. Логи сняты сразу после загрузки (игра 05:10, `debug.log` кончается
05:15 загрузкой окон): строк CM ноль, ворот дорог и долей бюджета в них нет.
**Значков авторасширения и житниц на кнопке RGO нет** — окно района у него от
Glorp UI Río (шапка «Запас пищи в провинции»), Río грузится позже CM и этих двух
виджетов не несёт; +perf11 собирает три окна CM на файлах Río. Строитель дорог
1.4 — новое окно с уровнями I–IV. Подсказка: цифра эпохи — хорошо; условия
строкой — нет: на надпись трудно навестись, и десяток условий разорвёт строку,
нужен значок «?» с отдельным окном условий.

**2026-10-04 (04:50), 1.4: `cm_dev_perf` +perf9, `glorpui_hints` 1.2.0.**
Вюртемберг. Ошибок «нет карты» в `error.log` ноль: +perf9 работает. Журнал: CM
сам поставил гильдию портных в Штутгарте (`cm_log_prod_queued`, окупаемость 1.5)
и расширил RGO в Бакнанге (`cm_log_rgo_ok`); в очереди он видел ещё канцелярию и
двор. **Дорог нет**, хотя денег много, скидка свободна, «Запустить сейчас»
нажат: ни одной строки дорог, а сводка зонда дорог пишет `cmf_log_value`
напрямую и в `debug.log` не попадала. +perf10 зеркалит прямые `cmf_log*` и
печатает ворота плана дорог. Подсказка: «Пока недоступно» ничего не объясняла
(игра пишет эпоху); 1.2.1 пишет эпоху, достижение или «требования ещё не
выполнены».

**2026-10-04 (ночь), 1.4: `cmf_dev_beta` +beta5, `cm_dev_perf` +perf8,
`glorpui_hints` 1.2.0 с Glorp UI Río.** Валахия. Зонд CM: пару секунд на паузе
«классификация НЕ закрыта», затем закрыта; `is_host` — нет, `cmf_is_host` — да.
Кнопки CMF в порядке. Все функции CM включены, деньги через `cash`, ограничения
контроля и близости сняты, 4–5 месяцев. **Журнал +perf8 в `debug.log` пишет**
(«CMproduction$cm_log_rgo_slots$…», ключ сырым, числа дробью `|2` печатаются):
цикл идёт каждый месяц; расширение RGO в Тырговиште и Плоешти каждый месяц
упирается в «нет свободного слота» (слоты стройки района заняты); уборка один раз
закрыла 5 и снесла 3 здания с прибылью ~0 при пороге 0.05 (лесные деревни,
гончары, пивоварня). Строк «поставил в очередь» нет: у основных товаров и еды
такой строки в журнале нет вовсе. `error.log`: 1 243 ошибки CM
`is_key_in_variable_map` «нет карты» (`cm_rgob_cov`/`cm_rgob_sum` — 1 195, после
его нажатий в «Отладке»), остальное — ваниль. +perf9 ставит на поиск
`has_variable_map`. Подсказка ценности рисует оба списка с нашими строками;
длинные строки мельче — сжаты под ширину.

**2026-10-02, `quiet_alerts` 0.1.1.** Красные и оранжевые без звука, зелёные
со звуком; молчат предложения союза (их ключ мод не трогал). Жёлтый звук он
счёл приемлемым — 0.2.0 ставит его красным и оранжевым.

**2026-10-02, `quiet_alerts` 0.1.0.** Замолчали все уведомления, в том числе
зелёные (предложение союза). Файл держал блок `NAlertAudio` из двух ключей.
Версия: блок defines заменяется целиком. 0.1.1 копирует блок игры.

**2026-10-02 (вечер, третий), бета: `cmf_dev_beta` +beta4, `cm_dev_perf` +perf7.**
Зонд: классификация закрыта, дерево убрано; `is_host` (как читает игра) — нет,
`cmf_is_host` — да, ворота закрыты. **Подтверждено: на бете `is_host` — триггер
игры, а не CMF, и в одиночной партии он ложный.** Всё, что в модах стоит на
`is_host`, на бете молчит.

**2026-10-02 (вечер, второй), бета: `cmf_dev_beta` +beta3 с CM.** CMF Dev теперь
в партии, ошибок CM в логах нет. Зонд: классификация не закрывается, не пройдены
400+ из 453 типов зданий. Найдено по дампам, не прогоном: бета добавила свой
триггер `is_host` («хозяин сетевой партии»), тёзку скриптового триггера CMF;
ворота классификации стоят на `is_host`. +beta4 / +perf7: CMF и CM зовут
`cmf_is_host` (тело CMF), зонд показывает оба `is_host` и ворота. Горячая клавиша
меню CMF: `cmm_open_menu` нет ни в одном загруженном профиле ввода.
(error.log этой партии начинается с 17:30, загрузки в нём нет.)

**2026-10-02 (вечер), бета: `cmf_dev_beta` +beta2, логи.** Дублей в меню паузы
нет. Причина трёх остальных симптомов — в плейсете не было самого CMF Dev:
список модов движка — четыре наших (`cmf_dev_beta`, `cm_dev_perf`, `qol_beta`,
`ru_loc_fix`); в error.log все эффекты `cmf_*`/`cmm_*` неизвестны, макросы
`CMMHomeCountryValid` не разобраны, ключ `CMM_PAUSE_MENU_BUTTON` без текста.
Заплатка грузилась без фреймворка. +beta3 — полная копия CMF Dev, ставится
вместо него. Ещё: лобби давало 20 двойных типов; окно рынка из `ru_loc_fix`
было копией 1.3 и на бете сыпало ошибками (`action_button_regular`,
`AutomatedTradeSlider`) — 0.4.2 на файле беты.

**2026-10-02, бета: `ru_loc_fix` 0.4.0, `cm_dev_perf` +perf5, `cmf_dev_beta`.**
Перевод «много где встал как надо»; ключ подсказки автосортировки в меню модов
был сырым (0.4.1 переводит английские файлы движка). Зонд CM: классификация
закрылась. Значки авторасширения CM и ванили в производстве стоят оба; кнопки
меню CMF в паузе нет, вместо неё дубли «Настройки уведомлений» и «Сообщить о
проблеме» (+beta2 чинит дубли); панели быстрых кнопок CMF нет вовсе. Последние
три, по коду, — одна причина: CMF не записал моды в `cmf_active_mod_ids` (на нём
держатся `glorpui_is_cm_active` и кнопки). Ждём error.log.

**2026-10-01, `mods.bat` → 9 после патча (Steam build 25606497).** Дошёл до
конца, «много ошибок» (текста нет). 2 984 файла (`94932966`), обновились NMT и
Playmaker; дампы API не снимались. Падают сборщики `where_to_produce` и
`ru_loc_fix`. По модам:
[`investigations/patch_2026_10_01.md`](investigations/patch_2026_10_01.md).

**2026-10-01, `ru_loc_fix` 0.3.5 и зонд 0.3.6.** Ключ «указанной культуры» убрал
ошибки, но и остаток названия («ой»); зонд `$NAME$` показал «NAME» — игра
аргумент в этот ключ не передаёт. Он: «как было — окончание было, так и
должно быть». Ванильный ключ возвращён (0.3.6). В error.log сверх того
4 360 строк другого: `#l` Glorp (1 603), окна совета и отношений, `CL_tt`/
`predlog_vvo` у района.

Runs of 09-26 … 09-30: [`docs/archive/testlog_0926_0930.md`](archive/testlog_0926_0930.md).

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
