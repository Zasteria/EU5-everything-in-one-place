# 劳动力与在建产能接口核验

[English](../en/workforce_capacity_audit.md)

核验日期：2026-09-25；代码基线：`3a60fa8`。按本轮确认，只做已明确的修正和接口文档，不添加数值核验入口、不重新注册探针 Mod，不将待核准的产能估算接入评分。自然增长与迁移模拟不属于本轮人口目标。

## 版本与证据等级

本机安装的 Steam App 为 `3450310`，build 为 `24187685`（`E:/SteamLibrary/steamapps/appmanifest_3450310.acf` 第 3、13 行）。此前调查使用版本名 1.3.11；现存接口导出没有版本头，exe 文件版本只写 `1.0`。因此本次记录准确的安装 build 和导出指纹，**不声称独立确认了当前语义版本或完成了该版本游戏实测**。

下表证据缩写：

- `D`：`C:/Users/shenh/OneDrive/Documents/Paradox Interactive/Europa Universalis V/docs`。
- `G`：`C:/Users/shenh/OneDrive/Documents/Paradox Interactive/Europa Universalis V/logs/data_types/data_types_uncategorized.txt`。
- `V`：`E:/SteamLibrary/steamapps/common/Europa Universalis V/game`。

`D/triggers.log` 导出时间为本地 17:56:31，SHA-256 为 `b167d63b7c7e79fd6aff0dc4771d1fcc21219b5a98c0d2ef35f2d25704f1add2`；`G` 为 17:56:36，SHA-256 为 `8645d905912edf163e0e449e973aa22f76b3cdd662b0851bbf5862bb08b1489d`。下表行号指向这份导出。

“导出已注册”“原版 GUI 使用”“仓库已有调用”“游戏内实测”分别记录，不能互相替代。除单独注明外，**刷新顺序、对象缺失时的返回值、关闭面板及读档行为均未由文档说明或本轮实测确认**。`CFixedPoint` 只证明数值类型；不证明单位、统计周期和后台可读。`[unregistered]` 是导出中的类型标签，也不能直接解释为接口不存在。

## 劳动力能力表

| 数据/接口 | 作用域、环境与类型 | 单位、周期及已确认范围 | 证据、缺口与当前处理 |
| --- | --- | --- | --- |
| `location_unemployed_population_for_building_type` | 地点，后台数值比较/脚本值 | 按建筑类型查询闲置人口，支持可选 owner；现有 Mod 按千人使用 | `D/triggers.log:8207`；原版数值使用 `V/in_game/common/attribute_columns/05_location.txt:236`。默认 owner、是否等于 effective/expected、是否已扣除空缺岗位及队列未核准。保留既有查询，不另扣竞争岗位。 |
| `unemployed_pops_of_pop_type_in_location` | 地点，后台数值 | 指定阶层闲置人口；现有 Mod 按千人使用 | `D/triggers.log:10778`；原版使用 `05_location.txt:154`。所有者、就业例外及岗位预留仍需数值对照，保留 RGO 和转职来源池调用。 |
| 岗位阶层、`employment_size`、`rgo_level` | 原版定义提取为常量；建筑类型后台值 | 每级岗位；提取层保存人数，生成运行时统一除以 1,000 | `D/triggers.log:3842`；`game_data.py:extract_workforce_model`；`V/main_menu/common/static_modifiers/location.txt:614`。沿用已有单位边界，不据此推定新 GUI 数值单位。 |
| `promote_to`、`promotion_factor`、转职修正项 | 人口定义、地点/国家修正项 | 现有公式为能力估算×目标因子×期限，并受直接合格闲置来源上限约束 | `V/in_game/common/pop_types/00_default.txt:114,170,200`；`V/main_menu/common/static_modifiers/location.txt:17`。不能证明每月实际转职量或施工期间提前招工。 |
| `Location.GetPromoteValue` | GUI 地点，`CFixedPoint` | 数值；实际量/能力、单位和周期未确认 | `G:85770`。没有经过验证的数值桥接和后台运行证据，不替换现有速度公式。 |
| `Location.GetEffectiveUnEmployedValue(PopType)` | GUI 地点，`CFixedPoint` | 原版界面将其文本对应项用作当前可用；扣减公式未确认 | `G:84804`；`V/in_game/gui/shared/location_tooltips.gui:6396`。不能直接认定与后台闲置查询相同。 |
| `Location.GetExpectedUnEmployedValue(PopType)` | GUI 地点，`CFixedPoint` | 界面区分含建设需求的可用值；允许负数判断，单位及公式未核准 | `G:84846`；`location_tooltips.gui:6353–6412`。不新增截断、扣减或数值桥接。 |
| `Location.GetCivilConstructionsNeededPopsValue(PopType)` | GUI 地点，`CFixedPoint` | 界面单列队列用工；RGO、升级、阶层工程覆盖未确认 | `G:84450`；`location_tooltips.gui:6412`。不重复扣除，也不声称后台已扣除。 |
| 升级资格/员工转换 | 后台 `building_can_be_upgraded_by`，加提取的前身关系 | 升级资格有文档；员工是否自动转换阶层没有证据 | `D/triggers.log:2508`。按已确认规则跨阶层不抵扣，同阶层暂沿旧规则；旧岗位容量不等于实际保留员工。 |

就业提示界面支持“预计可用包含队列需求”的调查假设，但不证明其与两个后台闲置接口的关系。本轮没有把 getter 名字或界面布局推断直接写成计算公式。

当前原版转职图没有自转职边，奴隶也不是劳工的直接转职来源。因此当前 RGO 直接就业人口（劳工、满足原版开关的奴隶）与直接转职来源没有同阶层交集；这只是定义核查，不能证明没有其他空缺岗位吸收这些人。每地点一项 Mod 工程及已有民用建造的拦截仍保留，不能把这两条限制当作全部劳动力竞争已正确处理的证明。

## 在建产能能力表

| 数据/接口 | 作用域、环境与类型 | 数值口径和限制 | 证据与降级处理 |
| --- | --- | --- | --- |
| `every_location_in_market`、`every_buildings_in_location` | 后台，市场→地点→建筑 | 提供超出 Mod 自身工程的枚举路径；队列专属对象、外资/阶层工程完整可见性未实测 | `D/effects.log:2530,1690`。不声称工程覆盖完整。 |
| `building_level`、`building_levels_under_construction` | 后台建筑，数值 | 等级数，不是工程唯一身份和产量 | `D/triggers.log:2551,2557`。0 级新建对象、升级重叠未验证。 |
| `num_civil_constructions` | 后台地点，数值 | 民用工程数量，不是带类型的工程列表 | `D/triggers.log:8728`。现有 RGO 数量用民用工程减建筑在建等级，余量语义尚未核准，不能用来新建精确产能记录。 |
| `location`、`owner`、`building_type`、地点 `market` | 后台作用域链接 | 可定位地点、所有者、类型、市场；市场所有者不等于建筑所有者 | `D/event_targets.log:1106,1163,1425,1486` 及仓库已有调用。逐对象关联，不用玩家国家代替。 |
| `Location.GetCivilConstructions` | GUI 集合，`[unregistered]` | 原版 GUI 枚举 `Construction`；全市场覆盖、无人操作枚举未确认 | `G:84438`；`location_tooltips.gui:6430`。未添加桥接。 |
| `Construction.GetID/GetKey/GetBuilding/GetCountry/IsRGO` | GUI；int32、CString、Building/Country 链接、bool | 有身份/归属/类型线索；ID 跨读档稳定性及复用规则未知 | `G:53506,53518,53380,53386,53698`。不伪造稳定身份，不据此声称已去重。 |
| `Construction.GetDurationInDays/GetDurationInDaysIncludingQueue/GetProgress/GetFinishedDateIncludingQueue` | GUI；int32、int32、float、CString | 名称指向天数/进度，但总时长与剩余时长、进度范围、停工及排队行为未确认；完工日期为文本 | `G:53464,53470,53560,53488`。不自行推导剩余工期，不解析文本。 |
| `Building.GetLevelsUnderConstruction/GetLevelsUnderUpgrade` | GUI；int32、CFixedPoint | 在建/升级等级，但替代方向及两者重叠未知 | `G:44902,44908`。不直接转成净增等级。 |
| `building_employed_amount/building_employment_size_amount` | 后台建筑，数值 | 文档分别称有效就业人数、最大工人数 | `D/triggers.log:2527,2533`。人数/有效人数、单位及未来等级适用方式待测。 |
| `Building.GetEmployed/CalcEmploymentPercent` | GUI，CFixedPoint | 当前就业读数，不代表未来满就业 | `G:44734,44674`。需核对与后台值的比例。 |
| `Building.GetWorkersRequired/GetMaxWorkersRequired/GetEmploymentSize` | GUI，CString | 格式化文字 | `G:45088,44938,44746`。不作为运行时数值来源。 |
| `Building.GetProductionMethods`、`any_production_method_of_building` | GUI 集合；后台方法迭代器 | 后台文档明确说 **available**，不等于实际激活的方法 | `G:44992`；`D/triggers.log:1895`。现有每槽首个可行配方继续仅视为代理。 |
| `Building.GetEffectiveOutput(ProductionMethod)` | GUI 建筑，CFixedPoint | 原版实际建筑产出绑定；是否包含全部就业/效率/接入修正及统计周期仍需对照 | `G:44722`；有效 GUI 使用 `V/in_game/gui/shared/production_method_details.gui:234–244`。参数是生产方式，不是商品 ID；不再自行乘效率。 |
| `Building.GetBuildingProductionEfficiency(Arg0)`、`building_efficiency` | GUI 数值/后台地点数值 | 有当地效率接口；参数和完整倍率链未确认 | `G:44692`；`D/triggers.log:2521`。不以全国统一固定产量代替。 |
| `GoodsDemandEntry.GetValue × ProductionMethod.GetInputScale(Building)` | GUI 数值乘积 | 原版用其显示该方法的投入量；仅配方基础用量不够 | `G:71208,105022`；`production_method_details.gui:160–170`。周期、缩放和未来等级适用性待核准。 |
| `ActiveProductionMethod.GetActiveInputScale/GetOutputLevel` | GUI，CFixedPoint | 是数值，但数量/倍率含义及对象寿命未知 | `G:36529,36547`。不直接解释为商品产量。 |
| `building_goods_input/building_produced_goods` | 后台建筑，数值/商品判定 | 前者参数说明不足；后者仅判断生产某商品 | `D/triggers.log:2539,2586`。不构成经验证的分商品增量预测。 |
| `BuildingCandidate.GetActiveInputs/GetActiveOutputs` | GUI 候选对象集合，`[unregistered]` | 候选语义及元素类型未说明；找到的生产侧栏使用已被注释 | `G:45219,45225`；`V/in_game/gui/production_lateralview.gui:2920,2959`。不能认定为可用的完工后净增量接口。 |
| `GetBuildOrExpandBuildingCost/GetBuildingTypeProfitInLocation/GetBuildingTypeIncomeToOwnerInLocation` | GUI 全局函数，CFixedPoint | 仓库已有费用/利润/所有者收入桥接；不是商品数量 | `G:3715,3769,3757`；`generator.py:render_engine_queue_gui`。保留安全门槛，不用金钱除价格反推物量。 |
| `goods_supply_in_market/goods_demand_in_market` | 后台市场，数值 | 商品供需；精确周期、刷新顺序、贸易及建材需求覆盖未由导出说明 | `D/triggers.log:4222,4205`。既有使用保留，不加入未经核准的未来流量。 |
| `market_price/produced_in_market/traded_in_market/stockpile_in_market` | 后台市场→value | 分别为价格、生产量、贸易量、库存；周期/方向说明不足 | `D/event_targets.log:1364–1398`。库存不能加到流量；市场总量不能冒充项目净增量。 |
| `total_effective_goods_production_buildings` | 后台国家，数值 | 明确是生产某商品的有效建筑等级数 | `D/triggers.log:10577`。排除作为商品产量。 |

本轮没有建立经过验证的候选增量产出路径。上述接口足以指导下一步只读核验，但不足以宣称已能精确预测未来产能。新 GUI 绑定的面板关闭、切换地点、无人操作、读档、多国家与异步回调表现均未验证，也未接入生产路径。

## 已实施修正与状态兼容

1. 优化扫描与实时脚本值共用升级岗位抵扣函数。只有新旧岗位阶层集合相同，才抵扣两者岗位数较小值。跨阶层前身仍保留原来的选择顺序，但抵扣为 0，不能跳过它后抵扣另一个同阶层前身。多种前身共存时原有排序是否与原版实际替代完全一致仍待核验。
2. 普通建筑两个审批回调都在预留资金之前调用一次实时 `eu5ab_has_local_workforce`，覆盖供需审批、利润候选收集和利润胜出者最终审批。先清除扫描转职缓存，再按当前闲置、来源、速度、期限与岗位需求检查。劳动力保护开关继续有效。
3. RGO 原有路径已通过 `eu5ab_try_construct_rgo_need` → `eu5ab_rgo_expansion_allowed` → `eu5ab_rgo_workforce_allowed` 实时检查，且不复用普通建筑转职缓存，因此保留此路径。
4. 保留月度扫描和地点内短期缓存，不新增人口历史或假设施工期间提前转职。0～96 个月从评估时起算，0 个月没有未来转职贡献。
5. 审批缺工使用现有劳动力拒绝计数。它表示模型判断供给不足，不伪称已识别原版真实原因。阶层不符、岗位竞争、来源/期限限制等更细诊断仍需足够证据；前三候选的人口数字仍是扫描快照，不是保存下来的审批实测。

只新增两个调用内标志 `eu5ab_validation_workforce_checked/passed`，进入和退出审批均清理；没有新增持久历史或存档 schema，不要求状态迁移，不修改玩家设置。已有存档下一次扫描/回调使用新规则。审批后的异步 GUI 实际建造窗口仍按此前决定延期，本轮不声称原子开工复核。

## 未完成范围与后续顺序

转职仍是修正项能力估算，受当前直接来源上限约束。自然增长和迁移是“未建模”，不是“观测为零”。实际转职实现率、已有岗位吸收及队列扣减仍未核准，因此没有添加额外竞争惩罚。同阶层抵扣仍依赖旧岗位容量，不代表已测量保留员工。

在建产能反馈尚未实施。没有添加未经确认的开关默认值、时间分组、产能记录、置信度倍率或评分系数。下一步须验证逐项目净产出/投入、实际生产方式、就业和效率、队列覆盖/身份及完工与市场刷新的先后关系；再做快照汇总、批准到在建的去重、两种策略的有限重排。原版收益门槛与当前原料可用性检查继续独立保留。

## 验证记录

自动测试执行生成的脚本分支，并注入原版读数。覆盖全部支持建筑的扫描/实时一致性，同/跨阶层及多前身升级，人数边界，零期限，来源上限，零值缓存标志，扫描后人口/来源/速度/期限变化，关闭保护，重复回调，两种策略及原有安全门槛相对顺序。不能以这些离线测试证明原版接口语义。

本轮结果（Python 3.14.5，启用本机原版数据）：

- `python -B -m unittest tests.test_workforce_runtime tests.test_queue_validation_runtime tests.test_queue_recovery_runtime`：**22 项通过**。
- 全套 `unittest` discovery：**执行 581 项，0 个断言失败，3 个初始化错误，0 项跳过**。缺少的历史夹具为 `tests/fixtures/candidate_collection_before.txt`、`score_short_circuit_before.txt`、`scan_bucket_before_f2.txt`；`git ls-tree` 确认基线提交没有跟踪这些文件。对应三个测试类未执行，不能称全套通过。首次沙箱运行还遇到临时目录权限错误，正常权限复跑后这部分错误消失。
- 生成器检查和本地化检查通过；**74/74** 个生成文件与源码一致。其他九种语言继续按已有规则对缺失/变更翻译回退为英语，包括本次更新的两条帮助文本。
- 再生成发现原有海军迁移说明漏了一条映射，已补上显式映射，使生成 GUI 保持基线提交的绑定；专项 GUI 隔离测试通过，没有改动总督行为或生成的总督 GUI。
- `git diff --check`：通过。

**本轮没有游戏内对照及同档性能测量**；用户选择暂不添加核验入口。原版调用耗时、帧耗时和新增绑定可靠性均未测，Python 测试耗时不是游戏性能。已知结构性增量是每个符合审批条件的回调增加一次实时劳动力门槛、两个临时标志；没有全国/全市场扫描或持久历史。完整 Goal 仍需剩余人口口径与在建产能的运行时证据，不能因 Python 测试通过而标记完成。
