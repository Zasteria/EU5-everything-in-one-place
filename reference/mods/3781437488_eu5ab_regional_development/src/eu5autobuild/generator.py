"""Generate EU5 mod files from policy templates."""

from __future__ import annotations

from pathlib import Path
import argparse
import json
import re

from . import (
    annual_budget, save_resume, template_coverage, queue_gui_commands, queue_bridge, quote_cache, winner_batch, queue_script_dispatch,
    candidate_backfill, queue_validation, recipe_snapshot, scan_reserve, monthly_schedule, production_forecast, production_cohorts,
    rgo_automation, rgo_localization, building_capacity, rgo_pending, rgo_queue, output_prices, market_price_cache, native_recipes, construction_slots, project_tracking, market_supply, queued_workforce, queue_ranking, upgrade_queue,
)
from .town_rights import render_town_rights_values
from . import industry_promotion
from .food_infrastructure import (
    FOOD_BUILDING_GATES, RGO_BOOST_GOODS, associated_goods,
    render_food_building_triggers, render_food_building_values,
)
from .game_data import (
    BuildingUpgradeData,
    ConstructionDemand,
    WorkforceModelData,
    building_upgrades_as_json,
    construction_demands_as_json,
    extract_building_upgrades,
    extract_rgo_base_costs,
    extract_supported_construction_demands,
    extract_workforce_model,
    registered_dlc_names,
    workforce_model_as_json,
)
from .governor_connections import extract_straits, straits_json
from .game_root import require_game_root
from .production import (
    BuildingProduction, extract_production_models, production_models_as_json,
    render_production,
)
from .ui_values import bind_ui_values, render_ui_script_values
from .governor_layout_ui import render_layout_worker_gui
from .governor_generator import (
    GOVERNOR_ENGLISH_LOCALIZATION,
    GOVERNOR_RECOMMENDATION_BUILDINGS,
    GOVERNOR_SIMP_CHINESE_LOCALIZATION,
    render_governor_effects,
    render_governor_events,
    render_governor_gui,
    render_governor_script_values,
    render_governor_scripted_guis,
    render_governor_triggers,
)
from .localization import (
    SUPPORTED_TRANSLATION_LANGUAGES,
    load_translation_catalog,
    render_translated_localization,
    translation_report,
)
from .policy import BuildingCatalog, Policy, load_building_catalog, load_policies
from .rgo_cost import render_rgo_cost_input_trigger, render_rgo_cost_script_values
from .rules import (
    AutomationRules,
    WORKFORCE_FORECAST_MAX_MONTHS,
    load_automation_rules,
)


MOD_ID = "eu5ab_regional_development"
MOD_VERSION = "0.9.7-beta"
ENGLISH_FALLBACK_LANGUAGES = SUPPORTED_TRANSLATION_LANGUAGES
CUSTOM_POLICY_ID = "custom_template"
CUSTOM_POLICY_VALUE = 100
CANDIDATE_BUILDING_SCOPE = "eu5ab_candidate_building"
CANDIDATE_LOCATION_SCOPE = "eu5ab_candidate_location"
TEMPLATE_SLOTS = tuple(range(1, 21))
PLAYER_TEMPLATE_LIMIT = 20
BUILTIN_BUDGET_MULTIPLIER = 6
BUDGET_MODE_FIXED = 0
BUDGET_MODE_INCOME = 1
BUDGET_INCOME_MULTIPLIERS = (4, 6, 8)
TEMPLATE_NAME_CHOICES = (
    (1, "food_security"),
    (2, "mining_development"),
    (3, "port_trade"),
    (4, "urban_industry"),
    (5, "military_frontier"),
    (6, "custom"),
)
TEMPLATE_SCALAR_SUFFIXES = (
    "name_id",
    "name_selected",
    "preset_origin",
)
TEMPLATE_TOGGLE_SUFFIXES: tuple[str, ...] = ()
TEMPLATE_PRIORITIES_INITIALIZED_SUFFIX = "building_priorities_initialized"
# Retired names retained for regression audits, never emitted as live settings.
LEGACY_TEMPLATE_RUNTIME_SUFFIXES = (
    "min_cash_reserve", "price_min", "price_max", "annual_budget",
    "budget_mode", "budget_multiplier", "budget_limit", "budget_remaining",
    "rgo_priority", "rgo_min_utilization", "rgo_monthly_limit",
    "job_fill_deadline_months", "native_input_priority", "allow_special_buildings",
    "auto_build_input_sources", "pause_low_workforce", "stop_input_shortage", "allow_rgo",
)
CMM_MOD_ID = "eu5ab_regional_development"
CMM_SETTING_PREFIX = f"{CMM_MOD_ID}__"
CMM_BUDGET_MODE_FIXED = 1
CMM_BUDGET_MODE_INCOME_X4 = 2
CMM_BUDGET_MODE_INCOME_X6 = 3
CMM_BUDGET_MODE_INCOME_X8 = 4
CMM_ECONOMIC_METRIC_TAX_INCOME = 1
CMM_ECONOMIC_METRIC_PROFIT = 2
CMM_ECONOMIC_METRIC_ROI_TAX_INCOME = 3
CMM_ECONOMIC_METRIC_ROI_PROFIT = 4
CMM_CANDIDATE_RANKING_COMPOSITE = 1
CMM_CANDIDATE_RANKING_ACTUAL_PROFIT = 2
ENGINE_QUEUE_WATCHDOG_INTERVAL_DAYS = 2
ENGINE_QUEUE_WATCHDOG_STALL_CHECKS = 2
CMM_PERFORMANCE_PRESET_CONSERVATIVE = 1
CMM_PERFORMANCE_PRESET_BALANCED = 2
CMM_PERFORMANCE_PRESET_THROUGHPUT = 3
CMM_PERFORMANCE_PRESET_CUSTOM = 4
CMM_PERFORMANCE_PLANNING_WARNING_SETTINGS = (
    "performance_throughput_warning_action",
    "performance_throughput_warning_planning_consequence",
)
CMM_PERFORMANCE_PROFIT_WARNING_SETTINGS = (
    "performance_throughput_warning_profit_action",
    "performance_throughput_warning_profit_consequence",
)
CMM_PERFORMANCE_WARNING_SETTINGS = (
    "performance_throughput_warning_summary",
    *CMM_PERFORMANCE_PLANNING_WARNING_SETTINGS,
    *CMM_PERFORMANCE_PROFIT_WARNING_SETTINGS,
    "performance_throughput_warning_common_action",
)
CMM_CANDIDATE_PRIORITY_SETTING = "candidate_priority"
CANDIDATE_PRIORITY_FEATURES = (
    ("upgrade", "eu5ab_feature_upgrade_building"),
    ("expand", "eu5ab_feature_expand_building"),
    ("rgo", "eu5ab_feature_expand_rgo"),
    ("new", "eu5ab_feature_new_building"),
)
CANDIDATE_BUILDING_CLASSES = (
    ("upgrade", "eu5ab_candidate_is_upgrade"),
    ("expansion", "eu5ab_candidate_is_expansion"),
    ("new", "eu5ab_candidate_is_new_build"),
)
CURRENT_CANDIDATE_POOLS = tuple(
    f"eu5ab_current_{candidate_class}_candidate_pool"
    for candidate_class, _trigger in CANDIDATE_BUILDING_CLASSES
)
CURRENT_INPUT_CANDIDATE_POOLS = tuple(
    f"eu5ab_current_input_{candidate_class}_candidate_pool"
    for candidate_class, _trigger in CANDIDATE_BUILDING_CLASSES
)
GLOBAL_RULE_DEFAULTS = {
    "enabled": 1,
    "monthly_build_hard_cap": 9,
    "budget_mode": CMM_BUDGET_MODE_INCOME_X6,
    "economic_metric": CMM_ECONOMIC_METRIC_TAX_INCOME,
    "candidate_ranking_mode": CMM_CANDIDATE_RANKING_ACTUAL_PROFIT,
    "candidate_backfill_enabled": 0,
    "emergency_food_exhaustion_override": 1,
    "emergency_food_stockpile_override": 1,
    "emergency_construction_goods_override": 1,
    "emergency_wartime_military_override": 1,
    "emergency_strategic_input_override": 1,
    "fixed_annual_budget": 500,
    "min_cash_reserve": 1000,
    "price_min": 80,
    "price_max": 125,
    "allow_special_buildings": 0,
    "fill_market_shortages_when_idle": 0,
    "auto_build_input_sources": 1,
    "pause_low_workforce": 1,
    "stop_input_shortage": 1,
    "allow_rgo": 1,
    "rgo_workforce_mode": 1,
    "rgo_job_fill_deadline_months": 180,
    "job_fill_deadline_months": 12,
    "native_input_priority": 5,
    "performance_preset": CMM_PERFORMANCE_PRESET_THROUGHPUT,
    "parallel_location_scan": 1,
    "daily_location_task_limit": 30,
    "max_additions_per_run": 0,
    "candidates_per_location": 3,
    "actual_profit_candidates_per_location": 10,
    "early_stop_when_candidates_sufficient": 1,
    "governor_recommendations_enabled": 1,
    "governor_relocation_enabled": 1,
    "governor_migration_enabled": 0,
    "governor_migration_threshold_percent": 80,
    "naval_governor_migration_threshold_percent": 80,
    "governor_refresh_interval": 2,
    "governor_scoring_profile": 1,
    "governor_strategic_value": 0,
}

PERFORMANCE_ADVANCED_SETTING_IDS = (
    "parallel_location_scan",
    "daily_location_task_limit",
    "max_additions_per_run",
    "candidates_per_location",
    "actual_profit_candidates_per_location",
    "early_stop_when_candidates_sufficient",
)
WORKER_DIAGNOSTIC_COUNTERS = (
    "eu5ab_diag_legal_candidates",
    "eu5ab_diag_fail_building_capacity",
    "eu5ab_diag_fail_capacity_unavailable",
    "eu5ab_diag_fail_workforce",
    "eu5ab_diag_fail_inputs",
    "eu5ab_diag_fail_oversupply",
    "eu5ab_diag_fail_pending_output",
    "eu5ab_diag_fail_irrigation_need",
    "eu5ab_diag_fail_granary_need",
    "eu5ab_diag_fail_storage_pending",
    "eu5ab_diag_fail_windmill_need",
    "eu5ab_diag_fail_no_legal",
    "eu5ab_diag_rgo_checked",
    "eu5ab_diag_rgo_fail_capacity",
    "eu5ab_diag_rgo_fail_location",
    "eu5ab_diag_rgo_fail_disabled",
    "eu5ab_diag_rgo_fail_finance",
    "eu5ab_diag_rgo_fail_utilization",
    "eu5ab_diag_rgo_fail_workforce",
    "eu5ab_diag_rgo_fail_market_need",
    "eu5ab_diag_rgo_fail_score",
    "eu5ab_diag_rgo_fail_pending_data",
    "eu5ab_diag_rgo_fail_pending_limit",
    "eu5ab_diag_rgo_eligible",
)
WORKER_TOP_FIELD_SUFFIXES = (
    "building",
    "kind",
    "priority",
    "score",
    "need",
    "economic",
    "labor_jobs",
    "labor_current",
    "labor_projected",
    "rgo_price_factor",
    "rgo_pending_factor",
    "rgo_pending_quantity",
    "rgo_pending_limit",
    "rgo_market_gap",
    "rgo_labor_factor",
    "reason",
)


def _increment_runtime_counter(name: str) -> str:
    """Native zero-valued counters may be absent after initialization/load."""
    return (
        f"if = {{ limit = {{ has_variable = {name} }} change_variable = {{ name = {name} add = 1 }} }} "
        f"else = {{ set_variable = {{ name = {name} value = 1 }} }}"
    )


def _global_setting_var(setting_id: str) -> str:
    if setting_id == "monthly_build_hard_cap":
        return "eu5ab_monthly_build_hard_cap"
    return f"eu5ab_global_{setting_id}"


def _cmm_setting_value(setting_id: str) -> str:
    return f'"variable_map(cmm|flag:{CMM_SETTING_PREFIX}{setting_id})"'
PRESET_TEMPLATE_IDS = (
    "granary",
    "industrial_zone",
    "trade_center",
    "naval_base",
    "frontier",
    "food_priority",
    "military_industry",
    "shipbuilding",
    "textiles",
    "mining",
    "luxury_goods",
)
ROOT = Path(__file__).resolve().parents[2]
POLICY_FILE = ROOT / "policies" / "templates.json"
CATALOG_FILE = ROOT / "policies" / "building_catalog.json"
RULES_FILE = ROOT / "policies" / "automation_rules.json"
TRANSLATION_ROOT = ROOT / "localization" / "translations"


def _gui_binary_call(function: str, expressions: list[str] | tuple[str, ...]) -> str:
    """Fold GUI functions such as Or/And, whose Jomini binding is binary."""
    if not expressions:
        raise ValueError(f"GUI function {function} requires at least one expression")
    result = expressions[-1]
    for expression in reversed(expressions[:-1]):
        result = f"{function}({expression},{result})"
    return result


def _policy_index(policy: Policy, index: int) -> str:
    return f"{index + 1}"


def _balanced_script(text: str) -> bool:
    depth = 0
    in_quote = False
    escaped = False
    for char in text:
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_quote


def _normalize_generated_text(text: str) -> str:
    """Remove template indentation from blank lines and all trailing whitespace."""
    has_final_newline = text.endswith(("\n", "\r"))
    normalized = "\n".join(line.rstrip() for line in text.splitlines())
    return normalized + ("\n" if has_final_newline else "")


def _write_generated_file(path: Path, content: str) -> None:
    encoding = "utf-8-sig" if path.suffix in {".json", ".txt", ".gui", ".yml"} else "utf-8"
    newline = "\r\n" if path.suffix == ".yml" else None
    path.write_text(content.lstrip("\ufeff"), encoding=encoding, newline=newline)


def render_metadata() -> str:
    metadata = {
        "name": "EU5 Advanced Auto Build",
        "id": MOD_ID,
        "version": MOD_VERSION,
        "supported_game_version": "1.4.*",
        "short_description": "使用可调整的建造顺序、收益要求和紧急规则，自动发展已应用模板的地点。需要社区模组框架。",
        "picture": "thumbnail.png",
        "tags": ["Economy", "Utilities", "Gameplay"],
        "relationships": [
            {
                "rel_type": "dependency",
                "id": "community_mod_framework",
                "display_name": "Community Mod Framework",
                "resource_type": "mod",
                "version": "2.5.*",
            }
        ],
        "game_custom_data": {"replace_paths": []},
    }
    return json.dumps(metadata, indent=2, ensure_ascii=False) + "\n"


def render_on_actions() -> str:
    general_bool_settings = (
        ("enabled", "general", "limits"),
    )
    automation_bool_settings = (
        ("allow_special_buildings", "automation", "safety"),
        ("fill_market_shortages_when_idle", "automation", "safety"),
        ("auto_build_input_sources", "automation", "safety"),
        ("pause_low_workforce", "automation", "safety"),
        ("stop_input_shortage", "automation", "safety"),
        ("allow_rgo", "automation", "rgo"),
    )
    performance_bool_settings = (
        ("candidate_backfill_enabled", "performance", "advanced"),
        ("parallel_location_scan", "performance", "advanced"),
        ("early_stop_when_candidates_sufficient", "performance", "advanced"),
    )
    general_return_override_settings = (
        ("emergency_food_exhaustion_override", "general", "returns"),
        ("emergency_food_stockpile_override", "general", "returns"),
        ("emergency_construction_goods_override", "general", "returns"),
        ("emergency_wartime_military_override", "general", "returns"),
        ("emergency_strategic_input_override", "general", "returns"),
    )
    general_numeric_settings = (
        ("monthly_build_hard_cap", "general", "limits", 0, 599, 1),
    )
    automation_numeric_settings = (
        ("rgo_job_fill_deadline_months", "automation", "rgo", 0, 1200, 1),
        (
            "job_fill_deadline_months",
            "automation",
            "workforce",
            0,
            WORKFORCE_FORECAST_MAX_MONTHS,
            1,
        ),
        ("native_input_priority", "automation", "ranking", 0, 10, 1),
    )
    finance_numeric_settings = (
        ("fixed_annual_budget", "finance", "budget", 0, 999999, 100),
        ("min_cash_reserve", "finance", "budget", 0, 100000, 100),
        ("price_min", "finance", "market", 0, 300, 5),
        ("price_max", "finance", "market", 0, 300, 5),
    )
    performance_numeric_settings = (
        ("daily_location_task_limit", "performance", "advanced", 1, 30, 1),
        ("max_additions_per_run", "performance", "advanced", 0, 600, 10),
        ("candidates_per_location", "performance", "advanced", 3, 30, 1),
        ("actual_profit_candidates_per_location", "performance", "advanced", 3, 30, 1),
    )
    governor_bool_settings = (
        ("governor_recommendations_enabled", "governors", "recommendations"),
        ("governor_relocation_enabled", "governors", "recommendations"),
        ("governor_migration_enabled", "governors", "recommendations"),
        ("governor_strategic_value", "governors", "scoring"),
    )
    slider_setting_ids = {
        "monthly_build_hard_cap",
        "fixed_annual_budget",
        "min_cash_reserve",
    }
    registration_lines = []

    def register_bool_settings(settings: tuple[tuple[str, str, str], ...]) -> None:
        for setting_id, tab_id, group_id in settings:
            registration_lines.extend([
                "\t\tcmm_register_bool_setting = {",
                f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = {setting_id}",
                f"\t\t\ttab_id = {tab_id} group_id = {group_id}",
                f"\t\t\tdefault_value = {GLOBAL_RULE_DEFAULTS[setting_id]}",
                "\t\t}",
            ])

    def register_numeric_settings(
        settings: tuple[tuple[str, str, str, int, int, int], ...],
    ) -> None:
        for setting_id, tab_id, group_id, minimum, maximum, step in settings:
            registration_effect = (
                "cmm_register_slider_setting"
                if setting_id in slider_setting_ids
                else "cmm_register_numeric_setting"
            )
            registration_lines.extend([
                f"\t\t{registration_effect} = {{",
                f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = {setting_id}",
                f"\t\t\ttab_id = {tab_id} group_id = {group_id}",
                f"\t\t\tdefault_value = {GLOBAL_RULE_DEFAULTS[setting_id]}",
                f"\t\t\tmin_value = {minimum} max_value = {maximum} step_value = {step}",
                "\t\t}",
            ])
            if setting_id in ("fixed_annual_budget", "job_fill_deadline_months", "rgo_job_fill_deadline_months"):
                registration_lines.extend([
                    "\t\tcmm_add_scripted_gui = {",
                    f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = {setting_id}",
                    "\t\t}",
                ])

    # CMM uses first registration to choose the visible tab and preserve tab/group
    # order. Register General first, Automation second, Finance third, and the
    # isolated performance controls fourth.
    register_bool_settings(general_bool_settings)
    registration_lines.extend([
        "\t\tcmm_register_dropdown_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = economic_metric",
        "\t\t\ttab_id = general group_id = returns",
        f"\t\t\tdefault_index = {GLOBAL_RULE_DEFAULTS['economic_metric']} option_count = 4",
        "\t\t}",
    ])
    register_bool_settings(general_return_override_settings)
    register_numeric_settings(general_numeric_settings)

    # Within Automation, keep the player's build order above safety controls.
    registration_lines.extend([
        "\t\tcmm_register_dropdown_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = candidate_ranking_mode",
        "\t\t\ttab_id = automation group_id = ranking",
        f"\t\t\tdefault_index = {GLOBAL_RULE_DEFAULTS['candidate_ranking_mode']} option_count = 2",
        "\t\t}",
        "\t\tcmm_register_settings_list = {",
        f"\t\t\tmod_id = {CMM_MOD_ID}",
        f"\t\t\tsetting_id = {CMM_CANDIDATE_PRIORITY_SETTING}",
        "\t\t\ttab_id = automation",
        f"\t\t\titem_count = {len(CANDIDATE_PRIORITY_FEATURES)}",
        "\t\t\tis_ordered = 1",
        "\t\t}",
    ])
    for item, (_, feature_flag) in enumerate(CANDIDATE_PRIORITY_FEATURES, 1):
        registration_lines.append(
            "\t\tcmm_set_list_item_value = { "
            f"mod_id = {CMM_MOD_ID} setting_id = {CMM_CANDIDATE_PRIORITY_SETTING} "
            f"item = {item} value = flag:{feature_flag} }}"
        )
    # CMM expands numeric handlers for all five slots even for a fieldless
    # ordering list. Supply neutral bounds without registering visible fields.
    for slot in range(1, 6):
        for bound, value in (("min", 0), ("max", 0), ("step", 1)):
            registration_lines.append(
                f"\t\tset_variable = {{ name = cmm_list_field_{slot}_{bound}_{CMM_SETTING_PREFIX}{CMM_CANDIDATE_PRIORITY_SETTING} value = {value} }}"
            )
    # CMM expands reset code for all 50 x 5 optional field keys even for our
    # fieldless list. Declare only those known flag reads to its static checker.
    # This branch never executes and creates no variables or save data.
    registration_lines.extend(["\t\tif = {", "\t\t\tlimit = {", "\t\t\t\talways = no"])
    registration_lines.extend(
        f"\t\t\t\texists = flag:{CMM_SETTING_PREFIX}{CMM_CANDIDATE_PRIORITY_SETTING}_i{item}_f{field}"
        for item in range(1, 51) for field in range(1, 6)
    )
    registration_lines.extend(["\t\t\t}", "\t\t}"])
    register_bool_settings(automation_bool_settings)
    registration_lines.extend([
        "\t\tcmm_register_dropdown_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = rgo_workforce_mode",
        "\t\t\ttab_id = automation group_id = rgo",
        "\t\t\tdefault_index = 1 option_count = 2",
        "\t\t}",
        "\t\tcmm_add_scripted_gui = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = rgo_workforce_mode",
        "\t\t}",
        "\t\tcmm_register_button_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = rgo_forced_relaxed",
        "\t\t\ttab_id = automation group_id = rgo",
        "\t\t}",
        f"\t\tremove_from_variable_map = {{ name = cmm_type key = flag:{CMM_MOD_ID}__rgo_forced_relaxed }}",
        f"\t\tadd_to_variable_map = {{ name = cmm_type key = flag:{CMM_MOD_ID}__rgo_forced_relaxed value = 0 }}",
        "\t\tcmm_add_scripted_gui = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = rgo_forced_relaxed",
        "\t\t}",
    ])
    register_numeric_settings(automation_numeric_settings)

    registration_lines.extend([
        "\t\tcmm_register_dropdown_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = budget_mode",
        "\t\t\ttab_id = finance group_id = budget",
        f"\t\t\tdefault_index = {GLOBAL_RULE_DEFAULTS['budget_mode']} option_count = 4",
        "\t\t}",
    ])
    register_numeric_settings(finance_numeric_settings)
    registration_lines.extend([
        "\t\tcmm_register_dropdown_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = performance_preset",
        "\t\t\ttab_id = performance group_id = preset",
        f"\t\t\tdefault_index = {GLOBAL_RULE_DEFAULTS['performance_preset']} option_count = 4",
        "\t\t}",
    ])
    registration_lines.extend([
        "\t\t# CMM has no display-only setting type. Register each warning row, then",
        "\t\t# clear its control type so only the localized label remains visible.",
    ])
    for warning_setting in CMM_PERFORMANCE_WARNING_SETTINGS:
        registration_lines.extend([
            "\t\tcmm_register_button_setting = {",
            f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = {warning_setting}",
            "\t\t\ttab_id = performance group_id = preset",
            "\t\t}",
            f"\t\tremove_from_variable_map = {{ name = cmm_type key = flag:{CMM_MOD_ID}__{warning_setting} }}",
            f"\t\tadd_to_variable_map = {{ name = cmm_type key = flag:{CMM_MOD_ID}__{warning_setting} value = 0 }}",
            "\t\tcmm_add_scripted_gui = {",
            f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = {warning_setting}",
            "\t\t}",
        ])
    register_bool_settings(performance_bool_settings)
    register_numeric_settings(performance_numeric_settings)
    for ranking_candidate_setting in (
        "candidates_per_location",
        "actual_profit_candidates_per_location",
    ):
        registration_lines.extend([
            "\t\tcmm_add_scripted_gui = {",
            f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = {ranking_candidate_setting}",
            "\t\t}",
        ])

    # Governor recommendation is a separate top-level CMM tab.  These controls
    # affect recommendations only; Local Governor and Naval Governor are never
    # submitted to the automated construction queue.
    register_bool_settings(governor_bool_settings[:1])
    registration_lines.extend([
        "\t\tcmm_register_dropdown_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = governor_refresh_interval",
        "\t\t\ttab_id = governors group_id = recommendations",
        f"\t\t\tdefault_index = {GLOBAL_RULE_DEFAULTS['governor_refresh_interval']} option_count = 4",
        "\t\t}",
        "\t\tcmm_register_button_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = governor_refresh_now",
        "\t\t\ttab_id = governors group_id = recommendations",
        "\t\t}",
        "\t\tcmm_register_dropdown_setting = {",
        f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = governor_scoring_profile",
        "\t\t\ttab_id = governors group_id = scoring",
        f"\t\t\tdefault_index = {GLOBAL_RULE_DEFAULTS['governor_scoring_profile']} option_count = 3",
        "\t\t}",
    ])
    register_bool_settings(governor_bool_settings[1:])
    register_numeric_settings((
        ("governor_migration_threshold_percent", "governors", "recommendations", 0, 200, 1),
        ("naval_governor_migration_threshold_percent", "governors", "recommendations", 0, 200, 1),
    ))
    for setting_id in ("governor_migration_enabled", "governor_migration_threshold_percent", "naval_governor_migration_threshold_percent"):
        registration_lines.extend([
            "\t\tcmm_add_scripted_gui = {",
            f"\t\t\tmod_id = {CMM_MOD_ID} setting_id = {setting_id}",
            "\t\t}",
        ])
    registration = "\n".join(registration_lines)
    governor_country_dirty_effect = """\teffect = {
\t\tif = {
\t\t\tlimit = { scope_type = country }
\t\t\tif = {
\t\t\t\tlimit = { is_human = yes }
\t\t\t\tset_variable = eu5ab_governor_dirty
\t\tset_variable = eu5ab_naval_planner_dirty
\t\t\t}
\t\t}
\t}"""
    script = """# Generated by eu5autobuild.generator.
monthly_country_pulse = {
\ton_actions = {
\t\teu5ab_monthly_country_policy_pulse
\t\teu5ab_governor_monthly_pulse_on_action
\t}
}

eu5ab_monthly_country_policy_pulse = {
\teffect = {
\t\t# Close the old month before assessing the new month's independent quota.
\t\tif = { limit = { is_human = yes } eu5ab_expire_old_scan_month = yes }
\t\tif = {
\t\t\tlimit = {
\t\t\t\tis_human = yes
\t\t\t\tvar:eu5ab_global_enabled > 0
\t\t\t\tany_owned_location = { has_variable = eu5ab_policy_id }
\t\t\t\tNOT = { has_variable = eu5ab_scan_active }
\t\t\t\tNOT = { has_variable = eu5ab_scan_round_active }
\t\t\t\tNOT = { has_variable = eu5ab_q_active }
\t\t\t\tNOT = { has_variable = eu5ab_scan_resume_after_load }
\t\t\t}
\t\t\t# Scan the persisted buckets from day 2, use day 22 for deferred
\t\t\t# locations, then finalize the construction queue from day 23.
\t\t\ttrigger_event_silently = {
\t\t\t\tid = eu5ab_monthly.1
\t\t\t\tdays = 1
\t\t\t}
\t\t}
\t}
}

eu5ab_governor_monthly_pulse_on_action = {
\teffect = {
\t\teu5ab_governor_monthly_pulse = yes
\t}
}

# Each location invocation is an independent task when the engine dispatches
# this events block. The worker event writes only to its root location.
eu5ab_parallel_location_scan_on_action = {
\tevents = {
\t\teu5ab_worker.1
\t}
}

on_location_changed_owner = {
\ton_actions = {
\t\teu5ab_on_location_changed_owner
\t\teu5ab_governor_dirty_from_owner_change_on_action
\t}
}

eu5ab_governor_dirty_from_owner_change_on_action = {
\teffect = {
\t\teu5ab_governor_dirty_from_owner_change = yes
\t}
}

eu5ab_on_location_changed_owner = {
\teffect = {
\t\teu5ab_remove_location_template_coverage = yes
\t\tif = {
\t\t\tlimit = { has_variable = eu5ab_scan_bucket }
\t\t\tscope:loser ?= {
\t\t\t\tswitch = {
\t\t\t\t\ttrigger = root.var:eu5ab_scan_bucket
{ownership_unregister_cases}
\t\t\t\t}
\t\t\t}
\t\t\tremove_variable = eu5ab_scan_bucket
\t\t}
\t\tif = {
\t\t\tlimit = { has_variable = eu5ab_policy_id scope:winner ?= { is_human = yes } }
\t\t\teu5ab_register_location_for_scan = yes
\t\t}
\t\teu5ab_sync_location_template_coverage = yes
\t}
}

# Register the Mod and its conflict-free window entry point with CMF.
cmf_on_mod_registration = {
\ton_actions = {
\t\teu5ab_on_cmf_registration
\t}
}

eu5ab_on_cmf_registration = {
\teffect = {
{registration}
\t\tcmf_add_action_bar_element = { element = eu5ab_action_bar }
\t\tcmf_register_scripted_gui = { element = eu5ab_action_bar }
\t\teu5ab_register_governor_alerts = yes
\t\teu5ab_sync_cmm_settings = yes
\t\teu5ab_ensure_annual_budget = yes
\t}
}

# CMF 2.4.1 copies CMM values when the player changes country, but a country
# created after the first global registration has no action-bar active list.
# Move EU5AB's player-facing registration to the new country and deactivate the
# old country without deleting its persistent templates or historical data.
cmf_on_country_transfer = {
\ton_actions = {
\t\teu5ab_on_cmf_country_transfer
\t}
}

eu5ab_on_cmf_country_transfer = {
\teffect = {
\t\tif = {
\t\t\tlimit = {
\t\t\t\texists = scope:old_country
\t\t\t\tscope:old_country = {
\t\t\t\t\tis_target_in_variable_list = {
\t\t\t\t\t\tname = cmf_action_bar_active_elements
\t\t\t\t\t\ttarget = flag:eu5ab_action_bar
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\tif = {
\t\t\t\tlimit = {
\t\t\t\t\tNOT = {
\t\t\t\t\t\tis_target_in_variable_list = {
\t\t\t\t\t\t\tname = cmf_action_bar_active_elements
\t\t\t\t\t\t\ttarget = flag:eu5ab_action_bar
\t\t\t\t\t\t}
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tadd_to_variable_list = {
\t\t\t\t\tname = cmf_action_bar_active_elements
\t\t\t\t\ttarget = flag:eu5ab_action_bar
\t\t\t\t}
\t\t\t}
\t\t}
\t\telse = {
\t\t\tremove_list_variable = {
\t\t\t\tname = cmf_action_bar_active_elements
\t\t\t\ttarget = flag:eu5ab_action_bar
\t\t\t}
\t\t}

\t\t# Registration rebuilt the CMM action-bar rows before this callback.
\t\t# Resync EU5AB's bool field after restoring the transferred active list.
\t\teu5ab_sync_cmf_action_bar_toggle = yes

\t\tif = {
\t\t\tlimit = { exists = scope:old_country NOT = { this ?= scope:old_country } }
\t\t\tscope:old_country = {
\t\t\t\tremove_list_variable = {
\t\t\t\t\tname = cmf_action_bar_active_elements
\t\t\t\t\ttarget = flag:eu5ab_action_bar
\t\t\t\t}
\t\t\t\tremove_list_variable = {
\t\t\t\t\tname = cmm_registered_mod_ids
\t\t\t\t\ttarget = flag:eu5ab_regional_development
\t\t\t\t}
\t\t\t\tremove_variable = eu5ab_cmf_window_requested
\t\t\t\teu5ab_recover_runtime_after_load = yes
\t\t\t\tremove_variable = eu5ab_scan_resume_after_load
\t\t\t}
\t\t}
\t}
}

# CMF dispatches action-bar clicks through a shared callback.
cmf_on_callback = {
\ton_actions = {
\t\teu5ab_on_cmf_callback
\t}
}

eu5ab_on_cmf_callback = {
\teffect = {
\t\tif = {
\t\t\tlimit = {
\t\t\t\tOR = {
\t\t\t\t\tvar:cmf_callback = flag:eu5ab_local_governor_available_alert
\t\t\t\t\tvar:cmf_callback = flag:eu5ab_local_governor_relocation_alert
\t\t\t\t\tvar:cmf_callback = flag:eu5ab_naval_governor_available_alert
\t\t\t\t\tvar:cmf_callback = flag:eu5ab_naval_governor_relocation_alert
\t\t\t\t}
\t\t\t}
\t\t\teu5ab_prepare_governor_window = yes
\t\t}
\t\tif = {
\t\t\tlimit = { var:cmf_callback = flag:eu5ab_action_bar }
\t\t\tset_variable = eu5ab_cmf_window_requested
\t\t\tremove_variable = eu5ab_active_preset_policy
\t\t\teu5ab_select_first_player_template = yes
\t\t}
\t\t# CMM auto-apply fires the same callback with the composite setting key.
\t\tif = {
\t\t\tlimit = { var:cmf_callback != flag:eu5ab_action_bar }
\t\t\tif = {
\t\t\t\tlimit = { var:cmf_callback = flag:{CMM_MOD_ID}__governor_refresh_now }
\t\t\t\teu5ab_governor_manual_recalculation = yes
\t\t\t}
\t\t\telse_if = {
\t\t\t\tlimit = {
\t\t\t\t\tOR = {
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__governor_recommendations_enabled
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__governor_relocation_enabled
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__governor_migration_enabled
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__governor_migration_threshold_percent
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__governor_refresh_interval
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__governor_scoring_profile
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__governor_strategic_value
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tset_variable = eu5ab_governor_dirty
\t\t\t\tif = { limit = { NOT = { var:cmf_callback = flag:{CMM_MOD_ID}__governor_migration_threshold_percent } } set_variable = eu5ab_naval_planner_dirty }
\t\t\t}
\t\t\tif = {
\t\t\t\tlimit = { var:cmf_callback = flag:{CMM_MOD_ID}__performance_preset }
\t\t\t\tswitch = {
\t\t\t\t\ttrigger = "variable_map(cmm|flag:{CMM_MOD_ID}__performance_preset)"
\t\t\t\t\t1 = {
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__parallel_location_scan value = 1 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__daily_location_task_limit value = 10 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__max_additions_per_run value = 30 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__candidates_per_location value = 5 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__actual_profit_candidates_per_location value = 15 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__early_stop_when_candidates_sufficient value = 1 }
\t\t\t\t\t}
\t\t\t\t\t2 = {
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__parallel_location_scan value = 1 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__daily_location_task_limit value = 20 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__max_additions_per_run value = 50 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__candidates_per_location value = 4 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__actual_profit_candidates_per_location value = 12 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__early_stop_when_candidates_sufficient value = 1 }
\t\t\t\t\t}
\t\t\t\t\t3 = {
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__parallel_location_scan value = 1 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__daily_location_task_limit value = 30 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__max_additions_per_run value = 0 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__candidates_per_location value = 3 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__actual_profit_candidates_per_location value = 10 }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__early_stop_when_candidates_sufficient value = 1 }
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\telse_if = {
\t\t\t\tlimit = {
\t\t\t\t\tOR = {
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__parallel_location_scan
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__daily_location_task_limit
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__max_additions_per_run
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__candidates_per_location
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__actual_profit_candidates_per_location
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__early_stop_when_candidates_sufficient
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__performance_preset value = 4 }
\t\t\t}
\t\t\t# CMM's stock Shift gesture jumps to min/max. Reinterpret those endpoint
\t\t\t# writes as the larger step documented by this Mod's tooltips.
\t\t\tif = {
\t\t\t\tlimit = { var:cmf_callback = flag:{CMM_MOD_ID}__monthly_build_hard_cap }
\t\t\t\tif = {
\t\t\t\t\tlimit = { has_variable = eu5ab_monthly_build_hard_cap }
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { "variable_map(cmm|flag:{CMM_MOD_ID}__monthly_build_hard_cap)" = 599 var:eu5ab_monthly_build_hard_cap < 599 }
\t\t\t\t\t\tset_variable = { name = eu5ab_cmm_shift_step value = { value = var:eu5ab_monthly_build_hard_cap add = 10 max = 599 } }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__monthly_build_hard_cap value = var:eu5ab_cmm_shift_step }
\t\t\t\t\t}
\t\t\t\t\telse_if = {
\t\t\t\t\t\tlimit = { "variable_map(cmm|flag:{CMM_MOD_ID}__monthly_build_hard_cap)" = 0 var:eu5ab_monthly_build_hard_cap > 0 }
\t\t\t\t\t\tset_variable = { name = eu5ab_cmm_shift_step value = { value = var:eu5ab_monthly_build_hard_cap subtract = 10 min = 0 } }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__monthly_build_hard_cap value = var:eu5ab_cmm_shift_step }
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\telse_if = {
\t\t\t\tlimit = { var:cmf_callback = flag:{CMM_MOD_ID}__fixed_annual_budget }
\t\t\t\tif = {
\t\t\t\t\tlimit = { has_variable = eu5ab_global_fixed_annual_budget }
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { "variable_map(cmm|flag:{CMM_MOD_ID}__fixed_annual_budget)" = 999999 var:eu5ab_global_fixed_annual_budget < 999999 }
\t\t\t\t\t\tset_variable = { name = eu5ab_cmm_shift_step value = { value = var:eu5ab_global_fixed_annual_budget add = 1000 max = 999999 } }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__fixed_annual_budget value = var:eu5ab_cmm_shift_step }
\t\t\t\t\t}
\t\t\t\t\telse_if = {
\t\t\t\t\t\tlimit = { "variable_map(cmm|flag:{CMM_MOD_ID}__fixed_annual_budget)" = 0 var:eu5ab_global_fixed_annual_budget > 0 }
\t\t\t\t\t\tset_variable = { name = eu5ab_cmm_shift_step value = { value = var:eu5ab_global_fixed_annual_budget subtract = 1000 min = 0 } }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__fixed_annual_budget value = var:eu5ab_cmm_shift_step }
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\telse_if = {
\t\t\t\tlimit = { var:cmf_callback = flag:{CMM_MOD_ID}__min_cash_reserve }
\t\t\t\tif = {
\t\t\t\t\tlimit = { has_variable = eu5ab_global_min_cash_reserve }
\t\t\t\t\tif = {
\t\t\t\t\t\tlimit = { "variable_map(cmm|flag:{CMM_MOD_ID}__min_cash_reserve)" = 100000 var:eu5ab_global_min_cash_reserve < 100000 }
\t\t\t\t\t\tset_variable = { name = eu5ab_cmm_shift_step value = { value = var:eu5ab_global_min_cash_reserve add = 1000 max = 100000 } }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__min_cash_reserve value = var:eu5ab_cmm_shift_step }
\t\t\t\t\t}
\t\t\t\t\telse_if = {
\t\t\t\t\t\tlimit = { "variable_map(cmm|flag:{CMM_MOD_ID}__min_cash_reserve)" = 0 var:eu5ab_global_min_cash_reserve > 0 }
\t\t\t\t\t\tset_variable = { name = eu5ab_cmm_shift_step value = { value = var:eu5ab_global_min_cash_reserve subtract = 1000 min = 0 } }
\t\t\t\t\t\tcmm_set_setting_value = { setting = {CMM_MOD_ID}__min_cash_reserve value = var:eu5ab_cmm_shift_step }
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t\tif = {
\t\t\t\tlimit = { var:cmf_callback = flag:{CMM_MOD_ID}__governor_migration_threshold_percent }
\t\t\t\teu5ab_governor_adjust_threshold_step = yes
\t\t\t}
\t\t\tif = {
\t\t\t\tlimit = { var:cmf_callback = flag:{CMM_MOD_ID}__naval_governor_migration_threshold_percent }
\t\t\t\teu5ab_naval_planner_adjust_threshold_step = yes
\t\t\t\tset_variable = eu5ab_naval_planner_dirty
\t\t\t}
\t\t\tif = {
\t\t\t\tlimit = { var:cmf_callback = flag:{CMM_MOD_ID}__rgo_job_fill_deadline_months }
\t\t\t\teu5ab_rgo_adjust_horizon_step = yes
\t\t\t}
\t\t\tremove_variable = eu5ab_cmm_shift_step
\t\t\teu5ab_sync_cmm_settings = yes
\t\t\tif = {
\t\t\t\tlimit = {
\t\t\t\t\tOR = {
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__budget_mode
\t\t\t\t\t\tvar:cmf_callback = flag:{CMM_MOD_ID}__fixed_annual_budget
\t\t\t\t\t}
\t\t\t\t}
\t\t\t\teu5ab_refresh_global_budget = yes
\t\t\t}
\t\t}
\t}
}

# The GUI bridge variable is saved by the engine; do not reopen a window merely
# because the player saved while it was visible.
on_game_load_after_lobby_human_country = {
\ton_actions = {
\t\teu5ab_on_cmf_after_load
\t}
}

eu5ab_on_cmf_after_load = {
\teffect = {
\t\t# No synchronous dispatcher survives a load. Retire the saved guard
\t\t# here, before recovery; normal queue cleanup must preserve reentry protection.
\t\tremove_variable = eu5ab_batch_running
\t\tremove_variable = eu5ab_cmf_window_requested
\t\tremove_variable = eu5ab_governor_window
\t\tremove_variable = eu5ab_governor_window_requested
\t\tset_variable = eu5ab_governor_dirty
\t\tset_variable = eu5ab_naval_planner_dirty
\t\teu5ab_mark_interrupted_scan_on_load = yes
\t\teu5ab_recover_runtime_after_load = yes
\t\teu5ab_sync_cmm_settings = yes
\t\teu5ab_schedule_scan_resume_after_load = yes
\t\teu5ab_ensure_annual_budget = yes
\t}
}

# Periodic refresh also catches expiring effects without native hooks.
on_road_construction_started = {
\ton_actions = { eu5ab_governor_dirty_from_road }
}
on_road_construction_ended = {
\ton_actions = { eu5ab_governor_dirty_from_road }
}
on_road_built = {
\ton_actions = { eu5ab_governor_dirty_from_road }
}
eu5ab_governor_dirty_from_road = {
{governor_country_dirty_effect}
}
on_building_construction_started = {
\ton_actions = { eu5ab_governor_dirty_from_building }
}
on_building_construction_ended = {
\ton_actions = { eu5ab_governor_dirty_from_building }
}
on_building_built = {
\ton_actions = { eu5ab_governor_dirty_from_building }
}
on_building_destroyed = {
\ton_actions = { eu5ab_governor_dirty_from_building }
}
eu5ab_governor_dirty_from_building = {
\teffect = {
\t\tlocation ?= {
\t\t\towner ?= {
\t\t\t\tif = { limit = { is_human = yes } set_variable = eu5ab_governor_dirty set_variable = eu5ab_naval_planner_dirty }
\t\t\t}
\t\t}
\t}
}

on_location_changed_rank = {
\ton_actions = { eu5ab_governor_dirty_from_location }
}

eu5ab_governor_dirty_from_location = {
\teffect = {
\t\towner ?= {
\t\t\tif = { limit = { is_human = yes } set_variable = eu5ab_governor_dirty
\t\t\t\tset_variable = eu5ab_naval_planner_dirty }
\t\t}
\t}
}

# Append distinct callbacks without replacing vanilla/other mods' effects.
# Keep the country guard: reform notifications may use organization scope.
# Reform changes can batch identical notifications; mark dirty inline so the
# engine does not queue the same child on-action repeatedly.
on_capital_moved = {
\ton_actions = { eu5ab_governor_dirty_on_capital_moved }
}
eu5ab_governor_dirty_on_capital_moved = {
{governor_country_dirty_effect}
}

on_reform_change = {
{governor_country_dirty_effect}
}

on_policy_changed = {
\ton_actions = { eu5ab_governor_dirty_on_policy_changed }
}
eu5ab_governor_dirty_on_policy_changed = {
{governor_country_dirty_effect}
}

on_country_rank_change = {
\ton_actions = { eu5ab_governor_dirty_on_country_rank_change }
}
eu5ab_governor_dirty_on_country_rank_change = {
{governor_country_dirty_effect}
}
"""
    return (
        script.replace("{registration}", registration)
        .replace("{governor_country_dirty_effect}", governor_country_dirty_effect)
        .replace(
            "{ownership_unregister_cases}",
            "\n".join(
                f"\t\t\t\t\t{bucket} = {{ remove_list_variable = {{ name = eu5ab_scan_bucket_{bucket}_locations target = root }} }}"
                for bucket in range(1, 21)
            ),
        )
        .replace("{CMM_MOD_ID}", CMM_MOD_ID)
    )


def render_events() -> str:
    return """# Generated by eu5autobuild.generator.
namespace = eu5ab_monthly

eu5ab_monthly.1 = {
\ttype = country_event
\ttitle = eu5ab_window_title
\toutcome = neutral
\thidden = yes

\timmediate = {
\t\t# Vanilla building allow/potential checks resolve the constructing country
\t\t# through scope:actor. Each delayed country event must recreate that scope.
\t\tsave_scope_as = actor
\t\teu5ab_expire_old_scan_month = yes
\t\tif = {
\t\t\tlimit = { eu5ab_scan_calendar_open = yes NOT = { eu5ab_scan_month_current = yes } is_human = yes var:eu5ab_global_enabled > 0 NOT = { has_variable = eu5ab_scan_resume_after_load } NOT = { has_variable = eu5ab_scan_active } NOT = { has_variable = eu5ab_scan_round_active } NOT = { has_variable = eu5ab_q_active } }
\t\t\teu5ab_reset_policy_budgets_if_needed = yes
\t\t\teu5ab_run_regional_development_policy = yes
\t\t}
\t\tif = {
\t\t\tlimit = { has_variable = eu5ab_scan_active eu5ab_scan_month_current = yes eu5ab_scan_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load }
\t\t\t\tOR = { NOT = { has_variable = eu5ab_scan_dispatch_day } NOT = { var:eu5ab_scan_dispatch_day = eu5ab_pl_today } } }
\t\t\tset_variable = { name = eu5ab_scan_dispatch_day value = eu5ab_pl_today }
\t\t\teu5ab_finish_pending_capacity_workers = yes
\t\t\teu5ab_merge_location_worker_results = yes
\t\t\tif = { limit = { var:eu5ab_scan_bucket_day <= 20 } eu5ab_scan_regional_development_bucket = yes }
\t\t\telse = { eu5ab_scan_initial_tail = yes }
\t\t\tif = {
\t\t\t\tlimit = { var:eu5ab_scan_bucket_day < 21 }
\t\t\t\tchange_variable = { name = eu5ab_scan_bucket_day add = 1 }
\t\t\t\ttrigger_event_silently = { id = eu5ab_monthly.1 days = 1 }
\t\t\t}
\t\t\telse = { set_variable = eu5ab_scan_finalizing trigger_event_silently = { id = eu5ab_monthly.2 days = 1 } }
\t\t}
\t\telse_if = { limit = { has_variable = eu5ab_scan_active eu5ab_queue_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load } }
\t\t\tset_variable = eu5ab_scan_finalizing trigger_event_silently = { id = eu5ab_monthly.2 days = 1 }
\t\t}
\t}
}

eu5ab_monthly.2 = {
\ttype = country_event
\ttitle = eu5ab_window_title
\toutcome = neutral
\thidden = yes

\timmediate = {
\t\t# Keep the constructing country available while finalizing and dispatching the queue.
\t\tsave_scope_as = actor
\t\teu5ab_expire_old_scan_month = yes
\t\tif = {
\t\t\tlimit = { has_variable = eu5ab_scan_active eu5ab_queue_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load } }
\t\t\teu5ab_finish_pending_capacity_workers = yes
\t\t\teu5ab_merge_location_worker_results = yes
\t\t\teu5ab_finish_regional_development_scan = yes
\t\t}
\t\telse_if = {
\t\t\t# Old saves can already have a finalizer scheduled for the 22nd.
\t\t\tlimit = { has_variable = eu5ab_scan_active eu5ab_scan_month_current = yes eu5ab_scan_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load } }
\t\t\tif = { limit = { OR = { NOT = { has_variable = eu5ab_scan_dispatch_day } NOT = { var:eu5ab_scan_dispatch_day = eu5ab_pl_today } } }
\t\t\t\tset_variable = { name = eu5ab_scan_dispatch_day value = eu5ab_pl_today }
\t\t\t\teu5ab_finish_pending_capacity_workers = yes
\t\t\t\teu5ab_merge_location_worker_results = yes
\t\t\t\teu5ab_scan_initial_tail = yes
\t\t\t}
\t\t\ttrigger_event_silently = { id = eu5ab_monthly.2 days = 1 }
\t\t}
\t}
}

# Continue persisted work after scheduled pre-load events have drained.
""" + save_resume.render_event() + """
""" + scan_reserve.render_events() + production_cohorts.render_event() + """
namespace = eu5ab_queue_watchdog

eu5ab_queue_watchdog.1 = {
\ttype = country_event
\ttitle = eu5ab_window_title
\toutcome = neutral
\thidden = yes

\timmediate = {
\t\teu5ab_expire_old_scan_month = yes
\t\tif = {
\t\t\tlimit = { has_variable = eu5ab_q_active eu5ab_queue_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load } }
\t\t\teu5ab_check_engine_candidate_queue_watchdog = yes
\t\t\t# A successful check may finish the queue. Only an active queue needs
\t\t\t# another independent liveness check.
\t\t\tif = {
\t\t\t\tlimit = { has_variable = eu5ab_q_active NOT = { has_variable = eu5ab_scan_resume_after_load } }
\t\t\t\ttrigger_event_silently = { id = eu5ab_queue_watchdog.1 days = {ENGINE_QUEUE_WATCHDOG_INTERVAL_DAYS} }
\t\t\t}
\t\t}
\t}
}

namespace = eu5ab_worker

eu5ab_worker.1 = {
\ttype = location_event
\ttitle = eu5ab_window_title
\toutcome = neutral
\thidden = yes

\timmediate = {
\t\t# Recreate actor for vanilla building allow/potential checks. All mutations
\t\t# below remain on this location until the country reducer runs next day.
\t\towner = { save_scope_as = actor }
\t\t# An event from an earlier scan must not consume a fresh request that
\t\t# is still waiting for its GUI snapshot. The daily fallback handles it.
\t\tif = {
\t\t\tlimit = { NOT = { has_variable = eu5ab_capacity_requested } }
\t\t\teu5ab_run_capacity_worker_once = yes
\t\t}
\t}
}
""".replace(
        "{ENGINE_QUEUE_WATCHDOG_INTERVAL_DAYS}",
        str(ENGINE_QUEUE_WATCHDOG_INTERVAL_DAYS),
    )


def render_scripted_effects(policies: list[Policy], catalog: BuildingCatalog, rules: AutomationRules) -> str:
    # The preset selector is consumed directly from CMM, never as a scalar.
    global_setting_ids = tuple(key for key in GLOBAL_RULE_DEFAULTS if key != "performance_preset")
    global_effects = [
        "eu5ab_sync_cmf_action_bar_toggle = {",
        "\tcmm_for_each_list_item = {",
        "\t\tsetting = cmf_core__action_bar_buttons",
        "\t\teffect = eu5ab_sync_cmf_action_bar_toggle_item",
        "\t}",
        "}",
        "",
        "eu5ab_sync_cmf_action_bar_toggle_item = {",
        "\tif = {",
        "\t\t# Consume the iterator's setting/i contract and reject rows without an attached value;",
        "\t\t# CMF's temporary value scope may still refer to the preceding row.",
        "\t\tlimit = { has_variable_list = $setting$_i$i$_value scope:cmm_list_current_item_value = flag:eu5ab_action_bar }",
        "\t\tif = {",
        "\t\t\tlimit = { is_target_in_variable_list = { name = cmf_action_bar_active_elements target = flag:eu5ab_action_bar } }",
        "\t\t\tcmm_set_list_field_value = { mod_id = cmf_core setting_id = action_bar_buttons field_id = active item = $i$ value = 1 }",
        "\t\t}",
        "\t\telse = { cmm_set_list_field_value = { mod_id = cmf_core setting_id = action_bar_buttons field_id = active item = $i$ value = 0 } }",
        "\t}",
        "}",
        "",
        "eu5ab_sync_cmm_settings = {",
        "\t# CMM owns these country/save settings; EU5AB mirrors them for fast runtime reads.",
        "\teu5ab_governor_initialize_threshold_setting = yes",
        "\teu5ab_naval_planner_initialize_threshold_setting = yes",
        "\teu5ab_governor_initialize_relocation_setting = yes",
        "\teu5ab_initialize_rgo_settings = yes",
    ]
    for setting_id in global_setting_ids:
        global_effects.append(
            f"\tset_variable = {{ name = {_global_setting_var(setting_id)} "
            f"value = {_cmm_setting_value(setting_id)} }}"
        )
    global_effects.extend([
        "\teu5ab_governor_apply_migration_settings = yes",
        "\teu5ab_rebuild_candidate_priority = yes",
        "}",
        "",
        "eu5ab_rebuild_candidate_priority = {",
        f"\tcmm_build_list_ordered_values = {{ setting = {CMM_SETTING_PREFIX}{CMM_CANDIDATE_PRIORITY_SETTING} list_name = eu5ab_candidate_priority_features }}",
        "\t# Saved games without an initialized CMM list retain deterministic defaults.",
        "\tset_variable = { name = eu5ab_candidate_priority_upgrade value = 1 }",
        "\tset_variable = { name = eu5ab_candidate_priority_expand value = 2 }",
        "\tset_variable = { name = eu5ab_candidate_priority_rgo value = 3 }",
        "\tset_variable = { name = eu5ab_candidate_priority_new value = 4 }",
        "\tif = {",
        "\t\tlimit = { has_variable_list = eu5ab_candidate_priority_features }",
        "\t\tsave_scope_as = eu5ab_priority_country",
        "\t\tset_variable = { name = eu5ab_candidate_priority_counter value = 0 }",
        "\t\tevery_in_list = {",
        "\t\t\tvariable = eu5ab_candidate_priority_features",
        "\t\t\tsave_scope_as = eu5ab_priority_feature",
        "\t\t\tscope:eu5ab_priority_country = {",
        "\t\t\t\tchange_variable = { name = eu5ab_candidate_priority_counter add = 1 }",
        "\t\t\t\tswitch = {",
        "\t\t\t\t\ttrigger = scope:eu5ab_priority_feature",
        *(
            f"\t\t\t\t\tflag:{feature_flag} = {{ set_variable = {{ name = eu5ab_candidate_priority_{feature_id} value = var:eu5ab_candidate_priority_counter }} }}"
            for feature_id, feature_flag in CANDIDATE_PRIORITY_FEATURES
        ),
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
        "\t\tremove_variable = eu5ab_candidate_priority_counter",
        "\t}",
        "}",
        "",
        "eu5ab_recalculate_budget_limit = {",
        "\tif = {",
        f"\t\tlimit = {{ var:{_global_setting_var('budget_mode')} = {CMM_BUDGET_MODE_FIXED} }}",
        f"\t\tset_variable = {{ name = eu5ab_global_budget_limit value = var:{_global_setting_var('fixed_annual_budget')} }}",
        "\t}",
    ])
    for mode, multiplier in (
        (CMM_BUDGET_MODE_INCOME_X4, 4),
        (CMM_BUDGET_MODE_INCOME_X6, 6),
        (CMM_BUDGET_MODE_INCOME_X8, 8),
    ):
        global_effects.extend([
            "\telse_if = {",
            f"\t\tlimit = {{ var:{_global_setting_var('budget_mode')} = {mode} }}",
            "\t\tset_variable = { name = eu5ab_global_budget_limit value = {",
            "\t\t\tvalue = monthly_income_total",
            f"\t\t\tmultiply = {multiplier}",
            "\t\t} }",
            "\t}",
        ])
    global_effects.extend([
        "\telse = {",
        "\t\t# Defensive fallback for settings saved by an incompatible CMM version.",
        "\t\tset_variable = { name = eu5ab_global_budget_limit value = {",
        "\t\t\tvalue = monthly_income_total",
        f"\t\t\tmultiply = {BUILTIN_BUDGET_MULTIPLIER}",
        "\t\t} }",
        "\t}",
        "}",
        "",
    ])
    chunks = [
        "# Generated by eu5autobuild.generator.",
        *global_effects,
        "# Persistent twenty-bucket location registry. Policy application and owner",
        "# changes maintain it incrementally; monthly scans never rebuild all locations.",
        "eu5ab_register_location_for_scan = {",
        "\teu5ab_sync_location_template_coverage = yes",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_policy_id NOT = { has_variable = eu5ab_scan_bucket } }",
        "\t\tsave_scope_as = eu5ab_registry_location",
        "\t\towner = {",
        "\t\t\tif = { limit = { NOT = { has_variable = eu5ab_scan_bucket_assignment } } set_variable = { name = eu5ab_scan_bucket_assignment value = 0 } }",
        "\t\t\tchange_variable = { name = eu5ab_scan_bucket_assignment add = 1 }",
        "\t\t\tif = { limit = { var:eu5ab_scan_bucket_assignment > 20 } set_variable = { name = eu5ab_scan_bucket_assignment value = 1 } }",
        "\t\t\tset_variable = { name = eu5ab_scan_registry_schema_version value = 1 }",
        "\t\t\tscope:eu5ab_registry_location = { set_variable = { name = eu5ab_scan_bucket value = owner.var:eu5ab_scan_bucket_assignment } }",
        "\t\t\tswitch = {",
        "\t\t\t\ttrigger = var:eu5ab_scan_bucket_assignment",
        *(f"\t\t\t\t{bucket} = {{ add_to_variable_list = {{ name = eu5ab_scan_bucket_{bucket}_locations target = scope:eu5ab_registry_location }} }}" for bucket in range(1, 21)),
        "\t\t\t}",
        "\t\t}",
        "\t}",
        "}",
        "",
        "eu5ab_unregister_location_from_scan = {",
        "\towner ?= { eu5ab_ensure_template_coverage = yes }",
        "\teu5ab_remove_location_template_coverage = yes",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_scan_bucket }",
        "\t\tsave_scope_as = eu5ab_registry_location",
        "\t\towner = {",
        "\t\t\tswitch = {",
        "\t\t\t\ttrigger = scope:eu5ab_registry_location.var:eu5ab_scan_bucket",
        *(f"\t\t\t\t{bucket} = {{ remove_list_variable = {{ name = eu5ab_scan_bucket_{bucket}_locations target = scope:eu5ab_registry_location }} }}" for bucket in range(1, 21)),
        "\t\t\t}",
        "\t\t}",
        "\t\tremove_variable = eu5ab_scan_bucket",
        "\t}",
        "}",
        "",
        "# One-time repair for saves produced while the visible template actions",
        "# wrote policy bindings without registering their locations in the buckets.",
        "eu5ab_rebuild_scan_registry_v1 = {",
        *(f"\tclear_variable_list = eu5ab_scan_bucket_{bucket}_locations" for bucket in range(1, 21)),
        "\tremove_variable = eu5ab_scan_bucket_assignment",
        "\tevery_owned_location = {",
        "\t\tif = {",
        "\t\t\tlimit = { has_variable = eu5ab_policy_id }",
        "\t\t\tremove_variable = eu5ab_scan_bucket",
        "\t\t\teu5ab_register_location_for_scan = yes",
        "\t\t}",
        "\t}",
        "\tset_variable = { name = eu5ab_scan_registry_schema_version value = 1 }",
        "}",
        "",
        "eu5ab_clear_location_policy = {",
        *_clear_location_policy_lines("\t"),
        "}",
        "",
        "eu5ab_reset_policy_budgets_if_needed = {",
        "\teu5ab_template_ensure_defaults = yes",
        "\t# Every template shares one country-level CMM-controlled annual pool.",
        "\tif = {",
        "\t\tlimit = { OR = { NOT = { has_variable = eu5ab_budget_initialized } current_month = 1 } }",
        "\t\tset_variable = eu5ab_budget_initialized",
        "\t\teu5ab_refresh_global_budget = yes",
    ]
    chunks.extend([
        "\t}",
        "}",
        "",
        "eu5ab_run_regional_development_policy = {",
        "\tevery_owned_location = {",
        "\t\tlimit = { has_variable = eu5ab_policy_id }",
        "\t\teu5ab_try_construct_policy_candidate = yes",
        "\t}",
        "}",
        "",
        "eu5ab_try_construct_policy_candidate = {",
        "\t# The effect body is generated as a policy router. Candidate selection uses",
        "\t# scripted triggers/values so that tests can mirror the same priority order.",
    ])
    for index, policy in enumerate(policies):
        value = _policy_index(policy, index)
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ var:eu5ab_policy_id = {value} }}",
            f"\t\teu5ab_try_construct_{policy.id} = yes",
            "\t}",
        ])
    chunks.extend([
        "\tif = {",
        f"\t\tlimit = {{ var:eu5ab_policy_id = {CUSTOM_POLICY_VALUE} }}",
        "\t\teu5ab_try_construct_custom_template = yes",
        "\t}",
    ])
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ var:eu5ab_template_slot = {slot} }}",
            f"\t\teu5ab_try_construct_template_slot_{slot} = yes",
            "\t}",
        ])
    chunks.extend(["}", ""])

    for index, policy in enumerate(policies):
        chunks.extend([
            f"eu5ab_apply_policy_{policy.id}_to_location = {{",
            f"\tset_variable = {{ name = eu5ab_policy_id value = {_policy_index(policy, index)} }}",
            "\tremove_variable = eu5ab_policy_decoupled",
            "\teu5ab_register_location_for_scan = yes",
            "}",
            "",
            f"eu5ab_try_construct_{policy.id} = {{",
        ])
        if policy.auto_build_input_sources:
            chunks.extend([
                "\tif = {",
                f"\t\tlimit = {{ NOT = {{ eu5ab_{policy.id}_has_input_materials = yes }} }}",
                f"\t\teu5ab_try_construct_{policy.id}_input_source = yes",
                "\t}",
            ])
        chunks.extend([
            "\tordered_buildable_building_type = {",
            "\t\tposition = 0",
            f"\t\torder_by = eu5ab_score_{policy.id}",
            "\t\tlimit = {",
            f"\t\t\teu5ab_{policy.id}_building_allowed = yes",
            f"\t\t\teu5ab_{policy.id}_special_building_allowed = yes",
            f"\t\t\teu5ab_{policy.id}_has_local_workforce = yes",
            f"\t\t\teu5ab_{policy.id}_has_input_materials = yes",
            f"\t\t\teu5ab_{policy.id}_price_in_range = yes",
            f"\t\t\teu5ab_{policy.id}_has_budget = yes",
            f"\t\t\teu5ab_{policy.id}_keeps_cash_reserve = yes",
            "\t\t}",
            "\t\troot = {",
            "\t\t\tconstruct_building = {",
            "\t\t\t\tbuilding_type = prev",
            "\t\t\t\tinstant = no",
            "\t\t\t\towner = owner",
            "\t\t\t\tpayer = owner",
            "\t\t\t}",
            "\t\t}",
            "\t}",
            "}",
            "",
        ])
        if policy.auto_build_input_sources:
            chunks.extend([
                f"eu5ab_try_construct_{policy.id}_input_source = {{",
                "\t# Optional upstream construction pass independently repairs input shortages",
                "\t# by missing construction or production materials. It intentionally bypasses",
                "\t# the normal allowlist, but still respects bans, special-building, workforce,",
                "\t# price, annual budget, and cash reserve checks.",
                "\tordered_buildable_building_type = {",
                "\t\tposition = 0",
                f"\t\torder_by = eu5ab_score_{policy.id}",
                "\t\tlimit = {",
                f"\t\t\teu5ab_{policy.id}_input_source_building_allowed = yes",
                f"\t\t\teu5ab_{policy.id}_special_building_allowed = yes",
                f"\t\t\teu5ab_{policy.id}_has_local_workforce = yes",
                f"\t\t\teu5ab_{policy.id}_price_in_range = yes",
                f"\t\t\teu5ab_{policy.id}_has_budget = yes",
                f"\t\t\teu5ab_{policy.id}_keeps_cash_reserve = yes",
                "\t\t}",
                "\t\troot = {",
                "\t\t\tconstruct_building = {",
                "\t\t\t\tbuilding_type = prev",
                "\t\t\t\tinstant = no",
                "\t\t\t\towner = owner",
                "\t\t\t\tpayer = owner",
                "\t\t\t}",
                "\t\t}",
                "\t}",
                "}",
                "",
            ])
    building_ids = _catalog_building_ids(catalog)

    def add_slot_defaults(slot: int) -> None:
        chunks.extend([
            f"eu5ab_template_slot_{slot}_ensure_defaults = {{",
            f"\tif = {{ limit = {{ NOT = {{ has_variable = {_slot_var(slot, 'name_id')} }} }} set_variable = {{ name = {_slot_var(slot, 'name_id')} value = {slot} }} }}",
            f"\tif = {{ limit = {{ NOT = {{ has_variable = {_slot_var(slot, 'name_selected')} }} }} set_variable = {{ name = {_slot_var(slot, 'name_selected')} value = 0 }} }}",
            f"\tif = {{ limit = {{ NOT = {{ has_variable = {_slot_var(slot, 'preset_origin')} }} }} set_variable = {{ name = {_slot_var(slot, 'preset_origin')} value = 0 }} }}",
            "\t# Retired scalar settings in old saves are inert; only the priority map is read.",
            "\t# One building-type-keyed map replaces hundreds of scalar checks. The",
            "\t# marker keeps an intentionally empty map from being reseeded on reload.",
            "\tif = {",
            f"\t\tlimit = {{ NOT = {{ has_variable = {_slot_var(slot, TEMPLATE_PRIORITIES_INITIALIZED_SUFFIX)} }} }}",
            "\t\tif = {",
            f"\t\t\tlimit = {{ NOT = {{ has_variable_map = {_slot_priority_map(slot)} }} }}",
        ])
        for building_id in building_ids:
            default_priority = rules.building_priority_for(building_id)
            if default_priority > 0:
                chunks.append(
                    f"\t\t\tadd_to_variable_map = {{ name = {_slot_priority_map(slot)} key = building_type:{building_id} value = {default_priority:g} }}"
                )
        chunks.extend([
            "\t\t}",
            f"\t\tset_variable = {{ name = {_slot_var(slot, TEMPLATE_PRIORITIES_INITIALIZED_SUFFIX)} value = 1 }}",
            "\t}",
        ])
        chunks.extend(["}", ""])

    def add_slot_save(slot: int) -> None:
        chunks.extend([
            f"eu5ab_template_slot_{slot}_save = {{",
            f"\teu5ab_template_slot_{slot}_ensure_defaults = yes",
            f"\tset_variable = {{ name = {_slot_var(slot, 'exists')} value = 1 }}",
            f"\tset_variable = {{ name = {_slot_var(slot, 'saved')} value = 1 }}",
            "}",
            "",
        ])

    def add_slot_copy(src: int, dst: int) -> None:
        chunks.extend([
            f"eu5ab_copy_template_slot_{src}_to_slot_{dst} = {{",
            f"\teu5ab_load_template_slot_{src}_into_editor = yes",
            f"\teu5ab_commit_template_editor_to_slot_{dst}_and_refresh_budget = yes",
            "}",
            "",
        ])

    for slot in TEMPLATE_SLOTS:
        add_slot_defaults(slot)
        add_slot_save(slot)

    chunks.extend([
        "eu5ab_template_ensure_defaults = {",
    ])
    for slot in TEMPLATE_SLOTS:
        chunks.append(f"\teu5ab_template_slot_{slot}_ensure_defaults = yes")
    chunks.extend(["}", ""])

    scalar_suffixes = TEMPLATE_SCALAR_SUFFIXES
    toggle_suffixes = TEMPLATE_TOGGLE_SUFFIXES

    def copy_optional_name(source: str, destination: str) -> None:
        # User text is a flag scope, not a numeric scalar. An absent source
        # must clear a previous name when switching editors or reusing a slot.
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ has_variable = {source} }}",
            f"\t\tset_variable = {{ name = {destination} value = var:{source} }}",
            "\t}",
            "\telse = {",
            f"\t\tremove_variable = {destination}",
            "\t}",
        ])

    def add_new_template_loader(effect_id: str, *, recommended: bool) -> None:
        chunks.extend([
            f"{effect_id} = {{",
            f"\tremove_variable = {_editor_var('custom_name')}",
            f"\tset_variable = {{ name = {_editor_var('name_id')} value = 6 }}",
            f"\tset_variable = {{ name = {_editor_var('name_selected')} value = 0 }}",
            f"\tset_variable = {{ name = {_editor_var('preset_origin')} value = 0 }}",
        ])
        for suffix in toggle_suffixes:
            chunks.append(
                f"\tset_variable = {{ name = {_editor_var(suffix)} value = 0 }}"
            )
        for building_id in building_ids:
            priority = rules.building_priority_for(building_id) if recommended else 0
            chunks.append(
                f"\tset_variable = {{ name = {_editor_priority_var(building_id)} "
                f"value = {priority:g} }}"
            )
        chunks.extend(["}", ""])

    add_new_template_loader(
        "eu5ab_load_blank_template_into_editor",
        recommended=False,
    )
    add_new_template_loader(
        "eu5ab_load_recommended_template_into_editor",
        recommended=True,
    )
    chunks.extend([
        "# Compatibility alias: the former new-template action used recommended defaults.",
        "eu5ab_load_new_template_into_editor = {",
        "\teu5ab_load_recommended_template_into_editor = yes",
        "}",
        "",
    ])

    def add_editor_load(slot: int) -> None:
        chunks.extend([
            f"eu5ab_load_template_slot_{slot}_into_editor = {{",
            f"\tset_variable = {{ name = eu5ab_active_template_slot value = {slot} }}",
            f"\teu5ab_template_slot_{slot}_ensure_defaults = yes",
        ])
        for suffix in scalar_suffixes:
            chunks.append(f"\tset_variable = {{ name = {_editor_var(suffix)} value = var:{_slot_var(slot, suffix)} }}")
        copy_optional_name(_slot_custom_name_var(slot), _editor_var('custom_name'))
        for suffix in toggle_suffixes:
            chunks.extend([
                f"\tset_variable = {{ name = {_editor_var(suffix)} value = 0 }}",
                "\tif = {",
                f"\t\tlimit = {{ has_variable = {_slot_var(slot, suffix)} }}",
                f"\t\tset_variable = {{ name = {_editor_var(suffix)} value = 1 }}",
                "\t}",
            ])
        for building_id in building_ids:
            chunks.extend([
                f"\tset_variable = {{ name = {_editor_priority_var(building_id)} value = 0 }}",
                f"\tif = {{ limit = {{ has_variable_map = {_slot_priority_map(slot)} is_key_in_variable_map = {{ name = {_slot_priority_map(slot)} target = building_type:{building_id} }} }} set_variable = {{ name = {_editor_priority_var(building_id)} value = \"variable_map({_slot_priority_map(slot)}|building_type:{building_id})\" }} }}",
            ])
        chunks.extend(["}", ""])

    def add_editor_commit(slot: int) -> None:
        chunks.extend([
            f"eu5ab_commit_template_editor_to_slot_{slot} = {{",
        ])
        for suffix in scalar_suffixes:
            chunks.append(f"\tset_variable = {{ name = {_slot_var(slot, suffix)} value = var:{_editor_var(suffix)} }}")
        copy_optional_name(_editor_var('custom_name'), _slot_custom_name_var(slot))
        for suffix in toggle_suffixes:
            chunks.extend([
                "\tif = {",
                f"\t\tlimit = {{ var:{_editor_var(suffix)} = 1 }}",
                f"\t\tset_variable = {{ name = {_slot_var(slot, suffix)} value = 1 }}",
                "\t}",
                "\telse = {",
                f"\t\tremove_variable = {_slot_var(slot, suffix)}",
                "\t}",
            ])
        for building_id in building_ids:
            chunks.extend([
                f"\tremove_from_variable_map = {{ name = {_slot_priority_map(slot)} key = building_type:{building_id} }}",
                f"\tif = {{ limit = {{ var:{_editor_priority_var(building_id)} > 0 }} add_to_variable_map = {{ name = {_slot_priority_map(slot)} key = building_type:{building_id} value = var:{_editor_priority_var(building_id)} }} }}",
            ])
        chunks.extend([
            f"\tset_variable = {{ name = {_slot_var(slot, TEMPLATE_PRIORITIES_INITIALIZED_SUFFIX)} value = 1 }}",
            f"\tset_variable = {{ name = {_slot_var(slot, 'exists')} value = 1 }}",
            f"\tset_variable = {{ name = {_slot_var(slot, 'saved')} value = 1 }}",
            f"\tclear_variable_list = eu5ab_active_normal_catalog_template_{slot}",
            f"\tremove_variable = eu5ab_active_normal_catalog_template_{slot}_ready",
            f"\tremove_variable = eu5ab_active_normal_catalog_template_{slot}_ready_month",
            f"\tremove_variable = eu5ab_active_normal_catalog_template_{slot}_ready_year",
            "}",
            "",
        ])

    for slot in TEMPLATE_SLOTS:
        add_editor_load(slot)
        add_editor_commit(slot)
        chunks.extend([
            f"eu5ab_commit_template_editor_to_slot_{slot}_and_refresh_budget = {{",
            f"\teu5ab_commit_template_editor_to_slot_{slot} = yes",
            "}",
            "",
        ])

    for index, policy in enumerate(policies):
        copied_buildings = set(policy.allowed_buildings) - set(policy.banned_buildings)
        chunks.extend([
            f"eu5ab_load_preset_{policy.id}_into_editor = {{",
            f"\tremove_variable = {_editor_var('custom_name')}",
            f"\tset_variable = {{ name = {_editor_var('name_id')} value = 6 }}",
            f"\tset_variable = {{ name = {_editor_var('name_selected')} value = 0 }}",
            f"\tset_variable = {{ name = {_editor_var('preset_origin')} value = {_policy_index(policy, index)} }}",
        ])
        for building_id in building_ids:
            copied_priority = 0.0
            if building_id in copied_buildings:
                copied_priority = max(
                    rules.building_priority_for(building_id),
                    1.0,
                )
            chunks.append(
                f"\tset_variable = {{ name = {_editor_priority_var(building_id)} "
                f"value = {copied_priority:g} }}"
            )
        chunks.extend(["}", ""])

    chunks.extend([
        "eu5ab_commit_active_template_editor = {",
    ])
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ var:eu5ab_active_template_slot = {slot} }}",
            f"\t\teu5ab_commit_template_editor_to_slot_{slot} = yes",
            "\t}",
        ])
    chunks.extend(["}", ""])
    chunks.extend([
        "eu5ab_select_first_player_template = {",
        "\tremove_variable = eu5ab_custom_templates_empty",
        "\tremove_variable = eu5ab_template_slot_claimed",
    ])
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ NOT = {{ has_variable = eu5ab_active_template_slot }} NOT = {{ has_variable = eu5ab_template_slot_claimed }} has_variable = {_slot_var(slot, 'exists')} }}",
            f"\t\tset_variable = {{ name = eu5ab_active_template_slot value = {slot} }}",
            "\t\tset_variable = { name = eu5ab_template_slot_claimed value = 1 }",
            "\t}",
        ])
    chunks.extend([
        "\tif = {",
        "\t\tlimit = { NOT = { has_variable = eu5ab_active_template_slot } }",
        "\t\tset_variable = { name = eu5ab_custom_templates_empty value = 1 }",
        "\t}",
        "\tremove_variable = eu5ab_template_slot_claimed",
        "}",
        "",
    ])
    chunks.extend([
        "# Build one transient view for the template currently opened in the scope window.",
        "# The previous implementation recalculated 20 slots and every preset on each click.",
        "eu5ab_prepare_template_scope_view = {",
        "\tset_variable = { name = eu5ab_scope_location_count value = 0 }",
        "\tset_variable = { name = eu5ab_scope_province_count value = 0 }",
        "\tset_variable = { name = eu5ab_scope_area_count value = 0 }",
        "\tevery_owned_location = {",
        "\t\tremove_variable = eu5ab_scope_view_selected",
        "\t\tif = {",
        "\t\t\tlimit = { root = { var:eu5ab_scope_view_mode = 1 } }",
        "\t\t\tif = {",
        "\t\t\t\tlimit = { has_variable = eu5ab_template_slot }",
        "\t\t\t\tif = {",
        "\t\t\t\t\tlimit = { var:eu5ab_template_slot = root.var:eu5ab_scope_view_value }",
        "\t\t\t\t\tset_variable = { name = eu5ab_scope_view_selected value = 1 }",
        "\t\t\t\t\troot = { change_variable = { name = eu5ab_scope_location_count add = 1 } }",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
        "\t\telse_if = {",
        "\t\t\tlimit = { root = { var:eu5ab_scope_view_mode = 2 } }",
        "\t\t\tif = {",
        "\t\t\t\tlimit = { NOT = { has_variable = eu5ab_template_slot } }",
        "\t\t\t\tif = {",
        "\t\t\t\t\tlimit = { has_variable = eu5ab_policy_id }",
        "\t\t\t\t\tif = {",
        "\t\t\t\t\t\tlimit = { var:eu5ab_policy_id = root.var:eu5ab_scope_view_value }",
        "\t\t\t\t\t\tset_variable = { name = eu5ab_scope_view_selected value = 1 }",
        "\t\t\t\t\t\troot = { change_variable = { name = eu5ab_scope_location_count add = 1 } }",
        "\t\t\t\t\t}",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
        "\t\tif = {",
        "\t\t\tlimit = { has_variable = eu5ab_scope_view_selected }",
        "\t\t\tprovince = {",
        "\t\t\t\tif = {",
        "\t\t\t\t\tlimit = { NOT = { is_in_list = eu5ab_scope_selected_provinces } }",
        "\t\t\t\t\tadd_to_temporary_list = eu5ab_scope_selected_provinces",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t\tarea = {",
        "\t\t\t\tif = {",
        "\t\t\t\t\tlimit = { NOT = { is_in_list = eu5ab_scope_selected_areas } }",
        "\t\t\t\t\tadd_to_temporary_list = eu5ab_scope_selected_areas",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
        "\t}",
        "\t# Count only the deduplicated parents reached from selected owned locations.",
        "\t# This replaces the former every_province/every_area world scans.",
        "\tevery_in_list = {",
        "\t\tlist = eu5ab_scope_selected_provinces",
        "\t\troot = { change_variable = { name = eu5ab_scope_province_count add = 1 } }",
        "\t}",
        "\tevery_in_list = {",
        "\t\tlist = eu5ab_scope_selected_areas",
        "\t\troot = { change_variable = { name = eu5ab_scope_area_count add = 1 } }",
        "\t}",
        "}",
        "",
    ])

    for src in TEMPLATE_SLOTS:
        for dst in TEMPLATE_SLOTS:
            if src != dst:
                add_slot_copy(src, dst)

    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            f"eu5ab_apply_template_slot_{slot}_to_target_location = {{",
            "\tscope:actor ?= {",
            f"\t\teu5ab_template_slot_{slot}_ensure_defaults = yes",
            "\t\tif = {",
            f"\t\t\tlimit = {{ NOT = {{ has_variable = {_slot_var(slot, 'saved')} }} }}",
            f"\t\t\teu5ab_template_slot_{slot}_save = yes",
            "\t\t}",
            "\t}",
            "\tscope:target_location ?= {",
            f"\t\tset_variable = {{ name = eu5ab_policy_id value = {CUSTOM_POLICY_VALUE} }}",
            f"\t\tset_variable = {{ name = eu5ab_template_slot value = {slot} }}",
            "\t\tremove_variable = eu5ab_policy_decoupled",
            "\t\teu5ab_register_location_for_scan = yes",
            "\t}",
            "}",
            "",
            f"eu5ab_apply_template_slot_{slot}_to_target_province = {{",
            "\tscope:target_province ?= {",
            "\t\tevery_location_in_province = {",
            "\t\t\tlimit = { owner ?= scope:actor }",
            "\t\t\tsave_scope_as = target_location",
            f"\t\t\tscope:actor ?= {{ eu5ab_apply_template_slot_{slot}_to_target_location = yes }}",
            "\t\t}",
            "\t}",
            "}",
            "",
            f"eu5ab_apply_template_slot_{slot}_to_target_area = {{",
            "\tscope:target_area ?= {",
            "\t\tevery_location_in_area = {",
            "\t\t\tlimit = { owner ?= scope:actor }",
            "\t\t\tsave_scope_as = target_location",
            f"\t\t\tscope:actor ?= {{ eu5ab_apply_template_slot_{slot}_to_target_location = yes }}",
            "\t\t}",
            "\t}",
            "}",
            "",
        ])

    chunks.extend([
        "eu5ab_try_construct_custom_template = {",
        "\t# Slot-specific template rules are routed by eu5ab_template_slot.",
        "}",
        "",
    ])
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            f"eu5ab_try_construct_template_slot_{slot} = {{",
            "\tordered_buildable_building_type = {",
            "\t\tposition = 0",
            f"\t\torder_by = eu5ab_score_template_slot_{slot}",
            "\t\tlimit = {",
            f"\t\t\teu5ab_template_slot_{slot}_building_allowed = yes",
            f"\t\t\teu5ab_template_slot_{slot}_special_building_allowed = yes",
            f"\t\t\teu5ab_template_slot_{slot}_has_local_workforce = yes",
            f"\t\t\teu5ab_template_slot_{slot}_has_input_materials = yes",
            f"\t\t\teu5ab_template_slot_{slot}_price_in_range = yes",
            f"\t\t\teu5ab_template_slot_{slot}_keeps_cash_reserve = yes",
            "\t\t}",
            "\t\troot = {",
            "\t\t\tconstruct_building = {",
            "\t\t\t\tbuilding_type = prev",
            "\t\t\t\tinstant = no",
            "\t\t\t\towner = owner",
            "\t\t\t\tpayer = owner",
            "\t\t\t}",
            "\t\t}",
            "\t}",
            "}",
            "",
        ])
    return "\n".join(chunks)


def _replace_top_level_script_block(text: str, name: str, replacement: str) -> str:
    marker = f"{name} = {{"
    start = text.find(marker)
    while start >= 0 and start > 0 and text[start - 1] != "\n":
        start = text.find(marker, start + 1)
    if start < 0:
        raise ValueError(f"Generated script block not found: {name}")

    depth = 0
    in_quote = False
    escaped = False
    opened = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == "{":
            opened = True
            depth += 1
        elif char == "}":
            depth -= 1
            if opened and depth == 0:
                end = index + 1
                while end < len(text) and text[end] == "\n":
                    end += 1
                return text[:start] + replacement.rstrip() + "\n\n" + text[end:]
    raise ValueError(f"Generated script block is unbalanced: {name}")


def _construction_demand_goods(
    construction_demands: dict[str, ConstructionDemand],
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                good
                for demand in construction_demands.values()
                for good, amount in demand.goods.items()
                if amount > 0
            }
        )
    )


def render_construction_material_script_values(
    construction_demands: dict[str, ConstructionDemand],
    rules: AutomationRules,
) -> str:
    """Generate per-building demand and per-market projected shortage values."""
    chunks = [
        "# Vanilla construction demand plus approvals already committed this cycle.",
        "eu5ab_construction_shortage_factor = {",
        '\tvalue = "define:NMarket|MARKET_CONSTRUCTION_NEEDS_BLOCK_FACTOR"',
        f"\tmultiply = {rules.thresholds.construction_stall_headroom_ratio:g}",
        "}",
        "",
    ]
    for good in _construction_demand_goods(construction_demands):
        chunks.extend([
            f"eu5ab_construction_demand_{good} = {{",
            "\tvalue = 0",
        ])
        branch = "if"
        for building_id, demand in sorted(construction_demands.items()):
            amount = demand.goods.get(good, 0)
            if amount <= 0:
                continue
            chunks.extend([
                f"\t{branch} = {{",
                f"\t\tlimit = {{ this = building_type:{building_id} }}",
                f"\t\tadd = {amount:g}",
                "\t}",
            ])
            branch = "else_if"
        chunks.extend([
            "}",
            "",
            f"eu5ab_market_{good}_projected_construction_overage = {{",
            f'\tvalue = "market.goods_demand_in_market(goods:{good})"',
            "\tmarket = { save_temporary_scope_as = eu5ab_material_market }",
            "\tif = {",
            "\t\tlimit = {",
            f"\t\t\thas_global_variable_map = eu5ab_q_market_committed_{good}",
            f"\t\t\tis_key_in_global_variable_map = {{ name = eu5ab_q_market_committed_{good} target = scope:eu5ab_material_market }}",
            "\t\t}",
            f'\t\tadd = "global_variable_map(eu5ab_q_market_committed_{good}|scope:eu5ab_material_market)"',
            "\t}",
            f"\tadd = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_construction_demand_{good}",
            "\tsubtract = {",
            f'\t\tvalue = "market.goods_supply_in_market(goods:{good})"',
            "\t\tmultiply = eu5ab_construction_shortage_factor",
            "\t}",
            "}",
            "",
        ])
    return "\n".join(chunks)


def render_construction_material_triggers(
    construction_demands: dict[str, ConstructionDemand],
    rules: AutomationRules,
) -> str:
    chunks = [
        "# Reject a candidate before approval if its actual vanilla material mix",
        "# would cross the construction-stall headroom or an extreme price ceiling.",
        "eu5ab_engine_construction_materials_available = {",
    ]
    for good in _construction_demand_goods(construction_demands):
        chunks.extend([
            "\ttrigger_if = {",
            f"\t\tlimit = {{ scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_construction_demand_{good} > 0 }}",
            f"\t\teu5ab_market_{good}_projected_construction_overage < 0",
            "\t\tmarket ?= {",
            f'\t\t\t"market_price(goods:{good})" <= {{',
            f'\t\t\t\tvalue = "default_price(goods:{good})"',
            f"\t\t\t\tmultiply = {rules.thresholds.construction_price_ceiling_ratio:g}",
            "\t\t\t}",
            "\t\t}",
            "\t}",
        ])
    chunks.extend(["}", ""])
    return "\n".join(chunks)


def render_engine_queue_triggers(
    catalog: BuildingCatalog,
    rules: AutomationRules,
) -> str:
    strategic_output_goods = (
        set(rules.food_goods)
        | set(rules.goods_groups["construction_core"])
        | set(rules.goods_groups["military"])
    )
    strategic_consumers_by_input: dict[str, tuple[str, ...]] = {}
    for good in sorted(rules.input_goods):
        consumers = tuple(sorted(
            building.id
            for building in catalog.buildings.values()
            if good in building.input_goods
            and strategic_output_goods.intersection(building.output_goods)
        ))
        if consumers and _supporting_building_ids((good,), catalog):
            strategic_consumers_by_input[good] = consumers

    chunks = [
        "# GUI-only actual values are passed as fixed-value scopes by the hidden bridge.",
        "# Candidate classes are mutually exclusive: replacement upgrade, from-zero new build,",
        "# or another level of an existing ordinary building.",
        "eu5ab_candidate_is_upgrade = {",
        "\teu5ab_candidate_replaces_existing_building = yes",
        "}",
        "",
        "eu5ab_candidate_is_new_build = {",
        "\tNOT = { eu5ab_candidate_replaces_existing_building = yes }",
        "\teu5ab_candidate_lacks_existing_building = yes",
        "}",
        "",
        "eu5ab_candidate_lacks_existing_building = {",
        "\tOR = {",
        *(
            f"\t\tAND = {{ this = building_type:{building_id} scope:{CANDIDATE_LOCATION_SCOPE} = {{ NOT = {{ has_building = building_type:{building_id} }} }} }}"
            for building_id in _catalog_building_ids(catalog)
        ),
        "\t}",
        "}",
        "",
        "eu5ab_candidate_is_expansion = {",
        "\tNOT = { eu5ab_candidate_replaces_existing_building = yes }",
        "\teu5ab_candidate_has_existing_building = yes",
        "}",
        "",
        "eu5ab_candidate_has_existing_building = {",
        "\tswitch = {",
        "\t\ttrigger = this",
        *(
            f"\t\tbuilding_type:{building_id} = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_building = building_type:{building_id} }} }}"
            for building_id in _catalog_building_ids(catalog)
        ),
        "\t\tfallback = { always = no }",
        "\t}",
        "}",
        "",
        "eu5ab_candidate_produces_food = {",
    ]
    chunks.extend(_food_support_trigger_lines(catalog, rules, "\t"))
    chunks.extend([
        "}",
        "",
        "# The two existing food switches own both parts of emergency response:",
        "# priority over non-food work and the ordinary-building return-metric bypass.",
        "eu5ab_food_emergency_enabled = {",
        "\tOR = {",
        "\t\tAND = {",
        f"\t\t\towner.var:{_global_setting_var('emergency_food_exhaustion_override')} > 0",
        "\t\t\tmarket ?= { is_projected_to_run_out_of_food_stockpile = yes }",
        "\t\t}",
        "\t\tAND = {",
        f"\t\t\towner.var:{_global_setting_var('emergency_food_stockpile_override')} > 0",
        f"\t\t\tmarket ?= {{ market_food_percentage <= {rules.thresholds.food_emergency_ratio:g} }}",
        "\t\t}",
        "\t}",
        "}",
        "",
        "eu5ab_rgo_food_emergency_enabled = {",
        "\teu5ab_food_emergency_enabled = yes",
        "\tOR = {",
        *(f"\t\traw_material = goods:{good}" for good in sorted(rules.food_goods)),
        "\t}",
        "}",
        "",
        "eu5ab_engine_candidate_is_food_emergency = {",
        "\teu5ab_food_emergency_enabled = yes",
        f"\tscope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_produces_food = yes }}",
        "}",
        "",
        *(
            line
            for priority_rank in range(1, len(CANDIDATE_PRIORITY_FEATURES) + 1)
            for line in (
                f"eu5ab_engine_candidate_feature_rank_{priority_rank} = {{",
                "\tOR = {",
                "\t\tAND = {",
                f"\t\t\tscope:eu5ab_engine_country.var:eu5ab_candidate_priority_upgrade = {priority_rank}",
                f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_is_upgrade = yes }}",
                "\t\t}",
                "\t\tAND = {",
                f"\t\t\tscope:eu5ab_engine_country.var:eu5ab_candidate_priority_new = {priority_rank}",
                f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_is_new_build = yes }}",
                "\t\t}",
                "\t\tAND = {",
                f"\t\t\tscope:eu5ab_engine_country.var:eu5ab_candidate_priority_expand = {priority_rank}",
                f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_is_expansion = yes }}",
                "\t\t}",
                "\t}",
                "}",
                "",
            )
        ),
        "# Eight queue phases implement the exact four-feature order twice:",
        "# food-emergency ranks 1-4 first, then normal ranks 1-4 as phases 5-8.",
        "eu5ab_engine_candidate_in_current_priority_phase = {",
        "\tOR = {",
        *(
            f"\t\tAND = {{ scope:eu5ab_engine_country.var:eu5ab_q_phase = {priority_rank} eu5ab_engine_candidate_is_food_emergency = yes eu5ab_engine_candidate_feature_rank_{priority_rank} = yes }}"
            for priority_rank in range(1, len(CANDIDATE_PRIORITY_FEATURES) + 1)
        ),
        *(
            f"\t\tAND = {{ scope:eu5ab_engine_country.var:eu5ab_q_phase = {priority_rank + len(CANDIDATE_PRIORITY_FEATURES)} NOT = {{ eu5ab_engine_candidate_is_food_emergency = yes }} eu5ab_engine_candidate_feature_rank_{priority_rank} = yes }}"
            for priority_rank in range(1, len(CANDIDATE_PRIORITY_FEATURES) + 1)
        ),
        *(f"\t\tAND = {{ scope:eu5ab_engine_country.var:eu5ab_q_phase = {rank + offset} {emergency} eu5ab_engine_candidate_feature_rank_{rank} = yes }}"
          for offset, emergency in ((8, "eu5ab_engine_candidate_is_food_emergency = yes"),
                                    (12, "NOT = { eu5ab_engine_candidate_is_food_emergency = yes }"))
          for rank in range(1, 5)),
        "\t}",
        "}",
        "",
        "eu5ab_rgo_in_current_priority_phase = {",
        "\tOR = {",
        *(
            f"\t\tAND = {{ owner.var:eu5ab_q_phase = {priority_rank} owner.var:eu5ab_candidate_priority_rgo = {priority_rank} eu5ab_rgo_food_emergency_enabled = yes }}"
            for priority_rank in range(1, len(CANDIDATE_PRIORITY_FEATURES) + 1)
        ),
        *(
            f"\t\tAND = {{ owner.var:eu5ab_q_phase = {priority_rank + len(CANDIDATE_PRIORITY_FEATURES)} owner.var:eu5ab_candidate_priority_rgo = {priority_rank} NOT = {{ eu5ab_rgo_food_emergency_enabled = yes }} }}"
            for priority_rank in range(1, len(CANDIDATE_PRIORITY_FEATURES) + 1)
        ),
        "\t}",
        "}",
        "",
        "eu5ab_engine_candidate_passes_selected_metric = {",
        "\tOR = {",
        "\t\tAND = {",
        "\t\t\tscope:eu5ab_engine_country = {",
        "\t\t\t\tOR = {",
        f"\t\t\t\t\tNOT = {{ has_variable = {_global_setting_var('economic_metric')} }}",
        f"\t\t\t\t\tvar:{_global_setting_var('economic_metric')} = {CMM_ECONOMIC_METRIC_TAX_INCOME}",
        "\t\t\t\t}",
        "\t\t\t}",
        f"\t\t\tscope:eu5ab_engine_income > {rules.thresholds.positive_profit:g}",
        "\t\t}",
        "\t\tAND = {",
        f"\t\t\tscope:eu5ab_engine_country = {{ var:{_global_setting_var('economic_metric')} = {CMM_ECONOMIC_METRIC_PROFIT} }}",
        f"\t\t\tscope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit > {rules.thresholds.positive_profit:g}",
        "\t\t}",
        "\t\tAND = {",
        f"\t\t\tscope:eu5ab_engine_country = {{ var:{_global_setting_var('economic_metric')} = {CMM_ECONOMIC_METRIC_ROI_TAX_INCOME} }}",
        "\t\t\tscope:eu5ab_engine_income >= {",
        "\t\t\t\tvalue = scope:eu5ab_engine_cost",
        f"\t\t\t\tmultiply = {rules.thresholds.engine_min_annual_return_ratio:g}",
        "\t\t\t\tdivide = 12",
        "\t\t\t}",
        "\t\t}",
        "\t\tAND = {",
        f"\t\t\tscope:eu5ab_engine_country = {{ var:{_global_setting_var('economic_metric')} = {CMM_ECONOMIC_METRIC_ROI_PROFIT} }}",
        "\t\t\tscope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit >= {",
        "\t\t\t\tvalue = scope:eu5ab_engine_cost",
        f"\t\t\t\tmultiply = {rules.thresholds.engine_min_annual_return_ratio:g}",
        "\t\t\t\tdivide = 12",
        "\t\t\t}",
        "\t\t}",
        "\t}",
        "}",
        "",
        "# Emergency demand is deliberately separate from candidate ranking. Each",
        "# reason has its own CMM switch and can bypass only the selected return metric.",
        "eu5ab_engine_candidate_uses_emergency_override = {",
        f"\tscope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_recipe_expected_output_value > 0",
        "\tNOT = { eu5ab_engine_candidate_passes_selected_metric = yes }",
        "\teu5ab_engine_candidate_has_emergency_demand = yes",
        "}", "",
        "eu5ab_engine_candidate_has_emergency_demand = {",
        "\tOR = {",
    ])

    food_goods = tuple(sorted(rules.food_goods))
    if _supporting_building_ids(food_goods, catalog):
        chunks.extend([
            "\t\tAND = {",
            f"\t\t\tscope:eu5ab_engine_country.var:{_global_setting_var('emergency_food_exhaustion_override')} > 0",
            f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{",
        ])
        chunks.extend(_support_trigger_lines(food_goods, catalog, "\t\t\t\t"))
        chunks.extend([
            "\t\t\t}",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.market ?= {{ is_projected_to_run_out_of_food_stockpile = yes }}",
            "\t\t}",
            "\t\tAND = {",
            f"\t\t\tscope:eu5ab_engine_country.var:{_global_setting_var('emergency_food_stockpile_override')} > 0",
            f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{",
        ])
        chunks.extend(_support_trigger_lines(food_goods, catalog, "\t\t\t\t"))
        chunks.extend([
            "\t\t\t}",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.market ?= {{ market_food_percentage <= {rules.thresholds.food_emergency_ratio:g} }}",
            "\t\t}",
        ])

    for good in sorted(set(rules.goods_groups["construction_core"])):
        if not _supporting_building_ids((good,), catalog):
            continue
        chunks.extend([
            "\t\tAND = {",
            f"\t\t\tscope:eu5ab_engine_country.var:{_global_setting_var('emergency_construction_goods_override')} > 0",
            f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{",
        ])
        chunks.extend(_support_trigger_lines((good,), catalog, "\t\t\t\t"))
        chunks.append("\t\t\t}")
        chunks.extend(_market_supply_condition_lines(
            good,
            rules.thresholds.goods_critical_supply_ratio,
            "\t\t\t",
        ))
        chunks.append("\t\t}")

    for good in sorted(set(rules.goods_groups["military"])):
        if not _supporting_building_ids((good,), catalog):
            continue
        chunks.extend([
            "\t\tAND = {",
            f"\t\t\tscope:eu5ab_engine_country.var:{_global_setting_var('emergency_wartime_military_override')} > 0",
            "\t\t\tscope:eu5ab_engine_country = { at_war = yes }",
            f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{",
        ])
        chunks.extend(_support_trigger_lines((good,), catalog, "\t\t\t\t"))
        chunks.append("\t\t\t}")
        chunks.extend(_market_supply_condition_lines(
            good,
            rules.thresholds.goods_critical_supply_ratio,
            "\t\t\t",
        ))
        chunks.append("\t\t}")

    for good, consumer_ids in strategic_consumers_by_input.items():
        chunks.extend([
            "\t\tAND = {",
            f"\t\t\tscope:eu5ab_engine_country.var:{_global_setting_var('emergency_strategic_input_override')} > 0",
            f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{",
        ])
        chunks.extend(_support_trigger_lines((good,), catalog, "\t\t\t\t"))
        chunks.extend([
            "\t\t\t}",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.market ?= {{",
            f'\t\t\t\t"goods_supply_in_market(goods:{good})" < {{',
            f'\t\t\t\t\tvalue = "goods_demand_in_market(goods:{good})"',
            f"\t\t\t\t\tmultiply = {rules.thresholds.goods_critical_supply_ratio:g}",
            "\t\t\t\t}",
            "\t\t\t\tany_location_in_market = {",
            "\t\t\t\t\tany_buildings_in_location = {",
            "\t\t\t\t\t\tOR = {",
            *(f"\t\t\t\t\t\t\tbuilding_type = building_type:{building_id}" for building_id in consumer_ids),
            "\t\t\t\t\t\t}",
            "\t\t\t\t\t\towner = scope:eu5ab_engine_country",
            "\t\t\t\t\t\tis_opened = yes",
            "\t\t\t\t\t\tis_lacking_goods = yes",
            "\t\t\t\t\t}",
            "\t\t\t\t}",
            "\t\t\t}",
            "\t\t}",
        ])

    chunks.extend([
        "\t}",
        "}",
        "",
        "eu5ab_engine_candidate_economically_sound = {",
        "\tscope:eu5ab_engine_cost > 0",
        "\tOR = {",
        "\t\t# Infrastructure without a production recipe has no comparable return metric.",
        f"\t\tscope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_recipe_expected_output_value <= 0",
        "\t\teu5ab_engine_candidate_passes_selected_metric = yes",
        "\t\teu5ab_engine_candidate_uses_emergency_override = yes",
        "\t}",
        "}",
        "",
        "eu5ab_engine_candidate_has_actual_budget = {",
        "\towner = {",
        "\t\tvar:eu5ab_global_budget_remaining >= {",
        "\t\t\tvalue = scope:eu5ab_engine_cost",
        "\t\t\tadd = var:eu5ab_q_planned_budget",
        "\t\t}",
        "\t}",
        "}",
        "",
        "eu5ab_engine_candidate_keeps_actual_cash_reserve = {",
        "\towner = {",
        "\t\tgold >= {",
        "\t\t\tvalue = scope:eu5ab_engine_cost",
        "\t\t\tadd = var:eu5ab_q_planned_spend",
        f"\t\t\tadd = scope:{CANDIDATE_LOCATION_SCOPE}.eu5ab_current_min_cash_reserve",
        "\t\t}",
        "\t}",
        "}",
        "",
    ])
    return "\n".join(chunks)


def render_construction_material_effects(
    construction_demands: dict[str, ConstructionDemand],
) -> str:
    goods = _construction_demand_goods(construction_demands)
    chunks = [
        "eu5ab_reset_committed_construction_demand = {",
        *(f"\tclear_global_variable_map = eu5ab_q_market_committed_{good}" for good in goods),
        "}",
        "",
        "# Reserve a candidate's material demand immediately after approval so",
        "# later candidates in the same GUI drain see the already-planned load.",
        "eu5ab_commit_candidate_construction_demand = {",
        "\tmarket = { save_temporary_scope_as = eu5ab_material_market }",
        "\tset_variable = { name = eu5ab_q_material_market value = scope:eu5ab_material_market }",
    ]
    for good in goods:
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_construction_demand_{good} > 0 }}",
            f"\t\tset_local_variable = {{ name = eu5ab_new_committed_{good} value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_construction_demand_{good} }}",
            "\t\tif = {",
            "\t\t\tlimit = {",
            f"\t\t\t\thas_global_variable_map = eu5ab_q_market_committed_{good}",
            f"\t\t\t\tis_key_in_global_variable_map = {{ name = eu5ab_q_market_committed_{good} target = scope:eu5ab_material_market }}",
            "\t\t\t}",
            f'\t\t\tchange_local_variable = {{ name = eu5ab_new_committed_{good} add = "global_variable_map(eu5ab_q_market_committed_{good}|scope:eu5ab_material_market)" }}',
            f"\t\t\tremove_from_global_variable_map = {{ name = eu5ab_q_market_committed_{good} key = scope:eu5ab_material_market }}",
            "\t\t}",
            f"\t\tadd_to_global_variable_map = {{ name = eu5ab_q_market_committed_{good} key = scope:eu5ab_material_market value = local_var:eu5ab_new_committed_{good} }}",
            "\t}",
        ])
    chunks.extend(["}", ""])
    chunks.extend([
        "# Roll back only the rejected approval, preserving other planned projects.",
        "eu5ab_release_candidate_construction_demand = {",
        "\tvar:eu5ab_q_material_market = { save_temporary_scope_as = eu5ab_material_market }",
    ])
    for good in goods:
        chunks.extend([
            "\tif = {",
            "\t\tlimit = {",
            f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_construction_demand_{good} > 0",
            f"\t\t\tis_key_in_global_variable_map = {{ name = eu5ab_q_market_committed_{good} target = scope:eu5ab_material_market }}",
            "\t\t}",
            f'\t\tset_local_variable = {{ name = eu5ab_remaining_committed_{good} value = {{ value = "global_variable_map(eu5ab_q_market_committed_{good}|scope:eu5ab_material_market)" subtract = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_construction_demand_{good} min = 0 }} }}',
            f"\t\tremove_from_global_variable_map = {{ name = eu5ab_q_market_committed_{good} key = scope:eu5ab_material_market }}",
            f"\t\tadd_to_global_variable_map = {{ name = eu5ab_q_market_committed_{good} key = scope:eu5ab_material_market value = local_var:eu5ab_remaining_committed_{good} }}",
            "\t}",
        ])
    chunks.extend(["}", ""])
    return "\n".join(chunks)


def render_engine_queue_effects(
    policies: list[Policy],
    rules: AutomationRules,
) -> str:
    """Script-side staging, reservation, confirmation, and teardown effects."""
    phase_count = len(CANDIDATE_PRIORITY_FEATURES) * 4

    def copy_country_diagnostic_slot(source: int, target: int, indent: str) -> list[str]:
        lines: list[str] = []
        for suffix in ("location", *WORKER_TOP_FIELD_SUFFIXES):
            source_variable = f"eu5ab_diag_top_{source}_{suffix}"
            target_variable = f"eu5ab_diag_top_{target}_{suffix}"
            lines.extend([
                f"{indent}if = {{",
                f"{indent}\tlimit = {{ has_variable = {source_variable} }}",
                f"{indent}\tset_variable = {{ name = {target_variable} value = var:{source_variable} }}",
                f"{indent}}}",
                f"{indent}else = {{ remove_variable = {target_variable} }}",
            ])
        return lines

    def copy_worker_diagnostic_candidate(target: int, indent: str) -> list[str]:
        lines = [
            f"{indent}set_variable = {{ name = eu5ab_diag_top_{target}_location value = scope:{CANDIDATE_LOCATION_SCOPE} }}",
            f"{indent}remove_variable = eu5ab_diag_top_{target}_economic",
            f"{indent}remove_variable = eu5ab_diag_top_{target}_building",
        ]
        # Workers publish RGO diagnostics only. Ordinary building identity and
        # economics come from batch_publish_diagnostics after native quotes.
        for suffix in (field for field in WORKER_TOP_FIELD_SUFFIXES if field not in {"economic", "building"}):
            source_variable = f"eu5ab_worker_top_1_{suffix}"
            target_variable = f"eu5ab_diag_top_{target}_{suffix}"
            lines.extend([
                f"{indent}if = {{",
                f"{indent}\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_variable = {source_variable} }} }}",
                f"{indent}\tset_variable = {{ name = {target_variable} value = scope:{CANDIDATE_LOCATION_SCOPE}.var:{source_variable} }}",
                f"{indent}}}",
                f"{indent}else = {{ remove_variable = {target_variable} }}",
            ])
        return lines

    def worker_candidate_beats_slot(slot: int, indent: str) -> list[str]:
        candidate_priority = (
            f"scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_worker_top_1_priority"
        )
        candidate_score = f"scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_worker_top_1_score"
        slot_priority = f"var:eu5ab_diag_top_{slot}_priority"
        slot_score = f"var:eu5ab_diag_top_{slot}_score"
        return [
            f"{indent}OR = {{",
            f"{indent}\t{slot_priority} > {{ value = {candidate_priority} }}",
            f"{indent}\tAND = {{",
            f"{indent}\t\tNOT = {{ {slot_priority} > {{ value = {candidate_priority} }} }}",
            f"{indent}\t\tNOT = {{ {slot_priority} < {{ value = {candidate_priority} }} }}",
            f"{indent}\t\t{slot_score} < {{ value = {candidate_score} }}",
            f"{indent}\t}}",
            f"{indent}}}",
        ]

    def merge_worker_diagnostic_candidate() -> list[str]:
        lines = [
            "\t\tif = {",
            "\t\t\tlimit = { has_variable = eu5ab_worker_top_1_kind has_variable = eu5ab_worker_top_1_priority }",
            "\t\t\tscope:eu5ab_worker_merge_country = {",
        ]
        for slot in range(1, rules.cadence.candidates_per_location + 1):
            keyword = "if" if slot == 1 else "else_if"
            lines.extend([
                f"\t\t\t\t{keyword} = {{",
                "\t\t\t\t\tlimit = {",
                *worker_candidate_beats_slot(slot, "\t\t\t\t\t\t"),
                "\t\t\t\t\t}",
            ])
            for source in range(rules.cadence.candidates_per_location - 1, slot - 1, -1):
                lines.extend(
                    copy_country_diagnostic_slot(source, source + 1, "\t\t\t\t\t")
                )
            lines.extend(copy_worker_diagnostic_candidate(slot, "\t\t\t\t\t"))
            lines.append("\t\t\t\t}")
        lines.extend([
            "\t\t\t}",
            "\t\t}",
        ])
        return lines

    def _candidate_phase_route_lines(indent: str, *, worker: bool, offset: int) -> list[str]:
        lines: list[str] = []
        for emergency, phase_offset in ((True, 0), (False, len(CANDIDATE_PRIORITY_FEATURES))):
            if emergency:
                lines.extend([
                    f"{indent}if = {{",
                    f"{indent}\tlimit = {{ eu5ab_engine_candidate_is_food_emergency = yes }}",
                ])
            else:
                lines.append(f"{indent}else = {{")
            for rank in range(1, len(CANDIDATE_PRIORITY_FEATURES) + 1):
                phase = rank + phase_offset + offset
                phase_list = (
                    f"eu5ab_worker_phase_{phase}_types" if worker
                    else f"eu5ab_q_phase_{phase}_types"
                )
                phase_indent = indent + "\t"
                lines.extend([
                    f"{phase_indent}{'if' if rank == 1 else 'else_if'} = {{",
                    f"{phase_indent}\tlimit = {{ var:eu5ab_stage_candidate_priority = {rank} }}",
                    f"{phase_indent}\tif = {{",
                    f"{phase_indent}\t\tlimit = {{ NOT = {{ is_target_in_variable_list = {{ name = {phase_list} target = scope:{CANDIDATE_BUILDING_SCOPE} }} }} }}",
                    f"{phase_indent}\t\tadd_to_variable_list = {{ name = {phase_list} target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
                    f"{phase_indent}\t\tif = {{ limit = {{ NOT = {{ is_key_in_variable_map = {{ name = eu5ab_batch_labor_factor target = scope:{CANDIDATE_BUILDING_SCOPE} }} }} }} add_to_variable_map = {{ name = eu5ab_batch_labor_factor key = scope:{CANDIDATE_BUILDING_SCOPE} value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_candidate_current_labor_factor }} }}",
                    # Native economic data arrives after worker reduction. No
                    # estimated score is allowed to truncate this phase pool.
                    f"{phase_indent}\t\tset_variable = {{ name = eu5ab_capacity_phase_{phase}_order value = 0 }}",
                    f"{phase_indent}\t\tset_variable = eu5ab_capacity_phase_{phase}_order_ready",
                ])
                if worker:
                    lines.extend([
                        f"{phase_indent}\t\tchange_variable = {{ name = eu5ab_worker_staged add = 1 }}",
                    ])
                else:
                    lines.extend([
                        f"{phase_indent}\t\tscope:eu5ab_q_stage_country = {{",
                        f"{phase_indent}\t\t\tif = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_phase_{phase}_unsorted_locations target = scope:eu5ab_q_stage_location }} }} }} add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_unsorted_locations target = scope:eu5ab_q_stage_location }} }}",
                        f"{phase_indent}\t\t\tchange_variable = {{ name = eu5ab_q_phase_{phase}_staged add = 1 }}",
                        f"{phase_indent}\t\t\tchange_variable = {{ name = eu5ab_q_staged add = 1 }}",
                        f"{phase_indent}\t\t\tchange_variable = {{ name = eu5ab_diag_staged_candidates add = 1 }}",
                        f"{phase_indent}\t\t}}",
                    ])
                lines.extend([
                    f"{phase_indent}\t\tset_variable = eu5ab_location_candidate_staged",
                    *([f"{phase_indent}\t\tset_variable = eu5ab_ordinary_candidate_staged"] if offset == 0 else []),
                    f"{phase_indent}\t}}",
                    f"{phase_indent}}}",
                ])
            lines.append(f"{indent}}}")
        return lines

    def candidate_phase_route_lines(indent: str, *, worker: bool) -> list[str]:
        # The supplemental pool runs only after all ordinary phases finish.
        return [f"{indent}if = {{",
                f"{indent}\tlimit = {{ has_variable = eu5ab_collecting_supplemental }}",
                *_candidate_phase_route_lines(indent + "\t", worker=worker, offset=8),
                f"{indent}}}", f"{indent}else = {{",
                *_candidate_phase_route_lines(indent + "\t", worker=worker, offset=0),
                f"{indent}}}"]

    def rgo_phase_route_lines(indent: str) -> list[str]:
        lines: list[str] = []
        for emergency, phase_offset in ((True, 0), (False, len(CANDIDATE_PRIORITY_FEATURES))):
            emergency_trigger = (
                "eu5ab_rgo_food_emergency_enabled = yes"
                if emergency
                else "NOT = { eu5ab_rgo_food_emergency_enabled = yes }"
            )
            for rank in range(1, len(CANDIDATE_PRIORITY_FEATURES) + 1):
                phase = rank + phase_offset
                lines.extend([
                    f"{indent}if = {{",
                    f"{indent}\tlimit = {{ owner.var:eu5ab_candidate_priority_rgo = {rank} {emergency_trigger} }}",
                    f"{indent}\towner = {{",
                    f"{indent}\t\tif = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_phase_{phase}_rgo_unsorted_locations target = scope:eu5ab_q_stage_location }} }} }} add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_rgo_unsorted_locations target = scope:eu5ab_q_stage_location }} change_variable = {{ name = eu5ab_q_phase_{phase}_rgo_staged add = 1 }} change_variable = {{ name = eu5ab_q_rgo_staged add = 1 }} }}" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
                    f"{indent}\t}}",
                    f"{indent}}}",
                ])
        return lines

    def worker_rgo_phase_route_lines(indent: str) -> list[str]:
        lines: list[str] = []
        for emergency, phase_offset in ((True, 0), (False, len(CANDIDATE_PRIORITY_FEATURES))):
            emergency_trigger = (
                "eu5ab_rgo_food_emergency_enabled = yes"
                if emergency
                else "NOT = { eu5ab_rgo_food_emergency_enabled = yes }"
            )
            for rank in range(1, len(CANDIDATE_PRIORITY_FEATURES) + 1):
                phase = rank + phase_offset
                lines.extend([
                    f"{indent}if = {{",
                    f"{indent}\tlimit = {{ owner.var:eu5ab_candidate_priority_rgo = {rank} {emergency_trigger} }}",
                    f"{indent}\tset_variable = {{ name = eu5ab_worker_phase_{phase}_rgo value = 1 }}",
                    f"{indent}}}",
                ])
        return lines

    chunks = [
        "# Asynchronous engine-value bridge queue.",
        "# Location-only teardown, shared by queue cancellation and completion.",
        "# Safe to repeat when a location belongs to multiple phases or indexes.",
        "eu5ab_clear_location_candidate_state = {",
        "\teu5ab_clear_worker_screening = yes",
        "\tremove_variable = eu5ab_worker_data_wait remove_variable = eu5ab_worker_data_ready",
        "\teu5ab_clear_building_capacity = yes",
        "\teu5ab_clear_native_recipes = yes",
        "\tclear_variable_list = eu5ab_active_recipe_catalog_view",
        "\tremove_variable = eu5ab_active_recipe_catalog_ready",
        "\tremove_variable = eu5ab_active_recipe_catalog_country",
        "\tremove_variable = eu5ab_active_recipe_catalog_month",
        "\tremove_variable = eu5ab_active_recipe_catalog_year",
        "\teu5ab_clear_parallel_capacity = yes",
        f"\t{production_forecast.clear_candidate_reference()}",
        "\tremove_variable = eu5ab_pending_approval_market",
        "\tremove_variable = eu5ab_pending_approval_country",
        "\tremove_variable = eu5ab_collecting_supplemental",
        "\tremove_variable = eu5ab_capacity_requested",
        "\tremove_variable = eu5ab_capacity_worker_country",
        "\tclear_variable_list = eu5ab_capacity_tickets",
        "\tremove_variable = eu5ab_capacity_request remove_variable = eu5ab_capacity_received remove_variable = eu5ab_capacity_reason",
        *building_capacity.clear_phase_lines(phase_count),
        *(f"\tclear_variable_list = eu5ab_q_phase_{phase}_types" for phase in range(1, phase_count + 1)),
        *(f"\tclear_variable_list = eu5ab_q_{name}" for name in (
            "done_types", "approved_types", "seen_types",
            "confirmed_types", "failed_types", "profit_best_types", "waiting_types",
        )),
        *(f"\tremove_variable = eu5ab_q_{name}" for name in (
            "profit_best_actual", "profit_best_rank", "profit_done", "location_approved",
            "queue_before", "approved_cost", "approved_income", "approved_profit",
            "approved_build_kind", "approved_emergency_override", "material_market", "done_rgo", "waiting_rgo", "dependency_wait",
            "profit_candidate_priority", "profit_candidate_magnitude", "profit_candidate_rank",
            "fire_requested", "fire_issued", "type_queue_before", "type_level_before",
        )),
        "\tremove_variable = eu5ab_location_candidate_staged",
        "\tremove_variable = eu5ab_ordinary_candidate_staged",
        "\tremove_variable = eu5ab_action_taken",
        "\tremove_variable = eu5ab_cached_location_need_score",
        "\tremove_variable = eu5ab_cached_rgo_queue_score",
        "\tremove_variable = eu5ab_q_rgo_attempted",
        "}",
        "",
        "eu5ab_clear_engine_candidate_queue = {",
        "\tsave_scope_as = eu5ab_q_clear_country",
        "\teu5ab_apply_queue_cooldowns = yes",
        *(
            line
            for phase in range(1, phase_count + 1)
            for line in (
                *(f"\tevery_in_list = {{ variable = eu5ab_q_phase_{phase}_{suffix} limit = {{ OR = {{ owner = scope:eu5ab_q_clear_country var:eu5ab_pending_approval_country = scope:eu5ab_q_clear_country var:eu5ab_capacity_worker_country = scope:eu5ab_q_clear_country }} }} eu5ab_clear_location_candidate_state = yes }}"
                  for suffix in ("unsorted_locations", "locations", "rgo_unsorted_locations", "rgo_locations") if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 or not suffix.startswith("rgo_")),
                f"\tclear_variable_list = eu5ab_q_phase_{phase}_locations",
                f"\tclear_variable_list = eu5ab_q_phase_{phase}_unsorted_locations",
                f"\tclear_variable_list = eu5ab_q_phase_{phase}_rgo_locations" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
                f"\tclear_variable_list = eu5ab_q_phase_{phase}_rgo_unsorted_locations" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
                f"\tremove_variable = eu5ab_q_phase_{phase}_staged",
                f"\tremove_variable = eu5ab_q_phase_{phase}_rgo_staged" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
            )
        ),
        "\t# Include auxiliary indexes before discarding their references.",
        *(line for suffix in (
            "approved_locations", "profit_locations",
        ) for line in (
            f"\tevery_in_list = {{ variable = eu5ab_q_{suffix} limit = {{ OR = {{ owner = scope:eu5ab_q_clear_country var:eu5ab_pending_approval_country = scope:eu5ab_q_clear_country var:eu5ab_capacity_worker_country = scope:eu5ab_q_clear_country }} }} eu5ab_clear_location_candidate_state = yes }}",
            f"\tclear_variable_list = eu5ab_q_{suffix}",
        )),
        "\tremove_variable = eu5ab_q_profit_selecting",
        "\tremove_variable = eu5ab_q_retry_phase",
        "\tremove_variable = eu5ab_q_rank_refreshed",
        "\tremove_variable = eu5ab_q_waiting_data",
        "\tremove_variable = eu5ab_q_data_day",
        "\tremove_variable = eu5ab_q_watchdog_last_phase",
        "\tremove_variable = eu5ab_q_watchdog_last_processed",
        "\tremove_variable = eu5ab_q_watchdog_last_seen",
        "\tremove_variable = eu5ab_q_watchdog_last_confirmed",
        "\tremove_variable = eu5ab_q_watchdog_stall_checks",
        "\t# Legacy callback-heartbeat fields from the first watchdog version.",
        "}",
        "",
        "eu5ab_prepare_engine_candidate_queue = {",
        "\tif = {",
        "\t\tlimit = { exists = var:eu5ab_q_active }",
        "\t\tchange_variable = { name = eu5ab_diag_queue_recoveries add = 1 }",
        "\t\teu5ab_clear_engine_candidate_queue = yes",
        "\t}",
        "\tif = { limit = { NOT = { has_variable = eu5ab_scan_refill_active } } eu5ab_reset_committed_construction_demand = yes }",
        "\tset_variable = { name = eu5ab_q_staged value = 0 }",
        "\tset_variable = { name = eu5ab_q_rgo_staged value = 0 }",
        *(f"\tset_variable = {{ name = eu5ab_q_phase_{phase}_staged value = 0 }}" for phase in range(1, phase_count + 1)),
        *(f"\tset_variable = {{ name = eu5ab_q_phase_{phase}_rgo_staged value = 0 }}" for phase in range(1, len(CANDIDATE_PRIORITY_FEATURES) * 2 + 1)),
        "\tset_variable = { name = eu5ab_q_processed value = 0 }",
        "\tset_variable = { name = eu5ab_q_approved value = 0 }",
        "\tset_variable = { name = eu5ab_q_seen value = 0 }",
        "\tset_variable = { name = eu5ab_q_confirmed value = 0 }",
        "\tset_variable = { name = eu5ab_q_progress_last value = 0 }",
        "\tset_variable = { name = eu5ab_q_stall_rounds value = 0 }",
        "\tset_variable = { name = eu5ab_q_confirm_stall_rounds value = 0 }",
        "\tset_variable = { name = eu5ab_q_planned_spend value = 0 }",
        "\tset_variable = { name = eu5ab_q_planned_budget value = 0 }",
        "\tremove_variable = eu5ab_q_active",
        "\tremove_variable = eu5ab_q_fire",
        "\tremove_variable = eu5ab_q_phase",
        "\tremove_variable = eu5ab_q_expected",
        "\tset_variable = { name = eu5ab_diag_queue_state value = 1 }",
        "}",
        "",
        "# Snapshot only meaningful queue progress. GUI callbacks may still fire while",
        "# processing is stuck, so animation activity alone is not a liveness signal.",
        "eu5ab_reset_engine_candidate_watchdog_progress = {",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\thas_variable = eu5ab_q_active",
        "\t\t\thas_variable = eu5ab_q_phase",
        "\t\t\thas_variable = eu5ab_q_processed",
        "\t\t\thas_variable = eu5ab_q_seen",
        "\t\t\thas_variable = eu5ab_q_confirmed",
        "\t\t}",
        "\t\tset_variable = { name = eu5ab_q_watchdog_last_phase value = var:eu5ab_q_phase }",
        "\t\tset_variable = { name = eu5ab_q_watchdog_last_processed value = var:eu5ab_q_processed }",
        "\t\tset_variable = { name = eu5ab_q_watchdog_last_seen value = var:eu5ab_q_seen }",
        "\t\tset_variable = { name = eu5ab_q_watchdog_last_confirmed value = var:eu5ab_q_confirmed }",
        "\t\tset_variable = { name = eu5ab_q_watchdog_stall_checks value = 0 }",
        "\t}",
        "}",
        "",
        "# Parallel worker lifecycle. These effects only mutate the root location.",
        "eu5ab_clear_location_worker_state = {",
        "\teu5ab_clear_worker_screening = yes",
        "\tremove_variable = eu5ab_worker_data_wait remove_variable = eu5ab_worker_data_ready",
        *(f"\tremove_variable = eu5ab_worker_rgo_pending_{field}" for field in rgo_pending.DIAGNOSTIC_FIELDS),
        *building_capacity.clear_phase_lines(phase_count),
        "\teu5ab_clear_backfill_worker_state = yes",
        *(f"\tclear_variable_list = eu5ab_worker_phase_{phase}_types" for phase in range(1, phase_count + 1)),
        *(f"\tclear_variable_list = {pool}" for pool in (*CURRENT_CANDIDATE_POOLS, *CURRENT_INPUT_CANDIDATE_POOLS)),
        *(f"\tremove_variable = eu5ab_worker_phase_{phase}_rgo" for phase in range(1, len(CANDIDATE_PRIORITY_FEATURES) * 2 + 1)),
        "\tremove_variable = eu5ab_worker_active",
        "\tremove_variable = eu5ab_worker_complete",
        "\tremove_variable = eu5ab_worker_staged",
        "\tremove_variable = eu5ab_pending_failure_cooldown",
        "\tremove_variable = eu5ab_had_capacity_blocked_candidate",
        f"\tclear_variable_map = {candidate_backfill.SCORE_CACHE}",
        "\tremove_variable = eu5ab_location_candidate_staged",
        "\tremove_variable = eu5ab_ordinary_candidate_staged",
        "\tremove_variable = eu5ab_cached_rgo_queue_score",
        "\tremove_variable = eu5ab_q_rgo_attempted",
        *(f"\tremove_variable = eu5ab_worker_{counter}" for counter in WORKER_DIAGNOSTIC_COUNTERS),
        *(
            f"\tremove_variable = eu5ab_worker_top_{rank}_{suffix}"
            for rank in (1,)
            for suffix in WORKER_TOP_FIELD_SUFFIXES if suffix not in {"economic", "building"}
        ),
        "}",
        "",
        "eu5ab_run_location_worker = {",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_backfill_dispatch_country exists = var:eu5ab_backfill_dispatch_country }",
        "\t\tvar:eu5ab_backfill_dispatch_country = { save_scope_as = eu5ab_backfill_dispatch_country }",
        "\t\teu5ab_clear_location_worker_state = yes",
        "\t\teu5ab_initialize_candidate_backfill = yes",
        "\t}",
        "\telse = { eu5ab_clear_location_worker_state = yes }",
        "\tset_variable = eu5ab_worker_active",
        "\tset_variable = { name = eu5ab_worker_staged value = 0 }",
        *(f"\tset_variable = {{ name = eu5ab_worker_{counter} value = 0 }}" for counter in WORKER_DIAGNOSTIC_COUNTERS),
        "\teu5ab_try_construct_policy_candidate = yes",
        "\teu5ab_clear_worker_screening = yes",
        "\teu5ab_clear_backfill_scratch = yes",
        "\tremove_variable = eu5ab_worker_active",
        "\tset_variable = eu5ab_worker_complete",
        "}",
        "",
        "# Country-only reducer. It preserves insertion order and consumes only",
        "# completed GUI/worker results; pending captures survive an early merge.",
        "eu5ab_merge_location_worker_results = {",
        "\tsave_scope_as = eu5ab_worker_merge_country",
        "\tevery_in_list = {",
        "\t\tvariable = eu5ab_worker_pending_locations",
        "\t\tlimit = { owner = scope:eu5ab_worker_merge_country has_variable = eu5ab_worker_complete }",
        f"\t\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
        "\t\t# Count once per completed worker, not once per candidate or phase.",
        "\t\tif = { limit = { has_variable = eu5ab_capacity_reason } scope:eu5ab_worker_merge_country = {",
        "\t\t\tset_variable = { name = eu5ab_diag_capacity_unavailable value = { value = 0 if = { limit = { has_variable = eu5ab_diag_capacity_unavailable } add = var:eu5ab_diag_capacity_unavailable } add = 1 } }",
        "\t\t\tset_variable = { name = eu5ab_diag_capacity_last_reason value = prev.var:eu5ab_capacity_reason } } }",
        "\t\tif = {",
        "\t\t\tlimit = { OR = {",
        "\t\t\t\tvar:eu5ab_worker_staged > 0",
        *(f"\t\t\t\thas_variable = eu5ab_worker_phase_{phase}_rgo" for phase in range(1, len(CANDIDATE_PRIORITY_FEATURES) * 2 + 1)),
        "\t\t\t}",
        "\t\t\tOR = { NOT = { has_variable = eu5ab_worker_data_wait } has_variable = eu5ab_worker_data_ready }",
        "\t\t\t}",
        "\t\t\tscope:eu5ab_worker_merge_country = { eu5ab_record_scan_candidate_location = yes }",
        "\t\t}",
        *(
            line
            for phase in range(1, phase_count + 1)
            for line in (
                "\t\tevery_in_list = {",
                f"\t\t\tvariable = eu5ab_worker_phase_{phase}_types",
                f"\t\t\tsave_scope_as = {CANDIDATE_BUILDING_SCOPE}",
                f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
                f"\t\t\t\tif = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_phase_{phase}_types target = scope:{CANDIDATE_BUILDING_SCOPE} }} }} }} add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_types target = scope:{CANDIDATE_BUILDING_SCOPE} }} scope:eu5ab_worker_merge_country = {{ if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_phase_{phase}_unsorted_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }} }} add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_unsorted_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }} change_variable = {{ name = eu5ab_q_phase_{phase}_staged add = 1 }} change_variable = {{ name = eu5ab_q_staged add = 1 }} change_variable = {{ name = eu5ab_diag_staged_candidates add = 1 }} }} }}",
                "\t\t\t}",
                "\t\t}",
                (f"\t\tif = {{ limit = {{ has_variable = eu5ab_worker_phase_{phase}_rgo }} scope:eu5ab_worker_merge_country = {{ if = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_phase_{phase}_rgo_unsorted_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }} }} add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_rgo_unsorted_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} change_variable = {{ name = eu5ab_q_phase_{phase}_rgo_staged add = 1 }} change_variable = {{ name = eu5ab_q_rgo_staged add = 1 }} }} }} }}" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else ""),
            )
        ),
        *(
            # Resumed workers can arrive before this country's monthly reset.
            # Native change_variable rejects an absent target (Type: empty).
            # Publish the worker's real count first; preserve existing totals.
            f"\t\tif = {{ limit = {{ has_variable = eu5ab_worker_{counter} }} scope:eu5ab_worker_merge_country = {{ if = {{ limit = {{ has_variable = {counter} }} change_variable = {{ name = {counter} add = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_worker_{counter} }} }} else = {{ set_variable = {{ name = {counter} value = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_worker_{counter} }} }} }} }}"
            for counter in WORKER_DIAGNOSTIC_COUNTERS
        ),
        *merge_worker_diagnostic_candidate(),
        *rgo_pending.merge_diagnostics_lines(),
        *(f"\t\tremove_variable = eu5ab_worker_rgo_pending_{field}" for field in rgo_pending.DIAGNOSTIC_FIELDS),
        *candidate_backfill.merge_lines(),
        *(f"\t\tclear_variable_list = eu5ab_worker_phase_{phase}_types" for phase in range(1, phase_count + 1)),
        *(f"\t\tremove_variable = eu5ab_worker_phase_{phase}_rgo" for phase in range(1, len(CANDIDATE_PRIORITY_FEATURES) * 2 + 1)),
        *(f"\t\tremove_variable = eu5ab_worker_{counter}" for counter in WORKER_DIAGNOSTIC_COUNTERS),
        *(
            f"\t\tremove_variable = eu5ab_worker_top_{rank}_{suffix}"
            for rank in (1,)
            for suffix in WORKER_TOP_FIELD_SUFFIXES if suffix not in {"economic", "building"}
        ),
        "\t\tremove_variable = eu5ab_worker_complete",
        "\t\tremove_variable = eu5ab_worker_staged",
        "\t\tremove_variable = eu5ab_worker_data_wait remove_variable = eu5ab_worker_data_ready",
        "\t\tif = { limit = { NOT = { has_variable = eu5ab_location_candidate_staged } NOT = { has_variable = eu5ab_cached_rgo_queue_score } } remove_variable = eu5ab_cached_location_need_score }",
        f"\t\tscope:eu5ab_worker_merge_country = {{ remove_list_variable = {{ name = eu5ab_worker_pending_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }}",
        "\t}",
        "\t# Preserve requests awaiting the GUI; discard locations whose owner changed.",
        "\tevery_in_list = {",
        "\t\tvariable = eu5ab_worker_pending_locations",
        "\t\tlimit = { NOT = { owner = scope:eu5ab_worker_merge_country } }",
        f"\t\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
        "\t\tif = { limit = { OR = { var:eu5ab_capacity_worker_country = scope:eu5ab_worker_merge_country var:eu5ab_backfill_dispatch_country = scope:eu5ab_worker_merge_country var:eu5ab_pending_approval_country = scope:eu5ab_worker_merge_country } }",
        "\t\t\teu5ab_clear_location_worker_state = yes eu5ab_clear_location_candidate_state = yes",
        "\t\t}",
        f"\t\tscope:eu5ab_worker_merge_country = {{ remove_list_variable = {{ name = eu5ab_worker_pending_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }}",
        "\t}",
        "}",
        "",
        "# Root is the candidate location; the ordered iterator saved the building type.",
        "eu5ab_stage_engine_candidate = {",
        f"\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ save_scope_as = eu5ab_q_stage_location }}",
        "\towner = { save_scope_as = eu5ab_q_stage_country save_scope_as = eu5ab_engine_country }",
        "\tif = { limit = { scope:eu5ab_candidate_building = { NOT = { eu5ab_candidate_pending_data_ready = yes } } } set_variable = eu5ab_worker_data_wait }",
        "\telse = { set_variable = eu5ab_worker_data_ready }",
        "\t# Pool visitors provide the class priority once; standalone callers classify once here.",
        "\tif = {",
        "\t\tlimit = { NOT = { has_variable = eu5ab_stage_candidate_priority } }",
        "\t\tset_variable = { name = eu5ab_stage_candidate_priority value = 0 }",
        "\t\tset_variable = eu5ab_stage_priority_computed",
        "\t\tif = {",
        f"\t\t\tlimit = {{ scope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_is_upgrade = yes }} }}",
        "\t\t\tset_variable = { name = eu5ab_stage_candidate_priority value = owner.var:eu5ab_candidate_priority_upgrade }",
        "\t\t}",
        "\t\telse_if = {",
        f"\t\t\tlimit = {{ scope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_has_existing_building = yes }} }}",
        "\t\t\tset_variable = { name = eu5ab_stage_candidate_priority value = owner.var:eu5ab_candidate_priority_expand }",
        "\t\t}",
        "\t\telse_if = {",
        f"\t\t\tlimit = {{ scope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_lacks_existing_building = yes }} }}",
        "\t\t\tset_variable = { name = eu5ab_stage_candidate_priority value = owner.var:eu5ab_candidate_priority_new }",
        "\t\t}",
        "\t}",
        "\tif = {",
        "\t\tlimit = { scope:eu5ab_candidate_building = { eu5ab_candidate_has_capacity = yes } has_variable = eu5ab_worker_active }",
        *candidate_phase_route_lines("\t\t", worker=True),
        "\t}",
        "\telse_if = {",
        "\t\tlimit = { scope:eu5ab_candidate_building = { eu5ab_candidate_has_capacity = yes } NOT = { has_variable = eu5ab_worker_active } }",
        *candidate_phase_route_lines("\t\t", worker=False),
        "\t}",
        "\tif = { limit = { has_variable = eu5ab_stage_priority_computed } remove_variable = eu5ab_stage_candidate_priority remove_variable = eu5ab_stage_priority_computed }",
        "}",
        "",
        "eu5ab_sort_candidate_queue = {",
        "\tsave_scope_as = eu5ab_q_sort_country",
        *(
            line
            for phase in range(1, phase_count + 1)
            for line in (
                f"\tclear_variable_list = eu5ab_q_phase_{phase}_locations",
                "\tordered_in_list = {",
                f"\t\tvariable = eu5ab_q_phase_{phase}_unsorted_locations",
                f"\t\torder_by = eu5ab_capacity_phase_{phase}_order_value",
                f"\t\tmax = {rules.cadence.deep_score_location_limit}",
                "\t\tcheck_range_bounds = no",
                "\t\tsave_scope_as = eu5ab_q_sorted_location",
                f"\t\tscope:eu5ab_q_sort_country = {{ add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_locations target = scope:eu5ab_q_sorted_location }} }}",
                "\t}",
                "\t# Retain all staged locations until teardown, including any outside the sort limit.",
            )
        ),
        "}",
        "",
        "# RGO actions are staged too, so the hidden bridge can execute them at their",
        "# exact user-selected position between ordinary candidate classes.",
        "eu5ab_stage_rgo_candidate = {",
        f"\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ save_scope_as = eu5ab_q_stage_location }}",
        "\tif = { limit = { NOT = { eu5ab_rgo_food_emergency_enabled = yes } NOT = { eu5ab_rgo_pending_data_available = yes } } set_variable = eu5ab_worker_data_wait }",
        "\telse = { set_variable = eu5ab_worker_data_ready }",
        "\tset_variable = { name = eu5ab_cached_rgo_queue_score value = eu5ab_rgo_queue_order_score }",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_worker_active }",
        *worker_rgo_phase_route_lines("\t\t"),
        "\t}",
        "\telse = {",
        *rgo_phase_route_lines("\t\t"),
        "\t}",
        "}",
        "",
        "eu5ab_sort_rgo_candidate_queue = {",
        "\tsave_scope_as = eu5ab_q_sort_country",
        *(
            line
            for phase in range(1, len(CANDIDATE_PRIORITY_FEATURES) * 2 + 1)
            for line in (
                f"\tclear_variable_list = eu5ab_q_phase_{phase}_rgo_locations" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
                "\tordered_in_list = {",
                f"\t\tvariable = eu5ab_q_phase_{phase}_rgo_unsorted_locations" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
                "\t\torder_by = var:eu5ab_cached_rgo_queue_score",
                f"\t\tmax = {rules.cadence.deep_score_location_limit}",
                "\t\tcheck_range_bounds = no",
                "\t\tsave_scope_as = eu5ab_q_sorted_rgo_location",
                f"\t\tscope:eu5ab_q_sort_country = {{ add_to_variable_list = {{ name = eu5ab_q_phase_{phase}_rgo_locations target = scope:eu5ab_q_sorted_rgo_location }} }}" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
                "\t}",
                "\t# Retain all staged RGO locations until teardown, including any outside the sort limit.",
            )
        ),
        "}",
        "",
        "eu5ab_start_engine_candidate_queue = {",
        "\teu5ab_sort_candidate_queue = yes",
        "\teu5ab_sort_rgo_candidate_queue = yes",
        "\tif = {",
        "\t\tlimit = { OR = { var:eu5ab_q_staged > 0 var:eu5ab_q_rgo_staged > 0 } }",
        "\t\tset_variable = { name = eu5ab_q_active value = 1 }",
        "\t\tset_variable = { name = eu5ab_q_phase value = 1 }",
        "\t\tset_variable = { name = eu5ab_diag_queue_state value = 2 }",
        "\t\t# A refill is another batch in the same round; retain earlier starts.",
        "\t\tset_variable = { name = eu5ab_diag_built_this_run value = 2 }",
        "\t\tif = { limit = { has_variable = eu5ab_constructions_started_this_tick } if = { limit = { var:eu5ab_constructions_started_this_tick > 0 } set_variable = { name = eu5ab_diag_built_this_run value = 1 } } }",
        "\t\teu5ab_reset_engine_candidate_watchdog_progress = yes",
        f"\t\ttrigger_event_silently = {{ id = eu5ab_queue_watchdog.1 days = {ENGINE_QUEUE_WATCHDOG_INTERVAL_DAYS} }}",
        "\t\teu5ab_prepare_engine_priority_phase = yes",
        "\t}",
        "\telse = { eu5ab_finish_engine_candidate_queue = yes }",
        "}",
        "",
        "eu5ab_reset_engine_priority_phase_progress = {",
        "\tremove_variable = eu5ab_q_waiting_data",
        *(f"\tif = {{ limit = {{ var:eu5ab_q_phase = {phase} }} every_in_list = {{ variable = eu5ab_q_phase_{phase}_rgo_locations remove_variable = eu5ab_q_waiting_rgo }} }}" for phase in range(1, len(CANDIDATE_PRIORITY_FEATURES) * 2 + 1)),
        "\tset_variable = { name = eu5ab_q_data_day value = eu5ab_pl_today }",
        "\tremove_variable = eu5ab_q_rank_refreshed",
        *(
            line
            for phase in range(1, phase_count + 1)
            for line in (
                f"\tif = {{ limit = {{ var:eu5ab_q_phase = {phase} }} every_in_list = {{ variable = eu5ab_q_phase_{phase}_locations clear_variable_list = eu5ab_q_done_types clear_variable_list = eu5ab_q_waiting_types remove_variable = eu5ab_q_dependency_wait clear_variable_list = eu5ab_q_approved_types clear_variable_list = eu5ab_q_seen_types clear_variable_list = eu5ab_q_confirmed_types clear_variable_list = eu5ab_q_profit_best_types remove_variable = eu5ab_q_profit_best_actual remove_variable = eu5ab_q_profit_best_rank remove_variable = eu5ab_q_profit_done remove_variable = eu5ab_q_location_approved remove_variable = eu5ab_q_queue_before remove_variable = eu5ab_q_approved_cost remove_variable = eu5ab_q_approved_income remove_variable = eu5ab_q_approved_profit remove_variable = eu5ab_q_approved_build_kind remove_variable = eu5ab_q_approved_emergency_override remove_variable = eu5ab_q_material_market remove_variable = eu5ab_q_fire_requested {production_forecast.clear_candidate_reference()} remove_variable = eu5ab_pending_approval_market remove_variable = eu5ab_pending_approval_country remove_variable = eu5ab_q_fire_issued remove_variable = eu5ab_q_type_queue_before remove_variable = eu5ab_q_type_level_before }} }}",
                f"\tif = {{ limit = {{ var:eu5ab_q_phase = {phase} }} every_in_list = {{ variable = eu5ab_q_phase_{phase}_rgo_locations remove_variable = eu5ab_q_done_rgo }} }}" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
            )
        ),
        "\tclear_variable_list = eu5ab_q_approved_locations",
        "\tclear_variable_list = eu5ab_q_profit_locations",
        "\tset_variable = { name = eu5ab_q_processed value = 0 }",
        "\tset_variable = { name = eu5ab_q_approved value = 0 }",
        "\tset_variable = { name = eu5ab_q_seen value = 0 }",
        "\tset_variable = { name = eu5ab_q_confirmed value = 0 }",
        "\tset_variable = { name = eu5ab_q_progress_last value = 0 }",
        "\tset_variable = { name = eu5ab_q_stall_rounds value = 0 }",
        "\tset_variable = { name = eu5ab_q_confirm_stall_rounds value = 0 }",
        "\tremove_variable = eu5ab_q_fire",
        "\tremove_variable = eu5ab_q_profit_selecting",
        "\teu5ab_reset_engine_candidate_watchdog_progress = yes",
        "}",
        "",
        "eu5ab_clear_engine_priority_phase = {",
        "\teu5ab_reset_engine_priority_phase_progress = yes",
        *(f"\tif = {{ limit = {{ var:eu5ab_q_phase = {phase} }} every_in_list = {{ variable = eu5ab_q_phase_{phase}_locations clear_variable_list = eu5ab_q_failed_types }} }}" for phase in range(1, phase_count + 1)),
        "\tremove_variable = eu5ab_q_retry_phase",
        "\tremove_variable = eu5ab_q_rank_refreshed",
        "}",
        "",
        "eu5ab_prepare_engine_priority_phase = {",
        "\t# Serial refresh reads only registered Mod production projects.",
        "\teu5ab_ensure_rgo_pending = yes",
        "\teu5ab_ensure_build_pending = yes",
        "\tremove_variable = eu5ab_q_expected",
        *(
            line
            for phase in range(1, phase_count + 1)
            for line in (
                "\tif = {",
                f"\t\tlimit = {{ var:eu5ab_q_phase = {phase} }}",
                f"\t\tif = {{ limit = {{ has_variable_list = eu5ab_q_phase_{phase}_locations }} set_variable = {{ name = eu5ab_q_expected value = var:eu5ab_q_phase_{phase}_staged }} }}",
                f"\t\tif = {{ limit = {{ has_variable_list = eu5ab_q_phase_{phase}_rgo_locations }} if = {{ limit = {{ has_variable = eu5ab_q_expected }} change_variable = {{ name = eu5ab_q_expected add = var:eu5ab_q_phase_{phase}_rgo_staged }} }} else = {{ set_variable = {{ name = eu5ab_q_expected value = var:eu5ab_q_phase_{phase}_rgo_staged }} }} }}" if phase <= len(CANDIDATE_PRIORITY_FEATURES) * 2 else "",
                "\t}",
            )
        ),
        "\tif = { limit = { NOT = { has_variable = eu5ab_q_expected } } eu5ab_advance_engine_priority_phase = yes }",
        "}",
        "",
        "# Predicted-profit selection first records the strongest engine-valued candidate",
        "# in each location. One priority point adds a 1% soft bonus based on the",
        "# absolute profit magnitude (floored at 1), so priorities can decide close",
        "# comparisons without defeating a materially larger predicted monthly profit.",
        "eu5ab_record_actual_profit_candidate = {",
        f"\tset_variable = {{ name = eu5ab_q_profit_candidate_priority value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_current_candidate_configured_priority }}",
        "\tset_variable = { name = eu5ab_q_profit_candidate_magnitude value = scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit }",
        "\tif = {",
        "\t\tlimit = { eu5ab_profit_candidate_magnitude_value < 0 }",
        "\t\tset_variable = { name = eu5ab_q_profit_candidate_magnitude value = { value = eu5ab_profit_candidate_magnitude_value multiply = -1 } }",
        "\t}",
        "\tif = { limit = { eu5ab_profit_candidate_magnitude_value < 1 } set_variable = { name = eu5ab_q_profit_candidate_magnitude value = 1 } }",
        "\tset_variable = {",
        "\t\tname = eu5ab_q_profit_candidate_rank",
        "\t\tvalue = {",
        "\t\t\tvalue = eu5ab_profit_candidate_magnitude_value",
        "\t\t\tmultiply = eu5ab_profit_candidate_priority_value",
        "\t\t\tmultiply = 0.01",
        "\t\t\tadd = scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit",
        "\t\t}",
        "\t}",
        "\t# Penalize ranking only. Emergency negative-profit projects stay eligible.",
        "\tif = {",
        "\t\tlimit = { eu5ab_profit_candidate_rank_value >= 0 }",
        "\t\tset_variable = { name = eu5ab_q_profit_candidate_rank value = { value = eu5ab_profit_candidate_rank_value multiply = scope:eu5ab_candidate_building.eu5ab_candidate_current_labor_factor } }",
        "\t}",
        "\telse = {",
        "\t\tset_variable = { name = eu5ab_q_profit_candidate_rank value = { value = eu5ab_profit_candidate_rank_value divide = scope:eu5ab_candidate_building.eu5ab_candidate_current_labor_factor } }",
        "\t}",
        "\tset_variable = { name = eu5ab_q_profit_candidate_rank value = eu5ab_price_profit_rank }",
        "\tset_variable = { name = eu5ab_q_profit_candidate_rank value = eu5ab_pending_profit_rank }",
        "\tset_variable = { name = eu5ab_q_profit_candidate_rank value = eu5ab_capacity_profit_rank }",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\tOR = {",
        "\t\t\t\tNOT = { has_variable_list = eu5ab_q_profit_best_types }",
        "\t\t\t\teu5ab_profit_best_rank_value < eu5ab_profit_candidate_rank_value",
        "\t\t\t}",
        "\t\t}",
        "\t\tset_variable = { name = eu5ab_q_profit_best_actual value = scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit }",
        "\t\tset_variable = { name = eu5ab_q_profit_best_rank value = eu5ab_profit_candidate_rank_value }",
        "\t\tclear_variable_list = eu5ab_q_profit_best_types",
        f"\t\tadd_to_variable_list = {{ name = eu5ab_q_profit_best_types target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t}",
        "\tremove_variable = eu5ab_q_profit_candidate_priority",
        "\tremove_variable = eu5ab_q_profit_candidate_magnitude",
        "\tremove_variable = eu5ab_q_profit_candidate_rank",
        "}",
        "",
        "eu5ab_prepare_actual_profit_selection = {",
        "\tclear_variable_list = eu5ab_q_profit_locations",
        "\tset_variable = { name = eu5ab_q_expected value = 0 }",
        "\tsave_scope_as = eu5ab_q_profit_country",
        *(
            line
            for phase in range(1, phase_count + 1)
            for line in (
                "\tif = {",
                f"\t\tlimit = {{ var:eu5ab_q_phase = {phase} has_variable_list = eu5ab_q_phase_{phase}_locations }}",
                "\t\tordered_in_list = {",
                f"\t\t\tvariable = eu5ab_q_phase_{phase}_locations",
                "\t\t\tlimit = { has_variable_list = eu5ab_q_profit_best_types }",
                "\t\t\torder_by = eu5ab_profit_best_rank_value",
                f"\t\t\tmax = {rules.cadence.deep_score_location_limit}",
                "\t\t\tcheck_range_bounds = no",
                "\t\t\tsave_scope_as = eu5ab_q_profit_location",
                "\t\t\tscope:eu5ab_q_profit_country = {",
                "\t\t\t\tadd_to_variable_list = { name = eu5ab_q_profit_locations target = scope:eu5ab_q_profit_location }",
                "\t\t\t\tchange_variable = { name = eu5ab_q_expected add = 1 }",
                "\t\t\t}",
                "\t\t}",
                "\t}",
            )
        ),
        "\tif = {",
        "\t\tlimit = { var:eu5ab_q_expected > 0 }",
        "\t\tset_variable = { name = eu5ab_q_processed value = 0 }",
        "\t\tset_variable = { name = eu5ab_q_progress_last value = 0 }",
        "\t\tset_variable = { name = eu5ab_q_stall_rounds value = 0 }",
        "\t\tset_variable = eu5ab_q_profit_selecting",
        "\t\tset_variable = { name = eu5ab_diag_queue_state value = 6 }",
        "\t\teu5ab_reset_engine_candidate_watchdog_progress = yes",
        "\t}",
        "\telse_if = { limit = { eu5ab_q_waiting_data_value <= 0 } eu5ab_advance_engine_priority_phase = yes }",
        "}",
        "",
        "eu5ab_restart_engine_priority_phase = {",
        "\teu5ab_reset_engine_priority_phase_progress = yes",
        "\tremove_variable = eu5ab_q_retry_phase",
        "\tremove_variable = eu5ab_q_rank_refreshed",
        "\teu5ab_prepare_engine_priority_phase = yes",
        "}",
        "",
        "eu5ab_advance_engine_priority_phase = {",
        "\teu5ab_clear_engine_priority_phase = yes",
        "\tif = {",
        "\t\tlimit = {",
        f"\t\t\tvar:eu5ab_q_phase < {len(CANDIDATE_PRIORITY_FEATURES) * 4}",
        "\t\t\tvar:eu5ab_constructions_started_this_tick < { value = var:eu5ab_monthly_build_quota }",
        "\t\t}",
        "\t\tchange_variable = { name = eu5ab_q_phase add = 1 }",
        "\t\teu5ab_prepare_engine_priority_phase = yes",
        "\t}",
        "\telse = { eu5ab_finish_engine_candidate_queue = yes }",
        "}",
        "",
        "# Root is an approved location. Reserve actual engine cost without",
        "# charging the annual pool until queue growth confirms success.",
        "eu5ab_reserve_engine_candidate = {",
        "\towner = {",
        f"\t\tchange_variable = {{ name = eu5ab_q_planned_spend add = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_q_approved_cost }}",
        f"\t\tchange_variable = {{ name = eu5ab_q_planned_budget add = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_q_approved_cost }}",
        "\t}",
        "}",
        "",
        "eu5ab_release_engine_candidate_reservation = {",
        "\towner = {",
        f"\t\tchange_variable = {{ name = eu5ab_q_planned_spend subtract = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_q_approved_cost }}",
        f"\t\tchange_variable = {{ name = eu5ab_q_planned_budget subtract = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_q_approved_cost }}",
        "\t}",
        "}",
        "",
        "eu5ab_commit_engine_candidate_budget = {",
        f"\tset_local_variable = {{ name = eu5ab_budget_charge value = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_q_approved_cost }}",
        "\towner = { eu5ab_charge_annual_budget = yes }",
        "\teu5ab_release_engine_candidate_reservation = yes",
        "}",
        "",
        "# Called by the validation GUI after all actual-value gates pass.",
        "eu5ab_approve_engine_candidate = {",
        "\teu5ab_report_candidate_approved = yes",
        "\tremove_variable = eu5ab_pending_predecessor",
        "\tremove_variable = eu5ab_pending_predecessor_before",
        "\tset_variable = { name = eu5ab_q_queue_before value = num_civil_constructions }",
        "\tset_variable = { name = eu5ab_q_type_queue_before value = eu5ab_candidate_queued_levels }",
        '\tset_variable = { name = eu5ab_q_type_level_before value = eu5ab_candidate_completed_levels }',
        "\tset_variable = { name = eu5ab_q_approved_cost value = scope:eu5ab_engine_cost }",
        "\tset_variable = { name = eu5ab_q_approved_income value = scope:eu5ab_engine_income }",
        "\tset_variable = { name = eu5ab_q_approved_profit value = scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit }",
        "\t# Snapshot the action before construction changes has_building state.",
        "\tset_variable = { name = eu5ab_q_approved_build_kind value = 3 }",
        f"\tif = {{ limit = {{ scope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_replaces_existing_building = yes }} }} set_variable = {{ name = eu5ab_q_approved_build_kind value = 2 }} }}",
        f"\telse_if = {{ limit = {{ scope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_candidate_is_expansion = yes }} }} set_variable = {{ name = eu5ab_q_approved_build_kind value = 4 }} }}",
        "\tset_variable = eu5ab_q_location_approved",
        f"\tadd_to_variable_list = {{ name = eu5ab_q_approved_types target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\tsave_scope_as = eu5ab_q_approved_location",
        "\towner = {",
        "\t\tif = {",
        "\t\t\tlimit = { NOT = { is_target_in_variable_list = { name = eu5ab_q_approved_locations target = scope:eu5ab_q_approved_location } } }",
        "\t\t\tadd_to_variable_list = { name = eu5ab_q_approved_locations target = scope:eu5ab_q_approved_location }",
        "\t\t}",
        "\t\tchange_variable = { name = eu5ab_q_approved add = 1 }",
        "\t\tset_variable = { name = eu5ab_diag_last_actual_cost value = scope:eu5ab_engine_cost }",
        "\t\tset_variable = { name = eu5ab_diag_last_actual_income value = scope:eu5ab_engine_income }",
        "\t\tset_variable = { name = eu5ab_diag_last_actual_profit value = scope:eu5ab_candidate_location.eu5ab_engine_adjusted_profit }",
        "\t}",
        "\teu5ab_reserve_engine_candidate = yes",
        "\teu5ab_commit_candidate_construction_demand = yes",
        "\teu5ab_reserve_candidate_output = yes",
        "\teu5ab_acknowledge_approved_engine_candidate = yes",
        "}",
        "",
        "# Queue confirmation is the only place that settles annual budget and cooldown.",
        "eu5ab_confirm_engine_candidate = {",
        "\tif = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_q_confirmed_types target = scope:eu5ab_candidate_building } } }",
        f"\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
        "\tif = {",
        "\t\tlimit = { eu5ab_approved_building_started = yes }",
        "\t\teu5ab_commit_engine_candidate_budget = yes",
        "\t\tremove_variable = eu5ab_failure_cooldown",
        "\t\tset_variable = eu5ab_action_taken",
        "\t\teu5ab_record_confirmed_building = yes",
        "\t\teu5ab_report_candidate_confirmed = yes",
        "\t\teu5ab_pf_confirm_start = yes",
        "\t\teu5ab_record_queue_start_location = yes",
        "\t\tif = { limit = { eu5ab_location_has_parallel_room = yes } owner = { set_variable = eu5ab_q_retry_phase } }",
        "\t\tif = { limit = { scope:eu5ab_candidate_building = { NOT = { eu5ab_candidate_has_direct_output = yes } } } set_variable = { name = eu5ab_recent_build_penalty value = 12 } }",
        "\t\towner = {",
        f"\t\t\tif = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_active_project_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }} }} add_to_variable_list = {{ name = eu5ab_active_project_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }}",
        "\t\t\t" + _increment_runtime_counter("eu5ab_diag_active_mod_projects"),
        "\t\t\t" + _increment_runtime_counter("eu5ab_constructions_started_this_tick"),
        "\t\t\tif = {",
        f"\t\t\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ exists = var:eu5ab_q_approved_emergency_override }} }}",
        "\t\t\t\t" + _increment_runtime_counter("eu5ab_diag_emergency_overrides_used"),
        "\t\t\t}",
        "\t\t\tset_variable = { name = eu5ab_diag_built_this_run value = 1 }",
        f"\t\t\tset_variable = {{ name = eu5ab_diag_last_build_location value = scope:{CANDIDATE_LOCATION_SCOPE} }}",
        f"\t\t\tset_variable = {{ name = eu5ab_diag_last_building value = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t\t\tset_variable = { name = eu5ab_diag_last_build_kind value = 3 }",
        f"\t\t\tif = {{ limit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_variable = eu5ab_q_approved_build_kind }} }} set_variable = {{ name = eu5ab_diag_last_build_kind value = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_q_approved_build_kind }} }}",
        "\t\t}",
        "\t}",
        "\telse = {",
        "\t\teu5ab_release_engine_candidate_reservation = yes",
        "\t\teu5ab_release_candidate_construction_demand = yes",
        "\t\teu5ab_release_candidate_output = yes",
        f"\t\tset_variable = {{ name = eu5ab_failure_cooldown value = {rules.failure_cooldowns.vanilla_rejected} }}",
        "\t\towner = { change_variable = { name = eu5ab_diag_fail_vanilla add = 1 } }",
        f"\t\tadd_to_variable_list = {{ name = eu5ab_q_failed_types target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t\towner = { set_variable = eu5ab_q_retry_phase }",
        "\t}",
        "\towner = { " + _increment_runtime_counter("eu5ab_q_confirmed") + " }",
        "\tremove_variable = eu5ab_q_material_market",
        f"\tadd_to_variable_list = {{ name = eu5ab_q_confirmed_types target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t}",
        "}",
        "",
        "# Script-event watchdog for the hidden GUI bridge. It ignores callback activity",
        "# and requires phase, processed, seen, or confirmed to make real progress.",
        "eu5ab_check_engine_candidate_queue_watchdog = {",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\thas_variable = eu5ab_q_active",
        "\t\t\thas_variable = eu5ab_q_phase",
        "\t\t\thas_variable = eu5ab_q_processed",
        "\t\t\thas_variable = eu5ab_q_seen",
        "\t\t\thas_variable = eu5ab_q_confirmed",
        "\t\t\thas_variable = eu5ab_q_watchdog_last_phase",
        "\t\t\thas_variable = eu5ab_q_watchdog_last_processed",
        "\t\t\thas_variable = eu5ab_q_watchdog_last_seen",
        "\t\t\thas_variable = eu5ab_q_watchdog_last_confirmed",
        "\t\t\thas_variable = eu5ab_q_watchdog_stall_checks",
        "\t\t}",
        "\t\tif = {",
        "\t\t\tlimit = {",
        "\t\t\t\tOR = {",
        "\t\t\t\t\tvar:eu5ab_q_phase > { value = var:eu5ab_q_watchdog_last_phase }",
        "\t\t\t\t\tvar:eu5ab_q_processed > { value = var:eu5ab_q_watchdog_last_processed }",
        "\t\t\t\t\tvar:eu5ab_q_seen > { value = var:eu5ab_q_watchdog_last_seen }",
        "\t\t\t\t\tvar:eu5ab_q_confirmed > { value = var:eu5ab_q_watchdog_last_confirmed }",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t\teu5ab_reset_engine_candidate_watchdog_progress = yes",
        "\t\t}",
        "\t\telse_if = { limit = { eu5ab_q_waiting_data_value > 0 NOT = { has_variable = eu5ab_q_fire } eu5ab_q_outstanding_approvals_value <= 0 }",
        "\t\t\teu5ab_ensure_build_pending = yes",
        "\t\t\teu5ab_retry_waiting_candidate_data = yes",
        "\t\t\tset_variable = { name = eu5ab_q_watchdog_stall_checks value = 0 }",
        "\t\t}",
        "\t\telse = { change_variable = { name = eu5ab_q_watchdog_stall_checks add = 1 } }",
        "\t\tif = {",
        f"\t\t\tlimit = {{ has_variable = eu5ab_q_active var:eu5ab_q_watchdog_stall_checks >= {ENGINE_QUEUE_WATCHDOG_STALL_CHECKS} }}",
        "\t\t\tchange_variable = { name = eu5ab_diag_queue_recoveries add = 1 }",
        "\t\t\tset_variable = { name = eu5ab_diag_queue_state value = 5 }",
        "\t\t\teu5ab_finish_engine_candidate_queue = yes",
        "\t\t}",
        "\t}",
        "}",
        "",
        "eu5ab_finish_engine_candidate_queue = {",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_constructions_started_this_tick }",
        "\t\tset_variable = { name = eu5ab_diag_previous_month_added value = var:eu5ab_constructions_started_this_tick }",
        "\t}",
        "\tif = { limit = { has_variable = eu5ab_rgo_started_this_tick } set_variable = { name = eu5ab_diag_rgo_quota_used value = var:eu5ab_rgo_started_this_tick } }",
        "\t# Reconstruct the round result from confirmed starts, including saved rounds.",
        "\tset_variable = { name = eu5ab_diag_built_this_run value = 2 }",
        "\tif = { limit = { has_variable = eu5ab_constructions_started_this_tick } if = { limit = { var:eu5ab_constructions_started_this_tick > 0 } set_variable = { name = eu5ab_diag_built_this_run value = 1 } } }",
        "\tif = { limit = { NOT = { var:eu5ab_diag_queue_state = 5 } } set_variable = { name = eu5ab_diag_queue_state value = 4 } }",
        "\teu5ab_settle_scan_candidate_batch = yes",
        "\teu5ab_clear_engine_candidate_queue = yes",
        "\tif = { limit = { NOT = { has_variable = eu5ab_scan_refill_active } } eu5ab_reset_committed_construction_demand = yes }",
        "\tremove_variable = eu5ab_q_active",
        "\tremove_variable = eu5ab_q_fire",
        "\t# Keep phase/expected/tick counters as harmless sentinels until the next",
        "\t# prepare call; an already-scheduled GUI animation may finish one frame late.",
        "}",
        "",
    ]
    return "\n".join(chunks)


def render_runtime_recovery_effects() -> str:
    chunks = [
        "# Internal save migration. Persistent templates, settings, budgets, and",
        "# already-confirmed construction markers are deliberately preserved.",
        "eu5ab_migrate_runtime_v2 = {",
        "\tclear_variable_list = eu5ab_active_project_locations",
        "\tsave_scope_as = eu5ab_migration_country",
        "\tevery_owned_location = {",
        "\t\tif = {",
        "\t\t\tlimit = { OR = { has_variable_list = eu5ab_active_building_types has_variable = eu5ab_active_rgo_construction } }",
        "\t\t\tsave_scope_as = eu5ab_migration_active_location",
        "\t\t\tscope:eu5ab_migration_country = { add_to_variable_list = { name = eu5ab_active_project_locations target = scope:eu5ab_migration_active_location } }",
        "\t\t}",
        "\t}",
        "\tset_variable = { name = eu5ab_runtime_schema_version value = 2 }",
        "}",
        "",
        "eu5ab_mark_interrupted_scan_on_load = {",
        "\tif = {",
        "\t\tlimit = { OR = { has_variable = eu5ab_scan_active has_variable = eu5ab_scan_round_active has_variable = eu5ab_scan_refill_active has_variable = eu5ab_q_active has_variable = eu5ab_scan_resume_after_load } }",
        "\t\tset_variable = eu5ab_scan_resume_after_load",
        "\t}",
        "}",
        "",
        "eu5ab_schedule_scan_resume_after_load = {",
        "\tif = {",
        "\t\tlimit = { is_human = yes var:eu5ab_global_enabled > 0 has_variable = eu5ab_scan_resume_after_load }",
        "\t\t# Drain even the longest pre-load queue watchdog before resuming.",
        f"\t\ttrigger_event_silently = {{ id = eu5ab_monthly.4 days = {ENGINE_QUEUE_WATCHDOG_INTERVAL_DAYS + 1} }}",
        "\t}",
        "\telse = { remove_variable = eu5ab_scan_resume_after_load }",
        "}",
        "",
    ]
    return "\n".join(chunks) + save_resume.render_effects()


def render_needs_scripted_effects(
    policies: list[Policy],
    catalog: BuildingCatalog,
    rules: AutomationRules,
    construction_demands: dict[str, ConstructionDemand],
    upgrades: BuildingUpgradeData,
) -> str:
    text = render_scripted_effects(policies, catalog, rules)

    reset_lines = [
        "eu5ab_reset_policy_budgets_if_needed = {",
        "\teu5ab_template_ensure_defaults = yes",
        "\teu5ab_ensure_annual_budget = yes",
        "}",
    ]
    text = _replace_top_level_script_block(
        text,
        "eu5ab_reset_policy_budgets_if_needed",
        "\n".join(reset_lines),
    )

    run_lines = [
        "eu5ab_run_regional_development_policy = {",
        "\teu5ab_ensure_template_coverage = yes",
        "\teu5ab_stamp_scan_month = yes",
        "\teu5ab_clear_scan_market_cache = yes",
        "\teu5ab_refresh_rgo_pending = yes",
        "\teu5ab_ensure_build_pending = yes",
        "\tremove_variable = eu5ab_diag_rgo_pending_location",
        *(f"\tremove_variable = eu5ab_diag_rgo_pending_{field}" for field in rgo_pending.DIAGNOSTIC_FIELDS),
        "\teu5ab_clear_scan_continuation = yes",
        "\tremove_variable = eu5ab_scan_finalizing",
        "\tremove_variable = eu5ab_diag_scan_stalled",
        "\tremove_variable = eu5ab_diag_capacity_waiting remove_variable = eu5ab_diag_capacity_unavailable remove_variable = eu5ab_diag_capacity_last_reason",
        "\t# Reset per-run diagnostics; persistent template coverage stays intact.",
        "\tset_variable = { name = eu5ab_constructions_started_this_tick value = 0 }",
        "\tset_variable = { name = eu5ab_rgo_started_this_tick value = 0 }",
        "\tset_variable = { name = eu5ab_diag_preliminary_passed value = 0 }",
        "\tset_variable = { name = eu5ab_diag_deep_scored value = 0 }",
        "\tset_variable = { name = eu5ab_diag_legal_candidates value = 0 }",
        "\tset_variable = { name = eu5ab_diag_active_mod_projects value = 0 }",
        "\tset_variable = { name = eu5ab_diag_run_state value = 0 }",
        "\tset_variable = { name = eu5ab_diag_concurrent_limit_state value = 2 }",
        "\tset_variable = { name = eu5ab_diag_built_this_run value = 0 }",
        "\tset_variable = { name = eu5ab_diag_has_run value = 1 }",
        "\tset_variable = { name = eu5ab_diag_base_quota value = 0 }",
        "\tset_variable = { name = eu5ab_diag_final_quota value = 0 }",
        "\t# Keep the last completed construction count visible while this month's",
        "\t# initial scan is still running. The per-run tick counter was reset above.",
        "\tset_variable = { name = eu5ab_diag_rgo_quota_used value = 0 }",
        "\tset_variable = { name = eu5ab_diag_workforce_prediction_mode value = 1 }",
        "\tset_variable = { name = eu5ab_diag_queue_recoveries value = 0 }",
        "\tset_variable = { name = eu5ab_diag_emergency_overrides_used value = 0 }",
        "\tset_variable = { name = eu5ab_diag_staged_candidates value = 0 }",
        "\tset_variable = { name = eu5ab_scan_candidate_reserve value = 0 }",
        "\tremove_variable = eu5ab_scan_settled_locations",
        "\tset_variable = { name = eu5ab_diag_engine_probes value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_checked value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_capacity value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_location value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_disabled value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_finance value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_utilization value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_workforce value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_market_need value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_score value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_pending_data value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_fail_pending_limit value = 0 }",
        "\tset_variable = { name = eu5ab_diag_rgo_eligible value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_workforce value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_building_capacity value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_capacity_unavailable value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_inputs value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_oversupply value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_pending_output value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_irrigation_need value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_granary_need value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_storage_pending value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_windmill_need value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_budget value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_cash value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_vanilla value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_no_legal value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_engine_economics value = 0 }",
        "\tset_variable = { name = eu5ab_diag_fail_construction_materials value = 0 }",
        *(
            f"\tremove_variable = eu5ab_diag_top_{rank}_{suffix}"
            for rank in range(1, rules.cadence.candidates_per_location + 1)
            for suffix in ("location", *WORKER_TOP_FIELD_SUFFIXES)
        ),
        *(
            f"\tset_variable = {{ name = eu5ab_diag_top_{rank}_score value = -1000000 }}"
            for rank in range(1, rules.cadence.candidates_per_location + 1)
        ),
        *(
            f"\tset_variable = {{ name = eu5ab_diag_top_{rank}_priority value = 999 }}"
            for rank in range(1, rules.cadence.candidates_per_location + 1)
        ),
        "\tif = {",
        "\t\tlimit = { NOT = { has_variable = eu5ab_monthly_build_hard_cap } }",
        f"\t\tset_variable = {{ name = eu5ab_monthly_build_hard_cap value = {GLOBAL_RULE_DEFAULTS['monthly_build_hard_cap']} }}",
        "\t}",
    ]
    run_lines.extend([
        "\t# Snapshot performance settings once. Mid-run changes apply next month.",
        *candidate_backfill.snapshot_lines(),
        "\tset_variable = { name = eu5ab_scan_parallel value = var:eu5ab_global_parallel_location_scan }",
        "\tset_variable = { name = eu5ab_scan_daily_task_limit value = var:eu5ab_global_daily_location_task_limit }",
        "\tset_variable = { name = eu5ab_scan_max_additions value = var:eu5ab_global_max_additions_per_run }",
        "\tset_variable = { name = eu5ab_scan_early_stop value = var:eu5ab_global_early_stop_when_candidates_sufficient }",
        "\tclamp_variable = { name = eu5ab_scan_daily_task_limit min = 1 max = 30 }",
        "\tclamp_variable = { name = eu5ab_scan_max_additions min = 0 max = 600 }",
        "\tclear_variable_list = eu5ab_worker_pending_locations",
        "\tclear_variable_list = eu5ab_active_project_locations_next",
    ])
    run_lines.extend([
        "\t# Count only locations indexed after this Mod confirmed a project.",
        "\tsave_scope_as = eu5ab_active_project_country",
        "\tevery_in_list = {",
        "\t\tvariable = eu5ab_active_project_locations",
        "\t\tsave_scope_as = eu5ab_active_project_location",
        "\t\tif = {",
        "\t\t\tlimit = { owner = scope:eu5ab_active_project_country has_variable_list = eu5ab_active_building_types }",
        "\t\t\tevery_in_list = {",
        "\t\t\t\tvariable = eu5ab_active_building_types",
        "\t\t\t\tsave_scope_as = eu5ab_candidate_building",
        "\t\t\t\tscope:eu5ab_active_project_location = { save_scope_as = eu5ab_candidate_location eu5ab_refresh_active_building_type = yes }",
        "\t\t\t}",
        "\t\t}",
        "\t\tif = {",
        "\t\t\tlimit = { owner = scope:eu5ab_active_project_country has_variable = eu5ab_active_rgo_construction }",
        "\t\t\tif = {",
        "\t\t\t\t# Population/workforce capacity is not construction completion.",
        "\t\t\t\t# Keep confirmed attribution while the exact RGO queue is unknown.",
        "\t\t\t\tlimit = { NOT = { eu5ab_rgos_under_construction = 0 } }",
        "\t\t\t\towner = { change_variable = { name = eu5ab_diag_active_mod_projects add = 1 } }",
        "\t\t\t}",
        "\t\t\telse = { remove_variable = eu5ab_active_rgo_construction }",
        "\t\t}",
        "\t\tif = {",
        "\t\t\tlimit = {",
        "\t\t\t\towner = scope:eu5ab_active_project_country",
        "\t\t\t\tOR = { has_variable_list = eu5ab_active_building_types has_variable = eu5ab_active_rgo_construction }",
        "\t\t\t}",
        "\t\t\tscope:eu5ab_active_project_country = { add_to_variable_list = { name = eu5ab_active_project_locations_next target = scope:eu5ab_active_project_location } }",
        "\t\t}",
        "\t}",
        "\tclear_variable_list = eu5ab_active_project_locations",
        "\tevery_in_list = {",
        "\t\tvariable = eu5ab_active_project_locations_next",
        "\t\tsave_scope_as = eu5ab_active_project_location",
        "\t\tscope:eu5ab_active_project_country = { add_to_variable_list = { name = eu5ab_active_project_locations target = scope:eu5ab_active_project_location } }",
        "\t}",
        "\tclear_variable_list = eu5ab_active_project_locations_next",
        "\t# Persistent scan buckets are maintained when a policy is applied or a",
        "\t# location changes owner. No all-owned-location rebuild occurs here.",
        "\t# The slider is extra concurrent capacity: 0 means one total slot, 599 means 600.",
        "\tset_variable = { name = eu5ab_monthly_build_quota value = var:eu5ab_monthly_build_hard_cap }",
        "\tchange_variable = { name = eu5ab_monthly_build_quota add = 1 }",
        "\tif = {",
        f"\t\tlimit = {{ var:eu5ab_monthly_build_quota > {rules.cadence.max_country_concurrent_projects} }}",
        f"\t\tset_variable = {{ name = eu5ab_monthly_build_quota value = {rules.cadence.max_country_concurrent_projects} }}",
        "\t}",
        "\tset_variable = { name = eu5ab_diag_base_quota value = var:eu5ab_monthly_build_quota }",
        "\tchange_variable = { name = eu5ab_monthly_build_quota subtract = var:eu5ab_diag_active_mod_projects }",
        "\tif = {",
        "\t\tlimit = { var:eu5ab_monthly_build_quota < 0 }",
        "\t\tset_variable = { name = eu5ab_monthly_build_quota value = 0 }",
        "\t}",
        "\tif = {",
        "\t\tlimit = { var:eu5ab_scan_max_additions > 0 var:eu5ab_monthly_build_quota > { value = var:eu5ab_scan_max_additions } }",
        "\t\tset_variable = { name = eu5ab_monthly_build_quota value = var:eu5ab_scan_max_additions }",
        "\t}",
        "\tif = {",
        "\t\tlimit = { var:eu5ab_diag_active_mod_projects >= { value = var:eu5ab_diag_base_quota } }",
        "\t\tset_variable = { name = eu5ab_diag_concurrent_limit_state value = 1 }",
        "\t}",
        "\tif = {",
        "\t\tlimit = { var:eu5ab_diag_run_state = 0 var:eu5ab_diag_concurrent_limit_state = 1 }",
        "\t\tset_variable = { name = eu5ab_diag_run_state value = 2 }",
        "\t}",
        "\tset_variable = { name = eu5ab_diag_final_quota value = var:eu5ab_monthly_build_quota }",
        "\teu5ab_update_scan_candidate_target = yes",
        "\tset_variable = { name = eu5ab_deep_score_budget value = var:eu5ab_monthly_build_quota }",
        f"\tchange_variable = {{ name = eu5ab_deep_score_budget multiply = {rules.cadence.deep_score_quota_multiplier} }}",
        "\tif = {",
        f"\t\tlimit = {{ var:eu5ab_deep_score_budget > {rules.cadence.deep_score_location_limit} }}",
        f"\t\tset_variable = {{ name = eu5ab_deep_score_budget value = {rules.cadence.deep_score_location_limit} }}",
        "\t}",
        "\t# The daily limit controls pacing, not the round's search coverage.",
        "\t# Remaining locations are dispatched by the existing bounded refill.",
        "\t# Preserve the minimum deep budget for small quotas; early stop may still",
        "\t# prevent later buckets from dispatching workers in this scan.",
        "\tif = { limit = { var:eu5ab_deep_score_budget < 20 } set_variable = { name = eu5ab_deep_score_budget value = 20 } }",
        "\tset_variable = { name = eu5ab_deep_score_attempts value = 0 }",
        "\teu5ab_prepare_engine_candidate_queue = yes",
        "\tif = {",
        "\t\tlimit = { var:eu5ab_monthly_build_quota > 0 }",
        "\t\t# Rotate only when a scan starts, not on quota-zero checks or daily events.",
        "\t\t# Persist the start across loads so early buckets cannot monopolize every run.",
        "\t\tif = {",
        "\t\t\tlimit = { OR = { NOT = { has_variable = eu5ab_scan_start_bucket } var:eu5ab_scan_start_bucket < 1 var:eu5ab_scan_start_bucket >= 20 } }",
        "\t\t\tset_variable = { name = eu5ab_scan_start_bucket value = 1 }",
        "\t\t}",
        "\t\telse = { change_variable = { name = eu5ab_scan_start_bucket add = 1 } }",
        "\t\tset_variable = { name = eu5ab_scan_bucket_day value = 1 }",
        "\t\tset_variable = eu5ab_scan_active",
        "\t\tset_variable = eu5ab_scan_round_active",
        "\t}",
        "\telse = {",
        "\t\tset_variable = { name = eu5ab_diag_built_this_run value = 2 }",
        "\t\t# Queue preparation also performs stale-state cleanup, but an empty",
        "\t\t# check must not be displayed as a prepared construction queue.",
        "\t\tremove_variable = eu5ab_diag_queue_state",
        "\t}",
        "}",
    ])
    text = _replace_top_level_script_block(
        text,
        "eu5ab_run_regional_development_policy",
        "\n".join(run_lines),
    )

    scan_lines = [
        "eu5ab_scan_regional_development_bucket = {",
        "\teu5ab_record_scan_date = yes",
        "\t# Previous workers have merged before this country-only refresh.",
        "\teu5ab_refresh_rgo_pending = yes",
        "\teu5ab_ensure_build_pending = yes",
        "\tsave_scope_as = eu5ab_scan_country",
        "\t# Keep the event's day counter independent of the rotated physical bucket.",
        "\t# Missing start state retains the legacy day-to-bucket mapping.",
        "\tset_variable = { name = eu5ab_scan_bucket_index value = var:eu5ab_scan_bucket_day }",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_scan_start_bucket }",
        "\t\tchange_variable = { name = eu5ab_scan_bucket_index add = var:eu5ab_scan_start_bucket }",
        "\t\tchange_variable = { name = eu5ab_scan_bucket_index subtract = 1 }",
        "\t}",
        "\tif = { limit = { var:eu5ab_scan_bucket_index > 20 } change_variable = { name = eu5ab_scan_bucket_index subtract = 20 } }",
        "\t# Per-call scratch state; never carry a stop decision into a new scan.",
        "\tremove_variable = eu5ab_bucket_dispatch_stopped",
        "\tset_variable = { name = eu5ab_daily_deep_score_budget value = { value = var:eu5ab_deep_score_budget divide = 21 ceiling = yes } }",
        "\tif = { limit = { var:eu5ab_daily_deep_score_budget > { value = var:eu5ab_scan_daily_task_limit } } set_variable = { name = eu5ab_daily_deep_score_budget value = var:eu5ab_scan_daily_task_limit } }",
        "\tset_variable = { name = eu5ab_daily_deep_score_attempts value = 0 }",
    ]
    for bucket in range(1, 21):
        scan_lines.extend([
            "\tif = {",
            f"\t\tlimit = {{ var:eu5ab_scan_bucket_index = {bucket} }}",
            "\t\t# Only the global budget/reserve stop is permanent for this scan.",
            "\t\tif = {",
            "\t\t\tlimit = { OR = { eu5ab_scan_attempt_count >= { value = var:eu5ab_deep_score_budget } AND = { eu5ab_scan_early_stop_value > 0 eu5ab_scan_reserve_count >= { value = var:eu5ab_scan_candidate_target } } } }",
            "\t\t\t# Ordered dispatch reads each member's owner. Preserve legacy behavior",
            "\t\t\t# if a stale bucket contains a location belonging to another country.",
            "\t\t\tif = {",
            f"\t\t\t\tlimit = {{ NOT = {{ any_in_list = {{ variable = eu5ab_scan_bucket_{bucket}_locations NOT = {{ owner = scope:eu5ab_scan_country }} }} }} }}",
            "\t\t\t\tset_variable = { name = eu5ab_bucket_dispatch_stopped value = 1 }",
            "\t\t\t}",
            "\t\t}",
            "\t\tevery_in_list = {",
            f"\t\t\tvariable = eu5ab_scan_bucket_{bucket}_locations",
            "\t\t\tlimit = { owner = scope:eu5ab_scan_country has_variable = eu5ab_policy_id }",
            "\t\t\tif = { limit = { has_variable = eu5ab_build_cooldown } change_variable = { name = eu5ab_build_cooldown subtract = 1 } if = { limit = { var:eu5ab_build_cooldown <= 0 } remove_variable = eu5ab_build_cooldown } }",
            "\t\t\tif = { limit = { has_variable = eu5ab_failure_cooldown } change_variable = { name = eu5ab_failure_cooldown subtract = 1 } if = { limit = { var:eu5ab_failure_cooldown <= 0 } remove_variable = eu5ab_failure_cooldown } }",
            "\t\t\tif = { limit = { has_variable = eu5ab_recent_build_penalty } change_variable = { name = eu5ab_recent_build_penalty subtract = 1 } if = { limit = { var:eu5ab_recent_build_penalty <= 0 } remove_variable = eu5ab_recent_build_penalty } }",
            "\t\t\tif = {",
            "\t\t\t\tlimit = {",
            "\t\t\t\t\teu5ab_location_template_not_paused = yes",
            "\t\t\t\t\teu5ab_location_has_parallel_room = yes",
            "\t\t\t\t\tNOT = { has_variable = eu5ab_build_cooldown }",
            "\t\t\t\t\tNOT = { has_variable = eu5ab_failure_cooldown }",
            "\t\t\t\t}",
            "\t\t\t\towner = { change_variable = { name = eu5ab_diag_preliminary_passed add = 1 } }",
            "\t\t\t\tif = { limit = { NOT = { has_variable = eu5ab_wait_months } } set_variable = { name = eu5ab_wait_months value = 0 } }",
            "\t\t\t\tchange_variable = { name = eu5ab_wait_months add = 1 }",
            "\t\t\t\tsave_scope_as = eu5ab_candidate_location",
            "\t\t\t\towner = { add_to_variable_list = { name = eu5ab_scan_unscanned_locations target = scope:eu5ab_candidate_location } }",
            "\t\t\t\t# Cache after cooldown and waiting updates so both mutually exclusive",
            "\t\t\t\t# sorts observe exactly the same daily score as before.",
            "\t\t\t\tif = {",
            "\t\t\t\t\tlimit = { scope:eu5ab_scan_country = { NOT = { has_variable = eu5ab_bucket_dispatch_stopped } } }",
            "\t\t\t\t\tset_variable = { name = eu5ab_bucket_need_score value = eu5ab_location_need_score }",
            "\t\t\t\t}",
            "\t\t\t}",
            "\t\t}",
        ])
        sort_lines = []
        for emergency_condition in (
            "eu5ab_food_emergency_enabled = yes",
            "NOT = { eu5ab_food_emergency_enabled = yes }",
        ):
            sort_lines.extend([
                "\t\tordered_in_list = {",
                f"\t\t\tvariable = eu5ab_scan_bucket_{bucket}_locations",
                "\t\t\tlimit = {",
                "\t\t\t\thas_variable = eu5ab_policy_id",
                "\t\t\t\teu5ab_location_template_not_paused = yes",
                "\t\t\t\teu5ab_location_has_parallel_room = yes",
                "\t\t\t\tNOT = { has_variable = eu5ab_build_cooldown }",
                "\t\t\t\tNOT = { has_variable = eu5ab_failure_cooldown }",
                f"\t\t\t\t{emergency_condition}",
                "\t\t\t}",
                "\t\t\torder_by = var:eu5ab_bucket_need_score",
                "\t\t\tmax = 30",
                "\t\t\tcheck_range_bounds = no",
                "\t\t\tif = {",
                "\t\t\t\tlimit = { owner = { eu5ab_scan_daily_attempt_count < { value = var:eu5ab_daily_deep_score_budget } eu5ab_scan_attempt_count < { value = var:eu5ab_deep_score_budget } OR = { eu5ab_scan_early_stop_value <= 0 eu5ab_scan_reserve_count < { value = var:eu5ab_scan_candidate_target } } } }",
                f"\t\t\t\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
                "\t\t\t\tset_variable = { name = eu5ab_cached_location_need_score value = var:eu5ab_bucket_need_score }",
                "\t\t\t\towner = {",
                "\t\t\t\t\tchange_variable = { name = eu5ab_daily_deep_score_attempts add = 1 }",
                "\t\t\t\t\tchange_variable = { name = eu5ab_deep_score_attempts add = 1 }",
                "\t\t\t\t\tremove_list_variable = { name = eu5ab_scan_unscanned_locations target = scope:eu5ab_candidate_location }",
                "\t\t\t\t\tchange_variable = { name = eu5ab_diag_deep_scored add = 1 }",
                "\t\t\t\t}",
                "\t\t\t\tremove_variable = eu5ab_wait_months",
                "\t\t\t\teu5ab_prepare_backfill_dispatch = yes",
                "\t\t\t\towner = { if = { limit = { NOT = { is_target_in_variable_list = { name = eu5ab_worker_pending_locations target = scope:eu5ab_candidate_location } } } add_to_variable_list = { name = eu5ab_worker_pending_locations target = scope:eu5ab_candidate_location } } }",
                "\t\t\t\teu5ab_request_building_capacity = yes",
                "\t\t\t}",
                "\t\t}",
            ])
        scan_lines.extend([
            "\t\tif = {",
            "\t\t\tlimit = { NOT = { has_variable = eu5ab_bucket_dispatch_stopped } }",
            *("\t" + line for line in sort_lines),
            "\t\t}",
            "\t\tevery_in_list = {",
            f"\t\t\tvariable = eu5ab_scan_bucket_{bucket}_locations",
            "\t\t\tremove_variable = eu5ab_bucket_need_score",
            "\t\t}",
            "\t}",
        ])
    scan_lines.extend([
        "\tremove_variable = eu5ab_scan_bucket_index",
        "\tremove_variable = eu5ab_bucket_dispatch_stopped",
        "\tif = { limit = { var:eu5ab_scan_parallel <= 0 } eu5ab_merge_location_worker_results = yes }",
        "\tremove_variable = eu5ab_daily_deep_score_budget",
        "\tremove_variable = eu5ab_daily_deep_score_attempts",
        "}",
        "",
        "eu5ab_finish_regional_development_scan = {",
        "\tif = { limit = { has_variable_list = eu5ab_worker_pending_locations }",
        "\t\tset_variable = eu5ab_scan_finalizing eu5ab_count_capacity_waiting = yes",
        "\t\ttrigger_event_silently = { id = eu5ab_monthly.2 days = 1 }",
        "\t}",
        "\telse = {",
        "\t# EU5 drops variables set to zero; persist non-zero snapshot states for GUI reads.",
        "\tif = { limit = { NOT = { has_variable = eu5ab_diag_run_state } } set_variable = { name = eu5ab_diag_run_state value = 5 } }",
        "\tif = { limit = { NOT = { has_variable = eu5ab_diag_built_this_run } } set_variable = { name = eu5ab_diag_built_this_run value = 2 } }",
        "\tremove_variable = eu5ab_scan_active",
        "\tremove_variable = eu5ab_scan_bucket_day",
        "\tif = { limit = { var:eu5ab_diag_run_state = 0 var:eu5ab_diag_covered_locations <= 0 } set_variable = { name = eu5ab_diag_run_state value = 1 } }",
        "\tif = { limit = { var:eu5ab_diag_run_state = 0 var:eu5ab_diag_preliminary_passed <= 0 } set_variable = { name = eu5ab_diag_run_state value = 4 } }",
        "\t# The final reducer has selected the displayed Top-3. Hydrate expensive",
        "\t# building-only diagnostic details once per displayed candidate.",
        "\teu5ab_hydrate_final_building_diagnostics = yes",
        "\teu5ab_start_engine_candidate_queue = yes",
        "\t}",
        "}",
    ])
    refill_dispatch = [line.replace(f"eu5ab_scan_bucket_{bucket}_locations", "eu5ab_scan_unscanned_locations") for line in sort_lines]
    text = text.rstrip() + "\n\n" + "\n".join(scan_lines) + "\n"
    text += scan_reserve.render_effects()
    text += scan_reserve.render_watchdog()
    text += scan_reserve.render_refill(refill_dispatch)

    def rgo_candidate_diagnostic_lines() -> list[str]:
        return [
            "\t\t# RGO participates in the same per-location diagnostic choice as buildings.",
            "\t\tset_variable = { name = eu5ab_rgo_diag_priority value = owner.var:eu5ab_candidate_priority_rgo }",
            "\t\tif = { limit = { NOT = { eu5ab_rgo_food_emergency_enabled = yes } } change_variable = { name = eu5ab_rgo_diag_priority add = 4 } }",
            "\t\tif = {",
            "\t\t\tlimit = {",
            "\t\t\t\tOR = {",
            "\t\t\t\t\tNOT = { has_variable = eu5ab_worker_top_1_kind }",
            "\t\t\t\t\tvar:eu5ab_worker_top_1_priority > { value = var:eu5ab_rgo_diag_priority }",
            "\t\t\t\t}",
            "\t\t\t}",
            *(
                f"\t\t\tremove_variable = eu5ab_worker_top_1_{suffix}"
                for suffix in WORKER_TOP_FIELD_SUFFIXES if suffix not in {"economic", "building"}
            ),
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_kind value = 2 }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_priority value = var:eu5ab_rgo_diag_priority }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_score value = eu5ab_rgo_queue_order_score }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_need value = eu5ab_location_need_score }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_labor_jobs value = { value = eu5ab_rgo_jobs_per_expansion multiply = 1000 } }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_labor_current value = { value = eu5ab_rgo_current_available_workers multiply = 1000 } }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_labor_projected value = { value = eu5ab_rgo_projected_available_workers multiply = 1000 } }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_rgo_price_factor value = { value = eu5ab_rgo_price_factor multiply = 100 } }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_rgo_pending_factor value = { value = eu5ab_rgo_pending_factor multiply = 100 } }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_rgo_pending_quantity value = eu5ab_rgo_market_pending_quantity }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_rgo_pending_limit value = eu5ab_rgo_pending_limit }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_rgo_market_gap value = eu5ab_rgo_market_gap }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_rgo_labor_factor value = { value = eu5ab_rgo_current_labor_factor multiply = 100 } }",
            "\t\t\tset_variable = { name = eu5ab_worker_top_1_reason value = 8 }",
            "\t\t}",
            "\t\tremove_variable = eu5ab_rgo_diag_priority",
        ]

    router_lines = [
        "eu5ab_try_construct_policy_candidate = {",
        "\tremove_variable = eu5ab_action_taken",
        "\tremove_variable = eu5ab_location_candidate_staged",
        "\tremove_variable = eu5ab_ordinary_candidate_staged",
        "\tremove_variable = eu5ab_pending_failure_cooldown",
        "\t# Defer this pass's ordinary-building failures until RGO has been evaluated.",
        "\t# Existing cooldowns remain active throughout candidate selection.",
        "\t# All four feature classes are staged. The hidden queue applies the player's",
        "\t# ordered CMM list and the enabled food-emergency layer before it executes.",
    ]
    for index, policy in enumerate(policies):
        router_lines.extend([
            "\tif = {",
            "\t\tlimit = {",
            "\t\t\tNOT = { has_variable = eu5ab_action_taken }",
            "\t\t\tmarket ?= { always = yes }",
            f"\t\t\tvar:eu5ab_policy_id = {_policy_index(policy, index)}",
            "\t\t}",
            f"\t\teu5ab_try_construct_{policy.id} = yes",
            "\t}",
        ])
    for slot in TEMPLATE_SLOTS:
        router_lines.extend([
            "\tif = {",
            "\t\tlimit = {",
            "\t\t\tNOT = { has_variable = eu5ab_action_taken }",
            "\t\t\tmarket ?= { always = yes }",
            f"\t\t\tvar:eu5ab_policy_id = {CUSTOM_POLICY_VALUE}",
            f"\t\t\tvar:eu5ab_template_slot = {slot}",
            "\t\t}",
            f"\t\teu5ab_try_construct_template_slot_{slot} = yes",
            "\t}",
        ])
    router_lines.extend([
        "\t# Each deeply-scored location enters exactly one RGO gate result.",
        "\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_checked add = 1 }",
        "\tif = {",
        "\t\tlimit = { NOT = { eu5ab_rgo_capacity_available = yes } }",
        "\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_capacity add = 1 }",
        "\t}",
        "\telse_if = {",
        "\t\tlimit = { NOT = { eu5ab_rgo_location_available = yes } }",
        "\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_location add = 1 }",
        "\t}",
        "\telse_if = {",
        "\t\tlimit = { NOT = { eu5ab_rgo_enabled = yes } }",
        "\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_disabled add = 1 }",
        "\t}",
        "\telse_if = {",
        "\t\tlimit = { NOT = { eu5ab_rgo_finance_available = yes } }",
        "\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_finance add = 1 }",
        "\t}",
        "\telse_if = {",
        "\t\tlimit = { NOT = { eu5ab_rgo_utilization_allowed = yes } }",
        "\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_utilization add = 1 }",
        "\t}",
        "\telse_if = {",
        "\t\tlimit = { NOT = { eu5ab_rgo_workforce_allowed = yes } }",
        "\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_workforce add = 1 }",
        "\t}",
        "\telse = {",
        "\t\t# Only surviving RGO candidates need a synchronous market snapshot.",
        "\t\teu5ab_prepare_rgo_screening = yes",
        "\t\tif = {",
        "\t\t\tlimit = { NOT = { eu5ab_rgo_food_emergency_enabled = yes } NOT = { eu5ab_rgo_pending_data_available = yes } }",
        "\t\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_pending_data add = 1 }",
        "\t\t\teu5ab_capture_rgo_pending_diagnostics = yes",
        "\t\t\teu5ab_stage_rgo_candidate = yes",
        "\t\t}",
        "\t\telse_if = {",
        "\t\t\tlimit = { NOT = { eu5ab_rgo_market_need_present = yes } }",
        "\t\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_market_need add = 1 }",
        "\t\t}",
        "\t\telse_if = {",
        "\t\t\tlimit = { NOT = { eu5ab_rgo_score_allowed = yes } }",
        "\t\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_score add = 1 }",
        "\t\t}",
        "\t\telse_if = {",
        "\t\t\tlimit = { NOT = { eu5ab_rgo_pending_allowed = yes } }",
        "\t\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_fail_pending_limit add = 1 }",
        "\t\t\teu5ab_capture_rgo_pending_diagnostics = yes",
        "\t\t}",
        "\t\telse = {",
        "\t\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_rgo_eligible add = 1 }",
        "\t\t\teu5ab_capture_rgo_pending_diagnostics = yes",
        *("\t" + line for line in rgo_candidate_diagnostic_lines()),
        "\t\t\teu5ab_stage_rgo_candidate = yes",
        "\t\t}",
        "\t\teu5ab_clear_rgo_screening = yes",
        "\t}",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_pending_failure_cooldown }",
        "\t\tset_variable = { name = eu5ab_failure_cooldown value = var:eu5ab_pending_failure_cooldown }",
        "\t}",
        "\tremove_variable = eu5ab_pending_failure_cooldown",
    ])
    router_lines.append("}")
    text = _replace_top_level_script_block(
        text,
        "eu5ab_try_construct_policy_candidate",
        "\n".join(router_lines),
    )

    # Engine values are GUI-only. Regular building candidates are staged for
    # the hidden bridge instead of executing a script-side fixed-cost build.
    dispatcher_lines = [
        "eu5ab_hydrate_final_building_diagnostics = {",
        "\tsave_scope_as = eu5ab_diag_country",
        *(
            line
            for rank in range(1, rules.cadence.candidates_per_location + 1)
            for line in (
                "\tif = {",
                f"\t\tlimit = {{ has_variable = eu5ab_diag_top_{rank}_kind }}",
                "\t\tif = {",
                "\t\t\tlimit = {",
                f"\t\t\t\tvar:eu5ab_diag_top_{rank}_kind = 1",
                f"\t\t\t\thas_variable = eu5ab_diag_top_{rank}_location",
                f"\t\t\t\thas_variable = eu5ab_diag_top_{rank}_building",
                "\t\t\t}",
                f"\t\t\tvar:eu5ab_diag_top_{rank}_location = {{",
                f"\t\t\t\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
                "\t\t\t\tscope:eu5ab_diag_country = {",
                f"\t\t\t\t\tvar:eu5ab_diag_top_{rank}_building = {{",
                f"\t\t\t\t\t\tsave_scope_as = {CANDIDATE_BUILDING_SCOPE}",
                "\t\t\t\t\t\tscope:eu5ab_diag_country = {",
                f"\t\t\t\t\t\t\tset_variable = {{ name = eu5ab_diag_top_{rank}_need value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_universal_need_score }}",
                f"\t\t\t\t\t\t\tset_variable = {{ name = eu5ab_diag_top_{rank}_economic value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_recipe_economic_efficiency_score }}",
                f"\t\t\t\t\t\t\tset_variable = {{ name = eu5ab_diag_top_{rank}_labor_jobs value = {{ value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_candidate_net_new_jobs multiply = 1000 }} }}",
                f"\t\t\t\t\t\t\tset_variable = {{ name = eu5ab_diag_top_{rank}_labor_current value = {{ value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_candidate_current_available_workers multiply = 1000 }} }}",
                f"\t\t\t\t\t\t\tset_variable = {{ name = eu5ab_diag_top_{rank}_labor_projected value = {{ value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_candidate_projected_available_workers multiply = 1000 }} }}",
                "\t\t\t\t\t\t}",
                "\t\t\t\t\t}",
                "\t\t\t\t}",
                "\t\t\t}",
                "\t\t}",
                "\t}",
            )
        ),
        "}",
        "",
        "eu5ab_try_construct_saved_building_type = {",
        "\tif = {",
        f"\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ NOT = {{ has_variable = eu5ab_action_taken }} }} }}",
        f"\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ eu5ab_stage_engine_candidate = yes }}",
        "\t}",
        "}",
    ]
    text = text.rstrip() + "\n\n" + "\n".join(dispatcher_lines) + "\n"

    def candidate_gate_lines(
        gates: list[tuple[str, str, int, int]],
    ) -> list[str]:
        """Classify expensive gates inside the retained candidate iterator."""
        from .worker_screening import prepare
        preparations = {
            "eu5ab_candidate_pending_preliminary_allowed": prepare("pending_allowed"),
            "eu5ab_inputs_available": prepare("inputs"),
            "eu5ab_output_not_oversupplied": prepare("prices"),
        }
        lines: list[str] = []
        for index, (trigger, counter, cooldown, _) in enumerate(gates):
            stage = [
                f"\t\tif = {{ limit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ NOT = {{ has_variable = eu5ab_action_taken }} }} }} {preparations[trigger]} = yes }}",
                "\t\tif = {",
                "\t\t\tlimit = {",
                f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ NOT = {{ has_variable = eu5ab_action_taken }} }}",
                f"\t\t\t\tNOT = {{ {trigger} = yes }}",
                "\t\t\t}",
                f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
                *([f"\t\t\t\tset_variable = {{ name = eu5ab_pending_failure_cooldown value = {cooldown} }}"] if cooldown else []),
                "\t\t\t}",
                f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
                f"\t\t\t\tchange_variable = {{ name = eu5ab_worker_{counter} add = 1 }}",
            ]
            stage.extend(["\t\t\t}", "\t\t}", "\t\telse = {"])
            lines.extend("\t" * index + line for line in stage)
        lines.append("\t" * (len(gates) + 2) + "eu5ab_try_construct_saved_building_type = yes")
        lines.extend("\t" * (index + 2) + "}" for index in reversed(range(len(gates))))
        return lines

    def lock_candidate_diagnostics_lines() -> list[str]:
        """The serial reducer locks the first deterministic worker result."""
        return []

    def no_legal_candidate_lines() -> list[str]:
        return [
            "\t# Candidate collection already records projects rejected only by the",
            "\t# strict workforce gate, so no second full-domain scan is needed here.",
            "\tif = {",
            "\t\tlimit = {",
            "\t\t\tNOT = { has_variable = eu5ab_had_legal_candidate }",
            "\t\t\thas_variable = eu5ab_had_workforce_blocked_candidate",
            "\t\t}",
            f"\t\tset_variable = {{ name = eu5ab_pending_failure_cooldown value = {rules.failure_cooldowns.workforce} }}",
            "\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_fail_workforce add = 1 }",
            "\t}",
            "\telse_if = {",
            "\t\tlimit = { NOT = { has_variable = eu5ab_had_legal_candidate } NOT = { has_variable = eu5ab_had_capacity_blocked_candidate } }",
            f"\t\tset_variable = {{ name = eu5ab_pending_failure_cooldown value = {rules.failure_cooldowns.no_legal_building} }}",
            "\t\tchange_variable = { name = eu5ab_worker_eu5ab_diag_fail_no_legal add = 1 }",
            "\t}",
            "\tremove_variable = eu5ab_had_workforce_blocked_candidate",
            "\tremove_variable = eu5ab_had_capacity_blocked_candidate",
            "\tremove_variable = eu5ab_had_legal_candidate",
        ]

    # Policy-specific dispatch adapters route every preset and custom slot
    # through one execution chain.
    for policy in policies:
        text = _replace_top_level_script_block(
            text,
            f"eu5ab_try_construct_{policy.id}",
            "\n".join([
                f"eu5ab_try_construct_{policy.id} = {{",
                "\teu5ab_try_construct_current_policy = yes",
                "}",
            ]),
        )
        if policy.auto_build_input_sources:
            text = _replace_top_level_script_block(
                text,
                f"eu5ab_try_construct_{policy.id}_input_source",
                "\n".join([
                    f"eu5ab_try_construct_{policy.id}_input_source = {{",
                    "\teu5ab_try_construct_current_input_source = yes",
                    "}",
                ]),
            )

    for slot in TEMPLATE_SLOTS:
        text = _replace_top_level_script_block(
            text,
            f"eu5ab_try_construct_template_slot_{slot}",
            "\n".join([
                f"eu5ab_try_construct_template_slot_{slot} = {{",
                "\teu5ab_try_construct_current_policy = yes",
                "}",
            ]),
        )

    ordinary_candidate_gates = [
        ("eu5ab_candidate_pending_preliminary_allowed", "eu5ab_diag_fail_pending_output", 0, 9),
        (
            "eu5ab_inputs_available",
            "eu5ab_diag_fail_inputs",
            rules.failure_cooldowns.inputs,
            2,
        ),
        (
            "eu5ab_output_not_oversupplied",
            "eu5ab_diag_fail_oversupply",
            rules.failure_cooldowns.oversupply,
            3,
        ),
    ]

    catalog_size = len(_catalog_building_ids(catalog))

    def active_catalog_name(kind: str, identity: str) -> str:
        # Custom templates use the same allow list for ordinary and upstream
        # collection. Presets may have a wider, input-specific allow list.
        if identity.startswith("template_"):
            kind = "normal"
        return f"eu5ab_active_{kind}_catalog_{identity}"

    def active_catalog_marker(kind: str, identity: str) -> str:
        return active_catalog_name(kind, identity) + "_ready"

    def active_catalog_builder(kind: str, identity: str) -> str:
        return "eu5ab_rebuild_" + active_catalog_name(kind, identity)

    def preset_catalogs(kind: str):
        suffix = "input_source_building_allowed" if kind == "input" else "building_allowed"
        return [(_policy_index(policy, index), f"policy_{_policy_index(policy, index)}",
                 f"eu5ab_{policy.id}_{suffix}") for index, policy in enumerate(policies)]

    def template_catalogs(kind: str):
        return [(slot, f"template_{slot}", f"eu5ab_template_slot_{slot}_building_allowed")
                for slot in TEMPLATE_SLOTS]

    def catalog_rebuild_call(kind: str, identity: str, indent: str) -> list[str]:
        marker = active_catalog_marker(kind, identity)
        return [
            f"{indent}if = {{",
            f"{indent}\tlimit = {{ OR = {{ NOT = {{ has_variable = {marker} }} "
            f"var:{marker}_month != var:eu5ab_scan_month var:{marker}_year != var:eu5ab_scan_year }} }}",
            f"{indent}\t{active_catalog_builder(kind, identity)} = yes",
            f"{indent}}}",
        ]

    def active_catalog_effects() -> list[str]:
        lines = [
            "# Country/template catalogs are rebuilt lazily once per monthly scan.",
            "# Location permission, capacity and workforce remain live per candidate.",
        ]
        for kind in ("normal", "input"):
            catalogs = [*preset_catalogs(kind)]
            if kind == "normal":
                catalogs += template_catalogs(kind)
            for _, identity, allowed in catalogs:
                name = active_catalog_name(kind, identity)
                marker = active_catalog_marker(kind, identity)
                lines += [
                    f"{active_catalog_builder(kind, identity)} = {{",
                    f"\tclear_variable_list = {name}",
                    "\tordered_buildable_building_type = {",
                    f"\t\tmax = {catalog_size}",
                    "\t\tcheck_range_bounds = no",
                    "\t\tlimit = {",
                    f"\t\t\t{allowed} = yes",
                    "\t\t\teu5ab_candidate_is_latest_unlocked = yes",
                    "\t\t}",
                    f"\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner = {{",
                    f"\t\t\tadd_to_variable_list = {{ name = {name} target = prev }}",
                    "\t\t}",
                    "\t}",
                    f"\tset_variable = {{ name = {marker}_month value = var:eu5ab_scan_month }}",
                    f"\tset_variable = {{ name = {marker}_year value = var:eu5ab_scan_year }}",
                    f"\tset_variable = {marker}",
                    "}", "",
                ]
            lines += [f"eu5ab_prepare_current_{kind}_catalog = {{", "\tswitch = {",
                      f"\t\ttrigger = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_policy_id"]
            for value, identity, _ in preset_catalogs(kind):
                lines += [f"\t\t{value} = {{", *catalog_rebuild_call(kind, identity, "\t\t\t"), "\t\t}"]
            lines += [f"\t\t{CUSTOM_POLICY_VALUE} = {{", "\t\t\tswitch = {",
                      f"\t\t\t\ttrigger = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_template_slot"]
            for slot, identity, _ in template_catalogs(kind):
                lines += [f"\t\t\t\t{slot} = {{", *catalog_rebuild_call(kind, identity, "\t\t\t\t\t"),
                          "\t\t\t\t}"]
            lines += ["\t\t\t}", "\t\t}", "\t}", "}", ""]
        lines += [
            "# One location-local union drives native production-method capture.",
            "# It contains active normal/input destinations; the native filter",
            "# separately maps their existing vanilla upgrade predecessors.",
            "eu5ab_prepare_active_recipe_catalog_view = {",
            f"\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
            "\tclear_variable_list = eu5ab_active_recipe_catalog_view",
            "\tremove_variable = eu5ab_active_recipe_catalog_ready",
            "\tremove_variable = eu5ab_active_recipe_catalog_country",
            "\tremove_variable = eu5ab_active_recipe_catalog_month",
            "\tremove_variable = eu5ab_active_recipe_catalog_year",
            "\tif = {",
            "\t\tlimit = {",
            "\t\t\thas_variable = eu5ab_policy_id",
            "\t\t\towner = { has_variable = eu5ab_scan_active has_variable = eu5ab_scan_month has_variable = eu5ab_scan_year eu5ab_scan_month_current = yes }",
            "\t\t}",
            "\t\towner = {",
            "\t\t\teu5ab_prepare_current_normal_catalog = yes",
            *catalog_selection("normal", "eu5ab_active_recipe_catalog_view", "\t\t\t", dedupe=True),
            "\t\t}",
            "\t\tif = {",
            "\t\t\tlimit = { OR = { eu5ab_current_policy_auto_builds_input_sources = yes owner.var:eu5ab_global_fill_market_shortages_when_idle > 0 } }",
            "\t\t\towner = {",
            "\t\t\t\teu5ab_prepare_current_input_catalog = yes",
            *catalog_selection("input", "eu5ab_active_recipe_catalog_view", "\t\t\t\t", dedupe=True),
            "\t\t\t}",
            "\t\t}",
            "\t\tset_variable = { name = eu5ab_active_recipe_catalog_country value = owner }",
            "\t\tset_variable = { name = eu5ab_active_recipe_catalog_month value = owner.var:eu5ab_scan_month }",
            "\t\tset_variable = { name = eu5ab_active_recipe_catalog_year value = owner.var:eu5ab_scan_year }",
            "\t\tset_variable = eu5ab_active_recipe_catalog_ready",
            "\t}",
            "}", "",
        ]
        return lines

    def catalog_copy(
        kind: str,
        identity: str,
        indent: str,
        target_list: str = "eu5ab_active_catalog_view",
        *,
        dedupe: bool = False,
    ) -> list[str]:
        body = [
            f"{indent}every_in_list = {{",
            f"{indent}\tvariable = {active_catalog_name(kind, identity)}",
            f"{indent}\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
        ]
        if dedupe:
            body += [
                f"{indent}\t\tif = {{",
                f"{indent}\t\t\tlimit = {{ NOT = {{ is_target_in_variable_list = {{ name = {target_list} target = prev }} }} }}",
                f"{indent}\t\t\tadd_to_variable_list = {{ name = {target_list} target = prev }}",
                f"{indent}\t\t}}",
            ]
        else:
            body.append(f"{indent}\t\tadd_to_variable_list = {{ name = {target_list} target = prev }}")
        return [*body, f"{indent}\t}}", f"{indent}}}"]

    def catalog_selection(
        kind: str,
        target_list: str,
        indent: str,
        *,
        dedupe: bool = False,
    ) -> list[str]:
        lines = [f"{indent}switch = {{",
                 f"{indent}\ttrigger = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_policy_id"]
        for value, identity, _ in preset_catalogs(kind):
            lines += [f"{indent}\t{value} = {{",
                      *catalog_copy(kind, identity, indent + "\t\t", target_list, dedupe=dedupe),
                      f"{indent}\t}}"]
        lines += [f"{indent}\t{CUSTOM_POLICY_VALUE} = {{", f"{indent}\t\tswitch = {{",
                  f"{indent}\t\t\ttrigger = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_template_slot"]
        for slot, identity, _ in template_catalogs(kind):
            lines += [f"{indent}\t\t\t{slot} = {{",
                      *catalog_copy(kind, identity, indent + "\t\t\t\t", target_list, dedupe=dedupe),
                      f"{indent}\t\t\t}}"]
        return [*lines, f"{indent}\t\t}}", f"{indent}\t}}", f"{indent}}}"]

    def active_catalog_iteration(kind: str, body: list[str]) -> list[str]:
        # Select one persistent country catalog into a location-local view, then
        # execute the candidate body once. Keeping the body outside the policy
        # switch prevents generated-script bloat and preserves a single probe
        # hook for the collection profiler.
        lines = ["\tclear_variable_list = eu5ab_active_catalog_view",
                 "\t# eu5ab_candidate_catalog_native_probe_hook",
                 "\towner = {", f"\t\teu5ab_prepare_current_{kind}_catalog = yes", "\t\tswitch = {",
                 f"\t\t\ttrigger = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_policy_id"]
        for value, identity, _ in preset_catalogs(kind):
            lines += [f"\t\t\t{value} = {{", *catalog_copy(kind, identity, "\t\t\t\t"), "\t\t\t}"]
        lines += [f"\t\t\t{CUSTOM_POLICY_VALUE} = {{", "\t\t\t\tswitch = {",
                  f"\t\t\t\t\ttrigger = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_template_slot"]
        for slot, identity, _ in template_catalogs(kind):
            lines += [f"\t\t\t\t\t{slot} = {{", *catalog_copy(kind, identity, "\t\t\t\t\t\t"),
                      "\t\t\t\t\t}"]
        lines += ["\t\t\t\t}", "\t\t\t}", "\t\t}", "\t}",
                  "\tevery_in_list = {",
                  "\t\tvariable = eu5ab_active_catalog_view",
                  "\t\tlimit = {",
                  "\t\t\teu5ab_current_special_building_allowed = yes",
                  "\t\t}",
                  f"\t\tsave_scope_as = {CANDIDATE_BUILDING_SCOPE}",
                  "\t\teu5ab_prepare_worker_location_eligibility = yes",
                  f"\t\tif = {{ limit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_variable = eu5ab_worker_location_eligible }} }}",
                  *("\t" + line for line in body), "\t\t}", "\t}",
                  "\tremove_variable = eu5ab_worker_location_eligible"]
        return lines

    def current_candidate_pool_lines(
        effect_name: str,
        pools: tuple[str, ...],
        allowed_trigger: str,
        additional_triggers: tuple[str, ...] = (),
        workforce_blocking_triggers: tuple[str, ...] = (),
        reuse_base: bool = False,
    ) -> list[str]:
        """Enumerate once, classify feasible candidates, and remember workforce blocks."""
        if len(pools) != len(CANDIDATE_BUILDING_CLASSES):
            raise ValueError("Candidate pool count must match candidate class count")

        # Capture before food/workforce gates: upstream has separate diagnostics.
        # Only custom slots share the exact ordinary/upstream allow predicate.
        lines = [
            f"\t\t\tsave_scope_as = {CANDIDATE_BUILDING_SCOPE}",
            "\t\t\teu5ab_prepare_candidate_collection_gate = yes",
            *([] if reuse_base else [
                "\t\t\tif = {",
                f"\t\t\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_variable = eu5ab_candidate_base_recording }} }}",
                f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ add_to_variable_list = {{ name = eu5ab_candidate_base_pool target = scope:{CANDIDATE_BUILDING_SCOPE} }} }}",
                "\t\t\t}",
            ]),
            "\t\t\tif = {",
            f"\t\t\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_candidate_collection_gate = 2 }}",
            f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
            "\t\t\t\t\tset_variable = eu5ab_had_capacity_blocked_candidate",
            "\t\t\t\t\tif = { limit = { has_variable = eu5ab_capacity_ready } change_variable = { name = eu5ab_worker_eu5ab_diag_fail_building_capacity add = 1 } }",
            "\t\t\t\t\telse = { change_variable = { name = eu5ab_worker_eu5ab_diag_fail_capacity_unavailable add = 1 } }",
            "\t\t\t\t}",
            "\t\t\t}",
            *(
                line for index, (_, counter) in enumerate(FOOD_BUILDING_GATES)
                for line in (
                    "\t\t\telse_if = {",
                    f"\t\t\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_candidate_collection_gate = {index + 3} }}",
                    f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ change_variable = {{ name = eu5ab_worker_{counter} add = 1 }} }}",
                    "\t\t\t}",
                )
            ),
        ]
        food_lines = lines
        lines = [
            "\t\t\telse = {",
            "\t\t\t\teu5ab_prepare_candidate_workforce = yes",
            "\t\t\t\tif = {",
            f"\t\t\t\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_variable = eu5ab_candidate_workforce_passed }} }}",
            "\t\t\t\t\teu5ab_prepare_worker_screen_upgrades = yes",
        ]
        for index, ((candidate_class, class_trigger), pool) in enumerate(
            zip(CANDIDATE_BUILDING_CLASSES, pools, strict=True)
        ):
            keyword = "if" if index == 0 else "else_if"
            # The preceding upgrade branch already established that this is
            # not a replacement, so only inspect the building at the location.
            if candidate_class == "expansion":
                class_trigger = "eu5ab_candidate_has_existing_building"
            elif candidate_class == "new":
                # Both native and cached paths passed the catalog-only latest
                # and legality switches. After excluding upgrade and existing,
                # every remaining supported candidate is a new construction.
                keyword = "else"
            lines.extend([
                f"\t\t\t\t\t{keyword} = {{",
                *([] if keyword == "else" else [f"\t\t\t\t\t\tlimit = {{ {class_trigger} = yes }}"]),
                f"\t\t\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ add_to_variable_list = {{ name = {pool} target = scope:{CANDIDATE_BUILDING_SCOPE} }} }}",
                "\t\t\t\t\t}",
            ])
        lines.extend([
            "\t\t\t\t}",
            "\t\t\t\telse_if = {",
            "\t\t\t\t\tlimit = {",
            f"\t\t\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_pause_low_workforce > 0",
            f"\t\t\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ NOT = {{ has_variable = eu5ab_had_workforce_blocked_candidate }} }}",
            "\t\t\t\t\t}",
            *(["\t\t\t\t\teu5ab_prepare_worker_screen_inputs = yes"] if workforce_blocking_triggers else []),
            "\t\t\t\t\tif = {",
            "\t\t\t\t\t\tlimit = { eu5ab_inputs_available = yes }",
            *(["\t\t\t\t\t\teu5ab_prepare_worker_screen_prices = yes"]
              if "eu5ab_output_not_oversupplied" in workforce_blocking_triggers else []),
            "\t\t\t\t\t\tif = {",
            f"\t\t\t\t\t\t\tlimit = {{ {' '.join(trigger + ' = yes' for trigger in workforce_blocking_triggers if trigger != 'eu5ab_inputs_available')} }}",
            f"\t\t\t\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ set_variable = eu5ab_had_workforce_blocked_candidate }}",
            "\t\t\t\t\t\t}",
            "\t\t\t\t\t}",
            "\t\t\t\t}",
            "\t\t\t}",
        ])
        lines = food_lines + lines
        if additional_triggers:
            # Effects cannot run in iterator limits. Prepare only the readiness
            # needed by upstream admission, then execute the identical body
            # for the identical surviving types, in the original iterator order.
            lines = [
                f"\t\t\tsave_scope_as = {CANDIDATE_BUILDING_SCOPE}",
                "\t\t\teu5ab_prepare_worker_screen_pending_ready = yes",
                "\t\t\teu5ab_prepare_candidate_upstream_market_cache = yes",
                "\t\t\tif = {",
                f"\t\t\t\tlimit = {{ {' '.join(trigger + ' = yes' for trigger in additional_triggers)} }}",
                *("\t" + line for line in lines), "\t\t\t}",
            ]
        kind = "input" if allowed_trigger == "eu5ab_current_input_source_building_allowed" else "normal"
        native = active_catalog_iteration(kind, lines)
        start = [
            f"{effect_name} = {{",
            f"\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
            *(f"\tclear_variable_list = {pool}" for pool in pools),
        ]
        if reuse_base:
            return [
                *start,
                "\tif = {",
                "\t\tlimit = {",
                "\t\t\thas_variable = eu5ab_scan_promotion_active",
                "\t\t\thas_variable = eu5ab_candidate_base_slot",
                f"\t\t\tvar:eu5ab_policy_id = {CUSTOM_POLICY_VALUE}",
                "\t\t\tvar:eu5ab_template_slot = var:eu5ab_candidate_base_slot",
                "\t\t}",
                "\t\t# eu5ab_candidate_catalog_reuse_probe_hook",
                "\t\tevery_in_list = {",
                "\t\t\tvariable = eu5ab_candidate_base_pool",
                "\t\t\tlimit = {",
                "\t\t\t}", *lines, "\t\t}", "\t}",
                "\telse = {", *("\t" + line for line in native), "\t}",
                "\tremove_variable = eu5ab_candidate_workforce_passed",
                "\tremove_variable = eu5ab_candidate_collection_gate",
                "}", "",
            ]
        return [
            *start,
            "\tclear_variable_map = eu5ab_candidate_collection_gates",
            "\tclear_variable_list = eu5ab_candidate_base_pool",
            "\tremove_variable = eu5ab_candidate_base_slot",
            "\tremove_variable = eu5ab_candidate_base_recording",
            "\tif = {",
            f"\t\tlimit = {{ has_variable = eu5ab_scan_promotion_active var:eu5ab_policy_id = {CUSTOM_POLICY_VALUE} has_variable = eu5ab_template_slot }}",
            "\t\tset_variable = eu5ab_candidate_base_recording",
            "\t}",
            *native,
            "\tif = {",
            "\t\tlimit = { has_variable = eu5ab_candidate_base_recording }",
            "\t\tset_variable = { name = eu5ab_candidate_base_slot value = var:eu5ab_template_slot }",
            "\t}",
            "\tremove_variable = eu5ab_candidate_base_recording",
            "\tremove_variable = eu5ab_candidate_workforce_passed",
            "\tremove_variable = eu5ab_candidate_collection_gate",
            "}", "",
        ]

    def current_feature_candidate_lines(
        effect_name: str,
        pool: str,
        priority_value: str,
        gates: list[tuple[str, str, int, int]],
    ) -> list[str]:
        """Stage the feasible pool; native snapshots rank before final Top-N."""
        return [
            f"{effect_name} = {{",
            f"\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
            f"\tset_variable = {{ name = eu5ab_stage_candidate_priority value = {priority_value} }}",
            "\tevery_in_list = {",
            f"\t\tvariable = {pool}",
            f"\t\tsave_scope_as = {CANDIDATE_BUILDING_SCOPE}",
            f"\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ set_variable = eu5ab_had_legal_candidate change_variable = {{ name = eu5ab_worker_eu5ab_diag_legal_candidates add = 1 }} }}",
            *candidate_gate_lines(gates),
            "\t}",
            "\tremove_variable = eu5ab_stage_candidate_priority",
            "}",
            "",
        ]

    input_candidate_gates = ordinary_candidate_gates

    shared_candidate_lines = [
        *active_catalog_effects(),
        "# Only one synchronous location worker shares these stable gates.",
        "# Nonzero result codes preserve passed/failed state even in old saves",
        "# whose serializer omits zero map values. Diagnostics still run per pool.",
        "eu5ab_prepare_candidate_collection_gate = {",
        f"\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
        "\t\tif = {",
        "\t\t\tlimit = { has_variable = eu5ab_scan_promotion_active",
        f"\t\t\t\tis_key_in_variable_map = {{ name = eu5ab_candidate_collection_gates target = scope:{CANDIDATE_BUILDING_SCOPE} }} }}",
        f'\t\t\tset_variable = {{ name = eu5ab_candidate_collection_gate value = "variable_map(eu5ab_candidate_collection_gates|scope:{CANDIDATE_BUILDING_SCOPE})" }}',
        "\t\t}",
        "\t\telse = {",
        "\t\t\tset_variable = { name = eu5ab_candidate_collection_gate value = 1 }",
        f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{",
        f"\t\t\t\tif = {{ limit = {{ employment_size > 0 scope:{CANDIDATE_LOCATION_SCOPE} = {{ NOT = {{ has_variable = eu5ab_capacity_open }} }} }} eu5ab_prepare_worker_screen_upgrades = yes }}",
        "\t\t\t\tif = { limit = { NOT = { eu5ab_candidate_has_capacity = yes } }",
        f"\t\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ set_variable = {{ name = eu5ab_candidate_collection_gate value = 2 }} }} }}",
        *(line for index, (gate, _) in enumerate(FOOD_BUILDING_GATES) for line in (
            f"\t\t\t\telse_if = {{ limit = {{ NOT = {{ {gate} = yes }} }}",
            f"\t\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ set_variable = {{ name = eu5ab_candidate_collection_gate value = {index + 3} }} }} }}",
        )),
        "\t\t\t}",
        "\t\t\tif = { limit = { has_variable = eu5ab_scan_promotion_active }",
        f"\t\t\t\tadd_to_variable_map = {{ name = eu5ab_candidate_collection_gates key = scope:{CANDIDATE_BUILDING_SCOPE} value = var:eu5ab_candidate_collection_gate }} }}",
        "\t\t}",
        "\t}",
        "}", "",
        "eu5ab_clear_candidate_collection_cache = {",
        "\teu5ab_clear_worker_screening = yes",
        "\tclear_variable_map = eu5ab_candidate_collection_gates",
        "\tremove_variable = eu5ab_candidate_collection_gate",
        "\teu5ab_clear_recipe_score_snapshot = yes",
        "\tclear_variable_list = eu5ab_candidate_base_pool",
        "\tremove_variable = eu5ab_candidate_base_slot",
        "\tremove_variable = eu5ab_candidate_base_recording",
        "\tclear_variable_list = eu5ab_candidate_workforce_checked",
        "\tclear_variable_list = eu5ab_candidate_workforce_passed_types",
        "\tremove_variable = eu5ab_candidate_workforce_passed",
        "\tremove_variable = eu5ab_candidate_required_workers",
        "\tremove_variable = eu5ab_candidate_available_workers",
        "}", "",
        *current_candidate_pool_lines(
            "eu5ab_collect_current_candidate_pools",
            CURRENT_CANDIDATE_POOLS,
            "eu5ab_current_building_allowed",
            workforce_blocking_triggers=(
                "eu5ab_inputs_available",
                "eu5ab_output_not_oversupplied",
            ),
        ),
        *current_candidate_pool_lines(
            "eu5ab_collect_current_input_candidate_pools",
            CURRENT_INPUT_CANDIDATE_POOLS,
            "eu5ab_current_input_source_building_allowed",
            ("eu5ab_upstream_output_shortage_preliminary",),
            ("eu5ab_inputs_available",),
            reuse_base=True,
        ),
        "eu5ab_try_construct_current_policy = {",
        f"\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
        "\teu5ab_clear_candidate_collection_cache = yes",
        "\teu5ab_clear_scan_promotion_cache = yes",
        "\tif = { limit = { has_variable = eu5ab_worker_active } set_variable = eu5ab_worker_screen_active }",
        "\tset_variable = eu5ab_scan_promotion_active",
        "\tremove_variable = eu5ab_scan_preset_origin",
        "\tif = {",
        f"\t\tlimit = {{ var:eu5ab_policy_id = {CUSTOM_POLICY_VALUE} }}",
        "\t\tset_variable = { name = eu5ab_scan_preset_origin value = eu5ab_uncached_preset_origin }",
        "\t}",
        "\tremove_variable = eu5ab_had_legal_candidate",
        "\tremove_variable = eu5ab_had_workforce_blocked_candidate",
        "\teu5ab_collect_current_candidate_pools = yes",
        "\towner = {",
        "\t\tif = {",
        "\t\t\tlimit = { has_variable_list = eu5ab_candidate_priority_features }",
        "\t\t\tsave_scope_as = eu5ab_priority_country",
        "\t\t\tevery_in_list = {",
        "\t\t\t\tvariable = eu5ab_candidate_priority_features",
        "\t\t\t\tsave_scope_as = eu5ab_priority_feature",
        f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
        "\t\t\t\t\tswitch = {",
        "\t\t\t\t\t\ttrigger = scope:eu5ab_priority_feature",
        "\t\t\t\t\t\tflag:eu5ab_feature_upgrade_building = { eu5ab_stage_current_upgrade_candidates = yes }",
        "\t\t\t\t\t\tflag:eu5ab_feature_new_building = { eu5ab_stage_current_new_candidates = yes }",
        "\t\t\t\t\t\tflag:eu5ab_feature_expand_building = { eu5ab_stage_current_expansion_candidates = yes }",
        "\t\t\t\t\t\tflag:eu5ab_feature_expand_rgo = { }",
        "\t\t\t\t\t}",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
        "\t\telse = {",
        f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
        "\t\t\t\teu5ab_stage_current_upgrade_candidates = yes",
        "\t\t\t\teu5ab_stage_current_expansion_candidates = yes",
        "\t\t\t\teu5ab_stage_current_new_candidates = yes",
        "\t\t\t}",
        "\t\t}",
        "\t}",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\tOR = {",
        "\t\t\t\teu5ab_current_policy_auto_builds_input_sources = yes",
        "\t\t\t\t# Optional legacy-style fallback: an otherwise idle location may",
        "\t\t\t\t# search the same constrained pool for a scarce upstream industry.",
        f"\t\t\t\towner.var:{_global_setting_var('fill_market_shortages_when_idle')} > 0",
        "\t\t\t}",
        "\t\t}",
        "\t\teu5ab_try_construct_current_input_source = yes",
        "\t}",
        "\tif = { limit = { has_variable = eu5ab_backfill_country } eu5ab_try_candidate_backfill = yes }",
        *(f"\tclear_variable_list = {pool}" for pool in CURRENT_CANDIDATE_POOLS),
        *lock_candidate_diagnostics_lines(),
        *no_legal_candidate_lines(),
        "\teu5ab_clear_candidate_collection_cache = yes",
        "\teu5ab_clear_scan_promotion_cache = yes",
        "\tremove_variable = eu5ab_scan_preset_origin",
        "}",
        "",
        *current_feature_candidate_lines(
            "eu5ab_stage_current_upgrade_candidates",
            CURRENT_CANDIDATE_POOLS[0],
            f"scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_candidate_priority_upgrade",
            ordinary_candidate_gates,
        ),
        *current_feature_candidate_lines(
            "eu5ab_stage_current_expansion_candidates",
            CURRENT_CANDIDATE_POOLS[1],
            f"scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_candidate_priority_expand",
            ordinary_candidate_gates,
        ),
        *current_feature_candidate_lines(
            "eu5ab_stage_current_new_candidates",
            CURRENT_CANDIDATE_POOLS[2],
            f"scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_candidate_priority_new",
            ordinary_candidate_gates,
        ),
        "eu5ab_try_construct_current_input_source = {",
        "\tset_variable = eu5ab_collecting_supplemental",
        f"\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
        "\teu5ab_collect_current_input_candidate_pools = yes",
        "\towner = {",
        "\t\tif = {",
        "\t\t\tlimit = { has_variable_list = eu5ab_candidate_priority_features }",
        "\t\t\tevery_in_list = {",
        "\t\t\t\tvariable = eu5ab_candidate_priority_features",
        "\t\t\t\tsave_scope_as = eu5ab_priority_feature",
        f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
        "\t\t\t\t\tswitch = {",
        "\t\t\t\t\t\ttrigger = scope:eu5ab_priority_feature",
        "\t\t\t\t\t\tflag:eu5ab_feature_upgrade_building = { eu5ab_stage_current_input_upgrade_candidates = yes }",
        "\t\t\t\t\t\tflag:eu5ab_feature_new_building = { eu5ab_stage_current_input_new_candidates = yes }",
        "\t\t\t\t\t\tflag:eu5ab_feature_expand_building = { eu5ab_stage_current_input_expansion_candidates = yes }",
        "\t\t\t\t\t\tflag:eu5ab_feature_expand_rgo = { }",
        "\t\t\t\t\t}",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
        "\t\telse = {",
        f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
        "\t\t\t\teu5ab_stage_current_input_upgrade_candidates = yes",
        "\t\t\t\teu5ab_stage_current_input_expansion_candidates = yes",
        "\t\t\t\teu5ab_stage_current_input_new_candidates = yes",
        "\t\t\t}",
        "\t\t}",
        "\t}",
        "\tremove_variable = eu5ab_collecting_supplemental",
        *(f"\tclear_variable_list = {pool}" for pool in CURRENT_INPUT_CANDIDATE_POOLS),
        *lock_candidate_diagnostics_lines(),
        "}",
        "",
        *current_feature_candidate_lines(
            "eu5ab_stage_current_input_upgrade_candidates",
            CURRENT_INPUT_CANDIDATE_POOLS[0],
            f"scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_candidate_priority_upgrade",
            input_candidate_gates,
        ),
        *current_feature_candidate_lines(
            "eu5ab_stage_current_input_expansion_candidates",
            CURRENT_INPUT_CANDIDATE_POOLS[1],
            f"scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_candidate_priority_expand",
            input_candidate_gates,
        ),
        *current_feature_candidate_lines(
            "eu5ab_stage_current_input_new_candidates",
            CURRENT_INPUT_CANDIDATE_POOLS[2],
            f"scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_candidate_priority_new",
            input_candidate_gates,
        ),
    ]
    text = text.rstrip() + "\n\n" + "\n".join(shared_candidate_lines) + "\n" + candidate_backfill.render_effects(
        planning_default=rules.cadence.candidates_per_location,
        profit_default=rules.cadence.actual_profit_candidates_per_location,
    )

    rgo_lines = [
        "eu5ab_try_construct_rgo_need = {",
        "\tif = {",
        "\t\tlimit = { owner = { eu5ab_queue_calendar_open = yes } eu5ab_rgo_expansion_allowed = yes }",
        "\t\tset_variable = { name = eu5ab_queue_before_attempt value = num_civil_constructions }",
        "\t\teu5ab_capture_rgo_start_output = yes",
        "\t\t# Capture the native payment for budget settlement.",
        "\t\tset_local_variable = { name = eu5ab_rgo_paid_cost value = owner.gold }",
        "\t\tconstruct_rgo_upgrade = { }",
        "\t\tchange_local_variable = { name = eu5ab_rgo_paid_cost subtract = owner.gold }",
        "\t\tif = {",
        "\t\t\t# The native effect can reject hidden vanilla constraints; charge only on success.",
        "\t\t\tlimit = { num_civil_constructions > eu5ab_queue_before_attempt_value }",
        "\t\t\tremove_variable = eu5ab_failure_cooldown",
        "\t\t\teu5ab_record_queue_start_location = yes",
        "\t\t\teu5ab_record_rgo_start = yes",
        "\t\t\tset_variable = eu5ab_action_taken",
        "\t\t\tset_variable = eu5ab_active_rgo_construction",
        "\t\t\towner = {",
        f"\t\t\t\tif = {{ limit = {{ NOT = {{ is_target_in_variable_list = {{ name = eu5ab_active_project_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }} }} add_to_variable_list = {{ name = eu5ab_active_project_locations target = scope:{CANDIDATE_LOCATION_SCOPE} }} }}",
        "\t\t\t" + _increment_runtime_counter("eu5ab_diag_active_mod_projects"),
        "\t\t\t\t" + _increment_runtime_counter("eu5ab_constructions_started_this_tick"),
        "\t\t\t\t" + _increment_runtime_counter("eu5ab_rgo_started_this_tick"),
        "\t\t\t\tset_variable = { name = eu5ab_diag_built_this_run value = 1 }",
        f"\t\t\t\tset_variable = {{ name = eu5ab_diag_last_build_location value = scope:{CANDIDATE_LOCATION_SCOPE} }}",
        "\t\t\t\tset_variable = { name = eu5ab_diag_last_build_kind value = 1 }",
        "\t\t\t}",
        "\t\t\towner = {",
        "\t\t\t\t# Gold is charged by the native effect. Only settle the internal budget here.",
        "\t\t\t\t# Unexpected negative cash movement must never refund the budget.",
        "\t\t\t\tif = {",
        "\t\t\t\t\tlimit = { local_var:eu5ab_rgo_paid_cost >= 0 }",
        "\t\t\t\t\tset_local_variable = { name = eu5ab_budget_charge value = local_var:eu5ab_rgo_paid_cost }",
        "\t\t\t\t\teu5ab_charge_annual_budget = yes",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
        "\t\telse = {",
        "\t\t\towner = { change_variable = { name = eu5ab_diag_fail_vanilla add = 1 } }",
        "\t\t}",
        "\t\tremove_variable = eu5ab_queue_before_attempt",
        "\t\tremove_local_variable = eu5ab_rgo_paid_cost",
        "\t\tremove_variable = eu5ab_rgo_start_output",
        "\t\tremove_variable = eu5ab_rgo_start_level",
        "\t\tremove_variable = eu5ab_rgo_start_queue",
        "\t\tremove_variable = eu5ab_rgo_start_queue_known",
        "\t}",
        "}",
    ]
    text = monthly_schedule.guard_effects("\n\n".join(
        part.rstrip()
        for part in (
            text,
            "\n".join(rgo_lines),
            rgo_automation.render_effects(),
            rgo_pending.render_effects(),
            rgo_queue.render_effects(),
            rgo_automation.render_live_queue_effect(len(CANDIDATE_PRIORITY_FEATURES) * 2),
            render_construction_material_effects(construction_demands),
            render_engine_queue_effects(policies, rules),
            queue_script_dispatch.render_effects(len(CANDIDATE_PRIORITY_FEATURES) * 2),
            queue_script_dispatch.render_control_effects(CMM_CANDIDATE_RANKING_ACTUAL_PROFIT),
            template_coverage.render_effects(),
            render_runtime_recovery_effects(),
        )
    ) + "\n", _replace_top_level_script_block)
    text = queue_bridge.apply_effects(text, _replace_top_level_script_block,
        len(CANDIDATE_PRIORITY_FEATURES) * 4, len(CANDIDATE_PRIORITY_FEATURES) * 2)
    text = quote_cache.apply_effects(text, _replace_top_level_script_block, queue_bridge._block)
    return winner_batch.apply_effects(text) + winner_batch.render_effects(rules)


def _all_special_buildings(catalog: BuildingCatalog) -> tuple[str, ...]:
    return tuple(
        building.id
        for building in catalog.buildings.values()
        if building.is_special
    )


def _policy_buildings(policy: Policy, catalog: BuildingCatalog) -> tuple[str, ...]:
    ids = set(policy.allowed_buildings) | set(policy.banned_buildings)
    if policy.auto_build_input_sources:
        for good in policy.priority_goods:
            ids.update(catalog.source_buildings_by_good.get(good, ()))
        for building_ids in catalog.source_buildings_by_good.values():
            ids.update(building_ids)
    return tuple(sorted(ids))


def _source_building_ids(
    policy: Policy,
    catalog: BuildingCatalog,
    rules: AutomationRules,
) -> tuple[str, ...]:
    ids: set[str] = set()
    for building_ids in catalog.source_buildings_by_good.values():
        ids.update(building_ids)
    ids.difference_update(policy.banned_buildings)
    ids = {
        building_id
        for building_id in ids
        if rules.building_priority_for(building_id) > rules.building_priorities.minimum
    }
    return tuple(sorted(ids))


def _catalog_building_ids(catalog: BuildingCatalog) -> tuple[str, ...]:
    # Governor buildings are recommendation-only.  Keeping them out of this
    # central list prevents template defaults, editor rows, candidate triggers,
    # and runtime scoring from reintroducing automatic construction even when a
    # user raises a legacy saved priority.
    return tuple(
        sorted(set(catalog.buildings) - GOVERNOR_RECOMMENDATION_BUILDINGS)
    )


def _supporting_building_ids(goods: tuple[str, ...] | list[str] | set[str], catalog: BuildingCatalog) -> tuple[str, ...]:
    wanted = set(goods)
    return tuple(
        sorted(
            building.id
            for building in catalog.buildings.values()
            if wanted.intersection(building.output_goods)
        )
    )


def _support_trigger_lines(
    goods: tuple[str, ...] | list[str] | set[str],
    catalog: BuildingCatalog,
    indent: str,
    building_id: str | None = None,
    recipes: dict[str, BuildingProduction] | None = None,
) -> list[str]:
    if building_id is not None and recipes is not None:
        model = recipes.get(building_id)
        choices = [f"eu5ab_recipe_{building_id}_{slot_index}_selected = {method_index}"
                   for slot_index, slot in enumerate(model.slots if model else ())
                   for method_index, method in enumerate(slot, 1)
                   if set(goods).intersection(method.outputs)]
        for good in sorted(set(goods).intersection(RGO_BOOST_GOODS.get(building_id, ()))):
            choices.append(f"scope:{CANDIDATE_LOCATION_SCOPE} = {{ raw_material_output > 0 raw_material = goods:{good} }}")
        return [f"{indent}OR = {{ {' '.join(choices)} }}"] if choices else [f"{indent}always = no"]
    return [f"{indent}OR = {{ " + " ".join(f"eu5ab_output_supports_{g} = yes" for g in sorted(set(goods))) + " }"]


def _food_support_trigger_lines(
    catalog: BuildingCatalog, rules: AutomationRules, indent: str,
    building_id: str | None = None,
    recipes: dict[str, BuildingProduction] | None = None,
) -> list[str]:
    """Food modifiers support reserves, but are not traded-goods producers."""
    if building_id is not None:
        if building_id == "irrigation_systems" and catalog.get(building_id) is not None:
            return [f"{indent}always = yes"]
        return _support_trigger_lines(rules.food_goods, catalog, indent, building_id, recipes)
    producers = _support_trigger_lines(tuple(sorted(rules.food_goods)), catalog, indent + "\t")
    return [
        f"{indent}OR = {{",
        *producers,
        *([f"{indent}\tthis = building_type:irrigation_systems"]
          if catalog.get("irrigation_systems") is not None else []),
        f"{indent}}}",
    ]


def render_irrigation_triggers(rules: AutomationRules) -> str:
    """Gate irrigation using native food reserves and population capacity."""
    thresholds = rules.thresholds
    return f"""# Location scope. Demand is independent of emergency priority switches.
eu5ab_irrigation_food_demand = {{
\texists = market
\tmarket = {{
\t\tOR = {{
\t\t\tis_projected_to_run_out_of_food_stockpile = yes
\t\t\tmarket_food_percentage <= {thresholds.food_emergency_ratio:g}
\t\t\tAND = {{
\t\t\t\tmarket_food_percentage <= {thresholds.food_low_ratio:g}
\t\t\t\tmarket_monthly_food_balance < 0
\t\t\t}}
\t\t}}
\t}}
}}

eu5ab_irrigation_population_demand = {{
\t# Guard undefined/zero capacity before reading the native fraction.
\tlocation_max_population > 0
\tlocation_population_percentage >= {thresholds.irrigation_population_capacity_ratio:g}
}}

# Building-type scope. Other buildings retain their existing eligibility rules.
eu5ab_candidate_has_irrigation_demand = {{
\tOR = {{
\t\tNOT = {{ this = building_type:irrigation_systems }}
\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{
\t\t\tOR = {{
\t\t\t\teu5ab_irrigation_population_demand = yes
\t\t\t\teu5ab_irrigation_food_demand = yes
\t\t\t}}
\t\t}}
\t}}
}}
"""


def _consuming_building_ids(
    goods: tuple[str, ...] | list[str] | set[str],
    catalog: BuildingCatalog,
) -> tuple[str, ...]:
    ids: set[str] = set()
    for good in goods:
        ids.update(catalog.consumer_buildings_by_good.get(good, ()))
    return tuple(sorted(ids))


def _consumer_trigger_lines(
    goods: tuple[str, ...] | list[str] | set[str],
    catalog: BuildingCatalog,
    indent: str,
) -> list[str]:
    building_ids = _consuming_building_ids(goods, catalog)
    if not building_ids:
        return [f"{indent}always = no"]
    return [
        f"{indent}OR = {{",
        *(f"{indent}\tthis = building_type:{building_id}" for building_id in building_ids),
        f"{indent}}}",
    ]


def _market_supply_condition_lines(
    good: str,
    ratio: float,
    indent: str,
    location_scope: str = f"scope:{CANDIDATE_LOCATION_SCOPE}",
) -> list[str]:
    scope_prefix = f"{location_scope}." if location_scope else ""
    return [
        f"{indent}{scope_prefix}market ?= {{",
        f'{indent}\t"goods_supply_in_market(goods:{good})" < {{',
        f'{indent}\t\tvalue = "goods_demand_in_market(goods:{good})"',
        f"{indent}\t\tmultiply = {ratio}",
        f"{indent}\t}}",
        f"{indent}}}",
    ]


def _market_high_price_condition_lines(
    good: str,
    ratio: float,
    indent: str,
    location_scope: str = f"scope:{CANDIDATE_LOCATION_SCOPE}",
) -> list[str]:
    scope_prefix = f"{location_scope}." if location_scope else ""
    return [
        f"{indent}{scope_prefix}market ?= {{",
        f'{indent}\t"market_price(goods:{good})" > {{',
        f'{indent}\t\tvalue = "default_price(goods:{good})"',
        f"{indent}\t\tmultiply = {ratio}",
        f"{indent}\t}}",
        f"{indent}}}",
    ]


def _upstream_output_shortage_condition_lines(
    catalog: BuildingCatalog,
    rules: AutomationRules,
    indent: str,
    recipe_recovery: bool = False,
    building_id: str | None = None,
    recipes: dict[str, BuildingProduction] | None = None,
    market_cache: bool = False,
) -> list[str]:
    goods = tuple(sorted(rules.input_goods & catalog.source_buildings_by_good.keys()))
    outputs = {}
    if building_id is not None:
        model = (recipes or {}).get(building_id)
        for slot_index, slot in enumerate(model.slots if model else ()):
            for method_index, method in enumerate(slot, 1):
                for good in method.outputs:
                    outputs.setdefault(good, []).append(
                        f"eu5ab_recipe_{building_id}_{slot_index}_selected = {method_index}")
        goods = tuple(good for good in goods if good in outputs)
    if not goods:
        return [f"{indent}always = no"]
    lines = [f"{indent}OR = {{"]
    for good in goods:
        lines.append(f"{indent}\tAND = {{")
        if building_id is None:
            lines.append(f"{indent}\t\teu5ab_recipe_produces_{good} = yes")
        elif recipe_recovery:
            from .production import guaranteed_output_condition
            # The guarantee includes the selected-output check. Evaluate it
            # once, without redispatching across every producer of this good.
            lines.append(f"{indent}\t\t{guaranteed_output_condition(building_id, model, good)}")
        else:
            lines.extend([f"{indent}\t\tOR = {{",
                          *(f"{indent}\t\t\t{condition}" for condition in outputs[good]),
                          f"{indent}\t\t}}"])
        if recipe_recovery and market_cache:
            if building_id is None:
                lines.append(f"{indent}\t\teu5ab_recipe_guarantees_{good} = yes")
            lines.append(f"{indent}\t\teu5ab_market_upstream_shortage_{good} = yes")
            lines.append(f"{indent}\t}}")
            continue
        if recipe_recovery:
            if building_id is None:
                lines.append(f"{indent}\t\teu5ab_recipe_guarantees_{good} = yes")
            lines.append(f"{indent}\t\teu5ab_market_needs_{good} = yes")
        lines.append(f"{indent}\t\tOR = {{")
        if recipe_recovery:
            lines.extend([
                f"{indent}\t\t\tAND = {{",
                f"{indent}\t\t\t\teu5ab_market_effective_demand_{good} > 0",
                f'{indent}\t\t\t\t"scope:{CANDIDATE_LOCATION_SCOPE}.market.goods_supply_in_market(goods:{good})" < {{ value = eu5ab_market_effective_demand_{good} multiply = {rules.thresholds.goods_shortage_supply_ratio} }}',
                f"{indent}\t\t\t}}",
            ])
        else:
            lines.extend(_market_supply_condition_lines(
                good, rules.thresholds.goods_shortage_supply_ratio, f"{indent}\t\t\t",
            ))
        if recipe_recovery:
            lines.extend([
                f'{indent}\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.market = {{',
                f'{indent}\t\t\t\t"market_price(goods:{good})" > {{ value = "default_price(goods:{good})" multiply = eu5ab_global_price_max_ratio }}',
                f'{indent}\t\t\t}}',
            ])
        lines.extend([f"{indent}\t\t}}", f"{indent}\t}}"])
    lines.append(f"{indent}}}")
    return lines


def _universal_need_score_lines(
    catalog: BuildingCatalog, rules: AutomationRules,
    building_id: str | None = None,
    recipes: dict[str, BuildingProduction] | None = None,
) -> list[str]:
    lines: list[str] = []
    thresholds = rules.thresholds
    scores = rules.scores
    food_goods = tuple(sorted(rules.food_goods))
    food_support = _food_support_trigger_lines(catalog, rules, "\t\t\t", building_id, recipes)
    food_supported = building_id is None or food_support != ["\t\t\talways = no"]

    food_cases = [
        (
            "if",
            [
                f"scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:{_global_setting_var('emergency_food_exhaustion_override')} > 0",
                f"scope:{CANDIDATE_LOCATION_SCOPE}.market ?= {{",
                "\tis_projected_to_run_out_of_food_stockpile = yes",
                "}",
            ],
            scores.food_projected_exhaustion,
        ),
        (
            "else_if",
            [
                f"scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:{_global_setting_var('emergency_food_stockpile_override')} > 0",
                f"scope:{CANDIDATE_LOCATION_SCOPE}.market ?= {{",
                f"\tmarket_food_percentage <= {thresholds.food_emergency_ratio}",
                "}",
            ],
            scores.food_emergency,
        ),
        (
            "else_if",
            [f"scope:{CANDIDATE_LOCATION_SCOPE}.market ?= {{", f"\tmarket_food_percentage <= {thresholds.food_low_ratio}", "}"],
            scores.food_low,
        ),
    ]
    for keyword, market_condition, score in food_cases if food_supported else ():
        lines.extend([f"\t{keyword} = {{", "\t\tlimit = {"])
        lines.extend(food_support)
        lines.extend(f"\t\t\t{item}" for item in market_condition)
        lines.extend(["\t\t}", f"\t\tadd = {score}", "\t}"])
    if food_supported:
        lines.extend(["\tif = {", "\t\tlimit = {", *food_support,
                      f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.market ?= {{ market_monthly_food_balance < 0 }}",
                      "\t\t}", f"\t\tadd = {scores.food_negative_balance}", "\t}"])

    score_groups = [
        (
            rules.goods_groups["construction_core"] + rules.goods_groups["construction_secondary"],
            scores.critical_construction_good,
            scores.short_construction_good,
        ),
        (
            rules.goods_groups["population_basic"],
            scores.critical_population_good,
            scores.short_population_good,
        ),
        (
            rules.goods_groups["military"],
            scores.critical_military_good,
            scores.short_military_good,
        ),
    ]
    covered_goods = set().union(*(set(group) for group, _, _ in score_groups)) | set(food_goods)
    generic_goods = tuple(sorted(rules.essential_goods - covered_goods))
    if generic_goods:
        score_groups.append((generic_goods, scores.critical_generic_good, scores.short_generic_good))

    for goods, critical_score, shortage_score in score_groups:
        for good in sorted(set(goods)):
            support = _support_trigger_lines((good,), catalog, "\t\t\t", building_id, recipes)
            if building_id is not None and support == ["\t\t\talways = no"]:
                continue
            lines.extend(["\tif = {", "\t\tlimit = {"])
            lines.extend(support)
            lines.extend(_market_supply_condition_lines(good, thresholds.goods_critical_supply_ratio, "\t\t\t"))
            lines.extend(["\t\t}", f"\t\tadd = {critical_score}", "\t}"])
            lines.extend(["\telse_if = {", "\t\tlimit = {"])
            lines.extend(support)
            lines.extend(_market_supply_condition_lines(good, thresholds.goods_shortage_supply_ratio, "\t\t\t"))
            lines.extend([
                "\t\t}",
                f"\t\tadd = {shortage_score}",
                "\t}",
            ])

    military_support = _support_trigger_lines(rules.goods_groups["military"], catalog, "\t\t\t", building_id, recipes)
    if building_id is None or military_support != ["\t\t\talways = no"]:
        lines.extend(["\tif = {", "\t\tlimit = {", f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner = {{ at_war = yes }}",
                      *military_support, "\t\t}", f"\t\tadd = {scores.wartime_military_bonus}", "\t}"])

    # Upstream producers are strategic only while their output is actually scarce.
    # This makes the fallback deterministic without turning every raw producer into
    # a permanent high-priority candidate.
    upstream_support = _upstream_output_shortage_condition_lines(
        catalog, rules, "\t\t\t", building_id=building_id, recipes=recipes)
    if building_id is None or upstream_support != ["\t\t\talways = no"]:
        lines.extend(["\tif = {", "\t\tlimit = {", *upstream_support,
                      "\t\t}", f"\t\tadd = {scores.upstream_source_bonus}", "\t}"])

    lines.extend([
        "\tif = {",
        "\t\tlimit = { eu5ab_candidate_scoring_input_shortage = yes }",
        f"\t\tadd = {scores.input_shortage_penalty}",
        "\t}",
    ])
    lines.extend([
        "\tif = {",
        "\t\tlimit = { eu5ab_candidate_replaces_existing_building = yes }",
        f"\t\tadd = {thresholds.upgrade_replacement_bonus}",
        "\t}",
    ])
    # Only an ordinary expansion receives its own existing-level bonus.
    # A destination replacing another identity does not inherit either scale.
    lines.extend([
        "\tif = {",
        "\t\tlimit = { NOT = { eu5ab_candidate_replaces_existing_building = yes } }",
    ])
    if building_id is not None:
        lines.extend(["\t\tadd = {",
                      f'\t\t\tvalue = "scope:{CANDIDATE_LOCATION_SCOPE}.location_building_level(building_type:{building_id})"',
                      f"\t\t\tmultiply = {thresholds.expansion_bonus_per_level}", "\t\t}", "\t}"])
        return lines
    for index, building_id in enumerate(_catalog_building_ids(catalog)):
        lines.extend([
            "\t\tif = {" if index == 0 else "\t\telse_if = {",
            f"\t\t\tlimit = {{ this = building_type:{building_id} }}",
            "\t\t\tadd = {",
            f'\t\t\t\tvalue = "scope:{CANDIDATE_LOCATION_SCOPE}.location_building_level(building_type:{building_id})"',
            f"\t\t\t\tmultiply = {thresholds.expansion_bonus_per_level}",
            "\t\t\t}",
            "\t\t}",
        ])
    lines.append("\t}")
    return lines


def _building_name_key(building_id: str) -> str:
    return f"eu5ab_building_{building_id}"


def _building_localization_key(building_id: str, catalog: BuildingCatalog) -> str:
    definition = catalog.get(building_id)
    if definition is None or not definition.localization_key:
        raise ValueError(f"Building {building_id} is missing localization_key")
    return definition.localization_key


def _slot_var(slot: int, suffix: str) -> str:
    return f"eu5ab_tpl_{slot}_{suffix}"


def _building_priority_var(building_id: str, slot: int) -> str:
    return _slot_var(slot, f"priority_building_{building_id}")


def _slot_priority_map(slot: int) -> str:
    return _slot_var(slot, "building_priorities")


def _preset_paused_var(policy_id: str) -> str:
    return f"eu5ab_preset_{policy_id}_paused"


def _editor_var(suffix: str) -> str:
    return f"eu5ab_edit_{suffix}"


def _editor_priority_var(building_id: str) -> str:
    return _editor_var(f"priority_building_{building_id}")


def _location_allow_var(building_id: str) -> str:
    return f"eu5ab_allow_building_{building_id}"


def _location_ban_var(building_id: str) -> str:
    return f"eu5ab_ban_building_{building_id}"


def _clear_location_policy_lines(indent: str = "") -> list[str]:
    """Remove every location-level setting owned by this mod."""
    return [
        f"{indent}eu5ab_unregister_location_from_scan = yes",
        f"{indent}remove_variable = eu5ab_policy_id",
        f"{indent}remove_variable = eu5ab_template_slot",
        f"{indent}remove_variable = eu5ab_policy_decoupled",
    ]


def render_scripted_triggers(policies: list[Policy], catalog: BuildingCatalog, rules: AutomationRules) -> str:
    chunks = ["# Generated by eu5autobuild.generator."]
    special_buildings = _all_special_buildings(catalog)
    chunks.extend([
        "eu5ab_location_template_not_paused = {",
        "\tNOT = {",
        "\t\tOR = {",
    ])
    for index, policy in enumerate(policies):
        chunks.extend([
            "\t\t\tAND = {",
            f"\t\t\t\tvar:eu5ab_policy_id = {_policy_index(policy, index)}",
            f"\t\t\t\towner = {{ has_variable = {_preset_paused_var(policy.id)} }}",
            "\t\t\t}",
        ])
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            "\t\t\tAND = {",
            f"\t\t\t\tvar:eu5ab_template_slot = {slot}",
            f"\t\t\t\towner = {{ has_variable = {_slot_var(slot, 'paused')} }}",
            "\t\t\t}",
        ])
    chunks.extend([
        "\t\t}",
        "\t}",
        "}",
        "",
    ])
    for policy in policies:
        chunks.extend([
            f"eu5ab_{policy.id}_building_allowed = {{",
            "\t# Rule order: banned buildings are checked before allowlist membership.",
        ])
        if policy.banned_buildings:
            chunks.append("\tNOT = {")
            chunks.append("\t\tOR = {")
            for building in policy.banned_buildings:
                chunks.append(f"\t\t\tthis = building_type:{building}")
            chunks.append("\t\t}")
            chunks.append("\t}")
        if policy.allowed_buildings:
            # A preset allowlist is an explicit policy decision and therefore
            # overrides the global building-quality fallback, including score 0.
            # Custom templates still use their per-slot priority 0 as a hard ban.
            chunks.append("\tOR = {")
            for building in policy.allowed_buildings:
                chunks.append(f"\t\tthis = building_type:{building}")
            chunks.append("\t}")
        else:
            chunks.append("\talways = yes")
        chunks.extend([
            "}",
            "",
            f"eu5ab_{policy.id}_special_building_allowed = {{",
        ])
        if not special_buildings:
            chunks.append("\talways = yes")
        else:
            chunks.append("\tOR = {")
            chunks.append(f"\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_allow_special_buildings > 0")
            chunks.append("\t\tNOT = {")
            chunks.append("\t\t\tOR = {")
            for building in special_buildings:
                chunks.append(f"\t\t\t\tthis = building_type:{building}")
            chunks.append("\t\t\t}")
            chunks.append("\t\t}")
            chunks.append("\t}")
        chunks.extend([
            "}",
            "",
            f"eu5ab_{policy.id}_has_local_workforce = {{",
            "\t# Building type -> local pop class gate. A location must still have",
            "\t# at least one matching pop class before auto construction or upgrade.",
        ])
        workforce_checks: list[str] = []
        for building_id in _policy_buildings(policy, catalog):
            definition = catalog.get(building_id)
            if definition is None or not definition.workforce_pop_types:
                continue
            workforce_checks.append(building_id)
        if workforce_checks:
            chunks.append("\tOR = {")
            for building_id in workforce_checks:
                definition = catalog.get(building_id)
                if definition is None:
                    raise ValueError(f"Missing catalog definition for {building_id}")
                chunks.append("\t\tAND = {")
                chunks.append(f"\t\t\tthis = building_type:{building_id}")
                chunks.append("\t\t\tOR = {")
                for pop_type in definition.workforce_pop_types:
                    chunks.append(f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.num_pop_type:{pop_type} > 0.001")
                chunks.append("\t\t\t}")
                chunks.append("\t\t}")
            chunks.append("\t}")
        else:
            chunks.append("\talways = yes")
        chunks.extend([
            "}",
            "",
            f"eu5ab_{policy.id}_input_source_building_allowed = {{",
        ])
        source_ids = _source_building_ids(policy, catalog, rules)
        if source_ids:
            if policy.banned_buildings:
                chunks.append("\tNOT = {")
                chunks.append("\t\tOR = {")
                for building in policy.banned_buildings:
                    chunks.append(f"\t\t\tthis = building_type:{building}")
                chunks.append("\t\t}")
                chunks.append("\t}")
            chunks.append("\tOR = {")
            for building_id in source_ids:
                chunks.append(f"\t\tthis = building_type:{building_id}")
            chunks.append("\t}")
        else:
            chunks.append("\talways = no")
        chunks.extend([
            "}",
            "",
            f"eu5ab_{policy.id}_has_input_materials = {{",
            "\t# Material-shortage handling remains disabled until the game exposes",
            "\t# a stable building_type -> goods market scope combination.",
            "\talways = yes",
            "}",
            "",
            f"eu5ab_{policy.id}_price_in_range = {{",
            "\t# Shared CMM price gates are applied by the common candidate checks.",
            "\talways = yes",
            "}",
            "",
            f"eu5ab_{policy.id}_has_budget = {{",
            f"\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_budget_remaining >= building_base_cost_in_gold",
            "}",
            "",
            f"eu5ab_{policy.id}_keeps_cash_reserve = {{",
            f"\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.gold >= eu5ab_cash_required_{policy.id}",
            "}",
            "",
        ])
    building_ids = _catalog_building_ids(catalog)
    special_buildings = _all_special_buildings(catalog)
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            f"eu5ab_template_slot_{slot}_building_allowed = {{",
            f"\tscope:{CANDIDATE_LOCATION_SCOPE}.owner = {{",
            f"\t\thas_variable_map = {_slot_priority_map(slot)}",
            f"\t\tis_key_in_variable_map = {{ name = {_slot_priority_map(slot)} target = prev }}",
            "\t}",
            "}",
            "",
            f"eu5ab_template_slot_{slot}_special_building_allowed = {{",
        ])
        if special_buildings:
            chunks.append("\tOR = {")
            chunks.append(f"\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_allow_special_buildings > 0")
            chunks.append("\t\tNOT = {")
            chunks.append("\t\t\tOR = {")
            for building_id in special_buildings:
                chunks.append(f"\t\t\t\tthis = building_type:{building_id}")
            chunks.append("\t\t\t}")
            chunks.append("\t\t}")
            chunks.append("\t}")
        else:
            chunks.append("\talways = yes")
        chunks.extend([
            "}",
            "",
            f"eu5ab_template_slot_{slot}_has_local_workforce = {{",
            "\tOR = {",
            f"\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_pause_low_workforce <= 0",
        ])
        for building_id in building_ids:
            definition = catalog.get(building_id)
            if definition is None or not definition.workforce_pop_types:
                continue
            chunks.append("\t\tAND = {")
            chunks.append(f"\t\t\tthis = building_type:{building_id}")
            chunks.append("\t\t\tOR = {")
            for pop_type in definition.workforce_pop_types:
                chunks.append(f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.num_pop_type:{pop_type} > 0.001")
            chunks.append("\t\t\t}")
            chunks.append("\t\t}")
        chunks.extend([
            "\t}",
            "}",
            "",
            f"eu5ab_template_slot_{slot}_has_input_materials = {{",
            "\t# The shared CMM shortage gate is applied by the common candidate checks.",
            "\talways = yes",
            "}",
            "",
            f"eu5ab_template_slot_{slot}_price_in_range = {{",
            "\t# Shared CMM price gates are applied by the common candidate checks.",
            "\talways = yes",
            "}",
            "",
            f"eu5ab_template_slot_{slot}_keeps_cash_reserve = {{",
            f"\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.gold >= eu5ab_cash_required_template_slot_{slot}",
            "}",
            "",
            f"eu5ab_template_slot_{slot}_has_budget = {{",
            f"\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_budget_remaining >= building_base_cost_in_gold",
            "}",
            "",
        ])
    return "\n".join(chunks)


def render_needs_scripted_triggers(
    policies: list[Policy],
    catalog: BuildingCatalog,
    rules: AutomationRules,
    upgrades: BuildingUpgradeData,
    construction_demands: dict[str, ConstructionDemand],
    recipes: dict[str, BuildingProduction] | None = None,
) -> str:
    def replacement_body(building_id: str, *, capacity: bool = False) -> list[str]:
        predecessors = upgrades.predecessors.get(building_id, ())
        if not predecessors:
            return ["always = no"]
        # This branch already knows the destination. Filter cheap type facts
        # before asking native upgrade permission for an existing building.
        return [
            f"scope:{CANDIDATE_LOCATION_SCOPE} = {{",
            "\tany_buildings_in_location = {",
            "\t\tOR = {",
            *(f"\t\t\tbuilding_type = building_type:{predecessor}" for predecessor in predecessors),
            "\t\t}",
            "\t\tbuilding_level >= 1",
            "\t\teu5ab_upgrade_source_available = yes",
            *(["\t\tbuilding_type = { employment_size > 0 }"] if capacity else []),
            f"\t\tbuilding_can_be_upgraded_by = scope:{CANDIDATE_LOCATION_SCOPE}.owner",
            "\t}", "}",
        ]

    latest_unlocked_lines = [
        "# Keep only the newest vanilla replacement currently unlocked by the owner.",
        "# Building identities are mutually exclusive, so switch avoids walking the full catalog.",
        "eu5ab_candidate_is_latest_unlocked = {",
        "\tswitch = {",
        "\t\ttrigger = this",
    ]
    base_candidate_lines = [
        "# Country permission is established first. Vanilla's location_and_owner_can_build",
        "# repeats that same country query; only its location query remains necessary here.",
        "eu5ab_candidate_base_eligible = {", "\tswitch = {", "\t\ttrigger = this",
    ]
    location_candidate_lines = [
        "# The active monthly catalog already established country permission and successor exclusion.",
        "eu5ab_candidate_location_eligible = {", "\tswitch = {", "\t\ttrigger = this",
    ]
    for building_id in _catalog_building_ids(catalog):
        case = [
            f"\t\tbuilding_type:{building_id} = {{",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner = {{",
            f"\t\t\t\tcan_build_building = building_type:{building_id}",
        ]
        successors = upgrades.successors.get(building_id, ())
        if successors:
            case.append("\t\t\t\tNOR = {")
            case.extend(
                f"\t\t\t\t\tcan_build_building = building_type:{successor}"
                for successor in successors
            )
            case.append("\t\t\t\t}")
        case.append("\t\t\t}")
        latest_unlocked_lines.extend([*case, "\t\t}"])
        base_candidate_lines.extend(case)
        legal = f"scope:{CANDIDATE_LOCATION_SCOPE} = {{ can_build_building = building_type:{building_id} }}"
        if upgrades.predecessors.get(building_id):
            location_body = [
                "\t\t\tOR = {", "\t\t\t\t" + legal,
                "\t\t\t\teu5ab_candidate_replaces_existing_building = yes",
                "\t\t\t}",
            ]
            base_candidate_lines.extend([
                "\t\t\tOR = {", "\t\t\t\t" + legal,
                *("\t\t\t\t" + line for line in replacement_body(building_id)),
                "\t\t\t}",
            ])
        else:
            location_body = ["\t\t\t" + legal]
            base_candidate_lines.extend(location_body)
        base_candidate_lines.append("\t\t}")
        location_candidate_lines.extend([
            f"\t\tbuilding_type:{building_id} = {{",
            *location_body,
            "\t\t}",
        ])
    # Collection's final new-build branch is valid only for this catalog.
    latest_unlocked_lines.extend(["\t\tfallback = { always = no }", "\t}", "}", ""])
    base_candidate_lines.extend(["\t\tfallback = { always = no }", "\t}", "}", ""])
    location_candidate_lines.extend(["\t\tfallback = { always = no }", "\t}", "}", ""])

    upgrade_candidate_lines = [
        "# True only when this destination can replace an existing vanilla predecessor.",
        "# Upgrade destinations are mutually exclusive building identities.",
        "eu5ab_candidate_replaces_existing_building = {",
        "\tswitch = {",
        "\t\ttrigger = this",
    ]
    upgrade_buildings = [building_id for building_id in _catalog_building_ids(catalog)
                         if upgrades.predecessors.get(building_id)]
    for building_id in upgrade_buildings:
        upgrade_candidate_lines.extend([
            f"\t\tbuilding_type:{building_id} = {{",
            *("\t\t\t" + line for line in replacement_body(building_id)),
            "\t\t}",
        ])
    if not upgrade_buildings:
        upgrade_candidate_lines = [
            "# True only when this destination can replace an existing vanilla predecessor.",
            "# Upgrade destinations are mutually exclusive building identities.",
            "eu5ab_candidate_replaces_existing_building = {",
            "\talways = no",
            "}",
            "",
        ]
    else:
        upgrade_candidate_lines.extend(["\t}", "}", ""])

    capacity_upgrade_lines = [
        "eu5ab_candidate_replaces_capacity_building = {",
        "\tswitch = {", "\t\ttrigger = this",
        *(line for building_id in upgrade_buildings for line in (
            f"\t\tbuilding_type:{building_id} = {{",
            *("\t\t\t" + part for part in replacement_body(building_id, capacity=True)),
            "\t\t}",
        )),
        "\t\tfallback = { always = no }", "\t}", "}", "",
    ]

    chunks = [
        render_scripted_triggers(policies, catalog, rules),
        "",
        render_construction_material_triggers(construction_demands, rules),
        "",
        render_engine_queue_triggers(catalog, rules),
        render_irrigation_triggers(rules),
        render_food_building_triggers(rules),
        "",
        *latest_unlocked_lines,
        *base_candidate_lines,
        *location_candidate_lines,
        *upgrade_candidate_lines,
        *capacity_upgrade_lines,
        building_capacity.render_triggers(),
        native_recipes.render_active_filter_trigger(recipes or {}, upgrades),
        quote_cache.render_triggers(),
        "# Only destinations the saved location can construct or upgrade reach scoring.",
        "# Select the matching building branch directly instead of scanning every mapping.",
        "eu5ab_candidate_location_can_build = {",
        "\tswitch = {",
        "\t\ttrigger = this",
        *(
            line
            for building_id in _catalog_building_ids(catalog)
            for line in (
                f"\t\tbuilding_type:{building_id} = {{",
                "\t\t\tOR = {",
                f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
                f"\t\t\t\t\tlocation_and_owner_can_build = {{ building_type = {building_id} }}",
                "\t\t\t\t}",
                "\t\t\t\teu5ab_candidate_replaces_existing_building = yes",
                "\t\t\t}",
                "\t\t}",
            )
        ),
        "\t\tfallback = { always = no }",
        "\t}",
        "}",
        "",
        "# Static job demand is exact for the selected building type and upgrade.",
        "# The forward gate adds vanilla promotion modifiers for the configured",
        f"# 0-{WORKFORCE_FORECAST_MAX_MONTHS} month horizon and caps the result by eligible source populations.",
        "# Net-new jobs is generated non-negative, so the availability comparison",
        "# also accepts zero-job upgrades without evaluating net-new jobs twice.",
        "eu5ab_candidate_current_workforce_sufficient = {",
        "\teu5ab_candidate_current_available_workers >= eu5ab_candidate_net_new_jobs",
        "}",
        "",
        "eu5ab_candidate_projected_workforce_sufficient = {",
        "\teu5ab_candidate_projected_available_workers >= eu5ab_candidate_net_new_jobs",
        "}",
        "",
        "# Cross-template safety gates.",
        "eu5ab_has_local_workforce = {",
        "\tOR = {",
        f"\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_pause_low_workforce <= 0",
        "\t\teu5ab_candidate_projected_workforce_sufficient = yes",
        "\t}",
        "}",
        "",
    ]
    chunks.extend(["eu5ab_upstream_output_shortage = {"])
    if recipes is None:
        chunks.extend(_upstream_output_shortage_condition_lines(
            catalog, rules, "\t", recipe_recovery=True, market_cache=True
        ))
    else:
        chunks.extend(["\tswitch = {", "\t\ttrigger = this", "\t\tfallback = { always = no }"])
        for building_id in _catalog_building_ids(catalog):
            body = _upstream_output_shortage_condition_lines(
                catalog, rules, "\t\t\t", recipe_recovery=True,
                building_id=building_id, recipes=recipes, market_cache=True,
            )
            if body == ["\t\t\talways = no"]:
                continue
            chunks.append(f"\t\tbuilding_type:{building_id} = {{")
            chunks.extend(body)
            chunks.append("\t\t}")
        chunks.append("\t}")
    chunks.extend([
        "}",
        "eu5ab_upstream_output_shortage_preliminary = {",
        "\tOR = { NOT = { eu5ab_candidate_pending_data_ready = yes } eu5ab_upstream_output_shortage = yes }",
        "}",
        "",
        "# RGO gates are split so the monthly diagnostics can classify every",
        "# deeply-scored location by its first blocking condition.",
        "eu5ab_rgo_capacity_available = {",
        "\tis_full_expanded_rgo = no",
        "}",
        "",
        "eu5ab_rgo_location_available = {",
        "\teu5ab_location_has_parallel_room = yes",
        "\tNOT = { has_variable = eu5ab_build_cooldown }",
        "\tOR = { NOT = { has_variable = eu5ab_failure_cooldown } owner = { exists = var:eu5ab_q_active } }",
        "}",
        "",
        "eu5ab_rgo_enabled = {",
        "\towner.var:eu5ab_global_enabled > 0",
        "\towner.var:eu5ab_global_allow_rgo > 0",
        "\teu5ab_location_template_not_paused = yes",
        "}",
        "",
        render_rgo_cost_input_trigger(),
        "eu5ab_rgo_finance_available = {",
        "\teu5ab_rgo_cost_inputs_available = yes",
        "\towner.gold >= eu5ab_rgo_cash_required",
        "\towner.eu5ab_global_budget_remaining_value > 0",
        "\towner.var:eu5ab_constructions_started_this_tick < { value = owner.var:eu5ab_monthly_build_quota }",
        "}",
        "",
        "eu5ab_rgo_utilization_allowed = {",
        "\trgo_workers >= eu5ab_rgo_current_capacity",
        "}",
        "",
        "# One RGO level always adds the vanilla rgo_level workforce demand.",
        "# The strict gate evaluates that prospective level, not merely whether",
        "# the currently built RGO is staffed.",
        "eu5ab_rgo_projected_workforce_sufficient = {",
        "\teu5ab_rgo_projected_available_workers >= eu5ab_rgo_jobs_per_expansion",
        "}",
        "",
        "eu5ab_rgo_workforce_allowed = {",
        "\tOR = {",
        "\t\tNOT = { eu5ab_rgo_population_mode = yes }",
        "\t\teu5ab_rgo_projected_workforce_sufficient = yes",
        "\t}",
        "}",
        "",
        rgo_automation.render_triggers(),
        rgo_pending.render_triggers(),
        rgo_queue.render_triggers(),
        "eu5ab_rgo_market_need_present = { eu5ab_rgo_price_allowed = yes }",
        "",
        "eu5ab_rgo_expansion_allowed = {",
        "\teu5ab_rgos_under_construction >= 0",
        "\teu5ab_rgo_capacity_available = yes",
        "\teu5ab_rgo_location_available = yes",
        "\teu5ab_rgo_enabled = yes",
        "\teu5ab_rgo_finance_available = yes",
        "\teu5ab_rgo_utilization_allowed = yes",
        "\teu5ab_rgo_workforce_allowed = yes",
        "\teu5ab_rgo_price_allowed = yes",
        "\teu5ab_rgo_score_allowed = yes",
        "\teu5ab_rgo_pending_allowed = yes",
        "}",
        "",
    ])

    chunks.extend([
        "# Compatibility aliases retained for diagnostics and older generated references.",
        "eu5ab_location_food_emergency = { eu5ab_food_emergency_enabled = yes }",
        "eu5ab_rgo_food_emergency = { eu5ab_rgo_food_emergency_enabled = yes eu5ab_rgo_expansion_allowed = yes }",
        "",
    ])
    def current_policy_switch_trigger_lines(
        trigger_name: str,
        preset_suffix: str,
        template_suffix: str | None = None,
    ) -> list[str]:
        """Route one mutually exclusive policy outside expensive candidate checks."""
        template_suffix = template_suffix or preset_suffix
        lines = [
            f"{trigger_name} = {{",
            "\tswitch = {",
            f"\t\ttrigger = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_policy_id",
        ]
        for index, policy in enumerate(policies):
            lines.append(
                f"\t\t{_policy_index(policy, index)} = {{ eu5ab_{policy.id}_{preset_suffix} = yes }}"
            )
        lines.extend([
            f"\t\t{CUSTOM_POLICY_VALUE} = {{",
            "\t\t\tswitch = {",
            f"\t\t\t\ttrigger = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_template_slot",
        ])
        for slot in TEMPLATE_SLOTS:
            lines.append(
                f"\t\t\t\t{slot} = {{ eu5ab_template_slot_{slot}_{template_suffix} = yes }}"
            )
        lines.extend(["\t\t\t}", "\t\t}", "\t}", "}", ""])
        return lines

    chunks.extend([
        "# Shared preset/custom routing for the single Top-3 execution chain.",
        "# Policy and template IDs are mutually exclusive, so switch avoids walking",
        "# every unrelated route for each building candidate.",
    ])
    for trigger_name, preset_suffix, template_suffix in (
        ("eu5ab_current_building_allowed", "building_allowed", None),
        ("eu5ab_current_special_building_allowed", "special_building_allowed", None),
        ("eu5ab_current_has_budget", "has_budget", None),
        ("eu5ab_current_keeps_cash_reserve", "keeps_cash_reserve", None),
        (
            "eu5ab_current_input_source_building_allowed",
            "input_source_building_allowed",
            "building_allowed",
        ),
    ):
        chunks.extend(
            current_policy_switch_trigger_lines(
                trigger_name,
                preset_suffix,
                template_suffix,
            )
        )
    chunks.extend([
        "eu5ab_current_policy_auto_builds_input_sources = {",
        "\towner.var:eu5ab_global_auto_build_input_sources > 0",
        "}",
        "",
    ])

    return "\n".join(chunks)


def render_workforce_cache_effects(
    workforce: WorkforceModelData, upgrades: BuildingUpgradeData,
) -> str:
    """Cache promotion, queued jobs and eligibility during candidate staging.

    Staging does not construct buildings or advance time. The normal and input
    pools share this lifetime; diagnostic/GUI calls outside it stay uncached.
    """
    building_ids = _catalog_building_ids_from_workforce(workforce)
    targets = sorted({workforce.buildings[key].pop_types[0] for key in building_ids})
    lines = [
        "", "eu5ab_clear_scan_promotion_cache = {",
        "\tremove_variable = eu5ab_scan_promotion_active",
        *(f"\tremove_variable = eu5ab_scan_promotion_{target}" for target in targets),
        *(f"\tremove_variable = eu5ab_scan_promotion_{target}_ready" for target in targets),
        *queued_workforce.scan_cache_clear_lines(workforce),
        "}", "", "eu5ab_cache_candidate_promotion = {",
        "\tif = {",
        f"\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_variable = eu5ab_scan_promotion_active }} }}",
        "\t\tswitch = {", "\t\t\ttrigger = this",
    ]
    for key in building_ids:
        target = workforce.buildings[key].pop_types[0]
        lines.extend([
            f"\t\t\tbuilding_type:{key} = {{",
            f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
            "\t\t\t\t\tif = {",
            f"\t\t\t\t\t\tlimit = {{ NOT = {{ has_variable = eu5ab_scan_promotion_{target} }} NOT = {{ has_variable = eu5ab_scan_promotion_{target}_ready }} }}",
            # Evaluate the unchanged formula before the cache variable exists.
            f"\t\t\t\t\t\tset_variable = {{ name = eu5ab_scan_promotion_{target} value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_candidate_projected_promotion }}",
            f"\t\t\t\t\t\tset_variable = eu5ab_scan_promotion_{target}_ready",
            "\t\t\t\t\t}", "\t\t\t\t}", "\t\t\t}",
        ])
    lines.extend([
        "\t\t}", "\t}", "}", "",
    ])
    for target in targets:
        lines.extend([
            f"eu5ab_prepare_promotion_{target} = {{",
            "\tif = {",
            f"\t\tlimit = {{ has_variable = eu5ab_scan_promotion_active NOT = {{ has_variable = eu5ab_scan_promotion_{target} }} NOT = {{ has_variable = eu5ab_scan_promotion_{target}_ready }} }}",
            f"\t\tset_variable = {{ name = eu5ab_scan_promotion_{target} value = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_candidate_projected_promotion }}",
            f"\t\tset_variable = eu5ab_scan_promotion_{target}_ready",
            "\t}", "}", "",
        ])
    lines.extend([
        "# Eligibility is reused only within one worker, including failed results.",
        "# The final construction/GUI workforce triggers remain live and uncached.",
        "eu5ab_prepare_candidate_workforce = {",
        f"\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
        "\t\tremove_variable = eu5ab_candidate_workforce_passed",
        "\t\tif = {",
        "\t\t\tlimit = { owner.var:eu5ab_global_pause_low_workforce <= 0 }",
        "\t\t\tset_variable = eu5ab_candidate_workforce_passed",
        "\t\t}",
        "\t\telse_if = {",
        "\t\t\tlimit = {",
        "\t\t\t\thas_variable = eu5ab_scan_promotion_active",
        f"\t\t\t\tis_target_in_variable_list = {{ name = eu5ab_candidate_workforce_checked target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t\t\t}",
        "\t\t\tif = {",
        f"\t\t\t\tlimit = {{ is_target_in_variable_list = {{ name = eu5ab_candidate_workforce_passed_types target = scope:{CANDIDATE_BUILDING_SCOPE} }} }}",
        "\t\t\t\tset_variable = eu5ab_candidate_workforce_passed",
        "\t\t\t}",
        "\t\t}",
        "\t\telse = {",
        f"\t\t\tscope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_evaluate_candidate_workforce = yes }}",
        "\t\t\tif = {",
        "\t\t\t\tlimit = { has_variable = eu5ab_scan_promotion_active }",
        f"\t\t\t\tadd_to_variable_list = {{ name = eu5ab_candidate_workforce_checked target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t\t\t\tif = {",
        "\t\t\t\t\tlimit = { has_variable = eu5ab_candidate_workforce_passed }",
        f"\t\t\t\t\tadd_to_variable_list = {{ name = eu5ab_candidate_workforce_passed_types target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t\t\t\t}",
        "\t\t\t}",
        "\t\t}",
        "\t}",
        "}", "",
        "# Dispatch once; keep the original available >= net-new-jobs arithmetic.",
        "eu5ab_evaluate_candidate_workforce = {",
        "\tswitch = {", "\t\ttrigger = this",
    ])
    for key in building_ids:
        destination = workforce.buildings[key]
        target = destination.pop_types[0]
        predecessors = sorted(
            ((p, workforce.all_buildings[p]) for p in upgrades.predecessors.get(key, ())
             if p in workforce.all_buildings
             and workforce.all_buildings[p].pop_types == destination.pop_types),
            key=lambda row: (-row[1].jobs_per_level, row[0]),
        )
        lines.extend([
            f"\t\tbuilding_type:{key} = {{",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
            f"\t\t\t\teu5ab_prepare_promotion_{target} = yes",
            *(f"\t\t\t\teu5ab_prepare_scan_queued_jobs_{pop} = yes" for pop in destination.pop_types),
            *([f"\t\t\t\tif = {{ limit = {{ has_variable = eu5ab_worker_screen_active }} scope:{CANDIDATE_BUILDING_SCOPE} = {{ eu5ab_prepare_worker_screen_upgrades = yes }} }}"] if predecessors else []),
            "\t\t\t\tset_variable = { name = eu5ab_candidate_required_workers value = {",
            f"\t\t\t\t\tif = {{ limit = {{ has_variable = eu5ab_worker_screen_active is_key_in_variable_map = {{ name = eu5ab_worker_screen_net_new_jobs_ready target = scope:{CANDIDATE_BUILDING_SCOPE} }} }}",
            f"\t\t\t\t\t\tvalue = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_candidate_net_new_jobs",
            "\t\t\t\t\t}",
            "\t\t\t\t\telse = {",
            f"\t\t\t\t\tvalue = {destination.jobs_per_level / 1000:g}",
        ])
        for index, (predecessor, row) in enumerate(predecessors):
            lines.extend([
                f"\t\t\t\t\t{'if' if index == 0 else 'else_if'} = {{",
                "\t\t\t\t\t\tlimit = { any_buildings_in_location = {",
                f"\t\t\t\t\t\t\tbuilding_type = building_type:{predecessor}",
                "\t\t\t\t\t\t\teu5ab_upgrade_source_available = yes",
                f"\t\t\t\t\t\t\tbuilding_can_be_upgraded_by = scope:{CANDIDATE_LOCATION_SCOPE}.owner",
                "\t\t\t\t\t\t} }",
                f"\t\t\t\t\t\tsubtract = {min(destination.jobs_per_level, row.jobs_per_level) / 1000:g}",
                "\t\t\t\t\t}",
            ])
        lines.extend([
            "\t\t\t\t\t}",
            "\t\t\t\t} }",
            "\t\t\t\tset_variable = { name = eu5ab_candidate_available_workers value = {",
            f'\t\t\t\t\tvalue = "location_unemployed_population_for_building_type(building_type:{key})"',
            "\t\t\t\t\tif = {",
            f"\t\t\t\t\t\tlimit = {{ has_variable = eu5ab_scan_promotion_{target} }}",
            f"\t\t\t\t\t\tadd = var:eu5ab_scan_promotion_{target}",
            "\t\t\t\t\t}",
            "\t\t\t\t\telse_if = {",
            f"\t\t\t\t\t\tlimit = {{ NOT = {{ has_variable = eu5ab_scan_promotion_{target}_ready }} }}",
            f"\t\t\t\t\t\tadd = scope:{CANDIDATE_BUILDING_SCOPE}.eu5ab_candidate_projected_promotion",
            "\t\t\t\t\t}",
            f"\t\t\t\t\tsubtract = {queued_workforce.scan_reservation(destination.pop_types)}",
            "\t\t\t\t\tmin = 0",
            "\t\t\t\t} }",
            "\t\t\t\tif = {",
            "\t\t\t\t\tlimit = { var:eu5ab_candidate_available_workers >= var:eu5ab_candidate_required_workers }",
            "\t\t\t\t\tset_variable = eu5ab_candidate_workforce_passed",
            "\t\t\t\t}",
            "\t\t\t\tremove_variable = eu5ab_candidate_required_workers",
            "\t\t\t\tremove_variable = eu5ab_candidate_available_workers",
            "\t\t\t}", "\t\t}",
        ])
    lines.extend([
        "\t\tfallback = {",
        "\t\t\tif = {",
        "\t\t\t\tlimit = { eu5ab_candidate_projected_workforce_sufficient = yes }",
        f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ set_variable = eu5ab_candidate_workforce_passed }}",
        "\t\t\t}", "\t\t}", "\t}", "}", "",
    ])
    return "\n".join(lines) + '\n' + queued_workforce.render_scan_cache_effects(workforce) + '\n'


def render_workforce_script_values(
    workforce: WorkforceModelData,
    upgrades: BuildingUpgradeData,
    policies: list[Policy],
    rules: AutomationRules,
) -> str:
    if workforce.rgo_jobs_per_level is None or workforce.rgo_jobs_per_level <= 0:
        raise ValueError(
            "Vanilla rgo_level must define a positive local_laborers_desired_pop"
        )
    rgo_jobs_per_expansion = workforce.rgo_jobs_per_level / 1000.0
    laborer_path = workforce.promotion_paths.get("laborers")
    laborer_promotion_factor = (
        laborer_path.promotion_factor if laborer_path is not None else 1.0
    )
    laborer_promotion_sources = tuple(
        sorted(
            source
            for source, path in workforce.promotion_paths.items()
            if "laborers" in path.targets
        )
    )
    chunks = [
        "# Metadata keeps people, but EU5 population script values use thousands",
        "# of people. Convert only at this generated runtime boundary.",
        "# The forecast uses exposed vanilla promotion modifiers, the target",
        "# pop type's promotion factor, and the direct eligible source pool.",
        "eu5ab_candidate_jobs_per_level = {",
        "\tvalue = 0",
    ]
    first_building_branch = True
    for building_id in _catalog_building_ids_from_workforce(workforce):
        jobs = workforce.buildings[building_id].jobs_per_level
        chunks.extend([
            "\tif = {" if first_building_branch else "\telse_if = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
            f"\t\tadd = {jobs / 1000:g}",
            "\t}",
        ])
        first_building_branch = False
    chunks.extend([
        "}",
        "",
        "eu5ab_candidate_net_new_jobs = {",
        "\tvalue = eu5ab_candidate_jobs_per_level",
    ])
    first_building_branch = True
    for building_id in _catalog_building_ids_from_workforce(workforce):
        destination = workforce.buildings[building_id]
        predecessor_rows = sorted(
            (
                (predecessor, workforce.all_buildings[predecessor])
                for predecessor in upgrades.predecessors.get(building_id, ())
                if predecessor in workforce.all_buildings
                and workforce.all_buildings[predecessor].pop_types == destination.pop_types
            ),
            key=lambda row: (-row[1].jobs_per_level, row[0]),
        )
        if not predecessor_rows:
            continue
        chunks.extend([
            "\tif = {" if first_building_branch else "\telse_if = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
        ])
        for index, (predecessor_id, predecessor) in enumerate(predecessor_rows):
            keyword = "if" if index == 0 else "else_if"
            net_reduction = min(
                destination.jobs_per_level,
                predecessor.jobs_per_level,
            )
            chunks.extend([
                f"\t\t{keyword} = {{",
                "\t\t\tlimit = {",
                f"\t\t\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{",
                "\t\t\t\t\tany_buildings_in_location = {",
                f"\t\t\t\t\t\tbuilding_type = building_type:{predecessor_id}",
                "\t\t\t\t\t\teu5ab_upgrade_source_available = yes",
                f"\t\t\t\t\t\tbuilding_can_be_upgraded_by = scope:{CANDIDATE_LOCATION_SCOPE}.owner",
                "\t\t\t\t\t}",
                "\t\t\t\t}",
                "\t\t\t}",
                f"\t\t\tsubtract = {net_reduction / 1000:g}",
                "\t\t}",
            ])
        chunks.extend(["\t}",])
        first_building_branch = False
    chunks.extend([
        "}",
        "",
        "eu5ab_candidate_current_available_workers = {",
        "\tvalue = 0",
    ])
    first_building_branch = True
    for building_id in _catalog_building_ids_from_workforce(workforce):
        chunks.extend([
            "\tif = {" if first_building_branch else "\telse_if = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
            f'\t\tadd = "scope:{CANDIDATE_LOCATION_SCOPE}.location_unemployed_population_for_building_type(building_type:{building_id})"',
            "\t}",
        ])
        first_building_branch = False
    chunks.append("\tsubtract = eu5ab_candidate_queued_jobs")
    pop_type_codes = {
        "nobles": 1,
        "clergy": 2,
        "burghers": 3,
        "laborers": 4,
        "soldiers": 5,
        "peasants": 6,
        "tribesmen": 7,
        "slaves": 8,
    }
    chunks.extend([
        "}",
        "",
        "eu5ab_location_combined_pop_promotion_speed = {",
        "\tvalue = modifier:local_pop_promotion_speed",
        "\towner = { add = modifier:global_pop_promotion_speed }",
        "\tadd = {",
        "\t\tvalue = modifier:local_pop_promotion_speed_scaled",
        "\t\tmultiply = population",
        "\t}",
        "\tmultiply = {",
        "\t\tvalue = 1",
        "\t\towner = { add = modifier:global_pop_promotion_speed_modifier }",
        "\t\tadd = modifier:local_pop_promotion_speed_modifier",
        "\t}",
        "}",
        "",
        "# Vanilla rgo_level adds a fixed workforce demand to every raw material.",
        "# Laborers always qualify; unemployed slaves count only when the owner",
        "# has the vanilla country modifier that lets slaves work RGOs.",
        "eu5ab_rgo_jobs_per_expansion = {",
        f"\tvalue = {rgo_jobs_per_expansion:g}",
        "}",
        "",
        "eu5ab_rgo_current_available_workers = {",
        '\tvalue = "unemployed_pops_of_pop_type_in_location(pop_type:laborers)"',
        "\tsubtract = eu5ab_queued_jobs_laborers",
        "\tif = {",
        "\t\tlimit = { owner = { modifier:allow_rgo_slave_demand = yes } }",
        '\t\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:slaves)"',
        "\t\tsubtract = eu5ab_queued_jobs_slaves",
        "\t\t# The shared RGO reservation is included in both eligible pop pools.",
        "\t\tadd = eu5ab_rgo_queued_jobs",
        "\t}",
        "}",
        "",
        "eu5ab_rgo_promotion_source_pool = {",
        "\tvalue = 0",
        *(
            f'\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:{source})"'
            for source in laborer_promotion_sources
        ),
        "}",
        "",
        "eu5ab_rgo_projected_promotion = {",
        "\tvalue = 0",
        "\tif = {",
        "\t\tlimit = { eu5ab_rgo_population_mode = yes }",
        "\t\tvalue = eu5ab_location_combined_pop_promotion_speed",
        f"\t\tmultiply = {laborer_promotion_factor:g}",
        "\t\tmultiply = owner.var:eu5ab_global_rgo_job_fill_deadline_months",
        "\t\tmin = 0",
        "\t\tmax = eu5ab_rgo_promotion_source_pool",
        "\t}",
        "}",
        "",
        "eu5ab_rgo_projected_available_workers = {",
        "\tvalue = eu5ab_rgo_current_available_workers",
        "\tadd = eu5ab_rgo_projected_promotion",
        "}",
        "",
        "eu5ab_candidate_workforce_pop_type_code = {",
        "\tvalue = 0",
    ])
    first_building_branch = True
    for building_id in _catalog_building_ids_from_workforce(workforce):
        pop_type = workforce.buildings[building_id].pop_types[0]
        chunks.extend([
            "\tif = {" if first_building_branch else "\telse_if = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
            f"\t\tadd = {pop_type_codes.get(pop_type, 0)}",
            "\t}",
        ])
        first_building_branch = False
    chunks.extend([
        "}",
        "",
        "eu5ab_candidate_promotion_source_type_count = {",
        "\tvalue = 0",
    ])
    first_building_branch = True
    for building_id in _catalog_building_ids_from_workforce(workforce):
        target = workforce.buildings[building_id].pop_types[0]
        source_count = sum(
            target in path.targets for path in workforce.promotion_paths.values()
        )
        chunks.extend([
            "\tif = {" if first_building_branch else "\telse_if = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
            f"\t\tadd = {source_count}",
            "\t}",
        ])
        first_building_branch = False
    chunks.extend([
        "}",
        "",
        "eu5ab_candidate_promotion_source_pool = {",
        "\tvalue = 0",
    ])
    first_building_branch = True
    for building_id in _catalog_building_ids_from_workforce(workforce):
        target = workforce.buildings[building_id].pop_types[0]
        sources = sorted(
            source
            for source, path in workforce.promotion_paths.items()
            if target in path.targets
        )
        chunks.extend([
            "\tif = {" if first_building_branch else "\telse_if = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
        ])
        for source in sources:
            chunks.append(
                f'\t\tadd = "scope:{CANDIDATE_LOCATION_SCOPE}.unemployed_pops_of_pop_type_in_location(pop_type:{source})"'
            )
        chunks.extend(["\t}"])
        first_building_branch = False
    chunks.extend([
        "}",
        "",
        "eu5ab_current_job_fill_deadline_months = {",
        f"\tvalue = scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_job_fill_deadline_months",
        "}",
        "",
        "eu5ab_candidate_projected_promotion = {",
        "\tvalue = 0",
        "\tif = {",
        f"\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_pause_low_workforce > 0 }}",
    ])
    first_building_branch = True
    for building_id in _catalog_building_ids_from_workforce(workforce):
        target = workforce.buildings[building_id].pop_types[0]
        target_path = workforce.promotion_paths.get(target)
        factor = target_path.promotion_factor if target_path is not None else 1.0
        chunks.extend([
            "\tif = {" if first_building_branch else "\telse_if = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
            "\t\tif = {",
            f"\t\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_variable = eu5ab_scan_promotion_{target} }} }}",
            f"\t\t\tadd = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_scan_promotion_{target}",
            "\t\t}",
            "\t\telse_if = {",
            f"\t\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ NOT = {{ has_variable = eu5ab_scan_promotion_{target}_ready }} }} }}",
            "\t\t\tadd = {",
            f"\t\t\t\tvalue = scope:{CANDIDATE_LOCATION_SCOPE}.eu5ab_location_combined_pop_promotion_speed",
            f"\t\t\t\tmultiply = {factor:g}",
            "\t\t\t\tmultiply = eu5ab_current_job_fill_deadline_months",
            "\t\t\t\tmin = 0",
            "\t\t\t\tmax = eu5ab_candidate_promotion_source_pool",
            "\t\t\t}",
            "\t\t}",
            "\t}",
        ])
        first_building_branch = False
    chunks.extend([
        "\t}",
        "}",
        "",
        "eu5ab_candidate_projected_available_workers = {",
        "\tvalue = eu5ab_candidate_current_available_workers",
        "\tadd = eu5ab_candidate_projected_promotion",
        "\tmin = 0",
        "}",
        "",
        "eu5ab_workforce_prediction_available = {",
        "\tvalue = 1",
        "}",
        "",
        "eu5ab_labor_result_code = {",
        "\tvalue = 3 # 1 current, 2 fills inside horizon, 3 still short",
        "\tif = {",
        "\t\tlimit = { eu5ab_candidate_current_workforce_sufficient = yes }",
        "\t\tsubtract = 2",
        "\t}",
        "\telse_if = {",
        "\t\tlimit = { eu5ab_candidate_projected_workforce_sufficient = yes }",
        "\t\tsubtract = 1",
        "\t}",
        "}",
        "",
    ])
    return "\n".join(chunks)


def _catalog_building_ids_from_workforce(
    workforce: WorkforceModelData,
) -> tuple[str, ...]:
    return tuple(sorted(workforce.buildings))


def render_native_input_script_values(
    recipes: dict[str, BuildingProduction],
    policies: list[Policy],
    rules: AutomationRules,
) -> str:
    chunks = [
        "# Province-native raw-input fit is a recipe-consistent proxy, not the exact",
        "# Building.GetBuildingProductionEfficiency C++ value.",
        "eu5ab_native_input_coverage_percent = {",
        "\tvalue = 0",
        "\tif = {",
        "\t\tlimit = { eu5ab_recipe_expected_raw_total > 0 }",
        "\t\tvalue = eu5ab_recipe_expected_raw_matched",
        "\t\tdivide = eu5ab_recipe_expected_raw_total",
        "\t\tmultiply = 100",
        "\t}",
        "}",
        "",
        "eu5ab_native_input_fit_unscaled = {",
        "\tvalue = eu5ab_native_input_coverage_percent",
        "\tdivide = 100",
        f"\tmultiply = {rules.native_input_fit.max_bonus}",
        "}",
        "",
        "eu5ab_native_input_shortage_factor = {",
        "\tvalue = 1",
        "\tif = {",
        "\t\tlimit = { eu5ab_candidate_scoring_input_shortage = yes }",
        f"\t\tmultiply = {rules.native_input_fit.shortage_discount:g}",
        "\t}",
        "}",
        "",
    ]
    chunks.extend([
        "eu5ab_current_native_input_priority = {",
        f"\tvalue = scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_native_input_priority",
        "}",
        "",
        "eu5ab_native_input_fit_proxy_score = {",
        "\tvalue = 0",
        "\t# A disabled preference needs neither province matching nor shortage queries.",
        "\tif = {",
        "\t\tlimit = { NOT = { eu5ab_current_native_input_priority = 0 } }",
        "\t\tvalue = eu5ab_native_input_fit_unscaled",
        "\t\tmultiply = eu5ab_current_native_input_priority",
        "\t\tdivide = 10",
        f"\t\tmultiply = scope:{CANDIDATE_LOCATION_SCOPE}.market_access",
        f"\t\tmultiply = scope:{CANDIDATE_LOCATION_SCOPE}.local_control",
        "\t\tmultiply = eu5ab_native_input_shortage_factor",
        "\t}",
        "}",
        "",
        "eu5ab_native_input_method_code = {",
        "\tvalue = 0 # 0 none, 1 recipe/province proxy, 2 exact vanilla",
        "\tif = { limit = { eu5ab_recipe_expected_raw_total > 0 } add = 1 }",
        "}",
        "",
        "eu5ab_recipe_selection_method_code = { value = 1 if = { limit = { scope:eu5ab_candidate_location = { eu5ab_native_recipes_current = yes is_target_in_variable_list = { name = eu5ab_native_recipe_types target = scope:eu5ab_candidate_building } } } value = 2 } } # 1 estimate; 2 captured native active method",
        "",
    ])
    return "\n".join(chunks)


def render_recipe_script_values(
    recipes: dict[str, BuildingProduction],
    rules: AutomationRules,
) -> str:
    chunks = [
        render_production(recipes, rules)[1],
        "eu5ab_recipe_expected_gross_margin = {",
        "\tvalue = eu5ab_recipe_expected_output_value",
        "\tsubtract = eu5ab_recipe_expected_input_cost",
        "}",
        "",
        "eu5ab_recipe_economic_efficiency_score = {",
        "\tvalue = eu5ab_recipe_expected_gross_margin",
        "\tdivide = building_base_cost_in_gold",
        f"\tmultiply = {rules.thresholds.economic_score_scale:g}",
        "}",
        "",
    ]
    return "\n".join(chunks)


def render_needs_script_values(
    policies: list[Policy],
    catalog: BuildingCatalog,
    rules: AutomationRules,
    recipes: dict[str, BuildingProduction],
    workforce: WorkforceModelData,
    upgrades: BuildingUpgradeData,
    construction_demands: dict[str, ConstructionDemand],
    industries: dict[str, list[str]] | None = None,
) -> str:
    chunks = [
        "# Generated by eu5autobuild.generator.",
        "# Bounded scoring combines strategic needs with an extracted recipe proxy.",
        render_workforce_script_values(workforce, upgrades, policies, rules),
        "",
        render_recipe_script_values(recipes, rules),
        render_food_building_values(rules),
        "",
        render_construction_material_script_values(construction_demands, rules),
        "",
        render_native_input_script_values(recipes, policies, rules),
        render_town_rights_values(recipes, rules),
        industry_promotion.render_values(recipes, industries if industries is not None else industry_promotion.load_industries()),
        scan_reserve.render_values(),
        "",
        "# Convert the shared CMM percentage settings once for every template.",
        "eu5ab_global_price_min_ratio = {",
        f"\tvalue = scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_price_min",
        "\tdivide = 100",
        "}",
        "",
        "eu5ab_global_price_max_ratio = {",
        f"\tvalue = scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_price_max",
        "\tdivide = 100",
        "}",
        "",
        "# Compatibility aliases used by shared strategic scoring.",
        "eu5ab_current_custom_price_min_ratio = {",
        "\tvalue = eu5ab_global_price_min_ratio",
        "}",
        "",
        "eu5ab_current_preset_origin = {",
        "\tif = {",
        f"\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ has_variable = eu5ab_scan_preset_origin }} }}",
        f"\t\tvalue = scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_scan_preset_origin",
        "\t}",
        "\telse = { value = eu5ab_uncached_preset_origin }",
        "}",
        "",
        "eu5ab_uncached_preset_origin = {",
        "\tvalue = 0",
    ]
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            "\tif = {" if slot == TEMPLATE_SLOTS[0] else "\telse_if = {",
            f"\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_template_slot = {slot} }}",
            f"\t\tadd = scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:{_slot_var(slot, 'preset_origin')}",
            "\t}",
        ])
    chunks.extend(["}", ""])
    universal_score = _universal_need_score_lines(catalog, rules)
    chunks.extend(recipe_snapshot.cached_value("eu5ab_universal_need_score", "need_score", universal_score))
    # Only the candidate snapshot calls these values, after selecting every slot.
    # Keep the generic path above for other callers and unknown building types.
    for building_id in _catalog_building_ids(catalog):
        chunks.extend([f"eu5ab_typed_need_score_{building_id} = {{", "\tvalue = 0",
                       *_universal_need_score_lines(catalog, rules, building_id, recipes), "}", ""])

    chunks.extend(["eu5ab_copied_preset_origin_score = {", "\tvalue = 0"])
    for index, policy in enumerate(policies):
        chunks.extend([
            "\tif = {" if index == 0 else "\telse_if = {",
            f"\t\tlimit = {{ eu5ab_current_preset_origin = {_policy_index(policy, index)} }}",
        ])
        for rank, good in enumerate(policy.priority_goods):
            keyword = "if" if rank == 0 else "else_if"
            score = max(
                0,
                rules.scores.policy_priority_base
                - rank * rules.scores.policy_priority_step,
            )
            chunks.extend([f"\t\t{keyword} = {{", "\t\t\tlimit = {"])
            chunks.extend(_support_trigger_lines((good,), catalog, "\t\t\t\t"))
            chunks.extend(["\t\t\t}", f"\t\t\tadd = {score}", "\t\t}"])
        role_buildings = rules.building_groups.get(policy.role, ())
        if role_buildings:
            chunks.extend([
                "\t\tif = {",
                "\t\t\tlimit = {",
                "\t\t\t\tOR = {",
            ])
            for building_id in role_buildings:
                chunks.append(f"\t\t\t\t\tthis = building_type:{building_id}")
            chunks.extend([
                "\t\t\t\t}",
                "\t\t\t}",
                f"\t\t\tadd = {rules.scores.role_match}",
                "\t\t}",
            ])
        chunks.append("\t}")
    chunks.extend(["}", ""])

    chunks.extend([
        "eu5ab_default_candidate_configured_priority = {",
        "\tvalue = 0",
    ])
    for building_id in _catalog_building_ids(catalog):
        configured_priority = rules.building_priority_for(building_id)
        if configured_priority <= rules.building_priorities.minimum:
            continue
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
            f"\t\tadd = {configured_priority:g}",
            "\t}",
        ])
    chunks.extend([
        "}",
        "",
        "# The 0-10 value is kept separate from the composite score so the",
        "# predicted-profit strategy can use it as a bounded soft preference.",
        "eu5ab_current_candidate_configured_priority = {",
        "\tvalue = 0",
        "\tif = {",
        f"\t\tlimit = {{ NOT = {{ scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_policy_id = {CUSTOM_POLICY_VALUE} }} }}",
        "\t\tadd = eu5ab_default_candidate_configured_priority",
        "\t}",
    ])
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            "\tif = {",
            "\t\tlimit = {",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_policy_id = {CUSTOM_POLICY_VALUE}",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_template_slot = {slot}",
            "\t\t}",
            f"\t\tscope:{CANDIDATE_LOCATION_SCOPE}.owner = {{",
            "\t\t\tif = {",
            f"\t\t\t\tlimit = {{ has_variable_map = {_slot_priority_map(slot)} is_key_in_variable_map = {{ name = {_slot_priority_map(slot)} target = prev }} }}",
            "\t\t\t\tadd = {",
            f"\t\t\t\t\tvalue = \"variable_map({_slot_priority_map(slot)}|prev)\"",
            "\t\t\t\t}",
            "\t\t\t}",
            "\t\t}",
            "\t}",
        ])
    chunks.extend(["\tmin = 0", "\tmax = 10", "}", ""])

    building_quality_score: list[str] = []
    for building_id in _catalog_building_ids(catalog):
        quality_score = round(
            rules.building_priority_for(building_id)
            * rules.building_priorities.score_per_point
        )
        if quality_score <= 0:
            continue
        building_quality_score.extend([
            "\tif = {",
            f"\t\tlimit = {{ this = building_type:{building_id} }}",
            f"\t\tadd = {quality_score}",
            "\t}",
        ])

    for policy in policies:
        chunks.extend([f"eu5ab_score_{policy.id} = {{", "\tvalue = 0"])
        chunks.append("\tadd = eu5ab_universal_need_score")
        chunks.append("\tadd = eu5ab_recipe_economic_efficiency_score")
        chunks.append("\tadd = eu5ab_native_input_fit_proxy_score")
        chunks.append("\tadd = eu5ab_town_rights_candidate_score")
        chunks.append("\tadd = eu5ab_industry_candidate_score")
        chunks.extend(building_quality_score)
        for building_id in policy.allowed_buildings:
            if (
                rules.building_priority_for(building_id)
                > rules.building_priorities.minimum
            ):
                continue
            chunks.extend([
                "\tif = {",
                f"\t\tlimit = {{ this = building_type:{building_id} }}",
                f"\t\tadd = {rules.building_priorities.score_per_point}",
                "\t}",
            ])
        chunks.append("\tadd = eu5ab_output_high_price_bonus")
        for rank, good in enumerate(policy.priority_goods):
            keyword = "if" if rank == 0 else "else_if"
            score = max(0, rules.scores.policy_priority_base - rank * rules.scores.policy_priority_step)
            chunks.extend([f"\t{keyword} = {{", "\t\tlimit = {"])
            chunks.extend(_support_trigger_lines((good,), catalog, "\t\t\t"))
            chunks.extend(["\t\t}", f"\t\tadd = {score}", "\t}"])
        role_buildings = rules.building_groups.get(policy.role, ())
        if role_buildings:
            chunks.extend(["\tif = {", "\t\tlimit = {", "\t\t\tOR = {"])
            for building_id in role_buildings:
                chunks.append(f"\t\t\t\tthis = building_type:{building_id}")
            chunks.extend([
                "\t\t\t}",
                "\t\t}",
                f"\t\tadd = {rules.scores.role_match}",
                "\t}",
            ])
        chunks.extend([
            "}",
            "",
            f"eu5ab_cash_required_{policy.id} = {{",
            "\tvalue = building_base_cost_in_gold",
            f"\tadd = scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_min_cash_reserve",
            "}",
            "",
        ])

    chunks.extend([
        "eu5ab_score_custom_template = {",
        "\tvalue = 0",
    ])
    chunks.append("\tadd = eu5ab_universal_need_score")
    chunks.append("\tadd = eu5ab_recipe_economic_efficiency_score")
    chunks.append("\tadd = eu5ab_native_input_fit_proxy_score")
    chunks.append("\tadd = eu5ab_town_rights_candidate_score")
    chunks.append("\tadd = eu5ab_industry_candidate_score")
    chunks.extend([
        "}",
        "",
        "eu5ab_cash_required_custom_template = {",
        "\tvalue = building_base_cost_in_gold",
        "}",
        "",
    ])

    for slot in TEMPLATE_SLOTS:
        chunks.extend([f"eu5ab_score_template_slot_{slot} = {{", "\tvalue = 0"])
        chunks.append("\tadd = eu5ab_universal_need_score")
        chunks.append("\tadd = eu5ab_recipe_economic_efficiency_score")
        chunks.append("\tadd = eu5ab_native_input_fit_proxy_score")
        chunks.append("\tadd = eu5ab_town_rights_candidate_score")
        chunks.append("\tadd = eu5ab_industry_candidate_score")
        chunks.append("\tadd = eu5ab_copied_preset_origin_score")
        chunks.append("\tadd = eu5ab_output_high_price_bonus")
        chunks.extend([
            f"\tscope:{CANDIDATE_LOCATION_SCOPE}.owner = {{",
            "\t\tif = {",
            f"\t\t\tlimit = {{ has_variable_map = {_slot_priority_map(slot)} is_key_in_variable_map = {{ name = {_slot_priority_map(slot)} target = prev }} }}",
            "\t\t\tadd = {",
            f"\t\t\t\tvalue = \"variable_map({_slot_priority_map(slot)}|prev)\"",
            f"\t\t\t\tmultiply = {rules.building_priorities.score_per_point}",
            "\t\t\t}",
            "\t\t}",
            "\t}",
        ])
        chunks.extend([
            "}",
            "",
            f"eu5ab_cash_required_template_slot_{slot} = {{",
            "\tvalue = building_base_cost_in_gold",
            f"\tadd = scope:{CANDIDATE_LOCATION_SCOPE}.owner.var:eu5ab_global_min_cash_reserve",
            "}",
            "",
        ])

    chunks.extend([
        "eu5ab_location_available_workforce_signal = {",
        '\tvalue = "unemployed_pops_of_pop_type_in_location(pop_type:peasants)"',
        '\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:laborers)"',
        '\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:burghers)"',
        '\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:clergy)"',
        '\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:nobles)"',
        '\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:soldiers)"',
        '\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:tribesmen)"',
        '\tadd = "unemployed_pops_of_pop_type_in_location(pop_type:slaves)"',
        "}",
        "",
        "eu5ab_location_need_score = {",
        "\tvalue = 0",
    ])
    for good in sorted(rules.food_goods):
        chunks.extend([
            "\tif = {",
            "\t\tlimit = {",
            f"\t\t\traw_material = goods:{good}",
            f"\t\t\towner.var:{_global_setting_var('emergency_food_exhaustion_override')} > 0",
            "\t\t\tmarket ?= { is_projected_to_run_out_of_food_stockpile = yes }",
            "\t\t}",
            f"\t\tadd = {rules.scores.food_projected_exhaustion}",
            "\t}",
            "\telse_if = {",
            "\t\tlimit = {",
            f"\t\t\traw_material = goods:{good}",
            f"\t\t\towner.var:{_global_setting_var('emergency_food_stockpile_override')} > 0",
            f"\t\t\tmarket ?= {{ market_food_percentage <= {rules.thresholds.food_emergency_ratio} }}",
            "\t\t}",
            f"\t\tadd = {rules.scores.food_emergency}",
            "\t}",
            "\telse_if = {",
            "\t\tlimit = {",
            f"\t\t\traw_material = goods:{good}",
            f"\t\t\tmarket ?= {{ market_food_percentage <= {rules.thresholds.food_low_ratio} }}",
            "\t\t}",
            f"\t\tadd = {rules.scores.food_low}",
            "\t}",
        ])
    for good in sorted(rules.construction_goods):
        chunks.extend([
            "\tif = {",
            "\t\tlimit = {",
            f"\t\t\traw_material = goods:{good}",
        ])
        chunks.extend(_market_supply_condition_lines(good, rules.thresholds.goods_shortage_supply_ratio, "\t\t\t", ""))
        chunks.extend([
            "\t\t}",
            f"\t\tadd = {rules.scores.short_construction_good}",
            "\t}",
        ])
    for index, policy in enumerate(policies):
        for rank, good in enumerate(policy.priority_goods):
            score = max(0, rules.scores.policy_priority_base - rank * rules.scores.policy_priority_step)
            chunks.extend([
                "\tif = {",
                "\t\tlimit = {",
                f"\t\t\tvar:eu5ab_policy_id = {_policy_index(policy, index)}",
                f"\t\t\traw_material = goods:{good}",
            ])
            chunks.extend(_market_supply_condition_lines(good, rules.thresholds.goods_shortage_supply_ratio, "\t\t\t", ""))
            chunks.extend(["\t\t}", f"\t\tadd = {score}", "\t}"])
    chunks.extend([
        "\t# EU5 population values are thousands: 100 means 100,000 people.",
        "\tadd = {",
        "\t\tvalue = population",
        f"\t\tmultiply = {rules.location_scores.population / 100:g}",
        f"\t\tmax = {rules.location_scores.population:g}",
        "\t}",
        "\t# 0.1 script units is 100 actually available people.",
        "\tif = {",
        "\t\tlimit = { eu5ab_location_available_workforce_signal >= 0.1 }",
        f"\t\tadd = {rules.location_scores.workforce}",
        "\t}",
        "\tadd = {",
        "\t\tvalue = development",
        f"\t\tmultiply = {rules.location_scores.development / 50:g}",
        "\t}",
        "\tadd = {",
        "\t\tvalue = local_control",
        f"\t\tmultiply = {rules.location_scores.control:g}",
        "\t}",
        "\tadd = {",
        "\t\tvalue = market_access",
        f"\t\tmultiply = {rules.location_scores.market_access:g}",
        "\t}",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_recent_build_penalty }",
        f"\t\tadd = {rules.location_scores.recent_build_penalty}",
        "\t}",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_wait_months }",
        "\t\tadd = {",
        "\t\t\tvalue = var:eu5ab_wait_months",
        f"\t\t\tmultiply = {rules.location_scores.waiting_per_month}",
        "\t\t}",
        "\t}",
        "}",
        "",
        "# Current RGO utilization is workers divided by built capacity, not by",
        "# the location's theoretical geological maximum.",
        "eu5ab_rgo_current_capacity = {",
        "\tvalue = rgo_level",
        "\tmultiply = eu5ab_rgo_jobs_per_expansion",
        "}",
        "",
        "eu5ab_rgo_utilization_ratio = {",
        "\tvalue = rgo_workers",
        "\tdivide = { value = eu5ab_rgo_current_capacity min = 0.001 }",
        "\tmin = 0",
        "\tmax = 1",
        "}",
        "",
        "eu5ab_rgo_candidate_score = {",
        "\tvalue = 0",
        "\tadd = eu5ab_town_rights_rgo_score",
        "\tif = {",
        "\t\tlimit = { is_full_expanded_rgo = no }",
        f"\t\tadd = {rules.rgo_scores.expansion_space}",
        "\t}",
        "\tadd = {",
        "\t\tvalue = eu5ab_rgo_utilization_ratio",
        f"\t\tmultiply = {rules.rgo_scores.utilization}",
        "\t}",
        f"\tadd = {rules.thresholds.rgo_budget_cost * rules.rgo_scores.cost_penalty}",
    ])
    for good in rgo_automation.raw_goods():
        chunks.extend([
            "\tif = {",
            "\t\tlimit = {",
            f"\t\t\traw_material = goods:{good}",
        ])
        chunks.extend(
            _market_supply_condition_lines(
                good,
                rules.thresholds.goods_shortage_supply_ratio,
                "\t\t\t",
                "",
            )
        )
        chunks.extend(["\t\t}", f"\t\tadd = {rules.rgo_scores.shortage}", "\t}"])
    chunks.extend([
        "\tadd = {",
        "\t\tvalue = eu5ab_rgo_high_price_factor",
        f"\t\tmultiply = {rules.rgo_scores.high_price}",
        "\t}",
    ])
    for good in sorted(
        rules.food_goods
        | rules.construction_goods
        | frozenset(rules.goods_groups["military"])
    ):
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ raw_material = goods:{good} }}",
            f"\t\tadd = {rules.rgo_scores.strategic}",
            "\t}",
        ])
    for good in sorted(rules.food_goods):
        chunks.extend([
            "\tif = {",
            "\t\tlimit = {",
            f"\t\t\traw_material = goods:{good}",
            "\t\t\tOR = {",
            "\t\t\t\tAND = {",
            f"\t\t\t\t\towner.var:{_global_setting_var('emergency_food_exhaustion_override')} > 0",
            "\t\t\t\t\tmarket ?= { is_projected_to_run_out_of_food_stockpile = yes }",
            "\t\t\t\t}",
            "\t\t\t\tAND = {",
            f"\t\t\t\t\towner.var:{_global_setting_var('emergency_food_stockpile_override')} > 0",
            f"\t\t\t\t\tmarket ?= {{ market_food_percentage <= {rules.thresholds.food_emergency_ratio} }}",
            "\t\t\t\t}",
            "\t\t\t}",
            "\t\t}",
            f"\t\tadd = {rules.rgo_scores.food_emergency}",
            "\t}",
        ])
    chunks.extend([
        "}",
        "",
        "# Cross-feature priority comes from the ordered CMM list. This score only",
        "# combines general location need with RGO-specific need inside the RGO class.",
        "eu5ab_rgo_base_score = {",
        "\tvalue = eu5ab_location_need_score",
        "\t# RGO does not inherit the ordinary-building recent-start penalty.",
        "\tif = {",
        "\t\tlimit = { has_variable = eu5ab_recent_build_penalty }",
        f"\t\tsubtract = {rules.location_scores.recent_build_penalty}",
        "\t}",
        "\tadd = eu5ab_rgo_candidate_score",
        "}",
        "",
        "eu5ab_rgo_queue_order_score = {",
        "\tvalue = eu5ab_rgo_base_score",
        "\tmultiply = eu5ab_rgo_price_factor",
        "\tmultiply = eu5ab_rgo_pending_factor",
        "\tmultiply = eu5ab_rgo_current_labor_factor",
        "}",
        "",
        rgo_automation.render_values(),
        rgo_pending.render_values(),
        "eu5ab_current_min_cash_reserve = {",
        "\tvalue = owner.var:eu5ab_global_min_cash_reserve",
        "}",
        "",
        rgo_queue.render_values(),
        "",
        render_rgo_cost_script_values(rules.thresholds.rgo_budget_cost),
        "eu5ab_rgo_cash_required = {",
        "\tvalue = eu5ab_rgo_expansion_cost",
        "\tadd = eu5ab_current_min_cash_reserve",
        "}",
        "",
    ])
    chunks.extend([
        "# One score entrypoint lets every preset and custom slot share the same",
        "# bounded ordered_buildable_building_type iterator.",
        "eu5ab_candidate_base_score = {",
        "\tvalue = 0",
    ])
    for index, policy in enumerate(policies):
        chunks.extend([
            "\tif = {",
            f"\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_policy_id = {_policy_index(policy, index)} }}",
            f"\t\tadd = eu5ab_score_{policy.id}",
            "\t}",
        ])
    for slot in TEMPLATE_SLOTS:
        chunks.extend([
            "\tif = {",
            "\t\tlimit = {",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_policy_id = {CUSTOM_POLICY_VALUE}",
            f"\t\t\tscope:{CANDIDATE_LOCATION_SCOPE}.var:eu5ab_template_slot = {slot}",
            "\t\t}",
            f"\t\tadd = eu5ab_score_template_slot_{slot}",
            "\t}",
        ])
    chunks.extend([
        "}", "",
        "eu5ab_unadjusted_candidate_score = {",
        "\tvalue = eu5ab_candidate_base_score",
        "\tif = {",
        "\t\tlimit = { eu5ab_candidate_base_score >= 0 }",
        "\t\tmultiply = eu5ab_candidate_current_labor_factor",
        "\t}",
        "\telse = { divide = eu5ab_candidate_current_labor_factor }",
        "}", "",
        output_prices.render(recipes, rules)[1],
        construction_slots.render()[2],
        project_tracking.render(rules, recipes)[2],
        building_capacity.render_values(),
        building_capacity.render_score_values(),
        quote_cache.render_values(),
        winner_batch.render_values(),
        building_capacity.phase_values(len(CANDIDATE_PRIORITY_FEATURES) * 4),
    ])
    chunks.extend([
        "# Pool ranking reuses its snapshot; standalone/backfill staging reads live.",
        f"{candidate_backfill.CACHED_SCORE} = {{",
        "\tvalue = 0",
        "\tif = {",
        f"\t\tlimit = {{ scope:{CANDIDATE_LOCATION_SCOPE} = {{ is_key_in_variable_map = {{ name = {candidate_backfill.SCORE_CACHE} target = prev }} }} }}",
        f'\t\tscope:{CANDIDATE_LOCATION_SCOPE} = {{ add = "variable_map({candidate_backfill.SCORE_CACHE}|prev)" }}',
        "\t}",
        "\telse = { add = eu5ab_current_candidate_score }",
        "}", "",
    ])
    return "\n".join(chunks)


def render_engine_queue_scripted_guis(rules: AutomationRules) -> str:
    phase_count = len(CANDIDATE_PRIORITY_FEATURES) * 4
    check_stage_guard = queue_script_dispatch.CHECK_STAGE_GUARD
    chunks = [
        "# GUI data adapters; queue transitions and confirmations live in script.",
        "eu5ab_gui_queue_should_validate = {",
        "\tis_shown = { exists = var:eu5ab_q_active NOT = { has_variable = eu5ab_scan_resume_after_load } NOT = { exists = var:eu5ab_q_fire } }",
        "}",
        "",
        *(
            line
            for phase in range(1, phase_count + 1)
            for line in (
                f"eu5ab_gui_queue_phase_{phase}_should_validate = {{",
                f"\tis_shown = {{ exists = var:eu5ab_q_active NOT = {{ has_variable = eu5ab_scan_resume_after_load }} NOT = {{ exists = var:eu5ab_q_fire }} NOT = {{ exists = var:eu5ab_q_profit_selecting }} var:eu5ab_q_phase = {phase} }}",
                "}",
                "",
            )
        ),
        "eu5ab_gui_queue_profit_should_validate = {",
        "\tis_shown = { exists = var:eu5ab_q_active NOT = { has_variable = eu5ab_scan_resume_after_load } exists = var:eu5ab_q_profit_selecting NOT = { exists = var:eu5ab_q_fire } }",
        "}",
        "",
        "eu5ab_gui_queue_should_fire = {",
        "\tis_shown = { exists = var:eu5ab_q_active NOT = { has_variable = eu5ab_scan_resume_after_load } exists = var:eu5ab_q_fire }",
        "}",
        "",
        "eu5ab_gui_queue_try_candidate = {",
        f"\tsaved_scopes = {{ {CANDIDATE_BUILDING_SCOPE} eu5ab_engine_country eu5ab_engine_queue_check_stage eu5ab_engine_cost eu5ab_engine_income eu5ab_engine_profit eu5ab_engine_can_build eu5ab_engine_province_food_balance eu5ab_engine_province_food_natural eu5ab_engine_rgo_revenue {building_capacity.GUI_SCOPES} eu5ab_engine_replaced_building }}",
        "\tis_valid = { always = yes }",
        "\teffect = {",
        f"\t\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
        "\t\tif = {",
        "\t\t\tlimit = {",
        "\t\t\t\tscope:eu5ab_engine_country = { has_variable = eu5ab_q_active NOT = { has_variable = eu5ab_scan_resume_after_load } has_variable = eu5ab_q_phase NOT = { exists = var:eu5ab_q_fire } }",
        f"\t\t\t\tscope:eu5ab_engine_country = {{ {check_stage_guard} }}",
        "\t\t\t\tOR = {",
        *(f"\t\t\t\t\tAND = {{ scope:eu5ab_engine_country.var:eu5ab_q_phase = {phase} is_target_in_variable_list = {{ name = eu5ab_q_phase_{phase}_types target = scope:{CANDIDATE_BUILDING_SCOPE} }} }}" for phase in range(1, phase_count + 1)),
        "\t\t\t\t}",
        f"\t\t\t\tNOT = {{ is_target_in_variable_list = {{ name = eu5ab_q_done_types target = scope:{CANDIDATE_BUILDING_SCOPE} }} }}",
        "\t\t\t}",
        "\t\t\teu5ab_prepare_candidate_dependencies = yes",
        f"\t\t\tadd_to_variable_list = {{ name = eu5ab_q_done_types target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t\t\tscope:eu5ab_engine_country = { change_variable = { name = eu5ab_q_processed add = 1 } change_variable = { name = eu5ab_diag_engine_probes add = 1 } }",
        "\t\t\tif = { limit = { NOT = { has_variable = eu5ab_q_dependency_wait } }",
        *queue_validation.validation_lines(rules, profit=False, actual_profit_mode=CMM_CANDIDATE_RANKING_ACTUAL_PROFIT),
        "\t\t\t}",
        "\t\t\tscope:eu5ab_engine_country = { eu5ab_check_engine_phase_completion = yes }",
        "\t\t}",
        "\t}",
        "}",
        "",
        "eu5ab_gui_queue_try_profit_candidate = {",
        f"\tsaved_scopes = {{ {CANDIDATE_BUILDING_SCOPE} eu5ab_engine_country eu5ab_engine_queue_check_stage eu5ab_engine_cost eu5ab_engine_income eu5ab_engine_profit eu5ab_engine_can_build eu5ab_engine_province_food_balance eu5ab_engine_province_food_natural eu5ab_engine_rgo_revenue {building_capacity.GUI_SCOPES} eu5ab_engine_replaced_building }}",
        "\tis_valid = { always = yes }",
        "\teffect = {",
        f"\t\tsave_scope_as = {CANDIDATE_LOCATION_SCOPE}",
        "\t\tif = {",
        "\t\t\tlimit = {",
        "\t\t\t\tscope:eu5ab_engine_country = { has_variable = eu5ab_q_active NOT = { has_variable = eu5ab_scan_resume_after_load } has_variable = eu5ab_q_phase has_variable = eu5ab_q_profit_selecting NOT = { exists = var:eu5ab_q_fire } }",
        f"\t\t\t\tscope:eu5ab_engine_country = {{ {check_stage_guard} }}",
        "\t\t\t\tNOT = { has_variable = eu5ab_q_profit_done }",
        f"\t\t\t\tis_target_in_variable_list = {{ name = eu5ab_q_profit_best_types target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t\t\t}",
        "\t\t\teu5ab_prepare_candidate_dependencies = yes",
        "\t\t\tset_variable = eu5ab_q_profit_done",
        "\t\t\tscope:eu5ab_engine_country = { change_variable = { name = eu5ab_q_processed add = 1 } change_variable = { name = eu5ab_diag_engine_probes add = 1 } }",
        "\t\t\tif = { limit = { NOT = { has_variable = eu5ab_q_dependency_wait } }",
        *queue_validation.validation_lines(rules, profit=True, actual_profit_mode=CMM_CANDIDATE_RANKING_ACTUAL_PROFIT),
        "\t\t\t}",
        "\t\t\t# A winner can become unaffordable after another location reserves funds.",
        "\t\t\t# Exclude it for this phase and re-rank the remaining candidates after",
        "\t\t\t# approved projects settle. Every retry removes a candidate, so it is bounded.",
        "\t\t\tif = {",
        "\t\t\t\tlimit = {",
        "\t\t\t\t\tNOT = { has_variable = eu5ab_q_location_approved }",
        "\t\t\t\t\tNOT = { has_variable = eu5ab_q_dependency_wait }",
        "\t\t\t\t\teu5ab_location_has_parallel_room = yes",
        "\t\t\t\t\tscope:eu5ab_engine_country = { eu5ab_q_outstanding_approvals_value < { value = var:eu5ab_monthly_build_quota subtract = var:eu5ab_constructions_started_this_tick } }",
        "\t\t\t\t}",
        f"\t\t\t\tadd_to_variable_list = {{ name = eu5ab_q_failed_types target = scope:{CANDIDATE_BUILDING_SCOPE} }}",
        "\t\t\t\tscope:eu5ab_engine_country = { set_variable = eu5ab_q_retry_phase }",
        "\t\t\t}",
        "\t\t\tscope:eu5ab_engine_country = { eu5ab_check_engine_phase_completion = yes }",
        "\t\t}",
        "\t}",
        "}",
        "",
        "# Compatibility adapters for callbacks queued before script migration.",
        "eu5ab_gui_queue_sync_check = {",
        "    saved_scopes = { eu5ab_engine_queue_check_stage }",
        "    is_valid = { always = yes }",
        "    effect = { if = { limit = { NOT = { has_variable = eu5ab_bridge_schema } } eu5ab_tick_engine_script_queue = yes } }",
        "}",
        "eu5ab_gui_queue_confirm_candidate = {",
        f"    saved_scopes = {{ {CANDIDATE_BUILDING_SCOPE} eu5ab_engine_country {building_capacity.GUI_SCOPES} eu5ab_engine_replaced_building }}",
        "    is_valid = { always = yes }",
        "    effect = { if = { limit = { owner = scope:eu5ab_engine_country owner = { NOT = { has_variable = eu5ab_bridge_schema } has_variable = eu5ab_q_active has_variable = eu5ab_q_fire eu5ab_queue_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load } } } eu5ab_confirm_requested_engine_candidate = yes } }",
        "}",
        "eu5ab_gui_queue_confirm_sync = {",
        "    is_valid = { always = yes }",
        "    effect = { if = { limit = { NOT = { has_variable = eu5ab_bridge_schema } } eu5ab_tick_engine_script_confirmation = yes } }",
        "}",
        "",
    ]
    # All country queue gates share the month/date barrier. Native reader
    # controllers remain usable during the 2--21 scanning period.
    text = "\n".join(chunks).replace(
        "NOT = { has_variable = eu5ab_scan_resume_after_load }",
        "eu5ab_queue_calendar_open = yes NOT = { has_variable = eu5ab_scan_resume_after_load }",
    ) + queue_gui_commands.render_guis(phase_count)
    text = text.replace('eu5ab_capture_building_capacity = yes eu5ab_confirm_requested_engine_candidate', 'eu5ab_confirm_requested_engine_candidate')
    return queue_bridge.wrap_candidate_guis(text, _replace_top_level_script_block) + queue_bridge.render_guis() + quote_cache.render_guis() + winner_batch.render_guis()


def render_engine_queue_gui() -> str:
    def engine_arguments() -> str:
        return (
            "GuiScope.SetRoot(Location.MakeScope)"
            f".AddScope('{CANDIDATE_BUILDING_SCOPE}', BuildingType.MakeScope)"
            ".AddScope('eu5ab_engine_country', GetPlayer.MakeScope)"
            ".AddScope('eu5ab_engine_cost', MakeScopeValue(GetBuildOrExpandBuildingCost(BuildingType.Self, Location.Self)))"
            ".AddScope('eu5ab_engine_income', MakeScopeValue(GetBuildingTypeIncomeToOwnerInLocation(BuildingType.Self, Location.Self)))"
            ".AddScope('eu5ab_engine_profit', MakeScopeValue(GetBuildingTypeProfitInLocation(BuildingType.Self, Location.Self)))"
            ".AddScope('eu5ab_engine_can_build', MakeScopeBool(CanBuildOrExpandBuilding(BuildingType.Self, Location.Self)))"
            ".AddScope('eu5ab_engine_province_food_balance', MakeScopeValue(Add_CFixedPoint(Location.GetProvince.GetMonthlyFood, Location.GetProvince.GetFoodFromMarket)))"
            ".AddScope('eu5ab_engine_province_food_natural', MakeScopeValue(Location.GetProvince.GetMonthlyFood))"
            ".AddScope('eu5ab_engine_rgo_revenue', MakeScopeValue(Location.GetRawMaterialsPrice))"
            + building_capacity.gui_arguments(replacement=True, capacity_used=False)
        )

    return queue_bridge.render_widget(engine_arguments())


def render_scripted_guis(
    policies: list[Policy],
    catalog: BuildingCatalog,
    rules: AutomationRules,
) -> str:
    chunks = ["# Generated by eu5autobuild.generator.", "# scripted_gui definitions for the slot-based Advanced Auto Build template editor."]
    default_policy_value = _policy_index(policies[0], 0) if policies else "1"
    priority_step_var = "eu5ab_priority_adjust_step"

    def add_gui(
        gui_id: str,
        effect_lines: list[str],
        *,
        saved_scope: str | None = None,
    ) -> None:
        chunks.extend([
            f"{gui_id} = {{",
            "\tscope = country",
            *([f"\tsaved_scopes = {{ {saved_scope} }}"] if saved_scope else []),
            "\tis_shown = { always = yes }",
            (f"\tis_valid = {{ exists = scope:{saved_scope} }}" if saved_scope
             else "\tis_valid = { always = yes }"),
            "\teffect = {",
            *effect_lines,
            "\t}",
            "}",
            "",
        ])

    def add_toggle(gui_id: str, variable: str) -> None:
        add_gui(gui_id, [
            "\t\tif = {",
            f"\t\t\tlimit = {{ var:{variable} = 1 }}",
            f"\t\t\tset_variable = {{ name = {variable} value = 0 }}",
            "\t\t}",
            "\t\telse = {",
            f"\t\t\tset_variable = {{ name = {variable} value = 1 }}",
            "\t\t}",
            "\t\teu5ab_commit_active_template_editor = yes",
        ])

    def add_priority_adjust(gui_id: str, variable: str, operation: str) -> None:
        add_gui(gui_id, [
            f"\t\tif = {{ limit = {{ NOT = {{ has_variable = {variable} }} }} set_variable = {{ name = {variable} value = 0 }} }}",
            f"\t\tif = {{ limit = {{ NOT = {{ has_variable = {priority_step_var} }} }} set_variable = {{ name = {priority_step_var} value = 0.1 }} }}",
            f"\t\tchange_variable = {{ name = {variable} {operation} = var:{priority_step_var} }}",
            f"\t\tclamp_variable = {{ name = {variable} min = 0 max = 10 }}",
            f"\t\tremove_variable = {priority_step_var}",
            "\t\teu5ab_commit_active_template_editor = yes",
        ])

    chunks.extend([
        "# CMF Action Bar visibility/validity contract. The scripted GUI name must match the element id.",
        "eu5ab_action_bar = {",
        "\tscope = country",
        "\tis_shown = { is_human = yes }",
        "\tis_valid = { is_human = yes }",
        "}",
        "",
        "# CMM uses this hook both for conditional visibility and optional change effects.",
        f"{CMM_SETTING_PREFIX}fixed_annual_budget_on_changed = {{",
        "\tscope = country",
        "\tis_shown = {",
        f"\t\t{_cmm_setting_value('budget_mode')} = {CMM_BUDGET_MODE_FIXED}",
        "\t}",
        "\teffect = { }",
        "}",
        "",
        "# Planning shortlist size is relevant only to supply-demand planning.",
        f"{CMM_SETTING_PREFIX}candidates_per_location_on_changed = {{",
        "\tscope = country",
        "\tis_shown = {",
        f"\t\t{_cmm_setting_value('candidate_ranking_mode')} = {CMM_CANDIDATE_RANKING_COMPOSITE}",
        "\t}",
        "\teffect = { }",
        "}",
        "",
        "# Profit shortlist size is relevant only to predicted-profit selection.",
        f"{CMM_SETTING_PREFIX}actual_profit_candidates_per_location_on_changed = {{",
        "\tscope = country",
        "\tis_shown = {",
        f"\t\t{_cmm_setting_value('candidate_ranking_mode')} = {CMM_CANDIDATE_RANKING_ACTUAL_PROFIT}",
        "\t}",
        "\teffect = { }",
        "}",
        "",
    ])
    chunks.extend([
        f"{CMM_SETTING_PREFIX}rgo_forced_relaxed_on_changed = {{",
        "\tscope = country",
        f"\tis_shown = {{ {_cmm_setting_value('pause_low_workforce')} <= 0 }}",
        "\teffect = { }",
        "}", "",
    ])
    for setting_id in ("job_fill_deadline_months", "rgo_workforce_mode", "rgo_job_fill_deadline_months"):
        chunks.extend([
            f"{CMM_SETTING_PREFIX}{setting_id}_on_changed = {{",
            "\tscope = country",
            "\tis_shown = {",
            f"\t\t{_cmm_setting_value('pause_low_workforce')} > 0",
            *([f"\t\t{_cmm_setting_value('rgo_workforce_mode')} = 2"] if setting_id == "rgo_job_fill_deadline_months" else []),
            "\t}",
            "\teffect = { }",
            "}", "",
        ])
    for setting_id in ("governor_migration_enabled", "governor_migration_threshold_percent", "naval_governor_migration_threshold_percent"):
        chunks.extend([
            f"{CMM_SETTING_PREFIX}{setting_id}_on_changed = {{",
            "\tscope = country",
            f"\tis_shown = {{ {_cmm_setting_value('governor_relocation_enabled')} > 0 }}",
            "\teffect = { }",
            "}",
            "",
        ])
    for warning_setting in CMM_PERFORMANCE_WARNING_SETTINGS:
        strategy_visibility_lines: list[str] = []
        if warning_setting in CMM_PERFORMANCE_PLANNING_WARNING_SETTINGS:
            strategy_visibility_lines.append(
                f"\t\t{_cmm_setting_value('candidate_ranking_mode')} = {CMM_CANDIDATE_RANKING_COMPOSITE}",
            )
        elif warning_setting in CMM_PERFORMANCE_PROFIT_WARNING_SETTINGS:
            strategy_visibility_lines.append(
                f"\t\t{_cmm_setting_value('candidate_ranking_mode')} = {CMM_CANDIDATE_RANKING_ACTUAL_PROFIT}",
            )
        chunks.extend([
            "# Display-only CMM row shown while the maximum-throughput preset is active.",
            f"{CMM_SETTING_PREFIX}{warning_setting}_on_changed = {{",
            "\tscope = country",
            "\tis_shown = {",
            f"\t\t{_cmm_setting_value('performance_preset')} = {CMM_PERFORMANCE_PRESET_THROUGHPUT}",
            *strategy_visibility_lines,
            "\t}",
            "\tis_valid = { always = no }",
            "\teffect = { }",
            "}",
            "",
        ])
    add_gui(f"{CMM_SETTING_PREFIX}{CMM_CANDIDATE_PRIORITY_SETTING}_on_changed", [
        f"\t\tcmm_apply_list_change = {{ setting = {CMM_SETTING_PREFIX}{CMM_CANDIDATE_PRIORITY_SETTING} }}",
        "\t\teu5ab_rebuild_candidate_priority = yes",
    ])
    add_gui("eu5ab_gui_clear_cmf_window_request", [
        "\t\tremove_variable = eu5ab_cmf_window_requested",
    ])
    add_gui("eu5ab_gui_open_presets_tab", [
        f"\t\tset_variable = {{ name = eu5ab_active_preset_policy value = {default_policy_value} }}",
        "\t\tremove_variable = eu5ab_active_template_slot",
        "\t\tremove_variable = eu5ab_custom_templates_empty",
    ])
    add_gui("eu5ab_gui_open_player_templates", [
        "\t\tremove_variable = eu5ab_active_preset_policy",
        "\t\teu5ab_select_first_player_template = yes",
        "\t\t# Scope view is prepared only when its window is opened.",
    ])
    def add_new_template_gui(gui_id: str, loader: str) -> None:
        add_gui(gui_id, [
            "\t\tremove_variable = eu5ab_template_slot_claimed",
            "\t\tremove_variable = eu5ab_custom_templates_empty",
            "\t\tremove_variable = eu5ab_active_preset_policy",
            *[
                line
                for slot in TEMPLATE_SLOTS
                for line in [
                    "\t\tif = {",
                    f"\t\t\tlimit = {{ NOT = {{ has_variable = eu5ab_template_slot_claimed }} NOT = {{ has_variable = {_slot_var(slot, 'exists')} }} }}",
                    f"\t\t\tset_variable = {{ name = eu5ab_active_template_slot value = {slot} }}",
                    f"\t\t\t{loader} = yes",
                    f"\t\t\teu5ab_commit_template_editor_to_slot_{slot}_and_refresh_budget = yes",
                    "\t\t\tset_variable = { name = eu5ab_template_slot_claimed value = 1 }",
                    "\t\t}",
                ]
            ],
            "\t\tremove_variable = eu5ab_template_slot_claimed",
        ])

    add_new_template_gui(
        "eu5ab_gui_new_blank_player_template",
        "eu5ab_load_blank_template_into_editor",
    )
    add_new_template_gui(
        "eu5ab_gui_new_recommended_player_template",
        "eu5ab_load_recommended_template_into_editor",
    )
    # Compatibility alias for older GUI references and submods.
    add_new_template_gui(
        "eu5ab_gui_new_player_template",
        "eu5ab_load_new_template_into_editor",
    )
    for index, policy in enumerate(policies):
        policy_value = _policy_index(policy, index)
        add_gui(f"eu5ab_gui_open_preset_{policy.id}", [
            f"\t\tset_variable = {{ name = eu5ab_active_preset_policy value = {policy_value} }}",
            "\t\tremove_variable = eu5ab_active_template_slot",
            "\t\tremove_variable = eu5ab_custom_templates_empty",
        ])
        add_gui(f"eu5ab_gui_open_preset_locations_{policy.id}", [
            f"\t\tset_variable = {{ name = eu5ab_active_preset_policy value = {policy_value} }}",
            "\t\tremove_variable = eu5ab_active_template_slot",
            "\t\tremove_variable = eu5ab_custom_templates_empty",
        ])
        add_gui(f"eu5ab_gui_open_preset_scope_{policy.id}", [
            f"\t\tset_variable = {{ name = eu5ab_active_preset_policy value = {policy_value} }}",
            "\t\tremove_variable = eu5ab_active_template_slot",
            "\t\tremove_variable = eu5ab_custom_templates_empty",
            "\t\tset_variable = { name = eu5ab_scope_view_mode value = 2 }",
            f"\t\tset_variable = {{ name = eu5ab_scope_view_value value = {policy_value} }}",
            "\t\teu5ab_prepare_template_scope_view = yes",
        ])
        add_gui(f"eu5ab_gui_toggle_preset_{policy.id}_paused", [
            "\t\tif = {",
            f"\t\t\tlimit = {{ has_variable = {_preset_paused_var(policy.id)} }}",
            f"\t\t\tremove_variable = {_preset_paused_var(policy.id)}",
            "\t\t}",
            "\t\telse = {",
            f"\t\t\tset_variable = {{ name = {_preset_paused_var(policy.id)} value = 1 }}",
            "\t\t}",
        ])
        copy_lines = [
            "\t\tremove_variable = eu5ab_template_slot_claimed",
            "\t\tremove_variable = eu5ab_custom_templates_empty",
        ]
        for slot in TEMPLATE_SLOTS:
            copy_lines.extend([
                "\t\tif = {",
                f"\t\t\tlimit = {{ NOT = {{ has_variable = eu5ab_template_slot_claimed }} NOT = {{ has_variable = {_slot_var(slot, 'exists')} }} }}",
                f"\t\t\tset_variable = {{ name = eu5ab_active_template_slot value = {slot} }}",
                f"\t\t\teu5ab_load_preset_{policy.id}_into_editor = yes",
                f"\t\t\teu5ab_commit_template_editor_to_slot_{slot}_and_refresh_budget = yes",
                "\t\t\tset_variable = { name = eu5ab_template_slot_claimed value = 1 }",
                "\t\t}",
            ])
        copy_lines.extend([
            "\t\tremove_variable = eu5ab_template_slot_claimed",
            "\t\tremove_variable = eu5ab_active_preset_policy",
        ])
        add_gui(
            f"eu5ab_gui_copy_preset_{policy.id}_to_player_template",
            copy_lines,
        )


    for slot in TEMPLATE_SLOTS:
        open_lines = [
            "\t\tremove_variable = eu5ab_active_preset_policy",
            "\t\tremove_variable = eu5ab_custom_templates_empty",
            f"\t\teu5ab_load_template_slot_{slot}_into_editor = yes",
        ]
        add_gui(f"eu5ab_gui_edit_template_slot_{slot}", open_lines)
        add_gui(f"eu5ab_gui_open_player_template_slot_{slot}", open_lines)
        add_gui(f"eu5ab_gui_open_template_locations_slot_{slot}", open_lines)
        add_gui(f"eu5ab_gui_open_template_buildings_slot_{slot}", [
            *open_lines,
            "\t\tset_variable = { name = eu5ab_edit_building_filter value = 0 }",
            "\t\tset_variable = { name = eu5ab_edit_building_age value = 0 }",
            "\t\tclamp_variable = { name = eu5ab_edit_building_filter min = 0 max = 5 }",
            "\t\tclamp_variable = { name = eu5ab_edit_building_age min = 0 max = 6 }",
        ])
        add_gui(f"eu5ab_gui_open_template_rules_slot_{slot}", [
            *open_lines,
        ])
        add_gui(f"eu5ab_gui_open_template_scope_slot_{slot}", [
            *open_lines,
            "\t\tset_variable = { name = eu5ab_scope_view_mode value = 1 }",
            f"\t\tset_variable = {{ name = eu5ab_scope_view_value value = {slot} }}",
            "\t\teu5ab_prepare_template_scope_view = yes",
        ])
        for name_value, name_id in TEMPLATE_NAME_CHOICES:
            custom = name_id == "custom"
            name_lines = (
                [
                    f"\t\tset_variable = {{ name = {_slot_custom_name_var(slot)} value = scope:eu5ab_template_name_input }}",
                    f"\t\tset_variable = {{ name = {_editor_var('custom_name')} value = scope:eu5ab_template_name_input }}",
                ] if custom else [
                    f"\t\tremove_variable = {_slot_custom_name_var(slot)}",
                    f"\t\tremove_variable = {_editor_var('custom_name')}",
                ]
            )
            add_gui(f"eu5ab_gui_slot_{slot}_name_{name_id}", [
                *name_lines,
                f"\t\tset_variable = {{ name = {_slot_var(slot, 'name_id')} value = {name_value} }}",
                f"\t\tset_variable = {{ name = {_slot_var(slot, 'name_selected')} value = 1 }}",
                f"\t\tset_variable = {{ name = {_editor_var('name_id')} value = {name_value} }}",
                f"\t\tset_variable = {{ name = {_editor_var('name_selected')} value = 1 }}",
                f"\t\tset_variable = {{ name = {_slot_var(slot, 'saved')} value = 1 }}",
            ], saved_scope="eu5ab_template_name_input" if custom else None)
        for dst in TEMPLATE_SLOTS:
            if dst == slot:
                continue
            add_gui(
                f"eu5ab_gui_copy_slot_{slot}_to_slot_{dst}",
                [f"\t\teu5ab_copy_template_slot_{slot}_to_slot_{dst} = yes"],
            )
        add_gui(f"eu5ab_gui_copy_active_template_to_slot_{slot}", [
            f"\t\teu5ab_commit_template_editor_to_slot_{slot}_and_refresh_budget = yes",
        ])

        delete_lines = [
            "\t\t# A deleted template must not leave locations pointing at a reusable slot.",
            "\t\tevery_owned_location = {",
            f"\t\t\tlimit = {{ has_variable = eu5ab_template_slot var:eu5ab_template_slot = {slot} }}",
            "\t\t\teu5ab_clear_location_policy = yes",
            "\t\t}",
            "\t\t# Reset the reusable slot through the blank editor path without duplicating hundreds of fields here.",
            "\t\teu5ab_load_blank_template_into_editor = yes",
            f"\t\teu5ab_commit_template_editor_to_slot_{slot}_and_refresh_budget = yes",
            f"\t\tremove_variable = {_slot_var(slot, 'saved')}",
            f"\t\tremove_variable = {_slot_var(slot, 'exists')}",
            f"\t\tremove_variable = {_slot_var(slot, 'paused')}",
            "\t\tremove_variable = eu5ab_active_template_slot",
            "\t\teu5ab_select_first_player_template = yes",
        ]
        add_gui(f"eu5ab_gui_delete_template_slot_{slot}", delete_lines)
        add_gui(f"eu5ab_gui_toggle_template_slot_{slot}_paused", [
            "\t\tif = {",
            f"\t\t\tlimit = {{ has_variable = {_slot_var(slot, 'paused')} }}",
            f"\t\t\tremove_variable = {_slot_var(slot, 'paused')}",
            "\t\t}",
            "\t\telse = {",
            f"\t\t\tset_variable = {{ name = {_slot_var(slot, 'paused')} value = 1 }}",
            "\t\t}",
        ])


    for step_id, step in (("default", 0.1), ("ctrl", 0.5), ("shift", 1)):
        add_gui(f"eu5ab_gui_priority_step_{step_id}", [
            f"\t\tset_variable = {{ name = {priority_step_var} value = {step:g} }}",
        ])

    for building_id in _catalog_building_ids(catalog):
        variable = _editor_priority_var(building_id)
        add_priority_adjust(
            f"eu5ab_gui_active_priority_dec_{building_id}",
            variable,
            "subtract",
        )
        add_priority_adjust(
            f"eu5ab_gui_active_priority_inc_{building_id}",
            variable,
            "add",
        )

    for value in range(6):
        add_gui(f"eu5ab_gui_active_building_filter_{value}", [
            f"\t\tset_variable = {{ name = eu5ab_edit_building_filter value = {value} }}",
        ])
    for value in range(7):
        add_gui(f"eu5ab_gui_active_building_age_{value}", [
            f"\t\tset_variable = {{ name = eu5ab_edit_building_age value = {value} }}",
        ])

    clear_visible_lines: list[str] = []
    for building_id in _catalog_building_ids(catalog):
        building = catalog.get(building_id)
        if building is None:
            raise ValueError(f"Unknown building in active editor: {building_id}")
        filter_id = _building_filter_id(building_id, catalog)
        clear_visible_lines.extend([
            "\t\tif = {",
            "\t\t\tlimit = {",
            f"\t\t\t\tOR = {{ var:eu5ab_edit_building_filter = 0 var:eu5ab_edit_building_filter = {filter_id} }}",
            f"\t\t\t\tOR = {{ var:eu5ab_edit_building_age = 0 var:eu5ab_edit_building_age = {building.age} }}",
        ])
        if building.is_special:
            clear_visible_lines.extend([
                "\t\t\t\tany_owned_location = {",
                f"\t\t\t\t\tlocation_and_owner_can_build = {{ building_type = {building_id} }}",
                "\t\t\t\t}",
            ])
        clear_visible_lines.extend([
            "\t\t\t}",
            f"\t\t\tset_variable = {{ name = {_editor_priority_var(building_id)} value = 0 }}",
            "\t\t}",
        ])
    clear_visible_lines.append("\t\teu5ab_commit_active_template_editor = yes")
    add_gui("eu5ab_gui_clear_visible_priorities", clear_visible_lines)

    for building in catalog.buildings.values():
        if not building.is_special:
            continue
        chunks.extend([
            f"eu5ab_gui_special_building_available_{building.id} = {{",
            "\tscope = country",
            "\tis_shown = {",
            "\t\tany_owned_location = {",
            f"\t\t\tlocation_and_owner_can_build = {{ building_type = {building.id} }}",
            "\t\t}",
            "\t}",
            "\tis_valid = { always = yes }",
            "\teffect = { }",
            "}",
            "",
        ])

    chunks.extend([
        "eu5ab_gui_expand_scope_province = {",
        "\tscope = location",
        "\tis_shown = { always = yes }",
        "\tis_valid = { always = yes }",
        "\teffect = {",
        "\t\tset_variable = { name = eu5ab_scope_view_expanded value = 1 }",
        "\t}",
        "}",
        "",
        "eu5ab_gui_collapse_scope_province = {",
        "\tscope = location",
        "\tis_shown = { always = yes }",
        "\tis_valid = { always = yes }",
        "\teffect = {",
        "\t\tremove_variable = eu5ab_scope_view_expanded",
        "\t}",
        "}",
        "",
    ])

    chunks.extend([
        "eu5ab_gui_active_template_has_locations_in_province = {",
        "\tscope = location",
        "\tis_shown = {",
        "\t\tprovince = {",
        "\t\t\tany_location_in_province = { has_variable = eu5ab_scope_view_selected }",
        "\t\t}",
        "\t}",
        "\tis_valid = { always = yes }",
        "\teffect = { }",
        "}",
        "",
    ])
    chunks.extend([
        "eu5ab_gui_clear_location_template = {",
        "\tscope = country",
        "\tsaved_scopes = { target_location }",
        "\tis_shown = {",
        "\t\tscope:target_location ?= {",
        "\t\thas_owner = yes",
        "\t\towner ?= { is_human = yes }",
        "\t\thas_variable = eu5ab_policy_id",
        "\t\t}",
        "\t}",
        "\tis_valid = { always = yes }",
        "\teffect = {",
        "\t\tscope:target_location ?= {",
        "\t\teu5ab_clear_location_policy = yes",
        "\t\t}",
        "\t\teu5ab_prepare_template_scope_view = yes",
        "\t}",
        "}",
        "",
        "eu5ab_gui_clear_current_template_scope = {",
        "\tscope = country",
        "\tis_shown = { always = yes }",
        "\tis_valid = { var:eu5ab_scope_location_count > 0 }",
        "\teffect = {",
        "\t\tevery_owned_location = {",
        "\t\t\tif = {",
        "\t\t\t\tlimit = {",
        "\t\t\t\t\troot = { var:eu5ab_scope_view_mode = 1 }",
        "\t\t\t\t\thas_variable = eu5ab_template_slot",
        "\t\t\t\t\tvar:eu5ab_template_slot = root.var:eu5ab_scope_view_value",
        "\t\t\t\t}",
        "\t\t\t\teu5ab_clear_location_policy = yes",
        "\t\t\t}",
        "\t\t\telse_if = {",
        "\t\t\t\tlimit = {",
        "\t\t\t\t\troot = { var:eu5ab_scope_view_mode = 2 }",
        "\t\t\t\t\tNOT = { has_variable = eu5ab_template_slot }",
        "\t\t\t\t\thas_variable = eu5ab_policy_id",
        "\t\t\t\t\tvar:eu5ab_policy_id = root.var:eu5ab_scope_view_value",
        "\t\t\t\t}",
        "\t\t\t\teu5ab_clear_location_policy = yes",
        "\t\t\t}",
        "\t\t}",
        "\t\teu5ab_prepare_template_scope_view = yes",
        "\t}",
        "}",
        "",
    ])
    chunks.extend(render_engine_queue_scripted_guis(rules).splitlines())
    chunks.append(building_capacity.render_guis())
    chunks.append(rgo_queue.render_guis())
    return "\n".join(chunks)


def render_actions(policies: list[Policy], catalog: BuildingCatalog) -> str:
    def select_action(
        action_id: str,
        looking_for: str,
        target_flag: str,
        name_key: str,
        tooltip_key: str,
        effect_lines: list[str],
        *,
        assigned: bool = False,
    ) -> list[str]:
        state_limit = "has_variable = eu5ab_policy_id" if assigned else "NOT = { has_variable = eu5ab_policy_id }"
        if looking_for == "location":
            source_lines = [
                "\t\tinteraction_source_list = {",
                "\t\t\tscope:actor = {",
                "\t\t\t\tevery_owned_location = {",
                f"\t\t\t\t\tlimit = {{ {state_limit} }}",
                "\t\t\t\t\tadd_to_list = source",
                "\t\t\t\t}",
                "\t\t\t}",
                "\t\t}",
            ]
        else:
            geography_scope = "province" if looking_for == "province" else "area"
            source_lines = [
                "\t\tinteraction_source_list = {",
                "\t\t\tscope:actor = {",
                "\t\t\t\tevery_owned_location = {",
                f"\t\t\t\t\tlimit = {{ {state_limit} }}",
                f"\t\t\t\t\t{geography_scope} = {{",
                "\t\t\t\t\t\tif = {",
                "\t\t\t\t\t\t\tlimit = { NOT = { is_in_list = source } }",
                "\t\t\t\t\t\t\tadd_to_list = source",
                "\t\t\t\t\t\t}",
                "\t\t\t\t\t}",
                "\t\t\t\t}",
                "\t\t\t}",
                "\t\t}",
            ]
        # Candidates are already restricted to the actor's owned locations and their
        # deduplicated parent geographies. Avoid re-evaluating ownership per row.
        visible_line = "\t\tvisible = { always = yes }"
        return [
            f"{action_id} = {{",
            "\ttype = owncountry",
            "\tplayer_automated_category = buildings",
            "\tshow_in_gui_list = no",
            "\tshow_message = no",
            "\tai_tick = never",
            "\tautomation_tick = never",
            "\tpotential = { always = yes }",
            "\tallow = { always = yes }",
            "\tselect_trigger = {",
            f"\t\tlooking_for_a = {looking_for}",
            *source_lines,
            f"\t\ttarget_flag = {target_flag}",
            f"\t\tname = {name_key}",
            "\t\tmap_mode = raw_material",
            "\t\tbottom_widget = eu5ab_automation_policy_footer",
            "\t\tcolumn = { data = name }",
            "\t\tcolumn = { data = population }",
            visible_line,
            "\t\tenabled = { always = yes }",
            f"\t\ttooltip_msg_key = {tooltip_key}",
            "\t}",
            "\teffect = {",
            *effect_lines,
            "\t\t# Scope view is rebuilt on demand, never during map selection.",
            "\t}",
            "\tai_will_do = { value = 0 }",
            "}",
            "",
        ]

    def select_location_action(action_id: str, effect_lines: list[str], *, assigned: bool = False) -> list[str]:
        return select_action(action_id, "location", "target_location", "eu5ab_choose_location", "eu5ab_location_select_tooltip", effect_lines, assigned=assigned)

    def select_province_action(action_id: str, effect_lines: list[str], *, assigned: bool = False) -> list[str]:
        return select_action(action_id, "province", "target_province", "eu5ab_choose_province", "eu5ab_province_select_tooltip", effect_lines, assigned=assigned)

    def select_area_action(action_id: str, effect_lines: list[str], *, assigned: bool = False) -> list[str]:
        return select_action(action_id, "area", "target_area", "eu5ab_choose_area", "eu5ab_area_select_tooltip", effect_lines, assigned=assigned)

    chunks = [
        "# Generated by eu5autobuild.generator.",
        "# Generic actions used by the visible controls in the Advanced Auto Build window.",
        "",
    ]
    for policy in policies:
        chunks.extend(select_location_action(f"eu5ab_apply_preset_{policy.id}_to_selected_location", [
            "\t\tscope:target_location ?= {",
            f"\t\t\teu5ab_apply_policy_{policy.id}_to_location = yes",
            "\t\t\tremove_variable = eu5ab_template_slot",
            "\t\t}",
        ]))
        chunks.extend(select_province_action(f"eu5ab_apply_preset_{policy.id}_to_selected_province", [
            "\t\tscope:target_province ?= {",
            "\t\t\tevery_location_in_province = {",
            "\t\t\t\tlimit = { owner ?= scope:actor NOT = { has_variable = eu5ab_policy_id } }",
            f"\t\t\t\teu5ab_apply_policy_{policy.id}_to_location = yes",
            "\t\t\t\tremove_variable = eu5ab_template_slot",
            "\t\t\t}",
            "\t\t}",
        ]))
        chunks.extend(select_area_action(f"eu5ab_apply_preset_{policy.id}_to_selected_area", [
            "\t\tscope:target_area ?= {",
            "\t\t\tevery_location_in_area = {",
            "\t\t\t\tlimit = { owner ?= scope:actor NOT = { has_variable = eu5ab_policy_id } }",
            f"\t\t\t\teu5ab_apply_policy_{policy.id}_to_location = yes",
            "\t\t\t\tremove_variable = eu5ab_template_slot",
            "\t\t\t}",
            "\t\t}",
        ]))
    for slot in TEMPLATE_SLOTS:
        chunks.extend(select_location_action(f"eu5ab_apply_template_slot_{slot}_to_selected_location", [
            "\t\tscope:target_location ?= {",
            f"\t\t\tset_variable = {{ name = eu5ab_policy_id value = {CUSTOM_POLICY_VALUE} }}",
            f"\t\t\tset_variable = {{ name = eu5ab_template_slot value = {slot} }}",
            "\t\t\tremove_variable = eu5ab_policy_decoupled",
            "\t\t\teu5ab_register_location_for_scan = yes",
            "\t\t}",
        ]))
        chunks.extend(select_province_action(f"eu5ab_apply_template_slot_{slot}_to_selected_province", [
            "\t\tscope:target_province ?= {",
            "\t\t\tevery_location_in_province = {",
            "\t\t\t\tlimit = { owner ?= scope:actor NOT = { has_variable = eu5ab_policy_id } }",
            f"\t\t\t\tset_variable = {{ name = eu5ab_policy_id value = {CUSTOM_POLICY_VALUE} }}",
            f"\t\t\t\tset_variable = {{ name = eu5ab_template_slot value = {slot} }}",
            "\t\t\t\tremove_variable = eu5ab_policy_decoupled",
            "\t\t\t\teu5ab_register_location_for_scan = yes",
            "\t\t\t}",
            "\t\t}",
        ]))
        chunks.extend(select_area_action(f"eu5ab_apply_template_slot_{slot}_to_selected_area", [
            "\t\tscope:target_area ?= {",
            "\t\t\tevery_location_in_area = {",
            "\t\t\t\tlimit = { owner ?= scope:actor NOT = { has_variable = eu5ab_policy_id } }",
            f"\t\t\t\tset_variable = {{ name = eu5ab_policy_id value = {CUSTOM_POLICY_VALUE} }}",
            f"\t\t\t\tset_variable = {{ name = eu5ab_template_slot value = {slot} }}",
            "\t\t\t\tremove_variable = eu5ab_policy_decoupled",
            "\t\t\t\teu5ab_register_location_for_scan = yes",
            "\t\t\t}",
            "\t\t}",
        ]))
    chunks.extend(select_location_action("eu5ab_decouple_selected_location", [
        "\t\tscope:target_location ?= { set_variable = eu5ab_policy_decoupled }",
    ], assigned=True))

    clear_lines = [
        "\t\tscope:target_location ?= {",
        "\t\t\teu5ab_clear_location_policy = yes",
    ]
    clear_lines.extend([
        "\t\t}",
    ])
    chunks.extend(select_location_action("eu5ab_clear_selected_location_policy", clear_lines, assigned=True))
    return "\n".join(chunks)


def _gui_scripted_button(
    gui_id: str,
    text_key: str,
    width: int = 58,
    tooltip_key: str | None = None,
) -> str:
    text_width = max(width - 8, 32)
    tooltip_key = tooltip_key or text_key
    return f"""button_regular = {{
						size = {{ {width} 40 }}
						tooltip = "{tooltip_key}"
						text_single = {{
							size = {{ {text_width} 36 }}
							parentanchor = center
							autoresize = no
							maximumsize = {{ {text_width} 36 }}
							fontsize = 14
							fontsize_min = 10
							align = center|nobaseline
							elide = right
							text = "{text_key}"
						}}
						onclick = "[GetScriptedGui('{gui_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
					}}"""


def _gui_select_action_button(action_id: str, text_key: str, desc_key: str) -> str:
    # EU5 1.4 dispatches generic actions through regular button tooltips;
    # the old action_button widget and left_action property no longer exist.
    return f"""button_regular = {{
					size = {{ 176 36 }}
					visible = "[PdxGuiWidget.IsUberButtonVisible]"
					enabled = "[PdxGuiWidget.IsUberButtonEnabled]"
					scripted_action_tooltip = {{
						click_type = left
						click_mode = single
						action_name = "{action_id}"
						actor = "[Player]"
					}}
					tooltip = "{desc_key}"
					text_single = {{
						size = {{ 168 32 }}
						parentanchor = center
						autoresize = no
						maximumsize = {{ 168 32 }}
						fontsize = 13
						fontsize_min = 9
						align = center|nobaseline
						elide = right
						text = "{text_key}"
					}}
				}}"""


def _building_filter_id(building_id: str, catalog: BuildingCatalog) -> int:
    building = catalog.get(building_id)
    if building is None:
        return 5
    if building.is_special:
        return 5
    workforce = set(building.workforce_pop_types)
    if "soldiers" in workforce:
        return 4
    if "burghers" in workforce:
        return 3
    if "laborers" in workforce:
        return 2
    if workforce & {"peasants", "slaves"}:
        return 1
    return 5


def _rules_help_template_name(title_key: str) -> str:
    return f"EU5ABRulesHelp_{title_key}"


def _gui_ogas_card(
    icon: str,
    title_key: str,
    content: str,
    visible: str | None = None,
    max_width: int = 860,
    tooltip_key: str | None = None,
) -> str:
    visible_line = f'\n					visible = "{visible}"' if visible is not None else ""
    help_widget = (
        f'''
						icon = {{
							size = {{ 24 24 }}
							texture = "{INFO_ICON}"
							texture_density = 2
							tooltipwidget = {{ using = {_rules_help_template_name(title_key)} }}
						}}'''
        if tooltip_key is not None
        else ""
    )
    return f"""vbox = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = preferred
					layoutstretchfactor_horizontal = 1
					using = bg_square_wood_tile
					using = bg_cabinet_card_frame
					max_width = {max_width}
					margin = {{ 10 6 }}
					spacing = 5{visible_line}

					hbox = {{
						layoutpolicy_horizontal = expanding
						spacing = 6
						icon = {{
							size = {{ 28 28 }}
							texture = "{icon}"
							texture_density = 2
						}}
						text_single = {{
							layoutpolicy_horizontal = expanding
							size = {{ -1 28 }}
							default_format = "#yellow_titles"
							fontsize = 16
							fontsize_min = 12
							align = left|vcenter
							text = "{title_key}"
						}}
{help_widget}
					}}

					vbox = {{
						layoutpolicy_horizontal = expanding
						layoutpolicy_vertical = preferred
						spacing = 5
{content}
					}}
				}}"""


def _render_rules_help_tooltips() -> str:
    definitions = [
        ("eu5ab_ranking_mode_section_title", "eu5ab_ranking_mode_help", PREDICTION_ICON),
        ("eu5ab_diag_overview_title", "eu5ab_diagnostics_snapshot_help", PREDICTION_ICON),
        ("eu5ab_diag_quota_title", "eu5ab_quota_help", CASH_ICON),
        ("eu5ab_diag_result_title", "eu5ab_diag_result_help", BUILDING_RULES_ICON),
        ("eu5ab_diag_rgo_title", "eu5ab_diag_rgo_help", BUILDING_RULES_ICON),
        ("eu5ab_diag_failure_title", "eu5ab_diag_failure_help", MISSING_GOODS_ICON),
        ("eu5ab_diag_candidates_title", "eu5ab_diag_candidates_help", PREDICTION_ICON),
    ]
    return "\n\n".join(
        f"""template {_rules_help_template_name(title_key)} {{
	ConceptTooltipType = {{
		blockoverride "title_icon" {{ icon = {{ texture = "{icon}" using = tooltip_concept_title_icon_size }} }}
		blockoverride "title_text" {{ text = "{title_key}" }}
		blockoverride "tooltip_content" {{ TooltipTextBlock = {{ blockoverride "text" {{ text = "{body_key}" }} }} }}
	}}
}}"""
        for title_key, body_key, icon in definitions
    )


def _slot_custom_name_var(slot: int) -> str:
    return f"eu5ab_tpl_{slot}_custom_name"


def _slot_display_name_expr(slot: int, *, player: str = "Player") -> str:
    name_variable = _slot_var(slot, "name_id")
    preset_origin = _slot_var(slot, "preset_origin")
    custom_name = _slot_custom_name_var(slot)
    saved_display = f"Localize('eu5ab_template_slot_{slot}_title')"
    for name_value, name_id in reversed(TEMPLATE_NAME_CHOICES):
        saved_display = (
            "Select_CString("
            f"EqualTo_CFixedPoint({player}.MakeScope.GetVariable('{name_variable}').GetValue,"
            f"'(CFixedPoint){name_value}'),"
            f"Localize('eu5ab_template_name_{name_id}'),{saved_display})"
        )
    preset_display = f"Localize('eu5ab_template_slot_{slot}_title')"
    for policy_value, policy_id in reversed(tuple(enumerate(PRESET_TEMPLATE_IDS, start=1))):
        preset_display = (
            "Select_CString("
            f"EqualTo_CFixedPoint({player}.MakeScope.GetVariable('{preset_origin}').GetValue,"
            f"'(CFixedPoint){policy_value}'),"
            f"Localize('eu5ab_policy_{policy_id}'),{preset_display})"
        )
    return (
        "[Select_CString("
        f"{player}.MakeScope.GetVariable('{custom_name}').IsSet,"
        f"{player}.MakeScope.GetVariable('{custom_name}').GetFlagName,"
        "Select_CString("
        f"EqualTo_CFixedPoint({player}.MakeScope.GetVariable('{_slot_var(slot, 'name_selected')}').GetValue,"
        "'(CFixedPoint)1'),"
        f"{saved_display},"
        f"{preset_display}))]"
    )


def _slot_sidebar_display_name_expr(slot: int) -> str:
    return (
        f"{_slot_display_name_expr(slot)}"
        "[AddTextIf("
        f"Player.MakeScope.GetVariable('{_slot_var(slot, 'paused')}').IsSet,"
        "Localize('eu5ab_template_paused_badge'))]"
    )


def _text_property_for(value: str) -> str:
    return "raw_text" if value.startswith("[") else "text"


DEFAULT_ICON = "gfx/interface/icons/buildings/_default.dds"
TEMPLATE_ICON = "gfx/interface/icons/flat_icons/tabicons/economy.dds"
BUILDING_RULES_ICON = "gfx/interface/icons/flat_icons/building_panel/productionfiltered_button.dds"
GEOGRAPHY_ICON = "gfx/interface/icons/flat_icons/tabicons/geography_flat_icon.dds"
CASH_ICON = "gfx/interface/icons/resources/gold.dds"
OPERATING_RULES_ICON = "gfx/interface/icons/flat_icons/tabicons/production.dds"
PRICE_ICON = "gfx/interface/icons/flat_icons/advances_panel/market_price.dds"
PREDICTION_ICON = "gfx/interface/icons/sort/development.dds"
IMPORT_ICON = "gfx/interface/icons/flat_icons/trade_market/import.dds"
WORKFORCE_ICON = "gfx/interface/icons/flat_icons/tabicons/demography.dds"
MISSING_GOODS_ICON = "gfx/interface/icons/flat_icons/trade_market/missing_goods.dds"
INFO_ICON = "gfx/interface/icons/flat_icons/tabicons/info_flat_icon.dds"


def _gui_window(
    window_name: str,
    title_key: str,
    visible_var: str,
    body: str,
    close_lines: list[str] | None = None,
    height: int = 720,
    width: int = 1200,
    visible_expression: str | None = None,
) -> str:
    if close_lines is None:
        close_lines = [
            f"on_action = \"[GetVariableSystem.Clear('{visible_var}')]\"",
            "on_action = \"[GetVariableSystem.Set('eu5ab_window_open', '1')]\"",
        ]
    close_block = "\n\t\t\t\t\t\t".join(close_lines)
    if visible_expression is None:
        visible_expression = f"GetVariableSystem.Exists('{visible_var}')"
    return f"""# Generated by eu5autobuild.generator.
window = {{
	name = "{window_name}"
	datacontext = "[GetPlayer]"
	allow_outside = yes
	alwaystransparent = no
	parentanchor = center
	position = {{ 0 0 }}
	movable = yes
	size = {{ {width} {height} }}
	visible = "[{visible_expression}]"
	enabled = "[{visible_expression}]"

	widget = {{
		size = {{ {width} {height} }}
		using = bg_window_default_alt
		allow_outside = yes

		widget = {{
			parentanchor = right
			position = {{ -5 5 }}
			size = {{ 40 40 }}
			ui_direction_button_holder_right = {{}}
			button_close_alt = {{
				blockoverride "close_on_action" {{
						{close_block}
				}}
			}}
		}}

		vbox = {{
			using = window_margin_alt
			window_header_alt = {{
				blockoverride "header_text" {{ text = "{title_key}" }}
				blockoverride "window_header_alt_color_texture" {{ using = color_production_texture }}
			}}
{body}
		}}
	}}
}}
"""


def _window_visible_var(window_name: str) -> str | None:
    return {
        "eu5ab_template_editor_window": "eu5ab_template_editor_visible",
        "eu5ab_template_buildings_window": "eu5ab_template_buildings_visible",
        "eu5ab_template_rules_window": "eu5ab_template_rules_visible",
        "eu5ab_template_rename_window": "eu5ab_template_rename_visible",
        "eu5ab_template_scope_window": "eu5ab_template_scope_visible",
    }.get(window_name)


def _gui_open_window_button(gui_id: str, text_key: str, gui_path: str, window_name: str, width: int = 150) -> str:
    del gui_path
    text_width = max(width - 8, 32)
    visible_var = _window_visible_var(window_name)
    clear_cmf_request_line = '\n\t\t\t\t\t\tonclick = "[GetScriptedGui(\'eu5ab_gui_clear_cmf_window_request\').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"' if visible_var else ""
    hide_main_line = '\n						onclick = "[GetVariableSystem.Clear(\'eu5ab_window_open\')]"' if visible_var else ""
    visible_line = f'\n						onclick = "[GetVariableSystem.Set(\'{visible_var}\', \'1\')]"' if visible_var else ""
    return f"""button_regular = {{
						size = {{ {width} 40 }}
						tooltip = "{text_key}"
						text_single = {{
							size = {{ {text_width} 36 }}
							parentanchor = center
							autoresize = no
							maximumsize = {{ {text_width} 36 }}
							fontsize = 14
							fontsize_min = 10
							align = center|nobaseline
							elide = right
							text = "{text_key}"
						}}
						onclick = "[GetScriptedGui('{gui_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
						{clear_cmf_request_line}
						{hide_main_line}
						{visible_line}
					}}"""


def render_template_editor_gui(policies: list[Policy], catalog: BuildingCatalog) -> str:
    del catalog

    def slot_visible(slot: int) -> str:
        return f"[EqualTo_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_active_template_slot').GetValue,'(CFixedPoint){slot}')]"

    def rename_button(slot: int) -> str:
        display_name = _slot_display_name_expr(slot)
        return f"""vbox = {{
							layoutpolicy_horizontal = expanding
							spacing = 4
							text_single = {{ size = {{ -1 24 }} fontsize = 14 fontsize_min = 10 text = "eu5ab_template_name_click_hint" }}
							button_regular = {{
								size = {{ 520 40 }}
								tooltip = "eu5ab_template_name_click_tooltip"
								text_single = {{
									size = {{ 500 36 }}
									parentanchor = center
									autoresize = no
									maximumsize = {{ 500 36 }}
									fontsize = 18
									fontsize_min = 12
									align = center|nobaseline
									elide = right
									raw_text = "{display_name}"
								}}
								onclick = "[GetScriptedGui('eu5ab_gui_open_player_template_slot_{slot}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
								onclick = "[GetScriptedGui('eu5ab_gui_clear_cmf_window_request').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
								onclick = "[GetVariableSystem.Set('eu5ab_template_name_input', {display_name[1:-1]})]"
								onclick = "[GetVariableSystem.Clear('eu5ab_window_open')]"
								onclick = "[GetVariableSystem.Set('eu5ab_template_rename_visible', '1')]"
							}}
						}}"""

    def slot_editor(slot: int) -> str:
        return f"""vbox = {{
						visible = "{slot_visible(slot)}"
						layoutpolicy_horizontal = expanding
						spacing = 4
{_gui_ogas_card(TEMPLATE_ICON, f"eu5ab_template_slot_{slot}_editor_title", f'''						text_multi = {{ layoutpolicy_horizontal = expanding autoresize = yes text = "eu5ab_template_editor_desc" }}
						{rename_button(slot)}''')}
{_gui_ogas_card(BUILDING_RULES_ICON, "eu5ab_template_editor_sections_title", f'''						hbox = {{
							layoutpolicy_horizontal = expanding
							spacing = 8
							{_gui_open_window_button(f"eu5ab_gui_open_template_buildings_slot_{slot}", "eu5ab_open_buildings_editor_button", "gui/eu5ab_template_buildings_window.gui", "eu5ab_template_buildings_window", 180)}
							{_gui_open_window_button(f"eu5ab_gui_open_template_rules_slot_{slot}", "eu5ab_open_rules_editor_button", "gui/eu5ab_template_rules_window.gui", "eu5ab_template_rules_window", 180)}
						}}
						text_multi = {{ layoutpolicy_horizontal = expanding autoresize = yes text = "eu5ab_template_editor_sections_desc" }}''')}
					}}"""

    def preset_visible(index: int) -> str:
        return f"[EqualTo_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_active_preset_policy').GetValue,'(CFixedPoint){index + 1}')]"

    def preset_editor(index: int, policy: Policy) -> str:
        return f"""vbox = {{
						visible = "{preset_visible(index)}"
						layoutpolicy_horizontal = expanding
						spacing = 4
{_gui_ogas_card(TEMPLATE_ICON, policy.name_key, f'''						text_multi = {{ layoutpolicy_horizontal = expanding autoresize = yes text = "{policy.description_key}" }}
						text_multi = {{ layoutpolicy_horizontal = expanding autoresize = yes text = "eu5ab_preset_readonly_desc" }}
						hbox = {{
							layoutpolicy_horizontal = expanding
							spacing = 8
                            {_gui_open_window_button(f"eu5ab_gui_copy_preset_{policy.id}_to_player_template", "eu5ab_copy_preset_to_player_button", "gui/eu5ab_template_editor_window.gui", "eu5ab_template_editor_window", 190)}
						}}''')}
					}}"""

    body = f"""
			vbox = {{
				layoutpolicy_horizontal = expanding
				layoutpolicy_vertical = expanding
				using = bg_secondary_inner_alt
				margin = {{ 8 8 }}
				spacing = 6
				scrollarea = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = expanding
					scrollbarpolicy_horizontal = always_off
					scrollbar_vertical = {{ using = Scrollbar_Vertical }}
					vbox = {{
						layoutpolicy_horizontal = expanding
						spacing = 4
						situation_card_expandable = {{ visible = no size = {{ 0 0 }} }}
{''.join(preset_editor(index, policy) for index, policy in enumerate(policies))}
{''.join(slot_editor(slot) for slot in TEMPLATE_SLOTS)}
					}}
				}}
			}}
"""
    return _gui_window("eu5ab_template_editor_window", "eu5ab_template_editor_title", "eu5ab_template_editor_visible", body)


def render_template_rename_gui(policies: list[Policy], catalog: BuildingCatalog) -> str:
    del policies, catalog

    def slot_visible(slot: int) -> str:
        return f"[EqualTo_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_active_template_slot').GetValue,'(CFixedPoint){slot}')]"

    accept_buttons = "\n".join(
        f"""button_regular = {{
							visible = "{slot_visible(slot)}"
							enabled = "[And(GetVariableSystem.Exists('eu5ab_template_name_input'), Not(StringIsEmpty(GetVariableSystem.Get('eu5ab_template_name_input'))))]"
							size = {{ 150 40 }}
							tooltip = "eu5ab_template_rename_accept"
							text_single = {{
								size = {{ 142 36 }}
								parentanchor = center
								autoresize = no
								maximumsize = {{ 142 36 }}
								fontsize = 14
								fontsize_min = 10
								align = center|nobaseline
								elide = right
								text = "eu5ab_template_rename_accept"
							}}
							onclick = "[GetScriptedGui('eu5ab_gui_slot_{slot}_name_custom').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('eu5ab_template_name_input', MakeScopeFlag(GetVariableSystem.Get('eu5ab_template_name_input'))).End)]"
							onclick = "[GetVariableSystem.Clear('eu5ab_template_name_input')]"
							onclick = "[GetVariableSystem.Clear('eu5ab_template_rename_visible')]"
							onclick = "[GetVariableSystem.Set('eu5ab_window_open', '1')]"
							input_action = "confirm"
						}}"""
        for slot in TEMPLATE_SLOTS
    )

    body = f"""
			vbox = {{
				layoutpolicy_horizontal = expanding
				layoutpolicy_vertical = expanding
				using = bg_secondary_inner_alt
				margin = {{ 16 16 }}
				spacing = 12
				text_multi = {{
					size = {{ 580 48 }}
					autoresize = no
					maximumsize = {{ 580 48 }}
					fontsize = 14
					fontsize_min = 10
					align = center
					text = "eu5ab_template_rename_desc"
				}}
				hbox = {{
					size = {{ 580 44 }}
					margin = {{ 5 0 }}
					using = message_text_box_background
					editbox_single = {{
						size = {{ 560 34 }}
						focus_on_visible = yes
						focuspolicy = all
						alwaystransparent = no
						blockoverride "editbox_label" {{
							text = "eu5ab_template_rename_input"
						}}
						blockoverride "editbox_properties" {{
							name = "eu5ab_template_name_input_box"
							text = "[GetVariableSystem.Get('eu5ab_template_name_input')]"
							ontextchanged = "[GetVariableSystem.Set('eu5ab_template_name_input', GetTextFromSelfOrAnyChildEditbox(PdxGuiWidget.Self))]"
							maxcharacters = 42
						}}
					}}
				}}
				hbox = {{
					layoutpolicy_horizontal = expanding
					spacing = 16
					ignoreinvisible = yes
					button_regular = {{
						size = {{ 150 40 }}
						tooltip = "eu5ab_template_rename_cancel"
						text_single = {{
							size = {{ 142 36 }}
							parentanchor = center
							autoresize = no
							maximumsize = {{ 142 36 }}
							fontsize = 14
							fontsize_min = 10
							align = center|nobaseline
							elide = right
							text = "eu5ab_template_rename_cancel"
						}}
						onclick = "[GetVariableSystem.Clear('eu5ab_template_name_input')]"
						onclick = "[GetVariableSystem.Clear('eu5ab_template_rename_visible')]"
						onclick = "[GetVariableSystem.Set('eu5ab_window_open', '1')]"
					}}
{accept_buttons}
				}}
			}}
"""
    return f"""# Generated by eu5autobuild.generator.
window = {{
	name = "eu5ab_template_rename_window"
	datacontext = "[GetPlayer]"
	allow_outside = yes
	alwaystransparent = no
	parentanchor = center
	position = {{ 0 0 }}
	movable = yes
	size = {{ 640 260 }}
	visible = "[GetVariableSystem.Exists('eu5ab_template_rename_visible')]"
	enabled = "[GetVariableSystem.Exists('eu5ab_template_rename_visible')]"

	widget = {{
		size = {{ 640 260 }}
		using = bg_window_default_alt
		allow_outside = yes

		widget = {{
			size = {{ 100% 100% }}
			alwaystransparent = yes
			filter_mouse = none
		}}

		widget = {{
			parentanchor = right
			position = {{ -5 5 }}
			size = {{ 40 40 }}
			ui_direction_button_holder_right = {{}}
			button_close_alt = {{
				blockoverride "close_on_action" {{
						on_action = "[GetVariableSystem.Clear('eu5ab_template_name_input')]"
						on_action = "[GetVariableSystem.Clear('eu5ab_template_rename_visible')]"
						on_action = "[GetVariableSystem.Set('eu5ab_window_open', '1')]"
				}}
			}}
		}}

		vbox = {{
			using = window_margin_alt
			window_header_alt = {{
				blockoverride "header_text" {{ text = "eu5ab_template_rename_window_title" }}
				blockoverride "window_header_alt_color_texture" {{ using = color_production_texture }}
			}}
{body}
		}}
	}}
}}
"""


def render_gui(policies: list[Policy], catalog: BuildingCatalog) -> str:
    del catalog
    sidebar_width = 520
    sidebar_button_width = 500
    sidebar_text_width = sidebar_button_width - 8
    detail_x = sidebar_width + 10
    detail_width = 640
    selected_preset_var = "eu5ab_selected_preset"
    selected_template_var = "eu5ab_selected_template_slot"

    def tab_visible(value: int) -> str:
        if value == 2:
            return "[Or(Not(GetVariableSystem.Exists('eu5ab_main_tab')), GetVariableSystem.HasValue('eu5ab_main_tab', '2'))]"
        return f"[GetVariableSystem.HasValue('eu5ab_main_tab', '{value}')]"

    def preset_visible(index: int) -> str:
        return f"[GetVariableSystem.HasValue('{selected_preset_var}', '{index + 1}')]"

    def slot_visible(slot: int) -> str:
        selection = f"GetVariableSystem.HasValue('{selected_template_var}', '{slot}')"
        if slot == 1:
            selection = (
                f"Or(Not(GetVariableSystem.Exists('{selected_template_var}')), {selection})"
            )
        return f"[And({selection}, Player.MakeScope.GetVariable('{_slot_var(slot, 'exists')}').IsSet)]"

    def slot_exists_expr(slot: int) -> str:
        return f"Player.MakeScope.GetVariable('{_slot_var(slot, 'exists')}').IsSet"

    def combine_gui_conditions(function: str, conditions: list[str]) -> str:
        expression = conditions[0]
        for condition in conditions[1:]:
            expression = f"{function}({expression}, {condition})"
        return expression

    def first_free_slot_visible(slot: int) -> str:
        conditions = [slot_exists_expr(previous_slot) for previous_slot in range(1, slot)]
        conditions.append(f"Not({slot_exists_expr(slot)})")
        return f"[{combine_gui_conditions('And', conditions)}]"

    no_selected_template_visible = (
        f"[Not({combine_gui_conditions('Or', [slot_visible(slot)[1:-1] for slot in TEMPLATE_SLOTS])})]"
    )

    def main_scripted_button(
        gui_id: str,
        text_key: str,
        width: int = 58,
        extra_onclicks: tuple[str, ...] = (),
        visible: str | None = None,
        tooltip_key: str | None = None,
    ) -> str:
        text_width = max(width - 8, 32)
        tooltip_key = tooltip_key or text_key
        visible_line = f'\n\t\t\t\t\t\tvisible = "{visible}"' if visible else ""
        extra_lines = "".join(f"\n						{line}" for line in extra_onclicks)
        return f"""button_regular = {{
						layoutpolicy_vertical = fixed
						size = {{ {width} 40 }}{visible_line}
						tooltip = "{tooltip_key}"
						text_single = {{
							size = {{ {text_width} 36 }}
							parentanchor = center
							autoresize = no
							maximumsize = {{ {text_width} 36 }}
							fontsize = 14
							fontsize_min = 10
							align = center|nobaseline
							elide = right
							text = "{text_key}"
						}}
						onclick = "[GetScriptedGui('{gui_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
						{extra_lines}
					}}"""

    def tab_button(gui_id: str, text_key: str, tooltip_key: str, value: int) -> str:
        if value == 1:
            selection_onclicks = (
                f"onclick = \"[GetVariableSystem.Set('{selected_preset_var}', '1')]\"",
                f"onclick = \"[GetVariableSystem.Clear('{selected_template_var}')]\"",
            )
        else:
            selection_onclicks = (
                f"onclick = \"[GetVariableSystem.Set('{selected_template_var}', '1')]\"",
                f"onclick = \"[GetVariableSystem.Clear('{selected_preset_var}')]\"",
            )
        selection_lines = "\n".join(f"\t\t\t\t\t\t\t{line}" for line in selection_onclicks)
        return f"""button_main_tab_alt = {{
							layoutpolicy_horizontal = expanding
							text = "{text_key}"
							tooltip = "{tooltip_key}"
							onclick = "[GetVariableSystem.Set('eu5ab_main_tab', '{value}')]"
							onclick = "[GetVariableSystem.Clear('eu5ab_delete_confirmation_slot')]"
{selection_lines}
							onclick = "[GetScriptedGui('{gui_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
							down = "{tab_visible(value)}"
						}}"""

    def sidebar_button(
        gui_id: str,
        text_key: str,
        down_expr: str,
        selection_var: str,
        selection_value: int,
        visible: str | None = None,
    ) -> str:
        visible_line = f'\n							visible = "{visible}"' if visible else ""
        text_property = _text_property_for(text_key)
        tooltip_key = "eu5ab_select_template_tooltip"
        tooltip_line = f'\n							tooltip = "{tooltip_key}"'
        return f"""checkbutton_02_alt = {{
							layoutpolicy_horizontal = expanding
							layoutpolicy_vertical = fixed
							size = {{ {sidebar_button_width} 50 }}{visible_line}{tooltip_line}
							minimumsize = {{ {sidebar_button_width} 50 }}
							maximumsize = {{ {sidebar_button_width} 50 }}
							down = "{down_expr}"
							text_single = {{
								size = {{ {sidebar_text_width} 44 }}
								parentanchor = center
								autoresize = no
								maximumsize = {{ {sidebar_text_width} 44 }}
								fontsize = 16
								fontsize_min = 10
								align = center|nobaseline
								elide = right
								{text_property} = "{text_key}"
							}}
							onclick = "[GetVariableSystem.Set('{selection_var}', '{selection_value}')]"
							onclick = "[GetVariableSystem.Clear('eu5ab_delete_confirmation_slot')]"
							onclick = "[GetScriptedGui('{gui_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
						}}"""

    def new_template_buttons(gui_id: str, text_key: str, width: int) -> str:
        return "\n".join(
            main_scripted_button(
                gui_id,
                text_key,
                width,
                (
                    "onclick = \"[GetVariableSystem.Set('eu5ab_main_tab', '2')]\"",
                    f"onclick = \"[GetVariableSystem.Clear('{selected_preset_var}')]\"",
                    f"onclick = \"[GetVariableSystem.Set('{selected_template_var}', '{slot}')]\"",
                ),
                first_free_slot_visible(slot),
            )
            for slot in TEMPLATE_SLOTS
        )

    def template_creation_buttons(total_width: int) -> str:
        spacing = 8
        button_width = (total_width - spacing) // 2
        return f"""hbox = {{
							layoutpolicy_horizontal = preferred
							layoutpolicy_vertical = fixed
							size = {{ {total_width} 40 }}
							spacing = {spacing}
							vbox = {{
								size = {{ {button_width} 40 }}
								ignoreinvisible = yes
{new_template_buttons("eu5ab_gui_new_blank_player_template", "eu5ab_new_blank_template_button", button_width)}
							}}
							vbox = {{
								size = {{ {button_width} 40 }}
								ignoreinvisible = yes
{new_template_buttons("eu5ab_gui_new_recommended_player_template", "eu5ab_new_recommended_template_button", button_width)}
							}}
						}}"""

    def rename_button(slot: int) -> str:
        display_name = _slot_display_name_expr(slot)
        return f"""vbox = {{
							layoutpolicy_horizontal = expanding
							spacing = 4
							text_single = {{ size = {{ -1 24 }} fontsize = 14 fontsize_min = 10 text = "eu5ab_template_name_click_hint" }}
							button_regular = {{
								size = {{ 520 40 }}
								tooltip = "eu5ab_template_name_click_tooltip"
								text_single = {{
									size = {{ 500 36 }}
									parentanchor = center
									autoresize = no
									maximumsize = {{ 500 36 }}
									fontsize = 18
									fontsize_min = 12
									align = center|nobaseline
									elide = right
									raw_text = "{display_name}"
								}}
								onclick = "[GetScriptedGui('eu5ab_gui_open_player_template_slot_{slot}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
								onclick = "[GetScriptedGui('eu5ab_gui_clear_cmf_window_request').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
								onclick = "[GetVariableSystem.Set('eu5ab_template_name_input', {display_name[1:-1]})]"
								onclick = "[GetVariableSystem.Clear('eu5ab_window_open')]"
								onclick = "[GetVariableSystem.Set('eu5ab_template_rename_visible', '1')]"
							}}
						}}"""

    def location_action_buttons(location_action: str, province_action: str, area_action: str) -> str:
        return f"""hbox = {{
							layoutpolicy_horizontal = expanding
							spacing = 8
							{_gui_select_action_button(location_action, "eu5ab_map_select_location_click", "eu5ab_map_select_location_click_desc")}
							{_gui_select_action_button(province_action, "eu5ab_map_select_province_ctrl", "eu5ab_map_select_province_ctrl_desc")}
							{_gui_select_action_button(area_action, "eu5ab_map_select_area_shift", "eu5ab_map_select_area_shift_desc")}
						}}"""

    preset_sidebar = "\n".join(
        sidebar_button(
            f"eu5ab_gui_open_preset_{policy.id}",
            policy.name_key,
            preset_visible(index),
            selected_preset_var,
            index + 1,
        )
        for index, policy in enumerate(policies)
    )
    custom_sidebar = "\n".join(
        sidebar_button(
            f"eu5ab_gui_open_player_template_slot_{slot}",
            _slot_sidebar_display_name_expr(slot),
            slot_visible(slot),
            selected_template_var,
            slot,
            f"[Player.MakeScope.GetVariable('{_slot_var(slot, 'exists')}').IsSet]",
        )
        for slot in TEMPLATE_SLOTS
    )

    def template_footer(slot: int) -> str:
        paused_var = _slot_var(slot, "paused")
        confirmation_visible = (
            f"[GetVariableSystem.HasValue('eu5ab_delete_confirmation_slot', '{slot}')]"
        )
        normal_visible = (
            f"[Not(GetVariableSystem.HasValue('eu5ab_delete_confirmation_slot', '{slot}'))]"
        )
        paused = f"[Player.MakeScope.GetVariable('{paused_var}').IsSet]"
        not_paused = f"[Not(Player.MakeScope.GetVariable('{paused_var}').IsSet)]"
        return f"""vbox = {{
								visible = "{slot_visible(slot)}"
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = fixed
								size = {{ {detail_width - 20} 44 }}
								ignoreinvisible = yes
								hbox = {{
									visible = "{normal_visible}"
									layoutpolicy_horizontal = expanding
									layoutpolicy_vertical = fixed
									size = {{ {detail_width - 20} 40 }}
									margin = {{ 72 0 }}
									spacing = 12
									ignoreinvisible = yes
									button_regular_alt_yellow = {{
										size = {{ 230 40 }}
										visible = "{not_paused}"
										text = "eu5ab_pause_template_button"
										tooltip = "eu5ab_pause_template_tooltip"
										onclick = "[GetScriptedGui('eu5ab_gui_toggle_template_slot_{slot}_paused').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
									}}
									button_regular_alt_green = {{
										size = {{ 230 40 }}
										visible = "{paused}"
										text = "eu5ab_resume_template_button"
										tooltip = "eu5ab_pause_template_tooltip"
										onclick = "[GetScriptedGui('eu5ab_gui_toggle_template_slot_{slot}_paused').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
									}}
									button_regular_alt_red = {{
										size = {{ 230 40 }}
										text = "eu5ab_delete_template_button"
										tooltip = "eu5ab_delete_template_tooltip"
										onclick = "[GetVariableSystem.Set('eu5ab_delete_confirmation_slot', '{slot}')]"
									}}
								}}
								hbox = {{
									visible = "{confirmation_visible}"
									layoutpolicy_horizontal = expanding
									layoutpolicy_vertical = fixed
									size = {{ {detail_width - 20} 40 }}
									spacing = 8
									text_single = {{ size = {{ 276 40 }} align = center|vcenter fontsize = 14 fontsize_min = 10 text = "eu5ab_delete_template_confirm_prompt" }}
									button_regular_alt_red = {{
										size = {{ 160 40 }}
										text = "eu5ab_delete_template_confirm_button"
										tooltip = "eu5ab_delete_template_confirm_tooltip"
										onclick = "[GetScriptedGui('eu5ab_gui_delete_template_slot_{slot}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
										onclick = "[GetVariableSystem.Clear('{selected_template_var}')]"
										onclick = "[GetVariableSystem.Clear('eu5ab_delete_confirmation_slot')]"
									}}
									button_regular_alt = {{
										size = {{ 160 40 }}
										text = "eu5ab_delete_template_cancel_button"
										tooltip = "eu5ab_delete_template_cancel_tooltip"
										onclick = "[GetVariableSystem.Clear('eu5ab_delete_confirmation_slot')]"
									}}
								}}
							}}"""

    template_footers = "\n".join(template_footer(slot) for slot in TEMPLATE_SLOTS)

    def preset_detail(policy: Policy, index: int) -> str:
        paused_var = _preset_paused_var(policy.id)
        paused = f"[Player.MakeScope.GetVariable('{paused_var}').IsSet]"
        not_paused = f"[Not(Player.MakeScope.GetVariable('{paused_var}').IsSet)]"
        return f"""vbox = {{
								visible = "{preset_visible(index)}"
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = preferred
								spacing = 8
{_gui_ogas_card(TEMPLATE_ICON, policy.name_key, f'''						text_multi = {{ layoutpolicy_horizontal = expanding autoresize = yes text = "{policy.description_key}" }}
						text_multi = {{ layoutpolicy_horizontal = expanding autoresize = yes text = "eu5ab_preset_readonly_desc" }}
							hbox = {{
							layoutpolicy_horizontal = expanding
							spacing = 8
                            {new_template_buttons(f"eu5ab_gui_copy_preset_{policy.id}_to_player_template", "eu5ab_copy_preset_to_player_button", 190)}
							button_regular_alt_yellow = {{
								size = {{ 190 40 }}
								visible = "{not_paused}"
								text = "eu5ab_pause_template_button"
								tooltip = "eu5ab_pause_template_tooltip"
								onclick = "[GetScriptedGui('eu5ab_gui_toggle_preset_{policy.id}_paused').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
							}}
							button_regular_alt_green = {{
								size = {{ 190 40 }}
								visible = "{paused}"
								text = "eu5ab_resume_template_button"
								tooltip = "eu5ab_pause_template_tooltip"
								onclick = "[GetScriptedGui('eu5ab_gui_toggle_preset_{policy.id}_paused').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
							}}
						}}
						text_single = {{ layoutpolicy_horizontal = expanding fontsize = 14 fontsize_min = 10 text = "eu5ab_template_locations_short" }}
						{location_action_buttons(f"eu5ab_apply_preset_{policy.id}_to_selected_location", f"eu5ab_apply_preset_{policy.id}_to_selected_province", f"eu5ab_apply_preset_{policy.id}_to_selected_area")}
						{_gui_open_window_button(f"eu5ab_gui_open_preset_scope_{policy.id}", "eu5ab_view_scope_button", "gui/eu5ab_template_scope_window.gui", "eu5ab_template_scope_window", 180)}''')}
							}}"""

    def slot_detail(slot: int) -> str:
        return f"""vbox = {{
								visible = "{slot_visible(slot)}"
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = preferred
								spacing = 8
{_gui_ogas_card(TEMPLATE_ICON, f"eu5ab_template_slot_{slot}_editor_title", f'''						{rename_button(slot)}
						text_multi = {{ layoutpolicy_horizontal = expanding autoresize = yes text = "eu5ab_template_slot_{slot}_summary" }}
						hbox = {{
							layoutpolicy_horizontal = expanding
							spacing = 8
							{_gui_open_window_button(f"eu5ab_gui_open_template_buildings_slot_{slot}", "eu5ab_open_buildings_editor_button", "gui/eu5ab_template_buildings_window.gui", "eu5ab_template_buildings_window", 155)}
							{_gui_open_window_button(f"eu5ab_gui_open_template_rules_slot_{slot}", "eu5ab_open_rules_editor_button", "gui/eu5ab_template_rules_window.gui", "eu5ab_template_rules_window", 155)}
						}}
						text_single = {{ layoutpolicy_horizontal = expanding fontsize = 14 fontsize_min = 10 text = "eu5ab_template_locations_short" }}
						{location_action_buttons(f"eu5ab_apply_template_slot_{slot}_to_selected_location", f"eu5ab_apply_template_slot_{slot}_to_selected_province", f"eu5ab_apply_template_slot_{slot}_to_selected_area")}
						{_gui_open_window_button(f"eu5ab_gui_open_template_scope_slot_{slot}", "eu5ab_view_scope_button", "gui/eu5ab_template_scope_window.gui", "eu5ab_template_scope_window", 180)}''')}
							}}"""

    preset_details = "\n".join(preset_detail(policy, index) for index, policy in enumerate(policies))
    slot_details = "\n".join(slot_detail(slot) for slot in TEMPLATE_SLOTS)
    custom_empty_detail = f"""vbox = {{
								visible = "{no_selected_template_visible}"
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = preferred
								spacing = 8
{_gui_ogas_card(TEMPLATE_ICON, "eu5ab_custom_tab", f'''						text_multi = {{ layoutpolicy_horizontal = expanding autoresize = yes text = "eu5ab_custom_empty_detail" }}
                        {template_creation_buttons(388)}''')}
							}}"""

    preset_detail_group = f"""vbox = {{
								visible = "{tab_visible(1)}"
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = preferred
								spacing = 4
{preset_details}
							}}"""
    custom_detail_group = f"""vbox = {{
								visible = "{tab_visible(2)}"
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = preferred
								spacing = 4
{custom_empty_detail}
{slot_details}
							}}"""

    body = f"""
			vbox = {{
				layoutpolicy_horizontal = expanding
				layoutpolicy_vertical = expanding
				using = bg_secondary_inner_alt
				margin = {{ 8 8 }}
				spacing = 8
				header_main_tabs = {{
					blockoverride "content" {{
						{tab_button("eu5ab_gui_open_player_templates", "eu5ab_custom_tab", "eu5ab_custom_tab_tooltip", 2)}
						{tab_button("eu5ab_gui_open_presets_tab", "eu5ab_presets_tab", "eu5ab_presets_tab_tooltip", 1)}
					}}
				}}
				widget = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = expanding
					size = {{ 1170 585 }}
					widget = {{
						position = {{ 0 0 }}
						size = {{ {sidebar_width} 585 }}
						vbox = {{
							size = {{ {sidebar_width} 585 }}
							using = bg_main_inner_alt
							margin = {{ 8 8 }}
							spacing = 6
							ignoreinvisible = yes
							text_single = {{ size = {{ {sidebar_button_width} 28 }} align = center fontsize = 16 fontsize_min = 10 text = "eu5ab_sidebar_title" }}
							scrollbox = {{
								size = {{ {sidebar_button_width} 480 }}
								blockoverride "scrollbox_content" {{
									vbox = {{
										layoutpolicy_horizontal = expanding
										layoutpolicy_vertical = fixed
										spacing = 4
										ignoreinvisible = yes
									vbox = {{
										visible = "{tab_visible(1)}"
										layoutpolicy_horizontal = expanding
										layoutpolicy_vertical = fixed
										spacing = 4
										ignoreinvisible = yes
{preset_sidebar}
									}}
									vbox = {{
										visible = "{tab_visible(2)}"
										layoutpolicy_horizontal = expanding
										layoutpolicy_vertical = fixed
										spacing = 4
										ignoreinvisible = yes
{custom_sidebar}
									}}
									}}
								}}
							}}
							vbox = {{
								visible = "{tab_visible(2)}"
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = fixed
								size = {{ {sidebar_button_width} 40 }}
								ignoreinvisible = yes
								{template_creation_buttons(sidebar_button_width)}
							}}
						}}
					}}
					widget = {{
						position = {{ {detail_x} 0 }}
						size = {{ {detail_width} 585 }}
						vbox = {{
							size = {{ {detail_width} 585 }}
							using = bg_main_inner_alt
							margin = {{ 8 8 }}
							spacing = 6
							ignoreinvisible = yes
							text_single = {{ size = {{ {detail_width - 20} 28 }} align = center fontsize = 16 fontsize_min = 10 text = "eu5ab_detail_title" }}
							scrollbox = {{
								size = {{ {detail_width - 20} 480 }}
								blockoverride "scrollbox_content" {{
									vbox = {{
										layoutpolicy_horizontal = expanding
										layoutpolicy_vertical = preferred
										spacing = 4
{preset_detail_group}
{custom_detail_group}
									}}
								}}
							}}
							vbox = {{
								visible = "{tab_visible(2)}"
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = fixed
								size = {{ {detail_width - 20} 44 }}
								ignoreinvisible = yes
{template_footers}
							}}
						}}
					}}
				}}
			}}
"""
    window = _gui_window(
        "eu5ab_automation_buildings_window",
        "eu5ab_window_title",
        "eu5ab_window_open",
        body,
        [
            "on_action = \"[GetVariableSystem.Clear('eu5ab_window_open')]\"",
            "on_action = \"[GetScriptedGui('eu5ab_gui_clear_cmf_window_request').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]\"",
            "on_action = \"[GetVariableSystem.Clear('eu5ab_template_buildings_visible')]\"",
            "on_action = \"[GetVariableSystem.Clear('eu5ab_template_rules_visible')]\"",
            "on_action = \"[GetVariableSystem.Clear('eu5ab_template_rename_visible')]\"",
            "on_action = \"[GetVariableSystem.Clear('eu5ab_template_scope_visible')]\"",
            "on_action = \"[GetVariableSystem.Clear('eu5ab_template_name_input')]\"",
            "on_action = \"[GetVariableSystem.Clear('eu5ab_delete_confirmation_slot')]\"",
        ],
        visible_expression=(
            "And(Or(GetVariableSystem.Exists('eu5ab_window_open'),"
            "Player.MakeScope.GetVariable('eu5ab_cmf_window_requested').IsSet),"
            "Not(Or5(GetVariableSystem.Exists('eu5ab_template_editor_visible'),"
            "GetVariableSystem.Exists('eu5ab_template_buildings_visible'),"
            "GetVariableSystem.Exists('eu5ab_template_rules_visible'),"
            "GetVariableSystem.Exists('eu5ab_template_rename_visible'),"
            "GetVariableSystem.Exists('eu5ab_template_scope_visible'))))"
        ),
    )
    gui_types = """types EU5ABAutomationPanelTypes {
	type eu5ab_automation_policy_footer = widget {
		size = { 420 72 }
		alwaystransparent = no
		text_multi = { position = { 8 8 } size = { 404 56 } text = "eu5ab_automation_policy_footer_text" }
	}
}
"""
    return gui_types + "\n" + window


def _gui_active_filter_button(text_key: str, value: int, kind: str = "filter") -> str:
    variable = "eu5ab_edit_building_filter" if kind == "filter" else "eu5ab_edit_building_age"
    gui_id = f"eu5ab_gui_active_building_{kind}_{value}"
    down_expr = (
        f"[EqualTo_CFixedPoint(Player.MakeScope.GetVariable('{variable}').GetValue,"
        f"'(CFixedPoint){value}')]"
    )
    width = 180 if kind == "filter" else 154
    return f"""checkbutton_02_alt = {{
		layoutpolicy_horizontal = preferred
		size = {{ {width} 40 }}
		down = "{down_expr}"
		tooltip = "{text_key}"
		text_single = {{
			margin = {{ 8 7 }}
			default_format = "#high"
			using = Font_Size_Small
			align = center|nobaseline
			text = "{text_key}"
		}}
		onclick = "[GetScriptedGui('{gui_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
	}}"""


def _gui_priority_adjust_button(
    building_id: str,
    direction: str,
    enabled: str,
    text_key: str,
) -> str:
    action_id = f"eu5ab_gui_active_priority_{direction}_{building_id}"
    tooltip_prefix = f"eu5ab_priority_{'decrease' if direction == 'dec' else 'increase'}"
    return f"""button_regular = {{
			size = {{ 46 36 }}
			enabled = "{enabled}"
			text_single = {{ size = {{ 38 32 }} parentanchor = center align = center|nobaseline text = "{text_key}" }}
			action_tooltip = {{
				click_mode = single
				click_type = left
				click_modifier = default
				title = "{tooltip_prefix}_default_tt"
			}}
			action_tooltip = {{
				click_mode = single
				click_type = left
				click_modifier = ctrl
				title = "{tooltip_prefix}_ctrl_tt"
			}}
			action_tooltip = {{
				click_mode = single
				click_type = left
				click_modifier = shift
				title = "{tooltip_prefix}_shift_tt"
			}}
			click_modifiers = {{
				ondefault = "[GetScriptedGui('eu5ab_gui_priority_step_default').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
				ondefault = "[GetScriptedGui('{action_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
				onctrl = "[GetScriptedGui('eu5ab_gui_priority_step_ctrl').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
				onctrl = "[GetScriptedGui('{action_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
				onshift = "[GetScriptedGui('eu5ab_gui_priority_step_shift').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
				onshift = "[GetScriptedGui('{action_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
			}}
			tooltipwidget = {{ BasicFunctionalTooltip = {{}} }}
		}}"""


def _gui_active_priority_row(building_id: str, catalog: BuildingCatalog) -> str:
    definition = catalog.get(building_id)
    if definition is None:
        raise ValueError(f"Unknown building in active editor: {building_id}")
    filter_id = _building_filter_id(building_id, catalog)
    priority_var = _editor_priority_var(building_id)
    category_match = (
        f"Or(EqualTo_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_edit_building_filter').GetValue,"
        f"'(CFixedPoint)0'),EqualTo_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_edit_building_filter').GetValue,"
        f"'(CFixedPoint){filter_id}'))"
    )
    age_match = (
        f"Or(EqualTo_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_edit_building_age').GetValue,"
        f"'(CFixedPoint)0'),EqualTo_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_edit_building_age').GetValue,"
        f"'(CFixedPoint){definition.age}'))"
    )
    visible_logic = f"And({category_match},{age_match})"
    if definition.is_special:
        available = (
            f"GetScriptedGui('eu5ab_gui_special_building_available_{building_id}')"
            ".IsShown(GuiScope.SetRoot(Player.MakeScope)"
            ".AddScope('actor', Player.MakeScope).End)"
        )
        visible_logic = f"And({visible_logic},{available})"
    visible_expr = f"[{visible_logic}]"
    dec_enabled = (
        f"[GreaterThan_CFixedPoint(Player.MakeScope.GetVariable('{priority_var}').GetValue,'(CFixedPoint)0')]"
    )
    inc_enabled = (
        f"[LessThan_CFixedPoint(Player.MakeScope.GetVariable('{priority_var}').GetValue,'(CFixedPoint)10')]"
    )
    category_key = {
        1: "eu5ab_filter_rural",
        2: "eu5ab_filter_laborers",
        3: "eu5ab_filter_burghers",
        4: "eu5ab_filter_soldiers",
        5: "eu5ab_filter_special",
    }[filter_id]
    return f"""hbox = {{
		visible = "{visible_expr}"
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = fixed
		size = {{ -1 44 }}
		spacing = 8
		margin = {{ 8 2 }}
		using = bg_number_container_bckg
		text_single = {{
			layoutpolicy_horizontal = expanding
			size = {{ -1 36 }}
			autoresize = no
			fontsize = 14
			fontsize_min = 9
			align = left|vcenter
			elide = right
			text = "{_building_name_key(building_id)}"
		}}
		text_single = {{
			size = {{ 170 36 }}
			autoresize = no
			fontsize = 14
			fontsize_min = 10
			align = center|vcenter
			text = "{category_key}"
		}}
		text_single = {{
			size = {{ 130 36 }}
			autoresize = no
			fontsize = 14
			fontsize_min = 10
			align = center|vcenter
			text = "eu5ab_building_age_{definition.age}"
		}}
{_gui_priority_adjust_button(building_id, "dec", dec_enabled, "eu5ab_priority_decrease")}
		text_single = {{
			size = {{ 52 36 }}
			autoresize = no
			align = center|nobaseline
			raw_text = "[Player.MakeScope.GetVariable('{priority_var}').GetValue|1]"
		}}
{_gui_priority_adjust_button(building_id, "inc", inc_enabled, "eu5ab_priority_increase")}
	}}"""


def render_active_template_buildings_gui(catalog: BuildingCatalog) -> str:
    filter_tabs = "\n".join([
        _gui_active_filter_button("eu5ab_filter_all", 0, "filter"),
        _gui_active_filter_button("eu5ab_filter_rural", 1, "filter"),
        _gui_active_filter_button("eu5ab_filter_laborers", 2, "filter"),
        _gui_active_filter_button("eu5ab_filter_burghers", 3, "filter"),
        _gui_active_filter_button("eu5ab_filter_soldiers", 4, "filter"),
        _gui_active_filter_button("eu5ab_filter_special", 5, "filter"),
    ])
    age_tabs = "\n".join(
        [_gui_active_filter_button("eu5ab_age_all", 0, "age")]
        + [
            _gui_active_filter_button(f"eu5ab_building_age_{age}", age, "age")
            for age in range(1, 7)
        ]
    )

    rows = "\n".join(
        _gui_active_priority_row(building_id, catalog)
        for building_id in _catalog_building_ids(catalog)
    )
    body = f"""
			vbox = {{
				layoutpolicy_horizontal = expanding
				layoutpolicy_vertical = expanding
				using = bg_secondary_inner_alt
				margin = {{ 12 12 }}
				spacing = 8
				text_multi = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = fixed
					size = {{ -1 44 }}
					autoresize = no
					text = "eu5ab_building_rules_desc"
				}}
				hbox = {{
					layoutpolicy_horizontal = expanding
					spacing = 6
{filter_tabs}
				}}
				hbox = {{
					layoutpolicy_horizontal = expanding
					spacing = 6
{age_tabs}
				}}
				scrollarea = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = fixed
					size = {{ -1 430 }}
					scrollbarpolicy_horizontal = always_off
					scrollbarpolicy_vertical = as_needed
					scrollbar_vertical = {{ using = Scrollbar_Vertical }}
					scrollwidget = {{
						vbox = {{
							layoutpolicy_horizontal = expanding
							layoutpolicy_vertical = expanding
							vbox = {{
								layoutpolicy_horizontal = expanding
								layoutpolicy_vertical = preferred
								margin = {{ 10 8 }}
								margin_right = 18
								margin_bottom = 12
								spacing = 4
								ignoreinvisible = yes
{rows}
							}}
							# Keep a short filtered list packed at the top of the viewport.
							vbox = {{ layoutpolicy_vertical = expanding }}
						}}
					}}
				}}
				hbox = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = fixed
					size = {{ -1 36 }}
					spacing = 8
					text_single = {{ layoutpolicy_horizontal = expanding size = {{ -1 32 }} align = left|vcenter text = "eu5ab_priority_scale_hint" }}
					button_regular_alt_red = {{
						size = {{ 250 36 }}
						text = "eu5ab_clear_visible_priorities_button"
						tooltip = "eu5ab_clear_visible_priorities_tooltip"
						onclick = "[GetScriptedGui('eu5ab_gui_clear_visible_priorities').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
					}}
				}}
			}}
"""
    return _gui_window(
        "eu5ab_template_buildings_window",
        "eu5ab_template_buildings_window_title",
        "eu5ab_template_buildings_visible",
        body,
    )


def _gui_active_choice_button(gui_id: str, text_key: str, variable: str, value: int) -> str:
    return f"""checkbutton_02_alt = {{
		layoutpolicy_horizontal = expanding
		size = {{ -1 38 }}
		down = "[EqualTo_CFixedPoint(Player.MakeScope.GetVariable('{variable}').GetValue,'(CFixedPoint){value}')]"
		tooltip = "{text_key}"
		text_single = {{
			margin = {{ 8 6 }}
			default_format = "#high"
			using = Font_Size_Small
			align = center|nobaseline
			text = "{text_key}"
		}}
		onclick = "[GetScriptedGui('{gui_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
	}}"""


def _gui_active_toggle(gui_id: str, text_key: str, variable: str, icon: str) -> str:
    return f"""checkbutton_02_alt = {{
		layoutpolicy_horizontal = expanding
		size = {{ -1 38 }}
		down = "[EqualTo_CFixedPoint(Player.MakeScope.GetVariable('{variable}').GetValue,'(CFixedPoint)1')]"
		tooltip = "{text_key}"
		hbox = {{
			size = {{ 100% 100% }}
			margin = {{ 10 0 }}
			spacing = 8
			icon = {{ size = {{ 22 22 }} texture = "{icon}" texture_density = 2 }}
			text_single = {{
				layoutpolicy_horizontal = expanding
				size = {{ -1 32 }}
				autoresize = no
				fontsize = 14
				fontsize_min = 10
				align = left|vcenter
				text = "{text_key}"
			}}
		}}
		onclick = "[GetScriptedGui('{gui_id}').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).End)]"
	}}"""


def _gui_card_note(text_key: str) -> str:
    del text_key
    return ""


def _gui_value_row(
    label_key: str,
    value_key: str,
    buttons: list[tuple[str, str]],
    tooltip_key: str,
) -> str:
    del tooltip_key
    decrease_buttons = [button for button in buttons if "_dec" in button[0]]
    increase_buttons = [button for button in buttons if "_inc" in button[0]]
    if (
        len(decrease_buttons) != len(increase_buttons)
        or len(decrease_buttons) + len(increase_buttons) != len(buttons)
    ):
        raise ValueError(f"Numeric control must have balanced decrease/increase buttons: {value_key}")
    decrease_widgets = "\n".join(
        _gui_scripted_button(gui_id, text_key, 42)
        for gui_id, text_key in decrease_buttons
    )
    increase_widgets = "\n".join(
        _gui_scripted_button(gui_id, text_key, 42)
        for gui_id, text_key in increase_buttons
    )
    return f"""hbox = {{
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = fixed
		size = {{ -1 48 }}
		spacing = 8
		hbox = {{
			layoutpolicy_horizontal = preferred
			spacing = 4
{decrease_widgets}
		}}
		vbox = {{
			layoutpolicy_horizontal = expanding
			layoutpolicy_vertical = fixed
			size = {{ -1 44 }}
			spacing = 0
			text_single = {{
				layoutpolicy_horizontal = expanding
				size = {{ -1 18 }}
				autoresize = no
				fontsize = 12
				fontsize_min = 10
				align = center|vcenter
				elide = right
				text = "{label_key}"
			}}
			text_single = {{
				layoutpolicy_horizontal = expanding
				size = {{ -1 24 }}
				autoresize = no
				default_format = "#high"
				fontsize = 14
				fontsize_min = 10
				align = center|vcenter
				elide = right
				text = "{value_key}"
			}}
		}}
		hbox = {{
			layoutpolicy_horizontal = preferred
			spacing = 4
{increase_widgets}
		}}
	}}"""


def _gui_kv_row(
    label_key: str,
    value_key: str,
    *,
    visible: str | None = None,
    value_format: str | None = None,
) -> str:
    visible_line = f'\n\t\tvisible = "{visible}"' if visible is not None else ""
    format_line = f'\n\t\t\tdefault_format = "{value_format}"' if value_format is not None else ""
    return f"""hbox = {{
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = fixed
		size = {{ -1 24 }}
		spacing = 6{visible_line}
		text_single = {{
			size = {{ 210 22 }}
			autoresize = no
			fontsize = 13
			fontsize_min = 10
			align = left|vcenter
			elide = right
			text = "{label_key}"
		}}
		text_single = {{
			layoutpolicy_horizontal = expanding
			size = {{ -1 22 }}
			autoresize = no
			fontsize = 13
			fontsize_min = 10
			align = right|vcenter
			elide = right{format_line}
			text = "{value_key}"
		}}
	}}"""




def _rules_gui_equal(variable: str, value: int) -> str:
    return (
        f"[EqualTo_CFixedPoint(Player.MakeScope.GetVariable('{variable}').GetValue,"
        f"'(CFixedPoint){value}')]"
    )


def _rules_gui_greater(variable: str, value: int) -> str:
    return (
        f"[GreaterThan_CFixedPoint(Player.MakeScope.GetVariable('{variable}').GetValue,"
        f"'(CFixedPoint){value}')]"
    )


def _rules_gui_less(variable: str, value: int) -> str:
    return (
        f"[LessThan_CFixedPoint(Player.MakeScope.GetVariable('{variable}').GetValue,"
        f"'(CFixedPoint){value}')]"
    )


def _rules_gui_and(left: str, right: str) -> str:
    return (
        "[And("
        f"{left.removeprefix('[').removesuffix(']')},"
        f"{right.removeprefix('[').removesuffix(']')}"
        ")]"
    )


def _rules_gui_or(left: str, right: str) -> str:
    return (
        "[Or("
        f"{left.removeprefix('[').removesuffix(']')},"
        f"{right.removeprefix('[').removesuffix(']')}"
        ")]"
    )


def _rules_gui_not(expression: str) -> str:
    inner = expression.removeprefix("[").removesuffix("]")
    return f"[Not({inner})]"


RULES_DIAGNOSTIC_AVAILABLE = (
    "Or("
    "EqualTo_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_diag_has_run').GetValue,"
    "'(CFixedPoint)1'),"
    "GreaterThan_CFixedPoint(Player.MakeScope.GetVariable('eu5ab_diag_last_run_year').GetValue,"
    "'(CFixedPoint)0'))"
)


def _rules_gui_when_available(expression: str) -> str:
    inner = expression.removeprefix("[").removesuffix("]")
    return f"[And({RULES_DIAGNOSTIC_AVAILABLE},{inner})]"


def _render_rules_finance_content() -> str:
    fixed_budget_visible = _rules_gui_equal(_editor_var("budget_mode"), BUDGET_MODE_FIXED)
    income_budget_visible = _rules_gui_equal(_editor_var("budget_mode"), BUDGET_MODE_INCOME)
    budget_mode_choices = f"""hbox = {{
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = fixed
		size = {{ -1 42 }}
		spacing = 6
		{_gui_active_choice_button("eu5ab_gui_active_budget_mode_fixed", "eu5ab_budget_mode_fixed", _editor_var("budget_mode"), BUDGET_MODE_FIXED)}
		{_gui_active_choice_button("eu5ab_gui_active_budget_mode_income", "eu5ab_budget_mode_income", _editor_var("budget_mode"), BUDGET_MODE_INCOME)}
	}}"""
    fixed_budget_controls = f"""vbox = {{
		visible = "{fixed_budget_visible}"
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = preferred
		ignoreinvisible = yes
		{_gui_value_row(
            "eu5ab_budget_label",
            "eu5ab_annual_budget_amount",
            [
                ("eu5ab_gui_active_annual_budget_dec_10k", "eu5ab_step_dec_10k"),
                ("eu5ab_gui_active_annual_budget_dec_1k", "eu5ab_step_dec_1k"),
                ("eu5ab_gui_active_annual_budget_dec", "eu5ab_step_dec_100"),
                ("eu5ab_gui_active_annual_budget_inc", "eu5ab_step_inc_100"),
                ("eu5ab_gui_active_annual_budget_inc_1k", "eu5ab_step_inc_1k"),
                ("eu5ab_gui_active_annual_budget_inc_10k", "eu5ab_step_inc_10k"),
            ],
            "eu5ab_budget_help",
        )}
	}}"""
    income_budget_controls = f"""vbox = {{
		visible = "{income_budget_visible}"
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = preferred
		ignoreinvisible = yes
		spacing = 4
		hbox = {{
			layoutpolicy_horizontal = expanding
			layoutpolicy_vertical = fixed
			size = {{ -1 42 }}
			spacing = 6
			{_gui_active_choice_button("eu5ab_gui_active_budget_multiplier_4", "eu5ab_budget_multiplier_4", _editor_var("budget_multiplier"), 4)}
			{_gui_active_choice_button("eu5ab_gui_active_budget_multiplier_6", "eu5ab_budget_multiplier_6", _editor_var("budget_multiplier"), 6)}
			{_gui_active_choice_button("eu5ab_gui_active_budget_multiplier_8", "eu5ab_budget_multiplier_8", _editor_var("budget_multiplier"), 8)}
		}}
		{_gui_kv_row("eu5ab_budget_effective_label", "eu5ab_budget_effective_amount")}
	}}"""
    cash_card = _gui_ogas_card(
        CASH_ICON,
        "eu5ab_cash_section_title",
        "\n".join([
            _gui_card_note("eu5ab_cash_short_desc"),
            _gui_value_row(
                "eu5ab_cash_label",
                "eu5ab_active_cash_amount",
                [
                    ("eu5ab_gui_active_cash_dec_10k", "eu5ab_step_dec_10k"),
                    ("eu5ab_gui_active_cash_dec_1k", "eu5ab_step_dec_1k"),
                    ("eu5ab_gui_active_cash_inc_1k", "eu5ab_step_inc_1k"),
                    ("eu5ab_gui_active_cash_inc_10k", "eu5ab_step_inc_10k"),
                ],
                "eu5ab_cash_help",
            ),
        ]),
        tooltip_key="eu5ab_cash_help",
    )
    budget_card = _gui_ogas_card(
        CASH_ICON,
        "eu5ab_budget_section_title",
        "\n".join([
            _gui_card_note("eu5ab_budget_short_desc"),
            budget_mode_choices,
            fixed_budget_controls,
            income_budget_controls,
            _gui_card_note("eu5ab_budget_cash_comparison"),
            _gui_card_note("eu5ab_budget_reset_note"),
        ]),
        max_width=2000,
        tooltip_key="eu5ab_budget_help",
    )
    quota_card = _gui_ogas_card(
        PREDICTION_ICON,
        "eu5ab_quota_section_title",
        "\n".join([
            _gui_card_note("eu5ab_quota_short_desc"),
            _gui_value_row(
                "eu5ab_hard_cap_label",
                "eu5ab_hard_cap_amount",
                [
                    ("eu5ab_gui_monthly_hard_cap_dec", "eu5ab_step_dec_1"),
                    ("eu5ab_gui_monthly_hard_cap_inc", "eu5ab_step_inc_1"),
                ],
                "eu5ab_quota_help",
            ),
        ]),
        tooltip_key="eu5ab_quota_help",
    )
    price_card = _gui_ogas_card(
        PRICE_ICON,
        "eu5ab_price_section_title",
        "\n".join([
            _gui_card_note("eu5ab_price_short_desc"),
            _gui_value_row(
                "eu5ab_price_min_label",
                "eu5ab_active_price_min_amount",
                [
                    ("eu5ab_gui_active_price_min_dec_10", "eu5ab_step_dec_10"),
                    ("eu5ab_gui_active_price_min_dec_1", "eu5ab_step_dec_1"),
                    ("eu5ab_gui_active_price_min_inc_1", "eu5ab_step_inc_1"),
                    ("eu5ab_gui_active_price_min_inc_10", "eu5ab_step_inc_10"),
                ],
                "eu5ab_price_section_desc",
            ),
            _gui_value_row(
                "eu5ab_price_max_label",
                "eu5ab_active_price_max_amount",
                [
                    ("eu5ab_gui_active_price_max_dec_10", "eu5ab_step_dec_10"),
                    ("eu5ab_gui_active_price_max_dec_1", "eu5ab_step_dec_1"),
                    ("eu5ab_gui_active_price_max_inc_1", "eu5ab_step_inc_1"),
                    ("eu5ab_gui_active_price_max_inc_10", "eu5ab_step_inc_10"),
                ],
                "eu5ab_price_section_desc",
            ),
        ]),
        tooltip_key="eu5ab_price_section_desc",
    )
    operating_card = _gui_ogas_card(
        OPERATING_RULES_ICON,
        "eu5ab_operating_rules_title",
        "\n".join([
            _gui_card_note("eu5ab_operating_rules_short_desc"),
            _gui_active_toggle(
                "eu5ab_gui_active_toggle_allow_special_buildings",
                "eu5ab_toggle_special_buildings",
                _editor_var("allow_special_buildings"),
                BUILDING_RULES_ICON,
            ),
            _gui_active_toggle(
                "eu5ab_gui_active_toggle_auto_build_input_sources",
                "eu5ab_toggle_auto_build_input_sources",
                _editor_var("auto_build_input_sources"),
                IMPORT_ICON,
            ),
            _gui_active_toggle(
                "eu5ab_gui_active_toggle_stop_input_shortage",
                "eu5ab_toggle_stop_input_shortage",
                _editor_var("stop_input_shortage"),
                MISSING_GOODS_ICON,
            ),
        ]),
        tooltip_key="eu5ab_operating_rules_help",
    )
    return f"""vbox = {{
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = preferred
		spacing = 8
		{budget_card}
		hbox = {{
			name = "eu5ab_rules_finance_row_reserve_quota"
			layoutpolicy_horizontal = expanding
			layoutpolicy_vertical = preferred
			spacing = 8
			{cash_card}
			{quota_card}
		}}
		hbox = {{
			name = "eu5ab_rules_finance_row_price_operating"
			layoutpolicy_horizontal = expanding
			layoutpolicy_vertical = preferred
			spacing = 8
			{price_card}
			{operating_card}
		}}
	}}"""


def _render_rules_ranking_mode_card() -> str:
    composite_mode_visible = _rules_gui_equal(
        "eu5ab_global_candidate_ranking_mode",
        CMM_CANDIDATE_RANKING_COMPOSITE,
    )
    actual_profit_mode_visible = _rules_gui_equal(
        "eu5ab_global_candidate_ranking_mode",
        CMM_CANDIDATE_RANKING_ACTUAL_PROFIT,
    )

    def algorithm_text(text_key: str, visible: str | None = None) -> str:
        visible_line = f'\n\t\tvisible = "{visible}"' if visible else ""
        return f'''text_multi = {{
\t\tlayoutpolicy_horizontal = expanding
\t\tautoresize = yes{visible_line}
\t\ttext = "{text_key}"
\t}}'''

    return _gui_ogas_card(
        PREDICTION_ICON,
        "eu5ab_ranking_mode_section_title",
        "\n".join([
            _gui_kv_row(
                "eu5ab_ranking_mode_current_label",
                "eu5ab_ranking_mode_composite_value",
                visible=composite_mode_visible,
            ),
            _gui_kv_row(
                "eu5ab_ranking_mode_current_label",
                "eu5ab_ranking_mode_actual_profit_value",
                visible=actual_profit_mode_visible,
            ),
            algorithm_text("eu5ab_ranking_mode_common_desc"),
            algorithm_text("eu5ab_town_rights_preference_desc"),
            algorithm_text(
                "eu5ab_ranking_mode_composite_desc",
                composite_mode_visible,
            ),
            algorithm_text(
                "eu5ab_ranking_mode_actual_profit_desc",
                actual_profit_mode_visible,
            ),
            algorithm_text(
                "eu5ab_ranking_mode_actual_profit_scope_desc",
                actual_profit_mode_visible,
            ),
        ]),
        max_width=2000,
        tooltip_key="eu5ab_ranking_mode_help",
    )


def _render_rules_automation_content() -> str:
    ranking_mode_card = _render_rules_ranking_mode_card()
    workforce_card = _gui_ogas_card(
        WORKFORCE_ICON,
        "eu5ab_workforce_section_title",
        "\n".join([
            _gui_active_toggle(
                "eu5ab_gui_active_toggle_pause_low_workforce",
                "eu5ab_toggle_pause_low_workforce",
                _editor_var("pause_low_workforce"),
                WORKFORCE_ICON,
            ),
            _gui_card_note("eu5ab_pause_workforce_short_desc"),
            _gui_value_row(
                "eu5ab_job_fill_deadline_label",
                "eu5ab_job_fill_deadline_amount",
                [
                    ("eu5ab_gui_active_job_fill_deadline_dec", "eu5ab_step_dec_1"),
                    ("eu5ab_gui_active_job_fill_deadline_inc", "eu5ab_step_inc_1"),
                ],
                "eu5ab_job_fill_deadline_desc",
            ),
            f"""hbox = {{
				name = "eu5ab_deadline_shortcuts"
				layoutpolicy_horizontal = expanding
				spacing = 6
				{_gui_scripted_button("eu5ab_gui_active_job_fill_deadline_0", "eu5ab_deadline_0", 76)}
				{_gui_scripted_button("eu5ab_gui_active_job_fill_deadline_3", "eu5ab_deadline_3", 76)}
				{_gui_scripted_button("eu5ab_gui_active_job_fill_deadline_6", "eu5ab_deadline_6", 76)}
				{_gui_scripted_button("eu5ab_gui_active_job_fill_deadline_12", "eu5ab_deadline_12", 76)}
			}}""",
            _gui_kv_row(
                "eu5ab_prediction_status_label",
                "eu5ab_status_promotion_forecast",
            ),
            _gui_card_note("eu5ab_prediction_promotion_short_desc"),
        ]),
        tooltip_key="eu5ab_workforce_help",
        visible="[GreaterThan_CFixedPoint(GetPlayer.MakeScope.GetVariable('eu5ab_global_pause_low_workforce').GetValue, '(CFixedPoint)0')]",
    )
    native_input_card = _gui_ogas_card(
        IMPORT_ICON,
        "eu5ab_native_input_section_title",
        "\n".join([
            _gui_card_note("eu5ab_native_input_short_desc"),
            _gui_value_row(
                "eu5ab_native_input_priority_label",
                "eu5ab_native_input_priority_amount",
                [
                    ("eu5ab_gui_active_native_input_priority_dec", "eu5ab_step_dec_1"),
                    ("eu5ab_gui_active_native_input_priority_inc", "eu5ab_step_inc_1"),
                ],
                "eu5ab_native_input_priority_desc",
            ),
        ]),
        max_width=2000,
        tooltip_key="eu5ab_native_input_priority_desc",
    )
    rgo_card = _gui_ogas_card(
        BUILDING_RULES_ICON,
        "eu5ab_rgo_section_title",
        "\n".join([
            _gui_active_toggle(
                "eu5ab_gui_active_toggle_allow_rgo",
                "eu5ab_rgo_allow",
                _editor_var("allow_rgo"),
                BUILDING_RULES_ICON,
            ),
            _gui_card_note("eu5ab_rgo_short_desc"),
        ]),
        tooltip_key="eu5ab_rgo_help",
    )
    return f"""vbox = {{
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = preferred
		spacing = 8
		{ranking_mode_card}
		hbox = {{
			name = "eu5ab_rules_automation_row_workforce_rgo"
			layoutpolicy_horizontal = expanding
			layoutpolicy_vertical = preferred
			spacing = 8
			{workforce_card}
			{rgo_card}
		}}
		hbox = {{
			name = "eu5ab_rules_automation_row_inputs"
			layoutpolicy_horizontal = expanding
			layoutpolicy_vertical = preferred
			spacing = 8
			{native_input_card}
		}}
	}}"""


def _render_rules_diagnostic_overview_card() -> str:
    diag_visible = f"[{RULES_DIAGNOSTIC_AVAILABLE}]"
    diag_not_visible = f"[Not({RULES_DIAGNOSTIC_AVAILABLE})]"
    diag_success = _rules_gui_when_available(
        _rules_gui_and(
            _rules_gui_equal("eu5ab_diag_built_this_run", 1),
            _rules_gui_not(_rules_gui_equal("eu5ab_diag_scan_stalled", 1)),
        )
    )
    diag_completed_no_build = _rules_gui_when_available(
        _rules_gui_and(
            _rules_gui_and(
                _rules_gui_equal("eu5ab_diag_run_state", 5),
                _rules_gui_equal("eu5ab_diag_built_this_run", 2),
            ),
            _rules_gui_not(_rules_gui_equal("eu5ab_diag_scan_stalled", 1)),
        )
    )
    rows = [
        _gui_card_note("eu5ab_diagnostics_snapshot_note"),
        _gui_kv_row(
            "eu5ab_diag_label_status",
            "eu5ab_diag_state_not_run",
            visible=diag_not_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_status",
            "eu5ab_diag_state_success",
            visible=diag_success,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_status",
            "eu5ab_diag_state_complete_no_build",
            visible=diag_completed_no_build,
        ),
    ]
    for state, key in [
        (1, "eu5ab_diag_state_no_coverage"),
        (2, "eu5ab_diag_state_hard_cap"),
        (4, "eu5ab_diag_state_no_preliminary"),
    ]:
        rows.append(
            _gui_kv_row(
                "eu5ab_diag_label_status",
                key,
                visible=_rules_gui_when_available(
                    _rules_gui_equal("eu5ab_diag_run_state", state)
                ),
            )
        )
    rows.extend([
        *(_gui_kv_row(f"eu5ab_diag_label_capacity_{field}", f"eu5ab_diag_capacity_{field}_value", visible=diag_visible)
          for field in ("waiting", "unavailable", "expired")),
        *(_gui_kv_row("eu5ab_diag_label_capacity_reason", f"eu5ab_diag_capacity_reason_{reason}",
                     visible=_rules_gui_when_available(_rules_gui_equal("eu5ab_diag_capacity_last_reason", reason)))
          for reason in (1, 2, 3)),
        _gui_kv_row(
            "eu5ab_diag_label_status",
            "eu5ab_diag_state_scan_stalled",
            visible=_rules_gui_when_available(
                _rules_gui_equal("eu5ab_diag_scan_stalled", 1)
            ),
        ),
        _gui_kv_row(
            "eu5ab_diag_label_last_run",
            "eu5ab_diag_last_run_value",
            visible=diag_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_covered",
            "eu5ab_diag_covered_value",
            visible=diag_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_preliminary",
            "eu5ab_diag_preliminary_value",
            visible=diag_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_deep_scored",
            "eu5ab_diag_deep_scored_value",
            visible=diag_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_legal",
            "eu5ab_diag_legal_value",
            visible=diag_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_staged_candidates",
            "eu5ab_diag_staged_candidates_value",
            visible=diag_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_engine_probes",
            "eu5ab_diag_engine_probes_value",
            visible=diag_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_queue_throttle",
            "eu5ab_status_queue_throttled",
            visible=_rules_gui_when_available(
                _rules_gui_equal("eu5ab_diag_concurrent_limit_state", 1)
            ),
        ),
        _gui_kv_row(
            "eu5ab_diag_label_queue_throttle",
            "eu5ab_status_not_throttled",
            visible=_rules_gui_when_available(
                _rules_gui_equal("eu5ab_diag_concurrent_limit_state", 2)
            ),
        ),
        *[
            _gui_kv_row(
                "eu5ab_diag_label_engine_queue",
                key,
                visible=_rules_gui_when_available(
                    _rules_gui_equal("eu5ab_diag_queue_state", state)
                ),
            )
            for state, key in [
                (1, "eu5ab_status_engine_queue_prepared"),
                (2, "eu5ab_status_engine_queue_validating"),
                (3, "eu5ab_status_engine_queue_executing"),
                (4, "eu5ab_status_engine_queue_confirmed"),
                (5, "eu5ab_status_engine_queue_recovered"),
                (6, "eu5ab_status_engine_queue_profit_ranking"),
            ]
        ],
        _gui_kv_row(
            "eu5ab_diag_label_queue_recoveries",
            "eu5ab_diag_queue_recoveries_value",
            visible=diag_visible,
        ),
        _gui_kv_row(
            "eu5ab_diag_label_prediction_mode",
            "eu5ab_status_prediction_realtime",
            visible=_rules_gui_when_available(
                _rules_gui_and(_rules_gui_equal("eu5ab_diag_workforce_prediction_mode", 1), _rules_gui_equal("eu5ab_global_pause_low_workforce", 1))
            ),
        ),
        _gui_kv_row(
            "eu5ab_diag_label_prediction_mode",
            "eu5ab_status_prediction_proxy",
            visible=_rules_gui_when_available(
                _rules_gui_and(_rules_gui_equal("eu5ab_diag_workforce_prediction_mode", 2), _rules_gui_equal("eu5ab_global_pause_low_workforce", 1))
            ),
        ),
        _gui_kv_row(
            "eu5ab_diag_label_prediction_mode",
            "eu5ab_status_conservative_fallback",
            visible=_rules_gui_when_available(
                _rules_gui_and(_rules_gui_equal("eu5ab_diag_workforce_prediction_mode", 3), _rules_gui_equal("eu5ab_global_pause_low_workforce", 1))
            ),
        ),
    ])
    return _gui_ogas_card(
        PREDICTION_ICON,
        "eu5ab_diag_overview_title",
        "\n".join(rows),
        max_width=920,
        tooltip_key="eu5ab_diagnostics_snapshot_help",
    )


def _render_rules_quota_diagnostics_card() -> str:
    diag_visible = f"[{RULES_DIAGNOSTIC_AVAILABLE}]"
    return _gui_ogas_card(
        CASH_ICON,
        "eu5ab_diag_quota_title",
        "\n".join([
            _gui_card_note("eu5ab_diag_quota_short_desc"),
            _gui_kv_row(
                "eu5ab_diag_label_capacity_summary",
                "eu5ab_diag_capacity_summary_value",
                visible=diag_visible,
            ),
            _gui_kv_row(
                "eu5ab_diag_label_emergency_overrides",
                "eu5ab_diag_emergency_overrides_value",
                visible=diag_visible,
            ),
            _gui_kv_row(
                "eu5ab_diag_label_rgo_used",
                "eu5ab_diag_rgo_used_value",
                visible=diag_visible,
            ),
        ]),
        max_width=920,
        tooltip_key="eu5ab_quota_help",
    )


def _render_rules_rgo_diagnostics_card() -> str:
    diag_visible = f"[{RULES_DIAGNOSTIC_AVAILABLE}]"
    rows = [_gui_card_note("eu5ab_diag_rgo_short_desc")]
    for label_key, value_key in [
        ("eu5ab_diag_rgo_checked_label", "eu5ab_diag_rgo_checked_value"),
        ("eu5ab_diag_rgo_eligible_label", "eu5ab_diag_rgo_eligible_value"),
        ("eu5ab_diag_rgo_fail_capacity_label", "eu5ab_diag_rgo_fail_capacity_value"),
        ("eu5ab_diag_rgo_fail_location_label", "eu5ab_diag_rgo_fail_location_value"),
        ("eu5ab_diag_rgo_fail_disabled_label", "eu5ab_diag_rgo_fail_disabled_value"),
        ("eu5ab_diag_rgo_fail_finance_label", "eu5ab_diag_rgo_fail_finance_value"),
        ("eu5ab_diag_rgo_fail_utilization_label", "eu5ab_diag_rgo_fail_utilization_value"),
        ("eu5ab_diag_rgo_fail_workforce_label", "eu5ab_diag_rgo_fail_workforce_value"),
        ("eu5ab_diag_rgo_fail_market_need_label", "eu5ab_diag_rgo_fail_market_need_value"),
        ("eu5ab_diag_rgo_fail_score_label", "eu5ab_diag_rgo_fail_score_value"),
        ("eu5ab_diag_rgo_fail_pending_data_label", "eu5ab_diag_rgo_fail_pending_data_value"),
        ("eu5ab_diag_rgo_fail_pending_limit_label", "eu5ab_diag_rgo_fail_pending_limit_value"),
    ]:
        rows.append(_gui_kv_row(label_key, value_key, visible=diag_visible))
    pending_visible = _rules_gui_when_available(_rules_gui_greater("eu5ab_diag_rgo_pending_state", 0))
    for key in ("location", "gap", "quantity", "limit", "factor"):
        rows.append(_gui_kv_row(f"eu5ab_diag_rgo_pending_{key}_label", f"eu5ab_diag_rgo_pending_{key}_value", visible=pending_visible))
    for state in range(1, 5):
        rows.append(_gui_kv_row("eu5ab_diag_rgo_pending_state_label", f"eu5ab_diag_rgo_pending_state_{state}", visible=_rules_gui_when_available(_rules_gui_equal("eu5ab_diag_rgo_pending_state", state))))
    return _gui_ogas_card(
        BUILDING_RULES_ICON,
        "eu5ab_diag_rgo_title",
        "\n".join(rows),
        max_width=920,
        tooltip_key="eu5ab_diag_rgo_help",
    )


def _render_rules_result_card() -> str:
    diag_visible = f"[{RULES_DIAGNOSTIC_AVAILABLE}]"
    diag_not_visible = f"[Not({RULES_DIAGNOSTIC_AVAILABLE})]"
    actual_build_visible = _rules_gui_when_available(
        _rules_gui_and(
            _rules_gui_equal("eu5ab_diag_built_this_run", 1),
            _rules_gui_or(
                _rules_gui_equal("eu5ab_diag_last_build_kind", 2),
                _rules_gui_or(
                    _rules_gui_equal("eu5ab_diag_last_build_kind", 3),
                    _rules_gui_equal("eu5ab_diag_last_build_kind", 4),
                ),
            ),
        )
    )
    return _gui_ogas_card(
        BUILDING_RULES_ICON,
        "eu5ab_diag_result_title",
        "\n".join([
            _gui_kv_row(
                "eu5ab_diag_label_result",
                "eu5ab_status_waiting_next_month",
                visible=diag_not_visible,
            ),
            _gui_kv_row(
                "eu5ab_diag_label_result",
                "eu5ab_diag_no_build_this_run",
                visible=_rules_gui_when_available(
                    _rules_gui_equal("eu5ab_diag_built_this_run", 2)
                ),
            ),
            _gui_kv_row(
                "eu5ab_diag_label_result",
                "eu5ab_diag_result_rgo_value",
                visible=_rules_gui_when_available(
                    _rules_gui_and(
                        _rules_gui_equal("eu5ab_diag_built_this_run", 1),
                        _rules_gui_equal("eu5ab_diag_last_build_kind", 1),
                    )
                ),
            ),
            _gui_kv_row(
                "eu5ab_diag_label_result",
                "eu5ab_diag_result_new_value",
                visible=_rules_gui_when_available(
                    _rules_gui_and(
                        _rules_gui_equal("eu5ab_diag_built_this_run", 1),
                        _rules_gui_equal("eu5ab_diag_last_build_kind", 3),
                    )
                ),
            ),
            _gui_kv_row(
                "eu5ab_diag_label_result",
                "eu5ab_diag_result_upgrade_value",
                visible=_rules_gui_when_available(
                    _rules_gui_and(
                        _rules_gui_equal("eu5ab_diag_built_this_run", 1),
                        _rules_gui_equal("eu5ab_diag_last_build_kind", 2),
                    )
                ),
            ),
            _gui_kv_row(
                "eu5ab_diag_label_result",
                "eu5ab_diag_result_expansion_value",
                visible=_rules_gui_when_available(
                    _rules_gui_and(
                        _rules_gui_equal("eu5ab_diag_built_this_run", 1),
                        _rules_gui_equal("eu5ab_diag_last_build_kind", 4),
                    )
                ),
            ),
            _gui_kv_row(
                "eu5ab_diag_label_previous_month_added",
                "eu5ab_diag_previous_month_added_value",
                visible=diag_visible,
            ),
            _gui_kv_row(
                "eu5ab_diag_label_expected_this_run",
                "eu5ab_diag_expected_this_run_value",
                visible=diag_visible,
            ),
            _gui_kv_row(
                "eu5ab_diag_label_actual_cost",
                "eu5ab_diag_actual_cost_value",
                visible=actual_build_visible,
            ),
            _gui_kv_row(
                "eu5ab_diag_label_actual_income",
                "eu5ab_diag_actual_income_value",
                visible=actual_build_visible,
            ),
            _gui_kv_row(
                "eu5ab_diag_label_actual_profit",
                "eu5ab_diag_actual_profit_value",
                visible=actual_build_visible,
            ),
        ]),
        max_width=920,
        tooltip_key="eu5ab_diag_result_help",
    )


def _render_rules_failure_card() -> str:
    diag_visible = f"[{RULES_DIAGNOSTIC_AVAILABLE}]"
    rows = [_gui_card_note("eu5ab_diag_failure_short_desc")]
    for label_key, value_key in [
        ("eu5ab_diag_fail_building_capacity_label", "eu5ab_diag_fail_building_capacity_value"),
        ("eu5ab_diag_fail_capacity_unavailable_label", "eu5ab_diag_fail_capacity_unavailable_value"),
        ("eu5ab_diag_fail_workforce_label", "eu5ab_diag_fail_workforce_value"),
        ("eu5ab_diag_fail_inputs_label", "eu5ab_diag_fail_inputs_value"),
        ("eu5ab_diag_fail_pending_output_label", "eu5ab_diag_fail_pending_output_value"),
        ("eu5ab_diag_fail_oversupply_label", "eu5ab_diag_fail_oversupply_value"),
        ("eu5ab_diag_fail_irrigation_need_label", "eu5ab_diag_fail_irrigation_need_value"),
        ("eu5ab_diag_fail_granary_need_label", "eu5ab_diag_fail_granary_need_value"),
        ("eu5ab_diag_fail_storage_pending_label", "eu5ab_diag_fail_storage_pending_value"),
        ("eu5ab_diag_fail_windmill_need_label", "eu5ab_diag_fail_windmill_need_value"),
        ("eu5ab_diag_fail_budget_label", "eu5ab_diag_fail_budget_value"),
        ("eu5ab_diag_fail_cash_label", "eu5ab_diag_fail_cash_value"),
        ("eu5ab_diag_fail_engine_economics_label", "eu5ab_diag_fail_engine_economics_value"),
        ("eu5ab_diag_fail_construction_materials_label", "eu5ab_diag_fail_construction_materials_value"),
        ("eu5ab_diag_fail_vanilla_label", "eu5ab_diag_fail_vanilla_value"),
        ("eu5ab_diag_fail_no_legal_label", "eu5ab_diag_fail_no_legal_value"),
    ]:
        rows.append(_gui_kv_row(label_key, value_key, visible=diag_visible))
    return _gui_ogas_card(
        MISSING_GOODS_ICON,
        "eu5ab_diag_failure_title",
        "\n".join(rows),
        max_width=920,
        tooltip_key="eu5ab_diag_failure_help",
    )


def _render_rules_candidates_card() -> str:
    candidate_widgets: list[str] = []
    for rank in range(1, 4):
        candidate_available = _rules_gui_greater(f"eu5ab_diag_top_{rank}_kind", 0)
        candidate_visible = _rules_gui_when_available(
            candidate_available
        )
        empty_visible = _rules_gui_when_available(
            _rules_gui_not(candidate_available)
        )
        ordinary_visible = _rules_gui_equal(f"eu5ab_diag_top_{rank}_kind", 1)
        rgo_visible = _rules_gui_equal(f"eu5ab_diag_top_{rank}_kind", 2)
        reason_rows = []
        for reason_code, reason_key in [
            (8, "eu5ab_candidate_reason_ranked"),
            (10, "eu5ab_candidate_reason_waiting"),
            (11, "eu5ab_candidate_reason_approved"),
            (12, "eu5ab_candidate_reason_confirmed"),
            (13, "eu5ab_candidate_reason_rejected"),
            (1, "eu5ab_candidate_reason_workforce"),
            (2, "eu5ab_candidate_reason_inputs"),
            (3, "eu5ab_candidate_reason_oversupply"),
            (9, "eu5ab_candidate_reason_pending_output"),
            (4, "eu5ab_candidate_reason_budget"),
            (5, "eu5ab_candidate_reason_cash"),
            (6, "eu5ab_candidate_reason_vanilla"),
            (7, "eu5ab_candidate_reason_no_legal"),
        ]:
            reason_rows.append(
                _gui_kv_row(
                    "eu5ab_diag_label_unselected_reason",
                    reason_key,
                    visible=_rules_gui_equal(
                        f"eu5ab_diag_top_{rank}_reason",
                        reason_code,
                    ),
                )
            )
        candidate_widgets.append(
            f"""vbox = {{
				visible = "{candidate_visible}"
				layoutpolicy_horizontal = expanding
				layoutpolicy_vertical = preferred
				using = bg_number_container_bckg
				margin = {{ 10 8 }}
				spacing = 4
				text_single = {{
					layoutpolicy_horizontal = expanding
					default_format = "#yellow_titles"
					text = "eu5ab_diag_candidate_{rank}_title"
				}}
				{_gui_kv_row("eu5ab_diag_label_location", f"eu5ab_diag_candidate_{rank}_location_value")}
				{_gui_kv_row("eu5ab_diag_label_building", f"eu5ab_diag_candidate_{rank}_building_value", visible=ordinary_visible)}
				{_gui_kv_row("eu5ab_diag_label_building", "eu5ab_diag_candidate_rgo_value", visible=rgo_visible)}
				{_gui_kv_row("eu5ab_diag_label_scores", f"eu5ab_diag_candidate_{rank}_scores_value", visible=ordinary_visible)}
				{_gui_kv_row("eu5ab_diag_label_scores", f"eu5ab_diag_candidate_{rank}_rgo_scores_value", visible=rgo_visible)}
				{_gui_kv_row("eu5ab_diag_label_workforce", f"eu5ab_diag_candidate_{rank}_workforce_value", visible=_rules_gui_when_available(_rules_gui_and(_rules_gui_equal("eu5ab_global_pause_low_workforce", 1), _rules_gui_or(_rules_gui_equal(f"eu5ab_diag_top_{rank}_kind", 1), _rules_gui_equal("eu5ab_global_rgo_workforce_mode", 2)))))}
				{_gui_kv_row("eu5ab_diag_rgo_factors_label", f"eu5ab_diag_candidate_{rank}_rgo_factors_value", visible=_rules_gui_when_available(_rules_gui_equal(f"eu5ab_diag_top_{rank}_kind", 2)))}
				{_gui_kv_row("eu5ab_diag_rgo_pending_label", f"eu5ab_diag_candidate_{rank}_rgo_pending_value", visible=rgo_visible)}
				{'\n'.join(reason_rows)}
			}}"""
        )
        candidate_widgets.append(
            f"""vbox = {{
				visible = "{empty_visible}"
				layoutpolicy_horizontal = expanding
				layoutpolicy_vertical = preferred
				using = bg_number_container_bckg
				margin = {{ 10 8 }}
				spacing = 4
				text_single = {{
					layoutpolicy_horizontal = expanding
					default_format = "#yellow_titles"
					text = "eu5ab_diag_candidate_{rank}_title"
				}}
				text_multi = {{
					layoutpolicy_horizontal = expanding
					autoresize = yes
					text = "eu5ab_diag_candidate_empty_value"
				}}
			}}"""
        )
    no_candidates = _rules_gui_less("eu5ab_diag_top_1_kind", 1)
    concurrent_limit_full = _rules_gui_equal(
        "eu5ab_diag_concurrent_limit_state",
        1,
    )
    full_limit_visible = _rules_gui_when_available(
        _rules_gui_and(no_candidates, concurrent_limit_full)
    )
    no_candidates_visible = _rules_gui_when_available(
        _rules_gui_and(no_candidates, _rules_gui_not(concurrent_limit_full))
    )
    return _gui_ogas_card(
        PREDICTION_ICON,
        "eu5ab_diag_candidates_title",
        "\n".join([
            f"""text_multi = {{
				visible = "{full_limit_visible}"
				layoutpolicy_horizontal = expanding
				autoresize = yes
				text = "eu5ab_diag_candidates_not_scanned_full"
			}}""",
            f"""text_multi = {{
				visible = "{no_candidates_visible}"
				layoutpolicy_horizontal = expanding
				autoresize = yes
				text = "eu5ab_diag_no_ranked_candidates"
			}}""",
            *candidate_widgets,
        ]),
        max_width=920,
        tooltip_key="eu5ab_diag_candidates_help",
    )


def _render_rules_diagnostics_content() -> str:
    return f"""vbox = {{
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = preferred
		spacing = 6
		{_render_rules_diagnostic_overview_card()}
		{_render_rules_quota_diagnostics_card()}
		{_render_rules_rgo_diagnostics_card()}
		{_render_rules_result_card()}
		{_render_rules_failure_card()}
		{_render_rules_candidates_card()}
	}}"""


def _render_rules_page_scrollarea(page: int, name: str, content: str) -> str:
    return f"""vbox = {{
		name = "eu5ab_rules_page_{name}"
		visible = "{_rules_gui_equal('eu5ab_rules_page', page)}"
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = expanding
		scrollarea = {{
			layoutpolicy_horizontal = expanding
			layoutpolicy_vertical = expanding
			scrollbarpolicy_horizontal = always_off
			scrollbarpolicy_vertical = as_needed
			scrollbar_vertical = {{ using = Scrollbar_Vertical }}
			scrollwidget = {{
				vbox = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = expanding
					vbox = {{
						layoutpolicy_horizontal = expanding
						layoutpolicy_vertical = preferred
						margin = {{ 8 8 }}
						margin_right = 18
						spacing = 8
						{content}
					}}
					# Keep compact rule cards at the top; this spacer absorbs unused height.
					vbox = {{ layoutpolicy_vertical = expanding }}
				}}
			}}
		}}
	}}"""


def render_active_template_rules_gui() -> str:
    body = f"""
			vbox = {{
				layoutpolicy_horizontal = expanding
				layoutpolicy_vertical = expanding
				using = bg_secondary_inner_alt
				margin = {{ 10 10 }}
				spacing = 8
				text_multi = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = fixed
					autoresize = yes
					align = center
					text = "eu5ab_diagnostics_cmm_hint"
				}}
				scrollarea = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = expanding
					scrollbarpolicy_horizontal = always_off
					scrollbarpolicy_vertical = as_needed
					scrollbar_vertical = {{ using = Scrollbar_Vertical }}
					scrollwidget = {{
						vbox = {{
							layoutpolicy_horizontal = expanding
							layoutpolicy_vertical = preferred
							margin = {{ 8 8 }}
							margin_right = 18
							spacing = 8
							{_render_rules_ranking_mode_card()}
							{_render_rules_diagnostics_content()}
						}}
					}}
				}}
			}}
"""
    window = _gui_window(
        "eu5ab_template_rules_window",
        "eu5ab_template_rules_window_title",
        "eu5ab_template_rules_visible",
        body,
        height=700,
        width=980,
    )
    return _render_rules_help_tooltips() + "\n\n" + window


def render_template_scope_gui(policies: list[Policy]) -> str:
    del policies

    types = """types EU5ABTemplateScopeTypes {
	type eu5ab_template_scope_location_entry = hbox {
		visible = "[Location.MakeScope.GetVariable('eu5ab_scope_view_selected').IsSet]"
		layoutpolicy_horizontal = expanding
		size = { -1 34 }
		spacing = 0
		using = bg_number_container_bckg
		widget = {
			size = { 44 34 }
			icon = {
				size = { 22 22 }
				parentanchor = center
				widgetanchor = center
				texture = "[Location.GetRankIcon]"
				tooltipwidget = { using = location_simple_tooltip }
			}
		}
		text_single = {
			size = { 310 34 }
			autoresize = no
			maximumsize = { 310 34 }
			align = left|vcenter
			elide = right
			text = "[Location.GetName]"
		}
		widget = { size = { 36 34 } }
		button_regular = {
			size = { 112 28 }
			enabled = "[GetScriptedGui('eu5ab_gui_clear_location_template').IsValid(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('target_location', Location.MakeScope).End)]"
			tooltip = "eu5ab_scope_remove_location_tt"
			text_single = {
				size = { 104 24 }
				parentanchor = center
				widgetanchor = center
				autoresize = no
				maximumsize = { 104 24 }
				fontsize = 13
				fontsize_min = 10
				align = center|nobaseline
				elide = right
				text = "eu5ab_scope_remove_location"
			}
			onclick = "[GetScriptedGui('eu5ab_gui_clear_location_template').Execute(GuiScope.SetRoot(GetPlayer.MakeScope).AddScope('target_location', Location.MakeScope).End)]"
		}
		widget = { layoutpolicy_horizontal = expanding size = { -1 34 } }
	}

	type eu5ab_template_scope_province_entry = vbox {
		visible = "[GetScriptedGui('eu5ab_gui_active_template_has_locations_in_province').IsShown(GuiScope.SetRoot(Province.GetCapital.MakeScope).End)]"
		layoutpolicy_horizontal = expanding
		layoutpolicy_vertical = preferred
		spacing = 2
		widget = {
			layoutpolicy_horizontal = expanding
			size = { -1 36 }
			using = bg_paper_card
			hbox = {
				layoutpolicy_horizontal = expanding
				spacing = 0
				widget = {
					size = { 44 36 }
					button_square_plus = {
						size = { 28 28 }
						parentanchor = center
						widgetanchor = center
						visible = "[Not(Province.GetCapital.MakeScope.GetVariable('eu5ab_scope_view_expanded').IsSet)]"
						enabled = "[GetScriptedGui('eu5ab_gui_expand_scope_province').IsValid(GuiScope.SetRoot(Province.GetCapital.MakeScope).End)]"
						tooltip = "eu5ab_scope_expand_province_tt"
						onclick = "[GetScriptedGui('eu5ab_gui_expand_scope_province').Execute(GuiScope.SetRoot(Province.GetCapital.MakeScope).End)]"
					}
					button_square_minus = {
						size = { 28 28 }
						parentanchor = center
						widgetanchor = center
						visible = "[Province.GetCapital.MakeScope.GetVariable('eu5ab_scope_view_expanded').IsSet]"
						enabled = "[GetScriptedGui('eu5ab_gui_collapse_scope_province').IsValid(GuiScope.SetRoot(Province.GetCapital.MakeScope).End)]"
						tooltip = "eu5ab_scope_collapse_province_tt"
						onclick = "[GetScriptedGui('eu5ab_gui_collapse_scope_province').Execute(GuiScope.SetRoot(Province.GetCapital.MakeScope).End)]"
					}
				}
				text_single = { size = { 310 36 } autoresize = no maximumsize = { 310 36 } align = left|vcenter elide = right text = "[Province.GetCapital.GetArea.GetNameWithNoTooltip]" }
				text_single = { size = { 36 36 } autoresize = no maximumsize = { 36 36 } align = center raw_text = "›" }
				text_single = { size = { -1 36 } layoutpolicy_horizontal = expanding autoresize = no align = left|vcenter elide = right text = "[Province.GetName]" }
			}
		}
		vbox = {
			visible = "[Province.GetCapital.MakeScope.GetVariable('eu5ab_scope_view_expanded').IsSet]"
			layoutpolicy_horizontal = expanding
			layoutpolicy_vertical = preferred
			ignoreinvisible = yes
			datamodel = "[Province.GetLocations]"
			item = { eu5ab_template_scope_location_entry = {} }
		}
	}
}

"""
    body = f"""
			vbox = {{
				layoutpolicy_horizontal = expanding
				layoutpolicy_vertical = expanding
				using = bg_secondary_inner_alt
				margin = {{ 12 12 }}
				spacing = 8
				text_multi = {{ size = {{ -1 42 }} autoresize = yes align = center text = "eu5ab_template_scope_desc" }}
				text_multi = {{ size = {{ -1 34 }} autoresize = yes align = center text = "eu5ab_scope_map_mode_hint" }}
				hbox = {{
					layoutpolicy_horizontal = expanding
					spacing = 8
					text_single = {{ size = {{ -1 34 }} layoutpolicy_horizontal = expanding align = center text = "eu5ab_scope_current_summary" }}
					{_gui_scripted_button("eu5ab_gui_clear_current_template_scope", "eu5ab_scope_clear_all", 220, "eu5ab_scope_clear_all_tt")}
				}}
				scrollbox = {{
					layoutpolicy_horizontal = expanding
					layoutpolicy_vertical = expanding
					blockoverride "scrollbox_content" {{
						vbox = {{
							layoutpolicy_horizontal = expanding
							layoutpolicy_vertical = preferred
							margin = {{ 10 8 }}
							margin_right = 20
							spacing = 3
							ignoreinvisible = yes
							datamodel = "[Player.GetProvinces]"
							item = {{ eu5ab_template_scope_province_entry = {{}} }}
						}}
					}}
				}}
			}}
"""
    window = _gui_window(
        "eu5ab_template_scope_window",
        "eu5ab_template_scope_window_title",
        "eu5ab_template_scope_visible",
        body,
        close_lines=[
            "on_action = \"[GetVariableSystem.Clear('eu5ab_template_scope_visible')]\"",
            "on_action = \"[GetVariableSystem.Set('eu5ab_window_open', '1')]\"",
        ],
    )
    return types + "\n" + window


def render_template_scope_map_mode() -> str:
    return """# Generated by eu5autobuild.generator.
# Native map mode shown in the base game's Geography category.
eu5ab_template_coverage = {
	map_color = {
		if = {
			limit = {
				has_owner = yes
				owner ?= { is_human = yes }
				OR = {
					AND = {
						owner = {
							has_variable = eu5ab_scope_view_mode
							has_variable = eu5ab_scope_view_value
							var:eu5ab_scope_view_mode = 1
						}
						has_variable = eu5ab_template_slot
						var:eu5ab_template_slot = owner.var:eu5ab_scope_view_value
					}
					AND = {
						owner = {
							has_variable = eu5ab_scope_view_mode
							has_variable = eu5ab_scope_view_value
							var:eu5ab_scope_view_mode = 2
						}
						NOT = { has_variable = eu5ab_template_slot }
						has_variable = eu5ab_policy_id
						var:eu5ab_policy_id = owner.var:eu5ab_scope_view_value
					}
				}
			}
			value = define:NMapColors|MAP_COLOR_HIGH
		}
		else_if = {
			limit = { has_owner = yes owner ?= { is_human = yes } has_variable = eu5ab_policy_id }
			value = define:NMapColors|MAP_COLOR_LOW
		}
		else = { value = define:NMapColors|DEFAULT_COLOR }
	}

	tooltip_key = {
		if = {
			limit = {
				has_owner = yes
				owner ?= { is_human = yes }
				OR = {
					AND = {
						owner = {
							has_variable = eu5ab_scope_view_mode
							has_variable = eu5ab_scope_view_value
							var:eu5ab_scope_view_mode = 1
						}
						has_variable = eu5ab_template_slot
						var:eu5ab_template_slot = owner.var:eu5ab_scope_view_value
					}
					AND = {
						owner = {
							has_variable = eu5ab_scope_view_mode
							has_variable = eu5ab_scope_view_value
							var:eu5ab_scope_view_mode = 2
						}
						NOT = { has_variable = eu5ab_template_slot }
						has_variable = eu5ab_policy_id
						var:eu5ab_policy_id = owner.var:eu5ab_scope_view_value
					}
				}
			}
			value = eu5ab_scope_map_selected_tt
		}
		else_if = {
			limit = { has_owner = yes owner ?= { is_human = yes } has_variable = eu5ab_policy_id }
			value = eu5ab_scope_map_other_tt
		}
		else = { value = eu5ab_scope_map_unassigned_tt }
	}

	legend_key = {
		desc = eu5ab_scope_map_legend_selected
		color = define:NMapColors|MAP_COLOR_HIGH
	}
	legend_key = {
		desc = eu5ab_scope_map_legend_other
		color = define:NMapColors|MAP_COLOR_LOW
	}

	small_map_names = location
	medium_map_names = province
	large_map_names = area
	small_tooltip_context = location
	medium_tooltip_context = location
	large_tooltip_context = location
	category = geography
	# EU5 1.3 enumerates geography groups 0-3 explicitly in this map-mode selector.
	index = 3
	allow_allocate_hotkey = yes
	flatmap_behaviour = Always
	fill_in_impassable = no
	use_fow = no
	enable_rivers = yes
	map_markers = { all = no }

	gradient_parameters = {
		zoom_step = 2
		gradient_alpha_inside = 1
		gradient_alpha_outside = 1
		gradient_width = 0.25
		gradient_color_mult = 0.9
		edge_width = 0
		edge_sharpness = 0.01
		edge_alpha = 0
		edge_color_mult = 0
		before_lighting_blend = 0.5
		after_lighting_blend = 0.5
	}
	flatmap_gradient_parameters = {
		zoom_step = 12
		gradient_alpha_inside = 1
		gradient_alpha_outside = 1
		gradient_width = 0.25
		gradient_color_mult = 0.9
		edge_width = 0
		edge_sharpness = 0.01
		edge_alpha = 0
		edge_color_mult = 0
		before_lighting_blend = 0.5
		after_lighting_blend = 0.5
	}
	color_refresh_counters = { Day }
	color_and_names_refresh_counters = { LocationOwnerChanged }
}
"""


def render_scripted_windows() -> str:
    return """gui/eu5ab_engine_queue_window.gui = eu5ab_engine_queue_window
gui/eu5ab_automation_buildings_window.gui = eu5ab_automation_buildings_window
gui/eu5ab_governor_recommendation_window.gui = eu5ab_governor_recommendation_window
gui/eu5ab_governor_worker.gui = eu5ab_governor_worker
gui/eu5ab_template_editor_window.gui = eu5ab_template_editor_window
gui/eu5ab_template_buildings_window.gui = eu5ab_template_buildings_window
gui/eu5ab_template_rules_window.gui = eu5ab_template_rules_window
gui/eu5ab_template_rename_window.gui = eu5ab_template_rename_window
gui/eu5ab_template_scope_window.gui = eu5ab_template_scope_window
"""


def _cmm_chinese_localization_lines() -> list[str]:
    values = {
        "eu5ab_regional_development_name": "高级自动建造",
        "eu5ab_regional_development_desc": "配置全国所有模板共享的建造预算、安全限制、收益门槛、决策策略与性能参数。各模板单独保存启停状态、应用地点与建筑优先级。",
        "eu5ab_regional_development__general_name": "总开关与额度",
        "eu5ab_regional_development__finance_name": "财政与市场",
        "eu5ab_regional_development__automation_name": "建造安全与排序",
        "eu5ab_regional_development__performance_name": "性能优化",
        "eu5ab_regional_development__performance__preset_name": "性能预设",
        "eu5ab_regional_development__performance__preset_desc": "性能预设会自动联动下方高级参数。手动修改高级设置后会自动切换为「自定义」，并于下一次月度检查开始生效。",
        "eu5ab_regional_development__performance__advanced_name": "高级设置",
        "eu5ab_regional_development__performance__advanced_desc": "调整每天检查的地点数、每轮新增工程数和备选项目数。检查和比较的项目越多，耗时可能越长。",
        "eu5ab_regional_development__general__limits_name": "总开关与同时建造上限",
        "eu5ab_regional_development__general__limits_desc": "配置自动建造总开关以及本 Mod 允许同时在建的民用工程总数上限。",
        "eu5ab_regional_development__general__returns_name": "收益条件与紧急放宽",
        "eu5ab_regional_development__general__returns_desc": "为普通生产建筑设定开工的最低收益门槛，并配置在食物短缺、建材匮乏、战时军需告急或战略原料断供时是否自动放宽收益限制。",
        "eu5ab_regional_development__finance__budget_name": "共享年度预算",
        "eu5ab_regional_development__finance__budget_desc": "全国所有模板、普通建筑与原产扩建共享同一个年度建造预算池。",
        "eu5ab_regional_development__finance__market_name": "市场价格范围",
        "eu5ab_regional_development__finance__market_desc": "设置商品物价偏离基础价格时的供需判定参考百分比。",
        "eu5ab_regional_development__automation__safety_name": "建造安全规则",
        "eu5ab_regional_development__automation__safety_desc": "设置特殊建筑、上游补建、劳动力与投入品保护等共享安全限制。",
        "eu5ab_regional_development__automation__rgo_name": "原产扩建",
        "eu5ab_regional_development__automation__workforce_name": "劳动力预测",
        "eu5ab_regional_development__automation__workforce_desc": "配置测算未来劳动力供给时允许的最长等待期限。",
        "eu5ab_regional_development__automation__ranking_name": "建造决策策略",
        "eu5ab_regional_development__automation__ranking_desc": "选择普通建筑的决策排序策略，并设置各类建造行为的先后执行顺序。",
        "eu5ab_regional_development__candidate_ranking_mode_name": "普通建筑决策策略",
        "eu5ab_regional_development__candidate_backfill_enabled_name": "尝试备选项目",
        "eu5ab_regional_development__candidate_backfill_enabled_desc": "当前类型的优先项目均未开工时，继续尝试排名靠后的项目。每轮每个地点额外尝试最多 2 项（供需规划）或 5 项（预测利润择优），各类普通建筑共用次数；该地点有普通建筑开工后停止。读档不恢复次数，建造条件仍须满足。默认关闭，下轮检查生效，开启可能增加耗时。",
        "eu5ab_regional_development__candidate_ranking_mode_desc": "选择普通建筑满足收益和建造条件后的优先顺序。食物紧急保障和「自动建造顺序」优先；原产按短缺、价格、就业及战略需求另行判断。",
        "eu5ab_regional_development__candidate_ranking_mode_option_1_name": "供需规划",
        "eu5ab_regional_development__candidate_ranking_mode_option_1_desc": "根据市场短缺、战略需求、配方效率、本地原料、商品价格和劳动力风险综合安排建造，侧重产业链完整与长期供需稳定。",
        "eu5ab_regional_development__candidate_ranking_mode_option_2_name": "预测利润择优",
        "eu5ab_regional_development__candidate_ranking_mode_option_2_desc": "先筛选符合模板和安全条件的项目，再按照预测月净收益择优建造，风车计入资源增产收益，粮仓计入减少腐损的食物估值。当不同建筑的预计收益相近时，模板中设置的建筑优先级将作为辅助参考。",
        "eu5ab_regional_development__automation__candidate_priority_name": "自动建造顺序",
        "eu5ab_regional_development__automation__candidate_priority_desc": "拖动四类建造行为自定义先后顺序（建筑升级、普通扩建、原产扩建、新建建筑）。系统会优先安排完当前类型中所有可开工的项目，再进入下一类型；同类型项目不能开工时会继续寻找同类替代。食物紧急时，产粮项目优先处理但仍遵照此顺序。",
        "eu5ab_regional_development__candidate_priority_name": "自动建造顺序",
        "eu5ab_regional_development__candidate_priority_desc": "拖动调整建筑升级、普通扩建、原产扩建和新建建筑的先后顺序。",
        "eu5ab_regional_development__candidate_priority_item_column_name": "建造类型",
        "eu5ab_regional_development__candidate_priority_i1_name": "自动升级建筑",
        "eu5ab_regional_development__candidate_priority_i1_desc": "将现有旧式建筑替换为当前已解锁的最新一代升级建筑。",
        "eu5ab_regional_development__candidate_priority_i2_name": "自动扩建现有建筑",
        "eu5ab_regional_development__candidate_priority_i2_desc": "为当地已有的普通建筑提升等级，不包含升级替换和原产扩建。",
        "eu5ab_regional_development__candidate_priority_i3_name": "自动扩建资源采集点",
        "eu5ab_regional_development__candidate_priority_i3_desc": "扩建当地原产资源采集点，现有岗位须满员，并满足价格、年度预算、国库储备等规则。",
        "eu5ab_regional_development__candidate_priority_i4_name": "自动新建建筑",
        "eu5ab_regional_development__candidate_priority_i4_desc": "在当地从零新建尚不存在的普通建筑。",
        "eu5ab_regional_development__enabled_name": "启用自动建造",
        "eu5ab_regional_development__enabled_desc": "总开关。关闭后保留模板设置和应用地点，但停止每月自动建造检查。",
        "eu5ab_regional_development__monthly_build_hard_cap_name": "额外同时建造上限",
        "eu5ab_regional_development__monthly_build_hard_cap_desc": "设置本 Mod 允许额外同时在建的民用工程上限（总上限为该数值 + 1）。设为 0 表示全国最多同时开工 1 个项目，设为 599 表示最多 600 个。仅统计本 Mod 开工的项目；玩家手动建造、道路修筑及其他 Mod 不受此限制。",
        "eu5ab_regional_development__budget_mode_name": "年度预算模式",
        "eu5ab_regional_development__budget_mode_desc": "选择固定金额，或按月总收入的 4、6、8 倍确定年度额度。新一年首次检查时重新计算，年内调整设置会保留已有支出。",
        "eu5ab_regional_development__budget_mode_option_1_name": "固定年度预算",
        "eu5ab_regional_development__budget_mode_option_2_name": "月总收入 ×4",
        "eu5ab_regional_development__budget_mode_option_3_name": "月总收入 ×6（推荐）",
        "eu5ab_regional_development__budget_mode_option_4_name": "月总收入 ×8",
        "eu5ab_regional_development__economic_metric_name": "自动建造收益指标",
        "eu5ab_regional_development__economic_metric_desc": "普通生产建筑须满足所选条件：预计月收入或月利润为正，或年化回报率达到 5%。这是当前预测，实际收益可能变化。一般公共设施不受限制。风车须有正的增产净收益，回报率模式下还须达到 5%；粮仓以减少腐损为建造理由时，始终须达到 5%。原产另按自身规则判断。",
        "eu5ab_regional_development__economic_metric_option_1_name": "@income! 收入",
        "eu5ab_regional_development__economic_metric_option_1_desc": "仅当游戏预测该建筑开工后月收入大于 0 时才允许开工。",
        "eu5ab_regional_development__economic_metric_option_2_name": "@wealth! 利润",
        "eu5ab_regional_development__economic_metric_option_2_desc": "仅当游戏预测该建筑扣除维护与原料成本后的月利润大于 0 时才允许开工。",
        "eu5ab_regional_development__economic_metric_option_3_name": "@efficiency! 收入回报率",
        "eu5ab_regional_development__economic_metric_option_3_desc": "预计月收入至少达到建造成本的 5%÷12，才符合此项要求。这里比较的是收入，没有扣除运营成本。",
        "eu5ab_regional_development__economic_metric_option_4_name": "@efficiency! 利润回报率",
        "eu5ab_regional_development__economic_metric_option_4_desc": "预计月利润至少达到建造成本的 5%÷12，才符合此项要求。实际利润可能随经营情况变化。",
        "eu5ab_regional_development__emergency_food_exhaustion_override_name": "预计食物耗尽：优先建造，不检查收益",
        "eu5ab_regional_development__emergency_food_exhaustion_override_desc": "当所属市场预测食物储备将耗尽时，系统优先调度产粮项目，并对普通食物建筑豁免收益门槛检查。产粮项目内部仍按「自动建造顺序」执行，且预算、国库储备、劳动力及原版建造条件等安全限制依然有效。",
        "eu5ab_regional_development__emergency_food_stockpile_override_name": "食物储备不高于 25%：优先建造，不检查收益",
        "eu5ab_regional_development__emergency_food_stockpile_override_desc": "当所属市场的食物储备降至25%及以下时，系统优先调度产粮项目，并对普通食物建筑豁免收益门槛检查。其他建造与财政安全限制依然有效。",
        "eu5ab_regional_development__emergency_construction_goods_override_name": "建造所需商品供应低于 65%：不检查收益",
        "eu5ab_regional_development__emergency_construction_goods_override_desc": "当木材、石料与工具等核心建材的市场供应率低于65%时，生产对应建材的建筑豁免收益门槛检查，防止建材昂贵阻碍经济建设。建造类型顺序与财政安全限制依然有效。",
        "eu5ab_regional_development__emergency_wartime_military_override_name": "战时军需供应低于 65%：不检查收益",
        "eu5ab_regional_development__emergency_wartime_military_override_desc": "当国家处于战争状态且军需品的市场供应率低于65%时，生产对应军需装备的建筑豁免收益门槛检查，确保战时物资供应。",
        "eu5ab_regional_development__emergency_strategic_input_override_name": "战略生产缺料：不检查上游收益",
        "eu5ab_regional_development__emergency_strategic_input_override_desc": "当某原料的市场供应率低于65%，且同一市场中存在消耗该原料、处于开启状态并缺少投入品的本国食物、核心建材或军需建筑时，生产该原料的上游建筑豁免收益门槛检查。不要求下游已经停工，也不要求其缺少的投入品恰好是该原料；其他建造规则仍然有效。",
        "eu5ab_regional_development__fixed_annual_budget_name": "固定年度预算",
        "eu5ab_regional_development__fixed_annual_budget_desc": "仅在固定预算模式下生效；全国所有模板共享该年度总额度。",
        "eu5ab_regional_development__fixed_annual_budget_format": "[CMMV('eu5ab_regional_development__fixed_annual_budget')]@gold!",
        "eu5ab_regional_development__min_cash_reserve_name": "最低国库储备",
        "eu5ab_regional_development__min_cash_reserve_desc": "按预计费用检查本项及其他已安排工程，余额不足以保留储备金时暂不开工。原产最终费用可能与估算不同。",
        "eu5ab_regional_development__min_cash_reserve_format": "[CMMV('eu5ab_regional_development__min_cash_reserve')]@gold!",
        "eu5ab_regional_development__price_min_name": "最低价格百分比",
        "eu5ab_regional_development__price_min_format": "[CMMV('eu5ab_regional_development__price_min')]%",
        "eu5ab_regional_development__price_max_name": "高价参考百分比",
        "eu5ab_regional_development__price_max_format": "[CMMV('eu5ab_regional_development__price_max')]%",
        "eu5ab_regional_development__allow_special_buildings_name": "允许特殊建筑",
        "eu5ab_regional_development__allow_special_buildings_desc": "开启后，模板允许建造符合条件的特殊建筑（如宗教、文化或特定奇观类建筑）。关闭后自动建造将忽略所有特殊建筑。",
        "eu5ab_regional_development__fill_market_shortages_when_idle_name": "有空余建造名额时补建市场紧缺产业",
        "eu5ab_regional_development__fill_market_shortages_when_idle_desc": "常规工程安排后，利用空余名额，在本轮已检查、属于同一市场的本国地点补充紧缺产业。会考虑已安排工程的原料需求和尚未实现的增产。风味模板可补建原先未规划的产业；禁用项和自定义优先级 0 仍有效，其他建造条件也须满足。",
        "eu5ab_regional_development__auto_build_input_sources_name": "短缺时自动补建上游",
        "eu5ab_regional_development__auto_build_input_sources_desc": "开启后，系统会独立检查原料市场缺口，并尝试补建模板允许的上游产业；已满员但仍缺料的下游建筑也能触发补建。",
        "eu5ab_regional_development__pause_low_workforce_name": "劳动力不足时暂停",
        "eu5ab_regional_development__stop_input_shortage_name": "关键投入品短缺时停止",
        "eu5ab_regional_development__stop_input_shortage_desc": "开启后，所需关键工业原料的市场供应至少须达到需求的 75%，才允许安排相关工程。",
        "eu5ab_regional_development__allow_rgo_name": "允许扩建原产",
        "eu5ab_regional_development__allow_rgo_desc": "开启后，允许所有模板在满足条件时自动扩建当地原产资源采集点。",
        "eu5ab_regional_development__native_input_priority_name": "本地原料优先级",
        "eu5ab_regional_development__native_input_priority_desc": "调节本地原料在「供需规划」中的加分权重（默认 5）。数值越高，能直接消耗本省所产原料的制造类建筑优先级越高；设为 0 则不额外加分。",
        "eu5ab_regional_development__performance_preset_name": "性能预设",
        "eu5ab_regional_development__performance_preset_desc": "性能预设会自动联动下方高级参数。手动修改高级设置后会自动切换为「自定义」，并于下一次月度检查开始生效。",
        "eu5ab_regional_development__performance_preset_option_1_name": "保守",
        "eu5ab_regional_development__performance_preset_option_1_desc": "每天最多检查 10 个地点，每轮最多新增 30 个项目；规划候选数为 5、利润候选数为 15（分别仅用于对应策略），找到足够候选后停止检查剩余地点。",
        "eu5ab_regional_development__performance_preset_option_2_name": "平衡",
        "eu5ab_regional_development__performance_preset_option_2_desc": "每天最多检查 20 个地点，每轮最多新增 50 个项目；规划候选数为 4、利润候选数为 12（分别仅用于对应策略），找到足够候选后停止检查剩余地点。",
        "eu5ab_regional_development__performance_preset_option_3_name": "效率优先",
        "eu5ab_regional_development__performance_preset_option_3_desc": "适合已应用模板地点较多的国家。每天最多检查 30 个地点，不限制本轮新增数；规划候选数为 3、利润候选数为 10（分别仅用于对应策略），找到足够候选后停止检查剩余地点。",
        "eu5ab_regional_development__performance_preset_option_4_name": "自定义",
        "eu5ab_regional_development__performance_preset_option_4_desc": "使用当前自定义配置的高级性能参数。",
        "eu5ab_regional_development__performance_throughput_warning_summary_name": "大量地点应用模板可能降低游戏性能。",
        "eu5ab_regional_development__performance_throughput_warning_summary_desc": "效率优先模式下每天检查最多 30 个地点且不限每轮新增数。国家领地规模极大时可能会延长月结耗时。",
        "eu5ab_regional_development__performance_throughput_warning_action_name": "「供需规划」耗时过长：降低「规划候选数」。",
        "eu5ab_regional_development__performance_throughput_warning_action_desc": "仅在供需规划时显示。降低「规划候选数」可以减少每个地点、每种普通建造类别接受后续检查的项目数量。",
        "eu5ab_regional_development__performance_throughput_warning_planning_consequence_name": "后果：备选项目减少，可能漏掉后续可行项目。",
        "eu5ab_regional_development__performance_throughput_warning_planning_consequence_desc": "系统会按规划评分依次检查项目。降低候选数上限后，若前几个高分项目未满足开工条件，可供备选的后续项目数量将减少，可能导致原本可建的项目未被检查到。",
        "eu5ab_regional_development__performance_throughput_warning_profit_action_name": "「预测利润择优」耗时过长：降低「利润候选数」。",
        "eu5ab_regional_development__performance_throughput_warning_profit_action_desc": "仅在「预测利润择优」时显示。降低「利润候选数」，减少后续逐项检查的备选项目。",
        "eu5ab_regional_development__performance_throughput_warning_profit_consequence_name": "备选减少，优先项目无法开工时可能没有其他选择。",
        "eu5ab_regional_development__performance_throughput_warning_profit_consequence_desc": "按预计利润和建造偏好排序后保留备选。减少数量后，优先项目无法开工时，可继续尝试的项目也会减少。",
        "eu5ab_regional_development__performance_throughput_warning_common_action_name": "也可降低每天检查地点和每轮新增。",
        "eu5ab_regional_development__performance_throughput_warning_common_action_desc": "降低每天检查地点数，可将检查分散到更多天；降低每轮最多新增，可减少单轮安排的工程。设为 0 时不限制每轮新增数。",
        "eu5ab_regional_development__parallel_location_scan_name": "分开处理各地点",
        "eu5ab_regional_development__parallel_location_scan_desc": "开启后分开检查各地点，减少停顿；关闭后集中处理当天的地点。两者的建造优先级、预算和顺序相同。",
        "eu5ab_regional_development__daily_location_task_limit_name": "每天检查地点上限",
        "eu5ab_regional_development__daily_location_task_limit_desc": "每天最多详细检查的地点数。数值越低，每天处理更少，但检查全国需要更多天。",
        "eu5ab_regional_development__max_additions_per_run_name": "每轮最多新增",
        "eu5ab_regional_development__max_additions_per_run_desc": "单次月度检查允许开工的最大项目数（设为 0 表示不设上限）。",
        "eu5ab_regional_development__candidates_per_location_name": "规划候选数",
        "eu5ab_regional_development__candidates_per_location_desc": "仅在「供需规划」策略下生效。每个地点的每个普通建造类别分别按规划评分保留用于后续检查的候选项目数。保留越多越不容易遗漏备选项目，但会增加性能开销。",
        "eu5ab_regional_development__actual_profit_candidates_per_location_name": "利润候选数",
        "eu5ab_regional_development__actual_profit_candidates_per_location_desc": "仅用于「预测利润择优」。每个地点、每类普通建造按预计利润和建造偏好排序，保留 3—30 个备选项目。保留越多，优先项目无法开工时的选择越多，但后续检查可能更慢。",
        "eu5ab_regional_development__early_stop_when_candidates_sufficient_name": "候选足够后停止检查",
        "eu5ab_regional_development__early_stop_when_candidates_sufficient_desc": "备选项目达到本轮可新增工程数的 2 倍后，停止详细检查其他地点。可新增数受空余名额和「每轮最多新增」限制；后者设为 0 时只取消每轮新增限制。备选仍须满足开工条件。",
        "eu5ab_diagnostics_cmm_hint": "全国共享规则请在社区模组框架的「模组设置」中配置；「建造报告」展示最近一次月度建造结果。",
        "EU5AB_CMM_NUMERIC_INCREASE_MAX": "[SelectLocalization(Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__monthly_build_hard_cap'), Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__governor_migration_threshold_percent'), EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__naval_governor_migration_threshold_percent'))), 'eu5ab_cmm_shift_increase_10', SelectLocalization(Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__fixed_annual_budget'), EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__min_cash_reserve')), 'eu5ab_cmm_shift_increase_1000', 'eu5ab_cmm_shift_increase_max'))]",
        "EU5AB_CMM_NUMERIC_DECREASE_MIN": "[SelectLocalization(Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__monthly_build_hard_cap'), Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__governor_migration_threshold_percent'), EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__naval_governor_migration_threshold_percent'))), 'eu5ab_cmm_shift_decrease_10', SelectLocalization(Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__fixed_annual_budget'), EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__min_cash_reserve')), 'eu5ab_cmm_shift_decrease_1000', 'eu5ab_cmm_shift_decrease_min'))]",
        "eu5ab_cmm_shift_increase_10": "增加 10",
        "eu5ab_cmm_shift_decrease_10": "减少 10",
        "eu5ab_cmm_shift_increase_1000": "增加 1000",
        "eu5ab_cmm_shift_decrease_1000": "减少 1000",
        "eu5ab_cmm_shift_increase_max": "设为最大值",
        "eu5ab_cmm_shift_decrease_min": "设为最小值",
    }
    values.update(rgo_localization.CMM_ZH)
    rgo_localization.add_horizon_step_tooltips(values, english=False)
    values.update(GOVERNOR_SIMP_CHINESE_LOCALIZATION)
    return [f' {key}: "{value}"' for key, value in values.items()]


def _cmm_english_localization_values() -> dict[str, str]:
    values = {
        **rgo_localization.CMM_EN,
        "eu5ab_regional_development_name": "Advanced Auto Build",
        "eu5ab_regional_development_desc": "Set the budget, construction requirements, decision strategy, and performance options shared by every template. Each template keeps its own enabled state, coverage, and building priorities.",
        "eu5ab_regional_development__general_name": "Master Controls & Limits",
        "eu5ab_regional_development__finance_name": "Finance & Market",
        "eu5ab_regional_development__automation_name": "Safety & Ranking",
        "eu5ab_regional_development__performance_name": "Performance Optimization",
        "eu5ab_regional_development__performance__preset_name": "Performance Preset",
        "eu5ab_regional_development__performance__preset_desc": "Performance presets adjust the options below. Changing an advanced setting switches to Custom, and the new values take effect with the next monthly check.",
        "eu5ab_regional_development__performance__advanced_name": "Advanced Settings",
        "eu5ab_regional_development__performance__advanced_desc": "Adjust daily location checks, new projects per round, and the number of alternatives. Checking more projects may take longer.",
        "eu5ab_regional_development__general__limits_name": "Master Controls & Concurrent Limit",
        "eu5ab_regional_development__general__limits_desc": "Control whether the Mod runs and how many civil projects it may manage at once.",
        "eu5ab_regional_development__general__returns_name": "Return Rules & Emergency Overrides",
        "eu5ab_regional_development__general__returns_desc": "Choose return requirements for ordinary production buildings and whether shortages of food, construction goods, military goods, or strategic inputs may relax them.",
        "eu5ab_regional_development__finance__budget_name": "Shared Annual Budget",
        "eu5ab_regional_development__finance__budget_desc": "All built-in templates, custom templates, buildings, and RGOs share one national annual budget pool.",
        "eu5ab_regional_development__finance__market_name": "Market Price Range",
        "eu5ab_regional_development__finance__market_desc": "Set shared minimum and high-price reference percentages relative to default prices.",
        "eu5ab_regional_development__automation__safety_name": "Construction Safety Rules",
        "eu5ab_regional_development__automation__safety_desc": "Shared handling for special buildings, upstream construction, workforce, and input shortages.",
        "eu5ab_regional_development__automation__rgo_name": "RGO Expansion",
        "eu5ab_regional_development__automation__workforce_name": "Workforce Forecast",
        "eu5ab_regional_development__automation__workforce_desc": "Configure the maximum forecast horizon when projecting future workforce supply.",
        "eu5ab_regional_development__automation__ranking_name": "Construction Decision Strategy",
        "eu5ab_regional_development__automation__ranking_desc": "Choose the decision strategy for ordinary buildings, set the order of upgrades, expansions, RGOs, and new buildings, and control local-input influence on supply-demand planning.",
        "eu5ab_regional_development__candidate_ranking_mode_name": "Ordinary-Building Strategy",
        "eu5ab_regional_development__candidate_backfill_enabled_name": "Try Other Projects",
        "eu5ab_regional_development__candidate_backfill_enabled_desc": "If leading projects in the current type cannot start, try lower-ranked alternatives. Each location gets up to 2 extra attempts per round for Supply-Demand Planning or 5 for Predicted Profit Selection, shared across ordinary types. Stop once an ordinary building starts there. Loading a save does not restore attempts. All requirements still apply. Off by default; takes effect next round and may increase checking time.",
        "eu5ab_regional_development__candidate_ranking_mode_desc": "Choose how eligible ordinary buildings are prioritized. Food safeguards and Automated Build Order take precedence. RGOs are assessed separately by shortages, prices, employment, and strategic needs.",
        "eu5ab_regional_development__candidate_ranking_mode_option_1_name": "Supply-Demand",
        "eu5ab_regional_development__candidate_ranking_mode_option_1_desc": "Arrange construction using market shortages, strategic demand, recipe efficiency, local inputs, commodity prices, and workforce risk, emphasizing complete production chains and stable long-term supply and demand.",
        "eu5ab_regional_development__candidate_ranking_mode_option_2_name": "Predicted Profit",
        "eu5ab_regional_development__candidate_ranking_mode_option_2_desc": "Filter candidates through template and safety rules, then prioritize construction by predicted monthly net benefit, including windmill resource gains and the food value saved by granaries. When predicted benefits are close, building priorities configured in the template serve as a secondary reference.",
        "eu5ab_regional_development__automation__candidate_priority_name": "Automated Build Order",
        "eu5ab_regional_development__automation__candidate_priority_desc": "Drag the four types into the order you want. The Mod tries every project it can start in the current type before moving to the next; if one project cannot start, it looks for another of the same type. During a food emergency, food projects are handled first but still follow this order.",
        "eu5ab_regional_development__candidate_priority_name": "Automated Build Order",
        "eu5ab_regional_development__candidate_priority_desc": "Drag to order building upgrades, ordinary expansions, RGO expansions, and new ordinary buildings.",
        "eu5ab_regional_development__candidate_priority_item_column_name": "Build Type",
        "eu5ab_regional_development__candidate_priority_i1_name": "Upgrade Buildings",
        "eu5ab_regional_development__candidate_priority_i1_desc": "Replace an obsolete building with the newest currently unlocked tier in its upgrade chain.",
        "eu5ab_regional_development__candidate_priority_i2_name": "Expand Existing Buildings",
        "eu5ab_regional_development__candidate_priority_i2_desc": "Add a level to an existing ordinary building, excluding replacements and RGOs.",
        "eu5ab_regional_development__candidate_priority_i3_name": "Expand Resource Locations",
        "eu5ab_regional_development__candidate_priority_i3_desc": "Expands local RGOs, requiring full existing employment and satisfying price, annual budget and treasury reserve rules.",
        "eu5ab_regional_development__candidate_priority_i4_name": "Build New Buildings",
        "eu5ab_regional_development__candidate_priority_i4_desc": "Construct an ordinary building from zero where it does not yet exist.",
        "eu5ab_regional_development__enabled_name": "Enable Automated Construction",
        "eu5ab_regional_development__enabled_desc": "Turn monthly automated construction checks on or off. Templates and location assignments are kept when disabled.",
        "eu5ab_regional_development__monthly_build_hard_cap_name": "Extra Concurrent Projects",
        "eu5ab_regional_development__monthly_build_hard_cap_desc": "How many civil projects this Mod may run at once beyond the base slot. 0 means 1 project in total and 599 means 600; manual construction, roads, and projects from other Mods do not use this limit.",
        "eu5ab_regional_development__budget_mode_name": "Annual Budget Mode",
        "eu5ab_regional_development__budget_mode_desc": "Choose a fixed amount or 4, 6, or 8 times total monthly income. Recalculate at the first check of a new year; changing settings preserves spending already recorded.",
        "eu5ab_regional_development__budget_mode_option_1_name": "Fixed Annual Budget",
        "eu5ab_regional_development__budget_mode_option_2_name": "Monthly Income ×4",
        "eu5ab_regional_development__budget_mode_option_3_name": "Monthly Income ×6 (Recommended)",
        "eu5ab_regional_development__budget_mode_option_4_name": "Monthly Income ×8",
        "eu5ab_regional_development__economic_metric_name": "Ordinary Building Economic Threshold",
        "eu5ab_regional_development__economic_metric_desc": "Ordinary production buildings must meet the selected condition: positive predicted monthly income or profit, or a 5% annualized return. Actual returns may change. Ordinary public infrastructure is exempt. Windmills need positive net gains from extra output and a 5% annual return in return-rate modes. Granaries built for spoilage savings always need 5%. RGOs follow separate rules.",
        "eu5ab_regional_development__economic_metric_option_1_name": "@income! Monthly Income > 0",
        "eu5ab_regional_development__economic_metric_option_1_desc": "Start an ordinary production building only when the game predicts positive monthly income.",
        "eu5ab_regional_development__economic_metric_option_2_name": "@wealth! Monthly Profit > 0",
        "eu5ab_regional_development__economic_metric_option_2_desc": "Start an ordinary production building only when the game predicts positive total monthly profit.",
        "eu5ab_regional_development__economic_metric_option_3_name": "@efficiency! Annualized Income Return ≥ 5%",
        "eu5ab_regional_development__economic_metric_option_3_desc": "Predicted monthly income must be at least 5% of construction cost divided by 12. This compares income before operating costs.",
        "eu5ab_regional_development__economic_metric_option_4_name": "@efficiency! Annualized Profit Return ≥ 5%",
        "eu5ab_regional_development__economic_metric_option_4_desc": "Predicted monthly profit must be at least 5% of construction cost divided by 12. Actual profit may change with operating conditions.",
        "eu5ab_regional_development__emergency_food_exhaustion_override_name": "Food Expected to Run Out: Build First, Ignore Return",
        "eu5ab_regional_development__emergency_food_exhaustion_override_desc": "When the market is expected to run out of food, handle food projects first and do not require ordinary food buildings to meet the selected return. Food projects still follow Automated Build Order, and all budget, treasury, workforce, input, material, and game construction rules remain in force.",
        "eu5ab_regional_development__emergency_food_stockpile_override_name": "Food at or below 25%: Build First, Ignore Return",
        "eu5ab_regional_development__emergency_food_stockpile_override_desc": "While market food is at or below 25%, handle food projects first and do not require ordinary food buildings to meet the selected return. Food projects still follow Automated Build Order, and every other construction rule remains in force.",
        "eu5ab_regional_development__emergency_construction_goods_override_name": "Construction Supply below 65%: Ignore Return",
        "eu5ab_regional_development__emergency_construction_goods_override_desc": "When a core construction good has less than 65% of the supply it needs, buildings that produce it do not have to meet the selected return. Every other construction rule still applies.",
        "eu5ab_regional_development__emergency_wartime_military_override_name": "Wartime Military Supply below 65%: Ignore Return",
        "eu5ab_regional_development__emergency_wartime_military_override_desc": "While at war, if a military good has less than 65% of the supply it needs, buildings that produce it do not have to meet the selected return. Every other construction rule still applies.",
        "eu5ab_regional_development__emergency_strategic_input_override_name": "Strategic Production Lacks Inputs: Ignore Upstream Return",
        "eu5ab_regional_development__emergency_strategic_input_override_desc": "When an upstream good's market supply is below 65% of demand and the same market contains an open domestic food, core construction, or military building that consumes this good and lacks inputs, producers of this good are exempt from the selected return threshold. The downstream building need not have stopped production, and its missing input need not be this particular good. Every other construction rule still applies.",
        "eu5ab_regional_development__fixed_annual_budget_name": "Fixed Annual Budget",
        "eu5ab_regional_development__fixed_annual_budget_desc": "Used only in fixed mode; every template shares this amount.",
        "eu5ab_regional_development__fixed_annual_budget_format": "[CMMV('eu5ab_regional_development__fixed_annual_budget')]@gold!",
        "eu5ab_regional_development__min_cash_reserve_name": "Minimum Treasury Reserve",
        "eu5ab_regional_development__min_cash_reserve_desc": "Keep this reserve after estimated costs for all planned projects. Actual RGO costs may differ.",
        "eu5ab_regional_development__min_cash_reserve_format": "[CMMV('eu5ab_regional_development__min_cash_reserve')]@gold!",
        "eu5ab_regional_development__price_min_name": "Minimum Price Percentage",
        "eu5ab_regional_development__price_min_format": "[CMMV('eu5ab_regional_development__price_min')]%",
        "eu5ab_regional_development__price_max_name": "High-Price Reference Percentage",
        "eu5ab_regional_development__price_max_format": "[CMMV('eu5ab_regional_development__price_max')]%",
        "eu5ab_regional_development__allow_special_buildings_name": "Allow Special Buildings",
        "eu5ab_regional_development__allow_special_buildings_desc": "Allow automated construction to consider special buildings; the game's own construction requirements still apply.",
        "eu5ab_regional_development__fill_market_shortages_when_idle_name": "Fill Market Shortages with Free Construction Slots",
        "eu5ab_regional_development__fill_market_shortages_when_idle_desc": "After regular projects, use free construction space to address shortages at owned locations checked this round in the same market. Account for planned projects' input needs and output gains not yet realized. Built-in presets may add unplanned industries; bans, custom priority 0, and other construction requirements still apply.",
        "eu5ab_regional_development__auto_build_input_sources_name": "Build Upstream Sources on Shortage",
        "eu5ab_regional_development__auto_build_input_sources_desc": "Independently check input-market shortages and build allowed upstream sources, including when downstream factories are fully staffed but short of inputs.",
        "eu5ab_regional_development__pause_low_workforce_name": "Pause on Low Workforce",
        "eu5ab_regional_development__stop_input_shortage_name": "Stop on Critical Input Shortage",
        "eu5ab_regional_development__stop_input_shortage_desc": "Required key industrial inputs must have market supply covering at least 75% of demand before related construction can be arranged.",
        "eu5ab_regional_development__allow_rgo_name": "Allow RGO Expansion",
        "eu5ab_regional_development__allow_rgo_desc": "Allow every template to consider expanding resource locations.",
        "eu5ab_regional_development__native_input_priority_name": "Local Input Priority",
        "eu5ab_regional_development__native_input_priority_desc": "0–10; higher values make buildings that can use raw materials from the same province more likely to be built first.",
        "eu5ab_regional_development__performance_preset_name": "Performance Preset",
        "eu5ab_regional_development__performance_preset_desc": "A preset synchronizes the advanced settings below. Custom retains their current values.",
        "eu5ab_regional_development__performance_preset_option_1_name": "Conservative",
        "eu5ab_regional_development__performance_preset_option_1_desc": "Check up to 10 locations per day and start at most 30 projects per run. Planning Candidates is 5 and Profit Candidates is 15, each used only by its matching strategy. Stop checking remaining locations once enough candidates are available.",
        "eu5ab_regional_development__performance_preset_option_2_name": "Balanced",
        "eu5ab_regional_development__performance_preset_option_2_desc": "Check up to 20 locations per day and start at most 50 projects per run. Planning Candidates is 4 and Profit Candidates is 12, each used only by its matching strategy. Stop checking remaining locations once enough candidates are available.",
        "eu5ab_regional_development__performance_preset_option_3_name": "Maximum Throughput",
        "eu5ab_regional_development__performance_preset_option_3_desc": "Best for countries with many assigned locations. Check up to 30 locations per day with no per-run project limit. Planning Candidates is 3 and Profit Candidates is 10, each used only by its matching strategy. Stop checking remaining locations once enough candidates are available.",
        "eu5ab_regional_development__performance_preset_option_4_name": "Custom",
        "eu5ab_regional_development__performance_preset_option_4_desc": "Use the current advanced settings.",
        "eu5ab_regional_development__performance_throughput_warning_summary_name": "Many templated locations can reduce game performance.",
        "eu5ab_regional_development__performance_throughput_warning_summary_desc": "Under Maximum Throughput, up to 30 locations are checked daily with no per-run limit. Very large realms may experience longer monthly tick times.",
        "eu5ab_regional_development__performance_throughput_warning_action_name": "\"Supply-Demand\" taking too long: lower \"Planning Candidates\".",
        "eu5ab_regional_development__performance_throughput_warning_action_desc": "Shown only with Supply-Demand Planning. Lowering Planning Candidates reduces the projects per location and ordinary build category sent to later checks.",
        "eu5ab_regional_development__performance_throughput_warning_planning_consequence_name": "Consequence: fewer alternate candidates may miss viable later projects.",
        "eu5ab_regional_development__performance_throughput_warning_planning_consequence_desc": "Projects are checked in descending planning-score order. Lowering candidate limits leaves fewer alternate candidates when top projects fail prerequisites, potentially skipping viable later projects.",
        "eu5ab_regional_development__performance_throughput_warning_profit_action_name": "\"Predicted Profit\" taking too long: lower \"Profit Candidates\".",
        "eu5ab_regional_development__performance_throughput_warning_profit_action_desc": "Shown only with Predicted Profit Selection. Lower Profit Candidates to reduce the alternatives checked later.",
        "eu5ab_regional_development__performance_throughput_warning_profit_consequence_name": "Fewer alternatives may leave no other choice if leading projects cannot start.",
        "eu5ab_regional_development__performance_throughput_warning_profit_consequence_desc": "Alternatives are retained after ranking by predicted profit and building preferences. Keeping fewer leaves fewer choices when leading projects cannot start.",
        "eu5ab_regional_development__performance_throughput_warning_common_action_name": "Also lower daily locations or additions per run.",
        "eu5ab_regional_development__performance_throughput_warning_common_action_desc": "Fewer daily locations spread checks across more days. Fewer additions per round reduce projects arranged at once. Setting additions to 0 removes the per-round limit.",
        "eu5ab_regional_development__parallel_location_scan_name": "Process Locations Separately",
        "eu5ab_regional_development__parallel_location_scan_desc": "Check locations separately to reduce pauses, or together each day when off. Priorities, budget, and build order stay the same.",
        "eu5ab_regional_development__daily_location_task_limit_name": "Locations Checked per Day",
        "eu5ab_regional_development__daily_location_task_limit_desc": "Maximum locations checked in detail each day. Lower values mean less daily work but more days to cover the country.",
        "eu5ab_regional_development__max_additions_per_run_name": "Maximum Additions per Run",
        "eu5ab_regional_development__max_additions_per_run_desc": "Limit the maximum projects started in one run, from 0 to 600. Zero means unlimited.",
        "eu5ab_regional_development__candidates_per_location_name": "Planning Candidates per Location",
        "eu5ab_regional_development__candidates_per_location_desc": "Active only under 'Supply-Demand Planning'. Sets the number of candidate projects retained by planning score for each location and ordinary build category before subsequent requirement checks (3–30). Retaining more candidates reduces the risk of missing viable alternatives, but increases performance overhead.",
        "eu5ab_regional_development__actual_profit_candidates_per_location_name": "Profit Candidates per Location",
        "eu5ab_regional_development__actual_profit_candidates_per_location_desc": "For Predicted Profit Selection only. Keep 3–30 alternatives per location and ordinary construction type, ranked by predicted profit and building preferences. More alternatives offer more choices when leading projects cannot start, but may slow later checks.",
        "eu5ab_regional_development__early_stop_when_candidates_sufficient_name": "Stop Checking When Enough Candidates Are Found",
        "eu5ab_regional_development__early_stop_when_candidates_sufficient_desc": "Stop detailed checks of other locations once alternatives reach twice the projects that can be added this round. Free space and Maximum Additions per Run set this number; 0 removes only the per-round cap. Construction requirements still apply.",
        "eu5ab_diagnostics_cmm_hint": "Change shared rules in Community Mod Framework's Mod Settings. Construction Report shows the latest automated construction result.",
        "EU5AB_CMM_NUMERIC_INCREASE_MAX": "[SelectLocalization(Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__monthly_build_hard_cap'), Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__governor_migration_threshold_percent'), EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__naval_governor_migration_threshold_percent'))), 'eu5ab_cmm_shift_increase_10', SelectLocalization(Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__fixed_annual_budget'), EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__min_cash_reserve')), 'eu5ab_cmm_shift_increase_1000', 'eu5ab_cmm_shift_increase_max'))]",
        "EU5AB_CMM_NUMERIC_DECREASE_MIN": "[SelectLocalization(Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__monthly_build_hard_cap'), Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__governor_migration_threshold_percent'), EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__naval_governor_migration_threshold_percent'))), 'eu5ab_cmm_shift_decrease_10', SelectLocalization(Or(EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__fixed_annual_budget'), EqualTo_string(Scope.GetFlagName, 'eu5ab_regional_development__min_cash_reserve')), 'eu5ab_cmm_shift_decrease_1000', 'eu5ab_cmm_shift_decrease_min'))]",
        "eu5ab_cmm_shift_increase_10": "Increase by 10",
        "eu5ab_cmm_shift_decrease_10": "Decrease by 10",
        "eu5ab_cmm_shift_increase_1000": "Increase by 1000",
        "eu5ab_cmm_shift_decrease_1000": "Decrease by 1000",
        "eu5ab_cmm_shift_increase_max": "Set to Maximum",
        "eu5ab_cmm_shift_decrease_min": "Set to Minimum",
    }
    rgo_localization.add_horizon_step_tooltips(values, english=True)
    return values


def render_localization(policies: list[Policy], catalog: BuildingCatalog) -> str:
    lines = [
        "l_simp_chinese:",
        ' eu5ab_window_title: "区域发展与自动建造"',
        ' eu5ab_template_editor_title: "编辑区域发展模板"',
        ' eu5ab_template_buildings_window_title: "建筑规则"',
        ' eu5ab_template_rules_window_title: "建造报告"',
        ' eu5ab_template_rename_window_title: "重命名模板"',
        ' eu5ab_template_scope_window_title: "当前应用范围"',
        ' eu5ab_automation_buildings_tab: "自动建造"',
        ' eu5ab_automation_buildings_tab_desc: "管理模板、建筑优先级与应用范围。全国共享的预算、收益与安全规则请在 CMF「模组设置」中配置。"',
        ' eu5ab_action_bar_name: "高级自动建造"',
        ' eu5ab_action_bar_tooltip: "打开区域发展模板面板，配置建筑优先级与应用范围，并查看最近一次月度建造报告。"',
        ' eu5ab_action_bar_icon: "@production_panel!"',
        ' eu5ab_action_bar_color: "gold"',
        ' eu5ab_template_overview_title: "区域发展模板"',
        ' eu5ab_presets_tab: "风味模板"',
        ' eu5ab_presets_tab_tooltip: "为不同发展目标提供固定的建筑优先级，可复制为自定义模板后修改。"',
        ' eu5ab_custom_tab: "自定义模板"',
        ' eu5ab_custom_tab_tooltip: "自行设置建筑优先级和应用范围。"',
        ' eu5ab_sidebar_title: "模板"',
        ' eu5ab_detail_title: "规则详情"',
        ' eu5ab_new_template_plus_button: "+ 新建模板"',
        ' eu5ab_new_blank_template_button: "+ 空白模板"',
        ' eu5ab_new_recommended_template_button: "+ 推荐模板"',
        ' eu5ab_custom_empty_detail: "请从左侧列表选择一个自定义模板，或新建空白模板、按推荐优先级新建模板。"',
        ' eu5ab_template_intro_title: "模板编辑"',
        ' eu5ab_automation_buildings_intro: "自定义模板可自由设置建筑优先级并应用到地点。风味模板的建筑优先级固定，如需修改，可复制为自定义模板。"',
        ' eu5ab_player_templates_button: "自定义模板"',
        ' eu5ab_copy_preset_to_player_button: "复制为自定义模板"',
        ' eu5ab_delete_template_button: "删除模板"',
        ' eu5ab_delete_template_tooltip: "删除此自定义模板。确认后，使用它的地点也会取消应用。"',
        ' eu5ab_delete_template_confirm_prompt: "确定删除当前模板？"',
        ' eu5ab_delete_template_confirm_button: "确认删除"',
        ' eu5ab_delete_template_confirm_tooltip: "永久删除此模板，并取消所有地点对它的应用。此操作不可撤销。"',
        ' eu5ab_delete_template_cancel_button: "取消"',
        ' eu5ab_delete_template_cancel_tooltip: "取消删除并返回模板操作。"',
        ' eu5ab_pause_template_button: "暂停模板"',
        ' eu5ab_resume_template_button: "恢复模板"',
        ' eu5ab_template_paused_badge: "（已暂停）"',
        ' eu5ab_pause_template_tooltip: "暂停或恢复此模板。暂停会保留建筑优先级和应用地点，但不再为这些地点安排自动建造。"',
        ' eu5ab_select_template_tooltip: "选择此模板并查看规则详情。"',
        ' eu5ab_preset_readonly_desc: "风味模板的建筑优先级固定，可单独暂停、恢复或应用到地点。如需修改优先级，可复制为自定义模板。共享规则在 CMF「模组设置」中调整。"',
        ' eu5ab_template_name_pencil_hint: "模板名"',
        ' eu5ab_template_name_click_hint: "点击模板名可重命名"',
        ' eu5ab_template_name_click_tooltip: "输入当前模板的新名称。"',
        ' eu5ab_template_rename_desc: "为当前模板输入新名称，最多 42 个字符。"',
        ' eu5ab_template_rename_input: "模板名"',
        ' eu5ab_template_rename_accept: "确认"',
        ' eu5ab_template_rename_cancel: "取消"',
        ' eu5ab_target_location_title: "目标地点"',
        ' eu5ab_target_location_desc: "选择地点以执行清除策略或取消省份联动；分配模板请直接点击对应模板卡片上的「应用」按钮。"',
        ' eu5ab_template_editor_desc: "配置此模板的建筑优先级与应用范围。所有修改均会立即自动保存并生效。"',
        ' eu5ab_template_auto_save_hint: "修改会立即保存，关闭窗口即可返回。"',
        ' eu5ab_rules_tab_finance: "财政与建造"',
        ' eu5ab_rules_tab_automation: "劳动力与建造偏好"',
        ' eu5ab_rules_tab_diagnostics: "建造报告"',
        ' eu5ab_template_editor_sections_title: "模板设置"',
        ' eu5ab_template_editor_sections_desc: "每个模板单独保存启停状态、应用范围与建筑优先级。最近一次月度建造结果可在「建造报告」中查看。"',
        ' eu5ab_open_buildings_editor_button: "建筑规则"',
        ' eu5ab_open_rules_editor_button: "建造报告"',
        ' eu5ab_edit_template_button: "编辑"',
        ' eu5ab_copy_to_slot_button: "复制到这里"',
        ' eu5ab_policy_section_title: "模板规则"',
        ' eu5ab_cash_section_title: "储备金"',
        ' eu5ab_cash_short_desc: "国库必须保留的最低余额。"',
        ' eu5ab_cash_label: "储备金"',
        ' eu5ab_active_cash_amount: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_min_cash_reserve\').GetValue|0] 金币"',
        ' eu5ab_cash_help: "开工前按预计费用检查国库余额，同时计入其他已安排工程；预计余额低于储备金时暂不开工。\\n例如国库有 1050 金币、储备金设为 1000 时，不会安排预计花费 100 金币的工程。原产最终费用可能与估算不同。年度预算也须有余额。"',
        ' eu5ab_budget_section_title: "年度建造预算"',
        ' eu5ab_budget_short_desc: "选择固定金额，或按月总收入确定年度额度。"',
        ' eu5ab_budget_mode_fixed: "固定预算"',
        ' eu5ab_budget_mode_income: "收入联动"',
        ' eu5ab_budget_multiplier_4: "×4 保守"',
        ' eu5ab_budget_multiplier_6: "×6 推荐"',
        ' eu5ab_budget_multiplier_8: "×8 积极"',
        ' eu5ab_budget_effective_label: "本年预算额度"',
        ' eu5ab_budget_effective_amount: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_budget_limit\').GetValue|0] 金币"',
        ' eu5ab_budget_label: "年度预算"',
        ' eu5ab_annual_budget_amount: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_fixed_annual_budget\').GetValue|0] 金币/年"',
        ' eu5ab_budget_cash_comparison: "年度预算决定本年计划投入多少，储备金决定国库需要留多少。最后一项可超出预算余额，但仍须通过储备金检查。"',
        ' eu5ab_budget_reset_note: "新一年首次检查时重置预算，成功开工后按实际支出扣减。年内调整预算不会清除已有支出。"',
        ' eu5ab_budget_help: "普通建筑和原产扩建共用年度预算，可设为固定金额或月总收入的 4、6、8 倍。新一年首次检查时重置；年内调整预算不会清除已有支出。\\n成功开工后按实际支出扣减，未开工不扣预算。最后一项工程可超出剩余额度，之后停止新增；国库储备要求仍须满足。"',
        ' eu5ab_quota_section_title: "本 Mod 同时建造上限"',
        ' eu5ab_quota_short_desc: "设置在基础 1 项之外，本 Mod 允许同时在建的民用工程数量上限。"',
        ' eu5ab_hard_cap_label: "额外同时建造数"',
        ' eu5ab_hard_cap_amount: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_monthly_build_hard_cap\').GetValue|0] 项（总上限为此数值 + 1）"',
        ' eu5ab_quota_help: "设置基础 1 项之外的额外名额：0 表示最多同时建造 1 项，599 表示 600 项。普通建筑和原产共用，只统计本 Mod 尚未完工的工程；手动建造、道路及其他 Mod 不计入。每轮只补充空余名额。同一地点有空位时可安排多项工程，本轮结束后等待 3 个月再安排新工程。"',
        ' eu5ab_template_cash_value: "储备金：[GetPlayer.MakeScope.GetVariable(\'eu5ab_tpl_min_cash_reserve\').GetValue|0Y]@gold!"',
        ' eu5ab_step_dec_10k: "-10k"',
        ' eu5ab_step_dec_1k: "-1k"',
        ' eu5ab_step_inc_1k: "+1k"',
        ' eu5ab_step_inc_10k: "+10k"',
        ' eu5ab_step_dec_10: "-10"',
        ' eu5ab_step_dec_1: "-1"',
        ' eu5ab_step_inc_1: "+1"',
        ' eu5ab_step_inc_10: "+10"',
        ' eu5ab_step_dec_5: "-5"',
        ' eu5ab_step_inc_5: "+5"',
        ' eu5ab_step_dec_100: "-100"',
        ' eu5ab_step_inc_100: "+100"',
        ' eu5ab_building_rules_title: "建筑规则"',
        ' eu5ab_building_rules_desc: "第一行按就业阶层筛选，第二行按解锁时代分组。建筑优先级范围为 0.0–10.0；0 表示完全禁止建造。特殊页仅展示当前国家在至少一个自有地点满足建造前置的特殊建筑。"',
        ' eu5ab_allow_button: "允许"',
        ' eu5ab_ban_button: "禁止"',
        ' eu5ab_priority_decrease: "−"',
        ' eu5ab_priority_increase: "+"',
        ' eu5ab_priority_decrease_default_tt: "优先级减少 0.1"',
        ' eu5ab_priority_decrease_ctrl_tt: "Ctrl：优先级减少 0.5"',
        ' eu5ab_priority_decrease_shift_tt: "Shift：优先级减少 1.0"',
        ' eu5ab_priority_increase_default_tt: "优先级增加 0.1"',
        ' eu5ab_priority_increase_ctrl_tt: "Ctrl：优先级增加 0.5"',
        ' eu5ab_priority_increase_shift_tt: "Shift：优先级增加 1.0"',
        ' eu5ab_priority_scale_hint: "0 = 禁止"',
        ' eu5ab_clear_visible_priorities_button: "当前列表全部清零"',
        ' eu5ab_clear_visible_priorities_tooltip: "立即将当前就业阶层与时代筛选下所有可见建筑的优先级重置为 0，并自动保存模板。未在当前视图中显示的建筑不受影响。"',
        ' eu5ab_priority_low: "低"',
        ' eu5ab_priority_medium: "中"',
        ' eu5ab_priority_high: "高"',
        ' eu5ab_priority_high_icon: "↑"',
        ' eu5ab_priority_medium_icon: "–"',
        ' eu5ab_priority_low_icon: "↓"',
        ' eu5ab_ban_icon: "×"',
        ' eu5ab_filter_all: "全部"',
        ' eu5ab_filter_rural: "乡村"',
        ' eu5ab_filter_laborers: "劳工"',
        ' eu5ab_filter_burghers: "市民"',
        ' eu5ab_filter_soldiers: "军事"',
        ' eu5ab_filter_special: "特殊"',
        ' eu5ab_age_all: "全部时代"',
        ' eu5ab_building_age_1: "传统时代"',
        ' eu5ab_building_age_2: "文艺复兴时代"',
        ' eu5ab_building_age_3: "大发现时代"',
        ' eu5ab_building_age_4: "宗教改革时代"',
        ' eu5ab_building_age_5: "专制时代"',
        ' eu5ab_building_age_6: "革命时代"',
        ' eu5ab_status_enabled: "#G 已启用#!"',
        ' eu5ab_status_disabled: "#L 已禁用#!"',
        ' eu5ab_status_currently_available: "#G 当前可用#!"',
        ' eu5ab_operating_rules_title: "自动建造规则"',
        ' eu5ab_operating_rules_short_desc: "设置特殊建筑、上游补建和投入品短缺规则。"',
        ' eu5ab_operating_rules_help: "特殊建筑仍须满足游戏的解锁与建造条件。\\n原料短缺时，可补建模板允许的相关产业；已有工厂即使满员，也可能因缺料需要补建。\\n开启原料保护后，所需关键工业原料的供应须达到需求的 75%。已有建筑优先按当前生产方式判断，无法确定时按可用方式估算；不同方式的原料需求分别计算，不会自动切换生产方式。"',
        ' eu5ab_rgo_section_title: "原产"',
        ' eu5ab_rgo_allow: "允许此模板扩建原产"',
        ' eu5ab_toggle_special_buildings: "允许特殊建筑"',
        ' eu5ab_toggle_auto_build_input_sources: "缺少投入品时自动补建上游"',
        ' eu5ab_toggle_pause_low_workforce: "劳动力不足时暂停建造"',
        ' eu5ab_ranking_mode_section_title: "建造决策策略"',
        ' eu5ab_town_rights_preference_desc: "城市特权偏好与鼓励产业各自最多增加 500 规划分，独立叠加。鼓励产业仅支持本国扶持地区内直接产出匹配的建筑；按所选配方的产出基价占比计分，不沿产业链传递。可与本地原料分叠加；预测利润模式仅用于初筛。原产扩建仅沿用城市特权加分。仍须满足全部开工条件。"',
        ' eu5ab_ranking_mode_current_label: "当前模式"',
        ' eu5ab_ranking_mode_composite_value: "#G 供需规划#!"',
        ' eu5ab_ranking_mode_actual_profit_value: "#G 预测利润择优#!"',
        ' eu5ab_ranking_mode_common_desc: "两种策略均仅考虑已解锁、符合建造条件且模板优先级大于 0 的建筑，并必须满足收益门槛、年度预算、国库储备、原料与劳动力等安全限制。食物紧急状态与「自动建造顺序」层级始终优先。"',
        ' eu5ab_ranking_mode_composite_desc: "根据市场短缺、战略需求、配方效率、本地原料、商品价格和劳动力风险综合安排建造，侧重产业链完整与长期供需稳定。"',
        ' eu5ab_ranking_mode_actual_profit_desc: "先筛选符合模板和安全条件的项目，再按照预测月净收益择优建造，风车计入资源增产收益，粮仓计入减少腐损的食物估值。当不同建筑的预计收益相近时，模板中设置的建筑优先级将作为辅助参考。"',
        ' eu5ab_ranking_mode_actual_profit_scope_desc: "每个地点、每类普通建造保留 3—30 个备选，数量由设置决定。食物紧急保障和「自动建造顺序」优先，开工前仍须满足收益与建造条件。原产按短缺、价格、就业和战略需求另行判断。"',
        ' eu5ab_ranking_mode_help: "可在 CMF 模组设置中切换：\\n·「供需规划」：根据市场供需缺口、战略需求、产业链配套、本地原料与劳动力风险综合评分，侧重宏观调控与长期产业平稳。\\n·「预测利润择优」：在通过模板与安全检查的前提下，优先选择预测月净收益最高的建筑（含风车增产与粮仓减损估值）；当预计收益相近时，模板优先级将作为辅助参考加分。"',
        ' eu5ab_workforce_section_title: "劳动力"',
        ' eu5ab_pause_workforce_short_desc: "控制劳动力不足是否会直接阻止建造。"',
        ' eu5ab_job_fill_deadline_label: "劳动力预测期限"',
        ' eu5ab_job_fill_deadline_amount: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_job_fill_deadline_months\').GetValue|0] 个月"',
        ' eu5ab_job_fill_deadline_value: "劳动力预测期限：[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_job_fill_deadline_months\').GetValue|0] 个月"',
        ' eu5ab_job_fill_deadline_desc: "设定评估劳动力时最长向后预测的月数（可在 0—240 个月间调整）。设为 0 时仅计算当前可用劳动力，不计入未来晋升人口。是否因缺工阻止开工由「劳动力不足时暂停建造」决定：开启时，预计劳动力不足将禁止开工；关闭时，缺工仅降低建造优先级。"',
        ' eu5ab_deadline_0: "0月"',
        ' eu5ab_deadline_3: "3月"',
        ' eu5ab_deadline_6: "6月"',
        ' eu5ab_deadline_12: "12月"',
        ' eu5ab_toggle_stop_input_shortage: "关键投入品短缺时停止建造"',
        ' eu5ab_prediction_status_label: "劳动力估算方式"',
        ' eu5ab_status_promotion_forecast: "#G 按所选期限预测晋升#!"',
        ' eu5ab_status_conservative_fallback: "#L 按当前劳动力保守估算#!"',
        ' eu5ab_prediction_promotion_short_desc: "将当前可用劳动力与设定期限内预计能晋升至目标阶层的人口合并计算；最长可预测 240 个月。"',
        ' eu5ab_prediction_unavailable_short_desc: "无法可靠预测未来劳动力时，只按当前可用人数保守判断。"',
        ' eu5ab_native_input_section_title: "本地原料偏好"',
        ' eu5ab_native_input_short_desc: "提高使用本省原料的生产建筑排序。"',
        ' eu5ab_native_input_priority_label: "本地原料优先级"',
        ' eu5ab_native_input_priority_amount: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_native_input_priority\').GetValue|0] / 10"',
        ' eu5ab_native_input_priority_value: "本地原料优先级：[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_native_input_priority\').GetValue|0] / 10"',
        ' eu5ab_native_input_priority_desc: "「本地」指建筑所在的省份。系统会查看建筑配方需要哪些原料，并检查同一省份是否存在能够产出这些原料的原产；原料在配方中占比越高，匹配后提供的排序加分越多。0 表示不考虑本地原料，5 为默认，10 表示最看重本地原料。这个设置只改变备选建筑的排序；即使设为 10，系统也可能因为商品紧缺、收益、劳动力或其他条件选择别的建筑。这里只判断省内是否存在对应原产，不比较原产等级或实际产量。投入品短缺、市场接入度不足或控制力偏低会降低加分；原产本身不会获得这项加分。按可用生产方式估算，不会自动切换生产方式。"',
        ' eu5ab_price_section_title: "价格区间"',
        ' eu5ab_price_short_desc: "按市场价格筛选和排序生产建筑。"',
        ' eu5ab_price_min_label: "最低价格"',
        ' eu5ab_price_max_label: "高价参考"',
        ' eu5ab_active_price_min_amount: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_price_min\').GetValue|0]%"',
        ' eu5ab_active_price_max_amount: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_price_max\').GetValue|0]%"',
        ' eu5ab_price_section_desc: "以基础价为 100%。低价降低优先级，全部产出均不高于最低价时暂停；多产出按产量和基础价综合判断。高价加分至参考值封顶，不会因价格过高停建。无商品产出的设施不受限，食物紧急保障按设置生效。"',
        ' eu5ab_active_cash_value: "储备金：[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_min_cash_reserve\').GetValue|0Y]@gold!"',
        ' eu5ab_active_price_min_value: "最低价格：[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_price_min\').GetValue|0Y]%"',
        ' eu5ab_active_price_max_value: "高价参考：[GetPlayer.MakeScope.GetVariable(\'eu5ab_global_price_max\').GetValue|0Y]%"',
        ' eu5ab_price_min_value: "最低价格：[GetPlayer.MakeScope.GetVariable(\'eu5ab_tpl_price_min\').GetValue|0Y]%"',
        ' eu5ab_price_max_value: "高价参考：[GetPlayer.MakeScope.GetVariable(\'eu5ab_tpl_price_max\').GetValue|0Y]%"',
        ' eu5ab_prediction_section_title: "自动建造规则"',
        ' eu5ab_prediction_diagnostics_title: "劳动力估算与建造状态"',
        ' eu5ab_prediction_section_body: "按你设置的「自动建造顺序」安排升级、普通扩建、原产扩建和新建；优先尝试当前类型的可行项目。\\n食物紧急保障开启且符合条件时，先安排相关产粮项目，并按设置放宽收益和价格等限制。建材、战时军需或战略原料短缺，也可按设置放宽相关项目的收益要求。\\n预算、国库储备及适用的原料、劳动力、建筑容量和游戏建造条件仍须满足。普通建筑只考虑已解锁的最新一代；升级只计新增岗位。"',
        ' eu5ab_diagnostics_title: "自动建造状态"',
        ' eu5ab_diagnostics_snapshot_note: "设置会立即保存；报告随检查和开工进度更新，完成后保留结果。"',
        ' eu5ab_diagnostics_snapshot_help: "报告随检查和开工进度更新，结果保留到下一轮。每月从 23 日起陆续安排工程，数量和支出可能逐步变化；检查未完成时，部分结果仍需等待。"',
        ' eu5ab_diag_overview_title: "本月建造概况"',
        ' eu5ab_diag_quota_title: "本轮建造名额"',
        ' eu5ab_diag_result_title: "本轮新增项目"',
        ' eu5ab_diag_failure_title: "上次检查未通过的项目"',
        ' eu5ab_diag_candidates_title: "优先考虑的三个项目"',
        ' eu5ab_diag_label_status: "自动建造状态"',
        ' eu5ab_diag_label_last_run: "最近检查日期"',
        ' eu5ab_diag_label_covered: "已应用模板地点"',
        ' eu5ab_diag_label_preliminary: "当前可安排地点"',
        ' eu5ab_diag_label_deep_scored: "已逐项检查地点"',
        ' eu5ab_diag_label_legal: "劳动力足够的候选"',
        ' eu5ab_diag_label_staged_candidates: "进入最终检查的候选"',
        ' eu5ab_diag_label_engine_probes: "成本与收益检查次数"',
        ' eu5ab_diag_label_queue_throttle: "同时建造空位"',
        ' eu5ab_diag_label_engine_queue: "本轮建造进度"',
        ' eu5ab_diag_label_queue_recoveries: "自动重置次数"',
        ' eu5ab_diag_label_prediction_mode: "劳动力预测模式"',
        ' eu5ab_diag_last_run_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_run_year\').GetValue|0] 年 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_run_month\').GetValue|0] 月 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_run_day\').GetValue|0] 日"',
        ' eu5ab_diag_covered_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_covered_locations\').GetValue|0] 个"',
        ' eu5ab_diag_preliminary_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_preliminary_passed\').GetValue|0] 个"',
        ' eu5ab_diag_deep_scored_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_deep_scored\').GetValue|0] 个"',
        ' eu5ab_diag_legal_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_legal_candidates\').GetValue|0] 个"',
        ' eu5ab_diag_staged_candidates_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_staged_candidates\').GetValue|0] 个"',
        ' eu5ab_diag_engine_probes_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_engine_probes\').GetValue|0] 次"',
        ' eu5ab_diag_state_not_run: "#L 等待下月检查#!"',
        ' eu5ab_diag_state_success: "#G 成功执行#!"',
        ' eu5ab_diag_state_complete_no_build: "#Y 检查完成，未新增项目#!"',
        ' eu5ab_diag_state_scan_stalled: "#Y 本轮检查未完成，将在下轮重新检查。#!"',
        ' eu5ab_diag_label_capacity_waiting: "待查建筑容量的地点"',
        ' eu5ab_diag_label_capacity_unavailable: "建筑容量不足或不明"',
        ' eu5ab_diag_label_capacity_expired: "上月未完成的容量检查"',
        ' eu5ab_diag_label_capacity_reason: "最近容量限制原因"',
        ' eu5ab_diag_capacity_reason_1: "已用建筑容量不明"',
        ' eu5ab_diag_capacity_reason_2: "无可用建筑容量上限"',
        ' eu5ab_diag_capacity_reason_3: "建筑容量占用已达到停建标准"',
        " eu5ab_diag_capacity_waiting_value: \"[GetPlayer.MakeScope.GetVariable('eu5ab_diag_capacity_waiting').GetValue|0]\"",
        " eu5ab_diag_capacity_unavailable_value: \"[GetPlayer.MakeScope.GetVariable('eu5ab_diag_capacity_unavailable').GetValue|0]\"",
        " eu5ab_diag_capacity_expired_value: \"[GetPlayer.MakeScope.GetVariable('eu5ab_diag_capacity_expired').GetValue|0]\"",
        ' eu5ab_diag_state_ready: "月度检查已完成。"',
        ' eu5ab_diag_state_no_coverage: "#R 没有应用本 Mod 模板的地点#!"',
        ' eu5ab_diag_state_hard_cap: "#Y 已达到本 Mod 同时建造上限#!"',
        ' eu5ab_diag_state_no_preliminary: "#R 目前没有可安排的地点#!"',
        ' eu5ab_diag_state_queue_throttled: "本 Mod 当前仍在建造的项目已经占满设置的同时建造名额。"',
        ' eu5ab_status_queue_throttled: "#Y 已满#!"',
        ' eu5ab_status_not_throttled: "#G 尚有空位#!"',
        ' eu5ab_status_engine_queue_prepared: "#L 正在整理可建项目#!"',
        ' eu5ab_status_engine_queue_validating: "#Y 正在检查成本、收益与条件#!"',
        ' eu5ab_status_engine_queue_executing: "#Y 正在尝试开工#!"',
        ' eu5ab_status_engine_queue_confirmed: "#G 项目已确认开工#!"',
        ' eu5ab_status_engine_queue_recovered: "#R 上次检查未完成，已自动重置#!"',
        ' eu5ab_status_engine_queue_profit_ranking: "#Y 正在按预测月利润择优#!"',
        ' eu5ab_diag_queue_recoveries_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_queue_recoveries\').GetValue|0] 次"',
        ' eu5ab_status_waiting_next_month: "#L 等待下月检查#!"',
        ' eu5ab_status_prediction_realtime: "#G 按所选期限预测晋升#!"',
        ' eu5ab_status_prediction_proxy: "#Y 保守劳动力估算#!"',
        ' eu5ab_diag_no_build_this_run: "#Y 本月没有新项目开工#!"',
        ' eu5ab_diag_candidates_not_scanned_full: "同时建造名额已满，本轮没有继续寻找新项目。释放名额后再检查。"',
        ' eu5ab_diag_no_ranked_candidates: "上次检查没有找到可建项目。下方会列出主要原因。"',
        ' eu5ab_diag_quota_short_desc: "显示本 Mod 当前在建、同时建造上限以及本轮最多可新增名额。"',
        ' eu5ab_diag_label_capacity_summary: "自动建造名额"',
        ' eu5ab_diag_label_rgo_used: "其中原产"',
        ' eu5ab_diag_capacity_summary_value: "在建 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_active_mod_projects\').GetValue|0] / 上限 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_base_quota\').GetValue|0] 项 · 本轮最多新增 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_final_quota\').GetValue|0] 项"',
        ' eu5ab_diag_label_previous_month_added: "上轮确认开工"',
        ' eu5ab_diag_previous_month_added_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_previous_month_added\').GetValue|0] 项"',
        ' eu5ab_diag_label_expected_this_run: "本轮最多新增"',
        ' eu5ab_diag_expected_this_run_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_final_quota\').GetValue|0] 项"',
        ' eu5ab_diag_rgo_used_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_quota_used\').GetValue|0] 项"',
        ' eu5ab_diag_label_result: "开工结果"',
        ' eu5ab_diag_label_actual_cost: "建造成本"',
        ' eu5ab_diag_label_actual_income: "游戏预测月收入"',
        ' eu5ab_diag_label_actual_profit: "预测月净收益"',
        ' eu5ab_diag_label_emergency_overrides: "因战略需要放宽收益要求"',
        ' eu5ab_diag_actual_cost_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_actual_cost\').GetValue|2]"',
        ' eu5ab_diag_actual_income_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_actual_income\').GetValue|2]"',
        ' eu5ab_diag_actual_profit_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_actual_profit\').GetValue|2]"',
        ' eu5ab_diag_emergency_overrides_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_emergency_overrides_used\').GetValue|0] 项"',
        ' eu5ab_diag_result_rgo_value: "#G 成功#! · [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_build_location\').GetLocation.GetName] · 原产 · 扩建"',
        ' eu5ab_diag_result_new_value: "#G 成功#! · [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_build_location\').GetLocation.GetName] · [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_building\').GetBuildingType.GetName] · 新建"',
        ' eu5ab_diag_result_upgrade_value: "#G 成功#! · [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_build_location\').GetLocation.GetName] · [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_building\').GetBuildingType.GetName] · 升级"',
        ' eu5ab_diag_result_expansion_value: "#G 成功#! · [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_build_location\').GetLocation.GetName] · [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_last_building\').GetBuildingType.GetName] · 扩建"',
        ' eu5ab_diag_result_help: "食物紧急保障开启且满足条件时，优先安排产粮项目；其他工程按「自动建造顺序」安排，同类项目无法开工时会尝试备选。\\n原产按短缺、价格、就业及战略需求判断，仍须满足游戏建造条件。\\n成功开工后才扣减预算并占用名额；本轮安排结束后，开工地点等待 3 个月再安排新工程。"',
        ' eu5ab_diag_rgo_title: "原产候选检查"',
        ' eu5ab_diag_rgo_short_desc: "每个地点只记录一个结果；未通过时计入最先遇到的原因。"',
        ' eu5ab_diag_rgo_help: "显示上次原产扩建检查的结果。已有岗位须满员；「考虑人口」会预测新增岗位的劳动力，「宽松」不预测。价格、尚未实现的增产和当前缺工会影响优先级。增产按本国同市场、同商品汇总；信息不全时只显示已知部分。达到增产限额只暂停新增，已有工程继续。"',
        ' eu5ab_diag_rgo_checked_label: "检查的原产地点"',
        ' eu5ab_diag_rgo_eligible_label: "符合全部条件"',
        ' eu5ab_diag_rgo_fail_capacity_label: "已达到原产上限"',
        ' eu5ab_diag_rgo_fail_location_label: "建造名额已满或仍需等待"',
        ' eu5ab_diag_rgo_fail_disabled_label: "原产扩建已关闭"',
        ' eu5ab_diag_rgo_fail_finance_label: "国库、预算或本轮名额不足"',
        ' eu5ab_diag_rgo_fail_workforce_label: "新增一级的劳动力预测不足"',
        ' eu5ab_diag_rgo_checked_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_checked\').GetValue|0]"',
        ' eu5ab_diag_rgo_eligible_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_eligible\').GetValue|0]"',
        ' eu5ab_diag_rgo_fail_capacity_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_fail_capacity\').GetValue|0]"',
        ' eu5ab_diag_rgo_fail_location_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_fail_location\').GetValue|0]"',
        ' eu5ab_diag_rgo_fail_disabled_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_fail_disabled\').GetValue|0]"',
        ' eu5ab_diag_rgo_fail_finance_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_fail_finance\').GetValue|0]"',
        ' eu5ab_diag_rgo_fail_utilization_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_fail_utilization\').GetValue|0]"',
        ' eu5ab_diag_rgo_fail_workforce_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_fail_workforce\').GetValue|0]"',
        ' eu5ab_diag_rgo_fail_market_need_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_rgo_fail_market_need\').GetValue|0]"',
        ' eu5ab_diag_failure_short_desc: "只显示上一次月度检查，不会累计到下个月。"',
        ' eu5ab_diag_failure_help: "这里仅显示上一次月度检查的结果，不会跨月累计。系统会分别统计劳动力不足、生产投入不足、产出过剩、预算或国库储备不足、收益未达到设置、建造所需商品过贵或本轮计划消耗过多，以及不满足游戏自身建造条件的项目。"',
        ' eu5ab_diag_fail_workforce_label: "劳动力不足"',
        ' eu5ab_diag_fail_building_capacity_label: "满员建筑等级已达上限的 110%"',
        ' eu5ab_diag_fail_capacity_unavailable_label: "建筑容量不明或无可用上限"',
        ' eu5ab_diag_fail_building_capacity_value: "[GetPlayer.MakeScope.ScriptValue(\'eu5ab_diag_fail_building_capacity_ui\')|0]"',
        ' eu5ab_diag_fail_capacity_unavailable_value: "[GetPlayer.MakeScope.ScriptValue(\'eu5ab_diag_fail_capacity_unavailable_ui\')|0]"',
        ' eu5ab_diag_fail_inputs_label: "投入品不足"',
        ' eu5ab_diag_fail_pending_output_label: "待释放产能满额或数据不足"',
        ' eu5ab_diag_fail_oversupply_label: "产出过剩"',
        ' eu5ab_diag_fail_irrigation_need_label: "灌溉没有食物或人口容量需求"',
        ' eu5ab_diag_fail_granary_need_label: "粮仓储备需求或减损回报不足"',
        ' eu5ab_diag_fail_storage_pending_label: "同省已有在建或待开工粮仓"',
        ' eu5ab_diag_fail_windmill_need_label: "风车增产需求或净收益不足"',
        ' eu5ab_diag_fail_budget_label: "预算不足"',
        ' eu5ab_diag_fail_cash_label: "储备金不足"',
        ' eu5ab_diag_fail_engine_economics_label: "收益未达到设置"',
        ' eu5ab_diag_fail_construction_materials_label: "建造所需商品压力过高"',
        ' eu5ab_diag_fail_vanilla_label: "不满足游戏建造条件"',
        ' eu5ab_diag_fail_no_legal_label: "没有符合条件的建筑"',
        ' eu5ab_diag_fail_workforce_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_workforce\').GetValue|0]"',
        ' eu5ab_diag_fail_inputs_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_inputs\').GetValue|0]"',
        ' eu5ab_diag_fail_pending_output_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_pending_output\').GetValue|0]"',
        ' eu5ab_diag_fail_oversupply_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_oversupply\').GetValue|0]"',
        ' eu5ab_diag_fail_irrigation_need_value: "[GetPlayer.MakeScope.ScriptValue(\'eu5ab_diag_fail_irrigation_need_ui\')|0]"',
        ' eu5ab_diag_fail_granary_need_value: "[GetPlayer.MakeScope.ScriptValue(\'eu5ab_diag_fail_granary_need_ui\')|0]"',
        ' eu5ab_diag_fail_storage_pending_value: "[GetPlayer.MakeScope.ScriptValue(\'eu5ab_diag_fail_storage_pending_ui\')|0]"',
        ' eu5ab_diag_fail_windmill_need_value: "[GetPlayer.MakeScope.ScriptValue(\'eu5ab_diag_fail_windmill_need_ui\')|0]"',
        ' eu5ab_diag_fail_budget_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_budget\').GetValue|0]"',
        ' eu5ab_diag_fail_cash_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_cash\').GetValue|0]"',
        ' eu5ab_diag_fail_engine_economics_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_engine_economics\').GetValue|0]"',
        ' eu5ab_diag_fail_construction_materials_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_construction_materials\').GetValue|0]"',
        ' eu5ab_diag_fail_vanilla_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_vanilla\').GetValue|0]"',
        ' eu5ab_diag_fail_no_legal_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_fail_no_legal\').GetValue|0]"',
        ' eu5ab_diag_candidates_help: "按食物紧急情况、建造顺序和当前策略列出优先项目，同一地点可出现多项。列入备选不代表一定开工，仍须满足预算、劳动力、原料、产能及其他建造条件。"',
        ' eu5ab_diag_candidate_1_title: "项目 1"',
        ' eu5ab_diag_candidate_2_title: "项目 2"',
        ' eu5ab_diag_candidate_3_title: "项目 3"',
        ' eu5ab_diag_label_location: "地点"',
        ' eu5ab_diag_label_building: "建筑或原产"',
        ' eu5ab_diag_label_scores: "排序评分"',
        ' eu5ab_diag_label_workforce: "劳动力（人数）"',
        ' eu5ab_diag_label_unselected_reason: "项目状态"',
        ' eu5ab_diag_candidate_1_location_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_location\').GetLocation.GetName]"',
        ' eu5ab_diag_candidate_2_location_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_location\').GetLocation.GetName]"',
        ' eu5ab_diag_candidate_3_location_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_location\').GetLocation.GetName]"',
        ' eu5ab_diag_candidate_1_building_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_building\').GetBuildingType.GetName]"',
        ' eu5ab_diag_candidate_2_building_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_building\').GetBuildingType.GetName]"',
        ' eu5ab_diag_candidate_3_building_value: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_building\').GetBuildingType.GetName]"',
        ' eu5ab_diag_candidate_rgo_value: "原产扩建"',
        ' eu5ab_diag_candidate_empty_value: "#weak 没有更多候选项目#!"',
        ' eu5ab_diag_candidate_1_scores_value: "总分 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_score\').GetValue|0] · 需求 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_need\').GetValue|0] · 经济 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_economic\').GetValue|1]"',
        ' eu5ab_diag_candidate_2_scores_value: "总分 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_score\').GetValue|0] · 需求 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_need\').GetValue|0] · 经济 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_economic\').GetValue|1]"',
        ' eu5ab_diag_candidate_3_scores_value: "总分 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_score\').GetValue|0] · 需求 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_need\').GetValue|0] · 经济 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_economic\').GetValue|1]"',
        ' eu5ab_diag_candidate_1_rgo_scores_value: "排序总分 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_score\').GetValue|0] · 地点需求 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_need\').GetValue|0]"',
        ' eu5ab_diag_candidate_2_rgo_scores_value: "排序总分 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_score\').GetValue|0] · 地点需求 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_need\').GetValue|0]"',
        ' eu5ab_diag_candidate_3_rgo_scores_value: "排序总分 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_score\').GetValue|0] · 地点需求 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_need\').GetValue|0]"',
        ' eu5ab_diag_candidate_1_workforce_value: "需要 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_labor_jobs\').GetValue|0] · 当前 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_labor_current\').GetValue|0] · 期限内 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_1_labor_projected\').GetValue|0]"',
        ' eu5ab_diag_candidate_2_workforce_value: "需要 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_labor_jobs\').GetValue|0] · 当前 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_labor_current\').GetValue|0] · 期限内 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_2_labor_projected\').GetValue|0]"',
        ' eu5ab_diag_candidate_3_workforce_value: "需要 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_labor_jobs\').GetValue|0] · 当前 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_labor_current\').GetValue|0] · 期限内 [GetPlayer.MakeScope.GetVariable(\'eu5ab_diag_top_3_labor_projected\').GetValue|0]"',
        ' eu5ab_candidate_reason_ranked: "已列入备选，开工前仍须检查预算、劳动力、产能和其他建造条件。"',
        ' eu5ab_candidate_reason_waiting: "正在确认生产情况，请稍候。"',
        ' eu5ab_candidate_reason_approved: "已满足开工要求，正在确认是否成功开工。"',
        ' eu5ab_candidate_reason_confirmed: "已开始施工。"',
        ' eu5ab_candidate_reason_rejected: "未满足开工要求，本次未开工。"',
        ' eu5ab_candidate_reason_workforce: "劳动力不足"',
        ' eu5ab_candidate_reason_inputs: "关键投入品不足"',
        ' eu5ab_candidate_reason_pending_output: "待释放产能满额或数据不足"',
        ' eu5ab_candidate_reason_oversupply: "产出已过剩"',
        ' eu5ab_candidate_reason_budget: "年度建造预算不足"',
        ' eu5ab_candidate_reason_cash: "储备金不足"',
        ' eu5ab_candidate_reason_vanilla: "不满足游戏自身的建造条件"',
        ' eu5ab_candidate_reason_no_legal: "没有符合条件的建筑"',
        ' eu5ab_control_section_title: "地点控制"',
        ' eu5ab_policy_status_body: "这里会显示当前模板、年度策略预算、储备金、特殊建筑设置、下一个项目、暂停原因和劳动力估算结果。"',
        ' eu5ab_automation_policy_footer_text: "选择要应用或清除本 Mod 设置的地点。控制入口已移至社区模组框架的「高级自动建造」。"',
        ' eu5ab_automation_panel_tooltip: "通过社区模组框架的「高级自动建造」入口打开模板与自动建造控制项。"',
        ' eu5ab_special_on_button: "特殊开"',
        ' eu5ab_special_off_button: "特殊关"',
        ' eu5ab_special_toggle_tooltip: "控制该地点是否允许自动建造或升级特殊建筑。"',
        ' eu5ab_cash_0_button: "留0"',
        ' eu5ab_cash_500_button: "留500"',
        ' eu5ab_cash_1000_button: "留1000"',
        ' eu5ab_cash_2000_button: "留2000"',
        ' eu5ab_decouple_button: "停止跟随省份模板"',
        ' eu5ab_decouple_tooltip: "该地点将不再跟随省份模板更新。"',
        ' eu5ab_clear_button: "清除策略"',
        ' eu5ab_clear_tooltip: "移除该地点的区域发展策略。"',
        ' eu5ab_choose_location: "选择地点"',
        ' eu5ab_choose_province: "选择省份"',
        ' eu5ab_choose_area: "选择地区"',
        ' eu5ab_location_select_tooltip: "选择要单独设置发展策略的地点。"',
        ' eu5ab_province_select_tooltip: "选择要批量套用模板的省份。"',
        ' eu5ab_area_select_tooltip: "选择要批量应用模板的地区。"',
        ' eu5ab_enter_map_selection: "进入地图选择"',
        ' eu5ab_enter_map_selection_desc: "选择明确的地点、省份或地区作为应用范围。"',
        ' eu5ab_map_select_location_click: "应用到地点"',
        ' eu5ab_map_select_location_click_desc: "在地图上选择一个地点，应用当前模板。"',
        ' eu5ab_map_select_province_ctrl: "应用到省份"',
        ' eu5ab_map_select_province_ctrl_desc: "在地图上选择省份，并把当前模板应用到该省份内拥有的地点。"',
        ' eu5ab_map_select_area_shift: "应用到地区"',
        ' eu5ab_map_select_area_shift_desc: "在地图上选择地区，并把当前模板应用到该地区内拥有的地点。"',
        ' eu5ab_template_locations_desc: "选择要应用此模板的地点、省份或地区。"',
        ' eu5ab_template_locations_short: "应用范围："',
        ' eu5ab_view_scope_button: "查看应用范围"',
        ' eu5ab_template_scope_desc: "展示当前模板的实际地理覆盖层级，按「地区 › 省份 › 地点」排列。"',
        ' eu5ab_scope_current_summary: "[GetPlayer.MakeScope.GetVariable(\'eu5ab_scope_location_count\').GetValue|0] 个地点 / [GetPlayer.MakeScope.GetVariable(\'eu5ab_scope_province_count\').GetValue|0] 个省份 / [GetPlayer.MakeScope.GetVariable(\'eu5ab_scope_area_count\').GetValue|0] 个地区"',
        ' eu5ab_scope_expand_province_tt: "展开该省份以查看当前模板覆盖的下辖地点。"',
        ' eu5ab_scope_collapse_province_tt: "折叠该省份以隐藏地点列表。"',
        ' eu5ab_scope_remove_location: "取消应用"',
        ' eu5ab_scope_remove_location_tt: "取消此地点使用的模板，并更新应用范围。"',
        ' eu5ab_scope_clear_all: "清空当前模板的所有地点"',
        ' eu5ab_scope_clear_all_tt: "取消所有地点对当前模板的应用，这些地点将停止自动建造。其他模板不受影响。"',
        ' eu5ab_scope_map_mode_hint: "可在原版「地理」地图模式中选择「高级自动建造覆盖」：亮色为当前模板，暗色为本 Mod 的其他模板。"',
        ' mapmode_eu5ab_template_coverage_name: "高级自动建造覆盖"',
        ' MAPMODE_EU5AB_TEMPLATE_COVERAGE: "#T $mapmode_eu5ab_template_coverage_name$#!\\n亮色地点使用当前在模板界面中选定的模板；暗色地点使用本 Mod 的其他模板；未着色地点未应用模板。"',
        ' eu5ab_scope_map_legend_selected: "当前选中的模板"',
        ' eu5ab_scope_map_legend_other: "本 Mod 的其他模板"',
        ' eu5ab_scope_map_selected_tt: "此地点使用当前选中的本 Mod 模板。"',
        ' eu5ab_scope_map_other_tt: "此地点使用本 Mod 的其他模板。"',
        ' eu5ab_scope_map_unassigned_tt: "此地点未应用本 Mod 模板。"',
        ' eu5ab_template_conflict_replace_desc: "只能选择尚未应用本 Mod 模板的地点。批量应用到省份或地区时，会保留已有模板。"',
        ' eu5ab_open_panel_tooltip: "打开区域发展政策面板。"',
        ' eu5ab_open_regional_development_policy: "本 Mod：查看自动建造设置"',
        ' eu5ab_open_regional_development_policy_desc: "在社区模组框架的「模组设置」中选择「高级自动建造」。"',
        ' eu5ab_set_cash_reserve_0: "EU5AB：最低现金保留 0"',
        ' eu5ab_set_cash_reserve_0_desc: "将所选地点的自动建造最低储备金设为 0。"',
        ' eu5ab_set_cash_reserve_500: "EU5AB：最低现金保留 500"',
        ' eu5ab_set_cash_reserve_500_desc: "将所选地点的自动建造最低储备金设为 500。"',
        ' eu5ab_set_cash_reserve_1000: "EU5AB：最低现金保留 1000"',
        ' eu5ab_set_cash_reserve_1000_desc: "将所选地点的自动建造最低储备金设为 1000。"',
        ' eu5ab_set_cash_reserve_2000: "EU5AB：最低现金保留 2000"',
        ' eu5ab_set_cash_reserve_2000_desc: "将所选地点的自动建造最低储备金设为 2000。"',
        ' eu5ab_enable_special_buildings_for_location: "EU5AB：允许特殊建筑"',
        ' eu5ab_enable_special_buildings_for_location_desc: "允许自动建造系统在所选地点建造或升级特殊建筑。"',
        ' eu5ab_disable_special_buildings_for_location: "EU5AB：禁止特殊建筑"',
        ' eu5ab_disable_special_buildings_for_location_desc: "禁止自动建造系统在所选地点建造或升级特殊建筑。"',
        ' eu5ab_decouple_selected_location: "EU5AB：停止跟随省份模板"',
        ' eu5ab_decouple_selected_location_desc: "以后更改省份模板时，不再更新所选地点。"',
        ' eu5ab_clear_selected_location_policy: "本 Mod：清除地点策略"',
        ' eu5ab_clear_selected_location_policy_desc: "选择地点后，取消模板应用并清除相关设置。"',
    ]
    lines.extend(f' {key}: "{value}"' for key, value in rgo_localization.ZH.items())
    lines.extend(_cmm_chinese_localization_lines())
    for _, name_id in TEMPLATE_NAME_CHOICES:
        display = {
            "food_security": "食物安全区",
            "mining_development": "矿业开发区",
            "port_trade": "港口贸易区",
            "urban_industry": "城市工商业区",
            "military_frontier": "军事边区",
            "custom": "自定义",
        }[name_id]
        lines.append(f' eu5ab_template_name_{name_id}: "{display}"')
    for slot in TEMPLATE_SLOTS:
        cash_var = "eu5ab_global_min_cash_reserve"
        price_min_var = "eu5ab_global_price_min"
        price_max_var = "eu5ab_global_price_max"
        display_name = f"$eu5ab_template_slot_{slot}_display_name$"
        # Coverage counts are computed only for the template whose scope window is open.
        lines.extend([
            f' eu5ab_template_slot_{slot}_title: "自定义模板 {slot}"',
            f' eu5ab_template_slot_{slot}_display_name: "{_slot_display_name_expr(slot, player="GetPlayer")}"',
            f' eu5ab_template_slot_{slot}_editor_title: "编辑本模板"',
            f' eu5ab_template_slot_{slot}_buildings_title: "自定义模板 {slot}：建筑规则"',
            f' eu5ab_template_slot_{slot}_locations_title: "自定义模板 {slot}：设置地点"',
            f" eu5ab_template_slot_{slot}_summary: \"修改会立即保存。\\n规则摘要：建筑优先级、价格区间、储备金、劳动力和投入品规则由编辑界面控制。\\n覆盖：点击「查看实际覆盖范围」时按当前模板即时统计。\"",
            f" eu5ab_template_slot_{slot}_cash_value: \"储备金：[GetPlayer.MakeScope.GetVariable('{cash_var}').GetValue|0Y]@gold!\"",
            f" eu5ab_template_slot_{slot}_price_min_value: \"最低价格：[GetPlayer.MakeScope.GetVariable('{price_min_var}').GetValue|0Y]%\"",
            f" eu5ab_template_slot_{slot}_price_max_value: \"最高价格：[GetPlayer.MakeScope.GetVariable('{price_max_var}').GetValue|0Y]%\"",
            f' eu5ab_apply_template_slot_{slot}_to_selected_location: "将「{display_name}」应用到地点"',
            f' eu5ab_apply_template_slot_{slot}_to_selected_location_desc: "将模板「{display_name}」应用到所选的已拥有地点。后续对模板的修改会继续生效。"',
            f' eu5ab_apply_template_slot_{slot}_to_selected_province: "将「{display_name}」应用到省份"',
            f' eu5ab_apply_template_slot_{slot}_to_selected_province_desc: "将模板「{display_name}」应用到所选省份内尚未分配模板的已拥有地点。"',
            f' eu5ab_apply_template_slot_{slot}_to_selected_area: "将「{display_name}」应用到地区"',
            f' eu5ab_apply_template_slot_{slot}_to_selected_area_desc: "将模板「{display_name}」应用到所选地区内尚未分配模板的已拥有地点。"',
        ])
    for building_id in _catalog_building_ids(catalog):
        localization_key = _building_localization_key(building_id, catalog)
        lines.append(f' {_building_name_key(building_id)}: "' + "$" + localization_key + '$"')
    for policy in policies:
        zh_name = policy.prediction.get("display_name", policy.id)
        zh_desc = policy.prediction.get("summary", policy.role)
        lines.append(f' {policy.name_key}: "{zh_name}"')
        lines.append(f' {policy.description_key}: "{zh_desc}"')
        lines.append(f' eu5ab_apply_{policy.id}_to_selected_location: "EU5AB：套用{zh_name}"')
        lines.append(f' eu5ab_apply_{policy.id}_to_selected_location_desc: "将「{zh_name}」区域发展模板套用到所选地块。{zh_desc}"')
        lines.append(f' eu5ab_apply_preset_{policy.id}_to_selected_location: "EU5AB：套用{zh_name}"')
        lines.append(f' eu5ab_apply_preset_{policy.id}_to_selected_location_desc: "将「{zh_name}」区域发展模板套用到所选地块。{zh_desc}"')
        lines.append(f' eu5ab_apply_preset_{policy.id}_to_selected_province: "EU5AB：省份套用{zh_name}"')
        lines.append(f' eu5ab_apply_preset_{policy.id}_to_selected_province_desc: "将「{zh_name}」区域发展模板套用到所选省份内已拥有地点。{zh_desc}"')
        lines.append(f' eu5ab_apply_preset_{policy.id}_to_selected_area: "EU5AB：地区应用{zh_name}"')
        lines.append(f' eu5ab_apply_preset_{policy.id}_to_selected_area_desc: "将「{zh_name}」区域发展模板应用到所选地区内已拥有地点。{zh_desc}"')
        # All presets share the on-demand eu5ab_scope_current_summary view.
    replacements = [
        ("EU5 Advanced Auto Build", "本 Mod"),
        ("EU5AB", "本 Mod"),
        ("现金储备安全线", "储备金"),
        ("最低现金保留", "储备金"),
        ("现金安全线", "储备金"),
        ("现金储备", "储备金"),
        ("现金保留", "储备金"),
        ("地块", "地点"),
        ("劳力", "劳动力"),
        ("本体", "原版"),
        ("其他 MOD", "其他 Mod"),
        ("tab", "页签"),
        ("套用", "应用"),
        ("政策", "策略"),
    ]
    chinese_overrides = {
        "eu5ab_template_rules_window_title": "建造报告",
        "eu5ab_open_rules_editor_button": "建造报告",
        "eu5ab_automation_buildings_tab_desc": "管理模板、建筑优先级与应用范围。全国共享的预算、收益与安全规则请在 CMF「模组设置」中配置。",
        "eu5ab_action_bar_tooltip": "打开区域发展模板面板，配置建筑优先级与应用范围，并查看最近一次月度建造报告。",
        "eu5ab_template_editor_desc": "配置此模板的建筑优先级与应用范围。全国共享的预算、市场、劳动力与建造安全规则请在 CMF「模组设置」中配置。",
        "eu5ab_template_editor_sections_title": "模板设置",
        "eu5ab_template_editor_sections_desc": "每个模板单独保存启停状态、应用范围与建筑优先级。最近一次月度建造结果可在「建造报告」中查看。",
        "eu5ab_preset_readonly_desc": "风味模板的建筑优先级固定，可单独暂停、恢复或应用到地点。如需修改优先级，可复制为自定义模板。共享规则在 CMF「模组设置」中调整。",
        "eu5ab_pause_template_tooltip": "暂停或恢复此模板。暂停会保留建筑优先级和应用地点，但不再为这些地点安排自动建造。",
    }
    for slot in TEMPLATE_SLOTS:
        chinese_overrides[f"eu5ab_template_slot_{slot}_summary"] = (
            "此模板单独保存启停状态、应用范围与建筑优先级。全国共享的预算、收益门槛与安全规则请在 CMF「模组设置」中配置；「建造报告」展示最近一次月度建造结果。"
        )
        chinese_overrides[f"eu5ab_template_slot_{slot}_cash_value"] = (
            "共享储备金：[GetPlayer.MakeScope.GetVariable('eu5ab_global_min_cash_reserve').GetValue|0Y]@gold!"
        )
        chinese_overrides[f"eu5ab_template_slot_{slot}_price_min_value"] = (
            "共享最低价格：[GetPlayer.MakeScope.GetVariable('eu5ab_global_price_min').GetValue|0Y]%"
        )
        chinese_overrides[f"eu5ab_template_slot_{slot}_price_max_value"] = (
            "共享高价参考：[GetPlayer.MakeScope.GetVariable('eu5ab_global_price_max').GetValue|0Y]%"
        )
    normalized_lines: list[str] = []
    for line in lines:
        key, separator, value = line.partition(":")
        if not separator:
            normalized_lines.append(line)
            continue
        for old, new in replacements:
            value = value.replace(old, new)
        override = chinese_overrides.get(key.strip())
        if override is not None:
            value = f' "{override}"'
        normalized_lines.append(key + separator + value)
    return "\n".join(normalized_lines) + "\n"


def _english_localization_values() -> dict[str, str]:
    return {
        "eu5ab_window_title": "Automated Regional Development",
        "eu5ab_template_editor_title": "Edit Regional Development Template",
        "eu5ab_template_buildings_window_title": "Building Rules",
        "eu5ab_template_rules_window_title": "Construction Report",
        "eu5ab_template_rename_window_title": "Rename Template",
        "eu5ab_template_scope_window_title": "Current Coverage",
        "eu5ab_automation_buildings_tab": "Automated Construction",
        "eu5ab_automation_buildings_tab_desc": "Manage templates, building priorities, and coverage. Change rules shared by all templates in Community Mod Framework Mod Settings.",
        "eu5ab_action_bar_name": "Advanced Auto Build",
        "eu5ab_action_bar_tooltip": "Manage regional-development templates, building priorities, and coverage, and review the latest automated construction result.",
        "eu5ab_action_bar_icon": "@production_panel!",
        "eu5ab_action_bar_color": "gold",
        "eu5ab_template_overview_title": "Regional Development Templates",
        "eu5ab_presets_tab": "Built-in Presets",
        "eu5ab_presets_tab_tooltip": "Fixed building priorities for different goals. Copy a preset as a player template to edit it.",
        "eu5ab_custom_tab": "Custom Templates",
        "eu5ab_custom_tab_tooltip": "Set your own building priorities and coverage.",
        "eu5ab_sidebar_title": "Templates",
        "eu5ab_detail_title": "Rule Details",
        "eu5ab_new_template_plus_button": "+ New Template",
        "eu5ab_new_blank_template_button": "+ Blank Template",
        "eu5ab_new_recommended_template_button": "+ Recommended Template",
        "eu5ab_custom_empty_detail": "Select a custom template on the left, or create a blank template or one with recommended priorities.",
        "eu5ab_template_intro_title": "Template Editor",
        "eu5ab_automation_buildings_intro": "Custom templates let you set building priorities and assign locations. Built-in presets have fixed priorities; copy one as a player template to edit them.",
        "eu5ab_player_templates_button": "Player Templates",
        "eu5ab_copy_preset_to_player_button": "Copy as Player Template",
        "eu5ab_delete_template_button": "Delete Template",
        "eu5ab_delete_template_tooltip": "Delete this custom template. Locations using it will also be unassigned.",
        "eu5ab_delete_template_confirm_prompt": "Delete the current template?",
        "eu5ab_delete_template_confirm_button": "Confirm Delete",
        "eu5ab_delete_template_confirm_tooltip": "Permanently delete this template and remove it from every assigned location. This cannot be undone.",
        "eu5ab_delete_template_cancel_button": "Cancel",
        "eu5ab_delete_template_cancel_tooltip": "Cancel deletion and return to the template actions.",
        "eu5ab_pause_template_button": "Pause Template",
        "eu5ab_resume_template_button": "Resume Template",
        "eu5ab_template_paused_badge": " (Paused)",
        "eu5ab_pause_template_tooltip": "Pause or resume this template. Priorities and location assignments are kept, but automated construction skips these locations while paused.",
        "eu5ab_select_template_tooltip": "Select this template and view its rule details.",
        "eu5ab_preset_readonly_desc": "Built-in presets have fixed priorities and can be paused, resumed, or assigned separately. Copy one as a player template to edit priorities. Shared rules are in CMF Mod Settings.",
        "eu5ab_template_name_pencil_hint": "Template Name",
        "eu5ab_template_name_click_hint": "Click the name to rename",
        "eu5ab_template_name_click_tooltip": "Enter a new name for the current template.",
        "eu5ab_template_rename_desc": "Enter a new name for the current template, up to 42 characters.",
        "eu5ab_template_rename_input": "Template Name",
        "eu5ab_template_rename_accept": "Confirm",
        "eu5ab_template_rename_cancel": "Cancel",
        "eu5ab_target_location_title": "Target Location",
        "eu5ab_target_location_desc": "Choose a location before clearing its settings or stopping province-template updates. Use the selection buttons on a template card to apply a template.",
        "eu5ab_template_editor_desc": "Name this template and configure its building priorities. Shared budget, market, workforce, and safety rules are in Community Mod Framework Mod Settings.",
        "eu5ab_template_auto_save_hint": "Changes are saved immediately. Close the window to return.",
        "eu5ab_rules_tab_finance": "Finance & Construction",
        "eu5ab_rules_tab_automation": "Workforce & Building Preferences",
        "eu5ab_rules_tab_diagnostics": "Construction Report",
        "eu5ab_template_editor_sections_title": "Template Settings",
        "eu5ab_template_editor_sections_desc": "Each template stores its enabled state, coverage, and building priorities. Open Construction Report to review the latest automated construction result.",
        "eu5ab_open_buildings_editor_button": "Building Rules",
        "eu5ab_open_rules_editor_button": "Construction Report",
        "eu5ab_edit_template_button": "Edit",
        "eu5ab_copy_to_slot_button": "Copy Here",
        "eu5ab_policy_section_title": "Template Rules",
        "eu5ab_cash_section_title": "Treasury Reserve",
        "eu5ab_cash_short_desc": "Minimum balance that must remain in the treasury.",
        "eu5ab_cash_label": "Treasury Reserve",
        "eu5ab_active_cash_amount": "[GetPlayer.MakeScope.GetVariable('eu5ab_global_min_cash_reserve').GetValue|0] gold",
        "eu5ab_cash_help": "Before construction, estimated costs for this and other planned projects must leave enough gold for the reserve.\\nWith 1,050 gold and a reserve of 1,000, a project estimated to cost 100 cannot start. Actual RGO costs may differ from estimates. Some annual budget must also remain.",
        "eu5ab_budget_section_title": "Annual Construction Budget",
        "eu5ab_budget_short_desc": "Choose a fixed amount or a yearly allowance based on total monthly income.",
        "eu5ab_budget_mode_fixed": "Fixed Budget",
        "eu5ab_budget_mode_income": "Income Linked",
        "eu5ab_budget_multiplier_4": "×4 Conservative",
        "eu5ab_budget_multiplier_6": "×6 Recommended",
        "eu5ab_budget_multiplier_8": "×8 Active",
        "eu5ab_budget_effective_label": "Current-Year Budget",
        "eu5ab_budget_effective_amount": "[GetPlayer.MakeScope.GetVariable('eu5ab_global_budget_limit').GetValue|0] gold",
        "eu5ab_budget_label": "Annual Budget",
        "eu5ab_annual_budget_amount": "[GetPlayer.MakeScope.GetVariable('eu5ab_global_fixed_annual_budget').GetValue|0] gold/year",
        "eu5ab_budget_cash_comparison": "The annual budget sets planned spending; the treasury reserve sets how much gold to keep. The final project may exceed the remaining budget but must pass the reserve check.",
        "eu5ab_budget_reset_note": "Reset at the first check of a new year; charge actual spending only after construction starts. Changing the budget does not erase recorded spending.",
        "eu5ab_budget_help": "Ordinary buildings and RGO expansions share a yearly budget: a fixed amount or 4, 6, or 8 times total monthly income. It resets at the first check of a new year; changing it during the year keeps spending already recorded.\\nOnly successful starts count, at their actual cost. The final project may exceed the remaining budget; no further projects are added afterward. Treasury reserve requirements still apply.",
        "eu5ab_quota_section_title": "This Mod's Concurrent Construction Limit",
        "eu5ab_quota_short_desc": "Sets how many civil projects this Mod may run at once beyond the base slot.",
        "eu5ab_hard_cap_label": "Extra Concurrent Projects",
        "eu5ab_hard_cap_amount": "[GetPlayer.MakeScope.GetVariable('eu5ab_monthly_build_hard_cap').GetValue|0] projects (total limit is this value + 1)",
        "eu5ab_quota_help": "Set extra space beyond the first project: 0 allows 1 concurrent project; 599 allows 600. Ordinary buildings and RGOs share it. Only unfinished projects from this Mod count; manual construction, roads, and other Mods do not. Each round fills free space only. A location may receive several projects if space allows, then waits 3 months after the round before new projects are arranged.",
        "eu5ab_template_cash_value": "Treasury reserve: [GetPlayer.MakeScope.GetVariable('eu5ab_tpl_min_cash_reserve').GetValue|0Y]@gold!",
        "eu5ab_step_dec_10k": "-10K",
        "eu5ab_step_dec_1k": "-1K",
        "eu5ab_step_inc_1k": "+1K",
        "eu5ab_step_inc_10k": "+10K",
        "eu5ab_step_dec_10": "-10",
        "eu5ab_step_dec_1": "-1",
        "eu5ab_step_inc_1": "+1",
        "eu5ab_step_inc_10": "+10",
        "eu5ab_step_dec_5": "-5",
        "eu5ab_step_inc_5": "+5",
        "eu5ab_step_dec_100": "-100",
        "eu5ab_step_inc_100": "+100",
    }


def _english_rules_localization_values() -> dict[str, str]:
    return {
        "eu5ab_building_rules_title": "Building Rules",
        "eu5ab_building_rules_desc": "Filter by workforce on the first row and unlock age on the second. Priorities range from 0.0 to 10.0; 0 disables construction. The Special page only lists special buildings the country can actively build in at least one owned location.",
        "eu5ab_allow_button": "Allow",
        "eu5ab_ban_button": "Ban",
        "eu5ab_priority_decrease": "−",
        "eu5ab_priority_increase": "+",
        "eu5ab_priority_decrease_default_tt": "Decrease priority by 0.1",
        "eu5ab_priority_decrease_ctrl_tt": "Ctrl: decrease priority by 0.5",
        "eu5ab_priority_decrease_shift_tt": "Shift: decrease priority by 1.0",
        "eu5ab_priority_increase_default_tt": "Increase priority by 0.1",
        "eu5ab_priority_increase_ctrl_tt": "Ctrl: increase priority by 0.5",
        "eu5ab_priority_increase_shift_tt": "Shift: increase priority by 1.0",
        "eu5ab_priority_scale_hint": "0 disables",
        "eu5ab_clear_visible_priorities_button": "Clear Current List",
        "eu5ab_clear_visible_priorities_tooltip": "Immediately set every building visible under the current workforce and age filters to 0 and save this template. Hidden special buildings are unchanged.",
        "eu5ab_priority_low": "Low",
        "eu5ab_priority_medium": "Medium",
        "eu5ab_priority_high": "High",
        "eu5ab_priority_high_icon": "↑",
        "eu5ab_priority_medium_icon": "–",
        "eu5ab_priority_low_icon": "↓",
        "eu5ab_ban_icon": "×",
        "eu5ab_filter_all": "All",
        "eu5ab_filter_rural": "Rural",
        "eu5ab_filter_laborers": "Laborers",
        "eu5ab_filter_burghers": "Burghers",
        "eu5ab_filter_soldiers": "Military",
        "eu5ab_filter_special": "Special",
        "eu5ab_age_all": "All Ages",
        "eu5ab_building_age_1": "Age of Traditions",
        "eu5ab_building_age_2": "Age of Renaissance",
        "eu5ab_building_age_3": "Age of Discovery",
        "eu5ab_building_age_4": "Age of Reformation",
        "eu5ab_building_age_5": "Age of Absolutism",
        "eu5ab_building_age_6": "Age of Revolutions",
        "eu5ab_status_enabled": "#G Enabled#!",
        "eu5ab_status_disabled": "#L Disabled#!",
        "eu5ab_status_currently_available": "#G Available#!",
        "eu5ab_operating_rules_title": "Construction Rules",
        "eu5ab_operating_rules_short_desc": "Configure special buildings, upstream construction, and input shortages.",
        "eu5ab_operating_rules_help": "Special buildings must meet the game's unlock and construction requirements.\\nInput shortages can prompt construction of suppliers allowed by the template, even when existing factories are fully staffed.\\nWith input protection enabled, supply of required key industrial inputs must cover 75% of demand. Use current production methods where possible, otherwise estimate an available method. Alternative methods are assessed separately; production methods are not changed automatically.",
        "eu5ab_rgo_section_title": "RGO",
        "eu5ab_rgo_allow": "Allow This Template to Expand RGOs",
        "eu5ab_toggle_special_buildings": "Allow Special Buildings",
        "eu5ab_toggle_auto_build_input_sources": "Build Upstream Sources on Missing Inputs",
        "eu5ab_toggle_pause_low_workforce": "Pause Expansion on Low Workforce",
        "eu5ab_ranking_mode_section_title": "Construction Decision Strategy",
        "eu5ab_ranking_mode_current_label": "Current Mode",
        "eu5ab_ranking_mode_composite_value": "#G Supply-Demand Planning#!",
        "eu5ab_ranking_mode_actual_profit_value": "#G Predicted Profit Selection#!",
        "eu5ab_ranking_mode_common_desc": "Both strategies consider only unlocked, buildable buildings with a template priority above 0. Projects must also meet the selected return requirement, budget, treasury reserve, input, workforce, and other safety rules. Food emergencies and Automated Build Order always come first.",
        "eu5ab_town_rights_preference_desc": "Urban rights and Promote Industry each add up to 500 planning points independently. Industry support applies only to direct matching building outputs in your promoted area, weighted by selected recipe output at base prices; it does not propagate along supply chains. Both stack with local-input points. Profit mode uses these points only for preselection. RGO expansion retains only the urban-right bonus. All construction requirements still apply.",
        "eu5ab_ranking_mode_composite_desc": "Balances market shortages, strategic demand, production efficiency, local raw-material availability, commodity prices, and workforce supply risk, prioritizing complete production chains and long-term economic stability.",
        "eu5ab_ranking_mode_actual_profit_desc": "Filters candidate projects through template and safety rules, then prioritizes construction by predicted monthly net benefit, including windmill resource gains and the food value saved by granaries. When predicted benefits are close, building priorities configured in the template serve as a secondary reference.",
        "eu5ab_ranking_mode_actual_profit_scope_desc": "Keep the configured 3–30 alternatives per location and ordinary build type. Food safeguards and Automated Build Order take precedence; return and construction requirements still apply. RGOs are assessed separately by shortages, prices, employment, and strategic needs.",
        "eu5ab_ranking_mode_help": "Decision Strategy\\nSwitch strategies in Community Mod Framework → Mod Settings → Advanced Auto Build → Safety & Ranking → Construction Decision Strategy.\\n• Supply-Demand Planning: Emphasizes market supply and demand, complete production chains, and long-term economic stability.\\n• Predicted Profit Selection: Uses predicted monthly net benefit, including windmill resource gains and granary decay savings, with template building priorities as a tiebreaker.",
        "eu5ab_workforce_section_title": "Workforce",
        "eu5ab_pause_workforce_short_desc": "Controls whether workforce shortages block expansion.",
        "eu5ab_job_fill_deadline_label": "Workforce Forecast Horizon",
        "eu5ab_job_fill_deadline_amount": "[GetPlayer.MakeScope.GetVariable('eu5ab_global_job_fill_deadline_months').GetValue|0] months",
        "eu5ab_job_fill_deadline_value": "Workforce forecast horizon: [GetPlayer.MakeScope.GetVariable('eu5ab_global_job_fill_deadline_months').GetValue|0] months",
        "eu5ab_job_fill_deadline_desc": "Sets the maximum workforce forecast horizon in months (0–240). Zero counts only currently available workers, without future promotions. Pause on Low Workforce determines whether shortages block construction: when enabled, insufficient projected workers prevent a start; when disabled, shortages only lower build priority.",
        "eu5ab_deadline_0": "0 mo.",
        "eu5ab_deadline_3": "3 mo.",
        "eu5ab_deadline_6": "6 mo.",
        "eu5ab_deadline_12": "12 mo.",
        "eu5ab_toggle_stop_input_shortage": "Stop Expansion on Critical Input Shortage",
        "eu5ab_prediction_status_label": "Workforce Estimate",
        "eu5ab_status_promotion_forecast": "#G Promotion Forecast for Selected Horizon#!",
        "eu5ab_status_conservative_fallback": "#L Conservative Current-Workforce Estimate#!",
        "eu5ab_prediction_promotion_short_desc": "Combines currently available workers with eligible population projected to promote into the target social class within the horizon (up to 240 months).",
        "eu5ab_prediction_unavailable_short_desc": "When a reliable forecast is unavailable, relies strictly on currently available idle workers.",
        "eu5ab_native_input_section_title": "Local Input Preference",
        "eu5ab_native_input_short_desc": "Ranks production buildings higher when their raw materials exist in the same province.",
        "eu5ab_native_input_priority_label": "Local Input Priority",
        "eu5ab_native_input_priority_amount": "[GetPlayer.MakeScope.GetVariable('eu5ab_global_native_input_priority').GetValue|0] / 10",
        "eu5ab_native_input_priority_value": "Local input priority: [GetPlayer.MakeScope.GetVariable('eu5ab_global_native_input_priority').GetValue|0] / 10",
        "eu5ab_native_input_priority_desc": "Local Raw Material Preference\\nLocal refers to the province containing the building. The system checks raw materials required by the building recipe and grants ranking bonus when matching RGOs exist in the province; inputs comprising a larger share of the recipe yield a higher bonus.\\n• 0 ignores local raw materials, 5 is the default recommendation, and 10 grants maximum weight.\\n• This setting affects ranking scores only; actual construction remains subject to other shortages, profit, workforce, and base-game conditions.\\n• Checks only whether a matching RGO exists, not its level or output.\\n• Input shortages, low market access, or low control reduce the bonus. RGOs themselves do not receive this bonus. Estimates use eligible production methods; production methods are not switched automatically.",
        "eu5ab_price_section_title": "Price Range",
        "eu5ab_price_short_desc": "Filters and ranks production buildings by market price.",
        "eu5ab_price_min_label": "Minimum Price",
        "eu5ab_price_max_label": "High-Price Reference",
        "eu5ab_active_price_min_amount": "[GetPlayer.MakeScope.GetVariable('eu5ab_global_price_min').GetValue|0]%",
        "eu5ab_active_price_max_amount": "[GetPlayer.MakeScope.GetVariable('eu5ab_global_price_max').GetValue|0]%",
        "eu5ab_price_section_desc": "Prices use base price as 100%. Low prices reduce priority; pause construction if all outputs are at or below the minimum. Weight multiple outputs by quantity and base price. High-price bonuses stop growing at the reference; high prices do not block construction. Buildings without output goods are exempt. Food safeguards apply as configured.",
        "eu5ab_active_cash_value": "Treasury reserve: [GetPlayer.MakeScope.GetVariable('eu5ab_global_min_cash_reserve').GetValue|0Y]@gold!",
        "eu5ab_active_price_min_value": "Minimum price: [GetPlayer.MakeScope.GetVariable('eu5ab_global_price_min').GetValue|0Y]%",
        "eu5ab_active_price_max_value": "High-price reference: [GetPlayer.MakeScope.GetVariable('eu5ab_global_price_max').GetValue|0Y]%",
        "eu5ab_price_min_value": "Minimum price: [GetPlayer.MakeScope.GetVariable('eu5ab_tpl_price_min').GetValue|0Y]%",
        "eu5ab_price_max_value": "High-price reference: [GetPlayer.MakeScope.GetVariable('eu5ab_tpl_price_max').GetValue|0Y]%",
    }


def _english_diagnostics_localization_values() -> dict[str, str]:
    values = {
        "eu5ab_prediction_section_title": "Automated Construction Rules",
        "eu5ab_prediction_diagnostics_title": "Workforce Estimate & Construction Status",
        "eu5ab_prediction_section_body": "Arrange upgrades, ordinary expansions, RGO expansions, and new buildings in your chosen Automated Build Order, trying eligible projects of the current type first.\\nWhen enabled food safeguards apply, relevant food projects come first and return, price, or other limits are relaxed as configured. Enabled safeguards for construction goods, wartime supplies, or strategic inputs can also relax return requirements.\\nBudget, treasury reserve, and applicable input, workforce, building capacity, and game construction requirements still apply. Only the latest unlocked ordinary building tier is considered; upgrades count added jobs only.",
        "eu5ab_diagnostics_title": "Automated Construction Status",
        "eu5ab_diagnostics_snapshot_note": "Settings save immediately. Reports update as checks progress and projects start, retaining results afterward.",
        "eu5ab_diagnostics_snapshot_help": "The report updates as checks progress and construction starts, keeping results until the next round. Projects are arranged from the 23rd, so counts and spending may change gradually. Some results remain pending until checks finish.",
        "eu5ab_diag_overview_title": "Monthly Construction Overview",
        "eu5ab_diag_quota_title": "Construction Capacity This Check",
        "eu5ab_diag_result_title": "Projects Started This Check",
        "eu5ab_diag_failure_title": "Projects Rejected Last Check",
        "eu5ab_diag_candidates_title": "Top Three Project Choices",
        "eu5ab_diag_label_status": "Automated Construction Status",
        "eu5ab_diag_label_last_run": "Last Check Date",
        "eu5ab_diag_label_covered": "Locations Using Templates",
        "eu5ab_diag_label_preliminary": "Eligible Locations",
        "eu5ab_diag_label_deep_scored": "Locations Checked",
        "eu5ab_diag_label_legal": "Candidates with Enough Workforce",
        "eu5ab_diag_label_staged_candidates": "Candidates Reaching Final Checks",
        "eu5ab_diag_label_engine_probes": "Profit and Cost Checks",
        "eu5ab_diag_label_queue_throttle": "Concurrent Slots",
        "eu5ab_diag_label_engine_queue": "Current Build Check",
        "eu5ab_diag_label_queue_recoveries": "Automatic Resets",
        "eu5ab_diag_label_prediction_mode": "Workforce Estimate",
        "eu5ab_diag_last_run_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_run_year').GetValue|0]-[GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_run_month').GetValue|0]-[GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_run_day').GetValue|0]",
        "eu5ab_diag_covered_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_covered_locations').GetValue|0]",
        "eu5ab_diag_preliminary_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_preliminary_passed').GetValue|0]",
        "eu5ab_diag_deep_scored_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_deep_scored').GetValue|0]",
        "eu5ab_diag_legal_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_legal_candidates').GetValue|0]",
        "eu5ab_diag_staged_candidates_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_staged_candidates').GetValue|0]",
        "eu5ab_diag_engine_probes_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_engine_probes').GetValue|0]",
        "eu5ab_diag_state_not_run": "#L Awaiting next monthly check#!",
        "eu5ab_diag_state_success": "#G Executed successfully#!",
        "eu5ab_diag_state_complete_no_build": "#Y Check complete; no project added#!",
        "eu5ab_diag_state_scan_stalled": "#Y This check was incomplete; a new check will begin next round.#!",
        "eu5ab_diag_label_capacity_waiting": "Locations Awaiting Capacity Checks",
        "eu5ab_diag_label_capacity_unavailable": "Insufficient or Unknown Capacity",
        "eu5ab_diag_label_capacity_expired": "Unfinished Capacity Checks Last Month",
        "eu5ab_diag_label_capacity_reason": "Last capacity restriction",
        "eu5ab_diag_capacity_reason_1": "Used Capacity Unknown",
        "eu5ab_diag_capacity_reason_2": "No Usable Capacity Limit",
        "eu5ab_diag_capacity_reason_3": "Building Capacity Usage Limit Reached",
        "eu5ab_diag_capacity_waiting_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_capacity_waiting').GetValue|0]",
        "eu5ab_diag_capacity_unavailable_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_capacity_unavailable').GetValue|0]",
        "eu5ab_diag_capacity_expired_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_capacity_expired').GetValue|0]",
        "eu5ab_diag_state_ready": "Monthly check completed.",
        "eu5ab_diag_state_no_coverage": "#R No locations use this Mod's templates#!",
        "eu5ab_diag_state_hard_cap": "#Y This Mod's concurrent construction limit reached#!",
        "eu5ab_diag_state_no_preliminary": "#R No locations are currently eligible#!",
        "eu5ab_diag_state_queue_throttled": "Projects still under construction from this Mod have filled all configured concurrent slots.",
        "eu5ab_status_queue_throttled": "#Y Full#!",
        "eu5ab_status_not_throttled": "#G Space available#!",
        "eu5ab_status_engine_queue_prepared": "#L Organizing buildable projects#!",
        "eu5ab_status_engine_queue_validating": "#Y Verifying costs, returns, and conditions#!",
        "eu5ab_status_engine_queue_executing": "#Y Attempting construction#!",
        "eu5ab_status_engine_queue_confirmed": "#G Project construction confirmed#!",
        "eu5ab_status_engine_queue_recovered": "#R Previous check did not complete; reset automatically#!",
        "eu5ab_status_engine_queue_profit_ranking": "#Y Ranking by predicted monthly profit#!",
        "eu5ab_diag_queue_recoveries_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_queue_recoveries').GetValue|0]",
        "eu5ab_status_waiting_next_month": "#L Awaiting next monthly check#!",
        "eu5ab_status_prediction_realtime": "#G Promotion forecast for selected horizon#!",
        "eu5ab_status_prediction_proxy": "#Y Conservative workforce estimate#!",
        "eu5ab_diag_no_build_this_run": "#Y No new project started this month#!",
        "eu5ab_diag_candidates_not_scanned_full": "All concurrent construction slots were full, so this check did not scan for new projects. Checks resume after slots become available.",
        "eu5ab_diag_no_ranked_candidates": "The previous check found no buildable project. The sections below detail the reasons.",
        "eu5ab_diag_quota_short_desc": "Shows this Mod's active projects, concurrent limit, and maximum new projects for the current check.",
        "eu5ab_diag_label_capacity_summary": "Automated Construction Capacity",
        "eu5ab_diag_label_rgo_used": "Used by RGOs",
        "eu5ab_diag_capacity_summary_value": "Active [GetPlayer.MakeScope.GetVariable('eu5ab_diag_active_mod_projects').GetValue|0] / limit [GetPlayer.MakeScope.GetVariable('eu5ab_diag_base_quota').GetValue|0] · maximum new this check [GetPlayer.MakeScope.GetVariable('eu5ab_diag_final_quota').GetValue|0]",
        "eu5ab_diag_label_previous_month_added": "Confirmed Starts in Previous Round",
        "eu5ab_diag_previous_month_added_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_previous_month_added').GetValue|0] projects",
        "eu5ab_diag_label_expected_this_run": "Maximum New This Check",
        "eu5ab_diag_expected_this_run_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_final_quota').GetValue|0] projects",
        "eu5ab_diag_rgo_used_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_quota_used').GetValue|0] projects",
        "eu5ab_diag_label_result": "Project Started",
        "eu5ab_diag_label_actual_cost": "Construction Cost",
        "eu5ab_diag_label_actual_income": "Game-Predicted Monthly Income",
        "eu5ab_diag_label_actual_profit": "Predicted Monthly Net Benefit",
        "eu5ab_diag_label_emergency_overrides": "Return Requirement Relaxed for Strategic Need",
        "eu5ab_diag_actual_cost_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_actual_cost').GetValue|2]",
        "eu5ab_diag_actual_income_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_actual_income').GetValue|2]",
        "eu5ab_diag_actual_profit_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_actual_profit').GetValue|2]",
        "eu5ab_diag_emergency_overrides_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_emergency_overrides_used').GetValue|0] projects",
        "eu5ab_diag_result_rgo_value": "#G Success#! · [GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_build_location').GetLocation.GetName] · RGO · Expansion",
        "eu5ab_diag_result_new_value": "#G Success#! · [GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_build_location').GetLocation.GetName] · [GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_building').GetBuildingType.GetName] · New",
        "eu5ab_diag_result_upgrade_value": "#G Success#! · [GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_build_location').GetLocation.GetName] · [GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_building').GetBuildingType.GetName] · Upgrade",
        "eu5ab_diag_result_expansion_value": "#G Success#! · [GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_build_location').GetLocation.GetName] · [GetPlayer.MakeScope.GetVariable('eu5ab_diag_last_building').GetBuildingType.GetName] · Expansion",
        "eu5ab_diag_result_help": "When enabled food safeguards apply, food projects come first. Other projects follow Automated Build Order, trying alternatives if a project cannot start.\\nRGOs are assessed by shortages, prices, employment, and strategic needs, subject to game construction requirements.\\nOnly successful starts use budget and construction space. After the round, locations with new projects wait 3 months before further construction.",
        "eu5ab_diag_rgo_title": "RGO Candidate Checks",
        "eu5ab_diag_rgo_short_desc": "Each location records one result. A rejected location is counted under the first reason that blocked it.",
        "eu5ab_diag_rgo_help": "Shows the last RGO expansion check. Existing jobs must be full. Consider Population forecasts new workers; Relaxed does not. Prices, output gains not yet realized, and current worker shortages affect priority. Output gains are combined for owned projects producing the same good in the same market; incomplete figures show only known amounts. Reaching the limit pauses new starts, not existing projects.",
        "eu5ab_diag_rgo_checked_label": "RGO Locations Checked",
        "eu5ab_diag_rgo_eligible_label": "Met All Requirements",
        "eu5ab_diag_rgo_fail_capacity_label": "Already at RGO Limit",
        "eu5ab_diag_rgo_fail_location_label": "No Free Slots / Waiting",
        "eu5ab_diag_rgo_fail_disabled_label": "RGO Expansion Disabled",
        "eu5ab_diag_rgo_fail_finance_label": "Treasury, Budget, or Check Limit",
        "eu5ab_diag_rgo_fail_workforce_label": "Next-Level Workforce Forecast Too Low",
        "eu5ab_diag_rgo_checked_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_checked').GetValue|0]",
        "eu5ab_diag_rgo_eligible_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_eligible').GetValue|0]",
        "eu5ab_diag_rgo_fail_capacity_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_capacity').GetValue|0]",
        "eu5ab_diag_rgo_fail_location_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_location').GetValue|0]",
        "eu5ab_diag_rgo_fail_disabled_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_disabled').GetValue|0]",
        "eu5ab_diag_rgo_fail_finance_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_finance').GetValue|0]",
        "eu5ab_diag_rgo_fail_utilization_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_utilization').GetValue|0]",
        "eu5ab_diag_rgo_fail_workforce_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_workforce').GetValue|0]",
        "eu5ab_diag_rgo_fail_market_need_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_rgo_fail_market_need').GetValue|0]",
        "eu5ab_diag_failure_short_desc": "Shows only the previous monthly check; counts do not carry into the next month.",
        "eu5ab_diag_failure_help": "Reasons Projects Did Not Start\\nDisplays blocking reasons recorded during the previous monthly check; counts do not carry over across months.\\nSeparately tracks projects blocked by insufficient workforce, missing production inputs, output oversupply, insufficient annual budget, insufficient treasury reserve, return below setting, construction material shortages, and unmet base-game conditions.",
        "eu5ab_diag_fail_workforce_label": "Insufficient Workforce",
        "eu5ab_diag_fail_building_capacity_label": "Staffed Building Levels at 110% of Capacity",
        "eu5ab_diag_fail_capacity_unavailable_label": "Building Capacity Unknown or No Usable Limit",
        "eu5ab_diag_fail_building_capacity_value": "[GetPlayer.MakeScope.ScriptValue('eu5ab_diag_fail_building_capacity_ui')|0]",
        "eu5ab_diag_fail_capacity_unavailable_value": "[GetPlayer.MakeScope.ScriptValue('eu5ab_diag_fail_capacity_unavailable_ui')|0]",
        "eu5ab_diag_fail_inputs_label": "Missing Inputs",
        "eu5ab_diag_fail_pending_output_label": "Pending Output Limit or Missing Data",
        "eu5ab_diag_fail_pending_output_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_fail_pending_output').GetValue|0]",
        "eu5ab_diag_fail_oversupply_label": "Output Oversupply",
        "eu5ab_diag_fail_irrigation_need_label": "Irrigation: No Need for More Food or Population Capacity",
        "eu5ab_diag_fail_granary_need_label": "Insufficient Granary Reserve Need or Decay Return",
        "eu5ab_diag_fail_storage_pending_label": "Granary Already Under Construction or Queued in Province",
        "eu5ab_diag_fail_windmill_need_label": "Insufficient Windmill Demand or Net Return",
        "eu5ab_diag_fail_irrigation_need_value": "[GetPlayer.MakeScope.ScriptValue('eu5ab_diag_fail_irrigation_need_ui')|0]",
        "eu5ab_diag_fail_granary_need_value": "[GetPlayer.MakeScope.ScriptValue('eu5ab_diag_fail_granary_need_ui')|0]",
        "eu5ab_diag_fail_storage_pending_value": "[GetPlayer.MakeScope.ScriptValue('eu5ab_diag_fail_storage_pending_ui')|0]",
        "eu5ab_diag_fail_windmill_need_value": "[GetPlayer.MakeScope.ScriptValue('eu5ab_diag_fail_windmill_need_ui')|0]",
        "eu5ab_diag_fail_budget_label": "Insufficient Budget",
        "eu5ab_diag_fail_cash_label": "Insufficient Treasury Reserve",
        "eu5ab_diag_fail_engine_economics_label": "Return Below Setting",
        "eu5ab_diag_fail_construction_materials_label": "Construction-Material Pressure",
        "eu5ab_diag_fail_vanilla_label": "Game Construction Rules Not Met",
        "eu5ab_diag_fail_no_legal_label": "No Qualifying Building",
        "eu5ab_diag_candidates_help": "Priority reflects food emergencies, build order, and the current strategy. Several projects may share a location. Being listed does not guarantee construction; budget, workforce, inputs, capacity, and other requirements still apply.",
        "eu5ab_diag_candidate_1_title": "Project 1",
        "eu5ab_diag_candidate_2_title": "Project 2",
        "eu5ab_diag_candidate_3_title": "Project 3",
        "eu5ab_diag_label_location": "Location",
        "eu5ab_diag_label_building": "Building or RGO",
        "eu5ab_diag_label_scores": "Priority Scores",
        "eu5ab_diag_label_workforce": "Workforce (People)",
        "eu5ab_diag_label_unselected_reason": "Project Status",
        "eu5ab_diag_candidate_1_location_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_location').GetLocation.GetName]",
        "eu5ab_diag_candidate_2_location_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_location').GetLocation.GetName]",
        "eu5ab_diag_candidate_3_location_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_location').GetLocation.GetName]",
        "eu5ab_diag_candidate_1_building_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_building').GetBuildingType.GetName]",
        "eu5ab_diag_candidate_2_building_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_building').GetBuildingType.GetName]",
        "eu5ab_diag_candidate_3_building_value": "[GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_building').GetBuildingType.GetName]",
        "eu5ab_diag_candidate_rgo_value": "RGO Expansion",
        "eu5ab_diag_candidate_empty_value": "#weak No more candidate projects#!",
        "eu5ab_diag_candidate_1_scores_value": "Total [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_score').GetValue|0] · Need [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_need').GetValue|0] · Economy [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_economic').GetValue|1]",
        "eu5ab_diag_candidate_2_scores_value": "Total [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_score').GetValue|0] · Need [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_need').GetValue|0] · Economy [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_economic').GetValue|1]",
        "eu5ab_diag_candidate_3_scores_value": "Total [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_score').GetValue|0] · Need [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_need').GetValue|0] · Economy [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_economic').GetValue|1]",
        "eu5ab_diag_candidate_1_rgo_scores_value": "Total [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_score').GetValue|0] · Location Need [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_need').GetValue|0]",
        "eu5ab_diag_candidate_2_rgo_scores_value": "Total [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_score').GetValue|0] · Location Need [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_need').GetValue|0]",
        "eu5ab_diag_candidate_3_rgo_scores_value": "Total [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_score').GetValue|0] · Location Need [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_need').GetValue|0]",
        "eu5ab_diag_candidate_1_workforce_value": "Required [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_labor_jobs').GetValue|0] · Current [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_labor_current').GetValue|0] · Within Horizon [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_1_labor_projected').GetValue|0]",
        "eu5ab_diag_candidate_2_workforce_value": "Required [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_labor_jobs').GetValue|0] · Current [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_labor_current').GetValue|0] · Within Horizon [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_2_labor_projected').GetValue|0]",
        "eu5ab_diag_candidate_3_workforce_value": "Required [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_labor_jobs').GetValue|0] · Current [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_labor_current').GetValue|0] · Within Horizon [GetPlayer.MakeScope.GetVariable('eu5ab_diag_top_3_labor_projected').GetValue|0]",
        "eu5ab_candidate_reason_ranked": "Shortlisted. Budget, workforce, capacity, and other construction requirements still need checking.",
        "eu5ab_candidate_reason_waiting": "Checking production details. Please wait.",
        "eu5ab_candidate_reason_approved": "Requirements met; confirming whether construction has started.",
        "eu5ab_candidate_reason_confirmed": "Construction has started.",
        "eu5ab_candidate_reason_rejected": "Requirements were not met; construction did not start.",
        "eu5ab_candidate_reason_workforce": "Insufficient workforce",
        "eu5ab_candidate_reason_inputs": "Critical inputs unavailable",
        "eu5ab_candidate_reason_pending_output": "Pending output limit or missing data",
        "eu5ab_candidate_reason_oversupply": "Output already oversupplied",
        "eu5ab_candidate_reason_budget": "Annual construction budget exhausted",
        "eu5ab_candidate_reason_cash": "Treasury reserve requirement not met",
        "eu5ab_candidate_reason_vanilla": "The game's own construction conditions are not met",
        "eu5ab_candidate_reason_no_legal": "No qualifying building",
    }
    for suffix in (
        "workforce",
        "inputs",
        "oversupply",
        "budget",
        "cash",
        "engine_economics",
        "construction_materials",
        "vanilla",
        "no_legal",
    ):
        values[f"eu5ab_diag_fail_{suffix}_value"] = (
            f"[GetPlayer.MakeScope.GetVariable('eu5ab_diag_fail_{suffix}').GetValue|0]"
        )
    return values


def _english_scope_localization_values() -> dict[str, str]:
    return {
        "eu5ab_control_section_title": "Location Controls",
        "eu5ab_policy_status_body": "Shows the current template, annual strategy budget, treasury reserve, special-building setting, next project, pause reason, and forecast result.",
        "eu5ab_automation_policy_footer_text": "Select locations where this Mod's settings should be applied or cleared. Open its controls from Advanced Auto Build in Community Mod Framework.",
        "eu5ab_automation_panel_tooltip": "Open templates and automated-construction controls from Advanced Auto Build in Community Mod Framework.",
        "eu5ab_special_on_button": "Special On",
        "eu5ab_special_off_button": "Special Off",
        "eu5ab_special_toggle_tooltip": "Controls whether this location may automatically build or upgrade special buildings.",
        "eu5ab_cash_0_button": "Reserve 0",
        "eu5ab_cash_500_button": "Reserve 500",
        "eu5ab_cash_1000_button": "Reserve 1000",
        "eu5ab_cash_2000_button": "Reserve 2000",
        "eu5ab_decouple_button": "Stop Following Province Template",
        "eu5ab_decouple_tooltip": "This location will no longer follow province-template updates.",
        "eu5ab_clear_button": "Clear Policy",
        "eu5ab_clear_tooltip": "Remove the regional development policy from this location.",
        "eu5ab_choose_location": "Choose Location",
        "eu5ab_choose_province": "Choose Province",
        "eu5ab_choose_area": "Choose Area",
        "eu5ab_location_select_tooltip": "Choose one location to configure.",
        "eu5ab_province_select_tooltip": "Choose a province to receive a template in bulk.",
        "eu5ab_area_select_tooltip": "Choose an area and assign a template to its owned locations.",
        "eu5ab_enter_map_selection": "Select on Map",
        "eu5ab_enter_map_selection_desc": "Choose a location, province, or area on the map.",
        "eu5ab_map_select_location_click": "Apply to Location",
        "eu5ab_map_select_location_click_desc": "Select a location on the map and assign the current template.",
        "eu5ab_map_select_province_ctrl": "Apply to Province",
        "eu5ab_map_select_province_ctrl_desc": "Select a province and apply the current template to its owned locations.",
        "eu5ab_map_select_area_shift": "Apply to Area",
        "eu5ab_map_select_area_shift_desc": "Select an area and apply the current template to its owned locations.",
        "eu5ab_template_locations_desc": "Choose locations, provinces, or areas for this template.",
        "eu5ab_template_locations_short": "Coverage:",
        "eu5ab_view_scope_button": "View Current Coverage",
        "eu5ab_template_scope_desc": "Shows the selected custom template or built-in preset as Area › Province › Location.",
        "eu5ab_scope_current_summary": "[GetPlayer.MakeScope.GetVariable('eu5ab_scope_location_count').GetValue|0] locations / [GetPlayer.MakeScope.GetVariable('eu5ab_scope_province_count').GetValue|0] provinces / [GetPlayer.MakeScope.GetVariable('eu5ab_scope_area_count').GetValue|0] areas",
        "eu5ab_scope_expand_province_tt": "Expand this province and list the locations covered by the current template.",
        "eu5ab_scope_collapse_province_tt": "Collapse this province and hide its location list.",
        "eu5ab_scope_remove_location": "Remove",
        "eu5ab_scope_remove_location_tt": "Remove the template from this location and update its coverage.",
        "eu5ab_scope_clear_all": "Clear All Locations for This Template",
        "eu5ab_scope_clear_all_tt": "Remove all location assignments for this template and stop automated construction there. Other templates are unaffected.",
        "eu5ab_scope_map_mode_hint": "In the base game's Geography map modes, choose Advanced Auto Build Coverage: bright locations use the selected template and dark locations use another template from this Mod.",
        "mapmode_eu5ab_template_coverage_name": "Advanced Auto Build Coverage",
        "MAPMODE_EU5AB_TEMPLATE_COVERAGE": "#T $mapmode_eu5ab_template_coverage_name$#!\\nBright locations use the template selected in the template window. Dark locations use another template from this Mod. Uncolored locations have no template.",
        "eu5ab_scope_map_legend_selected": "Selected Template",
        "eu5ab_scope_map_legend_other": "Other Template",
        "eu5ab_scope_map_selected_tt": "This location uses the currently selected template.",
        "eu5ab_scope_map_other_tt": "This location uses another template from this Mod.",
        "eu5ab_scope_map_unassigned_tt": "This location has no template from this Mod.",
        "eu5ab_template_conflict_replace_desc": "Only locations without a template from this Mod can be selected. Applying to a province or area keeps existing assignments.",
        "eu5ab_open_panel_tooltip": "Open the regional development policy panel.",
        "eu5ab_open_regional_development_policy": "This Mod: View Automated Construction Controls",
        "eu5ab_open_regional_development_policy_desc": "Choose Advanced Auto Build in Community Mod Framework's Mod Settings.",
        "eu5ab_set_cash_reserve_0": "This Mod: Treasury Reserve 0",
        "eu5ab_set_cash_reserve_0_desc": "Set this location's automated-construction treasury reserve to 0.",
        "eu5ab_set_cash_reserve_500": "This Mod: Treasury Reserve 500",
        "eu5ab_set_cash_reserve_500_desc": "Set this location's automated-construction treasury reserve to 500.",
        "eu5ab_set_cash_reserve_1000": "This Mod: Treasury Reserve 1000",
        "eu5ab_set_cash_reserve_1000_desc": "Set this location's automated-construction treasury reserve to 1000.",
        "eu5ab_set_cash_reserve_2000": "This Mod: Treasury Reserve 2000",
        "eu5ab_set_cash_reserve_2000_desc": "Set this location's automated-construction treasury reserve to 2000.",
        "eu5ab_enable_special_buildings_for_location": "This Mod: Allow Special Buildings",
        "eu5ab_enable_special_buildings_for_location_desc": "Allow automated construction to build or upgrade special buildings in the selected location.",
        "eu5ab_disable_special_buildings_for_location": "This Mod: Ban Special Buildings",
        "eu5ab_disable_special_buildings_for_location_desc": "Prevent automated construction from building or upgrading special buildings in the selected location.",
        "eu5ab_decouple_selected_location": "This Mod: Stop Following Province Template",
        "eu5ab_decouple_selected_location_desc": "Future province template changes will no longer update the selected location.",
        "eu5ab_clear_selected_location_policy": "This Mod: Clear Location Policy",
        "eu5ab_clear_selected_location_policy_desc": "Select a location, then remove its template assignment and related settings.",
    }


def render_english_localization(policies: list[Policy], catalog: BuildingCatalog) -> str:
    values: dict[str, str] = {}
    values.update(_english_localization_values())
    values.update(_english_rules_localization_values())
    values.update(_english_diagnostics_localization_values())
    values.update(_english_scope_localization_values())
    values.update(_cmm_english_localization_values())
    values.update(rgo_localization.EN)
    values.update(GOVERNOR_ENGLISH_LOCALIZATION)
    values.update({
        "eu5ab_template_rules_window_title": "Construction Report",
        "eu5ab_open_rules_editor_button": "Construction Report",
        "eu5ab_automation_buildings_tab_desc": "Manage templates, building priorities, and coverage. Change rules shared by all templates in Community Mod Framework Mod Settings.",
        "eu5ab_action_bar_tooltip": "Manage regional-development templates, building priorities, and coverage, and review the latest automated construction result.",
        "eu5ab_template_editor_desc": "Name this template and configure its building priorities. Shared budget, market, workforce, and safety rules are in Community Mod Framework Mod Settings.",
        "eu5ab_template_editor_sections_title": "Template Settings",
        "eu5ab_template_editor_sections_desc": "Each template stores its enabled state, coverage, and building priorities. Open Construction Report to review the latest automated construction result.",
        "eu5ab_preset_readonly_desc": "Built-in presets have fixed priorities and can be paused, resumed, or assigned separately. Copy one as a player template to edit priorities. Shared rules are in CMF Mod Settings.",
        "eu5ab_pause_template_tooltip": "Pause or resume this template. Priorities and location assignments are kept, but automated construction skips these locations while paused.",
    })

    template_names = {
        "food_security": "Food Security",
        "mining_development": "Mining Development",
        "port_trade": "Port & Trade",
        "urban_industry": "Urban Industry",
        "military_frontier": "Military Frontier",
        "custom": "Custom",
    }
    for name_id, display in template_names.items():
        values[f"eu5ab_template_name_{name_id}"] = display

    for slot in TEMPLATE_SLOTS:
        display_name = f"$eu5ab_template_slot_{slot}_display_name$"
        values.update({
            f"eu5ab_template_slot_{slot}_title": f"Custom Template {slot}",
            f"eu5ab_template_slot_{slot}_display_name": _slot_display_name_expr(slot, player="GetPlayer"),
            f"eu5ab_template_slot_{slot}_editor_title": "Edit This Template",
            f"eu5ab_template_slot_{slot}_buildings_title": f"Custom Template {slot}: Building Rules",
            f"eu5ab_template_slot_{slot}_locations_title": f"Custom Template {slot}: Set Locations",
            f"eu5ab_template_slot_{slot}_summary": "This template stores its own enabled state, assigned locations, and building priorities. Change shared rules in Community Mod Framework's Mod Settings; Construction Report shows the latest automated construction result.",
            f"eu5ab_template_slot_{slot}_cash_value": "Shared treasury reserve: [GetPlayer.MakeScope.GetVariable('eu5ab_global_min_cash_reserve').GetValue|0Y]@gold!",
            f"eu5ab_template_slot_{slot}_price_min_value": "Shared minimum price: [GetPlayer.MakeScope.GetVariable('eu5ab_global_price_min').GetValue|0Y]%",
            f"eu5ab_template_slot_{slot}_price_max_value": "Shared high-price reference: [GetPlayer.MakeScope.GetVariable('eu5ab_global_price_max').GetValue|0Y]%",
            f"eu5ab_apply_template_slot_{slot}_to_selected_location": f"Apply {display_name} to Location",
            f"eu5ab_apply_template_slot_{slot}_to_selected_location_desc": f"Assign the {display_name} template to the selected owned location. Later template edits continue to apply.",
            f"eu5ab_apply_template_slot_{slot}_to_selected_province": f"Apply {display_name} to Province",
            f"eu5ab_apply_template_slot_{slot}_to_selected_province_desc": f"Assign the {display_name} template to owned locations without a template in the selected province.",
            f"eu5ab_apply_template_slot_{slot}_to_selected_area": f"Apply {display_name} to Area",
            f"eu5ab_apply_template_slot_{slot}_to_selected_area_desc": f"Assign the {display_name} template to owned locations without a template in the selected area.",
        })

    policy_english = {
        "granary": ("Granary", "Prioritizes food production and builds city or village granaries for provincial storage and preservation needs, reducing famine and high food-price risks."),
        "industrial_zone": ("Industrial Zone", "Prioritizes basic manufacturing, construction materials, and urban industrial supply."),
        "trade_center": ("Trade Center", "Prioritizes trade, storage, and commerce to enhance market access and trading revenue."),
        "naval_base": ("Naval Base", "Prioritizes ports, shipyards, and naval supplies to expand fleet construction capacity."),
        "frontier": ("Frontier", "Prioritizes fortifications, garrisons, and frontier infrastructure to enhance territorial defense and security."),
        "food_priority": ("Food Priority", "Expands high-value food production without designating the area as a dedicated granary."),
        "military_industry": ("Military Industry", "Prioritizes weaponry, artillery, and strategic metals to sustain national warfare capability."),
        "shipbuilding": ("Shipbuilding", "Prioritizes shipyards and upstream timber, naval stores, rope, and marine inputs."),
        "textiles": ("Textiles", "Expands the textile supply chain around cloth, cotton, wool, dyes, and silk."),
        "mining": ("Mining", "Prioritizes mines and quarries to extract metals, coal, gems, and strategic minerals."),
        "luxury_goods": ("Luxury Goods", "Pursues high-value luxury goods and precious metals to satisfy upper-strata demand and boost revenues."),
    }
    for policy in policies:
        name, description = policy_english.get(
            policy.id,
            (policy.id.replace("_", " ").title(), policy.role.replace("_", " ").title()),
        )
        values[policy.name_key] = name
        values[policy.description_key] = description
        values[f"eu5ab_apply_{policy.id}_to_selected_location"] = f"This Mod: Apply {name}"
        values[f"eu5ab_apply_{policy.id}_to_selected_location_desc"] = (
            f"Apply the {name} regional development template to the selected location. {description}"
        )
        values[f"eu5ab_apply_preset_{policy.id}_to_selected_location"] = f"This Mod: Apply {name}"
        values[f"eu5ab_apply_preset_{policy.id}_to_selected_location_desc"] = (
            f"Apply the {name} regional development template to the selected location. {description}"
        )
        values[f"eu5ab_apply_preset_{policy.id}_to_selected_province"] = (
            f"This Mod: Apply {name} to Province"
        )
        values[f"eu5ab_apply_preset_{policy.id}_to_selected_province_desc"] = (
            f"Apply the {name} template to owned locations in the selected province. {description}"
        )
        values[f"eu5ab_apply_preset_{policy.id}_to_selected_area"] = (
            f"This Mod: Apply {name} to Area"
        )
        values[f"eu5ab_apply_preset_{policy.id}_to_selected_area_desc"] = (
            f"Apply the {name} template to owned locations in the selected area. {description}"
        )

    chinese_lines = render_localization(policies, catalog).splitlines()
    english_lines = ["l_english:"]
    for line in chinese_lines[1:]:
        key, separator, raw_value = line.strip().partition(":")
        if not separator:
            continue
        original = raw_value.strip()
        original_text = original[1:-1] if original.startswith('"') and original.endswith('"') else original
        if original_text.startswith("$") and original_text.endswith("$"):
            english_text = original_text
        else:
            english_text = values.get(key)
            if english_text is None:
                readable = key
                for prefix in ("eu5ab_", "MAPMODE_EU5AB_", "mapmode_eu5ab_"):
                    if readable.startswith(prefix):
                        readable = readable[len(prefix):]
                        break
                english_text = readable.replace("_", " ").strip().title()
        if re.search(r"[\u3400-\u9fff]", english_text):
            raise ValueError(f"English localization contains Chinese text for {key}")
        escaped = english_text.replace('"', '\\"')
        english_lines.append(f' {key}: "{escaped}"')
    return "\n".join(english_lines) + "\n"


def generated_files(
    policies: list[Policy],
    catalog: BuildingCatalog | None = None,
    rules: AutomationRules | None = None,
    recipes: dict[str, BuildingProduction] | None = None,
    construction_demands: dict[str, ConstructionDemand] | None = None,
    game_root: Path | None = None,
    upgrades: BuildingUpgradeData | None = None,
    workforce: WorkforceModelData | None = None,
    straits: dict[str, list[str]] | None = None,
) -> dict[Path, str]:
    policy_ids = tuple(policy.id for policy in policies)
    if policy_ids != PRESET_TEMPLATE_IDS:
        raise ValueError(
            "Built-in preset list does not match policies/templates.json: "
            f"expected {PRESET_TEMPLATE_IDS}, got {policy_ids}"
        )
    if catalog is None:
        catalog = load_building_catalog(CATALOG_FILE)
    if rules is None:
        rules = load_automation_rules(RULES_FILE)
    source_root: Path | None = None
    if (
        recipes is None
        or construction_demands is None
        or upgrades is None
        or workforce is None
        or straits is None
    ):
        source_root = require_game_root(game_root)
    if recipes is None:
        recipes = extract_production_models(source_root, catalog)
    if construction_demands is None:
        construction_demands = extract_supported_construction_demands(
            source_root, catalog
        )
    if upgrades is None:
        upgrades = extract_building_upgrades(source_root, catalog)
    if workforce is None:
        workforce = extract_workforce_model(source_root, catalog)
    if straits is None:
        straits = extract_straits(source_root)
    industries = industry_promotion.extract_industries(source_root) if source_root is not None else industry_promotion.load_industries()
    if source_root is not None:
        if rgo_automation.extract_raw_goods(source_root) != rgo_automation.raw_goods():
            raise ValueError("Raw-good snapshot differs from vanilla; refresh .metadata/eu5ab_raw_goods.json")
        rgo_base_costs = extract_rgo_base_costs(source_root)
        mirrored_rgo_base_cost = float(rules.thresholds.rgo_budget_cost)
        if set(rgo_base_costs.values()) != {mirrored_rgo_base_cost}:
            raise ValueError(
                "RGO base-cost mirror does not match vanilla prices: "
                f"mirror={mirrored_rgo_base_cost:g}, vanilla={rgo_base_costs}"
            )
    unknown_priority_buildings = set(rules.building_priorities.overrides) - set(catalog.buildings)
    if unknown_priority_buildings:
        raise ValueError(
            "Automation building priorities reference unknown catalog ids: "
            f"{sorted(unknown_priority_buildings)}"
        )
    chinese_localization = render_localization(policies, catalog)
    english_localization = render_english_localization(policies, catalog)
    forecast_effects, forecast_triggers, forecast_values = market_supply.render(recipes, rules, upgrades)
    forecast_effects += annual_budget.render_effects() + annual_budget.render_scan_date()
    market_cache_effects, market_cache_triggers, market_cache_values = market_price_cache.render(
        recipes, catalog, rules, required_goods=output_prices.price_goods(recipes, rules)
    )
    files = {
        ROOT / ".metadata" / "metadata.json": render_metadata(),
        ROOT / ".metadata" / "eu5ab_governor_connections.json": straits_json(straits),
        industry_promotion.SNAPSHOT: json.dumps(industries, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        ROOT / ".metadata" / "eu5ab_production_recipes.json": production_models_as_json(recipes),
        ROOT / ".metadata" / "eu5ab_construction_demands.json": construction_demands_as_json(
            construction_demands
        ),
        ROOT / ".metadata" / "eu5ab_building_upgrades.json": building_upgrades_as_json(upgrades),
        ROOT / ".metadata" / "eu5ab_workforce_model.json": workforce_model_as_json(workforce),
        ROOT / "in_game" / "common" / "on_action" / "eu5ab_on_actions.txt": render_on_actions(),
        ROOT / "in_game" / "events" / "eu5ab_monthly_events.txt": render_events(),
        ROOT / "in_game" / "events" / "eu5ab_governor_events.txt": render_governor_events(),
        ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_scripted_effects.txt": render_needs_scripted_effects(policies, catalog, rules, construction_demands, upgrades) + render_workforce_cache_effects(workforce, upgrades) + render_production(recipes, rules, score_buildings=set(_catalog_building_ids(catalog)))[2] + queue_validation.render_effects() + building_capacity.render_effects() + native_recipes.render(recipes, upgrades)[0] + construction_slots.render()[0] + project_tracking.render(rules, recipes)[0] + forecast_effects + market_cache_effects + queue_ranking.render(len(CANDIDATE_PRIORITY_FEATURES) * 4, rules.cadence.deep_score_location_limit),
        ROOT / "in_game" / "common" / "scripted_effects" / "eu5ab_governor_effects.txt": render_governor_effects(straits),
        ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_scripted_triggers.txt": render_needs_scripted_triggers(policies, catalog, rules, upgrades, construction_demands, recipes) + render_production(recipes, rules)[0] + output_prices.render(recipes, rules)[0] + construction_slots.render()[1] + project_tracking.render(rules, recipes)[1] + forecast_triggers + market_cache_triggers + monthly_schedule.render_triggers(),
        ROOT / "in_game" / "common" / "scripted_triggers" / "eu5ab_governor_triggers.txt": render_governor_triggers(),
        ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt": render_needs_script_values(
            policies,
            catalog,
            rules,
            recipes,
            workforce,
            upgrades,
            construction_demands,
            industries,
        ) + forecast_values + market_cache_values + queued_workforce.render(workforce, upgrades) + annual_budget.render_values(),
        ROOT / "in_game" / "common" / "script_values" / "eu5ab_governor_values.txt": render_governor_script_values(
            registered_dlcs=registered_dlc_names(source_root) if source_root is not None else frozenset()),
        ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_scripted_guis.txt": render_scripted_guis(policies, catalog, rules) + native_recipes.render(recipes)[2] + construction_slots.render()[3] + project_tracking.render_guis() + queue_ranking.GUI + production_forecast.render_guis(),
        ROOT / "in_game" / "common" / "scripted_guis" / "eu5ab_governor_scripted_guis.txt": render_governor_scripted_guis(),
        ROOT / "in_game" / "common" / "generic_actions" / "eu5ab_development_policy_actions.txt": render_actions(policies, catalog),
        ROOT / "in_game" / "gfx" / "map" / "map_modes" / "eu5ab_template_coverage.txt": render_template_scope_map_mode(),
        ROOT / "in_game" / "gui" / "eu5ab_automation_buildings_window.gui": render_gui(policies, catalog),
        ROOT / "in_game" / "gui" / "eu5ab_engine_queue_window.gui": render_engine_queue_gui(),
        ROOT / "in_game" / "gui" / "eu5ab_governor_recommendation_window.gui": render_governor_gui(),
        ROOT / "in_game" / "gui" / "eu5ab_governor_worker.gui": render_layout_worker_gui(),
        ROOT / "in_game" / "gui" / "eu5ab_template_editor_window.gui": render_template_editor_gui(policies, catalog),
        ROOT / "in_game" / "gui" / "eu5ab_template_buildings_window.gui": render_active_template_buildings_gui(catalog),
        ROOT / "in_game" / "gui" / "eu5ab_template_rules_window.gui": render_active_template_rules_gui(),
        ROOT / "in_game" / "gui" / "eu5ab_template_rename_window.gui": render_template_rename_gui(policies, catalog),
        ROOT / "in_game" / "gui" / "eu5ab_template_scope_window.gui": render_template_scope_gui(policies),
        ROOT / "in_game" / "gui" / "scripted_widgets" / "eu5ab_scripted_windows.txt": render_scripted_windows(),
        ROOT / "in_game" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml": chinese_localization,
        ROOT / "main_menu" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml": chinese_localization,
        ROOT / "in_game" / "localization" / "english" / "eu5ab_l_english.yml": english_localization,
        ROOT / "main_menu" / "localization" / "english" / "eu5ab_l_english.yml": english_localization,
    }
    from .recipe_snapshot import bind_score_values
    for folder, text in zip(('scripted_effects', 'scripted_triggers', 'script_values', 'scripted_guis'), upgrade_queue.render(upgrades)):
        files[ROOT / 'in_game' / 'common' / folder / ('eu5ab_' + folder + '.txt')] += '\n' + text
    for folder, text in zip(('scripted_effects', 'scripted_triggers', 'script_values', 'scripted_guis'), industry_promotion.render()):
        files[ROOT / 'in_game' / 'common' / folder / ('eu5ab_' + folder + '.txt')] += '\n' + text
    score_path = ROOT / "in_game" / "common" / "script_values" / "eu5ab_script_values.txt"
    files[score_path] = bind_score_values(files[score_path])
    from . import construction_batch
    construction_batch.apply(files, ROOT, recipes, construction_demands, rules,
                             _replace_top_level_script_block)
    from . import worker_screening
    worker_screening.apply(files, ROOT)
    from . import worker_upgrades
    worker_upgrades.apply(files, ROOT, upgrades, workforce, _catalog_building_ids(catalog))
    from . import rgo_screening
    rgo_screening.apply(files, ROOT)
    from . import scan_probe
    scan_probe.apply(files, ROOT, _replace_top_level_script_block)
    from . import manual_decisions
    manual_decisions.apply(files, ROOT, GLOBAL_RULE_DEFAULTS, PRESET_TEMPLATE_IDS,
                           len(_catalog_building_ids(catalog)), _replace_top_level_script_block)
    chinese_localization = files[ROOT / 'in_game/localization/simp_chinese/eu5ab_l_simp_chinese.yml']
    english_localization = files[ROOT / 'in_game/localization/english/eu5ab_l_english.yml']
    for language in ENGLISH_FALLBACK_LANGUAGES:
        translation_catalog = load_translation_catalog(
            TRANSLATION_ROOT / f"{language}.json",
            language,
        )
        translated_localization = render_translated_localization(
            chinese_localization,
            english_localization,
            translation_catalog,
        )
        for game_layer in ("in_game", "main_menu"):
            files[
                ROOT
                / game_layer
                / "localization"
                / language
                / f"eu5ab_l_{language}.yml"
            ] = translated_localization
    # Override framework strings through the engine's replacement localization
    # layer; ordinary Mod catalogs contain only our namespaced translations.
    for language in ("simp_chinese", "english", *ENGLISH_FALLBACK_LANGUAGES):
        overrides = f"l_{language}:\n" + "\n".join(
            f' {key}: "$EU5AB_{key}$"'
            for key in (
                "CMM_NUMERIC_INCREASE_MAX", "CMM_NUMERIC_DECREASE_MIN",
                "CMM_NUMERIC_INCREASE_5X", "CMM_NUMERIC_DECREASE_5X",
            )
        ) + "\n"
        for layer in ("in_game", "main_menu"):
            files[ROOT / layer / "localization" / "replace" / f"eu5ab_cmm_overrides_l_{language}.yml"] = overrides
    files[ROOT / "in_game" / "common" / "script_values" / "eu5ab_ui_values.txt"] = render_ui_script_values()
    # Run after all specializations/copies: sparse-map membership must be safe
    # in every consumer, including negated cache misses and saved-state views.
    from .map_access import guard_map_membership
    for path in files:
        if path.suffix == ".txt":
            files[path] = guard_map_membership(files[path])
    return {
        path: _normalize_generated_text(bind_ui_values(content) if path.suffix in {".gui", ".yml"} else content)
        for path, content in files.items()
    }


def generate(game_root: Path | None = None) -> list[Path]:
    policies = load_policies(POLICY_FILE)
    catalog = load_building_catalog(CATALOG_FILE)
    rules = load_automation_rules(RULES_FILE)
    files = generated_files(policies, catalog, rules, game_root=game_root)
    written: list[Path] = []
    for path, content in files.items():
        if path.suffix in {".txt", ".gui"} and not _balanced_script(content):
            raise ValueError(f"Generated script is not balanced: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        _write_generated_file(path, content)
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--game-root",
        type=Path,
        help="EU5 installation root; defaults to the EU5_GAME_ROOT environment variable.",
    )
    parser.add_argument("--check", action="store_true", help="Validate generated content without writing files.")
    args = parser.parse_args()
    policies = load_policies(POLICY_FILE)
    catalog = load_building_catalog(CATALOG_FILE)
    rules = load_automation_rules(RULES_FILE)
    try:
        files = generated_files(
            policies,
            catalog,
            rules,
            game_root=args.game_root,
        )
    except FileNotFoundError as error:
        parser.error(str(error))
    for path, content in files.items():
        if path.suffix in {".txt", ".gui"} and not _balanced_script(content):
            raise ValueError(f"Generated script is not balanced: {path}")
    if not args.check:
        for path, content in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_generated_file(path, content)
        print(f"Generated {len(files)} files.")
    else:
        chinese_localization = files[
            ROOT / "in_game" / "localization" / "simp_chinese" / "eu5ab_l_simp_chinese.yml"
        ]
        english_localization = files[
            ROOT / "in_game" / "localization" / "english" / "eu5ab_l_english.yml"
        ]
        for language in ENGLISH_FALLBACK_LANGUAGES:
            catalog = load_translation_catalog(
                TRANSLATION_ROOT / f"{language}.json",
                language,
            )
            report = translation_report(
                chinese_localization,
                english_localization,
                catalog,
            )
            print(
                f"{language}: translated={len(report.translated)} "
                f"missing={len(report.missing)} changed={len(report.changed)} "
                f"obsolete={len(report.obsolete)}"
            )
            for label, keys in (
                ("missing", report.missing),
                ("changed", report.changed),
                ("obsolete", report.obsolete),
            ):
                if keys:
                    print(f"  {label}: {', '.join(keys)}")


if __name__ == "__main__":
    main()
