# Development and Validation

[简体中文](../zh-CN/development.md) | [Documentation](../../README.md)

## Environment and generation

See [pyproject.toml](../../pyproject.toml) for Python requirements and dependencies. Core tools use the standard library; the optional save validator also requires NumPy and Pillow.

Run from the repository root with your actual game installation:

```powershell
$env:EU5_GAME_ROOT = 'D:\SteamLibrary\steamapps\common\Europa Universalis V'
python -B -m src.eu5autobuild.catalog_builder
python -B -m src.eu5autobuild.generator
```

The installation must contain `game/in_game/common`. `--game-root` takes precedence over the environment variable. For game or CMF updates, use the [update workflow](game_updates.md) to compare upstream data before synchronizing.

The catalog builder updates building data, priority ratings and the raw-goods snapshot. The mod generator writes `.metadata/`, `in_game/` and `main_menu/localization/`. Edit sources, regenerate and review the diff rather than editing generated files alone.

## Choosing checks

For routine changes, run only the smallest checks directly relevant to the change. Repeat a passed check only after a change affecting that path, a new failure or an unresolved risk. See [tests/README.md](../../tests/README.md) for module selection.

Group regressions by current behavior. Use named subtests for input variations in the same flow, and keep distinct lifecycle boundaries independently covered. Before deleting a duplicate, identify the retained case that exercises its behavior. Use small explicit fixtures for compatibility cases instead of historical save samples. Keep generator contracts for syntax, scope, event hooks and GUI bindings; validate behavioral rules in the relevant runtime tests.

| Change | Check |
| --- | --- |
| Catalog or ratings | `python -B -m src.eu5autobuild.catalog_builder --check`; requires the game directory |
| Generated scripts | `python -B -m src.eu5autobuild.generator --check` plus relevant behavior tests |
| UI copy or translations | `python -B -m src.eu5autobuild.localization_check`; no game installation needed |
| Upstream version or complete output synchronization | Update-tool `check`; see [commands](game_updates.md#commands) |
| Documentation | Local links, commands, bilingual correspondence and related code facts |

Both `--check` commands leave generated files unchanged. `catalog_builder --check` compares catalog and priority copies. `generator --check` checks generated bracket balance and reports translation coverage; it **does not compare all generated files on disk**. For an independent comparison:

```powershell
@'
from src.eu5autobuild import generator as g
files = g.generated_files(g.load_policies(g.POLICY_FILE), g.load_building_catalog(g.CATALOG_FILE), g.load_automation_rules(g.RULES_FILE))
stale = [str(p.relative_to(g.ROOT)) for p, text in files.items()
         if not p.exists() or p.read_text(encoding="utf-8-sig") != text.lstrip("\ufeff").replace("\r\n", "\n")]
if stale:
    raise SystemExit("Stale generated files: " + ", ".join(stale))
print(f"Matched {len(files)} generated files")
'@ | python -B -
```

This comparison normalizes BOM and line endings. `localization_check` checks localization encoding and the in-game/main-menu copies. Native-data integration tests require `EU5_GAME_ROOT`; record failures and skips. Offline tests inject game readings and do not establish native UI behavior, engine timing or performance.

Routine generation and investigation do not calculate hashes. Only an explicit formal-release or hash-verification request permits the required artifact checks; see [AGENTS.md](../../AGENTS.md).

## Configuration and text sources

| Content | Source |
| --- | --- |
| Building catalog and ratings | [catalog_builder.py](../../src/eu5autobuild/catalog_builder.py), [rating sources](building_quality_priorities.md#sources-and-maintenance) |
| Built-in Presets | [templates.json](../../policies/templates.json), loaded by [policy.py](../../src/eu5autobuild/policy.py) |
| Rules, ranges and defaults | [rules.py](../../src/eu5autobuild/rules.py), [automation_rules.json](../../policies/automation_rules.json); CMF settings use `GLOBAL_RULE_DEFAULTS` and registration in [generator.py](../../src/eu5autobuild/generator.py) |
| Chinese and English UI copy | The two localization renderers in [generator.py](../../src/eu5autobuild/generator.py), plus [rgo_localization.py](../../src/eu5autobuild/rgo_localization.py), [manual_decisions.py](../../src/eu5autobuild/manual_decisions.py), [governor_generator.py](../../src/eu5autobuild/governor_generator.py) and [governor_layout_ui.py](../../src/eu5autobuild/governor_layout_ui.py) |
| Other languages | [Translation catalogs](../../localization/translations), checked and rendered by [localization.py](../../src/eu5autobuild/localization.py) |
| Open upstream adaptations | `open_adaptations` in [game_update_rules.json](../../policies/game_update_rules.json) |

Chinese UI copy uses 「」 and nested 『』. Preserve color, icon, dynamic-value and localization references. Keep the existing Chinese and English names for Built-in Presets, Custom Templates / Player Templates, Copy as Player Template and Maximum Throughput. Descriptions should explain behavior players can observe.

Translation entries retain their Chinese and English sources. Missing or source-changed entries fall back to current English. Update source records only after reviewing the translation; replacing records alone must not disguise stale translations. Keep Chinese and English documentation aligned when rules change.

## Implementation entry points

| Feature | Main modules |
| --- | --- |
| Monthly scans, budget and load recovery | [generator.py](../../src/eu5autobuild/generator.py), [annual_budget.py](../../src/eu5autobuild/annual_budget.py), [scan_reserve.py](../../src/eu5autobuild/scan_reserve.py), [save_resume.py](../../src/eu5autobuild/save_resume.py) |
| Ordinary construction batches and backfill | [construction_batch.py](../../src/eu5autobuild/construction_batch.py), [batch_backfill.py](../../src/eu5autobuild/batch_backfill.py) |
| RGO starts, counts and pending output | [rgo_batch.py](../../src/eu5autobuild/rgo_batch.py), [rgo_queue.py](../../src/eu5autobuild/rgo_queue.py), [rgo_pending.py](../../src/eu5autobuild/rgo_pending.py), [rgo_cost.py](../../src/eu5autobuild/rgo_cost.py) |
| Construction slots, capacity and upgrades | [construction_slots.py](../../src/eu5autobuild/construction_slots.py), [building_capacity.py](../../src/eu5autobuild/building_capacity.py), [upgrade_queue.py](../../src/eu5autobuild/upgrade_queue.py), [worker_upgrades.py](../../src/eu5autobuild/worker_upgrades.py) |
| Prices, recipes and market construction | [Prices and Market Construction](market_construction.md) |
| Project output and commissioning protection | [Production Forecasts](production_forecast.md) |
| Food buildings and industry preference | [food_infrastructure.py](../../src/eu5autobuild/food_infrastructure.py), [industry_promotion.py](../../src/eu5autobuild/industry_promotion.py) |
| Manual decisions and player configuration | [manual_decisions.py](../../src/eu5autobuild/manual_decisions.py), [decision_state.py](../../src/eu5autobuild/decision_state.py) |
| Governor recommendations and refresh | [governor_generator.py](../../src/eu5autobuild/governor_generator.py), [governor_refresh.py](../../src/eu5autobuild/governor_refresh.py), [governor_layout_generator.py](../../src/eu5autobuild/governor_layout_generator.py) |

Preserve these contracts:

- EU5 may omit zero-valued variables; valid zero and missing data need separate states.
- Reloads, stale callbacks and duplicate events must not repeat starts, budget charges or protection extensions.
- Ordinary buildings and RGOs record actual per-project payments. Cash preflight uses estimates, and the final project may exceed the annual budget.
- RGO counts come from native readings, not civil count minus buildings. Do not add target construction counts to predecessor upgrade counts.
- Before fixing unused-variable warnings, trace real generation, writes, reads and consumers, including old saves. Do not add dummy accesses or remove useful caches merely to silence warnings.
- Manual decisions override `eventwindow.gui` and `decisions_lateralview.gui`. Compare the native templates in `src/eu5autobuild/assets/` after game updates; other mods overriding the same files need a merge.
- Increment `STRAIT_SCHEMA` in [governor_connections.py](../../src/eu5autobuild/governor_connections.py) when changing embedded strait topology.

## Diagnostics and validation

[In-Game Validation Guide](runtime_validation.md) describes current interface rules and performance-capture steps.

Under `scripts/`, `audit_game_log.py`, `audit_saved_production.py`, `validate_governor_save.py` and `analyze_native_profile.py` analyze logs, saved production data, governor propagation and profiling reports respectively. Use `--help` for arguments. Keep original saves and experiment on copies. Record the code revision, uncommitted changes, game/CMF versions, commands and results; historical passes do not validate today's implementation.
