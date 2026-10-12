"""Re-rank the bounded planning pool after each native recipe/capacity capture."""
from . import building_capacity
from .queue_script_dispatch import CHECK_STAGE_GUARD


def render(phase_count: int, location_limit: int) -> str:
    lines = ['eu5ab_refresh_planning_queue = {',
             '    save_scope_as = eu5ab_q_rank_country',
             '    switch = { trigger = var:eu5ab_q_phase']
    for phase in range(1, phase_count + 1):
        locations = f'eu5ab_q_phase_{phase}_locations'
        types = f'eu5ab_q_phase_{phase}_types'
        order = f'eu5ab_capacity_phase_{phase}_order'
        lines += [f'''        {phase} = {{
            every_in_list = {{
                variable = {locations}
                save_scope_as = eu5ab_candidate_location
                remove_variable = {order}
                remove_variable = {order}_ready
                clear_variable_map = eu5ab_candidate_sort_scores
                every_in_list = {{
                    variable = {types}
                    save_scope_as = eu5ab_candidate_building
                    eu5ab_prepare_candidate_score_snapshot = yes
                    scope:eu5ab_candidate_location = {{
                        add_to_variable_map = {{ name = eu5ab_candidate_sort_scores key = prev value = prev.eu5ab_current_candidate_score }}
                        if = {{ limit = {{
                            NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_failed_types target = scope:eu5ab_candidate_building }} }}
                            scope:eu5ab_candidate_building = {{
                                eu5ab_candidate_route_allowed = yes
                                eu5ab_output_not_oversupplied = yes
                                eu5ab_candidate_pending_preliminary_allowed = yes
                                eu5ab_inputs_available = yes
                                eu5ab_has_local_workforce = yes
                            }}
                        }}
''', *building_capacity.phase_order_lines(phase, '                            '), '''                        }
                    }
                    scope:eu5ab_candidate_location = { eu5ab_clear_recipe_score_snapshot = yes }
                }
                clear_variable_list = eu5ab_q_rank_types
                ordered_in_list = {''', f'''                    variable = {types}
                    order_by = eu5ab_candidate_sort_score
                    max = 100
                    check_range_bounds = no
                    save_scope_as = eu5ab_candidate_building
                    scope:eu5ab_candidate_location = {{ add_to_variable_list = {{ name = eu5ab_q_rank_types target = scope:eu5ab_candidate_building }} }}
                }}
                clear_variable_list = {types}
                every_in_list = {{ variable = eu5ab_q_rank_types save_scope_as = eu5ab_candidate_building
                    scope:eu5ab_candidate_location = {{ add_to_variable_list = {{ name = {types} target = scope:eu5ab_candidate_building }} }}
                }}
                clear_variable_list = eu5ab_q_rank_types
                clear_variable_map = eu5ab_candidate_sort_scores
            }}
            clear_variable_list = eu5ab_q_rank_locations
            ordered_in_list = {{ variable = {locations} order_by = {order}_value max = {location_limit} check_range_bounds = no
                save_scope_as = eu5ab_q_rank_location
                scope:eu5ab_q_rank_country = {{ add_to_variable_list = {{ name = eu5ab_q_rank_locations target = scope:eu5ab_q_rank_location }} }}
            }}
            clear_variable_list = {locations}
            every_in_list = {{ variable = eu5ab_q_rank_locations save_scope_as = eu5ab_q_rank_location
                scope:eu5ab_q_rank_country = {{ add_to_variable_list = {{ name = {locations} target = scope:eu5ab_q_rank_location }} }}
            }}
            clear_variable_list = eu5ab_q_rank_locations
        }}''']
    return '\n'.join([*lines, '    }', '}']).replace('\t', '    ')


GUI = '''eu5ab_gui_refresh_planning_queue = {
    saved_scopes = { eu5ab_engine_queue_check_stage }
    is_valid = { always = yes }
    effect = {
        if = { limit = { has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load }
            OR = { AND = { scope:eu5ab_engine_queue_check_stage = -1 has_variable = eu5ab_q_fire } $STAGE_GUARD$ } }
        eu5ab_ensure_build_pending = yes
        if = {
            limit = { has_variable = eu5ab_q_active var:eu5ab_global_candidate_ranking_mode = 1
                NOT = { has_variable = eu5ab_q_rank_refreshed } var:eu5ab_q_processed = 0 var:eu5ab_q_approved = 0 }
            eu5ab_refresh_planning_queue = yes
            set_variable = eu5ab_q_rank_refreshed
        }
        if = { limit = { NOT = { has_variable = eu5ab_q_fire } $STAGE_GUARD$ }
            eu5ab_tick_engine_script_queue = yes
        }
        }
    }
}
'''.replace('$STAGE_GUARD$', 'AND = { ' + CHECK_STAGE_GUARD + ' }')
