"""Screened RGO snapshots and synchronous batches at the existing phase position.

Project and group identities are country-owned numeric IDs. Only active rows
remain in per-good pools; a changed market/good refreshes its group, and the
dispatcher compares cached group winners. No construction depends on a GUI tick.
"""
from .rgo_automation import raw_goods
from .rgo_pending import DEMAND_BUFFER_RATIO, MIN_FACTOR

PREFIX = 'eu5ab_batch_rgo_'
ID = 'scope:eu5ab_batch_id'
GROUP = 'scope:eu5ab_batch_rgo_group'
COUNTRY = 'scope:eu5ab_engine_country'
LOCATION = 'scope:eu5ab_candidate_location'
FIELDS = ('location', 'market', 'good', 'group', 'status', 'phase', 'month', 'year', 'cost', 'base', 'price',
          'labor', 'output', 'emergency', 'score', 'queue_before', 'level_before', 'debit')


def read(field, key=ID):
    return f'"variable_map({PREFIX}{field}|{key})"'


def write(field, value, key=ID):
    return f'add_to_variable_map = {{ name = {PREFIX}{field} key = {key} value = {value} }}'


def snapshot_value(field):
    if field == 'emergency':
        # False snapshots omit the marker. Old saves store true as a boolean,
        # so never pass that value to numeric arithmetic or a numeric map.
        return f'''{{ value = 0 {LOCATION} = {{ if = {{ limit = {{ has_variable = {PREFIX}snapshot_emergency }}
            value = 1 }} }} }}'''
    return f'''{{ value = 0 {LOCATION} = {{ if = {{ limit = {{ has_variable = {PREFIX}snapshot_{field} }}
        add = var:{PREFIX}snapshot_{field} }} }} }}'''


def render(goods):
    from .construction_batch import OPEN, increment, map_value
    goods = set(goods)
    raw = raw_goods()
    cases, refresh, remove, holds = [], [], [], []
    for g in raw:
        index = f'{PREFIX}index_{g}'
        pool = f'{PREFIX}pool_{g}'
        held = f'{PREFIX}held_{g}'
        cases.append(f'''goods:{g} = {{
            if = {{ limit = {{ NOT = {{ is_key_in_variable_map = {{ name = {index} target = scope:eu5ab_batch_market }} }} }}
                add_to_variable_map = {{ name = {index} key = scope:eu5ab_batch_market value = {ID} }}
                add_to_variable_list = {{ name = {PREFIX}groups target = {ID} }}
                {write('group_market', 'scope:eu5ab_batch_market')}
                {write('group_good', 'goods:' + g)}
                {write('group_demand', snapshot_value('demand'))}
                {write('group_supply', snapshot_value('supply'))}
                {write('group_emergency', read('emergency'))}
            }}
            {write('group', f'"variable_map({index}|scope:eu5ab_batch_market)"')}
            add_to_variable_list = {{ name = {pool} target = {ID} }}
        }}''')
        ordinary = map_value('eu5ab_build_pending_' + g, 'scope:eu5ab_batch_market')
        demand = read('group_demand', GROUP)
        supply = read('group_supply', GROUP)
        if g in goods:
            # Ordinary and RGO candidates use the same screened market baseline
            # when one exists; deltas below include all approved building inputs.
            ordinary = f'''{{ value = {ordinary}
                if = {{ limit = {{ is_target_in_variable_list = {{ name = eu5ab_batch_markets target = scope:eu5ab_batch_market }} }}
                    value = {map_value('eu5ab_batch_output_' + g, 'scope:eu5ab_batch_market')} }} }}'''
            demand = f'''{{ value = {demand}
                if = {{ limit = {{ is_target_in_variable_list = {{ name = eu5ab_batch_markets target = scope:eu5ab_batch_market }} }}
                    value = {map_value('eu5ab_batch_eu5ab_market_effective_demand_' + g, 'scope:eu5ab_batch_market')} }}
                add = {map_value('eu5ab_batch_input_delta_' + g, 'scope:eu5ab_batch_market')} }}'''
            supply = f'''{{ value = {supply}
                if = {{ limit = {{ is_target_in_variable_list = {{ name = eu5ab_batch_markets target = scope:eu5ab_batch_market }} }}
                    value = {map_value('eu5ab_batch_supply_' + g, 'scope:eu5ab_batch_market')} }} }}'''
        refresh.append(f'''goods:{g} = {{
            set_local_variable = {{ name = eu5ab_rgo_demand value = {demand} }}
            set_local_variable = {{ name = eu5ab_rgo_limit value = {{ value = local_var:eu5ab_rgo_demand subtract = {supply} min = 0
                add = {{ value = local_var:eu5ab_rgo_demand multiply = {DEMAND_BUFFER_RATIO:g} }} }} }}
            set_local_variable = {{ name = eu5ab_rgo_pending value = {{ value = {ordinary}
                add = {map_value('eu5ab_rgo_pending_output_' + g, 'scope:eu5ab_batch_market')}
                add = {map_value(held, 'scope:eu5ab_batch_market')} }} }}
            set_local_variable = {{ name = eu5ab_rgo_unknown value = {map_value('eu5ab_rgo_pending_unknown_' + g, 'scope:eu5ab_batch_market')} }}
            eu5ab_batch_rgo_compute_factor = yes
            every_in_list = {{ variable = {pool}
                save_scope_value_as = {{ name = eu5ab_batch_rgo_row value = this }}
                {COUNTRY} = {{ if = {{ limit = {{ {read('group', 'scope:eu5ab_batch_rgo_row')} = {GROUP}
                    {read('status', 'scope:eu5ab_batch_rgo_row')} = 1 }}
                    {write('score', '{ value = ' + read('base', 'scope:eu5ab_batch_rgo_row') + ' multiply = ' + read('price', 'scope:eu5ab_batch_rgo_row') +
                        ' multiply = local_var:eu5ab_rgo_factor multiply = ' + read('labor', 'scope:eu5ab_batch_rgo_row') + ' }', 'scope:eu5ab_batch_rgo_row')}
                    if = {{ limit = {{ local_var:eu5ab_rgo_factor > 0 OR = {{
                        NOT = {{ is_key_in_variable_map = {{ name = {PREFIX}best target = {GROUP} }} }}
                        {read('score', 'scope:eu5ab_batch_rgo_row')} > {read('best_score', GROUP)}
                        AND = {{ {read('score', 'scope:eu5ab_batch_rgo_row')} = {read('best_score', GROUP)}
                            scope:eu5ab_batch_rgo_row < {read('best', GROUP)} }} }} }}
                        {write('best', 'scope:eu5ab_batch_rgo_row', GROUP)}
                        {write('best_score', read('score', 'scope:eu5ab_batch_rgo_row'), GROUP)}
                    }}
                }} }}
            }}
        }}''')
        remove.append(f'goods:{g} = {{ remove_list_variable = {{ name = {pool} target = {ID} }} }}')
        holds.append(f'''goods:{g} = {{ add_to_variable_map = {{ name = {held} key = scope:eu5ab_batch_market value = {{
            value = {map_value(held, 'scope:eu5ab_batch_market')} add = {{ value = {read('output')} multiply = local_var:eu5ab_rgo_hold_direction }} min = 0 }} }} }}''')
    clear_groups = '\n'.join(f'clear_variable_map = {PREFIX}{f}' for f in
                            ('group_market', 'group_good', 'group_demand', 'group_supply', 'group_emergency', 'best', 'best_score'))
    clear_groups += '\n' + '\n'.join(f'clear_variable_map = {PREFIX}index_{g}\nclear_variable_list = {PREFIX}pool_{g}' for g in raw)
    snapshot = '\n'.join(f'set_variable = {{ name = {PREFIX}snapshot_{f} value = {v} }}' for f, v in (
        ('cost', 'eu5ab_rgo_expansion_cost'), ('base', 'eu5ab_rgo_base_score'), ('price', 'eu5ab_rgo_price_factor'),
        ('labor', 'eu5ab_rgo_current_labor_factor'), ('output', 'eu5ab_rgo_full_level_output'),
        ('demand', 'eu5ab_rgo_market_demand'), ('supply', 'eu5ab_rgo_market_supply'),
        ('market', 'market'), ('good', 'raw_material'), ('owner', 'owner'),
        ('month', 'owner.var:eu5ab_scan_month'), ('year', 'owner.var:eu5ab_scan_year')))
    copies = '\n'.join(write(f, LOCATION + '.var:' + PREFIX + 'snapshot_' + f if f in ('market', 'good') else snapshot_value(f))
                       for f in ('cost', 'base', 'price', 'labor', 'output', 'emergency', 'market', 'good'))
    collect = '\n'.join(f'''{phase} = {{ every_in_list = {{ variable = eu5ab_q_phase_{phase}_rgo_locations
        limit = {{ owner = {COUNTRY} NOT = {{ has_variable = eu5ab_q_rgo_attempted }}
            NOT = {{ AND = {{ exists = var:{PREFIX}attempt_owner var:{PREFIX}attempt_owner = owner
                has_variable = {PREFIX}attempt_month has_variable = {PREFIX}attempt_year
                var:{PREFIX}attempt_month = owner.var:eu5ab_scan_month var:{PREFIX}attempt_year = owner.var:eu5ab_scan_year }} }} }}
        save_scope_as = eu5ab_candidate_location
        # Pre-upgrade saves get one new snapshot, never an old GUI replay.
        if = {{ limit = {{ NOT = {{ AND = {{ exists = var:{PREFIX}snapshot_owner var:{PREFIX}snapshot_owner = owner
            has_variable = {PREFIX}snapshot_month has_variable = {PREFIX}snapshot_year
            var:{PREFIX}snapshot_month = owner.var:eu5ab_scan_month var:{PREFIX}snapshot_year = owner.var:eu5ab_scan_year }} }} }}
            eu5ab_batch_rgo_screen = yes }}
        owner = {{ {increment('eu5ab_q_processed')}
            if = {{ limit = {{ {LOCATION} = {{ has_variable = {PREFIX}snapshot_ready }} }} eu5ab_batch_rgo_add = yes }} }}
    }} }}''' for phase in range(1, 9))
    recover = '\n'.join(f'''every_in_list = {{ variable = eu5ab_q_phase_{phase}_rgo_locations
        limit = {{ owner = scope:eu5ab_rgo_screen_country
            exists = var:{PREFIX}snapshot_owner var:{PREFIX}snapshot_owner = owner
            has_variable = {PREFIX}snapshot_month has_variable = {PREFIX}snapshot_year
            var:{PREFIX}snapshot_month = owner.var:eu5ab_scan_month var:{PREFIX}snapshot_year = owner.var:eu5ab_scan_year
            NOT = {{ has_variable = {PREFIX}snapshot_ready }}
            OR = {{ NOT = {{ has_variable = {PREFIX}snapshot_evaluated }}
                AND = {{ has_variable = {PREFIX}snapshot_pending
                    OR = {{ eu5ab_rgo_food_emergency_enabled = yes eu5ab_rgo_pending_data_available = yes }} }} }} }}
        save_scope_as = eu5ab_candidate_location
        eu5ab_batch_rgo_screen = yes
    }}''' for phase in range(1, 9))
    return f'''
eu5ab_batch_rgo_screen = {{
    {snapshot}
    remove_variable = {PREFIX}snapshot_emergency remove_variable = {PREFIX}snapshot_ready
    remove_variable = {PREFIX}snapshot_pending set_variable = {PREFIX}snapshot_evaluated
    if = {{ limit = {{ eu5ab_rgo_food_emergency_enabled = yes }} set_variable = {{ name = {PREFIX}snapshot_emergency value = 1 }} }}
    if = {{ limit = {{ eu5ab_rgo_expansion_allowed = yes }} set_variable = {PREFIX}snapshot_ready }}
    else_if = {{ limit = {{ NOT = {{ eu5ab_rgo_food_emergency_enabled = yes }} NOT = {{ eu5ab_rgo_pending_data_available = yes }} }}
        set_variable = {PREFIX}snapshot_pending }}
    eu5ab_batch_slots_ensure = yes
}}
eu5ab_recover_pending_rgo_screens = {{
    # Retry incomplete screening before queue entry, never reopen a known
    # rejection or alter the batch's ranking, approval or construction loop.
    save_scope_as = eu5ab_rgo_screen_country
    {recover}
}}
eu5ab_batch_rgo_add = {{
    {increment('eu5ab_batch_sequence')}
    save_scope_value_as = {{ name = eu5ab_batch_id value = var:eu5ab_batch_sequence }}
    add_to_variable_list = {{ name = {PREFIX}records target = {ID} }}
    {write('location', LOCATION)} {write('status', '1')} {copies}
    {write('phase', 'var:eu5ab_q_phase')} {write('month', 'var:eu5ab_scan_month')} {write('year', 'var:eu5ab_scan_year')}
    {read('market')} = {{ save_scope_as = eu5ab_batch_market }}
    switch = {{ trigger = {read('good')} {' '.join(cases)} }}
}}
eu5ab_batch_rgo_prepare = {{
    # The reducer owns shared ledgers. Parallel screening workers only write
    # their own location snapshots, including in an RGO-only country.
    if = {{ limit = {{ NOT = {{ AND = {{ has_variable = eu5ab_batch_ledger_month has_variable = eu5ab_batch_ledger_year
        var:eu5ab_batch_ledger_month = var:eu5ab_scan_month var:eu5ab_batch_ledger_year = var:eu5ab_scan_year }} }} }}
        eu5ab_batch_reset_ledgers = yes
        set_variable = {{ name = eu5ab_batch_ledger_month value = var:eu5ab_scan_month }}
        set_variable = {{ name = eu5ab_batch_ledger_year value = var:eu5ab_scan_year }} }}
    {clear_groups}
    clear_variable_list = {PREFIX}groups
    clear_variable_list = {PREFIX}active_groups
    clear_variable_list = {PREFIX}deferred
    set_variable = {{ name = {PREFIX}phase value = var:eu5ab_q_phase }}
    switch = {{ trigger = var:eu5ab_q_phase {collect} }}
    every_in_list = {{ variable = {PREFIX}groups save_scope_value_as = {{ name = eu5ab_batch_rgo_group value = this }}
        {COUNTRY} = {{ eu5ab_batch_rgo_refresh_group = yes }} }}
    clear_variable_list = {PREFIX}dirty
}}
eu5ab_batch_rgo_compute_factor = {{
    set_local_variable = {{ name = eu5ab_rgo_factor value = 0 }}
    if = {{ limit = {{ {read('group_emergency', GROUP)} > 0 }} set_local_variable = {{ name = eu5ab_rgo_factor value = 1 }} }}
    else_if = {{ limit = {{ local_var:eu5ab_rgo_unknown > 0 }} set_local_variable = {{ name = eu5ab_rgo_factor value = 0 }} }}
    else_if = {{ limit = {{ local_var:eu5ab_rgo_pending = 0 }} set_local_variable = {{ name = eu5ab_rgo_factor value = 1 }} }}
    else_if = {{ limit = {{ local_var:eu5ab_rgo_pending < local_var:eu5ab_rgo_limit local_var:eu5ab_rgo_limit > 0 }}
        set_local_variable = {{ name = eu5ab_rgo_factor value = {{ value = 1 subtract = {{ value = local_var:eu5ab_rgo_pending
            divide = local_var:eu5ab_rgo_limit multiply = {{ value = local_var:eu5ab_rgo_pending divide = local_var:eu5ab_rgo_limit }} }} min = {MIN_FACTOR:.5f} }} }} }}
}}
eu5ab_batch_rgo_refresh_group = {{
    remove_from_variable_map = {{ name = {PREFIX}best key = {GROUP} }}
    {read('group_market', GROUP)} = {{ save_scope_as = eu5ab_batch_market }}
    switch = {{ trigger = {read('group_good', GROUP)} {' '.join(refresh)} }}
    remove_list_variable = {{ name = {PREFIX}active_groups target = {GROUP} }}
    if = {{ limit = {{ is_key_in_variable_map = {{ name = {PREFIX}best target = {GROUP} }} }}
        add_to_variable_list = {{ name = {PREFIX}active_groups target = {GROUP} }} }}
}}
eu5ab_batch_rgo_select = {{
    remove_variable = {PREFIX}winner
    every_in_list = {{ variable = {PREFIX}active_groups save_scope_value_as = {{ name = eu5ab_batch_rgo_group value = this }}
        {COUNTRY} = {{ if = {{ limit = {{ is_key_in_variable_map = {{ name = {PREFIX}best target = {GROUP} }}
            OR = {{ NOT = {{ has_variable = {PREFIX}winner }} {read('best_score', GROUP)} > var:{PREFIX}winner_score
                AND = {{ {read('best_score', GROUP)} = var:{PREFIX}winner_score {read('best', GROUP)} < var:{PREFIX}winner }} }} }}
            set_variable = {{ name = {PREFIX}winner value = {read('best', GROUP)} }}
            set_variable = {{ name = {PREFIX}winner_score value = {read('best_score', GROUP)} }}
        }} }}
    }}
}}
eu5ab_batch_rgo_context = {{
    {read('location')} = {{ save_scope_as = eu5ab_candidate_location }}
    {read('market')} = {{ save_scope_as = eu5ab_batch_market }}
    save_scope_value_as = {{ name = eu5ab_batch_rgo_group value = {read('group')} }}
}}
eu5ab_batch_rgo_remove = {{ switch = {{ trigger = {read('good')} {' '.join(remove)} }} }}
eu5ab_batch_rgo_hold_output = {{ switch = {{ trigger = {read('good')} {' '.join(holds)} }} }}
eu5ab_batch_rgo_reserve = {{
    {write('status', '2')} {increment('eu5ab_q_approved')}
    set_variable = {{ name = eu5ab_batch_reserved value = {{ value = eu5ab_batch_reserved_value add = 1 }} }}
    set_variable = {{ name = eu5ab_batch_planned value = {{ value = eu5ab_batch_planned_value add = {read('cost')} }} }}
    {LOCATION} = {{ eu5ab_batch_slots_reserve = yes }}
    set_local_variable = {{ name = eu5ab_rgo_hold_direction value = 1 }} eu5ab_batch_rgo_hold_output = yes
    add_to_variable_list = {{ name = {PREFIX}approved target = {ID} }}
    eu5ab_batch_rgo_remove = yes eu5ab_batch_rgo_refresh_group = yes
}}
eu5ab_batch_rgo_release = {{
    set_variable = {{ name = eu5ab_batch_reserved value = {{ value = eu5ab_batch_reserved_value subtract = 1 min = 0 }} }}
    set_variable = {{ name = eu5ab_batch_planned value = {{ value = eu5ab_batch_planned_value subtract = {read('cost')} min = 0 }} }}
    set_local_variable = {{ name = eu5ab_rgo_hold_direction value = -1 }} eu5ab_batch_rgo_hold_output = yes
}}
eu5ab_batch_rgo_withdraw = {{
    eu5ab_batch_rgo_release = yes {write('status', '7')} {increment('eu5ab_q_confirmed')}
    {LOCATION} = {{ eu5ab_batch_slots_release = yes }}
}}
eu5ab_batch_rgo_approve = {{
    clear_variable_list = {PREFIX}approved remove_variable = eu5ab_batch_boundary
    eu5ab_batch_rgo_select = yes
    while = {{ count = 100000 limit = {{ has_variable = {PREFIX}winner NOT = {{ has_variable = eu5ab_batch_boundary }} }}
        save_scope_value_as = {{ name = eu5ab_batch_id value = var:{PREFIX}winner }} eu5ab_batch_rgo_context = yes
        {LOCATION} = {{ if = {{ limit = {{ owner = {COUNTRY} }} eu5ab_batch_slots_ensure = yes }} }}
        if = {{ limit = {{ {LOCATION} = {{ owner = {COUNTRY} eu5ab_batch_slots_value > 0 }}
            var:eu5ab_constructions_started_this_tick < {{ value = var:eu5ab_monthly_build_quota subtract = eu5ab_batch_reserved_value }}
            eu5ab_global_budget_remaining_value > eu5ab_batch_planned_value
            gold >= {{ value = {read('cost')} add = eu5ab_batch_planned_value add = {LOCATION}.eu5ab_current_min_cash_reserve }} }}
            if = {{ limit = {{ eu5ab_global_budget_remaining_value >= {{ value = eu5ab_batch_planned_value add = {read('cost')} }} }} eu5ab_batch_rgo_reserve = yes }}
            else_if = {{ limit = {{ eu5ab_batch_reserved_value = 0 }} eu5ab_batch_rgo_reserve = yes set_variable = eu5ab_batch_boundary }}
            else = {{ set_variable = eu5ab_batch_boundary }}
        }}
        else_if = {{ limit = {{ OR = {{
            var:eu5ab_constructions_started_this_tick >= {{ value = var:eu5ab_monthly_build_quota subtract = eu5ab_batch_reserved_value }}
            eu5ab_global_budget_remaining_value <= eu5ab_batch_planned_value }} }}
            set_variable = eu5ab_batch_boundary
        }}
        else = {{
            # Only a real temporary hold can defer this row. Losing ownership,
            # permanent slot exhaustion and intrinsically unaffordable rows retire.
            if = {{ limit = {{ eu5ab_batch_reserved_value > 0
                {LOCATION} = {{ owner = {COUNTRY}
                    OR = {{ eu5ab_batch_slots_value > 0 eu5ab_batch_slots_held_value > 0 }} }}
                gold >= {{ value = {read('cost')} add = {LOCATION}.eu5ab_current_min_cash_reserve }} }}
                {write('status', '8')} add_to_variable_list = {{ name = {PREFIX}deferred target = {ID} }} }}
            else = {{ {write('status', '7')} eu5ab_batch_rgo_remove = yes }}
            eu5ab_batch_rgo_refresh_group = yes
        }}
        eu5ab_batch_rgo_select = yes
    }}
}}
eu5ab_batch_rgo_issue = {{
    every_in_list = {{ variable = {PREFIX}approved save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{ eu5ab_batch_rgo_context = yes
            if = {{ limit = {{ {read('status')} = 2 }}
                if = {{ limit = {{ {OPEN} {read('phase')} = var:eu5ab_q_phase {read('month')} = var:eu5ab_scan_month {read('year')} = var:eu5ab_scan_year
                    eu5ab_global_budget_remaining_value > 0 {LOCATION} = {{ owner = {COUNTRY}
                        raw_material = "{COUNTRY}.variable_map({PREFIX}good|{ID})" }}
                    gold >= {{ value = eu5ab_batch_planned_value add = {LOCATION}.eu5ab_current_min_cash_reserve }} }}
                    {write('status', '3')} {increment('eu5ab_q_seen')}
                    {write('queue_before', LOCATION + '.num_civil_constructions')} {write('level_before', LOCATION + '.rgo_level')}
                    {LOCATION} = {{ set_variable = eu5ab_q_rgo_attempted
                        set_variable = {{ name = {PREFIX}attempt_owner value = owner }}
                        set_variable = {{ name = {PREFIX}attempt_month value = owner.var:eu5ab_scan_month }}
                        set_variable = {{ name = {PREFIX}attempt_year value = owner.var:eu5ab_scan_year }}
                        eu5ab_prepare_rgo_pending_start = yes
                        eu5ab_capture_rgo_start_queue = yes
                        set_variable = {{ name = eu5ab_rgo_start_output value = "{COUNTRY}.variable_map({PREFIX}output|{ID})" }}
                        set_variable = {{ name = eu5ab_rgo_start_level value = rgo_level }}
                        set_local_variable = {{ name = eu5ab_rgo_gold_before value = owner.gold }}
                        construct_rgo_upgrade = {{ }}
                        set_local_variable = {{ name = eu5ab_rgo_paid_cost value = {{ value = local_var:eu5ab_rgo_gold_before subtract = owner.gold min = 0 }} }}
                        if = {{ limit = {{ OR = {{ num_civil_constructions > "{COUNTRY}.variable_map({PREFIX}queue_before|{ID})"
                            rgo_level > "{COUNTRY}.variable_map({PREFIX}level_before|{ID})" }} }}
                            eu5ab_record_queue_start_location = yes eu5ab_record_rgo_start = yes
                            eu5ab_batch_slots_commit = yes
                            set_variable = eu5ab_active_rgo_construction set_variable = eu5ab_action_taken remove_variable = eu5ab_failure_cooldown
                            owner = {{ {write('status', '4')} {write('debit', 'local_var:eu5ab_rgo_paid_cost')}
                                set_local_variable = {{ name = eu5ab_budget_charge value = local_var:eu5ab_rgo_paid_cost }} eu5ab_charge_annual_budget = yes
                                {increment('eu5ab_constructions_started_this_tick')} {increment('eu5ab_rgo_started_this_tick')}
                                if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_active_project_locations target = {LOCATION} }} }} }}
                                    add_to_variable_list = {{ name = eu5ab_active_project_locations target = {LOCATION} }} }}
                                eu5ab_batch_rgo_release = yes
                                add_to_variable_map = {{ name = eu5ab_batch_market_generation key = scope:eu5ab_batch_market
                                    value = {{ value = eu5ab_batch_market_generation_value add = 1 }} }}
                            }}
                        }}
                        else = {{
                            owner = {{ eu5ab_batch_rgo_withdraw = yes {write('status', '5')} {increment('eu5ab_diag_fail_vanilla')} }} }}
                        remove_variable = eu5ab_rgo_start_output remove_variable = eu5ab_rgo_start_level remove_variable = eu5ab_rgo_start_queue remove_variable = eu5ab_rgo_start_queue_known
                        remove_local_variable = eu5ab_rgo_gold_before remove_local_variable = eu5ab_rgo_paid_cost
                    }}
                }}
                else = {{ eu5ab_batch_rgo_withdraw = yes }}
            }}
        }}
    }}
    eu5ab_batch_rgo_confirm = yes
    every_in_list = {{ variable = {PREFIX}deferred save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{ if = {{ limit = {{ {read('status')} = 8 }}
            eu5ab_batch_rgo_context = yes
            if = {{ limit = {{ {LOCATION} = {{ owner = {COUNTRY} eu5ab_batch_slots_value > 0 }}
                gold >= {{ value = {read('cost')} add = {LOCATION}.eu5ab_current_min_cash_reserve }} }}
                {write('status', '1')} }}
            else = {{ {write('status', '7')} eu5ab_batch_rgo_remove = yes }}
        }} }} }}
    clear_variable_list = {PREFIX}deferred
    # Refresh only groups touched by approval/withdrawal; unchanged groups keep their winner.
    every_in_list = {{ variable = {PREFIX}dirty save_scope_value_as = {{ name = eu5ab_batch_rgo_group value = this }}
        {COUNTRY} = {{ eu5ab_batch_rgo_refresh_group = yes }} }}
    clear_variable_list = {PREFIX}dirty
}}
eu5ab_batch_rgo_confirm = {{
    every_in_list = {{ variable = {PREFIX}approved save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{ if = {{ limit = {{ {read('status')} = 4 }}
            {write('status', '6')} {increment('eu5ab_q_confirmed')} {increment('eu5ab_diag_active_mod_projects')}
            set_variable = {{ name = eu5ab_diag_built_this_run value = 1 }}
            set_variable = {{ name = eu5ab_diag_last_build_location value = {read('location')} }}
            set_variable = {{ name = eu5ab_diag_last_build_kind value = 1 }}
            set_variable = {{ name = eu5ab_diag_last_actual_cost value = {read('debit')} }}
        }} }}
    }}
    clear_variable_list = {PREFIX}approved
}}
eu5ab_batch_rgo_run = {{
    if = {{ limit = {{ NOT = {{ AND = {{ has_variable = {PREFIX}phase var:{PREFIX}phase = var:eu5ab_q_phase }} }} }} eu5ab_batch_rgo_prepare = yes }}
    eu5ab_batch_rgo_approve = yes eu5ab_batch_rgo_issue = yes
    eu5ab_batch_rgo_select = yes
    if = {{ limit = {{ NOT = {{ has_variable = {PREFIX}winner }} }} set_variable = {{ name = {PREFIX}done_phase value = var:eu5ab_q_phase }} }}
}}
eu5ab_batch_rgo_close = {{
    eu5ab_batch_rgo_confirm = yes
    every_in_list = {{ variable = {PREFIX}records save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{ if = {{ limit = {{ {read('status')} = 2 }} eu5ab_batch_rgo_context = yes eu5ab_batch_rgo_withdraw = yes }} }} }}
    {clear_groups}
    {' '.join('clear_variable_map = ' + PREFIX + f for f in FIELDS)}
    {' '.join('clear_variable_map = ' + PREFIX + 'held_' + g for g in raw)}
    clear_variable_list = {PREFIX}records clear_variable_list = {PREFIX}groups clear_variable_list = {PREFIX}active_groups clear_variable_list = {PREFIX}deferred clear_variable_list = {PREFIX}dirty
    remove_variable = {PREFIX}phase remove_variable = {PREFIX}done_phase remove_variable = {PREFIX}winner remove_variable = {PREFIX}winner_score
}}
'''.replace('eu5ab_batch_rgo_refresh_group = {', '''eu5ab_batch_rgo_refresh_group = {
    if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_batch_rgo_dirty target = scope:eu5ab_batch_rgo_group } } }
        add_to_variable_list = { name = eu5ab_batch_rgo_dirty target = scope:eu5ab_batch_rgo_group } }''', 1)


def apply(effects, triggers, guis, widget, goods, block, replace):
    effects = effects.replace('eu5ab_stage_rgo_candidate = {',
        'eu5ab_stage_rgo_candidate = {\n    eu5ab_batch_rgo_screen = yes', 1)
    effects += render(goods)
    name = 'eu5ab_start_engine_candidate_queue'
    start = block(effects, name).replace('eu5ab_sort_rgo_candidate_queue = yes',
        'eu5ab_sort_rgo_candidate_queue = yes\n    eu5ab_refresh_rgo_pending = yes\n    eu5ab_recover_pending_rgo_screens = yes', 1)
    effects = replace(effects, name, start)
    name = 'eu5ab_resume_saved_queue'
    resume = block(effects, name).replace('eu5ab_prepare_engine_priority_phase = yes',
        'eu5ab_recover_pending_rgo_screens = yes\n    eu5ab_prepare_engine_priority_phase = yes', 1)
    effects = replace(effects, name, resume)
    migration = '\n'.join(f'''every_in_list = {{ variable = eu5ab_q_phase_{phase}_rgo_locations
        limit = {{ owner = scope:eu5ab_rgo_resume_country has_variable = eu5ab_q_rgo_attempted }}
        set_variable = {{ name = {PREFIX}attempt_owner value = owner }}
        set_variable = {{ name = {PREFIX}attempt_month value = owner.var:eu5ab_scan_month }}
        set_variable = {{ name = {PREFIX}attempt_year value = owner.var:eu5ab_scan_year }}
    }}''' for phase in range(1, 9))
    effects += f'''\neu5ab_batch_rgo_migrate_attempts = {{
        if = {{ limit = {{ has_variable = eu5ab_scan_month has_variable = eu5ab_scan_year }}
            save_scope_as = eu5ab_rgo_resume_country {migration}
        }}
    }}\n'''
    for name in ('eu5ab_recover_runtime_after_load', 'eu5ab_resume_saved_queue'):
        effects = effects.replace(name + ' = {', name + ' = {\n    eu5ab_migrate_rgo_pending_registry = yes\n    eu5ab_batch_rgo_migrate_attempts = yes', 1)
    # Batch-schema saves never publish another legacy token. Retire an in-flight
    # old request before entering the synchronous phase dispatcher.
    effects = effects.replace('eu5ab_batch_retire_cost_requests = yes',
        'eu5ab_batch_retire_cost_requests = yes\n        eu5ab_clear_queue_bridge = yes', 1)
    effects = effects.replace('if = { limit = { has_variable_list = eu5ab_bridge_unread_rgos } eu5ab_dispatch_legacy_queue_bridge = yes }',
        '''if = { limit = { has_variable_list = eu5ab_bridge_unread_rgos
            NOT = { AND = { has_variable = eu5ab_batch_rgo_done_phase var:eu5ab_batch_rgo_done_phase = var:eu5ab_q_phase } } } eu5ab_batch_rgo_run = yes }''', 1)
    for name in ('eu5ab_batch_close', 'eu5ab_batch_resume'):
        effects = effects.replace(name + ' = {', name + ' = {\n    save_scope_as = eu5ab_engine_country eu5ab_batch_rgo_close = yes', 1)
    name = 'eu5ab_process_script_rgo_queue'
    legacy = block(effects, name)
    effects = replace(effects, name, name + ' = {\n    if = { limit = { NOT = { has_variable = eu5ab_batch_schema } }\n' +
                      legacy[len(name + ' = {'):-1] + '\n    }\n}')
    name = 'eu5ab_gui_bridge_rgo'
    old = block(guis, name).replace('effect = {', 'effect = {\n    if = { limit = { scope:eu5ab_engine_country = { NOT = { has_variable = eu5ab_batch_schema } } }', 1)
    guis = replace(guis, name, old[:-1] + '}\n}')
    return effects, triggers, guis, widget
