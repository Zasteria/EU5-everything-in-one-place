"""Native staffed-building capacity, separate from structural project occupancy.

The GUI captures occupied capacity from the vanilla location tooltip; the
limit is read directly from the native modifier, after exact native comparison.
Workers capture one scan snapshot; validation reuses it, and firing does not
recheck employed capacity or parallel construction occupancy.
RGO and actual zero-occupancy replacements do not use this capacity discount.
"""

from decimal import Decimal, InvalidOperation, ROUND_DOWN
import math

from . import construction_slots, queue_bridge, rgo_queue, upgrade_queue, industry_promotion


QUANTUM = Decimal("0.00001")
# Stay within EU5's signed 64-bit fixed point range (five decimal places).
RANK_FLOOR = -90_000_000_000_000
CAPACITY_FIELDS = ("used", "limit", "ready", "open", "factor")
GUI_SCOPES = "eu5ab_engine_capacity_used " + construction_slots.GUI_SCOPES + ' ' + rgo_queue.GUI_SCOPES + ' eu5ab_industry_count'
FIRE_GUARD = '''
    owner = scope:eu5ab_engine_country
    owner = { eu5ab_queue_calendar_open = yes has_variable = eu5ab_q_active has_variable = eu5ab_q_fire NOT = { has_variable = eu5ab_scan_resume_after_load } }
    has_variable = eu5ab_q_location_approved
    has_variable = eu5ab_q_fire_requested
    NOT = { has_variable = eu5ab_q_fire_issued }
    has_variable = eu5ab_q_fire_quote_ready
    is_target_in_variable_list = { name = eu5ab_q_approved_types target = scope:eu5ab_candidate_building }
    NOT = { is_target_in_variable_list = { name = eu5ab_q_confirmed_types target = scope:eu5ab_candidate_building } }
    eu5ab_approved_candidate_keeps_cash_reserve = yes
''' + queue_bridge.COMPATIBLE + '''
    OR = { owner = { NOT = { has_variable = eu5ab_bridge_schema } }
        owner = { var:eu5ab_bridge_kind = 4 has_variable = eu5ab_bridge_data_received } }
'''
# Expanded in Python: new scripted triggers can be registered after their GUI
# consumers during filewatcher reload. Keep both gates and the callback aligned.
REQUEST_PENDING_CONDITIONS = """
    has_variable = eu5ab_capacity_requested
    has_variable = eu5ab_capacity_worker_country
    NOT = { has_variable = eu5ab_worker_complete }
    owner = var:eu5ab_capacity_worker_country
    has_variable = eu5ab_capacity_request
    var:eu5ab_capacity_month = owner.var:eu5ab_scan_month
    var:eu5ab_capacity_year = owner.var:eu5ab_scan_year
    owner = {
        has_variable = eu5ab_scan_active
        eu5ab_scan_month_current = yes
        NOT = { has_variable = eu5ab_scan_resume_after_load }
        is_target_in_variable_list = { name = eu5ab_worker_pending_locations target = prev }
    }
"""
RECEIPT_CURRENT = REQUEST_PENDING_CONDITIONS + '''
    exists = scope:eu5ab_capacity_ticket
    scope:eu5ab_capacity_ticket = var:eu5ab_capacity_request
'''


def readings_valid(used: float | None, limit: float | None) -> bool:
    try:
        if isinstance(used, bool) or isinstance(limit, bool):
            return False
        u, maximum = Decimal(str(used)), Decimal(str(limit))
        return u.is_finite() and maximum.is_finite() and u >= 0 and maximum > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def coefficient(used: float | None, limit: float | None) -> float:
    """Fail closed for unknown readings, preserving genuine zero occupancy."""
    try:
        if not readings_valid(used, limit):
            return 0.0
        u, maximum = Decimal(str(used)), Decimal(str(limit))
        if 100 * u >= 110 * maximum:
            return 0.0
        if 100 * u <= 95 * maximum:
            return 1.0
        # A positive ratio below the engine's resolution remains eligible.
        ratio = (u / maximum).quantize(QUANTUM, rounding=ROUND_DOWN)
        result = (Decimal("1.10") - ratio) / Decimal("0.15")
        return float(max(QUANTUM, result.quantize(QUANTUM, rounding=ROUND_DOWN)))
    except (InvalidOperation, TypeError, ValueError):
        return 0.0


def discount(score: float, factor: float) -> float | None:
    """Return no rank when blocked, and never improve a signed score."""
    if not math.isfinite(score) or not math.isfinite(factor) or not 0 < factor <= 1:
        return None
    if score >= 0:
        return score * factor
    if score < RANK_FLOOR:
        return score
    return max(float(RANK_FLOOR), score / factor)


def gui_arguments(*, replacement: bool = False, capacity_used: bool = True) -> str:
    result = (
        ".AddScope('eu5ab_engine_capacity_used', MakeScopeValue(Location.GetNumBuildingLevelsWithEmployment))"
    ) if capacity_used else ''
    if replacement:
        result += (
            ".AddScope('eu5ab_engine_replaced_building', "
            "BuildingType.GetObsoleteBuildingInLocation(Location.Self, GetPlayer.Self).MakeScope)"
        )
    return result + construction_slots.gui_arguments()


def render_values() -> str:
    return """
# Zero numeric variables may be absent; readiness is stored independently.
eu5ab_q_planned_spend_value = { value = 0 if = { limit = { has_variable = eu5ab_q_planned_spend } add = var:eu5ab_q_planned_spend } }
eu5ab_q_planned_budget_value = { value = 0 if = { limit = { has_variable = eu5ab_q_planned_budget } add = var:eu5ab_q_planned_budget } }
eu5ab_q_approved_cost_value = { value = 0 if = { limit = { has_variable = eu5ab_q_approved_cost } add = var:eu5ab_q_approved_cost } }
eu5ab_q_outstanding_approvals_value = { value = 0
    if = { limit = { has_variable = eu5ab_q_approved } add = var:eu5ab_q_approved }
    if = { limit = { has_variable = eu5ab_q_confirmed } subtract = var:eu5ab_q_confirmed }
    min = 0
}
eu5ab_capacity_used_value = {
    value = 0
    if = { limit = { has_variable = eu5ab_capacity_used } add = var:eu5ab_capacity_used }
}
eu5ab_capacity_limit_value = {
    value = 0
    if = { limit = { has_variable = eu5ab_capacity_limit } add = var:eu5ab_capacity_limit }
}
eu5ab_capacity_overage = {
    value = eu5ab_capacity_used_value
    subtract = eu5ab_capacity_limit_value
}
eu5ab_capacity_headroom = {
    value = eu5ab_capacity_limit_value
    subtract = eu5ab_capacity_used_value
}
eu5ab_capacity_hard_slice = { value = eu5ab_capacity_limit_value divide = 10 }
eu5ab_capacity_soft_slice = { value = eu5ab_capacity_limit_value divide = 20 }
eu5ab_queue_before_value = {
    value = 0
    if = { limit = { has_variable = eu5ab_q_queue_before } add = var:eu5ab_q_queue_before }
}
# Location scope. A genuine zero is distinct from a missing ready/open flag.
eu5ab_location_capacity_factor = {
    value = 0
    if = { limit = { has_variable = eu5ab_capacity_open } value = var:eu5ab_capacity_factor }
}
# Building type scope. Only crowded/unknown locations need the replacement scan.
eu5ab_candidate_capacity_factor = {
    value = scope:eu5ab_candidate_location.eu5ab_location_capacity_factor
    if = {
        limit = {
            scope:eu5ab_candidate_location.eu5ab_location_capacity_factor < 1
            eu5ab_candidate_capacity_exempt = yes
        }
        value = 1
    }
}
eu5ab_engine_capacity_input_overage = {
    value = scope:eu5ab_engine_capacity_used
    subtract = modifier:free_building_levels
}
eu5ab_engine_capacity_input_slice = { value = modifier:free_building_levels divide = 10 }
eu5ab_engine_capacity_factor = {
    value = eu5ab_location_capacity_factor
    if = {
        limit = { eu5ab_location_capacity_factor < 1 eu5ab_engine_candidate_capacity_exempt = yes }
        value = 1
    }
}
"""


def render_triggers() -> str:
    return """
# Compare the last fixed-point unit exactly without multiplying large readings.
# On the equality branch slice * divisor cannot exceed the original limit.
eu5ab_capacity_below_stop = {
    OR = {
        eu5ab_capacity_overage < eu5ab_capacity_hard_slice
        AND = {
            eu5ab_capacity_overage = eu5ab_capacity_hard_slice
            eu5ab_capacity_limit_value > { value = eu5ab_capacity_overage multiply = 10 }
        }
    }
}
eu5ab_capacity_no_discount = {
    OR = {
        eu5ab_capacity_headroom > eu5ab_capacity_soft_slice
        AND = {
            eu5ab_capacity_headroom = eu5ab_capacity_soft_slice
            eu5ab_capacity_limit_value <= { value = eu5ab_capacity_headroom multiply = 20 }
        }
    }
}
# Building type scope. No employment means no structural occupancy, not merely
# an empty workforce today. The replacement trigger also checks its source type.
eu5ab_candidate_capacity_exempt = {
    OR = {
        employment_size <= 0
        eu5ab_candidate_replaces_capacity_building = yes
    }
}
eu5ab_candidate_has_capacity = {
    OR = {
        scope:eu5ab_candidate_location = { has_variable = eu5ab_capacity_open }
        eu5ab_candidate_capacity_exempt = yes
    }
}
# The view is valid only for the country and monthly scan that built it.
# Old saves and non-worker callers deliberately fail this check and keep the
# former full native-recipe scan as their compatibility fallback.
eu5ab_active_recipe_catalog_current = {
    has_variable = eu5ab_active_recipe_catalog_ready
    exists = var:eu5ab_active_recipe_catalog_country
    var:eu5ab_active_recipe_catalog_country = owner
    var:eu5ab_active_recipe_catalog_month = owner.var:eu5ab_scan_month
    var:eu5ab_active_recipe_catalog_year = owner.var:eu5ab_scan_year
    owner = { has_variable = eu5ab_scan_active eu5ab_scan_month_current = yes }
}
# Closed locations still need recipes when at least one active zero-employment
# or real upgrade candidate can pass the capacity gate.
eu5ab_active_recipe_capture_needed = {
    OR = {
        NOT = { eu5ab_active_recipe_catalog_current = yes }
        AND = {
            has_variable_list = eu5ab_active_recipe_catalog_view
            OR = {
                has_variable = eu5ab_capacity_open
                any_in_list = {
                    variable = eu5ab_active_recipe_catalog_view
                    eu5ab_candidate_capacity_exempt = yes
                }
            }
        }
    }
}
# GUI validation has the exact native predecessor for this destination.
eu5ab_engine_candidate_capacity_exempt = {
    OR = {
        scope:eu5ab_candidate_building = { employment_size <= 0 }
        AND = {
            exists = scope:eu5ab_engine_replaced_building
            scope:eu5ab_engine_replaced_building = {
                building_level >= 1
                eu5ab_upgrade_source_available = yes
                building_can_be_upgraded_by = scope:eu5ab_engine_country
                building_type = { employment_size > 0 }
            }
        }
    }
}
eu5ab_engine_candidate_has_capacity = {
    OR = {
        has_variable = eu5ab_capacity_open
        eu5ab_engine_candidate_capacity_exempt = yes
    }
}
# Approval already checked capacity; firing only refreshes the cash hold.
eu5ab_approved_candidate_keeps_cash_reserve = {
    has_variable = eu5ab_q_fire_quote_ready
    owner = { gold >= {
        value = eu5ab_q_planned_spend_value
        add = scope:eu5ab_candidate_location.eu5ab_current_min_cash_reserve
    } }
}
eu5ab_engine_candidate_has_capacity_now = {
    OR = {
        eu5ab_engine_candidate_capacity_exempt = yes
        AND = {
            exists = scope:eu5ab_engine_capacity_used
            scope:eu5ab_engine_capacity_used >= 0
            modifier:free_building_levels > 0
            OR = {
                eu5ab_engine_capacity_input_overage < eu5ab_engine_capacity_input_slice
                AND = {
                    eu5ab_engine_capacity_input_overage = eu5ab_engine_capacity_input_slice
                    modifier:free_building_levels > { value = eu5ab_engine_capacity_input_overage multiply = 10 }
                }
            }
        }
    }
}
"""


def render_effects() -> str:
    clear = "\n".join(f"    remove_variable = eu5ab_capacity_{name}" for name in CAPACITY_FIELDS)
    return """
eu5ab_clear_building_capacity = {
""" + clear + """
}
# Readings belong to this invocation, never to a former candidate or owner.
eu5ab_refresh_approved_cash_quote = {
    remove_variable = eu5ab_q_fire_quote_ready
    if = { limit = { exists = scope:eu5ab_engine_cost scope:eu5ab_engine_cost >= 0 }
        # Replace this project's hold in one expression, including a zero
        # balance. Other approved projects keep their reservations unchanged.
        owner = {
            set_variable = { name = eu5ab_q_planned_spend value = {
                value = eu5ab_q_planned_spend_value subtract = scope:eu5ab_candidate_location.eu5ab_q_approved_cost_value add = scope:eu5ab_engine_cost } }
            set_variable = { name = eu5ab_q_planned_budget value = {
                value = eu5ab_q_planned_budget_value subtract = scope:eu5ab_candidate_location.eu5ab_q_approved_cost_value add = scope:eu5ab_engine_cost } }
        }
        set_variable = { name = eu5ab_q_approved_cost value = scope:eu5ab_engine_cost }
        set_variable = eu5ab_q_fire_quote_ready
    }
}
eu5ab_capture_building_capacity = {
    save_scope_as = eu5ab_candidate_location
    eu5ab_prepare_active_recipe_catalog_view = yes
    eu5ab_clear_building_capacity = yes
    if = {
        limit = {
            exists = scope:eu5ab_engine_capacity_used
            scope:eu5ab_engine_capacity_used >= 0
            modifier:free_building_levels > 0
        }
        set_variable = { name = eu5ab_capacity_used value = scope:eu5ab_engine_capacity_used }
        set_variable = { name = eu5ab_capacity_limit value = modifier:free_building_levels }
        set_variable = eu5ab_capacity_ready
        if = {
            limit = { eu5ab_capacity_below_stop = yes }
            set_variable = eu5ab_capacity_open
            set_variable = { name = eu5ab_capacity_factor value = 1 }
            if = {
                limit = { NOT = { eu5ab_capacity_no_discount = yes } }
                set_variable = { name = eu5ab_capacity_factor value = {
                    value = eu5ab_capacity_used_value
                    divide = eu5ab_capacity_limit_value
                    subtract = 1.10
                    multiply = -1
                    divide = 0.15
                    min = 0.00001
                    max = 1
                } }
            }
        }
    }
    if = {
        limit = { eu5ab_active_recipe_capture_needed = yes }
        eu5ab_refresh_native_recipes = yes
    }
    else = { eu5ab_clear_native_recipes = yes }
}
# Dispatch requests carry no old snapshot, including after loading an old save.
eu5ab_request_building_capacity = {
    eu5ab_clear_industry_snapshot = yes
    eu5ab_clear_rgo_queue = yes
    eu5ab_clear_building_capacity = yes
    eu5ab_clear_native_recipes = yes
    eu5ab_clear_parallel_capacity = yes
    remove_variable = eu5ab_worker_complete
    remove_variable = eu5ab_capacity_received remove_variable = eu5ab_capacity_reason
    set_variable = { name = eu5ab_capacity_sequence value = { value = 0
        if = { limit = { has_variable = eu5ab_capacity_sequence } add = var:eu5ab_capacity_sequence } add = 1 } }
    set_variable = { name = eu5ab_capacity_request value = var:eu5ab_capacity_sequence }
    set_variable = { name = eu5ab_capacity_month value = owner.var:eu5ab_scan_month }
    set_variable = { name = eu5ab_capacity_year value = owner.var:eu5ab_scan_year }
    clear_variable_list = eu5ab_capacity_tickets
    add_to_variable_list = { name = eu5ab_capacity_tickets target = var:eu5ab_capacity_request }
    set_variable = eu5ab_capacity_requested
    set_variable = { name = eu5ab_capacity_worker_country value = owner }
    eu5ab_request_upgrade_snapshot = yes
}
# A delayed parallel event and the next-day fallback can never run twice.
eu5ab_run_capacity_worker_once = {
    if = {
        limit = { has_variable = eu5ab_capacity_worker_country has_variable = eu5ab_capacity_received
            NOT = { has_variable = eu5ab_worker_complete }
            NOT = { owner = { has_variable = eu5ab_scan_resume_after_load } } }
        if = {
            limit = {
                owner = var:eu5ab_capacity_worker_country
                var:eu5ab_capacity_month = owner.var:eu5ab_scan_month
                var:eu5ab_capacity_year = owner.var:eu5ab_scan_year
                owner = { has_variable = eu5ab_scan_active eu5ab_scan_month_current = yes }
            }
            remove_variable = eu5ab_capacity_worker_country
            remove_variable = eu5ab_capacity_requested
            owner = { save_scope_as = actor }
            eu5ab_run_location_worker = yes
        }
        else = {
            remove_variable = eu5ab_capacity_worker_country
            remove_variable = eu5ab_capacity_requested
            eu5ab_clear_building_capacity = yes
        }
    }
}
# Retrying a missing receipt preserves its identity and never starts screening.
eu5ab_finish_pending_capacity_workers = {
    every_in_list = {
        variable = eu5ab_worker_pending_locations
        eu5ab_run_capacity_worker_once = yes
        if = { limit = { $REQUEST_PENDING$ }
            clear_variable_list = eu5ab_capacity_tickets
            add_to_variable_list = { name = eu5ab_capacity_tickets target = var:eu5ab_capacity_request }
        }
    }
    eu5ab_count_capacity_waiting = yes
}
eu5ab_count_capacity_waiting = {
    set_variable = { name = eu5ab_diag_capacity_waiting value = 0 }
    save_scope_as = eu5ab_capacity_count_country
    every_in_list = { variable = eu5ab_worker_pending_locations
        limit = { owner = scope:eu5ab_capacity_count_country has_variable = eu5ab_capacity_requested }
        scope:eu5ab_capacity_count_country = { set_variable = { name = eu5ab_diag_capacity_waiting value = {
            value = 0 if = { limit = { has_variable = eu5ab_diag_capacity_waiting } add = var:eu5ab_diag_capacity_waiting } add = 1 } } }
    }
}
# GUI callbacks are serial. Parallel worker events publish only location state;
# this reducer runs from the GUI pump as soon as the complete batch is ready.
eu5ab_reduce_capacity_batch = {
    if = { limit = { has_variable = eu5ab_scan_active eu5ab_scan_month_current = yes
        NOT = { has_variable = eu5ab_scan_resume_after_load }
        has_variable_list = eu5ab_worker_pending_locations
        NOT = { any_in_list = { variable = eu5ab_worker_pending_locations owner = prev
            NOT = { has_variable = eu5ab_worker_complete } } } }
        eu5ab_merge_location_worker_results = yes
        eu5ab_count_capacity_waiting = yes
        if = { limit = { has_variable = eu5ab_scan_finalizing eu5ab_queue_calendar_open = yes }
            eu5ab_finish_regional_development_scan = yes }
    }
}
""".replace('$REQUEST_PENDING$', REQUEST_PENDING_CONDITIONS)


def signed_value_lines(score: str, factor: str, indent: str = "\t") -> list[str]:
    """Adjust an already-composed script value without fixed-point overflow."""
    return [
        f"{indent}value = {score}",
        f"{indent}if = {{",
        f"{indent}\tlimit = {{ {factor} > 0 }}",
        f"{indent}\tif = {{ limit = {{ {score} >= 0 }} multiply = {factor} }}",
        f"{indent}\telse_if = {{ limit = {{ {score} < {RANK_FLOOR} }} value = {score} }}",
        f"{indent}\telse_if = {{ limit = {{ {score} < {{ value = {RANK_FLOOR} multiply = {factor} }} }} value = {RANK_FLOOR} }}",
        f"{indent}\telse = {{ divide = {factor} }}",
        f"{indent}}}",
        f"{indent}else = {{ value = 0 }}",
    ]


def render_score_values() -> str:
    specifications = (
        ("eu5ab_current_candidate_score", "eu5ab_pending_adjusted_candidate_score",
         "eu5ab_candidate_capacity_factor"),
        ("eu5ab_capacity_location_order", "eu5ab_location_order_base",
         "scope:eu5ab_candidate_building.eu5ab_candidate_capacity_factor"),
        ("eu5ab_capacity_profit_rank", "eu5ab_profit_candidate_rank_value",
         "eu5ab_engine_capacity_factor"),
    )
    lines = [
        "eu5ab_location_order_base = {", "\tvalue = 0",
        "\tif = { limit = { has_variable = eu5ab_cached_location_need_score } add = var:eu5ab_cached_location_need_score }",
        "}", "",
    ]
    for field in ("candidate_rank", "best_rank", "candidate_priority", "candidate_magnitude"):
        lines += [
            f"eu5ab_profit_{field}_value = {{", "\tvalue = 0",
            f"\tif = {{ limit = {{ has_variable = eu5ab_q_profit_{field} }} add = var:eu5ab_q_profit_{field} }}",
            "}", "",
        ]
    for name, score, factor in specifications:
        lines += [f"{name} = {{", *signed_value_lines(score, factor), "}", ""]
    return "\n".join(lines)


def phase_order_lines(phase: int, indent: str) -> list[str]:
    name = f"eu5ab_capacity_phase_{phase}_order"
    # Retain the best complete planning score at each location. A location-only
    # score here would erase output-price weighting from the final ordering.
    score = "scope:eu5ab_candidate_building.eu5ab_candidate_sort_score"
    return [
        f"{indent}if = {{",
        f"{indent}\tlimit = {{ OR = {{ NOT = {{ has_variable = {name}_ready }} {name}_value < {score} }} }}",
        f"{indent}\tset_variable = {{ name = {name} value = {score} }}",
        f"{indent}\tset_variable = {name}_ready",
        f"{indent}}}",
    ]


def phase_values(phase_count: int) -> str:
    return "\n".join(
        f"eu5ab_capacity_phase_{phase}_order_value = {{ value = 0 "
        f"if = {{ limit = {{ has_variable = eu5ab_capacity_phase_{phase}_order }} "
        f"add = var:eu5ab_capacity_phase_{phase}_order }} }}"
        for phase in range(1, phase_count + 1)
    ) + "\n"


def clear_phase_lines(phase_count: int, indent: str = "\t") -> list[str]:
    return [f"{indent}remove_variable = eu5ab_capacity_phase_{phase}_order{suffix}"
            for phase in range(1, phase_count + 1) for suffix in ("", "_ready")]


def render_guis() -> str:
    from . import queue_bridge
    return ("""
eu5ab_gui_capacity_requests_exist = {
    is_shown = {
        has_variable = eu5ab_scan_active
        NOT = { has_variable = eu5ab_scan_resume_after_load }
        any_in_list = {
            variable = eu5ab_worker_pending_locations
            owner = prev
            $REQUEST_PENDING$
        }
    }
}
eu5ab_gui_capacity_request_pending = {
    saved_scopes = { eu5ab_engine_country }
    is_shown = {
        owner = scope:eu5ab_engine_country
        $REQUEST_PENDING$
    }
}
eu5ab_gui_reduce_capacity_batch = {
    is_shown = { has_variable = eu5ab_scan_active has_variable_list = eu5ab_worker_pending_locations
        NOT = { has_variable = eu5ab_scan_resume_after_load }
        NOT = { any_in_list = { variable = eu5ab_worker_pending_locations owner = prev
            NOT = { has_variable = eu5ab_worker_complete } } } }
    is_valid = { always = yes }
    effect = { eu5ab_reduce_capacity_batch = yes }
}
eu5ab_gui_capture_building_capacity = {
    saved_scopes = { eu5ab_capacity_ticket eu5ab_engine_country """ + GUI_SCOPES + """ }
    is_valid = { always = yes }
    effect = {
        save_scope_as = eu5ab_candidate_location
        if = {
            limit = {
                $RECEIPT_CURRENT$
                owner = scope:eu5ab_engine_country
            }
            eu5ab_capture_rgo_queue = yes
            eu5ab_prepare_rgo_pending_start = yes
            eu5ab_capture_building_capacity = yes
            eu5ab_finish_industry_snapshot = yes
            set_variable = eu5ab_capacity_received
            # A returned invalid reading is different from no response.
            set_variable = { name = eu5ab_capacity_reason value = 1 }
            if = { limit = { has_variable = eu5ab_capacity_ready }
                set_variable = { name = eu5ab_capacity_reason value = 3 }
                if = { limit = { has_variable = eu5ab_capacity_open } remove_variable = eu5ab_capacity_reason }
            }
            else_if = { limit = { modifier:free_building_levels <= 0 }
                set_variable = { name = eu5ab_capacity_reason value = 2 } }
            clear_variable_list = eu5ab_capacity_tickets
            remove_variable = eu5ab_capacity_requested
            if = {
                limit = { owner.var:eu5ab_scan_parallel > 0 }
                trigger_event_silently = { on_action = eu5ab_parallel_location_scan_on_action }
            }
            else = { eu5ab_run_capacity_worker_once = yes owner = { eu5ab_reduce_capacity_batch = yes } }
        }
    }
}
eu5ab_gui_queue_request_fire = {
    saved_scopes = { eu5ab_candidate_building eu5ab_engine_country eu5ab_engine_cost eu5ab_engine_replaced_building }
    is_valid = { always = yes }
    effect = {
        save_scope_as = eu5ab_candidate_location
        if = {
            limit = {
                owner = scope:eu5ab_engine_country
                owner = { eu5ab_queue_calendar_open = yes has_variable = eu5ab_q_active has_variable = eu5ab_q_fire NOT = { has_variable = eu5ab_scan_resume_after_load } }
                has_variable = eu5ab_q_location_approved
                is_target_in_variable_list = { name = eu5ab_q_approved_types target = scope:eu5ab_candidate_building }
                NOT = { is_target_in_variable_list = { name = eu5ab_q_confirmed_types target = scope:eu5ab_candidate_building } }
            }
            if = { limit = { NOT = { has_variable = eu5ab_q_fire_issued } }
                eu5ab_refresh_approved_cash_quote = yes
                set_variable = { name = eu5ab_q_type_queue_before value = eu5ab_candidate_queued_levels }
                set_variable = { name = eu5ab_q_type_level_before value = eu5ab_candidate_completed_levels }
                eu5ab_pf_capture_start_geometry = yes
                remove_variable = eu5ab_pending_predecessor
                remove_variable = eu5ab_pending_predecessor_before
                if = {
                    limit = { scope:eu5ab_candidate_building = { eu5ab_pending_exact_predecessor = yes } }
                    set_variable = { name = eu5ab_pending_predecessor value = scope:eu5ab_engine_replaced_building }
                    set_variable = { name = eu5ab_pending_predecessor_before value = scope:eu5ab_engine_replaced_building.building_level }
                }
            }
            set_variable = eu5ab_q_fire_requested
            if = { limit = { has_variable = eu5ab_q_fire_issued }
                eu5ab_confirm_requested_engine_candidate = yes
            }
            else_if = { limit = { NOT = { $FIRE_GUARD$ } }
                eu5ab_confirm_requested_engine_candidate = yes
            }
            owner = { eu5ab_dispatch_queue_bridge = yes }
        }
    }
}
eu5ab_gui_queue_fire_permitted = {
    saved_scopes = { eu5ab_candidate_location eu5ab_candidate_building eu5ab_engine_country }
    is_shown = {
        $FIRE_GUARD$
    }
}
""").replace('$REQUEST_PENDING$', REQUEST_PENDING_CONDITIONS).replace('$RECEIPT_CURRENT$', RECEIPT_CURRENT).replace('$FIRE_GUARD$', FIRE_GUARD).replace(
    'saved_scopes = { eu5ab_candidate_building eu5ab_engine_country eu5ab_engine_cost',
    'saved_scopes = { eu5ab_bridge_ticket eu5ab_candidate_building eu5ab_engine_country eu5ab_engine_cost').replace(
    'saved_scopes = { eu5ab_candidate_location eu5ab_candidate_building',
    'saved_scopes = { eu5ab_bridge_ticket eu5ab_candidate_location eu5ab_candidate_building').replace(
    '                has_variable = eu5ab_q_location_approved',
    '                ' + queue_bridge.COMPATIBLE + '\n                OR = { owner = { NOT = { has_variable = eu5ab_bridge_schema } }\n                    owner = { var:eu5ab_bridge_kind = 4 NOT = { has_variable = eu5ab_bridge_data_received } } }\n                has_variable = eu5ab_q_location_approved').replace(
    '            if = { limit = { NOT = { has_variable = eu5ab_q_fire_issued } }',
    '            owner = { if = { limit = { has_variable = eu5ab_bridge_schema } set_variable = eu5ab_bridge_data_received } }\n            if = { limit = { NOT = { has_variable = eu5ab_q_fire_issued } }').replace(
    '                eu5ab_confirm_requested_engine_candidate = yes',
    '                eu5ab_confirm_requested_engine_candidate = yes\n                owner = { eu5ab_clear_queue_bridge = yes eu5ab_dispatch_queue_bridge = yes }')


def render_capture_widget() -> str:
    ticket = ".AddScope('eu5ab_capacity_ticket', MakeScopeValue(Scope.GetValue))"
    args = "GuiScope.SetRoot(Location.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope)" + ticket + gui_arguments() + rgo_queue.gui_arguments() + industry_promotion.count_argument() + ".End"
    pending = "GetScriptedGui('eu5ab_gui_capacity_request_pending').IsShown(GuiScope.SetRoot(Location.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope).End)"
    return """
        widget = {
            size = { 0 0 }
            visible = "[And(GetPlayer.Exists, Or(GetScriptedGui('eu5ab_gui_capacity_requests_exist').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End), GetScriptedGui('eu5ab_gui_reduce_capacity_batch').IsShown(GuiScope.SetRoot(GetPlayer.MakeScope).End)))]"
            state = { name = _show next = eu5ab_capacity_capture_loop }
            state = {
                name = eu5ab_capacity_capture_loop
                duration = 0.15
                on_finish = "[GetScriptedGui('eu5ab_gui_begin_industry_snapshot').Execute(GuiScope.SetRoot(GetPlayer.MakeScope)""" + industry_promotion.count_argument() + """.End)]"
                on_finish = "[PdxGuiTriggerAllAnimations('eu5ab_worker_parallel_sample')]"
                next = eu5ab_capacity_publish
            }
            state = {
                name = eu5ab_capacity_publish
                duration = 0.1
                on_finish = "[PdxGuiTriggerAllAnimations('eu5ab_capacity_capture')]"
                on_finish = "[GetScriptedGui('eu5ab_gui_reduce_capacity_batch').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
                next = eu5ab_capacity_capture_loop
            }
        }
        widget = {
            datamodel = "[GetPlayer.MakeScope.GetList('eu5ab_worker_pending_locations')]"
            item = { widget = {
                datacontext = "[Scope.GetLocation]"
                widget = {
                    datamodel = "[DataModelRepeatedItem(Select_int32(""" + pending + """, '(int32)1', '(int32)0'))]"
                    item = { widget = {
                    datamodel = "[Location.MakeScope.GetList('eu5ab_capacity_tickets')]"
                    item = { widget = {
""" + construction_slots.capture_widget("eu5ab_worker_parallel", capacity=True) + """
""" + upgrade_queue.capture_widget() + """
""" + industry_promotion.capture_widget() + """
                state = {
                    name = eu5ab_capacity_capture
                    duration = 0.01
                    on_finish = "[GetScriptedGui('eu5ab_gui_capture_building_capacity').Execute(""" + args + """)]"
                }
                    } }
                    } }
                }
            } }
        }
"""


def fire_widget(*, ticket: str = '') -> str:
    args = (
        "GuiScope.SetRoot(Location.MakeScope)"
        ".AddScope('eu5ab_candidate_location', Location.MakeScope)"
        ".AddScope('eu5ab_candidate_building', BuildingType.MakeScope)"
        ".AddScope('eu5ab_engine_country', GetPlayer.MakeScope)"
        + ticket + ".End"
    )
    return """
            widget = {
                visible_at_creation = no
                visible = "[GetScriptedGui('eu5ab_gui_queue_fire_permitted').IsShown(""" + args + """)]"
                state = { name = _hide alpha = 0 }
                state = {
                    name = _show
                    alpha = 1
                    on_finish = "[GetScriptedGui('eu5ab_gui_queue_record_fire').Execute(GuiScope.SetRoot(Location.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope).AddScope('eu5ab_candidate_building', BuildingType.MakeScope)$TICKET$.End)]"
                    on_finish = "[BuildOrExpandBuildingDefault(BuildingType.Self, Location.Self)]"
                }
            }
""".replace('$TICKET$', ticket)
