"""Read-only screening memoization for one synchronous location worker.

No country or shared building-type state is written. A missing map key means
not computed; predicate codes are 1=failed, 2=passed, 3=unknown. Numeric
readiness is independent of the value, because EU5 can omit numeric zero.
Admission, quotation and standalone callers retain the live fallbacks.
"""

import re

LOCATION = 'scope:eu5ab_candidate_location'
BUILDING = 'scope:eu5ab_candidate_building'
ACTIVE = 'eu5ab_worker_screen_active'
PREFIX = 'eu5ab_worker_screen_'
PREDICATES = {
    'inputs': 'eu5ab_inputs_available',
    'cooldown': 'eu5ab_candidate_production_cooldown_clear',
    'pending_ready': 'eu5ab_candidate_pending_data_ready',
    'pending_allowed': 'eu5ab_candidate_pending_preliminary_allowed',
    'price_valid': 'eu5ab_output_price_data_valid',
}
PRICE_VALUES = ('eu5ab_output_weight', 'eu5ab_output_low_weight', 'eu5ab_output_price_factor')
# One fused preparation effect still snapshots the two intermediates. The
# final factor references each weight more than once, so omitting these maps
# would repeat the expensive building/recipe price chains inside that effect.
SCREEN_PRICE_VALUES = PRICE_VALUES


def mapping(kind):
    return PREFIX + kind


def missing(kind):
    return f'NOT = {{ is_key_in_variable_map = {{ name = {mapping(kind)} target = {BUILDING} }} }}'


def store(kind, value):
    return f'add_to_variable_map = {{ name = {mapping(kind)} key = {BUILDING} value = {value} }}'


def prepare(kind):
    return f'eu5ab_prepare_worker_screen_{kind}'


def bind_definition(text, name, wrapper):
    text, count = re.subn(rf'(?m)^{name} = ', name + '_worker_live = ', text)
    if count != 1:
        raise ValueError(f'Expected one worker screening definition for {name}, got {count}')
    return text + '\n' + wrapper + '\n'


def predicate_wrapper(name, kind):
    # prev is the building type while examining location-owned maps.
    hit = f'{LOCATION} = {{ has_variable = {ACTIVE} is_key_in_variable_map = {{ name = {mapping(kind)} target = prev }} }}'
    return f'''{name} = {{ OR = {{
        AND = {{ {hit} {LOCATION} = {{ "variable_map({mapping(kind)}|prev)" = 2 }} }}
        AND = {{ NOT = {{ {hit} }} {name}_worker_live = yes }}
    }} }}'''


def value_wrapper(name, kind):
    return f'''{name} = {{ value = 0
        if = {{ limit = {{ {LOCATION} = {{ has_variable = {ACTIVE}
            is_key_in_variable_map = {{ name = {mapping(kind + '_ready')} target = prev }} }} }}
            {LOCATION} = {{ if = {{ limit = {{ is_key_in_variable_map = {{ name = {mapping(kind)} target = prev }} }}
                add = "variable_map({mapping(kind)}|prev)" }} }}
        }}
        else = {{ value = {name}_worker_live }}
    }}'''


def render_effects():
    maps = [*PREDICATES]
    maps += [suffix for v in SCREEN_PRICE_VALUES
             for suffix in (v.removeprefix('eu5ab_'), v.removeprefix('eu5ab_') + '_ready')]
    lines = ['eu5ab_clear_worker_screening = {',
             *(f'\tclear_variable_map = {mapping(kind)}' for kind in maps),
             f'\tremove_variable = {ACTIVE}', '}', '']
    for kind, trigger in PREDICATES.items():
        if kind == 'price_valid':
            # Price validity is produced only by the fused building snapshot
            # below; no separate preparation pass remains.
            continue
        lines += [f'{prepare(kind)} = {{', f'\t{LOCATION} = {{',
                  f'\t\tif = {{ limit = {{ has_variable = {ACTIVE} {missing(kind)} }}']
        if kind == 'pending_allowed':
            # Preserve the original cooldown-first short circuit.
            lines += [f'\t\t\t{BUILDING} = {{ {prepare("cooldown")} = yes }}']
            lines += [f'\t\t\tif = {{ limit = {{ {BUILDING} = {{ eu5ab_candidate_production_cooldown_clear = yes }} }} {BUILDING} = {{ {prepare("pending_ready")} = yes }} }}']
        lines += [f'\t\t\t{store(kind, 1)}',
                  f'\t\t\tif = {{ limit = {{ {BUILDING} = {{ {trigger}_worker_live = yes }} }} {store(kind, 2)} }}']
        if kind == 'pending_ready':
            lines += [f'\t\t\telse = {{ {store(kind, 3)} }}']
        elif kind == 'pending_allowed':
            lines += [f'\t\t\telse_if = {{ limit = {{ {BUILDING} = {{ eu5ab_candidate_production_cooldown_clear = yes }} is_key_in_variable_map = {{ name = {mapping("pending_ready")} target = {BUILDING} }} "variable_map({mapping("pending_ready")}|{BUILDING})" = 3 }} {store(kind, 3)} }}']
        elif kind == 'price_valid':
            lines += [f'\t\t\telse_if = {{ limit = {{ NOT = {{ exists = market }} }} {store(kind, 3)} }}']
        lines += ['\t\t}', '\t}', '}', '']
    lines += [
        f'{prepare("prices")} = {{',
        f'\t{LOCATION} = {{',
        f'\t\tif = {{ limit = {{ has_variable = {ACTIVE} {missing("output_price_factor_ready")} }}',
        # Fuse validity, weights and final factor into one building-level
        # effect. Code 1 is known invalid, 2 valid and 3 missing-market unknown.
        f'\t\t\t{BUILDING} = {{ eu5ab_prepare_candidate_market_prices = yes }}',
        f'\t\t\t{store("price_valid", 1)}',
        '\t\t\tif = {',
        f'\t\t\t\tlimit = {{ {BUILDING} = {{ eu5ab_output_price_data_valid_worker_live = yes }} }}',
        f'\t\t\t\t{store("price_valid", 2)}',
        f'\t\t\t\t{store("output_weight", BUILDING + ".eu5ab_output_weight_live_worker_live")}',
        f'\t\t\t\t{store("output_weight_ready", 1)}',
        '\t\t\t\tif = {',
        f'\t\t\t\t\tlimit = {{ is_key_in_variable_map = {{ name = {mapping("output_weight")} target = {BUILDING} }} "variable_map({mapping("output_weight")}|{BUILDING})" > 0 NOT = {{ AND = {{ eu5ab_food_emergency_enabled = yes {BUILDING} = {{ eu5ab_candidate_produces_food = yes }} }} }} }}',
        f'\t\t\t\t\t{store("output_low_weight", BUILDING + ".eu5ab_output_low_weight_live_worker_live")}',
        f'\t\t\t\t\t{store("output_low_weight_ready", 1)}',
        '\t\t\t\t}',
        '\t\t\t}',
        f'\t\t\telse_if = {{ limit = {{ NOT = {{ exists = market }} }} {store("price_valid", 3)} }}',
        f'\t\t\t{store("output_price_factor", BUILDING + ".eu5ab_output_price_factor_live_worker_live")}',
        f'\t\t\t{store("output_price_factor_ready", 1)}',
        '\t\t}', '\t}', '}', '',
    ]
    return '\n'.join(lines)


def apply(files, root):
    effects = root / 'in_game/common/scripted_effects/eu5ab_scripted_effects.txt'
    triggers = root / 'in_game/common/scripted_triggers/eu5ab_scripted_triggers.txt'
    values = root / 'in_game/common/script_values/eu5ab_script_values.txt'
    for kind, name in PREDICATES.items():
        files[triggers] = bind_definition(files[triggers], name, predicate_wrapper(name, kind))
    # Bind inside the candidate-local recipe snapshot's retained live path.
    for name in PRICE_VALUES:
        live = name + '_live'
        files[values] = bind_definition(files[values], live, value_wrapper(live, name.removeprefix('eu5ab_')))
    files[effects] += '\n' + render_effects()
