"""Invocation-local GUI validation; diagnostic order differs from gate order."""

from .food_infrastructure import FOOD_BUILDING_FINAL_GATES

PREFIX = "eu5ab_validation_"
FIELDS = ("inputs_checked", "inputs_passed", "economics_checked", "economics_passed",
          "materials_checked", "materials_passed", "emergency", "passed")


def render_effects() -> str:
    lines = ["eu5ab_clear_validation = {",
             *(f"\tremove_variable = {PREFIX}{name}" for name in FIELDS), "}", ""]
    for name, condition in (
        ("inputs", "scope:eu5ab_candidate_building = { eu5ab_inputs_available = yes }"),
        ("materials", "eu5ab_engine_construction_materials_available = yes"),
    ):
        lines += [f"eu5ab_ensure_validation_{name} = {{", "\tif = {",
                  f"\t\tlimit = {{ NOT = {{ has_variable = {PREFIX}{name}_checked }} }}",
                  f"\t\tif = {{ limit = {{ {condition} }} set_variable = {PREFIX}{name}_passed }}",
                  f"\t\tset_variable = {PREFIX}{name}_checked", "\t}", "}", ""]
    lines += ["""# Called only within one GUI invocation, before any reservation is changed.
eu5ab_ensure_validation_economics = {
    if = {
        limit = { NOT = { has_variable = eu5ab_validation_economics_checked } }
        if = {
            limit = { scope:eu5ab_engine_cost > 0 }
            if = {
                limit = { scope:eu5ab_candidate_building.eu5ab_recipe_expected_output_value <= 0 }
                set_variable = eu5ab_validation_economics_passed
            }
            else_if = {
                limit = { eu5ab_engine_candidate_passes_selected_metric = yes }
                set_variable = eu5ab_validation_economics_passed
            }
            else_if = {
                limit = { eu5ab_engine_candidate_has_emergency_demand = yes }
                set_variable = eu5ab_validation_economics_passed
                set_variable = eu5ab_validation_emergency
            }
        }
        set_variable = eu5ab_validation_economics_checked
    }
}
"""]
    for status, code in (("waiting", 10), ("approved", 11), ("confirmed", 12), ("rejected", 13)):
        lines += [f"eu5ab_report_candidate_{status} = {{", "    owner = {"]
        for rank in range(1, 4):
            lines += [f'''        if = {{ limit = {{
                exists = var:eu5ab_diag_top_{rank}_location var:eu5ab_diag_top_{rank}_location = prev
                exists = var:eu5ab_diag_top_{rank}_building var:eu5ab_diag_top_{rank}_building = scope:eu5ab_candidate_building
            }} set_variable = {{ name = eu5ab_diag_top_{rank}_reason value = {code} }} }}''']
        lines += ["    }", "}"]
    for status, code in (("waiting", 10), ("confirmed", 12)):
        lines += [f"eu5ab_report_rgo_{status} = {{", "    owner = {"]
        for rank in range(1, 4):
            lines += [f'''        if = {{ limit = {{ has_variable = eu5ab_diag_top_{rank}_kind
                exists = var:eu5ab_diag_top_{rank}_location }}
                if = {{ limit = {{ var:eu5ab_diag_top_{rank}_kind = 2 var:eu5ab_diag_top_{rank}_location = prev }}
                    set_variable = {{ name = eu5ab_diag_top_{rank}_reason value = {code} }} }}
            }}''']
        lines += ["    }", "}"]
    return "\n".join(lines)


def validation_lines(rules, *, profit: bool, actual_profit_mode: int,
                     can_build: str = 'scope:eu5ab_engine_can_build = yes') -> list[str]:
    """Keep cheap rejection, lazy gates, and the original failure precedence."""
    food = "\n        ".join(f"scope:eu5ab_candidate_building = {{ {gate} = yes }}"
                     for gate, _ in FOOD_BUILDING_FINAL_GATES)
    failed = "" if profit else "NOT = { is_target_in_variable_list = { name = eu5ab_q_failed_types target = scope:eu5ab_candidate_building } }"
    approve = "eu5ab_approve_engine_candidate = yes" if profit else """if = {
        limit = {
            scope:eu5ab_engine_country.var:eu5ab_global_candidate_ranking_mode = $PROFIT_MODE$
            NOT = { scope:eu5ab_engine_country = { has_variable = eu5ab_q_profit_selecting } }
        }
        eu5ab_record_actual_profit_candidate = yes
    }
    else = { eu5ab_approve_engine_candidate = yes }"""
    approve = approve.replace("$PROFIT_MODE$", str(actual_profit_mode))
    body = f"""eu5ab_clear_validation = yes
eu5ab_refresh_native_recipes = yes
scope:eu5ab_candidate_building = {{ eu5ab_prepare_recipe_score_snapshot = yes }}
if = {{
    limit = {{
        NOT = {{ has_variable = eu5ab_q_location_approved }}
        {failed}
        eu5ab_engine_candidate_in_current_priority_phase = yes
        eu5ab_engine_has_parallel_room = yes
        scope:eu5ab_engine_country = {{ eu5ab_q_outstanding_approvals_value < {{
            value = var:eu5ab_monthly_build_quota subtract = var:eu5ab_constructions_started_this_tick
        }} }}
        {can_build}
        eu5ab_engine_candidate_has_capacity = yes
        scope:eu5ab_candidate_building = {{
            eu5ab_candidate_route_allowed = yes
            eu5ab_has_local_workforce = yes
            eu5ab_output_not_oversupplied = yes
            eu5ab_candidate_pending_allowed = yes
        }}
        {food}
    }}
    eu5ab_ensure_validation_inputs = yes
    if = {{
        limit = {{ has_variable = eu5ab_validation_inputs_passed }}
        eu5ab_ensure_validation_economics = yes
        if = {{
            limit = {{
                has_variable = eu5ab_validation_economics_passed
                eu5ab_engine_candidate_has_actual_budget = yes
                eu5ab_engine_candidate_keeps_actual_cash_reserve = yes
            }}
            eu5ab_ensure_validation_materials = yes
            if = {{
                limit = {{ has_variable = eu5ab_validation_materials_passed }}
                set_variable = eu5ab_validation_passed
            }}
        }}
    }}
}}
if = {{
    limit = {{ has_variable = eu5ab_validation_passed }}
    if = {{ limit = {{ has_variable = eu5ab_validation_emergency }} set_variable = eu5ab_q_approved_emergency_override }}
    else = {{ remove_variable = eu5ab_q_approved_emergency_override }}
    {approve}
}}
else_if = {{
    limit = {{ NOT = {{ eu5ab_engine_candidate_has_capacity = yes }} }}
    if = {{
        limit = {{ has_variable = eu5ab_capacity_ready }}
        scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_diag_fail_building_capacity add = 1 }} }}
    }}
    else = {{ scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_diag_fail_capacity_unavailable add = 1 }} }} }}
}}
else_if = {{
    limit = {{ NOT = {{ {can_build} }} }}
    scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_diag_fail_vanilla add = 1 }} }}
}}
else_if = {{
    limit = {{ scope:eu5ab_candidate_building = {{ NOT = {{ eu5ab_candidate_pending_allowed = yes }} }} }}
    scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_diag_fail_pending_output add = 1 }} }}
}}
else_if = {{
    limit = {{ scope:eu5ab_candidate_building = {{ NOT = {{ eu5ab_output_not_oversupplied = yes }} }} }}
    scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_diag_fail_oversupply add = 1 }} }}
}}
"""
    for gate, counter in FOOD_BUILDING_FINAL_GATES:
        body += f"""else_if = {{
    limit = {{ scope:eu5ab_candidate_building = {{ NOT = {{ {gate} = yes }} }} }}
    scope:eu5ab_engine_country = {{ change_variable = {{ name = {counter} add = 1 }} }}
}}
"""
    # Diagnostics intentionally check economics before inputs, materials before
    # budget/cash. A main-path short circuit must not change the failure reason.
    body += """else = {
    eu5ab_ensure_validation_economics = yes
    if = {
        limit = { NOT = { has_variable = eu5ab_validation_economics_passed } }
        scope:eu5ab_engine_country = { change_variable = { name = eu5ab_diag_fail_engine_economics add = 1 } }
    }
    else = {
        eu5ab_ensure_validation_inputs = yes
        if = {
            limit = { NOT = { has_variable = eu5ab_validation_inputs_passed } }
            scope:eu5ab_engine_country = { change_variable = { name = eu5ab_diag_fail_inputs add = 1 } }
        }
        else = {
            eu5ab_ensure_validation_materials = yes
            if = {
                limit = { NOT = { has_variable = eu5ab_validation_materials_passed } }
                scope:eu5ab_engine_country = { change_variable = { name = eu5ab_diag_fail_construction_materials add = 1 } }
            }
            else_if = {
                limit = { NOT = { eu5ab_engine_candidate_has_actual_budget = yes } }
                scope:eu5ab_engine_country = { change_variable = { name = eu5ab_diag_fail_budget add = 1 } }
            }
            else_if = {
                limit = { NOT = { eu5ab_engine_candidate_keeps_actual_cash_reserve = yes } }
                scope:eu5ab_engine_country = { change_variable = { name = eu5ab_diag_fail_cash add = 1 } }
            }
        }
    }
}
if = { limit = { NOT = { has_variable = eu5ab_validation_passed } } eu5ab_report_candidate_rejected = yes }
eu5ab_clear_validation = yes
eu5ab_clear_recipe_score_snapshot = yes
"""
    return ["\t\t\t" + line.replace("    ", "\t") for line in body.splitlines() if line.strip()]
