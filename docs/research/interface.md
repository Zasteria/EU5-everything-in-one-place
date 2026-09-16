# The interface

Split out of [`engine.md`](engine.md) when it outgrew its budget: which panel is
which, how a list filter is scoped, what a view object can and cannot be read
from, what a scripted widget costs, and what the game's own map selection is made
of.

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

## Which window is which

Three different panels list buildings, and they are easy to mix up:

| File | View object | Lists |
| --- | --- | --- |
| `location_production_lateralview.gui` | `LocationProductionView` | Buildings of one location — the "Buildings of <town>" panel |
| `production_lateralview.gui` | `ProductionView` | Buildings across the whole country (macrobuilder) |
| `build_location_lateralview.gui` | `BuildInLocationLateralView` | Locations to build one chosen building type in |
| `location_window.gui` | `LocationView` | The location panel itself, where the RGO badge is drawn |

`location_production_lateralview.gui` is the one to target for a
"only what is efficient here" filter. Its list is
`LocationProductionView.GetBuildingsSortSearch.WithFilterTags('building')`, its
items are `BuildingItem`, and its sort keys are `name`, `profit`, `income`,
`production_efficiency` and `level`. Glorp UI does not override this file.

## List filters

`in_game/gui/filters/*.txt` defines filters declaratively, and
`filters/readme.txt` documents the schema. The fields that matter:

| Field | Meaning |
| --- | --- |
| `scope` | Object type the filter runs on; `root` is that object |
| `trigger` | Script trigger deciding whether the object passes |
| `tag` | Pipe separated list; a view exposes filters whose tags intersect its `WithFilterTags(...)` call |
| `group` | Groups filters under one UI background |
| `exclusive_group` | Radio button behaviour inside the group |
| `invert` | Exclude by default, include when ticked |
| `enabled_at_start` | Initial tick state |
| `hidden_in_searchbar` | Filter works and appears in the side menu, but shows no chip — for panels with a dedicated button |
| `range` | `min` / `max` / `step` / `format`, exposes `scope:min_value` and `scope:max_value` to the trigger |

Localization keys are `search_filter_<key>_name`, `_desc` and `_format`.

Sub-items matter: "For lists with sub-items, if one of the sub-items pass the
filter, the entire item pass it." That is how one `building` tag serves filters
scoped to `building_type` (`58_building_type.txt`), `building`
(`42_building.txt`) and `location` (`05_location.txt`) at once.

For building scoped filters, `root` is the building or building type. **The
location is not passed in**, which is the awkward part for anything province
dependent — the viewed location has to be parked in a global variable by a
scripted GUI probe first. Glorp UI does much the same for Construction Manager's
own R.G.O. filter, storing the viewed building type through
`cm_rgob_store_selected_type` from a zero sized widget with
`trigger_on_create = yes`. What else a filter can read depends on its scope; see
[Filter scopes](#filter-scopes-what-a-trigger-actually-gets).

**Two mods that need the same probe must share it, or the later one silently
wins.** The probe has to live inside the panel it reads, so every mod wanting the
viewed location overrides `location_production_lateralview.gui` — and the game
keeps one definition of a window name. `rgo_bonus_filter` and `where_to_produce`
therefore ship *one* probe under names belonging to neither
(`bag_view_location`, `bag_store_view_location`,
`bag_view_location_is_current`), in two byte-identical files
(`gui/location_production_lateralview.gui` and
`common/scripted_guis/bag_shared_view_location.txt`). Either mod alone works,
both together work in any load order, and `tools/check_script.py` fails the build
when the copies drift.

Filters are the right tool rather than hiding rows from the GUI: the list body
is a `fixedgridbox` with a fixed row height, so a hidden row still occupies its
cell and leaves a gap.

Not every filter key is script defined — `hide_estate_only_buildings` is
referenced by `SearchBar.EnableFilterByKey` in three panels but appears nowhere
in `gui/filters/`, so some are built into the engine.

## Filter scopes: what a trigger actually gets

`58_building_type.txt` opens with "root is the building_type / scope:target is
the country to filter". The second half does not hold: no vanilla
`building_type` filter ever reads `scope:target`, and one that does matches
nothing and logs an error on every pass of the list. Only the `building` and
`location` scoped files use it (`building_can_be_upgraded_by = scope:target`,
`owner = scope:target`), so treat it as available there and absent here.

**The first half does not hold either, measured 2026-09-09.** `root` in a filter
trigger is *not* the object being filtered. A `where_to_produce` chip built on
`is_target_in_variable_list = { name = ... target = root }` left the list empty
while its probe had the location (`view_location=1`) and the list it reads was
populated on 454 locations; the only other `root`-reading chip in this
repository, `rgo_bonus_filter`'s location-panel pair, is precisely the one that
had never worked, while every chip asking the implicit `this` works.
`06_country.txt` says "root is player" in its own header, so root is likely the
player throughout. **Ask the filtered object as `this`, before any scope
change**, and put a literal on the far side of one:

```
bag_wtp_type_in_plan_here = {
	has_global_variable = bag_view_location
	OR = {
		AND = {
			this = building_type:clay_pit
			global_var:bag_view_location = {
				is_target_in_variable_list = { name = bag_wtp_plan_builds target = building_type:clay_pit }
			}
		}
		… one branch per type
	}
}
```

A `building_type` filter therefore sees `this` and global variables, nothing
else. Anything else a filter needs — the location on screen, a user setting —
has to be parked in a global variable first. CMM settings registered with
`cmm_register_global_bool_setting` land in the global half of the `cmm` map, and
`cmm_sync_bool_alias` then mirrors them onto a plain global variable a trigger
can read.

Evaluating a view's data in a always-present widget needs a guard: reading
`LocationProductionView.GetSelectedLocation` while no buildings panel is open
logs an error every frame. Taking it as a `datacontext` on a child widget and
gating that child on `Location.IsValid` keeps it quiet.

Square brackets in a localization value are data function syntax, so a display
name like `[debug] location known` renders as `ERROR:` — brackets have to stay
out of plain text.

## View objects are panel scoped

`LocationProductionView`, and by the look of it the other `*View` objects, only
resolve inside the widget tree of their own panel. Vanilla never reads
`LocationProductionView.GetSelectedLocation` outside
`location_production_lateralview.gui`; other files only call the global
`ShowLocationProductionView(...)` to open it.

Reading one from a scripted widget fails, and fails loudly — a zero sized always
present widget doing so logs on every frame:

```
FetchData failed for 'Location.IsValid' - gui/bag_rgo/bag_rgo_location_probe.gui:22
Promote 'AddScope' returned nullptr, in 'GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('bag_rgo_loc', Location.MakeScope).End'
```

The `datacontext` silently yields nothing, so every expression depending on it
fails. Scripted widgets themselves work fine — the file loads and its states run
— but anything panel scoped has to be injected into that panel's own file.

`error.log` names the file and line for GUI failures, which makes it the fastest
way to tell "the widget never loaded" from "the widget loaded and its
expressions fail". Script side failures show up there too; a filter trigger that
merely returns false logs nothing at all.

## Scripted widgets

`in_game/gui/scripted_widgets/*.txt` maps `<gui path> = <widget name>`, one per
line, and the engine instantiates those widgets into the running interface. That
is how a mod adds behaviour without copying a vanilla `.gui`. CMF registers
twelve of them this way; `python3 tools/guicost.py --drivers` lists what every
mod in the tree registers, so nothing here has to remember a count.

Global view objects such as `LocationProductionView` stay readable from any
widget, so a scripted widget can observe a panel it is not part of.

CMF's change detectors are the pattern to copy. `cmm_window_open_gate.gui` uses
`state = { trigger_when = "[...]" on_start = ... }`, which fires when the
condition turns true and re-arms once it goes false again — no polling, and no
`trigger_on_create` juggling. `cmf_country_transfer.gui` shows the older variant
built on `GetVariableSystem` plus `TriggerAnimation`.

**They never come down.** A scripted widget is registered for the session, not
for as long as it is useful, and hiding it with `visible = no` hides a live
widget tree whose `visible`, `enabled` and `datacontext` expressions are still
asked every frame. So the cost of one is its whole subtree, paid from load,
whether or not the player ever opens the mod. CMF's twelve come to 104 widgets
and Construction Manager's three to 96 — probes, which is the size a scripted
widget is meant to be. Advanced Auto Build registers seven whole windows,
**14 125 widgets**, against a vanilla interface of about 27 800 in total.

**`GetScriptedGui('x')` is the expensive expression.** It runs a script trigger
from the interface, entering the script engine, and vanilla uses it **nine
times** across 387 `.gui` files — it is not what the base game reaches for. A
count in the thousands means a mod has moved its logic into the interface layer
and is paying for it every frame the widget is alive.

**An animation state that names itself as its own `next` is a timer.** Inside an
always-live window that is a background worker with no off switch;
`eu5ab_engine_queue_window` runs eight of them at 0.15 s, each walking a
`datamodel` of locations × building types and calling
`GetBuildOrExpandBuildingCost`, `GetBuildingTypeProfitInLocation` and
`CanBuildOrExpandBuilding` per pair. The window keeps itself "visible" with
`[EqualTo_CFixedPoint('(CFixedPoint)0', '(CFixedPoint)0')]` and parks at
`position = { -10000 1 }` so it ticks offscreen.

**A `datamodel` multiplies whatever is inside it, so a static widget count is
not a cost.** `cm_hidden_window` declares twenty-three widgets and binds
`datamodel = "[GetGlobalList('cm_building_types_to_process')]"`; what lives is
that subtree once per building type, and there are 465. Two more datamodels nest
inside each row, over the type's construction demand entries and its production
methods. Whenever a number is meant to be about cost rather than about files,
find what the window repeats over first.

`python3 tools/guicost.py` counts all of it across the game and every mod in the
tree, with `--drivers` for the always-live windows, their loop periods and the
lists they repeat over. What it cannot know is which mods the player actually
runs — `reference/` is not the playset, and `python3 tools/playset.py <logs>`
reads the real one out of the mount table in his `debug.log`. It was
written for the question *why does a panel open instantly in vanilla and with a
hitch under the playset*; the answer it gives is in
[`../investigations/panel_hitch.md`](../investigations/panel_hitch.md).

## Число, которое движок отдаёт только интерфейсу, — как его получает скрипт

**Прочитано в коде Construction Manager 2.3.0 (dev), в игре не проверено.** Это
ответ на то, из-за чего `where_to_produce` намеренно не моделировал стоимость
постройки: `GetBuildOrExpandBuildingCost`, `GetBuildingTypeProfitInLocation`,
`GetBuildingTypeIncomeToOwnerInLocation`, `CanBuildOrExpandBuilding`,
`CanUpgradeToBuilding`, `GetMarketAccess`, `GetTotalIncome`,
`GetRGOProfitPerLevel` — функции данных, а не скриптовые триггеры: из скрипта их
не видно вовсе.

**Дорога одна и она через `AddScope`:**

```
GetScriptedGui('cm_ab_score_build').IsShown(GuiScope.SetRoot(Location.MakeScope)
    .AddScope('cm_cost',  MakeScopeValue(GetBuildOrExpandBuildingCost(BuildingType.Self, Location.Self)))
    .AddScope('cm_can_build', MakeScopeBool(CanBuildOrExpandBuilding(BuildingType.Self, Location.Self)))
    .End)
```

а scripted GUI объявляет `saved_scopes = { cm_cost cm_can_build ... }` и читает
их как `scope:cm_cost`. `MakeScopeValue` и `MakeScopeBool` — обёртки, без них
число не становится скоупом.

**Отсюда два следствия.** Первое: такое число доступно **только там, где есть
виджет** с нужным `datacontext`, — то есть в открытом окне или всегда живом
scripted widget, а не в проходе по миру из эффекта. Второе: CM поэтому и устроен
как «окно очереди считает, скрипт потом одобряет»
(`cm_queue_approval_effects.txt`), а не как один проход.

## Долгий расчёт без фриза — батчами по тикам драйвера

**Тоже из CM 2.3.0 (dev), по коду.** Два приёма, оба про то, чтобы тяжёлый проход
не был одним нажатием: `cm_proximity_finder_effects.txt` считает пачку
кандидатов за тик всегда живого виджета, пока не кончатся, и кеширует результат;
`cm_slice_effects.txt` берёт за цикл не всю страну, а вращающееся подмножество
рынков (`@cm_slice_location_budget = 300`), так что цена прохода у огромной
державы такая же, как у средней.

## Карта глобалок с ключом-скоупом — и почему это зацепка для пикера

**Найдено 2026-09-05, не проверено в игре.** Движок держит полноценные
*variable maps*: `add_to_global_variable_map = { name = X key = Y value = Z }`,
`remove_from_global_variable_map`, `clear_global_variable_map`, обходы
`every_key_in_…` / `ordered_key_in_…` / `random_key_in_…`, триггеры
`is_key_in_…`, `is_value_in_…`, `global_variable_map_size`,
`has_global_variable_map`. Со стороны интерфейса ключ читается
`GetVariableFromGlobalVariableMap('имя', <скоуп>)` — так CMF печатает свой лог
(`cmf_log_loc`).

**Зачем это `where_to_produce`.** Пикер редактора расписан по товару — 47 ячеек
руками — **потому что строка datamodel несёт скоуп товара, а скоуп не достаёт до
нумерованной глобалки `_pn<n>`**. Из-за этого ячейки стоят на фиксированных
местах, и на земле, которая умеет 35 товаров из 47, в сетке двенадцать дыр:
владелец, 2026-09-05, «если их грамотно упорядочить — места они станут занимать
раза в 2 меньше».

**Карта снимает ровно это ограничение**, если её значением может быть число:
`_pn` кладётся в карту с ключом `goods:X`, и строка datamodel читает свой
счётчик через `GetVariableFromGlobalVariableMap`. Тогда пикер становится
datamodel'ом — то есть упакованным, — и вопрос выравнивания исчезает вместе с
дырами.

**И карта, возможно, не нужна вовсе — товар сам себе скоуп.** `every_goods`
существует как эффект, значит скрипт входит в товар как в область и может
положить на него переменную; `Goods.MakeScope` есть в дампах и возвращает
`Scope`, а `Scope.GetVariable` — та самая форма, которой этот мод уже читает
`_r_good_<n>` с локации. Тогда цепочка короче карты:

- скрипт: `every_goods = { … set_variable = { name = bag_wtp_n value = … } }`,
  где значение берётся из `_pn<n>` через диспетчер по товару — их тут и так
  полно;
- интерфейс: строка datamodel по `_edit_pool` → `Scope.GetGoods` →
  `Goods.MakeScope.GetVariable('bag_wtp_n')`.

**Это ровно то, что владелец спрашивал трижды** — «почему мод не может сам
вычислить, каких товаров не окажется, и просто не добавлять их в список». Может.
Не «ячейки расписаны по товару, поэтому нельзя», а «счётчик негде было взять, и
теперь есть где». Кнопки «+1»/«−1» при этом получают товар как скоуп и
диспетчеризуются внутри эффекта — мост, который однажды убрали ради надёжности,
возвращается с одним разбором вместо двух путей.

**Что не проверено, и проверять это первым.** **Держит ли товар переменную на самом деле — не
установлено**: `every_goods` и `Goods.MakeScope` есть в дампах, но записи на
товар в этом дереве не встречается ни у игры, ни у модов, а дерево неполное.
Это первая проверка, и она дешёвая — один `set_variable` внутри `every_goods` и
одно чтение на экране. Карта (значением которой, по документации, идёт event
target, а не число) — запасной путь, если товар переменную не держит. Вторым
идёт `fixedgridbox`:
это то, чем игра рисует сетку по datamodel во всех 138 случаях, а единственная
здешняя попытка нарисовала ячейки друг на друге — вероятнее всего от нехватки
`addcolumn`/`addrow`/`datamodel_wrap`/`flipdirection`, а не потому что виджет не
годится. `flowcontainer` с datamodel — тот, что ронял игру, — сюда не годится
и проверять его снова не нужно.


## Ползунки экономики: запись есть только у интерфейса, и только через сам ползунок

Искано под `war_sliders` 2026-09-16, по полным дампам, а не по памяти.

**Скрипт до них не достаёт вовсе.** В `effects.log` нет ни одного эффекта на
чеканку и на содержание армии, флота, крепостей; `set_maintenance` и
`lock_maintenance` есть, но их scope — `bureaucracy`, то есть институты.
`set_automated_system` знает систему `finances` целиком и отдельных ползунков
не знает.

**У интерфейса дверь одна.** Чеканка — `EconomyView.OnChangedCoinMinting` +
`EconomyView.PostTaxes`, содержание — `MaintenanceSetting.OnChanged` +
`MaintenanceSetting.Post` (`economy_lateralview.gui:1105`, `:2060`).
**Аргументов ни один не берёт** — значение обработчику даёт виджет, а кнопки
«+»/«−» сидят внутри движкового `ranged_slider` и функции под собой не имеют.
Отсюда единственный незакрытый вопрос: срабатывает ли `onvaluechanged`, когда
значение поменял `mincap`/`maxcap` чужого ползунка, привязанного к тому же
объекту. Ванильный комментарий на `economy_lateralview.gui:2059` («set value
first or setting the min/max/mincap/maxcap changes the existing value») и пара
`PdxGuiWidget.DisableValueUpdate`/`EnableValueUpdate` говорят, что привязка
значение двигает, и молчат о том, доходит ли это до обработчика.

**Что ванильная автоматика делает — это её собственные тексты, не догадка.**
`AUTOMATION_MINTING_ZERO_ON_TT` = «Automated Minting with 0 Monthly Inflation»:
держит месячный прирост в нуле, накопленное не отыгрывает.
`TOGGLE_AUTO_ARMY_MAINTENANCE_TOOLTIP_OFF_TT` = «**Raise** the army maintenance
automatically **at the start of a conflict**»: опускающей половины нет.

## `ExecuteConsoleCommand` — консоль игры доступна виджету

`ExecuteConsoleCommand('<команда>')` зовётся из `onclick`/`on_start` как любая
другая функция, и команда `effect <любой скриптовый эффект>` делает из неё
полноценный мост «интерфейс → скрипт» без `scripted_gui`. Так CMF отправляет
текстовые настройки (`cmm_text_setting.gui`) и чистит свой лог
(`cmm_log_pane.gui:96`). Команды, которые уже встречаются в чужих модах:
`debug_mode`, `fow`, `InstantConstruction`, `InstantSiege`, `YesMan`,
`age <ключ>`, `gui.ClearWidgets <окно>`, `Log.ClearErrorLog`.

CMF прячет такие настройки за `cmf_core__enable_unrestricted_tools` — то есть
считает их читерскими, а не недоступными: в обычной игре они работают.
