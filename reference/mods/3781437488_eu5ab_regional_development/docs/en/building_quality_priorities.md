# Recommended Building Priorities

[简体中文](../zh-CN/building_quality_priorities.md) | [Build Rules](automation_rules.md)

## How ratings work

Recommended priorities range from 0 to 10. Recommended templates use these ratings; blank templates start at 0 throughout. A custom priority of 0 disables the building. Ratings express construction preferences, not predicted profits.

- **2–4:** narrower demand or more restrictive use cases.
- **5–7:** industries and facilities built according to need.
- **8–9:** favored supply-chain links or local output improvements.
- **10:** highest recommendation, still subject to need and construction checks.

Built-in Presets may explicitly allow buildings with a general rating of 0, using priority 1. **Copy as Player Template** retains that 1. For example, Silk Production Guild is generally disabled but remains available in the Textiles preset. Higher ratings do not override construction-type order or safeguards; see [Strategy and Performance](automation_rules.md#strategy-and-performance).

## Representative ratings

Upgrade chains sharing a rating are grouped below. IDs identify configuration entries; the in-game template list and [rules configuration](../../policies/automation_rules.json) contain the complete catalog.

| Building or upgrade chain | Rating | Role and limits |
| --- | ---: | --- |
| `granary`, `village_granary` | 10 | Storage and decay savings, subject to province need and return checks. |
| `windmill` | 9 | Local grain improvement; needs actual crop output and positive marginal net returns. |
| `irrigation_systems` | 9 | Food and population capacity, subject to a need check. |
| `farming_village`, `sheep_farms` | 7 | Agricultural and wool supply, according to local need. |
| `fishing_village` | 5 | Coastal production and port value. |
| `maghreb_palm_irrigation` | 7 | Fruit and development; special-building and native conditions still apply. |
| `fiber_crops_farm` | 6 | Inputs for textiles and shipbuilding. |
| `salt_collector`, `stone_quarry` | 3 | Limited additions when supply is short. |
| `dyes_workshop` | 4 | Depends on dye demand and sufficient lumber. |
| `cloth_guild`, `cloth_workshop`, `cloth_manufactory`, `textile_mill` | 8 | Cloth upgrade chain. |
| `fine_cloth_guild`, `fine_cloth_workshop`, `fine_cloth_manufactory`, `fine_cloth_mill` | 9 | Fine-cloth upgrade chain. |
| `tools_guild`, `tools_workshop`, `iron_foundry`, `iron_mill` | 9 | Tools upgrade chain; secure upstream inputs. |
| `paper_guild`, `paper_workshop`, `paper_manufactory`, `paper_mill` | 7 | Paper upgrade chain supplying books. |
| `scriptorium`, `printing_press_shop`, `printing_manufactory`, `printing_mill` | 6 | Books and printing upgrade chain. |
| `glass_workshop`, `glassworks` | 6 | Build to meet glass demand. |
| `mason` | 9 | Core construction materials. |
| `lumber_mill` | 8 | Additional lumber supply. |
| `tar_kiln`, `naval_supplies_workshop` | 3 | Narrower demand; avoid excess construction. |
| `marketplace`, `commerce_center`, `al_qaysariyya_market` | 6 | Trade facilities; special locations still need native permission. |
| `market_warehouse` | 6 | Market stock buffer. |
| `caravanserai` | 4 | Situational market attraction. |
| `armory`, `barracks` | 7 | Manpower buildings; value depends on army composition. |
| `horse_breeders` | 3 | Noble and cavalry demand. |
| `weapon_workshop`, `weapon_factory` | 7 | Weapons upgrade chain. |
| `cannon_workshop`, `cannon_foundry` | 3 | Add according to military shortages. |
| `bog_iron_smelter` | 8 | Additional iron; effectiveness depends on location and era. |
| `local_smelters` | 9 | Local metal-output improvement. |
| `charcoal_maker`, `improved_charcoal_maker` | 6 | Upstream supply for the coal, iron and tools chain. |
| `jewelry_guild` | 2 | Depends on precious-metal costs and trade conditions. |
| `silk_production_guild` | 0 | Disabled generally; the Textiles preset can enable it at priority 1. |
| `fruit_orchard`, `cotton_plantation` | 0 | Disabled by default; adjustable in a custom template. |
| `port_authority`, `funduq`, `dock`, `dry_dock`, `shipyard`, `grand_shipyard`, `naval_base`, `protected_harbor` | 0 | Disabled generally; explicitly allowed preset entries can use priority 1. |
| `stockade`, `castle`, `bastion`, `star_fort`, `fortress`, `city_walls` | 0 | Defensive buildings disabled by default. |
| `training_fields`, `mercury_patio`, `porcelain_manufactory`, `perfumery` | 0 | No separate rating evidence, or a zero inherited through upgrades. |

## Sources and maintenance

Ratings draw on [Shou Bianbian's Bilibili](https://space.bilibili.com/456154809) three-part building reviews and development guide. [Original transcripts](../../source) provide the rating sources. Actual starts still check current need, prices, workforce and returns.

Direct reviews establish base ratings. Upgrades inherit along native predecessor links, taking the highest predecessor rating when several converge. Buildings without evidence or rated predecessors default to 0. Explicit project adjustments take precedence over direct and inherited ratings.

[video_building_priorities.json](../../policies/video_building_priorities.json) stores direct ratings and adjustments. `build_priority_overrides` in [catalog_builder.py](../../src/eu5autobuild/catalog_builder.py) generates ratings and their basis. Effective scores are written to `building_priorities.overrides` in `automation_rules.json`. [templates.json](../../policies/templates.json) separately determines which buildings each preset allows.

Change the source and regenerate when adjusting ratings; do not maintain a second manual rating source. See [generation instructions](development.md#environment-and-generation).
