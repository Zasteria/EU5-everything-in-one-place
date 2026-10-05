# Construction Manager

How CM's automation is put together, what it builds and why, and where an addon
or our `cm_dev_perf` can reach into it. Moved out of `cmf.md` 2026-10-04, when
the notes on CM outgrew the framework's.

## Where CM gets its buildings from

Read off CM Dev 2.3.0 in `mods/cm_dev_perf`, 2026-10-04.

**Production buildings are found in the game, from any mod.** At load
`cm_populate_building_types_to_process` walks `every_building_type` into the
global list `cm_building_types_to_process`, and the hidden window classifies
each; «Производство» takes whatever `cm_is_building_type_production_building`
passes. So a mod's production buildings reach CM with nobody listing them —
which is how National Destinies' ones were already built before `cm_dev_perf`
gave ND a list of its own.

**Everything else is a list the author wrote by hand.** The «Пользовательский»
sets — capital, market centres, control, and the roster «Выбрать здания» — are
spelled out in `cm_ab_custom_effects.txt` for 1.3. A mod's non-production
building is in none of them and CM never builds it. `cm_dev_perf` adds the
beta's new ones and every buildable ND building from the files, at build time
(`mods/cm_dev_perf/tools/buildings.py`); nothing scans in the game.

**The game does not tell script which mod a building came from.** No
`BuildingType` function in the GUI dumps names a source (checked 2026-10-04;
the dumps, not a run). The only way to tell is from the other end: a list of
the vanilla types written in at build, and anything not on it is a mod's. That
list then follows the game's version, not the playset. Proposed to him
2026-10-04 as the way to take in any mod's buildings without a rebuild; he
rejected the other way (a list per mod, built from his playset copies) as
«костыль»: a mod must not need help from outside the game to work.

**A roster row is built only where all of these hold**
(`cm_ab_stage_roster_type_here`): proximity at least «Минимальная близость»
(default 1, `cm_ab_min_proximity_value`); room for another level; the location
may build it; no older tier of its chain standing; pops to staff it; the row's
own minimum control and minimum price impact; the RGO requirement; minimum
market access; a free queue slot. With control 0 and the cheapest discount a
row builds everywhere proximity is 1 or more — his 10-05 run, which looked
wrong and was the rules.

**«Пользовательский» spends one pool, in a fixed order**, in
`cm_ab_pass_custom`: capital, control (bailiffs, then max-control types),
market centres, the roster, and in `cm_dev_perf` the ND list last. Each takes
what fits until the share or «Золотой запас» (`cm_minimum_gold`) stops it.
Two traps in that file, both paid for:
- a row merged into the roster's lists builds only while «Выбрать здания» is on
  (`exists = var:cm_ab_custom_roster`): +perf23's ND rows staged nothing with it off;
- a capital type is both staged (`cm_ab_stage_capital_type_here`) and drained
  (`cm_ab_drain_capital_type`), in two lists; +perf20 added the beta's to the
  first only, and they were never approved.

**Buildings appear that no list holds.** «Автоматически улучшать все здания»
(priority row 4, `cm_run_upgrade_all_buildings`) rebuilds every obsolete
building into its replacement. In 1.4 the castle obsoletes the stockade, so an
advance can start castles across the country with no row ticked anywhere.

## CM and the game's own automation

**Systems are named as their cards are.** `AUTOMATED_SYSTEM_<NAME>` in the
localization; the lower-case name is what `set_automated_system = { system = x
activate = no }`, `is_system_automated = x` and `AutomatedSystemsItem.IsName('x')`
take. «Сооружения» is `buildings`, «Добыча ресурсов» is `rgo`.

**A building's auto-expand mark acts only while `expandbuildings` is on** — the
system's own description says so. Marks and system are separate state.

**CM takes over five cards and no more.** `cm_automation_lateralview.gui`
redraws `buildings`, `closebuildings`, `destroybuildings`, `expandbuildings`
and `expandrgo` so the card drives CM's feature instead. The Production tab's
right click (`multi_automated_tab` over `buildings`, `productionmethods`,
`closebuildings`, `subsidizebuildings`) still switches the vanilla systems.
`cm_suppress_engine_automation` turns the five off only on load and on a change
of country; `cm_dev_perf` repeats it monthly (+perf24). **`rgo` stays the
player's**: +perf25 turned it off too and he had it taken out — «не нужно,
чтобы мне принудительно выключали что-то, что можно использовать не мешая
остальному». Switch off only what collides with CM.

## The automation, and how to add to it

Read off CM 2.2.12. This is what an addon has to fit into.

**One dispatcher, monthly.** CM's `cm_unified_auto_expand` hangs off
`cmf_monthly_human_country_pulse`. It clears the queues, walks
`cm_priority_features_list` in the player's own order, and for each flag also
present in `cm_priority_features_enabled` runs that feature through a `switch`:

```
flag:cm_feature_auto_expand_buildings = { cm_run_auto_expand_buildings = yes }
flag:cm_feature_auto_expand_rgos      = { cm_run_auto_expand_rgos = yes }
flag:cm_feature_auto_build            = { cm_run_auto_build = yes }
...
```

Then, if anything was staged, it sets `cm_should_construct` and the queue window
builds it.

**The switch has no default branch.** Appending a feature flag to CM's lists
from another mod therefore does nothing at all, silently — the flag matches no
case and the dispatcher moves on. A new feature has to reach the cycle some
other way: a leaf action of its own on `cmf_monthly_human_country_pulse` (which
merges cleanly), staging into CM's queues and setting `cm_q_staged` /
`cm_should_construct` itself.

**There is already an ungated queue.** `cm_stage_ungated_candidate` files a
location and building type into `cm_q_ungated_locations` /
`cm_q_ungated_building_types`, which skip the profitability and minimum-discount
gates entirely. CM's own Auto Build feature is built on it: it walks the building
types the player ticked and stages them in every owned location, checking only
build-queue slots and `cm_location_can_auto_build`. An addon that must ignore the
profit gates should stage there rather than invent a queue.

**Auto Town Rights is a priority walk with no delegation point.**
`cm_run_auto_town_rights` walks `cm_auto_town_rights_list` — an ordered list of
`town_rights_type` values built from its CMM list — and for each right walks
owned locations, granting where `has_max_town_rights = no`,
`cm_can_grant_specific_town_right_at_location` and affordability allow, then pays
`price:grant_town_rights`. The right granted is `scope:cm_town_right` and nothing
else: there is no branch where another mod could say "ask me which right this
town wants". Structurally the same fact as the feature dispatcher's `switch` with
no default branch — **CM is extensible where it chose to be, and a marker entry
in one of its lists is not one of those places.** An addon that wants a
per-location right grants it itself: `grant_town_rights` is a plain location
effect, and the gates above are readable from script.

**The granary mode is a location variable too.** CM's per-location food toggle
(`cm_set_auto_food_for_location`) sets `cm_auto_food_location_enabled` on the
location and pins it with the `cm_auto_food_locked_location` modifier; a second
pair, the country's `cm_auto_food_rgo_types_enabled` against the location's
`cm_auto_food_location_excluded`, is the mass form, and that one also passes
through CM's own river filter. So the manual opt-in reads in one word, and the
mass form does not without repeating a trigger of CM's.

**The auto-build tick box is three variables, and that is the whole of it.** The
two-up-arrows icon (`gfx/interface/icons/flat_icons/mass_upgrade.dds`) beside a
building in the production panel is CM's, drawn by
`cm_auto_expand_existing_building_button` for a standing building and
`cm_auto_expand_new_building_button` for a type not built yet. Both write the
same state, which is per **location and building type**:

| variable | scope | meaning |
| --- | --- | --- |
| `cm_auto_expand_registered_building_types` | location | ticked here |
| `cm_mass_auto_expand_building_types` | country | ticked everywhere |
| `cm_auto_expand_excluded_building_types` | location | untick, against the mass list |

So it is **on** when the location's registered list holds the type, or the
country's mass list holds it and the location's excluded list does not. Turning
it on means: mass list holds the type → remove it from the location's excluded
list; otherwise → add it to the location's registered list. Off is the mirror.
`cm_apply_auto_expand_toggle` is the original, and it takes `scope:cm_set_off` to
set rather than flip. An addon that wants to arm a set of buildings hands CM this
and stops — CM's own monthly cycle then decides when and what to build.

**Feeding that queue needs no CM name at all — write its variables.** A call to a
scripted effect or trigger CM does not ship breaks in a place nobody looks
(`PITFALLS.md`), and an addon has to survive CM being absent. Variables have no
such problem: `add_to_variable_list = { name = cm_q_ungated_locations target =
<location> }` on the country, `cm_q_ungated_building_types` on the location,
`cm_q_staged` up by one, and `cm_should_construct` set — the queue window hangs
off that variable, not off who wrote it. Mirror
`cm_stage_location_and_type_to_queue` exactly, including clearing the location's
`cm_q_done_ungated_types` the first time it is added. With CM absent, the writes
land in variables nobody reads.

**But the monthly leaf order decides whether it survives.** CM's dispatcher is a
leaf of `cmf_monthly_human_country_pulse` and *starts by clearing every queue*.
Another mod's leaf on the same pulse runs before or after it depending on file
merge order, which nothing in CMF or the game guarantees. Staging before CM's
leaf is erased in the same tick, and on screen that is indistinguishable from
"there was nothing to build" — so an addon that stages here has to print its own
count and let a run say which side of the dispatcher it landed on.

**The gates it would be skipping** are `cm_should_rgo_auto_expand` and its
building equivalent: gold on hand, nothing already under construction, a metric
gate (`cm_priority_min_profit` per feature) and a discount gate
(`cm_priority_min_discount` per feature).

**Construction cost discount is readable in script.** CM computes it per
building type in `cm_construction_cost_adjustments_script_values.txt`, weighting
each construction good by `cm_construction_demand_<good>`, and clamping to the
engine's own `define:NMarket|MIN_PRICE_IMPACT` / `MAX_PRICE_IMPACT`, which are
-0.33 and 3.0. The per-good half comes from Glorp UI's
`glorpui_construction_good_adjustment`, which is plain
`market_price(good) / default_price(good)`. So "how far is this good from the
33% cap" is answerable from script at any moment.

**Subsidies are scriptable**, though no mod in `reference/` does it:

```
set_subsidized    change whether a building is subsidised or not   scope: building
is_subsidized     checks if a building is subsidized               scope: building
```

That pair was written off here as GUI-only, because `ToggleSubsidizeBuildings`
and friends appear in `production_lateralview.gui` and nothing in vanilla's
`common/` or in any reference mod touches a subsidy. The game's own dump says
otherwise — see [The game prints its own API](engine.md#the-game-prints-its-own-api).

`subsidizebuildings` is also one of the game's own automated systems, alongside
`expandbuildings` and `expandrgo` — CM turns those two off with
`set_automated_system = { system = <x> activate = no }`.

## Автостройка CM: флажок на локации есть, и он — список на локации

Измерено на CM 2.2.12, 2026-09-04, под вопрос «наш мод ставит флажки
автостроительства пачкой, дальше CM сам». **Ответ: да, и писать есть куда.**

**Первый заход этой сессии был неверен** — он нашёл только массовую функцию
(`cm_auto_build_building_types_enabled`, список типов на стране, кнопка с двумя
стрелками в общем окне продукции) и заключил, что пофлажковой записи у зданий
нет. Есть, просто в другом файле. Владелец поправил скриншотами окна конкретного
города.

### Где на самом деле лежит флажок

**Ванильный флажок — состояние движка и только для существующего здания.**
`ToggleAutoExpandBuilding(Building.Self)` и `IsAutoExpand(Building.Self)` —
**функции GUI, не эффекты**: в дампе эффектов их нет, и область у них
`Building`, то есть построенное здание. Отсюда и ограничение, которое CM
снимает: **нет здания — нет области — ваниль не может предложить галку**.

**CM хранит своё, и это обычные списки переменных:**

| список | где лежит | что значит |
| --- | --- | --- |
| `cm_auto_expand_registered_building_types` | **на локации** | типы, включённые в этой локации поимённо |
| `cm_auto_expand_excluded_building_types` | **на локации** | исключения из массового режима |
| `cm_mass_auto_expand_building_types` | на стране | массовый режим, «строить везде» |

`cm_scripted_gui.txt:401` (`cm_set_auto_expand_for_building_type`, корень —
тип здания, плюс область `cm_location`) — это и есть галка на здании, которого в
локации ещё нет. Проверка — `cm_is_auto_expand_active_for_building_type:410`:
включено, если тип в списке локации **или** включён массово и не исключён.

### Как это включать из чужого мода

Два пути, оба открыты:

1. **Позвать эффект CM.** `cm_apply_auto_expand_toggle`
   (`cm_feature_effects.txt:221`) — обычный scripted effect, область — локация,
   ждёт `scope:cm_building_type` и необязательный `scope:cm_set_off`. Сам
   разбирает массовый режим и исключения. **Но это жёсткая зависимость**: без CM
   в плейсете имени не существует.
2. **Писать список самим.** `add_to_variable_list` по
   `cm_auto_expand_registered_building_types` в области локации. Имя списка —
   просто строка, поэтому **без CM это ничего не ломает**: запись лежит
   непрочитанной. Взамен придётся повторить одну ветку CM: если тип уже включён
   массово на стране, включать надо **снятием** из
   `cm_auto_expand_excluded_building_types`, а не добавлением в список локации.

**Второй путь предпочтительнее** — мягкая зависимость за счёт одной
воспроизведённой ветки.

**И очередь без гейтов здесь ни при чём.** `cm_stage_ungated_candidate` — это
как добавить в CM свою *функцию*; чтобы просто поставить галки, нужен список
выше.
