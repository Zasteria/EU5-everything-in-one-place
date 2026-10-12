"""Commodity allowance from current market data and confirmed Mod cohorts."""
from . import building_capacity, production_projects, production_reference, production_cohorts
from . import production_quote_snapshot
from .production_goods import goods_in, map_value
from .rgo_pending import DEMAND_BUFFER_RATIO
from .script_syntax import lower_map_formulas, parse, render as script, specialize

LOCATION = 'scope:eu5ab_candidate_location'


def clear_candidate_reference():
    maps = ('pending_approval_output', 'pending_approval_net_input',
            'pending_approval_old_output', 'pending_approval_old_input',
            'pf_start_levels', 'pf_start_queue')
    variables = ('pf_approval_known', 'pf_approval_efficiency', 'pf_reference_building',
                 'pf_start_type', 'pf_start_owner',
                 'pending_predecessor', 'pending_predecessor_before')
    return ' '.join(['eu5ab_clear_quote_production_snapshot = yes',
                     *(f'clear_variable_map = eu5ab_{name}' for name in maps),
                     *(f'remove_variable = eu5ab_{name}' for name in variables)])


def render(models, rules, upgrades=None):
    from . import queue_dependencies
    from .market_supply import render_route_trigger
    from .rgo_automation import raw_goods
    goods = goods_in(models, rules)
    raw = set(raw_goods())
    project_effects, project_triggers, project_values = production_projects.render()
    _, reference_values = production_reference.render(models, goods)
    quote_effects, quote_triggers = production_quote_snapshot.render(models)
    effects = [project_effects, quote_effects, production_cohorts.render(models, goods),
               production_reference.render_candidate_effects(models),
               queue_dependencies.render_effects()]
    triggers = [project_triggers, quote_triggers, render_route_trigger()]
    values = [project_values, reference_values, render_day_value(), production_cohorts.render_date_values(), queue_dependencies.render_values(),
              'eu5ab_pending_predecessor_before_value = { value = 0 if = { limit = { has_variable = eu5ab_pending_predecessor_before } add = var:eu5ab_pending_predecessor_before } }']
    producers = [b for b, m in models.items() if any(p.outputs for s in m.slots for p in s)]
    triggers.append('eu5ab_candidate_has_direct_output = { OR = { ' +
                    ' '.join(f'this = building_type:{b}' for b in sorted(producers)) + ' } }')
    triggers.append(f'''eu5ab_pending_identity_known_live = {{
        {LOCATION} = {{ exists = var:eu5ab_pf_reference_building
            var:eu5ab_pf_reference_building = {{ building_type = scope:eu5ab_candidate_building
                owner = {LOCATION}.owner NOT = {{ exists = estate_type }}
                eu5ab_pr_recipe_known = yes eu5ab_pr_efficiency_known = yes }} }}
    }}''')
    for good in goods:
        key = f'goods:{good}'
        for kind, prop in (('output', 'outputs'), ('input', 'inputs')):
            cases = []
            for building, model in sorted(models.items()):
                terms = []
                for slot_index, slot in enumerate(model.slots):
                    for method_index, method in enumerate(slot, 1):
                        quantity = getattr(method, prop).get(good, 0)
                        if quantity > 0:
                            terms.append(f'if = {{ limit = {{ eu5ab_recipe_{building}_{slot_index}_selected = {method_index} }} add = {quantity:g} }}')
                if terms:
                    cases.append(f'if = {{ limit = {{ this = building_type:{building} }} {" ".join(terms)} }}')
            values.append(f'''eu5ab_proposed_{kind}_{good} = {{ value = 0 {" ".join(cases)} }}
eu5ab_candidate_{kind}_unit_{good} = {{
    value = 0
    if = {{ limit = {{ eu5ab_pending_identity_known = yes }}
        {production_quote_snapshot.quantity_value(kind, good)}
    }}
}}
eu5ab_candidate_old_{kind}_{good} = {{
    value = 0
    if = {{ limit = {{ eu5ab_pending_exact_predecessor = yes }}
        {production_quote_snapshot.quantity_value(kind, good, predecessor=True)}
    }}
}}
eu5ab_candidate_net_{kind}_{good} = {{
    value = 0
    if = {{ limit = {{ eu5ab_quote_production_current = yes
        {LOCATION} = {{ has_variable = {production_quote_snapshot.PREFIX}{kind}_ready }} }}
        value = {production_quote_snapshot.cached_quantity('net', kind, good, scoped=True)}
    }}
    else = {{ value = eu5ab_candidate_{kind}_unit_{good}
        subtract = eu5ab_candidate_old_{kind}_{good} min = 0 }}
}}
''')
        values.append(f'''eu5ab_market_future_input_{good} = {{
    value = 0
    {LOCATION}.owner = {{
        if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_build_future_input_{good} target = {LOCATION}.market }} }} add = "variable_map(eu5ab_build_future_input_{good}|{LOCATION}.market)" }}
    }}
}}
eu5ab_market_effective_demand_{good} = {{
    value = "{LOCATION}.market.goods_demand_in_market({key})"
    add = eu5ab_market_future_input_{good}
}}
eu5ab_market_pending_{good} = {{
    value = 0
    {LOCATION}.owner = {{
        if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_build_pending_{good} target = {LOCATION}.market }} }} add = "variable_map(eu5ab_build_pending_{good}|{LOCATION}.market)" }}
''')
        if good in raw:
            values.append(f'''        if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_rgo_pending_output_{good} target = {LOCATION}.market }} }} add = "variable_map(eu5ab_rgo_pending_output_{good}|{LOCATION}.market)" }}''')
        values.append(f'''    }}
    if = {{ limit = {{ {LOCATION} = {{
        exists = var:eu5ab_pending_approval_market market = var:eu5ab_pending_approval_market
        is_target_in_variable_list = {{ name = eu5ab_q_approved_types target = scope:eu5ab_candidate_building }}
        is_key_in_variable_map = {{ name = eu5ab_pending_approval_output target = {key} }}
    }} }} subtract = "{LOCATION}.variable_map(eu5ab_pending_approval_output|{key})" }}
    min = 0
}}
eu5ab_market_pending_limit_{good} = {{
    value = eu5ab_market_effective_demand_{good}
    subtract = "{LOCATION}.market.goods_supply_in_market({key})"
    min = 0
    add = {{ value = eu5ab_market_effective_demand_{good} multiply = {DEMAND_BUFFER_RATIO:g} }}
}}
eu5ab_market_uncovered_{good} = {{ value = eu5ab_market_pending_limit_{good} subtract = eu5ab_market_pending_{good} min = 0 }}
eu5ab_market_pending_factor_{good} = {{
    value = 0
    if = {{ limit = {{ eu5ab_market_pending_known_{good} = yes }}
        if = {{ limit = {{ eu5ab_market_pending_{good} <= 0 }} value = 1 }}
        else_if = {{ limit = {{ eu5ab_market_pending_limit_{good} > 0 eu5ab_market_pending_{good} < eu5ab_market_pending_limit_{good} }}
            value = 1
            subtract = {{ value = eu5ab_market_pending_{good} divide = eu5ab_market_pending_limit_{good}
                multiply = {{ value = eu5ab_market_pending_{good} divide = eu5ab_market_pending_limit_{good} }} }}
            min = 0.00001
        }}
    }}
}}
''')
        checks = [f'''{LOCATION} = {{ exists = market owner = {{ has_variable = eu5ab_build_pending_ready }} }}''',
                  f'''"{LOCATION}.market.goods_demand_in_market({key})" >= 0''',
                  f'''"{LOCATION}.market.goods_supply_in_market({key})" >= 0''']
        for prefix in (['eu5ab_rgo_pending_unknown'] if good in raw else []):
            checks.append(f'''{LOCATION}.owner = {{ OR = {{ NOT = {{ is_key_in_variable_map = {{ name = {prefix}_{good} target = {LOCATION}.market }} }} "variable_map({prefix}_{good}|{LOCATION}.market)" <= 0 }} }}''')
        triggers += [f'eu5ab_market_pending_known_{good} = {{ {" ".join(checks)} }}',
                     f'eu5ab_market_needs_{good} = {{ eu5ab_market_pending_known_{good} = yes eu5ab_market_effective_demand_{good} > 0 eu5ab_market_uncovered_{good} > 0 }}']

    predecessor_cases = []
    if upgrades:
        for target, sources in sorted(upgrades.predecessors.items()):
            if sources:
                predecessor_cases.append(f'building_type:{target} = {{ scope:eu5ab_engine_replaced_building = {{ OR = {{ ' +
                                         ' '.join(f'building_type = building_type:{b}' for b in sources) + ' } } }')
    triggers.append('''eu5ab_pending_exact_predecessor_live = {
    # A captured absence cannot reuse a replacement from an earlier callback.
    scope:eu5ab_candidate_location = { NOT = { has_variable = eu5ab_quote_no_replacement } }
    exists = scope:eu5ab_engine_replaced_building
    scope:eu5ab_engine_replaced_building = {
        building_level > 0 location = scope:eu5ab_candidate_location
        eu5ab_upgrade_source_available = yes
        owner = scope:eu5ab_candidate_location.owner
        building_can_be_upgraded_by = scope:eu5ab_candidate_location.owner
        eu5ab_pr_recipe_known = yes eu5ab_pr_efficiency_known = yes
    }
    switch = { trigger = this fallback = { always = no }
''' + '\n'.join(predecessor_cases) + '\n    }\n}')
    cooldown_cases = []
    for building in sorted(models):
        mapping = f'eu5ab_pf_cooldown_{building}'
        cooldown_cases.append(f'''building_type:{building} = {{
            {LOCATION}.owner = {{ OR = {{
                NOT = {{ is_key_in_variable_map = {{ name = {mapping} target = {LOCATION} }} }}
                "variable_map({mapping}|{LOCATION})" <= eu5ab_pl_today
            }} }}
        }}''')
    triggers.append('eu5ab_candidate_production_cooldown_clear = { switch = { trigger = this fallback = { always = yes } ' + ' '.join(cooldown_cases) + ' } }')
    # A target type can only have positive net output for its own possible
    # goods: subtracting a predecessor's nonnegative output cannot add a good.
    # Avoid revalidating the donor recipe for every other type's goods.
    output_goods = {
        b: sorted({g for slot in model.slots for method in slot for g in method.outputs})
        for b, model in sorted(models.items())
    }

    def output_checks(name, expression):
        cases = ' '.join(
            f'building_type:{b} = {{ ' +
            ' '.join(expression.format(good=g) for g in type_goods) + ' }'
            for b, type_goods in output_goods.items() if type_goods
        )
        # Unsupported or nonproducing types have zero modeled net output.
        return f'{name} = {{ switch = {{ trigger = this fallback = {{ always = yes }} {cases} }} }}'
    # Unknown projects contribute no invented goods. They may start under the
    # ordinary construction gates and receive a bounded post-completion reread.
    triggers += [output_checks(
                     'eu5ab_candidate_pending_data_ready',
                     'OR = {{ eu5ab_candidate_net_output_{good} <= 0 eu5ab_market_pending_known_{good} = yes }}'),
                 output_checks(
                     'eu5ab_candidate_output_limits_allow',
                     'OR = {{ eu5ab_candidate_net_output_{good} <= 0 eu5ab_market_pending_factor_{good} > 0 }}'),
                 f'''eu5ab_candidate_pending_allowed = {{
    eu5ab_candidate_production_cooldown_clear = yes
    eu5ab_candidate_pending_data_ready = yes
    OR = {{
        NOT = {{ eu5ab_candidate_has_direct_output = yes }}
        NOT = {{ eu5ab_pending_identity_known = yes }}
        AND = {{ {LOCATION} = {{ exists = market }} OR = {{
            AND = {{ {LOCATION} = {{ eu5ab_food_emergency_enabled = yes }} eu5ab_candidate_produces_food = yes }}
            eu5ab_candidate_output_limits_allow = yes
        }} }}
    }}
}}''',
                 'eu5ab_candidate_pending_preliminary_allowed = { eu5ab_candidate_pending_allowed = yes }']
    for name, factor in (('weight', ''), ('weighted', ' multiply = eu5ab_market_pending_factor_{good}')):
        branches = []
        for b, type_goods in output_goods.items():
            if not type_goods:
                continue
            terms = [f'if = {{ limit = {{ eu5ab_candidate_net_output_{g} > 0 }} add = {{ value = eu5ab_candidate_net_output_{g} multiply = "default_price(goods:{g})"{factor.format(good=g)} }} }}' for g in type_goods]
            branches.append(f'{"if" if not branches else "else_if"} = {{ limit = {{ this = building_type:{b} }} {" ".join(terms)} }}')
        # Script values use if/else_if, rather than the trigger-only switch.
        values.append(f'eu5ab_pending_{name} = {{ value = 0 {" ".join(branches)} }}')
    values.append(f'''eu5ab_candidate_pending_factor = {{
    value = 0
    if = {{ limit = {{ eu5ab_candidate_pending_allowed = yes }}
        value = 1
        if = {{ limit = {{ eu5ab_pending_weight > 0 NOT = {{ AND = {{ {LOCATION} = {{ eu5ab_food_emergency_enabled = yes }} eu5ab_candidate_produces_food = yes }} }} }}
            value = eu5ab_pending_weighted divide = eu5ab_pending_weight min = 0.00001 max = 1
        }}
    }}
}}
eu5ab_candidate_pending_preliminary_factor = {{ value = eu5ab_candidate_pending_factor }}
''')
    for name, score, factor in (
        ('eu5ab_pending_adjusted_candidate_score', 'eu5ab_price_adjusted_candidate_score', 'eu5ab_candidate_pending_preliminary_factor'),
        ('eu5ab_pending_profit_rank', 'eu5ab_profit_candidate_rank_value', 'scope:eu5ab_candidate_building.eu5ab_candidate_pending_factor'),
    ):
        values.append(f'{name} = {{\n' + '\n'.join(building_capacity.signed_value_lines(score, factor)) + '\n}')
    effects.extend((render_refresh(models, goods), render_reservations(goods),
                    '''eu5ab_pf_confirm_start = {
    if = { limit = { scope:eu5ab_candidate_building = { eu5ab_candidate_has_direct_output = yes } }
        eu5ab_pf_register_start = yes
        owner = { set_variable = eu5ab_build_pending_dirty }
    }
}'''))
    effects_text = script(specialize(parse('\n'.join(effects)), {'eu5ab_pf_add_market'}))
    return (lower_map_formulas(effects_text),
            script(parse('\n'.join(triggers))) + '\n',
            script(parse('\n'.join(values))) + '\n')


def render_day_value():
    # Calendar ordering stamp. Completion deadlines clamp their target day
    # separately, so short months cannot extend protection into another month.
    terms = ['value = current_year', 'multiply = 372']
    for part, count, scale in (('month', 12, 31), ('day', 31, 1)):
        terms.extend(f'if = {{ limit = {{ current_{part} = {n} }} add = {n * scale} }}'
                     for n in range(1, count + 1))
    return 'eu5ab_pl_today = { ' + ' '.join(terms) + ' }\n'


def render_refresh(models, goods):
    lines = ['''eu5ab_ensure_build_pending = {
    if = { limit = { OR = {
        NOT = { has_variable = eu5ab_build_pending_ready }
        has_variable = eu5ab_build_pending_dirty
        NOT = { var:eu5ab_pf_aggregate_day = eu5ab_pl_today }
    } } eu5ab_refresh_build_pending = yes }
}
eu5ab_refresh_build_pending = {
    save_scope_as = eu5ab_pending_country
    save_scope_as = eu5ab_pf_country
    eu5ab_pf_clear_recipe_cache = yes
    if = { limit = { exists = scope:eu5ab_candidate_location } scope:eu5ab_candidate_location = { save_scope_as = eu5ab_pf_saved_candidate_location } }
    if = { limit = { exists = scope:eu5ab_candidate_building } scope:eu5ab_candidate_building = { save_scope_as = eu5ab_pf_saved_candidate_type } }
    remove_variable = eu5ab_build_pending_dirty
    remove_variable = eu5ab_build_pending_ready
    set_variable = { name = eu5ab_pf_aggregate_day value = eu5ab_pl_today }
''']
    for good in goods:
        lines.extend(f'clear_variable_map = {prefix}_{good}' for prefix in
                     ('eu5ab_build_pending', 'eu5ab_build_future_input'))
    lines.extend(f'clear_variable_map = eu5ab_pf_cooldown_{b}' for b in sorted(models))
    lines.append('eu5ab_pf_refresh_projects = yes')
    lines.append(production_cohorts.each('eu5ab_pf_refresh_cohort = yes'))
    lines.append('''every_in_list = { variable = eu5ab_q_approved_locations
        limit = { owner = scope:eu5ab_pf_country exists = market
            exists = var:eu5ab_pending_approval_market market = var:eu5ab_pending_approval_market }
        market = { save_scope_as = eu5ab_pending_market }
        every_in_list = { variable = eu5ab_q_approved_types
            save_scope_as = eu5ab_candidate_building
            prev = { save_scope_as = eu5ab_candidate_location
                if = { limit = { NOT = { eu5ab_approved_building_started = yes } }
''')
    for good in goods:
        lines.append(f'''if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_pending_approval_output target = goods:{good} }} }}
            set_local_variable = {{ name = eu5ab_pending_quantity value = "variable_map(eu5ab_pending_approval_output|goods:{good})" }}
            eu5ab_pf_add_market = {{ MAP = eu5ab_build_pending_{good} }}
        }}''')
    lines.append('''} } } }
    set_variable = eu5ab_build_pending_ready
    if = { limit = { exists = scope:eu5ab_pf_saved_candidate_location } scope:eu5ab_pf_saved_candidate_location = { save_scope_as = eu5ab_candidate_location } }
    if = { limit = { exists = scope:eu5ab_pf_saved_candidate_type } scope:eu5ab_pf_saved_candidate_type = { save_scope_as = eu5ab_candidate_building } }
}
eu5ab_pf_add_market = {
    scope:eu5ab_pending_country = {
        if = { limit = { is_key_in_variable_map = { name = $MAP$ target = scope:eu5ab_pending_market } }
            change_local_variable = { name = eu5ab_pending_quantity add = "variable_map($MAP$|scope:eu5ab_pending_market)" }
        }
        add_to_variable_map = { name = $MAP$ key = scope:eu5ab_pending_market value = local_var:eu5ab_pending_quantity }
    }
}''')
    return '\n'.join(lines)


def render_reservations(goods):
    lines = []
    for action in ('reserve', 'release'):
        lines.append(f'eu5ab_{action}_candidate_output = {{')
        if action == 'reserve':
            lines += ['    clear_variable_map = eu5ab_pending_approval_output',
                      '    clear_variable_map = eu5ab_pending_approval_net_input',
                      '    clear_variable_map = eu5ab_pending_approval_old_output',
                      '    clear_variable_map = eu5ab_pending_approval_old_input',
                      '    remove_variable = eu5ab_pf_approval_known',
                      '    remove_variable = eu5ab_pf_approval_efficiency',
                      '    if = { limit = { exists = market }',
                      '        set_variable = { name = eu5ab_pending_approval_market value = market }',
                      '        set_variable = { name = eu5ab_pending_approval_country value = owner }']
        else:
            lines.append('    if = { limit = { exists = var:eu5ab_pending_approval_market exists = var:eu5ab_pending_approval_country }')
        lines.append('        var:eu5ab_pending_approval_market = { save_scope_as = eu5ab_pending_market }')
        if action == 'reserve':
            lines.append(f'''        if = {{ limit = {{ scope:eu5ab_candidate_building = {{ eu5ab_pending_identity_known = yes }} }}
                set_variable = eu5ab_pf_approval_known
                set_variable = {{ name = eu5ab_pf_approval_efficiency value = var:eu5ab_pf_reference_building.eu5ab_pr_efficiency }}
            }}''')
            for good in goods:
                for kind in ('output', 'input'):
                    lines.append(f"""        if = {{ limit = {{ scope:eu5ab_candidate_building.eu5ab_candidate_old_{kind}_{good} > 0 }}
            add_to_variable_map = {{ name = eu5ab_pending_approval_old_{kind} key = goods:{good} value = scope:eu5ab_candidate_building.eu5ab_candidate_old_{kind}_{good} }}
        }}""")
                lines.append(f'''        if = {{ limit = {{ scope:eu5ab_candidate_building.eu5ab_candidate_net_input_{good} > 0 }}
                    add_to_variable_map = {{ name = eu5ab_pending_approval_net_input key = goods:{good} value = scope:eu5ab_candidate_building.eu5ab_candidate_net_input_{good} }}
                }}''')
        for good in goods:
            mapping = f'eu5ab_build_pending_{good}'
            if action == 'reserve':
                lines.append(f'''        if = {{ limit = {{ scope:eu5ab_candidate_building.eu5ab_candidate_net_output_{good} > 0 }}
            add_to_variable_map = {{ name = eu5ab_pending_approval_output key = goods:{good} value = scope:eu5ab_candidate_building.eu5ab_candidate_net_output_{good} }}''')
            else:
                lines.append(f'        if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_pending_approval_output target = goods:{good} }} }}')
            lines.append(f'''            set_local_variable = {{ name = eu5ab_pending_delta value = "variable_map(eu5ab_pending_approval_output|goods:{good})" }}
            var:eu5ab_pending_approval_country = {{
                set_local_variable = {{ name = eu5ab_pending_total value = {map_value(mapping, 'scope:eu5ab_pending_market')} }}
                set_local_variable = {{ name = eu5ab_pending_total value = {{ value = local_var:eu5ab_pending_total {'add' if action == 'reserve' else 'subtract'} = local_var:eu5ab_pending_delta min = 0 }} }}
                add_to_variable_map = {{ name = {mapping} key = scope:eu5ab_pending_market value = local_var:eu5ab_pending_total }}
            }}
        }}''')
        lines += ['    }', '}']
    return '\n'.join(lines)



def render_guis():
    return ''
