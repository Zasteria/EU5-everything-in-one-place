"""Read-only market inputs and base score for the synchronous RGO worker segment.

The worker does not start construction or update shared ledgers. Drop the
snapshot before returning; admission and later batch phases must read live data.
Each field has its own readiness bit because numeric zero may be omitted by EU5.
The base score reads stable location facts, not the diagnostic or staging writes.
"""

import re

PREFIX = 'eu5ab_rgo_screen_'
VALUES = ('eu5ab_rgo_market_demand', 'eu5ab_rgo_market_supply',
          'eu5ab_rgo_market_pending_quantity', 'eu5ab_rgo_market_pending_unknown',
          'eu5ab_rgo_price_percent', 'eu5ab_rgo_market_gap', 'eu5ab_rgo_pending_limit',
          'eu5ab_rgo_base_score')


def field(name):
    return PREFIX + name.removeprefix('eu5ab_rgo_')


def render_effects():
    clear = '\n'.join(f'    remove_variable = {field(name)}\n    remove_variable = {field(name)}_ready'
                      for name in VALUES)
    prepare = '\n'.join(f'    set_variable = {{ name = {field(name)} value = {name}_screen_live }}\n'
                        f'    set_variable = {field(name)}_ready' for name in VALUES)
    return f'''eu5ab_clear_rgo_screening = {{
{clear}
}}
eu5ab_prepare_rgo_screening = {{
    eu5ab_clear_rgo_screening = yes
{prepare}
}}
'''


def apply(files, root):
    effects = root / 'in_game/common/scripted_effects/eu5ab_scripted_effects.txt'
    values = root / 'in_game/common/script_values/eu5ab_script_values.txt'
    for name in VALUES:
        files[values], count = re.subn(rf'(?m)^{name} = ', name + '_screen_live = ', files[values])
        if count != 1:
            raise ValueError(f'Expected one RGO screening definition for {name}, got {count}')
        variable = field(name)
        files[values] += f'''
{name} = {{
    value = 0
    if = {{ limit = {{ has_variable = {variable}_ready }}
        if = {{ limit = {{ has_variable = {variable} }} value = var:{variable} }}
    }}
    else = {{ value = {name}_screen_live }}
}}
'''
    files[effects] += '\n' + render_effects()
