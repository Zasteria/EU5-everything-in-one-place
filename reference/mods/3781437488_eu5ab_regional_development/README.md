# EU5 Advanced Auto Build

English | [简体中文](README.zh-CN.md)

An unofficial *Europa Universalis V* mod that automates construction in locations assigned a development template. It also recommends local and naval governor seats and relocations.

## Install and start

1. Use this repository as a local mod folder, or place `.metadata/`, `in_game/` and `main_menu/` together under `Paradox Interactive/Europa Universalis V/mod/<mod-folder>/` in your Documents directory. Use the actual location if Documents is redirected to OneDrive.
2. In the game's **Mods and DLCs** menu, add this mod and **Community Mod Framework (CMF)** to an editable playset and choose **Apply**. Playing does not require Python.
3. Load a save and open the panel from the CMF Action Bar. Set your budget and construction rules in CMF Mod Settings, then choose from **Built-in Presets** or create a custom template and assign it to locations, provinces or areas.
4. Use **Construction Report** to review starts and rejection reasons, and **Governor Recommendations** to review suggestions.

The current release is **0.9.7 beta**, for new campaigns on EU5 `1.4.*`, and requires CMF `2.5.*`. See the [mod metadata](.metadata/metadata.json) for version requirements.

## Documentation

- [Automated Build Rules](docs/en/automation_rules.md): templates, budgets, scheduling, food buildings and manual decisions.
- [Building Priorities](docs/en/building_quality_priorities.md): recommended ratings, sources and adjustments.
- [Development and Validation](docs/en/development.md): code entry points, generation, translations and focused checks.
- [Game and CMF Updates](docs/en/game_updates.md): upstream changes, synchronization and baselines.

## Contributing and license

Issues and pull requests are welcome. Bug reports should include game and CMF versions, reproduction steps, and relevant screenshots or logs. Published versions are on the repository's Releases page; the source version is in [pyproject.toml](pyproject.toml).

Building ratings draw on reviews and guides by [Shou Bianbian on Bilibili](https://space.bilibili.com/456154809). Developed with assistance from OpenAI's GPT-5.6-Sol (Sol 5.6) model. Licensed under the [MIT License](LICENSE).
