"""Distinct predecessor facts shared only within one synchronous worker."""

from .worker_screening import (
    ACTIVE, BUILDING, LOCATION, bind_definition, mapping, missing,
    predicate_wrapper, store, value_wrapper,
)
from .script_syntax import lower_map_formulas

PREDICATES = {
    'replaces_existing': 'eu5ab_candidate_replaces_existing_building',
    'replaces_capacity': 'eu5ab_candidate_replaces_capacity_building',
}
FIELDS = (*PREDICATES, 'net_new_jobs', 'net_new_jobs_ready')
LOCATION_PASSED = 'eu5ab_worker_location_eligible'


def render_location_eligibility(building_ids, upgrades):
    cases = []
    for building in building_ids:
        legal = f'{LOCATION} = {{ can_build_building = building_type:{building} }}'
        passed = f'{LOCATION} = {{ set_variable = {LOCATION_PASSED} }}'
        replacement = ''
        if upgrades.predecessors.get(building):
            replacement = f'''else = {{
                eu5ab_prepare_worker_screen_upgrades = yes
                if = {{ limit = {{ eu5ab_candidate_replaces_existing_building = yes }} {passed} }}
            }}'''
        cases.append(f'''building_type:{building} = {{
            if = {{ limit = {{ {legal} }} {passed} }}
            {replacement}
        }}''')
    # Execute the same legal OR in an effect so only its fallback may prepare
    # shared facts. The native location permission is still queried once.
    return f'''eu5ab_prepare_worker_location_eligibility = {{
        {LOCATION} = {{ remove_variable = {LOCATION_PASSED} }}
        switch = {{ trigger = this
            {' '.join(cases)}
        }}
    }}
'''


def render_effects(upgrades, workforce):
    cases = []
    for destination, predecessors in sorted(upgrades.predecessors.items()):
        if not predecessors or destination not in workforce.buildings:
            continue
        model = workforce.buildings[destination]
        deductions = []
        for predecessor in predecessors:
            source = workforce.all_buildings.get(predecessor)
            if source is None or source.pop_types != model.pop_types:
                continue
            net = max(model.jobs_per_level - source.jobs_per_level, 0) / 1000
            # Zero can be omitted from a map; readiness is stored separately.
            value = f'''{{ value = 0
                if = {{ limit = {{ NOT = {{ {missing('net_new_jobs')} }} }}
                    add = "variable_map({mapping('net_new_jobs')}|{BUILDING})" }} max = {net:g} }}'''
            deductions.append(f'''if = {{ limit = {{ building_type = building_type:{predecessor} }}
                {LOCATION} = {{ {store('net_new_jobs', value)} }} }}''')
        cases.append(f'''building_type:{destination} = {{
            {LOCATION} = {{ if = {{ limit = {{ has_variable = {ACTIVE} {missing('net_new_jobs_ready')} }}
                {store('replaces_existing', 1)} {store('replaces_capacity', 1)}
                {store('net_new_jobs', f'{model.jobs_per_level / 1000:g}')}
                {store('net_new_jobs_ready', 1)}
                every_buildings_in_location = {{
                    limit = {{ OR = {{ {' '.join('building_type = building_type:' + p for p in predecessors)} }}
                        eu5ab_upgrade_source_available = yes
                        building_can_be_upgraded_by = {LOCATION}.owner }}
                    if = {{ limit = {{ building_level >= 1 }}
                        {LOCATION} = {{ {store('replaces_existing', 2)} }}
                        if = {{ limit = {{ building_type = {{ employment_size > 0 }} }}
                            {LOCATION} = {{ {store('replaces_capacity', 2)} }} }}
                    }}
                    # Only an unreserved native level can transfer matching jobs.
                    {' '.join(deductions)}
                }}
            }} }}
        }}''')
    return lower_map_formulas('''eu5ab_prepare_worker_screen_upgrades = {
        switch = { trigger = this
''' + '\n'.join(cases) + '\n        }\n}\n')


def apply(files, root, upgrades, workforce, building_ids):
    effects = root / 'in_game/common/scripted_effects/eu5ab_scripted_effects.txt'
    triggers = root / 'in_game/common/scripted_triggers/eu5ab_scripted_triggers.txt'
    values = root / 'in_game/common/script_values/eu5ab_script_values.txt'
    for kind, name in PREDICATES.items():
        files[triggers] = bind_definition(files[triggers], name, predicate_wrapper(name, kind))
    name = 'eu5ab_candidate_net_new_jobs'
    files[values] = bind_definition(files[values], name, value_wrapper(name, 'net_new_jobs'))
    clear = '\n'.join('    clear_variable_map = ' + mapping(kind) for kind in FIELDS)
    files[effects] = files[effects].replace('eu5ab_clear_worker_screening = {',
        'eu5ab_clear_worker_screening = {\n    remove_variable = ' + LOCATION_PASSED + '\n' + clear, 1)
    files[effects] += '\n' + render_effects(upgrades, workforce)
    files[effects] += '\n' + render_location_eligibility(building_ids, upgrades)
