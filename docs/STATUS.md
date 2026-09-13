# Where the seven mods stand

One line each, and a link to the brief. **Read the brief for the mod the task is
about and no others** — `mods/<mod>/CLAUDE.md` is 300–800 tokens and holds the
state, the commands, and what fails silently in that mod.

| mod | state | never been in game |
| --- | --- | --- |
| [`glorpui_hints`](../mods/glorpui_hints/CLAUDE.md) | confirmed in game; ready to publish once `mods.bat` can install it | the religious-aspect gate |
| [`ru_loc_fix`](../mods/ru_loc_fix/CLAUDE.md) | working; repairs the base game's own Russian markup, 207 keys | rounds two and three |
| [`auto_build_ru`](../mods/auto_build_ru/CLAUDE.md) | done and confirmed; 1269 keys. **Пересобрать нельзя**: Advanced Auto Build убран из дерева 2026-09-12, а генератор читает его английские ключи | the 0.9.3 work, 28 keys |
| [`nd_ru`](../mods/nd_ru/CLAUDE.md) | in progress; 4 174 keys, 10.2% | everything except Westphalia and the override itself |
| [`rgo_bonus_filter`](../mods/rgo_bonus_filter/CLAUDE.md) | working, in use, nothing outstanding | the location-panel chip |
| [`goods_target`](../mods/goods_target/CLAUDE.md) | paused, half working, four faults known | anything on the monthly pulse |
| [`where_to_produce`](../mods/where_to_produce/CLAUDE.md) | **Единственная версия, и работа идёт в ней.** Его список после партии записан — [`investigations/wtp_backlog.md`](investigations/wtp_backlog.md), девять пунктов и открыт. Из девяти пунктов открыты два: 9 (ручное заполнение) и ванильная отмашка автостроя. Карта «Лучшее городское право» перенесена из CM dev целиком — [`investigations/wtp_town_right_map.md`](investigations/wtp_town_right_map.md), там же разбор его расчёта и три отличия от нашего. Попытка второй версии закрыта в день начала ([`archive/wtp2_failed.md`](archive/wtp2_failed.md)) | **всё, что построено 2026-09-12, прогона не видело**; и **его слово в тот же день: 90% из того, что документы звали непрогнанным, уже прогонялось или неактуально** — сверять с ним, не с документами |

`where_to_produce` is the second attempt at a question the first one failed at
without ever being tested. Why the first was removed, and the lesson that shaped
this one, is [`archive/where_to_produce.md`](archive/where_to_produce.md).

## Two things being hunted that are not any mod's fault

- **[The widget leak](investigations/widget_leak.md)** — the game accumulates
  GUI widgets and never releases them. Measured across five runs, established as
  the base game's, and the open question is whether a mod or a setting is a
  lever. A run is prepared and the owner has agreed to it.
- **[The panel hitch](investigations/panel_hitch.md)** — panels open slower with
  the playset from the first minute. A different thing, and it must not be filed
  with the leak. The next step is a bisect the owner can do in five minutes.

## The tooling around all of it

Finished and not to be rebuilt: `mods.bat` → `tools/mods.ps1`, the menu that
does his whole mod loop, and `tools/workshop.py`, which answers whether a
refresh is owed without needing the game, an account or the files.
[`CONVENTIONS.md`](CONVENTIONS.md) is how it fits together.
