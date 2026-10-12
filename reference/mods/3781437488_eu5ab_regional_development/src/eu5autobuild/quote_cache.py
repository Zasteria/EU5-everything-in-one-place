"""Native screening transport and legacy profit-winner compatibility.

construction_batch extends captures to both modes and owns current ordinary
dispatch; the winner routines below remain readable for interrupted old saves.

Readiness is independent of numeric values, including zero. A location ticket
identifies one owner/month generation and survives retries of the same phase.
"""
from . import building_capacity
from .food_infrastructure import FOOD_BUILDING_FINAL_GATES

FIELDS = ('cost', 'income', 'profit', 'province_food_balance',
          'province_food_natural', 'rgo_revenue')
CACHE_FIELDS = (*FIELDS, 'capacity_factor')
TICKET = 'eu5ab_quote_ticket'


def render_triggers():
    return '''eu5ab_quote_context_current = {
    exists = var:eu5ab_quote_country owner ?= var:eu5ab_quote_country
    has_variable = eu5ab_quote_ticket has_variable = eu5ab_quote_month has_variable = eu5ab_quote_year
    owner ?= { eu5ab_scan_month_current = yes
        var:eu5ab_scan_month = prev.var:eu5ab_quote_month
        var:eu5ab_scan_year = prev.var:eu5ab_quote_year }
}
'''


def render_values():
    quotes = '\n'.join(f'''eu5ab_cached_quote_{field} = {{ value = 0
    if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_quote_{field} target = scope:eu5ab_candidate_building }} }}
        add = "variable_map(eu5ab_quote_{field}|scope:eu5ab_candidate_building)" }}
}}''' for field in CACHE_FIELDS)
    return quotes + '\n' + '\n'.join(['eu5ab_cached_capacity_profit_rank = {',
        *building_capacity.signed_value_lines('eu5ab_profit_candidate_rank_value',
            'eu5ab_cached_quote_capacity_factor'), '}', ''])


def render_effects(phase_count=16):
    clear = '\n'.join(f'    clear_variable_map = eu5ab_quote_{field}'
                      for field in (*CACHE_FIELDS, 'sample_day', 'replaced_building'))
    requests = '\n'.join(f'''        every_in_list = {{ variable = eu5ab_q_phase_{phase}_types
            limit = {{ NOT = {{ scope:eu5ab_candidate_location = {{ OR = {{
                is_target_in_variable_list = {{ name = eu5ab_quote_ready_types target = prev }}
                is_target_in_variable_list = {{ name = eu5ab_quote_requests target = prev }}
            }} }} }} }}
            save_scope_as = eu5ab_quote_request_type
            scope:eu5ab_candidate_location = {{ add_to_variable_list = {{ name = eu5ab_quote_requests target = scope:eu5ab_quote_request_type }} }}
        }}''' for phase in range(1, phase_count + 1))
    restore = '\n'.join(f'                        save_scope_value_as = {{ name = eu5ab_engine_{field} value = eu5ab_cached_quote_{field} }}'
                        for field in FIELDS)
    food = '\n'.join(f'                                scope:eu5ab_candidate_building = {{ {gate} = yes }}'
                     for gate, _ in FOOD_BUILDING_FINAL_GATES)
    return f'''eu5ab_clear_candidate_quotes = {{
    clear_variable_list = eu5ab_quote_requests clear_variable_list = eu5ab_quote_ready_types
    clear_variable_list = eu5ab_quote_tickets
{clear}
    remove_variable = eu5ab_quote_ticket remove_variable = eu5ab_quote_country
    remove_variable = eu5ab_quote_month remove_variable = eu5ab_quote_year
    remove_variable = eu5ab_quote_no_replacement remove_variable = eu5ab_quote_replacement
}}
# Called by the country reducer after staging, never by parallel workers.
eu5ab_request_candidate_quotes = {{
    if = {{ limit = {{ owner = {{ eu5ab_scan_month_current = yes var:eu5ab_global_candidate_ranking_mode = 2 }} }}
        save_scope_as = eu5ab_candidate_location
        if = {{ limit = {{ NOT = {{ eu5ab_quote_context_current = yes }} }}
            eu5ab_clear_candidate_quotes = yes
            set_variable = {{ name = eu5ab_quote_country value = owner }}
            set_variable = {{ name = eu5ab_quote_month value = owner.var:eu5ab_scan_month }}
            set_variable = {{ name = eu5ab_quote_year value = owner.var:eu5ab_scan_year }}
            owner = {{
                if = {{ limit = {{ NOT = {{ has_variable = eu5ab_quote_sequence }} }} set_variable = {{ name = eu5ab_quote_sequence value = 0 }} }}
                change_variable = {{ name = eu5ab_quote_sequence add = 1 }}
            }}
            set_variable = {{ name = eu5ab_quote_ticket value = owner.var:eu5ab_quote_sequence }}
        }}
{requests}
        eu5ab_prepare_quote_reader_ticket = yes
        owner = {{ if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_quote_locations target = scope:eu5ab_candidate_location }} }} }}
            add_to_variable_list = {{ name = eu5ab_quote_locations target = scope:eu5ab_candidate_location }} }} }}
        if = {{ limit = {{ has_variable_list = eu5ab_quote_requests }}
            owner = {{ if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_quote_pending_locations target = scope:eu5ab_candidate_location }} }} }}
                add_to_variable_list = {{ name = eu5ab_quote_pending_locations target = scope:eu5ab_candidate_location }} }} }}
        }}
    }}
}}
# One immutable numeric row per owner/month generation. Retries and load
# recovery rebuild this projection without changing the authoritative ticket.
eu5ab_prepare_quote_reader_ticket = {{
    if = {{ limit = {{ eu5ab_quote_context_current = yes
        NOT = {{ is_target_in_variable_list = {{ name = eu5ab_quote_tickets target = var:eu5ab_quote_ticket }} }} }}
        clear_variable_list = eu5ab_quote_tickets
        add_to_variable_list = {{ name = eu5ab_quote_tickets target = var:eu5ab_quote_ticket }}
    }}
}}
# No reservation or approval is allowed here. Preserve the original pool order
# even when native callbacks arrive out of order; pause at the first missing row.
eu5ab_rank_cached_queue = {{
    save_scope_as = actor save_scope_as = eu5ab_engine_country
    remove_variable = eu5ab_quote_waiting
    every_in_list = {{ variable = eu5ab_bridge_unread_locations
        limit = {{ owner = scope:eu5ab_engine_country scope:eu5ab_engine_country = {{ NOT = {{ has_variable = eu5ab_quote_waiting }} }} }}
        save_scope_as = eu5ab_candidate_location
        eu5ab_request_candidate_quotes = yes
        every_in_list = {{ variable = eu5ab_bridge_unread_types
            if = {{ limit = {{ scope:eu5ab_engine_country = {{ NOT = {{ has_variable = eu5ab_quote_waiting }} }} }}
            save_scope_as = eu5ab_candidate_building
            scope:eu5ab_candidate_location = {{
                if = {{ limit = {{ eu5ab_quote_context_current = yes
                    is_target_in_variable_list = {{ name = eu5ab_quote_ready_types target = scope:eu5ab_candidate_building }}
                    is_key_in_variable_map = {{ name = eu5ab_quote_sample_day target = scope:eu5ab_candidate_building }} }}
{restore}
                    if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_quote_replaced_building target = scope:eu5ab_candidate_building }} }}
                        set_variable = {{ name = eu5ab_quote_replacement value = "variable_map(eu5ab_quote_replaced_building|scope:eu5ab_candidate_building)" }}
                        var:eu5ab_quote_replacement = {{ save_scope_as = eu5ab_engine_replaced_building }}
                        remove_variable = eu5ab_quote_replacement
                        remove_variable = eu5ab_quote_no_replacement
                    }}
                    else = {{ set_variable = eu5ab_quote_no_replacement }}
                    eu5ab_prepare_candidate_dependencies = yes
                    add_to_variable_list = {{ name = eu5ab_q_done_types target = scope:eu5ab_candidate_building }}
                    scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_q_processed add = 1 }} }}
                    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_q_dependency_wait }}
                        NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_failed_types target = scope:eu5ab_candidate_building }} }} }}
                        eu5ab_refresh_native_recipes = yes
                        scope:eu5ab_candidate_building = {{ eu5ab_prepare_recipe_score_snapshot = yes }}
                        if = {{ limit = {{
                            scope:eu5ab_engine_cost > 0
                            eu5ab_engine_candidate_in_current_priority_phase = yes
                            scope:eu5ab_candidate_building = {{
                                eu5ab_candidate_route_allowed = yes
                                eu5ab_has_local_workforce = yes
                                eu5ab_output_not_oversupplied = yes
                                eu5ab_candidate_pending_allowed = yes
                                eu5ab_inputs_available = yes
                            }}
                            eu5ab_cached_quote_capacity_factor > 0
{food}
                            OR = {{ scope:eu5ab_candidate_building.eu5ab_recipe_expected_output_value <= 0
                                eu5ab_engine_candidate_passes_selected_metric = yes
                                eu5ab_engine_candidate_has_emergency_demand = yes }}
                        }} eu5ab_record_cached_profit_candidate = yes }}
                        eu5ab_clear_recipe_score_snapshot = yes
                    }}
                    remove_list_variable = {{ name = eu5ab_bridge_unread_types target = scope:eu5ab_candidate_building }}
                    remove_variable = eu5ab_quote_no_replacement
                }}
                else = {{ scope:eu5ab_engine_country = {{ set_variable = eu5ab_quote_waiting }} }}
            }}
            }}
        }}
        if = {{ limit = {{ NOT = {{ has_variable_list = eu5ab_bridge_unread_types }} }}
            scope:eu5ab_engine_country = {{ remove_list_variable = {{ name = eu5ab_bridge_unread_locations target = scope:eu5ab_candidate_location }} }} }}
    }}
}}
'''


def render_guis():
    fields = ' '.join(f'eu5ab_engine_{field}' for field in FIELDS)
    guards = ' '.join(f'exists = scope:eu5ab_engine_{field}' for field in FIELDS)
    store = '\n'.join(f'            add_to_variable_map = {{ name = eu5ab_quote_{field} key = scope:eu5ab_candidate_building value = scope:eu5ab_engine_{field} }}'
                      for field in FIELDS)
    return f'''eu5ab_gui_quote_request_pending = {{
    saved_scopes = {{ eu5ab_engine_country eu5ab_candidate_building {TICKET} }}
    is_shown = {{
        owner ?= scope:eu5ab_engine_country eu5ab_quote_context_current = yes
        scope:eu5ab_engine_country = {{ NOT = {{ has_variable = eu5ab_scan_resume_after_load }} }}
        exists = scope:{TICKET} scope:{TICKET} = var:eu5ab_quote_ticket
        exists = scope:eu5ab_candidate_building
        is_target_in_variable_list = {{ name = eu5ab_quote_requests target = scope:eu5ab_candidate_building }}
        NOT = {{ is_target_in_variable_list = {{ name = eu5ab_quote_ready_types target = scope:eu5ab_candidate_building }} }}
    }}
}}
eu5ab_gui_capture_candidate_quote = {{
    saved_scopes = {{ eu5ab_engine_country eu5ab_candidate_building {TICKET} {fields} eu5ab_engine_replaced_building }}
    is_valid = {{ always = yes }}
    effect = {{
        if = {{ limit = {{ owner ?= scope:eu5ab_engine_country eu5ab_quote_context_current = yes
            scope:eu5ab_engine_country = {{ NOT = {{ has_variable = eu5ab_scan_resume_after_load }} }}
            exists = scope:{TICKET} scope:{TICKET} = var:eu5ab_quote_ticket
            exists = scope:eu5ab_candidate_building {guards}
            is_target_in_variable_list = {{ name = eu5ab_quote_requests target = scope:eu5ab_candidate_building }}
            NOT = {{ is_target_in_variable_list = {{ name = eu5ab_quote_ready_types target = scope:eu5ab_candidate_building }} }} }}
{store}
            save_scope_as = eu5ab_candidate_location
            add_to_variable_map = {{ name = eu5ab_quote_capacity_factor key = scope:eu5ab_candidate_building value = eu5ab_engine_capacity_factor }}
            if = {{ limit = {{ exists = scope:eu5ab_engine_replaced_building }}
                add_to_variable_map = {{ name = eu5ab_quote_replaced_building key = scope:eu5ab_candidate_building value = scope:eu5ab_engine_replaced_building }} }}
            add_to_variable_map = {{ name = eu5ab_quote_sample_day key = scope:eu5ab_candidate_building value = eu5ab_pl_today }}
            add_to_variable_list = {{ name = eu5ab_quote_ready_types target = scope:eu5ab_candidate_building }}
            remove_list_variable = {{ name = eu5ab_quote_requests target = scope:eu5ab_candidate_building }}
            save_scope_as = eu5ab_quote_finished_location
            if = {{ limit = {{ NOT = {{ has_variable_list = eu5ab_quote_requests }} }}
                owner = {{ remove_list_variable = {{ name = eu5ab_quote_pending_locations target = scope:eu5ab_quote_finished_location }} }} }}
            owner = {{
                if = {{ limit = {{ has_variable = eu5ab_diag_engine_probes }} change_variable = {{ name = eu5ab_diag_engine_probes add = 1 }} }}
                else = {{ set_variable = {{ name = eu5ab_diag_engine_probes value = 1 }} }}
                remove_variable = eu5ab_quote_waiting
                eu5ab_dispatch_queue_bridge = yes
            }}
        }}
    }}
}}
'''


def render_widget(engine_arguments):
    # Read the original pending queues directly, without a batch publisher or
    # cross-row wait. Reject completed/stale rows before native getter creation.
    import re
    args = re.sub(r"\.AddScope\('eu5ab_engine_can_build', MakeScopeBool\(CanBuildOrExpandBuilding\(BuildingType.Self, Location.Self\)\)\)", '', engine_arguments)
    args = re.sub(r"\.AddScope\('eu5ab_engine_parallel_modifier', .*?(?=\.AddScope|$)", '', args)
    ticket = f".AddScope('{TICKET}', MakeScopeValue(Scope.GetValue))"
    args += ticket + ".End"
    pending = "GetScriptedGui('eu5ab_gui_quote_request_pending').IsShown(GuiScope.SetRoot(Location.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope).AddScope('eu5ab_candidate_building', BuildingType.MakeScope)" + ticket + ".End)"
    return f'''widget = {{
    name = "eu5ab_quote_reader_root"
    datamodel = "[DataModelRepeatedItem(Select_int32(GetPlayer.Exists, '(int32)1', '(int32)0'))]"
    item = {{ widget = {{
widget = {{
    # Explicit activation, like the capacity reader. No native getters on
    # _show: recreated widgets only read when the pending guard accepts them.
    state = {{ name = _show alpha = 1 next = eu5ab_quote_capture_loop }}
    state = {{ name = eu5ab_quote_capture_init trigger_on_create = yes
        alpha = 1 duration = 0.1 next = eu5ab_quote_capture_loop }}
    state = {{ name = eu5ab_quote_capture_loop alpha = 0 duration = 0.1
        on_finish = "[PdxGuiTriggerAllAnimations('eu5ab_quote_capture')]"
        next = eu5ab_quote_capture_wait }}
    state = {{ name = eu5ab_quote_capture_wait alpha = 1 duration = 0.01
        next = eu5ab_quote_capture_loop }}
}}
widget = {{
    datamodel = "[GetPlayer.MakeScope.GetList('eu5ab_quote_pending_locations')]"
    item = {{ widget = {{ datacontext = "[Scope.GetLocation]"
        widget = {{ datamodel = "[Location.MakeScope.GetList('eu5ab_quote_requests')]"
            item = {{ widget = {{ datacontext = "[Scope.GetBuildingType]"
                widget = {{ datamodel = "[Location.MakeScope.GetList('eu5ab_quote_tickets')]"
                    item = {{ widget = {{
                widget = {{ datamodel = "[DataModelRepeatedItem(Select_int32({pending}, '(int32)1', '(int32)0'))]"
                    item = {{ widget = {{
                        visible_at_creation = no visible = "[GetPlayer.Exists]"
                        state = {{ name = _hide alpha = 0 }}
                        state = {{ name = _show alpha = 1 }}
                        state = {{ name = eu5ab_quote_capture alpha = 0 duration = 0.01
                            on_finish = "[GetScriptedGui('eu5ab_gui_capture_candidate_quote').Execute({args})]" }}
                    }} }}
                }}
                    }} }}
                }}
            }} }}
        }}
    }} }}
}}
    }} }}
}}
'''


def apply_effects(text, replace, block):
    import re
    source = block(text, 'eu5ab_record_actual_profit_candidate')
    cached = source.replace('eu5ab_record_actual_profit_candidate = {',
                            'eu5ab_record_cached_profit_candidate = {', 1)
    cached = cached.replace('value = eu5ab_capacity_profit_rank', 'value = eu5ab_cached_capacity_profit_rank')
    # Read at most enough location winners to fill the remaining monthly quota.
    # Rejected winners retain the existing bounded retry after approvals settle.
    name = 'eu5ab_prepare_actual_profit_selection'
    source = block(text, name)
    cap = re.search(r'max = (\d+)\s+check_range_bounds = no', source)[1]
    source = source.replace(name + ' = {', name + ''' = {
    set_variable = { name = eu5ab_quote_winner_limit value = {
        value = var:eu5ab_monthly_build_quota subtract = var:eu5ab_constructions_started_this_tick
        min = 0 max = ''' + cap + ''' } }''', 1)
    source = re.sub(r'max = \d+(?=\s+check_range_bounds = no)', 'max = var:eu5ab_quote_winner_limit', source)
    source = source[:-1] + '\n    remove_variable = eu5ab_quote_winner_limit\n}'
    text = replace(text, name, source)
    name = 'eu5ab_merge_location_worker_results'
    source = block(text, name)
    marker = '\t\tremove_variable = eu5ab_worker_complete'
    if source.count(marker) != 1:
        raise ValueError('Worker merge quote hook must be unique')
    text = replace(text, name, source.replace(marker, '\t\teu5ab_request_candidate_quotes = yes\n' + marker))
    name = 'eu5ab_stage_engine_candidate'
    source = block(text, name)
    text = replace(text, name, source[:-1] + '\n    if = { limit = { NOT = { has_variable = eu5ab_worker_active } } eu5ab_request_candidate_quotes = yes }\n}')
    text = text.replace('eu5ab_clear_location_candidate_state = {',
        'eu5ab_clear_location_candidate_state = {\n    eu5ab_clear_candidate_quotes = yes', 1)
    text = text.replace('eu5ab_clear_engine_candidate_queue = {',
        '''eu5ab_clear_engine_candidate_queue = {
    save_scope_as = eu5ab_quote_clear_country
    every_in_list = { variable = eu5ab_quote_locations limit = { owner = scope:eu5ab_quote_clear_country }
        eu5ab_clear_candidate_quotes = yes }
    clear_variable_list = eu5ab_quote_locations
    clear_variable_list = eu5ab_quote_pending_locations remove_variable = eu5ab_quote_waiting''', 1)
    text = text.replace('eu5ab_reset_engine_priority_phase_progress = {',
        'eu5ab_reset_engine_priority_phase_progress = {\n    remove_variable = eu5ab_quote_waiting', 1)
    text = text.replace('eu5ab_recover_runtime_after_load = {',
        '''eu5ab_recover_runtime_after_load = {
    remove_variable = eu5ab_quote_waiting
    save_scope_as = eu5ab_quote_restore_country
    every_in_list = { variable = eu5ab_quote_pending_locations
        limit = { owner ?= scope:eu5ab_quote_restore_country }
        eu5ab_prepare_quote_reader_ticket = yes
    }''', 1)
    return text + '\n' + cached + '\n' + render_effects()
