# Test log — the runs before the plan settled

Archived out of [`../TESTLOG.md`](../TESTLOG.md) so the live log stays the size
of a thing a session can afford to read. Nothing here is superseded; it is
simply finished. What these runs settled is in
[`../SETTLED.md`](../SETTLED.md), and this is the evidence behind it.

Ask for a run by name rather than reading the file:
`python3 tools/kb.py <words>`.

### 2026-08 — `nd_ru`, overriding a base mod's localization

**Loaded:** National Destinies, then `nd_ru` below it in the playset.
**Expected:** the Russian keys of `nd_ru` to replace National Destinies' own,
which are English text under an `l_russian:` header.
**Observed:** they did. Westphalia reads in Russian end to end.
**Verdict:** the whole approach of the mod rests on this and it holds. Load order
decides; `nd_ru` must sit after the base mod.

### 2026-08 — `goods_target`, every good and a target each, with logs

**Loaded:** game 1.3.11, the player's normal playset. Logs supplied.
**Expected:** monthly checks counted in the settings tooltip, a target per row,
readings updating monthly.
**Observed, in four parts:**

1. **Monthly checks: 0.** The pulse leaves no trace at all. The display path is
   not the suspect — Construction Manager reads `var:` inside script values the
   same way this does.
2. **The Target column shows a raw key**, `bgt__construction__t…`.
3. **The readings do not change from month to month.**
4. **The game visibly loses ticks while the Mod Menu is open** — obvious with
   the game unpaused, opening and closing the menu.

**The logs say nothing about this mod.** Zero lines in `error.log`, its five
rotations, `gui.log` or `game.log`; `debug.log` shows only that it mounted and
that its `1.3.*` matched game 1.3.11. So none of the four is an error the engine
noticed — all four are the silent kind.

**Diagnosed from the logs and the reference tree, not guessed:**

- The raw key is the **format keys**. `cmm_set_list_field_conditional_format`
  makes the widget read `<mod>__<setting>__<field>_prefix` and `_postfix`, and
  the `_high` / `_low` pair for the sign. CMF detects their existence by
  comparing `Localize(key)` against the key itself, so a missing one renders as
  its own name and logs nothing. `cm__auto_build_list__min_discount_*` is the
  worked example.
- The performance and the frozen readings are the same cause: each of the 74
  row labels calls `ScriptValue('bgt_impact_<good>')`, and each of those does
  four market and default price lookups. That is evaluated for every drawn row,
  every frame. The version before this one had no reading in its rows and cost
  nothing noticeable; the tooltip with five of them was also fine.

**Not resolved:** why the monthly pulse never runs. `monthly_country_pulse`
exists in the game's own dump, CMF chains it through `_cmf_on_monthly` into
`cmf_monthly_human_country_pulse`, and this mod's *registration* leaf on
`cmf_on_mod_registration` demonstrably works — so on_action merging from this
mod's file works at least once.

### 2026-08 — `goods_target`, the goods list

**Expected:** a 28-row list with two ticks per row, and a monthly log line
naming what is ticked.
**Observed:** the list draws, the rows name their goods, a row can be selected
and the game's own goods tooltip comes up on hover. Ticks can be set. **The log
shows nothing new** — no monthly entries at all.
**Verdict:** the list half works, including the `_on_changed` callback without
which nothing would draw. Whether a tick reaches script is still unknown,
because the only thing that would have said so was the log.
**Two suspects, both removed rather than diagnosed:** the monthly effect was
gated on `variable_map(cmm|flag:bgt__log_readings)`, and asking a variable map
for a key it does not hold is an error rather than false — a setting left at its
registered default may never have been written to the map. And the count was
logged with `cmf_log_value = { value = var:... }`, a CMF macro taking `var:` in
an argument, which is the shape that kills a CMM list on `item = var:x`.
**Learnt:** the mod now counts into country variables that a script value reads
back into the tooltip, so the next answer does not depend on the log at all.
**Also asked for:** every good rather than the 28 construction ones (cannons
were missing), and a target per good rather than one for all.

### 2026-08 — `goods_target`, first load: do the readings match

**Loaded:** the player's normal playset with `goods_target` added.
**Expected:** a Mod Menu tab with two settings, and readings that agree with the
game's own construction cost tooltip.
**Observed:** both. The tab renders in Russian, and the tooltip of "Писать замеры
в журнал" showed lumber -14.7%, masonry +22.1%, glass -33.0%, sand -18.7%,
stone +1.1%. The player confirms the discount matched the game at the start of
the run.
**Verdict:** the measurement the whole mod rests on is right. Registration, the
`capital.market.market_price` reading, the per-good script values and
`GuiScope...ScriptValue` in a CMM tooltip all work.
**Learnt:** the readings move every month, so a yearly log line is the wrong
cadence — the probe moved to CMF's monthly pulse, which is also where
Construction Manager's own dispatcher runs.

### 2026-08 — logs from a live playset, checked for our own mods

**Loaded:** the player's normal playset — CMF, Construction Manager, Glorp UI,
National Destinies, our mods — while dumping `script_docs`.
**Observed:** `error.log` carries no line mentioning `bag_rgo`, `eu5ab`, `nd_`
or any `_ru_generated_` file. Its 164 repeated script errors come from another
Russian localization mod (`common/customizable_localization/ru_EUN_custom_loc.txt`,
"Event target link 'location_rank' returned an invalid object"), and `gui.log`
only notes CMF and Glorp overriding vanilla types, which is what they are for.
**Verdict:** nothing of ours errors at load or in play.

### 2026-08 — `auto_build_ru`, does the game pick the file up

**Loaded:** Advanced Auto Build with `auto_build_ru`.
**Expected:** the mod's Mod Menu tab in Russian instead of raw keys.
**Observed:** works as intended — reported by the player.
**Verdict:** the mod is done. Adding keys for a language a base mod does not ship
needs no dependency on it and no load-order care.
**Since:** the base mod moved to 0.9.2 Beta, bringing 40 new keys. Those are
translated but have not been on screen.

### 2026-08 — `rgo_bonus_filter`, buildings panel chip

**Expected:** a filter chip in the funnel menu of a location's buildings panel,
leaving only buildings that gain efficiency from raw materials in the province.
**Observed:** works. Lightly tested — not walked across many provinces.
**Still unrun:** the second chip, in the build panel
(`BuildInLocationLateralView`).

### 2026-08 — `where_to_produce`, the good-first build

**Expected:** for a chosen good, a ranked list of provinces.
**Observed:** correct on screen — `Рудные горы / Оружейные заводы / 1.88% /
4.075` read true against the game's own tooltip.
**Note:** this build was then replaced by a province-first one that was never
run, and the mod was removed. See
[`HANDOFF.md`](../HANDOFF.md#why-where_to_produce-failed).

### 2026-08-24 — logs from a live game, EU5 1.3.11

The player sent a full `logs/` after a short session: main menu at 22:02, game
from 22:05:17 to 22:08:32, Sweden, the playset below. Nothing was being tested;
the question was where the errors come from and why the game slows down the
longer it runs. Both were answered from the files, so this is the most useful
run in this log so far.

**Loaded:** Community Mod Framework, Autonomous Diplomats, Construction Manager,
Goods Target, Glorp UI + two local `glorpui_*` addons, Quality of Life by Buddy,
Integration Hotfix, Please Buy My Terrible Art, National Destinies + Nation
Destinies Rus + `nd_ru`, OGAS Optimized, `auto_build_ru`, `rgo_bonus_filter`,
`sheep_farm_food`. Game in Russian.

**Observed — errors.** 39 289 lines across `error.log` and its five rotations.

| source | lines |
| --- | --- |
| the game's own Russian localization | 34 700 (88%) |
| `ForeignCountryView` with no context, vanilla GUI | 1 497 |
| `location_rank` in `common/customizable_localization/ru_EU5_custom_loc.txt` | 484 |
| everything else | ~2 600 |

**31 350 of those were written in the single second 22:05:49**, all from five
search-filter strings, and they rotated `error.log` five times over. Every error
the game produced before that second is gone. That alone is a reason to fix
them: the log is unusable for anything else while they are there.

`game.log` carries 804 more the error log never sees — `Object of type
'country' is not valid for 'longname_ru_GEN'` (576), `'CL_tt'` (152), `'CL_ACC'`
(76) — all from the same custom localization file.

**Observed — the slowdown.** `performance_degradation.log` samples every 3 600
rendered frames, and the two in-game intervals are unambiguous:

| | frames | GUI widgets | memory |
| --- | --- | --- | --- |
| after load | — | 37 768 | 12 675 MB |
| +1 sample | 3 601 | 64 318 (+26 550) | 12 977 MB (+301) |
| +1 sample | 3 601 | 98 195 (+33 877) | 13 214 MB (+237) |

Seven to nine GUI widgets and roughly 280 MB per minute, steadily, while the
frame time itself stays flat at 14–15 ms. So the degradation the player
describes is not the renderer giving up: it is the process growing until the
machine runs out of memory. It starts at 12.4 GB and gains ~280 MB a minute, and
the machine had 20.5 GB free at launch — about an hour and a quarter to
swapping. Reloading the save frees it, which is exactly what the player reports.

**Verdict:** the errors are the game's, not the mods'; `ru_loc_fix` is the
answer to 88% of them. The leak is a separate fault, is real, is measurable
with the game's own counter, and is **not** attributed to anything yet — see
[HANDOFF](../HANDOFF.md#the-memory-leak) for the next step, which is two short
runs and one number.

### 2026-08-24 (evening) — `ru_loc_fix` in game, an hour of play

**The first thing this repository has fixed that the log can confirm.**

**Loaded:** the same playset as the morning run, with `ru_loc_fix` added at the
top. No time-acceleration mod this time; the player notes the game degrades
without it too, and that the mod exists to paper over exactly this.

**Expected:** no `FetchData failed for 'AddTextIf(EqualTo_string(` from the five
search-filter strings, and no burst at load.
**Observed:** zero. Not one `CUSTOM_SEARCH_FILTER` line anywhere in
`error.log`, `gui.log` or `game.log`. The 31 350-lines-in-one-second burst is
gone and `error.log` no longer rotates itself out of existence at startup.
**Rate:** 39 289 errors in three minutes became 35 455 in an hour — about twenty
times fewer per minute.

**And the log became readable, which was the other half of the point.** Three
keys nobody could see before now stand at the top, all with the same fault the
filters had: `RGO_BUILD_GOODS_PRICE_IMPACT_ON_COST` 13 950 lines,
`FILTER_BY_GOODS` 3 866, `MARKET_SURPLYS_INFO` 1 650. So the fault was never
about filter strings; it is about reaching a Russian case through
`$GOODS_..._RU_*$` from a panel where the reference loses the scope. Round two
fixes those and eight more.

**One thing the run settled that no amount of reading could.** `gui.log` still
lists seventeen `Failed parsing localized text` lines for keys this mod repairs
— and they are all stamped 23:12:33, sixteen seconds *before* the mod's
localization is merged at 23:12:49. They are the frontend pass parsing vanilla's
value. None of the seventeen appears again anywhere in the run. So a
`Failed parsing localized text` at frontend load is not evidence of anything
being broken in game.

**Verdict:** the approach works and the tooling around it works. What it cannot
do is tell in advance *which* of the ninety-odd keys that reference a declension
helper will fail; only a run says that, which is what `fixes/observed.txt` is for.

**Still not checked by eye:** whether the repaired sentences read correctly on
screen. The log says they no longer fail; it does not say the Russian is right.
The quickest look is a religion tooltip (harmony, purity, honor) and the goods
filter chips in a location's buildings panel.

### 2026-08-25 — the widget experiment, five blocks on one save

The protocol from [`HANDOFF.md`](../HANDOFF.md#the-slowdown), run by the player on a
loaded 1362 save: paused throughout except the last block, two minutes per
activity, a short unpaused skip between blocks so the in-game date separates
them in the log. One sampler row is 3 601 frames, about fifty seconds here.

Only intervals *inside* one block are counted; a row whose date differs from the
row before it spans the skip as well and is thrown out.

| block | what was done | widgets | per frame |
| --- | --- | --- | --- |
| 1 | paused, hands off | **+0, +0, +0** | **0.00** |
| 2 | clicking countries, opening diplomacy | +20 099 | +1.86 |
| 3 | clicking locations, opening the build panel | +3 178 | +0.29 |
| 4 | cycling map modes | +32 254 | +1.49 |
| 5 | speed 7, panning the map, dismissing events | +27 566 in one row | — |

**Three findings, and the first two are settled.**

**Idle costs nothing at all.** Not "little" — three consecutive rows of exactly
+0 across 10 800 frames. Every widget this game accumulates is created by
something the player did. (The first row of block 1 adds 9 624; that is the
interface finishing its build after the save loaded, not idling.)

**Widgets *are* released — but only on teardown.** Quitting the 1337 game at the
start of the run took the count from 38 281 to 2 618 to 367 in two rows. Nothing
comparable happens during play: the largest fall inside the session is −557.

**It is not one window.** That was the hypothesis and it is wrong. Diplomacy
panels and map modes leak at comparable rates — 1.86 and 1.49 widgets a frame,
ten to seventeen thousand per fifty seconds of clicking — and the location panel
leaks too, six times slower but never zero. Whatever is failing to release is
shared by most of the interface, so bisecting panels further is a dead end.

**A caveat about frame time, and it matters.** This run stayed at 14 ms
throughout, at 175 000 widgets, where the hour-long run was at 17–21 ms with the
same count. The difference is that this run was paused for all but the last
block, and a paused game does no simulation. So this run says nothing about the
frame-time cost of widgets; it was designed to measure accumulation and that is
all it measured.

**What it rules out for this repository:** `rgo_bonus_filter` adds to the
location panel, and the location panel is the *lightest* of the three. Nothing
of ours is implicated.

**Next:** the remaining axis is mods against vanilla, and one run settles it —
see [`HANDOFF.md`](../HANDOFF.md#the-slowdown).

### 2026-08-25 — vanilla against the full playset, and the case closes

The run before this one left one question: is the widget leak the mod set or the
base game. This run answers it, and the answer is the base game.

**What the file shows happened.** One process, two games. The first is the full
playset — 37 768 widgets at 1337_04_01, 449 Gfx units, 843 trade wagons, the same
three numbers to the unit as every modded run in this log. Then a return to the
main menu, the playset changed, and a second new game: 36 977 widgets, 448 Gfx
units, **713** trade wagons. A genuinely different and lighter data set, so the
mods really did come off. (EU5 reloads a playset in place; the process never
restarted.)

**The same activity, both sides:**

| | idle, paused | clicking countries and opening diplomacy |
| --- | --- | --- |
| full playset (1362 save) | +0 | +20 099 over 10 803 frames = **+1.86/frame** |
| mods off (1337 start) | +0 | +21 472 over 10 803 frames = **+1.99/frame** |

**Vanilla leaks at the same rate — slightly faster, if anything.** The two sides
are not perfectly matched (a 1362 save knows more countries than a 1337 start),
but the magnitudes are identical and the idle baseline is exactly zero in both.
Nothing in the playset causes this, and nothing in this repository can fix it.

**Confirmed again, twice in one file: the main menu releases everything.**
Leaving a game took widgets from 37 768 to 2 618 to 364 — the same 364 the
process starts with — and memory from 12 952 MB to 9 951 MB, which is what it
was before any game was loaded. So quitting to the main menu and loading the save
again is worth exactly as much as restarting the executable, and costs a
fraction of the time.

**Verdict:** a base-game defect, measured and quantified. The measurement is
finished — but the investigation is *not*, and the owner said so plainly when
this entry first ended with "so file a bug report". They already knew it was
vanilla. What is wanted is a lever from the mod side, or evidence that there is
none. The lead and the next run are in
[`HANDOFF.md`](../HANDOFF.md#the-slowdown--it-is-the-base-game-and-the-hunt-is-for-a-lever).

### 2026-08-25 — `glorpui_hints`, the merge, and a key on screen

**Loaded:** the merged `glorpui_hints` in place of `glorpui_ru_svh_fix` and
`glorpui_svh_extra`.
**Expected:** the societal value tooltip to read in Russian and to carry the
added block.
**Observed:** it does. Screenshot of *Оборона*: Glorp UI's own list in Russian
("Принять реформу правления Система гарнизонов +0.05"), and under it «Также
влияет на смещение» with the four parliament issues about building forts and
«Обороняющаяся сторона в войне +0.10», scrolled. The owner's words: "в целом всё
работает как и раньше".
**Verdict:** **the merge is confirmed.** Two mods in one folder under one id load
and behave as the two did. Nothing in `glorpui_hints` is outstanding.

**And the screenshot showed something else — three raw keys, none of them ours.**
The tooltip read «Дальше продвинуться в сторону
*SOCIEALVALUE_RIGHTITEM_WNTT_GEN*:», «При своём максимальном значении
*SOCIEALVALUE_NAME_GEN* будет оказывать…» and «Поддержать *SOCIEALVALUE_VALUE_ACC*
с помощью действий совета». That is the game's own Russian localization: it
defines seven declension helpers spelled `SOCIETALVALUE_*` and references all
seven as `SOCIEALVALUE_*` — a missing T — in twenty four keys. No overlap, so
every reference resolves to nothing.

`$NAME$` naming nothing neither errors nor logs: the engine prints the name in
capitals and carries on. So this class was invisible to every rule
`ru_loc_fix` had, and it took a screenshot to find one. It has a rule now
(`missing_ref`), and finding it turned up **49 keys in thirteen references**,
which `ru_loc_fix` repairs 45 of. Unfixed and reported: four culture tooltips
whose nearest defined key belongs to a different people.

**Riding on the same rule: `locscan.py` could not see 18 012 keys** — 3.4% of
the tree — because its key regex rejected a line with a comment after the
closing quote. `hre_tt: "0" #True` read as undefined, so every reference to it
looked broken. Fixed; every other rule's count is unchanged, which is how we
know the fix did not disturb them.

**Untested:** all 45 repairs. Any run checks them — the three keys above are on
the societal value tooltip, which is one hover away.

### 2026-08-25 — `ru_loc_fix` round three, and the game files arrived

**Loaded:** the playset with `ru_loc_fix` at 207 keys.
**Expected:** the three raw keys on the societal value tooltip to become words.
**Observed:** they did. The owner: "проверил, что ценности теперь отображаются
правильно".
**Verdict:** **round three confirmed.** `$SOCIEALVALUE_*$` was the fault and the
rewrite to `$SOCIETALVALUE_*$` is the repair, on screen. That also settles the
class: a `$NAME$` naming no key really does print the name, and repairing the
reference really does fix it — which is what makes the other 21 repairs
(`protestant_union.tt`, `catholic_league.tt`, `pirate_events.2.a`) worth
believing without seeing each one.

**And the game files came in**, by `tools/extract_game_files.ps1` on the owner's
Windows box — 597 files, `in_game/common/` up from seven directories to
thirty one. The PowerShell script had never been run when it was written; it
works.

**What the extraction missed, and it matters:** `static_modifiers` — 298 of the
1405 societal value pushes, and the whole "scaling" half of `glorpui_hints`
(fort maintenance, army size, at war, defender in war). The scan of what did
arrive finds **1128 pushes across 22 source types**; the missing 298 are all
that folder. It is not under `in_game/` at all, and the first sweep only looked
there. Both scripts now search the whole install for a manifest directory that
is not where it says, and sweep every `.txt` in the install rather than one
mount — so re-running brings it. `modifier_type_definitions` is missing for the
same reason.

**Still untested:** nothing about `glorpui_hints` changed in this round, so its
extra hint lists are still the ones built before any of this. Rebuilding them
against the arrived files is the next thing, and it needs `static_modifiers`
first.

### 2026-08-25 — culture tooltips, and a theory that did not survive them

**Loaded:** the playset, after the game files went into `reference/`.
**Expected:** to find out whether the Russian culture tooltips resolve, since
every `*_culture_tt` key in the game's Russian custom localization holds a bare
number equal to its own line number minus two — 1755 of them, no exceptions.
**Observed:** they resolve, completely. Screenshot of a location's culture list:
*Вестфальск* opens a full culture tooltip (traditions 179.00, cultural influence
71.63, language, culture groups, the eight countries it is primary for),
*Германск* opens the culture group, *Нижнефранконск* the same. The owner: "вроде
они работают как надо и раньше работали так же".
**Verdict:** **the theory was wrong and this is closed.** The key on screen is
`westphalian_cadj`, which is literally
`#TOOLTIP:CULTURE,$westphalian_tt$, #L Вестфальск#!#!`, and `westphalian_tt`
holds `"1052"` on line 1054 — so the number is exactly what the engine wants
there, or it ignores the argument. Repairing 1755 keys would have fixed nothing
and broken whatever it touched. `PITFALLS.md` carries the lesson: a pattern in
the data explains a fault, it does not establish one.

**And the rest of the game files arrived**, `static_modifiers` among them — not
under `in_game/` but under `main_menu/common/`, found by the by-name search the
last round added. The manifest now names the real paths. The source scan is
complete for the first time: **1426 pushes across 23 source types**, up from
1128.

**So `glorpui_hints` was rebuilt from real game files** — the first time that
has been possible in this repository rather than on the owner's machine. 243
hint lines became **264**, 107 gated became **138**, and nothing was lost. The
twelve new ones are five Italian and foreign leagues the game has added since
the lists were last built, plus two placements of *Обороняющаяся сторона в войне*
and *Парламент в столице*. Defensive goes from 9 lines to 15.

**Untested:** the rebuilt lists. The visible change is the defensive axis
growing by six lines and new international organizations appearing; one hover
over a societal value shows it.

### 2026-08-25 — the rebuilt hint lists

**Loaded:** `glorpui_hints` with the lists rebuilt from the game files now in
`reference/`.
**Expected:** more lines per direction, and no raw keys from the 21 new gated
entries.
**Observed:** "всякого в списках действительно больше. Каких-то глючных ключей и
т.п. не вижу. Всё работает ок."
**Verdict:** **the rebuild is confirmed.** 264 hint lines and 138 gates render
correctly, which also confirms the pipeline end to end for the first time inside
this repository: game files in `reference/` → scan → generator → mod → screen.

**English is out of scope by the owner's decision**, unless the mod is ever
published: "английским языком заниматься не планирую, по крайней мере пока не
появится желание выложить этот мод в общий доступ." The gap stays recorded in
the mod's README; it is not work.

### 2026-08-25 — the availability gates, first round

**Loaded:** `glorpui_hints` with the four new gate kinds, on the owner's own
save (a Catholic German county).
**Expected:** organizations he cannot join and missions in a missions-off game
to disappear; religious aspect lines to start appearing.
**Observed:** "итальянские лиги пропали, миссии тоже". Both confirmed.
**Verdict:** `can_join_international_organization` and
`game_has_missions_enabled` both work as gates in a country scoped
customizable localization. That is the mechanism proven, not just these two
categories.

**Religious aspects: still unknown, and not his fault.** He plays Catholic,
where aspects are set by the Papacy rather than chosen, so the repaired
`religion = religion:X` gate has nothing to show him either way. It needs a run
as a religion that picks its own aspects — Lutheran was his example. Until then
the `country_religion` repair is reasoned, not seen.

**Two things still not filtered, both reported from the screen:**

- **Cabinet actions.** *Дикастерия по евангелизации* and *Влияние Строгановых*
  were on screen for a Catholic German county. They are `office_of_new_converts`
  (`potential` wants a modifier on Kazan) and `stroganov_influences` (`potential`
  wants the Stroganov variable) — national, and both carry a `potential` block
  this mod was not reading. All eight cabinet actions that push have one.
- **Parliament issues.** All four *Поддержка строительства …* lines showed at
  once when only one can ever be valid: `promote_castle_building` requires
  `has_advance = castle_advance` and forbids the better advances, and the other
  three do the same one rung up. The gate was `has_parliament = yes` and nothing
  else.

Both are fixed in the same session: cabinet actions take `potential` + `allow`
verbatim, parliament issues take `has_parliament = yes` plus the estate that
raises the issue plus `potential` + `allow`. Gated lines 167 → **175**.

**A bonus the verbatim copy brings:** two parliament issues carry
`potential = { always = no }` with a comment saying they are event-driven.
Copying `potential` drops them, which is right.

**Untested:** the cabinet action and parliament issue gates. What to look for —
*Дикастерия по евангелизации* and *Влияние Строгановых* gone, and exactly one
*Поддержка строительства …* line instead of four.

**The mod menu switch and the scaling hovers, both unrun.** Two mechanisms
landed together and they fail differently, which is how to tell them apart:

- **The switch.** `Подсказки общественных ценностей → Списки → Фильтрация →
  Показывать всё без фильтра`, in CMF's mod menu. If the row is not there at
  all, registration did not run. If the row is there and the tooltip does not
  change, the `.gui` condition is wrong. Nothing else in the mod moves either
  way.
- **The hovers.** «(масштабируется)» and «(условие)» on the 41 scaled and
  conditional lines. These are game concepts this mod defines. If they work, the
  hover says what the modifier scales with and at what value it is at full size
  — 100 army tradition, 200% of the fort limit, `army_size_percentage > 1.0` for
  the expected-army one. If a text-only concept is not a thing, those 41 words
  render bare or as `ERROR:` and nothing else is affected.

### 2026-08-25 — the switch works, the two clever bits did not

**Loaded:** `glorpui_hints` with the mod menu switch and the scaling hovers.
**Expected:** a switch that restores the unfiltered pool, and a hover on
«(масштабируется)» saying what the modifier scales with.
**Observed:** **the switch works** — "переключатель есть и свою функцию он
выполняет". The hovers do not, and they took text with them: on
*Децентрализация* the *Парламент вне столицы* line rendered as a bare `+0.20`
with no words at all, and on *Традиционализм* the *Доля крестьян в населении*
line as a bare `до +0.10`. In the same list *Банкрот* and *Сословие Племена*
rendered correctly.
**Verdict:** two separate faults, both in the same commit, both silent.

1. **A label that is nothing but a `$reference$` has no floor.** The labels had
   been changed to the game's own `$STATIC_MODIFIER_NAME_x$` so a rename would
   be followed for free. All three keys exist in the game's Russian files;
   `is_bankrupt` rendered and `parliament_outside_capital` and
   `peasants_percentage_in_country` rendered as nothing. What separates them is
   **still unknown** — and the fix does not depend on knowing, because a label
   made only of a reference loses the whole line when the reference fails.
2. **A mod-defined game concept with no `texture` renders as nothing.** The
   hovers were `[Concept('svx_scale_x','(масштабируется)')|e]` with the concepts
   declared in the mod's own `game_concepts/`. The whole data block produced
   empty output — visible on *Банкрот*, which kept its label and its value and
   lost the word between them. Glorp UI's own concepts all carry a `texture`.

**Both are backed out.** Labels are this mod's own strings again, and the
explanation is inline in the same line, which cannot fail:
«Превышен лимит крепостей *(масштабируется: максимум при
used_fort_limit_percentage = 200%)*: +0.10» and «Армия больше ожидаемой *(при
army_size_percentage > 1.0)*: +0.10». Where the game's files say nothing — every
`static_modifier`, *Средняя грамотность* among them — it reads
*(масштабируется, показан максимум)* and claims nothing more. A trigger that
only repeats its own label gets no bracket at all.

**And the checker that would have caught the first one is in.** Every hint label
must carry literal text of its own; a label made only of markup and references
fails the run. Its first version silently passed the very line it was written
for — a non-greedy match started at an earlier `@hint!` and swallowed the whole
entry before it — so it is verified in both directions now: clean on the real
file, and failing on a planted reference-only label.

**Untested:** the inline notes. Everything they replace was rendering before the
change, so the risk is the wording rather than the mechanism.

### 2026-08-25 — the inline scaling notes, rejected on sight

**Loaded:** `glorpui_hints` with the explanation inline in each hint line.
**Observed:** it does not fit. The screenshots show the *labels* truncated —
*Традиции армии* as «Традиции армии ( …», *Во время войны* as «Во вр …», *Доля
крестьян в населении* as «Доля …» — with the bracket spilling across the value
column. And where a modifier declares nothing, "(масштабируется, показан
максимум)" says what «до +0.10» already said. The owner: "чёт супер гига пупер
фу… просто пара бесполезных слов".
**Verdict:** **reverted.** The hint text is byte-identical to the 2026-08-25
version he approved; only the switch's keys are new on top of it. The left half
of a `TooltipScrolledStringPairList` row is narrow and truncates rather than
wraps — in [`PITFALLS.md`](../PITFALLS.md#interface) now.

The arithmetic behind the notes was correct and is kept in
[`research/engine.md`](../research/engine.md): `auto_modifiers` declare
`scales_with` and `potential_trigger`, `static_modifiers` declare neither. It is
recorded rather than used, so a later session does not derive it a third time.

**One correction from the owner, not acted on at his request.** He believes
"expected army" is set by the estates — what they expect the country to field.
The file says only `army_size_percentage > 1.0`, which is a ratio against
something the modifier does not name, so both can be true and the file does not
settle it. Nothing in the mod depends on this any more.

### 2026-08-27 — a logs drop, and the error nobody would have seen

**Not a designed run.** The player was asked to look at the eleven-language
rebuild, said it "looks the same as before", and sent the whole `logs/` folder
instead. It answered three things anyway, one of them a real bug.

**What was loaded.** The 2026-08-25 build of `glorpui_hints`, out of
`Documents/.../mod/glorpui_hints` — **not** the 2026-08-27 rebuild, which had
not been installed. So "looks the same as before" is not evidence about the
rewrite, and the axis he was looking at (*Миролюбие*) could not have shown a
difference in any case: its extra block is two conditional lines,
«В мирное время» and «Крепостей меньше половины лимита», and those words are
identical in both builds. The catalogue lines are the ones that changed.

Also loaded: `3784988919` (`Glorp UI small fix`), the rival addon, alongside
ours. The screenshot shows **our** phrasing — «Даровать привилегию Религиозные
дипломаты», «Принять реформу правления Дипломатические традиции» — where his
says «Предоставить …» and «Добавить … ([government_reform|e])». So on this
playset ours wins the shared keys. Worth knowing and worth not relying on: the
mount lines interleave the two across several passes and the order is not
obviously ours to control.

| | |
| --- | --- |
| **`Missing loc key 'GLORP_UI_SVH_*'`** | **0.** Was 725 per load before this mod existed. The translation half does its whole job. |
| **`ru_loc_fix` round two** | **confirmed.** All six keys it was to repair — `RGO_BUILD_GOODS_PRICE_IMPACT_ON_COST`, `FILTER_BY_GOODS`, `MARKET_SURPLYS_INFO`, `ALERT_HAS_UNMARRIED_CHILDREN`, `THIRD_DESTROY_BUILDING_EFFECT`, `DESTROY_BUILDING_EFFECT` — appear **0 times** in `error.log`. Round one was already confirmed; round two now is. |
| **`glorpui_hints` gates** | **one broken gate, found only because the logs came.** |

**The bug.** One line, once, in `error.log`:

```
[jomini_trigger.cpp:803]: is_core_of: Inconsistent trigger scopes (country vs.
location) at common/customizable_localization/svx_extra_hint_loc.txt:3073
```

`svx_n_sinicized_004` is the Confucian Academy, and its gate is that building's
own `allow` block copied verbatim. **A building's `allow` is evaluated on the
location being built in**, not on the country — `is_core_of = owner`,
`owner = { ... }`, `region`, `market`, `has_building`, `dominant_culture` — and
all 179 of them were being pasted into a `type = country` customizable
localization. `is_core_of` is simply the one strict enough to say so.

On screen this shows as nothing at all: the gate does not answer, so the hint
either never appears or always does, and no player would ever connect the two.

**The repair is the exact question rather than a workaround.** Every building
push here is a `capital_country_modifier` — the building has to be *in the
capital* — so the block belongs in the capital's scope:
`exists = capital capital = { ... }`. `capital` is a country → location event
target (`python3 tools/api.py capital`) and the game writes `exists = capital`
in front of it 76 times in its own `common/`.

**And the rule went into the checker.** `check_gate_scopes` in
`mods/glorpui_hints/tools/generate.py` reads **Supported Scopes** out of the
engine's own trigger dump (`reference/game/docs/triggers.log`) and reports
any trigger called in country scope
that the engine does not allow there. It follows only the outer scope — a nested
`capital = { ... }` is a different scope and is left alone, which is precisely
what the repair is. Checked both ways: it catches the old line and passes the
new one.

**Still unrun, and unchanged by this:** everything the 2026-08-27 rebuild added.
The cheapest single check is now known — turn the mod menu switch
«Показывать всё без фильтра» on and hover **Децентрализация**: the subject type
lines should read «**Тип ленника** …» where the old build said «Тип вассала».

### 2026-08-27 — the concept tokens render, and in two languages

**The change with the widest blast radius is confirmed.** Screenshots of the
*Decentralization* tooltip with the mod menu switch «Показывать всё без фильтра»
on, in Russian and then in English — the player switches language from the
console on the fly, which turns out to make testing the other ten languages
almost free.

| expected | observed |
| --- | --- |
| the catalogue lines open with the game's own word for the category, from `[religious_aspect\|e]` and friends | **yes.** «**Религиозная особенность** Двенадцать представителей», «**Тип ленника** Феод / Пронии / Удж-бей / Вассал» — where the 2026-08-25 build said «Аспект веры» and «Тип вассала» |
| the concept renders as an encyclopedia link, not plain text | **yes** — the category word is coloured and hoverable, the object name beside it is not |
| English exists at all | **yes.** "Religious Aspect The Twelve Emissaries", "Subject Type Fiefdom". The old build shipped no English `SVX_*` keys, so this block would have been raw keys |
| the English openers are Glorp UI's own | **yes** — "Enact the Traditional Distribution Policy" |
| the unfiltered block replaces the two filtered ones | **yes**, and the block titles translate: «Влияет на смещение (без фильтра)» / "Pushes towards this (unfiltered)" |

So `catalog` in `languages.py` stays a concept token, and the seven Russian
terms it corrected are the game's own words on screen. **That was the one change
that could have gone badly, and it did not.**

**One thing the hot language switch does not do:** the vanilla block title
«Дальше продвинуться в сторону децентрализации:» stayed Russian in the English
screenshot while everything this mod owns switched. Not our key and not our bug
— but it means a language switched from the console is not a clean test of
*vanilla* strings, only of ours. A real check of another language wants a
restart.

**Still unconfirmed:** the five advance-gated privileges, the building `allow`
repair from earlier today, and nine of the eleven languages.

### 2026-08-27 — the upload button exists, and it is hidden

Two screenshots, an hour apart, and the second corrected the first.

**First read, wrong:** the launcher's «Модификации и дополнения» shows playsets,
order and checkboxes and nothing about publishing, so EU5 was written up as
having no first-party upload.

**It has one.** The player found it: the same screen, the row **«Выбранные
модификации: N/M»**, a small **sandbox icon** in that row next to the gear. It
opens **Mod Tools**, with tabs *Create mod* and *Uploaded mods*, the whole of
`metadata.json` as a form — Name, ID, Path, Version, Supported game version,
Description, and the tag list as checkboxes — and a button reading **Upload New
Mod**.

It is documented, in one sentence, in the middle of a dev diary about writing
events and situations:
[Tinto Talks 85, Modding](https://forum.paradoxplaza.com/forum/developer-diary/tinto-talks-85-22nd-of-october-modding.1864004/)
— *"navigate into the Mods & DLCs Menu in the top right corner and then open the
Mod Tools view by clicking on the sandbox icon next to Selected Mods"*. That
diary is otherwise entirely about authoring; publishing is that clause and the
button in a screenshot. The wiki does not mention it at all, which is why it
documents the third-party uploader instead — and why an hour went on finding a
button that was on screen the whole time.

**So the route is the game's own**, and the tag checkboxes in that form are the
authoritative tag vocabulary — the same one four mods here were outside of.
[PDX Workshop Manager](https://github.com/kaiser-chris/pdx-workshop-manager)
stays as the fallback; `mods.bat → 5 → «к»` still writes its config.

Also confirmed from the same screenshot: the load order the player actually
runs puts `Glorp UI` at 3 and `Glorp UI - Societal Value Hints` at 4, directly
after it, which is what the declared dependency is for.

## `where_to_produce`, the first seven loads

Moved out of the live log when it outgrew its budget; the fourth and fifth
runs are still there.

**2026-08-30 — `where_to_produce`, third load. The map mode works; the design of
the picker did not.** Five screenshots.

- **The map mode paints**, and it is the thing the owner wanted: Wallachia green
  as chosen, the ticked Carpathians dark as the zone. Its name showed as
  `mapmode_bag_wtp_selection_name` — a map mode's name key is
  `mapmode_<key>_name`, not `<key>`.
- **The target picker opens and works, and closes after each pick.** That is the
  generic action's lifecycle; `fire_generic_action` fires with a supplied target
  rather than reopening the panel, so there is no script-side way to keep it up.
  Area granularity is the mitigation.
- **Asking the player for the production method was wrong.** Owner's words: the
  mod is meant to find the best method for his ground, and asking him to guess it
  first "полностью ломает конечную суть мода". Rebuilt: the good is the only
  question, every method for it is scored per location, and the row names the
  building that won.
- **Six region groups were a bad frame.** Replaced by five continents, which also
  removed the zone walk entirely — a location's continent is a plain trigger.
- **The window listed nothing when no region was ticked**, so nothing could be
  trimmed. It now lists the provinces something is picked in, which is its actual
  job and what bounds it.

**2026-08-30 — `where_to_produce`, second load. The data half works; the picker
is capped at twenty.** Five screenshots.

- **The result table reads.** "Бельцы — 9.25% (2/2)", fifty rows, descending.
  That is a location name out of a global variable and two script values printed
  from a localization key — the mechanism nothing in this repository had ever
  done, and the reason the first `where_to_produce` was worth attempting again.
- **The region lists render** with the game's own names ("Балканы", "Карпаты",
  "Польша"), so a list row's label set to `flag:<game key>` works and arrives
  translated. The ticks reach script: the zone came out at 260 locations in 53
  provinces.
- **A CMM dropdown is clickable only to its twentieth option.** Reported as
  "некоторые здания просто не выбираются". Found in CMF: an option click runs
  `CMM_MarkDropdownSelection_<index>` and CMF defines `_0` to `_19`. The
  218-option method picker was replaced by two lists — 47 goods, then at most 20
  ways to make the chosen one.
- **The selection window's rows collapsed to zero height**, all but the one
  expanded province, which piled them at the left edge. The item was wrapped in
  a `widget`, which does not size itself to its child; Advanced Auto Build puts
  the row type directly in `item`.
- **The window was the wrong shape for the job anyway.** The owner wanted what
  Advanced Auto Build actually does: the game's own target picker, which is a
  `select_trigger` block inside a `generic_action` — search box, sortable list,
  map highlight, and a map click picking the same thing a row does. AAB's
  restriction to owned land is its own `interaction_source_list`, not the
  engine's; vanilla's actions mostly give no source and filter with `visible`,
  which runs in the candidate's scope.

**2026-08-30 — `where_to_produce`, first load. The tab renders; no list on it
does.** Screenshot: the Mod Menu tab "Где производить" shows the group "Здание и
метод" with its three settings (the method dropdown, the tick, the button) and
nothing else — no region groups, no result table. Diagnosed from the files, not
guessed: `cmm_register_settings_list` declares `is_ordered` and the generated
call omitted it, so all six region lists and the result list died at
registration. Fixed; `tools/check_cmm.py` grew the missing-argument check that
would have caught it.

Two things the same screenshot settled without being asked:

- **The method dropdown is unusable at 218 options**, and the label was the
  reason. The control is about 165 pixels and elides the tail, so "good, icon,
  building, method" showed the good — which repeats for twenty rows — and cut off
  the method entirely. Relabelled to icon, building, method, and sorted by
  building so one building's methods sit together. Better, and still not a
  substitute for a real picker.
- **Registration itself works.** The dropdown, the tick and the button all
  rendered with their names and descriptions, so `cmf_on_mod_registration`, the
  mod id, the tab and the group keys are all right.

**2026-08-30 — `where_to_produce`, fifth load. The tabs and the table are on
screen; the row says too little.** One screenshot of the «Расчёт» tab, cloth
guild ranked.

- **The three tabs render** — «Товар», «Земля», «Расчёт» — and the button and
  the table are under the right one. The tab/setting key collision is behind us.
- **The table fills**, one row per province: twelve different names down the
  screen where the fourth run repeated one. The building prints
  («Гильдия прядильщиков»).
- **Every row reads 10.00%.** Not a bug: that method's only raw input is
  `fiber_crops`, so any province with fibre crops is at the ceiling. It is,
  though, the reason the ranking looks like it is not ranking — the row does not
  say what the number is made of.
- **What the owner asked for, off this screen:** the row names a location and he
  reads it as a province («показывается только 1 какая-то локация»); he wants
  the province, with its locations under it; which of the building's methods
  won; and the goods the bonus is made of («должно показывать прядильные
  культуры»).
- Regions, the age filter and `error.log` were not reported and stay open.

**2026-08-30 — `where_to_produce`, fourth load. Everything asked for worked.**
Owner: the goods tick moves; the ranking "работает, подбирает"; the map picker
"выбирается всё как надо"; nothing worth pulling out of `error.log`. That closes
the mod's whole mechanism — the scoring, the picker, the window, the map mode.

Four things the run asked for, all built and none of them loaded yet:

- **Tabs.** Five groups on one scroll. A CMM tab is just a `tab_id`, but a tab
  key and a setting key are both `<mod>__<id>_name` — so a tab and a list may not
  share a name, and the zone list had to become `continent`.
- **Regions back beside the continents.** A ticked continent paints the whole
  screen; the good case was one region ticked with its neighbours addable.
- **Methods the age has not reached were being recommended.** The unlock data is
  in the tree now: `1_building_unlocks.txt` gates 119 buildings by age and
  `3_production_method_unlocks.txt` gates ten methods directly, so
  `can_build_building` in country scope plus `has_advance` answers "available to
  me now". This is what `docs/archive/where_to_produce/where_to_produce.md` recorded as
  unanswerable; `common/advances/` was not in the tree then.
- **The table ran out of rows before it ran out of answers.** Every location of a
  province scores the same, so it now holds one row per province.

**2026-08-30 — `where_to_produce`, sixth load. The results window works; the
province is not what the game says it is.** One screenshot, everything selected.
Owner: «в целом вроде ок».

- **The window renders and does its job.** Rows, the area, 10.00%, the building
  **and the method after the colon** — and the methods differ between rows,
  «Гильдия прядильщиков льна» against «…шерсти», which is the scoring choosing
  per province in plain sight. The plus expands a row into its locations, each
  with its raw material and «Добавить».
- **A province is not a province.** Two rows, «Измаил» and «Молдавская провинция
  Бессарабия», are two halves of one province split by ownership — the game
  splits a `province` by owner and names the pieces that way. Ranking the halves
  answers for half the ground, and the answer would move on the day they join,
  which is the day the mod plans for. Now one row per `province_definition`,
  scored over every location in it, with each location's owner shown under the
  row. **Which of the two the engine's own bonus counts is still unknown** —
  `docs/research/engine.md` has the one-hover test that would settle it.
- **The window drew outside itself** — frame ending where it should, header and
  rows carrying on past it over the game's top bar. One description line:
  `autoresize` with no `maximumsize` does not wrap, it grows, and
  `allow_outside = yes` let it drag every expanding row with it. Bounded now, in
  both of this mod's windows, and `widgetanchor = center` added to match vanilla.
  Advanced Auto Build has the same defect, which is where the shape came from.
- **Unclear from the screenshot: the «Из чего» column looks empty.** The goods
  icons in the *location* rows draw fine, so `GetGoodsIcon` works; if the column
  is genuinely empty the fault is the `bag_wtp_goods` variable list. The row now
  prints «supplied/total» beside the icons, which tells an empty list from an
  icon that will not draw without another round trip.

**2026-08-30 — `where_to_produce`, seventh load. Whole provinces and the frame
hold; the goods icons do not.** Two screenshots, «в целом вроде ок».

- **The window is inside its frame** and **a row is one whole province** —
  «Бессарабия» as a single row, its locations under it with the owner's flag
  beside each. The owner's flag: «нахер не нужно, но и не мешает, пусть
  останется».
- **The goods icons never drew, and the count off the same list did.** «1/2» and
  «2/2» print correctly beside an empty space — so `bag_wtp_goods` holds the
  right items and `GetDataModelSize` reads them. What was missing is the
  `datacontext` on the datamodel item: the province rows work because they carry
  one, and this one addressed `Scope.GetGoods` from inside the type instead.
  Vanilla's own scope lists set `datacontext = "[Scope.Get<Type>]"` on the item
  and then use the type name, `GetGoodsIcon(Goods.Self)`.
- **Lakes and sea zones were in the expanded rows**, a screenful of «Ничья земля»
  under every coastal province. `ProvinceDefinition.GetLocations` hands out
  everything. Hidden now on `Location.IsPossibleToOwn`, and the whole mod's
  notion of ground moved from `is_land` to `is_ownable` — "not sea, lake or an
  impassable" — so nothing unbuildable enters the plan through the map picker
  either.
- **The count drifted with the number of icons**, «1/2» sitting a few pixels
  right of «2/2». An hbox sizes itself to its children, so one icon fewer moved
  everything after it. Placed in a plain `widget` now.
- **The method in the row is enough on its own** — the owner reads the recipe off
  its tooltip. The icons stay because a method with several inputs still needs
  them, and the count says what the icons cannot when they fail to draw.

### 2026-08-30 — `where_to_produce`, eighth load, with logs. Everything asked for
is on screen; the map picker is the one thing left.** Owner: «в остальном —
круто».

- **The goods icons draw**, the lakes are gone from the expanded rows, the count
  sits still. The `datacontext` on the datamodel item was the whole of the icon
  fault.
- **The whole-province rule is confirmed by eye**: Bessarabia is split by a
  border and the horses in the far half count towards its number, which is what
  the mod means by planning for the ground rather than the border. The engine's
  own tooltip was not the thing compared, so *that* question stays open — it is
  just no longer urgent.
- **`error.log` carries nothing of this mod's**, first time it has been read for
  it. 1706 of its 2742 lines are `jomini_custom_text.h` on vanilla Russian,
  341 are a null promote in a loc string, and the four `Widget cannot have a
  position in a layout` are Glorp UI's.
- **`gui.log` had 124 lines that were ours**: `bag_wtp_select_window.gui:177`,
  `Widget cannot have a position in a layout` — a `parentanchor` on a button that
  is a direct child of an hbox. Anchors belong inside a plain widget; an hbox is
  a layout and places its own children.
- **The icons sat a column apart.** An hbox given more width than its children
  spreads them across it. Left to hug its content now.
- **And the ask, for the fourth time: the game's own map selection.** Both
  screenshots are the same mechanism — `military_objective_group.gui`, driven by
  `MilitaryObjectiveGroupView` with `GeographyGlue` rows. **Engine objects: a mod
  cannot instantiate either**, and there is no on_action for a map click, so a
  window of one's own cannot be told what the player clicked. What *is* reusable
  is `PdxGuiWidget.SetHighlight{Region,Area,Province,ProvinceDefinition,Location}`
  — the game's own map highlight, callable from any `.gui`.

### 2026-08-30 — `where_to_produce`, ninth load. The tree came up empty, and the
ranking was ranking the wrong thing.** Three screenshots.

- **All four columns of the tree were empty, headers and all four frames drawn.**
  That pairing is the diagnosis: the header's `blockoverride` reached the
  instance and the rows' did not, because the rows' `block` was nested inside the
  `blockoverride` of the scrollbox. A block inside a blockoverride never
  resolves. The four columns are written out now, no column type at all.
- **The goods icons still sat a column apart** after being given no width: the
  spreading was the `icon` widget inside an hbox, not the hbox's size. They are
  text icons now — `[Goods.GetIcon]`, which is what vanilla writes in its own
  strings — and a text hugs its glyph.
- **The ranking put forest villages at the top of a weapons search.** Not a bug
  in the scoring; the scoring was answering the wrong question. A village wants
  one raw material, so it reaches the full 10% anywhere, and it produces 0.2
  weaponry a level against a weapon guild's 1.0 and a factory's 4.0. Ranking is
  by **effective output** now — `output * (1 + bonus/100)`, the bonus being an
  efficiency percentage and therefore a multiplier — and villages are scored on
  their own side, so a row shows two answers: the best built-up building and the
  best village.
- **The Mod Menu table is gone.** It said the same thing as the window one line
  at a time, and it was the only thing holding the answer to fifty rows.
- **The owner uses the region lists and nothing else** to frame a search:
  Карпаты in Europe, then the map picker for Валахия, Молдова, Трансильвания.
  That answers what six runs of "the region lists are untested" was asking.

### 2026-08-30 — `where_to_produce`, tenth load. The rows collapsed into each
other, the tree was still empty, and the selection window was the wrong idea.**
Two screenshots.

- **The province rows overlapped.** The card holding a row is a `widget`, and a
  widget does not size itself to its child: it was given
  `layoutpolicy_vertical = preferred` and no height when the row grew a second
  line. Fixed heights all the way down now — 60 for the card, 28 per answer.
- **The tree columns were still empty** after being written out, so the block
  nesting was not the fault either. Whatever it is, it is not worth another
  round trip: the whole selection window is deleted.
- **And the owner said what to do instead**: «нахрена для этого всего вообще
  целое отдельное окно? Просто засунь кнопки „выбрать…“ в окно результатов.
  Чтобы я прямо там выбирал и он мне прямо сразу показывал результаты после
  каждого изменения границ.» So the three map-picker buttons, the running count
  and «Очистить выбор» are in the results window, and **every pick re-ranks
  while that window is open** — the answer follows the borders as they are
  drawn.
- The scoring, the two-line row and the goods icons from the ninth build could
  not be judged under rows that overlapped; they come back for the eleventh.

### 2026-08-30 — `where_to_produce`, eleventh load. The window picked the ground
up and then ignored it, and the ranking arrived in map order.** One screenshot,
no logs.

Region «Карпаты» ticked in the Mod Menu, `books` the good, «Считать» pressed —
and the table was the region, correctly. Then «Выбрать область» three times:
Валахия, Молдавия, Трансильвания. The header count moved to «127 лок. в 26
пров.» and **the table did not change at all** — Северный Альфёльд, another of
Carpathia's seven areas and none of the three picked, was still in it.

- **A generic action's `effect` does not run in the country's scope.** The
  three map pickers ended with `bag_wtp_rebuild_browse` and
  `bag_wtp_recompute_live`, unwrapped. The first survived it — every line in it
  is scope-agnostic, which is why the count on screen kept moving and made the
  selection look like it had landed. The second opens with
  `has_variable = bag_wtp_result_open`, a country variable, got no, and returned
  having done nothing. Vanilla wraps all five of its own actions' effects in
  `scope:actor` and Advanced Auto Build's forty touch nothing but
  `scope:target_location`; not one of them relies on the bare scope. Wrapped
  now.
- **The ranking was ranking, and then an unordered copy shuffled it.**
  `bag_wtp_fill_rows` sorts with `ordered_in_global_list` into `bag_wtp_ranked`;
  `bag_wtp_show_results` then copied that into the window's datamodel with
  `every_in_global_list`, which promises nothing about order. On screen the rows
  came out clustered by area — the shape of map order, not of a ranking — with
  2.85% and 0.00% alternating down a list where every row was the same building,
  the same method and the same output. The copy is `ordered_in_global_list` now,
  each row carries the rank the pass gave it, and the window prints that rank.
- **Two numbers were added to say which half failed**, because both failures
  wrote nothing anywhere: the «№» column and «обошёл · нашёл · пересчётов». The
  twelfth run above is what they bought.
- **Found while reading, never reported:** `bag_wtp_can_build_something` is
  asked in a location's scope and read `global_var:bag_wtp_good_index`, which
  nothing ever wrote — the index is a country variable. Every branch missed, a
  scripted trigger of unmatched `if`s comes back true, and "only where it can be
  built today" filtered nothing whatever it was set to. The index is mirrored
  into a global now.

### 2026-08-30 — `where_to_produce`, twelfth load. The pick reaches the pass now,
and the two numbers put on the window for exactly this said which half of each
remaining fault was lying.** Three screenshots, no logs. `books`, region
Карпаты, Wallachia picked as one area.

- **«Обошёл 44 · нашёл 0», and the window emptied on every pick.** The scope fix
  landed — «пересчётов» went 4 → 11 and the walk found the right 44 locations —
  but the pass found no method in any of them. `bag_wtp_score_N` asks each
  method's advance with `root = { bag_wtp_avail_N = yes }`, and `root` inside a
  generic action is not the country any more than the bare scope is. **The rule
  had been applied to half the mod**: `root` was taken out of the row pass in
  the eleventh build and left in all 218 places in the scoring pass. The country
  is `save_scope_as` at the top of `bag_wtp_score_candidates` now and every one
  of them reads `scope:bag_wtp_country`. Pressing «Считать» found the same 44
  locations and 6 provinces, which is what proves the scope and nothing else was
  the difference.
- **The ranking was never sorting, and it is a matter of magnitude.** The «№»
  column came out 1, 2, 3 down the window — so the copy was fine — while the
  bonus went 0.00, 2.85, 2.85, 2.85, 0.00, 4.29, and the rows sat in
  alphabetical order of the province *key* (east_muntenia, north_muntenia,
  north_oltenia, south_muntenia, south_oltenia, west_muntenia). That is the
  unordered walk, so `order_by` was doing nothing. The scriptorium is the only
  book method this age unlocks, and in its own units it scores 0.3000 to 0.3129
  across the whole of Europe. **Nothing in the game or in any mod in
  `reference/` sorts on a fraction** — vanilla ranks on `military_strength` and
  `country_tax_base`, Advanced Auto Build on a score built out of `add = 12000`.
  `bag_wtp_m<n>` is the output times 1000 now: the same scriptorium runs 300.00
  to 312.88 and the provinces separate. Nothing prints it.
- **The «№» column and «обошёл · нашёл · пересчётов» did their job.** Both faults
  were invisible without them and both were named by them in one run rather than
  two: «пересчётов» rising with «нашёл 0» is the scope, and ranks in order with
  a scrambled bonus is `order_by`.
- **«44 лок. в 6 пров.» became «44 лок. в 0 пров.»** across a window close and a
  «Считать», with the selection untouched. `bag_wtp_rebuild_browse` only ran
  where a pick happened; it runs in the pass now. Not diagnosed further — the
  browse list has had no other reader since the selection window was deleted.

### 2026-08-31 — `where_to_produce`, fourteenth load. The filter works and the
offer to defeat it was the litter.** Owner: «Хвосты ушли… Хотя я абсолютно не
понимаю нахера вообще есть возможность смотреть на эти пустые хвосты — выглядит
как просто мусорная часть мода.» The tick is gone; the one case it protected —
a method that wants no raw material and so can earn no bonus anywhere — is a
branch in `bag_wtp_row_is_worth_it` and needs no setting.

**`mods.bat → 2` does not re-extract the game.** «Ничего нового там не было,
только копирование модов в плейсет и референс.» Adding a folder to
`tools/game_files_manifest.txt` is therefore not enough to get it into
`reference/`, and the owner copied `common/town_rights` in by hand instead.
Which menu entry runs `extract_game_files` — and whether one exists — is the
open question; the manifest entries for `goods`, `production_methods`,
`building_types` and `town_rights` are right either way, since without them the
next real extraction would have deleted three folders `where_to_produce`
compiles from.

**2026-08-30 — `where_to_produce`, thirteenth load. It works.** Owner: «В целом
вроде как всё починилось, что мне нужно было. Я выбирал области — всё
обновлялось сразу же.» Two screenshots.

- **The ranking sorts and the pick re-ranks.** «Обошёл 127 · нашёл 19 ·
  пересчётов 3» and again at 10, the areas following each pick, and the «№»
  column running 1…19 with the bonus falling down it. Both of the twelfth run's
  faults are closed: `order_by` sorts once the values are in the thousands, and
  the pass reaches the country from a generic action.
- **The two-line row reads**, first time it has been judged: «Гильдия
  ружейников: Кузнецы-клиночники ×1.00» at 2.37% over «Лесная деревня: Сельский
  оружейник ×0.20» at 10.00%, with the goods icons beside their `1/2` and `1/1`.
  Which also settles the ninth run's question: **the village is no longer at the
  top of a weapons search** — 0.22 effective against the guild's 1.0237 — and it
  is on the row where it belongs rather than above it.
- **The tail of 0.00% rows is noise.** Nineteen provinces found, and the ones
  after about ten were all «0.00% … ×0.30 … 0/2» — the same building at the same
  output as the rows above, supplying none of its raw materials. Filtered now,
  with a tick on the Answer tab to bring them back, and shown regardless when
  the winning method wants no raw material at all.
- **The mod page is a page to scroll.** Seven region lists and two goods lists,
  all unfolded. They are folded once now, the first time a player sees the page,
  and his own folding is his after that.

### 2026-08-31 — `where_to_produce`, fifteenth load. The rights window never
loaded, and the logs named both faults at once.** A right ticked, Карпаты
ticked, «Считать» pressed, nothing on screen. Logs supplied — first time this
mod has been diagnosed entirely from them, and neither fault was findable any
other way.

- **`gui/bag_wtp_right_window.gui:17 - '﻿' is not a valid widget/type/property`,
  then `Could not find widget 'bag_wtp_right_window'`.** The file carried
  **two** byte order marks: the header string in the generator already began
  with one and it was written through `encoding='utf-8-sig'`, which adds
  another. The second is a character in the text, the parser abandons the file
  at it, and every type in it goes missing — so «Считать» set the variable the
  window watches and there was no window. Nothing about the file looked wrong
  from here.
- **`Unknown trigger type: else_if` — 59 times, and it is not new.** A trigger's
  conditional is `trigger_if` / `trigger_else_if` / `trigger_else`: `if` is an
  *effect* in the engine's dump and `else_if` is not in it at all.
  `bag_wtp_can_build_something` has been an `if`/`else_if` chain since it was
  written, so it came back **true for every location** and «only where it can be
  built today» has never filtered anything — through fifteen loads, while the
  tick sat on the "never reported" list as though it were merely untested.
- **The one guess in the build was right**: `town_rights_type:<key>` stores fine
  as a CMM list item value. Nothing in any of the five `error.log`s mentions the
  rights list, its registration, or its localization.
- **`tools/check_script.py` is the answer to both**, and runs from
  `refresh.py`: a doubled byte order mark and an effect's `if` inside
  `common/scripted_triggers/` are each one regex, and each cost a run.

### 2026-08-29 — `mods.bat`, an update run on the owner's own machine

Not a game run — the mod menu, on the box that has Steam, reported by the owner
in full. It is here because only he can run it and because two of the three
things it found were invisible from a session.

**Loaded:** `mods.bat → 2 → 3` (reference and playset both), against a Steam
workshop folder that had Advanced Auto Build's 2026-08-28 build and Glorp UI's
2026-08-28 build in it.
**Expected:** the copies in `reference/` replaced, the generators rebuilt, and a
report of what moved.
**Observed:** the copies were replaced; **two generators failed and stopped the
run**, and the run then ended by telling him the two mods it had just copied in
were still behind.

- `auto_build_ru` — `28 key(s) the base mod does not define`. The new Advanced
  Auto Build deleted 28 keys, the ranking-mode block among them, and no key was
  added or renamed. A deletion, and it stopped everything.
- `glorpui_hints` — `Glorp UI writes a hint this mod cannot translate:
  GLORP_UI_SVH_CENTRALIZATION_PV_PETTY_BUREAUCRACY: @hint! Grant
  [ShowEstatePrivilegeName('petty_bureaucracy')]`. Glorp UI moved its hint
  references to the engine's own data function.
- `svx_unlock_gate.txt` changed in the same run, which is the quiet half: the
  advance gates are found by a second regex that only knew the old shape, so it
  matched nothing and wrote the file empty. Nothing errored.
- `workshop.py record` then stamped both freshly copied mods `behind`, because
  it dates a copy by `git log` and the copy was not committed yet.

**Verdict:** all four are fixed and the exact run was replayed against files
rewritten into the new shapes — refresh comes out green, with one note naming
the nine dropped keys. Still his to confirm: that the real 2026-08-28 files
behave the way the rewritten ones did, which is one `mods.bat → 2` away.

**He also said the tool never actually updated a mod in Steam for him** — he
still had to unsubscribe and resubscribe. It compared install dates, and Steam
stamps a mod updated when it *notices* the update rather than when it downloads
it. It compares build ids now (`manifest` against `hcontent_file`), and will
re-fetch a mod on demand whatever the check says. Untested against a real
`appworkshop_3450310.acf`; see [`STATUS.md`](STATUS.md).

### 2026-08-30 — `glorpui_hints` against Glorp UI's 2026-08-28 build, in game

**Loaded:** the owner's playset, Glorp UI 2026-08-28 with `glorpui_hints` after it.
**Observed, reported by the owner:** with Glorp UI's new «показать недоступные»
switch **on**, the two mods conflict and something on Glorp UI's side breaks;
with it **off**, everything is fine. He also reports their version of the
feature has gaps and does not show everything worth using, and that with their
filter off it is «совсем плохо».

**Cause, found in the files and not guessed:** their update added one
`TooltipScrolledStringPairList` per side that prints vanilla's own C++ hint blob
(`[SocietalValue.GetLeftHint(Player.Self)]`) when the country variable
`showUnavailableSocietalValueSuggestions` is set, and added
`NOT = { has_variable = showUnavailableSocietalValueSuggestions }` to every one
of their `glorpui_svh_visible_*` script values. So their switch is an either/or:
their filtered lists off, vanilla's blob on. This mod replaces that whole
`blockoverride`, and rebuilt their half from the entries its regex recognised —
which the blob entry is not. Switch on: their lists gone (their own script
values say so), their blob gone (this mod dropped it). Half the tooltip empty,
nothing in `error.log`. «Совсем плохо» is vanilla's raw blob, which is what
their switch shows.

**Fixed:** their block is now spliced in byte for byte and the check compares
text rather than parsed entries. Replaying the old behaviour against the new
files reproduces the fault and the check now names it.

**Verdict:** unrun. The fix has never been in game — the next load with their
switch **on** is the test, and what should appear is vanilla's blob plus this
mod's own lists, with Glorp UI's per-axis lists hidden by their own design.


### 2026-08-30 — the same switch, and `gui.log` named the build that answered

**Reported by the owner**, two screenshots and the whole `logs/` folder. Playing
Wallachia, both mods on, the *Наступление ↔ Оборона* tooltip. Switch **off**:
«Дальше продвинуться в сторону обороны» with its one takeable line, and this
mod's «Также влияет на смещение» under it — "the same as before the update, and
it suited me". Switch **on**: the «Дальше продвинуться» block disappears
outright; only this mod's block is left.

**That is the pre-fix bug, exactly, and the run did not test the fix.**
`gui.log` gives the line of every template that overrides another:

```
Template 'SocietalValueCountryLeft_tooltip'  at gui/svx_extra_societal_value_hints.gui:6
Template 'SocietalValueCountryRight_tooltip' at gui/svx_extra_societal_value_hints.gui:964
```

The file in this tree puts them at **9** and **984**. Lines 6 and 964 are commit
`012317f`, 2026-08-25 — the build with no blob block at all. The deploy in
`Documents/.../mod/glorpui_hints/` was never refreshed after 2026-08-29. The same
log fingerprints `glorpUI_generated_societal_value_hints.gui` at 3 and 261, which
is the 2026-08-28 build in `reference/` byte for byte, so their half is the half
we think it is.

**Confirmed anyway,** because the 25 Aug build is a real build:

| | |
| --- | --- |
| **the override chain** | `svx_… > glorpUI_… > shared/government_tooltips.gui`, both sides, no error. Load order is right and this mod does win the templates. |
| **`error.log`, 356 lines** | not one names a `svx_` file, `svx_unlock_`, `country_religion`, `GLORP_UI_SVH_*` or `SVX_*`. The advance gate and the aspect gate log nothing; the one `jomini_trigger` line is another mod's event. |
| **`ru_loc_fix` round two** | still 0, on a fourth run. `MARKET_SURPLYS_INFO` was 82 in the 07:44 logs of the same day and 0 in this one. |

**Not confirmed:** the splice, the five advance-locked privileges as *shown*
(Wallachia offers none of them either way), and `Inconsistent trigger scopes` —
its repair is newer than the gui file, so the deployed build's provenance for
`svx_extra_hint_loc.txt` is not pinned, and the Confucian Academy gate is on an
axis Wallachia does not have.

**Written down as a tool, not as a warning.** `python3 tools/which_build.py
<logs folder>` fingerprints every gui file in a log against this tree and against
`git log`, and says which commit ran. This is the second run lost this way.


### 2026-08-30 — the splice, in game, and it works

**Loaded:** the 2026-08-29 build, installed by hand from the repository because
`mods.bat` did not do it (see below). Wallachia, *Наступление ↔ Оборона*, Glorp
UI's «показать недоступные» **on**.

**Observed:** «Дальше продвинуться в сторону обороны» is back and now carries
vanilla's own unfiltered blob — five lines where the filtered list had one:
«Добавить государственный принцип "Система гарнизонов"» +0.05, «…"Тактика
асимметричной войны"» +0.10, «Установить политику "Оборонительная позиция"»
+0.10, «Содержание крепостей» and «Влияние совета», both (масштабируется).
This mod's «Также влияет на смещение» sits under it with its four. Glorp UI's
per-axis list is gone, which is their design.

**Verdict: the splice is confirmed.** Vanilla's blob, this mod's lists, their
lists hidden — exactly what was predicted, and the last thing this mod was
waiting on. The owner: «вроде всё работает ок», and «наш мод более показателен и
ясен визуально».

**Known and deliberately not fixed:** a few rows appear in both blocks —
«Содержание крепостей» is in vanilla's blob and in this mod's list. The owner
was asked nothing and said to leave it: the blob is theirs to decide and
de-duplicating across it would mean parsing it, which is the thing that broke
this feature the first time.

**2026-08-31 — `where_to_produce`, nineteenth load. The fed-first rule is right
and the second column was hiding behind it.** Two screenshots, fine cloth in
the Carpathians again.

- **Wool is back, exactly as asked.** «Гильдия портных: Мериносовая шерсть
  ×0.50» at 10.00% down the table, where the eighteenth run had one silk row at
  0.00%. Owner: «Теперь он показывает мне варианты с шерсть… Пустых и
  бесполезных провинций не показывается. Оружие и другие товары появились в
  списках.» Urban rights use wool too.
- **And the «В конце» column went blank on almost every row** — one province in
  the whole table had a figure. Not a display fault: **fine cloth from wool has
  no rung above the workshop.** The manufactory and the mill take only silk or
  cloth, so once the wool workshop is obsolete a wool province has no fine cloth
  recipe it can feed, and the fed-first rule correctly found nothing. A blank
  cell said that no better than it said "nothing changes here", which is what it
  had meant the day before. The far column now always prints: the fed survivor
  where there is one, the best survivor at 0.00% where there is not.
- **Weapons showed no far column at all**, same cause, same fix.
- **Two ticks nobody could tell apart.** «Ранжировать по последней эпохе» and
  «Считать методы, до которых не дошла эпоха» sat together and read alike, and
  with both on the table still offered workshops — which was right (the ladder
  ends there for wool) and looked wrong. Owner: «кнопку сортировки… нужно
  перенести в само окно результатов и делать это прямо там». Done: the two
  number columns are the buttons, and the ranking follows whichever was clicked.
  The unreached-methods tick stays on the mod page.
- **Right-aligned numbers against left-aligned names** read «1Восточная
  Мунтения». Every column is left-aligned now.

**2026-08-31 — `where_to_produce`, eighteenth load. The second column works,
and it brought back three things the first column had been hiding.** Five
screenshots, Wallachia, 1369, 127 locations in 26 provinces.

- **Both columns render and both ticks work.** «Прибавка» and «В конце» side by
  side, «Ранжировать по последней эпохе» visibly reorders and the re-rank
  counter moves with it. Paper: `2.49% -> 10.00%` on lumber-only provinces,
  `10.00% -> 10.00%` on Северная Олтения, which supplies both fiber and lumber.
  The ladder arithmetic is right on screen.
- **Ranking by the last age had no tiebreak**, so the 10.00 -> 10.00 province
  sat below a 2.49 -> 10.00 one. Owner: «конечный в приоритете, а начальный
  бонус — вторичным в счёте». Fixed with a thousandth of the near score added
  to the far one: the smallest step a raw material makes in the endgame set is
  1.9, so it can only order ties.
- **Cannons and firearms were not in the goods list at all** — hidden because
  no building for them is unlocked in the second age. That hiding is gone: every
  good some building makes is offered now, whatever the age, which also means a
  good another mod adds a building for.
- **Fine cloth answered with silk weavers at 0.00% in a wool country**, one row
  in the whole Carpathians. Not a bug in the arithmetic — 0.70 a level unfed
  beats 0.50 at the full ten percent — but the wrong answer: the game would run
  the recipe the market can feed, and the market is fed by the ground. **A
  method whose raw materials the province supplies none of is no longer an
  answer**; the wool provinces come back with wool weavers at 10%.
- **`fine_cloth_guild` runs two methods at once, not one.** The owner said cloth
  and jewelry have «улучшения» and cannons and firearms have ammunition; the
  files agree — eight buildings carry two `unique_production_methods` blocks,
  and a building runs one method from each. The mod treats them as alternatives
  and so understates both the output and the inputs of exactly those eight.
  Unbuilt, and the one thing here that needs a measurement before it can be:
  [`investigations/production_ladder.md`](investigations/production_ladder.md).
- **The rights window still answers for today only**, and its bundle showed
  weaponry alone until «Считать методы, до которых не дошла эпоха» was ticked —
  firearms and cannons have no unlocked building in the second age. It has no
  second column yet; that tick is what stands in for one.

## `where_to_produce`, the sixteenth to the twentieth load

Moved out of [`../TESTLOG.md`](../TESTLOG.md) when it outgrew its budget.
Every fault named here was fixed in the session that recorded it.

**2026-08-31 — `where_to_produce`, twentieth load. Everything asked for works,
and the middle age is missing.** Four screenshots, fine cloth and a weaponry
right.

- **Confirmed:** the far column prints 0.00% on every row; the sort buttons
  work and the mark follows them; two ticks on the page instead of three; no
  province at 0.00% in a rights table; «Уникальные права» empty for Wallachia.
- **Sorting appeared to do nothing with «Считать методы…» on**, and it was not a
  fault: with that tick the near column already held the best method of any age,
  which is the same ordering the far column gives. Two states saying one thing.
  The tick no longer touches the goods pass at all — the third column replaces
  it — and it is named for the rights window, which is all it still does.
- **Every column header sat ten pixels left of its column.** The rows are inside
  a scrollbox whose content carries a 10px margin and the header is not;
  `margin_left` is 48 now, and the three sort buttons have gaps between them.
- **A good of a bundle vanished when the ground fed it nothing** — Северная
  Мунтения showed мебель and керамика but not кожа. Owner: it should stay, at
  0%, and only a row where *every* good is fed nothing should go. A slot now
  falls back to the best available method whether it is fed or not; its value to
  the ranking stays zero.
- **And the ask this run is really about.** «В конце» is 0.00% for every wool
  province, so it cannot order them, and what the owner wants ordered is
  precisely that: where to build so that nothing is rebuilt, taking the best the
  ground gives *along the way*. There is now a third column, «По пути»: the best
  recipe this ground ever feeds in any age, and the last age it can be built —
  `10.00% до 5` for wool fine cloth, because the manufactory that obsoletes the
  wool workshop unlocks in the fifth. Sorting by «В конце» breaks its ties on
  it, so the top row is the province that ends best and, among equals, is best
  on the road there.

**2026-08-31 — `where_to_produce`, seventeenth load. The registration fix holds,
two things are confirmed after weeks of «never reported», and the filter that
was meant to be fixed was never written.** Owner: «Список теперь сохраняется
после закрытия и открытия окна мода… Думаю основной пул задач для этой сессии
был выполнен.»

- **The counters are honest.** «Обошёл 127 · нашёл 19 · пересчётов 3», «в 26
  пров.», «№» running 16…19 down the visible part. Opening the mod page no
  longer throws the answer away, and «Открыть» reopens the last result — which
  is the whole of what that button is for.
- **Confirmed, both long outstanding:** the pickers stay folded («свёрнутые
  списки давно проверены — они сохраняются свёрнутыми»), and **the age filter
  works** — «метода производств и домики действительно меняются на более крутые
  и расчёт идёт уже от них». Seventeen loads to get that one reported.
- **Южная Олтения at 0.00% on all three goods is still there**, and the reason
  is not the filter's logic. `bag_wtp_right_row_is_worth_it` is *called* by the
  generated pass and **nothing defines it**: the patch that was to have written
  the trigger died half way through and only the call survived. An undefined
  name in a `limit` does not stop anything — the limit passes, and the symptom
  is a filter that filters nothing, exactly as the `trigger_if` fault looked.
  Written now, and `tools/check_script.py` refuses an unresolved call: every
  `<name> = yes` in a mod's own `common/` must resolve to the mod, to a mod in
  `reference/`, or to the engine's dumps.
- **And the buildable tick does not mean what it said.** «При её включении —
  показывается всё равно не только моя земля, но и чужая. Основное что она
  фильтрует — наличие городов в провинции.» He is right and the label was wrong:
  `can_build_building` is asked in the *location's* scope and answers about the
  location — its rank, its terrain, what the building needs — not about who owns
  it. It reads «Только там, где здание вообще может стоять» now, and says so.

**2026-08-31 — `where_to_produce`, sixteenth load. The rights window works, and
one screenshot carried three faults at once.** «Вроде как работает… выглядит
наглядно и понятно.» The bundle rows read: three goods, each with its own
method, bonus and materials, «Ценность» ranking them.

- **«Обошёл 127 · нашёл 0 · пересчётов 3», «в 0 пров.», and «№» reading 0 on
  every row — with rows on screen.** All one cause: `bag_wtp_register` ended
  with `bag_wtp_drop_browse` and `bag_wtp_clear_rows`, and **CMF's registration
  hook fires again every time the mod page is opened**. Opening the menu wiped
  the answer, zeroed the counters and took the rank off every location. The
  owner had already described the symptom without connecting it: «если закрыть
  окно cmm и открыть мод заново — расчёт сбросится». Registration touches
  nothing now.
- **The rows survived that wipe because `bag_wtp_clear_rows` did not know about
  `bag_wtp_right_results`** — a second window's list added and not added to the
  one effect that empties them. Hence a table of rows whose rank had just been
  removed.
- **A province at 0.00% on all three goods, «0/2» three times.** The good pass
  has filtered those since the fourteenth run; the rights pass had no equivalent
  and `var:bag_wtp_r_total > 0` is true of any province where the bundle can be
  made at all. `bag_wtp_right_row_is_worth_it` now asks the bundle's bonuses.
- **And the rights list wanted splitting.** «Мне за валахию не особо то надо
  видеть монополию константинополя.» Two lists now, and the split is the game's
  data rather than an opinion: a right `town_rights_enable` unlocks is general
  (nine of them), anything else is unique. A unique right is offered only where
  the game's own condition passes — the silk monopoly carries
  `potential = { OR = { has_or_had_tag = BYZ has_or_had_tag = ROM } }` and the
  Scandinavian privileges carry an advance nobody else takes.

## `where_to_produce`, the twenty-first load

Moved out of [`../TESTLOG.md`](../TESTLOG.md) when it outgrew its budget a
second time. This is the run that settled the two-slot question; the working of
it is in
[`../investigations/production_ladder.md`](where_to_produce/production_ladder.md).

**2026-08-31 — `where_to_produce`, twenty-first load. The two-slot question is
answered, from the game's own panel.** Three screenshots.

- **Confirmed:** «По пути» prints `10.00% до 5` on the wool provinces and
  `0.81% до 6` where there are dyes; sorting by «В конце» orders them; a bundle
  keeps every good, at 0% where the ground feeds it nothing; alignment is better.
- **Each production slot earns its own bonus, over its own output.** A tailors'
  guild in Dordrecht: the tooltip is headed «Производственная эффективность
  метода "Красители с квасцами"» and lists «Добыча ресурса "Красители"…
  +10.01%» under it. Not the building's efficiency — the method's. So the eight
  two-slot buildings are now one method of the summed output at the
  output-weighted blend of the two bonuses, and the owner's own reading of the
  screenshot said the same thing before the arithmetic did.
- **Which explains what he noticed first:** Западная Мунтения showed «1/1» and
  the wool icon while the province also supplies dyes. The dyes feed the
  *improvement* slot, which the mod was not modelling. That row is a pair now.
- **The «×» is per building level.** The panel showed 0.76 against the method's
  0.2: four levels, an age multiplier, and efficiency multiplying output but not
  inputs. Nothing there separates provinces, so the mod keeps the per-level
  figure.
- **Three sort buttons in a header were one control too many.** Owner: «Я хочу
  иметь ровно две кнопки расчитать» — one for what you can build now, one aimed
  at the end of the game, both filling the same three columns. The headers are
  plain labels again and the second «Считать» is on the mod page.
- **The rights window's header lined up with nothing.** Same 10px scrollbox
  margin as the goods window, now fixed, and its columns read left too.

**2026-08-31 — `where_to_produce`, twenty-third load, with logs.** Owner: rights
work and the two tables differ; unique rights arrived in Wallachia; the goods
table ranked for the last age still named first-age buildings; «Из чего» still
sits away from its header.

- **`error.log` carries one real line and no more:** `PostValidate of trigger
  'trigger_else_if' returned false at bag_wtp_generated_triggers.txt:107` — the
  last link of the `bag_wtp_can_build_something` chain, which ended on an
  `else_if` with no `trigger_else` after it. Everything else naming the mod is
  `Flag 'bag_wtp_good_*' is set but is never used`, which is CMM's list flags and
  is cosmetic. The chain ends `trigger_else = { always = no }` now.
- **Dropping the advance gate let the Scandinavian privileges into a Wallachian
  list.** Those two rights carry no `potential` of their own; what keeps them out
  is `culture = { has_culture_group = culture_group:scandinavian_group }` on the
  *advance* that unlocks them. A right inherits its advance's `potential` now —
  a country gate that is a fact rather than a thing you have not got round to.
- **Ranked for the last age, the row still named the building you can build
  today.** The order followed the button and the printing did not: the method
  column reads the near column whenever it is set, and it always is. `row_end` is
  written on the row now and the window reads the column the button asked for,
  goods icons included.
- **«Из чего» drifts because the method column expands.** An expanding column is
  as wide as what is left, and a row inside a scrollbox has less left than the
  header — by the scrollbar and the content margin. Both windows give the method
  column a fixed width and put the slack in a spacer at the far right.

**2026-08-31 — `where_to_produce`, twenty-second load. The pairs are right and
the rights window was answering the wrong question.** Three screenshots, fine
cloth and cannons, and a weaponry right.

- **The pairs read correctly.** «Гильдия портных: Гильдия ткачей шёлка ×0.90 +
  Красители с квасцами», «Здание пушкарей: Железные стволы ×1.16 + Железные
  снаряды», with both slots' raw materials counted.
- **«Считать» looked like it was sorting by the endgame** — 1.78% above 7.14%.
  It was not: the ranking is by effective output and always has been, so ×0.90
  at 1.78% (0.916) outranks ×0.70 at 7.14% (0.750). Settled at the eighth run,
  when a forest village at 10% topped a weapons search; the owner reached the
  same reading himself from the cannons table.
- **«На конец» did nothing at all in the rights window.** The bundle pass read
  `bag_wtp_best_method` and nothing else, so both buttons gave the same table in
  the same order, showing first-age buildings. It reads the column the button
  names now, falls back the same way, and breaks its ties on «По пути» — with
  the row filter widened, or the table would empty itself exactly where a ladder
  ends early.
- **«Права: считать методы будущих эпох» is deleted.** Owner: «нафига вообще
  нужна?» — right twice over: since the twentieth load it reached no method at
  all, and a right should obey the same two buttons a good does. A unique right
  is still gated on `potential` — a tag is a fact about the country — but never
  on the advance that unlocks it.
- **«Из чего» sat far right of its header** in the rights window: the block was
  sized by its own icons and started wherever the expanding method column
  stopped. It is 190 wide in both windows now, like the header.

Everything before 2026-08-29, and `where_to_produce`'s first twenty-one loads — the
map mode, the twenty-option dropdown, the missing `is_ordered`, the run that
turned the mod from asking for a method into finding one, and the four that
confirmed the scoring, the tabs, the results window and whole provinces — is in
[`archive/testlog_2026-08.md`](archive/testlog_2026-08.md), moved rather than
trimmed. Search both with `python3 tools/kb.py`.

**2026-08-31 — `where_to_produce`, twenty-fourth load. The fixed-width columns
ate the building's name.** Two screenshots, fine cloth and textile.

- **A row printed «± Красители с квасцами» and nothing else** — no building, no
  method, no «×». The cause is one line: the method cell was given a size of its
  own, and a child carrying `layoutpolicy_horizontal = expanding` inside a sized
  hbox gets **no width at all**, so the text elided to nothing. The improvement
  beside it survived because it was `autoresize = yes`. Every column in both
  windows carries an explicit width now and none of them expands; the slack goes
  to a spacer at the far right, and the row's widths add up to the header's to
  the pixel (762 after the area column in the goods window, 700 per slot in the
  rights one).
- **Two spacers where the header had one.** «В конце» was followed by 10px in a
  row and 6 in the header, and a second 6 had crept in before «По пути»: four
  and six pixels, and every column after them out of line. That is the whole of
  the «Из чего» drift.
- **Fifty pixels moved from «Из чего» to «Здание и метод»**, which is where the
  long names are: a building, a method and an improvement in one cell.
- **Urban rights work on both buttons**, owner's words, and the unique list is
  empty again — which for Wallachia is the right answer, since the two
  Scandinavian privileges gate on a culture group and the Byzantine one on a tag.

**2026-08-31 — `where_to_produce`, twenty-fifth load, with logs.** Two
screenshots of fine cloth, «Считать» and «На конец».

- **The row names its building again and every column sits under its header** —
  both asked for and both confirmed. `error.log` carries no `PostValidate` with
  `bag_wtp` in it; the only `bag_wtp` lines are `Flag … never used` and five
  `Variable … used but never set` for `_mid_goods*` and `_pm2_rural`, which are
  a generated `clear_variable_list` and a village that never runs a pair. Noise.
- **«Из чего» is still not under its header, and worse on the second
  screenshot.** Not a drift this time: the icons are *centred* in their column.
  The container is an hbox with a width, `ignoreinvisible` leaves it exactly one
  visible child, and an hbox with a width spreads its children across it — so
  the offset is half the slack, which is why «0/1» alone sat further right than
  «1/3» with an icon. Both windows' goods columns are plain `widget`s now with a
  `parentanchor = left|vcenter` inside.
- **A silk weaver was offered where there is no silk.** Западная Мунтения
  supplies dyes and nothing else the recipe wants, and it came first at 1.78% on
  «Гильдия ткачей шёлка + Красители с квасцами» — one input of three. Owner:
  the market will not have silk either, so it is not an answer at all. The floor
  a method has to clear is **half the bonus its raw materials could ever add**
  now, not one point above nothing; `generate.fed_floor`, and the same fed/unfed
  fallback as before behind it.
- **The buildable tick drops provinces, but only after the window is closed and
  opened again.** It never re-ranked — it wrote the setting and refreshed the
  lists, which is right for every other tick on that page and wrong for the one
  that changes which provinces are candidates. It calls
  `bag_wtp_recompute_live` now, the same guard the map pickers go through.
- **Wallachia sees no unique rights, which is the right answer.** The mod offers
  three of them — two Scandinavian, gated on a culture group, and the Byzantine
  silk monopoly on a tag. The other five grant building levels rather than an
  output ratio and are deliberately not in the list. The Scandinavian half of
  the question is still unrun and the owner has said he would rather not.

**2026-08-31 — `where_to_produce`, twenty-sixth load. All four fixes hold.**
Three screenshots, fine cloth, and the owner's verdict: «если не придираться к
этим злосчастным столбикам и выравниваниям, сейчас меня устраивает функционал».

- **No silk weaver where there is no silk.** Западная Мунтения now reads
  «Гильдия портных: Мериносовая шерсть ×0.70 + Красители с квасцами», **9.43%**,
  «2/3» — and the two icons say why the old answer was wrong in a way nobody had
  spotted: **the province works wool *and* dyes**. Silk never had anything to do
  with it. 7.14 (wool) + 2.29 (dyes) = 9.43, the recipe fed on both halves; the
  silk one won before only because 0.90 a level unfed beat 0.70 a level at 7.14%.
  «В конце» is «Фабрики тонкого сукна ×4.00», 0.63%, «1/1». The wool provinces
  behind it are untouched at 7.14% «1/3», and the count went 13 → 12.
- **The buildable tick re-ranks the open window** — third screenshot, «Обошёл 8 ·
  нашёл 5 · пересчётов 4», five provinces left standing with the window never
  closed.
- **`error.log` is clean**: not one `bag_wtp` line beyond the `Flag … never used`
  and `Variable … used but never set` noise. The two `PostValidate` lines are
  `qol_vassal_test_events`, another mod's.
- **Two columns I narrowed were narrowed too far.** «Восточная Мунтения» abuts
  «Валахия» and «Трансильвания» abuts its percentage: `elide` fills a column to
  the last pixel and then touches the next one, so width alone can never fix it.
  Both got their width back and a spacer of their own, paid for out of the method
  column, and the row still adds up to what the header does.
- **Not settled: whether «Из чего» is now under its heading.** The middle columns
  read as aligned in the screenshots and that one may still sit a dozen pixels
  right, which is too fine to call at this resolution. One glance on the next run
  answers it.

**2026-08-31 — `where_to_produce`, twenty-seventh load. The market picker works,
and it is drawn on the map after all.** One screenshot, fine cloth, «На конец».

- **A market *is* a map region to the picker.** Hovering outlines the market's own
  borders and a click takes it — no list needed, the same feel as an area. The
  file said the opposite for one commit; a market not being drawn on the map was
  a guess from vanilla's one usage and it was wrong.
- **But only the markets `interaction_source_list` names are clickable**, and it
  named `every_market_present_in_country`, so the neighbour's market could not be
  taken — which is exactly the market somebody planning a conquest wants to lay
  out. It is `every_market_in_world` now, framed by the ticked continents the way
  the other three pickers are.
- **The picking works and the owner is happy with it**: «В остальном всё чётко,
  удобно, классно.» Selection, re-rank and the counters all followed.
- **The four picker buttons were transparent and dreary** — an `action_button`
  with `bg_button_flavor_1`, copied from Advanced Auto Build, which is a flavour
  background over a bare button. They are `action_button_regular` now, which is
  the game's own type using `button_regular_texture`: the same solid look as
  «Очистить выбор» beside them.
- **The corner above the +/- buttons was empty** and read as a column out of
  line. It has a «+» heading now; `margin_left` went 48 → 10 and the new 38-wide
  cell makes the difference back, so «№» has not moved.
- **And the goods row was four pixels wider than the scrollbox it sits in** —
  1104 against 1100 — which nothing had noticed. The trailing spacer pays it
  back.
- **Still open: «Из чего» reads as sitting right of its heading.** Measured out
  of the file, the header and the row are identical column for column, so this is
  not a width. What is left is a constant inset the rows have and the header does
  not, and `margin_left` is the one number that moves it.

**2026-09-01 — `where_to_produce`, twenty-eighth load. The whole-map plan runs,
and the owner's verdict is «получилось даже более менее сносно, я ожидал большой
лажи».** Three screenshots, Wallachia, caps 3/3.

- **The pass survives a button press and nothing was reported slow.** 44
  locations, 132 rooms, **30 of the 47 goods makeable on that ground**, 90
  buildings in 31 locations at 3 per good. The window drew, the counters read,
  the map mode painted. Everything built on 2026-09-01 is now loaded except the
  «Открыть» button and the caps at anything but 3.
- **The per-good number was the binding constraint, not the caps.** Raising the
  urban cap 3 → 5 changed nothing; raising «зданий на товар» to 10 filled the
  ground exactly — **132 buildings in all 44 locations**. So the caps were never
  reached and the ceiling the plan actually ran into was its own rounds.
- **Locations were left empty at 3 per good**, 13 of the 44, and the owner's
  ruling is that **no location in the plan's ground should ever be left empty**:
  what a displaced building leaves behind is exactly what should cascade into the
  poorer ground.
- **And the one-good-per-province rule was the wrong rule.** It was built to
  spread a good across provinces; the owner plays the opposite way — «вся
  сельская местность в одной провинции в большинстве случаев получит линейку
  домиков одинаковую», a province specialises and its locations repeat it. He
  read the scatter on the screenshot as a fault before realising the rows were
  grouped: what he expected under Западная Мунтения was «ряд почти одинаковых
  товаров». The rule is inverted rather than tuned — see
  [`investigations/whole_map_plan.md`](investigations/whole_map_plan.md).
- **Asked for besides:** urban rights in the plan, with first pick of the ground
  and a switch to leave them out.
- No logs asked for and none needed: nothing did nothing.

### 2026-09 — `where_to_produce`, the plan's first three loads

The twenty-ninth to thirty-first, archived when the thirty-fourth tripped the
live log's budget. Each is superseded by a later run: the province model's
silence was the `province_definition` variable, the empty plan was the shared
sweep budget, and both are closed. Kept because they are the evidence.

**2026-09-01 — `where_to_produce`, thirty-first load. The plan was planning
things that cannot be built.** Three screenshots, Westphalia, 48 locations in 31
provinces, caps 3/4, once without rights and once with.

- **«Локаций 48 (городских 6) · провинций 8 · мест 150 · товаров 32 · записей в
  списках 43 · зданий 148 в 48 локациях · кругов 4».** The building rule and the
  rank-gate sides both hold — village lists are different buildings now.
- **And the plan offered iron in East Westphalia, where iron has exactly one
  building: `bog_iron_smelter`, whose `location_potential` is
  `is_adjacent_to_lake` or `topography = wetlands`.** There are no wetlands
  there. Plantations were on offer in Westphalia too, and `sugar_plantation`
  wants the location to already grow sugar *and* be overseas or colonial.
  **The plan never asked whether a building may stand where it is put** — the
  ranking has that tick and the plan did not inherit it.
- **The fix is one condition and the engine's own words justify it.**
  `can_build_building` documents itself as "location only checks local
  requirements, country checks the country scope requirements", so asked in the
  location's scope it is terrain, rank and `location_potential` and never the
  country's advances — which is exactly what a plan wants, and it is safe on the
  end-of-game side too.
- **A right was granted where its bundle does not fit.** Brewing rights (beer,
  liquor, wine) landed on a province with no wine, and the ordinary sweeps filled
  the third slot with horses and salt. His rule: **a right obliges every good of
  its bundle to be made where it is granted**, so all or nothing. No two goods of
  any bundle in the game share a town building, so the test is an exact AND of
  the per-good conditions.
- **The right was printed on village rows as well**, where a right never applies.
- **The window's toolbar was 1272 wide inside 1130** — four 164-pixel picker
  buttons, a 260 summary and two 150 buttons — which is the frame «уехала» he
  saw at the top right, twice now.
- **And the doubt underneath all of it:** «я начинаю сомневаться, что мод вообще
  хоть как-то ранжирует». It does — `bag_wtp_m<n>` (output × RGO bonus) →
  `_pnowbest_*` → `_p<g>` → `order_by` — and the fed floor is applied. It was
  ranking correctly over a set of methods that included ones the ground cannot
  hold, which reads exactly like not ranking at all.
- No logs asked for and none needed.

**2026-09-01 — `where_to_produce`, thirtieth load. The plan runs, and the owner
found the model's real mistake in one province.** Two screenshots, 127 locations
in 26 provinces, caps 3/4, rights on.

- **«Локаций 127 (городских 8) · провинций 19 · мест 389 · товаров 30 · записей
  в списках 75 · зданий 322 в 120 локациях · кругов 8».** The province model
  works end to end: rows grouped by province, its towns first, and its locations
  carrying the same list. The `province_definition` fix held.
- **And the list is wrong, because its unit is wrong.** Székely Land's villages
  each got tools, jewelry and beer — «по сути все три этих товара даёт одно и то
  же здание „торговая деревня"». He is right: `market_village` makes all three,
  **a location holds one building of a type and a building runs one method**, so
  those three entries are one building's worth of answer and two wasted slots.
  The plan's list is a list of **buildings** now, not of goods, and a good whose
  winning building is already on the province's list is not an answer.
- **The worse half of the same mistake, found by following it up.** The plan's
  «village» side was `village_category` — four buildings in the whole game. But
  **thirty production buildings declare `rural_settlement = yes`**, and the other
  twenty-six are exactly what he said should have been there: stone quarries,
  clay pits, lumber mills, masons, salt collectors, sand pits. The two sides are
  split on the building's own rank gates now (`eu5data.Method.rural` / `.urban`),
  which takes a rural location's choice from 4 buildings to 30 and from a
  handful of goods to 31.
- **19 provinces against 26 «выбрано»** is not yet explained. The picker counts
  provinces its own way and the plan counts the ones it prepared; they should
  agree, and one of them is wrong.
- **What he could not read:** the town/village override. It was two glyphs drawn
  over the corner of the rank icon — «просто на значке появились какие-то
  символы». It is a labelled button in a column of its own now, saying
  «авто / город / село» in words.
- **Asked for besides:** «Пересчитать» inside the window, so a run happens when
  he says so and not after every click; the urban right named on the row, not
  merely implied by its goods; and the plan on two buttons like the ranking,
  now and at the end of the game.
- No logs asked for and none needed.

**2026-09-01 — `where_to_produce`, twenty-ninth load. The province model placed
nothing at all, and `error.log` carried not one line about it.** One screenshot,
Wallachia and more, with logs.

- **«Рассмотрено локаций: 127 · мест: 381 · товаров тут можно делать: 30 ·
  зданий: 0 в 0 локациях · лимиты 3/3 · кругов: 1».** So the ground was
  collected, the capacity counted, thirty goods scored and normalized — and then
  every one of the 47 picks failed its `limit` in silence. The rights switch made
  no difference and neither did the per-good ceiling, which places the fault
  before either of them.
- **The logs are clean.** Not one script error, trigger error or missing-variable
  line from the pass. This is the failure `CLAUDE.md` names: an effect that
  merely does nothing logs nothing.
- **The cause, on the evidence: a `province_definition` will not hold a
  variable.** The province's lists and their counters were kept on the
  definition, and `var:bag_wtp_plan_town_n < …` was then read back in every
  pick's `limit`. A definition is static map data; **nothing in vanilla and
  nothing in any mod in `reference/` writes a variable to one**, and the mod's
  own proven idiom has always been `every_location_in_province_definition`
  instead. Everything the pass reads was moved onto the locations, mirrored
  across the province.
- **Not proven, and that is why the summary line grew.** It now reads locations,
  towns among them, provinces, room, goods, list entries, buildings — left to
  right, so the first zero names the step that failed without another zip.
- **The other thing the log gave up:** «Value of wrong type in
  `bag_wtp_show_found:0`», once a frame with the page open, because the
  *ranking's* `bag_wtp_found` was never initialised on a fresh save. Fixed in
  `bag_wtp_init_counters`.
- **Asked for besides:** a hand switch to plan a location as a town, because the
  game's rank is only what is true today; the map pickers in the plan window,
  since choosing ground meant opening the other window and coming back; and a
  better name for «не больше стольких провинций на товар», which read as «не
  больше сельских».

### 2026-09 — `where_to_produce`, the thirty-second and thirty-third loads

Archived when the thirty-seventh tripped the live log's budget. Both are closed
and both are confirmed by a later run: the buildability gate works, and the sweep
budget is per tier.

**2026-09-01 — `where_to_produce`, thirty-third load. The sweep guard ate the
plan, and the owner called a halt to iterating.** Three screenshots, Westphalia,
caps 3/3, rights on; and the ranking checked separately on stone.

- **«Локаций 48 (городских 7) · провинций 8 · мест 144 · товаров 27 · прав
  выдано 1 · зданий 28 в 20 локациях · лимиты 3/3 · кругов 12».** Twenty-eight
  buildings out of a hundred and forty-four places, most locations holding one
  thing, whole provinces cut short.
- **«Кругов 12» is the diagnosis and it is in the line.** `PLAN_ROUNDS` is 12 and
  the sweep counter was **one counter shared by all six scarcity tiers**, so the
  scarce tiers spent the budget and the last tier — the one that fills the ground
  — never ran. Each tier has its own budget now.
- **The ranking's buildability gate works and is visibly right.** Stone in
  Westphalia: the wholly flat province is gone, and Sauerland stayed with 3.72%.
  **But Sauerland has seven locations and one of them is flat**, and the row said
  nothing about that: «мне должно предлагаться конкретнее место». A row prints
  `n/m` now — how many of the province's locations can hold the winning building
  — counted for free off the winners the scoring pass already wrote.
- **«Обошёл 48 · нашёл 1»** for stone across the whole of Westphalia. One
  province. That is the gate being strict, and it is worth knowing whether it is
  too strict before anything else is built on top of it.
- **Only one urban right granted** (tools, in Münster). All-or-nothing plus
  buildability is a hard filter and Westphalia is a poor ground for bundles, but
  whether that is right or too strict is not settled.
- **The picker says «48 лок. в 31 пров.» and the plan says «провинций 8».** They
  count different things — the picker counts `province`, the owner-split piece,
  and the plan counts `province_definition` — and neither label says so.
- **The plan's icons ran together.** 26-wide cells at 2 spacing; 32 at 6 now.
- **And the owner's instruction:** «Мне кажется нам нужно сначала вывести точную и
  доходчивую формулу приоритетов и выгоды постройки производства, нежели вот так
  вот долбить всё туда-сюда.» No more counters, no more rounds of guessing —
  agree the formula first. It is written out in
  [`investigations/plan_formula.md`](investigations/plan_formula.md) and that
  document is the next session's first move.

**2026-09-01 — `where_to_produce`, thirty-second load. The buildability gate
holds, and the owner took the model apart one level further.** Two screenshots,
Westphalia, 48 locations, caps 3/3.

- **«Локаций 48 (городских 6) · провинций 8 · мест 144 · товаров 27 · записей 37
  · зданий 140 в 48 локациях · кругов 4».** Goods fell 32 → 27 and buildings 148
  → 140 with the gate in, and **no iron anywhere** — which is the gate working,
  though he knows of a wetland province and wants to see it offered there.
- **The building icons drew nothing.** `BuildingType.GetIcon` returns a `CString`
  — a texticon, the same as `Goods.GetIcon` — so it belongs in `raw_text` and not
  in an `icon`'s `texture`. Vanilla writes it that way in `alertmanager.gui`.
- **`§Yгород§!` printed literally** in the override button, and its rank icon of
  course never changed, being the game's. One word, no markup, and the game's
  own rank icon moved out beside the location name.
- **No urban right anywhere, all dashes.** Truthful under all-or-nothing —
  Westphalia can make no whole bundle — but indistinguishable from a broken
  feature, so the summary counts rights granted now.
- **And the ranking beside the plan was cheating the same way.** «Каменоломню мне
  выдало что отлично можно построить в провинции где полностью равнина, но там
  есть дерево». `can_build_building` now gates every one of the ranking's
  answers too, in all three ages.
- **Two rules of the model were wrong, and he found both.**
  **One:** uniqueness is per *location*, not per province — a market village
  makes tools, jewelry, beer and pottery, so four villages of a province may take
  one each rather than all taking pottery. The province lists are gone; the plan
  decides per location and a province looks coherent only where it deserves to.
  **Two:** a good only one place can hold must take that place before a common
  good takes its second — «жёстко зарезервировать». The sweeps run in scarcity
  tiers now (1, 2, 4, 8, 16, then everything), ordered by how many candidate
  locations can host each good.
- **He asked for the algorithm in plain words**, and it is on the «План» button's
  own tooltip now, six steps.
- No logs asked for and none needed.

### 2026-09 — `where_to_produce`, the thirty-fourth and thirty-fifth loads

Archived when the thirty-eighth tripped the live log's budget. The window's own
open flag and the per-tier sweep budget, both closed and both confirmed by later
runs.

**2026-09-01 — `where_to_produce`, thirty-fifth load. Both plan buttons opened
nothing, and it was a rename in the same session that did it.** Logs supplied;
`which_build.py` confirms the tree.

- **«Кнопка "план" и одна и вторая теперь просто не работают и не открывают окно
  расчётов (с гор правами и без них). По отдельным товарам — всё работает.»**
- **`error.log`: «Variable 'bag_wtp_plan_open' is used but is never set.»** That
  is the whole fault. Adding the quota phase introduced a global flag and it was
  renamed `_plan_free` to keep it away from the window's own `plan_open`; the
  rename matched on `plan_open value = 1` and caught
  `bag_wtp_open_plan_window_effect` too — the **only** thing that sets the flag
  the window's `visible` reads. Both plan buttons go through that one effect,
  which is why both died and the per-good windows did not.
- **Nothing else of this mod's is in the log.** No script-value error from the
  province divisor, the quota, the RGO count or the mandatory rights, so the
  pass itself is untried rather than broken — the window never opened to show it.
- **Also in the log all along and now explained:** «Variable
  'bag_wtp_pm2_rural' is used but is never set», and its `mid_`/`end_` twins.
  Not a fault: **no two-part method may stand in a rural settlement** — all
  eight two-slot buildings are town and above — so the second-method half of a
  village row is always hidden, which is what it should be. The widgets are left
  alone and marked.
- **A checker now catches this class**, and was proven against this exact bug: a
  variable the mod reads that nothing in it, and not CMF, ever writes.
  `remove_variable` deliberately does not count as a write — read, removed, and
  never set is the shape of the fault.
- **The plan is still unloaded.** The thirty-fourth run's four changes have not
  been seen once.

**2026-09-01 — `where_to_produce`, thirty-fourth load. The per-tier sweep budget
works; the plan is full and wrong in a way that named its own fault.** One
screenshot of the plan window, Westphalia, caps 3/3, rights on. «Довольно плохо,
объяснять пока не хочу, посмотри сам.»

- **«Локаций 48 (городских 6) · провинций 8 · мест 144 · товаров 27 · прав
  выдано 1 · зданий 140 в 48 локациях · лимиты 3/3 · кругов 41».** The
  thirty-third load's fault is closed: 140 of 144 places filled against 28
  before, every location used. The per-tier budget was the whole of it.
- **Six villages of Paderborner Plateau, rows 3 to 8, each given the same three
  buildings.** This is the fault the formula work then explained: every location
  of a province scores identically for a good — the bonus is the province's — so
  with nothing to stop it a good takes its best province whole and that
  province's locations come out clones of each other. The fix is the province
  divisor, unloaded.
- **One right across six towns.** All-or-nothing needed a bundle of three to fit
  a cap of three exactly. The owner settled it the same day: a right is granted
  to every town regardless. Unloaded.
- **27 goods of 47 placed**, which is the ground and not a fault: twenty goods
  have no candidate location in Westphalia at all.
- **No log asked for and none needed** — the header line carried the diagnosis,
  which is what it was added for.

### 2026-09 — `where_to_produce`, the thirty-sixth and thirty-seventh loads

Archived when the Wallachia test tripped the live log's budget. Both are closed:
the side-blind goods count and the lifted open pass, and the charter that was
granted forty-eight times before a right was scored on what a town could finish.

**2026-09-01 — `where_to_produce`, thirty-sixth load. The plan works and reads
right; three faults in the allocation, all named by the screenshots.** Two
screenshots, Westphalia whole and Münsterland alone. «Вау, оно кажется даже
адекватно работает… вся визуальная часть теперь работает как надо.»

- **Westphalia: «Локаций 48 (городских 7) · провинций 8 · мест 144 · товаров 27
  · норма 4 · прав выдано 7 · зданий 140 в 48 локациях · лимиты 3/3 · кругов
  40».** Rights on seven towns against one before, the quota reads 4, and the
  window and its rows are what he wanted.
- **Münsterland alone, five towns, one province: «мест 15 · товаров 13 · норма 1
  · прав выдано 5 · зданий 10 в 5 локациях».** Ten buildings in fifteen rooms,
  and the same goods standing in three of the five.
- **Fault one: «товаров» counts goods that cannot stand on this ground.**
  `_ordmax` is the better of the two sides, so a good whose only buildings are
  rural counts as makeable where every candidate is a town. Münsterland reported
  13 where at most 8 could ever be placed — **and the quota divides by that
  number**, so every good's share came out too small. `_ng<n>` and
  `_plan_scored` are counted on the side the location actually is now.
- **Fault two: the open pass lifted the quota instead of raising it**, so the
  first good down the list took every free room at once. That is the repetition
  in three of five towns. It raises every quota by one a round now, and the
  leftover ground fills in even layers.
- **Fault three: identical towns all take the same right.** Every location of a
  province scores the same, so four of five Münsterland towns took the masonry
  and glass charter and then held the same buildings. A right's score is divided
  by how often it has been granted now — the same shape as a good's province
  divisor. A better right still wins; a tie spreads.
- **Not a fault, and worth writing down: a right whose bundle the ground cannot
  make is granted anyway and comes out short.** Липпштадт took «Права на
  каменные и стекольные» and the plan put masonry, horses and spinning. Glass is
  the reason: every glass recipe wants sand, the province has none, so glass
  falls under `generate.fed_floor` and `glass_guild` also gates on
  `is_produced_in_location_market = goods:sand`. The mandatory-rights rule is
  doing what it was told; the ground refused the second half.

### 2026-09 — `where_to_produce`, the thirty-eighth load and the derivation

Archived when the Wallachia runs tripped the live log's budget. The four grounds
that tested the derived formula, and the day it was derived.

**2026-09-01 — `where_to_produce`, thirty-eighth load. Four tests of the derived
formula. «Как будто бы выглядит всё довольно хорошо и ты сделал большой рывок».**
Nothing that follows was re-run after being fixed.

- **Westphalia, 6 towns, caps 3/3: it holds up.** «Он ставит нужные домики к гор.
  правам и заполняет свободные ячейки… всем 5 выданы разные права.» All 144 rooms
  filled, 64 sweeps. The rights spread — the grant divisor works. At caps 3/4 it
  filled 153 of 153 and gave 9 rights.
- **One province alone, 5 locations: «все товары разные на каждую маленькую
  локацию, это выглядит правильно».** The band ordering doing what it is for.
- **Every location forced to a town in the first province, villages below:
  glass lands in the villages and never in the towns, while saltpetre and clay —
  which a village could dig — take the town slots.** Not a fault in itself: an
  RGO building declares `town = yes` as well, so the plan may put one there.
  **But it is a loss the formula can name.** A right carries a blanket
  `local_production_efficiency` penalty over the whole town, so a building that
  is not in the bundle takes the penalty and none of the bonus — the same
  building is strictly better in a town with no right. `_ord<n>` halves a
  right-holding town's spare slots now. Halved rather than forbidden: the
  penalty's value is a define `reference/` does not hold.
- **All of northern Germany, 416 locations and 1312 rooms: 970 buildings in 354
  locations, and «мод не справился досчитать всё как надо».** He is right, and
  the cause is the round guard. A sweep places at most one building per good per
  side, so 970 buildings over 32 goods needs thirty sweeps at the very least, and
  `PLAN_ROUNDS` was 12 — every pass was being cut off with work left.
  **Fixed twice over**: the guard is 50, and the tier ladder now runs in the last
  band only, which is twelve passes where there were thirty-three. The guard is
  free where a pass has no work, since the `while` leaves the moment a sweep adds
  nothing.
- **«Показано всего 150 локаций» is the window's row cap, not the count.**
  `PLAN_ROWS` is 150 and the datamodel is what costs, so the cap stays; the
  header line says «показано N» now, beside the 354 it really used.
- **A one-off spike and a short hitch on «Пересчитать» over that ground**,
  reported without complaint. Worth keeping in mind against the pass count.
- **The province ceiling is gone.** «Я не представляю ситуацию, когда бы я мог
  захотеть сменить значение этой строки с 0.» Under the formula the quota does
  that job and is derived rather than typed, so the setting, its alias, its
  default and both localizations are removed.
- **Known and deliberately left:** faults in the single-good side of the mod,
  which he named and set aside for a later session.

**Wallachia, the same day, and it answered the question the Westphalia test left
open.** «В 90% случаев мне спамятся права стекла или судостроительства. При этом
везде он отказывается ставить и стекло и судостроительный завод.» 44 locations,
26 of them towns, 26 rights — and nearly all of them the same two charters.

- **His guess at the mechanism was right, and the cause was a fix from the same
  day.** The substitution — where a granted right's good cannot stand, plant the
  input that would let it — was also being counted in the right's *score*. And
  `sand_pit` asks only that the location is not already a sand RGO, so it stands
  nearly everywhere. That made `royal_masonry_rights` the one charter in the game
  that is complete in every town, and a sand pit went in wherever the glass
  should have.
- **Two things fixed in the score.** A right is now scored on the goods the town
  can really make — planting an input is a consolation for a right already
  granted, never a reason to grant it. And a bundle is no longer averaged over
  its size: each good the town can make is worth 2000 plus its gain, each it
  cannot takes 1000 off. Averaging had made a one-good charter tie with a whole
  three-good one, and every two-good bundle beat a three-good one with a single
  gap — which is the other half of why the same two kept winning.
- **Unverified.** Neither fix has been in the game.

**2026-09-01 — `where_to_produce`, no run. The owner stated the objective, and
the formula was derived from it rather than assembled from rules.** Nothing here
has been in the game.

- **«Все товары которые можно произвести на выбранной земле — должны
  производиться, все. И не важно есть для них сырьё на этой земле или нет.»**
  Coverage is a hard constraint. The RGO bonus only ever decides *which* recipe a
  building runs, never whether it is built.
- **«Максимально возможная часть получит свои плюшки… но при этом товары будут
  все.»** That is maximise-subject-to-cover, and it has one answer;
  [`investigations/plan_formula.md`](investigations/plan_formula.md) is the
  derivation.
- **The currency changed, and this is the substance of it.** Measured: a recipe's
  ceiling runs from 2.00% to 10.00% and five goods are capped under 5%, so a raw
  bonus cannot compare across goods — and the old `worth ÷ the good's own best on
  this ground` compares worse, squeezing everything into 0.909–1.000. What
  compares is **`gain = bonus ÷ that recipe's ceiling`**, 0 to 1: how much of what
  this good could ever get here, it gets.
- **The ground is now dealt in descending bands of gain, across every good at
  once.** By the time a good that would gain a fifth reaches a location, the good
  that would have gained four fifths has taken it — the opportunity cost paid by
  the ordering rather than by asking every other good. That is «дальше не жиреть»
  and «выделить у менее вкусных провинций место под всё остальное», and it
  replaces the per-good round-robin that produced the chaos.
- **A covering pass was added and it is his first requirement**: after the bands,
  any good still at zero takes a free slot anywhere, at any gain.
- **`town_right_efficiency_penalty` is understood structurally at last.** A right
  is a `location_modifier` carrying `local_<good>_output_modifier` per bundle good
  *and* a blanket `local_production_efficiency` penalty on the whole town. So the
  owner was right — «права дают слишком жирный бонус и дебафят всё остальное» —
  and a town holding a right should hold its bundle and as little else. **The
  number is a define and is in no file `reference/` holds**: one `grep` on his
  install, and until then the discount is a direction without a size.
- **Cost:** the normalisation pass is gone with the old currency, which is 47
  ordered walks saved a run; the bands cost 32 tier passes where there were 7.
- **Not in the formula, and named by him:** a rural location per province set
  aside for food. «До этого мы пока ещё не дошли.»

**2026-09-01 — `where_to_produce`, thirty-seventh load. Every town took the same
charter and none of them got glass; the glass half is the game's answer, the
charter is ours.** Three screenshots, Westphalia with every location forced to a
town. «Всё ещё довольно плохая раскидка даже на глаз.»

- **«Локаций 48 (городских 48) · провинций 8 · мест 144 · товаров 28 · норма 3 ·
  прав выдано 48 · зданий 138 в 48 локациях · лимиты 3/3 · кругов 23».** The
  ground is 96% full and every town has a right, which is what the last two runs
  were for. **Bog iron went to the wetland locations and got room**, which is the
  scarcity tiers doing their job on the case he named.
- **A session said glass was unbuildable there. It was wrong, and the owner's
  screenshots settled it the same day** — the game offers a glass guild in
  Münster and a rural glassmaker in Dülmen, both age 0. The gate was read
  correctly (`is_produced_in_location_market = goods:sand`); what was never
  checked is whether the ground satisfies it, and nothing here can check that.
  Filed in `PITFALLS.md`. **So glass is placeable, in the few towns whose market
  has sand — and on this run a charter had already filled those.**
- **The fault is that the charter was granted anyway, forty-eight times.**
  `mason` is age 0 and stands in every town, so `royal_masonry_rights` scored
  around a thousand everywhere while its rival bundles scored what their own
  goods could reach — and the grant divisor added on the previous run was
  dividing a thousand against near-zero rivals, so it never turned the outcome
  over. **Six other charters are wholly age-0 buildable** — artisan, brewing,
  naval, textile, tooling, jewelry — and any of them would have filled the town.
- **Fixed: a right is scored by how much of it the town could actually finish.**
  Each bundle good the town can build adds a flat 2000 plus its own score;
  one it cannot adds nothing; the total is divided by the bundle's size. So the
  number is "what fraction of this charter would really go up here" first and
  "how good would it be" second, and a bundle a town can finish outranks a bigger
  one it cannot whatever the scores inside them. The grant divisor stays on top.
- **The empty slots follow from the same thing.** Дюльмен at 1 of 3 and three
  towns at 2 of 3 had all been given the masonry charter and could place only
  its masonry half.
- **Tried and reverted the same day: running the scarcest tiers before the
  charters.** It was built as the owner's own exception to a mandatory right, and
  it was the wrong reading of both the exception and the fault. Glass is *inside*
  `royal_masonry_rights`; it never needed to pre-empt the right, and letting
  every scarce good jump the queue contradicts what he had said several times —
  a right's buildings are mandatory. Rights are first again, whole bundle.
- **Built instead, and it is what he actually asked for:** where a granted
  right's good cannot stand, **the slot goes to the input that would make it
  possible**. Glass wants sand in the market and `sand_pit` stands at any rank
  asking only that the location is not already a sand RGO — so a town given
  `royal_masonry_rights` with no sand gets the pit, and the glass follows on the
  next plan. Derived rather than named: `generate.market_inputs` scans every
  `location_potential` in the game and finds exactly one usable pair,
  glass ← sand. The right's own score counts the good as reachable either way,
  so the substitution does not push the right down the list that needs it.

### 2026-09-01 — `where_to_produce`, the two Wallachia runs that ended the guessing

Moved out of the live log when it tripped its budget. Both are the run that
settled «гадать НИКОГДА не нужно» and the owner's rule about raw materials.

**2026-09-01 — `where_to_produce`, Wallachia a third time, and the run that
refuted every theory the session had.** Nothing was changed after it; the owner
called a halt: «я заебался впустую делать прогоны».

- **The charter spam survived every fix.** Tar and sand, tar and sand, down the
  whole list, and neither `royal_masonry_rights` nor `royal_naval_rights` ever
  getting its own goods.
- **The one observation that kills the market theory.** `glass_guild` and
  `rural_glassmaker` carry the **identical** `location_potential = {
  is_produced_in_location_market = goods:sand }`, and **glass appears in the
  villages while never appearing in the towns.** One condition cannot be true and
  false in the same market. So whatever stops town glass, it is not that gate —
  and four sessions' worth of explanation went with it.
- **He built a sand pit by hand and re-ran the plan: no change.** Expected — the
  plan reads no state of its own here — but worth recording as a fact rather than
  a guess.
- **Nothing was concluded, deliberately.** The next move is a probe, not a fifth
  theory. `pitfalls/diagnosis.md` has the episode and `CLAUDE.md` the rule that
  came out of it.
- **`can_build_building` stays.** His call: «не надо убирать то, из-за чего
  работает другое… скорее всего проблема в чём-то другом.» It is what keeps a
  stone quarry off flat ground.

**2026-09-01 — `where_to_produce`, Wallachia again. The charter spam survived the
scoring fix, and the owner struck out the rule underneath it.** «Убери вообще
любое упоминание этого правила.»

- **His rule, now the sharpest line in `investigations/plan_formula.md`:**
  «Отсутствие сырья не должно влиять на то будет ли домик существовать вообще или
  будет ли он как-то смещён в очереди из-за этого. Отсутствие сырья может влиять
  только на ВЫБОР метода производства в конкретном домике.»
- **Two rules removed under it.** The unfed divisor, which halved a recipe the
  ground feeds nothing on top of a gain already zero — the same fact counted
  twice. And the input substitution entirely, score *and* placement: where a
  granted right's good could not stand, the slot had been going to the market
  input that would unblock it. `generate.market_inputs` is gone with it.
- **His stone quarry question, checked: it does earn a bonus.** Lumber is an RGO
  and `crude_quarry_maintenance` tops out at 10%. **But seven recipes in the game
  can never earn one at all** — `lumber_mill`, `slave_market`, `shoen` quarries
  among them — and the divisor was punishing them for it twice over.
- **What no rule of ours can change, and it must not be confused with the
  above:** `can_build_building` is the *game* refusing a building. A glass guild
  may not stand until sand is in the market. That is not the ground failing to
  feed a recipe, and the plan cannot plan a building the game forbids — which is
  why a right is scored on the bundle a town can actually finish.
- **Unverified.** Whether the spam ends needs a run.

### 2026-09-02 — `where_to_produce`, the diagnosis's own first press

Moved out of the live log when it tripped its budget.

**2026-09-02 — `where_to_produce`, the diagnosis, first press. It named the cause
and found two faults in itself.** «Нажал "диагностика"… вроде появился такой
файлик» — the file was **0 bytes**; with the reader fixed the same press gave the
whole report.

- **The mod's half worked on the first load.** Button, CMF registration, callback,
  `bag_wtp_diag` and `debug_log` — none of them had ever run. `SELFTEST 1` came
  back `12345`, so every number below it is trustworthy.
- **The empty file was the reader's fault**, and it is a rule now: `diag.py` cut
  the game's line prefix with a regex written against a *guessed* shape, matched
  nothing, and the fold dropped every line it did not recognise
  (`pitfalls/diagnosis.md`).
- **The ground: 44 locations, 17 on the town side, 27 villages, 6 provinces, and
  it filled completely** — `placed=149 rooms=149`, no pass anywhere near the
  12-sweep guard (the worst was 7).
- **The cause of «no glass in towns», and it is one number.** A town-side method
  won on **3 of the 17 town-side locations** — for glass, and for cloth, tools,
  pottery, jewelry, beer, leather, paper, weaponry and eleven more. For the
  RGO-side goods it won on all 17: sand 17, masonry 17, fiber_crops 17, horses 16,
  tar 12. **Fourteen of those «towns» refuse manufacturing and accept only
  RGO buildings** — which is exactly «в городах я вижу много селитры, глины и
  прочего что можно добывать в сельских местностях».
- **Why they refuse it:** `glass_guild` is `town = yes, city = yes,
  megalopolis = yes` and `rural_glassmaker` is `rural_settlement = yes,
  town = no`. The game has four ranks and `bag_wtp_plan_is_town` admits a
  location either because the player ticked it or because its rank is not
  `rural_settlement` — and any non-rural rank takes a guild. So those fourteen
  are ticked villages. **The tick moves a location to the plan's town side and
  cannot move its rank in the game.**
- **The market gate is dead for good.** Both glass buildings carry the *identical*
  `is_produced_in_location_market = goods:sand`, and the rural one stood in all 27
  villages — so sand is in those markets. Twenty goods with no market condition at
  all were stopped in the same fourteen places.
- **The charter spam is the same fault one level up.** 17 rights for 17 towns:
  `royal_masonry_rights` in **9**, `royal_naval_rights` in **5**. In a ticked town
  masonry and tar can stand and glass and naval supplies cannot, so the bundle
  comes out half-made every time — and the `L` lines show it: «Район Арджеш …
  right=6 | clay, sand, masonry, tar».
- **And glass would lose anyway in the three real towns**: its best ordering there
  was `o=108` out of 1000, so it qualifies only in the last band, by which time
  those three have spent their four slots each on their own granted right.
- **Two faults in the dump, both fixed.** `[glass, masonry]` in a `debug_log`
  string is data-function syntax — the engine looked for a function called
  `glass`, failed, and cut `given=` onto a line of its own; round brackets now.
  And `error_log` writes into `debug.log` as well, so every headline arrived
  twice; one pointer in `error.log` now and the detail once.
- **Both remaining self-tests answered, and two retired.** A localization key as a
  `debug_log` message comes out as the key; `ROOT.GetName` and `SCOPE.GetName` do
  not exist. `debug_log_scopes = no` names the scope and is what every row uses.
  All of it in `research/engine.md`.
- **The one thing inferred rather than measured** — that those fourteen are ticked
  rather than some rank the mod does not know about — the next press prints
  outright: `ROOM` now carries how many of the town side are of town rank and how
  many the tick moved, and every `L` line carries `town_rank` and `forced_town`.

### Guild level caps, and why `where_to_produce` will never read them

Moved out of `investigations/town_rights.md` on 2026-09-02, when the owner
ruled the mod must never score building levels: «это число непостоянно и все
локации растут — высчитывать это полный абсурд». The arithmetic is kept
because it is what answers «flemish or royal textile» in prose, and that
answer is still live in the investigation.

### The cap is computable, unlike a building slot

`guild_max_level` in `common/script_values/building_caps.txt`:

    1 + development × 0.1 + population × 0.05 + (5 if city, 10 if megalopolis)

and `cloth_guild_max_level = guild_max_level + local_cloth_guild_building_levels`.
Every term is readable from a location in script. So a row for a level right can
honestly print **cap before → cap after**, which the mod could never do for
building slots (`mods/where_to_produce/CLAUDE.md`: the game exposes no slot count
at all — that stays true, a level cap is a different thing).

### 2026-09-02 — `where_to_produce`, the tick runs and the rank simulation

Moved out of the live log when it tripped its budget. Both entries are the
day the tick was settled as the rank; the rows they closed are in
`../SETTLED.md`.

**2026-09-02 — `where_to_produce`, three presses in one log, and the tick never
reverted.** He ran the two-press test written the same day and it answered on the
first reading. «Тумблеры не переключились никуда… потом я нажал пересчитать — и
тогда они переключились снова на города.»

- **The ticks he cleared stayed cleared.** Presses one and two walked the same 44
  locations of Wallachia — `ticks now set: town=0 village=0` both times, and
  `towns=3` live where the plan before them had counted 17. The clicks land and
  they hold; closing the window and changing the map area do nothing to them.
- **The third press walked 127 locations, and the fourteen ticks in it are not
  the ones he cleared.** They are Марошвашархей, Кездивашархей, Ковасна,
  Секейкерестур, Дьердьосентмиклош, Гёргеньсентимре, Секейудвархей,
  Шепшисентдьёрдь, Чиксереда, Бырлад, Аджуд, Кудалби, Фокшаны, Галац — every one
  of them outside the 44 he had on screen, ticked earlier in the session and
  never cleared. Widening the ground brought them into the plan for the first
  time; four slots each put them at the top of the window; and that is
  indistinguishable from a revert. **Wallachia's own rows all read
  `forced_town=0` in the same report.**
- **So it is not a fault, and the window is what should have said so.** A tick is
  a location variable and it outlives a save, so «clear the rows I can see» was
  never «clear them». A button was added the same day: «Сбросить пометки
  город/село», all five continents in one press, printing how many it cleared.
- **And the number he asked for, at last.** `GAIN` in all three presses: **79%,
  76% and 82% of placed buildings earn a bonus where they stand**, and the
  average building captures **73%, 74% and 78% of the ceiling its own recipe
  could ever reach.** The largest ground, the one with the ticks in it, is the
  best of the three on both counts — the rank simulation costs nothing in
  quality.
- **The ticks also make more of the ground**: 44 locations gave 149 rooms with
  them and 135 without, 17 towns against 3, 17 rights against 3.

**2026-09-02 — `where_to_produce`, the rank simulation, and it works.** «Открыл
план — на первый взгляд работает как надо. Города получают права и домики из
прав.» Transylvania and Wallachia together: 127 locations, 22 towns of which 8
are of town rank and 14 ticked, 19 provinces, 403 buildings in 403 rooms.

- **Both predictions from the previous entry came back right.** Glass `T … w`
  went from 3 of 17 to **22 of 22**; every made good now wins a town method in
  every town. And the charter spam is gone: 22 rights over **nine different
  ones**, the largest holding 3 towns where masonry held 9 of 17 before.
- **No pass came near the sweep guard** — the worst was 11 of 12, on the open
  pass. `RIGHT`, `ROOM` and the location rows all read cleanly with the round
  brackets.
- **The distribution, which he asked to have read for him.** 36 goods of the 38
  the ground can make got something, from 1 building to 20. **Nine goods take 20
  each and that is 45% of the ground**: coal, sand, beer, cloth, glass, jewelry,
  leather, masonry, pottery — every one of them makeable in all 127 locations, so
  every one reaches the quota. Twenty goods took 7 or fewer, all of them
  town-only, competing for 88 town slots the rights have first call on. **That is
  the formula working as written**; `plan_max`, his own per-good ceiling, is the
  lever and it is 0.
- **How much of it earns anything, and why the answer is not in this report.**
  `o=0` on a side means every placement there earns nothing, and those alone are
  38 buildings of 403 — a floor, not the figure, because `o` is a maximum. Two
  counters were added for it the same day (`GAIN fed=… gain_total=…`), one `if`
  a placement.
- **One bug he found and it is not diagnosed.** Toggles cleared to auto, replan,
  «всё вроде бы было окей» — then he left the window or changed the map area and
  **the ticks were back on the towns**. Nothing in the mod writes
  `bag_wtp_force_town` except the button on the row, so this is not guessable
  from the source. The `ROOM` line now counts both ticks over every walked
  location and reads them live, so one press of «Диагностика» — with no plan —
  separates «the variable came back» from «the window is drawing a stale state».
- **`Important assertion failed: (Getting player in synchronous state, likely to
  cause a desync)`** appears once, at the first `[…GetPlayer…]` the dump reads.
  It is how the dump reads every number, and it matters in multiplayer rather
  than here — recorded so the next session does not chase it.

### The rollback of 2026-09-02, from `investigations/plan_formula.md`

Moved here on 2026-09-03: every one of the three things it tracked as open
is built and struck through, and the section is history rather than state.
The rules it carries that outlive the code — the owner's raw-material rule,
and the observation that killed the market theory — are quoted where they
are used.

## The rollback of 2026-09-02, and what survives it

**The tree is back at the build of the thirty-eighth load** — the four tests the
owner called «большой рывок», and the first time the spread of goods over a whole
ground looked to him the way he had meant it: «именно в этом коммите я
почувствовал, что мод выглядит так, как я его задумывал». Everything built above
it was undone at his word — «лучше мы решим уже на том моменте основную мучающую
проблему, чем будем делать это после того как накрутили сверху множество других
неработающих правок» — so everything above in this file is the code again,
exactly. The run itself is in [`../archive/testlog_2026-08.md`](testlog_2026-08.md).

**Open at the rollback, and he named all of it himself. Three of the five were
answered on 2026-09-02 when he asked for them by name:**

- ~~**a big ground does not finish.**~~ All of northern Germany: 970 buildings in
  354 of 416 locations, «мод не справился досчитать всё как надо». The cause was
  measured afterwards and the arithmetic is not in doubt — a sweep places at most
  one building per good per side, so 970 buildings over 32 goods needs thirty
  sweeps at the least, and `PLAN_ROUNDS` was 12. **It is 50, and the tier ladder
  runs in the last band only** — twelve passes where there were thirty-three, and
  the passes saved are what pay for the sweeps. Not run;
- ~~**«показано всего 150 локаций»**~~ was `PLAN_ROWS`, the window's row cap, not
  the count of what the plan used: nothing was lost, only undrawn. **The rows are
  ranked whole and drawn a page at a time now** — `PLAN_RANKED` locations keep
  their place and the page they fall on, the datamodel still holds one page of
  `PLAN_ROWS`, and two buttons under the summary line walk them. Not run;
- ~~**the province ceiling setting**~~ is gone — setting, alias, default, both
  localizations and its gate in the allocator: «я не представляю ситуацию, когда
  бы я мог захотеть сменить значение этой строки с 0». Under this formula the
  quota does that job and is derived rather than typed. Not run;
- **the scarce claim first only in the last band now**, and he named the cost on
  2026-09-03: «если всем товарам мод попытается выделить по 20 мест, он должен
  проверить хватит ли болотных локаций для железа, прежде чем забивать эти
  локации чем-то другим». Moving the tier ladder into band 0 bought the round
  guard twelve passes instead of thirty-three, and it spent exactly this. **The
  rights have no such ladder at all** — they are dealt town by town in walk
  order, so a right only two towns on the map can serve has no claim on them;
- **a one-off spike and a short hitch on «Пересчитать»** over that ground,
  reported without complaint: thirty-three passes and ninety-eight sweeps a plan.
  The pass count is twelve now and the guard is what grew, so this wants watching
  on the next big ground rather than calling fixed;
- **the symptom that is the whole of the job.** Force a province to towns and
  glass lands in the villages below and never in those towns, while saltpetre and
  clay — which a village could dig — take the town slots. And the glass-and-
  masonry charter is handed out over and over.

**What the undone runs still know, and no run should buy twice:**

- **The owner's rule about raw materials**, 2026-09-01. A decision, not a build,
  so it outlives the code that carried it:
  > Отсутствие сырья не должно влиять на то будет ли домик существовать вообще
  > или будет ли он как-то смещён в очереди из-за этого. Отсутствие сырья может
  > влиять только на ВЫБОР метода производства в конкретном домике.

  ~~**`UNFED_PENALTY` above breaks it**~~ — **removed 2026-09-02 at his word.**
  A recipe that missed `fed_floor` had its score halved on top of a `gain` that
  already *is* how much of its ceiling the ground pays: the same fact counted
  twice, and it moved the building in the queue for want of raw materials, which
  is exactly what he forbade. It had been left standing as a named suspect for the
  charter symptom; that symptom was settled otherwise (the tick is the rank,
  `../SETTLED.md`), so it was being kept for nothing. **`fed_floor` stays** — it
  chooses which method a building runs, which is the half of the rule he
  affirmed: «может влиять только на ВЫБОР метода производства». It is also not a
  gate: the plan keeps an unfloored twin of every side.
- **The observation that killed the market theory**, thirty-ninth load. It is
  about the game, so it stands whatever our code does: `glass_guild` and
  `rural_glassmaker` carry the **identical** `location_potential = {
  is_produced_in_location_market = goods:sand }`, and glass appears in the
  villages while never appearing in the towns. One condition is not true and false
  in the same market, so the market gate is not what stops town glass — and four
  sessions' worth of explanation went with it
  ([`../pitfalls/diagnosis.md`](../pitfalls/diagnosis.md)).
- **What was built above the rollback and is still not in the tree.** The three
  that answered measurements he made himself came back on 2026-09-02 at his
  request, and are struck through above. **The rest stay out**, because they were
  aimed at a cause nobody had named: a right-holding town's spare slots halved,
  the input substitution (sand planted where a charter wanted glass, which spammed
  a realm with charters), the rescored rights, and `UNFED_PENALTY`'s own removal.

### 2026-09-02 — `where_to_produce`, the two runs the province divisor cost

Moved out of the live log when it tripped its budget. Both are superseded:
the province divisor they diagnose was removed whole on 2026-09-03, and the
rule that replaced it is in `../investigations/plan_formula.md`.

**2026-09-02 — `where_to_produce`, the province divisor in game. It works, and
Goslar still says no.** Same 416 locations, «на конец», plus a second press over
one province with every location ticked to a town.

- **The divisor does what it was changed for.** The rights came out
  18/12/10/10/4/3/2/1/1 where they had been 8/8/7/7/7/6/6/6/6 — the ground
  deciding instead of a round robin. And the one-province press gave **five towns
  five different rights**, which is the Münsterland fault it was built for, held.
  1309 of 1309 rooms, no pass near the guard.
- **Goslar took `royal_book_rights` instead of the jewelry it should have.** Harz
  has one town, so its divisor is 1 and the ground decides alone — which means
  the score itself now says books beat jewelry there. The report cannot say why:
  it prints the winner and never the field it beat. `paper o=1000, dyes o=952,
  books o=615` against `jewelry o=909`, and a three-good bundle is averaged, so
  the two land within a hundred of each other — **but those are bests over the
  whole ground, not Harz's numbers.**
- **So the probe, not a fifth theory.** `WTP RQ` prints every right's bundle
  score for each town, before the province divisor, and `tools/diag.py` folds it
  under that town's own line. A one-good right reads as `2000 + that good's
  gain`, so the line gives jewelry's gain in Harz directly. One press answers it.
- **Two of his rulings are in the build with it.** `hand_cannon_guild` and
  `cannon_maker` are always available (`generate.ALWAYS_AVAILABLE`) — both carry
  only rank gates in the game files, so nothing else is being waved through — and
  a right that grants guild *levels* is now scored on the goods it favours like
  any other, which admits `flemish_cloth_industries_right` and nothing else.

**2026-09-02 — `where_to_produce`, the same ground planned «на конец», and one
town of it named the fault the numbers had been hiding.** «В этот самый город мод
выделил права на инструменты. Почему?» Goslar, the only town of Harz — a province
with silver in it — took `royal_tooling_rights`, where iron is what a tools mill
eats and silver is what a jewelry guild eats.

- **He is right and the cause is arithmetic, not a guess.** A right scores
  `(2000 a reachable good + its gain, gain ≤ 1000) ÷ bundle size ÷ (1 + times
  already granted)`, and the divisor counted **the whole map**. A right never
  granted scores 2000–3000; granted once, at most 1500. **The ranges do not
  overlap**, so a right handed out anywhere could never again win on merit. The
  rights were dealt round robin and the ground only broke ties inside one turn.
- **The distribution is the fingerprint of it**: 8, 8, 7, 7, 7, 6, 6, 6, 6 over
  61 towns and 9 rights, on both this run and the «сейчас» one. Too even to be
  the ground.
- **The fix is the divisor the goods already have**: `_rp<k>` counts the grants
  **in this province**. The fault it was built for — five towns of Münsterland
  all taking the masonry charter — is inside one province, and so is the divisor
  now. Harz has one town, so its divisor is always 1 and the ground decides
  alone. Not run.
- **Jewelry really is what silver feeds.** All twelve `jewelry_guild` methods are
  a base of gold, silver or copper plus one enhancement; a province with silver
  and no gems pays 8.7% of a 10% ceiling. Tools' best anywhere on this ground was
  `o=399`. Nothing about Harz suited tooling.
- **The end-game plan itself is sound**: 1309 buildings in 1309 rooms, 36 of 38
  goods placed, no pass near the guard, 113 sweeps.
- **`GAIN fed=952 gain_total=900864`** — 73%, and among the fed 946 of 1000. The
  unfed divisor's removal cannot be read off this: it is the «на конец» plan and
  the run before it was «сейчас».

### 2026-09-02 — `where_to_produce`, the first Münster run

Moved out of the live log when it tripped its budget. The three fixes it
confirmed are long settled; what it is still quoted for is the 95% figure —
a building that earns anything captures 948 of 1000 of its ceiling.

**2026-09-02 — `where_to_produce`, Münster and all of northern Germany. The three
fixes work, and the number the mod exists for is 95%.** «Вроде как всё
заполняется хорошо… как будто бы основные функции мод теперь выполняет как надо.»
416 locations, 74 provinces, 61 towns, no ticks set anywhere.

- **All three fixes confirmed in one press.** 1309 buildings in 1309 rooms —
  100%, against 970 of 1312 on the same ground before. **No pass came near the
  guard**: the worst was 31 of 50, and the twelve passes are the ones the
  generator lists. The page bar and the removed province ceiling were on screen
  and neither drew a remark.
- **Selection quality, and it is the answer to «идеально ли он работает».**
  `GAIN fed=968 of placed=1309 gain_total=918033`. 74% of placed buildings earn
  a bonus where they stand — but **the ones that do capture 948 of 1000 of their
  own recipe's ceiling** (918033÷968). The 26% that earn nothing are the price of
  the covering constraint and of filling the ground, both of which he asked for.
  The overall 70.1% is those two numbers mixed, and is the less useful of them.
- **The distribution is the ground's arithmetic, not the formula's.** 355 of 416
  locations are villages and only 23 goods have a village side at all, so the ten
  goods makeable in all 355 take ~66 each and half the ground between them, while
  town-only goods share 244 slots of which the rights claim ~135. Town slots came
  out exactly 244 = 61×4 and village 1065 = 355×3, so nothing was left on the
  table anywhere.
- **Rights: 61 grants over 61 towns, 9 distinct, the largest 8.** No charter
  spam. `constantinopolitan_silk` (no silk here) and both Scandinavian ones went
  to 0, correctly.
- **Two faults this run makes visible, neither of them new.**
  `royal_weaponry_rights` was granted twice on a ground where cannons and
  firearms have no advance, so those towns carry a charter that delivers one good
  of three and the location-wide penalty for all of it — the rescored bundle
  (2000 a makeable good, −1000 a gap) is the fix and is one of the things still
  out of the tree. And **the mod page still says a right is all-or-nothing**,
  which stopped being true on 2026-09-01 at his own word: `plan_right_fits_<k>`
  is an `OR`.
- **Nine goods scored 0 for want of an advance** — lumber, silk, silver, sugar,
  tobacco, cotton, incense, ivory, wild game — so «сейчас» covers 32 of 47. That
  is the age and not the plan; «В конце» is the button that answers for them.

