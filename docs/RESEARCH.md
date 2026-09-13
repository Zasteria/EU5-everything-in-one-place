# EU5 modding notes

How EU5 modding actually works, learnt mostly by getting it wrong first. The
game ships no modding documentation, so everything here came from the game's own
files, from mods that already work, and from `error.log` after each attempt.

Split by subject, because a session rarely needs more than one of them: a
translation does not care how a CMM list is registered, and an interface mod
does not care what a `$vanilla_key$` passthrough is.

| | |
| --- | --- |
| **[`research/engine.md`](research/engine.md)** | What the engine gives a mod: how to ask it what exists, mod layout, why localization is code and the ways it fails to compile, what gates a production method, geography from script, and where the RGO bonus and the goods data live |
| **[`research/interface.md`](research/interface.md)** | The interface half of the same: which panel is which, list filters and what a filter trigger receives, view object scoping, what a scripted widget costs, and the game's own map selection — what it is made of and which parts of it a mod may have |
| **[`research/cmf.md`](research/cmf.md)** | Community Mod Framework: its hooks, Mod Menu settings, the list machinery that fails silently, and how Construction Manager's automation is put together for an addon to reach |
| **[`research/translation.md`](research/translation.md)** | Translating somebody else's mod: what the job is, what it costs, and how a localization breaks without a word |

Two things are worth knowing before opening any of them.

**The game prints its own API.** `-debug_mode`, then `script_docs` and
`dump_data_types` in the console; the dumps are in `reference/game/docs/`. Ask
them rather than inferring from what mods happen to use:

```
python3 tools/api.py set_subsidized       exact name, across every dump
python3 tools/api.py --find subsid        substring, anywhere
python3 tools/api.py --scope building     everything taking that scope
python3 tools/api.py --gui IsAvailable    GUI data functions only
```

That distinction cost real work once: subsidies were written off as
interface-only because nothing in `common/` used `set_subsidized`, and the
engine had it all along. What the dumps do *not* say is how something behaves,
or whether it does anything useful in a given scope. That still comes from
vanilla, from the reference mods, and in the end from a run.

**Versions are not written down here.** The owner refreshes `reference/`
whenever a mod updates; `python3 tools/refs.py` says what is in the tree. What
these notes describe was true of CMF 2.3.x and re-checked against 2.4.1, and
says so where a version matters.

The companion documents are [`PITFALLS.md`](PITFALLS.md) — the same knowledge
from the other end, as mistakes and the symptom each one showed — and
[`TESTLOG.md`](TESTLOG.md), which is what has actually been in the game.

## Автострой зданий: запись есть уже у стройки

**Галочку авторасширения ставит только интерфейс** --
`ToggleAutoExpandBuilding(Building.Self)`, `IsAutoExpand(Building.Self)`. Ни
эффекта, ни триггера для неё нет: проверено по полным `effects.log` и
`triggers.log`, а не по ключевому слову. Среди систем `set_automated_system`
постройки зданий тоже нет.

**Но `Building` достаётся не только из панели игры.** Здание **в стройке** уже
имеет запись, и до неё дотягивается любое окно, у которого есть локация:
`Location.GetCivilConstructions` -> `Construction.GetBuilding`. Обе формы --
ванильные (`build_location_lateralview.gui:1460`,
`map_markers_construction.gui:116`).

**Заказать стройку скрипт умеет**: `construct_building` в скоупе локации,
с `cost_multiplier`, `payer` и `instant = yes/no`. `change_building_level_in_location`
ставит уровень напрямую, `every_buildings_in_location` заводит в скоуп здания
(`building_level`, `building_max_level`, `building_levels_under_construction`,
`is_at_max_level`).

**Здание с потолком в один уровень галочки не получает** -- гейт по потолку,
а не по существованию записи.

