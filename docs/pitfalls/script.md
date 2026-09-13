# Pitfalls: script

Split out of [`../PITFALLS.md`](../PITFALLS.md) on 2026-09-14, when that file went
over its budget. Everything here is a mistake made in this repository in script —
effects, triggers, values, variables — and the symptom that gave it away. **None
of them raises an error you would notice**; most of them do nothing at all, which
is the expensive kind.


## Где что живёт, и что молча не читается

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

## Триггеры: чью правду они говорят

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

## Синтаксис, который принимается и не работает

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

## Порядок, обходы и счётчики

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

## Чтение игровых файлов генератором

**Numeric-looking keys are not all goods.** `debug_max_profit = -1` on the
plantations was being counted as an input, turning four recipes' total input
weight negative. Match keys against the goods catalogue rather than against
"is it a number".

**A method with no `produced` outputs nothing.** A monastery burns clay for
upkeep, so it has no production efficiency for local clay to improve — which is
why the game gates its own shovel badge on `IsProducing`. Counting upkeep
methods put castles and monasteries in a list of things to build for their raw
materials.

## Скоуп, операции и форматы — цена одного слова

**A trigger copied out of a working file keeps that file's scope, and the scope
is not in the line.** `any_location_in_province_definition` exists in
`province_definition` only (`api.py` says so in one line). Copied out of
Construction Manager's coverage values — which are *evaluated* in that scope, as
their own file header says — into a location-scoped effect of ours, it never
passed once: every `_cov_<товар>` stayed zero, every `_rq<k>` with them, and the
«Пригодность» column printed 0 % in every row of the rights search while looking
like a calculation. Measured 2026-09-14 by diffing against `_b<n>` in the same
mod, which has drawn correctly since the day it was written and carries the
`province_definition = { }` step the copy dropped. **The diff against something
that draws is the first move, and here it was also the last one.**

**`change_variable` has no `value`.** Its operations are `add`, `subtract`,
`multiply`, `divide`, `modulo`, `min`, `max` — `api.py change_variable`. Written
as `change_variable = { name = X value = { ... } }` the block is accepted,
does nothing, and says nothing; the local output modifier it was meant to add to
a coverage was simply absent. `set_variable` takes `value`, which is where the
habit comes from.

**"Not in this tree" is not "not in the engine", and a search is not a
diagnosis.** `GetVariable('x').GetValue|%1` appears nowhere in the game's 430
uses of the `|%` format — every one of those is on a `ScriptValue`, a widget
function or a `$VAR$` — so a session concluded the form was invalid and rewrote
the swap list's percent around it. **The form works.** The owner, 2026-09-14:
«процент в правом списке и так был в порядке, я не просил его менять». The
column that really printed 0 % was somewhere else entirely, and the absence
proved nothing about either. `api.py` ends every answer with the same warning
for the same reason; it applies to a grep over the tree just as much.

## Один переключатель на два окна — это два разных переключателя

**У каждого окна свой тумблер эпохи, и расчёт обязан читать тумблер того окна,
которое его позвало.** «Считать на конец игры» в окне поиска пишет
`_rank_by_end`; такая же галочка в окне плана пишет `_plan_by_end`. Проход
покрытия гейтился на `_plan_by_end` **всегда** — и звали его оба окна. Значит в
поиске галочка не делала для столбца «Пригодность» ничего: он считал по тумблеру
соседнего окна, которого игрок в этот момент даже не видит. Владелец, 2026-09-14:
«ебучий мод опять не различает что он советует на "сейчас" и на "конец"… я уже
раз 50 на этой теме правки вношу за тобой».

**Лечится тем, что возраст приносит вызывающий**: общий проход читает одну
служебную глобалку, а каждое окно ставит её из своего тумблера перед вызовом.
Один расчёт, две точки входа, и разойтись они больше не могут.

**И подписывай эпоху там, где число от неё зависит.** Галочка стоит в одном окне,
число читается в другом, подсказка живёт третьей — «на какую эпоху это
посчитано» должно быть написано рядом с числом, а не выводиться игроком из того,
какие галочки он помнит нажатыми.

## Перенесённая формула — копия, а не пересказ

**Переписанная формула теряет ту строку, ради которой она и написана.** Счёт
пригодности земли под городскую грамоту был перенесён из Construction Manager
«по смыслу»: доля входа рецепта, которую даёт провинция, плюс местный
модификатор вывода в единицах `_trmm_rgo_unit`. В оригинале
(`bag_wtp_trmm_lm_<товар>`, перенесён в это дерево файлом) у этого слагаемого
есть **вычитание уже выданной здесь грамоты**, с его же комментарием: «A town
right granted here is subtracted, or it would raise its own fit». Пересказ этой
строки не содержал — и город, уже держащий королевскую грамоту на
книгопечатание, выходил лучшим местом, чтобы выдать её ему же: 236.1 % против
132.7 % у земли, у которой сырья и денег больше (его прогон 2026-09-14).

**Там же вторая потеря: частный случай, размазанный на все.** У него усреднение
собственного РГО (`add = 1`, `divide = 2`) стоит ровно у двух товаров, `dyes` и
`wine`, потому что модификатор вывода грамоты поднимает и собственное РГО именно
этого сырья. Пересказ применял его ко **всем двадцати**.

**Правило одно и оно уже стоит в `PITFALLS.md`**: «Возьми этот инструмент» — это
`cp` и замена префикса, а не новый код. Если чужое значение уже лежит в дереве —
**зови его**, а не пиши рядом второе с тем же именем в комментарии. Расхождение
двух копий одной формулы не видно нигде, кроме числа на экране, и заметить его
может только владелец, которому это число кажется абсурдным.

## Окно и эффект, которые обязаны договориться

**Число и его подсказка обязаны быть одним счётом.** Столбец «Пригодность» в
поиске по грамоте считал наш `_rq<k>` -- покрытие по **доступным** способам, --
а подсказка под ним рисовала разбор перенесённой карты (`_trmm_*`), то есть
числа Construction Manager, которые про эпоху не знают. На его экране 2026-09-14
подсказка говорила «76.1 %», столбец «236.1 %», и сойтись они не могли ни при
каких данных. Он прочёл это как «бардак», и был прав: **подсказка, которая
объясняет чужой расчёт, хуже отсутствующей** -- она не просто не помогает, она
опровергает то, что стоит рядом. Перенося чужой инструмент, переноси **или**
расчёт вместе с его объяснением, **или** ни того ни другого.

**Разбор показывает слагаемые, а не итог.** «Текстиль 100 %» он читать отказался:
«а с чего бы он 100%? Я этого не вижу». Число, сложенное из покрытия сырья и
местного модификатора, обязано показывать обе половины порознь -- иначе 236 % на
земле, у которой каждый товар меньше сотни, выглядит ошибкой, а не суммой.

**A list that offers what its own button refuses is a bug report waiting.** The
swap window's right column asked whether the building may stand here and never
asked the side, while every branch of the placement asks
`_plan_is_town`; so a village building sat in a city's list and «+» on it did
nothing at all. **Build such a list out of the placement's own gate** — one arm
per (good, side), side and room and free good together — and the list cannot
promise what the press will not do.

**Two entries for one good mean two gates, and the wrong one can eat the
press.** `mason` is one of the few buildings the game allows in a village **and**
in a town, so it carries a rural and a town entry for `masonry`. Both gates read
`_pm<n>` — the town variable — and listed the same method numbers, so in a city
the rural branch matched first, called an effect that asks `_plan_is_town = no`
inside itself, did nothing, and spent the one-shot counter; the town branch never
ran and the building could not be removed at all. **Each side reads its own
variable (`_pm` / `_prm`) and carries its own side in the gate.**

## Что стоит кадра

**A live script value in a list row costs a frame, every frame.** 74 rows each
labelled with `ScriptValue('bgt_impact_<good>')`, each of those reading a market
price and a default price, made the game visibly lose ticks whenever the Mod
Menu was open — and the figures still looked frozen, because what a row shows is
recomputed constantly rather than when the thing it describes changes. Compute
on a pulse into a variable and let the row read the variable; the same five
values inside one tooltip cost nothing, so it is the number of rows drawing them
that matters, not the values themselves.
