"""Move linear layout work to saved cursors without changing its arithmetic."""
from __future__ import annotations

from .governor_planner import script_definition
from .governor_refresh import cursor_batch, split_block


def batch_layout_effects(text: str, work: int) -> str:
    begin = script_definition(text, "eu5ab_layout_begin")
    prefix, initialize, rest = split_block(begin, "    every_owned_location = {")
    _, bounds, finish = split_block(rest, "    every_owned_location = {")
    finish = finish[:finish.rindex("}")]
    prefix = prefix.replace("    clear_variable_list = eu5ab_layout_snapshot_locations\n", "")
    prefix = prefix.replace("    set_variable = { name = eu5ab_governor_total_value value = 0 }\n", "")
    initialize = initialize.replace("        eu5ab_governor_clear_location_cache = yes\n        eu5ab_governor_prepare_location_value = yes", """
        if = { limit = { root = { NOT = { has_variable = eu5ab_gov_inputs_ready } } }
            eu5ab_governor_clear_location_cache = yes
            eu5ab_governor_prepare_location_value = yes
            set_variable = { name = eu5ab_gov_snapshot_source value = eu5ab_governor_current_proximity_source }
            set_variable = { name = eu5ab_gov_snapshot_native_source value = modifier:local_proximity_source }
        }""")
    initialize = initialize.replace("        save_temporary_scope_as = eu5ab_layout_snapshot_node\n        root = { add_to_variable_list = { name = eu5ab_layout_snapshot_locations target = scope:eu5ab_layout_snapshot_node } }\n", "")
    initialize = initialize.replace("name = eu5ab_layout_source value = eu5ab_governor_current_proximity_source", "name = eu5ab_layout_source value = var:eu5ab_gov_snapshot_source")
    initialize = "if = { limit = { owner ?= root } " + initialize + " } else = { root = { eu5ab_layout_abort = yes } }"
    prefix += """
    if = { limit = { NOT = { has_variable = eu5ab_gov_inputs_ready } }
        set_variable = { name = eu5ab_governor_total_value value = 0 }
        eu5ab_governor_snapshot_locations = yes
    }
    set_variable = { name = eu5ab_layout_phase value = 12 }
    set_variable = { name = eu5ab_layout_cursor value = var:eu5ab_gov_snapshot_head }
    eu5ab_layout_schedule_watchdog = yes
    eu5ab_layout_snapshot_progress = yes
}"""
    text = text.replace(begin, prefix)
    source = script_definition(text, "eu5ab_layout_start_source_wave")
    _, seed, _ = split_block(source, "    every_owned_location = {")
    text = text.replace(source, """eu5ab_layout_start_source_wave = {
    eu5ab_layout_reset_wave = yes
    set_variable = { name = eu5ab_layout_phase value = 11 }
    set_variable = { name = eu5ab_layout_cursor value = var:eu5ab_gov_snapshot_head }
}""")

    tick = script_definition(text, "eu5ab_layout_tick")
    # These reductions have no meaningful ranking: list cursors preserve their
    # original insertion order, avoiding a fresh full-list sort for each batch.
    for phase, iterator, head, next_var, effect in (
        (2, "ordered_in_list", "eu5ab_gov_footprint_head", "eu5ab_gov_footprint_next", "collect_one"),
        (4, "ordered_in_list", "eu5ab_gov_footprint_head", "eu5ab_gov_footprint_next", "apply_one"),
        (6, "ordered_owned_location", "eu5ab_gov_snapshot_head", "eu5ab_gov_snapshot_next", "collect_exclusive"),
        (9, "ordered_owned_location", "eu5ab_gov_snapshot_head", "eu5ab_gov_snapshot_next", "reduce_full_plan"),
        (10, "ordered_owned_location", "eu5ab_gov_snapshot_head", "eu5ab_gov_snapshot_next", "prepare_single_winner"),
    ):
        marker = f"limit = {{ var:eu5ab_layout_phase = {phase} }}"
        offset = tick.index(marker)
        before, _, after = split_block(tick[offset:], f"            {iterator} = {{")
        tick = tick[:offset] + before + cursor_batch("eu5ab_layout_cursor", next_var, f"eu5ab_layout_{effect} = yes", work) + after
        assignment = f"set_variable = {{ name = eu5ab_layout_phase value = {phase} }}"
        text = text.replace(assignment, assignment + f"\n    set_variable = {{ name = eu5ab_layout_cursor value = var:{head} }}")
        tick = tick.replace(assignment, assignment + f"\n    set_variable = {{ name = eu5ab_layout_cursor value = var:{head} }}")

    # Score/validation are also linear. Publish rows and country UI values only
    # after both passes finish; no partially accumulated score is exposed.
    publish = script_definition(text, "eu5ab_layout_publish")
    before, validation, after = split_block(publish, "    every_in_list = {")
    validation = validation.replace("        variable = eu5ab_layout_snapshot_locations\n", "")
    publish = before + after
    before, score, after = split_block(publish, "        every_owned_location = {")
    publish = before + after
    for reset in (
        "    remove_variable = eu5ab_layout_invalid_snapshot\n",
        "        set_variable = { name = eu5ab_layout_after value = 0 }\n",
        "        set_variable = { name = eu5ab_layout_planned_vs_live_difference value = 0 }\n",
    ):
        publish = publish.replace(reset, "")
    text = text.replace(script_definition(text, "eu5ab_layout_publish"), publish)

    def phase(number: int, body: str, completed: str) -> str:
        return f"""else_if = {{
            limit = {{ var:eu5ab_layout_phase = {number} }}
            {cursor_batch('eu5ab_layout_cursor', 'eu5ab_gov_snapshot_next', body + ' root = { change_variable = { name = eu5ab_layout_total_work add = 1 } }', work)}
            if = {{ limit = {{ has_variable = eu5ab_governor_scan_active NOT = {{ has_variable = eu5ab_layout_cursor }} }} {completed} }}
        }}
        """

    def next_phase(number: int) -> str:
        return f"set_variable = {{ name = eu5ab_layout_phase value = {number} }} set_variable = {{ name = eu5ab_layout_cursor value = var:eu5ab_gov_snapshot_head }}"

    extra = phase(11, seed, "set_variable = { name = eu5ab_layout_phase value = 1 }")
    extra += phase(12, initialize, "set_variable = eu5ab_gov_inputs_ready " + next_phase(13))
    extra += phase(13, bounds, finish)
    extra += phase(14, validation, next_phase(15))
    extra += phase(15, score, "EU5AB_COMPLETE_PUBLICATION_PHASE")
    tick = tick.replace("        else = { eu5ab_layout_abort = yes }", "        " + extra + "else = { eu5ab_layout_abort = yes }")
    text = text.replace(script_definition(text, "eu5ab_layout_tick"), tick)
    # Static transitions to publication start its first pass. The transition
    # from phase 15 itself is already complete and must not be rewritten.
    start_publication = """set_variable = { name = eu5ab_layout_phase value = 14 }
    remove_variable = eu5ab_layout_invalid_snapshot
    set_variable = { name = eu5ab_layout_after value = 0 }
    set_variable = { name = eu5ab_layout_planned_vs_live_difference value = 0 }
    set_variable = { name = eu5ab_layout_cursor value = var:eu5ab_gov_snapshot_head }"""
    text = text.replace("set_variable = { name = eu5ab_layout_phase value = 5 }", start_publication)
    return text.replace("EU5AB_COMPLETE_PUBLICATION_PHASE", "set_variable = { name = eu5ab_layout_phase value = 5 }")
