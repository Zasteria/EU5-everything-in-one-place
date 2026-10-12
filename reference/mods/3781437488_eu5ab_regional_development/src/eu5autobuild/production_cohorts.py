"""Persistent individual Mod starts and independently dated completions.

Building scopes cannot own variables. Country maps use monotonic numeric IDs;
the building geometry index is separate and never enrolls native queue deltas.
"""
from .script_syntax import lower_map_formulas

ID = 'scope:eu5ab_pf_id'
COUNTRY = 'scope:eu5ab_pf_country'
BUILDING = 'scope:eu5ab_pf_building'


def read(field):
    return f'"variable_map(eu5ab_pf_c_{field}|{ID})"'


def write(field, value):
    return f'add_to_variable_map = {{ name = eu5ab_pf_c_{field} key = {ID} value = {value} }}'


def each(body):
    return f'''every_in_list = {{ variable = eu5ab_pf_cohorts
        save_scope_value_as = {{ name = eu5ab_pf_id value = this }}
        {COUNTRY} = {{ {body} }}
    }}'''


def goods_push(prefix, key, index, good):
    """Sparse per-object linked list; numeric IDs/buildings cannot own lists."""
    from .production_goods import map_value
    return f'''if = {{ limit = {{ NOT = {{ is_key_in_variable_map = {{ name = {prefix}_next_{good} target = {key} }} }} }}
        add_to_variable_map = {{ name = {prefix}_next_{good} key = {key}
            value = {{ value = {map_value(prefix + '_head', key)} if = {{ limit = {{ NOT = {{ is_key_in_variable_map = {{ name = {prefix}_head target = {key} }} }} }} value = -1 }} }} }}
        add_to_variable_map = {{ name = {prefix}_head key = {key} value = {index} }}
    }}'''


def goods_walk(prefix, key, goods, bodies, *, rebuild=False):
    from .production_goods import map_value
    branches = '\n'.join(f'''{i} = {{
        set_local_variable = {{ name = eu5ab_pf_goods_cursor value = "variable_map({prefix}_next_{g}|{key})" }}
        {bodies[g]}
    }}''' for i, g in enumerate(goods, 1) if g in bodies)
    return f'''set_local_variable = {{ name = eu5ab_pf_goods_cursor value = {map_value(prefix + '_head', key)} }}
    {f'remove_from_variable_map = {{ name = {prefix}_head key = {key} }}' if rebuild else ''}
    while = {{ count = {len(goods)} limit = {{ local_var:eu5ab_pf_goods_cursor > 0 }}
        switch = {{ trigger = local_var:eu5ab_pf_goods_cursor {branches} }}
    }}'''


def recipe_goods(models, goods):
    """Dimensions with real writers; retain the global goods IDs in walks."""
    return {kind: {g for model in models.values() for slot in model.slots
                   for method in slot for g, amount in getattr(method, prop).items()
                   if amount > 0 and g in goods}
            for kind, prop in (('input', 'inputs'), ('output', 'outputs'))}


def render_recipe_cache(models, goods):
    """One native identity check and one method walk per building per refresh.

Only nominal quantities are shared. Cohorts retain their own efficiency,
predecessor credits and release deadlines. Clearing at each refresh observes
manual PM changes, including known-to-unknown transitions, without a hash.
"""
    dimensions = recipe_goods(models, goods)
    dimensions['next'] = dimensions['input'] | dimensions['output']
    maps = [f'eu5ab_pf_recipe_{kind}_{g}' for kind in ('input', 'output', 'next')
            for g in goods if g in dimensions[kind]]
    maps.append('eu5ab_pf_recipe_head')
    cases = []
    for building, model in sorted(models.items()):
        methods = {}
        for slot in model.slots:
            for method in slot:
                methods[method.production_method_id] = method
        branches = []
        for name, method in sorted(methods.items()):
            additions = []
            for good in sorted(set(method.inputs) | set(method.outputs)):
                if good in goods and max(method.inputs.get(good, 0), method.outputs.get(good, 0)) > 0:
                    additions.append(goods_push('eu5ab_pf_recipe', BUILDING, goods.index(good) + 1, good))
            for kind, quantities in (('input', method.inputs), ('output', method.outputs)):
                for good, quantity in sorted(quantities.items()):
                    if good in goods and quantity > 0:
                        mapping = f'eu5ab_pf_recipe_{kind}_{good}'
                        additions.append(f'''add_to_variable_map = {{ name = {mapping} key = {BUILDING} value = {{ value = {quantity:g}
                            if = {{ limit = {{ is_key_in_variable_map = {{ name = {mapping} target = {BUILDING} }} }}
                                add = "variable_map({mapping}|{BUILDING})" }} }} }}''')
            branches.append(f'production_method:{name} = {{ {" ".join(additions)} }}')
        cases.append(f'''building_type:{building} = {{
            {BUILDING} = {{ every_production_method_of_building = {{ save_scope_as = eu5ab_pf_recipe_method
                {COUNTRY} = {{ switch = {{ trigger = scope:eu5ab_pf_recipe_method {' '.join(branches)} }} }}
            }} }}
        }}''')
    return f'''eu5ab_pf_clear_recipe_cache = {{
        clear_variable_list = eu5ab_pf_recipe_captured clear_variable_list = eu5ab_pf_recipe_known
        {' '.join('clear_variable_map = ' + name for name in maps)}
    }}
    eu5ab_pf_capture_project_recipe = {{
        if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_pf_recipe_captured target = {BUILDING} }} }} }}
            add_to_variable_list = {{ name = eu5ab_pf_recipe_captured target = {BUILDING} }}
            if = {{ limit = {{ {BUILDING} = {{ eu5ab_pr_recipe_known = yes }} }}
                add_to_variable_list = {{ name = eu5ab_pf_recipe_known target = {BUILDING} }}
                switch = {{ trigger = {BUILDING}.building_type {' '.join(cases)} }}
            }}
        }}
    }}
    '''


def render_date_values():
    values = []
    for part, count in (('month', 12), ('day', 31)):
        values.append(f'eu5ab_pf_current_{part} = {{ value = 0 ' +
                      ' '.join(f'if = {{ limit = {{ current_{part} = {n} }} value = {n} }}'
                               for n in range(1, count + 1)) + ' }')
    values.append('''eu5ab_pf_completion_deadline = {
    value = current_year multiply = 372
    add = { value = eu5ab_pf_current_month add = local_var:eu5ab_pf_protection_months multiply = 31 }
    add = { value = eu5ab_pf_current_day max = local_var:eu5ab_pf_month_days }
}''')
    return '\n'.join(values)


def render_maintenance_effects():
    return '''# Keep geometry and expiry independent of monthly construction.
# The next-day marker coalesces duplicate saved/new events without tickets.
eu5ab_pf_ensure_maintenance = {
    if = { limit = { has_variable_list = eu5ab_pf_cohorts
        NOT = { has_variable = eu5ab_pf_maintenance_after } }
        set_variable = { name = eu5ab_pf_maintenance_after value = { value = eu5ab_pl_today add = 1 } }
        trigger_event_silently = { id = eu5ab_pf_maintenance.1 days = 1 }
    }
}
eu5ab_pf_resume_maintenance = {
    remove_variable = eu5ab_pf_maintenance_after
    eu5ab_pf_ensure_maintenance = yes
}
eu5ab_pf_maintain_registered_projects = {
    if = { limit = { has_variable = eu5ab_pf_maintenance_after
        var:eu5ab_pf_maintenance_after <= eu5ab_pl_today }
        remove_variable = eu5ab_pf_maintenance_after
        if = { limit = { has_variable_list = eu5ab_pf_cohorts }
            eu5ab_ensure_build_pending = yes
            eu5ab_pf_ensure_maintenance = yes
        }
    }
}
'''


def render_event():
    return '''namespace = eu5ab_pf_maintenance
eu5ab_pf_maintenance.1 = {
    type = country_event
    title = eu5ab_window_title
    outcome = neutral
    hidden = yes
    immediate = { eu5ab_pf_maintain_registered_projects = yes }
}
'''


def render(models, goods):
    # Geometry, owner and market checks use the live building.location. A saved
    # duplicate location is redundant; old saves may retain that inert map.
    fields = ['building', 'type', 'market', 'state', 'known', 'eff_known',
              'efficiency', 'horizon', 'deadline', 'jobs', 'baseline_jobs', 'baseline_levels', 'released',
              'predecessor', 'old_levels']
    base_fields = fields[:]
    fields += [f'{kind}_{good}' for kind in ('output', 'input', 'credit', 'input_credit') for good in goods]
    effects = [render_maintenance_effects(), render_recipe_cache(models, goods), '''eu5ab_pf_rebuild_goods_index = {
        clear_variable_map = eu5ab_pf_c_goods_ready clear_variable_map = eu5ab_pf_c_goods_head
        ''' + ' '.join(f'clear_variable_map = eu5ab_pf_c_goods_next_{g}' for g in goods) + '''
    }
    # Country scope. Approval references are copied before any
# subsequent market reading; only a confirmed Mod start creates this ID.
eu5ab_pf_register_cohort = {
    save_scope_as = eu5ab_pf_country
    set_variable = { name = eu5ab_pf_serial value = { value = 0
        if = { limit = { has_variable = eu5ab_pf_serial } add = var:eu5ab_pf_serial } add = 1 } }
    save_scope_value_as = { name = eu5ab_pf_id value = var:eu5ab_pf_serial }
    add_to_variable_list = { name = eu5ab_pf_cohorts target = scope:eu5ab_pf_id }
    set_local_variable = { name = eu5ab_pf_active_count value = 0 }
    if = { limit = { is_key_in_variable_map = { name = eu5ab_pf_active_records target = scope:eu5ab_pf_building } }
        set_local_variable = { name = eu5ab_pf_active_count value = "variable_map(eu5ab_pf_active_records|scope:eu5ab_pf_building)" }
    }
    change_local_variable = { name = eu5ab_pf_active_count add = 1 }
    add_to_variable_map = { name = eu5ab_pf_active_records key = scope:eu5ab_pf_building value = local_var:eu5ab_pf_active_count }
''']
    initial = {'building': BUILDING,
               'type': BUILDING + '.building_type', 'market': BUILDING + '.location.market',
               'horizon': BUILDING + '.location.owner.var:eu5ab_global_job_fill_deadline_months'}
    effects += [write(field, initial.get(field, '0')) for field in fields if field != 'predecessor']
    effects.append(f'''{BUILDING}.location = {{
        if = {{ limit = {{ has_variable = eu5ab_pf_approval_known }}
            {COUNTRY} = {{ {write('known', '1')} {write('eff_known', '1')}
                {write('efficiency', BUILDING + '.location.var:eu5ab_pf_approval_efficiency')} }}
        }}
        if = {{ limit = {{ exists = var:eu5ab_pending_predecessor }}
            var:eu5ab_pending_predecessor = {{ save_scope_as = eu5ab_pf_old_building }}
            {COUNTRY} = {{ {write('predecessor', 'scope:eu5ab_pf_old_building')}
                {write('old_levels', BUILDING + '.location.eu5ab_pending_predecessor_before_value')} }}
        }}
''')
    for good in goods:
        for field, approval in (('output', 'output'), ('input', 'net_input'), ('credit', 'old_output'), ('input_credit', 'old_input')):
            effects.append(f'''if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_pending_approval_{approval} target = goods:{good} }} }}
                {COUNTRY} = {{ {write(field + '_' + good, f'"{BUILDING}.location.variable_map(eu5ab_pending_approval_{approval}|goods:{good})"')} }}
            }}''')
    effects.append('} eu5ab_pf_ensure_goods = yes eu5ab_pf_ensure_maintenance = yes }')
    effects.append(f'''# One migration pass for saved cohorts; maintenance thereafter
# visits only recorded goods, including predecessor-only credits.
eu5ab_pf_ensure_goods = {{
    if = {{ limit = {{ NOT = {{ is_key_in_variable_map = {{ name = eu5ab_pf_c_goods_ready target = {ID} }} }} }}
        {write('goods_ready', '1')}
''')
    for i, good in enumerate(goods, 1):
        present = ' '.join(f'{read(kind + "_" + good)} > 0' for kind in ('input', 'output', 'credit', 'input_credit'))
        effects.append(f'if = {{ limit = {{ OR = {{ {present} }} }} {goods_push("eu5ab_pf_c_goods", ID, i, good)} }}')
    effects.append('} }')
    effects.append(f'''# Geometry observations allocate existing IDs only. Oldest
# Mod IDs complete first after all observed manual work ahead has completed.
eu5ab_pf_reconcile_cohorts = {{
    location.owner = {{
        save_scope_as = eu5ab_pf_country
        {each(f'''if = {{ limit = {{ {read('building')} = {BUILDING} {read('state')} = 0 local_var:eu5ab_pf_done > 0 }}
            eu5ab_pf_complete_cohort = yes
            change_local_variable = {{ name = eu5ab_pf_done subtract = 1 }}
        }}''')}
        {each(f'''if = {{ limit = {{ {read('building')} = {BUILDING} {read('state')} = 0 local_var:eu5ab_pf_cancelled > 0 }}
            eu5ab_pf_drop_cohort = yes
            change_local_variable = {{ name = eu5ab_pf_cancelled subtract = 1 }}
        }}''')}
        {each(f'''if = {{ limit = {{ {read('building')} = {BUILDING} {read('state')} = 1 local_var:eu5ab_pf_cancelled > 0 }}
            eu5ab_pf_drop_cohort = yes
            change_local_variable = {{ name = eu5ab_pf_cancelled subtract = 1 }}
        }}''')}
    }}
}}
eu5ab_pf_complete_cohort = {{
    {write('state', '1')}
    {write('jobs', BUILDING + '.eu5ab_pr_jobs_per_level')}
    {write('baseline_levels', '{ value = local_var:eu5ab_pf_levels subtract = local_var:eu5ab_pf_done min = 0 }')}
    {write('baseline_jobs', '{ value = local_var:eu5ab_pf_levels subtract = local_var:eu5ab_pf_done multiply = ' + BUILDING + '.eu5ab_pr_jobs_per_level min = 0 }')}
    if = {{ limit = {{ {read('horizon')} <= 0 }} eu5ab_pf_drop_cohort = yes }}
    else = {{
        set_local_variable = {{ name = eu5ab_pf_protection_months value = {read('horizon')} }}
        if = {{ limit = {{ {read('known')} = 0 }} set_local_variable = {{ name = eu5ab_pf_protection_months value = 3 }} }}
        set_local_variable = {{ name = eu5ab_pf_month_total value = {{ value = eu5ab_pf_current_month add = local_var:eu5ab_pf_protection_months subtract = 1 }} }}
        set_local_variable = {{ name = eu5ab_pf_year_offset value = {{ value = local_var:eu5ab_pf_month_total divide = 12 floor = yes }} }}
        set_local_variable = {{ name = eu5ab_pf_target_month value = {{ value = local_var:eu5ab_pf_month_total subtract = {{ value = local_var:eu5ab_pf_year_offset multiply = 12 }} add = 1 }} }}
        set_local_variable = {{ name = eu5ab_pf_month_days value = 31 }}
        if = {{ limit = {{ OR = {{ local_var:eu5ab_pf_target_month = 4 local_var:eu5ab_pf_target_month = 6 local_var:eu5ab_pf_target_month = 9 local_var:eu5ab_pf_target_month = 11 }} }}
            set_local_variable = {{ name = eu5ab_pf_month_days value = 30 }}
        }}
        else_if = {{ limit = {{ local_var:eu5ab_pf_target_month = 2 }}
            set_local_variable = {{ name = eu5ab_pf_month_days value = 28 }}
        }}
        {write('deadline', 'eu5ab_pf_completion_deadline')}
    }}
}}
eu5ab_pf_drop_cohort = {{
    eu5ab_pf_ensure_goods = yes
    # Native map-link arguments cannot contain another map link. Preserve the
    # stored building value even when its native object has disappeared.
    set_local_variable = {{ name = eu5ab_pf_drop_building value = {read('building')} }}
    set_local_variable = {{ name = eu5ab_pf_active_count value = {{ value = "variable_map(eu5ab_pf_active_records|local_var:eu5ab_pf_drop_building)" subtract = 1 min = 0 }} }}
    add_to_variable_map = {{ name = eu5ab_pf_active_records key = local_var:eu5ab_pf_drop_building value = local_var:eu5ab_pf_active_count }}
    if = {{ limit = {{ local_var:eu5ab_pf_active_count <= 0 }}
        remove_list_variable = {{ name = eu5ab_pf_projects target = local_var:eu5ab_pf_drop_building }}
        remove_from_variable_map = {{ name = eu5ab_pf_active_records key = local_var:eu5ab_pf_drop_building }}
    }}
    remove_list_variable = {{ name = eu5ab_pf_cohorts target = {ID} }}
''' + goods_walk('eu5ab_pf_c_goods', ID, goods, {
        g: '\n'.join(f'remove_from_variable_map = {{ name = eu5ab_pf_c_{kind}_{g} key = {ID} }}' for kind in ('output', 'input', 'credit', 'input_credit', 'goods_next'))
        for g in goods}) + '\n' + '\n'.join(f'remove_from_variable_map = {{ name = eu5ab_pf_c_{f} key = {ID} }}'
        for f in (*base_fields, 'goods_head', 'goods_ready')) + '\n}')
    effects.append(f'''# Country scope, ID selected. Expiry happens before a reread.
# Reading or loading a completed cohort cannot change its deadline.
eu5ab_pf_refresh_cohort = {{
    if = {{ limit = {{ exists = {read('building')} }}
        {read('building')} = {{ save_scope_as = eu5ab_pf_building }}
        if = {{ limit = {{ {BUILDING} = {{ location.owner = {COUNTRY} owner = {COUNTRY} NOT = {{ exists = estate_type }} }} }}
            if = {{ limit = {{ {read('state')} = 1 {read('deadline')} <= eu5ab_pl_today }} eu5ab_pf_drop_cohort = yes }}
            else = {{
                {write('market', BUILDING + '.location.market')}
                eu5ab_pf_read_project_recipe = yes
                set_local_variable = {{ name = eu5ab_pf_fraction value = 1 }}
                if = {{ limit = {{ {read('state')} = 1 }}
                    if = {{ limit = {{ {read('jobs')} <= 0 {BUILDING}.eu5ab_pr_jobs_per_level > 0 }}
                        {write('jobs', BUILDING + '.eu5ab_pr_jobs_per_level')}
                        {write('baseline_jobs', '{ value = ' + read('baseline_levels') + ' multiply = ' + read('jobs') + ' }')}
                    }}
                    # Incumbent jobs are excluded. Additional manual levels do
                    # not increase this cohort's jobs or its reference output.
                    if = {{ limit = {{ {read('jobs')} > 0 }}
                        set_local_variable = {{ name = eu5ab_pf_fraction value = {{
                            value = {BUILDING}.building_employed_amount subtract = {read('baseline_jobs')}
                            divide = {read('jobs')} min = 0 max = 1
                            multiply = -1 add = 1 }} }}
                    }}
                    else_if = {{ limit = {{ {BUILDING} = {{ building_employment_size_amount > 0 is_full_capacity = yes }} }}
                        set_local_variable = {{ name = eu5ab_pf_fraction value = 0 }}
                    }}
                    if = {{ limit = {{ local_var:eu5ab_pf_fraction <= 0 }} {write('released', '1')} }}
                    if = {{ limit = {{ {read('released')} = 1 }} set_local_variable = {{ name = eu5ab_pf_fraction value = 0 }} }}
                    eu5ab_pf_add_cooldown = yes
                }}
                if = {{ limit = {{ {read('known')} = 1 exists = {BUILDING}.location.market }} eu5ab_pf_add_reservation = yes }}
            }}
        }}
        else = {{ eu5ab_pf_drop_cohort = yes }}
    }}
    else = {{ eu5ab_pf_drop_cohort = yes }}
}}
eu5ab_pf_read_project_recipe = {{
    eu5ab_pf_ensure_goods = yes
    # An uncompleted first build with no native PM yet retains its justified
    # donor snapshot. An observable unknown recipe removes obsolete goods.
    eu5ab_pf_capture_project_recipe = yes
    if = {{ limit = {{ OR = {{ {BUILDING}.building_level > 0 is_target_in_variable_list = {{ name = eu5ab_pf_recipe_known target = {BUILDING} }} }} }}
        {write('known', '0')}
        if = {{ limit = {{ {read('eff_known')} = 0 {read('state')} = 1 is_target_in_variable_list = {{ name = eu5ab_pf_recipe_known target = {BUILDING} }}
            {BUILDING} = {{ eu5ab_pr_efficiency_known = yes }} }}
            {write('efficiency', BUILDING + '.eu5ab_pr_efficiency')} {write('eff_known', '1')}
        }}
        if = {{ limit = {{ {read('eff_known')} = 1 is_target_in_variable_list = {{ name = eu5ab_pf_recipe_known target = {BUILDING} }} }} {write('known', '1')} }}
''')
    old_goods = {}
    for i, good in enumerate(goods, 1):
        old_goods[good] = write('output_' + good, '0') + write('input_' + good, '0') + f'''
            remove_from_variable_map = {{ name = eu5ab_pf_c_goods_next_{good} key = {ID} }}
            if = {{ limit = {{ OR = {{ {read('credit_' + good)} > 0 {read('input_credit_' + good)} > 0 }} }}
                {goods_push('eu5ab_pf_c_goods', ID, i, good)} }}'''
    effects.append(goods_walk('eu5ab_pf_c_goods', ID, goods, old_goods, rebuild=True))
    new_goods = {}
    dimensions = recipe_goods(models, goods)
    for i, good in enumerate(goods, 1):
        if good not in dimensions['input'] | dimensions['output']:
            continue
        lines = [goods_push('eu5ab_pf_c_goods', ID, i, good)]
        for kind in ('output', 'input'):
            if good not in dimensions[kind]:
                continue
            credit = read(('credit_' if kind == 'output' else 'input_credit_') + good)
            mapping = f'eu5ab_pf_recipe_{kind}_{good}'
            lines.append(f'''if = {{ limit = {{ {read('known')} = 1 is_key_in_variable_map = {{ name = {mapping} target = {BUILDING} }} }}
                {write(f'{kind}_{good}', '{ value = "variable_map(' + mapping + '|' + BUILDING + ')" multiply = ' + read('efficiency') + ' subtract = ' + credit + ' min = 0 }')}
            }}''')
        new_goods[good] = '\n'.join(lines)
    effects.append(goods_walk('eu5ab_pf_recipe', BUILDING, goods, new_goods))
    effects.append('} }')
    effects.append('eu5ab_pf_add_cooldown = { switch = { trigger = ' + read('type'))
    for building in sorted(models):
        mapping = f'eu5ab_pf_cooldown_{building}'
        effects.append(f'''building_type:{building} = {{
            set_local_variable = {{ name = eu5ab_pf_until value = {read('deadline')} }}
            if = {{ limit = {{ is_key_in_variable_map = {{ name = {mapping} target = {BUILDING}.location }} }}
                change_local_variable = {{ name = eu5ab_pf_until max = "variable_map({mapping}|{BUILDING}.location)" }}
            }}
            add_to_variable_map = {{ name = {mapping} key = {BUILDING}.location value = local_var:eu5ab_pf_until }}
        }}''')
    effects.append('} }')
    effects.append('eu5ab_pf_add_reservation = {')
    reservations = {}
    for good in goods:
        lines = []
        for kind, mapping in (('output', 'eu5ab_build_pending'), ('input', 'eu5ab_build_future_input')):
            lines.append(f'''set_local_variable = {{ name = eu5ab_pending_quantity value = {{ value = {read(kind + '_' + good)} multiply = local_var:eu5ab_pf_fraction }} }}''')
            if kind in ('output', 'input'):
                credit = read(('credit_' if kind == 'output' else 'input_credit_') + good)
                lines.append(f'''# Compensate the loss of the already credited predecessor
                # exactly once while constructing. Current S can fall independently.
                if = {{ limit = {{ {read('state')} = 0 {credit} > 0 }}
                    set_local_variable = {{ name = eu5ab_pf_old_loss value = 1 }}
                    if = {{ limit = {{ exists = {read('predecessor')} }}
                        {read('predecessor')} = {{ save_scope_as = eu5ab_pf_old_building }}
                        set_local_variable = {{ name = eu5ab_pf_old_loss value = {{
                            value = {read('old_levels')} subtract = scope:eu5ab_pf_old_building.building_level min = 0 max = 1 }} }}
                    }}
                    change_local_variable = {{ name = eu5ab_pending_quantity add = {{ value = {credit} multiply = local_var:eu5ab_pf_old_loss }} }}
                }}''')
            lines.append(f'''if = {{ limit = {{ local_var:eu5ab_pending_quantity > 0 }}
                {read('market')} = {{ save_scope_as = eu5ab_pending_market }}
                eu5ab_pf_add_market = {{ MAP = {mapping}_{good} }}
            }}''')
        reservations[good] = '\n'.join(lines)
    effects.append(goods_walk('eu5ab_pf_c_goods', ID, goods, reservations))
    effects.append('}')
    return lower_map_formulas('\n'.join(effects))
