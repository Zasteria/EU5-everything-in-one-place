"""RGO preflight cost model; native gold movement remains the settlement source.

This is not a native quote accessor. The material-price curve and fixed-point
order need in-game calibration across resource categories and prices. Keep the
model isolated so calibration cannot change the construction accounting path.
"""

RGO_METHODS = ("mining", "farming", "hunting", "gathering", "forestry")


def render_rgo_cost_script_values(base_cost: int) -> str:
    lines = [
        "# Preflight estimate, not an engine quote. Source: src/eu5autobuild/rgo_cost.py.",
        "# Location scope. The batch screener caches this estimate; no location/goods iteration.",
        "eu5ab_rgo_category_cost_multiplier = {",
        "\tvalue = 1",
    ]
    for index, method in enumerate(RGO_METHODS):
        lines.extend([
            f"\t{'if' if index == 0 else 'else_if'} = {{",
            f"\t\tlimit = {{ raw_material = {{ goods_method = {method} }} }}",
            f"\t\tadd = owner.modifier:expand_rgo_{method}_cost_modifier",
            "\t}",
        ])
    lines.extend([
        "}",
        "",
        "eu5ab_rgo_material_price_ratio = {",
        "\tvalue = 1",
        "\tif = {",
        "\t\tlimit = { exists = market }",
        "\t\tif = {",
        "\t\t\tlimit = { raw_material = { goods_method = forestry } }",
        '\t\t\tvalue = "market.market_price(goods:masonry)"',
        '\t\t\tdivide = "default_price(goods:masonry)"',
        "\t\t}",
        "\t\telse = {",
        '\t\t\tvalue = "market.market_price(goods:lumber)"',
        '\t\t\tdivide = "default_price(goods:lumber)"',
        "\t\t}",
        "\t}",
        "}",
        "",
        "eu5ab_rgo_material_cost_multiplier = {",
        "\tvalue = eu5ab_rgo_material_price_ratio",
        "\tsubtract = 1",
        "\t# Provisional price curve; bounds are native NMarket defines.",
        "\tif = {",
        "\t\tlimit = { eu5ab_rgo_material_price_ratio < 1 }",
        "\t\tmultiply = 10",
        "\t\tdivide = 9",
        "\t}",
        "\telse = { divide = 2 }",
        '\tmin = "define:NMarket|MIN_PRICE_IMPACT"',
        '\tmax = "define:NMarket|MAX_PRICE_IMPACT"',
        "\tadd = 1",
        "}",
        "",
        "eu5ab_rgo_expansion_cost = {",
        "\t# Multiplication order reproduces the SWE 75.43575 calibration case",
        "\t# under five-decimal fixed-point arithmetic; not proof for all cases.",
        "\tvalue = 1",
        "\tadd = owner.inflation",
        "\tmultiply = eu5ab_rgo_material_cost_multiplier",
        f"\tmultiply = {base_cost}",
        "\tmultiply = {",
        '\t\tvalue = "default_price(raw_material)"',
        '\t\tmultiply = "define:NEconomy|GOODS_RGO_PRICE_SCALE"',
        '\t\tadd = "define:NEconomy|GOODS_RGO_BASE_COST"',
        "\t}",
        "\tmultiply = eu5ab_rgo_category_cost_multiplier",
        "}",
        "",
    ])
    return "\n".join(lines)


def render_rgo_cost_input_trigger() -> str:
    return "\n".join([
        "# Do not invent a price for unsupported/missing cost inputs.",
        "eu5ab_rgo_cost_inputs_available = {",
        "\texists = owner",
        "\texists = market",
        "\texists = raw_material",
        '\t"default_price(raw_material)" > 0',
        '\t"default_price(goods:lumber)" > 0',
        '\t"default_price(goods:masonry)" > 0',
        "\traw_material = {",
        "\t\tOR = {",
        *(f"\t\t\tgoods_method = {method}" for method in RGO_METHODS),
        "\t\t}",
        "\t}",
        "\towner.inflation >= 0",
        "\teu5ab_rgo_category_cost_multiplier > 0",
        "}",
        "",
    ])
