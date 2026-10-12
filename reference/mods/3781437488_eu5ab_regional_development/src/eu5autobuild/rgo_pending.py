"""RGO output reserved by construction and completed, unfilled levels.

Only confirmed Mod starts enter the persistent country location registry.
Ownership/resource changes retire records; market changes move their summaries.
Only the serial country dispatcher writes summaries, never parallel workers.
"""

import math

from .rgo_automation import raw_goods


DEMAND_BUFFER_RATIO = 0.10
MIN_FACTOR = 0.00001
DIAGNOSTIC_FIELDS = ("gap", "quantity", "limit", "factor", "state")


def merge_diagnostics_lines() -> list[str]:
    lines = [
        "\t\tif = {",
        "\t\t\tlimit = { has_variable = eu5ab_worker_rgo_pending_state }",
        "\t\t\tscope:eu5ab_worker_merge_country = {",
        "\t\t\t\tset_variable = { name = eu5ab_diag_rgo_pending_location value = scope:eu5ab_candidate_location }",
    ]
    for field in DIAGNOSTIC_FIELDS:
        lines.extend([
            f"\t\t\t\tset_variable = {{ name = eu5ab_diag_rgo_pending_{field} value = 0 }}",
            f"\t\t\t\tif = {{ limit = {{ scope:eu5ab_candidate_location = {{ has_variable = eu5ab_worker_rgo_pending_{field} }} }} set_variable = {{ name = eu5ab_diag_rgo_pending_{field} value = scope:eu5ab_candidate_location.var:eu5ab_worker_rgo_pending_{field} }} }}",
        ])
    lines.extend(["\t\t\t}", "\t\t}"])
    return lines


def pending_factor(pending: float, demand: float, supply: float) -> float:
    """Reference curve; a zero result means the candidate must be excluded."""
    if any(not math.isfinite(v) or v < 0 for v in (pending, demand, supply)):
        return 0.0
    limit = max(demand - supply, 0.0) + demand * DEMAND_BUFFER_RATIO
    if pending == 0:
        return 1.0
    if pending >= limit:
        return 0.0
    return max(MIN_FACTOR, 1.0 - (pending / limit) ** 2)


def render_values() -> str:
    chunks = ['''
# All quantities are goods, not workers or RGO levels. Missing market readings
# use a negative sentinel; genuine zero demand has its own one-level rule.
''']
    for name, query in (("demand", "goods_demand_in_market"),
                        ("supply", "goods_supply_in_market")):
        chunks.append(f'''eu5ab_rgo_market_{name} = {{
    value = -1
    if = {{
        limit = {{ exists = market exists = raw_material }}''')
        # A location has exactly one raw material. Dispatch once, then read
        # every applicable ledger for that good inside the selected branch.
        # In particular, an absent RGO map must not skip an ordinary map.
        for index, good in enumerate(raw_goods()):
            branch = 'if' if index == 0 else 'else_if'
            chunks.append(f'''        {branch} = {{
            limit = {{ raw_material = goods:{good} }}
            value = "market.{query}(goods:{good})"''')
            if name == 'demand':
                chunks.append(f'''            if = {{ limit = {{ owner = {{ is_key_in_variable_map = {{ name = eu5ab_build_future_input_{good} target = prev.market }} }} }}
                owner = {{ add = "variable_map(eu5ab_build_future_input_{good}|prev.market)" }}
            }}''')
            chunks.append('        }')
        chunks.append('    }\n}')
    for name, prefix in (("quantity", "output"), ("unknown", "unknown")):
        chunks.append(f'''eu5ab_rgo_market_pending_{name} = {{
    value = 0
    if = {{
        limit = {{ exists = owner exists = market exists = raw_material }}''')
        for index, good in enumerate(raw_goods()):
            branch = 'if' if index == 0 else 'else_if'
            mapping = f"eu5ab_rgo_pending_{prefix}_{good}"
            chunks.append(f'''        {branch} = {{
            limit = {{ raw_material = goods:{good} }}
            if = {{ limit = {{ owner = {{ is_key_in_variable_map = {{ name = {mapping} target = prev.market }} }} }}
                owner = {{ add = "variable_map({mapping}|prev.market)" }}
            }}''')
            # Building cohorts reserve only known goods. Unknown projects keep
            # their cohort and retry the native recipe after completion; they
            # never invent a per-good unknown output/input ledger.
            if name == 'quantity':
                building_map = f"eu5ab_build_pending_{good}"
                chunks.append(f'''            if = {{ limit = {{ owner = {{ is_key_in_variable_map = {{ name = {building_map} target = prev.market }} }} }}
                owner = {{ add = "variable_map({building_map}|prev.market)" }}
            }}''')
            chunks.append('        }')
        chunks.append('    }\n}')
    chunks.append(f'''
eu5ab_rgo_market_gap = {{
    value = eu5ab_rgo_market_demand
    subtract = eu5ab_rgo_market_supply
    min = 0
}}
eu5ab_rgo_pending_limit = {{
    value = eu5ab_rgo_market_demand
    min = 0
    multiply = {DEMAND_BUFFER_RATIO:g}
    add = eu5ab_rgo_market_gap
}}
eu5ab_rgo_pending_factor = {{
    value = 0
    if = {{ limit = {{ eu5ab_rgo_food_emergency_enabled = yes }} value = 1 }}
    else_if = {{
        limit = {{ eu5ab_rgo_pending_data_available = yes eu5ab_rgo_pending_below_limit = yes }}
        value = 1
        if = {{
            limit = {{ eu5ab_rgo_market_pending_quantity > 0 eu5ab_rgo_pending_limit > 0 }}
            subtract = {{
                value = eu5ab_rgo_market_pending_quantity
                divide = eu5ab_rgo_pending_limit
                multiply = {{ value = eu5ab_rgo_market_pending_quantity divide = eu5ab_rgo_pending_limit }}
            }}
            # Keep a positive factor below the stop, even at fixed-point resolution.
            min = {MIN_FACTOR:.5f}
        }}
    }}
}}

# The pre-start value is read only after full existing staffing has passed.
eu5ab_rgo_full_level_output = {{
    value = 0
    if = {{
        limit = {{ rgo_level > 0 raw_material_output > 0 eu5ab_rgo_utilization_allowed = yes }}
        value = raw_material_output
        divide = rgo_level
    }}
}}
eu5ab_rgo_staffed_levels = {{
    value = 0
    if = {{
        limit = {{ eu5ab_rgo_jobs_per_expansion > 0 rgo_workers >= 0 rgo_level >= 0 }}
        value = rgo_workers
        divide = eu5ab_rgo_jobs_per_expansion
        floor = yes
        min = 0
        max = rgo_level
    }}
}}
''')
    return '\n'.join(chunks)


def render_triggers() -> str:
    return '''
eu5ab_rgo_pending_location_data_available = {
    rgo_level >= 0
    rgo_workers >= 0
    eu5ab_rgo_jobs_per_expansion > 0
    eu5ab_rgos_under_construction >= 0
}
eu5ab_rgo_pending_data_available = {
    exists = market
    exists = raw_material
    owner = { has_variable = eu5ab_rgo_pending_ready }
    owner = { has_variable = eu5ab_build_pending_ready }
    eu5ab_rgo_market_demand >= 0
    eu5ab_rgo_market_supply >= 0
    eu5ab_rgo_market_pending_unknown = 0
    eu5ab_rgo_full_level_output > 0
}
eu5ab_rgo_pending_below_limit = {
    OR = {
        eu5ab_rgo_market_pending_quantity = 0
        eu5ab_rgo_market_pending_quantity < eu5ab_rgo_pending_limit
    }
}
eu5ab_rgo_pending_allowed = {
    OR = {
        eu5ab_rgo_food_emergency_enabled = yes
        AND = {
            eu5ab_rgo_pending_data_available = yes
            eu5ab_rgo_pending_below_limit = yes
        }
    }
}
'''


def _add_summary_lines(direction: int = 1) -> list[str]:
    """Location scope; debit/credit exactly its last published contribution."""
    lines = ["    if = {", "        limit = { exists = var:eu5ab_rgo_pending_owner",
             "            exists = var:eu5ab_rgo_pending_market OR = {",
             "            AND = { has_variable = eu5ab_rgo_pending_quantity trigger_if = { limit = { has_variable = eu5ab_rgo_pending_quantity } var:eu5ab_rgo_pending_quantity > 0 } }",
             "            AND = { has_variable = eu5ab_rgo_pending_unknown trigger_if = { limit = { has_variable = eu5ab_rgo_pending_unknown } var:eu5ab_rgo_pending_unknown > 0 } }",
             "        } }"]
    for index, good in enumerate(raw_goods()):
        branch = 'if' if index == 0 else 'else_if'
        lines.extend([f"        {branch} = {{",
                      f"            limit = {{ var:eu5ab_rgo_pending_good = goods:{good} }}"])
        for field, prefix in (("quantity", "output"), ("unknown", "unknown")):
            variable = f"eu5ab_rgo_pending_{field}"
            mapping = f"eu5ab_rgo_pending_{prefix}_{good}"
            lines.append(f'''            if = {{
                limit = {{ has_variable = {variable} var:{variable} > 0 }}
                var:eu5ab_rgo_pending_owner = {{
                    set_local_variable = {{ name = eu5ab_rgo_summary_add value = {{ value = prev.var:{variable} multiply = {direction} }} }}
                    if = {{
                        limit = {{ is_key_in_variable_map = {{ name = {mapping} target = prev.var:eu5ab_rgo_pending_market }} }}
                        change_local_variable = {{ name = eu5ab_rgo_summary_add add = "variable_map({mapping}|prev.var:eu5ab_rgo_pending_market)" }}
                    }}
                    # Keep a numeric floor explicit: effect min/max mutation
                    # is not the script-value min/max clamp contract.
                    if = {{ limit = {{ local_var:eu5ab_rgo_summary_add < 0 }}
                        set_local_variable = {{ name = eu5ab_rgo_summary_add value = 0 }}
                    }}
                    add_to_variable_map = {{ name = {mapping} key = prev.var:eu5ab_rgo_pending_market value = local_var:eu5ab_rgo_summary_add }}
                    remove_local_variable = eu5ab_rgo_summary_add
                }}
            }}''')
        lines.append("        }")
    lines.append("    }")
    return lines


def render_effects() -> str:
    chunks = ['''
# Repair the lost active marker only from a confirmed, unmixed pending record
# whose original level has not completed. Never enroll arbitrary civil work.
# An unknown queue keeps existing attribution but cannot prove a recovery.
eu5ab_restore_active_rgo = {
    if = { limit = {
        NOT = { has_variable = eu5ab_active_rgo_construction }
        exists = var:eu5ab_rgo_pending_owner
        has_variable = eu5ab_rgo_pending_good
        has_variable = eu5ab_rgo_pending_baseline
        has_variable = eu5ab_rgo_pending_levels
        NOT = { has_variable = eu5ab_rgo_pending_ambiguous }
        NOT = { has_variable = eu5ab_rgo_pending_level_loss }
    }
        if = { limit = {
            owner = var:eu5ab_rgo_pending_owner
            raw_material = var:eu5ab_rgo_pending_good
            rgo_level = var:eu5ab_rgo_pending_baseline
            var:eu5ab_rgo_pending_levels > 0
            eu5ab_rgos_under_construction > 0
        }
            set_variable = eu5ab_active_rgo_construction
            owner = { if = { limit = { NOT = {
                is_target_in_variable_list = { name = eu5ab_active_project_locations target = prev }
            } } add_to_variable_list = { name = eu5ab_active_project_locations target = prev } } }
        }
    }
}

# Only this registry is authoritative. Unproven legacy location totals never
# enroll a location. Clearing a record removes the index as well as its data.
eu5ab_clear_rgo_pending_location = {
    if = { limit = { exists = var:eu5ab_rgo_pending_owner }
        var:eu5ab_rgo_pending_owner = {
            remove_list_variable = { name = eu5ab_rgo_pending_locations target = prev }
            remove_list_variable = { name = eu5ab_rgo_timing_requests target = prev }
        }
    }
''']
    for field in ("owner", "good", "market", "levels", "baseline", "last_level", "ambiguous", "level_loss",
                  "quantity", "unknown", "unit_output", "timing_ready", "build_days", "wait_construction"):
        chunks.append(f"    remove_variable = eu5ab_rgo_pending_{field}")
    chunks.append('''}

eu5ab_reconcile_rgo_pending_location = {
    remove_variable = eu5ab_rgo_pending_quantity
    remove_variable = eu5ab_rgo_pending_unknown
    if = { limit = { NOT = { AND = {
        exists = var:eu5ab_rgo_pending_owner owner = var:eu5ab_rgo_pending_owner
        exists = raw_material has_variable = eu5ab_rgo_pending_good
        raw_material = var:eu5ab_rgo_pending_good
        has_variable = eu5ab_rgo_pending_levels var:eu5ab_rgo_pending_levels > 0
        has_variable = eu5ab_rgo_pending_baseline
        has_variable = eu5ab_rgo_pending_last_level
    } } }
        eu5ab_clear_rgo_pending_location = yes
    }
    else_if = { limit = { NOT = { eu5ab_rgo_pending_location_data_available = yes } }
        # Unknown readings cannot establish completion, cancellation or output.
        set_variable = { name = eu5ab_rgo_pending_unknown value = var:eu5ab_rgo_pending_levels }
        if = { limit = { eu5ab_rgos_under_construction < 0 } eu5ab_request_rgo_queue = yes }
    }
    else = {
        eu5ab_request_rgo_timing = yes
        if = { limit = { rgo_level < var:eu5ab_rgo_pending_last_level }
            # Destruction can remove old or Mod levels. The original baseline
            # no longer proves that a remaining project was cancelled.
            set_variable = eu5ab_rgo_pending_level_loss
        }
        if = { limit = { OR = {
            has_variable = eu5ab_rgo_pending_level_loss
            eu5ab_rgos_under_construction > { value = var:eu5ab_rgo_pending_baseline add = var:eu5ab_rgo_pending_levels subtract = rgo_level }
        } }
            # External additions/destruction make aggregate attribution unknown.
            # Once mixed, returning to the old total does not prove identity.
            set_variable = eu5ab_rgo_pending_ambiguous
        }
        if = { limit = { has_variable = eu5ab_rgo_pending_ambiguous }
            set_variable = { name = eu5ab_rgo_pending_levels value = {
                value = rgo_level add = eu5ab_rgos_under_construction
                if = { limit = { NOT = { has_variable = eu5ab_rgo_pending_level_loss } }
                    subtract = var:eu5ab_rgo_pending_baseline }
                min = 0 max = var:eu5ab_rgo_pending_levels
            } }
            if = { limit = { eu5ab_rgos_under_construction = 0 eu5ab_rgo_pending_staffing_due = yes }
                if = { limit = { eu5ab_rgo_staffed_levels >= rgo_level }
                    set_variable = { name = eu5ab_rgo_pending_levels value = 0 }
                }
            }
        }
        else = {
            # A monotonic staffing floor prevents unemployment from reopening
            # released capacity. Native construction alone never raises it.
            if = { limit = { eu5ab_rgo_pending_staffing_due = yes }
                set_variable = { name = eu5ab_rgo_pending_baseline value = {
                    value = var:eu5ab_rgo_pending_baseline min = eu5ab_rgo_staffed_levels
                } }
            }
            set_variable = { name = eu5ab_rgo_pending_levels value = {
                value = rgo_level add = eu5ab_rgos_under_construction
                subtract = var:eu5ab_rgo_pending_baseline min = 0 max = var:eu5ab_rgo_pending_levels
            } }
        }
        set_variable = { name = eu5ab_rgo_pending_last_level value = rgo_level }
        if = { limit = { var:eu5ab_rgo_pending_levels <= 0 }
            eu5ab_clear_rgo_pending_location = yes
        }
        else_if = { limit = { NOT = { has_variable = eu5ab_rgo_pending_ambiguous }
            has_variable = eu5ab_rgo_pending_unit_output var:eu5ab_rgo_pending_unit_output > 0 }
            set_variable = { name = eu5ab_rgo_pending_quantity value = {
                value = var:eu5ab_rgo_pending_levels multiply = var:eu5ab_rgo_pending_unit_output
            } }
        }
        else = { set_variable = { name = eu5ab_rgo_pending_unknown value = var:eu5ab_rgo_pending_levels } }
    }
}

# Template changes do not remove registered projects. Empty registries never
# traverse locations; refresh is idempotent and never discovers manual work.
eu5ab_ensure_rgo_pending = {
    if = { limit = { OR = {
        NOT = { has_variable = eu5ab_rgo_pending_ready }
        NOT = { has_variable = eu5ab_rgo_pending_day }
        NOT = { var:eu5ab_rgo_pending_day = eu5ab_pl_today }
    } } eu5ab_refresh_rgo_pending = yes }
}
eu5ab_refresh_rgo_pending = {
    eu5ab_migrate_rgo_pending_registry = yes
    set_variable = { name = eu5ab_rgo_pending_day value = eu5ab_pl_today }
    remove_variable = eu5ab_rgo_pending_ready
''')
    for good in raw_goods():
        chunks.append(f"    clear_variable_map = eu5ab_rgo_pending_output_{good}\n"
                      f"    clear_variable_map = eu5ab_rgo_pending_unknown_{good}")
    chunks.append('''    save_scope_as = eu5ab_rgo_pending_country
    if = { limit = { has_variable_list = eu5ab_rgo_pending_locations }
        every_in_list = { variable = eu5ab_rgo_pending_locations
            if = { limit = { has_variable = eu5ab_rgo_pending_owner
                var:eu5ab_rgo_pending_owner = scope:eu5ab_rgo_pending_country }
                eu5ab_reconcile_rgo_pending_location = yes
                eu5ab_restore_active_rgo = yes
                eu5ab_add_rgo_pending_summary = yes
            }
            else = { scope:eu5ab_rgo_pending_country = {
                remove_list_variable = { name = eu5ab_rgo_pending_locations target = prev }
            } }
        }
    }
    set_variable = eu5ab_rgo_pending_ready
}

eu5ab_add_rgo_pending_summary = {
    remove_variable = eu5ab_rgo_pending_market
    if = { limit = { has_variable = eu5ab_rgo_pending_levels exists = market }
        set_variable = { name = eu5ab_rgo_pending_market value = market }
    }
''')
    chunks.extend(_add_summary_lines())
    chunks.append('}\n\neu5ab_remove_rgo_pending_summary = {')
    chunks.extend(_add_summary_lines(-1))
    chunks.append('''}

# Reconcile a previous record before issuing another command at this location.
# Debiting the stored market/owner handles same-day market/ownership changes.
eu5ab_prepare_rgo_pending_start = {
    if = { limit = { has_variable = eu5ab_rgo_pending_levels }
        eu5ab_remove_rgo_pending_summary = yes
        eu5ab_reconcile_rgo_pending_location = yes
        eu5ab_restore_active_rgo = yes
        eu5ab_add_rgo_pending_summary = yes
    }
}
# Called before the native command. A rejection discards these scratch values.
eu5ab_capture_rgo_start_output = {
    eu5ab_prepare_rgo_pending_start = yes
    set_variable = { name = eu5ab_rgo_start_output value = eu5ab_rgo_full_level_output }
    set_variable = { name = eu5ab_rgo_start_level value = rgo_level }
    eu5ab_capture_rgo_start_queue = yes
}
# Only native success reaches this entry point; migration uses the helper below.
eu5ab_record_rgo_start = {
    eu5ab_update_rgo_queue_after_start = yes
    eu5ab_report_rgo_confirmed = yes
    eu5ab_register_rgo_pending_start = yes
}
eu5ab_register_rgo_pending_start = {
    if = { limit = { has_variable = eu5ab_rgo_pending_levels }
        eu5ab_remove_rgo_pending_summary = yes
        change_variable = { name = eu5ab_rgo_pending_levels add = 1 }
        # Same-output confirmed Mod starts can share a known record. Different
        # snapshots cannot be assigned to individual completions from totals.
        if = { limit = { NOT = { AND = {
            has_variable = eu5ab_rgo_pending_unit_output has_variable = eu5ab_rgo_start_output
            var:eu5ab_rgo_pending_unit_output = var:eu5ab_rgo_start_output
        } } } set_variable = eu5ab_rgo_pending_ambiguous }
    }
    else = {
        # Remove unproven legacy estimates; never turn them into Mod projects.
        eu5ab_clear_rgo_pending_location = yes
        set_variable = { name = eu5ab_rgo_pending_levels value = 1 }
        set_variable = { name = eu5ab_rgo_pending_baseline value = var:eu5ab_rgo_start_level }
        set_variable = { name = eu5ab_rgo_pending_last_level value = var:eu5ab_rgo_start_level }
        if = { limit = { OR = {
            NOT = { has_variable = eu5ab_rgo_start_queue_known }
            AND = { has_variable = eu5ab_rgo_start_queue var:eu5ab_rgo_start_queue > 0 }
        } }
            set_variable = eu5ab_rgo_pending_ambiguous
        }
        if = { limit = { has_variable = eu5ab_rgo_start_output var:eu5ab_rgo_start_output > 0 }
            set_variable = { name = eu5ab_rgo_pending_unit_output value = var:eu5ab_rgo_start_output }
        }
    }
    set_variable = { name = eu5ab_rgo_pending_owner value = owner }
    set_variable = { name = eu5ab_rgo_pending_good value = raw_material }
    # A new confirmed command needs its own native remaining-time snapshot.
    remove_variable = eu5ab_rgo_pending_timing_ready
    remove_variable = eu5ab_rgo_pending_build_days
    remove_variable = eu5ab_rgo_pending_wait_construction
    owner = { if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_rgo_pending_locations target = prev } } }
        add_to_variable_list = { name = eu5ab_rgo_pending_locations target = prev }
    } }
    eu5ab_reconcile_rgo_pending_location = yes
    eu5ab_request_rgo_timing = yes
    eu5ab_add_rgo_pending_summary = yes
}

# Old broad totals and attempted/approved rows cannot prove a start.
# Only retained country-owned success receipts (4/6) can seed one level each.
# This one-time migration walks receipts, never owned locations.
eu5ab_migrate_rgo_pending_registry = {
    if = { limit = { NOT = { has_variable = eu5ab_rgo_pending_registry_version } }
        set_variable = { name = eu5ab_rgo_pending_registry_version value = 1 }
        save_scope_as = eu5ab_rgo_migration_country
        every_in_list = { variable = eu5ab_batch_rgo_records
            save_scope_value_as = { name = eu5ab_rgo_migration_id value = this }
            scope:eu5ab_rgo_migration_country = {
                if = { limit = {
                    is_key_in_variable_map = { name = eu5ab_batch_rgo_status target = scope:eu5ab_rgo_migration_id }
                    OR = { "variable_map(eu5ab_batch_rgo_status|scope:eu5ab_rgo_migration_id)" = 4
                           "variable_map(eu5ab_batch_rgo_status|scope:eu5ab_rgo_migration_id)" = 6 }
                    is_key_in_variable_map = { name = eu5ab_batch_rgo_location target = scope:eu5ab_rgo_migration_id }
                    is_key_in_variable_map = { name = eu5ab_batch_rgo_good target = scope:eu5ab_rgo_migration_id }
                    is_key_in_variable_map = { name = eu5ab_batch_rgo_level_before target = scope:eu5ab_rgo_migration_id }
                }
                    "variable_map(eu5ab_batch_rgo_location|scope:eu5ab_rgo_migration_id)" = {
                        if = { limit = { owner = scope:eu5ab_rgo_migration_country
                            raw_material = "scope:eu5ab_rgo_migration_country.variable_map(eu5ab_batch_rgo_good|scope:eu5ab_rgo_migration_id)"
                            NOT = { has_variable = eu5ab_rgo_pending_levels } }
                            set_variable = { name = eu5ab_rgo_start_level value = "scope:eu5ab_rgo_migration_country.variable_map(eu5ab_batch_rgo_level_before|scope:eu5ab_rgo_migration_id)" }
                            # Totals since this old receipt may include manual work.
                            set_variable = { name = eu5ab_rgo_start_queue value = 1 }
                            remove_variable = eu5ab_rgo_start_output
                            eu5ab_register_rgo_pending_start = yes
                            remove_variable = eu5ab_rgo_start_level
                            remove_variable = eu5ab_rgo_start_queue
                        }
                    }
                }
            }
        }
    }
}

# Worker-local snapshots are merged by the serial country dispatcher.
eu5ab_capture_rgo_pending_diagnostics = {
    set_variable = { name = eu5ab_worker_rgo_pending_gap value = eu5ab_rgo_market_gap }
    set_variable = { name = eu5ab_worker_rgo_pending_quantity value = eu5ab_rgo_market_pending_quantity }
    set_variable = { name = eu5ab_worker_rgo_pending_limit value = eu5ab_rgo_pending_limit }
    set_variable = { name = eu5ab_worker_rgo_pending_factor value = { value = eu5ab_rgo_pending_factor multiply = 100 } }
    set_variable = { name = eu5ab_worker_rgo_pending_state value = 1 }
    if = { limit = { eu5ab_rgo_food_emergency_enabled = yes } set_variable = { name = eu5ab_worker_rgo_pending_state value = 4 } }
    else_if = { limit = { NOT = { eu5ab_rgo_pending_data_available = yes } } set_variable = { name = eu5ab_worker_rgo_pending_state value = 3 } }
    else_if = { limit = { NOT = { eu5ab_rgo_pending_below_limit = yes } } set_variable = { name = eu5ab_worker_rgo_pending_state value = 2 } }
}
''')
    return '\n'.join(chunks)
