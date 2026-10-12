"""Exact-instance geometry for confirmed Mod starts, with no native enrollment.

Only indexed instances are revisited. Completed units live in individual
cohort records; geometry needs only queued Mod quantity and physical baselines.
"""
from .script_syntax import parse, render as script

FIELDS = ('queued', 'last_levels', 'last_queue')


def render():
    values = []
    for field in (*FIELDS, 'start_levels', 'start_queue'):
        values.append(f'''eu5ab_pf_{field}_value = {{
    value = 0
    location = {{ if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_pf_{field} target = prev }} }}
        add = "variable_map(eu5ab_pf_{field}|prev)"
    }} }}
}}''')
    triggers = '''eu5ab_pf_registered = {
    location = {
        is_key_in_variable_map = { name = eu5ab_pf_owner target = prev }
        "variable_map(eu5ab_pf_owner|prev)" = owner
    }
    location.owner = { is_key_in_variable_map = { name = eu5ab_pf_active_records target = prev } }
    owner = location.owner
    NOT = { exists = estate_type }
}'''
    effects = '''eu5ab_pf_observe_geometry = {
    set_local_variable = { name = eu5ab_pf_old_queue value = eu5ab_pf_queued_value }
    set_local_variable = { name = eu5ab_pf_done value = {
        value = local_var:eu5ab_pf_levels subtract = eu5ab_pf_last_levels_value
        subtract = { value = eu5ab_pf_last_queue_value subtract = local_var:eu5ab_pf_old_queue min = 0 }
        min = 0 max = local_var:eu5ab_pf_old_queue
    } }
    set_local_variable = { name = eu5ab_pf_cancelled value = {
        value = eu5ab_pf_last_levels_value add = eu5ab_pf_last_queue_value
        subtract = local_var:eu5ab_pf_levels subtract = local_var:eu5ab_pf_physical_queue min = 0
    } }
    set_local_variable = { name = eu5ab_pf_next_queue value = {
        value = local_var:eu5ab_pf_old_queue subtract = local_var:eu5ab_pf_done
        subtract = local_var:eu5ab_pf_cancelled min = 0 max = local_var:eu5ab_pf_physical_queue
    } }
    save_scope_as = eu5ab_pf_building
    eu5ab_pf_reconcile_cohorts = yes
    eu5ab_pf_store_geometry = yes
}
eu5ab_pf_observe = {
    if = { limit = { eu5ab_pf_registered = yes NOT = { AND = {
        building_level = eu5ab_pf_last_levels_value
        building_levels_under_construction = eu5ab_pf_last_queue_value
    } } }
        set_local_variable = { name = eu5ab_pf_levels value = building_level }
        set_local_variable = { name = eu5ab_pf_physical_queue value = building_levels_under_construction }
        eu5ab_pf_observe_geometry = yes
    }
}
# The fire path snapshots exact instances before issuing its native command.
eu5ab_pf_capture_start_geometry = {
    set_variable = { name = eu5ab_pf_start_type value = scope:eu5ab_candidate_building }
    set_variable = { name = eu5ab_pf_start_owner value = owner }
    clear_variable_map = eu5ab_pf_start_levels
    clear_variable_map = eu5ab_pf_start_queue
    every_buildings_in_location = {
        limit = { owner = scope:eu5ab_candidate_location.owner NOT = { exists = estate_type }
            building_type = { this = scope:eu5ab_candidate_building } }
        save_scope_as = eu5ab_pf_start_building
        set_local_variable = { name = eu5ab_pf_start_level_value value = building_level }
        set_local_variable = { name = eu5ab_pf_start_queue_value value = building_levels_under_construction }
        location = {
            add_to_variable_map = { name = eu5ab_pf_start_levels key = scope:eu5ab_pf_start_building value = local_var:eu5ab_pf_start_level_value }
            add_to_variable_map = { name = eu5ab_pf_start_queue key = scope:eu5ab_pf_start_building value = local_var:eu5ab_pf_start_queue_value }
        }
    }
}
# Only a changed instance, once per issued and confirmed command, can enroll.
eu5ab_pf_register_start = {
    if = { limit = { has_variable = eu5ab_pf_start_type
        var:eu5ab_pf_start_type = scope:eu5ab_candidate_building
        var:eu5ab_pf_start_owner = owner }
    save_scope_as = eu5ab_candidate_location
    set_local_variable = { name = eu5ab_pf_registered_this_attempt value = 0 }
    every_buildings_in_location = {
        limit = { owner = scope:eu5ab_candidate_location.owner NOT = { exists = estate_type }
            building_type = { this = scope:eu5ab_candidate_building }
            local_var:eu5ab_pf_registered_this_attempt = 0
            OR = { building_level > eu5ab_pf_start_levels_value
                building_levels_under_construction > eu5ab_pf_start_queue_value } }
        save_scope_as = eu5ab_pf_building
        set_local_variable = { name = eu5ab_pf_levels value = eu5ab_pf_start_levels_value }
        set_local_variable = { name = eu5ab_pf_physical_queue value = eu5ab_pf_start_queue_value }
        if = { limit = { eu5ab_pf_registered = yes }
            eu5ab_pf_observe_geometry = yes
            set_local_variable = { name = eu5ab_pf_next_queue value = { value = eu5ab_pf_queued_value add = 1 } }
        }
        else = {
            set_local_variable = { name = eu5ab_pf_next_queue value = 1 }
            location = { add_to_variable_map = { name = eu5ab_pf_owner key = scope:eu5ab_pf_building value = owner } }
        }
        location.owner = { eu5ab_pf_register_cohort = yes }
        change_local_variable = { name = eu5ab_pf_physical_queue add = 1 }
        eu5ab_pf_store_geometry = yes
        location.owner = {
            if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_pf_projects target = scope:eu5ab_pf_building } } }
                add_to_variable_list = { name = eu5ab_pf_projects target = scope:eu5ab_pf_building }
            }
        }
        eu5ab_pf_observe = yes
        set_local_variable = { name = eu5ab_pf_registered_this_attempt value = 1 }
    }
    remove_variable = eu5ab_pf_start_type
    remove_variable = eu5ab_pf_start_owner
    }
}
eu5ab_pf_refresh_projects = {
    save_scope_as = eu5ab_pf_country
    every_in_list = {
        variable = eu5ab_pf_projects
        save_scope_as = eu5ab_pf_building
        if = { limit = { exists = this location.owner = scope:eu5ab_pf_country eu5ab_pf_registered = yes }
            eu5ab_pf_observe = yes
        }
        else = { scope:eu5ab_pf_country = { remove_list_variable = { name = eu5ab_pf_projects target = scope:eu5ab_pf_building } } }
    }
}
'''
    stores = []
    for field, local in (('queued', 'next_queue'), ('last_levels', 'levels'), ('last_queue', 'physical_queue')):
        stores.append(f'add_to_variable_map = {{ name = eu5ab_pf_{field} key = scope:eu5ab_pf_building value = local_var:eu5ab_pf_{local} }}')
    effects += 'eu5ab_pf_store_geometry = { save_scope_as = eu5ab_pf_building location = {\n' + '\n'.join(stores) + '\n} }\n'
    return tuple(script(parse(text)) + '\n' for text in (effects, triggers, '\n'.join(values)))
