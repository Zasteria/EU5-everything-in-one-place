"""Derived market/good indexes for ordinary batch score invalidation.

The country owns numeric candidate IDs; markets and IDs never own variables.
Quote net quantities remain fixed while indexed. The phase pool is authoritative;
load, phase changes, or quote invalidation discard/rebuild this lookup.
"""


def render(goods):
    from .construction_batch import COUNTRY, LOCATION

    row = 'scope:eu5ab_batch_index_id'
    market = 'scope:eu5ab_batch_index_market'
    kind = 'scope:eu5ab_batch_index_type'
    refresh = 'scope:eu5ab_batch_refresh_id'
    insert, collect, clear = [], [], []
    for good in goods:
        head = f'eu5ab_batch_score_head_{good}'
        next_row = f'eu5ab_batch_score_next_{good}'
        clear += [f'clear_variable_map = {head}', f'clear_variable_map = {next_row}']
        # A nonzero end sentinel also survives engines that erase numeric zero.
        insert.append(f'''if = {{ limit = {{
            is_key_in_variable_map = {{ name = eu5ab_quote_net_output_{good} target = {kind} }}
            "variable_map(eu5ab_quote_net_output_{good}|{kind})" > 0 }}
            {COUNTRY} = {{
                add_to_variable_map = {{ name = {next_row} key = {row} value = {{ value = -1
                    if = {{ limit = {{ is_key_in_variable_map = {{ name = {head} target = {market} }} }}
                        value = "variable_map({head}|{market})" }} }} }}
                add_to_variable_map = {{ name = {head} key = {market} value = {row} }}
            }}
        }}''')
        collect.append(f'''if = {{ limit = {{ OR = {{
            {LOCATION}.eu5ab_batch_quote_net_output_{good} > 0
            {LOCATION}.eu5ab_batch_quote_net_input_{good} > 0 }}
            is_key_in_variable_map = {{ name = {head} target = scope:eu5ab_batch_market }} }}
            set_local_variable = {{ name = eu5ab_batch_score_cursor value = "variable_map({head}|scope:eu5ab_batch_market)" }}
            while = {{ count = 100000 limit = {{ local_var:eu5ab_batch_score_cursor > 0 }}
                save_scope_value_as = {{ name = eu5ab_batch_refresh_id value = local_var:eu5ab_batch_score_cursor }}
                set_local_variable = {{ name = eu5ab_batch_score_cursor value = "variable_map({next_row}|{refresh})" }}
                if = {{ limit = {{ OR = {{ "variable_map(eu5ab_batch_status|{refresh})" = 1
                    "variable_map(eu5ab_batch_status|{refresh})" = 8 }}
                    NOT = {{ is_key_in_variable_map = {{ name = eu5ab_batch_score_seen target = {refresh} }} }} }}
                    add_to_variable_map = {{ name = eu5ab_batch_score_seen key = {refresh} value = 1 }}
                    add_to_variable_list = {{ name = eu5ab_batch_score_dirty target = {refresh} }}
                }}
            }}
        }}''')
    return f'''eu5ab_batch_clear_score_index = {{
        remove_variable = eu5ab_batch_score_index_ready
        {' '.join(clear)}
        clear_variable_map = eu5ab_batch_score_seen clear_variable_list = eu5ab_batch_score_dirty
    }}
    eu5ab_batch_index_score_candidate = {{
        "variable_map(eu5ab_batch_market|{row})" = {{ save_scope_as = eu5ab_batch_index_market }}
        "variable_map(eu5ab_batch_type|{row})" = {{ save_scope_as = eu5ab_batch_index_type }}
        "variable_map(eu5ab_batch_location|{row})" = {{ {' '.join(insert)} }}
    }}
    eu5ab_batch_ensure_score_index = {{
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_batch_score_index_ready }} }}
            eu5ab_batch_clear_score_index = yes
            every_in_list = {{ variable = eu5ab_batch_pool
                save_scope_value_as = {{ name = eu5ab_batch_index_id value = this }}
                {COUNTRY} = {{ eu5ab_batch_index_score_candidate = yes }}
            }}
            set_variable = eu5ab_batch_score_index_ready
        }}
    }}
    eu5ab_batch_collect_score_changes = {{
        eu5ab_batch_ensure_score_index = yes
        clear_variable_map = eu5ab_batch_score_seen clear_variable_list = eu5ab_batch_score_dirty
        {' '.join(collect)}
        remove_local_variable = eu5ab_batch_score_cursor
        clear_variable_map = eu5ab_batch_score_seen
    }}
    '''
