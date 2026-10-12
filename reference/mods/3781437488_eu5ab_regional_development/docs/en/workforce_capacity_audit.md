# Workforce and construction-capacity API audit

[简体中文](../zh-CN/workforce_capacity_audit.md)

Static audit: 2026-09-25, starting from commit `3a60fa8`. The current instruction permits confirmed fixes and documentation only. No observation UI, probe Mod, speculative capacity scoring, or population-growth/migration model is added.

## Version and evidence

The installed Steam app is `3450310`, build `24187685` (`E:/SteamLibrary/steamapps/appmanifest_3450310.acf`, lines 3, 13). Prior investigation identified EU5 1.3.11; these exports have no version header and the executable reports only `1.0`. This audit identifies the exact installed build and export fingerprints; it does **not** independently reconfirm the semantic game version or claim runtime tests against it.

Local evidence roots:

- `D`: `C:/Users/shenh/OneDrive/Documents/Paradox Interactive/Europa Universalis V/docs`.
- `G`: `C:/Users/shenh/OneDrive/Documents/Paradox Interactive/Europa Universalis V/logs/data_types/data_types_uncategorized.txt`.
- `V`: `E:/SteamLibrary/steamapps/common/Europa Universalis V/game`.

`D/triggers.log` was exported at 17:56:31 local time, SHA-256 `b167d63b7c7e79fd6aff0dc4771d1fcc21219b5a98c0d2ef35f2d25704f1add2`. `G` was exported at 17:56:36, SHA-256 `8645d905912edf163e0e449e973aa22f76b3cdd662b0851bbf5862bb08b1489d`. Line numbers below refer to these files. Documentation registration, vanilla GUI use, repository use, and in-game validation are distinct levels of evidence.

Unless a row states otherwise, **refresh order, missing-object behavior and off-panel/reload behavior are not documented or runtime-verified**. `CFixedPoint` establishes a numeric type, not its unit, period, meaning or backend accessibility. `[unregistered]` is the export's type label, not proof that an API is absent or unusable.

## Workforce capabilities

| Data / API | Scope, environment and type | Unit / period / confirmed meaning | Evidence and remaining boundary |
| --- | --- | --- | --- |
| `location_unemployed_population_for_building_type` | Location; backend numeric comparator, used as a script value | Building-qualified idle-population query, optional owner; the Mod uses thousands of people | `D/triggers.log:8207`; native arithmetic use at `V/in_game/common/attribute_columns/05_location.txt:236`. Default-owner behavior, effective-vs-expected equivalence and vacancy/queue deductions remain unverified. Retain existing query; no extra deduction. |
| `unemployed_pops_of_pop_type_in_location` | Location; backend numeric comparator | Idle population of specified class; existing Mod boundary uses thousands | `D/triggers.log:10778`; vanilla use in `05_location.txt:154`. Ownership, eligibility exceptions and job reservations still need paired readings. Retain RGO/source-pool usage. |
| Job class, `employment_size`, `rgo_level` | Vanilla definitions; offline extraction to generated constants; backend `employment_size` on building type | Per-level job demand; extraction stores people and generated values divide by 1,000 once | `D/triggers.log:3842`; `game_data.py:extract_workforce_model`; `V/main_menu/common/static_modifiers/location.txt:614`. Direct amount conversion follows the existing model; no new GUI conversion is inferred. |
| `promote_to`, `promotion_factor`, promotion modifiers | Pop-type definitions and location/country modifiers; backend calculation | Current formula estimates capacity × target factor × horizon, capped by directly eligible idle source classes | `V/in_game/common/pop_types/00_default.txt:114,170,200`; `V/main_menu/common/static_modifiers/location.txt:17`; `generator.py:render_workforce_script_values`. Does not prove realized monthly promotions or pre-completion hiring. |
| `Location.GetPromoteValue` | GUI Location; `CFixedPoint` | Numeric; capacity vs actual amount, unit and period unverified | `G:85770`. No verified numeric transport or background lifetime; not substituted for current formula. |
| `Location.GetEffectiveUnEmployedValue(PopType)` | GUI Location; `CFixedPoint` | GUI treats formatted counterpart as current availability; exact subtraction formula unverified | `G:84804`; `V/in_game/gui/shared/location_tooltips.gui:6396`. Not treated as equivalent to a backend query. |
| `Location.GetExpectedUnEmployedValue(PopType)` | GUI Location; `CFixedPoint` | GUI distinguishes availability with construction; exact formula and units unverified | `G:84846`; `location_tooltips.gui:6353–6412`. Negative values are possible in GUI conditions; no clamping/transport added. |
| `Location.GetCivilConstructionsNeededPopsValue(PopType)` | GUI Location; `CFixedPoint` | GUI displays a separate queue deduction; upgrades, estates and RGO coverage unverified | `G:84450`; `location_tooltips.gui:6412`. Neither subtract again nor assume the backend already subtracts it. |
| Upgrade eligibility / employee transfer | Backend `building_can_be_upgraded_by` + extracted predecessors | Eligibility is documented; employee class conversion is not | `D/triggers.log:2508`. Cross-class credit now zero by user-approved rule; same-class old-job credit retained as compatibility behavior, not verified transferred employment. |

The employment tooltip supports a hypothesis that expected availability incorporates queue demand. It does not prove the relationship to either backend idle query. No runtime relationship has been silently encoded from the getter names.

The inspected vanilla promotion graph has no self-promotion edge and slaves are not a direct source of laborers. Thus the current RGO direct idle laborer/slave set and direct promotion-source set are disjoint. This static fact does not resolve absorption by other vacancies. Current one-project-per-location and no-existing-civil-construction gates remain in force; they reduce contention but do not prove all worker accounting is correct.

## Construction and market capabilities

| Data / API | Scope / environment / type | Units, inclusion and limits | Evidence / fallback |
| --- | --- | --- | --- |
| `every_location_in_market`, `every_buildings_in_location` | Backend market → locations → buildings | Provides an enumeration route independent of Mod ownership; visibility of all queue-only and foreign/estate objects not tested | `D/effects.log:2530,1690`. No claim of full project coverage. |
| `building_level`, `building_levels_under_construction` | Backend building; numeric | Level counts, not stable project identity or output | `D/triggers.log:2551,2557`. Zero-level objects and upgrade overlap need tests. |
| `num_civil_constructions` | Backend location; numeric | Civil-construction count; not a typed project list | `D/triggers.log:8728`. Existing RGO count subtracts building construction levels; completeness of this residual is unverified and unsuitable as a new capacity identity. |
| `location`, `owner`, `building_type`; location `market` | Backend scope links | Location, country, type and market; owner of market differs from owner of individual building | `D/event_targets.log:1106,1163,1425,1486`; exported links and existing repository usage. Follow each object's scope; do not substitute player's country. |
| `Location.GetCivilConstructions` | GUI Location; `[unregistered]` collection | Native GUI enumerates `Construction`; complete market coverage and unattended enumeration unverified | `G:84438`; `location_tooltips.gui:6430`. No new bridge implemented. |
| `Construction.GetID`, `.GetKey`, `.GetBuilding`, `.GetCountry`, `.IsRGO` | GUI construction; int32, CString, promoted Building/Country, bool | Identity/classification candidates; ID stability across save/load or reuse unknown | `G:53506,53518,53380,53386,53698`. Do not manufacture stable IDs or dedup on unverified semantics. |
| `Construction.GetDurationInDays`, `.GetDurationInDaysIncludingQueue`, `.GetProgress`, `.GetFinishedDateIncludingQueue` | GUI construction; int32, int32, float, CString | Names specify days/progress, but total vs remaining time, progress range and queue/stall interpretation unknown; finish date is text | `G:53464,53470,53560,53488`. No remaining-time formula or runtime text parsing. |
| `Building.GetLevelsUnderConstruction`, `.GetLevelsUnderUpgrade` | GUI building; int32, CFixedPoint | Counts; replacement direction and overlap unknown | `G:44902,44908`. Not converted into net new levels without evidence. |
| `building_employed_amount`, `building_employment_size_amount` | Backend building; numeric | Documented effective employed amount and max workers | `D/triggers.log:2527,2533`. Raw-vs-effective population units and application to future levels need tests. |
| `Building.GetEmployed`, `.CalcEmploymentPercent` | GUI building; CFixedPoint | Employment readings; scaling needs comparison against backend | `G:44734,44674`. Not a forecast for future workers. |
| `Building.GetWorkersRequired`, `.GetMaxWorkersRequired`, `.GetEmploymentSize` | GUI building; CString | Formatted text | `G:45088,44938,44746`. Excluded from runtime numeric data. |
| `Building.GetProductionMethods`; `any_production_method_of_building` | GUI collection; backend production-method iterator | GUI has methods; backend documentation explicitly says **available** methods, not selected active methods | `G:44992`; `D/triggers.log:1895`. Current first-feasible recipe remains a proxy, not actual PM observation. |
| `Building.GetEffectiveOutput(ProductionMethod)` | GUI building; CFixedPoint | Actual-building output binding; inclusion of all employment/efficiency/access effects and unit period need measurements | `G:44722`; active GUI use `V/in_game/gui/shared/production_method_details.gui:234–244`. Argument is a production method in vanilla use, not a goods ID. Never multiply extra efficiency automatically. |
| `Building.GetBuildingProductionEfficiency(Arg0)`, `building_efficiency` | GUI CFixedPoint / backend location numeric | Location/building efficiency evidence; argument and complete multiplier chain not established | `G:44692`; `D/triggers.log:2521`. No national per-level substitute. |
| `GoodsDemandEntry.GetValue × ProductionMethod.GetInputScale(Building)` | GUI numeric product | Vanilla displays this per-method input amount; base recipe entry alone is insufficient | `G:71208,105022`; `production_method_details.gui:160–170`. Period, all scaling and future-level applicability remain unverified. |
| `ActiveProductionMethod.GetActiveInputScale`, `.GetOutputLevel` | GUI CFixedPoint | Numeric scale/output-level values; quantity vs multiplier and object lifetime unknown | `G:36529,36547`. Not interpreted as direct commodity output. |
| `building_goods_input`, `building_produced_goods` | Backend building numeric / goods predicate | First has sparse argument documentation; second only tests whether a good is produced | `D/triggers.log:2539,2586`. Neither establishes a verified per-good incremental output path. |
| `BuildingCandidate.GetActiveInputs/Outputs` | GUI candidate; `[unregistered]` | Collection and candidate meaning not documented; located uses in production lateral view are commented out | `G:45219,45225`; `V/in_game/gui/production_lateralview.gui:2920,2959`. Not proof of usable post-minus-pre capacity prediction. |
| `GetBuildOrExpandBuildingCost`, `GetBuildingTypeProfitInLocation`, `GetBuildingTypeIncomeToOwnerInLocation` | GUI global; CFixedPoint | Monetary cost/profit/income already bridged by repository; not goods quantities | `G:3715,3769,3757`; `generator.py:render_engine_queue_gui`. Preserve current gates; do not derive physical output by dividing money by prices. |
| `goods_supply_in_market`, `goods_demand_in_market` | Backend market; numeric | Current commodity supply/demand; exact period, update ordering, trade and construction-demand inclusion not documented | `D/triggers.log:4222,4205`. Current use retained; no unverified future flows added. |
| `market_price`, `produced_in_market`, `traded_in_market`, `stockpile_in_market` | Backend market → value | Price, produced amount, traded amount, stock respectively; period and sign details sparse | `D/event_targets.log:1364–1398`. Stock is not a flow; market aggregate is not a project increment. |
| `total_effective_goods_production_buildings` | Backend country; numeric | Number of effective building levels producing the good | `D/triggers.log:10577`. Explicitly excluded as commodity quantity. |

No validated candidate incremental-output API was established. The available interfaces justify further read-only measurement, not implementation of exact future capacity. A GUI entry point cannot be called directly as a backend value. No test has established closed-panel, location-switch, save/load, unattended, multi-country or async transport behavior for these new bindings.

## Implemented workforce corrections

1. Both the optimized scan and live script values use the same class-checked upgrade-credit helper. Credit is `min(old jobs, new jobs)` only for identical job-class sets. A cross-class predecessor retains its position in the existing selection order and receives zero credit; it cannot fall through to another same-class predecessor. Existing predecessor selection itself is not a verified engine replacement decision when multiple predecessors coexist.
2. Both ordinary approval callbacks now check `eu5ab_has_local_workforce` once per invocation before reservations. This covers planning approval, profit-candidate collection, and the final profit winner. They clear scan promotion caches before evaluating current idle population, eligible sources, modifiers, horizon and net job demand. The player's workforce-protection setting still applies.
3. RGO already reaches `eu5ab_rgo_expansion_allowed` → `eu5ab_rgo_workforce_allowed` via `eu5ab_try_construct_rgo_need`; its formula is live and has no scan promotion cache. This path is retained.
4. Monthly scheduling and per-location scan cache lifetime remain unchanged. There is no history cache or newly assumed construction-time promotion. The horizon starts at evaluation, not completion; zero months adds no future promotion.
5. Approval failures increment the existing workforce counter. It reports modeled insufficient workforce, not an unproven causal diagnosis of class mismatch, queue competition or realized promotion. The top-three workforce numbers remain scan diagnostics, not a stored approval snapshot.

Two invocation-local flags (`eu5ab_validation_workforce_checked/passed`) are cleared at entry/exit. No persistent schema or migration is introduced. Existing saves acquire the new behavior on the next scan/callback; no settings are changed. The later asynchronous GUI construction call remains deferred and is not protected by a new atomic recheck.

## Boundaries and subsequent work

The current forecast retains its modifier-based speed and class-specific idle source ceiling. Natural growth/migration are outside scope, not observed zero. Actual promotion realization, existing vacancy absorption and queue deductions are still uncalibrated; no competing-job penalty was invented. Same-class credit still uses old job capacity, not measured retained employees.

Capacity feedback remains unimplemented pending verified sources and user-approved approximation choices. No capacity switch, ledger, confidence multiplier, scoring coefficient or time bucket has been invented. Next evidence must establish per-project net outputs/inputs, true active methods, employment/efficiency scaling, queue coverage/identity, and completion versus market-refresh ordering. Then implement snapshot aggregation, pending-to-building deduplication and bounded re-ranking in **both** strategies. Native profit thresholds and present input checks must remain separate from future planning risk.

## Validation record

Offline tests execute generated script branches with injected native readings. They cover every supported building's scan/live consistency, same/cross-class and multiple-predecessor upgrades, exact workforce thresholds, zero horizon, source-limited promotion, zero-cache markers, changed idle/source/speed/horizon at approval, protection disabled, duplicate callbacks, both ranking modes and existing gate precedence. These are not engine-semantic tests.

Recorded results (Python 3.14.5, installed-game data enabled):

- `python -B -m unittest tests.test_workforce_runtime tests.test_queue_validation_runtime tests.test_queue_recovery_runtime`: **22 passed**.
- Full `unittest` discovery: **581 executed, 0 assertion failures, 3 setup errors, 0 skips**. The three errors are absent historical fixtures: `tests/fixtures/candidate_collection_before.txt`, `score_short_circuit_before.txt`, and `scan_bucket_before_f2.txt`. `git ls-tree` confirms these were not tracked at the baseline commit. Their test classes did not execute; the whole suite cannot be reported as passing. An initial sandbox run also encountered temporary-directory permission errors; those disappeared on the normal-permission rerun.
- Generator validation and localization validation passed. All **74/74** output files match regenerated source. Nine other-language catalogs retain the existing English-fallback mechanism for missing or changed translations, including the two updated help strings.
- Regeneration exposed a pre-existing omitted naval migration-label binding. A single explicit mapping now preserves the already-committed GUI output; its focused GUI isolation test passes. No governor behavior or generated governor GUI change is included.
- `git diff --check`: passed.

Game-internal comparison and same-save performance measurement: **not run**. The user declined adding an observation entry point in this round. Native call latency, frame cost and new-bindings reliability are unmeasured; offline test runtime is not game performance. The correction adds one fresh workforce gate per eligible approval invocation, with no national/market scan, no persistent history and two temporary flags. A completed Goal requires separate runtime evidence for remaining population accounting and construction capacity, not merely passing Python tests.
