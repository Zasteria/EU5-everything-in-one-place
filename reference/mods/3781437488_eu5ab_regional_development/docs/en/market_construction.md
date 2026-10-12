# Prices and Market Construction

[简体中文](../zh-CN/market_construction.md) | [Build Rules](automation_rules.md) | [Production Forecasts](production_forecast.md)

This page describes price, recipe and additional-construction calculations. Ordinary buildings and RGOs use prices from the candidate location's market.

## Prices and ranking

Let `p` be current price as a percentage of base price, `L` the minimum and `H` the high-price reference:

| Condition | Treatment |
| --- | --- |
| `p ≤ L` | Stop new projects |
| `L < p < 100` with `L < 100` | Low-price factor `(p − L) / (100 − L)` |
| Above the minimum and `p ≥ 100` | Low-price factor 1 |
| `L ≥ 100` | Apply only the minimum-price gate |
| `H > 100` | Planning bonus `140 × clamp((p − 100) / (H − 100), 0, 1)` |
| `H ≤ 100` | Full 140-point bonus only when `p > 100` |

The high reference caps the bonus and cannot bypass the minimum. Multiple outputs are weighted by selected-recipe quantity × base price. An output at the floor contributes zero; all contributions must be zero to stop the building. Goods producers pause without valid market or price data; facilities with no goods output remain price-neutral.

Low-price factors multiply nonnegative scores and divide negative scores, preserving the direction of the penalty, minimum positive precision and a numeric floor. Planning and final profit ranking each apply the factor once. The 140-point bonus applies only to planning; native predicted returns already reflect prices in profit ranking. Actual shortages add their own bonus.

Enabled food safeguards waive minimum-price and low-price penalties for relevant food producers, while retaining valid-data and other construction requirements. Material and military return exemptions do not waive prices. Windmills use their actual local crop; granaries and irrigation follow special need rules.

## Recipes and industry preferences

Expansion prefers actual production methods. New buildings and replacements estimate available recipes, favoring supply-feasible and more economical choices. Ties preserve declaration order; when none is feasible, an estimate remains for input-shortage diagnostics. Actual methods are not replaced by estimates merely because they lack inputs or earn less. The mod does not change or lock methods.

An upstream source must be known to produce the target good: either its actual method does so, or every available alternative in a production slot does. An estimated tools recipe or positive native profit alone cannot prove that the completed building will produce tools.

The planning economic term uses native predicted profit divided by cost, with indirect returns added for windmills and granaries. Town rights and Promote Industry favor matching direct outputs by their base-price value share. These preferences are not actual profit and are not added again during final profit ranking.

## Where additional construction is considered

- Ordinary stages run first. Market construction compares only locations checked this round that you own, share the market and manage with templates.
- Built-in Presets may support industries outside their main focus, but explicit exclusions and custom priorities of 0 still apply.
- Upstream construction checks shortages independently of downstream candidate failure. Fully staffed factories short of inputs can still trigger it.
- Locations with ongoing projects can participate if slots remain. Upstream construction does not consume ordinary backfill's extra attempts.

Both paths, ordinary production and RGOs share pending output and future inputs for each country, market and good. Effective demand adds confirmed operating inputs not yet reflected in market demand. If both current and future demand are zero, no market construction is added. The allowance is the effective shortage plus 10% of effective demand. Pending output reduces ranking and stops additions at the allowance. See [Production Forecasts](production_forecast.md) for unknown references, commissioning protection and mixed-project attribution.

## Timing of checks and starts

Ordinary buildings and RGOs retain screened prices, workforce, costs and capacity. Before starting, they check ownership, cash, other reservations and available slots. Ordinary costs come from native quotes; RGO costs remain estimates. Cached market-goods readings are reused after the first read that month; uncached auxiliary goods retain live price reads.

Ordinary and RGO batches issue native commands and confirm results within the same script execution. Successful starts record the individual treasury delta against the annual budget. Failures release cash, materials, output and slot reservations and skip that candidate for the month. The final project may exceed the annual budget, after which remaining starts stop.

Ordinary buildings and RGOs share location slots. Native occupancy includes manual, estate and other civil work; unfinished construction departments do not provide slots early. Repeated expansions at one location have separate project records. Later processing refreshes affected supply and reservations rather than repeating the entire screening process.

## Implementation and validation

See [output_prices.py](../../src/eu5autobuild/output_prices.py) for prices, [native_recipes.py](../../src/eu5autobuild/native_recipes.py) for methods and [market_supply.py](../../src/eu5autobuild/market_supply.py) for reservations. Construction and tracking entry points are listed in [Development](development.md#implementation-entry-points).

Offline checks cover emitted gates, ranking and accounting. Actual quotes and payment timing, GUI delivery, mixed queues and high-speed operation still need [in-game validation](runtime_validation.md).
