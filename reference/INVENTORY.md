<!-- Written by tools/refs.py --write. Do not edit by hand. -->
# What is in `reference/` right now

Versions live here rather than in prose, so refreshing a mod needs no
edit anywhere else. Re-run after any refresh:

```
python3 tools/refresh.py
```

| Folder | Mod id | Version | Game |
| --- | --- | --- | --- |
| `3600272327_sakuya` | `sakuya` | 1.6.0 | 1.3.* |
| `3601047146_glorp_ui` | `glorp.ui` | 10.08.26 | 1.3.* |
| `3619540530_no_more_becoming_hre` | no metadata | 1.0 | 1.3.10 |
| `3668193813_trin_national_destinies` | `trin.national_destinies` | 1.3.8 | 1.*.* |
| `3680208976_sakuya_afterburner` | `sakuya_afterburner` | 1.6.0 | 1.3.* |
| `3692202776_community_mod_framework` | `community_mod_framework` | 2.4.1 | 1.3.* |
| `3736668860_construction_manager` | `romaimperator.construction_manager` | 2.2.12 | 1.3.* |
| `3742578604_national_mission_trees` | `national_mission_trees` | 0.2 | 1.3.10 |
| `3784699906_calidad_de_vida_eu5` | `calidad_de_vida_eu5` | 1.0.6 | 1.3.* |
| `3789103426_community_mod_framework_dev` | `community_mod_framework.dev` | 2.4.1 | 1.3.* |
| `3789151637_romaimperator_construction_manager_dev` | `romaimperator.construction_manager.dev` | 2.3.0 | 1.3.* |

## The rest of the playset

Text only — no `gfx`, no sound, and only English and Russian
localization. These are here to be read and measured, not built
against: `refs.mods()` does not see them, and nothing generated
compiles from them.

| Folder | Mod id | Version | Mounts |
| --- | --- | --- | --- |
| `3633816300_ogasoptimized` | `ogasoptimized` | 20260627 | in_game, main_menu |
| `3662193478_faster_universalis` | `faster.universalis` | 1.8.2 | in_game, loading_screen, main_menu |
| `3662933683_fusm_daily_tick` | `fusm.daily.tick` | 1.3.2 | in_game, loading_screen, main_menu |
| `3662938575_fusm_hourly_tick` | `fusm.hourly.tick` | 1.3.2 | in_game, loading_screen, main_menu |
| `3677315887_fusm_halfday_tick` | `fusm.halfday.tick` | 1.3.2 | in_game, loading_screen, main_menu |
| `3696243603_autonomous_diplomats` | `autonomous_diplomats` | 1.5.0 | in_game, main_menu |
| `3721516330_integration_hotfix` | `Integration Hotfix` | 0.7 | in_game, loading_screen, main_menu |
| `3779064076_rexbert_buymyart` | `rexbert.buymyart` | 1.0 | in_game |
| `3780623638_nation_destinies_rus` | `nation_destinies_rus` | 1.3 | main_menu |

`reference/game/` holds 2395 files of EU5 itself — `in_game/gui/`, the parts
of `in_game/common/` the mods here reason about, and the game's own
localization, which is how `mods/nd_ru/tools/term.py` answers what the game
calls a concept.
