# Next session: the job in progress

Six mods, a pile of documents and more history than any session should read.
This file is the part that is live. What has already been settled is in
[`SETTLED.md`](SETTLED.md); where each mod stands is [`STATUS.md`](STATUS.md).

## Вторая версия мода закрыта, работа возвращается в первую

**2026-09-12: `where_to_produce_v2` построен и удалён в тот же день**
([`archive/wtp2_failed.md`](archive/wtp2_failed.md)). Его решение: править
готовую первую версию, а не строить рядом новую. **Чужой инструмент, который
просят «взять», — копировать файлами, а не воспроизводить формулой.**

**Список пришёл 2026-09-12 и записан целиком** —
[`investigations/wtp_backlog.md`](investigations/wtp_backlog.md). Девять пунктов
плюс решение, из которого следует половина работы: **он снял с плейсета CM и
Glorp UI** («оба снижают производительность, особенно CM»); CMF остаётся.

## Работа: `where_to_produce` — что ждёт прогона

**Непроверенное в сборке:** «+» и «−» в окне замены, покрытие
`bag_wtp_cov_pass`, столбец «Пригодность» в поиске по грамоте, ступень лестницы
только верхняя, процент выгоды в строке, полнота правого списка. Что именно
смотреть — в конце
[`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), раздел
«Двенадцатый прогон».

**Четыре починки 09-14, все по коду и ни одна не прогнана** (двенадцатый заход в
том же файле): `_cov_pass` считался в скоупе локации и потому не считался вовсе —
отсюда 0 % в «Пригодности»; «−» не снимало здание, которое игра пускает и в село,
и в город; правый список окна замены собран теперь воротами самой постановки;
процент в нём печатался формой `|%` на `GetValue`, которой в дереве игры нет.
Правила из них — [`pitfalls/script.md`](pitfalls/script.md).

**Community Mod Toolkit прочитан** —
[`investigations/community_mod_toolkit.md`](investigations/community_mod_toolkit.md).
Игрового скрипта в нём нет вовсе, поэтому к автострою он не относится никак.
Взять стоит их `upload.py` (загрузка в мастерскую и страниц на одиннадцати языках
через SteamworksPy — у нас это руками через окно Mod Tools) и `.editorconfig` с
`.gitattributes`. **Его решения по этому ещё нет.**

**Автострой закрыт его решением 2026-09-14 — не предлагать.** Почему заглушку
подсунуть нечем, разобрано в [`RESEARCH.md`](RESEARCH.md): `Building` и
`Construction` — объекты движка, скрипт их не создаёт, а флаг авторасширения
лежит полем на объекте, о котором движок скрипт не спрашивает вовсе. Он сказал,
что будет решать это отдельной сессией.

**Открыто из первых девяти:** режим ручного заполнения (9).

## Старое по `where_to_produce`, до его списка

**Раздача закрыта прогоном 2026-09-08**
([`archive/wtp_brief_plan_rules.md`](archive/wtp_brief_plan_rules.md)).
**Перетасовка, шаг 7 и шаг 8 построены**; фильтр «Из плана — сюда», кнопка
житницы и «снести лишнее» видены в игре, автострой и здания чужих модов — нет.
Устройство всего, что мод делает в чужих окнах, и правила, которые дороже
прочих, — [`investigations/wtp_integration.md`](investigations/wtp_integration.md);
про `_plan_*` — [`plan_gaps.md`](investigations/plan_gaps.md) и
[`plan_as_reservation.md`](investigations/plan_as_reservation.md).

**Три числа в диагностике существуют затем, чтобы не гадать**, и все три обязаны
быть тем, чем названы: `FOREIGN ... unbuildable=` — ноль; `EXT ... moved=` —
ноль; `CM found/were_on/touched` — что сделало последнее нажатие отмашки.

**Цена чужих модов измерена**: 241 → 656 методов, `in_game` 11 → 18 МБ,
`check_script` 1.8 минуты. Загрузка, по его слову, «как обычно». Если станет
дорого — резать по `country_potential`, а не по категории.

**Продовольственный потенциал стоит в строке каждой локации с
продовольственным сырьём** — то же число, что красит режим карты CM, но своим
значением: формула списана генератором, мод без CM от этого не ломается.

### Отложено: грамоты из плана

Идея 2026-09-09, разобранная до конца и не построенная:
[`archive/wtp_charters_from_plan.md`](archive/wtp_charters_from_plan.md). Новых
механизмов не нужно ни одного; встала в очередь за его списком.

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
