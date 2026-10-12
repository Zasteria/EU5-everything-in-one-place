"""Concurrent native winner reads, followed by ordered server validation.

The batch has an independent ticket so receipts can arrive during a physical
start. Approval consumes only the ready prefix of the ranked pool; cash and
materials remain reserved serially. Retries/load/phase changes invalidate it.
"""
from . import quote_cache, construction_slots, queue_validation

TICKET = 'eu5ab_winner_ticket'
FIELDS = (*quote_cache.FIELDS, 'parallel_modifier')
VARIABLES = (*FIELDS, 'ticket', 'type', 'requested', 'data_ready', 'parallel_needed',
             'parallel_received', 'can_build', 'replaced_building')
COUNTRY = '''has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes
    NOT = { has_variable = eu5ab_scan_resume_after_load }
    has_variable = eu5ab_q_profit_selecting has_variable = eu5ab_winner_ticket
    var:eu5ab_winner_phase = var:eu5ab_q_phase
    var:eu5ab_winner_month = var:eu5ab_scan_month var:eu5ab_winner_year = var:eu5ab_scan_year'''
LOCATION = f'''owner = scope:eu5ab_engine_country has_variable = eu5ab_winner_requested
    exists = scope:{TICKET} scope:{TICKET} = var:eu5ab_winner_ticket
    scope:eu5ab_engine_country = {{ {COUNTRY} scope:{TICKET} = var:eu5ab_winner_ticket }}'''


def render_values():
    return '\n'.join(f'''eu5ab_winner_{field}_value = {{ value = 0
    if = {{ limit = {{ has_variable = eu5ab_winner_{field} }} add = var:eu5ab_winner_{field} }}
}}''' for field in FIELDS) + '\n'


def render_effects(rules):
    clear = ' '.join(f'remove_variable = eu5ab_winner_{field}' for field in VARIABLES)
    restore = '\n'.join(f'                save_scope_value_as = {{ name = eu5ab_engine_{field} value = eu5ab_winner_{field}_value }}'
                        for field in FIELDS)
    validate = '\n'.join(queue_validation.validation_lines(rules, profit=True,
        actual_profit_mode=2, can_build='has_variable = eu5ab_winner_can_build'))
    return f'''eu5ab_clear_location_winner = {{ {clear}
    clear_variable_list = eu5ab_winner_parallel_tickets
}}
eu5ab_clear_winner_batch = {{
    save_scope_as = eu5ab_winner_clear_country
    every_in_list = {{ variable = eu5ab_q_profit_locations limit = {{ owner = scope:eu5ab_winner_clear_country }}
        eu5ab_clear_location_winner = yes }}
    clear_variable_list = eu5ab_winner_locations_1 clear_variable_list = eu5ab_winner_locations_2
    remove_variable = eu5ab_winner_ticket remove_variable = eu5ab_winner_phase
    remove_variable = eu5ab_winner_month remove_variable = eu5ab_winner_year
    remove_variable = eu5ab_winner_waiting
}}
eu5ab_publish_winner_batch = {{
    save_scope_as = eu5ab_engine_country
    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_winner_ticket }} }}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_bridge_sequence }} }} set_variable = {{ name = eu5ab_bridge_sequence value = 0 }} }}
        change_variable = {{ name = eu5ab_bridge_sequence add = 1 }}
        set_variable = {{ name = eu5ab_winner_ticket value = var:eu5ab_bridge_sequence }}
        set_variable = {{ name = eu5ab_winner_phase value = var:eu5ab_q_phase }}
        set_variable = {{ name = eu5ab_winner_month value = var:eu5ab_scan_month }}
        set_variable = {{ name = eu5ab_winner_year value = var:eu5ab_scan_year }}
        if = {{ limit = {{ has_variable = eu5ab_bridge_lane var:eu5ab_bridge_lane = 1 }} set_variable = {{ name = eu5ab_bridge_lane value = 2 }} }}
        else = {{ set_variable = {{ name = eu5ab_bridge_lane value = 1 }} }}
    }}
    ordered_in_list = {{ variable = eu5ab_bridge_unread_locations order_by = 1 max = var:eu5ab_q_expected check_range_bounds = no
        limit = {{ owner = scope:eu5ab_engine_country NOT = {{ has_variable = eu5ab_winner_requested }} }}
        save_scope_as = eu5ab_candidate_location
        eu5ab_clear_location_winner = yes
        set_variable = eu5ab_winner_requested
        set_variable = {{ name = eu5ab_winner_ticket value = scope:eu5ab_engine_country.var:eu5ab_winner_ticket }}
        ordered_in_list = {{ variable = eu5ab_q_profit_best_types order_by = 1 max = 1 check_range_bounds = no
            save_scope_as = eu5ab_candidate_building
            scope:eu5ab_candidate_location = {{ set_variable = {{ name = eu5ab_winner_type value = scope:eu5ab_candidate_building }} }} }}
        if = {{ limit = {{ num_civil_constructions > 0 }} set_variable = eu5ab_winner_parallel_needed
            add_to_variable_list = {{ name = eu5ab_winner_parallel_tickets target = var:eu5ab_winner_ticket }} }}
        scope:eu5ab_engine_country = {{
            if = {{ limit = {{ var:eu5ab_bridge_lane = 1 }} add_to_variable_list = {{ name = eu5ab_winner_locations_1 target = scope:eu5ab_candidate_location }} }}
            else = {{ add_to_variable_list = {{ name = eu5ab_winner_locations_2 target = scope:eu5ab_candidate_location }} }}
        }}
    }}
}}
eu5ab_process_winner_batch = {{
    if = {{ limit = {{ {COUNTRY} }}
        save_scope_as = actor save_scope_as = eu5ab_engine_country
        remove_variable = eu5ab_winner_waiting
        every_in_list = {{ variable = eu5ab_bridge_unread_locations limit = {{ owner = scope:eu5ab_engine_country }}
            if = {{ limit = {{ scope:eu5ab_engine_country = {{ NOT = {{ has_variable = eu5ab_winner_waiting }} }} }}
            save_scope_as = eu5ab_candidate_location
            if = {{ limit = {{ has_variable = eu5ab_winner_requested has_variable = eu5ab_winner_data_ready
                var:eu5ab_winner_ticket = scope:eu5ab_engine_country.var:eu5ab_winner_ticket
                OR = {{ NOT = {{ has_variable = eu5ab_winner_parallel_needed }} has_variable = eu5ab_winner_parallel_received }} }}
                var:eu5ab_winner_type = {{ save_scope_as = eu5ab_candidate_building }}
{restore}
                if = {{ limit = {{ exists = var:eu5ab_winner_replaced_building }}
                    var:eu5ab_winner_replaced_building = {{ save_scope_as = eu5ab_engine_replaced_building }}
                    remove_variable = eu5ab_quote_no_replacement }}
                else = {{ set_variable = eu5ab_quote_no_replacement }}
                eu5ab_prepare_candidate_dependencies = yes set_variable = eu5ab_q_profit_done
                scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_q_processed add = 1 }}
                    change_variable = {{ name = eu5ab_diag_engine_probes add = 1 }} }}
                if = {{ limit = {{ NOT = {{ has_variable = eu5ab_q_dependency_wait }} }}
{validate}
                }}
                if = {{ limit = {{ NOT = {{ has_variable = eu5ab_q_location_approved }} NOT = {{ has_variable = eu5ab_q_dependency_wait }}
                    eu5ab_location_has_parallel_room = yes scope:eu5ab_engine_country = {{
                        eu5ab_q_outstanding_approvals_value < {{ value = var:eu5ab_monthly_build_quota subtract = var:eu5ab_constructions_started_this_tick }} }} }}
                    add_to_variable_list = {{ name = eu5ab_q_failed_types target = scope:eu5ab_candidate_building }}
                    scope:eu5ab_engine_country = {{ set_variable = eu5ab_q_retry_phase }} }}
                remove_variable = eu5ab_quote_no_replacement
                scope:eu5ab_engine_country = {{
                    remove_list_variable = {{ name = eu5ab_bridge_unread_locations target = scope:eu5ab_candidate_location }}
                    remove_list_variable = {{ name = eu5ab_winner_locations_1 target = scope:eu5ab_candidate_location }}
                    remove_list_variable = {{ name = eu5ab_winner_locations_2 target = scope:eu5ab_candidate_location }} }}
                eu5ab_clear_location_winner = yes
            }}
            else = {{ scope:eu5ab_engine_country = {{ set_variable = eu5ab_winner_waiting }} }}
            }}
        }}
        eu5ab_check_engine_phase_completion = yes
    }}
}}
'''


def render_guis():
    scopes = ' '.join('eu5ab_engine_' + field for field in FIELDS)
    guards = ' '.join('exists = scope:eu5ab_engine_' + field for field in FIELDS)
    stores = '\n'.join(f'            set_variable = {{ name = eu5ab_winner_{field} value = scope:eu5ab_engine_{field} }}'
                       for field in FIELDS)
    guis = f'''eu5ab_gui_capture_winner = {{
    saved_scopes = {{ {TICKET} eu5ab_engine_country eu5ab_candidate_building {scopes} eu5ab_engine_can_build eu5ab_engine_replaced_building }}
    is_valid = {{ always = yes }}
    effect = {{ if = {{ limit = {{ {LOCATION} var:eu5ab_winner_type = scope:eu5ab_candidate_building
        {guards} exists = scope:eu5ab_engine_can_build NOT = {{ has_variable = eu5ab_winner_data_ready }} }}
{stores}
        if = {{ limit = {{ scope:eu5ab_engine_can_build = yes }} set_variable = eu5ab_winner_can_build }}
        else = {{ remove_variable = eu5ab_winner_can_build }}
        if = {{ limit = {{ exists = scope:eu5ab_engine_replaced_building }}
            set_variable = {{ name = eu5ab_winner_replaced_building value = scope:eu5ab_engine_replaced_building }} }}
        set_variable = eu5ab_winner_data_ready
        scope:eu5ab_engine_country = {{ eu5ab_process_winner_batch = yes eu5ab_dispatch_queue_bridge = yes }}
    }} }}
}}
'''
    for suffix, effect in (('parallel', 'eu5ab_capture_parallel_queue = yes'), ('parallel_overflow', 'eu5ab_clear_parallel_capacity = yes')):
        guis += f'''eu5ab_gui_capture_winner_{suffix} = {{
    saved_scopes = {{ {TICKET} eu5ab_engine_country eu5ab_engine_queue_count eu5ab_engine_queue_has_room eu5ab_engine_parallel_modifier }}
    is_valid = {{ always = yes }}
    effect = {{ if = {{ limit = {{ {LOCATION} has_variable = eu5ab_winner_parallel_needed
        NOT = {{ has_variable = eu5ab_winner_parallel_received }} }}
        {effect} set_variable = eu5ab_winner_parallel_received clear_variable_list = eu5ab_winner_parallel_tickets
        scope:eu5ab_engine_country = {{ eu5ab_process_winner_batch = yes eu5ab_dispatch_queue_bridge = yes }}
    }} }}
}}
'''
    return guis


def render_widget(engine_arguments):
    widgets = []
    args = engine_arguments + f".AddScope('{TICKET}', MakeScopeValue(Location.MakeScope.GetVariable('{TICKET}').GetValue)).End"
    for lane in (1, 2):
        prefix = 'eu5ab_winner_batch_' + str(lane)
        parallel = construction_slots.capture_widget(prefix + '_parallel', bridge=True)
        parallel = parallel.replace('eu5ab_bridge_parallel_tickets', 'eu5ab_winner_parallel_tickets').replace('eu5ab_bridge_ticket', TICKET)
        parallel = parallel.replace('eu5ab_gui_capture_parallel_queue', 'eu5ab_gui_capture_winner_parallel').replace('eu5ab_gui_clear_parallel_queue', 'eu5ab_gui_capture_winner_parallel_overflow')
        # Each visible count selector sends once. A per-row global animation
        # broadcast would multiply N readers into N-squared GUI commands.
        parallel = parallel.replace('name = _show alpha = 1 }',
            f'name = _show alpha = 1 duration = 0.01 next = {prefix}_parallel_sample }}')
        parallel = parallel.replace(f'name = {prefix}_parallel_sample on_finish',
            f'name = {prefix}_parallel_sample alpha = 0 duration = 0.01 on_finish')
        widgets.append(f'''widget = {{ datamodel = "[GetPlayer.MakeScope.GetList('eu5ab_winner_locations_{lane}')]"
    item = {{ widget = {{ datacontext = "[Scope.GetLocation]"
        {parallel}
        widget = {{ datacontext = "[Location.MakeScope.GetVariable('eu5ab_winner_type').GetBuildingType]"
            visible_at_creation = no visible = "[GetPlayer.Exists]"
            state = {{ name = _hide alpha = 0 }}
            state = {{ name = _show alpha = 1 duration = 0.01
                on_finish = "[GetScriptedGui('eu5ab_gui_capture_winner').Execute({args})]" }}
        }}
    }} }}
}}''')
    return '\n'.join(widgets)


def apply_effects(text):
    for name in ('eu5ab_prepare_actual_profit_selection', 'eu5ab_reset_engine_priority_phase_progress',
                 'eu5ab_clear_engine_candidate_queue', 'eu5ab_recover_runtime_after_load'):
        text = text.replace(name + ' = {', name + ' = {\n    eu5ab_clear_winner_batch = yes', 1)
    return text.replace('eu5ab_clear_location_candidate_state = {',
        'eu5ab_clear_location_candidate_state = {\n    eu5ab_clear_location_winner = yes', 1)
