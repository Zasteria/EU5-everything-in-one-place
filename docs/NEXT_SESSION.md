# Next session: the job in progress

Six mods, a pile of documents and more history than any session should read.
This file is the part that is live. What has already been settled is in
[`SETTLED.md`](SETTLED.md); where each mod stands is [`STATUS.md`](STATUS.md).

## Вторая версия мода закрыта, работа возвращается в первую

**2026-09-12: `where_to_produce_v2` построен и удалён в тот же день**
([`archive/wtp2_failed.md`](archive/wtp2_failed.md)). **Чужой инструмент,
который просят «взять», — копировать файлами, а не воспроизводить формулой.**
Его список от того же дня и всё, что из него выросло, —
[`investigations/wtp_backlog.md`](investigations/wtp_backlog.md); **CM и Glorp UI
сняты с плейсета, CMF остаётся.**

## Работа: `where_to_produce` — что ждёт прогона

## Игра вылетает, и причину назвать пока нечем

**Его слово 2026-09-14:** «игра 1-2 слияния веток назад начала вылетать. Просто
умирать на мертво без видимых на то триггеров или действий… чаще этот момент
случается именно когда игра какое-то время свёрнута.» Симптом с мышью, названный
рядом, он снял сам: «откат, симптома с наводкой мыши нет, это вероятно проблема
оконного режима».

**Что проверено по коду и причиной не является:** наш единственный файл поверх
игрового (`location_production_lateralview.gui`) полон — из игрового в нём нет
лишь одной строки форматирования; теперь это стережёт `stale_overrides` в
`tools/check_script.py`.

**Что нужно от него, и это одно сообщение, не вечер:**

1. Папка `Documents\Paradox Interactive\Europa Universalis V\logs` целиком —
   `error.log`, `gui.log`, `system.log`, и `crashes`/`exceptions`, если они там
   есть. Логи сначала через `python3 tools/which_build.py <папка>`, как всегда:
   дважды уже случалось, что игра крутила не ту сборку.
2. **Один заход без нашего мода** — снять `where_to_produce` с плейсета, играть
   как обычно, сворачивать так же. Вылетело — мод ни при чём, и это дешевле
   любой догадки; не вылетело — сузилось до нас.

**Гадать до этого нечего**, и `pitfalls/diagnosis.md` про ровно этот случай.

**Непроверенное в сборке:** «+» и «−» в окне замены, покрытие
`bag_wtp_cov_pass`, столбец «Пригодность» в поиске по грамоте, ступень лестницы
только верхняя, процент выгоды в строке, полнота правого списка. Что именно
смотреть — в конце
[`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), раздел
«Двенадцатый прогон».

**Его разбор 09-14 принял две починки из четырёх и отменил одну** (правка
процента в окне замены — не просил, и он работал; возвращено как было). Живое —
«Пригодность»: подсказка под столбцом рисовала разбор карты CM, а столбец считал
наш `_rq<k>`, и на экране стояли 76.1 % и 236.1 % разом. Подсказка переписана на
наш счёт: лесенка прав плюс разбор по товарам «итог = сырьё + модификатор», со
способом и чипами сырья. **Порядок строк не тронут — причину назвать нечем, пока
он не посмотрит разбор**; что смотреть, в конце
[`investigations/wtp_backlog.md`](investigations/wtp_backlog.md).

**Community Mod Toolkit прочитан** —
[`investigations/community_mod_toolkit.md`](investigations/community_mod_toolkit.md).
Игрового скрипта в нём нет вовсе, поэтому к автострою он не относится никак.
Живая работа у них не в `main`, а в `dev` (его поправка, и она верна). Взято
оттуда: `.editorconfig` наполовину (без их CRLF — здесь всё LF) и мысль
`gui_update.py` как `stale_overrides` в `check_script.py`. Ждёт его решения одно:
их `upload.py` со SteamworksPy — загрузка в мастерскую и страниц на одиннадцати
языках, у нас это руками через окно Mod Tools. Вечер работы и его Steam.

**Автострой закрыт его решением 2026-09-14 — не предлагать.** Почему заглушку
подсунуть нечем, разобрано в [`RESEARCH.md`](RESEARCH.md): `Building` и
`Construction` — объекты движка, скрипт их не создаёт, а флаг авторасширения
лежит полем на объекте, о котором движок скрипт не спрашивает вовсе. Он сказал,
что будет решать это отдельной сессией.

**Открыто из первых девяти:** режим ручного заполнения (9).

## Старое по `where_to_produce`, до его списка — в архиве

Раздача, перетасовка, три числа диагностики, цена чужих модов, продовольственный
потенциал и отложенные грамоты из плана:
[`archive/wtp_before_his_list.md`](archive/wtp_before_his_list.md).

## The job: `mods.bat`, and one run to confirm it

**Both halves are repaired and neither has been run on his machine** — a failed
steamcmd run looked exactly like a successful one
([`archive/mods_bat_repair.md`](archive/mods_bat_repair.md)). **Ask for:**
`mods.bat → 1`, `→ 4`, `mods.bat check`, and the output of all three. Logs go
through `python3 tools/which_build.py <logs folder>` first, as always.

## Then `glorpui_hints` goes out

Nothing outstanding; publishing is five steps in
[`WORKSHOP.md`](WORKSHOP.md#putting-glorpui_hints-out-in-order), the lists are in
[`archive/next_glorpui_publish.md`](archive/next_glorpui_publish.md).

## Also waiting on the owner, all of it cheap

- **`mods.bat → 2` on his machine.** The 2026-08-28 files of Advanced Auto Build
  and Glorp UI are still not in this tree; both generators were fixed against
  rewritten copies. Entry 2 does **not** re-extract the game.
- **The panel-open bisect and the hover run** — protocols written out in
  [`investigations/panel_hitch.md`](investigations/panel_hitch.md) and
  [`investigations/widget_leak.md`](investigations/widget_leak.md), every branch
  with its next step. **Do not design a different test until they have run.**

## Before asking him for anything

Read [`SETTLED.md`](SETTLED.md). And walk the protocol as the person who has to
do it: *"sit on the map and open nothing"* is impossible while events fire, which
is why everything is paused now. He cannot be asked to run a thing twice.
