"""Synchronous production references; only invalid market/RGO data can wait."""


def render_effects() -> str:
    return '''eu5ab_retry_waiting_candidate_data = {
    if = { limit = { eu5ab_q_waiting_data_value > 0 NOT = { has_variable = eu5ab_q_fire }
        eu5ab_q_outstanding_approvals_value <= 0 OR = {
            NOT = { has_variable = eu5ab_q_data_day }
            NOT = { var:eu5ab_q_data_day = eu5ab_pl_today }
        } }
        eu5ab_ensure_build_pending = yes
        eu5ab_restart_engine_priority_phase = yes
    }
}
eu5ab_prepare_rgo_dependencies = {
    if = { limit = { NOT = { eu5ab_rgo_food_emergency_enabled = yes }
        NOT = { eu5ab_rgo_pending_data_available = yes }
        NOT = { has_variable = eu5ab_q_waiting_rgo } }
        set_variable = eu5ab_q_waiting_rgo
        eu5ab_report_rgo_waiting = yes
        owner = { set_variable = { name = eu5ab_q_waiting_data value = { value = eu5ab_q_waiting_data_value add = 1 } } }
    }
}
eu5ab_prepare_candidate_dependencies = {
    eu5ab_refresh_native_recipes = yes
    eu5ab_prepare_production_reference = yes
    owner = { eu5ab_ensure_build_pending = yes }
    remove_variable = eu5ab_q_dependency_wait
    if = { limit = { scope:eu5ab_candidate_building = { NOT = { eu5ab_candidate_pending_data_ready = yes } } }
        set_variable = eu5ab_q_dependency_wait
        eu5ab_report_candidate_waiting = yes
        if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_q_waiting_types target = scope:eu5ab_candidate_building } } }
            add_to_variable_list = { name = eu5ab_q_waiting_types target = scope:eu5ab_candidate_building }
            owner = { set_variable = { name = eu5ab_q_waiting_data value = { value = eu5ab_q_waiting_data_value add = 1 } } }
        }
    }
    else_if = { limit = { is_target_in_variable_list = { name = eu5ab_q_waiting_types target = scope:eu5ab_candidate_building } }
        remove_list_variable = { name = eu5ab_q_waiting_types target = scope:eu5ab_candidate_building }
        owner = { set_variable = { name = eu5ab_q_waiting_data value = { value = eu5ab_q_waiting_data_value subtract = 1 min = 0 } } }
    }
}
'''


def render_values() -> str:
    return '''eu5ab_q_waiting_data_value = { value = 0
    if = { limit = { has_variable = eu5ab_q_waiting_data } add = var:eu5ab_q_waiting_data }
}
'''
