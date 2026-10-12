"""Reviewed indirect food effects, distinct from goods production recipes.

Vanilla 1.4: irrigation, windmills, and city/village granaries. Forecasts hold
current stocks, prices and existing modifiers constant. Each new granary level
is deliberately approximated as +0.05 province preservation, regardless of jobs.
"""

import math
from decimal import Decimal, ROUND_DOWN


def windmill_incremental_revenue(revenue, output_factor):
    """Current employed RGO base * +0.10 * native location sale price."""
    if (revenue is None or output_factor is None
            or not math.isfinite(revenue) or not math.isfinite(output_factor)
            or revenue < 0 or output_factor <= 0):
        return None
    return revenue / output_factor * 0.1


def granary_monthly_savings(stock, base_decay, preservation):
    """Whole-province loss before/after +0.05; location rank is irrelevant.

    Match the observed five-decimal rate and loss truncation. Nonpositive base
    decay earns no preservation credit by policy; storage demand is independent.
    Negative preservation is unverified and cannot establish a return.
    """
    if base_decay is None or not math.isfinite(base_decay):
        return None
    if base_decay <= 0:
        return 0.0
    if any(v is None or not math.isfinite(v) for v in (stock, preservation)):
        return None
    if preservation < 0:
        return None
    stock, base, preservation = map(Decimal, map(str, (max(0, stock), base_decay, preservation)))
    unit = Decimal("0.00001")

    def loss(efficiency):
        rate = (base / (1 + efficiency)).quantize(unit, rounding=ROUND_DOWN)
        return (stock * rate).quantize(unit, rounding=ROUND_DOWN)

    return float(loss(preservation) - loss(preservation + Decimal("0.05")))

GRANARY_BUILDINGS = frozenset({"granary", "village_granary"})
NON_RECIPE_FOOD_BUILDINGS = GRANARY_BUILDINGS | {"irrigation_systems", "windmill"}
RGO_BOOST_GOODS = {"windmill": ("wheat", "rice", "millet")}
FOOD_BUILDING_GATES = (
    ("eu5ab_candidate_has_irrigation_demand", "eu5ab_diag_fail_irrigation_need"),
    ("eu5ab_candidate_storage_project_available", "eu5ab_diag_fail_storage_pending"),
    ("eu5ab_candidate_has_granary_demand", "eu5ab_diag_fail_granary_need"),
    ("eu5ab_candidate_has_windmill_demand", "eu5ab_diag_fail_windmill_need"),
)
FOOD_BUILDING_FINAL_GATES = FOOD_BUILDING_GATES + (
    ("eu5ab_candidate_has_granary_food_balance", "eu5ab_diag_fail_granary_need"),
    ("eu5ab_candidate_has_windmill_return", "eu5ab_diag_fail_windmill_need"),
)


def render_food_building_values(rules):
    crops = '\n'.join(f'''\tif = {{
\t\tlimit = {{ raw_material = goods:{good} }}
\t\tadd = modifier:local_{good}_output_modifier
\t\towner = {{ add = modifier:global_{good}_output_modifier }}
\t}}''' for good in RGO_BOOST_GOODS['windmill'])
    return f'''# Location scope. Native food_consumption is an engine value, not a per-capita guess.
# Same market as the former GUI read: the province capital, not this location.
eu5ab_location_food_price = {{
\tvalue = 0
\tif = {{ limit = {{ eu5ab_location_food_price_known = yes }}
\t\tvalue = province.capital.market.food_price
\t}}
}}
eu5ab_location_food_consumption = {{
\tvalue = food_consumption
\tmultiply = -1
\tmin = food_consumption
}}
eu5ab_province_food_reserve_target = {{
\tvalue = 0
\tprovince = {{ every_location_in_province = {{ add = eu5ab_location_food_consumption }} }}
\tmultiply = {rules.thresholds.food_reserve_months:g}
}}
# Native GetRawMaterialsOutput: employed base * max(0, 1 + these four modifiers).
eu5ab_windmill_output_factor = {{
\tvalue = 1
\tadd = modifier:local_raw_material_output
\towner = {{ add = modifier:global_raw_material_output }}
{crops}
\tmin = 0
}}
eu5ab_windmill_added_revenue = {{
\tvalue = 0
\tif = {{
\t\tlimit = {{ exists = scope:eu5ab_engine_rgo_revenue eu5ab_windmill_output_factor > 0 }}
\t\tvalue = scope:eu5ab_engine_rgo_revenue
\t\tdivide = eu5ab_windmill_output_factor
\t\tmultiply = 0.1
\t\tmin = 0
\t}}
}}
# Location scope, including non-capitals: base decay comes from the province
# capital and its owner, while preservation includes every location in the province.
eu5ab_province_food_decay_base = {{
\tvalue = 0
\tif = {{ limit = {{ exists = province.capital exists = province.capital.owner }}
\t\tprovince.capital = {{
\t\t\tvalue = modifier:local_food_decay
\t\t\towner = {{ add = modifier:global_food_decay }}
\t\t}}
\t}}
\tmin = 0
}}
eu5ab_province_food_preservation = {{
\tvalue = 0
\tif = {{ limit = {{ exists = province }}
\t\tprovince = {{ every_location_in_province = {{
\t\t\tadd = modifier:local_food_preservation_efficiency_modifier
\t\t}} }}
\t}}
}}
# Fixed-point division precedes multiplication, preserving the native rate/loss
# truncation. Current stock is identical on both sides; new capacity is not food.
eu5ab_province_monthly_food_decay = {{
\tvalue = 0
\tif = {{ limit = {{ exists = province eu5ab_province_food_preservation >= 0 }}
\t\tvalue = eu5ab_province_food_decay_base
\t\tdivide = {{ value = eu5ab_province_food_preservation add = 1 }}
\t\tmultiply = {{ value = province.province_food min = 0 }}
\t}}
}}
eu5ab_province_monthly_food_decay_after_granary = {{
\tvalue = 0
\tif = {{ limit = {{ exists = province eu5ab_province_food_preservation >= 0 }}
\t\tvalue = eu5ab_province_food_decay_base
\t\tdivide = {{ value = eu5ab_province_food_preservation add = 1.05 }}
\t\tmultiply = {{ value = province.province_food min = 0 }}
\t}}
}}
eu5ab_granary_monthly_food_saved = {{
\tvalue = eu5ab_province_monthly_food_decay
\tsubtract = eu5ab_province_monthly_food_decay_after_granary
\tmin = 0
}}
# Native recipe profit already subtracts operation costs. Add indirect value exactly once.
# Food savings are an opportunity value, never reported as tax income.
eu5ab_engine_adjusted_profit = {{
\tvalue = scope:eu5ab_engine_profit
\tif = {{
\t\tlimit = {{ scope:eu5ab_candidate_building = {{ this = building_type:windmill }} }}
\t\tadd = eu5ab_windmill_added_revenue
\t}}
\telse_if = {{
\t\tlimit = {{ scope:eu5ab_candidate_building = {{ eu5ab_is_granary = yes }} eu5ab_location_food_price_known = yes }}
\t\tadd = {{ value = eu5ab_granary_monthly_food_saved multiply = eu5ab_location_food_price }}
\t}}
}}
'''


def associated_goods(building_id, output_goods):
    """Goods whose prices may matter, including conditional RGO boosters."""
    return tuple(output_goods) + RGO_BOOST_GOODS.get(building_id, ())


def boost_support_lines(goods, catalog, indent):
    lines = []
    for building, supported in RGO_BOOST_GOODS.items():
        matching = sorted(set(goods).intersection(supported))
        if catalog.get(building) is None or not matching:
            continue
        lines += [f"{indent}AND = {{", f"{indent}\tthis = building_type:{building}",
                  f"{indent}\tscope:eu5ab_candidate_location = {{",
                  f"{indent}\t\traw_material_output > 0", f"{indent}\t\tOR = {{"]
        lines += [f"{indent}\t\t\traw_material = goods:{good}" for good in matching]
        lines += [f"{indent}\t\t}}", f"{indent}\t}}", f"{indent}}}"]
    return lines


def render_food_building_triggers(rules):
    granary_types = '\n'.join(f'\t\tthis = building_type:{building}'
                              for building in sorted(GRANARY_BUILDINGS))
    pending_granaries = '\n'.join(f'''\t\t\t\tAND = {{
\t\t\t\t\towner = {{ has_variable = eu5ab_q_active }}
\t\t\t\t\tis_target_in_variable_list = {{ name = eu5ab_q_approved_types target = building_type:{building} }}
\t\t\t\t\tNOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_confirmed_types target = building_type:{building} }} }}
\t\t\t\t}}'''
                                 for building in sorted(GRANARY_BUILDINGS))
    existing_granaries = '\n'.join(f'\t\t\t\t\t\tbuilding_type = building_type:{building}'
                                  for building in sorted(GRANARY_BUILDINGS))
    grain_cases = []
    for good in RGO_BOOST_GOODS["windmill"]:
        grain_cases.append(f'''\t\tAND = {{
\t\t\traw_material = goods:{good}
\t\t\tOR = {{
\t\t\t\teu5ab_irrigation_food_demand = yes
\t\t\t\tmarket = {{
\t\t\t\t\t"goods_supply_in_market(goods:{good})" < "goods_demand_in_market(goods:{good})"
\t\t\t\t}}
\t\t\t\tmarket = {{
\t\t\t\t\t"market_price(goods:{good})" > {{
\t\t\t\t\t\tvalue = "default_price(goods:{good})"
\t\t\t\t\t\tmultiply = {{ value = scope:eu5ab_candidate_location.owner.var:eu5ab_global_price_max divide = 100 }}
\t\t\t\t\t}}
\t\t\t\t}}
\t\t\t}}
\t\t}}''')
    return f'''# Building-type scope. Both granaries share province storage and preservation rules.
eu5ab_is_granary = {{
\tOR = {{
{granary_types}
\t}}
}}

# Existence of the capital's market distinguishes unknown from a genuine zero.
eu5ab_location_food_price_known = {{ exists = province.capital.market }}
# Granaries expand PROVINCE storage, not market food output.
# A final partial level is allowed; the next pass stops at the six-month target.
eu5ab_granary_storage_demand = {{
\texists = province
\tprovince = {{
\t\tprovince_max_food > 0
\t\tprovince_food_percentage >= {rules.thresholds.granary_full_ratio:g}
\t\tprovince_max_food < scope:eu5ab_candidate_location.eu5ab_province_food_reserve_target
\t}}
}}

eu5ab_granary_project_pending = {{
\tprovince = {{
\t\tany_location_in_province = {{
\t\t\tOR = {{
\t\t\t\tany_buildings_in_location = {{
\t\t\t\t\tOR = {{
{existing_granaries}
\t\t\t\t\t}}
\t\t\t\t\tbuilding_levels_under_construction > 0
\t\t\t\t}}
{pending_granaries}
\t\t\t}}
\t\t}}
\t}}
}}

eu5ab_candidate_storage_project_available = {{
\tOR = {{
\t\tNOT = {{ eu5ab_is_granary = yes }}
\t\tscope:eu5ab_candidate_location = {{ NOT = {{ eu5ab_granary_project_pending = yes }} }}
\t}}
}}

eu5ab_candidate_has_granary_demand = {{
\tOR = {{
\t\tNOT = {{ eu5ab_is_granary = yes }}
\t\tscope:eu5ab_candidate_location = {{
\t\t\tOR = {{ eu5ab_granary_storage_demand = yes eu5ab_granary_monthly_food_saved > 0 }}
\t\t}}
\t}}
}}

# Expansion needs a refill surplus; decay-only projects need a positive 5% annual return.
# Exports must not hide local surplus which could refill the added storage instead.
eu5ab_candidate_has_granary_food_balance = {{
\tOR = {{
\t\tNOT = {{ eu5ab_is_granary = yes }}
\t\tOR = {{
\t\t\tAND = {{
\t\t\t\tscope:eu5ab_candidate_location = {{ eu5ab_granary_storage_demand = yes }}
\t\t\t\tOR = {{
\t\t\t\t\tAND = {{ exists = scope:eu5ab_engine_province_food_balance scope:eu5ab_engine_province_food_balance > 0 }}
\t\t\t\t\tAND = {{ exists = scope:eu5ab_engine_province_food_natural scope:eu5ab_engine_province_food_natural > 0 }}
\t\t\t\t}}
\t\t\t}}
\t\t\tAND = {{
\t\t\t\tscope:eu5ab_candidate_location = {{ eu5ab_location_food_price_known = yes }}
\t\t\t\texists = scope:eu5ab_engine_profit
\t\t\t\texists = scope:eu5ab_engine_cost
\t\t\t\tscope:eu5ab_candidate_location.eu5ab_location_food_price > 0
\t\t\t\tscope:eu5ab_candidate_location = {{
\t\t\t\t\teu5ab_granary_monthly_food_saved > 0
\t\t\t\t\teu5ab_engine_adjusted_profit > 0
\t\t\t\t\teu5ab_engine_adjusted_profit >= {{ value = scope:eu5ab_engine_cost multiply = {rules.thresholds.engine_min_annual_return_ratio:g} divide = 12 }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
}}

# A producing local grain RGO and a reason to increase that crop are required.
# Its separate final return gate uses native sale revenue and recipe operating costs.
eu5ab_windmill_output_demand = {{
\texists = market
\traw_material_output > 0
\tOR = {{
{chr(10).join(grain_cases)}
\t}}
}}

eu5ab_candidate_has_windmill_demand = {{
\tOR = {{
\t\tNOT = {{ this = building_type:windmill }}
\t\tscope:eu5ab_candidate_location = {{ eu5ab_windmill_output_demand = yes }}
\t}}
}}

eu5ab_candidate_has_windmill_return = {{
\tOR = {{
\t\tNOT = {{ this = building_type:windmill }}
\t\tAND = {{
\t\t\texists = scope:eu5ab_engine_rgo_revenue
\t\t\texists = scope:eu5ab_engine_profit
\t\t\texists = scope:eu5ab_engine_cost
\t\t\tscope:eu5ab_engine_rgo_revenue > 0
\t\t\tscope:eu5ab_candidate_location = {{
\t\t\t\teu5ab_windmill_output_factor > 0
\t\t\t\teu5ab_engine_adjusted_profit > 0
\t\t\t\tOR = {{
\t\t\t\t\towner = {{ OR = {{ NOT = {{ has_variable = eu5ab_global_economic_metric }} var:eu5ab_global_economic_metric < 3 }} }}
\t\t\t\t\teu5ab_engine_adjusted_profit >= {{ value = scope:eu5ab_engine_cost multiply = {rules.thresholds.engine_min_annual_return_ratio:g} divide = 12 }}
\t\t\t\t}}
\t\t\t}}
\t\t}}
\t}}
}}
'''
