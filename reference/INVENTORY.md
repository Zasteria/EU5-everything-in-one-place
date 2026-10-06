<!-- Written by tools/refs.py --write. Do not edit by hand. -->
# What is in `reference/` right now

Versions live here rather than in prose, so refreshing a mod needs no
edit anywhere else. Re-run after any refresh:

```
python3 tools/refresh.py
```

| Folder | Mod id | Version | Game |
| --- | --- | --- | --- |
| `3624485168_labelplace` | `labelplace` | 0.1 | 1.* |
| `3668193813_trin_national_destinies` | `trin.national_destinies` | 1.4.0 | 1.4.* |
| `3681629733_eu5_noblesautomarry_fix` | `eu5.noblesautomarry.fix` | 1.4.0 | 1.3.* |
| `3692202776_community_mod_framework` | `community_mod_framework` | 2.5.0 | 1.4.* |
| `3736668860_construction_manager` | `romaimperator.construction_manager` | 2.2.12 | 1.3.* |
| `3742578604_national_mission_trees` | `national_mission_trees` | 0.2 | 1.3.10 |
| `3765240629_responsive_universalis_aggressive_ticks` | `responsive_universalis_aggressive_ticks` | 1.1.0 | 1.4.* |
| `3784699906_calidad_de_vida_eu5` | `calidad_de_vida_eu5` | 1.2.1 | 1.4.* |
| `3789103426_community_mod_framework_dev` | `community_mod_framework.dev` | 2.4.1 | 1.3.* |
| `3789151637_romaimperator_construction_manager_dev` | `romaimperator.construction_manager.dev` | 2.3.0 | 1.3.* |
| `3812518640_glorp_ui_rio` | `glorp.ui.rio` | 04.10.26 | 1.4.* |
| `3813746228_grackbox_formables_atlas` | `grackbox.formables_atlas` | 1.0.2 | 1.4.* |

## The rest of the playset

Text only — no `gfx`, no sound, and only English and Russian
localization. These are here to be read and measured, not built
against: `refs.mods()` does not see them, and nothing generated
compiles from them.

| Folder | Mod id | Version | Mounts |
| --- | --- | --- | --- |
| `3633816300_ogasoptimized` | `ogasoptimized` | 20260627 | in_game, main_menu |
| `3696243603_autonomous_diplomats` | `autonomous_diplomats` | 1.5.0 | in_game, main_menu |
| `3721516330_integration_hotfix` | `Integration Hotfix` | 0.7 | in_game, loading_screen, main_menu |
| `3779064076_rexbert_buymyart` | `rexbert.buymyart` | 1.0 | in_game |
| `3780623638_nation_destinies_rus` | `nation_destinies_rus` | 1.3 | main_menu |

`reference/game/` holds 5147 files of EU5 itself — `in_game/gui/`, the parts
of `in_game/common/` the mods here reason about, and the game's own
localization, which is how `mods/nd_ru/tools/term.py` answers what the game
calls a concept.
