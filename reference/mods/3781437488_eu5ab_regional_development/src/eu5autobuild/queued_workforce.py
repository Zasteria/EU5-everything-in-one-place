"""Reserve the future workers of native construction, including manual work."""


def scan_pop_types(workforce):
    return sorted({pop for row in workforce.buildings.values() for pop in row.pop_types})


def scan_cache_clear_lines(workforce):
    return [f'\tremove_variable = eu5ab_scan_queued_jobs_{pop}{suffix}'
            for pop in scan_pop_types(workforce) for suffix in ('', '_ready')]


def scan_reservation(pop_types):
    # EU5 min is a lower bound: preserve max(0, reservations...), not a sum.
    # The caller is already in the selected building's location scope.
    terms = ' '.join(f'min = eu5ab_scan_queued_jobs_{pop}' for pop in pop_types)
    return '{ value = 0 ' + terms + ' }'


def render_scan_cache_effects(workforce):
    # Same lifetime as promotion: one synchronous location evaluation. These
    # effects never change the native construction queue or population data.
    return '\n'.join(f'''eu5ab_prepare_scan_queued_jobs_{pop} = {{
    if = {{ limit = {{ has_variable = eu5ab_scan_promotion_active
        NOT = {{ has_variable = eu5ab_scan_queued_jobs_{pop}_ready }} }}
        set_variable = {{ name = eu5ab_scan_queued_jobs_{pop} value = eu5ab_queued_jobs_{pop} }}
        set_variable = eu5ab_scan_queued_jobs_{pop}_ready
    }}
}}''' for pop in scan_pop_types(workforce))


def render(workforce, upgrades=None):
    from .upgrade_queue import job_credit_cases
    pops = sorted({pop for row in workforce.all_buildings.values() for pop in row.pop_types})
    values = []
    for pop in pops:
        types = [key for key, row in sorted(workforce.all_buildings.items()) if pop in row.pop_types]
        conditions = ' '.join(f'building_type = building_type:{key}' for key in types)
        values.append(f'''eu5ab_queued_jobs_{pop} = {{
    value = 0
    every_buildings_in_location = {{
        limit = {{ building_levels_under_construction > 0 OR = {{ {conditions} }} }}
        # Native employment_size is already in thousands, like the population values.
        add = {{ value = building_levels_under_construction multiply = building_type.employment_size }}
    }}
''')
        deductions = job_credit_cases(workforce, upgrades, pop) if upgrades else []
        if deductions:
            values.append('''    # Upgrading predecessors keep their old jobs until completion.
    # Credit only proven reservations in compatible occupation chains.
    every_buildings_in_location = {
        limit = { eu5ab_upgrade_source_sampled = yes }
''' + '\n'.join(deductions) + '''
    }
    min = 0
''')
        if pop in ('laborers', 'slaves'):
            guard = ('owner = { modifier:allow_rgo_slave_demand = yes }' if pop == 'slaves' else 'always = yes')
            values.append(f'''    if = {{ limit = {{ {guard} }} add = eu5ab_rgo_queued_jobs }}''')
        values.append('}')
    # Keep eu5ab_queued_jobs_* and the public candidate lookup live. Only the
    # selected scan branch uses these readers, with explicit zero readiness.
    for pop in scan_pop_types(workforce):
        values.append(f'''eu5ab_scan_queued_jobs_{pop} = {{
    value = 0
    if = {{ limit = {{ has_variable = eu5ab_scan_promotion_active
        has_variable = eu5ab_scan_queued_jobs_{pop}_ready }}
        if = {{ limit = {{ has_variable = eu5ab_scan_queued_jobs_{pop} }}
            add = var:eu5ab_scan_queued_jobs_{pop} }}
    }}
    else = {{ add = eu5ab_queued_jobs_{pop} }}
}}''')
    values += ['eu5ab_candidate_queued_jobs = {', '    value = 0']
    for index, (key, row) in enumerate(sorted(workforce.buildings.items())):
        # Most building types have one occupation. Shared eligible populations
        # must not be reused by a second project, so use the largest reservation.
        terms = ' '.join(f'min = scope:eu5ab_candidate_location.eu5ab_queued_jobs_{pop}' for pop in row.pop_types)
        branch = 'if' if index == 0 else 'else_if'
        values.append(f'    {branch} = {{ limit = {{ this = building_type:{key} }} {terms} }}')
    values += ['}']
    return '\n'.join(values)
