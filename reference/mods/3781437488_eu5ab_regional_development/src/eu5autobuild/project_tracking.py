"""Count confirmed projects, including repeated levels of the same building.

Old saves have one baseline per type and implicitly one project. Read those as
one until refreshed; new confirmations increment a count without overwriting
the original baseline. Queue observations bound the remaining count. Since the
native API does not identify the Mod's individual queue items, mixed manual/Mod
work of the same type is attributed conservatively until that queue drains.
"""


def render(rules, models=()) -> tuple[str, str, str]:
    from . import queue_bridge
    values = '''eu5ab_candidate_queued_levels = {
    value = 0
    every_buildings_in_location = {
        limit = { building_type = scope:eu5ab_candidate_building owner = scope:eu5ab_candidate_location.owner NOT = { exists = estate_type } }
        add = building_levels_under_construction
    }
}
eu5ab_type_queue_before_value = { value = 0 if = { limit = { has_variable = eu5ab_q_type_queue_before } add = var:eu5ab_q_type_queue_before } }
eu5ab_type_level_before_value = { value = 0 if = { limit = { has_variable = eu5ab_q_type_level_before } add = var:eu5ab_q_type_level_before } }
eu5ab_active_type_count = {
    value = 0
    if = {
        limit = { has_variable_map = eu5ab_active_building_counts is_key_in_variable_map = { name = eu5ab_active_building_counts target = scope:eu5ab_candidate_building } }
        value = "variable_map(eu5ab_active_building_counts|scope:eu5ab_candidate_building)"
    }
    else_if = {
        limit = { is_target_in_variable_list = { name = eu5ab_active_building_types target = scope:eu5ab_candidate_building } }
        value = 1
    }
}
'''
    triggers = '''eu5ab_approved_building_started = {
    has_variable = eu5ab_q_fire_issued
    OR = {
        eu5ab_candidate_queued_levels > eu5ab_type_queue_before_value
        "location_building_level(scope:eu5ab_candidate_building)" > eu5ab_type_level_before_value
    }
}
'''
    effects = '''eu5ab_record_requested_engine_fire = {
    if = { limit = {
        owner = scope:eu5ab_engine_country
        owner = { has_variable = eu5ab_q_active has_variable = eu5ab_q_fire eu5ab_queue_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load } }
        has_variable = eu5ab_q_fire_requested
        NOT = { has_variable = eu5ab_q_fire_issued }
        is_target_in_variable_list = { name = eu5ab_q_approved_types target = scope:eu5ab_candidate_building }
        NOT = { is_target_in_variable_list = { name = eu5ab_q_confirmed_types target = scope:eu5ab_candidate_building } }
    }
        set_variable = eu5ab_q_fire_issued
        if = { limit = { owner = { has_variable = eu5ab_bridge_schema } }
            owner = { eu5ab_publish_bridge_confirmation = yes }
        }
    }
}
eu5ab_record_confirmed_building = {
    set_variable = { name = eu5ab_active_count_next value = { value = eu5ab_active_type_count add = 1 } }
    if = {
        limit = { NOT = { is_target_in_variable_list = { name = eu5ab_active_building_types target = scope:eu5ab_candidate_building } } }
        add_to_variable_list = { name = eu5ab_active_building_types target = scope:eu5ab_candidate_building }
        add_to_variable_map = { name = eu5ab_active_building_baselines key = scope:eu5ab_candidate_building value = eu5ab_type_level_before_value }
    }
    add_to_variable_map = { name = eu5ab_active_building_counts key = scope:eu5ab_candidate_building value = var:eu5ab_active_count_next }
    remove_variable = eu5ab_active_count_next
}
eu5ab_record_queue_start_location = {
    save_scope_as = eu5ab_started_location
    owner = {
        if = {
            limit = { NOT = { is_target_in_variable_list = { name = eu5ab_q_started_locations target = scope:eu5ab_started_location } } }
            add_to_variable_list = { name = eu5ab_q_started_locations target = scope:eu5ab_started_location }
        }
    }
}
eu5ab_apply_queue_cooldowns = {
    save_scope_as = eu5ab_cooldown_country
    every_in_list = {
        variable = eu5ab_q_started_locations
        limit = { owner = scope:eu5ab_cooldown_country }
        set_variable = { name = eu5ab_build_cooldown value = ''' + str(rules.cadence.location_cooldown_months) + ''' }
    }
    clear_variable_list = eu5ab_q_started_locations
}
# Called serially during the country project-count refresh.
eu5ab_refresh_active_building_type = {
    set_variable = { name = eu5ab_active_count_next value = eu5ab_active_type_count }
    if = {
        limit = { has_variable_map = eu5ab_active_building_baselines is_key_in_variable_map = { name = eu5ab_active_building_baselines target = scope:eu5ab_candidate_building } }
        if = {
            limit = { "location_building_level(scope:eu5ab_candidate_building)" >= { value = "variable_map(eu5ab_active_building_baselines|scope:eu5ab_candidate_building)" } }
            set_variable = { name = eu5ab_active_count_next value = {
                value = var:eu5ab_active_count_next
                min = 0
                max = eu5ab_candidate_queued_levels
            } }
        }
        else = { remove_variable = eu5ab_active_count_next }
    }
    else = { remove_variable = eu5ab_active_count_next }
    if = {
        limit = { has_variable = eu5ab_active_count_next var:eu5ab_active_count_next > 0 }
        add_to_variable_map = { name = eu5ab_active_building_counts key = scope:eu5ab_candidate_building value = var:eu5ab_active_count_next }
        add_to_variable_map = { name = eu5ab_active_building_baselines key = scope:eu5ab_candidate_building value = "location_building_level(scope:eu5ab_candidate_building)" }
        owner = { change_variable = { name = eu5ab_diag_active_mod_projects add = scope:eu5ab_candidate_location.var:eu5ab_active_count_next } }
    }
    else = {
        remove_list_variable = { name = eu5ab_active_building_types target = scope:eu5ab_candidate_building }
        remove_from_variable_map = { name = eu5ab_active_building_counts key = scope:eu5ab_candidate_building }
        remove_from_variable_map = { name = eu5ab_active_building_baselines key = scope:eu5ab_candidate_building }
    }
    remove_variable = eu5ab_active_count_next
}
'''
    # Keep literal building-type arguments, as used by all other generated
    # location queries; dynamic arguments are not assumed to be engine-safe.
    level = 'eu5ab_candidate_completed_levels'
    dynamic = '"location_building_level(scope:eu5ab_candidate_building)"'
    effects, triggers = effects.replace(dynamic, level), triggers.replace(dynamic, level)
    effects = effects.replace('        has_variable = eu5ab_q_fire_requested',
        '        ' + queue_bridge.COMPATIBLE + '\n        has_variable = eu5ab_q_fire_requested', 1)
    cases = ' '.join(f'if = {{ limit = {{ scope:eu5ab_candidate_building = building_type:{key} }} value = "scope:eu5ab_candidate_location.location_building_level(building_type:{key})" }}' for key in sorted(models))
    values += f'{level} = {{ value = 0 {cases} }}\n'
    return effects, triggers, values


def render_guis() -> str:
    return '''eu5ab_gui_queue_record_fire = {
    saved_scopes = { eu5ab_bridge_ticket eu5ab_engine_country eu5ab_candidate_building }
    is_valid = { always = yes }
    effect = {
        eu5ab_record_requested_engine_fire = yes
    }
}
'''
