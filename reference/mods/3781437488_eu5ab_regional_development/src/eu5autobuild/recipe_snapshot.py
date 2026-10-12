"""Candidate-local recipe attributes prepared immediately before scoring.

Production methods remain read-only approximations. The snapshot never survives
the current candidate, and normal callers retain the original live calculation.
"""

LOCATION = "scope:eu5ab_candidate_location"
BUILDING = "eu5ab_recipe_snapshot_building"
PROPERTIES = ("output_value", "input_cost", "raw_total", "raw_matched")
RANK_READY = "eu5ab_recipe_snapshot_rank_ready"
FILTER_SCORE_VALUES = ("eu5ab_output_weight", "eu5ab_output_low_weight", "eu5ab_output_price_factor")
TOWN_RIGHTS_SCORE_CACHE = (
    "eu5ab_town_rights_candidate_score_cached",
    "eu5ab_town_rights_candidate_score_building",
    "eu5ab_town_rights_candidate_score_ready",
)
# Dependency order matters: each stage reads only earlier, already-ready values.
SCORE_VALUES = (
    "eu5ab_output_weight", "eu5ab_output_low_weight", "eu5ab_output_high_weight",
    "eu5ab_output_price_factor", "eu5ab_output_high_price_bonus",
    "eu5ab_candidate_base_score", "eu5ab_candidate_current_labor_factor",
    "eu5ab_unadjusted_candidate_score", "eu5ab_price_adjusted_candidate_score",
    "eu5ab_candidate_pending_factor", "eu5ab_candidate_pending_preliminary_factor",
    "eu5ab_pending_adjusted_candidate_score", "eu5ab_candidate_capacity_factor",
)


def bind_score_values(text: str) -> str:
    """Keep live fallbacks, but reuse invocation-local stages when prepared."""
    import re
    for name in SCORE_VALUES:
        text, count = re.subn(rf"(?m)^{name} = ", name + "_live = ", text)
        if count != 1:
            raise ValueError(f"Expected one score definition for {name}, got {count}")
        text += "\n" + "\n".join(cached_value(name, name.removeprefix('eu5ab_'),
                                                 [f"value = {name}_live"]))
    return text


def field(prop: str) -> str:
    return f"eu5ab_recipe_snapshot_{prop}"


def cached_value(name: str, prop: str, live_body: list[str]) -> list[str]:
    return [
        f"{name} = {{", "\tvalue = 0", "\tif = {",
        f"\t\tlimit = {{ {LOCATION} = {{ has_variable = {BUILDING} "
        f"var:{BUILDING} = prev has_variable = {field(prop)}_ready }} }}",
        # EU5 can remove numeric zero variables. Readiness is independent of value.
        f"\t\tif = {{ limit = {{ {LOCATION} = {{ has_variable = {field(prop)} }} }} add = {LOCATION}.var:{field(prop)} }}",
        "\t}", "\telse = {",
        *("\t" + line for line in live_body), "\t}", "}", "",
    ]


def render_effects(models, *, score_buildings=()) -> str:
    slots = max((len(model.slots) for model in models.values()), default=0)
    properties = (*PROPERTIES, 'need_score', *(v.removeprefix('eu5ab_') for v in SCORE_VALUES))
    scratch = [BUILDING, RANK_READY, *(field(prop) for prop in properties),
               *(field(prop) + '_ready' for prop in properties),
               *(f"eu5ab_recipe_snapshot_slot_{i}" for i in range(slots)),
               *TOWN_RIGHTS_SCORE_CACHE]
    lines = ["eu5ab_clear_recipe_score_snapshot = {",
             *(f"\tremove_variable = {name}" for name in scratch), "}", "",
             "# Building scope. Never put mutable state on shared building types.",
             "eu5ab_prepare_recipe_screen_snapshot = {",
             f"\t{LOCATION} = {{ eu5ab_clear_recipe_score_snapshot = yes }}",
             "\tswitch = {", "\t\ttrigger = this"]
    ranking = ["eu5ab_complete_recipe_score_snapshot = {",
               f"\tif = {{ limit = {{ NOT = {{ {LOCATION} = {{ has_variable = {BUILDING} var:{BUILDING} = prev }} }} }} eu5ab_prepare_recipe_screen_snapshot = yes }}",
               f"\tif = {{ limit = {{ NOT = {{ {LOCATION} = {{ has_variable = {RANK_READY} }} }} }}",
               "\tswitch = {", "\t\ttrigger = this"]
    for building, model in sorted(models.items()):
        lines += [f"\t\tbuilding_type:{building} = {{", f"\t\t\t{LOCATION} = {{"]
        ranking += [f"\t\tbuilding_type:{building} = {{", f"\t\t\t{LOCATION} = {{"]
        for index, slot in enumerate(model.slots):
            if slot:
                lines.append(
                    f"\t\t\t\tset_variable = {{ name = eu5ab_recipe_snapshot_slot_{index} "
                    f"value = prev.eu5ab_recipe_{building}_{index}_live_selected }}")

        def prepare(prop, indent, model=model):
            result = [f"{indent}set_variable = {{ name = {field(prop)} value = {{", f"{indent}\tvalue = 0"]
            for index, slot in enumerate(model.slots):
                for method_index, method in enumerate(slot, 1):
                    if prop in ("output_value", "input_cost"):
                        goods = method.outputs if prop == "output_value" else method.inputs
                        body = [f'add = {{ value = "{LOCATION}.market.market_price(goods:{good})" multiply = {amount:g} }}'
                                for good, amount in goods.items()]
                    elif prop == "raw_total":
                        body = [f"add = {sum(method.raw_inputs.values()):g}"]
                    else:
                        body = [f"if = {{ limit = {{ {LOCATION}.province = {{ any_location_in_province = {{ raw_material = goods:{good} }} }} }} add = {amount:g} }}"
                                for good, amount in method.raw_inputs.items()]
                    result += [f"{indent}\t{'if' if method_index == 1 else 'else_if'} = {{",
                               f"{indent}\t\tlimit = {{ var:eu5ab_recipe_snapshot_slot_{index} = {method_index} }}",
                               *(f"{indent}\t\t{line}" for line in body), f"{indent}\t}}"]
            return [*result, f"{indent}}} }}", f"{indent}set_variable = {field(prop)}_ready"]

        lines += prepare("output_value", "\t\t\t\t")
        lines += [f"\t\t\t\tset_variable = {{ name = {BUILDING} value = prev }}"]
        ranking += prepare("input_cost", "\t\t\t\t")
        ranking += ["\t\t\t\tif = {", "\t\t\t\t\tlimit = { NOT = { prev.eu5ab_current_native_input_priority = 0 } }"]
        ranking += prepare("raw_total", "\t\t\t\t\t")
        ranking += ["\t\t\t\t\tif = {", f"\t\t\t\t\t\tlimit = {{ var:{field('raw_total')} > 0 }}"]
        ranking += prepare("raw_matched", "\t\t\t\t\t\t")
        ranking += ["\t\t\t\t\t}", "\t\t\t\t}"]
        if building in score_buildings:
            ranking += [f"\t\t\t\tset_variable = {{ name = {field('need_score')} value = prev.eu5ab_typed_need_score_{building} }}",
                      f"\t\t\t\tset_variable = {field('need_score')}_ready"]
        lines += ["\t\t\t}", "\t\t}"]
        ranking += [f"\t\t\t\tset_variable = {RANK_READY}", "\t\t\t}", "\t\t}"]
    lines += ["\t}", "}", ""]
    lines += ranking + ["\t}", "\t}", "}", "",
                       "eu5ab_prepare_recipe_score_snapshot = {",
                       "\teu5ab_prepare_recipe_screen_snapshot = yes",
                       "\teu5ab_complete_recipe_score_snapshot = yes", "}", ""]
    # Validation needs recipe attributes but no planning-score computation.
    # Only collection/ranking callers request these additional intermediates.
    lines += ["eu5ab_prepare_candidate_score_snapshot = {",
              "\teu5ab_complete_recipe_score_snapshot = yes",
              "\teu5ab_prepare_town_rights_candidate_score = yes", f"\t{LOCATION} = {{"]
    for value in SCORE_VALUES:
        name = field(value.removeprefix('eu5ab_'))
        lines += [f"\t\tif = {{ limit = {{ NOT = {{ has_variable = {name}_ready }} }}",
                  f"\t\t\tset_variable = {{ name = {name} value = prev.{value} }}",
                  f"\t\t\tset_variable = {name}_ready", "\t\t}"]
    lines += ["\t}", "}", ""]
    lines += ["eu5ab_prepare_candidate_filter_prices = {", f"\t{LOCATION} = {{"]
    for value in FILTER_SCORE_VALUES:
        name = field(value.removeprefix('eu5ab_'))
        lines += [f"\t\tset_variable = {{ name = {name} value = prev.{value} }}",
                  f"\t\tset_variable = {name}_ready"]
    lines += ["\t}", "}", ""]
    return "\n".join(lines)
