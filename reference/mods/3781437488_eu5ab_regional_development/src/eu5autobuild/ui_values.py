"""Guarded script values for numbers otherwise consumed only by the UI.

EU5's variable checker cannot see GetVariable calls in localization. Route
these reads through script values, also providing zero before a report exists.
"""
from __future__ import annotations

UI_NUMERIC_VARIABLES = (
    'eu5ab_manual_count', 'eu5ab_manual_cost',
    *(f"eu5ab_diag_top_{rank}_{field}" for rank in range(1, 4)
      for field in ("score", "need", "economic", "labor_jobs", "labor_current", "labor_projected", "reason")),
    "eu5ab_diag_fail_building_capacity",
    "eu5ab_diag_fail_capacity_unavailable",
    "eu5ab_diag_capacity_expired",
    "eu5ab_diag_rgo_fail_score",
    "eu5ab_diag_rgo_fail_pending_data",
    "eu5ab_diag_rgo_fail_pending_limit",
    *(f"eu5ab_diag_top_{rank}_rgo_{factor}_factor" for rank in range(1, 4) for factor in ("price", "pending", "labor")),
    *(f"eu5ab_diag_top_{rank}_rgo_{field}" for rank in range(1, 4) for field in ("pending_quantity", "pending_limit", "market_gap")),
    *(f"eu5ab_diag_rgo_pending_{field}" for field in ("gap", "quantity", "limit", "factor", "state")),
    "eu5ab_diag_final_quota",
    "eu5ab_diag_fail_irrigation_need",
    "eu5ab_diag_fail_granary_need",
    "eu5ab_diag_fail_storage_pending",
    "eu5ab_diag_fail_windmill_need",
    "eu5ab_diag_has_run",
    "eu5ab_diag_last_actual_cost",
    "eu5ab_diag_last_actual_income",
    "eu5ab_diag_last_actual_profit",
    "eu5ab_diag_last_build_kind",
    "eu5ab_diag_last_run_day",
    "eu5ab_diag_last_run_month",
    "eu5ab_diag_last_run_year",
    "eu5ab_diag_previous_month_added",
    "eu5ab_diag_rgo_quota_used",
    "eu5ab_diag_workforce_prediction_mode",
    "eu5ab_gov_sync_capacity",
    "eu5ab_gov_sync_occupied",
    "eu5ab_gov_sync_lieutenancies",
    "eu5ab_gov_sync_other_slots",
    "eu5ab_gov_sync_fresh_other_slots",
    "eu5ab_gov_sync_fresh_occupied",
    "eu5ab_gov_sync_fresh_lieutenancies",
    "eu5ab_gov_sync_threshold",
    "eu5ab_gov_sync_slot_available",
    "eu5ab_gov_sync_fresh_slot_available",
    "eu5ab_gov_sync_slot_cache_mismatch",
    "eu5ab_gov_sync_candidates",
    "eu5ab_gov_sync_shortlisted",
    "eu5ab_gov_sync_stage",
    "eu5ab_gov_sync_status",
    "eu5ab_naval_gov_sync_status",
    "eu5ab_naval_gov_sync_runs",
    "eu5ab_layout_page_number",
    "eu5ab_layout_result_after",
    "eu5ab_layout_result_before",
    "eu5ab_layout_result_kind",
    "eu5ab_layout_result_net",
    "eu5ab_naval_layout_page_number",
    "eu5ab_naval_layout_result_after",
    "eu5ab_naval_layout_result_before",
    "eu5ab_naval_layout_result_kind",
    "eu5ab_naval_layout_result_net",
)


def bind_ui_values(text: str) -> str:
    """Apply after translation so every language uses identical data bindings."""
    for variable in UI_NUMERIC_VARIABLES:
        text = text.replace(
            f"GetVariable('{variable}').GetValue",
            f"ScriptValue('{variable}_ui')",
        )
    return text


def render_ui_script_values() -> str:
    blocks = ["# Generated guarded values for GUI and localization consumers."]
    for variable in UI_NUMERIC_VARIABLES:
        conditions = [f"has_variable = {variable}"]
        if variable == "eu5ab_diag_last_build_kind":
            # Never display a stale/deleted location or an absent building type.
            conditions += [
                "exists = var:eu5ab_diag_last_build_location",
                "OR = { var:eu5ab_diag_last_build_kind = 1 exists = var:eu5ab_diag_last_building }",
            ]
        blocks.append(
            f"{variable}_ui = {{\n"
            "\tvalue = 0\n"
            "\tif = {\n"
            f"\t\tlimit = {{ {' '.join(conditions)} }}\n"
            f"\t\tvalue = var:{variable}\n"
            "\t}\n}"
        )
    return "\n\n".join(blocks) + "\n"
