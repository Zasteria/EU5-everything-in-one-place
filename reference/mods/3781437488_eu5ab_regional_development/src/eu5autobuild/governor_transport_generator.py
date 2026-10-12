"""Generate source-scoped transport snapshots and highest-road planning values.

Schema 2 separates speed from terrain and cannot be replayed as the old
destination-factor cache. Water connections never receive hypothetical roads.
"""


def render_transport_values() -> str:
    common_values = r'''
# Country scope. Unlocks, not the roads already built, define the planning tier.
eu5ab_governor_highest_road_tier = {
    value = 0
    if = { limit = { has_advance = railroad_advance } value = 4 }
    else_if = { limit = { has_advance = modern_road_advance } value = 3 }
    else_if = { limit = { has_advance = paved_road_advance } value = 2 }
    else_if = { limit = { has_advance = road_building } value = 1 }
}

eu5ab_governor_topography_penalty = {
    value = 0
    if = { limit = { topography = mountains } value = -0.5 }
    else_if = { limit = { topography = hills } value = -0.25 }
    else_if = { limit = { topography = plateau } value = -0.125 }
    else_if = { limit = { topography = wetlands } value = -0.25 }
}
eu5ab_governor_topography_impact = {
    value = 0
    if = { limit = { topography = mountains } value = owner.modifier:mountains_proximity_impact }
    else_if = { limit = { topography = hills } value = owner.modifier:hills_proximity_impact }
    else_if = { limit = { topography = plateau } value = owner.modifier:plateau_proximity_impact }
    else_if = { limit = { topography = wetlands } value = owner.modifier:wetlands_proximity_impact }
}
eu5ab_governor_vegetation_penalty = {
    value = 0
    if = { limit = { vegetation = desert } value = -0.05 }
    else_if = { limit = { vegetation = farmland } value = -0.05 }
    else_if = { limit = { vegetation = woods } value = -0.125 }
    else_if = { limit = { vegetation = forest } value = -0.25 }
    else_if = { limit = { vegetation = jungle } value = -0.5 }
}
eu5ab_governor_transport_speed = {
    value = 1
    add = root.var:eu5ab_gov_cached_global_speed
    add = root.var:eu5ab_gov_cached_land_speed
    add = var:eu5ab_gov_cached_local_speed
    min = 0.05
}
eu5ab_governor_transport_topography = {
    value = var:eu5ab_gov_cached_topography
    multiply = { value = 1 add = var:eu5ab_gov_cached_topography_impact }
    max = 0
}
eu5ab_governor_edge_cost_factor = {
    value = 1
    divide = eu5ab_governor_transport_speed
    divide = { value = 1 add = eu5ab_governor_transport_topography min = 0.5 }
}
eu5ab_governor_road_edge_base_cost = {
    value = root.var:eu5ab_gov_cached_road_base
    multiply = eu5ab_governor_edge_cost_factor
}
eu5ab_governor_planned_road_cost = {
    value = var:eu5ab_gov_road_edge_base_cost
    subtract = {
        value = root.var:eu5ab_gov_transport_road_tier
        subtract = 1
        multiply = 5
        multiply = var:eu5ab_gov_edge_cost_factor
    }
    min = { value = 0.01 multiply = var:eu5ab_gov_edge_cost_factor }
}
eu5ab_governor_land_edge_base_cost = {
    value = root.var:eu5ab_gov_cached_land_base
    min = 0.01
    divide = eu5ab_governor_transport_speed
    divide = {
        value = 1
        add = eu5ab_governor_transport_topography
        add = var:eu5ab_gov_cached_vegetation
        min = 0.5
    }
}
'''

    # Called on a destination. All local costs belong to the saved SOURCE endpoint.
    # The known-land variant is called only after a neighbor filter has excluded
    # straits. The general variant preserves naval straits' actual connection.
    actual_cost = r'''        if = {
            limit = { has_road_to = scope:eu5ab_gov_edge_from }
            value = scope:eu5ab_gov_edge_from.var:eu5ab_gov_road_edge_base_cost
            if = {
                limit = { has_road_of_type_to = { target = scope:eu5ab_gov_edge_from type = road_type:railroad } }
                subtract = { value = 15 multiply = scope:eu5ab_gov_edge_from.var:eu5ab_gov_edge_cost_factor }
            }
            else_if = {
                limit = { has_road_of_type_to = { target = scope:eu5ab_gov_edge_from type = road_type:modern_road } }
                subtract = { value = 10 multiply = scope:eu5ab_gov_edge_from.var:eu5ab_gov_edge_cost_factor }
            }
            else_if = {
                limit = { has_road_of_type_to = { target = scope:eu5ab_gov_edge_from type = road_type:paved_road } }
                subtract = { value = 5 multiply = scope:eu5ab_gov_edge_from.var:eu5ab_gov_edge_cost_factor }
            }
            min = { value = 0.01 multiply = scope:eu5ab_gov_edge_from.var:eu5ab_gov_edge_cost_factor }
        }
        else = { value = scope:eu5ab_gov_edge_from.var:eu5ab_gov_land_edge_base_cost }'''
    edge_prediction = r'''
@DESCRIPTION@
@NAME@ = {
    value = scope:eu5ab_gov_edge_from.var:eu5ab_gov_predicted
    subtract = {
@COST@
    }
    min = 0
}
'''
    planned_cost = r'''        if = {
            limit = {
                root.var:eu5ab_gov_transport_road_tier > 0
@STRAIT_FILTER@
            }
            value = scope:eu5ab_gov_edge_from.var:eu5ab_gov_planned_road_cost
        }
''' + actual_cost.replace("        if = {", "        else_if = {", 1)

    lake_values = r'''
# Contract a known lake transit into two directed edges. Lake local speed is
# zero; entering uses the land source's local modifier. Never mutate a lake.
eu5ab_governor_lake_transit_prediction = {
    value = scope:eu5ab_gov_edge_from.var:eu5ab_gov_predicted
    subtract = {
        value = root.var:eu5ab_gov_cached_lake_base
        divide = {
            value = 1 add = root.var:eu5ab_gov_cached_global_speed
            add = scope:eu5ab_gov_edge_from.var:eu5ab_gov_cached_local_speed
            min = 0.05
        }
    }
    subtract = {
        value = root.var:eu5ab_gov_cached_lake_base
        divide = { value = 1 add = root.var:eu5ab_gov_cached_global_speed min = 0.05 }
    }
    min = 0
}

eu5ab_governor_comparison_proximity = {
    value = var:eu5ab_gov_planned_proximity
}
'''
    strait_filter = "                NOT = { eu5ab_is_strait_connection_to = { target = scope:eu5ab_gov_edge_from } }"
    planned = edge_prediction.replace("@COST@", planned_cost)
    general = planned.replace("@DESCRIPTION@", "# Naval straits keep their actual connection, without a hypothetical road.").replace(
        "@NAME@", "eu5ab_governor_land_edge_prediction").replace("@STRAIT_FILTER@", strait_filter)
    known_land = planned.replace("@DESCRIPTION@", "# Called after the neighbor filter has excluded straits.").replace(
        "@NAME@", "eu5ab_governor_known_land_edge_prediction").replace("@STRAIT_FILTER@\n", "")
    actual = edge_prediction.replace("@DESCRIPTION@", "# Actual connections only: the caller has already selected the road mode.").replace(
        "@NAME@", "eu5ab_governor_actual_land_edge_prediction").replace("@COST@", actual_cost)
    return common_values + general + known_land + actual + lake_values


def render_transport_effects() -> str:
    # Invalidate obsolete published cards without touching the scheduled-event
    # or skip-next-event markers, refresh counters, or the worker's new state.
    clear_obsolete_cards = ["        remove_variable = eu5ab_gov_result_road_tier"]
    for kind in ("local",):
        for suffix in ("has_new_recommendation", "notified_target"):
            clear_obsolete_cards.append(f"        remove_variable = eu5ab_{kind}_{suffix}")
        clear_obsolete_cards.append(f"        cmf_remove_alert = {{ alert = eu5ab_{kind}_governor_available_alert }}")
        for rank in range(1, 4):
            prefix = f"eu5ab_{kind}_top_{rank}"
            clear_obsolete_cards.append(f"        remove_variable = {prefix}")
            clear_obsolete_cards.append(f"        clear_variable_list = {prefix}_list")
            for suffix in (
                "score", "site_gain", "surrounding_gain", "coverage",
            ):
                clear_obsolete_cards.append(f"        remove_variable = {prefix}_{suffix}")
    return r'''
eu5ab_governor_snapshot_transport = {
    set_variable = { name = eu5ab_gov_transport_schema value = 2 }
    set_variable = { name = eu5ab_gov_transport_road_tier value = eu5ab_governor_highest_road_tier }
    set_variable = { name = eu5ab_gov_cached_global_speed value = modifier:global_distance_from_capital_speed_propagation }
    set_variable = { name = eu5ab_gov_cached_land_speed value = modifier:land_cost_on_distance_from_capital_speed_propagation }
    set_variable = { name = eu5ab_gov_cached_road_base value = modifier:road_cost_on_distance_from_capital }
    set_variable = { name = eu5ab_gov_cached_land_base value = modifier:land_cost_on_distance_from_capital }
    set_variable = { name = eu5ab_gov_cached_lake_base value = modifier:sea_cost_on_distance_from_capital_when_maritime }
}

# New rules cannot resume an old worker phase or inherit its confirmation.
# Called from entry points and the worker, including while game time is paused.
eu5ab_governor_check_transport_rules = {
    if = {
        limit = { NOT = { has_variable = eu5ab_gov_transport_schema } }
        eu5ab_governor_invalidate_transport_snapshot = yes
    }
    else_if = {
        limit = { var:eu5ab_gov_transport_schema != 2 }
        eu5ab_governor_invalidate_transport_snapshot = yes
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

eu5ab_governor_invalidate_transport_snapshot = {
        set_local_variable = { name = eu5ab_transport_resume_manual value = 0 }
        if = { limit = { has_variable = eu5ab_governor_manual_run } set_local_variable = { name = eu5ab_transport_resume_manual value = 1 } }
        if = { limit = { has_variable = eu5ab_governor_scan_active } eu5ab_layout_abort = yes }
        if = { limit = { local_var:eu5ab_transport_resume_manual > 0 } set_variable = eu5ab_governor_resume_manual }
        remove_local_variable = eu5ab_transport_resume_manual
        remove_variable = eu5ab_layout_confirmation_streak
        remove_variable = eu5ab_layout_has_results
        eu5ab_governor_clear_local_migration = yes
@CLEAR_OBSOLETE_CARDS@
        set_variable = eu5ab_governor_dirty
}

# Multi-source baseline on exactly the network used for candidate footprints.
# This is deliberately not live proximity: projected road improvements are
# common to the existing and proposed layouts, never attributed to a new seat.
eu5ab_governor_prepare_planned_baseline = {
    set_variable = { name = eu5ab_gov_eval_kind value = 3 }
    eu5ab_governor_prepare_planned_baseline_core = yes
}

# Naval candidates can traverse existing straits. Use the same connections in
# their baseline, without granting straits a hypothetical road.
eu5ab_governor_prepare_planned_naval_baseline = {
    set_variable = { name = eu5ab_gov_eval_kind value = 2 }
    eu5ab_governor_prepare_planned_baseline_core = yes
}

eu5ab_governor_prepare_planned_baseline_core = {
    remove_variable = eu5ab_governor_baseline_failed
    set_variable = { name = eu5ab_gov_eval_generation value = 0 }
    clear_variable_list = eu5ab_gov_eval_locations
    remove_variable = eu5ab_gov_queue_head
    remove_variable = eu5ab_gov_queue_tail
    every_owned_location = {
        set_variable = { name = eu5ab_gov_planned_proximity value = 0 }
        set_variable = { name = eu5ab_gov_visit_generation value = 0 }
        set_variable = { name = eu5ab_gov_predicted value = 0 }
        set_variable = { name = eu5ab_gov_depth value = 0 }
        set_local_variable = { name = eu5ab_gov_baseline_seed value = modifier:local_proximity_source }
        if = {
            limit = { local_var:eu5ab_gov_baseline_seed > 0 }
            set_variable = { name = eu5ab_gov_predicted value = { value = local_var:eu5ab_gov_baseline_seed max = 100 } }
            eu5ab_governor_queue_enqueue = yes
        }
        remove_local_variable = eu5ab_gov_baseline_seed
    }
    while = {
        limit = { has_variable = eu5ab_gov_queue_head }
        count = { value = num_locations multiply = 20 min = 100 }
        eu5ab_governor_queue_relax_one = yes
    }
    if = {
        limit = { has_variable = eu5ab_gov_queue_head }
        set_variable = eu5ab_governor_baseline_failed
        set_variable = eu5ab_governor_queue_exhausted
    }
    every_owned_location = {
        set_variable = { name = eu5ab_gov_planned_proximity value = var:eu5ab_gov_predicted }
        set_variable = {
            name = eu5ab_gov_node_demand
            value = { value = { value = modifier:local_proximity_source add = 80 min = 0 max = 100 } subtract = var:eu5ab_gov_planned_proximity min = 0 divide = 100 multiply = var:eu5ab_gov_node_value }
        }
        remove_variable = eu5ab_gov_in_queue
        remove_variable = eu5ab_gov_queue_next
    }
    remove_variable = eu5ab_gov_queue_head
    remove_variable = eu5ab_gov_queue_tail
    clear_variable_list = eu5ab_gov_eval_locations
}
'''.replace("@CLEAR_OBSOLETE_CARDS@", "\n".join(clear_obsolete_cards))


def render_lake_relaxation(*, layout: bool) -> str:
    """Owned-land -> known lake -> owned-land without shared water variables."""
    if layout:
        initialize = '''if = {
                    limit = { OR = { NOT = { has_variable = eu5ab_gov_visit_generation } var:eu5ab_gov_visit_generation != root.var:eu5ab_gov_eval_generation } }
                    eu5ab_layout_visit = yes
                }'''
        enqueue = "eu5ab_governor_queue_enqueue = yes"
        depth_gate = ""
        depth_update = ""
    else:
        initialize = '''if = {
                    limit = { OR = { NOT = { has_variable = eu5ab_gov_visit_generation } var:eu5ab_gov_visit_generation != root.var:eu5ab_gov_eval_generation } }
                    set_variable = { name = eu5ab_gov_visit_generation value = root.var:eu5ab_gov_eval_generation }
                    set_variable = { name = eu5ab_gov_predicted value = 0 }
                    set_variable = { name = eu5ab_gov_depth value = 99 }
                    save_temporary_scope_as = eu5ab_gov_newly_visited
                    root = { add_to_variable_list = { name = eu5ab_gov_eval_locations target = scope:eu5ab_gov_newly_visited } }
                }'''
        enqueue = "eu5ab_governor_queue_enqueue = yes"
        depth_gate = "OR = { root.var:eu5ab_gov_eval_kind != 1 scope:eu5ab_gov_edge_from.var:eu5ab_gov_depth <= 4 }"
        depth_update = "set_variable = { name = eu5ab_gov_depth value = { value = scope:eu5ab_gov_edge_from.var:eu5ab_gov_depth add = 2 } }"
    return '''
        every_neighbor_location = {
            limit = { OR = { topography = lakes topography = high_lakes topography = salt_pans } }
            every_neighbor_location = {
                limit = { is_ownable = yes owner ?= root NOT = { this = scope:eu5ab_gov_edge_from } @DEPTH_GATE@ }
                @INITIALIZE@
                set_local_variable = { name = eu5ab_gov_lake_relaxed value = eu5ab_governor_lake_transit_prediction }
                if = {
                    limit = { local_var:eu5ab_gov_lake_relaxed > var:eu5ab_gov_predicted }
                    set_variable = { name = eu5ab_gov_predicted value = local_var:eu5ab_gov_lake_relaxed }
                    @DEPTH_UPDATE@
                    @ENQUEUE@
                }
                remove_local_variable = eu5ab_gov_lake_relaxed
            }
        }
'''.replace("@INITIALIZE@", initialize).replace("@ENQUEUE@", enqueue).replace("@DEPTH_GATE@", depth_gate).replace("@DEPTH_UPDATE@", depth_update)
