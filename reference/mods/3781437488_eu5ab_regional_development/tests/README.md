# Tests

Run checks from the repository root. For routine work, select the smallest relevant module or test; do not run the full suite by default or repeat a passed check without a new reason. See [Development](../docs/en/development.md) / [开发与校验](../docs/zh-CN/development.md) for generation and localization checks.

```powershell
python -B -m unittest tests.test_annual_budget_runtime -v
python -B -m unittest tests.test_manual_decisions_runtime -v
```

These are separate examples, not a required sequence.

## Finding relevant coverage

| Change | Starting points |
| --- | --- |
| Budget and ordinary starts | `test_annual_budget_runtime`, `test_construction_batch_runtime`, `test_batch_lock_runtime` |
| Queue retries, delayed callbacks and cleanup | `test_queue_recovery_runtime`, `test_queue_lifecycle_runtime`, `test_queue_cleanup_runtime` |
| RGO starts, counts and output | `test_rgo_batch_runtime`, `test_rgo_queue_runtime`, `test_rgo_pending_runtime` |
| Recipes and production forecasts | `test_native_recipes_runtime`, `test_production_reference`, `test_production_projects_runtime`, `test_production_cohorts_runtime`, `test_production_maintenance_runtime` |
| Saved recipe names and economic associations | `test_save_production` |
| Prices, materials and food | `test_output_prices_runtime`, `test_market_supply_runtime`, `test_food_infrastructure_runtime` |
| Capacity, slots and upgrades | `test_building_capacity_runtime`, `test_parallel_construction_runtime`, `test_upgrade_queue_runtime`, `test_worker_upgrades_runtime` |
| Monthly scans and recovery | `test_monthly_schedule_runtime`, `test_scan_reserve_runtime`, `test_save_resume_runtime` |
| Templates, settings and decisions | `test_template_name_runtime`, `test_template_coverage_runtime`, `test_cmf_settings_runtime`, `test_manual_decisions_runtime` |
| Industry and governor rules | `test_industry_promotion_runtime`, `test_governor_14`, relevant `test_governor_*` modules |
| Generation, translations and upstream data | `test_generator`, `test_script_engine_contracts`, `test_localization_check`, `test_catalog_builder`, `test_game_update` |

These modules are entry points, not mandatory bundles. Use the individual regression that exercises the changed behavior when possible.

Organize regressions by current behavior, rather than the date of an investigation. Queue data waits belong in `test_queue_recovery_runtime`; pending-output refresh coalescing belongs in `test_production_maintenance_runtime`; CMF registration and callbacks belong in `test_cmf_settings_runtime`.

## What to test

Test decisions, calculations and observable boundaries. The small Python interpreters execute generated script control flow with injected engine inputs. They cover accounting, cleanup, stale callbacks, missing values, save recovery and related behavior; they do not validate the EU5 engine or measure in-game performance.

Keep structural checks for contracts these interpreters cannot exercise: syntax, scope, hooks, GUI bindings, localization keys, markup and encoding. Avoid locking tests to exact prose, pixel spacing, release numbers or arbitrary generated-file sizes. Do not duplicate behavior coverage with long lists of text fragments.

Use named `subTest` cases for the same setup and assertions with different inputs. Keep distinct lifecycle boundaries separate. Before removing a regression, identify the retained case that covers it; preserve save compatibility and failure paths with small explicit fixtures instead of historical save dumps or sample totals.

## Fixtures and optional inputs

`_generated.py` renders the default mod once per process from checked-in metadata in `_game_data_fixtures.py`. Treat the cached result as read-only and copy or parse it into each harness's own mutable state. Tests with different policies or recipes should render their own inputs; do not call another test class's `setUpClass()` for shared data.

Native-data integration tests skip unless `EU5_GAME_ROOT` is configured. The optional governor save validator also needs NumPy and Pillow. Report skips and failures with results.

Native acceptance remains separate: compare actual quotes, payments, project progress, UI callbacks, saves and timing as described in [In-Game Validation Guide](../docs/en/runtime_validation.md). A construction quota is a ceiling, not a required start count.
