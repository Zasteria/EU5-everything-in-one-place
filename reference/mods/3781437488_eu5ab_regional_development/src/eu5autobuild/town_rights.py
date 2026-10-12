"""Local industrial intent from vanilla town rights.

These are ranking preferences, not estimates of the rights' economic return.
Sources: game/in_game/common/town_rights/*.txt. Matching uses the existing
first-feasible-method proxy, never the union of alternative production methods.
"""

from .food_infrastructure import GRANARY_BUILDINGS
from .production import LOCATION, selected_method_branches


MAX_BONUS = 500
SCORE_CACHE = "eu5ab_town_rights_candidate_score_cached"
SCORE_CACHE_BUILDING = "eu5ab_town_rights_candidate_score_building"
SCORE_CACHE_READY = "eu5ab_town_rights_candidate_score_ready"
OUTPUT_RIGHTS = {
    "royal_tooling_rights": ("tools",),
    "royal_jewelry_rights": ("jewelry",),
    "royal_naval_rights": ("naval_supplies", "tar"),
    "royal_textile_rights": ("cloth", "fine_cloth", "dyes"),
    "royal_weaponry_rights": ("weaponry", "firearms", "cannons"),
    "royal_book_rights": ("paper", "books", "dyes"),
    "royal_artisan_rights": ("furniture", "pottery", "leather"),
    "royal_brewing_rights": ("liquor", "beer", "wine"),
    "royal_masonry_rights": ("masonry", "glass"),
    "scandinavian_bergslag_privileges": ("tools",),
    "scandinavian_tar_privileges": ("tar", "naval_supplies"),
    "constantinopolitan_silk_monopoly_rights": ("silk", "cloth", "fine_cloth"),
}
BUILDING_RIGHTS = {
    "jewelry_guild": ("royal_jewelry_rights",),
    "cloth_guild": ("flemish_cloth_industries_right",),
    "fine_cloth_guild": ("flemish_cloth_industries_right",),
}
RGO_RIGHTS = (
    "mining_charter", "agrarian_community_town_right",
    "scandinavian_fishing_privileges", "scandinavian_bergslag_privileges",
    "upper_bergregal", "lower_bergregal", "furs_de_valencia_town_rights",
)
FOOD_RIGHTS = ("agrarian_community_town_right", "manorial_customals")
STORAGE_RIGHTS = ("granary_town", "imperial_breadbasket_rights")


def rights_condition(rights):
    return "OR = { " + " ".join(
        f"has_town_rights = town_rights_type:{right}" for right in sorted(set(rights))
    ) + " }"


def _value(name, body):
    return "\n".join([f"{name} = {{", "\tvalue = 0", *body, "}", ""])


def _when(condition, body, keyword="if"):
    return [f"\t{keyword} = {{ limit = {{ {condition} }}", *[f"\t\t{line}" for line in body], "\t}"]


def _candidate_score_data(models, rules):
    """Return supporting values and ordered, building-local score cases."""
    by_good = {}
    for right, goods in OUTPUT_RIGHTS.items():
        for good in goods:
            by_good.setdefault(good, set()).add(right)
    for good in rules.food_goods:
        by_good.setdefault(good, set()).update(FOOD_RIGHTS)

    values, cases = [], {}

    def add_case(building, condition, live_body, cached_body):
        cases.setdefault(building, []).append((condition, live_body, cached_body))

    for building, model in sorted(models.items()):
        supported = {g for slot in model.slots for method in slot for g, q in method.outputs.items()
                     if q > 0 and g in by_good}
        if not supported:
            continue
        total, matched = [], []
        for slot_index, slot in enumerate(model.slots):
            def amounts(method, matching=False):
                lines = []
                for good, quantity in method.outputs.items():
                    if quantity <= 0:
                        continue
                    amount = f'add = {{ value = "default_price(goods:{good})" min = 0 multiply = {quantity:g} }}'
                    if not matching:
                        lines.append(amount)
                    elif good in by_good:
                        lines.append(f"if = {{ limit = {{ {LOCATION} = {{ {rights_condition(by_good[good])} }} }} {amount} }}")
                return lines
            total += selected_method_branches(building, slot_index, slot, amounts)
            matched += selected_method_branches(building, slot_index, slot, lambda m: amounts(m, True))
        stem = f"eu5ab_town_rights_{building}"
        values += [_value(stem + "_total", total), _value(stem + "_matched", matched)]
        rights = set().union(*(by_good[g] for g in supported))
        add_case(building, f"{LOCATION} = {{ {rights_condition(rights)} }}", [
            f"if = {{ limit = {{ {stem}_total > 0 }} value = {stem}_matched divide = {stem}_total multiply = {MAX_BONUS} }}",
        ], [
            f"set_variable = {{ name = {SCORE_CACHE} value = {{",
            "\tvalue = 0",
            f"\tif = {{ limit = {{ prev.{stem}_total > 0 }} add = {{ value = prev.{stem}_matched divide = prev.{stem}_total multiply = {MAX_BONUS} }} }}",
            "} }",
        ])

    for building, rights in BUILDING_RIGHTS.items():
        if building in models:
            add_case(building, f"{LOCATION} = {{ {rights_condition(rights)} }}",
                     [f"min = {MAX_BONUS}"],
                     [f"set_variable = {{ name = {SCORE_CACHE} value = {MAX_BONUS} }}"])

    # Reviewed non-recipe food effects. Keep the existing demand gates, and
    # require an actually producing grain/food RGO for percentage boosters.
    food_rgo = "OR = { " + " ".join(f"raw_material = goods:{g}" for g in sorted(rules.food_goods)) + " }"
    for building, demand in (
        ("windmill", "eu5ab_windmill_output_demand = yes"),
        ("irrigation_systems", f"eu5ab_irrigation_food_demand = yes raw_material_output > 0 {food_rgo}"),
        ("forest_village", "always = yes"),  # rural_buildings: local_monthly_food = 1
    ):
        if building in models:
            add_case(building, f"{LOCATION} = {{ {rights_condition(FOOD_RIGHTS)} {demand} }}",
                     [f"min = {MAX_BONUS}"],
                     [f"set_variable = {{ name = {SCORE_CACHE} value = {MAX_BONUS} }}"])
    for building in sorted(GRANARY_BUILDINGS.intersection(models)):
        add_case(building, f"{LOCATION} = {{ {rights_condition(STORAGE_RIGHTS)} OR = {{ eu5ab_granary_storage_demand = yes eu5ab_granary_monthly_food_saved > 0 }} }}",
                 [f"min = {MAX_BONUS}"],
                 [f"set_variable = {{ name = {SCORE_CACHE} value = {MAX_BONUS} }}"])
    return values, cases, by_good


def render_town_rights_values(models, rules):
    """Building scope for normal projects; location scope for RGO scoring.

Output shares use quantity * vanilla base price (across all selected slots).
Each good is counted once even when several rights support it. Fixed project
support and output support use their maximum, so together cannot exceed 500.
"""
    values, cases_by_building, by_good = _candidate_score_data(models, rules)
    cases = []
    for building, building_cases in cases_by_building.items():
        for condition, live_body, _ in building_cases:
            cases += _when(f"this = building_type:{building} {condition}", live_body,
                           "if" if not cases else "else_if")
    # One native lookup rejects the common no-rights case before any dispatch.
    values.append(_value("eu5ab_town_rights_candidate_score_live", _when(
        f"{LOCATION} = {{ has_any_town_rights = yes }}", cases,
    ) + ["\tmin = 0", f"\tmax = {MAX_BONUS}"]))
    values.append(_value("eu5ab_town_rights_candidate_score", [
        "\tif = {",
        f"\t\tlimit = {{ {LOCATION} = {{ has_variable = {SCORE_CACHE_BUILDING} "
        f"var:{SCORE_CACHE_BUILDING} = prev has_variable = {SCORE_CACHE_READY} }} }}",
        f"\t\t{LOCATION} = {{ if = {{ limit = {{ has_variable = {SCORE_CACHE} }} add = var:{SCORE_CACHE} }} }}",
        "\t}",
        "\telse = { value = eu5ab_town_rights_candidate_score_live }",
        "\tmin = 0",
        f"\tmax = {MAX_BONUS}",
    ]))

    # RGO expansion is a separate project class; no building scope is needed.
    rgo = _when(rights_condition(RGO_RIGHTS), [f"value = {MAX_BONUS}"])
    for good, rights in sorted(by_good.items()):
        rgo += _when(f"raw_material = goods:{good} {rights_condition(rights)}", [f"min = {MAX_BONUS}"])
    values.append(_value("eu5ab_town_rights_rgo_score", [
        "\tif = { limit = { is_full_expanded_rgo = no }", *["\t" + line for line in rgo], "\t}",
        f"\tmax = {MAX_BONUS}",
    ]))
    return "\n".join(values)


def render_town_rights_effects(models, rules):
    """Prepare the candidate score with direct building-type dispatch."""
    _, cases_by_building, _ = _candidate_score_data(models, rules)
    lines = [
        "# Building scope. Cache belongs to the current candidate location only.",
        "eu5ab_prepare_town_rights_candidate_score = {",
        f"\t{LOCATION} = {{",
        f"\t\tremove_variable = {SCORE_CACHE}",
        f"\t\tset_variable = {{ name = {SCORE_CACHE_BUILDING} value = prev }}",
        f"\t\tset_variable = {SCORE_CACHE_READY}",
        "\t}",
        "\tif = {",
        f"\t\tlimit = {{ {LOCATION} = {{ has_any_town_rights = yes }} }}",
        "\t\tswitch = {",
        "\t\t\ttrigger = this",
    ]
    for building, building_cases in cases_by_building.items():
        lines.append(f"\t\t\tbuilding_type:{building} = {{")
        for index, (condition, _, cached_body) in enumerate(building_cases):
            lines += [
                f"\t\t\t\t{'if' if index == 0 else 'else_if'} = {{",
                f"\t\t\t\t\tlimit = {{ {condition} }}",
                f"\t\t\t\t\t{LOCATION} = {{",
                *(f"\t\t\t\t\t\t{line}" for line in cached_body),
                "\t\t\t\t\t}",
                "\t\t\t\t}",
            ]
        lines.append("\t\t\t}")
    lines += ["\t\t}", "\t}", "}", ""]
    return "\n".join(lines)
