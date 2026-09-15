# Where the eight mods stand

One line each, and a link to the brief. **Read the brief for the mod the task is
about and no others** — `mods/<mod>/CLAUDE.md` holds the state, the commands and
what fails silently there.

| mod | state | never been in game |
| --- | --- | --- |
| [`glorpui_hints`](../mods/glorpui_hints/CLAUDE.md) | **автономен с 09-14**: машинерия подсказок Glorp UI форкнута под `svx_svh_*`, окно ценностей своё и подтверждено | весь форк; религиозный аспект |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | working; repairs the base game's own Russian markup, 207 keys | rounds two and three |
| [`auto_build_ru`](../mods/auto_build_ru/CLAUDE.md) | done and confirmed; 1269 keys. **Пересобрать нельзя**: Advanced Auto Build убран из дерева 2026-09-12, а генератор читает его английские ключи | the 0.9.3 work, 28 keys |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 174 keys, 10.2% | everything except Westphalia and the override itself |
| [`rgo_bonus_filter`](../mods/rgo_bonus_filter/CLAUDE.md) | working, in use, nothing outstanding | the location-panel chip |
| [`goods_target`](../mods/goods_target/CLAUDE.md) | paused, half working, four faults known | anything on the monthly pulse |
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, и работа идёт в ней.** Его список и все заходы по нему — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md); открыт пункт 9 (ручное заполнение). Карта «Лучшее городское право» перенесена из CM dev целиком — [`investigations/wtp_town_right_map.md`](investigations/wtp_town_right_map.md) | окно замены, порядок «Пригодности» и `ERROR` прогонами 09-14 приняты; **не видело прогона: `_cov_pass` со спросом о локации (`_stands_`), «на конец» без устаревших зданий, поделённое среднее провинции в лесенке**; и **его слово 09-12: 90% из того, что документы звали непрогнанным, уже прогонялось или неактуально** — сверять с ним, не с документами |
| [`cm_maps`](../mods/cm_maps/CLAUDE.md) | **новый 09-15, в игре не был.** Три карты CM dev без CM и CMF: еда, права (+9 детских), губернатор | всё |

`where_to_produce` is the **second** attempt; the first failed untested, and why
is [`archive/where_to_produce.md`](archive/where_to_produce.md).

**Игра вылетает с 09-14, причина не названа.** Без видимого повода, чаще после
того как она какое-то время свёрнута. Что нужно от него — логи и один заход без
мода — в [`NEXT_SESSION.md`](NEXT_SESSION.md).

## Two things being hunted that are not any mod's fault

- **[The widget leak](investigations/widget_leak.md)** — the game accumulates
  GUI widgets and never releases them. Measured across five runs, established as
  the base game's, and the open question is whether a mod or a setting is a
  lever. A run is prepared and the owner has agreed to it.
- **[The panel hitch](investigations/panel_hitch.md)** — panels open slower with
  the playset from the first minute. A different thing, and it must not be filed
  with the leak. The next step is a bisect the owner can do in five minutes.

## The tooling around all of it

`mods.bat` → `tools/mods.ps1` is his whole mod loop and `tools/workshop.py`
answers whether a refresh is owed; both finished, and **not to be rebuilt** —
that rule lives in [`SETTLED.md`](SETTLED.md). How it fits together:
[`CONVENTIONS.md`](CONVENTIONS.md).
