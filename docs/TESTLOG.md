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

**2026-10-04 (~23:09; логи его 05.10 04:08), 1.4: `cm_dev_perf` +perf24, Румыния.** Автостройка: только «Пользовательский», доля 100%; в списке ND отмечены 4 здания, скидка — самая невыгодная, контроль 0%; рыночные остались включены. За месяц CM заложил 3 горные крепости (ND), рыночный склад и пакгауз и встал, потратив 700 из 900: остаток 200 — «Золотой запас». С миллионом золота из консоли ND строится везде, где близость ≥ 1 («Минимальная близость» по умолчанию 1, контроль 0). То есть строки ND идут по правилам ростера CM. Еда: РГО еды росли при выключенных автоеде и авторасширении; CM их по своим путям не строит без бюджета/галочки, ванильная «Добыча ресурсов» (`rgo`) им не гасится; +perf25 гасил её каждый месяц, но 23:16 он сказал, что она и так была выключена, и велел её не трогать (+perf26 откатил). Откуда еда, не установлено; он махнул рукой. Логи бесполезны: debug.log (предел 4 МБ) и error.log покрывают последние 2–10 с, их забил ванильный русский `EU5_customizable_localization_ru_goods` (`FetchData failed … TARGET_GOODS`).

**2026-10-04 (~22:44; логи его 05.10 03:43), 1.4: `cm_dev_perf` +perf23, Румыния, включён только список ND.** CM строит только бейлифов и еду; бюджет весь в «Пользовательском» (110.84), стройки из него нет: строки ND шли через ростер «Выбрать здания», а тот выключен (чинит +perf24). Начали строиться замки, строк CM о них нет. Ванильная автоматизация CM выключает при загрузке, а замок устаревшим делает частокол, который CM-овское «Автоматически улучшать все здания» перестраивает; кто из двух, не установлено. +perf24 гасит ванильную стройку каждый месяц. В error.log 608 строк от еды CM (`scope:cm_location` не сохранён, как у автора) и ~350 «set but never used» от строк ND: обе починены в +perf24.

**2026-10-04 (~22:38), 1.4: `cm_dev_perf` +perf23.** Наведение на название здания в списке ND показывает подсказку здания — «выглядит нормально».

**2026-10-04 (~22:31), 1.4: `cm_dev_perf` +perf22, Румыния.** Список «Здания National Destinies» подписан названиями (Провинциальная усадьба, Порт Коммандери, Горная крепость, Укрепленная церковь, Хан Коммерческий, Куртя Домняска — управленческое ND перешло в список). Справочный список «все здания державы» рисуется, с припиской «— список «Здания National Destinies»». Наведение на название ничего не показывает (было `GetNameWithNoTooltip`); +perf23 — `GetName`.

**2026-10-04 (~22:15), 1.4: `cm_dev_perf` +perf21 + `cm_rio_patch` 0.1.1, Румыния (RMN).** Значок у непостроенных в «Сооружениях» — «ок». В окне производства у построенного здания стоит кнопка CM (подсказка «Авторасширение зданий» с условиями ROI, Shift/Ctrl). Список «Здания National Destinies»: 5 строк — ровно 5 зданий RMN первой группы, — но все подписаны «-»: копия флага `set_variable value = var:` подпись строки не меняет. +perf22: подпись из переменной со зданием.

**2026-10-04 (~17:42), 1.4: `cm_dev_perf` +perf18.** Значок авторасширения у непостроенных в окне района появился (Канцелярия, Фруктовый сад, Горная крепость и др.), но лёг поверх колонки дохода «+0.44 / +0.15». +perf19 переносит его в пустую ячейку перед эффективностью.

**2026-10-04 (~17:33), 1.4: `cm_dev_perf` +perf17, зонд в строке непостроенного здания, Тырговиште.** Видны A (строка рисуется), B (`Location.HasOwner`), D (`ObjectsEqual(Location.GetOwner, GetPlayer)`); C (`ObjectsEqual(Location.GetOwner, Player.Self)`) нет. Копия кнопки авторасширения без гейта рисуется в каждой строке. Причина — `Player.Self` в этом контексте не игрок; +perf18 сравнивает с `GetPlayer`.

**2026-10-04 (~17:14), 1.4: `cm_dev_perf` +perf16.** Карта рекомендаций прав на молдавских районах «вроде починилась». Значка авторасширения у непостроенных в «Сооружения городка Тырговиште» по-прежнему нет (Библиотека, Горная крепость, Канцелярия и др.; у построенных Амбар, Рынок, Храм есть), а в общей стройке державы по зданиям он есть. Значит, `GetTag`-строка была не (единственной) причиной; +perf17 — зонд в этой строке.

**2026-10-04 (~15:50), 1.4: `cm_dev_perf` +perf14, карта рекомендаций городских прав.** На захваченных у Молдавии районах (Роман, Сирет) цвет есть, а «Подробности» и «Лучшие производства» пусты (у Сирета местами «Наравне с:»). Тот же случай, что `cm_maps` 09-19: покрытие лежит на срезе провинции по владельцу, смена владельца делает пустой срез, CM считает раз за сохранение. +perf16 переносит починку `cm_maps`.

**2026-10-04 (~14:50), 1.4: `cm_dev_perf` +perf14 с Río, «Сооружения городка Тырговиште».** У построенного здания (Дубильня) значок авторасширения CM есть, у непостроенных — нет (на скриншоте справа висела подсказка, но место значка, ~133 px от правого края строки, видно и пусто). Крючок `cm_auto_expand_new_building_button_pl` в типе `location_filtered_header_no_candidate` на месте, как у CM Dev и Río; 15:46 он уточнил: у непостроенной ювелирки значка нет и без подсказки. Причина: гейт значка `EqualTo_string(Location.GetOwner.GetTag, GetPlayer.GetTag)`, а `Country.GetTag` на бете не CString; +perf15 сравнивает объекты.

**2026-10-04 (~13:30), 1.4: `centered_towns` 0.1.0 вместо Better label placement.** Без эффекта: Русе и другие значки после загрузки на тех же местах у реки. Значит, веса `NGameCityLocators` при загрузке партии позицию значка не задают (или задают из кэша); откуда она берётся, не известно. По списку файлов установки (`FILES.txt` в reference/game) причина нашлась: файлы `city`/`vfx` игра везёт, но под новыми именами `generated_locators_*`, так что запись ниже («не везёт») неверна. 0.2.0 кладёт позиции старого мода под новые имена. Заодно 10-04: Османы одеты, болгары и валахи без одежды — виновата группа одежды DLC Fate of the Phoenix, не новый тег; портреты он трогать не велел.

**2026-10-04 (~12:55), 1.4: Better label placement 0.1 (чужой, под 1.2), Валахия.** Скриншот: валашские значки (Тырговиште, Бузэу, Бухарест, Комана) в середине районов, болгарские Русе, Червен, Доростол — на Дунае, на границе. Игра 1.4 не везёт файлов `city`/`vfx`, города ставит сама по `NGameCityLocators` (река −200); болгарские значки на 55–90 px от центров мода, то есть его файл `city` не применяется (вывод). Ответ — `centered_towns` 0.1.0, в игре не был.

Earlier runs of 10-04 (glorpui_hints 1.2.4–1.2.10, cm_dev_perf +perf11): [`archive/testlog_1004_morning.md`](archive/testlog_1004_morning.md).

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
