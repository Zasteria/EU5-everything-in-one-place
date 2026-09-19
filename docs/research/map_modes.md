# Map selection, map modes and what a mod may have

Split out of [`interface.md`](interface.md) 2026-09-17, when it outgrew its
budget. `cm_maps` and `where_to_produce` are what reads this.

Ask for a section rather than reading the file: `python3 tools/kb.py <words>`.

## The game's own map selection, and what a mod may have

Two panels select geography against the live map: the peace deal
(`peace_offer_view.gui`) and a military objective group
(`military_objective_group.gui`, «Ковровая осада»). The second is the fuller one
— region, area, province and location in one indented list, any level selectable
in a click, the map clickable at the same time and the panel never closing.

**Neither is available to a mod.** Both are engine view objects:
`PeaceOfferLateralView` with `PeaceTreaty` rows, `MilitaryObjectiveGroupView`
with `GeographyGlue` rows — `GetGeography`, `GetIndentation`, `ToggleSelection`,
`ToggleAll`, `IsFullySelected`. A mod cannot instantiate a view, and per
`PITFALLS.md` reading one from outside its own panel returns null and logs every
frame.

**And a map click cannot reach script at all.** `on_actions.log` has no
selection or click hook — `on_location_*` is occupation, ownership and rank, not
the mouse. The only channel is a `generic_action` with a `select_trigger`, which
is the game's own target panel: a searchable list, the map highlighted, a click
picking the same thing a row does — and it closes after each pick, because
`fire_generic_action` executes with a supplied target rather than reopening.
Nothing in the `select_trigger` vocabulary keeps it open.

**What is reusable, and it is worth having:** the highlight functions are on the
generic widget, not on any view —
`PdxGuiWidget.SetHighlightRegion / SetHighlightArea / SetHighlightProvince /
SetHighlightProvinceDefinition / SetHighlightLocation / SetHighlightLocations /
SetHighlightLocationList`, alongside `SetHighlightCountry`, `SetHighlightGoods`
and a dozen more. `onmousehierarchyenter = "[PdxGuiWidget.SetHighlightArea(Area.Self)]"`
on a row is the game's own map highlight in a mod's own window, and the engine
clears it when the mouse leaves. Vanilla pairs no leave handler with it.

So the shape a mod can build is the panel without the map clicking: geography in
columns or rows of its own, each level opened from the one before through global
lists — `Region.GetAreas` and `Area.GetProvinces` are not interface promotes, so
only script can go down a level — with the map highlighting what the mouse is
over. `where_to_produce`'s selection window is that.

### A map mode is a mod's to define, and it reads location variables

The one part of the map a mod owns outright. A file in
`in_game/gfx/map/map_modes/` defines a mode the same way vanilla does, and it
appears in the game's own map-mode bar under whatever `category` it names.

**`map_color` is script, evaluated per location, and it may read that location's
variables.** `where_to_produce` already paints its selection that way
(`mods/where_to_produce/in_game/gfx/map/map_modes/bag_wtp_selection.txt`), and so
do both reference mods that add a mode: Advanced Auto Build compares
`eu5ab_template_slot` against a variable on the owner, Construction Manager lerps
a gradient over a script value. So anything a scripted pass parks on locations is
showable on the map without further machinery: the pass writes the variable, the
mode reads it.

**And the refresh is the one thing to get right.** A mode recolours on the
counters it names, and a variable written by script is not one of them.
`color_refresh_counters = { Day }` is the cheap answer and what this mod uses;
Construction Manager's is a `category = hidden` duplicate of the mode, activated
for an instant to force it.

What comes with it, all from the same file: `secondary_map_color` for a second
signal over the first, `legend_key` rows, a `tooltip_key` that picks a
localization key per location by trigger, `small/medium/large_map_names` from a
fixed set (`location`, `province`, `area`, `country`, `market`, `raw_material`)
and a matching `*_tooltip_context`, and `map_markers = { ... }` to turn the
game's own markers on and off — `raw_goods_marker` among them, which is the RGO
icon a plan wants left on.

**A mode can be switched from a widget**: `[GetMapMode('key').SetMapMode]`, which
is how Construction Manager follows a panel opening — so a window can put the map
into its own mode as it opens. `index` inside a `category` is claimed rather than
allocated: two mods numbering a geography mode the same would collide.

**What is still not a mod's:** the markers themselves. Every marker in
`map_markers*.gui` is a named widget the engine instantiates against a data
context of its own (`MarketMarker`, `ParliamentMarker`, `Construction`), so a
mod may hide and show them but cannot add one, and cannot put an icon of its own
over a location. A per-location colour, a per-location tooltip and the game's
existing icons are the whole of what the map will draw.

### A province is not a province definition

The game splits a province by ownership. Half of Bessarabia under Moldavia is
its own `province`, and the game names it that way on screen — «Молдавская
провинция Бессарабия» — while the other half is a second province with its own
name. What the map draws as one province is the `province_definition`, and both
are reachable:

| from a location | script | interface |
| --- | --- | --- |
| the owned piece | `province = { any_location_in_province = { … } }` | `Location.GetProvince` |
| the whole province | `province_definition = { any_location_in_province_definition = { … } }` | `Location.GetProvinceDefinition` |

`ProvinceDefinition` carries `GetName`, `GetLocations`, `GetNumLocations` and
`GetArea`, so an interface can list the whole thing; the definition's name is the
plain one, without the owner in front of it.

**И потому переменная, положенная на провинцию, не вечна.** Срезы рождаются и
исчезают вместе с владением: земля перешла — на её месте новый объект, и он не
несёт ничего из записанного на прежний. Локация переживает это, определение тоже,
провинция — нет. Карта прав `cm_maps` поймала это прогоном 2026-09-19: цвет она
читает с локации и продолжал рисоваться, а покрытие — с провинции, и подсказка
пустела спустя часы игры ([`../TESTLOG.md`](../TESTLOG.md)).

**Which of the two the engine's own RGO bonus counts is not known.** The three
tooltips the formula was verified against do not separate the cases, and
`where_to_produce` answers for the definition on purpose: it is a planning tool,
and the number for the ground *once it is yours* is the one a plan is made of.
Settling it costs one hover — a building's RGO tooltip in a location whose
province is currently split, checking whether it credits a good that only the
other country's half produces.

### The formula behind the number

The game shows the bonus only as tooltip text — "Coal in the Ore Mountains,
+2.86%". Recovered by matching those readings, and **verified to the digit
against three of them at 1.3.10**:

```
RGO bonus % = 10 * (input amounts the province supplies) / (all input amounts)
```

| Building / method | Available | Computed | Tooltip |
| --- | --- | --- | --- |
| `saltpeter_guild` / `saltpeter_guild_demands` | livestock | 8.33% | +8.33% |
| `weapon_guild` / `weapon_smith_maintenance` | coal | 2.86% | +2.86% |
| `mason` / `clay_bricks` | clay | 10.00% | +10.00% |

**Every input counts towards the denominator**, produced goods included — an RGO
can never supply tools, but tools still carry their weight:

```
weapon_smith_maintenance   lumber 0.2521 + coal 0.3034 + tools 0.5050 = 1.0605
                           lumber and coal are all an RGO can give
                           0.5555 / 1.0605  ->  ceiling 5.24%, not 10%
```

The bonus is production *efficiency*, so it multiplies output:
`volume = output * (1 + bonus / 100)`. That is the figure that compares two
buildings: a jeweller's guild and a village carver both reach 10%, but on outputs
of 1.0 and 0.1, so ranking on the percentage alone puts them level.

The community "Province Breakdown" spreadsheet tops out at 12.5% on single-input
buildings because it was built from patch 1.0.6; 1.3.10 tops out at 10%.

`tools/eu5data.py` holds all of this in code — it resolves every method per
building type, inline and shared, and skips upkeep methods that produce nothing.
