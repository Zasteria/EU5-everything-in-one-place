# Pitfalls

Mistakes already made here, each with the symptom that gave it away. Every one
cost at least one round trip through the game: none of them raises an error you
would notice.

**«Возьми этот инструмент» — это `cp` и замена префикса, а не новый код**, и
«соберём заново по подобию» оплачивается его прогонами:
[`archive/wtp2_failed.md`](archive/wtp2_failed.md), 2026-09-12.

**Молча не работает — сперва
[`pitfalls/how_to_fix.md`](pitfalls/how_to_fix.md)**, порядок действий, и только
потом этот список: правило, применённое не к тому случаю, стоило пяти сборок.

Two subjects outgrew this file and have their own, which `tools/kb.py`
searches like everything else:

- [`pitfalls/localization.md`](pitfalls/localization.md) — declensions,
  `customizable_localization`, `$NAME$` references, markup that renders as
  `ERROR:`, and the theory about culture tooltips that did not survive a run.
- [`pitfalls/reference_tree.md`](pitfalls/reference_tree.md) — what breaks when
  somebody else's mod updates under a generator.
- [`pitfalls/interface.md`](pitfalls/interface.md) — windows that draw outside
  themselves, skins that do nothing, view objects that resolve nowhere.
- [`pitfalls/diagnosis.md`](pitfalls/diagnosis.md) — how to find a fault that
  logs nothing, and how to spend a run on it rather than a guess. **Read it
  before proposing a cause for anything**: the four-theories episode is there.
- [`pitfalls/shipping.md`](pitfalls/shipping.md) — putting a mod out and getting
  it loaded: workshop tags, the app id, load order, `metadata.json`, and
  overriding somebody else's override.
- [`pitfalls/cmm.md`](pitfalls/cmm.md) — CMF and its macros: a call that fails
  silently, a list that loses its fifty-first row, a setting numbered from the
  wrong end.

## Script

**Two script values of the same name: the first wins, the second is dropped
silently** — the rule `customizable_localization` obeys too, and it costs the
same way: the wrong copy edited, nothing said anywhere. Two shipped in one day
on 2026-09-06. **`check_script.py` reports them now**, and the same folder rule
holds for both neighbours: a trigger lives only in `scripted_triggers`, a value
only in `script_values`, and each cost a run before its checker existed.

**A `building_type` filter receives the object as `this` — not `scope:target`,
and not `root` either.** Vanilla's `58_building_type.txt` promises both and has
neither: reading `scope:target` logs an error on every pass of the list, and
reading `root` logs nothing and matches nothing, which is worse. Measured
2026-09-09 — a chip on `target = root` left the list empty while its probe held
the location and the list it read was populated on 454 locations; the only other
`root` reader here is `rgo_bonus_filter`'s location-panel pair, the one that had
never worked; `06_country.txt` says "root is player" in its own header. **Ask
`this` before any scope change**, literal on the far side, one `AND` branch per
object — a generator's job. `building` and `location` scoped filters do get
`scope:target`.

**One predicate in two places will drift, and the copy that decides is the one
nobody edits.** `_reach_<n>` — "could this country ever have this method" — was
computed twice: once to write the trigger, once to decide whether to ask it. The
writer learnt about `country_potential`; the asker did not, so 429 triggers were
generated correct and never consulted, and a Tibetan atelier stood in Westphalia.
Both now call `method_gates`. The symptom is the worst kind: the fix looks
present in the generated files.

**A partial report read as a whole one is a wrong answer with a number attached.**
`WTP BLDG ... built=0` covers only *multi-good* buildings; concluding "no foreign
building was placed" from it was reading an absence in a subset as a fact about
the plan. The rule this repository already has — an empty result is a fact about
the tree, never about the game — applies to its own diagnostics too.

**`local_<x>_building_levels` names a building, not a good — and the two look
alike.** `local_fine_cloth_guild_building_levels` raises the level cap of
`fine_cloth_guild`; stripping `_guild` turns it into the good `fine_cloth`, and
the charter then reads as "favours fine cloth" and pulls in every building that
makes it — a Tibetan atelier the bonus will never touch. Caught by the owner on
2026-09-09. A per-building bonus has to stay attached to its building: derive the
good from the building, and gate on the winning method being that building's.

**A trigger that models what the player *means* must never gate what the game will
*do*.** `where_to_produce`'s `_stands_<building>` deliberately obeys the mod's own
rank override — that is the whole point of a plan that says «I will make this
village a town». Ask it before queueing a real construction order and the game is
handed a town building for a village. The owner named this before it was built,
2026-09-09: «чтобы не вышло так, что я просто переключил в плане тумблер и сделал
село городом, а на самом деле там всё ещё село». Anything the engine acts on asks
the engine: `can_build_building` at the location, plus the country's own answer
for the advance.

**A scripted trigger answers the question its first caller needed, not the one
its name promises.** `bag_wtp_plan_right_fits_<k>` reads as «может ли эта грамота
тут стоять» and is built out of `_plan_can_town_<n>`, which also demands **a free
room** — true of the empty towns the grant pass walks, false of every town of a
finished plan. Reused by the editor 2026-09-06, it was false everywhere: «+1» on
a charter found no candidate and «−1» found nobody to hand the town to, one cause
and two symptoms, both reading on screen as «кнопка не работает». **A trigger
carried into a second pass is read line by line before it is called**, and where
the question differs it gets its own (`_edit_right_fits_<k>`: a method exists
here, and never mind what already stands).

**And the same file's other half of that lesson.** `_edit_place_town_<n>` ends on
`var:_load < cap` — a deliberate invariant, and the right one — so **a placement
can say no**. The charter swap planted the arriving bundle and squared the load up
afterwards, which loses a building whenever the new bundle is bigger than the one
it replaced, and loses it in silence. **Count the rooms and free them first**, then
count again afterwards: the second reading is what did not get in, and it is worth
a line on screen.

**A `province_definition` does not keep a variable.** It is static map data, not
a runtime entity — the runtime one is `province` — and a `set_variable` inside
`province_definition = { … }` writes nothing, silently. `where_to_produce`'s plan
kept each province's counters there and placed *zero* buildings out of 381
places, with not one line in `error.log`. **Nothing in vanilla or in any mod in
`reference/` writes a variable to a definition** — a province's state lives on
its locations (`every_location_in_province_definition`). A definition is still a
perfectly good *scope* to read through, and to iterate from.

**A `trigger_if` chain must end in a `trigger_else`.** Ending on a
`trigger_else_if` logs `PostValidate of trigger 'trigger_else_if' returned false`
and voids the whole trigger — `where_to_produce`'s «only where the building can
stand» filtered nothing for two loads. `trigger_else = { always = no }` closes it.

**A condition copied out of a game file carries the game's comments with it.**
`copperworking`'s `potential` has a commented-out clause under the live one;
folded onto one line for a generated trigger, the `#` swallowed everything after
it — closing braces included — and the file was unbalanced. **Strip `#` to end of
line, per line, before collapsing anything the game wrote.**

**A call to a name nothing defines is not reported where you would look.** The
patch that was to write `bag_wtp_right_row_is_worth_it` died half way; the
`limit = { bag_wtp_right_row_is_worth_it = yes }` that called it survived,
passed for every province, and the filter filtered nothing — the same symptom as
the `trigger_if` fault below and a run of its own to find. `check_script.py`
resolves every `<name> = yes` in a mod's own `common/` against the mod, the mods
in `reference/`, and the engine's own effect and trigger dumps.

**A trigger's conditional is `trigger_if`, and nothing else is.** `if` is an
*effect* in the engine's own dump and `else_if` is not in it at all. Written
inside `common/scripted_triggers/` they log `Unknown trigger type: else_if` once
per line and leave a scripted trigger that comes back **true no matter what** —
the worst failure a filter can have, because it filters nothing and looks
correct. `where_to_produce`'s "only where it can be built today" was that from
the day it was written, through fifteen loads, and the tick was on the list of
things "never reported" the whole time. The forms are `trigger_if`,
`trigger_else_if`, `trigger_else`; `tools/check_script.py` refuses the others.

**A file carries one byte order mark, at byte zero.** A second one is a
character in the text: the interface parser answers `'﻿' is not a valid
widget/type/property` and abandons the file — every type in it missing and the
only symptom in game a button that does nothing. Writing a string that already
begins with a BOM through `encoding='utf-8-sig'` is how it happens.
`tools/check_script.py` counts them.

**A ranking on fractions does not sort.** `where_to_produce` ranked provinces on
a method's effective output — 0.3000 to 0.3129 across the whole of Europe — and
the rows came back in alphabetical order of the province key. The tell is in the
tree: **not one `order_by` anywhere sorts on a fraction.** Scale until the
differences are whole numbers, and keep the scaled value out of anything that
prints.

**A scope rule applied to half a mod is not applied.** The `root`s the rule
below condemns were taken out of one pass and left in all 218 places of the pass
beside it, which cost the next run too. Grep the whole mod for the construct in
the session the rule turns up.

**A generic action's `effect` does not run in the actor's scope.** The three map
pickers in `where_to_produce` ended with two scripted effects written for a
country and no wrapper. The first was scope-agnostic line by line and ran
anyway — the count it maintains went on moving, which is what made the whole
thing look like it was working. The second opened with `has_variable` on a
country variable, got no, and did nothing. Symptom: a selection that is visibly
registered and an answer that never changes. Vanilla writes `scope:actor = { … }`
around every one of its five actions' effects and Advanced Auto Build's forty
touch nothing but `scope:target_location`; **not one existing action anywhere
relies on the bare scope**, which is the tell. Wrap it, and prefer `scope:` and
`this` over `root` in anything an action can reach.

**An unordered iterator will undo a ranking, and nothing says so.**
`where_to_produce` sorted into one global list and copied that into the window's
datamodel with `every_in_global_list`. `every_*` promises nothing about order,
and a window draws its rows in the order its list holds them, so every hop
between lists has to be `ordered_*`. Cheapest guard: write the rank onto the row
and print it, so a shuffle is visible rather than looking like a ranking nobody
understands.

**`max` on an ordered iterator counts what it visits, not what you keep.**
`where_to_produce` ranks locations and keeps one row per province, since every
location of a province scores the same. With `max = 50` on
`ordered_in_global_list` it filled about a dozen of its fifty rows and looked
like a ranking that had run out of answers — the walk was spending its fifty on
the other locations of the same provinces. Any pass that filters inside the loop
has to ask for enough iterations to reach the rows it wants, and say in a comment
what the ratio is.

**A comment saying a trigger was confirmed is not a confirmation.**
`gates.py` gated 492 religious aspect hints on `country_religion = religion:X`,
under a comment reading "confirmed in common/religious_aspects". It is not there
and never was: `country_religion` appears nowhere in the game's script and is
not in the engine's trigger dump. What those files carry is
`religion = calvinist` — the aspect declaring its own religion, a different
thing in a different scope. The country trigger is `religion = religion:X`, 598
uses in the game's own `common/`.

Nothing caught it for months because a wrong trigger name in a
`customizable_localization` gate does not stop the mod loading; the gate simply
never passes and the lines never appear, which looks exactly like a country not
qualifying for them. It was found the day a checker started comparing every
trigger name in the file against what exists. **Put the confirmation in a
checker, not in a comment** — a comment records what someone believed once, and
a checker re-establishes it on every run.

**Numeric-looking keys are not all goods.** `debug_max_profit = -1` on the
plantations was being counted as an input, turning four recipes' total input
weight negative. Match keys against the goods catalogue rather than against
"is it a number".

**A method with no `produced` outputs nothing.** A monastery burns clay for
upkeep, so it has no production efficiency for local clay to improve — which is
why the game gates its own shovel badge on `IsProducing`. Counting upkeep
methods put castles and monasteries in a list of things to build for their raw
materials.

**A live script value in a list row costs a frame, every frame.** 74 rows each
labelled with `ScriptValue('bgt_impact_<good>')`, each of those reading a market
price and a default price, made the game visibly lose ticks whenever the Mod
Menu was open — and the figures still looked frozen, because what a row shows is
recomputed constantly rather than when the thing it describes changes. Compute
on a pulse into a variable and let the row read the variable; the same five
values inside one tooltip cost nothing, so it is the number of rows drawing them
that matters, not the values themselves.

## Never invent a name for something the game already names

**2026-09-01.** A session called `royal_masonry_rights` «масонская хартия» — a
name that exists in no game of his. Nothing had been invented but the name; his
game says «Права на каменные и стекольные работы», one grep away.

**Name a rule, building, good or right by its key or by the string the game
shows** — never by a translation, never by a smoother phrase. He cannot check
the code, so a name he cannot find costs him the whole report.

## Deciding what exists

**"No mod here uses it" is not "the engine lacks it".** Subsidies were declared
GUI-only after grepping vanilla's `common/`, CMF, Construction Manager and Glorp
UI and finding only `ToggleSubsidizeBuildings` in a `.gui`. The engine has
`set_subsidized` and `is_subsidized`, both in the building scope, and a feature
had already been redesigned around their absence. The game prints its whole API
— `python3 tools/api.py <name>` answers in a second, and
`reference/game/docs/` is where those dumps live. Ask it before concluding
anything is impossible.
