# Next session: the job in progress

Six mods, a pile of documents and more history than any session should read.
This file is the part that is live. What has already been settled is in
[`SETTLED.md`](SETTLED.md); where each mod stands is [`STATUS.md`](STATUS.md).

## Вторая версия мода закрыта, работа возвращается в первую

**2026-09-12: `where_to_produce_v2` построен и удалён в тот же день**
([`archive/wtp2_failed.md`](archive/wtp2_failed.md)) — **чужой инструмент
копировать файлами, а не воспроизводить формулой**. Его список —
[`investigations/wtp_backlog.md`](investigations/wtp_backlog.md); **CM и Glorp UI
сняты с плейсета, CMF остаётся.**

## Работа: `where_to_produce` — что ждёт прогона

## Glorp UI снят с плейсета, `glorpui_hints` автономен

Снят по его решению, дорогим он не был
([`investigations/glorp_ui_cost.md`](investigations/glorp_ui_cost.md)). **09-14
форкнуто** четыре их генерируемых файла под именами `svx_svh_*`, одиннадцать
языков шлются отсюда, зависимость `glorp.ui` снята; **имя мода — всё ещё их, это
его решение**. **Прогона форк не видел**, что смотреть —
[`../mods/glorpui_hints/README.md`](../mods/glorpui_hints/README.md#форк-что-взято-у-glorp-ui).

## Игра вылетает, и причину назвать пока нечем

**Его слово 2026-09-14:** «игра 1-2 слияния веток назад начала вылетать… без
видимых на то триггеров… чаще когда игра какое-то время свёрнута». Симптом с
мышью он снял сам — оконный режим.

**Причиной не является** наш файл поверх игрового (полон, стережёт
`stale_overrides`), и в логах 09-14 нет ни дампа, ни исключения. **Нужно от него
одно сообщение:** папка `logs` **упавшего запуска** (сперва через
`tools/which_build.py`) и **один заход без нашего мода**. **Гадать до этого
нечего** ([`pitfalls/diagnosis.md`](pitfalls/diagnosis.md)).

**Три его просьбы 2026-09-14, построены и не прогонялись:** отставшая грамота
(`_rgiven<k> × 2 < max`, счёт **в городах**) выбирается первой; грамота ставится
в локацию руками из окна замены; «+1»/«−1» у грамот ходят провинцией целиком, и
галочка «Менять грамоты всей провинцией» стоит по умолчанию. Разбор и что
смотреть — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md).

**И `_stands_<здание>` под галочкой ранга теряло сам ранг** — его прогон
2026-09-14: ювелирная грамота 100 % на городе, а в разборе «Торговая деревня».
Подмена `can_build_building` на `location_potential` ранга не спрашивала вовсе;
теперь под галочкой триггер несёт сторону. Заодно шапка столбца «Городское
право» перестала звать подсказку, которой нужна локация (13 строк в
`error.log`). **Прогона не видело.**

**Окно замены, порядок «Пригодности» и `ERROR` приняты прогонами 09-14.** **Не
видело прогона главное:** `_cov_pass` наконец спрашивает **локацию**; «на конец»
не пускает устаревших зданий; среднее провинции в лесенке поделено (было
90650 %); нули и нечитаемый разбор убраны. **Что смотреть — «Прогон: что
смотреть» в конце
[`investigations/wtp_backlog.md`](investigations/wtp_backlog.md)**, семь пунктов.

**Просить `debug.log`, а не только `error.log`:** три ошибки из четырёх за 09-14
нашлись только там. Почему CM ест производительность —
[`investigations/cm_performance.md`](investigations/cm_performance.md).
**Community Mod Toolkit прочитан**, игрового скрипта в нём нет
([`investigations/community_mod_toolkit.md`](investigations/community_mod_toolkit.md));
ждёт его решения про `upload.py` со SteamworksPy — вечер работы и его Steam.
**Автострой: закрыт, переоткрыт им же, построен, не заработал, снят целиком.**
Мод откачен байт в байт, опыт записан —
[`archive/wtp_vanilla_autoexpand_attempt.md`](archive/wtp_vanilla_autoexpand_attempt.md).
**Не предлагать заново.**

**Открыто из первых девяти:** режим ручного заполнения (9).

## Старое по `where_to_produce`, до его списка — в архиве

Раздача, перетасовка, три числа диагностики, цена чужих модов, продовольственный
потенциал и отложенные грамоты из плана:
[`archive/wtp_before_his_list.md`](archive/wtp_before_his_list.md).

## Отложено его решением — не поднимать самому

Два вопроса он задал сам 2026-09-14, выслушал ответ с числами и **сознательно
оставил как есть**: знаменатель покрытия (от всего входа или от сырьевой части)
и всегда истинный `visible` у `bag_wtp_trmm_search_panel`. Это не «не дошли
руки». Разбор, цена и его слова —
[`archive/next_deferred_by_him.md`](archive/next_deferred_by_him.md).
**Придёт с ответом — тогда и делать.**

## The job: `mods.bat`, and one run to confirm it

**Both halves are repaired and neither has been run on his machine** — a failed
steamcmd run looked exactly like a successful one
([`archive/mods_bat_repair.md`](archive/mods_bat_repair.md)). **Ask for** the
output of `mods.bat → 1`, `→ 4` and `mods.bat check`.

## Then `glorpui_hints` goes out

Nothing outstanding; five steps in
[`WORKSHOP.md`](WORKSHOP.md#putting-glorpui_hints-out-in-order) and
[`archive/next_glorpui_publish.md`](archive/next_glorpui_publish.md).

## Also waiting on the owner, all of it cheap

- **`mods.bat → 2` on his machine** — the 2026-08-28 files of Advanced Auto Build
  and Glorp UI are still missing here; entry 2 does **not** re-extract the game.
- **The panel-open bisect and the hover run** —
  [`investigations/panel_hitch.md`](investigations/panel_hitch.md),
  [`investigations/widget_leak.md`](investigations/widget_leak.md). **Do not
  design a different test until they have run.**

## Before asking him for anything

Read [`SETTLED.md`](SETTLED.md). And walk the protocol as the person who has to
do it: *"sit on the map and open nothing"* is impossible while events fire, which
is why everything is paused now. He cannot be asked to run a thing twice.
