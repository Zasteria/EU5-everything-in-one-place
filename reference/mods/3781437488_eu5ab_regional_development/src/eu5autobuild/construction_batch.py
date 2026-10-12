"""Monthly native snapshots and finite, ordered construction batches.

Country maps own monotonic project IDs. Location fields are invocation scratch,
never the identity of an approval. A native command and its two treasury reads
are synchronous; the batch reducer cannot issue another command for that ID.
Legacy GUI work remains readable solely for interrupted pre-batch saves.
"""
from . import recipe_snapshot, queue_bridge, construction_ledger, batch_score_index, batch_backfill
from .food_infrastructure import FOOD_BUILDING_FINAL_GATES, GRANARY_BUILDINGS
from .production_goods import goods_in
from .rgo_pending import DEMAND_BUFFER_RATIO
from .script_syntax import lower_map_formulas

ID = 'scope:eu5ab_batch_id'
COUNTRY = 'scope:eu5ab_engine_country'
LOCATION = 'scope:eu5ab_candidate_location'
TYPE = 'scope:eu5ab_candidate_building'
# The price-adjusted tail already includes the original base and labor stages.
# Restoring just these consumers keeps pending arithmetic live, without
# materializing unused intermediate snapshots after screening.
FROZEN = ('eu5ab_price_adjusted_candidate_score', 'eu5ab_candidate_capacity_factor')
OPEN = '''has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes
    NOT = { has_variable = eu5ab_scan_resume_after_load }
    has_variable = eu5ab_batch_schema'''


def read(field):
    return f'"variable_map(eu5ab_batch_{field}|{ID})"'


def write(field, value):
    return f'add_to_variable_map = {{ name = eu5ab_batch_{field} key = {ID} value = {value} }}'


def country_read(field):
    return f'"{COUNTRY}.variable_map(eu5ab_batch_{field}|{ID})"'


def increment(name):
    return f'''set_variable = {{ name = {name} value = {{ value = 0
        if = {{ limit = {{ has_variable = {name} }} add = var:{name} }} add = 1 }} }}'''


def quote(field):
    return f'"variable_map(eu5ab_quote_{field}|{TYPE})"'


def location_quote(field):
    return f'"{LOCATION}.variable_map(eu5ab_quote_{field}|{TYPE})"'


def quote_write(field, value):
    return f'add_to_variable_map = {{ name = eu5ab_quote_{field} key = {TYPE} value = {value} }}'


def map_value(name, key):
    return f'{{ value = 0 if = {{ limit = {{ is_key_in_variable_map = {{ name = {name} target = {key} }} }} add = "variable_map({name}|{key})" }} }}'


def data_fields(models, rules):
    goods = goods_in(models, rules)
    return tuple(f'{kind}_{good}' for good in goods
                 for kind in ('net_output', 'net_input', 'old_output', 'old_input'))


def render_values(models, demands, rules):
    from .rgo_automation import raw_goods
    raw = set(raw_goods())
    fields = ('score', 'rank_base', 'adjusted_profit', 'kind', 'emergency', 'food_emergency', 'pending_open', 'need',
              'efficiency', *FROZEN, *data_fields(models, rules))
    values = '\n'.join(f'eu5ab_batch_quote_{f} = {{ value = {map_value("eu5ab_quote_" + f, TYPE)} }}'
                       for f in fields)
    values += f'''\neu5ab_batch_order = {{ value = 0 {COUNTRY} = {{ add = "variable_map(eu5ab_batch_score|prev)" }} }}
eu5ab_batch_quote_order = {{ value = 0 {LOCATION} = {{ add = "variable_map(eu5ab_quote_score|prev)" }} }}
eu5ab_batch_slots_value = {{ value = 0 if = {{ limit = {{ has_variable = eu5ab_batch_slots }} add = var:eu5ab_batch_slots }} }}
eu5ab_batch_reserved_value = {{ value = 0 if = {{ limit = {{ has_variable = eu5ab_batch_reserved }} add = var:eu5ab_batch_reserved }} }}
eu5ab_batch_planned_value = {{ value = 0 if = {{ limit = {{ has_variable = eu5ab_batch_planned }} add = var:eu5ab_batch_planned }} }}
eu5ab_batch_market_generation_value = {{ value = {map_value('eu5ab_batch_market_generation', 'scope:eu5ab_batch_market')} }}
'''
    for good in goods_in(models, rules):
        # Freeze market demand/supply once. Pending production remains a shared
        # mutable ledger; starting a batch never walks all registered projects.
        rgo_pending = (f"add = {map_value('eu5ab_rgo_pending_output_' + good, LOCATION + '.var:eu5ab_pending_approval_market')}"
                       if good in raw else '')
        values += f'''eu5ab_market_effective_demand_{good}_snapshot = {{ value = 0 {LOCATION}.owner = {{
            add = {map_value('eu5ab_batch_eu5ab_market_effective_demand_' + good, LOCATION + '.var:eu5ab_pending_approval_market')}
            add = {map_value('eu5ab_batch_input_delta_' + good, LOCATION + '.var:eu5ab_pending_approval_market')}
        }} }}
eu5ab_market_pending_limit_{good}_snapshot = {{ value = eu5ab_market_effective_demand_{good}_snapshot
    {LOCATION}.owner = {{ subtract = {map_value('eu5ab_batch_supply_' + good, LOCATION + '.var:eu5ab_pending_approval_market')} }}
    min = 0 add = {{ value = eu5ab_market_effective_demand_{good}_snapshot multiply = {DEMAND_BUFFER_RATIO:g} }}
}}
eu5ab_market_pending_{good}_snapshot = {{ value = 0 {LOCATION}.owner = {{
    add = {map_value('eu5ab_batch_output_' + good, LOCATION + '.var:eu5ab_pending_approval_market')}
    {rgo_pending}
}} }}\n'''
    for good in sorted({g for d in demands.values() for g, n in d.goods.items() if n > 0}):
        values += f'''eu5ab_batch_material_need_{good} = {{ value = {map_value('eu5ab_quote_material_' + good, TYPE)} }}
eu5ab_batch_material_remaining_{good} = {{ value = {map_value('eu5ab_batch_material_' + good, 'scope:eu5ab_batch_market')} }}\n'''
    return values + construction_ledger.values()


def render_quote_quantities(models, rules):
    """Snapshot only recipe-reachable goods, keeping absent map entries zero.

    Net quantities cannot be positive for a good absent from the target recipe.
    Old quantities use the actual predecessor's type independently, so an
    old-only input/output is retained even when the target reference is unknown.
    Each type's union includes every supported production-method alternative;
    the existing live quantity readers still select the active methods.
    """
    clear = '\n'.join(
        f'remove_from_variable_map = {{ name = eu5ab_quote_{field} key = {TYPE} }}'
        for field in data_fields(models, rules))
    cases = {'net': [], 'old': []}
    for building, model in sorted(models.items()):
        fields = [(kind, good) for kind, prop in (('output', 'outputs'), ('input', 'inputs'))
                  for good in sorted({g for slot in model.slots for method in slot
                                      for g, amount in getattr(method, prop).items() if amount > 0})]
        if not fields:
            continue
        for role in cases:
            writes = ' '.join(quote_write(f'{role}_{kind}_{good}',
                                         f'{TYPE}.eu5ab_candidate_{role}_{kind}_{good}')
                              for kind, good in fields)
            cases[role].append(f'building_type:{building} = {{ {writes} }}')
    return f'''eu5ab_batch_snapshot_quote_quantities = {{
        # Clear only this candidate's keys, including legacy dense snapshots and
        # an earlier predecessor. Missing entries are read as zero downstream.
        {clear}
        if = {{ limit = {{ {TYPE} = {{ eu5ab_pending_identity_known = yes }} }}
            switch = {{ trigger = {TYPE} {' '.join(cases['net'])} }}
        }}
        if = {{ limit = {{ {TYPE} = {{ eu5ab_pending_exact_predecessor = yes }} }}
            switch = {{ trigger = scope:eu5ab_engine_replaced_building.building_type
                {' '.join(cases['old'])}
            }}
        }}
    }}
'''


def render_material_snapshot(demands):
    """Location scope: one type dispatch replaces one catalog walk per good."""
    materials = sorted({g for demand in demands.values() for g, amount in demand.goods.items() if amount > 0})
    clear = '\n'.join(f'remove_from_variable_map = {{ name = eu5ab_quote_material_{g} key = {TYPE} }}'
                      for g in materials)
    cases = []
    for building, demand in sorted(demands.items()):
        writes = ' '.join(quote_write('material_' + good, f'{amount:g}')
                          for good, amount in sorted(demand.goods.items()) if amount > 0)
        if writes:
            cases.append(f'building_type:{building} = {{ {writes} }}')
    return f'''eu5ab_batch_snapshot_quote_materials = {{
    # Clear the current type only, including old dense or reloaded snapshots.
    # Downstream material readers already treat a missing key as numeric zero.
    {clear}
    switch = {{ trigger = {TYPE} {' '.join(cases)} }}
}}
'''


def render_screening(models, demands, rules):
    goods = goods_in(models, rules)
    materials = sorted({g for d in demands.values() for g, n in d.goods.items() if n > 0})
    snapshots = '\n'.join(quote_write(v, 'prev.' + v) for v in FROZEN)
    quantities = 'eu5ab_batch_snapshot_quote_quantities = yes'
    init_material = '\n'.join(f'''
        add_to_variable_map = {{ name = eu5ab_batch_material_{g} key = scope:eu5ab_batch_market value = {{
            value = "scope:eu5ab_batch_market.goods_supply_in_market(goods:{g})"
            multiply = eu5ab_construction_shortage_factor
            subtract = "scope:eu5ab_batch_market.goods_demand_in_market(goods:{g})"
        }} }}
        if = {{ limit = {{ "scope:eu5ab_batch_market.market_price(goods:{g})" <= {{
            value = "default_price(goods:{g})" multiply = {rules.thresholds.construction_price_ceiling_ratio:g} }} }}
            add_to_variable_map = {{ name = eu5ab_batch_price_{g} key = scope:eu5ab_batch_market value = 1 }} }}'''
        for g in materials)
    init_economy = '\n'.join(f'''add_to_variable_map = {{ name = eu5ab_batch_eu5ab_market_effective_demand_{g}
        key = scope:eu5ab_batch_market value = {TYPE}.eu5ab_market_effective_demand_{g} }}
        add_to_variable_map = {{ name = eu5ab_batch_supply_{g} key = scope:eu5ab_batch_market
            value = "scope:eu5ab_batch_market.goods_supply_in_market(goods:{g})" }}
        add_to_variable_map = {{ name = eu5ab_batch_output_{g} key = scope:eu5ab_batch_market
            value = {map_value('eu5ab_build_pending_' + g, 'scope:eu5ab_batch_market')} }}
        if = {{ limit = {{ {TYPE} = {{ eu5ab_market_pending_known_{g} = yes }} }}
            add_to_variable_map = {{ name = eu5ab_batch_pending_known_{g} key = scope:eu5ab_batch_market value = 1 }} }}'''
        for g in goods)
    def reject(counter):
        return f'else = {{ {COUNTRY} = {{ {increment(counter)} }} }}'

    # Count the first gate that actually rejected this quote. Keep expensive
    # snapshots lazy, and let the quote callback's completion guard deduplicate.
    food_open = '\n'.join(f'if = {{ limit = {{ {TYPE} = {{ {gate} = yes }} }}'
                          for gate, _ in FOOD_BUILDING_FINAL_GATES)
    food_close = '\n'.join('} ' + reject(counter)
                           for _, counter in reversed(FOOD_BUILDING_FINAL_GATES))
    return render_quote_quantities(models, rules) + render_material_snapshot(demands) + f'''eu5ab_batch_screen_quote = {{
    save_scope_as = eu5ab_candidate_location
    eu5ab_clear_quote_production_snapshot = yes
    eu5ab_clear_recipe_score_snapshot = yes
    remove_variable = eu5ab_pf_reference_building
    owner = {{ save_scope_as = eu5ab_engine_country
        remove_variable = eu5ab_batch_score_index_ready
        if = {{ limit = {{ NOT = {{ AND = {{ has_variable = eu5ab_batch_ledger_month has_variable = eu5ab_batch_ledger_year
            var:eu5ab_batch_ledger_month = var:eu5ab_scan_month var:eu5ab_batch_ledger_year = var:eu5ab_scan_year }} }} }}
            eu5ab_batch_reset_ledgers = yes
            set_variable = {{ name = eu5ab_batch_ledger_month value = var:eu5ab_scan_month }}
            set_variable = {{ name = eu5ab_batch_ledger_year value = var:eu5ab_scan_year }}
        }}
    }}
    remove_variable = eu5ab_batch_quote_restored
    if = {{ limit = {{ NOT = {{ AND = {{ has_variable = eu5ab_batch_failure_month has_variable = eu5ab_batch_failure_year
        exists = var:eu5ab_batch_failure_country owner = var:eu5ab_batch_failure_country
        var:eu5ab_batch_failure_month = owner.var:eu5ab_scan_month var:eu5ab_batch_failure_year = owner.var:eu5ab_scan_year }} }} }}
        clear_variable_list = eu5ab_batch_failed_types
        set_variable = {{ name = eu5ab_batch_failure_country value = owner }}
        set_variable = {{ name = eu5ab_batch_failure_month value = owner.var:eu5ab_scan_month }}
        set_variable = {{ name = eu5ab_batch_failure_year value = owner.var:eu5ab_scan_year }}
    }}
    if = {{ limit = {{ exists = market }}
    market = {{ save_scope_as = eu5ab_batch_market }}
    {quote_write('market', 'market')} {quote_write('province', 'province')}
    if = {{ limit = {{ eu5ab_food_emergency_enabled = yes }} {quote_write('food_emergency', '1')} }}
    owner = {{ if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_markets target = scope:eu5ab_batch_market }} }} }}
        {init_material}
        {init_economy}
        add_to_variable_map = {{ name = eu5ab_batch_market_generation key = scope:eu5ab_batch_market value = 1 }}
        add_to_variable_list = {{ name = eu5ab_batch_markets target = scope:eu5ab_batch_market }}
    }} }}
    eu5ab_batch_slots_ensure = yes
    # Native permission, cost and the captured candidate-specific capacity
    # already include replacement/special-building exemptions.
    if = {{ limit = {{ exists = scope:eu5ab_engine_can_build scope:eu5ab_engine_can_build = yes }}
    if = {{ limit = {{ scope:eu5ab_engine_cost > 0 }}
    if = {{ limit = {{ eu5ab_cached_quote_capacity_factor > 0 }}
    scope:eu5ab_candidate_building = {{ eu5ab_prepare_recipe_screen_snapshot = yes }}
    if = {{ limit = {{ {TYPE} = {{ eu5ab_inputs_available = yes }} }}
    scope:eu5ab_candidate_building = {{
        # Reuse the monthly market x good snapshot prepared by ordinary workers;
        # a missing entry is populated once here before the quote filter reads it.
        eu5ab_prepare_candidate_market_prices = yes
        eu5ab_prepare_candidate_filter_prices = yes
    }}
    if = {{ limit = {{ {TYPE} = {{ eu5ab_output_not_oversupplied = yes }} }}
    {food_open}
    set_variable = eu5ab_quote_production_active
    eu5ab_prepare_production_reference = yes
    eu5ab_prepare_quote_production_snapshot = yes
    eu5ab_prepare_quote_production_output_quantities = yes
    if = {{ limit = {{ {TYPE} = {{ eu5ab_candidate_pending_allowed = yes }} }}
    eu5ab_prepare_quote_economy_snapshot = yes
    {quote_write('adjusted_profit', 'eu5ab_engine_adjusted_profit')}
    if = {{ limit = {{ OR = {{ {TYPE}.eu5ab_recipe_expected_output_value <= 0
            eu5ab_engine_candidate_passes_selected_metric = yes eu5ab_engine_candidate_has_emergency_demand = yes }}
    }}
    eu5ab_prepare_quote_production_input_quantities = yes
    if = {{ limit = {{ {TYPE} = {{ eu5ab_pending_identity_known = yes }} }} {quote_write('identity_known', '1')} }}
    eu5ab_batch_snapshot_quote_materials = yes
    scope:eu5ab_candidate_building = {{ eu5ab_prepare_candidate_score_snapshot = yes
        {LOCATION} = {{
            {snapshots}
            {quantities}
            {quote_write('efficiency', '0')}
            if = {{ limit = {{ exists = var:eu5ab_pf_reference_building }}
                {quote_write('reference', 'var:eu5ab_pf_reference_building')}
                {quote_write('efficiency', '{ value = 0 if = { limit = { has_variable = eu5ab_quote_production_reference_efficiency } add = var:eu5ab_quote_production_reference_efficiency } }')}
            }}
            {quote_write('kind', '3')}
            if = {{ limit = {{ {TYPE} = {{ eu5ab_candidate_replaces_existing_building = yes }} }} {quote_write('kind', '2')} }}
            else_if = {{ limit = {{ {TYPE} = {{ eu5ab_candidate_is_expansion = yes }} }} {quote_write('kind', '4')} }}
            if = {{ limit = {{ eu5ab_engine_candidate_has_emergency_demand = yes }} {quote_write('emergency', '1')} }}
            {quote_write('pending_open', '1')}
            add_to_variable_list = {{ name = eu5ab_batch_passed_types target = {TYPE} }}
        }}
    }}
    eu5ab_batch_compute_quote_score = yes
    {quote_write('need', TYPE + '.eu5ab_universal_need_score')}
    {quote_write('ledger_generation', COUNTRY + '.eu5ab_batch_market_generation_value')}
    }} {reject('eu5ab_diag_fail_engine_economics')}
    }} {reject('eu5ab_diag_fail_pending_output')}
    {food_close}
    }} {reject('eu5ab_diag_fail_oversupply')}
    }} {reject('eu5ab_diag_fail_inputs')}
    }} else = {{
        if = {{ limit = {{ has_variable = eu5ab_capacity_ready }}
            {COUNTRY} = {{ {increment('eu5ab_diag_fail_building_capacity')} }}
        }} {reject('eu5ab_diag_fail_capacity_unavailable')}
    }}
    }} {reject('eu5ab_diag_fail_engine_economics')}
    }} {reject('eu5ab_diag_fail_vanilla')}
    }} {reject('eu5ab_diag_fail_vanilla')}
    eu5ab_clear_recipe_score_snapshot = yes
    remove_variable = eu5ab_pf_reference_building
    eu5ab_clear_quote_production_snapshot = yes
    add_to_variable_list = {{ name = eu5ab_batch_screened_types target = {TYPE} }}
}}
eu5ab_batch_compute_quote_score = {{
    if = {{ limit = {{ owner.var:eu5ab_batch_ranking_mode = 2 }}
        # Exactly the existing priority/profit, labor and product-price stages.
        eu5ab_batch_compute_profit_base = yes
        {quote_write('rank_base', 'eu5ab_profit_candidate_rank_value')}
        set_variable = {{ name = eu5ab_q_profit_candidate_rank value = eu5ab_pending_profit_rank }}
        set_variable = {{ name = eu5ab_q_profit_candidate_rank value = eu5ab_cached_capacity_profit_rank }}
        {quote_write('score', 'eu5ab_profit_candidate_rank_value')}
        remove_variable = eu5ab_q_profit_candidate_rank
    }}
    else = {{
        {quote_write('rank_base', TYPE + '.eu5ab_price_adjusted_candidate_score')}
        {quote_write('score', TYPE + '.eu5ab_current_candidate_score')}
    }}
}}
'''


def render_effects(models, demands, rules, phase_count=16):
    goods = goods_in(models, rules)
    granary_type = 'OR = { ' + ' '.join(
        f'{TYPE} = building_type:{building}' for building in sorted(GRANARY_BUILDINGS)
    ) + ' }'
    materials = sorted({g for d in demands.values() for g, n in d.goods.items() if n > 0})
    restore_frozen = '\n'.join(f'''set_variable = {{ name = {recipe_snapshot.field(v.removeprefix('eu5ab_'))} value = eu5ab_batch_quote_{v} }}
        set_variable = {recipe_snapshot.field(v.removeprefix('eu5ab_'))}_ready''' for v in FROZEN)
    restore_quantities = '\n'.join(f'''add_to_variable_map = {{ name = eu5ab_pending_approval_{field} key = goods:{g}
        value = eu5ab_batch_quote_{kind}_{g} }}''' for g in goods
        for kind, field in (('net_output', 'output'), ('net_input', 'net_input'), ('old_output', 'old_output'), ('old_input', 'old_input')))
    material_checks = ' '.join(f'''trigger_if = {{ limit = {{ eu5ab_batch_material_need_{g} > 0 }}
        {COUNTRY} = {{ is_key_in_variable_map = {{ name = eu5ab_batch_price_{g} target = scope:eu5ab_batch_market }}
            eu5ab_batch_material_remaining_{g} > scope:eu5ab_candidate_location.eu5ab_batch_material_need_{g} }} }}''' for g in materials)
    def output_move(op):
        return '\n'.join(f'''add_to_variable_map = {{ name = {name}_{g} key = scope:eu5ab_batch_market value = {{
            value = {map_value(name + '_' + g, 'scope:eu5ab_batch_market')}
            {op} = {LOCATION}.eu5ab_batch_quote_{kind}_{g} min = 0 }} }}'''
            for g in goods for name, kind in (('eu5ab_batch_output', 'net_output'), ('eu5ab_batch_input_delta', 'net_input')))
    reserve_output = output_move('add')
    release_output = output_move('subtract')
    diagnostics = '\n'.join(f'''{rank} = {{
            set_variable = {{ name = eu5ab_diag_top_{rank}_kind value = 1 }}
            set_variable = {{ name = eu5ab_diag_top_{rank}_location value = {LOCATION} }}
            set_variable = {{ name = eu5ab_diag_top_{rank}_building value = {TYPE} }}
            set_variable = {{ name = eu5ab_diag_top_{rank}_priority value = var:eu5ab_q_phase }}
            set_variable = {{ name = eu5ab_diag_top_{rank}_score value = {read('score')} }}
            set_variable = {{ name = eu5ab_diag_top_{rank}_need value = {LOCATION}.eu5ab_batch_quote_need }}
            set_variable = {{ name = eu5ab_diag_top_{rank}_economic value = {{ value = {LOCATION}.eu5ab_batch_quote_adjusted_profit
                divide = {LOCATION}.eu5ab_cached_quote_cost multiply = {rules.thresholds.economic_score_scale:g} }} }}
            set_variable = {{ name = eu5ab_diag_top_{rank}_reason value = 10 }}
            remove_variable = eu5ab_diag_top_{rank}_labor_jobs remove_variable = eu5ab_diag_top_{rank}_labor_current
            remove_variable = eu5ab_diag_top_{rank}_labor_projected
    }}''' for rank in range(1, rules.cadence.candidates_per_location + 1))
    def material_move(op):
        return '\n'.join(f'''add_to_variable_map = {{ name = eu5ab_batch_material_{g} key = scope:eu5ab_batch_market value = {{
            value = eu5ab_batch_material_remaining_{g} {op} = {LOCATION}.eu5ab_batch_material_need_{g} }} }}''' for g in materials)
    derive = '\n'.join(f'''{phase} = {{ every_in_list = {{ variable = eu5ab_q_phase_{phase}_locations
        limit = {{ owner = {COUNTRY} }} save_scope_as = eu5ab_candidate_location
        eu5ab_request_candidate_quotes = yes
        every_in_list = {{ variable = eu5ab_q_phase_{phase}_types save_scope_as = eu5ab_candidate_building
            {LOCATION} = {{ if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_screened_types target = {TYPE} }} }} }}
                owner = {{ set_variable = eu5ab_batch_waiting }} }} }}
        }}
    }} }}''' for phase in range(1, phase_count + 1))
    collect = '\n'.join(f'''{phase} = {{ every_in_list = {{ variable = eu5ab_q_phase_{phase}_locations
        limit = {{ owner = {COUNTRY} }} save_scope_as = eu5ab_candidate_location
        every_in_list = {{ variable = eu5ab_q_phase_{phase}_types
            save_scope_as = eu5ab_batch_refresh_type
            {LOCATION} = {{ if = {{ limit = {{ is_target_in_variable_list = {{ name = eu5ab_batch_passed_types target = scope:eu5ab_batch_refresh_type }} }}
                save_scope_as = eu5ab_batch_refresh_location
                scope:eu5ab_batch_refresh_type = {{ save_scope_as = eu5ab_candidate_building }}
                {quote('market')} = {{ save_scope_as = eu5ab_batch_market }}
                if = {{ limit = {{ NOT = {{ "variable_map(eu5ab_quote_ledger_generation|scope:eu5ab_batch_refresh_type)" = {COUNTRY}.eu5ab_batch_market_generation_value }} }}
                    eu5ab_batch_refresh_quote_pending = yes }}
            }} }}
        }}
        {batch_backfill.prepare(phase)}
        ordered_in_list = {{ variable = eu5ab_batch_primary_types order_by = eu5ab_batch_quote_order
            max = 100000 check_range_bounds = no
            limit = {{ {LOCATION} = {{ is_target_in_variable_list = {{ name = eu5ab_batch_passed_types target = prev }}
                NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_failed_types target = prev }} }}
                NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_consumed_types target = prev }} }} }} }}
            save_scope_as = eu5ab_candidate_building
            {COUNTRY} = {{ eu5ab_batch_add_candidate = yes }}
        }}
    }} }}''' for phase in range(1, phase_count + 1))
    return batch_score_index.render(goods) + batch_backfill.render(rules, phase_count) + f'''eu5ab_batch_restore_score_context = {{
    # Rank readers access frozen quote maps directly. Only physical starts
    # need the approval quantities and reference geometry copied below.
    eu5ab_clear_recipe_score_snapshot = yes
    set_variable = {{ name = eu5ab_recipe_snapshot_building value = {TYPE} }}
    {restore_frozen}
    set_variable = {{ name = eu5ab_pending_approval_market value = {quote('market')} }}
    set_variable = {{ name = eu5ab_pending_approval_country value = owner }}
    set_variable = eu5ab_batch_quote_restored
}}
eu5ab_batch_restore_quote = {{
    eu5ab_batch_restore_score_context = yes
    {restore_quantities}
    remove_variable = eu5ab_pf_reference_building
    if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_quote_reference target = {TYPE} }} }}
        set_variable = {{ name = eu5ab_pf_reference_building value = {quote('reference')} }} }}
    set_variable = {{ name = eu5ab_pf_approval_efficiency value = eu5ab_batch_quote_efficiency }}
    remove_variable = eu5ab_pf_approval_known
    if = {{ limit = {{ exists = var:eu5ab_pf_reference_building }} set_variable = eu5ab_pf_approval_known }}
    remove_variable = eu5ab_pending_predecessor remove_variable = eu5ab_pending_predecessor_before
    if = {{ limit = {{ is_key_in_variable_map = {{ name = eu5ab_quote_replaced_building target = {TYPE} }} }}
        set_variable = {{ name = eu5ab_pending_predecessor value = {quote('replaced_building')} }}
        set_variable = {{ name = eu5ab_pending_predecessor_before value = var:eu5ab_pending_predecessor.building_level }} }}
    set_variable = eu5ab_batch_quote_restored
}}
eu5ab_batch_add_candidate = {{
    set_variable = {{ name = eu5ab_batch_sequence value = {{ value = 0
        if = {{ limit = {{ has_variable = eu5ab_batch_sequence }} add = var:eu5ab_batch_sequence }} add = 1 }} }}
    save_scope_value_as = {{ name = eu5ab_batch_id value = var:eu5ab_batch_sequence }}
    {write('location', LOCATION)} {write('type', TYPE)}
    {write('market', location_quote('market'))} {write('province', location_quote('province'))}
    {write('phase', 'var:eu5ab_q_phase')}
    {write('month', 'var:eu5ab_scan_month')} {write('year', 'var:eu5ab_scan_year')}
    {write('score', LOCATION + '.eu5ab_batch_quote_score')}
    {write('cost', LOCATION + '.eu5ab_cached_quote_cost')}
    {write('status', '1')}
    {increment('eu5ab_q_processed')}
    add_to_variable_list = {{ name = eu5ab_batch_pool target = {ID} }}
    add_to_variable_list = {{ name = eu5ab_batch_records target = {ID} }}
    if = {{ limit = {{ has_variable = eu5ab_batch_score_index_ready }}
        save_scope_value_as = {{ name = eu5ab_batch_index_id value = {ID} }}
        eu5ab_batch_index_score_candidate = yes
    }}
}}
eu5ab_batch_select_context = {{
    {read('location')} = {{ save_scope_as = eu5ab_candidate_location }}
    {read('type')} = {{ save_scope_as = eu5ab_candidate_building }}
    {read('market')} = {{ save_scope_as = eu5ab_batch_market }}
    {read('province')} = {{ save_scope_as = eu5ab_batch_province }}
}}
eu5ab_batch_prepare_phase = {{
    remove_variable = eu5ab_batch_waiting
    switch = {{ trigger = var:eu5ab_q_phase {derive} }}
    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_batch_waiting }} }}
        eu5ab_batch_clear_score_index = yes
        clear_variable_list = eu5ab_batch_pool
        set_variable = {{ name = eu5ab_batch_type_limit value = var:eu5ab_global_candidates_per_location }}
        if = {{ limit = {{ var:eu5ab_batch_ranking_mode = 2 }}
            set_variable = {{ name = eu5ab_batch_type_limit value = var:eu5ab_global_actual_profit_candidates_per_location }} }}
        switch = {{ trigger = var:eu5ab_q_phase {collect} }}
        eu5ab_batch_publish_diagnostics = yes
        set_variable = {{ name = eu5ab_batch_phase value = var:eu5ab_q_phase }}
        remove_variable = eu5ab_batch_type_limit
    }}
}}
eu5ab_batch_publish_diagnostics = {{
    set_variable = {{ name = eu5ab_batch_diag_index value = 0 }}
    ordered_in_list = {{ variable = eu5ab_batch_pool order_by = eu5ab_batch_order
        max = {rules.cadence.candidates_per_location} check_range_bounds = no
        save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{ eu5ab_batch_select_context = yes
            {increment('eu5ab_batch_diag_index')}
            switch = {{ trigger = var:eu5ab_batch_diag_index {diagnostics} }}
        }}
    }}
    remove_variable = eu5ab_batch_diag_index
}}
eu5ab_batch_retire_cost_requests = {{
    # Save compatibility only. Costs are already in the initial snapshot;
    # old in-flight GUI receipts must never resume or issue construction.
    clear_variable_list = eu5ab_batch_cost_requests
    clear_variable_map = eu5ab_batch_cost_project clear_variable_map = eu5ab_batch_cost_location
    clear_variable_map = eu5ab_batch_cost_type clear_variable_map = eu5ab_batch_cost_ticket
    clear_variable_map = eu5ab_batch_cost_ready clear_variable_map = eu5ab_batch_processed
    remove_variable = eu5ab_batch_cost_day remove_variable = eu5ab_batch_retry_costs
}}
eu5ab_batch_reserve = {{
    {write('status', '2')}
    {increment('eu5ab_q_approved')}
    set_variable = {{ name = eu5ab_batch_reserved value = {{ value = eu5ab_batch_reserved_value add = 1 }} }}
    set_variable = {{ name = eu5ab_batch_planned value = {{ value = eu5ab_batch_planned_value add = {read('cost')} }} }}
    {LOCATION} = {{ eu5ab_batch_slots_reserve = yes }}
    {material_move('subtract')}
    {reserve_output}
    if = {{ limit = {{ {granary_type} }}
        add_to_variable_list = {{ name = eu5ab_batch_granaries target = scope:eu5ab_batch_province }} }}
    add_to_variable_list = {{ name = eu5ab_batch_approved target = {ID} }}
    eu5ab_batch_update_market_scores = yes
}}
eu5ab_batch_release = {{
    set_variable = {{ name = eu5ab_batch_reserved value = {{ value = eu5ab_batch_reserved_value subtract = 1 min = 0 }} }}
    set_variable = {{ name = eu5ab_batch_planned value = {{ value = eu5ab_batch_planned_value subtract = {read('cost')} min = 0 }} }}
}}
eu5ab_batch_withdraw = {{
    eu5ab_batch_release = yes
    {increment('eu5ab_q_confirmed')}
    {LOCATION} = {{ eu5ab_batch_slots_release = yes }}
    {material_move('add')}
    {release_output}
    if = {{ limit = {{ {granary_type} }}
        remove_list_variable = {{ name = eu5ab_batch_granaries target = scope:eu5ab_batch_province }} }}
    {write('status', '7')}
    eu5ab_batch_update_market_scores = yes
}}
eu5ab_batch_fail = {{
    eu5ab_batch_withdraw = yes
    {write('status', '5')}
    {LOCATION} = {{ if = {{ limit = {{ owner = {COUNTRY} }}
        add_to_variable_list = {{ name = eu5ab_batch_failed_types target = {TYPE} }} }} }}
    set_variable = {{ name = eu5ab_diag_fail_vanilla value = {{ value = 0
        if = {{ limit = {{ has_variable = eu5ab_diag_fail_vanilla }} add = var:eu5ab_diag_fail_vanilla }} add = 1 }} }}
    eu5ab_batch_update_market_scores = yes
}}
eu5ab_batch_approve = {{
    clear_variable_list = eu5ab_batch_approved
    remove_variable = eu5ab_batch_boundary
    # Greedy ranked approval: an unaffordable row does not block later rows.
    while = {{ count = 100000 limit = {{ NOT = {{ has_variable = eu5ab_batch_boundary }}
        any_in_list = {{ variable = eu5ab_batch_pool {COUNTRY} = {{ "variable_map(eu5ab_batch_status|prev)" = 1 }} }} }}
    ordered_in_list = {{ variable = eu5ab_batch_pool order_by = eu5ab_batch_order
        max = 1 check_range_bounds = no
        limit = {{ {COUNTRY} = {{ "variable_map(eu5ab_batch_status|prev)" = 1 }} }}
        save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{
            eu5ab_batch_select_context = yes
            {LOCATION} = {{ if = {{ limit = {{ owner = {COUNTRY} }} eu5ab_batch_slots_ensure = yes }} }}
            if = {{ limit = {{ {read('status')} = 1
                NOT = {{ has_variable = eu5ab_batch_boundary }}
                var:eu5ab_constructions_started_this_tick < {{ value = var:eu5ab_monthly_build_quota subtract = eu5ab_batch_reserved_value }}
                eu5ab_global_budget_remaining_value > eu5ab_batch_planned_value
                {LOCATION} = {{ owner = {COUNTRY} eu5ab_batch_slots_value > 0 eu5ab_batch_quote_pending_open > 0 {material_checks} }}
                OR = {{ NOT = {{ {granary_type} }}
                    NOT = {{ is_target_in_variable_list = {{ name = eu5ab_batch_granaries target = scope:eu5ab_batch_province }} }} }}
                gold >= {{ value = {read('cost')} add = eu5ab_batch_planned_value add = {LOCATION}.eu5ab_current_min_cash_reserve }}
            }}
                if = {{ limit = {{ eu5ab_global_budget_remaining_value >= {{ value = eu5ab_batch_planned_value add = {read('cost')} }} }}
                    eu5ab_batch_reserve = yes
                }}
                else_if = {{ limit = {{ eu5ab_batch_reserved_value = 0 }}
                    eu5ab_batch_reserve = yes set_variable = eu5ab_batch_boundary
                }}
                else = {{ set_variable = eu5ab_batch_boundary }}
            }}
            else_if = {{ limit = {{ {read('status')} = 1 NOT = {{ has_variable = eu5ab_batch_boundary }} }}
                if = {{ limit = {{ eu5ab_batch_reserved_value > 0 }} {write('status', '8')} }}
                else = {{ {write('status', '7')} }}
            }}
        }}
    }}
    }}
}}
eu5ab_batch_issue = {{
    every_in_list = {{ variable = eu5ab_batch_approved
        save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{
            eu5ab_batch_select_context = yes
            if = {{ limit = {{ {read('status')} = 2 }}
            if = {{ limit = {{ {OPEN} eu5ab_global_budget_remaining_value > 0
                {LOCATION} = {{ owner = {COUNTRY} }}
                gold >= {{ value = eu5ab_batch_planned_value add = {LOCATION}.eu5ab_current_min_cash_reserve }}
            }}
                {write('status', '3')} {increment('eu5ab_q_seen')}
                {LOCATION} = {{
                    eu5ab_batch_restore_quote = yes
                    set_variable = {{ name = eu5ab_q_type_queue_before value = eu5ab_candidate_queued_levels }}
                    set_variable = {{ name = eu5ab_q_type_level_before value = eu5ab_candidate_completed_levels }}
                    set_variable = {{ name = eu5ab_q_approved_build_kind value = eu5ab_batch_quote_kind }}
                    eu5ab_pf_capture_start_geometry = yes
                    {COUNTRY} = {{
                        {write('queue_before', LOCATION + '.eu5ab_candidate_queued_levels')}
                        {write('levels_before', LOCATION + '.eu5ab_candidate_completed_levels')}
                    }}
                    # One item, one synchronous treasury delta. Never charge gold again.
                    set_local_variable = {{ name = eu5ab_batch_gold_before value = owner.gold }}
                    construct_building = {{ building_type = {TYPE} cost_multiplier = 1 instant = no
                        owner = {COUNTRY} payer = {COUNTRY} }}
                    set_local_variable = {{ name = eu5ab_batch_debit value = {{ value = local_var:eu5ab_batch_gold_before subtract = owner.gold min = 0 }} }}
                    if = {{ limit = {{ OR = {{ eu5ab_candidate_queued_levels > {country_read('queue_before')}
                        eu5ab_candidate_completed_levels > {country_read('levels_before')} }} }}
                        # Geometry enrollment must precede another same-type command.
                        eu5ab_record_confirmed_building = yes eu5ab_pf_confirm_start = yes
                        eu5ab_record_queue_start_location = yes
                        eu5ab_batch_slots_commit = yes
                        {COUNTRY} = {{
                            {write('debit', 'local_var:eu5ab_batch_debit')}
                            {write('status', '4')}
                            set_local_variable = {{ name = eu5ab_budget_charge value = local_var:eu5ab_batch_debit }}
                            eu5ab_charge_annual_budget = yes eu5ab_batch_release = yes
                            set_variable = {{ name = eu5ab_constructions_started_this_tick value = {{ value = 0
                                if = {{ limit = {{ has_variable = eu5ab_constructions_started_this_tick }} add = var:eu5ab_constructions_started_this_tick }} add = 1 }} }}
                        }}
                        set_variable = eu5ab_action_taken set_variable = eu5ab_batch_backfill_started
                        remove_variable = eu5ab_failure_cooldown
                        if = {{ limit = {{ NOT = {{ eu5ab_batch_quote_kind = 4 }} }}
                            add_to_variable_list = {{ name = eu5ab_batch_consumed_types target = {TYPE} }} }}
                    }}
                    else = {{ {COUNTRY} = {{ eu5ab_batch_fail = yes }} }}
                    eu5ab_clear_recipe_score_snapshot = yes remove_variable = eu5ab_batch_quote_restored
                    remove_local_variable = eu5ab_batch_gold_before remove_local_variable = eu5ab_batch_debit
                }}
            }}
            else = {{ eu5ab_batch_withdraw = yes }}
            }}
        }}
    }}
    eu5ab_batch_confirm = yes
    every_in_list = {{ variable = eu5ab_batch_pool save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{ if = {{ limit = {{ {read('status')} = 8 }} {write('status', '1')} }} }}
    }}
}}
eu5ab_batch_confirm = {{
    every_in_list = {{ variable = eu5ab_batch_approved
        save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
        {COUNTRY} = {{ if = {{ limit = {{ {read('status')} = 4 }}
            eu5ab_batch_select_context = yes
            {write('status', '6')}
            {increment('eu5ab_q_confirmed')}
            set_variable = {{ name = eu5ab_diag_built_this_run value = 1 }}
            set_variable = {{ name = eu5ab_diag_last_build_location value = {LOCATION} }}
            set_variable = {{ name = eu5ab_diag_last_building value = {TYPE} }}
            set_variable = {{ name = eu5ab_diag_last_actual_cost value = {read('debit')} }}
            set_variable = {{ name = eu5ab_diag_last_actual_income value = {LOCATION}.eu5ab_cached_quote_income }}
            set_variable = {{ name = eu5ab_diag_last_actual_profit value = {LOCATION}.eu5ab_batch_quote_adjusted_profit }}
            set_variable = {{ name = eu5ab_diag_last_build_kind value = {LOCATION}.eu5ab_batch_quote_kind }}
            {increment('eu5ab_diag_active_mod_projects')}
            if = {{ limit = {{ {LOCATION}.eu5ab_batch_quote_emergency > 0 }} {increment('eu5ab_diag_emergency_overrides_used')} }}
            if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_active_project_locations target = {LOCATION} }} }} }}
                add_to_variable_list = {{ name = eu5ab_active_project_locations target = {LOCATION} }} }}
            {LOCATION} = {{ eu5ab_report_candidate_confirmed = yes }}
            # An expansion may allocate a NEW ID for a later pass. The old ID
            # stays settled even if a stale callback arrives in another month.
            if = {{ limit = {{ {OPEN} NOT = {{ has_variable = eu5ab_batch_closing }} eu5ab_global_budget_remaining_value > 0
                {LOCATION}.eu5ab_batch_quote_kind = 4 {LOCATION}.eu5ab_batch_slots_value > 0
                var:eu5ab_constructions_started_this_tick < var:eu5ab_monthly_build_quota }}
                {LOCATION} = {{ save_scope_as = eu5ab_batch_refresh_location }}
                {TYPE} = {{ save_scope_as = eu5ab_batch_refresh_type }}
                {LOCATION} = {{ eu5ab_batch_refresh_quote_pending = yes }}
                if = {{ limit = {{ {LOCATION}.eu5ab_batch_quote_pending_open > 0 }} eu5ab_batch_add_candidate = yes }}
            }}
        }} }}
    }}
    clear_variable_list = eu5ab_batch_approved
}}
eu5ab_batch_update_market_scores = {{
    # Only retained candidates in the changed market. Restore frozen labor,
    # recipe and price stages; recalculate just the shared pending coefficient.
    add_to_variable_map = {{ name = eu5ab_batch_market_generation key = scope:eu5ab_batch_market
        value = {{ value = eu5ab_batch_market_generation_value add = 1 }} }}
    eu5ab_batch_collect_score_changes = yes
    every_in_list = {{ variable = eu5ab_batch_score_dirty
        save_scope_value_as = {{ name = eu5ab_batch_refresh_id value = this }}
        {COUNTRY} = {{ if = {{ limit = {{ OR = {{ "variable_map(eu5ab_batch_status|scope:eu5ab_batch_refresh_id)" = 1 "variable_map(eu5ab_batch_status|scope:eu5ab_batch_refresh_id)" = 8 }}
            "variable_map(eu5ab_batch_market|scope:eu5ab_batch_refresh_id)" = scope:eu5ab_batch_market }}
            "variable_map(eu5ab_batch_location|scope:eu5ab_batch_refresh_id)" = {{
                if = {{ limit = {{ owner = {COUNTRY} }}
                    save_scope_as = eu5ab_batch_refresh_location
                    "scope:eu5ab_engine_country.variable_map(eu5ab_batch_type|scope:eu5ab_batch_refresh_id)" = {{ save_scope_as = eu5ab_batch_refresh_type }}
                    eu5ab_batch_refresh_quote_pending = yes
                    {COUNTRY} = {{ add_to_variable_map = {{ name = eu5ab_batch_score key = scope:eu5ab_batch_refresh_id
                        value = scope:eu5ab_batch_refresh_location.eu5ab_batch_quote_score }} }}
                }}
            }}
        }} }}
    }}
    clear_variable_list = eu5ab_batch_score_dirty
}}
eu5ab_dispatch_construction_batch = {{
    if = {{ limit = {{ {OPEN} NOT = {{ has_variable = eu5ab_batch_running }} }}
        save_scope_as = actor save_scope_as = eu5ab_engine_country
        set_variable = eu5ab_batch_running
        eu5ab_batch_retire_cost_requests = yes
        remove_variable = eu5ab_batch_waiting
        # Drain ready phases and expansion successors synchronously. Each pass
        # consumes a finite candidate, a parallel slot, or advances the phase.
        while = {{ count = 100000 limit = {{ {OPEN} NOT = {{ has_variable = eu5ab_batch_waiting }} NOT = {{ has_variable = eu5ab_bridge_request }} }}
            if = {{ limit = {{ OR = {{ eu5ab_global_budget_remaining_value <= 0
                var:eu5ab_constructions_started_this_tick >= var:eu5ab_monthly_build_quota }} }}
                eu5ab_finish_engine_candidate_queue = yes
            }}
            else = {{
                if = {{ limit = {{ has_variable = eu5ab_bridge_rebuild }} eu5ab_rebuild_queue_bridge = yes }}
                if = {{ limit = {{ has_variable_list = eu5ab_bridge_unread_rgos }} eu5ab_dispatch_legacy_queue_bridge = yes }}
                else = {{
                    if = {{ limit = {{ OR = {{ NOT = {{ has_variable = eu5ab_batch_phase }} NOT = {{ var:eu5ab_batch_phase = var:eu5ab_q_phase }} }} }}
                        eu5ab_batch_prepare_phase = yes
                    }}
                    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_batch_waiting }} }}
                        eu5ab_batch_approve = yes eu5ab_batch_issue = yes
                        # Terminal rows leave the pool; they are never retried.
                        every_in_list = {{ variable = eu5ab_batch_pool save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
                            {COUNTRY} = {{ if = {{ limit = {{ {read('status')} >= 5 }}
                                if = {{ limit = {{ NOT = {{ {read('status')} = 6 }} }} eu5ab_batch_record_backfill_failure = yes }}
                                remove_list_variable = {{ name = eu5ab_batch_pool target = {ID} }} }} }}
                        }}
                        if = {{ limit = {{ NOT = {{ has_variable_list = eu5ab_batch_pool }} }} eu5ab_batch_try_backfill = yes }}
                        if = {{ limit = {{ NOT = {{ has_variable_list = eu5ab_batch_pool }} }} eu5ab_advance_engine_priority_phase = yes }}
                    }}
                }}
            }}
        }}
        remove_variable = eu5ab_batch_running
    }}
}}
    '''


def render_refresh():
    return f'''eu5ab_batch_refresh_quote_pending = {{
    # Keep the issuing context intact while visiting another candidate.
    {LOCATION} = {{ save_scope_as = eu5ab_batch_saved_location }}
    {TYPE} = {{ save_scope_as = eu5ab_batch_saved_type }}
    scope:eu5ab_batch_refresh_location = {{ save_scope_as = eu5ab_candidate_location }}
    scope:eu5ab_batch_refresh_type = {{ save_scope_as = eu5ab_candidate_building }}
    scope:eu5ab_batch_refresh_location = {{
        eu5ab_batch_restore_score_context = yes
        {quote_write('pending_open', '0')}
        if = {{ limit = {{ {TYPE}.eu5ab_candidate_pending_factor > 0 }} {quote_write('pending_open', '1')} }}
        if = {{ limit = {{ owner.var:eu5ab_batch_ranking_mode = 2 }}
            set_variable = {{ name = eu5ab_q_profit_candidate_rank value = eu5ab_batch_quote_rank_base }}
            set_variable = {{ name = eu5ab_q_profit_candidate_rank value = eu5ab_pending_profit_rank }}
            set_variable = {{ name = eu5ab_q_profit_candidate_rank value = eu5ab_cached_capacity_profit_rank }}
            {quote_write('score', 'eu5ab_profit_candidate_rank_value')}
            remove_variable = eu5ab_q_profit_candidate_rank
        }}
        else = {{ {quote_write('score', TYPE + '.eu5ab_current_candidate_score')} }}
        {quote_write('ledger_generation', COUNTRY + '.eu5ab_batch_market_generation_value')}
        eu5ab_clear_recipe_score_snapshot = yes remove_variable = eu5ab_batch_quote_restored
    }}
    scope:eu5ab_batch_saved_location = {{ save_scope_as = eu5ab_candidate_location }}
    scope:eu5ab_batch_saved_type = {{ save_scope_as = eu5ab_candidate_building }}
}}
'''


def render_guis():
    return '''# Retired callback: already queued receipts from older builds are inert.
eu5ab_gui_batch_capture_cost = {
    is_valid = { always = no }
    effect = { }
}
'''


def apply(files, root, models, demands, rules, replace):
    import re
    effects_path = root / 'in_game/common/scripted_effects/eu5ab_scripted_effects.txt'
    values_path = root / 'in_game/common/script_values/eu5ab_script_values.txt'
    guis_path = root / 'in_game/common/scripted_guis/eu5ab_scripted_guis.txt'
    triggers_path = root / 'in_game/common/scripted_triggers/eu5ab_scripted_triggers.txt'
    gui_path = root / 'in_game/gui/eu5ab_engine_queue_window.gui'
    effects = files[effects_path]
    values = files[values_path]
    block = queue_bridge._block
    # Copy the existing profit arithmetic through its price stage, unchanged.
    profit = block(effects, 'eu5ab_record_actual_profit_candidate')
    profit = profit[:profit.index('\n\tset_variable = { name = eu5ab_q_profit_candidate_rank value = eu5ab_pending_profit_rank')]
    profit = profit.replace('eu5ab_record_actual_profit_candidate', 'eu5ab_batch_compute_profit_base', 1)
    profit += '\n    remove_variable = eu5ab_q_profit_candidate_priority\n    remove_variable = eu5ab_q_profit_candidate_magnitude\n}\n'
    batch_effects = render_effects(models, demands, rules)
    effects += '\n' + profit + render_screening(models, demands, rules) + batch_effects + render_refresh()
    # Ordinary work uses batches; RGO keeps its original position and gates.
    dispatch = block(effects, 'eu5ab_dispatch_queue_bridge').replace(
        'eu5ab_dispatch_queue_bridge = {', 'eu5ab_dispatch_legacy_queue_bridge = {', 1)
    effects = replace(effects, 'eu5ab_dispatch_queue_bridge', f'''eu5ab_dispatch_queue_bridge = {{
        if = {{ limit = {{ has_variable = eu5ab_batch_schema }} eu5ab_dispatch_construction_batch = yes }}
        else = {{ eu5ab_dispatch_legacy_queue_bridge = yes }}
    }}''') + '\n' + dispatch
    # Requests are published after worker reduction, for every ranking mode.
    requests = block(effects, 'eu5ab_request_candidate_quotes').replace(
        'eu5ab_scan_month_current = yes var:eu5ab_global_candidate_ranking_mode = 2',
        'eu5ab_scan_month_current = yes OR = { has_variable = eu5ab_batch_schema var:eu5ab_global_candidate_ranking_mode = 2 }')
    requests = requests.replace('NOT = { eu5ab_quote_context_current = yes }', '''OR = {
        NOT = { eu5ab_quote_context_current = yes }
        AND = { owner = { has_variable = eu5ab_batch_schema } NOT = { var:eu5ab_batch_quote_schema = 3 } }
    }''', 1)
    requests = requests.replace('eu5ab_clear_candidate_quotes = yes', '''eu5ab_clear_candidate_quotes = yes
        # Version 1 may contain corrupted build kinds; version 2 used the old
        # capital-only granary benefit. Retire both scores and GUI receipts.
        if = { limit = { owner = { has_variable = eu5ab_batch_schema } }
            set_variable = { name = eu5ab_batch_quote_schema value = 3 } }''', 1)
    effects = replace(effects, 'eu5ab_request_candidate_quotes', requests)
    # Never truncate locations against a score computed before native quotes.
    sort = block(effects, 'eu5ab_sort_candidate_queue')
    sort = sort.replace(f'max = {rules.cadence.deep_score_location_limit}', 'max = 100000')
    effects = replace(effects, 'eu5ab_sort_candidate_queue', sort)
    for name in ('eu5ab_run_regional_development_policy', 'eu5ab_start_engine_candidate_queue'):
        effects = effects.replace(name + ' = {', name + ' = {\n    set_variable = eu5ab_batch_schema', 1)
    name = 'eu5ab_run_regional_development_policy'
    run = block(effects, name).replace('eu5ab_ensure_template_coverage = yes',
        'eu5ab_ensure_template_coverage = yes\n    set_variable = { name = eu5ab_batch_ranking_mode value = var:eu5ab_global_candidate_ranking_mode }', 1)
    effects = replace(effects, name, run)
    name = 'eu5ab_start_engine_candidate_queue'
    start = block(effects, name).replace('set_variable = eu5ab_batch_schema', '''set_variable = eu5ab_batch_schema
        if = { limit = { NOT = { has_variable = eu5ab_batch_ranking_mode } }
            set_variable = { name = eu5ab_batch_ranking_mode value = 2 }
            if = { limit = { has_variable = eu5ab_global_candidate_ranking_mode }
                set_variable = { name = eu5ab_batch_ranking_mode value = var:eu5ab_global_candidate_ranking_mode } }
        }''', 1)
    effects = replace(effects, name, start)
    # The state machine owns advancement. Late legacy pulses cannot start or
    # time out a different phase of the batch queue.
    for name in ('eu5ab_check_engine_phase_completion', 'eu5ab_check_engine_confirmation_completion',
                 'eu5ab_tick_engine_script_queue', 'eu5ab_tick_engine_script_confirmation'):
        old = block(effects, name)
        body = old[len(name + ' = {'):-1]
        effects = replace(effects, name, name + ' = {\n    if = { limit = { NOT = { has_variable = eu5ab_batch_schema } }\n' + body + '\n    }\n}')
    name = 'eu5ab_check_engine_candidate_queue_watchdog'
    body = block(effects, name)[len(name + ' = {'):-1]
    effects = replace(effects, name, f'''{name} = {{
        if = {{ limit = {{ has_variable = eu5ab_batch_schema {OPEN} }}
            save_scope_as = eu5ab_engine_country eu5ab_recover_queue_bridge = yes
        }}
        else_if = {{ limit = {{ NOT = {{ has_variable = eu5ab_batch_schema }} }} {body} }}
    }}''')
    # The RGO batch owns its slot holds and market generations. The legacy
    # single-item constructor is retained only for pre-batch compatibility.
    # Native debit is already booked, so cancellation/load/month cleanup can
    # settle results and release unissued holds without executing commands.
    field_names = ('location', 'type', 'market', 'province', 'phase', 'month', 'year', 'status', 'processed',
                   'cost', 'cost_ready', 'cost_ticket', 'score', 'debit', 'queue_before', 'levels_before',
                   'cost_project', 'cost_location', 'cost_type')
    clear = '\n'.join('clear_variable_map = eu5ab_batch_' + f for f in field_names)
    reset_ledgers = '\n'.join('clear_variable_map = eu5ab_batch_' + name for name in (
        *(f'material_{g}' for g in sorted({g for d in demands.values() for g, n in d.goods.items() if n > 0})),
        *(f'price_{g}' for g in sorted({g for d in demands.values() for g, n in d.goods.items() if n > 0})),
        *(f'{name}_{g}' for g in goods_in(models, rules) for name in ('eu5ab_market_effective_demand', 'input_delta', 'output', 'supply', 'pending_known')),
        'market_generation'))
    effects += construction_ledger.render()
    effects += f'''\neu5ab_batch_reset_ledgers = {{
        eu5ab_batch_clear_score_index = yes
        {reset_ledgers}
        clear_variable_list = eu5ab_batch_markets clear_variable_list = eu5ab_batch_granaries
    }}
    eu5ab_batch_close = {{
        save_scope_as = eu5ab_engine_country set_variable = eu5ab_batch_closing
        # Confirm successful IDs once. No recovery path calls the constructor.
        eu5ab_batch_confirm = yes
        every_in_list = {{ variable = eu5ab_batch_records save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
            {COUNTRY} = {{ if = {{ limit = {{ {read('status')} = 2 }}
                eu5ab_batch_select_context = yes eu5ab_batch_withdraw = yes
            }} }}
        }}
        {clear}
        eu5ab_batch_clear_score_index = yes
        clear_variable_list = eu5ab_batch_records clear_variable_list = eu5ab_batch_pool
        clear_variable_list = eu5ab_batch_approved clear_variable_list = eu5ab_batch_cost_requests
        # Monthly ledgers retain actual starts across refill/cancellation.
        # A new month's first screening replaces them with a fresh snapshot.
        remove_variable = eu5ab_batch_phase remove_variable = eu5ab_batch_waiting
        remove_variable = eu5ab_batch_planned remove_variable = eu5ab_batch_reserved
        remove_variable = eu5ab_batch_closing remove_variable = eu5ab_batch_cost_day
    }}\n'''
    effects = effects.replace('eu5ab_clear_engine_candidate_queue = {',
        'eu5ab_clear_engine_candidate_queue = {\n    if = { limit = { has_variable = eu5ab_batch_schema } eu5ab_batch_close = yes }', 1)
    # Same-month reload abandons old undelivered callbacks, keeping
    # screened scores, physical starts, expenditure, and monotonic IDs.
    effects += f'''\neu5ab_batch_resume = {{
        save_scope_as = eu5ab_engine_country set_variable = eu5ab_batch_closing eu5ab_batch_confirm = yes
        eu5ab_batch_clear_score_index = yes
        every_in_list = {{ variable = eu5ab_batch_pool save_scope_value_as = {{ name = eu5ab_batch_id value = this }}
            {COUNTRY} = {{
                if = {{ limit = {{ {read('status')} = 2 }} eu5ab_batch_select_context = yes eu5ab_batch_withdraw = yes }}
                else_if = {{ limit = {{ {read('status')} = 1 }} {write('status', '7')} }}
            }}
        }}
        clear_variable_list = eu5ab_batch_pool clear_variable_list = eu5ab_batch_cost_requests
        eu5ab_batch_clear_score_index = yes
        eu5ab_batch_slots_resume = yes
        remove_variable = eu5ab_batch_phase remove_variable = eu5ab_batch_waiting
        remove_variable = eu5ab_batch_closing remove_variable = eu5ab_batch_cost_day
    }}\n'''
    effects = effects.replace('eu5ab_resume_saved_queue = {',
        'eu5ab_resume_saved_queue = {\n    if = { limit = { has_variable = eu5ab_batch_schema } eu5ab_batch_resume = yes }', 1)
    extra_quote_fields = ('score', 'rank_base', 'adjusted_profit', 'kind', 'emergency', 'food_emergency', 'pending_open', 'need',
                          'market', 'province', 'ledger_generation',
                          'reference', 'efficiency', 'identity_known', *FROZEN, *data_fields(models, rules),
                          *(f'material_{g}' for g in sorted({g for d in demands.values() for g, n in d.goods.items() if n > 0})))
    effects = effects.replace('eu5ab_clear_candidate_quotes = {',
        'eu5ab_clear_candidate_quotes = {\n    owner = { remove_variable = eu5ab_batch_score_index_ready }\n' + '\n'.join('    clear_variable_map = eu5ab_quote_' + f for f in extra_quote_fields)
        + '\n    clear_variable_list = eu5ab_batch_screened_types clear_variable_list = eu5ab_batch_passed_types\n    clear_variable_list = eu5ab_batch_consumed_types\n    remove_variable = eu5ab_batch_quote_schema', 1)
    # The collection cache is cleared both before AND after worker staging.
    # Monthly labor snapshots must survive its end-of-worker cleanup.
    for name in ('eu5ab_clear_location_candidate_state',):
        effects = effects.replace(name + ' = {', name + ' = {\n    clear_variable_map = eu5ab_batch_labor_factor\n' + batch_backfill.cleanup(), 1)
    # Phase, quote and approval indexes overlap. Gather before dropping any
    # index, then clear each location exactly once; the slot ledger survives.
    name = 'eu5ab_clear_engine_candidate_queue'
    cleanup = block(effects, name)
    cleanup = cleanup.replace('eu5ab_clear_location_candidate_state = yes', 'eu5ab_batch_collect_cleanup = yes')
    cleanup = cleanup.replace('eu5ab_clear_candidate_quotes = yes', 'eu5ab_batch_collect_cleanup = yes')
    cleanup = cleanup.replace(name + ' = {', name + ''' = {
        save_scope_as = eu5ab_batch_cleanup_country clear_variable_list = eu5ab_batch_cleanup_locations''', 1)
    cleanup = cleanup[:-1] + '''
        every_in_list = { variable = eu5ab_batch_cleanup_locations eu5ab_clear_location_candidate_state = yes }
        clear_variable_list = eu5ab_batch_cleanup_locations
    }'''
    effects = replace(effects, name, cleanup)
    effects += '''\neu5ab_batch_collect_cleanup = {
        save_scope_as = eu5ab_batch_cleanup_location
        scope:eu5ab_batch_cleanup_country = {
            if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_batch_cleanup_locations target = scope:eu5ab_batch_cleanup_location } } }
                add_to_variable_list = { name = eu5ab_batch_cleanup_locations target = scope:eu5ab_batch_cleanup_location } }
        }
    }\n'''
    name = 'eu5ab_hydrate_final_building_diagnostics'
    body = block(effects, name)[len(name + ' = {'):-1]
    effects = replace(effects, name, f'''{name} = {{
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_batch_schema }} }} {body} }}
    }}''')
    # All batches see native profit/cost in the original economic score slot.
    name = 'eu5ab_recipe_economic_efficiency_score'
    values = replace(values, name, f'''{name} = {{ value = 0
        if = {{ limit = {{ {LOCATION} = {{ eu5ab_quote_context_current = yes
            is_target_in_variable_list = {{ name = eu5ab_quote_ready_types target = prev }} }}
            {LOCATION}.eu5ab_cached_quote_cost > 0 }}
            value = {LOCATION}.eu5ab_batch_quote_adjusted_profit
            divide = {LOCATION}.eu5ab_cached_quote_cost multiply = {rules.thresholds.economic_score_scale:g}
        }}
    }}''')
    # Economic score is needed inside the capture before its ready marker.
    values = values.replace('is_target_in_variable_list = { name = eu5ab_quote_ready_types target = prev }',
                            'is_key_in_variable_map = { name = eu5ab_quote_cost target = prev }')
    values += render_values(models, demands, rules)
    # Reuse the script's indirect-food calculation within this callback only.
    # Native profit/income/cost transport and the live arithmetic stay intact.
    name = 'eu5ab_engine_adjusted_profit'
    live = block(values, name).replace(name + ' = {', name + '_live = {', 1)
    values = replace(values, name, f'''{name} = {{ value = 0
        if = {{ limit = {{ {LOCATION} = {{ has_variable = eu5ab_quote_production_type
            var:eu5ab_quote_production_type = {TYPE}
            has_variable = eu5ab_quote_production_adjusted_profit_ready }} }}
            {LOCATION} = {{ if = {{ limit = {{ has_variable = eu5ab_quote_production_adjusted_profit }}
                add = var:eu5ab_quote_production_adjusted_profit }} }}
        }}
        else = {{ value = {name}_live }}
    }}''') + '\n' + live
    name = 'eu5ab_candidate_current_labor_factor_live'
    old = block(values, name).replace(name + ' = {', name + '_uncached = {', 1)
    values = replace(values, name, f'''{name} = {{ value = 1
        if = {{ limit = {{ {LOCATION} = {{ is_key_in_variable_map = {{ name = eu5ab_batch_labor_factor target = prev }} }} }}
            {LOCATION} = {{ value = "variable_map(eu5ab_batch_labor_factor|prev)" }} }}
        else = {{ value = {name}_uncached }}
    }}''') + '\n' + old
    for good in goods_in(models, rules):
        for kind in ('net_output', 'net_input', 'old_output', 'old_input'):
            name = f'eu5ab_candidate_{kind}_{good}'
            live = block(values, name).replace(name + ' = {', name + '_live = {', 1)
            values = replace(values, name, f'''{name} = {{ value = 0
                if = {{ limit = {{ {LOCATION} = {{ has_variable = eu5ab_batch_quote_restored }} }}
                    value = {LOCATION}.eu5ab_batch_quote_{kind}_{good} }}
                else = {{ value = {name}_live }}
            }}''') + '\n' + live
        for name in (f'eu5ab_market_effective_demand_{good}', f'eu5ab_market_pending_limit_{good}', f'eu5ab_market_pending_{good}'):
            live = block(values, name).replace(name + ' = {', name + '_live = {', 1)
            values = replace(values, name, f'''{name} = {{ value = 0
                if = {{ limit = {{ {LOCATION} = {{ has_variable = eu5ab_batch_quote_restored }} }} value = {name}_snapshot }}
                else = {{ value = {name}_live }}
            }}''') + '\n' + live
    guis = files[guis_path]
    capture = block(guis, 'eu5ab_gui_capture_candidate_quote')
    capture = capture.replace('eu5ab_engine_replaced_building }', 'eu5ab_engine_replaced_building eu5ab_engine_can_build }', 1)
    capture = capture.replace('add_to_variable_list = { name = eu5ab_quote_ready_types',
        'if = { limit = { owner = { has_variable = eu5ab_batch_schema } } eu5ab_batch_screen_quote = yes }\n            add_to_variable_list = { name = eu5ab_quote_ready_types', 1)
    guis = replace(guis, 'eu5ab_gui_capture_candidate_quote', capture) + render_guis()
    triggers = files[triggers_path]
    name = 'eu5ab_food_emergency_enabled'
    old = block(triggers, name)[len(name + ' = {'):-1]
    triggers = replace(triggers, name, f'''{name} = {{ OR = {{
        AND = {{ has_variable = eu5ab_batch_quote_restored eu5ab_batch_quote_food_emergency > 0 }}
        AND = {{ NOT = {{ has_variable = eu5ab_batch_quote_restored }} {old} }}
    }} }}''')
    name = 'eu5ab_pending_identity_known'
    old = block(triggers, name)[len(name + ' = {'):-1]
    triggers = replace(triggers, name, f'''{name} = {{ OR = {{
        AND = {{ {LOCATION} = {{ has_variable = eu5ab_batch_quote_restored
            is_key_in_variable_map = {{ name = eu5ab_quote_identity_known target = prev }} }} }}
        AND = {{ {LOCATION} = {{ NOT = {{ has_variable = eu5ab_batch_quote_restored }} }} {old} }}
    }} }}''')
    for good in goods_in(models, rules):
        name = f'eu5ab_market_pending_known_{good}'
        old = block(triggers, name)[len(name + ' = {'):-1]
        triggers = replace(triggers, name, f'''{name} = {{ OR = {{
            AND = {{ {LOCATION} = {{ has_variable = eu5ab_batch_quote_restored owner = {{
                is_key_in_variable_map = {{ name = eu5ab_batch_pending_known_{good} target = {LOCATION}.var:eu5ab_pending_approval_market }} }} }} }}
            AND = {{ {LOCATION} = {{ NOT = {{ has_variable = eu5ab_batch_quote_restored }} }} {old} }}
        }} }}''')
    name = 'eu5ab_candidate_pending_allowed'
    old = block(triggers, name)[len(name + ' = {'):-1]
    triggers = replace(triggers, name, f'''{name} = {{ OR = {{
        AND = {{ {LOCATION} = {{ has_variable = eu5ab_batch_quote_restored }}
            OR = {{ NOT = {{ eu5ab_candidate_has_direct_output = yes }}
                NOT = {{ eu5ab_pending_identity_known = yes }}
                AND = {{ {LOCATION} = {{ exists = market }} OR = {{
                    AND = {{ {LOCATION} = {{ eu5ab_food_emergency_enabled = yes }} eu5ab_candidate_produces_food = yes }}
                    eu5ab_candidate_output_limits_allow = yes }} }} }} }}
        AND = {{ {LOCATION} = {{ NOT = {{ has_variable = eu5ab_batch_quote_restored }} }} {old} }}
    }} }}''')
    widget = files[gui_path]
    # Screening needs the permission once; winners never reread it.
    # The early guard also carries the immutable ticket. Attach the expensive
    # permission getter only to the capture command, never to that guard.
    capture_command = re.search(
        r'on_finish = "\[GetScriptedGui\(\'eu5ab_gui_capture_candidate_quote\'\)\.Execute\([^\n]*',
        widget,
    )
    if capture_command is None:
        raise ValueError('Quote capture command is missing')
    widget = widget.replace(capture_command[0], capture_command[0].replace(
        ".AddScope('eu5ab_quote_ticket',",
        ".AddScope('eu5ab_engine_can_build', MakeScopeBool(CanBuildOrExpandBuilding(BuildingType.Self, Location.Self))).AddScope('eu5ab_quote_ticket',", 1), 1)
    from . import rgo_batch
    effects, triggers, guis, widget = rgo_batch.apply(
        effects, triggers, guis, widget, goods_in(models, rules), block, replace)
    # Lower new blocks only; preserve existing comments and formatting.
    effects = re.sub(r'(?m)^ +(?=eu5ab_(?:batch_\w+|dispatch_construction_batch) = \{)', '', effects)
    for name in re.findall(r'^(eu5ab_(?:batch_\w+|dispatch_construction_batch)) = \{', effects, re.M):
        effects = replace(effects, name, lower_map_formulas(block(effects, name)).rstrip())
    files[effects_path] = effects.rstrip() + '\n'
    files[values_path] = values
    files[guis_path] = guis
    files[triggers_path] = triggers
    files[gui_path] = widget
