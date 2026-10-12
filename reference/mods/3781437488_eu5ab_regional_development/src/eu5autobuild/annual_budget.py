"""Persistent annual expenditure; configuration refreshes never refund spending."""


def render_effects() -> str:
    return '''
eu5ab_update_budget_remaining = {
    set_variable = { name = eu5ab_global_budget_remaining value = {
        value = eu5ab_global_budget_limit_value subtract = eu5ab_global_budget_spent_value min = 0
    } }
}
eu5ab_record_budget_settings = {
    set_variable = { name = eu5ab_budget_config_mode value = eu5ab_budget_setting_mode_value }
    set_variable = { name = eu5ab_budget_config_fixed value = eu5ab_budget_setting_fixed_value }
}
eu5ab_ensure_annual_budget = {
    if = { limit = { NOT = { has_variable = eu5ab_budget_year } }
        # Initialize expenditure from the current pool before recalculating it.
        # An initialized missing balance
        # is a spent-out zero, not permission to fund the country again.
        if = { limit = { NOT = { has_variable = eu5ab_global_budget_limit } has_variable = eu5ab_global_budget_remaining }
            set_variable = { name = eu5ab_global_budget_limit value = var:eu5ab_global_budget_remaining }
        }
        if = { limit = { OR = { has_variable = eu5ab_budget_initialized has_variable = eu5ab_global_budget_limit has_variable = eu5ab_global_budget_remaining } }
            set_variable = { name = eu5ab_global_budget_spent value = {
                value = eu5ab_global_budget_limit_value subtract = eu5ab_global_budget_remaining_value min = 0
            } }
        }
        else = {
            eu5ab_recalculate_budget_limit = yes
            remove_variable = eu5ab_global_budget_spent
        }
        set_variable = { name = eu5ab_budget_year value = current_year }
        set_variable = eu5ab_budget_initialized
        eu5ab_record_budget_settings = yes
    }
    else_if = { limit = { var:eu5ab_budget_year < current_year }
        eu5ab_recalculate_budget_limit = yes
        remove_variable = eu5ab_global_budget_spent
        set_variable = { name = eu5ab_budget_year value = current_year }
        eu5ab_record_budget_settings = yes
    }
    eu5ab_update_budget_remaining = yes
}
eu5ab_refresh_global_budget = {
    eu5ab_ensure_annual_budget = yes
    if = { limit = { OR = {
        NOT = { eu5ab_budget_config_mode_value = eu5ab_budget_setting_mode_value }
        AND = { eu5ab_budget_setting_mode_value = 1 NOT = { eu5ab_budget_config_fixed_value = eu5ab_budget_setting_fixed_value } }
    } }
        eu5ab_recalculate_budget_limit = yes
        eu5ab_record_budget_settings = yes
    }
    eu5ab_update_budget_remaining = yes
}
eu5ab_charge_annual_budget = {
    eu5ab_ensure_annual_budget = yes
    if = { limit = { local_var:eu5ab_budget_charge >= 0 }
        set_variable = { name = eu5ab_global_budget_spent value = {
            value = eu5ab_global_budget_spent_value add = local_var:eu5ab_budget_charge
        } }
        eu5ab_update_budget_remaining = yes
    }
    remove_local_variable = eu5ab_budget_charge
}
'''


def render_values() -> str:
    values = '\n'.join(f'''eu5ab_global_budget_{field}_value = {{
    value = 0
    if = {{ limit = {{ has_variable = eu5ab_global_budget_{field} }} add = var:eu5ab_global_budget_{field} }}
}}''' for field in ('spent', 'limit', 'remaining')) + '\n'
    for name, variable in (
        ('setting_mode', 'eu5ab_global_budget_mode'),
        ('setting_fixed', 'eu5ab_global_fixed_annual_budget'),
        ('config_mode', 'eu5ab_budget_config_mode'),
        ('config_fixed', 'eu5ab_budget_config_fixed'),
    ):
        values += f'''eu5ab_budget_{name}_value = {{
    value = 0
    if = {{ limit = {{ has_variable = {variable} }} add = var:{variable} }}
}}
'''
    return values


def render_scan_date() -> str:
    # These are native date triggers. Do not assume a day/month trigger is also
    # available as a script value; fixed literals work on all supported builds.
    lines = ['eu5ab_record_scan_date = {',
             '    set_variable = { name = eu5ab_diag_last_run_year value = current_year }']
    for part, maximum in (('month', 12), ('day', 31)):
        lines.extend(f'    if = {{ limit = {{ current_{part} = {n} }} set_variable = {{ name = eu5ab_diag_last_run_{part} value = {n} }} }}'
                     for n in range(1, maximum + 1))
    return '\n'.join([*lines, '}']) + '\n'
