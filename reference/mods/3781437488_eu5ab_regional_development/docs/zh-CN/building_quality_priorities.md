# 推荐建筑优先级

[English](../en/building_quality_priorities.md) | [自动建造规则](automation_rules.md)

## 分数怎样生效

推荐优先级为 0～10。推荐模板使用这些分数，空白模板全部从 0 开始；自定义模板的 0 表示禁用。分数表达建设偏好，不是利润预测。

- **2～4**：需求较窄或适用条件较多。
- **5～7**：按需求补齐的产业与设施。
- **8～9**：较优先的产业节点或当地增产设施。
- **10**：最高推荐分，仍须通过需求和开工检查。

风味模板可以特别允许通用分数为 0 的建筑，此时按 1 分启用，复制为自定义模板时也保留 1 分。例如丝绸生产行会在通用模板中为 0，但纺织风味模板仍可启用。更高分数不会越过建造类型顺序或安全条件，详见[决策策略](automation_rules.md#决策策略与性能设置)。

## 代表性分数

相同分数的升级链合并展示。建筑 ID 用于与配置对应；完整目录以游戏内模板列表和[规则配置](../../policies/automation_rules.json)为准。

| 建筑或升级链 | 分数 | 用途与限制 |
| --- | ---: | --- |
| `granary`, `village_granary` | 10 | 储粮与减损，仍须满足省份需求和收益要求。 |
| `windmill` | 9 | 当地谷物增产，须有实际作物产出和正的增量净收益。 |
| `irrigation_systems` | 9 | 食物与人口容量设施，须有对应需求。 |
| `farming_village`, `sheep_farms` | 7 | 农业与羊毛上游，按当地需求安排。 |
| `fishing_village` | 5 | 沿海生产及港口用途。 |
| `maghreb_palm_irrigation` | 7 | 水果与发展用途，仍受特殊建筑及原版条件限制。 |
| `fiber_crops_farm` | 6 | 纺织与造船原料。 |
| `salt_collector`, `stone_quarry` | 3 | 按缺口少量补充。 |
| `dyes_workshop` | 4 | 需要染料需求与充足木材。 |
| `cloth_guild`, `cloth_workshop`, `cloth_manufactory`, `textile_mill` | 8 | 布料升级链。 |
| `fine_cloth_guild`, `fine_cloth_workshop`, `fine_cloth_manufactory`, `fine_cloth_mill` | 9 | 高级布料升级链。 |
| `tools_guild`, `tools_workshop`, `iron_foundry`, `iron_mill` | 9 | 工具升级链，注意上游原料供应。 |
| `paper_guild`, `paper_workshop`, `paper_manufactory`, `paper_mill` | 7 | 纸张升级链，为书籍提供原料。 |
| `scriptorium`, `printing_press_shop`, `printing_manufactory`, `printing_mill` | 6 | 书籍与印刷升级链。 |
| `glass_workshop`, `glassworks` | 6 | 按玻璃需求安排。 |
| `mason` | 9 | 核心建材。 |
| `lumber_mill` | 8 | 补充木材供应。 |
| `tar_kiln`, `naval_supplies_workshop` | 3 | 需求较窄，避免过量建设。 |
| `marketplace`, `commerce_center`, `al_qaysariyya_market` | 6 | 贸易设施，特殊地点建筑仍须原版许可。 |
| `market_warehouse` | 6 | 市场库存缓冲。 |
| `caravanserai` | 4 | 按市场吸引力需求使用。 |
| `armory`, `barracks` | 7 | 人力设施，价值取决于军队构成。 |
| `horse_breeders` | 3 | 贵族与骑兵需求。 |
| `weapon_workshop`, `weapon_factory` | 7 | 武器升级链。 |
| `cannon_workshop`, `cannon_foundry` | 3 | 按军需缺口补充。 |
| `bog_iron_smelter` | 8 | 补充铁供应，效率随地点与时代变化。 |
| `local_smelters` | 9 | 当地金属增产。 |
| `charcoal_maker`, `improved_charcoal_maker` | 6 | 煤铁工具链的上游。 |
| `jewelry_guild` | 2 | 依赖金银成本与贸易条件。 |
| `silk_production_guild` | 0 | 通用禁用；纺织风味模板仍可按 1 分启用。 |
| `fruit_orchard`, `cotton_plantation` | 0 | 默认禁用，可在自定义模板中调整。 |
| `port_authority`, `funduq`, `dock`, `dry_dock`, `shipyard`, `grand_shipyard`, `naval_base`, `protected_harbor` | 0 | 通用禁用；风味模板的明确允许项可按 1 分启用。 |
| `stockade`, `castle`, `bastion`, `star_fort`, `fortress`, `city_walls` | 0 | 默认不自动建造防御建筑。 |
| `training_fields`, `mercury_patio`, `porcelain_manufactory`, `perfumery` | 0 | 无独立评分依据，或沿升级关系继承 0。 |

## 来源与维护

评分参考 [Bilibili UP 主瘦扁扁](https://space.bilibili.com/456154809)的建筑评测上、中、下三期及种田攻略，[原始字幕](../../source)提供评分依据。实际开工仍按当前需求、价格、劳动力和收益检查。

直接评价用于基础分；升级建筑沿原版前置关系继承，多个前置取最高分；没有依据且无可继承前置时为 0。项目人工调整优先于直接评分和继承规则。

[video_building_priorities.json](../../policies/video_building_priorities.json) 保存直接评分及人工调整，[catalog_builder.py](../../src/eu5autobuild/catalog_builder.py) 的 `build_priority_overrides` 生成评分和依据。最终分数写入 `automation_rules.json` 的 `building_priorities.overrides`；[templates.json](../../policies/templates.json) 单独决定风味模板的允许范围。

调整分数时修改来源并重新生成，不维护第二份手工评分表。生成步骤见[开发指南](development.md#环境与生成)。
