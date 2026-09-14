# Glorp UI — Societal Value Hints

The societal value tooltip, with the sources Glorp UI's generator never looks
at. Glorp UI reads laws, government reforms and estate privileges; the game
pushes societal values from **23 source types in 1 426 places**, and the rest of
them are here — religious aspects, parliament issues, international
organizations, buildings, employment systems, chivalric orders, cabinet actions,
subject types, estates, religious schools, missions, advances, special statuses,
parliament types, and the modifiers that scale with the state of the country or
switch on under a condition. Each line is gated on whether the country can
actually reach it.

**It also used to give Glorp UI's own list a text in all eleven languages**, and
that is why it exists at all. Glorp UI's 2026-08-28 build ships those eleven
itself, in the opener-per-language shape worked out here, so the mod stopped:
Russian is still this mod's wording, and the other ten are Glorp UI's own. What
remains everywhere is the handful of hints this mod *changes* — the privileges
an advance has to unlock first, which Glorp UI still recommends to a country
that cannot take them.

Requires **Glorp UI** (`glorp.ui`) and must load **after** it — the mod overrides
Glorp UI's own override of the tooltip templates, carrying their block across
byte for byte. `.metadata/metadata.json` declares the dependency, so the
launcher orders it.

> **Confirmed in game, 2026-08-25.** Both blocks render in Russian on the
> societal value tooltip. Everything the 2026-08-27 rewrite changed — eleven
> languages, the category nouns as game concepts, the advance gates — is unrun.
> The list is in [what is untested](#what-is-untested).

## Somebody else's addon to the same mod

`Glorp UI small fix` (workshop 3784988919) translates Glorp UI's own hint keys
into **ten languages** and adds three fixes of its own. It does *not* extend the
hint lists — the 364 keys of extra sources below are this mod's alone — so the
two overlap only on the translation half, where whichever mounts later wins.
The full comparison, with numbers, is in
[`the comparison`](../../docs/archive/glorpui_small_fix.md).

**Both things worth taking from it have been taken**, and neither is his text:

- his file carries the log line that settles *why* a `customizable_localization`
  cannot be overridden, which is what
  [the advance gates](#the-hints-that-have-to-wait-for-an-advance) are built on;
- his phrasings put the verb after the object in German, Turkish, Japanese and
  Korean, which is the reason the openers here are written with a `{ref}`
  placeholder rather than as a prefix. The words themselves are ours.

## What it fixes

Hover a societal value and the tooltip offers **«Дальше продвинуться в сторону
X:»**. In a Russian game that block said **«Нет.»** for every axis, and in an
English game it was thin — a handful of national reforms and nothing else.

**The empty list** is a localization fault. Glorp UI removes the game's built-in
C++ hint block and replaces it with its own lists, whose text lives in 759
`GLORP_UI_SVH_*` keys — shipped in `english/` and in no other language. Paradox
games load the localization folder of the selected language only, with no
fallback to English, so on a Russian client every one of those keys is missing,
the list renders empty, and `debug.log` collects 725 lines like this on every
single load:

```
[jomini_custom_text.cpp:220]: Missing loc key 'GLORP_UI_SVH_CENTRALIZATION_PV_PETTY_BUREAUCRACY'
    for custom localization 'glorpui_svh_centralization_pv_petty_bureaucracy' (or variant),
    at 'common/customizable_localization/glorpui_generated_societal_value_hint_loc.txt:3'
```

The bug is not Russian-specific: it hits all ten non-English languages. The
right fix upstream is for Glorp UI to emit its generated file for every
language, even with English text in it, so the feature does not switch itself
off for everyone who plays in something else.

**The thin list** is a scope fault, and it is Glorp UI's generator being honest
about what it read: government reforms, laws/policies, estate privileges and
advances. The game pushes a societal value from far more than that. Every push
in the game is a `monthly_towards_<direction>` modifier — 34 of them, one per
direction, all flagged `is_societal_value_change = yes` in
`common/modifier_type_definitions`. Scanning every game file for them finds
**1405 pushes across 23 kinds of object**:

```
laws                442      static_modifiers   298      government_reforms 235
estate_privileges   150      auto_modifiers      87      religious_aspects   60
traits               24      parliament_issues   24      building_types      23
employment_systems    9      chivalric_orders     8      subject_types        6
international_orgs    5      estates              5      cabinet_actions      5
regencies             5      religious_schools    4      missions             4
disasters             3      advances             2      parliament_types     1
```

Glorp UI covers three of the twenty-three. That is why *defensive* was empty for
an ordinary country: of its thirteen candidates almost all are national —
`luc_libertas` (Ragusa), `katepanata`, `partitio_reform`, `margraviate` — and a
normal country qualifies for none.

## What it adds

A second block, **«Также влияет на смещение»**, under Glorp UI's own, and a
third, **«Станет доступно при условиях»**, for what is out of reach today but
not out of reach forever. A fourth, **«Влияет на смещение (без фильтра)»**,
replaces both when the mod menu switch is on. 264 hint lines across all 34 directions, of two kinds:

- **catalogue lines** — something to pick or to build: employment system,
  buildings, religious aspects, religious schools, parliament issues, chivalric
  orders, subject types, estates, cabinet actions, international organizations,
  advances, missions;
- **system lines, marked «масштабируется»** — always in force and growing with
  the state of the country: fort/army/navy maintenance, army size and
  experience, average control, average development, literacy, estate shares of
  the population, war and peace, attacker and defender, fort limit, legitimacy.
  Plus "point the cabinet at this value", for each of the 34 directions.

For *defensive* that is 0 → 15 lines, including `fort_maintenance_mod` and the
four parliament issues about building forts. The employment example lands too:
«Способ найма рабочих: Равенство +0.10».

### Filtering by availability

138 of the lines are wrapped in `customizable_localization` with a trigger and
disappear when the country cannot have the thing, and 78 more are listed under
«Станет доступно при условиях» instead. By category: religious aspects 120,
parliament issues 24, international organizations 24, buildings and religious
schools and subject types and chivalric orders and cabinet actions 65 between
them, employment systems 9, estates 5, missions 4, parliament types 2.

| Category | Gate |
| --- | --- |
| Religious aspects | `OR = { religion = religion:X ... }` + `NOT = { has_religious_aspect = ... }` |
| Religious schools | the object's own `enabled_for_country` block, copied verbatim |
| Estates | `country_has_estate = estate_type:X` |
| Parliament issues | `has_parliament = yes` + the estate that raises it + the issue's own `potential` and `allow` |
| Cabinet actions | the action's own `potential` and `allow` blocks, verbatim |
| Subject types | `is_subject_type = X` |
| Chivalric orders | `has_chivalric_order = yes` |
| Buildings | the object's own `country_potential` and `allow` blocks, verbatim |
| Employment systems | `NOT = { has_employment_system = employment_system:X }`, for itself and for every stronger option |
| International organizations | `exists = international_organization:X` + `can_join_international_organization = international_organization:X` |
| Status in an organization | membership of, or joinability of, the organization that grants it |
| Missions | the mission's own `visible` block, verbatim — which opens with `game_has_missions_enabled = yes` |
| Parliament types | the object's own `potential` and `allow` blocks, verbatim |

Argument forms come from `reference/game/docs/triggers.log`, the output of the
console's `script_docs`, where each trigger states its **Supported Scopes** and
**Supported Targets**. `has_employment_system` declares
`Supported Targets: employment_system`, which is where the `employment_system:`
prefix comes from. Nothing is guessed: a trigger form that does not appear
verbatim in the shipped files leaves the line ungated instead, because a
mistyped trigger is a load error and an ungated hint is only noise.

Employment systems are mutually exclusive, so an option is hidden not only when
it is already chosen but when any other option is chosen that pushes the same
axis at least as hard. With *Equality* (+0.10) active, every
`capitalism_prioritising_*` (+0.05) and *Equality* itself drop out.

**The organizations, missions and parliament types were the ungated ones**, and
they are the four the owner asked for on 2026-08-25: the Italian leagues showing
up for a country that can never join one, parliaments a monarchy cannot have,
and missions listed in a game where missions are switched off. Each is gated by
the game's own answer rather than by a guess:

- **`can_join_international_organization`** is an engine trigger, country scope,
  organization target — it is in the engine dump `reference/game/docs/triggers.log` and this mod simply asks
  it. The organization's own `can_join_trigger` cannot be copied instead: it is
  written against `scope:recipient`, which *is* the organization, and a country
  scoped customizable localization has no such scope. `exists` comes first
  because most of these are situational — the Italian leagues exist only while
  the Italian Wars run — and it is the guard the game puts in front of its own
  organization checks.
- **Missions** take the mission's own `visible` block verbatim, which every one
  of them opens with `game_has_missions_enabled = yes` — the game's own scripted
  trigger for the Missions game rule, `NOT = { has_game_rule = mission_packs_disabled }`.
  So a game with missions switched off loses those lines outright. `enabled` is
  deliberately not copied: it answers "can this be finished now", which changes
  month to month, where a hint only needs "is this a thing this country can be
  offered".
- **Parliament types** take `potential` and `allow` verbatim, the same shape as
  buildings. The ones belonging to an international organization gate on
  `international_organization_type`, which is asked of an organization and not
  of a country, so those are left ungated rather than copied into the wrong
  scope.

**Cabinet actions and parliament issues came back from the first run still
unfiltered**, and both were the same oversight: the object carries its own
`potential`, and the mod was not reading it.

- *Дикастерия по евангелизации* and *Влияние Строгановых* were on screen for a
  Catholic German county. They are `office_of_new_converts`, whose `potential`
  wants a location modifier on Kazan, and `stroganov_influences`, whose
  `potential` wants the Stroganov variable. All eight cabinet actions that push
  a societal value carry a `potential`.
- All four *Поддержка строительства …* parliament issues showed at once, when
  only one can ever be valid: `promote_castle_building` requires
  `has_advance = castle_advance` and forbids bastions, star forts and
  fortresses; the other three say the same thing one rung up. `has_parliament =
  yes` could not know that. The issue's `estate` goes in too, because an issue
  is raised by an estate and a country without that estate never sees it.

Copying `potential` verbatim also drops the two issues that carry
`potential = { always = no }` under a comment saying they are driven by events —
which is right, they are not something a country can be offered.

Nothing is left ungated now except what a trigger cannot reach.

Left out entirely: `traits`, `regencies`, `disasters` (situational, not the
player's choice) and the Byzantine `auto_modifiers` branch (hellenization and
latinization, ~50 objects, BYZ only).

### The switch, and what it is for

Filtering is the point, but a filtered list cannot be checked against itself.
`Списки → Фильтрация → Показывать всё без фильтра` in CMF's mod menu turns the
two filtered blocks off and one unfiltered block on: every line the direction
has, with no trigger in front of any of it. For the rare game where the plan is
to fight your way into a region you start nowhere near, and for answering "is
this filtered out, or is it simply not there".

**Confirmed in game 2026-08-25.** It is a `.gui` condition and nothing more —
`CMMSettingIsRegistered('svx__show_all')` and `CMMValueEqualsOne(...)`, both GUI
functions — so no script runs and the unfiltered body is a plain string that
cannot fail. The registration is the mod's only hand written script:
`in_game/common/scripted_effects/svx_cmm_registration.txt` on CMF's
`cmf_on_mod_registration`. `python3 tools/check_cmm.py
mods/glorpui_hints/in_game/common` checks the call against whichever CMF is in
`reference/`, and checks that every localization key CMM derives is defined.

The switch is per country rather than global: it is a reading preference of the
person looking at the tooltip, and CMF's global variants store one value for the
whole session, which is for rules rather than for what a player wants to see.

### Why «масштабируется» says nothing more than that

It was made to say more, twice, and both attempts came back off the screen.

The information exists and is exact for part of it: an `auto_modifier` declares
`scales_with`, an ordinary script value block, so the value at which the
modifier reaches full size is arithmetic — `army_tradition multiply = 0.01` is
full at 100, `used_fort_limit_percentage subtract = 1.0` at 200%. A
`static_modifier` declares nothing and the engine scales it, so *Средняя
грамотность* has no answer at all. That asymmetry is in
[`research/engine.md`](../../docs/research/engine.md) in case it is ever wanted.

What killed it was not the arithmetic. **A hint line is one row of a
`TooltipScrolledStringPairList`, and its left half is narrow.** Putting
"(масштабируется: максимум при used_fort_limit_percentage = 200%)" in there
truncated the labels themselves — *Традиции армии* rendered as «Традиции армии (
…» and *Во время войны* as «Во вр …», with the bracket spilling across the
value column. And where the modifier had nothing to declare, the honest
"(масштабируется, показан максимум)" was two words saying what «до +0.10»
already said.

The attempt before that put it in a hover instead and failed differently — see
[`PITFALLS.md`](../../docs/pitfalls/localization.md). The line is back to the
label, «(масштабируется)», and the number.

### Scaling versus conditional

Sources from `static_modifiers` / `auto_modifiers` split in two, and the value is
written differently for each:

- **scaling** — the magnitude grows with the state of the country (fort
  maintenance, army size and experience, average control, estate shares). Marked
  «масштабируется», value written as «до +X», which is the maximum;
- **conditional** — switched on whole when a condition holds (bankruptcy, war,
  over the fort limit, a ruler who is a general). No marking, the condition is
  named in the line itself, and the value is exact.

## What is in the folder

```
.metadata/metadata.json                                     id bag.glorpui_hints, depends on glorp.ui
.metadata/thumbnail.png                                     512x512, carried over from the two mods this replaces
main_menu/localization/<language>/                          eleven of these, identical key sets
  glorpui_generated_societal_value_hints_l_<lang>.yml       Glorp UI's 759, plus the five held back
  svx_extra_hints_l_<lang>.yml                              the added lines, body keys and gated ones
  svx_menu_l_<lang>.yml                                     the CMF mod menu entry
main_menu/localization/russian/
  svx_glorpui_fixes_l_russian.yml                           four keys of Glorp UI's own, repaired
in_game/gui/svx_extra_societal_value_hints.gui              the two tooltip templates, overridden
in_game/common/customizable_localization/svx_extra_hint_loc.txt   availability gates
in_game/common/customizable_localization/svx_unlock_gate.txt      the advance locks
in_game/common/script_values/svx_extra_hint_script_values.txt     visibility values
in_game/common/scripted_effects/svx_cmm_registration.txt          the mod menu switch
workshop/description_english.bbcode                         the workshop page, ready to paste
workshop/description_russian.bbcode
```

Everything under `main_menu/` and `in_game/` is generated except
`svx_cmm_registration.txt`. `svx_` is this mod's prefix for the names it puts
into the game's namespace. `workshop/` is not uploaded — `tools/mods.py` copies
only what the game mounts, and [`docs/WORKSHOP.md`](../../docs/WORKSHOP.md) is
how the upload works.

**Three of those files have no words in them at all** — the `.gui`, the two
customizable localizations and the script values are the same bytes whatever
language is running. That is the whole reason eleven languages cost eleven
`.yml` files and nothing else.

## Rebuilding

```
python3 mods/glorpui_hints/tools/generate.py
```

That is what `tools/refresh.py` runs, and it does two different jobs.

**Glorp UI's hint text is regenerated every time, in the languages
`SHIP_GLORP_HINTS` names** — Russian, since their 2026-08-28 build ships the
other ten itself — out of its own English file, see
[why a hint costs an opener](#why-a-hint-costs-an-opener-rather-than-a-translation).
A Glorp UI update that adds hints is picked up with nobody noticing; one that
writes a fourth shape fails the run and names the key.

**The added lines are not**, because they are compiled out of the game's own
`common/` tree, which is large and only partly needed. It is all in `reference/`
now — see [where the game files come from](#where-the-game-files-come-from) — so
the rebuild is one flag away, and the files are committed rather than rebuilt on
every run because the scan takes a minute:

```
python3 mods/glorpui_hints/tools/generate.py --game-files reference/game
```

### What the run checks even when it rebuilds nothing

The mod's real hazard is not a load error. It overrides Glorp UI's override and
**re-emits Glorp UI's own list inside it**, so if Glorp UI restructures those
templates nothing fails at load: the player quietly gets this mod's older copy
of Glorp UI's list and never sees what Glorp UI added. Nothing in `error.log`
would say so.

So every run compares the two files as an ordered sequence of tooltip lists —
which script value gates each one, which title it carries, which body key it
prints — and fails naming the difference:

```
Glorp UI now lists GLORP_UI_SVH_BODY_NEWTHING (glorpui_svh_visible_hellenization)
in SocietalValueCountryRight_tooltip and this mod does not — rebuild with --game-files
```

### What this mod writes over, listed

Three surfaces, and it is worth knowing they are only three, because each one is
a place where a Glorp UI update is reverted for anyone running both mods:

```
python3 mods/glorpui_hints/tools/generate.py --conflicts
```

1. **the two tooltip templates** — this mod's `blockoverride` replaces Glorp
   UI's wholesale, so their entries live here as a copy;
2. **the `GLORP_UI_SVH_*` keys in Russian** — 764 of them, against Glorp UI's own
   759, which is this mod's wording winning over theirs. In the other ten
   languages it is ten keys: the five hints held back until an advance unlocks
   them, and their text. Until 2026-08-28 it was all eleven languages, 7 920
   keys, most of which said exactly what Glorp UI's own file said;
3. **four of Glorp UI's own interface keys**, repaired in Russian only.

Run it before rebuilding against a new Glorp UI and again after: the first says
what their update changed, the second whether the rebuild picked it up. It also
names a repair that has stopped being needed, which is a repair worth deleting.

It also checks that every name the `.gui` reaches for resolves: each script value
is defined here or by Glorp UI, each `[Localize(...)]` key exists, each
`[Player.Custom(...)]` has a rule behind it, and each rule is actually printed by
something. A `.gui` asking for a name nothing defines does not fail to load — it
prints zero, or the raw key, which is the exact fault this mod exists to repair.

**And every trigger the gates call is a name that exists.** A mistyped trigger is
a load error — but in the *player's* game, a round trip away. Three sources
answer it together: the engine's dump, the game's `scripted_triggers/`, and
every name the game itself writes in the same position anywhere in `common/`.
The third is not optional: `religion = religion:catholic` and
`culture = culture:low_frankish` are scope comparisons, appear in the dump
nowhere, and the game writes them 598 and 1 418 times.

The check earned itself on the first run. `country_religion = religion:X` gated
**492** religious aspect lines and `country_religion` does not exist — not in the
dump, not anywhere in the game's script. The comment in `gates.py` claimed it
was confirmed in `common/religious_aspects`; what those files carry is
`religion = calvinist`, the aspect declaring its own religion, which is a
different thing in a different scope. It is `religion = religion:X` now.

## Eleven languages, out of about fifty strings each

The mod shipped in Russian. It ships in **English, French, German, Spanish,
Brazilian Portuguese, Polish, Russian, Turkish, Simplified Chinese, Japanese and
Korean** — the eleven folders every mod in `reference/mods/` carries and the
whole set the game has.

That was measured before it was built, because the number decided whether it was
a project or an afternoon. The mod's Russian is **1123 keys** and a language
needs nothing like that many translations:

| what | keys | what a language actually needs |
| --- | --- | --- |
| Glorp UI's own hint keys | 759 | **3 openers** |
| our catalogue lines | 284 | **nothing** — the category is a game concept |
| our data-function lines | 34 | nothing — no words in them |
| the rest of ours | 46 | about **45 short strings** |

Everything a player reads is in
[`tools/languages.py`](tools/languages.py), one table per language, and nothing
anywhere else. The generators hold no words at all.

### Why a hint costs an opener rather than a translation

One line of Glorp UI's English file:

```
@hint! Grant #TOOLTIP:ESTATE_PRIVILEGE,kormlenije #L $kormlenije$#!#!: #color_green +0.10#!\n
       ^^^^^ ^-------------------- the reference -------------------^  ^-- the number --^
```

Since 2026-08-28 Glorp UI writes the same reference as the engine's own data
function instead, and the parser takes either:

```
@hint! Grant [ShowEstatePrivilegeName('petty_bureaucracy')]: #color_green +0.20#!\n
```

Only the opener is language specific. The reference is what makes the
privilege's name appear and hover, and the game resolves it in whatever language
the player runs, in either shape, so it is copied through byte for byte. The
file is therefore the English file with the opener replaced, which is also why a
Glorp UI update that adds hints is picked up **in every language at once**
without anyone noticing it happened.

Each opener is written with a `{ref}` placeholder rather than as a prefix,
because German, Turkish, Japanese and Korean all want the verb after the object:

| | |
| --- | --- |
| english | `Grant {ref}` |
| russian | `Даровать привилегию {ref}` |
| german | `Privileg {ref} gewähren` |
| japanese | `{ref}を付与` |

**Rendering English gives Glorp UI's own file back character for character**, and
that is checked on every run. It is the proof that splitting a hint into opener,
reference and number loses nothing — the ten other languages have no original to
be compared against.

### The fourteen category nouns are not translated at all

"Religious aspect", "Advance", "Subject type" and the rest are **game concepts**.
The game defines `game_concept_religious_aspect` in all eleven of its
localization folders, so `[religious_aspect|e]` renders it in the player's
language, with the encyclopedia link attached, for free.

That is what makes ten extra languages cost nothing on the largest block of
lines. It also **fixed seven Russian terms** that were synonyms rather than the
game's own word:

| | was | the game's own |
| --- | --- | --- |
| `advance` | Достижение | **Улучшение** |
| `subject_type` | Тип вассала | **Тип ленника** |
| `religious_aspect` | Аспект веры | **Религиозная особенность** |
| `mission` | Миссия | **Задание** |
| `employment_system` | Способ найма рабочих | **Система найма** |
| `parliament_issue` | Вопрос парламента | **Парламентский вопрос** |
| `international_organization` | Международная организация | **Международное объединение** |

The price is that a concept the game renames becomes a raw token on screen in
every language at once, and nothing errors. So every id is checked against the
game's own localization on every run, and `check_hints_have_labels` — the rule
that a label must carry text certain to resolve — admits a concept token only
because that check stands behind it.

`building_types` is the one category that stays a real phrase: all 23 of its
pushes are `capital_country_modifier`, so the line has to say *build it in the
capital*, and no game concept says that.

### The hints that have to wait for an advance

Glorp UI's filter, `glorpui_svh_privilege_takeable`, reads a privilege's own
`potential` and `allow`. **Ten vanilla privileges are locked from the other
side** — by an advance's `unlock_estate_privilege` — and their own `potential` is
empty, so they sail through and get recommended to a country that cannot take
them. Four of the ten appear in Glorp UI's hints, across five keys:
`peasants_yeomanry`, `jaysh_armies`, `ghazi_privilege`, `ayans_privilege`.

They are read out of `common/advances` rather than listed, so a patch that locks
an eleventh is picked up by a rebuild.

**A `customizable_localization` cannot be overridden.** The first definition read
wins and a later duplicate is dropped, saying so in the log:

```
gamedatabase.h:408  Duplicated key glorpui_svh_free_subjects_pv_peasants_yeomanry
                    will not be created from file: ...
```

So Glorp UI's own entry is untouchable. What is not untouchable is the
*localization key* that entry prints — and this mod is already rewriting every
one of them. A gated hint's key becomes
`[Player.Custom('svx_unlock_<key>')]`, its words move to `SVX_UNLOCK_<key>`, and
`in_game/common/customizable_localization/svx_unlock_gate.txt` decides between
them on `has_advance`.

### Four keys of Glorp UI's own interface

Not hints: `GLORP_UI_AVG_CONTROL`, `GLORP_UI_AVG_PROXIMITY`,
`SWAP_TO_AVG_CONTROL` and `REFRESH_AVG_PROX` are broken Russian grammar —
«Средняя значение», «Обновить Средняя расстояние» — and Glorp UI marks all four
`# LOCK`, so they are not going to be repaired upstream.

**Only Russian.** The other nine translations of those keys are grammatical, so
nothing overrides them and Glorp UI keeps ownership of its own text there. That
made the mod the first here to define a key in one language and not the rest, and
`tools/check_cmm.py` used to call that drift; it now reports uneven keys only
where nothing else defines them either, which is what a deliberate override looks
like.

## What it costs the interface

`python3 tools/guicost.py` prices it at **136 widgets in one file, no
`GetScriptedGui`, no always-live window, no loop** — the cheapest thing in the
tree. What it does spend is script calls while a societal value tooltip is up:
136 `visible` expressions, one per tooltip list, each running a script value.
Thirty-three of every thirty-four fail on their first line
(`scope:glorpui_sv = societal_value_type:X`) and cost nothing more. The axis that
matches then evaluates its body, which is up to 21 `Player.Custom` gates on the
worst direction. Glorp UI's own version already ran 34 of those `visible` calls;
this mod takes it to 136, of which 34 are the unfiltered block that is hidden
unless the switch is on.

That is worth keeping in mind against the open
[panel-hitch question](../../docs/investigations/panel_hitch.md), whose live hypothesis is hover:
this is a hover-built tooltip that runs script. It has never been measured.

## Where the game files come from

Rebuilding the added lines needs the directories named in
`tools/game_files_manifest.txt`. **They are all in `reference/` as of
2026-08-25**, and the scan they feed reports 1426 societal value pushes across
23 kinds of object — complete. The list, and where each one actually lives:

Twenty three directories under `in_game/common/` — laws, government reforms,
estate privileges, religious aspects and schools, estates, subject types,
chivalric orders, parliament issues and types, employment systems, cabinet
actions, international organizations, missions, advances and the rest — plus two
that are **not under `in_game/` at all**: `main_menu/common/static_modifiers`
(298 pushes, the whole scaling half) and
`main_menu/common/modifier_type_definitions`. That second pair is why the
manifest carries a real path per entry rather than assuming a mount.

`tools/extract_game_files.ps1` copies the list out of an EU5 install straight
into `reference/game/` — run it on the machine that has the game, then commit
what appears. `tools/extract_game_files.py` is the same thing where Python is
easier to reach. Both read `tools/game_files_manifest.txt`, so the list cannot
drift between them; both give a directory that is not where the manifest says
one search by name across the whole install before calling it missing; and both
sweep every `.txt` in the install for `monthly_towards_`, so a directory Paradox
renames comes along regardless.

## Автономность: чего не хватает

Владелец снимает Glorp UI с плейсета (2026-09-14). По числам мод дорогим не был
— [`../../docs/investigations/glorp_ui_cost.md`](../../docs/investigations/glorp_ui_cost.md)
— но нужны от него только подсказки и полоски в окне ценностей.

**Полоски сделаны и ничего чужого не требуют.** `tools/generate_values_window.py`
читает `reference/game/in_game/gui/societal_values_lateralview.gui`, вынимает
`template societal_values` и применяет четыре точных куска. Всё, что он зовёт —
`progressbar_bar_small`, `progress_bar_goldish`, `progress_bar_blue_alt`,
`SocietalValueItem.GetDirection` — игровое; `progress_bar_goldish` игра зовёт
сама в `map_markers.gui` и `production_lateralview.gui`. `lateralview`,
`select_menu_left` и `types Values` остаются игре: файл кладётся под своим
именем и переопределяет только шаблон, по порядку загрузки — ровно так же это
делал Glorp UI, и в игре это работало.

### Два режима, и почему переключателя нет

Владелец просил: «если glorpui есть — подключается к нему, если его нет —
редактирует это окно самостоятельно». **Подключиться нельзя, и это свойство
формата, а не лень.** Шаблон регистрируется в тот момент, когда движок читает
файл; спросить «а загружен ли другой мод» на этом этапе нечем, а `visible` и
`enabled` выбирают только из того, что этот же файл уже объявил. И с Glorp UI в
плейсете **побеждает наш файл** — тем же порядком загрузки, на котором держится
вклейка подсказок.

**Поэтому режимы сделаны неотличимыми, а не переключаемыми.**
`check_matches_glorp` на каждой сборке сравнивает наше окно с их
`glorpUI_societal_values_lateralview.gui`, выбросив комментарии и отступы, и
**совпадение сейчас точное**. Включён Glorp UI или нет — владелец видит одно и
то же окно. День, когда они тронут своё окно, сборка падает и называет первое
расхождение: решить, нужна ли их правка, и внести её в `HUNKS`. Другого симптома
у устаревшей копии чужого окна не бывает — это та же ловушка, что уже стоила
прогона на подсказках.

**Подсказки без Glorp UI теряют 827 строк.** Вклеенный дословно блок ссылается
на их `ScriptValue('glorpui_svh_visible_<ось>')` и на
`Player.Custom('glorpui_svh_*')`; и то и другое — их генерируемые файлы
(`common/script_values`, `common/customizable_localization`). Наш русский `.yml`
с их текстом у нас есть, но текст этот состоит из вызовов их `Custom()`.
Пропадает и ванильный блоб: он у них за переменной
`showUnavailableSocietalValueSuggestions`, которую без мода некому поставить.

**Первый шаг сделан 09-14, после прогона, на котором подсказка без Glorp UI
оказалась вовсе без главного списка.** Их блок остался дословным — трогать его
нельзя, на этом стоит `check_glorp_list_is_current`, — а ванильный список
выпускается ещё раз, своим, под теми же заголовками
`TO_MOVE_FURTHER_TO_LEFT/RIGHT` и с воротами
`Not(CMMSettingIsRegistered('glorpui__showUnavailableSocietalValueSuggestions'))`.

Ворота — не догадка: это булева настройка, которую Glorp UI регистрирует в CMM
(`glorpui_cmm_effects.txt`), а `CMMSettingIsRegistered` — общий макрос CMF по
ключу настройки, которым сама CMF спрашивает про `cmf_core__action_bar_position`.
Два условия одновременно истинными быть не могут: их строка требует их
переменной, которую ставит только их окно. До того как CMF отработает
регистрацию, ответ «не зарегистрирован» — и показывается ванильный список, то
есть ванильное же поведение.

**Но вид с Glorp UI этим не получается**, и разницу надо называть прямо: у них
главный список **отфильтрован** по тому, что держава может взять, а игровой
блоб — нет, и владелец про него сказал «совсем плохо» (08-30). Остаются два
пути:
1. **827 строк генерировать самим.** Всё, что для этого нужно, уже лежит:
   `scan_sources.py` находит все 1 426 толчков (`laws` 442, `government_reforms`
   235, `estate_privileges` 150); зачины `ESTATE_PRIVILEGE`,
   `GOVERNMENT_REFORM`, `POLICY` есть в `languages.py` на всех одиннадцати
   языках; у игры есть реестры `LAW`, `GOVERNMENT_REFORM`, `ESTATE_PRIVILEGE` и
   функции `ShowLawName`, `ShowGovernmentReformName`, `ShowPolicyName`,
   `ShowEstatePrivilegeName`. Закон в находке лежит объектом, политика — вторым
   элементом `path`. Заодно закрываются 89 пар из 429, которых не показывает
   никто. Сессия работы, и чужих файлов мод не везёт.
2. **Перенести их генерируемые файлы под наши имена.** Дёшево и механически, но
   это публикация чужого генерированного дерева и вечная сверка с их обновлением
   — та самая устаревающая копия, которая здесь уже стоила прогона.

И отдельно от кода: в `.metadata/metadata.json` стоит жёсткая зависимость
`glorp.ui`, а в имени мода — чужое название. Автономный мод обязан снять и то и
другое, а вещь опубликована, поэтому переименование — решение владельца.

## What is untested

Everything the 2026-08-27 rewrite touched is unrun. In the order a single
Russian game would settle it, cheapest first — **one tooltip answers the first
three**:

- **The category as a game concept.** The largest change and the one with the
  widest blast radius: if `[religious_aspect|e]` does not render inside a
  `TooltipScrolledStringPairList` label, 284 lines lose their opening word in
  *all eleven languages at once* and nothing errors. What to look for on any
  societal value tooltip: «**Религиозная особенность** Corona…» rather than
  «Аспект веры …», and «**Улучшение**» rather than «Достижение». If the words
  are missing entirely, the token does not render there and
  `catalog` in `languages.py` goes back to a literal noun per language.
- **The four repaired Glorp UI keys.** Map mode panel, the average control /
  average proximity controls: «Переключиться на режим «Средний контроль»» rather
  than «…«Средняя»», and «Обновить среднюю досягаемость» rather than «Обновить
  Средняя расстояние».
- **The advance gates.** Playing anyone who is not England, Morocco or the
  Ottomans, `Даровать привилегию Yeomanry` / `Jaysh Armies` / `Ghazi` /
  `Ayans` should not be offered at all. As the Ottomans before taking the
  `ghazi` advance, the same. `error.log` must not carry `svx_unlock_`.
- **The ten other languages have never been on screen by anyone.** They are
  written against the game's own terminology where a concept exists and are
  otherwise a careful translation of the Russian; nobody who speaks them has
  read them. A correction belongs in `tools/languages.py`, never in a generated
  `.yml`.
- **Whether the thumbnail is load-bearing.** Both mods this replaces shipped a
  512x512 `.metadata/thumbnail.png` on the belief that the launcher skips a mod
  without one, and both were listed. Every other mod in this repository ships
  none and is listed too. So one of the two is wrong and nobody has isolated
  which; the file is carried over because it costs 1.8 KB to keep, and because
  it is also the workshop page's picture, which is not optional.

Still unrun from before the rewrite:

- **The cabinet action and parliament issue gates.** What to look for:
  *Дикастерия по евангелизации* and *Влияние Строгановых* gone, and exactly one
  *Поддержка строительства …* line instead of four.
- **The religious aspect gate.** The organizations and missions gates are
  confirmed on screen; this one is not, because the owner plays Catholic, where
  aspects are set by the Papacy rather than chosen. It needs a run as a religion
  that picks its own — Lutheran, for instance. Until then the `country_religion`
  repair is reasoned, not seen.
