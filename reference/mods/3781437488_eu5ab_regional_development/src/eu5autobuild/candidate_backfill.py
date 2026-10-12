"""Bounded, opt-in candidate backfill. All worker mutations stay on the location."""

CLASSES = ("upgrade", "expansion", "new")
POOLS = tuple(f"eu5ab_backfill_{kind}_candidates" for kind in CLASSES)
COUNTERS = (
    "triggered", "checked", "input_rejected", "output_rejected",
    "stage_failed", "staged", "budget_exhausted", "upstream_rechecks",
)
SCRATCH = (
    "country", "budget", "remaining", "rank", "head_limit", "window_limit",
    "stage_before", "done", "food_layer", "consumed",
)
SCORE_CACHE = "eu5ab_candidate_sort_scores"
CACHED_SCORE = "eu5ab_candidate_sort_score"


def _upsert_increment(name: str, add: str = "1") -> str:
    """Increment numeric state without asking EU5 to mutate an unset variable."""
    return (
        f"if = {{ limit = {{ has_variable = {name} }} "
        f"change_variable = {{ name = {name} add = {add} }} }} "
        f"else = {{ set_variable = {{ name = {name} value = {add} }} }}"
    )


def snapshot_lines() -> list[str]:
    return [
        "\t# Snapshot the CMM setting only at scan start.",
        "\tremove_variable = eu5ab_scan_backfill_enabled",
        "\tif = { limit = { var:eu5ab_global_candidate_backfill_enabled > 0 } set_variable = eu5ab_scan_backfill_enabled }",
        *(f"\tremove_variable = eu5ab_diag_backfill_{name}" for name in COUNTERS),
    ]


def merge_lines() -> list[str]:
    return [
        f"\t\tif = {{ limit = {{ has_variable = eu5ab_worker_backfill_{name} }} scope:eu5ab_worker_merge_country = {{ {_upsert_increment(f'eu5ab_diag_backfill_{name}', f'scope:eu5ab_candidate_location.var:eu5ab_worker_backfill_{name}')} }} }}"
        for name in COUNTERS
    ] + [f"\t\tremove_variable = eu5ab_worker_backfill_{name}" for name in COUNTERS]


def iterator_lines(pool: str, maximum: str, body: list[str]) -> list[str]:
    """Rank the prepared score snapshot; expand only ordinary pools when enrolled."""
    def ordered(cap: str, entries: list[str]) -> list[str]:
        return [
            "\t\tordered_in_list = {",
            f"\t\t\tvariable = {pool}", f"\t\t\tmax = {cap}",
            "\t\t\tlimit = { eu5ab_candidate_has_capacity = yes }",
            "\t\t\tcheck_range_bounds = no",
            f"\t\t\torder_by = {CACHED_SCORE}",
            "\t\t\tsave_scope_as = eu5ab_candidate_building",
            *entries,
            "\t\t}",
        ]

    if "_input_" in pool:
        return ordered(maximum, [
            "\t\t\tif = { limit = { scope:eu5ab_candidate_location = { has_variable = eu5ab_backfill_country } } scope:eu5ab_candidate_location = { eu5ab_record_backfill_upstream_check = yes } }",
            *body,
        ])
    kind = next(kind for kind in CLASSES if pool == f"eu5ab_current_{kind}_candidate_pool")
    expanded = [
        "\t\t\tif = {",
        "\t\t\t\tlimit = { scope:eu5ab_candidate_location = { var:eu5ab_backfill_rank <= var:eu5ab_backfill_head_limit } }",
        *("\t\t" + line for line in body),
        "\t\t\t}",
        "\t\t\telse = {",
        f"\t\t\t\tscope:eu5ab_candidate_location = {{ add_to_variable_list = {{ name = eu5ab_backfill_{kind}_candidates target = scope:eu5ab_candidate_building }} }}",
        "\t\t\t}",
        "\t\t\tscope:eu5ab_candidate_location = { change_variable = { name = eu5ab_backfill_rank add = 1 } }",
    ]
    return [
        "\t\tif = {",
        "\t\t\tlimit = { has_variable = eu5ab_backfill_country }",
        f"\t\t\tset_variable = {{ name = eu5ab_backfill_head_limit value = {maximum} }}",
        "\t\t\tset_variable = { name = eu5ab_backfill_window_limit value = { value = var:eu5ab_backfill_head_limit add = var:eu5ab_backfill_budget } }",
        "\t\t\tset_variable = { name = eu5ab_backfill_rank value = 1 }",
        *("\t" + line for line in ordered("var:eu5ab_backfill_window_limit", expanded)),
        "\t\t\tremove_variable = eu5ab_backfill_rank",
        "\t\t\tremove_variable = eu5ab_backfill_head_limit",
        "\t\t\tremove_variable = eu5ab_backfill_window_limit",
        "\t\t}",
        "\t\telse = {",
        *("\t" + line for line in ordered(maximum, body)),
        "\t\t}",
    ]


def render_effects(*, planning_default: int, profit_default: int) -> str:
    planning_budget = (planning_default + 1) // 2
    profit_budget = (profit_default + 1) // 2
    lines = [
        "eu5ab_clear_backfill_scratch = {",
        *(f"\tclear_variable_list = {pool}" for pool in POOLS),
        "\tclear_variable_list = eu5ab_backfill_upstream_checked",
        *(f"\tremove_variable = eu5ab_backfill_{name}" for name in SCRATCH),
        "}",
        "eu5ab_clear_backfill_worker_state = {",
        "\teu5ab_clear_backfill_scratch = yes",
        "\tremove_variable = eu5ab_backfill_dispatch_country",
        *(f"\tremove_variable = eu5ab_worker_backfill_{name}" for name in COUNTERS),
        "}",
        "eu5ab_prepare_backfill_dispatch = {",
        "\tremove_variable = eu5ab_backfill_dispatch_country",
        "\tif = {",
        "\t\tlimit = { owner = scope:eu5ab_scan_country owner = { has_variable = eu5ab_scan_active has_variable = eu5ab_scan_backfill_enabled } }",
        "\t\tset_variable = { name = eu5ab_backfill_dispatch_country value = owner }",
        "\t}",
        "}",
        "eu5ab_initialize_candidate_backfill = {",
        "\tsave_scope_as = eu5ab_candidate_location",
        "\tif = {",
        "\t\tlimit = {",
        "\t\t\towner = scope:eu5ab_backfill_dispatch_country",
        "\t\t\towner = { has_variable = eu5ab_scan_active has_variable = eu5ab_scan_backfill_enabled is_target_in_variable_list = { name = eu5ab_worker_pending_locations target = scope:eu5ab_candidate_location } }",
        "\t\t}",
        "\t\tset_variable = { name = eu5ab_backfill_country value = owner }",
        f"\t\tset_variable = {{ name = eu5ab_backfill_budget value = {planning_budget} }}",
        f"\t\tif = {{ limit = {{ owner.var:eu5ab_global_candidate_ranking_mode = 2 }} set_variable = {{ name = eu5ab_backfill_budget value = {profit_budget} }} }}",
        "\t}",
        "}",
        "eu5ab_record_backfill_upstream_check = {",
        "\tif = {",
        "\t\tlimit = { OR = {",
        *(f"\t\t\tis_target_in_variable_list = {{ name = {pool} target = scope:eu5ab_candidate_building }}" for pool in POOLS),
        "\t\t} NOT = { is_target_in_variable_list = { name = eu5ab_backfill_upstream_checked target = scope:eu5ab_candidate_building } } }",
        "\t\tadd_to_variable_list = { name = eu5ab_backfill_upstream_checked target = scope:eu5ab_candidate_building }",
        "\t}",
        "}",
        "# Root is the building; never run the mutating ordinary failure chain here.",
        "eu5ab_check_backfill_candidate = {",
        "\tscope:eu5ab_candidate_location = {",
        "\t\tchange_variable = { name = eu5ab_backfill_remaining subtract = 1 }",
        f"\t\t{_upsert_increment('eu5ab_worker_backfill_checked')}",
        f"\t\tif = {{ limit = {{ is_target_in_variable_list = {{ name = eu5ab_backfill_upstream_checked target = scope:eu5ab_candidate_building }} }} {_upsert_increment('eu5ab_worker_backfill_upstream_rechecks')} }}",
        "\t}",
        f"\tif = {{ limit = {{ NOT = {{ eu5ab_inputs_available = yes }} }} scope:eu5ab_candidate_location = {{ {_upsert_increment('eu5ab_worker_backfill_input_rejected')} }} }}",
        f"\telse_if = {{ limit = {{ NOT = {{ eu5ab_output_not_oversupplied = yes }} }} scope:eu5ab_candidate_location = {{ {_upsert_increment('eu5ab_worker_backfill_output_rejected')} }} }}",
        "\telse = {",
        "\t\tscope:eu5ab_candidate_location = {",
        "\t\t\tset_variable = { name = eu5ab_backfill_stage_before value = var:eu5ab_worker_staged }",
        "\t\t\teu5ab_stage_engine_candidate = yes",
        "\t\t\tif = {",
        "\t\t\t\tlimit = { var:eu5ab_worker_staged > var:eu5ab_backfill_stage_before }",
        "\t\t\t\tset_variable = eu5ab_backfill_done",
        f"\t\t\t\t{_upsert_increment('eu5ab_worker_backfill_staged')}",
        "\t\t\t}",
        f"\t\t\telse = {{ {_upsert_increment('eu5ab_worker_backfill_stage_failed')} }}",
        "\t\t\tremove_variable = eu5ab_backfill_stage_before",
        "\t\t}",
        "\t}",
        "}",
    ]
    for kind, pool in zip(CLASSES, POOLS, strict=True):
        priority_feature = "expand" if kind == "expansion" else kind
        lines.extend([
            f"eu5ab_visit_backfill_{kind}_candidates = {{",
            "\tif = { limit = { var:eu5ab_backfill_remaining > 0 NOT = { has_variable = eu5ab_backfill_done } }",
            f"\t\tset_variable = {{ name = eu5ab_stage_candidate_priority value = owner.var:eu5ab_candidate_priority_{priority_feature} }}",
            "\t\tevery_in_list = {",
            f"\t\t\tvariable = {pool}",
            "\t\t\tif = { limit = { scope:eu5ab_candidate_location = { var:eu5ab_backfill_remaining > 0 NOT = { has_variable = eu5ab_backfill_done } NOT = { has_variable = eu5ab_action_taken } owner = var:eu5ab_backfill_country owner = { has_variable = eu5ab_scan_active has_variable = eu5ab_scan_backfill_enabled } } }",
            "\t\t\t\tsave_scope_as = eu5ab_candidate_building",
            "\t\t\t\tif = { limit = { scope:eu5ab_candidate_location = { OR = { AND = { has_variable = eu5ab_backfill_food_layer eu5ab_engine_candidate_is_food_emergency = yes } AND = { NOT = { has_variable = eu5ab_backfill_food_layer } NOT = { eu5ab_engine_candidate_is_food_emergency = yes } } } } } eu5ab_check_backfill_candidate = yes }",
            "\t\t\t}", "\t\t}",
            "\t\tremove_variable = eu5ab_stage_candidate_priority",
            "\t}", "}",
        ])
    lines.extend([
        "eu5ab_visit_backfill_layer = {",
        "\towner = {",
        "\t\tif = { limit = { has_variable_list = eu5ab_candidate_priority_features }",
        "\t\t\tevery_in_list = { variable = eu5ab_candidate_priority_features save_scope_as = eu5ab_priority_feature",
        "\t\t\t\tscope:eu5ab_candidate_location = { switch = { trigger = scope:eu5ab_priority_feature",
        "\t\t\t\t\tflag:eu5ab_feature_upgrade_building = { eu5ab_visit_backfill_upgrade_candidates = yes }",
        "\t\t\t\t\tflag:eu5ab_feature_expand_building = { eu5ab_visit_backfill_expansion_candidates = yes }",
        "\t\t\t\t\tflag:eu5ab_feature_new_building = { eu5ab_visit_backfill_new_candidates = yes }",
        "\t\t\t\t\tflag:eu5ab_feature_expand_rgo = { }",
        "\t\t\t\t} }", "\t\t\t}", "\t\t}",
        "\t\telse = { scope:eu5ab_candidate_location = { eu5ab_visit_backfill_upgrade_candidates = yes eu5ab_visit_backfill_expansion_candidates = yes eu5ab_visit_backfill_new_candidates = yes } }",
        "\t}", "}",
        "eu5ab_try_candidate_backfill = {",
        "\tsave_scope_as = eu5ab_candidate_location",
        "\tif = { limit = {",
        "\t\thas_variable = eu5ab_worker_active has_variable = eu5ab_backfill_country",
        "\t\tNOT = { has_variable = eu5ab_backfill_consumed }",
        "\t\tNOT = { has_variable = eu5ab_action_taken } NOT = { has_variable = eu5ab_ordinary_candidate_staged }",
        "\t\towner = var:eu5ab_backfill_country owner = { has_variable = eu5ab_scan_active has_variable = eu5ab_scan_backfill_enabled }",
        "\t\tvar:eu5ab_backfill_budget > 0 OR = {",
        *(f"\t\t\thas_variable_list = {pool}" for pool in POOLS),
        "\t\t} }",
        "\t\tset_variable = eu5ab_backfill_consumed",
        f"\t\t{_upsert_increment('eu5ab_worker_backfill_triggered')}",
        "\t\tset_variable = { name = eu5ab_backfill_remaining value = var:eu5ab_backfill_budget }",
        "\t\tset_variable = eu5ab_backfill_food_layer",
        "\t\teu5ab_visit_backfill_layer = yes",
        "\t\tremove_variable = eu5ab_backfill_food_layer",
        "\t\teu5ab_visit_backfill_layer = yes",
        f"\t\tif = {{ limit = {{ var:eu5ab_backfill_remaining <= 0 NOT = {{ has_variable = eu5ab_backfill_done }} }} {_upsert_increment('eu5ab_worker_backfill_budget_exhausted')} }}",
        "\t}", "}", "",
    ])
    return "\n".join(lines)
