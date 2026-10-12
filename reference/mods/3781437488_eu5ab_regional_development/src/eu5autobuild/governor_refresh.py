"""Resumable recommendation pass, shared by scheduled and synchronous callers."""
from __future__ import annotations

import re

from .governor_planner import script_definition


WORK = 32


def split_block(text: str, marker: str) -> tuple[str, str, str]:
    """Split one known generated block, ignoring braces in comments/strings."""
    start = text.index(marker)
    opening = text.index("{", start)
    depth = 0
    for match in re.finditer(r'#[^\n]*|"[^"\n]*"|[{}]', text[opening:]):
        token = match.group()
        if token == "{":  # nosec B105: script delimiter
            depth += 1
        elif token == "}":  # nosec B105: script delimiter
            depth -= 1
            if depth == 0:
                end = opening + match.end()
                return text[:start], text[opening + 1:end - 1], text[end:]
    raise ValueError(f"Unclosed generated block: {marker}")


def cursor_batch(cursor: str, next_var: str, body: str, count: int = WORK) -> str:
    return f'''while = {{
        limit = {{ has_variable = {cursor} }}
        count = {count}
        var:{cursor} = {{
            if = {{ limit = {{ has_variable = {next_var} }} root = {{ set_variable = {{ name = {cursor} value = prev.var:{next_var} }} }} }}
            else = {{ root = {{ remove_variable = {cursor} }} }}
{body}
        }}
    }}'''


def render_refresh_effects(shared: str, *, naval: bool = False) -> str:
    # Preserve the existing arithmetic and native scope boundaries. Only the
    # loops move into continuations; manual and automatic work use these bodies.
    baseline = script_definition(shared, "eu5ab_governor_prepare_planned_baseline_core")
    _, seed, remaining = split_block(baseline, "    every_owned_location = {")
    _, _, remaining = split_block(remaining, "    while = {")
    _, collect, _ = split_block(remaining, "    every_owned_location = {")
    seed = seed.replace("value = modifier:local_proximity_source", "value = var:eu5ab_gov_snapshot_native_source")
    candidate = script_definition(shared, "eu5ab_governor_evaluate_candidate")
    candidate_body = candidate[candidate.index("{") + 1:candidate.rindex("}")]
    start, _, rest = split_block(candidate_body, "\troot = {\n\t\twhile = {")
    # The root block contains propagation and reduction; extract the latter.
    _, root_body, _ = split_block(candidate_body[len(start):], "\troot = {")
    _, reduce, _ = split_block(root_body, "\t\tevery_in_list = {")
    reduce = re.sub(r"\s*variable = eu5ab_gov_eval_locations", "", reduce, count=1)
    finish = rest
    begin_seed = 2 if naval else 3
    kind = 2 if naval else 1
    slot_effect = "eu5ab_governor_snapshot_naval_slots" if naval else "eu5ab_governor_snapshot_local_slot_state"
    slot_prefix, slot_body, _ = split_block(script_definition(shared, slot_effect), "    every_owned_location = {" if naval else "\tevery_owned_location = {")
    slots = slot_prefix[slot_prefix.index("{") + 1:]
    building = "naval_governor" if naval else "local_governor"
    preflight = slot_body
    if not naval:
        preflight += "\n        remove_variable = eu5ab_local_cheap_score"
    preflight += f'''
        remove_variable = eu5ab_local_score
        remove_variable = eu5ab_gov_refresh_eligible
        remove_variable = eu5ab_gov_refresh_old
        if = {{ limit = {{ eu5ab_local_governor_candidate = yes }}
            set_variable = eu5ab_gov_refresh_eligible
            root = {{ change_variable = {{ name = eu5ab_gov_refresh_candidates add = 1 }} }}
        }}
        if = {{ limit = {{ has_building = building_type:{building} }}
            set_variable = eu5ab_gov_refresh_old
            root = {{ change_variable = {{ name = eu5ab_gov_refresh_seats add = 1 }} }}
        }}'''
    prepare = '''
        eu5ab_governor_clear_location_cache = yes
        eu5ab_governor_prepare_location_value = yes
        set_variable = { name = eu5ab_gov_snapshot_native_source value = modifier:local_proximity_source }
        set_variable = { name = eu5ab_gov_snapshot_source value = eu5ab_governor_current_proximity_source }
    '''
    # Preserve the DLC-adjusted charge, not just the raw Lieutenancy count.
    capacity_snapshot = ("set_variable = { name = eu5ab_gov_snapshot_other_slots value = eu5ab_governor_fresh_local_other_slots }" if not naval else "")
    prepare = "if = { limit = { owner ?= root } " + prepare + " } else = { root = { set_variable = eu5ab_gov_refresh_invalid } }"
    cheap = '''if = { limit = { has_variable = eu5ab_gov_refresh_eligible } eu5ab_governor_prepare_local_cheap_score = yes }'''
    shortlist = '''ordered_owned_location = {
        limit = { has_variable = eu5ab_gov_refresh_eligible }
        order_by = var:eu5ab_local_cheap_score
        max = 8
        check_range_bounds = no
        eu5ab_governor_append_candidate = yes
    }''' if not naval else ''
    if naval:
        cheap = "if = { limit = { has_variable = eu5ab_gov_refresh_eligible } eu5ab_governor_append_candidate = yes }"
    result = '''
        set_variable = { name = eu5ab_local_score value = var:eu5ab_gov_eval_result_gain }
        set_variable = { name = eu5ab_local_site_gain value = var:eu5ab_gov_eval_result_site_gain }
        set_variable = { name = eu5ab_local_surrounding_gain value = var:eu5ab_gov_eval_result_surrounding_gain }
        set_variable = { name = eu5ab_local_coverage value = var:eu5ab_gov_eval_result_coverage }
    '''
    validate = f'''
        if = {{ limit = {{ OR = {{
            NOT = {{ owner ?= root }}
            AND = {{ has_variable = eu5ab_gov_inputs_ready var:eu5ab_gov_snapshot_native_source != modifier:local_proximity_source }}
            AND = {{ has_variable = eu5ab_gov_refresh_old NOT = {{ has_building = building_type:{building} }} }}
            AND = {{ NOT = {{ has_variable = eu5ab_gov_refresh_old }} has_building = building_type:{building} }}
            AND = {{ has_variable = eu5ab_gov_refresh_eligible NOT = {{ eu5ab_local_governor_candidate = yes }} }}
            AND = {{ NOT = {{ has_variable = eu5ab_gov_refresh_eligible }} eu5ab_local_governor_candidate = yes }}
        }} }} root = {{ set_variable = eu5ab_gov_refresh_invalid }} }}'''
    # inputs_ready belongs to the country, not a location.
    validate = validate.replace("has_variable = eu5ab_gov_inputs_ready", "root = { has_variable = eu5ab_gov_inputs_ready }")
    return f'''
# A refresh publishes only after validation. Previous cards survive partial work.
eu5ab_governor_refresh_begin = {{
    eu5ab_governor_snapshot_transport = yes
    {slots}
    set_variable = eu5ab_governor_scan_active
    remove_variable = eu5ab_governor_dirty
    remove_variable = eu5ab_gov_inputs_ready
    remove_variable = eu5ab_gov_refresh_invalid
    remove_variable = eu5ab_gov_refresh_need_new
    remove_variable = eu5ab_gov_refresh_need_layout
    remove_variable = eu5ab_governor_baseline_failed
    remove_variable = eu5ab_governor_queue_exhausted
    remove_variable = eu5ab_layout_failed
    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_sync_runs }} }} set_variable = {{ name = eu5ab_gov_sync_runs value = 0 }} }}
    change_variable = {{ name = eu5ab_gov_sync_runs add = 1 }}
    set_variable = {{ name = eu5ab_governor_total_value value = 0 }}
    set_variable = {{ name = eu5ab_gov_refresh_phase value = 1 }}
    set_variable = {{ name = eu5ab_gov_refresh_work value = 0 }}
    set_variable = {{ name = eu5ab_gov_refresh_candidates value = 0 }}
    set_variable = {{ name = eu5ab_gov_refresh_seats value = 0 }}
    set_variable = {{ name = eu5ab_gov_refresh_snapshot_count value = num_locations }}
    set_variable = {{ name = eu5ab_gov_refresh_snapshot_capital value = capital }}
    set_variable = {{ name = eu5ab_layout_ticks value = 0 }}
    set_variable = {{ name = eu5ab_layout_watchdog_last_ticks value = 0 }}
    set_variable = {{ name = eu5ab_layout_fallback_batches value = 0 }}
    eu5ab_governor_snapshot_locations = yes
    set_variable = {{ name = eu5ab_gov_refresh_cursor value = var:eu5ab_gov_snapshot_head }}
    eu5ab_layout_snapshot_progress = yes
    eu5ab_layout_schedule_watchdog = yes
}}

# Only lightweight links are built synchronously; expensive per-location work
# advances through the saved cursor without repeatedly sorting the whole realm.
eu5ab_governor_snapshot_locations = {{
    remove_variable = eu5ab_gov_snapshot_head
    remove_variable = eu5ab_gov_snapshot_tail
    clear_variable_list = eu5ab_layout_snapshot_locations
    every_owned_location = {{
        remove_variable = eu5ab_gov_snapshot_next
        save_temporary_scope_as = eu5ab_gov_snapshot_node
        root = {{
            add_to_variable_list = {{ name = eu5ab_layout_snapshot_locations target = scope:eu5ab_gov_snapshot_node }}
            if = {{ limit = {{ has_variable = eu5ab_gov_snapshot_tail }}
                var:eu5ab_gov_snapshot_tail = {{ set_variable = {{ name = eu5ab_gov_snapshot_next value = scope:eu5ab_gov_snapshot_node }} }}
            }}
            else = {{ set_variable = {{ name = eu5ab_gov_snapshot_head value = scope:eu5ab_gov_snapshot_node }} }}
            set_variable = {{ name = eu5ab_gov_snapshot_tail value = scope:eu5ab_gov_snapshot_node }}
        }}
    }}
}}

eu5ab_governor_append_candidate = {{
    remove_variable = eu5ab_gov_candidate_next
    save_temporary_scope_as = eu5ab_gov_new_candidate
    root = {{
        if = {{ limit = {{ has_variable = eu5ab_gov_candidate_tail }}
            var:eu5ab_gov_candidate_tail = {{ set_variable = {{ name = eu5ab_gov_candidate_next value = scope:eu5ab_gov_new_candidate }} }}
        }}
        else = {{ set_variable = {{ name = eu5ab_gov_candidate_head value = scope:eu5ab_gov_new_candidate }} }}
        set_variable = {{ name = eu5ab_gov_candidate_tail value = scope:eu5ab_gov_new_candidate }}
    }}
}}

eu5ab_governor_refresh_tick = {{
    change_variable = {{ name = eu5ab_layout_ticks add = 1 }}
    change_variable = {{ name = eu5ab_gov_refresh_work add = 1 }}
    if = {{ limit = {{ var:eu5ab_global_governor_recommendations_enabled <= 0 NOT = {{ has_variable = eu5ab_governor_manual_run }} }}
        eu5ab_layout_abort = yes
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 1 }}
        {cursor_batch('eu5ab_gov_refresh_cursor', 'eu5ab_gov_snapshot_next', preflight)}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_refresh_cursor }} }}
            {capacity_snapshot}
            if = {{ limit = {{ eu5ab_fresh_local_governor_slot_available = yes var:eu5ab_gov_refresh_candidates > 0 }} set_variable = eu5ab_gov_refresh_need_new }}
            if = {{ limit = {{ var:eu5ab_gov_refresh_seats > 0 var:eu5ab_global_governor_relocation_enabled > 0 OR = {{ var:eu5ab_global_governor_migration_enabled > 0 has_variable = eu5ab_governor_manual_run }} }} set_variable = eu5ab_gov_refresh_need_layout }}
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 9 }}
            if = {{ limit = {{ OR = {{ has_variable = eu5ab_gov_refresh_need_new has_variable = eu5ab_gov_refresh_need_layout }} }} set_variable = {{ name = eu5ab_gov_refresh_phase value = 2 }} }}
            set_variable = {{ name = eu5ab_gov_refresh_cursor value = var:eu5ab_gov_snapshot_head }}
        }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 2 }}
        {cursor_batch('eu5ab_gov_refresh_cursor', 'eu5ab_gov_snapshot_next', prepare)}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_refresh_cursor }} }}
            set_variable = eu5ab_gov_inputs_ready
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 9 }}
            if = {{ limit = {{ has_variable = eu5ab_gov_refresh_need_new NOT = {{ has_variable = eu5ab_gov_refresh_invalid }} }}
                set_variable = {{ name = eu5ab_gov_refresh_phase value = 3 }}
                set_variable = {{ name = eu5ab_gov_eval_kind value = {begin_seed} }}
                set_variable = {{ name = eu5ab_gov_eval_generation value = 0 }}
                remove_variable = eu5ab_gov_queue_head
                remove_variable = eu5ab_gov_queue_tail
                clear_variable_list = eu5ab_gov_eval_locations
                set_variable = {{ name = eu5ab_gov_refresh_wave_work value = 0 }}
            }}
            set_variable = {{ name = eu5ab_gov_refresh_cursor value = var:eu5ab_gov_snapshot_head }}
        }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 3 }}
        {cursor_batch('eu5ab_gov_refresh_cursor', 'eu5ab_gov_snapshot_next', seed)}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_refresh_cursor }} }} set_variable = {{ name = eu5ab_gov_refresh_phase value = 4 }} }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 4 }}
        while = {{ limit = {{ has_variable = eu5ab_gov_queue_head eu5ab_gov_refresh_wave_budget_available = yes }} count = {WORK}
            eu5ab_governor_queue_relax_one = yes
            change_variable = {{ name = eu5ab_gov_refresh_wave_work add = 1 }}
        }}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_queue_head }} }}
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 5 }}
            set_variable = {{ name = eu5ab_gov_refresh_cursor value = var:eu5ab_gov_snapshot_head }}
        }}
        else_if = {{ limit = {{ NOT = {{ eu5ab_gov_refresh_wave_budget_available = yes }} }}
            set_variable = eu5ab_governor_baseline_failed
            eu5ab_governor_refresh_failed = yes
        }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 5 }}
        {cursor_batch('eu5ab_gov_refresh_cursor', 'eu5ab_gov_snapshot_next', collect)}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_refresh_cursor }} }}
            clear_variable_list = eu5ab_gov_eval_locations
            remove_variable = eu5ab_gov_candidate_head
            remove_variable = eu5ab_gov_candidate_tail
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 6 }}
            set_variable = {{ name = eu5ab_gov_refresh_cursor value = var:eu5ab_gov_snapshot_head }}
        }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 6 }}
        {cursor_batch('eu5ab_gov_refresh_cursor', 'eu5ab_gov_snapshot_next', cheap)}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_refresh_cursor }} }}
            {shortlist}
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 7 }}
        }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 7 }}
        if = {{ limit = {{ has_variable = eu5ab_gov_candidate_head }}
            set_variable = {{ name = eu5ab_gov_eval_kind value = {kind} }}
            var:eu5ab_gov_candidate_head = {{ {start} }}
            set_variable = {{ name = eu5ab_gov_refresh_wave_work value = 0 }}
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 8 }}
        }}
        else = {{
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 9 }}
            set_variable = {{ name = eu5ab_gov_refresh_cursor value = var:eu5ab_gov_snapshot_head }}
        }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 8 }}
        while = {{ limit = {{ has_variable = eu5ab_gov_queue_head eu5ab_gov_refresh_wave_budget_available = yes }} count = {WORK}
            eu5ab_governor_queue_relax_one = yes
            change_variable = {{ name = eu5ab_gov_refresh_wave_work add = 1 }}
        }}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_queue_head }} }}
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 10 }}
            set_variable = {{ name = eu5ab_gov_refresh_cursor value = var:eu5ab_gov_footprint_head }}
        }}
        else_if = {{ limit = {{ NOT = {{ eu5ab_gov_refresh_wave_budget_available = yes }} }} eu5ab_governor_refresh_failed = yes }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 10 }}
        var:eu5ab_gov_candidate_head = {{ save_temporary_scope_as = eu5ab_gov_evaluated_candidate }}
        {cursor_batch('eu5ab_gov_refresh_cursor', 'eu5ab_gov_footprint_next', reduce)}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_refresh_cursor }} }}
            var:eu5ab_gov_candidate_head = {{
                {finish}
                {result}
                if = {{ limit = {{ has_variable = eu5ab_gov_candidate_next }} root = {{ set_variable = {{ name = eu5ab_gov_candidate_head value = prev.var:eu5ab_gov_candidate_next }} }} }}
                else = {{ root = {{ remove_variable = eu5ab_gov_candidate_head }} }}
            }}
            set_variable = {{ name = eu5ab_gov_refresh_phase value = 7 }}
        }}
    }}
    else_if = {{ limit = {{ var:eu5ab_gov_refresh_phase = 9 }}
        {cursor_batch('eu5ab_gov_refresh_cursor', 'eu5ab_gov_snapshot_next', validate)}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_refresh_cursor }} }} eu5ab_governor_refresh_commit = yes }}
    }}
    else = {{ eu5ab_governor_refresh_failed = yes }}
}}

eu5ab_governor_refresh_failed = {{
    set_variable = eu5ab_governor_queue_exhausted
    set_variable = {{ name = eu5ab_gov_sync_status value = 4 }}
    eu5ab_layout_abort = yes
}}
'''


def render_refresh_triggers() -> str:
    return '''eu5ab_gov_refresh_wave_budget_available = {
    OR = {
        AND = { var:eu5ab_gov_refresh_phase = 4 var:eu5ab_gov_refresh_wave_work < { value = num_locations multiply = 20 min = 100 } }
        AND = { var:eu5ab_gov_refresh_phase = 8 var:eu5ab_gov_refresh_wave_work < { value = num_locations multiply = 4 min = 100 } }
    }
}
'''


def integrate_refresh(shared: str, *, naval: bool = False) -> str:
    effects = render_refresh_effects(shared, naval=naval)
    old = script_definition(shared, "eu5ab_governor_refresh_other_recommendations")
    tail = old[old.index("eu5ab_governor_rank_local_results = yes"):old.rindex("}")]
    if not naval:
        tail = tail[:tail.rindex("}")]
    tail = tail.replace("eu5ab_governor_rank_local_results = yes", "if = { limit = { has_variable = eu5ab_gov_refresh_need_new } eu5ab_governor_rank_local_results = yes }")
    clear = "eu5ab_governor_clear_naval_results" if naval else "eu5ab_governor_clear_country_results"
    capacity = "naval" if naval else "local"
    slots = "eu5ab_governor_snapshot_naval_slots" if naval else "eu5ab_governor_snapshot_local_slot_state"
    # Publication must recheck structural inputs in this same callback. A
    # batched validation alone leaves already-visited nodes open to later edits.
    final_guard = f'''
    set_local_variable = {{ name = eu5ab_refresh_capacity value = var:eu5ab_gov_fresh_{capacity}_capacity }}
    set_local_variable = {{ name = eu5ab_refresh_occupied value = var:eu5ab_gov_fresh_{capacity}_occupied }}
    {slots} = yes
    if = {{ limit = {{ var:eu5ab_gov_fresh_{capacity}_capacity != local_var:eu5ab_refresh_capacity }} set_variable = eu5ab_gov_refresh_invalid }}
    if = {{ limit = {{ var:eu5ab_gov_fresh_{capacity}_occupied != local_var:eu5ab_refresh_occupied }} set_variable = eu5ab_gov_refresh_invalid }}
    {"if = { limit = { var:eu5ab_gov_snapshot_other_slots != eu5ab_governor_fresh_local_other_slots } set_variable = eu5ab_gov_refresh_invalid }" if not naval else ""}
    remove_local_variable = eu5ab_refresh_occupied
    remove_local_variable = eu5ab_refresh_capacity
    every_in_list = {{
        variable = eu5ab_layout_snapshot_locations
        if = {{ limit = {{ OR = {{
            NOT = {{ owner ?= root }}
            AND = {{ root = {{ has_variable = eu5ab_gov_inputs_ready }} var:eu5ab_gov_snapshot_native_source != modifier:local_proximity_source }}
            AND = {{ has_variable = eu5ab_gov_refresh_old NOT = {{ has_building = building_type:{capacity}_governor }} }}
            AND = {{ NOT = {{ has_variable = eu5ab_gov_refresh_old }} has_building = building_type:{capacity}_governor }}
            AND = {{ has_variable = eu5ab_gov_refresh_eligible NOT = {{ eu5ab_local_governor_candidate = yes }} }}
        }} }} root = {{ set_variable = eu5ab_gov_refresh_invalid }} }}
    }}'''
    # A changed country-wide transport rule invalidates cached directed costs.
    transport = script_definition(shared, "eu5ab_governor_snapshot_transport")
    invalid_transport = "\n".join(
        f"        var:{name} != {value}"
        for name, value in re.findall(r"name = (eu5ab_gov_cached_\w+) value = (modifier:\w+)", transport)
    )
    effects += f'''
eu5ab_governor_refresh_commit = {{
{final_guard}
    if = {{ limit = {{ OR = {{
        has_variable = eu5ab_gov_refresh_invalid
        has_variable = eu5ab_governor_dirty
        num_locations != var:eu5ab_gov_refresh_snapshot_count
        capital != var:eu5ab_gov_refresh_snapshot_capital
        var:eu5ab_gov_transport_road_tier != eu5ab_governor_highest_road_tier
{invalid_transport}
    }} }}
        # Abort clears overrides; restore the manual intent explicitly below.
        set_local_variable = {{ name = eu5ab_refresh_manual value = 0 }}
        if = {{ limit = {{ has_variable = eu5ab_governor_manual_run }} set_local_variable = {{ name = eu5ab_refresh_manual value = 1 }} }}
        eu5ab_layout_abort = yes
        if = {{ limit = {{ local_var:eu5ab_refresh_manual > 0 }} set_variable = eu5ab_governor_resume_manual }}
        set_variable = eu5ab_governor_dirty
        eu5ab_layout_recover_transport_restart = yes
        remove_local_variable = eu5ab_refresh_manual
    }}
    else = {{
        set_local_variable = {{ name = eu5ab_refresh_total value = var:eu5ab_governor_total_value }}
        {clear} = yes
        set_variable = {{ name = eu5ab_governor_total_value value = local_var:eu5ab_refresh_total }}
        remove_local_variable = eu5ab_refresh_total
        {tail}
        if = {{ limit = {{ NOT = {{ has_variable = eu5ab_gov_refresh_need_new }} }}
            set_variable = {{ name = eu5ab_gov_sync_status value = 1 }}
            if = {{ limit = {{ var:eu5ab_gov_fresh_{capacity}_capacity <= 0 }}
                set_variable = {{ name = eu5ab_gov_sync_status value = 6 }}
            }}
        }}
        set_variable = {{ name = eu5ab_gov_refresh_phase value = 0 }}
        if = {{ limit = {{ has_variable = eu5ab_gov_refresh_run_layout has_variable = eu5ab_gov_refresh_need_layout }}
            remove_variable = eu5ab_gov_refresh_run_layout
            eu5ab_layout_begin = yes
        }}
        else = {{
            remove_variable = eu5ab_gov_refresh_run_layout
            remove_variable = eu5ab_governor_scan_active
            remove_variable = eu5ab_governor_manual_run
            remove_variable = eu5ab_gov_inputs_ready
            eu5ab_layout_clear_liveness = yes
            if = {{ limit = {{ OR = {{ var:eu5ab_gov_refresh_seats = 0 NOT = {{ var:eu5ab_global_governor_relocation_enabled > 0 }} }} }}
                eu5ab_layout_clear_published_results = yes
                eu5ab_governor_clear_local_migration = yes
            }}
        }}
    }}
}}
'''
    wrapper = '''eu5ab_governor_refresh_other_recommendations = {
    eu5ab_governor_refresh_begin = yes
    while = {
        limit = { var:eu5ab_gov_refresh_phase > 0 has_variable = eu5ab_governor_scan_active }
        count = 100000
        eu5ab_governor_refresh_tick = yes
    }
    if = { limit = { var:eu5ab_gov_refresh_phase > 0 } eu5ab_governor_refresh_failed = yes }
}'''
    shared = shared.replace(old, wrapper)
    # A published result must remain visible until the replacement is complete.
    manual = script_definition(shared, "eu5ab_governor_manual_recalculation")
    shared = shared.replace(manual, re.sub(r"^\s*eu5ab_(?:layout_clear_published_results|governor_clear_local_migration) = yes\n", "\n", manual, flags=re.M))
    recalculate = script_definition(shared, "eu5ab_recalculate_governor_recommendations")
    shared = shared.replace(recalculate, '''eu5ab_recalculate_governor_recommendations = {
    set_variable = eu5ab_gov_refresh_run_layout
    eu5ab_governor_refresh_begin = yes
}''')
    return shared + "\n" + effects


def add_footprint_links(text: str) -> str:
    """Keep the existing diagnostic list, plus a cursor for linear reductions."""
    text = re.sub(
        r"add_to_variable_list = \{ name = eu5ab_gov_eval_locations target = ([^ }]+) \}",
        r"eu5ab_governor_record_visited = { node = \1 }", text,
    )
    text = text.replace("clear_variable_list = eu5ab_gov_eval_locations", "clear_variable_list = eu5ab_gov_eval_locations\n    remove_variable = eu5ab_gov_footprint_head\n    remove_variable = eu5ab_gov_footprint_tail")
    return text + '''
eu5ab_governor_record_visited = {
    add_to_variable_list = { name = eu5ab_gov_eval_locations target = $node$ }
    if = { limit = { has_variable = eu5ab_gov_footprint_tail }
        var:eu5ab_gov_footprint_tail = { set_variable = { name = eu5ab_gov_footprint_next value = $node$ } }
    }
    else = { set_variable = { name = eu5ab_gov_footprint_head value = $node$ } }
    $node$ = { remove_variable = eu5ab_gov_footprint_next }
    set_variable = { name = eu5ab_gov_footprint_tail value = $node$ }
}
'''
