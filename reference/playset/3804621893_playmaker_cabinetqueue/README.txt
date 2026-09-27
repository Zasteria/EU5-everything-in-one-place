PLAYMAKER CABINET QUEUE 0.3.59 — DIPLOMACY AUTOMATION (EXPERIMENTAL)

Levy dismissal fix: the log showed missing UnitOverview context in the topbar.
Pending dismissal now opens the military overview; native dispatch runs inside
that view. Army/navy auto-raise remains unchanged. Restart to load the new GUI.
Static checks passed; corrected runtime behavior still needs confirmation.

Default now includes Army raise and Navy raise (native auto-raise-at-war settings)
and Peace dismiss (opt-in automatic levy dismissal while out of all wars).
Dismissal checks daily, obeys native restrictions and preserves regular units.
See LEVY_AUTOMATION.txt. Static checks passed; in-game verification pending.

Diplo Boost is also available to the right of Send Demand in the peace footer.
It now tops up reputation and improved-relations impact to Diplomatic Endeavors
with the best currently assigned cabinet member, including native efficiency.
Existing equivalent action bonuses are subtracted independently for each stat.
The diplomatic-spending top-up, daily refresh and calendar-month expiry remain.
No members are hired or reassigned. In-game numeric/UI verification is pending.
See DIPLO_BOOST.txt for calculation details and checks.

Relations places Add all subjects and the Auto-annex subjects controls at the
top, with Create Subjects alongside Add all subjects. Resync has been removed.
The antagonism bulk-add uses a saved threshold selected with minus/plus:
10, 20, 30, 40, or 50 (default 30). Changing the threshold does not change the
existing queue; click Add antagonistic nations to append qualifying countries.

Opening Setup now includes Add land to HRE. Hold to add eligible owned locations
using the native HRE land eligibility check and the normal picker restriction
against conquered locations. Skips land already in the HRE. Repeats passes as
new imperial neighbors make more owned land eligible, stopping when no land
was added (engine loop safety cap: 1000 passes). Disabled if the HRE is absent
or no owned locations qualify. Static checks passed; in-game test pending.

Relations includes Add antagonistic nations. Click to append all discovered
nations in diplomatic range whose antagonism toward you is strictly above the
selected threshold.
Preserves queue order, skips duplicates, and resets completion records only
for newly added nations, like confirming a manual selection. Does not start a
paused queue or continuously add future targets. Native dispatch requirements
and completion limits still apply. Script checked against local game docs;
in-game verification remains pending.

Opening Setup now includes Dismantle HRE beside Conciliatory. Hold to dissolve
the Holy Roman Empire using the native organization destruction effect, from
any player country without peace treaty requirements. Disabled if no HRE exists.
Static validation complete; in-game verification remains pending.

0.3.59 connects Communalism to tested cabinet selection, removes test/step UI,
and applies zero diplomatic spending through the visible native budget slider.

0.3.58 makes Economy request zero diplomatic spending and enables cabinet-member automation.

0.3.57 moves Integrate All and its controls to Default, beneath the cabinet status
row. Removes the visible CT55 loaded/armed diagnostic labels. Behavior unchanged.

0.3.56 adds Integrate All: switches existing cabinet slots to Auto Integrate using
the native UIAction route confirmed by the user's successful 0.3.55 test.
See INTEGRATE_ALL.txt. Bulk reassignment still requires in-game verification.

0.3.55 tests the native parameterized UIAction dispatcher for cabinet selection.

0.3.54 delays arming cabinet and societal picker observers until after creation.

0.3.53 moves cabinet probes outside the header button and adds a visible CT53 marker.

0.3.52 fixes test sequencing before menu navigation and prevents overlapping runs.

0.3.51 allows Cabinet test to use empty idle slots. Selection probes now run on
the native cabinet action card and report each matching condition separately.

0.3.50 adds an isolated Cabinet test in Opening Setup. It attempts Communalism
promotion using one idle slot and logs each native selection step.
Privilege grants are unchanged. See CABINET_TEST.txt; runtime testing is required.

0.3.49 permanently removes finished relations targets. Native auto-recall no longer
causes a retry when the final progress observation was missed. Any ended dispatch
is retired unless this queue intentionally recalled it (Pause, limit, or war).
Manual recalls and failed starts are therefore also retired after the grace period.
Clear, Resync, Continue at +200 and Add all subjects retain the no-resend history.
History starts with this version; already-removed targets cannot be reconstructed.

0.3.48 removes Selection test and Script grant test controls and adds Humanist,
Spiritualist, Decentralization and Conciliatory presets. All presets use the
same ownership, eligibility, affordability and successful-grant guards.
Country-specific candidates remain subject to native availability checks.
Existing privileges are not revoked when selecting an opposing value preset.

0.3.47 adds Centralization and Innovative buttons to Opening Setup. Native
privilege definitions supply each preset's eligible candidates and individual
power/satisfaction values. Country restrictions, conflicts, ownership and
affordability are checked separately for every grant. No menus open and no
cabinet members are assigned. See VALUE_PRESETS.txt for the candidate lists.

0.3.46 stops the unfinished cabinet picker from opening after Communalism.
The normal button applies the same five guarded privilege grants and Equality,
without opening Government or appointing a cabinet member for an action that
cannot yet start automatically. Existing cabinet members/actions are untouched.
Cabinet promotion remains manual. Explicit diagnostic buttons remain available.

0.3.45 extends the user-tested scripted grant method to all five Communalism
privileges. Each grant checks missing ownership, estate presence, eligibility
and affordability; costs and satisfaction changes occur only after a successful
new grant. Values come from the installed privilege definitions. No estate
variables are used. The old privilege picker sequence is bypassed. Cabinet
selection retains its existing behavior and may still need manual input.

0.3.44 fixes the engine-confirmed variable-scope error in the isolated grant
test. Pre-grant penalty values now live on the country, because estate scopes
do not support variables. All six other non-Crown estate types are handled
when present. Main Communalism remains unchanged pending runtime comparison.

0.3.43 adds satisfaction effects to the isolated Strengthened Faith script test:
Clergy target-satisfaction bonus times the native grant multiplier, and other
non-Crown estate penalties scaled by pre-grant power. This formula fits the
user's native tooltip; in-game comparison is still required before integration.

0.3.42 adds an isolated Script grant test for Strengthened Faith. This is NOT
wired into Communalism. Compare its consequences with a native grant using the
same starting save; see SCRIPT_GRANT_TEST.txt. Native equivalence is unverified.

0.3.41 moves diagnostic grant controls out of the background table row into
a dedicated panel above the privilege list, with a visible heading and logging.
Automatic selection remains unresolved; this repairs the isolated test UI.

0.3.40 adds an opt-in Selection test in Opening Setup. It opens only the Clergy
picker and adds Direct grant / Native grant controls to Strengthened Faith.
Try Direct grant first, then Native grant only if the first has no effect.
Successful grants use normal game costs. The test does not run Communalism's
employment or cabinet effects. Automatic selection remains unresolved.

0.3.39 adds Tribes Allow Gatherings after the Commoners privilege and before
cabinet selection. It skips owned privileges, unavailable estate privileges,
and unaffordable grants. Native costs are preserved. The picker still needs a
manual click: automatic privilege selection is unresolved.

0.3.38 removes an unsupported CabinetAction.IsValid GUI call and adds picker
selection/confirmation diagnostics. Automatic privilege selection remains
unresolved; this build is diagnostic, not a confirmed fix.

0.3.37 keeps picker callbacks active while selecting their target, initializes
the native hovered-target context, and advances only after observing privilege
ownership or the cabinet action's destination view. Failed selections no longer
cycle through estate screens as though successful. Runtime validation pending.

0.3.36 adds Universal Christianity third and Guilds fourth to the Research
requests, skipping unavailable optional entries. Religion-specific advances use
the native unique-advance list. Communalism helpers now attach directly to picker
rows and activate after navigation finishes. Native eligibility, ownership checks
and grant costs are retained. Economy is unchanged. In-game validation is pending.

0.3.35 observes current/completed research outside the changing advance list,
so starting the first advance cannot remove its progression observer. Communalism
now uses the same delayed activation as the user-confirmed working Economy preset.
Economy implementation is unchanged. Research/Communalism need in-game validation.

0.3.34 records Communalism's next request stage before the native action can
destroy its source view. Economy and Research are armed by an explicit topbar
animation 0.75 seconds after opening their native screen, allowing initialization
before request visibility becomes true. In-game outcome remains unverified.

0.3.33 adds a 25% Dhimmi automatic-tax satisfaction target to Economy.

0.3.32 puts Research, Government, Economy and societal-value helpers inside
their inherited panel_content blocks. v31 logs recorded button clicks but no
native-view helper creation, so the previous root placement is being corrected.
Remove Forts now uses the regular button skin while retaining hold-to-execute.
Automation behavior still requires an in-game test; diagnostics remain enabled.

0.3.31 is a diagnostic build, not a confirmed Research/Communalism fix.
Opening Setup displays request stages. PMCQ31 markers in debug.log record
button clicks, view creation and helper animation entry/completion. The Economy
worker now uses its native budget screen context because the engine rejected
the topbar's const EconomyView provider. Repeat-charge protection is retained.

0.3.30 removes script-based privilege grants and grant-price deductions. Each
privilege is explicitly checked with has_estate_privilege; only missing entries
are submitted through the native grant action, which owns legitimacy and estate
satisfaction changes. Overlapping button clicks are disabled. Government opens
explicitly, and cabinet selection uses its native CabinetItem provider. The
native UI sequence is experimental and may require finishing selections manually.

0.3.29 adds Opening Setup > Communalism: the three standard Clergy privileges
and Access to Royal & Ecclesiastical Courts, Equality if unlocked and affordable,
and an experimental native cabinet-selection sequence. Existing tasks are preserved.
An eligible character can be appointed to an empty slot. Normal privilege,
employment and appointment prices are paid. Missing eligibility/resources skips
that step; click again after resolving it. Cabinet selection needs in-game testing.

0.3.28 replaces the Research helper's unconfigured grid with a nonvirtualized
list, submits the native queue command at entry, and waits for native queue/current/
researched confirmation before proceeding to Classic Scholasticism. Candidate fix;
requires an in-game test. Requests expire after eight seconds if unsuccessful.

0.3.27 moves the Economy worker to a persistent topbar provider and explicitly
submits slider changes; native automation toggles run at animation entry.
This is a candidate fix for the reported v26 toggles/sliders failure, untested in-game.

0.3.26 adds Opening Setup Research and Economy presets. Research opens the
native view and requests Improved Religious Organization followed by Classic
Scholasticism if available; existing research/queue entries are preserved.
Economy enables per-estate automatic taxation, automatic minting and automatic
general/admiral assignment. Satisfaction targets: nobles/burghers 1%, clergy and
tribes 100%, peasants 45%. Court spending maximum; diplomatic spending minimum.
Both buttons use native UI commands and require in-game validation after restart.
Economy applies once, leaving subsequent manual changes alone.

0.3.25 renames Estates to Default and groups its estate actions, Auto stability,
province controls, Diplo boost and cabinet status under that tab. All three menus
now start below a shared tab row in one anchored container. Automation remains
independent of the selected tab. The expand button stays accessible when collapsed.

0.3.24 organizes the utility controls into Opening Setup, Estates and Relations
tabs. Opening Setup contains Remove Forts. Estates contains the estate buttons
and Auto stability without the redundant heading. Relations contains Create
Subjects immediately left of Resync. Subject creation now releases only standard
vassals, skipping provinces where vassal creation is unavailable. Hold-to-execute
remains on fort removal and subject creation. Tab changes never pause automation.

0.3.23 remembers native improvement-cap completion independently of total opinion
and of the active-improvement flag. Quick relations and the Improve Opinion outliner
both observe progress, with a 0.01 percentage-point tolerance for rounding at 100%.
A recorded cap survives later scans, Resync and the Continue at +200 toggle until
the entry leaves the queue. Once recalled, it is removed instead of retried even
when total opinion is below +200. Explicitly adding it again starts a new entry.

0.3.22 dispatches annexation through the native Start Annexation GUI action,
instead of perform_diplomatic_action. It checks both quick and dynamic subject
actions. One target is requested per scan. Only the matching
Start Annexation confirmation is accepted during that request; existing dialogs
block dispatch. Native costs, requirements and the configured limit still apply.
Auto stability is now beside the existing bottom +20 stability button.

0.3.21 fixes the rejected annex action name: the installed engine registers
annexationaction. Both the native quick-action lookup and scripted start use it.
Resync clears previous failed annexation retry delays, retaining pending reservations.
Auto +20 stability (default Off) uses the existing Ask Commoners for Stability
action when stability is at most 80 and native eligibility/cooldown allow it.
It selects the eligible Peasants/Dhimmi estate with the highest satisfaction.
The native +20 stability, -20 percentage-point satisfaction cost and five-year
cooldown apply. A one-day retry guard prevents repeated failed calls per scan.
Neither feature bypasses game rules. Native execution needs in-game validation.

0.3.20 adds Continue at +200 (default Off): when On, total opinion does not
finish an entry, but the actual Improve Relations cap still does. Add all subjects
appends current direct subjects once, skips duplicates and preserves queue order.

Auto-annex eligible subjects is a separate opt-in toggle (default Off). It watches
all current and future direct subjects, using native Start Annexation availability.
It starts normal annexation, never instant annexation or forced acceptance. Normal
costs, time, loyalty, opinion and subject-type restrictions apply. It issues at most
one start per scan and waits 30 game days before retrying a failed request for that
subject. Existing annexations are skipped. Off stops new starts without cancelling
ongoing annexations. Relations Pause/Max do not control this separate feature.
The separate Annex maximum defaults to 1 and can be set from 1 to 20. It counts
all ongoing annexations, including manual ones, plus pending automatic starts.
Reducing the maximum stops new starts; it does not abort ongoing annexations.
When both need the last diplomat, annexation gets priority for that scan.
Native annex action availability and execution require in-game confirmation.

0.3.19 removes the fixed +100/+200 improvement-cap fallback. Completion uses
the engine's progress percentage for the actual target (including subjects and
improvement bonuses), or maximum total opinion. 100% progress is NOT +100 opinion.
Resync also clears old completion flags. After restarting, press Resync before
starting the queue. Re-add nations already removed by the previous fixed cap.

0.3.18 adds valid animated properties to every queue animation state after the
game reported animations with no valid state properties. Scripted GUIs explicitly
enter root, matching vanilla's country GUI effects. The header now shows Scans
(completed processing passes) and Resync (button executions). While running,
Scans should increase roughly every two seconds; Resync increases on each click.
These diagnostics distinguish a stopped GUI timer from stale native observations.

0.3.17 replaces the failed saved-scope timer with a repeating GUI update loop.
The queue refreshes every ~2 seconds of real time, including while paused or
minimized. It fills vacancies when diplomats become available and reconciles
manually cancelled assignments. Old timer callbacks are disabled.
Recall uses the native Improve Opinion outliner right-click action instead
of the nonexistent cancel_improve_relation script effect. Keep the Diplomacy
outliner and its Improve Opinion entries visible while testing automatic recall.
A short-lived matching
confirmation handler is added to ingame_dialogs.gui. This file can conflict with
other mods overriding that same dialog file or outliner_entries.gui.
Other confirmation types are untouched.
Resync clears stale grace/retry state without discarding the queue or its limit.
For an existing stuck queue: restart EU5, press Resync, then Start or Pause.

0.3.16 fixes missing native relation context in the monitor and a queue-order
map lookup that evaluated its key in the wrong country scope. These caused the
0.3.15 monitor to miss assignments and put sent nations back into Waiting.
GUI providers now live in separate parent/child widgets with one context each.
Both ordered passes explicitly visit the entire queue to fill every free slot.
Scripts use UTF-8 BOM and the new panel buttons use localization keys.
After updating: restart the game. Manually cancel any assignment that 0.3.15 sent
but now shows as Waiting; that old version discarded its ownership record.
Then Pause/Start the queue. Your queued nations and Max setting are preserved.

Add nation opens the native country picker. Repeat to queue several nations in
selection order. Set Max with +/- (1–20, default 1), then Start. The limit counts
this queue's simultaneous assignments including outbound diplomats, not lifetime
diplomat expenditure or manually assigned diplomats.

The queue uses native Improve Relations. It finishes when the native progress
reaches 100%, or the target has +200 total opinion. It recalls the assignment and
only releases the slot after the native action is observed to have ended. Completed
entries leave the queue: this is a one-pass queue, not an automatic repeat loop.

Unavailable targets wait while later eligible entries may start. Native action
availability, diplomatic range, wars and diplomat supply still apply. Existing
manual assignments are observed but never adopted or cancelled. Failed/interrupted
queue assignments wait 30 days before another attempt. Pausing recalls this queue's
assignments and retains unfinished entries. Lowering Max recalls excess assignments.
Remove works on waiting entries; Clear requires paused and fully recalled state.

The panel is above your existing controls and minimizes with them. Monitoring keeps
running while minimized. Save state includes queue/order, limit, assignment tracking,
and retry delays. Single-player only, matching the existing mod. Keep built-in Improve
Opinion automation and other diplomat automation disabled while using this queue.

VALIDATION: Static checks and an independent queue behavior model are provided in
VALIDATION_DIPLOMACY.json. No EU5 runtime test has been performed. In particular,
native GUI recall, confirmation and repeated scan behavior must be confirmed
in-game. This is an experimental implementation.
Completion requires the engine's native progress observation or maximum total
opinion. Missing progress observations do not fall back to a guessed fixed cap.



PREVIOUS VERSION NOTES

PLAYMAKER CABINET QUEUE 0.3.14

LATEST CHANGE — 0.3.14
Four estate buttons show remaining cooldown months after their next successful use.
Months round up; the native cooldown determines when the countdown disappears.
Works for successful actions from this panel or the native estate menu, and saves
its dates with the game. Pre-existing untracked cooldowns show (Cooldown); hover
for native action requirements. Green highlighting still means usable now.
This adds an override of common/generic_actions/estate_emergency_actions.txt from
the supplied game files. Other mods changing that same file may conflict.
In-game behavior and text fit still need testing.

PREVIOUS CHANGE — 0.3.13
Opening Setup is now a direct Remove Forts button: hold to remove all owned
stockades, castles and city walls. The setup menu, privilege grants, economy
and automation features have been removed, including the economy GUI override.
Create Subjects and the separate estate/cabinet controls are retained.
Replace the entire old mod folder; merging leaves deleted files installed.
Earlier version notes below describe historical features, including removed ones.

INSTALL
Close EU5, replace the entire Playmaker_Cabinet_Queue folder, and restart.
Use the existing queue and save. Press Pause then Start once after updating.

SETUP — ONE OR TWO MEMBERS
Assign Queued Increase Control, Queued Noblesse Oblige, or both in the cabinet.
These are the mod's custom actions; original vanilla actions do not join the queue.
Increase Control alone does NOT require the Noblesse Oblige reform.
Noblesse Oblige requires its reform whether alone or paired.
Add provinces in your preferred order and press Start.

BEHAVIOR
Only participating actions supply bonuses. No absent member's skill is read.
Both active: two separately scaled local buffs, plus native nobles satisfaction.
Control alone: control buff only. Nobles alone: nobles buff and satisfaction only.
One member leaving stops their contribution while the remaining action continues.
Newly assigned members join a running queue on its next daily refresh.
Losing Noblesse Oblige reform drops nobles support; control can keep running.
No eligible participants: pause and clear bonuses.
Pause removes buffs and retains assignments and queue. Restart starts at first entry.
Rotation uses your selected 1-6 calendar month stay (default 3); owned provinces at >=95% control
are skipped on target selection. Current target ownership loss pauses the queue.
Generation tokens reject obsolete callbacks after pause/restart.
GUI stays compact at far right, with minimize/expand; minimizing does not pause.
Control and Nobles bonuses persist while assigned. Daily checks remove stale
bonuses and update strength only when the assigned member's effective skill changes.
Pausing, changing targets, and removing participants explicitly clean up bonuses.
Single-player only.

SCALING AND VERIFICATION
Local bonus base values remain 0.10 maximum control and 0.01 monthly control
per assigned action, scaled by 1 + that cabinet's effective_skill and checked daily.
Exact equality with vanilla engine modifier scaling is still unverified.
Nobles satisfaction uses the original native country_modifier amount.
0.2.5 static checks and independent membership model cases passed; EU5 is not
installed here and this version has not been tested in-game.
Test control-only without the reform, nobles-only with it, then both. Remove
one member during a stay: only their bonus should disappear and rotation continue.
If anything fails, send error.log and debug.log.

ROTATION DURATION (0.2.5)
Use the - and + buttons around Stay: N mo in the panel header.
Range: 1 through 6 calendar months. Default for existing/new queues: 3.
This preference is saved with the country.
Changing it during a stay does not cancel or shorten the scheduled callback:
the next province receives the new duration. Start / Restart returns to the
first province and immediately begins a fresh stay using the chosen duration.
Panel size, minimize/expand, and independent action requirements are retained.


BUILD 0.3.0 — AUTO ASSIMILATE TO CORE
Assign one cabinet member to the new Auto Assimilate to Core action.
It starts on the next game day; it does not use the control queue Start button.
Stop it by changing/removing that cabinet assignment.
Promotes YOUR PRIMARY CULTURE. No culture picker is needed.
Targets owned provinces where all owned locations are integrated/core and at
least one remains integrated. Chooses highest population among eligible targets.
Existing promoting_culture markers are skipped at selection.
The action keeps its target until all owned locations have actual core status,
or ownership/eligibility changes. It NEVER sets integration level or forces cores.
Natural core requirements still apply; a province can remain a target if those
requirements are unmet even after cultural assimilation.
When no target remains it idles, retaining its seat and scanning daily.
Native promote_culture values copied: assimilation speed 0.04 and migration
attraction -0.15, scaled by 1 + effective_skill. Exact engine parity unverified.
Applies bonuses only to owned integrated locations; full cores no longer need it.
Sets/cleans the native promoting_culture province variable used by vanilla.
Do not manually assign native assimilation to the same active province: both
systems share that native marker and identical-culture overlaps are indistinguishable.
The small Auto core status strip shows the selected province or idle state.
Runs independently of the control queue and its 1-6 month setting.
Runtime test required: confirm the Auto Assimilate modifier on a target location,
primary-culture progress, cleanup and next-target selection upon natural coring.

0.3.1 — FOLLOW CULTURE CONVERSION
Click Manual provinces in the panel header to switch to Culture conversion.
Assign Queued Increase Control and press Start; no manual provinces are required.
The mode uses the promoting_culture province marker from vanilla assimilation
and Auto Assimilate to Core. It does not include passive assimilation without
an active culture-promotion marker. If Queued Noblesse Oblige is assigned, it
follows the same targets and still requires its reform.
Each stay uses your selected 1-6 months. A round visits eligible provinces once,
prioritizing population among unvisited provinces. Eligibility refreshes daily:
owned, currently culture-promoted, and average control below 95%.
Ending conversion, losing ownership, or reaching 95% ends a stay early.
No eligible targets: Waiting, no location bonuses; daily scanning continues.
Pause stops scanning. Changing mode while running starts the new source
immediately; changing back with an empty manual list leaves the queue paused.
Manual list and order are preserved. Pause then Start after upgrading so the
new timer protection is initialized. New behavior has not been tested in EU5.

0.3.2 — AUTO INTEGRATE PROVINCES
Assign one military cabinet member to Auto Integrate Provinces. No Start button
or manual queue is required. The first scan occurs on the next game day.
It selects your most populated province containing an owned conquered location,
applies province integration speed (base 1.0, matching the native action), and
checks daily until every owned location is integrated or a core. It then removes
its old bonus and selects the next eligible province. This does not create full
cores or set integration levels directly. If no target remains, it waits and
scans daily for new conquests. Reassign/remove the member to stop and clean up.
The action is separate from control and assimilation: no shared targets, month
setting, Start/Pause buttons, or timers. A small Integrating status line shows
its current province. Minimizing the panel hides the line without stopping it.
Multiple auto-integration members are supported in 0.3.3. Avoid assigning vanilla integration
to its current province; overlapping native integration is not detected and may
stack. This remains a province-sized action after the area-integration advance;
it does not gain the native area action's wider coverage.
New province-modifier application and exact native skill scaling parity require
in-game verification. Static validation does not run the EU5 engine.

0.3.3 — MULTIPLE AUTO CABINET MEMBERS
Auto Assimilate to Core and Auto Integrate Provinces now allow multiple members.
Each slot owns its target, skill-scaled bonus, and completion state. Daily scans
process them independently; reservations prevent duplicate targets within each
action. Extra members wait if there are fewer eligible provinces than members.
Reassigning one member only clears that member's target and bonus. A shared daily
scheduler visits all active slots without changing another slot's progress.
The panel displays active member counts (including members waiting for a target).
UPGRADING: Reassign ALL existing auto-assimilation and auto-integration members
to another action, then assign them back after installing. This initializes
per-member state and cleans the old single-member bonuses. The control queue is
unchanged. Native-action overlap caveats and unverified skill parity still apply.

0.3.4 — DIPLO BOOST BUTTON
Click Diplo boost in the panel header. It grants the BASE reputation bonus from
Diplomatic Endeavors plus 3 * (1 - diplomatic_maintenance). Slider 0/50/100%
therefore adds 3/1.5/0 reputation. The base cabinet portion is suppressed when a
member already performs Diplomatic Endeavors, Bironovshchina, or Posolsky.
There is no member-skill scaling, improved-relations bonus, treasury charge, or
slider movement. The bonus is removed on the first daily callback in the next
calendar month, including December-to-January. It is not a rolling 30-day bonus.
Click again to refresh after a slider change; daily checks also update the gap.
Between a slider change and that refresh, the previous top-up remains applied.
Repeated clicks do not stack or schedule additional callbacks. The short native
modifier expiry is refreshed daily; the script controls calendar-month expiry.
Source: uploaded triggers.log documents diplomatic_maintenance (0-1) and
current_month (1-12). Base cabinet modifier comes from supplied vanilla files;
full slider reputation of +3 supplied by user. Runtime testing is required.

0.3.5 — DEBUG MODE BUTTON
The expanded panel's status row now includes Debug ON/OFF. Click it to execute
the game's debug_mode toggle. Its label reads the actual InDebugMode state,
including changes made outside this button. It does not pause the queues.
The button uses the documented ExecuteConsoleCommand GUI function and the
same debug_mode command referenced in the supplied data-type dump.
In-game command availability and UI rendering still need testing.

0.3.6 — PANEL POSITION
Moved the panel into the outlined bottom-right area from the supplied screenshot.
The two auto-action status labels now share one row beneath the controls.
The collapsed panel follows the new position. Layout inferred from screenshot
UI scaling; exact placement still needs in-game confirmation.

0.3.7 — BOTTOM-LEFT ESTATE SHORTCUTS
Moved the controls and status labels to the bottom-left screen corner.
An estate panel sits immediately above them and minimizes with the main panel.
Four shortcuts invoke native actions with the appropriate estate parameter:
Appeal to Commoners, Clerical Endorsement, Request Noble Envoy, and Emergency
Parliament (Burghers fallback). Available action labels turn green; unavailable
actions remain disabled. Native tooltips explain requirements, costs and effects.
Rewards are provided by the installed game's actions, not hard-coded here.
Automatic highest-loyalty estate selection, bulk privileges and bulk subject
creation are not implemented in this build. The panel may overlap native
bottom-left controls at some UI scales; check placement in-game.

0.3.8 — OPENING SETUP (PARTIAL IMPLEMENTATION)
Opening Setup opens a separate menu above the estate panel. Hold Remove Forts
to delete all stockades/castles in owned locations. Privileges grants the two
test privileges directly, without reproducing native grant costs.
Tax Targets Only sets the uploaded economy scripts' variables to 1% nobles,
1% burghers, 100% clergy, 100% tribes and 45% commoners. These preferences alone
do not enable native auto-tax or force clergy/tribes taxes to zero.
Create Subjects 50/50 is outside the setup menu. It snapshots provinces with
owned non-integrated locations, including mixed integration, and creates one
subject per eligible province. It favors the less numerous type within this
batch and falls back if only one type is legal. Native subject-type checks and
colonized-land exclusions apply. Existing subjects are not included in balancing.
Full Economy (minting, switches, court/diplomatic sliders), ordered research
queue and Autosubject diplomacy are NOT implemented. The supplied effect dump
does not expose verified setters for these engine-controlled operations.
Research candidates found: organized_religion, scholasticism,
res_publica_christiana, guilds; display-name confirmation requires localization.
This build is for testing; no EU5 runtime execution was available.

0.3.9 — RIGHT-SIDE UI, SUBJECT AVAILABILITY, PRIVILEGE COSTS
All panels and status labels moved to bottom-right. The setup menu opens above.
Replaced incomplete can_do_generic_action(create_province_subject) check with
native country/union permission checks and an eligible-province check including
legal subject types. Mixed conquered/integrated provinces still qualify.
Privileges now cost a flat 5 government power each (legitimacy in monarchies),
matching the native base price; cost modifiers are not applied. Each newly
granted privilege also receives a custom -5 percentage-point Burghers satisfaction
penalty. Existing privileges are skipped. With 5-9 power, only the first missing
privilege is granted; with 10+, both can be granted. No grant occurs below 5.
All previous partial-setup limitations remain. In-game behavior unverified.

0.3.10 — INDEPENDENT-COUNTRY SUBJECT CHECK
Fixed the repeated invalid subject_type scope error in Create Subjects. The
allow_subject_creation check now executes only when the player is a subject.
Independent countries continue through union/province/type eligibility checks.
The other pending automation features remain unimplemented.

0.3.11 — WALLS, LABELS, FULL ECONOMY PROTOTYPE
Remove Forts includes the standard city_walls building type as well as castles
and stockades. Estate labels are +20 stab, +15 Gov power, +5 diplomat; underlying
native estate actions are unchanged.
Tax Targets Only was replaced by Economy (test). It sets the saved targets,
opens the Economy view, attempts native auto-minting and estate auto-tax switches,
then attempts native court/diplomatic sliders through clamped slider callbacks.
The request clears after a one-second UI pass. This requires runtime testing:
check auto-minting ON, every estate auto-tax ON, court 100%, diplomacy 0%, and
actual clergy/tribes tax rates. Targets: 1/1/100/100/45 percent as requested.
This adds an economy_lateralview.gui override and can conflict with other mods
that replace that view. No script invents additional income or grants research.
Relation/annexation queue execution remains pending. Intended relation controls:
manual ordered list or cycling subjects, opinion target, simultaneous diplomat
limit; recall only managed assignments at target. Annexation queue must count
all ongoing annexations and never start a third. Research needs a verified
AdvanceItem instance/queue callback, not research_advance (instant unlock).

0.3.12 — APPLY AUTOMATION / REMOVE INCORRECT PRIVILEGE PENALTY
Opening Setup now has Apply Automation, separate from Economy (test). It uses
native GUI toggles for minting, every estate's auto-tax, replacegenerals and
replaceadmirals. Each toggle runs only if currently off. The button opens Economy
and does not change targets or sliders. Native GUI execution still needs testing.
Removed both custom -5-point Burghers penalties from the batch privilege action.
The screenshot shows +15 Burghers, -10.71 Nobles, -5.86 Clergy, -2.06 Commoners;
these are not hard-coded because their dynamic calculation is unverified.
The batch action still lacks native immediate satisfaction effects. Its tooltip
now states this. Use vanilla grants to obtain the exact current satisfaction
changes. Previously applied wrong penalties are not retroactively refunded.
