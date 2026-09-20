# Версия про подсказки от мыши — закрыта 2026-09-20

Вынуто из [`../investigations/widget_leak.md`](../investigations/widget_leak.md).
**Его слово: «про подсказки от мышки забудь — это бред».** Дефайн
`OPEN_DELAYED_TIME = 0.0f` в файле стоит, но поверх лежит настройка игры,
так что сам по себе он про его игру не говорит ничего.

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
