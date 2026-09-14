# `glorpui_hints` — brief

The societal value tooltip, and the values window. **Autonomous since
2026-09-14** — Glorp UI's takeable-only hint machinery was forked into this mod
under `svx_svh_*` names, so the mod now carries both halves: their 827 lines
(laws, reforms, privileges) and this mod's own **264 from fourteen more source
types**, all gated by what the country can actually take.

## State

**The fork, 2026-09-14, his decision** — «просто спизди нужные вещи из glorp…
любые обновления уже свои сделаем». `tools/fork_hints.py` takes their four
generated files, renames every identifier into `svx_svh_*` (so there is no
`Duplicated key` even with Glorp UI installed) and drops their own «show
unavailable» clause: that switching is this mod's `svx__show_all` now — off, the
takeable-only lists; on, the game's whole blob. All eleven languages ship from
here. Nothing of theirs is reached at runtime; the reference tree is needed only
to rebuild.

**The tooltip itself is confirmed in game, 2026-08-30** — this mod's templates
win over Glorp UI's, which is what the whole override rests on. **The fork has
not been in game at all.**

**Read a logs drop with `tools/which_build.py` first** — a run once loaded a
five-day-old build and looked like a mod fault.

**What is only here:** the 264 extra lines; the availability gates (252 lines,
175 objects); `SVX_REACHABLE`; the five advance-locked privileges held back;
four repaired Russian keys of Glorp UI's interface.

**One gate cannot be seen by this owner.** The religious aspect gate — he plays
Catholic, where the Papacy sets aspects. It needs a run as a religion that picks
its own.

## Окно ценностей

**Подтверждено в игре 09-14** — `svx_societal_values_window.gui`, ванильный
`template societal_values` с четырьмя кусками. **Рисует ровно то же, что окно
Glorp UI, и это сверяется каждой сборкой**: переключателя быть не может, поэтому
режимы сделаны неотличимыми. `tools/generate_values_window.py`.

## The open piece of work

**89 of the 429 (axis, policy) pairs the game pushes are in nobody's list** —
21%, including the strongest tier, and they are not scattered: **six law files
are missing whole**, because they are laws belonging to an international
organization or a religion rather than to a country's own law list, which is
what Glorp UI's generator reads. Nothing has been built for them. This is the
biggest thing neither mod shows.

## How it is built

    python3 mods/glorpui_hints/tools/generate.py              the mod (in tools/refresh.py)
    python3 mods/glorpui_hints/tools/generate.py --conflicts  what overlaps Glorp UI
    python3 mods/glorpui_hints/tools/generate.py --game-files reference/game

The last one rebuilds the hint lists from the game's `common/` tree (it runs
`scan_sources.py`). **Not** in `refresh.py`: the scan takes a minute.

## Three things that fail silently here

- **A `customizable_localization` cannot be overridden** — first definition
  wins (`gamedatabase.h: Duplicated key`). The way round it is to take over the
  localization key it prints; that is why the advance gate works at all.
- **A forked name that moved on one side only prints nothing.** Everything is
  renamed in one pass in `fork_hints.rename`, applied to every file a generator
  writes, because the `.gui` sets the scopes and the script values read them.
  `check_references_resolve` then proves every `ScriptValue`, `Player.Custom`
  and `localization_key` resolves inside this mod — 1 072 definitions, no
  duplicates.
- **A gate on a trigger that does not exist never fires and never logs.** 492
  religious aspect lines were gated on `country_religion`, which is nothing
  anywhere. `generate.py` now checks every trigger name against the dumps.

Depth: [`README.md`](README.md). The other addon that looks like this one, and
why it is not: [`../../docs/archive/glorpui_small_fix.md`](../../docs/archive/glorpui_small_fix.md).
