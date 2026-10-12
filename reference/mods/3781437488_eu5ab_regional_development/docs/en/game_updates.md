# Game and CMF Updates

[简体中文](../zh-CN/game_updates.md) | [Development](development.md)

The update tool compares vanilla and CMF data and checks catalogs, rules and generated files. Synchronization, baseline recording and in-game acceptance are separate steps. Synchronizing does not change the supported version or publish the mod.

## Commands

From the repository root, set the actual installation paths and supply the observed version label:

```powershell
$env:EU5_GAME_ROOT = 'D:\SteamLibrary\steamapps\common\Europa Universalis V'
$env:EU5_CMF_ROOT = 'D:\Mods\Community Mod Framework'
python -B -m src.eu5autobuild.game_update audit --game-version '1.4-open-beta'
```

`--game-root` and `--cmf-root` override environment variables. `--baseline`, `--output` and `--config` select the baseline, report directory and monitoring configuration. The tool also records Steam build ID and beta branch; it does not infer the game version from CMF declarations.

| Command | Purpose |
| --- | --- |
| `audit` | Save a candidate snapshot and diff report, checking policy gaps without changing the mod or baseline. |
| `sync` | Audit, generate and validate in a temporary directory, then write changed files only. Roll back on write failure; leave the baseline unchanged. |
| `check` | Compare upstream data and all generated files on disk. Write reports without repairing the mod or advancing the baseline. |
| `baseline` | After data and generated files match and new decisions are recorded, archive the old baseline and record the current observation. Documented unfinished adaptations may remain. |

After reviewing the report and making necessary changes, run these as needed:

```powershell
python -B -m src.eu5autobuild.game_update sync --game-version '1.4-open-beta'
python -B -m src.eu5autobuild.game_update check --game-version '1.4-open-beta'
python -B -m src.eu5autobuild.game_update baseline --game-version '1.4-open-beta'
```

Exit `0` means command success and `2` means execution failure. `check` returns `1` for upstream/version changes, open adaptations, stale files or a missing baseline; read the report for the cause. A successful `audit` may return `0` while reporting work still to do.

## Baselines and reports

| Location | Purpose |
| --- | --- |
| `.upstream/baseline.json` | Current upstream observation baseline |
| `.upstream/history/` | Baselines archived before replacement |
| `.upstream/latest/candidate.json` | Current candidate observation |
| `.upstream/latest/report.md` and `report.json` | Summary and complete changes, sources and open work |
| `.upstream/archives/<topic-date>/` | Manually archived full audits, separate from the current baseline |

`.upstream/` is Git-ignored so full game definitions are not committed. Copy baselines and archives when moving machines as needed; a first observation cannot recover old data overwritten by Steam. Mismatched format or extractor versions require migration or a new baseline, rather than treating format changes as game changes.

The tool stores no Steam account information and calculates no hashes.

## Rule sources and open adaptations

- Ratings: [video_building_priorities.json](../../policies/video_building_priorities.json).
- Built-in Presets: [templates.json](../../policies/templates.json).
- Goods groups and effective rules: [automation_rules.json](../../policies/automation_rules.json).
- Monitoring scope, decisions and open work: [game_update_rules.json](../../policies/game_update_rules.json), not a second rating source.

New buildings receive `reviewed`, `pending` or `excluded` decisions in `building_decisions`. Group new goods or explain generic handling in `generic_goods`. Advancing the baseline does not remove `pending` decisions or `open_adaptations`. Close them only after implementation and required validation.

Monitoring retains operators, repeated keys and order in building, goods, production-method and related unlock definitions, ignoring comments and whitespace. Unparseable jobs or materials and missing required CMF symbols block synchronization. New fields still need review; symbol presence does not establish CMF API semantics. Strait extraction handles `sea` connections only; canals need separate review.

The current adaptation targets new 1.4 campaigns, not migration from 1.3 saves. See [In-Game Validation Guide](runtime_validation.md) for validation rules and methods.

CMF 2.5 setting writes use `cmm_set_setting_value`, and Action Bar fields use `cmm_set_list_field_value`. These save values without invoking callbacks. Keep the mod's own setting synchronization, budget refresh and country-switch handling. Widget-type metadata remains part of registration.

## Tools and checks

The repository includes the [eu5autobuild-game-update skill](../../.agents/skills/eu5autobuild-game-update/SKILL.md), invoked as `$eu5autobuild-game-update`. Its focused tool test is:

```powershell
python -B -m unittest tests.test_game_update -v
```

Choose other checks based on the actual changes; do not run the full suite by default. Native UI, queue progress, payments and performance require separate in-game validation.
