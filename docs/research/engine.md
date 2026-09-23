# How the engine works

What EU5 itself gives a mod: where to ask what exists, how a mod is
laid out, how the interface is put together, and where the numbers live.

## The game prints its own API

With `-debug_mode` on the launch options, the console commands `script_docs` and
`dump_data_types` write the complete list of what the engine understands. Those
dumps are in the repository, under `reference/game/docs/`:

| File | Holds |
| --- | --- |
| `effects.log` | 1534 effects, each with its supported scopes and targets |
| `triggers.log` | 1798 triggers, the same |
| `event_targets.log` | scope links, with input and output scopes |
| `on_actions.log` | every on_action and its expected scope |
| `modifiers.log` | every modifier tag and its categories |
| `custom_localization.log` | the customizable localization keys |
| `data_types/` | every GUI data function, promote and return type |

Ask them rather than reading them:

```
python3 tools/api.py set_subsidized       exact name, across every dump
python3 tools/api.py --find subsid        substring, anywhere
python3 tools/api.py --scope building     everything taking that scope
python3 tools/api.py --gui IsAvailable    GUI data functions only
```

**This replaces the rule this repository ran on for months** — "if vanilla or one
of the reference mods does not use it, treat it as unproven". That rule is now
only about *usage*, not about existence, and the difference is expensive: half a
mod was scoped around subsidies being impossible from script, because nothing in
`common/` used `set_subsidized`. The engine had it all along.

What the dumps do *not* say is how something behaves, what a sensible argument
is, or whether an effect does anything useful in a given scope. That still comes
from vanilla and from the reference mods — and, in the end, from a run.

## Спрос и предложение рынка читаются, и это меняет постановку задачи плана

**Найдено 2026-09-07.** Игра отдаёт оба числа своими триггерами, скоуп — рынок,
и оба работают как script value:

```
goods_demand_in_market(goods:X)     сколько товара рынок спрашивает
goods_supply_in_market(goods:X)     сколько рынок даёт
```

**Проверено по дампам самой игры** (`api.py goods_demand_in_market`), а не по
догадке; Construction Manager уже строит на них свой расчёт дефицита
(`cm_market_shortage_script_values.txt`, `cm_market_<good>_build_overage`) и
берёт порог из define `NMarket|MARKET_CONSTRUCTION_NEEDS_BLOCK_FACTOR`.

**Для `where_to_produce` это оказалось не нужно, и владелец объяснил почему**
(2026-09-07): план — карта резерваций, а не очередь стройки. «Спрос и предложение
решают не то, что и где будет построено — только то, КОГДА.» Так что в формулу
плана эти числа не входят;
[`../investigations/plan_as_reservation.md`](../investigations/plan_as_reservation.md).

**Где они всё-таки пригодятся:** шаг 8 — стыковка с Construction Manager, который
на них и стоит, и любой будущий ответ на вопрос «что строить прямо сейчас».
**В игре мы их не мерили ни разу.**

## What a modifier says about its own scaling

Two kinds of modifier push a societal value and they differ in what a mod can
learn about them, which matters any time a tooltip wants to say "how much do I
need".

**`auto_modifiers` declare it.** `potential_trigger` is the condition that
switches the modifier on, and `scales_with` is an ordinary script value block,
so the multiplier is `((value + add - subtract) * multiply) / divide` and the
quantity is at full size when that reaches 1:

```
army_tradition        scales_with = { value = army_tradition multiply = 0.01 }   full at 100
over_fort_limit       scales_with = { value = used_fort_limit_percentage subtract = 1.0 }   full at 200%
below_half_fort_limit scales_with = { value = 0.5 subtract = used_fort_limit_percentage multiply = 2 }   full at 0%
larger_than_expected_army   potential_trigger = { army_size_percentage > 1.0 }   no scaling at all
```

**`static_modifiers` declare neither.** `average_literacy` is
`monthly_towards_innovative = societal_value_monthly_move` and nothing else; the
engine decides how to scale it when it attaches it, and neither
`main_menu/common/static_modifiers/` nor `loading_screen/common/defines/` says by
how much. So "what literacy reaches the full +0.10" has no answer in the files,
and a mod that prints one is inventing it.

`glorpui_hints` computed all of this once and then stopped printing it, for
reasons of screen space rather than of correctness — see that mod's README. The
arithmetic is worth writing down because deriving it took two passes over the
game files.

## Mod layout

**Where a local mod lives.** Not in the game's install and not in Steam's
workshop folder: `Documents/Paradox Interactive/Europa Universalis V/mod/<any
folder name>/`, and what makes it a mod rather than a folder is
`.metadata/metadata.json` inside it. There is no `.mod` descriptor to write
beside it — that is the EU4/CK3 shape and it is gone. A mod put there is
enabled once in the launcher; replacing the folder's contents afterwards is how
it gets updated, which is what `tools/mods.py` does from its menu.

Documents may not be under `%USERPROFILE%` — OneDrive moves it without asking —
so the path is read from `HKCU\...\Explorer\Shell Folders\Personal` rather
than assembled from the user name.

EU5 splits a mod by *load context* at the top level, which is new compared to
EU4/CK3:

```
<mod>/
  .metadata/
    metadata.json          descriptor (replaces descriptor.mod)
    thumbnail.png
  in_game/                 loaded once a game session exists
    common/
      on_action/           event hooks
      scripted_effects/    reusable effects
      scripted_triggers/   reusable triggers
      scripted_guis/       is_shown / is_valid / effect bridges for the GUI
      script_values/       computed numbers
      game_concepts/
      customizable_localization/
    gfx/
    gui/
      filters/             data driven list filters
      scripted_widgets/
      *.gui                interface layout
  main_menu/               loaded at the launcher / main menu
    gfx/
    gui/
    localization/<lang>/*.yml
  loading_screen/
    data_binding/          GUI macros
    input_profile/         keybinds
```

`metadata.json` carries `id`, `version`, `game_id`, `supported_game_version`,
`tags` and a `relationships` array. Dependencies on other mods are declared
there:

```json
"relationships": [
    { "rel_type": "dependency", "id": "community_mod_framework",
      "display_name": "Community Mod Framework",
      "resource_type": "mod", "version": "2.*" }
]
```

Script and localization files carry a UTF-8 BOM. Localization keys take one
leading space under the `l_<language>:` header, as in earlier Clausewitz games.

## The RGO production efficiency bonus

The shovel badge on a building row is `gfx/interface/icons/sort/rgo.dds`. The
game exposes the state behind it through two GUI data functions, both of which
take the owning country and the location:

| Function | Object | Meaning |
| --- | --- | --- |
| `HasPossibleRGOBonus(country, location)` | `BuildingType` | The building *could* gain efficiency from raw materials present in the province |
| `IsUsingRGOBonus(country, location)` | `Building` | Its current production method actually consumes them |
| `HasBuildingRGOBonus(production_method)` | `Building` | Same, asked per production method |
| `ProductionEfficiencyInfo(country, location)` | `BuildingType` | String pair list used for the tooltip breakdown |
| `GetBuildingProductionEfficiencyInfo(production_method)` | `Building` | Per method variant of the same breakdown |

`location_window.gui` drives the badge with them — the icon is visible on
`And(BuildingType.IsProducing, BuildingType.HasPossibleRGOBonus(...))`, and it
is tinted green through `IsUsingRGOBonus` or yellow otherwise, with tooltip
strings `RGO_BONUS`, `PROD_METHOD_BONUS_ACTIVE` and `PROD_METHOD_BONUS_POTENTIAL`.
`building_view.gui` uses the per method pair to mark which production method
would pick the bonus up.

These are GUI data functions. There is no script-side counterpart in
`common/scripted_triggers/`, so a filter `trigger` cannot call them directly.

**Only the RGO feeds it, and a building next door does not.** Asked on
2026-09-03 because a whole class of recipes scores near nothing in
`where_to_produce`'s plan — cannons, firearms, jewelry, steel — and every one of
them is fed by *made* goods, which the plan itself would be putting in the same
province. If the engine counted a neighbour's output the plan would be blind to
its own work and the formula would need a second pass. It does not, and the game
says so in its own tooltip:

```
PROD_METHOD_BONUS_ACTIVE: "This [building] has increased [production_efficiency]
because some of its inputs are produced by the [rgo_with_icon] of the
@province! [province]."
```

«…поскольку часть потребляемых им товаров **добывается** в провинции» in the
Russian. The bonus is the province's raw materials and nothing else, which is
what its own name says and what `raw_material` is. **Read off
`interfaces_l_english.yml` and its Russian twin, not measured in play** — but it
is the string the game shows for this exact bonus, and no reading of it leaves
room for a workshop's output.

So a deep recipe scoring low is the truth about the ground and not a fault in the
formula. The player reasons «дерево и свинец — вот оно» because he knows the
chain will be local; the engine pays him for the lead and not for the chain.

## The interface

Everything about windows, lists, view objects, scripted widgets and the map's own
selection is in [`interface.md`](interface.md) — same entries, moved when this
file outgrew its budget rather than trimmed. Ask for one:
`python3 tools/kb.py <words>`.

## A condition read out of the game's files is answered in a scope

**And the scope is half the rule.** 2026-09-03, `where_to_produce`: the town
rights that forbid one another were read out of their `allow` blocks and turned
into a country rule — "a country that can grant the excluder never sees the
excluded one". The block says

```
allow = { scope:target = { NOT = { has_town_rights = town_rights_type:royal_textile_rights } } }
```

and `scope:target` in a town right is **the town**. The rule is "one town does
not hold both" and it says nothing whatever about a country. Eight pairs in the
game carry one. Read a scope too wide and it cost every Scandinavian country its
two best charters, in the plan and in the window alike, with no error anywhere:
the derived condition was valid script and simply meant something else.

**So when a rule is derived from a file rather than typed, name the scope it was
read in and check that the mod asks it in the same one.** A derived rule is
better than a typed list — it survives a patch — but only where the derivation
keeps the scope. The generator now asserts the pair it still relies on is still
in the game, so a patch that drops it is a build error and not a wrong answer.

## What gates a production method

`common/advances/` is in the tree now, which answers what
[`../archive/where_to_produce.md`](../archive/where_to_produce.md) recorded as
unanswerable. `1_building_unlocks.txt` carries 119 `unlock_building = <type>`
blocks, each with an `age = age_N_...`; `3_production_method_unlocks.txt` carries
ten `unlock_production_method = <method>` the same way. So a method is available
when its building is unlocked — `can_build_building` in **country** scope, which
the trigger's own description says checks the country requirements — and, for
those ten, when `has_advance` is true. There is still no script-side
`ProductionMethod.IsAvailable`; this is the way round it.

**And where a building may stand is the other half of the same trigger, asked in
the other scope.** `can_build_building` documents itself as *"location only
checks local requirements, country checks the country scope requirements"*, so in
a **location's** scope it is the rank, the terrain and the building's own
`location_potential` — and never an advance. That distinction is what makes it
usable in a planning tool: it answers for ground nobody owns and for a building
nobody has unlocked yet, which is exactly what a plan for the end of the game
needs.

`location_potential` is where the real conditions live and they are not
decoration. `bog_iron_smelter` — the only building that makes iron without an
RGO — wants `is_adjacent_to_lake` or `topography = wetlands`; `sugar_plantation`
wants the location to already grow sugar *and* be overseas or a colonial
subject's. A tool that offers a good without asking this offers iron where there
are no bogs, which is what `where_to_produce`'s plan did for one load.

## Geography from script, and sorting a list

`region:<key>` and `area:<key>` are ordinary scope links — the game's own script
uses `region:italy_region` seventy times — and `every_location_in_region` /
`every_location_in_area` walk them. `map_data` is not in `reference/`, so the
membership is unknowable here, but the **keys** are: `region_names_l_*.yml` and
`area_l_*.yml` carry every one, with the continent/subcontinent hierarchy in
their comments. Two cautions, both paid for: the file's sections lie in places
(five real regions sit under "Subcontinents", `poland` is a region without the
`_region` suffix), and filtering water by name throws out
`north_atlantic_islands_region`, which is dry land — the "Ocean Subcontinent"
grouping is the thing that actually knows. A key that localization names but the
map does not define fails at load, in `error.log`.

`ordered_in_global_list` and its siblings take `order_by = <script value>` and
sort **highest first**: vanilla writes `order_by = { value = X multiply = -1 }`
on the one place it wants the weakest, and pairs `max = N` with
`check_range_bounds = no` when the list may be shorter than asked for. So
ranking needs no hand-written sort — but the ranking lasts exactly as far as the
next `every_*`. An unordered iterator gives no order back, so a list ranked into
`A` and copied into `B` with `every_in_global_list` reaches an interface in
whatever order the copy felt like, and a `datamodel` draws its rows in the order
its list holds them. Every hop is `ordered_*`, or the rank goes onto the item as
a variable and the last hop sorts on that.

**And nothing sorts on a fraction.** Every `order_by` in the game and in every
mod in `reference/` ranks on numbers in the thousands — `military_strength`,
`country_tax_base`, `population`, `pop_size`, or a score assembled out of
`add = 12000`. A `where_to_produce` ranking whose values ran 0.3000 to 0.3129
came back in the list's own order, sorted by nothing. Scale before ranking.

**A generic action's `effect` is not in the actor's scope.** Every one of the
game's five and every one of Advanced Auto Build's forty enters a named scope
first — `scope:actor` for the country, `scope:<target_flag>` for what was
clicked. Nothing anywhere relies on the bare scope, and an effect written for a
country runs there without complaint until it asks for a country variable.

## Sorting

Sorting is already data driven. `sort_by_key_button` entries name a sort key,
and `production_efficiency` is one of the keys vanilla exposes on building
lists, with `gfx/interface/icons/sort/efficiency.dds` as its icon. Ascending /
descending toggling is built into the button. So the sorting half of a
"most efficient buildings here" workflow needs no new code — only the filter.

There is no built-in sort key for the RGO bonus itself. Sweeping every
`sort_by_key_button` in vanilla turns up `rgo_profit` and `rgo_income`, which
are about raw material output, not about a building picking the bonus up.

## Localization is code, and the Russian files do not compile

A `.yml` value is not text with decorations in it. `[...]` is a data function,
`$...$` quotes another key, `@name!` is a texticon and `#tag ... #!` is
formatting, and the engine parses all of it before anything reaches the screen.
When the parse fails the key produces nothing — not a fallback, not the English,
nothing — and the failure lands in `gui.log` as
`Failed parsing localized text: <key>` or in `error.log` as `FetchData failed
for '<expression>'` followed by `Data error in loc string '<key>'`.

The game's own Russian files fail this way in 146 places. What they get wrong is
worth knowing because a mod can get it wrong the same ways:

**Brackets have to balance.** Fifty-five keys do not. `|W ед.` was meant to be
`|W] ед.` and swallowed the rest of the sentence; `«[[FinishedWarUnitStats` has
one bracket too many.

**An accessor has to exist.** `dump_data_types` lists every one, root and member
alike, so `python3 tools/api.py <name>` settles it. Thirty-six Russian keys call
things like `GetAdjectvive`, `GetGovernnment`, `GerHerHis` and `GetFinishedDate`,
and the last of those is instructive: it is not a typo but a stale name, and the
English key of the same name uses `GetFinishedDateIncludingQueue`. **Comparing
the two languages' version of the same key is the cheapest bug finder there is.**

**A name accessor ends the chain.** `Country.GetName.Custom('CL_GEN')` cannot
work: `GetName` has produced text, and text has no members. Twenty-seven Russian
keys do exactly this.

**A custom localization declares the scope it runs in**, and
`reference/game/docs/custom_localization.log` says which — `Scope: country`,
`Scope: location`, `Scope: international_organization`. Handed anything else it
returns nothing. `[Loan.Custom('CL_DAT')]` asks a loan for a country's declension.

**A `$key$` reference is not always transparent.** In a search filter's name or
description it loses the object the filter is being built for, while a data
function written inline in the same string resolves normally. The evidence is
two keys four lines apart in `lists_l_russian.yml` doing the same job two ways,
one of which never fails and one of which always does. Assume the same anywhere
a string is built per object, and inline the data function.

**Some faults only the engine can see.** A promote that returns `nullptr`
(`TOWN_RIGHTS` where the key meant `TOWN_RIGHTS_TYPE`), a scope that is not
supplied (`LOCATION.GetProvince` in a tooltip whose context is `Location`), a
`Cabinet.` promote the engine explicitly refuses in a cabinet action's tooltip —
none of these are visible in the file. They are visible in the log, which is the
argument for reading it after every run rather than only when something looks
wrong.

`mods/ru_loc_fix/tools/locscan.py` is all of this written as rules, and can be
pointed at any localization tree.

## The interface is about 27 800 widgets, and one call destroys one

Two numbers worth carrying, both asked of the files rather than guessed.

**Every `.gui` the game ships declares roughly 27 800 widgets between them** —
that is the whole interface, every window, counted as widget declarations across
`in_game/gui/`. The heaviest single files are `ui_library.gui` (1 420),
`location_window.gui` (988), `alertmanager.gui` (770) and `cooltip.gui` (627).
A live session holds about 37 000 right after loading, so the multiplier from
`datamodel` instances is modest. When a count in
`performance_degradation.log` reaches six figures, that is instances piling up,
not a heavy panel.

**`PdxGuiDestroyWidget( Arg0 )` exists** — `data_types_gui.txt:287`, "Destroy
widget", a **global function**, which is why a search over the methods of GUI
types missed it and this section said the opposite until 2026-09-19. It is the
only destroying call in the whole dump: `PdxGuiWidget` itself offers `Hide`,
`FindChild`, `FindParent`, `GetChildrenCount`, `CountVisibleChildren`, animation
control and highlight setters, and every other `Destroy`/`Clear`/`Free` in the
dumps belongs to a building, an asset editor or a variable system.

**What is still not proven** is whether a mod can call it at all — it appears in
no shipped `.gui` — and what it takes. The game's own shape for passing a widget
to a global function is `[F(PdxGuiWidget.AccessParent.FindChild('name'))]`
(`searchbar.gui:165`, `hud_bot.gui:1068`), so that is what `mods/widget_probe`
tries.

**And nothing enumerates children — проверено в игре 2026-09-19.** No data type
in any dump returns a list of widgets, and `AccessChild('(int32)N')` returns
`nullptr` for every N from 0 to 23 on a container with 23 children. `FindChild`
takes a name. So even a working destroy
cannot sweep — every widget it removes has to be named in advance, and the leaked
ones have no names a mod knows. `GetChildrenCount` is what a mod has instead: it
measures a tree from inside the game, level by level, and that is how a container
holding the leak would be found.

**The console is reachable too.** `ExecuteConsoleCommand('...')` is a global the
game uses on its own editor buttons, and one of those commands is
**`gui.clearwidgets`** (`ui_library.gui:18261`, the UI Library's close button).
What it actually clears is unknown.

## Defines, and where they actually live

Not under `common/defines/` where a Paradox habit would put them —
**`game/loading_screen/common/defines/`**, because they have to be read before
anything else loads. The tree carries them:

| | |
| --- | --- |
| `00_defines.txt` | the main file, ~148 KB, sections `NGame NGUI NText NCountry NAI NLocation NMarket NEconomy …` |
| `graphic/00_graphics.txt` | rendering |
| `jomini/00_tooltips.txt` | **tooltip timings** |
| `jomini/*.txt` | fog of war, rivers, roads, adjacencies, icons, map editor |

A defines file is overridable by a mod, and the game demonstrates it on itself:
`jomini/00_tooltips.txt` opens with `# This file overrides
cw/jomini/modules/tooltip_manager/data/common/defines/jomini/00_tooltips.txt`.

**`NGUI` holds nothing about widgets.** Twenty lines: rename length, how many
rows a breakdown shows, how many things Ctrl-click queues, side-menu margins,
food alert thresholds, hint carousel time. No pool, no cache, no arena, no limit.
So "raise the widget limit" has no knob — asked and answered, do not re-check.

One line in it is worth remembering anyway, because it shows the engine does
know how to evict things:

```
PURGE_COA_SEARCH_COUNT = 100 # How many COA entries we will search through in a frame for purging
```

Coats of arms get purged a hundred entries a frame. Widgets get no such
treatment, and nothing exposes one.

## What `can_build_building` is made of, and how to take it apart

**Read off the game's own `building_types/`, 2026-09-02**, because the plan needed
to override one half of it and keep the other. In a *location's* scope the answer
is the conjunction of:

- **the rank flags** the building declares at its top level — `rural_settlement`,
  `town`, `city`, `megalopolis`, each a bare `= yes`. A guild is `town = yes` and
  has no rural flag; `rural_glassmaker` is `rural_settlement = yes, town = no`;
- **its `location_potential`**, which is where the terrain lives (`stone_quarry`
  wants mountains, plateau or hills), and the market conditions
  (`is_produced_in_location_market = goods:sand`), and the one-RGO-per-location
  rule (`NOT = { raw_material = goods:stone }`). **26 of the game's production
  buildings carry one and 110 do not**, so for most of the manufacturing ladder
  the rank is the whole of the check;
- **an `allow` or a `country_potential`** where the building has one — twelve of
  the hundred and ten the mod uses, all exotic: a Japanese reform, an English
  tag, the Spanish cloth industry, a climate.

**So the rank can be replaced without losing the rest**: ask the
`location_potential` directly and answer the rank yourself. That is what
`bag_wtp_stands_<building>` does for `where_to_produce`, and the flags come from
`eu5data.Method.ranks` — parsed, not guessed. Where an `allow` or a
`country_potential` is in play the game is asked as before; a condition evaluated
wrong is worse than one not overridden.

**The four ranks are the whole ladder**: `rural_settlement`, `town`, `city`,
`megalopolis`. There is no fifth, which is what makes "not rural" and "takes a
guild" the same statement.

## What a `debug_log` string reaches, measured

**2026-09-02, by a dump printing it.** All of it is what a mod may write into
`debug.log` from an effect, and all of it was in doubt before the run.

| written | comes out |
| --- | --- |
| `[GuiScope.SetRoot(GetPlayer.MakeScope).ScriptValue('<sv>')|0]` | **the number.** This is the way to print anything |
| a localization key as the whole message | **the key itself**, unresolved |
| `[ROOT.GetName]`, `[SCOPE.GetName]` | **nothing** — «Could not find data system function 'GetName'», and the bracket is echoed |
| `THIS.MakeScope` | **nothing** — «Failed to convert statement for argument '0' for call 'SetRoot'» |
| `debug_log_scopes = no` | **the current scope, named**, on its own line: «Держава Валахия (WAL)», «Район Тырговиште (3574)». This is how a row says which location it is |
| `error_log = "…"` | **the line lands in `error.log` and in `debug.log` both.** A message sent to both sinks therefore arrives in `debug.log` twice |

**And square brackets in a `debug_log` string are data function syntax**, exactly
as in a localization value (`CLAUDE.md` carries the rule and this is where it was
paid for a second time): `given=[…]` printed a number, and `[glass, masonry]`
next to it made the engine look for a data system function called `glass`, fail,
and cut the rest of the line — `given=` arrived as a separate log entry. **Write
a list in round brackets.** The same run turned `[cannons, firearms, weaponry]`
into a rendered game-concept tooltip, which is the same fault wearing a hat.

## The debug toolbox

`debug_mode` in the console, then a toolbox appears. As of 1.3.11:

```
TOOLBOX     Language  Environment  Map menu  Inspect  Explorer  Unit Viewer  Errors
2D Tools    UI Editor  Animator  UI Bounds  UI Library  Workbench  Reload GFX
3D Editors  E. Designer  Animation Edit  Particle Edit
```

`Tweaker`, `DrawCmdsViewer` and `ScriptProfilerGui` are types in the data dumps
but have no button here, so they are not reachable this way.

`UI Editor` is the live widget tree — the one tool that can name a widget that
should not exist. `UI Bounds` outlines every widget on screen. `Inspect` reports
what is under the cursor. `Errors` is `error.log` in a window.

## Building types, production methods and goods

`common/building_types/*.txt` defines each building type. Production methods
come from either of two fields, and a type can use both:

- `unique_production_methods = { <name> = { ... } }` — written inline
- `possible_production_methods = { <name> ... }` — names resolved against
  `common/production_methods/`

A production method lists its goods inputs as bare `<goods> = <amount>` pairs
alongside `produced`, `output`, `category` and `debug_max_profit`. Everything
numeric except `output` is a goods input:

```
saltpeter_guild_demands = {
	pottery = 0.1961
	livestock = 0.9804
	produced = saltpeter
	output = 1
	category = guild_input
}
```

`common/goods/*.txt` marks each good `category = raw_material` or `produced`,
defaulting to `raw_material` when omitted. A location's RGO good is its
`raw_material` scope link, and `province = { any_location_in_province = { ... } }`
walks the province from a location — the two pieces needed to ask whether the
province produces something a building type consumes. That reconstruction
matches the game: `saltpeter_guild` consumes `livestock`, and the tooltip in the
buildings panel credits "Livestock in the province" for its efficiency bonus.

Building types also carry `location_potential`, a trigger with the location as
root, which is how vanilla gates where a type may be built at all —
`saltpeter_guild` wants `livestock` and `clay` in the market.
