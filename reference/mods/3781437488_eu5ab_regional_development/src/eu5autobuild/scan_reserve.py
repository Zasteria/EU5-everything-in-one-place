"""Location-based reserves and bounded continuation of a monthly scan.

The country owns all counters/lists; parallel workers never mutate them.
Only normally exhausted queues train the estimate (quota-limited and watchdog
exits are censored). A successful start, including RGO, is the useful outcome.
"""

REFILL_STALL_DAYS = 6

# These counters legitimately disappear during cleanup or in an older save.
# A missing variable is an unset scope, not a numeric comparison operand.
ZERO_DEFAULTS = {
    "eu5ab_scan_reserve_count": "eu5ab_scan_candidate_reserve",
    "eu5ab_scan_settled_count": "eu5ab_scan_settled_locations",
    "eu5ab_scan_started_count": "eu5ab_constructions_started_this_tick",
    "eu5ab_scan_attempt_count": "eu5ab_deep_score_attempts",
    "eu5ab_scan_daily_attempt_count": "eu5ab_daily_deep_score_attempts",
    "eu5ab_scan_early_stop_value": "eu5ab_scan_early_stop",
    "eu5ab_scan_refill_stall_count": "eu5ab_scan_refill_stall_days",
}


def render_values() -> str:
    return "\n".join(
        f"{name} = {{\n    value = 0\n"
        f"    if = {{ limit = {{ has_variable = {variable} }} value = var:{variable} }}\n}}\n"
        for name, variable in ZERO_DEFAULTS.items()
    )


def render_effects() -> str:
    return """
# Called once per completed worker with candidates; count each location once.
eu5ab_record_scan_candidate_location = {
    if = {
        limit = { NOT = { is_target_in_variable_list = { name = eu5ab_scan_candidate_locations target = scope:eu5ab_candidate_location } } }
        add_to_variable_list = { name = eu5ab_scan_candidate_locations target = scope:eu5ab_candidate_location }
        if = {
            limit = { has_variable = eu5ab_scan_candidate_reserve }
            change_variable = { name = eu5ab_scan_candidate_reserve add = 1 }
        }
        else = { set_variable = { name = eu5ab_scan_candidate_reserve value = 1 } }
    }
}

eu5ab_update_scan_candidate_target = {
    if = { limit = { NOT = { has_variable = eu5ab_scan_acceptance_rate } } set_variable = { name = eu5ab_scan_acceptance_rate value = 0.5 } }
    # Bound the estimate, never the validation gates. Zero successes still have
    # a finite target and all work remains bounded by the original deep budget.
    set_variable = { name = eu5ab_scan_acceptance_rate value = { value = var:eu5ab_scan_acceptance_rate min = 0.05 max = 1 } }
    set_variable = { name = eu5ab_scan_candidate_target value = { value = var:eu5ab_monthly_build_quota subtract = eu5ab_scan_started_count min = 0 divide = var:eu5ab_scan_acceptance_rate ceiling = yes } }
}

eu5ab_clear_scan_continuation = {
    clear_variable_list = eu5ab_scan_unscanned_locations
    clear_variable_list = eu5ab_scan_candidate_locations
    remove_variable = eu5ab_scan_round_active
    remove_variable = eu5ab_scan_refill_active
    remove_variable = eu5ab_scan_backfill_enabled
    remove_variable = eu5ab_scan_refill_last_attempt
    remove_variable = eu5ab_scan_refill_stall_days
}

eu5ab_complete_scan_round = {
    eu5ab_clear_scan_continuation = yes
}

eu5ab_settle_scan_candidate_batch = {
    if = {
        limit = {
            has_variable = eu5ab_scan_round_active
            eu5ab_queue_calendar_open = yes
            NOT = { var:eu5ab_diag_queue_state = 5 }
            eu5ab_scan_started_count < { value = var:eu5ab_monthly_build_quota }
        }
        # Exhausted queues have visited all their candidate locations. Sum unique
        # locations, not building probes; retries and RGO cannot inflate capacity.
        if = {
            limit = { eu5ab_scan_reserve_count > 0 }
            set_variable = { name = eu5ab_scan_settled_locations value = { value = eu5ab_scan_settled_count add = eu5ab_scan_reserve_count } }
            # One success and one failure of smoothing prevent small samples
            # from oscillating between a zero and a perfect acceptance rate.
            set_variable = { name = eu5ab_scan_acceptance_rate value = { value = eu5ab_scan_started_count add = 1 divide = { value = var:eu5ab_scan_settled_locations add = 2 } min = 0.05 max = 1 } }
        }
        if = {
            limit = {
                var:eu5ab_global_enabled > 0
                eu5ab_scan_attempt_count < { value = var:eu5ab_deep_score_budget }
                has_variable_list = eu5ab_scan_unscanned_locations
            }
            set_variable = eu5ab_scan_refill_active
            # Always dispatch on a new day. Finishing a GUI batch must not reset
            # the current day's worker allowance or the round's total allowance.
            trigger_event_silently = { id = eu5ab_monthly.3 days = 1 }
        }
    }
    if = { limit = { NOT = { has_variable = eu5ab_scan_refill_active } } eu5ab_complete_scan_round = yes }
}
"""


def render_watchdog() -> str:
    return """
# Initial scanning is bounded to days 2-22; GUI execution has its own watchdog.
# Continuation needs a separate bound: an empty retry consumes no deep budget.
eu5ab_check_scan_refill_progress = {
    if = {
        limit = { NOT = { has_variable = eu5ab_scan_refill_last_attempt } }
        # Offset the snapshot so even zero completed work survives serialization.
        set_variable = { name = eu5ab_scan_refill_last_attempt value = { value = eu5ab_scan_attempt_count add = 1 } }
        remove_variable = eu5ab_scan_refill_stall_days
    }
    else_if = {
        limit = { eu5ab_scan_attempt_count > { value = var:eu5ab_scan_refill_last_attempt subtract = 1 } }
        set_variable = { name = eu5ab_scan_refill_last_attempt value = { value = eu5ab_scan_attempt_count add = 1 } }
        remove_variable = eu5ab_scan_refill_stall_days
    }
    else = {
        set_variable = { name = eu5ab_scan_refill_stall_days value = { value = eu5ab_scan_refill_stall_count add = 1 } }
    }
    if = {
        limit = { eu5ab_scan_refill_stall_count >= """ + str(REFILL_STALL_DAYS) + """
            NOT = { has_variable_list = eu5ab_worker_pending_locations } }
        set_variable = { name = eu5ab_diag_scan_stalled value = 1 }
        # Clear only transient workers/candidates and material reservations.
        # Confirmed projects, budgets, templates and cooldowns remain intact.
        every_in_list = { variable = eu5ab_worker_pending_locations eu5ab_clear_location_worker_state = yes eu5ab_clear_location_candidate_state = yes }
        clear_variable_list = eu5ab_worker_pending_locations
        eu5ab_clear_engine_candidate_queue = yes
        eu5ab_reset_committed_construction_demand = yes
        remove_variable = eu5ab_scan_active
        eu5ab_complete_scan_round = yes
    }
}
"""


def render_refill(dispatch_lines: list[str]) -> str:
    """Reuse the initial scan's exact gated worker dispatch and phase partitioning."""
    gates = f"""owner = scope:eu5ab_scan_country
                has_variable = eu5ab_policy_id
                eu5ab_location_template_not_paused = yes
                eu5ab_location_has_parallel_room = yes
                NOT = {{ has_variable = eu5ab_build_cooldown }}
                NOT = {{ has_variable = eu5ab_failure_cooldown }}"""
    return """
eu5ab_refill_regional_development_scan = {
    eu5ab_record_scan_date = yes
    save_scope_as = eu5ab_scan_country
    if = {
        limit = { NOT = { has_variable = eu5ab_scan_active } }
        eu5ab_prepare_engine_candidate_queue = yes
        clear_variable_list = eu5ab_scan_candidate_locations
        remove_variable = eu5ab_scan_candidate_reserve
        eu5ab_update_scan_candidate_target = yes
        set_variable = eu5ab_scan_active
    }
    set_variable = { name = eu5ab_daily_deep_score_budget value = var:eu5ab_scan_daily_task_limit }
    set_variable = { name = eu5ab_daily_deep_score_attempts value = 0 }
    eu5ab_scan_deferred_locations = yes
    remove_variable = eu5ab_daily_deep_score_budget
    remove_variable = eu5ab_daily_deep_score_attempts
}

# Keep the twenty persisted buckets intact. The 21st scan day uses their
# undelivered locations, without repeating cooldown/waiting maintenance.
eu5ab_scan_initial_tail = {
    eu5ab_record_scan_date = yes
    eu5ab_refresh_rgo_pending = yes
    eu5ab_ensure_build_pending = yes
    save_scope_as = eu5ab_scan_country
    set_variable = { name = eu5ab_daily_deep_score_budget value = { value = var:eu5ab_deep_score_budget divide = 21 ceiling = yes } }
    if = { limit = { var:eu5ab_daily_deep_score_budget > var:eu5ab_scan_daily_task_limit }
        set_variable = { name = eu5ab_daily_deep_score_budget value = var:eu5ab_scan_daily_task_limit } }
    set_variable = { name = eu5ab_daily_deep_score_attempts value = 0 }
    if = { limit = { eu5ab_scan_attempt_count < var:eu5ab_deep_score_budget
        OR = { eu5ab_scan_early_stop_value <= 0 eu5ab_scan_reserve_count < var:eu5ab_scan_candidate_target } }
        eu5ab_scan_deferred_locations = yes }
    remove_variable = eu5ab_daily_deep_score_budget
    remove_variable = eu5ab_daily_deep_score_attempts
}

eu5ab_scan_deferred_locations = {
    # Refresh eligibility and cheap ordering only. Monthly cooldown/waiting
    # maintenance already ran; dispatched locations have left this list forever.
    every_in_list = {
        variable = eu5ab_scan_unscanned_locations
        if = {
            limit = { """ + gates + """ }
            set_variable = { name = eu5ab_bucket_need_score value = eu5ab_location_need_score }
        }
        else = {
            save_scope_as = eu5ab_candidate_location
            scope:eu5ab_scan_country = { remove_list_variable = { name = eu5ab_scan_unscanned_locations target = scope:eu5ab_candidate_location } }
        }
    }
""" + "\n".join(dispatch_lines) + """
    every_in_list = { variable = eu5ab_scan_unscanned_locations remove_variable = eu5ab_bucket_need_score }
    every_in_list = { variable = eu5ab_worker_pending_locations remove_variable = eu5ab_bucket_need_score }
    if = { limit = { var:eu5ab_scan_parallel <= 0 } eu5ab_merge_location_worker_results = yes }
}
"""


def render_events() -> str:
    return """
eu5ab_monthly.3 = {
    type = country_event
    title = eu5ab_window_title
    outcome = neutral
    hidden = yes
    immediate = {
        save_scope_as = actor
        eu5ab_expire_old_scan_month = yes
        if = {
            limit = { eu5ab_queue_calendar_open = yes has_variable = eu5ab_scan_refill_active NOT = { has_variable = eu5ab_q_active } NOT = { has_variable = eu5ab_scan_resume_after_load }
                OR = { NOT = { has_variable = eu5ab_scan_dispatch_day } NOT = { var:eu5ab_scan_dispatch_day = eu5ab_pl_today } } }
            set_variable = { name = eu5ab_scan_dispatch_day value = eu5ab_pl_today }
            eu5ab_finish_pending_capacity_workers = yes
            eu5ab_merge_location_worker_results = yes
            if = { limit = { var:eu5ab_global_enabled > 0 } eu5ab_check_scan_refill_progress = yes }
            if = {
                limit = { NOT = { has_variable = eu5ab_scan_refill_active } }
                # Recovery has closed this month's exhausted/stalled work.
            }
            else_if = {
                limit = { NOT = { var:eu5ab_global_enabled > 0 } }
                eu5ab_clear_engine_candidate_queue = yes
                eu5ab_reset_committed_construction_demand = yes
                remove_variable = eu5ab_scan_active
                eu5ab_complete_scan_round = yes
            }
            else_if = {
                limit = {
                    eu5ab_scan_attempt_count < { value = var:eu5ab_deep_score_budget }
                    has_variable_list = eu5ab_scan_unscanned_locations
                    OR = { NOT = { has_variable = eu5ab_scan_active } eu5ab_scan_early_stop_value <= 0 eu5ab_scan_reserve_count < { value = var:eu5ab_scan_candidate_target } }
                }
                eu5ab_refill_regional_development_scan = yes
                trigger_event_silently = { id = eu5ab_monthly.3 days = 1 }
            }
            else = {
                remove_variable = eu5ab_scan_refill_active
                if = { limit = { has_variable = eu5ab_scan_active } eu5ab_finish_regional_development_scan = yes }
                else = { eu5ab_complete_scan_round = yes eu5ab_reset_committed_construction_demand = yes }
            }
        }
    }
}
"""
