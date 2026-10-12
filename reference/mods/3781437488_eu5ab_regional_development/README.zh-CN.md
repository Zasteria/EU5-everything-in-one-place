# EU5 Advanced Auto Build

[English](README.md) | 简体中文

一个非官方的《Europa Universalis V》（欧陆风云5）Mod。为地点应用发展模板后，自动安排建造；同时提供地方和海军总督的选址、迁移建议。

## 安装与上手

1. 将本仓库作为本地 Mod 目录，或将 `.metadata/`、`in_game/`、`main_menu/` 一并放入文档目录的 `Paradox Interactive/Europa Universalis V/mod/<Mod 文件夹名>/`。文档目录被 OneDrive 重定向时，使用实际位置。
2. 在游戏主菜单「模组和DLC」的可编辑播放集中加入本 Mod 与 **Community Mod Framework（CMF）**，点击「应用」。游玩不需要 Python。
3. 载入存档，从 CMF 操作栏打开面板。先在 CMF 模组设置中调整预算和建设规则，再选择风味模板或创建自定义模板，应用到地点、省份或地区。
4. 在「建造报告」查看开工结果和未开工原因；在「总督推荐」查看建议。

当前版本为 **0.9.7 beta**，面向 EU5 `1.4.*` 新开局，依赖 CMF `2.5.*`，以 [Mod 元数据](.metadata/metadata.json) 为准。

## 文档

- [自动建造规则](docs/zh-CN/automation_rules.md)：模板、预算、建造顺序、食物设施与手动决议。
- [建筑优先级](docs/zh-CN/building_quality_priorities.md)：推荐分数、来源和调整方法。
- [开发与校验](docs/zh-CN/development.md)：代码入口、生成、翻译与定向检查。
- [游戏与 CMF 更新](docs/zh-CN/game_updates.md)：上游变更、同步与版本基线。

## 贡献与许可

欢迎提交 Issue 或 Pull Request。问题报告请附游戏与 CMF 版本、复现步骤，以及相关截图或日志。已发布版本见仓库 Releases，源码版本见 [pyproject.toml](pyproject.toml)。

建筑评分参考 [Bilibili UP 主瘦扁扁](https://space.bilibili.com/456154809)的评测与攻略。本项目在 OpenAI GPT-5.6-Sol（Sol 5.6）模型协助下开发，采用 [MIT 许可证](LICENSE)。
