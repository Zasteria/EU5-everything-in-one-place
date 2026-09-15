# Community Mod Framework, and building on it

The framework both interface mods here depend on: its hooks, its Mod Menu
settings, the parts of its list machinery that fail without a word, and how
Construction Manager's automation is put together for an addon to reach.

## Community Mod Framework

CMF sets `cmf_active` as a global variable and keeps `cmf_active_mod_ids` as a
global list, so mods can detect each other. Glorp UI uses exactly that to check
for Construction Manager:

```
is_target_in_global_variable_list = { name = cmf_active_mod_ids target = flag:cm }
```

### Hooks

CMF adds the on_actions vanilla lacks. The important ones:

| on_action | Scope | When |
| --- | --- | --- |
| `cmf_on_mod_registration` | country | New game, save load and country transfer, per human country |
| `on_game_start_after_lobby` | none | New game, after country selection |
| `on_game_start_after_lobby_human_country` | country | Same, per human country |
| `on_game_load_after_lobby` | none | Save load, past the country selection screen |
| `cmf_on_country_transfer` | country | After the player switches country |
| `cmf_on_callback` | country | A CMM setting changed, or an alert / action bar button was clicked |
| `cmf_yearly_human_country_pulse` | country | Yearly, players only |
| `cmf_monthly_human_country_pulse` | country | Monthly, players only |

Vanilla `on_game_start` fires *before* the country selection screen, so
`is_ai = no` matches nothing there — that is what the `_after_lobby` variants
exist for.

A mod opts in by declaring the same on_action in its own file and appending a
leaf action; the engine merges the `on_actions` lists.

**And these are CMF's, not the engine's — checkable, not remembered.** The game's
own dump marks every one of them `From Code: No`
(`reference/game/docs/on_actions.log`); of the four hundred-odd on_actions it
lists, only `on_game_start` among the start and load hooks is `From Code: Yes`,
and it fires before country selection. So **a mod that wants to run anything at
load and does not want CMF has no on_action to use at all** — it has to drive
itself from a hidden window, the way `cm_maps` does. Established 2026-09-15,
building it.

### Mod Menu settings (CMM)

Registration effects, called from `cmf_on_mod_registration`:

- `cmm_register_bool_setting` / `cmm_register_global_bool_setting`
- `cmm_register_dropdown_setting` (+ `cmm_set_dropdown_multiselector`)
- `cmm_register_numeric_setting`, `cmm_register_slider_setting`
- `cmm_register_text_setting`, `cmm_register_button_setting`
- `cmm_begin_settings_list` / `cmm_add_settings_list_item` / `cmm_finish_settings_list`

`global` variants store one value for the session; the plain ones store per
country, which is what a per-player UI preference wants.

Keys are derived, and localization has to match:

| Thing | Key |
| --- | --- |
| Mod | `<mod_id>_name`, `<mod_id>_desc` |
| Tab | `<mod_id>__<tab_id>_name` |
| Group | `<mod_id>__<tab_id>__<group_id>_name` |
| Setting | `<mod_id>__<setting_id>_name`, `_desc` |
| Dropdown option | `<mod_id>__<setting_id>_option_<n>_name` |
| Button caption | `<mod_id>__<setting_id>_text` |

The GUI reads a setting back with `CMMSettingValue('<mod_id>__<setting_id>')`,
and `CMMSettingIsRegistered(...)` guards against the mod being absent.

Registering any CMM setting marks the mod active automatically;
`cmf_register_mod = { mod_id = ... }` does it explicitly.

### CMM list settings

A list setting is not like the others, in three ways that each fail silently.

**It is invisible without `<mod_id>__<setting_id>_on_changed`.** Registering a
list marks the setting as having a scripted GUI, and `CMMSettingRowVisible` then
gates the row on `CMMGuiIsShown(Concatenate(SettingKey, '_on_changed'))`. Absent
that scripted GUI the whole widget is hidden, header included. The *group*
header still renders, because `_cmm_register_setting_metadata` files a list under
`group_id = <setting_id>`, so a missing callback looks like an empty list rather
than a missing one.

**Lists have no auto-apply.** `cmm_core_auto_apply_scripted_gui.txt` covers
bool, dropdown, numeric, slider and button settings, and each of those fires
`cmf_on_callback`. A list does not: the widget marks the pending change and calls
that same `_on_changed` scripted GUI, which has to call `cmm_apply_list_change`
to commit it. Nothing about a list reaches `cmf_on_callback`.

**The dynamic builder runs once.** `cmm_begin_settings_list`, every
`cmm_add_settings_list_item` and `cmm_finish_settings_list` are gated on
`cmm_list_initialized_<setting>`, which `cmm_register_*_settings_list` sets. So
a list can be built dynamically *or* registered statically, never registered and
then refilled. For a list whose contents change, register it once at its full
height and write rows in place:

| Effect | Does |
| --- | --- |
| `cmm_set_list_item_value` | the scope or flag the row stands for |
| `cmm_set_list_data_value` | any field's value, bool fields included — they share one `cmm` variable map |
| `cmm_hide_list_item` / `cmm_show_list_item` | rows the current contents do not need |
| `set_variable = { name = <mod>__<setting>_i<n>_name value = flag:<key> }` | the row label, localized from the flag |
| `cmm_for_each_list_item` | calls an effect per row with the ordinal already resolved as `$i$` |
| `cmm_build_list_bool_list` | the values of the rows whose bool field is set |

Item ordinals must be literals — `item = var:x` is pasted into the macro verbatim
and dies at load with "More than one colon in event target link". CMF turns
counters into literals with a `switch`, and so should anything built on it.

**A row has a tooltip of its own.** `cmm_list_setting.gui` draws it from
`CMMLocalizedSuffixText(Key, '_desc')` and shows it only when
`CMMHasLocalizedSuffixText` says the key resolves, so defining
`<mod>__<setting>_i<n>_desc` gives row *n* a tooltip and defining nothing gives
it none. It is the only place a CMM row can say more than its one line.

**A tab and a setting may not share a name, and neither may two settings.** All
of them derive `<mod_id>__<id>_name`, so a tab `zone` and a list `zone` collide
on one localization key and one of them wins silently — and so do a list
`result` and a button `result`, which is how `where_to_produce`'s window button
came to be called `show`. Tabs otherwise cost nothing: a
`tab_id` on each setting is the whole of it, and it is the cure for a mod page
that scrolls past four groups to reach the fifth.

**A dropdown is clickable to twenty options, whatever its count says.** An
option's click runs `CMMExecuteGuiSuffix('CMM_MarkDropdownSelection_',
<widget index>)`, and CMF defines `CMM_MarkDropdownSelection_0` … `_19` and no
more. A dropdown registered with 218 options renders all 218 and scrolls through
them; clicking the twenty-first and beyond executes a scripted GUI that does not
exist, so the selection silently stays where it was. The equivalent for a list,
`CMM_MarkListPosition_*`, is unrolled to fifty and matches the item cap — so a
list is good to 50 and a dropdown to 20, and neither number is written anywhere
near the registration call that would care. `where_to_produce` found this by
having a player report that some rows "just would not pick".

**A button and a list may not share a `setting_id`.** Both want
`<mod>__<id>_name`, and the second registration loses — the same collision a tab
and a setting have. Symptom: one of the two renders under the other's label, or
not at all.

**Where the 50 actually lives, and what it does not cover.** The ceiling is
script side only, and it is two files: `cmm_core_list_setting_init_effects.txt`
and `..._runtime_effects.txt` unroll a chain of `if`s to item 50, about nine
times over — once for row metadata and identity, once per field type. The
unrolling is forced, not lazy: an ordinal has to be a literal. **The interface
has no cap** (`cmm_list_setting.gui` binds
`CMMHomeScope.GetList(Concatenate('cmm_list_items_', Scope.GetFlagName))`), and
**a dropdown has no cap at all** — `_cmm_register_dropdown_setting_internal`
stores `option_count` in a variable map and the GUI repeats over it, so a picker
with 218 options is one control rather than five lists. Raising the list ceiling
means replacing those two CMF files wholesale, which rides over every other CMM
mod in the playset on each CMF update; the way out is a window of one's own over
a plain global list, which Construction Manager already demonstrates.

**A row's label is a variable, not a key.** `CMMLocalizedSuffix(Key, Suffix)`
expands to `CMMVar(Concatenate(Key, Suffix)).GetFlagName`, and
`_cmm_initialize_list_item_metadata` defaults that variable to a flag of its own
name. So a static list is labelled by defining `<mod>__<setting>_i<n>_name` in
localization, and a row can be *re*labelled with any other key by setting the
variable — `set_variable = { name = <mod>__<setting>_i<n>_name value = flag:X }`
makes the row read whatever `X` localizes to, in every language, which is how a
list of the game's own regions costs no translation.

**How script reads a setting back.** `cmm_sync_setting_alias = { setting = ...
alias = ... }` copies out of the `cmm` map into a plain variable — global if the
setting was registered `global`, per country otherwise, which is what decides
whether a location-scoped trigger can see it. `cmm_sync_dropdown_option_alias`
sets or removes a variable per option index. And `cmf_on_callback` names what
changed in `var:cmf_callback`, as a flag.

**A list holds at most 50 items.** CMF documents `item_count` as `1..50`, and it
is not advice: `cmm_core_list_setting_init_effects.txt` initialises items
through an unrolled chain of `if`s that stops at 50. A longer list registers its
count and then leaves every row past the fiftieth uninitialised — counted,
undrawn, and silent. Anything with more rows than that has to be split into
several lists, and they cannot share their rebuilt output either, because
`cmm_build_list_bool_list` clears the list it writes into before filling it.

Two more things about a list's height, found while building one and never
confirmed in game:

- **A list cannot be registered empty.** `item_count` is clamped to at least one,
  so a list with nothing to show has to be hidden rather than emptied.
- **Re-registration only grows.** `_cmm_reconcile_list_setting_item_growth` adds
  rows and never removes them, so shrinking a list means clearing
  `cmm_list_items_<setting>`, removing `cmm_list_initialized_<setting>` and
  registering again — sending it back through the first-time branch. CMF itself
  has no caller that does this.

Construction Manager is the working reference: `cm_cmm_effects.txt` registers
statically and `cm_cmm_scripted_gui.txt` holds one `_on_changed` per list.

All three of those still hold in CMF 2.4.1, which reorganised the list code into
three files without changing the contract: `cmm_core_auto_apply_scripted_gui.txt`
still covers only bool, dropdown, numeric, slider and button, and
`loading_screen/data_binding/cmm_macros_settings.txt` still hides a setting
marked `_srsgui` unless `CMMGuiIsShown('<key>_on_changed')`.

### What CMF 2.4.1 added

Read off its `scripted_effects/`, not tried in game. Worth knowing before
building anything list shaped — the two marked below are what a hand written
selection sort and a static row-by-row registration were doing before 2.4.1:

| Effect | What it looks like it solves |
| --- | --- |
| `cmm_register_subtab` | a tab under a tab, so one mod's settings need not be one flat list |
| `cmm_move_list_item` | reordering rows, which a hand written selection sort currently does |
| `cmm_register_settings_list_from_list` | registering a list *from a script list*, instead of one static row at a time |
| `cmm_set_list_field_default_for_item` | per-row defaults, and the reset value |
| `cmm_disable_list_field_for_item` / `cmm_enable_list_field_for_item` | greying one field of one row |
| `cmm_set_list_field_conditional_format` | a field's format chosen by its value |

The ordinal rule is unchanged: these still take `item = <literal>`, and a
`var:` there still dies at load.

CMF 2.4.1 also grew an alert system (`cmf_alert_effects.txt`,
`cmf_sgui_alerts.txt`, `cmf_alert_settings.gui`) and a much larger
`cmf_log_effects.txt`. Neither has been read closely here.

Construction Manager 2.2.12 uses one engine effect this repository had not seen:
`set_automated_system = { system = expandbuildings activate = no }`, in a country
scope, which turns off the game's own building automation. It appears in no
vanilla file in `reference/`, so CM is the only evidence for it.

### Dev-сборки CMF и Construction Manager в дереве

Что в них нового и чего нет — [`dev_builds.md`](dev_builds.md).

### What a list field needs from localization

A field's column header is `<mod>__<setting>__<field>_name`, its hover is
`_desc`, and **a formatted field also needs its format keys**:

| Set by | Keys read |
| --- | --- |
| `cmm_set_list_field_format` | `_prefix`, `_postfix` |
| `cmm_set_list_field_conditional_format` | the same, plus `_prefix_high`, `_postfix_high`, `_prefix_low`, `_postfix_low` |

`cmm_macros_list.txt` decides whether a key exists by comparing `Localize(key)`
against the key itself, so a missing one does not error — the column prints the
key's own name where the number belongs. Construction Manager's
`cm__auto_build_list__min_discount_*` is the full set, colour codes included.

`tools/check_cmm.py` derives all of this from a mod's registration calls and
fails when one is missing.

### What CMM actually reads from localization

`cmm_setting_row.gui` builds a row's text from three suffixes and no others:
`CMMLocalizedSuffix(<setting key>, '_name')`, `..._desc` for the hover tooltip
and `..._text` for a button setting's caption. There is **no `_format` suffix
for a plain setting** — the only formatted values in CMM are *list fields*, and
those are opt-in through `cmm_set_list_field_format`, which sets prefix and
postfix keys per field. Advanced Auto Build ships five
`<mod>__<setting>_format` keys that nothing reads; they are harmless, but a
`_format` key is not the way to put a unit after a slider's number.

`_format` *is* real for a list filter, where `search_filter_<key>_format` goes
with a `range`. The two conventions are unrelated and easy to conflate.

### CMF's shared keys are overridable, for everyone

`CMM_NUMERIC_INCREASE_MAX` and `CMM_NUMERIC_DECREASE_MIN` are CMF's own keys and
are used by every mod's numeric settings. A mod can redefine them — Advanced
Auto Build does, to change the hint on its own sliders, wrapping the whole thing
in `SelectLocalization` on `Scope.GetFlagName` so other mods' settings fall back
to the original wording. It works, and whichever mod loads later wins the key,
so a translation of one mod has to reproduce the fallback in that language or
quietly change what every other mod's settings say.

### Localization goes in `main_menu/`

All three reference mods put every `.yml` under
`main_menu/localization/<lang>/`, including the text that only ever appears
in game — CMM settings, tooltips, filter chips. Both mods in this repository do
the same and work. Advanced Auto Build ships a byte-identical second copy under
`in_game/localization/`; nothing here needs it, and no reference mod does that.

### The source repository, and the wiki that is the actual contract

**CMF is developed in the open**, at
`github.com/Europa-Universalis-5-Modding-Co-op/community-mod-framework`, and its
own wiki folder there carries two files, cmf.wiki and cmm.wiki — the full API
reference, about nine thousand tokens the two of them. **The workshop copy in
`reference/` does not ship them**, so everything this repository knew about CMF
before 2026-09-01 was read off the framework's own script.

**Checked on 2026-09-01: the dev branch's `in_game` is byte-identical to our
reference copy.** So the API we code against is current, and the repository is
worth cloning for the wiki rather than for the files. Clone it read-only when a
question about a CMM call comes up; do not add it to `reference/`, which
`tools/refs.py` owns.

### Other CMF facilities

- `cmf_add_action_bar_element` / `cmf_remove_action_bar_element` put a button on
  the shared action bar instead of every mod drawing its own.
- `cmf_log`, `cmf_log_with_args` write to the shared mod action log, and
  `cmf_log_with_scope_arg` / `_args` take one and two country scopes besides
  (from `scope:cmf_log_arg1` and `scope:cmf_log_arg2`). `cmf_clear_log = yes`
  empties it. Every argument is a localization key. **Mod Menu > General >
  Session > Mod Action Log** is where it is read.
- `in_game/gui/vanilla/*_vanilla_types.gui` holds copies of vanilla widget types
  so several mods can restyle the same window without overwriting each other's
  copy of the vanilla file.
- **`Nand`, `Nor` and `Xor` are CMF GUI macros**, so a `visible` does not have to
  nest `And(And(Not(...)))` by hand.
- **`cmf_is_mod_active = { mod_id = X }`** answers whether another mod is loaded.
  A mod that registers CMM settings is detected for free; one that does not calls
  `cmf_register_mod = { mod_id = ... }` in its registration hook.
  `cmf_was_mod_active_at_game_start` is the same question about the save, and
  `cmf_game_start_mods_recorded` is false on saves older than the feature.
- **On-actions CMF shares**: `on_game_start_after_lobby`, `on_game_load`,
  `on_game_load_after_lobby`, each with a `_human_country` variant firing in
  country scope per human; `cmf_on_country_transfer`, which also copies the
  player's CMM settings across a tag switch, with `scope:old_country` and
  `scope:new_country`; and `cmf_yearly_human_country_pulse` /
  `cmf_monthly_human_country_pulse`, which are cheaper than every mod testing
  `is_ai = no` for itself.
- **`cmf_change_variable_map` and its local and global twins are deprecated** —
  `add_to_variable_map` overwrites an existing key by itself now.

### `cmf_suppress`, and why it is not to be reached for

```
if = { limit = { always = no }
	cmf_suppress = { v = my_variable }
	cmf_suppress = { v = my_flag } }
```

silences the engine's «Variable 'X' is used but is never set» and «Flag 'X' is
set but is never used». Group them in one `if` so `always = no` is evaluated
once.

**It silences the most useful line this repository gets.** «Variable
'bag_wtp_plan_open' is used but is never set» is the whole of how the plan
buttons' failure was found on 2026-09-01, and it was one line in a log otherwise
full of that same warning about harmless things. So: suppress a name only once
something has proved it harmless — `tools/check_script.py` catches the class
now, and its `check-script: never set` marker records the proof where the read
is. A blanket suppression buys a quieter log and costs the next run.

### CMM list fields, in full

A settings list takes a column per field, and there are more of them than this
repository has used. Registered after the list, all taking `mod_id`,
`setting_id` and `field_id`:

| field | what it is |
| --- | --- |
| `cmm_register_list_bool_field` | a tick, `default_value` |
| `cmm_register_list_numeric_field` | a number: `default_value`, `min_value`, `max_value`, **`step_value`** |
| `cmm_register_list_slider_field` | the same four, drawn as a slider |
| `cmm_register_list_dropdown_field` | `default_index`, `option_count` |
| `cmm_register_list_data_field` | **read-only, and the mod fills it** with `cmm_set_list_data_value` |
| `cmm_register_list_text_field` | display only; a cell is a loc key through `cmm_set_list_text_value = { … value = flag:<key> }` |
| `cmm_register_list_button_field` | stores nothing; a press arrives through the list callback |

`cmm_set_list_field_format` adds a prefix or postfix to a numeric, slider or data
field; `cmm_set_list_field_localization` repoints a field's text; and a field can
be disabled or an item hidden per item. **`cmm_register_list_data_field` is the
one worth remembering**: a number the mod computes and shows beside a good,
without another counter on a window's header.

## Construction Manager's automation, and how to add to it

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
otherwise — see [The game prints its own API](#the-game-prints-its-own-api).

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
