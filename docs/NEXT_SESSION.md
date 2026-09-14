# Next session: the job in progress

Six mods, a pile of documents and more history than any session should read.
This file is the part that is live. What has already been settled is in
[`SETTLED.md`](SETTLED.md); where each mod stands is [`STATUS.md`](STATUS.md).

## Вторая версия мода закрыта, работа возвращается в первую

**2026-09-12: `where_to_produce_v2` построен и удалён в тот же день**
([`archive/wtp2_failed.md`](archive/wtp2_failed.md)). **Чужой инструмент —
копировать файлами, а не воспроизводить формулой.** Его список и всё, что из
него выросло, — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md);
**CM и Glorp UI сняты с плейсета, CMF остаётся.**

## Работа: `where_to_produce` — что ждёт прогона

## Glorp UI снимается с плейсета

**Дорогим он не был** — числа в
[`investigations/glorp_ui_cost.md`](investigations/glorp_ui_cost.md); снять его
всё равно его решение, и нужны от мода две вещи. **Полоски в окне ценностей
сделаны 09-14** и чужого не требуют. **Подсказки — нет**, и это развилка: три
пути с ценой в [`../mods/glorpui_hints/README.md`](../mods/glorpui_hints/README.md#автономность-чего-не-хватает),
решает он.

## Игра вылетает, и причину назвать пока нечем

**Его слово 2026-09-14:** «игра 1-2 слияния веток назад начала вылетать… без
видимых на то триггеров… чаще когда игра какое-то время свёрнута». Симптом с
мышью он снял сам — оконный режим.

**Что причиной не является:** наш файл поверх игрового полон (стережёт
`stale_overrides`), а в логах 09-14 нет ни дампа, ни исключения.

**Что нужно от него, одно сообщение:** (1) папка `logs` **того запуска, который
упал** — `error.log`, `debug.log`, `gui.log`, `system.log`, `crashes`; сперва
через `python3 tools/which_build.py <папка>`. (2) **Один заход без нашего мода**,
играть и сворачивать как обычно. **Гадать до этого нечего**
([`pitfalls/diagnosis.md`](pitfalls/diagnosis.md)).

**Окно замены, порядок «Пригодности» и `ERROR` приняты прогонами 09-14.** **Не
видело прогона главное:** `_cov_pass` наконец спрашивает **локацию**
(`_stands_<здание>`) — без этого он предлагал городу сельское здание, а
Вестфалии японское; «на конец» больше не пускает зданий, которых в конце игры
нет; среднее провинции в лесенке поделено (было 90650 %); нули и нечитаемый
разбор убраны. **Что смотреть — «Прогон: что смотреть» в конце
[`investigations/wtp_backlog.md`](investigations/wtp_backlog.md)**, семь
пунктов.

**Почему CM ест производительность — измерено**,
[`investigations/cm_performance.md`](investigations/cm_performance.md). **Просить
`debug.log`, а не только `error.log`:** три ошибки из четырёх за 09-14 нашлись
только там.

**Community Mod Toolkit прочитан** —
[`investigations/community_mod_toolkit.md`](investigations/community_mod_toolkit.md).
Ждёт решения их `upload.py` со SteamworksPy — вечер работы и его Steam.

**Автострой закрыт его решением 2026-09-14 — не предлагать.** Почему заглушку
подсунуть нечем — [`RESEARCH.md`](RESEARCH.md). Он будет решать это отдельной
сессией.

**Открыто из первых девяти:** режим ручного заполнения (9).

## Старое по `where_to_produce`, до его списка — в архиве

Раздача, перетасовка, три числа диагностики, цена чужих модов, продовольственный
потенциал и отложенные грамоты из плана:
[`archive/wtp_before_his_list.md`](archive/wtp_before_his_list.md).

## Отложено его решением — не поднимать самому

Оба вопроса он задал сам 2026-09-14, выслушал ответ и **сознательно оставил
как есть**. Это не «не дошли руки»: у обоих есть разбор с числами, и оба ждут
его, а не нас.

- **Знаменатель покрытия.** Доля сырья от всего входа рецепта или от сырьевой
  части; сейчас от всего, поэтому рецепт с переделами упирается в 66.7 %.
  Правка — одно число, разбор и цена в
  [`investigations/wtp_town_right_map.md`](investigations/wtp_town_right_map.md).
  **Его слово: «сначала я поиграю с таким вариантом, потом может с другим и
  посмотрю что лучше ощущается».**
- **`bag_wtp_trmm_search_panel` на всегда истинном `visible`.** Перенос из CM:
  при выключенной карте каждый кадр считаются ~40 `GetMapMode(...).IsActive`.
  Чинится переносом проверки на корень,
  [`investigations/cm_performance.md`](investigations/cm_performance.md).
  **Его слово: «если эта полоска значков незначительна в нагрузке — то тоже пока
  так оставим».** Делать заодно, если полосу придётся открывать.

## The job: `mods.bat`, and one run to confirm it

**Both halves are repaired and neither has been run on his machine** — a failed
steamcmd run looked exactly like a successful one
([`archive/mods_bat_repair.md`](archive/mods_bat_repair.md)). **Ask for:**
`mods.bat → 1`, `→ 4`, `mods.bat check`, and the output of all three. Logs go
through `python3 tools/which_build.py <logs folder>` first, as always.

## Then `glorpui_hints` goes out

Nothing outstanding; five steps in
[`WORKSHOP.md`](WORKSHOP.md#putting-glorpui_hints-out-in-order),
[`archive/next_glorpui_publish.md`](archive/next_glorpui_publish.md).

## Also waiting on the owner, all of it cheap

- **`mods.bat → 2` on his machine.** The 2026-08-28 files of Advanced Auto Build
  and Glorp UI are still not in this tree. Entry 2 does **not** re-extract the game.
- **The panel-open bisect and the hover run** —
  [`investigations/panel_hitch.md`](investigations/panel_hitch.md) and
  [`investigations/widget_leak.md`](investigations/widget_leak.md), every branch
  with its next step. **Do not design a different test until they have run.**

## Before asking him for anything

Read [`SETTLED.md`](SETTLED.md). And walk the protocol as the person who has to
do it: *"sit on the map and open nothing"* is impossible while events fire, which
is why everything is paused now. He cannot be asked to run a thing twice.
