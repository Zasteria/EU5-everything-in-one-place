# Ordinary Building Production Forecasts

[简体中文](../zh-CN/production_forecast.md) | [Prices and Market Construction](market_construction.md) | [In-Game Validation Guide](runtime_validation.md)

Ordinary producers and RGOs share pending supply by country, market and good to control later starts. Reservations do not change actual game supply or demand and do not cancel existing projects.

## Demand, allowance and ranking

Let `D` be current monthly demand, `F` confirmed added operating inputs not yet reflected in market demand, `S` current monthly supply and `P` pending monthly output:

```text
Effective demand D_eff = D + F
Allowance B = max(D_eff − S, 0) + 0.10 × D_eff
```

| Pending output | Treatment |
| --- | --- |
| `P = 0` | Factor 1; other conditions still apply |
| `0 < P < B` | Factor `1 − (P/B)²`, retaining minimum positive precision |
| `P > 0` and `P ≥ B` | Stop additions; the last indivisible level may cross the allowance |

Nonnegative scores multiply by the factor; negative scores divide by it with a numeric floor. Planning and final profit ranking each apply it once. Multiple outputs are weighted by positive net reference quantity × base price. Any positive output reaching its allowance blocks the project; mutually exclusive methods are not summed as simultaneous production.

Enabled food safeguards waive the curve and allowance while still recording output. Material and military return exemptions do not waive supply limits. Future inputs do not bypass price, return, input, workforce, budget or construction conditions.

## Register confirmed starts only

Each mod command registers at most the requested one level, confirmed by changes to exact building instances captured before the command. Later manual additions do not enlarge the record. Refresh and reload neither adopt native queues nor scan nationwide production.

When manual and mod work of the same type cannot be individually identified, manual work completes first and cancellations remove mod work first. Eligible mod records complete in registration order. Cancellation and rebuilding between observations may remain undetectable if physical totals do not change.

## Reference quantities

Each production slot needs one recognized current method. Missing, conflicting or unknown methods remain unknown. Reference quantities use:

```text
Static recipe quantity × reference efficiency × confirmed added mod levels
```

Expansion uses the original building's efficiency for the added portion. New buildings and upgrades prefer an existing, nationally owned, non-estate target type in the same location. Otherwise, they inspect only one matching reference location owned by the country in the same market. Without a valid reference, output stays unknown; the mod neither assumes efficiency nor allocates total location output among buildings.

Upgrades fix target efficiency, predecessor output and positive per-good replacement differences before starting. If the predecessor disappears during construction, its former deduction is restored once, avoiding another deduction after actual market supply has already fallen.

Projects with unknown references may still pass other conditions, but create no invented output or input reservations. This can allow extra first-wave construction. A valid method and efficiency read during the original post-completion protection period can establish the reference without extending its deadline. Valid zero and unknown remain distinct.

## Construction and commissioning

Known construction reservations last until completion, cancellation or ownership invalidation. They do not expire merely because a population-forecast period has elapsed.

After completion, remaining reservations equal net reference quantities × the vacancy share of added jobs. Expansion excludes existing jobs, and later manual additions do not enlarge records. Full staffing releases reservations even if the building lacks inputs or is closed. Later employment loss does not restore them. This is an employment approximation, not measured production.

| State at completion | Commissioning protection and location/type cooldown |
| --- | --- |
| Recorded period 0 | Remove construction reservations; add no extra protection or cooldown |
| Nonzero period, known reference | Use the recorded period from completion |
| Nonzero period, unknown reference | Use three months from completion, without adding the configured period; create goods reservations only after a valid read |

Full staffing can release reservations early; the cooldown keeps its original deadline. Separate completions have separate deadlines. New reads, reloads and later completions do not extend them. Expired records are removed even if understaffed and cannot be recreated from physical levels. Month-end deadlines are clamped to the target month's actual length.

## Changes and maintenance

Recipe changes update goods using saved efficiency and clear old reservations. Each refresh checks current methods once per building, while each project retains its own efficiency, deductions, release state and deadline. Only relevant goods are visited.

Market changes move valid reservations to the current market. Ownership loss, cancellation or invalid instances remove records. Daily maintenance runs while registered projects exist, independently of monthly scans and the new-construction switch, then stops when the last record disappears. Reload rebuilds indices and maintenance from saved quantities without adding projects or extending periods.

Old production-sampling fields are not converted into new projects, and old construction without confirmed mod origin is not adopted. Forecasts no longer depend on production-sampling animations, callbacks or retries; quotes and capacity still use their own game UI readers.

Windmills, granaries and irrigation retain [special rules](automation_rules.md#food-buildings), rather than treating indirect benefits as ordinary independent recipe output.

## Implementation and validation

- [production_reference.py](../../src/eu5autobuild/production_reference.py): current methods, efficiency and reference search.
- [production_projects.py](../../src/eu5autobuild/production_projects.py): confirmed quantities and mixed-queue attribution.
- [production_cohorts.py](../../src/eu5autobuild/production_cohorts.py): separate completions, staffing release and deadlines.
- [production_forecast.py](../../src/eu5autobuild/production_forecast.py): market totals and candidate reservations.

Offline tests execute generated scripts with injected native readings. Efficiency API syntax and semantics, first reads for closed or unstaffed buildings, completion/maintenance order, save persistence and performance still need [in-game validation](runtime_validation.md).
