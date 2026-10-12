"""Independent RGO prices, workforce settings and live candidate selection."""

import json
from pathlib import Path

from .game_data import _blocks_from_directory
from .rgo_cost import RGO_METHODS


RAW_GOODS_FILE = Path(__file__).resolve().parents[2] / '.metadata/eu5ab_raw_goods.json'


def extract_raw_goods(game_root: Path) -> tuple[str, ...]:
    goods = _blocks_from_directory(game_root / 'game/in_game/common/goods')
    return tuple(sorted(good for good, body in goods.items()
                        if any(k == 'method' and v in RGO_METHODS for k, v in body)))


def raw_goods() -> tuple[str, ...]:
    return tuple(json.loads(RAW_GOODS_FILE.read_text(encoding='utf-8')))


def price_factor(price_percent: float, floor: float, emergency: bool = False) -> float:
    if emergency:
        return 1.0
    if price_percent <= floor:
        return 0.0
    if floor >= 100 or price_percent >= 100:
        return 1.0
    return (price_percent - floor) / (100 - floor)


def high_price_factor(price_percent: float, reference: float) -> float:
    """Scale the high-price reward from zero at standard price to its cap."""
    if price_percent <= 100:
        return 0.0
    if reference <= 100:
        return 1.0
    return min(1.0, (price_percent - 100) / (reference - 100))


def render_triggers() -> str:
    return '''
# Forecasting is explicit and uses the existing master switch.
eu5ab_rgo_population_mode = {
    owner.var:eu5ab_global_pause_low_workforce > 0
    owner.var:eu5ab_global_rgo_workforce_mode = 2
}
eu5ab_rgo_price_allowed = {
    OR = {
        eu5ab_rgo_food_emergency_enabled = yes
        AND = {
            exists = market
            exists = raw_material
            "default_price(raw_material)" > 0
            eu5ab_rgo_price_percent > owner.var:eu5ab_global_price_min
        }
    }
}
eu5ab_rgo_score_allowed = { eu5ab_rgo_base_score >= 0 }
'''


def render_values() -> str:
    lines = ['''
eu5ab_rgo_price_percent = {
    value = 0
    if = {
        limit = { exists = market exists = raw_material "default_price(raw_material)" > 0 }
''']
    # Explicit good targets avoid ambiguous argument resolution inside market scope.
    for index, good in enumerate(raw_goods()):
        branch = 'if' if index == 0 else 'else_if'
        lines.append(f'''        {branch} = {{
            limit = {{ raw_material = goods:{good} }}
            value = "market.market_price(goods:{good})"
            divide = "default_price(goods:{good})"
            multiply = 100
        }}''')
    lines.append('''    }
}
eu5ab_rgo_high_price_factor = {
    value = 0
    if = {
        limit = { eu5ab_rgo_price_percent > 100 }
        if = {
            limit = { owner.var:eu5ab_global_price_max > 100 }
            value = eu5ab_rgo_price_percent
            subtract = 100
            divide = { value = owner.var:eu5ab_global_price_max subtract = 100 }
            max = 1
        }
        else = { value = 1 }
    }
}
eu5ab_rgo_price_factor = {
    value = 1
    if = {
        limit = { NOT = { eu5ab_rgo_food_emergency_enabled = yes } }
        if = {
            limit = { eu5ab_rgo_price_percent <= owner.var:eu5ab_global_price_min }
            value = 0
        }
        else_if = {
            limit = { owner.var:eu5ab_global_price_min < 100 eu5ab_rgo_price_percent < 100 }
            value = eu5ab_rgo_price_percent
            subtract = owner.var:eu5ab_global_price_min
            divide = { value = 100 subtract = owner.var:eu5ab_global_price_min }
        }
    }
}
eu5ab_rgo_current_labor_factor = {
    value = 1
    if = {
        limit = {
            owner.var:eu5ab_global_pause_low_workforce <= 0
            eu5ab_rgo_current_available_workers < eu5ab_rgo_jobs_per_expansion
        }
        value = 0.4
    }
}
eu5ab_candidate_current_labor_factor = {
    value = 1
    if = {
        limit = {
            scope:eu5ab_candidate_location.owner.var:eu5ab_global_pause_low_workforce <= 0
            NOT = { eu5ab_candidate_current_workforce_sufficient = yes }
        }
        value = 0.4
    }
}
''')
    return '\n'.join(lines)


def render_effects() -> str:
    from .script_syntax import lower_map_formulas
    lines = ['''
# CMM sends Ctrl as +/-5 and Shift as a min/max write, then clears the gesture
# variables before calling us. Compare with the last synchronized setting.
# Reaching a bound by a normal/Ctrl click has the same clamped result as Shift.
# Reset callbacks carry cmm_reset_key and must keep the registered default.
eu5ab_rgo_adjust_horizon_step = {
    if = {
        limit = {
            has_variable = eu5ab_global_rgo_job_fill_deadline_months
            exists = scope:setting
            NOT = { exists = scope:cmm_reset_key }
        }
        # Scope-value equality treats a block as triggers, not arithmetic.
        set_local_variable = {
            name = eu5ab_rgo_horizon_delta
            value = {
                value = "variable_map(cmm|flag:eu5ab_regional_development__rgo_job_fill_deadline_months)"
                subtract = var:eu5ab_global_rgo_job_fill_deadline_months
            }
        }
        if = {
            limit = {
                "variable_map(cmm|flag:eu5ab_regional_development__rgo_job_fill_deadline_months)" = 1200
                var:eu5ab_global_rgo_job_fill_deadline_months < 1200
            }
            set_local_variable = {
                name = eu5ab_rgo_horizon_value
                value = { value = var:eu5ab_global_rgo_job_fill_deadline_months add = 120 max = 1200 }
            }
            cmm_set_setting_value = { setting = eu5ab_regional_development__rgo_job_fill_deadline_months value = local_var:eu5ab_rgo_horizon_value }
        }
        else_if = {
            limit = {
                "variable_map(cmm|flag:eu5ab_regional_development__rgo_job_fill_deadline_months)" = 0
                var:eu5ab_global_rgo_job_fill_deadline_months > 0
            }
            set_local_variable = {
                name = eu5ab_rgo_horizon_value
                value = { value = var:eu5ab_global_rgo_job_fill_deadline_months subtract = 120 min = 0 }
            }
            cmm_set_setting_value = { setting = eu5ab_regional_development__rgo_job_fill_deadline_months value = local_var:eu5ab_rgo_horizon_value }
        }
        else_if = {
            limit = {
                local_var:eu5ab_rgo_horizon_delta = 5
            }
            set_local_variable = {
                name = eu5ab_rgo_horizon_value
                value = { value = var:eu5ab_global_rgo_job_fill_deadline_months add = 12 max = 1200 }
            }
            cmm_set_setting_value = { setting = eu5ab_regional_development__rgo_job_fill_deadline_months value = local_var:eu5ab_rgo_horizon_value }
        }
        else_if = {
            limit = {
                local_var:eu5ab_rgo_horizon_delta = -5
            }
            set_local_variable = {
                name = eu5ab_rgo_horizon_value
                value = { value = var:eu5ab_global_rgo_job_fill_deadline_months subtract = 12 min = 0 }
            }
            cmm_set_setting_value = { setting = eu5ab_regional_development__rgo_job_fill_deadline_months value = local_var:eu5ab_rgo_horizon_value }
        }
    }
    remove_local_variable = eu5ab_rgo_horizon_value
}

eu5ab_initialize_rgo_settings = {
    if = {
        limit = { NOT = { is_key_in_variable_map = { name = cmm target = flag:eu5ab_regional_development__rgo_workforce_mode } } }
        cmm_set_setting_value = { setting = eu5ab_regional_development__rgo_workforce_mode value = 1 }
    }
    if = {
        limit = { NOT = { is_key_in_variable_map = { name = cmm target = flag:eu5ab_regional_development__rgo_job_fill_deadline_months } } }
        cmm_set_setting_value = { setting = eu5ab_regional_development__rgo_job_fill_deadline_months value = 180 }
    }
}
''']
    return lower_map_formulas('\n'.join(lines))


def render_live_queue_effect(phase_count: int) -> str:
    """Script list entries are completion tokens; each selects the live best RGO.

    The list stays stable while scores change after a successful start.
    Attempt markers are distinct from completion markers, so each script
    check consumes one token without retrying an already attempted location.
    """
    lines = ['eu5ab_try_best_remaining_rgo = {']
    for phase in range(1, phase_count + 1):
        lines.append(f'''    if = {{
        limit = {{ var:eu5ab_q_phase = {phase} }}
        ordered_in_list = {{
            variable = eu5ab_q_phase_{phase}_rgo_locations
            limit = {{
                owner = scope:eu5ab_engine_country
                NOT = {{ has_variable = eu5ab_q_rgo_attempted }}
                eu5ab_location_has_native_parallel_room = yes
                eu5ab_rgo_in_current_priority_phase = yes
                eu5ab_rgo_expansion_allowed = yes
            }}
            order_by = eu5ab_rgo_queue_order_score
            max = 1
            check_range_bounds = no
            set_variable = eu5ab_q_rgo_attempted
            save_scope_as = eu5ab_candidate_location
            eu5ab_try_construct_rgo_need = yes
        }}
    }}''')
    lines.append('}\n')
    return '\n'.join(lines)
