"""Calendar boundaries for persisted monthly scans and construction queues."""
import re

from .script_syntax import parse


def render_triggers():
    scan_days = ' '.join(f'current_day = {day}' for day in range(2, 23))
    queue_days = ' '.join(f'current_day = {day}' for day in range(23, 32))
    months = ' '.join(f'AND = {{ current_month = {m} var:eu5ab_scan_month = {m} }}' for m in range(1, 13))
    return f'''eu5ab_scan_month_current = {{
    has_variable = eu5ab_scan_year has_variable = eu5ab_scan_month
    var:eu5ab_scan_year = current_year OR = {{ {months} }}
}}
eu5ab_scan_calendar_open = {{ OR = {{ {scan_days} }} }}
eu5ab_queue_calendar_open = {{ eu5ab_scan_month_current = yes OR = {{ {queue_days} }} }}
'''


def render_effects():
    stamp = '\n'.join(f'    if = {{ limit = {{ current_month = {m} }} set_variable = {{ name = eu5ab_scan_month value = {m} }} }}' for m in range(1, 13))
    return '''eu5ab_stamp_scan_month = {
    set_variable = { name = eu5ab_scan_year value = current_year }
''' + stamp + '''
}
eu5ab_expire_old_scan_month = {
    if = { limit = { OR = { NOT = { eu5ab_scan_month_current = yes }
        AND = { has_variable = eu5ab_q_active NOT = { eu5ab_queue_calendar_open = yes } } }
        OR = {
        has_variable = eu5ab_scan_round_active has_variable = eu5ab_scan_active
        has_variable = eu5ab_scan_refill_active has_variable = eu5ab_q_active
        has_variable = eu5ab_scan_resume_after_load
        has_variable_list = eu5ab_q_approved_locations has_variable_list = eu5ab_worker_pending_locations
    } }
        # No continuation or approval can execute while physical starts settle.
        remove_variable = eu5ab_q_active remove_variable = eu5ab_q_fire
        eu5ab_settle_saved_approvals = yes
        eu5ab_count_capacity_waiting = yes
        set_variable = { name = eu5ab_diag_capacity_expired value = 0 }
        if = { limit = { var:eu5ab_diag_capacity_waiting > 0 }
            set_variable = { name = eu5ab_diag_capacity_expired value = var:eu5ab_diag_capacity_waiting }
            set_variable = { name = eu5ab_diag_scan_stalled value = 1 }
        }
        save_scope_as = eu5ab_expiring_country
        every_in_list = { variable = eu5ab_worker_pending_locations
            limit = { owner = scope:eu5ab_expiring_country }
            eu5ab_clear_location_worker_state = yes eu5ab_clear_location_candidate_state = yes
        }
        clear_variable_list = eu5ab_worker_pending_locations
        eu5ab_clear_engine_candidate_queue = yes
        set_variable = { name = eu5ab_q_planned_spend value = 0 }
        set_variable = { name = eu5ab_q_planned_budget value = 0 }
        eu5ab_reset_committed_construction_demand = yes
        eu5ab_clear_scan_continuation = yes
        remove_variable = eu5ab_scan_active remove_variable = eu5ab_scan_finalizing
        remove_variable = eu5ab_scan_bucket_day remove_variable = eu5ab_scan_resume_after_load
        remove_variable = eu5ab_scan_dispatch_day
    }
}
'''


def guard_effects(text, replace):
    """Guard entry points; settlement remains callable at a month boundary."""
    scopes = ('eu5ab_start_engine_candidate_queue', 'eu5ab_restart_engine_priority_phase',
              'eu5ab_prepare_engine_priority_phase', 'eu5ab_try_best_remaining_rgo',
              'eu5ab_refill_regional_development_scan', 'eu5ab_resume_saved_queue')
    for name in scopes:
        # Top-level closers are unindented. Preserve the original statements
        # and comments so adding a date gate does not rewrite the whole body.
        block = re.search(r'^' + re.escape(name) + r' = \{\n(.*?)^\}', text, re.M | re.S)
        if block is None:
            raise ValueError(f'Missing monthly queue entry point: {name}')
        body = '\n'.join('\t' + line for line in block[1].rstrip('\n').split('\n'))
        guarded = (name + ' = {\n\tif = { limit = { eu5ab_queue_calendar_open = yes }\n'
                   + body + '\n\t}\n}')
        parse(guarded)
        text = replace(text, name, guarded)
    return text + render_effects()
