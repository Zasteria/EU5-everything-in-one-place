# 游戏内验证指南

[English](../en/runtime_validation.md) | [开发与校验](development.md)

本页说明游戏内验证时应遵循的规则、性能采集方法和验证环境。

## 队列与升级规则

[rgo_queue.py](../../src/eu5autobuild/rgo_queue.py) 使用 `Location.GetMaxRGOWorkersUnderConstruction`。空民用队列按 0 处理；非空队列读数校验所有者、日期、队列总数和 RGO 等级，失效返回未知，不据此释放产能记录。等待期间的劳动力预留可使用保守上界，但不用于判断项目归属或取消。

民用总数和 `CountAllInLocation` 包含阶层、外资工程；`CountMyKindInLocation` 不等于地点总占用。[construction_slots.py](../../src/eu5autobuild/construction_slots.py) 检查地点上限与总占用。批次使用扫描结果，原生命令被拒绝时释放该项预留并继续，不额外等待开工前采样。混合工程的调度需推进日期比较实际进度。

[upgrade_queue.py](../../src/eu5autobuild/upgrade_queue.py) 在地点采样时读取 `Building.GetLevelsUnderUpgrade`。目标在建数与前身升级中数描述同一工程，不能相加。分类、容量豁免及旧岗位抵扣均要求还有未被预订的前身等级；职业不同时不抵扣。`building_type.employment_size` 已以千人为单位，不能再次除以 1000。

整数传递由 [gui_integer.py](../../src/eu5autobuild/gui_integer.py) 处理；`IntToFixedPoint` 返回的浮点值不能直接充当 `MakeScopeValue` 所需的固定点值。

## 产业、总督与决议规则

产业快照通过 `Country.GetIndustryPromotions` 与 `IndustryPromotion.GetArea/GetOwner/GetType` 获取，复用地点容量采样。漏采或过期数据只使当次偏好加零；不阻止普通筛选。撤销和换区在下一轮地点扫描刷新。

总督计算使用当前完整邻近度来源，包括特殊建筑、政策和临时效果；地方与海军分别只移动本类普通总督来源。名额扣除适用的特殊治所和在建占用，超过名额时不发布迁移建议。临时效果没有回调时靠周期刷新兜底；默认迁移门槛为 80%，仅提供建议。

手动决议通过本语言的名称识别专用入口，保留原生列表其他条目的行为。深算的「继续」启动计算但不选择原生事件选项，实际完成后才允许「完成」。日期跨月时未执行计划失效，事件应允许关闭。重置按玩家归属限定清理，保留模板与设置，清除地点分配、追踪和支出，不取消工程或退款。

## 性能采集与比较

1. 完全重启游戏加载修改。比较版本分别从同一份原始存档开始，保持国家、模板、设置、速度和日期区间一致。
2. 覆盖 2～22 日检查、23 日起开工及月底到次月。记录每个区间的检查量、实际开工地点与类型、未处理候选及预算；不能把少做工作当作单次提速。
3. 导出原生 profiler 的 CSV，并保留新产生的 `debug.log`、`error.log`。用 `python -B scripts/analyze_native_profile.py <报告.csv> --top 15` 分析。
4. 分开比较总耗时、调用次数和最大单次耗时。Inclusive Time 包含子调用，不能叠加为卡顿时长；毫秒累计值不等于单帧时间。
5. 最终性能对比关闭诊断探针，并记录实际帧时间或可定位日期的视频。保存与手动快照不计入采样区间。

[扫描探针](../../src/eu5autobuild/scan_probe.py)用于当前扫描量、回调和工作集中情况的性能复测，默认关闭，命令如下：

```text
effect eu5ab_probe_scan_start = yes
effect eu5ab_probe_scan_snapshot = yes
effect eu5ab_probe_scan_stop = yes
```

每轮只调用一次 `start`，在选定日期调用 `snapshot`，最后调用 `stop`。快照是累计计数，相邻差值才是区间增量；最大值不能相减。每天先导出 CSV，再采集快照，最后重置 profiler。GUI 在暂停时也可能返回，因此两种记录的边界会略有差异。

探针按启动时的自有地点统计，不限制施工；状态可能随存档保存，读回该存档后应停止或重新开始一轮。需要定位工作集中时，可调用 `effect eu5ab_probe_scan_trace = yes`，记录接下来 32 个有工作的诊断窗口；窗口并非精确渲染帧。

## 验证环境

完全重启游戏加载生成文件，再使用独立的原版 + CMF + EU5AB 测试组合。其他 UI Mod 的接口错误须按来源归因；文件热重载错误需重启复核。保留原始存档，使用副本进行建造、取消及日期推进。
