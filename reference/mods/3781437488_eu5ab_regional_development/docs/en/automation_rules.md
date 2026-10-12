# Automated Build Rules

[简体中文](../zh-CN/automation_rules.md) | [Installation](../../README.md)

## Templates and national settings

Templates determine which locations participate and which buildings they favor. **Built-in Presets** provide ready-made development plans; **Custom Templates** let you adjust individual priorities. A custom priority of 0 disables a building. A preset may explicitly allow a building whose general rating is 0; **Copy as Player Template** carries it over at priority 1. See [Building Priorities](building_quality_priorities.md).

A normal click changes priority by 0.1, Ctrl+click by 0.5 and Shift+click by 1.0. Assign templates to locations, provinces or areas; clearing a location's policy removes its assignment.

Budgets, cash reserves, concurrent construction limits, strategy and safeguards are shared nationally through CMF Mod Settings.

| Setting | What it does |
| --- | --- |
| Annual budget | Set at the first accounting check of each year, using a fixed amount or 4, 6 or 8 times national gross monthly income. Changing settings recalculates the allowance; loading a save does not restore spent budget. |
| Budget exhaustion | Ordinary buildings and RGO expansions share the budget and record actual payments. The final project may exceed the remaining budget; further starts then stop. |
| Minimum cash reserve | Checks estimated costs, commitments to other projects and current cash before starting. Actual costs can change, so the reserve is not an absolute guarantee. |
| Concurrent construction limit | The setting adds slots to a base of one: 0 allows one project, 599 allows 600. Ordinary buildings and RGOs share the limit. |
| Location limits | A location needs a free native construction slot and must have finished its cooldown. A three-month cooldown starts when its batch is finished. |

Manual, estate and other-mod projects still occupy native construction slots, but are not directly added to this mod's project count. Mixed projects of the same type may be impossible to attribute precisely; existing mod counts are then retained conservatively.

## Monthly scheduling

1. On **days 2–22**, the mod checks locations assigned an enabled template in batches. Regular monthly checks evaluate up to 600 locations in detail and rotate the starting point.
2. Construction begins **no earlier than the 23rd**. Outstanding game readings can delay it.
3. Enabled food emergencies come first, followed by the chosen construction order. The default is **upgrade → expand ordinary building → expand RGO → new building**. Drag the types in settings to reorder them.
4. If a project cannot start, other candidates are tried. Further locations may be checked within the same month while slots and scanning allowance remain.
5. Unexecuted plans end at the month boundary. The next month starts a fresh check; existing construction and actual spending are retained.

Priority affects comparisons within a stage and construction type; it does not override the type order. Prices, costs and other readings gathered during checks are reused when arranging starts, so a plan may not reflect every subsequent change.

The report's last scan date records an actual check, not a reload or settlement. Rankings list projects using the selected strategy; several may come from one location.

## Strategy and performance

- **Supply-Demand** weighs shortages, food and material needs, industry links, local inputs and workforce risks. Each template-priority point adds 50 planning points. Ordinary expansion also gains one point per completed level of that building.
- **Predicted Profit** favors predicted monthly net returns, including windmill output gains and granary decay savings. Template priority provides a secondary bonus of about 1% per point, up to about 10%. Comparisons cover evaluated candidates, not every possible project in the country.

Advanced performance settings control how many candidates are retained per location and ordinary construction type, from 3 to 30. More candidates provide more alternatives but can take longer to check.

| Performance preset | Planning candidates | Profit candidates |
| --- | ---: | ---: |
| Conservative | 5 | 15 |
| Balanced | 4 | 12 |
| Maximum Throughput | 3 | 10 |

Limited candidate backfill is off by default and takes effect on the next scan. If the leading projects in a type all fail and no ordinary building has started at that location, it tries further candidates. Each location gets at most two extra attempts under planning or five under predicted profit, shared across ordinary construction types in that round. A successful start ends backfill; reloading does not replenish attempts.

### Industry preferences

Town rights favor projects matching the location's industrial role, adding up to 500 planning points at that location. Promote Industry adds up to another 500 points for buildings directly producing supported goods in your promoted area. It does not reward buildings merely consuming those goods or RGO expansion.

For multiple outputs, the bonus follows each good's share of output quantity × base price. The two preferences add independently and remain subject to templates, prices, workforce and other construction conditions. They do not grant rights, change production methods or guarantee profits. Predicted-profit ranking does not add the planning bonus again to final profit.

### Building capacity

Capacity use follows employment: ten building levels at 50% staffing occupy about five fully staffed levels.

| Fully staffed levels as a share of capacity | Effect on added buildings |
| --- | --- |
| Up to 95% | Normal comparison |
| Between 95% and 110% | Gradually lower priority; about 2/3 at 100% and 1/3 at 105% |
| At least 110% | Stop projects that add net capacity use |

A genuine one-level replacement can still be considered. An upgrade link without an available predecessor does not qualify. RGOs and buildings excluded from this capacity limit follow their own rules. Food emergencies do not override the limit.

The check uses capacity observed during evaluation, without anticipating employment in unfinished projects. The last approved project may take use above 110% on completion; it is not cancelled or demolished.

## Why a project did not start

Start with the Construction Report, then check these conditions:

| Condition | Requirement |
| --- | --- |
| Template and game rules | The template permits the building, it is unlocked and native location conditions are met. Special buildings also need the relevant setting enabled. |
| Construction and capacity | A free construction slot, completed cooldown and sufficient building capacity. |
| Workforce | With protection enabled, ordinary buildings must be expected to fill added jobs within the chosen period: 12 months by default, adjustable from 0 to 240. |
| Inputs | With protection enabled, supply of protected industrial inputs must reach 75% of demand. |
| Output prices | A price at or below the minimum stops the project. Multiple outputs are weighted by value; all must hit the floor to stop it. |
| Materials | The check includes materials committed to other projects this round, with a price ceiling of 150% of base price. |
| Finances | A positive remaining annual budget and enough cash for estimated costs, other commitments and the minimum reserve. |
| Returns and special needs | The selected return threshold and the separate irrigation, granary or windmill requirements. |

Turning workforce protection off removes the forecast deadline. Insufficient eligible idle workers then lower priority instead of preventing construction by themselves. Existing RGO jobs must still be fully staffed.

Prices between the minimum and base price gradually reduce priority. Above base price, the bonus grows until the high-price reference, then stops growing. **The high-price reference is not a maximum permitted price.** See [Prices and Market Construction](market_construction.md) for formulas.

### Inputs and additional construction

Expansion prefers the building's current production methods; new buildings and replacements use feasible recipe estimates. The mod does not change or lock production methods.

Upstream construction checks input shortages without requiring a downstream project to fail first. Market-shortage construction uses spare slots after the ordinary stages, comparing locations already checked this round that you own, share the market and manage with templates. Custom priorities of 0 remain disabled. Locations with existing projects can participate if slots remain.

Ordinary buildings and RGOs account for output already arranged but not fully in production, reducing repeated construction for the same shortage. Without a reliable output reference, this adjustment cannot be made and extra projects may be planned. See [Production Forecasts](production_forecast.md).

## Return thresholds and emergencies

| UI option | Requirement |
| --- | --- |
| Monthly Income > 0 | Positive predicted monthly income |
| Monthly Profit > 0 | Positive predicted monthly profit |
| Annualized Income Return ≥ 5% | Predicted monthly income at least construction cost × 5% ÷ 12 |
| Annualized Profit Return ≥ 5% | Predicted monthly profit at least construction cost × 5% ÷ 12 |

Both return thresholds are **5% annually**. Income is before operating costs, and forecasts do not guarantee a payback date. Public infrastructure with no goods output is exempt from ordinary production-return thresholds.

When the relevant safeguard is enabled, these conditions can waive ordinary production-return requirements:

| Situation | Eligible projects | Scheduled first |
| --- | --- | --- |
| Food projected to run out, or stocks at most 25% | Matching food producers | Yes; separate switches control the two conditions |
| Core construction-material supply at most 65% of demand | Matching material producers | No |
| Wartime military supply at most 65% of demand | Matching military producers | No |
| Upstream supply at most 65% of demand, blocking strategic buildings | Matching input producers | No |

Food safeguards also waive the relevant food projects' minimum-price and pending-output limits. Material and military exemptions do not include those waivers. Budget, workforce, capacity and native conditions still apply.

## Food buildings

### Irrigation

At least one condition must hold:

- The market is projected to run out of food, or stocks are at most 25% of capacity.
- Stocks are at most 50% and the monthly food balance is negative.
- Location population reaches 90% of population capacity.

Irrigation adds local food output and population capacity. It does not directly produce grain goods, so grain prices neither reward nor block it. High priority cannot bypass the need check. Other irrigation under construction is not yet deducted from the estimated need, so several locations may respond to the same shortage.

### Granaries and windmills

City and village granaries both serve **province food storage**. Either reason can justify construction:

- **More storage:** stocks reach 75% of capacity, capacity is below six months of resident consumption, and either local food production has a surplus or net inflow including market exchange is positive.
- **Less decay:** food savings valued at current prices plus the building's operating net return are positive and reach a 5% annual return on construction cost.

Only one granary project may be pending or under construction per province, shared across both types. Capital and non-capital savings both use province-wide preservation. Each new level is estimated to add five percentage points of preservation, holding current stocks and prices fixed. Preservation above 100% continues to have diminishing benefits. No decay saving is credited when base decay is non-positive or total preservation is negative; storage demand is checked separately. Granaries do not enter the emergency queue as food producers. See the [granary preservation formula](food_preservation.md) for the calculation.

Windmills require actual local wheat, rice or millet output, plus market food need, a shortage of that crop or a price above the high-price reference. They must also have positive marginal net returns; return-rate modes require 5% annually. The estimate accounts for existing output modifiers and operating costs. Food emergencies do not waive this requirement.

## RGO expansion

RGOs use their own ranking rather than the ordinary building return metric. Existing jobs must be fully staffed, and template, level, price, budget, reserve and construction conditions must pass.

| Workforce protection | RGO mode | Added-job check |
| --- | --- | --- |
| On | Relaxed (default) | No future staffing forecast |
| On | Consider Population | Default 180 months, adjustable from 0 to 1,200; 0 checks current available population only |
| Off | Relaxed | No forecast; insufficient eligible idle workers lower priority |

Forecasts use current promotion rates. Longer periods are more exposed to migration, rate changes and competing jobs. Peasants are potential recruits, not existing laborers.

For each good in a market, added construction slows as your pending output approaches the supply gap plus 10% of demand. It stops at the allowance; the last indivisible level may exceed it. Existing projects are retained. Completed but understaffed added capacity continues to affect the check. Ambiguous attribution in mixed manual queues makes ordinary RGO expansion wait conservatively.

During an enabled food emergency, food RGOs receive priority and waive minimum-price, low-price and pending-output limits. Existing jobs must still be full and other construction conditions still apply.

## Manual decisions and governor suggestions

**Replan This Month's Construction** is available on days 1–22 before that month's construction orders have begun. Confirmation re-evaluates all owned locations assigned an enabled template and replaces the unexecuted plan. It removes regular scanning and candidate-count limits, while retaining construction slots, budgets and other requirements.

The event stays open during calculation, then shows project count and estimated spending. Zero projects is a valid result. The plan uses settings and templates from the start of calculation; later edits do not alter it. Starts are arranged from the 23rd and normal checks resume next month. Large countries may take time.

**Reset Advanced Auto Build** keeps templates and settings but clears location assignments, reports, cooldowns, project tracking and spending records. After switching countries, it can restore that player's previously saved configuration. Templates must be assigned again. Existing construction continues and spent gold is not refunded.

The governor panel only recommends sites and relocations; it does not build, demolish or move seats. Local and naval suggestions are calculated separately and can be refreshed manually.

See [In-Game Validation Guide](runtime_validation.md) for in-game verification limits and [Development](development.md) for implementation entry points.
