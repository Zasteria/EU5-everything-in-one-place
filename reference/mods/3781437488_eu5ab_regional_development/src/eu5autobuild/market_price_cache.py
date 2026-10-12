"""Monthly country cache for market-by-good candidate screening facts.

The ordinary worker intentionally spans days 2-22. These snapshots therefore
trade intra-scan freshness for one native market-price read, and one upstream
shortage evaluation, per country/market/good in the monthly scan. Quote
validation shares prepared price entries, while missing entries still fall
back to the live native value.
"""

from .food_infrastructure import RGO_BOOST_GOODS


LOCATION = "scope:eu5ab_candidate_location"
BUILDING = "scope:eu5ab_candidate_building"
ACTIVE = "eu5ab_worker_screen_active"


def price_map(good: str) -> str:
    return f"eu5ab_scan_market_price_{good}"


def price_ready_map(good: str) -> str:
    return price_map(good) + "_ready"


def price_value(good: str) -> str:
    return f"eu5ab_market_price_{good}"


def upstream_map(good: str) -> str:
    return f"eu5ab_scan_market_upstream_shortage_{good}"


def upstream_trigger(good: str) -> str:
    return f"eu5ab_market_upstream_shortage_{good}"


def _outputs_by_building(models) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for building, model in models.items():
        goods = {good for slot in model.slots for method in slot for good in method.outputs}
        goods.update(RGO_BOOST_GOODS.get(building, ()))
        if goods:
            result[building] = goods
    return result


def render(models, catalog, rules, *, required_goods: set[str]) -> tuple[str, str, str]:
    outputs = _outputs_by_building(models)
    upstream_goods = set(rules.input_goods) & set(catalog.source_buildings_by_good)
    goods = sorted(upstream_goods | {good for values in outputs.values() for good in values})

    effects = ["# Monthly market x good snapshots used by the initial worker scan.",
               "eu5ab_clear_scan_market_cache = {"]
    for good in goods:
        effects += [f"\tclear_variable_map = {price_map(good)}",
                    f"\tclear_variable_map = {price_ready_map(good)}"]
        if good in upstream_goods:
            effects.append(f"\tclear_variable_map = {upstream_map(good)}")
    effects += ["}", ""]

    values: list[str] = []
    triggers: list[str] = []
    for good in goods:
        native = f'"{LOCATION}.market.market_price(goods:{good})"'
        effects += [
            f"eu5ab_prepare_market_price_{good} = {{",
            "\tif = {",
            f"\t\tlimit = {{ {LOCATION} = {{ exists = market owner = {{ NOT = {{ is_key_in_variable_map = {{ name = {price_ready_map(good)} target = {LOCATION}.market }} }} }} }} }}",
            f"\t\t{LOCATION}.owner = {{",
            f"\t\t\tadd_to_variable_map = {{ name = {price_map(good)} key = {LOCATION}.market value = {native} }}",
            f"\t\t\tadd_to_variable_map = {{ name = {price_ready_map(good)} key = {LOCATION}.market value = 1 }}",
            "\t\t}",
            "\t}",
            "}", "",
        ]
        values += [
            f"{price_value(good)} = {{",
            "\tvalue = 0",
            "\tif = {",
            f"\t\tlimit = {{ {LOCATION}.owner = {{ is_key_in_variable_map = {{ name = {price_ready_map(good)} target = {LOCATION}.market }} }} }}",
            f"\t\t{LOCATION}.owner = {{",
            f"\t\t\tif = {{ limit = {{ is_key_in_variable_map = {{ name = {price_map(good)} target = {LOCATION}.market }} }} add = \"variable_map({price_map(good)}|{LOCATION}.market)\" }}",
            "\t\t}",
            "\t}",
            f"\telse = {{ value = {native} }}",
            "}", "",
        ]

        if good not in upstream_goods:
            continue
        live = upstream_trigger(good) + "_live"
        triggers += [
            f"{live} = {{",
            f"\teu5ab_market_needs_{good} = yes",
            "\tOR = {",
            "\t\tAND = {",
            f"\t\t\teu5ab_market_effective_demand_{good} > 0",
            f"\t\t\t\"{LOCATION}.market.goods_supply_in_market(goods:{good})\" < {{ value = eu5ab_market_effective_demand_{good} multiply = {rules.thresholds.goods_shortage_supply_ratio} }}",
            "\t\t}",
            f"\t\t{price_value(good)} > {{ value = \"default_price(goods:{good})\" multiply = eu5ab_global_price_max_ratio }}",
            "\t}",
            "}",
            f"{upstream_trigger(good)} = {{",
            "\tOR = {",
            "\t\tAND = {",
            f"\t\t\t{LOCATION} = {{ has_variable = {ACTIVE}",
            f"\t\t\t\towner = {{ is_key_in_variable_map = {{ name = {upstream_map(good)} target = {LOCATION}.market }} \"variable_map({upstream_map(good)}|{LOCATION}.market)\" = 2 }}",
            "\t\t\t}",
            "\t\t}",
            "\t\tAND = {",
            f"\t\t\tNOT = {{ {LOCATION} = {{ has_variable = {ACTIVE} owner = {{ is_key_in_variable_map = {{ name = {upstream_map(good)} target = {LOCATION}.market }} }} }} }}",
            f"\t\t\t{live} = yes",
            "\t\t}",
            "\t}",
            "}", "",
        ]
        effects += [
            f"eu5ab_prepare_market_upstream_shortage_{good} = {{",
            f"\teu5ab_prepare_market_price_{good} = yes",
            "\tif = {",
            f"\t\tlimit = {{ {LOCATION} = {{ exists = market owner = {{ NOT = {{ is_key_in_variable_map = {{ name = {upstream_map(good)} target = {LOCATION}.market }} }} }} }} }}",
            f"\t\t{LOCATION}.owner = {{ add_to_variable_map = {{ name = {upstream_map(good)} key = {LOCATION}.market value = 1 }} }}",
            f"\t\tif = {{ limit = {{ {live} = yes }} {LOCATION}.owner = {{ add_to_variable_map = {{ name = {upstream_map(good)} key = {LOCATION}.market value = 2 }} }} }}",
            "\t}",
            "}", "",
        ]

    # Auxiliary price readers need definitions, not additional monthly snapshots.
    for good in sorted(required_goods - set(goods)):
        values += [
            f"{price_value(good)} = {{",
            f'\tvalue = "{LOCATION}.market.market_price(goods:{good})"',
            "}", "",
        ]

    effects += ["eu5ab_prepare_candidate_market_prices = {", "\tswitch = {", "\t\ttrigger = this"]
    for building, building_goods in sorted(outputs.items()):
        effects += [f"\t\tbuilding_type:{building} = {{",
                    *(f"\t\t\teu5ab_prepare_market_price_{good} = yes" for good in sorted(building_goods)),
                    "\t\t}"]
    effects += ["\t}", "}", ""]

    effects += ["eu5ab_prepare_candidate_upstream_market_cache = {", "\tswitch = {", "\t\ttrigger = this"]
    for building, building_goods in sorted(outputs.items()):
        relevant = sorted(building_goods & upstream_goods)
        if relevant:
            effects += [f"\t\tbuilding_type:{building} = {{",
                        *(f"\t\t\teu5ab_prepare_market_upstream_shortage_{good} = yes" for good in relevant),
                        "\t\t}"]
    effects += ["\t}", "}", ""]

    return "\n".join(effects) + "\n", "\n".join(triggers) + "\n", "\n".join(values) + "\n"
