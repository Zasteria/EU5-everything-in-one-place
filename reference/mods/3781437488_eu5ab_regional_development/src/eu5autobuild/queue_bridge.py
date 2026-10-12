"""Finite GUI transport for the existing queue; no daily batch scheduler.

Full phase pools and original completion counters remain authoritative. The
bridge derives unread indexes once per phase/retry. Profit winners share a
concurrent read batch; physical starts retain the existing one-request guard.
Sequence numbers survive months and saves; a same-phase retry cannot reuse one.
"""
import re

TICKET = 'eu5ab_bridge_ticket'
KINDS = {'candidate': 1, 'profit': 2, 'rgo': 3, 'fire': 4}
ACTIVE = '''has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes
    NOT = { has_variable = eu5ab_scan_resume_after_load }'''
CURRENT = f'''{ACTIVE} exists = scope:{TICKET} has_variable = eu5ab_bridge_request
    scope:{TICKET} = var:eu5ab_bridge_request
    var:eu5ab_bridge_phase = var:eu5ab_q_phase
    var:eu5ab_bridge_month = var:eu5ab_scan_month
    var:eu5ab_bridge_year = var:eu5ab_scan_year'''
READER_LOCATION = f'''owner = scope:eu5ab_engine_country
    scope:eu5ab_engine_country = {{ {CURRENT} var:eu5ab_bridge_location = prev }}'''
LOCATION = f'''{READER_LOCATION}
    OR = {{ scope:eu5ab_engine_country.var:eu5ab_bridge_kind = 3
        scope:eu5ab_engine_country.var:eu5ab_bridge_type = scope:eu5ab_candidate_building }}'''
COMPATIBLE = f'''OR = {{ owner = {{ NOT = {{ has_variable = eu5ab_bridge_schema }} }}
    AND = {{ {LOCATION} }} }}'''


def ticket_argument():
    return f".AddScope('{TICKET}', MakeScopeValue(Scope.GetValue))"


def _block(text, name):
    start = re.search(r'^' + re.escape(name) + r' = \{', text, re.M).start()
    depth = 0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|#[^\n]*|[{}]', text[start:]):
        if token[0] == '{':
            depth += 1
        elif token[0] == '}':
            depth -= 1
            if depth == 0:
                return text[start:start + token.end()]
    raise ValueError('Unclosed ' + name)


def render_effects(phase_count: int, rgo_phase_count: int) -> str:
    derive = []
    for phase in range(1, phase_count + 1):
        derive.append(f'''{phase} = {{
            every_in_list = {{ variable = eu5ab_q_phase_{phase}_locations
                limit = {{ owner = scope:eu5ab_engine_country }}
                save_scope_as = eu5ab_candidate_location
                clear_variable_list = eu5ab_bridge_unread_types
                every_in_list = {{ variable = eu5ab_q_phase_{phase}_types
                    limit = {{ NOT = {{ scope:eu5ab_candidate_location = {{
                        is_target_in_variable_list = {{ name = eu5ab_q_done_types target = prev }} }} }} }}
                    save_scope_as = eu5ab_candidate_building
                    scope:eu5ab_candidate_location = {{ add_to_variable_list = {{ name = eu5ab_bridge_unread_types target = scope:eu5ab_candidate_building }} }}
                    scope:eu5ab_engine_country = {{ change_variable = {{ name = eu5ab_q_expected add = 1 }} }}
                }}
                if = {{ limit = {{ has_variable_list = eu5ab_bridge_unread_types }}
                    scope:eu5ab_engine_country = {{ add_to_variable_list = {{ name = eu5ab_bridge_unread_locations target = scope:eu5ab_candidate_location }} }} }}
            }}''')
        if phase <= rgo_phase_count:
            derive.append(f'''every_in_list = {{ variable = eu5ab_q_phase_{phase}_rgo_locations
                limit = {{ owner = scope:eu5ab_engine_country NOT = {{ has_variable = eu5ab_q_done_rgo }} }}
                save_scope_as = eu5ab_candidate_location
                scope:eu5ab_engine_country = {{ add_to_variable_list = {{ name = eu5ab_bridge_unread_rgos target = scope:eu5ab_candidate_location }}
                    change_variable = {{ name = eu5ab_q_expected add = 1 }} }}
            }}''')
        derive.append('}')
    clear_lists = '\n'.join(f'    clear_variable_list = eu5ab_bridge_{kind}_{lane}'
                           for kind in (*KINDS, 'confirmation') for lane in (1, 2))
    publish = '\n'.join(f'''{value} = {{ if = {{ limit = {{ var:eu5ab_bridge_lane = 1 }}
        add_to_variable_list = {{ name = eu5ab_bridge_{kind}_1 target = var:eu5ab_bridge_request }} }}
        else = {{ add_to_variable_list = {{ name = eu5ab_bridge_{kind}_2 target = var:eu5ab_bridge_request }} }} }}'''
                        for kind, value in KINDS.items())
    return f'''eu5ab_clear_queue_bridge = {{
    if = {{ limit = {{ exists = var:eu5ab_bridge_location }}
        save_scope_as = eu5ab_bridge_clear_country
        var:eu5ab_bridge_location = {{ if = {{ limit = {{ owner = scope:eu5ab_bridge_clear_country }}
            clear_variable_list = eu5ab_bridge_parallel_tickets }} }}
    }}
{clear_lists}
    clear_variable_map = eu5ab_bridge_request_locations clear_variable_map = eu5ab_bridge_request_types clear_variable_map = eu5ab_bridge_request_stages
    remove_variable = eu5ab_bridge_request remove_variable = eu5ab_bridge_location remove_variable = eu5ab_bridge_type
    remove_variable = eu5ab_bridge_kind remove_variable = eu5ab_bridge_parallel_needed remove_variable = eu5ab_bridge_parallel_received
    remove_variable = eu5ab_bridge_data_received remove_variable = eu5ab_bridge_request_day
}}
eu5ab_rebuild_queue_bridge = {{
    save_scope_as = eu5ab_engine_country
    clear_variable_list = eu5ab_bridge_unread_locations clear_variable_list = eu5ab_bridge_unread_rgos
    set_variable = {{ name = eu5ab_q_expected value = var:eu5ab_q_processed }}
    if = {{ limit = {{ has_variable = eu5ab_q_profit_selecting }}
        every_in_list = {{ variable = eu5ab_q_profit_locations
            limit = {{ owner = scope:eu5ab_engine_country NOT = {{ has_variable = eu5ab_q_profit_done }} }}
            save_scope_as = eu5ab_candidate_location
            clear_variable_list = eu5ab_bridge_unread_types
            every_in_list = {{ variable = eu5ab_q_profit_best_types save_scope_as = eu5ab_candidate_building
                scope:eu5ab_candidate_location = {{ add_to_variable_list = {{ name = eu5ab_bridge_unread_types target = scope:eu5ab_candidate_building }} }} }}
            if = {{ limit = {{ has_variable_list = eu5ab_bridge_unread_types }}
                scope:eu5ab_engine_country = {{ add_to_variable_list = {{ name = eu5ab_bridge_unread_locations target = scope:eu5ab_candidate_location }}
                    change_variable = {{ name = eu5ab_q_expected add = 1 }} }} }}
        }}
    }}
    else = {{ switch = {{ trigger = var:eu5ab_q_phase {' '.join(derive)} }} }}
    remove_variable = eu5ab_bridge_rebuild
}}
eu5ab_publish_queue_bridge = {{
    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_bridge_sequence }} }} set_variable = {{ name = eu5ab_bridge_sequence value = 0 }} }}
    change_variable = {{ name = eu5ab_bridge_sequence add = 1 }}
    set_variable = {{ name = eu5ab_bridge_request value = var:eu5ab_bridge_sequence }}
    set_variable = {{ name = eu5ab_bridge_request_day value = eu5ab_pl_today }}
    set_variable = {{ name = eu5ab_bridge_phase value = var:eu5ab_q_phase }}
    set_variable = {{ name = eu5ab_bridge_month value = var:eu5ab_scan_month }}
    set_variable = {{ name = eu5ab_bridge_year value = var:eu5ab_scan_year }}
    if = {{ limit = {{ has_variable = eu5ab_bridge_lane var:eu5ab_bridge_lane = 1 }} set_variable = {{ name = eu5ab_bridge_lane value = 2 }} }}
    else = {{ set_variable = {{ name = eu5ab_bridge_lane value = 1 }} }}
    add_to_variable_map = {{ name = eu5ab_bridge_request_locations key = var:eu5ab_bridge_request value = var:eu5ab_bridge_location }}
    add_to_variable_map = {{ name = eu5ab_bridge_request_stages key = var:eu5ab_bridge_request value = var:eu5ab_q_phase }}
    if = {{ limit = {{ var:eu5ab_bridge_kind = 2 }} add_to_variable_map = {{ name = eu5ab_bridge_request_stages key = var:eu5ab_bridge_request value = 0 }} }}
    if = {{ limit = {{ exists = var:eu5ab_bridge_type }} add_to_variable_map = {{ name = eu5ab_bridge_request_types key = var:eu5ab_bridge_request value = var:eu5ab_bridge_type }} }}
    switch = {{ trigger = var:eu5ab_bridge_kind {publish} }}
    if = {{ limit = {{ var:eu5ab_bridge_kind < 4 var:eu5ab_bridge_location = {{ num_civil_constructions > 0 }} }}
        set_variable = eu5ab_bridge_parallel_needed
        save_scope_as = eu5ab_engine_country
        var:eu5ab_bridge_location = {{ add_to_variable_list = {{ name = eu5ab_bridge_parallel_tickets target = scope:eu5ab_engine_country.var:eu5ab_bridge_request }} }}
    }}
}}
eu5ab_publish_bridge_confirmation = {{
    if = {{ limit = {{ has_variable = eu5ab_bridge_request }}
        if = {{ limit = {{ var:eu5ab_bridge_lane = 1 }} add_to_variable_list = {{ name = eu5ab_bridge_confirmation_1 target = var:eu5ab_bridge_request }} }}
        else = {{ add_to_variable_list = {{ name = eu5ab_bridge_confirmation_2 target = var:eu5ab_bridge_request }} }}
    }}
}}
eu5ab_dispatch_queue_bridge = {{
    if = {{ limit = {{ has_variable = eu5ab_bridge_schema {ACTIVE} NOT = {{ has_variable = eu5ab_bridge_request }} }}
        save_scope_as = actor save_scope_as = eu5ab_engine_country
        eu5ab_ensure_build_pending = yes
        remove_variable = eu5ab_winner_waiting
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_q_fire }} eu5ab_q_waiting_data_value > 0 }} eu5ab_retry_waiting_candidate_data = yes }}
        while = {{ count = {phase_count + 2} limit = {{ {ACTIVE} NOT = {{ has_variable = eu5ab_bridge_request }} NOT = {{ has_variable = eu5ab_quote_waiting }} NOT = {{ has_variable = eu5ab_winner_waiting }} }}
            if = {{ limit = {{ OR = {{
                any_in_list = {{ variable = eu5ab_bridge_unread_locations NOT = {{ owner = scope:eu5ab_engine_country }} }}
                any_in_list = {{ variable = eu5ab_bridge_unread_rgos NOT = {{ owner = scope:eu5ab_engine_country }} }}
            }} }} set_variable = eu5ab_bridge_rebuild }}
            if = {{ limit = {{ has_variable = eu5ab_bridge_rebuild }}
                if = {{ limit = {{ var:eu5ab_global_candidate_ranking_mode = 1
                    NOT = {{ has_variable = eu5ab_q_rank_refreshed }} var:eu5ab_q_processed = 0 var:eu5ab_q_approved = 0 }}
                    eu5ab_refresh_planning_queue = yes set_variable = eu5ab_q_rank_refreshed }}
                eu5ab_rebuild_queue_bridge = yes
            }}
            if = {{ limit = {{ has_variable = eu5ab_q_fire }}
                ordered_in_list = {{ variable = eu5ab_q_approved_locations order_by = 1 max = 1 check_range_bounds = no
                    limit = {{ owner = scope:eu5ab_engine_country any_in_list = {{ variable = eu5ab_q_approved_types
                        NOT = {{ prev = {{ is_target_in_variable_list = {{ name = eu5ab_q_confirmed_types target = prev }} }} }} }} }}
                    save_scope_as = eu5ab_candidate_location
                    ordered_in_list = {{ variable = eu5ab_q_approved_types order_by = 1 max = 1 check_range_bounds = no
                        limit = {{ NOT = {{ scope:eu5ab_candidate_location = {{ is_target_in_variable_list = {{ name = eu5ab_q_confirmed_types target = prev }} }} }} }}
                        save_scope_as = eu5ab_candidate_building
                        scope:eu5ab_engine_country = {{ set_variable = {{ name = eu5ab_bridge_location value = scope:eu5ab_candidate_location }}
                            set_variable = {{ name = eu5ab_bridge_type value = scope:eu5ab_candidate_building }}
                            set_variable = {{ name = eu5ab_bridge_kind value = 4 }} eu5ab_publish_queue_bridge = yes }}
                        scope:eu5ab_candidate_location = {{ if = {{ limit = {{ has_variable = eu5ab_q_fire_issued }} owner = {{ eu5ab_publish_bridge_confirmation = yes }} }} }}
                    }}
                }}
                if = {{ limit = {{ NOT = {{ has_variable = eu5ab_bridge_request }} }} eu5ab_check_engine_confirmation_completion = yes }}
            }}
            else = {{
                ordered_in_list = {{ variable = eu5ab_bridge_unread_rgos order_by = 1 max = 1 check_range_bounds = no
                    limit = {{ owner = scope:eu5ab_engine_country }} save_scope_as = eu5ab_candidate_location
                    scope:eu5ab_engine_country = {{ set_variable = {{ name = eu5ab_bridge_location value = scope:eu5ab_candidate_location }}
                        set_variable = {{ name = eu5ab_bridge_kind value = 3 }} eu5ab_publish_queue_bridge = yes }} }}
                if = {{ limit = {{ NOT = {{ has_variable = eu5ab_bridge_request }} }}
                    if = {{ limit = {{ var:eu5ab_global_candidate_ranking_mode = 2 NOT = {{ has_variable = eu5ab_q_profit_selecting }} }}
                        eu5ab_rank_cached_queue = yes
                    }}
                    else_if = {{ limit = {{ has_variable = eu5ab_q_profit_selecting }}
                        eu5ab_publish_winner_batch = yes eu5ab_process_winner_batch = yes
                    }}
                    else = {{
                    ordered_in_list = {{ variable = eu5ab_bridge_unread_locations order_by = 1 max = 1 check_range_bounds = no
                        limit = {{ owner = scope:eu5ab_engine_country }} save_scope_as = eu5ab_candidate_location
                        ordered_in_list = {{ variable = eu5ab_bridge_unread_types order_by = 1 max = 1 check_range_bounds = no
                            save_scope_as = eu5ab_candidate_building
                            scope:eu5ab_engine_country = {{ set_variable = {{ name = eu5ab_bridge_location value = scope:eu5ab_candidate_location }}
                                set_variable = {{ name = eu5ab_bridge_type value = scope:eu5ab_candidate_building }}
                                set_variable = {{ name = eu5ab_bridge_kind value = 1 }}
                                if = {{ limit = {{ has_variable = eu5ab_q_profit_selecting }} set_variable = {{ name = eu5ab_bridge_kind value = 2 }} }}
                                eu5ab_publish_queue_bridge = yes }}
                        }}
                    }}
                    }}
                }}
                if = {{ limit = {{ NOT = {{ has_variable = eu5ab_bridge_request }} }} eu5ab_check_engine_phase_completion = yes }}
            }}
        }}
    }}
}}
eu5ab_retire_bridge_candidate = {{
    save_scope_as = eu5ab_candidate_location
    remove_list_variable = {{ name = eu5ab_bridge_unread_types target = scope:eu5ab_candidate_building }}
    if = {{ limit = {{ NOT = {{ has_variable_list = eu5ab_bridge_unread_types }} }}
        scope:eu5ab_engine_country = {{ remove_list_variable = {{ name = eu5ab_bridge_unread_locations target = scope:eu5ab_candidate_location }} }} }}
    scope:eu5ab_engine_country = {{ eu5ab_clear_queue_bridge = yes }}
}}
eu5ab_recover_queue_bridge = {{
    if = {{ limit = {{ has_variable = eu5ab_bridge_schema {ACTIVE} }}
        save_scope_as = actor save_scope_as = eu5ab_engine_country
        if = {{ limit = {{ has_variable = eu5ab_bridge_request eu5ab_pl_today >= {{ value = var:eu5ab_bridge_request_day add = 2 }} }}
            if = {{ limit = {{ var:eu5ab_bridge_kind = 4 }}
                var:eu5ab_bridge_type = {{ save_scope_as = eu5ab_candidate_building }}
                var:eu5ab_bridge_location = {{ save_scope_as = eu5ab_candidate_location
                    if = {{ limit = {{ owner = scope:eu5ab_engine_country has_variable = eu5ab_q_fire_issued }} eu5ab_confirm_requested_engine_candidate = yes }} }}
            }}
            eu5ab_clear_queue_bridge = yes set_variable = eu5ab_bridge_rebuild
        }}
        eu5ab_dispatch_queue_bridge = yes
    }}
}}
'''


def apply_effects(text, replace, phase_count, rgo_phase_count):
    def prepend(name, code):
        nonlocal text
        text = text.replace(name + ' = {', name + ' = {\n    ' + code, 1)
    def append(name, code):
        nonlocal text
        block = _block(text, name)
        text = replace(text, name, block[:-1] + '\n    ' + code + '\n}')
    prepend('eu5ab_start_engine_candidate_queue', 'set_variable = eu5ab_bridge_schema')
    for name in ('eu5ab_clear_engine_candidate_queue', 'eu5ab_reset_engine_priority_phase_progress', 'eu5ab_prepare_actual_profit_selection'):
        prepend(name, 'eu5ab_clear_queue_bridge = yes set_variable = eu5ab_bridge_rebuild')
    prepend('eu5ab_clear_engine_candidate_queue', 'clear_variable_list = eu5ab_bridge_unread_locations clear_variable_list = eu5ab_bridge_unread_rgos')
    prepend('eu5ab_prepare_engine_priority_phase', 'set_variable = eu5ab_bridge_rebuild')
    append('eu5ab_start_engine_candidate_queue', 'eu5ab_dispatch_queue_bridge = yes')
    append('eu5ab_check_engine_candidate_queue_watchdog', 'eu5ab_recover_queue_bridge = yes')
    prepend('eu5ab_resume_saved_queue', 'set_variable = eu5ab_bridge_schema eu5ab_clear_queue_bridge = yes')
    append('eu5ab_resume_saved_queue', 'eu5ab_dispatch_queue_bridge = yes')
    prepend('eu5ab_clear_location_candidate_state', 'clear_variable_list = eu5ab_bridge_unread_types clear_variable_list = eu5ab_bridge_parallel_tickets remove_variable = eu5ab_q_fire_quote_ready')
    prepend('eu5ab_approve_engine_candidate', 'remove_variable = eu5ab_q_fire_quote_ready')
    prepend('eu5ab_recover_runtime_after_load', 'eu5ab_clear_queue_bridge = yes set_variable = eu5ab_bridge_rebuild')
    prepend('eu5ab_finish_engine_candidate_queue', 'eu5ab_clear_queue_bridge = yes\n    if = { limit = { has_variable_list = eu5ab_q_approved_locations } eu5ab_settle_saved_approvals = yes }')
    # Resetting the old phase must not scrub the new owner's queue data.
    for name in ('eu5ab_reset_engine_priority_phase_progress', 'eu5ab_clear_engine_priority_phase'):
        block = _block(text, name)
        block = block.replace(name + ' = {', name + ' = {\n    save_scope_as = eu5ab_engine_country', 1)
        block = re.sub(r'(variable = eu5ab_q_phase_\d+_(?:rgo_)?locations)(?! limit)',
                       r'\1 limit = { owner = scope:eu5ab_engine_country }', block)
        text = replace(text, name, block)
    for name in ('eu5ab_reserve_engine_candidate', 'eu5ab_release_engine_candidate_reservation', 'eu5ab_commit_engine_candidate_budget'):
        block = _block(text, name).replace('scope:eu5ab_candidate_location.var:eu5ab_q_approved_cost',
                                         'scope:eu5ab_candidate_location.eu5ab_q_approved_cost_value')
        text = replace(text, name, block)
    return text + render_effects(phase_count, rgo_phase_count)


def wrap_candidate_guis(text, replace):
    for kind, name in ((1, 'try_candidate'), (2, 'try_profit_candidate')):
        name = 'eu5ab_gui_queue_' + name
        source = _block(text, name)
        source = source.replace('saved_scopes = {', f'saved_scopes = {{ {TICKET}', 1)
        start = source.index('effect = {') + len('effect = {')
        body = source[start:source.rfind('}')].rstrip()
        body = body[:body.rfind('}')]
        wrapped = source[:start] + f'''\n        if = {{ limit = {{ OR = {{
            scope:eu5ab_engine_country = {{ NOT = {{ has_variable = eu5ab_bridge_schema }} }}
            AND = {{ {LOCATION} scope:eu5ab_engine_country = {{ var:eu5ab_bridge_kind = {kind}
                OR = {{ NOT = {{ has_variable = eu5ab_bridge_parallel_needed }} has_variable = eu5ab_bridge_parallel_received }} }} }}
        }} }}
            if = {{ limit = {{ scope:eu5ab_engine_country = {{ has_variable = eu5ab_bridge_schema }} }} eu5ab_retire_bridge_candidate = yes }}
{body}
            scope:eu5ab_engine_country = {{ eu5ab_dispatch_queue_bridge = yes }}
        }}
    }}
}}'''
        text = replace(text, name, wrapped)
    return text


def render_guis():
    return f'''eu5ab_gui_bridge_rgo = {{
    saved_scopes = {{ eu5ab_engine_country {TICKET} eu5ab_engine_rgo_count }} is_valid = {{ always = yes }}
    effect = {{ if = {{ limit = {{ {LOCATION} scope:eu5ab_engine_country = {{ var:eu5ab_bridge_kind = 3
        OR = {{ NOT = {{ has_variable = eu5ab_bridge_parallel_needed }} has_variable = eu5ab_bridge_parallel_received }} }} }}
        save_scope_as = eu5ab_bridge_finished_location
        eu5ab_capture_rgo_queue = yes
        eu5ab_prepare_rgo_pending_start = yes
        scope:eu5ab_engine_country = {{ eu5ab_clear_queue_bridge = yes eu5ab_process_script_rgo_queue = yes
            remove_list_variable = {{ name = eu5ab_bridge_unread_rgos target = scope:eu5ab_bridge_finished_location }}
            eu5ab_check_engine_phase_completion = yes eu5ab_dispatch_queue_bridge = yes }}
    }} }}
}}
eu5ab_gui_bridge_confirmation = {{
    saved_scopes = {{ eu5ab_engine_country eu5ab_candidate_building {TICKET} }} is_valid = {{ always = yes }}
    effect = {{ if = {{ limit = {{ {LOCATION} has_variable = eu5ab_q_fire_issued scope:eu5ab_engine_country = {{ var:eu5ab_bridge_kind = 4 }} }}
        eu5ab_confirm_requested_engine_candidate = yes
        scope:eu5ab_engine_country = {{ eu5ab_clear_queue_bridge = yes eu5ab_dispatch_queue_bridge = yes }}
    }} }}
}}
'''


def render_widget(engine_arguments):
    from . import building_capacity, construction_slots, quote_cache, winner_batch, rgo_queue
    ticket = ticket_argument()
    lookup = "GetPlayer.MakeScope.GetVariableFromVariableMap('{map}', MakeScopeValue(Scope.GetValue))"
    stage = ".AddScope('eu5ab_engine_queue_check_stage', MakeScopeValue(" + lookup.format(map='eu5ab_bridge_request_stages') + '.GetValue))'
    widgets = []
    for kind in (*KINDS, 'confirmation'):
        for lane in (1, 2):
            prefix = f'eu5ab_bridge_{kind}_{lane}'
            base = "GuiScope.SetRoot(Location.MakeScope).AddScope('eu5ab_engine_country', GetPlayer.MakeScope)" + ticket
            if kind == 'rgo':
                callback = "GetScriptedGui('eu5ab_gui_bridge_rgo').Execute(" + base + rgo_queue.gui_arguments() + '.End)'
            elif kind == 'confirmation':
                callback = "GetScriptedGui('eu5ab_gui_bridge_confirmation').Execute(" + base + ".AddScope('eu5ab_candidate_building', BuildingType.MakeScope).End)"
            elif kind == 'fire':
                callback = "GetScriptedGui('eu5ab_gui_queue_request_fire').Execute(" + base + ".AddScope('eu5ab_candidate_building', BuildingType.MakeScope).AddScope('eu5ab_engine_cost', MakeScopeValue(GetBuildOrExpandBuildingCost(BuildingType.Self, Location.Self))).AddScope('eu5ab_engine_replaced_building', BuildingType.GetObsoleteBuildingInLocation(Location.Self, GetPlayer.Self).MakeScope).End)"
            else:
                name = 'try_profit_candidate' if kind == 'profit' else 'try_candidate'
                callback = f"GetScriptedGui('eu5ab_gui_queue_{name}').Execute({engine_arguments}{ticket}{stage}.End)"
            parallel = kind in ('candidate', 'profit', 'rgo')
            type_context = 'widget = {' if kind == 'rgo' else 'widget = { datacontext = "[' + lookup.format(map='eu5ab_bridge_request_types') + '.GetBuildingType]"'
            widgets.append(f'''widget = {{
    datamodel = "[GetPlayer.MakeScope.GetList('{prefix}')]"
    item = {{ widget = {{ datacontext = "[{lookup.format(map='eu5ab_bridge_request_locations')}.GetLocation]"
        visible_at_creation = no visible = "[GetPlayer.Exists]"
        state = {{ name = _hide alpha = 0 }}
        state = {{ name = _show alpha = 1 duration = {'0.15' if kind == 'confirmation' else '0.01'} next = {prefix}_setup }}
        state = {{ name = {prefix}_setup alpha = 0 duration = 0.01
            {'on_finish = "[PdxGuiTriggerAllAnimations(\'' + prefix + '_parallel_sample\')]"' if parallel else ''} next = {prefix}_read }}
        state = {{ name = {prefix}_read alpha = 1 duration = 0.01 on_finish = "[PdxGuiTriggerAllAnimations('{prefix}_read_sample')]" }}
        {construction_slots.capture_widget(prefix + '_parallel', bridge=True) if parallel else ''}
            {type_context}
            visible_at_creation = no visible = "[GetPlayer.Exists]"
            state = {{ name = _hide alpha = 0 }} state = {{ name = _show alpha = 1 }}
            state = {{ name = {prefix}_read_sample on_finish = "[{callback}]" }}
            {building_capacity.fire_widget(ticket=ticket) if kind == 'fire' else ''}
        }}
    }} }}
}}''')
    return '''# Finite, script-owned readers. No complete phase pool is expanded.
widget = {
    name = "eu5ab_engine_queue_window"
    visible = "[EqualTo_CFixedPoint('(CFixedPoint)0', '(CFixedPoint)0')]"
    position = { -10000 1 }
    widget = {
''' + building_capacity.render_capture_widget() + rgo_queue.render_widget() + quote_cache.render_widget(engine_arguments) + winner_batch.render_widget(engine_arguments) + '\n'.join(widgets) + '\n    }\n}\n'
