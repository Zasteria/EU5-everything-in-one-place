"""Naval entry points; scoring, propagation, layouts and UI use shared templates."""
from .governor_planner import NAVAL_PLANNER, script_definition
from .governor_layout_generator import render_layout_effects
from .governor_refresh import integrate_refresh, add_footprint_links


def render_naval_effects(shared: str) -> str:
    helpers = (
        "clear_location_cache", "prepare_location_value", "queue_enqueue",
        "queue_relax_one", "evaluate_candidate", "snapshot_transport",
        "prepare_planned_naval_baseline", "prepare_planned_baseline_core",
        "store_local_rank", "rank_local_results", "evaluate_local_alerts",
        "clear_naval_results", "clear_local_migration",
    )
    text = "\n\n".join(script_definition(shared, "eu5ab_governor_" + name) for name in helpers)
    # The naval synchronous pass ranks all candidates directly and has no
    # cheap-score shortlist to clear.
    text = text.replace("\tremove_variable = eu5ab_local_cheap_score\n", "")
    text += r'''
eu5ab_governor_snapshot_naval_slots = {
    set_variable = { name = eu5ab_gov_fresh_naval_capacity value = modifier:num_naval_governors }
    set_variable = { name = eu5ab_gov_fresh_naval_occupied value = 0 }
    every_owned_location = {
        if = {
            limit = { OR = { has_building = building_type:naval_governor any_buildings_in_location = { building_type = building_type:naval_governor building_levels_under_construction > 0 } } }
            root = { change_variable = { name = eu5ab_gov_fresh_naval_occupied add = 1 } }
        }
    }
}

eu5ab_governor_refresh_other_recommendations = {
    eu5ab_governor_clear_naval_results = yes
    eu5ab_governor_snapshot_naval_slots = yes
    eu5ab_governor_snapshot_transport = yes
    remove_variable = eu5ab_governor_baseline_failed
    remove_variable = eu5ab_governor_queue_exhausted
    set_variable = { name = eu5ab_governor_total_value value = 0 }
    every_owned_location = {
        eu5ab_governor_clear_location_cache = yes
        eu5ab_governor_prepare_location_value = yes
    }
    eu5ab_governor_prepare_planned_naval_baseline = yes
    set_variable = { name = eu5ab_gov_sync_status value = 1 }
    if = {
        limit = { eu5ab_fresh_local_governor_slot_available = yes }
        set_variable = { name = eu5ab_gov_sync_status value = 2 }
        every_owned_location = {
            limit = { eu5ab_local_governor_candidate = yes root = { NOT = { has_variable = eu5ab_governor_baseline_failed } } }
            root = { set_variable = { name = eu5ab_gov_sync_status value = 3 } set_variable = { name = eu5ab_gov_eval_kind value = 2 } }
            eu5ab_governor_evaluate_candidate = yes
            set_variable = { name = eu5ab_local_score value = var:eu5ab_gov_eval_result_gain }
            set_variable = { name = eu5ab_local_site_gain value = var:eu5ab_gov_eval_result_site_gain }
            set_variable = { name = eu5ab_local_surrounding_gain value = var:eu5ab_gov_eval_result_surrounding_gain }
            set_variable = { name = eu5ab_local_coverage value = var:eu5ab_gov_eval_result_coverage }
        }
    }
    eu5ab_governor_rank_local_results = yes
    eu5ab_governor_evaluate_local_alerts = yes
    if = { limit = { has_variable = eu5ab_local_has_new_recommendation } set_variable = { name = eu5ab_gov_sync_status value = 5 } }
    if = {
        limit = { OR = { has_variable = eu5ab_governor_baseline_failed has_variable = eu5ab_governor_queue_exhausted } }
        set_variable = { name = eu5ab_gov_sync_status value = 4 }
    }
    else = { set_variable = { name = eu5ab_gov_result_road_tier value = var:eu5ab_gov_transport_road_tier } }
    set_variable = { name = eu5ab_governor_months_since_refresh value = 0 }
    remove_variable = eu5ab_governor_dirty
}

eu5ab_recalculate_governor_recommendations = {
    eu5ab_governor_refresh_other_recommendations = yes
    if = {
        limit = { var:eu5ab_global_governor_relocation_enabled > 0 OR = { var:eu5ab_global_governor_migration_enabled > 0 has_variable = eu5ab_governor_manual_run } }
        eu5ab_layout_begin = yes
    }
    else = { remove_variable = eu5ab_governor_scan_active remove_variable = eu5ab_governor_manual_run }
}

eu5ab_governor_run_recalculation_now = {
    if = {
        limit = { is_human = yes OR = { var:eu5ab_global_governor_recommendations_enabled > 0 has_variable = eu5ab_governor_manual_run } }
        if = { limit = { has_variable = eu5ab_governor_scan_active } set_variable = eu5ab_governor_dirty }
        else = { eu5ab_recalculate_governor_recommendations = yes }
    }
}

eu5ab_governor_manual_recalculation = {
    if = {
        limit = { is_human = yes }
        if = { limit = { has_variable = eu5ab_governor_scan_active } eu5ab_layout_abort = yes }
        set_variable = eu5ab_governor_manual_run
        set_variable = eu5ab_governor_manual_realert
        eu5ab_layout_clear_published_results = yes
        eu5ab_governor_clear_local_migration = yes
        eu5ab_recalculate_governor_recommendations = yes
        eu5ab_layout_finish_manual = yes
        remove_variable = eu5ab_governor_manual_realert
    }
}

eu5ab_governor_check_transport_rules = {
    if = {
        limit = { NOT = { has_variable = eu5ab_gov_transport_schema } }
        set_variable = eu5ab_governor_dirty
    }
    else_if = {
        limit = { var:eu5ab_gov_transport_schema != 2 }
        set_variable = eu5ab_governor_dirty
    }
    else_if = {
        limit = { NOT = { has_variable = eu5ab_gov_transport_road_tier } }
        set_variable = eu5ab_governor_dirty
    }
    else_if = {
        limit = { var:eu5ab_gov_transport_road_tier != eu5ab_governor_highest_road_tier }
        set_variable = eu5ab_governor_dirty
    }
}

eu5ab_governor_stop_auto_migration = {
    if = { limit = { has_variable = eu5ab_governor_scan_active NOT = { has_variable = eu5ab_governor_manual_run } } eu5ab_layout_abort = yes remove_variable = eu5ab_layout_failed }
    remove_variable = eu5ab_layout_confirmation_streak
}

eu5ab_governor_disable_migration = {
    if = { limit = { has_variable = eu5ab_governor_scan_active } eu5ab_layout_abort = yes }
    remove_variable = eu5ab_layout_failed
    eu5ab_layout_clear_published_results = yes
    eu5ab_governor_clear_local_migration = yes
    remove_variable = eu5ab_layout_confirmation_streak
}
'''
    text += "\n" + render_layout_effects(NAVAL_PLANNER, bind=False)
    # Naval scheduling uses its independent month counter, not the local
    # planner's calendar-year checkpoint.
    text = text.replace(
        "            set_variable = { name = eu5ab_governor_last_run_year value = current_year }\n",
        "",
    )
    # A failed naval refresh must not leave the road label from a prior result.
    text = text.replace(
        "eu5ab_governor_clear_naval_results = {\n",
        "eu5ab_governor_clear_naval_results = {\n\tremove_variable = eu5ab_gov_result_road_tier\n",
    )
    return NAVAL_PLANNER.bind(add_footprint_links(integrate_refresh(text, naval=True)))


def render_scheduled_planners() -> str:
    return '''# Snapshot dispatch intent before either consumer clears its own dirty flag.
eu5ab_governor_run_scheduled_planners = {
    eu5ab_governor_ensure_planner_schema = yes
    set_local_variable = { name = eu5ab_refresh_local value = 0 }
    set_local_variable = { name = eu5ab_refresh_naval value = 0 }
    if = {
        limit = { OR = { has_variable = eu5ab_governor_dirty has_variable = eu5ab_naval_planner_dirty } }
        if = { limit = { has_variable = eu5ab_governor_dirty } set_local_variable = { name = eu5ab_refresh_local value = 1 } }
        if = { limit = { has_variable = eu5ab_naval_planner_dirty } set_local_variable = { name = eu5ab_refresh_naval value = 1 } }
    }
    else = {
        set_local_variable = { name = eu5ab_refresh_local value = 1 }
        set_local_variable = { name = eu5ab_refresh_naval value = 1 }
    }
    if = { limit = { local_var:eu5ab_refresh_local = 1 } eu5ab_governor_run_recalculation_now = yes }
    if = { limit = { local_var:eu5ab_refresh_naval = 1 } eu5ab_naval_planner_run_recalculation_now = yes }
    remove_local_variable = eu5ab_refresh_local
    remove_local_variable = eu5ab_refresh_naval
}
'''
