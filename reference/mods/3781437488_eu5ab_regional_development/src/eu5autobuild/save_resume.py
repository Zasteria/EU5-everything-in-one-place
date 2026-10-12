"""Continue saved scan cursors and phases; rebuild only volatile GUI work."""


def render_effects():
    return '''eu5ab_recover_runtime_after_load = {
    # Legacy rounds without a verifiable month are closed conservatively once.
    eu5ab_expire_old_scan_month = yes
    # Scan buckets, worker results, candidate lists, phase, expenditure and
    # settlement floors are persistent. None is a GUI animation continuation.
    if = { limit = { NOT = { has_variable = eu5ab_scan_registry_schema_version } } eu5ab_rebuild_scan_registry_v1 = yes }
    else_if = { limit = { var:eu5ab_scan_registry_schema_version < 1 } eu5ab_rebuild_scan_registry_v1 = yes }
    eu5ab_ensure_template_coverage = yes
    if = { limit = { NOT = { has_variable = eu5ab_runtime_schema_version } } eu5ab_migrate_runtime_v2 = yes }
    else_if = { limit = { var:eu5ab_runtime_schema_version < 2 } eu5ab_migrate_runtime_v2 = yes }
    save_scope_as = eu5ab_resume_country
    every_in_list = { variable = eu5ab_worker_pending_locations
        limit = { owner = scope:eu5ab_resume_country NOT = { has_variable = eu5ab_worker_complete } }
        eu5ab_request_building_capacity = yes
    }
    # Rebuild aggregates from new confirmed IDs. No legacy GUI field enrolls
    # construction, and persistent completion dates are never reset here.
    eu5ab_pf_rebuild_goods_index = yes
    eu5ab_refresh_build_pending = yes
    eu5ab_pf_resume_maintenance = yes
    eu5ab_refresh_rgo_pending = yes
    if = { limit = { is_human = yes var:eu5ab_global_enabled > 0
        NOT = { has_variable = eu5ab_scan_resume_after_load }
        NOT = { has_variable = eu5ab_scan_round_active } NOT = { has_variable = eu5ab_q_active }
        any_owned_location = { has_variable = eu5ab_policy_id }
        OR = { current_day = 1 eu5ab_scan_calendar_open = yes }
    } trigger_event_silently = { id = eu5ab_monthly.1 days = 1 } }
}
eu5ab_settle_saved_approvals = {
    save_scope_as = actor
    save_scope_as = eu5ab_resume_country
    # Settle a physical start before any approved cost or baseline is discarded.
    every_in_list = { variable = eu5ab_q_approved_locations
        limit = { owner = scope:eu5ab_resume_country }
        save_scope_as = eu5ab_candidate_location
        every_in_list = { variable = eu5ab_q_approved_types
            save_scope_as = eu5ab_candidate_building
            scope:eu5ab_candidate_location = {
                if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_q_confirmed_types target = scope:eu5ab_candidate_building } } }
                    if = { limit = { has_variable = eu5ab_q_fire_issued eu5ab_approved_building_started = yes }
                        eu5ab_confirm_engine_candidate = yes
                    }
                    else = {
                        eu5ab_release_engine_candidate_reservation = yes
                        eu5ab_release_candidate_construction_demand = yes
                        eu5ab_release_candidate_output = yes
                    }
                }
            }
        }
    }
    # All approvals are now settled or withdrawn, including locations no longer
    # owned by this country. No temporary spending reservation carries forward.
    set_variable = { name = eu5ab_q_planned_spend value = 0 }
    set_variable = { name = eu5ab_q_planned_budget value = 0 }
}
eu5ab_resume_saved_queue = {
    eu5ab_settle_saved_approvals = yes
    eu5ab_reset_engine_priority_phase_progress = yes
    eu5ab_prepare_engine_priority_phase = yes
    eu5ab_reset_engine_candidate_watchdog_progress = yes
    trigger_event_silently = { id = eu5ab_queue_watchdog.1 days = 1 }
}
'''


def render_event():
    return '''eu5ab_monthly.4 = {
    type = country_event
    title = eu5ab_window_title
    outcome = neutral
    hidden = yes
    immediate = {
        save_scope_as = actor
        eu5ab_expire_old_scan_month = yes
        if = { limit = { has_variable = eu5ab_scan_resume_after_load }
            remove_variable = eu5ab_scan_resume_after_load
            if = { limit = { is_human = yes var:eu5ab_global_enabled > 0 }
                if = { limit = { has_variable = eu5ab_q_active } eu5ab_resume_saved_queue = yes }
                else_if = { limit = { has_variable = eu5ab_scan_refill_active }
                    trigger_event_silently = { id = eu5ab_monthly.3 days = 1 }
                }
                else_if = { limit = { has_variable = eu5ab_scan_active }
                    if = { limit = { has_variable = eu5ab_scan_finalizing }
                        trigger_event_silently = { id = eu5ab_monthly.2 days = 1 }
                    }
                    else = { trigger_event_silently = { id = eu5ab_monthly.1 days = 1 } }
                }
                else_if = { limit = { has_variable = eu5ab_scan_round_active } eu5ab_settle_scan_candidate_batch = yes }
                else_if = { limit = { any_owned_location = { has_variable = eu5ab_policy_id } }
                    trigger_event_silently = { id = eu5ab_monthly.1 days = 1 }
                }
            }
        }
    }
}
'''
