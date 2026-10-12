"""Local-market output prices shared by planning, final ranking and admission.

Each output is weighted by quantity times its base price, never current price.
The native engine uses five decimal fixed point: retain a positive quantum for
an eligible price arbitrarily close to the floor, and discount signed ranks.
"""

from dataclasses import dataclass
import math

from . import building_capacity
from .market_price_cache import price_value
from .food_infrastructure import RGO_BOOST_GOODS
from .rgo_automation import high_price_factor, price_factor, raw_goods


QUANTUM = 0.00001
LOCATION = "scope:eu5ab_candidate_location"


@dataclass(frozen=True)
class OutputPrice:
    quantity: float
    base_price: float
    market_price: float | None


def assess(outputs: tuple[OutputPrice, ...], floor: float, high: float,
           *, emergency: bool = False) -> tuple[float, float]:
    """Return low-price coefficient and high-price factor; empty means neutral."""
    if not outputs:
        return 1.0, 0.0
    if not all(math.isfinite(x) for x in (floor, high)):
        return 0.0, 0.0
    weight = low = bonus = 0.0
    for output in outputs:
        if (output.market_price is None or
                not all(math.isfinite(x) for x in
                        (output.quantity, output.base_price, output.market_price)) or
                output.quantity <= 0 or output.base_price <= 0 or output.market_price < 0):
            return 0.0, 0.0
        current = output.quantity * output.base_price
        if not math.isfinite(current):
            return 0.0, 0.0
        percent = output.market_price / output.base_price * 100
        weight += current
        low += current * price_factor(percent, floor, emergency)
        bonus += current * high_price_factor(percent, high)
    return (max(QUANTUM, low / weight), bonus / weight) if low > 0 else (0.0, 0.0)


def price_goods(models, rules) -> set[str]:
    """Goods referenced by the output-price helpers, including uncached goods."""
    return (set(raw_goods()) | set(rules.essential_goods) | set(rules.input_goods) |
            {g for m in models.values() for s in m.slots for p in s for g in p.outputs} |
            {g for gs in RGO_BOOST_GOODS.values() for g in gs})


def render(models, rules) -> tuple[str, str]:
    triggers, values = [], []
    for good in sorted(price_goods(models, rules)):
        price = price_value(good)
        base = f'"default_price(goods:{good})"'
        floor = f"{LOCATION}.owner.var:eu5ab_global_price_min"
        high = f"{LOCATION}.owner.var:eu5ab_global_price_max"
        key = f"eu5ab_output_{good}"
        triggers += [f"{key}_valid = {{ {LOCATION} = {{ exists = market }} {base} > 0 {price} >= 0 }}"]
        boosts = [f"AND = {{ this = building_type:{b} {LOCATION} = {{ raw_material_output > 0 raw_material = goods:{good} }} }}"
                  for b, gs in RGO_BOOST_GOODS.items() if b in models and good in gs]
        triggers += [f"eu5ab_output_supports_{good} = {{ OR = {{ eu5ab_recipe_produces_{good} = yes {' '.join(boosts)} }} }}"]
        values += [f'''{key}_low = {{
    value = 0
    if = {{
        limit = {{ {key}_valid = yes {price} > {{ value = {base} multiply = {floor} divide = 100 }} }}
        value = 1
        if = {{
            limit = {{ {floor} < 100 {price} < {base} }}
            value = {price}
            subtract = {{ value = {base} multiply = {floor} divide = 100 }}
            divide = {{ value = {base} multiply = {{ value = 100 subtract = {floor} }} divide = 100 min = 0.00001 }}
            min = 0.00001
            max = 1
        }}
    }}
}}
{key}_high = {{
    value = 0
    if = {{
        limit = {{ {key}_valid = yes {price} > {base} }}
        value = 1
        if = {{
            limit = {{ {high} > 100 }}
            value = {price}
            subtract = {base}
            divide = {base}
            multiply = 100
            divide = {{ value = {high} subtract = 100 }}
            max = 1
        }}
    }}
}}
''']
    # The chosen recipe is the only source of traded output identity.
    cases = {p: [] for p in ("weight", "low_weight", "high_weight")}
    valid_cases = []
    for building, model in sorted(models.items()):
        body = {p: [] for p in cases}
        validity = []
        for index, slot in enumerate(model.slots):
            if any(method.outputs for method in slot):
                validity.append(f"eu5ab_recipe_{building}_{index}_selected > 0")
            for method_index, method in enumerate(slot, 1):
                selected = f"eu5ab_recipe_{building}_{index}_selected = {method_index}"
                if method.outputs:
                    checks = " ".join(f"eu5ab_output_{g}_valid = yes" for g in method.outputs)
                    validity.append(f"OR = {{ NOT = {{ {selected} }} AND = {{ {checks} }} }}")
                for prop in cases:
                    additions = []
                    for good, quantity in method.outputs.items():
                        factor = f" multiply = eu5ab_output_{good}_{'low' if prop == 'low_weight' else 'high'}" if prop != "weight" else ""
                        addition = f'add = {{ value = "default_price(goods:{good})" multiply = {quantity:g}{factor}'
                        if prop == "low_weight":
                            addition += " min = 0.00001 }"
                            addition = f"if = {{ limit = {{ eu5ab_output_{good}_low > 0 }} {addition} }}"
                        else:
                            addition += " }"
                        additions.append(addition)
                    if additions:
                        body[prop].append(f"if = {{ limit = {{ {selected} }} {' '.join(additions)} }}")
        if building in RGO_BOOST_GOODS:
            for good in RGO_BOOST_GOODS[building]:
                condition = f"{LOCATION} = {{ raw_material_output > 0 raw_material = goods:{good} }}"
                validity.append(f"OR = {{ NOT = {{ {condition} }} eu5ab_output_{good}_valid = yes }}")
                for prop in cases:
                    factor = f" multiply = eu5ab_output_{good}_{'low' if prop == 'low_weight' else 'high'}" if prop != "weight" else ""
                    body[prop].append(f'if = {{ limit = {{ {condition} }} add = {{ value = "default_price(goods:{good})"{factor} }} }}')
        valid_cases.append(f"building_type:{building} = {{ {' '.join(validity) or 'always = yes'} }}")
        for prop in cases:
            if body[prop]:
                # Script values support conditional chains, not effect switch.
                branch = 'else_if' if cases[prop] else 'if'
                cases[prop].append(f"{branch} = {{ limit = {{ this = building_type:{building} }} {' '.join(body[prop])} }}")
    triggers += ["eu5ab_output_price_data_valid = { switch = { trigger = this fallback = { always = no } " + " ".join(valid_cases) + " } }",
                 "eu5ab_output_not_oversupplied = { eu5ab_output_price_data_valid = yes eu5ab_output_price_factor > 0 }"]
    for prop, body in cases.items():
        values += [f"eu5ab_output_{prop} = {{ value = 0 {' '.join(body)} }}"]
    values += [f'''eu5ab_output_price_factor = {{
    value = 0
    if = {{
        limit = {{ eu5ab_output_price_data_valid = yes }}
        value = 1
        if = {{
            limit = {{ eu5ab_output_weight > 0 NOT = {{ AND = {{ {LOCATION} = {{ eu5ab_food_emergency_enabled = yes }} eu5ab_candidate_produces_food = yes }} }} }}
            value = 0
            if = {{
                limit = {{ eu5ab_output_low_weight > 0 }}
                value = eu5ab_output_low_weight
                divide = eu5ab_output_weight
                min = 0.00001
                max = 1
            }}
        }}
    }}
}}
eu5ab_output_high_price_bonus = {{
    value = 0
    if = {{
        limit = {{ eu5ab_output_not_oversupplied = yes eu5ab_output_weight > 0 }}
        value = eu5ab_output_high_weight
        divide = eu5ab_output_weight
        multiply = {rules.rgo_scores.high_price}
    }}
}}
''']
    for name, score, factor in (
        ("eu5ab_price_adjusted_candidate_score", "eu5ab_unadjusted_candidate_score", "eu5ab_output_price_factor"),
        ("eu5ab_price_profit_rank", "eu5ab_profit_candidate_rank_value", f"scope:eu5ab_candidate_building.eu5ab_output_price_factor"),
    ):
        values += [f"{name} = {{", *building_capacity.signed_value_lines(score, factor), "}"]
    return "\n".join(triggers) + "\n", "\n".join(values) + "\n"
