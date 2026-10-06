# Nobles Auto Marry - Continued (1.2)

A fix and continuation of [Nobles Auto Marry](https://steamcommunity.com/sharedfiles/filedetails/?id=3606305941) by Fart Shartley, updated to work with Europa Universalis V patch 1.2.

## What it does

Automatically pairs unmarried nobles (and optionally other estate types) for marriage each month, keeping your court populated without manual effort. Configure eligibility, population limits, and notification settings through an in-game configuration panel.

## Changes from the original mod

### v1.3 (1.2 update)
- Updated `supported_game_version` to `1.2.*`
- Fixed court limit not working: pop_limit now initialized to 150 by default and required for all marriage on_actions to fire
- Fixed heir's wife killed by culling: crown estate members now excluded from population control
- Fixed estate marriages (burghers, clergy, etc.) ignoring the pop limit
- Fixed "unlimited" config option accidentally disabling all marriages

### v1.2
- Fixed AI pop control crash (wrong variable scope)
- Fixed AI population limit being silently ignored
- Added `character_can_marry_trigger` checks for 1.1 compatibility
- Added culture restriction settings (primary only, accepted/tolerated, or unrestricted)

### v1.1
- Updated `supported_game_version` from `1.0.*` to `1.1.*`
- Fixed AI auto-marry on_actions never connected to `monthly_country_pulse`
- Added missing `hint_noble_auto_marry` localization keys
- Fixed a missing closing quote typo in `noble_auto_marry.1.t` localization
- Fixed royal marriage reminders ignoring "hide notifications"; added independent toggle

## Features (inherited from original)

- Automatically marries unmarried nobles aged 18–25 each month
- Three eligibility modes: Unrestricted, Selective (few married relatives), Dynastic Preservation (dynasty-based filter)
- Optional marriages for Burghers, Clergy, Peasants, Dhimmi, Tribes, Cossacks estates
- Royal marriage reminder for crown estate characters eligible for royal marriage (independently toggleable)
- Population control: optionally kill surplus courtiers above a configurable limit
- AI auto-marry support (disabled by default)
- Full in-game configuration panel via the Situations screen
- Works on existing saves (situation activates within one month)
- Localization: English, French, Korean, Russian, Simplified Chinese, Turkish

## Compatibility

Requires EU5 patch **1.2.x**. Pure script mod — no base game file overwrites. Compatible with most other mods unless they also overwrite `monthly_country_pulse` in `on_action`.

## Credits

Original mod by **Fart Shartley** (Steam: [3606305941](https://steamcommunity.com/sharedfiles/filedetails/?id=3606305941)). This version fixes compatibility and known bugs.
