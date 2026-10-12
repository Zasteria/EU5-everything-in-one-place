# 游戏与 CMF 更新

[English](../en/game_updates.md) | [开发与校验](development.md)

更新工具比较原版与 CMF 数据，检查目录、规则和生成文件。数据同步、记录基线和游戏内验收是不同步骤；同步不会自动更改支持版本或发布 Mod。

## 命令

在仓库根目录设置实际安装路径，并根据安装版本填写版本标签：

```powershell
$env:EU5_GAME_ROOT = 'D:\SteamLibrary\steamapps\common\Europa Universalis V'
$env:EU5_CMF_ROOT = 'D:\Mods\Community Mod Framework'
python -B -m src.eu5autobuild.game_update audit --game-version '1.4-open-beta'
```

`--game-root`、`--cmf-root` 可覆盖环境变量；`--baseline`、`--output`、`--config` 可指定基线、报告目录与监测配置。工具另记录 Steam build ID 和 beta 分支，不根据 CMF 声明推测游戏版本。

| 操作 | 用途 |
| --- | --- |
| `audit` | 保存候选快照与差异报告，检查规则遗漏；不修改 Mod 或基线。 |
| `sync` | 先审计，再在临时目录生成和校验，仅写入变化文件；写入失败时回滚，不推进基线。 |
| `check` | 比较上游数据及磁盘中的全部生成产物；写报告，不修复 Mod 或推进基线。 |
| `baseline` | 数据和生成文件一致、新待决项已记录后，归档旧基线并记录当前观察；允许保留已登记的未完成适配。 |

审阅报告并完成必要修改后，按需运行：

```powershell
python -B -m src.eu5autobuild.game_update sync --game-version '1.4-open-beta'
python -B -m src.eu5autobuild.game_update check --game-version '1.4-open-beta'
python -B -m src.eu5autobuild.game_update baseline --game-version '1.4-open-beta'
```

退出码 `0` 表示命令成功，`2` 表示执行失败。`check` 返回 `1` 表示上游或版本身份变化、未完成适配、过期文件或缺少基线；须读报告确认原因。`audit` 成功写出报告时，即使仍有待办也可返回 `0`。

## 基线与报告

| 位置 | 用途 |
| --- | --- |
| `.upstream/baseline.json` | 当前上游观察基线 |
| `.upstream/history/` | 基线变更前的历史副本 |
| `.upstream/latest/candidate.json` | 本次候选观察 |
| `.upstream/latest/report.md`、`report.json` | 摘要与完整差异、来源及待办 |
| `.upstream/archives/<主题-日期>/` | 手动归档的完整历史审计，不替代当前基线 |

`.upstream/` 被 Git 忽略，完整游戏定义不随仓库提交。换机时按需复制基线和归档；首次采集无法还原已被 Steam 覆盖的旧数据。格式或提取器版本不匹配时，应迁移或另建基线，不能将格式差异误判为游戏变化。

工具不保存 Steam 账户信息，也不计算哈希。

## 规则来源与适配待办

- 建筑评分：[video_building_priorities.json](../../policies/video_building_priorities.json)。
- 风味模板：[templates.json](../../policies/templates.json)。
- 商品分组与有效规则：[automation_rules.json](../../policies/automation_rules.json)。
- 监测范围、决定理由和待办：[game_update_rules.json](../../policies/game_update_rules.json)，不作为第二套评分来源。

新建筑在 `building_decisions` 中标为 `reviewed`、`pending` 或 `excluded`。新商品应分组，或在 `generic_goods` 中说明使用通用规则的理由。`pending` 和 `open_adaptations` 中的未完成工作不会因推进基线而消失；完成实现及必要验证后再关闭。

监测保留建筑、商品、生产方式和相关解锁定义的运算符、重复键及顺序，忽略注释和空白。无法解析的岗位、建材或缺失的指定 CMF 符号会阻止同步。新增字段仍需人工审阅；CMF 符号存在性检查不等于 API 语义验证，海峡提取仅处理 `sea`，运河另行评估。

当前适配面向 1.4 新开局，不承担 1.3 存档迁移。游戏内验证的规则与方法见[游戏内验证指南](runtime_validation.md)。

CMF 2.5 的设置写入使用 `cmm_set_setting_value`，动作栏字段使用 `cmm_set_list_field_value`。这些接口仅保存值，不触发回调；更新时须保留 Mod 自身的设置同步、预算刷新及换国处理。控件类型元数据仍由注册逻辑维护。

## 工具与检查

仓库提供 [eu5autobuild-game-update Skill](../../.agents/skills/eu5autobuild-game-update/SKILL.md)，可通过 `$eu5autobuild-game-update` 调用。更新工具本身的定向检查为：

```powershell
python -B -m unittest tests.test_game_update -v
```

其他检查按实际修改选择，不默认执行全量回归。原生界面、队列进度、扣款和性能须在游戏中另外验证。
