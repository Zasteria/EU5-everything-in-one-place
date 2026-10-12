"""Bounded fallback after a native-ranked batch shortlist has failed.

Location state survives same-queue reloads. Only queue teardown resets the
budget; quote refresh and phase reconstruction must not grant extra attempts.
"""
from .candidate_backfill import POOLS, _upsert_increment

COUNTRY = 'scope:eu5ab_engine_country'
LOCATION = 'scope:eu5ab_candidate_location'
TYPE = 'scope:eu5ab_candidate_building'


def cleanup():
    return '\n'.join([
        *(f'clear_variable_list = {pool}' for pool in POOLS),
        'clear_variable_list = eu5ab_batch_primary_types',
        'clear_variable_list = eu5ab_batch_backfill_tried',
        'clear_variable_list = eu5ab_batch_backfill_reported_failures',
        *(f'remove_variable = eu5ab_batch_backfill_{field}' for field in
          ('country', 'phase', 'remaining', 'started', 'triggered', 'exhausted', 'added')),
    ])


def prepare(phase):
    """Location scope; retain primary and overflow identities before retries."""
    store = '\n'.join(f'''{'if' if i == 0 else 'else_if'} = {{
        limit = {{ {LOCATION}.eu5ab_batch_quote_kind = {kind} }}
        {LOCATION} = {{ add_to_variable_list = {{ name = {pool} target = {TYPE} }} }}
    }}''' for i, (kind, pool) in enumerate(zip((2, 4, 3), POOLS, strict=True)))
    return f'''eu5ab_batch_initialize_backfill = yes
    if = {{ limit = {{ NOT = {{ AND = {{ has_variable = eu5ab_batch_backfill_phase
        var:eu5ab_batch_backfill_phase = {phase} }} }} }}
        clear_variable_list = eu5ab_batch_primary_types
        {' '.join(f'clear_variable_list = {pool}' for pool in POOLS)}
        set_variable = {{ name = eu5ab_batch_backfill_phase value = {phase} }}
        set_variable = {{ name = eu5ab_backfill_rank value = 0 }}
        set_variable = {{ name = eu5ab_backfill_head_limit value = {COUNTRY}.var:eu5ab_batch_type_limit }}
        set_variable = {{ name = eu5ab_backfill_window_limit value = {{
            value = var:eu5ab_backfill_head_limit {'add = var:eu5ab_batch_backfill_remaining' if phase <= 8 else ''} }} }}
        ordered_in_list = {{ variable = eu5ab_q_phase_{phase}_types order_by = eu5ab_batch_quote_order
            max = var:eu5ab_backfill_window_limit check_range_bounds = no
            limit = {{ {LOCATION} = {{ is_target_in_variable_list = {{ name = eu5ab_batch_passed_types target = prev }}
                NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_failed_types target = prev }} }}
                NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_consumed_types target = prev }} }} }} }}
            save_scope_as = eu5ab_candidate_building
            {LOCATION} = {{ change_variable = {{ name = eu5ab_backfill_rank add = 1 }} }}
            if = {{ limit = {{ {LOCATION} = {{ var:eu5ab_backfill_rank <= var:eu5ab_backfill_head_limit }} }}
                {LOCATION} = {{ add_to_variable_list = {{ name = eu5ab_batch_primary_types target = {TYPE} }} }}
            }}
            else = {{ {store} }}
        }}
        remove_variable = eu5ab_backfill_rank remove_variable = eu5ab_backfill_head_limit
        remove_variable = eu5ab_backfill_window_limit
    }}'''


def render(rules, phase_count):
    planning = (rules.cadence.candidates_per_location + 1) // 2
    profit = (rules.cadence.actual_profit_candidates_per_location + 1) // 2
    phases = ' '.join(f'''{phase} = {{ every_in_list = {{ variable = eu5ab_q_phase_{phase}_locations
        limit = {{ owner = {COUNTRY} }} save_scope_as = eu5ab_candidate_location
        eu5ab_batch_promote_backfill = yes
    }} }}''' for phase in range(1, min(8, phase_count) + 1))
    visits = '\n'.join(f'''if = {{ limit = {{ NOT = {{ has_variable = eu5ab_batch_backfill_added }} }}
        ordered_in_list = {{ variable = {pool} order_by = eu5ab_batch_quote_order max = 1 check_range_bounds = no
            limit = {{ {LOCATION} = {{
                NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_failed_types target = prev }} }}
                NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_consumed_types target = prev }} }}
                NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_backfill_tried target = prev }} }} }} }}
            save_scope_as = eu5ab_candidate_building
            {LOCATION} = {{
                remove_list_variable = {{ name = {pool} target = {TYPE} }}
                add_to_variable_list = {{ name = eu5ab_batch_backfill_tried target = {TYPE} }}
                add_to_variable_list = {{ name = eu5ab_batch_primary_types target = {TYPE} }}
                change_variable = {{ name = eu5ab_batch_backfill_remaining subtract = 1 }}
                set_variable = eu5ab_batch_backfill_added
                if = {{ limit = {{ NOT = {{ has_variable = eu5ab_batch_backfill_triggered }} }}
                    set_variable = eu5ab_batch_backfill_triggered
                    {COUNTRY} = {{ {_upsert_increment('eu5ab_diag_backfill_triggered')} }}
                }}
                save_scope_as = eu5ab_batch_refresh_location
                {TYPE} = {{ save_scope_as = eu5ab_batch_refresh_type }}
                eu5ab_batch_refresh_quote_pending = yes
                {COUNTRY} = {{
                    {_upsert_increment('eu5ab_diag_backfill_checked')}
                    {_upsert_increment('eu5ab_diag_backfill_staged')}
                    eu5ab_batch_add_candidate = yes
                }}
            }}
        }}
    }}''' for pool in POOLS)
    return f'''eu5ab_batch_initialize_backfill = {{
    if = {{ limit = {{ NOT = {{ AND = {{ exists = var:eu5ab_batch_backfill_country
        var:eu5ab_batch_backfill_country = owner }} }} }}
        {cleanup()}
        set_variable = {{ name = eu5ab_batch_backfill_country value = owner }}
        set_variable = {{ name = eu5ab_batch_backfill_remaining value = 0 }}
        if = {{ limit = {{ owner = {{ has_variable = eu5ab_scan_backfill_enabled }} }}
            set_variable = {{ name = eu5ab_batch_backfill_remaining value = {planning} }}
            if = {{ limit = {{ owner.var:eu5ab_batch_ranking_mode = 2 }}
                set_variable = {{ name = eu5ab_batch_backfill_remaining value = {profit} }} }}
        }}
    }}
}}
eu5ab_batch_record_backfill_failure = {{
    eu5ab_batch_select_context = yes
    {LOCATION} = {{ if = {{ limit = {{ owner = {COUNTRY}
        is_target_in_variable_list = {{ name = eu5ab_batch_backfill_tried target = {TYPE} }}
        NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_backfill_reported_failures target = {TYPE} }} }}
    }}
        add_to_variable_list = {{ name = eu5ab_batch_backfill_reported_failures target = {TYPE} }}
        {COUNTRY} = {{ {_upsert_increment('eu5ab_diag_backfill_stage_failed')} }}
    }} }}
}}
eu5ab_batch_try_backfill = {{
    if = {{ limit = {{ has_variable = eu5ab_scan_backfill_enabled }}
        switch = {{ trigger = var:eu5ab_q_phase {phases} }}
    }}
}}
eu5ab_batch_promote_backfill = {{
    if = {{ limit = {{ owner = {COUNTRY} var:eu5ab_batch_backfill_country = owner
        has_variable = eu5ab_batch_backfill_phase
        var:eu5ab_batch_backfill_phase = {COUNTRY}.var:eu5ab_q_phase
        NOT = {{ has_variable = eu5ab_batch_backfill_started }}
    }}
        remove_variable = eu5ab_batch_backfill_added
        if = {{ limit = {{ var:eu5ab_batch_backfill_remaining > 0 }} {visits} }}
        else_if = {{ limit = {{ has_variable = eu5ab_batch_backfill_triggered
            NOT = {{ has_variable = eu5ab_batch_backfill_exhausted }} }}
            set_variable = eu5ab_batch_backfill_exhausted
            {COUNTRY} = {{ {_upsert_increment('eu5ab_diag_backfill_budget_exhausted')} }}
        }}
        remove_variable = eu5ab_batch_backfill_added
    }}
}}
'''
