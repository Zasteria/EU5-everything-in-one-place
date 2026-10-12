"""Queue work that requires no GUI values or GUI command transport."""

CHECK_STAGE_GUARD = '''exists = scope:eu5ab_engine_queue_check_stage OR = {
    AND = { scope:eu5ab_engine_queue_check_stage = 0 has_variable = eu5ab_q_profit_selecting }
    AND = { scope:eu5ab_engine_queue_check_stage > 0
        var:eu5ab_q_phase = scope:eu5ab_engine_queue_check_stage
        NOT = { has_variable = eu5ab_q_profit_selecting } }
}'''


def render_control_effects(actual_profit_mode: int) -> str:
    """Country controls are shared by native events and legacy save callbacks.

    Completion checks never spend a timeout. Only a tagged scheduling pulse
    may do that, after rechecking its origin following every stage transition.
    """
    return f'''eu5ab_check_engine_phase_completion = {{
    if = {{ limit = {{ has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes
        NOT = {{ has_variable = eu5ab_scan_resume_after_load }} NOT = {{ has_variable = eu5ab_q_fire }}
        has_variable = eu5ab_q_phase has_variable = eu5ab_q_processed has_variable = eu5ab_q_expected
        has_variable = eu5ab_q_approved has_variable = eu5ab_q_seen
        has_variable = eu5ab_constructions_started_this_tick has_variable = eu5ab_monthly_build_quota }}
        if = {{ limit = {{ eu5ab_q_outstanding_approvals_value > 0 var:eu5ab_q_seen >= {{ value = var:eu5ab_q_approved }} }}
            set_variable = {{ name = eu5ab_q_fire value = 1 }}
            set_variable = {{ name = eu5ab_diag_queue_state value = 3 }}
        }}
        else_if = {{ limit = {{ var:eu5ab_q_processed >= {{ value = var:eu5ab_q_expected }} }}
        if = {{ limit = {{ var:eu5ab_constructions_started_this_tick >= var:eu5ab_monthly_build_quota }}
            eu5ab_finish_engine_candidate_queue = yes
        }}
        else_if = {{ limit = {{ var:eu5ab_global_candidate_ranking_mode = {actual_profit_mode}
            NOT = {{ has_variable = eu5ab_q_profit_selecting }} }}
            eu5ab_prepare_actual_profit_selection = yes
        }}
        else_if = {{ limit = {{ has_variable = eu5ab_q_retry_phase eu5ab_q_waiting_data_value <= 0 }}
            eu5ab_restart_engine_priority_phase = yes
        }}
        else_if = {{ limit = {{ eu5ab_q_waiting_data_value <= 0 }}
            eu5ab_advance_engine_priority_phase = yes
        }}
        }}
    }}
}}
eu5ab_check_engine_confirmation_completion = {{
    if = {{ limit = {{ has_variable = eu5ab_q_active has_variable = eu5ab_q_fire
        eu5ab_queue_calendar_open = yes NOT = {{ has_variable = eu5ab_scan_resume_after_load }}
        has_variable = eu5ab_q_confirmed has_variable = eu5ab_q_approved
        has_variable = eu5ab_constructions_started_this_tick has_variable = eu5ab_monthly_build_quota
        var:eu5ab_q_confirmed >= {{ value = var:eu5ab_q_approved }} }}
        if = {{ limit = {{ var:eu5ab_q_processed < var:eu5ab_q_expected
            var:eu5ab_constructions_started_this_tick < var:eu5ab_monthly_build_quota }}
            remove_variable = eu5ab_q_fire
            set_variable = {{ name = eu5ab_q_confirm_stall_rounds value = 0 }}
            set_variable = {{ name = eu5ab_diag_queue_state value = 6 }}
        }}
        else_if = {{ limit = {{ var:eu5ab_constructions_started_this_tick < {{ value = var:eu5ab_monthly_build_quota }}
            OR = {{ has_variable = eu5ab_q_retry_phase eu5ab_q_waiting_data_value > 0 }} }}
            eu5ab_restart_engine_priority_phase = yes
        }}
        else_if = {{ limit = {{ var:eu5ab_constructions_started_this_tick < {{ value = var:eu5ab_monthly_build_quota }} }}
            eu5ab_advance_engine_priority_phase = yes
        }}
        else = {{ eu5ab_finish_engine_candidate_queue = yes }}
    }}
}}
eu5ab_confirm_requested_engine_candidate = {{
    if = {{ limit = {{ owner = scope:eu5ab_engine_country
        owner = {{ has_variable = eu5ab_q_active has_variable = eu5ab_q_fire eu5ab_queue_calendar_open = yes
            NOT = {{ has_variable = eu5ab_scan_resume_after_load }} }}
        has_variable = eu5ab_q_fire_requested
        is_target_in_variable_list = {{ name = eu5ab_q_approved_types target = scope:eu5ab_candidate_building }}
        NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_confirmed_types target = scope:eu5ab_candidate_building }} }} }}
        eu5ab_confirm_engine_candidate = yes
        owner = {{ eu5ab_check_engine_confirmation_completion = yes }}
    }}
}}
# Compatibility entry for already queued, stage-tagged GUI callbacks.
# Current data callbacks can call the completion-only effect directly.
eu5ab_tick_engine_script_queue = {{
    if = {{ limit = {{ {CHECK_STAGE_GUARD} }} eu5ab_process_script_rgo_queue = yes }}
    if = {{ limit = {{ {CHECK_STAGE_GUARD} has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes
        NOT = {{ has_variable = eu5ab_scan_resume_after_load }} }}
        eu5ab_retry_waiting_candidate_data = yes
        eu5ab_check_engine_phase_completion = yes
    }}
    if = {{ limit = {{ {CHECK_STAGE_GUARD} has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes
        NOT = {{ has_variable = eu5ab_scan_resume_after_load }} NOT = {{ has_variable = eu5ab_q_fire }}
        eu5ab_q_waiting_data_value <= 0 has_variable = eu5ab_q_processed has_variable = eu5ab_q_seen
        has_variable = eu5ab_q_progress_last has_variable = eu5ab_q_stall_rounds }}
        set_variable = {{ name = eu5ab_q_progress_now value = var:eu5ab_q_processed }}
        change_variable = {{ name = eu5ab_q_progress_now add = var:eu5ab_q_seen }}
        if = {{ limit = {{ var:eu5ab_q_progress_now > {{ value = var:eu5ab_q_progress_last }} }}
            set_variable = {{ name = eu5ab_q_progress_last value = var:eu5ab_q_progress_now }}
            set_variable = {{ name = eu5ab_q_stall_rounds value = 0 }}
        }}
        else = {{
            change_variable = {{ name = eu5ab_q_stall_rounds add = 1 }}
            if = {{ limit = {{ var:eu5ab_q_stall_rounds >= 12 }}
                change_variable = {{ name = eu5ab_diag_queue_recoveries add = 1 }}
                set_variable = {{ name = eu5ab_diag_queue_state value = 5 }}
                eu5ab_finish_engine_candidate_queue = yes
            }}
        }}
    }}
}}
eu5ab_tick_engine_script_confirmation = {{
    # Capture the phase before completion; late confirmation pulses cannot
    # spend a new phase's timeout after a successful restart or advance.
    if = {{ limit = {{ has_variable = eu5ab_q_active has_variable = eu5ab_q_fire
        eu5ab_queue_calendar_open = yes NOT = {{ has_variable = eu5ab_scan_resume_after_load }} }}
        eu5ab_check_engine_confirmation_completion = yes
        if = {{ limit = {{ has_variable = eu5ab_q_active has_variable = eu5ab_q_fire
            has_variable = eu5ab_q_confirm_stall_rounds }}
            change_variable = {{ name = eu5ab_q_confirm_stall_rounds add = 1 }}
            if = {{ limit = {{ var:eu5ab_q_confirm_stall_rounds >= 12 }}
                change_variable = {{ name = eu5ab_diag_queue_recoveries add = 1 }}
                set_variable = {{ name = eu5ab_diag_queue_state value = 5 }}
                eu5ab_finish_engine_candidate_queue = yes
            }}
        }}
    }}
}}
'''


def render_effects(rgo_phase_count: int) -> str:
    phases = '\n'.join(f'''        {phase} = {{
            ordered_in_list = {{
                variable = eu5ab_q_phase_{phase}_rgo_locations
                limit = {{ owner = scope:eu5ab_engine_country NOT = {{ has_variable = eu5ab_q_done_rgo }} }}
                order_by = 1 max = 1 check_range_bounds = no
                save_scope_as = eu5ab_candidate_location
                set_variable = eu5ab_q_done_rgo
                eu5ab_prepare_rgo_dependencies = yes
                scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_q_processed add = 1 }} }}
                if = {{ limit = {{ NOT = {{ has_variable = eu5ab_q_waiting_rgo }} }}
                    scope:eu5ab_engine_country = {{ eu5ab_try_best_remaining_rgo = yes }}
                }}
            }}
        }}''' for phase in range(1, rgo_phase_count + 1))
    return f'''# Root country. Consume at most one RGO completion token per check, after
# the independent native parallel reader has published. Re-rank live after
# each start, using the existing safety/price/workforce/budget script gates.
eu5ab_process_script_rgo_queue = {{
    if = {{ limit = {{ has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes
        NOT = {{ has_variable = eu5ab_scan_resume_after_load }}
        NOT = {{ has_variable = eu5ab_q_fire }} NOT = {{ has_variable = eu5ab_q_profit_selecting }} }}
        save_scope_as = eu5ab_engine_country
        save_scope_as = actor
        switch = {{ trigger = var:eu5ab_q_phase
{phases}
        }}
    }}
}}
# Root approved location. This acknowledges the approved script list itself;
# no engine quote, capacity sample, or client widget inspection is involved.
eu5ab_acknowledge_approved_engine_candidate = {{
    if = {{ limit = {{
        owner = scope:eu5ab_engine_country
        scope:eu5ab_engine_country = {{ has_variable = eu5ab_q_active
            eu5ab_queue_calendar_open = yes NOT = {{ has_variable = eu5ab_scan_resume_after_load }}
            OR = {{ NOT = {{ has_variable = eu5ab_q_fire }}
                AND = {{ has_variable = eu5ab_q_profit_selecting has_variable = eu5ab_winner_ticket }} }} }}
        is_target_in_variable_list = {{ name = eu5ab_q_approved_types target = scope:eu5ab_candidate_building }}
        NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_seen_types target = scope:eu5ab_candidate_building }} }}
    }}
        add_to_variable_list = {{ name = eu5ab_q_seen_types target = scope:eu5ab_candidate_building }}
        scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_q_seen add = 1 }} }}
    }}
}}
'''
