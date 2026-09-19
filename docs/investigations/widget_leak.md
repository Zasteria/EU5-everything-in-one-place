# The widget leak — the base game's, and the hunt is for a lever

The first of the two slowdowns, and the one that is measured. Do not file the
other one with it: [`panel_hitch.md`](panel_hitch.md) is a fixed cost present a
minute after loading, this one grows with play.

**«Перезагрузка» — это выход в главное меню и загрузка оттуда, не загрузка
изнутри партии.** Виджеты живут в процессе, а не в сохранении, и прогон 09-18 это
показал: загрузка сохранения без выхода в меню деградацию не сняла. Формулировка
здесь до того дня была двусмысленной, и он потратил на неё попытку.

Measured across five runs. The measurement is finished; what is open is whether a
mod or a setting can do anything about it. Numbers and method in
[`TESTLOG.md`](../TESTLOG.md); this is the state of it.

**What it is.** The game accumulates GUI widgets and never releases them while a
session is running. 364 at the main menu, ~37 000 once a game is loaded, 294 013
after an hour of ordinary play. Frame time follows: 14 ms early, 21 ms after an
hour.

**How big that is.** Every `.gui` file the game ships declares, in total, about
**27 800 widgets** — the whole interface, every window, counted statically
(`in_game/gui/`, widget declarations, minus properties that share the shape). So
after an hour the process is holding **more than ten copies of the entire
interface**. This is not a heavy panel; it is instances piling up.

**What causes it.** Interface interaction, and nothing else:

| | widgets per frame |
| --- | --- |
| paused, hands off | **0.00** — exactly zero, across 10 800 frames, twice |
| clicking countries, opening diplomacy | +1.86 |
| cycling map modes | +1.49 |
| clicking locations, opening the build panel | +0.29 |

**What it is not.** Ruled out, each with data rather than argument:

- *map markers, unit icons, the passage of time* — growth does not scale with
  game days (103 days added 138 widgets, 125 days added 10 936) and does not
  scale with the unit count, which swings 276 to 708 with no relation to it;
- *one bad window* — every kind of interaction leaks, at different rates and none
  of them zero;
- *the mod set* — with every mod off the same activity leaks **+1.99** widgets a
  frame against **+1.86** with the full playset. Vanilla is marginally worse;
- *anything in this repository* — `rgo_bonus_filter` adds to the location panel,
  the lightest of the three by a factor of six.

### The lead worth following

**Growth decays inside a block of unchanging activity.** Four blocks, four times
the same shape:

```
diplomacy, full playset   +24814   +8809  +11150    +140
locations, full playset    +3783   +1338   +1504    +336
map modes, full playset   +17532   +5191   +3278   +5123   +1130   +0
diplomacy, no mods        +14560   +3487   +3425    -418    +258
```

He was doing the same thing throughout each row, so a per-*action* leak would be
flat. A decaying one says the cost is per *distinct thing looked at*: the first
pass over a set of countries or map modes is expensive and the second is nearly
free. Over an hour of real play you keep meeting new things, which is why it
never plateaus.

**И плато всё-таки бывает — его наблюдение 2026-09-18.** За минут двадцать
обычной игры скорость сходит «очень шустрая → плавная → средняя → медленная с
перепадами → стабильно медленная», и дальше держится. Это ровно та же
затухающая кривая, что в таблице выше, только по всей сессии: пока встречается
новое — растёт, когда новое кончается — встаёт. Значит плато зависит от того,
сколько разного успел посмотреть, а не от времени.

**The engine offers nothing to release them.** `dump_data_types` has no widget
`Destroy`, `Clear`, `Free`, `Collect` or `Prune` — the only such names belong to
buildings, editors and variable systems. `PdxGuiWidget` can be hidden, found,
counted and animated, and that is all. So there is no mod-side call that undoes
this; a fix has to be something that stops the widgets being made.

### The candidate, and the lever that goes with it

Hover. It fits everything: idle costs nothing because an unmoving mouse shows no
tooltips; clicking through diplomacy sweeps the pointer over dozens of new flags,
names and numbers; map modes sweep it over a new legend each time; and the decay
within a block is what a per-subject tooltip cache would look like.

**And the defines say tooltips are built with no delay at all.**
`game/loading_screen/common/defines/jomini/00_tooltips.txt`, in full:

```
NTooltip = {
    OPEN_DELAYED_TIME = 0.0f;
    CLOSE_TIME = 0.2f;
    TENDENCY_BUFFER = 15;
    MIDDLE_MOUSE_LOCK_TIME = 0.25;
    MOUSE_MOVE_DISTANCE_TO_UPDATE_TOOLTIP_POSITION = 10.0f;
    MOUSE_MOVE_DURATION_TO_UPDATE_TOOLTIP_POSITION = 0.2;
}
```

Zero delay means every brush of the cursor over anything builds a tooltip
immediately. Sweeping across the map builds them by the dozen a second.

That file's own first line is `# This file overrides
cw/jomini/modules/tooltip_manager/data/common/defines/jomini/00_tooltips.txt`, so
overriding a defines file is the ordinary mechanism and **a mod can do the same
thing**. If hover is the source, a one-file mod setting `OPEN_DELAYED_TIME` to
something like `0.35f` cuts the creation rate by whatever fraction of hovers are
incidental — which is most of them.

Better still, the game's own **Settings → Tooltip Settings → Show Delay** almost
certainly drives the same value. So the setting tests the mod before the mod is
written.

### The run that decides it

One session, one save, paused throughout:

1. **A** — move the mouse over the map and the top bar for two minutes, sweeping
   across countries and buttons, **without a single click**.
2. Settings → Tooltip Settings: `Show Delay` to **maximum**, `Map Tooltips` to
   **Disabled**, `Map tooltips delay` to **maximum**.
3. **B** — exactly the same two minutes of sweeping.

Then `performance_degradation.log`.

- **A leaks and B does not** → the mechanism is tooltips. Write the defines mod,
  and then look at what else can be trimmed from the heaviest tooltip files
  (`shared/location_tooltips.gui` 438 widgets, `shared/combat_tooltips.gui` 428,
  `cooltip.gui` 627).
- **A leaks and B leaks the same** → the delay is not the knob, but hover still
  is. Then the tooltip `.gui` files are the place to look.
- **A does not leak at all** → hover is out entirely and the leak needs clicks.
  The next test is then the same panel opened thirty times against thirty
  different panels opened once, which separates a per-open leak (a mod can make
  panels cheaper) from a per-object cache (only Paradox can).

### The other route, if the run does not settle it

`debug_mode` in the console opens a toolbox. The buttons, as of 1.3.11:

```
TOOLBOX     Language  Environment  Map menu  Inspect  Explorer  Unit Viewer  Errors
2D Tools    UI Editor  Animator  UI Bounds  UI Library  Workbench  Reload GFX
3D Editors  E. Designer  Animation Edit  Particle Edit
```

There is **no Tweaker**, so the runtime-variable idea is out. But `UI Editor` is
the live widget tree, and that is the direct way to name what accumulates: play
until the count is high, open it, and see which container holds a quarter of a
million children. `UI Bounds` draws widget outlines and would show a stack of
invisible ones. `Inspect` reports whatever is under the cursor.

**The mitigation that is already established.** Leaving to the main menu releases
all of it — widgets back to the 364 the process starts with, memory back to what
it was before any game was loaded. So **main menu, then load the save** is worth
exactly as much as restarting the game and costs a fraction of the time.

## Reading the numbers when the run comes back

One sampler row is **3 601 frames**. Only compare intervals whose in-game date
matches the row before them — those were recorded paused, and they are the clean
ones. Every branch of the run above already has its next step written down; do
not design a different test until that one has been run.

If hover is confirmed, the defines mod is small: one file at
`common/defines/jomini/00_tooltips.txt` inside a mod, the whole `NTooltip` block
copied and `OPEN_DELAYED_TIME` raised. Then measure again.

## The rows moved out of `SETTLED.md`

Moved here on 2026-08-31 when that file outgrew its budget. Each one cost
the owner an evening and none of them is to be measured again.

| question | answer | where |
| --- | --- | --- |
| Is the slowdown memory running out? | No. The working set peaks and then falls; what grows without limit is the widget count. | TESTLOG 2026-08-24 evening |
| Do map icons / units / game time cause the widget growth? | No. It scales with neither game days nor unit count. | [investigations/widget_leak.md](investigations/widget_leak.md) |
| Does idling cost anything? | No — exactly +0, twice, across 10 800 frames each. | TESTLOG 2026-08-25 |
| Is it one bad window? | No. Diplomacy +1.86/frame, map modes +1.49, locations +0.29; none zero. | TESTLOG 2026-08-25 |
| Is it the mod set? | No. Vanilla leaks +1.99/frame against the playset's +1.86. | TESTLOG 2026-08-25 vanilla |
| Is it anything in this repository? | No. `rgo_bonus_filter` lives in the lightest panel of the three. | same |
| Can a mod free widgets? | No. `dump_data_types` has no `Destroy`/`Clear`/`Free`/`Collect`/`Prune` on any GUI type. | research/engine.md |
| Is there a widget limit or pool size to raise? | No. `NGUI` in `00_defines.txt` is twenty lines of name lengths, queue sizes and alert thresholds. Nothing about pools, caches or arenas. | research/engine.md |

