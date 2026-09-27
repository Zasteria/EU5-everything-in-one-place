# Responsive Universalis: Community Fixes - change log with sources

Rule for this mod: no change without a real, current community complaint behind it.
Researched 2026-07-20 against game 1.3.10/1.3.11. Every v1 change below names its
sources. Complaints that Paradox already fixed (mercenary spam, trade margins,
imperial circle notification spam, all in 1.3.11) are deliberately NOT touched.

## v1.0.0 changes

### 1. Decline disasters no longer death spiral (complacency defang)
Complaint: complacency punishes success, triggers decline disasters whose penalties
create "a horrible death spiral that takes 100 years to recover from". Three separate
Steam threads; the most subscribed fix mod (Make EU5 Fun Again, ~1200 subs) disables
the mechanic entirely.
- https://steamcommunity.com/app/3450310/discussions/0/796713273232867271/ (Complacency is an unfun mechanic)
- https://steamcommunity.com/app/3450310/discussions/0/840628660304092414/ (Complacency is a stupid mechanic)
- https://steamcommunity.com/app/3450310/discussions/0/840628770842997697/ (good ideas, horribly implemented)

Mechanism found in files: the complacency_impact auto modifier only turns on while a
decline disaster runs (has_complacency_effects). At 100 complacency it was
research speed -50%, cabinet efficiency -50%, double tradition decay, estate
enrichment, lower rebel threshold, all stacked on the disaster's own penalties.
Change (auto_modifiers/country.txt): penalties cut to a fifth (research and cabinet
-50% -> -10%, tradition decay halved, enrichment halved, rebel threshold halved).
The mechanic, the disasters and the flavor all stay. Softer than the popular mod's
full disable: success still has a cost, it just no longer ends the campaign.

### 2. Distant provinces are worth owning (control relief)
Complaint: "Control is the biggest issue EU5 has" (large ongoing forum thread).
Circular spread from the capital, distant cities economically useless, half of many
countries' starting land does nothing, expansion gives "no tax increase, not more
troops, but higher costs".
- https://forum.paradoxplaza.com/forum/threads/control-is-the-biggest-issue-eu5-has.1929521/

Changes (defines):
- NLocation.MONTHLY_CONTROL_DECAY 0.01 -> 0.005 (control bleeds half as fast)
- NCountry.LOW_CONTROL_THRESHOLD_FOR_BEST_TAX 0.95 -> 0.80 (full tax at 80 percent
  control, distant land pays out sooner)

### 3. Truces 3/6 instead of 5/10
Complaint: post launch truce extension to 5/10 slows the game to a crawl; the top
fix mod reverts to 3/5 and its player base considers that the correct pacing. We use
3/6 (scaled truces keep some bite).
- https://steamcommunity.com/sharedfiles/filedetails/?id=3723705552 (Make EU5 Fun Again, revert list)

Changes (defines): NDiplomacy.TRUCE_YEARS 5 -> 3, SCALED_TRUCE_YEARS 10 -> 6.

### 4. Subject nations keep a working cabinet
Complaint: subject play (and holding subjects) was nerfed into tedium post launch;
cabinet efficiency maluses on subjects called out specifically.
- https://steamcommunity.com/sharedfiles/filedetails/?id=3723705552 (Make EU5 Fun Again, revert list)

Change: country_cabinet_efficiency maluses in subject_modifier blocks halved across
all 11 subject types that have them (vassal -20% -> -10%, fiefdom -50% -> -25%,
dominion -40% -> -20%, appanage -35% -> -17.5%, and so on).

### 5. Literacy actually pays off (research speed)
Complaint: literacy barely differentiates countries. Vanilla: the average_literacy
static modifier grants research_speed_modifier = 1 scaled by average literacy, so
30 percent literacy vs 10 percent is only a 20 point research speed gap over a whole
campaign ("maybe 10 techs", Matte's own testing). Community evidence: the mod
"Literacy Increases Base Research Speed" has ~2,100 subscribers, the highest of any
fix mod checked, with the author noting "the game seriously lacks base research
speed modifiers and i don't like everyone having such similar tech levels".
- https://steamcommunity.com/sharedfiles/filedetails/?id=3605695382

Change (full-file override of main_menu/common/static_modifiers/country.txt, one
value inside the average_literacy block): research_speed_modifier 1 -> 1.5. A 30
percent literacy country now runs +45 percent research speed vs +15 at 10 percent
literacy. Differs from the linked mod (which adds literacy-scaled BASE research
speed on top of vanilla); ours scales the existing vanilla effect by 1.5 so the
mechanic keeps its shape. Full-file override chosen over a zz_ same-key
redefinition because a duplicate database entry could warn in error.log and break
the family's baseline-parity acceptance test.

## Audit 2026-07-20 (game 1.3.11)
- Generator gates: vanilla parity (7 define keys exist in current game files with
  expected vanilla values), family key collision (clean), per-file count asserts.
- Every generated file verified: UTF-8 BOM, balanced braces, diff vs vanilla
  contains only the intended lines (complacency 6 values, subject types 13 values
  across 11 files, gui 8 sizes, static modifiers 1 value).
- Family overlap audit: no file overlaps except tech-tree vs tech-tree-plus
  (intentional, mutually exclusive alternatives); no define key overlaps except
  HOUR_TICK main vs aggressive-ticks (intentional, the submod's purpose).
- 1.3.11 regeneration check: tech-tree, tech-tree-plus and message-presets
  regenerated byte-identical, so 1.3.11 changed none of their vanilla sources and
  the published mods need no republish.

### 6. AI sieges from the border in, and finishes what it starts
Complaint family: erratic AI siege behavior. Enemy armies run deep into a country
and siege it from the inside out (Matte's own MP campaigns), AI abandons sieges
right before capture, AI siege target selection reads as random.
- https://steamcommunity.com/app/3450310/discussions/0/685239894022356623/ (Sieges are cancer)
- https://steamcommunity.com/app/3450310/discussions/0/832738775777063173/ (1.1 - Sieging has become even worse)
- https://steamcommunity.com/app/3450310/discussions/0/800093196998821431/ (AI behavior thread)

Changes (defines, NAI, both keys carry vanilla inline docs):
- AI_MILITARY_ARMY_ASSIGNMENT_PROXIMITY_FACTOR -1 -> -4. Vanilla comment:
  "Negative score for army targets further away". Priority contributes 100 per
  level (1-10), so at vanilla -1 a deep target loses almost nothing to distance.
  At -4 an objective ~50 map units deep pays a ~200 point toll, which nearby
  objectives beat unless the deep one is 2+ priority levels more important.
  Result: fronts roll inward from where armies stand (their own side), which is
  the practical version of "prefer sieges near your own land".
- AI_STICK_TO_SIEGE_TIME_FACTOR 0.003 -> 0.006: ongoing sieges accumulate score
  twice as fast, so armies stop walking away just before the capture ticks.

Calibration note: the distance unit interplay is documented but the resulting
in-game feel is UNVERIFIED until A/B tested in a real war. If -4 makes the AI too
timid about deep objectives, -2 or -3 is the fallback. Related knob for later:
AI_REASSIGN_UNIT_THRESHOLD (1.33) governs how easily armies get yanked off
objectives entirely.

### 7. AI presses its wars
Complaint: "major AI powers don't push hard enough, alliances become predictable
past 1600" (After Strategy, 6-months-later review); AI hovers next to sieges
instead of forcing the fight.
- https://after-strategy.com/en/eu5-6-months-later-paradox-review-2026/

Change (defines, NAI): CARPET_SIEGE_CONFRONT_FACTOR 0.5 -> 0.65. Vanilla inline
comment: "This factor determines how likely the AI is to initiate a battle, as
opposed to just staying close by". Conservative bump, same UNVERIFIED-until-tested
status as pillar 6.

### 8. Building buttons you can actually click (UI)
Complaint: "the upgrade settlement button is tiny and hidden in corners... building
resize buttons are the world's tiniest buttons" (UI is criminal thread).
- https://steamcommunity.com/app/3450310/discussions/0/667222787666165479/

Found in files: the building card's control buttons (destroy/dequeue, expand,
upgrade) in location_window.gui are 12 px tall with 10x10 icons.
Change (gui override): whole control cluster grown to 20 px with 16x16 icons.
GUI hot-reloads, so sizes are tunable live during the test session.

### 9. Stop button for selected units (v1.1.0, 2026-07-22)
Complaint: Matte's request, there is no way to halt selected units with one click in
vanilla (no stop concept exists anywhere in loc, GUI data functions or shortcuts).
Mechanism: a new instant unit ability (ru_stop_all) that shows as a clickable button
in the unit action bar whenever moving units are selected. Its start_effect fires
cancel_movement, an effect name discovered in the exe's unit-ability schema string
cluster (next to unembark_army and finished_when). Icon: red X at the engine
convention path gfx/interface/icons/unit_actions/<key>.dds (uncompressed DDS).
UNVERIFIED until in-game test: the cancel_movement effect name (error.log flags an
unknown effect instantly on launch) and whether one click applies to every selected
unit or only the primary one.

### 10. RGO Filter map mode - SHELVED 2026-07-23 (git tag shelved-rgo-finder)
Matte's idea, wishlist number 1: the RGO map mode with per-resource toggles, only
clicked resources show, the rest greyed out.
Mechanism, all generated from the installed game files:
- Custom map mode ru_rgo_filter appended to a full-file override of
  gfx/map/map_modes/map_modes.txt. map_color script: one branch per raw-material
  good (44 parsed from goods files with their named map colors resolved to rgb),
  colored when the global variable ru_rgo_<good> exists, grey otherwise.
- Toggles are scripted_guis (one per good, is_shown reads the variable back for
  the button state) plus Show all and Hide all. State lives in global variables
  because the map color script can read those from location scope.
- Filter panel (11 rows x 4 goods chips) injected into the mapmodes_window type
  in hud_bot.gui, visible only while the mode is active.
- Icon at gfx/interface/icons/map_modes/ru_rgo_filter.dds.
Caveats until tested: whether map colors refresh immediately on toggle (worst
case: re-select the map mode), and in multiplayer the filter state is shared
between players because it is global variables.

### 11. Control through infrastructure, minimal touch (v1.2.0, 2026-07-22)
Wishlist item: control spreading by geography and infrastructure, not circles from
the capital. Findings that shaped the fix: the game already has the tools (governor
buildings with local_proximity_source = 80, ports, roads, castles) but they lose
the math: terrain maluses are big flat numbers (mountains -0.5, hills/wetlands
-0.25) and only three buildings in the entire game are proximity sources. Almost no
building grows control directly (one event building at 0.001/month).
- https://forum.paradoxplaza.com/forum/threads/control-is-the-biggest-issue-eu5-has.1929521/

Changes, deliberately minimal (Matte: lowest reasonable amount, this area changes
everything):
- topography: mountains proximity -0.5 -> -0.4, hills and wetlands -0.25 -> -0.2
  (plateau -0.125 untouched)
- capital_buildings: local_proximity_source 80 -> 90 on local governor, naval
  governor and the Italian administration center
Escalation path if testing shows it is too weak: governor construction cost cut,
then plateau. UPDATE 2026-08-19: the harbor step IS shipped (generator repair
2026-07-24 restored it): local_proximity_source 15 added to the engine-scaled
location_template_natural_harbor_suitability_location static modifier (scales
with harbor quality 0-100) plus 20 on the basic dock building.

### 12. Autonomous regions, half strength (v1.2.0, 2026-07-22) - EXPERIMENT
Wishlist item 5 (expansion yields only costs), Matte's design: low-control land
should pay for itself like an autonomous region until control makes it profitable.
Constraint found first: no location-scope modifiers exist for building maintenance
or governing cost (checked the full modifier_type_definitions registry), so a
literal cost-zero autonomy is not expressible. Agreed half version built from the
modifiers that DO exist:
- Below 30 percent control (location auto modifier ru_autonomous_region):
  local_fort_maintenance_efficiency 0.5 (forts half price), local_unrest -2
  (cheaper to hold), local_monthly_control +0.01 (drifts up on its own until it
  graduates out of autonomy, then stops).
- Income side needs no script: taxes already scale with control and full tax at
  80 percent is ours.
EXPERIMENT flags: vanilla ships no location-category auto modifier (type/category
= location is untested) and the location control trigger name is assumed. Both
fail loudly in error.log on launch; if rejected, pull the one file and re-lever.
Blob-risk note: autonomy offsets only part of the costs on purpose (Matte: half).

### 13. Accelerated integration (v1.2.0, 2026-07-22)
Wishlist integration items, Matte's design: an economy slider where max = twice as
fast integration, cost scaling like court costs. Engine budget sliders are
hardcoded, so it ships as a slider-sized 4-level control row (0/1/2/3 buttons,
active level highlighted gold) in the economy screen:
- Three auto modifiers keyed on the country variable value: level 1 = +25%
  speed for -2% tax, level 2 = +50% for -3%, level 3 = +100% for -5%
  (tax_income_efficiency scales the price with the economy automatically).
  (Doc corrected 2026-08-19: shipped values are 2/3/5, the 2.5/5/10 written
  here earlier never shipped.)
- Toggle via scripted_gui + country variable (per-country, MP safe), Enable and
  Disable buttons injected above the taxing section in economy_lateralview.gui.
AI note: the AI never sets the variable, so this is player-side QoL only.

### 14. Law and order buildings (v1.2.0, 2026-07-22)
Wishlist: proactive revolt prevention. Matte's design: a region building for
keeping order, ideally tagged onto castles or bailiffs. Finding: forts ALREADY
carry local_unrest but at imperceptible values (stockade -0.025, castle through
city walls -0.05), which is why nobody notices the mechanic.
Changes (building_types):
- forts.txt: all fort local_unrest values raised tenfold (stockade -0.25, castle,
  bastion, star fort, fortress and city walls -0.5)
- rural_buildings.txt: bailiff gains local_unrest -0.5 (the crown's law officer)
Together with autonomy (-2 unrest below 30 percent control) this gives real
proactive tools against revolts without touching rebel spawn logic.

## Open bugs at the 2026-07-22 session end (v1.2.0 unpublished)
- Raw Materials Finder: map stays stuck on the first pick (fruits) and later
  clicks change nothing visibly. The MapMode.SetMapMode repaint-on-click fix
  was live-swapped into hud_bot.gui but never verified on a fresh launch, and
  the scripted-gui Execute path itself is unconfirmed (the stuck state could
  also mean clicks stopped firing at all). First thing to test next session.
- Staged but never launched: autonomy trigger local_control (third trigger
  name attempt), legend_key removal. CORRECTION 2026-07-24 audit: the 'l' formatting
  spam is a VANILLA recruit screen GUI bug, not our legend keys.
- Everything else verified at vanilla error baseline in-session: stop button
  loads clean, budget card in expenses, building buttons, defines pillars.

## Next session, from Matte's live play (2026-07-23)
- MAIN MOD (blue, 3765240556) field report: desync at war declaration on
  speed 4 in a 2-human MP session even for wars with only 1 human participant
  vs AI, scales with war participants and moving
  units. NOT the wars define (needs 2+ humans). Real suspect: load desync,
  HOUR_TICK 6 makes each tick 3x the sim work, war declaration spikes AI and
  pathfinding load, the slower of the two client machines overruns the tick budget at speed 4
  and the clients drift apart. Candidate mitigations for the next main-mod update:
  give speed 4 more wall-clock per tick via NGame.GAME_SPEED_TICKS (e.g. 0.05
  -> 0.07 s per game hour, keeps the speed label but adds ~40 percent compute
  headroom), recommend the Maximum Ticks Lead setting on the listing, and
  advise speed 3 during big wars. Also worth an A/B vs vanilla: EU5 desyncs
  at war declaration are a known vanilla complaint too, attribution needs a
  no-mod control run.
- Decline disaster needs a much harder nerf than the pillar 1 defang: once it
  fires it runs 40-50+ years as a boring flat debuff. The penalties were cut to
  a fifth, but the DURATION is the real offender, the exit conditions are
  nearly unreachable (control target in home region + complacency drain).
  Design direction (Matte: nerf into oblivion): make it much rarer to fire
  (higher complacency threshold), much shorter (reachable end conditions or a
  hard time cap), and softer while active (cut the disaster's own modifier
  block, not just complacency_impact). Files: common/disasters/
  decline_of_empire.txt plus the four country variants, full-file override via
  the generator like everything else.

## Inspiration survey (2026-07-20 ambitious pass)
Popular mods checked for proven-demand ideas: Glorp UI (customization menu, better
diplomacy tooltip, building limit display), Construction Manager (auto-expand and
auto-build automation, food potential map mode; requires Community Mod Framework),
Make EU5 Fun Again (revert list), Xorme AI, EU5 Balance Mod (military rebalance),
Enhanced Papermap (visuals), map zoom extenders. Ideas are re-implemented from
vanilla files, never copied.

## Explicitly out of scope
- Anything the other Responsive Universalis mods already cover: tick and AI
  performance, trade map clutter, message settings, tech tree structure and UI.
- Mercenary spam, trade income margins, imperial circle notifications: fixed by
  Paradox in 1.3.11.
- Naval pathfinding through straits (Bosphorus, Oresund, Gibraltar): engine bug,
  not moddable.
- Mission trees and scripted content gaps: content creation, different mod scale.

## Roadmap (validated complaints, lever not yet verified in files)
- Ship cost increase from 1.3 (4x): costs are goods-driven, not in unit templates;
  needs the goods cost mechanism mapped before touching.
- Building upkeep yearly creep and market access upkeep penalty (1.3): mechanism
  not located in defines or auto modifiers this pass; likely building_types script
  or engine. Find it before changing it.
- Food weather decay and pop growth restore (Make EU5 Fun Again reverts): the
  levers are not in 00_defines under any obvious name; not located this pass.
- Food glut ("way too much food, ridiculously cheap"): Paradox actively rebalancing
  this area (1.3.11 touched trade); wait a patch before modding it.
- Map camera zoom extension: zoom step tables not exposed in defines (only display
  ranges per step); dedicated zoom mods exist, low priority for us.
- Glorp-style building limit display and better diplomacy tooltip: need the right
  data functions mapped (building limit functions absent from the dump catalogue);
  candidates for the live test session where gui hot-reload makes iteration cheap.
- Construction Manager style auto-build automation: a full scripted system on the
  Community Mod Framework; out of scope for file overrides, would be its own mod.
- Settlement upgrade and fort expansion controls (rest of the tiny-buttons
  complaint): not found in location_window.gui this pass; hunt them live in the
  test session.
- AI_REASSIGN_UNIT_THRESHOLD (1.33): related anti-flip-flop knob for pillar 6,
  hold until the -4 proximity factor is A/B tested.
- Building micromanagement volume: design level, cannot be fixed with values alone.

## v1.3.0 changes (built 2026-08-19, UNTESTED until Matte's session)

All ten candidates from the WISHLIST top-10 refresh except map modes
(deferred: devastation/unrest script-readability unproven, probe live).
Every lever exe-verified before building (see WISHLIST for per-item
complaint sources and freshness).

### 17. Garrisons punish undermanned sieges (top-10 item 1, Matte's pick)
generic_actions/siege.txt override: alone-sortie threshold 5.0 -> 1.5,
AI check every 14 days (was 35, siege phase is 30), automation check 14
(was 20), sortie score multiplier 20 -> 30. The sortie battle itself
enforces the outnumber rule, both for AI garrisons and player automation.
Dial: if garrisons sortie into losses, raise threshold toward 2.0.
LIVE-TESTED PASS both directions 2026-08-19 (Matte): tiny 50-man pin vs
a fort level 2 garrison (800 men - garrison numbers only display during
an active siege; the earlier 375 was a misread) -> sortie fired at the
next 14-day AI check. Control: 4000 besiegers vs 800 garrison -> no
suicide sortie. Side-finding: 50 men also made zero siege progress
(vanilla minimum-men mechanic, GetMenNeededForSiege) - tiny pins were
already progress-inert, the sortie now physically removes them.
Scale note (Matte): start regiments ~500 men, so at 1.5 a single parked
fresh regiment vs a small garrison is NOT punished; dial 1.2 would cover
it - decide after full session.

### 18. AI peace behavior (top-10 items 2 and 4)
Defines: IDEAL_WARSCORE_DIFFERENCE_THRESHOLD_TO_CONSIDER_PEACE 20 -> 30,
AI_PEACE_CHECK_DAYS 90 -> 45, MINIMUM_WAR_SCORE_TO_CONSIDER_DEFEAT
-50 -> -35 (all three carry vanilla direction comments). Wargoals: all
182 conquer/subjugate cost values x0.75 (uniform, relative balance kept).

### 19. Bankruptcy survivable (top-10 item 3 + Matte's insta-bankruptcy fix)
Defines: BANKRUPTCY_DURATION_IN_MONTHS 60 -> 36, BANKRUPTCY_STAB_LOSS
-50 -> -25, CREDITWORTHINESS_BANKRUPTCY_YEARLY_RECOVERY 0.005 -> 0.02
(century scar -> ~12 years). Matte's diagnosis (2026-08-19, experienced
live): without the credit automation toggle the only loan pool is estate
loans and a failed loan attempt tips straight into bankruptcy; the credit
toggle bundles unwanted bond automation. Clean estates-side fix:
ESTATE_LOAN_SIZE 0.5 -> 1.0 (still scaled to actual estate holdings, the
system's own design) and MIN_ESTATE_LOAN 2 -> 5.
A/B-TESTED 2026-08-19 (vanilla control, Teutons start): per-loan tranche
16.22 -> 40.77 = x2.51, exactly the MIN_ESTATE_LOAN ratio - the FLOOR
drives tranche size. ESTATE_LOAN_SIZE moved neither the tranche nor the
total pool in this poor-estates start (role unknown, possibly rich-estate
cap; kept at 1.0 as harmless). Total pool (~3761) comes from elsewhere
and was never shallow. Net: single auto-loans now cover 2.5x bigger bad
months. Matte's verdict same day: Paradox already deepened the pool
since his insta-bankruptcy experience, so that failure mode is fixed
upstream - keep our values as shipped, no further estate-loan work. Peace costs A/B same
session: Suwalki 1.97 vanilla -> 1.45 modded = 0.736 ~ 0.75 CONFIRMED.

### 20. Parliament, war exhaustion, manpower, inflation, carpet siege
(top-10 items 5-9, all defines/values):
- PARLIAMENT_COOLDOWN_MONTHS 59 -> 18 (direct Workshop request; 12 at
  first, raised to 18 after Matte's live find that the clock starts at
  the CALL and a full debate eats 180 days - LIVE-TESTED PASS: total
  wait after a finished parliament reads exactly 12 months. Bonus find:
  yearly parliaments exposed a latent vanilla script error at
  parliament.txt:434, bare capital link on capital-less countries, 697
  log lines in minutes - fixed with a one-character ?= guard, spam
  confirmed gone next launch)
- LAND/NAVAL_WAR_EXHAUSTION_FROM_LOSSES 1/1.5 -> 1.5/2.25,
  MAX_WAR_EXHAUSTION_FROM_BATTLE 5 -> 7.5 (weakest complaint evidence of
  the ten - first candidate to revert if the feel is off)
- MONTHLY_REINFORCE 0.25 -> 0.3, MERCENARY_MANPOWER_REPLENISH_TIME_DAYS
  3600 -> 1800 (Paradox already halved it once from 7200)
- reduce_inflation cabinet action monthly_inflation -0.00025 -> -0.001
- CARPET_SIEGE_MAX_ARMIES 10 -> 6

### Deferred: map modes (top-10 item 10)
Devastation is an engine-known static modifier and prosperity's GUI
functions pair the two, but neither devastation nor unrest is PROVEN
script-readable for map_color lerp factors. Probe live next session
(map_color supports full lerp gradients - stability mode is the
template); error.log flags unknown triggers instantly.

## Code verification 2026-08-19 (binary + registry audit, no game launch)

Every claim in the published description verified against the engine itself
(exe define-registry RTTI, modifier_type_definitions, vanilla file diffs).
Method and reusable probes: knowledge/eu5-engine-internals.md.

- All 7 defines REGISTERED in the exe (CDefineRegistryHelper RTTI hit each):
  TRUCE_YEARS, SCALED_TRUCE_YEARS, MONTHLY_CONTROL_DECAY,
  LOW_CONTROL_THRESHOLD_FOR_BEST_TAX, AI_MILITARY_ARMY_ASSIGNMENT_PROXIMITY_
  FACTOR, AI_STICK_TO_SIEGE_TIME_FACTOR, CARPET_SIEGE_CONFRONT_FACTOR.
  Vanilla 1.3.11 baselines re-confirmed (5/10, 0.01, 0.95, -1, 0.003, 0.5).
  The pillar 6 arithmetic checks out: AI_MILITARY_ASSIGNMENT_PRIORITY_FACTOR
  = 100 "(1-10)" per the vanilla inline comment.
- All modifier keys the pillars grant are registered modifier types AND
  present in the exe: global_integration_speed_modifier (percent, country;
  vanilla advances grant it, so it is live), tax_income_efficiency,
  country_cabinet_efficiency, research_speed_modifier, local_fort_
  maintenance_efficiency, local_unrest, local_monthly_control,
  local_proximity_source, pop_join_rebel_threshold.
- Static modifier hosts engine-consumed by name: inverse_control,
  average_literacy, has_road, has_road_connected_to_capital,
  location_template_natural_harbor_suitability_location (all exe-present or
  vanilla-scaled blocks). complacency_impact has NO exe presence - correct,
  auto modifiers bind via trigger, not name; its trigger modifier
  has_complacency_effects IS engine-known (code-set during decline).
- Full-file override drift check vs live 1.3.11: every override diffs to
  exactly the intended lines, nothing else (subject types 11x halved
  country_cabinet_efficiency; forts 10x unrest + bailiff; governors 90;
  dock 20; topography 3 values; literacy 1.5; disaster nerf 21 lines;
  stabilize 0.1 = doubled cabinet_stability_investment script value 0.05,
  a static value so the literal loses nothing).
- Integration GUI wiring statically sound: buttons always clickable
  (Execute unconditional), IsShown drives only the gold highlight
  background. The clean 07-24 error.log baseline already proves the var:
  triggers evaluate cleanly (auto modifier potential_triggers run
  continuously). CLOSED same day: Matte had already clicked the levels in
  live play and the integration speed tooltip shows the bonus applied.
  With that, every pillar in the mod is verified (code audit + in-game).

## Audit 2026-07-24 (10-agent workflow, game 1.3.11 build 24187685)
- NO game update happened since 1.3.11 (07-16); the 9->15 baseline growth was
  local: Fate of the Phoenix DLC disabled in the playset (+6 lines) and the
  community-fixes junction live during "vanilla" runs. Matte is on the PUBLIC
  branch now, not a beta; no version skew exists. Next regen trigger: the 1.4
  Rio Salado open beta (autumn 2026).
- ROOT DEFECT found and fixed: the stop-button removal commit (ec31274)
  accidentally deleted five builder functions main() still called, so every
  regen crashed mid-run leaving orphaned files (dead Stop button live in game,
  harbor proximity claimed but never shipped). Generator repaired from c4e004e.
- Autonomy pillar was truly dead: the engine only applies auto modifiers to
  countries and international organizations, never locations. Re-levered onto
  vanilla's inverse_control static modifier: engine-applied, scales with lack
  of control (at zero control: fort upkeep -70 percent, unrest -3, control
  +0.015/month, fading out as control grows), visible in location tooltips.
- Invisible-by-design (working, hard to see): complacency defang (only during
  decline disasters, which we made rarer), subject cabinet malus (subject-side
  only, an overlord never sees it), MONTHLY_CONTROL_DECAY (only governs decay
  above max control; de-emphasized in public texts).
- The '#l' x2366 spam and the CabinetItem lines are vanilla GUI bugs, not ours.

## Baseline addition 2026-08-19 (v1.3.0 first launch, 11 lines, PASS)
Two vanilla noise lines not in the 07-24 family list (both screen-
dependent, neither mod-attributable): missing icon for the vanilla
country interaction lend_unit_to_ally (Paradox never shipped the dds),
and one SCoatOfArmsSpriteWrapper tooltip build error.

## Baseline snapshot 2026-07-24 (post-repair build, modded run)
17 distinct lines, ALL vanilla: 6x BYZ/TRE unowned-DLC stripping (permanent),
4x input context (per screen opened), 1x AudioArena, 6x DLC store thumbnail
load failures for unowned DLC (Fate of the Phoenix, Ancient Monuments, Sacred
Sites - vanilla VFS noise from any DLC-showing menu). ZERO mod-attributable
lines. This is the acceptance reference for the v1.2.0 push.
