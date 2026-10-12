# Granary Preservation Formula and Limits

[简体中文](../zh-CN/food_preservation.md) | [Food Building Rules](automation_rules.md#food-buildings)

This page describes how the mod estimates granary preservation savings. See [Granaries and windmills](automation_rules.md#granaries-and-windmills) for storage demand, return requirements and province-wide construction limits. The implementation is in [food_infrastructure.py](../../src/eu5autobuild/food_infrastructure.py).

## Current formula

When total preservation is nonnegative, estimated monthly decay is calculated in this order:

```text
B = max(0, provincial capital local_food_decay + its owner's global_food_decay)
E = sum of actual local_food_preservation_efficiency_modifier across the province
F = max(0, current province stock)
r = trunc5(B / (1 + E))
D(E) = trunc5(F × r)
Estimated monthly food saved = max(0, D(E) − D(E + 0.05))
```

`trunc5` truncates to five decimals; `D` is the positive loss magnitude. Calculate the rate before multiplying by stock, preserving the game's fixed-point precision at each step.

## Rules and limits

- Capital and non-capital granaries use the same province-wide benefit calculation. Preservation includes modifiers from every location in the province.
- Each city or village granary level uses a rough preservation increment of `0.05`. Current stocks, prices and other modifiers remain fixed; added capacity is not counted as stored food.
- In this model, 100% preservation roughly halves positive base decay. Higher preservation continues to provide diminishing savings.
- The mod credits no decay savings when base decay is non-positive or total preservation is negative. Storage demand is checked separately.
- Indirect granary value is estimated monthly food saved multiplied by the current food price. It contributes to project comparisons and is not reported as tax income.

## Outstanding checks

- Native behavior with negative preservation, non-positive base decay and extreme preservation values.
- Actual marginal savings before and after controlled construction, compared with the fixed `+0.05` forecast.
- The complete automatic-start, payment, cancellation, reload and completion lifecycle, covered by the [In-Game Validation Guide](runtime_validation.md).
