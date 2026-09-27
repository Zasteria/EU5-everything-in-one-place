# Responsive Universalis

Performance & multiplayer-responsiveness mod for **Europa Universalis V** (built against **1.3.8**, targets `1.3.*`).

One defines-override file, no content changes: fewer simulation ticks, cheaper AI evaluation cycles, leaner AI pathfinding/trade budgets, calmer trade map.

## What it changes

All overrides live in [`loading_screen/common/defines/zz_responsive_universalis_defines.txt`](loading_screen/common/defines/zz_responsive_universalis_defines.txt) - every line documents the vanilla value.

| Area | Change | Effect |
|---|---|---|
| `NGame.HOUR_TICK` 2 → 6 | 4 sim ticks/day instead of 12 | ~3x less tick overhead; less tick lag at bounded speeds, faster days on speed 7 |
| `NAI.AI_PERFORMANCE_*` intervals | AI re-evaluates cabinet/reforms/policies/estates/scholars 2-4x less often | big cut in monthly-tick AI cost; AI reacts slightly slower to change |
| `NAI` sampling + pathfinding + trade budgets | smaller samples, tighter node limits, earlier trade cutoffs | cheaper AI decisions; marginally less optimal AI |
| `NMarket.MARKET_ASSIGNMENT_PERFORMANCE_FACTOR` 0.5 → 0.35 | cheaper market assignment | may affect protectionism for locations far from any market |
| `NTradeGraphics` wagon/ship caps roughly halved | ~60% fewer animated trade map objects + smaller per-frame route-scan budget | visual only - the map looks a bit calmer ([graphics defines file](loading_screen/common/defines/graphic/zz_responsive_universalis_graphics.txt)) |

## Install / enable

The repo lives at `T:\responsive-universalis` and is junctioned into the Paradox mod folder, so the launcher picks it up as a local mod:

1. Open the EU5 launcher → **DLC and Mods** → add **Responsive Universalis** to your playset.
2. Apply the playset and launch.

## Multiplayer notes

- **Every player must run the exact same playset** (this mod included) - mismatch = checksum mismatch = can't join / desync.
- Not ironman/achievement compatible (defines change the checksum). By design.
- Known desync trigger unrelated to mods: **all clients must use the same game language**.
- The in-game setting **"Maximum Ticks Lead"** (Settings → Game) governs how far the simulation may run ahead of the slowest client - worth experimenting with in your group.

## Options (separate mod entries - Paradox mods have no settings UI)

- **Aggressive Ticks (12h)** - [`submods/aggressive-ticks`](submods/aggressive-ticks): overrides only `HOUR_TICK` to 12 (2 sim ticks/day vs the main mod's 4). Maximum tick-cost reduction; combat phases, hourly morale, and event checks resolve in coarser 12-hour chunks. Enable it *in addition to* the main mod; its defines file sorts after the main mod's, so it wins.
- **Message Presets** - [`submods/message-presets`](submods/message-presets): adds three one-click preset buttons to the in-game message settings screen (**All Off / All On / Important Only**), applied instantly to all ~870 configurable message types - no restart, no 30 minutes of checkbox clicking. Vanilla's own *Reset to Default* button restores factory settings. The Important list is documented in [`docs/IMPORTANT_PRESET.md`](docs/IMPORTANT_PRESET.md). GUI+localization only - works standalone, independent of the performance mod. Rebuild after game patches with `python tools/build_message_presets_gui.py` (re-syncs the vanilla GUI copy).

## Tuning

- If the AI feels too passive, walk the `*_MONTHS_BETWEEN_UPDATES` values back toward vanilla.
- If you miss the busy trade roads, raise the `NTradeGraphics` values in the graphics defines file.

## Measuring

The game writes tick-timing telemetry to
`Documents/Paradox Interactive/Europa Universalis V/logs/performance_degradation.log` (CSV).
Compare average tick time before/after enabling the mod on the same save for a real A/B.

## Autosave frequency

Not a define - it's an engine-level user setting (`autosave`, options never/monthly/half-year/yearly exist in the engine). Check **Settings → Game** for an Autosave dropdown; a mod cannot override it.
