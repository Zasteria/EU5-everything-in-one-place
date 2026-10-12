"""Resumable local-Governor planner; UI/entry-point integration is separate.

The frontier queue and the last evaluated footprint survive GUI pulses. Score
upper bounds are reused between rounds (adding a source cannot increase any
remaining marginal gain). Only stale contenders are propagated again.
"""
from __future__ import annotations

from .governor_layout_ui import render_layout_page_effect
from .governor_layout_preview import render_preview_effects
from .governor_layout_liveness import render_liveness_effects
from .governor_transport_generator import render_lake_relaxation
from .governor_planner import LOCAL_PLANNER, PlannerType, script_definition
from .governor_layout_batches import batch_layout_effects
from .governor_refresh import split_block

WORK_PER_PULSE = 64
QUEUE_BUDGET_PER_LOCATION = 20


def render_layout_start_effect(planner: PlannerType = LOCAL_PLANNER) -> str:
    initial_wave = '''    eu5ab_layout_reset_wave = yes
    set_variable = { name = eu5ab_layout_mode value = 1 }
    capital = {
        set_local_variable = { name = eu5ab_layout_seed_value value = 1000000 }
        eu5ab_layout_seed = yes
        remove_local_variable = eu5ab_layout_seed_value
    }''' if planner.capital_bands else '''    set_variable = { name = eu5ab_layout_mode value = 2 }
    eu5ab_layout_start_source_wave = yes'''
    return r'''eu5ab_layout_clear_published_results = {
    remove_variable = eu5ab_layout_has_results
    remove_variable = eu5ab_layout_ready
    remove_variable = eu5ab_layout_result_proposal
    remove_variable = eu5ab_layout_result_road_tier
    remove_variable = eu5ab_layout_show_candidates
    eu5ab_layout_clear_candidates = yes
    set_variable = { name = eu5ab_layout_result_count value = 0 }
    set_variable = { name = eu5ab_layout_result_before value = 0 }
    set_variable = { name = eu5ab_layout_result_after value = 0 }
    set_variable = { name = eu5ab_layout_result_net value = 0 }
    set_variable = { name = eu5ab_layout_result_kind value = 0 }
    set_variable = { name = eu5ab_layout_page value = 0 }
    every_owned_location = {
        remove_variable = eu5ab_layout_row_order
        remove_variable = eu5ab_layout_row_to
        remove_variable = eu5ab_layout_row_gain
    }
    eu5ab_layout_refresh_page = yes
}

eu5ab_layout_begin = {
    if = { limit = { NOT = { has_variable = eu5ab_gov_inputs_ready } } eu5ab_governor_snapshot_local_slot_state = yes }
    if = { limit = { NOT = { has_variable = eu5ab_layout_generation } } set_variable = { name = eu5ab_layout_generation value = 0 } }
    change_variable = { name = eu5ab_layout_generation add = 1 }
    set_variable = { name = eu5ab_layout_work_generation value = var:eu5ab_layout_generation }
    # Snapshot the setting once; missing settings in older saves use the default.
    set_variable = { name = eu5ab_layout_threshold_percent value = 80 }
    if = {
        limit = { has_variable = eu5ab_global_governor_migration_threshold_percent }
        set_variable = { name = eu5ab_layout_threshold_percent value = { value = var:eu5ab_global_governor_migration_threshold_percent min = 0 max = 200 } }
    }
    set_variable = eu5ab_governor_scan_active
    remove_variable = eu5ab_governor_dirty
    remove_variable = eu5ab_layout_failed
    remove_variable = eu5ab_layout_last_footprint
    remove_variable = eu5ab_layout_force_keep
    remove_variable = eu5ab_layout_single_origin
    remove_variable = eu5ab_layout_single_target
    remove_variable = eu5ab_layout_single_destination_gain
    remove_variable = eu5ab_layout_compare_single
    remove_variable = eu5ab_layout_single_only
    set_variable = { name = eu5ab_layout_single_net value = 0 }
    set_variable = { name = eu5ab_layout_single_candidates value = 0 }
    set_variable = { name = eu5ab_layout_single_comparisons value = 0 }
    set_variable = { name = eu5ab_layout_changed_contribution value = 0 }
    set_variable = { name = eu5ab_layout_proposal_kind value = 1 }
    clear_variable_list = eu5ab_layout_snapshot_locations
    set_variable = { name = eu5ab_gov_eval_generation value = 0 }
    set_variable = { name = eu5ab_governor_total_value value = 0 }
    set_variable = { name = eu5ab_layout_seats value = 0 }
    set_variable = { name = eu5ab_layout_round value = 1 }
    set_variable = { name = eu5ab_layout_completed value = 0 }
    set_variable = { name = eu5ab_layout_before value = 0 }
    set_variable = { name = eu5ab_layout_total_work value = 0 }
    set_variable = { name = eu5ab_layout_ticks value = 0 }
    set_variable = { name = eu5ab_layout_watchdog_last_ticks value = 0 }
    set_variable = { name = eu5ab_layout_fallback_batches value = 0 }
    set_variable = { name = eu5ab_layout_propagations value = 0 }
    set_variable = { name = eu5ab_layout_snapshot_count value = num_locations }
    set_variable = { name = eu5ab_layout_snapshot_capital value = capital }
    set_variable = { name = eu5ab_layout_snapshot_capacity value = eu5ab_governor_relocation_capacity }
    set_variable = { name = eu5ab_layout_snapshot_occupied value = eu5ab_governor_relocation_occupied }
    set_variable = { name = eu5ab_layout_wave_budget value = { value = num_locations multiply = @BUDGET@ min = 100 } }
    every_owned_location = {
        remove_variable = eu5ab_layout_preview_from
        remove_variable = eu5ab_layout_preview_net
        remove_variable = eu5ab_layout_preview_before
        eu5ab_governor_clear_location_cache = yes
        eu5ab_governor_prepare_location_value = yes
        save_temporary_scope_as = eu5ab_layout_snapshot_node
        root = { add_to_variable_list = { name = eu5ab_layout_snapshot_locations target = scope:eu5ab_layout_snapshot_node } }
        set_variable = { name = eu5ab_gov_visit_generation value = -1 }
        set_variable = { name = eu5ab_layout_scored_round value = -1 }
        set_variable = { name = eu5ab_layout_source value = eu5ab_governor_current_proximity_source }
        set_variable = { name = eu5ab_layout_distance value = @DISTANCE@ }
        set_variable = { name = eu5ab_layout_band value = @BAND@ }
        set_variable = { name = eu5ab_layout_band_order value = -@BAND@ }
        set_variable = { name = eu5ab_layout_base value = 0 }
        set_variable = { name = eu5ab_layout_virtual value = 0 }
        set_variable = { name = eu5ab_layout_current value = 0 }
        set_variable = { name = eu5ab_layout_best_governor value = 0 }
        set_variable = { name = eu5ab_layout_second_governor value = 0 }
        set_variable = { name = eu5ab_layout_exclusive value = 0 }
        set_variable = { name = eu5ab_layout_retained value = 0 }
        set_variable = { name = eu5ab_layout_recovery_generation value = -1 }
        set_variable = { name = eu5ab_layout_compared_generation value = -1 }
        remove_variable = eu5ab_layout_best_origin
        remove_variable = eu5ab_layout_old_wave_done
        remove_variable = eu5ab_layout_single_checked
        remove_variable = eu5ab_layout_selected
        remove_variable = eu5ab_layout_old
        remove_variable = eu5ab_layout_eligible
        if = {
            limit = { has_building = building_type:local_governor }
            set_variable = eu5ab_layout_old
            set_variable = eu5ab_layout_eligible
            root = { change_variable = { name = eu5ab_layout_seats add = 1 } }
        }
        else_if = {
            limit = { eu5ab_local_governor_candidate = yes }
            set_variable = eu5ab_layout_eligible
        }
    }
    every_owned_location = {
        # An admissible upper bound; no live-Proximity shortlist can exclude a site.
        set_variable = { name = eu5ab_layout_upper_gain value = root.var:eu5ab_governor_total_value }
    }
    set_variable = { name = eu5ab_layout_min_gain value = @MIN_GAIN@ }
@INITIAL_WAVE@
    eu5ab_layout_schedule_watchdog = yes
    eu5ab_layout_snapshot_progress = yes
}
'''.replace("@BUDGET@", str(QUEUE_BUDGET_PER_LOCATION)).replace(
        "@INITIAL_WAVE@", initial_wave).replace("@DISTANCE@", "1000000" if planner.capital_bands else "0").replace(
        "@BAND@", "25000" if planner.capital_bands else "0").replace(
        "@MIN_GAIN@", "eu5ab_governor_layout_candidate_threshold" if planner.capital_bands else "0.00001")


def render_layout_publish_effects() -> str:
    return r'''# Called only after every source wave and every planning round completed.
eu5ab_layout_publish = {
    eu5ab_governor_check_transport_rules = yes
    if = {
        limit = { NOT = { has_variable = eu5ab_governor_scan_active } }
        eu5ab_layout_recover_transport_restart = yes
    }
    else = {
    eu5ab_governor_snapshot_local_slot_state = yes
    remove_variable = eu5ab_layout_invalid_snapshot
    if = {
        limit = {
            OR = {
                num_locations != var:eu5ab_layout_snapshot_count
                capital != var:eu5ab_layout_snapshot_capital
                var:eu5ab_layout_snapshot_capacity != eu5ab_governor_relocation_capacity
                var:eu5ab_layout_snapshot_occupied != eu5ab_governor_relocation_occupied
                var:eu5ab_layout_work_generation != var:eu5ab_layout_generation
            }
        }
        set_variable = eu5ab_layout_invalid_snapshot
    }
    every_in_list = {
        variable = eu5ab_layout_snapshot_locations
        if = {
            limit = {
                OR = {
                    NOT = { owner ?= root }
                    var:eu5ab_layout_source != eu5ab_governor_current_proximity_source
                    AND = { has_variable = eu5ab_layout_old NOT = { has_building = building_type:local_governor } }
                    AND = { NOT = { has_variable = eu5ab_layout_old } has_building = building_type:local_governor }
                    AND = { has_variable = eu5ab_layout_selected NOT = { has_variable = eu5ab_layout_old } NOT = { eu5ab_local_governor_candidate = yes } }
                }
            }
            root = { set_variable = eu5ab_layout_invalid_snapshot }
        }
    }
    # The detailed pass can span pulses. Recheck ownership/native sources and
    # selected seats atomically with publication, without recalculating scores.
    every_in_list = {
        variable = eu5ab_layout_snapshot_locations
        if = {
            limit = { OR = {
                NOT = { owner ?= root }
                var:eu5ab_gov_snapshot_native_source != modifier:local_proximity_source
                AND = { has_variable = eu5ab_layout_old NOT = { has_building = building_type:local_governor } }
                AND = { NOT = { has_variable = eu5ab_layout_old } has_building = building_type:local_governor }
                AND = { has_variable = eu5ab_layout_selected NOT = { has_variable = eu5ab_layout_old } NOT = { eu5ab_local_governor_candidate = yes } }
            } }
            root = { set_variable = eu5ab_layout_invalid_snapshot }
        }
    }
    if = {
        limit = { has_variable = eu5ab_layout_invalid_snapshot }
        eu5ab_layout_abort = yes
    }
    else_if = {
        # Demolishing one seat cannot free a replacement slot when already over cap.
        limit = { eu5ab_governor_relocation_occupied > eu5ab_governor_relocation_capacity }
        eu5ab_layout_clear_published_results = yes
        eu5ab_governor_clear_local_migration = yes
        remove_variable = eu5ab_governor_scan_active
        remove_variable = eu5ab_governor_manual_run
        remove_variable = eu5ab_gov_inputs_ready
        eu5ab_layout_clear_liveness = yes
    }
    else_if = {
        limit = { has_variable = eu5ab_governor_dirty }
        # Dirty state belongs to both recommendation consumers. Refresh the
        # synchronous cards before layout_begin consumes it for the next plan.
        eu5ab_recalculate_governor_recommendations = yes
    }
    else = {
        set_variable = { name = eu5ab_layout_after value = 0 }
        set_variable = { name = eu5ab_layout_planned_vs_live_difference value = 0 }
        every_owned_location = {
            root = {
                change_variable = {
                    name = eu5ab_layout_after
                    add = { value = prev.var:eu5ab_layout_virtual subtract = prev.var:eu5ab_layout_base min = 0 divide = 100 multiply = prev.var:eu5ab_gov_node_value }
                }
            }
            set_local_variable = { name = eu5ab_layout_live_difference value = { value = var:eu5ab_layout_current subtract = var:eu5ab_gov_cached_old_proximity } }
            if = { limit = { local_var:eu5ab_layout_live_difference < 0 } change_local_variable = { name = eu5ab_layout_live_difference multiply = -1 } }
            root = { change_variable = { name = eu5ab_layout_planned_vs_live_difference add = { value = local_var:eu5ab_layout_live_difference divide = 100 multiply = prev.var:eu5ab_gov_node_value } } }
            remove_local_variable = eu5ab_layout_live_difference
        }
        set_variable = { name = eu5ab_layout_net value = { value = var:eu5ab_layout_after subtract = var:eu5ab_layout_before } }
        remove_variable = eu5ab_layout_qualifies
        if = {
            limit = {
                var:eu5ab_layout_net > 0
                var:eu5ab_layout_net >= { value = var:eu5ab_layout_changed_contribution multiply = var:eu5ab_layout_threshold_percent divide = 100 }
            }
            set_variable = eu5ab_layout_qualifies
        }
        eu5ab_layout_publish_rows = yes
        eu5ab_layout_validate_rows = yes
        if = {
            limit = { has_variable = eu5ab_layout_invalid_rows }
            # Never combine a complete score/alert with a partial or mismatched list.
            eu5ab_layout_clear_published_results = yes
            eu5ab_layout_abort = yes
        }
        else = {
            eu5ab_layout_confirm = yes
            # UI reads only these published values, never work-in-progress fields.
            set_variable = { name = eu5ab_layout_result_before value = var:eu5ab_layout_before }
            set_variable = { name = eu5ab_layout_result_road_tier value = var:eu5ab_gov_transport_road_tier }
            set_variable = { name = eu5ab_layout_result_after value = var:eu5ab_layout_before }
            set_variable = { name = eu5ab_layout_result_net value = 0 }
            set_variable = { name = eu5ab_layout_result_kind value = 0 }
            remove_variable = eu5ab_layout_result_proposal
            if = {
                limit = { has_variable = eu5ab_layout_qualifies }
                set_variable = eu5ab_layout_result_proposal
                set_variable = { name = eu5ab_layout_result_after value = var:eu5ab_layout_after }
                set_variable = { name = eu5ab_layout_result_net value = var:eu5ab_layout_net }
                set_variable = { name = eu5ab_layout_result_kind value = var:eu5ab_layout_proposal_kind }
            }
            remove_variable = eu5ab_layout_has_results
            if = { limit = { var:eu5ab_layout_result_count > 0 } set_variable = eu5ab_layout_has_results }
            eu5ab_layout_refresh_page = yes
            eu5ab_layout_publish_candidates = yes
            if = {
                limit = { has_variable = eu5ab_governor_manual_run has_variable = eu5ab_layout_has_results }
                set_variable = eu5ab_layout_show_candidates
                remove_variable = eu5ab_layout_show_new
            }
            set_variable = { name = eu5ab_governor_last_run_year value = current_year }
            set_variable = { name = eu5ab_governor_months_since_refresh value = 0 }
            remove_variable = eu5ab_governor_scan_active
            remove_variable = eu5ab_governor_manual_run
            remove_variable = eu5ab_gov_inputs_ready
            set_variable = eu5ab_layout_ready
            eu5ab_layout_clear_liveness = yes
        }
    }
    }
}

eu5ab_layout_confirm = {
    remove_variable = eu5ab_layout_changed
    if = {
        limit = { OR = { NOT = { has_variable = eu5ab_layout_previous_seats } var:eu5ab_layout_previous_seats != var:eu5ab_layout_seats } }
        set_variable = eu5ab_layout_changed
    }
    set_variable = { name = eu5ab_layout_previous_seats value = var:eu5ab_layout_seats }
    every_owned_location = {
        if = {
            limit = {
                OR = {
                    AND = { has_variable = eu5ab_layout_selected NOT = { has_variable = eu5ab_layout_previous_target } }
                    AND = { NOT = { has_variable = eu5ab_layout_selected } has_variable = eu5ab_layout_previous_target }
                    AND = { has_variable = eu5ab_layout_old NOT = { has_variable = eu5ab_layout_previous_old } }
                    AND = { NOT = { has_variable = eu5ab_layout_old } has_variable = eu5ab_layout_previous_old }
                }
            }
            root = { set_variable = eu5ab_layout_changed }
        }
        remove_variable = eu5ab_layout_previous_target
        remove_variable = eu5ab_layout_previous_old
        if = { limit = { has_variable = eu5ab_layout_selected } set_variable = eu5ab_layout_previous_target }
        if = { limit = { has_variable = eu5ab_layout_old } set_variable = eu5ab_layout_previous_old }
    }
    if = {
        limit = { NOT = { has_variable = eu5ab_layout_qualifies } }
        remove_variable = eu5ab_layout_confirmation_streak
        remove_variable = eu5ab_local_has_migration
        cmf_remove_alert = { alert = eu5ab_local_governor_relocation_alert }
    }
    else_if = {
        # An explicit request publishes a qualifying plan immediately. The
        # confirmation/cooldown rules below apply only to unsolicited alerts.
        limit = { has_variable = eu5ab_governor_manual_run }
        remove_variable = eu5ab_layout_confirmation_streak
        set_variable = eu5ab_local_has_migration
        cmf_remove_alert = { alert = eu5ab_local_governor_relocation_alert }
        cmf_show_alert = { alert = eu5ab_local_governor_relocation_alert }
    }
    else = {
        if = {
            limit = { OR = { has_variable = eu5ab_layout_changed NOT = { has_variable = eu5ab_layout_confirmation_streak } } }
            set_variable = { name = eu5ab_layout_confirmation_streak value = 1 }
            remove_variable = eu5ab_local_has_migration
            cmf_remove_alert = { alert = eu5ab_local_governor_relocation_alert }
        }
        else = { change_variable = { name = eu5ab_layout_confirmation_streak add = 1 } }
        if = {
            limit = {
                var:eu5ab_layout_confirmation_streak >= 2
                NOT = { has_variable = eu5ab_local_has_migration }
                OR = { NOT = { has_variable = eu5ab_local_migration_cooldown } var:eu5ab_local_migration_cooldown <= 0 }
            }
            set_variable = eu5ab_local_has_migration
            set_variable = { name = eu5ab_local_migration_cooldown value = 12 }
            cmf_show_alert = { alert = eu5ab_local_governor_relocation_alert }
        }
    }
}

eu5ab_layout_publish_rows = {
    set_variable = { name = eu5ab_layout_result_count value = 0 }
    every_owned_location = {
        remove_variable = eu5ab_layout_row_order
        remove_variable = eu5ab_layout_row_to
        remove_variable = eu5ab_layout_row_gain
        remove_variable = eu5ab_layout_matched
        remove_variable = eu5ab_layout_display
        if = {
            limit = { root = { has_variable = eu5ab_layout_qualifies } has_variable = eu5ab_layout_selected }
            set_variable = eu5ab_layout_display
        }
        else_if = {
            limit = { root = { NOT = { has_variable = eu5ab_layout_qualifies } } has_variable = eu5ab_layout_old }
            set_variable = eu5ab_layout_display
        }
        # Reserve retained origins before matching ANY new destination.
        if = { limit = { has_variable = eu5ab_layout_old has_variable = eu5ab_layout_display } set_variable = eu5ab_layout_matched }
    }
    ordered_owned_location = {
        limit = { has_variable = eu5ab_layout_display }
        order_by = var:eu5ab_layout_band_order
        # Ordered effects default to one item, not the whole filtered list.
        max = var:eu5ab_layout_seats
        check_range_bounds = no
        save_temporary_scope_as = eu5ab_layout_row_destination
        root = {
            change_variable = { name = eu5ab_layout_result_count add = 1 }
            if = {
                limit = { scope:eu5ab_layout_row_destination = { has_variable = eu5ab_layout_old } }
                scope:eu5ab_layout_row_destination = { eu5ab_layout_store_row = yes }
            }
            else = {
                every_owned_location = {
                    limit = { has_variable = eu5ab_layout_old NOT = { has_variable = eu5ab_layout_matched } }
                    set_variable = { name = eu5ab_layout_match_score value = { value = var:eu5ab_layout_distance subtract = scope:eu5ab_layout_row_destination.var:eu5ab_layout_distance } }
                    if = { limit = { var:eu5ab_layout_match_score > 0 } change_variable = { name = eu5ab_layout_match_score multiply = -1 } }
                }
                ordered_owned_location = {
                    limit = { has_variable = eu5ab_layout_old NOT = { has_variable = eu5ab_layout_matched } }
                    order_by = var:eu5ab_layout_match_score
                    max = 1
                    eu5ab_layout_store_row = yes
                }
            }
        }
    }
    set_variable = { name = eu5ab_layout_page value = 0 }
}

eu5ab_layout_store_row = {
    set_variable = eu5ab_layout_matched
    set_variable = { name = eu5ab_layout_row_order value = root.var:eu5ab_layout_result_count }
    set_variable = { name = eu5ab_layout_row_to value = scope:eu5ab_layout_row_destination }
    set_variable = { name = eu5ab_layout_row_gain value = 0 }
    if = {
        limit = { root = { has_variable = eu5ab_layout_qualifies } }
        if = {
            limit = { root.var:eu5ab_layout_proposal_kind = 2 }
            # Single swaps have a conditional gain, not a greedy-round gain.
            remove_variable = eu5ab_layout_row_gain
        }
        else = { set_variable = { name = eu5ab_layout_row_gain value = scope:eu5ab_layout_row_destination.var:eu5ab_layout_planning_gain } }
    }
}

# Validate the one-to-one origin/destination mapping before publishing scores
# or showing an alert. Counting the destinations alone misses failed matches.
eu5ab_layout_validate_rows = {
    remove_variable = eu5ab_layout_invalid_rows
    set_variable = { name = eu5ab_layout_display_count value = 0 }
    set_variable = { name = eu5ab_layout_stored_rows value = 0 }
    set_variable = { name = eu5ab_layout_validated_moves value = 0 }
    every_owned_location = {
        remove_variable = eu5ab_layout_row_destination_seen
        if = {
            limit = { has_variable = eu5ab_layout_display }
            root = { change_variable = { name = eu5ab_layout_display_count add = 1 } }
        }
        if = {
            limit = {
                has_variable = eu5ab_layout_old
                OR = { NOT = { has_variable = eu5ab_layout_row_order } NOT = { has_variable = eu5ab_layout_row_to } }
            }
            root = { set_variable = eu5ab_layout_invalid_rows }
        }
    }
    every_owned_location = {
        limit = { has_variable = eu5ab_layout_row_order }
        root = { change_variable = { name = eu5ab_layout_stored_rows add = 1 } }
        if = {
            limit = {
                OR = {
                    NOT = { has_variable = eu5ab_layout_old }
                    NOT = { has_variable = eu5ab_layout_row_to }
                    var:eu5ab_layout_row_order < 1
                    var:eu5ab_layout_row_order > root.var:eu5ab_layout_result_count
                }
            }
            root = { set_variable = eu5ab_layout_invalid_rows }
        }
        if = {
            limit = { has_variable = eu5ab_layout_row_to }
            if = {
                limit = { this != var:eu5ab_layout_row_to }
                root = { change_variable = { name = eu5ab_layout_validated_moves add = 1 } }
            }
            var:eu5ab_layout_row_to = {
                if = {
                    limit = {
                        OR = { NOT = { owner ?= root } NOT = { has_variable = eu5ab_layout_display } has_variable = eu5ab_layout_row_destination_seen }
                    }
                    root = { set_variable = eu5ab_layout_invalid_rows }
                }
                set_variable = eu5ab_layout_row_destination_seen
            }
        }
    }
    every_owned_location = {
        if = {
            limit = { has_variable = eu5ab_layout_display NOT = { has_variable = eu5ab_layout_row_destination_seen } }
            root = { set_variable = eu5ab_layout_invalid_rows }
        }
        remove_variable = eu5ab_layout_row_destination_seen
    }
    if = {
        limit = {
            OR = {
                var:eu5ab_layout_result_count != var:eu5ab_layout_seats
                var:eu5ab_layout_display_count != var:eu5ab_layout_seats
                var:eu5ab_layout_stored_rows != var:eu5ab_layout_seats
                AND = { has_variable = eu5ab_layout_qualifies var:eu5ab_layout_validated_moves = 0 }
                AND = { NOT = { has_variable = eu5ab_layout_qualifies } var:eu5ab_layout_validated_moves > 0 }
            }
        }
        set_variable = eu5ab_layout_invalid_rows
    }
}
'''


def render_layout_queue_effects(planner: PlannerType = LOCAL_PLANNER) -> str:
    batch = '''while = {
                limit = { has_variable = eu5ab_gov_queue_head var:eu5ab_layout_wave_work < var:eu5ab_layout_wave_budget }
                count = @WORK@
                @RELAX@ = yes
            }'''
    text = r'''# A GUI pulse performs at most 64 queue or reduction operations.
# No game building is changed. All locations below belong to the snapshot country.
eu5ab_layout_reset_wave = {
    remove_variable = eu5ab_gov_queue_head
    remove_variable = eu5ab_gov_queue_tail
    clear_variable_list = eu5ab_gov_eval_locations
    change_variable = { name = eu5ab_gov_eval_generation add = 1 }
    set_variable = { name = eu5ab_layout_pending_nodes value = 0 }
    set_variable = { name = eu5ab_layout_footprint_nodes value = 0 }
    set_variable = { name = eu5ab_layout_wave_work value = 0 }
    set_variable = { name = eu5ab_layout_phase value = 1 }
}

eu5ab_layout_visit = {
    set_variable = { name = eu5ab_gov_visit_generation value = root.var:eu5ab_gov_eval_generation }
    set_variable = { name = eu5ab_gov_predicted value = 0 }
    save_temporary_scope_as = eu5ab_layout_visited
    root = {
        add_to_variable_list = { name = eu5ab_gov_eval_locations target = scope:eu5ab_layout_visited }
        change_variable = { name = eu5ab_layout_footprint_nodes add = 1 }
    }
}

eu5ab_layout_seed = {
    if = {
        limit = { local_var:eu5ab_layout_seed_value > 0 }
        eu5ab_layout_visit = yes
        set_variable = { name = eu5ab_gov_predicted value = local_var:eu5ab_layout_seed_value }
        eu5ab_governor_queue_enqueue = yes
    }
}

eu5ab_layout_relax_one = {
    var:eu5ab_gov_queue_head = {
        save_temporary_scope_as = eu5ab_gov_edge_from
        if = {
            limit = { has_variable = eu5ab_gov_queue_next }
            root = { set_variable = { name = eu5ab_gov_queue_head value = prev.var:eu5ab_gov_queue_next } }
        }
        else = { root = { remove_variable = eu5ab_gov_queue_head remove_variable = eu5ab_gov_queue_tail } }
        remove_variable = eu5ab_gov_queue_next
        remove_variable = eu5ab_gov_in_queue
        every_neighbor_location = {
            limit = {
                is_ownable = yes
                owner ?= root
                @CONNECTION_FILTER@
            }
            if = {
                limit = { var:eu5ab_gov_visit_generation != root.var:eu5ab_gov_eval_generation }
                eu5ab_layout_visit = yes
            }
            set_local_variable = { name = eu5ab_layout_relaxed value = eu5ab_governor_actual_land_edge_prediction }
            if = {
                limit = { local_var:eu5ab_layout_relaxed > var:eu5ab_gov_predicted }
                set_variable = { name = eu5ab_gov_predicted value = local_var:eu5ab_layout_relaxed }
                eu5ab_governor_queue_enqueue = yes
            }
            remove_local_variable = eu5ab_layout_relaxed
        }
@LAKE_RELAX@
    }
    change_variable = { name = eu5ab_layout_wave_work add = 1 }
    change_variable = { name = eu5ab_layout_total_work add = 1 }
}

eu5ab_layout_collect_one = {
    if = {
        limit = { root.var:eu5ab_layout_mode = 1 }
        # A high seed transforms propagation into shortest transport cost.
        # The watchdog rejects unfinished waves instead of truncating distance.
        set_variable = { name = eu5ab_layout_distance value = { value = 1000000 subtract = var:eu5ab_gov_predicted } }
        set_variable = { name = eu5ab_layout_band value = { value = var:eu5ab_layout_distance divide = 40 floor = yes } }
        set_variable = { name = eu5ab_layout_band_order value = { value = 0 subtract = var:eu5ab_layout_band } }
    }
    else_if = {
        limit = { root.var:eu5ab_layout_mode = 2 }
        set_variable = { name = eu5ab_layout_base value = var:eu5ab_gov_predicted }
        set_variable = { name = eu5ab_layout_virtual value = var:eu5ab_gov_predicted }
    }
    else_if = {
        limit = { root.var:eu5ab_layout_mode = 3 }
        root = {
            change_variable = {
                name = eu5ab_layout_before
                add = { value = prev.var:eu5ab_gov_predicted subtract = prev.var:eu5ab_layout_base min = 0 divide = 100 multiply = prev.var:eu5ab_gov_node_value }
            }
        }
        set_variable = { name = eu5ab_layout_current value = var:eu5ab_gov_predicted }
    }
    else_if = {
        limit = { root.var:eu5ab_layout_mode = 5 }
        # Keep two distinct old sources. Ties give zero exclusive contribution.
        if = {
            limit = { var:eu5ab_gov_predicted > var:eu5ab_layout_best_governor }
            set_variable = { name = eu5ab_layout_second_governor value = var:eu5ab_layout_best_governor }
            set_variable = { name = eu5ab_layout_best_governor value = var:eu5ab_gov_predicted }
            set_variable = { name = eu5ab_layout_best_origin value = root.var:eu5ab_layout_source_origin }
        }
        else_if = {
            limit = { var:eu5ab_gov_predicted > var:eu5ab_layout_second_governor }
            set_variable = { name = eu5ab_layout_second_governor value = var:eu5ab_gov_predicted }
        }
    }
    else_if = {
        limit = { root.var:eu5ab_layout_mode = 6 }
        set_variable = { name = eu5ab_layout_retained value = var:eu5ab_gov_predicted }
    }
    else_if = {
        limit = { root.var:eu5ab_layout_mode = 7 }
        set_variable = { name = eu5ab_layout_virtual value = var:eu5ab_gov_predicted }
    }
    else = {
        root = {
            change_variable = {
                name = eu5ab_layout_evaluated_gain
                add = { value = prev.var:eu5ab_gov_predicted subtract = prev.var:eu5ab_layout_virtual min = 0 divide = 100 multiply = prev.var:eu5ab_gov_node_value }
            }
        }
        if = {
            limit = { root = { has_variable = eu5ab_layout_compare_single } }
            eu5ab_layout_collect_single_gain = yes
        }
    }
    root = { change_variable = { name = eu5ab_layout_pending_nodes subtract = 1 } }
}

eu5ab_layout_start_source_wave = {
    eu5ab_layout_reset_wave = yes
    every_owned_location = {
        set_local_variable = { name = eu5ab_layout_seed_value value = var:eu5ab_layout_source }
        if = {
            limit = {
                has_variable = eu5ab_layout_old
                OR = {
                    root.var:eu5ab_layout_mode = 2
                    AND = {
                        OR = { root.var:eu5ab_layout_mode = 6 root.var:eu5ab_layout_mode = 7 }
                        NOT = { has_variable = eu5ab_layout_selected }
                    }
                }
            }
            change_local_variable = { name = eu5ab_layout_seed_value subtract = 80 }
        }
        if = {
            limit = { root.var:eu5ab_layout_mode = 7 has_variable = eu5ab_layout_selected NOT = { has_variable = eu5ab_layout_old } }
            change_local_variable = { name = eu5ab_layout_seed_value add = 80 }
        }
        set_local_variable = { name = eu5ab_layout_seed_value value = { value = local_var:eu5ab_layout_seed_value min = 0 max = 100 } }
        eu5ab_layout_seed = yes
        remove_local_variable = eu5ab_layout_seed_value
    }
}

eu5ab_layout_wave_finished = {
    if = {
        limit = { var:eu5ab_layout_mode = 1 }
        set_variable = { name = eu5ab_layout_mode value = 2 }
        eu5ab_layout_start_source_wave = yes
    }
    else_if = {
        limit = { var:eu5ab_layout_mode = 2 }
        set_variable = { name = eu5ab_layout_mode value = 3 }
        eu5ab_layout_start_source_wave = yes
    }
    else_if = {
        limit = { var:eu5ab_layout_mode = 3 }
        eu5ab_layout_next_old_source = yes
    }
    else_if = {
        limit = { var:eu5ab_layout_mode = 5 }
        eu5ab_layout_next_old_source = yes
    }
    else_if = {
        limit = { var:eu5ab_layout_mode = 6 }
        set_variable = { name = eu5ab_layout_after value = 0 }
        set_variable = { name = eu5ab_layout_changed_contribution value = 0 }
        set_variable = { name = eu5ab_layout_pending_nodes value = num_locations }
        set_variable = { name = eu5ab_layout_phase value = 9 }
    }
    else_if = {
        limit = { var:eu5ab_layout_mode = 7 }
        set_variable = { name = eu5ab_layout_phase value = 5 }
    }
    else = {
        var:eu5ab_layout_candidate = {
            set_variable = { name = eu5ab_layout_upper_gain value = root.var:eu5ab_layout_evaluated_gain }
            set_variable = { name = eu5ab_layout_scored_round value = root.var:eu5ab_layout_round }
        }
        set_variable = { name = eu5ab_layout_last_footprint value = var:eu5ab_layout_candidate }
        set_variable = { name = eu5ab_layout_phase value = 3 }
        if = {
            limit = { has_variable = eu5ab_layout_force_keep }
            set_variable = { name = eu5ab_layout_pending_nodes value = var:eu5ab_layout_footprint_nodes }
            set_variable = { name = eu5ab_layout_phase value = 4 }
        }
        if = { limit = { has_variable = eu5ab_layout_single_only } set_variable = { name = eu5ab_layout_phase value = 7 } }
        if = {
            limit = { has_variable = eu5ab_layout_compare_single }
            set_variable = { name = eu5ab_layout_resume_phase value = var:eu5ab_layout_phase }
            set_variable = { name = eu5ab_layout_single_pending value = var:eu5ab_layout_seats }
            set_variable = { name = eu5ab_layout_phase value = 8 }
        }
    }
}

eu5ab_layout_evaluate_contender = {
    eu5ab_layout_reset_wave = yes
    set_variable = { name = eu5ab_layout_mode value = 4 }
    set_variable = { name = eu5ab_layout_evaluated_gain value = 0 }
    remove_variable = eu5ab_layout_compare_single
    set_variable = { name = eu5ab_layout_single_common value = 0 }
    change_variable = { name = eu5ab_layout_propagations add = 1 }
    var:eu5ab_layout_candidate = {
        if = {
            limit = { NOT = { has_variable = eu5ab_layout_old } NOT = { has_variable = eu5ab_layout_single_checked } }
            root = { set_variable = eu5ab_layout_compare_single }
        }
        set_local_variable = { name = eu5ab_layout_seed_value value = var:eu5ab_layout_source }
        if = { limit = { has_variable = eu5ab_layout_old } change_local_variable = { name = eu5ab_layout_seed_value subtract = 80 } }
        change_local_variable = { name = eu5ab_layout_seed_value add = 80 }
        set_local_variable = { name = eu5ab_layout_seed_value value = { value = local_var:eu5ab_layout_seed_value max = 100 } }
        eu5ab_layout_seed = yes
        remove_local_variable = eu5ab_layout_seed_value
    }
}

eu5ab_layout_choose = {
    if = {
        limit = { var:eu5ab_layout_round > var:eu5ab_layout_seats }
        set_variable = { name = eu5ab_layout_phase value = 7 }
    }
    else = {
        remove_variable = eu5ab_layout_candidate
        ordered_owned_location = {
            limit = { has_variable = eu5ab_layout_eligible NOT = { has_variable = eu5ab_layout_selected } var:eu5ab_layout_upper_gain >= root.var:eu5ab_layout_min_gain }
            order_by = var:eu5ab_layout_band_order
            max = 1
            root = { set_variable = { name = eu5ab_layout_inner_band value = prev.var:eu5ab_layout_band } }
        }
        ordered_owned_location = {
            limit = {
                has_variable = eu5ab_layout_eligible
                NOT = { has_variable = eu5ab_layout_selected }
                var:eu5ab_layout_band = root.var:eu5ab_layout_inner_band
                var:eu5ab_layout_upper_gain >= root.var:eu5ab_layout_min_gain
            }
            order_by = var:eu5ab_layout_upper_gain
            max = 1
            save_temporary_scope_as = eu5ab_layout_contender
            root = { set_variable = { name = eu5ab_layout_candidate value = scope:eu5ab_layout_contender } }
        }
        if = {
            limit = { has_variable = eu5ab_layout_candidate }
@RETAIN_TIES@
            if = {
                limit = {
                    var:eu5ab_layout_candidate = { var:eu5ab_layout_scored_round = root.var:eu5ab_layout_round }
                    var:eu5ab_layout_last_footprint ?= var:eu5ab_layout_candidate
                }
                set_variable = { name = eu5ab_layout_pending_nodes value = var:eu5ab_layout_footprint_nodes }
                set_variable = { name = eu5ab_layout_phase value = 4 }
            }
            else = { eu5ab_layout_evaluate_contender = yes }
        }
        else = {
            # No remaining site clears the initial-build threshold. Retain an
            # old site, including its real (possibly small) modeled coverage.
            ordered_owned_location = {
                limit = { has_variable = eu5ab_layout_old NOT = { has_variable = eu5ab_layout_selected } }
                order_by = var:eu5ab_layout_band_order
                max = 1
                save_temporary_scope_as = eu5ab_layout_keep
                root = { set_variable = { name = eu5ab_layout_candidate value = scope:eu5ab_layout_keep } }
            }
            set_variable = eu5ab_layout_force_keep
            eu5ab_layout_evaluate_contender = yes
        }
    }
}

eu5ab_layout_apply_one = {
    if = {
        limit = { var:eu5ab_gov_predicted > var:eu5ab_layout_virtual }
        set_variable = { name = eu5ab_layout_virtual value = var:eu5ab_gov_predicted }
    }
    root = { change_variable = { name = eu5ab_layout_pending_nodes subtract = 1 } }
}

eu5ab_layout_abort = {
    set_variable = { name = eu5ab_gov_refresh_phase value = 0 }
    remove_variable = eu5ab_gov_inputs_ready
    remove_variable = eu5ab_gov_refresh_run_layout
    remove_variable = eu5ab_gov_refresh_cursor
    remove_variable = eu5ab_layout_cursor
    remove_variable = eu5ab_governor_scan_active
    remove_variable = eu5ab_governor_manual_run
    remove_variable = eu5ab_governor_resume_manual
    eu5ab_layout_clear_liveness = yes
    set_variable = eu5ab_layout_failed
    remove_variable = eu5ab_gov_queue_head
    remove_variable = eu5ab_gov_queue_tail
    every_in_list = {
        variable = eu5ab_gov_eval_locations
        remove_variable = eu5ab_gov_queue_next
        remove_variable = eu5ab_gov_in_queue
    }
    clear_variable_list = eu5ab_gov_eval_locations
    # Keep previously published rows; this incomplete attempt isn't confirmation.
    remove_variable = eu5ab_layout_confirmation_streak
    remove_variable = eu5ab_local_has_migration
    cmf_remove_alert = { alert = eu5ab_local_governor_relocation_alert }
}

eu5ab_layout_tick = {
    eu5ab_governor_check_transport_rules = yes
    if = {
        limit = { var:eu5ab_gov_refresh_phase > 0 has_variable = eu5ab_governor_scan_active }
        eu5ab_governor_refresh_tick = yes
    }
    else_if = {
        limit = { NOT = { has_variable = eu5ab_governor_scan_active } }
        eu5ab_layout_recover_transport_restart = yes
    }
    else_if = {
        limit = { has_variable = eu5ab_governor_scan_active }
        change_variable = { name = eu5ab_layout_ticks add = 1 }
        if = {
            limit = { OR = { num_locations != var:eu5ab_layout_snapshot_count capital != var:eu5ab_layout_snapshot_capital } }
            eu5ab_layout_abort = yes
        }
        else_if = {
            limit = { NOT = { var:eu5ab_global_governor_relocation_enabled > 0 } }
            eu5ab_governor_disable_migration = yes
        }
        else_if = {
            limit = { NOT = { var:eu5ab_global_governor_migration_enabled > 0 } NOT = { has_variable = eu5ab_governor_manual_run } }
            eu5ab_governor_stop_auto_migration = yes
        }
        else_if = {
            limit = { var:eu5ab_global_governor_recommendations_enabled <= 0 NOT = { has_variable = eu5ab_governor_manual_run } }
            eu5ab_layout_abort = yes
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 1 }
            if = {
                limit = { var:eu5ab_gov_transport_road_tier > 0 }
                @PLANNED_BATCH@
            }
            else = { @ACTUAL_BATCH@ }
            if = {
                limit = { NOT = { has_variable = eu5ab_gov_queue_head } }
                set_variable = { name = eu5ab_layout_pending_nodes value = var:eu5ab_layout_footprint_nodes }
                set_variable = { name = eu5ab_layout_phase value = 2 }
            }
            else_if = {
                limit = { var:eu5ab_layout_wave_work >= var:eu5ab_layout_wave_budget }
                eu5ab_layout_abort = yes
            }
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 2 }
            ordered_in_list = {
                variable = eu5ab_gov_eval_locations
                order_by = 1
                max = @WORK@
                check_range_bounds = no
                eu5ab_layout_collect_one = yes
            }
            if = { limit = { var:eu5ab_layout_pending_nodes = 0 } eu5ab_layout_wave_finished = yes }
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 3 }
            eu5ab_layout_choose = yes
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 4 }
            ordered_in_list = {
                variable = eu5ab_gov_eval_locations
                order_by = 1
                max = @WORK@
                check_range_bounds = no
                eu5ab_layout_apply_one = yes
            }
            if = {
                limit = { var:eu5ab_layout_pending_nodes = 0 }
                var:eu5ab_layout_candidate = {
                    set_variable = { name = eu5ab_layout_selected value = root.var:eu5ab_layout_round }
                    set_variable = { name = eu5ab_layout_planning_gain value = var:eu5ab_layout_upper_gain }
                }
                change_variable = { name = eu5ab_layout_round add = 1 }
                change_variable = { name = eu5ab_layout_completed add = 1 }
                remove_variable = eu5ab_layout_force_keep
                set_variable = { name = eu5ab_layout_phase value = 3 }
            }
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 5 }
            eu5ab_layout_publish = yes
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 6 }
            ordered_owned_location = {
                order_by = 1
                max = @WORK@
                check_range_bounds = no
                eu5ab_layout_collect_exclusive = yes
            }
            if = { limit = { var:eu5ab_layout_pending_nodes = 0 } set_variable = { name = eu5ab_layout_phase value = 3 } }
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 7 }
            eu5ab_layout_find_unchecked_candidate = yes
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 8 }
            ordered_owned_location = {
                limit = { has_variable = eu5ab_layout_old var:eu5ab_layout_compared_generation != root.var:eu5ab_gov_eval_generation }
                order_by = var:eu5ab_layout_band_order
                max = @WORK@
                check_range_bounds = no
                eu5ab_layout_compare_old_seat = yes
            }
            if = {
                limit = { var:eu5ab_layout_single_pending = 0 }
                var:eu5ab_layout_candidate = { set_variable = eu5ab_layout_single_checked }
                change_variable = { name = eu5ab_layout_single_candidates add = 1 }
                remove_variable = eu5ab_layout_compare_single
                set_variable = { name = eu5ab_layout_phase value = var:eu5ab_layout_resume_phase }
            }
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 9 }
            ordered_owned_location = {
                order_by = 1
                max = @WORK@
                check_range_bounds = no
                eu5ab_layout_reduce_full_plan = yes
            }
            if = { limit = { var:eu5ab_layout_pending_nodes = 0 } eu5ab_layout_select_proposal = yes }
        }
        else_if = {
            limit = { var:eu5ab_layout_phase = 10 }
            ordered_owned_location = {
                order_by = 1
                max = @WORK@
                check_range_bounds = no
                eu5ab_layout_prepare_single_winner = yes
            }
            if = {
                limit = { var:eu5ab_layout_pending_nodes = 0 }
                set_variable = { name = eu5ab_layout_mode value = 7 }
                eu5ab_layout_start_source_wave = yes
            }
        }
        else = { eu5ab_layout_abort = yes }
    }
}

# One pending event per country survives save/load and manual restarts.
eu5ab_layout_schedule_watchdog = {
    if = {
        limit = {
            is_human = yes
            has_variable = eu5ab_governor_scan_active
            NOT = { has_variable = eu5ab_layout_watchdog_scheduled }
        }
        set_variable = eu5ab_layout_watchdog_scheduled
        trigger_event_silently = { id = eu5ab_governor.2 days = 1 }
    }
}

eu5ab_layout_watchdog = {
    remove_variable = eu5ab_layout_watchdog_scheduled
    if = {
        limit = { is_human = yes has_variable = eu5ab_governor_scan_active }
        if = {
            limit = {
                OR = {
                    NOT = { has_variable = eu5ab_layout_ticks }
                    NOT = { has_variable = eu5ab_layout_watchdog_last_ticks }
                    var:eu5ab_layout_ticks = var:eu5ab_layout_watchdog_last_ticks
                }
            }
            # One bounded tick per fallback event; GUI and manual use the same work.
            change_variable = { name = eu5ab_layout_fallback_batches add = 1 }
            while = {
                limit = { has_variable = eu5ab_governor_scan_active }
                count = 1
                eu5ab_layout_tick = yes
            }
        }
        set_variable = { name = eu5ab_layout_watchdog_last_ticks value = var:eu5ab_layout_ticks }
        eu5ab_layout_schedule_watchdog = yes
    }
}
'''.replace("@PLANNED_BATCH@", batch.replace("@RELAX@", "eu5ab_layout_relax_one_planned")).replace(
        "@ACTUAL_BATCH@", batch.replace("@RELAX@", "eu5ab_layout_relax_one")).replace(
        "@WORK@", str(WORK_PER_PULSE)).replace("@RETAIN_TIES@", "" if planner.capital_bands else '''            var:eu5ab_layout_candidate = { set_local_variable = { name = eu5ab_layout_tied_gain value = var:eu5ab_layout_upper_gain } }
            ordered_owned_location = {
                limit = { has_variable = eu5ab_layout_old NOT = { has_variable = eu5ab_layout_selected } var:eu5ab_layout_upper_gain = local_var:eu5ab_layout_tied_gain }
                order_by = 1
                max = 1
                save_temporary_scope_as = eu5ab_layout_tied_old
                root = { set_variable = { name = eu5ab_layout_candidate value = scope:eu5ab_layout_tied_old } }
            }
            remove_local_variable = eu5ab_layout_tied_gain''').replace("@LAKE_RELAX@", render_lake_relaxation(layout=True)).replace(
        "@CONNECTION_FILTER@", "" if planner.allow_straits else
        "NOT = { eu5ab_is_strait_connection_to = { target = scope:eu5ab_gov_edge_from } }")

    # Planned land cost depends only on the source. Recompute after every pop,
    # since a later improvement can enqueue the same source again in this wave.
    planned = script_definition(text, "eu5ab_layout_relax_one").replace(
        "eu5ab_layout_relax_one = {", "eu5ab_layout_relax_one_planned = {")
    edge_value = "            set_local_variable = { name = eu5ab_layout_relaxed value = eu5ab_governor_actual_land_edge_prediction }"
    if planner.allow_straits:
        planned = planned.replace(edge_value, '''            if = {
                limit = { eu5ab_is_strait_connection_to = { target = scope:eu5ab_gov_edge_from } }
                set_local_variable = { name = eu5ab_layout_relaxed value = eu5ab_governor_actual_land_edge_prediction }
            }
            else = { set_local_variable = { name = eu5ab_layout_relaxed value = local_var:eu5ab_layout_source_prediction } }''')
    else:
        planned = planned.replace(edge_value + "\n", "").replace(
            "            remove_local_variable = eu5ab_layout_relaxed\n", "").replace(
            "local_var:eu5ab_layout_relaxed", "local_var:eu5ab_layout_source_prediction")
    planned = planned.replace("        every_neighbor_location = {", '''        set_local_variable = {
            name = eu5ab_layout_source_prediction
            value = { value = var:eu5ab_gov_predicted subtract = var:eu5ab_gov_planned_road_cost min = 0 }
        }
        every_neighbor_location = {''', 1).replace(
            "    change_variable = { name = eu5ab_layout_wave_work", "    remove_local_variable = eu5ab_layout_source_prediction\n    change_variable = { name = eu5ab_layout_wave_work")
    if not planner.allow_straits:
        # All planned land edges from this source share one nonnegative value.
        # Zero cannot improve any node; avoid visiting a zero-valued boundary
        # ring and reducing it again. Lake transit remains outside this guard:
        # its cost is different and it may still carry positive proximity.
        before, neighbors, after = split_block(planned, "        every_neighbor_location = {")
        planned = before + '''        if = {
            limit = { local_var:eu5ab_layout_source_prediction > 0 }
            every_neighbor_location = {''' + neighbors + '''}
        }''' + after
    return text + "\n" + planned


def render_layout_relocation_effects() -> str:
    return r'''# One wave per old source builds its exclusive contribution. Each new
# candidate footprint then evaluates all single replacements without repropagating
# the retained empire. All point and old-seat reductions run in bounded batches.
eu5ab_layout_recover_transport_restart = {
    if = {
        limit = { has_variable = eu5ab_governor_resume_manual }
        set_variable = eu5ab_governor_manual_run
        remove_variable = eu5ab_governor_resume_manual
    }
    if = {
        limit = {
            is_human = yes
            has_variable = eu5ab_governor_dirty
            OR = { var:eu5ab_global_governor_recommendations_enabled > 0 has_variable = eu5ab_governor_manual_run }
        }
        # Recovery must not turn an automatic job into a manual override.
        if = {
            limit = { has_variable = eu5ab_governor_recalculation_scheduled }
            set_variable = eu5ab_governor_skip_next_scheduled_event
        }
        eu5ab_governor_run_recalculation_now = yes
    }
}

eu5ab_layout_next_old_source = {
    remove_variable = eu5ab_layout_source_origin
    ordered_owned_location = {
        limit = { has_variable = eu5ab_layout_old NOT = { has_variable = eu5ab_layout_old_wave_done } }
        order_by = var:eu5ab_layout_band_order
        max = 1
        set_variable = eu5ab_layout_old_wave_done
        save_temporary_scope_as = eu5ab_layout_old_source
        root = { set_variable = { name = eu5ab_layout_source_origin value = scope:eu5ab_layout_old_source } }
    }
    if = {
        limit = { has_variable = eu5ab_layout_source_origin }
        eu5ab_layout_reset_wave = yes
        set_variable = { name = eu5ab_layout_mode value = 5 }
        var:eu5ab_layout_source_origin = {
            # Preserve other source buildings sharing this old seat.
            set_local_variable = { name = eu5ab_layout_seed_value value = { value = var:eu5ab_layout_source min = 0 max = 100 } }
            eu5ab_layout_seed = yes
            remove_local_variable = eu5ab_layout_seed_value
        }
    }
    else = {
        set_variable = { name = eu5ab_layout_pending_nodes value = num_locations }
        set_variable = { name = eu5ab_layout_phase value = 6 }
    }
}

eu5ab_layout_collect_exclusive = {
    if = {
        limit = { has_variable = eu5ab_layout_best_origin }
        set_local_variable = {
            name = eu5ab_layout_exclusive_gain
            value = {
                value = var:eu5ab_layout_current
                subtract = { value = var:eu5ab_layout_base min = var:eu5ab_layout_second_governor }
                min = 0 divide = 100 multiply = var:eu5ab_gov_node_value
            }
        }
        var:eu5ab_layout_best_origin = {
            change_variable = { name = eu5ab_layout_exclusive add = local_var:eu5ab_layout_exclusive_gain }
        }
        remove_local_variable = eu5ab_layout_exclusive_gain
    }
    root = { change_variable = { name = eu5ab_layout_pending_nodes subtract = 1 } }
}

eu5ab_layout_collect_single_gain = {
    set_local_variable = {
        name = eu5ab_layout_common_gain
        value = { value = var:eu5ab_gov_predicted subtract = var:eu5ab_layout_current min = 0 divide = 100 multiply = var:eu5ab_gov_node_value }
    }
    root = { change_variable = { name = eu5ab_layout_single_common add = local_var:eu5ab_layout_common_gain } }
    if = {
        limit = { has_variable = eu5ab_layout_best_origin }
        set_local_variable = {
            name = eu5ab_layout_recovery_gain
            value = {
                value = var:eu5ab_gov_predicted
                subtract = { value = var:eu5ab_layout_base min = var:eu5ab_layout_second_governor }
                min = 0 divide = 100 multiply = var:eu5ab_gov_node_value
                subtract = local_var:eu5ab_layout_common_gain
            }
        }
        var:eu5ab_layout_best_origin = {
            if = {
                limit = { var:eu5ab_layout_recovery_generation != root.var:eu5ab_gov_eval_generation }
                set_variable = { name = eu5ab_layout_recovery_generation value = root.var:eu5ab_gov_eval_generation }
                set_variable = { name = eu5ab_layout_recovery value = 0 }
            }
            change_variable = { name = eu5ab_layout_recovery add = local_var:eu5ab_layout_recovery_gain }
        }
        remove_local_variable = eu5ab_layout_recovery_gain
    }
    remove_local_variable = eu5ab_layout_common_gain
}

eu5ab_layout_compare_old_seat = {
    set_variable = { name = eu5ab_layout_compared_generation value = root.var:eu5ab_gov_eval_generation }
    set_local_variable = { name = eu5ab_layout_swap_net value = { value = root.var:eu5ab_layout_single_common subtract = var:eu5ab_layout_exclusive } }
    if = {
        limit = { var:eu5ab_layout_recovery_generation = root.var:eu5ab_gov_eval_generation }
        change_local_variable = { name = eu5ab_layout_swap_net add = var:eu5ab_layout_recovery }
    }
    # Save the best origin for every distinct destination, even below the gate.
    save_temporary_scope_as = eu5ab_layout_preview_origin
    root = {
        var:eu5ab_layout_candidate = {
            if = {
                limit = {
                    OR = {
                        NOT = { has_variable = eu5ab_layout_preview_net }
                        local_var:eu5ab_layout_swap_net > var:eu5ab_layout_preview_net
                    }
                }
                set_variable = { name = eu5ab_layout_preview_from value = scope:eu5ab_layout_preview_origin }
                set_variable = { name = eu5ab_layout_preview_before value = scope:eu5ab_layout_preview_origin.var:eu5ab_layout_exclusive }
                set_variable = { name = eu5ab_layout_preview_net value = local_var:eu5ab_layout_swap_net }
            }
        }
    }
    if = {
        limit = {
            local_var:eu5ab_layout_swap_net > root.var:eu5ab_layout_single_net
            local_var:eu5ab_layout_swap_net >= { value = var:eu5ab_layout_exclusive multiply = root.var:eu5ab_layout_threshold_percent divide = 100 }
        }
        save_temporary_scope_as = eu5ab_layout_swap_origin
        root = {
            set_variable = { name = eu5ab_layout_single_net value = local_var:eu5ab_layout_swap_net }
            set_variable = { name = eu5ab_layout_single_origin value = scope:eu5ab_layout_swap_origin }
            set_variable = { name = eu5ab_layout_single_target value = var:eu5ab_layout_candidate }
        }
    }
    remove_local_variable = eu5ab_layout_swap_net
    root = {
        change_variable = { name = eu5ab_layout_single_pending subtract = 1 }
        change_variable = { name = eu5ab_layout_single_comparisons add = 1 }
    }
}

eu5ab_layout_find_unchecked_candidate = {
    remove_variable = eu5ab_layout_candidate
    if = {
        limit = { var:eu5ab_layout_seats > 0 }
        ordered_owned_location = {
            limit = {
                NOT = { has_variable = eu5ab_layout_old }
                NOT = { has_variable = eu5ab_layout_single_checked }
                eu5ab_local_governor_candidate = yes
            }
            order_by = var:eu5ab_layout_band_order
            max = 1
            save_temporary_scope_as = eu5ab_layout_unchecked_candidate
            root = { set_variable = { name = eu5ab_layout_candidate value = scope:eu5ab_layout_unchecked_candidate } }
        }
    }
    if = {
        limit = { has_variable = eu5ab_layout_candidate }
        set_variable = eu5ab_layout_single_only
        eu5ab_layout_evaluate_contender = yes
    }
    else = {
        remove_variable = eu5ab_layout_single_only
        # Full-plan threshold excludes the contribution of retained old seats.
        set_variable = { name = eu5ab_layout_mode value = 6 }
        eu5ab_layout_start_source_wave = yes
    }
}

eu5ab_layout_reduce_full_plan = {
    root = {
        change_variable = {
            name = eu5ab_layout_after
            add = { value = prev.var:eu5ab_layout_virtual subtract = prev.var:eu5ab_layout_base min = 0 divide = 100 multiply = prev.var:eu5ab_gov_node_value }
        }
        change_variable = {
            name = eu5ab_layout_changed_contribution
            add = { value = prev.var:eu5ab_layout_current subtract = prev.var:eu5ab_layout_retained min = 0 divide = 100 multiply = prev.var:eu5ab_gov_node_value }
        }
        change_variable = { name = eu5ab_layout_pending_nodes subtract = 1 }
    }
}

eu5ab_layout_select_proposal = {
    set_variable = { name = eu5ab_layout_net value = { value = var:eu5ab_layout_after subtract = var:eu5ab_layout_before } }
    # Quantize the plan comparison to 0.00001 point for stable ties. This is
    # our deterministic comparison policy, not an assumption about the engine.
    set_local_variable = { name = eu5ab_layout_single_advantage value = { value = var:eu5ab_layout_single_net subtract = var:eu5ab_layout_net multiply = 100000 round = yes } }
    remove_variable = eu5ab_layout_full_qualifies
    if = {
        limit = {
            var:eu5ab_layout_net > 0
            var:eu5ab_layout_net >= { value = var:eu5ab_layout_changed_contribution multiply = var:eu5ab_layout_threshold_percent divide = 100 }
        }
        set_variable = eu5ab_layout_full_qualifies
    }
    if = {
        limit = {
            has_variable = eu5ab_layout_single_target
            OR = {
                NOT = { has_variable = eu5ab_layout_full_qualifies }
                local_var:eu5ab_layout_single_advantage > 0
            }
        }
        # Ties retain the qualifying full plan. Recompute winning coverage so
        # published scores and rows refer to exactly the same source set.
        set_variable = { name = eu5ab_layout_proposal_kind value = 2 }
        set_variable = { name = eu5ab_layout_changed_contribution value = var:eu5ab_layout_single_origin.var:eu5ab_layout_exclusive }
        set_variable = { name = eu5ab_layout_single_destination_gain value = { value = var:eu5ab_layout_single_net add = var:eu5ab_layout_changed_contribution } }
        set_variable = { name = eu5ab_layout_pending_nodes value = num_locations }
        set_variable = { name = eu5ab_layout_phase value = 10 }
    }
    else = { set_variable = { name = eu5ab_layout_phase value = 5 } }
    remove_local_variable = eu5ab_layout_single_advantage
}

eu5ab_layout_prepare_single_winner = {
    set_variable = { name = eu5ab_layout_virtual value = 0 }
    remove_variable = eu5ab_layout_selected
    remove_variable = eu5ab_layout_planning_gain
    if = {
        limit = { has_variable = eu5ab_layout_old this != root.var:eu5ab_layout_single_origin }
        set_variable = eu5ab_layout_selected
    }
    else_if = {
        limit = { this = root.var:eu5ab_layout_single_target }
        set_variable = eu5ab_layout_selected
    }
    root = { change_variable = { name = eu5ab_layout_pending_nodes subtract = 1 } }
}
'''


def render_layout_effects(planner: PlannerType = LOCAL_PLANNER, *, bind: bool = True) -> str:
    relocation = render_layout_relocation_effects()
    if planner.kind != "local":
        # Only the shared governor event is scheduled. A naval-only skip flag
        # has no consumer and must not be generated by the shared template.
        relocation = relocation.replace('''        if = {
            limit = { has_variable = eu5ab_governor_recalculation_scheduled }
            set_variable = eu5ab_governor_skip_next_scheduled_event
        }
''', '')
    text = (render_layout_start_effect(planner) + "\n" + render_layout_queue_effects(planner)
            + "\n" + relocation
            + "\n" + render_layout_publish_effects() + "\n" + render_layout_page_effect()
            + "\n" + render_preview_effects() + "\n" + render_liveness_effects())
    text = batch_layout_effects(text, WORK_PER_PULSE)
    if planner.kind != "local":
        text = text.replace("eu5ab_governor_snapshot_local_slot_state", "eu5ab_governor_snapshot_naval_slots")
        text = text.replace("building_type:local_governor", "building_type:naval_governor")
        text = text.replace("id = eu5ab_governor.2", "id = eu5ab_governor.3")
    return planner.bind(text) if bind else text
