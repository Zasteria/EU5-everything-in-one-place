# 开发与校验

[English](../en/development.md) | [文档入口](../../README.zh-CN.md)

## 环境与生成

Python 版本与依赖见 [pyproject.toml](../../pyproject.toml)。核心工具使用标准库；可选的存档验证器另需 NumPy 和 Pillow。

在仓库根目录运行，将路径替换为实际游戏安装目录：

```powershell
$env:EU5_GAME_ROOT = 'D:\SteamLibrary\steamapps\common\Europa Universalis V'
python -B -m src.eu5autobuild.catalog_builder
python -B -m src.eu5autobuild.generator
```

安装目录须包含 `game/in_game/common`；命令行 `--game-root` 优先于环境变量。游戏或 CMF 更新应使用[更新工作流](game_updates.md)，先比较上游数据再同步。

目录生成器更新建筑目录、推荐评分与原产商品快照；Mod 生成器写入 `.metadata/`、`in_game/` 和 `main_menu/localization/`。编辑来源后重新生成并审阅差异，不只修改生成文件。

## 检查如何选择

日常修改只运行直接相关的最小检查。已通过的检查仅在后续改动影响该路径、出现新失败或仍有明确风险时重跑。测试模块的选择见 [tests/README.md](../../tests/README.md)。

回归测试按当前功能归类，同一流程的输入差异用命名子用例合并；不同生命周期边界保留独立覆盖。删除重复测试前，确认保留用例仍覆盖对应行为。兼容性场景使用精简、明确的构造数据，不依赖历史存档采样表；生成器测试保留语法、作用域、事件挂接和 GUI 绑定等结构契约，行为规则由对应运行测试验证。

| 改动 | 检查 |
| --- | --- |
| 建筑目录或评分 | `python -B -m src.eu5autobuild.catalog_builder --check`，需要游戏目录 |
| 生成脚本 | `python -B -m src.eu5autobuild.generator --check`，另选相关行为测试 |
| 界面文案或翻译 | `python -B -m src.eu5autobuild.localization_check`，无需游戏安装 |
| 上游版本或完整产物同步 | 更新工具的 `check`，见[命令说明](game_updates.md#命令) |
| 文档 | 检查本地链接、命令、双语对应关系和相关代码事实 |

两项 `--check` 都不写生成文件。`catalog_builder --check` 会比较目录与评分副本；`generator --check` 检查生成内容的括号并报告翻译覆盖，**不比较磁盘中的全部生成文件**。需要独立比较时可运行：

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

该比较忽略 BOM 和换行形式；本地化编码及游戏内、主菜单两份副本由 `localization_check` 检查。依赖原版数据的测试需要 `EU5_GAME_ROOT`，结果应记录失败和跳过项。离线测试使用注入的游戏读数，不能证明实际界面、引擎时序或性能已经通过。

日常生成和排查不计算哈希；只有明确要求正式发版或哈希校验时才计算必要产物，详见 [AGENTS.md](../../AGENTS.md)。

## 配置与文本来源

| 内容 | 来源 |
| --- | --- |
| 建筑目录与评分 | [catalog_builder.py](../../src/eu5autobuild/catalog_builder.py)、[评分依据](building_quality_priorities.md#来源与维护) |
| 风味模板 | [templates.json](../../policies/templates.json)，由 [policy.py](../../src/eu5autobuild/policy.py) 读取 |
| 规则、范围及默认值 | [rules.py](../../src/eu5autobuild/rules.py)、[automation_rules.json](../../policies/automation_rules.json)；CMF 设置由 [generator.py](../../src/eu5autobuild/generator.py) 的 `GLOBAL_RULE_DEFAULTS` 与注册逻辑生成 |
| 中英文文案 | [generator.py](../../src/eu5autobuild/generator.py) 的两种本地化函数，以及 [rgo_localization.py](../../src/eu5autobuild/rgo_localization.py)、[manual_decisions.py](../../src/eu5autobuild/manual_decisions.py)、[governor_generator.py](../../src/eu5autobuild/governor_generator.py)、[governor_layout_ui.py](../../src/eu5autobuild/governor_layout_ui.py) |
| 其他语言 | [翻译目录](../../localization/translations)，由 [localization.py](../../src/eu5autobuild/localization.py) 检查源文并生成 |
| 上游适配待办 | [game_update_rules.json](../../policies/game_update_rules.json) 的 `open_adaptations` |

界面中文使用「」和嵌套的『』，保留颜色、图标、动态数值及本地化引用。风味模板、自定义模板、复制为自定义模板、效率优先及其现有英文名称保持一致。描述应说明玩家能观察到的行为。

其他语言的条目保留中英文源文；译文缺失或源文变化时回退当前英文。只有实际审阅译文后才更新其源文记录，不通过替换源文来掩盖过期翻译。修改规则时同步中英文文档。

## 实现入口

| 功能 | 主要模块 |
| --- | --- |
| 月度扫描、预算与读档 | [generator.py](../../src/eu5autobuild/generator.py)、[annual_budget.py](../../src/eu5autobuild/annual_budget.py)、[scan_reserve.py](../../src/eu5autobuild/scan_reserve.py)、[save_resume.py](../../src/eu5autobuild/save_resume.py) |
| 普通建筑批量开工与补位 | [construction_batch.py](../../src/eu5autobuild/construction_batch.py)、[batch_backfill.py](../../src/eu5autobuild/batch_backfill.py) |
| 原产开工、计数与产能 | [rgo_batch.py](../../src/eu5autobuild/rgo_batch.py)、[rgo_queue.py](../../src/eu5autobuild/rgo_queue.py)、[rgo_pending.py](../../src/eu5autobuild/rgo_pending.py)、[rgo_cost.py](../../src/eu5autobuild/rgo_cost.py) |
| 并行槽位、容量与升级 | [construction_slots.py](../../src/eu5autobuild/construction_slots.py)、[building_capacity.py](../../src/eu5autobuild/building_capacity.py)、[upgrade_queue.py](../../src/eu5autobuild/upgrade_queue.py)、[worker_upgrades.py](../../src/eu5autobuild/worker_upgrades.py) |
| 价格、配方与市场补建 | [价格与市场补建](market_construction.md) |
| 工程产能与竣工保护 | [产能预估](production_forecast.md) |
| 食物设施与产业偏好 | [food_infrastructure.py](../../src/eu5autobuild/food_infrastructure.py)、[industry_promotion.py](../../src/eu5autobuild/industry_promotion.py) |
| 手动决议与玩家配置 | [manual_decisions.py](../../src/eu5autobuild/manual_decisions.py)、[decision_state.py](../../src/eu5autobuild/decision_state.py) |
| 总督推荐与刷新 | [governor_generator.py](../../src/eu5autobuild/governor_generator.py)、[governor_refresh.py](../../src/eu5autobuild/governor_refresh.py)、[governor_layout_generator.py](../../src/eu5autobuild/governor_layout_generator.py) |

维护时保留以下边界：

- 数值零可能不保存在游戏变量中；有效零与缺失数据须分别表示。
- 读档、旧回执和重复事件不能重复开工、扣预算或延长保护期限。
- 普通建筑与原产按逐项实际扣款记账；现金预检使用估价，末项可超年度预算。
- RGO 数量来自原生计数，不能以民用工程数减建筑数代替。升级目标在建数与前身升级中数不能相加。
- 修复未使用变量警告前，追踪真实读写、生成及消费路径，兼顾旧存档；不添加假读写或只为消除警告删除有效缓存。
- 手动决议覆盖了 `eventwindow.gui` 和 `decisions_lateralview.gui`。游戏更新后应对照 `src/eu5autobuild/assets/` 内的原版模板；其他 Mod 覆盖同名文件时需要合并。
- 修改内置海峡拓扑时同步提升 [governor_connections.py](../../src/eu5autobuild/governor_connections.py) 的 `STRAIT_SCHEMA`。

## 诊断与验证

[游戏内验证指南](runtime_validation.md)说明当前接口规则和性能采集方法。

`scripts/` 下的 `audit_game_log.py`、`audit_saved_production.py`、`validate_governor_save.py` 和 `analyze_native_profile.py` 分别用于日志、存档生产数据、总督传播和性能报告分析；先用 `--help` 查看参数。保留原始存档，实验使用副本。记录代码版本、未提交改动、游戏与 CMF 版本、命令和结果，避免将旧记录视为当前版本的通过证明。
