"""Shared location slots, independent of ordinary quotes and candidate cleanup."""


def render():
    from .construction_batch import COUNTRY, ID, increment
    current = '''has_variable = eu5ab_batch_slots_ready
        exists = var:eu5ab_batch_slots_owner owner = var:eu5ab_batch_slots_owner
        has_variable = eu5ab_batch_slots_month has_variable = eu5ab_batch_slots_year
        var:eu5ab_batch_slots_month = owner.var:eu5ab_scan_month
        var:eu5ab_batch_slots_year = owner.var:eu5ab_scan_year'''
    return f'''
eu5ab_batch_slots_ensure = {{
    if = {{ limit = {{ NOT = {{ AND = {{ {current} }} }} }}
        clear_variable_list = eu5ab_batch_slot_holds
        set_variable = {{ name = eu5ab_batch_slots_held value = 0 }}
        set_variable = {{ name = eu5ab_batch_slots_owner value = owner }}
        set_variable = {{ name = eu5ab_batch_slots_month value = owner.var:eu5ab_scan_month }}
        set_variable = {{ name = eu5ab_batch_slots_year value = owner.var:eu5ab_scan_year }}
        eu5ab_batch_slots_reconcile = yes
        set_variable = eu5ab_batch_slots_ready
    }}
}}
# Only serial approval/recovery owns the country's touched-location index.
eu5ab_batch_slots_track = {{
    save_scope_as = eu5ab_slot_location
    {COUNTRY} = {{ if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_slot_locations target = scope:eu5ab_slot_location }} }} }}
        add_to_variable_list = {{ name = eu5ab_batch_slot_locations target = scope:eu5ab_slot_location }} }} }}
}}
# Recovery runs after unissued approvals have been withdrawn. It also accounts
# for native/manual queue changes since the saved monthly snapshot.
eu5ab_batch_slots_reconcile = {{
    set_variable = {{ name = eu5ab_batch_slots_occupied value = num_civil_constructions }}
    set_variable = {{ name = eu5ab_batch_slots value = {{ value = modifier:max_constructions_at_same_time floor = yes
        subtract = eu5ab_batch_slots_occupied_value subtract = eu5ab_batch_slots_held_value min = 0 }} }}
}}
eu5ab_batch_slots_reserve = {{
    eu5ab_batch_slots_ensure = yes
    eu5ab_batch_slots_track = yes
    if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_slot_holds target = {ID} }} }} }}
        add_to_variable_list = {{ name = eu5ab_batch_slot_holds target = {ID} }}
        set_variable = {{ name = eu5ab_batch_slots_held value = {{ value = eu5ab_batch_slots_held_value add = 1 }} }}
        set_variable = {{ name = eu5ab_batch_slots value = {{ value = eu5ab_batch_slots_value subtract = 1 min = 0 }} }}
    }}
}}
eu5ab_batch_slots_commit = {{
    if = {{ limit = {{ var:eu5ab_batch_slots_owner = {COUNTRY}
        is_target_in_variable_list = {{ name = eu5ab_batch_slot_holds target = {ID} }} }}
        remove_list_variable = {{ name = eu5ab_batch_slot_holds target = {ID} }}
        set_variable = {{ name = eu5ab_batch_slots_held value = {{ value = eu5ab_batch_slots_held_value subtract = 1 min = 0 }} }}
        {increment('eu5ab_batch_slots_occupied')}
    }}
}}
eu5ab_batch_slots_release = {{
    eu5ab_batch_slots_track = yes
    if = {{ limit = {{ var:eu5ab_batch_slots_owner = {COUNTRY}
        is_target_in_variable_list = {{ name = eu5ab_batch_slot_holds target = {ID} }} }}
        remove_list_variable = {{ name = eu5ab_batch_slot_holds target = {ID} }}
        set_variable = {{ name = eu5ab_batch_slots_held value = {{ value = eu5ab_batch_slots_held_value subtract = 1 min = 0 }} }}
        set_variable = {{ name = eu5ab_batch_slots value = {{ value = eu5ab_batch_slots_value add = 1 }} }}
    }}
}}
eu5ab_batch_slots_resume = {{
    save_scope_as = eu5ab_slot_country
    every_in_list = {{ variable = eu5ab_batch_slot_locations
        limit = {{ owner = scope:eu5ab_slot_country }}
        eu5ab_batch_slots_ensure = yes eu5ab_batch_slots_reconcile = yes
    }}
}}
'''


def values():
    return '''eu5ab_batch_slots_held_value = { value = 0
        if = { limit = { has_variable = eu5ab_batch_slots_held } add = var:eu5ab_batch_slots_held } }
eu5ab_batch_slots_occupied_value = { value = 0
        if = { limit = { has_variable = eu5ab_batch_slots_occupied } add = var:eu5ab_batch_slots_occupied } }
'''
