"""A GUI-time watchdog based on useful planner work, not callback counts."""

# Every field is initialized before layout_begin snapshots the first wave.
# These cover propagation, collection, application, selection, and comparison.
# Do not add layout_ticks: a callback that does no work must not reset the guard.
PROGRESS_FIELDS = (
    "eu5ab_layout_phase", "eu5ab_layout_mode", "eu5ab_layout_round",
    "eu5ab_gov_eval_generation", "eu5ab_layout_total_work",
    "eu5ab_layout_pending_nodes", "eu5ab_layout_completed",
    "eu5ab_layout_single_candidates", "eu5ab_layout_single_comparisons",
    "eu5ab_gov_refresh_phase", "eu5ab_gov_refresh_work",
)
STALLED_CHECKS = 2
MANUAL_TICK_LIMIT = 100000


def render_liveness_effects() -> str:
    remembered = [f"eu5ab_layout_observed_{index}" for index in range(len(PROGRESS_FIELDS))]
    clear = "\n".join(f"    remove_variable = {name}" for name in remembered)
    snapshot = "\n".join(
        f"    if = {{ limit = {{ NOT = {{ has_variable = {current} }} }} set_variable = {{ name = {current} value = 0 }} }}\n"
        f"    set_variable = {{ name = {old} value = var:{current} }}"
        for old, current in zip(remembered, PROGRESS_FIELDS, strict=True)
    )
    changes = "\n".join(
        f"                var:{current} != var:{old}"
        for old, current in zip(remembered, PROGRESS_FIELDS, strict=True)
    )
    return f'''# Manual refresh drains the same planner without GUI/date delays.
# A malformed job must terminate explicitly instead of leaving a pending task.
eu5ab_layout_finish_manual = {{
    if = {{
        limit = {{ has_variable = eu5ab_governor_manual_run has_variable = eu5ab_governor_scan_active }}
        while = {{
            limit = {{ has_variable = eu5ab_governor_manual_run has_variable = eu5ab_governor_scan_active }}
            count = {MANUAL_TICK_LIMIT}
            eu5ab_layout_tick = yes
            eu5ab_layout_check_liveness = yes
        }}
        if = {{ limit = {{ has_variable = eu5ab_governor_scan_active }} eu5ab_layout_abort = yes }}
    }}
    if = {{ limit = {{ NOT = {{ has_variable = eu5ab_governor_scan_active }} }} remove_variable = eu5ab_governor_manual_run }}
}}

eu5ab_layout_clear_liveness = {{
    remove_variable = eu5ab_layout_liveness_ready
    remove_variable = eu5ab_layout_stalled_checks
{clear}
}}

eu5ab_layout_snapshot_progress = {{
    set_variable = eu5ab_layout_liveness_ready
    set_variable = {{ name = eu5ab_layout_stalled_checks value = 0 }}
{snapshot}
}}

eu5ab_layout_check_liveness = {{
    if = {{
        limit = {{ is_human = yes has_variable = eu5ab_governor_scan_active }}
        if = {{
            # Old saves have no observation. Give them a full observation window.
            limit = {{ NOT = {{ has_variable = eu5ab_layout_liveness_ready }} }}
            eu5ab_layout_snapshot_progress = yes
        }}
        else_if = {{
            limit = {{ OR = {{
{changes}
            }} }}
            eu5ab_layout_snapshot_progress = yes
        }}
        else = {{
            change_variable = {{ name = eu5ab_layout_stalled_checks add = 1 }}
            if = {{
                limit = {{ var:eu5ab_layout_stalled_checks >= {STALLED_CHECKS} }}
                eu5ab_layout_abort = yes
            }}
        }}
    }}
}}
'''
