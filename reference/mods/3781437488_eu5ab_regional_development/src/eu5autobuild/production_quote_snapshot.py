"""Reuse production validation only inside one synchronous quote callback.

The candidate location owns the scratch fields, never a building or type.
Preparation clears both successful and failed results; the caller clears again
on exit. The type marker is installed last and guards every cached read.
"""

LOCATION = 'scope:eu5ab_candidate_location'
TYPE = 'scope:eu5ab_candidate_building'
PREFIX = 'eu5ab_quote_production_'
FIELDS = ('type', 'reference_known', 'reference_efficiency',
          'predecessor_known', 'predecessor_efficiency', 'output_ready', 'input_ready',
          'adjusted_profit', 'adjusted_profit_ready')
SEARCH_FIELDS = ('active', 'search_type', 'search_reference')
MAPS = tuple(role + '_' + kind for role in ('reference', 'predecessor', 'net')
             for kind in ('output', 'input'))


def render(models):
    effects = f'''eu5ab_clear_quote_production_values = {{
        {' '.join('remove_variable = ' + PREFIX + field for field in FIELDS)}
        {' '.join('clear_variable_map = ' + PREFIX + name for name in MAPS)}
    }}
    eu5ab_clear_quote_production_snapshot = {{
        eu5ab_clear_quote_production_values = yes
        {' '.join('remove_variable = ' + PREFIX + field for field in SEARCH_FIELDS)}
    }}
    eu5ab_prepare_quote_production_snapshot = {{
        eu5ab_clear_quote_production_values = yes
        {TYPE} = {{
            if = {{ limit = {{ {LOCATION} = {{ has_variable = {PREFIX}active
                has_variable = {PREFIX}search_type var:{PREFIX}search_type = prev }} }}
                {LOCATION} = {{ if = {{ limit = {{ exists = var:eu5ab_pf_reference_building
                    exists = var:{PREFIX}search_reference
                    var:eu5ab_pf_reference_building = var:{PREFIX}search_reference }}
                    set_variable = {PREFIX}reference_known
                }} }}
            }}
            else_if = {{ limit = {{ eu5ab_pending_identity_known_live = yes }}
                {LOCATION} = {{ set_variable = {PREFIX}reference_known }}
            }}
            {LOCATION} = {{ if = {{ limit = {{ has_variable = {PREFIX}reference_known }}
                set_variable = {{ name = {PREFIX}reference_efficiency
                    value = var:eu5ab_pf_reference_building.eu5ab_pr_efficiency }}
            }} }}
            if = {{ limit = {{ eu5ab_pending_exact_predecessor_live = yes }}
                {LOCATION} = {{
                    set_variable = {PREFIX}predecessor_known
                    set_variable = {{ name = {PREFIX}predecessor_efficiency
                        value = scope:eu5ab_engine_replaced_building.eu5ab_pr_efficiency }}
                }}
            }}
        }}
        set_variable = {{ name = {PREFIX}type value = {TYPE} }}
    }}
    eu5ab_prepare_quote_economy_snapshot = {{
        set_variable = {{ name = {PREFIX}adjusted_profit value = eu5ab_engine_adjusted_profit_live }}
        set_variable = {PREFIX}adjusted_profit_ready
    }}'''
    for kind, prop in (('output', 'outputs'), ('input', 'inputs')):
        cases = {role: [] for role in ('reference', 'predecessor', 'net')}
        helpers = {}
        for building, model in sorted(models.items()):
            goods = sorted({g for slot in model.slots for method in slot
                            for g, amount in getattr(method, prop).items() if amount > 0})
            for role in cases:
                writes = []
                for good in goods:
                    helper = f'{PREFIX}cache_{role}_{kind}_{good}'
                    if role == 'net':
                        body = (f'value = {cached_quantity("reference", kind, good)} '
                                f'subtract = {cached_quantity("predecessor", kind, good)} min = 0')
                    else:
                        source = ('var:eu5ab_pf_reference_building' if role == 'reference'
                                  else 'scope:eu5ab_engine_replaced_building')
                        body = (f'value = {source}.eu5ab_pr_nominal_{kind}_{good}_validated '
                                f'multiply = {{ value = 0 if = {{ limit = {{ has_variable = {PREFIX}{role}_efficiency }} '
                                f'add = var:{PREFIX}{role}_efficiency }} }}')
                    helpers[helper] = (f'add_to_variable_map = {{ name = {PREFIX}{role}_{kind} '
                                       f'key = goods:{good} value = {{ {body} }} }}')
                    writes.append(f'{helper} = yes')
                if writes:
                    cases[role].append(f'building_type:{building} = {{ {" ".join(writes)} }}')
        effects += f'''\neu5ab_prepare_quote_production_{kind}_quantities = {{
            if = {{ limit = {{ has_variable = {PREFIX}type NOT = {{ has_variable = {PREFIX}{kind}_ready }} }}
                if = {{ limit = {{ has_variable = {PREFIX}reference_known }}
                    switch = {{ trigger = {TYPE} {' '.join(cases['reference'])} }}
                }}
                if = {{ limit = {{ has_variable = {PREFIX}predecessor_known }}
                    switch = {{ trigger = scope:eu5ab_engine_replaced_building.building_type {' '.join(cases['predecessor'])} }}
                }}
                if = {{ limit = {{ has_variable = {PREFIX}reference_known }}
                    switch = {{ trigger = {TYPE} {' '.join(cases['net'])} }}
                }}
                set_variable = {PREFIX}{kind}_ready
            }}
        }}'''
        # Goods shared by many types use one write body, rather than expanding
        # the same map formula in every type's case. Only reachable goods run.
        effects += '\n' + '\n'.join(f'{name} = {{ {body} }}' for name, body in helpers.items())
    triggers = f'''eu5ab_quote_production_current = {{
        {LOCATION} = {{ has_variable = {PREFIX}type var:{PREFIX}type = prev }}
    }}'''
    for name, role in (('eu5ab_pending_identity_known', 'reference'),
                       ('eu5ab_pending_exact_predecessor', 'predecessor')):
        triggers += f'''\n{name} = {{ OR = {{
            AND = {{ eu5ab_quote_production_current = yes
                {LOCATION} = {{ has_variable = {PREFIX}{role}_known }} }}
            AND = {{ eu5ab_quote_production_current = no {name}_live = yes }}
        }} }}'''
    return effects, triggers


def cached_quantity(role, kind, good, *, scoped=False):
    from .production_goods import map_value
    reader = map_value(PREFIX + role + '_' + kind, 'goods:' + good)
    return f'{{ value = 0 {LOCATION} = {{ add = {reader} }} }}' if scoped else reader


def quantity_value(kind, good, *, predecessor=False):
    """Bypass repeated recipe validation only after full candidate validation."""
    role = 'predecessor' if predecessor else 'reference'
    source = ('scope:eu5ab_engine_replaced_building' if predecessor
              else LOCATION + '.var:eu5ab_pf_reference_building')
    return f'''if = {{ limit = {{ eu5ab_quote_production_current = yes }}
        if = {{ limit = {{ {LOCATION} = {{ has_variable = {PREFIX}{kind}_ready }} }}
            value = {cached_quantity(role, kind, good, scoped=True)}
        }}
        else = {{
            value = {source}.eu5ab_pr_nominal_{kind}_{good}_validated
            multiply = {{ value = 0
                if = {{ limit = {{ {LOCATION} = {{ has_variable = {PREFIX}{role}_efficiency }} }}
                    add = {LOCATION}.var:{PREFIX}{role}_efficiency }}
            }}
        }}
    }}
    else = {{ value = {source}.eu5ab_pr_reference_{kind}_{good} }}'''
