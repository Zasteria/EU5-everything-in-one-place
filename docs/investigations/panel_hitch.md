# The panel hitch — panels open slower with mods, from the first minute

The second of the two slowdowns. Not the widget leak
([`widget_leak.md`](widget_leak.md)): that one grows over hours and reloading
clears it. This is present on a save loaded a minute ago, so it is a fixed
per-frame or per-open cost the playset adds.

Reported 2026-08-25: *"открыть любую вкладку в ваниле происходит мгновенно, а вот
с модами с микрозадержкой или даже фризом даже при только-только запущенном
сохранении."* This is **not** the widget leak and must not be filed with it. The
leak grows over hours and reloading clears it; this is present on a save loaded a
minute ago, so it is a fixed per-frame or per-open cost that the playset adds.

**First, the size of what can be said.** The owner runs **22 workshop mods**, and
`reference/` holds five of them. `tools/playset.py` reads the mount table out of
his own `debug.log` — the engine writes one line per mod folder it mounts, in
load order — and reports that **17 of the 22 mount `in_game`**, which is the only
mount that can add a widget, a filter chip or a scripted widget to the running
game. Of those 17, at most 14 have never been looked at. So the census below is
honest about a quarter of the surface and silent about the rest; do not write
"the playset does X" on the strength of it.

**And the owner does not run Advanced Auto Build**, which the first version of
this section led with. His `debug.log` of 2026-08-24 does mount workshop id
`3781437488` — that is Auto Build, `in_game` and `main_menu` both — so either it
was turned off since, or it is enabled and unused, which costs the same because
a scripted widget is instantiated whether the player opens it or not. Its numbers
are kept below because they are the clearest example of the pattern, not because
they explain his hitch.

`tools/guicost.py` counts the rest from the files:

```
                          files  widgets GetScriptedGui   live  loops
vanilla                     387    58354              9      0      0
cmf                          44     7486             70     12      0
construction_manager         20     4545            344      3      0
glorp_ui                     49    13782             67      1      0
national_destinies            3      251              0      0      0
auto_build                    7    14125           4719      7     19
rgo_bonus_filter              2      207              4      0      0
```

**The number that does not belong.** `GetScriptedGui('x')` in a `.gui` file
runs a script trigger from the interface — the expensive kind of expression,
because it enters the script engine. Vanilla uses it **nine times** in 387 files.
Advanced Auto Build uses it **4 719 times** in seven, 2 166× vanilla's density
per widget; Construction Manager **344 times**, 491×. With Auto Build out of the
playset, **Construction Manager is the heaviest thing anybody here has looked
at** — and thirteen mods nobody has looked at are still in the room.

**And all seven of Auto Build's windows are in `scripted_widgets/`,** so the
engine instantiates them at load and never takes them down: **14 125 widgets
live for the whole session** whether or not the player opens the mod. Vanilla's
entire interface, statically, is about 27 800. CMF's twelve always-live windows
come to 104 widgets and Construction Manager's three to 96 — those are probes,
which is what a scripted widget is for. This is a different order of thing.

**`eu5ab_engine_queue_window` is a background worker.** It is deliberately kept
"visible" (`visible = "[EqualTo_CFixedPoint('(CFixedPoint)0', '(CFixedPoint)0')]"`
— always true) and parked at `position = { -10000 1 }` so it keeps ticking
offscreen. Inside are **eight phases**, each a self-restarting animation state at
**0.15 s**, each walking a `datamodel` of the player's candidate locations × their
candidate building types and running per pair:

```
GetBuildOrExpandBuildingCost           GetBuildingTypeIncomeToOwnerInLocation
GetBuildingTypeProfitInLocation        CanBuildOrExpandBuilding
```

Each phase's gate is itself a `GetScriptedGui(...).IsShown(...)` evaluated every
frame. That is a plausible cause of a hitch on any panel open, for the ordinary
reason: the frame budget is already spent before the panel asks for anything.

**Static widget counts understate a `datamodel` window, and Construction
Manager is the case in point.** `cm_hidden_window` declares twenty-three widgets
— and binds `datamodel = "[GetGlobalList('cm_building_types_to_process')]"`, so
what actually lives is that subtree **once per building type**, and the game has
465 of them. Nested inside each row are two more datamodels, over the type's
construction demand entries and over its production methods. The file's own
comments say what it is for: *"Always-present hidden window that classifies every
building type once per lobby"*, kept alive with
`visible = "[EqualTo_CFixedPoint('(CFixedPoint)0', '(CFixedPoint)0')]"` — always
true — at `position = { -10000 1 }`, and *"Keeps descendant visibility gates
re-evaluating each frame."* That is a few thousand live widgets whose `visible`
expressions (`BuildingType.HasConstructionGoodsDemand`, `BuildingType.IsProducing`,
`ProductionMethod.IsProducing`) are re-asked every frame, by design.

`cm_construct_queue_window` is the same shape with sixteen datamodels over
locations × building types, and it too is always live.

None of this is a bug: it is how CM gets at engine bindings that read only in
GUI. It is simply not free, and it is paid whether or not a panel is open.
`python3 tools/guicost.py --drivers` names the list every always-live window
iterates, because the multiplier is the number that matters and no static count
can know it.

**Filter chips are the second cost, and this repository is in it.** Every chip
whose `tag` matches a list is a trigger run once per item, every time the list
draws. `python3 tools/guicost.py --filters`:

| tag | vanilla | mods add |
| --- | --- | --- |
| building | 36 | +15 (+42%) |
| town_rights | 21 | +7 (+33%) |
| raw_goods | 15 | +4 (+27%) |
| ruler | 27 | +5 (+19%) |
| province | 8 | +1 (+12%) |

Four of the fifteen added to `building` are ours. They are not cheap ones:
`bag_rgo_has_local_bonus` walks `any_location_in_province` and evaluates a
40-branch `OR` per location, per building type in the list. On a five-location
province with a hundred buildable types that is thousands of trigger evaluations
per open of the build panel.

**Two hypotheses already dead, so nobody re-checks them:**

- *Glorp draws heavier panels.* No. On the sixteen vanilla files it replaces,
  Glorp's versions hold **3 850 widgets against vanilla's 4 956** — 0.78×. It
  adds 33 files of its own (2 399 widgets) but replaces nothing with something
  bigger.
- *A mod's Russian localization is throwing parse errors on open.* No. The hard
  rules of `mods/ru_loc_fix/tools/locscan.py` run over every mod's Russian files
  find **zero** faults: CMF 94 keys, Construction Manager 451, Glorp 139,
  National Destinies 40 719, Auto Build 1 241, and our own five mods. The broken
  markup is the base game's alone.

**The test.** Seventeen mods can be halved in four or five loads, and each load
is a minute. The same save and the same three panels every time — the country
panel, diplomacy, and a location's build panel — because the owner's own sense
of the hitch is a good enough measurement for a difference he describes as
obvious:

1. Everything on. Confirm the hitch is there.
2. Half the `in_game` mods off. Instant or not?
3. Keep halving whichever half still hitches.

Two named suspects are worth trying first, in case they save the bisect
entirely: **Construction Manager**, for the reasons above, and our own
`rgo_bonus_filter`. If it is CM, the choice is the owner's — the mod or the
responsiveness; nothing here can make another author's hidden window cheaper. If
it is ours it is fixable: those four chips can be made to cost a variable lookup
instead of a province walk.

If the bisect lands on a mod nobody has looked at, copy its folder from
`steamapps/workshop/content/3450310/<id>/` into `reference/mods/` and run
`guicost.py` again — that is what the id list from `playset.py` is for. If it
lands on nothing in particular, the cost is spread and the next instrument is
`ScriptProfilerEntry`, which the engine dumps expose with
`GetAverageTimeExclusive`, `GetCallCount` and `GetFileAndLine`.

## What the playset turned out to hold

Counted on 2026-08-25, the first time `tools/guicost.py` could see more than the
five mods in `reference/mods/`. Seventeen more, and the answer is mostly a
narrowing one — which is worth as much as a suspect:

- **not one playset mod adds a filter chip.** The `building` tag is still
  vanilla's 36 plus Construction Manager's 11 and our 4, so the +42% this
  repository has been reasoning about is the whole of it. That closes a
  direction rather than opening one;
- **three of them keep an always-live window**, and all three are small:
  `faster.universalis` has eight 24-widget `fum_speed_watcher_*` windows whose
  `visible` is `IsGameSpeedEqualOrGreaterThan` — cheap engine calls, no script —
  and `autonomous_diplomats` (8 widgets) and `calidad_de_vida_eu5` (4) have one
  each. Against Construction Manager's 344 `GetScriptedGui` calls that is
  nothing;
- **no playset mod overrides a file our mods ship.** Checked by relative path
  across every `.txt`, `.yml` and `.gui` in `mods/`.

So the interface census now covers the playset and still names the same two
heavy things: Construction Manager at 491x vanilla's script-call density, and
Advanced Auto Build at 2161x — **which he does not run**. The remaining
unexamined surface is behaviour, not declarations: what those mods do on tick.
